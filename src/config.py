"""Shared configuration for the CFP pipeline."""

# confs.tech topic/category JSON files to include. general.json is always included.
# Use upstream filename stems. An empty set includes every discovered topic file.
CONFS_TECH_TOPICS = {
    "devops",
    "opensource",
    "python",
    "ai"
}

# Which sources the refresh fetches, in run order (mirrors SOURCE_PRIORITY in
# cfp_writer.py). Comment out a source to skip it for a run. Notes owned by a
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
# An empty list makes manual input a no-op; a missing or absolute path fails the
# row.
MANUAL_INPUT_FILES = [
    "gmail1.md",
    "conferences-to-check.md",
]


# Allow-list of event_type values to keep in data/. Other types are skipped and
# existing notes are archived. Valid values: conference, meetup, summit,
# workshop, hackathon, webinar, other. Keep nonempty; invalid values fail a run.
# To keep only conferences and summits: EVENT_TYPES = ["conference", "summit"]
EVENT_TYPES = [
    # Enabled event types observed in the current live notes:
    "conference",
    "summit",
    "workshop",

    # Additional supported types: uncomment to include them.
    # "hackathon",
    # "webinar",
    # "other",
    # "meetup",
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
IGNORE_NAMES = [
    ".NET",
]

# Blacklist: drop any conference whose name/topics contain these terms.
IGNORE_TOPICS = [
    "bitcoin",
    "crypto",
    "frontend",
    "javascript",
    "mobile",
    "dotnet",
]

# Discovered confs.tech topic files (reference only; NOT used for extraction):
# DISCOVERED_TOPICS = [
#     "accessibility",
#     "android",
#     "api",
#     "clojure",
#     "cpp",
#     "css",
#     "data",
#     "devops",
#     "dotnet",
#     "general",
#     "golang",
#     "graphql",
#     "groovy",
#     "haskell",
#     "ios",
#     "iot",
#     "java",
#     "javascript",
#     "kotlin",
#     "leadership",
#     "networking",
#     "opensource",
#     "performance",
#     "php",
#     "product",
#     "python",
#     "rust",
#     "security",
#     "sre",
#     "tech-comm",
#     "testing",
#     "typescript",
#     "ux",
# ]
