"""The cloth's real openings, inside Blender (art #196, clothes step 2, C1h): clothes_dress.py's cut and
clothes_proof.py's poke-through both leave out the body near them. Per piece its boundary loops (clothes_shell.
edge_loops); an opening is the long loop at one of the piece's joints (clothes_shell.OPENINGS, pick_openings): the
top's collar and cuffs, the trousers' hems, the shoes' tops. Every other boundary (the straps' and panels' edges,
the cut edges, the holes of the top's hidden faces, the buttons' bottoms, the tucked hem) is no opening."""
from __future__ import annotations

import sys
from pathlib import Path

import bmesh
import bpy
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clothes_shell as H  # noqa: E402


def body_mesh(arm, cloth, name: str):
    """The character's body: the armature's mesh child <name>_char (alien_loco's build), or its only mesh child that
    is no cloth piece; refuses (ValueError) when there is none or the pick is not clear."""
    kids = [o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm and o not in cloth
            and o.name not in H.OPENINGS]
    named = [o for o in kids if o.name == f"{name}_char"]
    if len(named) == 1:
        return named[0]
    if len(kids) == 1:
        return kids[0]
    raise ValueError(f"no clear body mesh under {arm.name}: want {name}_char, have {sorted(o.name for o in kids)}")


def opening_points(cloth, arm) -> tuple[list[tuple[float, float, float]], dict]:
    """The world points of the cloth's real openings (at rest) and a report: per piece and joint the loops taken
    (vertices, length, centre)."""
    names = {o.name for o in cloth}
    joints = {b.name: tuple(arm.matrix_world @ b.head_local) for b in arm.data.bones}
    pts, rep = [], {}
    for o in cloth:
        want = H.OPENINGS.get(o.name, ())
        if o.name == "garment" and "top" not in names:
            want = want + H.OPENINGS["top"]
        if not want:
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.verts.ensure_lookup_table()
        co = [tuple(o.matrix_world @ v.co) for v in bm.verts]
        bedges = [(e.verts[0].index, e.verts[1].index) for e in bm.edges if e.is_boundary]
        bm.free()
        runs = H.edge_loops(bedges)
        lens = {}
        for a, b in bedges:
            lens[a] = lens.get(a, 0.0) + 0.5 * _dist(co[a], co[b])
            lens[b] = lens.get(b, 0.0) + 0.5 * _dist(co[a], co[b])
        loops = [(tuple(sum(co[k][j] for k in r) / len(r) for j in range(3)), sum(lens[k] for k in r)) for r in runs]
        taken = set()
        for jn in want:
            if jn not in joints:
                rep[f"{o.name}@{jn}"] = "no such bone"
                continue
            ids = H.pick_openings(loops, joints[jn], H.OPENING_REACH[jn])
            rep[f"{o.name}@{jn}"] = [{"verts": len(runs[i]), "length_m": round(loops[i][1], 3),
                                      "centre": [round(c, 3) for c in loops[i][0]]} for i in ids] or "NONE"
            taken |= set(ids)
        for i in taken:
            pts += [co[k] for k in runs[i]]
        rep[f"{o.name}_loops"] = len(runs)
    return pts, rep


def _dist(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def kd_of(pts) -> KDTree:
    kd = KDTree(max(1, len(pts)))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    return kd
