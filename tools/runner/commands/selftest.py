"""`selftest`: the runner's own tests, unittest discovery over tools/tests (every task's test_*.py files)."""

from __future__ import annotations

import argparse
import subprocess

from .. import common

NAME = "selftest"
HELP = "run the runner's unit tests (unittest discovery over tools/tests)"
TIMEOUT = 1800


def command(verbose: bool = False, pattern: str = "test*.py") -> list[str]:
    cmd = [common.python(), "-m", "unittest", "discover", "-s", "tools/tests", "-t", "tools", "-p", pattern]
    return cmd + (["-v"] if verbose else [])


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-v", "--verbose", action="store_true", help="name every test")
    parser.add_argument("-p", "--pattern", default="test*.py", help="test file pattern (default test*.py)")


def run(args: argparse.Namespace) -> int:
    try:
        result = subprocess.run(command(args.verbose, args.pattern), cwd=common.ROOT, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise common.Failure(f"the tests did not finish in {TIMEOUT} s") from exc
    if result.returncode != 0:
        raise common.Failure("tests failed (see above)")
    return 0
