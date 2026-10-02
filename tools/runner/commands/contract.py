"""`contract`: regenerates contract/humanoid.json from the pinned Godot and validates the whole contract.

`contract --check` changes nothing and fails when the committed humanoid.json differs from what Godot dumps now, or
when contract.toml or a bone map disagrees with the profile.
"""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path

from .. import common
from . import _contract

NAME = "contract"
HELP = "regenerate contract/humanoid.json from Godot's SkeletonProfileHumanoid and validate contract/"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--check", action="store_true", help="change nothing; fail when the committed contract is stale"
    )


def run(args: argparse.Namespace) -> int:
    raw = _contract.dump_profile(common.OUT / "contract" / "raw_profile.json")
    fresh = _contract.format_profile(raw)
    path = _contract.HUMANOID_JSON
    failed = False
    committed = path.read_text(encoding="utf-8") if path.is_file() else ""
    if committed == fresh:
        common.ok(f"{_show(path)} matches Godot {raw['godot_version']}")
    elif args.check:
        diff = difflib.unified_diff(committed.splitlines(), fresh.splitlines(), "committed", "Godot", lineterm="", n=1)
        common.bad(
            f"{_show(path)} differs from Godot {raw['godot_version']}",
            "\n".join(list(diff)[:30]) + "\nrun `tools/run.py contract` and commit the result",
        )
        failed = True
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fresh, encoding="utf-8", newline="\n")
        common.ok(f"wrote {_show(path)} from Godot {raw['godot_version']}")

    profile = json.loads(fresh)
    errors = _contract.validate_contract(_contract.load_contract(), profile)
    for name in _contract.map_names():
        bone_map = _contract.load_map(name)
        errors += _contract.validate_map(bone_map, profile)
        note = "" if bone_map.get("confirmed") else " (names unconfirmed)"
        if not _contract.validate_map(bone_map, profile):
            common.ok(f"bone map {name}{note}")
    for error in errors:
        common.bad(error)
    if not errors:
        common.ok(f"{_show(_contract.CONTRACT_TOML)} agrees with the profile")
    return 1 if failed or errors else 0


def _show(path: Path) -> str:
    return path.relative_to(common.ROOT).as_posix() if path.is_relative_to(common.ROOT) else path.as_posix()
