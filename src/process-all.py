#!/usr/bin/env python3
"""Wrapper that runs the full CFP pipeline (per-CFP files)."""
from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter
import sys
import tempfile
from pathlib import Path

BOLD = "\033[1m"
RESET = "\033[0m"


def _tty() -> bool:
    return sys.stdout.isatty()


def _style(text: str, code: str) -> str:
    return f"{code}{text}{RESET}" if _tty() else text


def collect_summaries(output: str) -> list[dict]:
    """Parse per-source ``summary_line`` rows emitted by each step."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from cfp_writer import SUMMARY_RE
    except Exception:
        return []
    rows = []
    for line in output.splitlines():
        m = SUMMARY_RE.match(line.strip())
        if m:
            rows.append({k: (int(v) if k != "source" else v) for k, v in m.groupdict().items()})
    return rows


def included_event_types() -> set[str]:
    """Resolve and validate the configured event-type allow-list."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import EVENT_TYPES, _event_type_included

    return {event_type for event_type in EVENT_TYPES if _event_type_included(event_type)}


# Canonical source name -> (script, manifest stem). Order mirrors
# ``cfp_writer.SOURCE_PRIORITY`` so a run always processes sources in the same
# order regardless of how config.INPUT_SOURCES is written.
SOURCE_STEPS = {
    "developers.events": ("process-developer-events.py", "dev"),
    "cfp.ninja": ("process-cfp-ninja.py", "ninja"),
    "confs.tech": ("process-confs-tech.py", "confs"),
    "adato-tracker": ("process-adato-tracker.py", "adato"),
    "open-tech-cfps": ("process-open-tech-cfps.py", "opentech"),
    "manual": ("process-manual-input.py", "manual"),
}


def selected_sources() -> list[str]:
    """Resolve and validate the configured source allow-list.

    Unknown names, non-string entries, and an empty list raise ``ValueError``
    before anything runs (same fail-loudly contract as ``EVENT_TYPES``).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg

    configured = getattr(_cfg, "INPUT_SOURCES", None)
    if configured is None:
        return list(SOURCE_STEPS)
    if isinstance(configured, str) or not hasattr(configured, "__iter__"):
        raise ValueError("config.INPUT_SOURCES must be a list of source names")
    names: list[str] = []
    for item in configured:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("config.INPUT_SOURCES must contain nonempty source names")
        name = item.strip()
        if name not in SOURCE_STEPS:
            raise ValueError(
                f"Unknown config.INPUT_SOURCES value: {name!r}; "
                f"choose from {', '.join(SOURCE_STEPS)}"
            )
        if name not in names:
            names.append(name)
    if not names:
        raise ValueError("config.INPUT_SOURCES must not be empty")
    return names


def collect_event_type_counts(data_dir: Path) -> dict[str, Counter]:
    """Count live CFP notes by stored source and resolved event type."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import (
        FrontmatterError,
        _as_str,
        _event_name,
        _read_frontmatter,
        infer_event_type,
    )

    counts: dict[str, Counter] = {}
    if not data_dir.is_dir():
        return counts
    for path in sorted(data_dir.rglob("*.md")):
        try:
            fm, _ = _read_frontmatter(path)
        except (OSError, FrontmatterError):
            continue
        if _as_str(fm.get("type")) != "cfp":
            continue
        source = _as_str(fm.get("source")) or "unknown"
        event_type = _as_str(fm.get("event_type")).strip() or infer_event_type(_event_name(fm))
        counts.setdefault(source, Counter())[event_type] += 1
    return counts


def event_type_summary_lines(
    counts: dict[str, Counter], summaries: list[dict], included: set[str]
) -> list[str]:
    """Format a source × event-type matrix, starring configured types."""
    if not counts:
        return []
    from cfp_writer import EVENT_TYPES

    rows = [
        (summary["source"], "manual" if summary["source"] == "manual input" else summary["source"])
        for summary in summaries
    ]
    used = {key for _, key in rows}
    rows.extend((source, source) for source in sorted(set(counts) - used))
    event_types = list(EVENT_TYPES)
    event_types += sorted(
        {event_type for counter in counts.values() for event_type in counter}
        - set(event_types)
    )
    labels = {
        event_type: event_type + (" ★" if event_type in included else "")
        for event_type in event_types
    }
    name_w = max(len(label) for label, _ in rows + [("Total", "")]) + 2
    name_w = max(name_w, len("source") + 2)
    totals = Counter()
    for counter in counts.values():
        totals.update(counter)
    widths = {
        event_type: max(len(labels[event_type]), len(str(totals[event_type]))) + 2
        for event_type in event_types
    }
    header = f"{'source':<{name_w}}" + "".join(
        f"{labels[event_type]:>{widths[event_type]}}" for event_type in event_types
    )
    lines = [
        "",
        _style(" Event types (live notes; ★ = included in EVENT_TYPES)", BOLD),
        header,
        "-" * len(header),
    ]
    for label, source in rows:
        total = Counter(counts.get(source, Counter()))
        lines.append(
            f"{label:<{name_w}}"
            + "".join(
                f"{total[event_type]:>{widths[event_type]}}" for event_type in event_types
            )
        )
    lines.append("-" * len(header))
    lines.append(
        f"{'Total':<{name_w}}"
        + "".join(f"{totals[event_type]:>{widths[event_type]}}" for event_type in event_types)
    )
    return lines


def print_summary(
    summaries: list[dict],
    data_dir: Path,
    archived: int = 0,
    archive_dir: Path | None = None,
    included: set[str] | None = None,
) -> None:
    if not summaries:
        return
    new_total = sum(s["new"] for s in summaries)
    updated_total = sum(s["updated"] for s in summaries)
    unchanged_total = sum(s["unchanged"] for s in summaries)
    found_total = sum(s["found"] for s in summaries)

    name_w = max(len(s["source"]) for s in summaries) + 2
    name_w = max(name_w, len("Total"))
    header = (
        f"{'source':<{name_w}}{'found':>7}{'new':>7}{'updated':>9}{'unchanged':>11}"
    )

    lines = [
        "",
        "=" * len(header),
        _style(" CFP refresh summary", BOLD),
        "=" * len(header),
        header,
        "-" * len(header),
    ]
    for s in summaries:
        lines.append(
            f"{s['source']:<{name_w}}{s['found']:>7}{s['new']:>7}{s['updated']:>9}{s['unchanged']:>11}"
        )
    lines.append("-" * len(header))
    lines.append(
        f"{'Total':<{name_w}}{found_total:>7}{new_total:>7}{updated_total:>9}{unchanged_total:>11}"
    )

    # Count notes actually on disk (what cfps.base reads).
    on_disk = sum(1 for _ in data_dir.rglob("*.md")) if data_dir.is_dir() else 0

    lines.append("")
    lines.append(
        _style(
            f"  Found {found_total} CFPs across {len(summaries)} source(s)  ·  "
            f"{new_total} new  ·  {updated_total} updated  ·  {unchanged_total} already current",
            BOLD,
        )
    )
    lines.append(f"  {on_disk} notes on disk in {data_dir}")
    if archived:
        lines.append(f"  {archived} archived (no source carries them any more) -> {archive_dir}")
    if included is None:
        included = included_event_types()
    lines.extend(event_type_summary_lines(collect_event_type_counts(data_dir), summaries, included))
    lines.append("=" * len(header))
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description="Run all CFP processors.")
    ap.add_argument("--out", default="data")
    ap.add_argument("--input", default="input")
    ap.add_argument(
        "--archive",
        default=None,
        help="Folder for notes no source produces any more (default: 'archived' beside --out).",
    )
    ap.add_argument("--no-archive", action="store_true", help="Do not archive orphan notes.")
    ap.add_argument(
        "--prestige",
        default=None,
        help="Curated ranking table; default prestige.md at the repo root when present.",
    )
    ap.add_argument(
        "--no-prestige", action="store_true", help="Do not stamp curated prestige tiers."
    )
    args, rest = ap.parse_known_args()
    included = included_event_types()  # Fail invalid config before notes or archives change.
    selected = selected_sources()      # Same fail-first contract for INPUT_SOURCES.
    skipped_sources = [name for name in SOURCE_STEPS if name not in selected]

    here = Path(__file__).resolve().parent
    data_dir = Path(args.out).resolve()
    input_dir = Path(args.input).resolve()
    archive_dir = Path(args.archive).resolve() if args.archive else data_dir.parent / "archived"

    summaries: list[dict] = []
    archived = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        manifests: dict[str, Path] = {stem: tmp / f"{stem}.json" for _, stem in SOURCE_STEPS.values()}

        steps = []
        for name in selected:
            script, stem = SOURCE_STEPS[name]
            manifest = manifests[stem]
            cmd = [
                sys.executable, str(here / script),
                "--out", str(data_dir), "--manifest", str(manifest),
            ]
            if name == "developers.events":
                cmd += [*rest]
            if name == "manual":
                if not input_dir.is_dir():
                    # A missing input dir is a normal state, not an error; nothing
                    # will claim the manual manifest, so drop it from archiving.
                    print(f"skipping {name}: input dir not found: {input_dir}")
                    continue
                cmd += ["--input", str(input_dir)]
            steps.append(cmd)

        for cmd in steps:
            print(">", " ".join(cmd))
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)
            if proc.returncode != 0:
                print(f"step failed (exit {proc.returncode}): {cmd}", file=sys.stderr)
                return proc.returncode
            summaries.extend(collect_summaries(proc.stdout))

        if not args.no_archive and data_dir.is_dir():
            cmd = [sys.executable, str(here / "archive-orphans.py"), "--data", str(data_dir),
                   "--archive", str(archive_dir)]
            for name in selected:
                cmd += ["--manifest", str(manifests[SOURCE_STEPS[name][1]])]
            # Notes owned by a skipped source are NOT orphans: the source was not
            # asked to produce them this run, so they must stay in data/.
            for name in skipped_sources:
                cmd += ["--skip-source", name]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)
            if proc.returncode != 0:
                print(f"step failed (exit {proc.returncode}): {cmd}", file=sys.stderr)
                return proc.returncode
            m = re.search(r"archive-orphans: \w+ (\d+) note", proc.stdout)
            archived = int(m.group(1)) if m else 0

    # Curated ranking (prestige.md) -> `tier` on the matching notes. Runs last on
    # purpose: archiving has moved the orphans aside, and a refresh must never
    # undo a curated value. Silent when the table is absent (a fresh clone).
    prestige_file = (
        Path(args.prestige).resolve() if args.prestige else here.parent / "prestige.md"
    )
    if not args.no_prestige and prestige_file.is_file() and data_dir.is_dir():
        cmd = [
            sys.executable, str(here / "apply-prestige.py"),
            "--data", str(data_dir), "--list", str(prestige_file),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if proc.returncode != 0:
            print(f"step failed (exit {proc.returncode}): {cmd}", file=sys.stderr)
            return proc.returncode

    print_summary(summaries, data_dir, archived, archive_dir, included)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
