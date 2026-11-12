# CFP Directory

- **Status:** Later pilot / undocumented endpoint
- **Official/source URL(s):** [cfp.directory](https://cfp.directory/), [public events UI](https://cfp.directory/events), [self-hosted project](https://github.com/l33tdawg/cfp-directory-self-hosted)
- **Interface:** Unauthenticated `GET https://cfp.directory/api/events`
- **Verification:** 2026-11-11

## Data and access

The public application endpoint returned one JSON array, without pagination or credentials. Records provide `event_name`, `slug`, event dates, venue/city/nullable country, `event_website`, type, rich topics, timezone and timezone-aware CFP boundaries. Map `event_website` to the event URL and derive the CFP URL as `https://cfp.directory/events/{slug}`.

**2026-11-11 snapshot:** 13 events in approximately 272 KB, seven marked open, five closed and one upcoming. Every open row had a future `cfp_end_at`. `Cache-Control: public, max-age=300` permits a five-minute shared cache.

## Caveats

`/api/events` is an **undocumented public app endpoint**, not the separate self-hosted repository’s authenticated federation API. There is no located public schema, version/stability promise, rate-limit policy or explicit bulk-reuse license. `/robots.txt` returned a custom 404, which leaves policy unstated rather than granting permission. `cfp_deadline` can be null while `cfp_end_at` is populated; country must remain unknown when null.

## Integration guidance

Run only as a disable-able shadow pilot with a pinned response fixture and a five-minute cache. Filter **both** `cfp_status == "open"` and `cfp_end_at >= now`. Fail closed on non-JSON, unexpected pagination/shape changes, missing slug/deadline or unexplained growth. Seek API and reuse confirmation before allowing note ownership; one request per refresh keeps current cost low.

## Evidence

[Public JSON](https://cfp.directory/api/events) · [event URL example](https://cfp.directory/events/security-bsides-dehradun-0x03) · [federation documentation](https://github.com/l33tdawg/cfp-directory-self-hosted)
