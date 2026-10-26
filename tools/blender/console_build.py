"""The ship engine's start console (art#263's stations; the engineer picked it on 2026-10-24): a round bronze and
graphite pedestal with the orange start button, three stage strips, two cyan strips and the hologram emitter, and
over it the hologram of the ship, built from code in headless Blender (no Meshy). The driver (console_run.py) calls
it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/console_build.py -- \
      --out <dir> --pieces <ship pieces dir> [--render <dir>] [--res 900] [--samples 64] [--views <concept dir>] \\
      [--hdri <studio HDRI for the metal's reflections>]

Blender axes: Z up, the front (the button) -Y (glTF: Y up, front +Z); the origin on the floor under the middle.

The shape is the drawing tools/blender/console_dims.toml (centimetres; console_drawing.py draws it):
- the plinth, the body and the rim: rings of bronze blocks round a graphite drum (the drum shows in the joints and in
  the dark rings between the parts); each block a swept profile with flat (chord) faces, every edge over 30 degrees a
  crisp chamfer (UV0 u = 1 there, so the material brightens it); the body's front block wide and flat for the button,
  a cyan channel either side of it;
- the button: a graphite seat and collar on the front block, the orange mushroom dome; the three stage strips in
  graphite bezels on the rim's front block;
- the emitter inside the rim's top: a graphite deck, the cyan ring in its groove, twelve plates, a raised collar and
  the glowing core, a soft light column up into the hologram;
- the hologram: the ship's own hull (the built pieces skin_top, skin_belly, skin_mouth, skin_cheeks and the three
  nozzle pods from <pieces>) at 1:16.3, its hall over the core at [hologram] disc_h, nose down 12 degrees toward the
  button, fixed to the ship's axes (its nose to the console's front, which faces the ship's mouth). Hollow: a faint
  see-through shell; lines cut from the hull's mesh (its outline, contours over its top, the keel, its long creases,
  a section grid over its top; the plates' own edges are left out, a dense grid of their own); and the rooms as one
  flat plan at the deck inside it, drawn bright: the hall's disc, the entrance channel to the nose, a band along each
  wing to the round tip disc with four order lamps on it (from the hall outward red, yellow, green, blue), and the
  three turbines. Every line is a thin three-sided tube, so it reads from every side.

The states are one mesh and three values (node group `console_state`; the game's look godot/console/console.gd):
`passed` the stage strips lit green (idle 1), `lit` the order lamp lit bright (-1 none; 0..3 the west wing from the
hall outward, 4..7 the east), `order` 1 while the order plays. UV0's v holds a strip's or a lamp's index (0..7) and
on the hologram's lines and shell their brightness.

Writes into --out: start_console.glb (the plain-PBR fallback, idle), start_console.blend (the look materials),
build.json (triangles per part and material, size), features.json (the blocks' edges for the drawing). With
--render, review renders into that folder: <state>_<view>.png, and the drawing's orthographic views
ortho_<front|side|top>.png at PX_PER_CM; with --views (the concept's straight views), concept_<front|side|top>.png
cut to the same frames, the body stretched as the drawing stretches it.
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

# --- sizes: the drawing (console_dims.toml, centimetres) ------------------------------------------------------------
DIMS = tomllib.loads((Path(__file__).with_name("console_dims.toml")).read_text(encoding="utf-8"))
CM = 0.01
CHAMFER_BLOCK, CHAMFER_SMALL = 0.009, 0.003
LIFT = [0.0]  # m: the raise the ship's pieces were built with ([deck] lift_m); the hologram takes it off again


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"out": None, "pieces": None, "render": None, "res": 900, "samples": 64, "views": None, "hdri": None,
           "lift": 0.0}
    i = 0
    while i < len(a):
        out[a[i].lstrip("-")] = a[i + 1]
        i += 2
    out["res"] = int(out["res"])
    out["samples"] = int(out["samples"])
    out["lift"] = float(out["lift"])
    LIFT[0] = out["lift"]
    return out


# --- mesh helpers --------------------------------------------------------------------------------------------------
def polar(angle_deg: float, r: float, z: float) -> Vector:
    """A point at angle_deg round the vertical axis (0 the front, -Y; + toward +X), radius r, height z (metres)."""
    a = math.radians(angle_deg)
    return Vector((r * math.sin(a), -r * math.cos(a), z))


def lathe(bm, prof: list, sides: int, rot_deg: float = 0.0, bottom: bool = True, top: bool = True,
          closed: bool = False) -> list:
    """A solid of revolution with flat sides: prof is [(r, z), ...] in metres from the bottom up (closed: a loop,
    the last point joined back to the first, no caps); returns the rings."""
    rings = [[bm.verts.new(polar(rot_deg + 360.0 * j / sides, r, z)) for j in range(sides)] for r, z in prof]
    if closed:
        rings.append(rings[0])
        bottom = top = False
    for i in range(len(rings) - 1):
        lo, hi = rings[i], rings[i + 1]
        for j in range(sides):
            k = (j + 1) % sides
            bm.faces.new((lo[j], lo[k], hi[k], hi[j]))
    if bottom:
        bm.faces.new(list(reversed(rings[0])))
    if top:
        bm.faces.new(rings[-1])
    return rings


def sector(bm, a0: float, a1: float, prof: list) -> list:
    """A block between angles a0 and a1 (degrees): the closed profile prof [(r, z), ...] (metres, counter-clockwise
    in the (r, z) plane) swept straight from a0 to a1, so every outer face is flat (a chord). Returns its faces."""
    ring0 = [bm.verts.new(polar(a0, r, z)) for r, z in prof]
    ring1 = [bm.verts.new(polar(a1, r, z)) for r, z in prof]
    faces = []
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i])))
    faces.append(bm.faces.new(list(reversed(ring0))))
    faces.append(bm.faces.new(ring1))
    return faces


def box(bm, centre: Vector, size: tuple, basis: Matrix) -> list:
    """A box about centre, size along basis's columns (x, y, z); returns its faces."""
    res = bmesh.ops.create_cube(bm, size=1.0)
    for v in res["verts"]:
        local = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        v.co = centre + basis @ local
    faces = list({f for v in res["verts"] for f in v.link_faces})
    for f in faces:
        f.normal_update()
    return faces


def disc_lathe(bm, prof: list, centre: Vector, basis: Matrix, sides: int) -> None:
    """A solid of revolution about basis's z column through centre: prof [(r, t), ...] (t along the axis)."""
    rings = []
    for r, t in prof:
        ring = []
        for j in range(sides):
            a = 2.0 * math.pi * j / sides
            ring.append(bm.verts.new(centre + basis @ Vector((r * math.cos(a), r * math.sin(a), t))))
        rings.append(ring)
    for i in range(len(rings) - 1):
        lo, hi = rings[i], rings[i + 1]
        for j in range(sides):
            k = (j + 1) % sides
            bm.faces.new((lo[j], lo[k], hi[k], hi[j]))
    bm.faces.new(list(reversed(rings[0])))
    if prof[-1][0] > 1e-6:
        bm.faces.new(rings[-1])


# --- the block layout ----------------------------------------------------------------------------------------------
LAY = DIMS["layout"]


def gap_deg(r_m: float) -> float:
    """Half the joint between two blocks as an angle at radius r_m (metres)."""
    return math.degrees(LAY["gap"] * 0.5 * CM / r_m)


def body_blocks() -> list:
    """The body's blocks [(a0, a1, kind)]: the front block, the two cyan channels, `segments` blocks round the back."""
    f, c, n = LAY["front_half"], LAY["channel_half"], int(LAY["segments"])
    step = (360.0 - 2.0 * c) / n
    out = [(-f, f, "front"), (f, c, "channel"), (-c, -f, "channel")]
    out += [(c + step * i, c + step * (i + 1), "block") for i in range(n)]
    return out


def ring_blocks() -> list:
    """The plinth's and the rim's blocks: the front block to the channels' middles, then `segments` round the back."""
    m, n = 0.5 * (LAY["front_half"] + LAY["channel_half"]), int(LAY["segments"])
    step = (360.0 - 2.0 * m) / n
    return [(-m, m, "front")] + [(m + step * i, m + step * (i + 1), "block") for i in range(n)]


def body_r(h_cm: float) -> float:
    """The body's vertex radius (cm) at height h_cm: its taper from r_bottom to r_top."""
    b = DIMS["body"]
    t = (h_cm - b["h0"]) / (b["h1"] - b["h0"])
    return b["r_bottom"] + (b["r_top"] - b["r_bottom"]) * t


def face_point(a0: float, a1: float, r_cm: float, h_cm: float, u_cm: float = 0.0) -> Vector:
    """A point on a block's flat face (the chord between a0 and a1 at vertex radius r_cm), u_cm across it from its
    middle (+ toward a1), at height h_cm; metres."""
    p0, p1 = polar(a0, r_cm * CM, h_cm * CM), polar(a1, r_cm * CM, h_cm * CM)
    mid = (p0 + p1) * 0.5
    across = (p1 - p0).normalized()
    return mid + across * (u_cm * CM)


def front_frame(h_cm: float) -> tuple:
    """The body's front block at h_cm: (the point on its face at u = 0, its outward normal, its up direction)."""
    f = LAY["front_half"]
    g = gap_deg(DIMS["body"]["r_bottom"] * CM)
    lo = face_point(-f + g, f - g, body_r(h_cm - 1.0), h_cm - 1.0)
    hi = face_point(-f + g, f - g, body_r(h_cm + 1.0), h_cm + 1.0)
    up = (hi - lo).normalized()
    out = Vector((0.0, -1.0, 0.0))
    out = (out - up * out.dot(up)).normalized()
    return (lo + hi) * 0.5, out, up


# --- the parts -----------------------------------------------------------------------------------------------------
FEATURES: list = []  # the pedestal's edges for the drawing: [part, [x, y, z] cm, [x, y, z] cm, [face normals]]


def record_features(name: str, bm, angle: float) -> None:
    """Keeps the edges the chamfer would bevel (folds over angle, and open edges), in centimetres, with their faces'
    normals: console_drawing.py projects them into the drawing's views."""
    limit = math.radians(min(angle, 30.0))
    for e in bm.edges:
        faces = list(e.link_faces)
        if len(faces) == 2 and faces[0].normal.angle(faces[1].normal, 0.0) < limit:
            continue
        FEATURES.append([name, [round(c / CM, 3) for c in e.verts[0].co], [round(c / CM, 3) for c in e.verts[1].co],
                         [[round(c, 3) for c in f.normal] for f in faces]])


IDX = "console_index"  # a face's strip or lamp index, or a line's brightness x 100


def part(name: str, build, mat_name: str, chamfer: float, angle: float = 30.0, more: tuple = (),
         drawn: bool = True) -> bpy.types.Object:
    """One part: its own material in slot 0, the chamfer marker in slot 1, `more` materials from slot 2 (a builder
    puts faces there by material_index); a builder may set the face int layer IDX."""
    bm = bmesh.new()
    bm.faces.layers.int.new(IDX)
    build(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if drawn:
        record_features(name, bm, angle)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(MATS[mat_name])
    me.materials.append(MATS["_chamfer"])
    for extra in more:
        me.materials.append(MATS[extra])
    if chamfer > 0:
        mod = ob.modifiers.new("chamfer", "BEVEL")
        mod.width = chamfer
        mod.segments = 1
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(angle)
        mod.material = 1
        mod.harden_normals = False
        mod.use_clamp_overlap = True
    return ob


def build_core(bm) -> None:
    c = DIMS["core"]
    lathe(bm, [(c["r"] * CM, c["h0"] * CM), (c["r"] * CM, c["h1"] * CM)], 48)


def build_bands(bm) -> None:
    """The dark rings in the joints between the plinth and the body and between the body and the rim (the
    concept's shadowed grooves), inside the front block's flat face too (its chord: 50.4 cm from the axis at its
    foot, 47.9 at its top; a ring outside it showed in front as a round lip, the engineer's review 2026-10-24)."""
    p, b, m = DIMS["plinth"], DIMS["body"], DIMS["rim"]
    for r, h0, h1 in ((49.8, p["h_top"] + 0.05, b["h0"] - 0.05), (47.4, b["h1"] + 0.05, m["h0"] - 0.05)):
        lathe(bm, [(r * CM, h0 * CM), (r * CM, h1 * CM)], 48)


def build_plinth(bm) -> None:
    p = DIMS["plinth"]
    prof = [(p["r_in"], 0.0), (p["r_bottom"], 0.0), (p["r_top"], p["h_chamfer"]), (p["r_chamfer"], p["h_top"]),
            (p["r_in"], p["h_top"])]
    for a0, a1, _kind in ring_blocks():
        g = gap_deg(p["r_top"] * CM)
        sector(bm, a0 + g, a1 - g, [(r * CM, z * CM) for r, z in prof])


def stave_profile(r_bottom: float, r_top: float) -> list:
    b = DIMS["body"]
    return [(b["r_in"], b["h0"]), (r_bottom - b["bevel_bottom"], b["h0"]), (r_bottom, b["h0"] + b["bevel_bottom"]),
            (r_top, b["h1"] - b["bevel_top"]), (r_top - b["bevel_top"], b["h1"]), (b["r_in"], b["h1"])]


def build_body(bm) -> None:
    b = DIMS["body"]
    for a0, a1, kind in body_blocks():
        if kind == "channel":
            continue
        g = gap_deg(b["r_bottom"] * CM)
        sector(bm, a0 + g, a1 - g, [(r * CM, z * CM) for r, z in stave_profile(b["r_bottom"], b["r_top"])])


def build_channels(bm) -> None:
    """The cyan strip either side of the button: a light bar in each channel, set back behind the staves' faces,
    between two graphite lips (material 2: the light)."""
    ch, b, core = DIMS["channels"], DIMS["body"], DIMS["core"]
    f, c = LAY["front_half"], LAY["channel_half"]
    for sign in (1.0, -1.0):
        a_mid = sign * 0.5 * (f + c)
        half = 0.5 * (c - f)
        g = gap_deg(b["r_bottom"] * CM)
        lip = math.degrees(0.6 * CM / (b["r_bottom"] * CM))
        r0, r1 = body_r(ch["h0"]) - ch["depth"], body_r(ch["h1"]) - ch["depth"]
        bar = [(core["r"] - 0.5, ch["h0"]), (r0, ch["h0"]), (r1, ch["h1"]), (core["r"] - 0.5, ch["h1"])]
        for face in sector(bm, a_mid - half + g + lip, a_mid + half - g - lip, [(r * CM, z * CM) for r, z in bar]):
            face.material_index = 2
        for lo, hi in ((a_mid - half + g, a_mid - half + g + lip), (a_mid + half - g - lip, a_mid + half - g)):
            lp = [(core["r"] - 0.5, ch["h0"] - 0.6), (r0 + 0.5, ch["h0"] - 0.6), (r1 + 0.5, ch["h1"] + 0.6),
                  (core["r"] - 0.5, ch["h1"] + 0.6)]
            sector(bm, lo, hi, [(r * CM, z * CM) for r, z in lp])


def build_rim(bm) -> None:
    m = DIMS["rim"]
    prof = [(m["r_in"], m["h0"]), (m["r_foot"], m["h0"]), (m["r"], m["h_face0"]), (m["r"], m["h_face1"]),
            (m["r_top"], m["h1"]), (m["r_in"], m["h1"])]
    for a0, a1, _kind in ring_blocks():
        g = gap_deg(m["r"] * CM)
        sector(bm, a0 + g, a1 - g, [(r * CM, z * CM) for r, z in prof])


def rim_front_frame() -> tuple:
    """The rim's front block: (its face's centre line point at h 0, the outward normal); its face is upright."""
    m = DIMS["rim"]
    a = 0.5 * (LAY["front_half"] + LAY["channel_half"]) - gap_deg(m["r"] * CM)
    p = face_point(-a, a, m["r"], 0.0)
    return p, Vector((0.0, -1.0, 0.0))


def build_strip_bezels(bm) -> None:
    """The three stage strips' graphite bezels on the rim's front block, each with the light inset into it
    (material 2) and the strip's index in IDX."""
    s = DIMS["strips"]
    idx = bm.faces.layers.int[IDX]
    p, out = rim_front_frame()
    basis = Matrix.Identity(3)  # x across, y along the face's normal (the box is symmetric), z up; never a mirror:
    # a mirrored basis turns the box's normals inward and the light ends on the hidden back face
    for i, (u0, u1) in enumerate(s["u"]):
        w, h = (u1 - u0) + 2.0 * s["bezel"], (s["h1"] - s["h0"]) + 2.0 * s["bezel"]
        centre = Vector((0.5 * (u0 + u1) * CM, p.y - 0.12 * CM, 0.5 * (s["h0"] + s["h1"]) * CM))
        faces = box(bm, centre, (w * CM, 0.9 * CM, h * CM), basis)
        front = max(faces, key=lambda f: f.normal.dot(out))
        res = bmesh.ops.inset_individual(bm, faces=[front], thickness=s["bezel"] * CM, depth=-s["depth"] * CM)
        front.material_index = 2
        front[idx] = i
        for f in res["faces"]:
            f[idx] = i


def build_button_seat(bm) -> None:
    """The graphite seat and collar of the start button on the body's front block: a flat round seat set into the
    face, the collar standing proud, its bore holding the dome."""
    btn = DIMS["button"]
    centre, out, up = front_frame(btn["h"])
    basis = Matrix((up.cross(out), up, out)).transposed()  # x across, y up, z outward
    seat, collar = btn["seat"] * 0.5 * CM, btn["collar"] * 0.5 * CM
    bore = btn["dome"] * 0.5 * CM + 0.0035
    disc_lathe(bm, [(seat, -0.012), (seat, 0.004), (seat - 0.004, 0.008), (0.0, 0.008)], centre, basis, 40)
    disc_lathe(bm, [(collar, 0.0), (collar, btn["collar_proud"] * CM - 0.004), (collar - 0.004,
               btn["collar_proud"] * CM), (bore + 0.002, btn["collar_proud"] * CM), (bore, btn["collar_proud"] * CM
               - 0.003), (bore, btn["dome_proud"] * CM - 0.004), (0.0, btn["dome_proud"] * CM - 0.004)],
               centre, basis, 40)


def build_button(bm) -> None:
    """The orange mushroom dome: a short stem out of the collar's bore, then the cap's rounded top."""
    btn = DIMS["button"]
    centre, out, up = front_frame(btn["h"])
    basis = Matrix((up.cross(out), up, out)).transposed()
    r = btn["dome"] * 0.5 * CM
    t0, t1 = btn["dome_proud"] * CM - 0.006, btn["proud"] * CM
    prof = [(r * 0.96, t0), (r, t0 + 0.004), (r, t0 + 0.009)]
    steps = 6
    cap = t1 - (t0 + 0.009)
    for k in range(1, steps + 1):  # a squashed quarter ellipse to the top
        a = 0.5 * math.pi * k / steps
        prof.append((r * math.cos(a), t0 + 0.009 + cap * math.sin(a)))
    disc_lathe(bm, prof, centre, basis, 32)


def build_deck(bm) -> None:
    """The emitter's graphite deck between the rim's blocks and the ring, and the ring's groove floor."""
    e, m = DIMS["emitter"], DIMS["rim"]
    ring_out = e["ring"] * 0.5 + e["ring_width"] * 0.5
    prof = [(m["r_in"] + 0.3, e["deck_h"] - 1.5), (m["r_in"] + 0.3, e["deck_h"] + 0.4),
            (ring_out + 0.6, e["deck_h"] + 0.4), (ring_out + 0.25, e["deck_h"]), (ring_out + 0.25, e["deck_h"] - 1.5)]
    lathe(bm, [(r * CM, z * CM) for r, z in reversed(prof)], 64, closed=True)


def build_ring(bm) -> None:
    """The cyan ring in its groove (the light)."""
    e = DIMS["emitter"]
    r0, r1 = (e["ring"] - e["ring_width"]) * 0.5 * CM, (e["ring"] + e["ring_width"]) * 0.5 * CM
    z = (e["deck_h"] - 0.3) * CM
    lathe(bm, [(r0, z - 0.004), (r1, z - 0.004), (r1, z), (r0, z)], 96, closed=True)


def build_plates(bm) -> None:
    """Twelve graphite plates inside the ring (their joints the radial seams of the concept's top view), the inner
    groove's floor under them."""
    e = DIMS["emitter"]
    r_in, r_out = e["collar_r"][1] + 1.2, e["plates_r"]
    prof = [(r_in, e["deck_h"] - 1.0), (r_out, e["deck_h"] - 1.0), (r_out, e["plates_h"] - 0.25),
            (r_out - 0.35, e["plates_h"]), (r_in + 0.35, e["plates_h"]), (r_in, e["plates_h"] - 0.25)]
    for k in range(12):
        a0, a1 = 15.0 + 30.0 * k, 15.0 + 30.0 * (k + 1)
        g = gap_deg(r_out * CM) * 0.6
        sector(bm, a0 + g, a1 - g, [(r * CM, z * CM) for r, z in prof])
    # the floor of the ring's groove and of the gap round the collar
    r_out = e["ring"] * 0.5 + e["ring_width"] * 0.5 + 0.3
    lathe(bm, [(r * CM, z * CM) for r, z in ((e["collar_r"][1] - 0.2, e["deck_h"] - 1.6), (r_out, e["deck_h"] - 1.6),
                                            (r_out, e["deck_h"] - 1.2), (e["collar_r"][1] - 0.2, e["deck_h"] - 1.2))],
          64, closed=True)


def build_collar(bm) -> None:
    """The raised graphite collar round the core."""
    e = DIMS["emitter"]
    r0, r1 = e["collar_r"]
    prof = [(r0, e["deck_h"] - 1.2), (r1, e["deck_h"] - 1.2), (r1, e["collar_h"] - 0.6), (r1 - 0.6, e["collar_h"]),
            (r0 + 0.5, e["collar_h"]), (r0, e["collar_h"] - 0.5)]
    lathe(bm, [(r * CM, z * CM) for r, z in prof], 48, closed=True)


def build_core_light(bm) -> None:
    """The glowing core: a shallow lens in the collar's bore."""
    e = DIMS["emitter"]
    r = e["core"] * 0.5
    prof = [(e["collar_r"][0] + 0.05, e["core_h"] - 0.8), (r, e["core_h"] - 0.1)]
    for k in range(1, 5):
        a = 0.5 * math.pi * k / 4
        prof.append((r * math.cos(a), e["core_h"] - 0.1 + 0.5 * math.sin(a)))
    lathe(bm, [(rr * CM, z * CM) for rr, z in prof], 48, bottom=True, top=False)


def build_beam(bm) -> None:
    """The soft light column from the core up into the hologram: an open cone (its index the height share x 100,
    read by the beam's fade)."""
    e = DIMS["emitter"]
    idx = bm.faces.layers.int[IDX]
    r0, r1 = e["core"] * 0.5 * CM, e["core"] * 1.2 * CM
    rings = 6
    prof = [(r0 + (r1 - r0) * (i / rings) ** 1.4, (e["core_h"] + 0.3 + (e["beam_top"] - e["core_h"] - 0.3) * i / rings)
             * CM) for i in range(rings + 1)]
    lathe(bm, prof, 32, bottom=False, top=False)
    for f in bm.faces:
        f[idx] = int(round(100.0 * ((f.calc_center_median().z / CM) - e["core_h"]) / (e["beam_top"] - e["core_h"])))


# --- the hologram --------------------------------------------------------------------------------------------------
HOLO = DIMS["hologram"]
SHIP_SPAN_M = 26.11                      # the built hull's span (skin_top's lens skins: x +-13.055)
HALL = Vector((0.0, 0.4, 0.0))           # the hall's centre in the pieces' frame (plan (0, -0.4); y = -plan y)
TIPS = [Vector((-10.5, -1.2, 0.0)), Vector((10.5, -1.2, 0.0))]  # the lens rooms (plan (-+10.5, 1.2))
HULL_PIECES = ("skin_top", "skin_belly", "skin_mouth", "skin_cheeks")
PODS = (("nozzle_pod_outer", (-3.0, 9.6, 2.0)), ("nozzle_pod_outer", (3.0, 9.6, 2.0)),
        ("nozzle_pod_mid", (0.0, 9.6, 2.55)))  # layouts/ship/exterior.toml place: plan (x, y), h
HULL_STATS: dict = {}


def holo_matrix() -> Matrix:
    """The pieces' frame (metres, the ship's nose +Y) -> the console's (metres): turned 180 degrees about Z (the nose
    to the console's front, -Y), the hall's centre over the core, the hull's middle height at disc_h, scaled so the
    span is [hologram] span, then leaned nose down by tilt about the hall's centre."""
    k = HOLO["span"] * CM / SHIP_SPAN_M
    move = Matrix.Translation(Vector((-HALL.x, -HALL.y, -HOLO["hull_mid_z"])))
    turn = Matrix.Rotation(math.pi, 4, "Z")
    tilt = Matrix.Rotation(math.radians(HOLO["tilt"]), 4, "X")
    lift = Matrix.Translation(Vector((0.0, 0.0, HOLO["disc_h"] * CM)))
    return lift @ tilt @ Matrix.Scale(k, 4) @ turn @ move


def import_glb(path: Path) -> list:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def hull_bmesh(pieces: Path) -> bmesh.types.BMesh:
    """The hull's skins in the pieces' frame as one welded mesh: the seam strips and the mouth's jambs left out (the
    plates' seams; the hologram draws its own lines)."""
    bm = bmesh.new()
    for name in HULL_PIECES:
        obs = import_glb(pieces / f"{name}.glb")
        for o in obs:
            mats = [m.name for m in o.data.materials if m] if o.type == "MESH" else []
            if o.type == "MESH" and not any(m.startswith(("ext_seam", "jamb")) for m in mats) \
                    and not o.name.startswith("jamb"):
                me = o.data.copy()
                me.transform(Matrix.Translation(Vector((0.0, 0.0, -LIFT[0]))) @ o.matrix_world)
                bm.from_mesh(me)
                bpy.data.meshes.remove(me)
        for o in obs:
            bpy.data.objects.remove(o)
    HULL_STATS["source_triangles"] = sum(len(f.verts) - 2 for f in bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.02)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.005)
    bm.normal_update()
    return bm


def pod_bmeshes(pieces: Path) -> list:
    """The three nozzle pods in the pieces' frame (their shells, collars and bells; the inner throat left out)."""
    out = []
    for name, (x, y, h) in PODS:
        obs = import_glb(pieces / f"{name}.glb")
        bm = bmesh.new()
        for o in obs:
            if o.type == "MESH" and not o.name.startswith("pod_throat"):
                me = o.data.copy()
                me.transform(Matrix.Translation(Vector((x, -y, h - LIFT[0]))) @ o.matrix_world)
                bm.from_mesh(me)
                bpy.data.meshes.remove(me)
        for o in obs:
            bpy.data.objects.remove(o)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
        bm.normal_update()
        out.append(bm)
    return out


def chains(segments: list, tol: float = 1e-4) -> list:
    """Joins segments [(a, b)] (Vectors) into polylines through their shared ends; returns [[p0, p1, ...]]."""
    key = lambda v: (round(v.x / tol), round(v.y / tol), round(v.z / tol))  # noqa: E731
    adj: dict = {}
    pts: dict = {}
    for i, (a, b) in enumerate(segments):
        for v in (a, b):
            pts[key(v)] = v
        adj.setdefault(key(a), []).append((i, key(b)))
        adj.setdefault(key(b), []).append((i, key(a)))
    used = set()
    out = []
    starts = [k for k, v in adj.items() if len(v) != 2] + list(adj.keys())
    for s in starts:
        for i, nxt in adj[s]:
            if i in used:
                continue
            line = [pts[s]]
            used.add(i)
            cur = nxt
            line.append(pts[cur])
            while len(adj[cur]) == 2:
                j, nn = next(((j, nn) for j, nn in adj[cur] if j not in used), (None, None))
                if j is None:
                    break
                used.add(j)
                cur = nn
                line.append(pts[cur])
            out.append(line)
    return out


def simplify(line: list, angle_deg: float = 4.0) -> list:
    """Drops a polyline's vertices where it bends less than angle_deg (and repeated points)."""
    if len(line) < 3:
        return line
    out = [line[0]]
    lim = math.radians(angle_deg)
    for i in range(1, len(line) - 1):
        a, b, c = out[-1], line[i], line[i + 1]
        d0, d1 = b - a, c - b
        if d0.length < 1e-6 or d1.length < 1e-6 or d0.angle(d1, 0.0) < lim:
            continue
        out.append(b)
    out.append(line[-1])
    return out


def feature_lines(bm, angle_deg: float, keep=None) -> list:
    """The polylines of bm's creases over angle_deg and its open edges; keep(edge) filters."""
    lim = math.radians(angle_deg)
    segs = []
    for e in bm.edges:
        faces = e.link_faces
        if len(faces) == 2 and faces[0].normal.angle(faces[1].normal, 0.0) < lim:
            continue
        if keep and not keep(e):
            continue
        segs.append((e.verts[0].co.copy(), e.verts[1].co.copy()))
    return [simplify(c) for c in chains(segs)]


def section_lines(bm, co: Vector, no: Vector, keep=None) -> list:
    """The polylines where the plane (co, no) cuts bm (a copy is cut); keep(midpoint) filters the cut's pieces."""
    work = bm.copy()
    res = bmesh.ops.bisect_plane(work, geom=work.verts[:] + work.edges[:] + work.faces[:], dist=1e-5, plane_co=co,
                                 plane_no=no)
    work.normal_update()
    segs = []
    for e in res["geom_cut"]:
        if isinstance(e, bmesh.types.BMEdge):
            if keep and not keep((e.verts[0].co + e.verts[1].co) * 0.5):
                continue
            segs.append((e.verts[0].co.copy(), e.verts[1].co.copy()))
    work.free()
    return [simplify(c, 3.0) for c in chains(segs)]


class Draper:
    """The hull's top over a plan point: a downward ray from above (x, y) in the pieces' frame."""

    def __init__(self, bm) -> None:
        self.tree = BVHTree.FromBMesh(bm)

    def top(self, x: float, y: float, lift: float = 0.04) -> Vector | None:
        hit, nrm, _i, _d = self.tree.ray_cast(Vector((x, y, 30.0)), Vector((0.0, 0.0, -1.0)))
        if hit is None:
            return None
        n = nrm if nrm.z > 0 else -nrm
        return hit + n * lift


def circle2(c: Vector, r: float, n: int = 48, a0: float = 0.0, a1: float = 360.0) -> list:
    return [(c.x + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             c.y + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def tube(bm, line: list, radius: float, idx_value: int, idx_layer, sides: int = 3) -> int:
    """A thin tube along the polyline (console metres): `sides` faces round, mitred joints, open ends; IDX on every
    face. Returns its triangles."""
    if len(line) < 2:
        return 0
    rings = []
    prev_n = None
    for i, p in enumerate(line):
        d0 = (p - line[i - 1]).normalized() if i > 0 else None
        d1 = (line[i + 1] - p).normalized() if i < len(line) - 1 else None
        if d0 is not None and d1 is not None and (d0 + d1).length > 1e-6:
            d = (d0 + d1).normalized()
        else:
            d = d0 if d0 is not None else d1
        if prev_n is None:
            ref = Vector((0.0, 0.0, 1.0)) if abs(d.z) < 0.9 else Vector((1.0, 0.0, 0.0))
            n = (ref - d * ref.dot(d)).normalized()
        else:  # parallel transport: no twist along the line
            n = (prev_n - d * prev_n.dot(d)).normalized()
        b = d.cross(n)
        scale = 1.0
        if d0 is not None and d1 is not None:
            scale = 1.0 / max(0.5, d0.dot(d))
        ring = [bm.verts.new(p + (n * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides))
                             * radius * scale) for k in range(sides)]
        rings.append(ring)
        prev_n = n
    tris = 0
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            j = (k + 1) % sides
            f = bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
            f[idx_layer] = idx_value
            tris += 2
    return tris


def sphere(bm, centre: Vector, radius: float, idx_value: int, idx_layer) -> None:
    res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=radius)
    for v in res["verts"]:
        v.co += centre
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f[idx_layer] = idx_value


HOLO_PARTS: dict = {}  # the hologram's line groups' triangles, for build.json


def build_hologram(pieces: Path) -> list:
    """The hologram's three objects: lines (console_holo_line, brightness x 100 in IDX), shell (console_holo_shell),
    lamps (console_lamp, index in IDX)."""
    M = holo_matrix()
    k = HOLO["span"] * CM / SHIP_SPAN_M
    hull = hull_bmesh(pieces)
    pods = pod_bmeshes(pieces)
    drape = Draper(hull)
    groups: dict = {}

    def add(group: str, lines: list, bright: int, width: float) -> None:
        groups.setdefault(group, []).extend((ln, bright, width) for ln in lines if len(ln) > 1)

    line_w, grid_w = HOLO["line"] * CM, HOLO["grid_line"] * CM
    # the hull's own shape, from its mesh: the outline (a level cut through its widest edge), contour cuts over its
    # top, the keel's profile, and its sharp creases (inside the plates: the plates' own outlines are left out, they
    # are a dense grid of their own)
    add("outline", section_lines(hull, Vector((0.0, 0.0, HOLO["outline_z"])), Vector((0.0, 0.0, 1.0))), 100,
        line_w * 1.2)
    for z in HOLO["contour_z"]:
        add("contours", section_lines(hull, Vector((0.0, 0.0, z)), Vector((0.0, 0.0, 1.0))), 55, grid_w)
    add("keel", section_lines(hull, Vector((0.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0))), 70, grid_w)
    creases = feature_lines(hull, 40.0, keep=lambda e: e.is_manifold)
    add("creases", [c for c in creases if sum((b - a).length for a, b in zip(c, c[1:])) > 1.5], 65, grid_w)
    # the surface grid: section lines over the top every grid_step, through the hall's centre
    step = HOLO["grid_step"]

    def up(p: Vector) -> bool:  # a piece of the cut on the hull's top (the first surface a ray from above meets)
        hit = drape.top(p.x, p.y, lift=0.0)
        return hit is not None and hit.z - p.z < 0.08

    for i in range(-9, 10):
        if i:
            add("grid", section_lines(hull, Vector((HALL.x + i * step, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), up),
                32, grid_w)
    for j in range(-9, 8):
        add("grid", section_lines(hull, Vector((0.0, HALL.y + j * step, 0.0)), Vector((0.0, 1.0, 0.0)), up), 32,
            grid_w)
    # the rooms' plan, flat at plan_z inside the hull, seen through its shell (the engineer's review, 2026-10-24: laid
    # on the curved top, the hall's disc sat over the hull and the rooms climbed its hump): the hall's disc with its
    # rings, dashed ring and spokes, the tip discs, the bands along the wings with the order lamps, the entrance
    # channel to the nose with its dashed middle line
    z = HOLO["plan_z"]
    flat = lambda pts: [[Vector((x, y, z)) for x, y in pts]]  # noqa: E731
    add("hall disc", flat(circle2(HALL, 4.0, 64)), 100, line_w * 1.25)
    add("hall disc", flat(circle2(HALL, 2.7, 48)), 70, grid_w)
    add("hall disc", flat(circle2(HALL, 1.3, 32)), 70, grid_w)
    # (the dashed ring round the disc at 4.45 m is the spin-up's charge ring now: build_spinup)
    for a in range(0, 360, 45):
        d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0.0))
        p0, p1 = HALL + d * 1.3, HALL + d * 4.0
        add("hall disc", flat([(p0.x, p0.y), (p1.x, p1.y)]), 45, grid_w)
    for t in TIPS:
        add("tip discs", flat(circle2(t, 2.0, 48)), 100, line_w * 1.25)
        add("tip discs", flat(circle2(t, 1.3, 32)), 70, grid_w)
        for a in (0, 90):
            d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0.0)) * 2.0
            add("tip discs", flat([(t.x - d.x, t.y - d.y), (t.x + d.x, t.y + d.y)]), 45, grid_w)
    lamps = []
    for w, t in enumerate(TIPS):
        axis = (t - HALL).normalized()
        side = Vector((-axis.y, axis.x, 0.0))
        u0, u1 = 4.0, (t - HALL).length - 2.0
        for s in (-0.5, 0.5):
            a, b = HALL + axis * u0 + side * s * HOLO["band_width"], HALL + axis * u1 + side * s * HOLO["band_width"]
            add("bands", flat([(a.x, a.y), (b.x, b.y)]), 100, line_w)
        for i in range(4):  # the order lamps from the hall outward: red, yellow, green, blue
            p = HALL + axis * (HOLO["lamp_from"] + HOLO["lamp_pitch"] * i)
            lamps.append((w * 4 + i, Vector((p.x, p.y, z))))
    for s in (-1.0, 1.0):  # the entrance channel: the throat's sides from the hall's disc to the nose
        add("entrance", flat([(s * 2.915, 3.252), (s * 1.65, 7.1)]), 100, line_w)
    add("entrance", flat([(-1.65, 7.1), (1.65, 7.1)]), 100, line_w)
    for q in range(8):  # its dashed middle line
        y0 = 4.4 + q * 0.34
        add("entrance", flat([(0.0, y0), (0.0, y0 + 0.2)]), 80, grid_w * 1.3)
    # the turbines: rings along each pod (bright at its ends) and lines down its length, all cut from its mesh; they
    # are the spin-up's own surface (console_holo_turbine: they pulse and spin), drawn by build_spinup
    turbines = []
    for pod in pods:
        lo = min(v.co.y for v in pod.verts)
        hi = max(v.co.y for v in pod.verts)
        cx = sum(v.co.x for v in pod.verts) / len(pod.verts)
        cz = sum(v.co.z for v in pod.verts) / len(pod.verts)
        cuts = []
        for i in range(1, 6):
            y = lo + (hi - lo) * i / 6.0
            cuts += [(ln, 100 if i in (1, 5) else 55, line_w if i in (1, 5) else grid_w)
                     for ln in section_lines(pod, Vector((0.0, y, 0.0)), Vector((0.0, 1.0, 0.0)))]
        for a in range(0, 180, 45):
            n = Vector((math.cos(math.radians(a)), 0.0, math.sin(math.radians(a))))
            cuts += [(ln, 70 if a in (0, 90) else 45, grid_w) for ln in section_lines(pod, Vector((cx, 0.0, cz)), n)]
        half = 0.5 * (max(v.co.x for v in pod.verts) - min(v.co.x for v in pod.verts))
        turbines.append({"centre": Vector((cx, hi, cz)), "lo": lo, "half": half,
                         "cuts": [c for c in cuts if len(c[0]) > 1]})

    # the line tubes, in the console's frame
    bm = bmesh.new()
    idx = bm.faces.layers.int.new(IDX)
    for group, items in groups.items():
        tris = 0
        for ln, bright, width in items:
            tris += tube(bm, [M @ p for p in ln], width * 0.5, bright, idx)
        HOLO_PARTS[group] = tris
    HULL_STATS["bounds_cm"] = [[round(min(v.co[i] for v in bm.verts) / CM, 2) for i in range(3)],
                               [round(max(v.co[i] for v in bm.verts) / CM, 2) for i in range(3)]]
    lines = mesh_object("holo_lines", bm, "console_holo_line")

    # the shell: the hull's surface thinned, faint; the hall's and the tip rooms' discs on the top a little brighter
    shell = hull.copy()
    bmesh.ops.dissolve_limit(shell, angle_limit=math.radians(6.0), verts=shell.verts, edges=shell.edges)
    bmesh.ops.triangulate(shell, faces=shell.faces)
    sidx = shell.faces.layers.int.new(IDX)
    for f in shell.faces:
        f[sidx] = 30
    for pod in pods:
        pm = pod.copy()
        pidx = pm.faces.layers.int.get(IDX) or pm.faces.layers.int.new(IDX)
        for f in pm.faces:
            f[pidx] = 30
        tmp = bpy.data.meshes.new("tmp")
        pm.to_mesh(tmp)
        shell.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        pm.free()
    sidx = shell.faces.layers.int[IDX]
    for c, r in [(HALL, 4.0)] + [(t, 2.0) for t in TIPS]:  # the discs' faint fill, in the plan's level
        verts = [shell.verts.new((x, y, HOLO["plan_z"])) for x, y in circle2(c, r, 40)[:-1]]
        centre = shell.verts.new((c.x, c.y, HOLO["plan_z"]))
        for i in range(len(verts)):
            f = shell.faces.new((centre, verts[i - 1], verts[i]))
            f[sidx] = 85
    shell.transform(M)
    HOLO_PARTS["shell"] = sum(len(f.verts) - 2 for f in shell.faces)
    shell_ob = mesh_object("holo_shell", shell, "console_holo_shell")

    # the order lamps: small glowing beads on the bands
    lb = bmesh.new()
    lidx = lb.faces.layers.int.new(IDX)
    for i, p in lamps:
        sphere(lb, M @ p + Vector((0.0, 0.0, HOLO["lamp"] * 0.6 * CM)), HOLO["lamp"] * 0.5 * CM, i, lidx)
    HOLO_PARTS["lamps"] = sum(len(f.verts) - 2 for f in lb.faces)
    lamps_ob = mesh_object("holo_lamps", lb, "console_lamp")
    HULL_STATS.update({"lamps": len(lamps), "scale": round(1.0 / k, 2)})
    spin = build_spinup(M, k, turbines, line_w, grid_w)
    hull.free()
    for p in pods:
        p.free()
    return [lines, shell_ob, lamps_ob] + spin


# --- the spin-up (art#263, step 1: the engineer's prime-game#1095 c6392050112) -------------------------------------
# Four parts on the hologram, each its own surface on console_holo.gdshader's modes, their ids in UV0 (as the strips'
# and lamps' indices): the turbines (console_holo_turbine: the pods' cuts, u their angle round the pod; and a fan at
# each pod's front, u 5, that the shader turns round the pod's axis), the stations' wiring (console_holo_wire: v the
# station's index, BUS the manifold; u the distance along its line in console dm, toward the turbines; the points
# u -1 and their halos u -2), the charge ring (console_holo_ring: u the bar's share 0..1, v 0 at its foot, 1 at its
# top) and the countdown (console_holo_digit: v digit x 10 + segment, a..g; the shader turns it to the eye).
SPIN = DIMS["spinup"]
FX = "console_fx"
FX_MATS = {"console_holo_turbine", "console_holo_wire", "console_holo_ring", "console_holo_digit"}
STATIONS = ("socket_w", "socket_e", "socket_fw", "socket_fe", "breaker_w", "breaker_e", "vent_w", "vent_e")
BUS = len(STATIONS)
SHIP_TOML = Path(__file__).resolve().parents[2] / "layouts" / "ship" / "ship.toml"
THROAT_E = (Vector((2.915, 3.252)), Vector((1.65, 7.1)))  # the throat's east wall (the entrance lines), pieces' frame
FAN_U = 5.0
SEGMENTS = "abcdefg"
SPINUP: dict = {}


def to_gltf(p: Vector) -> list:
    return [round(p.x, 5), round(p.z, 5), round(-p.y, 5)]


def fx_layers(bm) -> tuple:
    return bm.faces.layers.int.new(IDX), bm.loops.layers.uv.new(FX)


def fx_tube(bm, line: list, us: list, v: float, radius: float, layers: tuple, sides: int = 3) -> int:
    """tube() with its UV0 as built: (us[i], v) at the line's point i."""
    idx, fx = layers
    first = len(bm.faces)
    tris = tube(bm, line, radius, 0, idx, sides)
    bm.faces.ensure_lookup_table()
    for n in range(first, len(bm.faces)):
        i = (n - first) // sides
        for lp, uu in zip(bm.faces[n].loops, (us[i], us[i], us[i + 1], us[i + 1])):
            lp[fx].uv = (uu, v)
    return tris


def fx_sphere(bm, centre: Vector, radius: float, uv: tuple, layers: tuple) -> int:
    res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=radius)
    faces = {f for v in res["verts"] for f in v.link_faces}
    for v in res["verts"]:
        v.co += centre
    for f in faces:
        for lp in f.loops:
            lp[layers[1]].uv = uv
    return sum(len(f.verts) - 2 for f in faces)


def station_path(sid: str, at: list) -> list:
    """A station's line on the plan (the pieces' frame, metres, 2D) from its point to the manifold: in to its lane's
    radius round the hall's centre (a breaker along its corridor, a vent along the throat's wall), round the hall's
    wall to the back, then aft beside the others. Built on the east side and mirrored for the west."""
    s = 1.0 if at[0] > 0 else -1.0
    c = Vector((HALL.x, HALL.y))
    p = Vector((abs(at[0]), -at[1]))
    kind = "breaker" if sid.startswith("breaker") else "vent" if sid.startswith("vent") else \
        "socket_back" if p.y < c.y else "socket_front"
    r, lx = SPIN["lanes"][kind]
    pts = [p]
    if kind.startswith("socket"):
        pts.append(c + (p - c).normalized() * r)
    elif kind == "breaker":
        a = (Vector((TIPS[1].x, TIPS[1].y)) - c).normalized()
        n = Vector((-a.y, a.x))
        n = n if n.dot(p - c) > 0 else -n
        o = SPIN["breaker_offset"]
        pts.append(c + a * (p - c).dot(a) + n * o)
        pts.append(c + a * math.sqrt(r * r - o * o) + n * o)
    else:
        a, b = THROAT_E
        t = (a - b).normalized()
        m = Vector((-t.y, t.x))
        m = m if m.x < 0 else -m
        q = p + m * SPIN["vent_offset"]
        w = q - c  # along the wall into the hall's disc (4 m), then in to the lane: no other line is crossed there
        bb, cc = w.dot(t), w.dot(w) - 16.0
        e = q + t * (-bb - math.sqrt(bb * bb - cc))
        pts += [q, e, c + (e - c).normalized() * r]
    e = pts[-1] - c
    a0 = math.degrees(math.atan2(e.y, e.x))
    a1 = math.degrees(math.atan2(-math.sqrt(r * r - lx * lx), lx))
    n = max(2, int(abs(a0 - a1) / 4.0))
    pts += [Vector((c.x + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                    c.y + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))) for i in range(1, n + 1)]
    pts.append(Vector((lx, -SPIN["manifold_y"])))
    return [Vector((s * q.x, q.y)) for q in pts]


def lengths(line: list) -> list:
    """The distance along a line (console metres) in decimetres."""
    out = [0.0]
    for a, b in zip(line, line[1:]):
        out.append(out[-1] + (b - a).length * 10.0)
    return out


def build_spinup(M: Matrix, k: float, turbines: list, line_w: float, grid_w: float) -> list:
    z = HOLO["plan_z"]
    obs = []
    # the turbines: the pods' cuts (u their angle round the pod, unwrapped along each cut) and a fan at each front
    bm = bmesh.new()
    lay = fx_layers(bm)
    tris = {"cuts": 0, "fans": 0}
    centres = []
    for t in turbines:
        c = t["centre"]
        for ln, bright, width in t["cuts"]:
            us = []
            for p in ln:
                a = math.atan2(p.z - c.z, p.x - c.x) / (2.0 * math.pi) % 1.0
                if us:
                    a += round(us[-1] - a)
                us.append(a)
            tris["cuts"] += fx_tube(bm, [M @ p for p in ln], us, bright, width * 0.5, lay)
        y = c.y - 0.25
        r = SPIN["fan_r"] * t["half"]
        ring = [Vector((c.x + 0.2 * r * math.cos(a), y, c.z + 0.2 * r * math.sin(a)))
                for a in (2.0 * math.pi * i / 16 for i in range(17))]
        tris["fans"] += fx_tube(bm, [M @ p for p in ring], [FAN_U] * len(ring), 80, grid_w * 0.75, lay)
        for b in range(int(SPIN["fan_blades"])):
            a0 = 2.0 * math.pi * b / SPIN["fan_blades"]
            blade = [Vector((c.x + r * (0.24 + 0.76 * f) * math.cos(a0 + 0.6 * f), y,
                             c.z + r * (0.24 + 0.76 * f) * math.sin(a0 + 0.6 * f))) for f in (i / 5 for i in range(6))]
            tris["fans"] += fx_tube(bm, [M @ p for p in blade], [FAN_U] * 6, 90, grid_w * 0.8, lay)
        centres.append(to_gltf(M @ Vector((c.x, y, c.z))))
    HOLO_PARTS.update({"turbines": tris["cuts"], "fans": tris["fans"]})
    lo, hi = HULL_STATS["bounds_cm"]  # the hologram's box takes the turbines in, as before they had their own surface
    HULL_STATS["bounds_cm"] = [[round(min(lo[i], min(v.co[i] for v in bm.verts) / CM), 2) for i in range(3)],
                               [round(max(hi[i], max(v.co[i] for v in bm.verts) / CM), 2) for i in range(3)]]
    obs.append(mesh_object("holo_turbines", bm, "console_holo_turbine"))
    axis = (M.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    SPINUP["turbines"] = {"centres": centres, "axis": to_gltf(axis), "fan_u": FAN_U}

    # the wiring: each station's point and halo, its line to the manifold, the manifold and its feeds to the fans
    spots = {s["id"]: s["at"] for s in tomllib.loads(SHIP_TOML.read_text(encoding="utf-8"))["stations"]["spot"]}
    bm = bmesh.new()
    lay = fx_layers(bm)
    tris = 0
    SPINUP["stations"] = {}
    for i, sid in enumerate(STATIONS):
        at = spots[sid]
        line = [M @ Vector((q.x, q.y, z)) for q in station_path(sid, at)]
        tris += fx_tube(bm, line, lengths(line), i, line_w * 0.8, lay)
        p = Vector((at[0], -at[1], z))
        halo = [M @ Vector((x, y, z)) for x, y in circle2(p, SPIN["halo"], 24)]
        tris += fx_tube(bm, halo, [-2.0] * len(halo), i, grid_w * 1.2, lay)
        pt = M @ p + Vector((0.0, 0.0, SPIN["point"] * 0.6 * CM))
        tris += fx_sphere(bm, pt, SPIN["point"] * 0.5 * CM, (-1.0, float(i)), lay)
        SPINUP["stations"][sid] = {"index": i, "plan": at, "point": to_gltf(pt),
                                   "line_dm": round(lengths(line)[-1], 3)}
    ym = -SPIN["manifold_y"]
    for t in turbines:
        c = t["centre"]
        y = c.y - 0.25
        path = [Vector((0.0, ym, z)), Vector((c.x, ym, z)), Vector((c.x, 0.5 * (ym + y), z)), Vector((c.x, y, c.z))]
        if abs(c.x) < 0.01:
            path = path[1:]
        line = [M @ q for q in path]
        tris += fx_tube(bm, line, lengths(line), BUS, line_w * 0.9, lay)
    HOLO_PARTS["wiring"] = tris
    obs.append(mesh_object("holo_wiring", bm, "console_holo_wire"))

    # the charge ring: three stages of dashes round the hall's disc, one bar from the nose clockwise (seen from
    # above); an upright band over the plan, so it reads from the throat and the corridors
    bm = bmesh.new()
    idx, fx = fx_layers(bm)
    r, h = SPIN["ring_r"], SPIN["ring_h"]
    gap, dgap, nd = SPIN["ring_stage_gap"], SPIN["ring_dash_gap"], int(SPIN["ring_dashes"])
    span = 120.0 - gap
    dash = (span - (nd - 1) * dgap) / nd
    tris = 0
    for st in range(3):
        start = 90.0 - 120.0 * st - 0.5 * gap
        for d in range(nd):
            a0 = d * (dash + dgap)
            steps = max(1, math.ceil(dash / 2.5))
            col = []
            for j in range(steps + 1):
                along = a0 + dash * j / steps
                a = math.radians(start - along)
                foot = M @ Vector((HALL.x + r * math.cos(a), HALL.y + r * math.sin(a), z))
                top = M @ Vector((HALL.x + r * math.cos(a), HALL.y + r * math.sin(a), z + h))
                col.append((bm.verts.new(foot), bm.verts.new(top), (st + along / span) / 3.0))
            for (f0, t0, u0), (f1, t1, u1) in zip(col, col[1:]):
                f = bm.faces.new((f0, f1, t1, t0))
                for lp, uv in zip(f.loops, ((u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0))):
                    lp[fx].uv = uv
                tris += 2
    HOLO_PARTS["ring"] = tris
    obs.append(mesh_object("holo_ring", bm, "console_holo_ring"))
    SPINUP["ring"] = {"radius_cm": round(r * k / CM, 2), "height_cm": round(h * k / CM, 2), "dashes": 3 * nd}

    # the countdown: two seven-segment digits over the hologram, upright, facing the front (the shader turns them)
    bm = bmesh.new()
    idx, fx = fx_layers(bm)
    W, H, T = SPIN["digit_w"], SPIN["digit_h"], SPIN["digit_t"]
    x0, x1, z0, z1 = -(W - T) / 2, (W - T) / 2, -(H - T) / 2, (H - T) / 2
    segs = {"a": ((x0, z1), (x1, z1)), "b": ((x1, z1), (x1, 0.0)), "c": ((x1, 0.0), (x1, z0)),
            "d": ((x0, z0), (x1, z0)), "e": ((x0, 0.0), (x0, z0)), "f": ((x0, z1), (x0, 0.0)),
            "g": ((x0, 0.0), (x1, 0.0))}
    tris = 0
    for dg in range(2):
        cx = (dg - 0.5) * (W + SPIN["digit_gap"])
        for sn, name in enumerate(SEGMENTS):
            (ax, az), (bx, bz) = segs[name]
            a, b = Vector((ax, az)), Vector((bx, bz))
            dv = (b - a).normalized()
            a, b = a + dv * 0.45, b - dv * 0.45  # a hair's gap at the segments' tips
            nv = Vector((-dv.y, dv.x)) * (T / 2)
            ring = [a, a + dv * (T / 2) + nv, b - dv * (T / 2) + nv, b, b - dv * (T / 2) - nv, a + dv * (T / 2) - nv]
            verts = [bm.verts.new(((cx + q.x + q.y * SPIN["digit_slant"]) * CM, 0.0, (SPIN["digit_z"] + q.y) * CM))
                     for q in ring]
            f = bm.faces.new(verts)
            for lp in f.loops:
                lp[fx].uv = (0.0, float(dg * 10 + sn))
            tris += 4
    HOLO_PARTS["digits"] = tris
    obs.append(mesh_object("holo_digits", bm, "console_holo_digit"))
    SPINUP["countdown"] = {"centre_cm": [0.0, 0.0, SPIN["digit_z"]], "digit_h_cm": H, "segments": SEGMENTS}
    SPINUP["order"] = list(STATIONS) + ["bus"]
    return obs


def mesh_object(name: str, bm, mat_name: str) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(MATS[mat_name])
    me.materials.append(MATS["_chamfer"])
    return ob


# --- materials -----------------------------------------------------------------------------------------------------
MATS: dict = {}
CYAN = (0.0, 0.62, 1.0, 1.0)          # saturated: AgX bleaches a bright pale cyan to white
ORANGE = (1.0, 0.16, 0.0, 1.0)            # deep: AgX pales a bright orange to peach
GREEN = (0.08, 1.0, 0.18, 1.0)
WHITE = (0.85, 0.9, 1.0, 1.0)
LAMP_COLOURS = [(1.0, 0.05, 0.03, 1.0), (1.0, 0.72, 0.02, 1.0), (0.08, 1.0, 0.15, 1.0), (0.05, 0.3, 1.0, 1.0)]
STATES = {"idle": {"passed": 1.0, "lit": -1.0, "order": 0.0},
          "order": {"passed": 1.0, "lit": 1.0, "order": 1.0},     # the yellow lamp of the west wing
          "stage": {"passed": 2.0, "lit": -1.0, "order": 0.0}}


def state_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.new("console_state", "ShaderNodeTree")
    keys = ("passed", "lit", "order")
    for key in keys:  # the sockets first: the output node takes them when it is made
        ng.interface.new_socket(name=key, in_out="OUTPUT", socket_type="NodeSocketFloat")
    out = ng.nodes.new("NodeGroupOutput")
    for key in keys:
        val = ng.nodes.new("ShaderNodeValue")
        val.name = key
        val.outputs[0].default_value = STATES["idle"][key]
        ng.links.new(val.outputs[0], out.inputs[key])
    return ng


def set_state(name: str) -> None:
    for key, value in STATES[name].items():
        bpy.data.node_groups["console_state"].nodes[key].outputs[0].default_value = value


class Nodes:
    """A small wrapper for writing shader graphs."""

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

    def math(self, op: str, a, b=0.0, c=None):
        m = self.n("ShaderNodeMath")
        m.operation = op
        self.set(m, 0, a)
        self.set(m, 1, b)
        if c is not None:
            self.set(m, 2, c)
        return m.outputs[0]

    def mix_rgb(self, fac, a, b):
        m = self.n("ShaderNodeMix")
        m.data_type = "RGBA"
        self.set(m, 0, fac)
        self.set(m, 6, a)
        self.set(m, 7, b)
        return m.outputs[2]

    def state(self, key: str):
        g = self.n("ShaderNodeGroup")
        g.node_tree = bpy.data.node_groups["console_state"]
        return g.outputs[key]

    def uv(self):
        u = self.n("ShaderNodeUVMap")
        u.uv_map = "UVMap"
        sep = self.n("ShaderNodeSeparateXYZ")
        self.nt.links.new(u.outputs[0], sep.inputs[0])
        return sep.outputs[0], sep.outputs[1]  # chamfer flag, index or brightness

    def output(self, shader):
        o = self.n("ShaderNodeOutputMaterial")
        self.nt.links.new(shader if isinstance(shader, bpy.types.NodeSocket) else shader.outputs[0], o.inputs[0])


def bsdf(nd: Nodes, **kw):
    b = nd.n("ShaderNodeBsdfPrincipled")
    for k, v in kw.items():
        nd.set(b, k, v)
    return b


def metal_material(name: str, base, worn, rough: float, metallic: float) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    nd = Nodes(mat)
    flag, _ = nd.uv()
    tc = nd.n("ShaderNodeTexCoord")
    noise = nd.n("ShaderNodeTexNoise", Scale=22.0, Detail=4.0)
    nd.nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    big = nd.n("ShaderNodeTexNoise", Scale=3.5, Detail=2.0)
    nd.nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    # the bright edge: the chamfer, broken up a little by the fine noise
    wear = nd.math("MULTIPLY", flag, nd.math("ADD", nd.math("MULTIPLY", noise.outputs[0], 0.5), 0.6))
    wear = nd.math("MINIMUM", wear, 1.0)
    shade = nd.math("ADD", nd.math("MULTIPLY", big.outputs[0], 0.25), 0.88)
    col = nd.mix_rgb(wear, base, worn)
    col2 = nd.n("ShaderNodeVectorMath")
    col2.operation = "SCALE"
    nd.nt.links.new(col, col2.inputs[0])
    nd.set(col2, "Scale", shade)
    r = nd.math("ADD", rough, nd.math("SUBTRACT", nd.math("MULTIPLY", noise.outputs[0], 0.14), 0.07))
    r = nd.math("SUBTRACT", r, nd.math("MULTIPLY", wear, 0.14))
    b = bsdf(nd, Metallic=metallic, Roughness=r)
    nd.nt.links.new(col2.outputs[0], b.inputs["Base Color"])
    nd.output(b)
    return mat


def emissive(name: str, colour, strength) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    nd = Nodes(mat)
    b = bsdf(nd, **{"Base Color": (0.03, 0.03, 0.035, 1.0), "Roughness": 0.25, "Emission Color": colour,
                    "Emission Strength": strength})
    nd.output(b)
    return mat


def additive(nd: Nodes, colour, strength):
    """Transparent + emission: a light that adds to what is behind it (the game's blend_add)."""
    em = nd.n("ShaderNodeEmission")
    nd.set(em, "Color", colour)
    nd.set(em, "Strength", strength)
    tr = nd.n("ShaderNodeBsdfTransparent")
    add = nd.n("ShaderNodeAddShader")
    nd.nt.links.new(tr.outputs[0], add.inputs[0])
    nd.nt.links.new(em.outputs[0], add.inputs[1])
    return add


def blended(mat) -> None:
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    mat.use_transparency_overlap = True


def build_materials() -> None:
    state_group()
    MATS["console_bronze"] = metal_material("console_bronze", (0.56, 0.27, 0.10, 1.0), (1.0, 0.70, 0.40, 1.0),
                                            0.34, 1.0)
    MATS["console_graphite"] = metal_material("console_graphite", (0.06, 0.062, 0.07, 1.0), (0.36, 0.35, 0.34, 1.0),
                                              0.38, 0.85)
    MATS["console_cyan"] = emissive("console_cyan", CYAN, 6.0)

    # the start button: an orange glow, a little brighter at its top (the lens's hot spot)
    mat = bpy.data.materials.new("console_button")
    nd = Nodes(mat)
    lw = nd.n("ShaderNodeLayerWeight", Blend=0.4)
    hot = nd.math("ADD", 0.35, nd.math("MULTIPLY", nd.math("SUBTRACT", 1.0, lw.outputs["Facing"]), 0.9))
    b = bsdf(nd, **{"Base Color": (1.0, 0.22, 0.01, 1.0), "Roughness": 0.15, "Coat Weight": 1.0,
                    "Emission Color": ORANGE})
    nd.set(b, "Emission Strength", hot)
    nd.output(b)
    MATS["console_button"] = mat

    # the stage strips: index < passed lit green, the rest dim white
    mat = bpy.data.materials.new("console_stage")
    nd = Nodes(mat)
    _flag, index = nd.uv()
    on = nd.math("LESS_THAN", index, nd.math("SUBTRACT", nd.state("passed"), 0.5))
    col = nd.mix_rgb(on, WHITE, GREEN)
    b = bsdf(nd, **{"Base Color": (0.05, 0.05, 0.05, 1.0), "Roughness": 0.2})
    nd.nt.links.new(col, b.inputs["Emission Color"])
    nd.set(b, "Emission Strength", nd.math("ADD", 0.6, nd.math("MULTIPLY", on, 2.2)))
    nd.output(b)
    MATS["console_stage"] = mat

    # the order lamps: each its colour (index mod 4), dim; the lamp `lit` bright while the order plays
    mat = bpy.data.materials.new("console_lamp")
    nd = Nodes(mat)
    _flag, index = nd.uv()
    k = nd.math("MODULO", index, 4.0)
    col = LAMP_COLOURS[0]
    sock = None
    for i in range(1, 4):
        sel = nd.math("GREATER_THAN", k, i - 0.5)
        sock = nd.mix_rgb(sel, sock if sock is not None else col, LAMP_COLOURS[i])
    lit = nd.math("LESS_THAN", nd.math("ABSOLUTE", nd.math("SUBTRACT", index, nd.state("lit"))), 0.5)
    strength = nd.math("ADD", 4.0, nd.math("MULTIPLY", lit, 16.0))
    strength = nd.math("MULTIPLY", strength, nd.math("SUBTRACT", 1.0, nd.math("MULTIPLY", nd.math(
        "SUBTRACT", nd.state("order"), lit), 0.55)))  # while the order plays, the others dim
    em = nd.n("ShaderNodeEmission")
    nd.nt.links.new(sock, em.inputs["Color"])
    nd.set(em, "Strength", strength)
    nd.output(em)
    MATS["console_lamp"] = mat

    # the hologram's lines: cyan, additive, their brightness in UV0 v (x 100)
    mat = bpy.data.materials.new("console_holo_line")
    nd = Nodes(mat)
    _flag, bright = nd.uv()
    nd.output(additive(nd, (0.01, 0.28, 1.0, 1.0), nd.math("MULTIPLY", bright, 0.026)))
    blended(mat)
    MATS["console_holo_line"] = mat

    # the hologram's shell: a faint see-through glow, stronger where it turns away from the eye (its outline)
    mat = bpy.data.materials.new("console_holo_shell")
    nd = Nodes(mat)
    _flag, bright = nd.uv()
    lw = nd.n("ShaderNodeLayerWeight", Blend=0.5)
    rim = nd.math("ADD", 0.25, nd.math("MULTIPLY", lw.outputs["Facing"], 0.9))
    nd.output(additive(nd, (0.02, 0.3, 1.0, 1.0), nd.math("MULTIPLY", nd.math("MULTIPLY", bright, 0.009), rim)))
    blended(mat)
    MATS["console_holo_shell"] = mat

    # the light column: fades out upward (UV0 v: the height share x 100) and at its silhouette
    mat = bpy.data.materials.new("console_beam")
    nd = Nodes(mat)
    _flag, h = nd.uv()
    lw = nd.n("ShaderNodeLayerWeight", Blend=0.5)
    fade = nd.math("POWER", nd.math("SUBTRACT", 1.0, nd.math("MULTIPLY", h, 0.01)), 1.6)
    edge = nd.math("SUBTRACT", 1.0, lw.outputs["Facing"])
    nd.output(additive(nd, (0.1, 0.6, 1.0, 1.0), nd.math("MULTIPLY", nd.math("MULTIPLY", fade, edge), 0.45)))
    blended(mat)
    MATS["console_beam"] = mat

    # the spin-up's parts (Blender's look: their resting glow; the states are the game's, console_holo.gdshader)
    for name, strength in (("console_holo_turbine", 2.0), ("console_holo_wire", 1.2), ("console_holo_ring", 0.8),
                           ("console_holo_digit", 0.0)):
        mat = bpy.data.materials.new(name)
        nd = Nodes(mat)
        nd.output(additive(nd, (0.01, 0.28, 1.0, 1.0), strength))
        blended(mat)
        MATS[name] = mat

    MATS["_chamfer"] = bpy.data.materials.new("_chamfer")  # a marker slot: the bevel's faces, sorted in join()


ORDER = ["console_bronze", "console_graphite", "console_cyan", "console_button", "console_stage", "console_lamp",
         "console_holo_line", "console_holo_shell", "console_beam", "console_holo_turbine", "console_holo_wire",
         "console_holo_ring", "console_holo_digit"]


# --- assembly ------------------------------------------------------------------------------------------------------
def facet_random(co: Vector) -> float:
    h = math.sin(co.x * 1271.1 + co.y * 3117.7 + co.z * 743.3) * 43758.5453
    return h - math.floor(h)


INDEX_SEEN: dict = {}  # the strips' and lamps' indices written to UV0 v, for build.json
INDEXED = {"console_stage", "console_lamp", "console_holo_line", "console_holo_shell", "console_beam"}


def join(objs: list) -> bpy.types.Object:
    """Applies each part's chamfer, writes UV0 (u: chamfer face; v: IDX on the indexed materials, else the face's
    random value), gives every face its part's material in one shared slot list, joins the parts into one object."""
    deps = bpy.context.evaluated_depsgraph_get()
    bm_all = bmesh.new()
    bm_all.loops.layers.uv.new("UVMap")
    stats = {}
    for ob in objs:
        ev = ob.evaluated_get(deps)
        me = bpy.data.meshes.new_from_object(ev)
        own = me.materials[0].name
        bm = bmesh.new()
        bm.from_mesh(me)
        uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
        idx = bm.faces.layers.int.get(IDX)
        fx = bm.loops.layers.uv.get(FX)
        for f in bm.faces:
            slot = me.materials[f.material_index].name if f.material_index < len(me.materials) else own
            is_chamfer = slot == "_chamfer"
            name = own if is_chamfer else slot
            f.material_index = ORDER.index(name)
            v = float(f[idx]) if (idx is not None and name in INDEXED) else facet_random(f.calc_center_median())
            if name in ("console_stage", "console_lamp"):
                INDEX_SEEN.setdefault(name, set()).add(int(v))
            if name in FX_MATS and fx is not None:  # the spin-up's parts: (u, v) as built
                for lp in f.loops:
                    lp[uv].uv = tuple(lp[fx].uv)
                continue
            if name == "console_stage":  # u: the fill's share across the strip, left to right (the charge bar)
                u0, u1 = DIMS["strips"]["u"][int(v)]
                for lp in f.loops:
                    x = (ob.matrix_world @ lp.vert.co).x / CM
                    lp[uv].uv = (min(1.0, max(0.0, (x - u0) / (u1 - u0))), v)
                continue
            for lp in f.loops:
                lp[uv].uv = (1.0 if is_chamfer else 0.0, v)
        stats[ob.name] = stats.get(ob.name, 0) + sum(len(f.verts) - 2 for f in bm.faces)
        if fx is not None:
            bm.loops.layers.uv.remove(fx)
        tmp = bpy.data.meshes.new("tmp")
        bm.to_mesh(tmp)
        bm.free()
        bm_all.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new("start_console")
    bm_all.to_mesh(me)
    bm_all.free()
    for name in ORDER:
        me.materials.append(MATS[name])
    for p in me.polygons:
        p.use_smooth = MATS[ORDER[p.material_index]].name in ("console_button", "console_lamp", "console_beam")
    for ob in objs:
        bpy.data.objects.remove(ob)
    out = bpy.data.objects.new("start_console", me)
    bpy.context.collection.objects.link(out)
    out["part_triangles"] = json.dumps(stats)
    return out


def build(pieces: Path) -> bpy.types.Object:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    build_materials()
    parts = [
        part("core", build_core, "console_graphite", CHAMFER_SMALL),
        part("bands", build_bands, "console_graphite", CHAMFER_SMALL),
        part("plinth", build_plinth, "console_bronze", CHAMFER_BLOCK),
        part("body", build_body, "console_bronze", CHAMFER_BLOCK),
        part("channels", build_channels, "console_graphite", CHAMFER_SMALL, more=("console_cyan",)),
        part("rim", build_rim, "console_bronze", CHAMFER_BLOCK),
        part("strips", build_strip_bezels, "console_graphite", CHAMFER_SMALL, more=("console_stage",)),
        part("button_seat", build_button_seat, "console_graphite", CHAMFER_SMALL),
        part("button", build_button, "console_button", 0.0, drawn=False),
        part("deck", build_deck, "console_graphite", CHAMFER_SMALL),
        part("ring", build_ring, "console_cyan", 0.0, drawn=False),
        part("plates", build_plates, "console_graphite", CHAMFER_SMALL),
        part("collar", build_collar, "console_graphite", CHAMFER_SMALL),
        part("core_light", build_core_light, "console_cyan", 0.0, drawn=False),
        part("beam", build_beam, "console_beam", 0.0, drawn=False),
    ]
    parts += build_hologram(pieces)
    return join(parts)


# --- export --------------------------------------------------------------------------------------------------------
def plain_materials() -> dict:
    """Plain Principled copies for the GLB's fallback (idle): the exporter reads only plain BSDFs."""
    spec = {
        "console_bronze": dict(base=(0.50, 0.30, 0.15, 1.0), metallic=1.0, rough=0.3),
        "console_graphite": dict(base=(0.07, 0.072, 0.08, 1.0), metallic=0.85, rough=0.38),
        "console_cyan": dict(base=(0.02, 0.05, 0.06, 1.0), metallic=0.0, rough=0.2, emit=CYAN[:3], strength=6.0),
        "console_button": dict(base=(0.9, 0.25, 0.02, 1.0), metallic=0.0, rough=0.18, emit=ORANGE[:3], strength=4.0),
        "console_stage": dict(base=(0.05, 0.05, 0.05, 1.0), metallic=0.0, rough=0.2, emit=WHITE[:3], strength=1.0),
        "console_lamp": dict(base=(0.05, 0.05, 0.05, 1.0), metallic=0.0, rough=0.2, emit=(1.0, 0.6, 0.2),
                             strength=2.0),
        "console_holo_line": dict(base=(0.1, 0.6, 1.0, 0.85), metallic=0.0, rough=0.5, emit=(0.12, 0.66, 1.0),
                                  strength=4.0, blend=True),
        "console_holo_shell": dict(base=(0.05, 0.45, 1.0, 0.08), metallic=0.0, rough=0.5, emit=(0.05, 0.45, 1.0),
                                   strength=0.3, blend=True),
        "console_beam": dict(base=(0.1, 0.6, 1.0, 0.12), metallic=0.0, rough=0.5, emit=(0.1, 0.6, 1.0),
                             strength=0.6, blend=True),
        **{name: dict(base=(0.1, 0.6, 1.0, a), metallic=0.0, rough=0.5, emit=(0.12, 0.66, 1.0), strength=e, blend=True)
           for name, a, e in (("console_holo_turbine", 0.85, 4.0), ("console_holo_wire", 0.6, 2.0),
                              ("console_holo_ring", 0.3, 1.0), ("console_holo_digit", 0.0, 0.0))},
    }
    out = {}
    for name, s in spec.items():
        mat = bpy.data.materials.new(name + "_plain")
        nd = Nodes(mat)
        b = bsdf(nd, **{"Base Color": s["base"], "Metallic": s["metallic"], "Roughness": s["rough"]})
        if s.get("blend"):
            nd.set(b, "Alpha", s["base"][3])
            mat.surface_render_method = "BLENDED"
        if "emit" in s:
            nd.set(b, "Emission Color", (*s["emit"], 1.0))
            nd.set(b, "Emission Strength", s["strength"])
        nd.output(b)
        out[name] = mat
    return out


def export(ob, out: Path) -> dict:
    looks = list(ob.data.materials)
    plain = plain_materials()
    for i, m in enumerate(looks):
        ob.data.materials[i] = plain[m.name]
    for m in plain.values():  # the GLB keeps the look's names (the game's material script finds them by name)
        look = m.name[:-len("_plain")]
        bpy.data.materials[look].name = look + "_look"
        m.name = look
    for o in bpy.context.scene.objects:
        o.select_set(o == ob)
    bpy.ops.export_scene.gltf(filepath=str(out / "start_console.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True, export_normals=True,
                              export_materials="EXPORT", export_vertex_color="NONE", export_extras=False)
    for m in plain.values():
        name = m.name
        m.name = name + "_plain"
        bpy.data.materials[name + "_look"].name = name
    for i, m in enumerate(looks):
        ob.data.materials[i] = m
    for m in plain.values():
        bpy.data.materials.remove(m)
    me = ob.data
    tris = {}
    for p in me.polygons:
        name = me.materials[p.material_index].name
        tris[name] = tris.get(name, 0) + len(p.vertices) - 2
    co = [ob.matrix_world @ v.co for v in me.vertices]
    lo = [min(c[i] for c in co) for i in range(3)]
    hi = [max(c[i] for c in co) for i in range(3)]
    ped = [ob.matrix_world @ me.vertices[i].co for p in me.polygons
           if me.materials[p.material_index].name in ("console_bronze", "console_graphite") for i in p.vertices]
    return {"triangles": sum(tris.values()), "triangles_by_material": tris,
            "triangles_by_part": json.loads(ob["part_triangles"]), "hologram": {**HULL_STATS, "lines": HOLO_PARTS},
            "spinup": SPINUP,
            "indices": {k: sorted(v) for k, v in INDEX_SEEN.items()},
            "vertices": len(me.vertices), "size_m": [round(hi[i] - lo[i], 4) for i in range(3)],
            "min_m": [round(x, 4) for x in lo], "max_m": [round(x, 4) for x in hi],
            "pedestal_size_m": [round(max(c[i] for c in ped) - min(c[i] for c in ped), 4) for i in range(3)]}


# --- review renders ------------------------------------------------------------------------------------------------
# name: (yaw from the front, elevation, the target (cm: u, d, h), the frame's height in cm)
VIEWS = {
    "q34": (-35.0, 14.0, (0.0, 0.0, 92.0), 200.0),
    "front": (0.0, 3.0, (0.0, 0.0, 92.0), 200.0),
    "side": (-90.0, 3.0, (0.0, 0.0, 92.0), 200.0),
    "top": (0.0, 89.0, (0.0, 0.0, 110.0), 190.0),
    "button": (-18.0, 8.0, (0.0, 50.0, 86.0), 34.0),
    "strips": (12.0, 14.0, (0.0, 52.0, 99.0), 34.0),
    "emitter": (-20.0, 42.0, (0.0, 0.0, 109.0), 70.0),
    "holo": (-28.0, 22.0, (0.0, 0.0, 146.0), 95.0),
}
STATE_VIEWS = {"idle": list(VIEWS), "order": ["q34", "holo"], "stage": ["strips"]}


def stage(res: int, samples: int, hdri: str | None = None) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    try:
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Base Contrast"
    except TypeError:
        pass
    world = bpy.data.worlds.new("ship_night")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    bg.inputs[0].default_value = (0.016, 0.022, 0.04, 1.0)
    bg.inputs[1].default_value = 1.0
    if hdri and Path(hdri).is_file():
        # the metal mirrors a studio HDRI (as the game's room probes give it something to mirror); the camera sees
        # the dark backdrop
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri)
        ref = nt.nodes.new("ShaderNodeBackground")
        ref.inputs[1].default_value = 0.9
        nt.links.new(env.outputs[0], ref.inputs[0])
        path = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(ref.outputs[0], mix.inputs[1])
        nt.links.new(bg.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs[0])
    # the ship's hall at night: warm amber lamps round its wall (ship.toml [light] lamps 1.0, 0.7, 0.42), a cool key,
    # a dark blue ambient; a floor to catch the glow
    for name, loc, energy, colour, size in (("lamp_warm", (-1.4, -1.6, 2.4), 220.0, (1.0, 0.72, 0.46), 0.8),
                                            ("lamp_warm2", (1.6, -0.9, 2.2), 90.0, (1.0, 0.72, 0.46), 0.8),
                                            ("rim_cool", (1.4, 1.5, 2.2), 160.0, (0.62, 0.74, 1.0), 0.9),
                                            ("fill", (0.0, -2.4, 0.6), 12.0, (0.85, 0.85, 1.0), 1.5)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.color = colour
        ld.size = size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        d = Vector((0.0, 0.0, 0.9)) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    floor = bpy.data.meshes.new("floor")
    floor.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
    fo = bpy.data.objects.new("floor", floor)
    sc.collection.objects.link(fo)
    fm = bpy.data.materials.new("floor")
    nd = Nodes(fm)
    nd.output(bsdf(nd, **{"Base Color": (0.035, 0.04, 0.055, 1.0), "Roughness": 0.35, "Metallic": 0.6}))
    floor.materials.append(fm)
    bloom(sc)
    cam = bpy.data.cameras.new("cam")
    cam.lens = 85.0
    cam.clip_start = 0.05
    co = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co


def bloom(sc) -> None:
    """A soft bloom in the compositor, like the game's glow on the emissive parts; skipped (with a line) where this
    Blender's compositor API differs."""
    try:
        tree = bpy.data.node_groups.new("console_bloom", "CompositorNodeTree")
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = tree.nodes.new("CompositorNodeRLayers")
        gl = tree.nodes.new("CompositorNodeGlare")
        out = tree.nodes.new("NodeGroupOutput")
        for key, value in (("Type", "Bloom"), ("Threshold", 1.0), ("Strength", 0.55), ("Size", 0.6)):
            if key in gl.inputs:
                gl.inputs[key].default_value = value
        if hasattr(gl, "glare_type"):
            gl.glare_type = "BLOOM"
        tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
        tree.links.new(gl.outputs["Image"], out.inputs[0])
        sc.compositing_node_group = tree
        sc.render.use_compositing = True
        print("CONSOLE_BLOOM on")
    except Exception as exc:  # noqa: BLE001 - an optional nicety of the review renders
        print(f"CONSOLE_BLOOM off: {exc}")


def shoot(folder: Path, state: str, res: int) -> list:
    sc = bpy.context.scene
    co = sc.camera
    files = []
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    for view in STATE_VIEWS[state]:
        yaw, elev, (u, d, h), frame = VIEWS[view]
        target = Vector((u * CM, -d * CM, h * CM))
        fov = 2.0 * math.atan(36.0 / (2.0 * co.data.lens))
        dist = frame * CM * 0.5 / math.tan(fov * 0.5)
        y, e = math.radians(yaw), math.radians(elev)
        offset = Vector((math.sin(y) * math.cos(e), -math.cos(y) * math.cos(e), math.sin(e))) * dist
        co.location = target + offset
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
        path = folder / f"{state}_{view}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files.append(path.name)
    return files


# --- the drawing's views: orthographic renders and the concept's views at one scale ---------------------------------
PX_PER_CM = 4
# name: (width cm, height cm, the frame's middle (u, h); for the top view (u, d))
ORTHO = {"front": (200.0, 190.0, 0.0, 90.0), "side": (200.0, 190.0, 0.0, 90.0), "top": (190.0, 190.0, 0.0, 0.0)}


def shoot_ortho(folder: Path) -> list:
    """The front (from -Y), side (from -X: the button to the right, as the concept's side view) and top (from +Z,
    the button at the bottom) views with an orthographic camera at PX_PER_CM, framed like console_drawing.py's
    views, so the drawing lies over them exactly."""
    sc = bpy.context.scene
    co = sc.camera
    lens, kind = co.data.lens, co.data.type
    co.data.type = "ORTHO"
    floor = bpy.data.objects.get("floor")
    files = []
    for view, (w, h, cx, cz) in ORTHO.items():
        sc.render.resolution_x = int(w * PX_PER_CM)
        sc.render.resolution_y = int(h * PX_PER_CM)
        co.data.ortho_scale = max(w, h) * CM
        if view == "front":
            co.location = (cx * CM, -4.0, cz * CM)
            co.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        elif view == "side":
            co.location = (-4.0, -cx * CM, cz * CM)
            co.rotation_euler = (math.radians(90.0), 0.0, math.radians(-90.0))
        else:
            co.location = (cx * CM, -cz * CM, 4.0)
            co.rotation_euler = (0.0, 0.0, 0.0)
        if floor:
            floor.hide_render = view == "top"
        co.data.clip_end = 10.0
        path = folder / f"ortho_{view}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files.append(path.name)
    if floor:
        floor.hide_render = False
    co.data.type, co.data.lens = kind, lens
    return files


def concept_views(folder_in: Path, folder: Path) -> list:
    """The concept's straight views cut and scaled to the ortho renders' frames ([measure] in console_dims.toml),
    the front and side views stretched as the drawing stretches them: the part above `cut` lifted by `lift` cm, the
    gap filled by the plain rows just under the cut, stretched (drawing.js placed())."""
    import numpy as np

    m = DIMS["measure"]
    lift = m["lift"]
    files = []
    for view, (w, h, cx, cz) in ORTHO.items():
        img = bpy.data.images.load(str(folder_in / f"{view}-ortho.jpg"))
        sw, sh = img.size
        src = np.empty(sw * sh * 4, dtype=np.float32)
        img.pixels.foreach_get(src)
        src = src.reshape(sh, sw, 4)[::-1]  # rows from the top, like the measurements
        tw, th = int(w * PX_PER_CM), int(h * PX_PER_CM)
        us = cx - w / 2 + (np.arange(tw) + 0.5) / PX_PER_CM
        vs = cz + h / 2 - (np.arange(th) + 0.5) / PX_PER_CM  # h (or -d for the top view) per output row
        if view == "top":
            t = m["top"]
            xs = t["cx"] + us * t["px_per_cm"]
            ys = t["cy"] - vs * t["px_per_cm"]
            ok_rows = np.ones(th, dtype=bool)
        else:
            t = m[view]
            k = t["px_per_cm"]
            xs = t["cx"] + us * k  # the side view: d (toward the button) to the right, as the ortho render
            y_disp = t["floor"] - vs * k  # where the row sits in the stretched view
            d = lift * k
            ys = np.where(y_disp >= t["cut"], y_disp,
                          np.where(y_disp < t["cut"] - d, y_disp + d,
                                   t["cut"] + (y_disp - (t["cut"] - d)) / d * 20.0))
            ok_rows = np.ones(th, dtype=bool) if view == "front" else ys >= 440  # the side's hologram came out wrong
        xi = np.clip(xs, 0, sw - 1).astype(int)
        yi = np.clip(ys, 0, sh - 1).astype(int)
        cut = src[yi][:, xi]
        cut[~ok_rows] = (0.05, 0.07, 0.11, 1.0)
        outside = (xs < 0) | (xs > sw - 1)
        cut[:, outside] = (0.05, 0.07, 0.11, 1.0)
        out = bpy.data.images.new(f"concept_{view}", tw, th, alpha=True)
        out.pixels.foreach_set(cut[::-1].ravel())
        path = folder / f"concept_{view}.png"
        out.filepath_raw = str(path)
        out.file_format = "PNG"
        out.save()
        files.append(path.name)
    return files


OVERLAY_HIDDEN = {"front": {"core", "deck", "plates"}, "side": {"core", "deck", "plates"},
                  "top": {"core", "bands", "body", "channels", "button_seat", "strips"}}  # console_drawing.HIDDEN


def overlays(folder: Path) -> list:
    """The drawing over the pictures as PNGs: the pedestal's own edges (the faces toward the viewer, as
    console_drawing.py draws them, in gold), the drawing's heights (orange: the plinth's, the body's and the rim's
    tops, the button's centre, the hologram's hall) and the hologram's box (cyan), over the orthographic render and
    over the concept's stretched view: overlay_<model|concept>_<view>.png."""
    import numpy as np

    d = DIMS
    holo = HULL_STATS.get("bounds_cm")
    heights = [d["plinth"]["h_top"], d["body"]["h0"], d["body"]["h1"], d["rim"]["h0"], d["rim"]["h1"],
               d["button"]["h"], d["hologram"]["disc_h"]]
    files = []
    for view, (w, h, cx, cz) in ORTHO.items():
        tw, th = int(w * PX_PER_CM), int(h * PX_PER_CM)

        def px(p) -> tuple:
            if view == "front":
                return (p[0] - (cx - w / 2)) * PX_PER_CM, (cz + h / 2 - p[2]) * PX_PER_CM
            if view == "side":
                return (-p[1] - (cx - w / 2)) * PX_PER_CM, (cz + h / 2 - p[2]) * PX_PER_CM
            return (p[0] - (cx - w / 2)) * PX_PER_CM, (h / 2 - p[1] + cz) * PX_PER_CM

        facing = {"front": lambda n: -n[1], "side": lambda n: -n[0], "top": lambda n: n[2]}[view]
        segs = []
        for part_name, a, b, normals in FEATURES:
            if part_name in OVERLAY_HIDDEN[view] or (normals and not any(facing(n) > 1e-4 for n in normals)):
                continue
            segs.append((px(a), px(b), (1.0, 0.82, 0.42)))
        if view != "top":
            for z in heights:
                segs.append((px((-w / 2, w / 2, z)) if view == "front" else px((0, w / 2, z)),
                             px((w / 2, -w / 2, z)) if view == "front" else px((0, -w / 2, z)), (1.0, 0.5, 0.2)))
        if holo:
            (x0, y0, z0), (x1, y1, z1) = holo
            box = {"front": [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)],
                   "side": [(0, y0, z0), (0, y1, z0), (0, y1, z1), (0, y0, z1)],
                   "top": [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]}[view]
            for i in range(4):
                segs.append((px(box[i]), px(box[(i + 1) % 4]), (0.5, 0.9, 1.0)))
        for under in ("model", "concept"):
            name = f"ortho_{view}.png" if under == "model" else f"concept_{view}.png"
            if not (folder / name).is_file():
                continue
            img = bpy.data.images.load(str(folder / name))
            pix = np.empty(tw * th * 4, dtype=np.float32)
            img.pixels.foreach_get(pix)
            pix = pix.reshape(th, tw, 4)[::-1].copy()  # rows from the top
            pix[..., :3] *= 0.8
            for (xa, ya), (xb, yb), col in segs:
                n = int(max(abs(xb - xa), abs(yb - ya)) * 2) + 2
                t = np.linspace(0.0, 1.0, n)
                xs = np.clip(np.round(xa + (xb - xa) * t).astype(int), 0, tw - 1)
                ys = np.clip(np.round(ya + (yb - ya) * t).astype(int), 0, th - 1)
                pix[ys, xs, :3] = col
            out = bpy.data.images.new(f"overlay_{under}_{view}", tw, th, alpha=True)
            out.pixels.foreach_set(pix[::-1].ravel())
            path = folder / f"overlay_{under}_{view}.png"
            out.filepath_raw = str(path)
            out.file_format = "PNG"
            out.save()
            files.append(path.name)
    return files


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    ob = build(Path(a["pieces"]))
    info = export(ob, out)
    (out / "features.json").write_text(json.dumps({"units": "cm, Blender axes (Z up, front -Y)",
                                                   "edges": FEATURES}) + "\n", encoding="utf-8")
    set_state("idle")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "start_console.blend"), compress=True)
    renders = []
    if a["render"]:
        folder = Path(a["render"])
        folder.mkdir(parents=True, exist_ok=True)
        stage(a["res"], a["samples"], a["hdri"])
        for state in STATE_VIEWS:
            set_state(state)
            renders += shoot(folder, state, a["res"])
        set_state("idle")
        renders += shoot_ortho(folder)
        if a["views"]:
            renders += concept_views(Path(a["views"]), folder)
        renders += overlays(folder)
    info["renders"] = renders
    (out / "build.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print("CONSOLE_BUILD " + json.dumps(info))


main()
