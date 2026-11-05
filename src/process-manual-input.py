#!/usr/bin/env python3
"""Merge manually curated conference info from input/*.md into per-CFP files."""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import unquote

URL_RE = re.compile(r"https?://[^\s)\]<>\"']+", re.IGNORECASE)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
# Markdown link in a table cell: ``[text](url)`` (optional title).
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_EMPH_RE = re.compile(r"[*_]{1,3}")

_CLOSE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y")


def _clean_name(raw: str) -> tuple[str, str]:
    """Return ``(display name, url)`` from a cell like ``**[Name](url)**``.

    Without this the markdown source leaks into the name and the slug (a Google
    redirect URL became part of the filename).
    """
    raw = (raw or "").strip()
    m = _MD_LINK_RE.search(raw)
    if m:
        name, url = m.group(1), m.group(2)
    else:
        name, url = raw, ""
    name = re.sub(r"\s+", " ", _EMPH_RE.sub("", name)).strip()
    return name, url


def _unwrap_url(url: str) -> str:
    """Return the real target of a Google redirect wrapper, else *url* itself."""
    if not url:
        return ""
    if "google.com/url" in url:
        m = re.search(r"[?&]q=([^&]+)", url)
        if m:
            return unquote(m.group(1))
    return url


def _normalize_close(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return "—"
    for fmt in _CLOSE_FORMATS:
        try:
            return __import__("datetime").datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    # No exact date: drop "Unstated" qualifiers, e.g. "Dec 2026 / Unstated" -> "Dec 2026".
    parts = [p.strip() for p in raw.split("/") if p.strip() and "unstated" not in p.lower()]
    if not parts:
        return "Unstated"
    text = " / ".join(parts)
    for fmt in _CLOSE_FORMATS:
        try:
            return __import__("datetime").datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def extract_urls(text: str) -> list[str]:
    urls = []
    seen = set()
    for m in URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:!?")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def fetch_title(url: str, timeout: int = 10) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cfp-merge/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(200_000).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    m = OG_TITLE_RE.search(html)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m = TITLE_RE.search(html)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def parse_rows(text: str) -> list[dict]:
    rows = []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import config as _cfg
        _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]
    except Exception:
        _IGNORE = []

    for line in text.splitlines():
        if line.strip().startswith("|") and "|" in line:
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) >= 5 and not cols[0].lower().startswith("conf name") and not set(cols[0]) <= set("-: "):
                name, url = _clean_name(cols[0])
                if not name or "would you like" in name.lower():
                    continue
                if any(t in name.lower() for t in _IGNORE):
                    continue
                rows.append(
                    {
                        "name": name,
                        "location": cols[1] if len(cols) > 1 else "",
                        "cfp_close": _normalize_close(cols[3] if len(cols) > 3 else ""),
                        "event_date": cols[4] if len(cols) > 4 else "",
                        "topics": cols[5] if len(cols) > 5 else "",
                        "event_url": _unwrap_url(url),
                        "cfp_url": "",
                    }
                )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--input", default="input")
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args()

    base = Path(".").resolve()
    input_dir = (base / args.input).resolve()
    data_dir = (base / args.out).resolve()

    if not input_dir.is_dir():
        print(f"input directory not found: {input_dir}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import upsert_counted, parse_start_date, summary_line, write_manifest

    rows = []
    for md in sorted(input_dir.glob("*.md")):
        rows.extend(parse_rows(md.read_text(encoding="utf-8")))

    counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    produced = []
    for r in rows:
        row = {
            "name": r["name"],
            "event_date": parse_start_date(r["event_date"]) or r["event_date"] or "—",
            "location": r["location"] or "—",
            "country": "",
            "cfp_close": r["cfp_close"] or "—",
            "topics": [t.strip() for t in (r["topics"] or "").split(",") if t.strip()],
            "event_url": r["event_url"],
            "cfp_url": r["cfp_url"],
            "source": "manual",
        }
        upsert_counted(data_dir, row, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    print(summary_line("manual input", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
