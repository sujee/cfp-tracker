#!/usr/bin/env python3
"""Tests for additive synchronization of submission wikilinks into CFP notes."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer as cw  # noqa: E402


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sync = load_module(ROOT / "src" / "sync-submission-links.py", "sync_submission_links")


class SyncSubmissionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.data = self.root / "data"
        self.submissions = self.root / "submissions"
        self.data.mkdir()
        self.submissions.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cfp(
        self,
        relative: str,
        submissions: list[str] | None = None,
        extra: str = "",
        body: str = "Keep this note body.\n",
    ) -> Path:
        path = self.data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        values = cw._yaml_list(submissions or [])
        path.write_text(
            "---\n"
            "type: cfp\n"
            f"event_name: {path.stem}\n"
            f"submissions: {values}\n"
            "created: 2026-11-01T00:00:00\n"
            "updated: 2026-11-01T00:00:00\n"
            f"{extra}---\n\n## Notes\n\n{body}",
            encoding="utf-8",
        )
        return path

    def submission(
        self,
        relative: str,
        references,
        note_type: str = "talk-submission",
    ) -> Path:
        path = self.submissions / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = cw._yaml_list(references) if isinstance(references, list) else cw._yaml_str(references)
        path.write_text(
            "---\n"
            f"type: {note_type}\n"
            f"cfp: {rendered}\n"
            "status: submitted\n"
            "---\n\nSubmission body remains unchanged.\n",
            encoding="utf-8",
        )
        return path

    def run_sync(self) -> sync.SyncPlan:
        plan = sync.build_plan(self.data, self.submissions)
        sync.apply_plan(plan)
        return plan

    def run_cli(self, *extra: str) -> tuple[int, str, str]:
        command = [
            sys.executable,
            str(ROOT / "src" / "sync-submission-links.py"),
            "--data",
            str(self.data),
            "--submissions",
            str(self.submissions),
            *extra,
        ]
        process = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
        return process.returncode, process.stdout, process.stderr

    def submissions_of(self, path: Path) -> list[str]:
        return cw._read_submissions(cw._read_frontmatter(path)[0])

    def test_adds_both_supported_submission_types(self) -> None:
        cfp = self.cfp("2026/conf.md")
        first = self.submission("a-first.md", "[[2026/conf]]")
        second = self.submission("b-second.md", "[[conf]]", note_type="submission")
        first_before = first.read_text(encoding="utf-8")
        second_before = second.read_text(encoding="utf-8")

        plan = self.run_sync()

        self.assertEqual(plan.warnings, [])
        self.assertEqual(plan.submission_count, 2)
        self.assertEqual(plan.addition_count, 2)
        self.assertEqual(
            self.submissions_of(cfp), ["[[a-first]]", "[[b-second]]"]
        )
        self.assertEqual(first.read_text(encoding="utf-8"), first_before)
        self.assertEqual(second.read_text(encoding="utf-8"), second_before)

    def test_list_valued_cfp_populates_every_referenced_note(self) -> None:
        first = self.cfp("2026/first.md")
        second = self.cfp("2026/second.md")
        self.submission("shared.md", ["[[first]]", "[[second]]"])

        plan = self.run_sync()

        self.assertEqual(plan.addition_count, 2)
        self.assertEqual(self.submissions_of(first), ["[[shared]]"])
        self.assertEqual(self.submissions_of(second), ["[[shared]]"])

    def test_preserves_existing_entries_and_unrelated_content(self) -> None:
        cfp = self.cfp(
            "2026/conf.md",
            ["[[manual-entry]]"],
            extra="priority: high # keep this comment\n",
            body="A hand-written note.\n",
        )
        self.submission("new-submission.md", "[[conf]]")

        self.run_sync()

        text = cfp.read_text(encoding="utf-8")
        frontmatter, _body = cw._read_frontmatter(cfp)
        self.assertEqual(
            self.submissions_of(cfp), ["[[manual-entry]]", "[[new-submission]]"]
        )
        self.assertIn("priority: high # keep this comment", text)
        self.assertIn("A hand-written note.", text)
        self.assertEqual(cw._as_str(frontmatter["created"]), "2026-11-01T00:00:00")
        self.assertEqual(cw._as_str(frontmatter["updated"]), "2026-11-01T00:00:00")

    def test_resolves_aliases_paths_extensions_and_headings(self) -> None:
        cfp = self.cfp("2026/conf.md")
        self.submission("path-link.md", "[[2026/conf.md|Event name]]")
        self.submission("heading-link.md", "[[conf#Notes]]")

        plan = self.run_sync()

        self.assertEqual(plan.warnings, [])
        self.assertEqual(
            self.submissions_of(cfp), ["[[heading-link]]", "[[path-link]]"]
        )

    def test_path_reference_disambiguates_duplicate_stems(self) -> None:
        old = self.cfp("2026/conf.md")
        current = self.cfp("2027/conf.md")
        self.submission("current-submission.md", "[[2027/conf]]")

        plan = self.run_sync()

        self.assertEqual(plan.warnings, [])
        self.assertEqual(self.submissions_of(old), [])
        self.assertEqual(self.submissions_of(current), ["[[current-submission]]"])

    def test_nested_submission_paths_remain_distinct(self) -> None:
        cfp = self.cfp("2026/conf.md")
        self.submission("a/talk.md", "[[conf]]")
        self.submission("b/a/talk.md", "[[conf]]")

        plan = self.run_sync()

        self.assertEqual(plan.addition_count, 2)
        self.assertEqual(self.submissions_of(cfp), ["[[a/talk]]", "[[b/a/talk]]"])

    def test_arbitrary_cfp_path_prefix_is_unresolved(self) -> None:
        cfp = self.cfp("2026/conf.md")
        self.submission("bad-prefix.md", "[[wrong/2026/conf]]")

        code, _output, errors = self.run_cli()

        self.assertEqual(code, 1)
        self.assertIn("unresolved cfp reference", errors)
        self.assertEqual(self.submissions_of(cfp), [])

    def test_unique_shortened_existing_path_is_not_duplicated(self) -> None:
        cfp = self.cfp("2026/conf.md", ["[[talk|Existing alias]]"])
        self.submission("nested/talk.md", "[[conf]]")
        before = cfp.read_text(encoding="utf-8")

        plan = self.run_sync()

        self.assertEqual(plan.changes, [])
        self.assertEqual(cfp.read_text(encoding="utf-8"), before)

    def test_existing_alias_is_not_duplicated_and_is_not_reformatted(self) -> None:
        cfp = self.cfp("2026/conf.md", ["[[new-talk|Existing alias]]"])
        self.submission("new-talk.md", "[[conf]]")
        before = cfp.read_text(encoding="utf-8")

        plan = self.run_sync()

        self.assertEqual(plan.changes, [])
        self.assertEqual(cfp.read_text(encoding="utf-8"), before)

    def test_second_run_is_a_byte_and_mtime_noop(self) -> None:
        cfp = self.cfp("2026/conf.md")
        self.submission("new-submission.md", "[[conf]]")
        self.run_sync()
        before = cfp.read_text(encoding="utf-8")
        before_mtime = cfp.stat().st_mtime_ns

        second = self.run_sync()

        self.assertEqual(second.changes, [])
        self.assertEqual(second.unchanged_count, 1)
        self.assertEqual(cfp.read_text(encoding="utf-8"), before)
        self.assertEqual(cfp.stat().st_mtime_ns, before_mtime)

    def test_check_reports_changes_without_writing(self) -> None:
        cfp = self.cfp("2026/conf.md")
        self.submission("new-submission.md", "[[conf]]")
        before = cfp.read_text(encoding="utf-8")

        code, output, errors = self.run_cli("--check")

        self.assertEqual(code, 0, errors)
        self.assertIn("would update", output)
        self.assertIn("+ [[new-submission]]", output)
        self.assertIn("would add 1 link", output)
        self.assertEqual(cfp.read_text(encoding="utf-8"), before)

    def test_unresolved_and_ambiguous_references_are_not_guessed(self) -> None:
        first = self.cfp("2026/conf.md")
        second = self.cfp("2027/conf.md")
        self.submission("ambiguous.md", "[[conf]]")
        self.submission("missing.md", "[[not-on-disk]]")

        code, _output, errors = self.run_cli()

        self.assertEqual(code, 1)
        self.assertIn("ambiguous cfp reference", errors)
        self.assertIn("unresolved cfp reference", errors)
        self.assertEqual(self.submissions_of(first), [])
        self.assertEqual(self.submissions_of(second), [])

    def test_malformed_notes_are_reported_and_left_untouched(self) -> None:
        bad_cfp = self.cfp("2026/bad.md")
        bad_cfp.write_text("---\ntype: cfp\nbroken: [yaml\n---\n", encoding="utf-8")
        bad_submission = self.submission("bad-submission.md", "[[ignored]]")
        bad_submission.write_text(
            "---\ntype: talk-submission\ncfp: [yaml\n---\n", encoding="utf-8"
        )
        bad_cfp_before = bad_cfp.read_text(encoding="utf-8")
        bad_submission_before = bad_submission.read_text(encoding="utf-8")
        valid = self.cfp("2026/valid.md")
        self.submission("valid-submission.md", "[[valid]]")

        plan = self.run_sync()

        self.assertEqual(len(plan.warnings), 2)
        self.assertTrue(any("unreadable CFP note" in item for item in plan.warnings))
        self.assertTrue(any("unreadable submission note" in item for item in plan.warnings))
        self.assertEqual(bad_cfp.read_text(encoding="utf-8"), bad_cfp_before)
        self.assertEqual(bad_submission.read_text(encoding="utf-8"), bad_submission_before)
        self.assertEqual(self.submissions_of(valid), ["[[valid-submission]]"])

    def test_new_links_round_trip_as_safe_yaml(self) -> None:
        cfp = self.cfp("2026/conf.md")
        self.submission('Agentics Day: MCP + "Agents".md', "[[conf]]")

        self.run_sync()

        self.assertEqual(
            self.submissions_of(cfp), ['[[Agentics Day: MCP + "Agents"]]']
        )
        self.assertIn('submissions: ["[[Agentics Day: MCP', cfp.read_text(encoding="utf-8"))

    def test_ignores_other_note_types_and_reports_missing_cfp(self) -> None:
        ignored_cfp = self.data / "not-a-cfp.md"
        ignored_cfp.write_text("---\ntype: meeting\n---\n", encoding="utf-8")
        self.submission("talk-note.md", "[[not-a-cfp]]", note_type="talk")
        self.submission("missing-reference.md", [])

        plan = self.run_sync()

        self.assertEqual(plan.submission_count, 1)
        self.assertEqual(plan.addition_count, 0)
        self.assertEqual(len(plan.warnings), 1)
        self.assertIn("missing cfp reference", plan.warnings[0])

    def test_missing_directory_returns_2(self) -> None:
        missing = self.root / "missing"
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "src" / "sync-submission-links.py"),
                "--data",
                str(missing),
                "--submissions",
                str(self.submissions),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("directory not found", process.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
