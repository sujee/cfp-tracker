#!/usr/bin/env python3
"""Collect robotics speaking CFPs from the structured AgentConfs event listing."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from country import normalize_country
from http_cache import fetch_json
from listing_source import iso_prefix, run_main, with_domain_topics

SOURCE = "agentconfs"
EVENTS_URL = "https://agentconfs.com/data/events.json"
_ACADEMIC_PROVENANCE = re.compile(r"ccf-deadlines|ai-deadlines|openreview|arxiv", re.IGNORECASE)
_ROBOTICS = re.compile(r"\brobots?\b|robotics|physical[ ._-]*ai|embodied|humanoid|mechatron", re.IGNORECASE)


def _validate(data) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError("agentconfs: expected an object with an events list")
    if not all(isinstance(event, dict) for event in data["events"]):
        raise ValueError("agentconfs: expected every event to be an object")
    return True


def _fetch(cache_path: Path | None, offline: bool):
    return fetch_json(
        EVENTS_URL,
        cache_path,
        "agentconfs-events.json",
        offline=offline,
        source=SOURCE,
        validator=_validate,
    )


def is_robotics_event(event: dict) -> bool:
    """Select physical-robot events without treating Robot Framework as robotics."""
    name = str(event.get("name") or "")
    full_name = str(event.get("full_name") or "")
    if "robocon" in name.casefold() or "robot framework" in full_name.casefold():
        return False
    tags = event.get("topic_tags")
    text = " ".join([
        name,
        full_name,
        " ".join(str(tag) for tag in tags) if isinstance(tags, list) else "",
    ])
    return bool(_ROBOTICS.search(text))


def is_current_speaking_cfp(event: dict, cutoff) -> bool:
    """Require an unexpired close and exclude research-paper submission calls."""
    if not is_robotics_event(event):
        return False
    if str(event.get("type") or "").strip().casefold() == "academic conference":
        return False
    sources = event.get("sources")
    provenance = str(sources.get("cfp") or "") if isinstance(sources, dict) else ""
    if _ACADEMIC_PROVENANCE.search(provenance):
        return False
    close = iso_prefix(event.get("cfp_close"))
    return bool(
        str(event.get("name") or "").strip()
        and close
        and close >= cutoff.isoformat()
        and str(event.get("cfp_url") or "").strip()
    )


def _location(event: dict) -> tuple[str, str]:
    if str(event.get("format") or "").casefold() == "online":
        return "Online", "Online"
    city = str(event.get("city") or "").strip()
    country = normalize_country(event.get("country"))
    location = ", ".join(part for part in (city, country) if part) or "—"
    return location, country


def to_row(event: dict) -> dict:
    location, country = _location(event)
    tags = event.get("topic_tags")
    topics = with_domain_topics([str(tag) for tag in tags] if isinstance(tags, list) else [])
    event_kind = str(event.get("type") or "conference").strip().casefold()
    if event_kind not in {"conference", "meetup", "summit", "workshop", "hackathon", "webinar", "other"}:
        event_kind = "conference"
    return {
        "name": str(event.get("name") or "").strip(),
        "event_date": iso_prefix(event.get("start_date")) or "TBA",
        "location": location,
        "country": country,
        "cfp_close": iso_prefix(event.get("cfp_close")),
        "topics": topics,
        "event_url": str(event.get("official_url") or "").strip(),
        "cfp_url": str(event.get("cfp_url") or "").strip(),
        "event_type": event_kind,
    }


def collect_rows(cutoff, today, cache_path=None, offline=False) -> list[dict]:
    import config as _cfg

    ignored = [term.lower() for term in getattr(_cfg, "IGNORE_TOPICS", [])]
    rows = []
    seen = set()
    for event in _fetch(cache_path, offline)["events"]:
        if not is_current_speaking_cfp(event, cutoff):
            continue
        row = to_row(event)
        if any(term in row["name"].lower() for term in ignored):
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
