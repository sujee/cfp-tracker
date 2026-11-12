# confs.tech

- Status: Implemented
- Official/source URL(s): [confs.tech](https://confs.tech/), [`tech-conferences/conference-data`](https://github.com/tech-conferences/conference-data)
- Interface: GitHub directory listings under [`conferences/<year>/`](https://api.github.com/repos/tech-conferences/conference-data/contents/conferences) and raw `conferences/<year>/<topic>.json`; adapter [`src/process-confs-tech.py`](../../src/process-confs-tech.py)
- Verification: 2026-11-11

## Data and access

The community repository is MIT-licensed and publicly readable without application credentials. Event rows can contain `name`, `url`, `cfpUrl`, `cfpEndDate`, `startDate`, `city`, and `country`. The adapter discovers this year and next year through the GitHub contents API, then fetches raw JSON. Readable listing/topic caches have no expiration; per-listing or per-file failures are logged and skipped.

## Caveats

There is **no `ai` topic file** in the verified source tree. The current configuration requests `devops`, `opensource`, `python`, and `ai`, while `general` is always included; the nonexistent `ai` selection yields nothing itself, so AI events must arrive through `general` or another real topic. Setting `CONFS_TECH_TOPICS` empty selects every discovered topic. Dates must parse as supported ISO values. Source-level dedupe is normalized **name only** across both years and selected topics, so distinct editions or revised deadlines with the same name can collapse.

## Integration guidance

Filter `cfpEndDate` inclusively against the 30-day-default cutoff. Map `url` and `cfpUrl` to event and CFP URLs, parse `startDate`, and join nonempty city/country for display location. Despite upstream country and topic-file membership, the current normalized row deliberately writes `country: ""` and `topics: []`; the writer does not infer country from location. Ignore-term filtering uses only the event name. This source ranks below cfp.ninja and above adato-tracker. Its CLI also refreshes the commented discovered-topic list in `src/config.py`.

## Evidence

- [Data repository](https://github.com/tech-conferences/conference-data) — schema, license, and maintenance context.
- [Conference directory API](https://api.github.com/repos/tech-conferences/conference-data/contents/conferences) — available year directories.
