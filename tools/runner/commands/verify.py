"""`verify`: the definition-of-done gate (docs/decisions/2026-10-14-verify-affected.md).

`verify` runs every fast test file, the heavy (Blender, Godot) test files the change needs against --base (default
origin/main; tools/tests/areas.toml), then manifest-check. `verify --full` runs every test file: the night run on main.
It stops at the first red step.
"""

from __future__ import annotations

import argparse
import subprocess
import time

from .. import common
from . import _testrun

NAME = "verify"
HELP = "the definition-of-done gate: fast tests, the heavy tests a change needs (--full: all), manifest-check"
STEPS: tuple[str, ...] = ("selftest", "manifest-check")
TIMEOUT = 3600
DEFAULT_BASE = "origin/main"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--full", action="store_true", help="every test file (the night run on main)")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"compare against this ref (default {DEFAULT_BASE})")
    parser.add_argument("-j", "--jobs", type=int, default=0, help="fast files at a time (default: half the CPUs)")
    parser.add_argument("-v", "--verbose", action="store_true", help="every file's time and test names")


def choose(full: bool, base: str) -> tuple[list[str], list[str]]:
    """The fast and heavy test files to run; prints the heavy selection and why."""
    fast, heavy = _testrun.split([p.name for p in _testrun.test_files()])
    if full:
        common.say(f"verify: full run, {len(fast)} fast and {len(heavy)} heavy test files")
        return fast, heavy
    try:
        changed = _testrun.changed_files(base)
    except common.Failure as exc:
        common.say(f"verify: no diff against {base} ({exc}); running every heavy file")
        return fast, heavy
    sel = _testrun.select(changed, _testrun.load_areas(), heavy)
    common.say(f"verify: affected run against {base}: {len(changed)} changed files")
    if sel.full:
        common.say(f"verify: the full suite: {sel.full_reason}")
    elif not sel.heavy:
        common.say(f"verify: no heavy file selected ({len(heavy)} skipped as unaffected)")
    else:
        for name, reasons in sorted(sel.heavy.items()):
            extra = f" (+{len(reasons) - 1} more)" if len(reasons) > 1 else ""
            common.say(f"verify: heavy {name}: {reasons[0]}{extra}")
    return fast, [name for name in heavy if name in sel.heavy]


def run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    common.say("== verify: selftest")
    fast, heavy = choose(args.full, args.base)
    results = _testrun.run_files(fast, heavy, args.verbose, args.jobs or None)
    if any(r.returncode != 0 for r in results) or len(results) != len(fast) + len(heavy):
        raise common.Failure("red at selftest; fix it and run verify again")
    common.say(f"== verify: selftest green ({time.monotonic() - started:.1f} s)")
    common.say("== verify: manifest-check")
    step_start = time.monotonic()
    try:
        result = subprocess.run(
            [common.python(), str(common.ROOT / "tools" / "run.py"), "manifest-check"], cwd=common.ROOT, timeout=TIMEOUT
        )
    except subprocess.TimeoutExpired as exc:
        raise common.Failure(f"manifest-check did not finish in {TIMEOUT} s") from exc
    if result.returncode != 0:
        raise common.Failure(f"red at manifest-check (exit {result.returncode}); fix it and run verify again")
    common.say(f"== verify: manifest-check green ({time.monotonic() - step_start:.1f} s)")
    mode = "full" if args.full else "affected"
    common.say(f"verify: green ({mode}: selftest, manifest-check) in {time.monotonic() - started:.0f} s")
    return 0
