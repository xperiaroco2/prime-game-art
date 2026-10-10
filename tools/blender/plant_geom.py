"""The garden's plants (art #80, docs/house-garden.md "The plants"): pure Python, no Blender, Godot axes. Procedural
clay vegetation in the dressing library's style (prop_geom's primitives, soft blobs painted by role, no alpha cards:
the clay look and the budget both fit solid lumps), one builder per plant family:

- `garden_tree`: a tapered trunk, three branches into the crown and a crown of blobs above `canopy_bottom` (a player
  walks under it), two leaf tones and fruit on the crown's lower half; `crown` round, upright or spread;
- `bush`: a mound of blobs; `form` mound (boxwood), heads (hydrangea), spikes (lavender) or berries (currant);
- `flower_bed`: an edged bed of soil, leaf mounds and flowers; `form` cup, spike, disc or ball;
- `hedge`: a soft core with leafy lumps on its sides and top, flat ends so that segments tile along x.

Importing this module registers the builders in prop_geom.BUILDERS; tools/blender/plant_build.py does that and builds
props/plants.toml. A builder may put collider boxes in `prm["_boxes"]` (builder frame, before the pivot move): a tree
collides with its trunk only, so its crown overhangs paths. Sizes, crowns, forms and paints are data in plants.toml.
"""

from __future__ import annotations

import math

import prop_geom
from prop_geom import blob, cbox, cyl, loft, rod

LEAF = (7, 4)  # a leaf blob's segments and bands: 42 triangles
SMALL = (5, 3)  # a fruit, a berry, a flower head: 20 triangles


def _r(R: list, i: int) -> str:
    return R[min(i, len(R) - 1)]


def _ring(n: int, rad: float, y: float, rng, phase: float = 0.0, jitter: float = 0.15) -> list:
    out = []
    for i in range(n):
        a = phase + 2 * math.pi * i / n + jitter * (rng.random() - 0.5)
        out.append((rad * math.cos(a), y, rad * math.sin(a), a))
    return out


def build_garden_tree(m, s, R, prm, rng):
    L, W, H = s
    bark, leaf, light, fruit = R[0], _r(R, 1), _r(R, 2), _r(R, 3)
    cb = float(prm.get("canopy_bottom", 2.9))
    crown = prm.get("crown", "round")
    rx, rz = L / 2, W / 2
    hy = (H - cb) / 2
    cy = cb + hy
    tr = float(prm.get("trunk_r", 0.15))
    cyl(m, "y", (0.0, 0.0), tr, 0.0, cb + 0.6, bark, 7, r1=tr * 0.6, caps=(False, True))
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        rod(m, (0.0, cb - 0.3, 0.0), (0.55 * rx * math.cos(a), cb + 0.7, 0.55 * rz * math.sin(a)), tr * 0.4, bark, 5,
            caps=False)
    # the crown's profile: (ring height share of hy from the centre, ring reach share of the half width)
    lo_y, lo_w, hi_w = {"round": (-0.4, 1.0, 0.7), "upright": (-0.3, 1.0, 0.95), "spread": (-0.45, 1.0, 0.5)}[crown]
    blob(m, (0.0, cy, 0.0), 0.68 * rx, 0.72 * hy, 0.68 * rz, leaf, 8, 5)
    br = 0.42  # a ring blob's radius as a share of the half width
    low = _ring(8, (lo_w - br) * rx, cy + lo_y * hy, rng)
    for i, (x, y, z, a) in enumerate(low):
        ry = min(0.6 * hy, y - cb)  # the crown reaches down to canopy_bottom and never below it
        blob(m, (x, y, z * rz / rx), br * rx, ry, br * rz, light if i % 2 else leaf, *LEAF)
    high = _ring(4, (hi_w - 0.9 * br) * rx, cy + 0.42 * hy, rng, phase=math.pi / 4)
    for i, (x, y, z, a) in enumerate(high):
        blob(m, (x, y, z * rz / rx), br * rx * 0.9, min(0.4 * hy, H - y), br * rz * 0.9, leaf if i % 2 else light,
             *LEAF)
    top_r = 0.3 * hy
    blob(m, (0.0, H - top_r, 0.0), 0.4 * rx, top_r, 0.4 * rz, light, *LEAF)
    for k in range(int(prm.get("fruit", 12))):
        x, y, z, a = low[k % len(low)]
        t = a + 0.5 * (rng.random() - 0.5)
        reach = br * rx * 0.92
        fy = y - 0.1 * hy * rng.random()
        blob(m, (x + reach * math.cos(t), fy, (z + reach * math.sin(t)) * rz / rx), 0.06, 0.07, 0.06, fruit, *SMALL)
    prm["_boxes"] = [[(-tr, 0.0, -tr), (tr, cb, tr)]]


def build_bush(m, s, R, prm, rng):
    L, W, H = s
    leaf, light, bloom = R[0], _r(R, 1), _r(R, 2)
    form = prm.get("form", "mound")
    hx, hz = L / 2, W / 2
    blob(m, (0.0, 0.45 * H, 0.0), 0.8 * hx, 0.45 * H, 0.8 * hz, leaf, 9, 5, floor=0.0)
    if form == "spikes":  # lavender: a low mound and a fan of flower spikes up to H
        n = int(prm.get("spikes", 26))
        for i in range(n):
            a = 2 * math.pi * i / n + 0.3 * rng.random()
            rad = (0.25 + 0.7 * ((i * 7) % n) / n) * hx
            x, z = rad * math.cos(a), rad * math.sin(a) * hz / hx
            top = H if i == 0 else H * (0.75 + 0.25 * rng.random())
            base = (0.4 * x, 0.5 * H, 0.4 * z)
            stem = (x, top - 0.18, z)
            rod(m, base, stem, 0.012, light, 3, caps=False)
            cyl(m, "y", (x, z), 0.03, top - 0.2, top, bloom, 4, r1=0.0, caps=(True, False))
        return
    ring = _ring(6, 0.62 * hx, 0.42 * H, rng)
    for i, (x, y, z, a) in enumerate(ring):
        blob(m, (x, y, z * hz / hx), 0.38 * hx, min(0.36 * H, y), 0.38 * hz, light if i % 2 else leaf, *LEAF,
             floor=0.0)
    tops = _ring(3, 0.3 * hx, 0.72 * H, rng, phase=0.5)
    for i, (x, y, z, a) in enumerate(tops):
        blob(m, (x, y, z * hz / hx), 0.34 * hx, H - y, 0.34 * hz, leaf if i % 2 else light, *LEAF)
    if form == "heads":  # hydrangea: round flower heads on the outside
        for i, (x, y, z, a) in enumerate(ring + tops):
            r = 0.13 * L
            d = max(0.0, min(0.36 * hx, hx - math.hypot(x, z) - r))  # the heads stay inside the footprint
            blob(m, (x + d * math.cos(a), y + 0.1 * H, (z + d * math.sin(a)) * hz / hx), r, r * 0.85, r, bloom, 6, 4)
    elif form == "berries":  # currant: strings of berries
        for k in range(int(prm.get("berries", 18))):
            x, y, z, a = ring[k % len(ring)]
            t = a + 0.9 * (rng.random() - 0.5)
            d = 0.38 * hx * 0.95
            blob(m, (x + d * math.cos(t), y - 0.12 * H * rng.random(), (z + d * math.sin(t)) * hz / hx), 0.035,
                 0.035, 0.035, bloom, 4, 3)


def build_flower_bed(m, s, R, prm, rng):
    L, W, H = s
    edge, soil, leaf, bloom = R[0], _r(R, 1), _r(R, 2), _r(R, 3)
    form = prm.get("form", "cup")
    hx, hz = L / 2, W / 2
    eh = float(prm.get("edge_h", 0.12))
    loft(m, (-hx, hx, -hz, hz, 0.0), (-hx, hx, -hz, hz, eh), edge, inner=0.05)
    cbox(m, (-hx + 0.05, eh - 0.04, -hz + 0.05), (hx - 0.05, eh - 0.015, hz - 0.05), soil)
    n = 5
    for i in range(n):
        x = -hx + 0.25 + (L - 0.5) * i / (n - 1)
        blob(m, (x, eh - 0.02, 0.06 * (rng.random() - 0.5)), 0.24, 0.1, hz - 0.12, leaf, 7, 4, floor=eh - 0.02)
    count = int(prm.get("flowers", 16))
    for k in range(count):
        x = -hx + 0.15 + (L - 0.3) * (k + 0.5 * rng.random()) / count
        z = (hz - 0.17) * (1 if k % 2 else -1) * (0.3 + 0.7 * rng.random())
        top = H if k == count // 2 else eh + (H - eh) * (0.7 + 0.3 * rng.random())
        if form == "spike":  # foxglove: a tall cone of bells
            cyl(m, "y", (x, z), 0.045, top - 0.6 * (H - eh), top, bloom, 5, r1=0.0, caps=(True, False))
            rod(m, (x, eh, z), (x, top - 0.6 * (H - eh), z), 0.01, leaf, 3, caps=False)
            continue
        r = {"cup": 0.045, "disc": 0.06, "ball": 0.07}[form]
        hy = {"cup": 0.05, "disc": 0.02, "ball": 0.065}[form]
        rod(m, (x, eh, z), (x, top - 2 * hy, z), 0.01, leaf, 3, caps=False)
        blob(m, (x, top - hy, z), r, hy, r, bloom, *SMALL)


def build_hedge(m, s, R, prm, rng):
    L, W, H = s
    leaf, light = R[0], _r(R, 1)
    hx, hz = L / 2, W / 2
    r = float(prm.get("lump", 0.16))
    cbox(m, (-hx, 0.0, -hz + 0.06), (hx, H - 0.08, hz - 0.06), leaf)
    n = int(prm.get("per_row", 4))
    for i in range(n):
        x = -hx + r + (L - 2 * r) * (i + 0.5 * (rng.random() - 0.5)) / (n - 1)
        x = max(-hx + r, min(hx - r, x))
        for row, y in enumerate((0.35 * H, 0.72 * H)):
            for side in (-1, 1):
                blob(m, (x, y + 0.05 * rng.random(), side * (hz - r)), r, r * 1.1, r,
                     light if (i + row) % 2 else leaf, *LEAF)
        blob(m, (x, H - r, 0.0), r * 1.1, r, hz * 0.75, light if i % 2 else leaf, *LEAF)


BUILDERS = {name[6:]: fn for name, fn in dict(globals()).items() if name.startswith("build_") and callable(fn)}
prop_geom.BUILDERS.update(BUILDERS)


_FINISH = prop_geom.finish  # the library's finish, kept before plant_build.py points prop_geom at this module's


def build(p: dict, spec: dict) -> dict:
    """A plant built, finished and described as prop_geom.build does (with its collider boxes)."""
    pc = build_proc(p)
    finish(pc, p, spec)
    return prop_geom.describe(pc, spec)


def build_proc(p: dict):
    """prop_geom.build_proc for any shape; a plant builder's collider boxes are kept on the piece."""
    pc = prop_geom.Piece(p["id"], "prop")
    prm = dict(p.get("params", {}))
    prop_geom.BUILDERS[p["shape"]](pc.mesh, tuple(p["size_m"]), list(p["roles"]), prm, prop_geom.seed(p["id"]))
    pc.plant_boxes = prm.get("_boxes", [])
    return pc


def finish(pc, p: dict, spec: dict) -> None:
    """prop_geom.finish; with collision `boxes` the builder's boxes, moved with the pivot, are the colliders."""
    if p.get("collision") != "boxes":
        _FINISH(pc, p, spec)
        return
    boxes = getattr(pc, "plant_boxes", [])
    if not boxes:
        raise ValueError(f"{p['id']}: collision boxes but the builder made none")
    v0 = pc.mesh.verts[0]
    _FINISH(pc, dict(p, collision="none"), spec)  # moves every vertex by one offset and keeps their order
    d = [pc.mesh.verts[0][i] - v0[i] for i in range(3)]
    for a, b in boxes:
        pc.collide_box([a[i] + d[i] for i in range(3)], [b[i] + d[i] for i in range(3)])
    for k, c in enumerate(pc.colliders):
        c["name"] = f"{pc.id}_col{k}-convcolonly"
