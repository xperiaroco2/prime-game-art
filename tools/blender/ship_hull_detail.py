"""The hull's details (art #263; docs/ship.md "The hull's details"): the two cockpit canopies over the hall flush
in the hull with a rim, the three nozzle pods with their cyan rings, the amber ground lamps. The HULL lane owns this
file. Rebuild B (variant J): no lead blades, stripes or tip windows (no outside light strips; the rooms have no
windows), no pod housing (J's stern face holds the pods); no hatches, seam lines or scratches.

Every builder reads the hull's top from ship_hull_shape.heights (variant J), so a detail sits on the hull wherever it
moves; pieces in the plan frame are placed at the origin. Numbers (plan metres):
- canopies: J's, a glass ellipse 0.95 (x) by 1.35 (y) at (+-2.25, -3.6), 0.75 m high, its base on the hull (+ 0.02);
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
CANOPY = {"x": 2.25, "y": -3.6, "ax": 0.95, "ay": 1.35, "height": 0.75, "segs": 28, "rings": 5}   # J's


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


def ground_lamp(args: dict, layout: dict) -> list:
    """An amber ground lamp (local origin on the ground): a low faceted housing with a glowing lens."""
    body = L.disc(0.2, 8, 0.0, 0.07)
    lens = L.disc(0.13, 8, 0.07, 0.1)
    return [L.part("lamp_body", *body, "hull_dark"), L.part("lamp_lens", *lens, "glow_amber")]


for _name in ("canopy", "nozzle_pod", "pod_ring", "ground_lamp"):
    globals()[_name] = H._outward(globals()[_name])
