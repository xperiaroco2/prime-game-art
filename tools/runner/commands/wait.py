"""`wait <log> [--max S]`: wait at most S seconds for a background job's exit marker (docs/agents.md, rule 1; #55).

A workflow agent's prompt cache lives 5 minutes, so a tool call that blocks longer (verify, a Blender bake, a Godot
check) makes the agent's next call write its whole context again. An agent therefore starts a long job in the
background with the Bash tool, its output and then an exit marker going to a log:

    tools/run.sh verify > tools/out/verify.log 2>&1; echo "exit=$?" >> tools/out/verify.log

and polls it with `wait`, one tool call of at most S seconds each (default and maximum 170). The job is finished only
when the LAST complete non-empty line of the log is `exit=<n>`: the marker is the job's final write, a half-written
line (no newline yet) is never read, and a bare `exit=0` line in the job's own output is not mistaken for the end. Then
`wait` prints a short summary (the log's `verify:` lines, else its last TAIL_LINES non-empty lines) and returns n. Not
finished by the deadline: one "still running" line and 124. No log, or one it cannot read: 2.

Every line `wait` writes itself starts with "wait: ", so a job's own exit 2 or 124 is told apart by that line. It only
reads: it never writes, deletes or starts anything (a timeout leaves the job running).

A port of prime-game's tools/runner/wait.py (prime-game#303, #555) without its `--verified`.
"""

from __future__ import annotations

import argparse
import codecs
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from .. import common

NAME = "wait"
HELP = "wait at most 170 s for a background job's last line exit=<n>, print its summary and return n (124: running)"

# A poll every 3 minutes keeps a 5-minute cache warm: prime-game#555 measured about 94 s (p95) between wait's own
# deadline and the agent's next API call under load, so the step plus that stays under CACHE_TTL. A longer --max only
# brings that edge back: the step is the maximum too. It stays under the 180 s limit of one tool call (CLAUDE.md,
# "Shell"), leaving TOOL_CALL_MAX - DEFAULT_MAX for wait's start-up and its summary inside the same call.
DEFAULT_MAX = 170
TOOL_CALL_MAX = 180
MAX_ALLOWED = DEFAULT_MAX
CACHE_TTL = 300  # a workflow agent's prompt cache, in seconds
STILL_RUNNING = 124  # as coreutils' `timeout`
MISSING = 2  # no log, an unreadable one, or a bad --max (argparse's own errors are 2 too)
POLL_SECONDS = 3.0
APPEAR_GRACE = 10.0  # the background shell may not have created the log yet when the first wait starts
TAIL_LINES = 8
EXIT_LINE = re.compile(r"^exit=(\d+)$")
VERIFY_LINE = re.compile(r"^(== )?verify: ")  # verify's own lines, and the runner's "verify: <failure>"
MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("log", help="the background job's log; its last line exit=<n> marks the end")
    parser.add_argument(
        "--max", type=int, default=DEFAULT_MAX, metavar="S", help=f"seconds to wait, 1 to {MAX_ALLOWED} (default)"
    )


def run(args: argparse.Namespace) -> int:
    return main(args.log, args.max)


def native_path(text: str, windows: bool = os.name == "nt") -> Path:
    """The log's path for this Python: on Windows the Git Bash form /c/Users/... becomes C:/Users/...; other forms,
    spaces included, are kept."""
    text = os.path.expanduser(text)
    if windows:
        text = MSYS_DRIVE.sub(lambda m: m.group(1).upper() + ":", text, count=1)
    return Path(text)


def read_lines(path: Path) -> list[str] | None:
    """The log's complete lines (a trailing fragment without a newline is left out), or None when it is missing.
    UTF-16 with a BOM (PowerShell 5.1's `*>`) and UTF-8 with or without a BOM are read; CR line ends are dropped."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = data.decode("utf-16", errors="replace")
    else:
        text = data.decode("utf-8-sig", errors="replace")
    lines = text.split("\n")
    lines.pop()  # the part after the last newline: "" for a complete log, else a line still being written
    return [line.rstrip("\r") for line in lines]


def exit_code(lines: list[str]) -> int | None:
    """n when the last non-empty line is `exit=<n>`, else None (the job is still running)."""
    last = next((line for line in reversed(lines) if line.strip()), None)
    match = EXIT_LINE.match(last) if last is not None else None
    return int(match.group(1)) if match else None


def summary_lines(lines: list[str], tail: int = TAIL_LINES) -> list[str]:
    """What to print of a finished log: its `verify:` lines when it has any, else its last `tail` non-empty lines
    before the marker."""
    end = max(i for i, line in enumerate(lines) if line.strip())  # the marker
    body = lines[:end]
    verify = [line for line in body if VERIFY_LINE.match(line)]
    if verify:
        return verify
    return [line for line in body if line.strip()][-tail:]


def main(
    log: str,
    max_seconds: int = DEFAULT_MAX,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
    grace: float = APPEAR_GRACE,
    poll: float = POLL_SECONDS,
) -> int:
    say = common.say
    if not 1 <= max_seconds <= MAX_ALLOWED:
        say(f"wait: --max is 1 to {MAX_ALLOWED} s (a call over about {CACHE_TTL} s loses the 5-minute prompt cache)")
        return MISSING
    path = native_path(log)
    start = clock()
    deadline = start + max_seconds
    seen = False
    lines: list[str] | None = None
    while True:
        try:
            lines = read_lines(path)
        except OSError as error:  # a folder by mistake, a locked log: wait's own 2, never a traceback's 1
            say(f"wait: cannot read {path}: {error.strerror or error}")
            return MISSING
        if lines is None:
            if seen:
                say(f"wait: {path} disappeared during the wait (deleted, or another log name?)")
                return MISSING
            if clock() - start >= min(grace, max_seconds):
                hint = (
                    "; a Git Bash path such as /tmp is not visible to Windows programs: use a path under tools/out/"
                    if os.name == "nt" and log.startswith("/") and not MSYS_DRIVE.match(log)
                    else ""
                )
                say(f"wait: no log at {path} (did the background launch start?{hint})")
                return MISSING
        else:
            seen = True
            code = exit_code(lines)
            if code is not None:
                for line in summary_lines(lines):
                    say(line)
                say(f"wait: {path.name} finished: exit={code} (whole log: {path})")
                return code
        left = deadline - clock()
        if left <= 0:
            break
        sleep(min(poll, left))
    try:
        age = f"last written {max(0.0, now() - path.stat().st_mtime):.0f} s ago"
    except OSError:
        age = "not readable now"
    count = len(lines) if lines is not None else 0
    say(
        f"wait: still running after {clock() - start:.0f} s ({path}: {count} lines, {age}); "
        "call wait again, never start the job again"
    )
    return STILL_RUNNING
