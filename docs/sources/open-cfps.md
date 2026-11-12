# Open CFPs (Manvika Tuteja)

- **Status:** Later pilot after reuse permission
- **Official/source URL(s):** [dataset site](https://cfps.manvikatuteja.com/), [source repository](https://github.com/mtuteja-git/open-cfps)
- **Interface:** `https://cfps.manvikatuteja.com/data/cfps.json`; optional `/cal.ics`
- **Verification:** 2026-11-11

## Data and access

The keyless JSON contains `updated`, topic definitions and a `cfps` array. Each row can supply `id`, `name`, coded `topics`, city/country, event `start`/`end`, `close`, CFP `url` and `added`. The README says organizer pages are checked and data refreshes Monday at 07:00 Pacific; the inspected file and last push were dated 2026-11-02.

**2026-11-11 snapshot:** 156 rows, of which 20 already had deadlines before the verification date, leaving 136 date-current rows. Forty-seven matched neither baseline CFP URL nor exact normalized name; that conservative comparison is a discovery signal, not guaranteed unique-note yield.

## Caveats

The nominally open file retains expired rows, so `close >= today` is mandatory. There is no separate event URL, CFP opening timestamp/timezone or speaker-benefit field, and some academic calls share the pool. GitHub reported `license: null` and no repository-root LICENSE was found; public readability is not permission for persistent derived-data republication. Event URLs must not be invented from the CFP link.

## Integration guidance

Ask the maintainer about data reuse before integration. A subsequent weekly parser can map `url` to CFP URL, filter dates locally, retain topic codes and require an actionable submission link. Enrich event websites through reviewed official sources, apply developer-speaking relevance gates, and measure additions after URL plus compatible-name deduplication against the complete tracker.

## Evidence

[Live JSON](https://cfps.manvikatuteja.com/data/cfps.json) · [row format and calendar](https://github.com/mtuteja-git/open-cfps#readme) · [repository/license location](https://github.com/mtuteja-git/open-cfps)
