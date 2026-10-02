"""`check <model> --kind body|clothing|accessory|prop | --slot ID [--map NAME]`: measures a model in headless Blender
(tools/blender/check_model.py) and judges it against contract/contract.toml. Writes report.json; exits 1 on a hard
failure. --slot judges a piece for a slot in contract.toml: its check_kind and its own budget (hair_or_hat uses
head_item). With --map, bone names are read through contract/bone_maps/<NAME>.toml first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _checks, _contract

NAME = "check"
HELP = "check a model against the character contract and write report.json"
MARKS = {_checks.PASS: "ok   ", _checks.WARN: "warn ", _checks.FAIL: "FAIL "}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("model", help="a .glb, .gltf, .fbx, .obj or .blend file")
    parser.add_argument("--kind", choices=_contract.KINDS, help="what the model is (or give --slot)")
    parser.add_argument("--slot", help="a slot id from contract.toml: its check_kind and budget (e.g. hair_or_hat)")
    parser.add_argument("--map", choices=_contract.map_names(), help="read bone names through this bone map")
    parser.add_argument("--report", help="where to write report.json (default tools/out/check/<model>/report.json)")


def run(args: argparse.Namespace) -> int:
    model = Path(args.model).resolve()
    if not model.is_file():
        raise common.Failure(f"no such model: {model}")
    contract = _contract.load_contract()
    profile = _contract.load_profile()
    slot = _contract.checkable_slot(contract, args.slot) if args.slot else None
    kind = args.kind or (slot["check_kind"] if slot else None)
    if kind is None:
        raise common.Failure("give --kind or --slot")
    if slot and kind != slot["check_kind"]:
        raise common.Failure(f"slot {slot['id']} is checked as {slot['check_kind']}, not {kind}")
    bone_map = _contract.load_map(args.map) if args.map else None
    report_path = Path(args.report).resolve() if args.report else common.OUT / "check" / model.stem / "report.json"
    work = report_path.parent
    work.mkdir(parents=True, exist_ok=True)
    params_path, measure_path = work / "params.json", work / "measure.json"
    params_path.write_text(json.dumps(_checks.measure_params(contract)), encoding="utf-8")
    if measure_path.exists():
        measure_path.unlink()
    blender.run_script("check_model.py", [model.as_posix(), params_path.as_posix(), measure_path.as_posix()])
    measure = json.loads(measure_path.read_text(encoding="utf-8"))
    report = _checks.evaluate(measure, kind, contract, profile, bone_map, slot)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    note = ""
    if bone_map:
        note = f", map {bone_map['name']}" + ("" if bone_map.get("confirmed") else " (names unconfirmed)")
    target = f"{kind} for the slot {slot['id']}" if slot else kind
    common.say(f"check {model.name} as {target}, budget {report['budget']}{note}")
    for result in report["results"]:
        common.say(f"  {MARKS[result['status']]} {result['check']}: {result['detail']}")
    summary = report["summary"]
    common.say(
        f"{report['verdict'].upper()}: {summary['fail']} failed, {summary['warn']} warnings, {summary['pass']} passed; "
        f"report {report_path.as_posix()}"
    )
    return 1 if report["verdict"] == _checks.FAIL else 0
