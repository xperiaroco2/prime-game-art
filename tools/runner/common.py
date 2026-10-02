"""Shared helpers: paths, output, environment lookups, tool locations, running processes with a hard timeout."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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


def run(cmd: list[str], timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Runs cmd, captures text output, kills it after timeout seconds (raises Failure then)."""
    try:
        return subprocess.run(
            [str(c) for c in cmd],
            cwd=str(cwd) if cwd else None,
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
