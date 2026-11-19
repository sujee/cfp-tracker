#!/usr/bin/env python3
"""Collect robotics deadlines from the automaticDai conference listing."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from http_cache import fetch_json
from listing_source import conference_start_date, iso_prefix, run_main, with_domain_topics

SOURCE = "realtime-embedded-conferences"
DATA_URL = "https://automaticdai.github.io/realtime-embedded-conferences/assets/data/conferences.json"
_LINK = re.compile(r"^\[([^]]+)]\((https?://[^)]+)\)\s*$")
_OFFICIAL_CFP = re.compile(r"\[(?:official\s+CFP|call\s+for\s+papers)]\((https?://[^)]+)\)", re.IGNORECASE)
_PHYSICAL_AI = re.compile(r"physical[ ._-]*ai|embodied[ ._-]*ai", re.IGNORECASE)


def _validate(data) -> bool:
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("realtime-embedded-conferences: expected a list of objects")
    return True


def _fetch(cache_path: Path | None, offline: bool):
    return fetch_json(
        DATA_URL,
        cache_path,
        "realtime-embedded-conferences.json",
        offline=offline,
        source=SOURCE,
        validator=_validate,
    )


def _linked_name(raw: str) -> tuple[str, str]:
    match = _LINK.match(str(raw or "").strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return str(raw or "").strip(), ""


def _cfp_url(record: dict, fallback: str) -> str:
    match = _OFFICIAL_CFP.search(str(record.get("remarks") or ""))
    return match.group(1) if match else fallback


def _is_current(record: dict, cutoff) -> bool:
    if record.get("category") != "Robotics & Learning":
        return False
    if record.get("status") != "upcoming" or record.get("deadline_precision") != "day":
        return False
    close = iso_prefix(record.get("deadline"))
    return bool(close and close >= cutoff.isoformat())


def to_row(record: dict) -> dict:
    name, event_url = _linked_name(record.get("name"))
    where = str(record.get("where") or "").strip()
    topics = ["robotics"]
    if _PHYSICAL_AI.search(f"{name} {record.get('remarks') or ''}"):
        topics.append("physical ai")
    topics = with_domain_topics(topics)
    return {
        "name": name,
        "event_date": conference_start_date(record.get("when")),
        "location": where if where and where != "(TBD)" else "—",
        "country": "",
        "cfp_close": iso_prefix(record.get("deadline")),
        "topics": topics,
        "event_url": event_url,
        "cfp_url": _cfp_url(record, event_url),
        "event_type": "workshop" if record.get("type") == "workshop" else "conference",
    }


def collect_rows(cutoff, today, cache_path=None, offline=False) -> list[dict]:
    import config as _cfg

    ignored = [term.lower() for term in getattr(_cfg, "IGNORE_TOPICS", [])]
    rows = []
    seen = set()
    for record in _fetch(cache_path, offline):
        if not _is_current(record, cutoff):
            continue
        row = to_row(record)
        if not row["name"] or any(term in row["name"].lower() for term in ignored):
            continue
        key = (row["name"].casefold(), row["cfp_close"], row["cfp_url"])
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
