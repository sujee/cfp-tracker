# CFP Tracker
#cfp #conference

Conference CFPs (Call For Papers) worth submitting talks to, refreshed from public CFP feeds into one note per conference.

The code lives here. `data/` and `archived/` are symlinks to the Obsidian vault's `cfps/` folder, so a refresh updates the vault notes in place and no code lives in the vault.

## Quick start

Requires Python ≥ 3.10, network access, and PyYAML.

```bash
git clone git@github.com:sujee/cfp-tracker.git
cd cfp-tracker

# one time: link the note folders to your vault (create them first if missing)
ln -s /path/to/your-vault/cfps/data data
ln -s /path/to/your-vault/cfps/archived archived

uv sync                                 # create .venv + install PyYAML
uv run python src/process-all.py        # refresh the notes
```

No uv? `pip install -r requirements.txt`, then `python3 src/process-all.py`. (`pycountry` is optional, for country-flag emoji.)

Each run prints a line per source plus a summary, e.g. `developers.events: found 574 (new 0, updated 5, unchanged 569)`.

- Notes are rewritten only when their source data changed. `shortlist`, `submissions`, the `## Notes` body, and any extra frontmatter fields are preserved.
- Notes that no source carries any more are moved to `archived/` (`--no-archive` skips this).

**Dry run** (writes nothing to `data/`): `uv run python src/process-all.py --out /tmp/scratch`

**Tests:** `uv run python -m unittest discover -s tests`

## Using an agent

Open an agent in this folder and say `update cfps`. It runs the pipeline and reports the new CFP count per source. The full procedure is in [`INSTRUCTIONS.md`](INSTRUCTIONS.md).

## Browse the CFPs in Obsidian (cfps.base)

Copy [cfps.base](cfps.base) anywhere in your Obsidian vault and open it. Obsidian shows one table per way of looking at the CFPs, listed in the view switcher.

The views share one set of columns, sorted by CFP deadline (soonest first, except Archived): Event (links into the note), Shortlist, Country, Event date, Location, Topics, CFP close, CFP link, Event link, Submissions, Benefits, Source.

> **Vault path:** the views exclude archived notes by the path `cfps/archived/`. If your vault keeps the notes elsewhere, find-and-replace that path in `cfps.base`, or the live views will show archived notes and **Archived** will be empty.

The views:

| View | What it shows |
|---|---|
| **All CFPs** | Every live note. The default. |
| **Upcoming (> today)** | Only still-open CFPs (`cfp_close` today or later). Your working list. |
| **Upcoming (> -30 days)** | Open CFPs plus those that closed in the last 30 days. |
| **Closed (90d)** | CFPs that closed 30 to 90 days ago, for recap. |
| **Short listed** | Notes you flagged `shortlist: true`. |
| **Submitted** | Notes with at least one wiki link under `submissions`. |
| **Conf in USA / Conf outside USA / Online** | Geography filters. |
| **Local events** | Events in The San Francisco Bay Area, which is my area (feel free to tweak it to yours). Matches local cities in `location`. |
| **By source** | Same list, grouped by which feed the note came from. |
| **By country** | Same list, grouped by country. |
| **Archived** | The notes in `archived/` (moved there by a refresh once no source carries them), latest deadline first. Every other view excludes them. |

**Using it:** pick a view, click an Event link to open the note, and sort or filter by any column. To track intent, set `shortlist: true` or add wiki links under `submissions` in the note's frontmatter. The views pick that up immediately, and refreshes preserve both fields.

The base filters on `type: cfp`, so only pipeline notes appear. Your own details (where to submit, deadline quirks) go in the note's `## Notes` body. To tune the tables, edit the YAML in `cfps.base`.

## Dashboard counts (cfps-dashboard.md)

[cfps-dashboard.md](cfps-dashboard.md) counts the live CFPs in three small dataview tables: events by country, by topic, and by month. Copy it into your vault and open it. It reads the same notes as the base, so archived CFPs are excluded and the counts update after each refresh. (Same caveat as the base: if your vault keeps the notes elsewhere, find-and-replace `30-speaking-talks/cfps/data` in the dataview blocks.)

Events with several topics count once in each topic. Months come from the note's `event_date`.

## Options

`--help` on any script lists all flags.

| Flag | Effect |
|---|---|
| `--out DIR` | Write notes to DIR instead of `data/` |
| `--today YYYY-MM-DD` | Reproduce a past run; sets the "still open" cutoff |
| `--months-back N` | How far back "recently closed" reaches (default 1) |
| `--cache DIR` | Fetched-JSON cache (default `cache/`) |
| `--no-archive` | Keep orphaned notes instead of archiving them |
| `--archive DIR` | Archive orphans somewhere other than `archived/` |
| `--input DIR` | Read manual rows from DIR instead of `input/` |

Run a single source:

```bash
python3 src/process-developer-events.py --out data
python3 src/process-cfp-ninja.py --out data
python3 src/process-confs-tech.py --out data
python3 src/process-manual-input.py --out data
```

Useful checks:

```bash
find -L data -name '*.md' | wc -l          # note count, through the symlink
python3 src/archive-orphans.py --dry-run   # what would be archived
python3 src/check-links.py tmp/cfps.md     # HTTP liveness sweep
python3 src/normalize-data.py              # re-emit notes to the current shape (idempotent)
```

A healthy note opens with a `---` YAML frontmatter block, and `event_date` is `YYYY-MM-DD` (start date only) or `TBA`.

## Sources

| Source | Notes |
|---|---|
| **developers.events** | `all-cfps.json` + `all-events.json`, fetched live. `untilDate` is the deadline (epoch ms). |
| **cfp.ninja** | Open-source CFP platform ([sreday/cfp.ninja](https://github.com/sreday/cfp.ninja)); public API, no auth. Includes location, tags, and speaker benefits. |
| **confs.tech** | [tech-conferences/conference-data](https://github.com/tech-conferences/conference-data) (MIT). Has `cfpUrl` + `cfpEndDate`; no `ai` topic file, so AI events sit under `general` or a language topic. |
| **`input/*.md`** | Hand-curated rows, merged by `src/process-manual-input.py`. |

If two sources carry the same conference, the higher-priority one owns the note: `manual` > `developers.events` > `cfp.ninja` > `confs.tech`.

**Not yet scripted:** cfp.fru.dev (cross-check), events.fru.dev, dev.events, pretalx.com, Sessionize (a link target only).
**Dead, do not add:** papercall.io (shut down) and CFP Land.

Details and HTTP-verified status: [`cfp-sources.md`](cfp-sources.md).

## Repo layout

- `src/`: the pipeline. `process-all.py` runs every source; one `process-*.py` per source; `cfp_writer.py` writes notes; `country.py`, `archive-orphans.py`, `check-links.py`, `normalize-data.py` are helpers.
- `data/`, `archived/`: symlinks into the vault (gitignored; created in Quick start).
- `input/`: hand-curated rows (highest-priority source).
- `tests/`: stdlib `unittest` suite; fixtures are real slices of the downloaded data.
- `cache/`, `backups/`, `tmp/`: runtime scratch (gitignored).
- Docs: [`INSTRUCTIONS.md`](INSTRUCTIONS.md) (agent procedure), [`AGENTS.md`](AGENTS.md) (data shapes, note shape, pitfalls), [`cfp-sources.md`](cfp-sources.md).
- `cfps.base`: the Obsidian base; copy it into your vault.
- `cfps-dashboard.md`: an Obsidian note that counts the live CFPs by country, topic, and month.
- Lives in the vault, not here: `templates/cfp-template.md`.
