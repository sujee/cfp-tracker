"""Shared configuration for the CFP pipeline."""

# confs.tech topic/category JSON files to include. general.json is always included.
# Use upstream filename stems. An empty set includes every discovered topic file.
CONFS_TECH_TOPICS = {
    "devops",
    "opensource",
    "python",
    "ai"
}

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
