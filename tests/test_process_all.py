#!/usr/bin/env python3
"""Tests for src/process-all.py — parsing per-source summary lines.

Run from the project folder:

    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_process_all():
    """Import ``process-all.py`` (hyphen in the name prevents a normal import)."""
    spec = importlib.util.spec_from_file_location("process_all", ROOT / "src" / "process-all.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pa = load_process_all()
import config  # noqa: E402


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


class TestEventTypeSummary(unittest.TestCase):
    def test_counts_sources_and_stars_included_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            notes = data / "2026"
            notes.mkdir()
            rows_to_write = [
                ("a", "developers.events", "conference"),
                ("b", "developers.events", "conference"),
                ("c", "manual", "summit"),
            ]
            for name, source, event_type in rows_to_write:
                (notes / f"{name}.md").write_text(
                    "---\n"
                    "type: cfp\n"
                    f"event_name: {name}\n"
                    f"source: {source}\n"
                    f"event_type: {event_type}\n"
                    "created: 2026-11-11\n"
                    "updated: 2026-11-11\n"
                    "---\n",
                    encoding="utf-8",
                )
            summaries = [
                {"source": "developers.events", "found": 2, "new": 0, "updated": 0, "unchanged": 2},
                {"source": "manual input", "found": 1, "new": 0, "updated": 0, "unchanged": 1},
            ]
            counts = pa.collect_event_type_counts(data)
            buf = io.StringIO()
            with redirect_stdout(buf):
                pa.print_summary(
                    summaries,
                    data,
                    included={"conference", "summit"},
                )

        self.assertEqual(counts["developers.events"]["conference"], 2)
        self.assertEqual(counts["manual"]["summit"], 1)
        output = buf.getvalue()
        matrix = output.split("Event types", 1)[1]
        self.assertIn("conference ★", matrix)
        self.assertIn("summit ★", matrix)
        self.assertNotIn("meetup ★", matrix)
        dev = next(line for line in matrix.splitlines() if line.startswith("developers.events"))
        self.assertEqual(dev.split()[1:], ["2", "0", "0", "0", "0", "0", "0"])
        manual = next(line for line in matrix.splitlines() if line.startswith("manual input"))
        self.assertEqual(manual.split()[2:], ["0", "0", "1", "0", "0", "0", "0"])


class TestPipelineWiring(unittest.TestCase):
    def test_open_tech_step_and_manifest_reach_archiving(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            argv = [
                "process-all.py",
                "--out", str(data_dir),
                "--input", str(Path(tmp) / "missing-input"),
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(pa.subprocess, "run", return_value=completed) as run,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(pa.main(), 0)

        commands = [call.args[0] for call in run.call_args_list]
        open_tech = next(
            command for command in commands
            if any(part.endswith("process-open-tech-cfps.py") for part in command)
        )
        self.assertIn("--out", open_tech)
        self.assertIn("--manifest", open_tech)
        open_tech_manifest = open_tech[open_tech.index("--manifest") + 1]
        self.assertTrue(open_tech_manifest.endswith("opentech.json"))

        archive = next(
            command for command in commands
            if any(part.endswith("archive-orphans.py") for part in command)
        )
        manifests = [
            archive[index + 1]
            for index, part in enumerate(archive)
            if part == "--manifest"
        ]
        self.assertIn(open_tech_manifest, manifests)

    def test_invalid_event_types_fail_before_sources_or_archiving(self) -> None:
        argv = ["process-all.py", "--out", "unused", "--input", "also-unused"]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(config, "EVENT_TYPES", []),
            mock.patch.object(pa.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "EVENT_TYPES"):
                pa.main()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
