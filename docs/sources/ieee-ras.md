# IEEE Robotics and Automation Society deadlines

- **Status:** Implemented as an independent listing source. Disabled by default for academic use.
- **Official/source URL:** [IEEE RAS deadlines](https://www.ieee-ras.org/events/category/important-dates/deadlines/list/)
- **Adapter:** [`src/process-ieee-ras.py`](../../src/process-ieee-ras.py)
- **Interface:** [Official deadline iCalendar feed](https://www.ieee-ras.org/events/category/important-dates/deadlines/list/?ical=1)
- **Verification:** Offline fixtures checked against the live feed on 2026-11-18.

## Data and access

The feed publishes one `VEVENT` per deadline. Records include the all-day deadline, title, description, category, UID, and official detail URL.

The adapter unfolds continuation lines and decodes iCalendar escapes. It retains deadline records whose close is on or after the shared cutoff. It strips the paper-submission prefix from each title while preserving the conference name and short code. Every selected row carries normalized `robotics` and `physical.ai` topics.

## Caveats

These are paper deadlines, not speaking calls. The feed does not supply a normalized open status or a precise cutoff time. Deadline dates can change without a matching conference record.

The adapter does not infer event dates, locations, or countries from deadline pages. Unavailable values remain `TBA`, `—`, or empty. Event and CFP URLs both link to the official deadline detail page.

RSS and CoRL are outside RAS coverage, so this source requires other listings for complete robotics coverage.

## Integration guidance

Enable `ieee-ras` in `INPUT_SOURCES` only when academic paper rounds belong in the product. Keep it outside speaking-only refreshes. Reconcile rows by normalized name, close date, and detail URL rather than the event UID alone.

## Evidence

- [Deadline list](https://www.ieee-ras.org/events/category/important-dates/deadlines/list/) — current official deadline records.
- [Conference calendar](https://www.ieee-ras.org/events/category/conferences/) — separate event metadata for later enrichment.
- [Fixture-based tests](../../tests/test_listing_sources.py) — multiple deadline records, date filtering, and source labels.
