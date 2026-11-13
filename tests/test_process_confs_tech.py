#!/usr/bin/env python3
"""Tests for src/process-confs-tech.py using real sample data.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. ``tests/fixtures/confs-tech/general.sample.json`` is a real slice of the
confs.tech JSON (regenerate with ``tests/fixtures/extract_fixtures.py``).
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
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "confs-tech"
sys.path.insert(0, str(ROOT / "src"))

import config


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


class TestFetchCache(unittest.TestCase):
    def test_online_fetch_refreshes_an_existing_cache_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            dest = cache / "feed.json"
            dest.write_text('["stale"]', encoding="utf-8")
            response = io.BytesIO(b'["live"]')
            with mock.patch("http_cache.urllib.request.urlopen", return_value=response) as fetch:
                result = pct._fetch_json("https://example.test", cache, "feed.json")
            self.assertEqual(result, ["live"])
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8")), ["live"])
            self.assertEqual(list(cache.glob("*.tmp")), [])
            fetch.assert_called_once()

    def test_fetch_error_uses_and_reports_valid_cached_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "feed.json").write_text('["cached"]', encoding="utf-8")
            with (
                mock.patch("http_cache.urllib.request.urlopen", side_effect=OSError("down")),
                redirect_stderr(io.StringIO()) as errors,
            ):
                result = pct._fetch_json("https://example.test", cache, "feed.json")
            self.assertEqual(result, ["cached"])
            self.assertIn("cache fallback", errors.getvalue())

    def test_schema_invalid_topic_preserves_cached_events(self) -> None:
        cached = [{"name": "Cached"}]
        cached_text = json.dumps(cached, indent=2)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            dest = cache / "feed.json"
            dest.write_text(cached_text, encoding="utf-8")
            response = io.BytesIO(b'{"message": "temporarily unavailable"}')
            with (
                mock.patch("http_cache.urllib.request.urlopen", return_value=response),
                redirect_stderr(io.StringIO()),
            ):
                result = pct._fetch_json(
                    "https://example.test",
                    cache,
                    "feed.json",
                    validator=lambda data: pct._validate_topic_events(
                        data, 2026, "general.json"
                    ),
                )
            self.assertEqual(result, cached)
            self.assertEqual(dest.read_text(encoding="utf-8"), cached_text)

    def test_empty_topic_list_is_valid_but_empty_listing_is_not(self) -> None:
        self.assertTrue(pct._validate_topic_events([], 2026, "general.json"))
        with self.assertRaisesRegex(ValueError, "nonempty topic listing"):
            pct._validate_listing([], 2026)

    def test_offline_reads_cache_without_touching_the_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "feed.json").write_text('["cached"]', encoding="utf-8")
            with mock.patch("http_cache.urllib.request.urlopen") as fetch:
                result = pct._fetch_json(
                    "https://example.test", cache, "feed.json", offline=True
                )
            self.assertEqual(result, ["cached"])
            fetch.assert_not_called()

    def test_malformed_cache_is_not_a_silent_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "feed.json").write_text("not json", encoding="utf-8")
            with mock.patch("http_cache.urllib.request.urlopen", side_effect=OSError("down")):
                with self.assertRaisesRegex(ValueError, "cache fallback is unavailable"):
                    pct._fetch_json("https://example.test", cache, "feed.json")


class TestCollectRows(unittest.TestCase):
    def setUp(self) -> None:
        self.requested_topics = []

        # Patch the network fetch to serve the fixture for any topic file.
        def fake_fetch(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith(("2026", "2027", "2028")):
                return [
                    {"name": "general.json"},
                    {"name": "python.json"},
                    {"name": "javascript.json"},
                ]
            if url.endswith(".json"):
                self.requested_topics.append(url.rsplit("/", 1)[-1].removesuffix(".json"))
            if url.endswith("general.json"):
                return GENERAL
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
        self.assertEqual(web["country"], "Netherlands")
        self.assertEqual(web["topics"], [])

    def test_specialized_topic_is_retained(self) -> None:
        def general_and_python(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith(("2026", "2027")):
                return [{"name": "general.json"}, {"name": "python.json"}]
            return copy.deepcopy(GENERAL)

        with (
            mock.patch.object(pct, "_fetch_json", side_effect=general_and_python),
            mock.patch.object(config, "CONFS_TECH_TOPICS", {"python"}),
        ):
            rows = pct.collect_rows(CUTOFF, TODAY, None)
        self.assertTrue(rows)
        self.assertTrue(all(row["topics"] == ["python"] for row in rows))

    def test_utm_variant_merges_topics_when_general_comes_first(self) -> None:
        general = [copy.deepcopy(next(row for row in GENERAL if row["name"] == "Webdevcon"))]
        python = copy.deepcopy(general)
        python[0]["cfpUrl"] += "?utm_source=confs-tech&utm_medium=feed"

        def general_then_python(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith(("2026", "2027")):
                return [{"name": "general.json"}, {"name": "python.json"}]
            if url.endswith("python.json"):
                return python
            return general

        with (
            mock.patch.object(pct, "_fetch_json", side_effect=general_then_python),
            mock.patch.object(config, "CONFS_TECH_TOPICS", {"python"}),
        ):
            rows = pct.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Webdevcon")
        self.assertEqual(rows[0]["topics"], ["python"])
        self.assertEqual(rows[0]["cfp_url"], general[0]["cfpUrl"])

    def test_different_editions_with_one_name_survive_deduplication(self) -> None:
        first = copy.deepcopy(GENERAL)
        second = copy.deepcopy(GENERAL)
        event = next(row for row in second if row["name"] == "PyCascades")
        event["cfpEndDate"] = "2027-12-01"
        event["startDate"] = "2028-02-01"

        def yearly(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith("2026"):
                return [{"name": "general.json"}]
            if url.rstrip("/").endswith("2027"):
                return [{"name": "general.json"}]
            return first if "/2026/" in url else second

        with mock.patch.object(pct, "_fetch_json", side_effect=yearly):
            rows = pct.collect_rows(CUTOFF, TODAY, None)
        editions = [row for row in rows if row["name"] == "PyCascades"]
        self.assertEqual(
            {row["cfp_close"] for row in editions},
            {"2026-10-26", "2027-12-01"},
        )

    def test_same_conference_across_years_is_deduped(self) -> None:
        # The fixture year-listing returns the same data for 2026 and 2027.
        rows = pct.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(len([r for r in rows if r["name"] == "PyCascades"]), 1)

    def test_allowlist_selects_topics_and_always_keeps_general(self) -> None:
        with mock.patch.object(config, "CONFS_TECH_TOPICS", {"python"}):
            pct.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(self.requested_topics, ["general", "python"] * 2)

    def test_empty_allowlist_selects_all_topics(self) -> None:
        with mock.patch.object(config, "CONFS_TECH_TOPICS", set()):
            pct.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(self.requested_topics, ["general", "python", "javascript"] * 2)

    def test_missing_next_year_listing_keeps_current_year_rows(self) -> None:
        def missing_next_year(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith("2027"):
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            if url.rstrip("/").endswith("2026"):
                return [{"name": "general.json"}]
            return GENERAL

        with mock.patch.object(pct, "_fetch_json", side_effect=missing_next_year):
            rows = pct.collect_rows(CUTOFF, TODAY, None)
        self.assertEqual(
            {row["name"] for row in rows},
            {"AI in Production", "Webdevcon", "PyCascades"},
        )

    def test_missing_current_year_listing_is_fatal(self) -> None:
        def missing_current_year(url, cache_path=None, cache_key=None, offline=False, validator=None):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        with mock.patch.object(pct, "_fetch_json", side_effect=missing_current_year):
            with self.assertRaisesRegex(RuntimeError, "could not list conferences/2026"):
                pct.collect_rows(CUTOFF, TODAY, None)

    def test_invalid_next_year_listing_shape_is_fatal(self) -> None:
        def invalid_next_year(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith("2027"):
                return {"message": "Not Found"}
            if url.rstrip("/").endswith("2026"):
                return [{"name": "general.json"}]
            return GENERAL

        with mock.patch.object(pct, "_fetch_json", side_effect=invalid_next_year):
            with self.assertRaisesRegex(
                ValueError, "confs.tech 2027: expected a nonempty topic listing"
            ):
                pct.collect_rows(CUTOFF, TODAY, None)

    def test_listing_fetch_failure_aborts_the_whole_source(self) -> None:
        def fail_second_listing(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith("2027"):
                raise OSError("listing unavailable")
            if url.rstrip("/").endswith("2026"):
                return [{"name": "general.json"}]
            return GENERAL

        with mock.patch.object(pct, "_fetch_json", side_effect=fail_second_listing):
            with self.assertRaisesRegex(RuntimeError, "could not list conferences/2027"):
                pct.collect_rows(CUTOFF, TODAY, None)

    def test_topic_fetch_failure_aborts_instead_of_returning_partial_rows(self) -> None:
        def fail_second_topic(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith(("2026", "2027")):
                return [{"name": "general.json"}]
            if "/2027/" in url:
                raise OSError("topic unavailable")
            return GENERAL

        with mock.patch.object(pct, "_fetch_json", side_effect=fail_second_topic):
            with self.assertRaisesRegex(RuntimeError, "could not fetch 2027/general.json"):
                pct.collect_rows(CUTOFF, TODAY, None)

    def test_empty_listing_fails_instead_of_producing_an_empty_manifest(self) -> None:
        with mock.patch.object(pct, "_fetch_json", return_value=[]):
            with self.assertRaisesRegex(ValueError, "nonempty topic listing"):
                pct.collect_rows(CUTOFF, TODAY, None)

    def test_malformed_topic_data_fails_instead_of_being_skipped(self) -> None:
        def malformed_topic(url, cache_path=None, cache_key=None, offline=False, validator=None):
            if url.rstrip("/").endswith(("2026", "2027")):
                return [{"name": "general.json"}]
            return {"unexpected": []}

        with mock.patch.object(pct, "_fetch_json", side_effect=malformed_topic):
            with self.assertRaisesRegex(ValueError, "expected a list of events"):
                pct.collect_rows(CUTOFF, TODAY, None)


class TestWriteDiscoveredTopics(unittest.TestCase):
    def test_writes_sorted_topics_without_rewriting_config(self) -> None:
        config_path = ROOT / "src" / "config.py"
        original_config = config_path.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "nested" / "discovered-topics.txt"
            pct.write_discovered_topics({"python", "api", "data"}, dest)
            self.assertEqual(dest.read_text(encoding="utf-8"), "api\ndata\npython\n")
        self.assertEqual(config_path.read_bytes(), original_config)

    def run_main(self, extra_args) -> mock.Mock:
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "process-confs-tech.py",
                "--out", str(Path(tmp) / "data"),
                "--cache", str(Path(tmp) / "cache"),
                *extra_args,
            ]
            with (
                mock.patch.object(pct, "collect_rows", return_value=[]),
                mock.patch.object(pct, "write_discovered_topics") as writer,
                mock.patch.object(sys, "argv", argv),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(pct.main(), 0)
            return writer

    def test_normal_main_does_not_write_discovered_topics(self) -> None:
        self.run_main([]).assert_not_called()

    def test_discovered_topics_write_is_opt_in(self) -> None:
        self.run_main(["--write-discovered-topics"]).assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
