"""`mannequin`: builds our own low-poly base body by script in headless Blender (tools/blender/mannequin.py), one
folder per preset: a GLB, a .blend, clean orthographic reference images for image-to-3D and the 8-view review sheet.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _review

NAME = "mannequin"
HELP = "build our own low-poly base body (GLB, reference images, review sheet) for each preset"

# Must match PRESETS in tools/blender/mannequin.py (a test compares them).
PRESETS = ("base", "lanky", "bighead")


def default_out() -> Path:
    return common.raw_dir() / "mannequin"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset", choices=(*PRESETS, "all"), default="all", help="which preset (default all)")
    parser.add_argument("--out", type=Path, help="root folder; each preset goes to <out>/<preset>/ "
                                                 "(default D:/prime-art-raw/mannequin)")
    parser.add_argument("--size", type=int, default=1024, help="pixel size of the reference images (default 1024)")
    parser.add_argument("--cell", type=int, default=512, help="pixel size of one review-sheet view (default 512)")
    parser.add_argument("--no-refs", action="store_true", help="no reference images")
    parser.add_argument("--no-sheet", action="store_true", help="no review sheet")


def build(preset: str, out: Path, size: int = 1024, refs: bool = True) -> dict:
    """Runs tools/blender/mannequin.py for one preset into out; returns its info.json."""
    args = ["--preset", preset, "--out", out.as_posix(), "--size", str(size)]
    if not refs:
        args.append("--no-refs")
    info_path = out / "info.json"
    if info_path.exists():
        info_path.unlink()
    blender.run_script("mannequin.py", args, timeout=900)
    if not info_path.is_file():
        raise common.Failure(f"mannequin.py wrote no {info_path}")
    return json.loads(info_path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> int:
    if args.size < 64 or args.cell < 64:
        raise common.Failure("--size and --cell must be at least 64")
    root = (args.out or default_out()).resolve()
    presets = PRESETS if args.preset == "all" else (args.preset,)
    for preset in presets:
        out = root / preset
        info = build(preset, out, args.size, refs=not args.no_refs)
        parts = ", ".join(f"{name} {part['triangles']}" for name, part in info["objects"].items())
        common.say(f"{preset}: {info['triangles']} triangles ({parts}), height {info['height']} m, "
                   f"eyes at {info['eye_height']} m")
        common.say(f"  model: {info['glb']}")
        if "refs" in info:
            common.say(f"  references: {out / 'refs'} and {out / 'refs_flat'} (front, side, back; {args.size} px)")
        if not args.no_sheet:
            stats = _review.render(Path(info["glb"]), out / "sheet", args.cell)
            common.say(f"  sheet: {stats['sheet']}")
    return 0
