"""The manta's details (art #263, hull lane step 2; docs/ship.md "The hull's details"): the cockpit canopies in their
teardrop fairings, the three long nozzle pods with the middle one's raised housing, the cyan lead blades, the amber
ground lamps, the inset hatches with cyan seam lines and the scratches. The EXTERIOR lane owns this file.

Every builder reads the skin's top from ship_hull_skin.section (variant F), so a detail sits on the skin wherever the
skin moves; pieces in the plan frame are placed at the origin. Numbers (plan metres):
- canopies: glass ellipse 1.1 (x) by 1.4 (y) at (+-2.5, -2.7), either side of the spine, 0.95 m high over a deck
  plane fitted to the skin under it (least squares in x and y, tilts capped at 34 deg, raised to clear the skin; the
  collar above the skin averages 0.41 m, it was 2.2 m with a deck flat across x); the fairing's teardrop outline
  1.14x round the glass, stretched 1.6x backward; its collar runs down 0.06 under the skin.
- pods: the outer two r 1.05 at (+-2.75, h 2.15) from y 3.5, 3.6 long; the middle r 1.2 at h 2.45 from y 3.9, 4.0
  long, under a faceted housing from y 3.7 (top 4.75, the hall's eave) to y 6.4 (top 3.9).
- lead blades: 0.13 x 0.07 bars (0.07 x 0.05 until step 3) on the lead edge (section point 0) from x 2.0 to
  the swept tip point.
- seam lines: 0.025 m cyan bars on the front eave crease (section point 3) from x 4.0 to 9.0."""

from __future__ import annotations

import math

import ship_hull as H
import ship_hull_skin as S
import ship_lib as L

VARIANT = None  # the skin these details sit on (None: the skin's DEFAULT, read late: ship_hull imports this module half-way)


def _v() -> dict:
    return S.VARIANTS[VARIANT or S.DEFAULT]


def _section_h(x: float, y: float) -> float | None:
    up = S.section(x, _v())[:10]
    best = None
    for (y0, h0), (y1, h1) in zip(up, up[1:]):
        if min(y0, y1) - 1e-9 <= y <= max(y0, y1) + 1e-9 and abs(y1 - y0) > 1e-9:
            h = h0 + (h1 - h0) * (y - y0) / (y1 - y0)
            best = h if best is None else max(best, h)
    return best


def skin_h(x: float, y: float) -> float | None:
    """The skin's top height at plan (x, y), None off the skin: the upper loop points 0..9 of the loft's two stations
    round |x| (ship_hull_skin.STATIONS), linear between them as the loft's faces are."""
    ax = abs(x)
    if ax > S.TIP_X:
        return None
    st = sorted({v for xs in S.STATIONS.values() for v in xs})
    i = max(k for k in range(len(st) - 1) if st[k] <= ax + 1e-9) if ax < st[-1] else len(st) - 2
    x0, x1 = st[i], st[i + 1]
    a, b = _section_h(x0, y), _section_h(x1, y)
    if a is None or b is None:
        return a if b is None else b
    t = (ax - x0) / (x1 - x0)
    return a + (b - a) * t


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
CANOPY = {"x": 2.5, "y": -2.7, "ax": 1.1, "ay": 1.4, "height": 0.95, "tilt_deg": 34.0, "segs": 20, "rings": 5}


def _canopy_frame(side):
    c = CANOPY
    cx, cy = side * c["x"], c["y"]
    ts = [2 * math.pi * k / c["segs"] for k in range(c["segs"])]

    def outline(t, k=1.14):
        s = math.sin(t)
        tail = max(0.0, s) ** 2
        return (cx + c["ax"] * k * math.cos(t) * (1 - 0.35 * tail), cy + c["ay"] * k * s * (1 + 0.6 * tail))
    rim = [outline(t) for t in ts]
    glass = [(cx + c["ax"] * math.cos(t), cy + c["ay"] * math.sin(t)) for t in ts]
    # the deck plane: a least-squares fit of the skin under the glass and the fairing (tilts capped), raised to clear
    # the skin everywhere under the glass
    pts = [(x, y, skin_h(x, y)) for x, y in glass + rim + [(cx, cy)]]
    k = len(pts)
    mx, my, mh = (sum(q[i] for q in pts) / k for i in range(3))
    sxx = sum((q[0] - mx) ** 2 for q in pts)
    syy = sum((q[1] - my) ** 2 for q in pts)
    sxy = sum((q[0] - mx) * (q[1] - my) for q in pts)
    sxh = sum((q[0] - mx) * (q[2] - mh) for q in pts)
    syh = sum((q[1] - my) * (q[2] - mh) for q in pts)
    det = sxx * syy - sxy * sxy
    cap = math.tan(math.radians(c["tilt_deg"]))
    bx = max(-cap, min(cap, (sxh * syy - syh * sxy) / det))
    by = max(-cap, min(cap, (syh * sxx - sxh * sxy) / det))
    plane = lambda x, y: mh + bx * (x - mx) + by * (y - my)  # noqa: E731
    lift = max(skin_h(x, y) - plane(x, y) for x, y in glass + [outline(t, 1.0) for t in ts]) + 0.05
    return ts, rim, glass, (lambda x, y: plane(x, y) + lift), outline


def canopy(args: dict, layout: dict) -> list:
    """A cockpit canopy (args side; part glass|fairing|glow), outside only: the hall's ceiling closes it from inside."""
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
        return [L.part("canopy_glass", v, f, "glass_tint", solid=False),
                L.part("canopy_ribs", *L.merge(*ribs), "ext_frame")]
    if part == "fairing":
        # the deck ring between the glass and the teardrop outline, the collar down into the skin, the rim lip
        inner = [(x, y, deck(x, y)) for x, y in glass]
        outer = []
        for t, (x, y) in zip(ts, rim):
            tail = max(0.0, math.sin(t)) ** 2
            sh = skin_h(x, y) or deck(x, y)
            outer.append((x, y, max(sh + 0.04, deck(x, y) - 0.7 * tail)))
        foot = [(x, y, (skin_h(x, y) or deck(x, y)) - 0.06) for x, y in rim]
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
        return H._skin("canopy_fairing", v, f, size=0.9, inset=0.018, depth=0.012) + \
            [L.part("canopy_lip", lv, lf, "ext_frame")]
    # glow: the lit cockpit floor under the glass, a dark seat and a console
    floor = [(cx + (x - cx) * 0.85, cy + (y - cy) * 0.85, 0.0) for x, y in glass]
    fv = [(x, y, deck(x, y) + 0.06) for x, y, _h in floor] + [(cx, cy, deck(cx, cy) + 0.06)]
    ff = [(j, (j + 1) % n, n) for j in range(n)]
    ff = L.orient(fv, ff, lambda _c: (cx, cy, deck(cx, cy) - 1.0))
    def on(y, hx, hy):  # the highest deck point under a box's footprint
        return max(deck(cx + sx * hx, y + sy * hy) for sx in (-1, 1) for sy in (-1, 1))
    seat = H._obox((cx, cy + 0.3, on(cy + 0.3, 0.26, 0.22) + 0.35), (0.26, 0, 0), (0, 0.22, 0), (0, 0, 0.3))
    back = H._obox((cx, cy + 0.55, on(cy + 0.55, 0.26, 0.06) + 0.6), (0.26, 0, 0), (0, 0.06, 0), (0, 0, 0.32))
    desk = H._obox((cx, cy - 0.7, on(cy - 0.7, 0.55, 0.18) + 0.3), (0.55, 0, 0), (0, 0.18, 0), (0, 0, 0.2))
    screen = H._obox((cx, cy - 0.78, on(cy - 0.78, 0.42, 0.03) + 0.53), (0.42, 0, 0), (0, 0.03, 0), (0, 0, 0.05))
    return [L.part("canopy_floor", fv, ff, "ext_glow_warm", solid=False),
            L.part("canopy_seat", *L.merge(seat, back, desk), "ext_frame"),
            L.part("canopy_screen", *screen, "ext_glow_cyan_dim")]


# --- the nozzle pods -----------------------------------------------------------------------------------------------
def nozzle_pod(args: dict, layout: dict) -> list:
    """A long engine pod along +y (local origin: its nose on the axis; args r, length): a faceted nose cone into a
    12-sided panelled barrel, a reinforcing collar, the bell and the dark throat (the lights: pod_ring)."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    shell = H._lathe_y([(0.0, 0.0), (0.45 * r, 0.25), (0.8 * r, 0.8), (0.97 * r, 1.5), (r, ln - 0.7), (0.97 * r, ln - 0.35),
                        (0.0, ln - 0.35)], 12, math.pi / 12)
    collar = H._lathe_y([(0.0, ln - 1.5), (1.04 * r, ln - 1.5), (1.04 * r, ln - 1.22), (0.0, ln - 1.22)], 12, math.pi / 12)
    bell = H._lathe_y([(0.0, ln - 0.4), (0.95 * r, ln - 0.4), (0.92 * r, ln + 0.35), (0.84 * r, ln + 0.4),
                       (0.0, ln + 0.4)], 24)
    tv, tf = H._lathe_y([(0.82 * r, ln + 0.41), (0.62 * r, ln - 0.05), (0.0, ln - 0.25)], 24)
    throat = (tv, L.orient(tv, tf, lambda q: (0.0, q[1] - 1.0, 0.0)))
    return (H._skin("pod", *shell, size=1.0, inset=0.016, depth=0.011, mats=("hull_silver", "ext_silver_b",
                                                                              "ext_silver_c"))
            + [L.part("pod_collar", *collar, "hull_dark"), L.part("pod_bell", *bell, "ext_frame"),
               L.part("pod_throat", *throat, "ext_nozzle_inner")])


def pod_ring(args: dict, layout: dict) -> list:
    """A pod's cyan lights (local frame as nozzle_pod): the band round the bell, the segmented ring in its rear face."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    band = H._lathe_y([(0.0, ln + 0.02), (0.935 * r, ln + 0.02), (0.935 * r, ln + 0.16), (0.0, ln + 0.16)], 24)
    segs = []
    for k in range(10):
        a0, a1 = 2 * math.pi * k / 10 + 0.06, 2 * math.pi * (k + 1) / 10 - 0.06
        v, f = L.sector(0.5 * r, 0.62 * r, a0, a1, ln + 0.0, ln + 0.05)
        segs.append(([(x, h, y) for x, y, h in v], f))
    core = H._lathe_y([(0.0, ln - 0.22), (0.2 * r, ln - 0.22), (0.0, ln - 0.18)], 12)
    return [L.part("pod_band", *band, "glow_cyan"), L.part("pod_segments", *L.merge(*segs), "glow_cyan"),
            L.part("pod_core", *core, "ext_glow_cyan_dim")]


HOUSING = {"y0": 3.7, "y1": 6.4, "hw": 1.55, "top_end": 3.9}


def pod_housing(args: dict, layout: dict) -> list:
    """The middle pod's raised faceted housing in the plan frame: from the hall's eave at the stern (y 3.7) back over
    the middle pod, its sides running down into the skin or onto the pod's axis past the stern."""
    hs = HOUSING
    ys = [hs["y0"] + (hs["y1"] - hs["y0"]) * k / 6 for k in range(7)]
    secs = []
    for k, y in enumerate(ys):
        top = 4.75 + (hs["top_end"] - 4.75) * min(1.0, k / 3)
        hw = hs["hw"] * (1.0 - 0.25 * max(0, k - 4) / 2)
        if k == len(ys) - 1:
            top -= 0.35
        pts = []
        for x, dh in ((-hw, None), (-0.78 * hw, -0.28), (-0.3, 0.0), (0.3, 0.0), (0.78 * hw, -0.28), (hw, None)):
            if dh is None:
                sh = skin_h(x, y)
                h = (sh - 0.06) if sh is not None and sh > 2.3 else 2.45
                h = min(h, top - 0.4)
            else:
                h = top + dh
            pts.append((x, y, h))
        secs.append(pts)
    m = 6
    v = [p for s in secs for p in s]
    f = [(i * m + j, i * m + j + 1, (i + 1) * m + j + 1, (i + 1) * m + j) for i in range(len(secs) - 1)
         for j in range(m - 1)]
    last = (len(secs) - 1) * m
    f.append(tuple(last + j for j in range(m)))
    f = L.orient(v, f, lambda q: (0.0, min(q[1], hs["y1"] - 0.4), 2.45))
    return H._skin("housing", v, f, size=1.1, inset=0.018, depth=0.012)


# --- the cyan lead blade, seam lines, hatches, scratches -----------------------------------------------------------
def _lead_path(side):
    xs = [2.0 + k * 0.5 for k in range(int((S.TIP_X - 2.0) / 0.5) + 1)]
    path = [(side * x, S.section(x, _v())[0][0], S.section(x, _v())[0][1]) for x in xs]
    hl = H._lin(_v()["hl"], S.TIP_X)
    tip = max(_v()["tip"], key=lambda p: p[0])
    for dx, dy in _v()["tip"]:
        path.append((side * (S.TIP_X + dx), dy, hl))
        if (dx, dy) == tip:
            break
    return path


def lead_blade(args: dict, layout: dict) -> list:
    """The long bright cyan blade along a wing's lead edge (args side), from x 2.0 to the swept tip point."""
    side = float(args.get("side", 1.0))
    path = _lead_path(side)
    out = [H._add(p, (0.0, -1.0, 0.0), 0.02) for p in path]
    return [L.part("lead_blade", *_bar(out, 0.13, 0.07), "glow_cyan")]  # step 3: 0.07 x 0.05 read thin from the front


def seam_lines(args: dict, layout: dict) -> list:
    """Fine cyan seam lines (args side): on the front eave crease (section point 3) from x 4.0 to 9.0 and a short
    one on the rear eave (point 6) from x 5.0 to 8.0."""
    side = float(args.get("side", 1.0))
    out = []
    for j, x0, x1 in ((3, 4.0, 9.0), (6, 5.0, 8.0)):
        xs = [x0 + (x1 - x0) * k / 10 for k in range(11)]
        path = [(side * x, S.section(x, _v())[j][0], S.section(x, _v())[j][1] + 0.018) for x in xs]
        out.append(_bar(path, 0.025, 0.02))
    return [L.part("seam_lines", *L.merge(*out), "glow_cyan")]


HATCHES = [(4.6, -2.2, 0.9, 0.6), (6.4, -2.0, 1.1, 0.55), (8.2, 2.3, 0.8, 0.5), (5.2, 2.6, 1.2, 0.5),
           (3.2, -0.6, 0.7, 0.7), (1.0, 2.2, 0.8, 0.6)]


def _on_skin(x, y, ux, uy, lift):
    """A frame on the skin at (x, y): origin, the tangent axes (along x, along y) and the normal."""
    e = 0.05
    h = skin_h(x, y)
    tx = (ux, 0.0, ((skin_h(x + e * ux, y) or h) - (skin_h(x - e * ux, y) or h)) / (2 * e) * ux)
    ty = (0.0, uy, ((skin_h(x, y + e * uy) or h) - (skin_h(x, y - e * uy) or h)) / (2 * e) * uy)
    tx, ty = H._norm(tx), H._norm(ty)
    n = H._norm(H._cross(tx, ty))
    if n[2] < 0:
        n = (-n[0], -n[1], -n[2])
    return (x, y, h + lift), tx, ty, n


def hatches(args: dict, layout: dict) -> list:
    """Inset service hatches on a side's skin (args side): a bevelled frame round a recessed plate with two dark
    handle slots, plus thin bright scratches over the upper skin (a seeded scatter)."""
    side = float(args.get("side", 1.0))
    frames, plates, slots, scratches = [], [], [], []
    for x, y, a, b in HATCHES:
        o, tx, ty, n = _on_skin(side * x, y, side, 1.0, 0.0)
        for (sa, sb, la, lb) in ((0, -1, a, 0.04), (0, 1, a, 0.04), (-1, 0, 0.04, b), (1, 0, 0.04, b)):
            c = H._add(H._add(H._add(o, tx, sa * (a - 0.04)), ty, sb * (b - 0.04)), n, 0.025)
            frames.append(H._obox(c, H._lerp((0, 0, 0), tx, la), H._lerp((0, 0, 0), ty, lb),
                                  H._lerp((0, 0, 0), n, 0.03)))
        plates.append(H._obox(H._add(o, n, 0.004), H._lerp((0, 0, 0), tx, a - 0.08), H._lerp((0, 0, 0), ty, b - 0.08),
                              H._lerp((0, 0, 0), n, 0.012)))
        for s in (-1, 1):
            c = H._add(H._add(o, tx, s * 0.45 * a), n, 0.018)
            slots.append(H._obox(c, H._lerp((0, 0, 0), tx, 0.09), H._lerp((0, 0, 0), ty, 0.025),
                                 H._lerp((0, 0, 0), n, 0.004)))
    for k in range(40):
        x = 2.2 + 7.6 * H._hash(side, k, 1)
        y = -3.6 + 7.4 * H._hash(side, k, 2)
        if skin_h(x, y) is None:
            continue
        o, tx, ty, n = _on_skin(side * x, y, side, 1.0, 0.0)
        ang = math.pi * H._hash(side, k, 3)
        d = H._norm(H._add(H._lerp((0, 0, 0), tx, math.cos(ang)), ty, math.sin(ang)))
        w = H._norm(H._cross(n, d))
        ln = 0.18 + 0.5 * H._hash(side, k, 4)
        c = H._add(o, n, 0.004)
        scratches.append(([H._add(H._add(c, d, s1 * ln / 2), w, s2 * 0.006) for s1, s2 in ((-1, -1), (1, -1), (1, 1),
                                                                                          (-1, 1))], [(0, 1, 2, 3)]))
    sv, sf = L.merge(*scratches)
    sf = L.orient(sv, sf, lambda q: (q[0], q[1], q[2] - 1.0))
    return [L.part("hatch_frames", *L.merge(*frames), "ext_frame"),
            L.part("hatch_plates", *L.merge(*plates), "ext_silver_c"),
            L.part("hatch_slots", *L.merge(*slots), "ext_seam"),
            L.part("scratches", sv, sf, "ext_chrome", solid=False)]


def ground_lamp(args: dict, layout: dict) -> list:
    """An amber ground lamp (local origin on the ground): a low faceted housing with a glowing lens."""
    body = L.disc(0.2, 8, 0.0, 0.07)
    lens = L.disc(0.13, 8, 0.07, 0.1)
    return [L.part("lamp_body", *body, "hull_dark"), L.part("lamp_lens", *lens, "glow_amber")]


for _name in ("canopy", "nozzle_pod", "pod_ring", "pod_housing", "lead_blade", "seam_lines", "hatches",
              "ground_lamp"):
    globals()[_name] = H._outward(globals()[_name])
