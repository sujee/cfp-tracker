"""Shared helpers for writing one-markdown-file-per-CFP.

Frontmatter is written with every value YAML-quoted safely (``_yaml_str``); the
free-form ``notes`` live only in the note body, never in the frontmatter.

Reading is done with **PyYAML** (see ``requirements.txt``): the whole frontmatter
block is parsed into a dict, so flow/block lists, quoting and nested maps all
read correctly. Values keep their YAML types; ``_as_str`` / ``_as_list`` /
``_as_bool`` normalise the ones the writer cares about.
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

import yaml

try:
    from country import normalize_country
except ImportError:  # pragma: no cover - when src/ is not already on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from country import normalize_country

PRESERVED = {"shortlist", "submissions"}
NOTES_HEADING = "## Notes"
NOTES_PLACEHOLDER = "_Add notes here._"

# Frontmatter properties that are regenerated from the upstream row. ``upsert``
# compares these one by one against the existing note and skips the write when
# all of them already match, so a user's edits to the body, ``shortlist`` /
# ``submissions``, or any extra frontmatter survive an unchanged refresh.
SOURCE_SCALAR_FIELDS = (
    "name",
    "event_date",
    "location",
    "country",
    "cfp_close",
    "event_url",
    "cfp_url",
    "source",
)

# Source-owned list fields, compared as lists (semantic, order-sensitive).
LIST_FIELDS = ("topics", "benefits", "languages")

# Lower index = higher priority. Several conferences appear in more than one
# feed and map to the same slug; the lower-priority source must not overwrite the
# note a higher-priority one already owns (they disagree on location/country/source).
SOURCE_PRIORITY = {"manual": 0, "developers.events": 1, "cfp.ninja": 2, "confs.tech": 3}


def _source_priority(source: str) -> int:
    """Rank a source name; unknown sources rank lowest."""
    return SOURCE_PRIORITY.get((source or "").strip(), len(SOURCE_PRIORITY))


# Cross-source duplicates: two feeds can name the same conference differently
# ("SCaLE" vs "Southern California Linux Expo - SCaLE 24x"), so they slugify to
# *different* notes for one CFP and the same-slug :data:`SOURCE_PRIORITY` rule
# never fires. The submission page (``cfp_url``) identifies the CFP, so a row
# whose ``cfp_url`` is already owned under ``data/`` yields to that note — but
# only when the two names look like the same conference. Feeds also reuse one
# form for genuinely different events (JS Poland / NG Poland / AI Poland share a
# Google form; every Apidays city shares one Typeform; Dawn Conferences covers
# Appdevcon and Webdevcon), and merging on the URL alone would swallow them.
#
# Keyed by ``data_dir`` and built lazily by scanning the existing notes once per
# process (upsert is called hundreds of times a run, so a per-call scan would be
# wasteful). Entries are appended as notes are written during the run.
_CFP_URL_INDEX: dict[Path, dict[str, list[tuple[Path, str, str]]]] = {}

_YEAR_TOKEN_RE = re.compile(r"^(?:19|20)\d{2}$")


def reset_cfp_url_index() -> None:
    """Drop the cached ``cfp_url`` index (tests build notes on disk directly)."""
    _CFP_URL_INDEX.clear()


def _url_key(url) -> str:
    """Normalise a CFP URL for cross-source matching (``""`` when absent)."""
    return _as_str(url).strip().rstrip("/").lower()


def _name_tokens(name) -> set:
    """Lowercase alphanumeric tokens of *name*, dropping bare year tokens."""
    return {
        t for t in re.findall(r"[a-z0-9]+", _as_str(name).lower())
        if not _YEAR_TOKEN_RE.match(t)
    }


def _names_compatible(a, b) -> bool:
    """Heuristic: do two names refer to the same conference?

    Gates the ``cfp_url`` match so a shared form does not merge distinct events.
    True when one normalised name contains the other (``SCaLE`` vs
    ``Southern California Linux Expo - SCaLE 24x``) or one name's tokens are a
    subset of the other's, ignoring years (``DevFest Malta 2026`` vs
    ``DevFest 2026 Malta``). ``Apidays Paris`` / ``Apidays London`` and
    ``HalfStack Phoenix`` / ``HalfStack Vienna`` therefore stay apart.
    """
    na = re.sub(r"[^a-z0-9]", "", _as_str(a).lower())
    nb = re.sub(r"[^a-z0-9]", "", _as_str(b).lower())
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


def _cfp_url_index(data_dir: Path) -> dict[str, list[tuple[Path, str, str]]]:
    """Map normalised ``cfp_url`` -> ``[(note path, owner source, name), …]``.

    Built once per process from the notes that parse as ``type: cfp``. Every
    owner of a URL is kept (feeds reuse one form across events), so the caller
    can pick the compatible one.
    """
    cached = _CFP_URL_INDEX.get(data_dir)
    if cached is not None:
        return cached
    index: dict[str, list[tuple[Path, str, str]]] = {}
    for p in sorted(data_dir.rglob("*.md")):
        try:
            fm, _ = _read_frontmatter(p)
        except FrontmatterError:
            continue
        if _as_str(fm.get("type")) != "cfp":
            continue
        key = _url_key(fm.get("cfp_url"))
        if not key:
            continue
        index.setdefault(key, []).append(
            (p, _as_str(fm.get("source")), _as_str(fm.get("name")))
        )
    _CFP_URL_INDEX[data_dir] = index
    return index


# Every frontmatter key the writer owns; any other key found in a local note is
# user metadata and is preserved verbatim on a rewrite (see ``_extra_frontmatter_lines``).
KNOWN_FM_KEYS = {
    "type",
    "name",
    "event_date",
    "location",
    "country",
    "cfp_close",
    "topics",
    "benefits",
    "languages",
    "event_url",
    "cfp_url",
    "source",
    "shortlist",
    "submissions",
    # Legacy keys kept "known" (so they are consumed, not preserved as user
    # metadata) — a migrated note must not keep a stale ``submission`` or
    # ``conf_date`` line next to the new key.
    "submission",
    "conf_date",
}

# One summary line per source; parsed by ``process-all.py`` for the run summary.
SUMMARY_RE = re.compile(
    r"^(?P<source>.+?): found (?P<found>\d+) "
    r"\(new (?P<new>\d+), updated (?P<updated>\d+), unchanged (?P<unchanged>\d+)\)$"
)


def summary_line(source: str, found: int, new: int, updated: int, unchanged: int) -> str:
    """Friendly, parseable per-source result line (see :data:`SUMMARY_RE`)."""
    return f"{source}: found {found} (new {new}, updated {updated}, unchanged {unchanged})"

# A YAML plain scalar may not start with an indicator character...
_PLAIN_UNSAFE_START = set("-?:,[]{}#&*!|>'\"%@`")

# Frontmatter block: opening ``---`` … closing ``---`` on their own lines.
_FM_RE = re.compile(r"\A---\r?\n(?P<fm>.*?)\r?\n---\r?\n?(?P<body>.*)\Z", re.S)

_MONTHS = {
    m[:3]: i
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"],
        1,
    )
}


def _is_plain_safe(s: str, flow: bool = False) -> bool:
    """True when *s* can be written as an unquoted YAML scalar.

    ``flow=True`` for values inside a flow collection (``[a, b]``), where commas
    and brackets are indicators and must be quoted.
    """
    if s == "" or s != s.strip():
        return False
    if "\n" in s or "\t" in s:
        return False
    if s[0] in _PLAIN_UNSAFE_START and not (s[0] == "-" and len(s) > 1 and s[1] != " "):
        return False
    if ": " in s or " #" in s or s.endswith(":"):
        return False
    if flow and any(c in s for c in ",[]{}:"):
        return False
    return True


def _yaml_str(value, flow: bool = False) -> str:
    """Render *value* as a safe YAML scalar, quoting only when needed."""
    s = "" if value is None else str(value)
    if s == "":
        return '""'
    if _is_plain_safe(s, flow=flow):
        return s
    # JSON double-quoted strings are valid YAML and escape newlines/quotes.
    return json.dumps(s, ensure_ascii=False)


def _yaml_list(items) -> str:
    return "[" + ", ".join(_yaml_str(i, flow=True) for i in (items or [])) + "]"


class FrontmatterError(ValueError):
    """A note's ``---`` block exists but is not valid YAML."""


def _as_str(value) -> str:
    """Normalise a parsed frontmatter value to the writer's canonical string.

    YAML types are unwrapped: ``None`` -> ``""``, a bool -> ``"true"``/``"false"``,
    a date/datetime -> its ISO form (YAML resolves ``2026-11-01`` to a date), and
    everything else with ``str``.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value)


def _as_list(value) -> list:
    """Normalise a parsed value to a list of strings (``[]`` when empty/absent)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [_as_str(v) for v in value]
    s = _as_str(value)
    return [s] if s else []


def _as_bool(value) -> bool:
    """Normalise a parsed value to a bool (defaults to ``False``)."""
    if isinstance(value, bool):
        return value
    return _as_str(value).strip().lower() in ("true", "yes", "on", "1")


def _read_submissions(fm: dict) -> list:
    """The preserved ``submissions`` list (wiki links) from a note's frontmatter.

    Accepts the legacy scalar ``submission`` key so a note written before the
    rename migrates instead of losing its value: ``submission: "[[x]]"`` reads as
    ``["[[x]]"]``.
    """
    if "submissions" in fm:
        return _as_list(fm.get("submissions"))
    legacy = _as_str(fm.get("submission"))
    return [legacy] if legacy else []


def _extract_body_notes(body: str) -> str:
    """Notes text from a note body, minus ``## Notes`` heading(s) and the placeholder.

    Repeated headings / placeholder lines (from the old bug that folded the body
    into the frontmatter) are collapsed away.
    """
    text = (body or "").strip()
    while True:
        stripped = re.sub(r"^#+\s*Notes\s*", "", text, count=1, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"^" + re.escape(NOTES_PLACEHOLDER), "", stripped).strip()
        if stripped == text:
            break
        text = stripped
    return "" if text == NOTES_PLACEHOLDER else text


def parse_start_date(raw: str) -> str:
    """Return a conference's *starting* date as a clean ``YYYY-MM-DD``.

    Handles the shapes produced by the generators and manual input:
    ``2026-11-28 (Sat)``, ``2026-11-20 → 2026-11-21``, ``Aug 20–21, 2027``,
    ``May 7, 2027``. Returns ``""`` when no date can be read (``TBA``, ``—``).
    """
    s = (raw or "").strip()
    if not s:
        return ""
    s = re.sub(r"\s*\([A-Za-z]{3,}\)\s*$", "", s).strip()  # drop trailing "(Sat)"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(
        r"([A-Za-z]{3,})\.?\s+(\d{1,2})(?:\s*[–—-]\s*\d{1,2})?\s*,?\s*(\d{4})", s
    )
    if m:
        mon = _MONTHS.get(m.group(1).lower()[:3])
        if mon:
            return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(2)):02d}"
    return ""


def slugify(name: str, close: str = "", event_date: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    # Date prefix: prefer cfp_close, then event_date.
    date = (close or event_date or "")[:10]
    if not re.match(r"\d{4}-\d{2}-\d{2}", date):
        # fall back to year
        ym = re.search(r"(20\d{2})", name or "") or re.search(r"(20\d{2})", event_date or "")
        date = ym.group(1) if ym else ""
    if date and base:
        return f"{date}_{base}"
    return base or "cfp"


def _read_frontmatter_text(text: str) -> tuple[dict, str]:
    """Parse the ``---`` frontmatter block into ``(mapping, body)``.

    The whole block is parsed with PyYAML, so flow/block lists, quoting and
    nested maps all read correctly (a value keeps its YAML type — see the
    ``_as_*`` helpers). Returns ``({}, "")`` when there is no frontmatter block;
    raises :class:`FrontmatterError` when the block is not valid YAML, so callers
    skip such a note instead of clobbering it.
    """
    m = _FM_RE.match(text or "")
    if not m:
        return {}, ""
    body = m.group("body").strip()
    try:
        data = yaml.safe_load(m.group("fm"))
    except yaml.YAMLError as exc:
        raise FrontmatterError(str(exc)) from exc
    if data is None:
        return {}, body
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a YAML mapping")
    return data, body


def _read_frontmatter(path: Path) -> tuple[dict, str]:
    """Return ``(parsed frontmatter mapping, body)`` for *path*, or ``({}, "")``.

    Raises :class:`FrontmatterError` when the block is present but not valid YAML.
    """
    if not path.is_file():
        return {}, ""
    return _read_frontmatter_text(path.read_text(encoding="utf-8"))


_TOP_FM_KEY_RE = re.compile(r"^[A-Za-z0-9_][\w.-]*\s*:")


def _extra_frontmatter_lines(text: str) -> list[str]:
    """Raw frontmatter lines for keys the writer does not own, preserved verbatim.

    Captures each unknown top-level key with any indented continuation lines
    (block scalars, nested maps/lists) so user metadata survives a rewrite
    without being re-quoted or reinterpreted. Known keys are skipped.
    """
    m = _FM_RE.match(text or "")
    if not m:
        return []
    out: list[str] = []
    capturing = False
    for line in m.group("fm").split("\n"):
        line = line.rstrip("\r")
        if _TOP_FM_KEY_RE.match(line):
            key = line.split(":", 1)[0].strip()
            capturing = key not in KNOWN_FM_KEYS
            if capturing:
                out.append(line)
        elif capturing and line[:1] in (" ", "\t"):
            out.append(line)
        else:
            capturing = False
    return out


def _render(row: dict, shortlist: str, submissions: list, notes: str, extras: list[str] | None = None) -> str:
    fm = [
        "---",
        "type: cfp",
        f"name: {_yaml_str(row.get('name', ''))}",
        f"event_date: {_yaml_str(row.get('event_date', ''))}",
        f"location: {_yaml_str(row.get('location', ''))}",
        f"country: {_yaml_str(row.get('country', ''))}",
        f"cfp_close: {_yaml_str(row.get('cfp_close', ''))}",
        f"topics: {_yaml_list(row.get('topics'))}",
    ]
    # ``benefits`` is written only when the source states any (cfp.ninja marks
    # travel/hotel/honorarium), so notes from sources that don't carry it are
    # rendered byte-for-byte as before.
    if row.get("benefits"):
        fm.append(f"benefits: {_yaml_list(row.get('benefits'))}")
    # ``languages`` comes from the developers.events event tags; other sources
    # don't carry it, so it is written only when known.
    if row.get("languages"):
        fm.append(f"languages: {_yaml_list(row.get('languages'))}")
    fm += [
        f"event_url: {_yaml_str(row.get('event_url', ''))}",
        f"cfp_url: {_yaml_str(row.get('cfp_url', ''))}",
        f"source: {_yaml_str(row.get('source', ''))}",
        f"shortlist: {shortlist}",
        f"submissions: {_yaml_list(submissions)}",
    ]
    fm.extend(extras or [])  # user metadata, preserved verbatim
    fm += [
        "---",
        "",
        NOTES_HEADING,
        "",
        notes if notes else NOTES_PLACEHOLDER,
        "",
    ]
    return "\n".join(fm)


def write_manifest(path: Path, notes, data_dir: Path) -> None:
    """Write the sorted, data_dir-relative note paths as JSON (orphan detection)."""
    rels = sorted({Path(n).relative_to(data_dir).as_posix() for n in notes})
    Path(path).write_text(json.dumps(rels, indent=2) + "\n", encoding="utf-8")


def _write_if_changed(path: Path, text: str) -> str:
    """Write *text* to *path* only when it differs.

    Returns ``"new"`` when the file did not exist, ``"updated"`` when an
    existing file was rewritten, and ``"unchanged"`` when the rendered note
    matches the file byte-for-byte (nothing is written). Skipping the write
    keeps mtimes and file identity stable, so an unchanged refresh touches
    nothing. Any read error falls through to a normal write.
    """
    existed = path.is_file()
    if existed:
        try:
            if path.read_text(encoding="utf-8") == text:
                return "unchanged"
        except OSError:
            pass
    path.write_text(text, encoding="utf-8")
    return "updated" if existed else "new"


def _source_props_match(fm: dict, row: dict) -> bool:
    """True when *fm* already carries every source-derived property from *row*.

    Compares the scalar fields and the list fields (:data:`LIST_FIELDS`)
    semantically — YAML-normalised, so quoting or block-vs-flow formatting never
    forces a rewrite. Anything the source does not own — the body, ``shortlist``,
    ``submissions``, or extra frontmatter — is deliberately ignored.
    """
    if not fm:
        return False
    for key in SOURCE_SCALAR_FIELDS:
        existing = _as_str(fm.get(key))
        incoming = "" if row.get(key) is None else str(row.get(key, ""))
        if existing != incoming:
            return False
    for key in LIST_FIELDS:
        if _as_list(fm.get(key)) != [str(v) for v in (row.get(key) or [])]:
            return False
    return True


def note_path(data_dir: Path, row: dict) -> Path:
    """Path for *row*'s note under *data_dir* (no directories created)."""
    slug = slugify(row.get("name", ""), row.get("cfp_close", ""), row.get("event_date", ""))
    # Year subfolder based on cfp_close (or event_date).
    date = (row.get("cfp_close") or row.get("event_date") or "")[:4]
    if not (date.isdigit() and len(date) == 4):
        m = re.search(r"(20\d{2})", (row.get("event_date") or "") + (row.get("cfp_close") or ""))
        date = m.group(1) if m else "misc"
    return data_dir / date / f"{slug}.md"


def upsert(data_dir: Path, row: dict) -> str:
    """Write/refresh one note; return ``"new"``, ``"updated"``, ``"unchanged"`` or ``"skipped"``.

    ``"unchanged"`` means the note is current — every source-derived property
    already matches the file (see :func:`_source_props_match`).

    ``"skipped"`` means this row deliberately wrote nothing because another note
    owns the CFP: a higher-priority source already owns the same slug (see
    :data:`SOURCE_PRIORITY`), the same ``cfp_url`` is already owned by a note at a
    different path, or the target's frontmatter is not valid YAML. The caller
    must not record *this* row's path as produced, or the losing note could never
    be archived (see the ``--manifest`` handling in each ``process-*.py``).
    """
    # Canonicalise the country label before anything compares or writes it, so
    # "United Kingdom" and "UK" from different feeds land on the same value.
    row = {**row, "country": normalize_country(row.get("country"))}
    path = note_path(data_dir, row)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Cross-source duplicate: the same CFP under another name slugifies to a
    # different path, so the same-slug rule below misses it. Match on cfp_url —
    # if the URL is owned by a *compatibly named* note at a different path, this
    # row yields unless it comes from a strictly higher-priority source. This runs
    # before the "unchanged" short-circuit so a loser note already on disk is
    # skipped too, not just one that has not been created yet.
    key = _url_key(row.get("cfp_url"))
    incoming_priority = _source_priority(row.get("source", ""))
    if key:
        for owner_path, owner_source, owner_name in _cfp_url_index(data_dir).get(key, ()):
            if owner_path == path:
                continue
            if not _names_compatible(owner_name, row.get("name", "")):
                continue
            owner_priority = _source_priority(owner_source)
            # A strictly higher-priority owner always wins. On a tie, the lower
            # path wins deterministically — otherwise two equal-priority notes for
            # one URL would each yield to the other and both be archived.
            if owner_priority < incoming_priority or (
                owner_priority == incoming_priority and str(owner_path) < str(path)
            ):
                return "skipped"

    # Preserve user-curated frontmatter fields and body notes from the existing file.
    existing = ""
    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError:
            existing = ""
    try:
        fm, body = _read_frontmatter_text(existing)
    except FrontmatterError:
        print(f"cfp-writer: skipping note with unparseable frontmatter: {path}", file=sys.stderr)
        return "skipped"
    if _source_props_match(fm, row):
        return "unchanged"

    # A note another (higher-priority) source already owns is left as-is. The
    # feeds overlap on some conferences, so without this both write the same slug
    # every run and the lower-priority source's version wins the last write.
    if existing:
        owner = _as_str(fm.get("source"))
        if _source_priority(owner) < _source_priority(row.get("source", "")):
            return "skipped"

    shortlist = "true" if _as_bool(fm.get("shortlist")) else "false"
    submissions = _read_submissions(fm)
    notes = _extract_body_notes(body)
    extras = _extra_frontmatter_lines(existing)

    status = _write_if_changed(path, _render(row, shortlist, submissions, notes, extras))
    if key:
        # Keep the in-process index current so a later row for the same URL sees
        # the note this run just wrote.
        _cfp_url_index(data_dir).setdefault(key, []).append(
            (path, _as_str(row.get("source")), _as_str(row.get("name")))
        )
    return status


def upsert_counted(data_dir: Path, row: dict, counts: dict, produced: list) -> str:
    """Run :func:`upsert` and fold the result into a parser's counters.

    Increments ``counts[status]`` and, unless the status is ``"skipped"``,
    records the row's note path in *produced* — the ``--manifest`` list that
    ``archive-orphans.py`` treats as "still produced". A skipped row yields to
    another note, so it must **not** claim its own path, or the note it yields to
    would keep the loser alive as an un-archivable duplicate.
    """
    status = upsert(data_dir, row)
    counts[status] = counts.get(status, 0) + 1
    if status != "skipped":
        produced.append(note_path(data_dir, row))
    return status


def normalize_file(path: Path) -> bool:
    """Rewrite one existing note in place to the current frontmatter shape.

    Drops any frontmatter ``notes`` (kept only in the body), re-quotes every
    value safely, and re-renders the body. Returns False when there is no
    frontmatter block or the block is not valid YAML.
    """
    try:
        fm, body = _read_frontmatter(path)
    except FrontmatterError:
        print(f"cfp-writer: skipping note with unparseable frontmatter: {path}", file=sys.stderr)
        return False
    if not fm:
        return False
    text = path.read_text(encoding="utf-8")
    types = ("name", "event_date", "location", "country", "cfp_close", "event_url", "cfp_url", "source")
    row = {k: _as_str(fm.get(k)) for k in types}
    if not row["event_date"] and "conf_date" in fm:  # legacy key rename
        row["event_date"] = _as_str(fm.get("conf_date"))
    row["topics"] = _as_list(fm.get("topics"))
    row["benefits"] = _as_list(fm.get("benefits"))
    row["languages"] = _as_list(fm.get("languages"))
    row["country"] = normalize_country(row.get("country"))
    shortlist = "true" if _as_bool(fm.get("shortlist")) else "false"
    submissions = _read_submissions(fm)
    notes = _extract_body_notes(body)
    extras = _extra_frontmatter_lines(text)
    _write_if_changed(path, _render(row, shortlist, submissions, notes, extras))
    return True
