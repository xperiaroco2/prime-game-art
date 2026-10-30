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
import numpy as np

EXPORT = {"export_format": "GLB", "use_selection": False, "use_visible": False, "use_renderable": False,
          "use_active_collection": False, "export_yup": True, "export_apply": True, "export_skins": False,
          "export_animations": False, "export_morph": False, "export_cameras": False, "export_lights": False,
          "export_materials": "EXPORT", "export_texcoords": True, "export_normals": True,
          "export_tangents": True}
# The fixed materials (linear colour, roughness, metallic, emission strength), the same in every scheme; the others
# (panels, frames, trim, floor, the strips and the ring) come resolved from the layout's [look] scheme (req["look"]).
MATS = {"lobby_grout": ((0.010, 0.010, 0.012, 1), 0.55, 0.3, 0.0),
        "lobby_dark": ((0.018, 0.018, 0.020, 1), 0.5, 0.4, 0.0),
        "lobby_lamp": ((1.0, 0.015, 0.008, 1), 0.4, 0.0, 2.6),
        "lobby_lens": ((0.8, 0.76, 0.66, 1), 0.25, 0.0, 0.0),
        "lobby_hazard": ((0.78, 0.48, 0.015, 1), 0.5, 0.1, 0.0),
        "lobby_signal": ((0.42, 0.018, 0.012, 1), 0.42, 0.15, 0.0),   # the fire point's red paint (step 2c)
        "lobby_reflector": ((0.62, 0.62, 0.6, 1), 0.3, 0.9, 0.0),     # the pendant shades' insides (step 2c)
        "lobby_worn": ((0.30, 0.31, 0.31, 1), 0.36, 0.85, 0.0),       # bare steel on the worn edges (step 3)
        "lobby_glass": ((0.45, 0.6, 0.8, 0.12), 0.05, 0.0, 0.0)}
ARC_STEP_DEG = 2.0
# Step 2c: the fine metal surface in the GLBs' own materials: one shared tiling pair of maps (a brushed micro-normal
# with fine scratches; occlusion 1, a roughness multiplier, metallic 1), box-projected UVs, each 2 m cell offset and
# its brushing turned by a steady hash (per-plate variation). The materials scale them by their own numbers.
TEX_SIZE, TEX_M = 1024, 1.5                               # pixels, metres per repeat
NORMAL_STRENGTH = {"lobby_floor": 0.1, "lobby_floor2": 0.1, "lobby_floor3": 0.1}   # the floor stays clean
PLAIN = {"lobby_glass", "lobby_lens", "lobby_lamp", "lobby_strip", "lobby_ring"}       # no metal maps
# Step 3, light wear: every mapped material's colour times a shared grime map (soft blotches and specks, 0.86-1); the
# scuff map (rubbed patches, scratches) instead on the hazard stripes, the floor before the doors and the worn edges;
# a blotchier roughness map on the copper. About WEAR_SHARE of the narrow faces (bevels, chamfers, lips, edges under
# WEAR_W wide) of the WEARABLE materials turn into lobby_worn: the paint rubbed off the exposed edges.
SCUFFED = {"lobby_hazard", "lobby_floor_worn", "lobby_worn"}
ROUGH2 = {"lobby_trim"}
WEARABLE = {"lobby_metal", "lobby_pilaster", "lobby_hazard"}
WEAR_W, WEAR_SHARE = 0.06, 55
IMG: dict = {}


# --- parts ---------------------------------------------------------------------------------------------------------
class Part:
    def __init__(self, name: str, mat: str, closed: bool = True, col: bool = False):
        self.name, self.mat, self.closed, self.col = name, mat, closed, col
        self.smooth = False   # smooth shading (step 3: the pendants), sharp edges kept over 35 deg
        self.flags: list[bool] = []
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


def plate(part: "Part", F, u0, u1, v0, v1, w0, w1, bev, bev_v=None):
    """A bevelled plate on a local wall (front at w1, inset by bev, in v by bev_v if given; open at the back)."""
    bv = bev if bev_v is None else bev_v
    front = [F(u0 + bev, v0 + bv, w1), F(u1 - bev, v0 + bv, w1), F(u1 - bev, v1 - bv, w1), F(u0 + bev, v1 - bv, w1)]
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


def sweep(part: Part, poly, frames):
    """A 2D profile (any winding, may be concave) swept along frames [(origin, a_dir, b_dir)] (lobby frame), capped;
    each face's hint is the profile edge's outward normal (a loft's centre hints fail on concave profiles)."""
    n = len(poly)
    sgn = 1 if sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) > 0 else -1
    secs = [[tuple(o[k] + p[0] * A[k] + p[1] * B[k] for k in range(3)) for p in poly] for o, A, B in frames]
    for s in range(len(secs) - 1):
        _o, A, B = frames[s]
        for i in range(n):
            j = (i + 1) % n
            (ax, ay), (bx, by) = poly[i], poly[j]
            nx, ny = sgn * (by - ay), -sgn * (bx - ax)
            part.face([secs[s][i], secs[s][j], secs[s + 1][j], secs[s + 1][i]], [nx * A[k] + ny * B[k] for k in range(3)])
    part.face(secs[0], [frames[0][0][k] - frames[1][0][k] for k in range(3)])
    part.face(secs[-1], [frames[-1][0][k] - frames[-2][0][k] for k in range(3)])


def revolve(part: Part, x, z, profile, n=16):
    """A surface of revolution about the vertical axis at (x, z) from a profile [(r, y)]; each face faces the profile's
    left side (walk the profile with the outside on its left: out and down the outside, back up the inside)."""
    for i in range(n):
        a, b = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        am = (a + b) / 2
        for (r0, y0), (r1, y1) in zip(profile, profile[1:]):
            nr, ny = -(y1 - y0), (r1 - r0)
            part.face([(x + r0 * math.cos(a), y0, z + r0 * math.sin(a)), (x + r1 * math.cos(a), y1, z + r1 * math.sin(a)),
                       (x + r1 * math.cos(b), y1, z + r1 * math.sin(b)), (x + r0 * math.cos(b), y0, z + r0 * math.sin(b))],
                      (math.cos(am) * nr, ny, math.sin(am) * nr))


def disc(part: Part, x, z, r, y, up: bool, n=16):
    part.face([(x + r * math.cos(2 * math.pi * i / n), y, z + r * math.sin(2 * math.pi * i / n)) for i in range(n)],
              (0, 1 if up else -1, 0))


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
MID_BAND = (4.56, 4.76)                                  # a pilaster's mid-height band (on the panels' row seam)
PENDANT_N, PENDANT_DY = 40, (-0.7, 0.0, 0.6)             # step 3: the shades' segments, their heights' steps
# step 3, the floor: a flush bolt head in each plate's corners (BOLT_IN from the edges), service plates where
# pick(x, z, 13.0, n=SERVICE_N) is 0, the plates within WORN_R of a door's or the arch's middle mostly scuffed, a
# yellow keep-clear box before each door (KEEP: half-width, depth from the wall, start past the pilasters' plinths)
BOLT_IN, BOLT_R, SERVICE_N, WORN_R = 0.1, 0.022, 29, 3.4
KEEP = (1.9, 2.5, 0.75)
RING_W = (0.5, 0.36, 0.02)   # the ring's metal band half-width, its copper inlays' offset from r, their half-width
# Step 2c: one unique detail per chosen bay (wall, bay index from the wall's low end), none twice on a wall
GREEBLES = {("W", 1): "service", ("W", 2): "tray", ("W", 3): "pipes", ("W", 4): "fire",
            ("E", 0): "pipes", ("E", 1): "fire", ("E", 3): "tray", ("E", 4): "service"}


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


def floor_plates(parts: list, x0, x1, z0, z1, g, zmax=None, y=0.015, gap=0.006, bev=0.02, extra=None):
    """2 m plates with fine seams and bevelled edges (front at y) in three tones, clipped at zmax(x) (the arc).
    extra (step 3): {"bolts", "service", "dark", "near"}: the bolts, the service plates, their slots, near(x, z)."""
    F = lambda u, v, w: (u, w, v)   # u = x, v = z, w = up
    x = x0
    while x < x1 - 1e-6:
        z = z0
        while z < z1 - 1e-6:
            xa, xb, za, zb = x + gap, min(x + g, x1) - gap, z + gap, min(z + g, z1) - gap
            if zmax is not None:
                zb = min(zb, zmax(xa) - gap, zmax(xb) - gap)
            if zb - za > 1.9 and xb - xa > 1.9 and extra and pick(x, z, 13.0, n=SERVICE_N) == 0:
                plate(extra["service"], F, xa, xb, za, zb, 0.0, y - 0.004, bev)   # a service plate: a slot, 8 bolts
                lbox(extra["dark"], F, xa + 0.85, xb - 0.85, za + 0.12, za + 0.2, y - 0.0045, y - 0.003)
                for bx in (xa + 0.08, (xa + xb) / 2, xb - 0.08):
                    for bz in (za + 0.08, (za + zb) / 2, zb - 0.08):
                        if (bx, bz) != ((xa + xb) / 2, (za + zb) / 2):
                            disc(extra["bolts"], bx, bz, BOLT_R, y - 0.002, up=True, n=6)
            elif zb - za > 0.15:
                tone = parts[pick(x, z, 7.0)]
                if extra and extra["near"]((xa + xb) / 2, (za + zb) / 2) and pick(x, z, 17.0, n=10) < 8:
                    tone = parts[3]
                plate(tone, F, xa, xb, za, zb, 0.0, y, bev)
                if extra:
                    for bx in (xa + BOLT_IN, xb - BOLT_IN):
                        for bz in (za + BOLT_IN, zb - BOLT_IN):
                            disc(extra["bolts"], bx, bz, BOLT_R, y + 0.0015, up=True, n=6)
            z += g
        x += g


def _floor_set(prefix: str) -> list:
    return [Part(prefix, "lobby_floor", closed=False), Part(prefix + "2", "lobby_floor2", closed=False),
            Part(prefix + "3", "lobby_floor3", closed=False), Part(prefix + "_worn", "lobby_floor_worn", closed=False)]


def door_spots(H: "Hall") -> list:
    """Each door's (wall, at, the middle of its foot on the wall's face (x, z)) and the arch's ("A")."""
    h = H.h
    out = []
    for _id, wall, at in H.d["doors"]:
        out.append((wall, at, (h["x0"], at) if wall == "W" else (h["x1"], at) if wall == "E" else (at, h["zN"])))
    return out + [("A", 0.0, (0.0, h["zN"]))]


def markings(H: "Hall", paint: Part) -> None:
    """Step 3: a yellow keep-clear box on the floor before each door: two side lines, a front line and a hatched band
    inside the front line (hazard()'s stripes, 12 mm proud)."""
    h, (a, d, s) = H.h, KEEP
    for wall, at, _foot in door_spots(H):
        if wall == "A":
            continue
        F = ((lambda u, v, w, at=at: (at + u, w, h["zN"] + v)) if wall == "N" else
             (lambda u, v, w, at=at: (h["x0"] + v, w, at - u)) if wall == "W" else
             (lambda u, v, w, at=at: (h["x1"] - v, w, at + u)))
        for u0, u1, v0, v1 in ((-a, a, d - 0.1, d), (-a, -a + 0.1, s, d), (a - 0.1, a, s, d)):
            lbox(paint, F, u0, u1, v0, v1, 0.015, 0.018)
        hazard(paint, F, -a + 0.1, a - 0.1, d - 0.5, d - 0.1, 0.015, mirror=False, period=0.5)


def floor(H: Hall) -> list[Part]:
    h, t = H.h, H.h["wall_t"]
    slab = Part("floor_slab", "lobby_grout", col=True)
    arc = [H.arc_pt(a) for a in reversed(H.angles())]   # east to west
    prism(slab, [(h["x0"] - t, h["zN"] - t), (h["x1"] + t, h["zN"] - t), (h["x1"] + t, h["zS"]), *arc,
                 (h["x0"] - t, h["zS"])], -0.3, 0.0)
    plates = _floor_set("floor_plates")
    spots = [foot for _w, _at, foot in door_spots(H)]
    extra = {"bolts": Part("floor_bolts", "lobby_metal", closed=False),
             "service": Part("floor_service", "lobby_metal", closed=False),
             "dark": Part("floor_slots", "lobby_grout", closed=False),
             "near": lambda x, z: any(math.hypot(x - fx, z - fz) < WORN_R for fx, fz in spots)}
    floor_plates(plates, h["x0"], h["x1"], h["zN"], h["zS"] + h["bulge"], h["tile"], zmax=H.arc_z, extra=extra)
    paint = Part("floor_marks", "lobby_hazard", closed=False)
    markings(H, paint)
    # the ring (step 3: wider): a metal band with two copper inlays round the accent line, dark seams at its edges
    parts = [slab, *plates, extra["bolts"], extra["service"], extra["dark"], paint]
    rr, n = H.L["floor"]["ring_r"], 200
    bw, ci, cw = RING_W
    for name, mat, r0, r1, y in (("floor_ring_seam", "lobby_grout", rr - bw - 0.03, rr + bw + 0.03, 0.0158),
                                 ("floor_ring_band", "lobby_metal", rr - bw, rr + bw, 0.0165),
                                 ("floor_ring_inlay", "lobby_trim", rr - ci - cw, rr - ci + cw, 0.018),
                                 ("floor_ring_inlay2", "lobby_trim", rr + ci - cw, rr + ci + cw, 0.018),
                                 ("floor_ring_channel", "lobby_grout", rr - 0.1, rr + 0.1, 0.018),
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


def pilaster(H: Hall, F, u, lo, hi, shaft: Part, trim: Part, dark: Part, strip: Part, top: float, metal: Part):
    """A pilaster at u; below the cornice only lo..hi (narrowed beside a door's frame, step 2b)."""
    pw, pd, c = H.h["pilaster_w"] / 2, H.h["pilaster_d"], 0.12

    def prof(a, b):
        return [(a, 0.0), (b, 0.0), (b, pd - c), (b - c, pd), (a + c, pd), (a, pd - c)]

    l2 = lo - 0.08 if lo <= u - pw + 1e-6 else lo
    h2 = hi + 0.08 if hi >= u + pw - 1e-6 else hi
    # the chamfered base (step 2c): a plinth with cut corners and a sloped top into the shaft
    pp = pd + 0.1
    base = [(l2, 0.0), (h2, 0.0), (h2, pp - 0.1), (h2 - 0.1, pp), (l2 + 0.1, pp), (l2, pp - 0.1)]
    ext(metal, F, base, "v", 0.0, 0.4)   # step 3: the base in the dark metal with a thin copper band on top
    e = 0.012
    ext(trim, F, [(l2 - e, 0.0), (h2 + e, 0.0), (h2 + e, pp - 0.1), (h2 - 0.1 + e * 0.4, pp + e), (l2 + 0.1 - e * 0.4, pp + e),
                  (l2 - e, pp - 0.1)], "v", 0.355, 0.385)
    shaft.loft([[F(*_L("v", q, 0.4)) for q in base], [F(*_L("v", q, 0.62)) for q in prof(lo, hi)]])
    ext(shaft, F, prof(lo, hi), "v", 0.62, CORNICE[0])
    ext(shaft, F, prof(u - pw, u + pw), "v", CORNICE[0], top - 0.6)
    mb0, mb1 = MID_BAND   # the mid-height band: a human-sized step on the tall shaft
    ext(trim, F, [(mb0, 0.0), (mb0, pd + 0.03), (mb0 + 0.04, pd + 0.07), (mb1 - 0.04, pd + 0.07), (mb1, pd + 0.03),
                  (mb1, 0.0)], "u", lo - 0.04, hi + 0.04)
    # cover strips over the joints to the panels (the light seam beside the pilaster), not beside a door's frame
    for a, b, free in ((lo - 0.09, lo, lo <= u - pw + 1e-6), (hi, hi + 0.09, hi >= u + pw - 1e-6)):
        if free:
            lbox(shaft, F, a, b, 0.4, CORNICE[0], 0.0, PROUD + 0.025)
    for a, b in ((u - pw - 0.09, u - pw), (u + pw, u + pw + 0.09)):
        lbox(shaft, F, a, b, CORNICE[1], top - 0.6, 0.0, PROUD + 0.025)
    lbox(metal, F, u - pw - 0.06, u + pw + 0.06, top - 0.6, top, 0.0, pd + 0.1)        # the capital
    lbox(trim, F, u - pw - 0.07, u + pw + 0.07, top - 0.6, top - 0.57, 0.0, pd + 0.11)  # its copper lip
    lbox(trim, F, u - pw - 0.03, u + pw + 0.03, CORNICE[0], CORNICE[1], 0.0, pd + 0.05)  # the band at the cornice
    m = (lo + hi) / 2
    channel(F, m - 0.04, m + 0.04, STRIP[0], STRIP[1], pd, dark, strip)
    lbox(metal, F, m - 0.16, m + 0.16, 4.8, 6.9, pd, pd + 0.03)                        # a bolted face plate
    for v in (4.95, 6.75):
        bolts(metal, F, m - 0.1, m + 0.1, v, pd + 0.03, step=0.2)
    lbox(metal, F, u - pw + 0.1, u + pw - 0.1, 8.4, 10.6, pd, pd + 0.03)


def vent(F, u0, u1, v0, v1, trim: Part, dark: Part):
    lbox(dark, F, u0, u1, v0, v1, 0.0, 0.02)
    for side in ((u0, u0 + 0.08, v0, v1), (u1 - 0.08, u1, v0, v1), (u0, u1, v0, v0 + 0.08), (u0, u1, v1 - 0.08, v1)):
        lbox(trim, F, side[0], side[1], side[2], side[3], 0.0, 0.1)
    v = v0 + 0.16
    while v < v1 - 0.16:
        ext(trim, F, [(v, 0.02), (v + 0.05, 0.02), (v + 0.1, 0.08), (v + 0.05, 0.08)], "u", u0 + 0.08, u1 - 0.08)
        v += 0.14


def greeble(kind, F, b0, b1, c, P, trim, dark, shaft, pipes, lights, signal):
    """One bay's unique detail centred at u c (step 2c): a service hatch, a pipe junction with a valve, a fire point
    with a terminal, or a cable tray broken by a junction box."""
    w0 = PROUD
    if kind == "service":
        u0, u1, v0, v1 = c - 0.8, c + 0.8, 0.6, 4.3
        lbox(dark, F, u0, u1, v0, v1, w0, w0 + 0.02)
        for a in ((u0, u1, v0, v0 + 0.1), (u0, u1, v1 - 0.1, v1), (u0, u0 + 0.1, v0 + 0.1, v1 - 0.1),
                  (u1 - 0.1, u1, v0 + 0.1, v1 - 0.1)):
            lbox(trim, F, a[0], a[1], a[2], a[3], w0, w0 + 0.09)
        plate(P[2], F, u0 + 0.13, u1 - 0.13, v0 + 0.13, v1 - 0.13, w0 + 0.02, w0 + 0.07, 0.02)
        plate(P[0], F, u0 + 0.35, u1 - 0.35, v0 + 0.5, v0 + 1.6, w0 + 0.07, w0 + 0.1, 0.015)
        for v in (v0 + 0.55, v1 - 0.55):   # hinges
            lbox(shaft, F, u0 + 0.05, u0 + 0.2, v - 0.18, v + 0.18, w0 + 0.07, w0 + 0.13)
        lbox(trim, F, u1 - 0.33, u1 - 0.25, (v0 + v1) / 2 - 0.3, (v0 + v1) / 2 + 0.3, w0 + 0.07, w0 + 0.15)   # handle
        lbox(P[1], F, c - 0.32, c + 0.32, v1 - 0.6, v1 - 0.32, w0 + 0.07, w0 + 0.09)   # the label plate, its lines
        for v in (v1 - 0.43, v1 - 0.5):
            lbox(dark, F, c - 0.25, c + 0.2, v - 0.015, v + 0.015, w0 + 0.09, w0 + 0.096)
        bolts(trim, F, u0 + 0.05, u1 - 0.05, v0 + 0.05, w0 + 0.09, step=0.4)
        bolts(trim, F, u0 + 0.05, u1 - 0.05, v1 - 0.05, w0 + 0.09, step=0.4)
    elif kind == "pipes":
        for du in (-0.35, 0.35):   # two risers with copper flanges into a valve box
            vpipe(pipes, F, c + du, 0.35, 1.62, 0.26, 0.09)
            for v in (0.52, 1.0, 1.5):
                vpipe(trim, F, c + du, v, v + 0.07, 0.26, 0.125)
        plate(shaft, F, c - 0.6, c + 0.6, 1.6, 2.45, w0, 0.46, 0.04)
        plate(trim, F, c - 0.5, c + 0.5, 1.7, 2.35, 0.46, 0.48, 0.01)
        vpipe(pipes, F, c, 2.43, CORNICE[0] - 0.02, 0.26, 0.07)   # the riser up to the cornice
        for v in (2.5, 4.62, 6.9):
            vpipe(trim, F, c, v, v + 0.07, 0.26, 0.1)
        cv, r0, r1 = 2.02, 0.17, 0.21   # the valve wheel: a rim of 12 segments, two spokes, a hub
        for k in range(12):
            a, b = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
            ext(signal, F, [(c + r0 * math.cos(a), cv + r0 * math.sin(a)), (c + r1 * math.cos(a), cv + r1 * math.sin(a)),
                            (c + r1 * math.cos(b), cv + r1 * math.sin(b)), (c + r0 * math.cos(b), cv + r0 * math.sin(b))],
                "w", 0.56, 0.6)
        lbox(signal, F, c - r0, c + r0, cv - 0.015, cv + 0.015, 0.56, 0.59)
        lbox(signal, F, c - 0.015, c + 0.015, cv - r0, cv + r0, 0.56, 0.59)
        lbox(trim, F, c - 0.04, c + 0.04, cv - 0.04, cv + 0.04, 0.48, 0.62)
        pipe(pipes, F, c + 0.6, c + 1.5, 2.02, 0.26, 0.07)   # a branch into the wall beside the box
        lbox(trim, F, c + 1.5, c + 1.62, 1.86, 2.18, w0, 0.36)
    elif kind == "fire":
        plate(signal, F, c - 0.45, c + 0.45, 1.0, 2.3, w0, w0 + 0.24, 0.03)
        plate(dark, F, c - 0.36, c + 0.36, 1.32, 2.2, w0 + 0.24, w0 + 0.26, 0.012)
        lbox(trim, F, c + 0.27, c + 0.32, 1.55, 1.95, w0 + 0.26, w0 + 0.32)
        lbox(lights, F, c - 0.3, c + 0.3, 2.62, 2.66, w0 + 0.03, w0 + 0.045)
        plate(signal, F, c - 0.32, c + 0.32, 2.45, 2.82, w0, w0 + 0.03, 0.01)   # the sign over it
        plate(shaft, F, c + 0.62, c + 1.12, 1.15, 1.95, w0, w0 + 0.12, 0.02)   # the terminal beside it
        lbox(dark, F, c + 0.68, c + 1.06, 1.55, 1.88, w0 + 0.12, w0 + 0.13)
        for k in range(3):
            lbox(trim, F, c + 0.7 + k * 0.12, c + 0.78 + k * 0.12, 1.24, 1.32, w0 + 0.12, w0 + 0.14)
    elif kind == "tray":
        v, ua, ub = 6.75, b0 + 0.3, b1 - 0.45
        for a, b in ((ua, c - 0.42), (c + 0.42, ub)):   # the tray, broken at the box
            lbox(trim, F, a, b, v - 0.12, v - 0.1, 0.12, 0.44)
            for ww in (0.12, 0.42):
                lbox(trim, F, a, b, v - 0.12, v + 0.04, ww, ww + 0.02)
            for ww in (0.2, 0.27, 0.34):
                pipe(pipes, F, a, b, v - 0.06, ww, 0.03)
        u = ua + 0.25
        while u < ub:
            if abs(u - c) > 0.6:
                lbox(shaft, F, u - 0.03, u + 0.03, v - 0.22, v - 0.12, 0.0, 0.44)
            u += 1.2
        plate(shaft, F, c - 0.36, c + 0.36, v - 1.15, v - 0.32, w0, 0.46, 0.03)
        plate(P[1], F, c - 0.24, c + 0.24, v - 1.0, v - 0.6, 0.46, 0.475, 0.01)
        for k, ww in enumerate((0.2, 0.27, 0.34)):   # the cables drop from the tray's broken ends into the box
            for side in (-1, 1):
                uc = c + side * (0.37 - 0.04 * k)
                vpipe(pipes, F, uc, v - 0.34, v - 0.06, ww, 0.03)
                pipe(pipes, F, min(uc, c + side * 0.42), max(uc, c + side * 0.42), v - 0.06, ww, 0.03)


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
    metal = Part("wall_metal", "lobby_metal")
    dark = Part("wall_dark", "lobby_dark")
    strip = Part("wall_strips", "lobby_strip")
    P = [Part("wall_panels", "lobby_panel", closed=False), Part("wall_panels2", "lobby_panel2", closed=False),
         Part("wall_panels3", "lobby_panel3", closed=False)]
    inset = Part("wall_insets", "lobby_inset", closed=False)
    pipes = Part("wall_pipes", "lobby_rib")
    lights = Part("wall_lights", "lobby_strip")
    signal = Part("wall_signal", "lobby_signal")
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
            pilaster(H, F, u, lo, hi, shaft, trim, dark, strip, wall, metal)
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
        for bi, (b0, b1) in enumerate(bays):
            bay_no += 1
            kind = GREEBLES.get((side, bi))
            if kind:
                greeble(kind, F, b0, b1, b0 + 0.6 * (b1 - b0), P, trim, dark, shaft, pipes, lights, signal)
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
                        box = ri == 1 and kk == n - 1 and bay_no % 4 == 2 and u1 - u0 > 1.0 and not kind
                        wall_panel(F, u0, u1, v0, v1, -1 if box else pick(u0, v0, si, 2.0, n=4), tone, P, inset, trim)
                        if box:   # a small service box with an amber indicator
                            lbox(trim, F, u1 - 0.75, u1 - 0.25, v0 + 0.5, v0 + 1.2, PROUD, PROUD + 0.14)
                            lbox(dark, F, u1 - 0.68, u1 - 0.32, v0 + 0.62, v0 + 0.98, PROUD + 0.14, PROUD + 0.16)
                            lbox(lights, F, u1 - 0.66, u1 - 0.6, v0 + 1.06, v0 + 1.12, PROUD + 0.14, PROUD + 0.165)
    return [part, shaft, trim, metal, dark, strip, *P, inset, pipes, lights, signal]


def lunette_column(H: Hall, A, B, inn, yb, band: bool, parts: dict, xa) -> None:
    """One 2 m column of a lunette (step 2c): bevelled panels in rows up to the vault's curve (their tops follow it),
    a batten on its west seam, a trim along the curve and (band) a band over the window's head. A, B: the column's
    ends (x, z) on the lunette; inn: the unit direction into the hall."""
    L = math.hypot(B[0] - A[0], B[1] - A[1])
    d = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
    yt0, yt1 = H.vault_y(A[0]) - 0.22, H.vault_y(B[0]) - 0.22

    def xz(u, w):
        return A[0] + d[0] * u + inn[0] * w, A[1] + d[1] * u + inn[1] * w

    def Fb(u, v, w):   # plain: v is the height
        x, z = xz(u, w)
        return x, v, z

    def Fs(u, v, w):   # sheared: v from the curve's line
        x, z = xz(u, w)
        return x, yt0 + (yt1 - yt0) * u / L + v, z

    def Fl(u, v, w):   # v from 0 (yb) to 1 (the curve's line)
        x, z = xz(u, w)
        return x, yb + v * (yt0 + (yt1 - yt0) * u / L - yb), z

    wall = H.h["wall"]
    if band:
        ext(parts["trim"], Fb, [(wall, 0.0), (wall, 0.36), (wall + 0.06, 0.42), (wall + 0.3, 0.42), (wall + 0.36, 0.34),
                                (wall + 0.36, 0.0)], "u", 0.0, L)
    hm = max(yt0, yt1) - yb
    if min(yt0, yt1) - yb < 0.3:
        return
    # step 3: the rows hang from the curve at a steady 1.7 m (their seams parallel to it and level with the next
    # column's); the last row fills down to yb
    g, k = 0.0075, 0
    while True:
        t0, t1 = yt0 - 1.7 * k, yt1 - 1.7 * k
        b0, b1 = t0 - 1.7, t1 - 1.7
        last = min(b0, b1) - yb < 0.6
        if last:
            b0 = b1 = yb
        if min(t0, t1) - yb < 0.3:
            break

        def Fr(u, v, w, t0=t0, t1=t1, b0=b0, b1=b1):
            x, z = xz(u, w)
            bb, tt = b0 + (b1 - b0) * u / L, t0 + (t1 - t0) * u / L
            return x, bb + v * (tt - bb), z

        hr = min(t0 - b0, t1 - b1)
        part = parts["base"] if pick(xa, k, 3.0, n=2) == 0 else parts["inner"]
        plate(part, Fr, g, L - g, g / hr, 1.0 - g / hr, 0.0, 0.07, 0.02, bev_v=0.02 / hr)
        if last:
            break
        k += 1

    plate(parts["battens"], Fl, -0.035, 0.035, 0.0, 1.0, 0.0, 0.085, 0.008, bev_v=0.008 / hm)
    lbox(parts["trim"], Fs, 0.0, L, -0.04, 0.3, 0.0, 0.12)


def vault(H: Hall) -> list[Part]:
    h = H.h
    shell = Part("vault_shell", "lobby_grout", closed=False)   # matte and dark: the panels' seams show no sky
    lun = Part("vault_lunettes", "lobby_grout", closed=False)   # dark behind their panelling (step 2c)
    n = 40
    xs = [h["x0"] + (h["x1"] - h["x0"]) * i / n for i in range(n + 1)]
    for xa, xb in zip(xs, xs[1:]):
        ya, yb = H.vault_y(xa), H.vault_y(xb)
        shell.face([(xa, ya, h["zN"] - h["wall_t"]), (xb, yb, h["zN"] - h["wall_t"]), (xb, yb, H.arc_z(xb)), (xa, ya, H.arc_z(xa))], (0, -1, 0))
        # the lunettes: over the north wall and over the window's head, facing the hall
        lun.face([(xa, h["wall"], h["zN"]), (xb, h["wall"], h["zN"]), (xb, yb, h["zN"]), (xa, ya, h["zN"])], (0, 0, 1))
        za, zb = H.arc_z(xa), H.arc_z(xb)
        lun.face([(xa, h["wall"], za), (xb, h["wall"], zb), (xb, yb, zb), (xa, ya, za)], (0, 0, -1))
    # the infill: light bevelled panels between the ribs in two depths, their 1.5 cm seams under dark battens
    base = Part("vault_panels", "lobby_vault", closed=False)
    inner = Part("vault_panels2", "lobby_panel3", closed=False)
    battens = Part("vault_battens", "lobby_rib", closed=False)   # dark battens over the seams: no bright hairlines
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
                if k == 1:   # a batten over the seam between the span's two panels
                    plate(battens, F, xa, xb, za - 0.045, za + 0.03, 0.0, 0.092, 0.008)
            if xb < h["x1"] - 1e-6:   # and over the seam between this column and the next
                plate(battens, F, xb - 0.035, xb + 0.035, z0, z1, 0.0, 0.092, 0.008)
    # the lunettes' panelling (step 2c): over the north wall and over the window's head, 2 m columns like the vault's
    lparts = {"base": base, "inner": inner, "battens": battens, "trim": Part("vault_trim", "lobby_trim")}
    for xa, xb in zip(cols, cols[1:]):
        lunette_column(H, (xa, h["zN"]), (xb, h["zN"]), (0.0, 1.0), h["wall"] + 0.02, False, lparts, xa)
        mx = (xa + xb) / 2
        mz = H.arc_z(mx)
        rr = math.hypot(mx, mz - H.CZ)
        lunette_column(H, (xa, H.arc_z(xa)), (xb, H.arc_z(xb)), (-mx / rr, (H.CZ - mz) / rr), h["wall"] + 0.36, True,
                       lparts, xa)
    # the ribs (step 2c): an I-section (a broad top flange over the panels' ends, a web, a chamfered bottom flange,
    # still hanging rib_d), copper collars near the walls and a corbel from each pilaster's capital up under the rib
    ribs = Part("vault_ribs", "lobby_rib")
    d, cf, wb = h["rib_d"], 0.05, h["rib_d"] - 0.16
    prof = [(-0.62, 0.05), (0.62, 0.05), (0.62, -0.14), (0.2, -0.14), (0.2, -wb), (pw, -wb), (pw, -(d - cf)),
            (pw - cf, -d), (-pw + cf, -d), (-pw, -(d - cf)), (-pw, -wb), (-0.2, -wb), (-0.2, -0.14), (-0.62, -0.14)]
    collar = [(-pw - 0.05, -0.12), (pw + 0.05, -0.12), (pw + 0.05, -d - 0.04), (-pw - 0.05, -d - 0.04)]
    top, pd = h["wall"], h["pilaster_d"]
    corbel = [(top - 0.6, 0.0), (top - 0.6, pd + 0.1), (top - 0.08, pd + 0.6), (top + 0.1, pd + 0.6), (top + 0.1, 0.0)]
    for z in h["ribs"]:
        sweep(ribs, prof, [((x, H.vault_y(x), z), (0, 0, 1), (0, 1, 0)) for x in xs])
        for c0, c1 in ((h["x0"] + 1.3, h["x0"] + 1.42), (h["x1"] - 1.42, h["x1"] - 1.3)):
            sweep(lparts["trim"], collar, [((x, H.vault_y(x), z), (0, 0, 1), (0, 1, 0)) for x in (c0, c1)])
        for FW in (lambda u, v, w: (h["x0"] + w, v, u), lambda u, v, w: (h["x1"] - w, v, u)):
            ext(ribs, FW, corbel, "u", z - pw - 0.04, z + pw + 0.04)
    # a spine beam along the crown between the ribs
    spine = Part("vault_spine", "lobby_rib")
    yc = H.vault_y(0.0)
    for z0, z1 in zip(edges[::2], edges[1::2]):
        z1 = z1 if z1 is not None else H.arc_z(0.0) - 0.1
        spine.box(-0.45, 0.45, yc - 0.35, yc + 0.02, z0, z1)
    # the pendant lamps' housings (dome shades on rods; their light is step 4's, the lens is not emissive yet)
    # step 2c: real shades (a rim, a reflector inside, a socket and a bulb in the recess; unlit until step 4)
    # step 3: smooth shades (PENDANT_N segments, smooth shading) in the dark metal with a copper rim, each on a cable
    # from a ceiling canopy, their heights varied (PENDANT_DY by a steady pick)
    lamps, lens = Part("vault_lamps", "lobby_metal", closed=False), Part("vault_lens", "lobby_lens", closed=False)
    refl, sock = Part("vault_reflectors", "lobby_reflector", closed=False), Part("vault_sockets", "lobby_dark", closed=False)
    rims, cables = Part("vault_lamp_rims", "lobby_trim", closed=False), Part("vault_cables", "lobby_dark", closed=False)
    for p in (lamps, lens, refl, sock, rims, cables):
        p.smooth = True
    px, pz, yb0 = PENDANTS
    N = PENDANT_N
    for x in px:
        for z in pz:
            yb = yb0 + PENDANT_DY[pick(x, z, 11.0, n=len(PENDANT_DY))]
            ym = yc - 0.35 if abs(x) < 0.5 else H.vault_y(x) - 0.12   # the spine's or the panels' underside

            def sec(r, y, x=x, z=z, n=8):
                return [(x + r * math.cos(2 * math.pi * i / n), y, z + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

            revolve(lamps, x, z, [(0.001, ym + 0.02), (0.21, ym + 0.02), (0.21, ym - 0.03), (0.15, ym - 0.12),
                                  (0.06, ym - 0.16), (0.001, ym - 0.16)], n=N)              # the canopy
            cables.loft([sec(0.011, ym - 0.15), sec(0.011, yb + 1.12)])                    # the cable
            revolve(lamps, x, z, [(0.03, yb + 1.2), (0.05, yb + 1.15), (0.05, yb + 1.02), (0.13, yb + 0.98)], n=N)  # its grip
            revolve(lamps, x, z, [(0.13, yb + 0.98), (0.22, yb + 0.86), (0.3, yb + 0.7), (0.4, yb + 0.52), (0.55, yb + 0.3),
                                  (0.69, yb + 0.11)], n=N)
            revolve(rims, x, z, [(0.69, yb + 0.11), (0.76, yb + 0.06), (0.79, yb + 0.01), (0.785, yb - 0.035),
                                 (0.75, yb - 0.045), (0.72, yb - 0.035)], n=N)
            revolve(refl, x, z, [(0.72, yb - 0.035), (0.66, yb + 0.06), (0.5, yb + 0.26), (0.3, yb + 0.5), (0.19, yb + 0.6)], n=N)
            disc(sock, x, z, 0.19, yb + 0.6, up=False, n=N)
            revolve(sock, x, z, [(0.1, yb + 0.6), (0.1, yb + 0.5)], n=N)
            revolve(lens, x, z, [(0.1, yb + 0.5), (0.14, yb + 0.44), (0.15, yb + 0.36), (0.1, yb + 0.28), (0.001, yb + 0.25)], n=N)
    return [shell, lun, base, inner, battens, ribs, spine, lamps, lens, refl, sock, rims, cables, lparts["trim"]]


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
        top = wall - w["bar_h"]
        for part, hw, r0, r1, y0, y1 in ((mull, half, -0.3, 0.3, w["sill"], top),                        # the mullion
                                         (bars, 0.17, -0.48, -0.3, w["sill"], top),                       # its cap
                                         (mull, 0.07, -0.56, -0.48, w["sill"], top),                      # the cap's nose
                                         (mull, half + 0.08, -0.52, 0.3, w["sill"], w["sill"] + 0.45),    # a shoe
                                         (bars, half + 0.05, -0.54, 0.3, w["transom"] - 0.28, w["transom"] + 0.28)):
            pts = [H.arc_pt(a - hw / H.R, r0), H.arc_pt(a + hw / H.R, r0), H.arc_pt(a + hw / H.R, r1), H.arc_pt(a - hw / H.R, r1)]
            part.loft([[(x, y, z) for x, z in pts] for y in (y0, y1)])
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


def framed(F, a, h, c, bands, w_back, parts, fronts, edges=(None, None, None)):
    """Nested chamfered frame bands round an opening (half-width a, height h, chamfer c) in a local frame, each from
    w_back to its front (stepped); a band's bevel goes into its edges part if given (step 3: a thin copper edge)."""
    d, cb = 0.0, 0.045
    o = F(0.0, 0.0, 0.0)
    for band, part, front, edge in zip(bands, parts, fronts, edges):
        inner, outer, oc = (chamfer_outline(a, h, c, d), chamfer_outline(a, h, c, d + band),
                            chamfer_outline(a, h, c, d + band - cb))
        ext(part, F, ring(inner, oc), "w", w_back, front)
        ext(part, F, ring(oc, outer), "w", w_back, front - cb)
        for p, q, pc, qc in zip(outer, outer[1:], oc, oc[1:]):   # the bevel: it catches the light, the steps read
            hint = [F(-(q[1] - p[1]), q[0] - p[0], 1.0)[k] - o[k] for k in range(3)]
            (edge or part).face([F(p[0], p[1], front - cb), F(q[0], q[1], front - cb), F(qc[0], qc[1], front),
                       F(pc[0], pc[1], front)], hint)
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
    framed(F, a, dh, 0.45, DOOR_BANDS, w_back, (out["trim"], out["frame"], out["trim"]), DOOR_FRONTS,
           edges=(None, None, out["copper"]))
    s0, s1 = slab_w
    lbox(out["back"], F, -a - 0.05, a + 0.05, 0.0, dh + 0.05, s0 - 0.1, s0)
    for side in (-1, 1):   # step 2c: each leaf bevelled at the centre seam, its striped field inside a raised border
        u0, u1 = (-a, -0.012) if side < 0 else (0.012, a)
        if side < 0:
            poly = [(u0, s0), (u1, s0), (u1, s1 - 0.05), (u1 - 0.05, s1), (u0, s1)]
            outer_u, seam_u, fo, fs = (u0, u0 + 0.12), (u1 - 0.17, u1 - 0.07), u0, u1 - 0.07
        else:
            poly = [(u0, s0), (u1, s0), (u1, s1), (u0 + 0.05, s1), (u0, s1 - 0.05)]
            outer_u, seam_u, fo, fs = (u1 - 0.12, u1), (u0 + 0.07, u0 + 0.17), u0 + 0.07, u1
        ext(out["slab"], F, poly, "v", 0.0, dh)
        for b0, b1 in ((0.0, 0.12), (dh - 0.12, dh)):
            lbox(out["frame"], F, fo, fs, b0, b1, s1, s1 + 0.035)
        for uu in (outer_u, seam_u):
            lbox(out["frame"], F, uu[0], uu[1], 0.12, dh - 0.12, s1, s1 + 0.035)
        ha, hb = (u0 + 0.14, u1 - 0.19) if side < 0 else (u0 + 0.19, u1 - 0.14)
        hazard(out["hazard"], F, ha, hb, 0.14, dh - 0.14, s1, mirror=side > 0)
    # the frame's lip over the leaves' edges and a threshold plate
    ext(out["copper"], F, ring(chamfer_outline(a - 0.05, dh - 0.05, 0.43), chamfer_outline(a, dh, 0.45)), "w",
        s1 - 0.02, s1 + 0.07)
    lbox(out["trim"], F, -a, a, 0.0, 0.03, s1, DOOR_FRONTS[0])
    big = a + sum(DOOR_BANDS)
    top = dh + sum(DOOR_BANDS)
    ext(out["frame"], F, [(top, 0.0), (top, LINTEL - 0.06), (top + 0.06, LINTEL), (top + 0.86, LINTEL),
                          (top + 0.86, 0.0)], "u", -big, big)                                   # the lintel box
    FL = shifted(F, LINTEL)
    lamp_v = H.d["lamp"]
    for sg in (-1, 1):   # the lintel's grilles either side of the lamp
        ua, ub = sorted((sg * 0.55, sg * (big - 0.2)))
        vent(FL, ua, ub, top + 0.08, top + 0.5, out["trim"], out["dark"])
    # the red lamp in a housing: a back plate, cheeks, a sloped hood, a bottom lip and a cage over the lens
    lbox(out["trim"], FL, -0.4, 0.4, lamp_v - 0.2, lamp_v + 0.2, 0.0, 0.05)
    for sg in (-1, 1):
        ua, ub = sorted((sg * 0.3, sg * 0.36))
        lbox(out["trim"], FL, ua, ub, lamp_v - 0.17, lamp_v + 0.19, 0.05, 0.2)
    ext(out["trim"], FL, [(lamp_v + 0.15, 0.05), (lamp_v + 0.23, 0.05), (lamp_v + 0.19, 0.27), (lamp_v + 0.14, 0.27)],
        "u", -0.4, 0.4)
    lbox(out["trim"], FL, -0.3, 0.3, lamp_v - 0.17, lamp_v - 0.12, 0.05, 0.2)
    lbox(out["lamp"], FL, -0.26, 0.26, lamp_v - 0.09, lamp_v + 0.09, 0.05, 0.14)
    for u in (-0.13, 0.0, 0.13):
        lbox(out["dark"], FL, u - 0.012, u + 0.012, lamp_v - 0.12, lamp_v + 0.14, 0.17, 0.195)
    channel(FL, -0.9, 0.9, lamp_v + 0.4 - 0.035, lamp_v + 0.4 + 0.035, 0.0, out["dark"], out["strip"])
    bolts(out["trim"], FL, -big + 0.15, big - 0.15, top + 0.75, 0.0, step=0.45)
    if header:   # the wall above the door up to the panels' top row (no longer bare)
        plate(out["panel"], F, -big + 0.04, big - 0.04, top + 0.92, ROWS_LOW[-1][1], 0.0, PROUD, BEV)
        vent(shifted(F, PROUD), -0.75, 0.75, top + 1.12, ROWS_LOW[-1][1] - 0.22, out["trim"], out["dark"])


def _door_set(prefix: str, col: bool) -> dict:
    # step 3: the frames in the dark graphite-teal metal; copper only on the outer band's bevel and the lip
    return {"trim": Part(prefix + "_frame", "lobby_metal", col=col), "frame": Part(prefix + "_frame2", "lobby_pilaster", col=col),
            "copper": Part(prefix + "_copper", "lobby_trim"),
            "back": Part(prefix + "_back", "lobby_dark", col=col), "slab": Part(prefix + "_slab", "lobby_dark", col=col),
            "hazard": Part(prefix + "_hazard", "lobby_hazard"), "lamp": Part(prefix + "_lamp", "lobby_lamp"),
            "dark": Part(prefix + "_dark", "lobby_dark"), "strip": Part(prefix + "_strip", "lobby_strip"),
            "panel": Part(prefix + "_panel", "lobby_panel3", closed=False)}


def arch(H: Hall) -> list[Part]:
    h, a = H.h, H.a
    zN, t, w, ah, end = h["zN"], 0.3, a["w"] / 2, a["h"], h["zN"] - a["depth"]
    FN = lambda u, v, ww: (u, v, zN + ww)
    trim, frame2 = Part("arch_frame", "lobby_metal", col=True), Part("arch_frame2", "lobby_pilaster", col=True)
    dark, strip = Part("arch_dark", "lobby_dark"), Part("arch_strips", "lobby_strip")
    copper = Part("arch_copper", "lobby_trim")   # step 3: the frame in the dark metal, a thin copper edge outside
    framed(FN, w, ah, 1.0, ARCH_BANDS, -h["wall_t"], (trim, frame2, trim), ARCH_FRONTS, edges=(None, None, copper))
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
    return [trim, frame2, copper, dark, strip, shell, slab, *plates, panels, ribs, *out.values()]


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


def metal_images(folder: Path) -> None:
    """The shared maps (TEX_SIZE, seamless): normal (brushed streaks along u, fine scratches) and roughness (0.78-1:
    soft blotches, the streaks, the scratches rougher), saved as PNGs in folder and kept in IMG."""
    rng = np.random.default_rng(356)
    n = TEX_SIZE

    def blur(a, k, axis):
        acc = np.zeros_like(a)
        for i in range(-k, k + 1):
            acc += np.roll(a, i, axis=axis)
        return acc / (2 * k + 1)

    br = blur(blur(rng.standard_normal((n, n)).astype(np.float32), 24, 1), 1, 0)
    br /= br.std() + 1e-6
    sc = np.zeros((n, n), np.float32)
    for _ in range(260):
        x, y = rng.uniform(0, n, 2)
        ang, length, depth = rng.uniform(0, math.pi), rng.uniform(15, 110), rng.uniform(0.4, 1.0)
        t = np.arange(0, length, 0.7)
        xs = (x + t * math.cos(ang)).astype(int) % n
        ys = (y + t * math.sin(ang)).astype(int) % n
        sc[ys, xs] = np.maximum(sc[ys, xs], depth)
    g = rng.uniform(-1, 1, (8, 8)).astype(np.float32)
    idx = np.arange(n) * 8 / n
    i0 = np.floor(idx).astype(int)
    f = (idx - i0).astype(np.float32)
    i1 = (i0 + 1) % 8
    rows = g[i0] * (1 - f)[:, None] + g[i1] * f[:, None]
    blot = rows[:, i0] * (1 - f)[None, :] + rows[:, i1] * f[None, :]
    h = 0.35 * br - sc
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.3
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.3
    ln = np.sqrt(dx * dx + dy * dy + 1.0)
    one = np.ones_like(h)
    maps = {"n": np.stack([-dx / ln * 0.5 + 0.5, -dy / ln * 0.5 + 0.5, 1.0 / ln * 0.5 + 0.5, one], -1),
            "r": np.stack([one, np.clip(0.9 + 0.06 * blot + 0.025 * np.clip(br, -2, 2) + 0.08 * sc, 0.78, 1.0), one, one], -1)}
    # step 3 (after the 2c maps, which stay as they were): grime, scuffs and the copper's roughness
    def vnoise(k):
        gg = rng.uniform(-1, 1, (k, k)).astype(np.float32)
        ff = (idx * k / 8 - np.floor(idx * k / 8)).astype(np.float32)
        ff = ff * ff * (3 - 2 * ff)
        j0 = np.floor(idx * k / 8).astype(int) % k
        j1 = (j0 + 1) % k
        rr = gg[j0] * (1 - ff)[:, None] + gg[j1] * ff[:, None]
        return rr[:, j0] * (1 - ff)[None, :] + rr[:, j1] * ff[None, :]

    b16, b32 = vnoise(16), vnoise(32)
    speck = blur(blur(rng.standard_normal((n, n)).astype(np.float32), 1, 0), 1, 1)
    speck /= speck.std() + 1e-6
    sc2 = np.rot90(sc).copy()
    grime = np.clip(0.95 + 0.035 * blot + 0.03 * b16 - 0.05 * np.clip(speck - 1.6, 0, 2), 0.86, 1.0)
    rub = np.clip(b16 + 0.5 * b32 - 0.15, 0, 1)
    scuff = np.clip(0.97 - 0.28 * rub - 0.3 * np.maximum(sc, sc2) - 0.06 * np.clip(speck - 1.0, 0, 2), 0.5, 1.0)
    r2 = np.clip(0.82 + 0.16 * b16 + 0.08 * b32 + 0.03 * np.clip(br, -2, 2), 0.6, 1.0)
    for key, val in (("g", grime), ("s", scuff)):
        maps[key] = np.stack([val, val, val, one], -1)
    maps["r2"] = np.stack([one, r2, one, one], -1)
    folder.mkdir(parents=True, exist_ok=True)
    for key, arr in maps.items():
        img = bpy.data.images.new(f"lobby_metal_{key}", n, n, alpha=False)
        img.colorspace_settings.name = "sRGB" if key in ("g", "s") else "Non-Color"
        img.pixels.foreach_set(arr.astype(np.float32).ravel())
        img.filepath_raw = str(folder / f"lobby_metal_{key}.png")
        img.file_format = "PNG"
        img.save()
        IMG[key] = img


def metal_maps(mat, bsdf, name: str, rough: float, metallic: float, rgba=None) -> None:
    """The shared maps on a material: the normal at its strength, roughness and metallic as the maps' G and B times
    the material's numbers (the glTF exporter writes them as the factors)."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tn = nodes.new("ShaderNodeTexImage")
    tn.image = IMG["n"]
    nm = nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = NORMAL_STRENGTH.get(name, 1.0)
    links.new(tn.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    tr = nodes.new("ShaderNodeTexImage")
    tr.image = IMG["r2" if name in ROUGH2 else "r"]
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(tr.outputs["Color"], sep.inputs["Color"])
    for channel_name, socket, value in (("Green", "Roughness", rough), ("Blue", "Metallic", metallic)):
        m = nodes.new("ShaderNodeMath")
        m.operation = "MULTIPLY"
        m.inputs[1].default_value = value
        links.new(sep.outputs[channel_name], m.inputs[0])
        links.new(m.outputs[0], bsdf.inputs[socket])
    if rgba is not None:   # step 3: the colour times the grime (or scuff) map; the exporter writes rgba as the factor
        tc = nodes.new("ShaderNodeTexImage")
        tc.image = IMG["s" if name in SCUFFED else "g"]
        mix = nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        mix.inputs[7].default_value = rgba
        links.new(tc.outputs["Color"], mix.inputs[6])
        links.new(mix.outputs[2], bsdf.inputs["Base Color"])


def box_uvs(mesh) -> None:
    """Box-projected UVs in metres / TEX_M; per 2 m cell a steady offset and a 90 deg turn (the brushing's way)."""
    data = mesh.uv_layers.new(name="UVMap").data
    for poly in mesh.polygons:
        nrm, c = poly.normal, poly.center
        ax = max(range(3), key=lambda k: abs(nrm[k]))
        i, j = ((1, 2), (0, 2), (0, 1))[ax]
        cell = (math.floor(c.x / 2.0), math.floor(c.y / 2.0), math.floor(c.z / 2.0))
        ou, ov, turn = pick(*cell, 1.0, n=97) / 97.0, pick(*cell, 2.0, n=89) / 89.0, pick(*cell, 3.0, n=2)
        for li in poly.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            a, b = co[i] / TEX_M + ou, co[j] / TEX_M + ov
            data[li].uv = (b, a) if turn else (a, b)


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
    if name not in PLAIN and IMG:
        metal_maps(mat, bsdf, name, rough, metallic, rgba)
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
    smooth = any(part.flags) and len(part.flags) == len(bm.faces)
    if smooth:
        for f, s in zip(bm.faces, part.flags):
            f.smooth = s
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    if part.closed:   # every face carries its outward hint (Part.face); merged parts are never recalculated
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if smooth:   # sharp where the surface turns more than 35 deg (the shades' rims stay crisp)
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(35):
                e.smooth = False
    bm.to_mesh(mesh)
    bm.free()
    box_uvs(mesh)
    mesh.materials.append(material(part.mat))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def merged(pid: str, parts: list[Part], collide: bool) -> list[tuple[Part, bool]]:
    """One object per material and collision: fewer draw calls. Step 3: some narrow faces of the WEARABLE materials
    move into lobby_worn (worn())."""
    groups: dict = {}
    for p in parts:
        if not p.faces:
            continue
        col = collide and p.col
        for f in p.faces:
            mat = "lobby_worn" if p.mat in WEARABLE and worn([p.verts[i] for i in f]) else p.mat
            key = (mat, col)
            if key not in groups:
                groups[key] = Part(f"{pid}_{mat.removeprefix('lobby_')}" + ("_c" if col else ""), mat, closed=False)
            g = groups[key]
            base = len(g.verts)
            g.verts += [p.verts[i] for i in f]
            g.faces.append(list(range(base, base + len(f))))
            g.flags.append(p.smooth)
    return [(g, col) for (_m, col), g in groups.items()]


def worn(pts) -> bool:
    """A narrow face (a bevel, a chamfer, a lip: at most WEAR_W wide, at least 0.12 m long), about WEAR_SHARE % of
    them by a steady hash of the face's centre."""
    nrm = _normal(pts)
    area = 0.5 * math.sqrt(sum(c * c for c in nrm))
    longest = max(math.dist(a, b) for a, b in zip(pts, pts[1:] + pts[:1]))
    if longest < 0.12 or area / longest > WEAR_W:
        return False
    c = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
    return pick(round(c[0] * 3), round(c[1] * 3), round(c[2] * 3), 5.0, n=100) < WEAR_SHARE


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
            "objects": [o.name for o in objs], "materials": sorted({o.data.materials[0].name for o in objs}),

            "bounds": {"min": [lo[0], lo[2], -hi[1]], "max": [hi[0], hi[2], -lo[1]]}}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    req = json.loads(Path(argv[argv.index("--request") + 1]).read_text(encoding="utf-8"))
    out = Path(argv[argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)
    LOOK["mats"] = req["look"]
    metal_images(out / "textures")
    H = Hall(req)
    report = {"pieces": {}}
    for piece in req["layout"]["pieces"]:
        report["pieces"][piece["id"]] = build(piece, H, out)
        print(f"LOBBY built {piece['id']}: {report['pieces'][piece['id']]['triangles']} triangles")
    (out / "build_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    print(f"LOBBY done {len(report['pieces'])} pieces")


if __name__ == "__main__":
    main()
