# CFP Radar
- Status: Rejected
- Official/source URL: https://www.cfpradar.dev/
- Verification: 2026-11-11

## Finding
CFP Radar is not suitable as the tracker's Sessionize adapter. Its JSON Feed supplied only 200 items while the directory advertised roughly 700 open CFPs, so the feed is incomplete. Inspected leading rows contained expired close timestamps, including 2026-08-06, despite the current/open framing. Items provide Sessionize submission URLs and useful CFP fields but no separate event website. Automated use also has unresolved access and provenance problems: `robots.txt` disallows `/api/`, no clear data license was visible, and both the advertised source repository and its raw README returned 404.

## Tracker guidance
Do not build a recurring parser around this feed or treat directory totals as feed coverage. Its human-readable directory may remain an optional cross-check, with every deadline and submission URL independently verified. Revisit automation only if a complete, current, clearly licensed interface exists, robots policy permits the intended use, and project provenance is available again. Prefer Open Tech CFPs for broad Sessionize coverage; never import stale feed rows without applying a current-date cutoff.

## Evidence
- [JSON Feed](https://www.cfpradar.dev/api/feed.json)
- [Robots exclusion](https://www.cfpradar.dev/robots.txt)
- [Advertised repository returning 404](https://github.com/gemanor/cfp-radar)
