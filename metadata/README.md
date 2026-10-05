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
| `raw/phenocam/understory/` | NEON.D03.OSBS.DP1.00042 (ROI `UN_0001`, **unverified**) | PhenoCam understory camera | PhenoCam Network |
| `raw/phenocam/canopy/` | NEON.D03.OSBS.DP1.00033 (ROI `EN_1000`, **unverified**) | PhenoCam tower-top canopy camera | PhenoCam Network |
| `raw/eddy_covariance/` | DP4.00200.001 | Bundled Eddy Covariance (NEE, fluxes) | NEON API |

`processed/` is for derived/analysis outputs (not raw pulls). `scripts/`
holds the downloaders, copied unchanged from `neon_CPER` where they're
site-agnostic (`--site` is a CLI flag, not baked in).

## Status: nothing pulled yet

Unlike `neon_CPER`/`neon_CLBJ`, **no data has actually been downloaded for
this repo yet** as of 2026-10-05 -- this is a fresh scaffold. Before a
real pull:

1. `export NEON_API_TOKEN=<token>` (not set in this environment session --
   the metadata-only endpoints work without it, but `/data` does not).
2. `python3 scripts/neon_site_availability.py --site OSBS` to get OSBS's
   real per-product `availableMonths` range. A partial manual check on
   2026-10-05 (via NEON's `/sites/OSBS` endpoint) confirmed OSBS exists
   (domain **D03**, Southeast, Florida) and found at least three products
   with data 2014-08 through 2026-08: `DP1.00001.001` (wind),
   `DP1.00002.001` (air_temperature), `DP1.00004.001` (pressure) -- the
   other 8 sensor products plus eddy covariance were **not confirmed** in
   that pass (the check didn't reliably enumerate OSBS's full product
   list, not evidence those products are unavailable). Re-run the script
   yourself for the authoritative, complete answer before pulling.
3. See the **PhenoCam** section below -- OSBS's camera ROI structure is
   more complex than either sibling site and needs its own live
   verification before trusting `sensor_catalog.yaml`'s current
   `EN_1000`/`UN_0001` picks.

## PhenoCam: more complex here than at CPER or CLBJ

A live directory check of `phenocam.nau.edu/data/archive/<id>/ROI/` on
2026-10-05 found both OSBS PhenoCam products have noticeably more ROI
codes than CPER (1-4 codes) or CLBJ (1-3 codes):

| Camera | Product | ROI codes found | 
|---|---|---|
| canopy | `NEON.D03.OSBS.DP1.00033` | `EN_0001`, `EN_0002`, `EN_1000`, `EN_1001`, `EN_1002`, `EN_2000`, `EN_2001`, `EN_2002`, `XX_1000` (9 total) |
| understory | `NEON.D03.OSBS.DP1.00042` | `GR_1000`, `GR_1001`, `GR_2000`, `UN_0001`, `XX_1000`, `XX_2000` (6 total) |

PhenoCam ROI prefixes are standardized vegetation-type codes. `EN`
(evergreen needleleaf) fits OSBS's longleaf pine canopy; `GR`
(grassland)/`UN` (understory/unclassified) fit a pine-savanna
grass/wiregrass groundcover -- this is a genuinely different vegetation
structure from CLBJ's oak savanna (`DB`, deciduous broadleaf) or CPER's
open grassland (`GR` for both cameras).

**`sensor_catalog.yaml` currently picks `EN_1000` (canopy) and `UN_0001`
(understory) by naming convention alone, NOT by confirmed date-range
verification** the way CPER's and CLBJ's entries were. A first-pass check
fetching each `*_1day.csv`'s date range came back inconsistent -- most
`EN_*`/`GR_*`/`UN_0001` files clustered in a short 2016-12 → ~2018-02
window (plausible, echoing CPER's "several ROIs retired together in
2018" pattern), but the `XX_1000`/`XX_2000` files returned identical date
ranges across *different* source files, which is almost certainly a tool
artifact (truncation/caching) rather than real data. **Do not trust any
specific date in this file** -- that check used an AI-summarized fetch,
not a direct CSV parse. Before a real pull:

- Fetch each ROI's `_1day.csv` directly (`curl`, or pandas `read_csv`) and
  compare real first/last dates and row counts -- the same process used
  to confirm CPER's `GR_1000` alone covers 2016-06-29 → 2026-03-07.
- Only then decide whether `EN_1000`/`UN_0001` are actually the
  longest-running, least-gapped choice, or whether a `GR_*`/`XX_*` code
  turns out to be better -- update `metadata/sensor_catalog.yaml`'s
  `roi:` fields accordingly once confirmed.

## File naming conventions

Same as `neon_CPER`/`neon_CLBJ`:

```
<SITE>_<product_shortname>_<start_YYYY-MM>_<end_YYYY-MM>.csv
```

e.g. `OSBS_air_temperature_2014-08_2026-08.csv` (once pulled).
`product_shortname` is `aliases[0]` from the matching
`sensor_catalog.yaml` entry.

PhenoCam CSVs use day granularity instead of month:

```
<SITE>_<alias>_<start_YYYY-MM-DD>_<end_YYYY-MM-DD>.csv
```

## Note on tower heights and soil sensor positions

Not yet confirmed for OSBS -- do **not** assume CPER's (3 air-temp
heights, 5x8 soil array) or CLBJ's (4 heights, 5x8 soil array) position
layouts apply here. Once any product is actually pulled, check its own
`horizontalPosition`/`verticalPosition` combinations (or the raw
`sensor_positions.csv` from a NEON download) before any time-series
analysis -- this must be done per-site, it has differed every time so
far.

## API access

**NEON API**: the `/data` endpoint requires a token (anonymous requests
return `403 Access Denied`); metadata endpoints like `/products` and
`/sites` do not -- this is what `neon_site_availability.py` uses. Set
`NEON_API_TOKEN` as an environment variable before running any
`/data`-pulling script -- do not commit tokens to this repo (`.gitignore`
excludes `.env`).

**PhenoCam Network**: fully open, no token/account needed, but see the
PhenoCam section above -- OSBS's ROI codes need live re-verification
before trusting `sensor_catalog.yaml`'s current picks.

**HuggingFace**: `scripts/upload_to_huggingface.py` pushes `raw/` (plus
this README) to a HF dataset repo via `huggingface_hub`. Requires being
logged in (`hf auth login`, or `HF_TOKEN` env var) with write access to
the target repo -- see that script's docstring for the target repo id.

## Known bugs / quirks inherited from `neon_CPER`/`neon_CLBJ`

Expected to still apply here, since they're properties of
`neonutilities`/NEON's API rather than anything site-specific -- not yet
re-confirmed against an actual OSBS pull:

- `neonutilities` 2.0.1's `load_by_product()` raises an unhandled
  `TypeError` (not a clear error) if you request a `timeindex` that
  doesn't exist for a product.
- `soil_co2`'s real stacked table name is `SCO2C_30_minute`, not
  `SCO2C_30min`.
- `neonutilities` 2.0.1's `stack_eddy()` calls a `drop(columns=...,
  axis=1)` pattern that pandas 3.0 rejects. Fixed by pinning `pandas<3`
  in `scripts/requirements.txt` (same pin carried over unchanged).
- Bulk full-catalog pulls have twice hit transient `ConnectionError`s
  under heavy request volume at CPER (resolved with a 60-90s backoff and
  retry) -- not a sign of a bad token or site code if it recurs here.
