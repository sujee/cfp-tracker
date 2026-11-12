# CFPlease

- **Status:** Discovery only pending license/relevance filters
- **Official/source URL(s):** [cfplease.io](https://cfplease.io/), [API documentation](https://cfplease.io/api/v1/docs), [about](https://cfplease.io/about)
- **Interface:** Anonymous `GET /api/v1/cfps`, `/api/v1/openapi.json`, `/api/v1/facets`, `/api/v1/counts`
- **Verification:** 2026-11-11

## Data and access

The public JSON API (OpenAPI version 1.4.1) provides conference/event dates, free-text location and region, nullable CFP/event URLs, open/close dates, submission formats, description, tags, active state and revision timestamps. Filters include query, tags, region, location type, format and dates; there is no `since` delta interface.

**2026-11-11 snapshot:** 263 rows over six pages at a server-enforced page size of 50. Of 109 date-current rows, 43 lacked `cfp_url`, 15 lacked event start and 13 lacked location; 107 matched neither baseline URL nor exact name, but were not import-ready conferences.

## Caveats

Coverage includes developer talks, academic papers, journals and unrelated disciplines, with social links, WikiCFP and URL shorteners. There is no clean country field. No explicit bulk-data license, `/terms` page or numeric anonymous rate limit was found; `/robots.txt` returned an application-style 404. Responses support 304 and can return **429, meaning throttled/blocked—not dead**. Do not confuse this service with the unavailable `PLNech/cfp-please` repository.

## Integration guidance

Keep as a discovery pool until reuse/rate guidance and relevance rules exist. Follow `total_pages`, not requested `page_size`; retain ETags/local snapshots and back off on 429. Any later pilot must require current `cfp_close_date` and actionable `cfp_url`, resolve redirects for review, exclude journals/general academia/non-software subjects, and validate the actual submission destination before creating notes.

## Evidence

[CFP API](https://cfplease.io/api/v1/cfps) · [OpenAPI definition](https://cfplease.io/api/v1/openapi.json) · [health endpoint](https://cfplease.io/api/v1/health)
