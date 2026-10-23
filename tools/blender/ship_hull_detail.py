"""The hull's details (art #263; docs/ship.md "The hull's details"): the two cockpit canopies over the hall flush
in the hull with a rim, the three nozzle pods with their cyan rings, the amber ground lamps. The HULL lane owns this
file. Rebuild B (variant J): no lead blades, stripes or tip windows (no outside light strips; the rooms have no
windows), no pod housing (J's stern face holds the pods); no hatches, seam lines or scratches.

Every builder reads the hull's top from ship_hull_shape.heights (variant J), so a detail sits on the hull wherever it
moves; pieces in the plan frame are placed at the origin. Numbers (plan metres):
- canopies: J's, a glass ellipse 0.95 (x) by 1.35 (y) at (+-2.25, -3.6), 0.85 m high (details 1), its base on the hull (+ 0.02);
  a low collar round it; a dark rim lip; a lit floor, seat and desk under the glass.
- pods: the outer two r 1.05 at (+-2.75, h 2.15), the middle r 1.2 at h 2.45, their rear ends at J's (y 11.0 and
  11.8: exterior.toml places each at J's y less hull.pod_tail_m); smooth 32-sided shells with a round nose, one dark
  collar, the bell."""

from __future__ import annotations

import math

import ship_hull as H
import ship_hull_shape as S
import ship_lib as L

def skin_h(x: float, y: float) -> float | None:
    """The hull's top height at plan (x, y) (ship_hull_shape, variant J), None off its footprint."""
    hb = S.heights(x, y)
    return hb[0] if hb else None


def _smooth(p: dict) -> dict:
    p["smooth"] = True
    return p


def _bar(path, w, t, lift=0.0, up=(0.0, 0.0, 1.0)):
    """A closed bar along a polyline: width w across (horizontal, normal to the path), thickness t (up), lifted."""
    secs = []
    for i, p in enumerate(path):
        a, b = path[max(0, i - 1)], path[min(len(path) - 1, i + 1)]
        d = H._norm(H._sub(b, a))
        side = H._norm(H._cross(up, d))
        c = H._add(p, up, lift)
        secs.append([H._add(H._add(c, side, sx * w / 2), up, sz * t / 2) for sx, sz in ((-1, -1), (1, -1), (1, 1),
                                                                                        (-1, 1))])
    v = [q for s in secs for q in s]
    f = [(0, 1, 2, 3), tuple(len(v) - 4 + k for k in (3, 2, 1, 0))]
    for i in range(len(secs) - 1):
        for j in range(4):
            f.append((i * 4 + j, i * 4 + (j + 1) % 4, (i + 1) * 4 + (j + 1) % 4, (i + 1) * 4 + j))
    return v, f


# --- the canopies --------------------------------------------------------------------------------------------------
CANOPY = {"x": 2.25, "y": -3.6, "ax": 0.95, "ay": 1.35, "height": 0.85, "segs": 28, "rings": 5}   # J's; details 1:
#   0.85 high (was 0.75), room over a pilot's seat


def _canopy_frame(side):
    """The canopy's outlines and its deck: the skin itself (hull 3-2: flush in the forward hull, no raised pod)."""
    c = CANOPY
    cx, cy = side * c["x"], c["y"]
    ts = [2 * math.pi * (k + 0.5) / c["segs"] for k in range(c["segs"])]

    def outline(t, k=1.14):
        s = math.sin(t)
        tail = max(0.0, s) ** 2
        return (cx + c["ax"] * k * math.cos(t) * (1 - 0.35 * tail), cy + c["ay"] * k * s * (1 + 0.35 * tail))
    rim = [outline(t) for t in ts]
    glass = [(cx + c["ax"] * math.cos(t), cy + c["ay"] * math.sin(t)) for t in ts]

    def deck(x, y):
        h = skin_h(x, y)
        return (h if h is not None else skin_h(cx, cy)) + 0.02
    return ts, rim, glass, deck, outline


def canopy(args: dict, layout: dict) -> list:
    """A cockpit canopy (args side; part glass|fairing|glow), outside only: the hall's ceiling closes it from inside.
    Set flush in the forward hull (its base follows the skin), smooth (28 sides, 5 rings), a low smooth collar
    round it; details 1: a cockpit under lighter glass (glass_canopy): a pilot's seat facing forward (-y), a console
    with two grips and three cyan screens, a warm floor and a warm glow round the glass's foot (cockpit())."""
    side = float(args.get("side", 1.0))
    part = args.get("part", "glass")
    c = CANOPY
    ts, rim, glass, deck, outline = _canopy_frame(side)
    n = len(ts)
    cx, cy = side * c["x"], c["y"]
    if part == "glass":
        v, rings = [], c["rings"]
        for i in range(rings):
            phi = math.pi / 2 * i / rings
            for x, y in glass:
                px, py = cx + (x - cx) * math.cos(phi), cy + (y - cy) * math.cos(phi)
                v.append((px, py, deck(px, py) + 0.04 + c["height"] * math.sin(phi)))
        v.append((cx, cy, deck(cx, cy) + 0.04 + c["height"]))
        f = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
             for i in range(rings - 1) for j in range(n)]
        f += [((rings - 1) * n + j, (rings - 1) * n + (j + 1) % n, len(v) - 1) for j in range(n)]
        f = L.orient(v, f, lambda _c: (cx, cy, deck(cx, cy) - 0.5))
        ribs = []
        for t0 in (math.pi / 2, -math.pi / 2, 0.0, math.pi):  # a cross of frame ribs over the glass
            path = []
            for i in range(rings + 1):
                phi = math.pi / 2 * i / rings
                px, py = cx + c["ax"] * math.cos(t0) * math.cos(phi), cy + c["ay"] * math.sin(t0) * math.cos(phi)
                path.append((px, py, deck(px, py) + 0.06 + (c["height"] + 0.01) * math.sin(phi)))
            ribs.append(_bar(path, 0.07, 0.05))
        return [_smooth(L.part("canopy_glass", v, f, "glass_canopy", solid=False)),
                L.part("canopy_ribs", *L.merge(*ribs), "ext_frame")]
    if part == "fairing":
        # the deck ring between the glass and the teardrop outline, the collar down into the skin, the rim lip
        inner = [(x, y, deck(x, y) + 0.06) for x, y in glass]
        outer = []
        for t, (x, y) in zip(ts, rim):
            outer.append((x, y, (skin_h(x, y) or deck(x, y)) + 0.03))
        foot = [(x, y, (skin_h(x, y) or deck(x, y)) - 0.01) for x, y in rim]
        v = inner + outer + foot
        f = [(j, (j + 1) % n, n + (j + 1) % n, n + j) for j in range(n)]
        f += [(n + j, n + (j + 1) % n, 2 * n + (j + 1) % n, 2 * n + j) for j in range(n)]
        f = (L.orient(v, f[:n], lambda q: (q[0], q[1], q[2] - 1.0))
             + L.orient(v, f[n:], lambda q: (cx, cy + 0.4 * c["ay"], q[2])))
        lip = []
        for j in range(n):
            x, y = glass[j]
            ox, oy = cx + (x - cx) * 1.06, cy + (y - cy) * 1.06
            lip.append([(x, y, deck(x, y) - 0.02), (ox, oy, deck(ox, oy) - 0.02), (ox, oy, deck(ox, oy) + 0.09),
                        (x, y, deck(x, y) + 0.07)])
        lv = [q for s in lip for q in s]
        lf = [(j * 4 + k, j * 4 + (k + 1) % 4, ((j + 1) % n) * 4 + (k + 1) % 4, ((j + 1) % n) * 4 + k)
              for j in range(n) for k in range(4)]
        return [_smooth(L.part("canopy_fairing", v, f, "ext_silver_b", solid=False)),
                L.part("canopy_lip", lv, lf, "ext_frame")]
    return cockpit(side)


def glass_h(side: float, x: float, y: float) -> float:
    """The canopy glass's inner height over plan (x, y) (its ellipse's dome over the deck; the deck where outside)."""
    c = CANOPY
    _ts, _rim, _glass, deck, _o = _canopy_frame(side)
    q = math.hypot((x - side * c["x"]) / c["ax"], (y - c["y"]) / c["ay"])
    return deck(x, y) + 0.04 + c["height"] * math.sqrt(max(0.0, 1.0 - q * q))


# canopy fix (art #263, walk 2 item 3, "lower the saddle and give it a normal tilt"): the pilot's seat 8 cm lower
# (its pan flush with the floor's uphill corner, was 5.5 cm over it) and its back 25 deg from upright (was 40: a long
# dark ramp along the nose's slant that read as a seat only from close by); grid <raw>/ship/v4/canopy/sheets/
SEAT = {"drop": 0.08, "recline": 25.0}


def _tilt(c, hx, hy, hz, deg):
    """An oriented box at c, half sizes hx (x), hy, hz, turned deg about x (+: its top leans aft, +y)."""
    a = math.radians(deg)
    return H._obox(c, (hx, 0, 0), (0, hy * math.cos(a), -hy * math.sin(a)), (0, hz * math.sin(a), hz * math.cos(a)))


def cockpit(side: float) -> list:
    """details 1: the cockpit under a canopy (plan frame, outside only): the warm-lit floor and a warm glow ring at
    the glass's foot (the 2D's orange domes), a pilot's seat facing forward (-y): a pedestal, the seat pan with its
    cushion, a reclined back and a headrest, two armrests (silver shell, dark pads), and a console ahead with a
    sloped face, two grips and three cyan screens (ext_screen, bright enough to read through the glass at night).
    Sized for a person: the pan 0.5 m wide, the back and headrest 0.61 m long reclined SEAT 25 deg (the glass is
    0.85 m high); every vertex stays under the glass (test_ship_hull_detail)."""
    c = CANOPY
    ts, rim, glass, deck, outline = _canopy_frame(side)
    n = len(ts)
    cx, cy = side * c["x"], c["y"]
    # the floor in rings (a single fan's chords dipped under the convex hull: dark wedges through it), 8 cm up
    ks = (0.85, 0.6, 0.35)
    fv = [(cx + (x - cx) * k, cy + (y - cy) * k) for k in ks for x, y in glass]
    fv = [(x, y, deck(x, y) + 0.08) for x, y in fv] + [(cx, cy, deck(cx, cy) + 0.08)]
    ff = [(i * n + j, i * n + (j + 1) % n, (i + 1) * n + (j + 1) % n, (i + 1) * n + j)
          for i in range(len(ks) - 1) for j in range(n)]
    ff += [((len(ks) - 1) * n + j, (len(ks) - 1) * n + (j + 1) % n, len(fv) - 1) for j in range(n)]
    ff = L.orient(fv, ff, lambda _c: (cx, cy, deck(cx, cy) - 1.0))
    # the glow ring: a low warm band just inside the glass's foot, its face turned in
    gv = []
    for x, y in glass:
        ix, iy = cx + (x - cx) * 0.95, cy + (y - cy) * 0.95
        gv += [(ix, iy, deck(ix, iy) + 0.05), (ix, iy, deck(ix, iy) + 0.11)]
    gf = [(2 * j, 2 * ((j + 1) % n), 2 * ((j + 1) % n) + 1, 2 * j + 1) for j in range(n)]
    gf = L.orient(gv, gf, lambda q: (cx + (q[0] - cx) * 1.5, cy + (q[1] - cy) * 1.5, q[2]))

    def on(x, y, hx, hy):  # the highest cockpit floor point under a footprint
        return max(deck(x + sx * hx, y + sy * hy) for sx in (-1, 1) for sy in (-1, 1)) + 0.06
    # the seat: its pan's centre 0.1 m aft of the canopy's centre, the back pivot at its rear edge
    sy0 = cy + 0.02
    f0 = on(cx, sy0, 0.25, 0.3) - SEAT["drop"]
    pan_top = f0 + 0.17
    rec = SEAT["recline"]
    ra = math.radians(rec)
    up, aft = (math.sin(ra), math.cos(ra)), (math.cos(ra), -math.sin(ra))   # along the back (y, h), its thickness
    py, ph = sy0 + 0.2, pan_top          # the back's foot
    def along(t, d=0.0):  # a point t up the back, d behind its face
        return (cx, py + up[0] * t + aft[0] * d, ph + up[1] * t + aft[1] * d)
    shell = [H._obox((cx, sy0, f0 + 0.06), (0.07, 0, 0), (0, 0.07, 0), (0, 0, 0.06)),          # the pedestal
             H._obox((cx, sy0, pan_top - 0.06), (0.25, 0, 0), (0, 0.22, 0), (0, 0, 0.035)),      # the pan's shell
             _tilt(along(0.25, 0.05), 0.24, 0.035, 0.25, rec),                                   # the back's shell
             _tilt(along(0.55, 0.04), 0.14, 0.03, 0.06, rec)]                                    # the headrest's
    pads = [H._obox((cx, sy0 - 0.01, pan_top - 0.0125), (0.22, 0, 0), (0, 0.2, 0), (0, 0, 0.0125)),
            _tilt(along(0.25, 0.0), 0.21, 0.015, 0.23, rec), _tilt(along(0.55, 0.0), 0.12, 0.012, 0.05, rec)]
    for sx in (-1, 1):   # the armrests: a post and a pad, level with the pan + 0.18
        ax_ = cx + sx * 0.28
        shell.append(H._obox((ax_, sy0 + 0.1, pan_top + 0.06), (0.025, 0, 0), (0, 0.025, 0), (0, 0, 0.06)))
        pads.append(H._obox((ax_, sy0 + 0.02, pan_top + 0.15), (0.035, 0, 0), (0, 0.17, 0), (0, 0, 0.025)))
    # the console: a body 0.6 m wide 0.5 m ahead of the pan, its face sloped toward the pilot, a shelf, two grips
    ky = cy - 0.47
    k0 = on(cx, ky, 0.3, 0.12)
    shell.append(H._obox((cx, ky, k0 + 0.11), (0.3, 0, 0), (0, 0.12, 0), (0, 0, 0.11)))         # the body
    shell.append(_tilt((cx, ky + 0.07, k0 + 0.28), 0.3, 0.03, 0.1, -40.0))                     # the sloped face
    shell.append(H._obox((cx, ky + 0.18, k0 + 0.19), (0.27, 0, 0), (0, 0.07, 0), (0, 0, 0.015)))  # the shelf
    for sx in (-1, 1):
        gx = cx + sx * 0.2
        shell.append(H._obox((gx, ky + 0.2, k0 + 0.24), (0.018, 0, 0), (0, 0.018, 0), (0, 0, 0.045)))
        pads.append(H._obox((gx, ky + 0.205, k0 + 0.31), (0.028, 0, 0), (0, 0.03, 0), (0, 0, 0.035)))
    screens = []
    for k, (sx, w) in enumerate(((-0.225, 0.08), (0.0, 0.1), (0.225, 0.08))):
        # on the sloped face, 1 cm proud of it toward the pilot (+y, up)
        d = (0.0, math.cos(math.radians(40.0)) * 0.035, math.sin(math.radians(40.0)) * 0.035)
        cc = (cx + sx, ky + 0.07 + d[1], k0 + 0.28 + d[2])
        screens.append(_tilt(cc, w, 0.004, 0.07, -40.0))
    return [L.part("canopy_floor", fv, ff, "ext_glow_warm", solid=False),
            L.part("canopy_glow", gv, gf, "ext_glow_warm", solid=False),
            L.part("canopy_seat", *L.merge(*shell), "ext_seat"),
            L.part("canopy_pads", *L.merge(*pads), "ext_frame"),
            L.part("canopy_screen", *L.merge(*screens), "ext_screen")]


# --- the nozzle pods -----------------------------------------------------------------------------------------------
POD_SEGS = 32
THROAT_SMOOTH_DEG = 30.0   # fix 2: the throat smooth across its radial facets, sharp at its wall/floor crease
NOZZLE = (0.8, 0.45)   # lens step 2: the nozzle's radius at the bell's lip and 1.0 m in (x r), its floor 1.15 m in


def nozzle_pod(args: dict, layout: dict) -> list:
    """A long engine pod along +y (local origin: its nose on the axis; args r, length): a smooth shell with a round
    nose (shaded smooth, no plates), one dark collar, the bell (an open ring: lens step 2) and the dark nozzle, 1.15 m
    deep from the bell's lip (NOZZLE), behind it the shell's cone (the lights: pod_ring)."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    nose = [(0.97 * r * math.sin(math.pi / 2 * k / 7) ** 0.85, 1.5 * (1 - math.cos(math.pi / 2 * k / 7)))
            for k in range(1, 8)]
    shell = H._lathe_y([(0.0, 0.0)] + nose + [(r, ln - 0.7), (0.97 * r, ln - 0.35), (0.0, ln - 0.9)], POD_SEGS)
    collar = H._lathe_y([(0.0, ln - 1.5), (1.03 * r, ln - 1.5), (1.03 * r, ln - 1.3), (0.0, ln - 1.3)], POD_SEGS)
    # fix 2 (art #263, item 5): the bell and the throat open (caps=False). The lathe capped their rings off the axis:
    # the bell's lip ring and the throat's mouth were two flat discs in one plane (ln + 0.4) over the whole nozzle,
    # ext_frame and ext_nozzle_inner z-fighting, so the "dish" changed as the camera turned (wedges of the two discs'
    # triangles, the brushed frame's moving highlight), and the nozzle behind them was never seen
    bv, bf = H._lathe_y([(0.95 * r, ln - 0.4), (0.92 * r, ln + 0.35), (0.84 * r, ln + 0.4), (NOZZLE[0] * r, ln + 0.4)],
                        POD_SEGS, caps=False)
    bell = (bv, L.orient(bv, bf, lambda q: (0.0, q[1] - 2.0, 0.0)))
    tv, tf = H._lathe_y([(NOZZLE[0] * r, ln + 0.4), (NOZZLE[1] * r, ln - 0.6), (0.0, ln - 0.75)], POD_SEGS, caps=False)
    throat = (tv, L.orient(tv, tf, lambda q: (2.0 * q[0], q[1], 2.0 * q[2])))
    # fix 2 (art #263, item 5): the throat (the dark dish behind the cyan ring) shaded smooth round its POD_SEGS
    # radial facets (11.25 deg apart), its crease between the wall and the floor (about 50 deg) kept: flat, each facet
    # mirrored another strip of the sky, streaks that moved as the camera turned
    pt = L.part("pod_throat", *throat, "ext_nozzle_inner", solid=False)
    pt["smooth_deg"] = THROAT_SMOOTH_DEG
    return [_smooth(L.part("pod_shell", *shell, "hull_silver")), L.part("pod_collar", *collar, "hull_dark"),
            L.part("pod_bell", *bell, "ext_frame", solid=False), pt]


def pod_ring(args: dict, layout: dict) -> list:
    """A pod's cyan lights (local frame as nozzle_pod; glow_pod, dimmer than the strips: a ring you see, not a lamp):
    the band round the bell, a band on the barrel ahead of it, the segmented ring on the bell's lip and (lens step 2)
    the glowing inner ring 0.3 m down the nozzle, a dim core on its floor."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    # fix 2: the band round the bell a ring outside the nozzle's wall (it was a solid disc across the nozzle 16 cm in)
    rin = NOZZLE[0] * r
    band = H._lathe_y([(rin, ln + 0.02), (0.99 * r, ln + 0.02), (0.99 * r, ln + 0.24), (rin, ln + 0.24), (rin, ln + 0.02)],
                      POD_SEGS, caps=False)
    band2 = H._lathe_y([(0.0, ln - 0.95), (1.015 * r, ln - 0.95), (1.015 * r, ln - 0.8), (0.0, ln - 0.8)], POD_SEGS)
    segs = []
    for k in range(10):
        a0, a1 = 2 * math.pi * k / 10 + 0.06, 2 * math.pi * (k + 1) / 10 - 0.06
        v, f = L.sector(0.805 * r, 0.835 * r, a0, a1, ln + 0.405, ln + 0.435)
        v = [(x, h, y) for x, y, h in v]  # the swap mirrors the winding: orient the faces rearward (polish 4)
        segs.append((v, L.orient(v, f, lambda q: (0.0, q[1] - 1.0, 0.0))))
    core = H._lathe_y([(0.0, ln - 0.73), (0.3 * r, ln - 0.73), (0.0, ln - 0.7)], 12)

    def wall(y):   # the nozzle's radius at y, 6 mm inside it
        a, b = NOZZLE
        return (b + (a - b) * (y - (ln - 0.6)) / 1.0) * r - 0.006
    iv, i_f = H._lathe_y([(wall(ln - 0.27), ln - 0.27), (wall(ln - 0.33), ln - 0.33)], POD_SEGS, caps=False)
    inner = (iv, L.orient(iv, i_f, lambda q: (2.0 * q[0], q[1], 2.0 * q[2])))
    return [L.part("pod_band", *L.merge(band, band2), "glow_pod"),
            L.part("pod_segments", *L.merge(*segs), "glow_pod"),
            L.part("pod_inner_ring", *inner, "glow_pod", solid=False),
            L.part("pod_core", *core, "ext_glow_cyan_dim")]


def ground_lamp(args: dict, layout: dict) -> list:
    """An amber ground lamp (local origin on the ground): a low faceted housing with a glowing lens."""
    body = L.disc(0.2, 8, 0.0, 0.07)
    lens = L.disc(0.13, 8, 0.07, 0.1)
    return [L.part("lamp_body", *body, "hull_dark"), L.part("lamp_lens", *lens, "glow_amber")]


NAV_MATS = {"red": "glow_nav_red", "green": "glow_nav_green", "white": "glow_nav_white"}


def _rod(r, n, a, b, axis):
    """A closed n-sided rod of radius r from a to b along the local axis "x" (out of a wall) or "h" (up)."""
    v, f = L.disc(r, n, a, b)
    if axis == "x":
        v = [(h, x, y) for x, y, h in v]
    return v, f


def nav_lamp(args: dict, layout: dict) -> list:
    """light layer: a navigation lamp (args colour red/green/white, mount "wall" or "top"): a round housing in the
    hull's silver, its foot 3 cm into the skin, a glowing lens and a smaller cap on it. Local origin on the skin at
    the lamp's centre; a wall lamp looks along +x (the placement's yaw turns it outward), a top lamp up."""
    axis = "x" if args.get("mount", "wall") == "wall" else "h"
    mat = NAV_MATS[args.get("colour", "white")]
    return [L.part("nav_housing", *_rod(0.085, 10, -0.03, 0.06, axis), "hull_silver"),
            L.part("nav_bezel", *_rod(0.068, 10, 0.06, 0.075, axis), "ext_frame"),
            L.part("nav_lens", *L.merge(_rod(0.055, 10, 0.075, 0.115, axis), _rod(0.035, 10, 0.115, 0.13, axis)),
                   mat)]


def landing_lamp(args: dict, layout: dict) -> list:
    """light layer: a warm landing light under the belly (local origin on the belly's bottom): a round silver
    housing hanging 7 cm, its top 8 cm into the skin, a dark bezel and a warm lens facing down."""
    return [L.part("landing_housing", *L.disc(0.16, 12, -0.07, 0.08), "hull_silver"),
            L.part("landing_bezel", *L.disc(0.125, 12, -0.08, -0.07), "ext_frame"),
            L.part("landing_lens", *L.disc(0.105, 12, -0.09, -0.08), "glow_landing")]


for _name in ("canopy", "nozzle_pod", "pod_ring", "ground_lamp"):
    globals()[_name] = H._outward(globals()[_name])


# --- lens step 2: the edge light and the lens windows' outer frames --------------------------------------------------
EDGE_GLOW = (0.03, 0.006)      # the glow's half height (6 cm visible; 3.5 cm read thin at night) and its lift off the face
EDGE_LIP = (0.045, 0.014)      # the channel's lips: out to this half height, this far proud (the glow sits 8 mm in)


def _sweep(path, profile, mat_of):
    """Extrude a 2D profile [(lift, z)] along path [(point, outward n)] (z vertical): per profile edge a strip of
    quads, its normal the edge's outward side in (n, z). mat_of(i) names edge i's material. {mat: (verts, faces)}."""
    out = {}
    for i, ((o0, z0), (o1, z1)) in enumerate(zip(profile, profile[1:])):
        dz, do = z1 - z0, o1 - o0
        en = (dz, -do)   # the profile walks top to bottom on the outside: its right side faces out
        vs, fs = out.setdefault(mat_of(i), ([], []))
        for (p0, n0), (p1, n1) in zip(path, path[1:]):
            q = [tuple(p0[k] + o0 * n0[k] + (z0 if k == 2 else 0.0) for k in range(3)),
                 tuple(p1[k] + o0 * n1[k] + (z0 if k == 2 else 0.0) for k in range(3)),
                 tuple(p1[k] + o1 * n1[k] + (z1 if k == 2 else 0.0) for k in range(3)),
                 tuple(p0[k] + o1 * n0[k] + (z1 if k == 2 else 0.0) for k in range(3))]
            nm = tuple(0.5 * (n0[k] + n1[k]) for k in range(3))
            want = tuple(en[0] * nm[k] + (en[1] if k == 2 else 0.0) for k in range(3))
            base = len(vs)
            vs += q
            fs.append(tuple(base + j for j in ((0, 1, 2, 3) if S._dot(S._newell(q), want) > 0 else (3, 2, 1, 0))))
    return out


def edge_light(args: dict, layout: dict) -> list:
    """lens step 2: the thin cool-white light line round the hull's outer edge, where the top meets the belly: along
    each fin's lead edge from the nose (not across the mouth), round the lens rim under the window band and along the
    trail edge into the pod (ship_hull_shape.p_edge_line). A dark channel with two lips, the glow 8 mm
    in between them. lens polish: the glow 6 cm high, in EDGE_CHUNK pieces."""
    gh, go = EDGE_GLOW
    lh, lo = EDGE_LIP
    profile = [(0.003, lh), (lo, lh), (lo, gh), (go, gh), (go, -gh), (lo, -gh), (lo, -lh), (0.003, -lh)]
    groups: dict = {}
    glows = []
    for sx in (1, -1):
        for path in _chunks(S.p_edge_line(sx), EDGE_CHUNK):
            for mat, (v, f) in _sweep(path, profile, lambda i: "glow_edge" if i == 3 else "ext_frame").items():
                if mat == "glow_edge":
                    glows.append((v, f))
                else:
                    groups.setdefault(mat, []).append((v, f))
    parts = [L.part("edge_channel", *L.merge(*g), m, solid=False) for m, g in sorted(groups.items())]
    return parts + [L.part(f"edge_glow_{k:02d}", v, f, "glow_edge", solid=False) for k, (v, f) in enumerate(glows)]


EDGE_CHUNK = 4.0   # lens polish: the glow in pieces of about this length, so Godot's strip lights stand along the edge
#                    (one mesh put its one light in the ship's middle) and pool faintly on the ground under it


def _chunks(path, length):
    """A path [(point, n)] in consecutive runs of about `length` metres, each sharing its end point with the next."""
    out, run, run_len = [], [path[0]], 0.0
    for a, b in zip(path, path[1:]):
        run.append(b)
        run_len += math.dist(a[0], b[0])
        if run_len >= length:
            out.append(run)
            run, run_len = [b], 0.0
    if len(run) > 1:
        out.append(run)
    return out


def _rim_at(g, sx=1):
    """The lens rim's face point at plan angle g (east frame) and its facet's outward normal."""
    step = 2 * math.pi / S.P_LENS_N
    gm = (math.floor(g / step + 1e-9) + 0.5) * step
    r = S.P_RIM_R / math.cos(g - gm)
    cx, cy = S.P_TIP
    return (sx * (cx + r * math.cos(g)), cy + r * math.sin(g)), (sx * math.cos(gm), math.sin(gm))


def _box2(p0, p1, w, h0, h1, lift=0.0):
    """A solid bar from plan p0 to p1 (w wide, centred `lift` to the left), bottoms h0 (each end its own) to tops h1."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    nx, ny = -dy / ln, dx / ln
    v = []
    for (x, y), b, t in ((p0, h0[0], h1[0]), (p1, h0[1], h1[1])):
        for s in (-1, 1):
            o = lift + s * w / 2
            v += [(x + o * nx, y + o * ny, b), (x + o * nx, y + o * ny, t)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (1, 3, 7, 5), (0, 4, 6, 2)]
    return v, f


def lens_frames(args: dict, layout: dict) -> list:
    """lens step 2: the lenses' outer window frames (ext_frame): along the band's sill and head on the rim (5 cm, 3 cm
    proud), its two end posts, a mullion in the reveal at each of the room's inner window vertices (step 1's
    mullions), and (details 1) the oculus's thick silver ring frame on the top, and the band's warm glow: a faint
    emissive pane in the reveal, one-sided (it faces out: from the room it is culled), so the band reads lit at night
    from outside at a grazing angle."""
    bars = []
    ax = S.p_axis_deg()
    a0, a1 = math.radians(ax + S.P_BAND[0]), math.radians(ax + S.P_BAND[1])
    step = 2 * math.pi / S.P_LENS_N
    cuts = [a0] + [k * step for k in range(math.floor(a0 / step) + 1, math.ceil(a1 / step))] + [a1]
    facet = (S.P_BAND[1] - S.P_BAND[0]) / 5.0
    for sx in (1, -1):
        for a, b in zip(cuts, cuts[1:]):
            (p, n), (q, _m) = _rim_at(a + 1e-7, sx), _rim_at(b - 1e-7, sx)
            n = _rim_at(0.5 * (a + b), sx)[1]
            dx, dy = q[0] - p[0], q[1] - p[1]
            ln = math.hypot(dx, dy)
            p = (p[0] - 0.01 * dx / ln, p[1] - 0.01 * dy / ln)
            q = (q[0] + 0.01 * dx / ln, q[1] + 0.01 * dy / ln)
            lift = 0.015 if (-dy * n[0] + dx * n[1]) > 0 else -0.015   # the bar's middle 1.5 cm out of the face
            for h0, h1 in ((S.SILL - 0.05, S.SILL), (S.HEAD, S.HEAD + 0.05)):
                bars.append(_box2(p, q, 0.03, (h0, h0), (h1, h1), lift))
        for g in (a0, a1):   # the end posts, 5 cm wide outside the opening
            (p, n) = _rim_at(g, sx)
            t = (-n[1], n[0])
            s = -1 if g == a0 else 1
            c = (p[0] + s * sx * 0.025 * t[0] + 0.015 * n[0], p[1] + s * sx * 0.025 * t[1] + 0.015 * n[1])
            bars.append(H._obox((c[0], c[1], 0.5 * (S.SILL + S.HEAD)), (0.025 * t[0], 0.025 * t[1], 0.0),
                                (0.015 * n[0], 0.015 * n[1], 0.0), (0.0, 0.0, 0.5 * (S.HEAD - S.SILL) + 0.05)))
        for k in range(1, 5):   # the mullions: the room's inner window vertices, from the glass's reveal to the rim
            g = math.radians(ax + S.P_BAND[0] + k * facet)
            (p, n) = _rim_at(g, sx)
            cx, cy = sx * S.P_TIP[0], S.P_TIP[1]
            u = (sx * math.cos(g), math.sin(g))
            r0, r1 = S.P_BAND_IN - 0.01, math.hypot(p[0] - cx, p[1] - cy) + 0.02
            c = (cx + 0.5 * (r0 + r1) * u[0], cy + 0.5 * (r0 + r1) * u[1])
            bars.append(H._obox((c[0], c[1], 0.5 * (S.SILL + S.HEAD)), (0.5 * (r1 - r0) * u[0], 0.5 * (r1 - r0) * u[1], 0.0),
                                (-0.025 * u[1], 0.025 * u[0], 0.0), (0.0, 0.0, 0.5 * (S.HEAD - S.SILL))))
    # details 1: the oculus's ring frame on the hull, thick silver: the section (r, h over the hull's top) from a lip
    # 1 cm over the cut's edge and 4 cm down into it, 20 cm out over the plates (their cut slivers), a chamfered crown
    # 8.5 cm proud
    sec = [(-0.012, -0.04), (0.2, -0.02), (0.2, 0.03), (0.14, 0.085), (0.02, 0.085), (-0.012, 0.05)]
    n = S.P_OCULUS_N * 2
    ring_v, ring_f = [], []
    for sx in (1, -1):
        cx, cy = sx * S.P_TIP[0], S.P_TIP[1]
        base = len(ring_v)
        for j in range(n):
            a = 2 * math.pi * (j + 0.5) / n
            u = (math.cos(a), math.sin(a))
            r0 = S.P_OCULUS_R / math.cos(math.pi / S.P_OCULUS_N)   # the cut's vertices: no sliver of hull shows inside
            for dr, dh in sec:
                x, y = cx + (r0 + dr) * u[0], cy + (r0 + dr) * u[1]
                ring_v.append((x, y, S.heights(x, y, S.DEFAULT)[0] + dh))
        m = len(sec)
        for j in range(n):
            for q in range(m):
                a0, a1 = base + j * m + q, base + j * m + (q + 1) % m
                b0, b1 = base + ((j + 1) % n) * m + q, base + ((j + 1) % n) * m + (q + 1) % m
                ring_f.append((a0, b0, b1, a1))
    gv, gf = [], []
    step = 2 * math.pi / S.P_LENS_N
    for sx in (1, -1):
        g0, g1 = math.radians(ax + S.P_BAND[0]), math.radians(ax + S.P_BAND[1])
        cuts = [g0] + [k * step for k in range(math.floor(g0 / step) + 1, math.ceil(g1 / step))] + [g1]
        cx, cy = sx * S.P_TIP[0], S.P_TIP[1]
        for a, b in zip(cuts, cuts[1:]):
            k = len(gv)
            for g, h in ((a, S.SILL + 0.01), (b, S.SILL + 0.01), (b, S.HEAD - 0.01), (a, S.HEAD - 0.01)):
                gv.append((cx + sx * GLOW_PANE_R * math.cos(g), cy + GLOW_PANE_R * math.sin(g), h))
            gf.append((k, k + 1, k + 2, k + 3))
    gf = L.orient(gv, gf, lambda q: (math.copysign(S.P_TIP[0], q[0]), S.P_TIP[1], q[2]))
    return [L.part("band_frame", *L.merge(*bars), "ext_frame"), L.part("oculus_frame", ring_v, ring_f, "ext_silver_b"),
            L.part("band_glow", gv, gf, "ext_window_glow", solid=False)]


GLOW_PANE_R = 2.32   # details 1: the band's glow pane, outside the room's wall (2.21) and inside the rim (2.55)


for _name in ("edge_light", "lens_frames"):
    globals()[_name] = H._outward(globals()[_name])
