"""The ship's crystal charger (art#263's stations; two, one on each lens room's aft wall), built from code in headless
Blender from its drawing, tools/blender/charger_dims.toml (centimetres; charger_drawing.py draws it). The driver
(charger_run.py) calls it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/charger_build.py -- \
      --out <dir> [--crystal <energy_crystal.glb>] [--render <dir>] [--res 900] [--samples 64] [--hdri <hdr>]

Blender axes: X = u (across, + to the right as you face it), -Y = d (out of the wall, glTF +Z), Z = h; the origin
on the floor at the wall's face under the crystal's axis (the spot's `at`).

- The round base, cut at the back against the wall: the lower tier (a tapered skirt of blocks on the feet, then the
  straight drum band and its upper taper), the middle tier and its upper band with the deck's bevel; every tier a
  ring of bronze blocks round a graphite drum, each block a profile swept straight between two angles (flat chord
  faces), the joints between them thin dark seams (the drum shows there). Each block has two bevels: a broad
  chamfer (UV0 u 0.45) and a small bright bevel on its folds (UV0 u 1), which the metal brightens (the sheet's worn
  edges). The back is cut by two planes 2 cm off the lens room's wall facets (the spot is on a facet vertex).
- The front: the drum's tall graphite facet with its amber light, and the middle tier's panel with the start button,
  each a trapezoid recess between bronze wedge blocks; the amber and cyan slots in graphite bezels on the blocks.
- The deck: the graphite deck, the collar and bore of the slot, the fixed outer prongs (column, bend, cap; cyan and
  amber strips in bezels on their fronts, amber on their inner faces), three feet with amber slots.
- The leaves (own objects, pivot on their axes, children of the body): `carrier` (rises 6 cm and spins; the empty
  `crystal_anchor` on it where the crystal's tip sits), `track_ring` (spins, carries the inner prong pair with
  their electrodes), `button` (presses 1 cm in along +d). Convex colliders `*-convcolonly` for the body (base, feet,
  outer prongs) and the inner prongs (on the ring).

Writes into --out: crystal_charger.glb (plain-PBR fallback), crystal_charger.blend (the look materials), build.json
(triangles, size, pivots, the anchor, colliders, the clearance checks: the wall, the ring's full turn, the carrier's
rise), features.json (the blocks' edges for the drawing). With --render: the review renders into that folder
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
FR, TI, BL = DIMS["frame"], DIMS["tiers"], DIMS["blocks"]
AX = FR["axis_d"]
SEAM = TI["seam"]
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
    s = DIMS["strips"]
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


def cut_back(bm, gap: float) -> None:
    """Cuts away everything closer than gap cm to the lens room's wall (its two facets), closing each cut."""
    for side in (1.0, -1.0):
        no = Vector((-side * math.sin(FOLD) * CM, -math.cos(FOLD) * CM, 0.0)).normalized()  # into the room
        co = no * (gap * CM)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-7, plane_co=co, plane_no=no, clear_inner=True)
        edges = [e for e in bm.edges if e.is_boundary]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)


# --- the tiers -----------------------------------------------------------------------------------------------------
def blocks(edges: list, front: float | None = None) -> list:
    """[(a0, a1)] both sides from a tier's block edges (deg, the first the front block's half angle)."""
    out = []
    if front is not None:
        out.append((-front, front))
    for a0, a1 in zip(edges, edges[1:]):
        out += [(a0, a1), (-a1, -a0)]
    return out


def tier_sectors(bm, edges: list, prof: list, r_seam: float, with_front: bool) -> None:
    g = seam_deg(r_seam)
    for a0, a1 in blocks(edges, edges[0] if with_front else None):
        sector(bm, a0 + g, a1 - g, prof)


def r_core(tier: str) -> float:
    return {"skirt": 45.5, "drum": 49.0, "middle": 43.5, "band": 42.5}[tier]


def build_core(bm) -> None:
    """The graphite drum inside the blocks (seen in the seams and under the skirt), the deck between the band and
    the ring's groove, the groove's floor, the bore's walls: one loop round the axis."""
    t, s, rg = TI, DIMS["slot"], DIMS["ring"]
    deck = t["deck"] - 0.15
    g0, g1 = rg["r0"] - rg["groove"], rg["r1"] + rg["groove"]
    floor = t["deck"] - rg["h"] - rg["groove"]
    prof = [(3.0, 0.0), (r_core("skirt"), 0.0), (r_core("skirt"), t["widest"] - 0.3), (r_core("drum"), t["widest"]),
            (r_core("drum"), t["widest_top"]), (47.0, t["rim"] - 0.3), (r_core("middle"), t["rim"] + 0.2),
            (r_core("middle"), t["band_split"] - 0.2), (r_core("band"), t["band_split"] + 0.2),
            (r_core("band"), deck), (g1, deck), (g1, floor), (g0, floor), (g0, deck),
            (s["collar_bore"] / 2, deck), (s["collar_bore"] / 2, s["bore_bottom"]), (3.0, s["bore_bottom"])]
    lathe(bm, prof, 96)


def build_skirt(bm) -> None:
    t = TI
    prof = [(r_core("skirt") - 2.0, t["bottom"]), (t["r_bottom"], t["bottom"]), (t["r_widest"], t["widest"]),
            (r_core("skirt") - 2.0, t["widest"])]
    tier_sectors(bm, BL["skirt"], prof, t["r_bottom"], False)


def r_drum(h: float) -> float:
    t = TI
    if h <= t["widest_top"]:
        return t["r_widest"]
    return t["r_widest"] + (t["r_lower_top"] - t["r_widest"]) * (h - t["widest_top"]) / (t["rim"] - t["widest_top"])


def build_drum(bm) -> None:
    t = TI
    prof = [(r_core("drum") - 2.0, t["widest"]), (t["r_widest"], t["widest"]), (t["r_widest"], t["widest_top"]),
            (t["r_lower_top"], t["rim"]), (r_core("drum") - 2.0, t["rim"])]
    tier_sectors(bm, BL["drum"], prof, t["r_widest"], False)


def build_middle(bm) -> None:
    t = TI
    prof = [(r_core("middle") - 2.0, t["rim"]), (t["r_tier2"], t["rim"]), (t["r_tier2"], t["band_split"]),
            (r_core("middle") - 2.0, t["band_split"])]
    tier_sectors(bm, BL["middle"], prof, t["r_tier2"], False)


def build_band(bm) -> None:
    t = TI
    prof = [(r_core("band") - 1.5, t["band_split"]), (t["r_tier2"], t["band_split"]), (t["r_tier2"], t["bevel"]),
            (t["r_deck"], t["deck"]), (r_core("band") - 1.5, t["deck"])]
    tier_sectors(bm, BL["band"], prof, t["r_tier2"], True)


def panel_pieces(bm, spec: dict, h0: float, h1: float, slope0: float, slope1: float) -> None:
    """A front panel block: bronze wedges either side of a trapezoid recess, a strip under and over it (sloped back
    by slope0 / slope1 cm at the block's foot / top), all with seams; flat front at r_face."""
    rf, half = spec["r_face"], spec["half_deg"]
    w = rf * math.tan(math.radians(half - seam_deg(rf)))
    (tw, th), (bw, bh) = spec["top"], spec["bottom"]
    d = AX + rf
    s = SEAM * 0.5
    depth = 9.0
    # the strip under the recess, sloped back at its foot
    lo = [(-w, h0), (w, h0), (w, bh - s), (-w, bh - s)]
    loft(bm, [P(u, d - depth, h) for u, h in lo],
         [P(u, d - (slope0 if h == h0 else 0.0), h) for u, h in lo])
    hi = [(-w, th + s), (w, th + s), (w, h1), (-w, h1)]
    loft(bm, [P(u, d - depth, h) for u, h in hi],
         [P(u, d - (slope1 if h == h1 else 0.0), h) for u, h in hi])
    for sx in (-1.0, 1.0):  # the wedges, each its outline counter-clockwise seen from the front
        out = [(sx * w, bh + s), (sx * (bw + s), bh + s), (sx * (tw + s), th - s), (sx * w, th - s)]
        if sx < 0:
            out = list(reversed(out))
        prism(bm, out, d, depth)


def recess_plate(bm, spec: dict) -> tuple:
    """The graphite plate at the bottom of a panel's recess; returns (its face's d, the trapezoid)."""
    (tw, th), (bw, bh) = spec["top"], spec["bottom"]
    d = AX + spec["r_face"] - spec["recess"]
    m = 1.2
    prism(bm, [(-bw - m, bh - m), (bw + m, bh - m), (tw + m, th + m), (-tw - m, th + m)], d, 5.0)
    return d


def build_lower_panel(bm) -> None:
    t, f = TI, DIMS["facet"]
    panel_pieces(bm, f, t["bottom"], t["rim"], f["r_face"] - t["r_bottom"], f["r_face"] - t["r_lower_top"])


def build_mid_panel(bm) -> None:
    t, p = TI, DIMS["panel"]
    panel_pieces(bm, p, t["rim"], t["band_split"], 0.0, 0.0)


def build_recesses(bm) -> None:
    """The two graphite recess plates: the drum's facet with its vertical amber light, the middle tier's panel."""
    f = DIMS["facet"]
    d = recess_plate(bm, f)
    w, h0, h1 = f["light"]
    light_box(bm, P(0.0, d, (h0 + h1) / 2), Vector((0, -1, 0)), Vector((0, 0, 1)), h1 - h0, w)
    recess_plate(bm, DIMS["panel"])


def build_button_seat(bm) -> None:
    """The button's bezel ring on the panel's recess plate (graphite, bronze lip); the lens's bore through it."""
    p, b = DIMS["panel"], DIMS["button"]
    d = AX + p["r_face"] - p["recess"]
    c = P(0.0, d, b["h"])
    n = Vector((0.0, -1.0, 0.0))
    rr, rl = b["ring"] / 2, b["lens"] / 2 + 0.25
    disc(bm, [(rl, -1.5), (rr, -1.5), (rr, 0.9), (rr - 0.5, 1.4), (rl + 0.4, 1.4), (rl, 1.1)], c, n, 40, closed=True)


def strip_frame(tier_edges: list, r_of, deg: tuple, h: float) -> tuple:
    """(centre, normal, up, length cm) of a strip between two angles at height h on the block holding them."""
    a0, a1 = next((a, b) for a, b in zip(tier_edges, tier_edges[1:]) if a <= deg[0] and deg[1] <= b)
    g = seam_deg(r_of(h))

    def chord(hh: float) -> tuple:
        p0, p1 = polar(a0 + g, r_of(hh), hh), polar(a1 - g, r_of(hh), hh)
        return p0, (p1 - p0).normalized()

    p0, along = chord(h)
    ends = []
    for a in deg:
        q = polar(a, r_of(h), h)
        ends.append(p0 + along * (q - p0).dot(along))
    lo, _ = chord(h - 0.5)
    hi, _ = chord(h + 0.5)
    up = (hi - lo)
    up = (up - along * up.dot(along)).normalized()
    normal = along.cross(up).normalized()
    if normal.dot(Vector((polar(0.5 * (a0 + a1), 1, 0) - polar(0, 0, 0)))) < 0:
        normal = -normal
    return (ends[0] + ends[1]) * 0.5, normal, up, along, (ends[1] - ends[0]).length / CM


def build_slots(bm) -> None:
    """The amber and cyan slots on the round half, mirrored: graphite bezels, the light inset (slot 3 amber, 4 cyan)."""
    s, t = DIMS["strips"], TI
    jobs = [("lower_cyan", BL["drum"], r_drum, s["lower_cyan"], 4, False),
            ("lower_amber", BL["drum"], r_drum, s["lower_amber"], 3, True),
            ("mid_amber", BL["middle"], lambda h: t["r_tier2"], s["mid_amber"], 3, False)]
    jobs += [("deck_amber", BL["band"], lambda h: t["r_tier2"], x, 3, False) for x in s["deck_amber"]]
    for _name, edges, r_of, spec, light, vertical in jobs:
        h0, h1 = spec["h"]
        c, n, up, along, length = strip_frame(edges, r_of, tuple(spec["deg"]), (h0 + h1) / 2)
        for sx in (1.0, -1.0):
            m = (lambda v: Vector((sx * v.x, v.y, v.z)))  # noqa: E731 - the mirror across u 0
            if vertical:
                light_box(bm, m(c), m(n), m(up), h1 - h0, length, light)
            else:
                light_box(bm, m(c), m(n), m(along), length, h1 - h0, light)


def build_collar(bm) -> None:
    s, t = DIMS["slot"], TI
    ro, rb = s["collar_outer"] / 2, s["collar_bore"] / 2
    h0, h1 = t["deck"] - 0.2, s["collar_h"][1]
    lathe(bm, [(rb, h0), (ro, h0), (ro, h1 - 0.5), (ro - 0.5, h1), (rb + 0.4, h1), (rb, h1 - 0.4)], 48)


# --- the prongs and feet -------------------------------------------------------------------------------------------
def outer_pieces() -> list:
    o = DIMS["outer"]
    (b0, b1), s = o["split"], SEAM * 0.5
    deck = TI["deck"] - 0.15
    return [
        [(-42.7, deck), (-26.0, deck), (-26.0, b0 - s), (-42.7, b0 - s)],
        [(-42.7, b0 + s), (-25.5, b0 + s), (-20.0, 117.9), (-20.0, b1 - s), (-35.5, b1 - s), (-42.7, 117.9)],
        [(-35.5, b1 + s), (-20.0, b1 + s), (-20.0, 128.3), (-21.7, 130.1), (-31.4, 130.1), (-33.0, 129.1)],
    ]


def mirror_outline(pts: list) -> list:
    return [(-u, h) for u, h in reversed(pts)]


def build_outer_prongs(bm) -> None:
    o = DIMS["outer"]
    dz = o["depth"] / 2
    for sx in (1.0, -1.0):
        for pts in outer_pieces():
            pts = pts if sx < 0 else mirror_outline(pts)
            slab(bm, pts, AX - dz, AX + dz)


def build_prong_joints(bm) -> None:
    """Graphite plates in the outer prongs' joints (the seams read dark, never see-through), the prongs' feet."""
    o = DIMS["outer"]
    for sx in (1.0, -1.0):
        for h, u0, u1 in ((o["split"][0], -41.9, -25.0), (o["split"][1], -34.6, -20.8)):
            slab(bm, [(sx * u0, h - 0.6), (sx * u1, h - 0.6), (sx * u1, h + 0.6), (sx * u0, h + 0.6)]
                 if sx < 0 else [(sx * u1, h - 0.6), (sx * u0, h - 0.6), (sx * u0, h + 0.6), (sx * u1, h + 0.6)],
                 AX - o["depth"] / 2 + 1.2, AX + o["depth"] / 2 - 1.2)
        foot = [(-43.6, TI["deck"] - 0.15), (-25.2, TI["deck"] - 0.15), (-25.2, TI["deck"] + 1.4), (-43.6, TI["deck"] + 1.4)]
        slab(bm, foot if sx < 0 else mirror_outline(foot), AX - o["depth"] / 2 - 0.9, AX + o["depth"] / 2 + 0.9)


def build_outer_lights(bm) -> None:
    """The outer prongs' strips: cyan and amber on their fronts (as the sheet's front view), amber on their inner
    faces toward the crystal."""
    o = DIMS["outer"]
    front, n = AX + o["depth"] / 2, Vector((0.0, -1.0, 0.0))
    b0, b1 = o["split"]
    for sx in (1.0, -1.0):
        (cu, c0), (_, c1), (cu2, c2) = o["cyan"]
        au = o["amber"][0][0]
        segs = [((cu, c0), (cu, b0 - 1.4), 4, o["strip_w"][0]),
                ((cu + 0.35, c1 + 0.7), (cu2 + 1.0, b1 - 1.6), 4, o["strip_w"][0]),
                ((au, o["amber"][0][1]), (au, b0 - 1.4), 3, o["strip_w"][1])]
        for (u0, h0), (u1, h1), light, w in segs:  # traced on the left prong: -sx u is the right one's mirror
            segment_light(bm, P(-sx * u0, front, h0), P(-sx * u1, front, h1), n, w, light)
        # the inner face (u -26 on the left), toward the crystal
        nu = Vector((-sx, 0.0, 0.0))
        segment_light(bm, P(sx * 26.0, AX, TI["deck"] + 4.0), P(sx * 26.0, AX, b0 - 2.5), nu, 1.3, 3)


def inner_pieces() -> list:
    i = DIMS["inner"]
    s = SEAM * 0.5
    sp = i["split"]
    deck = TI["deck"]
    return [
        [(-24.5, deck), (-16.8, deck), (-16.8, sp - s), (-24.5, sp - s)],
        [(-24.5, sp + s), (-16.4, sp + s), (-13.8, 109.6), (-13.8, 112.8), (-17.6, 113.7), (-21.9, 112.6), (-24.5, 109.4)],
    ]


def build_inner_prongs(bm) -> None:
    i = DIMS["inner"]
    for sx in (1.0, -1.0):
        for pts in inner_pieces():
            slab(bm, pts if sx < 0 else mirror_outline(pts), AX - i["thick"] / 2, AX + i["thick"] / 2)
        j = [(-24.0, i["split"] - 0.6), (-17.2, i["split"] - 0.6), (-17.2, i["split"] + 0.6), (-24.0, i["split"] + 0.6)]
        slab(bm, j if sx < 0 else mirror_outline(j), AX - i["thick"] / 2 + 1.0, AX + i["thick"] / 2 - 1.0)


def build_inner_lights(bm) -> None:
    i = DIMS["inner"]
    front, n = AX + i["thick"] / 2, Vector((0.0, -1.0, 0.0))
    for sx in (1.0, -1.0):
        (u, h0), (_, h1) = i["amber"]
        segment_light(bm, P(-sx * u, front, h0), P(-sx * u, front, h1), n, i["amber_w"], 3)


def build_electrodes(bm) -> None:
    eu, eh, er = DIMS["inner"]["electrode"]
    front = AX + DIMS["inner"]["thick"] / 2
    for sx in (1.0, -1.0):
        c = P(sx * abs(eu), front - 0.3, eh)
        res = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=er * CM)
        for v in res["verts"]:
            v.co += c


def build_ring(bm) -> None:
    """The track ring: an inner and an outer course of bronze blocks (offset joints) either side of the cyan
    channel, a graphite band under them."""
    rg, t = DIMS["ring"], TI
    top, bot = t["deck"], t["deck"] - rg["h"]
    (l0, l1) = rg["light"]
    n = 16
    half = 180.0 / n
    for (r0, r1), rot in (((rg["r0"] / math.cos(math.radians(half)), l0), 0.0), ((l1, rg["r1"]), half)):
        g = seam_deg(r1)
        for k in range(n):  # b1: 8 blocks of 45 deg put the inner chords' middles 1 cm into the groove's wall
            a0, a1 = rot + 2 * half * k, rot + 2 * half * (k + 1)
            sector(bm, a0 + g, a1 - g, [(r0, bot), (r1, bot), (r1, top), (r0, top)])
    lathe(bm, [(rg["r0"] + 0.5, bot - 0.1), (rg["r1"] - 0.6, bot - 0.1), (rg["r1"] - 0.6, top - 1.0),
               (rg["r0"] + 0.5, top - 1.0)], 64)


def build_ring_light(bm) -> None:
    rg, t = DIMS["ring"], TI
    l0, l1 = rg["light"]
    lathe(bm, [(l0 - 0.05, t["deck"] - 1.2), (l1 + 0.05, t["deck"] - 1.2), (l1 + 0.05, t["deck"] - 0.45),
               (l0 - 0.05, t["deck"] - 0.45)], 96)


def build_carrier(bm) -> None:
    c = DIMS["carrier"]
    r, top, bot = c["d"] / 2, c["top"], c["top"] - c["h"]
    lathe(bm, [(0.5, bot), (r - 0.3, bot), (r, bot + 0.3), (r, top - 0.6), (r - 0.6, top), (0.5, top)], 40)
    lathe(bm, [(0.01, top - 0.3), (4.4, top - 0.3), (4.4, top + 0.2), (0.01, top + 0.2)], 6, rot=30.0)


def build_carrier_light(bm) -> None:
    c = DIMS["carrier"]
    lathe(bm, [(5.0, c["top"] - 0.1), (6.2, c["top"] - 0.1), (6.2, c["top"] + 0.06), (5.0, c["top"] + 0.06)], 48)


def build_button(bm) -> None:
    """The cyan lens: a short drum in the bezel's bore, its face at face_d (the drawing's d 73.3)."""
    b = DIMS["button"]
    c = P(0.0, b["face_d"], b["h"])
    n = Vector((0.0, -1.0, 0.0))
    r = b["lens"] / 2
    disc(bm, [(r, -0.7), (r, -0.4), (r - 0.4, 0.0), (0.01, 0.15)], c, n, 32)


def foot_outline(angle: float) -> tuple:
    f = DIMS["foot"]

    def at(r: float, s: float, h: float) -> Vector:
        a = math.radians(angle)
        return P(r * math.sin(a) + s * math.cos(a), AX + r * math.cos(a) - s * math.sin(a), h)

    def w(r: float) -> float:
        return 0.5 * (f["w_top"] + (f["w_bottom"] - f["w_top"]) * (r - f["r0"]) / (f["reach"] - f["r0"]))

    prof = [(f["r0"], 0.0), (f["reach"], 0.0), (f["reach"], f["face"]), (f["r_top0"], f["top"]), (f["r0"], f["top"])]
    return [at(r, -w(r), h) for r, h in prof], [at(r, w(r), h) for r, h in prof], at


def build_feet(bm) -> None:
    for a in DIMS["foot"]["angles"]:
        left, right, _at = foot_outline(a)
        loft(bm, left, right)


def build_foot_lights(bm) -> None:
    f = DIMS["foot"]
    w, h0, h1 = f["slot"]
    for a in f["angles"]:
        _l, _r, at = foot_outline(a)
        c = at(f["reach"], 0.0, (h0 + h1) / 2)
        n = (at(f["reach"] + 1.0, 0.0, 0.0) - at(f["reach"], 0.0, 0.0)).normalized()
        # b3: the default bezel stood 0.9 out of the face, 90.2 cm from the wall, past the spot's 90
        light_box(bm, c, n, Vector((0, 0, 1)), h1 - h0, w, proud=0.4, inset=0.3)


# --- parts, materials, assembly ------------------------------------------------------------------------------------
FEATURES: list = []
MATS: dict = {}
CYAN = (0.0, 0.62, 1.0, 1.0)
AMBER = (1.0, 0.22, 0.0, 1.0)  # deep: AgX pales a bright amber to white (b2)


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
        widths = ((0.0045 if small else BL["chamfer"] * CM, 1), (0.0012 if small else BL["edge"] * CM, 2))
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
    MATS["charger_amber"] = emissive("charger_amber", AMBER, 5.0)
    MATS["charger_cyan"] = emissive("charger_cyan", CYAN, 7.0)
    MATS["charger_lens"] = emissive("charger_lens", (0.05, 0.75, 1.0, 1.0), 5.0)
    MATS["_broad"] = bpy.data.materials.new("_broad")
    MATS["_edge"] = bpy.data.materials.new("_edge")


ORDER = ["charger_bronze", "charger_graphite", "charger_amber", "charger_cyan", "charger_lens"]
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
        p.use_smooth = me.materials[p.material_index].name in ("charger_lens",)
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
    """Convex colliders: the base (the D-cut drum to the deck), each foot, each outer prong; on the ring, each inner
    prong. Godot's importer turns `-convcolonly` nodes into static bodies."""
    out = []
    pts = []
    t = TI
    for k in range(72):
        a = 5.0 * k
        for r, h in ((t["r_bottom"], t["bottom"]), (t["r_widest"], t["widest"]), (t["r_widest"], t["widest_top"]),
                     (t["r_lower_top"], t["rim"]), (t["r_tier2"], t["bevel"]), (t["r_deck"], t["deck"])):
            p = polar(a, r, h)
            if wall_dist(p.x / CM, -p.y / CM) >= FR["wall_gap"]:
                pts.append(p)
        for h in (0.0, t["bottom"]):
            p = polar(a, r_core("skirt"), h)
            if wall_dist(p.x / CM, -p.y / CM) >= FR["wall_gap"]:
                pts.append(p)
    for sx in (-1.0, 1.0):  # the back's corners on the wall facets
        for h in (0.0, t["deck"]):
            u = sx * 40.0
            d = (FR["wall_gap"] + abs(u) * math.sin(FOLD)) / math.cos(FOLD)
            pts.append(P(u, d, h))
    out.append(hull_object("crystal_charger_col0-convcolonly", pts, body))
    for i, a in enumerate(DIMS["foot"]["angles"]):
        left, right, _ = foot_outline(a)
        out.append(hull_object(f"crystal_charger_col{1 + i}-convcolonly", left + right, body))
    o = DIMS["outer"]
    for i, sx in enumerate((-1.0, 1.0)):
        pts = [P(sx * abs(u), d, h) for piece in outer_pieces() for u, h in piece
               for d in (AX - o["depth"] / 2, AX + o["depth"] / 2)]
        out.append(hull_object(f"crystal_charger_col{4 + i}-convcolonly", pts, body))
    th = DIMS["inner"]["thick"] / 2
    for i, sx in enumerate((-1.0, 1.0)):
        pts = [P(sx * abs(u), d, h) for piece in inner_pieces() for u, h in piece for d in (AX - th, AX + th)]
        out.append(hull_object(f"track_ring_col{i}-convcolonly", pts, ring))
    return out


def build(crystal: str | None) -> dict:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    build_materials()
    gap, gap_b = FR["wall_gap"], FR["wall_gap"] + 0.4
    body_parts = [
        part("core", build_core, "charger_graphite", bevel=False, cut=gap),
        part("skirt", build_skirt, "charger_bronze", cut=gap_b),
        part("drum", build_drum, "charger_bronze", cut=gap_b),
        part("middle", build_middle, "charger_bronze", cut=gap_b),
        part("band", build_band, "charger_bronze", cut=gap_b),
        part("lower_panel", build_lower_panel, "charger_bronze"),
        part("mid_panel", build_mid_panel, "charger_bronze"),
        part("recesses", build_recesses, "charger_graphite", small=True),
        part("button_seat", build_button_seat, "charger_graphite", small=True),
        part("slots", build_slots, "charger_graphite", small=True, drawn=False),
        part("collar", build_collar, "charger_bronze", small=True),
        part("outer_prongs", build_outer_prongs, "charger_bronze"),
        part("prong_joints", build_prong_joints, "charger_graphite", small=True),
        part("outer_lights", build_outer_lights, "charger_graphite", small=True, drawn=False),
        part("feet", build_feet, "charger_bronze"),
        part("foot_lights", build_foot_lights, "charger_graphite", small=True, drawn=False),
    ]
    body = join("crystal_charger", body_parts, Vector((0.0, 0.0, 0.0)))
    c = DIMS["carrier"]
    carrier = join("carrier", [part("carrier_body", build_carrier, "charger_bronze", small=True),
                               part("carrier_light", build_carrier_light, "charger_cyan", bevel=False, drawn=False)],
                   P(0.0, AX, c["top"]))
    ring = join("track_ring", [part("ring", build_ring, "charger_bronze", small=True),
                               part("ring_light", build_ring_light, "charger_cyan", bevel=False, drawn=False),
                               part("inner_prongs", build_inner_prongs, "charger_bronze", small=True),
                               part("inner_lights", build_inner_lights, "charger_graphite", small=True, drawn=False),
                               part("electrodes", build_electrodes, "charger_cyan", bevel=False, drawn=False)],
                Vector(P(0.0, AX, TI["deck"])))
    b = DIMS["button"]
    button = join("button", [part("lens", build_button, "charger_lens", bevel=False, drawn=False)],
                  P(0.0, b["face_d"], b["h"]))
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
    "hero": (-14.0, 15.0, (0.0, 30.0, 70.0), 165.0, "charged"),
    "hero_idle": (-14.0, 15.0, (0.0, 30.0, 70.0), 165.0, "idle"),
    "charging": (-30.0, 12.0, (0.0, 30.0, 95.0), 90.0, "charging"),
    "side_q": (-70.0, 20.0, (0.0, 30.0, 70.0), 165.0, "idle"),
    "cu_button": (-20.0, 6.0, (0.0, 72.0, 70.0), 32.0, "idle"),
    "cu_facet": (16.0, 4.0, (0.0, 78.0, 36.0), 50.0, "idle"),
    "cu_seams": (-58.0, 8.0, (-38.0, 60.0, 52.0), 45.0, "idle"),
    "cu_band": (40.0, 30.0, (22.0, 66.0, 82.0), 40.0, "idle"),
    "cu_deck": (-25.0, 58.0, (0.0, 27.3, 86.0), 62.0, "idle"),
    "cu_prong_cap": (-35.0, 22.0, (-30.0, 30.0, 124.0), 24.0, "idle"),
    "cu_prong_strips": (-18.0, 8.0, (-32.0, 34.0, 102.0), 40.0, "idle"),
    "cu_inner_head": (25.0, 18.0, (-17.0, 30.0, 108.0), 22.0, "charging"),
    "cu_feet": (-50.0, 10.0, (-40.0, 55.0, 8.0), 50.0, "idle"),
    "cu_back": (-78.0, 10.0, (-46.0, 8.0, 50.0), 60.0, "idle"),
    "cu_slot": (8.0, 70.0, (0.0, 27.3, 86.0), 26.0, "idle"),
    "cu_panel_side": (-42.0, 6.0, (-22.0, 76.0, 40.0), 34.0, "idle"),
}
ORTHO = {"front": (0.0, 0.0, (0.0, 0.0, 68.0), 150.0), "side": (-90.0, 0.0, (0.0, 45.0, 68.0), 150.0),
         "top": (0.0, 90.0, (0.0, 45.0, 0.0), 150.0)}


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
