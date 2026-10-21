"""M11, the lashes eyes el2 (art #196, brief UPDATE 21): the upper lashes' plain geometry, no Blender. A lash set
rides an upper lid shell (alien_parts_geom.lid_shell): every point is built in the lid's own frame (the hinge on local
X, the edge on local -Y at elevation 0, the lid covering +p toward +Z), so the set turns with the lid in a blink, a
half lid or surprise, and scales with the eye unit (every length is a share of the eyeball's radius r).

- Each lash roots on the lid's rolled rim (alien_lids_geom.shell_profile's half circle: rim angle `root_a_deg` from the
  outer surface toward the front edge), sunk `sink` into it, and leaves `lift_deg` above the radial; it bends up over
  its length by `curl_deg` (more toward the tip, `curl_pow`) and splays toward its own side (`fan_deg` times its
  place from the middle), M11b all of them leaning toward the temple by `fan_bias_deg` (0.3 to 1 of it, inner to
  outer: el2's lashes sweep out, so they read as strokes from the front and less as a comb in profile); a tapered, slightly flat tube (`width`, `tip`, `flat`) with a round tip.
- The lashes run from `t_in_deg` (the nose side) to `t_out_deg` (the temple side) of latitude, closer together toward
  the outer corner (`crowd`), longer and thicker there (`len_*`, `width_*`); the last `wing` lashes are longer still and
  sweep out past the corner (`wing_sweep_deg`, `wing_len`): el2's winged look. None on the lower lid.
- `design_lift_deg` ({design: lift}): a design's own lift (alien_lashes.py): the manic lids rest 50 degrees up, so
  its lashes leave lower on the lid to stand off the dome as the bored ones do at their rest. M11b: `design`
  ({design: {key: value}}) any other keys of a design's own, over the rest (alien_lashes.py, `for_design`).
- The liner (`liner_deg` of the rim's roll, `liner` thick, 0 for none): a thin band hugging the roll along the roots,
  so the lash line reads as one dark line at the game's distance; it starts at `liner_t_in_deg` (or the first lash)
  and ends just past the last.

`side` is +1 when the lid's local +X points to the temple (the left eye; alien_lashes.py takes it from the world):
the set is built for +1 and mirrored for -1.
"""
from __future__ import annotations

import math

# The pick (M11's grids g1 to g5, beside el2): seven bold lashes on the outer half, the last two winging out, a liner
# along the whole edge. M11b (grids g6 to g8, brief UPDATE 23: el2's lashes are bold curls, ours were thin wires, the
# liner too faint, and in profile they stood over the dome like a comb): fatter (0.12 to 0.19 r at the root, a flatter
# section), curled round evenly (160 degrees, curl_pow 1) from a lower lift (10), all leaning toward the temple (45),
# and a bold liner (0.06 r, 1.8 times that at the outer end, over 130 degrees of the roll). The manic lids rest 50
# degrees up: its lashes leave 30 degrees below the radial and lean 25 (they stand out of the dome's outline as in
# el2's wide panel), and end at 66 degrees (at 74 the last lash's root touched the skin with the lid open).
LASHES = {"count": 7, "t_in_deg": 0.0, "t_out_deg": 74.0, "crowd": 1.5,
          "len_in": 0.35, "len_out": 0.80, "len_pow": 1.6, "width_in": 0.12, "width_out": 0.19, "tip": 0.3,
          "flat": 0.6, "lift_deg": 10.0, "curl_deg": 160.0, "curl_pow": 1.0, "fan_deg": 20.0, "fan_bias_deg": 45.0,
          "wing": 2, "wing_len": 1.4, "wing_sweep_deg": 45.0, "wing_lift_deg": -6.0,
          "root_a_deg": 30.0, "sink": 0.008, "seg": 10, "sides": 6,
          "liner": 0.06, "liner_deg": 130.0, "liner_a_deg": 60.0, "liner_t_in_deg": -60.0, "liner_rows": 48,
          "liner_k": 6, "liner_embed": 0.004, "liner_out": 1.8, "design_lift_deg": {"manic": 0.0},
          "design": {"manic": {"lift_deg": -30.0, "fan_bias_deg": 25.0, "t_out_deg": 66.0}}}


def merged(spec: dict | None = None) -> dict:
    """LASHES with spec's keys over it; an unknown key is refused (a typo would build the default silently)."""
    spec = spec or {}
    bad = sorted(set(spec) - set(LASHES))
    if bad:
        raise ValueError(f"unknown lash keys: {bad}")
    return dict(LASHES, **spec)


def for_design(c: dict, design: str) -> dict:
    """The spec a design builds with: its `design_lift_deg` as `lift_deg`, then its `design` keys."""
    out = dict(c)
    if design in c["design_lift_deg"]:
        out["lift_deg"] = c["design_lift_deg"][design]
    over = c["design"].get(design, {})
    bad = sorted(set(over) - set(LASHES))
    if bad:
        raise ValueError(f"unknown lash keys for {design}: {bad}")
    out.update(over)
    return out


def _norm(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _add(a, b, k=1.0):
    return tuple(x + k * y for x, y in zip(a, b))


def frame(t: float, p: float):
    """The lid frame's unit vectors at latitude t and elevation p: radial e_r, up the lid e_p (+p), along the latitude
    e_t (+t, toward local +X)."""
    ct, st, cp, sp = math.cos(t), math.sin(t), math.cos(p), math.sin(p)
    return (st, -ct * cp, ct * sp), (0.0, sp, cp), (ct, st * cp, -st * sp)


def rim(t: float, a: float, rho_in: float, rho_out: float, bead: float, corner: dict | None,
        t_max_deg: float = 89.0):
    """(point, outward normal) on the upper lid's rolled rim at latitude t and rim angle a (0: where the outer surface
    meets the roll, pi/2: the front edge), in r, with lid_shell's corner taper and edge droop (alien_lids_geom)."""
    import alien_lids_geom as LG
    tm = math.radians(t_max_deg)
    bt = LG.bead_at(bead, t, tm, corner) if corner else bead
    sh = LG.edge_shift(t, tm, True, corner) if corner else 0.0
    re = rho_out + bt
    rm, hw = (re + rho_in) / 2.0, (re - rho_in) / 2.0
    rho = rm + hw * math.cos(a)
    p = -(hw * math.sin(a)) / rm + sh  # the shift is full at the edge (shell_profile: it fades only far behind)
    e_r, e_p, _ = frame(t, p)
    pt = tuple(rho * c for c in e_r)
    n = _norm(_add(tuple(math.cos(a) * c for c in e_r), e_p, -math.sin(a)))
    return pt, n, p, hw


def lash_params(c: dict) -> list[dict]:
    """Per lash (inner to outer) its latitude (radians, + toward the temple), length, root width, splay and wing."""
    n = int(c["count"])
    out = []
    for i in range(n):
        u = i / (n - 1) if n > 1 else 1.0
        f = 1.0 - (1.0 - u) ** c["crowd"]  # closer together toward the outer corner
        t = math.radians(c["t_in_deg"] + (c["t_out_deg"] - c["t_in_deg"]) * f)
        g = u ** c["len_pow"]
        wing = max(0.0, (i - (n - 1 - c["wing"])) / c["wing"]) if c["wing"] > 0 else 0.0  # 0 .. 1 over the wing
        out.append({"t": t, "u": u, "wing": wing,
                    "len": (c["len_in"] + (c["len_out"] - c["len_in"]) * g) * (1.0 + (c["wing_len"] - 1.0) * wing),
                    "width": c["width_in"] + (c["width_out"] - c["width_in"]) * g,
                    "fan": (math.radians(c["fan_deg"]) * (2.0 * u - 1.0) + math.radians(c["wing_sweep_deg"]) * wing
                            + math.radians(c["fan_bias_deg"]) * (0.3 + 0.7 * u)),
                    "lift": math.radians(c["lift_deg"] + c["wing_lift_deg"] * wing)})
    return out


def lash_curve(lp: dict, c: dict, rho_in: float, rho_out: float, bead: float, corner: dict | None):
    """A lash's centre line in r (the temple toward +X): [(point, direction, half width)] from its sunk root to its
    tip."""
    pt, n, p, _ = rim(lp["t"], math.radians(c["root_a_deg"]), rho_in, rho_out, bead, corner)
    e_r, e_p, e_t = frame(lp["t"], p)
    pos = _add(pt, n, -c["sink"])
    seg = int(c["seg"])
    ds = (lp["len"] + c["sink"]) / seg
    pts = []
    for j in range(seg + 1):
        u = j / seg
        th = lp["lift"] + math.radians(c["curl_deg"]) * u ** c["curl_pow"]
        ph = lp["fan"] * min(1.0, 0.4 + u)
        v = _norm(_add(_add(tuple(math.cos(th) * math.cos(ph) * x for x in e_r),
                            tuple(math.sin(th) * math.cos(ph) * x for x in e_p)), e_t, math.sin(ph)))
        w = 0.5 * lp["width"] * (1.0 - (1.0 - c["tip"]) * u)
        pts.append((pos, v, w))
        pos = _add(pos, v, ds)
    return pts


def tube(curve, c: dict, side_axis) -> tuple[list, list]:
    """A tapered tube along curve ([(point, direction, half width)]) with a round tip: (verts, quads and triangles);
    the section an ellipse, `half width` along side_axis (made normal to the line), `flat` times it across."""
    sides = int(c["sides"])
    verts, faces = [], []
    for (p, v, w) in curve:
        s = _norm(_add(side_axis, v, -_dot(side_axis, v)))
        b = _cross(v, s)
        for k in range(sides):
            a = 2.0 * math.pi * k / sides
            verts.append(_add(_add(p, s, w * math.cos(a)), b, c["flat"] * w * math.sin(a)))
    m = len(curve)
    for j in range(m - 1):
        for k in range(sides):
            a0, a1 = j * sides + k, j * sides + (k + 1) % sides
            faces.append((a0, a1, a1 + sides, a0 + sides))
    p, v, w = curve[-1]
    tip = len(verts)
    verts.append(_add(p, v, 1.2 * w))  # the round tip
    for k in range(sides):
        faces.append(((m - 1) * sides + k, (m - 1) * sides + (k + 1) % sides, tip))
    root = len(verts)
    verts.append(curve[0][0])  # the root's cap (inside the rim)
    for k in range(sides):
        faces.append(((k + 1) % sides, k, root))
    return verts, faces


def _smooth(x: float) -> float:
    """A smoothstep from 0 to 1 over x in [0, 1]."""
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def split(verts: list, faces: list, u: list) -> dict:
    """M11b: a set's mesh (build's verts, faces and rep["u"]) cut into its parts, each (verts, faces) with its own
    indices: "lashes" (u >= 0, the tubes) and "liner" (u < 0). The liner is its own node, so the game can fade the
    tubes out past a few metres and keep the lash line (brief UPDATE 23)."""
    out = {}
    for part, keep in (("lashes", lambda x: x >= 0.0), ("liner", lambda x: x < 0.0)):
        idx = {i: n for n, i in enumerate(i for i, x in enumerate(u) if keep(x))}
        fs = [tuple(idx[i] for i in fc) for fc in faces if all(i in idx for i in fc)]
        if any(any(i in idx for i in fc) and not all(i in idx for i in fc) for fc in faces):
            raise ValueError(f"a face spans the lashes and the liner ({part})")
        out[part] = ([verts[i] for i in idx], fs)
    return out


def liner(c: dict, rho_in: float, rho_out: float, bead: float, corner: dict | None, t0: float, t1: float):
    """The liner band (verts, faces) in r: per latitude row from t0 to t1, a lens over `liner_deg` of the roll about
    `liner_a_deg`, `liner` thick in its middle, tapering to nothing at both ends of the row, its underside
    `liner_embed` inside the roll; `liner_out` times thicker at t1 than at t0 (M11b: el2's line swells toward the outer
    corner). None when `liner` is 0."""
    if c["liner"] <= 0.0:
        return None
    rows, k = int(c["liner_rows"]), int(c["liner_k"])
    a0, a1 = (math.radians(c["liner_a_deg"] - c["liner_deg"] / 2.0), math.radians(c["liner_a_deg"] + c["liner_deg"] / 2.0))
    verts, faces = [], []
    for i in range(rows + 1):
        f = i / rows
        t = t0 + (t1 - t0) * f
        taper = math.sin(math.pi * min(1.0, f / 0.12) / 2.0) * math.sin(math.pi * min(1.0, (1.0 - f) / 0.25) / 2.0)
        taper *= 1.0 + (c["liner_out"] - 1.0) * _smooth(f)
        for j in range(k + 1):  # the top (out), then back along the underside (in)
            a = a0 + (a1 - a0) * j / k
            pt, n, _, _ = rim(t, a, rho_in, rho_out, bead, corner)
            bump = math.sin(math.pi * j / k)
            verts.append(_add(pt, n, c["liner"] * taper * bump - c["liner_embed"] * (1.0 - bump)))
        for j in range(k - 1, 0, -1):
            a = a0 + (a1 - a0) * j / k
            pt, n, _, _ = rim(t, a, rho_in, rho_out, bead, corner)
            verts.append(_add(pt, n, -c["liner_embed"]))
    m = 2 * k
    for i in range(rows):
        for j in range(m):
            a, b = i * m + j, i * m + (j + 1) % m
            faces.append((a, b, b + m, a + m))
    for row, flip in ((0, True), (rows, False)):  # end caps
        ring = [row * m + j for j in range(m)]
        faces.append(tuple(reversed(ring)) if flip else tuple(ring))
    return verts, faces


def build(c: dict, rho_in: float, rho_out: float, bead: float, corner: dict | None, side: float):
    """The whole set in r: (verts, faces, report with "u" per vertex) — the lashes' tubes and the liner, one mesh; built
    with the temple
    toward +X, then mirrored (x negated, the faces' winding reversed) when side is -1."""
    verts, faces, u_of = [], [], []
    rep = {"lashes": []}
    lps = lash_params(c)
    for lp in lps:
        cur = lash_curve(lp, c, rho_in, rho_out, bead, corner)
        v, f = tube(cur, c, frame(lp["t"], 0.0)[2])
        base = len(verts)
        verts += v
        faces += [tuple(base + i for i in fc) for fc in f]
        sides = int(c["sides"])
        u_of += [j / (len(cur) - 1) for j in range(len(cur)) for _ in range(sides)] + [1.0, 0.0]  # rings, tip, root
        rep["lashes"].append({"t_deg": round(math.degrees(lp["t"]), 1), "len_r": round(lp["len"], 4),
                              "width_r": round(lp["width"], 4), "wing": round(lp["wing"], 2),
                              "tip": [round(x, 4) for x in cur[-1][0]]})
    ln = liner(c, rho_in, rho_out, bead, corner, min(lps[0]["t"] - math.radians(4.0), math.radians(c["liner_t_in_deg"])),
               lps[-1]["t"] + math.radians(2.0))
    if ln is not None:
        base = len(verts)
        verts += ln[0]
        faces += [tuple(base + i for i in fc) for fc in ln[1]]
        u_of += [-1.0] * len(ln[0])  # the liner
        rep["liner_verts"] = len(ln[0])
    if side < 0.0:
        verts = [(-x, y, z) for x, y, z in verts]
        faces = [tuple(reversed(fc)) for fc in faces]
    rep["verts"] = len(verts)
    rep["u"] = u_of  # per vertex: its place along its lash (0 root, 1 tip), -1 on the liner
    return verts, faces, rep
