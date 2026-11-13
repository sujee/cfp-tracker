#!/usr/bin/env python3
"""Tests for the collect/reconcile/archive pipeline and its reporting."""
from __future__ import annotations

import datetime
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_process_all():
    spec = importlib.util.spec_from_file_location("process_all", ROOT / "src/process-all.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pa = load_process_all()
import config
import cfp_writer as writer


def sample_row(**overrides) -> dict:
    row = {
        "name": "Wrapper Summit 2027",
        "event_date": "2027-04-01",
        "location": "Online",
        "country": "Online",
        "cfp_close": "2027-01-15",
        "topics": ["ai"],
        "event_url": "https://example.test",
        "cfp_url": "https://example.test/cfp",
        "source": "developers.events",
    }
    row.update(overrides)
    return row


class TestPrintSummary(unittest.TestCase):
    def test_summary_reports_totals_and_on_disk_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "2026").mkdir()
            (data / "2026/a.md").write_text("x", encoding="utf-8")
            (data / "2026/b.md").write_text("x", encoding="utf-8")
            rows = [
                {"source": "developers.events", "found": 10, "new": 2, "updated": 1, "unchanged": 7},
                {"source": "manual", "found": 4, "new": 0, "updated": 0, "unchanged": 4},
            ]
            buf = io.StringIO()
            with redirect_stdout(buf):
                pa.print_summary(rows, data)
            out = buf.getvalue()
            self.assertIn("CFP refresh summary", out)
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
            for name, source, event_type in [
                ("a", "developers.events", "conference"),
                ("b", "developers.events", "conference"),
                ("c", "manual", "summit"),
            ]:
                (notes / f"{name}.md").write_text(
                    "---\ntype: cfp\n"
                    f"event_name: {name}\nsource: {source}\nevent_type: {event_type}\n"
                    "created: 2026-11-11\nupdated: 2026-11-11\n---\n",
                    encoding="utf-8",
                )
            summaries = [
                {"source": "developers.events", "found": 2, "new": 0, "updated": 0, "unchanged": 2},
                {"source": "manual", "found": 1, "new": 0, "updated": 0, "unchanged": 1},
            ]
            counts = pa.collect_event_type_counts(data)
            buf = io.StringIO()
            with redirect_stdout(buf):
                pa.print_summary(summaries, data, included={"conference", "summit"})

        self.assertEqual(counts["developers.events"]["conference"], 2)
        self.assertEqual(counts["manual"]["summit"], 1)
        matrix = buf.getvalue().split("Event types", 1)[1]
        self.assertIn("conference ★", matrix)
        self.assertIn("summit ★", matrix)
        self.assertNotIn("meetup ★", matrix)
        dev = next(line for line in matrix.splitlines() if line.startswith("developers.events"))
        self.assertEqual(dev.split()[1:], ["2", "0", "0", "0", "0", "0", "0"])
        manual = next(line for line in matrix.splitlines() if line.startswith("manual"))
        self.assertEqual(manual.split()[1:], ["0", "0", "1", "0", "0", "0", "0"])


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.archive = self.root / "archived"
        self.data.mkdir()
        writer.reset_cfp_url_index()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def argv(self, *extra) -> list[str]:
        return [
            "process-all.py",
            "--out", str(self.data),
            "--archive", str(self.archive),
            "--input", str(self.root / "input"),
            "--no-prestige",
            *extra,
        ]

    def run_main(self, argv, **patches):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", argv))
            stack.enter_context(redirect_stdout(io.StringIO()))
            for name, value in patches.items():
                stack.enter_context(mock.patch.object(pa, name, value))
            return pa.main()

    def test_common_run_options_reach_every_selected_source(self) -> None:
        (self.root / "input").mkdir()
        cache = self.root / "chosen-cache"
        calls = []

        def collect(name, context):
            calls.append((name, context))
            return []

        argv = self.argv(
            "--today", "2026-01-15",
            "--months-back", "4",
            "--past-days", "45",
            "--cache", str(cache),
            "--offline",
            "--no-archive",
        )
        with mock.patch.object(config, "INPUT_SOURCES", ["developers.events", "manual"]):
            self.assertEqual(self.run_main(argv, collect_source=collect), 0)
        self.assertEqual([name for name, _ in calls], ["developers.events", "manual"])
        for _name, context in calls:
            self.assertEqual(context.today, datetime.date(2026, 1, 15))
            self.assertEqual(context.cutoff, datetime.date(2025, 12, 1))
            self.assertEqual(context.cache, cache.resolve())
            self.assertEqual(context.input_dir, (self.root / "input").resolve())
            self.assertTrue(context.offline)

    def test_missing_manual_input_protects_existing_manual_notes(self) -> None:
        note = writer.note_path(self.data, sample_row(source="manual"))
        writer.upsert(self.data, sample_row(source="manual"))
        with mock.patch.object(config, "INPUT_SOURCES", ["manual"]):
            self.assertEqual(self.run_main(self.argv()), 0)
        self.assertTrue(note.is_file())
        self.assertFalse(self.archive.exists())

    def test_disabled_sources_are_not_collected_or_archived(self) -> None:
        paused = sample_row(name="Paused Summit", source="open-tech-cfps")
        path = writer.note_path(self.data, paused)
        writer.upsert(self.data, paused)
        collect = mock.Mock(return_value=[])
        with mock.patch.object(config, "INPUT_SOURCES", ["developers.events"]):
            self.assertEqual(self.run_main(self.argv(), collect_source=collect), 0)
        collect.assert_called_once()
        self.assertEqual(collect.call_args.args[0], "developers.events")
        self.assertTrue(path.is_file())

    def test_collection_failure_writes_and_archives_nothing(self) -> None:
        original = sample_row()
        path = writer.note_path(self.data, original)
        writer.upsert(self.data, original)
        before = path.read_bytes()
        with mock.patch.object(config, "INPUT_SOURCES", ["developers.events", "cfp.ninja"]):
            result = self.run_main(
                self.argv(),
                collect_source=mock.Mock(side_effect=[[] , RuntimeError("partial source")]),
            )
        self.assertEqual(result, 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.archive.exists())

    def test_shared_today_reaches_writer_stamps(self) -> None:
        with mock.patch.object(config, "INPUT_SOURCES", ["developers.events"]):
            result = self.run_main(
                self.argv("--today", "2026-01-15", "--no-archive"),
                collect_source=mock.Mock(return_value=[sample_row()]),
            )
        self.assertEqual(result, 0)
        fm, _ = writer._read_frontmatter(writer.note_path(self.data, sample_row()))
        self.assertEqual(str(fm["created"]), "2026-01-15")
        self.assertEqual(str(fm["updated"]), "2026-01-15")

    def test_prestige_runs_after_archive(self) -> None:
        events = []

        def archived(*args):
            events.append("archive")
            return []

        def prestige(*args, **kwargs):
            events.append("prestige")
            return subprocess.CompletedProcess([], 0, stdout="", stderr="")

        argv = self.argv("--prestige", str(ROOT / "prestige.md"))
        argv.remove("--no-prestige")
        with mock.patch.object(config, "INPUT_SOURCES", ["developers.events"]):
            result = self.run_main(
                argv,
                collect_source=mock.Mock(return_value=[]),
                _archive_orphans=archived,
                subprocess=mock.Mock(run=mock.Mock(side_effect=prestige)),
            )
        self.assertEqual(result, 0)
        self.assertEqual(events, ["archive", "prestige"])

    def test_no_prestige_skips_subprocess(self) -> None:
        with (
            mock.patch.object(config, "INPUT_SOURCES", ["developers.events"]),
            mock.patch.object(pa, "collect_source", return_value=[]),
            mock.patch.object(pa.subprocess, "run") as run,
        ):
            self.assertEqual(self.run_main(self.argv()), 0)
        run.assert_not_called()

    def test_invalid_source_selection_fails_before_collection(self) -> None:
        for selected, message in (([], "INPUT_SOURCES"), (["bad"], "bad")):
            with self.subTest(selected=selected), mock.patch.object(config, "INPUT_SOURCES", selected):
                with mock.patch.object(pa, "collect_source") as collect:
                    with self.assertRaisesRegex(ValueError, message):
                        self.run_main(self.argv())
                collect.assert_not_called()

    def test_invalid_event_types_fail_before_collection(self) -> None:
        with (
            mock.patch.object(config, "EVENT_TYPES", []),
            mock.patch.object(pa, "collect_source") as collect,
            mock.patch.object(sys, "argv", self.argv()),
        ):
            with self.assertRaisesRegex(ValueError, "EVENT_TYPES"):
                pa.main()
        collect.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
