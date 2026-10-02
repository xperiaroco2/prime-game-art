"""Helpers for the probe and render commands: output folders, the fixture build and reading PNG sizes."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .. import blender, common

PROBE_OUT = common.OUT / "probe"
FIXTURES = common.OUT / "fixtures"
RENDERS = common.OUT / "renders"

# The fixtures make_fixture.py builds: file stem -> extra arguments.
FIXTURE_VARIANTS = {"humanoid": [], "humanoid_textured": ["--textured"]}


def make_fixtures(folder: Path = FIXTURES) -> list[Path]:
    """Builds every fixture variant into folder through headless Blender; returns the GLB paths."""
    made = []
    for stem, extra in FIXTURE_VARIANTS.items():
        blender.run_script("make_fixture.py", ["--out", str(folder), "--name", stem, *extra], timeout=300)
        path = folder / f"{stem}.glb"
        if not path.is_file():
            raise common.Failure(f"make_fixture.py wrote no {path}")
        made.append(path)
    return made


def render(model: Path, out: Path, cell: int = 512, anim: str = "", frames: int = 8, outline: bool = True) -> dict:
    """Renders model's review sheet into out and returns its stats.json."""
    args = [str(model), "--out", str(out), "--cell", str(cell)]
    if not outline:
        args.append("--no-outline")
    if anim:
        args += ["--anim", anim, "--frames", str(frames)]
    blender.run_script("render_views.py", args, timeout=1800)
    stats = out / "stats.json"
    if not stats.is_file():
        raise common.Failure(f"render_views.py wrote no {stats}")
    return json.loads(stats.read_text(encoding="utf-8"))


def png_size(path: Path) -> tuple[int, int]:
    """(width, height) from a PNG's IHDR chunk."""
    head = path.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise common.Failure(f"{path} is not a PNG")
    width, height = struct.unpack(">II", head[16:24])
    return width, height
