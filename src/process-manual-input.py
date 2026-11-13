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
import datetime
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import cfp_writer
from cfp_writer import parse_start_date
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
            return datetime.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    # No exact date: drop "Unstated" qualifiers, e.g. "Dec 2026 / Unstated" -> "Dec 2026".
    parts = [p.strip() for p in raw.split("/") if p.strip() and "unstated" not in p.lower()]
    if not parts:
        return "Unstated"
    text = " / ".join(parts)
    for fmt in _CLOSE_FORMATS:
        try:
            return datetime.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def _table_cells(line: str) -> list[str] | None:
    """Split one pipe-table line, or return ``None`` for ordinary Markdown."""
    if not line.strip().startswith("|"):
        return None
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _header_label(raw: str) -> str:
    """Normalize a header cell for exact, punctuation-insensitive matching."""
    label = _EMPH_RE.sub("", raw).lower()
    return " ".join(re.split(r"[^a-z0-9]+", label)).strip()


def _cfp_columns(header: list[str]) -> dict[str, int] | None:
    """Map a real manual CFP header to its columns, in any column order."""
    aliases = {
        "name": {"conf name", "conference name", "event name"},
        "location": {"conf location", "conference location", "event location", "location"},
        "open": {"cfp open", "cfp opens", "cfp opening"},
        "close": {"cfp close", "cfp closes", "cfp closing", "cfp deadline"},
        "event_date": {
            "conference date", "conference dates", "event date", "event dates",
        },
        "topics": {
            "conference topic", "conference topics", "event topic", "event topics",
            "topic", "topics",
        },
    }
    labels = [_header_label(cell) for cell in header]
    columns = {}
    for field, choices in aliases.items():
        matches = [index for index, label in enumerate(labels) if label in choices]
        if len(matches) > 1:
            return None
        if matches:
            columns[field] = matches[0]
    required = {"name", "location", "open", "close", "event_date"}
    return columns if required.issubset(columns) else None


def _is_separator_row(cells: list[str], width: int) -> bool:
    """Recognize the delimiter that must follow a manual CFP table header."""
    return len(cells) == width and all(
        re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells
    )


def _cell(cells: list[str], columns: dict[str, int], field: str) -> str:
    index = columns.get(field)
    return cells[index] if index is not None and index < len(cells) else ""


def parse_rows(text: str) -> list[dict]:
    """Read rows only from Markdown tables with the manual CFP header.

    Requiring the five known fields and their delimiter prevents other wide
    tables (including prestige and rubric tables) from becoming CFP notes.
    """
    rows = []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        header = _table_cells(lines[index])
        if header is None:
            index += 1
            continue
        block = []
        while index < len(lines):
            cells = _table_cells(lines[index])
            if cells is None:
                break
            block.append(cells)
            index += 1

        columns = _cfp_columns(block[0])
        if (
            columns is None
            or len(block) < 2
            or not _is_separator_row(block[1], len(block[0]))
        ):
            continue
        required_fields = ("name", "location", "open", "close", "event_date")
        required_width = max(columns[field] for field in required_fields)
        for cells in block[2:]:
            if (
                len(cells) <= required_width
                or _cfp_columns(cells) is not None
                or _is_separator_row(cells, len(cells))
            ):
                continue
            name, url = _clean_name(_cell(cells, columns, "name"))
            if not name or "would you like" in name.lower():
                continue
            if any(t in name.lower() for t in _IGNORE):
                continue
            rows.append(
                {
                    "name": name,
                    "location": _cell(cells, columns, "location"),
                    "cfp_close": _normalize_close(_cell(cells, columns, "close")),
                    "event_date": _cell(cells, columns, "event_date"),
                    "topics": _cell(cells, columns, "topics"),
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


def _normalize_event_date(raw: str) -> str:
    """Return a valid ISO start date, or ``TBA`` for unknown source text."""
    parsed = parse_start_date(raw)
    if not parsed:
        return "TBA"
    try:
        datetime.date.fromisoformat(parsed)
    except ValueError:
        return "TBA"
    return parsed


# ``_legacy_event_year`` is an in-memory path hint. It never reaches frontmatter.
# ``cfp_writer.note_path`` uses it to keep year-derived legacy manual paths.


def _normalize_row(row: dict) -> dict:
    """Convert a table or watchlist result to the common writer row shape."""
    raw_event_date = str(row.get("event_date") or "").strip()
    event_date = _normalize_event_date(raw_event_date)
    normalized = {
        "name": row.get("name", ""),
        "event_date": event_date,
        "location": row.get("location") or "—",
        "country": "",
        "cfp_close": row.get("cfp_close") or "—",
        "topics": [t.strip() for t in (row.get("topics") or "").split(",") if t.strip()],
        "event_url": row.get("event_url", ""),
        "cfp_url": row.get("cfp_url", ""),
        "source": "manual",
    }
    legacy_year = re.search(r"20\d{2}", raw_event_date) if event_date == "TBA" else None
    if legacy_year:
        normalized["_legacy_event_year"] = legacy_year.group(0)
    return normalized


def collect_rows(
    input_dir: Path,
    cache: Path | None = None,
    today=None,
    offline: bool = False,
) -> list[dict]:
    """Collect fully normalized manual rows without writing any CFP notes.

    Configuration, source-read, and fatal watchlist-fetch failures raise an
    exception. No note writer runs, so a failed collection cannot produce a
    partial manifest or cause existing notes to be archived.
    """
    input_dir = Path(input_dir)
    cache = Path(cache) if cache is not None else None
    if today is not None and not isinstance(today, datetime.date):
        try:
            datetime.date.fromisoformat(str(today))
        except ValueError as exc:
            raise ValueError(f"today must be YYYY-MM-DD, got {today!r}") from exc
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    rows = []
    checked = []
    for md in manual_input_files(input_dir):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"could not read manual input file {md}: {exc}") from exc
        rows.extend(parse_rows(text))
        checked.extend(watchlist.parse_entries(text))

    # Resolve every checklist before returning any rows. A failed page is
    # different from a page with no CFP: the former aborts note generation.
    watch_found = 0
    failures = []
    for entry in checked:
        result = watchlist.resolve(entry, cache=cache, today=today, offline=offline)
        if result.error:
            message = f"{entry['name']}: CFP unresolved ({result.error})"
            if result.failed:
                failures.append(message)
            else:
                print(f"manual input: {message}", file=sys.stderr)
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
    if failures:
        details = "; ".join(failures)
        raise RuntimeError(
            f"{len(failures)} watchlist page(s) could not be fetched; "
            "aborting before writing notes so existing notes are not orphaned: "
            f"{details}"
        )
    if checked:
        print(f"watchlist: {watch_found} CFP link(s) found, {len(checked) - watch_found} unresolved")

    return [_normalize_row(row) for row in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--input", default="input")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--superseded-manifest", default=None)
    ap.add_argument(
        "--cache", default=None,
        help="Optional fetched-HTML cache for watchlists (default: fetch live).",
    )
    ap.add_argument(
        "--today", default=None,
        help="YYYY-MM-DD cutoff for watchlist CFP closes (default: today's date).",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Read only cached watchlist pages; do not access the network.",
    )
    args = ap.parse_args()
    if args.today:
        try:
            datetime.date.fromisoformat(args.today)
        except ValueError:
            print(f"manual input: --today must be YYYY-MM-DD, got {args.today!r}", file=sys.stderr)
            return 1

    base = Path(".").resolve()
    input_dir = (base / args.input).resolve()
    data_dir = (base / args.out).resolve()
    cache = (base / args.cache).resolve() if args.cache else None

    try:
        rows = collect_rows(input_dir, cache=cache, today=args.today, offline=args.offline)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"manual input: {exc}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import emit_rows, summary_line

    counts = emit_rows(
        data_dir,
        rows,
        manifest=Path(args.manifest) if args.manifest else None,
        superseded_manifest=Path(args.superseded_manifest) if args.superseded_manifest else None,
        today=args.today,
    )

    print(summary_line("manual input", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
