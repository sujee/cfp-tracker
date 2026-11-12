# PostgreSQL Event Calendar

- **Status:** Later specialist candidate
- **Official/source URL(s):** [ics.postgresql.life](https://ics.postgresql.life/)
- **Interface:** Public calendar HTML with direct per-entry `.ics` downloads; Google Calendar subscription and Mastodon updates
- **Verification:** 2026-11-11

## Data and access

The “Open Calls for Papers” section links a separate ICS file for each deadline. In those files, `DTSTART` represents the CFP deadline and `DESCRIPTION` contains organizer, announcement and/or submission links. The same landing page separately links conference-date records carrying locations, so event metadata and CFP deadlines require an identity join rather than one flat import.

**2026-11-11 snapshot:** five active deadlines—FOSDEM PostgreSQL Devroom (2026-11-28), FOSDEM PGDay (2026-12-01), PG DATA (2027-01-11), PgDay Boston (2027-01-15) and FroSCon (2027-05-23).

## Caveats

Descriptions mix HTML and plain text, links vary by event, and a deadline calendar entry does not independently supply a full conference note. Close dates are date-level values; do not invent exact times. Joining solely by a broad series name could attach dates from the wrong edition. No explicit open-data license appears on the calendar page, despite technically easy anonymous downloads. The normalization and review cost is high relative to the five-row yield.

## Integration guidance

After a reuse decision, parse only the open-CFP section and its linked ICS files, filter `DTSTART` against the cutoff, and extract recognizable official/submission URLs. Join event-date records by normalized name plus compatible edition/year, preserving unresolved joins for review. Prefer the linked organizer page for final URL and deadline verification; keep this as narrow database-community enrichment, not a general PostgreSQL event crawl.

## Evidence

[Calendar](https://ics.postgresql.life/) · [PG DATA ICS](https://ics.postgresql.life/qsvcagbe9c3nv684o3ul3uq619009qn8tdptnj6b0brd9ja73rfqngks18.ics) · [PgDay Boston ICS](https://ics.postgresql.life/1752k2gr0hvjk20tspgistef98.ics)
