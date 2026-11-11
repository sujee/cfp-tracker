# CFP Tracker
#cfp #conference

A Conference CFPs (Call For Papers) tracker - it pulls data from public sources into Obisidian Vault.

## Quick start

Requires Python ≥ 3.10, network access, and PyYAML.

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

Optionally, you can set `IGNORE_TOPICS` as well

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
developers.events      592      0        0        592
cfp.ninja               34      0        0         34
confs.tech              13      0        0         13
adato-tracker          249      0        0        249
manual input             5      0        0          5
-----------------------------------------------------
Total                  893      0        0        893
```

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
| **Upcoming (> today)** | Only still-open CFPs (`cfp_close` today or later). Your working list. |
| **Upcoming (> -30 days)** | Open CFPs plus those that closed in the last 30 days. |
| **Closed (90d)** | CFPs that closed 30 to 90 days ago, for recap. |
| **Short listed** | Notes you flagged `shortlist: true`. |
| **Dismissed (+dismissed)** | Only dismissed notes. The minus version is empty by definition. |
| **Archived (+dismissed) / Archived (-dismissed)** | Archived notes with or without dismissed notes. |
| **Submitted** | Notes with at least one wiki link under `submissions`. |
| **Conf in USA / Conf outside USA / Online** | Geography filters. |
| **Local events** | Events in The San Francisco Bay Area, which is my area (feel free to tweak it to yours). Matches local cities in `location`. |

## Sample Workflow

- Do a run to update CFPS.  See [quick start](#Quick-start)
- Check `cfps.base` in Obsidian
- Browse CFPs and shortlist the the one's you are interested in - by selecting the **short listed** flag
- Not interested in one? Add the property `dismissed: true` to its note. **(-dismissed)** views hide it immediately. The corresponding **(+dismissed)** view still shows it. No pipeline run is needed. The note stays in `data/`, so your notes and history survive a refresh. Clear the flag to bring it back. **Dismissed (+dismissed)** lists all dismissed notes.

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
python3 src/process-adato-tracker.py --out data
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
| **adato-tracker** | The `tablesorter` table on [adatosystems.com/cfp-tracker](https://adatosystems.com/cfp-tracker/) (Leon Adato). Clean ISO dates, event + CFP URLs, city/state; no topics or benefits. It aggregates the other feeds, so it ranks lowest and only fills gaps. |
| **`input/*.md`** | Hand-curated rows, merged by `src/process-manual-input.py`. |

If two sources carry the same conference, the higher-priority one owns the note: `manual` > `developers.events` > `cfp.ninja` > `confs.tech` > `adato-tracker`.

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
