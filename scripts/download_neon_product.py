#!/usr/bin/env python3
"""
download_neon_product.py

Reusable downloader for NEON (National Ecological Observatory Network)
data products, for any product/site/date range. Built on the official
`neonutilities` package (`load_by_product`), which handles NEON's monthly
package pagination, zip download/unzip, and per-position table stacking
internally -- and is maintained by NEON to track changes to their file
layout, so this script doesn't have to.

Product-specific details -- which raw/ subfolder a product's output goes
in, which stacked table holds the actual sensor readings (a single NEON
product download can return several tables: readme, variables,
sensor_positions, issue log, etc. alongside the data itself), and what
native averaging interval that table publishes at -- are looked up from
metadata/sensor_catalog.yaml, not hardcoded here. Add a catalog entry
before pulling a new product.

NEON's /api/v0/data endpoint has rejected anonymous requests outright
since a June 2026 policy change; this script requires NEON_API_TOKEN (or
--token) and refuses to run without one, rather than silently falling
back to a public rate limit that no longer works.

Setup
-----
neonutilities and pyyaml aren't in the system Python (which is externally
managed on this machine) -- use the project-local virtualenv:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r scripts/requirements.txt

Examples
--------
Pull 5 years of CLBJ air temperature (catalog alias, from
metadata/sensor_catalog.yaml):

    python3 download_neon_product.py --site CLBJ --product air_temperature --years-back 5

Pull an explicit date range of soil moisture:

    python3 download_neon_product.py --site CLBJ --product soil_moisture \\
        --start 2022-01 --end 2023-12

Pull a product that isn't in the catalog yet (ad hoc; add a catalog entry
instead if you'll need this again):

    python3 download_neon_product.py --site CLBJ --product DP1.20288.001 \\
        --outdir ../raw/water_quality --file-match waq_instantaneous --interval-min 1
"""

import argparse
import os
import sys
from datetime import date

import pandas as pd
import yaml
import neonutilities as nu

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(SCRIPT_DIR, "..", "metadata", "sensor_catalog.yaml")


def load_catalog(path=CATALOG_PATH):
    with open(path) as f:
        catalog = yaml.safe_load(f) or {}
    by_key = {}
    for entry in catalog.get("products", []):
        by_key[entry["id"].lower()] = entry
        for alias in entry.get("aliases", []):
            by_key[alias.lower()] = entry
    return by_key


def add_months(year, month, delta):
    """Return (year, month) shifted by delta months (can be negative)."""
    index = (year * 12 + (month - 1)) + delta
    return index // 12, (index % 12) + 1


def month_string(year, month):
    return "%04d-%02d" % (year, month)


def resolve_date_range(args):
    if args.start and args.end:
        return args.start, args.end
    today = date.today()
    ey, em = today.year, today.month
    sy, sm = add_months(ey, em, -12 * args.years_back)
    return month_string(sy, sm), month_string(ey, em)


def list_months(start_ym, end_ym):
    """Inclusive list of 'YYYY-MM' strings from start_ym through end_ym."""
    sy, sm = (int(p) for p in start_ym.split("-"))
    ey, em = (int(p) for p in end_ym.split("-"))
    start_index = sy * 12 + (sm - 1)
    end_index = ey * 12 + (em - 1)
    return [month_string(*add_months(sy, sm, i)) for i in range(end_index - start_index + 1)]


NON_DATA_TABLE_PREFIXES = (
    "citation",
    "readme",
    "issueLog",
    "variables",
    "sensor_positions",
    "science_review_flags",
    "categoricalCodes",
)


def download_one(args):
    """Download one catalog (or ad hoc) product for one site/date range.

    Does not raise for expected failure modes (missing token, unresolvable
    product, empty result, neonutilities error) -- callers (CLI `run()` or
    a bulk runner looping over many products) get a structured result back
    instead, so one product's failure doesn't take down a whole batch.

    Returns a dict:
        status: "ok" | "error"
        dpid, product (input alias), and on "error" an "error" message.
        On "ok", additionally: path, rows, date_min, date_max,
        months_expected, months_present, months_missing (list of
        'YYYY-MM' strings with no rows in the result).
    """
    token = args.token or os.environ.get("NEON_API_TOKEN")
    if not token:
        return {
            "status": "error",
            "product": args.product,
            "error": (
                "NEON_API_TOKEN is not set. NEON has required an "
                "authenticated request for every /data download since a "
                "June 2026 policy change -- get a free token from "
                "https://data.neonscience.org/ and export NEON_API_TOKEN, "
                "or pass --token."
            ),
        }

    catalog = load_catalog()
    entry = catalog.get(args.product.lower())

    if entry:
        dpid = entry["id"]
        shortname = entry["aliases"][0] if entry.get("aliases") else dpid.replace(".", "_")
        outdir = args.outdir or entry["folder"]
        file_match = args.file_match or entry["file_match"]
        interval_min = args.interval_min or entry["interval_min"]
        print(
            "[%s] resolved '%s' -> %s (%s) via %s"
            % (dpid, args.product, dpid, entry["data_type"], os.path.relpath(CATALOG_PATH))
        )
    else:
        dpid = args.product
        if not (args.outdir and args.file_match and args.interval_min):
            return {
                "status": "error",
                "product": args.product,
                "dpid": dpid,
                "error": (
                    "'%s' is not in %s, so --outdir, --file-match, and "
                    "--interval-min must all be given explicitly for an ad "
                    "hoc pull." % (args.product, os.path.relpath(CATALOG_PATH))
                ),
            }
        shortname = dpid.replace(".", "_")
        outdir = args.outdir
        file_match = args.file_match
        interval_min = args.interval_min
        print(
            "[%s] WARNING: '%s' is not in %s -- running ad hoc, nothing "
            "will be recorded for future runs." % (dpid, dpid, os.path.relpath(CATALOG_PATH))
        )

    start_ym, end_ym = resolve_date_range(args)
    expected_months = list_months(start_ym, end_ym)
    print(
        "[%s] fetching site=%s months=%s..%s (package=%s, table=%s, interval=%smin, %d months)"
        % (dpid, args.site, start_ym, end_ym, args.package, file_match, interval_min, len(expected_months))
    )

    try:
        tables = nu.load_by_product(
            dpid=dpid,
            site=args.site,
            startdate=start_ym,
            enddate=end_ym,
            package=args.package,
            timeindex=str(interval_min),
            token=token,
            check_size=False,
            progress=True,
        )
    except Exception as e:
        return {
            "status": "error",
            "product": args.product,
            "dpid": dpid,
            "error": "neonutilities failed for %s/%s-%s (%s: %s)" % (args.site, start_ym, end_ym, type(e).__name__, e),
        }

    if not tables or file_match not in tables:
        available = [k for k in (tables or {}) if not k.startswith(NON_DATA_TABLE_PREFIXES)]
        return {
            "status": "error",
            "product": args.product,
            "dpid": dpid,
            "error": (
                "expected table '%s' not found in neonutilities result. "
                "Data-like tables actually returned: %s. Check file_match "
                "/ interval_min in the catalog for this product." % (file_match, available)
            ),
        }

    df = tables[file_match]
    if df is None or len(df) == 0:
        return {
            "status": "error",
            "product": args.product,
            "dpid": dpid,
            "error": "no data rows returned for %s/%s in range %s-%s" % (args.site, dpid, start_ym, end_ym),
        }

    os.makedirs(outdir, exist_ok=True)
    out_name = "%s_%s_%s_%s.csv" % (args.site, shortname, start_ym, end_ym)
    out_path = os.path.join(outdir, out_name)
    df.to_csv(out_path, index=False)

    months_present = set()
    date_min = date_max = None
    if "startDateTime" in df.columns:
        parsed = pd.to_datetime(df["startDateTime"], errors="coerce")
        months_present = set(parsed.dt.strftime("%Y-%m").dropna().unique().tolist())
        date_min, date_max = df["startDateTime"].min(), df["startDateTime"].max()

    months_missing = [m for m in expected_months if m not in months_present]
    for m in expected_months:
        if m in months_present:
            print("[%s] %s: OK" % (dpid, m))
        else:
            print("[%s] %s: MISSING -- skipped (not published / no data for this month)" % (dpid, m))

    print("[%s] done -- wrote %d rows to %s" % (dpid, len(df), out_path))

    result = {
        "status": "ok",
        "product": args.product,
        "dpid": dpid,
        "path": out_path,
        "rows": len(df),
        "date_min": date_min,
        "date_max": date_max,
        "months_expected": len(expected_months),
        "months_missing": months_missing,
    }
    if "verticalPosition" in df.columns:
        result["vertical_positions"] = sorted(v for v in df["verticalPosition"].dropna().unique().tolist())
    return result


def run(args):
    result = download_one(args)
    if result["status"] == "error":
        print("ERROR: %s" % result["error"], file=sys.stderr)
        return 1

    print("Date coverage: %s -> %s" % (result["date_min"], result["date_max"]))
    if result["months_missing"]:
        print("Missing months (%d of %d): %s" % (len(result["months_missing"]), result["months_expected"], result["months_missing"]))
    if "vertical_positions" in result:
        print("verticalPosition values present: %s" % result["vertical_positions"])
    return 0


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Download and stack a NEON data product for one site/date range, via neonutilities."
    )
    p.add_argument("--site", required=True, help="NEON site ID, e.g. CLBJ")
    p.add_argument(
        "--product",
        required=True,
        help="Catalog alias (see metadata/sensor_catalog.yaml) or raw NEON product id, e.g. DP1.00002.001",
    )
    p.add_argument(
        "--outdir",
        default=None,
        help="Override the catalog's output folder (required if --product isn't in the catalog)",
    )
    p.add_argument(
        "--package",
        default="basic",
        choices=["basic", "expanded"],
        help="NEON data package to pull (default: basic)",
    )
    p.add_argument(
        "--file-match",
        dest="file_match",
        default=None,
        help="Override the catalog's stacked table name (required if --product isn't in the catalog)",
    )
    p.add_argument(
        "--interval-min",
        dest="interval_min",
        default=None,
        help="Override the catalog's averaging interval in minutes, passed to neonutilities as timeindex "
        "(required if --product isn't in the catalog)",
    )
    p.add_argument(
        "--years-back",
        type=int,
        default=5,
        help="Number of years back from today to pull, if --start/--end are not given",
    )
    p.add_argument("--start", help="Explicit start month, format YYYY-MM (overrides --years-back)")
    p.add_argument("--end", help="Explicit end month, format YYYY-MM (overrides --years-back)")
    p.add_argument(
        "--token",
        default=None,
        help="NEON API token (overrides NEON_API_TOKEN env var if both are set)",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(run(parse_args()))
