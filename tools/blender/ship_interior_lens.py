"""Lens room C, step 1 (art #263, docs/ship.md "Lens room C"): the charger's wall alcove with its four conduits (both
lens rooms) and the east lens room's lounge (a six-module sofa along the window band, a table, a lamp, a speaker and a
plant on the sofa's spine). Static decor, built from the design's cm drawing (prime-game-design
ideas/ship-components/lens-room/drawing/drawing.js, look C; the concept c_lounge.jpg for what the drawing leaves out).

Frames. The alcove is built in the charger's frame (tools/blender/charger_dims.toml): u across (+ to the right as you
face the button), d out of the wall from the spot's vertex, h up from the deck, in cm; the piece's origin is the vertex
on the floor, placed like a wall piece (room toward -x), so a point (u, d, h) is local (-d, u, FLOOR + h). A sofa
module is built on its facet's face (origin the facet's middle on the face): d from the face, its ends on the two
vertices' bisectors. The lounge's items stand at their own points (origin on the floor under them)."""

from __future__ import annotations

import math

import ship_interior as S
import ship_interior_geom as G
import ship_lib as L

D = math.radians
FLOOR = S.FLOOR
CM = 0.01
HALF = S.TIP_STEP / 2                                  # 10.977 deg
HW = S.R_TIP * math.sin(D(HALF))                       # a facet's half width on its face (0.3905 m)
APO = S.R_TIP * math.cos(D(HALF))                      # the facets' apothem (2.0125 m)
TAN = math.tan(D(HALF))

L.MATERIALS.update({
    # the alcove's back panel and the speaker's face: the drawing's graphite, a dark grey; lens C step 3: rough and
    # nearly dielectric (metallic 0.55 / rough 0.38 mirrored the room's probe: the panel read light grey)
    "lens_graphite": {"base": (0.05, 0.052, 0.058, 1.0), "metallic": 0.12, "roughness": 0.66},
    "lens_graphite2": {"base": (0.075, 0.078, 0.086, 1.0), "metallic": 0.12, "roughness": 0.7},
    # the sofa's upholstery (c_lounge: terracotta seats and backs, one charcoal module), matte fabric; lens C step 2:
    # a deeper, warmer terracotta (step 1's 0.30/0.075/0.045 read salmon under the room's warm light); step 3: darker
    # and browner still (step 2's 0.17/0.036/0.020 read orange-salmon under the lamp)
    # step 4 (the critic: saturated orange-red, blown out under the lamp): a muted brick, rougher
    "lens_cushion_red": {"base": (0.06, 0.016, 0.012, 1.0), "metallic": 0.0, "roughness": 0.97},
    # step 4: the seats and the charcoal module a warm charcoal (the cold 0.05/0.05/0.055 read grey-mauve)
    "lens_cushion_dark": {"base": (0.034, 0.029, 0.026, 1.0), "metallic": 0.0, "roughness": 0.96},
    # step 4 (c_lounge): the throw pillows, a lighter terracotta and a slate blue-grey, and the folded charcoal throw
    "lens_pillow_terra": {"base": (0.10, 0.03, 0.019, 1.0), "metallic": 0.0, "roughness": 0.96},
    "lens_pillow_slate": {"base": (0.03, 0.038, 0.05, 1.0), "metallic": 0.0, "roughness": 0.95},
    "lens_throw": {"base": (0.022, 0.02, 0.019, 1.0), "metallic": 0.0, "roughness": 0.98},
    "lens_leaf": {"base": (0.05, 0.16, 0.04, 1.0), "metallic": 0.0, "roughness": 0.6},
    # the warm strips (sofa base, table rings, the alcove's): amber that glows and lights nothing (ship.toml
    # [light.mats] int_amber__lens, l 0: no strip lights for decor)
    "int_amber__lens": {**L.MATERIALS["int_amber"]},
    # step 4: the sofa's underside strip at a third (ship.toml e 0.047) and the table's lit edge ring (e 0.3)
    "int_amber__lens_toe": {**L.MATERIALS["int_amber"]},
    "int_amber__lens_ring": {**L.MATERIALS["int_amber"]},
    # lens C step 2: the conduits' cyan core, brighter than int_cyan's e 0.05 (ship.toml [light.mats], l 0)
    "int_cyan__lens_core": {**L.MATERIALS["int_cyan"]},
    # the charger traces (prime-game#1095, a_circuit.jpg): the alcove's back panel a matte dark navy (#0b1a2e, linear
    # here) and its inlaid cyan traces; ship.gd swaps lens_trace for godot/charger/traces.gdshader by name (the fill
    # the charger drives; no strip light), the GLB keeps a plain cyan glow for any other viewer
    "lens_panel": {"base": (0.0033, 0.0103, 0.027, 1.0), "metallic": 0.0, "roughness": 0.82},
    "lens_trace": {"base": (0.02, 0.12, 0.2, 1.0), "metallic": 0.0, "roughness": 0.4, "emission": (0.1, 0.7, 1.0),
                   "strength": 2.0},
})
# the stations' shared bronze (godot/console/console.gd's `bronze` on console_metal.gdshader): ship.gd swaps these three
# for that shader by name (LENS_BRONZE), the GLB keeps the same colours for any other viewer (linear here); the faces a
# rich bronze, the second tone a little darker, the edges a glossy bevel (the values the lens C shots were judged with)
for _n, (_c, _m, _r) in {"lens_bronze": ((0.64, 0.42, 0.22), 0.70, 0.30),
                         "lens_bronze2": ((0.58, 0.38, 0.20), 0.70, 0.32),
                         "lens_edge": ((0.74, 0.52, 0.30), 0.85, 0.18)}.items():
    L.MATERIALS.setdefault(_n, {"base": (*(x ** 2.2 for x in _c), 1.0), "metallic": _m, "roughness": _r})
BRONZE, BRONZE2, EDGE = "lens_bronze", "lens_bronze2", "lens_edge"

# --- the drawing's numbers (cm) -----------------------------------------------------------------------------------
ALCOVE = {"back": 10.0, "open_front": 50.0, "open_back": 46.0, "top": 200.0, "chamfer": (182.0, 34.0),
          "jamb_out": 60.0, "face": 46.0, "jamb_top": 226.0}
# lens C step 2: the conduits' axis at d 38 (the drawing's 21 hid them behind the 46 cm jambs head-on: their front
# now at 43.5, 2.5 behind the jambs' face line) and a wider core (Ø 4.4, the drawing's 3)
CONDUIT = {"u": 68.0, "d": 38.0, "r": 5.5, "bend": 8.0, "low": 92.0, "high": 170.0, "collar_r": 7.0, "collar_l": 4.0,
           "collars_h": (24.0, 56.0), "collars_top": (0.3, 0.7), "flange_r": 8.0, "flange_h": 3.0, "core_r": 2.2,
           "bracket": (3.0, 5.0)}   # step 4: two collars per straight run (the upper run's at 0.3 and 0.7 of it), each
                                    # with a bracket (3 wide, 5 tall) back to the wall
# the charger traces on the back panel (cm, the charger's frame: u across, h up; prime-game#1095 c6468773545): lines of
# `w` inlaid in the panel's face (each kind a hair proud of it, `lift`, so a branch tucks under its trunk, a trunk
# under the ring and the dots: no two coplanar), a ring behind the crystal (centre u 0, h `ring_h`, radius `ring_r` to
# its line's middle, line `ring_w`), hollow dots (`dot`: outer and inner radius) at the dot traces' tips
TRACE = {"w": 1.2, "ring_h": 115.0, "ring_r": 18.0, "ring_w": 1.5, "dot": (2.0, 1.0), "pair": 3.0,
         "lift": {"branch": 0.06, "trunk": 0.08, "dot": 0.1, "ring": 0.12}}
REACH = 70.0                                           # the charger's reach (renewer_e/_w depth_m 0.70)
AXIS_D = 38.0                                          # the crystal's axis (the charger step's)
SOFA = {"spine": (0.0, 18.0, 88.0), "back": (18.0, 32.0, 44.0, 80.0, 4.0), "seat": (18.0, 76.0, 30.0, 44.0),
        "cushion_d": 32.0, "toe": (4.0, 10.0), "arm": (9.0, 54.0), "strip": (7.0, 9.0)}   # step 4: slimmer arms (14 x 58)
SOFA_K = (-5, 1)                                       # the sofa's end vertices (k * TIP_STEP): -109.77 .. +21.95
ITEMS = {"lounge_table": {"th": -112.5, "r": 85.0}, "lounge_lamp": {"th": -60.0, "d": 9.0},
         "lounge_speaker": {"th": -38.0, "d": 9.0}, "lounge_plant": {"th": -16.0, "d": 9.0}}


def wall_d(u: float) -> float:
    """The wall's face d (cm) at u across the charger's vertex: the two facets beside it, then the next pair."""
    a, u1 = abs(u), S.R_TIP * 100 * math.sin(D(2 * HALF))
    d1 = S.R_TIP * 100 * (1 - math.cos(D(2 * HALF)))
    return a * TAN if a <= u1 else d1 + (a - u1) * math.tan(D(3 * HALF))


def facet_mid(th: float) -> float:
    return round((th - HALF) / S.TIP_STEP) * S.TIP_STEP + HALF


def item_polar(pid: str) -> tuple[float, float, float]:
    """An item's (r m, theta deg, yaw angle deg: the facet it faces) in the room's frame, as the drawing's atD/pol."""
    it = ITEMS[pid]
    if "r" in it:
        return it["r"] * CM, it["th"], it["th"]
    fm = facet_mid(it["th"])
    return (APO - it["d"] * CM) / math.cos(D(it["th"] - fm)), it["th"], fm


def ceiling_h(u: float, side: str) -> float:
    """The lens ceiling's clear height (m over the deck) over the conduit at u (cm) in the renewer's frame: the east
    room's +u runs toward the door (the slant's high side), the west room's (placed turned, not mirrored) outward."""
    th = D(S_RENEWER)
    t = (S.R_TIP * 100 * math.cos(th) - CONDUIT["d"] * math.cos(th) - (u if side == "e" else -u) * math.sin(th)) * CM
    return S.tip_clear(t)


_REN = next(s["at"] for s in S._SHIP["stations"]["spot"] if s["id"] == "renewer_e")
S_RENEWER = math.degrees(math.atan2(_REN[1] - S._ROOM["tip_e"]["centre"][1],
                                    _REN[0] - S._ROOM["tip_e"]["centre"][0])) - S.COR_ANG   # 87.82


# --- helpers ------------------------------------------------------------------------------------------------------
def P(name, vf, mat, solid=True):
    return L.part(name, *vf, mat, solid=solid)


def ud(u: float, d: float) -> tuple[float, float]:
    """A charger-frame plan point (cm) as the piece's local (x, y) in m."""
    return (-d * CM, u * CM)


def ccw(poly):
    return poly if G.area2(poly) > 0 else poly[::-1]


def loft(rings):
    """A closed solid through horizontal-ish rings of equal size (each a list of 3D points, counter-clockwise from
    above), capped at both ends."""
    n = len(rings[0])
    verts = [p for r in rings for p in r]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range((len(rings) - 1) * n, len(rings) * n))]
    faces += [(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i)
              for k in range(len(rings) - 1) for i in range(n)]
    return verts, faces


def disc_x(r, n, x0, x1, y, z):
    """A closed n-sided disc whose axis runs along x (a face toward -x), centred at (y, z)."""
    v, f = L.disc(r, n, x0, x1)
    return [(h, y + a, z + b) for a, b, h in v], f


def facet_quad(d0, d1, e0, e1, lean=0.0):
    """A plan quad on a facet's face (cm): d0..d1 out of the face, its ends on the vertices' bisectors moved in by
    e0 (the -y end) and e1 (the +y end); lean moves the front edge back (cm)."""
    def half(d):
        return HW - d * CM * TAN
    f = d1 - lean
    return [(-d0 * CM, -(half(d0) - e0 * CM)), (-d0 * CM, half(d0) - e1 * CM),
            (-f * CM, half(f) - e1 * CM), (-f * CM, -(half(f) - e0 * CM))]


def facet_block(d0, d1, h0, h1, e0=0.0, e1=0.0, top=0.0, bot=0.0, lean=0.0):
    """A block on a facet (cm), its top (and bottom) edges rounded off by a chamfer of `top` (`bot`) cm; the lean
    tilts its front back by `lean` at the top."""
    rings = []
    if bot:
        rings.append((facet_quad(d0 + bot, d1 - bot, e0 + bot, e1 + bot), h0))
    rings.append((facet_quad(d0, d1, e0, e1), h0 + bot))
    if top:
        rings.append((facet_quad(d0, d1, e0, e1, lean * (h1 - top - h0) / (h1 - h0)), h1 - top))
    rings.append((facet_quad(d0 + top, d1 - top, e0 + top, e1 + top, lean), h1))
    return loft([[(x, y, FLOOR + h * CM) for x, y in ccw(q)] for q, h in rings])


# --- the alcove (both lens rooms) ---------------------------------------------------------------------------------
def lens_alcove(args, layout):
    """The charger's surround at the renewer's vertex: a graphite back panel (a chord at d 10, u +-46, to h 200), the
    opening's splayed cheeks (+-46 at the back, +-50 at the front) with its top corners cut (+-50, 182) -> (+-34, 200),
    two bronze jambs (u +-50..60, face d 46) and the lintel (200..226), the warm strips on the cheeks, under the
    opening's head and on the lintel (the drawing's front view)."""
    A = ALCOVE
    fl = G.floor_frame(0.0)
    wf = G.wall_frame(FLOOR)
    out = []
    for k, s in enumerate((-1, 1)):
        jamb = [ud(s * A["open_back"], 0.0), ud(s * A["open_back"], A["back"]), ud(s * A["open_front"], A["face"]),
                ud(s * A["jamb_out"], A["face"]), ud(s * A["jamb_out"], 0.0)]
        out.append(P(f"jamb{k}", G.slab(fl, ccw(jamb), FLOOR, FLOOR + A["top"] * CM, 0.012), BRONZE))   # step 4: 0.006
        # the jamb's face plate: a bevelled plate 1 cm proud on its front, the concept's panel line
        out.append(P(f"jamb_plate{k}", G.slab(wf, G.rect(*sorted((s * (A["open_front"] + 1.5) * CM,
                                                                   s * (A["jamb_out"] - 1.5) * CM)),
                                                         0.06, A["top"] * CM - 0.06), A["face"] * CM,
                                              (A["face"] + 1.0) * CM, 0.008), EDGE))   # step 4: 0.004 aliased
        c0, c1 = A["chamfer"]
        tri = [(s * A["open_front"] * CM, c0 * CM), (s * A["open_front"] * CM, A["top"] * CM),
               (s * c1 * CM, A["top"] * CM)]
        out.append(P(f"corner{k}", G.slab(wf, ccw(tri), A["back"] * CM, A["face"] * CM), BRONZE2))
        # the warm strip on the cheek, d 22..34 (u ~48), h 104..196
        def cheek(d):
            return A["open_back"] + (A["open_front"] - A["open_back"]) * (d - A["back"]) / (A["face"] - A["back"])
        strip = [ud(s * (cheek(22) + 0.1), 22), ud(s * (cheek(34) + 0.1), 34), ud(s * (cheek(34) - 0.5), 34),
                 ud(s * (cheek(22) - 0.5), 22)]
        out.append(P(f"cheek_strip{k}", G.slab(fl, ccw(strip), FLOOR + 1.04, FLOOR + 1.96), "int_amber__lens"))
    out += [
        P("lintel", G.slab(wf, G.rect(-A["jamb_out"] * CM, A["jamb_out"] * CM, A["top"] * CM, A["jamb_top"] * CM),
                           0.0, A["face"] * CM, 0.012), BRONZE),
        # the charger traces: the panel matte navy, flat (the graphite plate on it went: the traces run edge to edge)
        P("back", G.slab(wf, G.rect(-A["open_back"] * CM, A["open_back"] * CM, 0.0, A["top"] * CM), 0.0,
                         A["back"] * CM, 0.004), "lens_panel"),
        *trace_parts(),
        P("head_strip", G.slab(wf, G.rect(-0.26, 0.26, 1.94, 1.98), A["back"] * CM, (A["back"] + 0.6) * CM),
          "int_amber__lens"),
        P("lintel_strip", G.slab(wf, G.rect(-0.14, 0.14, 2.10, 2.14), (A["face"] - 0.1) * CM, (A["face"] + 0.5) * CM),
          "int_amber__lens"),
    ]
    return out


# --- the charger traces (both lens rooms) -------------------------------------------------------------------------
def _seg_len(pts) -> list[float]:
    """The arc length (cm) at each point of a polyline."""
    s = [0.0]
    for (u0, h0), (u1, h1) in zip(pts, pts[1:]):
        s.append(s[-1] + math.hypot(u1 - u0, h1 - h0))
    return s


def trace_layout() -> dict:
    """The traces in the charger's frame (cm), from the concept a_circuit.jpg and the design's numbers: every line
    runs orthogonally with 45-degree bends from an outer end inward to the ring. Trunks end on the ring's line (under
    it); a branch ends on its trunk's centre line (under it). Each stroke's fill coordinate runs 0 at its outer end to
    1 at the ring: a trunk's is its arc length over its length, a branch's reaches its trunk's value at the junction,
    so a fill front reaches the junction on both at once. Returns {"strokes": [{"name", "kind" (trunk | branch), "pts"
    [(u, h)], "fill" [per point 0..1], "scale" (cm of line per unit of fill)}], "dots": [{"name", "at" (u, h), "fill",
    "scale"}], "ring": (u, h, r, w)}. The right half (u > 0) is mirrored to the left; the centre line is one."""
    T, A, K = TRACE, ALCOVE, CONDUIT
    r, hc = T["ring_r"], T["ring_h"]
    edge = A["open_back"] + 0.3                     # the side edge, tucked 3 mm into the cheek
    top = 194.5                                     # under the head strip (h 194..198, u +-26), 5 mm behind it
    def on_ring(u):                                 # a vertical line's end on the ring's middle
        return (u, hc + math.sqrt(r * r - u * u))
    diag = r / math.sqrt(2.0)
    d45 = [(22.0, top), (22.0, hc + 22.0), (diag, hc + diag)]   # the 45-degree lane: h = u + ring_h
    hi, lo, p = K["high"], K["low"], T["pair"]
    right = {
        # the dot line: from a hollow dot near the centre line, down, 45 degrees in, down to the ring
        "dot": ("trunk", [(12.0, 181.0 - sum(T["dot"]) / 2), (12.0, 174.0), (6.0, 168.0), on_ring(6.0)]),
        "top": ("trunk", d45),
        # the low conduit's line: in from the side edge at the conduit's height (behind the pedestal), up the gap
        # between the outer prong and the cheek, 45 degrees in and down, into the ring's side
        "low": ("trunk", [(edge, lo), (43.0, lo), (43.0, 136.0), (22.0, hc), (r, hc)]),
        # branches into the top lane: one down from the lintel and the high conduit's pair from the side edge
        "lintel": ("branch", [(30.0, A["top"] + 0.5), (30.0, 185.0), (22.0, 177.0)]),
        "high0": ("branch", [(edge, hi + p), (36.0, hi + p), (22.0, hi + p - 14.0)]),
        "high1": ("branch", [(edge, hi - p), (38.0, hi - p), (22.0, hi - p - 16.0)]),
    }
    trunk_s = _seg_len(d45)
    def trunk_fill_at(h):                           # the top lane's fill at a junction on its vertical run
        return (top - h) / trunk_s[-1]
    strokes, dots = [], []
    centre = [(0.0, top), on_ring(0.0)]
    strokes.append({"name": "centre", "kind": "trunk", "pts": centre, "fill": [0.0, 1.0], "scale": _seg_len(centre)[-1]})
    for s, side in ((1, "r"), (-1, "l")):
        for name, (kind, pts) in right.items():
            pts = [(s * u, h) for u, h in pts]
            arc = _seg_len(pts)
            end = 1.0 if kind == "trunk" else trunk_fill_at(pts[-1][1])
            fill = [end * a / arc[-1] for a in arc]
            strokes.append({"name": f"{name}_{side}", "kind": kind, "pts": pts, "fill": fill, "scale": arc[-1] / end})
            if name == "dot":
                dots.append({"name": f"dot_{side}", "at": (s * 12.0, 181.0), "fill": 0.0, "scale": arc[-1]})
    return {"strokes": strokes, "dots": dots, "ring": (0.0, hc, r, T["ring_w"])}


def _ribbon(pts, w):
    """A flat line of width w along a polyline (u, h): mitred corners; the left and right edge points per point."""
    out = []
    n = len(pts)
    for i in range(n):
        dirs = []
        if i > 0:
            dirs.append((pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        if i < n - 1:
            dirs.append((pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]))
        dirs = [(a / math.hypot(a, b), b / math.hypot(a, b)) for a, b in dirs]
        nu, nh = [(-b, a) for a, b in dirs][0] if len(dirs) == 1 else (0.0, 0.0)
        if len(dirs) == 2:                          # the miter: the two normals' bisector, stretched
            n0, n1 = (-dirs[0][1], dirs[0][0]), (-dirs[1][1], dirs[1][0])
            bu, bh = n0[0] + n1[0], n0[1] + n1[1]
            k = math.hypot(bu, bh)
            cos_half = k / 2.0
            nu, nh = bu / k / cos_half, bh / k / cos_half
        out.append(((pts[i][0] + nu * w / 2, pts[i][1] + nh * w / 2), (pts[i][0] - nu * w / 2, pts[i][1] - nh * w / 2)))
    return out


def _panel_point(u, h, lift):
    """A point on the back panel's face (cm; lift out of it) as the piece's local metres."""
    return (-(ALCOVE["back"] + lift) * CM, u * CM, FLOOR + h * CM)


def _facing(verts, face):
    """The face's corners turned toward the room (-x) once built: the harness mirrors plan y into Blender's (x, -y,
    h), which turns a face's winding over, so the plan-frame normal here must point away from the room (+x)."""
    a, b, c = (verts[i] for i in face[:3])
    nx = (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1])
    return face if nx > 0 else face[::-1]


def _uv(fill, scale_cm):
    """A trace's UV: x its fill coordinate, y (Godot's, after the glTF exporter's v -> 1 - v) the line's metres per
    unit of fill (the head's size in the shader); the ring has y -1."""
    return (fill, 1.0 - scale_cm * CM)


def _annulus(cu, ch, r0, r1, n, lift, uv):
    verts, faces, uvs = [], [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        verts += [_panel_point(cu + r1 * math.cos(a), ch + r1 * math.sin(a), lift),
                  _panel_point(cu + r0 * math.cos(a), ch + r0 * math.sin(a), lift)]
    for i in range(n):
        j = (i + 1) % n
        f = _facing(verts, (2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
        faces.append(f)
        uvs.append([uv] * 4)
    return verts, faces, uvs


def trace_parts() -> list[dict]:
    """The traces as three flat parts on the back panel in lens_trace (no collider): the lines, the dots, the ring;
    each corner's UV the fill coordinate (_uv) for godot/charger/traces.gdshader."""
    lay, T = trace_layout(), TRACE
    lv, lf, lu = [], [], []
    for st in lay["strokes"]:
        lift = T["lift"][st["kind"]]
        base = len(lv)
        for (left, right), f in zip(_ribbon(st["pts"], T["w"]), st["fill"]):
            lv += [_panel_point(*left, lift), _panel_point(*right, lift)]
            lu += [_uv(f, st["scale"])] * 2
        for i in range(len(st["pts"]) - 1):
            q = (base + 2 * i, base + 2 * i + 2, base + 2 * i + 3, base + 2 * i + 1)
            lf.append(_facing(lv, q))
    lines = P("trace_lines", (lv, lf), "lens_trace", solid=False)
    lines["uv"] = [[lu[i] for i in f] for f in lf]
    dv, df, du = [], [], []
    for d in lay["dots"]:
        v, f, u = _annulus(*d["at"], T["dot"][1], T["dot"][0], 20, T["lift"]["dot"], _uv(d["fill"], d["scale"]))
        df += [tuple(i + len(dv) for i in face) for face in f]
        dv += v
        du += u
    dots = P("trace_dots", (dv, df), "lens_trace", solid=False)
    dots["uv"] = du
    cu, ch, r, w = lay["ring"]
    rv, rf, ru = _annulus(cu, ch, r - w / 2, r + w / 2, 72, T["lift"]["ring"], (1.0, 2.0))
    ring = P("trace_ring", (rv, rf), "lens_trace", solid=False)
    ring["uv"] = ru
    return [lines, dots, ring]


def conduit_paths(side: str, s: int) -> list[list[tuple[float, float, float]]]:
    """The two conduits' axes on one side (s = -1, +1 in u), local metres: the lower out of the jamb's outer face at h
    92, an elbow of r 8 down to the deck; the upper out at h 170, an elbow up into the ceiling."""
    K, j = CONDUIT, ALCOVE["jamb_out"]
    x = -K["d"] * CM
    top = ceiling_h(s * K["u"], side) + 0.03
    low = [(x, s * (j - 1.0) * CM, FLOOR + K["low"] * CM)]
    high = [(x, s * (j - 1.0) * CM, FLOOR + K["high"] * CM)]
    for i in range(11):
        a = D(9.0 * i)
        low.append((x, s * (j + K["bend"] * math.sin(a)) * CM, FLOOR + (K["low"] - K["bend"] + K["bend"] * math.cos(a)) * CM))
        high.append((x, s * (j + K["bend"] * math.sin(a)) * CM, FLOOR + (K["high"] + K["bend"] - K["bend"] * math.cos(a)) * CM))
    low.append((x, s * K["u"] * CM, FLOOR - 0.02))
    high.append((x, s * K["u"] * CM, FLOOR + top))
    return [low, high]


CORE_SIDES = 10


def core_uvs(path, sides: int) -> list:
    """A conduit core's UVs per face of G.tube(path, r, sides) (its quads ring by ring, then the two caps): x the run
    coordinate (0 where the conduit leaves the jamb, 1 at the deck or the ceiling), y (Godot's, after the glTF
    exporter's v -> 1 - v) the run's length in metres, for godot/charger/conduit.gdshader's pulses (charger zap)."""
    run = [0.0]
    for a, b in zip(path, path[1:]):
        run.append(run[-1] + math.dist(a, b))
    total = run[-1]
    f = [r / total for r in run]
    y = 1.0 - total
    out = [[(f[i], y), (f[i], y), (f[i + 1], y), (f[i + 1], y)] for i in range(len(path) - 1) for _ in range(sides)]
    return out + [[(f[0], y)] * sides, [(f[-1], y)] * sides]


def lens_conduits(args, layout):
    """The four conduits (one piece per room: the ceiling slants, so the two sides reach it at different heights):
    bronze tubes of 11 cm, a 3 cm cyan core on the room side, collars of 14 x 4 where they leave the jamb and on the
    straight runs (h 40, 210), flanges of 16 x 3 at the deck and the ceiling."""
    side, K = args.get("side", "e"), CONDUIT
    tubes, cores, collars, core_uv = [], [], [], []
    for s in (-1, 1):
        x = -K["d"] * CM
        for path in conduit_paths(side, s):
            tubes.append(G.tube(path, K["r"] * CM, 16))
            off = (K["r"] - K["core_r"] + 0.4) * CM
            cores.append(G.tube([(px - off, py, pz) for px, py, pz in path], K["core_r"] * CM, CORE_SIDES))
            core_uv += core_uvs(path, CORE_SIDES)
        y0, y1 = sorted((s * ALCOVE["jamb_out"] * CM, s * (ALCOVE["jamb_out"] + K["collar_l"]) * CM))
        for h in (K["low"], K["high"]):
            v, f = L.cylinder_y(K["collar_r"] * CM, 20, y0, y1)
            collars.append(([(px + x, py, pz + FLOOR + h * CM) for px, py, pz in v], f))
        top = ceiling_h(s * K["u"], side)
        h_up0 = K["high"] + K["bend"]
        runs = list(K["collars_h"]) + [h_up0 + f * (top / CM - h_up0) for f in K["collars_top"]]
        for h0, h1 in [(hc - K["collar_l"] / 2, hc + K["collar_l"] / 2) for hc in runs] + [(0.0, K["flange_h"])]:
            collars.append(S.shift(L.disc((K["flange_r"] if h0 == 0.0 else K["collar_r"]) * CM, 20,
                                          FLOOR + h0 * CM, FLOOR + h1 * CM), x, s * K["u"] * CM))
        # step 4: a bracket from each straight run's collar back to the wall (1 cm into it) and a plate on the wall
        bw, bh = K["bracket"]
        dw = wall_d(K["u"])
        for hc in runs:
            zc = FLOOR + hc * CM
            for d0, d1, half, hh in ((dw - 1.0, K["d"] - K["r"] + 0.5, bw / 2, bh / 2),
                                     (dw - 1.0, dw + 0.8, bw * 1.6, bh * 1.2)):
                ring = [(-d0 * CM, s * (K["u"] - half) * CM), (-d0 * CM, s * (K["u"] + half) * CM),
                        (-d1 * CM, s * (K["u"] + half) * CM), (-d1 * CM, s * (K["u"] - half) * CM)]
                collars.append(loft([[(px, py, zc - hh * CM) for px, py in ccw(ring)],
                                     [(px, py, zc + hh * CM) for px, py in ccw(ring)]]))
        collars.append(S.shift(L.disc(K["flange_r"] * CM, 20, FLOOR + top - K["flange_h"] * CM, FLOOR + top + 0.02),
                               x, s * K["u"] * CM))
    core = P("cores", L.merge(*cores), "int_cyan__lens_core")
    core["uv"] = core_uv
    return [P("tubes", L.merge(*tubes), BRONZE2), core, P("collars", L.merge(*collars), EDGE)]


def cushion_block(d0, d1, h0, h1, e0=0.0, e1=0.0, r=3.5, crown=1.2, lean=0.0):
    """A cushion on a facet (cm), lens C step 2: its edges rounded by r in two steps (top) and r/2 (bottom), its top
    crowned: a plateau inset by a third of the way to the middle, `crown` cm over the rounded edge; `lean` as
    facet_block's."""
    half = min(d1 - d0, 78.0) / 2
    c_in = r + (half - r) / 3
    b = r / 2
    ring_spec = [(b, 0.0), (b * 0.29, b * 0.29), (0.0, b), (0.0, h1 - h0 - r), (r * 0.29, h1 - h0 - r * 0.29),
                 (r, h1 - h0), (c_in, h1 - h0 + crown)]
    rings = []
    for i, z in ring_spec:
        t = z / (h1 - h0 + crown)
        rings.append((facet_quad(d0 + i, d1 - i, e0 + i, e1 + i, lean * min(t, 1.0)), h0 + z))
    return loft([[(x, y, FLOOR + h * CM) for x, y in ccw(q)] for q, h in rings])


# --- the east lounge ----------------------------------------------------------------------------------------------
SEAM = 0.15        # cm: each module's spine and base stop short of the vertex's bisector (a 3 mm joint)
CUSHION_SEAM = 0.5  # cm: the cushions' joint at a module's end (1 cm between two modules)


def lounge_sofa_base(args, layout):
    """A sofa module's base (the collider): the toe recess (d 18..72, h 0..10), the base (d 18..76, h 10..30), the warm
    strip on the recess's face at h 7..9."""
    s0, s1, sh = SOFA["spine"]
    b0, b1, h0, top = SOFA["seat"]
    toe_d, toe_h = SOFA["toe"]
    st0, st1 = SOFA["strip"]
    return [P("toe", facet_block(b0, b1 - toe_d, 0.0, toe_h, SEAM, SEAM), "lens_graphite"),
            P("base", facet_block(b0, b1, toe_h, h0, SEAM, SEAM, top=0.8), BRONZE2),
            P("strip", facet_block(b1 - toe_d - 0.1, b1 - toe_d + 0.4, st0, st1, 1.0, 1.0), "int_amber__lens_toe")]


def lounge_sofa(args, layout):
    """A sofa module's spine and upholstery (no collider): the bronze spine (d 0..18, h 88), the back cushion (d
    18..32, h 44..80, its top 4 cm back), the seat cushion (d 32..76, h 30..44); `arm` -1 / +1 an end module's arm (14
    x 58) at its -y / +y end; `tone` the seat's fabric."""
    s0, s1, sh = SOFA["spine"]
    k0, k1, kh0, kh1, lean = SOFA["back"]
    b0, b1, h0, top = SOFA["seat"]
    aw, ah = SOFA["arm"]
    arm = args.get("arm", 0)
    back = "lens_cushion_dark" if args.get("tone") == "dark" else "lens_cushion_red"
    fab = "lens_cushion_dark"   # step 4: every seat a warm charcoal (c_lounge), the backs terracotta
    e0 = (aw if arm < 0 else 0.0) + CUSHION_SEAM
    e1 = (aw if arm > 0 else 0.0) + CUSHION_SEAM
    out = [P("spine", facet_block(s0, s1, 0.0, sh, SEAM, SEAM, top=1.2), BRONZE),
           P("spine_cap", facet_block(s1 - 0.6, s1 + 0.3, sh - 3.0, sh - 1.8, SEAM, SEAM), EDGE),
           P("fill", facet_block(k0, SOFA["cushion_d"], h0, kh0, SEAM, SEAM), "lens_graphite"),
           P("back", cushion_block(k0, k1, kh0, kh1 - 0.8, e0, e1, r=3.0, crown=0.8, lean=lean), back),
           P("seat", cushion_block(SOFA["cushion_d"], b1, h0, top - 1.2, e0, e1, r=4.0, crown=1.2), fab)]
    if arm:
        # the arm: a bronze block on the base from the spine to the seat's front, its outer face on the bisector
        quad = facet_quad(b0, b1, SEAM, SEAM)
        if arm < 0:
            q = [quad[0], (quad[0][0], quad[0][1] + aw * CM), (quad[3][0], quad[3][1] + aw * CM), quad[3]]
        else:
            q = [(quad[1][0], quad[1][1] - aw * CM), quad[1], quad[2], (quad[2][0], quad[2][1] - aw * CM)]
        # step 4: slimmer, the same at both ends: a bronze post to 6 cm under its top, a charcoal pad on it
        rings = [(ccw(q), h0), (ccw(q), ah - 6.0)]
        out.append(P("arm", loft([[(x, y, FLOOR + h * CM) for x, y in r] for r, h in rings]), BRONZE))
        pad = [(G.inset(ccw(q), 0.004), ah - 6.0), (ccw(q), ah - 4.8), (ccw(q), ah - 1.6), (G.inset(ccw(q), 0.012), ah)]
        out.append(P("arm_pad", loft([[(x, y, FLOOR + h * CM) for x, y in r] for r, h in pad]), "lens_cushion_dark"))
    return out


def lounge_pillow(args, layout):
    """A throw pillow leaning on the back cushion (c_lounge): 40 x 14 x 38 cm, rounded, tilted back 16 deg; `y` its
    centre along the facet (m)."""
    y, fab = args.get("y", 0.0), args.get("fabric", "lens_pillow_terra")
    lean = math.tan(D(16.0))
    # step 4: a puffy pillow (the box read as a block): about 42 x 36, its thickness swelling from 3 cm at the top and
    # bottom seams to 14 in the middle, its corners pinched; each ring a 12-point outline (front and back bulge)
    rings = []
    for h in (0.0, 0.03, 0.09, 0.18, 0.27, 0.33, 0.36):
        t = max(0.0, math.sin(math.pi * h / 0.36))   # never a hair under 0 at the top (a complex root)
        hw = 0.18 + 0.03 * t ** 0.5
        pts = []
        for k in range(12):
            a = 2 * math.pi * k / 12
            sa = math.sin(a)
            th = 0.0 if abs(sa) < 1e-6 else (0.015 + 0.055 * t) * (1.0 - 0.55 * abs(math.cos(a)) ** 3) * math.copysign(1.0, sa)
            pts.append((-(0.405 + th) + h * lean, y + hw * math.cos(a), FLOOR + 0.44 + h))
        rings.append(pts)
    return [P("pillow", loft([r if G.area2([(p[0], p[1]) for p in r]) > 0 else r[::-1] for r in rings]), fab)]


def lounge_throw(args, layout):
    """Step 4 (c_lounge): a folded charcoal throw on a seat, over its front edge: 34 cm wide along the facet (`y`
    its centre), 3 cm thick, from d 44 on the seat over the front down to h 33."""
    y, w, t = args.get("y", 0.12), 0.17, 3.0
    b1, top = SOFA["seat"][1], SOFA["seat"][3] - 1.2 + 0.3
    path = [(44.0, top), (b1 - 3.0, top), (b1 + 0.6, top - 3.2), (b1 + 1.0, 33.0)]   # (d, h) cm along its inside
    outer = [(d + dd, h + dh) for (d, h), (dd, dh) in zip(path, ((0.0, t), (0.6, t), (t * 0.8, t * 0.4), (t, 0.0)))]
    prof = path + outer[::-1]                                  # a closed (d, h) section
    rings = [[(-d * CM, y + e, FLOOR + h * CM) for d, h in prof] for e in (-w, w)]
    return [P("throw", loft(rings), "lens_throw")]


def lounge_table(args, layout):
    """The coffee table (the collider): Ø 56 x 48 (c_lounge's drum): a plinth and its warm ring, a 12-sided drum,
    the top with a warm edge ring and a graphite inset."""
    return [P("plinth", L.disc(0.24, 32, FLOOR, FLOOR + 0.04), BRONZE2),
            P("drum", L.disc(0.20, 12, FLOOR + 0.04, FLOOR + 0.42), BRONZE2),
            P("top", L.disc(0.28, 40, FLOOR + 0.42, FLOOR + 0.48), BRONZE),
            P("inset", L.disc(0.245, 40, FLOOR + 0.47, FLOOR + 0.482), "lens_graphite"),
            P("rings", L.disc(0.226, 32, FLOOR + 0.04, FLOOR + 0.052), "int_amber__lens"),
            # step 4: the top's lit edge ring (c_lounge), a 2.4 cm band 4 mm proud (was 1.4 cm x 1.5 mm, unseen)
            P("edge_ring", L.disc(0.284, 40, FLOOR + 0.438, FLOOR + 0.462), "int_amber__lens_ring")]


def lounge_cans(args, layout):
    """Two drink cans on the table (c_lounge), Ø 6.6 x 12, a cyan band each."""
    out = []
    for k, (x, y) in enumerate(((0.07, -0.06), (-0.05, 0.09))):
        out += [P(f"can{k}", S.shift(L.disc(0.033, 16, FLOOR + 0.482, FLOOR + 0.602), x, y), "int_silver_c"),
                P(f"band{k}", S.shift(L.disc(0.0336, 16, FLOOR + 0.525, FLOOR + 0.555), x, y),
                  "int_cyan__lens_core")]   # step 4: the conduits' cyan (int_cyan's e 0.05 read grey)
    return out


SPINE_TOP = FLOOR + SOFA["spine"][2] * CM


def lounge_lamp(args, layout):
    """The lamp on the spine (c_lounge's faceted lantern): Ø 18 x 36, a bronze hex foot and cap round a glowing
    faceted body."""
    def hexr(r, h, off=0.0):
        return [(r * math.cos(D(60 * i + off)), r * math.sin(D(60 * i + off)), SPINE_TOP + h) for i in range(6)]
    body = loft([hexr(0.05, 0.05), hexr(0.088, 0.17), hexr(0.06, 0.32), hexr(0.024, 0.345)])
    return [P("foot", L.disc(0.075, 6, SPINE_TOP, SPINE_TOP + 0.05), EDGE), P("body", body, "int_lamp"),
            P("cap", L.disc(0.03, 6, SPINE_TOP + 0.34, SPINE_TOP + 0.36), BRONZE)]


def lounge_speaker(args, layout):
    """The speaker on the spine: 34 wide, 22 tall, 16 deep, bronze, a graphite face with a cyan-ringed woofer and a
    tweeter (the front toward -x)."""
    z0 = SPINE_TOP
    fr = G.wall_frame(0.0, 0.08)
    return [P("body", G.slab(fr, G.rect(-0.17, 0.17, z0, z0 + 0.22), 0.0, 0.16, 0.012), BRONZE2),
            P("face", G.slab(fr, G.rect(-0.155, 0.155, z0 + 0.015, z0 + 0.205), 0.16, 0.163), "lens_graphite"),
            P("ring", disc_x(0.068, 28, -0.087, -0.083, 0.055, z0 + 0.11), "int_cyan"),
            P("cone", M_(disc_x(0.058, 28, -0.09, -0.084, 0.055, z0 + 0.11),
                         disc_x(0.026, 16, -0.095, -0.084, -0.1, z0 + 0.13)), "lens_graphite2"),
            P("dot", disc_x(0.008, 10, -0.0985, -0.094, -0.1, z0 + 0.13), "int_cyan")]


def M_(*vfs):
    return L.merge(*vfs)


def lounge_plant(args, layout):
    """The plant in a bronze pot on the spine: the pot Ø 16 x 14, its rim, soil, and nine blades up to 40."""
    z = SPINE_TOP

    def octr(r, h):
        return [(r * math.cos(D(45 * i + 22.5)), r * math.sin(D(45 * i + 22.5)), z + h) for i in range(8)]
    leaves = []
    for k in range(9):
        a = D(40 * k + 7)
        reach, rise, w = 0.10 + 0.05 * ((k * 5) % 3), 0.22 + 0.035 * ((k * 7) % 4), 0.028 + 0.004 * (k % 2)
        ca, sa = math.cos(a), math.sin(a)
        if ca > 0.0:   # toward the wall (+x): keep the blade in front of the window's face (d >= 0.5)
            reach = min(reach, 0.085 / ca)
        base = (0.012 * ca, 0.012 * sa, z + 0.12)
        mid = (reach * 0.55 * ca, reach * 0.55 * sa, z + 0.12 + rise * 0.75)
        tip = (reach * ca, reach * sa, z + 0.12 + rise)
        side = (-sa * w, ca * w, 0.0)
        pts = [base, (mid[0] + side[0], mid[1] + side[1], mid[2]), tip, (mid[0] - side[0], mid[1] - side[1], mid[2])]
        leaves.append((pts, [(0, 1, 2, 3), (3, 2, 1, 0)]))
    return [P("pot", loft([octr(0.068, 0.0), octr(0.08, 0.125)]), BRONZE),
            P("rim", loft([octr(0.083, 0.118), octr(0.083, 0.14)]), EDGE),
            P("soil", loft([octr(0.074, 0.12), octr(0.074, 0.132)]), "lens_graphite"),
            P("leaves", L.merge(*leaves), "lens_leaf", solid=False)]
