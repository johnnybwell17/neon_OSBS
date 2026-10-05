# NEON OSBS Data — Project Notes

Site: **OSBS** (Ordway-Swisher Biological Station, FL), NEON domain
**D03** (Southeast). Sibling project to `neon_CPER` (domain D10) and
`neon_CLBJ` (domain D11) -- same catalog-driven download architecture,
applied to a third site. Confirmed live against NEON's `/sites` metadata
API on 2026-10-05.

This project pulls data for OSBS from two separate sources:

- The **NEON Data Portal API** (https://data.neonscience.org/api/v0/), via
  `scripts/download_neon_product.py` (single product),
  `scripts/download_all_products.py` (fixed trailing window, all
  cataloged NEON products at once), `scripts/download_full_history.py`
  (all cataloged NEON products at once, each at its own true full
  available history), and `scripts/download_eddy_covariance.py` (the one
  HDF5-delivered product, `DP4.00200.001`).
- The **PhenoCam Network** archive (https://phenocam.nau.edu/), a
  completely separate, open, tokenless system, via
  `scripts/download_phenocam_gcc.py`.

## Folder-to-product mapping

| Folder | ID | Product name | Source |
|---|---|---|---|
| `raw/air_temperature/` | DP1.00002.001 | Single Aspirated Air Temperature | NEON API |
| `raw/soil_moisture/` | DP1.00094.001 | Soil Water Content | NEON API |
| `raw/soil_temperature/` | DP1.00041.001 | Soil Temperature | NEON API |
| `raw/precipitation/` | DP1.00044.001 | Precipitation - Weighing Gauge | NEON API |
| `raw/radiation/` | DP1.00023.001 | Net Radiation | NEON API |
| `raw/radiation/` | DP1.00024.001 | Photosynthetically Active Radiation (PAR) | NEON API |
| `raw/humidity/` | DP1.00098.001 | Relative Humidity | NEON API |
| `raw/pressure/` | DP1.00004.001 | Barometric Pressure | NEON API |
| `raw/wind/` | DP1.00001.001 | 2D Wind Speed and Direction | NEON API |
| `raw/soil_heat_flux/` | DP1.00040.001 | Soil Heat Flux Plate | NEON API |
| `raw/soil_co2/` | DP1.00095.001 | Soil CO2 Concentration | NEON API |
| `raw/phenocam/understory/` | NEON.D03.OSBS.DP1.00042 (ROIs `GR_1000`+`GR_2000`, verified) | PhenoCam understory camera | PhenoCam Network |
| `raw/phenocam/canopy/` | NEON.D03.OSBS.DP1.00033 (ROIs `EN_1000`+`EN_2000`, verified) | PhenoCam tower-top canopy camera | PhenoCam Network |
| `raw/eddy_covariance/` | DP4.00200.001 | Bundled Eddy Covariance (NEE, fluxes) | NEON API |

`processed/` is for derived/analysis outputs (not raw pulls). `scripts/`
holds the downloaders, copied unchanged from `neon_CPER` where they're
site-agnostic (`--site` is a CLI flag, not baked in).

## Status: all 11 sensor products + both PhenoCam cameras pulled

As of 2026-10-05, `python3 scripts/neon_site_availability.py --site OSBS`
confirmed OSBS (domain **D03**, Southeast, Florida) has **no missing
products and no internal gaps** across all 11 core sensor products plus
eddy covariance:

| Alias | ID | Available range |
|---|---|---|
| `wind` | DP1.00001.001 | 2014-08 -> 2026-08 |
| `air_temperature` | DP1.00002.001 | 2014-08 -> 2026-08 |
| `barometric_pressure` | DP1.00004.001 | 2014-08 -> 2026-08 |
| `radiation_net` | DP1.00023.001 | 2014-08 -> 2026-08 |
| `radiation_par` | DP1.00024.001 | 2014-08 -> 2026-08 |
| `soil_heat_flux` | DP1.00040.001 | 2016-09 -> 2026-08 |
| `soil_temperature` | DP1.00041.001 | 2016-09 -> 2026-08 |
| `precipitation` | DP1.00044.001 | 2016-09 -> 2026-08 |
| `soil_moisture` | DP1.00094.001 | 2016-09 -> 2026-08 |
| `soil_co2` | DP1.00095.001 | 2016-11 -> 2026-08 |
| `relative_humidity` | DP1.00098.001 | 2015-06 -> 2026-08 |
| eddy covariance | DP4.00200.001 | 2017-02 -> 2026-08 |

All 11 sensor products were then pulled via `download_full_history.py`
(5 needed an individual retry after transient rate-limiting -- see
[Known bugs / quirks](#known-bugs--quirks-inherited-from-neon_cperneon_clbj)
below), both PhenoCam cameras via `download_phenocam_gcc.py
--full-history`, and eddy covariance via `download_eddy_covariance.py`
(101 of 115 requested site-months downloaded; 1 of those 101, 2017-02,
had to be manually excluded before stacking due to a schema-
incompatibility bug -- see [Known bugs / quirks](#known-bugs--quirks-inherited-from-neon_cperneon_clbj)
below). See the top-level [README.md](../README.md#5-data-currently-on-hand)
for the full per-product rows/coverage table.

## PhenoCam: more complex here than at CPER or CLBJ, verified live

A live directory check of `phenocam.nau.edu/data/archive/<id>/ROI/` found
both OSBS PhenoCam products have noticeably more ROI codes than CPER (1-4
codes) or CLBJ (1-3 codes):

| Camera | Product | ROI codes found | 
|---|---|---|
| canopy | `NEON.D03.OSBS.DP1.00033` | `EN_0001`, `EN_0002`, `EN_1000`, `EN_1001`, `EN_1002`, `EN_2000`, `EN_2001`, `EN_2002`, `XX_1000` (9 total) |
| understory | `NEON.D03.OSBS.DP1.00042` | `GR_1000`, `GR_1001`, `GR_2000`, `UN_0001`, `XX_1000`, `XX_2000` (6 total) |

PhenoCam ROI prefixes are standardized vegetation-type codes. `EN`
(evergreen needleleaf) fits OSBS's longleaf pine canopy; `GR`
(grassland)/`UN` (understory/unclassified) fit a pine-savanna
grass/wiregrass groundcover -- a genuinely different vegetation structure
from CLBJ's oak savanna (`DB`, deciduous broadleaf) or CPER's open
grassland (`GR` for both cameras).

**Every ROI's real date range was then confirmed on 2026-10-05 via direct
`pandas.read_csv()`** (not a summarized fetch -- an earlier AI-summarized
pass on the same URLs gave unreliable/inconsistent numbers, which is why
this was redone properly):

| Product | ROI | Rows | Coverage | What it is |
|---|---|---|---|---|
| canopy | `EN_0001`/`EN_0002` | 453 each | 2016-12-14 -> 2018-03-11 | Retired together, like CPER's `GR_0001`/`0002`/`0003` |
| canopy | `EN_1000`/`1001`/`1002` | ~3358 each | 2016-12-15 -> 2026-02-23 | **Used.** Long-running generation, essentially gap-free |
| canopy | `EN_2000`/`2001`/`2002` | 201 each | 2026-03-18 -> present | **Used.** New generation, hand-off 23 days after `EN_1000` stops |
| canopy | `XX_1000` | 1023 | 2016-12-14 -> 2019-10-02 | Unrelated shorter series, not used |
| understory | `GR_1000` | 3283 | 2016-12-14 -> 2025-12-09 | **Used.** The real long-running series |
| understory | `GR_1001` | 6 | 2023-05-01 -> 2023-05-06 | Test/anomaly, ignore |
| understory | `GR_2000` | 263 | 2026-01-15 -> present | **Used.** Hand-off from `GR_1000`, ~5-week gap at the seam |
| understory | `UN_0001` | 453 | 2016-12-14 -> 2018-03-11 | **Rejected** -- see below |
| understory | `XX_1000`/`XX_2000` | 1023 each | 2016-12-14 -> 2019-10-02 | Identical to canopy's `XX_1000`, likely a shared/reused unclassified-ROI definition, not used |

**The semantically-obvious pick was wrong.** `UN_0001` ("UN" =
understory) looked like the right choice by naming convention, echoing
CLBJ's `UN_1000` for the same product role -- but it's actually the
*short* series, retired in 2018, same pattern as CPER's abandoned
understory camera. `GR_1000`+`GR_2000` gives coverage through the present
instead. **Lesson: don't pick a PhenoCam ROI by name pattern alone --
always check actual date ranges.**

`sensor_catalog.yaml` uses `rois: [EN_1000, EN_2000]` (canopy) and
`rois: [GR_1000, GR_2000]` (understory) -- `download_phenocam_gcc.py`
stitches multi-entry `rois:` lists chronologically, the same mechanism
CLBJ's canopy camera (`DB_1000`/`2000`/`3000`) uses. Actual pulled result
(2026-10-05): canopy 3,559 rows, 2016-12-15 -> 2026-10-04, one 22-day gap
at the hand-off; understory 3,546 rows, 2016-12-14 -> 2026-10-04, one
36-day gap at the hand-off.

## File naming conventions

Same as `neon_CPER`/`neon_CLBJ`:

```
<SITE>_<product_shortname>_<start_YYYY-MM>_<end_YYYY-MM>.csv
```

e.g. `OSBS_air_temperature_2014-08_2026-08.csv`.
`product_shortname` is `aliases[0]` from the matching
`sensor_catalog.yaml` entry.

PhenoCam CSVs use day granularity instead of month:

```
<SITE>_<alias>_<start_YYYY-MM-DD>_<end_YYYY-MM-DD>.csv
```

## Note on tower heights and soil sensor positions (verticalPosition / horizontalPosition)

**Confirmed for OSBS** (2026-10-05) by checking the actual distinct
`horizontalPosition`/`verticalPosition` combinations present in each
pulled file -- do **not** assume these match CPER's (3 air-temp heights)
or CLBJ's (4 heights):

| Product | Layout |
|---|---|
| air_temperature, wind | single tower location (`horizontalPosition` `000`), **5** heights (`verticalPosition` `010`-`050`) -- more than CPER (3) or CLBJ (4) |
| radiation_par | same single location, 6 heights (`010`-`060`) |
| radiation_net, relative_humidity | only 2 combos each: (`000`,`060`) and (`003`,`000`) -- the second combo's meaning not resolved from the stacked data alone, same ambiguity CPER found for its own secondary combo |
| barometric_pressure | single position (`000`,`025`) |
| soil_moisture | 5 horizontal (soil pits, `001`-`005`) x 8 depths (`501`-`508`) = 40 positions -- same shape as CPER |
| soil_temperature | 5 horizontal x **9** depths (`501`-`509`) = 45 positions -- one more depth than soil_moisture, same pattern CPER found |
| soil_co2 | 5 horizontal x 3 depths (`501`-`503`) = 15 positions -- same shape as CPER |
| soil_heat_flux | 3 plates only, at horizontal positions `001`/`003`/`005` (a subset of the 5 soil pits), single depth `501` each -- same shape as CPER |

**Always filter or group by `horizontalPosition`/`verticalPosition`
before any time-series analysis** -- otherwise readings from different
locations/heights/depths get mixed together.

## API access

**NEON API**: the `/data` endpoint requires a token (anonymous requests
return `403 Access Denied`); metadata endpoints like `/products` and
`/sites` do not -- this is what `neon_site_availability.py` uses. Set
`NEON_API_TOKEN` as an environment variable before running any
`/data`-pulling script -- do not commit tokens to this repo (`.gitignore`
excludes `.env`).

**PhenoCam Network**: fully open, no token/account needed. OSBS's ROI
codes have been verified live (direct CSV parse, 2026-10-05) -- see the
PhenoCam section above.

**HuggingFace**: `scripts/upload_to_huggingface.py` pushes `raw/` +
`metadata/` + the top-level `README.md` to a HF dataset repo via
`huggingface_hub`, creating it if it doesn't exist yet (`exist_ok=True`).
Requires being logged in (`hf auth login`, or `HF_TOKEN` env var) with
write access to the target repo -- default target
`johnnybwell/neon_OSBS` (public), matching `neon_CPER`'s naming
convention.

## Known bugs / quirks inherited from `neon_CPER`/`neon_CLBJ`

Confirmed to still apply at OSBS:

- `neonutilities` 2.0.1's `load_by_product()` raises an unhandled
  `TypeError` (not a clear error) if you request a `timeindex` that
  doesn't exist for a product.
- `soil_co2`'s real stacked table name is `SCO2C_30_minute`, not
  `SCO2C_30min`.
- `neonutilities` 2.0.1's `stack_eddy()` calls a `drop(columns=...,
  axis=1)` pattern that pandas 3.0 rejects. Fixed by pinning `pandas<3`
  in `scripts/requirements.txt` (same pin carried over unchanged).
- Bulk full-catalog pulls hit the same transient `ConnectionError` under
  heavy request volume that CPER documented: 5 of 11 products failed on
  the first `download_full_history.py` pass at OSBS (wind, radiation_net,
  radiation_par, soil_heat_flux, soil_co2) and all cleared on a 90s
  backoff + individual retry via `download_neon_product.py` -- not a sign
  of a bad token or site code if this recurs.

New, OSBS-specific bug found pulling eddy covariance (not seen at CPER
or CLBJ, neither of which completed a full eddy covariance pull):

- **One HDF5 file per site can have an incompatible schema and crash
  `stack_eddy()`.** OSBS's 2017-02 eddy covariance file
  (`NEON.D03.OSBS.DP4.00200.001.nsae.2017-02.basic.20221215T020221Z.h5`)
  was generated under an older NEON processing revision -- its
  generation timestamp (Dec 2022) is far older than every other pulled
  month's (Jan 2026+) -- giving it a different column layout.
  `neonutilities==2.0.1`'s `stack_eddy()` tries to `np.unique()` the
  column-name lists across all files and raises `ValueError: setting an
  array element with a sequence... inhomogeneous shape` when one file's
  columns don't match the rest. Symptom to watch for: this file also
  stayed as a `.h5.gz` that `zips_by_product()` never auto-decompressed
  (every other month got unzipped to a bare `.h5` automatically) --
  check for a lingering `.h5.gz` or an outlier generation timestamp in
  the staging dir as the tell. Not a network/disk/token problem;
  re-downloading reproduces the exact same file and the exact same
  crash. Fix applied here: move that one file out of the staging
  directory, re-run `stack_eddy(filepath=staging_dir, level="dp04")` on
  the rest. `download_eddy_covariance.py` does not currently detect or
  work around this automatically -- it will crash the same way if
  re-run end-to-end against OSBS without the manual exclusion step.
