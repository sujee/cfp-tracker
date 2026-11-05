#!/usr/bin/env python3
"""Tests for src/process-cfp-ninja.py using a real sample of the API data.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. ``tests/fixtures/cfp-ninja/events.sample.json`` is a short, verbatim
slice of the live ``cfp.ninja/api/v0/events`` response (regenerate with
``tests/fixtures/extract_fixtures.py``), so the tests see the real shapes:
ISO ``cfp_close_at`` / ``start_date`` strings, ``is_online``, country names and
comma-separated ``tags``.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "cfp-ninja"
sys.path.insert(0, str(ROOT / "src"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pcn = load_module(ROOT / "src" / "process-cfp-ninja.py", "pcn")

EVENTS = json.loads((FIX / "events.sample.json").read_text(encoding="utf-8"))

CUTOFF = datetime.date(2026, 10, 1)
TODAY = datetime.date(2026, 11, 2)


class TestParseDate(unittest.TestCase):
    def test_accepts_iso_datetime_and_date(self) -> None:
        self.assertEqual(pcn._parse_date("2027-11-18T23:59:00Z"), datetime.date(2027, 11, 18))
        self.assertEqual(pcn._parse_date("2027-03-09T00:00:00Z"), datetime.date(2027, 3, 9))
        self.assertEqual(pcn._parse_date("2026-11-07"), datetime.date(2026, 11, 7))

    def test_rejects_empty_and_garbage(self) -> None:
        self.assertIsNone(pcn._parse_date(""))
        self.assertIsNone(pcn._parse_date(None))
        self.assertIsNone(pcn._parse_date("sometime"))


class TestCollectRows(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = pcn.fetch_events
        pcn.fetch_events = lambda cache_path=None: EVENTS

    def tearDown(self) -> None:
        pcn.fetch_events = self._orig

    def test_keeps_only_entries_with_a_deadline_on_or_after_cutoff(self) -> None:
        rows = pcn.collect_rows(CUTOFF, TODAY, None)
        names = {r["name"] for r in rows}
        self.assertEqual(
            names,
            {
                "Conf42 Chaos Engineering 2027",
                "Conf42 MLOps 2027",
                "LLMday Montevideo 2026 Q4",
                "SREday Chennai 2026 Q4",
                "SREday Katowice 2027 Q2",
                "PLATFORMday London 2027 Q2",
            },
        )
        # SREday Lisbon 2025 Q4 closed 2025-11-13, long before the cutoff.
        self.assertNotIn("SREday Lisbon 2025 Q4", names)

    def test_row_shape_and_submission_url(self) -> None:
        rows = pcn.collect_rows(CUTOFF, TODAY, None)
        montevideo = next(r for r in rows if r["name"] == "LLMday Montevideo 2026 Q4")
        self.assertEqual(montevideo["cfp_close"], "2026-11-07")
        self.assertEqual(montevideo["event_date"], "2026-12-05")
        self.assertEqual(montevideo["location"], "World Trade Center Montevideo - Torre 4, Montevideo")
        self.assertEqual(montevideo["country"], "Uruguay")
        self.assertEqual(montevideo["event_url"], "https://llmday.com/2026-montevideo-q4/")
        self.assertEqual(montevideo["cfp_url"], "https://cfp.ninja/e/llmday-2026-montevideo-q4")
        self.assertEqual(montevideo["topics"], [])
        self.assertEqual(montevideo["benefits"], [])

    def test_online_event_gets_online_country_and_split_tags(self) -> None:
        rows = pcn.collect_rows(CUTOFF, TODAY, None)
        chaos = next(r for r in rows if r["name"] == "Conf42 Chaos Engineering 2027")
        self.assertEqual(chaos["country"], "Online")
        self.assertEqual(chaos["location"], "Online")
        self.assertEqual(chaos["topics"], ["conf42", "chaos-engineering", "sre"])

    def test_same_name_and_deadline_is_deduped(self) -> None:
        dup = dict(EVENTS[0])
        rows = pcn.collect_rows(CUTOFF, TODAY, None)
        single = [r for r in rows if r["name"] == "Conf42 Chaos Engineering 2027"]
        self.assertEqual(len(single), 1)

        pcn.fetch_events = lambda cache_path=None: EVENTS + [dup]
        again = pcn.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(len([r for r in again if r["name"] == "Conf42 Chaos Engineering 2027"]), 1)

    def test_benefits_are_mapped_from_the_flags(self) -> None:
        record = {
            "name": "Benefits Conf 2027",
            "slug": "benefits-conf-2027",
            "cfp_close_at": "2027-01-15T23:59:00Z",
            "start_date": "2027-05-01T00:00:00Z",
            "website": "https://benefits.example",
            "is_online": False,
            "location": "Lisbon",
            "country": "Portugal",
            "tags": "",
            "travel_covered": True,
            "hotel_covered": True,
            "honorarium_provided": True,
        }
        pcn.fetch_events = lambda cache_path=None: [record]
        row = pcn.collect_rows(CUTOFF, TODAY, None)[0]
        self.assertEqual(row["benefits"], ["travel", "hotel", "honorarium"])

    def test_results_are_sorted_by_deadline(self) -> None:
        rows = pcn.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual([r["cfp_close"] for r in rows], sorted(r["cfp_close"] for r in rows))


class TestBenefitsOf(unittest.TestCase):
    def test_empty_when_nothing_is_stated(self) -> None:
        self.assertEqual(pcn.benefits_of({}), [])
        self.assertEqual(
            pcn.benefits_of({"travel_covered": False, "hotel_covered": False, "honorarium_provided": False}),
            [],
        )

    def test_lists_only_the_true_flags(self) -> None:
        self.assertEqual(pcn.benefits_of({"travel_covered": True}), ["travel"])
        self.assertEqual(
            pcn.benefits_of({"hotel_covered": True, "honorarium_provided": True}),
            ["hotel", "honorarium"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
