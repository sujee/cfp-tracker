#!/usr/bin/env python3
"""Integration tests for current-run CFP identity and note replacement."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer as writer
from reconcile import Existing, reconcile_rows


def load_archiver():
    spec = importlib.util.spec_from_file_location("reconcile_test_archiver", ROOT / "src/archive-orphans.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archiver = load_archiver()


def row(**overrides) -> dict:
    value = {
        "name": "Example Summit 2027",
        "event_date": "2027-06-01",
        "location": "London, UK",
        "country": "UK",
        "cfp_close": "2026-12-01",
        "topics": ["ai"],
        "event_url": "https://example.test",
        "cfp_url": "https://sessionize.test/example-2027",
        "source": "developers.events",
    }
    value.update(overrides)
    return value


class ReconcileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "data"
        self.archive_dir = Path(self.tmp.name) / "archived"
        self.data.mkdir()
        writer.reset_cfp_url_index()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def curate(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        text = text.replace("shortlist: false", "shortlist: true")
        text = text.replace("dismissed: false", "dismissed: true")
        text = text.replace("submissions: []", 'submissions: ["[[My talk]]"]')
        text = text.replace("updated:", "priority: high\nupdated:", 1)
        text = text.replace("_Add notes here._", "Bring the demo.")
        path.write_text(text, encoding="utf-8")

    def archive(self, result) -> None:
        archiver.archive_orphans(
            self.data,
            self.archive_dir,
            result.produced,
            superseded=result.superseded,
        )

    def test_deadline_extension_migrates_curation_and_supersedes_old_path(self) -> None:
        original = row()
        self.assertEqual(writer.upsert(self.data, original, today="2026-11-01T00:00:00"), "new")
        old_path = writer.note_path(self.data, original)
        self.curate(old_path)

        current = row(cfp_close="2026-12-15")
        result = reconcile_rows(self.data, {"developers.events": [current]}, today="2026-12-01T00:00:00")
        new_path = writer.note_path(self.data, current)
        self.assertEqual(result.produced, {new_path.relative_to(self.data).as_posix()})
        self.assertEqual(result.superseded, {old_path.relative_to(self.data).as_posix()})
        self.assertEqual(result.summaries["developers.events"]["updated"], 1)

        fm, body = writer._read_frontmatter(new_path)
        self.assertTrue(fm["shortlist"])
        self.assertTrue(fm["dismissed"])
        self.assertEqual(fm["submissions"], ["[[My talk]]"])
        self.assertEqual(fm["priority"], "high")
        self.assertEqual(writer._as_str(fm["created"]), "2026-11-01T00:00:00")
        self.assertEqual(writer._as_str(fm["updated"]), "2026-12-01T00:00:00")
        self.assertIn("Bring the demo.", body)

        self.archive(result)
        self.assertFalse(old_path.exists())
        self.assertTrue((self.archive_dir / old_path.relative_to(self.data)).is_file())
        self.assertTrue(new_path.is_file())

    def test_active_lower_priority_source_takes_over_stale_owner(self) -> None:
        original = row(name="SCaLE 24x")
        writer.upsert(self.data, original)
        old_path = writer.note_path(self.data, original)
        self.curate(old_path)
        current = row(
            name="Southern California Linux Expo - SCaLE 24x",
            source="open-tech-cfps",
        )

        result = reconcile_rows(self.data, {"open-tech-cfps": [current]}, today="2026-11-20")
        current_path = writer.note_path(self.data, current)
        self.assertIn(current_path.relative_to(self.data).as_posix(), result.produced)
        self.archive(result)

        fm, body = writer._read_frontmatter(current_path)
        self.assertEqual(fm["source"], "open-tech-cfps")
        self.assertTrue(fm["shortlist"])
        self.assertIn("Bring the demo.", body)
        self.assertFalse(old_path.exists())

    def test_paused_higher_priority_source_retains_ownership(self) -> None:
        original = row()
        writer.upsert(self.data, original)
        old_path = writer.note_path(self.data, original)
        self.curate(old_path)
        current = row(name="Example Summit and Conference 2027", source="open-tech-cfps")

        result = reconcile_rows(
            self.data,
            {"open-tech-cfps": [current]},
            skipped_sources={"developers.events"},
        )
        self.assertFalse(result.produced)
        self.assertFalse(result.superseded)
        self.assertTrue(old_path.is_file())
        self.assertFalse(writer.note_path(self.data, current).exists())

    def test_existing_target_inherits_curation_from_older_duplicate(self) -> None:
        current = row(name="Example Summit 2027")
        writer.upsert(self.data, current)
        current_path = writer.note_path(self.data, current)
        older = row(name="Example Summit and Conference 2027", source="open-tech-cfps")
        writer.upsert(self.data, older, deduplicate=False, allow_source_takeover=True)
        older_path = writer.note_path(self.data, older)
        self.curate(older_path)

        result = reconcile_rows(self.data, {"developers.events": [current]}, today="2026-11-20")
        self.assertIn(older_path.relative_to(self.data).as_posix(), result.superseded)
        self.archive(result)
        fm, body = writer._read_frontmatter(current_path)
        self.assertTrue(fm["shortlist"])
        self.assertIn("Bring the demo.", body)
        self.assertFalse(older_path.exists())

    def test_two_current_revisions_choose_the_later_deadline(self) -> None:
        earlier = row(cfp_close="2026-12-01")
        later = row(cfp_close="2026-12-15")
        for value in (earlier, later):
            writer.upsert(self.data, value, deduplicate=False, allow_source_takeover=True)
        earlier_path = writer.note_path(self.data, earlier)
        later_path = writer.note_path(self.data, later)

        result = reconcile_rows(
            self.data, {"developers.events": [earlier, later]}, today="2026-12-01"
        )
        self.assertEqual(
            result.produced, {later_path.relative_to(self.data).as_posix()}
        )
        self.archive(result)
        self.assertTrue(later_path.is_file())
        self.assertFalse(earlier_path.exists())

    def test_same_properties_still_write_a_missing_canonical_target(self) -> None:
        current = row()
        writer.upsert(self.data, current)
        canonical = writer.note_path(self.data, current)
        legacy = canonical.with_name("legacy-name.md")
        canonical.rename(legacy)

        result = reconcile_rows(self.data, {"developers.events": [current]})
        self.assertTrue(canonical.is_file())
        self.assertIn(canonical.relative_to(self.data).as_posix(), result.produced)
        self.assertIn(legacy.relative_to(self.data).as_posix(), result.superseded)
        self.archive(result)
        self.assertTrue(canonical.is_file())
        self.assertFalse(legacy.exists())

    def test_sticky_allowed_event_type_survives_deadline_change(self) -> None:
        original = row(name="Community Meetup 2027", event_type="conference")
        writer.upsert(self.data, original)
        current = row(name="Community Meetup 2027", cfp_close="2026-12-15")
        result = reconcile_rows(self.data, {"developers.events": [current]})
        path = writer.note_path(self.data, current)
        self.assertTrue(path.is_file())
        fm, _ = writer._read_frontmatter(path)
        self.assertEqual(fm["event_type"], "conference")

    def test_unarchived_predecessor_does_not_overwrite_live_edits(self) -> None:
        original = row()
        writer.upsert(self.data, original, today="2026-11-01T00:00:00")
        self.curate(writer.note_path(self.data, original))
        current = row(cfp_close="2026-12-15")
        reconcile_rows(self.data, {"developers.events": [current]}, today="2026-12-01T00:00:00")
        canonical = writer.note_path(self.data, current)
        text = canonical.read_text(encoding="utf-8")
        self.assertIn("replaces:", text)
        text = text.replace("priority: high", "live_edit: keep-me")
        text = text.replace("shortlist: true", "shortlist: false")
        text = text.replace("dismissed: true", "dismissed: false")
        text = text.replace('submissions: ["[[My talk]]"]', "submissions: []")
        canonical.write_text(text.replace("Bring the demo.", "Live target edit."), encoding="utf-8")

        second = reconcile_rows(self.data, {"developers.events": [current]}, today="2026-12-02")
        fm, body = writer._read_frontmatter(canonical)
        self.assertEqual(fm["live_edit"], "keep-me")
        self.assertFalse(fm["shortlist"])
        self.assertFalse(fm["dismissed"])
        self.assertEqual(fm["submissions"], [])
        self.assertNotIn("priority", fm)
        self.assertEqual(writer._as_str(fm["updated"]), "2026-12-01T00:00:00")
        self.assertIn("Live target edit.", body)
        self.assertNotIn("Bring the demo.", body)
        self.assertEqual(second.summaries["developers.events"]["new"], 0)
        before = canonical.read_bytes()
        reconcile_rows(self.data, {"developers.events": [current]}, today="2026-12-03")
        self.assertEqual(canonical.read_bytes(), before)

    def test_standalone_superseded_manifest_retires_curated_predecessor(self) -> None:
        original = row()
        writer.upsert(self.data, original)
        old_path = writer.note_path(self.data, original)
        self.curate(old_path)
        current = row(cfp_close="2026-12-15")
        produced_path = self.data.parent / "produced.json"
        superseded_path = self.data.parent / "superseded.json"

        counts = writer.emit_rows(
            self.data,
            [current],
            manifest=produced_path,
            superseded_manifest=superseded_path,
            today="2026-12-01",
        )
        self.assertEqual(counts["found"], 1)
        new_path = writer.note_path(self.data, current)
        self.assertTrue(old_path.is_file())
        produced = archiver.load_manifests([produced_path])
        superseded = archiver.load_manifests([superseded_path])
        self.assertEqual(produced, {new_path.relative_to(self.data).as_posix()})
        self.assertEqual(superseded, {old_path.relative_to(self.data).as_posix()})

        archiver.archive_orphans(
            self.data, self.archive_dir, produced, superseded=superseded
        )
        fm, body = writer._read_frontmatter(new_path)
        self.assertTrue(fm["shortlist"])
        self.assertIn("Bring the demo.", body)
        self.assertIn("replaces", fm)
        self.assertFalse(old_path.exists())

    def test_invalid_preferred_target_falls_back_to_valid_source_note(self) -> None:
        import contextlib
        import io

        preferred = row()
        writer.upsert(self.data, preferred)
        preferred_path = writer.note_path(self.data, preferred)
        preferred_path.write_text("---\ninvalid: [yaml\n---\nbody\n", encoding="utf-8")
        alternative = row(name="Example Summit and Conference 2027", source="open-tech-cfps")
        writer.upsert(self.data, alternative, deduplicate=False, allow_source_takeover=True)
        alternative_path = writer.note_path(self.data, alternative)
        before = alternative_path.read_bytes()

        with contextlib.redirect_stderr(io.StringIO()):
            result = reconcile_rows(
                self.data,
                {
                    "developers.events": [preferred],
                    "open-tech-cfps": [alternative],
                },
            )
        self.assertEqual(
            result.produced, {alternative_path.relative_to(self.data).as_posix()}
        )
        self.archive(result)
        self.assertEqual(alternative_path.read_bytes(), before)
        self.assertTrue(preferred_path.is_file())

    def test_resolved_allowed_type_survives_curated_excluded_predecessor(self) -> None:
        allowed = row(name="Community Meetup 2027", event_type="conference")
        writer.upsert(self.data, allowed)
        excluded = row(
            name="Community Meetup and Conference 2027",
            event_type="conference",
        )
        writer.upsert(self.data, excluded, deduplicate=False, allow_source_takeover=True)
        excluded_path = writer.note_path(self.data, excluded)
        excluded_path.write_text(
            excluded_path.read_text(encoding="utf-8").replace(
                "event_type: conference", "event_type: meetup"
            ),
            encoding="utf-8",
        )
        self.curate(excluded_path)
        current = row(name="Community Meetup 2027", cfp_close="2026-12-15")

        result = reconcile_rows(self.data, {"developers.events": [current]})
        target = writer.note_path(self.data, current)
        self.assertTrue(target.is_file())
        self.assertIn(target.relative_to(self.data).as_posix(), result.produced)
        fm, _ = writer._read_frontmatter(target)
        self.assertEqual(fm["event_type"], "conference")

    def test_second_path_migration_uses_live_descendant_not_old_ancestor(self) -> None:
        original = row(cfp_close="2026-12-01")
        writer.upsert(self.data, original, today="2026-11-01T00:00:00")
        first_path = writer.note_path(self.data, original)
        self.curate(first_path)
        intermediate = row(cfp_close="2026-12-15")
        reconcile_rows(
            self.data, {"developers.events": [intermediate]}, today="2026-12-01"
        )
        second_path = writer.note_path(self.data, intermediate)
        text = second_path.read_text(encoding="utf-8")
        self.assertIn("replaces:", text)
        text = text.replace("priority: high", "live_edit: keep-me")
        text = text.replace("shortlist: true", "shortlist: false")
        text = text.replace("dismissed: true", "dismissed: false")
        text = text.replace('submissions: ["[[My talk]]"]', "submissions: []")
        second_path.write_text(
            text.replace("Bring the demo.", "Current intermediate edit."),
            encoding="utf-8",
        )

        current = row(cfp_close="2026-12-31")
        result = reconcile_rows(
            self.data, {"developers.events": [current]}, today="2026-12-02"
        )
        target = writer.note_path(self.data, current)
        fm, body = writer._read_frontmatter(target)
        self.assertEqual(fm["live_edit"], "keep-me")
        self.assertFalse(fm["shortlist"])
        self.assertFalse(fm["dismissed"])
        self.assertEqual(fm["submissions"], [])
        self.assertNotIn("priority", fm)
        self.assertEqual(writer._as_str(fm["created"]), "2026-11-01T00:00:00")
        self.assertIn("Current intermediate edit.", body)
        self.assertNotIn("Bring the demo.", body)
        self.assertEqual(
            set(fm["replaces"]),
            {
                first_path.relative_to(self.data).as_posix(),
                second_path.relative_to(self.data).as_posix(),
            },
        )
        self.assertIn(first_path.relative_to(self.data).as_posix(), result.superseded)
        self.assertIn(second_path.relative_to(self.data).as_posix(), result.superseded)

    def test_reversion_uses_live_descendant_and_never_replaces_itself(self) -> None:
        original = row(name="Community Meetup 2027", event_type="conference")
        writer.upsert(self.data, original)
        first_path = writer.note_path(self.data, original)
        text = first_path.read_text(encoding="utf-8")
        first_path.write_text(
            text.replace("shortlist: false", "shortlist: true").replace(
                "_Add notes here._", "Original ancestor notes."
            ),
            encoding="utf-8",
        )
        intermediate = row(name="Community Meetup 2027", cfp_close="2026-12-15")
        reconcile_rows(self.data, {"developers.events": [intermediate]})
        second_path = writer.note_path(self.data, intermediate)
        second_path.write_text(
            second_path.read_text(encoding="utf-8")
            .replace("shortlist: true", "shortlist: false")
            .replace("Original ancestor notes.", "Live descendant edit."),
            encoding="utf-8",
        )

        # Revert to the original filename, then move forward to a third path.
        reconcile_rows(self.data, {"developers.events": [original]})
        reverted_fm, _ = writer._read_frontmatter(first_path)
        self.assertNotIn(
            first_path.relative_to(self.data).as_posix(),
            reverted_fm.get("replaces", []),
        )
        final = row(name="Community Meetup 2027", cfp_close="2026-12-31")
        reconcile_rows(self.data, {"developers.events": [final]})
        final_path = writer.note_path(self.data, final)
        fm, body = writer._read_frontmatter(final_path)
        self.assertEqual(fm["event_type"], "conference")
        self.assertFalse(fm["shortlist"])
        self.assertIn("Live descendant edit.", body)
        self.assertNotIn("Original ancestor notes.", body)
        self.assertNotIn(final_path.relative_to(self.data).as_posix(), fm["replaces"])
        self.assertIn("replaces", fm)

    def test_fallback_does_not_supersede_paused_url_less_manual_note(self) -> None:
        manual = row(cfp_url="", source="manual")
        writer.upsert(self.data, manual)
        manual_path = writer.note_path(self.data, manual)
        self.curate(manual_path)
        before = manual_path.read_bytes()
        alternative = row(
            name="Example Summit and Conference 2027", source="open-tech-cfps"
        )

        result = reconcile_rows(
            self.data,
            {"developers.events": [row()], "open-tech-cfps": [alternative]},
            skipped_sources={"manual"},
        )
        self.assertNotIn(
            manual_path.relative_to(self.data).as_posix(), result.superseded
        )
        self.archive(result)
        self.assertTrue(manual_path.is_file())
        self.assertEqual(manual_path.read_bytes(), before)

    def test_second_reconciliation_is_unchanged(self) -> None:
        current = row()
        first = reconcile_rows(self.data, {"developers.events": [current]}, today="2026-11-01T00:00:00")
        path = writer.note_path(self.data, current)
        mtime = path.stat().st_mtime_ns
        self.archive(first)

        second = reconcile_rows(self.data, {"developers.events": [current]}, today="2026-11-02")
        self.assertEqual(second.summaries["developers.events"]["unchanged"], 1)
        self.assertEqual(path.stat().st_mtime_ns, mtime)
        self.assertFalse(second.superseded)

    def test_one_curated_duplicate_loser_converges(self) -> None:
        old = row(name="Example Summit 2027")
        writer.upsert(self.data, old)
        old_path = writer.note_path(self.data, old)
        self.curate(old_path)

        # A differently named note already exists from a less descriptive feed.
        other = row(name="Example Summit and Conference 2027", source="open-tech-cfps")
        writer.upsert(
            self.data, other, deduplicate=False, allow_source_takeover=True
        )
        other_path = writer.note_path(self.data, other)

        result = reconcile_rows(self.data, {"developers.events": [old]}, today="2026-11-20")
        self.archive(result)
        self.assertTrue(old_path.is_file())
        self.assertFalse(other_path.exists())
        self.assertFalse(writer.note_path(self.data, other).exists())

    def test_curated_value_migrates_from_a_duplicate_loser(self) -> None:
        # A curated note at the old path plus a plain note already at the current
        # row's path: the curated value must move to the live target instead of
        # being replaced by the target's source value.
        loser = row(name="Example Summit and Conference 2027")
        writer.upsert(self.data, loser)
        loser_path = writer.note_path(self.data, loser)
        text = loser_path.read_text(encoding="utf-8")
        text = text.replace(
            "location: London, UK",
            "curated_fields: [location]\nlocation: New York, USA",
        )
        loser_path.write_text(text, encoding="utf-8")

        current = row(location="Barcelona, Spain")
        writer.upsert(self.data, current, deduplicate=False)
        target = writer.note_path(self.data, current)

        result = reconcile_rows(self.data, {"developers.events": [row()]}, today="2026-11-20")

        fm, _ = writer._read_frontmatter(target)
        self.assertEqual(fm["location"], "New York, USA")
        self.assertEqual(fm["curated_fields"], ["location"])
        self.assertIn(loser_path.relative_to(self.data).as_posix(), fm["replaces"])
        self.archive(result)
        self.assertFalse(loser_path.exists())


class ExistingCuratedTest(unittest.TestCase):
    """``## Conflict`` is writer-owned, so it must not count as user curation."""

    CONFLICT = "\n## Conflict\n\n- location: kept `New York, USA`, source says `—`\n\n"

    def note(self, body: str, fm=None) -> Existing:
        return Existing(
            Path("data/2026/x.md"),
            "https://sessionize.test/example-2027",
            "developers.events",
            "Example Summit 2027",
            {"type": "cfp", "conflict": True} if fm is None else fm,
            body,
        )

    def test_conflict_only_note_is_not_curated(self) -> None:
        self.assertFalse(self.note(self.CONFLICT + "## Notes\n\n_Add notes here._\n").curated)

    def test_conflict_section_does_not_mask_body_notes(self) -> None:
        self.assertTrue(self.note(self.CONFLICT + "## Notes\n\nBring the demo.\n").curated)

    def test_curated_fields_still_count_as_curation(self) -> None:
        fm = {"type": "cfp", "conflict": True, "curated_fields": ["location"]}
        self.assertTrue(self.note(self.CONFLICT + "## Notes\n\n", fm=fm).curated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
