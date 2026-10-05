#!/usr/bin/env python3
"""
download_all_products.py

Bulk-pulls every product currently listed in metadata/sensor_catalog.yaml
for one site, using download_neon_product.download_one() for each. Each
product is fetched at its catalog-native averaging interval (all 30 min
except precipitation, which NEON only publishes at 60 min/daily for CLBJ
-- see the notes on that catalog entry). One product failing (bad token,
deprecated product id, missing table, etc.) does not stop the others; it's
recorded and reported in the final summary.

Usage
-----
    python3 download_all_products.py --site CLBJ --years-back 5
"""

import argparse
import os
import sys

from download_neon_product import download_one, load_catalog

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
    p = argparse.ArgumentParser(description="Download every cataloged NEON product for one site.")
    p.add_argument("--site", required=True, help="NEON site ID, e.g. CLBJ")
    p.add_argument("--years-back", type=int, default=5, help="Years back from today to pull (default 5)")
    p.add_argument("--start", help="Explicit start month, format YYYY-MM (overrides --years-back)")
    p.add_argument("--end", help="Explicit end month, format YYYY-MM (overrides --years-back)")
    p.add_argument("--token", default=None, help="NEON API token (overrides NEON_API_TOKEN env var)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    catalog = load_catalog()
    missing = [alias for alias in CATALOG_ORDER if alias not in catalog]
    if missing:
        print("ERROR: these aliases are not in the catalog: %s" % missing, file=sys.stderr)
        return 1

    results = []
    for alias in CATALOG_ORDER:
        print("=" * 72)
        product_args = argparse.Namespace(
            site=args.site,
            product=alias,
            outdir=None,
            package="basic",
            file_match=None,
            interval_min=None,
            years_back=args.years_back,
            start=args.start,
            end=args.end,
            token=args.token,
        )
        result = download_one(product_args)
        if result["status"] != "ok":
            print("[%s] FAILED: %s" % (alias, result.get("error")), file=sys.stderr)
        results.append(result)

    print("=" * 72)
    print("SUMMARY (site=%s)" % args.site)
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
