"""Bodies by drawing, step D3 (art #196): the Blender side of the station fit (body_fit_geom.py does the maths,
no bpy; body_fit_run.py drives it in plain Python).

    blender -b --factory-startup --python tools/blender/body_fit_blend.py -- dump --body <alien_body.blend> --out <dump.json>
    blender -b --factory-startup --python tools/blender/body_fit_blend.py -- apply --body <alien_body.blend>
        --fit <fit.json> --out <dir>

`dump` (read only): the Body mesh's world vertices, every vertex's weights, its edges, the armature's bones (world
head, tail, parent) and the open boundary loops. `apply`: opens the source body, writes the fit's vertices and bone
rest (heads and tails; the rolls and the rest orientations kept), puts the neck ring's weights on Neck and Head only
(the ADR, docs/decisions/2026-10-29-neck-ring.md) and saves <dir>/alien_body.blend; an out folder holding one is
refused, the source is never saved. Then it reopens the saved file and proves it (faces, edges, groups and UVs hash
as the source's; the vertices as the fit's) into <dir>/apply.json.
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
from alien_body_female import mesh_hashes  # noqa: E402


def open_loops(me) -> list:
    """Open boundary loops (edges with one face) as ordered vertex index lists."""
    count: dict = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            count[ek] = count.get(ek, 0) + 1
    nbr: dict = {}
    for (a, b), n in count.items():
        if n == 1:
            nbr.setdefault(a, []).append(b)
            nbr.setdefault(b, []).append(a)
    seen, out = set(), []
    for start in nbr:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v in nbr[cur] if v != prev and v not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        out.append(loop)
    return out


def _objs():
    return bpy.data.objects["Body"], bpy.data.objects["CharacterArmature"]


def dump(body_path: str, out: str) -> int:
    bpy.ops.wm.open_mainfile(filepath=str(Path(body_path).resolve()))
    body, arm = _objs()
    names = [g.name for g in body.vertex_groups]
    mw, aw = body.matrix_world, arm.matrix_world
    me = body.data
    d = {"blend": body_path,
         "verts": [[round(c, 6) for c in mw @ v.co] for v in me.vertices],
         "weights": [{names[g.group]: round(g.weight, 6) for g in v.groups if g.weight > 0} for v in me.vertices],
         "edges": [list(e.vertices) for e in me.edges],
         "bones": {b.name: {"head": list(aw @ b.head_local), "tail": list(aw @ b.tail_local),
                            "parent": b.parent.name if b.parent else None} for b in arm.data.bones},
         "loops": open_loops(me)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(d), encoding="utf-8")
    print(f"DUMP {len(d['verts'])} vertices, {len(d['edges'])} edges, {len(d['bones'])} bones, "
          f"loops {[len(x) for x in d['loops']]} -> {out}", flush=True)
    return 0


def apply(body_path: str, fit_path: str, out_dir: str) -> int:
    out = Path(out_dir)
    blend = out / "alien_body.blend"
    if blend.exists():
        print(f"REFUSED: {blend} exists", flush=True)
        return 2
    fit = json.loads(Path(fit_path).read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=str(Path(body_path).resolve()))
    body, arm = _objs()
    hash_a = mesh_hashes(body)
    inv = body.matrix_world.inverted()
    new = fit["verts"]
    if len(new) != len(body.data.vertices):
        print("REFUSED: vertex count differs", flush=True)
        return 2
    for v, q in zip(body.data.vertices, new):
        v.co = inv @ Vector(q)
    body.data.update()
    ring = fit.get("ring", [])
    names = {g.name: g for g in body.vertex_groups}
    for i in ring:  # weights only on Neck and Head, their sum kept at 1
        groups = {body.vertex_groups[g.group].name: g.weight for g in body.data.vertices[i].groups}
        keep = {n: groups.get(n, 0.0) for n in ("Neck", "Head")}
        tot = sum(keep.values()) or 1.0
        for n in groups:
            if n not in keep:
                names[n].remove([i])
        for n, w in keep.items():
            if w > 0 or n == "Neck" and tot == 1.0 and not any(keep.values()):
                names[n].add([i], w / tot if any(keep.values()) else 1.0, "REPLACE")
    rest = fit.get("rest")
    if rest:
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
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    body, arm = _objs()
    hash_b = mesh_hashes(body)
    mw = body.matrix_world
    err = max(math.dist(tuple(mw @ v.co), q) for v, q in zip(body.data.vertices, new))
    same = {k: hash_a[k] == hash_b[k] for k in ("faces_sha256", "edges_sha256", "groups", "uv_sha256")}
    ring_w = sorted({body.vertex_groups[g.group].name for i in ring for g in body.data.vertices[i].groups})
    res = {"source": body_path, "fit": fit_path, "blend": str(blend), "same": same, "all_same": all(same.values()),
           "weights_changed": hash_a["weights_sha256"] != hash_b["weights_sha256"], "ring_groups": ring_w,
           "saved_vs_fit_max_m": round(err, 8)}
    (out / "apply.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    print("APPLY", json.dumps(res), flush=True)
    return 0 if res["all_same"] and err < 1e-5 and set(ring_w) <= {"Neck", "Head"} else 1


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("dump", "apply"))
    ap.add_argument("--body", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fit", default="")
    a = ap.parse_args(argv)
    return dump(a.body, a.out) if a.mode == "dump" else apply(a.body, a.fit, a.out)


if __name__ == "__main__":
    sys.exit(main())
