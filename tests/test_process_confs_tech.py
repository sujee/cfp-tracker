#!/usr/bin/env python3
"""Tests for src/process-confs-tech.py using real sample data.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. ``tests/fixtures/confs-tech/general.sample.json`` is a real slice of the
confs.tech JSON (regenerate with ``tests/fixtures/extract_fixtures.py``).
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "confs-tech"
sys.path.insert(0, str(ROOT / "src"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pct = load_module(ROOT / "src" / "process-confs-tech.py", "pct")

GENERAL = json.loads((FIX / "general.sample.json").read_text(encoding="utf-8"))

CUTOFF = datetime.date(2026, 10, 1)
TODAY = datetime.date(2026, 11, 2)


class TestParseDate(unittest.TestCase):
    def test_accepts_the_shapes_in_the_source(self) -> None:
        self.assertEqual(pct._parse_date("2027-01-11"), datetime.date(2027, 1, 11))
        self.assertEqual(pct._parse_date("2027-01-15T23:59:59Z"), datetime.date(2027, 1, 15))
        self.assertEqual(pct._parse_date("2027-01-15T23:59:59"), datetime.date(2027, 1, 15))

    def test_rejects_empty_and_garbage(self) -> None:
        self.assertIsNone(pct._parse_date(""))
        self.assertIsNone(pct._parse_date(None))
        self.assertIsNone(pct._parse_date("next spring"))


class TestCollectRows(unittest.TestCase):
    def setUp(self) -> None:
        # Patch the network fetch to serve the fixture for any topic file.
        def fake_fetch(url, cache_path=None, cache_key=None):
            if url.rstrip("/").endswith(("2026", "2027", "2028")):
                return [{"name": "general.json"}, {"name": "python.json"}]
            if url.endswith("general.json"):
                return GENERAL
            if url.endswith("python.json"):
                return []
            return []

        self._orig = pct._fetch_json
        pct._fetch_json = fake_fetch

    def tearDown(self) -> None:
        pct._fetch_json = self._orig

    def test_keeps_only_entries_with_a_future_cfp(self) -> None:
        rows = pct.collect_rows(CUTOFF, TODAY, None)
        by_name = {r["name"]: r for r in rows}
        # Digital Crafts Day's cfp ended 2025-10-31; Fosdem has no cfpEndDate.
        self.assertEqual(set(by_name), {"AI in Production", "Webdevcon", "PyCascades"})

    def test_row_shape_and_normalisation(self) -> None:
        rows = pct.collect_rows(CUTOFF, TODAY, None)
        web = next(r for r in rows if r["name"] == "Webdevcon")
        self.assertEqual(web["cfp_close"], "2026-12-18")
        self.assertEqual(web["event_date"], "2027-03-16")
        self.assertEqual(web["location"], "Amsterdam, Netherlands")
        self.assertEqual(web["event_url"], "https://webdevcon.nl")
        self.assertEqual(web["cfp_url"], "https://sessionize.com/dawn-conferences-2027")

    def test_same_conference_across_years_is_deduped(self) -> None:
        # The fixture year-listing returns the same data for 2026 and 2027.
        rows = pct.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(len([r for r in rows if r["name"] == "PyCascades"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
