#!/usr/bin/env python3
"""Tests for src/process-manual-input.py using real sample data.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. ``tests/fixtures/manual/input.sample.md`` is a copy of the real
``input/gmail1.md`` table (regenerate with ``tests/fixtures/extract_fixtures.py``).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "manual"
sys.path.insert(0, str(ROOT / "src"))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pmi = load_module(ROOT / "src" / "process-manual-input.py", "pmi")

SAMPLE = (FIX / "input.sample.md").read_text(encoding="utf-8")


class TestNormalizeClose(unittest.TestCase):
    def test_formats(self) -> None:
        self.assertEqual(pmi._normalize_close("Dec 31, 2026"), "2026-12-31")
        self.assertEqual(pmi._normalize_close("Mar 1, 2027"), "2027-03-01")
        self.assertEqual(pmi._normalize_close("2027-03-01"), "2027-03-01")
        self.assertEqual(pmi._normalize_close("12/31/2026"), "2026-12-31")

    def test_unstated_qualifier_is_dropped(self) -> None:
        self.assertEqual(pmi._normalize_close("Early 2027 / Unstated"), "Early 2027")
        self.assertEqual(pmi._normalize_close("Dec 2026 / Unstated"), "Dec 2026")
        self.assertEqual(pmi._normalize_close("Unstated"), "Unstated")
        self.assertEqual(pmi._normalize_close(""), "—")


class TestParseRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = pmi.parse_rows(SAMPLE)

    def test_header_and_separator_skipped(self) -> None:
        # gmail1.md has one header row + separator, then 5 data rows.
        self.assertEqual(len(self.rows), 5)
        self.assertIn("QCon London 2027", self.rows[0]["name"])
        self.assertIn("Agentic AI Summit 2027", self.rows[4]["name"])

    def test_columns_mapped(self) -> None:
        qcon = self.rows[0]
        self.assertEqual(qcon["location"], "London, UK")
        self.assertEqual(qcon["cfp_close"], "Early 2027")
        self.assertEqual(qcon["event_date"], "Apr 13–15, 2027")

    def test_name_and_url_extracted_from_markdown_link(self) -> None:
        dww = next(r for r in self.rows if "DeveloperWeek" in r["name"])
        self.assertEqual(dww["name"], "DeveloperWeek 2027 / AI DevWorld")  # not the raw link
        self.assertEqual(dww["event_url"], "https://www.developerweek.com/")  # unwrapped from Google

    def test_all_markdown_links_become_plain_names_and_direct_urls(self) -> None:
        expected = {
            "QCon London 2027": "https://qconlondon.com/",
            "Seattle Startup Summit 2027": "https://www.nvidia.com/gtc/",
            "DeveloperWeek 2027 / AI DevWorld": "https://www.developerweek.com/",
            "AI Engineer Europe 2027": "https://www.ai.engineer/",
            "Agentic AI Summit 2027": "https://events.linuxfoundation.org/",
        }
        self.assertEqual({r["name"]: r["event_url"] for r in self.rows}, expected)
        for row in self.rows:
            with self.subTest(name=row["name"]):
                self.assertNotRegex(row["name"], r"https?://|\]\(|\*\*")

    def test_parseable_close_is_normalised(self) -> None:
        ai_engineer = next(r for r in self.rows if "AI Engineer Europe 2027" in r["name"])
        self.assertEqual(ai_engineer["cfp_close"], "2026-12-31")

    def test_free_text_close_strips_unstated(self) -> None:
        dww = next(r for r in self.rows if "DeveloperWeek 2027" in r["name"])
        self.assertEqual(dww["cfp_close"], "Dec 2026")

    def test_topics_kept_as_text(self) -> None:
        ai_engineer = next(r for r in self.rows if "AI Engineer Europe 2027" in r["name"])
        self.assertIn("AI in Production", ai_engineer["topics"])


class TestMainEndToEnd(unittest.TestCase):
    def test_runs_offline_and_writes_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "src" / "process-manual-input.py"),
                    "--out",
                    str(out),
                    "--input",
                    str(FIX),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("found 5 (new 5, updated 0, unchanged 0)", proc.stdout)
            notes = sorted(out.rglob("*.md"))
            self.assertEqual(len(notes), 5)
            self.assertEqual(
                {note.relative_to(out).as_posix() for note in notes},
                {
                    "2026/2026-12-31_ai-engineer-europe-2027.md",
                    "2027/2027_agentic-ai-summit-2027.md",
                    "2027/2027_developerweek-2027-ai-devworld.md",
                    "2027/2027_qcon-london-2027.md",
                    "2027/2027_seattle-startup-summit-2027.md",
                },
            )
            agentic = (out / "2027/2027_agentic-ai-summit-2027.md").read_text(encoding="utf-8")
            self.assertIn("\nname: Agentic AI Summit 2027\n", agentic)
            self.assertNotIn("google.com/url", agentic)
            self.assertIn("source: manual", notes[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
