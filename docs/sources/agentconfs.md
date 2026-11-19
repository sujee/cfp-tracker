# AgentConfs

- Status: Implemented and enabled by default, with speaking-only robotics filtering.
- Official/source URL(s): [AgentConfs](https://agentconfs.com/), [robotics topic](https://agentconfs.com/topics/robotics), [methodology](https://agentconfs.com/llms.txt)
- Interface: [`https://agentconfs.com/data/events.json`](https://agentconfs.com/data/events.json)
- Adapter: [`src/process-agentconfs.py`](../../src/process-agentconfs.py)
- Verification: 2026-11-11. Listing adapter verified 2026-11-18.

## Data and access

The keyless JSON includes `name`/`full_name`, `type`, `official_url`, event dates, `cfp_open`/`cfp_close`/`cfp_url`, city/country/venue, format, `topic_tags`, `travel_grants`, `last_verified`, verification metadata, and field-level `sources` provenance. Reuse is **CC BY 4.0 with attribution to AgentConfs**; robots explicitly permits the data file. The 2026-11-11 document reported 596 events. A local calculation found 24 rows with a CFP URL and close on/after that date, versus 23 in the site's coverage summary; retain this dated discrepancy rather than forcing the figures to agree. No delta API is documented.

The follow-up review verified a dedicated [Robotics & embodied AI topic](https://agentconfs.com/topics/robotics), its [topic calendar](https://agentconfs.com/feeds/topic-robotics.ics), and the shared [CFP calendar](https://agentconfs.com/feeds/cfp.ics). These feeds provide discovery data, not speaking-only status.

## Caveats

Coverage deliberately mixes developer-speaking opportunities with academic research-paper deadlines (for example CVPR, ACL, COLING, NAACL, and IJCAI). **Do not bulk-import all CFP-bearing rows.** Excluding `type: academic conference` is only an initial gate; manually/topic-review remaining rows for speaking relevance. Conference-only rows are not CFPs. Its upstreams include developers.events, confs.tech, ai-deadlines, and ccf-deadlines, so duplicates and academic contamination are expected.

Robotics records include conferences with no current CFP fields. Name matching also confuses Robot Framework with physical robots. Exclude RPA and software test automation when selecting physical-robot events.

## Integration guidance

The adapter selects robotics records by names, full names, and `topic_tags`. It rejects academic conference types, academic CFP provenance, Robot Framework, and RoboCon. Each accepted row requires a direct `cfp_url` and a current `cfp_close`.

The adapter maps `official_url`, `start_date`, city/country, and `topic_tags` to the common row. It also adds normalized `robotics` and `physical.ai` topics and merges equivalent labels. Use `sources.cfp` and `last_verified` for review/provenance, not as newly invented standard note fields. AgentConfs ownership ranks below PythonDeadlin.es and above confs.tech. Measure actual unique yield rather than using raw unmatched counts.

## Evidence

- [Events JSON](https://agentconfs.com/data/events.json) — live-shaped records, types, CFP fields, and provenance.
- [Methodology and coverage](https://agentconfs.com/llms.txt) — discovery inputs, verification, and coverage semantics.
- [Robots policy](https://agentconfs.com/robots.txt) — explicit data-file access.
- [Listing adapter tests](../../tests/test_listing_sources.py) — current speaking calls, academic exclusions, and RoboCon false positives.
- [Robotics & embodied AI topic](https://agentconfs.com/topics/robotics): event discovery and calendar feeds.
