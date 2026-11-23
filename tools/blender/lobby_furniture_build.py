"""The lobby's bar (art #389), mirror (art #390) and match console (art #391): Gate 2's rough builds from code in
headless Blender, each from its drawing as numbers (tools/blender/bar_dims.toml, mirror_dims.toml,
match_console_dims.toml; centimetres), without copper (the engineer, 2026-11-23). The driver
(lobby_furniture_run.py) calls it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/lobby_furniture_build.py -- \
      --piece bar|mirror|match_console --out <dir>

Every point is written in Godot's axes (y up; each piece's frame: the origin on the floor under its middle, its
player side +z) and turned into Blender's (x, -z, y) at the end, so the GLB (+Y up) comes out in Godot's frame.
Writes <out>/<piece>.glb (the piece as one mesh named as the piece, a separate mesh for a surface the game draws on:
MirrorGlass, ConsoleScreen; the game's markers as empties: bar TapSpot and TapSpout, match_console Screen; the mug
(art #392, mug_dims.toml): the meshes Mug and Beer and the Grip marker, by the contract with the game) and
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
SPECS = {"bar": "bar_dims.toml", "mirror": "mirror_dims.toml", "match_console": "match_console_dims.toml",
         "mug": "mug_dims.toml"}
PIECE: list = []
STYLE: list = []   # --style: a piece's variant (the mirror's)
LOOK: dict = {}
_MATS: dict = {}
TEX: dict = {}      # Gate 3: {"rough": {look key: png}, "albedo": {look key: png}} (make_textures)


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return {a[i].lstrip("-"): a[i + 1] for i in range(0, len(a) - 1, 2)}


def v3(p) -> Vector:
    return Vector((p[0] * CM, p[1] * CM, p[2] * CM))


def material(key: str) -> bpy.types.Material:
    if key in _MATS:
        return _MATS[key]
    srgb, metal, rough, emit, *rest = LOOK[key]
    alpha = rest[0] if rest else 1.0
    rgb = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)   # sRGB -> linear
    m = bpy.data.materials.new(f"{PIECE[0]}_{key}")
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*rgb, 1.0)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    if emit:
        p.inputs["Emission Color"].default_value = (*rgb, 1.0)
        p.inputs["Emission Strength"].default_value = emit
    nt = m.node_tree
    if key in TEX.get("albedo", {}):     # Gate 3: a base colour image (the bar top's marble)
        img = nt.nodes.new("ShaderNodeTexImage")
        img.image = bpy.data.images.load(str(TEX["albedo"][key]))
        nt.links.new(img.outputs["Color"], p.inputs["Base Color"])
    if key in TEX.get("rough", {}):      # Gate 3: a roughness break-up in the green channel (stored as data)
        img = nt.nodes.new("ShaderNodeTexImage")
        img.image = bpy.data.images.load(str(TEX["rough"][key]))
        img.image.colorspace_settings.name = "Non-Color"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(img.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], p.inputs["Roughness"])
    if alpha < 1.0:   # glass and beer: alpha-blended in the GLB (Godot imports it as transparent)
        p.inputs["Alpha"].default_value = alpha
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        else:
            m.blend_method = "BLEND"
    m.diffuse_color = (*rgb, max(alpha, 0.2))
    _MATS[key] = m
    return m


class Part:
    """One material's geometry in Godot axes (cm in, metres out), chamfered on edges over 30 degrees."""

    def __init__(self, name: str, mat: str, bevel: float = 0.4, segs: int = 2, uv_m: float = 1.0) -> None:
        self.name, self.mat, self.bevel, self.segs, self.uv_m = name, mat, bevel, segs, uv_m
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
        # a box projection, one tile per uv_m metres; u always horizontal (x, or z on the faces facing x), so a
        # brushed grain runs along the length on every side (Gate 3)
        uv_axes = {0: (2, 1), 1: (0, 2), 2: (0, 1)}
        for f in bm.faces:
            ax = max(range(3), key=lambda i: abs(f.normal[i]))
            ia, ib = uv_axes[ax]
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co[ia] / self.uv_m, lp.vert.co[ib] / self.uv_m)
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


# --- Gate 3's textures (numpy in Blender; tiling, so the box UVs repeat without seams) ------------------------------
def _save(rgb, path: Path) -> None:
    import numpy as np
    h, w = rgb.shape[:2]
    im = bpy.data.images.new(path.stem, w, h, alpha=False)
    a = np.ones((h, w, 4), dtype=np.float32)
    a[..., :3] = np.clip(rgb, 0.0, 1.0)
    im.pixels.foreach_set(np.ascontiguousarray(a[::-1]).ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def _noise(n: int, seed: int, power: float, stretch: float = 1.0):
    """Periodic 1/f noise in -1..1; stretch > 1 draws streaks along u (the image's rows)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    fu, fv = np.fft.fftfreq(n)[None, :] * stretch, np.fft.fftfreq(n)[:, None]
    k = fu ** 2 + fv ** 2
    k[0, 0] = 1.0
    f = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((n, n))) / k ** (power / 2)))
    return (f - f.mean()) / (np.abs(f).max() + 1e-9)


def brushed(path: Path, base: float, amp: float, seed: int, n: int = 512) -> None:
    """A brushed metal's roughness: long streaks along u over soft blotches, in [base - amp, base + amp]."""
    import numpy as np
    val = np.clip(base + amp * (0.55 * _noise(n, seed, 1.6, stretch=24.0) + 0.45 * _noise(n, seed + 1, 1.8)), 0.05, 0.95)
    # roughness in G only; R and B 1: the GLB's metallicRoughness image multiplies metallicFactor by B
    _save(np.stack([np.ones_like(val), val, np.ones_like(val)], axis=2), path)


def marble(path: Path, base_srgb, vein_srgb, seed: int, n: int = 1024) -> None:
    """A dark polished stone: a mottled base and thin cool veins along a warped diagonal, tiling."""
    import numpy as np
    u = np.arange(n)[None, :] / n
    v = np.arange(n)[:, None] / n
    warp = _noise(n, seed, 3.0)          # smooth: a few broad bends, no crack-like zigzags (v4's 2.2 read as cracks)
    field = np.sin(2 * np.pi * (2 * u + 1 * v) + 3.0 * warp)
    veins = np.clip((1 - np.abs(field)) ** 7, 0.0, 1.0) * (0.6 + 0.4 * _noise(n, seed + 2, 2.6))
    mott = 1.0 + 0.22 * _noise(n, seed + 3, 2.4)
    b, c = np.array(base_srgb)[None, None, :], np.array(vein_srgb)[None, None, :]
    _save(b * mott[..., None] + (c - b) * (np.clip(veins, 0.0, 1.0)[..., None] * VEIN_MIX[0]), path)


VEIN_MIX = [0.45]   # the veins' strength over the base (set from [detail] vein_mix)


def make_textures(piece: str, D: dict, folder: Path) -> None:
    """Gate 3's images for a piece with a [detail] section into folder; fills TEX."""
    X = D.get("detail")
    if not X:
        return
    folder.mkdir(parents=True, exist_ok=True)
    rough, albedo = {}, {}
    if piece == "bar":
        VEIN_MIX[0] = X.get("vein_mix", VEIN_MIX[0])
        albedo["stone"] = folder / "bar_stone.png"
        marble(albedo["stone"], LOOK["stone"][0], X["vein"], 11)
        for i, key in enumerate(("shell", "shell2")):
            rough[key] = folder / f"bar_{key}_rough.png"
            brushed(rough[key], LOOK[key][2], X["shell_rough"], 21 + i)
    elif piece == "match_console":
        for i, key in enumerate(("body", "facet", "floor")):
            rough[key] = folder / f"console_{key}_rough.png"
            brushed(rough[key], LOOK[key][2], X["body_rough"], 31 + i)
    TEX.update({"rough": rough, "albedo": albedo})


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
    X = D.get("detail", {"stone_tile": 100.0, "shell_tile": 100.0, "swoosh_bevel": 0.0})
    hx, hz, H = S["length"] / 2, S["depth"] / 2, S["height"]

    def outline(off: float) -> list:
        return rounded_rect(hx - off, hz - off, S["end_r"] - off)

    y_top0 = H - T["thick"]
    top = Part("top", "stone", bevel=T["round"], segs=3, uv_m=X["stone_tile"] * CM).plan(outline(0.0), y_top0, H)
    shell = Part("shell", "shell", bevel=0.8, uv_m=X["shell_tile"] * CM).plan(outline(B["inset"]), P["height"], y_top0)
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
    steel_line = Part("swoosh", "steel", bevel=X["swoosh_bevel"], segs=2).ribbon(pts, W["w"], zf - 0.1, zf + W["panel_proud"] + W["proud"])
    lower = Part("panel", "shell2", bevel=0.3, uv_m=X["shell_tile"] * CM)   # the swept lower panel: under the line, down to over the plinth
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
    if "tray_w" in X:   # Gate 3's hardware: the drip tray's grate, the window's bezel, the lever's knob
        tz, tw, td = tip[2], X["tray_w"], X["tray_d"]
        tray = Part("tray", "steel", bevel=0.3, segs=2).box((-tw / 2, H, tz - td / 2),
                                                            (tw / 2, H + X["tray_h"], tz + td / 2))
        slots = Part("tray_slots", "dark", bevel=0.0)
        n = X["tray_slots"]
        for i in range(n):
            sx = -tw / 2 + tw * (i + 1) / (n + 1)
            slots.box((sx - X["slot_w"] / 2, H + X["tray_h"] - 0.15, tz - td / 2 + 1.5),
                      (sx + X["slot_w"] / 2, H + X["tray_h"] + 0.05, tz + td / 2 - 1.5))
        wy0 = yb + K["base_h"] + K["window_y"]
        ww, wh, bw = K["window_w"] / 2, K["window_h"], X["bezel_w"]
        bezel = Part("bezel", "steel", bevel=0.0).ribbon(
            [(-ww - bw / 2, wy0 - bw / 2), (ww + bw / 2, wy0 - bw / 2), (ww * 0.95 + bw / 2, wy0 + wh + bw / 2),
             (-ww * 0.95 - bw / 2, wy0 + wh + bw / 2)], bw, wz - 0.2, wz + 0.4 + X["bezel_proud"], closed=True)
        knob = Part("knob", "stone", bevel=0.4, segs=3, uv_m=X["stone_tile"] * CM).cyl(
            (0, sy + K["handle_h"] + 1.0 + X["knob_h"] / 2, cz + cd / 2 + 2.5), "y", X["knob_r"], X["knob_h"], 24,
            X["knob_r"] * 0.8)
        parts += [tray, slots, bezel, knob]
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
    style = STYLE[0] if STYLE else D["style"]["pick"]
    base_x = gx + L["w"] + 1.0
    extra_parts = mirror_dressing(D, style, base_x, hw, y1, zf0)
    return [back, fr, glow, *extra_parts, glass], {"markers": {"MirrorFace": ((0.0, G["bottom"] + G["h"] / 2, G["front"]), 0.0)},
                                                  "separate": ["MirrorGlass"]}


def _lens(cx: float, y: float, w: float, d: float, n: int = 12) -> list:
    """A rounded fin section at height y: a half ellipse w wide bulging d out of the wall (z 0), its back flat."""
    return [(cx + w / 2 * math.cos(math.pi * i / (n - 1)), y, max(0.0, d * math.sin(math.pi * i / (n - 1))))
            for i in range(n)]


def mirror_dressing(D: dict, style: str, base_x: float, hw: float, y_top: float, z0: float) -> list:
    """The mirror's sides by style (the engineer rejected the first build's spiky fins, 2026-11-23):
    "spikes" the first build's faceted fins with steel tips; "soft" broad rounded fins with domed steel caps, the
    concept's sheaf without points; "flat" low stepped slabs, a relief with steel inner edges; "frame" no fins: a wide
    rounded steel frame with a cyan line round the glass and a light bar on top."""
    S = D["style"][style] if style in D["style"] else {}
    parts = []
    if style == "spikes":
        N = D["fins"]
        fins, tips = Part("fins", "fin", bevel=0.25), Part("fin_tips", "steel", bevel=0.2)
        for s in (-1, 1):
            for xo, fy0, fy1, bw, d, lean in N["left"]:
                x = s * (base_x + xo)
                def section(y: float, k: float) -> list:
                    c = x + s * math.tan(math.radians(lean)) * (y - fy0)
                    ridge = c + s * bw * (N["facet"] - 0.5) * k
                    return [(c - bw / 2 * k, y, 0.0), (c + bw / 2 * k, y, 0.0), (ridge + bw * 0.1 * k, y, d * k),
                            (ridge - bw * 0.1 * k, y, d * k)]
                yt = fy1 - N["tip"]
                fins.loft([section(fy0, 1.0), section(yt, N["tip_width"])])
                tips.loft([section(yt, N["tip_width"]), section(fy1, 0.04)])
        return [fins, tips]
    if style == "soft":   # leaf blades: flat layered fins with a rounded tip, the concept's sheaf without points
        fins, edges = Part("fins", "fin", bevel=S["round_edge"], segs=4), Part("fin_edges", "steel", bevel=0.0)
        for s in (-1, 1):
            for xo, fy0, fy1, w, d, lean in S["fins"]:
                h = fy1 - fy0
                xi = base_x + xo
                xo_top = xi + w + math.tan(math.radians(lean)) * h * 0.6   # the outer edge, leaning out a little
                tip = (xi + w * 0.45 + math.tan(math.radians(lean)) * h, fy1)
                inner = (xi, fy0 + h * S["inner_to"])
                pts = [(xi, fy0), (xi + w, fy0), (xo_top, fy0 + h * 0.6)]
                for i in range(1, 9):   # a quadratic curve over the tip from the outer edge round to the inner one
                    t = i / 9
                    c1 = (tip[0] + w * 0.35, tip[1])
                    q0x = (1 - t) * xo_top + t * c1[0]
                    q0y = (1 - t) * (fy0 + h * 0.6) + t * c1[1]
                    q1x = (1 - t) * c1[0] + t * tip[0]
                    q1y = (1 - t) * c1[1] + t * tip[1]
                    pts.append(((1 - t) * q0x + t * q1x, (1 - t) * q0y + t * q1y))
                pts.append(tip)
                for i in range(1, 6):
                    t = i / 6
                    pts.append((tip[0] + (inner[0] - tip[0]) * t - math.sin(math.pi * t) * w * 0.12,
                                tip[1] + (inner[1] - tip[1]) * t))
                pts = [(s * px, py) for px, py in pts]
                fins.face(pts if s > 0 else pts[::-1], z0, z0 + d)
                ex = s * xi
                edges.box((min(ex, ex + s * 1.2), fy0, z0 + d - 0.3), (max(ex, ex + s * 1.2), inner[1], z0 + d + 0.3))
        return [fins, edges]
    if style == "flat":
        slabs, edges = Part("slabs", "fin", bevel=0.6, segs=3), Part("slab_edges", "steel", bevel=0.0)
        for s in (-1, 1):
            for xo, w, h, d in S["slabs"]:
                x0, x1 = base_x + xo, base_x + xo + w
                r = min(S["round"], w * 0.9)
                pts = [(x0, 0.0), (x1, 0.0), (x1, h - r)]
                for i in range(1, 7):   # the outer top corner rounded, the inner edge stands straight
                    a = math.pi / 2 * i / 6
                    pts.append((x1 - r + r * math.cos(a), h - r + r * math.sin(a)))
                pts.append((x0, h))
                pts = [(s * px, py) for px, py in pts]
                slabs.face(pts if s > 0 else pts[::-1], z0, z0 + d)
                edges.box((min(s * x0, s * (x0 + 1.4)), 0.0, z0 + d - 0.3), (max(s * x0, s * (x0 + 1.4)), h, z0 + d + 0.4))
        return [slabs, edges]
    # "frame": no fins
    fw, fd, r = S["width"], S["depth"], S["round"]
    frame = Part("wide_frame", "steel", bevel=0.0)
    line = Part("frame_line", "glow", bevel=0.0)
    hx, h0, h1 = hw + fw / 2 + 0.5, fw / 2, y_top + fw / 2 + 0.5   # its foot on the floor
    path = [(-hx, h0), (-hx, h1 - r)]
    for i in range(1, 8):
        a = math.pi - math.pi / 2 * i / 8
        path.append((-hx + r + r * math.cos(a), h1 - r + r * math.sin(a)))
    path += [(hx - r, h1)]
    for i in range(1, 8):
        a = math.pi / 2 - math.pi / 2 * i / 8
        path.append((hx - r + r * math.cos(a), h1 - r + r * math.sin(a)))
    path.append((hx, h0))
    frame.ribbon(path, fw, z0, z0 + fd)
    line.ribbon(path, S["line"], z0 + fd, z0 + fd + 0.3)   # the cyan line along the frame's middle
    bar = Part("light_bar", "glow", bevel=0.0)
    bw = S["bar_w"]
    bar.box((-bw / 2, h1 + fw / 2 + 3.0, z0), (bw / 2, h1 + fw / 2 + 3.0 + S["bar_h"], z0 + S["bar_d"]))
    housing = Part("light_housing", "steel", bevel=0.4)
    housing.box((-bw / 2 - 3, h1 + fw / 2 + 1.5, z0), (bw / 2 + 3, h1 + fw / 2 + 3.0, z0 + S["bar_d"] + 2))
    housing.box((-bw / 2 - 3, h1 + fw / 2 + 3.0 + S["bar_h"], z0), (bw / 2 + 3, h1 + fw / 2 + 4.5 + S["bar_h"], z0 + S["bar_d"] + 2))
    return [frame, line, bar, housing]


# --- the match console ----------------------------------------------------------------------------------------------
def match_console(D: dict) -> tuple[list, dict]:
    B, S, F, BA = D["body"], D["screen"], D["front"], D["base"]
    X = D.get("detail", {"body_tile": 100.0, "seam_bevel": 0.0, "seam_proud": 0.35})
    w, h, d = B["w"], B["h"], B["d"]
    tc, wi, wy = B["top_chamfer"], B["waist_in"], B["waist_y"]
    y0 = BA["h"]
    outline = [(-w / 2 + wi, y0), (w / 2 - wi, y0), (w / 2, wy), (w / 2, h - tc), (w / 2 - tc, h), (-w / 2 + tc, h),
               (-w / 2, h - tc), (-w / 2, wy)]
    body = Part("body", "body", bevel=0.8, segs=3, uv_m=X["body_tile"] * CM).face(outline, -d / 2, d / 2)
    zf = d / 2
    facet = Part("facets", "facet", bevel=0.4, uv_m=X["body_tile"] * CM)
    # Gate 3: the concept's metal frame in steel, a part of its own; without [detail] bezel_mat it stays in `facets`
    bezel = Part("bezel", X["bezel_mat"], bevel=0.4, segs=2) if "bezel_mat" in X else facet
    bezel.face(cut_rect(S["w"] + 2 * S["bezel"], S["h"] + 2 * S["bezel"], S["corner"] + 1.5, S["centre_y"]), zf - 0.1, zf + 1.0)
    vt, vb = F["v_top_w"] / 2, F["v_bottom_w"] / 2
    facet.face([(-vb, F["v_bottom_y"] + y0), (vb, F["v_bottom_y"] + y0), (vt, F["v_top_y"]), (-vt, F["v_top_y"])],
               zf - 0.1, zf + F["proud"])
    steel = Part("seams", "steel", bevel=X["seam_bevel"], segs=2)
    for sx in F["seams_x"]:
        lo_y = y0 + 6.0
        frac = lambda y: wi * (1 - min(1.0, (y - y0) / (wy - y0)))   # noqa: E731  (the taper's x at height y)
        s = 1 if sx > 0 else -1
        steel.ribbon([(sx - s * frac(lo_y) * abs(sx) / (w / 2), lo_y), (sx, wy), (sx, S["centre_y"] - S["h"] / 2 - S["bezel"] - 1.5)],
                     F["seam_w"], zf - 0.1, zf + X["seam_proud"])
    glow = Part("glow", "glow", bevel=0.0)
    glow.ribbon(cut_rect(S["w"] + S["line_w"] * 2 + 0.6, S["h"] + S["line_w"] * 2 + 0.6, S["corner"] + 0.6, S["centre_y"]),
                S["line_w"], zf + 1.0, zf + 1.25, closed=True)
    glow.annulus(BA["ring_r"] - BA["ring_w"] / 2, BA["ring_r"] + BA["ring_w"] / 2, BA["h"], BA["h"] + 0.3)
    base = Part("base", "floor", bevel=0.3, uv_m=X["body_tile"] * CM).cyl((0, BA["h"] / 2, 0), "y", BA["r"],
                                                                           BA["h"], 64)
    screen = Part("ConsoleScreen", "screen", bevel=0.0).face(cut_rect(S["w"], S["h"], S["corner"], S["centre_y"]),
                                                            zf + 0.95, zf + 1.2)
    marker = (0.0, S["centre_y"], zf + 1.2)
    parts = [body, facet, *([bezel] if bezel is not facet else []), steel, glow, base, screen]
    if "edge_in" in X:   # Gate 3: the concept's metal lines along the front's outer edges (its copper, steel here)
        e = X["edge_in"]
        lo = y0 + 6.0
        x_lo = w / 2 - wi * (1 - min(1.0, (lo - y0) / (wy - y0))) - e
        side = [(x_lo, lo), (w / 2 - e, wy), (w / 2 - e, h - tc - e * 0.41), (w / 2 - tc - e * 0.41 + e, h - e)]
        line = [(-x, y) for x, y in side] + [(x, y) for x, y in reversed(side)]
        steel.ribbon(line, X["edge_w"], zf - 0.1, zf + X["seam_proud"])   # Gate 3: the screen's dark gasket inside its bezel, the base plate's steel lip
        gw = X["gasket_w"]
        gasket = Part("gasket", "dark", bevel=0.0).ribbon(
            cut_rect(S["w"] + gw, S["h"] + gw, S["corner"] + gw / 2, S["centre_y"]), gw, zf + 0.9, zf + 1.1, closed=True)
        lip = Part("lip", "steel", bevel=0.2, segs=2).annulus(BA["r"] - X["lip_w"], BA["r"] + 0.2, 0.0,
                                                               BA["h"] + X["lip_h"], 96)
        parts += [gasket, lip]
    return parts, {"markers": {"Screen": (marker, 0.0)}, "separate": ["ConsoleScreen"]}


# --- the mug of beer ------------------------------------------------------------------------------------------------
def _ring(y: float, r: float, sides: int, fluted: bool, groove: float) -> list:
    return [(r * (1 - (groove if fluted and i % 2 else 0.0)) * math.cos(2 * math.pi * i / sides), y,
             -r * (1 - (groove if fluted and i % 2 else 0.0)) * math.sin(2 * math.pi * i / sides)) for i in range(sides)]


def _spline(pts: list, n: int) -> list:
    """n points along a Catmull-Rom curve through pts (its ends held)."""
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


def mug(D: dict) -> tuple[list, dict]:
    B, Hd, Be, G = D["body"], D["handle"], D["beer"], D["grip"]
    n, gr, wall = B["sides"], B["groove"], B["wall"]
    outer = [_ring(y, r, n, fl, gr) for y, r, fl in B["rings"]]
    top_y, rim_r = B["rings"][-1][0], B["rings"][-1][1]
    lip = B["rim_round"]
    rim = [_ring(top_y + lip * 0.6, rim_r - wall / 2, n, False, 0.0)]
    inner = []
    for y, r, _fl in reversed(B["rings"]):   # the inside follows the outside a wall in, down to the thick floor
        if y > B["floor_y"]:
            inner.append(_ring(y, r - wall, n, False, 0.0))
    inner.append(_ring(B["floor_y"], B["rings"][3][1] - wall - 0.3, n, False, 0.0))
    glass = Part("glass", "glass", bevel=0.0).loft(outer + rim + inner)
    # the handle: a rounded-rectangle section swept along the path in the xy plane
    path = _spline([tuple(p) for p in Hd["path"]], Hd["samples"])
    w, d = Hd["width"] / 2, Hd["depth"] / 2
    sec = [(w * 0.75, d), (w, d * 0.7), (w, -d * 0.7), (w * 0.75, -d), (-w * 0.75, -d), (-w, -d * 0.7), (-w, d * 0.7),
           (-w * 0.75, d)]
    rings = []
    for i, (x, y) in enumerate(path):
        a, b = path[max(i - 1, 0)], path[min(i + 1, len(path) - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1.0
        nx, ny = ty / ln, -tx / ln          # the in-plane normal (outward on the loop)
        rings.append([(x + nx * u, y + ny * u, v) for u, v in sec])
    handle = Part("handle", "glass", bevel=0.0).loft(rings)
    # the beer and its head, inside the glass
    ri = B["rings"][3][1] - wall - Be["inset"]
    liquid = Part("liquid", "beer", bevel=0.0).loft([_ring(B["floor_y"] + 0.05, ri - 0.2, n, False, 0.0),
                                                    _ring(Be["top_y"], ri, n, False, 0.0)])
    head = [_ring(Be["top_y"], ri, n, False, 0.0), _ring(top_y, rim_r - wall - Be["inset"], n, False, 0.0)]
    for dy, k in Be["foam_profile"]:   # the head's dome over the rim, swelling past it first
        head.append(_ring(top_y + dy, max(0.05, rim_r * k), n, False, 0.0))
    foam = Part("foam", "foam", bevel=0.0).loft(head)
    return [glass, handle, liquid, foam], {"markers": {"Grip": (tuple(G["at"]), 90.0)}, "separate": [],
                                           "groups": {"liquid": "Beer", "foam": "Beer"}, "main": "Mug"}


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
    if args.get("style"):
        STYLE.append(args["style"])
    LOOK.update(D["look"])
    make_textures(piece, D, out / "tex")
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    parts, extra = {"bar": bar, "mirror": mirror, "match_console": match_console, "mug": mug}[piece](D)
    by_mat: dict = {}
    objs, separate, grouped = [], [], {}
    for p in parts:
        ob = p.obj()
        n = sum(len(f.vertices) - 2 for f in ob.data.polygons)
        by_mat[f"{piece}_{p.mat}"] = by_mat.get(f"{piece}_{p.mat}", 0) + n
        if p.name in extra.get("groups", {}):   # parts joined into a named mesh of their own (the mug's Beer)
            grouped.setdefault(extra["groups"][p.name], []).append(ob)
        else:
            (separate if p.name in extra["separate"] else objs).append(ob)
    main_ob = join(objs, extra.get("main", piece))
    meshes = [main_ob, *separate, *(join(obs, g) for g, obs in grouped.items())]
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
