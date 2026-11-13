"""Canonical source registry and side-effect-free collection for a full refresh."""
from __future__ import annotations

import datetime
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class SourceSpec:
    name: str
    script: str
    priority: int


# The priority belongs here, not in the writer and wrapper independently. Lower
# numbers describe richer sources and win when current rows identify one CFP.
SOURCE_SPECS = (
    SourceSpec("developers.events", "process-developer-events.py", 1),
    SourceSpec("cfp.ninja", "process-cfp-ninja.py", 2),
    SourceSpec("confs.tech", "process-confs-tech.py", 3),
    SourceSpec("adato-tracker", "process-adato-tracker.py", 4),
    SourceSpec("open-tech-cfps", "process-open-tech-cfps.py", 5),
    SourceSpec("manual", "process-manual-input.py", 0),
)
SOURCE_NAMES = tuple(spec.name for spec in SOURCE_SPECS)
SOURCE_SCRIPTS = {spec.name: spec.script for spec in SOURCE_SPECS}
SOURCE_PRIORITY = {spec.name: spec.priority for spec in SOURCE_SPECS}


@dataclass(frozen=True)
class RunContext:
    today: datetime.date
    cutoff: datetime.date
    cache: Path
    input_dir: Path
    offline: bool = False


_MODULES = {}


def load_source(name: str):
    """Load a hyphenated adapter once without executing its CLI entry point."""
    if name not in SOURCE_SCRIPTS:
        raise ValueError(f"unknown CFP source: {name!r}")
    if name not in _MODULES:
        module_name = "cfp_source_" + name.replace(".", "_").replace("-", "_")
        spec = importlib.util.spec_from_file_location(
            module_name, SRC_DIR / SOURCE_SCRIPTS[name]
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"could not load CFP source {name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        _MODULES[name] = module
    return _MODULES[name]


def collect_source(name: str, context: RunContext) -> list[dict]:
    """Return complete normalized rows for *name*, or raise before note writes."""
    module = load_source(name)
    if name == "developers.events":
        return module.collect_rows(context.cutoff, context.cache, context.offline)
    if name == "cfp.ninja":
        rows = module.collect_rows(
            context.cutoff, context.today, context.cache, offline=context.offline
        )
    elif name == "confs.tech":
        rows = module.collect_rows(
            context.cutoff, context.today, context.cache, offline=context.offline
        )
    elif name == "adato-tracker":
        rows = module.collect_rows(
            context.cutoff, context.today, context.cache, offline=context.offline
        )
    elif name == "open-tech-cfps":
        rows = module.collect_rows(context.cutoff, context.cache, offline=context.offline)
    elif name == "manual":
        return module.collect_rows(
            context.input_dir,
            cache=context.cache,
            today=context.today,
            offline=context.offline,
        )
    else:  # Registry validation makes this unreachable.
        raise ValueError(f"unsupported CFP source: {name!r}")
    return [{**row, "source": name} for row in rows]


def collect_all(names, context: RunContext) -> dict[str, list[dict]]:
    """Collect every enabled source before the caller changes any notes."""
    return {name: collect_source(name, context) for name in names}


def cutoff_for(
    today: datetime.date, months_back: int = 1, past_days: int | None = None
) -> datetime.date:
    """Resolve the one lookback policy used by every network source."""
    days = past_days if past_days is not None else 30 * max(1, months_back)
    return today - datetime.timedelta(days=days)
