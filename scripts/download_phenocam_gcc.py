#!/usr/bin/env python3
"""
download_phenocam_gcc.py

Downloads the daily GCC (green chromatic coordinate) summary CSV for a
site's PhenoCam Network camera(s), straight from phenocam.nau.edu's own
archive. Unlike download_neon_product.py this does NOT go through NEON's
/data API and needs no NEON_API_TOKEN -- it's a separate, fully open
archive.

Which PhenoCam Network site name(s)/ROI(s)/output folder(s) apply to a
given --site are looked up from metadata/sensor_catalog.yaml: every
catalog entry with `source: phenocam_network` whose `id` contains the
given site code (e.g. site='CPER' matches an id like
'NEON.D10.CPER.DP1.00042') is pulled -- there is no hardcoded per-site
alias list here, so adding a new site only requires adding catalog
entries for it, not editing this script.

Usage
-----
    python3 download_phenocam_gcc.py --site CPER --full-history

    python3 download_phenocam_gcc.py --site CPER --years-back 5
"""

import argparse
import io
import os
import sys

import pandas as pd
import requests

from download_neon_product import load_catalog, CATALOG_PATH

GAP_WARNING_DAYS = 14  # a single missing run at least this long gets flagged


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Download a site's PhenoCam Network daily GCC summaries.")
    p.add_argument("--site", required=True, help="NEON site ID, e.g. CPER -- matched against catalog entry ids")
    p.add_argument(
        "--years-back",
        type=int,
        default=5,
        help="Years back from the latest available date in each series to keep (default 5). "
        "Ignored if --full-history is given.",
    )
    p.add_argument(
        "--full-history",
        action="store_true",
        help="Keep each camera/ROI's entire archive instead of applying --years-back as a trailing cutoff",
    )
    return p.parse_args(argv)


def phenocam_entries_for_site(catalog, site):
    """Every unique PhenoCam Network catalog entry for this site, matched
    by the site code appearing in the entry's `id` (e.g.
    'NEON.D10.CPER.DP1.00042' for site='CPER') -- rather than a fixed
    alias list, so this script works unmodified for any site once its
    PhenoCam catalog entries exist.
    """
    seen_ids = set()
    entries = []
    for entry in catalog.values():
        if entry.get("source") != "phenocam_network":
            continue
        if entry["id"] in seen_ids:
            continue
        if site.upper() not in entry["id"].upper():
            continue
        seen_ids.add(entry["id"])
        entries.append(entry)
    return entries


def fetch_gcc_csv(entry):
    """Fetch and concatenate one or more ROI generations for a site.

    Some cameras have their ROI redefined over time (FOV/crop changes),
    producing multiple non-overlapping '{site}_{roi}_1day.csv' series
    for the same physical camera -- catalog entries with more than one
    of these list them oldest-to-newest under `rois`; entries with only
    one ROI ever defined use the singular `roi` field instead.
    """
    site = entry["id"]
    rois = entry.get("rois") or [entry["roi"]]

    frames = []
    urls = []
    for roi in rois:
        filename = entry["file_match"].format(site=site, roi=roi)
        url = "%s/%s/ROI/%s" % (entry["base_url"], site, filename)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), comment="#")
        df["date"] = pd.to_datetime(df["date"])
        df["roi"] = roi
        frames.append(df)
        urls.append(url)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("date").drop_duplicates(subset="date", keep="last").reset_index(drop=True)
    return combined, urls


def find_gaps(dates, threshold_days=GAP_WARNING_DAYS):
    """Runs of missing calendar days >= threshold_days within [min(dates),
    max(dates)]. Returns a list of (gap_start, gap_end, num_days)."""
    full_range = pd.date_range(dates.min(), dates.max(), freq="D")
    missing = full_range.difference(dates)
    if missing.empty:
        return []

    gaps = []
    run_start = prev = missing[0]
    for d in missing[1:]:
        if (d - prev).days > 1:
            if (prev - run_start).days + 1 >= threshold_days:
                gaps.append((run_start, prev, (prev - run_start).days + 1))
            run_start = d
        prev = d
    if (prev - run_start).days + 1 >= threshold_days:
        gaps.append((run_start, prev, (prev - run_start).days + 1))
    return gaps


def run(args):
    catalog = load_catalog()
    entries = phenocam_entries_for_site(catalog, args.site)
    if not entries:
        print(
            "ERROR: no PhenoCam Network catalog entries found for site '%s' in %s"
            % (args.site, os.path.relpath(CATALOG_PATH)),
            file=sys.stderr,
        )
        return 1

    overall_ok = True

    for entry in entries:
        alias = entry["aliases"][0] if entry.get("aliases") else entry["id"]
        rois = entry.get("rois") or [entry["roi"]]
        print("=" * 72)
        print("[%s] fetching %s (ROI(s)=%s)" % (entry["id"], alias, ", ".join(rois)))
        try:
            df, urls = fetch_gcc_csv(entry)
        except Exception as e:
            print(
                "[%s] ERROR: failed to fetch/parse %s (%s: %s)"
                % (entry["id"], alias, type(e).__name__, e),
                file=sys.stderr,
            )
            overall_ok = False
            continue

        if args.full_history:
            filtered = df.sort_values("date").reset_index(drop=True)
        else:
            max_date = df["date"].max()
            cutoff = max_date - pd.DateOffset(years=args.years_back)
            filtered = df[df["date"] >= cutoff].sort_values("date").reset_index(drop=True)

        os.makedirs(entry["folder"], exist_ok=True)
        start_str = filtered["date"].min().strftime("%Y-%m-%d")
        end_str = filtered["date"].max().strftime("%Y-%m-%d")
        out_name = "%s_%s_%s_%s.csv" % (args.site, alias, start_str, end_str)
        out_path = os.path.join(entry["folder"], out_name)
        filtered.to_csv(out_path, index=False)

        for u in urls:
            print("[%s] source: %s" % (entry["id"], u))
        print("[%s] wrote %d rows to %s" % (entry["id"], len(filtered), out_path))
        print("[%s] date coverage: %s -> %s" % (entry["id"], start_str, end_str))

        expected_days = (filtered["date"].max() - filtered["date"].min()).days + 1
        present_days = filtered["date"].nunique()
        missing_days = expected_days - present_days
        gaps = find_gaps(filtered["date"])

        if gaps:
            print(
                "[%s] WARNING: %d/%d expected days missing, including %d gap run(s) >= %d days:"
                % (entry["id"], missing_days, expected_days, len(gaps), GAP_WARNING_DAYS)
            )
            for gap_start, gap_end, n in gaps:
                print("    %s -> %s (%d days)" % (gap_start.date(), gap_end.date(), n))
        else:
            print(
                "[%s] no gaps >= %d days (%d/%d expected days present)"
                % (entry["id"], GAP_WARNING_DAYS, present_days, expected_days)
            )

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(run(parse_args()))
