"""Shared configuration for the CFP pipeline."""

# Topics of interest. Variations/aliases are included so matching is loose.
TOPICS = {
    "agentic",
    "agentic-ai",
    "ai",
    "ai-agent",
    "ai-agents",
    "ai-coding",
    "coding",
    "containers",
    "devops",
    "developer-conference",
    "genai",
    "generative-ai",
    "kubernetes"
    "llm",
    "llms",
    "local llms",
    "machine-learning",
    "ml",
    "open models",
    "open source",
    "open source ai",
    "open-models",
    "open-source",
    "open-source-ai",
    "open-source-llm",
    "open-weights",
    "open-weight",
    "opensource",
    "python",
    "programming"
    "software-development",
    "software-engineering"
}

# Normalised (lower, hyphens/spaces collapsed) lookup set.
TOPICS_NORMALIZED = {t.lower().replace(" ", "-").replace("_", "-") for t in TOPICS}
TOPICS_NORMALIZED |= {t.lower().replace("-", " ") for t in TOPICS}
TOPICS_NORMALIZED |= {t.lower().replace(" ", "") for t in TOPICS}

# Blacklist: drop any conference whose name/topics contain these terms.
IGNORE_TOPICS = [
    "bitcoin",
    "crypto",
    "mobile",
]

IGNORE_TOPICS_NORMALIZED = {t.lower().replace(" ", "-") for t in IGNORE_TOPICS}

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
