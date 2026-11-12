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
import re
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

# adato-tracker rows kept in the sample (exact event names in the table).
ADATO_NAMES = [
    ".NET Conf 2026 | Building the Next Generation of .NET Applications",  # VIRTUAL
    "Community Networks Conference",                 # city + state, CFP URL
    "Analytics and Data Summit 2027",                # city + state
    "Global AI Sarasota \u2013 Kickoff",             # entity in name, VIRTUAL
    "Dakar Bitcoin Days IV",                         # name hits IGNORE_TOPICS
    "SOAHR 2027 \u2013 SHRM-Atlanta's Annual Conference",  # entity + apostrophe
    "Mobile Makers",                                 # name hits IGNORE_TOPICS
    "AI Agents Day",                                 # VIRTUAL, mid-range date
    "SunSecCon",                                     # city + state
    "Conf42 MLOps 2027",                             # VIRTUAL, far-future deadline
]

# Open Tech CFPs records kept by stable upstream ID.
OPEN_TECH_CFPS_PICKS = {
    "open": [
        "sessionize:atlanta-hardware-builders",       # in-person, US, minimal tags/perks
        "sessionize:passmn-monthly-meetings-2026",    # online, tags, no event date
        "sessionize:agile-on-the-beach-2027",         # UK, travel + accommodation
    ],
    "closed": [
        "sessionize:6th-annual-north-carolina-cybersecurity",  # recently closed
        "sessionize:vku-stadtwerkekongress-2026-copy",         # too old to import
    ],
}


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


def extract_adato_tracker() -> None:
    html = (CACHE / "adato-tracker.html").read_text(encoding="utf-8")
    table = re.search(r"<table[^>]*tablesorter.*?</table>", html, re.S).group(0)
    rows = re.findall(r"<tr.*?</tr>", table, re.S)

    def _name(row: str) -> str:
        cell = re.search(r"<t[hd].*?</t[hd]>", row, re.S)
        return re.sub(r"<[^>]+>", "", cell.group(0)).strip() if cell else ""

    picked: dict[str, str] = {}
    for row in rows:
        n = _name(row)
        if n in ADATO_NAMES and n not in picked:
            picked[n] = row
    ordered = [picked[n] for n in ADATO_NAMES if n in picked]
    wrapper = (
        '<table class="tablesorter">\n<thead>\n<tr>\n'
        "<th>Event Name</th>\n<th>City</th>\n<th>State</th>\n"
        '<th class="dateFormat-ddd m/d/yy">Event Start</th>\n'
        '<th class="dateFormat-ddd m/d/yy">Event End</th>\n'
        '<th class="dateFormat-ddd m/d/yy">CFP Close</th>\n'
        "<th>Event URL</th>\n<th>CFP URL</th>\n</tr>\n</thead>\n<tbody>\n"
        + "\n".join(r.strip() for r in ordered)
        + "\n</tbody>\n</table>\n"
    )
    dest = OUT / "adato-tracker"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "cfp-tracker.sample.html").write_text(wrapper, encoding="utf-8")
    print(f"adato-tracker: {len(ordered)} rows")


def extract_open_tech_cfps() -> None:
    dest = OUT / "open-tech-cfps"
    dest.mkdir(parents=True, exist_ok=True)
    for kind, wanted in OPEN_TECH_CFPS_PICKS.items():
        data = _load(CACHE / f"open-tech-cfps-{kind}.json")
        by_id = {event.get("id"): event for event in data.get("cfps", [])}
        missing = [event_id for event_id in wanted if event_id not in by_id]
        if missing:
            raise ValueError(f"Open Tech CFPs {kind}: fixture records missing: {missing}")
        picks = [by_id[event_id] for event_id in wanted]
        sample = {"generated_at": data.get("generated_at"), "count": len(picks), "cfps": picks}
        (dest / f"{kind}.sample.json").write_text(
            json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Open Tech CFPs {kind}: {len(picks)} rows")


if __name__ == "__main__":
    extract_developers_events()
    extract_confs_tech()
    extract_cfp_ninja()
    extract_manual()
    extract_adato_tracker()
    extract_open_tech_cfps()
