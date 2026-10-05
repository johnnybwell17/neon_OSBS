#!/usr/bin/env python3
"""
neon_site_availability.py

Looks up, for a given NEON site, the true earliest/latest month with
published data for each cataloged product -- by querying NEON's site
metadata endpoint (https://data.neonscience.org/api/v0/sites/<site>),
which lists availableMonths per data product code. No token is needed for
this metadata endpoint (unlike /data, which NEON has required a token for
since June 2026).

This exists so a full-history pull can request each product's real
--start/--end instead of guessing a start date or applying one fixed
years-back window to every product -- coverage start differs by product
(e.g. at CPER, air_temperature starts 2014-02 but soil_moisture only
starts 2016-07) and by site, so a single guessed start date either misses
older data or generates spurious "missing month" entries in
download_one()'s summary for months that were simply never published in
the first place.

This is a separate, small helper rather than a change to
download_neon_product.py's --years-back/resolve_date_range() logic, so
that script (and any existing --years-back-based usage of it) stays
untouched and drop-in reusable.

Usage
-----
Print a table of every cataloged (non-PhenoCam) product's available range
for a site:

    python3 neon_site_availability.py --site CPER

Import for use by another script:

    from neon_site_availability import fetch_site_metadata, get_available_range
    site_metadata = fetch_site_metadata("CPER")
    start_ym, end_ym = get_available_range("CPER", "DP1.00002.001", site_metadata)
"""

import argparse
import os
import sys

import requests

from download_neon_product import CATALOG_PATH, load_catalog

SITES_API_URL = "https://data.neonscience.org/api/v0/sites/%s"


def fetch_site_metadata(site):
    """Fetch a site's metadata (no token required -- this is the /sites
    metadata endpoint, not /data)."""
    resp = requests.get(SITES_API_URL % site, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"]


def get_available_range(site, dpid, site_metadata=None):
    """Return (start_ym, end_ym) as 'YYYY-MM' strings for the given dpid
    at the given site, or (None, None) if that product isn't offered
    there at all. `site_metadata` can be passed in (from a prior
    fetch_site_metadata() call) to avoid re-fetching per product.
    """
    data = site_metadata if site_metadata is not None else fetch_site_metadata(site)
    for product in data.get("dataProducts", []):
        if product["dataProductCode"] == dpid:
            months = product.get("availableMonths") or []
            if not months:
                return None, None
            return months[0], months[-1]
    return None, None


def catalog_products(catalog):
    """Every unique non-PhenoCam catalog entry (PhenoCam Network products
    aren't in NEON's /data API or this /sites metadata, so they're not
    relevant here -- see download_phenocam_gcc.py for that source)."""
    seen_ids = set()
    entries = []
    for entry in catalog.values():
        if entry.get("source") == "phenocam_network":
            continue
        if entry["id"] in seen_ids:
            continue
        seen_ids.add(entry["id"])
        entries.append(entry)
    return entries


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Look up each cataloged NEON product's true available date range for a site."
    )
    p.add_argument("--site", required=True, help="NEON site ID, e.g. CPER")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    catalog = load_catalog()
    entries = catalog_products(catalog)

    try:
        site_metadata = fetch_site_metadata(args.site)
    except Exception as e:
        print(
            "ERROR: failed to fetch site metadata for %s (%s: %s)" % (args.site, type(e).__name__, e),
            file=sys.stderr,
        )
        return 1

    print("Available date ranges for %s, per %s and NEON's /sites metadata:" % (args.site, os.path.relpath(CATALOG_PATH)))
    print("-" * 72)
    for entry in sorted(entries, key=lambda e: e["id"]):
        start_ym, end_ym = get_available_range(args.site, entry["id"], site_metadata=site_metadata)
        alias = entry["aliases"][0] if entry.get("aliases") else entry["id"]
        if start_ym is None:
            print("%-22s %-14s NOT OFFERED at %s" % (alias, entry["id"], args.site))
        else:
            print("%-22s %-14s %s -> %s" % (alias, entry["id"], start_ym, end_ym))
    return 0


if __name__ == "__main__":
    sys.exit(main())
