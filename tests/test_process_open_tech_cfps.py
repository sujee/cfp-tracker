#!/usr/bin/env python3
"""Offline tests for src/process-open-tech-cfps.py using real source slices."""
from __future__ import annotations

import copy
import datetime
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "open-tech-cfps"
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer as cw


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


potc = load_module(ROOT / "src" / "process-open-tech-cfps.py", "potc")
OPEN = json.loads((FIX / "open.sample.json").read_text(encoding="utf-8"))
CLOSED = json.loads((FIX / "closed.sample.json").read_text(encoding="utf-8"))
CUTOFF = datetime.date(2026, 10, 13)


class OpenTechTestCase(unittest.TestCase):
    def collect(self, open_data=None, closed_data=None, cutoff=CUTOFF):
        open_data = OPEN if open_data is None else open_data
        closed_data = CLOSED if closed_data is None else closed_data

        def fake_fetch(url, cache_path=None, cache_key=None):
            if url.endswith("/open.json"):
                return copy.deepcopy(open_data)
            if url.endswith("/closed.json"):
                return copy.deepcopy(closed_data)
            raise AssertionError(f"unexpected URL: {url}")

        with mock.patch.object(potc, "_fetch_json", side_effect=fake_fetch):
            return potc.collect_rows(cutoff)


class TestDatesAndBenefits(OpenTechTestCase):
    def test_parses_utc_and_other_aware_offsets(self) -> None:
        self.assertEqual(
            potc._parse_utc("2026-11-12T04:59:00Z"),
            datetime.datetime(2026, 11, 12, 4, 59, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(
            potc._parse_utc("2026-11-12T05:59:00+01:00"),
            datetime.datetime(2026, 11, 12, 4, 59, tzinfo=datetime.timezone.utc),
        )

    def test_rejects_missing_naive_and_invalid_datetimes(self) -> None:
        for value in (None, "", "2026-11-12", "2026-11-12T04:59:00", "not-a-date"):
            with self.subTest(value=value):
                self.assertIsNone(potc._parse_utc(value))

    def test_event_dates_are_strict_iso_dates(self) -> None:
        self.assertEqual(potc._parse_date("2027-07-01"), datetime.date(2027, 7, 1))
        for value in (None, "", "2027-07-01junk", "July 2027"):
            with self.subTest(value=value):
                self.assertIsNone(potc._parse_date(value))

    def test_maps_only_explicit_travel_and_accommodation_coverage(self) -> None:
        event = {
            "perks": {
                "travel": "expenses covered",
                "accommodation": "Expenses Covered",
                "fee": "free for speakers",
            }
        }
        self.assertEqual(potc.benefits_of(event), ["travel", "hotel"])
        self.assertEqual(potc.benefits_of({"perks": {"fee": "free for speakers"}}), [])
        self.assertEqual(potc.benefits_of({"perks": {"travel": "not covered"}}), [])
        self.assertEqual(potc.benefits_of({"perks": None}), [])


class TestCollectRows(OpenTechTestCase):
    def test_real_fixtures_filter_sort_and_map_fields(self) -> None:
        rows = self.collect()
        self.assertEqual(
            [row["name"] for row in rows],
            [
                "6th Annual North Carolina Cybersecurity Symposium",
                "Atlanta Hardware Builders",
                "PASSMN Monthly Meetings 2026",
                "Agile On The Beach 2027",
            ],
        )
        self.assertNotIn("VKU-Gipfel 2027", {row["name"] for row in rows})

        atlanta = rows[1]
        self.assertEqual(atlanta["event_date"], "2026-12-03")
        self.assertEqual(atlanta["country"], "USA")
        self.assertEqual(atlanta["cfp_close"], "2026-11-12")
        self.assertEqual(
            atlanta["cfp_url"], "https://sessionize.com/atlanta-hardware-builders/"
        )

        online = rows[2]
        self.assertEqual(online["event_date"], "TBA")
        self.assertEqual(online["location"], "Online")
        self.assertEqual(online["country"], "Online")
        self.assertEqual(online["topics"], ["azure", "data", "microsoft"])

        agile = rows[3]
        self.assertEqual(agile["country"], "UK")
        self.assertEqual(agile["benefits"], ["travel", "hotel"])
        self.assertEqual(agile["cfp_close"], "2026-11-15")

        recently_closed = rows[0]
        self.assertEqual(recently_closed["event_url"], "")
        self.assertEqual(recently_closed["benefits"], [])  # a waived fee is not an honorarium

    def test_cutoff_includes_the_whole_cutoff_utc_date(self) -> None:
        rows = self.collect(cutoff=datetime.date(2026, 11, 12))
        names = {row["name"] for row in rows}
        self.assertIn("Atlanta Hardware Builders", names)
        self.assertNotIn("6th Annual North Carolina Cybersecurity Symposium", names)

    def test_duplicate_open_and_closed_record_imports_once(self) -> None:
        closed = copy.deepcopy(CLOSED)
        closed["cfps"].append(copy.deepcopy(OPEN["cfps"][0]))
        rows = self.collect(closed_data=closed)
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            sum(row["name"] == "Atlanta Hardware Builders" for row in rows), 1
        )

    def test_same_name_and_deadline_uses_the_newest_record(self) -> None:
        opened = copy.deepcopy(OPEN)
        other = copy.deepcopy(opened["cfps"][0])
        other["id"] = "sessionize:atlanta-hardware-builders-another-edition"
        other["url"] = "https://sessionize.com/atlanta-hardware-builders-another-edition/"
        other["updated"] = "2026-11-11T00:00:00Z"
        opened["cfps"].append(other)
        rows = self.collect(open_data=opened)
        atlanta = [row for row in rows if row["name"] == "Atlanta Hardware Builders"]
        self.assertEqual(len(atlanta), 1)
        self.assertEqual(atlanta[0]["cfp_url"], other["url"])

    def test_requires_name_and_cfp_url(self) -> None:
        opened = copy.deepcopy(OPEN)
        opened["cfps"][0]["url"] = ""
        opened["cfps"][1]["name"] = "  "
        rows = self.collect(open_data=opened)
        self.assertEqual({row["name"] for row in rows[1:]}, {"Agile On The Beach 2027"})
        self.assertEqual(len(rows), 2)

    def test_ignore_topics_checks_names_and_tags(self) -> None:
        with mock.patch.object(potc, "_IGNORE", ["agile", "azure"]):
            rows = self.collect()
        self.assertNotIn("Agile On The Beach 2027", {row["name"] for row in rows})
        self.assertNotIn("PASSMN Monthly Meetings 2026", {row["name"] for row in rows})
        self.assertEqual(len(rows), 2)

    def test_malformed_feed_fails_instead_of_silently_importing_nothing(self) -> None:
        with self.assertRaisesRegex(ValueError, "cfps list"):
            self.collect(open_data=[])


class TestMain(OpenTechTestCase):
    def test_writes_notes_source_and_manifest(self) -> None:
        def fake_fetch(url, cache_path=None, cache_key=None):
            return copy.deepcopy(OPEN if url.endswith("/open.json") else CLOSED)

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            manifest = Path(tmp) / "manifest.json"
            argv = [
                "process-open-tech-cfps.py",
                "--out", str(data_dir),
                "--today", "2026-11-12",
                "--manifest", str(manifest),
            ]
            cw.reset_cfp_url_index()
            with (
                mock.patch.object(potc, "_fetch_json", side_effect=fake_fetch),
                mock.patch.object(sys, "argv", argv),
                redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(potc.main(), 0)

            notes = list(data_dir.rglob("*.md"))
            self.assertEqual(len(notes), 4)
            self.assertEqual(len(json.loads(manifest.read_text(encoding="utf-8"))), 4)
            self.assertIn(
                "open-tech-cfps: found 4 (new 4, updated 0, unchanged 0)",
                output.getvalue(),
            )
            for note in notes:
                frontmatter, _ = cw._read_frontmatter(note)
                self.assertEqual(frontmatter["source"], "open-tech-cfps")
                self.assertTrue(frontmatter["event_type"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
