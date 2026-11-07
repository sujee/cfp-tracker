#!/usr/bin/env python3
"""Tests for src/cfp_writer.py — change detection and field preservation.

Run from the project folder:

    python3 -m unittest discover -s tests -v

These cover the contract that a refresh only rewrites a note when the
source-derived frontmatter properties actually change, and that user-owned
content (body notes, ``shortlist``/``submissions``, extra frontmatter) survives.
"""
from __future__ import annotations

import contextlib
import datetime
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer as cw  # noqa: E402


def sample_row(**overrides) -> dict:
    row = {
        "name": "Power Platform Days Barcelona 2026",
        "event_date": "2026-12-19",
        "location": "Online",
        "country": "Online",
        "cfp_close": "2026-11-30",
        "topics": ["microsoft", "cloud", "automation"],
        "event_url": "https://powerplatform.com",
        "cfp_url": "https://sessionize.com/power-platform-days-barcelona-2026/",
        "source": "developers.events",
    }
    row.update(overrides)
    return row


class WriterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data = Path(self._tmp.name)
        cw.reset_cfp_url_index()  # each test is a fresh data dir
        self.row = sample_row()
        self.path = (
            self.data / "2026" / "2026-11-30_power-platform-days-barcelona-2026.md"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers ----------------------------------------------------------
    def write_initial(self) -> str:
        status = cw.upsert(self.data, self.row)
        self.assertEqual(status, "new")
        return self.path.read_text(encoding="utf-8")

    def edit(self, old: str, new: str) -> None:
        text = self.path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        self.path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def frontmatter(self) -> dict:
        """Parsed frontmatter (typed values, straight from the YAML reader)."""
        fm, _ = cw._read_frontmatter(self.path)
        return fm


class TestNewAndUnchanged(WriterTestCase):
    def test_first_write_is_new_and_creates_year_folder(self) -> None:
        status = cw.upsert(self.data, self.row)
        self.assertEqual(status, "new")
        self.assertTrue(self.path.is_file())
        self.assertEqual(self.path.parent.name, "2026")

    def test_rerun_with_same_data_is_unchanged_and_untouched(self) -> None:
        self.write_initial()
        before = self.path.read_bytes()
        mtime = self.path.stat().st_mtime_ns

        status = cw.upsert(self.data, self.row)

        self.assertEqual(status, "unchanged")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.path.stat().st_mtime_ns, mtime)  # no write at all

    def test_source_property_change_is_updated(self) -> None:
        self.write_initial()
        status = cw.upsert(self.data, sample_row(location="Barcelona, Spain"))
        self.assertEqual(status, "updated")
        self.assertEqual(self.frontmatter()["location"], "Barcelona, Spain")

    def test_quoting_difference_alone_is_unchanged(self) -> None:
        # SEMANTIC compare: re-quoting a value must not force a rewrite.
        self.write_initial()
        self.edit("location: Online", 'location: "Online"')
        before = self.path.read_bytes()
        self.assertEqual(cw.upsert(self.data, self.row), "unchanged")
        self.assertEqual(self.path.read_bytes(), before)

    def test_topics_difference_is_updated(self) -> None:
        self.write_initial()
        status = cw.upsert(self.data, sample_row(topics=["microsoft", "cloud", "ai"]))
        self.assertEqual(status, "updated")
        self.assertEqual(self.frontmatter()["topics"], ["microsoft", "cloud", "ai"])

    def test_existing_file_without_frontmatter_is_updated(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("just a body, no frontmatter\n", encoding="utf-8")
        status = cw.upsert(self.data, self.row)
        self.assertEqual(status, "updated")
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("type: cfp", text)


class TestCreatedUpdated(WriterTestCase):
    """``created``/``updated`` are pipeline stamps written on every note.

    ``created`` is sticky (set at note birth, preserved across refreshes);
    ``updated`` advances to the run date only when a source change rewrites
    the note. A stamp back-fill (missing/garbled) mirrors ``created`` instead
    of counting as an update. Neither is part of the source-prop compare, so a
    no-op refresh stays byte-for-byte untouched.
    """

    def test_stamps_are_writer_owned_keys(self) -> None:
        self.assertIn("created", cw.KNOWN_FM_KEYS)
        self.assertNotIn("created", cw.SOURCE_SCALAR_FIELDS)
        self.assertNotIn("created", cw.LIST_FIELDS)

    def test_new_note_gets_today_for_both_stamps(self) -> None:
        self.assertEqual(cw.upsert(self.data, self.row, today="2026-11-06"), "new")
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2026, 11, 6))
        self.assertEqual(fm["updated"], datetime.date(2026, 11, 6))

    def test_noop_refresh_preserves_stamps_and_touches_nothing(self) -> None:
        cw.upsert(self.data, self.row, today="2026-11-06")
        before = self.path.read_bytes()
        mtime = self.path.stat().st_mtime_ns

        self.assertEqual(cw.upsert(self.data, self.row, today="2026-11-07"), "unchanged")

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.path.stat().st_mtime_ns, mtime)
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2026, 11, 6))
        self.assertEqual(fm["updated"], datetime.date(2026, 11, 6))

    def test_source_change_bumps_updated_but_preserves_created(self) -> None:
        cw.upsert(self.data, self.row, today="2026-11-06")
        self.assertEqual(
            cw.upsert(self.data, sample_row(location="Barcelona, Spain"), today="2026-11-09"),
            "updated",
        )
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2026, 11, 6))
        self.assertEqual(fm["updated"], datetime.date(2026, 11, 9))

    def test_note_missing_stamps_is_backfilled_on_refresh(self) -> None:
        # A note created before the stamps existed: props match, so the only
        # reason to rewrite is the missing stamp back-fill.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "---\ntype: cfp\nname: Power Platform Days Barcelona 2026\n"
            "event_date: 2026-12-19\nlocation: Online\ncountry: Online\n"
            "cfp_close: 2026-11-30\ntopics: [microsoft, cloud, automation]\n"
            "event_url: https://powerplatform.com\n"
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/\n"
            "source: developers.events\nshortlist: false\nsubmissions: []\n---\n\n"
            "## Notes\n\n_Add notes here._\n",
            encoding="utf-8",
        )
        self.assertEqual(cw.upsert(self.data, self.row, today="2026-11-06"), "updated")
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2026, 11, 6))
        self.assertEqual(fm["updated"], datetime.date(2026, 11, 6))

    def test_garbled_stamp_backfills_to_created(self) -> None:
        cw.upsert(self.data, self.row, today="2026-11-06")
        self.edit("updated: 2026-11-06", 'updated: "soon"')
        # Props match, so this is a stamp back-fill, not a data update:
        # ``updated`` mirrors ``created`` instead of jumping to the run date.
        self.assertEqual(cw.upsert(self.data, self.row, today="2026-11-09"), "updated")
        self.assertEqual(self.frontmatter()["updated"], datetime.date(2026, 11, 6))

    def test_missing_updated_backfills_to_created(self) -> None:
        # An existing note that already carries ``created`` gets ``updated``
        # equal to it, not to today's date.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "---\ntype: cfp\nname: Power Platform Days Barcelona 2026\n"
            "event_date: 2026-12-19\nlocation: Online\ncountry: Online\n"
            "cfp_close: 2026-11-30\ntopics: [microsoft, cloud, automation]\n"
            "event_url: https://powerplatform.com\n"
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/\n"
            "source: developers.events\nshortlist: false\nsubmissions: []\n"
            "created: 2025-03-04\n---\n\n## Notes\n\n_Add notes here._\n",
            encoding="utf-8",
        )
        self.assertEqual(cw.upsert(self.data, self.row, today="2026-11-09"), "updated")
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2025, 3, 4))
        self.assertEqual(fm["updated"], datetime.date(2025, 3, 4))

    def test_missing_created_backfills_to_updated(self) -> None:
        # The mirror case: a lone ``updated`` dates ``created``, so a back-fill
        # never produces created > updated.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "---\ntype: cfp\nname: Power Platform Days Barcelona 2026\n"
            "event_date: 2026-12-19\nlocation: Online\ncountry: Online\n"
            "cfp_close: 2026-11-30\ntopics: [microsoft, cloud, automation]\n"
            "event_url: https://powerplatform.com\n"
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/\n"
            "source: developers.events\nshortlist: false\nsubmissions: []\n"
            "updated: 2025-03-04\n---\n\n## Notes\n\n_Add notes here._\n",
            encoding="utf-8",
        )
        self.assertEqual(cw.upsert(self.data, self.row, today="2026-11-09"), "updated")
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2025, 3, 4))
        self.assertEqual(fm["updated"], datetime.date(2025, 3, 4))

    def test_user_stamps_do_not_force_rewrites(self) -> None:
        # Hand-maintained stamps are not compared: a note whose stamps differ
        # from today's date still reports unchanged.
        cw.upsert(self.data, self.row, today="2026-11-06")
        self.edit("created: 2026-11-06", "created: 2025-01-02")
        self.assertEqual(cw.upsert(self.data, self.row, today="2030-05-05"), "unchanged")
        self.assertEqual(self.frontmatter()["created"], datetime.date(2025, 1, 2))

    def test_normalize_backfills_missing_stamps_and_is_idempotent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "---\ntype: cfp\nname: Power Platform Days Barcelona 2026\n"
            "event_date: 2026-12-19\nlocation: Online\ncountry: Online\n"
            "cfp_close: 2026-11-30\ntopics: [microsoft, cloud, automation]\n"
            "event_url: https://powerplatform.com\n"
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/\n"
            "source: developers.events\nshortlist: false\nsubmissions: []\n---\n\n"
            "## Notes\n\n_Add notes here._\n",
            encoding="utf-8",
        )
        self.assertTrue(cw.normalize_file(self.path, today="2026-11-06"))
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2026, 11, 6))
        self.assertEqual(fm["updated"], datetime.date(2026, 11, 6))
        after = self.path.read_bytes()
        cw.normalize_file(self.path, today="2026-11-06")
        self.assertEqual(self.path.read_bytes(), after)  # idempotent: stamps kept

    def test_normalize_preserves_existing_stamps(self) -> None:
        cw.upsert(self.data, self.row, today="2026-11-06")
        self.edit("updated: 2026-11-06", "updated: 2026-11-07")
        self.assertTrue(cw.normalize_file(self.path, today="2026-11-20"))
        self.assertEqual(self.frontmatter()["updated"], datetime.date(2026, 11, 7))

    def test_normalize_mirrors_created_when_updated_is_missing(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "---\ntype: cfp\nname: Power Platform Days Barcelona 2026\n"
            "event_date: 2026-12-19\nlocation: Online\ncountry: Online\n"
            "cfp_close: 2026-11-30\ntopics: [microsoft, cloud, automation]\n"
            "event_url: https://powerplatform.com\n"
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/\n"
            "source: developers.events\nshortlist: false\nsubmissions: []\n"
            "created: 2025-03-04\n---\n\n## Notes\n\n_Add notes here._\n",
            encoding="utf-8",
        )
        self.assertTrue(cw.normalize_file(self.path, today="2026-11-09"))
        fm = self.frontmatter()
        self.assertEqual(fm["created"], datetime.date(2025, 3, 4))
        self.assertEqual(fm["updated"], datetime.date(2025, 3, 4))


class TestUserContentPreserved(WriterTestCase):
    def test_user_edits_do_not_trigger_a_rewrite(self) -> None:
        self.write_initial()
        self.edit("shortlist: false", "shortlist: true")
        self.edit("source: developers.events", "source: developers.events\npriority: high")
        self.edit("_Add notes here._", "My own notes about this CFP.")
        edited = self.path.read_bytes()

        status = cw.upsert(self.data, self.row)

        self.assertEqual(status, "unchanged")
        self.assertEqual(self.path.read_bytes(), edited)  # edits intact

    def test_extra_properties_survive_a_genuine_update(self) -> None:
        self.write_initial()
        extras = (
            "source: developers.events\n"
            "priority: high\n"
            "tags:\n"
            "  - speaking\n"
            "  - ai\n"
            "contact:\n"
            "  name: Sujee\n"
            "  slack: '@sujee'"
        )
        self.edit("source: developers.events", extras)

        status = cw.upsert(self.data, sample_row(location="Barcelona, Spain"))

        self.assertEqual(status, "updated")
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("location: Barcelona, Spain", text)
        self.assertIn("priority: high", text)
        self.assertIn("tags:\n  - speaking\n  - ai", text)
        self.assertIn("contact:\n  name: Sujee\n  slack: '@sujee'", text)

    def test_shortlist_submissions_and_notes_survive_update(self) -> None:
        self.write_initial()
        self.edit("shortlist: false", "shortlist: true")
        self.edit("submissions: []", 'submissions: ["[[my-talk]]"]')
        self.edit("_Add notes here._", "Hello notes.")

        cw.upsert(self.data, sample_row(location="Barcelona, Spain"))

        fm = self.frontmatter()
        self.assertTrue(fm["shortlist"])
        self.assertEqual(fm["submissions"], ["[[my-talk]]"])
        self.assertIn("Hello notes.", self.path.read_text(encoding="utf-8"))

    def test_known_key_is_not_treated_as_user_metadata(self) -> None:
        # A malformed known key must be regenerated, not preserved verbatim.
        self.write_initial()
        self.edit("location: Online", "location: WRONG")
        self.assertEqual(cw.upsert(self.data, self.row), "updated")
        self.assertEqual(self.frontmatter()["location"], "Online")

    def test_normalize_preserves_extras_and_is_idempotent(self) -> None:
        self.write_initial()
        self.edit("source: developers.events", "source: developers.events\npriority: high")
        self.assertTrue(cw.normalize_file(self.path))
        after_first = self.path.read_bytes()
        self.assertIn(b"priority: high", after_first)
        cw.normalize_file(self.path)
        self.assertEqual(self.path.read_bytes(), after_first)


class TestUserTags(WriterTestCase):
    """A hand-added ``tags`` property is user metadata: it must survive a refresh.

    ``topics`` is source-owned and gets regenerated (see ``TestNewAndUnchanged``),
    so ``tags`` is the key to reach for when you want personal tags that stick.
    It is not in :data:`cfp_writer.KNOWN_FM_KEYS`, so it is preserved verbatim.
    """

    def test_tags_is_not_a_writer_owned_key(self) -> None:
        self.assertNotIn("tags", cw.KNOWN_FM_KEYS)
        self.assertNotIn("tags", cw.SOURCE_SCALAR_FIELDS)
        self.assertNotIn("tags", cw.LIST_FIELDS)

    def test_added_tags_do_not_trigger_a_rewrite(self) -> None:
        self.write_initial()
        self.edit("submissions: []", "submissions: []\ntags: [ai, agents]")
        edited = self.path.read_bytes()

        status = cw.upsert(self.data, self.row)

        self.assertEqual(status, "unchanged")  # tags are not a source field
        self.assertEqual(self.path.read_bytes(), edited)

    def test_tags_survive_a_source_driven_rewrite(self) -> None:
        self.write_initial()
        self.edit("submissions: []", "submissions: []\ntags: [ai, agents]")

        status = cw.upsert(self.data, sample_row(location="Barcelona, Spain"))

        self.assertEqual(status, "updated")
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("location: Barcelona, Spain", text)  # source field updated
        self.assertIn("tags: [ai, agents]", text)          # user tags kept

    def test_block_form_tags_survive_a_rewrite_verbatim(self) -> None:
        self.write_initial()
        self.edit("submissions: []", "submissions: []\ntags:\n  - conference/ai\n  - speaking")

        cw.upsert(self.data, sample_row(location="Barcelona, Spain"))  # forces a rewrite

        text = self.path.read_text(encoding="utf-8")
        self.assertIn("tags:\n  - conference/ai\n  - speaking", text)
        self.assertEqual(
            cw._read_frontmatter(self.path)[0]["tags"], ["conference/ai", "speaking"]
        )

    def test_tags_survive_next_to_shortlist_and_notes(self) -> None:
        self.write_initial()
        self.edit("shortlist: false", "shortlist: true\ntags: [shortlist]")
        self.edit("_Add notes here._", "Worth submitting.")

        cw.upsert(self.data, sample_row(location="Barcelona, Spain"))

        fm = self.frontmatter()
        self.assertTrue(fm["shortlist"])
        self.assertEqual(fm["tags"], ["shortlist"])
        self.assertIn("Worth submitting.", self.path.read_text(encoding="utf-8"))

    def test_normalize_preserves_tags_and_is_idempotent(self) -> None:
        self.write_initial()
        self.edit("submissions: []", "submissions: []\ntags: [ai, agents]")

        self.assertTrue(cw.normalize_file(self.path))
        after_first = self.path.read_bytes()
        self.assertIn(b"tags: [ai, agents]", after_first)
        cw.normalize_file(self.path)
        self.assertEqual(self.path.read_bytes(), after_first)  # idempotent


class TestSourcePrecedence(WriterTestCase):
    """Shared slugs: a lower-priority source must not overwrite a higher one."""

    def test_lower_priority_source_does_not_overwrite(self) -> None:
        dev = sample_row(source="developers.events", location="London (UK)", country="UK")
        self.assertEqual(cw.upsert(self.data, dev), "new")

        confs = sample_row(source="confs.tech", location="London, U.K.", country="")
        self.assertEqual(cw.upsert(self.data, confs), "skipped")  # skipped, not overwritten

        fm = self.frontmatter()
        self.assertEqual(fm["source"], "developers.events")
        self.assertEqual(fm["location"], "London (UK)")
        self.assertEqual(fm["country"], "UK")

    def test_higher_priority_source_takes_over(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(source="confs.tech")), "new")
        self.assertEqual(cw.upsert(self.data, sample_row(source="developers.events")), "updated")
        self.assertEqual(self.frontmatter()["source"], "developers.events")

    def test_manual_beats_developers_events(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(source="developers.events")), "new")
        self.assertEqual(cw.upsert(self.data, sample_row(source="manual")), "updated")
        self.assertEqual(self.frontmatter()["source"], "manual")

    def test_unknown_source_ranks_lowest(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(source="developers.events")), "new")
        self.assertEqual(cw.upsert(self.data, sample_row(source="mystery.feed")), "skipped")
        self.assertEqual(self.frontmatter()["source"], "developers.events")

    def test_cfp_ninja_beats_confs_tech(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(source="confs.tech")), "new")
        self.assertEqual(cw.upsert(self.data, sample_row(source="cfp.ninja")), "updated")
        self.assertEqual(self.frontmatter()["source"], "cfp.ninja")

    def test_developers_events_beats_cfp_ninja(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(source="cfp.ninja")), "new")
        self.assertEqual(cw.upsert(self.data, sample_row(source="developers.events")), "updated")
        self.assertEqual(self.frontmatter()["source"], "developers.events")

    def test_same_source_still_compares_properties(self) -> None:
        self.write_initial()  # source: developers.events
        self.assertEqual(cw.upsert(self.data, sample_row(location="Barcelona, Spain")), "updated")


class TestCrossSourceDuplicateByCfpUrl(WriterTestCase):
    """One CFP, two names → two slugs → one note (match on ``cfp_url``).

    Feeds name the same edition differently ("SCaLE" vs "Southern California
    Linux Expo - SCaLE 24x"), so the same-slug priority rule never fires. The
    submission URL identifies the CFP, so the higher-priority source owns it and
    the other source skips.
    """

    def paths(self, *rows: dict) -> list[Path]:
        return [cw.note_path(self.data, r) for r in rows]

    def test_lower_priority_source_yields_to_a_different_slug(self) -> None:
        dev = sample_row(
            name="Southern California Linux Expo - SCaLE 24x",
            source="developers.events",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        confs = sample_row(
            name="SCaLE",
            source="confs.tech",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        self.assertEqual(cw.upsert(self.data, dev), "new")

        self.assertEqual(cw.upsert(self.data, confs), "skipped")

        dev_path, confs_path = self.paths(dev, confs)
        self.assertTrue(dev_path.is_file())
        self.assertFalse(confs_path.exists())  # never written; it will be archived

    def test_higher_priority_source_keeps_its_own_note(self) -> None:
        confs = sample_row(
            name="SCaLE",
            source="confs.tech",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        dev = sample_row(
            name="Southern California Linux Expo - SCaLE 24x",
            source="developers.events",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        self.assertEqual(cw.upsert(self.data, confs), "new")
        self.assertEqual(cw.upsert(self.data, dev), "new")

        dev_path, confs_path = self.paths(dev, confs)
        self.assertTrue(dev_path.is_file())
        self.assertTrue(confs_path.is_file())  # orphan, cleaned up by archive-orphans

    def test_existing_loser_note_is_skipped_not_called_current(self) -> None:
        # Regression: a loser note already on disk matches its own source, so the
        # "unchanged" short-circuit used to fire before the cross-url check and
        # the duplicate survived every run. Build both notes, then re-run the
        # lower-priority source as a fresh process (index rebuilt from disk).
        confs = sample_row(
            name="SCaLE",
            source="confs.tech",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        dev = sample_row(
            name="Southern California Linux Expo - SCaLE 24x",
            source="developers.events",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        cw.upsert(self.data, confs)   # writes the confs.tech note
        cw.upsert(self.data, dev)     # writes the developers.events note
        cw.reset_cfp_url_index()      # next call rebuilds the index from disk

        self.assertEqual(cw.upsert(self.data, confs), "skipped")

    def test_url_normalisation_ignores_case_and_trailing_slash(self) -> None:
        dev = sample_row(
            name="Power Platform Days",
            source="developers.events",
            cfp_url="https://Sessionize.com/PowerPlatform/",
        )
        confs = sample_row(
            name="Power Platform Days Barcelona",
            source="confs.tech",
            cfp_url="https://sessionize.com/powerplatform",
        )
        self.assertEqual(cw.upsert(self.data, dev), "new")
        self.assertEqual(cw.upsert(self.data, confs), "skipped")
        self.assertFalse(self.paths(confs)[0].exists())

    def test_shared_form_across_distinct_events_is_not_merged(self) -> None:
        # JS Poland / NG Poland / AI Poland share one Google form.
        url = "https://docs.google.com/forms/d/e/ai-poland/viewform"
        js = sample_row(name="JS Poland", cfp_url=url)
        ng = sample_row(name="NG Poland", cfp_url=url)
        self.assertEqual(cw.upsert(self.data, js), "new")
        self.assertEqual(cw.upsert(self.data, ng), "new")
        for p in self.paths(js, ng):
            self.assertTrue(p.is_file())

    def test_duplicate_notes_on_disk_leave_exactly_one(self) -> None:
        # Regression: two equal-priority notes for one URL must not each yield to
        # the other, or a re-run would archive both and lose the CFP.
        url = "https://app.advocu.com/events/devfest-malta"
        a = sample_row(name="DevFest Malta 2026", source="developers.events", cfp_url=url)
        b = sample_row(name="DevFest 2026 Malta", source="developers.events", cfp_url=url)
        for r in (a, b):  # seed both, as a buggy/earlier run would have left them
            p = cw.note_path(self.data, r)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                f"---\ntype: cfp\nname: {r['name']}\nsource: developers.events\n"
                f"cfp_url: {url}\nshortlist: false\nsubmissions: []\n---\n\n## Notes\n\n_Add notes here._\n",
                encoding="utf-8",
            )
        cw.reset_cfp_url_index()  # rebuild the index from what is on disk

        statuses = [cw.upsert(self.data, a), cw.upsert(self.data, b)]

        # Exactly one yields; the loser is left for archive-orphans to move (a
        # skip never deletes, so both files still exist here).
        self.assertEqual(statuses.count("skipped"), 1)

    def test_different_cfp_urls_are_not_merged(self) -> None:
        a = sample_row(name="Event A", cfp_url="https://example.com/a/cfp")
        b = sample_row(name="Event B", cfp_url="https://example.com/b/cfp")
        self.assertEqual(cw.upsert(self.data, a), "new")
        self.assertEqual(cw.upsert(self.data, b), "new")
        for p in self.paths(a, b):
            self.assertTrue(p.is_file())

    def test_empty_cfp_url_never_matches(self) -> None:
        a = sample_row(name="Event A", cfp_url="")
        b = sample_row(name="Event B", cfp_url="")
        self.assertEqual(cw.upsert(self.data, a), "new")
        self.assertEqual(cw.upsert(self.data, b), "new")
        for p in self.paths(a, b):
            self.assertTrue(p.is_file())

    def test_equal_priority_converges_to_one(self) -> None:
        # On a priority tie the lower path wins (a deterministic tie-break), so
        # once both notes are on disk exactly one row skips and the loser is left
        # for archive-orphans. (A first, fresh run can write both; the next run
        # converges.)
        first = sample_row(name="Event One", source="developers.events",
                           cfp_url="https://example.com/same")
        second = sample_row(name="Event One 2027", source="developers.events",
                            cfp_url="https://example.com/same")
        cw.upsert(self.data, first)   # first run writes both
        cw.upsert(self.data, second)
        cw.reset_cfp_url_index()      # next run rebuilds the index from disk

        statuses = [cw.upsert(self.data, first), cw.upsert(self.data, second)]

        self.assertEqual(statuses.count("skipped"), 1)

    def test_same_slug_still_uses_property_compare(self) -> None:
        # Same name → same path: the cross-url rule must not interfere.
        self.write_initial()
        self.assertEqual(self.frontmatter()["source"], "developers.events")


class TestNameCompatibility(unittest.TestCase):
    """The cfp_url match only merges notes whose names look like one conference."""

    def test_same_conference_different_spelling_merges(self) -> None:
        pairs = [
            ("SCaLE", "Southern California Linux Expo - SCaLE 24x"),
            ("Digital Crafts Day", "Digital Crafts Day 2027"),
            ("Umbracokalaset", "Umbracokalaset 2026"),
            ("DevFest Malta 2026", "DevFest 2026 Malta"),
            ("ConFoo Montreal", "Confoo 2027"),
            ("Webdevcon", "Webdevcon"),
        ]
        for a, b in pairs:
            with self.subTest(a=a, b=b):
                self.assertTrue(cw._names_compatible(a, b))

    def test_distinct_events_sharing_a_form_do_not_merge(self) -> None:
        # These all reuse one submission form across separate conferences.
        pairs = [
            ("JS Poland", "NG Poland"),
            ("Apidays Paris", "Apidays London"),
            ("Appdevcon", "Webdevcon"),
            ("Dutch AI Conference", "Webdevcon"),
            ("X-Ops Conference Madrid", "X-Ops Conference Dubai"),
            ("BC Waves Barcelona 2026", "BSides Copenhagen 2026"),
            ("HalfStack Phoenix", "HalfStack Vienna"),
        ]
        for a, b in pairs:
            with self.subTest(a=a, b=b):
                self.assertFalse(cw._names_compatible(a, b))

    def test_missing_name_is_never_compatible(self) -> None:
        self.assertFalse(cw._names_compatible("", "Anything"))
        self.assertFalse(cw._names_compatible("Anything", None))


class TestUpsertCounted(WriterTestCase):
    """``upsert_counted`` drives the per-source ``--manifest`` (orphan detection).

    A ``"skipped"`` row must not record its path as produced: it yielded to
    another note, and claiming the path would keep that loser alive forever.
    """

    def test_new_and_unchanged_rows_are_recorded_as_produced(self) -> None:
        counts: dict = {}
        produced: list = []
        self.assertEqual(
            cw.upsert_counted(self.data, self.row, counts, produced), "new"
        )
        self.assertEqual(
            cw.upsert_counted(self.data, self.row, counts, produced), "unchanged"
        )
        self.assertEqual(counts, {"new": 1, "unchanged": 1})
        self.assertEqual(produced, [self.path, self.path])

    def test_skipped_row_is_not_recorded_as_produced(self) -> None:
        dev = sample_row(
            name="Southern California Linux Expo - SCaLE 24x",
            source="developers.events",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        confs = sample_row(
            name="SCaLE",
            source="confs.tech",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        counts: dict = {}
        produced: list = []
        cw.upsert_counted(self.data, dev, counts, produced)
        self.assertEqual(cw.upsert_counted(self.data, confs, counts, produced), "skipped")

        self.assertEqual(counts, {"new": 1, "skipped": 1})
        self.assertEqual(produced, [cw.note_path(self.data, dev)])  # confs path absent


class TestBenefits(WriterTestCase):
    """``benefits`` is a writer-owned list, emitted only when the source has any."""

    def test_no_benefits_line_when_source_has_none(self) -> None:
        # Existing sources carry no benefits, so their notes stay byte-identical.
        text = self.write_initial()
        self.assertNotIn("benefits:", text)

    def test_benefits_written_when_present(self) -> None:
        row = sample_row(source="cfp.ninja", benefits=["travel", "hotel"])
        self.assertEqual(cw.upsert(self.data, row), "new")
        self.assertIn("benefits: [travel, hotel]", self.path.read_text(encoding="utf-8"))

    def test_benefits_change_triggers_an_update(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(source="cfp.ninja", benefits=["travel"])), "new")
        status = cw.upsert(self.data, sample_row(source="cfp.ninja", benefits=["travel", "honorarium"]))
        self.assertEqual(status, "updated")
        self.assertIn("benefits: [travel, honorarium]", self.path.read_text(encoding="utf-8"))

    def test_dropping_benefits_removes_the_line(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(source="cfp.ninja", benefits=["travel"])), "new")
        status = cw.upsert(self.data, sample_row(source="cfp.ninja"))
        self.assertEqual(status, "updated")
        self.assertNotIn("benefits:", self.path.read_text(encoding="utf-8"))

    def test_benefits_are_preserved_by_normalize(self) -> None:
        cw.upsert(self.data, sample_row(source="cfp.ninja", benefits=["travel"]))
        self.assertTrue(cw.normalize_file(self.path))
        after = self.path.read_bytes()
        self.assertIn(b"benefits: [travel]", after)
        cw.normalize_file(self.path)
        self.assertEqual(self.path.read_bytes(), after)  # idempotent


class TestLanguages(WriterTestCase):
    """``languages`` is a writer-owned list, emitted only when the source has any."""

    def test_no_languages_line_when_source_has_none(self) -> None:
        text = self.write_initial()
        self.assertNotIn("languages:", text)

    def test_languages_written_when_present(self) -> None:
        cw.upsert(self.data, sample_row(languages=["english"]))
        self.assertIn("languages: [english]", self.path.read_text(encoding="utf-8"))

    def test_languages_change_triggers_an_update(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(languages=["english"])), "new")
        self.assertEqual(cw.upsert(self.data, sample_row(languages=["english", "french"])), "updated")
        self.assertIn("languages: [english, french]", self.path.read_text(encoding="utf-8"))

    def test_dropping_languages_removes_the_line(self) -> None:
        self.assertEqual(cw.upsert(self.data, sample_row(languages=["english"])), "new")
        self.assertEqual(cw.upsert(self.data, sample_row()), "updated")
        self.assertNotIn("languages:", self.path.read_text(encoding="utf-8"))

    def test_languages_are_preserved_by_normalize(self) -> None:
        cw.upsert(self.data, sample_row(languages=["german"]))
        self.assertTrue(cw.normalize_file(self.path))
        after = self.path.read_bytes()
        self.assertIn(b"languages: [german]", after)
        cw.normalize_file(self.path)
        self.assertEqual(self.path.read_bytes(), after)  # idempotent


class TestBlockLists(WriterTestCase):
    """Block-form lists (what the Obsidian property editor writes) must read back.

    A block-form ``submissions`` was silently reset to ``[]`` on a rewrite before
    this: the reader only understood flow lists, so the items vanished.
    """

    def test_reader_parses_flow_and_block_lists(self) -> None:
        flow = "---\ntopics: [ai, agents]\n---\n\nb\n"
        block = "---\ntopics:\n  - ai\n  - agents\n---\n\nb\n"
        self.assertEqual(cw._read_frontmatter_text(flow)[0]["topics"], ["ai", "agents"])
        self.assertEqual(cw._read_frontmatter_text(block)[0]["topics"], ["ai", "agents"])

    def test_frontmatter_reader_keeps_block_items(self) -> None:
        text = '---\ntype: cfp\nsubmissions:\n  - "[[a]]"\n  - "[[b]]"\n---\n\nbody\n'
        fm, _ = cw._read_frontmatter_text(text)
        self.assertEqual(fm["submissions"], ["[[a]]", "[[b]]"])

    def test_block_submissions_survive_a_rewrite(self) -> None:
        self.write_initial()
        self.edit("submissions: []", 'submissions:\n  - "[[scale-a]]"\n  - "[[scale-b]]"')
        cw.upsert(self.data, sample_row(location="Barcelona, Spain"))  # forces a rewrite
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("[[scale-a]]", text)
        self.assertIn("[[scale-b]]", text)
        self.assertEqual(self.frontmatter()["submissions"], ["[[scale-a]]", "[[scale-b]]"])

    def test_block_topics_are_read_semantically(self) -> None:
        self.write_initial()
        self.edit(
            "topics: [microsoft, cloud, automation]",
            "topics:\n  - microsoft\n  - cloud\n  - automation",
        )
        self.assertEqual(cw.upsert(self.data, self.row), "unchanged")  # same values, block form


class TestCountryNormalization(WriterTestCase):
    """The writer canonicalises ``country`` before comparing and writing."""

    def test_full_name_is_written_short(self) -> None:
        cw.upsert(self.data, sample_row(country="United Kingdom"))
        self.assertEqual(self.frontmatter()["country"], "UK")

    def test_united_states_becomes_usa(self) -> None:
        cw.upsert(self.data, sample_row(country="United States"))
        self.assertEqual(self.frontmatter()["country"], "USA")

    def test_variant_then_canonical_is_unchanged(self) -> None:
        # Two sources disagreeing on the spelling must not cause a rewrite.
        self.assertEqual(cw.upsert(self.data, sample_row(country="United Kingdom")), "new")
        self.assertEqual(cw.upsert(self.data, sample_row(country="UK")), "unchanged")

    def test_unknown_country_is_left_alone(self) -> None:
        cw.upsert(self.data, sample_row(country="Peru"))
        self.assertEqual(self.frontmatter()["country"], "Peru")

    def test_normalize_file_canonicalises_existing_note(self) -> None:
        self.write_initial()
        self.edit("country: Online", "country: United States")
        self.assertTrue(cw.normalize_file(self.path))
        self.assertEqual(self.frontmatter()["country"], "USA")


class TestStripUtm(unittest.TestCase):
    """``strip_utm`` drops per-share Google Analytics tags without touching the rest."""

    def test_removes_a_full_set_of_utm_params(self) -> None:
        url = (
            "https://sessionize.com/swampup?utm_source=a&utm_medium=b"
            "&utm_campaign=c&utm_id=d&utm_term=e&utm_content=f"
        )
        self.assertEqual(cw.strip_utm(url), "https://sessionize.com/swampup")

    def test_keeps_non_utm_params_in_order(self) -> None:
        url = "https://x.com/cfp?utm_source=a&ref=nyc&utm_medium=b&page=2"
        self.assertEqual(cw.strip_utm(url), "https://x.com/cfp?ref=nyc&page=2")

    def test_only_utm_params_drops_the_question_mark(self) -> None:
        self.assertEqual(cw.strip_utm("https://x.com/cfp?utm_source=a"), "https://x.com/cfp")

    def test_url_without_a_query_is_unchanged(self) -> None:
        for url in ("https://x.com/cfp", "https://x.com/cfp#apply", ""):
            with self.subTest(url=url):
                self.assertEqual(cw.strip_utm(url), url)
        self.assertEqual(cw.strip_utm(None), "")

    def test_fragment_is_preserved(self) -> None:
        self.assertEqual(
            cw.strip_utm("https://x.com/cfp?utm_source=a&ref=b#form"),
            "https://x.com/cfp?ref=b#form",
        )

    def test_param_name_is_case_insensitive(self) -> None:
        self.assertEqual(cw.strip_utm("https://x.com/cfp?UTM_SOURCE=a"), "https://x.com/cfp")
        self.assertEqual(cw.strip_utm("https://x.com/cfp?Utm_Campaign=b"), "https://x.com/cfp")

    def test_only_params_starting_with_utm_are_dropped(self) -> None:
        url = "https://x.com/cfp?myutm_source=a&utmx=1&ref=utm_source"
        self.assertEqual(cw.strip_utm(url), url)  # key must start with utm_, value is irrelevant

    def test_no_re_encoding_of_kept_params(self) -> None:
        # A raw-string edit: percent-encoding and '+' in values survive verbatim.
        url = "https://x.com/cfp?utm_source=a&q=a%20b%2Cc&r=a+b"
        self.assertEqual(cw.strip_utm(url), "https://x.com/cfp?q=a%20b%2Cc&r=a+b")


class TestCfpUrlUtmStripping(WriterTestCase):
    """The writer strips UTM tags from ``cfp_url`` before comparing and writing."""

    def test_written_url_has_no_utm(self) -> None:
        row = sample_row(cfp_url="https://sessionize.com/x?utm_source=a&utm_medium=b")
        self.assertEqual(cw.upsert(self.data, row), "new")
        self.assertEqual(self.frontmatter()["cfp_url"], "https://sessionize.com/x")

    def test_existing_note_with_utm_is_cleaned_on_refresh(self) -> None:
        self.write_initial()
        self.edit(
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/",
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/?utm_source=news",
        )

        status = cw.upsert(self.data, self.row)

        self.assertEqual(status, "updated")
        self.assertEqual(
            self.frontmatter()["cfp_url"],
            "https://sessionize.com/power-platform-days-barcelona-2026/",
        )

    def test_utm_does_not_defeat_cross_source_url_match(self) -> None:
        # developers.events carries the CFP with a UTM tag, confs.tech without:
        # they must still match on the URL, so the lower-priority source skips.
        dev = sample_row(
            name="SCaLE",
            source="developers.events",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp?utm_source=dev-events",
        )
        confs = sample_row(
            name="Southern California Linux Expo - SCaLE 24x",
            source="confs.tech",
            cfp_url="https://www.socallinuxexpo.org/scale/24x/cfp",
        )
        self.assertEqual(cw.upsert(self.data, dev), "new")
        self.assertEqual(cw.upsert(self.data, confs), "skipped")

    def test_normalize_strips_utm_from_an_existing_note(self) -> None:
        self.write_initial()
        self.edit(
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/",
            "cfp_url: https://sessionize.com/power-platform-days-barcelona-2026/?utm_campaign=x",
        )
        self.assertTrue(cw.normalize_file(self.path))
        self.assertEqual(
            self.frontmatter()["cfp_url"],
            "https://sessionize.com/power-platform-days-barcelona-2026/",
        )


class TestEventUrlUtmStripping(WriterTestCase):
    """The writer strips UTM tags from ``event_url`` too."""

    def test_written_event_url_has_no_utm(self) -> None:
        row = sample_row(event_url="https://powerplatform.com/?utm_source=dev-events&utm_medium=link")
        self.assertEqual(cw.upsert(self.data, row), "new")
        self.assertEqual(self.frontmatter()["event_url"], "https://powerplatform.com/")

    def test_utm_in_event_url_is_a_no_op_on_rerun(self) -> None:
        # The row's tags are stripped before compare, so a tag never forces a rewrite.
        row = sample_row(event_url="https://powerplatform.com/?utm_source=a")
        self.assertEqual(cw.upsert(self.data, row), "new")
        self.assertEqual(cw.upsert(self.data, row), "unchanged")

    def test_existing_note_with_utm_is_cleaned_on_refresh(self) -> None:
        self.write_initial()
        self.edit(
            "event_url: https://powerplatform.com",
            "event_url: https://powerplatform.com?utm_campaign=spring",
        )

        self.assertEqual(cw.upsert(self.data, self.row), "updated")
        self.assertEqual(self.frontmatter()["event_url"], "https://powerplatform.com")

    def test_normalize_strips_utm_from_an_existing_note(self) -> None:
        self.write_initial()
        self.edit(
            "event_url: https://powerplatform.com",
            "event_url: https://powerplatform.com?utm_campaign=spring",
        )
        self.assertTrue(cw.normalize_file(self.path))
        self.assertEqual(self.frontmatter()["event_url"], "https://powerplatform.com")


class TestSubmissionsList(WriterTestCase):
    """``submissions`` replaced the scalar ``submission`` and is a list."""

    def test_new_note_has_an_empty_submissions_list(self) -> None:
        self.write_initial()
        self.assertIn("submissions: []", self.path.read_text(encoding="utf-8"))

    def test_submissions_list_round_trips_and_is_unchanged_on_rerun(self) -> None:
        self.write_initial()
        self.edit("submissions: []", 'submissions: ["[[a]]", "[[b-c]]"]')
        updated = sample_row(location="Barcelona, Spain")
        cw.upsert(self.data, updated)
        self.assertEqual(self.frontmatter()["submissions"], ["[[a]]", "[[b-c]]"])
        self.assertEqual(cw.upsert(self.data, updated), "unchanged")

    def test_legacy_scalar_submission_survives_a_source_update(self) -> None:
        # A pre-rename note must keep its value when the source rewrites the note.
        self.write_initial()
        self.edit("submissions: []", 'submission: "[[legacy]]"')
        cw.upsert(self.data, sample_row(location="Barcelona, Spain"))
        text = self.path.read_text(encoding="utf-8")
        self.assertIn('submissions: ["[[legacy]]"]', text)
        self.assertNotIn("submission:", text)

    def test_legacy_scalar_submission_migrates_on_normalize(self) -> None:
        self.write_initial()
        self.edit("submissions: []", 'submission: "[[legacy]]"')
        self.assertTrue(cw.normalize_file(self.path))
        text = self.path.read_text(encoding="utf-8")
        self.assertIn('submissions: ["[[legacy]]"]', text)
        self.assertNotIn("submission:", text)


class TestSummaryLine(WriterTestCase):
    def test_summary_line_round_trips_through_regex(self) -> None:
        line = cw.summary_line("manual input", 5, 1, 2, 2)
        m = cw.SUMMARY_RE.match(line)
        self.assertIsNotNone(m)
        self.assertEqual(
            m.groupdict(),
            {"source": "manual input", "found": "5", "new": "1", "updated": "2", "unchanged": "2"},
        )


class TestFrontmatterParsing(WriterTestCase):
    """Frontmatter is read with PyYAML, so YAML types are normalised explicitly."""

    def test_date_is_typed_by_yaml_and_normalised(self) -> None:
        fm, _ = cw._read_frontmatter_text("---\ncfp_close: 2026-11-01\n---\n\nb\n")
        self.assertEqual(fm["cfp_close"], datetime.date(2026, 11, 1))  # YAML typed it
        self.assertEqual(cw._as_str(fm["cfp_close"]), "2026-11-01")

    def test_bool_is_read(self) -> None:
        fm, _ = cw._read_frontmatter_text("---\nshortlist: true\n---\n\nb\n")
        self.assertTrue(cw._as_bool(fm["shortlist"]))

    def test_missing_key_is_treated_as_absent(self) -> None:
        fm, _ = cw._read_frontmatter_text("---\ntype: cfp\n---\n\nb\n")
        self.assertEqual(cw._as_list(fm.get("topics")), [])
        self.assertEqual(cw._as_str(fm.get("country")), "")

    def test_invalid_yaml_raises(self) -> None:
        with self.assertRaises(cw.FrontmatterError):
            cw._read_frontmatter_text("---\ntype: cfp\nname: [unclosed\n---\n\nb\n")

    def test_upsert_leaves_an_unparseable_note_untouched(self) -> None:
        self.write_initial()
        self.path.write_text("---\nname: [unclosed\n---\n\nbody\n", encoding="utf-8")
        before = self.path.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):  # the warning is expected
            status = cw.upsert(self.data, self.row)
        self.assertEqual(status, "skipped")
        self.assertEqual(self.path.read_bytes(), before)


class TestCfpTemplate(unittest.TestCase):
    """The vault's ``templates/cfp-template.md`` must match what the writer emits.

    A hand-created CFP note is interchangeable with a generated one only while the
    two shapes agree. The test follows the data symlink to the vault and walks up
    from there. It **skips** when the template is absent, so the suite still runs
    standalone.
    """

    SEARCH_PARENTS = (*ROOT.parents, *(ROOT / "data").resolve().parents)
    TEMPLATE = next(
        (base / "templates" / "cfp-template.md" for base in SEARCH_PARENTS
         if (base / "templates" / "cfp-template.md").is_file()),
        None,
    )
    REQUIRED = {
        "type", "name", "event_date", "location", "country", "cfp_close",
        "topics", "event_url", "cfp_url", "source", "shortlist", "submissions",
        "created", "updated",
    }

    @unittest.skipUnless(TEMPLATE, "templates/cfp-template.md not found")
    def test_template_keys_match_a_generated_note(self) -> None:
        fm, _ = cw._read_frontmatter(self.TEMPLATE)
        keys = set(fm)
        self.assertTrue(self.REQUIRED <= keys, f"missing: {self.REQUIRED - keys}")
        self.assertTrue(keys <= self.REQUIRED | {"benefits", "languages"}, f"unknown: {keys - self.REQUIRED - {'benefits', 'languages'}}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
