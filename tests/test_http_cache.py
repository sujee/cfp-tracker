#!/usr/bin/env python3
"""Tests for validation in the shared online-first HTTP cache."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import http_cache


class TestFetchValidation(unittest.TestCase):
    def test_invalid_live_json_uses_and_preserves_a_valid_cached_response(self) -> None:
        cached = {"cfps": []}
        cached_text = json.dumps(cached, indent=2)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            dest = cache / "feed.json"
            dest.write_text(cached_text, encoding="utf-8")
            response = io.BytesIO(b'{"message": "temporarily unavailable"}')
            with (
                mock.patch("http_cache.urllib.request.urlopen", return_value=response),
                mock.patch("http_cache.write_text_atomic") as write,
                redirect_stderr(io.StringIO()) as errors,
            ):
                result = http_cache.fetch_json(
                    "https://example.test/feed.json",
                    cache,
                    "feed.json",
                    source="test-source",
                    validator=lambda data: isinstance(data, dict) and "cfps" in data,
                )
            self.assertEqual(result, cached)
            self.assertEqual(dest.read_text(encoding="utf-8"), cached_text)
            write.assert_not_called()
            self.assertIn("test-source", errors.getvalue())
            self.assertIn("cache fallback", errors.getvalue())

    def test_validation_failure_without_a_cache_raises_the_source_error(self) -> None:
        response = io.BytesIO(b'{"message": "temporarily unavailable"}')
        with mock.patch("http_cache.urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "test-source: invalid feed"):
                http_cache.fetch_json(
                    "https://example.test/feed.json",
                    validator=self._reject_feed,
                )

    def test_offline_cache_must_pass_the_same_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "feed.json").write_text(
                '{"message": "temporarily unavailable"}', encoding="utf-8"
            )
            with mock.patch("http_cache.urllib.request.urlopen") as fetch:
                with self.assertRaisesRegex(ValueError, "test-source: invalid feed"):
                    http_cache.fetch_json(
                        "https://example.test/feed.json",
                        cache,
                        "feed.json",
                        offline=True,
                        validator=self._reject_feed,
                    )
            fetch.assert_not_called()

    @staticmethod
    def _reject_feed(data) -> bool:
        if not isinstance(data, dict) or not isinstance(data.get("cfps"), list):
            raise ValueError("test-source: invalid feed")
        return True


if __name__ == "__main__":
    unittest.main(verbosity=2)
