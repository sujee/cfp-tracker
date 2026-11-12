# submitcfp
- Status: Rejected
- Official/source URL: https://submitcfp.com/discover
- Verification: 2026-11-11

## Finding
The landing page advertises multi-event CFP hosting, but anonymous `/discover` rendered `Showing 0 of 0 open events`. Its sitemap contained 165 locations, yet inspected `/cfp/...` paths were taxonomy pages such as `/cfp/topic/ai`, not event or submission records. Access rules independently prevent routine extraction: robots allows `/discover` but disallows `/api/`, while Terms §6 expressly prohibits scraping, reselling, or misusing the service. Marketing claims do not establish usable coverage.

## Tracker guidance
Do not add a scraper, probe the disallowed API, or mistake sitemap taxonomy URLs for events. Revisit only by manual review when the public directory contains real events and an official export, API, or explicit permission supports automated use. Even then, verify each event's deadline and direct CFP URL. Zero rows was a dated observation, not proof that the platform remains empty.

## Evidence
- [Discovery page](https://submitcfp.com/discover)
- [Sitemap](https://submitcfp.com/sitemap.xml)
- [Terms, including §6](https://submitcfp.com/terms)
- [Robots rules](https://submitcfp.com/robots.txt)
