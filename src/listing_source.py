"""Shared utilities for independent event-listing adapters."""
from __future__ import annotations

import argparse
import datetime
import re
from pathlib import Path

from cfp_writer import emit_rows, parse_start_date, summary_line


def iso_prefix(value) -> str | None:
    """Return the first ISO date from a source value, or None when invalid."""
    text = str(value or "").strip()[:10]
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def with_domain_topics(values) -> list[str]:
    """Add normalized robotics and Physical AI topics without variant duplicates."""
    topics = []
    seen_other = set()
    has_robotics = False
    has_physical_ai = False
    for value in values or []:
        label = str(value or "").strip()
        if not label:
            continue
        key = re.sub(r"[^a-z0-9]+", "", label.casefold())
        if key == "robotics":
            if not has_robotics:
                topics.append("robotics")
                has_robotics = True
        elif key == "physicalai":
            if not has_physical_ai:
                topics.append("physical.ai")
                has_physical_ai = True
        elif label.casefold() not in seen_other:
            topics.append(label)
            seen_other.add(label.casefold())
    if not has_robotics:
        topics.append("robotics")
    if not has_physical_ai:
        topics.append("physical.ai")
    return topics


def conference_start_date(value) -> str:
    """Parse a listing's free-text start date, including cross-month ranges."""
    raw = str(value or "").strip()
    parsed = parse_start_date(raw)
    if parsed:
        return parsed
    year_match = re.search(r"(?:19|20)\d{2}", raw)
    if not year_match:
        return "TBA"
    first = re.split(r"\s+[–—-]\s*", raw, maxsplit=1)[0].strip(" ,")
    return parse_start_date(f"{first} {year_match.group(0)}") or "TBA"


def run_main(source: str, collect_rows) -> int:
    """Run one listing adapter with the common command-line options."""
    parser = argparse.ArgumentParser(description=f"Parse the {source} event listing.")
    parser.add_argument("--out", default="data")
    parser.add_argument("--today", default=datetime.date.today().isoformat())
    parser.add_argument("--months-back", type=int, default=1)
    parser.add_argument("--cache", default=str(Path(__file__).resolve().parent.parent / "cache"))
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--superseded-manifest", default=None)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    today = datetime.date.fromisoformat(args.today)
    cutoff = today - datetime.timedelta(days=30 * max(1, args.months_back))
    rows = [
        {**row, "source": source}
        for row in collect_rows(cutoff, today, Path(args.cache), args.offline)
    ]
    counts = emit_rows(
        Path(args.out).resolve(),
        rows,
        manifest=Path(args.manifest) if args.manifest else None,
        superseded_manifest=Path(args.superseded_manifest) if args.superseded_manifest else None,
        today=args.today,
    )
    print(summary_line(
        source,
        len(rows),
        counts["new"],
        counts["updated"],
        counts["unchanged"] + counts["skipped"],
    ))
    return 0
