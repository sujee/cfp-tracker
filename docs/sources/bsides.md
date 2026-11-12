# BSides Global

- **Status:** BSides Global, manual/enrichment
- **Official/source URL(s):** [bsides.org/events](https://bsides.org/events)
- **Interface:** Official event-calendar HTML, free-text chapter details and exportable ICS; organizer-linked external CFP pages
- **Verification:** 2026-11-11

## Data and access

BSides Global is authoritative event-level enrichment for chapter identity, dates, locations, official links and flags such as `Unconfirmed`. Some chapter details contain an external CFP link—for example BSides Groningen 2027 linked Sessionize—but the central listing does not systematically publish CFP close dates.

**2026-11-11 snapshot:** the official events page listed 68 upcoming BSides events. Its ICS export supports calendar reconciliation, not a normalized CFP feed.

## Caveats

Do not invent a uniform deadline when a chapter detail lacks one, and do not treat an event listing as an open call. CFPTime and official chapter sites overlap this directory for records such as BSides Tirol and Red Rocks; joining requires compatible chapter/year identity rather than series name alone. No explicit open-data license was found on the checked calendar output.

**AllBSides is a different, stale cross-check, not this official source.** On 2026-11-11, `allbsides.com/cfp.html` still labeled May–August 2026 deadlines “Open CFPs Right Now.” Its own text acknowledges chapter-specific timelines. Do not use it as CFP truth or as a substitute for BSides Global plus the actual chapter page.

## Integration guidance

Use BSides Global manually to enrich an existing note’s event date, location, status and official chapter URL. Obtain CFP URL/deadline from CFPTime, a supported aggregator or preferably the chapter’s own current page, then verify title/year before linking. Keep the official event calendar as the identity authority and exclude unverified chapter details from automatic date publication.

## Evidence

[Official BSides calendar](https://bsides.org/events) · [CFPTime overlap check](https://api.cfptime.org/api/cfps/) · [stale AllBSides page](https://allbsides.com/cfp.html)
