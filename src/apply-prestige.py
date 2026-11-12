#!/usr/bin/env python3
"""Stamp the curated `tier` from ``prestige.md`` onto the matching CFP notes.

Prestige is a judgement, not a feed value, so it lives in one hand-edited table
(``prestige.md``) rather than being inferred per source. This pass reads that
table and writes a single ``tier:`` property into every note whose name matches a
row — nothing else in the note is touched, and the ``created``/``updated`` stamps
are deliberately left alone (they track source-driven rewrites, not curation).

A note that matches **no** row keeps whatever ``tier`` it already has, so a
one-off can be ranked by editing the note directly. ``--check`` reports those so
they cannot rot silently.

Usage (from the repo root):
    python3 src/apply-prestige.py                 # stamp tiers under data/
    python3 src/apply-prestige.py --check         # report only; writes nothing
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prestige  # noqa: E402
from cfp_writer import (  # noqa: E402
    FrontmatterError,
    _as_str,
    _event_name,
    _read_frontmatter,
    set_property,
)


def _relative(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:  # pragma: no cover - only when --data names a single file
        return str(path)


def check_report(rules, notes, base: Path) -> list[str]:
    """Human-readable audit of the registry against the notes currently on disk.

    *notes* is ``[(path, name, existing tier)]``. Lists a per-row match count,
    the rows that matched nothing (the flagships no feed carries, and typos), the
    notes matched by more than one row, and existing tiers no rule claims.
    """
    hits = {
        id(rule): sum(
            1 for _p, name, _t in notes if any(prestige.phrase_matches(name, kw) for kw in rule.keywords)
        )
        for rule in rules
    }

    lines = [f"{len(rules)} rules · {len(notes)} notes", "", f"{'tier':>4}  {'notes':>5}  rule"]
    for rule in rules:
        count = hits[id(rule)]
        # A tier-3 row is usually a family series (Conf42, BSides) that is
        # expected to cover dozens of notes; only tiers 1-2 make a broad match
        # suspicious. Either way the count is shown, so a wrong keyword is visible.
        limit = 12 if rule.tier <= 2 else 50
        flag = ""
        if count == 0:
            flag = "   <- matches nothing"
        elif count > limit:
            flag = "   <- matches many; keyword may be too broad"
        lines.append(f"{rule.tier:>4}  {count:>5}  {rule.name}{flag}")

    unmatched = [r for r in rules if hits[id(r)] == 0]
    if unmatched:
        lines += ["", "No note matched (flagships no feed carries, or a keyword typo):"]
        lines += [f"  tier {r.tier}  {r.name}" for r in unmatched]

    conflicts: list[str] = []
    for _path, name, _tier in notes:
        matched = prestige.all_matching_rules(name, rules)
        if len(matched) > 1:
            best = matched[0]
            others = ", ".join(f"tier {r.tier} ({r.name})" for r in matched[1:])
            conflicts.append(f"  {name} -> tier {best.tier} ({best.name}); also {others}")
    if conflicts:
        lines += ["", "Matched several rows (lowest tier wins):"] + conflicts

    stale = [
        f"  {_relative(path, base)}  (tier {tier})"
        for path, name, tier in notes
        if tier and prestige.match_tier(name, rules) is None
    ]
    if stale:
        lines += [
            "",
            "Tier set but no rule matches (left as-is; add a row or clear the note):",
        ] + stale
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Stamp curated prestige tiers on CFP notes.")
    ap.add_argument("--data", default="data", help="Notes directory (default: data).")
    ap.add_argument(
        "--list", dest="list_path", default=None,
        help="Ranking table (default: prestige.md at the repo root).",
    )
    ap.add_argument("--check", action="store_true", help="Report only; write nothing.")
    args = ap.parse_args()

    rules_path = Path(args.list_path) if args.list_path else prestige.DEFAULT_FILE
    try:
        rules = prestige.load(rules_path)
    except ValueError as exc:
        print(f"apply-prestige: {exc}", file=sys.stderr)
        return 1
    if not rules:
        print(f"apply-prestige: no rules in {rules_path} (nothing to do)")
        return 0

    data_dir = Path(args.data).resolve()
    if not data_dir.is_dir():
        print(f"notes directory not found: {data_dir}", file=sys.stderr)
        return 1

    notes: list[tuple[Path, str, str]] = []
    skipped = 0
    for path in sorted(data_dir.rglob("*.md")):
        try:
            fm, _body = _read_frontmatter(path)
        except FrontmatterError:
            skipped += 1
            print(f"apply-prestige: skipping unparseable frontmatter: {path}", file=sys.stderr)
            continue
        if _as_str(fm.get("type")) != "cfp":
            continue
        notes.append((path, _event_name(fm), _as_str(fm.get("tier")).strip()))

    if args.check:
        print("\n".join(check_report(rules, notes, data_dir)))
        print(f"\nchecked {len(notes)} notes against {len(rules)} rules in {rules_path}")
        return 0

    counts: Counter = Counter()
    hand_set = []
    for path, name, existing in notes:
        tier = prestige.match_tier(name, rules)
        if tier is None:
            # No rule claims this note: a hand-set tier is the user's call.
            if existing:
                hand_set.append(_relative(path, data_dir))
            counts["untiered"] += 1
            continue
        counts[set_property(path, "tier", tier)] += 1

    unmatched_rules = sum(
        1
        for rule in rules
        if not any(
            prestige.phrase_matches(name, kw) for _p, name, _t in notes for kw in rule.keywords
        )
    )
    print(
        f"prestige: {len(rules)} rules, {len(notes)} notes -> "
        f"{counts['updated']} updated, {counts['unchanged']} unchanged, "
        f"{counts['untiered']} unmatched"
        + (f" ({len(hand_set)} with a hand-set tier kept)" if hand_set else "")
        + f"; {unmatched_rules} rule(s) matched nothing"
        + (f", {skipped} note(s) skipped" if skipped else "")
    )
    for rel in hand_set:
        print(f"  hand-set tier kept: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
