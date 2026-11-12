# CallingAllPapers
- Status: Blocked
- Official/source URL: https://callingallpapers.com/
- Verification: 2026-11-11

## Finding
The live API returned HTTP 200 JSON with a `cfps` array and newly timestamped records. Fields include CFP opening and exact closing dates, event dates, submission and event URLs, location, timezone, tags, sources, and `lastChange`. The homepage describes daily collection from joind.in, confs.tech, PaperCall, and Sessionize. This is useful live data, not evidence of a stale service. The separate blocker is permission: the API's `robots.txt` returned `User-agent: *` and `Disallow: /`. A successful public response does not override that exclusion.

## Tracker guidance
Do not schedule API ingestion or bypass the robots rule. Revisit only after the operator explicitly permits the tracker's automated use; retain any scope or rate limits given. If authorized, use `lastChange` for incremental comparison and measure unique yield against Open Tech CFPs because upstream coverage overlaps. A live API also does not prove that an old individual CFP remains open.

## Evidence
- [Live API checked](https://api.callingallpapers.com/v1/cfp)
- [API robots exclusion](https://api.callingallpapers.com/robots.txt)
- [Source and method description](https://callingallpapers.com/)
