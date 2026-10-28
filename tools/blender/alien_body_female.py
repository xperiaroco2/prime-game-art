"""The female variant of the shared alien body (art #196, clothes step 2), in headless Blender: opens the base body's
.blend (S4b's alien_body.blend), moves the Body mesh's vertices by alien_female_geom's fields from a target file
(tools/blender/alien_female_targets/<name>.toml) and saves the variant as <out>/alien_body.blend, the same mesh with
the same topology, vertex order, weights and skeleton. Then it reopens the saved file and proves it: the vertex, edge
and face counts, the faces' and edges' vertex indices, the vertex groups and the weights hash the same as the base's,
and the per-vertex delta report (<out>/female.json).

    blender -b --factory-startup --python tools/blender/alien_body_female.py -- --body <base alien_body.blend>
        --target tools/blender/alien_female_targets/f1.toml --out <dir>

A build never overwrites: an out folder holding alien_body.blend is refused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_female_geom as G  # noqa: E402


def mesh_hashes(obj) -> dict:
    me = obj.data
    topo = hashlib.sha256()
    for p in me.polygons:
        topo.update(repr(tuple(p.vertices)).encode())
    edges = hashlib.sha256(repr([tuple(e.vertices) for e in me.edges]).encode())
    names = [g.name for g in obj.vertex_groups]
    weights = hashlib.sha256()
    for v in me.vertices:
        weights.update(repr([(names[g.group], round(g.weight, 6)) for g in v.groups]).encode())
    uv = hashlib.sha256(repr([tuple(round(c, 6) for c in d.uv) for d in me.uv_layers.active.data]).encode()) \
        if me.uv_layers.active else None
    return {"vertices": len(me.vertices), "edges": len(me.edges), "faces": len(me.polygons),
            "faces_sha256": topo.hexdigest(), "edges_sha256": edges.hexdigest(), "groups": names,
            "weights_sha256": weights.hexdigest(), "uv_sha256": uv.hexdigest() if uv else None}


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    t = G.load(args.target)
    out = Path(args.out)
    if (out / "alien_body.blend").exists():
        print(f"REFUSED: {out / 'alien_body.blend'} exists", flush=True)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.body).resolve()))
    body, arm = bpy.data.objects["Body"], bpy.data.objects["CharacterArmature"]
    base_hash = mesh_hashes(body)
    aw = arm.matrix_world
    head = {b.name: aw @ b.head_local for b in arm.data.bones}
    toe = head["LeftToes"] - head["LeftFoot"]
    sign = 1.0 if toe.y > 0 else -1.0  # f = sign * y: the toes point forward
    chain = [(head[n].z, sign * head[n].y) for n in ("Hips", "Spine", "Chest", "UpperChest", "Neck")]
    groups = {g.index: g.name for g in body.vertex_groups}
    missing = [b for b in t["mask"]["bones"] if b not in groups.values()]
    if missing:
        raise SystemExit(f"mask bones without a vertex group: {missing}")
    mask = {i for i, n in groups.items() if n in t["mask"]["bones"]}
    mw, inv = body.matrix_world, body.matrix_world.inverted()
    base, moved = [], []
    for v in body.data.vertices:
        p = mw @ v.co
        w = sum(g.weight for g in v.groups if g.group in mask)
        c = G.centre_f(p.z, chain)
        f = sign * p.y - c
        dx, df = G.delta(p.x, f, p.z, w, t)
        q = p.copy()
        q.x += dx
        q.y += sign * df
        base.append((p.x, f, p.z))
        moved.append((q.x, sign * q.y - c, q.z))
        v.co = inv @ q
    body.data.update()
    blend = out / "alien_body.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    # the proof on the saved file
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    body = bpy.data.objects["Body"]
    saved = [tuple(body.matrix_world @ v.co) for v in body.data.vertices]
    saved_f = [(p[0], sign * p[1] - G.centre_f(p[2], chain), p[2]) for p in saved]
    female_hash = mesh_hashes(body)
    same = {k: base_hash[k] == female_hash[k] for k in base_hash}
    rep = G.report(base, saved_f)
    rep["saved_vs_computed_max_m"] = round(max(max(abs(a - b) for a, b in zip(p, q)) for p, q in zip(saved_f, moved)), 7)
    hands_feet = [n for n in groups.values() if any(k in n for k in ("Hand", "Thumb", "Index", "Middle", "Ring",
                                                                     "Foot", "Toes", "Neck", "Head", "Arm"))]
    hf = {groups_i for groups_i, n in groups.items() if n in hands_feet}
    still = 0
    for v, p0, p1 in zip(body.data.vertices, base, saved_f):
        if any(g.group in hf and g.weight > 0.5 for g in v.groups) and max(abs(a - b) for a, b in zip(p0, p1)) > 1e-6:
            still += 1
    res = {"target": str(Path(args.target).resolve()), "name": t["name"], "base": str(Path(args.body).resolve()),
           "blend": str(blend), "front_sign_y": sign, "centre_chain": chain, "hash_base": base_hash,
           "hash_female": female_hash, "same": same, "all_same": all(same.values()),
           "limb_head_vertices_moved": still, "delta": rep}
    (out / "female.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    print("FEMALE", json.dumps({"all_same": res["all_same"], "moved": rep["moved"], "max_m": rep["max_m"],
                                "limb_head_vertices_moved": still, "top": rep["top_z_m"], "low": rep["low_z_m"]}),
          flush=True)
    return 0 if res["all_same"] and still == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
