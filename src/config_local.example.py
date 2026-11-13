"""Personal CFP pipeline settings.

Copy this file to ``src/config_local.py`` and edit that copy::

    cp src/config_local.example.py src/config_local.py

``config_local.py`` is gitignored. It replaces only settings it defines; all
other values come from ``config.py``. Setting names are ALL_CAPS and must be
listed in ``config.KNOWN_SETTINGS``; unknown names fail the run. Public imports
and other non-ALL_CAPS names are ignored, and helper names may start with ``_``.
This example reproduces the maintainer's personal configuration.
"""

# confs.tech topics to fetch. general.json is always included; set() means all.
CONFS_TECH_TOPICS = {
    "devops",
    "opensource",
    "python",
    "ai",
}

# Sources to fetch, in run order. Keep nonempty; unknown names fail the run.
INPUT_SOURCES = [
    "developers.events",
    "cfp.ninja",
    "python-deadlines",
    "confs.tech",
    "adato-tracker",
    "open-tech-cfps",
    "manual",
]

# Only these files inside input/ are read by the manual source.
MANUAL_INPUT_FILES = [
    "gmail1.md",
    "conferences-to-check.md",
]

# Event types retained in data/. Others are skipped and their notes archived.
EVENT_TYPES = [
    "conference",
    "summit",
    "workshop",
]

# Optional: override the inference aliases in config.py. Keys must be inferable
# event types; mapping order controls precedence.
# EVENT_TYPE_KEYWORDS = {
#     "meetup": ["meetup", "meet-up", "user group"],
#     "summit": ["summit"],
#     "workshop": ["workshop"],
#     "hackathon": ["hackathon"],
#     "webinar": ["webinar"],
# }

# Case-insensitive event-name fragments to reject before note creation.
IGNORE_NAMES = [
    ".NET",
]

# Case-insensitive event-name/topic terms rejected by source adapters.
IGNORE_TOPICS = [
    "bitcoin",
    "crypto",
    "frontend",
    "javascript",
    "mobile",
    "dotnet",
]
