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
# or, with your own python + PyYAML installed:  python3 src/process-all.py
```

`src/process-all.py` runs all five sources: developers.events, cfp.ninja, confs.tech,
adato-tracker, and any hand-curated rows in `input/*.md`.

- `src/process-developer-events.py` and the other Python sources are real files under `src/`
  in this code folder. Edit them here.
- `--out` is the **directory** for the per-CFP notes (default `data/`). That symlink resolves
  into the vault, whose notes are what `0-dashboard/bases/cfps.base` reads.
- Omit `--today` — the real date is what is wanted. Pass `--today YYYY-MM-DD` only to reproduce
  a past run; it sets the "still open" cutoff.
- Flags: `--months-back N`, `--cache DIR`. Needs python3 + network + PyYAML. The uv project here
  (`pyproject.toml` / `uv.lock`) is the easiest setup: `uv sync` then `uv run python src/…`.
  Without uv, `pip install -r requirements.txt`. `pip install pycountry` is optional
  (country-flag emoji).
- After the sources run, notes that **no** source carries any more are moved through the
  `archived/` symlink into the vault (see below); the run reports how many. `--no-archive`
  skips this; `--archive DIR` changes the destination (default: `archived/` beside the resolved
  `--out` directory).
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
   - per-note edits are preserved: `shortlist`, `submissions`, and the `## Notes` body;
   - the note count is plausible for the sources — it drifts as upstream revises deadlines, so
     report what you actually got, do not force old numbers.
5. Report the new note count, the path, and anything suspicious.

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
`shortlist`, and the body come along. Each live view in `cfps.base` excludes that folder and a
separate **Archived** view matches it, so moved notes drop out of the live views and show only
there. (The exclusion is per-view: the base's top-level filter ANDs with every view.)

- Per-source `--manifest FILE` (JSON list of note paths) is how each parser reports what it
  produced; `src/archive-orphans.py` diffs those against `data/` and does the move. A row that
  yields to another note (`upsert` returns `"skipped"`) is **not** recorded — that is exactly what
  lets the losing duplicate be archived. `upsert_counted` (in `src/cfp_writer.py`) does this
  bookkeeping for all four parsers.
- Only notes with `type: cfp` belong in `data/`; anything else is yours, not the pipeline's.
- `python3 src/archive-orphans.py --dry-run` lists what *would* move, without moving.

## Rules

- Notes are generated. Do not hand-edit the source-owned fields (`name`, `event_date`,
  `location`, `country`, `cfp_close`, `benefits`, `languages`, `event_url`, `cfp_url`,
  `source`) — they are regenerated. Everything else survives a refresh: `shortlist`, `submissions`,
  the `## Notes` body, and any extra frontmatter property you add. `topics` is cumulative:
  existing values are kept and new source values are appended (exact, case-sensitive match), so
  hand-added topics and topics removed/reordered upstream remain unchanged. Only a genuinely
  new topic or another source-property change rewrites the note; a no-op refresh touches nothing.
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
  feeds, so it ranks lowest and only fills gaps.
- **`input/*.md`** — manually curated rows, merged by `src/process-manual-input.py`.

When two sources carry the same conference (same slug), the higher-priority one owns the note:
`manual` > `developers.events` > `cfp.ninja` > `confs.tech` > `adato-tracker`. A lower-priority source skips a note
a higher one already owns, so overlapping feeds do not overwrite each other. The same rule now
applies when the two sources *name* one CFP differently and it would slugify twice: `upsert`
matches on the submission URL (gated by name similarity, so a form reused across distinct events
does not merge them), and the lower-priority note is archived as an orphan.

More may be added — see `cfp-sources.md` for scriptable versus browsable-only sources and their
HTTP-verified status. When you add one: a fetcher under `src/` that normalises to the same row
shape, letting `src/cfp_writer.py` write the note, so the note shape stays stable. Update this
file and the README in the same change.

## Files in this folder

- `data/<year>/` — symlink to one markdown note per CFP in the vault (the data `cfps.base` reads).
- `archived/<year>/` — symlink to the vault's archived CFP notes.
- `tmp/cfps.md` — an earlier generated report; legacy/scratch in the excluded `tmp/`.
- `README.md` — what this folder is, and the source list.
- `INSTRUCTIONS.md` — this file: the procedure.
- `AGENTS.md` — the "why": data shapes, note shape, pitfalls, verification.
- `src/process-all.py` — wrapper that runs every source into `data/`.
- `src/process-developer-events.py`, `src/process-cfp-ninja.py`, `src/process-confs-tech.py`, `src/process-adato-tracker.py`, `src/process-manual-input.py` — per-source fetchers.
- `src/cfp_writer.py` — writes/refreshes one note per CFP (safe YAML, preserved fields).
- `src/country.py` — canonical country labels (`United Kingdom` → `UK`), used by the writer.
- `src/archive-orphans.py` — moves notes no source produces any more into `archived/`.
- `src/normalize-data.py` — one-off pass to re-emit existing notes to the current shape.
- `src/check-links.py` — HTTP liveness sweep over a report's links.
- `cfp-sources.md` — the other CFP sources and their status.
- `pyproject.toml` / `uv.lock` / `requirements.txt` — the uv project (PyYAML); `uv sync`, then
  `uv run python src/…`.
- `tests/` — stdlib `unittest` suite (`python3 -m unittest discover -s tests -v`).
