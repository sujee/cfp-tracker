#!/usr/bin/env python3
"""Tests for src/prestige.py — the curated ranking table and its matcher.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Prestige is a judgement, so the matcher is the only thing that can be tested:
the point of these cases is that a keyword never silently swallows a different
conference, and that a broken table fails loudly instead of ranking nothing.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import prestige as p  # noqa: E402


TABLE = """
# Title prose that is not a table.

| signal | 2 | 1 | 0 |
| :--- | :--- | :--- | :--- |
| Selectivity | curated | review | open |

| conf name | ranking | keywords |
| :--- | :---: | :--- |
| FOSDEM | 1 | fosdem |
| KubeCon + CloudNativeCon | 1 | kubecon, cloudnativecon |
| Devoxx Belgium | 1 | devoxx belgium |
| Devoxx | 2 | devoxx |
| BSides | 3 | bsides |
"""


class TestTokens(unittest.TestCase):
    def test_lowercases_and_splits_on_punctuation(self) -> None:
        self.assertEqual(p.tokens("AI Engineer"), ["ai", "engineer"])
        self.assertEqual(p.tokens("AWS re:Invent 2027"), ["aws", "re", "invent", "2027"])
        self.assertEqual(p.tokens("SREcon27 Americas"), ["srecon27", "americas"])

    def test_empty(self) -> None:
        self.assertEqual(p.tokens(""), [])
        self.assertEqual(p.tokens(None), [])


class TestPhraseMatches(unittest.TestCase):
    def test_exact_word(self) -> None:
        self.assertTrue(p.phrase_matches("FOSDEM 2027", "fosdem"))

    def test_year_glued_to_the_name_matches(self) -> None:
        # These two are the whole reason prefix matching exists: the edition year
        # is glued onto the word, so a whole-word match misses both.
        self.assertTrue(p.phrase_matches("SREcon27 Americas", "srecon"))
        self.assertTrue(p.phrase_matches("OffensiveCon26 - Tokyo", "offensivecon"))
        self.assertTrue(p.phrase_matches("KubeCon2026", "kubecon"))

    def test_non_year_suffix_does_not_match(self) -> None:
        # "engineer" must not swallow "AI Engineering Summit"...
        self.assertFalse(p.phrase_matches("AI Engineering Summit 2026", "ai engineer"))
        # ...and a generic word must not swallow a different conference.
        self.assertFalse(p.phrase_matches("Build, Secure, Scale", "scale 24x"))
        self.assertFalse(p.phrase_matches("Monster Scale Summit 2027", "scale 24x"))

    def test_multiword_phrase(self) -> None:
        self.assertTrue(p.phrase_matches("Write the Docs Portland 2027", "write the docs"))
        self.assertFalse(p.phrase_matches("Write Docs Portland", "write the docs"))

    def test_punctuation_and_case_insensitive(self) -> None:
        self.assertTrue(p.phrase_matches("AWS re:Invent 2027", "re invent"))
        self.assertTrue(p.phrase_matches("Google I/O 2027", "google i o"))

    def test_phrase_must_be_contiguous(self) -> None:
        self.assertFalse(p.phrase_matches("Devoxx and Greece", "devoxx greece"))

    def test_empty_inputs(self) -> None:
        self.assertFalse(p.phrase_matches("", "fosdem"))
        self.assertFalse(p.phrase_matches("FOSDEM", ""))


class TestParseTable(unittest.TestCase):
    def test_reads_only_ranking_tables(self) -> None:
        rules = p.parse_table(TABLE)
        self.assertEqual(
            [(r.name, r.tier) for r in rules],
            [
                ("FOSDEM", 1),
                ("KubeCon + CloudNativeCon", 1),
                ("Devoxx Belgium", 1),
                ("Devoxx", 2),
                ("BSides", 3),
            ],
        )

    def test_rubric_table_is_ignored(self) -> None:
        names = {r.name for r in p.parse_table(TABLE)}
        self.assertNotIn("Selectivity", names)
        self.assertNotIn("signal", names)

    def test_keywords_split_on_commas_and_semicolons(self) -> None:
        rules = p.parse_table(TABLE)
        kubecon = next(r for r in rules if r.name.startswith("KubeCon"))
        self.assertEqual(kubecon.keywords, ("kubecon", "cloudnativecon"))

    def test_markdown_wrapping_is_stripped(self) -> None:
        rules = p.parse_table(
            "| conf name | ranking | keywords |\n"
            "|---|---|---|\n"
            "| **[KubeCon](https://example.org)** | 1 | `kubecon` |\n"
        )
        self.assertEqual(rules[0].name, "KubeCon")
        self.assertEqual(rules[0].keywords, ("kubecon",))

    def test_extra_columns_are_ignored(self) -> None:
        rules = p.parse_table(
            "| conf name | ranking | keywords | notes |\n"
            "|---|---|---|---|\n"
            "| FOSDEM | 1 | fosdem | the free-software flagship |\n"
        )
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].tier, 1)

    def test_bad_ranking_fails_loudly(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            p.parse_table("| conf name | ranking | keywords |\n|---|---|---|\n| FOSDEM | high | fosdem |\n")
        self.assertIn("not a number", str(ctx.exception))

    def test_out_of_range_ranking_fails_loudly(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            p.parse_table("| conf name | ranking | keywords |\n|---|---|---|\n| FOSDEM | 4 | fosdem |\n")
        self.assertIn("not one of", str(ctx.exception))

    def test_missing_keywords_fails_loudly(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            p.parse_table("| conf name | ranking | keywords |\n|---|---|---|\n| FOSDEM | 1 |  |\n")
        self.assertIn("no keywords", str(ctx.exception))

    def test_prose_without_a_table_is_empty(self) -> None:
        self.assertEqual(p.parse_table("# Just prose\n\nNothing here.\n"), [])


class TestLoadAndMatch(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = p.parse_table(TABLE)

    def test_missing_file_is_not_an_error(self) -> None:
        self.assertEqual(p.load(ROOT / "tests" / "no-such-prestige.md"), [])

    def test_load_sorts_by_tier(self) -> None:
        tiers = [r.tier for r in p.load(ROOT / "prestige.md")]
        self.assertEqual(tiers, sorted(tiers))

    def test_lowest_tier_wins(self) -> None:
        self.assertEqual(p.match_tier("Devoxx Belgium 2027", self.rules), 1)
        self.assertEqual(p.match_tier("Devoxx Greece", self.rules), 2)

    def test_unmatched_returns_none(self) -> None:
        self.assertIsNone(p.match_tier("Power Platform Days Barcelona 2026", self.rules))
        self.assertIsNone(p.match_tier("", self.rules))

    def test_all_matching_rules_lists_every_hit(self) -> None:
        hits = p.all_matching_rules("Devoxx Belgium", self.rules)
        self.assertEqual([r.tier for r in hits], [1, 2])

    def test_no_rules(self) -> None:
        self.assertIsNone(p.match_tier("FOSDEM 2027", []))
        self.assertIsNone(p.match_rule("FOSDEM 2027", []))
        self.assertEqual(p.all_matching_rules("FOSDEM 2027", []), [])


class TestShippedTable(unittest.TestCase):
    """The real prestige.md — guards a bad edit to the curated list itself."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = p.load(ROOT / "prestige.md")

    def test_table_exists_and_is_nonempty(self) -> None:
        self.assertTrue((ROOT / "prestige.md").is_file())
        self.assertGreater(len(self.rules), 20)

    def test_every_rule_is_well_formed(self) -> None:
        for rule in self.rules:
            self.assertIn(rule.tier, p.TIERS, rule.name)
            self.assertTrue(rule.keywords, rule.name)
            for keyword in rule.keywords:
                self.assertTrue(keyword.strip(), rule.name)
                self.assertGreaterEqual(len(p.tokens(keyword)), 1, rule.name)

    def test_names_are_unique(self) -> None:
        names = [r.name.casefold() for r in self.rules]
        self.assertEqual(len(names), len(set(names)), "duplicate row in prestige.md")

    def test_no_generic_keywords(self) -> None:
        # A topic word would tag hundreds of unrelated notes as prestigious.
        banned = {"ai", "data", "cloud", "conference", "summit", "developer", "2026", "2027"}
        for rule in self.rules:
            for keyword in rule.keywords:
                self.assertNotIn(keyword.casefold(), banned, f"{rule.name}: {keyword!r}")

    def test_flagships_we_hold_are_ranked(self) -> None:
        self.assertEqual(p.match_tier("KubeCon + CloudNativeCon Europe 2027", self.rules), 1)
        self.assertEqual(p.match_tier("SREcon27 Americas", self.rules), 1)
        self.assertEqual(p.match_tier("FOSDEM 2027", self.rules), 1)
        self.assertEqual(p.match_tier("QCon London 2027", self.rules), 1)
        self.assertEqual(p.match_tier("KotlinConf", self.rules), 2)
        self.assertEqual(p.match_tier("Voxxed Days Zürich", self.rules), 3)

    def test_ordinary_community_events_are_not_ranked(self) -> None:
        for name in (
            "Power Platform Days Barcelona 2026",
            "Build, Secure, Scale",
            "Monster Scale Summit 2027",
            "DevFest Harare",
            "Microsoft Fabric User Group Pune",
            "AI Engineering Summit 2026",
        ):
            self.assertIsNone(p.match_tier(name, self.rules), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
