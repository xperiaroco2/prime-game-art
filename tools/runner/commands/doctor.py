"""`doctor [--quick]`: checks this PC for the art pipeline and prints a fix for every failure.

Python, git, Git LFS and the hooks path (set here to tools/githooks), Blender at the pin, glTF-Validator, Godot, the
raw folders, `gh auth status`, and whether MESHY_API_KEY is set (yes or no, never the value). --quick skips launching
Blender, the validator, Godot and gh.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .. import common, pins

NAME = "doctor"
HELP = "check the environment and print fixes (--quick: skip launching tools)"

HOOKS_PATH = "tools/githooks"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--quick", action="store_true", help="only check that tools exist; do not launch them")


class Report:
    def __init__(self) -> None:
        self.failures = 0

    def ok(self, text: str) -> None:
        common.ok(text)

    def bad(self, text: str, fix: str) -> None:
        self.failures += 1
        common.bad(text, fix)

    def warn(self, text: str) -> None:
        common.warn(text)


def _run(
    cmd: list[str | Path], timeout: float = 60, cwd: Path | None = None
) -> subprocess.CompletedProcess[str] | None:
    """Runs cmd; None when it cannot start or times out. Never waits for the heavy-run lock (version probes only)."""
    try:
        return common.run([str(c) for c in cmd], timeout, cwd, heavy=False)
    except (OSError, common.Failure):
        return None


def _first_line(result: subprocess.CompletedProcess[str] | None) -> str:
    text = ((result.stdout or "") + (result.stderr or "")).strip() if result else ""
    return text.splitlines()[0].strip() if text else ""


def check_python(report: Report) -> None:
    version = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info >= pins.PYTHON_MIN:
        report.ok(f"Python {version} ({sys.executable})")
    else:
        need = ".".join(map(str, pins.PYTHON_MIN))
        report.bad(f"Python {version} is older than {need}", f"Install Python {need} or newer and set PYTHON_BIN to it")


def check_git(report: Report) -> None:
    result = _run(["git", "--version"])
    if result and result.returncode == 0:
        report.ok(_first_line(result))
    else:
        report.bad("git not found", "Install Git for Windows (https://git-scm.com) and reopen the terminal")
        return
    lfs = _run(["git", "lfs", "version"])
    if not (lfs and lfs.returncode == 0):
        report.bad(
            "Git LFS not found", "Install Git LFS (it comes with Git for Windows), then: git lfs install --skip-repo"
        )
        return
    report.ok(_first_line(lfs))
    filt = _run(["git", "-C", common.ROOT, "config", "--get", "filter.lfs.process"])
    if filt and filt.returncode == 0 and filt.stdout.strip():
        report.ok("Git LFS filters are configured")
    else:
        report.bad("Git LFS filters are not configured", "Run: git lfs install --skip-repo")


def ensure_hooks_path(report: Report, repo: Path) -> None:
    """Sets core.hooksPath to tools/githooks (repository-wide: every worktree shares it) unless it already is."""
    if not (repo / HOOKS_PATH / "pre-push").is_file():
        report.bad(
            f"{HOOKS_PATH}/pre-push is missing in {repo.as_posix()}", "Check out a branch that has tools/githooks"
        )
        return
    current = _run(["git", "-C", repo, "config", "--get", "core.hooksPath"])
    value = current.stdout.strip() if current and current.returncode == 0 else ""
    if value == HOOKS_PATH:
        report.ok(f"core.hooksPath is {HOOKS_PATH}")
        return
    result = _run(["git", "-C", repo, "config", "core.hooksPath", HOOKS_PATH])
    if result and result.returncode == 0:
        was = f" (was {value!r})" if value else ""
        report.ok(f"core.hooksPath set to {HOOKS_PATH}{was}")
    else:
        report.bad("could not set core.hooksPath", f"Run: git -C {repo.as_posix()} config core.hooksPath {HOOKS_PATH}")


def check_blender(report: Report, quick: bool) -> None:
    path = common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)
    fix = (
        f"Blender {pins.BLENDER} LTS is the portable zip {pins.BLENDER_URL} (SHA-256 {pins.BLENDER_ZIP_SHA256}),\n"
        f"unpacked to {pins.BLENDER_DEFAULT}'s folder, or set {pins.BLENDER_ENV}. Downloads need the engineer's yes."
    )
    if not path or not path.is_file():
        report.bad(f"Blender not found at {path}", fix)
        return
    if quick:
        report.ok(f"Blender at {path.as_posix()} (version not checked: --quick)")
        return
    result = _run([path, "-b", "--factory-startup", "--version"], timeout=120)
    line = _first_line(result)
    if result and result.returncode == 0 and line.startswith(f"Blender {pins.BLENDER}"):
        report.ok(f"{line.split(' (')[0]} at {path.as_posix()}")
    else:
        report.bad(f"Blender at {path.as_posix()} says {line or 'nothing'!r}, not {pins.BLENDER}", fix)


def check_gltf_validator(report: Report, quick: bool) -> None:
    path = common.tool_path(pins.GLTF_VALIDATOR_ENV, pins.GLTF_VALIDATOR_DEFAULT)
    fix = (
        f"glTF-Validator {pins.GLTF_VALIDATOR} is {pins.GLTF_VALIDATOR_URL}\n"
        f"(zip SHA-256 {pins.GLTF_VALIDATOR_ZIP_SHA256}), unpacked to {pins.GLTF_VALIDATOR_DEFAULT}'s folder, or set "
        f"{pins.GLTF_VALIDATOR_ENV}. Downloads need the engineer's yes."
    )
    if not path or not path.is_file():
        report.bad(f"glTF-Validator not found at {path}", fix)
        return
    if quick:
        report.ok(f"glTF-Validator at {path.as_posix()} (version not checked: --quick)")
        return
    line = _first_line(_run([path, "--version"]))
    if line.endswith(f"version {pins.GLTF_VALIDATOR}"):
        report.ok(f"{line} at {path.as_posix()}")
    else:
        report.bad(f"glTF-Validator at {path.as_posix()} says {line or 'nothing'!r}, not {pins.GLTF_VALIDATOR}", fix)


def check_godot(report: Report, quick: bool) -> None:
    path = common.tool_path(pins.GODOT_ENV, None)
    fix = (
        f"Set {pins.GODOT_ENV} to the Godot {pins.GODOT} console exe the game repo uses"
        " (D:/prime-game: tools\\run.cmd doctor)"
    )
    if not path or not path.is_file():
        report.bad(f"Godot not found ({pins.GODOT_ENV} is {str(path) if path else 'not set'})", fix)
        return
    if quick:
        report.ok(f"Godot at {path.as_posix()} (version not checked: --quick)")
        return
    result = _run([path, "--headless", "--version"])
    text = ((result.stdout or "") if result else "").strip()
    version = text.splitlines()[-1].strip() if text else ""
    if version.startswith(pins.GODOT_VERSION_PREFIX):
        report.ok(f"Godot {version} at {path.as_posix()}")
    else:
        report.bad(f"Godot at {path.as_posix()} says {version or 'nothing'!r}, not {pins.GODOT_VERSION_PREFIX}", fix)


def check_raw_folders(report: Report) -> None:
    raw = common.raw_dir()
    if raw.is_dir():
        report.ok(f"raw folder {raw.as_posix()}")
    else:
        report.bad(
            f"raw folder {raw.as_posix()} is missing",
            f'Create it: New-Item -ItemType Directory "{raw}" (or set {pins.RAW_ENV})',
        )
    backup = common.raw_backup_dir()
    if backup is None:
        report.bad("raw backup folder unknown: OneDrive is not set", f"Set {pins.RAW_BACKUP_ENV} to the backup folder")
    elif backup.is_dir():
        report.ok(f"raw backup folder {backup.as_posix()}")
    else:
        report.bad(
            f"raw backup folder {backup.as_posix()} is missing",
            f'Create it: New-Item -ItemType Directory "{backup}" (or set {pins.RAW_BACKUP_ENV})',
        )


def check_gh(report: Report, quick: bool) -> None:
    if not shutil.which("gh"):
        report.bad("GitHub CLI (gh) not found", "Install it from https://cli.github.com, then: gh auth login")
        return
    if quick:
        report.ok("gh found (auth not checked: --quick)")
        return
    result = _run(["gh", "auth", "status", "--hostname", "github.com"], timeout=30)
    if result and result.returncode == 0:
        report.ok("gh is logged in to github.com")
    else:
        report.bad("gh is not logged in to github.com", "Run: gh auth login (the engineer, in their own terminal)")


def check_meshy_key(report: Report) -> None:
    """Says only whether the key is set; the value is never printed, logged or stored."""
    if common.env(pins.MESHY_KEY_ENV):
        report.ok(f"{pins.MESHY_KEY_ENV} is set: yes")
    else:
        report.warn(
            f"{pins.MESHY_KEY_ENV} is set: no"
            " (needed only to generate; the engineer sets it as a user environment variable)"
        )


def run(args: argparse.Namespace) -> int:
    report = Report()
    common.say(f"doctor{' --quick' if args.quick else ''}: {common.ROOT.as_posix()}")
    check_python(report)
    check_git(report)
    ensure_hooks_path(report, common.ROOT)
    check_blender(report, args.quick)
    check_gltf_validator(report, args.quick)
    check_godot(report, args.quick)
    check_raw_folders(report)
    check_gh(report, args.quick)
    check_meshy_key(report)
    if report.failures:
        common.say(f"doctor: {report.failures} problem(s); fix them as shown above")
        return 1
    common.say("doctor: all good")
    return 0
