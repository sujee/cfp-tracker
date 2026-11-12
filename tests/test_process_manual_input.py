#!/usr/bin/env python3
"""Tests for src/process-manual-input.py using real sample data.

Run from the project folder:

    python3 -m unittest discover -s tests -v

Offline. ``tests/fixtures/manual/input.sample.md`` is a copy of the real
``input/gmail1.md`` table (regenerate with ``tests/fixtures/extract_fixtures.py``).
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
import config  # noqa: E402  shared by src manuals and tests config patches

SAMPLE = (FIX / "input.sample.md").read_text(encoding="utf-8")


def run_manual_cli(arguments: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run the real CLI without depending on the developer's local config."""
    src_dir = ROOT / "src"
    code = (
        "import runpy, sys\n"
        f"sys.path.insert(0, {str(src_dir)!r})\n"
        "import config\n"
        "config.MANUAL_INPUT_FILES = ['gmail1.md', 'conferences-to-check.md']\n"
        f"runpy.run_path({str(src_dir / 'process-manual-input.py')!r}, run_name='__main__')\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code, *arguments],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


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


class TestManualInputFiles(unittest.TestCase):
    def test_only_listed_files_are_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in ("kept.md", "ignored.md"):
                (directory / name).write_text(SAMPLE, encoding="utf-8")
            with mock.patch.object(config, "MANUAL_INPUT_FILES", ["kept.md"]):
                files = pmi.manual_input_files(directory)
            self.assertEqual([p.name for p in files], ["kept.md"])

    def test_missing_configured_file_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(config, "MANUAL_INPUT_FILES", ["typo.md"]):
                with self.assertRaisesRegex(FileNotFoundError, "typo.md"):
                    pmi.manual_input_files(Path(tmp))

    def test_absolute_and_parent_paths_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for value in ("/etc/passwd", "../gmail1.md"):
                with self.subTest(value=value):
                    with mock.patch.object(config, "MANUAL_INPUT_FILES", [value]):
                        with self.assertRaisesRegex(ValueError, "inside"):
                            pmi.manual_input_files(Path(tmp))

    def test_empty_list_disables_manual_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(config, "MANUAL_INPUT_FILES", []):
                self.assertEqual(pmi.manual_input_files(Path(tmp)), [])

    def test_cli_reports_config_error_instead_of_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(config, "MANUAL_INPUT_FILES", ["typo.md"]):
                with mock.patch.object(sys, "argv", ["x", "--input", tmp, "--out", str(Path(tmp) / "data")]):
                    self.assertEqual(pmi.main(), 1)


class TestWatchlistEndToEnd(unittest.TestCase):
    """The manual CLI processes the checklist via a pre-seeded HTML cache, offline."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.input_dir = self.root / "input"
        self.input_dir.mkdir()
        self.out = self.root / "data"
        self.cache = self.root / "cache"
        self.cache.mkdir()
        shutil.copy(ROOT / "input" / "gmail1.md", self.input_dir / "gmail1.md")
        shutil.copy(ROOT / "input" / "conferences-to-check.md", self.input_dir / "conferences-to-check.md")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cache_page(self, url: str, fixture: str) -> None:
        import hashlib

        target = self.cache / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".html")
        target.write_text(
            (ROOT / "tests" / "fixtures" / "watchlist" / fixture).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def run_cli(self) -> subprocess.CompletedProcess:
        return run_manual_cli(
            [
                "--out", str(self.out), "--input", str(self.input_dir),
                "--cache", str(self.cache),
            ],
            cwd=str(ROOT),
        )

    def test_writes_table_and_discovered_notes_offline(self) -> None:
        self.cache_page("https://ai.engineer/", "no-cfp.html")
        self.cache_page("https://www.humanx.co/", "humanx-site.html")
        self.cache_page("https://www.humanx.co/europe/become-a-speaker", "humanx-speaker.html")
        self.cache_page("https://newyork.theaisummit.com/", "aisummit-site.html")
        self.cache_page("https://newyork.theaisummit.com/conference-speakers/call-for-papers/", "aisummit-cfp.html")
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("watchlist: 2 CFP link(s) found, 1 unresolved", proc.stdout)
        self.assertIn("found 7 (new 7, updated 0, unchanged 0)", proc.stdout)
        human = self.out / "2027/2027_humanx-amsterdam-2027.md"
        self.assertTrue(human.is_file())
        self.assertIn("event_date: 2027-09-20", human.read_text())
        summit = self.out / "2026/2026_the-ai-summit-new-york.md"
        self.assertIn("cfp_close: Unstated", summit.read_text())

    def test_invalid_today_fails_before_any_fetch_or_write(self) -> None:
        with mock.patch.object(sys, "argv", [
            "x", "--out", str(self.out), "--input", str(self.input_dir),
            "--today", "2026-11-32",
        ]):
            self.assertEqual(pmi.main(), 1)
        self.assertFalse(list(self.out.rglob("*.md")))

    def test_fetch_failure_does_not_write_partial_notes(self) -> None:
        # Only the failing AI Engineer cache when the actual checklist has three
        # sites: one missing page is fatal, rather than a reason to archive notes.
        with (
            mock.patch.object(pmi.watchlist, "resolve", return_value=pmi.watchlist.CfpResult(
                "Down", "https://down.example", error="TimeoutError", failed=True
            )),
            mock.patch.object(config, "MANUAL_INPUT_FILES", [
                "gmail1.md", "conferences-to-check.md",
            ]),
            mock.patch.object(sys, "argv", [
                "x", "--out", str(self.out), "--input", str(self.input_dir),
            ]),
        ):
            self.assertEqual(pmi.main(), 1)
        self.assertFalse(list(self.out.rglob("*.md")))


class TestMainEndToEnd(unittest.TestCase):
    def test_runs_offline_and_writes_only_the_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data"
            input_dir = Path(tmp) / "input"
            input_dir.mkdir()
            # The test config names gmail1.md; an identically-shaped table next
            # to it is not a source just because it lands in the directory.
            shutil.copy(FIX / "input.sample.md", input_dir / "gmail1.md")
            shutil.copy(FIX / "input.sample.md", input_dir / "scratch.md")
            # The configured checklist exists, but no links means this table-only
            # test must not need the network. The duplicate scratch table is not.
            (input_dir / "conferences-to-check.md").write_text("# Nothing selected\n")
            proc = run_manual_cli(["--out", str(out), "--input", str(input_dir)])
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
            self.assertIn("\nevent_name: Agentic AI Summit 2027\n", agentic)
            self.assertNotIn("google.com/url", agentic)
            self.assertIn("source: manual", notes[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
