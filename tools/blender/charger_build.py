"""The ship's crystal charger (art#263's stations; two, one on each lens room's aft wall), built from code in headless
Blender from its drawing, tools/blender/charger_dims.toml (centimetres; charger_drawing.py draws it). The driver
(charger_run.py) calls it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/charger_build.py -- \
      --out <dir> [--crystal <energy_crystal.glb>] [--render <dir>] [--res 900] [--samples 64] [--hdri <hdr>]

Blender axes: X = u (across, + to the right as you face it), -Y = d (out of the wall, glTF +Z), Z = h; the origin
on the floor at the wall's face under the crystal's axis (the spot's `at`).

- The faceted pedestal set into the lens room's alcove (lens room C, 2026-10-28; it replaced the stepped dome on
  four legs): in plan the back on the alcove's back panel (u +-44 at d 10), the sides to d 46, chamfers to the front
  face (u +-22 at d 68); a graphite plinth (h 0..10) and a bronze deck slab (h 86..99.1) overhanging it, the body
  between them five bronze plates in two courses on a graphite core (the seams show it). Each plate has two bevels:
  a broad chamfer (UV0 u 0.45) and a small bright bevel on its folds (UV0 u 1), which the metal brightens. The button
  (bezel and lens) on the front plate at h 75.9; cyan strips up the chamfers, an amber pair on the front, amber along
  the sides under the slab, in graphite bezels.
- The deck: the collar of the slot, the cyan slot ring, the fixed outer prongs on the u axis (the hero: an (r, h)
  claw profile swept round the axis: a root block, a column that bows out, a chunky cap hooking in, graphite joint
  plates; a cyan and an amber strip up the front face, amber up the inner face).
- The leaves (own objects, pivot on their axes, children of the body): `carrier` (the cup under the crystal with
  the pit for its point; rises 6 cm and spins; the empty `crystal_anchor` on it where the crystal's tip sits),
  `track_ring` (spins, carries the inner prong pair with their electrodes), `button` (presses 1 cm in toward -d, into the charger).
  Convex colliders `*-convcolonly`: the pedestal, the outer prongs; the inner prongs (on the ring).

Writes into --out: crystal_charger.glb (plain-PBR fallback), crystal_charger.blend (the look materials), build.json
(triangles, size, pivots, the anchor, colliders, the clearance checks: the alcove's back panel and cheeks, the
reach, the ring's full turn,
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
    """A point's distance (cm) in front of the alcove's back panel (lens room C: a flat chord at d FR["back"] across
    the spot's vertex, which hides the wall's fold there)."""
    return d - FR["back"]


def cheek_dist(u: float, d: float) -> float:
    """A point's distance (cm) inside the alcove's opening across u: its cheeks splay from FR["open"][0] at the back
    panel to [1] at the jambs' face (d [2])."""
    b, f, face = FR["open"]
    t = min(max((d - FR["back"]) / (face - FR["back"]), 0.0), 1.0)
    return b + (f - b) * t - abs(u)


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


# --- the pedestal --------------------------------------------------------------------------------------------------
# lens room C (art#263, 2026-10-28): the faceted pedestal set into the alcove, from the lens room's drawing (C.ped).
# Its plan outline (u, d), counter-clockwise from above: the back on the alcove's back panel, the +u side, the +u
# chamfer, the front, the -u chamfer, the -u side; LIPS the plinth's and the deck slab's overhang per edge (the back
# none).
OUTLINE = [(-BA["side"], FR["back"]), (BA["side"], FR["back"]), (BA["side"], BA["chamfer_d"]),
           (BA["front"], BA["front_d"]), (-BA["front"], BA["front_d"]), (-BA["side"], BA["chamfer_d"])]
LIPS = [0.0, BA["lip"][0], BA["lip"][1], BA["lip"][2], BA["lip"][1], BA["lip"][0]]


def offset(poly: list, offs: list) -> list:
    """A convex counter-clockwise (u, d) polygon with edge i (poly[i] -> poly[i+1]) moved offs[i] outward."""
    lines = []
    for i, (a, b) in enumerate(zip(poly, poly[1:] + poly[:1])):
        eu, ed = b[0] - a[0], b[1] - a[1]
        n = math.hypot(eu, ed)
        nu, nd = ed / n, -eu / n
        lines.append(((a[0] + nu * offs[i], a[1] + nd * offs[i]), (eu, ed)))
    out = []
    for i in range(len(lines)):
        (p, e), (q, f) = lines[i - 1], lines[i]
        den = e[0] * f[1] - e[1] * f[0]
        t = ((q[0] - p[0]) * f[1] - (q[1] - p[1]) * f[0]) / den
        out.append((p[0] + e[0] * t, p[1] + e[1] * t))
    return out


def block(bm, outline: list, h0: float, h1: float) -> list:
    """A vertical prism of a (u, d) outline from h0 to h1."""
    return loft(bm, [P(u, d, h0) for u, d in outline], [P(u, d, h1) for u, d in outline])


CORE = offset(OUTLINE, [0.0] + [-(BA["plate"] - 0.1)] * 5)  # the graphite core, just inside the plates
LIPPED = offset(OUTLINE, LIPS)


def build_core(bm) -> None:
    """The graphite core: the pedestal's body behind its plates (seen in the seams), the well's floor with the track
    ring's groove and the slot's bore."""
    s, rg = DIMS["slot"], DIMS["ring"]
    block(bm, CORE, BA["plinth"] - 0.2, BA["body"] + 0.2)
    well = BA["well"] - 0.3
    g0, g1 = rg["r0"] - rg["groove"], rg["r1"] + rg["groove"]
    floor = BA["well"] - rg["h"] - rg["groove"]
    r_wall = BA["well_r"] - 0.2
    prof = [(2.0, BA["body"]), (r_wall, BA["body"]), (r_wall, well), (g1, well), (g1, floor), (g0, floor), (g0, well),
            (s["collar"][0], well), (s["collar"][0], s["bore_bottom"]), (2.0, s["bore_bottom"])]
    lathe(bm, prof, 96)


def build_plinth(bm) -> None:
    block(bm, LIPPED, 0.0, BA["plinth"])


def plate_quads() -> list:
    """The five bronze plates round the core (0 the +u side, 1 the +u chamfer, 2 the front, 3 the -u chamfer, 4 the
    -u side): per plate its outer edge (a, b), its inner edge (a, b), trimmed by half a seam at each end (the seams
    show the core), and its outward normal (u, d)."""
    inner = offset(OUTLINE, [0.0] + [-BA["plate"]] * 5)
    out, s = [], SEAM * 0.5
    for i in range(1, 6):
        a, b = OUTLINE[i], OUTLINE[(i + 1) % 6]
        ia, ib = inner[i], inner[(i + 1) % 6]
        eu, ed = b[0] - a[0], b[1] - a[1]
        n = math.hypot(eu, ed)
        tu, td = eu / n, ed / n
        sa = 0.0 if i == 1 else s   # the side plates run to the back panel
        sb = 0.0 if i == 5 else s
        out.append(((a[0] + tu * sa, a[1] + td * sa), (b[0] - tu * sb, b[1] - td * sb),
                    (ia[0] + tu * sa, ia[1] + td * sa), (ib[0] - tu * sb, ib[1] - td * sb), (td, -tu)))
    return out


def build_plates(bm) -> None:
    """The body's plates in two courses (h plinth..band, band..body), the seams between them onto the core."""
    s = SEAM * 0.5
    for a, b, ia, ib, _n in plate_quads():
        for h0, h1 in ((BA["plinth"], BA["band"] - s), (BA["band"] + s, BA["body"])):
            block(bm, [ia, ib, b, a], h0, h1)


def build_deck(bm) -> None:
    """The deck slab (h body..deck) over the lipped outline, its well (r well_r) round the slot down to the well's
    floor: the outline and the well's circle sampled at the same angles round the axis (the outline's corners
    included), so its top is quads between them."""
    cu = [(u, d - AX) for u, d in LIPPED]
    corners = {round(math.degrees(math.atan2(u, d)), 4) for u, d in cu}
    angs = sorted(corners | {round(-180.0 + 3.75 * k, 4) for k in range(96)})
    angs = [a for a in angs if a in corners or all(abs(a - c) > 0.6 for c in corners)]

    def hit(a: float) -> tuple:
        du, dd = math.sin(math.radians(a)), math.cos(math.radians(a))
        best = None
        for p, q in zip(cu, cu[1:] + cu[:1]):
            eu, ed = q[0] - p[0], q[1] - p[1]
            den = du * ed - dd * eu
            if abs(den) < 1e-12:
                continue
            t = (p[0] * ed - p[1] * eu) / den
            s = (p[0] * dd - p[1] * du) / den
            if t > 0 and -1e-9 <= s <= 1 + 1e-9 and (best is None or t < best):
                best = t
        return du * best, AX + dd * best

    outer = [hit(a) for a in angs]
    rw = BA["well_r"]
    ring = [(rw * math.sin(math.radians(a)), AX + rw * math.cos(math.radians(a))) for a in angs]
    rings = [[bm.verts.new(P(u, d, h)) for u, d in pts] for pts, h in
             ((outer, BA["body"]), (outer, BA["deck"]), (ring, BA["deck"]), (ring, BA["well"] - 0.3))]
    ring_faces(bm, rings, closed=True)


BUTTON_PLATE = BA["front_d"]     # the bezel sits on the front plate's face
BUTTON_D = BUTTON_PLATE + 1.8    # the lens's face (the bezel's lip at +1.4): 69.95 with its dome, inside the reach


def build_button_seat(bm) -> None:
    """The button's bezel ring on the front plate (graphite, a bronze-bright lip)."""
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


def build_pedestal_lights(bm) -> None:
    """The strips on the plates: cyan up each chamfer's middle, an amber pair on the front's lower half, amber along
    each side under the deck slab (graphite bezels, the light inset; slot 3 amber, 4 cyan)."""
    li = DIMS["lights"]
    up = Vector((0.0, 0.0, 1.0))
    quads = plate_quads()
    for k in (1, 3):  # the chamfers
        a, b, _ia, _ib, (nu, nd) = quads[k]
        h0, h1 = li["chamfer_cyan"]
        light_box(bm, P((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (h0 + h1) / 2), Vector((nu, -nd, 0.0)), up, h1 - h0,
                  li["width"], 4)
    u, (h0, h1) = li["front_amber"]
    for sx in (-1.0, 1.0):
        light_box(bm, P(sx * u, BA["front_d"], (h0 + h1) / 2), Vector((0.0, -1.0, 0.0)), up, h1 - h0, li["width"], 3)
    (d0, d1), h = li["side_amber"]
    for k, sx in ((0, 1.0), (4, -1.0)):
        _a, _b, _ia, _ib, (nu, nd) = quads[k]
        light_box(bm, P(sx * BA["side"], (d0 + d1) / 2, h), Vector((nu, -nd, 0.0)), Vector((0.0, -1.0, 0.0)),
                  d1 - d0, li["width"], 3)


# --- the slot ------------------------------------------------------------------------------------------------------
def build_collar(bm) -> None:
    s = DIMS["slot"]
    rb, ro = s["collar"]
    h0, h1 = BA["well"] - 0.45, s["collar_top"]
    lathe(bm, [(rb, h0), (ro, h0), (ro, h1 - 0.5), (ro - 0.5, h1), (rb + 0.4, h1), (rb, h1 - 0.4)], 48)


def build_slot_glow(bm) -> None:
    r0, r1 = DIMS["slot"]["glow"]
    d = BA["well"]
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
    top, bot = BA["well"], BA["well"] - rg["h"]
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
    d = BA["well"]
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
        for prof in ([(26.4, 103.7), (39.8, 103.7), (39.8, 104.9), (26.4, 104.9)],
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
        top = i["column"][-1][1]  # the graphite plate in the joint under the head
        sweep(bm, [(17.4, top), (22.4, top), (22.4, top + 1.0), (17.4, top + 1.0)], a_mid, i["half_deg"] - 1.0, 3)


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


# --- parts, materials, assembly ------------------------------------------------------------------------------------
FEATURES: list = []
MATS: dict = {}
CYAN = (0.0, 0.5, 1.0, 1.0)
AMBER = (1.0, 0.26, 0.0, 1.0)  # deep: AgX pales a bright amber to white (b2)


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
    MATS["charger_bronze"] = metal_material("charger_bronze", (0.56, 0.27, 0.10, 1.0), (1.0, 0.70, 0.40, 1.0), 0.28, 1.0)
    MATS["charger_graphite"] = metal_material("charger_graphite", (0.06, 0.062, 0.07, 1.0), (0.36, 0.35, 0.34, 1.0),
                                              0.38, 0.85)
    MATS["charger_steel"] = metal_material("charger_steel", (0.40, 0.42, 0.45, 1.0), (0.85, 0.86, 0.88, 1.0), 0.16,
                                           1.0)
    MATS["charger_amber"] = emissive("charger_amber", AMBER, 1.6)  # b5q: 6 / 9 bleached to salmon and white
    # (b6: 1.6 under the darker studio and AgX Punchy; 2.6 to 3.4 read cream, flat salmon)
    MATS["charger_cyan"] = emissive("charger_cyan", CYAN, 2.4)
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
    """Convex colliders: the pedestal (the plinth's outline to the deck), each outer prong; on the ring,
    each inner prong. Godot's importer turns `-convcolonly` nodes into static bodies."""
    out = []
    pts = [P(u, d, h) for u, d in LIPPED for h in (0.0, BA["deck"])]
    out.append(hull_object("crystal_charger_col0-convcolonly", pts, body))
    for i, a_mid in enumerate(SIDES):
        pts = [polar(a_mid + sx * half, r, h) for prof, half, _ in outer_pieces() for r, h in prof for sx in (-1, 1)]
        out.append(hull_object(f"crystal_charger_col{1 + i}-convcolonly", pts, body))
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
        part("plinth", build_plinth, "charger_graphite"),
        part("plates", build_plates, "charger_bronze"),
        part("deck", build_deck, "charger_bronze"),
        part("button_seat", build_button_seat, "charger_graphite", small=True),
        part("pedestal_lights", build_pedestal_lights, "charger_graphite", bevel=False, drawn=False),
        part("collar", build_collar, "charger_bronze", small=True),
        part("slot_glow", build_slot_glow, "charger_cyan", bevel=False, drawn=False),
        part("outer_prongs", build_outer_prongs, "charger_bronze"),
        part("prong_joints", build_prong_joints, "charger_graphite", small=True, drawn=False),
        part("outer_lights", build_outer_lights, "charger_graphite", bevel=False, drawn=False),
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
                Vector(P(0.0, AX, BA["well"])))
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
    out["cheek_min_cm_body"] = round(min(cheek_dist(p.x / CM, -p.y / CM) for p in world_verts(body)), 3)
    out["reach_cm"] = round(max(-p.y / CM for ob in (body, ring, carrier, button) for p in world_verts(ob)), 3)
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
    "cu_button": (-20.0, 6.0, (0.0, BA["front_d"], 75.9), 30.0, "idle"),
    "cu_front": (18.0, 4.0, (0.0, BA["front_d"], 52.0), 70.0, "idle"),
    "cu_seams": (-50.0, 8.0, (-33.0, 57.0, 50.0), 40.0, "idle"),
    "cu_deck": (-25.0, 58.0, (0.0, AX, 95.0), 62.0, "idle"),
    "cu_slot": (8.0, 70.0, (0.0, AX, 95.0), 28.0, "idle"),
    "cu_prong_root": (-35.0, 25.0, (-31.0, AX + 6.0, 100.0), 30.0, "idle"),
    "cu_prong_cap": (-35.0, 22.0, (-28.0, AX + 5.0, 134.0), 26.0, "idle"),
    "cu_prong_strips": (-18.0, 8.0, (-33.0, AX + 8.0, 116.0), 44.0, "idle"),
    "cu_inner_head": (25.0, 18.0, (-18.0, AX + 4.0, 117.0), 26.0, "charging"),
    "cu_deck_edge": (-40.0, 12.0, (-30.0, 60.0, 92.0), 40.0, "idle"),
    "cu_plinth": (-40.0, 10.0, (-30.0, 60.0, 8.0), 40.0, "idle"),
    "cu_side": (-80.0, 8.0, (-44.0, 28.0, 60.0), 90.0, "idle"),
    "cu_low": (-30.0, 2.0, (0.0, AX, 45.0), 110.0, "idle"),
}
ORTHO = {"front": (0.0, 0.0, (0.0, 0.0, 75.0), 160.0), "side": (-90.0, 0.0, (0.0, 60.0, 75.0), 160.0),
         "top": (0.0, 90.0, (0.0, 40.0, 0.0), 160.0)}


def stage(samples: int, hdri: str | None) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    try:
        sc.eevee.use_raytracing = False  # b1: its reflections sparkled on the up-facing bronze (noise, not geometry)
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy"  # b6: plain AgX paled the amber to cream and the bronze to tan
    except TypeError:
        pass
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
        ref.inputs[1].default_value = 0.3  # b6: 0.8 washed the bronze to a pale studio tan
        nt.links.new(env.outputs[0], ref.inputs[0])
        path = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(ref.outputs[0], mix.inputs[1])
        nt.links.new(bg.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs[0])
    # b6: a darker, moodier studio so the strips glow (b5: key 380, fill 120 read as a washed studio)
    for name, loc, energy, colour, size in (("key", (-1.6, -2.2, 2.6), 230.0, (1.0, 0.93, 0.86), 1.0),
                                            ("fill", (1.8, -1.8, 1.4), 45.0, (0.7, 0.8, 1.0), 1.5),
                                            ("rim", (0.8, 1.4, 2.4), 200.0, (0.75, 0.85, 1.0), 0.8)):
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
        for key, value in (("Type", "Bloom"), ("Threshold", 0.75), ("Strength", 0.7), ("Size", 0.6)):  # b6: glow
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
