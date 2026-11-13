# developers.events

- Status: Implemented
- Official/source URL(s): [developers.events](https://developers.events/), [upstream data repository](https://github.com/scraly/developers-conferences-agenda)
- Interface: [`all-cfps.json`](https://developers.events/all-cfps.json) and [`all-events.json`](https://developers.events/all-events.json); adapter [`src/process-developer-events.py`](../../src/process-developer-events.py)
- Verification: 2026-11-11

## Data and access

The public JSON needs no authentication. CFP records provide `link`, free-text `until`, epoch-millisecond `untilDate`, and `conf` event data. The separate events file supplies dates, locations, links, and `tech`/`topic`/`language` tags for enrichment. The adapter fetches live data through the shared online-first cache. A failed fetch uses a valid cached response. `--offline` requires cached responses.

## Caveats

Do not scrape the rendered CFP page or filter on `conf.status`: the page is a stale build-time snapshot, and historical records can still say `open`. Use UTC dates from `untilDate`, not `until`. Match same-named event editions by location first and then the nearest date on/after the deadline; names alone can join the wrong year or city. Prefer the trailing location parenthetical for country because structured country values can be wrong. The source exposes deadlines, not a CFP-opening note field.

## Integration guidance

Select deadlines inclusively from the default cutoff of approximately 30 days back. Use the shared `--months-back` or `--past-days` option to change the window. Duplicate export rows collapse by normalized name and close date. Map `link` to `cfp_url`, the matched event's `hyperlink` or the CFP's `conf.hyperlink` to `event_url`, and the earliest event date to `event_date`. `tech`/`topic` tags become topics. `language` tags become lowercase cumulative note languages. The writer canonicalizes country, strips UTM parameters, and infers sticky `event_type`. This source ranks below `manual` but above every other feed among current rows.

## Evidence

- [Upstream repository](https://github.com/scraly/developers-conferences-agenda) — source project and maintenance context.
- [Live CFP JSON](https://developers.events/all-cfps.json) — CFP records and deadline fields.
- [Live event JSON](https://developers.events/all-events.json) — enrichment records and tags.
