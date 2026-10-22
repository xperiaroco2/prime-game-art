"""The ship's shared library for its piece builders (art #263, docs/ship.md): the material library every piece draws
from (one small shared set, so separate models do not mean separate texture sets) and the mesh helpers. SHARED and
FROZEN after the foundation step: the interior and exterior lanes only ADD new materials and new helper functions,
never change the existing ones.

A mesh part is a dict {"name", "verts" [(x, y, h)] in plan coordinates (x east, y south, h up; metres), "faces"
[(i, ...)], "mat" (a MATERIALS key), "solid" (closed: the harness recomputes its normals outward; else the builder
oriented its faces with `orient`)}. The harness (ship_build.py) turns plan coordinates into Blender's (x, -y, h), so the
glTF (Y up) holds Godot's (x, h, y)."""

from __future__ import annotations

import math

# name: base colour (linear RGBA), metallic, roughness, emission colour and strength, alpha blend
MATERIALS = {
    "hull_silver": {"base": (0.55, 0.57, 0.60, 1.0), "metallic": 0.9, "roughness": 0.32},
    "hull_dark": {"base": (0.10, 0.11, 0.12, 1.0), "metallic": 0.8, "roughness": 0.45},
    "wall_panel": {"base": (0.42, 0.44, 0.47, 1.0), "metallic": 0.75, "roughness": 0.40},
    "ceiling": {"base": (0.36, 0.38, 0.41, 1.0), "metallic": 0.75, "roughness": 0.42},
    "floor_grate": {"base": (0.20, 0.21, 0.22, 1.0), "metallic": 0.85, "roughness": 0.55},
    "leg_metal": {"base": (0.30, 0.31, 0.33, 1.0), "metallic": 0.9, "roughness": 0.38},
    "glass": {"base": (0.25, 0.35, 0.40, 0.25), "metallic": 0.0, "roughness": 0.05, "alpha": True},
    "glass_tint": {"base": (0.10, 0.08, 0.06, 0.6), "metallic": 0.0, "roughness": 0.06, "alpha": True,
                   "emission": (1.0, 0.55, 0.2), "strength": 0.6},
    # polish 4: the tip windows' one pane, clear and cool (glass_tint's 0.6 brown alpha dimmed the clearing orange)
    "glass_window": {"base": (0.10, 0.14, 0.17, 0.12), "metallic": 0.0, "roughness": 0.03, "alpha": True},
    "glow_cyan": {"base": (0.2, 0.9, 1.0, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (0.2, 0.9, 1.0),
                  "strength": 6.0},
    "glow_amber": {"base": (1.0, 0.6, 0.2, 1.0), "metallic": 0.0, "roughness": 0.3, "emission": (1.0, 0.6, 0.2),
                   "strength": 5.0},
}


def material(name: str):
    """The library material `name` (created once per Blender session)."""
    import bpy
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    spec = MATERIALS[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = spec["base"]
    bsdf.inputs["Metallic"].default_value = spec["metallic"]
    bsdf.inputs["Roughness"].default_value = spec["roughness"]
    if spec.get("alpha"):
        bsdf.inputs["Alpha"].default_value = spec["base"][3]
        mat.surface_render_method = "BLENDED"
    if spec.get("emission"):
        bsdf.inputs["Emission Color"].default_value = (*spec["emission"], 1.0)
        bsdf.inputs["Emission Strength"].default_value = spec["strength"]
    return mat


# --- mesh helpers (plain Python) -----------------------------------------------------------------------------------
def part(name: str, verts: list, faces: list, mat: str, solid: bool = True) -> dict:
    return {"name": name, "verts": [tuple(map(float, v)) for v in verts], "faces": [tuple(f) for f in faces],
            "mat": mat, "solid": solid}


def merge(*pieces: tuple[list, list]) -> tuple[list, list]:
    verts, faces = [], []
    for v, f in pieces:
        base = len(verts)
        verts += list(v)
        faces += [tuple(i + base for i in face) for face in f]
    return verts, faces


def box(x0: float, x1: float, y0: float, y1: float, h0: float, h1: float) -> tuple[list, list]:
    v = [(x, y, h) for h in (h0, h1) for y in (y0, y1) for x in (x0, x1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


def angles(a0: float, a1: float, step: float, cuts: tuple = ()) -> list[float]:
    """Angles (radians) from a0 to a1, at most `step` apart, through every cut inside the range."""
    marks = sorted({a0, a1, *[c for c in cuts if a0 < c < a1]})
    out = [marks[0]]
    for a, b in zip(marks, marks[1:]):
        n = max(1, math.ceil((b - a) / step - 1e-9))
        out += [a + (b - a) * (i + 1) / n for i in range(n)]
    return out


def sector(r0: float, r1: float, a0: float, a1: float, h0: float, h1: float) -> tuple[list, list]:
    """A solid block of a ring: radii r0..r1, angles a0..a1 (radians, from +x toward +y), heights h0..h1."""
    c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
    v = [(r0 * c0, r0 * s0, h0), (r1 * c0, r1 * s0, h0), (r1 * c1, r1 * s1, h0), (r0 * c1, r0 * s1, h0)]
    v += [(x, y, h1) for x, y, _ in v]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def ring(r0: float, r1: float, rows: list[float], step: float, skip=None, cuts: tuple = ()) -> tuple[list, list]:
    """A full ring of wall cells (each a closed block); skip(mid_angle, h0, h1) True leaves a cell out (an opening)."""
    a = angles(-math.pi, math.pi, step, cuts)
    out = []
    for a0, a1 in zip(a, a[1:]):
        for h0, h1 in zip(rows, rows[1:]):
            if skip and skip((a0 + a1) / 2, h0, h1):
                continue
            out.append(sector(r0, r1, a0, a1, h0, h1))
    return merge(*out)


def disc(r: float, n: int, h0: float, h1: float) -> tuple[list, list]:
    """A closed n-sided slab."""
    v = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), h) for h in (h0, h1) for i in range(n)]
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def dome(r: float, n: int, rim: float, apex: float, thick: float) -> tuple[list, list]:
    """A closed faceted cone slab: underside from the rim (h rim) up to the apex, `thick` above it."""
    v = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), rim + dh) for dh in (0, thick)
         for i in range(n)]
    v += [(0, 0, apex), (0, 0, apex + thick)]
    lo, hi = 2 * n, 2 * n + 1
    f = [(i, lo, (i + 1) % n) for i in range(n)] + [(n + i, n + (i + 1) % n, hi) for i in range(n)]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def cylinder_y(r: float, n: int, y0: float, y1: float) -> tuple[list, list]:
    """A closed n-sided cylinder along +y (plan south) from y0 to y1, its axis at x = 0, h = 0."""
    v, f = disc(r, n, y0, y1)
    return [(x, h, y) for x, y, h in v], f


def sphere(r: float, rings: int, segs: int) -> tuple[list, list]:
    v = [(0.0, 0.0, -r)]
    for i in range(1, rings):
        t = math.pi * i / rings - math.pi / 2
        v += [(r * math.cos(t) * math.cos(2 * math.pi * j / segs), r * math.cos(t) * math.sin(2 * math.pi * j / segs),
               r * math.sin(t)) for j in range(segs)]
    v.append((0.0, 0.0, r))
    f = [(0, 1 + (j + 1) % segs, 1 + j) for j in range(segs)]
    for i in range(rings - 2):
        a, b = 1 + i * segs, 1 + (i + 1) * segs
        f += [(a + j, a + (j + 1) % segs, b + (j + 1) % segs, b + j) for j in range(segs)]
    top, last = len(v) - 1, 1 + (rings - 2) * segs
    f += [(last + j, last + (j + 1) % segs, top) for j in range(segs)]
    return v, f


def orient(verts: list, faces: list, inner) -> list:
    """Faces turned so their normal points away from inner(face centre) (a point inside the shell)."""
    out = []
    for face in faces:
        p = [verts[i] for i in face]
        c = [sum(q[k] for q in p) / len(p) for k in range(3)]
        n = [0.0, 0.0, 0.0]
        for a, b in zip(p, p[1:] + p[:1]):  # Newell's normal
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        i = inner(c)
        out.append(face if sum(n[k] * (c[k] - i[k]) for k in range(3)) >= 0 else tuple(reversed(face)))
    return out
