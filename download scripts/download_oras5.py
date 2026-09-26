"""
01 | ORAS5 monthly ocean reanalysis  ->  data/raw/oras5/
Bay of Bengal MLD study, 1993-2020.

ORAS5 supplies MLD *and* most forcing terms on one grid, so this single
download covers Objectives 1-3. Dataset DOI: 10.24381/cds.67e8eeb7

SETUP (once):
    pip install "cdsapi>=0.7.2"
    Register at https://cds.climate.copernicus.eu/
    Put your token in ~/.cdsapirc :
        url: https://cds.climate.copernicus.eu/api
        key: <PERSONAL-ACCESS-TOKEN>
    Then OPEN the dataset page and ACCEPT the licence, or every request 403s:
        https://cds.climate.copernicus.eu/datasets/reanalysis-oras5

TWO THINGS TO KNOW BEFORE YOU RUN THIS
  1. ORAS5 is on the tripolar ORCA025 grid, NOT regular lat/lon. There is no
     area-subset option, so we pull global files and cut the basin out in
     script 05. Do not try to index by lat/lon on the raw files.
  2. product_type changes at 2015. "consolidated" = 1958-2014 (ERA-Interim
     forcing, reprocessed obs); "operational" = 2015-present (operational
     forcing, NRT obs). They are NOT the same product. See README section 4.
"""

import cdsapi
from pathlib import Path

OUT = Path("data/raw/oras5")
OUT.mkdir(parents=True, exist_ok=True)

# --- variables -------------------------------------------------------------
# 2D single-level fields. Names are the CDS API values as listed on the
# dataset download form.
SINGLE_LEVEL = [
    "mixed_layer_depth_0_03",      # <- target variable, 0.03 kg m-3 criterion
    "mixed_layer_depth_0_01",      # <- sensitivity test (see README section 5)
    "sea_surface_temperature",
    "sea_surface_salinity",
    "sea_surface_height",
    "zonal_wind_stress",
    "meridional_wind_stress",
    "net_downward_heat_flux",
    "net_upward_water_flux",       # E-P-R, the freshwater flux term
]

# 3D fields, only needed if you recompute MLD yourself or want the
# stratification profile. These are LARGE (75 levels). Comment out if not used.
MULTI_LEVEL = [
    "potential_temperature",
    "salinity",
]

CONSOLIDATED_YEARS = [str(y) for y in range(1993, 2015)]   # 1993-2014
OPERATIONAL_YEARS = [str(y) for y in range(2015, 2021)]    # 2015-2020
MONTHS = [f"{m:02d}" for m in range(1, 13)]


def fetch(client, product_type, years, variables, vertical, tag):
    """One request per year keeps each job inside CDS queue limits."""
    for year in years:
        target = OUT / f"oras5_{tag}_{product_type}_{year}.zip"
        if target.exists():
            print(f"  skip (exists): {target.name}")
            continue
        print(f"  requesting {target.name} ...")
        client.retrieve(
            "reanalysis-oras5",
            {
                "product_type": [product_type],
                "vertical_resolution": vertical,
                "variable": variables,
                "year": [year],
                "month": MONTHS,
                "data_format": "zip",
            },
            str(target),
        )


def main():
    c = cdsapi.Client()

    print("[1/2] single-level fields")
    fetch(c, "consolidated", CONSOLIDATED_YEARS, SINGLE_LEVEL, "single_level", "2d")
    fetch(c, "operational", OPERATIONAL_YEARS, SINGLE_LEVEL, "single_level", "2d")

    # Uncomment if you need the 3D T/S fields.
    # print("[2/2] multi-level fields (large)")
    # fetch(c, "consolidated", CONSOLIDATED_YEARS, MULTI_LEVEL, "all_levels", "3d")
    # fetch(c, "operational", OPERATIONAL_YEARS, MULTI_LEVEL, "all_levels", "3d")

    print("done ->", OUT.resolve())


if __name__ == "__main__":
    main()

# VERIFY THE REQUEST KEYS BEFORE A LONG RUN.
# The new CDS renamed some keys in 2024. Build one request by hand on the
# download form, press "Show API request code", and confirm the dict above
# matches. Test with a single year first.
