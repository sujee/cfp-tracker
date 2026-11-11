#!/usr/bin/env python3
"""Canonicalise the ``country`` value written into each CFP note.

Sources spell the same place differently — cfp.ninja writes ``United Kingdom``
where developers.events writes ``UK`` — and the ``cfps`` base filters on literal
values (``country == "USA"``).  :func:`normalize_country` folds the common
spellings of a handful of countries, plus the online/empty cases, onto one
canonical label, and leaves anything else untouched.

Canonical labels keep the conventions already present under ``data/``: ``USA``
and ``UK`` for those two (informal but conventional) abbreviations, full English
names for everything else, ``Online`` for virtual events and ``""`` for unknown.
"""
from __future__ import annotations

import re

ONLINE = "Online"

# Canonical label -> every spelling that folds onto it.  Keys are matched after
# :func:`_key`, so give plain words/phrases only (case, punctuation and extra
# spaces are handled for you).
_ALIAS_GROUPS: dict[str, list[str]] = {
    "USA": [
        "usa",
        "us",
        "u s",
        "u s a",
        "united states",
        "the united states",
        "united states of america",
        "america",
    ],
    "UK": [
        "uk",
        "u k",
        "united kingdom",
        "great britain",
        "britain",
        "gb",
        "england",
        "scotland",
        "wales",
        "northern ireland",
    ],
    ONLINE: [
        "online",
        "virtual",
        "remote",
        "online only",
        "virtual event",
        "online event",
        "virtual conference",
        "worldwide",
        "anywhere",
    ],
    "Netherlands": ["netherlands", "the netherlands", "holland", "nl"],
    "United Arab Emirates": ["united arab emirates", "uae", "u a e"],
    "Czechia": ["czechia", "czech republic"],
    "South Korea": ["south korea", "korea", "republic of korea"],
    "Ivory Coast": ["ivory coast", "cote d ivoire", "côte d ivoire"],
    "Turkey": ["turkey", "türkiye", "turkiye"],
    "Russia": ["russia", "russian federation"],
    "Vietnam": ["vietnam", "viet nam"],
    "Brazil": ["brazil", "brasil"],
    "Macedonia": ["macedonia", "north macedonia"],
    "Swaziland": ["swaziland", "eswatini"],
}


def _key(value: str) -> str:
    """Fold a spelling for lookup: lower-case, drop punctuation, squeeze spaces.

    ``"U.S.A."`` → ``"u s a"``, ``"Côte d'Ivoire"`` → ``"côte d ivoire"``.
    """
    s = (value or "").strip().lower().replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


# Flat lookup built once from the groups above (later groups never collide, but
# first-wins keeps it deterministic if a spelling is ever listed twice).
ALIASES: dict[str, str] = {}
for _canonical, _spellings in _ALIAS_GROUPS.items():
    for _spelling in _spellings:
        ALIASES.setdefault(_key(_spelling), _canonical)
del _canonical, _spellings, _spelling


def normalize_country(value: str | None) -> str:
    """Return the canonical label for *value*, or *value* unchanged when unknown.

    ``""``/``None``/whitespace collapse to ``""``.  Anything not in the alias
    table (``Germany``, ``Poland``, ``Peru``, …) is returned stripped but
    otherwise as-is, so the function never invents a country.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    return ALIASES.get(_key(raw), raw)
