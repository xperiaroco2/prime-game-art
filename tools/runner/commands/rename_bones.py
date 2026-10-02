"""`rename-bones <model> --map NAME --out FILE`: renames a vendor rig's bones to the contract's profile names with
contract/bone_maps/<NAME>.toml (tools/blender/rename_bones.py in headless Blender) and saves the result as FILE
(.glb, .gltf or .blend). The source file is never changed. Run `check FILE --kind ...` afterwards.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _contract

NAME = "rename-bones"
HELP = "rename a rig's bones to the contract's names with a bone map"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("model", help="a .glb, .gltf, .fbx, .obj or .blend file with one armature")
    parser.add_argument("--map", required=True, choices=_contract.map_names())
    parser.add_argument("--out", required=True, help="the renamed model: .glb, .gltf or .blend")


def run(args: argparse.Namespace) -> int:
    model, out = Path(args.model).resolve(), Path(args.out).resolve()
    if not model.is_file():
        raise common.Failure(f"no such model: {model}")
    if out == model:
        raise common.Failure("--out must differ from the model: the source file is never changed")
    if out.suffix.lower() not in (".glb", ".gltf", ".blend"):
        raise common.Failure("--out must end in .glb, .gltf or .blend")
    profile = _contract.load_profile()
    bone_map = _contract.load_map(args.map)
    errors = _contract.validate_map(bone_map, profile)
    if errors:
        raise common.Failure("the bone map is broken:\n" + "\n".join(errors))
    work = common.OUT / "rename-bones" / model.stem
    work.mkdir(parents=True, exist_ok=True)
    plan_path, summary_path = work / "plan.json", work / "summary.json"
    plan_path.write_text(json.dumps(_contract.rename_plan(bone_map, profile), indent=2), encoding="utf-8")
    if summary_path.exists():
        summary_path.unlink()
    blender.run_script(
        "rename_bones.py", [model.as_posix(), plan_path.as_posix(), out.as_posix(), summary_path.as_posix()]
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not bone_map.get("confirmed"):
        common.warn(f"the {args.map} map's names are unconfirmed: compare the result with the first real file")
    common.ok(f"renamed {len(summary['renamed'])} bones, dropped {len(summary['dropped'])}; wrote {out.as_posix()}")
    for move, count in summary["weights_moved"].items():
        common.say(f"  moved the weights of {count} vertices: {move}")
    if summary["kept_weighted_drop_bones"]:
        kept = ", ".join(summary["kept_weighted_drop_bones"])
        common.warn(f"kept weighted bones the map would drop, with no kept parent to take their weights: {kept}")
    if summary["not_in_profile"]:
        common.warn(f"still not profile bones: {', '.join(summary['not_in_profile'])}")
    if summary["missing_from_profile"]:
        common.warn(f"profile bones the rig lacks: {', '.join(summary['missing_from_profile'])}")
    common.say(f"next: tools/run.py check {out.as_posix()} --kind body")
    return 0
