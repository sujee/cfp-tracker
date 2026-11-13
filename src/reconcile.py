"""Resolve current source rows against existing notes before committing writes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cfp_writer as writer


@dataclass
class Candidate:
    row: dict
    source: str
    target: Path
    ordinal: int


@dataclass
class Existing:
    path: Path
    url: str
    source: str
    name: str
    fm: dict
    body: str

    @property
    def curated(self) -> bool:
        # The writer-owned ``## Conflict`` section is generated, not curation.
        notes, _conflict = writer._split_conflict_section(
            writer._extract_body_notes(self.body)
        )
        custom = set(self.fm) - writer.KNOWN_FM_KEYS - {"tier"}
        return bool(
            writer._as_bool(self.fm.get("shortlist"))
            or writer._read_submissions(self.fm)
            or notes
            or writer._as_str(self.fm.get("notes")).strip()
            or custom
        )


@dataclass
class ReconcileResult:
    summaries: dict[str, dict[str, int]]
    produced: set[str]
    superseded: set[str]

    def summary_rows(self) -> list[dict]:
        return [
            {
                "source": source,
                "found": counts["found"],
                "new": counts["new"],
                "updated": counts["updated"],
                "unchanged": counts["unchanged"] + counts["skipped"],
            }
            for source, counts in self.summaries.items()
        ]


def _existing_notes(data_dir: Path) -> tuple[set[Path], list[Existing]]:
    paths = set()
    notes = []
    if not data_dir.is_dir():
        return paths, notes
    for path in sorted(data_dir.rglob("*.md")):
        paths.add(path)
        try:
            fm, body = writer._read_frontmatter(path)
        except (OSError, writer.FrontmatterError):
            continue
        if writer._as_str(fm.get("type")) != "cfp":
            continue
        notes.append(
            Existing(
                path,
                writer._url_key(fm.get("cfp_url")),
                writer._as_str(fm.get("source")),
                writer._event_name(fm),
                fm,
                body,
            )
        )
    return paths, notes


def _paused_owner(
    candidate: Candidate, existing: list[Existing], skipped_sources: set[str]
) -> Existing | None:
    """Return the richer paused note that protects this candidate, if any."""
    key = writer._url_key(candidate.row.get("cfp_url"))
    incoming = writer._source_priority(candidate.source)
    for note in existing:
        if note.source not in skipped_sources:
            continue
        if writer._source_priority(note.source) >= incoming:
            continue
        if note.path == candidate.target:
            return note
        if (
            key
            and note.url == key
            and note.path != candidate.target
            and writer._names_compatible(note.name, candidate.row.get("name"))
        ):
            return note
    return None


def _retired_paths(data_dir: Path, existing: list[Existing]) -> set[Path]:
    """Paths already replaced by a descendant still present in the live tree."""
    return {
        data_dir / rel
        for note in existing
        for rel in writer._as_list(note.fm.get("replaces"))
        if data_dir / rel != note.path
    }


def _predecessor(
    candidate: Candidate,
    paths: set[Path],
    existing: list[Existing],
    selected_targets: set[Path],
    retired_paths: set[Path],
) -> Path:
    if candidate.target in paths and candidate.target not in retired_paths:
        return candidate.target
    key = writer._url_key(candidate.row.get("cfp_url"))
    if not key:
        return candidate.target
    # Do not use an unparseable/non-CFP target for migration, but preserve it
    # rather than overwriting it from a live descendant.
    if candidate.target in paths and all(
        note.path != candidate.target for note in existing
    ):
        return candidate.target
    matches = [
        note
        for note in existing
        if note.path not in retired_paths
        and (
            note.path == candidate.target
            or (
                key
                and note.url == key
                and note.path not in selected_targets
                and writer._names_compatible(note.name, candidate.row.get("name"))
            )
        )
    ]
    if not matches:
        return candidate.target
    matches.sort(
        key=lambda note: (
            not note.curated,
            note.source != candidate.source,
            writer._source_priority(note.source),
            str(note.path),
        )
    )
    return matches[0].path


def _event_type_metadata(
    row: dict,
    target: Path,
    existing: list[Existing],
    existing_at_path: dict[Path, Existing],
    retired_paths: set[Path],
) -> str:
    """Resolve sticky type from the target or a compatible predecessor first."""
    target_note = existing_at_path.get(target)
    if (
        target_note
        and target not in retired_paths
        and writer._as_str(target_note.fm.get("event_type")).strip()
    ):
        return writer._as_str(target_note.fm["event_type"]).strip()
    key = writer._url_key(row.get("cfp_url"))
    matches = [
        note
        for note in existing
        if key
        and note.url == key
        and note.path not in retired_paths
        and writer._names_compatible(note.name, row.get("name"))
        and writer._as_str(note.fm.get("event_type")).strip()
    ]
    matches.sort(
        key=lambda note: (
            not writer._event_type_included(writer._as_str(note.fm.get("event_type"))),
            note.source != writer._as_str(row.get("source")),
            not note.curated,
            str(note.path),
        )
    )
    if matches:
        return writer._as_str(matches[0].fm["event_type"]).strip()
    return writer._event_type_for({}, row)


def _duplicates(
    candidate: Candidate,
    existing: list[Existing],
    selected_targets: set[Path],
    predecessor: Path,
) -> list[Existing]:
    """Other stored versions whose user state can merge into the live target."""
    key = writer._url_key(candidate.row.get("cfp_url"))
    if not key:
        return []
    return [
        note
        for note in existing
        if note.path not in selected_targets
        and note.path != predecessor
        and note.url == key
        and writer._names_compatible(note.name, candidate.row.get("name"))
    ]


def _close_rank(candidate: Candidate) -> int:
    """Later ISO deadlines win a same-source revised-CFP tie."""
    value = writer._as_str(candidate.row.get("cfp_close"))
    try:
        return date.fromisoformat(value[:10]).toordinal()
    except ValueError:
        return date.min.toordinal()


def reconcile_rows(
    data_dir: Path,
    rows_by_source: dict[str, list[dict]],
    *,
    today=None,
    skipped_sources=(),
) -> ReconcileResult:
    """Choose current winners and write each at most once.

    Current rows decide source ownership. Existing notes are used for matching,
    curation, and timestamps rather than as permanent higher-priority vetoes.
    Paths of replaced notes are returned separately so archiving can move them
    after their curated state has been migrated.
    """
    data_dir = Path(data_dir)
    skipped_sources = set(skipped_sources or ())
    paths, existing = _existing_notes(data_dir)
    existing_at_path = {note.path: note for note in existing}
    retired_paths = _retired_paths(data_dir, existing)
    summaries = {
        source: {"found": 0, "new": 0, "updated": 0, "unchanged": 0, "skipped": 0}
        for source in rows_by_source
    }

    # Validate the settings that can otherwise remove a whole source before any
    # candidate can influence ownership or archiving.
    import config

    config.validate_filter_settings()
    writer._event_type_patterns()

    candidates = []
    ordinal = 0
    for source, rows in rows_by_source.items():
        for original in rows:
            ordinal += 1
            summaries[source]["found"] += 1
            row = {**original, "source": source}
            if writer.event_name_is_ignored(row.get("name")):
                summaries[source]["skipped"] += 1
                continue
            target = writer.note_path(data_dir, row)
            event_type = _event_type_metadata(
                row, target, existing, existing_at_path, retired_paths
            )
            if not writer._event_type_included(event_type):
                summaries[source]["skipped"] += 1
                continue
            row["event_type"] = event_type
            candidates.append(Candidate(row, source, target, ordinal))

    def skip(candidate: Candidate) -> None:
        summaries[candidate.source]["skipped"] += 1

    # First choose one current row per target path. This is intentionally a
    # current-data comparison, not a comparison with the note's old owner.
    by_path = {}
    for candidate in candidates:
        by_path.setdefault(candidate.target, []).append(candidate)
    path_winners = []
    for target, group in by_path.items():
        group.sort(key=lambda c: (writer._source_priority(c.source), c.ordinal))
        path_winners.append(group[0])
        for loser in group[1:]:
            skip(loser)

    # Then resolve differently named/path duplicates by normalized submission
    # URL plus the existing conservative compatibility check. Only directly
    # compatible rows merge; transitive guessing through shared forms is avoided.
    path_winners.sort(
        key=lambda c: (
            writer._source_priority(c.source),
            -_close_rank(c),
            str(c.target),
            c.ordinal,
        )
    )
    remaining = path_winners
    groups = []
    while remaining:
        winner = remaining[0]
        key = writer._url_key(winner.row.get("cfp_url"))
        compatible = []
        distinct = []
        for other in remaining[1:]:
            same_cfp = (
                key
                and writer._url_key(other.row.get("cfp_url")) == key
                and writer._names_compatible(
                    winner.row.get("name"), other.row.get("name")
                )
            )
            (compatible if same_cfp else distinct).append(other)
        groups.append([winner, *compatible])
        remaining = distinct

    all_targets = {candidate.target for group in groups for candidate in group}
    produced = set()
    superseded = set()
    for group in groups:
        attempted = set()
        protected_paths = set()
        for candidate in group:
            paused_owner = _paused_owner(candidate, existing, skipped_sources)
            if paused_owner is not None:
                protected_paths.add(paused_owner.path)
                skip(candidate)
                attempted.add(candidate.ordinal)
                continue
            predecessor = _predecessor(
                candidate, paths, existing, all_targets, retired_paths
            )
            status = writer.upsert(
                data_dir,
                candidate.row,
                today=today,
                previous_path=predecessor,
                target_path=candidate.target,
                deduplicate=False,
                allow_source_takeover=True,
                resolved_event_type=candidate.row.get("event_type"),
            )
            summaries[candidate.source][status] += 1
            attempted.add(candidate.ordinal)
            if status == "skipped":
                continue

            # Keep the other current alternatives out of the manifest but use
            # their stored state before archiving their old notes.
            for alternative in group:
                if alternative.ordinal not in attempted:
                    skip(alternative)
            alternative_notes = [
                existing_at_path[alternative.target]
                for alternative in group
                if alternative.target != candidate.target
                and alternative.target in existing_at_path
                and alternative.target != predecessor
            ]
            duplicates = _duplicates(candidate, existing, all_targets, predecessor)
            duplicates.extend(alternative_notes)
            unique_duplicates = {
                note.path: note
                for note in duplicates
                if note.path not in protected_paths
            }
            target_rel = candidate.target.relative_to(data_dir).as_posix()
            lineage_paths = [note.path for note in unique_duplicates.values()]
            if predecessor != candidate.target and predecessor not in protected_paths:
                lineage_paths.append(predecessor)
            for lineage_path in lineage_paths:
                writer.prune_lineage_reference(lineage_path, target_rel)
            merged = writer.merge_curation(
                candidate.target,
                [note.path for note in unique_duplicates.values()],
                data_dir,
            )
            if merged == "updated" and status == "unchanged":
                summaries[candidate.source]["unchanged"] -= 1
                summaries[candidate.source]["updated"] += 1

            produced.add(candidate.target.relative_to(data_dir).as_posix())
            if predecessor != candidate.target:
                superseded.add(predecessor.relative_to(data_dir).as_posix())
            for note in unique_duplicates.values():
                superseded.add(note.path.relative_to(data_dir).as_posix())
            break

    return ReconcileResult(summaries, produced, superseded)
