# Open Tech CFPs

- Status: Implemented
- Official/source URL(s): [Open Tech CFPs](https://1kevgriff.github.io/OpenTechCFPs/), [project repository](https://github.com/1kevgriff/OpenTechCFPs)
- Interface: [`api/open.json`](https://1kevgriff.github.io/OpenTechCFPs/api/open.json) and [`api/closed.json`](https://1kevgriff.github.io/OpenTechCFPs/api/closed.json); adapter [`src/process-open-tech-cfps.py`](../../src/process-open-tech-cfps.py)
- Verification: 2026-11-11

## Data and access

This keyless static, Sessionize-derived dataset supplies `name`, submission `url`, event `website`, `event_start`, exact `cfp_close_utc`, `location`, ISO alpha-2 `country`, `online`, inferred `tags`, `perks`, `id`, and `updated`. Both documents must contain a `cfps` list. Live fetches refresh the shared cache. A failed fetch uses valid cached JSON. `--offline` requires cached responses. The project states a three-hour rebuild cadence; the dated snapshot contained 556 open records generated at `2026-11-11T21:38:27Z`, not a stable coverage total.

Data is **CC BY 4.0** (code is separately MIT). Required attribution: **Open Tech CFPs, https://github.com/1kevgriff/OpenTechCFPs**, with a link to [LICENSE-DATA](https://github.com/1kevgriff/OpenTechCFPs/blob/main/LICENSE-DATA).

## Caveats

Never trust computed `status`; parse offset-aware `cfp_close_utc`, normalize to UTC, and compare with inclusive midnight on the cutoff date. Reject missing, invalid, or timezone-naive deadlines. Tags are keyword-inferred upstream, not native Sessionize topics; exclude `untagged`. The project is young and has one upstream, so monitor `generated_at`. `perks.fee: free for speakers` is admission, **not an honorarium**.

## Integration guidance

Require name and actionable `url`. Sort records by `updated` descending; newest wins duplicate IDs/submission URLs and then normalized-name plus UTC-close-date collisions. Map `website`→`event_url`, `url`→`cfp_url`, strict ISO `event_start` or `TBA`, and non-sentinel tags. Resolve alpha-2 country through `pycountry`; `online: true` becomes `Online`. Only `perks.travel`/`perks.accommodation == expenses covered` (case-insensitive) map to `travel`/`hotel`. Ignore filtering covers name and tags. This lowest-priority feed fills gaps; normal writer URL matching still requires compatible names.

## Evidence

- [Schema](https://1kevgriff.github.io/OpenTechCFPs/schema.json) — upstream fields.
- [Method and endpoint guide](https://1kevgriff.github.io/OpenTechCFPs/llms.txt) — cadence, status and tag caveats.
- [Data license](https://github.com/1kevgriff/OpenTechCFPs/blob/main/LICENSE-DATA) — CC BY 4.0 and attribution.
