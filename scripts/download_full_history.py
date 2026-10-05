#!/usr/bin/env python3
"""
download_full_history.py

Bulk-pulls every cataloged NEON sensor product (the 11 basic-package
products in metadata/sensor_catalog.yaml -- NOT eddy covariance, NOT
PhenoCam, see below) for one site, using each product's own true
earliest/latest available month (via neon_site_availability.py) instead
of a fixed --years-back trailing window.

This exists because coverage start differs by product and by site (e.g.
at CPER, air_temperature starts 2014-02 but soil_moisture only starts
2016-07 -- run `python3 neon_site_availability.py --site CPER` to see the
full table). A single guessed start date applied to every product would
either miss older data (if picked too late) or generate spurious
"missing month" entries in the summary for months that were never
published at this site in the first place (if picked too early).

download_neon_product.py's --years-back/resolve_date_range() logic is
left completely untouched by this script -- it calls the same
download_one() building block directly with an explicit start/end
Namespace per product, so any existing --years-back-based usage of that
script (e.g. neon_CLBJ's trailing-5-year pulls) keeps working unchanged.

Eddy covariance (DP4.00200.001) is deliberately NOT included here -- it's
a much larger download than the other 11 products (see
download_eddy_covariance.py's own disk-space check, which this script
does not duplicate) and uses a different neonutilities call path
(zips_by_product + stack_eddy, not load_by_product). Run
`neon_site_availability.py --site <site>` to get its available range,
then pass --start/--end explicitly to download_eddy_covariance.py
yourself as a separate, manually-confirmed step -- see this project's
README for the full walkthrough.

PhenoCam is also excluded -- it's not a NEON /data API product at all
(see download_phenocam_gcc.py) and is always run as its own separate
step regardless of site.

Usage
-----
    python3 download_full_history.py --site CPER
"""

import argparse
import sys

from download_neon_product import download_one, load_catalog
from neon_site_availability import fetch_site_metadata, get_available_range

CATALOG_ORDER = [
    "soil_moisture",
    "soil_temperature",
    "air_temperature",
    "relative_humidity",
    "barometric_pressure",
    "precipitation",
    "wind",
    "radiation_net",
    "radiation_par",
    "soil_heat_flux",
    "soil_co2",
]


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Download every cataloged NEON sensor product for one site, "
        "each at its own full available history (not a fixed years-back window)."
    )
    p.add_argument("--site", required=True, help="NEON site ID, e.g. CPER")
    p.add_argument("--token", default=None, help="NEON API token (overrides NEON_API_TOKEN env var)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    catalog = load_catalog()
    missing = [alias for alias in CATALOG_ORDER if alias not in catalog]
    if missing:
        print("ERROR: these aliases are not in the catalog: %s" % missing, file=sys.stderr)
        return 1

    try:
        site_metadata = fetch_site_metadata(args.site)
    except Exception as e:
        print(
            "ERROR: failed to fetch site metadata for %s (%s: %s)" % (args.site, type(e).__name__, e),
            file=sys.stderr,
        )
        return 1

    results = []
    for alias in CATALOG_ORDER:
        entry = catalog[alias]
        print("=" * 72)

        start_ym, end_ym = get_available_range(args.site, entry["id"], site_metadata=site_metadata)
        if start_ym is None:
            print("[%s] SKIPPED: not offered at %s per NEON site metadata" % (entry["id"], args.site))
            results.append(
                {"status": "error", "product": alias, "dpid": entry["id"], "error": "not offered at %s" % args.site}
            )
            continue

        print("[%s] full history at %s: %s -> %s" % (entry["id"], args.site, start_ym, end_ym))
        product_args = argparse.Namespace(
            site=args.site,
            product=alias,
            outdir=None,
            package="basic",
            file_match=None,
            interval_min=None,
            years_back=None,
            start=start_ym,
            end=end_ym,
            token=args.token,
        )
        result = download_one(product_args)
        if result["status"] != "ok":
            print("[%s] FAILED: %s" % (alias, result.get("error")), file=sys.stderr)
        results.append(result)

    print("=" * 72)
    print("SUMMARY (site=%s, full history per product)" % args.site)
    print("-" * 72)
    ok_count = 0
    for result in results:
        alias = result["product"]
        if result["status"] == "ok":
            ok_count += 1
            missing_n = len(result["months_missing"])
            print(
                "%-22s %-16s rows=%-9d %s -> %s%s"
                % (
                    alias,
                    result["dpid"],
                    result["rows"],
                    result["date_min"],
                    result["date_max"],
                    "  (%d months missing)" % missing_n if missing_n else "",
                )
            )
        else:
            print("%-22s FAILED: %s" % (alias, result.get("error")))
    print("-" * 72)
    print("%d/%d products downloaded successfully" % (ok_count, len(results)))

    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
