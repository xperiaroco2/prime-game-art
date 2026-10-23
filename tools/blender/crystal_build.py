"""The ship engine's energy crystal (art#263's station props; the cartridge decided on prime-game#1033): a faceted
crystal in a bronze and graphite cap with a hexagonal carry loop, built from code in headless Blender (no Meshy).
The driver (crystal_run.py) calls it; by hand, background only:

  blender -b --factory-startup --python-exit-code 1 --python tools/blender/crystal_build.py -- \
      --out <dir> [--render <dir>] [--res 900] [--samples 64]

Blender axes: Z up, front -Y (glTF: Y up, front +Z); origin at the crystal's tip, the lowest point, under its middle.

The shape (concept: prime-game-design ideas/ship-components/cartridge-v2, socket-claws.jpg and charge.jpg):
- the crystal: a hexagonal column of alternating rings (corners, then face middles 30 degrees on), so every band of
  triangles makes long diamond facets; flat faces on the hexagon's sides, the corners cut by the diamonds; a faceted
  taper to a point below and a shoulder into the cap above; every facet edge a thin chamfer;
- the core: a slimmer copy turned 30 degrees inside the crystal; seen through the charged crystal it is the inner
  glow and the second set of facet lines the concept paints;
- the cap: a bronze collar lip, a graphite hexagonal skirt with inset panels and two bronze claws on the crystal's
  shoulder, the widest band (two bronze rims, a graphite groove with four cyan windows and a chevron plate front and
  back), a bevelled dome, a boss with a cyan lens, two lugs and the hexagonal loop.

Every metal edge over 30 degrees gets a 1.2 mm chamfer (0.6 mm on the crystal); the chamfer faces are marked in UV0
(u = 1) so the materials brighten them (the worn bronze edges, the crystal's glinting edges); UV0's v holds a
per-facet random value for the crystal's facet-by-facet shade. No textures.

The two states are one mesh and one charge value: 1 charged (cyan, translucent, glowing from the core, the cap's
lights full), 0 spent (matte grey stone, no glow, the lights dimmed). The Blender look reads the node group
`crystal_charge`; the game's look is godot/crystal/crystal.gd (set_charge).

Writes into --out: energy_crystal.glb (the plain-PBR fallback, the charged state), energy_crystal.blend (the look
materials, charge 1), build.json (triangles per part and material, size). With --render, review renders of both
states into that folder: <state>_<view>.png.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

# --- sizes (metres) ------------------------------------------------------------------------------------------------
R = 0.060                      # the crystal's corner radius: 12.0 cm across the corners, 10.4 cm across the flats
BULGE = 1.12                   # the face middles' inner vertices sit this much outside the flat faces: facets fold
BODY_Z0, BODY_STEP, BODY_STEPS = 0.048, 0.0415, 4
TIP_RING = (0.022, 0.50)       # the taper's ring under the face middles: height, share of the apothem
SHOULDER = (0.232, 0.84)       # the shoulder ring into the cap (corners): height, share of R
TOP_RING = (0.246, 0.62)       # hidden inside the collar
CHAMFER_METAL, CHAMFER_SMALL, CHAMFER_CRYSTAL = 0.0012, 0.0008, 0.0006
CAP_SIDES = 16


def argv() -> dict:
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {"out": None, "render": None, "res": 900, "samples": 64}
    i = 0
    while i < len(a):
        key = a[i].lstrip("-")
        out[key] = a[i + 1]
        i += 2
    out["res"] = int(out["res"])
    out["samples"] = int(out["samples"])
    return out


# --- mesh helpers --------------------------------------------------------------------------------------------------
def ring(bm, r: float, z: float, sides: int, rot_deg: float) -> list:
    return [bm.verts.new((r * math.cos(math.radians(rot_deg + 360.0 * j / sides)),
                          r * math.sin(math.radians(rot_deg + 360.0 * j / sides)), z)) for j in range(sides)]


def lathe(bm, prof: list, sides: int, rot_deg: float = 0.0, bottom: bool = True, top: bool = True) -> list:
    """A solid of revolution with flat sides: prof is [(r, z), ...] from the bottom up; returns the rings."""
    rings = [ring(bm, r, z, sides, rot_deg) for r, z in prof]
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


def box(bm, centre, size, yaw_deg: float = 0.0) -> list:
    """A box about centre (x, y, z), size (along its local x, y, z), turned yaw_deg about Z; returns its faces."""
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res["verts"]
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    for v in verts:
        x, y, z = v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]
        v.co = Vector((centre[0] + x * c - y * s, centre[1] + x * s + y * c, centre[2] + z))
    return list({f for v in verts for f in v.link_faces})


def radial(angle_deg: float, r: float, z: float) -> tuple:
    a = math.radians(angle_deg)
    return (r * math.cos(a), r * math.sin(a), z)


def crystal_column(bm, scale: float, rot_deg: float, z_lift: float, z_squash: float) -> None:
    """The faceted crystal: a hexagonal column whose corners run straight up (vertices at every step), each face
    holding a column of long diamonds: its middle line has a vertex every other step, a little outside the flat face
    (BULGE), so the facets fold and catch the light; neighbouring faces are staggered by a step, so the diamonds'
    sides run on across the corners as one lattice. A faceted taper to a point below, a shoulder into the cap above,
    a flat top hidden inside it. scale shrinks the radii (the core), rot_deg turns it, z_lift and z_squash move and
    compress its heights about the body's middle."""
    top = BODY_Z0 + BODY_STEPS * BODY_STEP
    mid = 0.5 * (BODY_Z0 + top)

    def zz(z: float) -> float:
        return mid + (z - mid) * z_squash + z_lift

    def at(angle: float, r: float, z: float):
        a = math.radians(rot_deg + angle)
        return bm.verts.new((r * scale * math.cos(a), r * scale * math.sin(a), zz(z)))

    steps = [BODY_Z0 + i * BODY_STEP for i in range(BODY_STEPS + 1)]
    apothem = R * math.cos(math.radians(30.0))
    corners = [[at(60.0 * j, R, z) for z in steps] for j in range(6)]
    end_mids = {}
    for j in range(6):
        left, right = corners[j], corners[(j + 1) % 6]
        mids = []
        for i, z in enumerate(steps):
            end = i in (0, BODY_STEPS)
            if (i + j) % 2 == 1 or end:
                # the ends' middles lie on the flat face (the rings there stay hexagons); the inner ones bulge
                mids.append((i, at(60.0 * j + 30.0, apothem * (1.0 if end else BULGE), z)))
                if end:
                    end_mids[(j, i)] = mids[-1][1]
        # zip the middle line to each corner line: every corner vertex meets the middle vertex beside it
        for col, flip in ((left, False), (right, True)):
            for (i0, m0), (i1, m1) in zip(mids, mids[1:]):
                for i in range(i0, i1):
                    f = (col[i], col[i + 1], m1 if i + 1 > (i0 + i1) / 2 else m0)
                    bm.faces.new(f if not flip else tuple(reversed(f)))
                bm.faces.new((col[(i0 + i1) // 2], m1, m0) if not flip else (m0, m1, col[(i0 + i1) // 2]))
    # the ends: a 12-vertex ring each (the corners and the flat middles)
    def end_ring(i: int) -> list:
        out = []
        for j in range(6):
            out.append(corners[j][i])
            out.append(end_mids[(j, i)])
        return out

    def taper(ring12: list, z: float, share: float, point: float | None) -> None:
        # a 6-vertex ring under (or over) the face middles, then a point or a flat cap
        t = [at(60.0 * j + 30.0, apothem * share, z) for j in range(6)]
        for j in range(6):
            c, m, c2 = ring12[2 * j], ring12[2 * j + 1], ring12[(2 * j + 2) % 12]
            bm.faces.new((c, m, t[j]))
            bm.faces.new((m, c2, t[j]))
            bm.faces.new((c2, t[(j + 1) % 6], t[j]))
        if point is None:
            bm.faces.new(t)
        else:
            tip = bm.verts.new((0.0, 0.0, zz(point)))
            for j in range(6):
                bm.faces.new((t[j], t[(j + 1) % 6], tip))

    taper(end_ring(0), TIP_RING[0], TIP_RING[1], 0.0)
    shoulder = end_ring(BODY_STEPS)
    s6 = [at(60.0 * j, R * SHOULDER[1], SHOULDER[0]) for j in range(6)]
    for j in range(6):
        c, m, c2 = shoulder[2 * j], shoulder[2 * j + 1], shoulder[(2 * j + 2) % 12]
        bm.faces.new((c, m, s6[j]))
        bm.faces.new((m, c2, s6[(j + 1) % 6]))
        bm.faces.new((m, s6[(j + 1) % 6], s6[j]))
    t6 = [at(60.0 * j, R * TOP_RING[1], TOP_RING[0]) for j in range(6)]
    for j in range(6):
        k = (j + 1) % 6
        bm.faces.new((s6[j], s6[k], t6[k], t6[j]))
    bm.faces.new(t6)


def sweep_loop(bm, pts: list, width: float, depth: float) -> None:
    """A bar of width (in the loop's plane, XZ) by depth (along Y) along the polyline pts [(x, z), ...] with mitred
    corners and closed ends."""
    n = len(pts)
    P = [Vector((x, z)) for x, z in pts]
    sections = []
    for i in range(n):
        if i == 0:
            d = (P[1] - P[0]).normalized()
            nrm = Vector((-d.y, d.x))
            k = 1.0
        elif i == n - 1:
            d = (P[i] - P[i - 1]).normalized()
            nrm = Vector((-d.y, d.x))
            k = 1.0
        else:
            d0 = (P[i] - P[i - 1]).normalized()
            d1 = (P[i + 1] - P[i]).normalized()
            n0, n1 = Vector((-d0.y, d0.x)), Vector((-d1.y, d1.x))
            nrm = (n0 + n1).normalized()
            k = 1.0 / max(0.3, nrm.dot(n0))
        sec = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            q = P[i] + nrm * (sx * width * 0.5 * k)
            sec.append(bm.verts.new((q.x, sy * depth * 0.5, q.y)))
        sections.append(sec)
    for i in range(n - 1):
        a, b = sections[i], sections[i + 1]
        for j in range(4):
            k = (j + 1) % 4
            bm.faces.new((a[j], a[k], b[k], b[j]))
    bm.faces.new(sections[0])
    bm.faces.new(list(reversed(sections[-1])))


def prism(bm, poly: list, angle_deg: float, half_width: float) -> None:
    """A part drawn in the radial plane at angle_deg (poly: [(r, z), ...], counter-clockwise seen from the tangent
    side) extruded half_width to each side along the tangent."""
    a = math.radians(angle_deg)
    rad, tan = Vector((math.cos(a), math.sin(a), 0.0)), Vector((-math.sin(a), math.cos(a), 0.0))
    sides = []
    for s in (-1, 1):
        sides.append([bm.verts.new(rad * r + Vector((0, 0, z)) + tan * (s * half_width)) for r, z in poly])
    n = len(poly)
    bm.faces.new(sides[0])
    bm.faces.new(list(reversed(sides[1])))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((sides[0][j], sides[0][i], sides[1][i], sides[1][j]))


# --- the parts -----------------------------------------------------------------------------------------------------
def part(name: str, build, mat_name: str, chamfer: float, extra=None, angle: float = 30.0,
         more: tuple = ()) -> bpy.types.Object:
    """One part: its own material in slot 0, the chamfer marker in slot 1, `more` materials from slot 2 (a builder
    puts faces there by material_index)."""
    bm = bmesh.new()
    build(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if extra:
        extra(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(MATS[mat_name])
    me.materials.append(MATS["_chamfer"])
    for extra_mat in more:
        me.materials.append(MATS[extra_mat])
    if chamfer > 0:
        mod = ob.modifiers.new("chamfer", "BEVEL")
        mod.width = chamfer
        mod.segments = 1
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(angle)
        mod.material = 1
        mod.harden_normals = False
    return ob


def build_crystal(bm) -> None:
    crystal_column(bm, 1.0, 0.0, 0.0, 1.0)


def build_core(bm) -> None:
    crystal_column(bm, 0.52, 30.0, 0.012, 0.86)


def build_skirt(bm) -> None:
    # the graphite hexagonal skirt: narrow at the crystal, wide under the band; its six faces inset as panels
    lathe(bm, [(0.0585, 0.2350), (0.0620, 0.2390), (0.0690, 0.2700)], 6, 0.0)


def skirt_panels(bm) -> None:
    faces = [f for f in bm.faces if abs(f.normal.z) < 0.6 and f.calc_center_median().z > 0.2385]
    bmesh.ops.inset_individual(bm, faces=faces, thickness=0.0065, depth=-0.0016)
    for f in faces:  # the inset keeps the original faces in the middle: the dark panels in a bronze frame
        f.material_index = 2


def build_collar(bm) -> None:
    # the bronze lip where the crystal meets the cap
    lathe(bm, [(0.0580, 0.2285), (0.0605, 0.2295), (0.0610, 0.2345), (0.0585, 0.2365)], 6, 0.0)


def build_claws(bm) -> None:
    # thin claws hugging the crystal's two side corners, from under the band down onto the shoulder
    poly = [(0.0605, 0.2170), (0.0645, 0.2165), (0.0668, 0.2330), (0.0700, 0.2500), (0.0700, 0.2690),
            (0.0648, 0.2690), (0.0632, 0.2500), (0.0605, 0.2330)]
    for ang in (0.0, 180.0):
        prism(bm, poly, ang, 0.0055)


def build_band(bm) -> None:
    # bronze: lower rim, the groove's floor (hidden behind the graphite band), upper rim, the dome, the boss, the
    # lens recess
    lathe(bm, [(0.0620, 0.2690), (0.0670, 0.2710), (0.0670, 0.2713), (0.0598, 0.2715), (0.0598, 0.2850),
               (0.0670, 0.2852), (0.0670, 0.2915), (0.0655, 0.2918), (0.0655, 0.2926), (0.0670, 0.2929),
               (0.0670, 0.2990), (0.0645, 0.3010), (0.0360, 0.3110), (0.0285, 0.3118),
               (0.0285, 0.3185), (0.0262, 0.3208), (0.0150, 0.3208), (0.0142, 0.3178)],
          CAP_SIDES, 180.0 / CAP_SIDES)


def build_groove(bm) -> None:
    lathe(bm, [(0.0628, 0.2712), (0.0628, 0.2853)], CAP_SIDES, 180.0 / CAP_SIDES, bottom=False, top=False)


SLOT_ANGLES = (270.0 - 48.0, 270.0 + 48.0, 90.0 - 48.0, 90.0 + 48.0)


def build_slot_frames(bm) -> None:
    # four window frames on the groove; each front face inset into a recessed window (the light material)
    for ang in SLOT_ANGLES:
        faces = box(bm, radial(ang, 0.0638, 0.2782), (0.0040, 0.0200, 0.0092), ang)
        front = max(faces, key=lambda f: f.calc_center_median().to_2d().length)
        bmesh.ops.inset_individual(bm, faces=[front], thickness=0.0022, depth=-0.0012)
        front.material_index = 2  # the window (the inset keeps the original face in the middle): the light


def build_chevrons(bm) -> None:
    # a small chevron plate front and back on the groove (the concept's notch)
    for ang in (270.0, 90.0):
        a = math.radians(ang)
        rad, tan = Vector((math.cos(a), math.sin(a), 0.0)), Vector((-math.sin(a), math.cos(a), 0.0))
        outline = [(-0.0075, 0.2722), (0.0075, 0.2722), (0.0075, 0.2800), (0.0030, 0.2842), (-0.0030, 0.2842),
                   (-0.0075, 0.2800)]
        layers = []
        for r in (0.0610, 0.0650):
            layers.append([bm.verts.new(rad * r + tan * t + Vector((0, 0, z))) for t, z in outline])
        n = len(outline)
        bm.faces.new(list(reversed(layers[0])))
        bm.faces.new(layers[1])
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((layers[0][i], layers[0][j], layers[1][j], layers[1][i]))


def build_lens(bm) -> None:
    lathe(bm, [(0.0138, 0.3176), (0.0138, 0.3190)], CAP_SIDES, 180.0 / CAP_SIDES)


LOOP = [(-0.040, 0.303), (-0.040, 0.322), (-0.022, 0.347), (0.022, 0.347), (0.040, 0.322), (0.040, 0.303)]


def build_loop(bm) -> None:
    sweep_loop(bm, LOOP, 0.0115, 0.0130)


def build_lugs(bm) -> None:
    for x in (-0.040, 0.040):
        box(bm, (x, 0.0, 0.3095), (0.0170, 0.0200, 0.0120))


# --- materials -----------------------------------------------------------------------------------------------------
MATS: dict = {}
CYAN = (0.0, 0.72, 1.0, 1.0)      # saturated: AgX bleaches a bright pale cyan to white


def charge_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.new("crystal_charge", "ShaderNodeTree")
    ng.interface.new_socket(name="Charge", in_out="OUTPUT", socket_type="NodeSocketFloat")
    out = ng.nodes.new("NodeGroupOutput")
    val = ng.nodes.new("ShaderNodeValue")
    val.name = "charge"
    val.outputs[0].default_value = 1.0
    ng.links.new(val.outputs[0], out.inputs[0])
    return ng


def set_charge(c: float) -> None:
    bpy.data.node_groups["crystal_charge"].nodes["charge"].outputs[0].default_value = c


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

    def charge(self):
        g = self.n("ShaderNodeGroup")
        g.node_tree = bpy.data.node_groups["crystal_charge"]
        return g.outputs[0]

    def uv(self):
        u = self.n("ShaderNodeUVMap")
        u.uv_map = "UVMap"
        sep = self.n("ShaderNodeSeparateXYZ")
        self.nt.links.new(u.outputs[0], sep.inputs[0])
        return sep.outputs[0], sep.outputs[1]  # flag, random

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
    noise = nd.n("ShaderNodeTexNoise", Scale=55.0, Detail=4.0)
    nd.nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    big = nd.n("ShaderNodeTexNoise", Scale=9.0, Detail=2.0)
    nd.nt.links.new(tc.outputs["Object"], big.inputs["Vector"])
    # the worn edge: the chamfer, broken up a little by the fine noise
    wear = nd.math("MULTIPLY", flag, nd.math("ADD", nd.math("MULTIPLY", noise.outputs[0], 0.6), 0.55))
    wear = nd.math("MINIMUM", wear, 1.0)
    shade = nd.math("ADD", nd.math("MULTIPLY", big.outputs[0], 0.25), 0.88)
    col = nd.mix_rgb(wear, base, worn)
    col2 = nd.n("ShaderNodeVectorMath")
    col2.operation = "SCALE"
    nd.nt.links.new(col, col2.inputs[0])
    nd.set(col2, "Scale", shade)
    r = nd.math("ADD", rough, nd.math("SUBTRACT", nd.math("MULTIPLY", noise.outputs[0], 0.16), 0.08))
    r = nd.math("SUBTRACT", r, nd.math("MULTIPLY", wear, 0.14))
    b = bsdf(nd, Metallic=metallic, Roughness=r)
    nd.nt.links.new(col2.outputs[0], b.inputs["Base Color"])
    nd.output(b)
    return mat


def build_materials() -> None:
    charge_group()
    MATS["crystal_bronze"] = metal_material("crystal_bronze", (0.42, 0.29, 0.17, 1.0), (0.92, 0.74, 0.52, 1.0),
                                            0.36, 1.0)
    MATS["crystal_graphite"] = metal_material("crystal_graphite", (0.075, 0.075, 0.082, 1.0),
                                              (0.42, 0.40, 0.37, 1.0), 0.42, 0.8)

    # the cap's lights: full when charged, a dim glow when spent
    mat = bpy.data.materials.new("crystal_light")
    nd = Nodes(mat)
    strength = nd.math("MULTIPLY", 3.2, nd.math("ADD", 0.22, nd.math("MULTIPLY", nd.charge(), 0.78)))
    b = bsdf(nd, **{"Base Color": (0.02, 0.05, 0.06, 1.0), "Roughness": 0.2, "Emission Color": CYAN})
    nd.set(b, "Emission Strength", strength)
    nd.output(b)
    MATS["crystal_light"] = mat

    # the crystal's shell: charged, a tinted translucent gem with a facet-by-facet glow and bright edges; spent, a
    # matte grey stone; the charge mixes the two
    mat = bpy.data.materials.new("crystal_shell")
    nd = Nodes(mat)
    flag, rnd = nd.uv()
    ch = nd.charge()
    lw = nd.n("ShaderNodeLayerWeight", Blend=0.35)
    alpha = nd.math("ADD", 0.62, nd.math("MULTIPLY", lw.outputs["Facing"], 0.38))
    alpha = nd.math("MAXIMUM", alpha, nd.math("MULTIPLY", flag, 0.9))
    glow = nd.math("ADD", nd.math("MULTIPLY", nd.math("POWER", rnd, 2.0), 0.6), 0.12)
    glow = nd.math("ADD", glow, nd.math("MULTIPLY", flag, 0.3))
    hot = nd.mix_rgb(flag, (0.0, 0.62, 1.0, 1.0), (0.10, 0.85, 1.0, 1.0))
    charged = bsdf(nd, **{"Base Color": (0.0, 0.10, 0.24, 1.0), "Roughness": 0.1, "IOR": 1.55,
                          "Specular IOR Level": 0.2, "Alpha": alpha, "Emission Strength": glow})
    nd.nt.links.new(hot, charged.inputs["Emission Color"])
    grey = nd.math("ADD", 0.085, nd.math("MULTIPLY", rnd, 0.05))
    grey = nd.math("ADD", grey, nd.math("MULTIPLY", flag, 0.04))
    gcol = nd.n("ShaderNodeCombineXYZ")
    for i, k in enumerate((1.0, 1.06, 1.18)):
        nd.set(gcol, i, nd.math("MULTIPLY", grey, k))
    spent = bsdf(nd, Roughness=0.7, **{"Specular IOR Level": 0.35})
    nd.nt.links.new(gcol.outputs[0], spent.inputs["Base Color"])
    mix = nd.n("ShaderNodeMixShader")
    nd.set(mix, 0, ch)
    nd.nt.links.new(spent.outputs[0], mix.inputs[1])
    nd.nt.links.new(charged.outputs[0], mix.inputs[2])
    nd.output(mix)
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True  # like the game's cull_back: the far side's facets stacked into a milky haze
    mat.use_transparency_overlap = False
    MATS["crystal_shell"] = mat

    # the core: the glow inside, its own edges brighter; dark when spent (hidden behind the opaque stone)
    mat = bpy.data.materials.new("crystal_core")
    nd = Nodes(mat)
    flag, rnd = nd.uv()
    ch = nd.charge()
    glow = nd.math("ADD", nd.math("MULTIPLY", rnd, 0.5), 0.55)
    glow = nd.math("ADD", glow, nd.math("MULTIPLY", flag, 0.3))
    glow = nd.math("MULTIPLY", glow, ch)
    hot = nd.mix_rgb(flag, (0.0, 0.62, 1.0, 1.0), (0.08, 0.82, 1.0, 1.0))
    b = bsdf(nd, **{"Base Color": (0.10, 0.11, 0.12, 1.0), "Roughness": 0.5, "Emission Strength": glow})
    nd.nt.links.new(hot, b.inputs["Emission Color"])
    nd.output(b)
    MATS["crystal_core"] = mat

    MATS["_chamfer"] = bpy.data.materials.new("_chamfer")  # a marker slot: the bevel's faces, sorted in join()


# --- assembly ------------------------------------------------------------------------------------------------------
def facet_random(co: Vector) -> float:
    h = math.sin(co.x * 1271.1 + co.y * 3117.7 + co.z * 743.3) * 43758.5453
    return h - math.floor(h)


def join(objs: list) -> bpy.types.Object:
    """Applies each part's chamfer, writes UV0 (u: chamfer face, v: the facet's random value), gives every face its
    part's material in one shared slot list, joins the parts into one object."""
    order = ["crystal_shell", "crystal_core", "crystal_bronze", "crystal_graphite", "crystal_light"]
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
        for f in bm.faces:
            slot_name = me.materials[f.material_index].name if f.material_index < len(me.materials) else own
            is_chamfer = slot_name == "_chamfer"
            name = own if is_chamfer else slot_name
            f.material_index = order.index(name)
            r = facet_random(f.calc_center_median())
            for lp in f.loops:
                lp[uv].uv = (1.0 if is_chamfer else 0.0, r)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        stats[ob.name] = tris
        tmp = bpy.data.meshes.new("tmp")
        bm.to_mesh(tmp)
        bm.free()
        bm_all.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new("energy_crystal")
    lowest = min(v.co.z for v in bm_all.verts)  # the chamfer lifts the tip: the origin goes back under it
    for v in bm_all.verts:
        v.co.z -= lowest
    bm_all.to_mesh(me)
    bm_all.free()
    for name in order:
        me.materials.append(MATS[name])
    for p in me.polygons:
        p.use_smooth = False
    for ob in objs:
        bpy.data.objects.remove(ob)
    out = bpy.data.objects.new("energy_crystal", me)
    bpy.context.collection.objects.link(out)
    out["part_triangles"] = json.dumps(stats)
    return out


def build() -> bpy.types.Object:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    build_materials()
    parts = [
        # every facet edge of the crystal gets its chamfer line, however shallow the fold
        part("crystal", build_crystal, "crystal_shell", CHAMFER_CRYSTAL, angle=2.0),
        part("core", build_core, "crystal_core", CHAMFER_CRYSTAL, angle=2.0),
        part("skirt", build_skirt, "crystal_bronze", CHAMFER_SMALL, skirt_panels, more=("crystal_graphite",)),
        part("collar", build_collar, "crystal_bronze", CHAMFER_SMALL),
        part("claws", build_claws, "crystal_bronze", CHAMFER_SMALL),
        part("band", build_band, "crystal_bronze", CHAMFER_METAL),
        part("groove", build_groove, "crystal_graphite", 0.0),
        part("slot_frames", build_slot_frames, "crystal_bronze", CHAMFER_SMALL, more=("crystal_light",)),
        part("chevrons", build_chevrons, "crystal_bronze", CHAMFER_SMALL),
        part("lens", build_lens, "crystal_light", 0.0),
        part("loop", build_loop, "crystal_bronze", CHAMFER_METAL),
        part("lugs", build_lugs, "crystal_bronze", CHAMFER_SMALL),
    ]
    return join(parts)


# --- export --------------------------------------------------------------------------------------------------------
def plain_materials() -> dict:
    """Plain Principled copies for the GLB's fallback (the charged state): the exporter reads only plain BSDFs."""
    spec = {
        "crystal_shell": dict(base=(0.10, 0.62, 0.92, 0.72), metallic=0.0, rough=0.06, emit=CYAN[:3], strength=1.2,
                              blend=True),
        "crystal_core": dict(base=(0.10, 0.11, 0.12, 1.0), metallic=0.0, rough=0.5, emit=CYAN[:3], strength=4.0),
        "crystal_bronze": dict(base=(0.50, 0.32, 0.17, 1.0), metallic=1.0, rough=0.36),
        "crystal_graphite": dict(base=(0.08, 0.08, 0.088, 1.0), metallic=0.8, rough=0.42),
        "crystal_light": dict(base=(0.02, 0.05, 0.06, 1.0), metallic=0.0, rough=0.2, emit=CYAN[:3], strength=6.0),
    }
    out = {}
    for name, s in spec.items():
        mat = bpy.data.materials.new(name + "_plain")
        nd = Nodes(mat)
        b = bsdf(nd, **{"Base Color": s["base"], "Metallic": s["metallic"], "Roughness": s["rough"]})
        if s.get("blend"):
            nd.set(b, "Alpha", s["base"][3])
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
    bpy.ops.export_scene.gltf(filepath=str(out / "energy_crystal.glb"), export_format="GLB", use_selection=True,
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
    return {"triangles": sum(tris.values()), "triangles_by_material": tris,
            "triangles_by_part": json.loads(ob["part_triangles"]), "vertices": len(me.vertices),
            "size_m": [round(hi[i] - lo[i], 4) for i in range(3)], "min_m": [round(x, 4) for x in lo],
            "max_m": [round(x, 4) for x in hi]}


# --- review renders ------------------------------------------------------------------------------------------------
VIEWS = {  # name: (yaw from the front, elevation, framing: the share of the height shown, look-at lift in m)
    "q34": (-35.0, 14.0, 1.0, 0.0),
    "front": (0.0, 4.0, 1.0, 0.0),
    "top": (0.0, 88.0, 0.5, 0.13),
    "cap": (-30.0, 18.0, 0.34, 0.105),
    "loop": (20.0, 32.0, 0.24, 0.15),
    "facets": (-20.0, 6.0, 0.42, -0.05),
}


def stage(res: int, samples: int) -> None:
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
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.020, 0.026, 0.045, 1.0)
    bg.inputs[1].default_value = 1.0
    # the ship's interior at night: warm amber lamps (ship.toml [light] lamps: 1.0, 0.7, 0.42), a cool rim like the
    # night key, a dark blue ambient
    for name, loc, energy, colour, size in (("lamp_warm", (-0.55, -0.75, 0.75), 16.0, (1.0, 0.72, 0.46), 0.25),
                                            ("rim_cool", (0.6, 0.55, 0.65), 12.0, (0.62, 0.74, 1.0), 0.3),
                                            ("fill", (0.75, -0.6, 0.1), 3.0, (0.85, 0.85, 1.0), 0.5)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.color = colour
        ld.size = size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        d = Vector((0.0, 0.0, 0.18)) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bloom(sc)
    cam = bpy.data.cameras.new("cam")
    cam.lens = 85.0
    co = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co


def bloom(sc) -> None:
    """A soft bloom in the compositor, like the game's glow on the emissive parts; skipped (with a line) where this
    Blender's compositor API differs."""
    try:
        tree = bpy.data.node_groups.new("crystal_bloom", "CompositorNodeTree")
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = tree.nodes.new("CompositorNodeRLayers")
        gl = tree.nodes.new("CompositorNodeGlare")
        out = tree.nodes.new("NodeGroupOutput")
        for key, value in (("Type", "Bloom"), ("Threshold", 1.0), ("Strength", 0.6), ("Size", 0.5)):
            if key in gl.inputs:
                gl.inputs[key].default_value = value
        if hasattr(gl, "glare_type"):
            gl.glare_type = "BLOOM"
        tree.links.new(rl.outputs["Image"], gl.inputs["Image"])
        tree.links.new(gl.outputs["Image"], out.inputs[0])
        sc.compositing_node_group = tree
        sc.render.use_compositing = True
        print("CRYSTAL_BLOOM on")
    except Exception as exc:  # noqa: BLE001 - an optional nicety of the review renders
        print(f"CRYSTAL_BLOOM off: {exc}")


def shoot(ob, folder: Path, state: str, res: int) -> list:
    sc = bpy.context.scene
    co = sc.camera
    height = ob.dimensions.z
    centre = Vector((0.0, 0.0, height * 0.5))
    files = []
    for view, (yaw, elev, frame, lift) in VIEWS.items():
        target = centre + Vector((0.0, 0.0, lift))
        span = height * frame * 1.12
        fov = 2.0 * math.atan(36.0 / (2.0 * co.data.lens))
        dist = span * 0.5 / math.tan(fov * 0.5)
        y, e = math.radians(yaw), math.radians(elev)
        # yaw 0: the front, -Y in Blender
        offset = Vector((math.sin(y) * math.cos(e), -math.cos(y) * math.cos(e), math.sin(e))) * dist
        co.location = target + offset
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
        path = folder / f"{state}_{view}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files.append(path.name)
    return files


def main() -> None:
    a = argv()
    out = Path(a["out"])
    out.mkdir(parents=True, exist_ok=True)
    ob = build()
    info = export(ob, out)
    set_charge(1.0)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "energy_crystal.blend"), compress=True)
    renders = []
    if a["render"]:
        folder = Path(a["render"])
        folder.mkdir(parents=True, exist_ok=True)
        stage(a["res"], a["samples"])
        for state, c in (("charged", 1.0), ("spent", 0.0)):
            set_charge(c)
            renders += shoot(ob, folder, state, a["res"])
    info["renders"] = renders
    (out / "build.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print("CRYSTAL_BUILD " + json.dumps(info))


main()
