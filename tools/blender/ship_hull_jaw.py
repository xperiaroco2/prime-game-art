"""The ship's jaw nose, blockout b1 (art #263, docs/ship.md "The jaw nose"): the hull's own surface runs on into a flat,
pointed prow that splits along a horizontal seam. The upper jaw is the roof over the entrance and lifts a little; the
lower jaw hinges down to the ground and is the ramp, its top face the walking deck. A fixed root fairs the jaws into
the hull's nose between its lead edge and the lower jaw's hinge line. Plain Python (no bpy).

Every solid is a convex polyhedron cut from two outer hulls by planes: the upper hull O_U (the seam outline at
seam_h and the top plate) and the lower hull O_L (the seam outline and the belly). The cuts keep the mouth clear: the
passage |x| <= 1.65 (the throat's mouth) forward of the funnel, the throat's notch planes (ship_hull_shape.cutters,
1 cm out) aft, the deck plane over the lower jaw and the roof's underside over the passage.

The pieces are built in the closed pose at the real heights (grounded) and each one's origin is its hinge: jaw_lower
at [jaw] lower_hinge, jaw_upper at upper_hinge; ship.gd turns them about Godot's x axis by the pose's angles ([jaw]
lower_deg, upper_deg). jaw_root does not move."""

from __future__ import annotations

import itertools
import math

import ship_hull_shape as S
import ship_lib as L

EPS = 1e-6
MOUTH_X = 1.65     # the passage's half width (the throat's mouth, the ramp's 3.3 m)


def jaw(layout: dict) -> dict:
    """The [jaw] numbers with the derived ones: the deck's slope, the tip, the hinges."""
    j = dict(layout["jaw"])
    floor_h = layout["deck"]["floor_h"]
    hy = j["lower_hinge"][1]
    j["deck_slope"] = (j["seam_h"] - floor_h) / (hy - j["tip_y"])          # rise per metre forward, closed
    j["ceil_slope"] = (j["roof_h"] - j["seam_h"]) / (hy - j["tip_y"])      # the roof's underside falls forward
    j["floor_h"] = floor_h
    j["slab_m"] = layout["deck"]["slab_m"]
    return j


def _plane_pts(planes):
    """The corners of a bounded convex region {n . p <= d}: every triple of planes' meeting point inside all."""
    out = []
    for (n1, d1), (n2, d2), (n3, d3) in itertools.combinations(planes, 3):
        det = (n1[0] * (n2[1] * n3[2] - n2[2] * n3[1]) - n1[1] * (n2[0] * n3[2] - n2[2] * n3[0])
               + n1[2] * (n2[0] * n3[1] - n2[1] * n3[0]))
        if abs(det) < 1e-9:
            continue
        c23, c31, c12 = S._cross(n2, n3), S._cross(n3, n1), S._cross(n1, n2)
        p = tuple((d1 * c23[k] + d2 * c31[k] + d3 * c12[k]) / det for k in range(3))
        if all(S._dot(n, p) <= d + 1e-7 for n, d in planes):
            out.append(p)
    return out


def solid(hull_pts, cuts):
    """The convex hull of the points cut by the half-spaces [(n, d)] (n . p <= d kept): (verts, faces) or None."""
    planes = [(n, d) for n, d, _poly in S.convex_hull(hull_pts)] + list(cuts)
    pts = _plane_pts(planes)
    if len(pts) < 4:
        return None
    try:
        fac = S.convex_hull(pts)
    except (ValueError, ZeroDivisionError, IndexError):
        return None
    verts, faces = [], []
    for _n, _d, poly in fac:
        if len(poly) < 3 or S.area(poly) < 1e-6:
            continue
        base = len(verts)
        verts += list(poly)
        faces.append(tuple(range(base, base + len(poly))))
    return (verts, faces) if faces else None


def _hp(n, d):
    """A half-space n . p <= d with n made unit."""
    m = math.sqrt(S._dot(n, n))
    return (tuple(c / m for c in n), d / m)


def outer_points(j: dict):
    """The two outer hulls' points (closed pose): O_U (seam outline + top plate) and O_L (seam outline + belly)."""
    hs, tw, ty = j["seam_h"], j["tip_half_w"], j["tip_y"]
    seam = [(s * tw, ty, hs) for s in (-1, 1)] + [(s * x, y, hs) for x, y in j["outline"] for s in (-1, 1)]
    top = [(s * x, y, h) for x, y, h in j["top"] for s in (-1, 1)]
    belly = [(s * x, y, h) for x, y, h in j["belly"] for s in (-1, 1)]
    return seam + top, seam + belly


def cuts(j: dict) -> dict:
    """The planes that split the outer hulls into the jaws' convex solids (n . p <= d kept)."""
    hy = j["lower_hinge"][1]
    fh, ds, cs, rh = j["floor_h"], j["deck_slope"], j["ceil_slope"], j["roof_h"]
    planes = S.cutters()["notch"][:2]                                     # the throat's notch sides (outward normals)
    ne, de = planes[0]
    nw, dw = planes[1]
    # where the east notch plane crosses x = MOUTH_X: forward of it the passage is |x| <= MOUTH_X
    yc = (de + 0.01 - ne[0] * MOUTH_X) / ne[1]
    deck, deck_d = (0.0, ds, 1.0), fh + ds * hy                         # the deck: h <= fh + ds * (hy - y)
    ceil_n, ceil_d = (0.0, cs, -1.0), -rh + cs * hy                       # the roof's underside: h >= rh + cs * (y - hy)
    return {
        "fore": _hp((0, 1, 0), hy), "aft": _hp((0, -1, 0), -hy),
        "fore_c": _hp((0, 1, 0), yc), "aft_c": _hp((0, -1, 0), -yc),
        "east": _hp((-1, 0, 0), -MOUTH_X), "west": _hp((1, 0, 0), -MOUTH_X),
        "mid": [_hp((1, 0, 0), MOUTH_X), _hp((-1, 0, 0), MOUTH_X)],
        "out_e": _hp(tuple(-c for c in ne), -(de + 0.01)), "out_w": _hp(tuple(-c for c in nw), -(dw + 0.01)),
        "in_n": [_hp(ne, de + 0.01), _hp(nw, dw + 0.01)],
        "below_deck": _hp(deck, deck_d), "above_deck": _hp(tuple(-c for c in deck), -deck_d),
        "above_ceil": _hp(ceil_n, ceil_d), "above_roof": _hp((0, 0, -1), -rh),
        "under_floor": _hp((0, 0, 1), fh - j["slab_m"] - 0.01),
    }


def _solids(j: dict) -> dict:
    """{piece: [(name, (verts, faces), material)]} in the closed pose, plan frame, real heights."""
    ou, ol = outer_points(j)
    c = cuts(j)
    up, lo, root = [], [], []
    for side, inner, out in (("e", c["east"], c["out_e"]), ("w", c["west"], c["out_w"])):
        up.append((f"upper_cheek_{side}", solid(ou, [inner, out]), "hull_silver"))
        lo.append((f"lower_cheek_{side}", solid(ol, [c["fore"], c["above_deck"], inner]), "hull_silver"))
        root.append((f"root_{side}", solid(ol, [c["aft"], inner, out]), "hull_silver"))
    up.append(("upper_roof_fore", solid(ou, [c["fore"], *c["mid"], c["above_ceil"]]), "hull_silver"))
    up.append(("upper_roof_mid", solid(ou, [c["aft"], c["fore_c"], *c["mid"], c["above_roof"]]), "hull_silver"))
    up.append(("upper_roof_aft", solid(ou, [c["aft_c"], *c["in_n"], c["above_roof"]]), "hull_silver"))
    lo.append(("lower_body", solid(ol, [c["fore"], c["below_deck"]]), "hull_silver"))
    root.append(("root_under", solid(ol, [c["aft"], c["fore_c"], *c["mid"], c["under_floor"]]), "hull_dark"))
    return {"upper": [s for s in up if s[1]], "lower": [s for s in lo if s[1]], "root": [s for s in root if s[1]]}


def _shift(vf, o):
    v, f = vf
    return [(p[0] - o[0], p[1] - o[1], p[2] - o[2]) for p in v], f


def _strip(a, b, h0, h1, out_w, normal):
    """A thin glowing bar along a -> b (plan), from h0 to h1, out_w proud of the face along the plan normal."""
    nx, ny = normal
    pts = []
    for (x, y) in (a, b):
        for o in (0.0, out_w):
            for h in (h0, h1):
                pts.append((x + nx * o, y + ny * o, h))
    v = [pts[0], pts[4], pts[6], pts[2], pts[1], pts[5], pts[7], pts[3]]
    return v, [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]


def seam_outline(j: dict):
    """The seam's plan outline, east side from the tip aft (the points the convex hull keeps)."""
    ou, _ol = outer_points(j)
    hs = j["seam_h"]
    pts = sorted({(round(p[0], 6), round(p[1], 6)) for n, d, poly in S.convex_hull(ou) for p in poly
                  if abs(p[2] - hs) < 1e-6 and p[0] >= -EPS})
    return sorted(pts, key=lambda p: p[1])


def outline_x(j: dict, y: float) -> float:
    """The seam outline's half width at plan y."""
    pts = seam_outline(j)
    if y <= pts[0][1]:
        return pts[0][0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0) if y1 > y0 else max(x0, x1)
    return pts[-1][0]


def jaw_upper(args: dict, layout: dict) -> list:
    """The upper jaw: two cheeks over the seam and the roof over the passage, the cyan seam line along its lower
    edge; origin at [jaw] upper_hinge."""
    j = jaw(layout)
    o = j["upper_hinge"]
    parts = [L.part(nm, *_shift(vf, o), mat) for nm, vf, mat in _solids(j)["upper"]]
    hs, tw, ty = j["seam_h"], j["tip_half_w"], j["tip_y"]
    ye = j.get("seam_end_y", -6.2)                                  # where the seam runs into the hull's lead edge
    xe = outline_x(j, ye)
    chain = [(-xe, ye), (-tw, ty), (tw, ty), (xe, ye)]
    bars = []
    for a, b in zip(chain, chain[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        m = math.hypot(dx, dy)
        nrm = (dy / m, -dx / m)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 8.0)              # from a point inside the prow
        if nrm[0] * mid[0] + nrm[1] * mid[1] < 0:
            nrm = (-nrm[0], -nrm[1])
        bars.append(_strip(a, b, hs - 0.015, hs + 0.015, 0.015, nrm))
    parts.append(L.part("seam_glow", *_shift(L.merge(*bars), o), "glow_cyan"))
    return parts


def deck_frame(j: dict):
    """The deck's frame (closed): origin the hinge on the floor, u forward along the deck, w its normal up."""
    hy, fh, ds = j["lower_hinge"][1], j["floor_h"], j["deck_slope"]
    k = 1.0 / math.hypot(1.0, ds)
    u = (0.0, -k, ds * k)
    w = (0.0, ds * k, k)
    return (0.0, hy, fh), u, w


def jaw_lower(args: dict, layout: dict) -> list:
    """The lower jaw, the ramp: its body under the deck, two cheeks beside it up to the seam, ribs across the deck and
    two warm lit edges; origin at [jaw] lower_hinge."""
    j = jaw(layout)
    o = j["lower_hinge"]
    parts = [L.part(nm, *_shift(vf, o), mat) for nm, vf, mat in _solids(j)["lower"]]
    p0, u, w = deck_frame(j)
    length = math.hypot(j["lower_hinge"][1] - j["tip_y"], j["seam_h"] - j["floor_h"])

    def at(s, x, h):
        return tuple(p0[k] + u[k] * s + w[k] * h + (x if k == 0 else 0.0) for k in range(3))

    def half(s):
        y = p0[1] + u[1] * s
        return min(MOUTH_X, outline_x(j, y) - 0.06)

    ribs, edges = [], []
    s = 0.35
    while s < length - 0.3:
        hw = half(s) - 0.12
        if hw > 0.2:
            corners = [at(s + ds_, sx * hw, hh) for hh in (0.0, 0.014) for ds_ in (0.0, 0.07) for sx in (-1, 1)]
            ribs.append((corners, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]))
        s += 0.42
    step = length / 12
    for side in (-1, 1):
        for i in range(12):
            s0, s1 = i * step + 0.02, (i + 1) * step - 0.02
            if s1 > length - 0.15:
                break
            a0, a1 = side * (half(s0) - 0.05), side * (half(s1) - 0.05)
            v = [at(s0, a0, 0.0), at(s0, a0 + side * 0.04, 0.0), at(s1, a1 + side * 0.04, 0.0), at(s1, a1, 0.0)]
            v += [(p[0], p[1], p[2]) for p in [at(s0, a0, 0.012), at(s0, a0 + side * 0.04, 0.012),
                                               at(s1, a1 + side * 0.04, 0.012), at(s1, a1, 0.012)]]
            edges.append((v, [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]))
    rib = L.part("deck_ribs", *_shift(L.merge(*ribs), o), "leg_metal")
    rib["nocol"] = True
    lit = L.part("deck_edges", *_shift(L.merge(*edges), o), "glow_amber")
    lit["nocol"] = True
    return parts + [rib, lit]


def jaw_root(args: dict, layout: dict) -> list:
    """The fixed root: the lower hull between the throat's notch and the lower jaw's hinge line, and under the
    passage's floor; plan origin."""
    j = jaw(layout)
    return [L.part(nm, *vf, mat) for nm, vf, mat in _solids(j)["root"]]

