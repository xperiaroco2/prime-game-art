"""Dumps a body's rest for the body drawing (art #196, step D2; body_dims_geom.py does the maths, no bpy): the
armature's bones (world head and tail), every mesh object's name and z range, and the body mesh's rest vertices with
their dominant vertex group, plus its open boundary loops (the neck ring's vertex count, centre, radii and tilt).

    blender -b --factory-startup --python tools/blender/body_dims_probe.py -- --body <alien_body.blend> --out <probe.json>

Read only: the .blend is opened and never saved. The frame is the body file's: x lateral, z up from the sole, the
front at -y.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


def _loops(me):
    """Open boundary loops (edges with one face) as ordered vertex index lists."""
    count = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            count[ek] = count.get(ek, 0) + 1
    nbr = {}
    for (a, b), n in count.items():
        if n == 1:
            nbr.setdefault(a, []).append(b)
            nbr.setdefault(b, []).append(a)
    seen, loops = set(), []
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
        loops.append(loop)
    return loops


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.open_mainfile(filepath=args.body)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    bones = {b.name: {"head": list(arm.matrix_world @ b.head_local), "tail": list(arm.matrix_world @ b.tail_local)}
             for b in arm.data.bones}
    meshes = []
    for o in bpy.data.objects:
        if o.type == "MESH":
            zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
            meshes.append({"name": o.name, "vertices": len(zs), "z_min": min(zs) if zs else None,
                           "z_max": max(zs) if zs else None, "hide_render": o.hide_render})
    body = max((o for o in bpy.data.objects if o.type == "MESH" and o.vertex_groups),
               key=lambda o: len(o.data.vertices))
    names = [g.name for g in body.vertex_groups]
    verts = []
    for v in body.data.vertices:
        p = body.matrix_world @ v.co
        best = max(v.groups, key=lambda g: g.weight, default=None)
        verts.append([round(p.x, 5), round(p.y, 5), round(p.z, 5), names[best.group] if best else ""])
    loops = []
    for loop in _loops(body.data):
        pts = [body.matrix_world @ body.data.vertices[i].co for i in loop]
        c = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
        loops.append({"count": len(loop), "centre": c,
                      "x_half": (max(p.x for p in pts) - min(p.x for p in pts)) / 2,
                      "y_half": (max(p.y for p in pts) - min(p.y for p in pts)) / 2,
                      "z_min": min(p.z for p in pts), "z_max": max(p.z for p in pts),
                      "front_z": min(pts, key=lambda p: p.y).z, "back_z": max(pts, key=lambda p: p.y).z,
                      "points": [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in pts]})
    out = {"blend": args.body, "armature": arm.name, "body": body.name, "bones": bones, "meshes": meshes,
           "vertices": verts, "loops": sorted(loops, key=lambda l: -l["centre"][2])}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out), encoding="utf-8")
    print(f"probe: {len(verts)} vertices, {len(bones)} bones, {len(loops)} open loops -> {args.out}")


main()
