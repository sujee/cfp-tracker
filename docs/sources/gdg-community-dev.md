# GDG community.dev / DevFest / Advocu

- **Status:** Event discovery/manual
- **Official/source URL(s):** [GDG](https://gdg.community.dev/), [upcoming events](https://gdg.community.dev/events/), [DevFest directory](https://developers.google.com/community/devfest)
- **Interface:** Public chapter/event HTML (`/events/details/...`, `/e/{code}/`) and DevFest cards; organizer-specific external CFP pages
- **Verification:** 2026-11-11

## Data and access

GDG and DevFest directory entries are useful for chapter, event name, date, attendance style and location, with links to locally controlled sites or submission platforms. Google’s **2026-11-11 research snapshot** described the 2026 DevFest season as more than 800 locally curated events across 115 countries. That scale is decentralized event coverage, not a corresponding inventory of open calls.

DevFest Berlin illustrated the required evidence chain: its organizer-specific FAQ carried a 2026-11-01 CFP close and linked Sessionize, while a central GDG directory entry supplied no equivalent deadline.

## Caveats

There is no systematic CFP close field in the central event directories. Chapters variously use Advocu (`app.advocu.com/events/{id}` or public GDE URLs), Sessionize and their own forms. Research found **no verified authoritative Advocu-wide public CFP catalog/API**; organizer links do not establish one, and undocumented scraping must not be substituted. Shared DevFest branding and recurring names create edition-identity risk, while deadlines differ by chapter. Public pages are not an explicit bulk-data license.

## Integration guidance

Use GDG/DevFest for event discovery and joining an existing CFP to its official chapter/edition. Follow the actual organizer CFP link, validate city/year and extract the close from that page or an already-supported feed. Treat Advocu as an organizer-specific link target only; do not infer a global endpoint or create notes without a verified deadline and actionable submission URL.

## Evidence

[DevFest 2026 announcement](https://blog.google/innovation-and-ai/technology/developers-tools/devfest2026) · [DevFest Berlin example](https://2026.devfest-berlin.de/) · [GDG event directory](https://gdg.community.dev/events/#/list)
