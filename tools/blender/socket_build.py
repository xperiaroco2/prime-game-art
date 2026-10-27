"""The ship's crystal socket (art#263's stations) from its drawing, in headless Blender: the model from code
(socket_dims.toml through socket_drawing.load), one mesh in five surfaces (socket_bronze, socket_graphite,
socket_cyan, socket_amber, socket_lamp: the red problem-lamp's dome, its own surface the game lights), convex
colliders `crystal_socket_col<n>-convcolonly` (none for the lamp), and the `crystal_anchor` empty at the crystal's
pivot (its tip, on its axis, the middle at [mount] h; no tilt: the crystal slides out along glTF +Z). The origin on
the wall's face at floor level under the crystal's axis; glTF +Z out of the wall.

Then the checks with the built crystal (energy_crystal.glb) on the anchor: the claws' gap to the cap, the tip over
the collar, the crystal against the socket and its colliders (now and pulled out 30 cm), parts touching another part,
open edges, coplanar overlapping faces of two parts (z-fighting); and the orthographic front and side renders with
the crystal, the drawing's straight views cut to the same frames, the built numbers over both (socket_drawing.lines).

    blender -b --python socket_build.py -- --out DIR --crystal GLB --refs DIR [--samples N]

Writes into DIR: crystal_socket.glb, crystal_socket.blend, build.json, renders/.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import socket_drawing as sd  # noqa: E402

D = sd.load()
CM = 0.01
ORDER = ["socket_bronze", "socket_graphite", "socket_cyan", "socket_amber", "socket_lamp", "socket_bay"]
PART = "socket_part"
EDGE = "socket_chamfer"
PARTS: list = []


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"out": None, "crystal": None, "refs": None, "samples": 32}
    for i in range(0, len(a), 2):
        out[a[i].lstrip("-")] = a[i + 1]
    out["samples"] = int(out["samples"])
    return out


def P(u: float, d: float, h: float) -> Vector:
    return Vector((u * CM, -d * CM, h * CM))


# --- the parts -----------------------------------------------------------------------------------------------------
class Part:
    """Faces made between begin() and end() belong to one named part with one surface."""

    def __init__(self, bm, name: str, mat: str):
        self.bm, self.name, self.mat = bm, name, mat
        self.before = set(bm.faces)
        if name not in PARTS:
            PARTS.append(name)

    def end(self) -> list:
        """The part's faces get its surface and index; their edge level (EDGE: 0 flat, 1 a broad chamfer, 2 a fine
        bevel) the bevels set (bevel2, prism)."""
        bm = self.bm
        new = [f for f in bm.faces if f not in self.before]
        lay = bm.faces.layers.int[PART]
        for f in new:
            f.material_index = ORDER.index(self.mat)
            f[lay] = PARTS.index(self.name)
        return new


# socket-2: UV0 u per edge level, the metal shader's wear (console_metal.gdshader): the flat faces bronze, the broad
# chamfers half worn, the fine bevels on each side of them bright (the sheet's polished edges)
LEVEL_U = {0: 0.0, 1: 0.5, 2: 1.0}


def bevel2(bm, edges: list, chamfer) -> None:
    """socket-2's two bevels on the front edges: a broad chamfer (level 1), then a fine bevel (level 2) on both of
    its long edges (to the front face and to the side). chamfer: broad, or (broad, fine); the fine one defaults to
    the outline's `fine`, at most 0.3 of the broad one."""
    broad, fine = chamfer if isinstance(chamfer, tuple) else (chamfer, min(D["outline"]["fine"], 0.3 * chamfer))
    edges = [e for e in edges if e is not None and e.is_valid]
    if broad <= 0 or not edges:
        return
    lev = bm.faces.layers.int[EDGE]
    res = bmesh.ops.bevel(bm, geom=edges, offset=broad * CM, offset_type="OFFSET", segments=1, profile=0.5,
                          affect="EDGES", clamp_overlap=True)
    faces = [f for f in res["faces"] if f.is_valid]
    for f in faces:
        f[lev] = 1
    if fine <= 0:
        return
    fs = set(faces)
    rim = {e for f in faces for e in f.edges if not all(g in fs for g in e.link_faces)}
    res = bmesh.ops.bevel(bm, geom=list(rim), offset=fine * CM, offset_type="OFFSET", segments=1, profile=0.5,
                          affect="EDGES", clamp_overlap=True)
    for f in res["faces"]:
        if f.is_valid:
            f[lev] = 2


def slab(bm, name: str, mat: str, outer: list, inner, d0: float, d1: float, chamfer=0.0,
         which: str = "outer", ends=None) -> None:
    """outer (and a hole inner, the same count) extruded from d0 to d1, its front edges chamfered twice (bevel2;
    which: "outer", "inner", "both"; ends: only the outer loop's front edges i -> i + 1 for i in ends)."""
    part = Part(bm, name, mat)
    ob = [bm.verts.new(P(u, d0, h)) for u, h in outer]
    of = [bm.verts.new(P(u, d1, h)) for u, h in outer]
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ob[i], ob[j], of[j], of[i]))
    front_edges = [(of[i], of[(i + 1) % n]) for i in (ends if ends is not None else range(n))] \
        if which in ("outer", "both") else []
    if inner is None:
        bm.faces.new(of)
        bm.faces.new(list(reversed(ob)))
    else:
        ib = [bm.verts.new(P(u, d0, h)) for u, h in inner]
        if_ = [bm.verts.new(P(u, d1, h)) for u, h in inner]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ib[i], ib[j], if_[j], if_[i]))
            bm.faces.new((of[i], of[j], if_[j], if_[i]))
            bm.faces.new((ob[i], ob[j], ib[j], ib[i]))
        if which in ("inner", "both"):
            front_edges += [(if_[i], if_[(i + 1) % n]) for i in range(n)]
    new = [f for f in bm.faces if f not in part.before]
    bmesh.ops.recalc_face_normals(bm, faces=new)
    if front_edges:
        bevel2(bm, [bm.edges.get(pair) for pair in front_edges], chamfer)
    part.end()


def blocks(bm, ring_out: list, ring_in: list, c: tuple, seams: list, d0: float, d1: float, chamfer, gap: float):
    """socket-2: the outer frame as separate blocks (the sheet's): the matched ring cut on the rays through `seams`,
    each piece pulled back gap / 2 square to its seam's ray (the plate shows dark in the gaps), its outer side and
    both seam ends chamfered twice; the inner side lies under the inner ring."""
    n = len(ring_out)

    def near(a: float) -> int:
        return min(range(n), key=lambda i: abs(math.remainder(sd.ray_angle(ring_out[i], c) - a, 2 * math.pi)))
    cuts = sorted({near(sd.ray_angle(p, c)) for p in seams})
    for k, a in enumerate(cuts):
        b = cuts[(k + 1) % len(cuts)]
        idx = list(range(a, b + 1)) if b > a else list(range(a, n)) + list(range(0, b + 1))
        out, inn = [list(ring_out[i]) for i in idx], [list(ring_in[i]) for i in idx]
        for end, nxt in ((0, 1), (-1, -2)):
            ru, rh = out[end][0] - c[0], out[end][1] - c[1]
            ln = math.hypot(ru, rh)
            tu, th = rh / ln, -ru / ln
            if tu * (out[nxt][0] - out[end][0]) + th * (out[nxt][1] - out[end][1]) < 0:
                tu, th = -tu, -th
            for pts in (out, inn):
                pts[end] = [pts[end][0] + tu * gap / 2, pts[end][1] + th * gap / 2]
        m = len(out)
        poly = [tuple(p) for p in out] + [tuple(p) for p in reversed(inn)]
        # the front edges: along the outer side (0 .. m - 2), the end at b (m - 1), the end at a (2 m - 1)
        slab(bm, "outer", "socket_bronze", poly, None, d0, d1, chamfer, ends=[*range(m - 1), m - 1, 2 * m - 1])


def box(bm, name: str, mat: str, u0, u1, h0, h1, d0, d1) -> None:
    slab(bm, name, mat, [(u0, h1), (u1, h1), (u1, h0), (u0, h0)], None, d0, d1)


def prism(bm, name: str, mat: str, prof: list, ru: float, rd: float, dc: float, sides: int, chamfer_rings=(),
          rot: float = math.pi / 8) -> None:
    """A vertical solid of an ellipse (ru across, rd in depth, centred at d dc): prof [(scale, h), ...] bottom up;
    the faces between rings listed in chamfer_rings (index of the lower ring) are chamfer faces: a tuple of indices
    (fine bevels, level 2) or {index: level}."""
    part = Part(bm, name, mat)
    if not isinstance(chamfer_rings, dict):
        chamfer_rings = {i: 2 for i in chamfer_rings}
    lev = bm.faces.layers.int[EDGE]
    rings = []
    for s, h in prof:
        rings.append([bm.verts.new(P(s * ru * math.cos(rot + 2 * math.pi * j / sides),
                                     dc - s * rd * math.sin(rot + 2 * math.pi * j / sides), h)) for j in range(sides)])
    for i in range(len(rings) - 1):
        for j in range(sides):
            k = (j + 1) % sides
            f = bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
            f[lev] = chamfer_rings.get(i, 0)
    bm.faces.new(list(reversed(rings[0])))
    if prof[-1][0] > 1e-6:
        bm.faces.new(rings[-1])
    else:  # a point at the top: one apex vertex, no open ring
        bmesh.ops.remove_doubles(bm, verts=rings[-1], dist=1e-6)
    new = [f for f in bm.faces if f not in part.before and f.is_valid]
    bmesh.ops.recalc_face_normals(bm, faces=new)
    part.end()


def build_mesh() -> bpy.types.Object:
    bm = bmesh.new()
    bm.faces.layers.int.new(PART)
    bm.faces.layers.int.new(EDGE)
    dp, o, r = D["depth"], D["outline"], D["ring"]
    outline = sd.loop(o["pts"])
    bay = sd.loop(D["bay"]["pts"])
    slab(bm, "plate", "socket_graphite", outline, None, 0.0, dp["plate"], o["plate_chamfer"])
    # the hidden backs sit in the part behind at staggered depths (no two coplanar)
    c = (0.0, D["mount"]["h"] - 9.0)
    seams = [tuple(p) for p in o["seams"]] + [(-u, h) for u, h in o["seams"]]
    ring_out, ring_in = sd.match(sd.offset(outline, -o["inset"]), bay, c, seams)
    blocks(bm, ring_out, ring_in, c, seams, dp["plate"] - 0.1, dp["layer"], o["layer_chamfer"], o["seam"])
    # socket-3: the bay's floor its own surface (socket_bay): socket.gd glows it round a charged crystal
    slab(bm, "bay", "socket_bay", sd.offset(bay, -0.02), None, dp["plate"] - 0.2, dp["bay"])
    # socket-2: the inner bezel round the bay (raised), the cyan strip beside it, the ring's rim outside the strip
    lip, strip = sd.offset(bay, r["lip"]), sd.offset(bay, r["strip"])
    slab(bm, "lip", "socket_bronze", lip, bay, dp["layer"], dp["lip"], r["lip_chamfer"], "both")
    slab(bm, "strip", "socket_cyan", strip, lip, dp["layer"] - 0.2, dp["strip"])
    slab(bm, "ring", "socket_bronze", sd.loop(r["pts"]), strip, dp["layer"] - 0.1, dp["ring"], r["chamfer"], "outer")
    slab(bm, "header", "socket_bronze", sd.loop(D["header"]["pts"]), None, dp["plate"] - 0.3, dp["header"],
         D["header"]["chamfer"])
    # socket-3: the claws are their own leaves (claw_leaf); here the graphite pins they turn on, out of the ring
    k = D["claw"]
    for sgn in (1, -1):
        slab(bm, "pins", "socket_graphite", circle(sgn * k["hinge"][0], k["hinge"][1], 0.45, 12), None,
             dp["ring"] - 0.05, dp["claw_plate"] + 0.85)
    slab(bm, "block", "socket_bronze", sd.loop(D["block"]["pts"]), None, dp["plate"] - 0.4, dp["front"],
         D["block"]["chamfer"])
    # the collar: an octagon cup on the crystal's axis (drawing.js COLLAR's outline in front), its amber band
    # sunk between two bronze rims, a cone under it, a graphite stem back to the bay's floor
    c = D["collar"]
    ax = D["mount"]["axis_d"]
    ru = max(u for u, _h in c["pts"])
    rd = dp["collar"][1] - ax
    top, h0 = max(h for _u, h in c["pts"]), min(h for _u, h in c["pts"])
    w0, w1 = c["window_h"]
    straight = c["pts"][2][1]
    cone = c["pts"][3][0] / ru
    # socket-2: a turned cup (16 sides): a cone, a bright bevelled foot ring, the sunk amber band, a bevelled lip
    t16 = math.pi / 16
    prism(bm, "collar", "socket_bronze", [(cone, h0), (0.93, straight - 0.8), (1.0, straight - 0.3), (1.0, w0 + 0.05)],
          ru, rd, ax, 16, chamfer_rings={0: 1, 1: 2}, rot=t16)
    prism(bm, "collar", "socket_amber", [(0.93, w0), (0.93, w1)], ru, rd, ax, 16, rot=t16)
    prism(bm, "collar", "socket_bronze", [(1.0, w1 - 0.05), (1.0, top - 0.75), (0.97, top - 0.45), (0.9, top)],
          ru, rd, ax, 16, chamfer_rings={1: 2, 2: 1}, rot=t16)
    box(bm, "collar", "socket_graphite", -ru * 0.55, ru * 0.55, h0 + 0.5, top - 0.6, dp["collar"][0], ax)
    s = D["slots"]
    for (u0, u1, h0, h1), face in [(q, dp["layer"]) for q in s["outer"]] + \
            [((-q[1], -q[0], q[2], q[3]), dp["layer"]) for q in s["outer"]] + [(q, dp["front"]) for q in s["bottom"]]:
        b = s["bezel"]  # socket-2: a bronze bezel round the window, the amber sunk in it just over the block's face
        slab(bm, "slots", "socket_bronze", [(u0 - b, h1 + b), (u1 + b, h1 + b), (u1 + b, h0 - b), (u0 - b, h0 - b)],
             [(u0, h1), (u1, h1), (u1, h0), (u0, h0)], face - 0.6, face + s["proud"], 0.12, "both")
        box(bm, "slots", "socket_amber", u0 + 0.01, u1 - 0.01, h0 + 0.01, h1 - 0.01, face - 0.4, face + 0.08)
    n = D["neck"]
    (h0, h1) = n["h"]
    # socket-2: the neck turned (16 sides): a foot, a groove, a bevelled top
    prism(bm, "neck", "socket_bronze", [(0.9, h0 - 0.1), (1.0, h0 + 0.3), (1.0, h0 + 1.0), (0.92, h0 + 1.2),
                                        (0.92, h0 + 1.6), (1.0, h0 + 1.8), (1.0, h1 - 0.4), (0.9, h1)],
          n["ru"], n["rd"], n["d"], 16, chamfer_rings={0: 2, 2: 2, 4: 2, 6: 2}, rot=t16)
    lr = D["lamp_ring"]
    # socket-2: the lamp's bronze collar (the sheet's), a dark band where the dome sits in it
    (h0, h1) = lr["h"]
    prism(bm, "lamp_ring", "socket_bronze", [(0.9, h0), (1.0, h0 + 0.35), (1.0, h1 - 0.75), (0.93, h1 - 0.45)],
          lr["ru"], lr["rd"], n["d"], 16, chamfer_rings={0: 2, 2: 2}, rot=t16)
    prism(bm, "lamp_ring", "socket_graphite", [(0.85, h1 - 0.5), (0.85, h1 + 0.2)], lr["ru"], lr["rd"], n["d"], 16,
          rot=t16)
    lp = D["lamp"]
    (h0, h1) = lp["h"]
    top = h1 - h0 - lp["wall"]
    prof = [(1.0, h0 - 0.05), (1.0, h0 + lp["wall"])]
    for i in range(1, 7):
        a = math.radians(90.0 * i / 7)
        prof.append((math.cos(a), h0 + lp["wall"] + top * math.sin(a)))
    prof.append((0.0, h1))
    prism(bm, "lamp", "socket_lamp", prof, lp["ru"], lp["rd"], lp["d"], lp["sides"], rot=0.0)
    return to_object(bm, "crystal_socket")


def circle(cu: float, ch: float, r: float, n: int) -> list:
    """n points round (cu, ch), clockwise from the top as you face the socket (the polygons' order)."""
    return [(cu + r * math.sin(2 * math.pi * i / n), ch + r * math.cos(2 * math.pi * i / n)) for i in range(n)]


def claw_leaf(sgn: int) -> bpy.types.Object:
    """socket-3: one claw as its own object, claw_r (sgn 1) or claw_l (-1, the mirror), its origin on the hinge, no
    rotation (closed); the game turns it OPEN round its local glTF +Z (socket.gd set_claws). The drawing's CLAW as a
    plate in front of the lip (claw_plate .. claw[1]) cut in two segments, a barrel round the hinge, and the jaw
    finger behind the lower segment beside the cap (claw[0] .. claw_plate)."""
    k, dp = D["claw"], D["depth"]
    bm = bmesh.new()
    bm.faces.layers.int.new(PART)
    bm.faces.layers.int.new(EDGE)

    def side(pts: list) -> list:
        return [tuple(p) for p in pts] if sgn > 0 else [(-u, h) for u, h in reversed(pts)]
    claw = [tuple(p) for p in k["pts"]]
    a, b = (tuple(p) for p in k["cut"])
    d0, d1 = dp["claw_plate"], dp["claw"][1]
    for keep in (True, False):
        slab(bm, "claws", "socket_bronze", side(sd.clip(claw, a, b, keep, k["cut_gap"])), None, d0, d1, k["chamfer"])
    hu, hh = k["hinge"]
    slab(bm, "claws", "socket_bronze", circle(sgn * hu, hh, k["knuckle"], 16), None, d0 + 0.05, d1 - 0.1,
         (0.25, 0.08))
    slab(bm, "claws", "socket_bronze", side(k["finger"]), None, dp["claw"][0], d0 + 0.05)
    ob = to_object(bm, "claw_r" if sgn > 0 else "claw_l")
    pivot = P(sgn * hu, d0, hh)
    for v in ob.data.vertices:
        v.co -= pivot
    ob.location = pivot
    # its collider turns with it: the arm's hull kept 0.06 out of the cap (u >= 6.9), parented
    pts = [(sgn * max(u, 6.9), d, h) for u, h in claw for d in dp["claw"]]
    col = hull(f"crystal_socket_col{5 if sgn > 0 else 6}-convcolonly", pts)
    for v in col.data.vertices:
        v.co -= pivot
    col.parent = ob
    return ob


def to_object(bm, name: str) -> bpy.types.Object:
    """The bmesh as a mesh object: UV0 u the faces' edge level (LEVEL_U), v a random number per face, the surfaces
    in ORDER, flat shading but the lamp's dome."""
    me = bpy.data.meshes.new(name)
    uv = bm.loops.layers.uv.new("UVMap")
    edge = bm.faces.layers.int[EDGE]
    rng = random.Random(263)
    for f in bm.faces:
        v = rng.random()
        for lp_ in f.loops:
            lp_[uv].uv = (LEVEL_U.get(f[edge], 0.0), v)
    bm.to_mesh(me)
    bm.free()
    for surface in ORDER:
        me.materials.append(MATS[surface])
    for p in me.polygons:
        p.use_smooth = ORDER[p.material_index] == "socket_lamp"
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


# --- colliders and the anchor --------------------------------------------------------------------------------------
def hull(name: str, pts: list) -> bpy.types.Object:
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(P(*p))
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def colliders() -> list:
    """Convex hulls round the body that leave the crystal's room free: the back (to the bay's floor), the two side
    columns, the bottom (block and collar, under the tip), the top (header, claws' roots, neck; under the lamp)."""
    dp = D["depth"]
    ol = sd.loop(D["outline"]["pts"])
    back = [(u, d, h) for u, h in ol for d in (0.0, dp["bay"])]
    bay = D["bay"]["pts"]
    hs = [h for _, h in D["outline"]["pts"]]
    side = []
    for sgn in (1, -1):
        pts = [(sgn * u, d, h) for u, h in D["outline"]["pts"] if u > 20 for d in (dp["bay"], dp["layer"])]
        pts += [(sgn * 14.6, d, h) for h in (bay[4][1], bay[5][1]) for d in (dp["bay"], max(dp["ring"], dp["lip"]))]
        side.append(pts)
    tip = D["mount"]["tip_h"]
    low = [(u, d, h) for u, h in sd.loop(D["block"]["pts"]) + sd.loop(D["collar"]["pts"])
           for d in (dp["bay"], dp["front"])]
    low += [(sgn * u, d, h) for sgn in (1, -1) for u, h in ((6.4, min(hs)), (14.0, 112.0 + (tip - 122.55)))
            for d in (dp["bay"], max(dp["ring"], dp["lip"]))]
    # socket-3: the neck block and the lamp's collar; the claws have their own colliders (claw_leaf)
    up = [(u, d, h) for u, h in sd.loop(D["header"]["pts"]) for d in (dp["plate"], dp["header"])]
    lr = D["lamp_ring"]
    up += [(sgn * lr["ru"], D["neck"]["d"] + k * lr["rd"], lr["h"][1]) for sgn in (1, -1) for k in (1, -1)]
    return [hull(f"crystal_socket_col{i}-convcolonly", pts) for i, pts in enumerate([back, *side, low, up])]


def anchor() -> bpy.types.Object:
    e = bpy.data.objects.new("crystal_anchor", None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = 0.1
    e.location = P(0.0, D["mount"]["axis_d"], D["mount"]["tip_h"])
    bpy.context.collection.objects.link(e)
    return e


# --- materials -----------------------------------------------------------------------------------------------------
MATS: dict = {}
SPEC = {
    "socket_bronze": dict(base=(0.50, 0.30, 0.15), metallic=1.0, rough=0.3),
    "socket_graphite": dict(base=(0.07, 0.072, 0.08), metallic=0.85, rough=0.38),
    "socket_cyan": dict(base=(0.02, 0.05, 0.06), metallic=0.0, rough=0.2, emit=(0.0, 0.62, 1.0), strength=6.0),
    "socket_amber": dict(base=(0.06, 0.04, 0.01), metallic=0.0, rough=0.3, emit=(1.0, 0.55, 0.08), strength=4.0),
    # the GLB's fallback is the usual state, charged: the lamp's red glass unlit (socket.gd lights it)
    "socket_lamp": dict(base=(0.45, 0.02, 0.015), metallic=0.0, rough=0.12),
    # socket-3: the bay's floor, dark (socket.gd glows it cyan round a charged crystal)
    "socket_bay": dict(base=(0.03, 0.035, 0.045), metallic=0.2, rough=0.55),
}


def build_materials() -> None:
    for name, s in SPEC.items():
        m = bpy.data.materials.new(name)
        b = m.node_tree.nodes.get("Principled BSDF") if m.node_tree else None
        if b is None:
            m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*s["base"], 1.0)
        b.inputs["Metallic"].default_value = s["metallic"]
        b.inputs["Roughness"].default_value = s["rough"]
        if "emit" in s:
            b.inputs["Emission Color"].default_value = (*s["emit"], 1.0)
            b.inputs["Emission Strength"].default_value = s["strength"]
        MATS[name] = m


# --- checks --------------------------------------------------------------------------------------------------------
def world_tris(ob) -> tuple:
    me = ob.data
    mw = ob.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    return verts, [tuple(p.vertices) for p in me.polygons]


def bvh(ob) -> BVHTree:
    v, f = world_tris(ob)
    return BVHTree.FromPolygons(v, f)


def bvh_parts(obs: list, skip: tuple = ()) -> tuple:
    """One tree of several objects' faces in the world (but the faces of the parts named in skip) and each face's
    part name."""
    verts, faces, names = [], [], []
    for ob in obs:
        v, f = world_tris(ob)
        attr = ob.data.attributes.get(PART)
        base = len(verts)
        verts += v
        for i, poly in enumerate(f):
            name = PARTS[attr.data[i].value] if attr else "?"
            if name in skip:
                continue
            faces.append(tuple(base + j for j in poly))
            names.append(name)
    return BVHTree.FromPolygons(verts, faces), names


def turn(claws: list, deg: float) -> None:
    """socket-3: both claws opened deg (claw_r round -Y = glTF +Z, claw_l the mirror)."""
    for c in claws:
        c.rotation_euler = (0.0, math.radians(-deg if c.name == "claw_r" else deg), 0.0)
    bpy.context.view_layer.update()


def swing(ob, claws: list, crystal) -> dict:
    """socket-3: the claws turned 0 .. 40 degrees by 1 (and at [claw] open): their faces against the body's (the pins
    they turn on left out) and the crystal's; the largest angle reached with none (None when nothing met the frame by
    40: fix2, a sweep that never meets anything proves nothing, so the test fails on it), the closest gap of an open
    claw's vertices to the body, the crystal pulled out with the claws open."""
    body, _ = bvh_parts([ob], skip=("pins",))
    cry = bvh(crystal)
    per_deg, clear = [], None
    for deg in range(0, 41):
        turn(claws, deg)
        n = sum(len(bvh(c).overlap(body)) for c in claws)
        per_deg.append(n)
        if n and clear is None:
            clear = deg - 1
    k = D["claw"]
    turn(claws, k["open"])
    gap = min((body.find_nearest(c.matrix_world @ v.co)[3] or 1.0) / CM for c in claws for v in c.data.vertices)
    out = {"swing_pairs_per_deg": per_deg, "swing_clear_deg": clear,
           "open_deg": k["open"], "open_vs_body_pairs": sum(len(bvh(c).overlap(body)) for c in claws),
           "open_gap_cm": round(gap, 2), "open_vs_crystal_pairs": sum(len(bvh(c).overlap(cry)) for c in claws)}
    socket, _ = bvh_parts([ob, *claws])
    base = crystal.location.copy()
    pulled = []
    for step in range(0, 16):
        crystal.location = base + Vector((0.0, -2.0 * step * CM, 0.0))
        bpy.context.view_layer.update()
        pulled.append(len(socket.overlap(bvh(crystal))))
    crystal.location = base
    turn(claws, 0.0)
    out["open_pull_pairs_per_2cm"] = pulled
    out["closed_vs_body_pairs"] = sum(len(bvh(c).overlap(body)) for c in claws)
    return out


def import_crystal(path: Path, at: Vector) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in new:
        if o.parent is None:
            o.location = at
    bpy.context.view_layer.update()
    return meshes[0]


def checks(ob, claws: list, cols: list, crystal) -> dict:
    out = {}
    cv = [crystal.matrix_world @ v.co for v in crystal.data.vertices]
    m = D["mount"]
    z0, z1, flats = m["cap"]
    tip = m["tip_h"]
    band = [v for v in cv if (tip + z0) * CM - 1e-4 <= v.z <= (tip + z1) * CM + 1e-4]
    cap_half = max(abs(v.x) for v in band) / CM
    claw_u = min(abs(u) for u, h in D["claw"]["pts"] if h < tip + z1)
    claw_low = min(h for _, h in D["claw"]["pts"])
    out["cap_half_cm"] = round(cap_half, 3)
    out["claw_gap_cm"] = round(claw_u - cap_half, 3)
    out["claw_hold_cm"] = round(tip + z1 - claw_low, 2)
    out["tip_gap_cm"] = round(min(v.z for v in cv) / CM - max(h for _, h in D["collar"]["pts"]), 3)
    out["crystal_top_cm"] = round(max(v.z for v in cv) / CM, 2)
    out["header_clear_cm"] = round(min(h for _, h in D["header"]["pts"]) - max(v.z for v in cv) / CM, 2)
    out["crystal_back_cm"] = round(-max(v.y for v in cv) / CM, 2)
    sock, names = bvh_parts([ob, *claws])
    pairs = sock.overlap(bvh(crystal))
    out["crystal_vs_socket_pairs"] = len(pairs)
    by = {}
    for i, _j in pairs:
        by[names[i]] = by.get(names[i], 0) + 1
    out["crystal_vs_socket_by_part"] = by
    out["crystal_vs_colliders_pairs"] = sum(len(bvh(c).overlap(bvh(crystal))) for c in cols)
    pulled = []
    base = crystal.location.copy()
    for step in range(1, 16):
        crystal.location = base + Vector((0.0, -2.0 * step * CM, 0.0))
        bpy.context.view_layer.update()
        pulled.append(len(sock.overlap(bvh(crystal))))
    crystal.location = base
    bpy.context.view_layer.update()
    out["pull_out_pairs_per_2cm"] = pulled
    # parts: each part's box touches another's; open edges; coplanar overlapping faces of two parts (the claws closed,
    # in place)
    bm = bmesh.new()
    for o in (ob, *claws):
        before = set(bm.verts)
        bm.from_mesh(o.data)
        bmesh.ops.transform(bm, matrix=o.matrix_world, verts=[v for v in bm.verts if v not in before])
    lay = bm.faces.layers.int[PART]
    boxes = {}
    for f in bm.faces:
        for v in f.verts:
            b = boxes.setdefault(f[lay], [list(v.co), list(v.co)])
            for i in range(3):
                b[0][i] = min(b[0][i], v.co[i])
                b[1][i] = max(b[1][i], v.co[i])
    eps = 0.0005
    alone = []
    for k, (lo, hi) in boxes.items():
        if not any(all(lo[i] - eps <= hi2[i] and lo2[i] - eps <= hi[i] for i in range(3))
                   for k2, (lo2, hi2) in boxes.items() if k2 != k):
            alone.append(PARTS[k])
    out["parts"] = PARTS
    out["parts_touching_nothing"] = alone
    out["open_edges"] = sum(1 for e in bm.edges if not e.is_manifold)
    planes = {}
    for f in bm.faces:
        n = f.normal
        key = (round(n.x, 3), round(n.y, 3), round(n.z, 3), round(n.dot(f.verts[0].co) / CM, 2))
        planes.setdefault(key, []).append(f)
    z = []
    for key, fs in planes.items():
        for i, a in enumerate(fs):
            for b in fs[i + 1:]:
                if a[lay] == b[lay]:
                    continue
                # the two faces' extents along the plane's own two axes: both overlap by over 1 mm
                n = a.normal
                t1 = n.cross(Vector((0.0, 0.0, 1.0)))
                t1 = (t1 if t1.length > 0.1 else n.cross(Vector((1.0, 0.0, 0.0)))).normalized()
                t2 = n.cross(t1).normalized()
                ov = []
                for t in (t1, t2):
                    pa, pb = [v.co.dot(t) for v in a.verts], [v.co.dot(t) for v in b.verts]
                    ov.append(min(max(pa), max(pb)) - max(min(pa), min(pb)))
                if min(ov) > 0.001:
                    z.append(f"{PARTS[a[lay]]}/{PARTS[b[lay]]} {key}")
    out["coplanar_overlaps"] = sorted(set(z))[:20]
    bm.free()
    return out


# --- export --------------------------------------------------------------------------------------------------------
def export(out: Path) -> None:
    bpy.ops.export_scene.gltf(filepath=str(out / "crystal_socket.glb"), export_format="GLB", use_selection=False,
                              export_yup=True, export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_vertex_color="NONE", export_extras=False)


def mesh_info(ob, claws: list) -> dict:
    """The body's and the closed claws' triangles per surface, vertices and extent (cm)."""
    tris, co = {}, []
    for o in (ob, *claws):
        for p in o.data.polygons:
            name = ORDER[p.material_index]
            tris[name] = tris.get(name, 0) + len(p.vertices) - 2
        co += [o.matrix_world @ v.co for v in o.data.vertices]
    me = ob.data
    lay = None
    lo = [min(c[i] for c in co) / CM for i in range(3)]
    hi = [max(c[i] for c in co) / CM for i in range(3)]
    del lay
    return {"triangles": sum(tris.values()), "triangles_by_material": tris,
            "vertices": sum(len(o.data.vertices) for o in (ob, *claws)),
            "size_cm": {"u": round(hi[0] - lo[0], 2), "d": round(hi[1] - lo[1], 2), "h": round(hi[2] - lo[2], 2)},
            "u_cm": [round(lo[0], 2), round(hi[0], 2)], "d_cm": [round(-hi[1], 2), round(-lo[1], 2)],
            "h_cm": [round(lo[2], 2), round(hi[2], 2)]}


# --- renders -------------------------------------------------------------------------------------------------------
def stage(samples: int) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("night")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.04, 0.07, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    wall = bpy.data.meshes.new("wall")
    wall.from_pydata([(-1, 0.0005, 0), (1, 0.0005, 0), (1, 0.0005, 3), (-1, 0.0005, 3)], [], [(0, 1, 2, 3)])
    wm = bpy.data.materials.new("wall")
    wm.use_nodes = True
    wm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.07, 0.12, 1.0)
    wall.materials.append(wm)
    wo = bpy.data.objects.new("wall", wall)
    sc.collection.objects.link(wo)
    for name, loc, rot, energy in (("key", (-1.2, -2.0, 2.4), (60, 0, -30), 300.0), ("fill", (1.5, -1.5, 1.2), (80, 0, 45), 120.0),
                                   ("rim", (0.0, -0.5, 2.6), (20, 0, 0), 60.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = 1.5
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = [math.radians(a) for a in rot]
        sc.collection.objects.link(lo)
    cam = bpy.data.cameras.new("cam")
    co = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co


def shoot_ortho(folder: Path) -> list:
    """Front (from +d) and side (from +u: d to the right, the wall at the left, as the drawing's side view) at
    sd.PX_PER_CM, framed like socket_drawing.frame."""
    sc = bpy.context.scene
    co = sc.camera
    co.data.type = "ORTHO"
    co.data.clip_end = 10.0
    files = []
    for view in ("front", "side"):
        left, top, w, h = sd.frame(D, view)
        sc.render.resolution_x = int(w * sd.PX_PER_CM)
        sc.render.resolution_y = int(h * sd.PX_PER_CM)
        co.data.ortho_scale = max(w, h) * CM
        cz = (top - h / 2) * CM
        if view == "front":
            co.location = ((left + w / 2) * CM, -3.0, cz)
            co.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        else:  # from -X looking +X: -Y (out of the wall) to the right
            co.location = (-3.0, -(left + w / 2) * CM, cz)
            co.rotation_euler = (math.radians(90.0), 0.0, math.radians(-90.0))
        path = folder / f"ortho_{view}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files.append(path.name)
    return files


def concept_views(refs: Path, folder: Path) -> list:
    """The drawing's straight views cut and scaled to the ortho frames at the drawing's own scale ([measure])."""
    import numpy as np

    files = []
    for view in ("front", "side"):
        img = bpy.data.images.load(str(refs / f"{view}-ortho.jpg"))
        sw, sh = img.size
        src = np.empty(sw * sh * 4, dtype=np.float32)
        img.pixels.foreach_get(src)
        src = src.reshape(sh, sw, 4)[::-1]
        left, top, w, h = sd.frame(D, view)
        tw, th = int(w * sd.PX_PER_CM), int(h * sd.PX_PER_CM)
        us = left + (np.arange(tw) + 0.5) / sd.PX_PER_CM
        hs = top - (np.arange(th) + 0.5) / sd.PX_PER_CM
        m = D["measure"][view]
        k = m["px_per_cm"]
        xs = (m["cx"] if view == "front" else m["wall"]) + us * k
        ys = m["bottom"] - (hs - D["measure"]["bottom_h"]) * k
        xi = np.clip(xs, 0, sw - 1).astype(int)
        yi = np.clip(ys, 0, sh - 1).astype(int)
        cut = src[yi][:, xi].copy()
        cut[(ys < 0) | (ys > sh - 1)] = (0.05, 0.07, 0.11, 1.0)
        cut[:, (xs < 0) | (xs > sw - 1)] = (0.05, 0.07, 0.11, 1.0)
        out = bpy.data.images.new(f"concept_{view}", tw, th, alpha=True)
        out.pixels.foreach_set(cut[::-1].ravel())
        path = folder / f"concept_{view}.png"
        out.filepath_raw = str(path)
        out.file_format = "PNG"
        out.save()
        files.append(path.name)
    return files


def overlays(folder: Path) -> list:
    """socket_drawing.lines over the ortho render and over the concept: overlay_<model|concept>_<view>.png, and the
    four side by side (overlay.png)."""
    import numpy as np

    colours = {"axis": (0.5, 0.9, 1.0), "slot": (1.0, 0.7, 0.28), "bay": (1.0, 0.45, 0.2), "open": (1.0, 0.48, 0.85)}
    files, panels = [], []
    for view in ("front", "side"):
        left, top, w, h = sd.frame(D, view)
        tw, th = int(w * sd.PX_PER_CM), int(h * sd.PX_PER_CM)
        for under in ("concept", "model"):
            name = f"ortho_{view}.png" if under == "model" else f"concept_{view}.png"
            img = bpy.data.images.load(str(folder / name))
            pix = np.empty(tw * th * 4, dtype=np.float32)
            img.pixels.foreach_get(pix)
            pix = pix.reshape(th, tw, 4)[::-1].copy()
            pix[..., :3] *= 0.75
            for lname, pts, closed in sd.lines(D)[view]:
                col = colours.get(lname, (1.0, 0.85, 0.4))
                seq = pts + ([pts[0]] if closed else [])
                for (ua, ha), (ub, hb) in zip(seq, seq[1:]):
                    xa, ya = (ua - left) * sd.PX_PER_CM, (top - ha) * sd.PX_PER_CM
                    xb, yb = (ub - left) * sd.PX_PER_CM, (top - hb) * sd.PX_PER_CM
                    n = int(max(abs(xb - xa), abs(yb - ya)) * 2) + 2
                    t = np.linspace(0.0, 1.0, n)
                    xs = np.clip(np.round(xa + (xb - xa) * t).astype(int), 0, tw - 1)
                    ys = np.clip(np.round(ya + (yb - ya) * t).astype(int), 0, th - 1)
                    pix[ys, xs, :3] = col
                    pix[ys, xs, 3] = 1.0
            pix[..., 3] = 1.0
            panels.append(pix)
            out = bpy.data.images.new(f"overlay_{under}_{view}", tw, th, alpha=True)
            out.pixels.foreach_set(pix[::-1].ravel())
            path = folder / f"overlay_{under}_{view}.png"
            out.filepath_raw = str(path)
            out.file_format = "PNG"
            out.save()
            files.append(path.name)
    gap = np.full((panels[0].shape[0], 8, 4), (0.95, 0.95, 0.95, 1.0), dtype=np.float32)
    row = np.concatenate([x for p in panels for x in (p, gap)][:-1], axis=1)
    out = bpy.data.images.new("overlay", row.shape[1], row.shape[0], alpha=True)
    out.pixels.foreach_set(row[::-1].ravel())
    out.filepath_raw = str(folder / "overlay.png")
    out.file_format = "PNG"
    out.save()
    return files + ["overlay.png"]


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    build_materials()
    ob = build_mesh()
    claws = [claw_leaf(1), claw_leaf(-1)]
    bpy.context.view_layer.update()
    cols = colliders()
    anc = anchor()
    export(out)
    info = mesh_info(ob, claws)
    info["anchor_cm"] = {"u": 0.0, "d": D["mount"]["axis_d"], "h": D["mount"]["tip_h"]}
    info["mount_cm"] = D["mount"]["h"]
    info["colliders"] = {c.name: len(c.data.polygons) for c in cols + [c.children[0] for c in claws]}
    k = D["claw"]
    info["claws"] = {"nodes": [c.name for c in claws], "hinge_cm": {"u": k["hinge"][0], "h": k["hinge"][1]},
                     "open_deg": k["open"], "open_drawn_deg": k["open_drawn"], "pull_cm": k["pull"],
                     "axis": "local glTF +Z (out of the wall): claw_r +open, claw_l -open"}
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "crystal_socket.blend"), compress=True)
    renders = []
    if a["crystal"]:
        crystal = import_crystal(Path(a["crystal"]), anc.location.copy())
        info["checks"] = checks(ob, claws, cols, crystal)
        info["checks"].update(swing(ob, claws, crystal))
        for c in cols + [c.children[0] for c in claws]:
            c.hide_render = True
        anc.hide_render = True
        folder = out / "renders"
        folder.mkdir(exist_ok=True)
        stage(a["samples"])
        renders += shoot_ortho(folder)
        if a["refs"]:
            renders += concept_views(Path(a["refs"]), folder)
            renders += overlays(folder)
    info["renders"] = renders
    (out / "build.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("SOCKET_BUILD " + json.dumps(info))


main()
