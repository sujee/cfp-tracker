#!/usr/bin/env python3
"""Tests for default settings and config_local.py overrides in src/config.py."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer
import config


class TestLocalOverrides(unittest.TestCase):
    def test_missing_file_returns_no_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config_local.py"
            self.assertEqual(config.local_overrides(path), {})

    def test_valid_settings_are_returned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config_local.py"
            path.write_text(
                'INPUT_SOURCES = ["manual"]\n'
                "IGNORE_TOPICS = []\n"
                '_helper = "not a setting"\n',
                encoding="utf-8",
            )
            self.assertEqual(
                config.local_overrides(path),
                {"INPUT_SOURCES": ["manual"], "IGNORE_TOPICS": []},
            )

    def test_unknown_setting_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config_local.py"
            path.write_text('IGNORE_NAME = [".NET"]\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "IGNORE_NAME"):
                config.local_overrides(path)

    def test_public_imports_are_not_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config_local.py"
            path.write_text(
                "from pathlib import Path\nhelper = Path('input')\n",
                encoding="utf-8",
            )
            self.assertEqual(config.local_overrides(path), {})

    def test_syntax_error_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config_local.py"
            path.write_text("INPUT_SOURCES = [\n", encoding="utf-8")
            with self.assertRaises(SyntaxError):
                config.local_overrides(path)

    def test_runtime_error_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config_local.py"
            path.write_text("INPUT_SOURCES = 1 / 0\n", encoding="utf-8")
            with self.assertRaises(ZeroDivisionError):
                config.local_overrides(path)

    def test_example_configuration_has_no_personal_inputs_or_filters(self) -> None:
        values = config.local_overrides(ROOT / "src" / "config_local.example.py")
        self.assertEqual(values["MANUAL_INPUT_FILES"], [])
        self.assertEqual(values["IGNORE_NAMES"], [])
        self.assertEqual(values["IGNORE_TOPICS"], [])

    def test_default_local_file_is_next_to_default_config(self) -> None:
        self.assertEqual(
            config.LOCAL_CONFIG_PATH,
            Path(config.__file__).resolve().with_name("config_local.py"),
        )

    def test_writer_does_not_hide_an_import_error_inside_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.py").write_text(
                "import definitely_missing_cfp_dependency\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            proc = subprocess.run(
                [sys.executable, "-c", "import cfp_writer"],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("definitely_missing_cfp_dependency", proc.stderr)


class TestEffectiveConfiguration(unittest.TestCase):
    def test_settings_pass_writer_validation(self) -> None:
        self.assertTrue(config.INPUT_SOURCES)
        self.assertIsInstance(config.MANUAL_INPUT_FILES, list)
        self.assertTrue(config.EVENT_TYPES)
        for event_type in config.EVENT_TYPES:
            self.assertTrue(cfp_writer._event_type_included(event_type))
        self.assertTrue(cfp_writer._event_type_patterns())
        cfp_writer._ignored_names()

    def test_filter_settings_reject_strings_as_collections(self) -> None:
        from unittest import mock

        for name in ("IGNORE_NAMES", "IGNORE_TOPICS", "CONFS_TECH_TOPICS"):
            with self.subTest(name=name), mock.patch.object(config, name, "ai"):
                with self.assertRaisesRegex(ValueError, name):
                    config.validate_filter_settings()

    def test_filter_settings_reject_blank_entries(self) -> None:
        from unittest import mock

        for name in ("IGNORE_NAMES", "IGNORE_TOPICS", "CONFS_TECH_TOPICS"):
            for value in ([""], ["  "], [None]):
                with self.subTest(name=name, value=value), mock.patch.object(config, name, value):
                    with self.assertRaisesRegex(ValueError, name):
                        config.validate_filter_settings()

    def test_empty_filter_collections_are_allowed(self) -> None:
        from unittest import mock

        for name in ("IGNORE_NAMES", "IGNORE_TOPICS", "CONFS_TECH_TOPICS"):
            with self.subTest(name=name), mock.patch.object(config, name, []):
                config.validate_filter_settings()


if __name__ == "__main__":
    unittest.main(verbosity=2)
