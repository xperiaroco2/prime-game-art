"""Shared helpers: paths, output, environment lookups, tool locations, running processes with a hard timeout."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import pins

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tools" / "out"
IS_WINDOWS = os.name == "nt"


class Failure(Exception):
    """A command failed; the message already tells the reader what to do."""


def say(text: str = "") -> None:
    print(text, flush=True)


def ok(text: str) -> None:
    say(f"  ok    {text}")


def bad(text: str, fix: str = "") -> None:
    say(f"  FAIL  {text}")
    for line in fix.splitlines():
        say(f"        -> {line}")


def warn(text: str) -> None:
    say(f"  warn  {text}")


def env(name: str) -> str | None:
    """A variable from the process environment, else (on Windows) from the user environment in the registry, so a
    variable the engineer set with [Environment]::SetEnvironmentVariable(..., "User") works without a restart."""
    value = os.environ.get(name)
    if value:
        return value
    if IS_WINDOWS:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, name)
                return str(value) or None
        except OSError:
            return None
    return None


def tool_path(env_name: str, default: str | None) -> Path | None:
    """The path a tool's variable names, else its default; None when neither is set."""
    value = env(env_name) or default
    return Path(value) if value else None


def blender_bin() -> Path:
    path = tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)
    if not path or not path.is_file():
        raise Failure(f"Blender {pins.BLENDER} not found at {path}; set {pins.BLENDER_ENV} or install it there")
    return path


def gltf_validator_bin() -> Path:
    path = tool_path(pins.GLTF_VALIDATOR_ENV, pins.GLTF_VALIDATOR_DEFAULT)
    if not path or not path.is_file():
        raise Failure(f"glTF-Validator not found at {path}; set {pins.GLTF_VALIDATOR_ENV} or install it there")
    return path


def godot_bin() -> Path:
    path = tool_path(pins.GODOT_ENV, None)
    if not path or not path.is_file():
        raise Failure(f"Godot {pins.GODOT} not found: set {pins.GODOT_ENV} to the console exe the game repo uses")
    return path


def raw_dir() -> Path:
    return Path(env(pins.RAW_ENV) or pins.RAW_DEFAULT)


def raw_backup_dir() -> Path | None:
    explicit = env(pins.RAW_BACKUP_ENV)
    if explicit:
        return Path(explicit)
    onedrive = env("OneDrive")
    return Path(onedrive) / pins.RAW_BACKUP_SUBDIR if onedrive else None


# --- The heavy-run lock: one Blender or Godot process at a time on this machine --------------------------------------
# Several workflows may run at once, but their Blender and Godot processes take turns (the engineer, 2026-10-09: one
# Blender batch at a time on the shared PC). The lock is an OS file lock in the raw folder, shared by every checkout and
# worktree on the machine, and released by the OS when its holder exits or dies; inside one runner process a thread
# lock serializes its threads first (anim-review and anim-set run Blender from thread pools). The children of a holder
# get HEAVY_HELD_ENV in their own environment and do not take the lock again (no deadlock); this process's
# environment is never changed. No raw folder (the laptop's raw-free lane): no lock.

HEAVY_LOCK_ENV = "ART_HEAVY_LOCK"  # a lock file path, or "off"
HEAVY_HELD_ENV = "ART_HEAVY_LOCK_HELD"
HEAVY_WAIT_ENV = "ART_HEAVY_LOCK_WAIT"  # the most seconds to wait for the lock
HEAVY_WAIT_DEFAULT = 7200.0
HEAVY_POLL = 2.0
HEAVY_NAMES = ("blender", "godot")
_HEAVY_THREADS = threading.Lock()


def is_heavy(cmd: list[str]) -> bool:
    """True when cmd starts Blender or Godot (by the executable's file name)."""
    return bool(cmd) and Path(str(cmd[0])).name.lower().startswith(HEAVY_NAMES)


def heavy_lock_path() -> Path | None:
    """The lock file, or None when the lock is off or there is no raw folder."""
    explicit = env(HEAVY_LOCK_ENV)
    if explicit:
        return None if explicit.lower() == "off" else Path(explicit)
    raw = raw_dir()
    return raw / "locks" / "heavy.lock" if raw.is_dir() else None


def heavy_env() -> dict[str, str]:
    """The environment for a child of a lock holder: this process's, plus HEAVY_HELD_ENV."""
    return {**os.environ, HEAVY_HELD_ENV: "1"}


def _try_lock(handle) -> bool:
    # The handle is never written, so the file stays empty and byte 0 is the locked region whatever append mode does.
    handle.seek(0)
    try:
        if IS_WINDOWS:
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle) -> None:
    handle.seek(0)
    try:
        if IS_WINDOWS:
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def heavy_lock(what: str, wait: float | None = None) -> Iterator[None]:
    """Holds the heavy-run lock for the block; waits at most wait seconds (ART_HEAVY_LOCK_WAIT, default 2 h), then
    raises Failure. A no-op when the lock is off, there is no raw folder, or a parent process holds it. Children
    started inside the block must get heavy_env() to skip it."""
    path = heavy_lock_path()
    if path is None or os.environ.get(HEAVY_HELD_ENV):
        yield
        return
    if wait is None:
        raw_wait = env(HEAVY_WAIT_ENV)
        try:
            wait = float(raw_wait) if raw_wait else HEAVY_WAIT_DEFAULT
        except ValueError:
            raise Failure(f"{HEAVY_WAIT_ENV}={raw_wait!r} is not a number of seconds") from None
    holder = path.with_name(path.name + ".holder")
    start = time.monotonic()
    if not _HEAVY_THREADS.acquire(timeout=wait):
        raise Failure(f"the heavy-run lock stayed taken inside this process for {wait:.0f} s")
    try:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(path, "a+b")
        except OSError as exc:
            raise Failure(f"cannot open the heavy-run lock {path}: {exc}") from exc
        with handle:
            told = False
            while not _try_lock(handle):
                waited = time.monotonic() - start
                if waited >= wait:
                    raise Failure(f"the heavy-run lock {path} stayed taken for {waited:.0f} s: {_read_holder(holder)}")
                if not told:
                    print(f"heavy-run lock: waiting for {_read_holder(holder)}", file=sys.stderr, flush=True)
                    told = True
                time.sleep(max(0.05, min(HEAVY_POLL, wait - waited)))
            if told:
                print(f"heavy-run lock: taken after {time.monotonic() - start:.0f} s", file=sys.stderr, flush=True)
            try:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                holder.write_text(f"pid {os.getpid()} since {stamp}: {what}\n", encoding="utf-8")
            except OSError:
                pass
            try:
                yield
            finally:
                _unlock(handle)
    finally:
        _HEAVY_THREADS.release()


def _read_holder(holder: Path) -> str:
    try:
        return holder.read_text(encoding="utf-8").strip() or "an unknown holder"
    except OSError:
        return "an unknown holder"


def run(
    cmd: list[str], timeout: float, cwd: Path | None = None, heavy: bool | None = None
) -> subprocess.CompletedProcess[str]:
    """Runs cmd, captures text output, kills it after timeout seconds (raises Failure then). A Blender or Godot cmd
    (is_heavy, or heavy=True) first takes the heavy-run lock; heavy=False skips it (a version probe). The timeout
    counts from the start of the process, not the wait."""
    if is_heavy(cmd) if heavy is None else heavy:
        with heavy_lock(" ".join(Path(str(c)).name if i == 0 else str(c) for i, c in enumerate(cmd[:6]))):
            return _run(cmd, timeout, cwd, heavy_env())
    return _run(cmd, timeout, cwd, None)


def _run(
    cmd: list[str], timeout: float, cwd: Path | None, child_env: dict[str, str] | None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(c) for c in cmd],
            cwd=str(cwd) if cwd else None,
            env=child_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise Failure(f"{Path(str(cmd[0])).name} did not finish in {timeout:.0f} s") from exc


def python() -> str:
    return sys.executable
