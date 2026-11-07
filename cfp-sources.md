# Other CFP / conference sources

Use when the user asks "where else can I find upcoming conferences", when coverage
looks thin, or when a CFP note's link needs cross-checking. Everything here was verified
at the HTTP level (2026-11-02); re-verify statuses before promising anything.

## Machine-readable (scriptable)

| Source | Shape | Notes |
|---|---|---|
| developers.events | `all-cfps.json` + `all-events.json` | Primary. ~4k CFP records. Record `link` = CFP URL, `conf.hyperlink` = event site, `untilDate` = epoch ms. |
| **cfp.ninja** | `api/v0/events?per_page=100&page=N` | **Used.** Open-source CFP platform (`github.com/sreday/cfp.ninja`), public API, no auth. ~100 events, real `cfp_open_at`/`cfp_close_at` (ISO), `start_date`/`end_date`, `location`/`country`, comma-separated `tags`, and speaker benefits (`travel_covered`/`hotel_covered`/`honorarium_provided`). Submission page `cfp.ninja/e/<slug>`. **Trap:** `cfp_status` reports `open` for years-old rows — filter on `cfp_close_at`, never the status. Skews to a few recurring series (Conf42, SREday/LLMday/PLATFORMday). |
| confs.tech, data in `github.com/tech-conferences/conference-data` | `conferences/<year>/<topic>.json`, MIT, community PRs | Best second source: `name, url, startDate, endDate, city, country, cfpUrl, cfpEndDate` — real dates, not strings. Roughly half the entries carry `cfpEndDate`. **There is no `ai` topic file** — AI events live under `general` or a language topic, so an AI-focused sweep has to read many files. Actively committed. |
| **adato-tracker** | HTML: the `tablesorter` table on `adatosystems.com/cfp-tracker/` | **Used.** Leon Adato's evergreen tracker page: one 8-column table (Event Name, City, State, Event Start/End, CFP Close, Event URL, CFP URL) with clean ISO `YYYY-MM-DD` dates. No topics or benefits. It aggregates the same feeds (developers.events, Sessionize, …), so it ranks lowest and only fills gaps. Scrape the table, not the RSS: the dated "Call For Papers Listings for …" posts are stubs and the feeds carry just the excerpt. |
| cfp.fru.dev | `api/cfps?status=open` | CFP-only aggregator, OpenAPI 3.1, CC BY 4.0, refreshed weekly. Small (~34 open + history). Its own sources are confs.tech + **cfp.ninja + Sessionize + organizer call pages**, so it is a useful **cross-check** (it surfaces Sessionize-hosted CFPs) rather than a primary. Needs CC BY attribution. |
| events.fru.dev | `api/conferences` | Conference side only (no deadline), OpenAPI 3.1, CC BY 4.0, ~389 upcoming read from ~1,400 sources with host company + topics. Could enrich event dates/location for CFPs found elsewhere. |

The first four feed the per-CFP notes in `data/`: dedupe on normalized name + overlapping dates,
and record each note's origin in `source` so disagreements are traceable. When two sources own the
same slug, `manual` > `developers.events` > `cfp.ninja` > `confs.tech` > `adato-tracker`.

## Machine-readable, but no CFP deadline

| Source | Endpoint | Notes |
|---|---|---|
| pretalx.com | `api/events/` | Public, ~750 events — but the API carries **no CFP deadline**; that lives only on each event's `/cfp` page (visible text, no JSON-LD). Most conferences run their own pretalx instance, so `pretalx.com` sees only a fraction. Low yield for a CFP sweep. |
| dev.events | `rss.xml` | RSS of the 100 latest events (categories + date/location in the description) plus an HTML index. Events only, thin on CFP deadlines. Good for "what conferences exist". |
| gdg.community.dev | `api/event/?page=N` | Public JSON, ~72k events at 500/page (~144 pages), no CFP info. Only useful to catch GDG DevFests (which do open CFPs); heavy to enumerate. |
| lu.ma, Meetup | — | APIs exist but need a key / are rate-limited; not worth it for this watchlist. |

## Sessionize — a link target, not a discovery source

- No public directory and no feed: `/events`, `/events-directory`, `/discover`,
  `/browse`, `/cfp`, `/open-calls`, `/calls`, `/all-events` all 404.
- **Trap:** `/events` returns 200 but renders a *speaker's profile* — the bare
  `<slug>` space is shared, so a bogus path can look like a working page. Confirm the
  page `<title>` says "Call for Speakers" rather than trusting the status code.
- The walled area is only `/app/` and `/submission/helper/` (what its robots.txt
  disallows) — CFP pages themselves are public.
- Enumeration does exist: `/sitemap/events.xml` lists ~11k event URLs, but with no
  `lastmod` and no status, so ranking them means fetching every page.
- An event page carries its deadline only as visible text ("Call closes at 11:59 PM
  25 Nov 2026" plus a timezone note) — no JSON-LD, no meta tag. So read the deadline
  from the aggregator and use Sessionize purely as the submission link.

## Where CFPs are hosted (watch directly for early notice)

Sessionize; pretalx (`pretalx.com` plus per-conference instances); conference-hall.io
(the FR/EU community scene; its API needs a key); cfp.ninja; GitNation events; Linux
Foundation / CNCF events; devopsdays.org; the python.org events calendar; GDG DevFests via
`gdg.community.dev` and `app.advocu.com`; lu.ma; Meetup.

## Rot

- **papercall.io is dead** (shut down, site offline). Notes still pointing there need
  the `event_url` link instead — several appear in the source data regardless.
- **CFP Land is dead too.** `cfpland.com` is a parked "domain for sale" page and
  `api.cfpland.com` no longer connects (its `/v0/conferences` API docs are stale).
- Other checks that came back empty: **cfp.events** (a WordPress starter site with the
  default "Gutenberg Sample Post"), **cfp.dev** (301s to devoxx.com — Devoxx only),
  **10times** (Cloudflare 403), and **callforpapers.info / calls.dev / eventil.com**
  (no DNS).
- Sweep a report's links with `src/check-links.py` (e.g. `tmp/cfps.md`) before telling the
  user the list is actionable. Treat 403/429 as "blocked, unknown", not as dead.
