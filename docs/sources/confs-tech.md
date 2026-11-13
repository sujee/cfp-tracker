# confs.tech

- Status: Implemented
- Official/source URL(s): [confs.tech](https://confs.tech/), [`tech-conferences/conference-data`](https://github.com/tech-conferences/conference-data)
- Interface: GitHub directory listings and `conferences/<year>/<topic>.json`
- Adapter: [`src/process-confs-tech.py`](../../src/process-confs-tech.py)
- Verification: 2026-11-12

## Data and access

The community repository is MIT-licensed and publicly readable without application credentials.
The adapter reads this year and next year through the GitHub contents API. It fetches selected topic
files through the shared online-first cache. `--offline` requires cached responses.

A listing or topic-file failure aborts the source. The full pipeline then stops before note writes.
Malformed listings, malformed topic data, and non-object events also abort the source.

## Selection and caveats

There is **no `ai` topic file** in the verified source tree. The current personal configuration
requests `devops`, `opensource`, `python`, and `ai`. `general` is always included. An empty
`CONFS_TECH_TOPICS` collection selects every discovered topic. Name-based ignore filters apply.

`cfpEndDate` must parse as a supported ISO value. Selection compares it with the shared cutoff.
Exact export duplicates collapse. Distinct deadline, event date, location, and CFP URL values remain
available for reconciliation.

## Integration guidance

`url` and `cfpUrl` supply event and submission URLs. `startDate` supplies the event start.
City and country supply a display location. Structured country and online values populate `country`.
A specialized topic-file name becomes a topic. Rows from `general.json` do not invent a topic.

This source ranks below cfp.ninja and above adato-tracker among current rows. Its CLI writes
`src/discovered-topics.txt` only when `--write-discovered-topics` is present.

## Evidence

- [Data repository](https://github.com/tech-conferences/conference-data) — schema, license, and maintenance context.
- [Conference directory API](https://api.github.com/repos/tech-conferences/conference-data/contents/conferences) — available year directories.
