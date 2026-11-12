# Linux Foundation / CNCF Events

- **Status:** Manual/deadline enrichment
- **Official/source URL(s):** [LF event calendar](https://events.linuxfoundation.org/about/calendar/), [cloud-native calendar](https://events.linuxfoundation.org/calendar/cloud-native-devops-conferences/)
- **Interface:** Public HTML plus embedded Schema.org `ItemList`/`Event` JSON-LD; actual event-specific Speak/CFP links
- **Verification:** 2026-11-11

## Data and access

Calendar JSON-LD supplies event URL, ISO start/end, attendance mode, status, location/address and description, but **no normalized CFP deadline or submission URL**. Rendered entries separately expose `Closes`, `Closed`, `Details Coming Soon` or `No Call for Proposals`. Valid event CFP pages can add close datetime/timezone, topics and a direct submission link.

**2026-11-11 snapshot:** the main calendar listed 54 events, four with `Closes`: NeoCloudCon Europe (2026-11-30), Open Source Forum (2026-12-06), HPSF Conference (2027-01-17), and AGNTCon + MCPCon North America (2027-01-18). The cloud-native page advertised 122 events (24 LF, 98 community/industry), most without structured CFP deadlines.

## Caveats

**Never guess or synthesize `/program/cfp/` URLs.** Tested ASWF Open Source Forum and NeoCloudCon paths resolved to an archived 2020 KubeCon + CloudNativeCon North America CFP, not the named future events. CNCF/KCD/co-located pages do not share one complete metadata pattern. Community entries overlap devopsdays and existing aggregators, and no explicit open-data license was found on the checked calendar outputs.

## Integration guidance

Manually process only entries saying `CFP Status: Closes …`; follow the current event page’s real Speak/CFP hyperlink and validate title, event and year before ingestion. Use JSON-LD to enrich an existing note’s event fields, not to invent a deadline. Treat other statuses as non-actionable and avoid crawling all 54/122 events every refresh.

## Evidence

[HPSF CFP example](https://events.linuxfoundation.org/hpsf-conference/program/cfp/) · [ASWF wrong-archive example](https://events.linuxfoundation.org/aswf-open-source-forum/program/cfp/) · [NeoCloudCon wrong-archive example](https://events.linuxfoundation.org/kubecon-cloudnativecon-europe/co-located-events/neocloudcon/program/cfp/)
