"""`nightly`: the night run (docs/decisions/2026-10-14-verify-affected.md, #159).

Brings a dedicated worktree of origin/main up to date (created if missing; never the main checkout or a task
worktree), runs `verify --full` there with the log in this checkout's tools/out/nightly/<date>.log, and writes a
one-line summary (green or red, time, red files) to tools/out/nightly/summary.log. Red: opens, or comments on the
open, GitHub issue NIGHTLY_TITLE with the red files and the log's tail. Green: no issue. The art manager runs it
each night in the background; it may take as long as `verify --full` (about 10 minutes).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import common

NAME = "nightly"
HELP = "the night run: verify --full on an up-to-date origin/main worktree; a red run opens or updates an issue"
NIGHTLY_TITLE = "nightly: verify --full is red on main"
WORKTREE_NAME = "nightly"
REMOTE = "origin"
BRANCH = "main"
VERIFY_TIMEOUT = 3 * 3600
GIT_TIMEOUT = 900
TAIL_LINES = 40
OUT = common.ROOT / "tools" / "out" / "nightly"

_RED_LINE = re.compile(r"^\s*RED\s+[\d.]+ s\s+(\S+)\s*$", re.M)
_TESTS_LINE = re.compile(r"^tests: .*$", re.M)
_RED_AT = re.compile(r"red at ([\w-]+)")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--worktree", type=Path, help="the night worktree (default: <main checkout>-wt/nightly)")
    parser.add_argument("--no-issue", action="store_true", help="print the issue text instead of filing it")


# --- Pure parts (tested) --------------------------------------------------------------------------------------------


def default_worktree(main_checkout: Path) -> Path:
    """The night worktree beside the task worktrees: D:/prime-game-art -> D:/prime-game-art-wt/nightly."""
    return main_checkout.parent / f"{main_checkout.name}-wt" / WORKTREE_NAME


def check_worktree_path(path: Path, main_checkout: Path) -> None:
    """Refuses the main checkout, a path inside it, and any folder not named WORKTREE_NAME (a task worktree)."""
    target = path.resolve()
    main = main_checkout.resolve()
    if target == main or main in target.parents:
        raise common.Failure(f"{path} is the main checkout or inside it; the night run needs its own worktree")
    if target.name != WORKTREE_NAME:
        raise common.Failure(f"{path}: the night worktree's folder must be named {WORKTREE_NAME!r}")


@dataclass
class Outcome:
    green: bool
    seconds: float
    red_files: list[str] = field(default_factory=list)
    red_step: str = ""
    tests_line: str = ""


def parse_log(text: str, returncode: int, seconds: float) -> Outcome:
    """The night run's outcome from verify's log: the RED file lines, the red step, the tests line."""
    red_files = sorted(set(_RED_LINE.findall(text)))
    tests = _TESTS_LINE.findall(text)
    red_at = _RED_AT.findall(text)
    step = red_at[-1] if red_at else ("" if returncode == 0 else f"exit {returncode}")
    return Outcome(returncode == 0, seconds, red_files, "" if returncode == 0 else step, tests[-1] if tests else "")


def summary_line(date: str, commit: str, outcome: Outcome) -> str:
    """One line: date, commit, green or red, minutes, and the red step and files."""
    head = f"nightly {date} {commit[:9]}: {'green' if outcome.green else 'red'} in {outcome.seconds / 60:.1f} min"
    if outcome.green:
        return head + (f" ({outcome.tests_line})" if outcome.tests_line else "")
    files = ", ".join(outcome.red_files) if outcome.red_files else "none (see the log)"
    return f"{head}; red at {outcome.red_step or 'an unknown step'}; red files: {files}"


def tail(text: str, lines: int = TAIL_LINES) -> str:
    return "\n".join(text.rstrip().splitlines()[-lines:])


def issue_text(date: str, commit: str, outcome: Outcome, log: Path, log_text: str) -> str:
    """The issue body or comment for a red night run."""
    files = "\n".join(f"- `{name}`" for name in outcome.red_files) or "- none: the red step is not a test file"
    return (
        f"The night run of {date} is red: `verify --full` on `{BRANCH}` at {commit}.\n\n"
        f"{summary_line(date, commit, outcome)}\n\n"
        f"Red step: {outcome.red_step or 'unknown'}\n\n"
        f"Red files:\n{files}\n\n"
        f"Log (on the desktop): `{log}`\n\n"
        f"The log's last {TAIL_LINES} lines:\n\n```text\n{tail(log_text)}\n```\n\n"
        "A fix task for the art manager (docs/decisions/2026-10-14-verify-affected.md).\n"
    )


def open_issue_number(issues_json: str, title: str = NIGHTLY_TITLE) -> int | None:
    """The number of the open issue with exactly this title in `gh issue list --json number,title` output."""
    for item in json.loads(issues_json or "[]"):
        if item.get("title") == title:
            return int(item["number"])
    return None


def log_path(out: Path, date: str) -> Path:
    """out/<date>.log, or <date>-2.log and so on when a run of that date exists (never overwrites a log)."""
    path, n = out / f"{date}.log", 2
    while path.exists():
        path, n = out / f"{date}-{n}.log", n + 1
    return path


# --- The run --------------------------------------------------------------------------------------------------------


def _git(*args: str, cwd: Path | None = None) -> str:
    result = common.run(["git", "-C", str(cwd or common.ROOT), *args], timeout=GIT_TIMEOUT, heavy=False)
    if result.returncode != 0:
        raise common.Failure(f"git {' '.join(args)}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def _main_checkout() -> Path:
    common_dir = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common_dir.parent


def _worktrees() -> list[Path]:
    out = _git("worktree", "list", "--porcelain")
    return [Path(line[len("worktree "):]) for line in out.splitlines() if line.startswith("worktree ")]


def prepare(path: Path) -> str:
    """Fetches origin/main and puts the night worktree on it (detached); returns the commit."""
    _git("fetch", REMOTE, BRANCH)
    ref = f"{REMOTE}/{BRANCH}"
    _git("worktree", "prune")  # forgets a night worktree whose folder was deleted
    known = [w.resolve() for w in _worktrees()]
    if path.resolve() not in known:
        if path.exists() and any(path.iterdir()):
            raise common.Failure(f"{path} exists, is not a worktree of this repo and is not empty")
        common.say(f"nightly: creating the worktree {path}")
        _git("worktree", "add", "--detach", str(path), ref)
    else:
        dirty = _git("status", "--porcelain", "--untracked-files=no", cwd=path)
        if dirty:
            raise common.Failure(f"{path} has local changes; the night worktree is never edited by hand:\n{dirty}")
        _git("checkout", "--detach", ref, cwd=path)
    return _git("rev-parse", "HEAD", cwd=path)


def file_issue(text: str) -> str:
    """Comments on the open nightly issue, or opens one; returns its URL or number."""
    body = OUT / "issue.md"
    body.write_text(text, encoding="utf-8", newline="\n")
    listed = common.run(
        ["gh", "issue", "list", "--state", "open", "--search", f'"{NIGHTLY_TITLE}" in:title', "--json", "number,title"],
        timeout=120,
        cwd=common.ROOT,
    )
    if listed.returncode != 0:
        raise common.Failure(f"gh issue list: {listed.stderr.strip()}")
    number = open_issue_number(listed.stdout)
    if number is not None:
        cmd = ["gh", "issue", "comment", str(number), "--body-file", str(body)]
    else:
        cmd = ["gh", "issue", "create", "--title", NIGHTLY_TITLE, "--body-file", str(body)]
    result = common.run(cmd, timeout=120, cwd=common.ROOT)
    if result.returncode != 0:
        raise common.Failure(f"{' '.join(cmd[:3])}: {result.stderr.strip()}")
    return result.stdout.strip() or f"#{number}"


def run(args: argparse.Namespace) -> int:
    main = _main_checkout()
    path = args.worktree or default_worktree(main)
    check_worktree_path(path, main)
    commit = prepare(path)
    OUT.mkdir(parents=True, exist_ok=True)
    date = time.strftime("%Y-%m-%d")
    log = log_path(OUT, date)
    common.say(f"nightly: verify --full in {path} at {commit[:9]}; log {log}")
    started = time.monotonic()
    with log.open("w", encoding="utf-8", newline="\n") as handle:
        try:
            code = subprocess.run(
                [common.python(), str(path / "tools" / "run.py"), "verify", "--full"],
                cwd=path,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=VERIFY_TIMEOUT,
            ).returncode
        except subprocess.TimeoutExpired:
            code = 124
            handle.write(f"\nnightly: verify --full did not finish in {VERIFY_TIMEOUT} s\n")
    text = log.read_text(encoding="utf-8", errors="replace")
    outcome = parse_log(text, code, time.monotonic() - started)
    line = summary_line(date, commit, outcome)
    with (OUT / "summary.log").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    common.say(line)
    if outcome.green:
        return 0
    body = issue_text(date, commit, outcome, log, text)
    if args.no_issue:
        common.say(body)
    else:
        common.say(f"nightly: issue {file_issue(body)}")
    return 1
