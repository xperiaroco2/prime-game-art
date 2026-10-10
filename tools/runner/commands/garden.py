"""`garden`: checks the garden and the greenhouse's roof (layouts/house/outdoor/garden.toml, house_garden.py) and
writes the seeded scatter, the glass roof's placements, the herb route and a top-down plan (docs/house-garden.md).
`--proof` then rebuilds the plot (outdoor) and the house scenes, stages them with the kit, the props and the plants,
and runs godot/garden/proof.gd off-screen: the walks, the glass roof's ray test, the dusk pictures and the sheet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import common, house_garden, house_garden_scene, house_layout, house_outdoor
from . import _frames, _godot
from . import house as house_cmd
from . import outdoor as outdoor_cmd

NAME = "garden"
HELP = "check the garden and the greenhouse roof (layouts/house/outdoor/garden.toml); write the scatter and a plan"
PROOF = "res://garden/proof.gd"
PROOF_TIMEOUT = 330
ROOF_PREFIX = "glass_roof_"  # the roof pieces come from --roof-kit (the end bays are not in the kit's build on main yet)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--check", action="store_true", help="only validate; write nothing")
    parser.add_argument("--out", type=Path, help="output folder (default <raw>/house/80/build)")
    parser.add_argument("--proof", nargs="?", type=Path, const=Path(), metavar="DIR",
                        help="then walk, ray-test and shoot it in Godot off-screen (default <raw>/review/house/80)")
    parser.add_argument("--kit", type=Path, help="the house kit's build folder (default <raw>/kits/house/v<version>, the spec's version)")
    parser.add_argument("--roof-kit", type=Path, help="the glass roof pieces' folder (default <raw>/house/80/kit)")
    parser.add_argument("--plants", type=Path, help="the plants' GLB folder (default <raw>/house/80/plants)")


def run(args: argparse.Namespace) -> int:
    data, plot, layout = house_garden.load(), house_outdoor.load(), house_layout.load()
    out = None
    if args.check:
        rep = house_garden.build(data, plot, layout)
    else:
        out = (args.out or common.raw_dir() / "house" / "80" / "build").resolve()
        rep = house_garden.write(data, plot, layout, out)
        common.say(f"garden: wrote {out}")
    rt = rep["route"]
    common.say(f"garden: scatter {rep['counts']}; {len(rep['props'])} props; {len(rep['roof'])} roof pieces")
    common.say(f"garden: herb route {rt['length_m']} m, {rt['time_s']} s (doc {rt['doc_m']} m, {rt['doc_s']} s)")
    for g in rep["roof_gaps"]:
        common.say(f"garden: NOTE {g}")
    problems = list(rep["problems"])
    for p in problems:
        common.say(f"garden: PROBLEM {p}")
    if args.proof is not None and out is not None and not problems:
        raw = common.raw_dir()
        review = (args.proof if args.proof != Path() else raw / "review" / "house" / "80").resolve()
        found = proof(data, plot, layout, rep, out.parent, review, (args.kit or outdoor_cmd.default_kit()).resolve(),
                      (args.roof_kit or raw / "house" / "80" / "kit").resolve(),
                      (args.plants or raw / "house" / "80" / "plants").resolve())
        for p in found:
            common.say(f"garden: PROBLEM {p}")
        problems += found
    common.say(f"garden: {'FAILED' if problems else 'ok'}")
    return 1 if problems else 0


def greenhouse(layout: dict) -> dict:
    return next(r for lv in layout["levels"] for r in lv["rooms"] if r["id"] == "greenhouse")


def staged(rep: dict, req: dict, house: dict, found: dict, st: dict, build: Path, kit: Path, roof_kit: Path,
           plant_dir: Path) -> dict[str, Path]:
    """Staged name -> GLB: the plot, the kit pieces (the glass roof's from roof_kit), the dressing's and the garden's
    props (the garden's own from plant_dir), the plants."""
    names = {"outdoor": build / "outdoor.glb", "backdrop": build / "backdrop.glb"}
    for pid in set(req["pieces"]) | set(house["pieces"]):
        names[f"kit_{pid}"] = (roof_kit if pid.startswith(ROOF_PREFIX) else kit) / f"{pid}.glb"
    names |= {f"prop_{pid}": glb for pid, glb in found.items()}
    for p in rep["props"]:
        dirs = [plant_dir] if p["src"] == "garden" else [common.raw_dir() / d for d in st.get("prop_dirs", [])]
        hit = [d / f"{p['id']}.glb" for d in dirs if (d / f"{p['id']}.glb").is_file()]
        names.setdefault(f"prop_{p['id']}", hit[0] if hit else dirs[0] / f"{p['id']}.glb")
    for res in req["plants"]:
        stem = res.rsplit("/", 1)[1][:-len(".glb")]
        names[stem] = plant_dir / f"{stem[len('plant_'):]}.glb"
    return names


def proof(data: dict, plot: dict, layout: dict, rep: dict, raw80: Path, review: Path, kit: Path, roof_kit: Path,
          plant_dir: Path) -> list[str]:
    """The plot (outdoor.glb with the garden's paths) into <raw80>/outdoor, the house scenes into godot/import/house,
    then the scene in Godot off-screen; returns the problems."""
    build = raw80 / "outdoor"
    summary = house_outdoor.write(plot, build)
    if summary["problems"]:
        return [f"outdoor: {p}" for p in summary["problems"]]
    dressing = house_cmd.check_dressing(layout, house_layout.LAYOUT_DIR, [])
    planned = house_layout.plan(layout)
    found = house_cmd.prop_glbs(layout, dressing)
    st = layout["settings"]
    house = house_layout.write_scenes(layout, planned, house_cmd.DEFAULT_OUT, dressing,
                                      lambda pid: st["prop_res"].format(id=pid) if pid in found else None)
    doc = json.loads((build / "outdoor.json").read_text(encoding="utf-8"))
    req = house_garden_scene.request(plot, doc, build, outdoor_cmd.pack(kit), rep, data, greenhouse(layout))
    names = staged(rep, req, house, found, st, build, kit, roof_kit, plant_dir)
    missing = sorted(g.as_posix() for g in names.values() if not g.is_file())
    if missing:
        return [f"missing GLBs: {', '.join(missing)}"]
    _godot.clear_staged(set(names))
    for name, glb in names.items():
        _godot.stage(glb, name)
    lines = _godot.import_project()
    problems = [f"Godot import: {line}" for line in lines if "ERROR" in line]
    review.mkdir(parents=True, exist_ok=True)
    req_path = common.OUT / "garden" / "proof_request.json"
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text(json.dumps(req), encoding="utf-8")
    (review / "proof.json").unlink(missing_ok=True)
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", "1600x900", "-s", PROOF, "--", req_path.as_posix(), review.as_posix()],
                                PROOF_TIMEOUT)
    if code != 0 or not (review / "proof.json").is_file():
        tail = "\n".join(output.splitlines()[-25:])
        raise common.Failure(f"garden proof.gd failed (exit code {code}):\n{tail}")
    return problems + report(json.loads((review / "proof.json").read_text(encoding="utf-8")), review)


def report(result: dict, review: Path) -> list[str]:
    """Prints the walks, the ray test and the views' draw calls; returns the problems."""
    problems = []
    for name, w in result["walks"].items():
        state = "arrived" if w["arrived"] else f"stopped after {w['reached']} of {w['waypoints']} points"
        common.say(f"garden: walk {name}: {state} at {[round(c, 2) for c in w['end']]} in {w['seconds']:.1f} s "
                   f"({'ok' if w['pass'] else 'WRONG'})")
        if not w["pass"]:
            problems.append(f"walk {name} stopped at {[round(c, 2) for c in w['end']]}")
    r = result["rays"]
    common.say(f"garden: roof rays up {r['up_hit']}/{r['up']}, up along the gables {r['gable_up_hit']}/"
               f"{r['gable_up']}, level through the gables {r['level_hit']}/{r['level']}; control hit: "
               f"{r['control_hit']}")
    for m in r["misses"][:12]:
        common.say(f"garden: roof ray miss {m}")
    if r["misses"] or r["control_hit"]:
        problems.append(f"glass roof ray test: {len(r['misses'])} misses, control hit {r['control_hit']}")
    limit = result["draw_call_limit"]
    for name, v in result["views"].items():
        common.say(f"garden: view {name}: the garden layer {v['garden_draw_calls']} draw calls, "
                   f"{v['garden_primitives']} primitives; all {v['draw_calls']} draw calls, {v['primitives']} primitives")
        if v["garden_draw_calls"] >= limit:
            problems.append(f"view {name}: the garden layer {v['garden_draw_calls']} draw calls (limit {limit})")
    common.say(f"garden: sheet {(review / 'sheet.png').as_posix()}")
    return problems
