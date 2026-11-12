#!/usr/bin/env python3
"""Parse CFPs from Open Tech CFPs (CC BY 4.0, Sessionize-derived).

Public static JSON, with no authentication:

    https://1kevgriff.github.io/OpenTechCFPs/api/open.json
    https://1kevgriff.github.io/OpenTechCFPs/api/closed.json

``cfp_close_utc`` is the authoritative deadline. ``status`` is only correct at
``generated_at`` and is deliberately not used for date filtering.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import urllib.request
from pathlib import Path

API_BASE = "https://1kevgriff.github.io/OpenTechCFPs/api"
SOURCE = "open-tech-cfps"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from country import country_name_from_alpha2

import config as _cfg

_IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]


def _fetch_json(url: str, cache_path: Path | None = None, cache_key: str | None = None):
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


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_utc(value) -> _dt.datetime | None:
    """Parse an offset-aware ISO datetime and normalize it to UTC."""
    raw = _text(value)
    if not raw:
        return None
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(_dt.timezone.utc)


def _parse_date(value) -> _dt.date | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return _dt.date.fromisoformat(raw)
    except ValueError:
        return None


def benefits_of(event: dict) -> list[str]:
    """Map only explicit speaker expense coverage to the note's benefits."""
    perks = event.get("perks")
    if not isinstance(perks, dict):
        return []
    covered = {
        key
        for key, value in perks.items()
        if isinstance(value, str) and value.strip().lower() == "expenses covered"
    }
    benefits = []
    if "travel" in covered:
        benefits.append("travel")
    if "accommodation" in covered:
        benefits.append("hotel")
    # ``fee: free for speakers`` is admission, not an honorarium.
    return benefits


def fetch_records(cache_path: Path | None = None) -> list[dict]:
    records = []
    for kind in ("open", "closed"):
        data = _fetch_json(
            f"{API_BASE}/{kind}.json", cache_path, f"open-tech-cfps-{kind}.json"
        )
        if not isinstance(data, dict) or not isinstance(data.get("cfps"), list):
            raise ValueError(f"Open Tech CFPs {kind}: expected an object with a cfps list")
        for event in data["cfps"]:
            if not isinstance(event, dict):
                raise ValueError(f"Open Tech CFPs {kind}: expected every CFP to be an object")
            records.append(event)
    return records


def collect_rows(cutoff: _dt.date, cache_path: Path | None = None) -> list[dict]:
    """Return current and recently closed CFPs with an actionable CFP URL."""
    cutoff_utc = _dt.datetime.combine(cutoff, _dt.time.min, tzinfo=_dt.timezone.utc)
    rows = []
    seen: set[str] = set()
    seen_conferences: set[tuple[str, str]] = set()

    # The newest record wins a duplicate conference. This matters when a
    # Sessionize page is renamed or superseded but keeps the same name/deadline.
    records = sorted(
        fetch_records(cache_path),
        key=lambda event: _parse_utc(event.get("updated"))
        or _dt.datetime.min.replace(tzinfo=_dt.timezone.utc),
        reverse=True,
    )
    for event in records:
        close = _parse_utc(event.get("cfp_close_utc"))
        if close is None or close < cutoff_utc:
            continue
        name = _text(event.get("name"))
        cfp_url = _text(event.get("url"))
        if not name or not cfp_url:
            continue

        topics = []
        tags = event.get("tags")
        if isinstance(tags, list):
            for value in tags:
                tag = _text(value)
                if tag and tag.lower() != "untagged":
                    topics.append(tag)
        if any(t in name.lower() for t in _IGNORE):
            continue
        if any(any(ignored in tag.lower() for ignored in _IGNORE) for tag in topics):
            continue

        identities = {f"url:{cfp_url}"}
        event_id = _text(event.get("id"))
        if event_id:
            identities.add(f"id:{event_id}")
        if seen & identities:
            continue
        # Notes are keyed by normalized name + UTC close date. Distinct source
        # IDs sharing that key would rewrite one another in a single run.
        conference_key = (
            re.sub(r"[^a-z0-9]", "", name.lower()),
            close.date().isoformat(),
        )
        if conference_key in seen_conferences:
            continue
        seen.update(identities)
        seen_conferences.add(conference_key)

        start = _parse_date(event.get("event_start"))
        online = event.get("online") is True
        country = "Online" if online else country_name_from_alpha2(event.get("country"))
        location = _text(event.get("location")) or ("Online" if online else country) or "—"
        rows.append(
            {
                "name": name,
                "event_date": start.isoformat() if start else "TBA",
                "location": location,
                "country": country,
                "cfp_close": close.date().isoformat(),
                "topics": topics,
                "event_url": _text(event.get("website")),
                "cfp_url": cfp_url,
                "benefits": benefits_of(event),
            }
        )

    rows.sort(key=lambda row: (row["cfp_close"], row["name"].lower(), row["cfp_url"]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse CFPs from Open Tech CFPs.")
    ap.add_argument("--out", default="data")
    ap.add_argument("--today", default=_dt.date.today().isoformat())
    ap.add_argument("--months-back", type=int, default=1)
    ap.add_argument(
        "--cache", default=str(Path(__file__).resolve().parent.parent / "cache")
    )
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args()

    today = _dt.date.fromisoformat(args.today)
    cutoff = today - _dt.timedelta(days=30 * max(1, args.months_back))
    rows = collect_rows(cutoff, Path(args.cache))

    data_dir = Path(args.out).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    from cfp_writer import upsert_counted, summary_line, write_manifest

    counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    produced = []
    for row in rows:
        upsert_counted(data_dir, {**row, "source": SOURCE}, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    print(
        summary_line(
            SOURCE,
            len(rows),
            counts["new"],
            counts["updated"],
            counts["unchanged"] + counts["skipped"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
