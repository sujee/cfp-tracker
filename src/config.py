"""Shared configuration for the CFP pipeline."""

# confs.tech topic/category JSON files to include. general.json is always included.
# Use upstream filename stems. An empty set includes every discovered topic file.
CONFS_TECH_TOPICS = {
    "devops",
    "opensource",
    "python",
    "ai"
}

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

# Blacklist: drop any conference whose name/topics contain these terms.
IGNORE_TOPICS = [
    "bitcoin",
    "crypto",
    "frontend",
    "javascript",
    "mobile",
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
