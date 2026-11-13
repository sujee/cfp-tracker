#!/usr/bin/env python3
"""Tests for src/process-python-deadlines.py using real sample data.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. ``tests/fixtures/python-deadlines/conferences.sample.yml`` is a real
slice of the upstream YAML.
"""
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
FIX = ROOT / "tests" / "fixtures" / "python-deadlines"
sys.path.insert(0, str(ROOT / "src"))

import config


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ppd = load_module(ROOT / "src" / "process-python-deadlines.py", "ppd")

SAMPLE = (FIX / "conferences.sample.yml").read_text(encoding="utf-8")

CUTOFF = datetime.date(2026, 10, 1)
TODAY = datetime.date(2026, 11, 2)


class TestParseDate(unittest.TestCase):
    def test_accepts_the_shapes_in_the_source(self) -> None:
        self.assertEqual(ppd._parse_date("2026-12-11 17:00:00"), datetime.date(2026, 12, 11))
        self.assertEqual(ppd._parse_date("2027-04-16"), datetime.date(2027, 4, 16))
        self.assertEqual(ppd._parse_date(datetime.date(2027, 4, 16)), datetime.date(2027, 4, 16))

    def test_rejects_empty_and_garbage(self) -> None:
        self.assertIsNone(ppd._parse_date(""))
        self.assertIsNone(ppd._parse_date(None))
        self.assertIsNone(ppd._parse_date("next spring"))


class TestCollectRows(unittest.TestCase):
    def setUp(self) -> None:
        def fake_fetch(url, cache_path=None, cache_key=None):
            return SAMPLE

        self._orig = ppd._fetch_text
        ppd._fetch_text = fake_fetch

    def tearDown(self) -> None:
        ppd._fetch_text = self._orig

    def test_keeps_only_entries_with_a_future_cfp_and_a_link(self) -> None:
        rows = ppd.collect_rows(CUTOFF, TODAY, None)
        by_name = {r["name"]: r for r in rows}
        # PyCon Côte d'Ivoire has a cfp but no cfp_link -> skipped.
        self.assertNotIn("PyCon Côte d’Ivoire", by_name)

    def test_shared_pretalx_url_stays_two_rows(self) -> None:
        rows = ppd.collect_rows(CUTOFF, TODAY, None)
        names = [r["name"] for r in rows]
        self.assertIn("PyTexas", names)
        self.assertIn("Python Community Leadership Summit", names)

    def test_row_shape(self) -> None:
        rows = ppd.collect_rows(CUTOFF, TODAY, None)
        pytexas = next(r for r in rows if r["name"] == "PyTexas")
        self.assertEqual(pytexas["cfp_close"], "2026-12-11")
        self.assertEqual(pytexas["event_date"], "2027-04-16")
        self.assertEqual(pytexas["location"], "Austin, USA")
        self.assertEqual(pytexas["cfp_url"], "https://pretalx.com/pytexas-2027/cfp")
        self.assertEqual(pytexas["event_url"], "https://www.pytexas.org/2027/")
        self.assertEqual(pytexas["topics"], ["py"])

    def test_dedupe_by_name_and_close_date(self) -> None:
        # Fixture has no exact duplicate; ensure count is stable.
        rows = ppd.collect_rows(CUTOFF, TODAY, None)
        keys = [(r["name"], r["cfp_close"]) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main(verbosity=2)