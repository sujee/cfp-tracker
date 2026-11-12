# CFP watchlist — agent notes

Field notes for this code folder. The procedure an agent should follow is in
[`INSTRUCTIONS.md`](INSTRUCTIONS.md); this file is the "why" behind it — data shapes, traps,
and the shape each CFP note must take.

Code and support files live in this folder (the repo). The Obsidian
vault's `cfps/` folder contains only `data/` and `archived/`. This folder's `data`
and `archived` entries are relative symlinks to those vault directories, so the existing
commands operate on the notes in place. On a fresh clone the two symlinks must be created
first (`ln -s` commands in README › Quick start).

This folder is a git repo with `origin` → `git@github.com:sujee/cfp-tracker.git`.

Keeps a set of **one note per conference** under `data/`, refreshed from public CFP feeds
(developers.events, cfp.ninja, confs.tech, adato-tracker, Open Tech CFPs, and hand-curated files named in `MANUAL_INPUT_FILES`). The notes are the
data source for the `cfps` base in the dashboard (`0-dashboard/bases/cfps.base`).

## Documentation style

- Write `README.md` for human users. Keep it concise and focused on setup, configuration, and
  daily tasks. Put detailed implementation rules in `INSTRUCTIONS.md`, `AGENTS.md`, or `docs/spec.md`.
- Load the `asd-ste100` skill before rewriting documentation.
- Use STE-flavored writing for explanatory prose. Use strict ASD-STE100 writing for procedures,
  warnings, and instructions where a misreading has a cost.
- Use active voice and simple tenses. Give one instruction per sentence. Keep instructions to 20
  words or fewer per sentence and descriptions to 25 words or fewer.
- Do not use semicolons or phrasal verbs. Use lists for three or more steps or conditions. Use the
  same term for the same concept throughout a document.
- Preserve technical terms, conditions, scope, and uncertainty. Do not remove required details only
  to shorten a sentence.

## When to use

- The user points at developers.events (/#/<year>/cfp) and wants the open or recently-closed
  CFPs listed, filtered, or refreshed.
- A recurring speaking-CFP sweep.
- The user says **“update cfps”** — the standing trigger for the refresh in `INSTRUCTIONS.md`.
- Not for: scraping a specific conference's own CFP page (go there directly).

## Fetch the data, don't scrape the rendered page

The developers.events page bundle is a build-time snapshot and is *stale*. The live files are:

- `https://developers.events/all-cfps.json` — `link`, `until` string, `untilDate` (epoch ms),
  `conf.{name,date[],hyperlink,location,status}`, optional `durations` (`talk:20`)
- `https://developers.events/all-events.json` — `name, date[], hyperlink, location, city,
  country, misc, cfp, tags[{key,value}]`

confs.tech lives in `github.com/tech-conferences/conference-data`
(`conferences/<year>/<topic>.json`, with real `cfpUrl` + `cfpEndDate`).

Both are public; the scripts fetch the JSON live. Upstream developers.events data lives in
[scraly/developers-conferences-agenda](https://github.com/scraly/developers-conferences-agenda).

**Record fields:** the CFP URL is `link` (not `cfp`), the event site is `conf.hyperlink`.
Reading the wrong key returns zero matches and looks like the source stopped carrying that
platform.

Select rows with `untilDate >= <cutoff>`. Every `conf.status` is `"open"` even for 2019
entries, so ignore that field — filter on the date.

cfp.ninja (`cfp.ninja/api/v0/events?per_page=100&page=N`, public, no auth) has the same trap:
`cfp_status` says `"open"` for years-old rows, so filter on `cfp_close_at` (an ISO datetime).
Its `country` is a mix of codes and names (`USA`, `UK`, `NL`, `Germany`) and is empty for
online events (`is_online`); the submission page is `cfp.ninja/e/<slug>`. Its events skew
toward a few recurring series (Conf42, SREday/LLMday/PLATFORMday), which is expected.

Open Tech CFPs is a CC BY 4.0 Sessionize-derived dataset (`api/open.json` + `api/closed.json`).
Filter on the exact `cfp_close_utc`, never `status`. `url` is the submission page, `website` the
event page, and `country` is ISO alpha-2 (converted through `pycountry`). Only `travel` and
`accommodation` values of `"expenses covered"` become benefits; `fee: free for speakers` is not
an honorarium. Tags are inferred upstream. Dedupe by normalized name + UTC close date because
those values determine the note path; the newest source `updated` record wins duplicates.

## How to run

```
uv run python src/process-all.py      # every source → data/   (uv project: pyproject.toml + uv.lock)
# or:  python3 src/process-all.py
```

Options: `--months-back N` (how far back "recently closed" reaches, default 1), `--today
YYYY-MM-DD`, `--cache DIR`. Needs python3 + network + PyYAML + pycountry (`uv sync`, or
`pip install -r requirements.txt`). (`--focus-tags` /
`--no-focus` are retained but only affect the retired report — see *Focus filtering* below.)

`process-all.py` validates `EVENT_TYPES` before source/archive subprocesses. Its summary also
prints a source × event-type matrix of live notes after deduplication/archiving; ★ marks included
types. These note counts differ from the raw source-row totals.

`src/normalize-data.py` re-emits existing notes to the current shape in place (drops
frontmatter `notes`, re-quotes values); idempotent.

## Layout of this folder

Everything an agent needs is here, deliberately:

- `INSTRUCTIONS.md` — the procedure (command, checklist, rules).
- `AGENTS.md` — this file: data shapes, pitfalls, note shape.
- `data/<year>/` — symlink to the per-CFP notes in the vault (what `cfps.base` reads).
- `archived/<year>/` — symlink to notes no source produces any more, moved aside by
  `src/archive-orphans.py`; shown only in the base's Archived view.
- `src/config.py` — tracked defaults plus the validated `config_local.py` loader.
- `src/config_local.py` — personal overrides, gitignored; copy `src/config_local.example.py`
  to create it. Unset settings inherit the defaults.
- `src/discovered-topics.txt` — generated confs.tech topic reference; not used for extraction.
- `src/process-all.py` — wrapper that runs every **enabled** source (see `INPUT_SOURCES`
  in `src/config_local.py`) into `data/`; skipped sources' notes are left in `data/`, not archived.
- `src/process-developer-events.py` — developers.events fetcher (was `src/build-open-cfps.py`; that name remains as a shim).
- `src/process-cfp-ninja.py` — cfp.ninja fetcher (public `api/v0/events`).
- `src/process-confs-tech.py` — confs.tech fetcher.
- `src/process-adato-tracker.py` — adato-tracker fetcher (the `tablesorter` table on
  `adatosystems.com/cfp-tracker/`).
- `src/process-open-tech-cfps.py` — Open Tech CFPs fetcher (open + closed static JSON).
- `src/process-manual-input.py` — merges hand-curated `input/` files explicitly named in `MANUAL_INPUT_FILES` (`src/config_local.py`).
- `src/watchlist.py` — resolves `- [Conference](url)` checklists to CFP pages and event metadata.
- `src/cfp_writer.py` — writes/refreshes one note per CFP (safe YAML, preserved fields).
- `src/country.py` — canonicalises the `country` value (`United Kingdom` → `UK`, …).
- `src/archive-orphans.py` — moves notes no source produces any more into `archived/`.
- `src/normalize-data.py` — one-off pass to re-emit existing notes to the current shape.
- `src/check-links.py` — HTTP liveness sweep over a report's links.
- `prestige.md` — the hand-curated conference ranking (`conf name | ranking | keywords`) that
  `src/apply-prestige.py` turns into each note's `tier`. Judgment, not data: no feed carries
  attendance, acceptance rate, or program pedigree.
- `src/prestige.py` — parses `prestige.md` and matches a note name to a tier.
- `src/apply-prestige.py` — stamps `tier`; `--check` reports per-row match counts and writes nothing.
- `docs/cfp-sources.md` — source index with HTTP-verified status; detailed notes in `docs/sources/`.
- `pyproject.toml` / `uv.lock` / `requirements.txt` — the uv project (PyYAML + pycountry); `uv sync` creates
  the `.venv`, then `uv run python src/…` uses it.
- `cfps.base` — Obsidian views; personal country and local-area predicates live in `formulas`.
- `README.md` — overview and the source list.
- `tests/` — stdlib `unittest` suite for the writer, the run summary, and all six parsers
  (`python3 -m unittest discover -s tests -v`); fixtures under `tests/fixtures/` are real
  slices of the downloaded data.
- `tmp/cfps.md` — an earlier generated report, now a legacy/scratch copy kept in the excluded `tmp/`.

Do not replace the `data/` or `archived/` symlinks with ordinary directories: a refresh would
then write outside the vault. The Python sources and docs are real files in this code folder.

## Git

- **Never commit to git automatically.** Never push automatically. **Always ask
  permission before `git commit` or `git push`** — a recent commit in this session does not
  imply consent for the next one; ask each time.
- `data/` and `archived/` are gitignored symlinks into the vault (`README.md` › Quick start
  creates them). Never force-add their contents, and never replace them with real
  directories.

## Note shape

One note per conference, written by `src/cfp_writer.py`. Frontmatter:

```yaml
type: cfp
event_name: <conference name>
event_date: 2027-04-01          # start date only, clean YYYY-MM-DD (or "TBA")
event_type: conference          # inferred: conference | meetup | summit | workshop | hackathon | webinar | other
location: Pasadena, CA (USA)
country: USA                   # canonical: USA | UK | Online | a country name | empty
cfp_close: 2026-11-01          # deadline; may be free text ("Early 2027 / Unstated")
topics: [ai, agents]
benefits: [travel, hotel]      # optional; source-stated only (cfp.ninja, Open Tech CFPs) → travel | hotel | honorarium
languages: [english]           # optional; from developers.events event tags; other sources carry none
event_url: https://…           # conference site
cfp_url: https://…             # CFP / submission URL
source: developers.events      # developers.events | cfp.ninja | confs.tech | adato-tracker | open-tech-cfps | manual
shortlist: false               # user flag, preserved across runs
dismissed: false               # user flag, defaults false and preserved across runs; true hides live views
submissions: []                # wiki links (a list), preserved across runs
created: 2026-11-06            # pipeline stamp: the note's first-seen date, set once
updated: 2026-11-06            # pipeline stamp: run date of the last source-driven rewrite
tier: 1                        # optional; curated from prestige.md (1 flagship, 2 major, 3 notable)
```

`tier` is written by `src/apply-prestige.py`, not by `src/cfp_writer.py`, and appears only on
notes a `prestige.md` row matches. It is a *number* (`tier: 1`, unquoted) so a Bases filter can
compare `tier == 1`; it is not in `KNOWN_FM_KEYS`, so the writer treats it as user metadata and
re-emits it verbatim on every rewrite.

Then a body with a `## Notes` heading and the free-form notes. **Notes live only in the body**
— there is no `notes` frontmatter field.

A hand-created CFP note should start from `templates/cfp-template.md` at the vault root (the
core Templates plugin folder). It carries exactly the keys above — verified to match what
`src/cfp_writer.py` emits for a new note — so a manual note and a generated one are
interchangeable. Set `source: manual` there: `manual` outranks every feed, so the pipeline will
not overwrite a note you wrote by hand.

Quoting: every value is emitted through `cfp_writer._yaml_str` (and `_yaml_list` for `topics`,
`benefits` and `languages`), so names containing `": "`, quotes, leading indicators, or newlines
are double-quoted and stay valid YAML. A value YAML would otherwise retype is quoted too —
`365`, `2026`, `1.0`, `yes`, `null` resolve to int/float/bool/null, so a topic `365` is written
`"365"` and reads back as a string (`_yaml_reads_as_non_string`). ISO dates are the deliberate
exception: `event_date`, `cfp_close`, `created` and `updated` stay unquoted so PyYAML types them
as dates and Obsidian maps them to its date property; `_as_str` turns them back into
`YYYY-MM-DD`. `shortlist` and `dismissed` are written as bare `true`/`false` booleans.
`benefits` and `languages` are written only when a source states one, so notes from sources that
don't carry them are rendered exactly as before (no empty line).

## Focus filtering

Legacy. `FOCUS_TAGS` (in `src/process-developer-events.py`) and the 🤖 marker belonged to the
retired single-file report; the per-CFP notes carry no marker, so `--focus-tags` / `--no-focus`
currently change nothing the base reads. Kept for reference / if the report returns.

## Pitfalls

- **Personal configuration belongs in gitignored `src/config_local.py`.** `src/config.py`
  contains defaults and loads local ALL_CAPS overrides at import. A setting in the local file
  replaces its default; unset names inherit. Unknown setting names and errors in the local file
  fail loudly rather than reverting silently. Copy `src/config_local.example.py` to create it.
  Adapter imports deliberately do not swallow configuration errors.
- **The source-owned fields are regenerated; everything else survives a refresh.**
  `event_name`, `event_date`, `location`, `country`, `cfp_close`, `benefits`, `languages`,
  `event_url`, `cfp_url`, `source` are rebuilt from the row; `shortlist`, `dismissed`,
  `submissions`, the `## Notes` body, and any *extra* frontmatter property you add (e.g. `priority`,
  `tags`, a nested `contact:` map) are preserved. `type: cfp` is fixed.
  Legacy `name` is a fallback for `event_name`. A rewrite removes `name`. Renaming this key alone does not advance `updated`.
- **`event_type` is inferred once, then sticky.** New/unset notes use `infer_event_type(name)`,
  driven by the ordered `EVENT_TYPE_KEYWORDS` mapping, with defaults in `src/config.py` and
  optional overrides in `src/config_local.py`. It supports singular
  aliases for `meetup`, `summit`, `workshop`, `hackathon`, and `webinar`. Mapping order controls
  precedence; aliases match case-insensitively at word boundaries, allow spaces or hyphens between
  words, and accept an optional plural `s`. The default aliases cover meet-up variants and
  `user group`/`user-group`/`usergroup`. Everything else defaults to `conference`; `other` is for
  curation. Any existing non-empty value, including a manual override, is preserved and does not
  itself trigger a rewrite. A missing value back-fills during `upsert` and `normalize_file` with
  return status updated when a file changes, but valid `created`/`updated` stamps stay unchanged
  unless another source property changed. Invalid mappings and aliases raise `ValueError`.
- **Event types are controlled by an allow-list.** `src/config_local.py` can override the
  nonempty `EVENT_TYPES` default in `src/config.py`
  (currently `conference`, `summit`, `workshop`; the missing-config fallback enables every
  controlled type except `meetup`). After the sticky/inferred type is resolved, `upsert` returns
  `skipped` for a disallowed type before any URL dedupe or write. New excluded events create no
  note, and existing ones are omitted from manifests and archived byte-for-byte. An explicit
  allowed override remains sticky. The CFP-URL index ignores excluded notes so they cannot block
  replacements. Empty lists and unknown type names raise `ValueError` before any source or archive
  subprocess instead of silently archiving broadly.
- **`IGNORE_NAMES` filters literal event-name fragments, not only prefixes.** `cfp_writer.upsert`
  case-folds each configured string and skips any row whose name contains it anywhere. The `.NET`
  entry in the example/local configuration therefore rejects both `.NET Conf` and
  `Azure .NET Developer Days`. The check runs before
  note-path creation, event-type inference, and URL deduplication. Skipped rows enter no manifest, so
  existing notes archive normally. Empty or non-string settings fail without writing a note.
  `IGNORE_TOPICS` remains a separate, adapter-level name/topic/tag filter.
- **`topics` and `languages` are cumulative, not replaced.** `_merge_list` keeps the existing list verbatim
  as a prefix and appends only incoming values not already present (case-insensitive
  match — `English` and `english` are one value, the existing spelling wins; incoming
  duplicates append once). Hand-added values and source values removed or
  reordered upstream therefore survive without forcing a rewrite. A genuinely new value
  does rewrite the note and advances `updated`; the next identical refresh is unchanged.
  The merged list is built before `_source_props_match`, so this no-op behavior falls out
  of the normal semantic list comparison. `languages` values are additionally
  case-folded before the merge, so a note always stores them lowercase (`English` becomes
  `english`) — a pre-existing capitalised note reads as one mismatch, is rewritten
  lowercase on the next refresh, and then settles. The one exception is `benefits`,
  which is replaced on update.
- **`created` and `updated` are pipeline stamps, not source fields.** `created` is written
  when the note first appears and preserved afterwards; `updated` is advanced to the run date
  only when a source change rewrites the note (a no-op refresh changes neither). They are
  deliberately **not** part of the source-property compare: comparing them with today would
  rewrite every note on every run. A missing or non-`YYYY-MM-DD` stamp back-fills without
  counting as an update: a note that has one stamp copies it to the other, so existing notes
  start with `updated` equal to `created`, and a hand-typed valid date is left alone.
  `normalize_file` applies the same back-fill and preserves present stamps (a shape pass is
  not a data update), which is how the whole tree was populated. For notes that predate the
  stamps, `created`/`updated` were recovered from the note's first add commit in the vault's
  git history (following renames), so they carry the real first-seen date rather than the day
  the stamps were introduced.
- **A refresh only rewrites a note whose source properties actually changed.** Before
  writing, `upsert` compares each source-owned property in the existing note (semantic
  compare — quoting/formatting differences do not count) and skips the write when all
  match, so untouched notes keep their mtime and your edits are never clobbered. Extra
  properties are re-emitted verbatim, including block lists and nested maps. The exceptions are
  missing `created`/`updated` stamps and a missing `dismissed` flag: those back-fill once without
  advancing valid stamps, then the note is unchanged again.
- **Tests are required for every code change.** `python3 -m unittest discover -s tests -v`
  (stdlib only) covers the change detection and preservation rules. Any `src/` edit must keep
  the suite passing — update tests whose expectations legitimately changed, and add tests for
  new behaviour. Fixtures are real slices of the downloaded data under `tests/fixtures/`.
- **Dropped events are archived, not left behind.** `process-all.py` moves any `type: cfp` note
  under `data/` that **no** source produced this run into `archived/` (byte-for-byte: nothing
  edited or deleted). Each paired `(-dismissed)` data view uses `formula.is_live` to exclude dismissed
  notes. Its `(+dismissed)` variant uses `formula.is_in_data` instead. **Short listed** and
  **Submitted** are single views without dismissal filtering or a Dismissed column; Submitted also
  shows `formula.submission_count`. **Dismissed** and **Archived** are single views that include
  dismissed notes. Folder filters are per-view because the base's top-level filter ANDs with every view, so a global
  data-folder restriction would blank Archived. Only `type: cfp` notes are touched. Other files in
  `data/` are left alone. `--no-archive` disables archiving.
- **`dismissed: true` is the user's "not interested" flag.** New notes and the vault template
  default it to `false`; `upsert` and `normalize_file` back-fill it when missing without advancing
  valid stamps. It is in `KNOWN_FM_KEYS`, normalized to a bare Boolean on rewrite, and preserved
  across refreshes; the note stays in `data/` (a manual move to `archived/` would instead be
  re-created by the next run). `cfps.base` derives `formula.is_dismissed` / `formula.is_live` from
  it, so a view updates as soon as the property is set — no re-run. The two folder paths live once
  each as `formula.data_dir` / `formula.archived_dir` and match as path *suffixes*
  (`("/" + file.path).contains("/" + formula.data_dir)`), so the same base file works for a
  vault rooted at `cfps/` (the landing instructions) and for this vault
  (`30-speaking-talks/cfps/`, base at `0-dashboard/bases/cfps.base`, dashboard at
  `0-dashboard/cfps-dashboard.md`). The dashboard's Dataview `FROM "cfps/data"` is a literal
  vault-relative folder and does **not** suffix-match, so keep it in step with the vault's own
  copy. The `my_country` and `is_local_area` formulas centralize the personal location filters;
  Obsidian reads these base formulas, not the Python configuration.
- **Manual input reads only explicitly listed files — no `input/*.md` sweep.**
  `MANUAL_INPUT_FILES` in `src/config_local.py` lists relative file paths (usually basenames) inside `input/` and overrides the empty default; checklist and scratch files are ignored unless listed. Absolute paths, `..` traversal, and missing files fail the manual step so a typo cannot silently drop conferences. An empty list makes it a no-op. Only configured tables under those files provide rows.
- **A manual file may instead be a website checklist.** In the same explicitly listed
  `MANUAL_INPUT_FILES`, `- [Conference](https://event/)` bullets (also `*` / `+`) are
  watched, not searched: `src/watchlist.py` fetches that page, chooses only an explicit
  speaker-submission link (Call for Papers / Apply to Speak / …), and reads it once.
  Generic speaker rosters and empty links are not CFPs. JSON-LD `Event` metadata wins;
  an absent event date stays `TBA`, no venue is invented unless structured metadata
  supplies it, and a close is read only near words like "deadline" or "closes" —
  otherwise `Unstated`, never the event date. Unresolved entries are reported, not
  fabricated. A fetch failure aborts the manual step *before* writing so the manifest
  cannot orphan existing notes. `--cache DIR` supplies an optional hashed HTML cache
  (otherwise it always fetches live); process-manual-input accepts `--out`, `--input`,
  `--manifest` as before. A submission page explicitly saying applications/CFP/
  submissions are closed is **not** a discovered CFP; likewise a parsed close before
  today is skipped (`close >= today` remains eligible). `--today YYYY-MM-DD` gives the
  cutoff, or reproduces a past run. CFP pages are read as HTML only, with no browser/JS.
  Unstated close and unknown status stay conservative placeholders, not skipped.
- **Manual input rows are markdown tables.** The first column may be a link
  (`**[Name](url)**`): the parser takes the link *text* as `name`, the link as `event_url`
  (unwrapping Google `.../url?...&q=<real>` redirects), and strips emphasis. Without this the
  markdown — including a Google redirect URL — leaks into the name and slug. The CFP-Close
  cell keeps free text but drops a trailing `"/ Unstated"` (`Dec 2026 / Unstated` → `Dec 2026`).
- **Overlapping feeds: a higher-priority source wins a shared note.** Some conferences appear in
  both developers.events and confs.tech (or cfp.ninja) and normalize to the same slug. Without a
  rule the later writer would overwrite the other. `cfp_writer.SOURCE_PRIORITY`
  (`manual` > `developers.events` > `cfp.ninja` > `confs.tech` > `adato-tracker` > `open-tech-cfps`) makes a lower-priority source skip a
  note a higher-priority one already owns, so a no-op refresh reports 0 updated.
- **Two feeds can name one CFP differently, so it slugifies twice** (`SCaLE` from confs.tech vs
  `Southern California Linux Expo - SCaLE 24x` from developers.events — same `cfp_url`, two
  notes). `cfp_writer.upsert` matches on the submission URL (`_url_key`) **before** the
  "unchanged" short-circuit, so an existing loser note is skipped too, not just a not-yet-created
  one: the higher-priority source owns it and the other's note is archived as an orphan. The match
  is gated by `_names_compatible` — feeds reuse one form across *different* events (JS Poland /
  NG Poland / AI Poland share a Google form; every Apidays city shares one Typeform; Dawn
  Conferences covers Appdevcon and Webdevcon), so a shared URL alone must not merge them. Names
  merge only when one normalised name contains the other or one name's tokens are a subset of the
  other's (years ignored). On a priority tie the lower path wins, so two equal-priority notes for
  one URL converge to one on the next run instead of archiving each other.
- **A `"skipped"` row must not claim its path.** `upsert` returns `"new"` / `"updated"` /
  `"unchanged"` / `"skipped"`; `upsert_counted` folds a row into a parser's counters **and** only
  appends the note path to `produced` (the `--manifest`) when it is *not* skipped. If a yielding
  row claimed its own path, `archive-orphans` would see the loser as "still produced" and never
  move it — the duplicate would linger forever. `"skipped"` rows are counted as `unchanged` in the
  summary line, so `found` still equals the row count.
- **Never build frontmatter by hand-stringing values.** Use `cfp_writer`'s helpers; an
  unquoted name with `": "` (e.g. `Agentics Day: MCP + Agents Europe`) produces invalid YAML
  and the note exposes no properties.
- **Frontmatter is read with PyYAML** (`requirements.txt`), not by hand. `_read_frontmatter*`
  returns a parsed dict whose values keep their YAML types — a date is a `datetime.date`, a
  bool a `bool`, a list a `list` — so normalise with `_as_str` / `_as_list` / `_as_bool` before
  comparing or writing. `_source_props_match` compares only the fields the writer owns
  (`SOURCE_SCALAR_FIELDS` + `LIST_FIELDS`); everything else is preserved verbatim by
  `_extra_frontmatter_lines`. A note whose `---` block is not valid YAML raises
  `FrontmatterError`, and `upsert` / `normalize_file` **skip it** (leaving the file untouched)
  rather than clobbering it.
- **`country` is canonicalised on write.** `cfp_writer.upsert` runs the value through
  `src/country.py` before comparing or writing, so `United Kingdom` and `UK` from different
  feeds land on the same label and never fight over a note. The table folds the informal
  abbreviations the base filters on (`USA`, `UK`), the online spellings (`Virtual` → `Online`),
  and a handful of common variants (`Holland` → `Netherlands`, `Czech Republic` → `Czechia`).
  A value not in the table (`Germany`, `Peru`, …) is passed through stripped but unchanged — the
  normaliser never invents a country. Add spellings to `_ALIAS_GROUPS` and cover them in
  `tests/test_country.py`.
- **URLs are de-UTM'd on write.** `cfp_writer.upsert` runs `cfp_url` and `event_url` through
  `strip_utm`, which removes `utm_*` query parameters (case-insensitive) before comparing or
  writing — the upstream feeds tack per-share tracking tags onto the same page, and those must
  not force rewrites, leak into a note, or defeat the cross-source `cfp_url` match (`_url_key`
  strips them too). The edit is a raw-string one: other query params, their order, encoding and
  any `#fragment` survive verbatim. `normalize-data.py` cleans existing notes the same way.
- **CFP platforms die; verify links before calling a list actionable.** Whole platforms shut
  down and leave dead URLs in the source (papercall.io hosted many CFPs and is now offline).
  Sweep with `python3 src/check-links.py tmp/cfps.md` — it reports non-200s and can be narrowed
  with `--only sessionize.com`. When a note's CFP link is dead, point the user at its event link.
- **Page vs data mismatch is expected.** The developers.events site was built earlier, so its
  CFPs are a subset with older deadline strings (a rendered `Until 31-October-2026` can already
  be `01-November-2026` in the live JSON). Never reconcile the two; use the JSON and say the
  page is a stale snapshot.
- Some conferences appear in both files as a bare name across several editions (`DevFest 2026`
  exists for Faro *and* Ismailia). Match a CFP to its event by **location first, then nearest
  date on/after the deadline** — matching by name alone silently attaches a 2023 edition to a
  2026 CFP.
- `conf.country` in all-events.json can be plain wrong (`DevFest 2026` at `Faro (Portugal)` had
  `country: Lebanon`). Derive the flag/country from the trailing `(...)` **in the location
  string**, falling back to `country`.
- Conference dates carry no year on the page; in the JSON they are epoch ms, which is what
  gives you the real year. `format_event_dates` keeps a range for humans; the note's `event_date`
  is the start date only (`event_date_start`).
- `until` strings mix formats (`31-October-2026`, `March-15-2019`, French `10-Avr-2022`, ranges
  `21-Jan-2022->03-Mar-2022`) — use `untilDate`, not the string.
- The source publishes **no CFP opening date**, only the deadline, so there is no "CFP open"
  field; "still open" is simply `cfp_close >= today`.
- Many events are in the events file but *not* in the CFP file (no open CFP) — iterate the CFP
  file, never the events file.
- Dedupe is by `(normalized name, close date)`; the same conference can legitimately reappear
  with a revised deadline.
- **`tier` is curated, not derived — and it must never be inferred from feed data.** No source
  carries attendance, acceptance rate, or program pedigree, so any "prestige score" computed
  from what the feeds give you (deadline length, co-located events, benefits) would just measure
  which aggregator carried the row. `prestige.md` is the source of truth; `apply-prestige.py`
  only applies it. Two consequences: a tier-3 family series legitimately covers dozens of notes
  (`bsides` ≈ 24, `conf42` ≈ 28), and a *tier-1/2* keyword matching more than ~12 notes is a
  bug — the keyword is too broad.
- **Keyword matching is exact-per-word, plus a trailing year, and nothing else.**
  `srecon` must match `SREcon27 Americas` and `offensivecon` must match `OffensiveCon26`, so the
  matcher allows a name word to equal a keyword word *plus digits*. It deliberately does **not**
  allow any other suffix: `engineer` must not match `engineering` (or `AI Engineer` swallows
  `AI Engineering Summit`), and `scale` must not match `Build, Secure, Scale`. A name that glues
  a non-year suffix needs its own explicit keyword (`scale 24x`). This is precision over recall
  on purpose — `--check` surfaces the misses, and the fix is one more comma-separated keyword.
- **A row may legitimately match nothing.** Rows for flagships no feed carries (re:Invent,
  Google I/O, Cloud Next, Microsoft Build, WWDC, GitHub Universe, PyCon US, NeurIPS, ICML, ICLR,
  USENIX ATC, OSDI, GOTO, SIGMOD, VLDB, CVPR) sit in the same table on purpose: `--check` listing
  them as "matches nothing" *is* the coverage-gap report, and they start matching the day one
  appears in a file listed in `MANUAL_INPUT_FILES`. Never "clean up" a zero-match row without checking whether it is a
  gap row or a typo.
- **A zero-match row is not a failure, but a malformed row is.** `int(ranking)` and an empty
  `keywords` cell raise `ValueError` with the line number, so a typo fails the run instead of
  silently ranking a conference nowhere. Only tables whose header is `conf name | ranking |
  keywords` are parsed, which is why the rubric table in the same file is ignored.
- **The registry wins on a matched note; a hand-set tier survives on an unmatched one.**
  `apply-prestige.py` writes `tier` only when a row matches, so a note matching no row keeps its
  value (rank a one-off by editing the note). `--check` reports those as "tier set but no rule
  matches" so they do not rot. `tier` is never in `SOURCE_SCALAR_FIELDS`: it is not compared
  against source data, so stamping it does not advance `updated`, and the writer re-emits it
  verbatim as user metadata.
- **`INPUT_SOURCES` in `src/config_local.py` selects which sources run.** Remove a source from
  the local list to skip its fetch. Its notes stay in `data/` — `archive-orphans.py --skip-source NAME` exempts
  them — so a source can be paused without mass-archiving its notes. Unknown or empty values
  raise `ValueError` before any source runs (same contract as `EVENT_TYPES`).
- **`prestige.md` stays at the repo root** (and `apply-prestige.py` finds it there). The manual source reads only `MANUAL_INPUT_FILES`, so do not add the prestige list there either — it is a ranking table, not a CFP row.

## Verification

- Note count is in the ballpark of `untilDate >= cutoff` rows in the freshly fetched
  `all-cfps.json` (after dedupe) plus confs.tech and manual rows.
- Every note under `data/` parses as valid YAML frontmatter, `event_date` is `YYYY-MM-DD`
  (or `TBA`), and `event_type` is nonempty (inferred or manually curated).
- `python3 src/normalize-data.py` is idempotent — running it twice leaves the tree unchanged.
- `python3 src/apply-prestige.py` is idempotent too, and every `tier` value is `1`, `2`, or `3`.
  `--check` should show a non-zero count for every tier-1/2 row except the deliberate gap rows;
  a note in the "tier set but no rule matches" list is either a one-off you ranked by hand or a
  row you deleted from `prestige.md`.
- Counts legitimately move between runs: upstream revises deadlines and adds events daily, so a
  refresh gaining or losing a handful of notes is normal. Diff against the source data at run
  time, not against the previous state — a stale run is not the baseline.
