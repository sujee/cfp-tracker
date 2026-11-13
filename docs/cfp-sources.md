# CFP sources

Source notes verified 2026-11-11 unless a detail page says otherwise. Each source name links to detailed notes.

## Implemented

| Source | Input | Notes |
|---|---|---|
| [developers.events](sources/developers-events.md) | `all-cfps.json`, `all-events.json` | Primary; filter `untilDate`, not `conf.status`. |
| [cfp.ninja](sources/cfp-ninja.md) | `api/v0/events` | Public API; filter `cfp_close_at`; includes benefits. |
| [PythonDeadlin.es](sources/pythondeadlines.md) | `_data/conferences.yml` | Python speaking CFPs; MIT; require `cfp_link`. |
| [confs.tech](sources/confs-tech.md) | `conferences/<year>/<topic>.json` | MIT; `cfpUrl` + `cfpEndDate`; no `ai` topic file. |
| [adato-tracker](sources/adato-tracker.md) | HTML table | Aggregator; use the table, not RSS. |
| [Open Tech CFPs](sources/open-tech-cfps.md) | `api/open.json`, `api/closed.json` | CC BY 4.0; Sessionize-derived; filter `cfp_close_utc`; lowest priority. |
| [Manual](sources/manual.md) | Files named in `MANUAL_INPUT_FILES` | Tables and website checklists; highest priority. |

Among rows in the current run, priority is `manual` > `developers.events` > `cfp.ninja` >
`confs.tech` > `adato-tracker` > `open-tech-cfps`.
Disabled or unavailable sources retain their unmodified notes. A successful higher-priority
current replacement can supersede a lower-priority paused note after curation migration.
See `sources.py` for the canonical registry.

## Other sources

### Recommended next additions

| Source | Input | Notes |
|---|---|---|
| [TechConf Spain](sources/techconf-spain.md) | `events[]` JSON | Spain; structured dates/locations; CC BY 4.0. |
| [AgentConfs](sources/agentconfs.md) | `data/events.json` | AI; CC BY 4.0; filter out academic-paper CFPs. |
| [devopsdays](sources/devopsdays.md) | `data/events/<year>/<city>/main.yml` | Official series data; Apache 2.0; cache repository discovery. |

### Specialist feeds / later pilots

| Source | Input | Notes |
|---|---|---|
| [cfp.fru.dev](sources/cfp-fru-dev.md) | `/api/cfps`, `/api/changes` | History/cross-check; CC BY 4.0; high overlap; robots/API conflict. |
| [CFP Directory](sources/cfp-directory.md) | `/api/events` | Small but structured; undocumented endpoint; no explicit data license. |
| [JavaConferences](sources/javaconferences.md) | `conferences.json` | Java; CC0; human date strings; validate generated JSON. |
| [Conference Hall](sources/conference-hall.md) | Public search/event HTML | Small FR/EU source; brittle extraction; no global discovery API. |
| [CFPTime](sources/cfptime.md) | `/api/cfps/` | Security; validate URLs/countries; no explicit data license. |
| [Open CFPs](sources/open-cfps.md) | `data/cfps.json` | Broad developer topics; filter stale rows; no explicit data license. |
| [CFPlease](sources/cfplease.md) | `/api/v1/cfps` | Noisy; many missing CFP URLs; no explicit data license. |
| [PostgreSQL Event Calendar](sources/postgresql-event-calendar.md) | ICS files | Small; join CFP and event calendars; no explicit data license. |
| [foss.events](sources/foss-events.md) | Event HTML | Small FOSS source; ODbL/CC BY-SA obligations. |

### Enrichment or manual checks

| Source | Input | Notes |
|---|---|---|
| [Sessionize](sources/sessionize.md) | Event pages, sitemap | Submission-link target; no global feed; sitemap lacks status/`lastmod`. |
| [pretalx](sources/pretalx.md) | Per-event `/cfp` pages | Global event API has no deadlines; self-hosted instances vary. |
| [events.fru.dev](sources/events-fru-dev.md) | `/api/conferences` | Event enrichment only; no CFP deadlines; CC BY 4.0. |
| [dev.events](sources/dev-events.md), [GDG](sources/gdg-community-dev.md) | RSS/JSON | Event discovery only; no systematic CFP deadlines. |
| [LF/CNCF](sources/linux-foundation-cncf.md), [BSides](sources/bsides.md), [RubyEvents](sources/rubyevents.md) | HTML | Manual cross-checks; no normalized CFP feed. |
| [ai-deadlines](sources/ai-deadlines.md), [ccf-deadlines](sources/ccf-deadlines.md), [OpenReview](sources/openreview.md) | YAML/API | Academic paper deadlines; keep separate from speaking CFPs. |
| [lu.ma](sources/luma.md), [Meetup](sources/meetup.md) | APIs | Auth/rate limits; low yield for this tracker. |

### Blocked, stale, or dead

| Source | Reason |
|---|---|
| [CallingAllPapers](sources/callingallpapers.md) | Live API, but API robots rules disallow all agents. |
| [CFP Radar](sources/cfp-radar.md) | Incomplete/stale feed; robots disallow `/api/`. |
| [SpeakingGig AI](sources/speakinggig-ai.md), [submitcfp](sources/submitcfp.md) | Registration wall; zero open events plus scraping prohibition. |
| [PaperCall](sources/papercall.md), [CFP Land](sources/cfp-land.md) | Dead. |
| [cfp.events](sources/cfp-events.md), [cfp.dev](sources/cfp-dev.md), [callforpapers.info](sources/callforpapers-info.md), [calls.dev](sources/calls-dev.md), [eventil.com](sources/eventil-com.md) | Empty, redirected, or DNS failure. |

Treat `403`/`429` as blocked, not dead. Check links with `python3 src/check-links.py <report.md>`.
