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
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

PAGE_URL = "https://adatosystems.com/cfp-tracker/"
CACHE_NAME = "adato-tracker.html"  # cached page under --cache DIR

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]
except Exception:
    _IGNORE = []


def _fetch_page(cache_path: Path | None = None) -> str:
    """The tracker page HTML, served from ``cache_path`` when already fetched."""
    dest = cache_path / CACHE_NAME if cache_path else None
    if dest is not None and dest.is_file():
        try:
            return dest.read_text(encoding="utf-8")
        except OSError:
            pass
    req = urllib.request.Request(PAGE_URL, headers={"User-Agent": "cfp-merge/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return text


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
        self._in_table = False
        self._in_row = False
        self._cells: list | None = None  # row in progress: list of [text chunks, href]
        self._cell: list | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if not self._in_table and "tablesorter" in (a.get("class") or "").split():
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
    return parser.rows


def collect_rows(cutoff: _dt.date, today: _dt.date, cache_path: Path | None = None) -> list[dict]:
    """One row per tracker-table entry whose CFP deadline is on/after *cutoff*.

    Deduplication key is ``(normalized name, cfp_close)`` — the same conference
    can legitimately reappear with a revised deadline.
    """
    rows: list[dict] = []
    seen = set()
    for cells in _parse_rows(_fetch_page(cache_path)):
        if len(cells) != 8:
            continue
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
    args = ap.parse_args()

    today = _dt.date.fromisoformat(args.today)
    cutoff = today - _dt.timedelta(days=30 * max(1, args.months_back))

    rows = collect_rows(cutoff, today, Path(args.cache))

    data_dir = Path(args.out).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import upsert_counted, summary_line, write_manifest

    counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    produced = []
    for r in rows:
        row = {**r, "source": "adato-tracker"}
        upsert_counted(data_dir, row, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    print(summary_line("adato-tracker", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
