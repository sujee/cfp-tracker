# Real-Time, Embedded, CPS & Robotics Conferences

- **Status:** Implemented as an independent listing source. Disabled by default for academic use.
- **Official/source URL:** [Conference tracker](https://automaticdai.github.io/realtime-embedded-conferences/)
- **Adapter:** [`src/process-realtime-embedded-conferences.py`](../../src/process-realtime-embedded-conferences.py)
- **Interface:** [Public conferences JSON](https://automaticdai.github.io/realtime-embedded-conferences/assets/data/conferences.json)
- **Verification:** Offline fixtures checked against the live schema on 2026-11-18.

## Data and access

The community-maintained listing publishes every conference as one record. Records include the conference's Markdown name and event link, type, status, location, event dates, submission deadline, precision, category, and remarks.

The adapter selects `Robotics & Learning` records with `status: upcoming`, `deadline_precision: day`, and a close on or after the shared cutoff. It parses Markdown links and uses an explicit official CFP link when remarks provide one. Without that link, it preserves the event link as the submission information link. Selected rows always carry normalized `robotics` and `physical.ai` topics.

## Caveats

This is an academic paper-deadline source, not a developer-speaking feed. Dates with month or year precision are estimates and are excluded. Do not treat approximate deadlines as published calls.

Main event dates and locations come from free-text listing fields. Cross-month ranges retain only the event start. Unknown locations become `—`, and unknown countries remain empty.

The listing is community-maintained rather than organizer-controlled. Verify important deadlines on the organizer's CFP page.

## Integration guidance

Enable `realtime-embedded-conferences` in `INPUT_SOURCES` only when academic paper rounds belong in the product. Keep the source outside speaking-only refreshes. Duplicate rows use normalized name, close date, and URL identity.

## Evidence

- [Tracker](https://automaticdai.github.io/realtime-embedded-conferences/) — statuses and precision explanations.
- [Repository](https://github.com/automaticdai/realtime-embedded-conferences) — source maintenance and schema.
- [Fixture-based tests](../../tests/test_listing_sources.py) — current records, estimates, CFP links, and cross-month dates.
