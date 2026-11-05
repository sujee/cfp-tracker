#!/usr/bin/env python3
"""Rewrite the per-CFP notes to the current frontmatter shape, in place.

Drops any frontmatter ``notes`` (notes live only in the body) and re-quotes
every value safely. Idempotent: running it twice changes nothing the second
time. Safe to run on a vault that already matches the current format.

Usage (from the cfps/ folder):
    python3 src/normalize-data.py [--data data]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize per-CFP notes in place.")
    ap.add_argument("--data", default="data", help="Notes directory (default: data).")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import normalize_file

    data_dir = Path(args.data).resolve()
    if not data_dir.is_dir():
        print(f"notes directory not found: {data_dir}", file=sys.stderr)
        return 1

    changed = skipped = 0
    for p in sorted(data_dir.rglob("*.md")):
        if normalize_file(p):
            changed += 1
        else:
            skipped += 1
            print(f"skipped (no frontmatter): {p}", file=sys.stderr)

    print(f"normalized {changed} notes ({skipped} skipped) in {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
