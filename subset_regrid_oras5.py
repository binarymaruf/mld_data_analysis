"""
05 | Cut the Bay of Bengal out of global ORAS5 files and put everything on a
     common 0.25-degree lat/lon grid  ->  data/interim/

THE PROBLEM THIS SOLVES
ORAS5 files carry 2D coordinate arrays nav_lat(y,x) and nav_lon(y,x) on the
tripolar ORCA025 grid. The dimensions y and x are grid INDICES, not degrees.
    ds.sel(lat=slice(5, 23))            # fails, no such coordinate
    ds.isel(y=slice(600, 700))          # runs, but the box is wrong
You must mask on the 2D coordinate arrays, then interpolate.

The Bay of Bengal sits well inside the tropics, far from the northern
tripole seam, so the ORCA grid is close to regular here and bilinear
interpolation is safe. That would not be true in the Arctic.
"""

from pathlib import Path
import numpy as np
import xarray as xr

RAW = Path("data/raw/oras5")
OUT = Path("data/interim")
OUT.mkdir(parents=True, exist_ok=True)

LON_MIN, LON_MAX = 80.0, 100.0
LAT_MIN, LAT_MAX = 5.0, 23.0
PAD = 2.0  # margin so interpolation has neighbours at the edges

TARGET_LON = np.arange(LON_MIN, LON_MAX + 0.25, 0.25)
TARGET_LAT = np.arange(LAT_MIN, LAT_MAX + 0.25, 0.25)


def find_coord_names(ds):
    lat = next((n for n in ("nav_lat", "latitude", "lat") if n in ds), None)
    lon = next((n for n in ("nav_lon", "longitude", "lon") if n in ds), None)
    if lat is None or lon is None:
        raise KeyError(f"no lat/lon coords found in {list(ds.variables)}")
    return lat, lon


def crop_index_box(ds):
    """Shrink to the index window covering the padded basin, before interp."""
    latn, lonn = find_coord_names(ds)
    lat2d, lon2d = ds[latn], ds[lonn]

    if lat2d.ndim == 1:                      # already regular
        return ds.sel(
            {latn: slice(LAT_MIN - PAD, LAT_MAX + PAD),
             lonn: slice(LON_MIN - PAD, LON_MAX + PAD)}
        )

    mask = (
        (lat2d >= LAT_MIN - PAD) & (lat2d <= LAT_MAX + PAD)
        & (lon2d >= LON_MIN - PAD) & (lon2d <= LON_MAX + PAD)
    )
    ys, xs = np.where(np.asarray(mask))
    if ys.size == 0:
        raise ValueError("basin box did not intersect the grid")
    ydim, xdim = lat2d.dims
    return ds.isel({ydim: slice(ys.min(), ys.max() + 1),
                    xdim: slice(xs.min(), xs.max() + 1)})


def to_regular(ds):
    """Bilinear interpolation from the cropped curvilinear patch."""
    latn, lonn = find_coord_names(ds)
    if ds[latn].ndim == 1:
        return ds.interp({latn: TARGET_LAT, lonn: TARGET_LON})

    try:
        import xesmf as xe
    except ImportError:
        raise SystemExit(
            "Curvilinear regridding needs xesmf:\n"
            "    conda install -c conda-forge xesmf\n"
            "(pip alone will not build ESMF)."
        )

    src = ds.rename({latn: "lat", lonn: "lon"})
    dst = xr.Dataset({"lat": ("lat", TARGET_LAT), "lon": ("lon", TARGET_LON)})
    regridder = xe.Regridder(src, dst, "bilinear", ignore_degenerate=True)
    return regridder(src)


def main():
    files = sorted(RAW.glob("*.nc"))
    if not files:
        raise SystemExit(
            f"no .nc files in {RAW}. If script 01 gave you .zip archives, "
            "unzip them into that folder first."
        )

    pieces = []
    for fp in files:
        print("  ", fp.name)
        with xr.open_dataset(fp) as ds:
            pieces.append(to_regular(crop_index_box(ds)).load())

    out = xr.concat(pieces, dim="time").sortby("time")
    target = OUT / "oras5_bob_monthly.nc"
    out.to_netcdf(target)
    print("done ->", target.resolve())
    print("   time steps:", out.sizes.get("time"))


if __name__ == "__main__":
    main()

# CHECK AFTER RUNNING, BEFORE ANY ANALYSIS:
#   1. Plot one MLD field. If the coastline of Bangladesh and Myanmar is not
#      where you expect, the crop or the interpolation is wrong.
#   2. Confirm 336 monthly steps for 1993-2020 with no gaps.
#   3. Plot the basin-mean MLD time series and LOOK AT 2014/2015. A visible
#      step there is the consolidated-to-operational join, not a climate
#      signal. README section 4.
