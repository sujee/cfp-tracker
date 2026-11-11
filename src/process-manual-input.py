#!/usr/bin/env python3
"""Merge manually curated conference info from input/*.md into per-CFP files."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

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


def parse_rows(text: str) -> list[dict]:
    rows = []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import config as _cfg
        _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]
    except Exception:
        _IGNORE = []

    for line in text.splitlines():
        if line.strip().startswith("|"):
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
                        "location": cols[1],
                        "cfp_close": _normalize_close(cols[3]),
                        "event_date": cols[4],
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
