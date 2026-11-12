# PaperCall
- Status: Dead
- Official/source URL: https://www.papercall.io/
- Verification: 2026-11-11

## Finding
The live check of `www.papercall.io` failed during DNS resolution (`nodename nor servname provided, or not known`). It did not return HTTP 403 or 429, so this was an observed DNS/connection failure rather than a rate or access block. This rejects new integration without proving a universal or permanent shutdown. An old aggregator row still referenced PaperCall, demonstrating that stale links can survive elsewhere.

## Tracker guidance
Do not create a PaperCall source or assume legacy `cfp_url` values still work. For old-note remediation, follow the note's `event_url` to the official conference site and locate a current organizer-controlled CFP; replace or archive dead opportunities rather than repeatedly retrying PaperCall. Revisit only if DNS is restored and actual event pages, deadlines, and automation terms are verified.

## Evidence
- [URL whose DNS lookup failed](https://www.papercall.io/)
- Live hosting-platform verification dated 2026-11-11.
