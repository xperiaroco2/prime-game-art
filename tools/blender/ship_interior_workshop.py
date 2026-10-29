"""The west lens room's robot workshop, step 1 (art #263, docs/ship.md "The west lens room's workshop"): static decor
built from the design's cm drawing (<raw>/ship/v5/workshop/drawing/index.html) and its concept w_c_bot.jpg (painted
on the east room; tip_w is its mirror). A bench of four bronze modules along the facets -109.77..-21.95 (the drawing's
east angles; the west room's frame is their mirror, a_w = -a_e), two of its drawers pulled out 25 cm (spare eyes,
spare limbs); a low cabinet of two modules under the windows carrying two cradles, each with a small sleeping robot; a
bronze ceiling rail with a hoist holding the main robot by its crown over a dark green rug; an articulated lamp on the
bench aimed at the robot. Nothing moves; only the light lives (acid green strips, handles, rims, the lamp's lens and
the sleepers' dim eye lines).

Frames. A bench or cabinet module is built on its facet's face like a sofa module (ship_interior_lens: origin the
facet's middle on the face, d out of it toward -x, its ends on the vertices' bisectors). A free item stands at its own
point (origin on the floor under it) turned so local +x points along `face` (the room-frame angle of its facet or its
own radial), -x toward the room; the rail is built in the room's frame (origin the room's centre). Sizes in cm in the
tables, metres in the geometry."""

from __future__ import annotations

import math

import ship_interior as S
import ship_interior_geom as G
import ship_interior_lens as LN
import ship_lib as L

D = math.radians
FLOOR = S.FLOOR
CM = 0.01
# (ship_interior imports this module at its end, so a run that starts from ship_interior_lens finds it half made:
# its names are used inside the builders only, these are its numbers again)
HALF = S.TIP_STEP / 2
HW = S.R_TIP * math.sin(D(HALF))
TAN = math.tan(D(HALF))
BRONZE, BRONZE2, EDGE = "lens_bronze", "lens_bronze2", "lens_edge"
GRAPH, GRAPH2 = "lens_graphite", "lens_graphite2"
M = L.merge


def P(name, vf, mat, solid=True):
    return L.part(name, *vf, mat, solid=solid)

_GREEN = (0.42, 1.0, 0.08)
_CYAN = (0.1, 0.85, 1.0)
L.MATERIALS.update({
    # the robots' shells: an off-white glazed ceramic (the concept's ivory panels), the joints' second tone
    "ws_shell": {"base": (0.70, 0.67, 0.60, 1.0), "metallic": 0.0, "roughness": 0.3},
    "ws_shell2": {"base": (0.42, 0.41, 0.39, 1.0), "metallic": 0.1, "roughness": 0.4},
    # the eye's dark glass and the visors (glossy, nearly black)
    "ws_glass": {"base": (0.006, 0.008, 0.01, 1.0), "metallic": 0.0, "roughness": 0.06},
    # the sleepers' eye sockets: satin (r2's glossy glass caught two lamps as eyes over the lid's line: a smiley face)
    "ws_socket": {"base": (0.01, 0.012, 0.014, 1.0), "metallic": 0.0, "roughness": 0.55},
    # the cradles' cushions and the rug: dark green fabric, the rug's border a shade darker
    "ws_cushion": {"base": (0.012, 0.022, 0.018, 1.0), "metallic": 0.0, "roughness": 0.96},
    "ws_rug": {"base": (0.022, 0.09, 0.058, 1.0), "metallic": 0.0, "roughness": 0.99},   # r1: 0.010/0.040 read black
    "ws_rug2": {"base": (0.008, 0.038, 0.025, 1.0), "metallic": 0.0, "roughness": 0.99},
    # the main robot's insides: insulated cables (teal, orange, blue) and the hoist's steel cable
    "ws_cable_a": {"base": (0.02, 0.16, 0.12, 1.0), "metallic": 0.0, "roughness": 0.45},
    "ws_cable_b": {"base": (0.45, 0.12, 0.02, 1.0), "metallic": 0.0, "roughness": 0.45},
    "ws_cable_c": {"base": (0.02, 0.06, 0.28, 1.0), "metallic": 0.0, "roughness": 0.45},
    "ws_steel": {"base": (0.30, 0.31, 0.33, 1.0), "metallic": 0.9, "roughness": 0.35},
    # step 2: a fourth cable colour (a dull yellow) and the shells' dark insides (satin graphite)
    "ws_cable_d": {"base": (0.42, 0.30, 0.02, 1.0), "metallic": 0.0, "roughness": 0.45},
    "ws_inner": {"base": (0.035, 0.037, 0.04, 1.0), "metallic": 0.15, "roughness": 0.72},   # matte: a satin one mirrored the green
    # step 2: the cabinetry's dark bronze (the concept's olive-bronze fronts and tops; step 1's lens bronze read orange
    # plastic) and its second, darker tone; ship.gd swaps both for the stations' bronze shader (LENS_BRONZE)
    "ws_bronze": {"base": (*(x ** 2.2 for x in (0.26, 0.22, 0.14)), 1.0), "metallic": 0.55, "roughness": 0.4},
    "ws_bronze2": {"base": (*(x ** 2.2 for x in (0.13, 0.125, 0.10)), 1.0), "metallic": 0.35, "roughness": 0.5},
})
# the room's acid green (and the eyes' cyan): glows; ship.toml [light.mats] gives each its colour and strength, l 0
# (they light nothing: the room's green light is the "shop" lamp group's few omnis and spots); step 2: the open
# drawers' lit liners, the cores' small cyan lights and the eye's soft highlight
for _n, _c, _s in (("ws_green__strip", _GREEN, 8.0), ("ws_green__handle", _GREEN, 8.0), ("ws_green__rim", _GREEN, 8.0),
                   ("ws_green__lamp", _GREEN, 12.0), ("ws_green__sleep", _GREEN, 4.0), ("ws_cyan__eye", _CYAN, 6.0),
                   ("ws_cyan__pupil", _CYAN, 4.0), ("ws_green__liner", _GREEN, 2.0), ("ws_cyan__core", _CYAN, 8.0),
                   ("ws_glint", (1.0, 1.0, 1.0), 2.0)):
    L.MATERIALS[_n] = {"base": (*_c, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": _c, "strength": _s}
L.MATERIALS["ws_green__liner"]["base"] = (0.03, 0.12, 0.02, 1.0)   # a dark green felt that glows a little

# --- the drawing's numbers (cm) -----------------------------------------------------------------------------------
# the bench: d 0..55, top 90 (a 5 cm slab), the body's face at d 50, drawer fronts 2.5 thick on it (h 10..45, 47..82),
# the green strip under the top's overhang, a graphite work mat on the top; drawers pull out 25
BENCH = {"d": 55.0, "top": 90.0, "slab": 5.0, "body": 50.0, "front": 2.5, "toe": (8.0, 46.0),
         "drawers": ((10.0, 45.0), (47.0, 82.0)), "strip": (83.2, 84.4), "mat": 0.25, "pull": 25.0, "open_w": 26.8}
# the cradles' cabinet: d 0..59 (the drawing's 60 reached 1 mm over the floor light's bar on its middle vertex), top
# 55 (a 4 cm slab), one drawer per module
CAB = {"d": 59.0, "top": 55.0, "slab": 4.0, "body": 54.0, "front": 2.5, "toe": (8.0, 49.0), "drawer": (10.0, 47.0),
       "strip": (48.4, 49.6)}
BENCH_K = (-5, -1)        # the bench's end vertices (k * TIP_STEP, east): -109.77 .. -21.95
CAB_K = (-1, 1)           # the cabinet's: -21.95 .. +21.95
# the open drawers by facet (the drawing's east angle of the facet's middle): the top one's spare eyes, the low one's
# spare small hands and legs
OPEN = {-32.93: ("top", "eyes"), -98.81: ("low", "limbs")}
CRADLE = {"d": 54.0, "h": 18.0, "bed": 44.0}
SLEEPER = 28.0            # the sleeping robots' diameter
# step 2: the side shells smaller (caps of 40 deg, step 1's 45 read as two big ears) and opened 32 deg (the shells'
# grid, <raw>/ship/v5/workshop/grids/robot_grid_*.png, picked 40/36; 32 in the room: at 36 their dark insides read as
# two black ears from the bench's front)
ROBOT = {"d": 60.0, "h": 145.0, "eye": 16.0, "hands": 95.0, "open": 32.0, "panel": 40.0}
# step 2: the rail 14 cm lower (bottom 214; at 228 its top was 1.7..3.5 cm under the ceiling and the hangers did not
# show); it still clears the 1.8 m capsule by 34 cm; the hoist a chunky carriage, a short thick rod and a claw clamp
RAIL = {"r": 105.0, "th": (-110.0, -25.0), "bottom": 214.0, "w": 10.0, "t": 8.0, "hangers": (-100.0, -67.5, -35.0)}
HOIST = {"carriage": (30.0, 17.0, 12.0), "rod": 2.2, "clamp": (176.0, 188.0)}
RUG = {"d": 66.0, "r": 110.0}   # the drawing's D80 at r 95 covered the floor lights' bars: D66 between them at r 110
LAMP = {"base": 18.0, "head": 140.0}
# the free items in the WEST room's frame (a_w = -a_e of the drawing): (piece, r m, a_w deg, face deg); the robot,
# cradles and lamp at the drawing's tip_w points (r, theta), the rug moved out to clear the floor lights
_LAMP_FACE = -(round((-100.0 - HALF) / S.TIP_STEP) * S.TIP_STEP + HALF)   # LN.facet_mid(-100)
ITEMS = [("ws_rail", 0.0, 0.0, 0.0),
         ("ws_rug", RUG["r"] * CM, 67.5, 67.5),
         ("ws_robot_body", 1.0494, 67.5, 67.5),
         ("ws_robot", 1.0494, 67.5, 67.5),
         ("ws_hoist", 1.0494, 67.5, 67.5),
         ("ws_cradle", 1.7124, 11.0, 11.0),
         ("ws_sleeper_a", 1.7124, 11.0, 11.0),
         ("ws_cradle", 1.7128, -11.0, -11.0),
         ("ws_sleeper_b", 1.7128, -11.0, -11.0),
         ("ws_lamp", 1.8125, 100.0, _LAMP_FACE)]


def item(pid: str) -> tuple[float, float, float]:
    return next((r, a, f) for p, r, a, f in ITEMS if p == pid)


# --- helpers ------------------------------------------------------------------------------------------------------
def unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return tuple(x / n for x in v)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def rot(axis, deg):
    """The 3x3 rotation by deg about axis (right-handed)."""
    x, y, z = unit(axis)
    c, s = math.cos(D(deg)), math.sin(D(deg))
    t = 1 - c
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(r, v):
    return tuple(sum(r[i][k] * v[k] for k in range(3)) for i in range(3))


def moved(vf, r=None, t=(0.0, 0.0, 0.0), pivot=(0.0, 0.0, 0.0)):
    """A mesh turned by r about pivot, then moved by t."""
    v, f = vf
    out = []
    for p in v:
        q = tuple(a - b for a, b in zip(p, pivot))
        if r is not None:
            q = mv(r, q)
        out.append(tuple(a + b + c for a, b, c in zip(q, pivot, t)))
    return out, f


def lathe(prof, n, o=(0.0, 0.0, 0.0), ax=(0.0, 0.0, 1.0), e1=None, t0=0.0, t1=360.0):
    """A solid of revolution: prof a list of (rho, z) round the axis ax through o. An open profile whose end has rho 0
    closes on the axis there (else the end ring is capped); a closed profile (first == last point) sweeps a ring.
    A partial sweep (t0..t1 deg from e1, toward ax x e1) caps both ends with the profile (closed profiles only)."""
    a = unit(ax)
    if e1 is None:
        ref = (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0)
        e1 = unit(cross(cross(a, ref), a))
    e1 = unit(e1)
    e2 = cross(a, e1)
    closed = tuple(prof[0]) == tuple(prof[-1])
    pts = list(prof[:-1]) if closed else list(prof)
    full = abs(t1 - t0 - 360.0) < 1e-9
    ts = [D(t0 + (t1 - t0) * j / n) for j in range(n if full else n + 1)]
    verts, rows = [], []
    for rho, z in pts:
        if rho < 1e-9 and not closed:
            rows.append([len(verts)])
            verts.append(add(o, mul(a, z)))
            continue
        row = []
        for t in ts:
            row.append(len(verts))
            verts.append(add(o, add(mul(e1, rho * math.cos(t)), add(mul(e2, rho * math.sin(t)), mul(a, z)))))
        rows.append(row)
    m = len(ts)
    faces = []
    links = list(zip(range(len(rows) - 1), range(1, len(rows)))) + ([(len(rows) - 1, 0)] if closed else [])
    for i, k in links:
        A, B = rows[i], rows[k]
        for j in range(m if full else m - 1):
            jn = (j + 1) % m
            if len(A) == 1:
                faces.append((A[0], B[jn], B[j]))
            elif len(B) == 1:
                faces.append((A[j], A[jn], B[0]))
            else:
                faces.append((A[j], A[jn], B[jn], B[j]))
    if not closed and full:
        for row in (rows[0], rows[-1]):
            if len(row) > 1:
                faces.append(tuple(row))
    if not full:
        faces.append(tuple(r[0] for r in rows))
        faces.append(tuple(r[-1] for r in rows))
    return verts, faces


def zone(R, t, p0, p1, steps=10, bev=0.003):
    """A shell zone's closed profile (rho, z) on a sphere R: polar angles p0..p1 deg from the axis, thickness t, each
    free edge chamfered by bev (a crisp lip); p0 0 or p1 180 closes on the axis."""
    def pt(r, p):
        return (r * math.sin(D(p)), r * math.cos(D(p)))
    d = math.degrees(bev / R)
    a0, a1 = (p0 if p0 <= 0 else p0 + d), (p1 if p1 >= 180 else p1 - d)
    outer = [pt(R, a0 + (a1 - a0) * i / steps) for i in range(steps + 1)]
    inner = [pt(R - t, a1 + (a0 - a1) * i / steps) for i in range(steps + 1)]
    prof = []
    if p0 > 0:
        prof.append(pt(R - bev, p0))
    prof += outer
    if p1 < 180:
        prof.append(pt(R - bev, p1))
    prof += inner
    if p0 > 0:
        prof.append(prof[0])
    else:   # a cap: from the pole on the outer surface round to the pole on the inner one
        prof = [(0.0, R)] + prof[1:-1] + [(0.0, R - t)]
    return prof


def sphere(r, c, rings=16, segs=32):
    return lathe([(r * math.sin(D(180.0 * i / rings)), -r * math.cos(D(180.0 * i / rings))) for i in range(rings + 1)],
                 segs, c)


def capsule(p0, p1, r, n=12):
    """A rounded rod from p0 to p1."""
    ln = math.dist(p0, p1)
    prof = [(0.0, -r)] + [(r * math.sin(D(a)), -r * math.cos(D(a))) for a in (30, 60, 90)]
    prof += [(r * math.sin(D(a)), ln + r * math.cos(D(a))) for a in (90, 60, 30)] + [(0.0, ln + r)]
    return lathe(prof, n, p0, tuple(b - a for a, b in zip(p0, p1)))


def torus(R, r, o, ax, n=32, m=10):
    return lathe([(R + r * math.cos(D(360.0 * i / m)), r * math.sin(D(360.0 * i / m))) for i in range(m)] +
                 [(R + r, 0.0)], n, o, ax)


def cap_lens(R, ang, lift, depth, c, ax, n=20, steps=4):
    """A thin lens on a sphere (centre c, radius R) round the direction ax: its outer face lift over the sphere out to
    ang deg, its base depth under it (an iris or a pupil)."""
    prof = [(0.0, R + lift)] + [((R + lift) * math.sin(D(ang * i / steps)), (R + lift) * math.cos(D(ang * i / steps)))
                                for i in range(1, steps + 1)]
    prof += [((R - depth) * math.sin(D(ang)), (R - depth) * math.cos(D(ang))), (0.0, (R - depth) * math.cos(D(ang)))]
    return lathe(prof, n, c, ax)


def bez(pts, n):
    """n + 1 points along the Bezier curve of the control points pts."""
    out = []
    for i in range(n + 1):
        t = i / n
        q = list(pts)
        while len(q) > 1:
            q = [tuple(a + (b - a) * t for a, b in zip(u, v)) for u, v in zip(q, q[1:])]
        out.append(q[0])
    return out


def part(name, vf, mat, smooth=None):
    p = P(name, vf, mat)
    if smooth:
        p["smooth_deg"] = smooth
    return p


def half(d):
    """A facet module's half width (m) at d cm from the face, its ends on the vertices' bisectors."""
    return HW - d * CM * TAN


def fblock(d0, d1, h0, h1, e=0.0, top=0.0, bot=0.0):
    return LN.facet_block(d0, d1, h0, h1, e, e, top=top, bot=bot)


def stile(d0, d1, h0, h1, y_in, side, e=0.15):   # e: LN.SEAM
    """A block from a module's end (its bisector, in by e cm) to the line y = side * y_in (m), d0..d1, h0..h1 (cm)."""
    if side < 0:
        q = [(-d0 * CM, -(half(d0) - e * CM)), (-d0 * CM, -y_in), (-d1 * CM, -y_in), (-d1 * CM, -(half(d1) - e * CM))]
    else:
        q = [(-d0 * CM, y_in), (-d0 * CM, half(d0) - e * CM), (-d1 * CM, half(d1) - e * CM), (-d1 * CM, y_in)]
    return LN.loft([[(x, y, FLOOR + h * CM) for x, y in LN.ccw(q)] for h in (h0, h1)])


def front(y0, y1, h0, h1, d0, d1, bev=0.008):
    """A plate facing the room (-x): y0..y1 m, h0..h1 cm, d0..d1 cm out of the face, its front edges chamfered."""
    return G.slab(G.wall_frame(FLOOR), G.rect(y0, y1, h0 * CM, h1 * CM), d0 * CM, d1 * CM, bev)


def handle(h, d, w=24.0):
    """A drawer's pull: a graphite bezel (w x 3.2 cm, 0.8 deep) and its lit green bar (w - 4 x 1.2, 0.5 proud)."""
    return (front(-w / 2 * CM, w / 2 * CM, h - 1.6, h + 1.6, d, d + 0.8, 0.003),
            front((-w / 2 + 2) * CM, (w / 2 - 2) * CM, h - 0.6, h + 0.6, d + 0.8, d + 1.3, 0.002))


# --- the bench and the cabinet (facet modules) ---------------------------------------------------------------------
def _module(K, drawers, open_slot=None):
    """A module's carcass, top, closed drawer fronts, pulls and green strip; open_slot (h0, h1) leaves a drawer's
    opening (a graphite back, two stiles) for the pulled-out drawer piece."""
    t0, t1 = K["toe"]
    top, slab, body, fr = K["top"], K["slab"], K["body"], K["front"]
    seam = LN.SEAM
    # step 2: graphite carcass, dark bronze fronts with a chamfered raised panel each, a dark bronze top with a glossy
    # bronze nosing (step 1's lens bronze everywhere read as orange plastic)
    out = [part("toe", fblock(0.0, t1, 0.0, t0, seam), GRAPH)]
    if open_slot:
        s0, s1 = open_slot
        w = BENCH["open_w"] * CM / 2
        out += [part("body", M(fblock(0.0, body, t0, s0, seam, bot=0.0), fblock(0.0, body, s1, top - slab, seam)),
                     GRAPH2),
                part("bay", fblock(0.0, 18.0, s0, s1, seam), GRAPH),
                part("stiles", M(stile(18.0, body, s0, s1, w, -1), stile(18.0, body, s0, s1, w, 1)), "ws_bronze2")]
    else:
        out.append(part("body", fblock(0.0, body, t0, top - slab, seam), GRAPH2))
    yf = half(body + fr) - 0.0165
    fronts, panels, bezels, bars = [], [], [], []
    for h0, h1 in drawers:
        if open_slot and (h0, h1) == (open_slot[0] + 1.0, open_slot[1] - 1.0):
            continue
        fronts.append(front(-yf, yf, h0, h1, body, body + fr))
        panels.append(front(-yf + 0.03, yf - 0.03, h0 + 3.0, h1 - 3.0, body + fr - 0.1, body + fr + 0.5, 0.004))
        b, g = handle(h1 - 7.0, body + fr + 0.5)
        bezels.append(b)
        bars.append(g)
    if fronts:
        out += [part("fronts", M(*fronts), "ws_bronze2"), part("panels", M(*panels), "ws_bronze"),
                part("pulls", M(*bezels), GRAPH), part("pull_lights", M(*bars), "ws_green__handle")]
    s0, s1 = K["strip"]
    out.append(part("strip", fblock(body - 0.1, body + 0.5, s0, s1, 1.0), "ws_green__strip"))
    out.append(part("top", fblock(0.0, K["d"] - 1.2, top - slab, top, 0.0, top=1.0, bot=0.4), "ws_bronze"))
    out.append(part("nosing", fblock(K["d"] - 1.4, K["d"], top - slab, top, 0.0, top=0.5, bot=0.5), EDGE))
    return out


def ws_bench(args, layout):
    """A bench module: the toe recess (graphite, d 0..46, h 0..8), the bronze body to the top's underside (face d 50),
    two drawer fronts (h 10..45, 47..82, 2.5 thick) with lit green pulls, the green strip under the top's overhang
    (h 83.2..84.4), the bronze top (d 0..55, h 85..90, its seams continuous across modules) and a graphite work mat;
    `open` "top" / "low" leaves that drawer's opening for ws_drawer_*."""
    slot = {"top": BENCH["drawers"][1], "low": BENCH["drawers"][0]}.get(args.get("open", ""))
    out = _module(BENCH, BENCH["drawers"], (slot[0] - 1.0, slot[1] + 1.0) if slot else None)
    top = BENCH["top"]
    out.append(part("mat", fblock(5.0, BENCH["d"] - 6.0, top - 0.1, top + BENCH["mat"], 4.0, top=0.15), GRAPH2))
    return out


def ws_cabinet(args, layout):
    """A cradle cabinet module: the toe (graphite), the bronze body (face d 55), one drawer front (h 10..47) with its
    lit pull, the green strip under the top and the bronze top (d 0..60, h 51..55)."""
    return _module(CAB, [CAB["drawer"]])


def _tray(h0, h1, d_front):
    """A pulled-out drawer: its front (as the closed ones) at d_front, the tray behind it (1.2 cm walls, 48 deep) and
    a raised graphite insert 14 cm under the front's top; returns (parts, floor h cm, inner y m, inner d range cm)."""
    fr = BENCH["front"]
    yf = half(BENCH["body"] + fr) - 0.0165
    w = 0.25
    db = d_front - 48.0
    hf, ht, fl = h0 + 1.5, h1 - 3.0, h1 - 14.0
    walls = [L.box(-d_front * CM, -db * CM, -w, -w + 0.012, FLOOR + hf * CM, FLOOR + ht * CM),
             L.box(-d_front * CM, -db * CM, w - 0.012, w, FLOOR + hf * CM, FLOOR + ht * CM),
             L.box(-(db + 1.2) * CM, -db * CM, -w, w, FLOOR + hf * CM, FLOOR + ht * CM),
             L.box(-d_front * CM, -db * CM, -w, w, FLOOR + hf * CM, FLOOR + (hf + 1.0) * CM)]
    b, g = handle(h1 - 7.0, d_front + fr + 0.5)
    # step 2: the insert's top is a lit green felt liner (the concept's glowing drawer insides), the tray's rim a thin
    # green line round the inside of its walls
    x0, x1 = -(d_front - 0.3) * CM, -(db + 1.5) * CM
    yi = w - 0.015
    yw, xb = w - 0.012, -(db + 1.2) * CM          # the walls' inner faces: the rim sits on them
    rim = M(L.box(x0, xb, -yw, -yw + 0.003, FLOOR + (ht - 1.6) * CM, FLOOR + (ht - 0.8) * CM),
            L.box(x0, xb, yw - 0.003, yw, FLOOR + (ht - 1.6) * CM, FLOOR + (ht - 0.8) * CM),
            L.box(xb - 0.003, xb, -yw + 0.003, yw - 0.003, FLOOR + (ht - 1.6) * CM, FLOOR + (ht - 0.8) * CM))
    parts = [part("front", front(-yf, yf, h0, h1, d_front, d_front + fr), "ws_bronze2"),
             part("panel", front(-yf + 0.03, yf - 0.03, h0 + 3.0, h1 - 3.0, d_front + fr - 0.1, d_front + fr + 0.5,
                                 0.004), "ws_bronze"),
             part("tray", M(*walls), "ws_bronze2"),
             part("insert", G.bbox(x0, x1, -yi, yi, FLOOR + (hf + 0.5) * CM, FLOOR + (fl - 0.4) * CM, 0.004), GRAPH2),
             part("liner", L.box(x0 + 0.003, x1 - 0.003, -yi + 0.003, yi - 0.003, FLOOR + (fl - 0.45) * CM,
                                 FLOOR + fl * CM), "ws_green__liner"),
             part("rim", rim, "ws_green__strip"),
             part("pull", b, GRAPH), part("pull_light", g, "ws_green__handle")]
    return parts, fl, w - 0.015, (db + 1.5, d_front - 0.3)


def _eyes(fl, yin, dr):
    """Spare eyes (balls D8, a blue iris and a dark pupil) in rows on the liner, each looking its own way."""
    import random
    rnd = random.Random(7)
    whites, irises, pupils = [], [], []
    r = 0.04
    pitch = 0.092
    for row in range(4):
        d = dr[1] - 7.0 - row * pitch * 100
        for k in range(5):
            y = -yin + 0.046 + k * pitch + rnd.uniform(-0.006, 0.006)
            c = (-d * CM + rnd.uniform(-0.006, 0.006), y, FLOOR + fl * CM + r - 0.004)
            look = unit((rnd.uniform(-0.9, 0.3), rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.0)))
            whites.append(sphere(r, c, 10, 20))
            irises.append(cap_lens(r, 34.0, 0.0008, 0.004, c, look, 20, 4))
            pupils.append(cap_lens(r, 15.0, 0.0016, 0.004, c, look, 14, 2))
    return [part("eyes", M(*whites), "ws_shell", 40.0), part("irises", M(*irises), "ws_cyan__pupil", 40.0),
            part("pupils", M(*pupils), "ws_glass", 40.0)]


def seg(p0, p1, r0, r1, a=0.0, b=0.0, ch=0.003, n=16):
    """A tapered segment from p0 to p1 (radius r0 to r1), starting a and ending b short of its ends, its end rims
    chamfered by ch (an arm's ivory shell)."""
    ln = math.dist(p0, p1)
    prof = [(0.0, a), (r0 - ch, a), (r0, a + ch), (r1, ln - b - ch), (r1 - ch, ln - b), (0.0, ln - b)]
    return lathe(prof, n, p0, tuple(y - x for x, y in zip(p0, p1)))


def hinge(c, ax, r, w, cap=0.004, n=20):
    """A joint's hinge: a graphite drum radius r, w wide along ax through c, and its two bronze caps."""
    a = unit(ax)
    drum = lathe([(0.0, -w / 2), (r - 0.002, -w / 2), (r, -w / 2 + 0.002), (r, w / 2 - 0.002), (r - 0.002, w / 2),
                  (0.0, w / 2)], n, c, a)
    caps = M(*[lathe([(0.0, 0.0), (r * 0.62, 0.0), (r * 0.62, cap - 0.001), (r * 0.55, cap), (0.0, cap)], n,
                     add(c, mul(a, s * (w / 2 - 0.0005))), mul(a, s)) for s in (-1, 1)])
    return drum, caps


def claw(W, fa, up, r=1.0, spread=0.5):
    """A three-finger claw at the wrist W along fa: a graphite palm, three bronze fingers of two segments each with a
    knuckle, curled in at the tips; up picks the first finger's side. Returns (palm, knuckles, fingers)."""
    u = unit(cross(fa, up))
    v = cross(fa, u)
    palm = lathe([(0.0, 0.0), (0.021 * r, 0.0), (0.024 * r, 0.006 * r), (0.024 * r, 0.018 * r), (0.018 * r, 0.024 * r),
                  (0.0, 0.024 * r)], 18, W, fa)
    knuckles, fingers = [], []
    for k in range(3):
        a = D(120 * k + 90)
        rad = add(mul(u, math.cos(a)), mul(v, math.sin(a)))
        q0 = add(W, add(mul(fa, 0.02 * r), mul(rad, 0.014 * r)))
        q1 = add(q0, add(mul(fa, 0.03 * r), mul(rad, 0.014 * r * (0.5 + spread))))
        q2 = add(q1, add(mul(fa, 0.026 * r), mul(rad, -0.016 * r)))
        knuckles += [sphere(0.0085 * r, q1, 8, 14)]
        fingers += [seg(q0, q1, 0.0072 * r, 0.0066 * r, 0.0, 0.0, 0.0015, 10),
                    seg(q1, q2, 0.0064 * r, 0.0042 * r, 0.0, 0.0, 0.0012, 10)]
    return palm, knuckles, fingers


def _forearm(E, W, up, r=1.0, spread=0.5):
    """A spare forearm with its claw (the drawer's): the elbow's hinge, the ivory shell, the wrist's ring."""
    fa = unit(tuple(y - x for x, y in zip(E, W)))
    n = unit(cross(fa, up))
    drum, caps = hinge(E, n, 0.024 * r, 0.046 * r)
    shell = seg(E, W, 0.021 * r, 0.018 * r, 0.008 * r, 0.004 * r)
    ring = torus(0.018 * r, 0.004 * r, add(W, mul(fa, -0.002)), fa, 20, 8)
    palm, kn, fi = claw(W, fa, up, r, spread)
    return [shell], [drum, palm, *kn], [caps, ring], fi


def _limbs(fl, yin, dr):
    """Spare robot forearms with their claws laid in a row across the tray (step 2: step 1's arms and legs lying at
    angles read as a heap), the claws toward the room, each a little turned."""
    import random
    rnd = random.Random(11)
    z = FLOOR + fl * CM + 0.0245
    xf = -(dr[1] - 4.0) * CM
    shells, joints, trims, fingers = [], [], [], []
    for k, y in enumerate((-0.165, -0.055, 0.055, 0.165)):
        dy = rnd.uniform(-0.02, 0.02)
        E = (xf + 0.25, y - dy, z)
        W = (xf + 0.09, y + dy, z)
        sh, jo, tr, fi = _forearm(E, W, (0.0, 0.0, 1.0), 1.0, 0.35 + 0.15 * (k % 2))
        shells += sh
        joints += jo
        trims += tr
        fingers += fi
    return [part("limb_shells", M(*shells), "ws_shell", 40.0), part("limb_joints", M(*joints), GRAPH, 40.0),
            part("limb_trims", M(*trims), EDGE, 40.0), part("limb_tips", M(*fingers), "ws_bronze", 40.0)]


def ws_drawer(args, layout):
    """A bench drawer pulled out 25 cm (`slot` top / low) with its contents (`fill` eyes / limbs)."""
    h0, h1 = BENCH["drawers"][1 if args["slot"] == "top" else 0]
    out, fl, yin, dr = _tray(h0, h1, BENCH["body"] + BENCH["pull"])
    out += (_eyes if args["fill"] == "eyes" else _limbs)(fl, yin, dr)
    return out


# --- the cradles and the sleepers ----------------------------------------------------------------------------------
CAB_TOP = FLOOR + CAB["top"] * CM


def ws_cradle(args, layout):
    """A cradle on the cabinet (origin under its centre): a graphite bowl Ø 54 x 18 with a groove round its wall and a
    chamfered lip, the bed Ø 44, a soft dark cushion dipped in its middle, the green ring on the lip."""
    R, H, rb = CRADLE["d"] / 200, CRADLE["h"] * CM, CRADLE["bed"] / 200
    o = (0.0, 0.0, CAB_TOP)
    bowl = [(rb, 0.05), (rb, H - 0.012), (rb + 0.006, H), (R - 0.008, H), (R, H - 0.008), (R, 0.098), (R - 0.004, 0.094),
            (R - 0.004, 0.084), (R - 0.001, 0.08), (R - 0.012, 0.02), (R - 0.03, 0.0), (rb - 0.02, 0.0), (rb - 0.02, 0.05),
            (rb, 0.05)]
    # step 2: a padded cushion (step 1's read as a flat disc): a fat rolled edge round a dished, tufted middle
    cushion = [(0.0, 0.079), (0.03, 0.0795), (0.06, 0.082), (0.09, 0.088), (0.12, 0.098), (0.145, 0.111),
               (0.165, 0.121), (0.18, 0.126), (0.195, 0.127), (0.207, 0.123), (0.215, 0.114), (rb - 0.002, 0.10),
               (rb - 0.002, 0.07), (rb - 0.002, 0.048), (0.0, 0.048)]
    pad = lambda r: next(z0 + (z1 - z0) * (r - r0) / (r1 - r0)   # noqa: E731
                         for (r0, z0), (r1, z1) in zip(cushion, cushion[1:]) if r0 <= r <= r1)
    # the tufts: six buttons sunk in shallow dimples on the slope, a stitched groove round the roll's foot
    tufts = [sphere(0.0065, (0.105 * math.cos(D(60 * k + 30)), 0.105 * math.sin(D(60 * k + 30)), CAB_TOP + pad(0.105) - 0.002),
                    6, 12) for k in range(6)]
    groove = torus(0.152, 0.0028, (0.0, 0.0, CAB_TOP + pad(0.152) + 0.0003), (0, 0, 1), 64, 6)
    rim = [(rb + 0.012, H - 0.003), (R - 0.012, H - 0.003), (R - 0.013, H + 0.004), (rb + 0.013, H + 0.004),
           (rb + 0.012, H - 0.003)]
    return [part("bowl", lathe(bowl, 64, o), GRAPH2, 35.0), part("cushion", lathe(cushion, 64, o), "ws_cushion", 60.0),
            part("tufts", M(*tufts), GRAPH, 60.0), part("seam", groove, GRAPH, 60.0),
            part("rim", lathe(rim, 64, o), "ws_green__rim", 35.0)]


def _sleeper(roll, yaw, seed):
    """The small round robot, canonical (face toward -x, up +z, centre at the origin), the main robot's family (step
    2): an ivory shell band round a dark core, two closed side shells on 2 mm seams, one small layered eye (a graphite
    bezel, a dark glass lens) shut as a dim green arc, a short antenna; then tilted face-up 22 deg, rolled and turned."""
    R = SLEEPER / 200
    fx = (-1.0, 0.0, 0.0)
    E_ANG = 17.0                                    # the eye's lens out to 17 deg round -x (D8, the main eye's ratio)
    parts = {"core": [sphere(R - 0.007, (0, 0, 0), 14, 28)],
             "shell": [lathe(zone(R, 0.006, 41.0, 139.0, 14, 0.0018), 64, (0, 0, 0), (0.0, 1.0, 0.0))],
             "caps": [lathe(zone(R, 0.006, 0.0, 38.0, 10, 0.0018), 48, (0, 0, 0), (0.0, s, 0.0)) for s in (-1, 1)],
             "bezel": [lathe([((R - 0.004) * math.sin(D(E_ANG - 0.5)), (R - 0.004) * math.cos(D(E_ANG - 0.5))),
                              ((R + 0.0035) * math.sin(D(E_ANG - 0.5)), (R + 0.0035) * math.cos(D(E_ANG - 0.5))),
                              ((R + 0.0045) * math.sin(D(E_ANG + 2.0)), (R + 0.0045) * math.cos(D(E_ANG + 2.0))),
                              ((R + 0.0025) * math.sin(D(E_ANG + 5.0)), (R + 0.0025) * math.cos(D(E_ANG + 5.0))),
                              ((R - 0.004) * math.sin(D(E_ANG + 5.0)), (R - 0.004) * math.cos(D(E_ANG + 5.0))),
                              ((R - 0.004) * math.sin(D(E_ANG - 0.5)), (R - 0.004) * math.cos(D(E_ANG - 0.5)))],
                             40, (0, 0, 0), fx)],
             "glass": [cap_lens(R, E_ANG, 0.0022, 0.005, (0, 0, 0), fx, 32, 5)],
             "lid": [], "antenna": []}
    # the shut eye: a lid arc sagging across the lens, 1 mm over the glass
    rv = R + 0.0022 + 0.001
    arc = []
    for i in range(15):
        u = -12.0 + 24.0 * i / 14
        v = -1.5 + 4.0 * (u / 12.0) ** 2
        arc.append((-rv * math.cos(D(v)) * math.cos(D(u)), rv * math.cos(D(v)) * math.sin(D(u)), rv * math.sin(D(v))))
    parts["lid"].append(G.tube(arc, 0.0019, 8))
    tip = (0.03, 0.0, R + 0.045)
    parts["antenna"] = [capsule((0.012, 0.0, R - 0.01), tip, 0.0035, 8)]
    pitch = rot((0.0, 1.0, 0.0), 22.0)
    r = mm(rot((0.0, 0.0, 1.0), yaw), mm(rot((1.0, 0.0, 0.0), roll), pitch))
    return parts, r, mv(r, tip)


def ws_sleeper(args, layout):
    """A small sleeping robot Ø 28 lying in its cradle's dip (origin under the cradle's centre)."""
    parts, r, tip = _sleeper(args.get("roll", 0.0), args.get("yaw", 0.0), args.get("seed", 0))
    c = (0.0, 0.0, CAB_TOP + 0.075 + SLEEPER / 200)
    mats = {"core": "ws_inner", "shell": "ws_shell", "caps": "ws_shell", "bezel": GRAPH2, "glass": "ws_glass",
            "lid": "ws_green__sleep", "antenna": "ws_shell2"}
    out = [part(k, moved(M(*v), r, c), mats[k], 40.0) for k, v in parts.items()]
    out.append(part("bead", sphere(0.0075, add(tip, c), 8, 14), "ws_green__sleep", 40.0))
    return out


# --- the main robot ------------------------------------------------------------------------------------------------
RC = (0.0, 0.0, FLOOR + ROBOT["h"] * CM)
RR = ROBOT["d"] / 200        # 0.30
SHELL_T, LINER_T = 0.006, 0.0035   # step 2: thin shells, ivory outside, a dark liner inside (0.5 mm behind)
CORE_Y = 0.205               # the core's flat mechanism plates (the bays' floors)
MECH_R = RR - 0.008          # every part of the bays' mechanism stays inside this sphere (clear of the shells)


def panel_p() -> float:
    """The side shells' edge (deg from the side axes; step 1's 45, r1's 57 read as two balloons)."""
    return ROBOT["panel"]


def band_p() -> float:
    return panel_p() + 1.6


def _panel_r(s):
    return rot((0.0, 0.0, 1.0), -s * ROBOT["open"])


def _panel_pivot(s):
    """The side shells hinge at their back edge, so the bays open toward the room as in the concept (step 2 tried
    front hinges: the shells' ivory outsides faced the room swept back like ears and hid the bays from every view but
    the bench's)."""
    return (RC[0] + RR * math.sin(D(panel_p())), RC[1] + s * RR * math.cos(D(panel_p())), RC[2])


def _band(R, t, name):
    secs = [lathe(zone(R, t, band_p(), 180.0 - band_p(), 12, 0.003 if R == RR else 0.0015), 16, RC, (0, 1, 0),
                  (-1, 0, 0), a0 + 0.6, a1 - 0.6)
            for a0, a1 in ((-48.0, 48.0), (48.0, 132.0), (132.0, 228.0), (228.0, 312.0))]
    return part(name, M(*secs), "ws_shell" if name == "shell" else "ws_inner", 30.0)


def ws_robot_body(args, layout):
    """The main robot's body (the collider): the dark core, flat at y +-CORE_Y under the side shells, and the ivory
    shell band (the sphere Ø 60 between the side shells) in four panels on 6 mm seams, its dark liner inside."""
    rc = RR - 0.014
    a = math.degrees(math.asin(CORE_Y / rc))
    core = [(0.0, -CORE_Y), (math.sqrt(rc ** 2 - CORE_Y ** 2), -CORE_Y)]
    core += [(rc * math.cos(D(-a + i * 2 * a / 16)), rc * math.sin(D(-a + i * 2 * a / 16))) for i in range(1, 16)]
    core += [(math.sqrt(rc ** 2 - CORE_Y ** 2), CORE_Y), (0.0, CORE_Y)]
    return [part("core", lathe(core, 48, RC, (0, 1, 0)), GRAPH, 35.0),
            _band(RR, SHELL_T, "shell"), _band(RR - SHELL_T - 0.0005, LINER_T, "liner")]


def _eye():
    """The eye Ø 16 toward the room, layered (step 2; step 1's flat discs read as a bull's-eye): a proud graphite
    bezel, a thin bronze trim ring, a dark glass dome, on it a cyan iris with a brighter inner ring and a dark limbal
    ring round the dark pupil, a soft highlight crescent and a glint."""
    ex = (-1.0, 0.0, 0.0)
    bezel = [(0.070, 0.262), (0.095, 0.262), (0.095, 0.287), (0.092, 0.297), (0.085, 0.303), (0.077, 0.304),
             (0.072, 0.300), (0.070, 0.292), (0.070, 0.262)]
    trim = [(0.0635, 0.272), (0.0705, 0.272), (0.0705, 0.300), (0.068, 0.3025), (0.0645, 0.300), (0.0635, 0.272)]
    Rd, apex = 0.20, 0.312   # the dome stands proud of the shell (at 0.300 the shell covered all but its middle)

    def on(r, lift=0.0):
        return apex - (Rd - math.sqrt(Rd * Rd - r * r)) + lift
    dome = [(0.0, apex)] + [(r, on(r)) for r in (0.012, 0.024, 0.036, 0.048, 0.058, 0.064)] + [(0.064, 0.27), (0.0, 0.27)]

    def ring(r0, r1, lift, steps=4):
        top = [(r0 + (r1 - r0) * i / steps, on(r0 + (r1 - r0) * i / steps, lift)) for i in range(steps + 1)]
        return top + [(r1, on(r1, -0.002)), (r0, on(r0, -0.002)), top[0]]
    glint = [(0.044, on(0.044, 0.0012)), (0.051, on(0.051, 0.0012)), (0.051, on(0.051, -0.001)),
             (0.044, on(0.044, -0.001)), (0.044, on(0.044, 0.0012))]
    dot = [(0.0, on(0.0, 0.0016)), (0.0042, on(0.0042, 0.0016)), (0.0042, on(0.0042, -0.002)), (0.0, on(0.0, -0.002))]
    return [part("eye_ring", lathe(bezel, 48, RC, ex), GRAPH2, 35.0), part("eye_trim", lathe(trim, 48, RC, ex), EDGE, 35.0),
            part("eye_glass", lathe(dome, 48, RC, ex), "ws_glass", 40.0),
            part("eye_iris", lathe(ring(0.0185, 0.032, 0.0011), 48, RC, ex), "ws_cyan__eye", 40.0),
            part("eye_inner", lathe(ring(0.014, 0.0185, 0.0014, 2), 48, RC, ex), "ws_cyan__pupil", 40.0),
            part("eye_limbal", lathe(ring(0.032, 0.0355, 0.0011, 2), 48, RC, ex), GRAPH, 40.0),
            part("eye_glint", M(lathe(glint, 12, RC, ex, (0.0, 0.0, 1.0), 25.0, 75.0),
                                lathe(dot, 12, add(RC, (0.0, 0.017, 0.019)), ex)), "ws_glint", 40.0)]


def _gear(c, ax, r, teeth, t, depth=0.008):
    """A toothed disc of radius r (teeth deep) round ax through c, t thick."""
    a = unit(ax)
    u = unit(cross(a, (0.0, 0.0, 1.0) if abs(a[2]) < 0.9 else (1.0, 0.0, 0.0)))
    v = cross(a, u)
    fr = G.Frame(c, u, v, a)
    pts = []
    for k in range(teeth):
        for f, rr in ((0.0, r - depth), (0.18, r - depth), (0.3, r), (0.7, r), (0.82, r - depth)):
            ang = 2 * math.pi * (k + f) / teeth
            pts.append((rr * math.cos(ang), rr * math.sin(ang)))
    return G.slab(fr, pts, 0.0, t)


def _bay(s):
    """One side's mechanism on its core plate (step 2: step 1's flat plate with one gear read empty): a gear train of
    three (the big gear on the plate, the pinion and the idler a layer out), hub caps, two pistons in their mounts, a
    small board with chips and a cyan light, a silver motor, and cables in four colours: two loops out of the bay and
    back, three hanging out of its lower edge to loose plugs under the body. Returns {material: [meshes]}."""
    ax = (0.0, s, 0.0)
    y0 = s * CORE_Y

    def at(x, dy, z):
        return (RC[0] + x, RC[1] + y0 + s * dy, RC[2] + z)

    def box(x0, x1, d0, d1, z0, z1, bev):   # a block on the plate, d0..d1 out of it
        return G.bbox(RC[0] + x0, RC[0] + x1, *sorted((RC[1] + y0 + s * d0, RC[1] + y0 + s * d1)),
                      RC[2] + z0, RC[2] + z1, bev)
    out = {BRONZE: [], EDGE: [], "int_silver_c": [], "ws_steel": [], GRAPH2: [], GRAPH: [], "ws_cyan__core": [],
           "ws_cable_a": [], "ws_cable_b": [], "ws_cable_c": [], "ws_cable_d": [], "plugs": []}
    gears = (((-0.03, 0.03), 0.072, 16, 0.0, 0.014), ((0.062, 0.079), 0.040, 10, 0.014, 0.011),
             ((-0.099, -0.043), 0.034, 9, 0.014, 0.011))
    for (x, z), r, n, dy, t in gears:
        out[BRONZE].append(_gear(at(x, dy - 0.0005, z), ax, r, n, t + 0.0005))
        out[EDGE].append(lathe([(0.0, 0.0), (r * 0.36, 0.0), (r * 0.36, 0.006), (r * 0.3, 0.009), (0.0, 0.009)], 20,
                               at(x, dy + t, z), ax))
    for (x0, z0), (x1, z1), (x2, z2) in (((0.02, -0.09), (0.11, -0.035), (0.15, -0.01)),
                                         ((-0.03, -0.13), (0.06, -0.115), (0.105, -0.10))):
        out["int_silver_c"].append(seg(at(x0, 0.016, z0), at(x1, 0.016, z1), 0.0135, 0.0135, 0.0, 0.0, 0.002, 16))
        out["ws_steel"].append(seg(at(x1, 0.016, z1), at(x2, 0.016, z2), 0.0065, 0.0065, -0.004, 0.0, 0.001, 12))
        for x, z in ((x0, z0), (x2, z2)):
            out[GRAPH2].append(box(x - 0.014, x + 0.014, -0.0005, 0.026, z - 0.014, z + 0.014, 0.002))
    # the board, its chips and its light
    out[GRAPH2].append(box(-0.14, -0.07, -0.0005, 0.006, 0.05, 0.12, 0.0015))
    for cx, cz, w, h in ((-0.13, 0.068, 0.014, 0.012), (-0.088, 0.106, 0.02, 0.01), (-0.085, 0.064, 0.012, 0.012)):
        out[GRAPH].append(box(cx - w / 2, cx + w / 2, 0.0055, 0.0095, cz - h / 2, cz + h / 2, 0.001))
    out["ws_cyan__core"].append(lathe([(0.0, 0.0), (0.011, 0.0), (0.011, 0.004), (0.008, 0.009), (0.0, 0.011)], 20,
                                      at(-0.115, 0.005, 0.098), ax))
    out["int_silver_c"].append(lathe([(0.0, -0.05), (0.022, -0.05), (0.024, -0.046), (0.024, 0.046), (0.022, 0.05),
                                      (0.0, 0.05)], 24, at(-0.01, 0.026, -0.105), (1, 0, 0)))
    cables = ("ws_cable_a", "ws_cable_b", "ws_cable_c", "ws_cable_d")
    for k, mat in enumerate(cables[:2]):   # loops out and back
        o = 0.02 * k
        pts = [(0.07 + o, 0.006, -0.03 + o), (0.06 + o, 0.08, -0.08), (0.02 + o, 0.07, -0.20 - o), (0.06 + o, 0.006, -0.15)]
        out[mat].append(G.tube([at(*p) for p in bez(pts, 16)], 0.0066, 8))
    for k, mat in enumerate(cables[1:]):   # hanging to loose plugs
        x = 0.03 * k - (0.005 if s > 0 else 0.0)
        end = (x + 0.015, 0.05 - 0.008 * k, -0.30 - 0.05 * k - (0.03 if s < 0 else 0.0))
        pts = [(x - 0.01, 0.004, -0.10 - 0.01 * k), (x - 0.01, 0.075, -0.14), (x, 0.075, -0.24), end]
        pl = bez(pts, 18)
        out[mat].append(G.tube([at(*p) for p in pl], 0.0062, 8))
        d = unit(tuple(b - a for a, b in zip(at(*pl[-2]), at(*pl[-1]))))
        out["plugs"].append(lathe([(0.0, 0.0), (0.0095, 0.0), (0.0095, 0.022), (0.006, 0.026), (0.0, 0.026)], 14,
                                at(*pl[-1]), d))
    return out


def _arm(s, sh, el, wr):
    """One arm (step 2, visibly below the body): a graphite shoulder ball in a bronze collar, the ivory upper arm, a
    graphite elbow hinge with bronze caps, the ivory forearm, a bronze wrist ring and a three-finger claw."""
    S_, E_, W_ = add(RC, sh), add(RC, el), add(RC, wr)
    up_d = unit(tuple(b - a for a, b in zip(S_, E_)))
    fa = unit(tuple(b - a for a, b in zip(E_, W_)))
    n = cross(up_d, fa)
    n = unit(n) if math.sqrt(sum(x * x for x in n)) > 1e-6 else (0.0, 1.0, 0.0)
    drum, caps = hinge(E_, n, 0.027, 0.054)
    shells = [seg(S_, E_, 0.027, 0.023, 0.02, 0.006), seg(E_, W_, 0.023, 0.02, 0.006, 0.004)]
    collar = torus(0.033, 0.006, add(S_, mul(up_d, 0.012)), up_d, 24, 8)
    ring = torus(0.0195, 0.0045, add(W_, mul(fa, -0.002)), fa, 20, 8)
    palm, kn, fi = claw(W_, fa, (1.0, 0.0, 0.0), 1.15, 0.55 if s > 0 else 0.3)
    return shells, [sphere(0.034, S_, 12, 24), drum, palm, *kn], [collar, caps, ring], fi


ARMS = {1: ((-0.04, 0.15, -0.245), (-0.12, 0.235, -0.355), (-0.135, 0.205, -0.41)),
        -1: ((-0.04, -0.15, -0.245), (-0.10, -0.245, -0.36), (-0.15, -0.225, -0.405))}


def ws_robot(args, layout):
    """The main robot's details (no collider): the layered eye toward the room, the crown and its knob (the hoist's
    claw grips it), the two thin side shells (ivory outside, dark liner inside) opened on their back hinges, the
    mechanism in each bay, the two arms hanging below the body."""
    out = _eye()
    crown = [(0.0, RR + 0.005), (0.05, RR + 0.005), (0.052, RR - 0.002), (0.05, RR - 0.012), (0.0, RR - 0.012)]
    neck = [(0.0, RR + 0.02), (0.018, RR + 0.02), (0.018, RR + 0.004), (0.0, RR + 0.004)]
    out += [part("crown", lathe(crown, 40, RC), EDGE, 35.0),
            part("knob", M(lathe(neck, 24, RC), sphere(0.034, add(RC, (0.0, 0.0, RR + 0.032)), 12, 24)), BRONZE, 35.0)]
    shells, liners, hinges = [], [], []
    for s in (-1, 1):
        ax = (0.0, s, 0.0)
        r, pv = _panel_r(s), _panel_pivot(s)
        shells.append(moved(lathe(zone(RR, SHELL_T, 0.0, panel_p(), 12, 0.003), 48, RC, ax), r, pivot=pv))
        liners.append(moved(lathe(zone(RR - SHELL_T - 0.0005, LINER_T, 0.0, panel_p() - 0.4, 12, 0.0015), 48, RC, ax),
                            r, pivot=pv))
        hinges.append(lathe([(0.0, -0.04), (0.011, -0.04), (0.012, -0.035), (0.012, 0.035), (0.011, 0.04), (0.0, 0.04)],
                            16, pv, (0, 0, 1)))
    out += [part("panels", M(*shells), "ws_shell", 30.0), part("panel_liners", M(*liners), "ws_inner", 30.0),
            part("hinges", M(*hinges), GRAPH2, 35.0)]
    mech: dict = {}
    for s in (-1, 1):
        for m, v in _bay(s).items():
            mech.setdefault(m, []).extend(v)
    names = {BRONZE: "gears", EDGE: "hubs", "int_silver_c": "motors", "ws_steel": "rods", GRAPH2: "mounts",
             GRAPH: "chips", "ws_cyan__core": "core_light", "plugs": "plugs"}
    out += [part(names.get(m, f"cables_{m[-1]}"), M(*v), GRAPH if m == "plugs" else m,
                 40.0 if m.startswith("ws_cable") else 35.0)
            for m, v in mech.items() if v]
    shells, joints, trims, fingers = [], [], [], []
    for s, (sh, el, wr) in ARMS.items():
        a, b, c, d = _arm(s, sh, el, wr)
        shells += a
        joints += b
        trims += c
        fingers += d
    out += [part("arms", M(*shells), "ws_shell", 40.0), part("joints", M(*joints), GRAPH, 40.0),
            part("collars", M(*trims), EDGE, 40.0), part("claws", M(*fingers), "ws_bronze", 40.0)]
    return out


# --- the hoist, the rail, the rug, the lamp ------------------------------------------------------------------------
def ws_hoist(args, layout):
    """The hoist over the robot (its frame, the rail along y; step 2, step 1's thin cable read weak): a chunky bronze
    carriage (30 x 17 x 12) under the rail with cheeks round it and four wheel hubs, a graphite motor drum on its room
    side, a short thick steel rod (Ø 4.4) with bronze collars down to the claw: a bronze hub (h 183..188) and three
    two-segment fingers on graphite knuckles whose pads grip the crown's knob ball."""
    rb = FLOOR + RAIL["bottom"] * CM
    rt = rb + RAIL["t"] * CM
    cl, cw, chh = (v * CM for v in HOIST["carriage"])
    body = G.bbox(-cw / 2, cw / 2, -cl / 2, cl / 2, rb - chh, rb - 0.008, 0.014)
    cheeks = M(G.bbox(-0.074, -0.058, -0.09, 0.09, rb - 0.03, rt + 0.012, 0.004),
               G.bbox(0.058, 0.074, -0.09, 0.09, rb - 0.03, rt + 0.012, 0.004))
    hubs = M(*[lathe([(0.0, 0.0), (0.022, 0.0), (0.024, 0.004), (0.024, 0.009), (0.0, 0.009)], 20,
                     (s * 0.074, y, rt - 0.01), (s, 0, 0)) for s in (-1, 1) for y in (-0.05, 0.05)])
    drum = lathe([(0.0, -0.09), (0.036, -0.09), (0.04, -0.084), (0.04, 0.084), (0.036, 0.09), (0.0, 0.09)], 28,
                 (-cw / 2 - 0.022, 0.0, rb - chh / 2 - 0.005), (0, 1, 0))
    drum_caps = M(*[lathe([(0.0, 0.0), (0.03, 0.0), (0.03, 0.006), (0.024, 0.009), (0.0, 0.009)], 24,
                          (-cw / 2 - 0.022, s * 0.0895, rb - chh / 2 - 0.005), (0, s, 0)) for s in (-1, 1)])
    c0, c1 = FLOOR + HOIST["clamp"][0] * CM, FLOOR + HOIST["clamp"][1] * CM
    rr = HOIST["rod"] / 2 * CM
    rod = lathe([(0.0, c1 - 0.004), (rr, c1 - 0.004), (rr, rb - chh + 0.004), (0.0, rb - chh + 0.004)], 20, (0, 0, 0))
    collars = M(lathe([(0.0, rb - chh - 0.026), (0.034, rb - chh - 0.026), (0.036, rb - chh - 0.022),
                       (0.036, rb - chh + 0.002), (0.0, rb - chh + 0.002)], 28, (0, 0, 0)),
                lathe([(0.0, c1 - 0.002), (0.03, c1 - 0.002), (0.03, c1 + 0.016), (0.026, c1 + 0.02), (0.0, c1 + 0.02)],
                      28, (0, 0, 0)))
    head = lathe([(0.0, c1), (0.05, c1), (0.058, c1 - 0.008), (0.058, c1 - 0.04), (0.046, c1 - 0.05), (0.0, c1 - 0.05)],
                 36, (0, 0, 0))
    kc = RC[2] + RR + 0.032          # the knob ball's centre (r 0.034)
    seg1, seg2, knuckles, pads = [], [], [], []
    for k in range(3):
        a = D(120 * k + 30)
        d = (math.cos(a), math.sin(a), 0.0)
        tn = (-math.sin(a), math.cos(a), 0.0)
        p0 = add(mul(d, 0.05), (0.0, 0.0, c1 - 0.034))
        p1 = add(mul(d, 0.088), (0.0, 0.0, c1 - 0.078))
        p2 = add(mul(d, 0.047), (0.0, 0.0, kc - 0.004))
        seg1.append(seg(p0, p1, 0.0115, 0.0105, 0.0, 0.0, 0.002, 12))
        seg2.append(seg(p1, p2, 0.0095, 0.0085, 0.0, 0.0, 0.002, 12))
        for p, r_ in ((p0, 0.013), (p1, 0.0125)):
            dr, cp = hinge(p, tn, r_, 0.03, 0.003, 16)
            knuckles += [dr, cp]
        pads.append(lathe([(0.0, 0.0), (0.012, 0.0), (0.012, 0.008), (0.009, 0.011), (0.0, 0.011)], 16,
                          add(p2, mul(d, 0.004)), mul(d, -1.0)))
    assert c0 < kc
    return [part("carriage", body, BRONZE2), part("cheeks", cheeks, BRONZE), part("hubs", hubs, GRAPH2, 35.0),
            part("drum", drum, GRAPH, 35.0), part("drum_caps", drum_caps, EDGE, 35.0),
            part("rod", rod, "ws_steel", 40.0), part("collars", collars, BRONZE, 35.0),
            part("clamp", head, BRONZE2, 35.0), part("jaws", M(*seg1, *seg2), EDGE, 40.0),
            part("knuckles", M(*knuckles), GRAPH, 35.0), part("pads", M(*pads), GRAPH2, 35.0)]


def rail_points():
    """The rail's arc in the west room's frame (theta mirrored from the drawing's east angles), (x, y) m per 2 deg."""
    a0, a1 = sorted(-t for t in RAIL["th"])
    n = int(round((a1 - a0) / 2.0))
    r = RAIL["r"] * CM
    return [(r * math.cos(D(a0 + (a1 - a0) * i / n)), r * math.sin(D(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def ws_rail(args, layout):
    """The ceiling rail (the room's frame): a bronze box section 10 wide x 8 tall from h 228 on an arc r 105 over
    theta 25..110 (west), chamfered, a glossy lip down each side, end stops, three hangers (flat bars) up into the
    slanted ceiling with their plates."""
    rb = FLOOR + RAIL["bottom"] * CM
    rt = rb + RAIL["t"] * CM
    w, ch = RAIL["w"] * CM / 2, 0.008
    r = RAIL["r"] * CM
    prof = [(-w, rb + ch), (-w + ch, rb), (w - ch, rb), (w, rb + ch), (w, rt - ch), (w - ch, rt), (-w + ch, rt), (-w, rt - ch)]
    rings = []
    for x, y in rail_points():
        a = math.atan2(y, x)
        rings.append([((r + q) * math.cos(a), (r + q) * math.sin(a), h) for q, h in prof])
    out = [part("rail", LN.loft(rings), BRONZE2, 30.0)]
    lips = []
    for q in (-w - 0.002, w - 0.002):
        lr = []
        for x, y in rail_points():
            a = math.atan2(y, x)
            lr.append([((r + q + dq) * math.cos(a), (r + q + dq) * math.sin(a), h) for dq, h in
                       ((0.0, rb + 0.024), (0.004, rb + 0.024), (0.004, rb + 0.032), (0.0, rb + 0.032))])
        lips.append(LN.loft(lr))
    out.append(part("lips", M(*lips), EDGE))
    stops = []
    for x, y in (rail_points()[0], rail_points()[-1]):
        a = math.atan2(y, x)
        stops.append(moved(G.bbox(-0.07, 0.07, -0.02, 0.02, rb - 0.025, rt + 0.004, 0.006),
                           rot((0, 0, 1), math.degrees(a)), (r * math.cos(a), r * math.sin(a), 0.0)))
    out.append(part("stops", M(*stops), BRONZE))
    bars, plates = [], []
    for th in RAIL["hangers"]:
        a = D(-th)
        cx, cy = r * math.cos(a), r * math.sin(a)
        ceil = FLOOR + S.tip_clear(cx)
        rr = rot((0, 0, 1), math.degrees(a))
        bars.append(moved(G.bbox(-0.025, 0.025, -0.01, 0.01, rt - 0.01, ceil + 0.03, 0.003), rr, (cx, cy, 0.0)))
        plates.append(moved(lathe([(0.0, ceil - 0.009), (0.05, ceil - 0.009), (0.055, ceil - 0.004), (0.055, ceil + 0.03),
                                   (0.0, ceil + 0.03)], 24, (0, 0, 0)), None, (cx, cy, 0.0)))
    out += [part("hangers", M(*bars), BRONZE), part("plates", M(*plates), EDGE, 35.0)]
    return out


def ws_rug(args, layout):
    """The rug under the robot: dark green pile Ø 66 x 1.1, its edge rolled, a darker border band 1.5 mm proud."""
    R = RUG["d"] / 200
    o = (0.0, 0.0, FLOOR)
    body = [(0.0, 0.0115), (R - 0.012, 0.0115), (R - 0.004, 0.0095), (R, 0.0055), (R - 0.003, 0.0012), (0.0, 0.0012)]
    band = [(R - 0.07, 0.011), (R - 0.045, 0.011), (R - 0.046, 0.013), (R - 0.069, 0.013), (R - 0.07, 0.011)]
    return [part("rug", lathe(body, 72, o), "ws_rug", 40.0), part("band", lathe(band, 72, o), "ws_rug2", 40.0)]


def lamp_target() -> tuple[float, float, float]:
    """The robot's centre in the lamp's frame (m)."""
    rl, al, fl = item("ws_lamp")
    rr, ar, _ = item("ws_robot")
    dx = rr * math.cos(D(ar)) - rl * math.cos(D(al))
    dy = rr * math.sin(D(ar)) - rl * math.sin(D(al))
    c, s = math.cos(D(-fl)), math.sin(D(-fl))
    return (dx * c - dy * s, dx * s + dy * c, RC[2])


def lamp_points():
    """The lamp's joints (its frame): the base on the bench's mat, the shoulder, the elbow, the head's pivot at h 140,
    and the head's aim (unit) at the robot."""
    top = FLOOR + (BENCH["top"] + BENCH["mat"]) * CM
    tx, ty, tz = lamp_target()
    hor = unit((tx, ty, 0.0))
    shoulder = (0.0, 0.0, top + 0.07)
    elbow = add(shoulder, add(mul(hor, -0.10), (0.0, 0.0, 0.40)))
    head = add((hor[0] * 0.24, hor[1] * 0.24, 0.0), (0.0, 0.0, FLOOR + LAMP["head"] * CM))
    aim = unit((tx - head[0], ty - head[1], tz - 0.1 - head[2]))   # at the open bays, a little under the centre
    return top, shoulder, elbow, head, aim


def ws_lamp(args, layout):
    """The articulated lamp on the bench (its frame, +x to the wall): a bronze base Ø 18 with a graphite turntable,
    twin bronze arms through graphite joint hubs to the head's pivot at h 140, the bronze shade aimed at the robot
    and its acid green lens."""
    top, sh, el, hd, aim = lamp_points()
    base = lathe([(0.0, top), (0.09, top), (0.09, top + 0.012), (0.082, top + 0.02), (0.0, top + 0.02)], 40, (0, 0, 0))
    turn = lathe([(0.0, top + 0.02), (0.04, top + 0.02), (0.04, top + 0.05), (0.034, top + 0.056), (0.0, top + 0.056)],
                 32, (0, 0, 0))
    side = unit(cross((0.0, 0.0, 1.0), unit((hd[0], hd[1], 0.0))))
    arms, hubs = [], []
    for s in (-1, 1):
        o = mul(side, s * 0.016)
        arms.append(capsule(add(sh, o), add(el, o), 0.0065, 10))
        arms.append(capsule(add(el, o), add(hd, o), 0.006, 10))
    post = capsule((0.0, 0.0, top + 0.05), sh, 0.012, 12)
    for p, r in ((sh, 0.02), (el, 0.018), (hd, 0.017)):
        hubs.append(lathe([(0.0, -0.024), (r, -0.024), (r, 0.024), (0.0, 0.024)], 20, p, side))
    # the shade: a cone from the pivot along aim, its mouth Ø 11 with a rolled lip, the green lens inside the mouth
    sh_back = add(hd, mul(aim, 0.015))
    shade = lathe([(0.0, -0.01), (0.024, -0.01), (0.03, 0.0), (0.05, 0.06), (0.056, 0.085), (0.058, 0.09),
                   (0.052, 0.09), (0.048, 0.082), (0.026, 0.01), (0.0, 0.01)], 36, sh_back, aim)
    lens = lathe([(0.0, 0.074), (0.047, 0.074), (0.047, 0.079), (0.0, 0.082)], 36, sh_back, aim)
    return [part("base", base, BRONZE, 35.0), part("turntable", turn, GRAPH, 35.0), part("post", post, BRONZE2, 35.0),
            part("arms", M(*arms), BRONZE, 35.0), part("hubs", M(*hubs), GRAPH, 35.0),
            part("shade", shade, BRONZE, 30.0), part("lens", lens, "ws_green__lamp", 35.0)]


def lamp_head_world_local() -> tuple[float, float, float]:
    """The lens's centre in the lamp's frame (for the room's lamp light)."""
    _, _, _, hd, aim = lamp_points()
    return add(add(hd, mul(aim, 0.015)), mul(aim, 0.08))
