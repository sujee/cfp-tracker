#!/usr/bin/env python3
"""Tests for src/process-adato-tracker.py using a real slice of the tracker page.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. ``tests/fixtures/adato-tracker/cfp-tracker.sample.html`` is a small,
real slice of the ``tablesorter`` table from
https://adatosystems.com/cfp-tracker/ (regenerate with
``tests/fixtures/extract_fixtures.py``), so the tests see the real shapes: an
eight-column table of clean ISO dates, ``VIRTUAL`` city rows, and HTML entities
in names (``&#8211;``, ``&#39;``).
"""
from __future__ import annotations

import datetime
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "adato-tracker"
sys.path.insert(0, str(ROOT / "src"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pat = load_module(ROOT / "src" / "process-adato-tracker.py", "pat")

PAGE = (FIX / "cfp-tracker.sample.html").read_text(encoding="utf-8")

CUTOFF = datetime.date(2026, 11, 1)
TODAY = datetime.date(2026, 11, 6)

# Names the fixture carries, kept so the assertions stay readable.
VIRTUAL_NAME = ".NET Conf 2026 | Building the Next Generation of .NET Applications"


class TestParseDate(unittest.TestCase):
    def test_accepts_clean_iso(self) -> None:
        self.assertEqual(pat._parse_date("2027-04-01"), datetime.date(2027, 4, 1))
        self.assertEqual(pat._parse_date(" 2026-11-06 "), datetime.date(2026, 11, 6))

    def test_rejects_empty_and_garbage(self) -> None:
        self.assertIsNone(pat._parse_date(""))
        self.assertIsNone(pat._parse_date(None))
        self.assertIsNone(pat._parse_date("Dec 2026"))
        self.assertIsNone(pat._parse_date("2026-11-06T00:00:00"))


class TestTableParser(unittest.TestCase):
    def test_only_the_tablesorter_table_is_read(self) -> None:
        html = (
            '<table class="other"><tr><td>not me</td></tr></table>'
            + PAGE
        )
        rows = pat._parse_rows(html)
        names = {cells[0][0] for cells in rows}
        self.assertNotIn("not me", names)
        self.assertIn(VIRTUAL_NAME, names)

    def test_link_text_is_dropped_and_hrefs_kept(self) -> None:
        rows = pat._parse_rows(PAGE)
        first = next(c for c in rows if c[0][0] == VIRTUAL_NAME)
        self.assertEqual(first[6][0], "Link")  # event cell text, not the URL
        self.assertTrue(first[6][1].startswith("https://"))
        self.assertTrue(first[7][1].startswith("https://"))


class TestCollectRows(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = pat._fetch_page
        self._original_ignore = pat._IGNORE
        pat._fetch_page = lambda cache_path=None: PAGE
        # Fixture expectations must not depend on a developer's local config.
        pat._IGNORE = ["bitcoin", "mobile"]

    def tearDown(self) -> None:
        pat._fetch_page = self._orig
        pat._IGNORE = self._original_ignore

    def test_keeps_only_entries_with_a_deadline_on_or_after_cutoff(self) -> None:
        rows = pat.collect_rows(CUTOFF, TODAY, None)
        # Every fixture deadline is >= 2026-11-01, so all non-ignored rows survive.
        self.assertEqual(len(rows), 8)

        late = pat.collect_rows(datetime.date(2026, 11, 8), TODAY, None)
        names = {r["name"] for r in late}
        self.assertIn("AI Agents Day", names)
        self.assertNotIn("Analytics and Data Summit 2027", names)  # closed 11-07

    def test_ignored_names_are_dropped(self) -> None:
        rows = pat.collect_rows(CUTOFF, TODAY, None)
        names = {r["name"] for r in rows}
        self.assertNotIn("Dakar Bitcoin Days IV", names)  # IGNORE_TOPICS: bitcoin
        self.assertNotIn("Mobile Makers", names)          # IGNORE_TOPICS: mobile

    def test_virtual_row_becomes_online(self) -> None:
        rows = pat.collect_rows(CUTOFF, TODAY, None)
        row = next(r for r in rows if r["name"] == VIRTUAL_NAME)
        self.assertEqual(row["location"], "Online")
        self.assertEqual(row["country"], "Online")

    def test_city_and_state_join_into_location(self) -> None:
        rows = pat.collect_rows(CUTOFF, TODAY, None)
        row = next(r for r in rows if r["name"] == "Community Networks Conference")
        self.assertEqual(row["location"], "Seattle, WA")
        self.assertEqual(row["country"], "")
        self.assertEqual(row["event_date"], "2026-11-20")
        self.assertEqual(row["cfp_close"], "2026-11-07")
        self.assertTrue(row["cfp_url"].startswith("https://sessionize.com/"))

    def test_html_entities_are_decoded_in_names(self) -> None:
        rows = pat.collect_rows(CUTOFF, TODAY, None)
        names = {r["name"] for r in rows}
        self.assertIn("Global AI Sarasota \u2013 Kickoff", names)
        self.assertIn("SOAHR 2027 \u2013 SHRM-Atlanta's Annual Conference", names)

    def test_same_name_and_deadline_is_deduped(self) -> None:
        row = (
            "<tr><td>Repeat Conf 2027</td><td>VIRTUAL</td><td></td>"
            "<td>2027-04-01</td><td>2027-04-01</td><td>2026-11-20</td>"
            '<td><a href="https://example.test/e">Link</a></td>'
            '<td><a href="https://example.test/cfp">Link</a></td></tr>'
        )
        pat._fetch_page = lambda cache_path=None: (
            '<table class="tablesorter"><tbody>' + row + row + "</tbody></table>"
        )
        rows = pat.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(len([r for r in rows if r["name"] == "Repeat Conf 2027"]), 1)

    def test_results_are_sorted_by_deadline(self) -> None:
        rows = pat.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual([r["cfp_close"] for r in rows], sorted(r["cfp_close"] for r in rows))

    def test_topics_and_benefits_are_empty(self) -> None:
        row = pat.collect_rows(CUTOFF, TODAY, None)[0]
        self.assertEqual(row["topics"], [])
        self.assertNotIn("benefits", row)
        self.assertNotIn("languages", row)


if __name__ == "__main__":
    unittest.main(verbosity=2)
