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
import re
import sys
from pathlib import Path

API_URL = "https://cfp.ninja/api/v0/events"
PER_PAGE = 100
CFP_PAGE = "https://cfp.ninja/e"  # public submission page: /e/<slug>

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as _cfg
from http_cache import fetch_json

_IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]


def _validate_event_page(data) -> int:
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("cfp.ninja: expected an object with a data list")
    if not all(isinstance(event, dict) for event in data["data"]):
        raise ValueError("cfp.ninja: expected every event to be an object")
    pagination = data.get("pagination") or {}
    if not isinstance(pagination, dict):
        raise ValueError("cfp.ninja: expected pagination to be an object")
    try:
        total_pages = int(pagination.get("total_pages") or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("cfp.ninja: invalid pagination.total_pages") from exc
    if total_pages < 1:
        raise ValueError("cfp.ninja: pagination.total_pages must be positive")
    return total_pages


def _fetch_page(
    url: str,
    cache_path: Path | None = None,
    cache_key: str | None = None,
    offline: bool = False,
):
    """Fetch JSON through the shared online-first cache."""
    return fetch_json(
        url,
        cache_path,
        cache_key,
        offline=offline,
        source="cfp.ninja",
        validator=_validate_event_page,
    )


def fetch_events(cache_path: Path | None = None, offline: bool = False) -> list[dict]:
    """Every event across all pages of the public cfp.ninja API."""
    events: list[dict] = []
    page = 1
    while True:
        url = f"{API_URL}?per_page={PER_PAGE}&page={page}"
        data = _fetch_page(
            url, cache_path, f"cfp-ninja-events-{page}.json", offline=offline
        )
        total_pages = _validate_event_page(data)
        events.extend(data["data"])
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


def collect_rows(
    cutoff: _dt.date,
    today: _dt.date,
    cache_path: Path | None = None,
    offline: bool = False,
) -> list[dict]:
    """One row per cfp.ninja event whose CFP deadline is on/after *cutoff*.

    Deduplication key is ``(normalized name, cfp_close)`` — the same conference
    can legitimately reappear with a revised deadline.  ``cfp_status`` is ignored
    (it reports ``open`` for years-old rows); the date is the only filter.
    """
    rows: list[dict] = []
    seen = set()
    for event in fetch_events(cache_path, offline=offline):
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
    ap.add_argument("--superseded-manifest", default=None)
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Read only cached responses; do not access the network.",
    )
    args = ap.parse_args()

    today = _dt.date.fromisoformat(args.today)
    cutoff = today - _dt.timedelta(days=30 * max(1, args.months_back))

    rows = [
        {**row, "source": "cfp.ninja"}
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

    print(summary_line("cfp.ninja", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
