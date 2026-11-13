# CFP Tracker
#cfp #conference

CFP Tracker collects conference Calls for Papers (CFPs) from public sources, and saves them to Obsidian.

> This is a personal pipeline, not a(nother) CFP index. 
> Thank you to all the CFP site maintainers whose public feeds, datasets, calendars, and CFP pages make this project possible.

## Contents

- [Setup](#setup)
- [Configure](#configure)
- [Refresh the CFPs](#refresh-the-cfps)
- [Browse in Obsidian](#browse-in-obsidian)
- [Conference prestige](#conference-prestige)
- [Sources](#sources)
- [Development](#development)

## Quickstart

### 1 - Get the code

You need Python 3.10+ env.

```bash
git clone git@github.com:sujee/cfp-tracker.git
cd cfp-tracker

# Link the note folders to your Obsidian vault.
ln -s /path/to/your-vault/cfps/data data
ln -s /path/to/your-vault/cfps/archived archived

# Create your personal configuration.
cp src/config_local.example.py src/config_local.py
```

### 2 - Python setup

With uv (recommended)

```bash
uv sync
```

Without uv

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


### 3 - Configure (Optional)

[`src/config.py`](src/config.py) contains the defaults. 

You can customize as below; only customize what you need to overwrite

```bash
cp   src/config_local.example.py    src/config_local.py  # <- gitignored
```

You can configure:

- Sources to fetch with `INPUT_SOURCES`.
- confs.tech topics with `CONFS_TECH_TOPICS`.
- Manual files under `input/` with `MANUAL_INPUT_FILES`.
- Event types to retain with `EVENT_TYPES`.
- Event names and topics to reject with `IGNORE_NAMES` and `IGNORE_TOPICS`.

### 4 - Refresh the CFPs!

**Option-1 (easy): Using an agent**

Open an agent in this folder. Then enter:

```text
update cfps
```

That's it!

**Option 2: To run the pipeline yourself:**

```bash
# Write notes outside the vault for an isolated check.
uv run python src/process-all.py --out /tmp/cfp-scratch --no-archive

# Refresh the notes in your vault.
uv run python src/process-all.py

# Reproduce a run from cached source responses.
uv run python src/process-all.py --offline --today 2026-11-02
```

The run prints a summary for each source. It also prints an event-type matrix.

The pipeline collects every enabled source before it writes notes. A source error stops the run before note changes. The reconciler migrates curated fields when a note changes its path or source. Archive moves never overwrite existing archived notes.

Live fetches update the cache. A failed fetch uses a valid cached response. `--offline` requires cached responses and disables network access. Shared filters and dates apply to every source.

Use `uv run python src/process-all.py --help` to see all options.

## Browse in Obsidian

Copy [`cfps.base`](cfps.base) into your vault. Copy
[`cfps-dashboard.md`](cfps-dashboard.md) too if you want summary tables.

The base requires Obsidian Bases. The dashboard requires the Dataview plugin.

The base reads notes from `data/`. The archive views read notes from `archived/`. If your notes use
different folders, update the paths in both files.

Personalize the location views in the `formulas` section of `cfps.base`:

- Set `my_country` to the canonical `country` value for your notes.
- Edit `is_local_area` to list your local cities and area names.

## Typical workflow:

1. Refresh the CFPs.
2. Open **Upcoming** to find open CFPs.
3. Set `shortlist: true` for interesting events.
4. Set `dismissed: true` to hide an event from live views.
5. Add wiki links to `submissions` after you submit a talk.
6. To keep a source field you edited, add it to `curated_fields`, for example
   `curated_fields: [location]`. A source disagreement keeps your value and appears in the
   **Conflicts** view and the note's `## Conflict` section.

Most views let you include or exclude dismissed notes.

## Conference 'prestige'

[`prestige.md`](prestige.md) assigns optional reputation tiers. Tier 1 means flagship, tier 2 means major, and tier 3 means notable. The refresh adds these tiers to matching notes.

A tier describes the conference. Your shortlist describes your interest.

```bash
# Report prestige matches without changing notes.
uv run python src/apply-prestige.py --check
```

## Sources

The pipeline reads from various sources.

See [`docs/cfp-sources.md`](docs/cfp-sources.md) for source details and attribution.

## Development

Run the tests:

```bash
uv run python -m unittest discover -s tests -v
```

Project details:

- [`INSTRUCTIONS.md`](INSTRUCTIONS.md): refresh procedure and operating rules.
- [`AGENTS.md`](AGENTS.md): data shapes, configuration, and preservation rules.
- [`docs/spec.md`](docs/spec.md): historical specification from 2026-11-09.
  Use `INSTRUCTIONS.md` and `AGENTS.md` for current behavior.
