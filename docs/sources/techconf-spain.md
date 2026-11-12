# TechConf Spain

- Status: Recommended next
- Official/source URL(s): [TechConf Spain](https://techconf.es/), [`npatarino/tech-conferences-spain`](https://github.com/npatarino/tech-conferences-spain)
- Interface: [`https://techconf.es/events.json`](https://techconf.es/events.json) (OpenTechEvents v0.6)
- Verification: 2026-11-11

## Data and access

The keyless, CORS-enabled JSON publishes `events[]` with stable `id`/`partOf`, event `url`, ISO `startDate`/`endDate`, `timezone`, attendance mode, structured `location.address.locality`/`country`, venue, `tags`, `languages`, `status`, and a CFP block containing `url`, optional `opensAt`, and `closesAt`. Conference data is **CC BY 4.0**, declared by the feed and project documentation. On 2026-11-11 the feed reported `updatedAt: 2026-11-11T17:49:18.908Z`, contained 460 editions, and had five close timestamps on/after that date—snapshot counts, not standing coverage.

## Caveats

Most editions are historical and have no current CFP; volume must not be confused with live yield. Consume only `events[]`, skip `status != scheduled`, and filter the actual `cfp.closesAt`. Expect overlap with broad developer feeds even though normalization is straightforward. Stable source identifiers/series are not automatically persistent fields in the tracker's present note schema.

## Integration guidance

Require a usable close timestamp and actionable `cfp.url`; map event `url`→`event_url`, `cfp.url`→`cfp_url`, `startDate`→event start, structured locality/country, tags, and languages. Retain timezone and `partOf` in adapter parsing for correct date handling and series review, without inventing new note properties. Apply source-level normalized-name/close dedupe, then the shared compatible-name URL rules. Do not manufacture missing values. Proposed ownership is below cfp.ninja and above PythonDeadlin.es; quantify unique post-dedupe speaking notes before enabling this candidate in the pipeline.

## Evidence

- [Live OpenTechEvents feed](https://techconf.es/events.json) — schema, update timestamp, and dated examples.
- [Repository README and OTE mapping](https://raw.githubusercontent.com/npatarino/tech-conferences-spain/main/README.md) — source files, feed semantics, and license.
- [Repository metadata](https://api.github.com/repos/npatarino/tech-conferences-spain) — repository maintenance evidence checked on the verification date.
