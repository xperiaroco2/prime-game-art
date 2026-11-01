"""The hull's details (art #263; docs/ship.md "The hull's details"): the two cockpit canopies over the hall flush
in the hull with a rim, the three nozzle pods with their cyan rings, the amber ground lamps. The HULL lane owns this
file. Rebuild B (variant J): no lead blades, stripes or tip windows (no outside light strips; the rooms have no
windows), no pod housing (J's stern face holds the pods); no hatches, seam lines or scratches.

Every builder reads the hull's top from ship_hull_shape.heights (variant J), so a detail sits on the hull wherever it
moves; pieces in the plan frame are placed at the origin. Numbers (plan metres):
- canopies: J's, a glass ellipse 0.95 (x) by 1.35 (y) at (+-2.25, -3.6), 0.85 m high (details 1), its base on the hull (+ 0.02);
  a low collar round it; a dark rim lip; a lit floor, seat and desk under the glass.
- pods: the outer two r 1.05 at (+-2.75, h 2.15), the middle r 1.2 at h 2.45, their rear ends at J's (y 11.0 and
  11.8: exterior.toml places each at J's y less hull.pod_tail_m); smooth POD_SEGS-sided shells (polish n1: 64) with a round nose, one dark
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


def _tilt(c, hx, hy, hz, deg):
    """An oriented box at c, half sizes hx (x), hy, hz, turned deg about x (+: its top leans aft, +y)."""
    a = math.radians(deg)
    return H._obox(c, (hx, 0, 0), (0, hy * math.cos(a), -hy * math.sin(a)), (0, hz * math.sin(a), hz * math.cos(a)))


def cockpit(side: float) -> list:
    """details 1: the cockpit under a canopy (plan frame, outside only): the warm-lit floor and a warm glow ring at
    the glass's foot (the 2D's orange domes), a pilot's seat facing forward (-y): a pedestal, the seat pan with its
    cushion, a reclined back and a headrest, two armrests (silver shell, dark pads), and a console ahead with a
    sloped face, two grips and three cyan screens (ext_screen, bright enough to read through the glass at night).
    Sized for a person: the pan 0.5 m wide, the back and headrest 0.61 m long reclined 40 deg (the glass is 0.85 m
    high); every vertex stays under the glass (test_ship_hull_detail)."""
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
    f0 = on(cx, sy0, 0.25, 0.3)
    pan_top = f0 + 0.17
    rec = 40.0
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
# polish n1 (art #263): the stern seen up close from the lobby's spawn. 64 segments shaded smooth (16-facet corners on
# every rim before); the bell a solid ring with bevelled lips. nb: inside it the old look again (n1-n4's stepped
# throat, stator blades and spinner read as a jet engine): the dark throat, one light ring on its wall, a small dot on
# its floor, ten light segments with gaps in the lip. Their glow lives in the emissive materials (glow_pod,
# ext_glow_cyan_dim), so the package's bells glow wherever it is instanced, its run-time lights off (the lobby) or on.
POD_SEGS = 64
THROAT_SMOOTH_DEG = 30.0   # fix 2: the throat smooth across its radial facets, sharp at its wall/floor crease
NOZZLE = (0.8, 0.45)   # lens step 2: the throat's radius at the bell's inner wall and 0.9 m deeper (x r)
LIP = 0.45            # n1: the bell's lip plane past the args length (nb: its segments 1.6 cm into it: pod_tail_m)
POD_RIBS = (45.0, 90.0, 135.0, 225.0, 270.0, 315.0)   # n1: the stringers' angles, clear of the pods' contact (~ +-10)


def _ring(profile, inner, segs=POD_SEGS):
    """An open surface of revolution (no caps) oriented away from inner(face centre)."""
    v, f = H._lathe_y(profile, segs, caps=False)
    return v, L.orient(v, f, inner)


def _loop(profile, segs=POD_SEGS):
    """A closed ring solid: the profile's loop (its last point joins its first) turned round the y axis."""
    return H._lathe_y(list(profile) + [profile[0]], segs, caps=False)


def _radial(q):
    """A wall seen from the axis: oriented away from a point radially outside it."""
    return (2.0 * q[0], q[1], 2.0 * q[2])


def _back(q):
    """A face seen from behind (+y): oriented away from a point in front of it."""
    return (q[0], q[1] - 1.0, q[2])


def _box8(corners):
    """A solid from 8 corners in _obox's order (bit 0 the first axis, bit 1 the second, bit 2 the third)."""
    return list(corners), [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def _stringer(r, a, y0, y1, w=0.07, top=1.028):
    """A rib along the shell at angle a (deg) from y0 to y1: its foot inside the shell, its top at top * r."""
    u = (math.cos(math.radians(a)), 0.0, math.sin(math.radians(a)))
    t = (-u[2], 0.0, u[0])
    rm, hr = (0.955 + top) / 2 * r, (top - 0.955) / 2 * r
    return H._obox((u[0] * rm, (y0 + y1) / 2, u[2] * rm), (u[0] * hr, 0, u[2] * hr), (0, (y1 - y0) / 2, 0),
                   (t[0] * w / 2, 0, t[2] * w / 2))


# nb (art #263): the old nozzle look back. The engineer, 2026-11-01: n3/n4's stator blades, spinner and stepped
# throat read as a jet engine ("aliens on propellers?"); the pre-polish insides looked like a spaceship, "a bit like
# Daft Punk". Inside the bell again the dark throat (lens step 2's NOZZLE cone) with one cyan ring on its wall, a small
# glowing dot on its floor, and the bell's lip carrying ten light segments with gaps; n1's smooth 64-sided shells,
# bevelled lips, fairings, stringers, collar and beams kept.
SEG_N, SEG_GAP = 10, 0.06   # the lip's light segments and the gap on each side of a joint (rad): lens step 2's rhythm


def _arc(r0, r1, a0, a1, y0, y1, segs=POD_SEGS):
    """A closed curved block of a ring round the y axis (radii r0..r1, angles a0..a1, y0..y1), its arc in about
    segs-per-turn steps (no straight chord: the old segments were single blocks, a decagon)."""
    n = max(2, round((a1 - a0) / (2 * math.pi / segs)))
    v = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        c, s = math.cos(a), math.sin(a)
        v += [(r0 * c, y0, r0 * s), (r1 * c, y0, r1 * s), (r1 * c, y1, r1 * s), (r0 * c, y1, r0 * s)]
    f = [(4 * i + j, 4 * i + (j + 1) % 4, 4 * (i + 1) + (j + 1) % 4, 4 * (i + 1) + j) for i in range(n) for j in range(4)]
    f += [(0, 1, 2, 3), (4 * n, 4 * n + 1, 4 * n + 2, 4 * n + 3)]
    rc, yc, am = (r0 + r1) / 2, (y0 + y1) / 2, (a0 + a1) / 2

    def inner(q):   # the cross-section's middle at the face's angle (at an end cap: the arc's middle)
        a = math.atan2(q[2], q[0])
        if abs(math.remainder(a - a0, 2 * math.pi)) < 1e-6 or abs(math.remainder(a - a1, 2 * math.pi)) < 1e-6:
            a = am
        return (rc * math.cos(a), yc, rc * math.sin(a))
    return v, L.orient(v, f, inner)


def _bridge(r, mate, y0, y1, hd=0.22, hw=0.46, ch=0.06):
    """n1: the shared housing between this pod and a neighbour (mate [dx, dh, r] of its axis): a chamfered beam
    along y over their contact line, hiding where their collars and fairings would cross; its end bevelled, a bolt
    row on each flat side."""
    dx, dh, rb = (float(c) for c in mate)
    dist = math.hypot(dx, dh)
    d = (dx / dist, dh / dist)
    n = (-d[1], d[0])
    cd = r + (dist - r - rb) / 2
    sec = [(hd, hw - ch), (hd - ch, hw), (-hd + ch, hw), (-hd, hw - ch), (-hd, -hw + ch), (-hd + ch, -hw),
           (hd - ch, -hw), (hd, -hw + ch)]

    def ring(y, k):
        return [(d[0] * (cd + a * k) + n[0] * b * k, y, d[1] * (cd + a * k) + n[1] * b * k) for a, b in sec]
    rings = [ring(y0, 1.0), ring(y1, 1.0), ring(y1 + 0.14, 0.62)]
    v = [p for rg in rings for p in rg]
    m = len(sec)
    f = [tuple(range(m - 1, -1, -1)), tuple(range(2 * m, 3 * m))]
    for j in range(2):
        f += [(j * m + i, j * m + (i + 1) % m, (j + 1) * m + (i + 1) % m, (j + 1) * m + i) for i in range(m)]
    bolts = []
    for side in (-1, 1):
        for k in range(6):
            y = y0 + 0.55 + k * (y1 - y0 - 0.75) / 5
            c = (d[0] * cd + n[0] * side * hw, y, d[1] * cd + n[1] * side * hw)
            bolts.append(H._rod(c, (c[0] + n[0] * side * 0.022, y, c[2] + n[1] * side * 0.022), 0.028, 10))
    return (v, f), bolts


def nozzle_pod(args: dict, layout: dict) -> list:
    """A long engine pod along +y (local origin: its nose on the axis; args r, length, mount, bridges, bridge_y): a
    smooth shell with a round nose, n1's fairing where it leaves the hull (args mount, local y), six stringers, one
    dark collar, the housing round the bell (its light band: pod_ring), the bell (a solid ring, bevelled, a groove in
    its lip for the light segments) and inside it the dark throat (nb: lens step 2's cone, its ring and dot in
    pod_ring); args bridges [[dx, dh, r]] the shared housings to the neighbours' axes, from bridge_y [y0, y1]."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    ym = float(args.get("mount", ln - 2.2))
    nose = [(0.97 * r * math.sin(math.pi / 2 * k / 7) ** 0.85, 1.5 * (1 - math.cos(math.pi / 2 * k / 7)))
            for k in range(1, 8)]
    shell = H._lathe_y([(0.0, 0.0)] + nose + [(r, ln - 0.7), (0.97 * r, ln - 0.35), (0.0, ln - 0.9)], POD_SEGS)
    mount = _loop([(0.96 * r, ym - 0.75), (r, ym - 0.75), (1.03 * r, ym - 0.45), (1.06 * r, ym - 0.18),
                   (1.072 * r, ym - 0.06), (1.072 * r, ym + 0.04), (1.06 * r, ym + 0.09), (1.0 * r, ym + 0.12),
                   (0.96 * r, ym + 0.12)])
    collar = _loop([(0.97 * r, ln - 1.55), (1.0 * r, ln - 1.55), (1.03 * r, ln - 1.51), (1.04 * r, ln - 1.44),
                    (1.04 * r, ln - 1.37), (1.03 * r, ln - 1.31), (1.0 * r, ln - 1.28), (0.97 * r, ln - 1.28)])
    ribs = [_stringer(r, a, ym + 0.1, ln - 0.42) for a in POD_RIBS]
    # the housing round the bell's base: bevelled, its light groove (pod_band's strip, 1 cm proud of its floor); nb:
    # the groove near the old look's band round the bell (22 cm): 19 cm of light, n1's 8 cm read thin
    housing = _loop([(0.93 * r, ln - 0.43), (0.975 * r, ln - 0.43), (0.993 * r, ln - 0.41), (0.995 * r, ln + 0.01),
                     (0.985 * r, ln + 0.03), (0.962 * r, ln + 0.03), (0.962 * r, ln + 0.22), (0.985 * r, ln + 0.22),
                     (0.995 * r, ln + 0.24), (0.995 * r, ln + 0.25), (0.982 * r, ln + 0.27), (0.94 * r, ln + 0.285)])
    lp = ln + LIP
    bell = _loop([(0.95 * r, ln - 0.4), (0.935 * r, ln + 0.1), (0.921 * r, ln + 0.33), (0.913 * r, lp - 0.055),
                  (0.902 * r, lp - 0.02), (0.89 * r, lp), (0.873 * r, lp), (0.866 * r, lp - 0.018),
                  (0.834 * r, lp - 0.018), (0.827 * r, lp), (0.814 * r, lp), (0.805 * r, lp - 0.012),
                  (0.8 * r, lp - 0.035), (0.8 * r, ln + 0.3)])
    # nb: the old throat, a dark cone from the bell's inner wall to NOZZLE[1] 0.9 m in and its floor 1.2 m in from
    # the lip (lens step 2's 1.15 m from its lip 5 cm lower), open, shaded smooth round its 64 facets
    throat = _ring([(NOZZLE[0] * r, ln + 0.3), (NOZZLE[1] * r, ln - 0.6), (0.0, ln - 0.75)], _radial)
    smooth = {"pod_mount": 40.0, "pod_collar": 40.0, "pod_housing": 40.0, "pod_bell": 40.0,
              "pod_throat": THROAT_SMOOTH_DEG}
    parts = [_smooth(L.part("pod_shell", *shell, "hull_silver")), L.part("pod_mount", *mount, "hull_silver"),
             L.part("pod_collar", *collar, "hull_dark"), L.part("pod_ribs", *L.merge(*ribs), "ext_silver_c"),
             L.part("pod_housing", *housing, "ext_silver_c"), L.part("pod_bell", *bell, "ext_frame"),
             L.part("pod_throat", *throat, "ext_nozzle_inner", solid=False)]
    for p in parts:
        if p["name"] in smooth:
            p["smooth_deg"] = smooth[p["name"]]
    bridges = args.get("bridges", [])
    if bridges:
        b0, b1 = (float(c) for c in args.get("bridge_y", [ym - 1.0, ln - 0.9]))
        beams, bolts = [], []
        for mate in bridges:
            b, bs = _bridge(r, mate, b0, b1)
            beams.append(b)
            bolts += bs
        parts += [L.part("pod_bridge", *L.merge(*beams), "ext_frame"),
                  L.part("pod_bolts", *L.merge(*bolts), "ext_chrome")]
    return parts


def pod_ring(args: dict, layout: dict) -> list:
    """A pod's lights (local frame as nozzle_pod; glow_pod: a ring you see, not a lamp): the band in the bell
    housing's groove, the strip between two trim lips on the barrel (n1), and nb's old nozzle look: ten light
    segments with gaps in the bell's lip groove, one ring on the throat's wall 0.3 m below the shell's end, and the
    small glowing dot on its floor (ext_glow_cyan_dim). All emissive in their materials, so they glow with the ship's
    run-time lights off (the lobby); glow_pod's light (l 0.15) washes the throat teal in the ship's own night."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    lp = ln + LIP

    def out(q):
        return (0.0, q[1], 0.0)
    band = L.merge(_ring([(0.972 * r, ln + 0.031), (0.972 * r, ln + 0.219)], out),
                   _ring([(1.006 * r, ln - 0.925), (1.006 * r, ln - 0.825)], out))
    trim = L.merge(_loop([(0.99 * r, ln - 0.96), (1.017 * r, ln - 0.955), (1.017 * r, ln - 0.93),
                          (0.99 * r, ln - 0.925)]),
                   _loop([(0.99 * r, ln - 0.825), (1.017 * r, ln - 0.82), (1.017 * r, ln - 0.795),
                          (0.99 * r, ln - 0.79)]))
    # the lip's segments: lens step 2's ten (0.805..0.835 r, 6 cm deep chords) as arcs in the groove (0.836..0.864 r)
    segs = L.merge(*[_arc(0.836 * r, 0.864 * r, 2 * math.pi * k / SEG_N + SEG_GAP,
                          2 * math.pi * (k + 1) / SEG_N - SEG_GAP, lp - 0.0185, lp - 0.016) for k in range(SEG_N)])

    def wall(y):   # the throat's radius at y (its wall from 0.8 r at ln + 0.3 to 0.45 r at ln - 0.6), 6 mm inside it
        a, b = NOZZLE
        return (b + (a - b) * (y - (ln - 0.6)) / 0.9) * r - 0.006
    inner = _ring([(wall(ln - 0.27), ln - 0.27), (wall(ln - 0.33), ln - 0.33)], _radial)

    def floor(q):   # the throat's floor at radius q (x r), 6 mm above it
        return ln - 0.75 + 0.15 * q / NOZZLE[1] + 0.006
    dot = _ring([(0.12 * r, floor(0.12) - 0.004), (0.112 * r, floor(0.112)), (0.06 * r, floor(0.06) + 0.002),
                 (0.0, floor(0.0) + 0.003)], _back)
    parts = [L.part("pod_band", *band, "glow_pod", solid=False), L.part("pod_trim", *trim, "ext_frame"),
             L.part("pod_segments", *segs, "glow_pod"),
             L.part("pod_inner_ring", *inner, "glow_pod", solid=False),
             L.part("pod_dot", *dot, "ext_glow_cyan_dim", solid=False)]
    for p in parts:
        if p["name"] in ("pod_segments", "pod_inner_ring", "pod_dot"):
            p["smooth_deg"] = 40.0
    return parts


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


# polish n2 (art #263): the underbody's light lines, so the belly's and the wings' undersides read at night (they were
# dead black from below, out_lens_under_e, out_fair_lead_e_below): thin cyan strips in a dark channel under the
# hull's bottom, along the belly either side of the keel, spanwise under each corridor and a ring under each lens.
L.MATERIALS["glow_cyan__belly"] = {**L.MATERIALS["glow_cyan"], "strength": 3.0}
BELLY_LINES = [  # plan polylines (x, y), east side (mirrored)
    [(2.2, -2.6), (2.2, 4.4)],
    [(4.6, 1.2), (9.0, 1.2)],
]
BELLY_RING = (10.5, 1.2, 1.35, 48)   # the lens's centre, radius, segments


def _belly_strip(path, w, t, drop):
    """Boxes along a plan polyline under the hull's bottom (S.heights), w wide, t deep, its top `drop` under the skin;
    a step is left out where the bottom is missing or rises over 1.5 cm (no strip floats or cuts a chine)."""
    out = []
    for a, b in zip(path, path[1:]):
        ln = math.dist(a, b)
        n = max(1, int(ln / 0.2))
        d = ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
        sx, sy = -d[1] * w / 2, d[0] * w / 2
        for i in range(n):
            p0 = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            p1 = (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)
            h0, h1 = S.heights(*p0), S.heights(*p1)
            if not h0 or not h1 or abs(h0[1] - h1[1]) > 0.015:
                continue
            z0, z1 = h0[1] - drop, h1[1] - drop
            v = [(p0[0] + sx * k, p0[1] + sy * k, z0 - t * m) for m in (0, 1) for k in (-1, 1)]
            v += [(p1[0] + sx * k, p1[1] + sy * k, z1 - t * m) for m in (0, 1) for k in (-1, 1)]
            out.append((v, [(0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6), (0, 4, 6, 2), (1, 3, 7, 5)]))
    return out


# polish n3: n2's lines lie flat under a bottom 0.17 m over the ground, so from standing height they showed only as thin
# lines at a grazing angle. The chine lines run along the lower chines instead: the bottom's contour CHINE[0] m over
# the plan's zero (east side, mirrored), laid on the slanted face itself (glow facing out and down along its normal),
# only where the face slants at least CHINE[1] (rise per metre: an eye at 1.6 m, 4-8 m out, sees it) and clear of
# the nose's jaw (|x| < CHINE[2] for y < CHINE[3]). Glow only (glow_cyan__belly, l 0): no light pools on the ground.
CHINE = (0.45, 0.12, 2.0, -3.6)
CHINE_GRID = 0.12   # the marching squares' cell (m) over the bottom's heights


def _bottom(x, y):
    h = S.heights(x, y)
    return None if h is None else h[1]


def _chine_segments(level=CHINE[0], step=CHINE_GRID):
    """The bottom's contour at `level` (marching squares over S.heights' bottom), east side: [(a, b)] plan segments."""
    xs = [i * step for i in range(int(15.0 / step) + 1)]
    ys = [-9.0 + j * step for j in range(int(19.0 / step) + 1)]
    grid = [[_bottom(x, y) for y in ys] for x in xs]
    segs = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            c = [(xs[i], ys[j], grid[i][j]), (xs[i + 1], ys[j], grid[i + 1][j]),
                 (xs[i + 1], ys[j + 1], grid[i + 1][j + 1]), (xs[i], ys[j + 1], grid[i][j + 1])]
            if any(q[2] is None for q in c):
                continue
            pts = []
            for (x0, y0, h0), (x1, y1, h1) in zip(c, c[1:] + c[:1]):
                if (h0 - level) * (h1 - level) < 0:
                    f = (level - h0) / (h1 - h0)
                    pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
            if len(pts) == 2:
                segs.append(tuple(pts))
    return segs


def _chine_strip(a, b, w, o0, o1, level):
    """A box on the slanted bottom along plan segment a-b at height `level`: across the line up the slope (w wide),
    from o0 to o1 along the face's outward normal. None where the face slants under CHINE[1] or near the jaw."""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if abs(mx) < CHINE[2] and my < CHINE[3]:
        return None
    e = 0.04
    hx0, hx1, hy0, hy1 = _bottom(mx - e, my), _bottom(mx + e, my), _bottom(mx, my - e), _bottom(mx, my + e)
    if None in (hx0, hx1, hy0, hy1):
        return None
    gx, gy = (hx1 - hx0) / (2 * e), (hy1 - hy0) / (2 * e)
    g = math.hypot(gx, gy)
    if g < CHINE[1]:
        return None
    nl = math.sqrt(gx * gx + gy * gy + 1.0)
    n = (gx / nl, gy / nl, -1.0 / nl)                       # out of the bottom: down and outward
    sl = math.sqrt(1.0 + g * g)
    up = (gx / g / sl, gy / g / sl, g / sl)                 # across the line, up the slope, in the face
    v = []
    for o in (o0, o1):
        for q in (a, b):
            for k in (-1, 1):
                v.append(tuple((q[0], q[1], level)[j] + up[j] * k * w / 2 + n[j] * o for j in range(3)))
    # corners: bit 0 the side (down/up the slope), bit 1 the end (a/b), bit 2 the layer (under/over the skin)
    return v, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]


def chine_lines() -> tuple:
    """polish n3: the chine lines' channels and glows, both sides: ((verts, faces), (verts, faces))."""
    chan, glow = [], []
    for a, b in _chine_segments():
        for sx in (1, -1):
            pa, pb = (sx * a[0], a[1]), (sx * b[0], b[1])
            c = _chine_strip(pa, pb, 0.10, -0.006, 0.010, CHINE[0])
            gl = _chine_strip(pa, pb, 0.05, 0.008, 0.013, CHINE[0])
            if c and gl:
                chan.append(c)
                glow.append(gl)
    for lst in (chan, glow):   # each box wound outward from its own centre
        for i, (v, f) in enumerate(lst):
            mid = [sum(q[j] for q in v) / 8 for j in range(3)]
            lst[i] = (v, L.orient(v, f, lambda q, m=mid: m))
    return L.merge(*chan), L.merge(*glow)


def belly_lights(args: dict, layout: dict) -> list:
    """polish n2: the underbody's light lines (BELLY_LINES, BELLY_RING), both sides; origin the plan's (0, 0, 0). The
    channel hangs from 4 mm inside the skin to 8 mm under it, the glow 2 mm proud of the channel."""
    cx, cy, r, n = BELLY_RING
    ring = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
    paths = BELLY_LINES + [ring]
    paths += [[(-x, y) for x, y in p] for p in paths]
    glow, chan = [], []
    for p in paths:
        chan += _belly_strip(p, 0.09, 0.012, -0.004)
        glow += _belly_strip(p, 0.04, 0.004, 0.006)
    g = L.part("belly_glow", *L.merge(*glow), "glow_cyan__belly")
    g["nocol"] = True
    c = L.part("belly_channel", *L.merge(*chan), "ext_frame")
    c["nocol"] = True
    cc, cg = chine_lines()
    ch = L.part("chine_channel", *cc, "ext_frame")
    ch["nocol"] = True
    cgp = L.part("chine_glow", *cg, "glow_cyan__belly")
    cgp["nocol"] = True
    return [c, g, ch, cgp]


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
    n = S.P_OCULUS_N * 4   # polish n3: 128 sides shaded smooth (64 flat ones read low-poly in out_oculus_e)
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
    oc = L.part("oculus_frame", ring_v, ring_f, "ext_silver_b")
    oc["smooth_deg"] = 40.0
    return [L.part("band_frame", *L.merge(*bars), "ext_frame"), oc,
            L.part("band_glow", gv, gf, "ext_window_glow", solid=False)]


GLOW_PANE_R = 2.32   # details 1: the band's glow pane, outside the room's wall (2.21) and inside the rim (2.55)


for _name in ("edge_light", "lens_frames"):
    globals()[_name] = H._outward(globals()[_name])
