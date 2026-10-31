"""The alien's hand and wrist mesh rebuilt in place (art #196, Hands H1b; the maths in alien_hand_geom.py, the spec in
tools/blender/body_dims/hand_dims.toml, the driver alien_hand_run.py). Headless Blender:

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_hand_mesh.py -- dump \
        --blend <in.blend> --out <dump.json> [--bend 30]
    blender -b ... -- apply --blend <in.blend> --moves <moves.json> --out <out.blend>

- `dump`: per skinned mesh its name, vertex and face counts and a topology hash; every vertex weighted on a hand
  region bone (the LowerArm, the Hand and the five finger chains of each side): its rest position (world), its
  region weights (normalised over all its groups), its other weight, its faces' material names; the region's edges;
  the region bones' rest heads, tails and x/z axes. `--bend DEG`: the region vertices posed with each Hand bent
  +-DEG about its own x and z axes (no action), for the wrist's cross-section table.
- `apply`: moves the named vertices (world positions, by object name and index; every shape key moved by the same
  step), refuses a changed topology or an existing `--out`, saves `--out` and `<out>.json` (moved count, largest
  move, the topology hash before and after, every other vertex's largest move: 0).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

SIDES = ("Left", "Right")
CHAINS = {"Thumb": ("Metacarpal", "Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
          "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal"),
          "Little": ("Proximal", "Intermediate", "Distal")}


def region_bones() -> list:
    out = []
    for s in SIDES:
        out += [f"{s}LowerArm", f"{s}Hand"] + [f"{s}{f}{p}" for f, ps in CHAINS.items() for p in ps]
    return out


def _arm():
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def _meshes(arm):
    return [o for o in bpy.data.objects if o.type == "MESH"
            and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]


def topo_hash(me) -> str:
    h = hashlib.sha256()
    h.update(str(len(me.vertices)).encode())
    for p in me.polygons:
        h.update((",".join(map(str, p.vertices)) + ";").encode())
    return h.hexdigest()[:16]


def _region(o, names: set) -> dict:
    gname = {g.index: g.name for g in o.vertex_groups}
    out = {}
    for v in o.data.vertices:
        rw, other = {}, 0.0
        for g in v.groups:
            n = gname.get(g.group)
            if g.weight <= 0 or n is None:
                continue
            if n in names:
                rw[n] = g.weight
            else:
                other += g.weight
        if rw:
            t = sum(rw.values()) + other
            out[v.index] = ({k: round(x / t, 5) for k, x in rw.items()}, round(other / t, 5))
    return out


def dump(blend: str, out: str, bend: float) -> int:
    bpy.ops.wm.open_mainfile(filepath=blend)
    arm = _arm()
    names = set(region_bones())
    bones = {}
    for b in arm.data.bones:
        if b.name in names:
            m = arm.matrix_world @ b.matrix_local
            bones[b.name] = {"head": list(arm.matrix_world @ b.head_local), "tail": list(arm.matrix_world @ b.tail_local),
                             "x": list(m.to_3x3().col[0].normalized()), "z": list(m.to_3x3().col[2].normalized())}
    res = {"blend": blend, "bones": bones, "objects": []}
    for o in _meshes(arm):
        me, mw = o.data, o.matrix_world
        reg = _region(o, names)
        mats = [m.name if m else "" for m in me.materials]
        vmat = {}
        for p in me.polygons:
            for i in p.vertices:
                if i in reg:
                    vmat.setdefault(i, set()).add(mats[p.material_index] if p.material_index < len(mats) else "")
        idx = sorted(reg)
        edges = [list(e.vertices) for e in me.edges if e.vertices[0] in reg and e.vertices[1] in reg]
        res["objects"].append({
            "name": o.name, "verts": len(me.vertices), "faces": len(me.polygons), "topo": topo_hash(me),
            "shape_keys": len(me.shape_keys.key_blocks) if me.shape_keys else 0,
            "index": idx, "co": [[round(c, 6) for c in (mw @ me.vertices[i].co)] for i in idx],
            "w": [reg[i][0] for i in idx], "other": [reg[i][1] for i in idx],
            "mat": [sorted(vmat.get(i, ())) for i in idx], "edges": edges})
    if bend:
        if arm.animation_data:
            arm.animation_data.action = None
        res["bends"] = {}
        for s in SIDES:
            for ax in ("x", "z"):
                for sign in (1, -1):
                    for pb in arm.pose.bones:
                        pb.rotation_mode = "QUATERNION"
                        pb.location = (0, 0, 0)
                        pb.rotation_quaternion = (1, 0, 0, 0)
                    v = Vector((1, 0, 0)) if ax == "x" else Vector((0, 0, 1))
                    arm.pose.bones[f"{s}Hand"].rotation_quaternion = Matrix.Rotation(
                        sign * bend * 3.14159265 / 180, 4, v).to_quaternion()
                    bpy.context.view_layer.update()
                    dg = bpy.context.evaluated_depsgraph_get()
                    key = f"{s}_{ax}{'+' if sign > 0 else '-'}{bend:g}"
                    res["bends"][key] = {}
                    for o, ob in zip(_meshes(arm), res["objects"]):
                        ev = o.evaluated_get(dg)
                        em = ev.to_mesh()
                        mw = o.matrix_world
                        res["bends"][key][o.name] = [[round(c, 6) for c in (mw @ em.vertices[i].co)]
                                                     for i in ob["index"]]
                        ev.to_mesh_clear()
                    pbh = arm.pose.bones[f"{s}Hand"]
                    res["bends"][key]["_tail"] = list(arm.matrix_world @ pbh.tail)
    Path(out).write_text(json.dumps(res))
    print(f"dump: {len(res['objects'])} mesh(es) -> {out}")
    return 0


def apply(blend: str, moves_path: str, out: str) -> int:
    if Path(out).exists():
        raise SystemExit(f"{out} exists: never overwritten")
    bpy.ops.wm.open_mainfile(filepath=blend)
    moves = json.loads(Path(moves_path).read_text())
    arm = _arm()
    rep = {"blend": blend, "out": out, "objects": {}}
    for o in _meshes(arm):
        mv = moves.get("objects", {}).get(o.name)
        if not mv:
            continue
        me = o.data
        before = topo_hash(me)
        old = [v.co.copy() for v in me.vertices]
        inv = o.matrix_world.inverted()
        largest = 0.0
        for i, p in mv.items():
            i = int(i)
            new = inv @ Vector(p)
            d = new - me.vertices[i].co
            largest = max(largest, d.length)
            me.vertices[i].co = new
            if me.shape_keys:
                for kb in me.shape_keys.key_blocks:
                    kb.data[i].co = kb.data[i].co + d
        me.update()
        keep = set(int(i) for i in mv)
        other = max(((me.vertices[i].co - old[i]).length for i in range(len(old)) if i not in keep), default=0.0)
        after = topo_hash(me)
        if after != before:
            raise SystemExit(f"{o.name}: topology changed")
        rep["objects"][o.name] = {"moved": len(mv), "largest_mm": round(largest * 1000, 2), "topo": after,
                                  "others_largest_mm": round(other * 1000, 4), "verts": len(me.vertices)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    Path(out + ".json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep))
    return 0


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser(prog="alien_hand_mesh.py")
    ap.add_argument("mode", choices=("dump", "apply"))
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--moves", default="")
    ap.add_argument("--bend", type=float, default=0.0)
    a = ap.parse_args(argv)
    if a.mode == "dump":
        return dump(a.blend, a.out, a.bend)
    return apply(a.blend, a.moves, a.out)


if __name__ == "__main__":
    sys.exit(main())
