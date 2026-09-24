# Bay of Bengal Mixed Layer Depth

Long-term variability and physical drivers of mixed layer depth (MLD) in the
Bay of Bengal, 1996–2020. Reanalysis-based climatology, trend, and driver
attribution across three sub-basins, validated against independent Argo
profiles.

## Data sources

## Data sources

| Dataset | Role | Resolution |
|---|---|---|
| [ORAS5](https://doi.org/10.24381/cds.67e8eeb7) | MLD, ocean forcing (SST, SSS, SSH, wind stress, heat/freshwater flux) | 0.25°, monthly |
| [ERA5](https://doi.org/10.1002/qj.3803) | Atmospheric forcing (wind, radiation, precipitation, evaporation) | 0.25°, monthly |
| [DUACS](https://doi.org/10.48670/moi-00148) | EKE, sea level anomaly | 0.25°, daily |
| [Argo](https://argo.ucsd.edu/) | Independent validation | Profile |
| [Analysis Cube](https://data.mendeley.com/preview/fffdxy7dbk) | Processed analysis dataset used for MLD analysis and attribution | Monthly, 0.25° grid |

## Domain

5–23°N, 80–100°E, 0.25° grid (73 × 81 cells). Partitioned into North (≥18°N),
Central (12–18°N), and South (<12°N) sub-basins.

## What's in the notebook

- MLD climatology, seasonal cycle, and spatial distribution
- Theil-Sen trends with Mann-Kendall significance, corrected for serial
  autocorrelation
- Regime-shift and product-join discontinuity testing (Pettitt test,
  trend-aware step test)
- EOF decomposition of deseasonalised anomalies
- GLM driver attribution with explicit interaction terms and spatially
  blocked cross-validation
- Argo-based validation with signed-residual visualization

## Setup

```bash
conda create -n bobmld python=3.11
conda activate bobmld
conda install -c conda-forge xarray netcdf4 dask numpy pandas scipy \
    matplotlib cartopy gsw pyarrow
pip install cdsapi copernicusmarine argopy scikit-learn statsmodels
```

## Structure

```
BoB_MLD_Analysis_v7.ipynb    Main analysis notebook
download_argo.py             Chunked, resumable Argo downloader
data/
  raw/                       ORAS5, ERA5, altimetry, Argo (not tracked)
  processed/                 Merged analysis cube, tidy table
outputs/
  figures/
  tables/
```

## Key results

### MLD trends

![MLD seasonal trend](https://github.com/binarymaruf/mld_data_analysis/blob/main/fig14_mld_seasonal_trend.png "fig14_mld_seasonal_trend.png")

No significant basin-mean MLD trend (1996–2020), but 23.5% of grid cells show
significant local trends of opposing sign.

### GLM driver attribution

![GLM driver attribution by sub-basin](https://github.com/binarymaruf/mld_data_analysis/blob/main/fig11_glm_by_subbasin.png "fig11_glm_by_subbasin.png")

Sea level anomaly, wind stress, and net heat flux dominate the attribution; the
leading driver differs by sub-basin. Wind-driven deepening is significantly
damped by freshwater forcing (τ × P−E interaction, p < 0.001 throughout).

## Citation

If you use this pipeline, please cite the underlying data products (ORAS5,
ERA5, DUACS, Argo) per their individual usage policies.

## License

Add a license before publishing.
