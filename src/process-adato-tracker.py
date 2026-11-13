#!/usr/bin/env python3
"""Parse CFPs from the Adato Systems CFP Tracker — https://adatosystems.com/cfp-tracker/

Leon Adato's WordPress site keeps the list on the evergreen ``/cfp-tracker/``
page: one ``<table class="tablesorter">`` with the columns

    Event Name | City | State | Event Start | Event End | CFP Close | Event URL | CFP URL

Dates are clean ``YYYY-MM-DD`` strings; the last two columns are plain
``<a href>`` links (the link text is just "Link"). The dated "Call For
Papers Listings for …" posts (category "CFP Listings") only announce each
refresh — their pages are stubs, and the site's RSS feeds carry just the
excerpt, so the tracker page is the only place the table exists.

Speakers' benefits are not stated anywhere on the page, so ``benefits`` and
``languages`` are never written for this source. ``topics`` is empty.

Usage:

    python3 src/process-adato-tracker.py --out data
    python3 src/process-adato-tracker.py --out /tmp/scratch --today 2026-11-01
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from http_cache import fetch_text

PAGE_URL = "https://adatosystems.com/cfp-tracker/"
CACHE_NAME = "adato-tracker.html"  # cached page under --cache DIR

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as _cfg

_IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]


def _fetch_page(cache_path: Path | None = None, offline: bool = False) -> str:
    """Fetch tracker HTML through the shared online-first cache."""
    return fetch_text(
        PAGE_URL,
        cache_path,
        CACHE_NAME,
        offline=offline,
        source="adato-tracker",
        validator=_validate_page,
    )


def _parse_date(s) -> _dt.date | None:
    """The page's dates are clean ISO; anything else is unreadable here."""
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(str(s).strip())
    except ValueError:
        return None


class _TrackerTableParser(HTMLParser):
    """Pull ``(text, href)`` cells out of the ``tablesorter`` table only.

    ``convert_charrefs`` decodes the entities the page uses in names
    (``&#8217;`` etc.) and in href attributes (``&amp;``).
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str | None]]] = []
        self.found_table = False
        self._in_table = False
        self._in_row = False
        self._cells: list | None = None  # row in progress: list of [text chunks, href]
        self._cell: list | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if not self._in_table and "tablesorter" in (a.get("class") or "").split():
                self.found_table = True
                self._in_table = True
            return
        if not self._in_table:
            return
        if tag == "tr":
            self._in_row = True
            self._cells = []
        elif tag == "td" and self._in_row:
            self._cell = [[], None]
        elif tag == "a" and self._cell is not None and not self._cell[1]:
            self._cell[1] = (str(a.get("href") or "")).strip()

    def handle_data(self, data):
        if self._cell is not None:
            self._cell[0].append(data)

    def handle_endtag(self, tag):
        if tag == "table" and self._in_table:
            self._in_table = False
        elif not self._in_table:
            return
        elif tag == "td" and self._cell is not None:
            self._cells.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._cells:
                self.rows.append(
                    [(" ".join(chunks).strip(), href) for chunks, href in self._cells]
                )
            self._cells = None


def _parse_rows(html: str) -> list[list[tuple[str, str | None]]]:
    parser = _TrackerTableParser()
    parser.feed(html)
    parser.close()
    if not parser.found_table:
        raise ValueError("Adato tracker: expected a table with class 'tablesorter'")
    return parser.rows


def _validate_rows(rows) -> bool:
    for cells in rows:
        if cells and len(cells) != 8:
            raise ValueError(
                f"Adato tracker: expected 8 columns in a nonempty row, found {len(cells)}"
            )
    return True


def _validate_page(html: str) -> bool:
    return _validate_rows(_parse_rows(html))


def collect_rows(
    cutoff: _dt.date,
    today: _dt.date,
    cache_path: Path | None = None,
    offline: bool = False,
) -> list[dict]:
    """One row per tracker-table entry whose CFP deadline is on/after *cutoff*.

    Deduplication key is ``(normalized name, cfp_close)`` — the same conference
    can legitimately reappear with a revised deadline.
    """
    rows: list[dict] = []
    seen = set()
    table_rows = _parse_rows(_fetch_page(cache_path, offline=offline))
    _validate_rows(table_rows)
    for cells in table_rows:
        name, city, state = (cells[i][0] for i in (0, 1, 2))
        start = _parse_date(cells[3][0])
        close = _parse_date(cells[5][0])
        event_url = cells[6][1] or ""
        cfp_url = cells[7][1] or ""
        if not name or not cfp_url or close is None or close < cutoff:
            continue
        if any(t in name.lower() for t in _IGNORE):
            continue
        key = (re.sub(r"[^a-z0-9]", "", name.lower()), close.isoformat())
        if key in seen:
            continue
        seen.add(key)
        if city.upper() == "VIRTUAL":
            location, country = "Online", "Online"
        else:
            country = ""
            location = ", ".join(p for p in (city, state) if p) or "—"
        rows.append(
            {
                "name": name,
                "event_date": start.isoformat() if start else "TBA",
                "location": location,
                "country": country,
                "cfp_close": close.isoformat(),
                "event_url": event_url,
                "cfp_url": cfp_url,
                "topics": [],
            }
        )

    rows.sort(key=lambda r: (r["cfp_close"], r["name"].lower()))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse CFPs from the Adato Systems CFP Tracker page.")
    ap.add_argument("--out", default="data")
    ap.add_argument("--today", default=_dt.date.today().isoformat())
    ap.add_argument("--months-back", type=int, default=1)
    ap.add_argument(
        "--cache",
        default=str(Path(__file__).resolve().parent.parent / "cache"),
    )
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--superseded-manifest", default=None)
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Read only the cached response; do not access the network.",
    )
    args = ap.parse_args()

    today = _dt.date.fromisoformat(args.today)
    cutoff = today - _dt.timedelta(days=30 * max(1, args.months_back))

    rows = [
        {**row, "source": "adato-tracker"}
        for row in collect_rows(cutoff, today, Path(args.cache), offline=args.offline)
    ]

    data_dir = Path(args.out).resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import emit_rows, summary_line

    counts = emit_rows(
        data_dir,
        rows,
        manifest=Path(args.manifest) if args.manifest else None,
        superseded_manifest=Path(args.superseded_manifest) if args.superseded_manifest else None,
        today=args.today,
    )

    print(summary_line("adato-tracker", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
