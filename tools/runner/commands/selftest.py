"""`selftest`: the runner's own tests, unittest discovery over tools/tests (every task's test_*.py files)."""

from __future__ import annotations

import argparse
import subprocess

from .. import common

NAME = "selftest"
HELP = "run the runner's unit tests (unittest discovery over tools/tests)"
TIMEOUT = 1800
DEFAULT_PATTERN = "test*.py"


def command(verbose: bool = False, pattern: str = DEFAULT_PATTERN) -> list[str]:
    cmd = [common.python(), "-m", "unittest", "discover", "-s", "tools/tests", "-t", "tools", "-p", pattern]
    return cmd + (["-v"] if verbose else [])


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-v", "--verbose", action="store_true", help="name every test")
    parser.add_argument("-p", "--pattern", default=DEFAULT_PATTERN, help="test file pattern (default test*.py); a narrowed run does not hold the heavy-run lock")


def run(args: argparse.Namespace) -> int:
    try:
        if args.pattern == DEFAULT_PATTERN:
            # The full run holds the heavy-run lock: its Blender tests skip it, and the wait is outside the timeout.
            with common.heavy_lock("selftest"):
                result = subprocess.run(
                    command(args.verbose, args.pattern), cwd=common.ROOT, timeout=TIMEOUT, env=common.heavy_env()
                )
        else:
            # A narrowed run (-p) never waits for the lock up front: a pure-Python test file runs at once, and each
            # Blender or Godot process it starts takes the lock on its own.
            result = subprocess.run(command(args.verbose, args.pattern), cwd=common.ROOT, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise common.Failure(f"the tests did not finish in {TIMEOUT} s") from exc
    if result.returncode != 0:
        raise common.Failure("tests failed (see above)")
    return 0
