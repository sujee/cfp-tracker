# Pretalx

- **Status:** Targeted enrichment, not global discovery
- **Official/source URL(s):** [pretalx.com](https://pretalx.com/), [API fundamentals](https://docs.pretalx.org/api/fundamentals/), [open-source project](https://github.com/pretalx/pretalx)
- **Interface:** Hosted `/api/events/`, `/api/events/{slug}/`; public `/{slug}/cfp` pages on known instances
- **Verification:** 2026-11-11

## Data and access

The hosted global event list returns `name`, `slug`, `is_public`, `date_from`, `date_to` and `timezone`, but no CFP deadline, location, topics or event URL. Detail adds domains, localization and presentation fields, still without deadline/location. A known public CFP page can instead expose prose such as `Submissions close on 2027-02-08 23:59 (Europe/Berlin)`.

**2026-11-11 snapshot:** `/api/events/` returned a bare array of 757 public hosted events; 81 were future or undated. Adding `page_size=1` returned the same 757-row shape, so normal pagination must not be assumed.

## Caveats

`pretalx.com/robots.txt` explicitly disallows `/api/`; anonymous HTTP 200 does not authorize a scheduled global crawl. No global bulk-data reuse grant was established. Authenticated limits of 360 requests/user/minute do not establish an anonymous quota. Independent self-hosted instances are absent from the global API and differ in version, routes, robots, policy and API behavior; each needs separate evaluation. Sweeping 81 hosted CFP pages would still miss that universe and incur needless fan-out.

## Integration guidance

Use the global list, if access is clarified, only for event/slug/date reconciliation. Prefer known pretalx URLs from existing feeds and parse a small allowlist of public `/cfp` pages for close text and timezone, retaining unparsed values for review. Do not treat it as a global deadline source, assume hosted semantics on another domain, or create conference-only duplicate notes.

## Evidence

[Global event list](https://pretalx.com/api/events/) · [sample detail](https://pretalx.com/api/events/open-data-hub-day-2027/) · [sample CFP](https://pretalx.com/open-data-hub-day-2027/cfp) · [robots](https://pretalx.com/robots.txt)
