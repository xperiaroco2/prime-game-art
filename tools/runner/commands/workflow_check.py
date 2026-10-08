"""`workflow-check`: refuses a workflow script that breaks the cost rules (docs/agents.md, #56).

Run by the manager before every launch. Each refusal is one line, `<file>:<line>: <reason>`.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from .. import common
from . import _workflow_lint as lint

NAME = "workflow-check"
HELP = "refuse workflow scripts that break the cost rules (docs/agents.md); run before every launch"
NODE_TIMEOUT = 60
NODE_LINE_RE = re.compile(r"\.mjs:(\d+)")
NODE_ERROR_RE = re.compile(r"^\w*Error: (.+)$", re.M)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("scripts", nargs="+", metavar="script.js", help="workflow scripts to check")


def node_check(path: Path, text: str) -> list[tuple[int, str]] | None:
    """`node --check` on a module copy of the script under tools/out/; None when node is missing."""
    node = shutil.which("node")
    if node is None:
        return None
    body = lint.module_copy(text.replace("\r\n", "\n"))
    if body is None:
        return []  # the meta refusal already names the problem
    out = common.OUT / "workflow-check"
    out.mkdir(parents=True, exist_ok=True)
    copy = out / f"{path.stem}.mjs"
    copy.write_text(body, encoding="utf-8", newline="\n")
    result = common.run([node, "--check", copy], timeout=NODE_TIMEOUT)
    if result.returncode == 0:
        return []
    line = NODE_LINE_RE.search(result.stderr)
    error = NODE_ERROR_RE.search(result.stderr)
    if error:
        reason = error.group(1)
    else:
        lines = result.stderr.strip().splitlines()
        reason = lines[-1] if lines else f"exit {result.returncode}"
    return [(int(line.group(1)) if line else 1, f"node --check: {reason}")]


def check_file(path: Path) -> tuple[list[tuple[int, str]], str | None]:
    """(refusals, note) for one script."""
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return [(0, "no such file")], None
    except UnicodeDecodeError:
        return [(1, "not UTF-8 text")], None
    found = lint.check_text(text)
    node = node_check(path, text)
    if node is None:
        return found, "node not found: node --check skipped"
    return sorted(found + node), None


def run(args: argparse.Namespace) -> int:
    refused = 0
    for name in args.scripts:
        path = Path(name)
        found, note = check_file(path)
        if note:
            common.warn(f"{path}: {note}")
        for line, reason in found:
            common.say(f"  FAIL  {path}:{line}: {reason}")
        if found:
            refused += 1
        else:
            common.ok(str(path))
    if refused:
        raise common.Failure(f"{refused} of {len(args.scripts)} script(s) refused; fix them before the launch")
    return 0
