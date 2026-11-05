#!/usr/bin/env python3
"""Parse CFPs from cfp.ninja — an open-source CFP platform (github.com/sreday/cfp.ninja).

Public API, no auth::

    https://cfp.ninja/api/v0/events?per_page=100&page=N

Each record carries the CFP window (``cfp_open_at`` / ``cfp_close_at``), the
conference dates, location/country, tags and speaker benefits
(``travel_covered`` / ``hotel_covered`` / ``honorarium_provided``).  The public
submission page is ``https://cfp.ninja/e/<slug>`` (the SPA route is ``/e/:slug``).

The API marks past deadlines ``"open"`` the same way developers.events does, so
filter on ``cfp_close_at`` — never on ``cfp_status``.

Usage::

    python3 src/process-cfp-ninja.py --out data
    python3 src/process-cfp-ninja.py --out /tmp/scratch --today 2026-11-01
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import urllib.request
from pathlib import Path

API_URL = "https://cfp.ninja/api/v0/events"
PER_PAGE = 100
CFP_PAGE = "https://cfp.ninja/e"  # public submission page: /e/<slug>

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]
except Exception:
    _IGNORE = []


def _fetch_page(url: str, cache_path: Path | None = None, cache_key: str | None = None):
    """Fetch one JSON page, preferring the cache at ``cache_path/cache_key``."""
    dest = cache_path / cache_key if (cache_path and cache_key) else None
    if dest is not None and dest.is_file():
        try:
            return json.loads(dest.read_text(encoding="utf-8"))
        except Exception:
            pass
    req = urllib.request.Request(
        url, headers={"User-Agent": "cfp-merge/1.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data), encoding="utf-8")
    return data


def fetch_events(cache_path: Path | None = None) -> list[dict]:
    """Every event across all pages of the public cfp.ninja API."""
    events: list[dict] = []
    page = 1
    while True:
        url = f"{API_URL}?per_page={PER_PAGE}&page={page}"
        data = _fetch_page(url, cache_path, f"cfp-ninja-events-{page}.json")
        events.extend(data.get("data") or [])
        pagination = data.get("pagination") or {}
        total_pages = int(pagination.get("total_pages") or 1)
        if page >= total_pages:
            break
        page += 1
    return events


def _parse_date(s) -> _dt.date | None:
    """Parse an ISO date(-time) string; return ``None`` on anything unreadable."""
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def benefits_of(event: dict) -> list[str]:
    """Speaker benefits stated by the organizer, as short tokens (``[]`` if none)."""
    out = []
    if event.get("travel_covered"):
        out.append("travel")
    if event.get("hotel_covered"):
        out.append("hotel")
    if event.get("honorarium_provided"):
        out.append("honorarium")
    return out


def collect_rows(cutoff: _dt.date, today: _dt.date, cache_path: Path | None = None) -> list[dict]:
    """One row per cfp.ninja event whose CFP deadline is on/after *cutoff*.

    Deduplication key is ``(normalized name, cfp_close)`` — the same conference
    can legitimately reappear with a revised deadline.  ``cfp_status`` is ignored
    (it reports ``open`` for years-old rows); the date is the only filter.
    """
    rows: list[dict] = []
    seen = set()
    for event in fetch_events(cache_path):
        close = _parse_date(event.get("cfp_close_at"))
        if close is None or close < cutoff:
            continue
        name = (event.get("name") or "").strip()
        if not name:
            continue
        if any(t in name.lower() for t in _IGNORE):
            continue
        tags = [t.strip() for t in (event.get("tags") or "").split(",") if t.strip()]
        if any(any(ig in t.lower() for ig in _IGNORE) for t in tags):
            continue
        key = (re.sub(r"[^a-z0-9]", "", name.lower()), close)
        if key in seen:
            continue
        seen.add(key)

        start = _parse_date(event.get("start_date"))
        online = bool(event.get("is_online"))
        country = (event.get("country") or "").strip()
        if not country and online:
            country = "Online"
        loc = (event.get("location") or "").strip() or country or "—"
        slug = event.get("slug") or ""

        rows.append(
            {
                "name": name,
                "event_date": start.isoformat() if start else "TBA",
                "location": loc,
                "country": country,
                "cfp_close": close.isoformat(),
                "topics": tags,
                "event_url": event.get("website") or "",
                "cfp_url": f"{CFP_PAGE}/{slug}" if slug else "",
                "benefits": benefits_of(event),
            }
        )

    rows.sort(key=lambda r: (r["cfp_close"], r["name"].lower()))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse CFPs from cfp.ninja.")
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
        row = {**r, "source": "cfp.ninja"}
        upsert_counted(data_dir, row, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    print(summary_line("cfp.ninja", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
