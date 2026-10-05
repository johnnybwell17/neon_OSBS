#!/usr/bin/env python3
"""
upload_to_huggingface.py

Pushes this repo's pulled data to a HuggingFace dataset repo, via the
`huggingface_hub` package. Mirrors what was done manually (ad hoc, no
script) for neon_CPER -> https://huggingface.co/datasets/johnnybwell/neon_CPER
-- this script just makes that step repeatable instead of a one-off CLI
session.

What gets uploaded
-------------------
- `raw/` (every pulled product's combined CSVs) -- this is the actual
  dataset content.
- `metadata/` (sensor_catalog.yaml + its README) -- documents what each
  file is and how it was produced.
- The top-level `README.md` is uploaded as the dataset's model/dataset
  card (HF renders README.md at the repo root as the card automatically).

`scripts/` and `processed/` are NOT uploaded -- the former is code (lives
on GitHub instead), the latter is empty/local-analysis-only.

Auth
----
Requires being logged in with write access to the target repo:

    hf auth login

or set `HF_TOKEN` in the environment. This script does not read or print
any token -- `huggingface_hub` picks it up itself from the login cache or
the env var.

Examples
--------
Dry run (prints what would be uploaded, touches nothing remote):

    python3 scripts/upload_to_huggingface.py --dry-run

Real upload, creating the repo if it doesn't exist yet (public, per repo
default -- pass --private to override):

    python3 scripts/upload_to_huggingface.py
"""

import argparse
from pathlib import Path

from huggingface_hub import HfApi

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO_ID = "johnnybwell/neon_OSBS"
UPLOAD_PATHS = ["raw", "metadata", "README.md"]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID,
                    help=f"HF dataset repo id (default: {DEFAULT_REPO_ID})")
    p.add_argument("--private", action="store_true",
                    help="create the repo as private if it doesn't exist yet "
                         "(default: public; ignored if the repo already exists)")
    p.add_argument("--dry-run", action="store_true",
                    help="print what would be uploaded without contacting HF")
    return p.parse_args()


def main():
    args = parse_args()

    targets = [REPO_ROOT / p for p in UPLOAD_PATHS]
    missing = [t for t in targets if not t.exists()]
    if missing:
        print("Missing expected path(s), nothing uploaded:")
        for m in missing:
            print(f"  {m}")
        raise SystemExit(1)

    if args.dry_run:
        print(f"Would create/use dataset repo: {args.repo_id} "
              f"(private={args.private})")
        print("Would upload:")
        for t in targets:
            print(f"  {t.relative_to(REPO_ROOT)}")
        return

    api = HfApi()
    api.create_repo(repo_id=args.repo_id, repo_type="dataset",
                     private=args.private, exist_ok=True)

    for rel in UPLOAD_PATHS:
        local = REPO_ROOT / rel
        if local.is_dir():
            print(f"Uploading folder {rel}/ ...")
            api.upload_folder(repo_id=args.repo_id, repo_type="dataset",
                               folder_path=str(local), path_in_repo=rel)
        else:
            print(f"Uploading file {rel} ...")
            api.upload_file(repo_id=args.repo_id, repo_type="dataset",
                             path_or_fileobj=str(local), path_in_repo=rel)

    print(f"Done: https://huggingface.co/datasets/{args.repo_id}")


if __name__ == "__main__":
    main()
