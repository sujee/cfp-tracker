# CFP sources

Source notes verified 2026-11-11 unless a detail page says otherwise. Each source name links to detailed notes.

## Implemented

| Source | Input | Notes |
|---|---|---|
| [developers.events](developers-events.md) | `all-cfps.json`, `all-events.json` | Primary; filter `untilDate`, not `conf.status`. |
| [cfp.ninja](cfp-ninja.md) | `api/v0/events` | Public API; filter `cfp_close_at`; includes benefits. |
| [PythonDeadlin.es](pythondeadlines.md) | `_data/conferences.yml` | Python speaking CFPs; MIT; require `cfp_link`. |
| [AgentConfs](agentconfs.md) | `data/events.json` | Structured robotics listing; speaking calls only. Academic records and Robot Framework are excluded. |
| [confs.tech](confs-tech.md) | `conferences/<year>/<topic>.json` | MIT; `cfpUrl` + `cfpEndDate`; no `ai` topic file. |
| [adato-tracker](adato-tracker.md) | HTML table | Aggregator; use the table, not RSS. |
| [Open Tech CFPs](open-tech-cfps.md) | `api/open.json`, `api/closed.json` | CC BY 4.0; Sessionize-derived; filter `cfp_close_utc`; fills gaps below adato-tracker. |
| [Manual](manual.md) | Every file under `input/`, except `input/archived/` | Tables and website checklists; highest priority. |

Among rows in the current run, priority is `manual` > `developers.events` > `cfp.ninja` >
`python-deadlines` > `agentconfs` > `confs.tech` > `adato-tracker` > `open-tech-cfps` >
`realtime-embedded-conferences` > `ieee-ras` > `ccf-deadlines`.
Disabled or unavailable sources retain their unmodified notes. A successful higher-priority
current row can take ownership from a lower-priority paused note after curation migration.
See `sources.py` for the canonical registry.

## Independent academic listings

These sources have independent adapters but stay outside the default `INPUT_SOURCES` list.
Enable them explicitly when academic paper rounds belong in the product. All four listing sources
add standardized `robotics` and `physical.ai` topics and normalize equivalent spellings.

| Source | Input | Notes |
|---|---|---|
| [Real-Time, Embedded, CPS & Robotics](realtime-embedded-conferences.md) | Public listing JSON | Select current `Robotics & Learning` records with day precision. Exclude predicted dates. |
| [IEEE RAS](ieee-ras.md) | Official deadline iCalendar | Parse each deadline `VEVENT`. Do not infer event dates or venues from deadline pages. |
| [CCF Deadlines](ccf-deadlines.md) | `allconf.json` | Keep abstract, submission, rebuttal, and decision rounds separate. Ignore derived opening timestamps. |

## Other sources

### Recommended next additions

| Source | Input | Notes |
|---|---|---|
| [TechConf Spain](techconf-spain.md) | `events[]` JSON | Spain; structured dates/locations; CC BY 4.0. |
| [devopsdays](devopsdays.md) | `data/events/<year>/<city>/main.yml` | Official series data; Apache 2.0; cache repository discovery. |

### Specialist feeds / later pilots

| Source | Input | Notes |
|---|---|---|
| [cfp.fru.dev](cfp-fru-dev.md) | `/api/cfps`, `/api/changes` | History/cross-check; CC BY 4.0; high overlap; robots/API conflict. |
| [CFP Directory](cfp-directory.md) | `/api/events` | Small but structured; undocumented endpoint; no explicit data license. |
| [JavaConferences](javaconferences.md) | `conferences.json` | Java; CC0; human date strings; validate generated JSON. |
| [Conference Hall](conference-hall.md) | Public search/event HTML | Small FR/EU source; brittle extraction; no global discovery API. |
| [CFPTime](cfptime.md) | `/api/cfps/` | Security; validate URLs/countries; no explicit data license. |
| [Open CFPs](open-cfps.md) | `data/cfps.json` | Broad developer topics; filter stale rows; no explicit data license. |
| [CFPlease](cfplease.md) | `/api/v1/cfps` | Noisy; many missing CFP URLs; no explicit data license. |
| [PostgreSQL Event Calendar](postgresql-event-calendar.md) | ICS files | Small; join CFP and event calendars; no explicit data license. |
| [foss.events](foss-events.md) | Event HTML | Small FOSS source; ODbL/CC BY-SA obligations. |

### Enrichment or manual checks

| Source | Input | Notes |
|---|---|---|
| [Sessionize](sessionize.md) | Event pages, sitemap | Submission-link target; no global feed; sitemap lacks status/`lastmod`. |
| [pretalx](pretalx.md) | Per-event `/cfp` pages | Global event API has no deadlines; self-hosted instances vary. |
| [events.fru.dev](events-fru-dev.md) | `/api/conferences` | Event enrichment only; no CFP deadlines; CC BY 4.0. |
| [dev.events](dev-events.md), [GDG](gdg-community-dev.md) | RSS/JSON | Event discovery only; no systematic CFP deadlines. |
| [LF/CNCF](linux-foundation-cncf.md), [BSides](bsides.md), [RubyEvents](rubyevents.md) | HTML | Manual cross-checks; no normalized CFP feed. |
| [ai-deadlines](ai-deadlines.md), [OpenReview](openreview.md) | YAML/API | Other academic deadline sources. Keep separate from speaking CFPs. |
| [lu.ma](luma.md), [Meetup](meetup.md) | APIs | Auth/rate limits; low yield for this tracker. |

### Blocked, stale, or dead

| Source | Reason |
|---|---|
| [CallingAllPapers](callingallpapers.md) | Live API, but API robots rules disallow all agents. |
| [CFP Radar](cfp-radar.md) | Incomplete/stale feed; robots disallow `/api/`. |
| [SpeakingGig AI](speakinggig-ai.md), [submitcfp](submitcfp.md) | Registration wall; zero open events plus scraping prohibition. |
| [PaperCall](papercall.md), [CFP Land](cfp-land.md) | Dead. |
| [cfp.events](cfp-events.md), [cfp.dev](cfp-dev.md), [callforpapers.info](callforpapers-info.md), [calls.dev](calls-dev.md), [eventil.com](eventil-com.md) | Empty, redirected, or DNS failure. |

Treat `403`/`429` as blocked, not dead. Check links with `python3 src/check-links.py <report.md>`.
