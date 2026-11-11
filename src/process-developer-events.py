#!/usr/bin/env python3
"""Build a markdown report of open + recently-closed CFPs from developers.events.

Fetches two public static datasets on every run:

* ``https://developers.events/all-cfps.json``
* ``https://developers.events/all-events.json``

Stale ``developers.events`` HTML is never scraped — the JSON is the source of
truth (the page bundle is a build-time snapshot with older ``until`` strings).
Filtering uses ``untilDate`` (epoch ms), not the free-form ``until`` string.

Typical usage::

    python3 src/process-all.py                                        # everything → data/
    python3 src/process-developer-events.py --out data --past-days 30
    python3 src/process-developer-events.py --out /tmp/scratch --today 2026-11-01 --months-back 1

Writes one markdown note per CFP into the ``--out`` **directory** (default
``data/``), reading live ``developers.events`` JSON. Filtering uses ``untilDate``
(epoch ms), not the free-form ``until`` string.

Legacy ``--months-back`` is kept as a 30×N days alias. The old single-file
``cfps.md`` report is retired (a copy lives in the excluded ``tmp/``).
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import os
import re
import sys
import subprocess
import urllib.request
from pathlib import Path

try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config as _cfg
    _IGNORE = [t.lower() for t in getattr(_cfg, "IGNORE_TOPICS", [])]
except Exception:
    _IGNORE = []
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SRC_URLS: Dict[str, str] = {
    "all-cfps.json": "https://developers.events/all-cfps.json",
    "all-events.json": "https://developers.events/all-events.json",
}

# Country-name overrides that pycountry misses or that appear verbatim in the
# feed.  Keys are lower-cased.  Values are ISO 3166-1 alpha-2.
COUNTRY_ALIASES: Dict[str, str] = {
    "usa": "US",
    "uk": "GB",
    "south korea": "KR",
    "czechia": "CZ",
    "democratic republic of the congo": "CD",
    "ivory coast": "CI",
    "hong kong": "HK",
    "kosovo": "XK",
    "turkey": "TR",
    "türkiye": "TR",
    "czech republic": "CZ",
    "south africa": "ZA",
    "united arab emirates": "AE",
    "dominican republic": "DO",
    "new zealand": "NZ",
    "bolivia": "BO",
    "tanzania": "TZ",
    "iran": "IR",
    "syria": "SY",
    "moldova": "MD",
    "laos": "LA",
    "brunei": "BN",
    "cape verde": "CV",
    "swaziland": "SZ",
    "macedonia": "MK",
    "venezuela": "VE",
    "vietnam": "VN",
    "russia": "RU",
    "saudi arabia": "SA",
    "costa rica": "CR",
    "sri lanka": "LK",
}

# Topics that mark a conference as AI-adjacent.  Bare ``data``/``analytics``
# are deliberately excluded — they pull in BI/SQL-Saturday meetups.
FOCUS_TAGS: List[str] = [
    "ai",
    "artificial-intelligence",
    "generative-ai",
    "genai",
    "machine-learning",
    "ml",
    "mlops",
    "deep-learning",
    "nlp",
    "llm",
    "llms",
    "agentic-ai",
    "agent-based-ai",
    "agents",
    "ai-agents",
    "ai-coding",
    "agentic-coding",
    "voice-agents",
    "inference",
    "copilot",
    "data-science",
    "prompt-engineering",
    "rag",
    "computer-vision",
]

# Name heuristic (word boundaries prevent "Dubai"/"Domain" false positives).
FOCUS_NAME_RE = re.compile(
    r"(?i)(^|[^a-z])"
    r"(ai|genai|llm|ml|machine[ -]learning|agent\w*|copilot|"
    r"deep[ -]learning|data[ -]scien\w*|neural)"
    r"([^a-z]|$)"
)

# Presentation constants — extracted so no backslashes leak into f-string
# expression slots (illegal before Python 3.12).
EM_DASH = chr(8212)            # —
EN_ARROW = "\u2192"             # →
MIDDLE_DOT = "\u00b7"           # ·
ROBOT = "\U0001f916"            # 🤖
EARTH = chr(0x1F30E)            # 🌎 (fallback for online events)
TABLE_HEADER = "| # | Conference | Event date | Location | submission | CFP close | Topics | Links / notes |"
TABLE_SEP = "|---|------------|-----------|----------|-----------|-----------|--------|----------------|"

# ---------------------------------------------------------------------------
# Optional: country flag support via pycountry
# ---------------------------------------------------------------------------

try:
    import pycountry  # type: ignore[import-not-found]

    _PYCOUNTRY_MAP: Dict[str, str] = {c.name.lower(): c.alpha_2 for c in pycountry.countries}
except Exception:
    _PYCOUNTRY_MAP = {}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def country_flag(country: str | None) -> str:
    """Return the flag emoji for *country* or ``""`` when unknown.

    ``COUNTRY_ALIASES`` is checked first, then ``pycountry`` (if installed).
    ``country`` may be ``None``/empty for online-only events.
    """
    key = (country or "").strip().lower()
    if not key:
        return ""
    code = COUNTRY_ALIASES.get(key) or _PYCOUNTRY_MAP.get(key)
    if not code:
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code.upper())


def normalize_name(name: str | None) -> str:
    """Lower-case alphanumeric fold — stable for CFP↔event matching."""
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def epoch_ms_to_date(epoch_ms: int) -> datetime.date:
    """Convert ``untilDate``/``date[]`` epoch-milliseconds to UTC date.

    Uses ``datetime.timezone.utc`` for Python 3.9+ compat (``datetime.UTC``
    only exists since 3.11).
    """
    return datetime.datetime.fromtimestamp(epoch_ms / 1000, datetime.timezone.utc).date()


def extract_country_from_location(location: str | None) -> str:
    """Trailing ``(Country)`` from ``"City (Country)"``, or ``""``.

    The location string is the reliable source; ``conf.country`` / ``country``
    in ``all-events.json`` is occasionally wrong (e.g. DevFest Faro labelled
    ``Lebanon``).
    """
    match = re.search(r"\(([^)]+)\)\s*$", location or "")
    return match.group(1).strip() if match else ""


def sanitize_misc(raw: str | None) -> str:
    """Strip HTML tags/entities from ``misc`` and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = text.replace("\\", " ").replace("&amp;", "&")
    return " ".join(text.split())


def escape_pipes(text: str | None) -> str:
    """Escape ``|`` so markdown tables don't split mid-cell."""
    return (text or "").replace("|", "\\|").strip()


def format_event_dates(dates_ms: List[int]) -> str:
    """Human-readable conference date: ``YYYY-MM-DD (Day)`` or range/TBA."""
    if not dates_ms:
        return "TBA"
    unique = sorted({epoch_ms_to_date(ms) for ms in dates_ms})
    if len(unique) == 1:
        return unique[0].strftime("%Y-%m-%d (%a)")
    return f"{unique[0].strftime('%Y-%m-%d')} {EN_ARROW} {unique[-1].strftime('%Y-%m-%d')}"


def event_date_start(dates_ms: List[int]) -> str:
    """Starting conference date only, clean ISO ``YYYY-MM-DD`` (or ``TBA``)."""
    if not dates_ms:
        return "TBA"
    return min(epoch_ms_to_date(ms) for ms in dates_ms).strftime("%Y-%m-%d")


def compute_cutoff(
    today: datetime.date,
    months_back: int = 1,
    days_back: Optional[int] = None,
) -> datetime.date:
    """Cutoff date for “recently closed”.

    Rolling-window mode (default): ``days_back=30`` → 30 days before *today*.
    When *days_back* is set (via ``--past-days``/``--days-back``) it wins.

    ``months_back`` is kept for backwards compatibility and is interpreted as
    ``30 × N`` days, so ``--months-back 1`` ≈ past 30 days (≈ no breakage vs
    the older calendar-month logic that snapped to the 1st).
    """
    if days_back is not None:
        return today - datetime.timedelta(days=days_back)
    # Back-compat: months → rolling days (requested behaviour is “past 30 days”)
    return today - datetime.timedelta(days=30 * max(1, months_back))


# ---------------------------------------------------------------------------
# I/O — fetch & cache
# ---------------------------------------------------------------------------


def fetch_json(cache_dir: str | os.PathLike[str], filename: str, url: str) -> Any:
    """Fetch *url* into ``cache_dir/filename`` and return parsed JSON.

    Prefers ``curl -fsSL`` (handles redirects / retries); falls back to
    ``urllib`` only when ``curl`` is absent *and* no cache exists.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    dest = cache_path / filename

    # curl writes even on slow/redirected endpoints; --fail avoids caching HTML.
    curl_ok = subprocess.run(["curl", "-fsSL", "-o", str(dest), url]).returncode == 0
    if not curl_ok and not dest.exists():
        urllib.request.urlretrieve(url, str(dest))

    with dest.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Merge CFP ↔ Event
# ---------------------------------------------------------------------------

# A row is intentionally a plain dict rather than a dataclass — it is rendered
# immediately and never crosses module boundaries.
Row = Dict[str, Any]


def build_event_index(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Index events by normalised ``name``; bare names repeat across editions."""
    index: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for event in events:
        index[normalize_name(event.get("name"))].append(event)
    return index


def select_best_event(
    candidates: List[Dict[str, Any]],
    target_location: str,
    close_date: datetime.date,
) -> Dict[str, Any]:
    """Pick the event edition that best matches the CFP entry.

    Ranking is (1) exact location match, (2) nearest edition on/after the
    deadline, (3) otherwise the most recent prior edition.  This avoids
    attaching a 2023 ``DevFest`` edition to a 2026 CFP.
    """

    def distance(event: Dict[str, Any]) -> Tuple[int, int, int]:
        loc = (event.get("location") or "").strip().lower()
        loc_penalty = 0 if loc == target_location else 1

        dates_ms: List[int] = event.get("date") or []
        if not dates_ms:
            return (loc_penalty, 2, 10**6)

        event_dates = [epoch_ms_to_date(ms) for ms in dates_ms]
        upcoming = [d for d in event_dates if d >= close_date]
        if upcoming:
            return (loc_penalty, 0, min((d - close_date).days for d in upcoming))
        return (loc_penalty, 1, (close_date - max(event_dates)).days)

    return sorted(candidates, key=distance)[0]


def build_rows(
    cfps: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    cutoff: datetime.date,
) -> List[Row]:
    """One enriched row per ``(conference, deadline)`` with ``close >= cutoff``.

    Deduplication key is ``(normalized name, close_date)`` — some exports
    duplicate the same deadline entry verbatim.  Enrichment pulls
    ``topics/languages/event_url/misc`` from the closest event edition via
    :func:`select_best_event`.
    """
    event_index = build_event_index(events)
    rows: List[Row] = []
    seen: Set[Tuple[str, datetime.date]] = set()

    for entry in cfps:
        # The feed marks every historical row "open" — date is the only filter.
        until_ms = entry.get("untilDate")
        if until_ms is None:
            continue
        close_date = epoch_ms_to_date(int(until_ms))
        if close_date < cutoff:
            continue

        conf = entry.get("conf") or {}
        if any(t in (conf.get("name") or "").lower() for t in _IGNORE):
            continue
        dedup_key = (normalize_name(conf.get("name")), close_date)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        loc = conf.get("location") or ""
        candidates = event_index.get(normalize_name(conf.get("name")), [])
        event: Dict[str, Any] = {}
        if candidates:
            event = select_best_event(candidates, loc.strip().lower(), close_date)
            loc = loc or event.get("location") or ""

        tags = event.get("tags") or []
        # De-duplicate topics while preserving order (some events repeat tags).
        topics = list(
            dict.fromkeys(
                t["value"] for t in tags if t.get("key") in ("tech", "topic") and t.get("value")
            )
        )
        if any(any(ig in (tp or "").lower() for ig in _IGNORE) for tp in topics):
            continue
        languages = [t["value"] for t in tags if t.get("key") == "language" and t.get("value")]
        country = extract_country_from_location(loc) or event.get("country") or ""
        online = "online" in (loc or "").lower() or (country or "").lower() == "online"

        rows.append(
            {
                "name": conf.get("name") or "",
                "close": close_date,
                "dates": event.get("date") or conf.get("date") or [],
                "loc": loc,
                "country": country,
                "flag": country_flag(country),
                "topics": topics,
                "languages": languages,
                "event_url": event.get("hyperlink") or "",
                "cfp_url": entry.get("link") or "",
                "durations": entry.get("durations") or [],
                "misc": sanitize_misc(event.get("misc")),
                "online": online,
            }
        )

    rows.sort(key=lambda r: (r["close"], r["name"].lower()))
    return rows


def is_focus_row(row: Row, focus_tags: Set[str]) -> bool:
    """Whether *row* belongs in the AI/agentic focus set."""
    if not focus_tags:
        return False
    if focus_tags.intersection(row.get("topics") or []):
        return True
    return bool(FOCUS_NAME_RE.search(row.get("name") or ""))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_table(rows: List[Row], focus_tags: Set[str], start: int = 1) -> str:
    """Render *rows* as the project's markdown table.

    The spec mandates 7 columns plus the row number; pipes in names are
    escaped and ``|`` splits use negative-lookbehind logic upstream — never
    change the escaping independently.
    """
    lines: List[str] = [TABLE_HEADER, TABLE_SEP]

    # Pre-compute link separators without embedding backslashes in f-string
    # expression parts (illegal before Python 3.12).
    link_sep = f" {MIDDLE_DOT} "
    note_sep = "; "

    for idx, row in enumerate(rows, start):
        # --- Links column: [site] · [CFP] ---
        link_bits: List[str] = []
        if row.get("event_url"):
            link_bits.append(f"[site]({row['event_url']})")
        if row.get("cfp_url"):
            link_bits.append(f"[CFP]({row['cfp_url']})")

        # --- Notes suffix: online / lang: … / talks: … / misc ---
        notes: List[str] = []
        if row.get("online"):
            notes.append("online")
        if row.get("languages"):
            notes.append("lang: " + "/".join(row["languages"]))
        if row.get("durations"):
            talk_parts = [part.split(":", 1)[1] + "min" for part in row["durations"]]
            notes.append("talks: " + ", ".join(talk_parts))
        if row.get("misc"):
            notes.append(row["misc"][:120])

        # Flag + location cell (🌎 sentinel for online when flag absent).
        flag_prefix = row.get("flag") or (EARTH if row.get("online") else "")
        location_cell = escape_pipes(f"{flag_prefix + ' ' if flag_prefix else ''}{row.get('loc', '')}")

        # Robot marker for AI-focus rows.
        marker = f"{ROBOT} " if focus_tags and row.get("focus") else ""
        conf_cell = escape_pipes(marker + row.get("name", ""))
        topics_raw = ", ".join(row.get("topics") or [])
        topics_cell = escape_pipes(topics_raw or EM_DASH)
        event_date_cell = format_event_dates(row.get("dates") or [])

        links_text = link_sep.join(link_bits) if link_bits else EM_DASH
        notes_text = note_sep.join(notes) if notes else EM_DASH
        links_notes_cell = f"{links_text} {EM_DASH} {notes_text}"

        lines.append(
            f"| {idx} | **{conf_cell}** | {event_date_cell} | {location_cell} | — | "
            f"**{row['close'].isoformat()}** | {topics_cell} | {links_notes_cell} |"
        )

    return "\n".join(lines)


def render_frontmatter(today: datetime.date) -> str:
    """Obsidian frontmatter — fixed three-tag shape."""
    return (
        "---\n"
        "type: cfp-watchlist\n"
        "title: Open CFPs \u2014 tech conferences (developers.events)\n"
        f"source: https://developers.events/#/{today.year}/cfp\n"
        f"generated: {today.isoformat()}\n"
        "tags:\n"
        "  - cfp\n"
        "  - conference\n"
        "  - speaking\n"
        "---\n\n"
    )


def render_document(
    *,
    today: datetime.date,
    cutoff: datetime.date,
    open_rows: List[Row],
    recent_rows: List[Row],
    all_rows: List[Row],
    focus_tags: Set[str] | None = None,
    include_frontmatter: bool,
) -> str:
    """Assemble the full markdown note from partitioned rows."""
    by_month = collections.Counter(r["close"].strftime("%Y-%m") for r in open_rows)
    by_month_str = ", ".join(f"{k}: {v}" for k, v in sorted(by_month.items()))

    frontmatter = render_frontmatter(today) if include_frontmatter else ""
    header = (
        f"# Open CFPs \u2014 tech conferences (from developers.events)\n\n"
        f"- **Source:** [developers.events](https://developers.events/#/{today.year}/cfp)"
        f" \u2014 [`all-cfps.json`](https://developers.events/all-cfps.json)"
        f" + [`all-events.json`](https://developers.events/all-events.json)"
        f" ([repo](https://github.com/scraly/developers-conferences-agenda))\n"
        f"- **Generated:** {today.isoformat()} (UTC dates from the source epochs)\n"
        f"- **Scope:** every CFP with a deadline on/after {cutoff.isoformat()}"
        f" \u2014 still open plus the past 90\u00a0days, since deadlines get extended.\n"
        f"- **Counts:** {len(open_rows)} still open \u00b7 {len(recent_rows)} closed in the past 90 days"
        f" \u00b7 {len(all_rows)} rows\n"
        f"- **Still-open by deadline month:** {by_month_str}\n"
        f"- **{ROBOT}** marks AI / agentic events (topics or conference name match the focus set).\n"
        f"- **Note:** the source publishes only CFP deadlines, not opening dates;"
        f" topics come from event tags (many small DevFests carry none)."
        f" Confirm on the linked CFP page.\n"
    )

    body = (
        "\n## How to update this report\n\n"
        "This note is generated \u2014 see [INSTRUCTIONS.md](INSTRUCTIONS.md) in this folder for how to refresh it.\n"
        f"\n## Upcoming CFPs ({len(open_rows)})\n\n"
        f"{render_table(open_rows, focus_tags or set() )}\n"
        f"\n## Closed in the past 90 days \u2014 check for extensions ({len(recent_rows)})\n\n"
        f"{render_table(recent_rows, focus_tags or set() )}\n"
    )

    return frontmatter + header + body


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an Obsidian markdown report of open CFPs from developers.events.",
    )
    parser.add_argument(
        "--out",
        default="data",
        help="Output directory for per-CFP markdown files (default: data).",
    )
    parser.add_argument(
        "--today",
        default=datetime.date.today().isoformat(),
        help="Override 'today' as YYYY-MM-DD (repro mode). Default: real today.",
    )
    parser.add_argument(
        "--months-back",
        type=int,
        default=3,
        help="Deprecated: approximate window as 30×N days. Prefer --past-days N. (default: 1 → 30 days).",
    )
    parser.add_argument(
        "--past-days",
        "--days-back",
        type=int,
        default=None,
        dest="past_days",
        help="Rolling window for 'recently closed' (default: 30 days). Overrides --months-back.",
    )
    parser.add_argument(
        "--focus-tags",
        default=",".join(FOCUS_TAGS),
        help="Comma-separated focus topics; disables with --no-focus.",
    )
    parser.add_argument(
        "--no-focus",
        action="store_true",
        help="Disable 🤖 AI/agentic marking entirely.",
    )
    parser.add_argument(
        "--no-frontmatter",
        action="store_true",
        help="Omit Obsidian YAML frontmatter.",
    )
    parser.add_argument(
        "--cache",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache"),
        help="Cache directory for the two JSON feeds (default: cfps/cache).",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Write the JSON list of note paths produced (relative to --out), for orphan detection.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not save a timestamped backup of the previous output file.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    today = datetime.date.fromisoformat(args.today)
    cutoff = compute_cutoff(today, args.months_back, args.past_days)

    cfps = fetch_json(args.cache, "all-cfps.json", SRC_URLS["all-cfps.json"])
    events = fetch_json(args.cache, "all-events.json", SRC_URLS["all-events.json"])

    rows = build_rows(cfps, events, cutoff)

    focus_set: Set[str] = set()
    if not args.no_focus:
        raw = (args.focus_tags or "").strip()
        focus_set = {t.strip() for t in raw.split(",") if t.strip()}

    for row in rows:
        row["focus"] = is_focus_row(row, focus_set)

    # Upcoming includes CFPs closed in the past 30 days (extensions happen).
    recent_cutoff = today - datetime.timedelta(days=30)
    open_rows = [r for r in rows if r["close"] >= recent_cutoff]
    recent_rows = [r for r in rows if r["close"] < recent_cutoff]
    focus_open = sum(1 for r in open_rows if r.get("focus"))
    focus_recent = sum(1 for r in recent_rows if r.get("focus"))

    document = render_document(
        today=today,
        cutoff=cutoff,
        open_rows=open_rows,
        recent_rows=recent_rows,
        all_rows=rows,
        focus_tags=focus_set,
        include_frontmatter=not args.no_frontmatter,
    )

    data_dir = Path(args.out).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cfp_writer import upsert_counted, summary_line, write_manifest

    counts = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    produced = []
    for r in rows:
        r.setdefault("source", "developers.events")
        r.setdefault("event_date", event_date_start(r.get("dates") or []))
        r.setdefault("cfp_close", r["close"].isoformat())
        r.setdefault("location", r.get("loc", ""))
        upsert_counted(data_dir, r, counts, produced)

    if args.manifest:
        write_manifest(Path(args.manifest), produced, data_dir)

    # A "skipped" row is already covered by another note; count it as current.
    print(summary_line("developers.events", len(rows), counts["new"], counts["updated"],
                       counts["unchanged"] + counts["skipped"]))



if __name__ == "__main__":
    main()
