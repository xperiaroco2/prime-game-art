"""The test runner behind `selftest` and `verify` (#159, docs/decisions/2026-10-14-verify-affected.md).

Every test file under tools/tests runs in its own `python -m unittest` process. Fast files (no Blender, no Godot) run
in parallel; heavy files run after them, one at a time, inside the heavy-run lock. A file's class is read from its
text (HEAVY_MARKERS: it asks for the Blender or Godot binary), never from a hand-kept list. `verify` picks the heavy
files a change needs from tools/tests/areas.toml; every fast file always runs.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .. import common

TESTS = common.ROOT / "tools" / "tests"
AREAS = TESTS / "areas.toml"
TIMINGS = TESTS / "timings.json"
FILE_TIMEOUT = 1800
DEFAULT_PATTERN = "test*.py"
# A test file is heavy when it (or a tools/tests/_*.py helper it imports) looks the Blender or Godot binary up, the way
# its skip condition does (`tool_path(pins.BLENDER_ENV, ...)`, `tool_path("GODOT_BIN", ...)`), or starts one.
HEAVY_MARKERS = re.compile(
    r"(?:tool_path|have)\(\s*(?:pins\.(?:BLENDER|GODOT)_ENV|[\"'](?:BLENDER|GODOT)_BIN[\"'])|\b(?:blender|godot)_bin\(|\bblender\.run_script\("
)
_HELPER_IMPORT = re.compile(r"^\s*from\s+\.(?:\s+import\s+|(\w+)\s+import\s)(\w+)?", re.M)


# --- Classification -------------------------------------------------------------------------------------------------


def test_files(pattern: str = DEFAULT_PATTERN, tests: Path = TESTS) -> list[Path]:
    """The test files discovery would load for pattern, sorted by name."""
    return sorted(p for p in tests.glob("test*.py") if fnmatch.fnmatch(p.name, pattern))


def _helpers(text: str) -> set[str]:
    names = set()
    for match in _HELPER_IMPORT.finditer(text):
        name = match.group(1) or match.group(2)
        if name and name.startswith("_"):
            names.add(name)
    return names


def is_heavy_file(path: Path) -> bool:
    """True when the test file, or a tools/tests/_*.py helper it imports, matches HEAVY_MARKERS."""
    text = path.read_text(encoding="utf-8")
    if HEAVY_MARKERS.search(text):
        return True
    for helper in _helpers(text):
        helper_path = path.parent / f"{helper}.py"
        if helper_path.is_file() and HEAVY_MARKERS.search(helper_path.read_text(encoding="utf-8")):
            return True
    return False


# --- Selection --------------------------------------------------------------------------------------------------------


@dataclass
class Areas:
    shared: list[str]
    light: list[str]
    areas: dict[str, tuple[list[str], list[str]]]  # name -> (source patterns, test file patterns)


def load_areas(path: Path = AREAS) -> Areas:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    areas = {}
    for name, area in data.get("area", {}).items():
        areas[name] = (list(area["sources"]), list(area["tests"]))
    return Areas(list(data.get("shared", [])), list(data.get("light", [])), areas)


def matches(path: str, patterns: list[str]) -> bool:
    """fnmatch on the repo-relative POSIX path; `*` also crosses `/`."""
    return any(fnmatch.fnmatchcase(path, p) for p in patterns)


@dataclass
class Selection:
    full: bool = False
    full_reason: str = ""
    heavy: dict[str, list[str]] = field(default_factory=dict)  # selected heavy test file name -> reasons


def select(changed: list[str], areas: Areas, heavy_names: list[str]) -> Selection:
    """The heavy test files a change needs. changed: repo-relative POSIX paths (deleted files included);
    heavy_names: the heavy test files that exist. A shared module or an unmapped path selects the full suite."""
    sel = Selection()
    heavy_set = set(heavy_names)

    def pick(name: str, reason: str) -> None:
        if name in heavy_set:
            sel.heavy.setdefault(name, []).append(reason)

    for path in sorted(set(changed)):
        name = path.rsplit("/", 1)[-1]
        if matches(path, areas.shared):
            sel.full, sel.full_reason = True, f"{path} is shared (tools/tests/areas.toml)"
            break
        if path.startswith("tools/tests/") and fnmatch.fnmatch(name, "test*.py"):
            pick(name, f"{path} changed")
            continue
        hit = False
        for area, (sources, tests) in areas.areas.items():
            if matches(path, sources):
                hit = True
                for test in heavy_names:
                    if matches(test, tests):
                        pick(test, f"{path} (area {area})")
        if not hit and not matches(path, areas.light):
            sel.full, sel.full_reason = True, f"{path} is in no area of tools/tests/areas.toml"
            break
    if sel.full:
        sel.heavy = {name: [sel.full_reason] for name in heavy_names}
    return sel


def _git(root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise common.Failure(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(base: str, root: Path = common.ROOT) -> list[str]:
    """Paths changed since the merge base of base and HEAD, plus staged, unstaged and untracked ones (deleted files
    included); raises Failure when git cannot compare (an unknown base)."""
    paths = _git(root, "diff", "--name-only", "--no-renames", f"{base}...HEAD")
    paths += _git(root, "diff", "--name-only", "--no-renames", "HEAD")
    paths += _git(root, "ls-files", "--others", "--exclude-standard")
    return sorted(set(paths))


# --- Running ----------------------------------------------------------------------------------------------------------


@dataclass
class FileResult:
    name: str
    heavy: bool
    returncode: int
    seconds: float
    output: str
    launched: bool = False
    tests: int = 0
    skipped: int = 0


def unittest_command(name: str, verbose: bool = False) -> list[str]:
    cmd = [common.python(), "-m", "unittest", "discover", "-s", "tools/tests", "-t", "tools", "-p", name]
    return cmd + (["-v"] if verbose else [])


PROBES = common.ROOT / "tools" / "out" / "tests" / "probes"


def run_file(name: str, heavy: bool, verbose: bool = False, env: dict[str, str] | None = None) -> FileResult:
    """Runs one test file in its own process; FileResult.launched tells whether it started Blender or Godot."""
    PROBES.mkdir(parents=True, exist_ok=True)
    probe = PROBES / f"{name}.heavy"
    probe.unlink(missing_ok=True)
    started = time.monotonic()
    try:
        result = subprocess.run(
            unittest_command(name, verbose),
            cwd=common.ROOT,
            env={**(env if env is not None else os.environ), common.HEAVY_PROBE_ENV: str(probe)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FILE_TIMEOUT,
        )
        code, output = result.returncode, (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        code, output = 124, f"{name} did not finish in {FILE_TIMEOUT} s\n{exc.stdout or ''}{exc.stderr or ''}"
    out = FileResult(name, heavy, code, time.monotonic() - started, output, launched=probe.exists())
    if out.launched and not heavy:
        out.returncode = out.returncode or 3
        out.output += (
            f"\n{name} started Blender or Godot but reads as fast: name the tool the way the heavy files do "
            "(_testrun.HEAVY_MARKERS) so it runs in the heavy-run lock\n"
        )
    ran = re.findall(r"^Ran (\d+) tests?", output, re.M)
    out.tests = int(ran[-1]) if ran else 0
    skipped = re.findall(r"skipped=(\d+)", output)
    out.skipped = int(skipped[-1]) if skipped else 0
    return out


def jobs() -> int:
    """About half the CPUs, at least one."""
    return max(1, (os.cpu_count() or 2) // 2)


def _order(names: list[str]) -> list[str]:
    """Slowest first (from timings.json) so the pool's tail is short; unknown files first of all."""
    try:
        known = {row["file"]: row["seconds"] for row in json.loads(TIMINGS.read_text(encoding="utf-8"))["files"]}
    except (OSError, ValueError, KeyError, TypeError):
        known = {}
    return sorted(names, key=lambda n: (-known.get(n, 1e9), n))


def run_files(fast: list[str], heavy: list[str], verbose: bool = False, workers: int | None = None,
              runner=run_file) -> list[FileResult]:
    """Runs the fast files in a pool, then (only if they are green) the heavy files one at a time inside the heavy-run
    lock. Prints one line per red file as it ends (every file with verbose), each red file's output, and a summary."""
    results: list[FileResult] = []

    def report(res: FileResult) -> None:
        results.append(res)
        if res.returncode != 0 or verbose:
            common.say(f"  {'ok ' if res.returncode == 0 else 'RED'} {res.seconds:7.1f} s  {res.name}")

    started = time.monotonic()
    if fast:
        common.say(f"== tests: {len(fast)} fast files, {workers or jobs()} at a time")
        with ThreadPoolExecutor(max_workers=workers or jobs()) as pool:
            for res in pool.map(lambda n: runner(n, False, verbose, None), _order(fast)):
                report(res)
    if heavy and all(r.returncode == 0 for r in results):
        common.say(f"== tests: {len(heavy)} heavy files, one at a time in the heavy-run lock")
        with common.heavy_lock("tests: heavy files"):
            for name in _order(heavy):
                report(runner(name, True, verbose, common.heavy_env()))
    elif heavy:
        common.say(f"== tests: the fast files are red; the {len(heavy)} heavy files did not run")
    summary(results, time.monotonic() - started)
    return results


def summary(results: list[FileResult], seconds: float) -> None:
    red = [r for r in results if r.returncode != 0]
    for res in red:
        common.say(f"---- {res.name} (exit {res.returncode}) ----")
        common.say(res.output.rstrip())
    slow = sorted(results, key=lambda r: -r.seconds)[:5]
    common.say("slowest: " + ", ".join(f"{r.name} {r.seconds:.0f} s" for r in slow))
    common.say(
        f"tests: {len(results)} files, {sum(r.tests for r in results)} tests, "
        f"{sum(r.skipped for r in results)} skipped, {len(red)} red files, {seconds:.0f} s"
    )


def write_timings(results: list[FileResult], path: Path = TIMINGS) -> None:
    """Rewrites timings.json from a full run: per file its seconds and class (the fast pool's times run in parallel)."""
    rows = [
        {"file": r.name, "seconds": round(r.seconds, 1), "heavy": r.heavy, "launched": r.launched, "tests": r.tests}
        for r in sorted(results, key=lambda r: r.name)
    ]
    data = {"note": "per file of `selftest --write-timings`: wall seconds (fast files ran in parallel), class, whether it started Blender or Godot", "files": rows}
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")


def split(names: list[str], tests: Path = TESTS) -> tuple[list[str], list[str]]:
    fast, heavy = [], []
    for name in names:
        (heavy if is_heavy_file(tests / name) else fast).append(name)
    return fast, heavy

