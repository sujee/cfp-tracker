# Adato CFP Tracker

- Status: Implemented
- Official/source URL(s): [Adato Systems CFP Tracker](https://adatosystems.com/cfp-tracker/)
- Interface: the HTML `<table class="tablesorter">` on `/cfp-tracker/`; adapter [`src/process-adato-tracker.py`](../../src/process-adato-tracker.py)
- Verification: 2026-11-11

## Data and access

Leon Adato's public eight-column table supplies Event Name, City, State, Event Start, Event End, CFP Close, Event URL, and CFP URL. No authentication is required. Dates are expected as strict ISO `YYYY-MM-DD`; the last two columns provide hyperlinks rather than useful link text. The adapter prefers readable `cache/adato-tracker.html` indefinitely and otherwise fetches the page once.

## Caveats

Do **not** build from Adato RSS: dated CFP-listing posts only announce refreshes, their detail pages are stubs, and RSS carries excerpts rather than the table. Rows lacking exactly eight cells, a name, a CFP hyperlink, or a strict ISO close date are rejected; ISO datetimes and free-text deadlines are not accepted. Event End is ignored. This tracker aggregates other feeds, so substantial overlap is expected. No topics, languages, or speaker benefits are stated by this interface.

## Integration guidance

Include deadlines on/after the inclusive cutoff (standalone default: 30 days back) and dedupe by normalized name plus close date. Map Event Start or `TBA`, the two hrefs, and city/state display location. `City == VIRTUAL`, case-insensitively, becomes location and country `Online`; physical-event country remains empty rather than inferring a country from state. The shared writer still preserves cumulative hand-added topics. Ignore-term filtering examines only the event name. Priority is below confs.tech and above open-tech-cfps, making Adato a gap filler rather than the owner of richer overlapping notes.

## Evidence

- [CFP Tracker table](https://adatosystems.com/cfp-tracker/) — canonical table, columns, dates, and outbound links.
