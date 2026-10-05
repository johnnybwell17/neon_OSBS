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

**Current data status: nothing pulled yet.** This is a fresh scaffold as
of 2026-10-05 -- `raw/` and `processed/` are both empty. OSBS's own
PhenoCam ROI structure turned out to be noticeably more complex than
CPER's or CLBJ's (9 and 6 ROI codes vs. 1-4) and has **not** been fully
verified live yet -- see [metadata/README.md](metadata/README.md) before
trusting the catalog's current ROI picks. See
[Detailed guide](#detailed-guide) below for the full walkthrough.

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
├── raw/                       # one subfolder per product -- currently EMPTY, nothing pulled yet
│   ├── air_temperature/       # DP1.00002.001
│   ├── soil_moisture/         # DP1.00094.001
│   ├── soil_temperature/      # DP1.00041.001
│   ├── precipitation/         # DP1.00044.001
│   ├── radiation/             # DP1.00023.001 + DP1.00024.001
│   ├── humidity/              # DP1.00098.001
│   ├── pressure/              # DP1.00004.001
│   ├── wind/                  # DP1.00001.001
│   ├── soil_heat_flux/        # DP1.00040.001
│   ├── soil_co2/              # DP1.00095.001
│   ├── phenocam/
│   │   ├── understory/        # NEON.D03.OSBS.DP1.00042 (ROI UN_0001 -- UNVERIFIED, see metadata/README.md)
│   │   └── canopy/            # NEON.D03.OSBS.DP1.00033 (ROI EN_1000 -- UNVERIFIED, see metadata/README.md)
│   └── eddy_covariance/       # DP4.00200.001
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
**This has not been run in this environment yet** -- a partial manual
check (2026-10-05) confirmed OSBS has `DP1.00001.001` (wind),
`DP1.00002.001` (air_temperature), and `DP1.00004.001` (pressure) data
2014-08 through 2026-08, but did not confirm the other 8 sensor products
or eddy covariance -- run the script yourself for the real, complete
answer before pulling.

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
python3 scripts/neon_site_availability.py --site OSBS   # note the DP4.00200.001 row -- not yet confirmed
python3 scripts/download_eddy_covariance.py --site OSBS --start <start> --end <end>
```

`download_eddy_covariance.py` estimates total download size and checks
free disk space *before downloading anything*, aborting if the estimate
exceeds 90% of free space -- confirm the estimate it prints looks
reasonable before letting it proceed.

**Step 4 -- PhenoCam, always run separately from the above** (no token
needed):

```bash
python3 scripts/download_phenocam_gcc.py --site OSBS --full-history
```

**Before running this**, read [metadata/README.md](metadata/README.md)'s
PhenoCam section -- OSBS has 9 canopy ROI codes and 6 understory ROI
codes (vs. CPER's 1-4), and the catalog's current `EN_1000`/`UN_0001`
picks have **not** been confirmed to be the longest-running/least-gapped
choice the way CPER's and CLBJ's were. Re-verify live first.

### 4. Product catalog (`metadata/sensor_catalog.yaml`)

Catalog structure and the 11 core sensor product entries + the
`DP4.00200.001` eddy covariance entry are copied unchanged from
`neon_CPER` (NEON product catalog entries aren't site-specific -- `--site`
is passed at download time). The two PhenoCam entries are OSBS-specific
and **unverified** -- see [metadata/README.md](metadata/README.md) for
the full caveat before trusting them.

### 5. Data currently on hand

**Nothing.** `raw/` and `processed/` are both empty as of 2026-10-05 --
this is a fresh scaffold, not yet run against real data.

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

Carried forward from `neon_CPER`/`neon_CLBJ` (expected to still apply,
same root causes in `neonutilities`/NEON's API -- not yet re-confirmed
against a real OSBS pull):

- **`neonutilities` 2.0.1 vs `pandas` 3.0 incompatibility** -- fixed by
  pinning `pandas<3` in `scripts/requirements.txt`.
- **`soil_co2`'s real stacked table name is `SCO2C_30_minute`**, not
  `SCO2C_30min`.
- **`wind` (DP1.00001.001)** returns speed and direction in the same
  stacked table (`2DWSD_30min`).
- **`precipitation`** uses `DP1.00044.001` (weighing gauge), not the
  deprecated `DP1.00006.001` -- not yet confirmed OSBS actually publishes
  this specific product.
- **PhenoCam ROI codes need live re-verification** -- see
  [metadata/README.md](metadata/README.md). OSBS's structure (9 canopy +
  6 understory ROI codes) is more complex than either sibling site and a
  first-pass check returned some results (the `XX_*` ROIs) that look like
  tool artifacts rather than real data -- don't trust any specific date
  range in this repo's docs until re-checked with a direct CSV parse.

### 8. File naming conventions

Same as `neon_CPER`/`neon_CLBJ`:

```
<SITE>_<product_shortname>_<start_YYYY-MM>_<end_YYYY-MM>.csv
```

e.g. `OSBS_air_temperature_2014-08_2026-08.csv` (once pulled).

PhenoCam CSVs (day granularity, not month):

```
<SITE>_<alias>_<start_YYYY-MM-DD>_<end_YYYY-MM-DD>.csv
```

Raw source files from NEON (before this script concatenates them) follow
NEON's own convention:

```
NEON.DOM.SITE.DPL.PRNUM.REV.HOR.VER.TMI.NAME.yyyy-mm.PKGTYPE.GENTIME.csv
```

OSBS is in NEON domain **D03** (Southeast), vs. CPER's D10 (Central
Plains) and CLBJ's D11 (Southern Plains) -- e.g. a PhenoCam id here is
`NEON.D03.OSBS.DP1.00033`, not `NEON.D10.CPER.DP1.00033`.
