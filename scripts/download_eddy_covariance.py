#!/usr/bin/env python3
"""
download_eddy_covariance.py

Downloads and stacks NEON's Bundled Eddy Covariance product
(DP4.00200.001) for one site. Unlike every other script in this repo,
this product is delivered as HDF5 files, not CSV -- it needs
neonutilities.zips_by_product() (download only, no unzip/stack) followed
by neonutilities.stack_eddy(level="dp04") to get a tabular dataframe,
rather than the single load_by_product() call the other scripts use. See
the DP4.00200.001 entry in metadata/sensor_catalog.yaml for the full
rationale, including why the quality filter only touches one of the 11
qfFinl columns in the stacked table.

Eddy covariance downloads are far larger than every other product here
(measured ~130-150MB per CLBJ site-month vs a few MB for the sensor
products), so this script estimates total size and checks available disk
space before downloading anything.

Usage
-----
    python3 download_eddy_covariance.py --site CLBJ --years-back 5
"""

import argparse
import os
import shutil
import sys
import tempfile

import neonutilities as nu

from download_neon_product import CATALOG_PATH, list_months, load_catalog, resolve_date_range

QC_COLUMN = "qfqm.fluxCo2.nsae.qfFinl"  # NEE-specific final QC flag; see catalog notes
ESTIMATED_MB_PER_SITE_MONTH = 150  # padded up from a measured ~134MB CLBJ site-month


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Download and stack NEON bundled eddy covariance (DP4.00200.001) data.")
    p.add_argument("--site", default="CLBJ", help="NEON site ID (default CLBJ)")
    p.add_argument("--years-back", type=int, default=5, help="Years back from today to pull (default 5)")
    p.add_argument("--start", help="Explicit start month, format YYYY-MM (overrides --years-back)")
    p.add_argument("--end", help="Explicit end month, format YYYY-MM (overrides --years-back)")
    p.add_argument("--token", default=None, help="NEON API token (overrides NEON_API_TOKEN env var)")
    return p.parse_args(argv)


def check_disk_space(target_dir, num_months):
    os.makedirs(target_dir, exist_ok=True)
    estimated_bytes = num_months * ESTIMATED_MB_PER_SITE_MONTH * 1024 * 1024
    usage = shutil.disk_usage(target_dir)

    print(
        "Eddy covariance HDF5 downloads are much larger than the other products in "
        "this repo (NEON's own docs cite ~1GB per 2 site-months; a measured CLBJ "
        "test pull ran closer to ~130MB/month -- this estimate pads that up to "
        "%d MB/site-month for safety margin)." % ESTIMATED_MB_PER_SITE_MONTH
    )
    print("Estimated download size: ~%.2f GB across %d site-month(s)." % (estimated_bytes / 1e9, num_months))
    print(
        "Available disk space at %s: %.2f GB free of %.2f GB total."
        % (target_dir, usage.free / 1e9, usage.total / 1e9)
    )

    if estimated_bytes > usage.free * 0.9:
        print(
            "ERROR: estimated download size exceeds available free space (with a "
            "10%% safety margin). Aborting before downloading anything.",
            file=sys.stderr,
        )
        return False
    return True


def run(args):
    token = args.token or os.environ.get("NEON_API_TOKEN")
    if not token:
        print(
            "ERROR: NEON_API_TOKEN is not set. Export it or pass --token -- see "
            "download_neon_product.py for details on getting one.",
            file=sys.stderr,
        )
        return 1

    catalog = load_catalog()
    entry = catalog.get("dp4.00200.001")
    if not entry:
        print("ERROR: DP4.00200.001 not found in %s" % os.path.relpath(CATALOG_PATH), file=sys.stderr)
        return 1

    dpid = entry["id"]
    outdir = entry["folder"]

    start_ym, end_ym = resolve_date_range(argparse.Namespace(start=args.start, end=args.end, years_back=args.years_back))
    months = list_months(start_ym, end_ym)
    print("Fetching %s for site %s, months %s..%s (%d site-months)" % (dpid, args.site, start_ym, end_ym, len(months)))

    if not check_disk_space(outdir, len(months)):
        return 1

    staging_dir = tempfile.mkdtemp(prefix="eddy_covariance_")
    print("Downloading HDF5 zips to staging dir: %s" % staging_dir)

    try:
        nu.zips_by_product(
            dpid=dpid,
            site=args.site,
            startdate=start_ym,
            enddate=end_ym,
            package="basic",
            check_size=False,
            token=token,
            savepath=staging_dir,
            progress=True,
        )
    except Exception as e:
        print(
            "ERROR: zips_by_product failed (%s: %s). Staging files left at %s for debugging."
            % (type(e).__name__, e, staging_dir),
            file=sys.stderr,
        )
        return 1

    print("Download complete. Running stack_eddy(level='dp04') ...")
    try:
        stacked = nu.stack_eddy(filepath=staging_dir, level="dp04")
    except Exception as e:
        print(
            "ERROR: stack_eddy failed (%s: %s). Staging files left at %s for debugging."
            % (type(e).__name__, e, staging_dir),
            file=sys.stderr,
        )
        return 1

    df = stacked.get(args.site)
    if df is None or len(df) == 0:
        print(
            "ERROR: stack_eddy returned no data for site %s. Staging files left at %s for debugging."
            % (args.site, staging_dir),
            file=sys.stderr,
        )
        return 1

    if QC_COLUMN not in df.columns:
        print(
            "ERROR: expected QC column '%s' not found. Columns present: %s" % (QC_COLUMN, list(df.columns)),
            file=sys.stderr,
        )
        return 1

    total_rows = len(df)
    filtered = df[df[QC_COLUMN] == 0].reset_index(drop=True)
    dropped_rows = total_rows - len(filtered)

    os.makedirs(outdir, exist_ok=True)
    out_name = "%s_eddy_covariance_%s_%s.csv" % (args.site, start_ym, end_ym)
    out_path = os.path.join(outdir, out_name)
    filtered.to_csv(out_path, index=False)

    shutil.rmtree(staging_dir, ignore_errors=True)
    print("Cleaned up staging dir %s" % staging_dir)

    print("Done. Wrote %d rows to %s" % (len(filtered), out_path))
    if "timeBgn" in filtered.columns and len(filtered) > 0:
        print("Date coverage: %s -> %s" % (filtered["timeBgn"].min(), filtered["timeBgn"].max()))
    print(
        "Quality filter (%s == 0): dropped %d of %d rows (%.1f%%)"
        % (QC_COLUMN, dropped_rows, total_rows, 100.0 * dropped_rows / total_rows if total_rows else 0.0)
    )
    return 0


if __name__ == "__main__":
    sys.exit(run(parse_args()))
