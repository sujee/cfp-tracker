# CFP Radar

- Status: Rejected
- Official/source URL: https://www.cfpradar.dev/
- Verification: 2026-11-18 07:44 UTC

## Finding

CFP Radar is not suitable as a recurring tracker source. The public JSON Feed remains incomplete and stale.

The feed returned 200 items. Their close timestamps ranged from 2026-08-06 through 2026-09-01. Every item closed before this verification.

The directory displayed 707 open CFPs across 20 pages. Its index timestamp was 2026-11-17 11:55 UTC, approximately 20 hours before this verification. The footer states that Sessionize data refreshes every six hours.

Feed items provide Sessionize submission URLs, event dates, locations, topics, and travel benefits. They provide no separate event website.

## Directory findings

One directory snapshot contained 707 cards and 703 unique detail URLs. Four detail URLs appeared on two pages each.

- Close dates ranged from 2026-11-18 through 2027-11-09.
- 42 cards close between 2026-11-18 and 2026-11-24.
- 121 cards are online, and 586 cards are in person.
- 26 cards state flight or hotel coverage.
- 129 cards show a past event date.
- 127 cards show no event start date.

Repeated names occur in 107 groups. Many represent recurring meetup instances, so these groups do not all indicate duplicates.

The directory includes non-tech entries such as `Red Dog Casino Review`. One `CBUS HUG 2026` card pairs a 2026-09-30 event with a 2026-11-19 close.

The directory has current deadlines, but its event metadata requires individual review.

## Access and provenance

- `robots.txt` disallows `/api/`.
- The site shows no clear data license.
- The advertised source repository and its raw README returned HTTP 404.

## Tracker guidance

Do not add CFP Radar to `INPUT_SOURCES`. Do not build a recurring parser around the JSON Feed.

Use the human-readable directory only as an optional cross-check. Verify each deadline and submission URL independently. Do not use directory pagination to bypass the API access restriction.

Revisit automation only when all these conditions are true:

- An authorized interface exposes the complete data set.
- Close timestamps are current.
- The data license permits the intended use.
- The robots policy permits the intended access.
- Project provenance is available.

Prefer Open Tech CFPs for broad Sessionize coverage.

## Evidence

- [Directory](https://www.cfpradar.dev/)
- [JSON Feed](https://www.cfpradar.dev/api/feed.json)
- [Robots exclusion](https://www.cfpradar.dev/robots.txt)
- [Advertised repository returning HTTP 404](https://github.com/gemanor/cfp-radar)
