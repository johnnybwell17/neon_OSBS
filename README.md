# NEON OSBS Data

## TL;DR

This repo downloads and stores sensor data from the NSF **NEON**
(National Ecological Observatory Network) network for the **OSBS** site
(Ordway-Swisher Biological Station, FL, domain **D03**, Southeast). It's
a sibling of `neon_CPER` and `neon_CLBJ`, reusing the same catalog-driven
download architecture unchanged. Six scripts pull three different kinds
of NEON/NEON-adjacent data:

| Script | Source | Data |
|---|---|---|
| `scripts/download_neon_product.py` | NEON `/data` API (`neonutilities.load_by_product`) | any single CSV-tabular sensor product |
| `scripts/download_all_products.py` | same, looped, fixed `--years-back` window | all 11 cataloged sensor products at once |
| `scripts/download_full_history.py` | same, looped, **each product's own true full-history range** | all 11 cataloged sensor products, no trailing-window guessing |
| `scripts/neon_site_availability.py` | NEON `/sites` metadata API (no token needed) | per-product true earliest/latest available month for a site |
| `scripts/download_phenocam_gcc.py` | PhenoCam Network (phenocam.nau.edu) | daily GCC greenness summaries, OSBS's camera(s), `--site`-driven |
| `scripts/download_eddy_covariance.py` | NEON `/data` API (`neonutilities.zips_by_product` + `stack_eddy`) | bundled eddy covariance / NEE flux data |
| `scripts/upload_to_huggingface.py` | HuggingFace Hub (`huggingface_hub`) | pushes `raw/` + `metadata/` + this README to a HF dataset repo |

Which product maps to which folder/table/interval is defined in
`metadata/sensor_catalog.yaml`, not hardcoded in any script -- same as
`neon_CPER`/`neon_CLBJ`. You need a free **NEON API token** (env var
`NEON_API_TOKEN`) for anything going through NEON's own `/data` API (not
needed for the PhenoCam script or `neon_site_availability.py`, which only
hits NEON's open `/sites` metadata endpoint).

**Current data status: all 11 sensor products, both PhenoCam series, and
eddy covariance have been downloaded** (~3.1 GB sensor data, ~1.8 MB
PhenoCam, 14 MB final eddy covariance CSV -- pulled 2026-10-05, see
[Data currently on hand](#5-data-currently-on-hand) below for the real
per-product numbers). `processed/` is still empty. The eddy covariance
pull hit a genuine schema-incompatibility bug on one month (2017-02,
produced under an older NEON processing revision) that crashes
`neonutilities`'s `stack_eddy()` -- worked around by excluding that one
file; see [Known issues](#7-known-issues-and-gotchas) below.

OSBS's own PhenoCam ROI structure turned out to be noticeably more
complex than CPER's or CLBJ's (9 and 6 ROI codes vs. 1-4) -- live
verification (direct CSV parsing, 2026-10-05) found the semantically
obvious pick (`UN_0001`, matching CLBJ's naming) is actually the
*wrong* one: it's a short series retired in 2018, not the long-running
camera. `GR_1000`+`GR_2000` (stitched) is used instead -- see
[Product catalog](#4-product-catalog-metadatasensor_catalogyaml) below.

**Like `neon_CPER` (not `neon_CLBJ`), this repo's goal is full available
history per product**, not a trailing window.

---

## Repo layout

```
neon_OSBS/
├── README.md                  # this file
├── .gitignore                 # excludes .venv/, raw/, __pycache__/, etc. (copied from neon_CPER)
├── scripts/
│   ├── download_neon_product.py     # single-product downloader via NEON /data API (COPIED UNCHANGED from neon_CPER)
│   ├── download_all_products.py     # loops download_one() over every catalog product, fixed --years-back (COPIED UNCHANGED)
│   ├── download_full_history.py     # same loop, each product's own true full-history --start/--end (COPIED UNCHANGED)
│   ├── neon_site_availability.py    # looks up each product's true available date range for a site, no token (COPIED UNCHANGED)
│   ├── download_phenocam_gcc.py     # --site-driven PhenoCam downloader, catalog-lookup (COPIED UNCHANGED)
│   ├── download_eddy_covariance.py  # DP4.00200.001 HDF5 download + stack_eddy() + QC filter (COPIED UNCHANGED)
│   ├── upload_to_huggingface.py     # NEW: pushes raw/ + metadata/ + README.md to a HF dataset repo
│   └── requirements.txt             # neonutilities, pyyaml, pandas<3, requests, huggingface_hub
├── metadata/
│   ├── sensor_catalog.yaml    # product catalog: 11 core sensor products + eddy covariance, copied unchanged
│   │                          #   from neon_CPER; PhenoCam entries are OSBS-specific and UNVERIFIED, see notes
│   └── README.md              # folder-to-product mapping + OSBS-specific findings/caveats (this repo's version)
├── raw/                       # one subfolder per product -- all 11 sensor products + both PhenoCam series pulled (2026-10-05)
│   ├── air_temperature/       # DP1.00002.001 -- HAS DATA
│   ├── soil_moisture/         # DP1.00094.001 -- HAS DATA
│   ├── soil_temperature/      # DP1.00041.001 -- HAS DATA
│   ├── precipitation/         # DP1.00044.001 -- HAS DATA
│   ├── radiation/             # DP1.00023.001 + DP1.00024.001 -- HAS DATA
│   ├── humidity/              # DP1.00098.001 -- HAS DATA
│   ├── pressure/              # DP1.00004.001 -- HAS DATA
│   ├── wind/                  # DP1.00001.001 -- HAS DATA
│   ├── soil_heat_flux/        # DP1.00040.001 -- HAS DATA
│   ├── soil_co2/              # DP1.00095.001 -- HAS DATA
│   ├── phenocam/
│   │   ├── understory/        # NEON.D03.OSBS.DP1.00042 (ROIs GR_1000+GR_2000 stitched -- HAS DATA)
│   │   └── canopy/            # NEON.D03.OSBS.DP1.00033 (ROIs EN_1000+EN_2000 stitched -- HAS DATA)
│   └── eddy_covariance/       # DP4.00200.001 -- HAS DATA (100/101 site-months; 2017-02 excluded, schema bug)
└── processed/                 # empty; for derived/analysis outputs you create from raw/ (not written to by any script)
```

---

## Detailed guide

### 1. Setup

```bash
cd ~/projects/neon_OSBS
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

Dependencies (`scripts/requirements.txt`): `neonutilities>=2.0.1`,
`pyyaml>=6.0`, `pandas<3`, `requests>=2.0`, `huggingface_hub>=0.25.0`. The
`pandas<3` pin is required -- `stack_eddy()` (used only by
`download_eddy_covariance.py`) calls a `drop(columns=..., axis=1)`
pattern that pandas 3.0 rejects outright.

### 2. Getting a NEON API token (required for NEON API scripts)

Since a **June 2026 NEON policy change**, the `/data` endpoint rejects
anonymous requests outright (`403 Access Denied`). Metadata endpoints like
`/products` and `/sites` still work without a token -- that includes
`neon_site_availability.py` -- but any actual data pull through
`download_neon_product.py`, `download_all_products.py`,
`download_full_history.py`, or `download_eddy_covariance.py` needs one.
`download_phenocam_gcc.py` does **not** need a token either -- it pulls
from phenocam.nau.edu's own open archive, a separate system from NEON's
API.

1. Create a free account at https://data.neonscience.org/
2. Generate an API token from your account page.
3. Set it in your shell before running any NEON-API script:

```bash
export NEON_API_TOKEN=<your token>
```

(or pass `--token <your token>` directly to any script that needs it).
**Never commit a token to this repo.**

### 3. Downloading data

**Step 0 -- check per-product availability for OSBS first (no token, no
download):**

```bash
python3 scripts/neon_site_availability.py --site OSBS
```

This prints each of the 11 core products' + eddy covariance's true
available `start_ym -> end_ym`, straight from NEON's `/sites` metadata.
Run 2026-10-05, OSBS has **no missing products and no internal gaps** --
every one of the 11 sensor products plus eddy covariance is listed:

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

Re-run this yourself before a real pull if time has passed, since NEON's
published range can advance.

**Step 1 -- single-product test pull** (confirm token + site code work
before anything larger):

```bash
python3 scripts/download_neon_product.py --site OSBS --product air_temperature --start 2024-01 --end 2024-03
```

**Step 2 -- all 11 sensor products, full available history per product:**

```bash
python3 scripts/download_full_history.py --site OSBS
```

(`download_all_products.py --site OSBS --years-back N` also works, for a
fixed trailing window instead of full history.)

**Step 3 -- eddy covariance, as its own separate, manually-confirmed
step** (potentially large -- check the size estimate first):

```bash
python3 scripts/neon_site_availability.py --site OSBS   # DP4.00200.001: 2017-02 -> 2026-08 (confirmed 2026-10-05)
python3 scripts/download_eddy_covariance.py --site OSBS --start 2017-02 --end 2026-08
```

`download_eddy_covariance.py` estimates total download size and checks
free disk space *before downloading anything*, aborting if the estimate
exceeds 90% of free space -- confirm the estimate it prints looks
reasonable before letting it proceed. **For OSBS specifically, this
script's own `stack_eddy()` call will crash on the 2017-02 file** (see
[Known issues](#7-known-issues-and-gotchas)) -- the script does not
currently work around this automatically; the fix used here was manual
(move that one file out of the staging dir, re-run `stack_eddy()` on the
rest). If re-running this pull from scratch, expect to repeat that
workaround.

**Step 4 -- PhenoCam, always run separately from the above** (no token
needed):

```bash
python3 scripts/download_phenocam_gcc.py --site OSBS --full-history
```

**Before running this**, read [metadata/README.md](metadata/README.md)'s
PhenoCam section -- OSBS has 9 canopy ROI codes and 6 understory ROI
codes (vs. CPER's 1-4). These have now been verified live (direct CSV
parse, 2026-10-05): the catalog uses `EN_1000`+`EN_2000` (canopy) and
`GR_1000`+`GR_2000` (understory), stitched chronologically -- notably
`UN_0001`, the semantically obvious name match for "understory," turned
out to be the *wrong* pick (a short series retired in 2018).

### 4. Product catalog (`metadata/sensor_catalog.yaml`)

Catalog structure and the 11 core sensor product entries + the
`DP4.00200.001` eddy covariance entry are copied unchanged from
`neon_CPER` (NEON product catalog entries aren't site-specific -- `--site`
is passed at download time). The two PhenoCam entries are OSBS-specific
and have been verified live (direct CSV parse) -- see
[metadata/README.md](metadata/README.md) for the full detail, including
why `UN_0001` was rejected in favor of `GR_1000`+`GR_2000`.

### 5. Data currently on hand

**All 11 sensor products and both PhenoCam series have been pulled**
(2026-10-05), via `download_full_history.py` (plus individual retries
for 5 products that hit transient rate-limiting) and
`download_phenocam_gcc.py --full-history`.

**11 NEON sensor products**, basic package, ~3.1 GB total. Every product
was requested through 2026-08 but the actual pulled data stops at
**2025-06-30** in every case -- `neonutilities` excludes NEON's most
recent ~13-14 months as unreviewed "provisional" data by default. This is
uniform across all 11 products, not a per-product gap:

| Product | dpid | rows | size | coverage |
|---|---|---|---|---|
| air_temperature | DP1.00002.001 | 955,440 | 136M | 2014-08-07 -> 2025-06-30 |
| soil_moisture | DP1.00094.001 | 6,151,680 | 1.1G | 2016-09-22 -> 2025-06-30 |
| soil_temperature | DP1.00041.001 | 6,920,640 | 996M | 2016-09-22 -> 2025-06-30 |
| relative_humidity | DP1.00098.001 | 339,696 | 72M | 2015-06-08 -> 2025-06-30 |
| barometric_pressure | DP1.00004.001 | 191,376 | 32M | 2014-08-01 -> 2025-06-30 |
| precipitation | DP1.00044.001 | 76,800 | 8.1M | 2016-09-26 -> 2025-06-30 |
| wind | DP1.00001.001 | 955,440 | 151M | 2014-08-07 -> 2025-06-30 |
| radiation_net | DP1.00023.001 | 382,176 | 83M | 2014-08-07 -> 2025-06-30 |
| radiation_par | DP1.00024.001 | 1,146,816 | 169M | 2014-08-01 -> 2025-06-30 |
| soil_heat_flux | DP1.00040.001 | 461,376 | 64M | 2016-09-22 -> 2025-06-30 |
| soil_co2 | DP1.00095.001 | 2,275,920 | 310M | 2016-11-04 -> 2025-06-30 |

**Retry note:** on the first `download_full_history.py` pass, 5 of 11
products (wind, radiation_net, radiation_par, soil_heat_flux, soil_co2)
failed with a transient `ConnectionError: Cannot access NEON API` --
the same rate-limiting pattern already documented in `neon_CPER`'s
README. A 90s backoff followed by individually re-running each via
`download_neon_product.py` cleared all 5 on the first retry.

**2 PhenoCam Network cameras** -- verified live against
`phenocam.nau.edu`'s per-ROI CSV date ranges (direct `pandas.read_csv()`,
not a summarized fetch) on 2026-10-05:

| Camera | ROI(s) | Rows | Coverage | Notes |
|---|---|---|---|---|
| canopy (`NEON.D03.OSBS.DP1.00033`) | `EN_1000`+`EN_2000` | 3,559 | 2016-12-15 -> 2026-10-04 | One 22-day gap at the generation hand-off (2026-02-24 -> 2026-03-17). `EN_1000` alone runs gap-free 2016-12-15 -> 2026-02-23; `EN_2000` is a new generation starting right after. |
| understory (`NEON.D03.OSBS.DP1.00042`) | `GR_1000`+`GR_2000` | 3,546 | 2016-12-14 -> 2026-10-04 | One 36-day gap at the hand-off (2025-12-10 -> 2026-01-14). **`UN_0001` -- the semantically obvious name match -- was checked and rejected**: it's a short series that stops 2018-03-11 (453 rows), the same pattern as CPER's abandoned understory camera. `GR_1000`+`GR_2000` gives vastly better coverage. |

**Eddy covariance (DP4.00200.001)**: requested 2017-02 -> 2026-08 (115
site-months); `zips_by_product()` actually returned 101 site-months
(~18 GB raw HDF5). Of those, **one file (2017-02) crashed
`stack_eddy()`** with a column-shape error -- its generation timestamp
(Dec 2022) was far older than every other month's (Jan 2026+), meaning
it was produced under an incompatible older NEON processing schema. Not
a download/network/disk issue; re-pulling it would hit the same error.
Worked around by excluding that one file and stacking the remaining 100
(2017-03 -> 2025-06-30, 146,112 unfiltered rows). After the NEE QC filter
(`qfqm.fluxCo2.nsae.qfFinl == 0`, which dropped 78.8% of rows -- 115,124
of 146,112), the final output is **14 MB, 30,988 rows**
(`raw/eddy_covariance/OSBS_eddy_covariance_2017-03_2026-08.csv`).
Notably, the QC-passing rows don't start until **2019-09-15** -- every
row from 2017-03 through 2019-09-14 was flagged bad by the NEE quality
flag, not simply absent; real usable coverage is 2019-09-15 ->
2025-06-28.

### 6. Uploading to HuggingFace

Once real data has been pulled, push it to the HF dataset repo:

```bash
hf auth login   # if not already logged in
python3 scripts/upload_to_huggingface.py --dry-run   # preview first
python3 scripts/upload_to_huggingface.py             # real upload
```

Default target: `johnnybwell/neon_OSBS` (public). Uploads `raw/`,
`metadata/`, and this `README.md` (rendered by HF as the dataset card) --
not `scripts/` (code lives on GitHub) or `processed/` (local-only).

### 7. Known issues and gotchas

Carried forward from `neon_CPER`/`neon_CLBJ`, confirmed to still apply:

- **`neonutilities` 2.0.1 vs `pandas` 3.0 incompatibility** -- fixed by
  pinning `pandas<3` in `scripts/requirements.txt`.
- **`soil_co2`'s real stacked table name is `SCO2C_30_minute`**, not
  `SCO2C_30min`.
- **`wind` (DP1.00001.001)** returns speed and direction in the same
  stacked table (`2DWSD_30min`).
- **`precipitation`** uses `DP1.00044.001` (weighing gauge) -- confirmed
  OSBS publishes it, 2016-09-26 -> 2025-06-30, 76,800 rows.
- **Transient `ConnectionError`s under bulk pull volume** -- 5 of 11
  products failed on the first `download_full_history.py` pass with
  `ConnectionError: Cannot access NEON API`; a 90s backoff + individual
  retry via `download_neon_product.py` cleared all 5. Same pattern CPER
  documented -- don't assume a bad token/site code if this recurs.

New, OSBS-specific findings from this repo's setup (2026-10-05):

- **One eddy covariance month has an incompatible schema and crashes
  `stack_eddy()`.** The 2017-02 HDF5 file was generated under an older
  NEON processing revision (timestamp Dec 2022, vs. Jan 2026+ for every
  other month) and has a different column layout that
  `neonutilities==2.0.1`'s `stack_eddy()` can't merge alongside the
  newer files (`ValueError: setting an array element with a
  sequence... inhomogeneous shape`). Not a network/disk/token issue --
  re-downloading changes nothing. Fixed by excluding that one file from
  the staging directory before stacking the rest. If re-running this
  pull, check for a `.h5.gz` file that never got auto-decompressed
  (another symptom of the same file) and/or a generation timestamp that
  stands out from the rest, and exclude it rather than assuming the
  whole pull is broken.
- **PhenoCam's semantically-obvious ROI name was the wrong pick.**
  `UN_0001` ("UN" = understory, matching CLBJ's `UN_1000` naming for the
  same product) looked like the right choice by convention, but direct
  CSV verification showed it's actually a short series retired in 2018
  (453 rows, 2016-12-14 -> 2018-03-11) -- the real long-running camera is
  under `GR_1000`+`GR_2000` instead (3,546 rows spanning nearly the full
  decade). Don't pick a PhenoCam ROI by name pattern alone; check actual
  date ranges first. See [metadata/README.md](metadata/README.md) for
  the full verification detail on both OSBS PhenoCam products.

### 8. File naming conventions

Same as `neon_CPER`/`neon_CLBJ`:

```
<SITE>_<product_shortname>_<start_YYYY-MM>_<end_YYYY-MM>.csv
```

e.g. `OSBS_air_temperature_2014-08_2026-08.csv`.

PhenoCam CSVs (day granularity, not month):

```
<SITE>_<alias>_<start_YYYY-MM-DD>_<end_YYYY-MM-DD>.csv
```

e.g. `OSBS_phenocam_canopy_2016-12-15_2026-10-04.csv`.

Raw source files from NEON (before this script concatenates them) follow
NEON's own convention:

```
NEON.DOM.SITE.DPL.PRNUM.REV.HOR.VER.TMI.NAME.yyyy-mm.PKGTYPE.GENTIME.csv
```

OSBS is in NEON domain **D03** (Southeast), vs. CPER's D10 (Central
Plains) and CLBJ's D11 (Southern Plains) -- e.g. a PhenoCam id here is
`NEON.D03.OSBS.DP1.00033`, not `NEON.D10.CPER.DP1.00033`.
