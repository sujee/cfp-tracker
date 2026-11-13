"""Small online-first HTTP cache shared by source adapters and watchlists."""
from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable


Validator = Callable[[Any], object]


USER_AGENT = "cfp-merge/1.0"


def write_text_atomic(dest: Path, text: str) -> None:
    """Replace *dest* only after a complete temporary-file write succeeds."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dest.parent,
            prefix=f".{dest.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp.write(text)
            temp_name = temp.name
        Path(temp_name).replace(dest)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def _destination(cache_path: Path | None, cache_key: str | None) -> Path | None:
    return cache_path / cache_key if cache_path and cache_key else None


def _offline_destination(dest: Path | None) -> Path:
    if dest is None:
        raise ValueError("offline mode requires a cache path and cache key")
    if not dest.is_file():
        raise FileNotFoundError(f"offline mode requires cached response: {dest}")
    return dest


def _validate(value, validator: Validator | None):
    if validator is not None and not validator(value):
        raise ValueError("response validation failed")
    return value


def _cached_json(dest: Path, url: str, validator: Validator | None = None):
    try:
        value = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid cached JSON for {url} at {dest}: {exc}") from exc
    return _validate(value, validator)


def _cached_text(dest: Path, url: str, validator: Validator | None = None) -> str:
    try:
        value = dest.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"invalid cached text for {url} at {dest}: {exc}") from exc
    return _validate(value, validator)


def _fallback(
    dest: Path | None,
    url: str,
    source: str,
    error: Exception,
    reader,
    validator: Validator | None,
):
    if dest is None or not dest.is_file():
        raise error
    try:
        value = reader(dest, url, validator)
    except ValueError as cache_error:
        raise ValueError(
            f"fetch failed for {url}: {error}; cache fallback is unavailable: {cache_error}"
        ) from error
    print(
        f"{source}: fetch failed for {url}: {error}; using cache fallback {dest}",
        file=sys.stderr,
    )
    return value


def fetch_json(
    url: str,
    cache_path: Path | None = None,
    cache_key: str | None = None,
    *,
    offline: bool = False,
    source: str = "cfp",
    accept: str = "application/json",
    validator: Validator | None = None,
):
    """Read live JSON first, with a validated cached fallback on failure."""
    dest = _destination(cache_path, cache_key)
    if offline:
        return _cached_json(_offline_destination(dest), url, validator)
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": accept}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        _validate(data, validator)
    except Exception as fetch_error:
        return _fallback(dest, url, source, fetch_error, _cached_json, validator)
    if dest is not None:
        write_text_atomic(dest, json.dumps(data))
    return data


def fetch_text(
    url: str,
    cache_path: Path | None = None,
    cache_key: str | None = None,
    *,
    offline: bool = False,
    source: str = "cfp",
    validator: Validator | None = None,
) -> str:
    """Read live text first, with a validated cached fallback on failure."""
    dest = _destination(cache_path, cache_key)
    if offline:
        return _cached_text(_offline_destination(dest), url, validator)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8", errors="replace")
        _validate(text, validator)
    except Exception as fetch_error:
        return _fallback(dest, url, source, fetch_error, _cached_text, validator)
    if dest is not None:
        write_text_atomic(dest, text)
    return text
