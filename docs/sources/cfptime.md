# CFPTime

- **Status:** Later pilot after permission/validation
- **Official/source URL(s):** [cfptime.org](https://www.cfptime.org/), [API documentation](https://api.cfptime.org/api/docs)
- **Interface:** `GET https://api.cfptime.org/api/cfps/`; `/api/upcoming/`, paginated `/api/previously/`, `/openapi.json`
- **Verification:** 2026-11-11

## Data and access

The public, unauthenticated security API exposes `cfp_deadline`, `conf_start_date`, city, province, two-letter country, `website`, free-text `cfp_details`, `speaker_benefits`, code of conduct, creation time and event duration. Deadlines are ISO datetimes without serialized offsets; the HTML presents them as UTC.

**2026-11-11 snapshot:** 11 current open calls, matching the HTML count, including SO-CON, BSides Tirol, RE//verse, Nullcon Goa and several other practitioner-security events.

## Caveats

There is no dedicated `cfp_url` or exact event-end field. `website` alternates between an event site and a direct Sessionize submission page; other submission URLs occur only inside `cfp_details`. Benefits can be meaningful, explicitly absent or placeholders such as `Not populated yet`. One current Stockholm record was incorrectly coded `country: US`, so country and dates require official-page validation. No explicit data-reuse license was found in OpenAPI or the public About page. This is neither a complete BSides registry nor an authoritative deduplication key source.

## Integration guidance

Resolve reuse permission before persistent redistribution. Then pilot with strict anomaly checks: validate close/event dates and country against organizer pages, discard placeholders, and extract only identifiable organizer, Sessionize or Pretalx submission links from free text. Keep unresolved rows for review. Deduplicate against BSides Global, chapter sites and existing security feeds to avoid repeated upstream records.

## Evidence

[Open CFP API](https://api.cfptime.org/api/cfps/) · [OpenAPI schema](https://api.cfptime.org/openapi.json) · [HTML list](https://www.cfptime.org/) · [About](https://www.cfptime.org/about)
