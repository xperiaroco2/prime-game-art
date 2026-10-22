"""The hull's fittings (art #263, details 2; docs/ship.md "Details 2"): sparse, purposeful details on the hull P, each
piece built in the plan frame and placed at the origin. Every fitting sits on the live hull (ship_hull_shape.heights):
its local frame is the hull's facet there (the outward normal from the heights' slope), so it moves with the shape.

- portholes: three a side on the tail's flank (the steep face between the body's top and the fin's) behind the
  lenses, where no room lies behind the skin: a silver ring frame and dark tinted glass with a faint warm glow
  (ext_porthole, opaque: it never reads as a hole into nothing);
- tail_vents: two grilles of dark slats in a frame on the tail's top, just ahead of the pods;
- hump_sensors: a short antenna mast and a small sensor dome on the hump's centre line, behind the canopies;
- service_hatches: inset panel outlines with a handle notch, one on each fin's top, one on the belly;
- hazard_stripes: yellow-and-dark stripes on the ramp's side rails and across the mouth's floor edge."""

from __future__ import annotations

import math

import ship_hull as H
import ship_hull_shape as S
import ship_lib as L

L.MATERIALS.update({
    # details 2: opaque dark warm glass with a faint inner glow (0.07; details 3: 0.05 round a warm core) ([light.mats] l 0: it lights nothing)
    "ext_porthole": {"base": (0.012, 0.014, 0.018, 1.0), "metallic": 0.0, "roughness": 0.05,
                     "emission": (1.0, 0.55, 0.25), "strength": 0.05},
    # details 3: the glow is a soft warm core (0.55 of the glass, 4 mm over it) in the dark glossy glass: the whole
    # disc at 0.2 read as a flat brown disc; the core averages about 0.2 over the glass
    "ext_porthole_core": {"base": (0.03, 0.025, 0.02, 1.0), "metallic": 0.0, "roughness": 0.05,
                          "emission": (1.0, 0.62, 0.3), "strength": 0.6},
    "ext_dome": {"base": (0.05, 0.06, 0.07, 1.0), "metallic": 0.3, "roughness": 0.1},
    "ext_hazard": {"base": (0.92, 0.66, 0.06, 1.0), "metallic": 0.05, "roughness": 0.55},
    "ext_hazard_dark": {"base": (0.035, 0.035, 0.04, 1.0), "metallic": 0.3, "roughness": 0.6},
})

PORT_Y = (5.6, 6.8, 8.0)        # the portholes' plan y on each flank (the lens rims end at y 3.75, the pods' noses 9.6)
PORT_R = (0.17, 0.225, 0.26)    # the glass, the ring's crown and its flange (outer radii): about 0.35 m of glass
VENTS = [(1.15, 8.55)]          # mirrored: the vents' centres on the tail's top
VENT = (0.7, 0.42, 6)           # length along the ship, width, slats
MAST = (0.0, -1.6, 0.75)        # the antenna mast on the hump's centre line: x, y, height
DOME = (0.0, -2.9, 0.16)        # the sensor dome: x, y, radius
HATCHES = [("top", 5.6, 4.4, 0.9, 0.6), ("top", -5.6, 4.4, 0.9, 0.6), ("bottom", 0.0, 8.6, 0.8, 0.55)]   # clear of the
#   fin's plate seams (at x 6.2 one ran down the hatch)


def surface(x: float, y: float, side: str = "top", d: float = 0.03):
    """The hull's point over (or under) plan (x, y) and its outward unit normal there (the heights' slope)."""
    k = 0 if side == "top" else 1

    def h(px, py):
        return S.heights(px, py)[k]
    gx = (h(x + d, y) - h(x - d, y)) / (2 * d)
    gy = (h(x, y + d) - h(x, y - d)) / (2 * d)
    n = H._norm((-gx, -gy, 1.0) if k == 0 else (gx, gy, -1.0))
    return (x, y, h(x, y)), n


def frame(n, along=(0.0, 1.0, 0.0)):
    """A tangent frame (u, v) on the facet with normal n: u is `along` laid into the facet, v = n x u."""
    a = H._sub(along, H._lerp((0, 0, 0), n, sum(along[i] * n[i] for i in range(3))))
    u = H._norm(a)
    return u, H._cross(n, u)


def _place(vf, o, u, v, n):
    verts, faces = vf
    return [tuple(o[i] + a * u[i] + b * v[i] + c * n[i] for i in range(3)) for a, b, c in verts], faces


def _annulus(r0, r1, c0, c1, k=24):
    """A closed ring (local: a, b in the facet, c out), radii r0..r1, from c0 to c1."""
    v = [(r * math.cos(2 * math.pi * i / k), r * math.sin(2 * math.pi * i / k), c)
         for c in (c0, c1) for r in (r0, r1) for i in range(k)]
    f = []
    for i in range(k):
        j = (i + 1) % k
        ib, ob, it, ot = i, k + i, 2 * k + i, 3 * k + i
        jb, jo, jt, jot = j, k + j, 2 * k + j, 3 * k + j
        f += [(ib, jb, jo, ob), (it, ot, jot, jt), (ob, jo, jot, ot), (ib, it, jt, jb)]
    return v, f


def _disc(r, c0, c1, k=24):
    v, f = L.disc(r, k, c0, c1)
    return v, f + [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)] if len(f) == 2 else f


def _lbox(a0, a1, b0, b1, c0, c1):
    return L.box(a0, a1, b0, b1, c0, c1)


def porthole_spots():
    """[(centre, normal)] of every porthole: on each flank at PORT_Y, where the hull's top is midway between the
    body's (x 2.5) and the fin's (x 5.0), found by bisection."""
    out = []
    for s in (1, -1):
        for y in PORT_Y:
            mid = (S.heights(2.5, y)[0] + S.heights(5.0, y)[0]) / 2
            lo, hi = 2.5, 5.0
            for _ in range(40):
                x = (lo + hi) / 2
                lo, hi = (x, hi) if S.heights(x, y)[0] > mid else (lo, x)
            out.append(surface(s * (lo + hi) / 2, y))
    return out


def portholes(args: dict, layout: dict) -> list:
    """details 2: the tail's portholes (plan frame): a bright silver crown 4.5 cm proud on a darker flange, a dark
    bezel round the glass and the dark warm glass 4.5 cm under the crown (all 3 cm into the skin)."""
    ring, flanges, bezels, glass, core = [], [], [], [], []
    g, crown, flange = PORT_R
    for o, n in porthole_spots():
        u, v = frame(n)
        ring.append(_place(_annulus(g + 0.015, crown, -0.03, 0.045), o, u, v, n))
        flanges.append(_place(_annulus(crown - 0.01, flange, -0.03, 0.015), o, u, v, n))
        bezels.append(_place(_annulus(g - 0.005, g + 0.017, -0.03, 0.02), o, u, v, n))
        glass.append(_place(_disc(g, -0.04, 0.0), o, u, v, n))
        core.append(_place(_disc(0.55 * g, -0.01, 0.004), o, u, v, n))
    return [L.part("porthole_ring", *L.merge(*ring), "ext_silver_b"),
            L.part("porthole_flange", *L.merge(*flanges), "ext_silver_c"),
            L.part("porthole_bezel", *L.merge(*bezels), "ext_frame"),
            L.part("porthole_glass", *L.merge(*glass), "ext_porthole"),
            L.part("porthole_core", *L.merge(*core), "ext_porthole_core")]


def vent_spots():
    return [surface(s * x, y) for x, y in VENTS for s in (1, -1)]


def tail_vents(args: dict, layout: dict) -> list:
    """details 2: two grilles on the tail's top: a silver frame 3 cm proud, a dark well and VENT[2] slats tilted
    35 deg aft."""
    length, width, n_slat = VENT
    hl, hw, t = length / 2, width / 2, 0.035
    frames, wells, slats = [], [], []
    for o, n in vent_spots():
        u, v = frame(n)
        for b in (_lbox(-hl, hl, -hw, -hw + t, -0.02, 0.03), _lbox(-hl, hl, hw - t, hw, -0.02, 0.03),
                  _lbox(-hl, -hl + t, -hw, hw, -0.02, 0.03), _lbox(hl - t, hl, -hw, hw, -0.02, 0.03)):
            frames.append(_place(b, o, u, v, n))
        wells.append(_place(_lbox(-hl + t, hl - t, -hw + t, hw - t, -0.02, 0.004), o, u, v, n))
        step = (length - 2 * t) / n_slat
        for i in range(n_slat):
            a = -hl + t + step * (i + 0.5)
            ca, sa = math.cos(math.radians(35)), math.sin(math.radians(35))
            c = (a, 0.0, 0.014)
            ax, ay, az = (0.045 * ca, 0.0, 0.045 * sa), (0.0, hw - t - 0.005, 0.0), (-0.006 * sa, 0.0, 0.006 * ca)
            slats.append(_place(H._obox(c, ax, ay, az), o, u, v, n))
    return [L.part("vent_frame", *L.merge(*frames), "ext_silver_c"), L.part("vent_well", *L.merge(*wells), "ext_seam"),
            L.part("vent_slats", *L.merge(*slats), "ext_frame")]


def hump_sensors(args: dict, layout: dict) -> list:
    """details 2: on the hump's centre line behind the canopies: a short antenna mast (a base plate, a slim rod
    MAST[2] high with two small collars and a dark cap) and a sensor dome (a silver collar, a dark glossy dome)."""
    mx, my, mh = MAST
    o, n = surface(mx, my)
    u, v = frame(n)
    base = _place(_disc(0.11, -0.03, 0.035, 12), o, u, v, n)
    foot = H._add(o, n, 0.03)
    top = H._add(foot, (0.0, 0.0, 1.0), mh)
    rods = [H._rod(foot, top, 0.022, 10), H._rod(H._add(foot, (0.0, 0.0, 1.0), 0.0), H._add(foot, (0.0, 0.0, 1.0), 0.18),
                                                0.04, 10)]
    for f, r in ((0.55, 0.045), (0.7, 0.032)):   # two small collars up the rod (a cross-spar read as a cross)
        c = H._add(foot, (0.0, 0.0, 1.0), mh * f)
        rods.append(H._rod(H._add(c, (0.0, 0.0, 1.0), -0.012), H._add(c, (0.0, 0.0, 1.0), 0.012), r, 10))
    cap = H._rod(H._add(top, (0.0, 0.0, 1.0), -0.01), H._add(top, (0.0, 0.0, 1.0), 0.04), 0.03, 10)
    dx, dy, dr = DOME
    o2, n2 = surface(dx, dy)
    u2, v2 = frame(n2)
    collar = _place(_disc(dr + 0.04, -0.03, 0.05, 24), o2, u2, v2, n2)
    prof = [(dr * math.cos(math.radians(a)), dr * math.sin(math.radians(a))) for a in range(0, 76, 15)]
    dv, df = [], []
    k = 24
    for r, z in prof:
        dv += [(r * math.cos(2 * math.pi * i / k), r * math.sin(2 * math.pi * i / k), 0.04 + z) for i in range(k)]
    for j in range(len(prof) - 1):
        for i in range(k):
            a, b = j * k + i, j * k + (i + 1) % k
            df.append((a, b, b + k, a + k))
    df.append(tuple(range(k - 1, -1, -1)))
    df.append(tuple(range((len(prof) - 1) * k, len(prof) * k)))
    dome = _place((dv, df), o2, u2, v2, n2)
    return [L.part("mast_base", *L.merge(base, _place(_annulus(0.06, 0.08, 0.03, 0.06, 12), o, u, v, n)),
                   "ext_silver_c"),
            L.part("mast_rod", *L.merge(*rods), "ext_silver_b"), L.part("mast_cap", *cap, "ext_frame"),
            L.part("dome_collar", *collar, "ext_silver_c"), L.part("dome", *dome, "ext_dome")]


def hatch_spots():
    return [(side, *surface(x, y, side), length, width) for side, x, y, length, width in HATCHES]


def service_hatches(args: dict, layout: dict) -> list:
    """details 2: service hatches as inset panel outlines (a dark groove 2 cm wide, 3 mm proud), a handle notch at
    one end (a dark recess with a silver grip) and four small bolts."""
    grooves, notches, grips, bolts = [], [], [], []
    for _side, o, n, length, width in hatch_spots():
        u, v = frame(n)
        hl, hw, t = length / 2, width / 2, 0.01
        for b in (_lbox(-hl, hl, -hw - t, -hw + t, -0.01, 0.003), _lbox(-hl, hl, hw - t, hw + t, -0.01, 0.003),
                  _lbox(-hl - t, -hl + t, -hw, hw, -0.01, 0.003), _lbox(hl - t, hl + t, -hw, hw, -0.01, 0.003)):
            grooves.append(_place(b, o, u, v, n))
        notches.append(_place(_lbox(hl - 0.11, hl - 0.06, -0.08, 0.08, -0.01, 0.0035), o, u, v, n))
        grips.append(_place(_lbox(hl - 0.095, hl - 0.075, -0.06, 0.06, -0.01, 0.009), o, u, v, n))
        for a in (-hl + 0.06, hl - 0.06):
            for b in (-hw + 0.06, hw - 0.06):
                bolts.append(_place(L.disc(0.016, 8, -0.01, 0.006), H._add(H._add(o, u, a), v, b), u, v, n))
    return [L.part("hatch_groove", *L.merge(*grooves, *notches), "ext_seam"),
            L.part("hatch_grip", *L.merge(*grips), "ext_silver_b"), L.part("hatch_bolts", *L.merge(*bolts), "hull_silver")]


def _stripes(o, a_dir, b_dir, n, length, width, c0, period=0.2, slant=1.0):
    """A dark strip `length` along a_dir, `width` across b_dir from o (its centre line's start), and yellow
    parallelograms on it every `period`, slanted 45 deg (slant +-1), 2 mm proud of the dark."""
    def p(a, b, c):
        return tuple(o[i] + a * a_dir[i] + b * b_dir[i] + c * n[i] for i in range(3))
    hw = width / 2
    dark = ([p(a, b, c) for c in (c0, c0 + 0.003) for b in (-hw, hw) for a in (0.0, length)],
            [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    yel = []
    a = 0.02
    while a + period / 2 + width <= length - 0.02:
        q = [(a, -hw), (a + period / 2, -hw), (a + period / 2 + width, hw), (a + width, hw)]
        if slant < 0:
            q = [(qa, -qb) for qa, qb in q]
        v = [p(qa, qb, c) for c in (c0, c0 + 0.005) for qa, qb in q]
        yel.append((v, [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]))
        a += period
    return dark, yel


def hazard_stripes(args: dict, layout: dict) -> list:
    """details 2: warning stripes on the ramp's two side rails' tops (the rails' 12 cm, 10 cm over the deck: as in
    ship_hull.ramp) and across the mouth's floor edge (12 cm deep at the hinge, over the throat floor's rim)."""
    rp, deck = layout["ramp"], layout["deck"]
    run = rp["hinge"][1] - rp["foot"][1]
    fall = deck["floor_h"] - deck["ground_h"]
    hw = rp["width_m"] / 2
    length = math.hypot(run, fall)
    along = (0.0, -run / length, -fall / length)
    up = (0.0, -fall / length, run / length)
    if up[2] < 0:
        up = (0.0, -up[1], -up[2])
    top0 = (rp["hinge"][0], rp["hinge"][1], deck["floor_h"])
    darks, yels = [], []
    for s in (-1, 1):
        o = H._add(H._add(top0, (1.0, 0.0, 0.0), s * (hw - 0.06)), along, 0.06)
        d, y = _stripes(o, along, (1.0, 0.0, 0.0), up, length - 0.12, 0.12, 0.1, slant=s)
        darks.append(d)
        yels += y
    o = (-(hw - 0.1), rp["hinge"][1] + 0.065, deck["floor_h"])
    d, y = _stripes(o, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 2 * (hw - 0.1), 0.11, 0.006)
    darks.append(d)
    yels += y
    return [L.part("hazard_dark", *L.merge(*darks), "ext_hazard_dark"),
            L.part("hazard_yellow", *L.merge(*yels), "ext_hazard")]
