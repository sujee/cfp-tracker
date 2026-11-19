#!/usr/bin/env python3
"""Collect paper-submission deadlines from the official IEEE RAS iCalendar feed."""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

from http_cache import fetch_text
from listing_source import run_main, with_domain_topics

SOURCE = "ieee-ras"
CALENDAR_URL = "https://www.ieee-ras.org/events/category/important-dates/deadlines/list/?ical=1"
_SUBMISSION = re.compile(r"^(?:Deadlines|Call for Papers)\s*-\s*Paper submission deadline:\s*", re.IGNORECASE)


def _validate(text: str) -> bool:
    if "BEGIN:VCALENDAR" not in text or "BEGIN:VEVENT" not in text:
        raise ValueError("ieee-ras: expected a nonempty iCalendar feed")
    return True


def _fetch(cache_path: Path | None, offline: bool) -> str:
    return fetch_text(
        CALENDAR_URL,
        cache_path,
        "ieee-ras-deadlines.ics",
        offline=offline,
        source=SOURCE,
        validator=_validate,
    )


def _unfold(text: str) -> list[str]:
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _unescape(value: str) -> str:
    return value.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").replace("\\\\", "\\")


def parse_events(text: str) -> list[dict]:
    """Parse VEVENT mappings from normalized, unfolded iCalendar input."""
    events = []
    current = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        property_text, value = line.split(":", 1)
        key = _unescape(property_text.split(";", 1)[0].upper())
        current[key] = _unescape(value)
    return events


def _event_name(summary: str) -> str:
    return _SUBMISSION.sub("", summary).strip()


def to_row(event: dict, close: str) -> dict:
    url = str(event.get("URL") or "").strip()
    return {
        "name": _event_name(str(event.get("SUMMARY") or "")),
        "event_date": "TBA",
        "location": "—",
        "country": "",
        "cfp_close": close,
        "topics": with_domain_topics(["robotics"]),
        "event_url": url,
        "cfp_url": url,
    }


def collect_rows(cutoff, today, cache_path=None, offline=False) -> list[dict]:
    import config as _cfg

    ignored = [term.lower() for term in getattr(_cfg, "IGNORE_TOPICS", [])]
    rows = []
    seen = set()
    for event in parse_events(_fetch(cache_path, offline)):
        if "deadlines" not in str(event.get("CATEGORIES") or "").casefold():
            continue
        if not _SUBMISSION.search(str(event.get("SUMMARY") or "")):
            continue
        try:
            close = datetime.datetime.strptime(event.get("DTSTART", ""), "%Y%m%d").date().isoformat()
        except ValueError:
            continue
        if close < cutoff.isoformat():
            continue
        row = to_row(event, close)
        if not row["name"] or not row["cfp_url"] or any(term in row["name"].lower() for term in ignored):
            continue
        key = (row["name"].casefold(), close, row["cfp_url"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    rows.sort(key=lambda row: (row["cfp_close"], row["name"].casefold()))
    return rows


def main() -> int:
    return run_main(SOURCE, collect_rows)


if __name__ == "__main__":
    sys.exit(main())
