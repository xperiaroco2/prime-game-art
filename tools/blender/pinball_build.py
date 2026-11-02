"""The lobby's pinball machine (art #374), Gate 2's rough build from code in headless Blender (no Meshy): the cabinet
and the table's art from the drawing tools/blender/pinball_dims.toml (centimetres). The driver (pinball_run.py) calls
it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/pinball_build.py -- --out <dir> [--px 4]
      --earth <the night map, earth_night_cap.jpg>

Every point below is written in Godot's axes (y up; the cabinet frame: the origin on the floor under the footprint's
middle, the player on -z, the backbox at +z) and turned into Blender's (x, -z, y) at the end, so the GLBs (+Y up)
come out in Godot's frame. The tilted parts are written in the contract's table frame (the playfield's top at y 0,
-z up the table) and placed by MOUNT, TableMount's transform: 180 degrees about y, then the tilt (the far end up).

Two GLBs into --out:
- pinball.glb: the cabinet as one mesh `pinball` (the body with its rails, lockdown bar, front medallion, side buttons,
  side panels, legs with copper collars, cyan rings and pads, the backbox with its screen, cyan frame line, medallion,
  trims and rivets), and the markers TableMount, CloseUp and Display as empties (the game's greybox markers);
- pinball_table.glb: in the table frame, one mesh per contract body named as its node (WallLeft, WallRight, WallTop,
  InlaneLeft, InlaneRight, FlipperLeft, FlipperRight, Bumper, Kicker, Target) at the node's transform, the flippers'
  pivots at their origins, plus Playfield (the board) and Glass, and the markers BallStart and Drain.
Materials (Gate 3): pinball_teal_dark and pinball_teal_light with a roughness break-up texture, pinball_copper,
pinball_cyan (emissive), pinball_screen (dark glass), pinball_lens (the medallions' dark lenses), pinball_glass,
pinball_field and pinball_side_art (the night Earth: pinball_art.py's textures, --earth the night map), pinball_ivory
(the flippers), pinball_chrome (the domes). Bevels: a chamfer on every edge over 30 degrees, 2 segments (3 on the
copper). Rivets are flattened domes in rows.
Also build.json (triangles, bounds, the measured numbers), features.json (the model's feature edges for the drawing,
in the cabinet frame, cm) and renders/ortho_<front|side|top>.png (Workbench, orthographic, --px pixels per cm, framed
as pinball_drawing.py's views).
"""

import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).parent))
import pinball_art  # noqa: E402  (beside this file)

D = tomllib.loads(Path(__file__).with_name("pinball_dims.toml").read_text(encoding="utf-8"))
CM = 0.01
K, T, B, F, L, BB, MK = (D[k] for k in ("contract", "table", "body", "front", "legs", "backbox", "markers"))
TILT = math.radians(T["tilt_deg"])
SIN, COS = math.sin(TILT), math.cos(TILT)
H_C = (T["front_y"] + K["field"][1] / 2 * SIN) * CM      # TableMount's height: the field's front edge at front_y
Z_C = T["field_z"] * CM
MOUNT = Matrix(((-1, 0, 0, 0), (0, COS, -SIN, H_C), (0, -SIN, -COS, Z_C), (0, 0, 0, 1)))  # table frame -> cabinet
IDENT = Matrix.Identity(4)
G2B = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # Godot (x, y, z) -> Blender (x, -z, y)
# the drawing's views (pinball_drawing.py reads them from build.json): name: (width, height, centre h, centre v) in cm;
# front: h = -x, v = y (seen from the player); side: h = -z, v = y (from +x, the player on the right); top: h = -x, v = z
ORTHO = {"front": (110.0, 250.0, 0.0, 125.0), "side": (270.0, 250.0, 15.0, 125.0), "top": (110.0, 200.0, 0.0, 0.0)}
MATS = {  # name: (base RGB linear, metallic, roughness, emission strength, alpha); Gate 3 (step 2): tuned under the
    # hall's light L3 so the two greys read teal-grey beside the hall's S4 panels, not brown: less metal (the warm
    # pendants' reflections turned the metal brown), a cooler albedo, a roughness break-up (ROUGH) like the hall's panels
    "teal_dark": ((0.020, 0.060, 0.080), 0.12, 0.52, 0.0, 1.0),
    "teal_light": ((0.090, 0.200, 0.230), 0.20, 0.42, 0.0, 1.0),
    "copper": ((0.32, 0.17, 0.105), 0.9, 0.40, 0.0, 1.0),    # step 1's 0.78/0.40/0.22 at 0.28 glared orange
    "cyan": ((0.10, 0.80, 0.90), 0.0, 0.30, 1.4, 1.0),       # step 1's strength 5 bloomed to white
    "screen": ((0.008, 0.010, 0.014), 0.0, 0.08, 0.0, 1.0),
    "lens": ((0.090, 0.110, 0.125), 1.0, 0.14, 0.0, 1.0),    # the medallions' dark lenses (a dark chrome)
    "glass": ((0.10, 0.12, 0.13), 0.0, 0.02, 0.0, 0.05),
    "field": ((1.0, 1.0, 1.0), 0.0, 0.40, 0.55, 1.0),        # the playfield's night Earth (TEX), its lights glow
    "side_art": ((1.0, 1.0, 1.0), 0.0, 0.45, 0.35, 1.0),     # the side panels' night Earth (TEX)
    "ivory": ((0.82, 0.80, 0.74), 0.0, 0.35, 0.0, 1.0),
    "chrome": ((0.18, 0.19, 0.21), 1.0, 0.12, 0.0, 1.0),
}
TEX = {"field": "earth_field.png", "side_art": "earth_side.png"}   # base colour and emission from these images
ROUGH = {"teal_dark": ("rough_dark.png", 0.07), "teal_light": ("rough_light.png", 0.06)}   # file, +- around roughness
UV_CM = 40.0              # the box-projected UVs: one texture tile per 40 cm (the roughness break-up)
TEXDIR: list = []         # [the folder of the generated textures] (main sets it)
FEATURES: list = []       # [[a, b], [normals]] in the cabinet frame, cm


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"out": None, "px": "4", "earth": None}
    for i in range(0, len(a) - 1, 2):
        out[a[i].lstrip("-")] = a[i + 1]
    return out


def v3(p) -> Vector:
    return Vector((p[0] * CM, p[1] * CM, p[2] * CM))


def tf(p) -> Vector:
    """A table-frame point (cm) in the cabinet frame (m)."""
    return MOUNT @ v3(p)


class Part:
    """One material's geometry in Godot axes, built from boxes, cylinders, prisms and hulls (sizes in cm)."""

    def __init__(self, name: str, mat: str, bevel: float = B["chamfer"], features: bool = True,
                 frame: Matrix = IDENT, segs: int = 2, uv=None) -> None:
        self.name, self.mat, self.bevel, self.features, self.frame = name, mat, bevel, features, frame
        self.segs = segs          # the bevel's segments (step 1: 1; the CloseUp camera wants rounder edges)
        self.uv = uv              # a callable: point (m, the part's frame) -> (u, v); None: box projection
        self.bm = bmesh.new()

    def box(self, lo, hi, frame: Matrix | None = None) -> "Part":
        lo, hi = v3(lo), v3(hi)
        m = (frame or IDENT) @ Matrix.Translation((lo + hi) / 2) @ Matrix.Diagonal((*(hi - lo), 1.0))
        bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        return self

    def cyl(self, centre, axis: str, r: float, length: float, segs: int = 32, r2: float | None = None,
            frame: Matrix | None = None) -> "Part":
        rot = {"x": Matrix.Rotation(math.radians(90), 4, "Y"), "y": Matrix.Rotation(math.radians(-90), 4, "X"),
               "z": IDENT}[axis]
        m = (frame or IDENT) @ Matrix.Translation(v3(centre)) @ rot
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r * CM,
                              radius2=(r if r2 is None else r2) * CM, depth=length * CM, matrix=m)
        return self

    def hull(self, pts) -> "Part":
        """The convex hull of points already in metres (the part's frame)."""
        verts = [self.bm.verts.new(p) for p in pts]
        res = bmesh.ops.convex_hull(self.bm, input=verts)
        drop = {g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)}
        bmesh.ops.delete(self.bm, geom=list(drop), context="VERTS")
        return self

    def prism(self, pts, d, frame: Matrix | None = None) -> "Part":
        """A planar polygon (cm points) pushed along d (cm)."""
        f = frame or IDENT
        a = [self.bm.verts.new(f @ v3(p)) for p in pts]
        b = [self.bm.verts.new(f @ v3((p[0] + d[0], p[1] + d[1], p[2] + d[2]))) for p in pts]
        self.bm.faces.new(a[::-1])
        self.bm.faces.new(b)
        n = len(pts)
        for i in range(n):
            self.bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
        return self

    def sphere(self, centre, r: float, frame: Matrix | None = None) -> "Part":
        m = (frame or IDENT) @ Matrix.Translation(v3(centre))
        bmesh.ops.create_uvsphere(self.bm, u_segments=8, v_segments=5, radius=r * CM, matrix=m)
        return self

    def rivet(self, centre, normal, r: float, frame: Matrix | None = None) -> "Part":
        """A round-head rivet: a flattened dome (16 x 4 segments) on the surface at centre, its axis along normal."""
        f = frame or IDENT
        n = (f.to_3x3() @ Vector(normal)).normalized()
        rot = n.to_track_quat("Z", "Y").to_matrix().to_4x4()
        m = Matrix.Translation(f @ v3(centre)) @ rot @ Matrix.Diagonal((r * CM, r * CM, r * CM * 0.55, 1.0))
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=16, v_segments=8, radius=1.0, matrix=m)
        drop = [v for v in res["verts"] if (m.inverted() @ v.co).z < -0.05]
        bmesh.ops.delete(self.bm, geom=drop, context="VERTS")
        return self

    def obj(self) -> bpy.types.Object:
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:       # the art's own UVs, else a box projection (the roughness break-up's tiles)
            ax = max(range(3), key=lambda i: abs(f.normal[i]))
            for lp in f.loops:
                co = lp.vert.co
                if self.uv:
                    lp[uvl].uv = self.uv(co)
                else:
                    a, b = [co[i] for i in range(3) if i != ax]
                    lp[uvl].uv = (a / (UV_CM * CM), b / (UV_CM * CM))
        if self.features:
            for e in bm.edges:
                fs = e.link_faces
                if len(fs) != 2 or e.calc_face_angle(0.0) > math.radians(30):
                    a, b = (self.frame @ v.co for v in e.verts)
                    ns = [(self.frame.to_3x3() @ f.normal).normalized() for f in fs]
                    FEATURES.append([[round(c / CM, 2) for c in a], [round(c / CM, 2) for c in b],
                                     [[round(c, 3) for c in n] for n in ns]])
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
            mod.harden_normals = False
            dg = bpy.context.evaluated_depsgraph_get()
            baked = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            ob.modifiers.clear()
            ob.data = baked
            bpy.data.meshes.remove(me)
            baked.name = self.name
        ob.data.shade_smooth()
        ob.data.set_sharp_from_angle(angle=math.radians(30))
        return ob


_MATS: dict = {}


def material(name: str) -> bpy.types.Material:
    if name in _MATS:
        return _MATS[name]
    rgb, metal, rough, emit, alpha = MATS[name]
    m = bpy.data.materials.new("pinball_" + name)
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*rgb, 1.0)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    if emit:
        p.inputs["Emission Color"].default_value = (*rgb, 1.0)
        p.inputs["Emission Strength"].default_value = emit
    if alpha < 1.0:
        p.inputs["Alpha"].default_value = alpha
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        else:
            m.blend_method = "BLEND"
    nt = m.node_tree
    if name in TEX and TEXDIR:
        img = nt.nodes.new("ShaderNodeTexImage")
        img.image = bpy.data.images.load(str(TEXDIR[0] / TEX[name]))
        nt.links.new(img.outputs["Color"], p.inputs["Base Color"])
        nt.links.new(img.outputs["Color"], p.inputs["Emission Color"])
    if name in ROUGH and TEXDIR:
        img = nt.nodes.new("ShaderNodeTexImage")
        img.image = bpy.data.images.load(str(TEXDIR[0] / ROUGH[name][0]))
        img.image.colorspace_settings.name = "Non-Color"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(img.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], p.inputs["Roughness"])
    m.diffuse_color = (*rgb, max(alpha, 0.2))
    _MATS[name] = m
    return m


# --- the cabinet ---------------------------------------------------------------------------------------------------
def body_parts() -> list:
    """The tilted body, written in the table frame (x is mirrored by MOUNT: table +x is the cabinet's -x)."""
    w, t = B["outer_w"] / 2, B["wall_t"]
    fz, bz, by, ry = B["front_z"], B["back_z"], B["bottom_y"], B["rail_y"]
    tr = B["trim"]
    dark = Part("body", "teal_dark")
    for sx in (-1, 1):   # the side walls up to the rails, the floor, the front and the back
        dark.box((sx * (w - t) if sx > 0 else -w, by, bz), (w if sx > 0 else -(w - t), ry[0], fz), MOUNT)
    dark.box((-(w - t), by, bz), (w - t, -T["field_thick"] - 0.5, fz), MOUNT)          # the floor under the board
    dark.box((-(w - t), -T["field_thick"] - 0.5, K["field"][1] / 2), (w - t, ry[0], fz), MOUNT)   # the front block
    dark.box((-(w - t), -T["field_thick"] - 0.5, bz), (w - t, ry[0], -K["field"][1] / 2 - 1.0), MOUNT)  # the back
    copper = Part("trims", "copper", bevel=0.3, segs=3)
    for sx in (-1, 1):   # the top rails over the contract's walls, holding the glass
        a, b = sorted((sx * B["rail_in"], sx * B["rail_out"]))
        copper.box((a, ry[0], bz), (b, ry[1], fz + 0.6), MOUNT)
        xb = sorted((sx * (w - 1.0), sx * (w + 0.3)))   # the trim along the side's bottom edge
        copper.box((xb[0], by - 0.3, bz), (xb[1], by + tr, fz + 0.3), MOUNT)
        for z in (fz, bz):        # the vertical corner trims
            zz = (z - tr, z + 0.3) if z == fz else (z - 0.3, z + tr)
            xx = sorted((sx * (w + 0.3), sx * (w - tr)))
            copper.box((xx[0], by, zz[0]), (xx[1], ry[0], zz[1]), MOUNT)
    copper.box((-B["rail_out"], ry[0], B["lockdown_z"][0]), (B["rail_out"], ry[1], B["lockdown_z"][1]), MOUNT)
    copper.box((-w - 0.3, by - 0.3, fz - 0.2), (w + 0.3, by + tr, fz + 0.3), MOUNT)   # the front's bottom edge
    light = Part("panels", "teal_light", bevel=0.25)
    yt, yb = ry[0] - 1.0, by + tr + 1.0
    xt, xb, cw = w - 2 * w * F["v_top"], w - 2 * w * F["v_bottom"], F["v_strip"]
    # the front (the concept's V): the lighter trapezoid between two copper diagonals that run from the outer top to
    # the inner bottom, a dark plate round the medallion on it, the dark body outside
    light.prism([(-xb, yb, fz), (-xt, yt, fz), (xt, yt, fz), (xb, yb, fz)], (0, 0, 0.4), MOUNT)
    pr = F["medallion_r"][0] + F["plate"]
    dark.box((-pr, F["medallion_y"] - pr, fz), (pr, F["medallion_y"] + pr, fz + 0.7), MOUNT)
    for sx in (-1, 1):
        copper.prism([(sx * xt, yt, fz), (sx * (xt + cw), yt, fz), (sx * (xb + cw), yb, fz), (sx * xb, yb, fz)],
                     (0, 0, 0.6), MOUNT)
        # the side walls: the lighter band under the rail over the side art, the copper diagonal at its front edge
        xs = sx * w
        light.prism([(xs, yt - 4.5, fz - 50.0), (xs, yt, fz - 46.0), (xs, yt, bz + 1.0), (xs, yt - 4.5, bz + 1.0)],
                    (sx * 0.4, 0, 0), MOUNT)
        copper.prism([(xs, yt, fz - 46.0), (xs, yt, fz - 50.0), (xs, yb, fz - 4.0), (xs, yb, fz - 1.0)],
                     (sx * 0.6, 0, 0), MOUNT)
    a0, a1 = yb + 1.5, yt - 6.0     # the side art: the night Earth (pinball_art.SIDE), u from the front end
    inv = MOUNT.inverted()

    def side_uv(co):
        t = inv @ co
        return ((fz - 52.0 - t.z / CM) / (fz - 52.0 - bz - 30.0), (t.y / CM - a0) / (a1 - a0))
    art = Part("side_art", "side_art", bevel=0.2, uv=side_uv)
    for sx in (-1, 1):
        xs = sx * w
        art.prism([(xs, a0, fz - 56.0), (xs, a1, fz - 51.0), (xs, a1, bz + 30.0), (xs, a0, bz + 30.0)],
                  (sx * 0.3, 0, 0), MOUNT)
        f0, f1 = sorted((xs, xs + sx * 0.7))       # its copper frame: the top, the bottom and the back end
        copper.box((f0, a1 - 0.2, bz + 29.0), (f1, a1 + 0.9, fz - 50.5), MOUNT)
        copper.box((f0, a0 - 0.9, bz + 29.0), (f1, a0 + 0.2, fz - 55.0), MOUNT)
        copper.box((f0, a0 - 0.9, bz + 29.0), (f1, a1 + 0.9, bz + 30.2), MOUNT)
        for zc in (fz, bz):                       # the copper corner caps over the rails' ends
            c0, c1 = sorted((sx * (w - F["cap"]), sx * (w + 0.5)))
            z0, z1 = (zc - F["cap"], zc + 0.8) if zc == fz else (zc - 0.8, zc + F["cap"])
            copper.box((c0, ry[0] - F["cap"], z0), (c1, ry[1] + 0.4, z1), MOUNT)
    return [dark, copper, light, art]


def front_parts() -> list:
    """The front medallion and the side buttons (the concept's cyan rings), rivets on the front's corners."""
    fz = B["front_z"]
    r = F["medallion_r"]
    cop, cy = Part("medallion", "copper", 0.2, segs=3), Part("rings", "cyan", 0.1)
    dome = Part("domes", "lens", 0.0)
    y = F["medallion_y"]
    cop.cyl((0, y, fz + 0.8), "z", r[0], 1.6, 40, frame=MOUNT)
    cy.cyl((0, y, fz + 1.9), "z", r[1], 0.6, 40, frame=MOUNT)
    cop.cyl((0, y, fz + 2.2), "z", r[2], 0.8, 40, frame=MOUNT)
    dome.cyl((0, y, fz + 2.4), "z", r[3], 2.2, 32, r2=r[3] * 0.55, frame=MOUNT)
    w = B["outer_w"] / 2
    br = F["button_r"]
    for sx in (-1, 1):   # a cone's radius2 lies at +x: the domes narrow outward on both sides
        cop.cyl((sx * (w + F["button_len"] / 2), F["button_y"], F["button_z"]), "x", br[0], F["button_len"], 28,
                frame=MOUNT)
        cy.cyl((sx * (w + F["button_len"] + 0.15), F["button_y"], F["button_z"]), "x", br[1], 0.3, 28, frame=MOUNT)
        ra, rb = (br[2], br[2] * 0.6) if sx > 0 else (br[2] * 0.6, br[2])
        dome.cyl((sx * (w + F["button_len"] + 0.6), F["button_y"], F["button_z"]), "x", ra, 0.9, 24, r2=rb,
                 frame=MOUNT)
    riv = Part("rivets", "copper", 0.0, features=False)
    rr, pitch = F["rivet_r"], F["rivet_pitch"]
    yt, yb = B["rail_y"][0] - 3.0, B["bottom_y"] + 3.6
    run = B["front_z"] - B["back_z"] - 12.0
    n = int(run // pitch)
    for sx in (-1, 1):   # rows of rivets: the front's outer corners, the side walls under the rails and at the bottom
        for yy in (yt, yb):
            for dx in (3.2, 9.0):
                riv.rivet((sx * (w - dx), yy, fz), (0, 0, 1), rr, MOUNT)
        for i in range(n + 1):
            z = B["front_z"] - 6.0 - i * run / n
            for yy, out in ((B["rail_y"][0] - 2.4, 0.4), (B["bottom_y"] + 1.8, 0.0)):   # on the band, on the body
                riv.rivet((sx * (w + out), yy, z), (sx, 0, 0), rr, MOUNT)
    return [cop, cy, dome, riv]


def leg_parts() -> list:
    w = B["outer_w"] / 2
    steel, cop = Part("legs", "teal_light", 0.5), Part("leg_collars", "copper", 0.3, segs=3)
    cy = Part("leg_rings", "cyan", 0.1)
    for sx in (-1, 1):
        for zt in (B["front_z"] - L["inset"][1], B["back_z"] + L["inset"][1]):
            top = tf((sx * (w - L["inset"][0]), B["bottom_y"] + 3.0, zt)) / CM   # 3 cm up inside the body
            front = zt > 0
            ox = -sx * L["splay"]                 # MOUNT mirrors x: table +x is the cabinet's -x
            oz = -L["splay"] if front else L["splay"]
            foot_y = L["foot_r"][1] + L["ring_h"] + L["collar_h"]
            bot = Vector((top.x + ox, foot_y, top.z + oz))
            ht, hb = L["top"] / 2, L["waist"] / 2
            pts = []
            for (c, h) in ((top, ht), (bot, hb)):
                for dx, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    pts.append(v3((c.x + dx * h, c.y, c.z + dz * h)))
            steel.hull(pts)
            y0 = L["foot_r"][1] + L["ring_h"]
            cr = L["collar_r"]   # the round collar, a second cyan ring in its middle (the concept: two per foot)
            ch = (foot_y + 0.5 - y0 - L["ring2_h"]) / 2
            cop.cyl((bot.x, y0 + ch / 2, bot.z), "y", cr, ch, 40)
            cop.cyl((bot.x, foot_y + 0.5 - ch / 2, bot.z), "y", cr, ch, 40)
            cy.cyl((bot.x, y0 + ch + L["ring2_h"] / 2, bot.z), "y", cr + 0.15, L["ring2_h"], 40)
            cy.cyl((bot.x, L["foot_r"][1] + L["ring_h"] / 2, bot.z), "y", L["ring_r"], L["ring_h"], 40)
            c, lx = L["cap"], sx * (w - L["inset"][0])     # the copper cap where the leg meets the body
            cop.box((lx - ht - c, B["bottom_y"] - c, zt - ht - c), (lx + ht + c, B["bottom_y"] + 0.4, zt + ht + c),
                    MOUNT)
            cop.cyl((bot.x, L["foot_r"][1] / 2, bot.z), "y", L["foot_r"][0], L["foot_r"][1], 32,
                    r2=L["foot_r"][0] * 0.88)
    return [steel, cop, cy]


def backbox_parts() -> list:
    w = BB["w"] / 2
    z0, z1 = BB["z"]
    y0, y1 = BB["y"]
    cap = BB["cap_h"]
    dark = Part("backbox", "teal_dark", 0.8).box((-w, y0, z0), (w, y1 - cap, z1))
    cop = Part("backbox_trims", "copper", 0.4, segs=3)
    cop.box((-w - 0.4, y1 - cap, z0 - 0.4), (w + 0.4, y1, z1 + 0.4))         # the cap
    for sx in (-1, 1):   # the copper edges of the side faces, front and back
        xe = sorted((sx * (w + 0.3), sx * (w - 1.5)))
        for ze in ((z0 - 0.3, z0 + 1.5), (z1 - 1.5, z1 + 0.3)):
            cop.box((xe[0], y0, ze[0]), (xe[1], y1 - cap, ze[1]))
    sw, sh = BB["screen"]
    sy = BB["screen_y"]
    line_gap, line_w = BB["frame_line"]
    scr = Part("screen", "screen", 0.2).box((-sw / 2, sy - sh / 2, z0 - 0.6), (sw / 2, sy + sh / 2, z0 + 0.2))
    bez = Part("bezel", "teal_light", 0.3)
    m = line_gap + line_w + 1.5          # the lighter bezel round the screen and the line
    bez.box((-sw / 2 - m, sy - sh / 2 - m, z0 - 0.35), (sw / 2 + m, sy + sh / 2 + m, z0 + 0.2))
    cy = Part("screen_line", "cyan", 0.0)
    a, b = sw / 2 + line_gap, sh / 2 + line_gap
    cy.box((-a - line_w, sy + b, z0 - 0.75), (a + line_w, sy + b + line_w, z0 - 0.3))
    cy.box((-a - line_w, sy - b - line_w, z0 - 0.75), (a + line_w, sy - b, z0 - 0.3))
    cy.box((-a - line_w, sy - b, z0 - 0.75), (-a, sy + b, z0 - 0.3))
    cy.box((a, sy - b, z0 - 0.75), (a + line_w, sy + b, z0 - 0.3))
    r = BB["medallion_r"]
    my = BB["medallion_y"]
    cop.cyl((0, my, z0 - 0.6), "z", r[0], 1.2, 32)
    cy.cyl((0, my, z0 - 1.35), "z", r[1], 0.4, 32)
    dome = Part("backbox_dome", "lens", 0.0).cyl((0, my, z0 - 1.6), "z", r[2], 1.6, 24, r2=r[2] * 0.5)
    for sx in (-1, 1):   # the copper wings either side of the medallion (the concept's chevrons)
        cop.prism([(sx * (r[0] + 1.5), my - 1.0, z0), (sx * (r[0] + 22.0), my + 4.0, z0), (sx * (r[0] + 22.0), my + 5.5, z0),
                   (sx * (r[0] + 1.5), my + 1.5, z0)], (0, 0, -0.5))
    riv = Part("backbox_rivets", "copper", 0.0, features=False)
    for sx in (-1, 1):   # rows up the backbox's front corners and along its side faces' front edges
        for i in range(7):
            yy = y0 + 4.0 + i * (y1 - cap - 7.5 - y0) / 6
            riv.rivet((sx * (w - 3.0), yy, z0), (0, 0, -1), F["rivet_r"])
            riv.rivet((sx * w, yy, z0 + 3.2), (sx, 0, 0), F["rivet_r"])
    return [dark, cop, scr, bez, cy, dome, riv]


def markers() -> dict:
    """The game's markers in the cabinet frame (Godot matrices)."""
    a = math.radians(MK["closeup_down_deg"])
    d = MK["closeup_dist"] * CM
    cam_z = Vector((0.0, math.sin(a), -math.cos(a)))           # the camera looks along -z: down and toward +z
    cam_x = Vector((-1.0, 0.0, 0.0))
    cam_y = cam_z.cross(cam_x)
    pos = Vector((0.0, H_C, Z_C)) + cam_z * d
    closeup = Matrix((( *cam_x, 0), (*cam_y, 0), (*cam_z, 0), (0, 0, 0, 1))).transposed()
    closeup.translation = pos
    yaw180 = Matrix(((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1)))
    display = yaw180.copy()
    display.translation = Vector((0.0, BB["screen_y"] * CM, (BB["z"][0] - 0.6 - MK["display_ahead"]) * CM))
    return {"TableMount": MOUNT.copy(), "CloseUp": closeup, "Display": display}


def empty(name: str, m: Matrix) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.05
    bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = G2B @ m @ G2B.inverted()
    return ob


def join(objs: list, name: str) -> bpy.types.Object:
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]):
        bpy.ops.object.join()
    ob = objs[0]
    ob.name = name
    ob.data.name = name
    return ob


# --- the table's art (the contract's frame) ------------------------------------------------------------------------
def node_matrix(x: float, z: float, yaw_deg: float = 0.0, y: float | None = None) -> Matrix:
    m = Matrix.Rotation(math.radians(yaw_deg), 4, "Y")
    m.translation = v3((x, K["body_y"] if y is None else y, z))
    return m


def table_nodes() -> list:
    """[(node name, its Godot matrix in the table frame, [parts in the node's own frame])]."""
    by = K["body_y"]
    nodes = []
    sw, st = K["wall_side"], K["wall_top"]
    for name, sx in (("WallLeft", -1), ("WallRight", 1)):
        nodes.append((name, node_matrix(sx * K["wall_side_x"], 0.0), [
            Part(name, "teal_dark", 0.4).box((-sw[0] / 2, -sw[1] / 2, -sw[2] / 2), (sw[0] / 2, sw[1] / 2 - 1.2, sw[2] / 2)),
            Part(name + "_cap", "copper", 0.3).box((-sw[0] / 2, sw[1] / 2 - 1.2, -sw[2] / 2), (sw[0] / 2, sw[1] / 2, sw[2] / 2))]))
    nodes.append(("WallTop", node_matrix(0.0, K["wall_top_z"]), [
        Part("WallTop", "teal_dark", 0.4).box((-st[0] / 2, -st[1] / 2, -st[2] / 2), (st[0] / 2, st[1] / 2 - 1.2, st[2] / 2)),
        Part("WallTop_cap", "copper", 0.3).box((-st[0] / 2, st[1] / 2 - 1.2, -st[2] / 2), (st[0] / 2, st[1] / 2, st[2] / 2))]))
    il = K["inlane"]
    for name, sx in (("InlaneLeft", -1), ("InlaneRight", 1)):
        nodes.append((name, node_matrix(sx * K["inlane_at"][0], K["inlane_at"][1], sx * K["inlane_yaw"]), [
            Part(name, "copper", 0.3).box((-il[0] / 2, -by, -il[2] / 2), (il[0] / 2, il[1] / 2 - 2.0, il[2] / 2)),
            Part(name + "_light", "cyan", 0.0).box((-il[0] / 2 + 1.0, il[1] / 2 - 2.0, -0.4), (il[0] / 2 - 1.0, il[1] / 2 - 1.4, 0.4))]))
    fl = K["flipper"]
    for name, sx in (("FlipperLeft", -1), ("FlipperRight", 1)):
        length, r0, r1 = fl[0], 1.25, 0.65
        top, bot = fl[1] / 2 - 1.2, -by + 0.4
        pts = []
        for (cx, r) in ((0.0, r0), (-sx * (length - r1), r1)):
            for i in range(16):
                a = 2 * math.pi * i / 16
                for yy in (bot, top):
                    pts.append(v3((cx + r * math.cos(a), yy, r * math.sin(a))))
        lx = sorted((-sx * 1.6, -sx * (length - r1 - 0.2)))   # the inlay: a thin cyan line on top (step 1: a blob)
        pivot = Part(name + "_pivot", "copper", 0.0).cyl((0, top + 0.6, 0), "y", 0.6, 0.8, 16)
        nodes.append((name, node_matrix(sx * K["flipper_at"][0], K["flipper_at"][1], sx * K["flipper_rest_deg"]),
                      [Part(name, "ivory", 0.25).hull(pts), Part(name + "_inlay", "cyan", 0.0).box((lx[0], top - 0.1, -0.2), (lx[1], top + 0.25, 0.2)), pivot]))
    for name, (r, _h), at in (("Bumper", K["bumper"], K["bumper_at"]), ("Kicker", K["kicker"], K["kicker_at"])):
        parts = [Part(name, "copper", 0.2).cyl((0, -by + 0.75, 0), "y", r, 1.5, 32)
                 .cyl((0, 4.7, 0), "y", r * 0.92, 1.4, 32),
                 Part(name + "_body", "teal_dark", 0.2).cyl((0, 1.0, 0), "y", r * 0.82, 4.5, 32),
                 Part(name + "_ring", "cyan", 0.0).cyl((0, 3.6, 0), "y", r, 0.9, 32),
                 Part(name + "_dome", "chrome", 0.0).cyl((0, 5.8, 0), "y", r * 0.55, 0.8, 24, r2=r * 0.3)]
        nodes.append((name, node_matrix(at[0], at[1]), parts))
    tg = K["target"]
    nodes.append(("Target", node_matrix(0.0, K["target_z"]), [
        Part("Target", "copper", 0.3).box((-tg[0] / 2, -by, -tg[2] / 2), (tg[0] / 2, tg[1] / 2 - 2.0, tg[2] / 2)),
        Part("Target_face", "cyan", 0.0).box((-tg[0] / 2 + 1.2, -by + 1.5, tg[2] / 2), (tg[0] / 2 - 1.2, tg[1] / 2 - 3.2, tg[2] / 2 + 0.4))]))
    fw, fl_ = K["field"]
    zt = K["wall_top_z"] - K["wall_top"][2] / 2
    nodes.append(("Playfield", IDENT.copy(), [
        Part("Playfield", "field", 0.2, uv=lambda co: ((co.x / CM + fw / 2) / fw, (fl_ / 2 - co.z / CM) / (fl_ / 2 - zt)))
        .box((-fw / 2, -T["field_thick"], zt), (fw / 2, T["art_inset"], fl_ / 2))]))
    nodes.append(("Glass", IDENT.copy(), [
        Part("Glass", "glass", 0.0, features=False).box((-fw / 2, T["glass_y"] - T["glass_thick"], zt),
                                                        (fw / 2, T["glass_y"], fl_ / 2))]))
    return nodes


def build_table() -> tuple[list, dict]:
    objs, info = [], {}
    for name, m, parts in table_nodes():
        for p in parts:
            p.frame = MOUNT @ m      # the features are drawn in the cabinet frame
        built = [p.obj() for p in parts]
        ob = join(built, name) if len(built) > 1 else built[0]
        ob.name = ob.data.name = name
        ob.matrix_world = G2B @ m @ G2B.inverted()
        objs.append(ob)
        info[name] = {"at_cm": [round(c / CM, 2) for c in m.translation],
                      "yaw_deg": round(math.degrees(m.to_euler("XYZ").y), 2), "triangles": tris(ob)}
    bs = node_matrix(K["ball_start"][0], K["ball_start"][1], -10.0)
    objs.append(empty("BallStart", bs))
    objs.append(empty("Drain", node_matrix(0.0, K["drain_z"])))
    return objs, info


def tris(ob) -> int:
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def bounds(objs: list) -> dict:
    """The objects' bounds in Godot axes (cm)."""
    pts = []
    for ob in objs:
        if ob.type == "MESH":
            inv = G2B.inverted()
            pts += [inv @ (ob.matrix_world @ v.co) for v in ob.data.vertices]
    lo = [min(p[i] for p in pts) / CM for i in range(3)]
    hi = [max(p[i] for p in pts) / CM for i in range(3)]
    return {"min": [round(x, 2) for x in lo], "max": [round(x, 2) for x in hi]}


def export(objs: list, path: Path) -> None:
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_vertex_color="NONE", export_extras=False,
                              export_cameras=False, export_lights=False)


def ortho(folder: Path, px: int, hide: list) -> list:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_cavity = True
    sc.render.film_transparent = True
    for o in hide:
        o.hide_render = True
    cam = bpy.data.cameras.new("ortho")
    cam.type = "ORTHO"
    co = bpy.data.objects.new("ortho", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    files = []
    for view, (w, h, ch, cv) in ORTHO.items():
        sc.render.resolution_x, sc.render.resolution_y = int(w * px), int(h * px)
        cam.ortho_scale = max(w, h) * CM
        cam.clip_end = 20.0
        if view == "front":   # from the player's side (Blender +y), image right = cabinet -x
            co.location, co.rotation_euler = (-ch * CM, 5.0, cv * CM), (math.radians(90), 0, math.radians(180))
        elif view == "side":  # from +x, image right = cabinet -z (Blender +y)
            co.location, co.rotation_euler = (5.0, ch * CM, cv * CM), (math.radians(90), 0, math.radians(90))
        else:                 # from above, image up = cabinet +z (Blender -y), right = cabinet -x
            co.location, co.rotation_euler = (-ch * CM, -cv * CM, 5.0), (0, 0, math.radians(180))
        path = folder / f"ortho_{view}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files.append(path.name)
    return files


def main() -> None:
    args = argv()
    out = Path(args["out"])
    (out / "renders").mkdir(parents=True, exist_ok=True)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    TEXDIR.append(out / "tex")      # Gate 3's art: the night Earth and the roughness break-up (pinball_art.py)
    tex = pinball_art.make(TEXDIR[0], Path(args["earth"]),
                           {f: (MATS[m][2], amp) for m, (f, amp) in ROUGH.items()})
    parts = body_parts() + front_parts() + leg_parts() + backbox_parts()
    tri_parts = {}
    built = []
    for p in parts:
        ob = p.obj()
        tri_parts[p.name] = tris(ob)
        built.append(ob)
    cab = join(built, "pinball")
    mk = {name: empty(name, m) for name, m in markers().items()}
    export([cab, *mk.values()], out / "pinball.glb")
    table, info = build_table()
    export(table, out / "pinball_table.glb")
    cab_b = bounds([cab])
    tab_b = bounds([o for o in table if o.name not in ("Glass",)])
    # the measured numbers (the handoff's spec vs build table)
    field = next(o for o in table if o.name == "Playfield")
    fb = bounds([field])
    mats = {}
    for p in cab.data.polygons:
        n = cab.data.materials[p.material_index].name
        mats[n] = mats.get(n, 0) + len(p.vertices) - 2
    front_edge = MOUNT @ Vector((0, 0, K["field"][1] / 2 * CM))
    far_edge = MOUNT @ Vector((0, 0, -K["field"][1] / 2 * CM))
    mk_out = {n: {"at_cm": [round(c / CM, 2) for c in m.translation],
                  "basis_rows": [[round(m[r][c], 4) for c in range(3)] for r in range(3)]} for n, m in markers().items()}
    report = {
        "cabinet": {"triangles": tris(cab), "triangles_by_part": tri_parts, "triangles_by_material": mats,
                    "bounds_cm": cab_b},
        "table": {"nodes": info, "triangles": sum(i["triangles"] for i in info.values()), "bounds_cm": tab_b,
                  "playfield_cm": [round(fb["max"][0] - fb["min"][0], 2), round(fb["max"][2] - fb["min"][2], 2)]},
        "measured": {"field_front_y_cm": round(front_edge.y / CM, 2), "field_far_y_cm": round(far_edge.y / CM, 2),
                     "tilt_deg": round(math.degrees(math.atan2(far_edge.y - front_edge.y, far_edge.z - front_edge.z)), 3),
                     "top_y_cm": cab_b["max"][1], "width_cm": round(cab_b["max"][0] - cab_b["min"][0], 2),
                     "depth_cm": round(cab_b["max"][2] - cab_b["min"][2], 2),
                     "screen_cm": BB["screen"], "front_z_cm": cab_b["min"][2]},
        "markers": mk_out,
        "ortho": {k: list(v) for k, v in ORTHO.items()},
        "px_per_cm": int(args["px"]),
        "textures": tex,
    }
    (out / "features.json").write_text(json.dumps(FEATURES), encoding="utf-8")
    report["features"] = len(FEATURES)
    glass = [o for o in table if o.name == "Glass"]
    mount = G2B @ MOUNT @ G2B.inverted()   # after the export: the table in its place for the renders and the .blend
    for o in table:
        o.matrix_world = mount @ o.matrix_world
    report["renders"] = ortho(out / "renders", int(args["px"]), glass)
    (out / "build.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "pinball.blend"))
    print(f"PINBALL_BUILD cabinet {tris(cab)} tris {cab_b}; table {report['table']['triangles']} tris; "
          f"measured {report['measured']}")


if __name__ == "__main__":
    main()
