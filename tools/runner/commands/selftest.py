"""`selftest`: the runner's own tests (every task's tools/tests/test_*.py), each file in its own process: the fast
files in parallel, then the heavy ones (Blender, Godot) one at a time inside the heavy-run lock (_testrun.py)."""

from __future__ import annotations

import argparse

from .. import common
from . import _testrun

NAME = "selftest"
HELP = "run the runner's unit tests: fast files in parallel, then heavy files in the heavy-run lock"
DEFAULT_PATTERN = _testrun.DEFAULT_PATTERN


def command(verbose: bool = False, pattern: str = DEFAULT_PATTERN) -> list[str]:
    """One file's unittest command (discovery over tools/tests narrowed to pattern)."""
    return _testrun.unittest_command(pattern, verbose)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-v", "--verbose", action="store_true", help="name every test and every file's time")
    parser.add_argument("-p", "--pattern", default=DEFAULT_PATTERN, help="test file pattern (default test*.py)")
    parser.add_argument("-j", "--jobs", type=int, default=0, help="fast files at a time (default: half the CPUs)")
    parser.add_argument(
        "--write-timings", action="store_true", help="rewrite tools/tests/timings.json from this run (a full run)"
    )


def run(args: argparse.Namespace) -> int:
    names = [p.name for p in _testrun.test_files(args.pattern)]
    if not names:
        raise common.Failure(f"no test file matches {args.pattern!r}")
    fast, heavy = _testrun.split(names)
    results = _testrun.run_files(fast, heavy, args.verbose, args.jobs or None)
    if args.write_timings:
        _testrun.write_timings(results)
        common.say(f"wrote {_testrun.TIMINGS.relative_to(common.ROOT).as_posix()}")
    if any(r.returncode != 0 for r in results) or len(results) != len(names):
        raise common.Failure("tests failed (see above)")
    return 0
