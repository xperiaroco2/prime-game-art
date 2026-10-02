"""`pins`: prints the pinned tool versions and where each tool is looked for."""

from __future__ import annotations

import argparse

from .. import common, pins

NAME = "pins"
HELP = "print pinned tool versions and their paths"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--get", metavar="NAME", help="print one pin's value (for example BLENDER)")


def run(args: argparse.Namespace) -> int:
    if args.get:
        if not hasattr(pins, args.get):
            raise common.Failure(f"no pin named {args.get}")
        common.say(str(getattr(pins, args.get)))
        return 0
    rows = [
        ("Blender", pins.BLENDER, common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)),
        ("glTF-Validator", pins.GLTF_VALIDATOR, common.tool_path(pins.GLTF_VALIDATOR_ENV, pins.GLTF_VALIDATOR_DEFAULT)),
        ("Godot", pins.GODOT, common.tool_path(pins.GODOT_ENV, None)),
        ("raw folder", "", common.raw_dir()),
        ("raw backup", "", common.raw_backup_dir()),
    ]
    for name, version, path in rows:
        common.say(f"{name:15} {version:16} {path}")
    return 0
