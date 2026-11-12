#!/usr/bin/env python3
"""Curated conference-prestige registry: ``prestige.md`` -> a note's ``tier``.

The registry is a hand-maintained markdown table (see ``prestige.md`` at the repo
root). Prestige is judgement — no feed carries attendance, acceptance rate, or
program-committee pedigree — so nothing here is inferred from source data; the
table *is* the source of truth.

Matching rules (see ``prestige.md`` for the user-facing description):

* ``keywords`` is a comma-separated list of **alternatives**; a row matches when
  any one phrase occurs in the note's ``event_name``.
* Comparison is case- and punctuation-insensitive: both sides are reduced to
  lowercase alphanumeric tokens.
* Every word of a phrase must equal a whole word of the name, or that word plus a
  trailing **year**. So ``srecon`` matches ``SREcon27 Americas`` and
  ``offensivecon`` matches ``OffensiveCon26``, while ``engineer`` does not match
  ``engineering`` (which would let ``AI Engineer`` swallow ``AI Engineering
  Summit``). A glued non-year suffix must be listed explicitly as its own
  keyword — ``scale 24x``, not ``scale``.
* When several rows match one name the **lowest tier wins**, so a specific
  ``devoxx belgium`` (tier 1) row beats the broader ``devoxx`` (tier 2) row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "prestige.md"

# The only ranking values the table may use. Anything else is a typo that would
# silently rank a conference nowhere, so parsing fails on it instead.
TIERS = (1, 2, 3)

# A cell may be plain text, emphasised, or a markdown link; all three appear in
# hand-edited tables.
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPH_RE = re.compile(r"[*_`]{1,3}")
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
# A year glued onto a name token: ``SREcon27``, ``OffensiveCon2026``. Two digits
# cover the common short form, so they must be allowed as well as four.
_GLUED_YEAR_RE = re.compile(r"(?:\d{2}|\d{4})")
_HEADER_NAMES = {"conf name", "conference", "name", "event"}


@dataclass(frozen=True)
class Rule:
    """One curated ranking row."""

    name: str
    tier: int
    keywords: tuple[str, ...]
    line: int = 0

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.name} (tier {self.tier})"


def tokens(text) -> list[str]:
    """Lowercase alphanumeric tokens of *text* (``AI Engineer`` -> ``['ai', 'engineer']``)."""
    return [t for t in _TOKEN_SPLIT_RE.split(str(text or "").lower()) if t]


def _clean_cell(raw: str) -> str:
    """Strip markdown link/emphasis wrapper from a table cell."""
    cell = _MD_LINK_RE.sub(r"\1", (raw or "").strip())
    return re.sub(r"\s+", " ", _EMPH_RE.sub("", cell)).strip()


def _word_matches(name_token: str, keyword_token: str) -> bool:
    """A name word matches a keyword word exactly, or with a trailing year glued on."""
    if name_token == keyword_token:
        return True
    if not name_token.startswith(keyword_token):
        return False
    return bool(_GLUED_YEAR_RE.fullmatch(name_token[len(keyword_token):]))


def phrase_matches(name, phrase) -> bool:
    """True when *phrase* occurs in *name* as whole words (or with a glued year)."""
    name_toks = tokens(name)
    phrase_toks = tokens(phrase)
    if not name_toks or not phrase_toks:
        return False
    for start in range(len(name_toks) - len(phrase_toks) + 1):
        if all(
            _word_matches(name_toks[start + i], phrase_toks[i])
            for i in range(len(phrase_toks))
        ):
            return True
    return False


def _parse_keywords(cell: str) -> tuple[str, ...]:
    """Split a ``keywords`` cell on commas (or semicolons) into phrases."""
    seen: list[str] = []
    for part in re.split(r"[,;]", cell or ""):
        phrase = _clean_cell(part)
        if phrase and phrase.casefold() not in {p.casefold() for p in seen}:
            seen.append(phrase)
    return tuple(seen)


def parse_table(text: str) -> list[Rule]:
    """Parse the rows of every ranking table in a ``prestige.md`` body.

    Only tables whose header is ``conf name | ranking | keywords`` are read, so
    the rubric table and other prose tables in the same file are ignored. Columns
    beyond the third are ignored, which allows an optional ``notes`` column.

    Raises:
        ValueError: a row of a ranking table has an unparseable ``ranking``
            (anything but 1/2/3) or an empty ``keywords`` cell. A typo must fail
            the run rather than silently rank a conference nowhere.
    """
    rules: list[Rule] = []
    in_table = False
    for lineno, line in enumerate((text or "").splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if set("".join(cells)) <= set("-: "):  # ||---|---| separator
            continue
        name = _clean_cell(cells[0])
        if name.casefold() in _HEADER_NAMES and _clean_cell(cells[1]).casefold() in (
            "ranking", "rank", "tier",
        ):
            in_table = True
            continue
        if not in_table:
            continue
        raw_tier = _clean_cell(cells[1])
        try:
            tier = int(raw_tier)
        except (TypeError, ValueError):
            raise ValueError(
                f"prestige.md line {lineno}: ranking {raw_tier!r} is not a number "
                f"(use one of {', '.join(map(str, TIERS))})"
            ) from None
        if tier not in TIERS:
            raise ValueError(
                f"prestige.md line {lineno}: ranking {tier} is not one of "
                f"{', '.join(map(str, TIERS))}"
            )
        keywords = _parse_keywords(cells[2])
        if not keywords:
            raise ValueError(
                f"prestige.md line {lineno}: row {name!r} has no keywords to match on"
            )
        rules.append(Rule(name=name, tier=tier, keywords=keywords, line=lineno))
    return rules


def load(path=None) -> list[Rule]:
    """Load rules from *path* (default :data:`DEFAULT_FILE`); missing file -> ``[]``.

    A missing registry is not an error: a fresh clone has no ``prestige.md`` and
    the pipeline must still run. Rows are returned sorted by tier so
    :func:`match_rule` can take the first hit.
    """
    target = Path(path) if path is not None else DEFAULT_FILE
    if not target.is_file():
        return []
    rules = parse_table(target.read_text(encoding="utf-8"))
    return sorted(rules, key=lambda r: (r.tier, r.line))


def match_rule(name, rules) -> Rule | None:
    """The winning :class:`Rule` for *name*, or ``None``.

    Lowest tier wins; ``rules`` is normally already sorted, but sorting here keeps
    the result independent of input order.
    """
    for rule in sorted(rules or [], key=lambda r: (r.tier, r.line)):
        if any(phrase_matches(name, kw) for kw in rule.keywords):
            return rule
    return None


def match_tier(name, rules) -> int | None:
    """The ranking for *name* (``1``/``2``/``3``), or ``None`` when unmatched."""
    rule = match_rule(name, rules)
    return rule.tier if rule else None


def all_matching_rules(name, rules) -> list[Rule]:
    """Every rule that matches *name*, lowest tier first (for conflict reporting)."""
    hits = [
        rule
        for rule in (rules or [])
        if any(phrase_matches(name, kw) for kw in rule.keywords)
    ]
    return sorted(hits, key=lambda r: (r.tier, r.line))
