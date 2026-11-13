#!/usr/bin/env python3
"""Parse CFPs from PythonDeadlin.es (jesperdramsch/python-deadlines)."""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
import urllib.request
from pathlib import Path

import yaml

YAML_URL = "https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/_data/conferences.yml"


def _fetch_text(url: str, cache_path: Path | None = None, cache_key: str | None = None) -> str:
    if cache_path and cache_key:
        dest = cache_path / cache_key
        if dest.is_file():
            try:
                return dest.read_text(encoding="utf-8")
            except Exception:
                pass
    req = urllib.request.Request(url, headers={"User-Agent": "cfp-merge/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    if cache_path and cache_key:
        cache_path.mkdir(parents=True, exist_ok=True)
        (cache_path / cache_key).write_text(text, encoding="utf-8")
    return text


def _parse_date(value) -> _dt.date | None:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return _dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def collect_rows(cutoff: _dt.date, today: _dt.date, cache_path: Path | None = None) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]

    text = _fetch_text(YAML_URL, cache_path, "python-deadlines-conferences.yml")
    data = yaml.safe_load(text)
    if not isinstance(data, list):
        return []

    rows = []
    seen: set[tuple[str, str]] = set()
    for ev in data:
        if not isinstance(ev, dict):
            continue
        name = str(ev.get("conference") or "").strip()
        if not name:
            continue
        if any(t in name.lower() for t in _IGNORE):
            continue
        cfp_end = _parse_date(ev.get("cfp"))
        if cfp_end is None or cfp_end < cutoff:
            continue
        cfp_link = str(ev.get("cfp_link") or "").strip()
        # Require an actionable submission link; do not invent one.
        if not cfp_link:
            continue
        key = (re.sub(r"[^a-z0-9]", "", name.lower()), cfp_end.isoformat())
        if key in seen:
            continue
        seen.add(key)

        start = _parse_date(ev.get("start"))
        event_date = start.isoformat() if start else "TBA"
        place = str(ev.get("place") or "").strip()
        sub = ev.get("sub")
        if isinstance(sub, list):
            topics = [str(t).strip().lower() for t in sub if str(t).strip()]
        else:
            topics = [t.strip().lower() for t in str(sub or "").split(",") if t.strip()]

        rows.append(
            {
                "name": name,
                "location": place,
                "cfp_close": cfp_end.isoformat(),
                "event_date": event_date,
                "event_url": str(ev.get("link") or "").strip(),
                "cfp_url": cfp_link,
                "topics": topics,
            }
        )
    return rows


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
            "topics": r["topics"],
            "event_url": r["event_url"],
            "cfp_url": r["cfp_url"],
            "source": "python-deadlines",
        }
        upsert_counted(data_dir, row, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    print(summary_line("python-deadlines", len(rows), counts["new"], counts["updated"],
                      counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())