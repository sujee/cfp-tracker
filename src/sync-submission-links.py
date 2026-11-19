#!/usr/bin/env python3
"""Add missing submission wikilinks to CFP notes, additively and repeatably.

Submission notes identify their CFP through a frontmatter ``cfp`` wikilink.
This command resolves those references against CFP filenames and appends missing
links to each CFP's ``submissions`` list. Existing entries are never removed.
Submission notes are read-only, and CFP timestamps remain unchanged.

Usage (from the repository root):
    python3 src/sync-submission-links.py --data data --submissions /path/to/submissions --check
    python3 src/sync-submission-links.py --data data --submissions /path/to/submissions
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cfp_writer import (  # noqa: E402
    FrontmatterError,
    _as_list,
    _as_str,
    _read_frontmatter,
    _read_submissions,
    set_property,
)

SUBMISSION_TYPES = {"submission", "talk-submission"}
READ_ERRORS = (FrontmatterError, OSError, UnicodeError)


@dataclass
class CfpNote:
    path: Path
    relative_target: str
    submissions: list[str]


@dataclass
class Change:
    path: Path
    values: list[str]
    additions: list[str]


@dataclass
class SyncPlan:
    data_dir: Path
    changes: list[Change] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    targeted: set[Path] = field(default_factory=set)
    submission_count: int = 0
    resolved_references: int = 0

    @property
    def addition_count(self) -> int:
        return sum(len(change.additions) for change in self.changes)

    @property
    def unchanged_count(self) -> int:
        return len(self.targeted) - len(self.changes)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _link_target(value: str) -> str | None:
    """Return a normalized filename target from one Obsidian wikilink."""
    text = str(value).strip()
    if not (text.startswith("[[") and text.endswith("]]")):
        return None
    target = text[2:-2].split("|", 1)[0].split("#", 1)[0].strip()
    if target.casefold().endswith(".md"):
        target = target[:-3]
    target = target.replace("\\", "/").strip("/").strip()
    return target or None


def _submission_matches(target: str, available_targets: list[str]) -> list[str]:
    """Match a target against actual submission-relative paths."""
    key = target.casefold()
    if "/" not in key:
        return [
            relative
            for relative in available_targets
            if relative.rsplit("/", 1)[-1] == key
        ]
    return [
        relative
        for relative in available_targets
        if relative == key or relative.endswith("/" + key)
    ]


def _same_link(left: str, right: str, available_targets: list[str]) -> bool:
    """Compare exact links or links that uniquely resolve to the same file."""
    left_target = _link_target(left)
    right_target = _link_target(right)
    if left_target is None or right_target is None:
        return str(left).strip() == str(right).strip()
    if left_target.casefold() == right_target.casefold():
        return True
    left_matches = _submission_matches(left_target, available_targets)
    right_matches = _submission_matches(right_target, available_targets)
    return (
        len(left_matches) == 1
        and len(right_matches) == 1
        and left_matches == right_matches
    )


def _merge_links(
    existing: list[str], additions: list[str], available_targets: list[str]
) -> list[str]:
    """Keep existing entries and append only links not already represented."""
    merged = list(existing)
    for addition in additions:
        if not any(_same_link(current, addition, available_targets) for current in merged):
            merged.append(addition)
    return merged


def _resolve_cfp(target: str, notes: list[CfpNote]) -> list[CfpNote]:
    """Resolve a filename or path target, returning every possible match."""
    key = target.casefold()
    if "/" not in key:
        return [note for note in notes if note.path.stem.casefold() == key]
    return [
        note
        for note in notes
        if note.relative_target == key
        or note.relative_target.endswith("/" + key)
    ]


def build_plan(data_dir: Path, submissions_dir: Path) -> SyncPlan:
    """Scan both directories and build the complete additive update plan."""
    data_dir = data_dir.resolve()
    submissions_dir = submissions_dir.resolve()
    plan = SyncPlan(data_dir=data_dir)
    notes: list[CfpNote] = []

    for path in sorted(data_dir.rglob("*.md"), key=lambda item: item.as_posix()):
        try:
            frontmatter, _body = _read_frontmatter(path)
        except READ_ERRORS as exc:
            plan.warnings.append(f"unreadable CFP note {path}: {exc}")
            continue
        if _as_str(frontmatter.get("type")) != "cfp":
            continue
        relative = path.relative_to(data_dir).with_suffix("").as_posix().casefold()
        notes.append(CfpNote(path, relative, _read_submissions(frontmatter)))

    additions_by_cfp: dict[Path, list[str]] = defaultdict(list)
    notes_by_path = {note.path: note for note in notes}
    submission_files = sorted(
        submissions_dir.rglob("*.md"), key=lambda item: item.as_posix()
    )
    submission_targets = [
        path.relative_to(submissions_dir).with_suffix("").as_posix().casefold()
        for path in submission_files
    ]
    for path in submission_files:
        try:
            frontmatter, _body = _read_frontmatter(path)
        except READ_ERRORS as exc:
            plan.warnings.append(f"unreadable submission note {path}: {exc}")
            continue
        if _as_str(frontmatter.get("type")) not in SUBMISSION_TYPES:
            continue
        plan.submission_count += 1
        references = _as_list(frontmatter.get("cfp"))
        if not references:
            plan.warnings.append(f"missing cfp reference in {path}")
            continue
        addition = f"[[{path.relative_to(submissions_dir).with_suffix('').as_posix()}]]"
        for reference in references:
            target = _link_target(reference)
            if target is None:
                plan.warnings.append(f"invalid cfp reference {reference!r} in {path}")
                continue
            matches = _resolve_cfp(target, notes)
            if not matches:
                plan.warnings.append(f"unresolved cfp reference {reference!r} in {path}")
                continue
            if len(matches) > 1:
                choices = ", ".join(str(match.path) for match in matches)
                plan.warnings.append(
                    f"ambiguous cfp reference {reference!r} in {path}: {choices}"
                )
                continue
            note = matches[0]
            plan.resolved_references += 1
            plan.targeted.add(note.path)
            additions_by_cfp[note.path].append(addition)

    for cfp_path in sorted(additions_by_cfp, key=lambda item: item.as_posix()):
        note = notes_by_path[cfp_path]
        merged = _merge_links(
            note.submissions, additions_by_cfp[cfp_path], submission_targets
        )
        additions = merged[len(note.submissions) :]
        if additions:
            plan.changes.append(Change(note.path, merged, additions))
    return plan


def apply_plan(plan: SyncPlan) -> int:
    """Apply a prepared plan, changing only the CFP submissions property."""
    updated = 0
    for change in plan.changes:
        if set_property(change.path, "submissions", change.values) == "updated":
            updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add missing submission wikilinks to their referenced CFP notes."
    )
    parser.add_argument("--data", default="data", help="CFP notes directory (default: data).")
    parser.add_argument(
        "--submissions", required=True, help="Directory containing submission Markdown notes."
    )
    parser.add_argument(
        "--check", action="store_true", help="Report additions without writing files."
    )
    args = parser.parse_args()

    data_dir = Path(args.data).resolve()
    submissions_dir = Path(args.submissions).resolve()
    if not data_dir.is_dir():
        print(f"sync-submission-links: CFP directory not found: {data_dir}", file=sys.stderr)
        return 2
    if not submissions_dir.is_dir():
        print(
            f"sync-submission-links: submissions directory not found: {submissions_dir}",
            file=sys.stderr,
        )
        return 2

    plan = build_plan(data_dir, submissions_dir)
    for warning in plan.warnings:
        print(f"sync-submission-links: warning: {warning}", file=sys.stderr)

    for change in plan.changes:
        action = "would update" if args.check else "update"
        print(f"{action} {_relative(change.path, data_dir)}")
        for addition in change.additions:
            print(f"  + {addition}")

    try:
        updated = len(plan.changes) if args.check else apply_plan(plan)
    except (OSError, FrontmatterError) as exc:
        print(f"sync-submission-links: write failed: {exc}", file=sys.stderr)
        return 2

    action = "would add" if args.check else "added"
    link_noun = "link" if plan.addition_count == 1 else "links"
    note_noun = "note" if updated == 1 else "notes"
    print(
        f"sync-submission-links: {plan.submission_count} submission notes, "
        f"{plan.resolved_references} resolved references. {action} "
        f"{plan.addition_count} {link_noun} across {updated} CFP {note_noun}. "
        f"{plan.unchanged_count} targeted CFP notes already current."
    )
    return 1 if plan.warnings else 0


if __name__ == "__main__":
    sys.exit(main())
