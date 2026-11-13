#!/usr/bin/env python3
"""Parse CFPs from PythonDeadlin.es (jesperdramsch/python-deadlines)."""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
import urllib.error
from pathlib import Path

import yaml

from http_cache import fetch_text

YAML_URL = "https://raw.githubusercontent.com/jesperdramsch/python-deadlines/main/_data/conferences.yml"


def _validate_text(text: str) -> None:
    data = yaml.safe_load(text)
    if not isinstance(data, list) or not data:
        raise ValueError("python-deadlines: expected a nonempty YAML list")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError("python-deadlines: expected every entry to be a mapping")


def _fetch_text(
    url: str,
    cache_path: Path | None = None,
    cache_key: str | None = None,
    offline: bool = False,
):
    return fetch_text(
        url,
        cache_path,
        cache_key,
        offline=offline,
        source="python-deadlines",
        validator=_validate_text,
    )


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


def collect_rows(
    cutoff: _dt.date,
    today: _dt.date,
    cache_path: Path | None = None,
    offline: bool = False,
) -> list[dict]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]

    text = _fetch_text(YAML_URL, cache_path, "python-deadlines-conferences.yml", offline=offline)
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
                "country": "",
                "topics": topics,
                "event_url": str(ev.get("link") or "").strip(),
                "cfp_url": cfp_link,
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
    ap.add_argument("--superseded-manifest", default=None)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    today = _dt.date.fromisoformat(args.today)
    cutoff = today - _dt.timedelta(days=30 * max(1, args.months_back))

    rows = [
        {**row, "source": "python-deadlines"}
        for row in collect_rows(cutoff, today, Path(args.cache), offline=args.offline)
    ]

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

    print(summary_line("python-deadlines", len(rows), counts["new"], counts["updated"],
                      counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())