# cfp.fru.dev

- **Status:** Later pilot / cross-check
- **Official/source URL(s):** [cfp.fru.dev](https://cfp.fru.dev/), [agent guide](https://cfp.fru.dev/agents), [method](https://cfp.fru.dev/method)
- **Interface:** `GET /api/cfps`, `GET /api/cfps/{id}`, `GET /api/changes?since=<date-time>&limit=<1..500>`, `/openapi.json`
- **Verification:** 2026-11-11

## Data and access

The keyless JSON list supports `status=open|closed|all`, topic/format/travel/search filters, `limit` up to 200 and `offset`. Records include dates, location, topics, support, `unverified`, `lastChecked`, provenance and history. Data is **CC BY 4.0**, requiring attribution and a link to cfp.fru.dev. Responses have a documented one-hour edge cache; refresh cadence is weekly.

**2026-11-11 snapshot:** 39 open and 40 closed calls; 34/39 open CFP URLs already matched the three-source baseline. A changes query since 1 November returned 34 additions, corrections and closures.

## Caveats

`robots.txt` says `Disallow: /api/`, while `/agents`, OpenAPI and `llms.txt` explicitly instruct agents to call those GET endpoints. This is a contradictory access signal, not an HTTP failure; obtain operator confirmation before unattended scheduling.

Use **`cfpUrl` as the submission URL and `conferenceSite` as the event URL**. `sourceUrl` is reviewable provenance only; a Conf42 row retained a dead Papercall source. `eventsPage` is not canonical either and has pointed to the wrong event. Change timestamps appear timezone-naive despite UTC documentation, and no changes offset is documented.

## Integration guidance

Keep below established feeds as a discrepancy/history cross-check, not a discovery-scale source. After clarification, poll changes conservatively, checkpoint timestamp plus record ID, surface verification flags, and attribute the source.

## Evidence

[Open calls](https://cfp.fru.dev/api/cfps?status=open&limit=100) · [changes API](https://cfp.fru.dev/api/changes?since=2026-11-01T00:00:00Z&limit=500) · [robots conflict](https://cfp.fru.dev/robots.txt)
