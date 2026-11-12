# CCF Deadlines

- **Status:** Academic paper deadlines / separate product only.
- **Official/source URL(s):** [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines).
- **Interface:** Maintained, MIT-licensed YAML dataset with typed deadline rounds.
- **Verification:** Compact repository-and-schema assessment dated 2026-11-11.

## Data and access

The repository publishes structured academic conference deadlines in YAML, including venue links and typed rounds. Its [conference-entry schema](https://github.com/ccfddl/ccf-deadlines#conference-entry-file) documents repository conventions. By convention, date-only values are treated as `23:59:59`, and an unknown timezone is treated as `AoE` (Anywhere on Earth).

## Caveats

Those time and timezone defaults are dataset conventions, not organizer-stated precision; preserve that distinction when displaying or comparing deadlines. Records concern paper submissions and typed academic rounds, not talk CFPs, and do not guarantee a distinct speaking-application URL.

## Integration guidance

Keep this dataset outside the developer-speaking tracker unless a separate academic paper-deadline product is approved. Then model rounds explicitly rather than collapsing them into one speaker deadline, and retain convention metadata. [AgentConfs already consumes ccf-deadlines](https://agentconfs.com/llms.txt), so assess overlap before adding duplicate academic ingestion; finer rounds would need to justify that addition.

## Evidence

The compact review identified a maintained MIT YAML dataset, typed rounds, the `23:59:59` and `AoE` conventions, and AgentConfs overlap. It explicitly classified the source as suitable only for a separate academic product.
