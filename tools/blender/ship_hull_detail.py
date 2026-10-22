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
    bv, bf = H._lathe_y([(0.95 * r, ln - 0.4), (0.92 * r, ln + 0.35), (0.84 * r, ln + 0.4), (NOZZLE[0] * r, ln + 0.4)],
                        POD_SEGS)
    bell = (bv, L.orient(bv, bf, lambda q: (0.0, q[1] - 2.0, 0.0)))
    tv, tf = H._lathe_y([(NOZZLE[0] * r, ln + 0.4), (NOZZLE[1] * r, ln - 0.6), (0.0, ln - 0.75)], POD_SEGS)
    throat = (tv, L.orient(tv, tf, lambda q: (2.0 * q[0], q[1], 2.0 * q[2])))
    return [_smooth(L.part("pod_shell", *shell, "hull_silver")), L.part("pod_collar", *collar, "hull_dark"),
            L.part("pod_bell", *bell, "ext_frame", solid=False), L.part("pod_throat", *throat, "ext_nozzle_inner",
                                                                        solid=False)]


def pod_ring(args: dict, layout: dict) -> list:
    """A pod's cyan lights (local frame as nozzle_pod; glow_pod, dimmer than the strips: a ring you see, not a lamp):
    the band round the bell, a band on the barrel ahead of it, the segmented ring on the bell's lip and (lens step 2)
    the glowing inner ring 0.3 m down the nozzle, a dim core on its floor."""
    r, ln = float(args.get("r", 1.05)), float(args.get("length", 3.6))
    band = H._lathe_y([(0.0, ln + 0.02), (0.99 * r, ln + 0.02), (0.99 * r, ln + 0.24), (0.0, ln + 0.24)], POD_SEGS)
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
    iv, i_f = H._lathe_y([(wall(ln - 0.27), ln - 0.27), (wall(ln - 0.33), ln - 0.33)], POD_SEGS)
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


for _name in ("canopy", "nozzle_pod", "pod_ring", "ground_lamp"):
    globals()[_name] = H._outward(globals()[_name])


# --- lens step 2: the edge light and the lens windows' outer frames --------------------------------------------------
EDGE_GLOW = (0.0175, 0.006)    # the glow's half height (3.5 cm visible) and its lift off the face
EDGE_LIP = (0.04, 0.014)       # the channel's lips: out to this half height, this far proud (the glow sits 8 mm in)


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
    trail edge into the pod (ship_hull_shape.p_edge_line). A dark channel with two lips, the glow 3.5 cm high 8 mm
    in between them."""
    gh, go = EDGE_GLOW
    lh, lo = EDGE_LIP
    profile = [(0.003, lh), (lo, lh), (lo, gh), (go, gh), (go, -gh), (lo, -gh), (lo, -lh), (0.003, -lh)]
    groups: dict = {}
    for sx in (1, -1):
        for mat, (v, f) in _sweep(S.p_edge_line(sx), profile, lambda i: "glow_edge" if i == 3 else "ext_frame").items():
            groups.setdefault(mat, []).append((v, f))
    return [L.part(f"edge_{'glow' if m == 'glow_edge' else 'channel'}", *L.merge(*g), m, solid=False)
            for m, g in sorted(groups.items())]


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
    mullions), and a thin raised frame round each roof window on the slanted top."""
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
    roof = []
    la, lw = S.P_ROOF_WIN_M
    for sx in (1, -1):
        ux, uy = S.p_axis(sx)
        nx, ny = -uy, ux
        for t, w in S.P_ROOF_WIN:
            mx, my = sx * S.P_TIP[0] + t * ux + w * nx, S.P_TIP[1] + t * uy + w * ny
            cs = [(mx + a * (la / 2 + 0.025) * ux + b * (lw / 2 + 0.025) * nx,
                   my + a * (la / 2 + 0.025) * uy + b * (lw / 2 + 0.025) * ny)
                  for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            for i in range(4):
                p, q = cs[i], cs[(i + 1) % 4]
                dx, dy = q[0] - p[0], q[1] - p[1]
                ln = math.hypot(dx, dy)
                p2 = (p[0] - 0.025 * dx / ln, p[1] - 0.025 * dy / ln)
                q2 = (q[0] + 0.025 * dx / ln, q[1] + 0.025 * dy / ln)
                tops = [S.heights(*e, S.DEFAULT)[0] for e in (p2, q2)]
                roof.append(_box2(p2, q2, 0.05, tuple(h - 0.02 for h in tops), tuple(h + 0.02 for h in tops)))
    return [L.part("band_frame", *L.merge(*bars), "ext_frame"), L.part("roof_frame", *L.merge(*roof), "ext_frame")]


for _name in ("edge_light", "lens_frames"):
    globals()[_name] = H._outward(globals()[_name])
