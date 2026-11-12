#!/usr/bin/env python3
"""Tests for src/apply-prestige.py — stamping the curated `tier` onto notes.

Run from the project folder:

    python3 -m unittest discover -s tests -v

The contract: a note whose name matches a curated row gets a numeric ``tier``;
a note that matches nothing is left alone (so a hand-set tier survives); and a
second run changes nothing. ``--check`` never writes.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer as cw  # noqa: E402


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ap = load_module(ROOT / "src" / "apply-prestige.py", "apply_prestige")

TABLE = """# Ranking

| conf name | ranking | keywords |
| :--- | :---: | :--- |
| SREcon (USENIX) | 1 | srecon |
| Devoxx Belgium | 1 | devoxx belgium |
| Devoxx | 2 | devoxx |
| Conf42 | 3 | conf42 |
| AWS re:Invent | 1 | re invent |
"""


def row(name: str, **overrides) -> dict:
    base = {
        "name": name,
        "event_date": "2027-04-12",
        "location": "Seattle, WA",
        "country": "USA",
        "cfp_close": "2027-02-01",
        "topics": [],
        "event_url": "https://example.org/e",
        "cfp_url": f"https://example.org/{name.lower().replace(' ', '-')}/cfp",
        "source": "developers.events",
    }
    base.update(overrides)
    return base


class ApplyPrestigeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.table = self.root / "prestige.md"
        self.table.write_text(TABLE, encoding="utf-8")
        cw.reset_cfp_url_index()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def note(self, name: str, **overrides) -> Path:
        row_ = row(name, **overrides)
        status = cw.upsert(self.data, row_, today="2026-11-01")
        self.assertIn(status, ("new", "updated", "unchanged"))
        return cw.note_path(self.data, row_)

    def tier_of(self, path: Path):
        return cw._read_frontmatter(path)[0].get("tier")

    def run_cli(self, *extra) -> tuple[int, str, str]:
        import subprocess

        cmd = [
            sys.executable, str(ROOT / "src" / "apply-prestige.py"),
            "--data", str(self.data), "--list", str(self.table), *extra,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        return proc.returncode, proc.stdout, proc.stderr

    def test_stamps_a_matching_note_with_a_number(self) -> None:
        path = self.note("SREcon27 Americas")
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertIn("1 updated", out)
        self.assertEqual(self.tier_of(path), 1)  # an int, so Bases can compare it
        self.assertIn("\ntier: 1\n", path.read_text(encoding="utf-8"))

    def test_leaves_unmatched_notes_alone(self) -> None:
        path = self.note("Power Platform Days Barcelona 2026")
        before = path.read_text(encoding="utf-8")
        code, out, _err = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("1 unmatched", out)
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertIsNone(self.tier_of(path))

    def test_keeps_a_hand_set_tier_on_an_unmatched_note(self) -> None:
        path = self.note("Some Regional Conf 2027")
        cw.set_property(path, "tier", 2)
        code, out, _err = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("hand-set tier kept", out)
        self.assertEqual(self.tier_of(path), 2)

    def test_is_idempotent(self) -> None:
        self.note("SREcon27 Americas")
        self.assertEqual(self.run_cli()[0], 0)
        before = (self.root / "stamp.txt")
        paths = sorted(self.data.rglob("*.md"))
        snapshot = {p: p.read_text(encoding="utf-8") for p in paths}
        code, out, _err = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("0 updated", out)
        self.assertEqual({p: p.read_text(encoding="utf-8") for p in paths}, snapshot)
        self.assertFalse(before.exists())

    def test_lowest_tier_wins(self) -> None:
        path = self.note("Devoxx Belgium 2027")
        self.run_cli()
        self.assertEqual(self.tier_of(path), 1)

    def test_check_writes_nothing(self) -> None:
        path = self.note("SREcon27 Americas")
        before = path.read_text(encoding="utf-8")
        code, out, _err = self.run_cli("--check")
        self.assertEqual(code, 0)
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertIn("matches nothing", out)  # AWS re:Invent has no note here
        self.assertIn("SREcon (USENIX)", out)

    def test_check_reports_conflicts(self) -> None:
        notes = [(Path("x.md"), "Devoxx Belgium 2027", "")]
        rules = ap.prestige.load(self.table)
        report = "\n".join(ap.check_report(rules, notes, self.data))
        self.assertIn("Matched several rows", report)
        self.assertIn("Devoxx Belgium 2027 -> tier 1", report)
        self.assertIn("also tier 2 (Devoxx)", report)

    def test_missing_table_is_not_an_error(self) -> None:
        missing = self.root / "nope.md"
        import subprocess

        proc = subprocess.run(
            [
                sys.executable, str(ROOT / "src" / "apply-prestige.py"),
                "--data", str(self.data), "--list", str(missing),
            ],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no rules", proc.stdout)

    def test_bad_table_fails_with_a_pointer(self) -> None:
        self.table.write_text(
            "| conf name | ranking | keywords |\n|---|---|---|\n| FOSDEM | high | fosdem |\n",
            encoding="utf-8",
        )
        code, _out, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("prestige.md line 3", err)
        self.assertIn("not a number", err)

    def test_non_cfp_notes_are_ignored(self) -> None:
        other = self.data / "2027" / "a-meeting.md"
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_text("---\ntype: meeting\n---\n\nNot a CFP.\n", encoding="utf-8")
        self.assertEqual(self.run_cli()[0], 0)
        self.assertNotIn("tier:", other.read_text(encoding="utf-8"))

    def test_unparseable_note_is_skipped_not_clobbered(self) -> None:
        bad = self.data / "2027" / "broken.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("---\ntier: [oops\n---\n\n## Notes\n", encoding="utf-8")
        code, out, err = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("skipping unparseable", err)
        self.assertIn("skipped", out)
        self.assertIn("[oops", bad.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
