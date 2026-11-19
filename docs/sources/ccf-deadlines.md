# CCF Deadlines

- **Status:** Implemented as an independent academic listing source. Disabled by default for academic use.
- **Official/source URL(s):** [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines), [CCFDDL AI venues](https://ccfddl.com/venues/ai/)
- **Adapter:** [`src/process-ccf-deadlines.py`](../../src/process-ccf-deadlines.py)
- **Interface:** [Structured `allconf.json` catalogue](https://ccfddl.com/conference/allconf.json), plus the maintained MIT YAML repository.
- **Verification:** Repository review dated 2026-11-11. Listing adapter verified 2026-11-18.

## Data and access

The catalogue publishes one conference-series object per venue. Editions include links, event dates, locations, timezone labels, and typed deadline rounds. The adapter selects named robotics series and robotics-described AI venues.

The adapter emits separate rows for `abstract_deadline`, `deadline`, `rebuttal_deadline`, and `decision_deadline`. Each row name includes the stage and source comment. Deadline text retains its timezone instead of forcing all rounds into one submission date. Every row carries normalized `robotics` and `physical.ai` topics.

## Caveats

These are academic deadlines, not talk CFPs. Repository conventions treat date-only values as `23:59:59` and unknown zones as `AoE`. These conventions do not prove organizer-stated clock time or timezone precision.

The adapter ignores derived `opening` timestamps. Rebuttal and decision rounds remain distinct from the initial call. Event dates retain only the start date, and unknown countries remain empty. Links can lead to the conference homepage instead of a dedicated CFP page.

## Integration guidance

Enable `ccf-deadlines` in `INPUT_SOURCES` only when academic rounds belong in the product. Keep the source outside speaking-only refreshes. AgentConfs already consumes this dataset, so deduplicate shared venues instead of importing them twice as new speaker opportunities.

## Evidence

- [Repository and schema](https://github.com/ccfddl/ccf-deadlines#conference-entry-file) — conference-entry fields and conventions.
- [AgentConfs methodology](https://agentconfs.com/llms.txt) — shared upstream coverage.
- [Fixture-based tests](../../tests/test_listing_sources.py) — independent stages, timezone preservation, and cross-month event dates.
