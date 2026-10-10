"""`outdoor`: the House map outside the house (art #81a, #81c): checks `layouts/house/outdoor/` and writes the fence
and stairs plan, the ground and backdrop GLBs, the sky and flats PNGs and a top-down plan. Pure Python, about 5 s.
`--proof` then validates the two GLBs (glTF-Validator), stages them with the house kit's pieces into godot/import/ and runs
godot/outdoor/proof.gd off-screen: the walks (round the inside of the fence, through the wicket and the gates, down
the outdoor stairs; walking out at the fence must stop) and the review sheet. docs/house-outdoor.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common, house_outdoor, house_outdoor_scene
from . import _export, _frames, _godot, _kit

PROOF = "res://outdoor/proof.gd"
PROOF_TIMEOUT = 330
KIT_SPEC = common.ROOT / "kits" / "house.json"

NAME = "outdoor"
HELP = "the House map's plot: fence, ground, street, outdoor stairs, sky and backdrop from layouts/house/outdoor/"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--layouts", type=Path, default=house_outdoor.DATA, help="the outdoor layout folder")
    parser.add_argument("--out", type=Path, help="output folder (default <raw>/house/81/build)")
    parser.add_argument("--check", action="store_true", help="only check the layout; write nothing")
    parser.add_argument("--proof", nargs="?", type=Path, const=Path(), metavar="DIR",
                        help="then validate, walk and shoot it in Godot off-screen (default <raw>/review/house/81)")
    parser.add_argument("--kit", type=Path, help="the house kit's build folder (default <raw>/kits/house/v<version>, the spec's version)")



def default_kit() -> Path:
    """The house kit's build folder for the spec's version (kits/house.json), as the `kit` command writes it."""
    return _kit.default_out(json.loads(KIT_SPEC.read_text(encoding="utf-8")))

def run(args: argparse.Namespace) -> int:
    data = house_outdoor.load(args.layouts)
    if args.check:
        problems = house_outdoor.plan(data)["problems"]
    else:
        out = (args.out or common.raw_dir() / "house" / "81" / "build").resolve()
        summary = house_outdoor.write(data, out)
        problems = summary["problems"]
        pieces = ", ".join(f"{k} {v}" for k, v in summary["pieces"].items())
        common.say(f"outdoor: {summary['fence_m']:g} m of fence; {pieces}")
        common.say(f"outdoor: ground triangles {summary['ground_tris']}; {summary['flats']} flats; "
                   f"sky {summary['sky']['size']}, wrap step {summary['sky']['seam_step']} "
                   f"(inner {summary['sky']['inner_step']}); lit windows {summary['windows']}")
        common.say(f"outdoor: wrote {out}")
        if args.proof is not None and not problems:
            review = args.proof if args.proof != Path() else common.raw_dir() / "review" / "house" / "81"
            kit = (args.kit or default_kit()).resolve()
            problems += proof(data, out, kit, review.resolve())
    for p in problems:
        common.say(f"outdoor: PROBLEM {p}")
    common.say(f"outdoor: {'FAILED' if problems else 'ok'}")
    return 1 if problems else 0


def pack(kit: Path) -> dict | None:
    """The kit's `set` pack for kit_materials.gd: its textures and the layers' roughness and normal strength."""
    spec = json.loads(KIT_SPEC.read_text(encoding="utf-8"))
    mats = [spec["materials"][m] for m in spec.get("packs", {}).get("set", {}).get("layers", [])]
    if len(mats) != 3 or not (kit / "textures" / "set_d.png").is_file():
        return None
    return {"textures": (kit / "textures").as_posix(), "roughness": [m["roughness"] for m in mats],
            "normal_strength": [m["normal_strength"] for m in mats]}


def proof(data: dict, build: Path, kit: Path, review: Path) -> list[str]:
    """glTF-Validator on outdoor.glb and backdrop.glb, then the scene in Godot off-screen; returns the problems."""
    problems = []
    for name in ("outdoor", "backdrop"):
        ok, line = _export.verdict(_export.validate(build / f"{name}.glb", build / f"{name}.validator.json"))
        common.say(f"outdoor: {name}.glb {line}")
        if not ok:
            problems.append(f"{name}.glb fails glTF-Validator ({build / f'{name}.validator.json'})")
    doc = json.loads((build / "outdoor.json").read_text(encoding="utf-8"))
    req = house_outdoor_scene.request(data, doc, build, pack(kit))
    missing = [i for i in req["pieces"] if not (kit / f"{i}.glb").is_file()]
    if missing:
        return problems + [f"kit pieces missing in {kit}: {', '.join(missing)}"]
    names = {f"kit_{i}": kit / f"{i}.glb" for i in req["pieces"]} | {"outdoor": build / "outdoor.glb",
                                                                       "backdrop": build / "backdrop.glb"}
    _godot.clear_staged(set(names))
    for name, glb in names.items():
        _godot.stage(glb, name)
    lines = _godot.import_project()
    problems += [f"Godot import: {line}" for line in lines if "ERROR" in line]
    review.mkdir(parents=True, exist_ok=True)
    req_path = common.OUT / "outdoor" / "proof_request.json"
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text(json.dumps(req), encoding="utf-8")
    (review / "proof.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", "1600x900", "-s", PROOF, "--", req_path.as_posix(), review.as_posix()],
                                PROOF_TIMEOUT)
    if code != 0 or not (review / "proof.json").is_file():
        tail = "\n".join(output.splitlines()[-20:])
        raise common.Failure(f"proof.gd failed (exit code {code}):\n{tail}")
    result = json.loads((review / "proof.json").read_text(encoding="utf-8"))
    for name, w in result["walks"].items():
        state = "arrived" if w["arrived"] else f"stopped after {w['reached']} of {w['waypoints']} points"
        common.say(f"outdoor: walk {name}: {state} at {[round(c, 2) for c in w['end']]} "
                   f"({'ok' if w['pass'] else 'WRONG'})")
        if not w["pass"]:
            problems.append(f"walk {name} {'arrived' if w['arrived'] else 'stopped'} at "
                            f"{[round(c, 2) for c in w['end']]}")
    seen = result.get("windows", {})
    common.say("outdoor: lit-window pixels (every 2nd) " + ", ".join(f"{k} {v}" for k, v in seen.items()))
    blind = [k for k in seen if k.startswith("lookout") and not seen[k]]
    if not seen or blind:
        problems.append(f"no lit window shows in {', '.join(blind) or 'any picture'} (backdrop flats)")
    common.say(f"outdoor: sheet {(review / 'sheet.png').as_posix()}")
    return problems
