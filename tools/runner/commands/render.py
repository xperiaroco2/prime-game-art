"""`render`: an 8-view review sheet and stats.json of a model, optionally an animation contact sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import common
from . import _review

NAME = "render"
HELP = "render a model (GLB, glTF, FBX, OBJ, .blend) into an 8-view review sheet and stats.json"

FORMATS = {".glb", ".gltf", ".fbx", ".obj", ".blend"}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("model", type=Path, help="the model file")
    parser.add_argument("--out", type=Path, help="output folder (default tools/out/renders/<model name>/)")
    parser.add_argument("--cell", type=int, default=512, help="pixel size of one square view (default 512)")
    parser.add_argument("--anim", metavar="ACTION", default="", help="also an animation contact sheet of this action")
    parser.add_argument("--frames", type=int, default=8, help="frames in the animation sheet (default 8)")


def find_model(model: Path) -> Path:
    for candidate in (model, common.ROOT / model):
        if candidate.is_file():
            return candidate.resolve()
    raise common.Failure(f"no model at {model}")


def run(args: argparse.Namespace) -> int:
    model = find_model(args.model)
    if model.suffix.lower() not in FORMATS:
        raise common.Failure(f"{model.name}: use one of {', '.join(sorted(FORMATS))}")
    if args.cell < 64:
        raise common.Failure("--cell must be at least 64")
    if args.frames < 1:
        raise common.Failure("--frames must be at least 1")
    out = (args.out or _review.RENDERS / model.stem).resolve()
    stats = _review.render(model, out, args.cell, args.anim, args.frames)
    size = stats["bounding_box"]["size"]
    common.say(f"{model.name}: {stats['triangles']} triangles, {stats['vertices']} vertices, {stats['objects']} objects, "
               f"{stats['materials']} materials, {stats['bones']} bones")
    common.say(f"  height {stats['height']} m, size {size[0]} x {size[1]} x {size[2]} m, "
               f"feet at 0: {'yes' if stats['feet_at_zero'] else 'NO'}, colours: {stats['color_type'].lower()}")
    common.say(f"sheet: {stats['sheet']}")
    if "anim" in stats:
        common.say(f"animation sheet: {stats['anim']['sheet']}")
    common.say(f"stats: {out / 'stats.json'}")
    return 0
