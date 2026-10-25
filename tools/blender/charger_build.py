"""The ship's crystal charger (art#263's stations; two, one on each lens room's aft wall), built from code in headless
Blender from its drawing, tools/blender/charger_dims.toml (centimetres; charger_drawing.py draws it). The driver
(charger_run.py) calls it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/charger_build.py -- \
      --out <dir> [--crystal <energy_crystal.glb>] [--render <dir>] [--res 900] [--samples 64] [--hdri <hdr>]

Blender axes: X = u (across, + to the right as you face it), -Y = d (out of the wall, glTF +Z), Z = h; the origin
on the floor at the wall's face under the crystal's axis (the spot's `at`).

- The squat stepped dome, round and clear of the wall: the lower tier (a flared ring of bronze blocks: the underside
  slant, the widest straight band, the top bevel), the upper tier (Ø 82, its bevel to the deck), the deck's inner
  course of blocks; every block a profile swept straight between two angles (flat chord faces), the joints thin dark
  seams onto the graphite core. Each block has two bevels: a broad chamfer (UV0 u 0.45) and a small bright bevel on
  its folds (UV0 u 1), which the metal brightens (the sheet's worn edges).
- The front block: the button's trapezoid facet (a graphite plate behind the block's chords, the bezel and the lens)
  between a strip under it, a strip over it and a wedge either side, every face on the block's chords (flush with its
  neighbours). The amber and cyan slots in graphite bezels on the blocks, thick enough to read at 3 m.
- The deck: the collar of the slot, the cyan slot ring, the fixed outer prongs on the u axis (the hero: an (r, h)
  claw profile swept round the axis: a root block, a column that bows out, a chunky cap hooking in, graphite joint
  plates; a cyan and an amber strip up the front face, amber up the inner face).
- Four legs like the ship's landing legs, angled out: a bronze upper strut with an amber slot, a graphite gland, the
  dark steel piston rod (lengthened 27 cm), a bronze ankle sleeve, a faceted pad with two amber bars on three faces.
- The leaves (own objects, pivot on their axes, children of the body): `carrier` (the cup under the crystal with
  the pit for its point; rises 6 cm and spins; the empty `crystal_anchor` on it where the crystal's tip sits),
  `track_ring` (spins, carries the inner prong pair with their electrodes), `button` (presses 1 cm in along +d).
  Convex colliders `*-convcolonly`: the base, the outer prongs, each leg; the inner prongs (on the ring).

Writes into --out: crystal_charger.glb (plain-PBR fallback), crystal_charger.blend (the look materials), build.json
(triangles, size, pivots, the anchor, colliders, the clearance checks: the wall's facets, the ring's full turn,
the carrier's rise), features.json (the blocks' edges for the drawing). With --render: the review renders into that folder
(hero, the states, the orthographic views at PX_PER_CM, the close-ups of the edges and seams).
"""

import json
import math
import sys
import tomllib
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

DIMS = tomllib.loads((Path(__file__).with_name("charger_dims.toml")).read_text(encoding="utf-8"))
CM = 0.01
FR, BA = DIMS["frame"], DIMS["base"]
AX = FR["axis_d"]
SEAM = BA["seam"]
FOLD = math.radians(FR["back_fold_deg"])
PX_PER_CM = 4.0


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"out": None, "crystal": None, "render": None, "res": 900, "samples": 64, "hdri": None}
    i = 0
    while i < len(a):
        out[a[i].lstrip("-")] = a[i + 1]
        i += 2
    out["res"], out["samples"] = int(out["res"]), int(out["samples"])
    return out


# --- frames --------------------------------------------------------------------------------------------------------
def P(u: float, d: float, h: float) -> Vector:
    """The drawing's (u, d, h) cm -> Blender metres."""
    return Vector((u * CM, -d * CM, h * CM))


def polar(a_deg: float, r: float, h: float) -> Vector:
    """A point a_deg round the crystal's axis (0 toward the room, + toward +u), r cm from it, at h cm."""
    a = math.radians(a_deg)
    return P(r * math.sin(a), AX + r * math.cos(a), h)


def seam_deg(r: float) -> float:
    return math.degrees(SEAM * 0.5 / r)


def wall_dist(u: float, d: float) -> float:
    """A point's distance (cm) in front of the lens room's wall: its two facets fold toward the room by FOLD either
    side of the spot's vertex (u 0, d 0)."""
    return -abs(u) * math.sin(FOLD) + d * math.cos(FOLD)


# --- mesh helpers --------------------------------------------------------------------------------------------------
def ring_faces(bm, rings: list, closed: bool = False, caps: bool = True) -> list:
    out = []
    if closed:
        rings = rings + [rings[0]]
    n = len(rings[0])
    for lo, hi in zip(rings, rings[1:]):
        for j in range(n):
            k = (j + 1) % n
            out.append(bm.faces.new((lo[j], lo[k], hi[k], hi[j])))
    if caps and not closed:
        out.append(bm.faces.new(list(reversed(rings[0]))))
        out.append(bm.faces.new(rings[-1]))
    return out


def lathe(bm, prof: list, sides: int, closed: bool = True, rot: float = 0.0, centre=(0.0, AX)) -> list:
    """A solid of revolution round the vertical axis through (u, d) centre: prof [(r, h) cm]; closed: a loop."""
    rings = []
    for r, h in prof:
        ring = []
        for j in range(sides):
            a = math.radians(rot + 360.0 * j / sides)
            ring.append(bm.verts.new(P(centre[0] + r * math.sin(a), centre[1] + r * math.cos(a), h)))
        rings.append(ring)
    return ring_faces(bm, rings, closed=closed, caps=not closed)


def sector(bm, a0: float, a1: float, prof: list) -> list:
    """A block from a0 to a1 (deg): the closed profile [(r, h) cm] swept straight, so its outer faces are chords."""
    r0 = [bm.verts.new(polar(a0, r, h)) for r, h in prof]
    r1 = [bm.verts.new(polar(a1, r, h)) for r, h in prof]
    n = len(prof)
    faces = [bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i])) for i in range(n)]
    faces.append(bm.faces.new(list(reversed(r0))))
    faces.append(bm.faces.new(r1))
    return faces


def loft(bm, a: list, b: list) -> list:
    """A prism between two matching closed outlines a and b (Vectors): its sides and two caps."""
    va = [bm.verts.new(p) for p in a]
    vb = [bm.verts.new(p) for p in b]
    return ring_faces(bm, [va, vb])


def prism(bm, outline: list, plane: float, depth: float) -> list:
    """A block whose front is the outline [(u, h) cm] in the plane d = plane, extruded depth cm toward the wall."""
    return loft(bm, [P(u, plane - depth, h) for u, h in outline], [P(u, plane, h) for u, h in outline])


def slab(bm, outline: list, d0: float, d1: float) -> list:
    """A prism of a (u, h) outline between d0 and d1 (side-on)."""
    return loft(bm, [P(u, d0, h) for u, h in outline], [P(u, d1, h) for u, h in outline])


def box(bm, centre: Vector, size: tuple, basis: Matrix) -> list:
    res = bmesh.ops.create_cube(bm, size=1.0)
    for v in res["verts"]:
        v.co = centre + basis @ Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    faces = list({f for v in res["verts"] for f in v.link_faces})
    for f in faces:
        f.normal_update()
    return faces


def light_box(bm, centre: Vector, normal: Vector, up: Vector, length: float, width: float, light: int = 3,
              proud: float | None = None, inset: float | None = None) -> None:
    """A graphite bezel standing `proud` cm out of a face (centre on it, metres; length along up), its light inset
    in it (material slot `light`), still in front of the face (b1: an inset deeper than the bezel's height hid the
    light behind the host face)."""
    s = DIMS["lights"]
    across = normal.cross(up).normalized()  # right-handed (across, normal, up): the box keeps its normals outward
    basis = Matrix((across, normal, up)).transposed()
    proud = s["proud"] if proud is None else proud
    inset = s["inset"] if inset is None else inset
    t = (proud + 0.5) * CM  # 0.5 cm sunk into the host
    faces = box(bm, centre + normal * (t * 0.5 - 0.5 * CM), ((width + 2 * s["bezel"]) * CM, t,
                                                           (length + 2 * s["bezel"]) * CM), basis)
    front = max(faces, key=lambda f: f.normal.dot(normal))
    bmesh.ops.inset_individual(bm, faces=[front], thickness=s["bezel"] * CM, depth=-inset * CM)
    front.material_index = light


def segment_light(bm, a: Vector, b: Vector, normal: Vector, width: float, light: int = 3) -> None:
    """A light strip from a to b (metres) on a face with the given normal."""
    up = (b - a).normalized()
    light_box(bm, (a + b) * 0.5, normal, up, (b - a).length / CM, width, light)


def disc(bm, prof: list, centre: Vector, axis: Vector, sides: int, closed: bool = False) -> None:
    """A solid of revolution about axis through centre: prof [(r, t) cm], t along the axis; capped."""
    z = axis.normalized()
    x = Vector((1.0, 0.0, 0.0)) if abs(z.x) < 0.9 else Vector((0.0, 1.0, 0.0))
    x = (x - z * x.dot(z)).normalized()
    y = z.cross(x)
    rings = [[bm.verts.new(centre + (x * math.cos(2 * math.pi * j / sides) + y * math.sin(2 * math.pi * j / sides))
                           * r * CM + z * t * CM) for j in range(sides)] for r, t in prof]
    ring_faces(bm, rings, closed=closed, caps=not closed)


# --- the base ------------------------------------------------------------------------------------------------------
# the tiers' outer profiles, bottom to top [(r, h)]
LOWER = [(BA["r_bottom"], BA["bottom"]), (BA["r_widest"], BA["widest"]), (BA["r_widest"], BA["band_top"]),
         (BA["r_lower_top"], BA["lower_top"])]
UPPER = [(BA["r_upper"], BA["lower_top"]), (BA["r_upper"], BA["upper_band"]), (BA["r_deck_edge"], BA["deck"])]
R_LOWER_IN = 37.0                # the lower tier's blocks reach in to here (the core behind them)
R_CORE = 37.6                    # the graphite core seen in the lower tier's seams and under it


def r_of(prof: list, h: float) -> float:
    """A profile's radius at h (linear between its points)."""
    for (r0, h0), (r1, h1) in zip(prof, prof[1:]):
        if h0 <= h <= h1 and h1 > h0:
            return r0 + (r1 - r0) * (h - h0) / (h1 - h0)
    return prof[-1][0] if h > prof[-1][1] else prof[0][0]


def blocks(edges: list) -> list:
    """[(a0, a1)] round the axis from a tier's block edges (deg; the first the front block's half angle)."""
    out = [(-edges[0], edges[0])]
    for a0, a1 in zip(edges, edges[1:]):
        out += [(a0, a1), (-a1, -a0)]
    return out


def tier_seam(prof: list) -> float:
    return seam_deg(max(r for r, _ in prof))


def tier(bm, edges: list, prof: list, r_in: float, skip_front: bool) -> None:
    """A tier: a ring of blocks, each the profile (closed at r_in) swept straight between two angles (chords)."""
    full = [(r_in, prof[0][1])] + prof + [(r_in, prof[-1][1])]
    g = tier_seam(prof)
    for a0, a1 in blocks(edges):
        if skip_front and a0 == -edges[0]:
            continue
        sector(bm, a0 + g, a1 - g, full)


def build_core(bm) -> None:
    """The graphite core: the underside, the drum seen in the seams, the deck under its rings, the track ring's
    groove, the slot's bore."""
    s, rg = DIMS["slot"], DIMS["ring"]
    deck = BA["deck"] - 0.3
    g0, g1 = rg["r0"] - rg["groove"], rg["r1"] + rg["groove"]
    floor = BA["deck"] - rg["h"] - rg["groove"]
    prof = [(2.0, BA["bottom"] + 0.4), (R_CORE, BA["bottom"] + 0.4), (R_CORE, BA["lower_top"] - 0.4),
            (BA["r_inner"] + 0.6, BA["lower_top"] + 0.4), (BA["r_inner"] + 0.6, deck), (g1, deck), (g1, floor),
            (g0, floor), (g0, deck), (s["collar"][0], deck), (s["collar"][0], s["bore_bottom"]),
            (2.0, s["bore_bottom"])]
    lathe(bm, prof, 96)


def build_lower(bm) -> None:
    tier(bm, BA["lower_edges"], LOWER, R_LOWER_IN, True)


def build_upper(bm) -> None:
    tier(bm, BA["upper_edges"], UPPER, BA["r_inner"], False)


def build_deck_ring(bm) -> None:
    """The deck's inner course of blocks round the track ring, flush with the upper tier's top."""
    r0, r1 = BA["deck_ring"]
    n, top = 16, BA["deck"]
    g = seam_deg(r1)
    for k in range(n):
        a0 = 11.25 + 22.5 * k
        sector(bm, a0 + g, a0 + 22.5 - g, [(r0 / math.cos(math.radians(11.25)), top - 4.0), (r1, top - 4.0),
                                           (r1, top), (r0 / math.cos(math.radians(11.25)), top)])


# --- the front block: the button's trapezoid facet -----------------------------------------------------------------
def clip_band(poly: list, h0: float, h1: float) -> list:
    """The part of a (u, h) polygon between h0 and h1 (Sutherland-Hodgman), without repeated points."""
    def clip(pts: list, keep, cut: float) -> list:
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            if keep(p) != keep(q):
                t = (cut - q[1]) / (p[1] - q[1])
                out.append((q[0] + t * (p[0] - q[0]), cut))
            if keep(p):
                out.append(p)
        return out
    pts = clip(poly, lambda p: p[1] >= h0 - 1e-9, h0)
    pts = clip(pts, lambda p: p[1] <= h1 + 1e-9, h1) if pts else []
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6):
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-6 and abs(out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


FRONT_HALF = DIMS["panel"]["half_deg"] - tier_seam(LOWER)  # the front block's chord ends (deg)


def chord_d(h: float, inset: float = 0.0) -> float:
    """The front block's chord face at h: its d (it is flat across u)."""
    return AX + r_of(LOWER, h) * math.cos(math.radians(FRONT_HALF)) - inset


def chord_w(h: float) -> float:
    return r_of(LOWER, h) * math.sin(math.radians(FRONT_HALF))


def chord_piece(bm, poly: list, inset: float = 0.0, depth: float = 9.0) -> None:
    """A piece of the front block whose outline poly [(u, h)] lies on its chord faces, `inset` cm behind them: one
    planar prism per band of the lower tier's profile (the faces fold where the profile does)."""
    for (_r0, h0), (_r1, h1) in zip(LOWER, LOWER[1:]):
        part = clip_band(poly, h0, h1)
        if len(part) < 3:
            continue
        loft(bm, [P(u, chord_d(h, inset) - depth, h) for u, h in part], [P(u, chord_d(h, inset), h) for u, h in part])


def trap_x(h: float) -> float:
    (tw, th), (bw, bh) = DIMS["panel"]["top"], DIMS["panel"]["bottom"]
    return bw + (tw - bw) * (h - bh) / (th - bh)


def build_front_block(bm) -> None:
    """The lower tier's front block round the trapezoid facet: a strip under it, a strip over it, a wedge either side,
    seams between them; every face on the block's chords (flush with its neighbours' corners, b4's panels jutted)."""
    (_tw, th), (_bw, bh) = DIMS["panel"]["top"], DIMS["panel"]["bottom"]
    s = SEAM * 0.5
    breaks = [h for _r, h in LOWER]

    def w(h: float) -> float:
        return chord_w(h) - 0.01

    def strip(h0: float, h1: float) -> list:
        hs = sorted({h0, h1} | {h for h in breaks if h0 < h < h1})
        return [(w(h), h) for h in hs] + [(-w(h), h) for h in reversed(hs)]

    chord_piece(bm, strip(BA["bottom"], bh - s))
    chord_piece(bm, strip(th + s, BA["lower_top"]))
    hs = sorted({bh + s, th - s} | {h for h in breaks if bh + s < h < th - s})
    for sx in (-1.0, 1.0):
        chord_piece(bm, [(sx * w(h), h) for h in hs] + [(sx * (trap_x(h) + s), h) for h in reversed(hs)])


def build_facet(bm) -> None:
    """The plate at the bottom of the trapezoid facet (bronze), `recess` behind the chords."""
    (tw, th), (bw, bh) = DIMS["panel"]["top"], DIMS["panel"]["bottom"]
    m = 0.8
    chord_piece(bm, [(-bw - m, bh - m), (bw + m, bh - m), (tw + m, th + m), (-tw - m, th + m)],
                inset=DIMS["panel"]["recess"], depth=4.0)


BUTTON_PLATE = chord_d(DIMS["button"]["h"], DIMS["panel"]["recess"])
BUTTON_D = BUTTON_PLATE + 1.8    # the lens's face (the bezel's lip at +1.4; the chord at +2.2)


def build_button_seat(bm) -> None:
    """The button's bezel ring on the facet's plate (graphite, a bronze-bright lip)."""
    b = DIMS["button"]
    c = P(0.0, BUTTON_PLATE, b["h"])
    rr, rl = b["ring"] / 2, b["lens"] / 2 + 0.25
    disc(bm, [(rl, -1.5), (rr, -1.5), (rr, 0.9), (rr - 0.5, 1.4), (rl + 0.4, 1.4), (rl, 1.1)], c,
         Vector((0.0, -1.0, 0.0)), 32, closed=True)


def build_button(bm) -> None:
    """The cyan lens: a short drum in the bezel's bore, its face at BUTTON_D."""
    b = DIMS["button"]
    r = b["lens"] / 2
    disc(bm, [(r, -0.7), (r, -0.4), (r - 0.4, 0.0), (0.01, 0.15)], P(0.0, BUTTON_D, b["h"]),
         Vector((0.0, -1.0, 0.0)), 32)


# --- the lights on the tiers ---------------------------------------------------------------------------------------
def block_frame(edges: list, prof: list, deg: tuple, h: float) -> tuple:
    """(centre, normal, up, along, length cm) of a light between two angles at height h on the block of a tier that
    holds them (the block's chord face there)."""
    a0, a1 = next((a, b) for a, b in zip(edges, edges[1:]) if a <= deg[0] and deg[1] <= b)
    g = tier_seam(prof)

    def chord(hh: float) -> tuple:
        p0, p1 = polar(a0 + g, r_of(prof, hh), hh), polar(a1 - g, r_of(prof, hh), hh)
        return p0, (p1 - p0).normalized()

    p0, along = chord(h)
    ends = [p0 + along * (polar(a, r_of(prof, h), h) - p0).dot(along) for a in deg]
    lo, _ = chord(h - 0.4)
    hi, _ = chord(h + 0.4)
    up = hi - lo
    up = (up - along * up.dot(along)).normalized()
    normal = along.cross(up).normalized()
    if normal.dot(polar(0.5 * (a0 + a1), 1.0, 0.0) - polar(0.0, 0.0, 0.0)) < 0:
        normal = -normal
    return (ends[0] + ends[1]) * 0.5, normal, up, along, (ends[1] - ends[0]).length / CM


def build_tier_lights(bm) -> None:
    """The cyan and amber slots on the tiers, mirrored across u 0: graphite bezels, the light inset (slot 3 amber,
    4 cyan)."""
    li = DIMS["lights"]
    jobs = [(BA["lower_edges"], LOWER, x, 4, False) for x in li["cyan_lower"]]
    jobs += [(BA["lower_edges"], LOWER, x, 3, True) for x in li["amber_lower"]]
    jobs += [(BA["upper_edges"], UPPER, x, 3, False) for x in li["amber_upper"]]
    hd = BA["upper_band"] + 0.5 * (BA["deck"] - BA["upper_band"])
    jobs += [(BA["upper_edges"], UPPER, {"deg": d, "h": [hd - 0.7, hd + 0.7]}, 3, False) for d in li["amber_deck"]]
    for edges, prof, spec, light, vertical in jobs:
        h0, h1 = spec["h"]
        c, n, up, along, length = block_frame(edges, prof, tuple(spec["deg"]), (h0 + h1) / 2)
        for sx in (1.0, -1.0):
            def m(v: Vector) -> Vector:
                return Vector((sx * v.x, v.y, v.z))
            if vertical:
                light_box(bm, m(c), m(n), m(up), h1 - h0, length, light)
            else:
                light_box(bm, m(c), m(n), m(along), length, h1 - h0, light)


# --- the slot ------------------------------------------------------------------------------------------------------
def build_collar(bm) -> None:
    s = DIMS["slot"]
    rb, ro = s["collar"]
    h0, h1 = BA["deck"] - 0.45, s["collar_top"]
    lathe(bm, [(rb, h0), (ro, h0), (ro, h1 - 0.5), (ro - 0.5, h1), (rb + 0.4, h1), (rb, h1 - 0.4)], 48)


def build_slot_glow(bm) -> None:
    r0, r1 = DIMS["slot"]["glow"]
    d = BA["deck"]
    lathe(bm, [(r0, d - 0.8), (r1, d - 0.8), (r1, d - 0.05), (r0, d - 0.05)], 64)


def build_carrier(bm) -> None:
    """The cup under the crystal: its rim at `top`, the pit for the crystal's point (steeper than the point: it
    never touches it)."""
    c, s = DIMS["carrier"], DIMS["slot"]
    r, top, bot = c["r"], c["top"], c["top"] - c["h"]
    p0, p1 = c["pit"]
    floor = s["tip"] - 0.1
    lathe(bm, [(0.05, bot), (r - 0.3, bot), (r, bot + 0.3), (r, top - 0.6), (r - 0.6, top), (p0 + 0.4, top),
               (p0, top - 0.3), (p1, floor), (0.05, floor)], 40)


def build_carrier_light(bm) -> None:
    c = DIMS["carrier"]
    lathe(bm, [(c["pit"][0] + 0.5, c["top"] - 0.1), (c["r"] - 0.8, c["top"] - 0.1), (c["r"] - 0.8, c["top"] + 0.08),
               (c["pit"][0] + 0.5, c["top"] + 0.08)], 40)


def build_ring(bm) -> None:
    """The track ring: an inner and an outer course of bronze blocks (offset joints) either side of the cyan
    channel, a graphite band under them."""
    rg = DIMS["ring"]
    top, bot = BA["deck"], BA["deck"] - rg["h"]
    l0, l1 = rg["light"]
    n = 16
    half = 180.0 / n
    for (r0, r1), rot in (((rg["r0"] / math.cos(math.radians(half)), l0), 0.0), ((l1, rg["r1"]), half)):
        g = seam_deg(r1)
        for k in range(n):  # b1: 8 blocks of 45 deg put the inner chords' middles into the groove's wall
            a0, a1 = rot + 2 * half * k, rot + 2 * half * (k + 1)
            sector(bm, a0 + g, a1 - g, [(r0, bot), (r1, bot), (r1, top), (r0, top)])
    lathe(bm, [(rg["r0"] + 0.5, bot - 0.1), (rg["r1"] - 0.6, bot - 0.1), (rg["r1"] - 0.6, top - 1.0),
               (rg["r0"] + 0.5, top - 1.0)], 64)


def build_ring_light(bm) -> None:
    l0, l1 = DIMS["ring"]["light"]
    d = BA["deck"]
    lathe(bm, [(l0 - 0.05, d - 1.2), (l1 + 0.05, d - 1.2), (l1 + 0.05, d - 0.3), (l0 - 0.05, d - 0.3)], 96)


# --- the prongs ----------------------------------------------------------------------------------------------------
def sweep(bm, prof: list, a_mid: float, half: float, steps: int) -> list:
    """A closed (r, h) polygon swept round the crystal's axis from a_mid - half to a_mid + half deg (steps chords)."""
    rings = [[bm.verts.new(polar(a_mid - half + 2.0 * half * k / steps, r, h)) for r, h in prof]
             for k in range(steps + 1)]
    n = len(prof)
    faces = [bm.faces.new((lo[i], lo[(i + 1) % n], hi[(i + 1) % n], hi[i])) for lo, hi in zip(rings, rings[1:])
             for i in range(n)]
    faces.append(bm.faces.new(list(reversed(rings[0]))))
    faces.append(bm.faces.new(rings[-1]))
    return faces


def end_face(a_mid: float, half: float) -> tuple:
    """The angle of a swept piece's end toward the room, and its outward normal (Blender)."""
    a = a_mid + half if a_mid < 0 else a_mid - half
    t = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0.0))  # d polar / d angle
    return a, (t if a_mid < 0 else -t)


SIDES = (-90.0, 90.0)           # the prongs on the u axis


def outer_pieces() -> list:
    o = DIMS["outer"]
    return [(o["root"], o["root_deg"], 1), (o["column"], o["half_deg"], 3), (o["cap"], o["cap_deg"], 3)]


def build_outer_prongs(bm) -> None:
    for a_mid in SIDES:
        for prof, half, steps in outer_pieces():
            sweep(bm, [tuple(p) for p in prof], a_mid, half, steps)


def build_prong_joints(bm) -> None:
    """Graphite plates in the outer prongs' joints (the seams read dark, never see-through)."""
    o = DIMS["outer"]
    for a_mid in SIDES:
        for prof in ([(26.4, 100.7), (39.8, 100.7), (39.8, 101.9), (26.4, 101.9)],
                     [(25.0, 128.1), (38.8, 128.1), (38.8, 129.3), (25.0, 129.3)]):
            sweep(bm, prof, a_mid, o["half_deg"] - 1.0, 3)


def build_outer_lights(bm) -> None:
    """The outer prongs' strips: cyan up the front face and round onto the cap's, amber beside it, amber up the
    inner face toward the crystal; thick (b4's 1.3 cm read thin)."""
    o = DIMS["outer"]
    wc, wa = o["strip_w"]
    for a_mid in SIDES:
        a, n = end_face(a_mid, o["half_deg"])
        cy = o["cyan"]
        for (r0, h0), (r1, h1) in zip(cy, cy[1:]):
            segment_light(bm, polar(a, r0, h0), polar(a, r1, h1), n, wc, 4)
        (r0, h0), (r1, h1) = o["amber"]
        segment_light(bm, polar(a, r0, h0), polar(a, r1, h1), n, wa, 3)
        ac, nc = end_face(a_mid, o["cap_deg"])
        (r0, h0), (r1, h1) = o["cyan_cap"]
        segment_light(bm, polar(ac, r0, h0), polar(ac, r1, h1), nc, wc, 4)
        r_in = o["column"][-1][0] * math.cos(math.radians(o["half_deg"] / 3))  # the middle chord of three
        inward = -(polar(a_mid, 1.0, 0.0) - polar(a_mid, 0.0, 0.0)).normalized()
        h0, h1 = o["amber_inner"]
        segment_light(bm, polar(a_mid, r_in, h0), polar(a_mid, r_in, h1), inward, wa, 3)


def inner_pieces() -> list:
    i = DIMS["inner"]
    return [i["column"], i["head"]]


def build_inner_prongs(bm) -> None:
    i = DIMS["inner"]
    for a_mid in SIDES:
        for prof in inner_pieces():
            sweep(bm, [tuple(p) for p in prof], a_mid, i["half_deg"], 3)
        sweep(bm, [(17.4, 116.2), (22.4, 116.2), (22.4, 117.2), (17.4, 117.2)], a_mid, i["half_deg"] - 1.0, 3)


def build_inner_lights(bm) -> None:
    i = DIMS["inner"]
    for a_mid in SIDES:
        a, n = end_face(a_mid, i["half_deg"])
        (r0, h0), (r1, h1) = i["amber"]
        segment_light(bm, polar(a, r0, h0), polar(a, r1, h1), n, i["amber_w"], 3)


def build_electrodes(bm) -> None:
    for a_mid in SIDES:
        for r, h, er in DIMS["inner"]["electrodes"]:
            c = polar(a_mid, r * math.cos(math.radians(DIMS["inner"]["half_deg"] / 3)) - er * 0.45, h)
            res = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=er * CM)
            for v in res["verts"]:
                v.co += c


# --- the legs ------------------------------------------------------------------------------------------------------
LG = DIMS["legs"]
LEG_ANGLES = [a * sx for a in LG["angles"] for sx in (-1.0, 1.0)]


def pad_s(a: float) -> float:
    """A leg's pad centre from the crystal's axis: the front pair's, or the back pair's (tucked off the wall)."""
    return LG["pad_s"][0] if abs(a) < 90.0 else LG["pad_s"][1]


def leg_s(a: float, h: float) -> float:
    """A leg's axis: its distance from the crystal's axis at height h (the hip down to the pad's centre)."""
    (s0, h0), s1, h1 = LG["hip"], pad_s(a), LG["ankle_h"]
    return s1 + (s0 - s1) * (h - h1) / (h0 - h1)


def leg_basis(a: float) -> tuple:
    """(radial, tangential, axis up the leg, across-the-leg normal toward the outside) for a leg at a deg."""
    ra = math.radians(a)
    radial = Vector((math.sin(ra), -math.cos(ra), 0.0))
    tang = Vector((math.cos(ra), math.sin(ra), 0.0))
    (s0, h0), s1, h1 = LG["hip"], pad_s(a), LG["ankle_h"]
    axis = (radial * (s0 - s1) + Vector((0.0, 0.0, h0 - h1))).normalized()
    out = tang.cross(axis).normalized()
    if out.dot(radial) < 0:
        out = -out
    return radial, tang, axis, out


def octagon(centre: Vector, x: Vector, y: Vector, w: float, t: float) -> list:
    """An octagon (a w x t rectangle with chamfered corners, cm) round centre in the plane of x, y."""
    c = 0.24 * min(w, t)
    pts = [(w / 2, t / 2 - c), (w / 2 - c, t / 2), (-w / 2 + c, t / 2), (-w / 2, t / 2 - c), (-w / 2, -t / 2 + c),
           (-w / 2 + c, -t / 2), (w / 2 - c, -t / 2), (w / 2, -t / 2 + c)]
    return [centre + (x * px + y * py) * CM for px, py in pts]


def leg_at(a: float, h: float) -> Vector:
    return polar(a, leg_s(a, h), h)


def leg_prism(bm, a: float, h0: float, h1: float, size0: list, size1: list) -> None:
    """An octagonal prism along the leg's axis from h0 to h1, cut square to the axis."""
    _r, tang, axis, out = leg_basis(a)
    p0, p1 = leg_at(a, h0), leg_at(a, h1)
    loft(bm, octagon(p0, tang, out, *size0), octagon(p1, tang, out, *size1))


def build_struts(bm) -> None:
    for a in LEG_ANGLES:
        (w0, t0), (w1, t1) = LG["strut_size"]
        leg_prism(bm, a, LG["strut"][0], LG["strut"][1], [w0, t0], [w1, t1])
        (w0, t0), (w1, t1) = LG["sleeve_size"]
        leg_prism(bm, a, LG["sleeve"][0], LG["sleeve"][1], [w0, t0], [w1, t1])


def build_glands(bm) -> None:
    """The graphite glands where the rod leaves the strut and enters the ankle's sleeve, and the hip brackets."""
    for a in LEG_ANGLES:
        (w0, t0), _ = LG["strut_size"]
        g0, g1 = LG["gland"]
        leg_prism(bm, a, g0, g1, [w0 + 1.0, t0 + 1.0], [w0 + 1.0, t0 + 1.0])
        (_w, _t), (w1, t1) = LG["sleeve_size"]
        h = LG["sleeve"][1]
        leg_prism(bm, a, h - 0.6, h + 1.0, [w1 + 0.9, t1 + 0.9], [w1 + 0.9, t1 + 0.9])
        radial, tang, _axis, _out = leg_basis(a)
        basis = Matrix((tang, radial, Vector((0.0, 0.0, 1.0)))).transposed()
        box(bm, polar(a, LG["hip"][0] + 0.5, BA["bottom"] - 1.4), (17.0 * CM, 15.0 * CM, 3.4 * CM), basis)


def build_rods(bm) -> None:
    for a in LEG_ANGLES:
        _r, _t, axis, _o = leg_basis(a)
        p0, p1 = leg_at(a, LG["rod"][0]), leg_at(a, LG["rod"][1])
        length = (p1 - p0).length / CM
        disc(bm, [(LG["rod_r"], 0.0), (LG["rod_r"], length)], p0, axis, 16)


def pad_square(a: float, w: float, h: float) -> list:
    radial, tang, _axis, _out = leg_basis(a)
    c = polar(a, pad_s(a), h)
    return [c + (radial * x + tang * y) * (w / 2) * CM for x, y in ((1, -1), (1, 1), (-1, 1), (-1, -1))]


def build_pads(bm) -> None:
    """The feet: a square plinth, then a faceted taper to the top the sleeve stands on."""
    foot, top, plinth, top_h = LG["pad"]
    for a in LEG_ANGLES:
        rings = [[bm.verts.new(p) for p in pad_square(a, w, h)]
                 for w, h in ((foot, 0.0), (foot, plinth), (top, top_h), (top - 1.6, top_h + 0.6))]
        ring_faces(bm, rings)


def build_leg_lights(bm) -> None:
    """The amber slot on each strut's outer face; two amber bars on each pad's outer and side faces."""
    foot, top, plinth, top_h = LG["pad"]
    h0, h1, w = LG["strut_light"]
    (_w0, t0), (_w1, t1) = LG["strut_size"]
    s0, s1 = LG["strut"]
    for a in LEG_ANGLES:
        radial, tang, axis, out = leg_basis(a)

        def t_at(h: float) -> float:
            return t0 + (t1 - t0) * (h - s0) / (s1 - s0)
        segment_light(bm, leg_at(a, h0) + out * (t_at(h0) / 2) * CM, leg_at(a, h1) + out * (t_at(h1) / 2) * CM,
                      out, w)
        c = polar(a, pad_s(a), 0.0)
        rise, run = top_h - plinth, (foot - top) / 2
        for side in (radial, tang, -tang):
            normal = (side * rise + Vector((0.0, 0.0, run))).normalized()
            along = Vector((0.0, 0.0, 1.0)).cross(side).normalized()
            for hb, bw in LG["pad_bars"]:
                off = foot / 2 - run * (hb - plinth) / rise
                half_w = off - 1.6
                centre = c + side * off * CM + Vector((0.0, 0.0, hb * CM))
                light_box(bm, centre, normal, along, 2 * half_w - 1.2, bw, 3, proud=0.5, inset=0.3)


# --- parts, materials, assembly ------------------------------------------------------------------------------------
FEATURES: list = []
MATS: dict = {}
CYAN = (0.0, 0.62, 1.0, 1.0)
AMBER = (1.0, 0.3, 0.0, 1.0)  # deep: AgX pales a bright amber to white (b2)


def record_features(name: str, bm) -> None:
    limit = math.radians(30.0)
    for e in bm.edges:
        faces = list(e.link_faces)
        if len(faces) == 2 and faces[0].normal.angle(faces[1].normal, 0.0) < limit:
            continue
        FEATURES.append([name, [round(c / CM, 3) for c in e.verts[0].co], [round(c / CM, 3) for c in e.verts[1].co],
                         [[round(c, 3) for c in f.normal] for f in faces]])


def part(name: str, build, mat: str, bevel: bool = True, cut: float | None = None, small: bool = False,
         drawn: bool = True) -> bpy.types.Object:
    """One part: its material in slot 0, the broad chamfer's marker in 1, the edge bevel's in 2, amber light 3,
    cyan light 4. cut: cut at the back, that far off the wall (cm)."""
    bm = bmesh.new()
    build(bm)
    if cut is not None:
        cut_back(bm, cut)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if drawn:
        record_features(name, bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    for m in (mat, "_broad", "_edge", "charger_amber", "charger_cyan"):
        me.materials.append(MATS[m])
    if bevel:
        widths = ((0.0045 if small else BA["chamfer"] * CM, 1), (0.0012 if small else BA["edge"] * CM, 2))
        for i, (w, slot) in enumerate(widths):
            mod = ob.modifiers.new(f"bevel{i}", "BEVEL")
            mod.width = w
            mod.segments = 1
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(30.0 if i == 0 else 20.0)
            mod.material = slot
            mod.harden_normals = False
            mod.use_clamp_overlap = True
    return ob


class Nodes:
    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()

    def n(self, kind: str, **inputs):
        node = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            self.set(node, k, v)
        return node

    def set(self, node, key, v):
        sock = node.inputs[key]
        if hasattr(v, "bl_idname") or isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v if isinstance(v, bpy.types.NodeSocket) else v.outputs[0], sock)
        else:
            sock.default_value = v

    def math(self, op: str, a, b=0.0):
        m = self.n("ShaderNodeMath")
        m.operation = op
        self.set(m, 0, a)
        self.set(m, 1, b)
        return m.outputs[0]

    def output(self, shader):
        o = self.n("ShaderNodeOutputMaterial")
        self.nt.links.new(shader if isinstance(shader, bpy.types.NodeSocket) else shader.outputs[0], o.inputs[0])


def metal_material(name: str, base, worn, rough: float, metallic: float):
    """The console's metal (console_build.metal_material): the bright edge where UV0 u > 0, a mottle, a grain."""
    mat = bpy.data.materials.new(name)
    nd = Nodes(mat)
    uv = nd.n("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    sep = nd.n("ShaderNodeSeparateXYZ")
    nd.nt.links.new(uv.outputs[0], sep.inputs[0])
    flag = sep.outputs[0]
    tc = nd.n("ShaderNodeTexCoord")
    noise = nd.n("ShaderNodeTexNoise", Scale=22.0, Detail=4.0)
    nd.nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    big = nd.n("ShaderNodeTexNoise", Scale=3.5, Detail=2.0)
    nd.nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    wear = nd.math("MINIMUM", nd.math("MULTIPLY", flag, nd.math("ADD", nd.math("MULTIPLY", noise.outputs[0], 0.5), 0.6)), 1.0)
    shade = nd.math("ADD", nd.math("MULTIPLY", big.outputs[0], 0.25), 0.88)
    mix = nd.n("ShaderNodeMix")
    mix.data_type = "RGBA"
    nd.set(mix, 0, wear)
    nd.set(mix, 6, base)
    nd.set(mix, 7, worn)
    sc = nd.n("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nd.nt.links.new(mix.outputs[2], sc.inputs[0])
    nd.set(sc, "Scale", shade)
    r = nd.math("SUBTRACT", nd.math("ADD", rough, nd.math("SUBTRACT", nd.math("MULTIPLY", noise.outputs[0], 0.14), 0.07)),
                nd.math("MULTIPLY", wear, 0.14))
    b = nd.n("ShaderNodeBsdfPrincipled", Metallic=metallic)
    nd.nt.links.new(r, b.inputs["Roughness"])
    nd.nt.links.new(sc.outputs[0], b.inputs["Base Color"])
    nd.output(b)
    return mat


def emissive(name: str, colour, strength: float):
    mat = bpy.data.materials.new(name)
    nd = Nodes(mat)
    nd.output(nd.n("ShaderNodeBsdfPrincipled", **{"Base Color": (0.03, 0.03, 0.035, 1.0), "Roughness": 0.25,
                                                  "Emission Color": colour, "Emission Strength": strength}))
    return mat


def build_materials() -> None:
    MATS["charger_bronze"] = metal_material("charger_bronze", (0.56, 0.27, 0.10, 1.0), (1.0, 0.70, 0.40, 1.0), 0.34, 1.0)
    MATS["charger_graphite"] = metal_material("charger_graphite", (0.06, 0.062, 0.07, 1.0), (0.36, 0.35, 0.34, 1.0),
                                              0.38, 0.85)
    MATS["charger_steel"] = metal_material("charger_steel", (0.40, 0.42, 0.45, 1.0), (0.85, 0.86, 0.88, 1.0), 0.16,
                                           1.0)
    MATS["charger_amber"] = emissive("charger_amber", AMBER, 2.2)  # b5q: 6 / 9 bleached to salmon and white
    MATS["charger_cyan"] = emissive("charger_cyan", CYAN, 2.6)
    MATS["charger_lens"] = emissive("charger_lens", (0.05, 0.75, 1.0, 1.0), 5.0)
    MATS["_broad"] = bpy.data.materials.new("_broad")
    MATS["_edge"] = bpy.data.materials.new("_edge")


ORDER = ["charger_bronze", "charger_graphite", "charger_amber", "charger_cyan", "charger_lens", "charger_steel"]
FLAG = {"_broad": 0.45, "_edge": 1.0}


def facet_random(co: Vector) -> float:
    h = math.sin(co.x * 1271.1 + co.y * 3117.7 + co.z * 743.3) * 43758.5453
    return h - math.floor(h)


def join(name: str, objs: list, pivot: Vector) -> bpy.types.Object:
    """Applies the parts' bevels, writes UV0 (u: 0 face, 0.45 broad chamfer, 1 edge bevel; v: a per-face random), one
    shared slot list (ORDER), the origin at pivot."""
    deps = bpy.context.evaluated_depsgraph_get()
    bm_all = bmesh.new()
    stats = {}
    for ob in objs:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
        own = me.materials[0].name
        bm = bmesh.new()
        bm.from_mesh(me)
        uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            slot = me.materials[f.material_index].name
            u = FLAG.get(slot, 0.0)
            f.material_index = ORDER.index(own if slot in FLAG else slot)
            v = facet_random(f.calc_center_median())
            for lp in f.loops:
                lp[uv].uv = (u, v)
        bmesh.ops.translate(bm, verts=bm.verts, vec=-pivot)
        stats[ob.name] = sum(len(f.verts) - 2 for f in bm.faces)
        tmp = bpy.data.meshes.new("tmp")
        bm.to_mesh(tmp)
        bm.free()
        bm_all.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        bpy.data.meshes.remove(me)
    used = sorted({f.material_index for f in bm_all.faces})  # the GLB gets no empty primitives
    for f in bm_all.faces:
        f.material_index = used.index(f.material_index)
    me = bpy.data.meshes.new(name)
    bm_all.to_mesh(me)
    bm_all.free()
    for i in used:
        me.materials.append(MATS[ORDER[i]])
    for p in me.polygons:
        p.use_smooth = me.materials[p.material_index].name in ("charger_lens", "charger_steel")
    for ob in objs:
        bpy.data.objects.remove(ob)
    out = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(out)
    out.location = pivot
    out["part_triangles"] = json.dumps(stats)
    return out


def hull_object(name: str, points: list, parent, mesh_name: str | None = None) -> bpy.types.Object:
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    for v in [v for v in bm.verts if not v.link_faces]:
        bm.verts.remove(v)
    bmesh.ops.translate(bm, verts=bm.verts, vec=-parent.matrix_world.translation)
    me = bpy.data.meshes.new(mesh_name or name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.parent = parent
    ob.hide_render = True
    return ob


def colliders(body, ring) -> list:
    """Convex colliders: the base (both tiers to the deck), each outer prong, each leg (strut to pad); on the ring,
    each inner prong. Godot's importer turns `-convcolonly` nodes into static bodies."""
    out = []
    pts = [polar(5.0 * k, r, h) for k in range(72) for r, h in LOWER + UPPER]
    out.append(hull_object("crystal_charger_col0-convcolonly", pts, body))
    for i, a_mid in enumerate(SIDES):
        pts = [polar(a_mid + sx * half, r, h) for prof, half, _ in outer_pieces() for r, h in prof for sx in (-1, 1)]
        out.append(hull_object(f"crystal_charger_col{1 + i}-convcolonly", pts, body))
    foot, top, _plinth, top_h = LG["pad"]
    for i, a in enumerate(LEG_ANGLES):
        _r, tang, _axis, out_n = leg_basis(a)
        (w1, t1) = LG["strut_size"][1]
        pts = octagon(leg_at(a, BA["bottom"]), tang, out_n, w1, t1) + pad_square(a, foot, 0.0) + \
            pad_square(a, top, top_h)
        out.append(hull_object(f"crystal_charger_col{3 + i}-convcolonly", pts, body))
    th = DIMS["inner"]["half_deg"]
    for i, a_mid in enumerate(SIDES):
        pts = [polar(a_mid + sx * th, r, h) for prof in inner_pieces() for r, h in prof for sx in (-1, 1)]
        out.append(hull_object(f"track_ring_col{i}-convcolonly", pts, ring))
    return out


def build(crystal: str | None) -> dict:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    build_materials()
    body_parts = [
        part("core", build_core, "charger_graphite", bevel=False),
        part("lower", build_lower, "charger_bronze"),
        part("front_block", build_front_block, "charger_bronze"),
        part("facet", build_facet, "charger_bronze", small=True),  # b5: graphite read as a black hole in Godot
        part("button_seat", build_button_seat, "charger_graphite", small=True),
        part("upper", build_upper, "charger_bronze"),
        part("deck_ring", build_deck_ring, "charger_bronze", small=True),
        part("tier_lights", build_tier_lights, "charger_graphite", bevel=False, drawn=False),
        part("collar", build_collar, "charger_bronze", small=True),
        part("slot_glow", build_slot_glow, "charger_cyan", bevel=False, drawn=False),
        part("outer_prongs", build_outer_prongs, "charger_bronze"),
        part("prong_joints", build_prong_joints, "charger_graphite", small=True, drawn=False),
        part("outer_lights", build_outer_lights, "charger_graphite", bevel=False, drawn=False),
        part("struts", build_struts, "charger_bronze"),
        part("glands", build_glands, "charger_graphite", small=True),
        part("rods", build_rods, "charger_steel", bevel=False),
        part("pads", build_pads, "charger_bronze"),
        part("leg_lights", build_leg_lights, "charger_graphite", bevel=False, drawn=False),
    ]
    body = join("crystal_charger", body_parts, Vector((0.0, 0.0, 0.0)))
    c = DIMS["carrier"]
    carrier = join("carrier", [part("carrier_body", build_carrier, "charger_bronze", small=True),
                               part("carrier_light", build_carrier_light, "charger_cyan", bevel=False, drawn=False)],
                   P(0.0, AX, c["top"]))
    ring = join("track_ring", [part("ring", build_ring, "charger_bronze", small=True),
                               part("ring_light", build_ring_light, "charger_cyan", bevel=False, drawn=False),
                               part("inner_prongs", build_inner_prongs, "charger_bronze", small=True),
                               part("inner_lights", build_inner_lights, "charger_graphite", bevel=False, drawn=False),
                               part("electrodes", build_electrodes, "charger_cyan", bevel=False, drawn=False)],
                Vector(P(0.0, AX, BA["deck"])))
    b = DIMS["button"]
    button = join("button", [part("lens", build_button, "charger_lens", bevel=False, drawn=False)],
                  P(0.0, BUTTON_D, b["h"]))
    for leaf in (carrier, ring, button):
        loc = leaf.location.copy()
        leaf.parent = body
        leaf.location = loc
    anchor = bpy.data.objects.new("crystal_anchor", None)
    anchor.empty_display_type = "SINGLE_ARROW"
    anchor.empty_display_size = 0.05
    bpy.context.collection.objects.link(anchor)
    anchor.parent = carrier
    anchor.location = Vector((0.0, 0.0, (DIMS["slot"]["tip"] - c["top"]) * CM))
    bpy.context.view_layer.update()
    cols = colliders(body, ring)
    crystal_obs = []
    if crystal and Path(crystal).is_file():
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=crystal)
        crystal_obs = [o for o in bpy.data.objects if o not in before]
        for o in crystal_obs:
            if o.parent is None:
                m = o.matrix_world.copy()
                o.parent = anchor
                o.matrix_parent_inverse = Matrix.Identity(4)
                o.matrix_basis = m
    return {"body": body, "carrier": carrier, "ring": ring, "button": button, "anchor": anchor, "colliders": cols,
            "crystal": crystal_obs}


# --- checks --------------------------------------------------------------------------------------------------------
def bvh(obs: list) -> BVHTree:
    deps = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for ob in obs:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
        me.transform(ob.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def world_verts(ob) -> list:
    return [ob.matrix_world @ v.co for v in ob.data.vertices]


def checks(o: dict) -> dict:
    body, ring, carrier, button = o["body"], o["ring"], o["carrier"], o["button"]
    out = {}
    # the wall: every vertex's distance in front of the lens room's facets (the ring and inner prongs on a full turn)
    def wall_min(obs) -> float:
        return min(wall_dist(p.x / CM, -p.y / CM) for ob in obs for p in world_verts(ob))
    out["wall_min_cm_body"] = round(wall_min([body]), 3)
    turn = []
    body_tree = bvh([body])
    for k in range(0, 360, 5):
        ring.rotation_euler = (0.0, 0.0, math.radians(k))
        bpy.context.view_layer.update()
        hits = len(body_tree.overlap(bvh([ring])))
        turn.append([k, hits, round(wall_min([ring]), 3)])
    ring.rotation_euler = (0.0, 0.0, 0.0)
    out["ring_turn"] = {"steps_deg": 5, "overlaps": sum(t[1] for t in turn), "wall_min_cm": min(t[2] for t in turn),
                        "worst": [t for t in turn if t[1]][:6]}
    rise = []
    base = carrier.location.copy()
    ring_tree = bvh([ring])
    for k in range(0, 7):
        carrier.location = base + Vector((0.0, 0.0, k * CM))
        bpy.context.view_layer.update()
        t = bvh([carrier])
        rise.append([k, len(body_tree.overlap(t)), len(ring_tree.overlap(t))])
    carrier.location = base
    out["carrier_rise"] = {"overlaps": sum(r[1] + r[2] for r in rise), "steps": rise}
    bl = button.location.copy()
    button.location = bl + Vector((0.0, DIMS["button"]["travel"] * CM, 0.0))
    bpy.context.view_layer.update()
    out["button_pressed_overlaps"] = len(body_tree.overlap(bvh([button])))
    button.location = bl
    bpy.context.view_layer.update()
    if o["crystal"]:
        meshes = [c for c in o["crystal"] if c.type == "MESH"]
        for k in (0, 6):
            carrier.location = base + Vector((0.0, 0.0, k * CM))
            bpy.context.view_layer.update()
            ct = bvh(meshes)
            out[f"crystal_overlaps_rise{k}"] = {"body": len(body_tree.overlap(ct)), "ring": len(bvh([ring]).overlap(ct))}
            hi = max(p.z for c in meshes for p in world_verts(c))
            out[f"crystal_top_cm_rise{k}"] = round(hi / CM, 2)
        carrier.location = base
        bpy.context.view_layer.update()
    return out


def mesh_stats(ob) -> dict:
    me = ob.data
    tris = {}
    for p in me.polygons:
        n = me.materials[p.material_index].name
        tris[n] = tris.get(n, 0) + len(p.vertices) - 2
    return {"triangles": sum(tris.values()), "by_material": tris, "vertices": len(me.vertices),
            "parts": json.loads(ob["part_triangles"])}


def open_edges(ob) -> int:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return n


# --- export --------------------------------------------------------------------------------------------------------
PLAIN = {
    "charger_bronze": dict(base=(0.50, 0.30, 0.15, 1.0), metallic=1.0, rough=0.3),
    "charger_graphite": dict(base=(0.07, 0.072, 0.08, 1.0), metallic=0.85, rough=0.38),
    "charger_steel": dict(base=(0.55, 0.57, 0.6, 1.0), metallic=1.0, rough=0.18),
    "charger_amber": dict(base=(0.05, 0.03, 0.01, 1.0), metallic=0.0, rough=0.25, emit=AMBER[:3], strength=5.0),
    "charger_cyan": dict(base=(0.02, 0.05, 0.06, 1.0), metallic=0.0, rough=0.2, emit=CYAN[:3], strength=5.0),
    "charger_lens": dict(base=(0.05, 0.4, 0.6, 1.0), metallic=0.0, rough=0.15, emit=(0.05, 0.75, 1.0), strength=4.0),
}


def export(o: dict, out: Path) -> None:
    looks = {}
    plain = {}
    for name, s in PLAIN.items():
        mat = bpy.data.materials.new(name + "_plain")
        nd = Nodes(mat)
        b = nd.n("ShaderNodeBsdfPrincipled", **{"Base Color": s["base"], "Metallic": s["metallic"],
                                                "Roughness": s["rough"]})
        if "emit" in s:
            nd.set(b, "Emission Color", (*s["emit"], 1.0))
            nd.set(b, "Emission Strength", s["strength"])
        nd.output(b)
        plain[name] = mat
    meshes = [o["body"], o["carrier"], o["ring"], o["button"]]
    for ob in meshes:
        looks[ob.name] = list(ob.data.materials)
        for i, m in enumerate(ob.data.materials):
            ob.data.materials[i] = plain[m.name]
    for name, m in plain.items():
        MATS[name].name = name + "_look"
        m.name = name
    keep = set(meshes) | {o["anchor"]} | set(o["colliders"])
    for ob in bpy.context.scene.objects:
        ob.select_set(ob in keep)
    bpy.ops.export_scene.gltf(filepath=str(out / "crystal_charger.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_vertex_color="NONE", export_extras=False)
    for name, m in plain.items():
        m.name = name + "_plain"
        MATS[name].name = name
    for ob in meshes:
        for i, m in enumerate(looks[ob.name]):
            ob.data.materials[i] = m
    for m in plain.values():
        bpy.data.materials.remove(m)


# --- renders -------------------------------------------------------------------------------------------------------
# name: (yaw from the front, elevation, target (u, d, h cm), frame height cm, state)
VIEWS = {
    "hero": (-14.0, 12.0, (0.0, AX, 70.0), 196.0, "charged"),
    "hero_idle": (-14.0, 12.0, (0.0, AX, 70.0), 196.0, "idle"),
    "charging": (-30.0, 12.0, (0.0, AX, 114.0), 72.0, "charging"),
    "side_q": (-70.0, 14.0, (0.0, AX, 70.0), 196.0, "idle"),
    "cu_button": (-20.0, 6.0, (0.0, AX + 46.0, 75.9), 30.0, "idle"),
    "cu_facet": (18.0, 4.0, (0.0, AX + 44.0, 73.0), 46.0, "idle"),
    "cu_seams": (-58.0, 8.0, (-38.0, AX + 28.0, 78.0), 40.0, "idle"),
    "cu_deck": (-25.0, 58.0, (0.0, AX, 95.0), 62.0, "idle"),
    "cu_slot": (8.0, 70.0, (0.0, AX, 95.0), 28.0, "idle"),
    "cu_prong_root": (-35.0, 25.0, (-31.0, AX + 6.0, 100.0), 30.0, "idle"),
    "cu_prong_cap": (-35.0, 22.0, (-28.0, AX + 5.0, 134.0), 26.0, "idle"),
    "cu_prong_strips": (-18.0, 8.0, (-33.0, AX + 8.0, 116.0), 44.0, "idle"),
    "cu_inner_head": (25.0, 18.0, (-18.0, AX + 4.0, 117.0), 26.0, "charging"),
    "cu_hip": (-40.0, -8.0, (-30.0, AX + 25.0, 60.0), 40.0, "idle"),
    "cu_knee": (-40.0, 6.0, (-35.8, AX + 30.0, 36.0), 32.0, "idle"),
    "cu_feet": (-40.0, 16.0, (-44.0, AX + 37.0, 7.0), 40.0, "idle"),
    "cu_back_leg": (-55.0, 10.0, (-45.0, AX - 26.0, 24.0), 50.0, "idle"),
    "cu_low": (-30.0, 2.0, (0.0, AX, 45.0), 110.0, "idle"),
}
ORTHO = {"front": (0.0, 0.0, (0.0, 0.0, 75.0), 160.0), "side": (-90.0, 0.0, (0.0, 60.0, 75.0), 160.0),
         "top": (0.0, 90.0, (0.0, 55.0, 0.0), 160.0)}


def stage(samples: int, hdri: str | None) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    try:
        sc.eevee.use_raytracing = False  # b1: its reflections sparkled on the up-facing bronze (noise, not geometry)
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("studio")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    bg.inputs[0].default_value = (0.03, 0.04, 0.07, 1.0)
    if hdri and Path(hdri).is_file():
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri)
        ref = nt.nodes.new("ShaderNodeBackground")
        ref.inputs[1].default_value = 0.8
        nt.links.new(env.outputs[0], ref.inputs[0])
        path = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(ref.outputs[0], mix.inputs[1])
        nt.links.new(bg.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs[0])
    for name, loc, energy, colour, size in (("key", (-1.6, -2.2, 2.6), 380.0, (1.0, 0.95, 0.9), 1.2),
                                            ("fill", (1.8, -1.8, 1.4), 120.0, (0.85, 0.9, 1.0), 1.5),
                                            ("rim", (0.8, 1.4, 2.4), 160.0, (0.8, 0.85, 1.0), 1.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.color, ld.size = energy, colour, size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector((0.0, -0.3, 0.8)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    floor = bpy.data.meshes.new("floor")
    floor.from_pydata([(-4, -4, 0), (4, -4, 0), (4, 0, 0), (-4, 0, 0)], [], [(0, 1, 2, 3)])
    wall = bpy.data.meshes.new("wall")  # the lens room's two facets at the spot's vertex
    s, c = math.sin(FOLD), math.cos(FOLD)
    wall.from_pydata([(0, 0, 0), (2 * c, -2 * s, 0), (2 * c, -2 * s, 2.4), (0, 0, 2.4), (-2 * c, -2 * s, 0),
                      (-2 * c, -2 * s, 2.4)], [], [(0, 1, 2, 3), (4, 0, 3, 5)])
    fm = bpy.data.materials.new("floor")
    nd = Nodes(fm)
    nd.output(nd.n("ShaderNodeBsdfPrincipled", **{"Base Color": (0.05, 0.055, 0.07, 1.0), "Roughness": 0.45,
                                                  "Metallic": 0.4}))
    for me in (floor, wall):
        me.materials.append(fm)
        ob = bpy.data.objects.new(me.name, me)
        sc.collection.objects.link(ob)
    try:
        tree = bpy.data.node_groups.new("bloom", "CompositorNodeTree")
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = tree.nodes.new("CompositorNodeRLayers")
        gl = tree.nodes.new("CompositorNodeGlare")
        go = tree.nodes.new("NodeGroupOutput")
        for key, value in (("Type", "Bloom"), ("Threshold", 1.0), ("Strength", 0.5), ("Size", 0.5)):
            if key in gl.inputs:
                gl.inputs[key].default_value = value
        tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
        tree.links.new(gl.outputs["Image"], go.inputs[0])
        sc.compositing_node_group = tree
        sc.render.use_compositing = True
    except Exception as exc:  # noqa: BLE001 - an optional nicety of the review renders
        print(f"CHARGER bloom off: {exc}")
    cam = bpy.data.cameras.new("cam")
    cam.lens = 85.0
    cam.clip_start = 0.02
    co = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co


def set_state(o: dict, state: str) -> None:
    c = o["carrier"]
    base = P(0.0, AX, DIMS["carrier"]["top"])
    rise = state == "charging"
    c.location = base + Vector((0.0, 0.0, DIMS["carrier"]["rise"] * CM if rise else 0.0))
    c.rotation_euler = (0.0, 0.0, math.radians(20.0 if rise else 0.0))
    o["ring"].rotation_euler = (0.0, 0.0, math.radians(35.0 if rise else 0.0))
    for ob in o["crystal"]:
        ob.hide_render = state == "idle"
    bpy.context.view_layer.update()


def place_camera(co, yaw: float, elev: float, target: Vector, frame: float, ortho: bool) -> None:
    y, e = math.radians(yaw), math.radians(elev)
    direction = Vector((math.sin(y) * math.cos(e), -math.cos(y) * math.cos(e), math.sin(e)))
    if ortho:
        co.data.type = "ORTHO"
        co.data.ortho_scale = frame * CM
        co.location = target + direction * 6.0
    else:
        co.data.type = "PERSP"
        fov = 2.0 * math.atan(36.0 / (2.0 * co.data.lens))
        co.location = target + direction * (frame * CM * 0.5 / math.tan(fov * 0.5))
    if elev > 85.0:
        co.rotation_euler = (0.0, 0.0, 0.0)
    else:
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()


def shoot(o: dict, folder: Path, res: int) -> list:
    sc = bpy.context.scene
    co = sc.camera
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for name, (yaw, elev, (u, d, h), frame, state) in VIEWS.items():
        set_state(o, state)
        sc.render.resolution_x = res if not name.startswith("cu_") else int(res * 0.7)
        sc.render.resolution_y = sc.render.resolution_x
        place_camera(co, yaw, elev, P(u, d, h), frame, False)
        sc.render.filepath = str(folder / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        files.append(name)
    set_state(o, "idle")
    for name, (yaw, elev, (u, d, h), frame) in ORTHO.items():
        sc.render.resolution_x = sc.render.resolution_y = int(frame * PX_PER_CM)
        place_camera(co, yaw, elev, P(u, d, h), frame, True)
        sc.render.filepath = str(folder / f"ortho_{name}.png")
        bpy.ops.render.render(write_still=True)
        files.append(f"ortho_{name}")
    return files


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    o = build(a["crystal"])
    result = {"checks": checks(o)}
    for key in ("body", "carrier", "ring", "button"):
        result[key] = mesh_stats(o[key])
        result[key]["open_edges"] = open_edges(o[key])
        t = o[key].matrix_world.translation  # (u, d, h)
        result[key]["pivot_cm"] = [round(t.x / CM, 2), round(-t.y / CM, 2), round(t.z / CM, 2)]
    result["triangles"] = sum(result[k]["triangles"] for k in ("body", "carrier", "ring", "button"))
    t = o["anchor"].matrix_world.translation
    result["anchor_cm"] = [round(t.x / CM, 2), round(-t.y / CM, 2), round(t.z / CM, 2)]  # (u, d, h)
    result["colliders"] = [c.name for c in o["colliders"]]
    co = [o["body"].matrix_world @ v.co for v in o["body"].data.vertices]
    for leaf in ("ring",):
        co += world_verts(o[leaf])
    lo = [min(c[i] for c in co) for i in range(3)]
    hi = [max(c[i] for c in co) for i in range(3)]
    result["size_cm"] = {"u": [round(lo[0] / CM, 2), round(hi[0] / CM, 2)], "d": [round(-hi[1] / CM, 2),
                         round(-lo[1] / CM, 2)], "h": [round(lo[2] / CM, 2), round(hi[2] / CM, 2)]}
    export(o, out)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "crystal_charger.blend"))
    (out / "features.json").write_text(json.dumps({"edges": FEATURES}), encoding="utf-8")
    if a["render"]:
        stage(a["samples"], a["hdri"])
        result["renders"] = shoot(o, Path(a["render"]), a["res"])
    (out / "build.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("CHARGER_BUILD " + json.dumps({k: result[k] for k in ("triangles", "size_cm", "anchor_cm", "checks")}))


if __name__ == "__main__":
    main()
