# foss.events

- **Status:** Later specialist candidate with share-alike obligations
- **Official/source URL(s):** [foss.events](https://foss.events/), [data policy and license](https://foss.events/about.html#license)
- **Interface:** Small public event-index HTML and linked event pages; no currently verified bulk export
- **Verification:** 2026-11-11

## Data and access

The index exposes future CFP mentions and links to event pages carrying event dates, venue/location, type, language, timezone, deadline and direct contribution URL. Scope is deliberately narrow: public, full-day FOSS events in Europe and online events organized by European groups. Maintainers collect and recheck entries manually while disclaiming completeness and correctness.

**2026-11-11 snapshot:** three future CFP mentions—Odak 2026 (2026-11-26), OCX 2027 (2026-12-06) and foss-north 2027 (2027-02-15).

The database is **ODbL**; individual fields are **CC BY-SA 4.0**, excluding `Self-description`. Attribution and a source link are required, and derivatives built on the data must be republished as open data. Rights to `Self-description` remain with event authors.

## Caveats

Although documentation mentions `/data/` and `*_events_db.csv`, the inspected Codeberg `data/` directory contained only `events_db_license.txt`; guessed website CSV URLs returned 404. Do not design around that unavailable dump. HTML/microdata is the verified representation. Share-alike obligations affect persistent derived collections, not just copied prose.

## Integration guidance

Proceed only after accepting attribution/share-alike requirements and either confirming a current export or approving a fixture-tested, low-frequency HTML parser. Weekly index parsing is sufficient at current volume. Preserve raw deadline text alongside any interpreted date, validate the contribution page, avoid copying `Self-description`, and measure overlap with broader feeds before owning notes.

## Evidence

[Upcoming index](https://foss.events/) · [foss-north record](https://foss.events/2027/04-19-foss-north-2027.html) · [license](https://foss.events/about.html#license) · [Codeberg data directory](https://codeberg.org/api/v1/repos/foss.events/foss-events-website/contents/data)
