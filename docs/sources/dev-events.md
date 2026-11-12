# dev.events

- **Status:** Event discovery/manual
- **Official/source URL(s):** [dev.events](https://dev.events/), [FAQ/method](https://dev.events/about)
- **Interface:** `https://dev.events/rss.xml`, public `/conferences/{slug}` pages and `/ical/{slug}` downloads
- **Verification:** 2026-11-11

## Data and access

The public RSS feed contains title, stable GUID, dev.events link, publication date, prose event date/location and category values for topic and event type. The FAQ documents repeatable category filters, for example `/rss.xml?category=masterclass&category=hackathon&category=conference`, and says the feed contains **100 recently added events** (a feed-size description, not a CFP count). HTML adds broader browsing by place/topic and outbound organizer links. Organizers, contributors, manual checks and monitoring all feed the directory.

## Caveats

The FAQ explicitly says dev.events does **not store CFP information**, citing inconsistent publication and application mechanisms. Publication timestamps are not closing dates; RSS descriptions are prose rather than a normalized event schema. Sponsored/masterclass and mixed meetup content require type/relevance filtering, and directory popularity or promoted placement is not speaking-CFP evidence. Its JSON-LD discussion describes markup dev.events monitors on organizer sites, not a public global CFP JSON export. The RSS declares “All rights reserved”; no open-data reuse license was established.

## Integration guidance

Use low-frequency RSS or manual browsing only to discover event identities and fill missing event date/location/site leads. Follow the organizer page, then find and independently validate an actionable CFP URL and close date before creating or enriching a speaking note. Deduplicate against broad existing feeds and do not republish the directory wholesale or infer deadlines from `pubDate`.

## Evidence

[RSS feed](https://dev.events/rss.xml) · [filtered-feed example](https://dev.events/rss.xml?category=conference) · [CFP policy in FAQ](https://dev.events/about)
