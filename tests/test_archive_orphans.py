#!/usr/bin/env python3
"""Tests for src/archive-orphans.py — moving notes no source produces any more.

Run from the project folder:

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


arch = load_module(ROOT / "src" / "archive-orphans.py", "arch")


class ArchiveTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data = Path(self._tmp.name) / "data"
        self.archive = Path(self._tmp.name) / "archived"
        self.data.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def note(self, rel: str, text: str = "---\ntype: cfp\nname: X\n---\n\n## Notes\n\n") -> str:
        p = self.data / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return rel


class TestFindOrphans(ArchiveTestCase):
    def test_orphans_are_on_disk_minus_produced(self) -> None:
        self.note("2026/a.md")
        self.note("2026/b.md")
        self.note("2027/c.md")
        orphans = arch.find_orphans(self.data, {"2026/a.md", "2027/c.md"})
        self.assertEqual(orphans, ["2026/b.md"])

    def test_nothing_produced_means_everything_is_an_orphan(self) -> None:
        self.note("2026/a.md")
        self.note("2027/b.md")
        self.assertEqual(arch.find_orphans(self.data, set()), ["2026/a.md", "2027/b.md"])

    def test_skip_source_leaves_a_deliberately_skipped_source_alone(self) -> None:
        # A source disabled in config.INPUT_SOURCES was never asked to produce its
        # notes this run; those notes are un-produced by choice, not dropped
        # upstream, so they must stay in data/.
        self.note("2026/a.md", "---\ntype: cfp\nsource: open-tech-cfps\n---\n\n## Notes\n")
        self.note("2026/b.md", "---\ntype: cfp\nsource: developers.events\n---\n\n## Notes\n")
        orphans = arch.find_orphans(self.data, set(), skip_sources=["open-tech-cfps"])
        self.assertEqual(orphans, ["2026/b.md"])

    def test_skip_source_default_changes_nothing(self) -> None:
        self.note("2026/a.md")
        self.assertEqual(arch.find_orphans(self.data, set()), ["2026/a.md"])
        self.assertEqual(arch.find_orphans(self.data, set(), skip_sources=[]), ["2026/a.md"])

    def test_skip_source_ignores_empty_and_unknown_values(self) -> None:
        self.note("2026/a.md", "---\ntype: cfp\nsource: manual\n---\n\n## Notes\n")
        self.assertEqual(arch.find_orphans(self.data, set(), skip_sources=["", None]), ["2026/a.md"])
        self.assertEqual(arch.find_orphans(self.data, set(), skip_sources=["manual"]), [])

    def test_archive_orphans_moves_only_unskipped_notes(self) -> None:
        self.note("2026/a.md", "---\ntype: cfp\nsource: open-tech-cfps\n---\n\n## Notes\n")
        self.note("2026/b.md", "---\ntype: cfp\nsource: manual\n---\n\n## Notes\n")
        moved = arch.archive_orphans(self.data, self.archive, set(), skip_sources=["open-tech-cfps"])
        self.assertEqual(moved, ["2026/b.md"])
        self.assertTrue((self.data / "2026/a.md").is_file())
        self.assertFalse((self.data / "2026/b.md").is_file())
        self.assertTrue((self.archive / "2026/b.md").is_file())

    def test_non_cfp_note_is_left_alone(self) -> None:
        self.note("2026/a.md")
        self.note("2026/readme.md", "# just a note\n\nno frontmatter\n")
        self.note("2026/other.md", "---\ntype: project\nname: X\n---\n")
        self.assertEqual(arch.find_orphans(self.data, set()), ["2026/a.md"])


class TestManualChanges(ArchiveTestCase):
    def test_user_curation_is_not_archived(self) -> None:
        notes = {
            "2026/shortlisted.md": "---\ntype: cfp\nshortlist: true\n---\n\n## Notes\n",
            "2026/submitted.md": '---\ntype: cfp\nsubmissions: ["[[My talk]]"]\n---\n\n## Notes\n',
            "2026/body-notes.md": "---\ntype: cfp\n---\n\n## Notes\n\nBring the demo.\n",
            "2026/custom-field.md": "---\ntype: cfp\npriority: high\n---\n\n## Notes\n",
        }
        for rel, text in notes.items():
            self.note(rel, text)

        moved = arch.archive_orphans(self.data, self.archive, set())

        self.assertEqual(moved, [])
        for rel in notes:
            self.assertTrue((self.data / rel).is_file())
            self.assertFalse((self.archive / rel).exists())

    def test_default_curation_values_do_not_block_archiving(self) -> None:
        self.note(
            "2026/untouched.md",
            "---\ntype: cfp\nshortlist: false\ndismissed: false\n"
            "submissions: []\n---\n\n## Notes\n\n_Add notes here._\n",
        )
        self.assertEqual(arch.find_orphans(self.data, set()), ["2026/untouched.md"])

    def test_dismissed_note_can_be_archived(self) -> None:
        self.note("2026/dismissed.md", "---\ntype: cfp\ndismissed: true\n---\n\n## Notes\n")
        moved = arch.archive_orphans(self.data, self.archive, set())
        self.assertEqual(moved, ["2026/dismissed.md"])
        self.assertTrue((self.archive / "2026/dismissed.md").is_file())

    def test_registry_tier_alone_does_not_block_archiving(self) -> None:
        self.note("2026/tiered.md", "---\ntype: cfp\ntier: 1\n---\n\n## Notes\n")
        self.assertEqual(arch.find_orphans(self.data, set()), ["2026/tiered.md"])


class TestArchiveOrphans(ArchiveTestCase):
    def test_moves_orphan_and_leaves_produced(self) -> None:
        self.note("2026/keep.md")
        self.note("2026/drop.md", "---\ntype: cfp\nname: Drop\n---\n\n## Notes\n\n")

        moved = arch.archive_orphans(self.data, self.archive, {"2026/keep.md"})

        self.assertEqual(moved, ["2026/drop.md"])
        self.assertTrue((self.data / "2026/keep.md").is_file())
        self.assertFalse((self.data / "2026/drop.md").exists())
        dst = self.archive / "2026/drop.md"
        self.assertTrue(dst.is_file())

    def test_move_is_byte_identical_no_property_added(self) -> None:
        text = "---\ntype: cfp\nname: Drop\n---\n\n## Notes\n\n_Add notes here._\n"
        self.note("2026/drop.md", text)
        arch.archive_orphans(self.data, self.archive, set())
        moved_text = (self.archive / "2026/drop.md").read_text(encoding="utf-8")
        self.assertEqual(moved_text, text)
        self.assertNotIn("archived", moved_text)

    def test_preserves_year_layout(self) -> None:
        self.note("2027/deep/note.md")
        arch.archive_orphans(self.data, self.archive, set())
        self.assertTrue((self.archive / "2027/deep/note.md").is_file())

    def test_dry_run_moves_nothing(self) -> None:
        self.note("2026/drop.md")
        moved = arch.archive_orphans(self.data, self.archive, set(), dry_run=True)
        self.assertEqual(moved, ["2026/drop.md"])
        self.assertTrue((self.data / "2026/drop.md").is_file())
        self.assertFalse(self.archive.exists())


class TestLoadManifests(ArchiveTestCase):
    def test_union_of_multiple_manifests(self) -> None:
        a = Path(self._tmp.name) / "a.json"
        b = Path(self._tmp.name) / "b.json"
        a.write_text(json.dumps(["2026/x.md", "2026/shared.md"]), encoding="utf-8")
        b.write_text(json.dumps(["2026/shared.md", "2027/y.md"]), encoding="utf-8")
        self.assertEqual(
            arch.load_manifests([a, b]),
            {"2026/x.md", "2026/shared.md", "2027/y.md"},
        )

    def test_missing_manifest_ignored(self) -> None:
        self.assertEqual(arch.load_manifests([Path(self._tmp.name) / "nope.json"]), set())


class TestNotePathAndManifest(unittest.TestCase):
    def test_note_path_and_write_manifest(self) -> None:
        from cfp_writer import note_path, write_manifest

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            row = {"name": "PyTexas 2027", "cfp_close": "2027-01-15", "event_date": "2027-04-16"}
            p = note_path(data, row)
            self.assertEqual(p, data / "2027" / "2027-01-15_pytexas-2027.md")
            mf = data / "manifest.json"
            write_manifest(mf, [p], data)
            self.assertEqual(json.loads(mf.read_text(encoding="utf-8")), ["2027/2027-01-15_pytexas-2027.md"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
