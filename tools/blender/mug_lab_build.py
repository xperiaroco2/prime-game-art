"""The mug lab (research, art#392 follow-up): pipeline A, the beer stein of concept 3 built from code in headless
Blender at hero-prop quality, for the AI-art pipeline research. Not the art lane's build (lobby_furniture_build.py on
feat/lobby-furniture): this one tries what a release-quality held prop needs.

The frame is Godot's (y up, metres in the GLB; the numbers below in cm): the origin at the middle of the base's
underside, the handle on +x. Nodes (one GLB):
- `Mug`: the glass body and handle, one watertight mesh (boolean union), material `mug_glass`;
- `Beer` (empty): `Liquid` (a closed cylinder from the inside floor to the rim; the Godot shader cuts it at the fill
  level), `Foam` (the foam layer, its origin at its underside: the game moves it to the level), `FoamHead` (the head
  over the rim, shown only near full);
- `Grip` (empty): the handle's upright bar at mid height.

Args after "--": --out DIR [--spec path.toml]
"""
from __future__ import annotations

import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
CM = 0.01


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"out": None, "spec": str(HERE / "mug_lab.toml")}
    for i in range(0, len(a), 2):
        out[a[i].lstrip("-")] = a[i + 1]
    return out


def B(p) -> Vector:
    """Godot cm (x, y up, z) to Blender metres (x, -z, y): the glTF exporter's +Y up turns it back."""
    return Vector((p[0] * CM, -p[2] * CM, p[1] * CM))


# --- noise (deterministic, for the foam) -----------------------------------------------------------------------------
def _hash(i: int, j: int, k: int, seed: int) -> float:
    h = (i * 374761393 + j * 668265263 + k * 2147483647 + seed * 144665) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def vnoise(x: float, y: float, z: float, seed: int = 0) -> float:
    """Value noise in [-1, 1], smooth."""
    i, j, k = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - i, y - j, z - k
    sx, sy, sz = (f * f * (3 - 2 * f) for f in (fx, fy, fz))
    acc = 0.0
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                w = (sx if di else 1 - sx) * (sy if dj else 1 - sy) * (sz if dk else 1 - sz)
                acc += w * _hash(i + di, j + dj, k + dk, seed)
    return acc * 2 - 1


def fbm(x, y, z, seed=0, octaves=3) -> float:
    a, f, s, n = 1.0, 1.0, 0.0, 0.0
    for o in range(octaves):
        s += a * vnoise(x * f, y * f, z * f, seed + o * 17)
        n += a
        a *= 0.5
        f *= 2.1
    return s / n


# --- mesh helpers ----------------------------------------------------------------------------------------------------
def grid_mesh(name: str, rows: list[list], closed_u: bool = True, cap_first: bool = False, cap_last: bool = False):
    """A mesh from rows of Godot-cm points (each row a ring or a line), quads between rows; optional fan caps."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vr = [[bm.verts.new(B(p)) for p in row] for row in rows]
    n = len(rows[0])
    for a, b in zip(vr, vr[1:]):
        for i in range(n if closed_u else n - 1):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    for row, flip in ((vr[0], True), (vr[-1], False)) if (cap_first or cap_last) else ():
        if (row is vr[0] and not cap_first) or (row is vr[-1] and not cap_last):
            continue
        c = bm.verts.new(sum((v.co for v in row), Vector()) / len(row))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((row[j], row[i], c) if flip else (row[i], row[j], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def lerp_profile(prof: list, y: float) -> float:
    for (y0, r0), (y1, r1) in zip(prof, prof[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0) if y1 > y0 else 0.0
            t = t * t * (3 - 2 * t)
            return r0 + (r1 - r0) * t
    return prof[0][1] if y < prof[0][0] else prof[-1][1]


def stadium_sdf(u: float, y: float, half_w: float, y0: float, y1: float, corner: float) -> float:
    """Signed distance in (arc length u, height y) to a rounded rectangle centred at u 0 spanning y0..y1."""
    hh = (y1 - y0) / 2
    qx = abs(u) - half_w + corner
    qy = abs(y - (y0 + y1) / 2) - hh + corner
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - corner


def row_heights(Bd: dict) -> list:
    """The outer rows' heights: a coarse step, dense around every feature height (the pillows' ends, the profile)."""
    top = Bd["rim_y"]
    ys = set()
    y = 0.0
    while y < top:
        ys.add(round(y, 3))
        y += Bd["row_step"]
    for f in [p[0] for p in Bd["profile"]]:          # the profile's knees: a row on and either side
        for v in (f - Bd["dense_step"], f, f + Bd["dense_step"]):
            if 0.0 <= v <= top:
                ys.add(round(v, 3))
    for pn in Bd["pillows"]:                         # the panels' round ends: dense over the arch
        span = min(Bd["dense_span"], (pn["y1"] - pn["y0"]) / 2)
        for lo, hi in ((pn["y0"] - 0.2, pn["y0"] + span), (pn["y1"] - span, pn["y1"] + 0.2)):
            v = lo
            while v <= hi:
                if 0.0 <= v <= top:
                    ys.add(round(v, 3))
                v += Bd["dense_step"]
    ys.add(top)
    out = []
    for v in sorted(ys):
        if not out or v - out[-1] > 0.05:
            out.append(v)
    return out


def pillow(d: float, height: float, edge: float) -> float:
    """A flat-topped bulge for a signed distance d (negative inside), rounded over `edge` cm at its border."""
    if d >= 0:
        return 0.0
    s = min(-d / edge, 1.0)
    return height * math.sqrt(max(0.0, 1 - (1 - s) ** 2))


# --- the pieces ------------------------------------------------------------------------------------------------------
def body_outer(S: dict) -> list:
    Bd = S["body"]
    n_panels, per = Bd["panels"], Bd["segs_per_panel"]
    prof = [tuple(p) for p in Bd["profile"]]
    ys = row_heights(Bd)
    # angular samples: denser near each panel's edges (the grooves carry the highlights)
    local = [-1.0 + 2.0 * (0.5 - 0.5 * math.cos(math.pi * k / per)) for k in range(per)]
    thetas = [(p + (l + 1) / 2) * 2 * math.pi / n_panels for p in range(n_panels) for l in local]
    rows = []
    for y in ys:
        base = lerp_profile(prof, y)
        ring = []
        for th in thetas:
            ph = (th * n_panels / (2 * math.pi)) % 1.0           # 0..1 across a panel, 0.5 at its middle
            bulge = 0.0
            for pn in Bd["pillows"]:
                arc = 2 * math.pi * base / n_panels
                u = (ph - 0.5) * arc
                hw = arc / 2 - pn["groove"] / 2
                d = stadium_sdf(u, y, hw, pn["y0"], pn["y1"], min(pn["corner"], hw))
                bulge = max(bulge, pillow(d, pn["height"], pn["edge"]))
            r = base + bulge
            ring.append((r * math.cos(th), y, -r * math.sin(th)))
        rows.append(ring)
    return rows, thetas


def body(S: dict):
    Bd = S["body"]
    rows, thetas = body_outer(S)
    top = Bd["rim_y"]
    ri = Bd["inner_r"]
    lip = Bd["lip"]
    n = len(thetas)

    def ring(r, y):
        return [(r * math.cos(t), y, -r * math.sin(t)) for t in thetas]
    r_out = lerp_profile([tuple(p) for p in Bd["profile"]], top)
    # the rim: a rounded lip from the outer surface over to the inner wall
    rim = []
    for k in range(1, 6):
        a = math.pi * k / 6
        rc = (r_out + ri) / 2 + (r_out - ri) / 2 * math.cos(a)
        rim.append(ring(rc, top + lip * math.sin(a)))
    inner = [ring(ri, top), ring(ri, top - 1.0)]
    y = top - 1.0
    while y - Bd["inner_step"] > Bd["floor_y"] + Bd["floor_round"]:
        y -= Bd["inner_step"]
        inner.append(ring(ri, y))
    fr = Bd["floor_round"]
    for k in range(1, 5):                      # the inside floor's rounded corner
        a = math.pi / 2 * k / 4
        inner.append(ring(ri - fr + fr * math.cos(a), Bd["floor_y"] + fr - fr * math.sin(a)))
    inner.append(ring((ri - fr) * 0.5, Bd["floor_y"] - 0.05))   # the floor bulges a touch
    allrows = rows + rim + inner
    ob = grid_mesh("Mug", allrows, cap_last=True)
    # close the underside: a ring set from the first outer row in to the middle
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    first = bm.verts[:n]
    prev = first
    for r, yy in Bd["underside"]:
        cur = [bm.verts.new(B(p)) for p in ring(r, yy)]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((prev[j], prev[i], cur[i], cur[j]))
        prev = cur
    c = bm.verts.new(B((0.0, Bd["underside"][-1][1] + 0.05, 0.0)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((prev[j], prev[i], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def catmull(pts: list, n: int) -> list:
    out = []
    m = len(pts) - 1
    for i in range(n):
        t = i / (n - 1) * m
        k = min(int(t), m - 1)
        u = t - k
        p0, p1, p2, p3 = pts[max(k - 1, 0)], pts[k], pts[k + 1], pts[min(k + 2, m)]
        out.append(tuple(0.5 * ((2 * p1[j]) + (p2[j] - p0[j]) * u + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u * u
                                + (3 * p1[j] - p0[j] - 3 * p2[j] + p3[j]) * u ** 3) for j in range(2)))
    return out


def handle(S: dict):
    H = S["handle"]
    path = catmull([tuple(p) for p in H["path"]], H["samples"])
    sec_n = H["section_segs"]
    rows = []
    for i, (x, y) in enumerate(path):
        a, b = path[max(i - 1, 0)], path[min(i + 1, len(path) - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1.0
        nx, ny = ty / ln, -tx / ln
        t = i / (len(path) - 1)
        taper = 1.0 + H["taper"] * math.sin(math.pi * t)   # the loop a touch thicker at its middle
        w, d = H["width"] / 2 * taper, H["depth"] / 2 * taper
        ring = []
        for k in range(sec_n):   # a superellipse: a soft rounded rectangle, crisp but never sharp
            a_ = 2 * math.pi * k / sec_n
            c, s = math.cos(a_), math.sin(a_)
            e = H["squareness"]
            u = w * math.copysign(abs(c) ** e, c)
            v = d * math.copysign(abs(s) ** e, s)
            ring.append((x + nx * u, y + ny * u, v))
        rows.append(ring)
    ob = grid_mesh("Handle", rows, cap_first=True, cap_last=True)
    return ob


def thumb_rest(S: dict):
    T = S["thumb"]
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    ob = bpy.context.active_object
    ob.name = "Thumb"
    ob.scale = (T["size"][0] * CM, T["size"][2] * CM, T["size"][1] * CM)
    ob.location = B(T["at"])
    ob.rotation_euler = (0.0, math.radians(-T["tilt_deg"]), 0.0)
    bev = ob.modifiers.new("bevel", "BEVEL")
    bev.width = T["bevel"] * CM
    bev.segments = 3
    bpy.ops.object.modifier_apply(modifier="bevel")
    return ob


def union(base, others):
    for o in others:
        m = base.modifiers.new("u", "BOOLEAN")
        m.operation = "UNION"
        m.solver = "EXACT"
        m.object = o
        with bpy.context.temp_override(active_object=base, object=base):
            bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.data.objects.remove(o)
    return base


def liquid(S: dict):
    L, Bd = S["beer"], S["body"]
    r = Bd["inner_r"] - L["inset"]
    n = L["segments"]
    ys = [Bd["floor_y"] + 0.02]
    y = ys[0]
    while y < Bd["rim_y"] - 0.2:
        y = min(y + 2.5, Bd["rim_y"] - 0.2)
        ys.append(y)
    rows = []
    fr = Bd["floor_round"]
    for yy in ys:
        rr = r if yy > Bd["floor_y"] + fr else r - fr + math.sqrt(max(0.0, fr * fr - (Bd["floor_y"] + fr - yy) ** 2))
        rows.append([(rr * math.cos(2 * math.pi * k / n), yy, -rr * math.sin(2 * math.pi * k / n)) for k in range(n)])
    return grid_mesh("Liquid", rows, cap_first=True, cap_last=True)


def foam_unit(S: dict):
    """The foam as one canonical mesh (round 5): `rows` rings at UV.y = t along one profile and a pole at t = 1. The
    Godot foam shader (godot/mug_lab/foam.gdshader) evaluates the profile for the fill and puts every ring on it; the
    angle comes from the vertex's position, so the rings here are unit circles at any height."""
    F = S["foam"]
    n, rows = F["segments"], F["rows"]
    me = bpy.data.meshes.new("Foam")
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    ring = []
    for j in range(rows):
        t = j / rows
        ring.append(([bm.verts.new(B((math.cos(2 * math.pi * k / n), t, -math.sin(2 * math.pi * k / n))))
                      for k in range(n)], t))
    pole = bm.verts.new(B((0.0, 1.0, 0.0)))
    for (ra, ta), (rb, tb) in zip(ring, ring[1:]):
        for k in range(n):
            q = (k + 1) % n
            f = bm.faces.new((ra[k], ra[q], rb[q], rb[k]))
            for lp, t in zip(f.loops, (ta, ta, tb, tb)):
                lp[uv].uv = (0.0, t)
    last, tl = ring[-1]
    for k in range(n):
        q = (k + 1) % n
        f = bm.faces.new((last[k], last[q], pole))
        for lp, t in zip(f.loops, (tl, tl, 1.0)):
            lp[uv].uv = (0.0, t)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Foam", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def smooth(ob, angle: float):
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.set_sharp_from_angle(angle=math.radians(angle))


def mat(name: str, rgba, rough: float, alpha_blend: bool = False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = rough
    if alpha_blend:
        bsdf.inputs["Alpha"].default_value = rgba[3]
        m.surface_render_method = "BLENDED"
    return m


def tris(ob) -> int:
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    S = tomllib.loads(Path(a["spec"]).read_text(encoding="utf-8"))
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    glass = body(S)
    hnd = handle(S)
    parts = [hnd]
    if S["thumb"]["on"]:
        parts.append(thumb_rest(S))
    glass = union(glass, parts)
    smooth(glass, S["body"]["sharp_deg"])
    glass.data.materials.append(mat("mug_glass", (0.8, 0.88, 0.9, 0.2), 0.03, True))

    beer = bpy.data.objects.new("Beer", None)
    bpy.context.scene.collection.objects.link(beer)
    liq = liquid(S)
    smooth(liq, 30)
    liq.data.materials.append(mat("mug_beer", (0.55, 0.25, 0.02, 1.0), 0.15))
    fl = foam_unit(S)
    for p in fl.data.polygons:
        p.use_smooth = True
    fl.data.materials.append(mat("mug_foam", (0.95, 0.92, 0.85, 1.0), 0.7))
    for o in (liq, fl):
        o.parent = beer
    grip = bpy.data.objects.new("Grip", None)
    bpy.context.scene.collection.objects.link(grip)
    G = S["grip"]
    m = Matrix.Identity(4)
    m.translation = B(G["at"])
    # the Grip's +Y (Godot) up the bar = Blender +Z; its -Z (Godot) toward the mug's axis (-x) => Godot +Z = +x
    # Godot basis columns (x, y, z) = (0,0,-1)?: x = y cross z = (0,1,0) x (1,0,0) = (0,0,-1)
    gx, gy, gz = B((0, 0, -100)), B((0, 100, 0)), B((100, 0, 0))
    m.col[0][:3], m.col[1][:3], m.col[2][:3] = gx, gy, gz
    grip.matrix_world = m

    counts = {o.name: tris(o) for o in (glass, liq, fl)}
    for o in bpy.context.scene.objects:
        o.select_set(True)
    glb = out / "mug.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_normals=True, export_texcoords=True,
                              export_materials="EXPORT", export_extras=False, export_cameras=False,
                              export_lights=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "mug.blend"))
    rep = {"triangles": sum(counts.values()), "by_mesh": counts,
           "levels_cm": {"floor": S["body"]["floor_y"], "full": S["beer"]["full_level"], "rim": S["body"]["rim_y"],
                         "inner_r": S["body"]["inner_r"],
                         "rim_r": lerp_profile([tuple(p) for p in S["body"]["profile"]], S["body"]["rim_y"]),
                         "head_top": S["foam"]["head_top"]}}
    (out / "build.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print("MUG_LAB " + json.dumps(rep), flush=True)


if __name__ == "__main__":
    main()
