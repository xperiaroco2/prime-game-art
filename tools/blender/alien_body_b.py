"""Body type B, the female alien body (art #196, `docs/decisions/2026-10-29-body-types.md`), in headless Blender:
opens body A's .blend (S4b's alien_body.blend), moves the Body mesh's vertices and the armature's bones by
alien_body_b_geom from a target file (tools/blender/alien_body_types/<name>.toml) and saves body B as
<out>/alien_body.blend: the same mesh (topology, vertex order, weights, UVs) on its own skeleton rest (the same bone
names, parents and rest orientations, the heads and tails moved). Then it reopens the saved file and proves it:
the counts, the faces', edges', groups', weights' and UVs' hashes equal A's; every bone's rest turn against A's
(`rest_turn_max_deg`, from the bones' rest matrices); the ratio table B over A (and the last approved body's, `--f2`).

    blender -b --factory-startup --python tools/blender/alien_body_b.py -- --body <A alien_body.blend>
        --target tools/blender/alien_body_types/b1.toml --out <dir> [--f2 <f2 alien_body.blend>]

A build never overwrites: an out folder holding alien_body.blend is refused. The actions in A's file (the clips the
character build starts from) are kept as they are: the build's `--leg-fit` scales their Root and Hips keys.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_body_b_geom as G  # noqa: E402
from alien_body_female import mesh_hashes  # noqa: E402


def read(path: str) -> tuple[list, list, dict, dict]:
    """(world vertices, weights per vertex, bones {name: head, tail, parent}, rest matrices) of a body file."""
    bpy.ops.wm.open_mainfile(filepath=str(Path(path).resolve()))
    body, arm = bpy.data.objects["Body"], bpy.data.objects["CharacterArmature"]
    names = [g.name for g in body.vertex_groups]
    mw, aw = body.matrix_world, arm.matrix_world
    verts = [tuple(mw @ v.co) for v in body.data.vertices]
    weights = [{names[g.group]: g.weight for g in v.groups if g.weight > 0} for v in body.data.vertices]
    bones = {b.name: {"head": tuple(aw @ b.head_local), "tail": tuple(aw @ b.tail_local),
                      "parent": b.parent.name if b.parent else None} for b in arm.data.bones}
    mats = {b.name: (aw @ b.matrix_local).to_3x3().normalized().to_quaternion() for b in arm.data.bones}
    return verts, weights, bones, mats


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--f2", default="", help="the last approved body (C1's f2) for the ratio table")
    args = ap.parse_args(argv)
    t = G.load(args.target)
    out = Path(args.out)
    blend = out / "alien_body.blend"
    if blend.exists():
        print(f"REFUSED: {blend} exists", flush=True)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    f2 = read(args.f2)[0] if args.f2 else None
    verts, weights, bones, mats_a = read(args.body)
    body, arm = bpy.data.objects["Body"], bpy.data.objects["CharacterArmature"]
    hash_a = mesh_hashes(body)
    new, rest, rep = G.deform(verts, weights, bones, t)
    inv = body.matrix_world.inverted()
    for v, q in zip(body.data.vertices, new):
        v.co = inv @ Vector(q)
    body.data.update()
    ainv = arm.matrix_world.inverted()
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(o == arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        roll = eb.roll
        r = rest[eb.name]
        eb.use_connect = False
        eb.head, eb.tail = ainv @ Vector(r["head"]), ainv @ Vector(r["tail"])
        eb.roll = roll
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    # the proof on the saved file
    verts_b, weights_b, bones_b, mats_b = read(str(blend))
    hash_b = mesh_hashes(bpy.data.objects["Body"])
    same = {k: hash_a[k] == hash_b[k] for k in hash_a if k not in ("vertices",)}
    same["vertices"] = hash_a["vertices"] == hash_b["vertices"]
    turns = {n: math.degrees(mats_a[n].rotation_difference(mats_b[n]).angle) for n in mats_a}
    turns = {n: min(a, 360.0 - a) for n, a in turns.items()}
    worst = max(turns, key=turns.get)
    saved_err = max(math.dist(a, b) for a, b in zip(verts_b, new))
    moved_bones = {n: round(math.dist(bones[n]["head"], bones_b[n]["head"]) * 1000, 1) for n in bones}
    s = t["height"]["scale"]
    ma = G.measure(verts, weights, bones)
    mb = G.measure(verts_b, weights_b, bones_b, s)
    table = G.ratios(ma, mb)
    if f2 is not None:
        mf = G.measure(f2, weights, bones)
        for k in table:
            table[k]["f2"] = mf[k]
            table[k]["f2_ratio"] = round(mf[k] / ma[k], 3) if ma[k] else None
    res = {"target": str(Path(args.target).resolve()), "name": t["name"], "body_a": str(Path(args.body).resolve()),
           "f2": args.f2, "blend": str(blend), "hash_a": hash_a, "hash_b": hash_b, "same": same,
           "all_same": all(same.values()), "saved_vs_computed_max_m": round(saved_err, 7), "deform": rep,
           "rest_turn_max_deg": round(turns[worst], 6), "rest_turn_worst": worst,
           "bone_head_moves_mm": moved_bones, "ratios": table,
           "rest_b": {n: {"head": [round(x, 5) for x in b["head"]], "tail": [round(x, 5) for x in b["tail"]]}
                      for n, b in bones_b.items()}}
    (out / "body_b.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    print("BODY_B", json.dumps({"all_same": res["all_same"], "rest_turn_max_deg": res["rest_turn_max_deg"],
                                "worst": worst, "saved_err_m": res["saved_vs_computed_max_m"], **rep}), flush=True)
    for k, row in table.items():
        print(f"RATIO {k} {row}", flush=True)
    ok = res["all_same"] and res["rest_turn_max_deg"] < 0.01 and saved_err < 1e-5
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
