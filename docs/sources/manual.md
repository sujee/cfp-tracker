# Manual input

- Status: Implemented
- Official/source URL(s): [local `input/` directory](../../input/)
- Interface: sorted, nonrecursive [`input/*.md`](../../input/) Markdown tables; adapter [`src/process-manual-input.py`](../../src/process-manual-input.py)
- Verification: 2026-11-11

## Data and access

No network access is used. Each recognized row needs at least five columns: conference name/link, location, CFP open (ignored), CFP close, conference date, and optional comma-separated topics. Header/separator rows, empty names, solicitation text, and configured ignored-name matches are skipped. There is no recency filter or parser-level deduplication; input files and rows retain sorted-file/line order.

## Caveats

Only simple Markdown links and unescaped literal-pipe tables are supported. The first link's text becomes the clean event name and its destination the event URL; Google `/url?...&q=...` wrappers are unwrapped. `cfp_url` is always empty, country is not inferred from location, and a CFP opening value is discarded. Free-text dates can survive normalization, so not every manual note has an ISO deadline or event date. Ambiguous numeric dates try day/month before month/day (`03/04/2027` means 3 April 2027). Avoid literal `|` inside cells.

## Integration guidance

Recognized close formats become ISO. For other values, `Unstated` slash components are removed and remaining free text retained; if none remain the result is `Unstated`, while originally empty input becomes `—`. Event ranges contribute their parsed start date when supported, otherwise source text remains. Topics split on commas. Manual has the **highest ownership priority**, wins same-path conflicts, and rewrites source-owned fields while the shared writer preserves notes, shortlist, submissions, and extra properties. Empty CFP URLs cannot participate in cross-path URL dedupe, so use accurate names and avoid duplicate manual rows. The full wrapper omits this source when its input directory is absent; the standalone command errors instead.

## Evidence

- [Current curated input](../../input/gmail1.md) — real Markdown-table layout.
- [Adapter](../../src/process-manual-input.py) — exact parsing, normalization, and mapping rules specified above.
