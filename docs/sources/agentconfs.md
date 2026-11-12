# AgentConfs

- Status: Recommended next (**speaking-only filtering required**)
- Official/source URL(s): [AgentConfs](https://agentconfs.com/), [methodology](https://agentconfs.com/llms.txt)
- Interface: [`https://agentconfs.com/data/events.json`](https://agentconfs.com/data/events.json)
- Verification: 2026-11-11

## Data and access

The keyless JSON includes `name`/`full_name`, `type`, `official_url`, event dates, `cfp_open`/`cfp_close`/`cfp_url`, city/country/venue, format, `topic_tags`, `travel_grants`, `last_verified`, verification metadata, and field-level `sources` provenance. Reuse is **CC BY 4.0 with attribution to AgentConfs**; robots explicitly permits the data file. The 2026-11-11 document reported 596 events. A local calculation found 24 rows with a CFP URL and close on/after that date, versus 23 in the site's coverage summary; retain this dated discrepancy rather than forcing the figures to agree. No delta API is documented.

## Caveats

Coverage deliberately mixes developer-speaking opportunities with academic research-paper deadlines (for example CVPR, ACL, COLING, NAACL, and IJCAI). **Do not bulk-import all CFP-bearing rows.** Excluding `type: academic conference` is only an initial gate; manually/topic-review remaining rows for speaking relevance. Conference-only rows are not CFPs. Its upstreams include developers.events, confs.tech, ai-deadlines, and ccf-deadlines, so duplicates and academic contamination are expected.

## Integration guidance

Require nonempty `cfp_url`, a current `cfp_close`, and passage through the speaking-only gate. Map `official_url`, `start_date`, city/country, and `topic_tags` to the common row. Use `sources.cfp` and `last_verified` for review/provenance, not as newly invented standard note fields; snapshot locally for change detection. Dedupe by normalized name/deadline and the shared compatible-name URL heuristic. Proposed ownership is below PythonDeadlin.es and above confs.tech, solely for accepted speaking rows. Measure actual unique yield rather than using raw unmatched counts.

## Evidence

- [Events JSON](https://agentconfs.com/data/events.json) — live-shaped records, types, CFP fields, and provenance.
- [Methodology and coverage](https://agentconfs.com/llms.txt) — discovery inputs, verification, and coverage semantics.
- [Robots policy](https://agentconfs.com/robots.txt) — explicit data-file access.
