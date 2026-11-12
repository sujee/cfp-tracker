# Sessionize

- **Status:** Enrichment/link target, not primary discovery
- **Official/source URL(s):** [sessionize.com](https://sessionize.com/), [official API guide](https://sessionize.com/playbook/api)
- **Interface:** Known public `/{event-slug}/` CFP pages; organizer-specific `/api/v2/{endpointId}/...`; `/sitemap/events.xml`
- **Verification:** 2026-11-11

## Data and access

A known event page can supply event date, location, website, opening/closing datetimes and closing timezone. The official API uses an organizer-created endpoint ID per event and exposes read-only schedule data—sessions, speakers, rooms and relationships—with caching up to five minutes. It is neither a cross-event CFP index nor a deadline API.

**2026-11-11 snapshot:** `/sitemap/events.xml` contained 11,098 event URLs (about 1.25 MB) and no per-URL `lastmod`. Its response-level `Last-Modified` can invalidate the whole file but cannot identify changed or open calls.

## Caveats

`GET /events` returned HTTP **200 with the misleading title `Alberto P. Martí's Speaker Profile @ Sessionize`**. Thus status 200 is not validation; a deliberately nonexistent slug returned a genuine 404. Require the expected event name plus “Call for Papers” or “Call for Speakers” in title/body. The tested CFP page contained no JSON-LD. Sitemap order has no established stable meaning, and a full pass would require thousands of page fetches. Robots permits public CFP/sitemap paths but does not grant a bulk-reuse license.

## Integration guidance

Use known links from aggregators for targeted verification and submission targets. Validate title/event identity before extracting dates and timezone. Optionally conditional-fetch the sitemap as an inventory signal, but never routinely enumerate it; Open Tech CFPs and existing feeds already surface much of this overlap at far lower operational cost.

## Evidence

[Misleading `/events` response](https://sessionize.com/events) · [event sitemap](https://sessionize.com/sitemap/events.xml) · [sample CFP page](https://sessionize.com/aws-student-community-day-salvador/) · [robots](https://sessionize.com/robots.txt)
