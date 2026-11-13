"""Default configuration for the CFP pipeline.

Keep personal settings in ``config_local.py`` beside this file. Copy
``config_local.example.py`` to get started::

    cp src/config_local.example.py src/config_local.py

The local file replaces only the settings it defines. It is gitignored; this
file and the example are tracked. Unknown ALL_CAPS setting names fail loudly so
a typo cannot silently revert to a default.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

# confs.tech topic/category JSON files to include. general.json is always included.
# Use upstream filename stems. An empty set includes every discovered topic file.
CONFS_TECH_TOPICS = {
    "devops",
    "opensource",
    "python",
    "ai",
}

# Which sources the refresh fetches, in run order (mirrors SOURCE_PRIORITY in
# cfp_writer.py). Remove a source to skip it for a run. Notes owned by a
# skipped source are left in data/ untouched — they are NOT archived — so you can
# re-enable the source later without losing anything. Keep nonempty; unknown or
# empty values fail the run (same contract as EVENT_TYPES).
INPUT_SOURCES = [
    "developers.events",
    "cfp.ninja",
    "confs.tech",
    "adato-tracker",
    "open-tech-cfps",
    "manual",
]

# Explicit manual input files, relative to input/. No other single markdown file
# is read automatically — a checklist, scratch table, or new import file is not a
# CFP source until it is listed here (and the manual source is enabled above).
# The default is empty; name your personal files in config_local.py. A missing
# or absolute path fails the manual step.
MANUAL_INPUT_FILES = []

# Allow-list of event_type values to keep in data/. Other types are skipped and
# existing notes are archived. Valid values: conference, meetup, summit,
# workshop, hackathon, webinar, other. Keep nonempty; invalid values fail a run.
# To keep only conferences and summits: EVENT_TYPES = ["conference", "summit"]
EVENT_TYPES = [
    "conference",
    "summit",
    "workshop",
]

# Singular event-name aliases used to infer event_type. The mapping order controls
# precedence. Matching ignores case, treats spaces and hyphens as interchangeable,
# and accepts an optional plural "s". Use meetup, summit, workshop, hackathon, or
# webinar keys. New aliases affect new notes and notes without an event_type only.
EVENT_TYPE_KEYWORDS = {
    "meetup": [
        "meetup",
        "meet-up",
        "meet up",
        "user group",
        "user-group",
        "usergroup",
    ],
    "summit": ["summit"],
    "workshop": ["workshop"],
    "hackathon": ["hackathon"],
    "webinar": ["webinar"],
}

# Blacklist: drop any event whose name contains one of these strings, ignoring case.
IGNORE_NAMES = []

# Blacklist: drop any conference whose name/topics contain these terms.
IGNORE_TOPICS = []

KNOWN_SETTINGS = frozenset({
    "CONFS_TECH_TOPICS",
    "INPUT_SOURCES",
    "MANUAL_INPUT_FILES",
    "EVENT_TYPES",
    "EVENT_TYPE_KEYWORDS",
    "IGNORE_NAMES",
    "IGNORE_TOPICS",
})
LOCAL_CONFIG_PATH = Path(__file__).resolve().with_name("config_local.py")


def local_overrides(path: Path | str | None = None) -> dict:
    """Return validated ALL_CAPS overrides from the user's local config file.

    A missing file returns an empty mapping. Syntax or runtime errors in the
    file propagate instead of silently reverting to defaults. Public names that
    are not ALL_CAPS (such as imported classes) are ignored; use a leading
    underscore for helpers.
    """
    config_path = Path(path) if path is not None else LOCAL_CONFIG_PATH
    if not config_path.is_file():
        return {}

    spec = importlib.util.spec_from_file_location("cfp_config_local", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load local configuration from {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    values = {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_") and name.isupper()
    }
    unknown = sorted(set(values) - KNOWN_SETTINGS)
    if unknown:
        raise ValueError(
            f"unknown setting(s) in {config_path.name}: {', '.join(unknown)}; "
            f"known settings: {', '.join(sorted(KNOWN_SETTINGS))}"
        )
    return values


def validate_filter_settings() -> None:
    """Reject collection settings that could silently filter out a whole source."""
    for name in ("IGNORE_NAMES", "IGNORE_TOPICS", "CONFS_TECH_TOPICS"):
        value = globals()[name]
        if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
            raise ValueError(f"config.{name} must be a collection of nonempty strings")
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"config.{name} must contain nonempty strings")


globals().update(local_overrides())
validate_filter_settings()
