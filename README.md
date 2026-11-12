# CFP Tracker
#cfp #conference

A personal project to pull conference Calls for Papers (CFPs) from public sources into my personal Obsidian vault.

This is **not another public CFP tracker or index**. It is my personal ingestion pipeline for discovering, shortlisting, and tracking CFPs in Obsidian.

Thank you to all the CFP site maintainers whose public feeds, datasets, calendars, and CFP pages make this project possible.

## Quick start

Requires Python ≥ 3.10, network access, PyYAML, and pycountry.

**setup - one time**

```bash
git clone git@github.com:sujee/cfp-tracker.git
cd cfp-tracker

# one time: link the note folders to your vault (create them first if missing)
ln -s /path/to/your-vault/cfps/data data
ln -s /path/to/your-vault/cfps/archived archived
```

**Configuration**

Inspect [src/config.py](src/config.py) and choose which confs.tech topic files to fetch:

```python
CONFS_TECH_TOPICS = {
    "devops",
    "opensource",
    "python",
}
```

`general.json` is always included. Use `CONFS_TECH_TOPICS = set()` to fetch every confs.tech
category. This setting does not filter the other sources.

Optionally, you can set `IGNORE_TOPICS` as well.

`EVENT_TYPES` is the allow-list of event types to keep. The checked-in configuration currently
enables `conference`, `summit`, and `workshop`; other supported types are commented so you can
uncomment them as needed. To keep only conferences and summits, use:

```python
EVENT_TYPES = ["conference", "summit"]
```

Excluded types are archived. Empty lists and invalid type names fail the run instead of archiving notes.

**Run it: Option 1 (easy) -  with agent**

Open an agent in this folder and say 

```text
update cfps
```

That's it! :-) 

It runs the pipeline and reports the new CFP count per source. The full procedure is in [`INSTRUCTIONS.md`](INSTRUCTIONS.md).


**Run it: Option 2 -  Manually with UV (preferred)**

```bash
# dry run (nothing is updated)
uv run python src/process-all.py --out /tmp/scratch

# real run
uv run python src/process-all.py        # refresh the notes
```

**No uv?**

```bash
python3 -m venv .venv
source .venv/bin/activate          # activate it (zsh/bash)
pip install -r requirements.txt 
python3 src/process-all.py
```

Each run prints a line per source plus a summary, e.g.

```
=====================================================
 CFP refresh summary
=====================================================
source               found    new  updated  unchanged
-----------------------------------------------------
developers.events      582      0        0        582
cfp.ninja               34      0        0         34
confs.tech              13      0        0         13
adato-tracker          249      0        0        249
open-tech-cfps         629      0        0        629
manual input             5      0        0          5
-----------------------------------------------------
Total                 1512      0        0       1512

 Event types (live notes; ★ = included in EVENT_TYPES)
source               conference ★  meetup  summit ★  workshop ★  hackathon  webinar  other
developers.events             531       0        45           2          0        0      0
cfp.ninja                      34       0         0           0          0        0      0
confs.tech                      1       0         0           0          0        0      0
adato-tracker                  95       0        13           0          0        0      0
open-tech-cfps                323       0        10           0          0        0      0
manual input                    3       0         2           0          0        0      0
Total                         987       0        70           2          0        0      0
```

The event-type matrix counts live notes after deduplication and archiving. ★ marks types enabled in `EVENT_TYPES`.

**Tests:** 

```bash
uv run python -m unittest discover -s tests
```

## Browse the CFPs in Obsidian 

**Vault paths**

- `cfps/data` : where imported CFPs are 
- `cfps/archived` : deleted / archived CFPs

Copy these files into your Obsidian Vault — the folder that contains `cfps/`, or anywhere else
you keep your dashboards.

- [cfps.base](cfps.base): Has views defined to browse CFPs
- [cfps-dashboard.md](cfps-dashboard.md): CFP stats (Dataview tables: by country, topic, month)

> **Vault path:** `cfps.base` keeps its two folder paths in `data_dir` / `archived_dir` at the
> top of the file, matched as path *suffixes* — so it works with `cfps/data` at the vault root
> **and** with `30-speaking-talks/cfps/data`. If those note folders live elsewhere, change just
> those two constants and the dashboard's `FROM` clause.



A few views defined in `cfps.base` (you can customize them!)

Every view has a **(+dismissed)** version and a **(-dismissed)** version. The plus version includes dismissed notes. The minus version hides them. Every view shows **Shortlist** and **Dismissed** together, immediately after **CFP close**. No view displays **Benefits** or **Submissions**.

| View | What it shows |
|---|---|
| **All (-dismissed)** | Every non-dismissed note in `data/`. |
| **All (+dismissed)** | Every note in `data/`. The **Dismissed** column shows the flag. |
| **Recently Updated (+dismissed) / Recently Updated (-dismissed)** | Data notes sorted by `updated`, newest first; with or without dismissed notes. |
| **Upcoming (> today)** | Only still-open CFPs (`cfp_close` today or later). Your working list. |
| **Upcoming (> -30 days)** | Open CFPs plus those that closed in the last 30 days. |
| **Closed (90d)** | CFPs that closed 30 to 90 days ago, for recap. |
| **Short listed** | Notes you flagged `shortlist: true`. |
| **Prestigious** | Notes with a curated `tier` of 1 or 2, sorted by tier then CFP close. The ranking comes from `prestige.md`, not from any feed. |
| **Dismissed (+dismissed)** | Only dismissed notes. The minus version is empty by definition. |
| **Archived (+dismissed) / Archived (-dismissed)** | Archived notes with or without dismissed notes. |
| **Submitted** | Notes with at least one wiki link under `submissions`. |
| **Location - USA / Location - Out of USA / Location - Online** | Geography filters. |
| **Location - Local** | Events in The San Francisco Bay Area, which is my area (feel free to tweak it to yours). Matches local cities in `location`. |

## Prestige ranking

Feeds carry deadlines, not reputations, so the "is this a conference worth speaking at"
judgement is curated by hand in [`prestige.md`](prestige.md) — a plain table of
`conf name | ranking | keywords`. `python3 src/apply-prestige.py` stamps a numeric `tier`
(`1` flagship, `2` major, `3` notable) onto every note whose `event_name` matches a row;
`process-all.py` runs it last automatically. `tier` is separate from `shortlist`: the tier
is the conference's reputation, the shortlist is your interest.

```bash
python3 src/apply-prestige.py --check    # per-row match counts; writes nothing
```

A row matching **nothing** is either a flagship no feed carries (re:Invent, Google I/O,
Microsoft Build, WWDC, PyCon US, NeurIPS, USENIX ATC, GOTO…) or a typo; a tier-1/2 keyword
hitting far too many notes is too broad. Both need your attention.

## Selecting sources

Which sources run is also configured, not hardcoded: `INPUT_SOURCES` in
[`src/config.py`](src/config.py). Comment out a source to skip its fetch; its existing
notes stay in `data/` (they are **not** archived, so the source can be re-enabled later).
Unknown or empty values fail the run loudly.

## Sample Workflow

- Do a run to update CFPS.  See [quick start](#Quick-start)
- Check `cfps.base` in Obsidian
- Browse CFPs and shortlist the the one's you are interested in - by selecting the **short listed** flag
- Not interested in one? Check `dismissed = true`. **(-dismissed)** views hide it immediately. The corresponding **(+dismissed)** view still shows it. Clear the flag to bring it back. **Dismissed (+dismissed)** lists all dismissed notes.

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
| `--prestige FILE` | Rank from FILE instead of `prestige.md` |
| `--no-prestige` | Do not stamp curated `tier` values |

Run a single source:

```bash
python3 src/process-developer-events.py --out data
python3 src/process-cfp-ninja.py --out data
python3 src/process-confs-tech.py --out data
python3 src/process-adato-tracker.py --out data
python3 src/process-open-tech-cfps.py --out data
python3 src/process-manual-input.py --out data
```

Useful checks:

```bash
find -L data -name '*.md' | wc -l          # note count, through the symlink
python3 src/archive-orphans.py --dry-run   # what would be archived
python3 src/check-links.py tmp/cfps.md     # HTTP liveness sweep
python3 src/normalize-data.py              # re-emit notes to the current shape (idempotent)
python3 src/apply-prestige.py --check      # prestige.md vs the notes; nothing matched? why
```

A healthy note opens with a `---` YAML frontmatter block, and `event_date` is `YYYY-MM-DD` (start date only) or `TBA`. Notes whose resolved `event_type` is excluded by `EVENT_TYPES` are omitted from the live CFP tree and moved to `archived/`; explicit allowed event-type overrides are preserved.

## Sources

| Source | Notes |
|---|---|
| **developers.events** | `all-cfps.json` + `all-events.json`, fetched live. `untilDate` is the deadline (epoch ms). |
| **cfp.ninja** | Open-source CFP platform ([sreday/cfp.ninja](https://github.com/sreday/cfp.ninja)); public API, no auth. Includes location, tags, and speaker benefits. |
| **confs.tech** | [tech-conferences/conference-data](https://github.com/tech-conferences/conference-data) (MIT). Has `cfpUrl` + `cfpEndDate`; no `ai` topic file, so AI events sit under `general` or a language topic. |
| **adato-tracker** | The `tablesorter` table on [adatosystems.com/cfp-tracker](https://adatosystems.com/cfp-tracker/) (Leon Adato). Clean ISO dates, event + CFP URLs, city/state; no topics or benefits. It aggregates other feeds and only fills gaps. |
| **Open Tech CFPs** | Public [open/closed JSON](https://github.com/1kevgriff/OpenTechCFPs), filtered by exact `cfp_close_utc`. Includes topics and explicit travel/hotel coverage; lowest-priority gap filler. Data: CC BY 4.0. |
| **`input/*.md`** | Hand-curated rows, merged by `src/process-manual-input.py`. |

Open Tech CFPs data attribution: **Open Tech CFPs, https://github.com/1kevgriff/OpenTechCFPs** ([CC BY 4.0](https://github.com/1kevgriff/OpenTechCFPs/blob/main/LICENSE-DATA)).

If two sources carry the same conference, the higher-priority one owns the note: `manual` > `developers.events` > `cfp.ninja` > `confs.tech` > `adato-tracker` > `open-tech-cfps`.

Details and HTTP-verified status: [`cfp-sources.md`](docs/cfp-sources.md).

## Repo layout

- `src/`: the pipeline. `process-all.py` runs every enabled source (`INPUT_SOURCES` in `src/config.py`); one `process-*.py` per source; `cfp_writer.py` writes notes; `country.py`, `archive-orphans.py`, `check-links.py`, `normalize-data.py` are helpers.
- `prestige.md`: the curated conference ranking (tier 1/2/3) applied by `src/apply-prestige.py`; `src/prestige.py` is its loader/matcher.
- `data/`, `archived/`: symlinks into the vault (gitignored; created in Quick start).
- `input/`: hand-curated rows (highest-priority source).
- `tests/`: stdlib `unittest` suite; fixtures are real slices of the downloaded data.
- `cache/`, `backups/`, `tmp/`: runtime scratch (gitignored).
- Docs: [`INSTRUCTIONS.md`](INSTRUCTIONS.md) (agent procedure), [`AGENTS.md`](AGENTS.md) (data shapes, note shape, pitfalls), [`cfp-sources.md`](docs/cfp-sources.md).
- `cfps.base`: the Obsidian base; copy it into your vault.
- `cfps-dashboard.md`: an Obsidian note that counts the live CFPs by country, topic, and month.
- Lives in the vault, not here: `templates/cfp-template.md`.
