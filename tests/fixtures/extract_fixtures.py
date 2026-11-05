#!/usr/bin/env python3
"""Rebuild the committed test fixtures from the real downloaded source data.

The fixtures under ``tests/fixtures/`` are small, real slices of what the
pipeline fetches, so tests exercise the shapes the sources actually publish
(epoch-ms dates, event tags, ``cfpEndDate`` strings, ...) instead of invented data.

Source cache lives in ``cfps/cache/`` (gitignored), so this script is a
maintenance tool run by hand when you want to refresh the samples:

    python3 tests/fixtures/extract_fixtures.py

It reads the cache, keeps the records named below verbatim, and rewrites the
``*.sample.json`` fixtures. Committed fixtures are the source of truth for the
tests — this script just documents/reproduces how they were chosen.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "cache"
OUT = ROOT / "tests" / "fixtures"

# developers.events records kept in the sample (exact conference names).
CFP_NAMES = [
    "Dutch AI Conference",                    # AI, has durations, tags via event
    "AI Context New York 2027",               # AI, multiple talk lengths
    "ContainerDays & AI Context London 2027",  # durations + topics
    "AI & Copilot Summit 01.-02. Juni 2027",   # online-only
    "DevFest 2026",                            # 4 same-named event editions
    "Mobile Makers 2027",                      # name hits IGNORE_TOPICS ("mobile")
    "HashiConf EU",                            # long-closed deadline
]
EVENT_NAMES = [
    "Dutch AI Conference",
    "AI Context New York 2027",
    "ContainerDays & AI Context London 2027",
    "AI & Copilot Summit 01.-02. Juni 2027",
    "DevFest 2026",                            # all four editions
    "STARWEST",                                # an event with no CFP
]

# confs.tech records kept in the sample: (source file, conference name).
CONFS_TECH_PICKS = [
    ("confs-tech-2027-python.json", "AI in Production"),   # future cfpEndDate
    ("confs-tech-2027-general.json", "Webdevcon"),         # future cfpEndDate
    ("confs-tech-2027-python.json", "PyCascades"),         # future cfpEndDate
    ("confs-tech-2026-general.json", "Digital Crafts Day"),  # past cfpEndDate
    ("confs-tech-2026-general.json", "Fosdem"),            # no cfpEndDate
]

# cfp.ninja records kept in the sample, by slug (across every API page).
CFP_NINJA_PICKS = [
    "conf42-ce-2027",                 # online, tags, no country
    "conf42-mlops-2027",              # online, tags
    "llmday-2026-montevideo-q4",      # in-person, country, no tags
    "sreday-2026-chennai-q4",         # in-person, country
    "sreday-2027-katowice-q2",        # deadline in the following year
    "platformday-2027-london-q2",     # in-person, UK
    "sreday-2025-lisbon-q4",          # long-past deadline (filtered out)
]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def extract_developers_events() -> None:
    cfps = [c for c in _load(CACHE / "all-cfps.json") if (c.get("conf") or {}).get("name") in CFP_NAMES]
    events = [e for e in _load(CACHE / "all-events.json") if e.get("name") in EVENT_NAMES]
    dest = OUT / "developers-events"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "all-cfps.sample.json").write_text(json.dumps(cfps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (dest / "all-events.sample.json").write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"developers.events: {len(cfps)} CFPs, {len(events)} events")


def extract_confs_tech() -> None:
    picks = []
    for filename, name in CONFS_TECH_PICKS:
        for entry in _load(CACHE / filename):
            if entry.get("name") == name:
                picks.append(entry)
                break
    dest = OUT / "confs-tech"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "general.sample.json").write_text(json.dumps(picks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"confs.tech: {len(picks)} entries")


def extract_manual() -> None:
    src = ROOT / "input" / "gmail1.md"
    dest = OUT / "manual"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "input.sample.md").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print("manual: copied input/gmail1.md")


def extract_cfp_ninja() -> None:
    events: dict[str, dict] = {}
    for page in sorted(CACHE.glob("cfp-ninja-events-*.json")):
        for event in _load(page).get("data", []):
            events[event.get("slug")] = event
    picks = [events[s] for s in CFP_NINJA_PICKS if s in events]
    dest = OUT / "cfp-ninja"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "events.sample.json").write_text(
        json.dumps(picks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"cfp.ninja: {len(picks)} events")


if __name__ == "__main__":
    extract_developers_events()
    extract_confs_tech()
    extract_cfp_ninja()
    extract_manual()
