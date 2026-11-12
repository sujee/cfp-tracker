# Conference Hall

- **Status:** Manual or guarded pilot
- **Official/source URL(s):** [conference-hall.io](https://conference-hall.io/), [conference filter](https://conference-hall.io/?type=conference), [source code](https://github.com/conference-hall/conference-hall)
- **Interface:** Public search/event HTML with React Router/devalue loader data; `/sitemap.xml`
- **Verification:** 2026-11-11

## Data and access

The “Incoming call for papers” search exposes pagination and `slug`, `name`, `type`, `location`, `cfpState`, `timezone`, `cfpStart` and `cfpEnd`. Selected public event pages add conference dates, `websiteUrl`, formats and categories; dates in the internal stream can be encoded as `['D', epochMilliseconds]`.

**2026-11-11 snapshot:** the conference-only filter returned six events on one page. The sitemap returned 115 event URLs with `changefreq: weekly` and no `lastmod`. At that scale, discovery costs one index request plus at most six selected detail requests.

## Caveats

There is no documented global discovery JSON API. The keyed `GET /api/v1/event/{slug}` and `/schedule` interfaces are organizer-facing proposal/schedule exports using `X-API-Key`; **they are not discovery APIs**. Robots disallows `/api/` while allowing public pages. Sitemap/search meetup selection can require only non-null `cfpStart`, so 115 is not an open-CFP count. Loader serialization is internal and brittle, and no explicit bulk-data license or public-search quota was found.

## Integration guidance

Prefer manual monitoring unless the small French/European incremental yield justifies an adapter. Poll only `/?type=conference`, require a current `cfpEnd`, and fetch selected event pages for missing fields. Use a real devalue parser with deployment-change fixtures; do not scrape display whitespace, crawl the full sitemap or call the keyed API for enumeration.

## Evidence

[Public search implementation](https://github.com/conference-hall/conference-hall/blob/main/app/features/event-search/services/event-search.server.ts) · [sample event](https://conference-hall.io/ng-baguette-conf-2027) · [sitemap](https://conference-hall.io/sitemap.xml) · [robots](https://conference-hall.io/robots.txt)
