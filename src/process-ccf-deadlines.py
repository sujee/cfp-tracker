#!/usr/bin/env python3
"""Collect typed robotics deadline rounds from the CCFDDL catalogue."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from http_cache import fetch_json
from listing_source import conference_start_date, iso_prefix, run_main, with_domain_topics

SOURCE = "ccf-deadlines"
DATA_URL = "https://ccfddl.com/conference/allconf.json"
_FIELDS = (
    ("abstract_deadline", "abstract"),
    ("deadline", "submission"),
    ("rebuttal_deadline", "rebuttal"),
    ("decision_deadline", "decision"),
)
_ROBOTICS_TITLES = {"icra", "iros", "rss", "corl", "ro-man", "hri", "humanoids"}
_ROBOTICS_TEXT = re.compile(r"\brobots?\b|robotics|robot learning|physical[ ._-]*ai|embodied|humanoid|mechatron", re.IGNORECASE)


def _validate(data) -> bool:
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("ccf-deadlines: expected a list of conference series")
    for series in data:
        if not isinstance(series.get("confs"), list):
            raise ValueError("ccf-deadlines: expected every series to have a confs list")
        for edition in series["confs"]:
            if not isinstance(edition.get("timeline"), list):
                raise ValueError("ccf-deadlines: expected every edition to have a timeline list")
    return True


def _fetch(cache_path: Path | None, offline: bool):
    return fetch_json(
        DATA_URL,
        cache_path,
        "ccf-deadlines-allconf.json",
        offline=offline,
        source=SOURCE,
        validator=_validate,
    )


def _is_robotics(series: dict) -> bool:
    if str(series.get("title") or "").casefold() in _ROBOTICS_TITLES:
        return True
    if str(series.get("sub") or "") != "AI":
        return False
    return bool(_ROBOTICS_TEXT.search(str(series.get("description") or "")))


def _rounds(edition: dict, cutoff) -> list[tuple[str, str, str, str]]:
    rounds = []
    for timeline_entry in edition.get("timeline", []):
        for field, stage in _FIELDS:
            value = timeline_entry.get(field)
            text = str(value or "").strip()
            close = iso_prefix(text)
            if not close or close < cutoff.isoformat():
                continue
            comment = str(timeline_entry.get("comment") or "").strip()
            timezone = str(edition.get("timezone") or "").strip()
            close_text = text if not timezone or text.endswith(timezone) else f"{text} {timezone}"
            rounds.append((stage, comment, close, close_text))
    return rounds


def _location(edition: dict) -> tuple[str, str]:
    place = str(edition.get("place") or "").strip()
    if place.casefold() == "virtual":
        return "Online", "Online"
    if not place or place.casefold().strip("()") in {"tbd", "unknown", "n/a"}:
        return "—", ""
    return place, ""


def collect_rows(cutoff, today, cache_path=None, offline=False) -> list[dict]:
    import config as _cfg

    ignored = [term.lower() for term in getattr(_cfg, "IGNORE_TOPICS", [])]
    rows = []
    seen = set()
    for series in _fetch(cache_path, offline):
        if not _is_robotics(series):
            continue
        title = str(series.get("title") or "").strip()
        for edition in series["confs"]:
            for stage, comment, close, close_text in _rounds(edition, cutoff):
                year = str(edition.get("year") or "").strip()
                name = f"{title} {year} ({stage}{': ' + comment if comment else ''})"
                if not title or not year or any(term in name.lower() for term in ignored):
                    continue
                url = str(edition.get("link") or "").strip()
                key = (name.casefold(), close, stage, url)
                if key in seen:
                    continue
                seen.add(key)
                topics = ["robotics"]
                if _ROBOTICS_TEXT.search(str(series.get("description") or "")):
                    topics.append("physical ai")
                topics = with_domain_topics(topics)
                location, country = _location(edition)
                rows.append({
                    "name": name,
                    "event_date": conference_start_date(edition.get("date")),
                    "location": location,
                    "country": country,
                    "cfp_close": close_text,
                    "topics": topics,
                    "event_url": url,
                    "cfp_url": url,
                    "event_type": "conference",
                })
    rows.sort(key=lambda row: (row["cfp_close"][:10], row["name"].casefold()))
    return rows


def main() -> int:
    return run_main(SOURCE, collect_rows)


if __name__ == "__main__":
    sys.exit(main())
