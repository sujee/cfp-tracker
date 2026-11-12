# How to update the CFPs

Agent-facing instructions for this code folder. Everything needed is here: no other skill or
outside docs. The CFP notes stay in the Obsidian vault. This folder's `data/` and `archived/`
entries are relative symlinks to `cfps/data/` and
`cfps/archived/` in that vault. On a fresh clone they don't exist yet —
run the two `ln -s` commands in README › Quick start first.

**Trigger:** when the user says **“update cfps”** (launched in this folder), run this procedure.

Everything below is relative to this folder (the repo root); assume the agent is
launched here.

## Refresh the per-CFP notes

```
uv run python src/process-all.py      # every source → data/   (uses the project venv)
# or, with your own python + requirements installed:  python3 src/process-all.py
```

`src/process-all.py` runs all **enabled** sources (`INPUT_SOURCES` in `src/config.py`,
comment out a source to skip it; its notes stay in `data/` — they are *not* archived — and
unknown/empty values fail the run): developers.events, cfp.ninja, confs.tech,
adato-tracker, Open Tech CFPs, and any hand-curated rows in the files explicitly
named in `MANUAL_INPUT_FILES` (`src/config.py`).

- `src/process-developer-events.py` and the other Python sources are real files under `src/`
  in this code folder. Edit them here.
- `--out` is the **directory** for the per-CFP notes (default `data/`). That symlink resolves
  into the vault, whose notes are what `0-dashboard/bases/cfps.base` reads.
- Omit `--today` — the real date is what is wanted. Pass `--today YYYY-MM-DD` only to reproduce
  a past run; it sets the "still open" cutoff.
- Flags: `--months-back N`, `--cache DIR`. Needs python3 + network + PyYAML + pycountry.
  The uv project here (`pyproject.toml` / `uv.lock`) is the easiest setup: `uv sync` then
  `uv run python src/…`. Without uv, `pip install -r requirements.txt`.
- After the sources run, notes that **no** source carries any more are moved through the
  `archived/` symlink into the vault (see below); the run reports how many. `--no-archive`
  skips this; `--archive DIR` changes the destination (default: `archived/` beside the resolved
  `--out` directory).
- Last, `src/apply-prestige.py` stamps the curated `tier` (1/2/3) from `prestige.md` onto the
  matching notes. It runs inside `process-all.py` (`--no-prestige` skips it, `--prestige FILE`
  points at another table). A note matching no row keeps whatever `tier` it has, so a hand-set
  ranking survives.
- After a schema change, run `python3 src/normalize-data.py` to re-emit existing notes to the
  current shape (drops any frontmatter `notes`, re-quotes values, canonicalises `country` via
  `src/country.py`, back-fills missing `created`/`updated` stamps). It is idempotent.

## Checklist

1. Be in this code folder. The scripts (`src/`), docs, and manual input live here; `data/`
   and `archived/` are symlinks into the vault.
2. Run the command above.
3. Missing python3, network access, or a dependency (PyYAML, pycountry): install what is needed
   (`pip install -r requirements.txt`), re-run, and report
   what you installed.
4. Verify before reporting back:
   - every note under `data/` parses as valid YAML frontmatter;
   - `event_date` is a clean `YYYY-MM-DD` (start date only, or `TBA`);
   - `event_type` is nonempty (inferred or manually curated), existing overrides survive, and every live type is allowed by `EVENT_TYPES`;
   - per-note edits are preserved: `shortlist`, `dismissed`, `submissions`, and the `## Notes` body;
   - the note count is plausible for the sources — it drifts as upstream revises deadlines, so
     report what you actually got, do not force old numbers.
5. Report the new note count, the path, and anything suspicious. The summary's source × event-type
   matrix counts live notes after deduplication and archiving; ★ marks enabled `EVENT_TYPES`.
6. `python3 src/apply-prestige.py --check` — every tier-1/2 row should match at least one note,
   except the ones deliberately listed as flagships no feed carries. A row with an unexpected
   count means its `keywords` are too broad (or too narrow); fix `prestige.md`, then re-run.

## Testing (any code change)

Data refreshes need no tests, but **any edit to `src/` must leave the suite green and add
tests for the new behaviour**:

1. Run `python3 -m unittest discover -s tests -v`.
2. If your change alters behaviour, update the tests that encode the old behaviour so they
   match — do not weaken or delete them to force a pass.
3. Add tests covering the new/changed behaviour, using the real fixtures in `tests/fixtures/`
   (regenerate with `python3 tests/fixtures/extract_fixtures.py`).
4. A change is not done until the full suite passes.

## Archived notes

A refresh only writes the notes the sources still carry, so a dropped event would otherwise
linger forever. Instead, any note under `data/` that no source produced this run is **moved
byte-for-byte** into `archived/` (same `<year>/` layout). Nothing is edited or deleted — edits,
`shortlist`, `dismissed`, and the body come along. Each live view in `cfps.base` excludes that folder and a
separate **Archived** view matches it, so moved notes drop out of the live views and show only
there. (The exclusion is per-view: the base's top-level filter ANDs with every view.)

- Per-source `--manifest FILE` (JSON list of note paths) is how each parser reports what it
  produced; `src/archive-orphans.py` diffs those against `data/` and does the move. A row that
  yields to another note (`upsert` returns `"skipped"`) is **not** recorded — that is exactly what
  lets the losing duplicate be archived. Resolved event types excluded by the `EVENT_TYPES`
  allow-list use the same skip path: they never enter data, and existing notes of those types move
  to `archived/`. `upsert_counted` (in `src/cfp_writer.py`) does this bookkeeping for every parser.
- Only notes with `type: cfp` belong in `data/`; anything else is yours, not the pipeline's.
- `python3 src/archive-orphans.py --dry-run` lists what *would* move, without moving.

## Rules

- Notes are generated. Do not hand-edit the source-owned fields (`event_name`, `event_date`,
  `location`, `country`, `cfp_close`, `benefits`, `languages`, `event_url`, `cfp_url`,
  `source`) — they are regenerated. Everything else survives a refresh: `shortlist`, `dismissed`, `submissions`,
  the `## Notes` body, and any extra frontmatter property you add. `topics` is cumulative:
  existing values are kept and new source values are appended (case-insensitive match — `English`
  and `english` are one value), so hand-added topics and topics removed/reordered upstream remain
  unchanged. Only a genuinely new topic or another source-property change rewrites the note; a
  no-op refresh touches nothing. `languages` values are case-folded, so notes always store them
  lowercase.
- `event_type` is inferred for new/missing values as `conference`, `meetup`, `summit`, `workshop`,
  `hackathon`, or `webinar` (default `conference`; `other` is available for manual curation).
  `EVENT_TYPE_KEYWORDS` in `src/config.py` controls the ordered singular aliases. Matching ignores
  case, accepts spaces or hyphens between words, and permits a plural `s`. Existing non-empty values
  are sticky, including manual overrides. Alias changes therefore do not reclassify existing notes.
  A missing value back-fills during refresh or `normalize-data.py` without advancing a valid
  `updated` stamp. Invalid mappings or aliases raise `ValueError`.
- `EVENT_TYPES` in `src/config.py` is the nonempty allow-list applied after type resolution.
  The checked-in list currently enables `conference`, `summit`, and `workshop`; the writer's
  missing-config fallback excludes only `meetup`. Excluded rows are skipped and existing notes
  archived; an allowed explicit override survives. Unknown values or an empty list raise
  `ValueError` before source or archive steps run.
- `IGNORE_NAMES` in `src/config.py` drops any event whose name contains a configured string. Matching
  ignores case and applies anywhere in the name, not only at the start. The writer enforces this for
  every source before creating or rewriting a note. Skipped rows enter no manifest and archive normally.
  Invalid settings raise `ValueError`. `IGNORE_TOPICS` separately filters adapter-level name/topic terms.
- `created` and `updated` are pipeline stamps (`YYYY-MM-DD`). `created` is the note's
  first-seen date and is preserved. `updated` advances to the run date whenever a source change
  rewrites the note; a no-op refresh leaves both untouched. A missing or invalid stamp
  back-fills on the next refresh without counting as an update (the note's two stamps are
  copied from each other, so existing notes start with `updated` equal to `created`), and
  `src/normalize-data.py` applies the same back-fill to the whole tree in one pass.
- **Every code change must keep the tests green — and come with tests.** Run
  `python3 -m unittest discover -s tests -v` (stdlib only — no pytest) after any change to
  `src/`. Existing tests must pass: if a change legitimately alters behaviour, update the
  affected tests to match, and **add new tests** that cover the new behaviour. Never leave the
  suite failing and never delete a test just to make the run pass. Build new tests on the real
  sample fixtures under `tests/fixtures/` (refresh them with
  `python3 tests/fixtures/extract_fixtures.py`).
- Never scrape the developers.events website: it is a stale build-time snapshot carrying older
  deadline strings. The scripts fetch the JSON live.
- Rows are copied from the sources, not curated by hand. If a value looks wrong, check the
  source before "fixing" it in a note.
- `tier` is the exception, and it is not a source field: it is curated in `prestige.md` and
  applied by `src/apply-prestige.py`. Change a ranking there, not in a note — on a matched note
  the registry wins. A hand-set `tier` on a note that matches **no** row is kept, so a one-off
  can be ranked directly. `tier` is never compared against source data, so stamping it does not
  advance `updated`.
- Manual input reads only the explicit `MANUAL_INPUT_FILES` list (`src/config.py`), not every
  file in `input/`. Other Markdown checklists are ignored until added to that list.
- Do not commit or push anything to git unless asked. Always ask permission first — never
  commit or push automatically.

## Sources

Merged into `data/`:

- **developers.events** — `all-cfps.json` + `all-events.json`, fetched live.
- **cfp.ninja** — `cfp.ninja/api/v0/events` (public, no auth). Real `cfp_open_at`/`cfp_close_at`
  dates and speaker benefits (`travel`/`hotel`/`honorarium` → the note's `benefits`). The
  submission page is `cfp.ninja/e/<slug>`; filter on `cfp_close_at`, never `cfp_status`.
- **confs.tech** — `github.com/tech-conferences/conference-data` JSON (`cfpUrl` + `cfpEndDate`).
- **adato-tracker** — the `tablesorter` table on `adatosystems.com/cfp-tracker/` (Leon Adato).
  Clean ISO dates, event + CFP URLs, city/state; no topics or benefits. It aggregates the same
  feeds and only fills gaps. Scrape the table, not the RSS.
- **Open Tech CFPs** — public `open.json` + `closed.json`, CC BY 4.0, Sessionize-derived.
  Filter `cfp_close_utc`, not `status`; map only explicit travel/accommodation coverage to benefits.
  It ranks lowest and fills gaps.
- **Manual input** — rows from `input/` files explicitly named in `MANUAL_INPUT_FILES` (`src/config.py`); `- [Conference](url)` checklist bullets resolve CFP pages via `src/watchlist.py`. Explicitly closed submission pages and closes before `--today` are skipped.

When two sources carry the same conference (same slug), the higher-priority one owns the note:
`manual` > `developers.events` > `cfp.ninja` > `confs.tech` > `adato-tracker` > `open-tech-cfps`. A lower-priority source skips a note
a higher one already owns, so overlapping feeds do not overwrite each other. The same rule now
applies when the two sources *name* one CFP differently and it would slugify twice: `upsert`
matches on the submission URL (gated by name similarity, so a form reused across distinct events
does not merge them), and the lower-priority note is archived as an orphan.

More may be added — see `docs/cfp-sources.md` for scriptable/browsable-only status and
`docs/sources/` for detailed notes. When you add one: a fetcher under `src/` that normalises to the same row
shape, letting `src/cfp_writer.py` write the note, so the note shape stays stable. Update this
file and the README in the same change.

## Files in this folder

- `data/<year>/` — symlink to one markdown note per CFP in the vault (the data `cfps.base` reads).
- `archived/<year>/` — symlink to the vault's archived CFP notes.
- `tmp/cfps.md` — an earlier generated report; legacy/scratch in the excluded `tmp/`.
- `README.md` — what this folder is, and the source list.
- `INSTRUCTIONS.md` — this file: the procedure.
- `AGENTS.md` — the "why": data shapes, note shape, pitfalls, verification.
- `src/process-all.py` — wrapper that runs every **enabled** source (see `INPUT_SOURCES` in
  `src/config.py`) into `data/`; skipped sources' notes stay in `data/`.
- `src/process-developer-events.py`, `src/process-cfp-ninja.py`, `src/process-confs-tech.py`, `src/process-adato-tracker.py`, `src/process-open-tech-cfps.py`, `src/process-manual-input.py` — per-source fetchers.
- `src/cfp_writer.py` — writes/refreshes one note per CFP (safe YAML, preserved fields).
- `src/country.py` — canonical country labels (`United Kingdom` → `UK`), used by the writer.
- `src/archive-orphans.py` — moves notes no source produces any more into `archived/`.
- `src/watchlist.py` — parses explicit checklist bullets and discovers a conference site's own CFP link; extracts only stated dates/metadata.
- `src/normalize-data.py` — one-off pass to re-emit existing notes to the current shape.
- `src/check-links.py` — HTTP liveness sweep over a report's links.
- `prestige.md` — the curated conference ranking (tier 1/2/3), edited by hand.
- `src/prestige.py` — loads and matches `prestige.md`; `src/apply-prestige.py` stamps `tier`.
- `docs/cfp-sources.md` — source index; `docs/sources/` holds one detail page per source.
- `pyproject.toml` / `uv.lock` / `requirements.txt` — the uv project (PyYAML + pycountry); `uv sync`, then
  `uv run python src/…`.
- `tests/` — stdlib `unittest` suite (`python3 -m unittest discover -s tests -v`).
