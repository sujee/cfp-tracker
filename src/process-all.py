#!/usr/bin/env python3
"""Wrapper that runs the full CFP pipeline (per-CFP files)."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BOLD = "\033[1m"
DIM = "\033[2m"
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


def print_summary(summaries: list[dict], data_dir: Path, archived: int = 0, archive_dir: Path | None = None) -> None:
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
    args, rest = ap.parse_known_args()

    here = Path(__file__).resolve().parent
    data_dir = Path(args.out).resolve()
    input_dir = Path(args.input).resolve()
    archive_dir = Path(args.archive).resolve() if args.archive else data_dir.parent / "archived"

    summaries: list[dict] = []
    archived = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        dev_m, confs_m, ninja_m, manual_m = (
            tmp / f"{n}.json" for n in ("dev", "confs", "ninja", "manual")
        )

        steps = [
            [sys.executable, str(here / "process-developer-events.py"), "--out", str(data_dir), "--manifest", str(dev_m), *rest],
            [sys.executable, str(here / "process-cfp-ninja.py"), "--out", str(data_dir), "--manifest", str(ninja_m)],
            [sys.executable, str(here / "process-confs-tech.py"), "--out", str(data_dir), "--manifest", str(confs_m)],
        ]
        if input_dir.is_dir():
            steps.append(
                [sys.executable, str(here / "process-manual-input.py"), "--out", str(data_dir),
                 "--input", str(input_dir), "--manifest", str(manual_m)]
            )

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
            for m in (dev_m, confs_m, ninja_m, manual_m):
                cmd += ["--manifest", str(m)]
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

    print_summary(summaries, data_dir, archived, archive_dir)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
