# CFP Tracker documentation

Detailed documentation for CFP Tracker. The [README](../README.md) covers setup and the
first refresh. This page covers the pipeline, the note format, every setting, and every
command.

## Contents

- [How the pipeline works](#how-the-pipeline-works)
- [Note format](#note-format)
- [Configuration](#configuration)
- [Command reference](#command-reference)
- [Obsidian views](#obsidian-views)
- [Manual input and watchlists](#manual-input-and-watchlists)
- [Archiving](#archiving)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Other documents](#other-documents)

## How the pipeline works

One refresh runs five stages, in this order:

1. Check the configuration.
2. Collect every enabled source into memory.
3. Reconcile the rows and choose one owner for each note path.
4. Write the notes that changed.
5. Apply archive and retention rules to unproduced and duplicate notes.

A source error stops the run before the first note write. A failed fetch reuses a valid
cached response. `--offline` reads only the cache and stops at the first miss.

### Sources

CFP Tracker reads several public CFP feeds and datasets, plus every manual file under `input/`.
When two sources describe the same CFP, the pipeline keeps one note.

See [`docs/sources/README.md`](sources/README.md) for the source list, priorities, field mappings, and
attribution.

### Note paths

The pipeline writes one note per CFP at `data/<year>/<close-date>_<name>.md`.

- `<year>` comes from `cfp_close`, then `event_date`.
- `<close-date>` is the `cfp_close` value, or the event date when the source gives no close date.
- `<name>` is the lowercased event name with punctuation replaced by hyphens.

A deadline change moves the note to a new path. The reconciler migrates the user state to
the new path first, and archives the old note after that.

## Note format

A note is YAML frontmatter, then a `## Notes` body. Notes live in the body only. There is
no `notes` frontmatter key.

```md
---
type: cfp
event_name: Cloud Native AI Summit - EUROPE 2026
event_date: 2026-12-01
event_type: summit
location: CNIT Forest, Paris, France
country: France
cfp_close: 2026-10-31
topics: [cloud-native, artificial-intelligence, infrastructure, platform-engineering, architecture, ai, cloud, devops, kubernetes]
event_url: https://www.cloudnative.ai
cfp_url: https://sessionize.com/cloud-native-summit-europe-2026/
source: open-tech-cfps
shortlist: false
dismissed: false
submissions: []
created: 2026-11-02T00:00:00
updated: 2026-11-12T00:00:00
tier: 1
---

## Notes

_Add notes here._
```

### Fields

| Field | Written by | Notes |
|---|---|---|
| `type` | pipeline | Always `cfp`. |
| `event_name` | source | The legacy `name` key is a fallback. The pipeline removes it on rewrite. |
| `event_date` | source | Start date as `YYYY-MM-DD`, or `TBA`. |
| `event_type` | pipeline | Inferred once, then kept. One of `conference`, `summit`, `workshop`, `meetup`, `hackathon`, `webinar`, `other`. |
| `location` | source | Free text, usually `City, ST (Country)`. |
| `country` | source | Canonical value: `USA`, `UK`, `Online`, or a country name. |
| `cfp_close` | source | Deadline. The source may give free text when it has no date. |
| `topics` | source | Merged with the existing list, never replaced. |
| `benefits` | source | Optional. `travel`, `hotel`, `honorarium`. Replaced on update. |
| `languages` | source | Optional. Lowercased and merged. |
| `event_url` | source | Conference site. The pipeline removes tracking parameters. |
| `cfp_url` | source | Submission page. The pipeline removes tracking parameters. |
| `source` | source | Source name from the registry. |
| `shortlist` | you | Marks an event you want. Kept across refreshes. |
| `dismissed` | you | Hides an event from live views. Kept across refreshes. |
| `submissions` | you | Wiki links to your talk submissions. |
| `curated_fields` | you | Source fields that your value owns. |
| `created` | pipeline | First time the note appeared. Never changes. |
| `updated` | pipeline | Advanced only when a source value changes. |
| `conflict` | pipeline | `true` when a curated value and a source value disagree. |
| `replaces` | pipeline | Paths of duplicate notes merged into this note. |
| `tier` | `apply-prestige.py` | `1` flagship, `2` major, `3` notable. |

### What survives a refresh

The refresh rebuilds every source field. It keeps everything else:

- `shortlist`, `dismissed`, `submissions`, `curated_fields`.
- The `## Notes` body.
- Any extra frontmatter key you add, such as `priority` or `contact`.

A note rewrites only when a source value actually changed. An unchanged refresh leaves the
file and its modification time alone.

The writer uses a temporary sibling and an atomic replacement for changed notes. A failed write
keeps the previous contents.

A name or deadline revision updates and renames the existing note. It creates no archived
predecessor and adds no `replaces` entry. A duplicate merge preserves user curation and records
the archived duplicate in `replaces`.

### Curated fields and conflicts

Add a source field to `curated_fields` to keep your own value:

```yaml
curated_fields: [location]
```

When the source disagrees, the note keeps your value, sets `conflict: true`, and adds a
`## Conflict` section that names the field and both values. The conflict clears when the
source matches again or the field leaves `curated_fields`.

The **Conflicts** view in `cfps.base` lists notes with `conflict: true`.

### Timestamps

`created` and `updated` are pipeline stamps, not source data.

- The pipeline writes both stamps from the run date.
- An existing note keeps `created`. `updated` advances only on a real source change.
- The pipeline keeps a hand-typed valid stamp.
- The pipeline fills in a missing or invalid stamp without counting an update.

## Configuration

`src/config.py` holds the tracked defaults. Personal settings belong in
`src/config_local.py`, which is gitignored.

```bash
cp src/config_local.example.py src/config_local.py
```

The local file replaces only the settings it defines. An unknown setting name fails the
run. A syntax error in the local file also fails the run, so a typo cannot silently revert
to a default.

| Setting | Default | Effect |
|---|---|---|
| `INPUT_SOURCES` | All seven sources | Sources to fetch. Remove a source to skip it. Its notes stay in `data/`. |
| `CONFS_TECH_TOPICS` | `devops`, `opensource`, `python`, `ai` | Topic files to read from confs.tech. `general` is always included. An empty set reads every topic. |
| `EVENT_TYPES` | `conference`, `summit`, `workshop` | Event types to keep. The pipeline archives the other notes. |
| `EVENT_TYPE_KEYWORDS` | Meetup, summit, workshop, hackathon, webinar aliases | Name patterns used to infer `event_type`. Order sets precedence. |
| `IGNORE_NAMES` | `[]` | Event names to drop. Matches anywhere in the name, ignoring case. |
| `IGNORE_TOPICS` | `[]` | Topics or names to drop. |

`INPUT_SOURCES`, `EVENT_TYPES`, and `CONFS_TECH_TOPICS` must be nonempty collections of
nonempty strings. The two ignore lists also require strings, but they accept an empty value.
An invalid value stops the run before any source fetch.

Example:

```python
INPUT_SOURCES = ["developers.events", "cfp.ninja", "manual"]
EVENT_TYPES = ["conference", "summit"]
IGNORE_NAMES = [".NET"]
```

## Command reference

### Refresh

```bash
uv run python src/process-all.py
```

| Option | Default | Effect |
|---|---|---|
| `--out DIR` | `data` | Notes directory. |
| `--input DIR` | `input` | Directory for manual input files. |
| `--archive DIR` | `archived` beside `--out` | Archive directory. |
| `--no-archive` | off | Do not archive any note. Canonical revision renames still occur. |
| `--today YYYY-MM-DD` | Today | Run date. Reproduces a past run. |
| `--months-back N` | `3` | Source window and archive retention in 30-day units. The default is 90 days. |
| `--past-days N` | `30 × months-back` | Source window and archive retention in days. Also `--days-back`. Overrides `--months-back`. |
| `--cache DIR` | `cache/` | HTTP cache directory. |
| `--offline` | off | Read the cache only. No network access. |
| `--prestige FILE` | `prestige.md` | Ranking table. |
| `--no-prestige` | off | Do not stamp `tier`. |
| `--help` | | List every option. |

The run prints a per-source summary and an event-type matrix. Eligible source-missing notes stay
live while their ISO deadline is on or after the cutoff. Exclusions and duplicate matches still
allow archiving.

### Utility scripts

| Script | Purpose |
|---|---|
| `src/check-links.py PATH [--only TEXT] [--workers N] [--timeout S]` | Check CFP and event URLs. Only `404` and `410` count as dead. |
| `src/normalize-data.py [--data DIR]` | Re-emit existing notes in the current shape. Safe to repeat. |
| `src/apply-prestige.py [--data DIR] [--list FILE] [--check]` | Stamp `tier` from the ranking table. `--check` writes nothing. |
| `src/sync-submission-links.py [--data DIR] --submissions DIR [--check]` | Add missing submission wikilinks to CFP notes. `--check` writes nothing. |
| `src/archive-orphans.py [--data DIR] [--archive DIR] [--dry-run] [--json]` | Move notes that no source produces. `--skip-source NAME` protects one source. `--retain-after YYYY-MM-DD` enables rolling-window retention. |

Each source also has a standalone adapter, for example
`uv run python src/process-confs-tech.py`. An adapter command reconciles on its own and
treats every other source as paused.

### Submission synchronization

Each submission note must use `type: submission` or `type: talk-submission`. Its `cfp` property must contain a CFP wikilink. A list of CFP wikilinks also works.

Preview additions with:

```bash
uv run python src/sync-submission-links.py --data data --submissions /path/to/vault/submissions --check
```

Apply additions with:

```bash
uv run python src/sync-submission-links.py --data data --submissions /path/to/vault/submissions
```

The command follows these rules:

- Scan CFP notes below `--data`. The default is `data`.
- Resolve filename and path wikilinks, including aliases, headings, and optional `.md` extensions.
- Keep every existing `submissions` entry and append only missing links in deterministic order.
- Change only `submissions` when a CFP gains links. Do not change submission notes or CFP timestamps.
- Report unresolved, ambiguous, missing, and malformed references without guessing.
- Return `1` when any reference needs attention. Return `2` for missing directories or write failures.

The command is additive. Removing or retargeting a submission does not remove its old CFP link. Remove stale links manually. Adding links rewrites `submissions` as a flow list, but preserves unrelated frontmatter and body bytes.

Run synchronization before `process-all.py` after submissions change. A later refresh preserves the links. Synchronizing first also avoids unresolved links when a source revision renames the CFP file.

## Obsidian views

The [`obsidian/dashboard/`](../obsidian/dashboard/) folder contains these assets:

| Asset | Contents |
|---|---|
| [`cfps.base`](../obsidian/dashboard/cfps.base) | CFP discovery and tracking views. |
| [`talks.base`](../obsidian/dashboard/talks.base) | All talks and ready talks. |
| [`submissions.base`](../obsidian/dashboard/submissions.base) | All submissions, pending reviews, and accepted submissions. |
| [`cfps-dashboard.md`](../obsidian/dashboard/cfps-dashboard.md) | Dataview CFP summary tables. |

Copy the assets you use into the vault. The bases need the Obsidian Bases core plugin. The dashboard needs the Dataview plugin.

`talks.base` filters notes with `type: talk`. `submissions.base` supports `type: submission` and `type: talk-submission`.

### CFP views

| Group | Views |
|---|---|
| Find | Search, All, Recently Updated, Prestigious, Short listed, Submitted, Conflicts |
| Time | Upcoming (> today), Upcoming (> -30 days), Closed (90d) |
| Place | Location - My Country, Outside My Country, Online, My Local Area |
| Hidden | Dismissed, Archived |

Most groups have a `(+dismissed)` and a `(-dismissed)` variant. Short listed and
Submitted show both kinds of note.

### CFP formulas

`cfps.base` keeps the personal values in one place.

| Formula | Purpose |
|---|---|
| `data_dir`, `archived_dir` | Note folders. The match is a path suffix, so a nested vault works. |
| `my_country` | Country value used by the My Country views. |
| `is_local_area` | List of `location.contains(...)` clauses for the local views. |
| `is_in_data`, `is_archived` | Folder tests. |
| `is_dismissed`, `is_live` | Dismissal tests. Every paired view uses these. |
| `is_prestigious` | `tier == 1` or `tier == 2`. |
| `cfp_title` | Link to the note, with the event name as the text. |
| `submission_count` | Number of entries in `submissions`. |

The dashboard groups notes by country, topic, and month. It reads `cfps/data`, so update
that path when your vault uses another one.

## Manual input and watchlists

The pipeline reads every file below `input/` recursively. It ignores `input/archived/`.
It follows directory symlinks and reads each directory once to avoid cycles.
Filename extensions do not limit processing. Every file must contain UTF-8 text.
Unreadable files or directories abort collection before note writes.

Move inactive files into `input/archived/`. Remove `manual` from `INPUT_SOURCES` to disable
manual input. Remove the obsolete `MANUAL_INPUT_FILES` setting from `src/config_local.py`.

A file can hold a table:

```md
| Conference | Location | CFP Close |
|---|---|---|
| **[Example Conf](https://example.com/)** | Berlin, Germany | Nov 2026 |
```

A file can also hold a checklist of event sites:

```md
- [Example Conf](https://example.com/)
```

The pipeline fetches each site and looks for a speaker-submission page. It reads structured
event metadata, keeps an unknown close as `Unstated`, and reports an entry it cannot
resolve instead of inventing values.

The pipeline does not add a submission page that states the CFP is closed. It skips a
parsed close before `--today`. With `--today`, a past run is reproducible.

## Archiving

A refresh moves a note to `archived/` when no current source produces it and no protection applies.

A note stays in `data/` when it has any of these:

- `shortlist: true`.
- An entry in `submissions`.
- Body notes you wrote.
- Extra frontmatter keys you added.

Rolling-window retention also keeps an eligible source-missing note in `data/`. Its ISO
`cfp_close` must be on or after the shared cutoff. The note must pass configured name, type, and
topic filters. A current note with the same CFP identity prevents retention. Merged duplicates
still archive. A free-text close receives no rolling-window protection.

A `tier` alone does not keep a note in `data/`. A moved file keeps its bytes. Identical live-and-archived
duplicates collapse by deleting only the live duplicate. Conflicting copies receive numbered `-collision-N.md` filenames. `--no-archive` disables the stage. Dry runs never delete duplicates.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| The run prints `source failed before note writes` | Network or source format change. | Check the URL in `cfps-sources.md`, then retry with the cache or `--offline`. |
| No notes appear in `data/` | Configuration error, missing symlink, or empty cache with `--offline`. | Read the error line. Check `ls -l data`. |
| A note shows `conflict: true` | Your curated value differs from the source. | Keep it, or remove the field from `curated_fields`. |
| `event_type` is wrong | The pipeline infers the type once, then keeps it. | Edit the note, or add an alias to `EVENT_TYPE_KEYWORDS` before the first write. |
| A source produced nothing | The source is missing from `INPUT_SOURCES`. | Add the name. |
| A manual file is ignored | The file is in `input/archived/`, or manual input is disabled. | Move the file outside `input/archived/`, or enable `manual` in `INPUT_SOURCES`. |
| A CFP link is dead | The hosting platform shut down. | Run `check-links.py`, then use the event URL. |

## Development

Run the tests:

```bash
uv run python -m unittest discover -s tests -v
```

The suite uses the standard library only. Fixtures under `tests/fixtures/` are real slices
of the downloaded data. Any change under `src/` must keep the suite passing.

### Repository layout

| Path | Contents |
|---|---|
| `src/process-all.py` | The refresh entry point. |
| `src/sources.py` | Source registry, priority, and run context. |
| `src/reconcile.py` | Chooses owners, revision renames, and duplicate merges before writes. |
| `src/cfp_writer.py` | Writes and refreshes one note per CFP. |
| `src/http_cache.py` | Online-first HTTP cache with offline fallback. |
| `src/process-*.py` | One adapter per source. |
| `src/check-links.py` | URL checker for note directories. |
| `src/prestige.py`, `src/apply-prestige.py` | Ranking table parser and stamper. |
| `data/`, `archived/` | Symlinks into the Obsidian vault. |
| `obsidian/dashboard/` | CFP, talk, and submission bases plus the CFP dashboard. |
| `obsidian/templates/` | CFP, talk, and submission templates. |
| `obsidian/talks/`, `obsidian/submissions/` | Example talk and submission notes. |
| `obsidian/cfps/data/` | Example CFP notes linked from the submissions. |
| `tests/` | Unit tests and fixtures. |

### Add a source

1. Write an adapter with `collect_rows(...)` that returns row dicts.
2. Register it in `SOURCE_SPECS` in `src/sources.py` with a name, a script, and a priority.
3. Add the name to `INPUT_SOURCES` in `src/config.py`.
4. Add a parser test with a real fixture slice.
5. Add a page under `docs/sources/` and a row in `docs/sources/README.md`.

## Other documents

| Document | Contents |
|---|---|
| [`../README.md`](../README.md) | Setup and first refresh. |
| [`docs/sources/README.md`](sources/README.md) | Source index, status, and attribution. |
| [`sources/`](sources/) | One note per source, with fields and traps. |
| [`spec.md`](spec.md) | Historical specification from 2026-11-09. Not current behavior. |
| [`../INSTRUCTIONS.md`](../INSTRUCTIONS.md) | The refresh procedure for an agent. |
| [`../AGENTS.md`](../AGENTS.md) | Data shapes and preservation rules. |
