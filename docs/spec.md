# CFP Tracker — Software Specification

- **Status:** Historical specification of an earlier implementation
- **Code snapshot inspected:** 2026-11-09 (`26eefb8`)
- **Current procedures:** [`INSTRUCTIONS.md`](../INSTRUCTIONS.md)
- **Current data contracts:** [`AGENTS.md`](../AGENTS.md)
**Primary implementation:** `src/`  
**Primary outputs:** `data/**/*.md`, `archived/**/*.md`, and the Obsidian views in `cfps.base` / `cfps-dashboard.md`

This document specifies the code at the snapshot above. It does not describe later reconciliation,
cache, watchlist, or archive changes. Use the current procedures and data contracts for new work.

## 1. Purpose and scope

CFP Tracker collects Calls For Papers (CFPs) from public conference sources, normalizes them, and maintains one Markdown note per selected source row. The notes are intended for an Obsidian vault, where they support browsing, filtering, shortlisting, submission tracking, and aggregate dashboards.

The system shall:

1. Read five external CFP sources and optional hand-curated Markdown input.
2. Select open and recently closed CFPs according to source-specific date rules.
3. Convert each selected record to a common row shape.
4. Create or refresh Markdown notes without overwriting user-managed content unnecessarily.
5. Resolve overlapping source records using source ownership and duplicate rules.
6. Record the notes produced by each source in a run manifest.
7. Move CFP notes no longer produced by any source from the live tree to an archive tree.
8. Expose the resulting notes through Obsidian Base views and Dataview dashboard queries.

### 1.1 In scope

- Source fetching, caching, parsing, filtering, and normalization.
- Per-CFP note identity, rendering, change detection, and preservation rules.
- Source precedence, duplicate handling, manifests, and orphan archiving.
- Full-run orchestration and command-line reporting.
- Note-tree normalization and link-liveness utilities.
- Obsidian Base and Dataview presentation behavior.
- Runtime requirements and verification expectations.

### 1.2 Out of scope

- Submitting a talk to a conference.
- Tracking CFP opening dates as note properties. Sources generally provide only deadlines, and no `cfp_open` note field exists.
- Scraping the rendered `developers.events` CFP page. Its JSON files are authoritative.
- Maintaining a relational database or a long-running service.
- Guaranteeing complete conference coverage or perfect real-world duplicate detection.
- Automatically committing or pushing changes.
- Retired single-file report generation, except where compatibility code still exists.

## 2. Terminology

| Term | Meaning |
|---|---|
| **Source row** | One normalized Python `dict` produced by a source adapter. |
| **CFP note** | A Markdown file with `type: cfp` and the common frontmatter/body schema. |
| **Live tree** | The recursively scanned Markdown tree under `data/` by default. |
| **Archive tree** | The parallel destination under `archived/` by default. |
| **Source-owned property** | A note property regenerated from the current source row. |
| **User-owned content** | `shortlist`, `dismissed`, `submissions`, body notes, and additional frontmatter properties. |
| **Produced path** | A note path recorded by a source as current during a run. |
| **Orphan** | A parseable `type: cfp` Markdown note in the live tree whose relative path is absent from every produced manifest. |
| **Run date** | The actual current local date used by the writer for `created` / `updated`, unless the writer function is called directly with a test override. |
| **Cutoff date** | The inclusive earliest CFP deadline accepted by a network source adapter. |

## 3. Architecture and storage

### 3.1 Components

| Component | Implementation | Responsibility |
|---|---|---|
| Full pipeline | `src/process-all.py` | Run adapters, collect summaries, invoke archiving. |
| developers.events adapter | `src/process-developer-events.py` | Fetch CFP/event JSON, enrich CFPs with event data, emit common rows. |
| cfp.ninja adapter | `src/process-cfp-ninja.py` | Paginate the public API and map events, tags, and benefits. |
| confs.tech adapter | `src/process-confs-tech.py` | Fetch topic/year JSON from the community conference-data repository. |
| Adato adapter | `src/process-adato-tracker.py` | Parse the eight-column `tablesorter` HTML table. |
| Open Tech CFPs adapter | `src/process-open-tech-cfps.py` | Fetch open/closed JSON, normalize UTC deadlines and ISO countries, deduplicate records. |
| Manual adapter | `src/process-manual-input.py` | Parse curated Markdown tables under `input/`. |
| Shared writer | `src/cfp_writer.py` | Normalize values, determine note paths, deduplicate, preserve user data, and write notes/manifests. |
| Country normalizer | `src/country.py` | Canonicalize aliases and resolve ISO alpha-2 country codes through pycountry. |
| Orphan archiver | `src/archive-orphans.py` | Move unproduced CFP notes to the archive tree. |
| Shape normalizer | `src/normalize-data.py` + `cfp_writer.normalize_file` | Re-emit existing notes in the current shape. |
| Link checker | `src/check-links.py` | Concurrently check HTTP links extracted from a Markdown report. |
| Compatibility shim | `src/build-open-cfps.py` | Delegate to `process-developer-events.py`. |
| Configuration | `src/config.py` + gitignored `src/config_local.py` | Tracked defaults plus validated personal overrides; `config_local.example.py` is the template. |
| Discovered topics | `src/discovered-topics.txt` | Generated reference list of confs.tech topic files; not used for extraction. |
| Obsidian artifacts | `cfps.base`, `cfps-dashboard.md` | Browse and aggregate notes. |

### 3.2 Repository and vault boundary

Code and support files live in this repository. In the intended installation:

- `data` is a relative symlink to the Obsidian vault's `cfps/data/` directory.
- `archived` is a relative symlink to the vault's `cfps/archived/` directory.
- Both symlinks are gitignored.
- A refresh therefore edits notes in the vault in place.

These symlinks must not be replaced with ordinary directories. On a fresh clone they are created during setup:

```bash
ln -s /path/to/your-vault/cfps/data data
ln -s /path/to/your-vault/cfps/archived archived
```

The code does not require the output directory to be a symlink. `--out DIR` can target another directory for isolated execution or testing.

### 3.3 Processing model

The application is a sequential batch pipeline, not a transaction:

1. Fetch or read cached source data.
2. Filter and normalize source records.
3. Upsert each row immediately.
4. Write the source's manifest.
5. After all selected source processes succeed, archive orphans.
6. Print a combined summary.

A later failure does not roll back notes already written by an earlier source. Archiving is skipped when a source subprocess exits nonzero.

## 4. End-to-end refresh specification

The normal entry point is:

```bash
uv run python src/process-all.py
# or
python3 src/process-all.py
```

### 4.1 Source execution order

`process-all.py` runs adapters in this order:

1. `developers.events`
2. `cfp.ninja`
3. `confs.tech`
4. `adato-tracker`
5. `open-tech-cfps`
6. `manual input`, but only when the configured input directory exists

Each adapter runs in a separate subprocess using the same Python interpreter as the wrapper. The wrapper captures and relays standard output and standard error. It stops at the first nonzero exit and returns that exit code.

### 4.2 Source precedence

The writer defines ownership priority, from highest to lowest:

```text
manual > developers.events > cfp.ninja > confs.tech > adato-tracker > open-tech-cfps > unknown sources
```

This is whole-note ownership, not field-by-field merging:

- A lower-priority source must not overwrite an existing higher-priority note at the same path.
- A higher-priority source may replace all source-owned properties of a lower-priority note.
- A winning source can replace richer values with blank values if its normalized row is blank.
- `source` identifies the current owner after a successful write.

### 4.3 Full-run command options

`process-all.py` directly recognizes:

| Option | Default | Behavior |
|---|---|---|
| `--out DIR` | `data` | Live note directory; resolved to an absolute path. |
| `--input DIR` | `input` | Manual input directory. Manual processing is omitted if it does not exist. |
| `--archive DIR` | sibling `archived/` beside resolved `--out` | Destination for orphan notes. |
| `--no-archive` | false | Skip orphan archiving after source processing. |

Unrecognized arguments are collected and forwarded **only** to `process-developer-events.py`. They are not global options for the other adapters. See [§17.2](#172-cutoff-and-option-forwarding-are-not-uniform).

### 4.4 Manifests

The wrapper creates temporary manifest paths for all six sources and supplies those paths to each adapter that runs. After all source steps succeed, it invokes the archiver with all six manifest paths, including manifests for sources that did not run.

Each manifest is a UTF-8 JSON array containing sorted, deduplicated note paths:

- Relative to that run's resolved data directory.
- In POSIX form, including nested/year path components.
- Including paths for `new`, `updated`, and `unchanged` rows.
- Excluding paths for `skipped` rows.

Example:

```json
[
  "2026/2026-12-18_dutch-ai-conference.md",
  "2027/2027-01-15_pytexas-2027.md"
]
```

### 4.5 Run summary

Each adapter emits exactly one parseable summary line:

```text
<source>: found N (new N, updated N, unchanged N)
```

Adapters fold internal `skipped` results into displayed `unchanged`, so:

```text
found = new + updated + reported unchanged
```

The displayed summary therefore does not reveal how many rows yielded to another owner or were skipped for malformed frontmatter.

The wrapper:

- Parses only lines matching that exact shape.
- Sums `found`, `new`, `updated`, and `unchanged` across sources.
- Reports the number of all `*.md` files physically under the data directory.
- Reports the archived count only when nonzero.
- Resolves and validates the configured included types before starting any source or archive subprocess. Invalid or empty configuration stops the wrapper before those steps.
- After the archive step, prints a source × event-type matrix for parseable `type: cfp` notes in the live data directory. Counts use stored `source` and `event_type`; a missing type is inferred from the stored name. The `manual` source appears as `manual input` to match its adapter summary, and unknown sources/types are retained as extra rows/columns.
- Appends ★ to every type enabled by the validated `EVENT_TYPES` allow-list. The matrix includes all supported type columns and a Total row.

Totals are source-row totals, not counts of unique real-world conferences. The on-disk count is not restricted to valid `type: cfp` notes. In contrast, the event-type matrix counts parseable CFP notes only and reflects post-deduplication, post-archive ownership, so it can differ from either total.

## 5. Common normalized row

Every source adapter passes a mapping with these logical fields to the shared writer:

| Field | Type | Required by common shape | Notes |
|---|---|---:|---|
| `name` | string | Yes in rendered output | Conference or CFP name. Some adapters reject empty names. |
| `event_date` | string | Yes | Usually start date as `YYYY-MM-DD`, `TBA`, or source-specific fallback text. |
| `event_type` | string | Writer-managed | Inferred when new/unset; an existing nonempty value is preserved. Current sources provide no standardized event-kind value. |
| `location` | string | Yes | Display location; some sources use `—` when unknown. |
| `country` | string | Yes | Canonicalized by the writer; empty means unknown. |
| `cfp_close` | string | Yes | Usually `YYYY-MM-DD`; manual input may be free text, `—`, or `Unstated`. |
| `topics` | list of strings | Yes | Always rendered; defaults to `[]`. On refresh, incoming values merge into the existing list rather than replacing it. |
| `benefits` | list of strings | Optional | Rendered only when nonempty. cfp.ninja supplies it, and Open Tech CFPs supplies explicit travel/hotel coverage. |
| `languages` | list of strings | Optional | Rendered only when nonempty. developers.events currently supplies it. |
| `event_url` | string | Yes | Event website, or empty. UTM parameters are removed. |
| `cfp_url` | string | Yes | Submission/CFP page, or empty. UTM parameters are removed; also used for duplicate matching. |
| `source` | string | Yes | Normally `manual`, `developers.events`, `cfp.ninja`, `confs.tech`, `adato-tracker`, or `open-tech-cfps`. |

The common row's `name` field becomes `event_name` in note frontmatter. Other scalar field names stay unchanged.

Intermediate source values such as developers.events `durations`, `misc`, `online`, `flag`, and `focus` do not become note properties.

## 6. CFP note specification

### 6.1 Canonical rendered shape

A generated note has the following shape and property order:

```markdown
---
type: cfp
event_name: Example Conference 2027
event_date: 2027-04-01
event_type: conference
location: Pasadena, CA (USA)
country: USA
cfp_close: 2026-11-01
topics: [ai, agents]
benefits: [travel, hotel]
languages: [english]
event_url: https://example.com/
cfp_url: https://example.com/cfp
source: developers.events
shortlist: false
dismissed: false
submissions: []
created: 2026-11-06
updated: 2026-11-06
---

## Notes

_Add notes here._
```

`benefits` and `languages` are omitted when empty. Additional user properties, when present, are appended after `updated` and before the closing frontmatter delimiter.

### 6.2 Property ownership

The following scalar properties are source-owned and semantically compared on refresh:

- `event_name`
- `event_date`
- `location`
- `country`
- `cfp_close`
- `event_url`
- `cfp_url`
- `source`

`benefits` is source-owned and compared as an order-sensitive list, replaced on every rewrite. `topics` and `languages` are source-owned and order-sensitively compared too, but only after their incoming source values have been merged into the existing lists as specified in §6.4. They are cumulative rather than replace-on-refresh.

`event_type` is writer-managed sticky metadata, not a source-owned scalar: it is inferred when unset and preserved thereafter as specified in §6.7. It does not participate in `_source_props_match`.

`type: cfp` is fixed whenever the writer renders a note. It is not part of the source-property comparison.

### 6.3 User-managed content

The following content survives a genuine source-driven rewrite:

- `shortlist`, normalized to a bare YAML `true` or `false`.
- `dismissed`, also normalized to a bare YAML Boolean and defaulting to `false` when missing.
- `submissions`, emitted as a flow list; values are conventionally Obsidian wiki links.
- Free-form body notes under `## Notes`.
- Additional top-level frontmatter properties such as `priority`, `tags`, or a nested `contact` map.

Additional properties are copied as raw top-level YAML lines plus indented continuation lines. This preserves nested maps and block lists in supported layouts, but it is not a guarantee that every comment, anchor, blank line, or arbitrary YAML construction survives byte-for-byte during a rewrite.

User edits alone do not trigger a source refresh write. When source fields are unchanged, both stamps are valid, and `dismissed` is present, the entire file is left untouched. A missing `dismissed` flag back-fills to `false` without advancing valid stamps.

### 6.4 List merging: topics and languages

`topics` and `languages` are cumulative across refreshes. Before comparing or rendering a note, the writer computes each desired list as follows:

1. Read the existing list through the same YAML-to-list normalization used for other list fields.
2. Keep that existing list unchanged as the prefix, including hand-added values, source values that disappeared upstream, existing order, and any existing duplicates.
3. Process incoming source values in their supplied order and append each value not already present.
4. Match values case-insensitively (`English` and `english` are the same value; the existing or first-seen spelling wins). Incoming duplicates are appended only once. `languages` values are additionally case-folded before the merge, so the note always stores them lowercase.

The merged list, rather than the raw incoming list, is used for source-property comparison and rendering. For a new note, there is no existing prefix, so the result is the incoming source values deduplicated in first-seen order.

This produces the following refresh behavior:

- A hand-added topic or language does not trigger a rewrite and is not removed.
- A source removing or reordering topics or languages does not remove or reorder the note's values and does not alone trigger a rewrite.
- A source contributing no topics or languages leaves the existing lists intact.
- At least one genuinely new incoming value changes the desired list, so the note is rewritten and `updated` advances to the run date.
- The next refresh with the same incoming values is `unchanged`; bytes, mtime, and both stamps remain untouched.
- A capitalised `languages` value (`English`) is case-folded on the next write, so an old note is rewritten lowercase exactly once and is then stable; capitalization-only changes never append a near-duplicate.
- When another source property also changes, the same merge rules apply during that rewrite.

`benefits` is the exception among list fields: it is replaced outright on every rewrite and follows the plain §6.2 comparison.

### 6.5 Defaults, parsing, and legacy migration

- New notes default to `shortlist: false`, `dismissed: false`, and `submissions: []`.
- `shortlist` and `dismissed` values `true`, `yes`, `on`, and `1`, case-insensitively after string conversion, normalize to true; other values normalize to false.
- Existing `submissions` may be a block list, flow list, or scalar. A nonempty scalar becomes a one-element list.
- Legacy scalar `submission` is used only when `submissions` is absent, and migrates to `submissions` on the next rewrite.
- Legacy `name` populates `event_name` when `event_name` is empty. The next rewrite removes `name`. This shape migration does not advance a valid `updated` stamp.
- Legacy `conf_date` can populate `event_date` during normalization only when `event_date` is empty; the legacy key is not re-emitted.
- Leading repeated Notes headings and placeholder lines are collapsed when body notes are extracted.
- An empty body is replaced with `_Add notes here._`.

### 6.6 YAML handling and safety

Frontmatter must begin with `---` on the first line and end with a `---` delimiter. The writer parses the whole block with `yaml.safe_load` and requires a mapping.

Consequences:

- YAML dates, booleans, lists, quoted strings, nested maps, and nulls retain their parsed types until normalized by writer helpers.
- ISO date strings may therefore be read back as `datetime.date` values and converted to ISO strings for comparison.
- Rendering uses `_yaml_str` and `_yaml_list`; frontmatter must not be assembled by concatenating unescaped source values.
- Empty strings are rendered as `""`; strings requiring quoting use JSON-compatible double quotes.
- `shortlist` is emitted as a boolean rather than a quoted string.

If a target note contains invalid YAML or non-mapping frontmatter:

1. The writer prints a warning to standard error.
2. Returns `skipped`.
3. Leaves the file bytes unchanged.
4. Does not record that path as produced.

A file with no frontmatter is not protected by that rule; a colliding path can be regenerated as a CFP note, and its old body is not guaranteed to survive.

### 6.7 Event type classification and preservation

`event_type` classifies the event independently of `type: cfp`, which identifies the note itself. The supported controlled values exposed by `EVENT_TYPES` are:

```text
conference | meetup | summit | workshop | hackathon | webinar | other
```

After type resolution, a nonempty allow-list in `config.EVENT_TYPES` determines whether the note belongs in live data. When that setting is absent, the writer's fallback includes every controlled value except `meetup`; the checked-in configuration currently enables `conference`, `summit`, and `workshop` and leaves other supported types commented for opt-in. A project owner can set `["conference", "summit"]` to retain only those types. Values are trimmed and lowercased. Empty lists, non-string values, and names outside the supported set raise `ValueError` before ingestion rather than enabling an accidental broad archival. A disallowed row returns `skipped`, produces no note, and causes an existing note of that type to be archived because it is absent from manifests. An explicit sticky override is retained only when its type is allowed.

Current external sources do not expose a standardized event-kind property. The writer therefore resolves a new or unset event type as follows:

1. If existing frontmatter has a nonempty `event_type`, use that value and do not re-infer it. A trimmed value is re-rendered when another change rewrites the note.
2. Otherwise, if an incoming common row explicitly supplies a nonempty `event_type`, use it. This supports curated/programmatic callers even though current adapters do not supply one.
3. Otherwise, call `infer_event_type(name)`, which reads the ordered `EVENT_TYPE_KEYWORDS` mapping from `src/config_local.py` overrides or the defaults in `src/config.py`. Valid keys are `meetup`, `summit`, `workshop`, `hackathon`, and `webinar`. Each value is a nonempty list of singular phrase aliases. Matching is case-insensitive and word-bounded. Spaces and hyphens between alias words are interchangeable, and a trailing plural `s` is optional. Mapping order controls precedence. The checked-in aliases preserve the default meet-up and user-group variants.
4. If no keyword matches, default to `conference`. `other` is available for manual/source curation but has no inference aliases. Neither `conference` nor `other` is a valid keyword-mapping key.

Missing configuration falls back to built-in default aliases. A non-mapping setting, an unknown key, a non-list value, an empty list, or a blank/non-string alias raises `ValueError`. A change to aliases affects new and unset types only; existing values remain sticky.

Once a value exists, it is sticky:

- A manual override does not itself trigger a rewrite and survives later source-driven updates.
- A changed incoming `event_type` does not replace an existing note's value.
- A missing/blank value back-fills on `upsert` or `normalize_file`.
- A backfill-only refresh can return `updated` because bytes changed, but valid `created` and `updated` stamps remain unchanged. A simultaneous real source-property change advances `updated` normally.
- The next refresh with a present value is `unchanged` when all source properties and stamps are otherwise current.

## 7. Note identity and path rules

### 7.1 Slug

`slugify(name, cfp_close, event_date)`:

1. Lowercases the name and replaces each run of characters outside ASCII `[a-z0-9]` with `-`.
2. Trims leading/trailing `-`.
3. Prefixes the first ten characters of `cfp_close`, or then `event_date`, when that prefix begins with `YYYY-MM-DD`.
4. Otherwise uses a `20xx` year found first in the name, then in the event date.
5. Falls back to an unprefixed slug, or `cfp` when the slug is empty.

Examples:

```text
PyTexas 2027 + cfp_close 2027-01-15
→ 2027-01-15_pytexas-2027

Example + no parseable date or year
→ example
```

### 7.2 Directory

`note_path(data_dir, row)` returns:

```text
<data_dir>/<year>/<slug>.md
```

The year is selected as follows:

1. The first four characters of `cfp_close`, or then `event_date`, when they form a four-digit string.
2. Otherwise a `20xx` year found in event date or CFP close.
3. Otherwise `misc`.

Full example:

```text
data/2027/2027-01-15_pytexas-2027.md
```

Parent directories are created by `upsert`.

### 7.3 Identity-change behavior

A changed conference name, deadline, or fallback year can select a different note path. The writer creates or updates the new path; it does not rename the old file or migrate user metadata between paths. The old path may subsequently be archived if no source produces it.

## 8. Upsert, change detection, and timestamps

### 8.1 Status values

`cfp_writer.upsert(data_dir, row, today=None)` returns one of:

| Status | Meaning |
|---|---|
| `new` | A note did not previously exist at the target path and was written. |
| `updated` | An existing file was rewritten. This includes source changes and stamp-only backfills that change bytes. |
| `unchanged` | Source properties match and both stamps have valid date shape; no write occurred. |
| `skipped` | The resolved type is excluded by `config.EVENT_TYPES`, a higher-priority owner or URL duplicate wins, or target frontmatter is invalid. |

The optional `today` argument is a function-level testing/reproduction override. Production adapters call `upsert_counted` without it.

### 8.2 Pre-write normalization

Before path comparison or rendering, the writer:

1. Canonicalizes `country` with `normalize_country`.
2. Removes `utm_*` query parameters from `cfp_url`.
3. Removes `utm_*` query parameters from `event_url`.
4. After reading existing frontmatter, preserves a nonempty `event_type` or infers/backfills a missing one according to §6.7.
5. Merges incoming topics and languages into the existing lists according to §6.4.

After resolving `event_type` but before cross-path URL matching, the writer rejects any type excluded by the validated `config.EVENT_TYPES` allow-list. The subsequent merge steps apply only to retained types.

Thus spelling or tracking-parameter-only differences must not force repeated rewrites. Event-type edits alone do not force a rewrite. A genuinely new topic or language triggers a rewrite; source values removed or reordered upstream and user additions do not. Other source-owned properties retain their normal replacement semantics.

### 8.3 No-op invariant

A note is `unchanged` only when:

- Its frontmatter parses.
- `event_type` is nonempty; its actual value need not equal a new inference because existing values are sticky. A missing value backfills instead of taking the no-op path.
- Every source-owned scalar equals the normalized incoming value after YAML type normalization.
- `benefits` equals its incoming list, including item order.
- `languages` equals the case-folded cumulative merge of existing and incoming languages, so user additions, upstream removals, upstream reordering, and capitalization-only changes alone do not force an update.
- `topics` equals the cumulative merge of existing and incoming topics, so user additions, upstream removals, and upstream reordering alone do not force an update.
- Both `created` and `updated` match `^\d{4}-\d{2}-\d{2}$`.

When those conditions hold:

- No write occurs.
- File bytes remain unchanged.
- File modification time remains unchanged.
- User edits and harmless YAML formatting differences remain untouched.

Quoted versus unquoted scalars and block versus flow lists do not alone trigger an update. Stamp validity is format-only; impossible dates with the same textual shape pass this check.

### 8.4 Source updates and write avoidance

When a source-owned value differs, including when the cumulative topic merge adds at least one new topic:

- `created` is preserved or backfilled.
- `updated` becomes the run date.
- The note is rendered in canonical shape.
- User-managed content is retained according to §6.3.
- The write occurs only if rendered text differs from current bytes.

When source properties match but a stamp is missing or malformed, the writer backfills the stamp and may return `updated` because an existing file was rewritten. This is not treated as a new source-data change for purposes of advancing the `updated` property.

### 8.5 Timestamp semantics

| Situation | `created` | `updated` |
|---|---|---|
| New note | Run date | Run date |
| Real source property change | Existing value preserved | Run date |
| No-op refresh | Unchanged | Unchanged |
| Missing `event_type` backfill only | Preserved | Preserved when valid |
| Only `created` is valid, stamp-only backfill | Preserved | Copy `created` |
| Only `updated` is valid, stamp-only backfill | Copy `updated` | Preserved |
| Both missing/invalid | Run date | Run date |
| Normalization with both valid | Preserved | Preserved |

A stamp-only refresh does not falsely reset first-seen time to after last-update time. However, source adapters' `--today` options control source cutoff selection, not these writer timestamps; production stamps still use the actual current date.

## 9. Duplicate detection and source ownership

There are two independent mechanisms: same-path ownership and cross-path CFP URL matching.

### 9.1 Same-path ownership

After parsing the target path:

- If the existing note's `source` has strictly higher priority than the incoming row, the incoming row is `skipped`.
- If the incoming source has equal or higher priority, normal change detection and rendering proceed.
- Same-source/equal-source rows still use source-property comparison; priority does not make them automatically unchanged.

### 9.2 Cross-path CFP URL matching

A note may have a different slug but the same submission page. To detect this, the writer builds a lazy, per-process, per-data-directory index of existing parseable `type: cfp` notes keyed by normalized `cfp_url`, excluding notes whose `event_type` is disallowed by configuration. Those excluded notes cannot claim a URL against a replacement during the refresh that archives them. Successful writes are appended to the index during that process.

The duplicate URL key is derived by:

1. Stripping surrounding whitespace.
2. Removing `utm_*` query parameters.
3. Removing trailing slashes.
4. Lowercasing the complete URL.

An empty URL never matches.

The URL match is gated by name compatibility. Names are compatible when either:

- One name, lowercased and stripped to ASCII alphanumerics, contains the other; or
- One name's lowercase alphanumeric token set is a subset of the other's, ignoring tokens that are bare `19xx` or `20xx` years.

Examples that can match:

- `SCaLE` and `Southern California Linux Expo - SCaLE 24x`
- `DevFest Malta 2026` and `DevFest 2026 Malta`
- `Digital Crafts Day` and `Digital Crafts Day 2027`

Examples kept separate despite potentially sharing a form:

- `JS Poland` and `NG Poland`
- `Apidays Paris` and `Apidays London`
- `Appdevcon` and `Webdevcon`
- `HalfStack Phoenix` and `HalfStack Vienna`

For a compatible URL match at another path:

- A strictly higher-priority existing owner wins and the incoming row is `skipped`.
- An incoming strictly higher-priority source may write its note; the loser remains until archiving.
- On equal priority, the lexicographically lower path wins deterministically.
- Cross-path duplicate checking occurs before the unchanged short-circuit, allowing an existing losing note to stop claiming itself as current.

A skip never deletes or edits a losing note. With archiving disabled, duplicates can remain indefinitely.

### 9.3 Produced-path bookkeeping invariant

`upsert_counted` increments the counter corresponding to the returned status. It appends the computed note path to the produced list for every status except `skipped`.

A skipped row must not claim its path in the manifest. Otherwise a losing duplicate would remain permanently live and could never become an orphan.

### 9.4 Scope of deduplication

Deduplication is heuristic and path/source dependent. It does not guarantee one note per actual conference across:

- Different CFP URLs for the same event.
- Incompatible-looking names.
- Manual rows, which normally have empty `cfp_url`.
- Distinct events that happen to satisfy the name heuristic.
- Distinct editions collapsed by an adapter's own source-level deduplication.

## 10. Shared source selection and configuration

### 10.1 Recency window

Unless an adapter says otherwise, its standalone cutoff is:

```text
cutoff = today - 30 * max(1, months_back) days
```

A CFP deadline exactly equal to the cutoff is included. Values below one for `months_back` therefore behave as one.

A "month" is exactly 30 days, not calendar-month arithmetic.

The developers.events adapter alone also supports `--past-days N` / `--days-back N`, which overrides `months_back` without the minimum-one-month clamp.

Manual input has no recency filter.

### 10.2 Event-type allow-list

`config.EVENT_TYPES` is a nonempty collection of strings naming controlled types to retain in live data. If the setting is unavailable, the writer's fallback is:

```text
conference | summit | workshop | hackathon | webinar | other
```

The default configuration and local example enable `conference`, `summit`, and `workshop`; a user can add other supported types in `src/config_local.py`.

The writer validates and normalizes configured values on use. Unknown or empty values raise an error. Existing notes with excluded resolved types are absent from produced manifests and consequently archived, just like skipped duplicate paths.

### 10.3 Ignored terms

`src/config_local.py` can override two independent filters whose defaults in `src/config.py` are empty. The local example uses:

```text
IGNORE_NAMES = [.NET]
IGNORE_TOPICS = [bitcoin, crypto, frontend, javascript, mobile, dotnet]
```

`IGNORE_NAMES` is a central writer filter. Before note-path creation, event-type inference, or URL deduplication, `upsert` case-folds the event name and each configured literal fragment. Any substring match anywhere in the name returns `skipped`. It is not restricted to the start of the name, a word boundary, or a particular source. The row produces no note and no manifest entry, so an existing note can be archived normally. The example `.NET` fragment therefore matches both `.NET Conf` and `Azure .NET Developer Days`. An invalid non-list setting, a blank value, or a non-string value raises `ValueError` before that note can change.

Source adapters also reject configured `IGNORE_TOPICS` terms as follows:

| Source | Ignore matching behavior |
|---|---|
| developers.events | Case-insensitive substring in CFP conference name or any extracted topic. |
| cfp.ninja | Case-insensitive substring in event name or any parsed tag. |
| confs.tech | Case-insensitive substring in event name. |
| adato-tracker | Case-insensitive substring in event name. |
| open-tech-cfps | Case-insensitive substring in event name or any non-`untagged` tag. |
| Manual input | Case-insensitive substring in cleaned event name; manual topic text is not used for exclusion. |

Configuration import failures are broadly caught by adapters and result in no ignore list or confs.tech topic allowlist.

### 10.4 Country canonicalization

`normalize_country` trims the value, folds case/punctuation/whitespace for lookup, and maps known whole-value aliases to canonical labels. Unknown values are returned trimmed but otherwise unchanged. Empty input returns empty. Normalization is idempotent.

`country_name_from_alpha2` resolves ISO codes with pycountry and then applies the same aliases. `XK` maps to Kosovo; unknown two-letter codes and malformed values pass through rather than being replaced with invented countries.

| Canonical output | Representative accepted aliases |
|---|---|
| `USA` | `US`, `U.S.A.`, `United States`, `United States of America`, `America` |
| `UK` | `United Kingdom`, `Great Britain`, `Britain`, `GB`, `England`, `Scotland`, `Wales`, `Northern Ireland` |
| `Online` | `Virtual`, `Remote`, `Online Only`, `Virtual Event`, `Worldwide`, `Anywhere` |
| `Netherlands` | `The Netherlands`, `Holland`, `NL` |
| `United Arab Emirates` | `UAE`, `U.A.E.` |
| `Czechia` | `Czech Republic` |
| `South Korea` | `Korea`, `Republic of Korea` |
| `Ivory Coast` | `Cote d'Ivoire`, `Côte d'Ivoire` |
| `Turkey` | `Türkiye`, `Turkiye` |
| `Russia` | `Russian Federation` |
| `Vietnam` | `Viet Nam` |
| `Brazil` | `Brasil` |
| `Macedonia` | `North Macedonia` |
| `Swaziland` | `Eswatini` |

The function does not infer missing countries from arbitrary location text and does not validate unknown country names against a country database.

### 10.5 URL tracking cleanup

For both stored URL fields, `strip_utm`:

- Removes query parameters whose names begin with `utm_`, case-insensitively.
- Preserves non-UTM parameter order, encoding, `+` characters, and values.
- Preserves a `#fragment`.
- Removes the `?` when no parameters remain.
- Returns other strings unchanged apart from surrounding-whitespace trimming.
- Does not remove similarly named keys such as `myutm_source` or `utmx`.

## 11. Source adapter specifications

The adapter mapping tables below describe the incoming normalized source row. The shared writer subsequently applies the cumulative topic/language merge in §6.4 before comparison and note rendering.

### 11.1 developers.events

**Implementation:** `src/process-developer-events.py`  
**Source URLs:**

- `https://developers.events/all-cfps.json`
- `https://developers.events/all-events.json`

#### Input and caching

- Iterate CFP records from `all-cfps.json`; events without a CFP do not produce notes.
- `all-events.json` is enrichment data only.
- Fetch with `curl -fsSL -o <cache-file> <url>` on each run.
- Cache paths are `<cache>/all-cfps.json` and `<cache>/all-events.json`.
- If curl returns nonzero and a destination already exists, use that cached file.
- If curl returns nonzero and no destination exists, try `urllib.request.urlretrieve`.
- Parse the resulting files as JSON.

#### Filtering and deduplication

- Convert `untilDate` epoch milliseconds to a UTC date.
- Ignore records with missing `untilDate` or a deadline before the cutoff.
- Ignore the free-form `until` string for filtering.
- Ignore `conf.status`; historical records can claim to be open.
- Apply ignored-name/topic rules from §10.3.
- Deduplicate by `(normalized conference name, close date)`; the first row wins.
- Sort selected rows by `(close date, lowercase name)`.

A revised deadline can legitimately create a separate selected row because it has a different deduplication key and note path.

#### Event enrichment

Index events by lowercase alphanumeric-folded name. For CFPs with one or more same-name event candidates, select the best edition using:

1. Exact case/whitespace-normalized location match first.
2. Then an event date on or after the CFP deadline, minimizing positive date distance.
3. Otherwise the most recent prior edition, minimizing backward distance.
4. Events without dates rank after dated candidates within the same location class.

#### Note mapping

| Common field | Mapping |
|---|---|
| `name` | `conf.name` |
| `event_date` | Earliest date from matched event `date[]`, falling back to `conf.date[]`; otherwise `TBA`. |
| `location` | `conf.location`, falling back to matched event `location` when CFP location is empty. |
| `country` | Trailing parenthetical in final location, falling back to matched event `country`, then empty. |
| `cfp_close` | UTC date from `untilDate`, as ISO. |
| `topics` | Values of matched event tags whose key is `tech` or `topic`; deduplicated in first-seen order. |
| `languages` | Values of matched event tags whose key is `language`; omitted later when empty. |
| `event_url` | Matched event `hyperlink`, or empty. |
| `cfp_url` | CFP record `link`, or empty. |
| `source` | `developers.events` |

The trailing location parenthetical takes precedence because an upstream structured country can be wrong. A matched event's dates take precedence over CFP-conf dates. `conf.hyperlink` is not currently used as an event URL fallback.

#### Standalone CLI

Important options:

| Option | Actual default | Effect on notes |
|---|---|---|
| `--out` | `data` | Output directory. |
| `--today` | actual date | Base date for cutoff calculations only. |
| `--months-back` | **3** | Approximately 90 days by default; clamped to at least one unit. Help text claiming default 1 is stale. |
| `--past-days`, `--days-back` | unset | Explicit rolling-day cutoff overriding `--months-back`. |
| `--cache` | repository `cache/` | JSON cache directory. |
| `--manifest` | unset | Produced-path JSON output. |

`--focus-tags`, `--no-focus`, `--no-frontmatter`, and `--no-backup` remain in the CLI but do not change per-CFP note output. See §17.7.

### 11.2 cfp.ninja

**Implementation:** `src/process-cfp-ninja.py`  
**API:** `https://cfp.ninja/api/v0/events?per_page=100&page=N`  
**Submission page:** `https://cfp.ninja/e/<slug>`

#### Input and caching

- Request page 1 and continue through `pagination.total_pages`.
- Extend the result with each page's `data` list.
- Send User-Agent `cfp-merge/1.0` and Accept `application/json`.
- Use a 30-second request timeout.
- Prefer a readable JSON cache at `<cache>/cfp-ninja-events-<N>.json`.
- If cached JSON cannot be read or parsed, fetch the page and replace the cache.
- No cache expiration is implemented.

#### Filtering, mapping, and ordering

- Parse `cfp_close_at` by taking its leading ten characters as an ISO date; unreadable or missing dates are rejected.
- Ignore `cfp_status`.
- Require a nonempty trimmed event name.
- Include deadlines on/after cutoff.
- Apply ignored-name/tag rules.
- Split comma-separated `tags`, trim items, and discard empty items.
- Deduplicate by `(ASCII alphanumeric-folded lowercase name, close date)`.
- Sort by `(cfp_close, lowercase name)`.

| Common field | Mapping |
|---|---|
| `name` | Trimmed `name`. |
| `event_date` | Parsed `start_date`, otherwise `TBA`. |
| `location` | Trimmed `location`, falling back to country, then `—`. |
| `country` | Trimmed `country`; when empty and `is_online` is true, use `Online`. |
| `cfp_close` | Parsed `cfp_close_at`, as ISO. |
| `topics` | Parsed tags. |
| `benefits` | Ordered true flags: `travel`, `hotel`, `honorarium`. |
| `event_url` | `website`, or empty. |
| `cfp_url` | `https://cfp.ninja/e/<slug>` when a slug exists, otherwise empty. |
| `source` | `cfp.ninja` |

Standalone options are `--out`, `--today`, `--months-back` (default 1), `--cache`, and `--manifest`.

### 11.3 confs.tech

**Implementation:** `src/process-confs-tech.py`  
**Upstream repository:** `tech-conferences/conference-data`  
**Directory API:** `https://api.github.com/repos/tech-conferences/conference-data/contents/conferences`  
**Raw data:** `https://raw.githubusercontent.com/tech-conferences/conference-data/master/conferences`

#### Discovery and caching

For `today.year` and `today.year + 1`:

1. Fetch the GitHub directory listing for `conferences/<year>`.
2. Consider only items ending in `.json`.
3. Record the filename stem as a discovered topic.
4. Always include `general`; include other topics only when configured selection allows them.
5. Fetch `<year>/<topic>.json` and process list-valued data.

Selection uses `CONFS_TECH_TOPICS`, compared case-insensitively with underscores normalized to hyphens. When that set is empty, all discovered topic files are allowed. Year-listing and per-topic fetch errors are caught, printed to standard error, and skipped, allowing a partial result.

Readable JSON caches are preferred indefinitely:

- `confs-tech-listing-<year>.json`
- `confs-tech-<year>-<topic>.json`

Unreadable/invalid cached JSON triggers a network fetch. Requests use User-Agent `cfp-merge/1.0`, GitHub JSON Accept header, and a 30-second timeout.

After collection, the CLI writes the sorted discovered-topic list to `src/discovered-topics.txt` for reference. It does not rewrite Python source, and the discovered list is not itself used for extraction.

#### Filtering and deduplication

- Parse `cfpEndDate` as an ISO date or supported ISO datetime prefix.
- Reject missing/unparseable deadlines and deadlines before cutoff.
- Apply ignored-name rules.
- Deduplicate by normalized name **only**, across both years and all selected topic files; the first row wins.
- Do not apply an explicit final sort.

Unlike the other network adapters, two editions with the same normalized name but different deadlines are collapsed.

#### Note mapping

| Common field | Mapping |
|---|---|
| `name` | Event `name`. |
| `event_date` | Parsed `startDate`, otherwise `TBA`. |
| `location` | Nonempty `city`, `country` joined with `, `, otherwise `—`. |
| `country` | Always empty in the final row. |
| `cfp_close` | Parsed `cfpEndDate`, as ISO. |
| `topics` | Always `[]` in the final row; topic-file membership is discarded. |
| `event_url` | `url`, or empty. |
| `cfp_url` | `cfpUrl`, or empty. |
| `source` | `confs.tech` |

Standalone options are `--out`, `--today`, `--months-back` (default 1), `--cache`, and `--manifest`.

### 11.4 adato-tracker

**Implementation:** `src/process-adato-tracker.py`  
**Source page:** `https://adatosystems.com/cfp-tracker/`

#### Input and caching

- Prefer readable UTF-8 `<cache>/adato-tracker.html` without a freshness check.
- Otherwise GET the page with User-Agent `cfp-merge/1.0` and a 30-second timeout.
- Decode malformed bytes with replacement and write the page to cache.
- Parse only tables whose class tokens include exact lowercase `tablesorter`.
- Capture `<td>` text and the first nonempty link `href` in each cell; decode HTML character references.

Expected eight columns:

```text
Event Name | City | State | Event Start | Event End | CFP Close | Event URL | CFP URL
```

#### Filtering and mapping

Reject a row unless it:

- Has exactly eight cells.
- Has a nonempty event name.
- Has a nonempty CFP hyperlink.
- Has a strict ISO `YYYY-MM-DD` CFP close date on/after cutoff.

ISO datetime strings and free-text dates are rejected by this adapter. Event end is ignored. Apply ignored-name filtering and deduplicate by `(normalized name, ISO close date)`. Sort by deadline then lowercase name.

| Common field | Mapping |
|---|---|
| `name` | Event Name text. |
| `event_date` | Strict ISO Event Start, otherwise `TBA`. |
| `location` | `Online` when city is `VIRTUAL` case-insensitively; otherwise nonempty city/state joined with `, `, or `—`. |
| `country` | `Online` for virtual rows, otherwise empty. |
| `cfp_close` | Strict ISO CFP Close. |
| `topics` | `[]`. |
| `benefits`, `languages` | Absent/empty. |
| `event_url` | Event URL cell's `href`, or empty. |
| `cfp_url` | CFP URL cell's `href`. |
| `source` | `adato-tracker` |

Standalone options are `--out`, `--today`, `--months-back` (default 1), `--cache`, and `--manifest`.

### 11.5 Open Tech CFPs

**Implementation:** `src/process-open-tech-cfps.py`

**Source:** `https://1kevgriff.github.io/OpenTechCFPs/api/open.json` and `closed.json`

**Data license:** CC BY 4.0. Required attribution: **Open Tech CFPs, https://github.com/1kevgriff/OpenTechCFPs**.

#### Input and caching

- Fetch `open.json` then `closed.json`; prefer readable JSON caches named `open-tech-cfps-<kind>.json` without a freshness check.
- Require a top-level object with a `cfps` list of objects. A malformed document raises an error and stops the adapter rather than silently producing no rows.
- Requests use User-Agent `cfp-merge/1.0`, Accept `application/json`, and a 30-second timeout.

#### Filtering, identity, and ordering

- Parse `cfp_close_utc` as an offset-aware ISO datetime, normalize to UTC, and compare with midnight UTC on the inclusive cutoff date. Missing, invalid, or timezone-naive deadlines are rejected. Upstream `status` is not used.
- Require nonempty event `name` and submission `url`. Apply ignored-term rules to the name and tags; ignore the upstream `untagged` sentinel.
- Sort input records by source `updated` descending, with missing/invalid values oldest. Deduplicate repeated source IDs or submission URLs, then by normalized name + UTC close date—the note-path key—so one record cannot rewrite another in the same run.
- Sort output by UTC close date, lowercase name, then submission URL.

| Common field | Mapping |
|---|---|
| `name` | Event `name`. |
| `event_date` | Strict ISO `event_start`, otherwise `TBA`. |
| `location` | Source `location`; fallback is `Online`, resolved country, then `—`. |
| `country` | `Online` for `online: true`; otherwise resolve ISO alpha-2 `country` through `country_name_from_alpha2`. |
| `cfp_close` | UTC deadline date as ISO. |
| `topics` | Non-`untagged` source tags. |
| `benefits` | `travel` for `perks.travel` and `hotel` for `perks.accommodation`, only when value is `expenses covered` case-insensitively. `fee: free for speakers` is not an honorarium. |
| `event_url` | `website`, or empty. |
| `cfp_url` | `url`. |
| `source` | `open-tech-cfps` |

Standalone options are `--out`, `--today`, `--months-back` (default 1), `--cache`, and `--manifest`.

### 11.6 Manual Markdown input

**Implementation:** `src/process-manual-input.py`  
**Default input:** sorted, nonrecursive `input/*.md`  
**Network access:** none in the normal CLI path

Manual rows have highest source priority. All recognized table rows are processed without a recency cutoff or parser-level deduplication.

#### Table recognition

Only lines beginning with `|` after trimming are considered. Split on every literal `|`; escaped pipes are not supported. Require at least five columns.

Expected positions:

| Index | Meaning | Use |
|---:|---|---|
| 0 | Conference name and optional Markdown link | Name and event URL. |
| 1 | Location | Display location. |
| 2 | CFP open | Ignored. |
| 3 | CFP close | Normalized deadline or retained free text. |
| 4 | Conference date | Start date extraction or retained source text. |
| 5 | Topics | Optional comma-separated topic text. |

Skip:

- Header rows whose first cell begins with `Conf Name`, case-insensitively.
- Separator rows whose first cell contains only `-`, `:`, and spaces.
- Empty cleaned names.
- Names containing `would you like`.
- Names containing configured ignored terms.

Non-table prose is ignored. Input files are read in sorted filename order, and rows retain file/line order.

#### Name and URL extraction

From the first simple Markdown link in column 0:

- Use link text as the conference name.
- Use its destination as `event_url`.
- Strip runs of one to three `*` or `_` emphasis characters from the name.
- Collapse whitespace.

Without a link, use the entire cleaned cell as name and leave event URL empty.

For URLs containing case-sensitive `google.com/url`, extract and percent-decode the first `q` query value when present. Other URLs pass through unchanged. `cfp_url` remains empty.

#### Date normalization

Recognized exact deadline formats, tried in order:

```text
Month DD, YYYY       (for example December 31, 2026)
Mon DD, YYYY         (for example Dec 31, 2026)
DD Month YYYY        (for example 31 December 2026)
YYYY-MM-DD
DD/MM/YYYY
MM/DD/YYYY
```

Recognized values become ISO. Since day/month precedes month/day, ambiguous `03/04/2027` means 3 April 2027.

For other deadline strings:

- Remove slash-separated components that are empty or contain `unstated`, case-insensitively.
- Join remaining components with ` / ` and retry exact formats.
- Return `Unstated` when no components remain.
- Otherwise retain the resulting free text.
- Empty original input becomes `—`.

For event dates, `parse_start_date` recognizes:

- ISO prefixes, optionally followed by ranges or a weekday suffix.
- English month/day/year forms and same-month ranges such as `Apr 13–15, 2027`.

A recognized range contributes only its start date. Unrecognized nonempty manual date text is retained rather than replaced with `TBA`; empty input becomes `—`.

#### Final row mapping

| Common field | Mapping |
|---|---|
| `name` | Cleaned link text or cell text. |
| `event_date` | Parsed start date, original nonempty text, or `—`. |
| `location` | Column 1, or `—` when empty. |
| `country` | Always empty; not inferred from `London, UK` or similar text. |
| `cfp_close` | Normalized column 3. |
| `topics` | Column 5 split on commas, trimmed, with empty items removed. |
| `event_url` | Extracted/unwrapped link, or empty. |
| `cfp_url` | Always empty. |
| `source` | `manual`. |

Standalone options are `--out`, `--input`, and `--manifest`. A missing input directory prints an error and exits 1. This differs from the full wrapper, which silently omits manual processing when its input directory is absent.

## 12. Orphan archiving specification

**Implementation:** `src/archive-orphans.py`

After all source subprocesses succeed, and unless `--no-archive` is set, the full wrapper archives notes absent from the union of produced manifests.

### 12.1 Orphan calculation

Recursively scan sorted `*.md` files below the live data directory:

1. If the data-relative POSIX path is in the produced set, keep it without parsing.
2. Otherwise parse its frontmatter.
3. Leave the file alone when frontmatter is invalid, absent, empty, or `type` does not normalize to exact string `cfp`.
4. Leave the file alone when its `source` belongs to a source skipped through `--skip-source`.
5. Keep the file when `shortlist` is true. The `dismissed` value does not affect archiving.
6. Keep the file when `submissions` is nonempty or the notes body contains text.
7. Keep the file when custom frontmatter exists.
8. Treat `tier` as registry-managed rather than custom frontmatter. A `tier` value alone does not prevent archiving.
9. Classify every remaining CFP note as an orphan.

Malformed CFP notes remain in the live tree for manual repair. Notes with user curation also remain in the live tree.

### 12.2 Move behavior

For each orphan relative path `R`:

```text
source      = data_dir / R
destination = archive_dir / R
```

Create destination parents and rename the file. The operation:

- Preserves nested/year layout.
- Moves note contents byte-for-byte.
- Does not add an `archived` property.
- Does not edit `shortlist`, `dismissed`, submissions, notes, or timestamps.
- Does not delete empty source directories.
- Performs no rollback if a later move fails.

### 12.3 Standalone CLI

```bash
python3 src/archive-orphans.py \
  [--data data] [--archive archived] \
  [--manifest FILE ...] [--dry-run] [--json]
```

- `--manifest` is repeatable.
- Missing/non-file manifest paths are ignored.
- Existing manifests are JSON-decoded and unioned without additional schema validation.
- `--dry-run` computes and reports moves without creating destination directories or moving files.
- `--json` prints only the moved/would-move relative paths as indented JSON.
- Normal output reports `archived N note(s)` or `would archive N note(s)` and lists each path.

With no produced paths, every eligible parseable `type: cfp` note in the live tree is considered an orphan. The curation checks above still apply.

## 13. Existing-note normalization

**Implementation:** `src/normalize-data.py` and `cfp_writer.normalize_file`

Run:

```bash
python3 src/normalize-data.py [--data data]
```

The CLI recursively visits sorted `*.md` files below the data directory. It exits 1 when the directory does not exist.

For a file with valid, nonempty mapping frontmatter, normalization:

1. Converts known scalar values to the writer's canonical strings.
2. Uses legacy `conf_date` when `event_date` is empty.
3. Preserves a nonempty `event_type` or infers/backfills a missing one according to §6.7.
4. Converts topics, benefits, and languages through list normalization.
5. Canonicalizes country.
6. Removes UTM parameters from both URLs.
7. Normalizes `shortlist`, `dismissed`, and submissions; a missing `dismissed` flag becomes `false`.
8. Migrates legacy scalar submission where applicable.
9. Extracts body notes.
10. Preserves additional properties according to §6.3.
11. Backfills timestamps according to §8.5 without advancing valid `updated`.
12. Re-renders in canonical order and writes only if bytes differ.

Normalization is intended to be idempotent. Its reported `normalized N notes` count is the number successfully processed, not necessarily the number whose bytes changed. Files returning false are counted as skipped and do not make the command fail.

Important current edge behavior is listed in §17.8: the CLI does not restrict processing to existing `type: cfp` notes, and a top-level frontmatter `notes` key is currently preserved as extra metadata despite older comments saying it is dropped.

## 14. Link-liveness utility

**Implementation:** `src/check-links.py`

```bash
python3 src/check-links.py REPORT.md \
  [--only SUBSTRING] [--workers 8] [--timeout 20]
```

Behavior:

1. Read one Markdown report; this utility does not recursively scan CFP notes.
2. Extract absolute HTTP(S) destinations from Markdown links and supported bare URLs.
3. Strip trailing `, . ; : ! ?`, deduplicate, apply the optional case-sensitive substring filter, and sort.
4. Check URLs concurrently with a `ThreadPoolExecutor`.
5. Issue GET requests using redirect-aware `urllib` and a desktop Chrome-like User-Agent.
6. Treat an HTTP status as a result even when urllib raises `HTTPError`.
7. Convert DNS, TLS, timeout, reset, and other non-HTTP failures to `ERR` with an exception message.
8. Print only non-200 results, followed by `200: N | not-200: M`.
9. Exit 0 only when every checked URL returns exactly 200; otherwise exit 1.

Other 2xx statuses count as not-200. A 403 or 429 response means blocked/rate-limited or unknown, not necessarily dead. There are no retries or backoff; worker counts should remain modest.

## 15. Obsidian presentation specification

### 15.1 Base artifact

`cfps.base` can be copied into the vault. Its global filter is:

```text
type == "cfp"
```

Its `Event` formula links to `file.path`, displaying `event_name` when truthy and otherwise `file.name`. Its `submission_count` formula evaluates `list(submissions).length` and appears as **Submissions** in the Submitted view.

Most data views have **(+dismissed)** and **(-dismissed)** versions. The plus version includes dismissed notes through `formula.is_in_data`. The minus version hides them through `formula.is_live`. Short listed and Submitted are single views that include dismissed notes. Dismissed is a single view of dismissed data notes. Archived is a single view that includes dismissed archived notes.

Folder filtering is per-view because the global filter ANDs with each view. A global data-folder restriction would blank Archived. The `data_dir` and `archived_dir` formulas hold the configurable path suffixes.

The `my_country` formula holds the canonical country value for the user's country views. The `is_local_area` formula holds the location-substring predicate for the local-area views. Both personal settings live in the base's `formulas` section because Obsidian does not read the Python configuration.

### 15.2 Base views

| View | Filter and behavior |
|---|---|
| **All (-dismissed)** | Every non-dismissed CFP note under the configured data path. No deadline restriction. |
| **All (+dismissed)** | Every CFP note under the configured data path, including dismissed notes. |
| **Recently Updated (+/-dismissed)** | Data notes sorted by `updated` descending. The plus variant includes dismissed notes; the minus variant excludes them. |
| **Short listed** | All data notes with `shortlist == true`, including dismissed notes. No Dismissed column or deadline restriction. |
| **Submitted** | All data notes where `list(submissions).length > 0`, including dismissed notes. Shows the submission count and no Dismissed column. No deadline restriction. |
| **Upcoming (> -30 days) (-dismissed)** | `cfp_close >= today() - "30d"`. Includes that cutoff day and all future deadlines. |
| **Upcoming (> today) (-dismissed)** | `cfp_close >= today()`. Inclusive despite the label's `>`. |
| **Closed (90d) (-dismissed)** | `cfp_close < today() - "30d"` and `>= today() - "90d"`. |
| **Location - My Country (-dismissed)** | `country == formula.my_country`. |
| **Location - Outside My Country (-dismissed)** | `country != formula.my_country`. Includes online and empty or unknown country values. |
| **Location - Online (-dismissed)** | `country == "Online"`. |
| **Location - My Local Area (-dismissed)** | `formula.is_local_area` matches. |
| **Dismissed** | Dismissed notes under the configured data path. |
| **Archived** | All notes under the configured archived path, including dismissed notes. Sorted by deadline descending. |

For paired regular data views, the plus and minus versions differ only in dismissal filtering. Regular data views sort `cfp_close` ascending, except Recently Updated sorts `updated` descending. Archived sorts `cfp_close` descending.

The default `is_local_area` substring list covers San Francisco, San Jose, Oakland, Berkeley, Santa Clara, Sunnyvale, Palo Alto, Mountain View, Cupertino, Redwood, Menlo Park, San Mateo, Milpitas, Fremont, Hayward, Emeryville, Los Altos, Los Gatos, Pleasanton, Livermore, and Bay Area. Users edit this one formula to change both local-area views.

Most views display a common set of CFP properties. Short listed and Submitted omit the `dismissed` column; other views show it immediately after `shortlist`. Submitted shows `formula.submission_count` after `shortlist`. No view displays `benefits` or the raw `submissions` list. Upcoming (> today) additionally includes `languages`; Recently Updated adds `updated` after `dismissed`.

### 15.3 Dataview dashboard

`cfps-dashboard.md` uses three Dataview tables. All read positively from `cfps/data` and require `type = "cfp"`, thereby excluding archived notes by path.

| Table | Query semantics |
|---|---|
| **Events by country** | Require truthy `country`; group by stored label, count rows, sort counts descending. Empty-country notes are absent. |
| **Events by topic** | Require truthy `topics`, `FLATTEN topics AS topic`, group/count by topic, sort counts descending. One event contributes once to each topic. |
| **Events by month** | Require truthy `event_date`; group by `dateformat(event_date, "yyyy-MM")`, count rows, sort month descending. Uses conference start date, not CFP deadline. |

The dashboard performs no topic canonicalization. The month query does not explicitly exclude `TBA` or other unparseable values; rendering of those values is Dataview-dependent.

## 16. Runtime, development, and verification

### 16.1 Runtime requirements

- Python 3.10 or newer.
- Network access for fetching uncached external sources.
- PyYAML 6.0 or newer.
- pycountry 24.6.1 or newer.
- `curl` for the preferred developers.events fetch path.
- uv is supported but optional.

`pyproject.toml` and `requirements.txt` define PyYAML and pycountry as required Python dependencies. pycountry resolves Open Tech CFPs' ISO country codes and also supports country-flag emoji in the retired single-file developers.events report. The uv project is a scripts folder, not an installable package.

Setup and refresh:

```bash
uv sync
uv run python src/process-all.py
```

Alternative:

```bash
pip install -r requirements.txt
python3 src/process-all.py
```

Isolating note output:

```bash
uv run python src/process-all.py --out /tmp/cfp-scratch
```

This redirects note writes; it is not a universally side-effect-free dry run because caches and the confs.tech discovered-topic comments can still be updated.

### 16.2 Tests

Run the stdlib test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
# or
uv run python -m unittest discover -s tests -v
```

The suite is primarily offline and covers:

- Writer rendering, identity, no-op behavior, topic merging, event-type inference/preservation/backfill, precedence, duplicate matching, timestamps, UTM removal, and invalid YAML.
- Every source parser using real source slices under `tests/fixtures/`.
- Country aliases and ISO alpha-2 conversion.
- Manifest and orphan movement behavior.
- Summary parsing and output arithmetic.
- An offline manual-input subprocess path.
- Conformance of available vault template frontmatter keys to the generated schema; this test skips when the external template is unavailable.

Fixture slices represent downloaded developers.events, cfp.ninja, confs.tech, Adato, and Open Tech CFPs data plus real manual table rows. `tests/fixtures/extract_fixtures.py` regenerates them from cached/real input when maintenance is needed.

Any `src/` change must keep the suite green and add or update tests for changed behavior. Tests should not be deleted or weakened merely to force a pass.

### 16.3 Operational verification checklist

After a refresh:

1. Confirm every intended note under live data has valid YAML mapping frontmatter.
2. Check that generated `event_date` values are clean `YYYY-MM-DD` start dates or `TBA`, while recognizing the manual free-text exception described in §11.6 and §17.9.
3. Confirm a second identical run does not rewrite unchanged notes or change their mtimes.
4. Confirm `shortlist`, `dismissed`, `submissions`, body notes, and additional frontmatter survive source changes.
5. Confirm manifests exclude skipped rows and archive dry-run output is plausible.
6. Check that no unexpected non-CFP Markdown files were archived.
7. Compare source-row counts and on-disk counts with freshly fetched data, not with an assumed historical baseline.
8. Report actual new/updated/current and archived counts, along with suspicious links or source errors.

Useful commands:

```bash
find -L data -name '*.md' | wc -l
python3 src/archive-orphans.py --dry-run
python3 src/check-links.py tmp/cfps.md
python3 src/normalize-data.py
```

### 16.4 Extension contract for a new source

A new adapter should:

1. Fetch and parse its source without scraping a stale rendered snapshot when a live data endpoint exists.
2. Return rows in the common normalized shape.
3. Apply explicit, date-based deadline filtering rather than trusting upstream status labels.
4. Define source-level deduplication and ordering.
5. Assign a unique source label and, if necessary, a position in `SOURCE_PRIORITY`.
6. Call `upsert_counted` for every selected row.
7. Use `summary_line` and `write_manifest`.
8. Never manually concatenate unsafe YAML.
9. Add real-fixture parser tests and integration into `process-all.py`.
10. Update operational documentation and source inventories in the same change.

## 17. Current limitations and implementation quirks

The following are properties of the inspected code, not necessarily intended long-term design.

### 17.1 Refresh and archiving are not transactional

- An adapter upserts notes as it iterates; there is no staging or rollback.
- A later source failure stops archiving but leaves earlier writes in place.
- confs.tech can log and skip failed listings/files, then produce a successful but incomplete manifest.
- Missing manifests are ignored by the archiver.
- An empty produced set archives every parseable CFP note without user curation.
- Manual source omission due to a missing input directory can make manual-only notes appear unproduced.
- Archive destination collisions are not checked before `rename`; platform rename semantics apply, and an existing destination may be replaced.
- Cross-filesystem or permission errors can interrupt archiving partway through.

Consequently, archive results deserve review, especially after partial source success or configuration changes.

### 17.2 Cutoff and option forwarding are not uniform

- developers.events currently defaults `--months-back` to 3 (about 90 days), despite help and older documentation referring to 1.
- cfp.ninja, confs.tech, and Adato default to 1 (about 30 days).
- Wrapper leftover options such as `--today`, `--months-back`, `--past-days`, and `--cache` go only to developers.events.
- The other adapters use their own actual current dates and default caches during a wrapper run unless their code is changed or they are run separately.
- Adapter `--today` values never control production writer timestamps.
- `collect_rows` accepts a `today` parameter in several adapters even when only `cutoff` is used.

A full wrapper `--today` is therefore not a complete historical reproducibility mechanism.

### 17.3 Cache freshness differs by source

- developers.events attempts a fresh curl download on every run and can use an existing cache after a failed fetch.
- cfp.ninja, confs.tech, and Adato prefer any readable cached response indefinitely; no TTL or force-refresh flag exists.
- Corrupt JSON caches generally cause a refetch in JSON adapters.
- developers.events documentation says urllib is a fallback when curl is absent, but an actually missing curl executable raises `FileNotFoundError` before that return-code-based fallback can run.

A nominal refresh must not be interpreted as proof that every source was fetched live.

### 17.4 Refresh writes generated reference data

Every confs.tech CLI run calls `write_discovered_topics`, which rewrites the reference-only `src/discovered-topics.txt`. It does not modify implementation source. Refresh side effects therefore include more than notes, caches, and manifests.

### 17.5 Identity changes do not preserve history automatically

Changing a name or date can create a new path and new first-seen stamps. Existing user metadata remains at the old path until that file is archived or manually reconciled. There is no persistent conference ID independent of name/deadline/URL heuristics.

Similarly, when URL-based deduplication selects a winner, losing-note user content is not merged into the winner. It remains with the losing file and moves to Archived only if archiving runs.

### 17.6 Partial duplicates and source-specific loss are possible

- Empty manual `cfp_url` values cannot participate in URL deduplication.
- Different submission URLs are never merged by the cross-path rule.
- Shared-form protection can leave genuine duplicates separate.
- Name compatibility can theoretically merge distinct events that look compatible.
- confs.tech deduplicates by name alone, so later editions or revised deadlines with the same normalized name can be discarded.
- A higher-priority source replaces the source-owned note fields rather than combining the best fields from every source. Cumulative `topics` are the exception: existing values remain and new values are appended.

### 17.7 Legacy developers.events options are mostly inert for notes

`process-developer-events.py` still builds a retired single-file report and computes AI-focus markers, but discards the generated document. As a result:

- `--focus-tags` and `--no-focus` do not affect CFP notes.
- `--no-frontmatter` does not remove per-note frontmatter.
- `--no-backup` has no effect on per-note output.
Country-flag rendering is not used by the active note path.

`src/build-open-cfps.py` is retained solely as a compatibility shim and carries a stated removal date of 2027-03-01.

### 17.8 Normalization is broader and slightly different from its comments

- `normalize-data.py` processes every Markdown file with parseable, nonempty mapping frontmatter under the selected tree; it does not first require `type: cfp`.
- `normalize_file` renders such a file with `type: cfp`, so running it over unrelated Markdown notes is unsafe.
- Its `normalized N` count means successfully processed, not necessarily modified.
- Older comments say frontmatter `notes` is dropped, but `notes` is not in `KNOWN_FM_KEYS`; current `_extra_frontmatter_lines` behavior treats it as an additional property and preserves it.
- Invalid YAML also leads to the CLI's generic `skipped (no frontmatter)` message after the writer's more specific warning.

### 17.9 Date and schema validation are not uniformly enforced

- The shared writer accepts source strings as provided; it does not validate every field against a strict schema.
- `cfp_close` intentionally supports manual free text, which may not behave like a date in Base filters.
- Manual unparseable `event_date` text is retained, despite operational guidance that healthy notes use ISO or `TBA`.
- Timestamp validation checks only `YYYY-MM-DD` shape, not calendar validity.
- No CFP opening date is exposed in generated notes, even though cfp.ninja and manual input can contain one upstream.

### 17.10 Link checking is a heuristic operational aid

- Only exact status 200 passes; other successful statuses fail.
- 403/429 and network errors do not prove a link is dead.
- URL extraction is regular-expression based and does not support every legal Markdown destination or URL delimiter case.
- The checker reads a single report, not the whole current note tree, so its coverage depends on the report supplied.

### 17.11 Event type is heuristic metadata

Because current feeds provide no authoritative event-kind value, an inferred `event_type` is only a name-based classification. A fallback value of `conference` does not prove that an event is a conference, and multi-keyword names use the configured precedence in §6.7. Sticky preservation also means a later name change does not automatically reclassify an existing note; correcting or refining the type requires editing it explicitly or clearing it so it can be inferred again.
