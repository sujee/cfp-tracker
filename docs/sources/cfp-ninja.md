# cfp.ninja

- Status: Implemented
- Official/source URL(s): [cfp.ninja](https://cfp.ninja/), [open-source repository](https://github.com/sreday/cfp.ninja)
- Interface: [`GET /api/v0/events?per_page=100&page=N`](https://cfp.ninja/api/v0/events?per_page=100&page=1), submission pages `/e/<slug>`; adapter [`src/process-cfp-ninja.py`](../../src/process-cfp-ninja.py)
- Verification: 2026-11-11

## Data and access

The paginated public API requires no authentication. Records include `name`, `website`, `slug`, `start_date`, `cfp_open_at`/`cfp_close_at`, `location`, `country`, `is_online`, comma-separated `tags`, and speaker-benefit flags. Readable page caches under `cache/cfp-ninja-events-<N>.json` are preferred indefinitely; invalid caches are refetched.

## Caveats

Ignore `cfp_status`: even years-old rows may be marked `open`. Filter on `cfp_close_at`. The adapter takes its leading ISO date rather than calculating a timezone-normalized instant. Upstream country values mix abbreviations and names and are often empty for online events. Recurring series such as Conf42 and SREday/LLMday/PLATFORMday are expected, not proof of an API duplication fault. An available `cfp_open_at` is not emitted because the tracker has no CFP-opening property.

## Integration guidance

Include close dates on/after the inclusive cutoff (standalone default: 30 days back), require a name, and dedupe by normalized name plus close date. Map `website` to `event_url` and construct `cfp_url` as `https://cfp.ninja/e/<slug>` when a slug exists. Split and trim `tags`; lowercase language canonicalization does not apply because this source supplies no languages. True `travel_covered`, `hotel_covered`, and `honorarium_provided` flags map respectively to `travel`, `hotel`, and `honorarium`. An online event gets `country: Online` only when upstream country is empty. The writer canonicalizes mixed country aliases and merges topics cumulatively. Priority is below developers.events and above confs.tech.

## Evidence

- [API first page](https://cfp.ninja/api/v0/events?per_page=100&page=1) — records and pagination.
- [Project repository](https://github.com/sreday/cfp.ninja) — platform implementation.
