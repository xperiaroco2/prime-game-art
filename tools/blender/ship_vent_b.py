"""The throat vent, way B (art #263 station 1, vents-b1; docs/ship.md "Station 1"): the body and the gill blade built
in Blender from the concept's views (prime-game-design ideas/ship-components/vent-v2) and the traced numbers of
art#263 comment 6363433518, with way A's Meshy body only as the to-scale guide. Every shape is a flat-faceted solid
with crisp 45 deg chamfers (no rounded bevels, no baked texture): the chamfer faces carry a lighter polished bronze
(`vent_b_edge`), so each edge catches the light as the concept's do.
    blender -b --python ship_vent_b.py -- --out <dir> [--guide <way A body.glb>] [--preview]
The piece's frame (as ship_interior_vent.py): u along the wall (+u toward the column), v out of the wall, h over the
deck; Blender (x, y, z) = (u, -v, h), the GLB's origin on the spot.
- The body (`body.glb`): the box's back slab and roof, the front frame as a ring of nine chamfered panels round the
  octagonal opening with a lower inner lip, a header sill under the opening's top, the two cap rails in the well with seven copper caps each, the left foot
  and the plinth; the column (plinth, foot, shaft, a front panel, the light bar's housing and glass, the lower strip's
  bezel, the scanner's octagonal bezel and screen, the head and the lamp's stepped collar). The game's surfaces keep
  way A's names: `vent_a_body__band` (the bar's glass), `vent_a_body__hand` (the scanner's screen),
  `vent_a_body__lamp` (the lamp's core under the dome); a dark glass each, the clean light pieces lie over them.
- The blade (`blade.glb`): one thick faceted claw on the pivot in the calm pose (22 deg tip down): a round nose round
  the pivot, a broad convex upper face in four facets, a front lip facet (`int_halo__vent_seam`: lit with the heat),
  a concave underside; bowed BOW up at the middle, its ends chamfered.
- `lights.json` (the light pieces' places, as ship_vent_a_bronze.py measured them on way A's body) and `blade.json`
  (the blade's box about the pivot, the seams from the front calm and closed, the first cut, the closed angle)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import bmesh


def arg(k, d=None):
    a = sys.argv[sys.argv.index("--") + 1:]
    return a[a.index(k) + 1] if k in a else d


def flag(k):
    return k in sys.argv[sys.argv.index("--") + 1:]


# --- the numbers (m; art#263 c6363433518 and ship_interior_vent.py) ---------------------------------------------------
BEND, IN, TOP = 1.45, 0.55, 2.30          # the throat wall: vertical to 1.45, then 0.55 in at 2.3
BACK = 0.006                              # the backs off the wall
PIVOT_TOP, PITCH, SLATS, PIVOT_V = 1.276, 0.15, 7, 0.33
CAP_U = (-0.48, 0.32)
BLADE_U = (-0.441, 0.281)                 # the blade's ends, between the caps' inner edges
WELL_V = 0.115
FACE = 0.415                              # the frame's face
LIP = 0.395                               # the inner lip's face, a step down
GLASS_U, GLASS_H, GLASS_V = (0.500, 0.556), (0.622, 1.548), 0.405
SCAN_C, LAMP = (0.685, 1.398), (0.633, 0.335)   # the scanner's centre (u, h); the lamp's axis (u, v)
CALM_DEG, BOW = 22.0, 0.014
# outer frame and opening (u, h), counter-clockwise from the bottom left; the left bar split at 0.80 (two panels)
OUTER = [(-0.66, 0.10), (0.40, 0.10), (0.466, 0.17), (0.466, 1.43), (0.396, 1.50), (-0.58, 1.50), (-0.74, 1.33),
         (-0.74, 0.80), (-0.74, 0.20)]
OPEN = [(-0.49, 0.304), (0.33, 0.304), (0.388, 0.36), (0.388, 1.35), (0.33, 1.408), (-0.46, 1.408), (-0.56, 1.31),
        (-0.56, 0.80), (-0.56, 0.37)]

MATS = {  # name: (base colour linear, metallic, roughness, emission, strength)
    # vents-b2: a deeper, warmer bronze (b1's 0.26/0.13/0.05 read pale tan in EEVEE), the polished chamfers kept, a
    # darker tarnish on the recesses (the panels' gaps, the frame's inner sides, the column's slots)
    "vent_b_bronze": ((0.15, 0.08, 0.032), 0.8, 0.40, None, 0.0),
    "vent_b_edge": ((0.72, 0.43, 0.18), 1.0, 0.18, None, 0.0),
    "vent_b_tarnish": ((0.075, 0.034, 0.012), 0.8, 0.52, None, 0.0),
    "vent_b_under": ((0.30, 0.22, 0.16), 0.3, 0.40, None, 0.0),   # the blades' undersides: catch the well's glow
    "vent_b_copper": ((0.40, 0.10, 0.035), 1.0, 0.26, None, 0.0),
    "vent_b_dark": ((0.035, 0.03, 0.028), 0.85, 0.42, None, 0.0),
    "vent_b_well": ((0.03, 0.05, 0.07), 0.7, 0.38, None, 0.0),
    "vent_a_body__band": ((0.03, 0.025, 0.02), 0.0, 0.4, None, 0.0),
    "vent_a_body__hand": ((0.008, 0.012, 0.018), 0.0, 0.45, None, 0.0),
    "vent_a_body__lamp": ((0.10, 0.004, 0.003), 0.0, 0.4, None, 0.0),
    "int_halo__vent_seam": ((1.0, 0.22, 0.0), 0.0, 0.6, (1.0, 0.22, 0.0), 2.0),
}


def cv(h):
    return 0.0 if h <= BEND else (h - BEND) / (TOP - BEND) * IN


# --- geometry ---------------------------------------------------------------------------------------------------------
class Mesh:
    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def add(self, verts, faces, mats):
        b = len(self.v)
        self.v += verts
        self.f += [tuple(b + i for i in f) for f in faces]
        self.m += mats


def area(poly):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1])) / 2


def ccw(poly):
    return poly if area(poly) > 0 else poly[::-1]


def inset(poly, d):
    """A convex CCW polygon's edges moved d inward (negative: outward), adjacent lines intersected."""
    n, out = len(poly), []
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        lines.append(((a[0] - dy / ln * d, a[1] + dx / ln * d), (dx, dy)))
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-12:
            out.append(p2)
            continue
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + t * d1[0], p1[1] + t * d1[1]))
    return out


def frame(axis, p, q, w):
    """(p, q) in the profile's plane, w along the extrusion -> (u, v, h)."""
    return {"v": (p, w, q), "u": (w, p, q), "h": (p, q, w)}[axis]


def solid(M, poly, w0, w1, axis="v", front=((0.014, 0.014), (0.004, 0.002)), back=(), mat="vent_b_bronze",
          edge="vent_b_edge", cap=None, side=None):
    """A convex profile extruded from w0 to w1 along axis, its w1 end chamfered by `front` steps (dw, inset) and its
    w0 end by `back`. The chamfer faces get `edge`, the sides `side` (default mat), the end faces `cap` (default mat)."""
    poly = ccw(list(poly))
    n = len(poly)
    bands = []
    ins_b = sum(di for _, di in back)
    loops = [(w0, ins_b)]
    acc_w, acc_i = w0, ins_b
    for dw, di in back:
        acc_w += dw
        acc_i -= di
        loops.append((acc_w, acc_i))
        bands.append(edge)
    w1s = w1 - sum(dw for dw, _ in front)
    loops.append((w1s, 0.0))
    bands.append(side or mat)
    acc_w, acc_i = w1s, 0.0
    for dw, di in front:
        acc_w += dw
        acc_i += di
        loops.append((acc_w, acc_i))
        bands.append(edge)
    verts = []
    for w, d in loops:
        pts = inset(poly, d) if d else poly
        verts += [frame(axis, p, q, w) for p, q in pts]
    faces, mats = [], []
    for i in range(len(loops) - 1):
        for j in range(n):
            faces.append((i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j))
            mats.append(bands[i])
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range((len(loops) - 1) * n, len(loops) * n)))
    mats += [cap or mat, cap or mat]
    M.add(verts, faces, mats)


def ngon(c, r, n, rot=0.0):
    return [(c[0] + r * math.cos(rot + 2 * math.pi * i / n), c[1] + r * math.sin(rot + 2 * math.pi * i / n))
            for i in range(n)]


def octo(u0, h0, u1, h1, c):
    return [(u0 + c, h0), (u1 - c, h0), (u1, h0 + c), (u1, h1 - c), (u1 - c, h1), (u0 + c, h1), (u0, h1 - c),
            (u0, h0 + c)]


def ring(M, outer, inner, w0, w1, gap=0.004, **kw):
    """Panels between two matching polygons (a frame round an opening), each its own chamfered solid, `gap` apart."""
    n = len(outer)
    for i in range(n):
        quad = [outer[i], outer[(i + 1) % n], inner[(i + 1) % n], inner[i]]
        solid(M, inset(ccw(quad), gap / 2), w0, w1, **kw)


def slab_light(c, a1, n, e1, e2):
    a2 = (n[1] * a1[2] - n[2] * a1[1], n[2] * a1[0] - n[0] * a1[2], n[0] * a1[1] - n[1] * a1[0])
    return {"c": [round(x, 5) for x in c], "a1": [round(x, 5) for x in a1], "a2": [round(x, 5) for x in a2],
            "n": list(n), "e1": e1, "e2": e2, "texels": 1000}


# --- the body ---------------------------------------------------------------------------------------------------------
def body():
    M = Mesh()
    strips = []
    # the box's back slab (the well's back) and its roof over the frame, the back following the wall's slant
    solid(M, [(-0.72, 0.10), (0.45, 0.10), (0.45, 1.45), (-0.72, 1.45)], BACK, WELL_V, front=((0.01, 0.01),),
          side="vent_b_tarnish")
    roof = [(BACK, 1.42), (0.30, 1.42), (0.30, 1.53), (0.245, 1.608), (0.135, 1.608), (BACK + 0.012, 1.45)]
    solid(M, [(v, h) for v, h in roof], -0.72, 0.45, axis="u", front=((0.016, 0.016), (0.004, 0.002)),
          back=((0.016, 0.016), (0.004, 0.002)))
    # the frame: nine panels from the outline to 3 cm outside the opening, then the lip round the opening
    mid = inset(ccw(OPEN), -0.03)
    ring(M, OUTER, mid, WELL_V, FACE, front=((0.010, 0.010), (0.004, 0.002)), side="vent_b_tarnish")
    ring(M, mid, OPEN, WELL_V, LIP, gap=0.003, side="vent_b_well", front=((0.012, 0.012),))
    # the header: a chamfered sill under the opening's top, so no glow shows over the top blade (front_closed)
    solid(M, [(WELL_V, 1.335), (0.345, 1.335), (0.375, 1.36), (0.375, 1.412), (WELL_V, 1.412)], OPEN[-1][0] + 0.002,
          OPEN[3][0] - 0.002, axis="u", front=((0.006, 0.006),), back=((0.006, 0.006),))
    # the cap rails in the well and the caps (copper, on a dark socket, a boss in the middle)
    for u0, u1 in ((OPEN[-1][0], BLADE_U[0] - 0.004), (BLADE_U[1] + 0.004, OPEN[3][0])):
        solid(M, [(u0, 0.31), (u1, 0.31), (u1, 1.40), (u0, 1.40)], WELL_V, 0.30, mat="vent_b_dark",
              front=((0.006, 0.006),))
    for cu in CAP_U:
        for k in range(SLATS):
            c = (cu, PIVOT_TOP - k * PITCH)
            solid(M, ngon(c, 0.034, 16), 0.30, 0.322, mat="vent_b_dark", front=((0.004, 0.003),))
            solid(M, ngon(c, 0.029, 16), 0.318, 0.346, mat="vent_b_copper", edge="vent_b_copper",
                  front=((0.008, 0.007), (0.002, 0.003)))
            solid(M, ngon(c, 0.012, 12), 0.34, 0.356, mat="vent_b_copper", edge="vent_b_edge", front=((0.004, 0.003),))
    # the foot at the bottom left and the plinth under the box
    solid(M, [(-0.80, 0.0), (-0.54, 0.0), (-0.54, 0.07), (-0.62, 0.19), (-0.73, 0.19), (-0.80, 0.08)], BACK, 0.44,
          front=((0.018, 0.018), (0.004, 0.002)))
    solid(M, [(-0.56, 0.0), (0.45, 0.0), (0.45, 0.10), (-0.56, 0.10)], 0.03, 0.385, front=((0.016, 0.016),))
    # the frame's strips (each on its panel's face: the centre, the long axis, the half extents)
    def on_panel(i, e1, e2, t=0.5, lift=0.0):
        a, b = OUTER[i], OUTER[(i + 1) % len(OUTER)]
        ia, ib = mid[i], mid[(i + 1) % len(mid)]
        pa = (a[0] + (ia[0] - a[0]) * 0.5, a[1] + (ia[1] - a[1]) * 0.5)
        pb = (b[0] + (ib[0] - b[0]) * 0.5, b[1] + (ib[1] - b[1]) * 0.5)
        c = (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t + lift)
        dx, dh = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dh)
        return slab_light((c[0], FACE, c[1]), (dx / ln, 0.0, dh / ln), (0.0, 1.0, 0.0), e1, e2)
    strips += [on_panel(5, 0.055, 0.011), on_panel(3, 0.03, 0.010), on_panel(6, 0.13, 0.012),
               on_panel(7, 0.12, 0.012, t=0.5), on_panel(2, 0.13, 0.006, t=0.22), on_panel(0, 0.13, 0.012, t=0.55)]
    for st in strips:   # a dark slot under each strip
        c, a1, a2 = st["c"], st["a1"], st["a2"]
        e1, e2 = st["e1"] + 0.007, st["e2"] + 0.005
        pts = [(c[0] + i * e1 * a1[0] + j * e2 * a2[0], c[2] + i * e1 * a1[2] + j * e2 * a2[2])
               for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        solid(M, pts, FACE - 0.004, FACE + 0.0012, mat="vent_b_dark", front=())
    # --- the column ---
    solid(M, [(0.44, 0.0), (0.80, 0.0), (0.80, 0.08), (0.775, 0.12), (0.47, 0.12), (0.44, 0.08)], BACK, 0.46,
          front=((0.018, 0.018), (0.004, 0.002)))
    solid(M, [(0.47, 0.12), (0.785, 0.12), (0.785, 0.26), (0.47, 0.26)], BACK, 0.42, front=((0.016, 0.016),))
    shaft = [(BACK, 0.25), (0.36, 0.25), (0.36, 1.62), (cv(1.62) + 0.012, 1.62), (BACK, 1.45)]
    solid(M, shaft, 0.475, 0.785, axis="u", front=((0.014, 0.014),), back=((0.014, 0.014),))
    solid(M, octo(0.48, 0.27, 0.78, 1.60, 0.03), 0.30, 0.38, front=((0.012, 0.012), (0.003, 0.002)),
          side="vent_b_tarnish")
    # the light bar: a chamfered housing round the glass (the glass 1 mm into it)
    g_out = octo(GLASS_U[0] - 0.017, GLASS_H[0] - 0.024, GLASS_U[1] + 0.017, GLASS_H[1] + 0.024, 0.012)
    g_in = octo(GLASS_U[0], GLASS_H[0], GLASS_U[1], GLASS_H[1], 0.004)
    ring(M, g_out, g_in, 0.36, 0.425, gap=0.0, front=((0.01, 0.009), (0.002, 0.0015)))
    solid(M, [(GLASS_U[0] - 0.001, GLASS_H[0] - 0.001), (GLASS_U[1] + 0.001, GLASS_H[0] - 0.001),
              (GLASS_U[1] + 0.001, GLASS_H[1] + 0.001), (GLASS_U[0] - 0.001, GLASS_H[1] + 0.001)], 0.37, GLASS_V,
          mat="vent_a_body__band", front=())
    # the lower strip in its bezel under the bar
    s_out = octo(0.488, 0.29, 0.568, 0.565, 0.012)
    s_in = octo(0.504, 0.306, 0.552, 0.549, 0.005)
    ring(M, s_out, s_in, 0.36, 0.42, gap=0.0, front=((0.009, 0.008),))
    solid(M, [(0.503, 0.305), (0.553, 0.305), (0.553, 0.55), (0.503, 0.55)], 0.37, 0.397, mat="vent_b_dark", front=())
    strips.append(slab_light((0.528, 0.397, 0.4275), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), 0.112, 0.017))
    # the scanner: an octagonal bezel (two chamfers), its screen 1.5 cm behind the bezel's face
    su, sh = SCAN_C
    b_out = octo(su - 0.105, sh - 0.125, su + 0.105, sh + 0.125, 0.04)
    b_in = inset(ccw(b_out), 0.022)
    ring(M, b_out, b_in, 0.36, 0.45, gap=0.0, front=((0.012, 0.011), (0.003, 0.002)))
    screen_v = 0.435
    solid(M, inset(ccw(b_in), -0.001), 0.37, screen_v, mat="vent_a_body__hand", front=())
    xs, hs = [p[0] for p in b_in], [p[1] for p in b_in]
    hand = {"lo": [min(xs) + 0.004, 0.37, min(hs) + 0.004], "hi": [max(xs) - 0.004, screen_v, max(hs) - 0.004],
            "n": [0.0, 1.0, 0.0], "poly": [[round(x, 5), round(y, 5)] for x, y in b_in]}
    # the head and the lamp's stepped collar; the core under the dome (`__lamp`)
    solid(M, [(0.48, 1.60), (0.78, 1.60), (0.78, 1.665), (0.745, 1.70), (0.515, 1.70), (0.48, 1.665)],
          cv(1.70) + 0.012, 0.40, front=((0.014, 0.014), (0.004, 0.002)))
    solid(M, ngon(LAMP, 0.078, 8, math.pi / 8), 1.69, 1.726, axis="h", front=((0.008, 0.008),), back=())
    solid(M, ngon(LAMP, 0.066, 16), 1.726, 1.743, axis="h", mat="vent_b_dark", front=((0.002, 0.002),))
    solid(M, ngon(LAMP, 0.071, 16), 1.743, 1.757, axis="h", front=((0.004, 0.004),))
    solid(M, ngon(LAMP, 0.036, 12), 1.756, 1.79, axis="h", mat="vent_a_body__lamp", front=())
    r = 0.055
    lamp = {"lo": [LAMP[0] - r, LAMP[1] - r, 1.7555], "hi": [LAMP[0] + r, LAMP[1] + r, 1.838], "n": [0.0, 0.0, 1.0]}
    band = {"lo": [GLASS_U[0], 0.37, GLASS_H[0]], "hi": [GLASS_U[1], GLASS_V, GLASS_H[1]], "n": [0.0, 1.0, 0.0]}
    return M, {"lamp": lamp, "band": band, "hand": hand, "strips": strips}


# --- the blade --------------------------------------------------------------------------------------------------------
# the claw's section in the calm pose about the pivot (dv out of the wall, dh up), counter-clockwise from the front lip's
# bottom (the tip); index ranges: the lip SEAM, the upper facets, the nose, the underside
# vents-b2: a thicker, more curved claw (front_ortho, side_left): a broad upper face rising to a crest 8 cm out, curving
# over in seven facets to a hooked tip that curls back under itself, a concave underside; 10.5 cm thick at the root,
# 9.6 at 0.1 m, 6 at 0.2 m (b1: 8.5 and 4.5); the same 26.4 cm reach and 11 cm seen from the front (a 4 cm seam)
SECTION = [(0.250, -0.072), (0.264, -0.058), (0.262, -0.040), (0.252, -0.020), (0.234, -0.002), (0.208, 0.014),
           (0.172, 0.026), (0.128, 0.034), (0.078, 0.038), (0.028, 0.038), (-0.004, 0.034), (-0.024, 0.024),
           (-0.034, 0.006), (-0.034, -0.016), (-0.026, -0.040), (-0.006, -0.060), (0.040, -0.067), (0.100, -0.062),
           (0.160, -0.053), (0.205, -0.047), (0.232, -0.054), (0.244, -0.064)]
SEAM_EDGE = 0                    # the edge from point 0 to 1: the hooked tip's lip
EDGE_EDGES = {1, 7, 8, 11}       # the hook's outer edge, the crest's two facets and the nose's top catch the light
UNDER_EDGES = {14, 15, 16, 17, 18, 19, 20}   # the concave underside: less metal, so the well's glow lights it
END_CH = 0.012


def blade():
    M = Mesh()
    sec = SECTION
    n = len(sec)
    cx = sum(p[0] for p in sec) / n
    cy = sum(p[1] for p in sec) / n
    u0, u1 = BLADE_U
    L = u1 - u0
    um = (u0 + u1) / 2
    # the ends chamfered; a shallow crease at the middle (the concept's two halves): two rings 5 mm apart, 4% in
    xs = ([u0, u0 + END_CH] + [u0 + L * i / 10 for i in range(1, 5)] + [um - 0.005, um, um + 0.005]
          + [u0 + L * i / 10 for i in range(6, 10)] + [u1 - END_CH, u1])
    verts = []
    for i, x in enumerate(xs):
        t = (x - um) / (L / 2)
        bow = BOW * (1 - t * t)
        k = 0.82 if i in (0, len(xs) - 1) else (0.96 if abs(x - um) < 1e-9 else 1.0)
        for dv, dh in sec:
            verts.append((x, cx + (dv - cx) * k, cy + (dh - cy) * k + bow))
    faces, mats = [], []
    for i in range(len(xs) - 1):
        end = i in (0, len(xs) - 2)
        for j in range(n):
            faces.append((i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j))
            mats.append("vent_b_edge" if end or j in EDGE_EDGES else
                        ("int_halo__vent_seam" if j == SEAM_EDGE else
                         ("vent_b_under" if j in UNDER_EDGES else "vent_b_bronze")))
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range((len(xs) - 1) * n, len(xs) * n)))
    mats += ["vent_b_bronze", "vent_b_bronze"]
    # (x, dv, dh) -> (u, v, h) about the pivot: the frame keeps v as dv
    M.add([(x, dv, dh) for x, dv, dh in verts], faces, mats)
    return M


def turned(pts, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(p[0] * c - p[1] * s, p[0] * s + p[1] * c) for p in pts]


def seg_cross(a, b, c, d):
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def overlap(p1, p2):
    return any(seg_cross(p1[i], p1[(i + 1) % len(p1)], p2[j], p2[(j + 1) % len(p2)])
               for i in range(len(p1)) for j in range(len(p2)))


def blade_numbers():
    """The seams straight from the front and the first cut between two neighbours, turned d deg further down."""
    def seam(deg):
        s = turned(SECTION, -deg)
        return PITCH + min(p[1] for p in s) - max(p[1] for p in s)
    first_cut = None
    for tenth in range(0, 900):
        d = tenth / 10
        a = turned(SECTION, -d)
        b = [(p[0], p[1] - PITCH) for p in a]
        if overlap(a, b):
            first_cut = d
            break
    closed = None
    for tenth in range(0, 600):
        d = tenth / 10
        if seam(d) <= 0.006:
            closed = d
            break
    return {"calm_seam": round(seam(0), 4), "closed_deg": closed, "closed_seam": round(seam(closed), 4),
            "first_cut_deg": first_cut}


# --- Blender ----------------------------------------------------------------------------------------------------------
def material(name):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    base, metal, rough, emit, strength = MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = strength
    return m


def to_object(M, name):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(u, -v, h) for u, v, h in M.v], [], M.f)
    names = []
    for mn in M.m:
        if mn not in names:
            names.append(mn)
    for mn in names:
        me.materials.append(material(mn))
    for p, mn in zip(me.polygons, M.m):
        p.material_index = names.index(mn)
        p.use_smooth = False
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.new(name="UVMap")
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def export(ob, path):
    for o in bpy.context.scene.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_materials="EXPORT")


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def main():
    out = Path(arg("--out"))
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rep = {}
    if arg("--guide"):   # way A's Meshy body, the to-scale guide: its box in the piece's frame
        bpy.ops.import_scene.gltf(filepath=arg("--guide"))
        vs = [o.matrix_world @ v.co for o in bpy.context.scene.objects if o.type == "MESH" for v in o.data.vertices]
        rep["guide_box"] = {"u": [round(min(v.x for v in vs), 3), round(max(v.x for v in vs), 3)],
                            "v": [round(-max(v.y for v in vs), 3), round(-min(v.y for v in vs), 3)],
                            "h": [round(min(v.z for v in vs), 3), round(max(v.z for v in vs), 3)]}
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    M, lights = body()
    ob = to_object(M, "vent_b_body")
    rep["body_tris"] = tris(ob)
    rep["body_box"] = {k: [round(min(p[i] for p in M.v), 3), round(max(p[i] for p in M.v), 3)]
                       for i, k in enumerate("uvh")}
    rep["back_clear_min"] = round(min(v - cv(h) for _, v, h in M.v), 4)   # every vertex in front of the wall
    export(ob, out / "body.glb")
    bpy.data.objects.remove(ob, do_unlink=True)
    B = blade()
    ob = to_object(B, "vent_b_blade")
    rep["blade_tris"] = tris(ob)
    box = [[round(min(p[i] for p in B.v), 4), round(max(p[i] for p in B.v), 4)] for i in range(3)]
    # the box about the pivot, its u centred on the caps' mid (as ship_interior_vent.BLADE_BOX)
    um = (CAP_U[0] + CAP_U[1]) / 2 + 0.0
    rep["blade_box"] = [[round(box[0][0] - um, 4), round(box[0][1] - um, 4)], box[1], box[2]]
    rep["blade"] = blade_numbers()
    # the GLB's origin on the pivot: x about the caps' mid (the harness places it at the hinge)
    ob.data.transform(__import__("mathutils").Matrix.Translation((-um, 0, 0)))
    export(ob, out / "blade.glb")
    (out / "lights.json").write_text(json.dumps(lights, indent=1), encoding="utf-8", newline="\n")
    (out / "blade.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    print("VENTB " + json.dumps(rep))


if __name__ == "__main__":
    main()
