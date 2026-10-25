"""The ship's breaker board, the shells (art#263's stations; the engineer picked variant 3 on 2026-10-25): an octagonal
bronze board on a corridor's front wall with four bays, in each a crystal core behind a coloured enamel shell on a
bottom hinge, a lamp over each bay, the red problem beacon on top, cyan strips and two cable loops into the wall;
built from code in headless Blender from its drawing (board_dims.toml). The driver (board_run.py) calls it; by hand,
background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/board_build.py -- \
      --out <dir> [--views <dir with front-ortho.jpg, side-ortho.jpg>] [--res 1024]

Blender axes: Z up, x = u, the board's front (out of the wall) -Y (glTF: Y up, front +Z); the origin on the wall's
face at the floor under the centre line.

Objects (the GLB's nodes, the game drives them by name):
- `board_body`: the wall plate, the raised border and the inner panel in bronze blocks with dark joints, the four
  bays' surrounds, pockets, strips' carriers and fixed hinge knuckles, the lamps' rings, the beacon's collar, the
  core holders, the cyan strips and the cable loops with their couplings and clamps; colliders `board_col<k>`;
- `shell_<colour>` x4 (red, yellow, green, blue, left to right): the leaf, its origin on its hinge axis; its local
  rotation about X is the trip: 0 closed, +110 degrees tripped (the top falls forward and down); its convex collider
  `shell_<colour>_col` is its child;
- `core_<colour>` x4: the fixed crystal cores (material board_core, the game sets each one's glow);
- `lamp_<colour>` x4: the lamps' lenses (board_lamp); `beacon`: the red dome (board_beacon).
Every mesh has UV0: u = 1 on the blocks' chamfer faces (the metal's bright worn edges), v the face's random value.

Writes into --out: breaker_board.glb, breaker_board.blend, build.json (triangles, sizes, the measured numbers the
drawing checks, the shells' sweep check: intersections with the body, the cores, the lamps and their neighbours at
every tenth of the trip). With --views: drawing_front.png and drawing_side.png, the model as ink and outlines over
the picked sheet's straight views at the drawing's scale (yellow and green tripped, as in the views).
"""

import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

DIMS = tomllib.loads((Path(__file__).with_name("board_dims.toml")).read_text(encoding="utf-8"))
CM = 0.01
FR, BAY, SH, HG, CO, LA, BE, ST, CA = (DIMS[k] for k in ("frame", "bays", "shell", "hinge", "core", "lamp", "beacon",
                                                          "strips", "cables"))
COLOURS = BAY["colours"]
CHAMFER_BLOCK, CHAMFER_SMALL = 0.5, 0.2      # cm
SQ = 2.0 - math.sqrt(2.0)


def argv() -> dict:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"out": None, "views": None, "res": 1024}
    for i in range(0, len(args), 2):
        out[args[i].lstrip("-")] = args[i + 1]
    out["res"] = int(out["res"])
    return out


def P(u: float, d: float, h: float) -> Vector:
    return Vector((u * CM, -d * CM, h * CM))


# --- 2D outlines in the face's plane (u, h) -------------------------------------------------------------------------
def octagon(uc: float, h0: float, h1: float, w: float, c: float) -> list:
    W = w / 2.0
    return [(uc - W + c, h0), (uc + W - c, h0), (uc + W, h0 + c), (uc + W, h1 - c), (uc + W - c, h1),
            (uc - W + c, h1), (uc - W, h1 - c), (uc - W, h0 + c)]


def inset(uc: float, h0: float, h1: float, w: float, c: float, t: float) -> list:
    """The octagon moved in by t on every side (its corner cut shrinks by t(2 - sqrt 2))."""
    return octagon(uc, h0 + t, h1 - t, w - 2 * t, c - t * SQ)


def clip(poly: list, axis: int, value: float, keep_less: bool) -> list:
    out = []
    n = len(poly)
    inside = (lambda p: p[axis] <= value + 1e-9) if keep_less else (lambda p: p[axis] >= value - 1e-9)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if inside(a):
            out.append(a)
        if inside(a) != inside(b):
            t = (value - a[axis]) / (b[axis] - a[axis])
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    res = []
    for p in out:
        if not res or abs(p[0] - res[-1][0]) > 1e-6 or abs(p[1] - res[-1][1]) > 1e-6:
            res.append(p)
    if len(res) > 1 and abs(res[0][0] - res[-1][0]) < 1e-6 and abs(res[0][1] - res[-1][1]) < 1e-6:
        res.pop()
    return res


def cut(poly: list, u0=None, u1=None, h0=None, h1=None) -> list:
    for axis, v, less in ((0, u0, False), (0, u1, True), (1, h0, False), (1, h1, True)):
        if v is not None and len(poly) >= 3:
            poly = clip(poly, axis, v, less)
    return poly if len(poly) >= 3 else []


def split_u(poly: list, seams: list, gap: float) -> list:
    """The polygon cut into blocks at each seam's u, a gap wide."""
    pieces, rest = [], poly
    for x in sorted(seams):
        left = cut(rest, u1=x - gap / 2)
        if left:
            pieces.append(left)
        rest = cut(rest, u0=x + gap / 2)
        if not rest:
            break
    if rest:
        pieces.append(rest)
    return pieces


# --- bmesh solids (centimetres in, metres out) -----------------------------------------------------------------------
def prism(bm, poly: list, d0: float, d1: float, mi: int = 0) -> None:
    if len(poly) < 3:
        return
    back = [bm.verts.new(P(u, d0, h)) for u, h in poly]
    front = [bm.verts.new(P(u, d1, h)) for u, h in poly]
    faces = [bm.faces.new(front), bm.faces.new(list(reversed(back)))]
    for i in range(len(poly)):
        j = (i + 1) % len(poly)
        faces.append(bm.faces.new((back[i], back[j], front[j], front[i])))
    for f in faces:
        f.material_index = mi


def box(bm, u0, u1, h0, h1, d0, d1, mi: int = 0) -> None:
    prism(bm, [(u0, h0), (u1, h0), (u1, h1), (u0, h1)], d0, d1, mi)


def ring_verts(bm, centre: Vector, axis: Vector, radius, sides: int, phase: float = 0.0, ref=None) -> list:
    """A loop of verts round axis (radius a number or a function of the angle); centre in cm. ref: a fixed side
    vector (a tube's rings must share one, or they twist where the default one flips)."""
    axis = axis.normalized()
    if ref is None:
        ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    a = axis.cross(ref).normalized()
    b = axis.cross(a).normalized()
    out = []
    for k in range(sides):
        t = phase + 2 * math.pi * k / sides
        r = radius(t) if callable(radius) else radius
        p = centre + (a * math.cos(t) + b * math.sin(t)) * r
        out.append(bm.verts.new(p * CM))
    return out


def bridge(bm, a: list, b: list, mi: int = 0, smooth: bool = False) -> None:
    n = len(a)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((a[i], a[j], b[j], b[i]))
        f.material_index = mi
        f.smooth = smooth


def cap(bm, loop: list, mi: int = 0) -> None:
    f = bm.faces.new(loop)
    f.material_index = mi


def cyl(bm, p0: Vector, p1: Vector, r: float, sides: int = 20, mi: int = 0) -> None:
    """A capped cylinder from p0 to p1 (cm vectors in u, d, h order; converted by C)."""
    a0, a1 = C(p0), C(p1)
    axis = a1 - a0
    l0 = ring_verts(bm, a0, axis, r, sides)
    l1 = ring_verts(bm, a1, axis, r, sides)
    bridge(bm, l0, l1, mi, smooth=True)
    cap(bm, list(reversed(l0)), mi)
    cap(bm, l1, mi)


def C(p) -> Vector:
    """(u, d, h) in cm -> Blender's axes in cm."""
    return Vector((p[0], -p[1], p[2]))


def sweep(bm, pts: list, r: float, sides: int = 10, mi: int = 0) -> None:
    """A tube along a polyline of (u, d, h) cm points, capped."""
    pts = [C(p) for p in pts]
    loops = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        loops.append(ring_verts(bm, p, t, r, sides, ref=Vector((0, 1, 0))))  # the loops lie in a plane of constant d
    for i in range(len(loops) - 1):
        bridge(bm, loops[i], loops[i + 1], mi, smooth=True)
    cap(bm, list(reversed(loops[0])), mi)
    cap(bm, loops[-1], mi)


# --- the parts -------------------------------------------------------------------------------------------------------
W2 = FR["width"] / 2.0
OUTER = octagon(0.0, FR["h0"], FR["h1"], FR["width"], FR["chamfer"])
BS, BB, BT = FR["border"]
IN_H0, IN_H1, IN_U = FR["h0"] + BB, FR["h1"] - BT, W2 - BS
INNER = octagon(0.0, IN_H0, IN_H1, 2 * IN_U, FR["inner_chamfer"])
SEAM = FR["seam"]
OP_W2 = BAY["opening"]["w"] / 2.0


def build_plate(bm) -> None:
    prism(bm, OUTER, 0.0, FR["plate_d"])


def build_border(bm) -> None:
    d0, d1, g = FR["plate_d"], FR["border_d"], SEAM / 2
    nh, nu = FR["notch"]["h"], FR["notch"]["half"]
    pieces = [cut(OUTER, u1=-47.5 - g, h1=IN_H0), cut(OUTER, u0=-47.5 + g, u1=47.5 - g, h1=IN_H0),
              cut(OUTER, u0=47.5 + g, h1=IN_H0),
              cut(OUTER, u1=-IN_U, h0=IN_H0 + SEAM, h1=IN_H1 - SEAM), cut(OUTER, u0=IN_U, h0=IN_H0 + SEAM, h1=IN_H1 - SEAM),
              cut(OUTER, u1=-47.5 - g, h0=IN_H1), cut(OUTER, u0=47.5 + g, h0=IN_H1),
              cut(OUTER, u0=-47.5 + g, u1=-nu, h0=IN_H1), cut(OUTER, u0=nu, u1=47.5 - g, h0=IN_H1),
              cut(OUTER, u0=-nu, u1=nu, h0=IN_H1, h1=nh)]
    c = FR["inner_chamfer"]
    for su in (-1, 1):  # the inner panel's cut corners: the border fills them
        for h, sh in ((IN_H0, 1), (IN_H1, -1)):
            pieces.append([(su * IN_U, h), (su * (IN_U - c), h), (su * IN_U, h + sh * c)])
    for p in pieces:
        prism(bm, p, d0, d1)


def pockets() -> list:
    return [(c - OP_W2, c + OP_W2) for c in BAY["u"]]


def build_slab(bm) -> None:
    prism(bm, INNER, FR["plate_d"], BAY["socket_d"])


def build_panel(bm) -> None:
    d0, d1 = BAY["socket_d"], FR["body_d"]
    p0, p1 = BAY["pocket_h0"], BAY["opening"]["h1"]
    seams = [-33.6, 0.0, 33.6]
    pieces = [cut(INNER, h1=p0), cut(INNER, h0=p1)]
    edges = [-IN_U - 1] + [x for a, b in pockets() for x in (a, b)] + [IN_U + 1]
    for i in range(0, len(edges), 2):
        pieces.append(cut(INNER, u0=edges[i], u1=edges[i + 1], h0=p0, h1=p1))
    for p in pieces:
        for q in split_u(p, seams, SEAM):
            prism(bm, q, d0, d1)


def build_liners(bm) -> None:
    d0, d1 = BAY["socket_d"], FR["body_d"]
    p0, p1 = BAY["pocket_h0"], BAY["opening"]["h1"]
    s = BAY["strip"]
    for c in BAY["u"]:
        box(bm, c - OP_W2, c - OP_W2 + 0.5, p0, p1, d0, d1)
        box(bm, c + OP_W2 - 0.5, c + OP_W2, p0, p1, d0, d1)
        box(bm, c - OP_W2 + 0.5, c + OP_W2 - 0.5, p1 - 0.5, p1, d0, d1)
        for sgn in (-1, 1):  # the strips' carriers
            a, b = sorted((c + sgn * (s["u"][0] - 0.2), c + sgn * (OP_W2 - 0.5)))
            box(bm, a, b, s["h"][0] - 0.5, s["h"][1] + 0.5, d0, s["d"] - 0.2)
        hs = HG["fixed"]
        for sgn in (-1, 1):  # the saddles under the fixed knuckles
            a, b = sorted((c + sgn * hs[0], c + sgn * HG["cap"]["to"]))
            box(bm, a, b, p0, HG["h"], d0, HG["d"])


def build_surrounds(bm) -> None:
    s, o = BAY["surround"], BAY["opening"]
    notch = HG["cap"]["to"] + 0.25
    for c in BAY["u"]:
        out = octagon(c, s["h0"], s["h1"], s["w"], s["chamfer"])
        inn = octagon(c, o["h0"], o["h1"], o["w"], o["chamfer"])
        for i in range(8):
            j = (i + 1) % 8
            quad = [out[i], out[j], inn[j], inn[i]]
            if i == 0:  # the bottom rail: open in the middle, where the hinge sits
                prism(bm, cut(quad, u1=c - notch), FR["body_d"], s["d"])
                prism(bm, cut(quad, u0=c + notch), FR["body_d"], s["d"])
            else:
                prism(bm, quad, FR["body_d"], s["d"])


def build_knuckles(bm) -> None:
    h, d = HG["h"], HG["d"]
    for c in BAY["u"]:
        for sgn in (-1, 1):
            cyl(bm, (c + sgn * HG["fixed"][0], d, h), (c + sgn * HG["fixed"][1], d, h), HG["r"], 24)
            cyl(bm, (c + sgn * HG["fixed"][1], d, h), (c + sgn * HG["cap"]["to"], d, h), HG["cap"]["r"], 24)


def build_holders(bm) -> None:
    d = CO["d"]
    for c in BAY["u"]:
        hd, pn = CO["holder"], CO["pin"]
        cyl(bm, (c, d, CO["h1"] - 0.9), (c, d, hd["top"]), hd["r"], 16)
        cyl(bm, (c, d, hd["collar"][0]), (c, d, hd["collar"][1]), hd["collar_r"], 16)
        cyl(bm, (c, d, BAY["pocket_h0"]), (c, d, CO["h0"] + 1.0), pn["r"], 16)
        cyl(bm, (c, d, pn["collar"][0]), (c, d, pn["collar"][1]), pn["collar_r"], 16)


def build_lamp_rings(bm) -> None:
    for c in BAY["u"]:
        cyl(bm, (c, FR["body_d"] - 0.5, LA["h"]), (c, LA["ring_d"], LA["h"]), LA["ring_r"], 28)


def build_collar(bm) -> None:
    b = BE["collar"]
    cyl(bm, (0, BE["d"], b["h0"]), (0, BE["d"], b["h1"]), b["r"], 32)
    cyl(bm, (0, BE["d"], b["h1"]), (0, BE["d"], b["h2"]), b["r2"], 32)


def strip_rects() -> list:
    t, s, b = ST["top"], ST["side"], ST["bottom"]
    out = []
    for sgn in (-1, 1):
        out.append(sorted((sgn * t["u"][0], sgn * t["u"][1])) + t["h"])
        out.append(sorted((sgn * s["u"][0], sgn * s["u"][1])) + s["h"])
    out.append(b["u"] + b["h"])
    return out


def build_bezels(bm) -> None:
    d = FR["border_d"]
    for u0, u1, h0, h1 in strip_rects():
        box(bm, u0 - 0.6, u1 + 0.6, h0 - 0.6, h1 + 0.6, d - 0.4, d + 0.3)


def build_strips(bm) -> None:
    d = FR["border_d"]
    for u0, u1, h0, h1 in strip_rects():
        box(bm, u0, u1, h0, h1, d - 0.4, d + 0.45)
    s = BAY["strip"]
    for c in BAY["u"]:
        for sgn in (-1, 1):
            a, b = sorted((c + sgn * s["u"][0], c + sgn * s["u"][1]))
            box(bm, a, b, s["h"][0], s["h"][1], s["d"] - 0.5, s["d"])


R_LOOP = CA["outer_half"] - CA["bundle"] / 2.0
CABLE_R = CA["bundle"] / 6.0
HC = CA["low"] + CA["outer_half"]          # the arcs' centre


def build_cables(bm) -> None:
    for m in CA["centre"]:
        for o in (-2 * CABLE_R, 0.0, 2 * CABLE_R):
            rk = R_LOOP + o
            pts = [(m - rk, CA["d"], FR["h0"] + 4.0), (m - rk, CA["d"], HC)]
            for k in range(1, 24):
                a = math.pi + math.pi * k / 24
                pts.append((m + rk * math.cos(a), CA["d"], HC + rk * math.sin(a)))
            pts += [(m + rk, CA["d"], HC), (m + rk, CA["d"], FR["h0"] + 4.0)]
            sweep(bm, pts, CABLE_R * 0.97, 12)


def build_couplings(bm) -> None:
    w = CA["bundle"] / 2 + 0.9
    for m in CA["centre"]:
        for leg in (m - R_LOOP, m + R_LOOP):
            for h0, h1 in CA["couplings"]:
                box(bm, leg - w, leg + w, h0, h1, CA["d"] - CABLE_R - 1.0, CA["d"] + CABLE_R + 1.0)
        k = CA["clamp"]
        box(bm, m - k["w"] / 2, m + k["w"] / 2, k["h0"], k["h1"], k["plate"][3], k["d"])


def build_clamp_plates(bm) -> None:
    for m in CA["centre"]:
        w, h0, h1, d = CA["clamp"]["plate"]
        box(bm, m - w / 2, m + w / 2, h0, h1, 0.0, d)


def build_core(c: float):
    def make(bm) -> None:
        d, half_w, half_d = CO["d"], CO["w"] / 2, CO["depth"] / 2
        ha, hb = CO["h0"] + 3.2, CO["h1"] - 3.2
        hexa = [(half_w * math.cos(k * math.pi / 3), half_d * math.sin(k * math.pi / 3) / math.sin(math.pi / 3))
                for k in range(6)]
        la = [bm.verts.new(P(c + x, d + y, ha)) for x, y in hexa]
        lb = [bm.verts.new(P(c + x * 0.92, d + y * 0.92, hb)) for x, y in hexa]
        bot, top = bm.verts.new(P(c, d, CO["h0"])), bm.verts.new(P(c, d, CO["h1"]))
        for i in range(6):
            j = (i + 1) % 6
            bm.faces.new((la[i], la[j], lb[j], lb[i]))
            bm.faces.new((lb[i], lb[j], top))
            bm.faces.new((la[j], la[i], bot))
    return make


def build_lens(c: float):
    def make(bm) -> None:
        r, h = LA["lens_r"], LA["lens_d"] - (LA["ring_d"] - 0.4)
        R = (r * r + h * h) / (2 * h)
        loops = []
        for k in range(7):
            a = math.asin(r / R) * (1 - k / 7)
            loops.append(ring_verts(bm, C((c, LA["ring_d"] - 0.4 + (R * math.cos(a) - (R - h)), LA["h"])),
                                    Vector((0, -1, 0)), R * math.sin(a), 24))
        for i in range(6):
            bridge(bm, loops[i], loops[i + 1], 0, smooth=True)
        tip = bm.verts.new(P(c, LA["lens_d"], LA["h"]))
        for i in range(24):
            f = bm.faces.new((loops[-1][i], loops[-1][(i + 1) % 24], tip))
            f.smooth = True
        cap(bm, list(reversed(loops[0])))
    return make


def build_dome(bm) -> None:
    dm = BE["dome"]
    rib = lambda s: (lambda t: s * (1.0 + 0.035 * math.cos(dm["ribs"] * 2 * t)))  # noqa: E731
    h_cyl = dm["h0"] + 2.8
    loops = [ring_verts(bm, C((0, BE["d"], dm["h0"] - 0.3)), Vector((0, 0, 1)), rib(dm["r"]), 48),
             ring_verts(bm, C((0, BE["d"], h_cyl)), Vector((0, 0, 1)), rib(dm["r"]), 48)]
    cap_h = dm["top"] - h_cyl
    for k in range(1, 8):
        a = (math.pi / 2) * k / 8
        loops.append(ring_verts(bm, C((0, BE["d"], h_cyl + cap_h * math.sin(a))), Vector((0, 0, 1)),
                                rib(dm["r"] * math.cos(a)), 48))
    for i in range(len(loops) - 1):
        bridge(bm, loops[i], loops[i + 1], 0, smooth=True)
    tip = bm.verts.new(P(0, BE["d"], dm["top"]))
    for i in range(48):
        f = bm.faces.new((loops[-1][i], loops[-1][(i + 1) % 48], tip))
        f.smooth = True
    cap(bm, list(reversed(loops[0])))


def shell_outline(c: float, t: float) -> list:
    h0 = HG["h"] + SH["bottom"]
    return inset(c, h0, HG["h"] + SH["len"], SH["w"], SH["chamfer"], t)


def build_shell(c: float):
    """The leaf: an emerald-cut enamel dome in a bronze rim, hollow behind (a dark ribbed cup), a lug down to its own
    knuckle on the hinge axis. Slots: 0 bronze, 2 graphite, 3 enamel."""
    def make(bm) -> None:
        def loop(t: float, d: float) -> list:
            return [bm.verts.new(P(u, d, h)) for u, h in shell_outline(c, t)]
        l0, l1 = loop(0.0, SH["back_d"]), loop(0.0, SH["edge_d"])
        l2 = loop(SH["rim"], SH["edge_d"] + 0.5)
        tb = SH["table"]  # the table: short, so the face is the drawing's dome (its tripped top stays over h 53.9)
        l3 = [bm.verts.new(P(u, SH["face_d"], h)) for u, h in
              octagon(c, HG["h"] + tb["s"][0], HG["h"] + tb["s"][1], SH["w"] - 2 * tb["inset"],
                      SH["chamfer"] - tb["inset"] * SQ)]
        l4, l5 = loop(SH["rim"], SH["back_d"]), loop(SH["rim"], SH["cup_floor_d"])
        bridge(bm, l0, l1, 3)  # the sides and the back rim in the enamel: a tripped shell reads as the sheet's
        bridge(bm, l1, l2, 0)  # coloured tray round its dark ribs; the bronze is the lip round the facets
        bridge(bm, l2, l3, 3)
        cap(bm, l3, 3)
        bridge(bm, l4, l0, 3)
        bridge(bm, l5, l4, 2)
        cap(bm, list(reversed(l5)), 2)
        half = SH["w"] / 2 - SH["rim"] - 0.05
        for s in SH["ribs"]:
            box(bm, c - half, c + half, HG["h"] + s, HG["h"] + s + 1.0, SH["cup_floor_d"] - 1.2, SH["cup_floor_d"] + 0.05, 2)
        box(bm, c - 5.0, c + 5.0, HG["h"], HG["h"] + SH["bottom"] + 0.7, SH["back_d"] + 0.5, HG["d"] + 2.0, 0)
        cyl(bm, (c - HG["knuckle"], HG["d"], HG["h"]), (c + HG["knuckle"], HG["d"], HG["h"]), HG["r"], 24, 0)
    return make


# --- materials -------------------------------------------------------------------------------------------------------
MATS: dict = {}
CYAN = (0.0, 0.62, 1.0)
ENAMEL = {"red": (0.55, 0.035, 0.025), "yellow": (0.80, 0.52, 0.03), "green": (0.05, 0.30, 0.09),
          "blue": (0.04, 0.10, 0.45)}


def principled(name: str, base, metallic=0.0, rough=0.4, emit=None, strength=0.0, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = strength
    MATS[name] = mat
    return mat


def build_materials() -> None:
    principled("board_bronze", (0.50, 0.30, 0.15), 1.0, 0.32)
    principled("board_graphite", (0.07, 0.072, 0.08), 0.85, 0.4)
    principled("board_cyan", (0.02, 0.05, 0.06), 0.0, 0.2, CYAN, 6.0)
    principled("board_cable", (0.03, 0.03, 0.032), 0.0, 0.45)
    principled("board_core", (0.02, 0.06, 0.1), 0.0, 0.15, (0.0, 0.7, 1.0), 5.0)
    principled("board_lamp", (0.04, 0.2, 0.05), 0.0, 0.15, (0.1, 1.0, 0.2), 4.0)
    principled("board_beacon", (0.4, 0.02, 0.02), 0.0, 0.15, (1.0, 0.05, 0.02), 3.0)
    for c, col in ENAMEL.items():
        principled(f"board_enamel_{c}", col, 0.1, 0.22, coat=0.6)
    principled("_chamfer", (1.0, 0.0, 1.0))


def facet_random(co: Vector) -> float:
    x = math.sin(co.x * 127.1 + co.y * 311.7 + co.z * 74.7) * 43758.5453
    return round(x - math.floor(x), 4)


def make_object(name: str, parts: list, origin: Vector | None = None) -> bpy.types.Object:
    """parts: (builder, material, chamfer cm, extra materials for slots 2..). Applies each part's chamfer (its faces
    marked u = 1 in UV0 and given the part's material; chamfer < 0: a bevel that keeps the faces' own materials and
    no mark), joins the parts into one object with one slot per material name."""
    order: list[str] = []
    bm_all = bmesh.new()
    uv_all = bm_all.loops.layers.uv.new("UVMap")
    deps = None
    for builder, mat, chamfer, *extra in parts:
        extra = extra[0] if extra else []
        bm = bmesh.new()
        builder(bm)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new("tmp")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("tmp", me)
        bpy.context.collection.objects.link(ob)
        slots = [mat, "_chamfer"] + list(extra)
        for s in slots:
            me.materials.append(MATS[s])
        if chamfer != 0:
            mod = ob.modifiers.new("chamfer", "BEVEL")
            mod.width = abs(chamfer) * CM
            mod.segments = 1
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(30.0)
            mod.material = 1 if chamfer > 0 else -1
            mod.harden_normals = False
            mod.use_clamp_overlap = True
        deps = bpy.context.evaluated_depsgraph_get()
        ev = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
        bm = bmesh.new()
        bm.from_mesh(ev)
        for f in bm.faces:
            slot = slots[f.material_index] if f.material_index < len(slots) else mat
            marked = slot == "_chamfer"
            final = mat if marked else slot
            if final not in order:
                order.append(final)
            f.material_index = order.index(final)
            v = facet_random(f.calc_center_median() / CM)
            uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
            for lp in f.loops:
                lp[uv].uv = (1.0 if marked else 0.0, v)
        tmp = bpy.data.meshes.new("tmp2")
        bm.to_mesh(tmp)
        bm.free()
        bm_all.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        bpy.data.meshes.remove(ev)
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    if origin is not None:
        bmesh.ops.translate(bm_all, vec=-origin, verts=bm_all.verts)
    me = bpy.data.meshes.new(name)
    bm_all.to_mesh(me)
    bm_all.free()
    for s in order:
        me.materials.append(MATS[s])
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if origin is not None:
        ob.location = origin
    return ob


def hull_object(name: str, pts: list, parent=None) -> bpy.types.Object:
    """A closed convex hull of the points (Blender metres, in the parent's frame), named for Godot's importer."""
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.delete(bm, geom=list({*res["geom_interior"], *res["geom_unused"]}), context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name + "-convcolonly", me)
    bpy.context.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def box_pts(u0, u1, h0, h1, d0, d1) -> list:
    return [P(u, d, h) for u in (u0, u1) for h in (h0, h1) for d in (d0, d1)]


def build() -> dict:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    build_materials()
    body = make_object("board_body", [
        (build_plate, "board_graphite", CHAMFER_SMALL),
        (build_border, "board_bronze", CHAMFER_BLOCK),
        (build_slab, "board_graphite", CHAMFER_SMALL),
        (build_panel, "board_bronze", CHAMFER_BLOCK),
        (build_liners, "board_graphite", CHAMFER_SMALL),
        (build_surrounds, "board_bronze", CHAMFER_SMALL),
        (build_knuckles, "board_bronze", 0.0),
        (build_holders, "board_bronze", 0.0),
        (build_lamp_rings, "board_bronze", CHAMFER_SMALL),
        (build_collar, "board_bronze", CHAMFER_SMALL),
        (build_bezels, "board_graphite", CHAMFER_SMALL),
        (build_strips, "board_cyan", 0.0),
        (build_cables, "board_cable", 0.0),
        (build_couplings, "board_bronze", CHAMFER_SMALL),
        (build_clamp_plates, "board_graphite", CHAMFER_SMALL),
    ])
    oct_pts = [P(u, d, h) for u, h in OUTER for d in (0.0, BAY["surround"]["d"])]
    hull_object("board_col0", oct_pts, body)
    for k, m in enumerate(CA["centre"]):
        hull_object(f"board_col{k + 1}", box_pts(m - CA["outer_half"], m + CA["outer_half"], CA["low"], FR["h0"],
                                                 0.0, CA["d"] + CABLE_R), body)
    hull_object("board_col3", box_pts(-BE["collar"]["r"], BE["collar"]["r"], BE["collar"]["h0"], BE["dome"]["top"],
                                      BE["d"] - BE["collar"]["r"], BE["d"] + BE["collar"]["r"]), body)
    shells, cores, lamps = [], [], []
    for c, colour in zip(BAY["u"], COLOURS):
        origin = P(c, HG["d"], HG["h"])
        sh = make_object(f"shell_{colour}", [(build_shell(c), "board_bronze", -0.2,
                                              ["board_graphite", f"board_enamel_{colour}"])], origin)
        pts = [Vector(v.co) for v in sh.data.vertices]
        hull_object(f"shell_{colour}_col", pts, sh)
        shells.append(sh)
        cores.append(make_object(f"core_{colour}", [(build_core(c), "board_core", CHAMFER_SMALL / 2)]))
        lamps.append(make_object(f"lamp_{colour}", [(build_lens(c), "board_lamp", 0.0)]))
    beacon = make_object("beacon", [(build_dome, "board_beacon", 0.0)])
    bpy.data.materials.remove(MATS.pop("_chamfer"))
    return {"body": body, "shells": shells, "cores": cores, "lamps": lamps, "beacon": beacon}


# --- checks ----------------------------------------------------------------------------------------------------------
def world_bvh(ob) -> BVHTree:
    mw = ob.matrix_world
    return BVHTree.FromPolygons([mw @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])


def bounds(obs: list) -> tuple:
    co = [o.matrix_world @ v.co for o in obs for v in o.data.vertices]
    lo = [min(c[i] for c in co) / CM for i in range(3)]
    hi = [max(c[i] for c in co) / CM for i in range(3)]
    return lo, hi


def set_trip(sh, t: float) -> None:
    sh.rotation_euler = (math.radians(SH["trip_deg"]) * t, 0.0, 0.0)
    bpy.context.view_layer.update()


def sweep_check(parts: dict) -> dict:
    """Each shell at every tenth of its trip against the body, the cores, the lamps and its neighbours (closed):
    the number of intersecting triangle pairs (0 is clean)."""
    fixed = [parts["body"], parts["beacon"], *parts["cores"], *parts["lamps"]]
    fixed_bvh = {o.name: world_bvh(o) for o in fixed}
    out = {}
    for i, sh in enumerate(parts["shells"]):
        worst = {}
        for k in range(11):
            set_trip(sh, k / 10)
            b = world_bvh(sh)
            for name, other in fixed_bvh.items():
                n = len(b.overlap(other))
                if n:
                    worst[name] = max(worst.get(name, 0), n)
            for j, nb in enumerate(parts["shells"]):
                if j != i:
                    n = len(b.overlap(world_bvh(nb)))
                    if n:
                        worst[nb.name] = max(worst.get(nb.name, 0), n)
        set_trip(sh, 0.0)
        out[sh.name] = worst
    return out


def measure(parts: dict) -> dict:
    """The built numbers (cm, the drawing's axes) the drawing compares with its own."""
    def ud(lo, hi):  # Blender (x, y, z) bounds -> u, d, h ranges
        return {"u": [round(lo[0], 2), round(hi[0], 2)], "d": [round(-hi[1], 2), round(-lo[1], 2)],
                "h": [round(lo[2], 2), round(hi[2], 2)]}
    body = ud(*bounds([parts["body"]]))
    closed = ud(*bounds(parts["shells"] + [parts["body"], parts["beacon"]] + parts["lamps"]))
    for sh in parts["shells"][1:3]:
        set_trip(sh, 1.0)
    tripped = ud(*bounds(parts["shells"][1:2]))
    for sh in parts["shells"]:
        set_trip(sh, 0.0)
    shells = [ud(*bounds([s])) for s in parts["shells"]]
    cores = [ud(*bounds([c])) for c in parts["cores"]]
    lamps = [ud(*bounds([x])) for x in parts["lamps"]]
    cables = [v for v in parts["body"].data.vertices]
    mats = parts["body"].data.materials
    cable_idx = [i for i, m in enumerate(mats) if m.name == "board_cable"][0]
    cable_v = {i for p in parts["body"].data.polygons if p.material_index == cable_idx for i in p.vertices}
    cable_low = min(cables[i].co.z for i in cable_v) / CM
    plate = [v.co / CM for v in cables if -v.co.y / CM <= FR["plate_d"] + 0.01 and v.co.z / CM >= 40.0
             and abs(v.co.x / CM) > 10.0]
    frame = {"u": [round(min(p.x for p in plate), 2), round(max(p.x for p in plate), 2)],
             "h": [round(min(p.z for p in plate), 2), round(max(p.z for p in plate), 2)]}
    return {"body": body, "frame": frame,"all_closed": closed, "shell_tripped": tripped, "shells": shells, "cores": cores,
            "lamps": lamps, "beacon": ud(*bounds([parts["beacon"]])), "cable_low_h": round(cable_low, 2),
            "hinges": [[round(s.location.x / CM, 2), round(-s.location.y / CM, 2), round(s.location.z / CM, 2)]
                       for s in parts["shells"]]}


# --- export ----------------------------------------------------------------------------------------------------------
def export(parts: dict, out: Path) -> dict:
    for o in bpy.context.scene.objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out / "breaker_board.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_vertex_color="NONE", export_extras=False)
    tris, per_object = {}, {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o.name.endswith("-convcolonly"):
            continue
        n = 0
        for p in o.data.polygons:
            name = o.data.materials[p.material_index].name
            tris[name] = tris.get(name, 0) + len(p.vertices) - 2
            n += len(p.vertices) - 2
        per_object[o.name] = n
    cols = {o.name: len(o.data.vertices) for o in bpy.context.scene.objects if o.name.endswith("-convcolonly")}
    lo, hi = bounds([o for o in bpy.context.scene.objects if o.type == "MESH" and not o.name.endswith("-convcolonly")])
    return {"triangles": sum(tris.values()), "triangles_by_material": tris, "triangles_by_object": per_object,
            "colliders": cols, "size_m": [round((hi[i] - lo[i]) * CM, 4) for i in range(3)],
            "min_m": [round(x * CM, 4) for x in lo], "max_m": [round(x * CM, 4) for x in hi]}


# --- the drawing's overlays ------------------------------------------------------------------------------------------
# the straight views' scale and placement (drawing.js: F.K front px per cm, the side's Ks; board_dims [measure])
MF, MS = DIMS["measure"]["front"], DIMS["measure"]["side"]
K_FRONT = (MF["x1"] - MF["x0"]) / FR["width"]
K_SIDE = (MS["bot"] - MS["top"]) / (FR["h1"] - FR["h0"])
IMG_W, IMG_H = 1536, 1024


def image_plane(name: str, image: Path, corners: list) -> None:
    me = bpy.data.meshes.new(name)
    me.from_pydata(corners, [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for i, lp in enumerate(me.loops):
        uv.data[i].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][lp.vertex_index]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(image))
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tex.outputs[0], em.inputs[0])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], o.inputs[0])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)


def ink() -> bpy.types.Material:
    mat = bpy.data.materials.new("ink")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (1.0, 0.45, 0.05, 1.0)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.12
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], o.inputs[0])
    mat.surface_render_method = "BLENDED"
    return mat


def overlays(parts: dict, views: Path, out: Path, res: int) -> list:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 16
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = res, res * IMG_H // IMG_W
    try:
        sc.render.use_freestyle = True
        sc.render.line_thickness_mode = "ABSOLUTE"
        sc.render.line_thickness = 1.0
        ls = sc.view_layers[0].freestyle_settings.linesets[0]
        ls.linestyle.color = (1.0, 0.95, 0.4)
    except (AttributeError, IndexError):
        pass
    m = ink()
    for o in sc.objects:
        if o.type == "MESH" and not o.name.endswith("-convcolonly"):
            for i in range(len(o.data.materials)):
                o.data.materials[i] = m
        elif o.name.endswith("-convcolonly"):
            o.hide_render = True
    for sh in parts["shells"][1:3]:
        set_trip(sh, 1.0)
    # the front view: u = (px - cx) / K, h = h0 + (bot - py) / K, the plane 2 cm behind the wall
    cx = (MF["x0"] + MF["x1"]) / 2
    u0, u1 = (0 - cx) / K_FRONT, (IMG_W - cx) / K_FRONT
    hb, ht = FR["h0"] + (MF["bot"] - IMG_H) / K_FRONT, FR["h0"] + MF["bot"] / K_FRONT
    image_plane("ref_front", views / "front-ortho.jpg", [P(u0, -2, hb), P(u1, -2, hb), P(u1, -2, ht), P(u0, -2, ht)])
    # the side view: d = (wall - px) / Ks (the corridor to the left), h as above; the plane beyond the board's far end
    d_left, d_right = MS["wall"] / K_SIDE, (MS["wall"] - IMG_W) / K_SIDE
    sb, st = FR["h0"] + (MS["bot"] - IMG_H) / K_SIDE, FR["h0"] + MS["bot"] / K_SIDE
    xs = -95.0
    image_plane("ref_side", views / "side-ortho.jpg", [P(xs, d_left, sb), P(xs, d_right, sb), P(xs, d_right, st),
                                                       P(xs, d_left, st)])
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    co = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    shots = []
    for name, loc, rot, width, hide in (
            ("front", P((u0 + u1) / 2, 400, (hb + ht) / 2), (math.pi / 2, 0, 0), u1 - u0, "ref_side"),
            ("side", Vector((3.0, -(d_left + d_right) / 2 * CM, (sb + st) / 2 * CM)), (math.pi / 2, 0, math.pi / 2),
             d_left - d_right, "ref_front")):
        co.location = loc
        co.rotation_euler = rot
        cam.ortho_scale = width * CM
        cam.clip_end = 20.0
        for o in sc.objects:
            if o.name.startswith("ref_"):
                o.hide_render = o.name == hide
        sc.render.filepath = str(out / f"drawing_{name}.png")
        bpy.ops.render.render(write_still=True)
        shots.append(sc.render.filepath)
    return shots


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    parts = build()
    report = export(parts, out)
    report["sweep_check"] = sweep_check(parts)
    report["measured_cm"] = measure(parts)
    report["trip_deg"] = SH["trip_deg"]
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "breaker_board.blend"), compress=True)
    if a["views"]:
        report["overlays"] = overlays(parts, Path(a["views"]), out, a["res"])
    (out / "build.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print("BOARD_BUILD " + json.dumps({k: report[k] for k in ("triangles", "triangles_by_material", "size_m",
                                                               "sweep_check")}), flush=True)


main()
