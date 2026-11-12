# JavaConferences

- **Status:** Later pilot
- **Official/source URL(s):** [javaconferences.org](https://javaconferences.org/), [source repository](https://github.com/javaconferences/javaconferences.github.io)
- **Interface:** `https://javaconferences.org/conferences.json`; human-maintained repository `README.md`
- **Verification:** 2026-11-11

## Data and access

The public, keyless generated JSON is limited to the current and following year. Rows carry `name`, event `link`, `locationName`, country name/code, coordinates, hybrid flag, human-readable event `date`, `cfpLink` and `cfpEndDate`. Repository data is **CC0 1.0**; the inspected repository push was 2026-11-07.

**2026-11-11 snapshot:** 95 records and seven close dates on/after the verification date: Voxxed Days Amsterdam, Open Community Experience, Devoxx Greece, KotlinConf, JAX, jPrime and JNation.

## Caveats

Event and CFP dates are human strings such as `31 March - 1 April 2027`, not normalized ISO datetimes. Valid generated JSON is not necessarily complete: the Markdown source listed ChurConf Seoul on 2027-04-03 with a Google Forms CFP closing 2026-12-15, while its JSON row had empty `cfpLink` and `cfpEndDate`, apparently associated with an extra table date column. Overlap with confs.tech and generic Java lists is expected to be medium-to-high, but was not measured against the tracker.

## Integration guidance

Prefer JSON over table scraping, but include a ChurConf reconciliation fixture so live calls cannot silently disappear. Parse only explicitly supported date formats; preserve other text for review rather than fabricating ISO dates or times. Quantify full-pipeline URL/name deduplication before promotion, and use the feed to correct missing close dates and locations rather than creating duplicate editions.

## Evidence

[Generated JSON](https://javaconferences.org/conferences.json) · [Markdown discrepancy](https://raw.githubusercontent.com/javaconferences/javaconferences.github.io/main/README.md) · [CC0 license](https://raw.githubusercontent.com/javaconferences/javaconferences.github.io/main/LICENSE)
