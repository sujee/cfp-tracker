#!/usr/bin/env python3
"""Check event and submission URLs in CFP notes or one Markdown report.

Exit 1 means at least one confirmed dead link (404/410). Exit 2 means one or
more notes could not be read, so verification is incomplete. Authentication,
rate limits, network errors, and other statuses stay unknown rather than
becoming false claims that a conference or submission page is gone.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "cfp-tracker-link-check/1.0"}
LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
BARE = re.compile(r"(?<![(\w])(https?://[^\s)|<>\"']+)")
TRAILING = ",.;:!?"


def urls_in(text, only=None):
    """Extract URLs from Markdown using the legacy report-compatible parser."""
    found = set(LINK.findall(text)) | set(BARE.findall(text))
    clean = {url.rstrip(TRAILING) for url in found}
    if only:
        clean = {url for url in clean if only in url}
    return sorted(clean)


def urls_from_path(path: Path, only=None, *, unverified=None):
    """Read CFP/event URLs, optionally collecting ``(note, error)`` failures.

    A single Markdown file remains supported for older aggregate reports. Note
    parsing and read errors raise by default. The CLI supplies *unverified* so
    it can report every unreadable note instead of silently returning no URLs.
    """
    path = Path(path)
    if path.is_file():
        return urls_in(path.read_text(encoding="utf-8"), only)
    if not path.is_dir():
        raise FileNotFoundError(f"report or notes directory not found: {path}")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import _as_str, _read_frontmatter

    urls = set()
    for note in sorted(path.rglob("*.md")):
        try:
            fm, _body = _read_frontmatter(note)
        except (OSError, ValueError) as error:
            if unverified is None:
                raise
            unverified.append((note, error))
            continue
        if _as_str(fm.get("type")) != "cfp":
            continue
        for key in ("event_url", "cfp_url"):
            url = _as_str(fm.get(key)).strip()
            if url.startswith(("https://", "http://")) and (not only or only in url):
                urls.add(url)
    return sorted(urls)


def check(url, timeout):
    try:
        request = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return url, response.status, ""
    except urllib.error.HTTPError as error:
        return url, error.code, ""
    except Exception as error:
        return url, None, f"{type(error).__name__}: {error}"


def classify(results):
    """Partition (url, status, error) results into healthy, dead, and unknown."""
    groups = {"healthy": [], "dead": [], "unknown": []}
    for result in results:
        url, status, _error = result
        if status is not None and 200 <= status < 300:
            groups["healthy"].append(result)
        elif status in (404, 410):
            groups["dead"].append(result)
        else:
            groups["unknown"].append(result)
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", help="CFP notes directory or one Markdown report")
    ap.add_argument("--only", help="Substring filter, e.g. sessionize.com")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    unverified = []
    try:
        urls = urls_from_path(Path(args.path), args.only, unverified=unverified)
    except (OSError, ValueError) as error:
        print(f"check-links: {error}", file=sys.stderr)
        return 1
    print(
        f"checking {len(urls)} urls from {args.path}"
        + (f" (filter: {args.only})" if args.only else "")
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(lambda url: check(url, args.timeout), urls))

    groups = classify(results)
    for category in ("dead", "unknown"):
        for url, status, error in sorted(groups[category], key=lambda result: str(result[1])):
            label = str(status) if status is not None else "ERR"
            print(f"  {category.upper():7} {label:4} {url}" + (f" [{error}]" if error else ""))
    for note, error in unverified:
        print(f"  UNVERIFIED NOTE {note} [{type(error).__name__}: {error}]")
    print(
        f"healthy: {len(groups['healthy'])} | dead: {len(groups['dead'])} | "
        f"unknown: {len(groups['unknown'])} | unverified notes: {len(unverified)}"
    )
    if groups["dead"]:
        return 1
    return 2 if unverified else 0


if __name__ == "__main__":
    sys.exit(main())
