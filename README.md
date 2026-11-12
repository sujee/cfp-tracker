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

With uv (recomemnded)

```bash
uv sync
```

Without uv

```
python -m venv
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
# dry run
uv run python src/process-all.py --out /tmp/cfp-scratch

# Refresh the notes in your vault.
uv run python src/process-all.py
```

The run prints a summary for each source. It also prints an event-type matrix. Use
`uv run python src/process-all.py --help` to see all options.

## Browse in Obsidian

Copy [`cfps.base`](cfps.base) into your vault. Copy
[`cfps-dashboard.md`](cfps-dashboard.md) too if you want summary tables.

The base reads notes from `data/`. The archive views read notes from `archived/`. If your notes use
different folders, update the paths in both files.

## Typical workflow:

1. Refresh the CFPs.
2. Open **Upcoming** to find open CFPs.
3. Set `shortlist: true` for interesting events.
4. Set `dismissed: true` to hide an event from live views.
5. Add wiki links to `submissions` after you submit a talk.

Most views let you include or exclude dismissed notes.

## Conference 'prestige'

[`prestige.md`](prestige.md) assigns optional reputation tiers. Tier 1 means flagship, tier 2 means
major, and tier 3 means notable. The refresh adds these tiers to matching notes.

A tier describes the conference. Your shortlist describes your interest.

```bash
# Report prestige matches without changing notes.
uv run python src/apply-prestige.py --check
```

## Sources

The pipeline reads:

- **developers.events** for live CFP and event JSON.
- **cfp.ninja** for CFPs, locations, topics, and speaker benefits.
- **confs.tech** for community conference data.
- **adato-tracker** for additional CFPs from Leon Adato's tracker.
- **Open Tech CFPs** for open and recently closed CFPs. Its data uses CC BY 4.0.
- **Manual input** for tables and checklists from your configured `input/` files.

See [`docs/cfp-sources.md`](docs/cfp-sources.md) for source details and attribution.

## Development

Run the tests:

```bash
uv run python -m unittest discover -s tests -v
```

Project details:

- [`INSTRUCTIONS.md`](INSTRUCTIONS.md): refresh procedure and operating rules.
- [`AGENTS.md`](AGENTS.md): data shapes, configuration, and preservation rules.
- [`docs/spec.md`](docs/spec.md): detailed pipeline specification.
