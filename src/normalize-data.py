#!/usr/bin/env python3
"""Rewrite the per-CFP notes to the current frontmatter shape, in place.

Moves legacy frontmatter ``notes`` into the body and emits current note fields.
Only existing ``type: cfp`` notes are processed. Other Markdown files stay
unchanged. Missing flags and timestamps are back-filled without changing valid
stamps. Running the command twice leaves notes unchanged after the first pass.

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
            print(f"skipped (not an existing CFP note): {p}", file=sys.stderr)

    print(f"normalized {changed} notes ({skipped} skipped) in {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
