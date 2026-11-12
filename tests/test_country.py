#!/usr/bin/env python3
"""Tests for src/country.py — canonical country labels.

Run from the project folder:

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import country as c  # noqa: E402


class TestKey(unittest.TestCase):
    def test_folds_case_punctuation_and_spaces(self) -> None:
        self.assertEqual(c._key("U.S.A."), "u s a")
        self.assertEqual(c._key("  united   states  "), "united states")
        self.assertEqual(c._key("Côte d'Ivoire"), "côte d ivoire")
        self.assertEqual(c._key("UK & Ireland"), "uk and ireland")
        self.assertEqual(c._key(""), "")


class TestNormalizeCountry(unittest.TestCase):
    def test_empty_inputs_collapse_to_empty(self) -> None:
        self.assertEqual(c.normalize_country(""), "")
        self.assertEqual(c.normalize_country("   "), "")
        self.assertEqual(c.normalize_country(None), "")

    def test_canonical_values_pass_through(self) -> None:
        for value in ("USA", "UK", "Germany", "Poland", "Peru", "Online"):
            self.assertEqual(c.normalize_country(value), value)

    def test_united_states_spellings(self) -> None:
        for value in (
            "USA",
            "US",
            "us",
            "U.S.A.",
            "United States",
            "the United States",
            "United States of America",
            "America",
        ):
            self.assertEqual(c.normalize_country(value), "USA", value)

    def test_united_kingdom_spellings(self) -> None:
        for value in (
            "UK",
            "U.K.",
            "United Kingdom",
            "Great Britain",
            "Britain",
            "GB",
            "England",
            "Scotland",
            "Wales",
            "Northern Ireland",
        ):
            self.assertEqual(c.normalize_country(value), "UK", value)

    def test_online_spellings(self) -> None:
        for value in ("Online", "online", "Virtual", "Remote", "Online only", "Worldwide"):
            self.assertEqual(c.normalize_country(value), "Online", value)

    def test_other_country_variants(self) -> None:
        pairs = {
            "Holland": "Netherlands",
            "NL": "Netherlands",
            "the Netherlands": "Netherlands",
            "Czech Republic": "Czechia",
            "UAE": "United Arab Emirates",
            "U.A.E.": "United Arab Emirates",
            "Korea": "South Korea",
            "Republic of Korea": "South Korea",
            "Türkiye": "Turkey",
            "Russian Federation": "Russia",
            "Viet Nam": "Vietnam",
            "Brasil": "Brazil",
            "Côte d'Ivoire": "Ivory Coast",
            "North Macedonia": "Macedonia",
            "Eswatini": "Swaziland",
        }
        for value, canonical in pairs.items():
            self.assertEqual(c.normalize_country(value), canonical, value)

    def test_case_and_whitespace_insensitive(self) -> None:
        self.assertEqual(c.normalize_country("  united   states  "), "USA")
        self.assertEqual(c.normalize_country("uNiTeD kInGdOm"), "UK")
        self.assertEqual(c.normalize_country(" netherlands "), "Netherlands")

    def test_unknown_country_is_returned_unchanged(self) -> None:
        for value in ("Germany", "Poland", "Peru", "Republic of the Congo", "Narnia"):
            self.assertEqual(c.normalize_country(value), value)

    def test_unknown_value_is_stripped(self) -> None:
        self.assertEqual(c.normalize_country("  Peru  "), "Peru")

    def test_idempotent(self) -> None:
        for value in ("United States", "uk", "Virtual", "Peru", "", "Brasil"):
            once = c.normalize_country(value)
            self.assertEqual(c.normalize_country(once), once, value)

    def test_alias_table_is_consistent(self) -> None:
        # No spelling is claimed by two countries, and every group spelling that
        # is listed maps back to its own canonical label.
        for canonical, spellings in c._ALIAS_GROUPS.items():
            self.assertTrue(canonical, "empty canonical label")
            for spelling in spellings:
                self.assertEqual(c.ALIASES[c._key(spelling)], canonical, spelling)


class TestCountryNameFromAlpha2(unittest.TestCase):
    def test_resolves_iso_codes_to_canonical_labels(self) -> None:
        pairs = {
            "US": "USA",
            "GB": "UK",
            "DE": "Germany",
            "KR": "South Korea",
            "NL": "Netherlands",
            "XK": "Kosovo",
        }
        for value, expected in pairs.items():
            with self.subTest(value=value):
                self.assertEqual(c.country_name_from_alpha2(value), expected)

    def test_empty_unknown_and_malformed_codes_are_safe(self) -> None:
        self.assertEqual(c.country_name_from_alpha2(None), "")
        self.assertEqual(c.country_name_from_alpha2(""), "")
        self.assertEqual(c.country_name_from_alpha2("ZZ"), "ZZ")
        self.assertEqual(c.country_name_from_alpha2(" Unknown "), "Unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
