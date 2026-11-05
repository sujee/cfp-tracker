#!/usr/bin/env python3
"""Move notes no longer produced by any source into an ``archived/`` folder.

A refresh only ever writes the notes the sources still carry. When a source drops
an event, its note would otherwise linger in ``data/`` forever. This script takes
the union of note paths produced by the current run (the per-source ``--manifest``
files) and, for every other ``.md`` under ``--data``, moves it into ``--archive``
(keeping the ``<year>/`` layout). ``cfps.base`` scopes its live views to ``data/``
and has a separate Archived view, so moved notes simply drop out of the live views.

Nothing is updated or deleted — the note file is moved byte-for-byte, edits and all.

Usage::

    python3 src/archive-orphans.py --data data --archive archived \\
        --manifest /tmp/m-dev.json --manifest /tmp/m-confs.json --manifest /tmp/m-manual.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_manifests(paths) -> set[str]:
    """Union of the data_dir-relative note paths from the given manifest files."""
    produced: set[str] = set()
    for p in paths or []:
        path = Path(p)
        if path.is_file():
            produced.update(json.loads(path.read_text(encoding="utf-8")))
    return produced


def find_orphans(data_dir: Path, produced: set[str]) -> list[str]:
    """Relative paths of ``type: cfp`` notes under *data_dir* that no source produced.

    Non-CFP notes (anything without ``type: cfp``) are left alone — the pipeline
    only owns its own generated notes.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import _read_frontmatter, _as_str, FrontmatterError

    orphans = []
    for p in sorted(data_dir.rglob("*.md")):
        rel = p.relative_to(data_dir).as_posix()
        if rel in produced:
            continue
        try:
            fm, _ = _read_frontmatter(p)
        except FrontmatterError:
            continue  # not ours to move
        if _as_str(fm.get("type")) != "cfp":
            continue
        orphans.append(rel)
    return orphans


def archive_orphans(
    data_dir: Path, archive_dir: Path, produced: set[str], dry_run: bool = False
) -> list[str]:
    """Move orphan notes into *archive_dir* (plain move, no edits).

    Returns the list of relative paths that were (or would be) moved.
    """
    moved = []
    for rel in find_orphans(data_dir, produced):
        src = data_dir / rel
        dst = archive_dir / rel
        moved.append(rel)
        if dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    return moved


def main() -> int:
    ap = argparse.ArgumentParser(description="Archive notes no source produces any more.")
    ap.add_argument("--data", default="data", help="Live notes directory (default: data).")
    ap.add_argument("--archive", default="archived", help="Where orphans are moved (default: archived).")
    ap.add_argument("--manifest", action="append", default=[], help="A per-source manifest JSON (repeatable).")
    ap.add_argument("--dry-run", action="store_true", help="Report orphans without moving anything.")
    ap.add_argument("--json", action="store_true", help="Emit the moved paths as JSON.")
    args = ap.parse_args()

    data_dir = Path(args.data).resolve()
    archive_dir = Path(args.archive).resolve()
    produced = load_manifests(args.manifest)
    moved = archive_orphans(data_dir, archive_dir, produced, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(moved, indent=2))
        return 0

    verb = "would archive" if args.dry_run else "archived"
    print(f"archive-orphans: {verb} {len(moved)} note(s) -> {archive_dir}")
    for rel in moved:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
