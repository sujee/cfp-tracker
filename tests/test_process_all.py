#!/usr/bin/env python3
"""Tests for src/process-all.py — parsing per-source summary lines.

Run from the project folder:

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_process_all():
    """Import ``process-all.py`` (hyphen in the name prevents a normal import)."""
    spec = importlib.util.spec_from_file_location("process_all", ROOT / "src" / "process-all.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pa = load_process_all()


class TestCollectSummaries(unittest.TestCase):
    def test_parses_each_source_line(self) -> None:
        output = (
            "> running something\n"
            "developers.events: found 575 (new 2, updated 8, unchanged 565)\n"
            "confs.tech: found 16 (new 0, updated 10, unchanged 6)\n"
            "manual input: found 5 (new 0, updated 0, unchanged 5)\n"
            "done\n"
        )
        rows = pa.collect_summaries(output)
        self.assertEqual([r["source"] for r in rows], ["developers.events", "confs.tech", "manual input"])
        self.assertEqual(rows[0], {"source": "developers.events", "found": 575, "new": 2, "updated": 8, "unchanged": 565})
        self.assertEqual(rows[2]["unchanged"], 5)

    def test_ignores_non_summary_lines(self) -> None:
        self.assertEqual(pa.collect_summaries("hello\nfound 3 things\n"), [])


class TestPrintSummary(unittest.TestCase):
    def test_summary_reports_totals_and_on_disk_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "2026").mkdir()
            (data / "2026" / "a.md").write_text("x", encoding="utf-8")
            (data / "2026" / "b.md").write_text("x", encoding="utf-8")
            rows = [
                {"source": "developers.events", "found": 10, "new": 2, "updated": 1, "unchanged": 7},
                {"source": "manual input", "found": 4, "new": 0, "updated": 0, "unchanged": 4},
            ]
            buf = io.StringIO()
            with redirect_stdout(buf):
                pa.print_summary(rows, data)
            out = buf.getvalue()
            self.assertIn("CFP refresh summary", out)
            self.assertIn("developers.events", out)
            self.assertIn("Found 14 CFPs across 2 source(s)", out)
            self.assertIn("2 new", out)
            self.assertIn("2 notes on disk", out)

    def test_empty_summaries_prints_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with redirect_stdout(buf):
                pa.print_summary([], Path(tmp))
            self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
