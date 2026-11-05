#!/usr/bin/env python3
"""Backwards-compat shim for the renamed developer.events parser.

New location: src/process-developer-events.py
This file is kept so existing instructions, cron jobs, and vault bookmarks
still work. It simply delegates to the new module.

Remove after 2027-03-01 once callers have migrated.
"""
import pathlib
import runpy

new_script = pathlib.Path(__file__).with_name("process-developer-events.py")
runpy.run_path(str(new_script), run_name="__main__")
