# Events (events.fru.dev)

- **Status:** Event enrichment only
- **Official/source URL(s):** [events.fru.dev](https://events.fru.dev/), [agent guide](https://events.fru.dev/agents), [OpenAPI](https://events.fru.dev/openapi.json)
- **Interface:** `GET /api/conferences`, `/api/conferences/{id}`, `/api/search`, `/api/changes?since=YYYY-MM-DD`; `/api/calendar.ics`
- **Verification:** 2026-11-11

## Data and access

The public read API supplies conference/edition dates, tentative-date flags, city/country, format, venue, host, topics and official-site links. List filters include `from`, `to`, `host`, `place`, `topic`, `q`, `limit` (maximum 200) and `offset`. A nightly build draws from organizer sites, confs.tech and cfp.fru.dev; unverified discoveries are marked. Data is **CC BY 4.0**, with citation/link-back required and a requested ceiling around 60 requests/minute.

**2026-11-11 snapshot:** `llms.txt` reported 352 upcoming and 3,252 total conferences, 102 additions in 30 days from 1,416 sources, with the last run at 07:32:37 UTC.

## Caveats

There are **no systematic CFP deadlines or submission fields**. Dates can move and organizer pages remain authoritative; month-only and unverified entries need care. Coverage overlaps its named upstreams, so this is not an independent CFP corroboration chain. Robots allows the site generally but says `Disallow: /api/`, despite explicit OpenAPI/agent instructions—record this conflict and seek clarification before scheduling API polling.

## Integration guidance

Use targeted, interactive lookups to correct an existing note’s event identity, dates, location or official URL, then verify against the organizer. Do not create CFP notes from event existence alone or manufacture a deadline. Attribute “Events (events.fru.dev)” for reused data and avoid bulk refreshes of upstream-overlapping records.

## Evidence

[API list example](https://events.fru.dev/api/conferences?topic=AI&limit=3) · [machine guide and counters](https://events.fru.dev/llms.txt) · [robots](https://events.fru.dev/robots.txt)
