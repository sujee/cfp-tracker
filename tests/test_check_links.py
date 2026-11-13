#!/usr/bin/env python3
"""Tests for note-directory link discovery and response classification."""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer as writer


def load_checker():
    spec = importlib.util.spec_from_file_location("check_links", ROOT / "src/check-links.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


links = load_checker()


class LinkCheckerTest(unittest.TestCase):
    def test_reads_cfp_and_event_urls_from_note_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            row = {
                "name": "Example Summit 2027",
                "event_date": "2027-04-01",
                "cfp_close": "2027-01-01",
                "location": "Online",
                "source": "manual",
                "event_url": "https://example.test/event",
                "cfp_url": "https://example.test/cfp",
            }
            writer.upsert(data, row)
            (data / "project.md").write_text(
                "---\ntype: project\nlink: https://ignored.test\n---\n",
                encoding="utf-8",
            )
            self.assertEqual(
                links.urls_from_path(data),
                ["https://example.test/cfp", "https://example.test/event"],
            )
            self.assertEqual(
                links.urls_from_path(data, only="cfp"),
                ["https://example.test/cfp"],
            )

    def test_only_2xx_is_healthy_and_only_404_or_410_is_dead(self) -> None:
        results = [
            ("200", 200, ""),
            ("204", 204, ""),
            ("404", 404, ""),
            ("410", 410, ""),
            ("403", 403, ""),
            ("429", 429, ""),
            ("500", 500, ""),
            ("network", None, "TimeoutError"),
        ]
        groups = links.classify(results)
        self.assertEqual([item[0] for item in groups["healthy"]], ["200", "204"])
        self.assertEqual([item[0] for item in groups["dead"]], ["404", "410"])
        self.assertEqual(
            [item[0] for item in groups["unknown"]],
            ["403", "429", "500", "network"],
        )

    def test_malformed_note_is_unverified_and_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "bad.md").write_text(
                "---\ntype: cfp\nbroken: [yaml\n---\n", encoding="utf-8"
            )
            output = io.StringIO()
            with (
                mock.patch.object(sys, "argv", ["check-links.py", str(data)]),
                redirect_stdout(output),
            ):
                self.assertEqual(links.main(), 2)

            report = output.getvalue()
            self.assertIn("checking 0 urls", report)
            self.assertIn("UNVERIFIED NOTE", report)
            self.assertIn("bad.md", report)
            self.assertIn("FrontmatterError", report)
            self.assertIn("unverified notes: 1", report)

    def test_unreadable_note_is_unverified_and_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "unreadable.md").write_text("---\ntype: cfp\n---\n", encoding="utf-8")
            output = io.StringIO()
            with (
                mock.patch.object(writer, "_read_frontmatter", side_effect=OSError("permission denied")),
                mock.patch.object(sys, "argv", ["check-links.py", str(data)]),
                redirect_stdout(output),
            ):
                self.assertEqual(links.main(), 2)

            report = output.getvalue()
            self.assertIn("UNVERIFIED NOTE", report)
            self.assertIn("unreadable.md", report)
            self.assertIn("OSError: permission denied", report)
            self.assertIn("unverified notes: 1", report)

    def test_unknown_status_does_not_fail_the_command(self) -> None:
        with (
            mock.patch.object(links, "urls_from_path", return_value=["https://blocked.test"]),
            mock.patch.object(links, "check", return_value=("https://blocked.test", 403, "")),
            mock.patch.object(sys, "argv", ["check-links.py", "data"]),
        ):
            self.assertEqual(links.main(), 0)

    def test_dead_status_fails_the_command(self) -> None:
        with (
            mock.patch.object(links, "urls_from_path", return_value=["https://gone.test"]),
            mock.patch.object(links, "check", return_value=("https://gone.test", 404, "")),
            mock.patch.object(sys, "argv", ["check-links.py", "data"]),
        ):
            self.assertEqual(links.main(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
