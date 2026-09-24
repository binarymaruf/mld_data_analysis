"""
03 | Satellite altimetry: SLA + geostrophic velocity anomalies -> EKE
     data/raw/altimetry/
DUACS L4 reprocessed, product SEALEVEL_GLO_PHY_L4_MY_008_047
Product DOI: 10.48670/moi-00148

THIS IS WHAT SETS YOUR START YEAR.
The gridded altimetry record begins in January 1993. Your proposal says
1991-2020. If EKE and SLA are predictors, the analysis period is 1993-2020,
not 1991-2020. Change the period in the manuscript or drop the two altimetry
predictors for 1991-92 and accept a ragged predictor matrix. The first option
is cleaner. See README section 3.

SETUP (once):
    pip install copernicusmarine
    copernicusmarine login          # prompts for Copernicus Marine credentials
    (registration: https://data.marine.copernicus.eu/register)

The old MOTU/FTP endpoints are retired. The `copernicusmarine` toolbox is the
current access route.
"""

from pathlib import Path
import copernicusmarine as cm

OUT = Path("data/raw/altimetry")
OUT.mkdir(parents=True, exist_ok=True)

# Confirm the exact dataset_id before running:
#     copernicusmarine describe --contains SEALEVEL_GLO_PHY_L4_MY_008_047
# Product IDs are stable; the dataset_id inside a product carries a version
# suffix that changes between DUACS reprocessings (DT2021, DT2024, ...).
DATASET_ID = "cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.25deg_P1D"

VARIABLES = [
    "sla",     # sea level anomaly
    "adt",     # absolute dynamic topography
    "ugosa",   # geostrophic velocity anomaly, zonal
    "vgosa",   # geostrophic velocity anomaly, meridional
]

BOX = dict(
    minimum_longitude=78.0,
    maximum_longitude=102.0,
    minimum_latitude=3.0,
    maximum_latitude=25.0,
)


def main():
    target = OUT / "duacs_sla_bob_1993_2020.nc"
    if target.exists():
        print("exists, nothing to do:", target)
        return

    print("subsetting DUACS L4 over the Bay of Bengal ...")
    cm.subset(
        dataset_id=DATASET_ID,
        variables=VARIABLES,
        start_datetime="1993-01-01T00:00:00",
        end_datetime="2020-12-31T23:59:59",
        output_filename=target.name,
        output_directory=str(OUT),
        **BOX,
    )
    print("done ->", target.resolve())


if __name__ == "__main__":
    main()

# NEXT STEP (script 06): EKE from the velocity anomalies,
#     EKE = 0.5 * (ugosa**2 + vgosa**2)     [m2 s-2]
# Compute EKE on the DAILY fields, THEN average to monthly. Averaging the
# velocities to monthly first and squaring afterwards discards the eddy
# variance you are trying to measure and will bias EKE low by a large factor.
# This is the single most common error with this product.
