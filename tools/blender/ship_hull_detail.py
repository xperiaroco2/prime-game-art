"""The manta's details on the smooth skin (art #263 v2, hull lane step 2; docs/ship.md "The hull's details"): the
cockpit canopies flush in the forward hull with a rim, the three nozzle pods with the middle one's housing, the cyan
lead blades and diagonal stripes, the tip windows' glass and frames, the amber ground lamps. The HULL lane owns this
file. No hatches, seam lines or scratches: the skin is one clean surface (the engineer after the night build).

Every builder reads the skin's top from ship_hull_smooth.heights (variant DEFAULT), so a detail sits on the skin
wherever the skin moves; pieces in the plan frame are placed at the origin. Numbers (plan metres):
- canopies: a glass ellipse 1.15 (x) by 1.5 (y) at (+-2.3, -2.75), 0.85 m high, its base on the skin (skin_h + 0.02);
  a low smooth teardrop collar round it 0.03 over the skin; a dark rim lip; a lit floor, seat and desk under the glass.
- pods: the outer two r 1.05 at (+-2.75, h 2.15) from y 3.85, the middle r 1.2 at h 2.45 from y 4.25; smooth
  32-sided shells with a round nose, one dark collar, the bell; the middle one under a smooth housing (y 3.7..6.4).
- lead blades: 0.24 x 0.12 bars along the smooth lead edge from x 2.7 to the tip (x 13.6).
- stripes: 12 slanted cyan bars per side from x 3.0 to 10.4, each wrapping the lead edge (0.25 m under, 0.6 m over).
- tip windows: glass on the skin's open band round (+-8.3, 0) (rings pod_r(HEAD + 0.05) .. pod_r(SILL - 0.05), +-65 deg),
  a head and a sill bar, two jambs and three mullions, 0.03 m proud."""

from __future__ import annotations

import math

import ship_hull as H
import ship_hull_smooth as SM
import ship_lib as L

VARIANT = None  # the skin these details sit on (None: ship_hull_smooth.DEFAULT)


def _v() -> dict:
    return SM.VARIANTS[VARIANT or SM.DEFAULT]


def skin_h(x: float, y: float) -> float | None:
    """The smooth skin's top height at plan (x, y), None off its outline."""
    v, ax = _v(), abs(x)
    if ax > SM.SPAN_X or not (SM.lead(ax, v) - 1e-9 <= y <= SM.trail(ax, v) + 1e-9):
        return None
    return SM.heights(x, y, v)[0]


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
CANOPY = {"x": 2.3, "y": -2.75, "ax": 1.15, "ay": 1.5, "height": 0.85, "segs": 28, "rings": 5}


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
    round it and a lit floor, seat and desk under the tinted glass."""
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
        return [_smooth(L.part("canopy_glass", v, f, "glass_tint", solid=False)),
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
    # glow: the lit cockpit floor under the glass, a dark seat and a console
    floor = [(cx + (x - cx) * 0.85, cy + (y - cy) * 0.85, 0.0) for x, y in glass]
    fv = [(x, y, deck(x, y) + 0.06) for x, y, _h in floor] + [(cx, cy, deck(cx, cy) + 0.06)]
    ff = [(j, (j + 1) % n, n) for j in range(n)]
    ff = L.orient(fv, ff, lambda _c: (cx, cy, deck(cx, cy) - 1.0))
    def on(y, hx, hy):  # the highest deck point under a box's footprint
        return max(deck(cx + sx * hx, y + sy * hy) for sx in (-1, 1) for sy in (-1, 1))
    # hull 3-2: low enough to stay under the flush glass (0.85 high at the centre)
    seat = H._obox((cx, cy + 0.25, on(cy + 0.25, 0.26, 0.22) + 0.2), (0.26, 0, 0), (0, 0.22, 0), (0, 0, 0.14))
    back = H._obox((cx, cy + 0.5, on(cy + 0.5, 0.26, 0.06) + 0.4), (0.26, 0, 0), (0, 0.06, 0), (0, 0, 0.2))
    desk = H._obox((cx, cy - 0.55, on(cy - 0.55, 0.5, 0.16) + 0.2), (0.5, 0, 0), (0, 0.16, 0), (0, 0, 0.12))
    screen = H._obox((cx, cy - 0.62, on(cy - 0.62, 0.4, 0.03) + 0.36), (0.4, 0, 0), (0, 0.03, 0), (0, 0, 0.05))
    return [L.part("canopy_floor", fv, ff, "ext_glow_warm", solid=False),
            L.part("canopy_seat", *L.merge(seat, back, desk), "ext_frame"),
            L.part("canopy_screen", *screen, "ext_glow_cyan_dim")]


# --- the nozzle pods -----------------------------------------------------------------------------------------------
POD_SEGS = 32


def nozzle_pod(args: dict, layout: dict) -> list:
    """A long engine pod along +y (local origin: its nose on the axis; args r, length): a smooth shell with a round
    nose (shaded smooth, no plates), one dark collar, the bell and the dark throat (the lights: pod_ring)."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    nose = [(0.97 * r * math.sin(math.pi / 2 * k / 7) ** 0.85, 1.5 * (1 - math.cos(math.pi / 2 * k / 7)))
            for k in range(1, 8)]
    shell = H._lathe_y([(0.0, 0.0)] + nose + [(r, ln - 0.7), (0.97 * r, ln - 0.35), (0.0, ln - 0.35)], POD_SEGS)
    collar = H._lathe_y([(0.0, ln - 1.5), (1.03 * r, ln - 1.5), (1.03 * r, ln - 1.3), (0.0, ln - 1.3)], POD_SEGS)
    bell = H._lathe_y([(0.0, ln - 0.4), (0.95 * r, ln - 0.4), (0.92 * r, ln + 0.35), (0.84 * r, ln + 0.4),
                       (0.0, ln + 0.4)], POD_SEGS)
    tv, tf = H._lathe_y([(0.82 * r, ln + 0.41), (0.62 * r, ln - 0.05), (0.0, ln - 0.25)], POD_SEGS)
    throat = (tv, L.orient(tv, tf, lambda q: (0.0, q[1] - 1.0, 0.0)))
    return [_smooth(L.part("pod_shell", *shell, "hull_silver")), L.part("pod_collar", *collar, "hull_dark"),
            L.part("pod_bell", *bell, "ext_frame"), L.part("pod_throat", *throat, "ext_nozzle_inner")]


def pod_ring(args: dict, layout: dict) -> list:
    """A pod's cyan lights (local frame as nozzle_pod): the band round the bell, a band on the barrel ahead of it, the
    segmented ring in its rear face and the bright inner ring in the nozzle's mouth."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    band = H._lathe_y([(0.0, ln + 0.02), (0.99 * r, ln + 0.02), (0.99 * r, ln + 0.24), (0.0, ln + 0.24)], POD_SEGS)
    band2 = H._lathe_y([(0.0, ln - 0.95), (1.015 * r, ln - 0.95), (1.015 * r, ln - 0.8), (0.0, ln - 0.8)], POD_SEGS)
    segs = []
    for k in range(10):
        a0, a1 = 2 * math.pi * k / 10 + 0.06, 2 * math.pi * (k + 1) / 10 - 0.06
        v, f = L.sector(0.5 * r, 0.62 * r, a0, a1, ln + 0.0, ln + 0.05)
        v = [(x, h, y) for x, y, h in v]  # the swap mirrors the winding: orient the faces rearward (polish 4)
        segs.append((v, L.orient(v, f, lambda q: (0.0, q[1] - 1.0, 0.0))))
    core = H._lathe_y([(0.0, ln - 0.22), (0.2 * r, ln - 0.22), (0.0, ln - 0.18)], 12)
    inner = []
    for k in range(24):
        v, f = L.sector(0.5 * r, 0.72 * r, 2 * math.pi * k / 24, 2 * math.pi * (k + 1) / 24, ln + 0.405, ln + 0.435)
        v = [(x, h, y) for x, y, h in v]
        inner.append((v, L.orient(v, f, lambda q: (0.0, q[1] - 1.0, 0.0))))
    return [L.part("pod_band", *L.merge(band, band2), "glow_cyan"),
            L.part("pod_segments", *L.merge(*segs, *inner), "glow_cyan"),
            L.part("pod_core", *core, "ext_glow_cyan_dim")]


HOUSING = {"y0": 4.25, "y1": 6.4, "hw": 1.55, "top_end": 3.9, "rows": 13, "cols": 9}


def pod_housing(args: dict, layout: dict) -> list:
    """The middle pod's smooth housing in the plan frame: from the hall's eave at the stern (y 3.7) back over the
    middle pod (from y 4.25, out of the hall; its front rises out of the skin), a rounded section whose sides run down into the skin (or onto the pod's axis past the stern)."""
    hs = HOUSING
    nr, m = hs["rows"], hs["cols"]
    secs = []
    for k in range(nr):
        t = k / (nr - 1)
        y = hs["y0"] + (hs["y1"] - hs["y0"]) * t
        top = 4.75 + (hs["top_end"] - 4.75) * min(1.0, 2 * t) - 0.35 * max(0.0, (t - 0.85) / 0.15) ** 2
        hw = hs["hw"] * (1.0 - 0.25 * max(0.0, (t - 0.66) / 0.34))
        pts = []
        for j in range(m):
            th = math.pi * j / (m - 1)
            x = -hw * math.cos(th)
            sh = skin_h(hw, y)
            base = min((sh - 0.06) if sh is not None and sh > 2.3 else 2.45, top - 0.4)
            pts.append((x, y, base + (top - base) * math.sin(th) ** 0.6))
        secs.append(pts)
    v = [p for s in secs for p in s]
    f = [(i * m + j, i * m + j + 1, (i + 1) * m + j + 1, (i + 1) * m + j) for i in range(nr - 1) for j in range(m - 1)]
    inner = lambda q: (0.0, min(q[1], hs["y1"] - 0.4), 2.45)  # noqa: E731
    cap = [tuple((nr - 1) * m + j for j in range(m))]
    return [_smooth(L.part("housing", v, L.orient(v, f, inner), "hull_silver", solid=False)),
            L.part("housing_cap", v, L.orient(v, cap, inner), "hull_silver", solid=False)]


# --- the cyan lead blades and stripes ------------------------------------------------------------------------------
BLADE = (2.7, SM.SPAN_X - 0.15, 0.25)   # x from, x to, step


def _lead_path(side):
    v, (x0, x1, dx) = _v(), BLADE
    xs = [x0 + k * dx for k in range(int((x1 - x0) / dx) + 1)]
    if xs[-1] < x1 - 1e-6:
        xs.append(x1)
    return [(side * x, SM.lead(x, v), SM.edge_h(x, v)[0]) for x in xs]


def lead_blade(args: dict, layout: dict) -> list:
    """The long bright cyan blade along a wing's lead edge (args side), from x 2.7 to the curled tip."""
    side = float(args.get("side", 1.0))
    out = [H._add(p, (0.0, -1.0, 0.0), 0.02) for p in _lead_path(side)]
    return [L.part("lead_blade", *_bar(out, 0.24, 0.12), "glow_cyan")]


STRIPES = {"count": 12, "x0": 3.0, "x1": 10.4, "width": 0.3, "slant": 0.42, "under": 0.25, "over": 0.6}


def _wrap(x, s):
    """A point s metres from the lead edge round it (s < 0 under on the belly, s > 0 over on the top) at |x|, and the
    outward direction there."""
    v = _v()
    y = SM.lead(x, v) + abs(s)
    top, bot = SM.heights(x, y, v)
    w = min(1.0, abs(s) / 0.1)
    up = (0.0, -(1 - w), w if s >= 0 else -w)
    return (x, y, top if s >= 0 else bot), H._norm(up)


def stripe_bars(side):
    """The slanted bars as closed slabs (each a 2 x 9 sheet, 0.035 proud of the skin and 0.01 under it)."""
    st = STRIPES
    ss = [-st["under"] + (st["under"] + st["over"]) * k / 8 for k in range(9)]
    out = []
    for k in range(st["count"]):
        xa = st["x0"] + k * (st["x1"] - st["x0"]) / st["count"]
        outer, under = [], []
        for s in ss:
            xs = xa + st["slant"] * (s + st["under"]) / (st["under"] + st["over"])
            for x in (xs, xs + st["width"]):
                p, n = _wrap(x, s)
                q = (side * p[0], p[1], p[2])
                outer.append(H._add(q, n, 0.035))
                under.append(H._add(q, n, -0.01))
        nb = len(outer)
        f = []
        for i in range(len(ss) - 1):
            a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
            f += [(a, b, c, d), (nb + d, nb + c, nb + b, nb + a), (a, d, nb + d, nb + a), (b, nb + b, nb + c, c)]
        f += [(0, nb, nb + 1, 1), (nb - 2, nb - 1, 2 * nb - 1, 2 * nb - 2)]
        out.append((outer + under, f))
    return out


def smooth_stripes(args: dict, layout: dict) -> list:
    """The cyan diagonal light bars wrapping a wing's lead edge (args side), one piece per side."""
    return [L.part("stripes", *L.merge(*stripe_bars(float(args.get("side", 1.0)))), "glow_cyan")]


# --- the tip windows -----------------------------------------------------------------------------------------------
def _band_pt(side, a, r, lift=0.0):
    x, y = SM.TIP_X + r * math.cos(a), r * math.sin(a)
    h = SM.heights(x, y, _v())[0]
    return (side * (x + lift * math.cos(a)), y + lift * math.sin(a), h)


def smooth_window(args: dict, layout: dict) -> list:
    """The tip's big window in the skin's open band (args side; plan frame): tinted glass on the band's rings (head,
    middle, sill) within the window's half angle, a head and a sill bar along the band's edges, the two jambs and
    three mullions down the slope, all about 0.03 m proud."""
    side = float(args.get("side", 1.0))
    rh, rs = SM.pod_r(SM.HEAD + 0.05), SM.pod_r(SM.SILL - 0.05)
    rings = (rh, (rh + rs) / 2, rs)
    angs = L.angles(-SM.HALF, SM.HALF, SM.RAY)
    m = len(angs)
    gv = [_band_pt(side, a, r, -0.01) for r in rings for a in angs]
    gf = [(i * m + j, i * m + j + 1, (i + 1) * m + j + 1, (i + 1) * m + j) for i in range(2) for j in range(m - 1)]
    gf = L.orient(gv, gf, lambda q: (side * SM.TIP_X, 0.0, q[2] - 2.0))
    frames = [_bar([_band_pt(side, a, r, 0.03) for a in angs], 0.12, 0.08) for r in (rh, rs)]
    for a in (-SM.HALF, -SM.HALF / 2, 0.0, SM.HALF / 2, SM.HALF):
        w = 0.12 if abs(a) == SM.HALF else 0.07
        frames.append(_bar([_band_pt(side, a, r, 0.03) for r in rings], w, 0.06))
    return [_smooth(L.part("window_glass", gv, gf, "glass_window", solid=False)),
            L.part("window_frame", *L.merge(*frames), "ext_frame")]


def ground_lamp(args: dict, layout: dict) -> list:
    """An amber ground lamp (local origin on the ground): a low faceted housing with a glowing lens."""
    body = L.disc(0.2, 8, 0.0, 0.07)
    lens = L.disc(0.13, 8, 0.07, 0.1)
    return [L.part("lamp_body", *body, "hull_dark"), L.part("lamp_lens", *lens, "glow_amber")]


for _name in ("canopy", "nozzle_pod", "pod_ring", "pod_housing", "lead_blade", "smooth_stripes", "smooth_window",
              "ground_lamp"):
    globals()[_name] = H._outward(globals()[_name])
