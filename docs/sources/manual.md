# Manual input

- Status: Implemented
- Source: Personal files under `input/`
- Adapter: [`src/process-manual-input.py`](../../src/process-manual-input.py)
- Verification: 2026-11-14

## Data and access

The adapter reads every file below `input/` recursively. It ignores `input/archived/`.
It follows directory symlinks and reads each directory once to avoid cycles.
Filename extensions do not limit processing. Move inactive files into `input/archived/`.
Every file must contain UTF-8 text. Unreadable files or directories abort collection before note writes.
Remove `manual` from `INPUT_SOURCES` to disable manual input.

Two file shapes are supported:

- Markdown CFP tables.
- Checklists with `- [Conference](https://event-url/)` bullets. `*` and `+` bullets also work.

Other content produces no rows.

Remove the obsolete `MANUAL_INPUT_FILES` setting from `src/config_local.py`.
Unknown settings stop the run.

Table parsing needs the expected CFP header and a separator row. Column names define the mapping.
Reordered columns are supported. Unrelated tables are ignored. CFP-open values are discarded.

Watchlists use live HTML fetches by default. The shared `--cache` directory stores fetched pages.
A failed fetch uses a readable cached page. `--offline` requires cached pages. Watchlist discovery
checks up to three ranked submission candidates. Generic speaker rosters are not CFP links.

Explicitly closed submission pages are skipped. A dated close before `--today` is also skipped.
A fetch failure aborts collection before note writes. An unknown close remains `Unstated`.

## Normalization

Recognized close formats become ISO dates. Other close text stays free text after removal of
`Unstated` slash components. An unparseable event date becomes `TBA`. Topics split on commas.

Table links supply event names and event URLs. Google `/url?...&q=...` wrappers are unwrapped.
Watchlist pages can supply a submission URL and structured event metadata. Manual rows do not infer
`country` from location. Empty submission URLs cannot participate in URL-based deduplication.

Manual has the highest priority among current rows. The reconciler still preserves shortlist,
dismissed, submissions, body notes, and custom properties across source changes.

If the input directory is absent, the full wrapper treats manual as unavailable. Its existing notes
stay live. The standalone command reports an error instead.

## Evidence

- [Current curated input](../../input/gmail1.md) — a real Markdown CFP table.
- [Adapter](../../src/process-manual-input.py) — input selection and normalization.
- [Watchlist resolver](../../src/watchlist.py) — candidate ranking and metadata extraction.
