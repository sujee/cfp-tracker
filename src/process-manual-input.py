#!/usr/bin/env python3
"""Merge manually curated conference tables into per-CFP notes.

Only the files named in ``config.MANUAL_INPUT_FILES`` are read, resolved inside
``--input``. Scraps, checklists, and newly dropped files under ``input/`` are not
CFP sources until they are explicitly listed. To opt in to another file, add its
basename there; to remove one, comment its entry out.

Two opt-in file shapes coexist in that list: markdown CFP tables (no network),
and checklists of ``- [Conference](https://event-url/)`` links (discovered only
on the site itself, by ``src/watchlist.py``). Every other row is still ignored.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import watchlist

# Markdown link in a table cell: ``[text](url)`` (optional title).
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_EMPH_RE = re.compile(r"[*_]{1,3}")

_CLOSE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y")


def _clean_name(raw: str) -> tuple[str, str]:
    """Return ``(display name, url)`` from a cell like ``**[Name](url)**``.

    Without this the markdown source leaks into the name and the slug (a Google
    redirect URL became part of the filename).
    """
    raw = (raw or "").strip()
    m = _MD_LINK_RE.search(raw)
    if m:
        name, url = m.group(1), m.group(2)
    else:
        name, url = raw, ""
    name = re.sub(r"\s+", " ", _EMPH_RE.sub("", name)).strip()
    return name, url


def _unwrap_url(url: str) -> str:
    """Return the real target of a Google redirect wrapper, else *url* itself."""
    if not url:
        return ""
    if "google.com/url" in url:
        m = re.search(r"[?&]q=([^&]+)", url)
        if m:
            return unquote(m.group(1))
    return url


def _normalize_close(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return "—"
    for fmt in _CLOSE_FORMATS:
        try:
            return __import__("datetime").datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    # No exact date: drop "Unstated" qualifiers, e.g. "Dec 2026 / Unstated" -> "Dec 2026".
    parts = [p.strip() for p in raw.split("/") if p.strip() and "unstated" not in p.lower()]
    if not parts:
        return "Unstated"
    text = " / ".join(parts)
    for fmt in _CLOSE_FORMATS:
        try:
            return __import__("datetime").datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def parse_rows(text: str) -> list[dict]:
    rows = []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]

    for line in text.splitlines():
        if line.strip().startswith("|"):
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) >= 5 and not cols[0].lower().startswith("conf name") and not set(cols[0]) <= set("-: "):
                name, url = _clean_name(cols[0])
                if not name or "would you like" in name.lower():
                    continue
                if any(t in name.lower() for t in _IGNORE):
                    continue
                rows.append(
                    {
                        "name": name,
                        "location": cols[1],
                        "cfp_close": _normalize_close(cols[3]),
                        "event_date": cols[4],
                        "topics": cols[5] if len(cols) > 5 else "",
                        "event_url": _unwrap_url(url),
                        "cfp_url": "",
                    }
                )
    return rows


def manual_input_files(input_dir: Path) -> list[Path]:
    """Resolve the explicit manual input file list inside *input_dir*.

    ``MANUAL_INPUT_FILES`` in config is a list of relative paths — typically one
    basename, e.g. ``gmail1.md`` — never a directory sweep. An absent setting
    falls back to legacy ``*.md`` globbing (callers outside this repo still work);
    an empty list returns no files so manual input can be disabled while
    remaining enabled in ``INPUT_SOURCES``. Each named path must be a relative
    file inside the directory, and must exist: a typo would otherwise make its
    conferences vanish silently from the next refresh.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    configured = getattr(_cfg, "MANUAL_INPUT_FILES", None)
    if configured is None:
        return sorted(input_dir.glob("*.md"))
    if isinstance(configured, str) or not hasattr(configured, "__iter__"):
        raise ValueError("config.MANUAL_INPUT_FILES must be a list of relative file paths")

    files: list[Path] = []
    for item in configured:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("config.MANUAL_INPUT_FILES must contain nonempty file paths")
        name = item.strip()
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"config.MANUAL_INPUT_FILES entry must stay inside {input_dir}: {name!r}"
            )
        path = input_dir / relative
        if not path.is_file():
            raise FileNotFoundError(
                f"configured manual input file not found: {path} "
                "(fix MANUAL_INPUT_FILES in src/config_local.py or restore the file)"
            )
        files.append(path)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--input", default="input")
    ap.add_argument("--manifest", default=None)
    ap.add_argument(
        "--cache", default=None,
        help="Optional fetched-HTML cache for watchlists (default: fetch live).",
    )
    ap.add_argument(
        "--today", default=None,
        help="YYYY-MM-DD cutoff for watchlist CFP closes (default: today's date).",
    )
    args = ap.parse_args()
    if args.today:
        import datetime

        try:
            datetime.date.fromisoformat(args.today)
        except ValueError:
            print(f"manual input: --today must be YYYY-MM-DD, got {args.today!r}", file=sys.stderr)
            return 1

    base = Path(".").resolve()
    input_dir = (base / args.input).resolve()
    data_dir = (base / args.out).resolve()

    if not input_dir.is_dir():
        print(f"input directory not found: {input_dir}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import upsert_counted, parse_start_date, summary_line, write_manifest

    try:
        files = manual_input_files(input_dir)
    except (ValueError, FileNotFoundError) as exc:
        print(f"manual input: {exc}", file=sys.stderr)
        return 1

    rows = []
    checked = []
    for md in files:
        text = md.read_text(encoding="utf-8")
        rows.extend(parse_rows(text))
        checked.extend(watchlist.parse_entries(text))

    # A watchlist is not a table: the list supplies only conference names and
    # sites, and their submission pages supply the details. If every site asks
    # to sign up rather than to present, that is reported but not treated as a
    # found CFP. A fetch failure stops the source with a clean message so an
    # incomplete manifest cannot orphan yesterday's notes during archiving.
    cache = (base / args.cache).resolve() if args.cache else None
    watch_found = 0
    failed = 0
    for entry in checked:
        result = watchlist.resolve(entry, cache=cache, today=args.today)
        if result.error:
            failed += int(result.failed)
            print(
                f"manual input: {entry['name']}: CFP unresolved ({result.error})",
                file=sys.stderr,
            )
            continue
        watch_found += 1
        print(f"manual input: {entry['name']} -> {result.cfp_url}")
        rows.append(
            {
                "name": result.name,
                "location": result.location,
                "cfp_close": result.cfp_close,
                "event_date": result.event_date,
                "topics": "",
                "event_url": result.event_url,
                "cfp_url": result.cfp_url,
            }
        )
    if failed:
        print(
            f"manual input: {failed} watchlist page(s) could not be fetched; "
            "aborting before writing notes so existing notes are not orphaned",
            file=sys.stderr,
        )
        return 1
    if checked:
        print(f"watchlist: {watch_found} CFP link(s) found, {len(checked) - watch_found} unresolved")

    counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    produced = []
    for r in rows:
        row = {
            "name": r["name"],
            "event_date": parse_start_date(r["event_date"]) or r["event_date"] or "—",
            "location": r["location"] or "—",
            "country": "",
            "cfp_close": r["cfp_close"] or "—",
            "topics": [t.strip() for t in (r["topics"] or "").split(",") if t.strip()],
            "event_url": r["event_url"],
            "cfp_url": r["cfp_url"],
            "source": "manual",
        }
        upsert_counted(data_dir, row, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    print(summary_line("manual input", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
