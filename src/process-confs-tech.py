#!/usr/bin/env python3
"""Parse CFPs from confs.tech (github.com/tech-conferences/conference-data)."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import urllib.request
from pathlib import Path

GITHUB_API = "https://api.github.com/repos/tech-conferences/conference-data/contents/conferences"
RAW_BASE = "https://raw.githubusercontent.com/tech-conferences/conference-data/master/conferences"


def _fetch_json(url: str, cache_path: Path | None = None, cache_key: str | None = None):
    if cache_path and cache_key:
        dest = cache_path / cache_key
        if dest.is_file():
            try:
                return json.loads(dest.read_text(encoding="utf-8"))
            except Exception:
                pass
    req = urllib.request.Request(url, headers={"User-Agent": "cfp-merge/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if cache_path and cache_key:
        cache_path.mkdir(parents=True, exist_ok=True)
        (cache_path / cache_key).write_text(json.dumps(data), encoding="utf-8")
    return data


def _parse_date(s) -> _dt.date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return _dt.datetime.strptime(str(s)[:19], fmt).date()
        except ValueError:
            continue
    return None


_DISCOVERED: set[str] = set()


def collect_rows(cutoff: _dt.date, today: _dt.date, cache_path: Path | None = None) -> list[dict]:
    rows = []
    seen = set()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    _CONFS_TECH_TOPICS = {
        t.lower().replace("_", "-")
        for t in getattr(_cfg, "CONFS_TECH_TOPICS", set())
    }
    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]

    for year in (today.year, today.year + 1):
        try:
            listing = _fetch_json(f"{GITHUB_API}/{year}", cache_path, f"confs-tech-listing-{year}.json")
        except Exception as e:
            print(f"could not list conferences/{year}: {e}", file=sys.stderr)
            continue
        for item in listing:
            if not item.get("name", "").endswith(".json"):
                continue
            topic = item["name"].replace(".json", "")
            _DISCOVERED.add(topic)
            if _CONFS_TECH_TOPICS and topic != "general" and topic.lower().replace("_", "-") not in _CONFS_TECH_TOPICS:
                continue
            try:
                data = _fetch_json(f"{RAW_BASE}/{year}/{item['name']}", cache_path, f"confs-tech-{year}-{item['name']}")
            except Exception as e:
                print(f"could not fetch {year}/{item['name']}: {e}", file=sys.stderr)
                continue
            if not isinstance(data, list):
                continue
            for ev in data:
                cfp_end = _parse_date(ev.get("cfpEndDate"))
                if cfp_end is None or cfp_end < cutoff:
                    continue
                name = ev.get("name") or ""
                if any(t in name.lower() for t in _IGNORE):
                    continue
                key = re.sub(r"[^a-z0-9]", "", name.lower())
                if key in seen:
                    continue
                seen.add(key)
                start = _parse_date(ev.get("startDate"))
                event_date = start.isoformat() if start else "TBA"
                loc_parts = [ev.get("city"), ev.get("country")]
                loc = ", ".join(p for p in loc_parts if p) or "—"
                rows.append(
                    {
                        "name": name,
                        "location": loc,
                        "cfp_close": cfp_end.isoformat(),
                        "event_date": event_date,
                        "event_url": ev.get("url") or "",
                        "cfp_url": ev.get("cfpUrl") or "",
                    }
                )
    return rows


DISCOVERED_TOPICS_PATH = Path(__file__).resolve().with_name("discovered-topics.txt")


def write_discovered_topics(topics: set[str], path: Path | str | None = None) -> None:
    """Write upstream topic names for reference; never used for extraction."""
    dest = Path(path) if path is not None else DISCOVERED_TOPICS_PATH
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("".join(f"{topic}\n" for topic in sorted(topics)), encoding="utf-8")
    except OSError as exc:
        print(f"could not write {dest}: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--today", default=_dt.date.today().isoformat())
    ap.add_argument("--months-back", type=int, default=1)
    ap.add_argument("--cache", default=str(Path(__file__).resolve().parent.parent / "cache"))
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args()

    today = _dt.date.fromisoformat(args.today)
    cutoff = today - _dt.timedelta(days=30 * max(1, args.months_back))

    rows = collect_rows(cutoff, today, Path(args.cache))
    write_discovered_topics(_DISCOVERED)

    data_dir = Path(args.out).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import upsert_counted, summary_line, write_manifest

    counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    produced = []
    for r in rows:
        row = {
            "name": r["name"],
            "event_date": r["event_date"],
            "location": r["location"],
            "country": "",
            "cfp_close": r["cfp_close"],
            "topics": [],
            "event_url": r["event_url"],
            "cfp_url": r["cfp_url"],
            "source": "confs.tech",
        }
        upsert_counted(data_dir, row, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    print(summary_line("confs.tech", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
