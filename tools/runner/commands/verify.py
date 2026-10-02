"""`verify`: the definition-of-done gate. Runs selftest, then manifest-check, and stops at the first red step."""

from __future__ import annotations

import argparse
import subprocess
import time

from .. import common

NAME = "verify"
HELP = "run every check in order (selftest, manifest-check): the definition-of-done gate"
STEPS: tuple[str, ...] = ("selftest", "manifest-check")
TIMEOUT = 3600


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> int:
    runner = common.ROOT / "tools" / "run.py"
    for step in STEPS:
        common.say(f"== verify: {step}")
        started = time.monotonic()
        try:
            result = subprocess.run([common.python(), str(runner), step], cwd=common.ROOT, timeout=TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise common.Failure(f"{step} did not finish in {TIMEOUT} s") from exc
        if result.returncode != 0:
            raise common.Failure(f"red at {step} (exit {result.returncode}); fix it and run verify again")
        common.say(f"== verify: {step} green ({time.monotonic() - started:.1f} s)")
    common.say(f"verify: green ({', '.join(STEPS)})")
    return 0
