"""Builds the lobby hall's grey massing, one GLB per piece (art #356, docs/lobby.md): run by `lobby --build`.

    blender -b --python lobby_build.py -- --request <request.json> --out <dir>

request.json (tools/runner/commands/lobby.py): {"layout": <layouts/lobby/hall.toml>, "arc": [r, cz], "ring_z": z}.
Parts are written in the lobby's (Godot's) frame (x, y up, z south) and turned into Blender's (x, -z, y), so the GLB
(Y up) holds the lobby's frame again. A piece with collide gets its parts named `<name>-col` (Godot's importer makes
a trimesh static body of each). Writes <out>/<id>.glb and <out>/build_report.json: per piece its triangles, objects,
materials and bounds in the lobby's frame."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

EXPORT = {"export_format": "GLB", "use_selection": False, "use_visible": False, "use_renderable": False,
          "use_active_collection": False, "export_yup": True, "export_apply": True, "export_skins": False,
          "export_animations": False, "export_morph": False, "export_cameras": False, "export_lights": False,
          "export_materials": "EXPORT", "export_texcoords": True, "export_normals": True}
# The grey massing's colours (linear): neutral greys a step apart so the forms read; the door ochre, the lamp red.
MATS = {"lobby_floor": (0.30, 0.30, 0.31, 1), "lobby_grout": (0.08, 0.08, 0.09, 1), "lobby_ring": (0.55, 0.42, 0.20, 1),
        "lobby_wall": (0.42, 0.42, 0.43, 1), "lobby_pilaster": (0.33, 0.33, 0.34, 1), "lobby_vault": (0.38, 0.38, 0.39, 1),
        "lobby_rib": (0.28, 0.28, 0.29, 1), "lobby_frame": (0.20, 0.20, 0.21, 1), "lobby_glass": (0.45, 0.6, 0.8, 0.12),
        "lobby_door": (0.45, 0.36, 0.12, 1), "lobby_lamp": (1.0, 0.05, 0.03, 1), "lobby_trim": (0.24, 0.24, 0.25, 1)}
ARC_STEP_DEG = 2.0


# --- parts ---------------------------------------------------------------------------------------------------------
class Part:
    def __init__(self, name: str, mat: str, closed: bool = True):
        self.name, self.mat, self.closed = name, mat, closed
        self.verts: list[tuple[float, float, float]] = []
        self.faces: list[list[int]] = []

    def face(self, pts, normal=None):
        """A face from lobby-frame points; with normal, turned to face it."""
        pts = list(pts)
        if normal is not None:
            n = _normal(pts)
            if sum(a * b for a, b in zip(n, normal)) < 0:
                pts.reverse()
        base = len(self.verts)
        self.verts += [tuple(map(float, p)) for p in pts]
        self.faces.append(list(range(base, base + len(pts))))

    def box(self, x0, x1, y0, y1, z0, z1):
        c = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        mid = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        for quad in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            pts = [c[i] for i in quad]
            ctr = [sum(p[k] for p in pts) / 4 for k in range(3)]
            self.face(pts, [ctr[k] - mid[k] for k in range(3)])

    def loft(self, sections):
        """A closed solid through sections of four points each (same order), capped at both ends."""
        k = len(sections[0])
        for s0, s1 in zip(sections, sections[1:]):
            for i in range(k):
                self.face([s0[i], s0[(i + 1) % k], s1[(i + 1) % k], s1[i]])
        self.face(list(reversed(sections[0])))
        self.face(list(sections[-1]))


def _normal(pts):
    a, b, c = pts[0], pts[1], pts[2]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]


def prism(part: Part, poly, y0, y1):
    """A solid from a plan polygon [(x, z)] between heights y0 and y1."""
    part.face([(x, y1, z) for x, z in poly], (0, 1, 0))
    part.face([(x, y0, z) for x, z in poly], (0, -1, 0))
    n = len(poly)
    cx, cz = sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n
    for i in range(n):
        (ax, az), (bx, bz) = poly[i], poly[(i + 1) % n]
        mx, mz = (ax + bx) / 2, (az + bz) / 2
        part.face([(ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az)], (mx - cx, 0, mz - cz))


# --- the hall's numbers --------------------------------------------------------------------------------------------
class Hall:
    def __init__(self, req):
        self.L = req["layout"]
        self.h, self.w, self.a, self.d = self.L["hall"], self.L["window"], self.L["arch"], self.L["door"]
        self.R, self.CZ = req["arc"]
        self.ring_z = req["ring_z"]
        self.a0 = math.asin(self.h["x1"] / self.R)

    def arc_z(self, x):
        return self.CZ + math.sqrt(max(0.0, self.R * self.R - x * x))

    def vault_y(self, x):
        half, rise = (self.h["x1"] - self.h["x0"]) / 2, self.h["apex"] - self.h["wall"]
        rv = (half * half + rise * rise) / (2 * rise)
        return self.h["apex"] - rv + math.sqrt(max(0.0, rv * rv - x * x))

    def arc_pt(self, ang, dr=0.0):
        """A point (x, z) on the window arc at angle ang (0 = south), dr further out."""
        r = self.R + dr
        return r * math.sin(ang), self.CZ + r * math.cos(ang)

    def angles(self, a0=None, a1=None):
        a0 = -self.a0 if a0 is None else a0
        a1 = self.a0 if a1 is None else a1
        n = max(1, math.ceil(math.degrees(a1 - a0) / ARC_STEP_DEG))
        return [a0 + (a1 - a0) * i / n for i in range(n + 1)]


# --- the pieces ----------------------------------------------------------------------------------------------------
def floor(H: Hall) -> list[Part]:
    h, t = H.h, H.h["wall_t"]
    slab = Part("floor_slab", "lobby_grout")
    arc = [H.arc_pt(a) for a in reversed(H.angles())]   # east to west
    prism(slab, [(h["x0"] - t, h["zN"] - t), (h["x1"] + t, h["zN"] - t), (h["x1"] + t, h["zS"]), *arc,
                 (h["x0"] - t, h["zS"])], -0.3, 0.0)
    plates = Part("floor_plates", "lobby_floor", closed=False)
    g, inset, y = h["tile"], 0.025, 0.004
    x = h["x0"]
    while x < h["x1"] - 1e-6:
        z = h["zN"]
        while z < h["zS"] + h["bulge"] - 1e-6:
            x0, x1, z0, z1 = x + inset, x + g - inset, z + inset, z + g - inset
            south = [(xx, min(z1, H.arc_z(xx) - inset)) for xx in (x1, x1 - (x1 - x0) / 3, x0 + (x1 - x0) / 3, x0)]
            if all(sz > z0 + 0.05 for _sx, sz in south):
                plates.face([(x0, y, z0), (x1, y, z0)] + [(sx, y, sz) for sx, sz in south], (0, 1, 0))
            z += g
        x += g
    ring = Part("floor_ring", "lobby_ring", closed=False)
    r0, r1, n = H.L["floor"]["ring_r"] - 0.1, H.L["floor"]["ring_r"] + 0.1, 128
    for i in range(n):
        a, b = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        ring.face([(r0 * math.sin(a), 0.007, H.ring_z + r0 * math.cos(a)), (r1 * math.sin(a), 0.007, H.ring_z + r1 * math.cos(a)),
                   (r1 * math.sin(b), 0.007, H.ring_z + r1 * math.cos(b)), (r0 * math.sin(b), 0.007, H.ring_z + r0 * math.cos(b))], (0, 1, 0))
    return [slab, plates, ring]


def _cut(span, holes):
    """The parts of span (a, b) outside holes [(a, b, y_top)]: [(a, b, None)] full height or (a, b, y) above y."""
    a, b = span
    out, cur = [], a
    for h0, h1, top in sorted(holes):
        if h0 > cur:
            out.append((cur, h0, None))
        out.append((h0, h1, top))
        cur = h1
    if cur < b:
        out.append((cur, b, None))
    return out


def walls(H: Hall) -> list[Part]:
    h, t, dw, wall = H.h, H.h["wall_t"], H.d["w"] / 2, H.h["wall"]
    part = Part("walls", "lobby_wall")
    doors = {"W": [], "E": [], "N": []}
    for _id, w, at in H.d["doors"]:
        doors[w].append((at - dw, at + dw, H.d["h"]))
    doors["N"].append((-H.a["w"] / 2, H.a["w"] / 2, H.a["h"]))
    for side, x0, x1 in (("W", h["x0"] - t, h["x0"]), ("E", h["x1"], h["x1"] + t)):
        for z0, z1, top in _cut((h["zN"], h["zS"]), doors[side]):
            part.box(x0, x1, top or 0.0, wall, z0, z1)
    for xa, xb, top in _cut((h["x0"] - t, h["x1"] + t), doors["N"]):
        part.box(xa, xb, top or 0.0, wall, h["zN"] - t, h["zN"])
    pil = Part("pilasters", "lobby_pilaster")
    pw, pd = h["pilaster_w"] / 2, h["pilaster_d"]
    for z in h["ribs"]:
        pil.box(h["x0"], h["x0"] + pd, 0.0, wall, z - pw, z + pw)
        pil.box(h["x1"] - pd, h["x1"], 0.0, wall, z - pw, z + pw)
    for x in h["north_pilasters"]:
        pil.box(x - pw, x + pw, 0.0, wall, h["zN"], h["zN"] + pd)
    return [part, pil]


def vault(H: Hall) -> list[Part]:
    h = H.h
    shell = Part("vault_shell", "lobby_vault", closed=False)
    n = 40
    xs = [h["x0"] + (h["x1"] - h["x0"]) * i / n for i in range(n + 1)]
    for xa, xb in zip(xs, xs[1:]):
        ya, yb = H.vault_y(xa), H.vault_y(xb)
        shell.face([(xa, ya, h["zN"] - h["wall_t"]), (xb, yb, h["zN"] - h["wall_t"]), (xb, yb, H.arc_z(xb)), (xa, ya, H.arc_z(xa))], (0, -1, 0))
        # the lunettes: over the north wall and over the window's head, facing the hall
        shell.face([(xa, h["wall"], h["zN"]), (xb, h["wall"], h["zN"]), (xb, yb, h["zN"]), (xa, ya, h["zN"])], (0, 0, 1))
        za, zb = H.arc_z(xa), H.arc_z(xb)
        shell.face([(xa, h["wall"], za), (xb, h["wall"], zb), (xb, yb, zb), (xa, ya, za)], (0, 0, -1))
    ribs = Part("vault_ribs", "lobby_rib")
    pw, d = h["pilaster_w"] / 2, h["rib_d"]
    for z in h["ribs"]:
        secs = []
        for x in xs:
            y = H.vault_y(x)
            secs.append([(x, y - d, z - pw), (x, y - d, z + pw), (x, y + 0.05, z + pw), (x, y + 0.05, z - pw)])
        ribs.loft(secs)
    return [shell, ribs]


def window_frame(H: Hall) -> list[Part]:
    w, wall = H.w, H.h["wall"]
    parts = []
    bars = Part("window_bars", "lobby_frame")
    for name, y0, y1, d0, d1 in (("sill", 0.0, w["sill"], -0.1, 0.5), ("transom", w["transom"] - w["bar_h"] / 2, w["transom"] + w["bar_h"] / 2, -0.15, 0.25),
                                 ("head", wall - w["bar_h"], wall, -0.15, 0.25)):
        secs = []
        for a in H.angles():
            (ix, iz), (ox, oz) = H.arc_pt(a, d0), H.arc_pt(a, d1)
            secs.append([(ix, y0, iz), (ox, y0, oz), (ox, y1, oz), (ix, y1, iz)])
        bars.loft(secs)
    parts.append(bars)
    mull = Part("window_mullions", "lobby_frame")
    half = w["mullion_w"] / 2
    for a in [-H.a0 + 2 * H.a0 * i / w["panes"] for i in range(w["panes"] + 1)]:
        da = half / H.R
        pts = [H.arc_pt(a - da, -0.25), H.arc_pt(a + da, -0.25), H.arc_pt(a + da, 0.25), H.arc_pt(a - da, 0.25)]
        mull.loft([[(x, y, z) for x, z in pts] for y in (w["sill"], wall - w["bar_h"])])
    parts.append(mull)
    return parts


def window_glass(H: Hall) -> list[Part]:
    glass = Part("window_glass", "lobby_glass", closed=False)
    angs = H.angles()
    for a, b in zip(angs, angs[1:]):
        (ax, az), (bx, bz) = H.arc_pt(a, 0.05), H.arc_pt(b, 0.05)
        m = H.arc_pt((a + b) / 2)
        glass.face([(ax, H.w["sill"], az), (bx, H.w["sill"], bz), (bx, H.h["wall"] - H.w["bar_h"], bz), (ax, H.h["wall"] - H.w["bar_h"], az)],
                   (-m[0], 0, H.CZ - m[1]))
    return [glass]


def arch(H: Hall) -> list[Part]:
    h, a = H.h, H.a
    zN, t, w, ah, f, end = h["zN"], 0.3, a["w"] / 2, a["h"], a["frame"], h["zN"] - a["depth"]
    frame = Part("arch_frame", "lobby_trim")
    frame.box(-w - f, -w, 0.0, ah + f, zN, zN + 0.3)
    frame.box(w, w + f, 0.0, ah + f, zN, zN + 0.3)
    frame.box(-w, w, ah, ah + f, zN, zN + 0.3)
    shell = Part("corridor", "lobby_wall")
    back = zN - h["wall_t"]
    shell.box(-w - t, -w, 0.0, ah, end, back)
    shell.box(w, w + t, 0.0, ah, end, back)
    shell.box(-w - t, w + t, ah, ah + t, end - t, back)
    shell.box(-w - t, w + t, 0.0, ah, end - t, end)
    floor = Part("corridor_floor", "lobby_floor")
    floor.box(-w, w, -0.3, 0.0, end, back)
    door = Part("corridor_door", "lobby_door")
    door.box(-H.d["w"] / 2, H.d["w"] / 2, 0.0, H.d["h"], end, end + 0.12)
    return [frame, shell, floor, door]


def door(H: Hall) -> list[Part]:
    """A sealed door in its opening, facing +z (the hall); the wall's inner face at z 0, its outer at -wall_t."""
    w, dh, t = H.d["w"] / 2, H.d["h"], H.h["wall_t"]
    slab = Part("door_slab", "lobby_door")
    slab.box(-w, w, 0.0, dh, -0.35, -0.15)
    trim = Part("door_frame", "lobby_trim")
    trim.box(-w - 0.3, -w, 0.0, dh + 0.3, -t, 0.12)
    trim.box(w, w + 0.3, 0.0, dh + 0.3, -t, 0.12)
    trim.box(-w, w, dh, dh + 0.3, -t, 0.12)
    lamp = Part("door_lamp", "lobby_lamp")
    lamp.box(-0.25, 0.25, H.d["lamp"] - 0.15, H.d["lamp"] + 0.15, 0.0, 0.15)
    return [slab, trim, lamp]


BUILDERS = {"floor": floor, "walls": walls, "vault": vault, "window_frame": window_frame,
            "window_glass": window_glass, "arch": arch, "door": door}


# --- Blender -------------------------------------------------------------------------------------------------------
def clear() -> None:
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials):
        for item in list(coll):
            coll.remove(item)


def material(name: str):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    rgba = MATS[name]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.85 if name != "lobby_glass" else 0.05
    if name == "lobby_lamp":
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = 4.0
    if rgba[3] < 1:
        bsdf.inputs["Alpha"].default_value = rgba[3]
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        else:
            mat.blend_method = "BLEND"
    return mat


def make(part: Part, collide: bool):
    name = part.name + ("-col" if collide else "")
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x, -z, y) for x, y, z in part.verts], [], part.faces)
    mesh.validate()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    if part.closed:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material(part.mat))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def build(piece: dict, H: Hall, out: Path) -> dict:
    clear()
    parts = BUILDERS[piece["id"]](H)
    objs = [make(p, piece.get("collide", False) and p.mat not in ("lobby_lamp",)) for p in parts]
    glb = out / f"{piece['id']}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), **EXPORT)
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    return {"glb": glb.as_posix(), "triangles": sum(len(pl.vertices) - 2 for o in objs for pl in o.data.polygons),
            "objects": [o.name for o in objs], "materials": sorted({p.mat for p in parts}),
            "bounds": {"min": [lo[0], lo[2], -hi[1]], "max": [hi[0], hi[2], -lo[1]]}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    req = json.loads(Path(argv[argv.index("--request") + 1]).read_text(encoding="utf-8"))
    out = Path(argv[argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)
    H = Hall(req)
    report = {"pieces": {}}
    for piece in req["layout"]["pieces"]:
        report["pieces"][piece["id"]] = build(piece, H, out)
        print(f"LOBBY built {piece['id']}: {report['pieces'][piece['id']]['triangles']} triangles")
    (out / "build_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print(f"LOBBY done {len(report['pieces'])} pieces")


if __name__ == "__main__":
    main()
