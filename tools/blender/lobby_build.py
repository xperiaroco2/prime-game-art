"""Builds the lobby hall's shell, one GLB per piece (art #356, docs/lobby.md): run by `lobby --build`.

    blender -b --python lobby_build.py -- --request <request.json> --out <dir>

request.json (tools/runner/commands/lobby.py): {"layout": <layouts/lobby/hall.toml>, "arc": [r, cz], "ring_z": z,
"look": the scheme's materials}.
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
# The fixed materials (linear colour, roughness, metallic, emission strength), the same in every scheme; the others
# (panels, frames, trim, floor, the strips and the ring) come resolved from the layout's [look] scheme (req["look"]).
MATS = {"lobby_grout": ((0.010, 0.010, 0.012, 1), 0.55, 0.3, 0.0),
        "lobby_dark": ((0.018, 0.018, 0.020, 1), 0.5, 0.4, 0.0),
        "lobby_lamp": ((1.0, 0.015, 0.008, 1), 0.4, 0.0, 2.6),
        "lobby_lens": ((0.8, 0.76, 0.66, 1), 0.25, 0.0, 0.0),
        "lobby_hazard": ((0.78, 0.48, 0.015, 1), 0.5, 0.1, 0.0),
        "lobby_glass": ((0.45, 0.6, 0.8, 0.12), 0.05, 0.0, 0.0)}
ARC_STEP_DEG = 2.0


# --- parts ---------------------------------------------------------------------------------------------------------
class Part:
    def __init__(self, name: str, mat: str, closed: bool = True, col: bool = False):
        self.name, self.mat, self.closed, self.col = name, mat, closed, col
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
        ctr = [[sum(p[q] for p in sec) / k for q in range(3)] for sec in sections]
        for n, (s0, s1) in enumerate(zip(sections, sections[1:])):
            c = [(ctr[n][q] + ctr[n + 1][q]) / 2 for q in range(3)]
            for i in range(k):
                quad = [s0[i], s0[(i + 1) % k], s1[(i + 1) % k], s1[i]]
                self.face(quad, [sum(p[q] for p in quad) / 4 - c[q] for q in range(3)])
        self.face(list(sections[0]), [ctr[0][q] - ctr[1][q] for q in range(3)])
        self.face(list(sections[-1]), [ctr[-1][q] - ctr[-2][q] for q in range(3)])


def _normal(pts):
    """Newell's normal: right for concave polygons too."""
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def _L(axis, p2, t):
    """A local (u, v, w) point from a 2D point in the two axes other than axis (in u, v, w order) and axis's value."""
    a, b = p2
    return (a, b, t) if axis == "w" else (a, t, b) if axis == "v" else (t, a, b)


def ext(part: "Part", F, poly, axis, t0, t1):
    """A prism in a local frame F(u, v, w) -> lobby point: the 2D polygon (any winding, may be concave) along axis."""
    n = len(poly)
    sgn = 1 if sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) > 0 else -1
    o = F(0.0, 0.0, 0.0)

    def wd(d):  # a local direction in the lobby frame (F is affine)
        q = F(*d)
        return [q[k] - o[k] for k in range(3)]

    ax = {"u": (1, 0, 0), "v": (0, 1, 0), "w": (0, 0, 1)}[axis]
    s = 1 if t1 > t0 else -1
    P0 = [F(*_L(axis, p, t0)) for p in poly]
    P1 = [F(*_L(axis, p, t1)) for p in poly]
    part.face(P1, wd([a * s for a in ax]))
    part.face(P0, wd([-a * s for a in ax]))
    for i in range(n):
        j = (i + 1) % n
        (ax2, ay2), (bx2, by2) = poly[i], poly[j]
        part.face([P0[i], P0[j], P1[j], P1[i]], wd(_L(axis, (sgn * (by2 - ay2), -sgn * (bx2 - ax2)), 0.0)))


def plate(part: "Part", F, u0, u1, v0, v1, w0, w1, bev):
    """A bevelled plate on a local wall (front at w1, inset by bev; open at the back, against the wall)."""
    front = [F(u0 + bev, v0 + bev, w1), F(u1 - bev, v0 + bev, w1), F(u1 - bev, v1 - bev, w1), F(u0 + bev, v1 - bev, w1)]
    back = [F(u0, v0, w0), F(u1, v0, w0), F(u1, v1, w0), F(u0, v1, w0)]
    o = F(0.0, 0.0, 0.0)

    def wd(d):
        q = F(*d)
        return [q[k] - o[k] for k in range(3)]

    part.face(front, wd((0, 0, 1)))
    for i, d in enumerate(((0, -1, 0.3), (1, 0, 0.3), (0, 1, 0.3), (-1, 0, 0.3))):
        j = (i + 1) % 4
        part.face([back[i], back[j], front[j], front[i]], wd(d))


def lbox(part: "Part", F, u0, u1, v0, v1, w0, w1):
    ext(part, F, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], "w", w0, w1)


def chamfer_outline(a, h, c, d=0.0):
    """An opening of half-width a and height h with its top corners cut by c (45 deg), offset outward by d."""
    a2, h2, c2 = a + d, h + d, c + d * (2 - math.sqrt(2))
    return [(-a2, 0.0), (-a2, h2 - c2), (-a2 + c2, h2), (a2 - c2, h2), (a2, h2 - c2), (a2, 0.0)]


def ring(inner, outer):
    """The U-shaped frame between two outlines, open at the floor."""
    return list(outer) + list(reversed(inner))


def clip(poly, nx, ny, c):
    """Sutherland-Hodgman: the part of a convex 2D polygon where nx * x + ny * y <= c."""
    out = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        da, db = nx * a[0] + ny * a[1] - c, nx * b[0] + ny * b[1] - c
        if da <= 0:
            out.append(a)
        if (da < 0) != (db < 0) and da != db:
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def intervals(span, cuts):
    """span (a, b) minus the intervals cuts [(a, b)]."""
    out = [span]
    for c0, c1 in cuts:
        nxt = []
        for a, b in out:
            if c1 <= a or c0 >= b:
                nxt.append((a, b))
                continue
            if c0 > a:
                nxt.append((a, c0))
            if c1 < b:
                nxt.append((c1, b))
        out = nxt
    return [(a, b) for a, b in out if b - a > 1e-6]


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
# Ours, not the drawing's (steps 2 and 2b, docs/lobby.md): the wall's bands and rows (v, metres up), the frames' bands,
# the panels' gaps, bevels and depths, the strips' and lamps' sizes.
ROWS_LOW = [(0.32, 2.35), (2.41, 4.6), (4.66, 7.1)]      # the wall panels under the cornice
ROWS_HIGH = [(7.8, 9.7), (10.85, 11.5)]                  # and above it, round the frieze's channel
CORNICE = (7.2, 7.7)
FRIEZE = (9.7, 10.85)                                    # the recessed channel: its lips, two conduits, the blocks
FRIEZE_STEPS = (1.1, 1.9, 1.4, 2.5, 1.2, 2.1)            # the frieze blocks' spacing along a wall, cycled
PANEL_MAX, GAP, BEV, PROUD = 2.1, 0.05, 0.03, 0.07
DOOR_BANDS = (0.16, 0.14, 0.12)                          # a door's three nested frame bands, inside out
DOOR_FRONTS = (0.26, 0.17, 0.08)                         # their fronts: stepped back outward
ARCH_BANDS = (0.4, 0.33, 0.27)                           # the portal's (their sum is [arch] frame + 0.4)
ARCH_FRONTS = (0.42, 0.28, 0.14)
STRIP = (2.0, 4.4)                                       # a pilaster's light strip, v
LAMP_HALF = (0.3, 0.13)
LINTEL = 0.3                                             # a door's lintel box: its depth
PENDANTS = ((-10.0, 0.0, 10.0), (-21.0, -9.0, 3.0), 9.6)  # the pendant lamps: x, z, the shade's bottom (y)


def pick(*keys, n=3):
    """A steady pseudo-random choice in 0..n-1 from numbers (the same panel always gets the same tone)."""
    x = math.sin(sum(float(k) * m for k, m in zip(keys, (12.9898, 78.233, 37.719, 4.581)))) * 43758.5453
    return int((x - math.floor(x)) * n) % n


def shifted(F, dw):
    return lambda u, v, w: F(u, v, w + dw)


def wall_frames(H: "Hall"):
    """Each wall's local frame: u along the wall, v up, w out of its inner face into the hall."""
    h = H.h
    return {"N": lambda u, v, w: (u, v, h["zN"] + w),
            "W": lambda u, v, w: (h["x0"] + w, v, u),
            "E": lambda u, v, w: (h["x1"] - w, v, u)}


def wall_cuts(H: "Hall"):
    """Per wall its pilasters' u and the openings' (u0, u1, v_top) with their frames, lintels and headers."""
    h, a = H.h, H.a
    pil = {"N": list(h["north_pilasters"]), "W": list(h["ribs"]), "E": list(h["ribs"])}
    holes = {"N": [], "W": [], "E": []}
    half = H.d["w"] / 2 + sum(DOOR_BANDS) + 0.05
    for _id, wall, at in H.d["doors"]:
        holes[wall].append((at - half, at + half, H.d["lamp"] + 0.5))
    ah = a["w"] / 2 + sum(ARCH_BANDS) + 0.1
    holes["N"].append((-ah, ah, a["h"] + sum(ARCH_BANDS) + 0.8))   # up to its lintel, over the cornice
    span = {"N": (h["x0"], h["x1"]), "W": (h["zN"], h["zS"]), "E": (h["zN"], h["zS"])}
    return pil, holes, span


def floor_plates(parts: list, x0, x1, z0, z1, g, zmax=None, y=0.015, gap=0.006, bev=0.02):
    """2 m plates with fine seams and bevelled edges (front at y) in three tones, clipped at zmax(x) (the arc)."""
    F = lambda u, v, w: (u, w, v)   # u = x, v = z, w = up
    x = x0
    while x < x1 - 1e-6:
        z = z0
        while z < z1 - 1e-6:
            xa, xb, za, zb = x + gap, min(x + g, x1) - gap, z + gap, min(z + g, z1) - gap
            if zmax is not None:
                zb = min(zb, zmax(xa) - gap, zmax(xb) - gap)
            if zb - za > 0.15:
                plate(parts[pick(x, z, 7.0)], F, xa, xb, za, zb, 0.0, y, bev)
            z += g
        x += g


def _floor_set(prefix: str) -> list:
    return [Part(prefix, "lobby_floor", closed=False), Part(prefix + "2", "lobby_floor2", closed=False),
            Part(prefix + "3", "lobby_floor3", closed=False)]


def floor(H: Hall) -> list[Part]:
    h, t = H.h, H.h["wall_t"]
    slab = Part("floor_slab", "lobby_grout", col=True)
    arc = [H.arc_pt(a) for a in reversed(H.angles())]   # east to west
    prism(slab, [(h["x0"] - t, h["zN"] - t), (h["x1"] + t, h["zN"] - t), (h["x1"] + t, h["zS"]), *arc,
                 (h["x0"] - t, h["zS"])], -0.3, 0.0)
    plates = _floor_set("floor_plates")
    floor_plates(plates, h["x0"], h["x1"], h["zN"], h["zS"] + h["bulge"], h["tile"], zmax=H.arc_z)
    # the ring: a dark channel with the accent line inlaid
    parts = [slab, *plates]
    rr, n = H.L["floor"]["ring_r"], 160
    for name, mat, r0, r1, y in (("floor_ring_channel", "lobby_grout", rr - 0.17, rr + 0.17, 0.016),
                                 ("floor_ring", "lobby_ring", rr - 0.06, rr + 0.06, 0.019)):
        ring_p = Part(name, mat, closed=False)
        for i in range(n):
            a, b = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            ring_p.face([(r0 * math.sin(a), y, H.ring_z + r0 * math.cos(a)), (r1 * math.sin(a), y, H.ring_z + r1 * math.cos(a)),
                         (r1 * math.sin(b), y, H.ring_z + r1 * math.cos(b)), (r0 * math.sin(b), y, H.ring_z + r0 * math.cos(b))], (0, 1, 0))
        parts.append(ring_p)
    return parts


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


def channel(F, u0, u1, v0, v1, w, dark: Part, strip: Part, lip=0.03):
    """A light strip seated in a dark channel: a back, four lips round it and only the strip's front face, 1 cm behind
    the lips' fronts (no side or back faces of the emissive to smear light beside it)."""
    lbox(dark, F, u0 - lip, u1 + lip, v0 - lip, v1 + lip, w, w + 0.012)
    for a in ((u0 - lip, u0, v0 - lip, v1 + lip), (u1, u1 + lip, v0 - lip, v1 + lip), (u0, u1, v0 - lip, v0),
              (u0, u1, v1, v1 + lip)):
        lbox(dark, F, a[0], a[1], a[2], a[3], w + 0.012, w + 0.035)
    o, q = F(0.0, 0.0, 0.0), F(0.0, 0.0, 1.0)
    strip.face([F(u0, v0, w + 0.024), F(u1, v0, w + 0.024), F(u1, v1, w + 0.024), F(u0, v1, w + 0.024)],
               [q[k] - o[k] for k in range(3)])


def bolts(part: Part, F, u0, u1, v, w, step=0.32, s=0.025):
    n = max(2, int((u1 - u0) / step))
    for i in range(n + 1):
        u = u0 + (u1 - u0) * i / n
        lbox(part, F, u - s, u + s, v - s, v + s, w, w + 0.018)


def pilaster(H: Hall, F, u, lo, hi, shaft: Part, trim: Part, dark: Part, strip: Part, top: float):
    """A pilaster at u; below the cornice only lo..hi (narrowed beside a door's frame, step 2b)."""
    pw, pd, c = H.h["pilaster_w"] / 2, H.h["pilaster_d"], 0.12

    def prof(a, b):
        return [(a, 0.0), (b, 0.0), (b, pd - c), (b - c, pd), (a + c, pd), (a, pd - c)]

    ext(shaft, F, prof(lo, hi), "v", 0.0, CORNICE[0])
    ext(shaft, F, prof(u - pw, u + pw), "v", CORNICE[0], top - 0.6)
    l2 = lo - 0.08 if lo <= u - pw + 1e-6 else lo
    h2 = hi + 0.08 if hi >= u + pw - 1e-6 else hi
    lbox(trim, F, l2, h2, 0.0, 0.5, 0.0, pd + 0.08)                                  # the plinth
    lbox(trim, F, u - pw - 0.06, u + pw + 0.06, top - 0.6, top, 0.0, pd + 0.1)         # the capital
    lbox(trim, F, u - pw - 0.03, u + pw + 0.03, CORNICE[0], CORNICE[1], 0.0, pd + 0.05)  # the band at the cornice
    m = (lo + hi) / 2
    channel(F, m - 0.04, m + 0.04, STRIP[0], STRIP[1], pd, dark, strip)
    lbox(trim, F, m - 0.16, m + 0.16, 4.8, 6.9, pd, pd + 0.03)                         # a bolted face plate
    for v in (4.95, 6.75):
        bolts(trim, F, m - 0.1, m + 0.1, v, pd + 0.03, step=0.2)
    lbox(trim, F, u - pw + 0.1, u + pw - 0.1, 8.4, 10.6, pd, pd + 0.03)


def vent(F, u0, u1, v0, v1, trim: Part, dark: Part):
    lbox(dark, F, u0, u1, v0, v1, 0.0, 0.02)
    for side in ((u0, u0 + 0.08, v0, v1), (u1 - 0.08, u1, v0, v1), (u0, u1, v0, v0 + 0.08), (u0, u1, v1 - 0.08, v1)):
        lbox(trim, F, side[0], side[1], side[2], side[3], 0.0, 0.1)
    v = v0 + 0.16
    while v < v1 - 0.16:
        ext(trim, F, [(v, 0.02), (v + 0.05, 0.02), (v + 0.1, 0.08), (v + 0.05, 0.08)], "u", u0 + 0.08, u1 - 0.08)
        v += 0.14


def pipe(part: Part, F, u0, u1, v, w, r):
    ext(part, F, [(v + r * math.cos(k * math.pi / 4), w + r * math.sin(k * math.pi / 4)) for k in range(8)], "u", u0, u1)


def vpipe(part: Part, F, u, v0, v1, w, r):
    ext(part, F, [(u + r * math.cos(k * math.pi / 4), w + r * math.sin(k * math.pi / 4)) for k in range(8)], "v", v0, v1)


def wall_panel(F, u0, u1, v0, v1, style, tone, P: list, inset: Part, trim: Part):
    """One wall panel in two or three depths (step 2b): style 0 a raised inner plate, 1 a frame round a recessed
    centre, 2 plain with bolt rows, 3 plain with two raised ribs, -1 plain; tone picks one of the three panel tones."""
    p, p2 = P[tone], P[(tone + 1) % 3]
    if style == 1 and u1 - u0 > 0.9 and v1 - v0 > 0.9:
        b = 0.14
        for a in ((u0, u1, v0, v0 + b), (u0, u1, v1 - b, v1), (u0, u0 + b, v0 + b, v1 - b), (u1 - b, u1, v0 + b, v1 - b)):
            plate(p, F, a[0], a[1], a[2], a[3], 0.0, 0.12, 0.025)
        plate(inset, F, u0 + b, u1 - b, v0 + b, v1 - b, 0.0, 0.035, 0.015)
        return
    plate(p, F, u0, u1, v0, v1, 0.0, PROUD, BEV)
    if style == 0 and u1 - u0 > 0.8 and v1 - v0 > 0.8:
        plate(p2, F, u0 + 0.16, u1 - 0.16, v0 + 0.16, v1 - 0.16, PROUD, PROUD + 0.04, 0.025)
    elif style == 2:
        for v in (v0 + 0.09, v1 - 0.09):
            bolts(trim, F, u0 + 0.12, u1 - 0.12, v, PROUD)
    elif style == 3 and v1 - v0 > 0.8:
        for v in (v0 + (v1 - v0) / 3, v0 + 2 * (v1 - v0) / 3):
            lbox(p2, F, u0 + 0.1, u1 - 0.1, v - 0.03, v + 0.03, PROUD, PROUD + 0.03)


def walls(H: Hall) -> list[Part]:
    h, t, dw, wall = H.h, H.h["wall_t"], H.d["w"] / 2, H.h["wall"]
    part = Part("walls", "lobby_wall", col=True)
    doors = {"W": [], "E": [], "N": []}
    for _id, w, at in H.d["doors"]:
        doors[w].append((at - dw, at + dw, H.d["h"]))
    doors["N"].append((-H.a["w"] / 2, H.a["w"] / 2, H.a["h"]))
    for side, x0, x1 in (("W", h["x0"] - t, h["x0"]), ("E", h["x1"], h["x1"] + t)):
        for z0, z1, top in _cut((h["zN"], h["zS"]), doors[side]):
            part.box(x0, x1, top or 0.0, wall, z0, z1)
    for xa, xb, top in _cut((h["x0"] - t, h["x1"] + t), doors["N"]):
        part.box(xa, xb, top or 0.0, wall, h["zN"] - t, h["zN"])
    shaft = Part("pilasters", "lobby_pilaster", col=True)
    trim = Part("wall_trim", "lobby_trim")
    dark = Part("wall_dark", "lobby_dark")
    strip = Part("wall_strips", "lobby_strip")
    P = [Part("wall_panels", "lobby_panel", closed=False), Part("wall_panels2", "lobby_panel2", closed=False),
         Part("wall_panels3", "lobby_panel3", closed=False)]
    inset = Part("wall_insets", "lobby_inset", closed=False)
    pipes = Part("wall_pipes", "lobby_rib")
    lights = Part("wall_lights", "lobby_strip")
    pw = h["pilaster_w"] / 2
    pil, holes, span = wall_cuts(H)
    bay_no = 0
    for si, (side, F) in enumerate(wall_frames(H).items()):
        door_holes = [(a, b) for a, b, top in holes[side] if top < CORNICE[0]]
        for i, u in enumerate(pil[side]):
            lo, hi = u - pw, u + pw
            for a, b in door_holes:   # D1, D2: the pilaster at z 0 steps back from the door's frame (step 2b)
                if a < hi and b > lo:
                    if a > u:
                        hi = min(hi, a + 0.03)
                    else:
                        lo = max(lo, b - 0.03)
            pilaster(H, F, u, lo, hi, shaft, trim, dark, strip, wall)
            cu = u - pw - 0.22   # a vertical conduit left of every other pilaster, on brackets
            if i % 2 == 0 and cu > span[side][0] + 0.3 and not any(a - 0.2 < cu < b + 0.2 for a, b, _t in holes[side]):
                for v0, v1 in ((0.35, CORNICE[0] - 0.02), (CORNICE[1] + 0.02, FRIEZE[0])):
                    vpipe(pipes, F, cu, v0, v1, 0.2, 0.055)
                    v = v0 + 0.45
                    while v < v1 - 0.25:
                        lbox(trim, F, cu - 0.09, cu + 0.09, v - 0.045, v + 0.045, 0.0, 0.22)
                        v += 1.5
        bays = intervals(span[side], [(u - pw - 0.03, u + pw + 0.03) for u in pil[side]])
        # the frieze: a recessed channel along the wall with its lips, two conduits and blocks at varied spacing
        for a, b in bays:
            for lv0, lv1 in ((FRIEZE[0], FRIEZE[0] + 0.08), (FRIEZE[1] - 0.08, FRIEZE[1])):
                lbox(trim, F, a, b, lv0, lv1, 0.0, 0.16)
            for v in (10.05, 10.5):
                pipe(pipes, F, a, b, v, 0.12, 0.065)
        u, k = span[side][0] + 0.7, si * 2
        while u < span[side][1] - 0.4:
            if not any(p - pw - 0.25 < u < p + pw + 0.25 for p in pil[side]):
                lbox(trim, F, u - 0.09, u + 0.09, FRIEZE[0] + 0.1, FRIEZE[1] - 0.1, 0.0, 0.24)
                lbox(dark, F, u - 0.05, u + 0.05, 10.2, 10.35, 0.24, 0.255)
            u += FRIEZE_STEPS[k % len(FRIEZE_STEPS)]
            k += 1
        for b0, b1 in bays:
            bay_no += 1
            low = [(a, b) for a, b, top in holes[side] if top > 0.0]
            # the base trim, the cornice and the crown band, cut by the openings
            for a, b in intervals((b0, b1), low):
                ext(trim, F, [(0.0, 0.0), (0.0, 0.11), (0.24, 0.11), (0.3, 0.05), (0.3, 0.0)], "u", a, b)
            for a, b in intervals((b0, b1), [(a, b) for a, b, top in holes[side] if top > CORNICE[0]]):
                ext(trim, F, [(CORNICE[0], 0.0), (CORNICE[0], 0.18), (CORNICE[0] + 0.12, 0.3), (CORNICE[1] - 0.1, 0.3),
                              (CORNICE[1], 0.2), (CORNICE[1], 0.0)], "u", a, b)
            ext(trim, F, [(11.55, 0.0), (11.55, 0.24), (11.7, 0.3), (wall, 0.3), (wall, 0.0)], "u", b0, b1)
            # the panels, row by row, around the openings
            for ri, (v0, v1) in enumerate(ROWS_LOW + ROWS_HIGH):
                cuts = [(a, b) for a, b, top in holes[side] if top > v0]
                for ci, (a, b) in enumerate(intervals((b0, b1), cuts)):
                    n = max(1, math.ceil((b - a) / PANEL_MAX))
                    step = (b - a) / n
                    for kk in range(n):
                        u0, u1 = a + kk * step + GAP / 2, a + (kk + 1) * step - GAP / 2
                        if u1 - u0 < 0.35:
                            continue
                        tone = pick(u0, v0, si, 1.0)
                        if ri == 0 and kk == 0 and ci == 0 and bay_no % 3 == 1 and u1 - u0 > 1.0:
                            vent(F, u0 + 0.15, u1 - 0.15, v0 + 0.25, v1 - 0.35, trim, dark)
                            plate(P[tone], F, u0, u1, v0, v0 + 0.2, 0.0, PROUD, BEV)
                            continue
                        box = ri == 1 and kk == n - 1 and bay_no % 4 == 2 and u1 - u0 > 1.0
                        wall_panel(F, u0, u1, v0, v1, -1 if box else pick(u0, v0, si, 2.0, n=4), tone, P, inset, trim)
                        if box:   # a small service box with an amber indicator
                            lbox(trim, F, u1 - 0.75, u1 - 0.25, v0 + 0.5, v0 + 1.2, PROUD, PROUD + 0.14)
                            lbox(dark, F, u1 - 0.68, u1 - 0.32, v0 + 0.62, v0 + 0.98, PROUD + 0.14, PROUD + 0.16)
                            lbox(lights, F, u1 - 0.66, u1 - 0.6, v0 + 1.06, v0 + 1.12, PROUD + 0.14, PROUD + 0.165)
    return [part, shaft, trim, dark, strip, *P, inset, pipes, lights]


def vault(H: Hall) -> list[Part]:
    h = H.h
    shell = Part("vault_shell", "lobby_grout", closed=False)   # matte and dark: the panels' seams show no sky
    lun = Part("vault_lunettes", "lobby_vault", closed=False)
    n = 40
    xs = [h["x0"] + (h["x1"] - h["x0"]) * i / n for i in range(n + 1)]
    for xa, xb in zip(xs, xs[1:]):
        ya, yb = H.vault_y(xa), H.vault_y(xb)
        shell.face([(xa, ya, h["zN"] - h["wall_t"]), (xb, yb, h["zN"] - h["wall_t"]), (xb, yb, H.arc_z(xb)), (xa, ya, H.arc_z(xa))], (0, -1, 0))
        # the lunettes: over the north wall and over the window's head, facing the hall
        lun.face([(xa, h["wall"], h["zN"]), (xb, h["wall"], h["zN"]), (xb, yb, h["zN"]), (xa, ya, h["zN"])], (0, 0, 1))
        za, zb = H.arc_z(xa), H.arc_z(xb)
        lun.face([(xa, h["wall"], za), (xb, h["wall"], zb), (xb, yb, zb), (xa, ya, za)], (0, 0, -1))
    # the infill: light bevelled panels between the ribs in two depths, 1.5 cm seams over the dark shell
    base = Part("vault_panels", "lobby_vault", closed=False)
    inner = Part("vault_panels2", "lobby_panel3", closed=False)
    pw = h["pilaster_w"] / 2
    edges = [h["zN"]] + [z for r in h["ribs"] for z in (r - pw, r + pw)] + [None]
    cols = [h["x0"] + 2.0 * i for i in range(int((h["x1"] - h["x0"]) / 2.0) + 1)]
    F = lambda u, v, w: (u, H.vault_y(u) - w, v)   # u = x, v = z, w down from the shell
    for xa, xb in zip(cols, cols[1:]):
        for z0, z1 in zip(edges[::2], edges[1::2]):
            z1 = z1 if z1 is not None else min(H.arc_z(xa + 0.02), H.arc_z(xb - 0.02)) - 0.1
            for k in range(2):
                za, zb = z0 + (z1 - z0) * k / 2 + 0.0075, z0 + (z1 - z0) * (k + 1) / 2 - 0.0075
                plate(base, F, xa + 0.0075, xb - 0.0075, za, zb, 0.0, 0.08, 0.02)
                if zb - za > 1.2:
                    plate(inner, F, xa + 0.32, xb - 0.32, za + 0.32, zb - 0.32, 0.08, 0.12, 0.02)
    # the ribs: a broad flange over the panels' ends and the chamfered body (still hanging rib_d)
    ribs = Part("vault_ribs", "lobby_rib")
    d, c = h["rib_d"], 0.12
    for z in h["ribs"]:
        fl, body = [], []
        for x in xs:
            y = H.vault_y(x)
            fl.append([(x, y + 0.05, z - 0.62), (x, y + 0.05, z + 0.62), (x, y - 0.17, z + 0.62), (x, y - 0.17, z - 0.62)])
            body.append([(x, y - 0.1, z - pw), (x, y - 0.1, z + pw), (x, y - d + c, z + pw), (x, y - d, z + pw - c),
                         (x, y - d, z - pw + c), (x, y - d + c, z - pw)])
        ribs.loft(fl)
        ribs.loft(body)
    # a spine beam along the crown between the ribs
    spine = Part("vault_spine", "lobby_rib")
    yc = H.vault_y(0.0)
    for z0, z1 in zip(edges[::2], edges[1::2]):
        z1 = z1 if z1 is not None else H.arc_z(0.0) - 0.1
        spine.box(-0.45, 0.45, yc - 0.35, yc + 0.02, z0, z1)
    # the pendant lamps' housings (dome shades on rods; their light is step 4's, the lens is not emissive yet)
    lamps, lens = Part("vault_lamps", "lobby_trim"), Part("vault_lens", "lobby_lens", closed=False)
    px, pz, yb = PENDANTS
    for x in px:
        for z in pz:
            ytop = yc - 0.3 if abs(x) < 0.5 else H.vault_y(x) - 0.1

            def sec(r, y, x=x, z=z):
                return [(x + r * math.cos(2 * math.pi * i / 16), y, z + r * math.sin(2 * math.pi * i / 16)) for i in range(16)]

            lamps.loft([sec(0.045, ytop), sec(0.045, yb + 0.9)])
            lamps.loft([sec(0.13, yb + 0.98), sec(0.22, yb + 0.82), sec(0.34, yb + 0.62), sec(0.7, yb + 0.12),
                        sec(0.78, yb), sec(0.72, yb - 0.02)])
            lens.face(sec(0.66, yb - 0.026), (0, -1, 0))
    return [shell, lun, base, inner, ribs, spine, lamps, lens]


def window_frame(H: Hall) -> list[Part]:
    w, wall = H.w, H.h["wall"]
    parts = []
    bars = Part("window_bars", "lobby_trim", col=True)
    # the sill (top at [window] sill), its ledge 0.5 m into the hall, the transom and the head, each with depth
    for y0, y1, d0, d1 in ((0.0, w["sill"], -0.1, 0.5), (w["sill"] - 0.09, w["sill"], -0.55, 0.5),
                           (w["transom"] - w["bar_h"] / 2, w["transom"] + w["bar_h"] / 2, -0.32, 0.3),
                           (wall - w["bar_h"], wall, -0.32, 0.3)):
        secs = []
        for a in H.angles():
            (ix, iz), (ox, oz) = H.arc_pt(a, d0), H.arc_pt(a, d1)
            secs.append([(ix, y0, iz), (ox, y0, oz), (ox, y1, oz), (ix, y1, iz)])
        bars.loft(secs)
    parts.append(bars)
    mull = Part("window_mullions", "lobby_pilaster", col=True)
    half = w["mullion_w"] / 2
    for a in [-H.a0 + 2 * H.a0 * i / w["panes"] for i in range(w["panes"] + 1)]:
        for hw, r0, r1, y0, y1 in ((half, -0.3, 0.3, w["sill"], wall - w["bar_h"]),            # the mullion
                                   (0.12, -0.46, -0.3, w["sill"], wall - w["bar_h"])):        # its cap, inside
            pts = [H.arc_pt(a - hw / H.R, r0), H.arc_pt(a + hw / H.R, r0), H.arc_pt(a + hw / H.R, r1), H.arc_pt(a - hw / H.R, r1)]
            (mull if hw == half else bars).loft([[(x, y, z) for x, z in pts] for y in (y0, y1)])
    parts.append(mull)
    return parts


def window_glass(H: Hall) -> list[Part]:
    glass = Part("window_glass", "lobby_glass", closed=False, col=True)
    angs = H.angles()
    for a, b in zip(angs, angs[1:]):
        (ax, az), (bx, bz) = H.arc_pt(a, 0.05), H.arc_pt(b, 0.05)
        m = H.arc_pt((a + b) / 2)
        glass.face([(ax, H.w["sill"], az), (bx, H.w["sill"], bz), (bx, H.h["wall"] - H.w["bar_h"], bz), (ax, H.h["wall"] - H.w["bar_h"], az)],
                   (-m[0], 0, H.CZ - m[1]))
    return [glass]


def framed(F, a, h, c, bands, w_back, parts, fronts):
    """Nested chamfered frame bands round an opening (half-width a, height h, chamfer c) in a local frame, each from
    w_back to its front (stepped)."""
    d = 0.0
    for band, part, front in zip(bands, parts, fronts):
        ext(part, F, ring(chamfer_outline(a, h, c, d), chamfer_outline(a, h, c, d + band)), "w", w_back, front)
        d += band
    return chamfer_outline(a, h, c)


def hazard(part: Part, F, u0, u1, v0, v1, w, mirror: bool, period=0.6):
    """Yellow diagonal stripes on a leaf (the dark leaf shows between them); mirror turns them for chevrons."""
    rect = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    sx = -1.0 if mirror else 1.0
    lo = min(sx * u0, sx * u1) - v1
    hi = max(sx * u0, sx * u1) - v0
    k = math.floor(lo / period) - 1
    while k * period < hi + period:
        s0, s1 = k * period, k * period + period / 2
        poly = clip(clip(rect, -sx, 1.0, -s0), sx, -1.0, s1)   # s0 <= sx * u - v <= s1
        if len(poly) >= 3:
            ext(part, F, poly, "w", w, w + 0.012)
        k += 1


def door_parts(H: Hall, F, out: dict, w_back: float, slab_w: tuple[float, float], header: bool = True):
    """A sealed door facing +w at w 0 in frame F (step 2b): two hazard-striped leaves recessed in three nested stepped
    frames, a lintel box with the red lamp and an accent strip, and (header) a panel with a grille above it."""
    a, dh = H.d["w"] / 2, H.d["h"]
    framed(F, a, dh, 0.45, DOOR_BANDS, w_back, (out["trim"], out["frame"], out["trim"]), DOOR_FRONTS)
    s0, s1 = slab_w
    lbox(out["back"], F, -a - 0.05, a + 0.05, 0.0, dh + 0.05, s0 - 0.1, s0)
    for side in (-1, 1):
        u0, u1 = (-a, -0.012) if side < 0 else (0.012, a)
        lbox(out["slab"], F, u0, u1, 0.0, dh, s0, s1)
        hazard(out["hazard"], F, u0 + 0.12, u1 - 0.12, 0.14, dh - 0.14, s1, mirror=side > 0)
    big = a + sum(DOOR_BANDS)
    top = dh + sum(DOOR_BANDS)
    lbox(out["frame"], F, -big, big, top, top + 0.86, 0.0, LINTEL)                    # the lintel box
    FL = shifted(F, LINTEL)
    lh, lv = LAMP_HALF
    lamp_v = H.d["lamp"]
    lbox(out["trim"], FL, -lh, lh, lamp_v - lv, lamp_v + lv, 0.0, 0.1)
    lbox(out["lamp"], FL, -lh + 0.07, lh - 0.07, lamp_v - lv + 0.05, lamp_v + lv - 0.05, 0.1, 0.12)
    channel(FL, -0.9, 0.9, lamp_v + 0.4 - 0.035, lamp_v + 0.4 + 0.035, 0.0, out["dark"], out["strip"])
    bolts(out["trim"], FL, -big + 0.15, big - 0.15, top + 0.75, 0.0, step=0.45)
    if header:   # the wall above the door up to the panels' top row (no longer bare)
        plate(out["panel"], F, -big + 0.04, big - 0.04, top + 0.92, ROWS_LOW[-1][1], 0.0, PROUD, BEV)
        vent(shifted(F, PROUD), -0.75, 0.75, top + 1.12, ROWS_LOW[-1][1] - 0.22, out["trim"], out["dark"])


def _door_set(prefix: str, col: bool) -> dict:
    return {"trim": Part(prefix + "_frame", "lobby_trim", col=col), "frame": Part(prefix + "_frame2", "lobby_pilaster", col=col),
            "back": Part(prefix + "_back", "lobby_dark", col=col), "slab": Part(prefix + "_slab", "lobby_dark", col=col),
            "hazard": Part(prefix + "_hazard", "lobby_hazard"), "lamp": Part(prefix + "_lamp", "lobby_lamp"),
            "dark": Part(prefix + "_dark", "lobby_dark"), "strip": Part(prefix + "_strip", "lobby_strip"),
            "panel": Part(prefix + "_panel", "lobby_panel3", closed=False)}


def arch(H: Hall) -> list[Part]:
    h, a = H.h, H.a
    zN, t, w, ah, end = h["zN"], 0.3, a["w"] / 2, a["h"], h["zN"] - a["depth"]
    FN = lambda u, v, ww: (u, v, zN + ww)
    trim, frame2 = Part("arch_frame", "lobby_trim", col=True), Part("arch_frame2", "lobby_pilaster", col=True)
    dark, strip = Part("arch_dark", "lobby_dark"), Part("arch_strips", "lobby_strip")
    framed(FN, w, ah, 1.0, ARCH_BANDS, -h["wall_t"], (trim, frame2, trim), ARCH_FRONTS)
    big = w + sum(ARCH_BANDS) + 0.25
    lbox(frame2, FN, -big, big, ah + sum(ARCH_BANDS), ah + sum(ARCH_BANDS) + 0.78, 0.0, 0.45)   # the lintel box
    channel(shifted(FN, 0.45), -1.6, 1.6, ah + sum(ARCH_BANDS) + 0.35, ah + sum(ARCH_BANDS) + 0.43, 0.0, dark, strip)
    bolts(trim, shifted(FN, 0.45), -big + 0.2, big - 0.2, ah + sum(ARCH_BANDS) + 0.12, 0.0, step=0.5)
    shell = Part("corridor", "lobby_wall", col=True)
    back = zN - h["wall_t"]
    shell.box(-w - t, -w, 0.0, ah, end, back)
    shell.box(w, w + t, 0.0, ah, end, back)
    shell.box(-w - t, w + t, ah, ah + t, end - t, back)
    shell.box(-w - t, w + t, 0.0, ah, end - t, end)
    slab = Part("corridor_slab", "lobby_grout", col=True)
    slab.box(-w, w, -0.3, 0.0, end, back)
    plates = _floor_set("corridor_plates")
    floor_plates(plates, -w, w, end, back, H.h["tile"])
    # the nested portal frames down the corridor, each with two accent strips seated in channels on its jambs
    panels = Part("corridor_panels", "lobby_panel", closed=False)
    nested = [zN - 2.0, zN - 4.0, zN - 6.0]
    for zf in nested:
        F = lambda u, v, ww, zf=zf: (u, v, zf + ww)
        ext(trim, F, ring(chamfer_outline(w - 0.4, ah - 0.5, 0.9), [(-w, 0.0), (-w, ah), (w, ah), (w, 0.0)]), "w", -0.25, 0.25)
        for u in (-w + 0.2, w - 0.2):
            channel(F, u - 0.03, u + 0.03, 2.06, 3.84, 0.25, dark, strip)
    for side, x in ((-1, -w), (1, w)):
        F = lambda u, v, ww, x=x, side=side: (x - side * ww, v, u)
        for z0, z1 in zip([back] + [zf - 0.25 for zf in nested], [zf + 0.25 for zf in nested] + [end]):
            for v0, v1 in ((0.3, 2.9), (2.96, 5.6)):
                plate(panels, F, min(z0, z1) + 0.04, max(z0, z1) - 0.04, v0, v1, 0.0, 0.05, 0.03)
        ext(trim, F, [(0.0, 0.0), (0.0, 0.1), (0.22, 0.1), (0.28, 0.04), (0.28, 0.0)], "u", end, back)
    # the ceiling: ribs midway between the frames (a 1 m rhythm with them) and a light strip along its middle
    ribs = Part("corridor_ribs", "lobby_rib")
    FC = lambda u, v, ww: (u, ah - ww, v)   # u = x, v = z, w down from the ceiling
    z = back - 0.5
    while z > end + 0.3:
        if all(abs(z - zf) > 0.6 for zf in nested):
            lbox(ribs, FC, -w, w, z - 0.1, z + 0.1, 0.0, 0.22)
        z -= 1.0
    channel(FC, -0.05, 0.05, end + 0.4, back - 0.1, 0.0, dark, strip)
    # the shut door at the end, hazard-striped like the hall's, facing the hall
    out = _door_set("corridor_door", True)
    door_parts(H, lambda u, v, ww: (u, v, end + ww), out, 0.0, (0.1, 0.2), header=False)
    return [trim, frame2, dark, strip, shell, slab, *plates, panels, ribs, *out.values()]


def door(H: Hall) -> list[Part]:
    """A sealed door in its opening, facing +z (the hall); the wall's inner face at z 0, its outer at -wall_t."""
    out = _door_set("door", True)
    door_parts(H, lambda u, v, w: (u, v, w), out, -H.h["wall_t"], (-0.42, -0.27))
    return list(out.values())


BUILDERS = {"floor": floor, "walls": walls, "vault": vault, "window_frame": window_frame,
            "window_glass": window_glass, "arch": arch, "door": door}


# --- Blender -------------------------------------------------------------------------------------------------------
def clear() -> None:
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials):
        for item in list(coll):
            coll.remove(item)


LOOK: dict = {}   # "mats": the scheme's materials by name (tools/runner/lobby_layout.look_materials)


def material(name: str):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    if name in LOOK["mats"]:
        spec = LOOK["mats"][name]
        rgba = (*[c ** 2.2 for c in spec["rgb"]], 1.0)
        rough, metallic, emit = spec["roughness"], spec["metallic"], spec["emit"]
    else:
        rgba, rough, metallic, emit = MATS[name]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    if emit:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emit
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
    if part.closed:   # every face carries its outward hint (Part.face); merged parts are never recalculated
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material(part.mat))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def merged(pid: str, parts: list[Part], collide: bool) -> list[tuple[Part, bool]]:
    """One object per material and collision: fewer draw calls."""
    groups: dict = {}
    for p in parts:
        if not p.faces:
            continue
        col = collide and p.col
        key = (p.mat, col)
        if key not in groups:
            groups[key] = Part(f"{pid}_{p.mat.removeprefix('lobby_')}" + ("_c" if col else ""), p.mat, closed=True)
            groups[key].closed = False
        g = groups[key]
        base = len(g.verts)
        g.verts += p.verts
        g.faces += [[i + base for i in f] for f in p.faces]
    return [(g, col) for (_m, col), g in groups.items()]


def build(piece: dict, H: Hall, out: Path) -> dict:
    clear()
    parts = BUILDERS[piece["id"]](H)
    objs = [make(p, col) for p, col in merged(piece["id"], parts, piece.get("collide", False))]
    glb = out / f"{piece['id']}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), **EXPORT)
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    return {"glb": glb.as_posix(), "triangles": sum(len(pl.vertices) - 2 for o in objs for pl in o.data.polygons),
            "objects": [o.name for o in objs], "materials": sorted({p.mat for p in parts if p.faces}),
            "bounds": {"min": [lo[0], lo[2], -hi[1]], "max": [hi[0], hi[2], -lo[1]]}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    req = json.loads(Path(argv[argv.index("--request") + 1]).read_text(encoding="utf-8"))
    out = Path(argv[argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)
    LOOK["mats"] = req["look"]
    H = Hall(req)
    report = {"pieces": {}}
    for piece in req["layout"]["pieces"]:
        report["pieces"][piece["id"]] = build(piece, H, out)
        print(f"LOBBY built {piece['id']}: {report['pieces'][piece['id']]['triangles']} triangles")
    (out / "build_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print(f"LOBBY done {len(report['pieces'])} pieces")


if __name__ == "__main__":
    main()
