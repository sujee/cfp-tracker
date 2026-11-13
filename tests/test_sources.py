#!/usr/bin/env python3
"""Tests for canonical source metadata and shared collection context."""
from __future__ import annotations

import datetime
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cfp_writer
import sources


class SourceRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.context = sources.RunContext(
            today=datetime.date(2026, 11, 12),
            cutoff=datetime.date(2026, 10, 13),
            cache=root / "cache",
            input_dir=root / "input",
            offline=True,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_writer_and_wrapper_share_one_source_priority(self) -> None:
        self.assertEqual(cfp_writer.SOURCE_PRIORITY, sources.SOURCE_PRIORITY)
        self.assertEqual(len(sources.SOURCE_PRIORITY), len(sources.SOURCE_NAMES))

    def test_cutoff_uses_one_policy(self) -> None:
        self.assertEqual(
            sources.cutoff_for(datetime.date(2026, 11, 12), 2),
            datetime.date(2026, 9, 13),
        )
        self.assertEqual(
            sources.cutoff_for(datetime.date(2026, 11, 12), 99, 7),
            datetime.date(2026, 11, 5),
        )

    def test_network_adapter_receives_common_context(self) -> None:
        module = mock.Mock()
        module.collect_rows.return_value = [{"name": "Example"}]
        with mock.patch.object(sources, "load_source", return_value=module):
            rows = sources.collect_source("cfp.ninja", self.context)
        module.collect_rows.assert_called_once_with(
            self.context.cutoff,
            self.context.today,
            self.context.cache,
            offline=True,
        )
        self.assertEqual(rows, [{"name": "Example", "source": "cfp.ninja"}])

    def test_developer_adapter_returns_normalized_rows(self) -> None:
        module = mock.Mock()
        module.collect_rows.return_value = [{"name": "Example", "source": "developers.events"}]
        with mock.patch.object(sources, "load_source", return_value=module):
            rows = sources.collect_source("developers.events", self.context)
        module.collect_rows.assert_called_once_with(
            self.context.cutoff, self.context.cache, True
        )
        self.assertEqual(rows[0]["source"], "developers.events")

    def test_manual_adapter_receives_input_cache_today_and_offline(self) -> None:
        module = mock.Mock()
        module.collect_rows.return_value = [{"name": "Example", "source": "manual"}]
        with mock.patch.object(sources, "load_source", return_value=module):
            rows = sources.collect_source("manual", self.context)
        module.collect_rows.assert_called_once_with(
            self.context.input_dir,
            cache=self.context.cache,
            today=self.context.today,
            offline=True,
        )
        self.assertEqual(rows[0]["source"], "manual")


if __name__ == "__main__":
    unittest.main(verbosity=2)
