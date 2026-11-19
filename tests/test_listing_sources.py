#!/usr/bin/env python3
"""Tests for structured event-listing adapters and offline note generation."""
from __future__ import annotations

import datetime
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "listings"
sys.path.insert(0, str(ROOT / "src"))

ADAPTERS = (
    "process-agentconfs.py",
    "process-realtime-embedded-conferences.py",
    "process-ieee-ras.py",
    "process-ccf-deadlines.py",
)
CACHE_FILES = {
    "process-agentconfs.py": "agentconfs-events.json",
    "process-realtime-embedded-conferences.py": "realtime-embedded-conferences.json",
    "process-ieee-ras.py": "ieee-ras-deadlines.ics",
    "process-ccf-deadlines.py": "ccf-deadlines-allconf.json",
}
TODAY = datetime.date(2026, 11, 18)


def load_adapter(script: str):
    name = "test_listing_" + script.removesuffix(".py").replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, ROOT / "src" / script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestStructuredListings(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
        self.cache.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def seed(self, script: str) -> None:
        filename = CACHE_FILES[script]
        shutil_source = FIXTURES / filename
        (self.cache / filename).write_text(shutil_source.read_text(encoding="utf-8"), encoding="utf-8")

    def rows(self, script: str) -> list[dict]:
        module = load_adapter(script)
        self.seed(script)
        return module.collect_rows(TODAY, TODAY, self.cache, offline=True)

    def test_agentconfs_keeps_only_current_speaking_robotics_calls(self) -> None:
        rows = self.rows("process-agentconfs.py")
        self.assertEqual([row["name"] for row in rows], ["Embedded Vision Summit 2027"])
        row = rows[0]
        self.assertEqual(row["cfp_close"], "2026-11-21")
        self.assertEqual(row["event_date"], "2027-02-02")
        self.assertEqual(row["event_type"], "summit")
        self.assertEqual(row["country"], "USA")
        self.assertEqual(row["location"], "San Francisco, USA")

    def test_automatic_drops_estimates_and_old_records(self) -> None:
        rows = self.rows("process-realtime-embedded-conferences.py")
        self.assertEqual({row["name"] for row in rows}, {"RSS 2027", "IROS 2027"})
        by_name = {row["name"]: row for row in rows}
        self.assertEqual(by_name["RSS 2027"]["cfp_url"], "https://roboticsconference.org/information/cfp/")
        self.assertEqual(by_name["RSS 2027"]["cfp_close"], "2026-12-04")
        self.assertEqual(by_name["IROS 2027"]["event_date"], "2027-09-26")
        self.assertNotIn("TAROS 2027", by_name)

    def test_ieee_ras_parses_each_deadline_vevent(self) -> None:
        rows = self.rows("process-ieee-ras.py")
        self.assertEqual([row["cfp_close"] for row in rows], ["2026-12-01", "2027-02-05"])
        self.assertEqual(
            rows[0]["name"],
            "ARSO: 2027 IEEE International Conference on Advanced Robotics and its Social Impacts (ARSO)",
        )
        self.assertEqual(rows[0]["event_date"], "TBA")
        self.assertEqual(rows[0]["location"], "—")

    def test_ccf_keeps_rounds_separate_without_mixing_initial_submission(self) -> None:
        rows = self.rows("process-ccf-deadlines.py")
        self.assertEqual(len(rows), 4)
        by_name = {row["name"]: row for row in rows}
        self.assertEqual(len([name for name in by_name if name.startswith("IROS 2027")]), 1)
        self.assertEqual(len([name for name in by_name if name.startswith("RSS 2027")]), 3)
        self.assertFalse(any(name.startswith("AAAI") for name in by_name))
        stage_one = next(name for name in by_name if "Stage 1" in name and "(submission:" in name)
        self.assertNotIn("rebuttal", stage_one.casefold())
        self.assertEqual(by_name[stage_one]["event_date"], "2027-07-06")
        self.assertTrue(any("(rebuttal:" in name for name in by_name))
        self.assertTrue(any("(decision:" in name for name in by_name))

    def test_ccf_abstract_and_submission_have_independent_identities(self) -> None:
        module = load_adapter("process-ccf-deadlines.py")
        edition = {
            "timeline": [{
                "abstract_deadline": "2027-01-15 23:59:59",
                "deadline": "2027-01-20 23:59:59",
                "comment": "Main round",
            }],
            "timezone": "AoE",
        }
        rounds = module._rounds(edition, TODAY)
        self.assertEqual([stage for stage, _comment, _close, _text in rounds], ["abstract", "submission"])
        self.assertEqual(rounds[0][2], "2027-01-15")
        self.assertEqual(rounds[1][2], "2027-01-20")
        self.assertTrue(all(close_text.endswith("AoE") for _stage, _comment, _close, close_text in rounds))

    def test_every_adapter_assigns_both_domain_topics(self) -> None:
        for script in ADAPTERS:
            with self.subTest(script=script):
                for row in self.rows(script):
                    self.assertIn("robotics", row["topics"])
                    self.assertIn("physical.ai", row["topics"])
                    physical_variants = [
                        topic for topic in row["topics"]
                        if topic.casefold().replace(".", "").replace("-", "").replace(" ", "") == "physicalai"
                    ]
                    self.assertEqual(len(physical_variants), 1)

    def test_domain_topic_variants_are_normalized(self) -> None:
        from listing_source import with_domain_topics

        self.assertEqual(with_domain_topics(["robotics"]), ["robotics", "physical.ai"])
        self.assertEqual(with_domain_topics(["Physical AI", "robotics"]), ["physical.ai", "robotics"])
        self.assertEqual(with_domain_topics(["physical-ai", "robotics", "Physical AI"]), ["physical.ai", "robotics"])

    def test_standalone_listing_adapter_writes_note_with_source(self) -> None:
        module = load_adapter("process-agentconfs.py")
        self.seed("process-agentconfs.py")
        out = Path(self.tmp.name) / "data"
        manifest = Path(self.tmp.name) / "manifest.json"
        with mock.patch.object(sys, "argv", [
            "process-agentconfs.py",
            "--out", str(out),
            "--cache", str(self.cache),
            "--manifest", str(manifest),
            "--today", "2026-11-18",
            "--offline",
        ]):
            self.assertEqual(module.main(), 0)
        notes = list(out.rglob("*.md"))
        self.assertEqual(len(notes), 1)
        frontmatter = yaml.safe_load(notes[0].read_text(encoding="utf-8").split("---")[1])
        self.assertEqual(frontmatter["source"], "agentconfs")
        self.assertEqual(frontmatter["cfp_close"], datetime.date(2026, 11, 21))
        self.assertEqual(frontmatter["event_type"], "summit")
        self.assertIn("robotics", frontmatter["topics"])
        self.assertIn("physical.ai", frontmatter["topics"])
        self.assertEqual(yaml.safe_load(manifest.read_text(encoding="utf-8")), [notes[0].relative_to(out).as_posix()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
