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
    import config as _cfg
except ImportError as exc:  # Optional when using the writer outside the repo.
    if exc.name != "config":
        raise  # Do not hide an import error raised inside config_local.py.
    _cfg = None

try:
    from country import normalize_country
except ImportError:  # pragma: no cover - when src/ is not already on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from country import normalize_country

NOTES_HEADING = "## Notes"
NOTES_PLACEHOLDER = "_Add notes here._"

EVENT_TYPES = (
    "conference",
    "meetup",
    "summit",
    "workshop",
    "hackathon",
    "webinar",
    "other",
)
DEFAULT_EVENT_TYPE = "conference"
_INFERABLE_EVENT_TYPES = tuple(
    event_type for event_type in EVENT_TYPES if event_type not in ("conference", "other")
)
_DEFAULT_EVENT_TYPE_KEYWORDS = {
    "meetup": ("meetup", "meet-up", "meet up", "user group", "user-group", "usergroup"),
    "summit": ("summit",),
    "workshop": ("workshop",),
    "hackathon": ("hackathon",),
    "webinar": ("webinar",),
}


def _event_type_patterns() -> tuple[tuple[str, re.Pattern], ...]:
    """Compile and validate the ordered, configurable event-name aliases."""
    configured = getattr(_cfg, "EVENT_TYPE_KEYWORDS", None) if _cfg is not None else None
    if configured is None:
        configured = _DEFAULT_EVENT_TYPE_KEYWORDS
    if not isinstance(configured, dict):
        raise ValueError("config.EVENT_TYPE_KEYWORDS must be a mapping of event types to keywords")

    patterns = []
    for event_type, keywords in configured.items():
        if event_type not in _INFERABLE_EVENT_TYPES:
            choices = ", ".join(_INFERABLE_EVENT_TYPES)
            raise ValueError(
                f"Unknown config.EVENT_TYPE_KEYWORDS event type {event_type!r}; "
                f"choose from {choices}"
            )
        if isinstance(keywords, str) or not hasattr(keywords, "__iter__"):
            raise ValueError("config.EVENT_TYPE_KEYWORDS values must be lists of keywords")
        keywords = list(keywords)
        if not keywords:
            raise ValueError("config.EVENT_TYPE_KEYWORDS values must not be empty")
        for keyword in keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError("config.EVENT_TYPE_KEYWORDS must contain nonempty strings")
            words = [word for word in re.split(r"[\s-]+", keyword.strip()) if word]
            if not words:
                raise ValueError("config.EVENT_TYPE_KEYWORDS must contain words")
            body = r"[\s-]*".join(re.escape(word) for word in words)
            patterns.append((event_type, re.compile(rf"\b{body}s?\b", re.IGNORECASE)))
    return tuple(patterns)


def infer_event_type(name: str) -> str:
    """Infer a controlled event type from *name*, defaulting to conference."""
    for event_type, pattern in _event_type_patterns():
        if pattern.search(name or ""):
            return event_type
    return DEFAULT_EVENT_TYPE


def _ignored_names() -> tuple[str, ...]:
    """Return validated, case-folded literal event-name exclusions."""
    configured = getattr(_cfg, "IGNORE_NAMES", ()) if _cfg is not None else ()
    if configured is None:
        configured = ()
    if isinstance(configured, str) or not hasattr(configured, "__iter__"):
        raise ValueError("config.IGNORE_NAMES must be a list of event-name fragments")
    ignored = []
    for value in configured:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("config.IGNORE_NAMES must contain nonempty strings")
        ignored.append(value.strip().casefold())
    return tuple(ignored)


def event_name_is_ignored(name: str) -> bool:
    """Return whether *name* contains any configured, case-insensitive fragment."""
    folded = (name or "").strip().casefold()
    return any(fragment in folded for fragment in _ignored_names())


def _event_type_included(value: str) -> bool:
    """Return whether config's validated, nonempty allow-list includes *value*."""
    configured = getattr(_cfg, "EVENT_TYPES", None) if _cfg is not None else None
    if configured is None:
        configured = tuple(t for t in EVENT_TYPES if t != "meetup")
    if isinstance(configured, str) or not hasattr(configured, "__iter__"):
        raise ValueError("config.EVENT_TYPES must be a nonempty list of event types")
    allowed = set()
    for item in configured:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("config.EVENT_TYPES must contain nonempty strings")
        allowed.add(item.strip().lower())
    if not allowed:
        raise ValueError("config.EVENT_TYPES must not be empty")
    invalid = allowed.difference(EVENT_TYPES)
    if invalid:
        raise ValueError(
            f"Unknown config.EVENT_TYPES value(s): {', '.join(sorted(invalid))}; "
            f"choose from {', '.join(EVENT_TYPES)}"
        )
    return value in allowed


# Frontmatter properties that are regenerated from the upstream row. ``upsert``
# compares these one by one against the existing note and skips the write when
# all of them already match, so a user's edits to the body, ``shortlist`` /
# ``submissions``, or any extra frontmatter survive an unchanged refresh.
SOURCE_SCALAR_FIELDS = (
    "event_name",
    "event_date",
    "location",
    "country",
    "cfp_close",
    "event_url",
    "cfp_url",
    "source",
)

# List fields, compared semantically and order-sensitively. ``upsert`` first
# merges incoming topics and languages into the existing note (cumulative, see
# ``_merge_list``), so those two comparisons are against the cumulative values
# rather than the raw source lists. ``benefits`` is the exception: it is
# replaced on update.
LIST_FIELDS = ("topics", "benefits", "languages")

# Lower index = higher priority. Several conferences appear in more than one
# feed and map to the same slug; the lower-priority source must not overwrite the
# note a higher-priority one already owns (they disagree on location/country/source).
SOURCE_PRIORITY = {
    "manual": 0,
    "developers.events": 1,
    "cfp.ninja": 2,
    "confs.tech": 3,
    # Derived aggregators fill gaps without overwriting richer sources.
    "adato-tracker": 4,
    "open-tech-cfps": 5,
}


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


# Tracking parameters to drop from a submission URL. Google Analytics UTM tags
# are per-share noise: two feeds (or two runs) can carry the same CFP page with
# different tags, so they must not defeat URL matching or leak into a note.
_UTM_PARAM_RE = re.compile(r"^utm_", re.IGNORECASE)


def strip_utm(url) -> str:
    """Remove ``utm_*`` query parameters from *url*, keeping everything else.

    Works on the raw string without re-encoding it, so the remaining query
    parameters keep their order and encoding, and any ``#fragment`` survives.
    A URL with no query, or none of whose parameters start with ``utm_``, is
    returned unchanged (only surrounding whitespace is trimmed).
    """
    s = _as_str(url).strip()
    if not s or "?" not in s:
        return s
    main, has_frag, frag = s.partition("#")
    base, _, query = main.partition("?")
    kept = [
        part
        for part in query.split("&")
        if part and not _UTM_PARAM_RE.match(part.split("=", 1)[0])
    ]
    out = base + ("?" + "&".join(kept) if kept else "")
    return f"{out}#{frag}" if has_frag else out


def _url_key(url) -> str:
    """Normalise a CFP URL for cross-source matching (``""`` when absent)."""
    return strip_utm(url).strip().rstrip("/").lower()


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
        # Excluded event types are archived when unproduced; they must not keep
        # a replacement CFP from claiming the same URL. Older notes may not have
        # a type yet, so infer it from the stored name rather than dropping them.
        owner_type = _as_str(fm.get("event_type")).strip() or infer_event_type(_event_name(fm))
        if not _event_type_included(owner_type):
            continue
        key = _url_key(fm.get("cfp_url"))
        if not key:
            continue
        index.setdefault(key, []).append(
            (p, _as_str(fm.get("source")), _event_name(fm))
        )
    _CFP_URL_INDEX[data_dir] = index
    return index


# Every frontmatter key the writer owns; any other key found in a local note is
# user metadata and is preserved verbatim on a rewrite (see ``_extra_frontmatter_lines``).
KNOWN_FM_KEYS = {
    "type",
    "event_name",
    "event_date",
    "event_type",
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
    "dismissed",
    "submissions",
    # Pipeline timestamps. ``created`` is the note's first-seen date, set once
    # and kept; ``updated`` is bumped to the run date whenever the pipeline
    # rewrites the note because its source data changed. They are intentionally
    # NOT part of ``_source_props_match``: comparing them against today would
    # force a rewrite of every note on every run, so they are only checked for
    # validity (a missing/garbled stamp back-fills on the next refresh).
    "created",
    "updated",
    # Legacy keys are consumed instead of preserved as user metadata. A migrated
    # note must not keep a stale key next to its replacement.
    "name",
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


# ISO dates are deliberately left unquoted: PyYAML reads them as
# ``datetime.date`` and Obsidian maps the unquoted form to its date property
# type, which ``event_date``/``cfp_close``/``created``/``updated`` rely on.
# ``_as_str`` turns them back into ``YYYY-MM-DD`` on read, so the round-trip is
# lossless.


def _yaml_reads_as_non_string(s: str) -> bool:
    """True when YAML would read the plain scalar *s* as anything but a string.

    ``365``, ``2026``, ``1.0``, ``yes``/``on``, ``null`` and sexagesimals like
    ``1:30`` all resolve to int / float / bool / None, so they must be quoted or
    the value silently changes type — a topic ``365`` comes back from the note
    as a number. ISO dates are exempt (see ``_ISO_DATE_RE``).
    """
    if _ISO_DATE_RE.fullmatch(s):
        return False
    try:
        return not isinstance(yaml.safe_load(s), str)
    except yaml.YAMLError:  # not a valid plain scalar at all -> quote it
        return True


def _yaml_str(value, flow: bool = False) -> str:
    """Render *value* as a safe YAML scalar, quoting only when needed.

    Quoted when the plain form would not read back as the same string: YAML
    indicators, flow-collection characters, and anything YAML would resolve to
    a number / bool / null (``365`` -> ``"365"``). ISO dates stay plain.
    """
    s = "" if value is None else str(value)
    if s == "":
        return '""'
    if _is_plain_safe(s, flow=flow) and not _yaml_reads_as_non_string(s):
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


def _event_name(fm: dict) -> str:
    """Read the canonical event name, falling back to the legacy ``name`` key."""
    return _as_str(fm.get("event_name")) or _as_str(fm.get("name"))


def _as_list(value) -> list:
    """Normalise a parsed value to a list of strings (``[]`` when empty/absent)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [_as_str(v) for v in value]
    s = _as_str(value)
    return [s] if s else []


def _casefold_list(values) -> list[str]:
    """``_as_list`` normalisation with every value folded to lowercase.

    ``languages`` is always stored folded (``English`` -> ``english``), so the
    note's form stays stable when the source's tag spellings vary by edition.
    """
    return [str(v).casefold() for v in _as_list(values)]


def _as_bool(value) -> bool:
    """Normalise a parsed value to a bool (defaults to ``False``)."""
    if isinstance(value, bool):
        return value
    return _as_str(value).strip().lower() in ("true", "yes", "on", "1")


# The pipeline stamps ``created``/``updated`` as plain ISO dates; a stamp is
# "valid" when it matches exactly that shape. The writer knows nothing about
# what the source data was on those days, so the check is format-only.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_iso_date(value) -> bool:
    """True when *value* is a non-empty ``YYYY-MM-DD`` stamp."""
    return bool(_ISO_DATE_RE.match(_as_str(value)))


def _today_str(today=None) -> str:
    """Today's ISO date; *today* (a ``YYYY-MM-DD`` string) overrides for tests."""
    if today:
        return str(today)
    return datetime.date.today().isoformat()


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
    return text


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


def _render(
    row: dict,
    shortlist: str,
    dismissed: str,
    submissions: list,
    notes: str,
    created: str,
    updated: str,
    extras: list[str] | None = None,
) -> str:
    fm = [
        "---",
        "type: cfp",
        f"event_name: {_yaml_str(row.get('name', ''))}",
        f"event_date: {_yaml_str(row.get('event_date', ''))}",
        f"event_type: {_yaml_str(row.get('event_type', ''))}",
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
    # don't carry it, so it is written only when known. Values are case-folded,
    # so a note always stores them lowercase.
    if row.get("languages"):
        fm.append(f"languages: {_yaml_list(row.get('languages'))}")
    fm += [
        f"event_url: {_yaml_str(row.get('event_url', ''))}",
        f"cfp_url: {_yaml_str(row.get('cfp_url', ''))}",
        f"source: {_yaml_str(row.get('source', ''))}",
        f"shortlist: {shortlist}",
        f"dismissed: {dismissed}",
        f"submissions: {_yaml_list(submissions)}",
        f"created: {_yaml_str(created)}",
        f"updated: {_yaml_str(updated)}",
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


def set_property(path: Path, key: str, value) -> str:
    """Set one top-level scalar frontmatter property in place.

    Used by registry-driven taggers (``apply-prestige.py`` writing ``tier``) so a
    curated value can land on a note without :func:`upsert` re-rendering it: the
    body notes, every other property, the key order, and the ``created`` /
    ``updated`` stamps are left byte-for-byte alone. Only the ``---`` block is
    touched, and only the one key line.

    Returns ``"updated"`` when the file changed and ``"unchanged"`` when the key
    already held the value (nothing is written, so mtimes stay put). A file with
    no frontmatter block is ``"unchanged"`` — it is not a CFP note.

    Raises:
        FrontmatterError: the ``---`` block is present but not valid YAML, so the
            caller can skip the note instead of clobbering it.
    """
    text = path.read_text(encoding="utf-8")
    fm, _ = _read_frontmatter_text(text)
    if not fm:
        return "unchanged"
    # Numeric values (``tier``) stay unquoted on purpose: a YAML scalar ``1`` is
    # read back as a number, so an Obsidian Bases filter can compare ``tier == 1``.
    # ``_yaml_str`` would quote it (it "looks like" an int), which is right for the
    # string fields but wrong here.
    rendered = str(int(value)) if isinstance(value, int) and not isinstance(value, bool) else _yaml_str(value)

    m = _FM_RE.match(text)
    if not m:
        return "unchanged"
    fm_text = m.group("fm")
    fm_lines = fm_text.split("\n")
    key_re = re.compile(rf"^{re.escape(key)}\s*:")

    new_line = f"{key}: {rendered}"
    for i, line in enumerate(fm_lines):
        if not key_re.match(line):
            continue
        # Drop any indented continuation (block scalar / nested map) that belongs
        # to the old value before replacing it, so no orphan lines are left behind.
        end = i + 1
        while end < len(fm_lines) and fm_lines[end][:1] in (" ", "\t"):
            end += 1
        fm_lines[i:end] = [new_line]
        break
    else:
        fm_lines.append(new_line)

    new_fm = "\n".join(fm_lines)
    if new_fm == fm_text:
        return "unchanged"
    updated = text[: m.start("fm")] + new_fm + text[m.end("fm") :]
    if updated == text:
        return "unchanged"
    path.write_text(updated, encoding="utf-8")
    return "updated"


def _event_type_for(fm: dict, row: dict) -> str:
    """Return a sticky existing event type, or infer one when it is unset."""
    existing = _as_str(fm.get("event_type")).strip()
    if existing:
        return existing
    supplied = _as_str(row.get("event_type")).strip()
    return supplied or infer_event_type(_as_str(row.get("name")))


def _merge_list(existing: list[str], incoming) -> list[str]:
    """Keep the existing list verbatim and append newly seen incoming values.

    Used for the cumulative list fields (``topics`` and ``languages``).
    Matching is case-insensitive (``English`` and ``english`` are the same
    value), so a capitalization-only upstream change never appends and the
    existing or first-seen spelling always wins. Existing order (and any
    existing duplicates) is preserved; incoming duplicates are appended once.
    """
    merged = list(existing)
    seen = {str(v).casefold() for v in merged}
    for value in incoming or []:
        item = str(value)
        key = item.casefold()
        if key not in seen:
            merged.append(item)
            seen.add(key)
    return merged


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
        source_key = "name" if key == "event_name" else key
        existing = _event_name(fm) if key == "event_name" else _as_str(fm.get(key))
        incoming = "" if row.get(source_key) is None else str(row.get(source_key, ""))
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


def upsert(data_dir: Path, row: dict, today=None) -> str:
    """Write/refresh one note; return ``"new"``, ``"updated"``, ``"unchanged"`` or ``"skipped"``.

    ``"unchanged"`` means the note is current — every source-derived property
    already matches the file (see :func:`_source_props_match`) and the
    ``created``/``updated`` stamps are valid ISO dates. Topics and languages
    are cumulative: existing values are preserved and new incoming values are
    appended (case-insensitive match), so a hand-added value or one the source
    removed/reordered upstream does not force a rewrite, while a genuinely new
    one does. ``languages`` values are case-folded, so the note always stores
    them lowercase: a pre-existing capitalised value reads as one mismatch,
    is rewritten lowercase once, and then settles.
    ``event_type`` is sticky: an existing non-empty value is preserved, and a
    missing one is inferred from the conference name and back-filled without
    constituting a source change.

    The stamps are writer-owned but deliberately excluded from the source-prop
    compare: a no-op refresh must not touch anything. ``created`` is preserved
    once set; ``updated`` advances to *today* only when a source change rewrites
    the note. A missing/garbled stamp back-fills without counting as an update
    (``updated`` mirrors ``created``), so existing notes start with both equal.
    A missing ``dismissed`` flag similarly back-fills to ``false`` without
    advancing valid stamps; an existing flag is preserved across rewrites.

    ``"skipped"`` means this row deliberately wrote nothing because its name
    matches ``config.IGNORE_NAMES``, its resolved ``event_type`` is excluded by
    ``config.EVENT_TYPES``, another note owns the CFP: a higher-priority source
    already owns the same slug (see
    :data:`SOURCE_PRIORITY`), the same ``cfp_url`` is already owned by a note at a
    different path, or the target's frontmatter is not valid YAML. The caller
    must not record *this* row's path as produced, or the losing note could never
    be archived (see the ``--manifest`` handling in each ``process-*.py``).
    """
    # Validate configurable name rules before touching note paths. Ignored names
    # and malformed settings therefore cannot create or rewrite a note.
    _event_type_patterns()
    if event_name_is_ignored(row.get("name")):
        return "skipped"

    # Canonicalise the country label before anything compares or writes it, so
    # "United Kingdom" and "UK" from different feeds land on the same value.
    # Drop UTM tracking tags from the submission and event URLs for the same
    # reason: they are per-share noise that would otherwise force rewrites and
    # defeat matching.
    row = {
        **row,
        "country": normalize_country(row.get("country")),
        "cfp_url": strip_utm(row.get("cfp_url")),
        "event_url": strip_utm(row.get("event_url")),
    }
    path = note_path(data_dir, row)
    path.parent.mkdir(parents=True, exist_ok=True)

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

    # Event type is curated metadata: preserve a non-empty existing value and
    # infer it only when absent. Like missing stamps, a missing type back-fills
    # on the next refresh without advancing a valid ``updated`` stamp.
    event_type_set = bool(_as_str(fm.get("event_type")).strip())
    row["event_type"] = _event_type_for(fm, row)
    if not _event_type_included(row["event_type"]):
        # Excluded types never enter the live CFP tree. A skipped row is absent
        # from the manifest, so the refresh archives an existing note as-is.
        return "skipped"

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

    # Topics and languages accumulate across refreshes instead of being
    # replaced by the current source row. Merge before comparing so an
    # unchanged cumulative list remains a no-op and only genuinely new
    # values trigger a rewrite. ``benefits`` keeps its replace semantics.
    row["topics"] = _merge_list(_as_list(fm.get("topics")), row.get("topics"))
    # ``languages`` values are case-folded on both sides, so the note always
    # stores them lowercase. A pre-existing capitalised value reads as one
    # mismatch against the folded merge — the note is rewritten lowercase once
    # and then settles.
    row["languages"] = _merge_list(
        _casefold_list(fm.get("languages")), _casefold_list(row.get("languages"))
    )
    props_match = _source_props_match(fm, row)
    if (
        props_match
        and "name" not in fm
        and event_type_set
        and "dismissed" in fm
        and _valid_iso_date(fm.get("created"))
        and _valid_iso_date(fm.get("updated"))
    ):
        return "unchanged"

    # A note another (higher-priority) source already owns is left as-is. The
    # feeds overlap on some conferences, so without this both write the same slug
    # every run and the lower-priority source's version wins the last write.
    if existing:
        owner = _as_str(fm.get("source"))
        if _source_priority(owner) < _source_priority(row.get("source", "")):
            return "skipped"

    shortlist = "true" if _as_bool(fm.get("shortlist")) else "false"
    dismissed = "true" if _as_bool(fm.get("dismissed")) else "false"
    submissions = _read_submissions(fm)
    notes = _extract_body_notes(body)
    extras = _extra_frontmatter_lines(existing)

    today_iso = _today_str(today)
    created = _as_str(fm.get("created"))
    updated = _as_str(fm.get("updated"))
    if not _valid_iso_date(created):
        # Mirror an existing ``updated`` so a back-fill never dates ``created``
        # after ``updated``; a note with neither stamp starts both at today.
        created = updated if _valid_iso_date(updated) else today_iso
    if not props_match:
        # A real source change is an update of the note: advance ``updated``.
        updated = today_iso
    elif not _valid_iso_date(updated):
        # Stamp back-fill only, not a data update: an existing note's
        # ``updated`` starts equal to its ``created``.
        updated = created

    status = _write_if_changed(
        path,
        _render(row, shortlist, dismissed, submissions, notes, created, updated, extras),
    )
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


def normalize_file(path: Path, today=None) -> bool:
    """Rewrite one existing note in place to the current frontmatter shape.

    Drops any frontmatter ``notes`` (kept only in the body), re-quotes every
    value safely, back-fills a missing ``event_type`` from the name and a
    missing ``dismissed`` flag with ``false``, and re-renders the body.
    Missing ``created``/``updated`` stamps back-fill with
    today (or mirror the other stamp when one exists); stamps and existing event
    types are preserved (re-emitting the shape is not a data update). Returns
    False when there is no frontmatter block or the
    block is not valid YAML.
    """
    try:
        fm, body = _read_frontmatter(path)
    except FrontmatterError:
        print(f"cfp-writer: skipping note with unparseable frontmatter: {path}", file=sys.stderr)
        return False
    if not fm:
        return False
    text = path.read_text(encoding="utf-8")
    row = {k: _as_str(fm.get(k)) for k in SOURCE_SCALAR_FIELDS if k != "event_name"}
    row["name"] = _event_name(fm)
    if not row["event_date"] and "conf_date" in fm:  # legacy key rename
        row["event_date"] = _as_str(fm.get("conf_date"))
    row["topics"] = _as_list(fm.get("topics"))
    row["benefits"] = _as_list(fm.get("benefits"))
    row["languages"] = _casefold_list(fm.get("languages"))
    row["event_type"] = _event_type_for(fm, row)
    row["country"] = normalize_country(row.get("country"))
    row["cfp_url"] = strip_utm(row.get("cfp_url"))
    row["event_url"] = strip_utm(row.get("event_url"))
    shortlist = "true" if _as_bool(fm.get("shortlist")) else "false"
    dismissed = "true" if _as_bool(fm.get("dismissed")) else "false"
    submissions = _read_submissions(fm)
    notes = _extract_body_notes(body)
    extras = _extra_frontmatter_lines(text)
    created = _as_str(fm.get("created"))
    updated = _as_str(fm.get("updated"))
    if not _valid_iso_date(created):
        created = updated if _valid_iso_date(updated) else _today_str(today)
    if not _valid_iso_date(updated):
        # A shape pass is not a data update: back-filled stamps stay equal.
        updated = created
    _write_if_changed(
        path,
        _render(row, shortlist, dismissed, submissions, notes, created, updated, extras),
    )
    return True
