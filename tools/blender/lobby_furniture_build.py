"""The lobby's bar (art #389), mirror (art #390) and match console (art #391): Gate 2's rough builds from code in
headless Blender, each from its drawing as numbers (tools/blender/bar_dims.toml, mirror_dims.toml,
match_console_dims.toml; centimetres), without copper (the engineer, 2026-11-23). The driver
(lobby_furniture_run.py) calls it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/lobby_furniture_build.py -- \
      --piece bar|mirror|match_console --out <dir>

Every point is written in Godot's axes (y up; each piece's frame: the origin on the floor under its middle, its
player side +z) and turned into Blender's (x, -z, y) at the end, so the GLB (+Y up) comes out in Godot's frame.
Writes <out>/<piece>.glb (the piece as one mesh named as the piece, a separate mesh for a surface the game draws on:
MirrorGlass, ConsoleScreen; the game's markers as empties: bar TapSpot and TapSpout, match_console Screen) and
<out>/<piece>.json (triangles by material, the bounds in cm, the markers).
"""

import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).parent
CM = 0.01
G2B = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # Godot (x, y, z) -> Blender (x, -z, y)
SPECS = {"bar": "bar_dims.toml", "mirror": "mirror_dims.toml", "match_console": "match_console_dims.toml"}
PIECE: list = []
LOOK: dict = {}
_MATS: dict = {}


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return {a[i].lstrip("-"): a[i + 1] for i in range(0, len(a) - 1, 2)}


def v3(p) -> Vector:
    return Vector((p[0] * CM, p[1] * CM, p[2] * CM))


def material(key: str) -> bpy.types.Material:
    if key in _MATS:
        return _MATS[key]
    srgb, metal, rough, emit = LOOK[key]
    rgb = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)   # sRGB -> linear
    m = bpy.data.materials.new(f"{PIECE[0]}_{key}")
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*rgb, 1.0)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    if emit:
        p.inputs["Emission Color"].default_value = (*rgb, 1.0)
        p.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = (*rgb, 1.0)
    _MATS[key] = m
    return m


class Part:
    """One material's geometry in Godot axes (cm in, metres out), chamfered on edges over 30 degrees."""

    def __init__(self, name: str, mat: str, bevel: float = 0.4, segs: int = 2) -> None:
        self.name, self.mat, self.bevel, self.segs = name, mat, bevel, segs
        self.bm = bmesh.new()

    def box(self, lo, hi) -> "Part":
        lo, hi = v3(lo), v3(hi)
        bmesh.ops.create_cube(self.bm, size=1.0,
                              matrix=Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*(hi - lo), 1.0)))
        return self

    def cyl(self, centre, axis: str, r: float, length: float, segs: int = 32, r2: float | None = None) -> "Part":
        rot = {"x": Matrix.Rotation(math.radians(90), 4, "Y"), "y": Matrix.Rotation(math.radians(-90), 4, "X"),
               "z": Matrix.Identity(4)}[axis]
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r * CM,
                              radius2=(r if r2 is None else r2) * CM, depth=length * CM,
                              matrix=Matrix.Translation(v3(centre)) @ rot)
        return self

    def loft(self, rings) -> "Part":
        """Closed rings of equal length (cm points), each joined to the next, capped at both ends."""
        vs = [[self.bm.verts.new(v3(p)) for p in ring] for ring in rings]
        n = len(vs[0])
        self.bm.faces.new(vs[0][::-1])
        self.bm.faces.new(vs[-1])
        for a, b in zip(vs, vs[1:]):
            for i in range(n):
                self.bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
        return self

    def plan(self, pts, y0: float, y1: float) -> "Part":
        """A plan polygon (x, z) pushed up from y0 to y1."""
        return self.loft([[(x, y0, z) for x, z in pts], [(x, y1, z) for x, z in pts]])

    def face(self, pts, z0: float, z1: float) -> "Part":
        """A front polygon (x, y) pushed along z from z0 to z1."""
        return self.loft([[(x, y, z0) for x, y in pts], [(x, y, z1) for x, y in pts]])

    def ribbon(self, pts, w: float, z0: float, z1: float, closed: bool = False) -> "Part":
        """A line of width w along the (x, y) points on a front plane, from z0 to z1: one box per segment, mitred
        enough by their overlap."""
        segs = list(zip(pts, pts[1:] + (pts[:1] if closed else [])))
        for (ax, ay), (bx, by) in segs:
            dx, dy = bx - ax, by - ay
            ln = math.hypot(dx, dy)
            if ln < 1e-6:
                continue
            nx, ny = -dy / ln * w / 2, dx / ln * w / 2
            ex, ey = dx / ln * w / 2, dy / ln * w / 2   # half a width past each end: closes the joints
            q = [(ax - ex + nx, ay - ey + ny), (bx + ex + nx, by + ey + ny), (bx + ex - nx, by + ey - ny),
                 (ax - ex - nx, ay - ey - ny)]
            self.face(q[::-1] if (dx * ny - dy * nx) > 0 else q, z0, z1)
        return self

    def annulus(self, r0: float, r1: float, y0: float, y1: float, segs: int = 64) -> "Part":
        ring = lambda r, y: [self.bm.verts.new(v3((r * math.cos(2 * math.pi * i / segs), y,  # noqa: E731
                                                   r * math.sin(2 * math.pi * i / segs)))) for i in range(segs)]
        a0, a1, b0, b1 = ring(r0, y0), ring(r1, y0), ring(r0, y1), ring(r1, y1)
        for i in range(segs):
            j = (i + 1) % segs
            for f in ((b0[i], b0[j], b1[j], b1[i]), (a1[i], a1[j], a0[j], a0[i]), (a1[i], b1[i], b1[j], a1[j]),
                      (a0[j], b0[j], b0[i], a0[i])):
                self.bm.faces.new(f)
        return self

    def obj(self) -> bpy.types.Object:
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:   # a box projection, one tile per metre
            ax = max(range(3), key=lambda i: abs(f.normal[i]))
            for lp in f.loops:
                a, b = [lp.vert.co[i] for i in range(3) if i != ax]
                lp[uvl].uv = (a, b)
        bm.transform(G2B)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        me.materials.append(material(self.mat))
        if self.bevel > 0:
            mod = ob.modifiers.new("chamfer", "BEVEL")
            mod.width = self.bevel * CM
            mod.segments = self.segs
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(30)
            dg = bpy.context.evaluated_depsgraph_get()
            baked = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            ob.modifiers.clear()
            ob.data = baked
            bpy.data.meshes.remove(me)
            baked.name = self.name
        ob.data.shade_smooth()
        ob.data.set_sharp_from_angle(angle=math.radians(30))
        return ob


def rounded_rect(hx: float, hz: float, r: float, n: int = 10) -> list:
    """A plan outline (x, z): a rectangle of half sizes hx, hz with corners of radius r, counter-clockwise."""
    r = max(0.5, min(r, hx, hz))
    pts = []
    for cx, cz, a0 in ((hx - r, hz - r, 0.0), (-(hx - r), hz - r, 90.0), (-(hx - r), -(hz - r), 180.0),
                       (hx - r, -(hz - r), 270.0)):
        for i in range(n + 1):
            a = math.radians(a0 + 90.0 * i / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def cut_rect(w: float, h: float, c: float, cy: float = 0.0) -> list:
    """A front outline (x, y) of w x h centred on (0, cy) with its corners cut by c, counter-clockwise."""
    x, y = w / 2, h / 2
    return [(-x + c, cy - y), (x - c, cy - y), (x, cy - y + c), (x, cy + y - c), (x - c, cy + y), (-x + c, cy + y),
            (-x, cy + y - c), (-x, cy - y + c)]


# --- the bar --------------------------------------------------------------------------------------------------------
def bar(D: dict) -> tuple[list, dict]:
    S, P, B, W, T, K = (D[k] for k in ("size", "plinth", "body", "swoosh", "top", "tap"))
    hx, hz, H = S["length"] / 2, S["depth"] / 2, S["height"]

    def outline(off: float) -> list:
        return rounded_rect(hx - off, hz - off, S["end_r"] - off)

    y_top0 = H - T["thick"]
    top = Part("top", "stone", bevel=T["round"], segs=3).plan(outline(0.0), y_top0, H)
    shell = Part("shell", "shell", bevel=0.8).plan(outline(B["inset"]), P["height"], y_top0)
    steel = Part("trims", "steel", bevel=0.4, segs=3).plan(outline(B["inset"] + P["inset"]), P["glow_h"], P["height"])
    glow = Part("glow", "glow", bevel=0.0)
    glow.plan(outline(B["inset"] + P["inset"] - 0.4), 0.0, P["glow_h"])                       # the floor line
    gy = y_top0 - T["glow_drop"]
    glow.plan(outline(B["inset"] - 0.3), gy - T["glow_h"], gy)                                 # under the top's lip
    zf = hz - B["inset"]                         # the long faces' flat planes
    seam = Part("seams", "steel", bevel=0.0)
    for sx in B["seam_x"]:
        for zs, z0, z1 in ((1, zf, zf + B["seam_d"]), (-1, -zf - B["seam_d"], -zf)):
            seam.box((sx - B["seam_w"] / 2, P["height"], z0), (sx + B["seam_w"] / 2, y_top0, z1))
    # the front's sweep: high near the ends, a long low run in the middle, smooth (cosine) between
    pts = []
    for i in range(61):
        x = W["ends_x"][0] + (W["ends_x"][1] - W["ends_x"][0]) * i / 60
        ax = abs(x)
        t = 0.0 if ax <= W["low_x"][1] else min(1.0, (ax - W["low_x"][1]) / (W["ends_x"][1] - W["low_x"][1]))
        pts.append((x, W["low_y"] + (W["top_y"] - W["low_y"]) * (1 - math.cos(math.pi * t)) / 2))
    steel_line = Part("swoosh", "steel", bevel=0.0).ribbon(pts, W["w"], zf - 0.1, zf + W["panel_proud"] + W["proud"])
    lower = Part("panel", "shell2", bevel=0.3)   # the swept lower panel: under the line, down to over the plinth
    foot = P["height"] + W["panel_bottom"]
    lower.face([(pts[0][0], foot)] + [(x, y - W["w"] / 2) for x, y in pts] + [(pts[-1][0], foot)], zf - 0.1,
               zf + W["panel_proud"])
    # the tap on the top at the long side's middle
    yb = H
    tap = Part("tap", "steel", bevel=0.3, segs=3)
    tap.cyl((0, yb + K["base_h"] / 2, K["at_z"]), "y", K["base_r"], K["base_h"], 40)
    cz, cw, cd = K["at_z"], K["column_w"], K["column_d"]
    col_top = yb + K["base_h"] + K["column_h"]
    tap.loft([[(-cw / 2, yb + K["base_h"], cz - cd / 2), (cw / 2, yb + K["base_h"], cz - cd / 2),
               (cw / 2, yb + K["base_h"], cz + cd / 2), (-cw / 2, yb + K["base_h"], cz + cd / 2)],
              [(-cw * 0.38, col_top, cz - cd * 0.38), (cw * 0.38, col_top, cz - cd * 0.38),
               (cw * 0.38, col_top, cz + cd * 0.38), (-cw * 0.38, col_top, cz + cd * 0.38)]])
    for s in (-1, 1):                            # the crest: two fins leaning out of the column's top
        x0 = s * cw * 0.12
        tap.loft([[(x0 - 1.2, col_top - 2, cz - 1.5), (x0 + 1.2, col_top - 2, cz - 1.5), (x0 + 1.2, col_top - 2, cz + 1.5),
                   (x0 - 1.2, col_top - 2, cz + 1.5)],
                  [(x0 + s * 3.0 - 0.3, col_top + K["crest_h"], cz - 0.3), (x0 + s * 3.0 + 0.3, col_top + K["crest_h"], cz - 0.3),
                   (x0 + s * 3.0 + 0.3, col_top + K["crest_h"], cz + 0.3), (x0 + s * 3.0 - 0.3, col_top + K["crest_h"], cz + 0.3)]])
    sy = yb + K["spout_y"]
    tap.cyl((0, sy, cz + cd / 2 + K["spout_len"] / 2), "z", K["spout_r"] * 1.6, K["spout_len"], 24, K["spout_r"])
    tip = (0.0, sy - 1.5, cz + cd / 2 + K["spout_len"])
    tap.cyl((0, sy - 0.8, tip[2]), "y", K["spout_r"] * 1.2, 2.0, 20)                        # the nozzle down
    tap.cyl((0, sy + K["handle_h"] / 2 + 1.0, cz + cd / 2 + 2.5), "y", 0.8, K["handle_h"], 16, 0.6)
    beer = Part("window", "beer", bevel=0.0)
    wz = cz + cd / 2 - 0.2                      # the window's face on the column's front, the column narrowing
    beer.face([(-K["window_w"] / 2, yb + K["base_h"] + K["window_y"]),
               (K["window_w"] / 2, yb + K["base_h"] + K["window_y"]),
               (K["window_w"] / 2 * 0.95, yb + K["base_h"] + K["window_y"] + K["window_h"]),
               (-K["window_w"] / 2 * 0.95, yb + K["base_h"] + K["window_y"] + K["window_h"])], wz - 0.5, wz + 0.4)
    parts = [top, shell, steel, glow, seam, steel_line, lower, tap, beer]
    pl = D["placement"]
    spot = [0.0, 0.0, math.hypot(pl["tap_spot"][0] - pl["origin"][0], pl["tap_spot"][2] - pl["origin"][2])]
    markers = {"TapSpout": (tip, 0.0), "TapSpot": (tuple(spot), 0.0)}
    return parts, {"markers": markers, "separate": []}


# --- the mirror -----------------------------------------------------------------------------------------------------
def mirror(D: dict) -> tuple[list, dict]:
    G, F, L, N = D["glass"], D["frame"], D["glow"], D["fins"]
    hw = G["w"] / 2
    back = Part("back", "back", bevel=0.6).box((-F["back_w"] / 2, 0.0, 0.0), (F["back_w"] / 2, F["back_h"], F["back_d"]))
    glass = Part("MirrorGlass", "glass", bevel=0.0).box((-hw, G["bottom"], G["front"] - G["thick"]),
                                                        (hw, G["bottom"] + G["h"], G["front"]))
    fr = Part("frame", "steel", bevel=0.3)
    zf0, zf1 = F["back_d"], G["front"] + 0.4
    y0, y1 = G["bottom"], G["bottom"] + G["h"]
    fw = F["w"]
    for s in (-1, 1):
        fr.box((s * hw if s > 0 else -hw - fw, y0, zf0), (hw + fw if s > 0 else -hw, y1 + fw, zf1))
    fr.box((-hw, y1, zf0), (hw, y1 + fw, zf1))
    glow = Part("glow", "glow", bevel=0.0)
    gx = hw + fw + L["gap"]
    for s in (-1, 1):
        a, b = sorted((s * gx, s * (gx + L["w"])))
        glow.box((a, y0, zf0), (b, y1, zf0 + L["d"] + 2.0))
    fins = Part("fins", "fin", bevel=0.25)
    tips = Part("fin_tips", "steel", bevel=0.2)
    base_x = gx + L["w"] + 1.0
    for s in (-1, 1):
        for xo, fy0, fy1, bw, d, lean in N["left"]:
            x = s * (base_x + xo)
            def section(y: float, k: float) -> list:   # a faceted crystal section: a back edge and a forward ridge
                shift = s * math.tan(math.radians(lean)) * (y - fy0)
                c = x + shift
                ridge = c + s * bw * (N["facet"] - 0.5) * k   # the front face off-centre, outward: a faceted look
                return [(c - bw / 2 * k, y, 0.0), (c + bw / 2 * k, y, 0.0), (ridge + bw * 0.1 * k, y, d * k),
                        (ridge - bw * 0.1 * k, y, d * k)]
            yt = fy1 - N["tip"]
            k_t = N["tip_width"]
            fins.loft([section(fy0, 1.0), section(yt, k_t)])
            tips.loft([section(yt, k_t), section(fy1, 0.04)])
    return [back, fr, glow, fins, tips, glass], {"markers": {"MirrorFace": ((0.0, G["bottom"] + G["h"] / 2, G["front"]), 0.0)},
                                                  "separate": ["MirrorGlass"]}


# --- the match console ----------------------------------------------------------------------------------------------
def match_console(D: dict) -> tuple[list, dict]:
    B, S, F, BA = D["body"], D["screen"], D["front"], D["base"]
    w, h, d = B["w"], B["h"], B["d"]
    tc, wi, wy = B["top_chamfer"], B["waist_in"], B["waist_y"]
    y0 = BA["h"]
    outline = [(-w / 2 + wi, y0), (w / 2 - wi, y0), (w / 2, wy), (w / 2, h - tc), (w / 2 - tc, h), (-w / 2 + tc, h),
               (-w / 2, h - tc), (-w / 2, wy)]
    body = Part("body", "body", bevel=0.8, segs=3).face(outline, -d / 2, d / 2)
    zf = d / 2
    facet = Part("facets", "facet", bevel=0.4)
    facet.face(cut_rect(S["w"] + 2 * S["bezel"], S["h"] + 2 * S["bezel"], S["corner"] + 1.5, S["centre_y"]), zf - 0.1, zf + 1.0)
    vt, vb = F["v_top_w"] / 2, F["v_bottom_w"] / 2
    facet.face([(-vb, F["v_bottom_y"] + y0), (vb, F["v_bottom_y"] + y0), (vt, F["v_top_y"]), (-vt, F["v_top_y"])],
               zf - 0.1, zf + F["proud"])
    steel = Part("seams", "steel", bevel=0.0)
    for sx in F["seams_x"]:
        lo_y = y0 + 6.0
        frac = lambda y: wi * (1 - min(1.0, (y - y0) / (wy - y0)))   # noqa: E731  (the taper's x at height y)
        s = 1 if sx > 0 else -1
        steel.ribbon([(sx - s * frac(lo_y) * abs(sx) / (w / 2), lo_y), (sx, wy), (sx, S["centre_y"] - S["h"] / 2 - S["bezel"] - 1.5)],
                     F["seam_w"], zf - 0.1, zf + 0.35)
    glow = Part("glow", "glow", bevel=0.0)
    glow.ribbon(cut_rect(S["w"] + S["line_w"] * 2 + 0.6, S["h"] + S["line_w"] * 2 + 0.6, S["corner"] + 0.6, S["centre_y"]),
                S["line_w"], zf + 1.0, zf + 1.25, closed=True)
    glow.annulus(BA["ring_r"] - BA["ring_w"] / 2, BA["ring_r"] + BA["ring_w"] / 2, BA["h"], BA["h"] + 0.3)
    base = Part("base", "floor", bevel=0.3).cyl((0, BA["h"] / 2, 0), "y", BA["r"], BA["h"], 64)
    screen = Part("ConsoleScreen", "screen", bevel=0.0).face(cut_rect(S["w"], S["h"], S["corner"], S["centre_y"]),
                                                            zf + 0.95, zf + 1.2)
    marker = (0.0, S["centre_y"], zf + 1.2)
    return [body, facet, steel, glow, base, screen], {"markers": {"Screen": (marker, 0.0)}, "separate": ["ConsoleScreen"]}


def join(objs: list, name: str) -> bpy.types.Object:
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]):
        bpy.ops.object.join()
    ob = objs[0]
    ob.name = ob.data.name = name
    return ob


def empty(name: str, at, yaw: float) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.05
    bpy.context.scene.collection.objects.link(ob)
    m = Matrix.Rotation(math.radians(yaw), 4, "Y")
    m.translation = v3(at)
    ob.matrix_world = G2B @ m @ G2B.inverted()
    return ob


def main() -> None:
    args = argv()
    piece, out = args["piece"], Path(args["out"])
    out.mkdir(parents=True, exist_ok=True)
    D = tomllib.loads((HERE / SPECS[piece]).read_text(encoding="utf-8"))
    PIECE.append(piece)
    LOOK.update(D["look"])
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    parts, extra = {"bar": bar, "mirror": mirror, "match_console": match_console}[piece](D)
    by_mat: dict = {}
    objs, separate = [], []
    for p in parts:
        ob = p.obj()
        n = sum(len(f.vertices) - 2 for f in ob.data.polygons)
        by_mat[f"{piece}_{p.mat}"] = by_mat.get(f"{piece}_{p.mat}", 0) + n
        (separate if p.name in extra["separate"] else objs).append(ob)
    main_ob = join(objs, piece)
    meshes = [main_ob, *separate]
    mk = [empty(n, at, yaw) for n, (at, yaw) in extra["markers"].items()]
    inv = G2B.inverted()
    pts = [inv @ (o.matrix_world @ v.co) for o in meshes for v in o.data.vertices]
    bounds = {"min": [round(min(p[i] for p in pts) / CM, 2) for i in range(3)],
              "max": [round(max(p[i] for p in pts) / CM, 2) for i in range(3)]}
    for o in bpy.context.scene.objects:
        o.select_set(o in meshes or o in mk)
    bpy.ops.export_scene.gltf(filepath=str(out / f"{piece}.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_vertex_color="NONE", export_extras=False,
                              export_cameras=False, export_lights=False)
    report = {"piece": piece, "triangles": sum(by_mat.values()), "triangles_by_material": by_mat,
              "meshes": [o.name for o in meshes], "bounds_cm": bounds,
              "markers": {n: [round(c, 2) for c in at] for n, (at, _y) in extra["markers"].items()}}
    (out / f"{piece}.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print("FURNITURE_BUILD " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
