"""
06 | Build the analysis cube straight from interim/parts/  -> processed/
     No combine step required.

    python 06_build_analysis_cube.py

Reads the regridded ORAS5 parts lazily, keeps only the 2D fields, merges in
ERA5 and altimetry, and writes:
    processed/bob_analysis_cube.nc    2D fields on the common grid
    processed/bob_tidy.parquet        long format, one row per cell-month

WHY THIS IS FAST WHERE THE COMBINE STEP WAS SLOW
Combining rewrote every part, including 3D fields with 30+ depth levels,
through zlib compression. This script drops the 3D fields as each file is
opened, so they never enter memory or get rewritten. What remains is roughly
60 MB, not tens of gigabytes.

If your run still crawls, the cause is almost always the number of files.
CDS ORAS5 unpacks to one file per variable per month, which is ~3,400 files
for 1993-2020. Opening that many is slow no matter what. Run with
--consolidate once to rewrite the parts as one file per year, after which
every later run is quick.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import common as C


# ------------------------------------------------------------------ inputs
def load_era5():
    if not C.ERA5_FILE.exists():
        print(f"  WARNING: {C.ERA5_FILE} missing, continuing without ERA5")
        return None
    ds = xr.open_dataset(C.ERA5_FILE)
    tname = C.time_name(ds)
    if tname and tname != "time":
        ds = ds.rename({tname: "time"})
    keep = [v for v in ("wind_speed", "wind_speed_cubed", "tau_mag",
                        "ekman_pumping", "qnet", "p_minus_e", "msl")
            if v in ds.data_vars]
    if not keep:
        print(f"  WARNING: no expected ERA5 variables in {C.ERA5_FILE}")
        return None
    print(f"  ERA5 variables: {keep}")
    return C.to_month_start(ds[keep])


def load_altimetry(target_lat, target_lon):
    files = sorted(C.ALT_DIR.glob("*.nc"))
    if not files:
        print("  WARNING: no altimetry found, EKE and SLA omitted")
        return None
    ds = (xr.open_mfdataset(files, combine="by_coords")
          if len(files) > 1 else xr.open_dataset(files[0]))

    latn = "latitude" if "latitude" in ds.dims else "lat"
    lonn = "longitude" if "longitude" in ds.dims else "lon"
    if "ugosa" not in ds or "vgosa" not in ds:
        print(f"  WARNING: ugosa/vgosa absent, EKE skipped. "
              f"Present: {list(ds.data_vars)}")
        return None

    # EKE on DAILY anomalies, THEN averaged monthly. Averaging the velocities
    # first and squaring afterwards removes the eddy variance being measured.
    eke = 0.5 * (ds["ugosa"] ** 2 + ds["vgosa"] ** 2)
    eke.attrs = {"units": "m2 s-2",
                 "long_name": "eddy kinetic energy from geostrophic anomalies",
                 "comment": "0.5*(ugosa^2+vgosa^2) daily, then monthly mean"}
    keep = {"eke": eke}
    if "sla" in ds:
        keep["sla"] = ds["sla"]

    monthly = xr.Dataset(keep).resample(time="MS").mean()
    monthly = monthly.rename({latn: "lat", lonn: "lon"})
    monthly = monthly.interp(lat=target_lat, lon=target_lon, method="linear")
    print(f"  altimetry variables: {list(monthly.data_vars)}")
    return C.to_month_start(monthly).load()


# ------------------------------------------------------------- consolidation
def consolidate(parts_dir):
    """Rewrite thousands of small parts as one file per year. Run once."""
    files = sorted(Path(parts_dir).glob("*.nc"))
    print(f"consolidating {len(files)} parts by year ...")
    ds = C.open_oras5(parts_dir)
    ds = C.to_month_start(ds).load()
    out_dir = parts_dir.parent / "parts_yearly"
    out_dir.mkdir(exist_ok=True)
    for year, chunk in ds.groupby("time.year"):
        target = out_dir / f"oras5_bob_{year}.nc"
        enc = {v: {"zlib": True, "complevel": 4} for v in chunk.data_vars}
        chunk.to_netcdf(target, encoding=enc)
        print(f"  {target.name}  ({chunk.sizes['time']} months)")
    print(f"\ndone -> {out_dir}")
    print("Now set ORAS5_PARTS = INTERIM / 'parts_yearly' in common.py")


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default=str(C.ORAS5_PARTS))
    ap.add_argument("--consolidate", action="store_true",
                    help="rewrite parts as one file per year, then exit")
    a = ap.parse_args()
    parts = Path(a.parts)

    if a.consolidate:
        consolidate(parts)
        return

    print("loading ORAS5 parts ...")
    oras = C.to_month_start(C.open_oras5(parts))

    print("\nloading forcing ...")
    era = load_era5()
    alt = load_altimetry(oras["lat"], oras["lon"])

    parts_list = [oras] + [d for d in (era, alt) if d is not None]
    names = ["ORAS5"] + [n for n, d in (("ERA5", era), ("DUACS", alt)) if d is not None]

    print("\ntime coverage:")
    for nm, p in zip(names, parts_list):
        t = pd.to_datetime(p.time.values)
        print(f"  {nm:6} {t.min():%Y-%m} -> {t.max():%Y-%m}  ({p.sizes['time']} months)")

    common_t = parts_list[0].time.values
    for p in parts_list[1:]:
        common_t = np.intersect1d(common_t, p.time.values)
    if common_t.size == 0:
        raise SystemExit(
            "no overlapping months across the inputs.\n"
            "Most likely the time axes decoded differently. Check that every "
            "input has CF units and calendar on its time variable."
        )
    t0, t1 = pd.to_datetime(common_t.min()), pd.to_datetime(common_t.max())
    print(f"  common: {t0:%Y-%m} -> {t1:%Y-%m} "
          f"({common_t.size} months, {common_t.size/12:.1f} years)")
    if common_t.size < 120:
        print("  WARNING: fewer than 10 years in common. Trend and decadal")
        print("           analysis will be weak. Check the inputs before going on.")

    print("\nmerging ...")
    ds = xr.merge([p.sel(time=common_t) for p in parts_list], join="exact")
    ds = ds.load()

    ds["sub_basin"] = C.sub_basin_labels(ds["lat"])
    ocean = np.isfinite(ds["mld"]).any("time")
    ds = ds.where(ocean)
    print(f"  ocean cells: {int(ocean.sum())} of {ocean.size}")

    ds.attrs["title"] = "Bay of Bengal mixed layer analysis cube"
    ds.attrs["history"] = (
        f"{pd.Timestamp.utcnow():%Y-%m-%dT%H:%M:%SZ}: merged ORAS5 parts, ERA5 "
        "and DUACS on a common 0.25 deg monthly grid (06_build_analysis_cube.py)"
    )
    ds.attrs["sub_basins"] = (
        f"north >= {C.LAT_N_MIN}N; central {C.LAT_C_MIN}-{C.LAT_N_MIN}N; "
        f"south < {C.LAT_C_MIN}N"
    )

    enc = {v: {"zlib": True, "complevel": 4}
           for v in ds.data_vars if ds[v].dtype.kind == "f"}
    ds.to_netcdf(C.CUBE, encoding=enc)
    print(f"\nwrote {C.CUBE}  ({C.CUBE.stat().st_size/2**20:.1f} MiB)")

    df = ds.to_dataframe().reset_index().dropna(subset=["mld"])
    df["year"] = df["time"].dt.year
    df["month"] = df["time"].dt.month
    df.to_parquet(C.TIDY, index=False)
    print(f"wrote {C.TIDY}  ({len(df):,} rows, {df.shape[1]} columns)")

    print("\nmissing data per variable (% of ocean rows):")
    for c in sorted(df.columns):
        if df[c].dtype.kind == "f":
            pct = 100 * df[c].isna().mean()
            flag = "   <- check this" if pct > 20 else ""
            print(f"  {c:<18} {pct:5.2f}%{flag}")

    print("\nquick sanity on MLD:")
    m = df["mld"]
    print(f"  range {m.min():.1f} .. {m.max():.1f} m, mean {m.mean():.1f} m")
    if m.max() > 500 or m.min() < 0:
        print("  WARNING: values outside a physical range for this basin")


if __name__ == "__main__":
    main()
