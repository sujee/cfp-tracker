#!/usr/bin/env python3
"""Tests for src/process-developer-events.py using real sample data.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. The fixtures under ``tests/fixtures/developers-events/`` are small,
verbatim slices of the live ``all-cfps.json`` / ``all-events.json`` (regenerate
with ``tests/fixtures/extract_fixtures.py``), so the tests see the real shapes:
epoch-ms dates, duplicate editions, event tags, online events.
"""
from __future__ import annotations

import copy
import datetime
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "developers-events"
sys.path.insert(0, str(ROOT / "src"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pde = load_module(ROOT / "src" / "process-developer-events.py", "pde")

CFPS = json.loads((FIX / "all-cfps.sample.json").read_text(encoding="utf-8"))
EVENTS = json.loads((FIX / "all-events.sample.json").read_text(encoding="utf-8"))

CUTOFF = datetime.date(2026, 10, 1)
EXPECTED = {
    "Dutch AI Conference",                        # 2026-12-18
    "DevFest 2026",                               # 2026-11-06
    "ContainerDays & AI Context London 2027",     # 2026-12-01
    "AI & Copilot Summit 01.-02. Juni 2027",      # 2026-12-21, online
    "AI Context New York 2027",                   # 2027-01-04
}


class TestFetchValidation(unittest.TestCase):
    def test_non_list_live_feed_preserves_the_cached_list(self) -> None:
        cached = [{"conf": {"name": "Cached"}}]
        cached_text = json.dumps(cached, indent=2)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            dest = cache / "all-cfps.json"
            dest.write_text(cached_text, encoding="utf-8")
            response = io.BytesIO(b'{"message": "temporarily unavailable"}')
            with (
                mock.patch("http_cache.urllib.request.urlopen", return_value=response),
                redirect_stderr(io.StringIO()),
            ):
                result = pde.fetch_json(
                    cache, "all-cfps.json", pde.SRC_URLS["all-cfps.json"]
                )
            self.assertEqual(result, cached)
            self.assertEqual(dest.read_text(encoding="utf-8"), cached_text)

    def test_offline_rejects_a_non_list_cached_feed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "all-events.json").write_text('{"message": "down"}', encoding="utf-8")
            with mock.patch("http_cache.urllib.request.urlopen") as fetch:
                with self.assertRaisesRegex(ValueError, "expected a JSON list"):
                    pde.fetch_json(
                        cache,
                        "all-events.json",
                        pde.SRC_URLS["all-events.json"],
                        offline=True,
                    )
            fetch.assert_not_called()


class TestBuildRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Fixture expectations must not depend on a developer's local config.
        cls._original_ignore = pde._IGNORE
        pde._IGNORE = ["mobile"]
        cls.rows = pde.build_rows(CFPS, EVENTS, CUTOFF)
        cls.by_name = {r["name"]: r for r in cls.rows}

    @classmethod
    def tearDownClass(cls) -> None:
        pde._IGNORE = cls._original_ignore

    def test_keeps_the_open_cfps(self) -> None:
        self.assertEqual(set(self.by_name), EXPECTED)

    def test_drops_long_closed_cfp(self) -> None:
        self.assertNotIn("HashiConf EU", self.by_name)  # 2019

    def test_drops_older_duplicate_edition_of_same_name(self) -> None:
        # Fixture has "Dutch AI Conference" twice: close 2025-12-19 (past) + 2026-12-18.
        dutch = [r for r in self.rows if r["name"] == "Dutch AI Conference"]
        self.assertEqual(len(dutch), 1)
        self.assertEqual(dutch[0]["cfp_url"], "https://sessionize.com/dawn-conferences-2027/")

    def test_drops_ignored_topic_name(self) -> None:
        self.assertNotIn("Mobile Makers 2027", self.by_name)  # "mobile" in IGNORE_TOPICS

    def test_event_without_a_cfp_is_not_a_row(self) -> None:
        self.assertNotIn("STARWEST", self.by_name)  # present in all-events only

    def test_identical_duplicate_entry_is_deduped(self) -> None:
        dup = copy.deepcopy(CFPS[CFPS.index(next(c for c in CFPS if c["conf"]["name"] == "AI Context New York 2027"))])
        rows = pde.build_rows(CFPS + [dup], EVENTS, CUTOFF)
        self.assertEqual(len([r for r in rows if r["name"] == "AI Context New York 2027"]), 1)

    def test_country_comes_from_location(self) -> None:
        self.assertEqual(self.by_name["DevFest 2026"]["country"], "Portugal")
        self.assertEqual(self.by_name["Dutch AI Conference"]["country"], "Netherlands")

    def test_topics_and_languages_from_event_tags(self) -> None:
        dutch = self.by_name["Dutch AI Conference"]
        self.assertEqual(dutch["topics"], ["ai", "data", "ml"])
        self.assertEqual(dutch["languages"], ["english"])
        self.assertIn("containers", self.by_name["ContainerDays & AI Context London 2027"]["topics"])

    def test_matched_event_url(self) -> None:
        # Real event hyperlinks, matched by (name, location, nearest date).
        self.assertTrue(self.by_name["Dutch AI Conference"]["event_url"].startswith("https://"))
        self.assertEqual(
            self.by_name["AI Context New York 2027"]["cfp_url"],
            "https://sessionize.com/ai-context-ny-co/",
        )

    def test_row_contains_only_note_enrichment_fields(self) -> None:
        dutch = self.by_name["Dutch AI Conference"]
        self.assertEqual(
            set(dutch),
            {"name", "close", "dates", "loc", "country", "topics", "languages", "event_url", "cfp_url"},
        )
        self.assertEqual(pde.event_date_start(dutch["dates"]), "2027-03-16")
        self.assertEqual(dutch["loc"], "Amsterdam (Netherlands)")

    def test_event_url_falls_back_to_cfp_conf_when_matched_event_lacks_one(self) -> None:
        entry = copy.deepcopy(next(c for c in CFPS if c["link"] == "https://sessionize.com/dawn-conferences-2027/"))
        event = copy.deepcopy(next(
            e for e in EVENTS
            if e["name"] == "Dutch AI Conference" and e["date"] == entry["conf"]["date"]
        ))
        event.pop("hyperlink")

        row = pde.build_rows([entry], [event], CUTOFF)[0]

        self.assertEqual(row["event_url"], entry["conf"]["hyperlink"])
        self.assertEqual(row["topics"], ["ai", "data", "ml"])


class TestSelectBestEvent(unittest.TestCase):
    def test_DevFest_picks_the_matching_city(self) -> None:
        candidates = [e for e in EVENTS if e["name"] == "DevFest 2026"]
        self.assertEqual(len(candidates), 4)  # Tripoli, Ismailia, Setif, Faro
        chosen = pde.select_best_event(candidates, "faro (portugal)", datetime.date(2026, 11, 6))
        self.assertTrue(chosen["location"].startswith("Faro"))

    def test_prefers_the_upcoming_edition(self) -> None:
        candidates = [e for e in EVENTS if e["name"] == "Dutch AI Conference"]
        self.assertEqual(len(candidates), 2)  # 2026-03 and 2027-03
        chosen = pde.select_best_event(candidates, "amsterdam (netherlands)", datetime.date(2026, 12, 18))
        self.assertEqual(pde.epoch_ms_to_date(chosen["date"][0]).year, 2027)


class TestHelpers(unittest.TestCase):
    def test_normalize_name(self) -> None:
        self.assertEqual(pde.normalize_name("AI Engineer World's Fair 2027!"), "aiengineerworldsfair2027")

    def test_extract_country_from_location(self) -> None:
        self.assertEqual(pde.extract_country_from_location("Faro (Portugal)"), "Portugal")
        self.assertEqual(pde.extract_country_from_location("Online"), "")
        self.assertEqual(pde.extract_country_from_location(None), "")

    def test_event_date_start(self) -> None:
        self.assertEqual(pde.event_date_start([1802908800000, 1802736000000]), "2027-02-16")
        self.assertEqual(pde.event_date_start([]), "TBA")

    def test_compute_cutoff_rolling_days(self) -> None:
        today = datetime.date(2026, 11, 2)
        self.assertEqual(pde.compute_cutoff(today, months_back=1), datetime.date(2026, 10, 3))
        self.assertEqual(pde.compute_cutoff(today, days_back=7), datetime.date(2026, 10, 26))

    def test_legacy_report_flags_remain_parseable(self) -> None:
        args = pde.build_arg_parser().parse_args([
            "--focus-tags", "ai", "--no-focus", "--no-frontmatter", "--no-backup"
        ])
        self.assertEqual(args.months_back, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
