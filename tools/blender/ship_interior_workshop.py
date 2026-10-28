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
HW, TAN = LN.HW, LN.TAN
BRONZE, BRONZE2, EDGE = LN.BRONZE, LN.BRONZE2, LN.EDGE
GRAPH, GRAPH2 = "lens_graphite", "lens_graphite2"
P = LN.P
M = L.merge

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
})
# the room's acid green (and the eyes' cyan): glows; ship.toml [light.mats] gives each its colour and strength, l 0
# (they light nothing: the room's green light is the "shop" lamp group's few omnis)
for _n, _c, _s in (("ws_green__strip", _GREEN, 8.0), ("ws_green__handle", _GREEN, 8.0), ("ws_green__rim", _GREEN, 8.0),
                   ("ws_green__lamp", _GREEN, 12.0), ("ws_green__sleep", _GREEN, 4.0), ("ws_cyan__eye", _CYAN, 6.0),
                   ("ws_cyan__pupil", _CYAN, 4.0)):
    L.MATERIALS[_n] = {"base": (*_c, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": _c, "strength": _s}

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
ROBOT = {"d": 60.0, "h": 145.0, "eye": 16.0, "hands": 95.0, "open": 30.0}
RAIL = {"r": 105.0, "th": (-110.0, -25.0), "bottom": 228.0, "w": 10.0, "t": 8.0, "hangers": (-100.0, -67.5, -35.0)}
HOIST = {"trolley": (20.0, 12.0), "cable": 190.0, "clamp": (177.0, 190.0)}
RUG = {"d": 66.0, "r": 110.0}   # the drawing's D80 at r 95 covered the floor lights' bars: D66 between them at r 110
LAMP = {"base": 18.0, "head": 140.0}
# the free items in the WEST room's frame (a_w = -a_e of the drawing): (piece, r m, a_w deg, face deg); the robot,
# cradles and lamp at the drawing's tip_w points (r, theta), the rug moved out to clear the floor lights
_LAMP_FACE = -LN.facet_mid(-100.0)
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


def stile(d0, d1, h0, h1, y_in, side, e=LN.SEAM):
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
    out = [part("toe", fblock(0.0, t1, 0.0, t0, seam), GRAPH)]
    if open_slot:
        s0, s1 = open_slot
        w = BENCH["open_w"] * CM / 2
        out += [part("body", M(fblock(0.0, body, t0, s0, seam, bot=0.0), fblock(0.0, body, s1, top - slab, seam)),
                     BRONZE2),
                part("bay", fblock(0.0, 18.0, s0, s1, seam), GRAPH),
                part("stiles", M(stile(18.0, body, s0, s1, w, -1), stile(18.0, body, s0, s1, w, 1)), BRONZE2)]
    else:
        out.append(part("body", fblock(0.0, body, t0, top - slab, seam), BRONZE2))
    yf = half(body + fr) - 0.0165
    fronts, bezels, bars = [], [], []
    for h0, h1 in drawers:
        if open_slot and (h0, h1) == (open_slot[0] + 1.0, open_slot[1] - 1.0):
            continue
        fronts.append(front(-yf, yf, h0, h1, body, body + fr))
        b, g = handle(h1 - 6.0, body + fr)
        bezels.append(b)
        bars.append(g)
    if fronts:
        out += [part("fronts", M(*fronts), BRONZE), part("pulls", M(*bezels), GRAPH),
                part("pull_lights", M(*bars), "ws_green__handle")]
    s0, s1 = K["strip"]
    out.append(part("strip", fblock(body - 0.1, body + 0.5, s0, s1, 1.0), "ws_green__strip"))
    out.append(part("top", fblock(0.0, K["d"], top - slab, top, 0.0, top=1.0, bot=0.4), BRONZE))
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
    b, g = handle(h1 - 6.0, d_front + fr)
    parts = [part("front", front(-yf, yf, h0, h1, d_front, d_front + fr), BRONZE),
             part("tray", M(*walls), BRONZE2),
             part("insert", G.bbox(-(d_front - 0.3) * CM, -(db + 1.5) * CM, -w + 0.015, w - 0.015,
                                   FLOOR + (hf + 0.5) * CM, FLOOR + fl * CM, 0.004), GRAPH2),
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


def _limb(base, ang, kind, s=1.0):
    """A spare arm or leg lying on the tray: a shell segment, a graphite joint, a second segment and a claw or a foot,
    in the tray's plane from base along ang (rad, in the x-y plane)."""
    dx, dy = math.cos(ang), math.sin(ang)
    bend = ang + (0.3 if kind == "arm" else -0.2)
    ex, ey = math.cos(bend), math.sin(bend)
    z = base[2]
    p0 = base
    p1 = (p0[0] + dx * 0.085 * s, p0[1] + dy * 0.085 * s, z)
    p2 = (p1[0] + ex * 0.075 * s, p1[1] + ey * 0.075 * s, z - 0.002)
    shells = [capsule(p0, p1, 0.016 * s, 12), capsule(p1, p2, 0.014 * s, 12)]
    joints = [sphere(0.019 * s, p0, 8, 14), sphere(0.018 * s, p1, 8, 14)]
    tips = []
    if kind == "arm":
        for k in (-1, 0, 1):
            a = bend + k * 0.45
            q0 = (p2[0] + math.cos(a) * 0.012, p2[1] + math.sin(a) * 0.012, z)
            q1 = (q0[0] + math.cos(a) * 0.022, q0[1] + math.sin(a) * 0.022, z)
            q2 = (q1[0] + math.cos(a - k * 0.6) * 0.016, q1[1] + math.sin(a - k * 0.6) * 0.016, z - 0.003)
            tips.append(G.tube([q0, q1, q2], 0.0055 * s, 8))
        joints.append(sphere(0.015 * s, p2, 8, 14))
    else:   # a foot: a rounded pad
        tips.append(lathe([(0.0, 0.012), (0.022, 0.011), (0.03, 0.006), (0.03, -0.006), (0.0, -0.007)], 18,
                          (p2[0] + ex * 0.02, p2[1] + ey * 0.02, z - 0.004), (0, 0, 1)))
        joints.append(sphere(0.016 * s, p2, 8, 14))
    return shells, joints, tips


def _limbs(fl, yin, dr):
    """Spare small hands and legs on the liner: three arms with claws, two legs with feet, a loose hand."""
    z = FLOOR + fl * CM + 0.017
    x0 = -(dr[1] - 5.0) * CM
    lay = [((x0, -0.18), D(8), "arm", 1.0), ((x0 - 0.01, -0.09), D(-5), "leg", 1.0), ((x0, 0.0), D(4), "arm", 0.95),
           ((x0 - 0.008, 0.09), D(-9), "leg", 1.0), ((x0 + 0.004, 0.18), D(6), "arm", 0.9)]
    shells, joints, tips = [], [], []
    for (x, y), a, kind, s in lay:
        sh, jo, ti = _limb((x, y, z), a, kind, s)
        shells += sh
        joints += jo
        tips += ti
    return [part("limb_shells", M(*shells), "ws_shell", 40.0), part("limb_joints", M(*joints), GRAPH, 40.0),
            part("limb_tips", M(*tips), BRONZE2, 40.0)]


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
    cushion = [(0.0, 0.086), (0.05, 0.088), (0.10, 0.104), (0.14, 0.122), (0.17, 0.127), (0.195, 0.122),
               (rb - 0.004, 0.108), (rb - 0.002, 0.07), (rb - 0.002, 0.048), (0.0, 0.048)]
    rim = [(rb + 0.012, H - 0.003), (R - 0.012, H - 0.003), (R - 0.013, H + 0.004), (rb + 0.013, H + 0.004),
           (rb + 0.012, H - 0.003)]
    return [part("bowl", lathe(bowl, 64, o), GRAPH2, 35.0), part("cushion", lathe(cushion, 48, o), "ws_cushion", 50.0),
            part("rim", lathe(rim, 64, o), "ws_green__rim", 35.0)]


def _sleeper(roll, yaw, seed):
    """The small round robot, canonical (face toward -x, up +z, centre at the origin): an ivory shell round a dark
    core, a recessed glossy visor with the shut eye's dim green line, two ear discs with a faint green ring, a short
    antenna; then tilted face-up 22 deg, rolled and turned."""
    R = SLEEPER / 200
    fx = (-1.0, 0.0, 0.0)
    parts = {"core": [sphere(R - 0.008, (0, 0, 0), 14, 28)],
             "shell": [lathe(zone(R, 0.006, 0.0, 116.0, 14, 0.0025), 48, (0, 0, 0), (1.0, 0.0, 0.0))],
             "visor": [lathe(zone(R - 0.003, 0.006, 0.0, 25.0, 8, 0.0015), 40, (0, 0, 0), fx)],
             "face": [lathe(zone(R, 0.006, 28.0, 64.0, 8, 0.002), 48, (0, 0, 0), fx)],
             "ears": [], "ear_caps": [], "ear_rings": [], "lid": [], "antenna": []}
    for s in (-1, 1):
        ax = (0.0, s, 0.0)
        y0 = math.sqrt(R * R - 0.042 ** 2) - 0.004
        parts["ears"].append(lathe([(0.0, y0), (0.044, y0), (0.044, R + 0.012), (0.04, R + 0.016), (0.0, R + 0.016)],
                                   32, (0, 0, 0), ax))
        parts["ear_caps"].append(lathe([(0.0, R + 0.015), (0.026, R + 0.015), (0.024, R + 0.02), (0.0, R + 0.02)], 28,
                                       (0, 0, 0), ax))
        parts["ear_rings"].append(lathe([(0.029, R + 0.014), (0.036, R + 0.014), (0.036, R + 0.0172),
                                         (0.029, R + 0.0172), (0.029, R + 0.014)], 32, (0, 0, 0), ax))
    # the shut eye: a short lid line sagging in its socket, 1.2 mm over the glass
    rv = R - 0.003 + 0.0012
    arc = []
    for i in range(13):
        u = -15.0 + 30.0 * i / 12
        v = -0.8 + 2.0 * (u / 15.0) ** 2
        arc.append((-rv * math.cos(D(v)) * math.cos(D(u)), rv * math.cos(D(v)) * math.sin(D(u)), rv * math.sin(D(v))))
    parts["lid"].append(G.tube(arc, 0.0026, 8))
    tip = (0.03, 0.0, R + 0.045)
    parts["antenna"] = [capsule((0.012, 0.0, R - 0.01), tip, 0.0035, 8)]
    pitch = rot((0.0, 1.0, 0.0), 22.0)
    r = mm(rot((0.0, 0.0, 1.0), yaw), mm(rot((1.0, 0.0, 0.0), roll), pitch))
    return parts, r, mv(r, tip)


def ws_sleeper(args, layout):
    """A small sleeping robot Ø 28 lying in its cradle's dip (origin under the cradle's centre)."""
    parts, r, tip = _sleeper(args.get("roll", 0.0), args.get("yaw", 0.0), args.get("seed", 0))
    c = (0.0, 0.0, CAB_TOP + 0.075 + SLEEPER / 200)
    mats = {"core": GRAPH, "shell": "ws_shell", "face": "ws_shell", "visor": "ws_socket", "ears": GRAPH2, "ear_caps": "ws_shell",
            "ear_rings": "ws_green__sleep", "lid": "ws_green__sleep", "antenna": "ws_shell2"}
    out = [part(k, moved(M(*v), r, c), mats[k], 40.0) for k, v in parts.items()]
    out.append(part("bead", sphere(0.0075, add(tip, c), 8, 14), "ws_green__sleep", 40.0))
    return out


# --- the main robot ------------------------------------------------------------------------------------------------
RC = (0.0, 0.0, FLOOR + ROBOT["h"] * CM)
RR = ROBOT["d"] / 200        # 0.30
PANEL_P = 45.0               # the side panels' edge (deg from the side axes; r1's 57 read as two balloons)
BAND_P = 46.6                # the shell band's edge
HINGE_X = RR * math.sin(D(PANEL_P))
HINGE_Y = RR * math.cos(D(PANEL_P))
CORE_Y = 0.19                # the core's flat mechanism plates


def _panel_r(s):
    return rot((0.0, 0.0, 1.0), -s * ROBOT["open"])


def _panel_pivot(s):
    return (RC[0] + HINGE_X, RC[1] + s * HINGE_Y, RC[2])


def ws_robot_body(args, layout):
    """The main robot's body (the collider): the dark core, flat at y +-0.215 under the side panels, and the ivory
    shell band (the sphere Ø 60 between the side panels) in four panels with 6 mm seams; the eye's socket in the front
    panel."""
    core = [(0.0, -CORE_Y), (math.sqrt((RR - 0.014) ** 2 - CORE_Y ** 2), -CORE_Y)]
    core += [((RR - 0.014) * math.cos(D(a)), (RR - 0.014) * math.sin(D(a)))
             for a in [-math.degrees(math.asin(CORE_Y / (RR - 0.014))) + i * 2 * math.degrees(math.asin(CORE_Y / (RR - 0.014))) / 16
                       for i in range(1, 16)]]
    core += [(math.sqrt((RR - 0.014) ** 2 - CORE_Y ** 2), CORE_Y), (0.0, CORE_Y)]
    band = zone(RR, 0.01, BAND_P, 180.0 - BAND_P, 12, 0.003)
    secs = [lathe(band, 16, RC, (0, 1, 0), (-1, 0, 0), a0 + 0.6, a1 - 0.6)
            for a0, a1 in ((-48.0, 48.0), (48.0, 132.0), (132.0, 228.0), (228.0, 312.0))]
    return [part("core", lathe(core, 48, RC, (0, 1, 0)), GRAPH, 35.0),
            part("shell", M(*secs), "ws_shell", 30.0)]


def _eye():
    ex = (-1.0, 0.0, 0.0)
    ring = [(0.068, 0.27), (0.094, 0.27), (0.094, 0.286), (0.088, 0.297), (0.08, 0.3), (0.073, 0.299), (0.068, 0.293),
            (0.068, 0.27)]
    Rd, apex = 0.243, 0.306
    dome = [(0.0, apex)] + [(r, apex - (Rd - math.sqrt(Rd * Rd - r * r))) for r in (0.02, 0.04, 0.055, 0.069)]
    dome += [(0.069, 0.275), (0.0, 0.275)]

    def on(r, lift):
        return apex - (Rd - math.sqrt(Rd * Rd - r * r)) + lift
    # r3: an iris round a dark pupil (r1's and r2's rings round a dot read as a target)
    iris = [(0.017, on(0.017, 0.0011)), (0.03, on(0.03, 0.0011)), (0.043, on(0.043, 0.0011)), (0.05, on(0.05, 0.0011)),
            (0.05, on(0.05, -0.002)), (0.017, on(0.017, -0.002)), (0.017, on(0.017, 0.0011))]
    dot = [(0.0, on(0.0, 0.0013)), (0.0045, on(0.0045, 0.0013)), (0.0045, on(0.0045, -0.002)), (0.0, on(0.0, -0.002))]
    return [part("eye_ring", lathe(ring, 48, RC, ex), GRAPH2, 35.0), part("eye_glass", lathe(dome, 48, RC, ex), "ws_glass", 40.0),
            part("eye_iris", lathe(iris, 48, RC, ex), "ws_cyan__eye", 40.0),
            part("eye_dot", lathe(dot, 16, add(RC, (0.0, 0.016, 0.018)), ex), "ws_shell", 40.0)]


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


def _arm(s, sh, el, wr):
    """One arm: a graphite shoulder ball with a bronze collar, the upper arm and forearm (ivory), a graphite elbow and
    wrist, three bronze claw fingers curled in."""
    c = lambda p: add(RC, p)   # noqa: E731
    S_, E_, W_ = c(sh), c(el), c(wr)
    fa = unit(tuple(b - a for a, b in zip(E_, W_)))
    shells = [capsule(S_, E_, 0.022, 14), capsule(E_, W_, 0.02, 14)]
    joints = [sphere(0.033, S_, 10, 20), sphere(0.027, E_, 10, 20), sphere(0.021, W_, 8, 16)]
    collar = torus(0.031, 0.006, S_, tuple(b - a for a, b in zip(S_, E_)), 24, 8)
    u = unit(cross(fa, (1.0, 0.0, 0.0)))
    v = cross(fa, u)
    fingers = []
    for k in range(3):
        a = D(120 * k + 30 * s)
        rad = add(mul(u, math.cos(a)), mul(v, math.sin(a)))
        q0 = add(W_, add(mul(fa, 0.012), mul(rad, 0.012)))
        q1 = add(q0, add(mul(fa, 0.022), mul(rad, 0.009)))
        q2 = add(q1, add(mul(fa, 0.018), mul(rad, -0.011)))
        fingers.append(G.tube(bez([q0, q1, q2], 4), 0.0058, 8))
    return shells, joints, [collar], fingers


ARMS = {1: ((-0.02, 0.135, -0.255), (-0.06, 0.20, -0.375), (-0.05, 0.19, -0.444)),
        -1: ((-0.02, -0.135, -0.255), (-0.09, -0.18, -0.37), (-0.12, -0.16, -0.439))}


def ws_robot(args, layout):
    """The main robot's details (no collider): the eye Ø 16 toward the room (a graphite socket ring, a dark glass dome,
    a dim cyan iris and centre dot), the crown knob the hoist's clamp holds, the two side panels opened 30 deg on their
    back hinges, the mechanism in each bay (a bronze gear and pinion, a hub, a silver motor, three cables looping out
    and back) and the two arms hanging to h 95."""
    out = _eye()
    # the crown: a bronze flange, neck and knob on the top panel
    crown = [(0.0, RR + 0.005), (0.05, RR + 0.005), (0.052, RR - 0.002), (0.05, RR - 0.012), (0.0, RR - 0.012)]
    knob = [(0.0, RR + 0.035), (0.026, RR + 0.035), (0.032, RR + 0.03), (0.032, RR + 0.022), (0.02, RR + 0.018),
            (0.02, RR + 0.004), (0.0, RR + 0.004)]
    out += [part("crown", lathe(crown, 40, RC), EDGE, 35.0), part("knob", lathe(knob, 32, RC), BRONZE, 35.0)]
    panels, hinges, gears, hubs, motors = [], [], [], [], []
    cables = {"ws_cable_a": [], "ws_cable_b": [], "ws_cable_c": []}
    for s in (-1, 1):
        ax = (0.0, s, 0.0)
        cap = lathe(zone(RR, 0.01, 0.0, PANEL_P, 12, 0.003), 48, RC, ax)
        panels.append(moved(cap, _panel_r(s), pivot=_panel_pivot(s)))
        hp = _panel_pivot(s)
        hinges.append(lathe([(0.0, -0.035), (0.011, -0.035), (0.012, -0.03), (0.012, 0.03), (0.011, 0.035), (0.0, 0.035)],
                            16, hp, (0, 0, 1)))
        y = s * CORE_Y
        y0 = y - s * 0.0005   # sunk half a mm into the plate
        gears.append(_gear((RC[0] - 0.01, RC[1] + y0, RC[2] + 0.01), ax, 0.085, 18, 0.016))
        gears.append(_gear((RC[0] + 0.095, RC[1] + y0, RC[2] + 0.085), ax, 0.045, 11, 0.012))
        hubs.append(lathe([(0.0, 0.0), (0.03, 0.0), (0.03, 0.026), (0.024, 0.032), (0.0, 0.032)], 24,
                          (RC[0] - 0.01, RC[1] + y, RC[2] + 0.01), ax))
        hubs.append(lathe([(0.0, 0.0), (0.016, 0.0), (0.016, 0.02), (0.0, 0.02)], 16,
                          (RC[0] + 0.095, RC[1] + y, RC[2] + 0.085), ax))
        motors.append(lathe([(0.0, -0.065), (0.028, -0.065), (0.032, -0.06), (0.032, 0.06), (0.028, 0.065), (0.0, 0.065)],
                            24, (RC[0] + 0.0, RC[1] + s * (CORE_Y + 0.031), RC[2] - 0.115), (1, 0, 0)))
        for k, mat in enumerate(cables):
            o = 0.018 * (k - 1)
            sag = 0.31 + 0.035 * k + (0.02 if s > 0 else 0.0)
            pts = [(0.06 + o, s * (CORE_Y + 0.005), -0.04 + o), (0.04 + o, s * 0.33, -0.10),
                   (0.0 + o, s * 0.30, -sag - 0.06), (0.06 + o, s * 0.12, -sag), (0.07 + o, s * 0.1, -0.22)]
            cables[mat].append(G.tube([add(RC, p) for p in bez(pts, 18)], 0.0068, 8))
    out += [part("panels", M(*panels), "ws_shell", 30.0), part("hinges", M(*hinges), GRAPH2, 35.0),
            part("gears", M(*gears), BRONZE), part("hubs", M(*hubs), EDGE, 35.0),
            part("motors", M(*motors), "int_silver_c", 35.0)]
    out += [part(f"cables_{m[-1]}", M(*v), m, 40.0) for m, v in cables.items()]
    shells, joints, collars, fingers = [], [], [], []
    for s, (sh, el, wr) in ARMS.items():
        a, b, c, d = _arm(s, sh, el, wr)
        shells += a
        joints += b
        collars += c
        fingers += d
    out += [part("arms", M(*shells), "ws_shell", 40.0), part("joints", M(*joints), GRAPH, 40.0),
            part("collars", M(*collars), EDGE, 40.0), part("claws", M(*fingers), BRONZE2, 40.0)]
    return out


# --- the hoist, the rail, the rug, the lamp ------------------------------------------------------------------------
def ws_hoist(args, layout):
    """The hoist over the robot (its frame): the trolley (20 x 12, bronze, its cheeks round the rail and four wheel
    hubs), the graphite cable drum, the steel cable down to h 190, a shackle and the clamp (h 177..190) whose three
    jaws hold the crown's knob."""
    rb = FLOOR + RAIL["bottom"] * CM
    rt = rb + RAIL["t"] * CM
    L2, W2 = HOIST["trolley"][0] * CM / 2, HOIST["trolley"][1] * CM / 2
    body = G.bbox(-W2, W2, -L2, L2, rb - 0.085, rb - 0.006, 0.008)
    cheeks = M(L.box(-W2 - 0.006, -W2 + 0.004, -L2 + 0.015, L2 - 0.015, rb - 0.03, rt - 0.004),
               L.box(W2 - 0.004, W2 + 0.006, -L2 + 0.015, L2 - 0.015, rb - 0.03, rt - 0.004))
    hubs = M(*[lathe([(0.0, 0.0), (0.02, 0.0), (0.022, 0.004), (0.022, 0.008), (0.0, 0.008)], 20,
                     (s * (W2 + 0.006), y, rb + 0.035), (s, 0, 0)) for s in (-1, 1) for y in (-0.055, 0.055)])
    drum = lathe([(0.0, -0.07), (0.034, -0.07), (0.034, -0.062), (0.028, -0.058), (0.028, 0.058), (0.034, 0.062),
                  (0.034, 0.07), (0.0, 0.07)], 24, (0.0, 0.0, rb - 0.118), (0, 1, 0))
    c0, c1 = FLOOR + HOIST["clamp"][0] * CM, FLOOR + HOIST["clamp"][1] * CM
    cable = G.tube([(0.0, 0.0, rb - 0.15), (0.0, 0.0, c1 + 0.028)], 0.005, 10)
    shackle = torus(0.016, 0.0045, (0.0, 0.0, c1 + 0.016), (1, 0, 0), 20, 8)
    head = lathe([(0.0, c1), (0.034, c1), (0.04, c1 - 0.006), (0.04, c1 - 0.04), (0.03, c1 - 0.05), (0.0, c1 - 0.05)], 6,
                 (0, 0, 0))
    jaws = []
    knob_r, knob_top = 0.032, RC[2] + RR + 0.035
    for k in range(3):
        a = D(120 * k + 30)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(0.026 * ca, 0.026 * sa, c1 - 0.045), (0.05 * ca, 0.05 * sa, c1 - 0.075), (0.047 * ca, 0.047 * sa, c0 + 0.016),
               ((knob_r + 0.007) * ca, (knob_r + 0.007) * sa, c0 + 0.004), ((knob_r + 0.004) * ca, (knob_r + 0.004) * sa, c0)]
        jaws.append(G.tube(bez(pts[:3], 6) + pts[3:], 0.0075, 8))
    assert c0 < knob_top
    return [part("trolley", body, BRONZE), part("cheeks", cheeks, BRONZE2), part("hubs", hubs, GRAPH2, 35.0),
            part("drum", drum, GRAPH, 35.0), part("cable", cable, "ws_steel", 40.0),
            part("shackle", shackle, "ws_steel", 40.0), part("clamp", head, BRONZE2), part("jaws", M(*jaws), EDGE, 40.0)]


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
        bars.append(moved(L.box(-0.02, 0.02, -0.0075, 0.0075, rt - 0.01, ceil + 0.03), rr, (cx, cy, 0.0)))
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
