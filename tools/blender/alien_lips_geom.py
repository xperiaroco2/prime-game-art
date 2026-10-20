"""M8 (art #196): the alien's lips shaped like lips, not two rolls of one thickness. Plain Python (no Blender), used by
alien_mouths.py's build_piece and tested in tools/tests/test_alien_lips_geom.py.

The S6..M6c lips are tubes (closed shapes) or a ring (open shapes) whose half-height follows the sheet's measured
edges, smoothed, with an elliptical section; on the head they read as two sausages of nearly one thickness end to end.
The approved sheets (mf1, mo1) and rf2 show each lip fine at the corners and fullest in the middle, the upper lip
thinner with a soft dip at its centre (a gentle bow), the lower lip a rounder cushion, a defined line where they meet
and the corners tucked into the skin. A lip shape (LIP_SHAPE, or a variant merged over it) is:

- w: how far the designed profile replaces the measured one (0: the M6c lips exactly, 1: the designed profile);
- corner: a lip's thickness at its corners as a share of its centre's; pw: the profile's exponent (T below);
- full: the centre's thickness times this (against the measured centre);
- upper, lower: each lip's thickness times this (the upper thinner, the lower fuller);
- bow: the upper lip's top edge dips at its centre by this share of the upper lip's centre height (bow_w: the dip's
  half width in s), with two soft peaks either side (bow_peak of the dip, at bow_at);
- lean: the section's forward swell moves toward the lip line (the edge where the lips meet) by this share, so both
  lips are fullest at the line and it reads as a crisp crease; square: the section's superellipse exponent (1: an
  ellipse; below 1 a flatter, cushion-like front);
- depth_corner: the share of a lip's constant depth (alien_mouths.DEPTH_C) kept at the corners, so the corners sink
  to a point instead of ending as blunt caps;
- ring: per open shape (A, E, O) the weight of the profile on the ring (O's pucker is round, so less);
- width (M8b): the mouth's width as a share of the sheet-measured one (1: M8's first lips, about 0.8 of the face's
  silhouette at the socket). Every x of a piece (lips, cup, tongue, teeth) is scaled about the face's centre line by
  it (scale_x), its heights are kept, so all six phases narrow together and the corners still meet the skin where
  they now sit (the pieces are laid on the skin by ray casts at the scaled x);
- plump (M10): both lips' thickness times this on top of `full` (1: M8b's lips). The depth follows the thickness
  (alien_mouths.DEPTH_A), so the volume grows with it; the bow's dip (a share of the thickness), the corners' taper
  (`corner`, a share of the centre) and the lip line are kept.
- size (M12): the whole mouth (x and height) as a share of the sheet-measured one, about the face's centre line and
  the Mouth socket's height (scale_size), so a design measured off its own sheet gets its own size on the fixed mount.

Every edit keeps the lip line where the sheet measured it: the upper lip moves its top edge, the lower lip its bottom
edge, an open ring its outer edge, so the six speech phases keep their openings and stay consistent.
"""
from __future__ import annotations

import math

# The M6c lips (S9's tubes and rings): no change at all.
LIP_SHAPE_M6C = {"w": 0.0}

# The pick (M8's grid, cell c8: corner 0.15, full 1.2, bow 0.30; see docs/godot.md, M8).
LIP_SHAPE = {
    "w": 1.0, "corner": 0.15, "pw": 1.8, "full": 1.2, "upper": 0.82, "lower": 1.12,
    "bow": 0.30, "bow_w": 0.085, "bow_peak": 0.35, "bow_at": 0.20,
    "lean": 0.30, "square": 0.85, "depth_corner": 0.25,
    "ring": {"A": 1.0, "E": 1.0, "O": 0.35},
    "width": 0.72,
    "plump": 1.0,
}

# M9b (art #196, PR #242's review minor 2): the mouth mount, the mouth-side twin of alien_lids_geom.SOCKET. The skin's
# marks round the mouth (alien_detail.py's philtrum and nasolabial lines, alien_texture.py's soft mouth rim, flush and
# cheek patches) hang on this constant box, placed by the `Mouth` socket node (rest pose, world), never on one mouth
# piece's box (they followed `mouth_frog_rest`'s), so a new mouth design or width lands on the same neutral skin. The
# values are M8b's frog rest box measured on its kit (centre 2.7 mm below and 3.8 mm behind the node, half width 41.4 mm, half height
# 20.8 mm, its front 19.8 mm before the node), centred on the face's midline (frog rest's box sat 1.4 mm to one side),
# so the frog and overbite skin reads as in M8b. Metres.
MOUTH_MOUNT = {"dy": 0.0038, "dz": -0.0027, "half_w": 0.0414, "half_h": 0.0208, "front": -0.0198}


def mouth_mount(node: tuple, m: dict = MOUTH_MOUNT) -> tuple:
    """The mount box from the Mouth node's world position (x, y, z; Blender: z up, the face toward -y): its centre
    (x 0, the face's midline), half width, half height and front y."""
    return ((0.0, node[1] + m["dy"], node[2] + m["dz"]), m["half_w"], m["half_h"], node[1] + m["front"])


# M12 (art #196): the red pout mouth mp1 (D:/prime-art-raw/2026-10-20-alien-face-sheets-2/mp1/), the third mouth
# design ("pout") on the same mount. Its sheet already draws full lips, so the profile keeps about the sheet's
# thickness per lip (upper 0.95, lower 1.10: the lower lip the bigger cushion), tapers to fine tucked ends a little
# rounder than the frog's (corner 0.18, pw 2.0), a soft cupid's bow (0.25; at 0.45 with corner 0.30 the upper lip
# read as four lumps), M8's section (square 0.85, lean 0.25) and corners that sink a little less (depth_corner 0.35);
# O, the kiss, keeps half the profile; the bow's side peaks low (bow_peak 0.15: at 0.40 the upper lip had four lumps).
# size 0.95 and plump 1.15: the pick of M12's 3 x 2 grid (size 0.85 / 0.95 / 1.05 x plump 1.00 / 1.15). ring_corner (0.45): the open rings' corners keep this share of the centre's
# thickness (E's wide corners at 0.18 were thin flaps the AO painted almost black). size and plump are the grid's pick
# (docs/godot.md, M12).
# M12b (UPDATE 19): the bow softer and wider (0.14 over bow_w 0.16, side peaks 0.10; at 0.25 / 0.10 with the depth
# dipping too the upper lip read as two balls), and it notches the outline only (bow_flat 1: the depth from the lip
# without the bow, so the front is one continuous roll). A, E and O are designed rings (ring_param; the traced
# contours waved, tore and ran out in spikes; see ring_param): the opening a superellipse inside the measured
# envelope, an even roll round it with round corners (A 0.68 of the centre's thickness, E 0.60) tucked 35 % of their
# depth into the skin, A 4 % wider; O a round hole of 0.30 of its half width in an even pursed ring with the sheet's
# M-shaped top (bow 0.30), its dark cup lifted to 0.85 of the lips' axis depth (cup_throat: else the hole showed the
# lips' long lit inner wall, a pale triangle); every ring stands out along the mouth's mean normal (n_flat 1: along the skin's own, the
# chin's and philtrum's slopes squeezed O's hole to a slit). The variant grids: docs/godot.md, M12b.
_RING = {"bow": 0.12, "tuck": 0.35, "side_keep": 0.85, "depth_corner": 0.5, "n_flat": 1.0}
LIP_SHAPE_POUT = {
    "w": 1.0, "corner": 0.18, "pw": 2.0, "full": 1.0, "upper": 0.95, "lower": 1.10,
    "bow": 0.14, "bow_w": 0.16, "bow_peak": 0.10, "bow_at": 0.24,
    "lean": 0.25, "square": 0.85, "depth_corner": 0.35,
    "ring": {"A": 1.0, "E": 1.0, "O": 0.5}, "ring_corner": 0.45,
    "width": 1.0, "size": 0.95, "plump": 1.15,
    "bow_flat": 1.0,
    "ring_param": {
        "A": dict(_RING, n=2.1, corner=0.68, wide=1.04),
        "E": dict(_RING, n=2.0, corner=0.60),
        "O": dict(_RING, n=2.0, hole=0.30, corner=1.0, thick=0.9, bow=0.30, tuck=0.0, cup_throat=0.85),
    },
}

# M12: the third mouth's contact channel. TEXCOORD_4 (bored, manic) and TEXCOORD_5 (frog, overbite) are full, so the
# pout mouth's skin contact is Body's seventh UV layer, glTF TEXCOORD_6 (u: pout, v: free for the next mouth, mg2),
# which Godot imports as CUSTOM2 (x pout). Like the other layers, v is stored flipped (the exporter writes 1 - v).
CONTACT_UV_MOUTH2 = ("contact_mouth2", ("pout", ""))
CONTACT_MARKER_MOUTH2 = {"prime_contact_mouth2": "custom2_xy"}


def merged(over: dict | None) -> dict:
    """LIP_SHAPE with `over` merged on top (the ring weights merged key by key); None or {} is LIP_SHAPE itself."""
    out = dict(LIP_SHAPE)
    out["ring"] = dict(LIP_SHAPE["ring"])
    for k, v in (over or {}).items():
        if k == "ring":
            out["ring"].update(v)
        else:
            out[k] = v
    return out


def scale_x(world, k: float):
    """world(x_px, y_px) -> (x, z) with x scaled by k about the face's centre line (x = 0); world itself for k = 1."""
    if k == 1.0:
        return world

    def scaled(x, y):
        wx, wz = world(x, y)
        return wx * k, wz
    return scaled


def scale_size(world, k: float, z0: float):
    """world(x_px, y_px) -> (x, z) scaled by k about (0, z0) (the face's centre line, the Mouth socket's height);
    world itself for k = 1."""
    if k == 1.0:
        return world

    def scaled(x, y):
        wx, wz = world(x, y)
        return wx * k, z0 + (wz - z0) * k
    return scaled


def merged_pout(over: dict | None = None) -> dict:
    """LIP_SHAPE_POUT with `over` merged on top (as merged(); ring_param merged shape by shape, key by key)."""
    out = dict(LIP_SHAPE_POUT)
    out["ring"] = dict(LIP_SHAPE_POUT["ring"])
    out["ring_param"] = {k: dict(v) for k, v in LIP_SHAPE_POUT.get("ring_param", {}).items()}
    for k, v in (over or {}).items():
        if k == "ring":
            out["ring"].update(v)
        elif k == "ring_param":
            for shape, rp in v.items():
                out["ring_param"].setdefault(shape, {}).update(rp)
        else:
            out[k] = v
    return out


def taper(s: float, p: dict) -> float:
    """The thickness along a lip relative to its centre's: 1 at s = 0, p["corner"] at the corners (|s| = 1), a
    pointed lens between (1 - |s|^pw has a finite slope at the end, so the lip ends in a point, not a round cap)."""
    a = min(1.0, abs(s))
    return p["corner"] + (1.0 - p["corner"]) * (1.0 - a ** p["pw"])


def bow(s: float, p: dict) -> float:
    """The upper lip's top-edge offset in shares of its centre height: negative (down) at the centre, a small rise
    at +-bow_at, nothing toward the corners."""
    g = math.exp(-(s / p["bow_w"]) ** 2)
    pk = math.exp(-((abs(s) - p["bow_at"]) / p["bow_w"]) ** 2)
    return p["bow"] * (-g + p["bow_peak"] * pk)


def centre_value(ss, vals, within: float = 0.3) -> float:
    """The median of vals where |s| < within (the lip's measured centre)."""
    mid = sorted(v for s, v in zip(ss, vals) if abs(s) < within)
    if not mid:
        mid = sorted(vals)
    n = len(mid)
    return mid[n // 2] if n % 2 else 0.5 * (mid[n // 2 - 1] + mid[n // 2])


def closed_edges(ss, top, bot, lip: str, p: dict):
    """A closed shape's lip (`u` or `l`) re-profiled: ss the stations' s in [-1, 1], top/bot its measured edges (z, m,
    top > bot). Keeps the lip line (the upper lip's bottom, the lower lip's top) and moves the outer edge to the
    designed thickness: returns (top, bot) lists."""
    w = p.get("w", 0.0)
    if w <= 0.0:
        return list(top), list(bot)
    hb = [(t - b) / 2 for t, b in zip(top, bot)]
    hc = centre_value(ss, hb)
    k = p["upper"] if lip == "u" else p["lower"]
    full = p["full"] * p.get("plump", 1.0)
    nt, nb = [], []
    for s, t, b, h in zip(ss, top, bot, hb):
        target = hc * full * k * taper(s, p)
        h2 = h + w * (target - h)
        if lip == "u":
            t2 = b + 2 * h2 + w * bow(s, p) * 2 * hc * k * full
            nt.append(max(t2, b + 1e-4))
            nb.append(b)
        else:
            nt.append(t)
            nb.append(t - 2 * h2)
    return nt, nb


def depth_scale(s: float, p: dict) -> float:
    """The share of the constant depth term kept at s (1 at the centre, depth_corner at the corners), blended by w."""
    w = p.get("w", 0.0)
    if w <= 0.0:
        return 1.0
    t = (taper(s, p) - p["corner"]) / max(1e-6, 1.0 - p["corner"])
    return 1.0 + w * (p["depth_corner"] + (1.0 - p["depth_corner"]) * t - 1.0)


def ring_width(th: float, hw: float, hc: float, low: float, shape: str, p: dict) -> float:
    """An open ring's lip half width at angle th (cos th = +-1 at the corners, sin th > 0 the lower lip; low the
    lower lip's share at th): hw measured, hc the ring's measured centre width."""
    w = p.get("w", 0.0) * p.get("ring", {}).get(shape, 1.0)
    if w <= 0.0:
        return hw
    s = math.cos(th)
    k = p["upper"] + (p["lower"] - p["upper"]) * low
    tp = dict(p, corner=p["ring_corner"]) if "ring_corner" in p else p  # M12: the open ring's own corner
    target = hc * p["full"] * p.get("plump", 1.0) * k * taper(s, tp)
    up = max(0.0, -math.sin(th))  # the upper lip's top centre: the bow
    target *= 1.0 + bow(s, p) * up * up
    return hw + w * (target - hw)


def section(phi: float, lean: float, square: float, toward_line: float) -> tuple[float, float]:
    """A lip's section point at angle phi: (along the skin normal, across) in shares of the half axes. The ellipse
    (cos, sin) with the front made flatter by `square` (a superellipse) and its forward swell moved toward the lip
    line by `lean`: toward_line is +1 when sin(phi) > 0 points at the lip line, -1 when it points away."""
    c, s = math.cos(phi), math.sin(phi)
    cn = math.copysign(abs(c) ** square, c)
    if c > 0:
        cn *= 1.0 + lean * s * toward_line
    return cn, s


def flat_bow(p: dict) -> dict:
    """M12b: the lip shape whose thickness gives a lip's depth (the tube's forward radius): with bow_flat 1 the bow is
    left out, so the bow notches the upper lip's outline only and its front stays one continuous roll (the bow's
    dip in the depth made two separate balls); 0 the bow as before."""
    k = p.get("bow_flat", 0.0)
    return p if k <= 0.0 else dict(p, bow=p["bow"] * (1.0 - k))


def _smooth01(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ring_param(meas: dict, rp: dict, p: dict, n: int):
    """M12b: an open mouth's ring as designed curves, not the sheet's traced contours (they waved, the roll's
    thickness changed along the rim, the inner edge was ragged and E's corners ran out in spikes). From the panel's
    measured scalars (px; meas: cx, cy the opening's centre, W the lips' outer half width, hu the opening's half
    height at the centre, t_u, t_l the lips' thickness at the centre):

    - the opening: a superellipse (exponent rp["n"]; 2 an ellipse) of half height hu * rp["open"] and half width W
      (times rp["wide"]) less the corners' thickness; rp["hole"]: a round hole of radius hole x W in lips W less it
      thick; its lower half rp["drop"] times the upper's;
    - the lips round it: the measured mean thickness times full * plump and upper/lower (the lower lip the bigger
      cushion), blended round the ring, tapering toward the corners to rp["corner"] of it (exponent rp["pw"] in the
      opening's |x| share), the upper lip's top with the bow (rp["bow"], else p's) laid off the opening's edge along
      its normal, so the roll is one even ring with round ends (an outward offset of a convex curve never folds).

    Returns ((cx, cy), [(inner, outer)] per angle, outer edges without the bow (the depth's thickness), the corner
    weights (0 at the centre, 1 at the corners)), n angles, th = 2 pi k / n, sin > 0 the lower lip (px y down)."""
    cx, cy, W = meas["cx"], meas["cy"], meas["W"] * rp.get("wide", 1.0)
    tm = 0.5 * (meas["t_u"] + meas["t_l"]) * rp.get("thick", 1.0)
    full = p["full"] * p.get("plump", 1.0)
    corner, pw, ex = rp.get("corner", 0.6), rp.get("pw", 2.5), 2.0 / rp.get("n", 2.0)
    if rp.get("hole"):  # a round hole of radius hole x W, the lips all round W - the radius thick
        ow = oh = rp["hole"] * W
        tm = (W - ow) / corner * rp.get("thick", 1.0)
    else:
        ow = max(0.15 * W, W - corner * tm)
        oh = meas["hu"] * rp.get("open", 1.0)
    drop = rp.get("drop", 1.0)
    tu, tl = tm * full * p["upper"], tm * full * p["lower"]
    bp = dict(p, bow=rp.get("bow", p["bow"]))
    inner = []
    for k in range(n):
        th = 2 * math.pi * k / n
        c, s = math.cos(th), math.sin(th)
        x = cx + ow * math.copysign(abs(c) ** ex, c)
        y = cy + oh * (drop if s > 0 else 1.0) * math.copysign(abs(s) ** ex, s)
        inner.append((x, y))
    pairs, outer0, cw = [], [], []
    for k in range(n):
        (xa, ya), (xb, yb), (x, y) = inner[k - 1], inner[(k + 1) % n], inner[k]
        tx, ty = xb - xa, yb - ya
        nx, ny = ty, -tx
        if nx * (x - cx) + ny * (y - cy) < 0:
            nx, ny = -nx, -ny
        ln = math.hypot(nx, ny) or 1.0
        nx, ny = nx / ln, ny / ln
        s = math.sin(2 * math.pi * k / n)
        u = min(1.0, abs(x - cx) / max(1e-6, ow))
        low = _smooth01(0.5 + 0.5 * s / 0.6)
        w = u ** pw
        t0 = (tu + (tl - tu) * low) * (corner + (1.0 - corner) * (1.0 - w))
        up = max(0.0, -s)
        t = t0 * (1.0 + bow((x - cx) / W, bp) * up * up)  # the bow over the lips' width, as ring_width
        pairs.append(((x, y), (x + nx * t, y + ny * t)))
        outer0.append((x + nx * t0, y + ny * t0))
        cw.append(w)
    return (cx, cy), pairs, outer0, cw
