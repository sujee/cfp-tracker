# AI Deadlines

- **Status:** Academic paper deadlines / separate product only.
- **Official/source URL(s):** [huggingface/ai-deadlines](https://github.com/huggingface/ai-deadlines); historical [paperswithcode/ai-deadlines](https://github.com/paperswithcode/ai-deadlines).
- **Interface:** Maintained, MIT-licensed YAML dataset hosted on GitHub.
- **Verification:** Compact repository-and-schema assessment dated 2026-11-11.

## Data and access

The maintained Hugging Face repository provides structured academic conference deadline data in YAML under an MIT license. Its [README and schema](https://github.com/huggingface/ai-deadlines#readme) are the appropriate starting point for understanding fields and updates. This is paper-submission deadline data, not a developer speaking-CFP feed.

## Caveats

Academic venue and deadline records do not guarantee a distinct talk-submission URL. Do not mix paper rounds into speaking reminders without a separate product decision. The original Papers With Code repository was last pushed in 2024; do not use that inactive original to displace maintained descendants or forks.

## Integration guidance

Do not add this source to the current developer-speaking pipeline. If an academic product is approved, evaluate the maintained dataset on its own and preserve its deadline semantics. Check overlap first: [AgentConfs already consumes ai-deadlines](https://agentconfs.com/llms.txt), so direct ingestion could duplicate existing academic intake.

## Evidence

The compact review identified the Hugging Face repository as maintained MIT YAML, distinguished academic paper deadlines from speaking CFPs, documented AgentConfs overlap, and recorded the 2024 last-push finding for the original repository.
