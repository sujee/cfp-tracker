#!/usr/bin/env python3
"""Move unproduced CFP notes into an ``archived/`` folder, fail on collisions.

Expected manifests must exist and contain relative note paths. ``--skip-source``
protects unmodified notes owned by a deliberately unavailable source. Replaced
notes are explicitly supplied by reconciliation, so their curated fields can be
migrated before the old note is archived even when curation would normally keep
it live.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class ArchiveCollisionError(ValueError):
    """An archive destination already exists; no moves have been performed."""


def load_manifests(paths) -> set[str]:
    """Union validated relative note paths from every expected manifest file."""
    produced: set[str] = set()
    for value in paths or []:
        path = Path(value)
        if not path.is_file():
            raise FileNotFoundError(f"expected source manifest not found: {path}")
        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list) or not all(isinstance(rel, str) for rel in entries):
            raise ValueError(f"manifest must be a JSON list of note paths: {path}")
        for rel in entries:
            relative = Path(rel)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"manifest contains an unsafe note path {rel!r}: {path}")
        produced.update(entries)
    return produced


def has_manual_changes(fm: dict, body: str) -> bool:
    """Return whether a note contains user curation instead of generated defaults."""
    from cfp_writer import (
        KNOWN_FM_KEYS,
        _as_bool,
        _as_str,
        _extract_body_notes,
        _read_submissions,
    )

    custom_keys = set(fm) - KNOWN_FM_KEYS - {"tier"}
    return bool(
        _as_bool(fm.get("shortlist"))
        or _read_submissions(fm)
        or _extract_body_notes(body)
        or _as_str(fm.get("notes")).strip()
        or custom_keys
    )


def find_orphans(data_dir: Path, produced: set[str], skip_sources=(), superseded=()) -> list[str]:
    """Return notes eligible for archiving after one complete reconciliation.

    Curated unproduced notes normally stay live. A reconciler can explicitly mark
    a note as superseded after migrating its curated state, which overrides that
    protection for that note only. Non-CFP files are always left untouched.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import _read_frontmatter, _as_str, FrontmatterError

    skipped = {source for source in (skip_sources or ()) if source}
    replaced = set(superseded or ())
    orphans = []
    for path in sorted(data_dir.rglob("*.md")):
        rel = path.relative_to(data_dir).as_posix()
        if rel in produced:
            continue
        try:
            fm, body = _read_frontmatter(path)
        except FrontmatterError:
            continue
        if _as_str(fm.get("type")) != "cfp":
            continue
        if rel not in replaced:
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
    superseded=(),
) -> list[str]:
    """Move orphan notes byte-for-byte, or return planned moves for a dry run.

    Validate every destination before the first move. A collision aborts the
    operation instead of overwriting an existing archived note or leaving a
    partially executed move plan.
    """
    moved = find_orphans(data_dir, produced, skip_sources, superseded)
    moves = [(data_dir / rel, archive_dir / rel, rel) for rel in moved]
    if dry_run:
        return moved

    collisions = [dst for _src, dst, _rel in moves if dst.exists()]
    if collisions:
        names = ", ".join(str(path) for path in collisions)
        raise ArchiveCollisionError(f"archive destination(s) already exist: {names}")

    for src, dst, _rel in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    return moved


def main() -> int:
    ap = argparse.ArgumentParser(description="Archive notes no complete source produces.")
    ap.add_argument("--data", default="data", help="Live notes directory (default: data).")
    ap.add_argument("--archive", default="archived", help="Archive destination (default: archived).")
    ap.add_argument("--manifest", action="append", default=[], help="Expected source manifest JSON (repeatable).")
    ap.add_argument(
        "--superseded",
        action="append",
        default=[],
        help="Replacement manifest JSON from --superseded-manifest (repeatable).",
    )
    ap.add_argument(
        "--skip-source", action="append", default=[],
        help="Notes owned by this source are never archived (repeatable).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Report moves without changing files.")
    ap.add_argument("--json", action="store_true", help="Emit the moved paths as JSON.")
    args = ap.parse_args()

    data_dir = Path(args.data).resolve()
    archive_dir = Path(args.archive).resolve()
    try:
        produced = load_manifests(args.manifest)
        superseded = load_manifests(args.superseded)
        moved = archive_orphans(
            data_dir,
            archive_dir,
            produced,
            dry_run=args.dry_run,
            skip_sources=args.skip_source,
            superseded=superseded,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"archive-orphans: {exc}", file=sys.stderr)
        return 1

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
