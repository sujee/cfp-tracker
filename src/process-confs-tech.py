#!/usr/bin/env python3
"""Parse CFPs from confs.tech (github.com/tech-conferences/conference-data)."""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
import urllib.error
from pathlib import Path

from http_cache import fetch_json

GITHUB_API = "https://api.github.com/repos/tech-conferences/conference-data/contents/conferences"
RAW_BASE = "https://raw.githubusercontent.com/tech-conferences/conference-data/master/conferences"


def _validate_listing(data, year: int) -> bool:
    if not isinstance(data, list) or not data:
        raise ValueError(f"confs.tech {year}: expected a nonempty topic listing")
    topic_items = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError(f"confs.tech {year}: malformed topic listing entry")
        if item["name"].endswith(".json"):
            topic_items.append(item)
    if not topic_items:
        raise ValueError(f"confs.tech {year}: topic listing contains no JSON files")
    return True


def _validate_topic_events(data, year: int, filename: str) -> bool:
    if not isinstance(data, list):
        raise ValueError(f"confs.tech {year}/{filename}: expected a list of events")
    if not all(isinstance(event, dict) for event in data):
        raise ValueError(
            f"confs.tech {year}/{filename}: expected every event to be an object"
        )
    return True


def _fetch_json(
    url: str,
    cache_path: Path | None = None,
    cache_key: str | None = None,
    offline: bool = False,
    validator=None,
):
    """Fetch JSON through the shared online-first cache."""
    return fetch_json(
        url,
        cache_path,
        cache_key,
        offline=offline,
        source="confs.tech",
        accept="application/vnd.github+json",
        validator=validator,
    )


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


def collect_rows(
    cutoff: _dt.date,
    today: _dt.date,
    cache_path: Path | None = None,
    offline: bool = False,
) -> list[dict]:
    rows = []
    seen = {}
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg
    import cfp_writer as _writer

    _CONFS_TECH_TOPICS = {
        t.lower().replace("_", "-")
        for t in getattr(_cfg, "CONFS_TECH_TOPICS", set())
    }
    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]

    for year in (today.year, today.year + 1):
        try:
            listing = _fetch_json(
                f"{GITHUB_API}/{year}",
                cache_path,
                f"confs-tech-listing-{year}.json",
                offline=offline,
                validator=lambda data, year=year: _validate_listing(data, year),
            )
        except Exception as exc:
            if (
                year == today.year + 1
                and isinstance(exc, urllib.error.HTTPError)
                and exc.code == 404
            ):
                continue
            raise RuntimeError(
                f"confs.tech: could not list conferences/{year}: {exc}"
            ) from exc
        _validate_listing(listing, year)
        topic_items = [item for item in listing if item["name"].endswith(".json")]

        for item in topic_items:
            topic = item["name"].removesuffix(".json")
            _DISCOVERED.add(topic)
            if (
                _CONFS_TECH_TOPICS
                and topic != "general"
                and topic.lower().replace("_", "-") not in _CONFS_TECH_TOPICS
            ):
                continue
            try:
                data = _fetch_json(
                    f"{RAW_BASE}/{year}/{item['name']}",
                    cache_path,
                    f"confs-tech-{year}-{item['name']}",
                    offline=offline,
                    validator=lambda data, year=year, filename=item["name"]: (
                        _validate_topic_events(data, year, filename)
                    ),
                )
            except Exception as exc:
                raise RuntimeError(
                    f"confs.tech: could not fetch {year}/{item['name']}: {exc}"
                ) from exc
            _validate_topic_events(data, year, item["name"])
            for ev in data:
                cfp_end = _parse_date(ev.get("cfpEndDate"))
                if cfp_end is None or cfp_end < cutoff:
                    continue
                name = ev.get("name") or ""
                if any(t in name.lower() for t in _IGNORE):
                    continue
                start = _parse_date(ev.get("startDate"))
                event_date = start.isoformat() if start else "TBA"
                online = ev.get("online") is True
                country = "Online" if online else (ev.get("country") or "")
                loc_parts = [ev.get("city"), ev.get("country")]
                loc = "Online" if online else (", ".join(p for p in loc_parts if p) or "—")
                key = (
                    re.sub(r"[^a-z0-9]", "", name.lower()),
                    cfp_end.isoformat(),
                    event_date,
                    loc.casefold(),
                    _writer._url_key(ev.get("cfpUrl")),
                )
                topic_values = [] if topic == "general" else [topic]
                if key in seen:
                    previous = rows[seen[key]]
                    previous["topics"] = list(
                        dict.fromkeys(previous.get("topics", []) + topic_values)
                    )
                    continue
                seen[key] = len(rows)
                rows.append(
                    {
                        "name": name,
                        "location": loc,
                        "cfp_close": cfp_end.isoformat(),
                        "event_date": event_date,
                        "country": country,
                        "topics": topic_values,
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
    ap.add_argument("--superseded-manifest", default=None)
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Read only cached responses; do not access the network.",
    )
    ap.add_argument(
        "--write-discovered-topics",
        action="store_true",
        help="Write the upstream topic reference after a successful fetch.",
    )
    args = ap.parse_args()

    today = _dt.date.fromisoformat(args.today)
    cutoff = today - _dt.timedelta(days=30 * max(1, args.months_back))

    rows = [
        {**row, "source": "confs.tech"}
        for row in collect_rows(cutoff, today, Path(args.cache), offline=args.offline)
    ]
    if args.write_discovered_topics:
        write_discovered_topics(_DISCOVERED)

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

    print(summary_line("confs.tech", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
