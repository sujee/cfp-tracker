#!/usr/bin/env python3
"""Move notes no longer produced by any source into an ``archived/`` folder.

A refresh only ever writes the notes the sources still carry. When a source drops
an event, its note would otherwise linger in ``data/`` forever. This script takes
the union of note paths produced by the current run (the per-source ``--manifest``
files) and, for every other ``.md`` under ``--data``, moves it into ``--archive``
(keeping the ``<year>/`` layout). ``cfps.base`` scopes its live views to ``data/``
and has a separate Archived view, so moved notes simply drop out of the live views.

Nothing is updated or deleted — an untouched note file is moved byte-for-byte.
Notes with user curation stay in ``data/``: a shortlist flag, a submission,
body notes, or custom frontmatter. The registry-managed ``tier``
property alone does not count as curation.

Usage::

    python3 src/archive-orphans.py --data data --archive archived \\
        --manifest /tmp/m-dev.json --manifest /tmp/m-confs.json --manifest /tmp/m-manual.json

A source can be deliberately skipped for a run (``config.INPUT_SOURCES``). Its notes
were never asked to be produced, so they are not orphans: ``--skip-source NAME``
(repeatable) leaves every note whose ``source`` frontmatter matches untouched.
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


def has_manual_changes(fm: dict, body: str) -> bool:
    """Return whether a note contains user curation instead of generated defaults.

    These fields have known generated defaults, so the current values can be
    compared without another copy of the note. ``tier`` is excluded because the
    prestige registry writes it automatically.
    """
    from cfp_writer import (
        KNOWN_FM_KEYS,
        _as_bool,
        _extract_body_notes,
        _read_submissions,
    )

    custom_keys = set(fm) - KNOWN_FM_KEYS - {"tier"}
    return bool(
        _as_bool(fm.get("shortlist"))
        or _read_submissions(fm)
        or _extract_body_notes(body)
        or custom_keys
    )


def find_orphans(data_dir: Path, produced: set[str], skip_sources=()) -> list[str]:
    """Relative paths of ``type: cfp`` notes under *data_dir* that no source produced.

    Non-CFP notes (anything without ``type: cfp``) are left alone — the pipeline
    only owns its own generated notes. A note whose ``source`` is one of
    *skip_sources* is also left alone: that source was deliberately not run, so
    its notes are un-produced by choice, not dropped by upstream. A note with
    user curation is left alone as well, before any move can occur.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import _read_frontmatter, _as_str, FrontmatterError

    skipped = {s for s in (skip_sources or ()) if s}
    orphans = []
    for p in sorted(data_dir.rglob("*.md")):
        rel = p.relative_to(data_dir).as_posix()
        if rel in produced:
            continue
        try:
            fm, body = _read_frontmatter(p)
        except FrontmatterError:
            continue  # not ours to move
        if _as_str(fm.get("type")) != "cfp":
            continue
        if _as_str(fm.get("source")) in skipped:
            continue
        if has_manual_changes(fm, body):
            continue
        orphans.append(rel)
    return orphans


def archive_orphans(
    data_dir: Path,
    archive_dir: Path,
    produced: set[str],
    dry_run: bool = False,
    skip_sources=(),
) -> list[str]:
    """Move orphan notes into *archive_dir* (plain move, no edits).

    Returns the list of relative paths that were (or would be) moved.
    """
    moved = []
    for rel in find_orphans(data_dir, produced, skip_sources):
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
    ap.add_argument(
        "--skip-source", action="append", default=[],
        help="Notes owned by this source are never orphans (repeatable; a deliberately skipped source).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Report orphans without moving anything.")
    ap.add_argument("--json", action="store_true", help="Emit the moved paths as JSON.")
    args = ap.parse_args()

    data_dir = Path(args.data).resolve()
    archive_dir = Path(args.archive).resolve()
    produced = load_manifests(args.manifest)
    moved = archive_orphans(
        data_dir, archive_dir, produced, dry_run=args.dry_run, skip_sources=args.skip_source
    )

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
