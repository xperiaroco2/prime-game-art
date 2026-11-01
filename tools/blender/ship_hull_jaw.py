"""The ship's jaw nose, b2 (art #263, docs/ship.md "The jaw nose"): the hull runs on into a flat, pointed prow that
opens as a mouth. Every moving part is a thin plated shell (SHELL thick, the hull's plates on its outside) that follows
the prow's outer surface; nothing is a solid wedge. Plain Python (no bpy).

The prow is two convex outer hulls: O_U (the seam outline at seam_h and the top points, which lie just under the
hull's top at the upper hinge's line, so the top grows out of the hull) and O_L (the seam outline and the belly
points, the belly continuing the hull's flat bottom). Three pieces:

- jaw_lower, the ramp: the shell of O_L forward of the hinge line and under the rail plane (the deck's plane raised
  RAIL): the belly, the low side rails, a deck plate in the deck's plane, a bulkhead under the deck at the hinge. Its
  aft face below the hinge leans forward V_DEG, so turning down to the ground it never swings into the root.
- jaw_upper, the roof: the shell of O_U (top and sides) and the skirts (O_L over the rail plane, forward of the hinge
  line), so closed the parting line runs from the tip along the seam and down the rails' tops: the mouth line, a cyan
  strip. Under it a ceiling plate (the roof's underside, its lit edges) and a bulkhead over the seam at the mouth.
- jaw_root, fixed: the shell of O_L aft of the hinge line, the front bulkhead round the throat's opening (the portal,
  a chrome lip), and the hood and lid that close the entry tunnel's outside inside the prow.

Built closed at the real heights (grounded); each piece's origin is its hinge: jaw_lower at [jaw] lower_hinge,
jaw_upper at upper_hinge; ship.gd turns them about Godot's x axis by the pose's angles. jaw_root does not move."""

from __future__ import annotations

import itertools
import math
import zlib

import ship_hull as H
import ship_hull_j as HJ
import ship_hull_shape as S
import ship_lib as L

EPS = 1e-6
MOUTH_X = 1.65      # the passage's half width (the throat's mouth, the ramp's 3.3 m)
SHELL = 0.04        # the shells' thickness
RAIL = 0.30         # the ramp's side rails over the deck (the parting line on the sides: the deck's plane + RAIL)
V_DEG = 36.0        # the lower jaw's aft face under the hinge leans forward this much (its swing is 34.4 deg)
PLATE_T = 0.05      # the deck plate and the ceiling plate
BULK = 0.05         # the root's front bulkhead (y hinge .. hinge + BULK)
UPPER_BULK = (0.11, 0.07)   # the upper jaw's bulkhead over the seam, this far forward of the hinge line
CLEAR = 0.25        # the root's bulkhead over the seam stays this far inside the upper shell (its lift)
LIP = (0.10, 0.03)  # the portal's chrome lip: width round the opening, proud of the bulkhead
STRIP = (0.025, 0.006)      # the cyan mouth line: width on the upper face, proud
PLATED = True       # False: the outer faces flat (the seal and clash checks; the plates sink inside the skin)


# polish n2 (art #263): the mouth ceiling's two bars, half glow_cyan's strength; their cell light dimmed in ship.toml
# (the throat's ceiling clipped white over them, in_throat)
L.MATERIALS.setdefault("ext_hazard", {"base": (0.92, 0.66, 0.06, 1.0), "metallic": 0.05, "roughness": 0.55})
L.MATERIALS.setdefault("ext_hazard_dark", {"base": (0.035, 0.035, 0.04, 1.0), "metallic": 0.3, "roughness": 0.6})
L.MATERIALS["glow_cyan__jaw_ceil"] = {**L.MATERIALS["glow_cyan"], "strength": 3.0}

def jaw(layout: dict) -> dict:
    """The [jaw] numbers with the derived ones: the deck's slope, the roof's underside, the floor and the throat."""
    j = dict(layout["jaw"])
    floor_h = layout["deck"]["floor_h"]
    hy = j["lower_hinge"][1]
    j["deck_slope"] = (j["seam_h"] - floor_h) / (hy - j["tip_y"])          # rise per metre forward, closed
    j["ceil_slope"] = (j["roof_h"] - j["seam_h"]) / (hy - j["tip_y"])      # the roof's underside falls forward
    j["floor_h"] = floor_h
    j["slab_m"] = layout["deck"]["slab_m"]
    th = next(r for r in layout["rooms"] if r["id"] == "throat")
    bend, cin = th.get("tunnel_chamfer", th["chamfer"])
    j["portal"] = (MOUTH_X, floor_h + bend, MOUTH_X - cin, floor_h + th["clear_h"])   # wall x, bend h, top x, top h
    return j


def _plane_pts(planes):
    """The corners of a bounded convex region {n . p <= d}: every triple of planes' meeting point inside all."""
    out = {}
    for (n1, d1), (n2, d2), (n3, d3) in itertools.combinations(planes, 3):
        det = (n1[0] * (n2[1] * n3[2] - n2[2] * n3[1]) - n1[1] * (n2[0] * n3[2] - n2[2] * n3[0])
               + n1[2] * (n2[0] * n3[1] - n2[1] * n3[0]))
        if abs(det) < 1e-9:
            continue
        c23, c31, c12 = S._cross(n2, n3), S._cross(n3, n1), S._cross(n1, n2)
        p = tuple((d1 * c23[k] + d2 * c31[k] + d3 * c12[k]) / det for k in range(3))
        if all(S._dot(n, p) <= d + 1e-7 for n, d in planes):
            out[tuple(round(c, 7) for c in p)] = p
    return list(out.values())


def _hp(n, d):
    """A half-space n . p <= d with n made unit."""
    m = math.sqrt(S._dot(n, n))
    return (tuple(c / m for c in n), d / m)


def _flip(pl):
    return (tuple(-c for c in pl[0]), -pl[1])


def _order(pts, n):
    """Points of one plane wound counter-clockwise about n (their Newell normal along n)."""
    c = tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))
    e1, e2 = HJ._basis(n)
    return sorted(pts, key=lambda p: math.atan2(S._dot(S._sub(p, c), e2), S._dot(S._sub(p, c), e1)))


def faces(planes) -> dict:
    """{plane index: its face polygon (wound along the plane's outward normal)} of the convex region."""
    pts = _plane_pts(planes)
    out = {}
    if len(pts) < 4:
        return out
    for k, (n, d) in enumerate(planes):
        on = [p for p in pts if abs(S._dot(n, p) - d) < 1e-6]
        if len(on) >= 3:
            poly = _order(on, n)
            if S.area(poly) > 1e-6:
                out[k] = poly
    return out


def _edge_planes(g, n):
    """A convex polygon's edges as in-plane half-spaces (inside n_e . p <= d), for S._subtract."""
    out = []
    for a, b in zip(g, g[1:] + g[:1]):
        ne = S._unit3(S._cross(S._sub(b, a), n))
        out.append((ne, S._dot(ne, a)))
    return out


AFT_Y = -5.6        # nothing of the shells' rims aft of this (the throat's roofed part; inside the hull there)


def shell(planes, skin, t=SHELL, hide=()) -> dict:
    """A convex region's shell t thick behind its skin planes: {"outer": [(poly, n)], "inner": [(poly, n)],
    "rim": {plane index: [(poly, n)]}} - the rims the cut faces' bands between the outer and the inner region, none
    aft of AFT_Y. The `hide` planes (the hulls' aft faces, which would wall off the throat) get no face at all."""
    out = faces(planes)
    if not out:
        return {"outer": [], "inner": [], "rim": {}}
    inner = faces([(n, d - t) if k in skin else (n, d) for k, (n, d) in enumerate(planes)])
    res = {"outer": [], "inner": [], "rim": {}}
    for k, poly in out.items():
        n = planes[k][0]
        if k in hide:
            continue
        if k in skin:
            res["outer"].append((poly, n))
            continue
        g = inner.get(k)
        pieces = S._subtract(poly, _edge_planes(g, n)) if g else [poly]
        pieces = [S.clip(q, (0.0, 1.0, 0.0), AFT_Y) for q in pieces]
        res["rim"][k] = [(q, n) for q in pieces if len(q) >= 3 and S.area(q) > 1e-7]
    for k, poly in inner.items():
        if k in skin:
            res["inner"].append((list(reversed(poly)), S._neg(planes[k][0])))
    return res


def _mesh(polys):
    return L.merge(*[(list(q), [tuple(range(len(q)))]) for q, _n in polys]) if polys else ([], [])


def outer_points(j: dict):
    """The two outer hulls' points (closed pose): O_U (seam outline + top points) and O_L (seam outline + belly)."""
    hs, tw, ty = j["seam_h"], j["tip_half_w"], j["tip_y"]
    seam = [(s * tw, ty, hs) for s in (-1, 1)] + [(s * x, y, hs) for x, y in j["outline"] for s in (-1, 1)]
    top = [(s * x, y, h) for x, y, h in j["top"] for s in (-1, 1)]
    belly = [(s * x, y, h) for x, y, h in j["belly"] for s in (-1, 1)]
    return _uniq(seam + top), _uniq(seam + belly)


def _uniq(pts):
    """The points without repeats (a point on the centre line, x 0, is mirrored onto itself)."""
    out = {}
    for p in pts:
        out.setdefault(tuple(round(c, 7) for c in p), p)
    return list(out.values())


def hulls(j: dict):
    """(O_U planes, its skin indices, O_L planes, its skin indices): every face but the seam and the aft faces is skin
    (aft_faces: those inside the hull, which would cross the throat)."""
    ou, ol = outer_points(j)
    out = []
    for pts, up in ((ou, -1.0), (ol, 1.0)):
        pl = [(n, d) for n, d, _poly in S.convex_hull(pts)]
        skin = {k for k, (n, d) in enumerate(pl) if not (abs(n[2] - up) < 1e-6 and abs(n[2] * j["seam_h"] - d) < 1e-6)}
        out += [pl, skin - aft_faces(pl)]
    return tuple(out)


def aft_faces(pl) -> set:
    """The hull's faces looking aft (n_y > 0.3): inside the hull, they would wall off the throat."""
    return {k for k, (n, _d) in enumerate(pl) if n[1] > 0.3}


def _offset(planes, skin, t):
    return [(n, d - t) if k in skin else (n, d) for k, (n, d) in enumerate(planes)]


def cuts(j: dict) -> dict:
    """The planes that split the outer hulls into the jaws (n . p <= d kept)."""
    hy, fh, ds, cs, rh, hs = j["lower_hinge"][1], j["floor_h"], j["deck_slope"], j["ceil_slope"], j["roof_h"], j["seam_h"]
    tv = math.tan(math.radians(V_DEG))
    deck = ((0.0, ds, 1.0), fh + ds * hy)                         # h + ds y <= fh + ds hy: under the deck
    wx, bh, tx, th = j["portal"]
    cham = (wx - tx, 0.0, th - bh)                                # the portal's chamfer line's outward normal (east)
    cd = cham[0] * wx + cham[2] * bh
    return {
        "fore": _hp((0, 1, 0), hy), "aft": _hp((0, -1, 0), -hy),
        "v": _hp((0, 1, -tv), hy - fh * tv),                     # the lower jaw's aft face under the hinge
        "below_deck": _hp(*deck), "above_deck": _flip(_hp(*deck)),
        "below_plate": _flip(_hp(deck[0], deck[1] - PLATE_T)),    # over the deck plate's bottom
        "below_rail": _hp(deck[0], deck[1] + j.get("rail", RAIL)),
        "above_rail": _flip(_hp(deck[0], deck[1] + j.get("rail", RAIL))),
        "below_ceil": _hp((0, -cs, 1), rh - cs * hy), "above_ceil": _flip(_hp((0, -cs, 1), rh - cs * hy)),
        "above_seam": _hp((0, 0, -1), -hs), "below_seam": _hp((0, 0, 1), hs),
        "cham_out_e": _flip(_hp(cham, cd)), "cham_out_w": _flip(_hp((-cham[0], 0, cham[2]), cd)),
        "cham_in": [_hp(cham, cd), _hp((-cham[0], 0, cham[2]), cd)],
    }


def _pose(p, o, deg):
    """A plan point turned about Godot's x through the hinge o by deg (+ lifts the front)."""
    a = math.radians(deg)
    dy, dh = p[1] - o[1], p[2] - o[2]
    return (p[0], o[1] + dy * math.cos(a) + dh * math.sin(a), o[2] - dy * math.sin(a) + dh * math.cos(a))


def _below(polys, plane, gap=0.003):
    """Faces looking up or down (|n_z| > 0.5) clipped under a plane (the deck's: at the ramp's thin tip the shell's
    inner face and under-skin would stand through the deck)."""
    if plane is None:
        return polys
    out = []
    for q, n in polys:
        if abs(n[2]) > 0.5 and abs(n[0]) < 0.3:   # the front and belly (b3: not the sides, which face down too)
            q = S.clip(q, plane[0], plane[1] - gap)
        if len(q) >= 3 and S.area(q) > 1e-7:
            out.append((q, n))
    return out


def jaw_cells(poly, n) -> list:
    """polish n3: a jaw face's plates on one global seam family for the whole prow, so the closed nose's grids meet
    across its pieces (HJ.plates laid each facet's grid in its own frame: 3-4 grids that did not meet on the closed
    front): faces looking up or down rows of constant y and ends of constant x (the hull's top family); the others
    horizontal bands (planes of constant h) with ends of constant x, or of constant y where the face looks sideways.
    The bands' seams run on round every fold of the prow, and onto the hull's own fore-looking faces."""
    if abs(n[2]) > 0.7:
        r, c = S.Y, S.X
    else:
        r, c = S.H, (S.X if abs(n[0]) < 0.7 else S.Y)
    return [q for _key, q in HJ._rows(poly, r, c)]


def _plated(polys, name, under_clip=None, nocol_down=False):
    """Outer faces as the hull's plates (ship_hull_j: inset, chamfered seams, v1's silvers) and the dark under-skin.
    nocol_down: the faces looking down (n_z < -0.3, built closed) and the whole under-skin stay visual (the ramp's
    underside: open, it lies under the deck, and its slivers at the tip stopped the walk, b3)."""
    if nocol_down:
        down = [(q, n) for q, n in polys if n[2] < -0.3]
        rest = [(q, n) for q, n in polys if n[2] >= -0.3]
        parts = _plated(rest, name, under_clip) + _plated(down, f"{name}_under", under_clip)
        for p in parts:
            if p["name"].startswith(f"{name}_under") or p["name"].endswith("_seam"):
                p["nocol"] = True
        return parts
    if not PLATED:
        return _flat(f"{name}_flat", polys, "hull_silver")
    groups, under = {}, []
    for poly, n in polys:
        for q in jaw_cells(poly, n):
            c = tuple(round(sum(x[k] for x in q) / len(q), 1) for k in range(3))
            mat = HJ.MATS["top"][zlib.crc32(repr(c).encode()) % len(HJ.MATS["top"])]
            groups.setdefault(mat, []).append(HJ.lay(q))
        sunk = _below([([H._add(x, n, -HJ.DEPTH * 1.8) for x in poly], n)], under_clip)
        under += [(q, [tuple(range(len(q)))]) for q, _n in sunk]
    parts = [L.part(f"{name}_{m}", *L.merge(*g), m, solid=False) for m, g in sorted(groups.items())]
    if under:
        parts.append(L.part(f"{name}_seam", *L.merge(*under), "ext_seam", solid=False))
    return parts


def _flat(name, polys, mat, nocol=False):
    if not polys:
        return []
    p = L.part(name, *_mesh(polys), mat, solid=False)
    if nocol:
        p["nocol"] = True
    return [p]


def _solid_polys(planes):
    return [(q, planes[k][0]) for k, q in faces(planes).items()]


def _band(a, b, n, inward, w, lift, lift0=0.001):
    """A thin glowing bar on a face of normal n along a -> b, w wide toward `inward`, from lift0 to lift proud."""
    e = S._unit3(S._cross(n, S._sub(b, a)))
    if S._dot(e, inward) < 0:
        e = S._neg(e)
    base = [a, b, H._add(b, e, w), H._add(a, e, w)]
    lo = [H._add(p, n, lift0) for p in base]
    hi = [H._add(p, n, lift) for p in base]
    v = lo + hi
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    # wind every face outward: the top along +n
    if S._dot(S._newell([v[i] for i in f[1]]), n) < 0:
        f = [tuple(reversed(x)) for x in f]
    return v, f


def _on(p, pl):
    return abs(S._dot(pl[0], p) - pl[1]) < 1e-6


def parting(j: dict) -> list:
    """The mouth line on the outside, closed: [(a, b, face normal, face polygon)] along the lower jaw's top edges
    (the seam at the tip, the rails' tops on the sides), each on the upper part's face over it."""
    ou, sku, ol, skl = hulls(j)
    c = cuts(j)
    reg = ol + [c["fore"], c["v"], c["below_rail"]]
    fs = faces(reg)
    top = [len(ol) + 2] + [k for k in range(len(ol)) if k not in skl]   # the rail plane, the seam
    up_faces = [(ou[k], q) for k, q in faces(ou).items() if k in sku]
    up_faces += [(ol[k], q) for k, q in faces(ol + [c["fore"], c["above_rail"]]).items() if k in skl]
    out = []
    for k in top:
        poly = fs.get(k)
        if not poly:
            continue
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if math.dist(a, b) < 0.02 or not any(_on(a, ol[s]) and _on(b, ol[s]) for s in skl):
                continue
            for pl, q in up_faces:
                if _on(a, pl) and _on(b, pl):
                    out.append((a, b, pl[0], q))
                    break
    return out


def _seam_aft(j: dict, ye: float) -> list:
    """The seam aft of the hinge line to ye (where it meets the hull's lead edge), on O_U's faces."""
    ou, sku, _ol, _skl = hulls(j)
    hy = j["lower_hinge"][1]
    seam_k = next(k for k in range(len(ou)) if k not in sku)
    poly = faces(ou)[seam_k]
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        q = S.clip(S.clip([a, b, b], (0, -1, 0), -hy), (0, 1, 0), ye)
        q = [p for i, p in enumerate(q) if i == 0 or math.dist(p, q[i - 1]) > 1e-6]
        if len(q) < 2 or math.dist(q[0], q[-1]) < 0.02:
            continue
        a2, b2 = q[0], q[-1]
        for k in sku:
            if _on(a2, ou[k]) and _on(b2, ou[k]):
                out.append((a2, b2, ou[k][0], faces(ou)[k]))
                break
    return out


def _strips(lines, w=STRIP[0], lift=STRIP[1]):
    bars = []
    for a, b, n, q in lines:
        c = tuple(sum(p[k] for p in q) / len(q) for k in range(3))
        bars.append(_band(a, b, n, S._sub(c, a), w, lift))
    return bars


def _shift_parts(parts, o):
    for p in parts:
        p["verts"] = [(v[0] - o[0], v[1] - o[1], v[2] - o[2]) for v in p["verts"]]
    return parts


def lower_parts(j: dict) -> list:
    """The lower jaw in the plan frame (closed): rails and belly shell, deck plate, bulkhead, ribs and edge lights."""
    ou, sku, ol, skl = hulls(j)
    c = cuts(j)
    reg = ol + [c["fore"], c["v"], c["below_rail"]]
    sh = shell(reg, skl, hide=aft_faces(ol))
    k_fore, k_v, k_rail = len(ol), len(ol) + 1, len(ol) + 2
    k_seam = [k for k in range(len(ol)) if k not in skl]
    glow = [r for k in [k_rail] for r in sh["rim"].get(k, [])]
    seam_glow = [r for k in k_seam for r in sh["rim"].get(k, [])]   # the tip's rim: visual (the walk, b3)
    frame = [r for k in (k_fore, k_v) for r in sh["rim"].get(k, [])]
    olh = _offset(ol, skl, SHELL / 2)
    # the deck plate runs out to the tip: over the belly it may thin out (3 mm inside the belly's skin there)
    old_ = [(n, d - (0.003 if n[2] < -0.5 and abs(n[0]) < 0.3 else SHELL / 2)) if k in skl else (n, d)
            for k, (n, d) in enumerate(ol)]
    deck = _solid_polys(old_ + [c["fore"], c["v"], c["below_deck"], c["below_plate"]])
    bulk = _solid_polys(olh + [c["v"], _flip((c["v"][0], c["v"][1] - BULK)), _flip(c["below_plate"])])
    parts = _plated(sh["outer"], "lower_skin", c["below_deck"], nocol_down=True)
    parts += _flat("lower_inner", _below(sh["inner"], c["below_deck"]), "ext_silver_c")
    parts += _flat("lower_rail_glow", glow, "glow_cyan")
    parts += _flat("lower_tip_glow", seam_glow, "glow_cyan", nocol=True)
    parts += _flat("lower_rim", frame, "ext_frame")
    # only the deck's top face collides: the plate's underside and edges face down or away at the tip, and Jolt's
    # recovery from those back faces pressed the capsule into the ground there (the open walk's stop, b3; b4)
    p0, u, w = deck_frame(j)
    deck_top = [(q, n) for q, n in deck if n[2] > 0.5 and abs(S._dot(n, w) - 1.0) < 1e-6]
    parts += _flat("lower_deck", deck_top, "ext_silver_c")
    parts += _flat("lower_deck_edge", [(q, n) for q, n in deck if (q, n) not in deck_top], "ext_silver_c", nocol=True)
    parts += _flat("lower_bulkhead", bulk, "hull_dark")
    # ribs across the deck and two amber lit edges along the rails' feet
    top = deck_top[0][0]
    length = math.hypot(j["lower_hinge"][1] - j["tip_y"], j["seam_h"] - j["floor_h"])

    def at(s, x, hh):
        return tuple(p0[k] + u[k] * s + w[k] * hh + (x if k == 0 else 0.0) for k in range(3))

    def half(s):
        pts = [p for a, b in zip(top, top[1:] + top[:1]) for p in [a, b]]
        best = 0.0
        for a, b in zip(top, top[1:] + top[:1]):
            sa, sb = S._dot(S._sub(a, p0), u), S._dot(S._sub(b, p0), u)
            if (sa - s) * (sb - s) <= 0 and abs(sa - sb) > 1e-9:
                t = (s - sa) / (sb - sa)
                best = max(best, abs(a[0] + (b[0] - a[0]) * t))
        return best if pts else 0.0

    ribs, edges = [], []
    s = 0.35
    while s < length - 0.4:
        hw = half(s) - 0.3   # polish n2: the ribs stop short of the hazard bands along the edges
        if hw > 0.2:
            corners = [at(s + d_, sx * hw, hh) for hh in (0.0, 0.014) for d_ in (0.0, 0.07) for sx in (-1, 1)]
            ribs.append((corners, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]))
        s += 0.42
    n_seg = 12
    step = length / n_seg
    for side in (-1, 1):
        for i in range(n_seg):
            s0, s1 = i * step + 0.03, (i + 1) * step - 0.03
            if s1 > length - 0.35:
                break
            a0, a1 = side * (half(s0) - 0.07), side * (half(s1) - 0.07)
            v = [at(s0, a0, 0.0), at(s0, a0 + side * 0.04, 0.0), at(s1, a1 + side * 0.04, 0.0), at(s1, a1, 0.0)]
            v += [at(s0, a0, 0.012), at(s0, a0 + side * 0.04, 0.012), at(s1, a1 + side * 0.04, 0.012), at(s1, a1, 0.012)]
            edges.append((v, [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]))
    # polish n2: hazard bands inboard of the amber edge lights (the old ramp's stripes went with it): a dark band
    # 12 cm wide, 13 cm in from each edge, yellow bars slanted 45 deg every 0.2 m on it
    def box(q, h0, h1):
        v = [at(sv, xv, hh) for hh in (h0, h1) for sv, xv in q]
        return v, [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    dark, yel = [], []
    for side in (-1, 1):
        def xe(sv, e, side=side):
            return side * (half(sv) - e)
        sv = 0.3
        while sv + 0.2 <= length - 0.4:
            q = [(sv, xe(sv, 0.25)), (sv + 0.2, xe(sv + 0.2, 0.25)), (sv + 0.2, xe(sv + 0.2, 0.13)), (sv, xe(sv, 0.13))]
            dark.append(box(q if side > 0 else q[::-1], 0.0, 0.004))
            q = [(sv, xe(sv, 0.25)), (sv + 0.1, xe(sv + 0.1, 0.25)), (sv + 0.2, xe(sv + 0.2, 0.13)),
                 (sv + 0.1, xe(sv + 0.1, 0.13))]
            yel.append(box(q if side > 0 else q[::-1], 0.004, 0.007))
            sv += 0.2
    hz = [L.part("deck_hazard_dark", *L.merge(*dark), "ext_hazard_dark"),
          L.part("deck_hazard", *L.merge(*yel), "ext_hazard")]
    for p_ in hz:
        p_["nocol"] = True
    rib = L.part("deck_ribs", *L.merge(*ribs), "leg_metal")
    rib["nocol"] = True
    lit = L.part("deck_edges", *L.merge(*edges), "glow_amber")
    lit["nocol"] = True
    return parts + [rib, lit] + hz


def upper_parts(j: dict) -> list:
    """The upper jaw in the plan frame (closed): the top shell, the skirts, the ceiling plate with its lit edges, the
    bulkhead over the seam, the cyan mouth line."""
    ou, sku, ol, skl = hulls(j)
    c = cuts(j)
    hy = j["lower_hinge"][1]
    k_seam_u = next(k for k in range(len(ou)) if k not in sku)
    u_aft = shell(ou + [c["aft"]], sku, hide=aft_faces(ou))
    u_fore = shell(ou + [c["fore"]], sku, hide=aft_faces(ou))
    skirt = shell(ol + [c["fore"], c["above_rail"]], skl, hide=aft_faces(ol))
    parts = _plated(u_aft["outer"] + u_fore["outer"] + skirt["outer"], "upper_skin")
    parts += _flat("upper_inner", u_aft["inner"] + u_fore["inner"] + skirt["inner"], "ext_silver_c")
    parts += _flat("upper_rim", u_aft["rim"].get(k_seam_u, []) + u_fore["rim"].get(k_seam_u, [])
                   + skirt["rim"].get(len(ol), []), "ext_frame")
    parts += _flat("upper_skirt_glow", skirt["rim"].get(len(ol) + 1, []), "glow_cyan")
    ouh = _offset(ou, sku, SHELL / 2)
    yb0, yb1 = hy - UPPER_BULK[0], hy - UPPER_BULK[1]
    ceil = ouh + [_hp((0, 1, 0), yb1), c["below_ceil"], _flip((c["below_ceil"][0], c["below_ceil"][1] - PLATE_T))]
    ceil_polys = _solid_polys(ceil)
    parts += _flat("upper_ceiling", ceil_polys, "ext_silver_b")
    bulk = []
    for side in ("cham_out_e", "cham_out_w"):
        bulk += _solid_polys(ouh + [_hp((0, 1, 0), yb1), _hp((0, -1, 0), -yb0), c["below_ceil"], c["above_seam"], c[side]])
    parts += _flat("upper_bulkhead", bulk, "ext_frame")
    # the ceiling's lit edges: a cyan bar under each side edge
    under = max(((q, n) for q, n in ceil_polys if n[2] < -0.5), key=lambda qn: S.area(qn[0]), default=None)
    bars = []
    if under:
        q, n = under
        cq = tuple(sum(p[k] for p in q) / len(q) for k in range(3))
        for a, b in zip(q, q[1:] + q[:1]):
            if abs(b[1] - a[1]) > 0.5:
                lo_h = j["seam_h"] + 0.2                    # the bar stops where the roof comes down near the seam
                if min(a[2], b[2]) < lo_h < max(a[2], b[2]):
                    t = (lo_h - a[2]) / (b[2] - a[2])
                    m = tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
                    a, b = (m, b) if a[2] < lo_h else (a, m)
                if min(a[2], b[2]) >= lo_h - 1e-6:
                    bars.append(_band(a, b, n, S._sub(cq, a), 0.035, 0.012, 0.004))
    glow = L.part("ceiling_glow", *L.merge(*bars), "glow_cyan__jaw_ceil") if bars else None
    line = L.part("seam_glow", *L.merge(*_strips(parting(j) + _seam_aft(j, j.get("seam_end_y", -6.2)))), "glow_cyan")
    line["nocol"] = True
    out = parts + [line]
    if glow:
        glow["nocol"] = True
        out.append(glow)
    return out


def root_parts(j: dict) -> list:
    """The fixed root in the plan frame: the lower hull's shell aft of the hinge line, the front bulkhead round the
    portal with its chrome lip, and the hood and lid over the entry tunnel inside the prow."""
    ou, sku, ol, skl = hulls(j)
    c = cuts(j)
    hy, fh, hs = j["lower_hinge"][1], j["floor_h"], j["seam_h"]
    wx, bh, tx, th = j["portal"]
    sh = shell(ol + [c["aft"]], skl, hide=aft_faces(ol))
    k_seam = [k for k in range(len(ol)) if k not in skl]
    parts = _plated(sh["outer"], "root_skin")
    parts += _flat("root_inner", sh["inner"], "hull_dark")
    parts += _flat("root_rim", [r for k in k_seam + [len(ol)] for r in sh["rim"].get(k, [])], "ext_frame")
    # the front bulkhead (y hy .. hy + BULK) round the opening; the tunnel's slab front is its own face
    olh = _offset(ol, skl, SHELL / 2)
    ouc = _offset(ou, sku, SHELL + CLEAR)
    bw = [_hp((0, -1, 0), -hy), _hp((0, 1, 0), hy + BULK)]
    slab_b = fh - j["slab_m"]

    def hz(lo, hi):
        return [_hp((0, 0, -1), -lo), _hp((0, 0, 1), hi)]

    regions = [olh + bw + hz(-9.0, slab_b)]
    for sx in (1, -1):
        side = _hp((-sx, 0, 0), -wx)
        cham = c["cham_out_e"] if sx > 0 else c["cham_out_w"]
        regions += [olh + bw + hz(slab_b, fh) + [side], olh + bw + hz(fh, bh) + [side],
                    olh + bw + hz(bh, hs) + [cham], ouc + bw + hz(hs, th + 0.3) + [cham]]
    regions.append(ouc + bw + hz(th, th + 0.3) + c["cham_in"])
    bulk = [pq for r in regions for pq in _solid_polys(r)]
    parts += _flat("root_bulkhead", bulk, "ext_frame")
    # the chrome lip round the opening (sides and top, none across the floor), LIP[1] proud of the bulkhead
    lw, lp = LIP
    f0 = fh + 0.04                                       # its feet over the deck plate's hinge end
    prof = [(wx, f0), (wx, bh), (tx, th), (-tx, th), (-wx, bh), (-wx, f0)]
    outp = [(wx + lw, f0), (wx + lw, bh + lw * 0.45), (tx + lw * 0.55, th + lw), (-tx - lw * 0.55, th + lw),
            (-wx - lw, bh + lw * 0.45), (-wx - lw, f0)]
    lip = []
    for i in range(len(prof) - 1):
        a, b, bo, ao = prof[i], prof[i + 1], outp[i + 1], outp[i]
        quad = [(a[0], a[1]), (b[0], b[1]), (bo[0], bo[1]), (ao[0], ao[1])]
        v = [(x, hy - lp, h) for x, h in quad] + [(x, hy, h) for x, h in quad]
        f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        if S._dot(S._newell([v[k] for k in f[0]]), (0, -1, 0)) < 0:
            f = [tuple(reversed(x)) for x in f]
        lip.append((v, f))
    lip_p = L.part("root_lip", *L.merge(*lip), "glow_edge")
    lip_p["nocol"] = True
    parts.append(lip_p)
    # the hood over the tunnel's chamfers and ceiling, and the lid at the seam beside it, inside the prow
    ys = [hy + BULK, -7.1, S.TH_ROOF_Y + 0.04]
    hood, lid = [], []
    olt = _offset(ol, skl, SHELL)

    def tun(y):
        w, k = HJ._tun_w(y)
        return w, k

    for sx in (1, -1):
        for y0, y1 in zip(ys, ys[1:]):
            (w0, k0), (w1, k1) = tun(y0), tun(y1)
            h_lo = hs - 0.06
            ch0 = (w0 - (h_lo - bh) * (wx - tx) / (th - bh) * k0 + 0.012, h_lo)
            ch1 = (w1 - (h_lo - bh) * (wx - tx) / (th - bh) * k1 + 0.012, h_lo)
            t0, t1 = (w0 - (wx - tx) * k0 + 0.012, th + 0.012), (w1 - (wx - tx) * k1 + 0.012, th + 0.012)
            q = [(sx * ch0[0], y0, ch0[1]), (sx * ch1[0], y1, ch1[1]), (sx * t1[0], y1, t1[1]), (sx * t0[0], y0, t0[1])]
            nrm = S._newell(q)
            hood.append((q if nrm[0] * sx > 0 else list(reversed(q)), None))
            if sx > 0:
                tq = [(-t0[0], y0, t0[1]), (t0[0], y0, t0[1]), (t1[0], y1, t1[1]), (-t1[0], y1, t1[1])]
                hood.append((tq if S._newell(tq)[2] > 0 else list(reversed(tq)), None))
            # the lid: the seam's plane just under it, from beside the hood out to the shell
            xin = (w0 - 0.035, w1 - 0.035)
            n_in = S._unit3((-sx * 1.0, (xin[1] - xin[0]) / (y1 - y0) * 1.0, 0.0))
            d_in = S._dot(n_in, (sx * xin[0], y0, 0.0))
            lid += _solid_polys(olt + [_hp((0, -1, 0), -y0), _hp((0, 1, 0), y1), _hp(n_in, d_in),
                                       _hp((0, 0, 1), hs - 0.004), _hp((0, 0, -1), -(hs - 0.03))])
    parts += _flat("root_hood", hood, "hull_silver")
    parts += _flat("root_lid", lid, "hull_dark")
    return parts


def deck_frame(j: dict):
    """The deck's frame (closed): origin the hinge on the floor, u forward along the deck, w its normal up."""
    hy, fh, ds = j["lower_hinge"][1], j["floor_h"], j["deck_slope"]
    k = 1.0 / math.hypot(1.0, ds)
    u = (0.0, -k, ds * k)
    w = (0.0, ds * k, k)
    return (0.0, hy, fh), u, w


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


def _front(parts):
    """The shells' faces are wound counter-clockwise about their outward side in the plan frame (x, y, h), and
    ship_build.make mirrors y into Blender, which turns that winding over: every open shell (solid False, no normal
    recalculation) came out facing inward (b2, b3). The materials are double-sided, so the look never showed it, but
    Godot's trimesh colliders are one-sided: the deck's top let the capsule fall through from above and its underside
    caught it at the tip (the open walk's stop, b4). Reversed here, each face's front is its outward side in Blender
    and Godot."""
    for p in parts:
        if not p.get("solid", True):
            p["faces"] = [tuple(reversed(f)) for f in p["faces"]]
    return parts


def front_normal(q):
    """A face's front (Blender's and Godot's) in the plan frame, after _front: the opposite of its Newell normal."""
    n = S._unit3(S._newell(q))
    return (-n[0], -n[1], -n[2])


def jaw_upper(args: dict, layout: dict) -> list:
    """The upper jaw, origin at [jaw] upper_hinge."""
    j = jaw(layout)
    return _front(_shift_parts(upper_parts(j), j["upper_hinge"]))


def jaw_lower(args: dict, layout: dict) -> list:
    """The lower jaw, the ramp, origin at [jaw] lower_hinge."""
    j = jaw(layout)
    return _front(_shift_parts(lower_parts(j), j["lower_hinge"]))


def jaw_root(args: dict, layout: dict) -> list:
    """The fixed root, plan origin."""
    return _front(root_parts(jaw(layout)))
