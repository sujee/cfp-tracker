#!/usr/bin/env python3
"""Write per-CFP notes for open and recently closed developers.events CFPs.

Fetches two public static datasets on every run:

* ``https://developers.events/all-cfps.json``
* ``https://developers.events/all-events.json``

Stale ``developers.events`` HTML is never scraped — the JSON is the source of
truth (the page bundle is a build-time snapshot with older ``until`` strings).
Filtering uses ``untilDate`` (epoch ms), not the free-form ``until`` string.

Typical usage::

    python3 src/process-all.py                                        # everything → data/
    python3 src/process-developer-events.py --out data --past-days 30
    python3 src/process-developer-events.py --out /tmp/scratch --today 2026-11-01 --months-back 1

Writes one markdown note per CFP into the ``--out`` **directory** (default
``data/``), reading live ``developers.events`` JSON.

Legacy ``--months-back`` is kept as a 30×N days alias.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as _cfg
from http_cache import fetch_json as _fetch_cached_json

_IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SRC_URLS: Dict[str, str] = {
    "all-cfps.json": "https://developers.events/all-cfps.json",
    "all-events.json": "https://developers.events/all-events.json",
}

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def normalize_name(name: str | None) -> str:
    """Lower-case alphanumeric fold — stable for CFP↔event matching."""
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def epoch_ms_to_date(epoch_ms: int) -> datetime.date:
    """Convert ``untilDate``/``date[]`` epoch-milliseconds to UTC date.

    Uses ``datetime.timezone.utc`` for Python 3.9+ compat (``datetime.UTC``
    only exists since 3.11).
    """
    return datetime.datetime.fromtimestamp(epoch_ms / 1000, datetime.timezone.utc).date()


def extract_country_from_location(location: str | None) -> str:
    """Trailing ``(Country)`` from ``"City (Country)"``, or ``""``.

    The location string is the reliable source; ``conf.country`` / ``country``
    in ``all-events.json`` is occasionally wrong (e.g. DevFest Faro labelled
    ``Lebanon``).
    """
    match = re.search(r"\(([^)]+)\)\s*$", location or "")
    return match.group(1).strip() if match else ""


def event_date_start(dates_ms: List[int]) -> str:
    """Starting conference date only, clean ISO ``YYYY-MM-DD`` (or ``TBA``)."""
    if not dates_ms:
        return "TBA"
    return min(epoch_ms_to_date(ms) for ms in dates_ms).strftime("%Y-%m-%d")


def compute_cutoff(
    today: datetime.date,
    months_back: int = 1,
    days_back: Optional[int] = None,
) -> datetime.date:
    """Cutoff date for “recently closed”.

    Rolling-window mode (default): ``days_back=30`` → 30 days before *today*.
    When *days_back* is set (via ``--past-days``/``--days-back``) it wins.

    ``months_back`` is kept for backwards compatibility and is interpreted as
    ``30 × N`` days, so ``--months-back 1`` ≈ past 30 days (≈ no breakage vs
    the older calendar-month logic that snapped to the 1st).
    """
    if days_back is not None:
        return today - datetime.timedelta(days=days_back)
    # Back-compat: months → rolling days (requested behaviour is “past 30 days”)
    return today - datetime.timedelta(days=30 * max(1, months_back))


# ---------------------------------------------------------------------------
# I/O — fetch & cache
# ---------------------------------------------------------------------------


def _validate_feed(data: Any) -> bool:
    if not isinstance(data, list):
        raise ValueError("developers.events: expected a JSON list")
    return True


def fetch_json(
    cache_dir: str | os.PathLike[str], filename: str, url: str, offline: bool = False
) -> Any:
    """Fetch JSON through the shared online-first cache."""
    return _fetch_cached_json(
        url,
        Path(cache_dir),
        filename,
        offline=offline,
        source="developers.events",
        validator=_validate_feed,
    )


# ---------------------------------------------------------------------------
# Merge CFP ↔ Event
# ---------------------------------------------------------------------------

# A row is intentionally a plain dict rather than a dataclass so callers can
# add the note-level fields before handing it to cfp_writer.
Row = Dict[str, Any]


def build_event_index(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Index events by normalised ``name``; bare names repeat across editions."""
    index: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for event in events:
        index[normalize_name(event.get("name"))].append(event)
    return index


def select_best_event(
    candidates: List[Dict[str, Any]],
    target_location: str,
    close_date: datetime.date,
) -> Dict[str, Any]:
    """Pick the event edition that best matches the CFP entry.

    Ranking is (1) exact location match, (2) nearest edition on/after the
    deadline, (3) otherwise the most recent prior edition.  This avoids
    attaching a 2023 ``DevFest`` edition to a 2026 CFP.
    """

    def distance(event: Dict[str, Any]) -> Tuple[int, int, int]:
        loc = (event.get("location") or "").strip().lower()
        loc_penalty = 0 if loc == target_location else 1

        dates_ms: List[int] = event.get("date") or []
        if not dates_ms:
            return (loc_penalty, 2, 10**6)

        event_dates = [epoch_ms_to_date(ms) for ms in dates_ms]
        upcoming = [d for d in event_dates if d >= close_date]
        if upcoming:
            return (loc_penalty, 0, min((d - close_date).days for d in upcoming))
        return (loc_penalty, 1, (close_date - max(event_dates)).days)

    return sorted(candidates, key=distance)[0]


def build_rows(
    cfps: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    cutoff: datetime.date,
) -> List[Row]:
    """One enriched row per ``(conference, deadline)`` with ``close >= cutoff``.

    Deduplication key is ``(normalized name, close_date)`` — some exports
    duplicate the same deadline entry verbatim.  Enrichment pulls conference
    dates, location, country, topics, languages and URLs from the closest event
    edition via :func:`select_best_event`.
    """
    event_index = build_event_index(events)
    rows: List[Row] = []
    seen: Set[Tuple[str, datetime.date]] = set()

    for entry in cfps:
        # The feed marks every historical row "open" — date is the only filter.
        until_ms = entry.get("untilDate")
        if until_ms is None:
            continue
        close_date = epoch_ms_to_date(int(until_ms))
        if close_date < cutoff:
            continue

        conf = entry.get("conf") or {}
        if any(t in (conf.get("name") or "").lower() for t in _IGNORE):
            continue
        dedup_key = (normalize_name(conf.get("name")), close_date)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        loc = conf.get("location") or ""
        candidates = event_index.get(normalize_name(conf.get("name")), [])
        event: Dict[str, Any] = {}
        if candidates:
            event = select_best_event(candidates, loc.strip().lower(), close_date)
            loc = loc or event.get("location") or ""

        tags = event.get("tags") or []
        # De-duplicate topics while preserving order (some events repeat tags).
        topics = list(
            dict.fromkeys(
                t["value"] for t in tags if t.get("key") in ("tech", "topic") and t.get("value")
            )
        )
        if any(any(ig in (tp or "").lower() for ig in _IGNORE) for tp in topics):
            continue
        languages = [t["value"] for t in tags if t.get("key") == "language" and t.get("value")]
        country = extract_country_from_location(loc) or event.get("country") or ""

        rows.append(
            {
                "name": conf.get("name") or "",
                "close": close_date,
                "dates": event.get("date") or conf.get("date") or [],
                "loc": loc,
                "country": country,
                "topics": topics,
                "languages": languages,
                "event_url": event.get("hyperlink") or conf.get("hyperlink") or "",
                "cfp_url": entry.get("link") or "",
            }
        )

    rows.sort(key=lambda r: (r["close"], r["name"].lower()))
    return rows


def collect_rows(
    cutoff: datetime.date,
    cache_path: Path,
    offline: bool = False,
) -> list[dict]:
    """Collect normalized note rows without writing any CFP notes."""
    cfps = fetch_json(cache_path, "all-cfps.json", SRC_URLS["all-cfps.json"], offline)
    events = fetch_json(cache_path, "all-events.json", SRC_URLS["all-events.json"], offline)
    rows = []
    for raw in build_rows(cfps, events, cutoff):
        rows.append(
            {
                "name": raw["name"],
                "event_date": event_date_start(raw["dates"]),
                "location": raw["loc"],
                "country": raw["country"],
                "cfp_close": raw["close"].isoformat(),
                "topics": raw["topics"],
                "languages": raw["languages"],
                "event_url": raw["event_url"],
                "cfp_url": raw["cfp_url"],
                "source": "developers.events",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write per-CFP Obsidian notes from developers.events.",
    )
    parser.add_argument(
        "--out",
        default="data",
        help="Output directory for per-CFP markdown files (default: data).",
    )
    parser.add_argument(
        "--today",
        default=datetime.date.today().isoformat(),
        help="Override 'today' as YYYY-MM-DD (repro mode). Default: real today.",
    )
    parser.add_argument(
        "--months-back",
        type=int,
        default=1,
        help="Approximate window as 30×N days. Prefer --past-days N. (default: 1).",
    )
    parser.add_argument(
        "--past-days",
        "--days-back",
        type=int,
        default=None,
        dest="past_days",
        help="Rolling window for 'recently closed' (default: 30 days). Overrides --months-back.",
    )
    parser.add_argument(
        "--cache",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache"),
        help="Cache directory for the two JSON feeds (default: cfps/cache).",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Write the JSON list of note paths produced (relative to --out), for orphan detection.",
    )
    parser.add_argument(
        "--superseded-manifest",
        default=None,
        help="Write replaced note paths for collision-safe archive handling.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Read only cached responses; do not access the network.",
    )
    # Retired report options remain accepted through the shim's removal window.
    parser.add_argument("--focus-tags", help=argparse.SUPPRESS)
    for legacy in ("--no-focus", "--no-frontmatter", "--no-backup"):
        parser.add_argument(legacy, action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    today = datetime.date.fromisoformat(args.today)
    cutoff = compute_cutoff(today, args.months_back, args.past_days)

    rows = collect_rows(cutoff, Path(args.cache), offline=args.offline)

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
    print(summary_line(
        "developers.events", len(rows), counts["new"], counts["updated"],
        counts["unchanged"] + counts["skipped"],
    ))



if __name__ == "__main__":
    main()
