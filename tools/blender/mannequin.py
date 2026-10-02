"""Builds our own simple low-poly base body by script (a blockout and the reference image for image-to-3D).

Run through the runner (`tools/run.py mannequin`), or directly:
    blender -b --factory-startup --python-exit-code 1 --python tools/blender/mannequin.py -- \
        --preset base --out DIR [--size 1024] [--no-refs]

Every shape is a loft of elliptical rings (bmesh), nothing is traced or copied from any model: an egg-shaped bald head
with a long simple nose and no eyes or mouth (they are changeable slots later), ears, a slightly lanky adult body,
a T-pose with the arms horizontal and the palms down, five separate fingers per hand (three segments each), bare feet
with five simple toes, and a plain t-shirt and shorts as separate flat-coloured objects over the body.

Blender axes: Z up, the model faces -Y (+Z in glTF), its left is +X; feet at z = 0, the top of the head at exactly
1.75 m (the whole figure is scaled to that height last). Writes into --out:
    mannequin_<preset>.glb, mannequin_<preset>.blend, info.json,
    refs/front.png, side.png, back.png (soft even light) and refs_flat/... (unlit flat colour), unless --no-refs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402

HEIGHT = 1.75

# Proportion multipliers per preset; 1.0 is the base figure. The figure is scaled to HEIGHT afterwards, so a bigger
# head makes the body a little shorter rather than the figure taller.
PRESETS: dict[str, dict[str, float]] = {
    # Near-human, slightly lanky: long legs and arms, narrow shoulders, a head a little big for the body.
    "base": {"head": 1.0, "nose": 1.0, "limb": 1.0, "torso": 1.0, "neck": 1.0, "leg": 1.0, "arm": 1.0},
    # Lankier: thinner limbs and torso, a longer neck and legs, a slightly longer nose.
    "lanky": {"head": 0.96, "nose": 1.15, "limb": 0.84, "torso": 0.9, "neck": 1.3, "leg": 1.08, "arm": 1.05},
    # A bigger head and a longer nose on the base body, a little more cartoony.
    "bighead": {"head": 1.2, "nose": 1.15, "limb": 1.0, "torso": 1.0, "neck": 0.85, "leg": 0.96, "arm": 1.0},
}

# Flat colours (sRGB); the shared palette replaces them later.
COLOURS = {"Skin": (0.87, 0.64, 0.49), "Shirt": (0.24, 0.5, 0.72), "Shorts": (0.36, 0.32, 0.27)}

SEGMENTS = 12  # around a limb, the torso or the head; divisible by 4 so a ring has a lowest point


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="mannequin.py")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="base")
    parser.add_argument("--out", required=True, help="the folder the files go to")
    parser.add_argument("--size", type=int, default=1024, help="pixel size of the square reference images")
    parser.add_argument("--no-refs", action="store_true", help="no reference images")
    return parser.parse_args(argv)


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def perpendicular(axis: Vector, hint: Vector) -> tuple[Vector, Vector]:
    """Two unit vectors at right angles to axis: u as close to hint as possible, and v = axis x u."""
    axis = axis.normalized()
    u = hint - axis * hint.dot(axis)
    if u.length < 1e-6:
        u = Vector((0.0, 0.0, 1.0)) - axis * axis.z
    u.normalize()
    return u, axis.cross(u).normalized()


class Builder:
    """Collects lofted shells into one bmesh with a UV layer; each shell is closed (a fan at each end)."""

    def __init__(self) -> None:
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.shells = 0

    def loft(self, rings: list[tuple[Vector, Vector, Vector, float, float]], start: Vector, end: Vector,
             segments: int = SEGMENTS) -> None:
        """rings: (centre, u, v, radius along u, radius along v), in order; start and end: the tips of the end fans."""
        bm = self.bm
        columns = len(rings) + 1
        loops = []
        for centre, u, v, ru, rv in rings:
            loops.append([bm.verts.new(centre + u * (ru * math.cos(a)) + v * (rv * math.sin(a)))
                          for a in (2 * math.pi * k / segments for k in range(segments))])
        tips = (bm.verts.new(start), bm.verts.new(end))

        def uv_at(column: float, k: int) -> tuple[float, float]:
            # Shells are laid side by side in strips of 0.1 so the map stays in 0..1.
            strip = (self.shells % 10) * 0.1
            return strip + 0.1 * k / segments, column / columns

        faces = []
        for i in range(len(loops) - 1):
            a, b = loops[i], loops[i + 1]
            for k in range(segments):
                k2 = (k + 1) % segments
                face = bm.faces.new((a[k], a[k2], b[k2], b[k]))
                coords = (uv_at(i + 0.5, k), uv_at(i + 0.5, k + 1), uv_at(i + 1.5, k + 1), uv_at(i + 1.5, k))
                faces.append((face, coords))
        for tip, loop, column in ((tips[0], loops[0], 0.0), (tips[1], loops[-1], columns)):
            edge = 0.5 if column == 0.0 else columns - 0.5
            for k in range(segments):
                face = bm.faces.new((tip, loop[(k + 1) % segments], loop[k]))
                faces.append((face, (uv_at(column, k), uv_at(edge, k + 1), uv_at(edge, k))))
        for face, coords in faces:
            face.smooth = True
            for loop, coord in zip(face.loops, coords):
                loop[self.uv].uv = coord
        self.shells += 1

    def tube(self, path: list[tuple[Vector, float, float]], hint: Vector, start_cap: float = 0.0,
             end_cap: float = 0.0, segments: int = SEGMENTS) -> None:
        """A loft along a polyline; each point has radii along hint and across it. A cap > 0 rounds that end out by
        that fraction of its radius, 0 closes it flat."""
        rings = []
        for i, (point, ru, rv) in enumerate(path):
            before = path[max(i - 1, 0)][0]
            after = path[min(i + 1, len(path) - 1)][0]
            u, v = perpendicular(after - before, hint)
            rings.append((point, u, v, ru, rv))
        first, last = path[0][0], path[-1][0]
        axis_start = (path[1][0] - first).normalized()
        axis_end = (last - path[-2][0]).normalized()
        start = first - axis_start * (start_cap * min(path[0][1], path[0][2]))
        end = last + axis_end * (end_cap * min(path[-1][1], path[-1][2]))
        self.loft(rings, start, end, segments)

    def to_object(self, name: str, material: bpy.types.Material) -> bpy.types.Object:
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        mesh = bpy.data.meshes.new(name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        mesh.materials.append(material)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj


def material(name: str) -> bpy.types.Material:
    colour = (*(srgb_to_linear(c) for c in COLOURS[name]), 1.0)
    mat = bpy.data.materials.new(name)
    tree = mat.node_tree
    if tree is None:  # Blender before 5.0 made node trees only on request
        mat.use_nodes = True
        tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = colour
    bsdf.inputs["Roughness"].default_value = 1.0
    mat.diffuse_color = colour
    mat.roughness = 1.0
    return mat


class Figure:
    """The figure's dimensions for one preset, in metres before the final scale to HEIGHT."""

    def __init__(self, p: dict[str, float]) -> None:
        self.p = p
        self.hip_z = 0.92 * p["leg"]  # hip joint height
        self.crotch = self.hip_z - 0.07
        self.torso_top = self.hip_z + 0.56
        self.shoulder_z = self.torso_top - 0.075
        self.neck_top = self.torso_top + 0.1 * p["neck"]
        self.head_h = 0.285 * p["head"]
        self.head_w = 0.108 * p["head"]  # half width
        self.head_d = 0.118 * p["head"]  # half depth
        self.chin = self.neck_top - 0.03 * p["head"]
        self.head_top = self.chin + self.head_h
        self.eye_z = self.chin + self.head_h * 0.47

    # --- the head -----------------------------------------------------------------------------------------------

    def head_radii(self, t: float) -> tuple[float, float]:
        """Half width and half depth of the egg at height fraction t (0 chin, 1 crown): a round crown, the widest
        part a little above the middle, narrower at the jaw."""
        t = min(max(t, 0.0), 1.0)
        s = t**1.2
        round_ = math.sqrt(max(0.0, 1.0 - (2.0 * s - 1.0) ** 2))
        return self.head_w * round_ * (0.8 + 0.26 * t), self.head_d * round_ * (0.92 + 0.1 * t)

    def head(self, body: Builder) -> None:
        rings = []
        x, y = Vector((1, 0, 0)), Vector((0, 1, 0))
        count = 14
        for i in range(1, count):
            t = (1 - math.cos(math.pi * i / count)) / 2  # denser near the chin and the crown, so both are round
            rw, rd = self.head_radii(t)
            rings.append((Vector((0.0, 0.008 * (1 - t), self.chin + self.head_h * t)), x, y, rw, rd))
        body.loft(rings, Vector((0.0, 0.008, self.chin)), Vector((0.0, 0.0, self.head_top)))

    def nose(self, body: Builder) -> None:
        p = self.p
        z = self.eye_z - 0.035 * p["head"]
        _, depth = self.head_radii((z - self.chin) / self.head_h)
        base = Vector((0.0, -depth + 0.02, z))
        direction = Vector((0.0, -1.0, -0.42)).normalized()
        length = 0.07 * p["nose"]
        path = [
            (base, 0.02, 0.024),
            (base + direction * 0.03, 0.02, 0.024),
            (base + direction * (0.02 + length * 0.55), 0.017, 0.02),
            (base + direction * (0.02 + length), 0.016, 0.017),
        ]
        body.tube(path, Vector((1.0, 0.0, 0.0)), start_cap=0.0, end_cap=0.9, segments=8)

    def ears(self, body: Builder) -> None:
        z = self.eye_z - 0.01
        for side in (1.0, -1.0):
            width, _ = self.head_radii((z - self.chin) / self.head_h)
            base = Vector((side * (width - 0.01), 0.01, z))
            path = [(base, 0.03, 0.02), (base + Vector((side * 0.02, 0.006, 0.0)), 0.028, 0.016)]
            body.tube(path, Vector((0.0, 0.0, 1.0)), start_cap=0.0, end_cap=0.5, segments=8)

    def neck(self, body: Builder) -> None:
        r = 0.054 * self.p["limb"] ** 0.5
        path = [(Vector((0.0, 0.01, self.torso_top - 0.06)), r, r * 0.95),
                (Vector((0.0, 0.01, self.chin + 0.05)), r * 0.92, r * 0.9)]
        body.tube(path, Vector((1.0, 0.0, 0.0)))

    # --- the trunk ----------------------------------------------------------------------------------------------

    def torso_rings(self, grow: float = 1.0, add: float = 0.0, low: float = -1.0, high: float = 9.0) -> list:
        """(z, half width, half depth, y) of the torso from the crotch up, optionally grown for clothing."""
        w = self.p["torso"]
        d = 0.5 + 0.5 * w
        c, top = self.crotch, self.torso_top
        span = top - c
        table = [
            (0.0, 0.1, 0.08, 0.0), (0.09, 0.132, 0.092, 0.0), (0.22, 0.138, 0.095, 0.0), (0.36, 0.128, 0.09, 0.0),
            (0.52, 0.134, 0.095, -0.004), (0.68, 0.148, 0.1, -0.006), (0.82, 0.156, 0.095, 0.0),
            (0.92, 0.148, 0.085, 0.005), (0.985, 0.1, 0.065, 0.01),
        ]
        rings = []
        for f, hw, hd, y in table:
            z = c + span * f
            if low <= z <= high:
                rings.append((z, hw * w * grow + add, hd * d * grow + add, y))
        return rings

    def torso(self, body: Builder) -> None:
        rings = [(Vector((0.0, y, z)), Vector((1, 0, 0)), Vector((0, 1, 0)), hw, hd)
                 for z, hw, hd, y in self.torso_rings()]
        body.loft(rings, Vector((0.0, 0.0, self.crotch - 0.02)), Vector((0.0, 0.01, self.torso_top + 0.01)))

    # --- the arms and hands -------------------------------------------------------------------------------------

    def arm_path(self, side: float) -> list[tuple[Vector, float, float]]:
        """Shoulder to wrist along X at shoulder height; radii are (vertical, depth)."""
        limb, reach = self.p["limb"] * 1.08, self.p["arm"]
        z = self.shoulder_z
        points = [(0.1, 0.056, 0.054), (0.19, 0.058, 0.054), (0.31, 0.047, 0.045), (0.45, 0.039, 0.037),
                  (0.58, 0.037, 0.035), (0.69, 0.028, 0.025)]
        return [(Vector((side * (0.1 + (x - 0.1) * reach), 0.0, z)), rz * limb, ry * limb) for x, rz, ry in points]

    def wrist_x(self) -> float:
        return 0.1 + 0.59 * self.p["arm"]

    def arm(self, body: Builder, side: float) -> None:
        body.tube(self.arm_path(side), Vector((0.0, 0.0, 1.0)), start_cap=0.5, end_cap=0.0)

    def hand(self, body: Builder, side: float) -> None:
        """The palm faces down (-Z), the fingers point out along X, the thumb points forward (-Y)."""
        hand = 0.5 + 0.5 * self.p["limb"]
        x0, z = self.wrist_x() - 0.01, self.shoulder_z
        # The palm: radii are (thickness along Z, half width along Y).
        palm = [(0.0, 0.017, 0.03), (0.03, 0.017, 0.042), (0.075, 0.015, 0.044), (0.095, 0.012, 0.039)]
        body.tube([(Vector((side * (x0 + dx * hand), 0.0, z)), rz * hand, ry * hand) for dx, rz, ry in palm],
                  Vector((0.0, 0.0, 1.0)), start_cap=0.3, end_cap=0.3)
        knuckle_x = x0 + 0.085 * hand
        # Fingers: (offset along Y at the knuckle, spread angle in degrees, length, radius); index first.
        fingers = [(-0.03, -7.0, 0.074, 0.0085), (-0.01, -2.0, 0.082, 0.0088), (0.01, 3.0, 0.077, 0.0084),
                   (0.03, 9.0, 0.061, 0.0076)]
        for dy, angle, length, radius in fingers:
            a = math.radians(angle)
            direction = Vector((side * math.cos(a), math.sin(a), -0.04)).normalized()
            start = Vector((side * knuckle_x, dy * hand, z - 0.002))
            self.finger(body, start, direction, length * hand, radius * hand)
        # The thumb: from the forward edge of the palm, forward and outward.
        start = Vector((side * (x0 + 0.035 * hand), -0.03 * hand, z - 0.004))
        direction = Vector((side * 0.72, -0.66, -0.12)).normalized()
        self.finger(body, start, direction, 0.062 * hand, 0.0108 * hand)

    @staticmethod
    def finger(body: Builder, start: Vector, direction: Vector, length: float, radius: float) -> None:
        """Three segments (four rings) from inside the palm to a rounded tip."""
        back = start - direction * 0.012
        path = [(back, radius, radius), (start + direction * (length * 0.36), radius * 0.95, radius),
                (start + direction * (length * 0.68), radius * 0.88, radius * 0.92),
                (start + direction * length, radius * 0.8, radius * 0.82)]
        body.tube(path, Vector((0.0, 0.0, 1.0)), start_cap=0.0, end_cap=0.9, segments=6)

    # --- the legs and feet --------------------------------------------------------------------------------------

    def leg_path(self, side: float) -> list[tuple[Vector, float, float]]:
        """Hip to ankle along -Z; radii are (width along X, depth along Y)."""
        limb, leg = self.p["limb"] * 1.1, self.p["leg"]
        x = side * 0.088 * (0.5 + 0.5 * self.p["torso"])
        points = [(1.0, 0.074, 0.078), (0.87, 0.072, 0.074), (0.68, 0.058, 0.06), (0.53, 0.047, 0.05),
                  (0.44, 0.05, 0.056), (0.27, 0.039, 0.042), (0.11, 0.03, 0.033), (0.08, 0.03, 0.034)]
        return [(Vector((x, 0.005, 0.92 * f * leg if f < 1 else self.hip_z + 0.02)), rx * limb, ry * limb)
                for f, rx, ry in points]

    def leg(self, body: Builder, side: float) -> None:
        body.tube(self.leg_path(side), Vector((1.0, 0.0, 0.0)), start_cap=0.0, end_cap=0.0)

    def foot(self, body: Builder, side: float) -> None:
        """A rounded wedge from the heel forward (-Y), its sole at z = 0, and five toes, the big toe on the inside."""
        x = self.leg_path(side)[-1][0].x
        # (y, half width, half height); each ring's centre sits at its half height so the sole is at z = 0.
        rings = [(0.045, 0.028, 0.03), (0.02, 0.036, 0.04), (-0.04, 0.041, 0.034), (-0.1, 0.045, 0.024),
                 (-0.15, 0.045, 0.017)]
        path = [(Vector((x, y, hz)), hz, hw) for y, hw, hz in rings]
        body.tube(path, Vector((0.0, 0.0, 1.0)), start_cap=0.6, end_cap=0.0)
        # Toes: (offset along X towards the outside, length, radius); the big toe first.
        toes = [(-0.028, 0.045, 0.0125), (-0.008, 0.038, 0.0085), (0.008, 0.034, 0.008), (0.022, 0.03, 0.0075),
                (0.035, 0.026, 0.007)]
        for dx, length, radius in toes:
            start = Vector((x + side * dx, -0.14, radius))
            tip = start + Vector((0.0, -length, 0.0))
            body.tube([(start, radius, radius), (tip, radius * 0.92, radius)], Vector((0.0, 0.0, 1.0)),
                      start_cap=0.0, end_cap=0.8, segments=6)

    # --- clothing -----------------------------------------------------------------------------------------------

    def shirt(self, cloth: Builder) -> None:
        rings = [(Vector((0.0, y, z)), Vector((1, 0, 0)), Vector((0, 1, 0)), hw, hd)
                 for z, hw, hd, y in self.torso_rings(1.06, 0.006, low=self.crotch + 0.12)]
        top = rings[-1]
        rings[-1] = (top[0], top[1], top[2], max(top[3], 0.075), max(top[4], 0.06))  # the collar
        cloth.loft(rings, rings[0][0], rings[-1][0] + Vector((0.0, 0.0, 0.005)))
        for side in (1.0, -1.0):
            arm = self.arm_path(side)
            sleeve = [(point, rz * 1.1 + 0.006, ry * 1.1 + 0.006) for point, rz, ry in arm[:3]]
            end = arm[2][0] + (arm[3][0] - arm[2][0]) * 0.15
            sleeve[-1] = (end, sleeve[-1][1], sleeve[-1][2])
            cloth.tube(sleeve, Vector((0.0, 0.0, 1.0)), start_cap=0.5, end_cap=0.0)

    def shorts(self, cloth: Builder) -> None:
        waist = self.crotch + 0.2
        rings = [(Vector((0.0, y, z)), Vector((1, 0, 0)), Vector((0, 1, 0)), hw, hd)
                 for z, hw, hd, y in self.torso_rings(1.08, 0.008, high=waist)]
        cloth.loft(rings, Vector((0.0, 0.0, self.crotch - 0.025)), rings[-1][0])
        for side in (1.0, -1.0):
            leg = self.leg_path(side)
            tube = [(point, rx * 1.22 + 0.01, ry * 1.22 + 0.01) for point, rx, ry in leg[:3]]
            cloth.tube(tube, Vector((1.0, 0.0, 0.0)), start_cap=0.0, end_cap=0.0)


def build(preset: str) -> dict:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    figure = Figure(PRESETS[preset])
    body = Builder()
    figure.head(body)
    figure.nose(body)
    figure.ears(body)
    figure.neck(body)
    figure.torso(body)
    for side in (1.0, -1.0):
        figure.arm(body, side)
        figure.hand(body, side)
        figure.leg(body, side)
        figure.foot(body, side)
    shirt, shorts = Builder(), Builder()
    figure.shirt(shirt)
    figure.shorts(shorts)
    objects = [body.to_object("Body", material("Skin")), shirt.to_object("Shirt", material("Shirt")),
               shorts.to_object("Shorts", material("Shorts"))]
    top = max(v.co.z for obj in objects for v in obj.data.vertices)
    bottom = min(v.co.z for obj in objects for v in obj.data.vertices)
    scale = HEIGHT / top
    for obj in objects:
        obj.data.transform(Matrix.Scale(scale, 4))
        obj.data.update()
    return {
        "preset": preset,
        "proportions": PRESETS[preset],
        "height": round(top * scale, 4),
        "lowest": round(bottom * scale, 4),
        "eye_height": round(figure.eye_z * scale, 4),
        "objects": {obj.name: {"triangles": sum(len(p.vertices) - 2 for p in obj.data.polygons),
                               "vertices": len(obj.data.vertices), "shells": shells}
                    for obj, shells in zip(objects, (body.shells, shirt.shells, shorts.shells))},
    }


def main() -> None:
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    info = build(args.preset)
    info["triangles"] = sum(o["triangles"] for o in info["objects"].values())
    stem = f"mannequin_{args.preset}"
    glb = out / f"{stem}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", export_yup=True, export_apply=True,
                              export_animations=False)
    blend = out / f"{stem}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), check_existing=False, compress=True)
    info["glb"], info["blend"] = glb.as_posix(), blend.as_posix()
    if not args.no_refs:
        info["refs"] = refs.render(out / "refs", args.size, "studio")
        info["refs_flat"] = refs.render(out / "refs_flat", args.size, "flat")
    (out / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(f"MANNEQUIN {json.dumps({'preset': args.preset, 'triangles': info['triangles'], 'height': info['height']})}")


main()
