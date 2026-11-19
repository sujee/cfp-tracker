#!/usr/bin/env python3
"""Archive unproduced CFP notes, with optional rolling-window retention.

Expected manifests must exist and contain relative note paths. ``--skip-source``
protects unmodified notes owned by a deliberately unavailable source. Duplicate
notes are explicitly supplied after reconciliation migrates their curated fields.
They can therefore move even when curation would normally keep them live.
"""
from __future__ import annotations

import argparse
import datetime
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
    """Return whether a note contains user curation instead of generated defaults.

    The writer-owned ``## Conflict`` section is not curation: the pipeline
    regenerates it on every rewrite, so a conflict alone must not keep an
    unproduced note alive.
    """
    from cfp_writer import (
        KNOWN_FM_KEYS,
        _as_bool,
        _as_str,
        _extract_body_notes,
        _read_submissions,
        _split_conflict_section,
    )

    notes, _conflict = _split_conflict_section(_extract_body_notes(body))
    custom_keys = set(fm) - KNOWN_FM_KEYS - {"tier"}
    return bool(
        _as_bool(fm.get("shortlist"))
        or _read_submissions(fm)
        or notes
        or _as_str(fm.get("notes")).strip()
        or custom_keys
    )


def _iso_day(value):
    """Return a date for an exact ISO frontmatter value, else ``None``."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _excluded_from_retention(fm: dict) -> bool:
    """Apply the configured name, type, and topic exclusions to a stored note."""
    import config
    from cfp_writer import (
        _as_list,
        _as_str,
        _event_name,
        _event_type_included,
        event_name_is_ignored,
        infer_event_type,
    )

    name = _event_name(fm)
    if event_name_is_ignored(name):
        return True
    event_type = _as_str(fm.get("event_type")).strip() or infer_event_type(name)
    if not _event_type_included(event_type):
        return True
    ignored = [str(term).casefold() for term in getattr(config, "IGNORE_TOPICS", [])]
    texts = [name, *_as_list(fm.get("topics"))]
    return any(term in text.casefold() for term in ignored for text in texts)


def _same_cfp_identity(first: dict, second: dict) -> bool:
    """Match current CFP identity, with a strict event-page fallback for URL edits."""
    from cfp_writer import _event_name, _name_tokens, _names_compatible, _url_key

    if not _names_compatible(_event_name(first), _event_name(second)):
        return False
    first_cfp = _url_key(first.get("cfp_url"))
    if first_cfp and first_cfp == _url_key(second.get("cfp_url")):
        return True

    # A changed CFP URL needs stronger evidence than the usual name heuristic.
    # Equal token sets allow year-only name changes but separate workshops and
    # other suffix editions from the main event. Placeholder dates never match.
    first_event = _url_key(first.get("event_url"))
    first_date = _iso_day(first.get("event_date"))
    if (
        not first_event
        or first_event != _url_key(second.get("event_url"))
        or not first_date
        or first_date != _iso_day(second.get("event_date"))
    ):
        return False
    first_tokens = _name_tokens(_event_name(first))
    return bool(first_tokens and first_tokens == _name_tokens(_event_name(second)))


def find_orphans(
    data_dir: Path,
    produced: set[str],
    skip_sources=(),
    superseded=(),
    retain_after=None,
) -> list[str]:
    """Return notes eligible for archiving after one complete reconciliation.

    Curated unproduced notes normally stay live. A reconciler can explicitly mark
    a merged duplicate as superseded after migrating its curated state. This
    overrides protection for that duplicate only. Eligible source-missing notes
    with deadlines on or after ``retain_after`` also stay live. Exclusions and
    current duplicate matches override this rolling-window protection.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import _read_frontmatter, _as_str, FrontmatterError

    cutoff = _iso_day(retain_after) if retain_after is not None else None
    if retain_after is not None and cutoff is None:
        raise ValueError(f"retain_after must be YYYY-MM-DD, got {retain_after!r}")
    current_notes = []
    paths = sorted(data_dir.rglob("*.md"))
    if cutoff:
        for path in paths:
            if path.relative_to(data_dir).as_posix() not in produced:
                continue
            try:
                fm, _body = _read_frontmatter(path)
            except (OSError, FrontmatterError):
                continue
            if _as_str(fm.get("type")) == "cfp":
                current_notes.append(fm)

    skipped = {source for source in (skip_sources or ()) if source}
    replaced = set(superseded or ())
    orphans = []
    for path in paths:
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
            close = _iso_day(fm.get("cfp_close"))
            if cutoff and close and close >= cutoff:
                if not _excluded_from_retention(fm) and not any(
                    _same_cfp_identity(fm, current) for current in current_notes
                ):
                    continue
        orphans.append(rel)
    return orphans


def _collision_destination(src: Path, dst: Path, dry_run: bool) -> Path | None:
    """Resolve one destination without overwriting any existing note.

    Identical copies collapse by removing only the duplicate source. Conflicts
    receive a numbered ``-collision-N`` filename instead of aborting the run.
    """
    if not dst.exists():
        return dst
    if src == dst or src.read_bytes() == dst.read_bytes():
        if src != dst and not dry_run:
            src.unlink()
        return None
    number = 1
    while True:
        candidate = dst.with_name(f"{dst.stem}-collision-{number}{dst.suffix}")
        if not candidate.exists():
            return candidate
        if src.read_bytes() == candidate.read_bytes():
            if not dry_run:
                src.unlink()
            return None
        number += 1


def archive_orphans(
    data_dir: Path,
    archive_dir: Path,
    produced: set[str],
    dry_run: bool = False,
    skip_sources=(),
    superseded=(),
    retain_after=None,
) -> list[str]:
    """Move orphan notes byte-for-byte, or return planned moves for a dry run.

    Identical archived copies collapse without losing content. Conflicting
    versions receive collision suffixes instead of overwriting archived notes.
    """
    moved = find_orphans(
        data_dir, produced, skip_sources, superseded, retain_after=retain_after
    )
    moves = []
    for src in [data_dir / rel for rel in moved]:
        dst = _collision_destination(src, archive_dir / src.relative_to(data_dir), dry_run)
        if dst is not None:
            moves.append((src, dst, dst.relative_to(archive_dir).as_posix()))
    if dry_run:
        return [rel for _src, _dst, rel in moves]
    for src, dst, _rel in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    return [rel for _src, _dst, rel in moves]


def main() -> int:
    ap = argparse.ArgumentParser(description="Archive notes no complete source produces.")
    ap.add_argument("--data", default="data", help="Live notes directory (default: data).")
    ap.add_argument("--archive", default="archived", help="Archive destination (default: archived).")
    ap.add_argument("--manifest", action="append", default=[], help="Expected source manifest JSON (repeatable).")
    ap.add_argument(
        "--superseded",
        action="append",
        default=[],
        help="Merged-duplicate manifest JSON from --superseded-manifest (repeatable).",
    )
    ap.add_argument(
        "--retain-after",
        default=None,
        help="Keep eligible source-missing CFPs closing on or after YYYY-MM-DD.",
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
            retain_after=args.retain_after,
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
