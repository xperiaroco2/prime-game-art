"""The House map's task-station props and the procedural room-defining props no other package owns (art #82, #73;
docs/props.md). Plain Python, standard library only, like kit_geom.py whose Mesh, Piece, UV0 and UV2 it reuses: the
runner and the tests build every prop without Blender; tools/blender/props_task_build.py only turns them into objects.

Conventions (docs/props.md): Godot axes (metres, +Y up); each prop's pivot is on the floor at its game marker, the
footprint centred on it (x in [-w/2, w/2], z in [-d/2, d/2], y in [0, h]); its one front faces +Z. The paint is a
role per face (the kit's roles and materials, kits/house.json, plus the prop roles of props/tasks.toml). Moving parts
(lids) are separate meshes with their hinge as origin; state pieces (a switch's on and off) are separate meshes the
game shows or hides. A board the game writes on has one flat quad facing +Z on the `surface_game` material with UV0
0..1 over the quad. Collision: closed convex hulls named `<id>_col<k>-convcolonly`, as the kit's.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_geom  # noqa: E402
from kit_geom import EPS, Mesh, Piece  # noqa: E402

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ has it
    tomllib = None

SURFACE_MATERIAL = "surface_game"
SIZE_TOLERANCE_M = 0.01  # the built bounds equal the spec's w, d, h
CH = 0.015  # the default chamfer of a prop's boxes and cylinders


# --- the spec ------------------------------------------------------------------------------------------------------
def load_spec(path: Path) -> dict:
    """props/tasks.toml merged with its kit's materials and roles (the kit's roles come first; a prop role may not
    redefine one)."""
    path = Path(path).resolve()
    with path.open("rb") as f:
        spec = tomllib.load(f)
    kit = json.loads((path.parents[1] / spec["kit"]).read_text(encoding="utf-8"))
    spec["kit_roles"] = sorted(kit["roles"])
    spec["clashes"] = sorted(set(kit["roles"]) & set(spec.get("roles", {})))
    spec["materials"] = {**kit["materials"], **spec.get("materials", {})}
    spec["roles"] = {**spec.get("roles", {}), **kit["roles"]}
    return spec


# --- primitives ----------------------------------------------------------------------------------------------------
def cbox(m: Mesh, lo, hi, role: str, c: float = CH) -> None:
    """A box with its 12 edges chamfered by c (44 triangles); a plain box when it is too thin for the chamfer."""
    c = min(c, *((hi[i] - lo[i]) / 3 for i in range(3)))
    if c < 0.002:
        m.box(lo, hi, role)
        return
    ends = (lo, hi)

    def P(s, axis):  # the vertex near corner s (0 or 1 per axis) on the face normal to axis
        return tuple(ends[s[i]][i] if i == axis else (lo[i] + c if s[i] == 0 else hi[i] - c) for i in range(3))

    def sign(s):
        return tuple(1 if v else -1 for v in s)

    for axis in range(3):
        u, v = [i for i in range(3) if i != axis]
        for side in (0, 1):
            pts = []
            for su, sv in ((0, 0), (1, 0), (1, 1), (0, 1)):
                s = [0, 0, 0]
                s[axis], s[u], s[v] = side, su, sv
                pts.append(P(s, axis))
            n = [0, 0, 0]
            n[axis] = 1 if side else -1
            m.poly(pts, n, role)
    for e in range(3):  # edges along axis e
        a, b = [i for i in range(3) if i != e]
        for sa in (0, 1):
            for sb in (0, 1):
                s0, s1 = [0, 0, 0], [0, 0, 0]
                s0[a] = s1[a] = sa
                s0[b] = s1[b] = sb
                s1[e] = 1
                n = [0, 0, 0]
                n[a], n[b] = (1 if sa else -1), (1 if sb else -1)
                m.poly([P(s0, a), P(s0, b), P(s1, b), P(s1, a)], n, role)
    for sx in (0, 1):
        for sy in (0, 1):
            for sz in (0, 1):
                s = (sx, sy, sz)
                m.poly([P(s, 0), P(s, 1), P(s, 2)], sign(s), role)


def obox(m: Mesh, centre, ux, uy, uz, half, role: str) -> None:
    """An oriented box: centre, three unit axes, half sizes (12 triangles)."""
    def pt(a, b, c):
        return tuple(centre[i] + a * half[0] * ux[i] + b * half[1] * uy[i] + c * half[2] * uz[i] for i in range(3))
    for axis, u in enumerate((ux, uy, uz)):
        for s in (-1, 1):
            q = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                k = [0, 0, 0]
                k[axis] = s
                k[(axis + 1) % 3], k[(axis + 2) % 3] = a, b
                q.append(pt(*k))
            m.poly(q, tuple(s * c for c in u), role)


def _frame(axis: str):
    """(along, cos-axis, sin-axis) index triple of a lathe's axis."""
    return {"x": (0, 1, 2), "y": (1, 2, 0), "z": (2, 0, 1)}[axis]


def lathe(m: Mesh, base, axis: str, profile, role: str, n: int = 8, caps=(True, True), cap_roles=(None, None),
          band_roles=None) -> None:
    """A surface of revolution: profile [(a, r), ...] along axis from base, r the apothem (the n-gon's flats lie at r,
    so a lathe's bounds are exact along the cos axis). A ring of r 0 is an apex. Caps close the first and last rings."""
    al, ac, as_ = _frame(axis)
    k = 1.0 / math.cos(math.pi / n)
    rings = []
    for a, r in profile:
        if r < EPS:
            p = list(base)
            p[al] += a
            rings.append([tuple(p)])
            continue
        ring = []
        for j in range(n):
            t = math.pi / n + 2 * math.pi * j / n
            p = list(base)
            p[al] += a
            p[ac] += r * k * math.cos(t)
            p[as_] += r * k * math.sin(t)
            ring.append(tuple(p))
        rings.append(ring)
    for i in range(len(rings) - 1):
        (a0, r0), (a1, r1) = profile[i], profile[i + 1]
        R0, R1 = rings[i], rings[i + 1]
        role_i = band_roles[i] if band_roles and i < len(band_roles) and band_roles[i] else role
        for j in range(n):
            if len(R0) == 1 and len(R1) == 1:
                continue
            if len(R0) == 1:
                pts = [R0[0], R1[(j + 1) % n], R1[j]]
            elif len(R1) == 1:
                pts = [R0[j], R0[(j + 1) % n], R1[0]]
            else:
                pts = [R0[j], R0[(j + 1) % n], R1[(j + 1) % n], R1[j]]
            cen = [sum(p[c] for p in pts) / len(pts) for c in range(3)]
            radial = [cen[c] - base[c] for c in range(3)]
            radial[al] = 0.0
            nr = math.sqrt(sum(c * c for c in radial)) or 1.0
            da, dr = a1 - a0, r1 - r0
            normal = [radial[c] / nr * da for c in range(3)]
            normal[al] += -dr
            if abs(da) < EPS and abs(dr) < EPS:
                continue
            m.poly(pts, tuple(normal), role_i)
    for idx, (want, cr, sgn) in enumerate(((caps[0], cap_roles[0], -1), (caps[1], cap_roles[1], 1))):
        ring = rings[0] if idx == 0 else rings[-1]
        if want and len(ring) > 2:
            nrm = [0.0, 0.0, 0.0]
            nrm[al] = sgn
            m.poly(ring, tuple(nrm), cr or role)


def cyl(m: Mesh, base, axis: str, length: float, r: float, role: str, n: int = 8, c: float = 0.0,
        cap_roles=(None, None)) -> None:
    """A cylinder of apothem r from base along axis; c chamfers both rims."""
    c = min(c, r / 3, length / 3)
    prof = [(0, r - c), (c, r), (length - c, r), (length, r - c)] if c > 0.002 else [(0, r), (length, r)]
    lathe(m, base, axis, prof, role, n, cap_roles=cap_roles)


def prism_zy(m: Mesh, poly_zy, x0: float, x1: float, role: str) -> None:
    """A convex polygon in the (z, y) plane, counter-clockwise seen from +X, extruded over x0..x1."""
    m.poly([(x1, y, z) for z, y in poly_zy], (1, 0, 0), role)
    m.poly([(x0, y, z) for z, y in poly_zy], (-1, 0, 0), role)
    n = len(poly_zy)
    for i in range(n):
        (za, ya), (zb, yb) = poly_zy[i], poly_zy[(i + 1) % n]
        mid = ((za + zb) / 2, (ya + yb) / 2)
        cz = sum(z for z, _ in poly_zy) / n
        cy = sum(y for _, y in poly_zy) / n
        m.poly([(x0, ya, za), (x0, yb, zb), (x1, yb, zb), (x1, ya, za)], (0, mid[1] - cy, mid[0] - cz), role)


def surface(m: Mesh, x0, x1, y0, y1, z) -> None:
    """The game's writable quad, facing +Z (UV0 0..1 is set in describe)."""
    m.quad_z(x0, x1, y0, y1, z, 1, "game_surface")


def collide_lathe(pc: Piece, base, axis: str, length: float, r: float, parent=None) -> None:
    al, ac, as_ = _frame(axis)
    pts = []
    for a in (0.0, length):
        for j in range(8):
            t = math.pi / 8 + 2 * math.pi * j / 8
            p = list(base)
            p[al] += a
            p[ac] += r / math.cos(math.pi / 8) * math.cos(t)
            p[as_] += r / math.cos(math.pi / 8) * math.sin(t)
            pts.append(p)
    pc.collide(pts, parent=parent)


def _dims(p: dict):
    return float(p["w"]), float(p["d"]), float(p["h"])


def _full_collider(pc: Piece, p: dict, y1: float | None = None) -> None:
    w, d, h = _dims(p)
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, h if y1 is None else y1, d / 2))


# --- shared parts ----------------------------------------------------------------------------------------------------
def shelving(m: Mesh, w, d, h, levels, post_role="steel_dark", shelf_role="steel", post=0.04):
    """A metal shelving unit: four posts, shelves at the given heights (their tops); returns the shelf tops."""
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0 = w / 2 - post if sx > 0 else -w / 2
            z0 = d / 2 - post if sz > 0 else -d / 2
            cbox(m, (x0, 0, z0), (x0 + post, h, z0 + post), post_role, 0.006)
    for y in levels:
        cbox(m, (-w / 2 + 0.005, y - 0.03, -d / 2 + 0.005), (w / 2 - 0.005, y, d / 2 - 0.005), shelf_role, 0.008)
    return levels


def open_crate(m: Mesh, lo, hi, role: str, wall: float = 0.012) -> None:
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    m.box((x0, y0, z0), (x1, y0 + wall, z1), role)
    m.box((x0, y0, z0), (x1, y1, z0 + wall), role)
    m.box((x0, y0, z1 - wall), (x1, y1, z1), role)
    m.box((x0, y0, z0 + wall), (x0 + wall, y1, z1 - wall), role)
    m.box((x1 - wall, y0, z0 + wall), (x1, y1, z1 - wall), role)


def table_frame(m: Mesh, w, d, h, top_t, top_role, leg_role, leg=0.07, inset=0.06, apron=0.09, turned=False):
    cbox(m, (-w / 2, h - top_t, -d / 2), (w / 2, h, d / 2), top_role, 0.012)
    for sx in (-1, 1):
        for sz in (-1, 1):
            cx = sx * (w / 2 - inset - leg / 2)
            cz = sz * (d / 2 - inset - leg / 2)
            if turned:
                lathe(m, (cx, 0, cz), "y", [(0, leg * 0.35), (0.04, leg / 2), (0.12, leg * 0.3),
                                            (h - top_t - apron - 0.04, leg * 0.42), (h - top_t, leg / 2)],
                      leg_role, n=6)
            else:
                cbox(m, (cx - leg / 2, 0, cz - leg / 2), (cx + leg / 2, h - top_t, cz + leg / 2), leg_role, 0.008)
    if apron:
        ax, az = w / 2 - inset - leg / 2, d / 2 - inset - leg / 2
        y0, y1 = h - top_t - apron, h - top_t
        m.box((-ax, y0, az - 0.012), (ax, y1, az + 0.012), leg_role)
        m.box((-ax, y0, -az - 0.012), (ax, y1, -az + 0.012), leg_role)
        m.box((ax - 0.012, y0, -az), (ax + 0.012, y1, az), leg_role)
        m.box((-ax - 0.012, y0, -az), (-ax + 0.012, y1, az), leg_role)


def bottle(m: Mesh, base, length=0.3, r=0.037, axis="z"):
    lathe(m, base, axis, [(0, r * 0.8), (0.01, r), (length * 0.62, r), (length * 0.78, r * 0.38), (length, r * 0.36)],
          "bottle", n=6, cap_roles=("bottle", "foil"), band_roles=[None, None, None, "foil"])


# --- the props -----------------------------------------------------------------------------------------------------
def build_box_stack(pc: Piece, p: dict, spec: dict) -> None:
    """Delivery boxes on a pallet: three layers of taped cardboard boxes, each a little askew in place."""
    m = pc.mesh
    w, d, h = _dims(p)
    ph = 0.15
    for i in range(3):  # runners
        z = -d / 2 + 0.05 + i * (d - 0.1 - 0.1) / 2
        cbox(m, (-w / 2, 0, z), (w / 2, ph - 0.025, z + 0.1), "wood_dark", 0.008)
    for i in range(7):  # deck boards
        x = -w / 2 + i * (w - 0.12) / 6
        m.box((x, ph - 0.025, -d / 2), (x + 0.12, ph, d / 2), "boards")
    layers = [(2, 2, 0.42), (2, 2, 0.4), (1, 2, h - ph - 0.823)]
    y = ph
    shrink = [0.02, 0.06, 0.18]
    for li, (nx, nz, bh) in enumerate(layers):
        s = shrink[li]
        cw = (w - 2 * s) / nx
        cd = (d - 2 * s) / nz
        for ix in range(nx):
            for iz in range(nz):
                j = ((ix * 7 + iz * 3 + li * 5) % 5 - 2) * 0.006
                x0 = -w / 2 + s + ix * cw + 0.008 + j
                z0 = -d / 2 + s + iz * cd + 0.008 - j
                x1, z1 = x0 + cw - 0.016, z0 + cd - 0.016
                top = y + bh - (0.0 if (ix + iz + li) % 3 else 0.03)
                cbox(m, (x0, y, z0), (x1, top, z1), "cardboard", 0.012)
                m.box(((x0 + x1) / 2 - 0.03, top, z0 + 0.01), ((x0 + x1) / 2 + 0.03, top + 0.003, z1 - 0.01), "tape")
                m.box(((x0 + x1) / 2 - 0.03, y + 0.02, z1), ((x0 + x1) / 2 + 0.03, top, z1 + 0.003), "tape")
        y += bh
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, ph + 0.82, d / 2))
    pc.collide_box((-w / 2 + 0.18, ph + 0.82, -d / 2 + 0.18), (w / 2 - 0.18, h, d / 2 - 0.18))


def build_wine_rack(pc: Piece, p: dict, spec: dict) -> None:
    """A cubby rack of bottles, necks out; mount "wall" has a back board, "floor" is double-sided on sole feet."""
    m = pc.mesh
    w, d, h = _dims(p)
    double = p.get("mount") == "floor"
    body_d = p.get("body_d", d)
    t = 0.035
    cols, rows = p.get("cubbies", [4, 4])
    z0, z1 = -body_d / 2, body_d / 2
    y0 = 0.08 if double else 0.0
    if double:
        for sx in (-1, 1):
            x = sx * (w / 2 - 0.05)
            cbox(m, (x - 0.05, 0, -d / 2), (x + 0.05, y0, d / 2), "wood_dark", 0.01)
    for i in range(cols + 1):
        x = -w / 2 + i * (w - t) / cols
        cbox(m, (x, y0, z0), (x + t, h, z1), "wood_dark" if i in (0, cols) else "wood_light", 0.008)
    for j in range(rows + 1):
        y = y0 + j * (h - y0 - t) / rows
        m.box((-w / 2 + t, y, z0), (w / 2 - t, y + t, z1), "wood_light")
    if not double:
        m.box((-w / 2 + t, y0 + t, z0), (w / 2 - t, h - t, z0 + 0.012), "boards")
    cw = (w - t) / cols
    ch = (h - y0 - t) / rows
    per = p.get("bottles_per_cubby", 3)
    for i in range(cols):
        for j in range(rows):
            for k in range(per):
                if (i * 5 + j * 3 + k) % 7 == 6:
                    continue  # a few gaps: the rack is in use
                cx = -w / 2 + t + i * cw + (k + 0.5) * (cw - t) / per
                cy = y0 + t + j * ch + 0.04
                bl = min(0.3, body_d / 2 - 0.01) if double else min(0.3, body_d - 0.03)
                bottle(m, (cx, cy, z1 - bl), bl)
                if double:
                    m2 = bl
                    lathe(m, (cx, cy, z0 + m2), "z",
                          [(0, 0.036 * 0.8), (-0.01, 0.036), (-m2 * 0.62, 0.036), (-m2 * 0.78, 0.014),
                           (-m2, 0.013)], "bottle", n=6, cap_roles=("bottle", "foil"),
                          band_roles=[None, None, None, "foil"])
    _full_collider(pc, p)


def build_table(pc: Piece, p: dict, spec: dict) -> None:
    """A drop-off table with a clear top: "dining" on turned legs, "terrace" with a slatted top on metal legs."""
    m = pc.mesh
    w, d, h = _dims(p)
    if p.get("style") == "terrace":
        n = 7
        gap = 0.012
        sw = (w - (n - 1) * gap) / n
        for i in range(n):
            x = -w / 2 + i * (sw + gap)
            cbox(m, (x, h - 0.035, -d / 2), (x + sw, h, d / 2), "wood_light", 0.008)
        table_frame(m, w - 0.1, d - 0.1, h - 0.035, 0.0, "wood_light", "steel_dark", leg=0.045, inset=0.02,
                    apron=0.05)
    else:
        table_frame(m, w, d, h, 0.055, "wood_light", "wood_dark", leg=0.09, inset=0.12, apron=0.1, turned=True)
        m.box((-w / 2 + 0.02, h - 0.056, -d / 2 + 0.02), (w / 2 - 0.02, h - 0.054, d / 2 - 0.02), "wood_dark")
    _full_collider(pc, p)


def build_potting_bench(pc: Piece, p: dict, spec: dict) -> None:
    """The garden drop-off: a weathered bench with a clear top and pots on a slatted shelf."""
    m = pc.mesh
    w, d, h = _dims(p)
    table_frame(m, w, d, h, 0.045, "fence", "wood_dark", leg=0.07, inset=0.03, apron=0.08)
    for i in range(5):
        x = -w / 2 + 0.1 + i * (w - 0.2 - 0.12) / 4
        m.box((x, 0.2, -d / 2 + 0.06), (x + 0.12, 0.225, d / 2 - 0.06), "fence")
    m.box((-w / 2 + 0.1, 0.18, -d / 2 + 0.07), (w / 2 - 0.1, 0.2, -d / 2 + 0.1), "wood_dark")
    m.box((-w / 2 + 0.1, 0.18, d / 2 - 0.1), (w / 2 - 0.1, 0.2, d / 2 - 0.07), "wood_dark")
    for i, x in enumerate((-0.5, -0.25, 0.1, 0.42)):
        r = 0.09 if i % 2 else 0.11
        lathe(m, (x * w / 1.6, 0.225, 0.02 * (i % 2)), "y",
              [(0, r * 0.7), (r * 1.4, r), (r * 1.4 + 0.02, r * 1.08), (r * 1.4 + 0.04, r * 1.08), (r * 1.4 + 0.04, r * 0.9)],
              "terracotta", n=8, cap_roles=(None, "soil"))
    _full_collider(pc, p)


def build_workbench(pc: Piece, p: dict, spec: dict) -> None:
    """The garage drop-off: a heavy bench, clear top, a vice on the front edge, drawers and a crate on the shelf."""
    m = pc.mesh
    w, d, h = _dims(p)
    table_frame(m, w, d, h, 0.06, "wood_light", "steel_dark", leg=0.07, inset=0.02, apron=0.12)
    cbox(m, (-w / 2 + 0.06, 0.12, -d / 2 + 0.06), (w / 2 - 0.06, 0.15, d / 2 - 0.06), "boards", 0.006)
    cbox(m, (w / 2 - 0.62, h - 0.27, -d / 2 + 0.08), (w / 2 - 0.1, h - 0.06, d / 2 - 0.02), "machine_grey", 0.01)
    for i in range(2):
        y = h - 0.25 + i * 0.095
        cbox(m, (w / 2 - 0.6, y, d / 2 - 0.02), (w / 2 - 0.12, y + 0.085, d / 2), "steel", 0.006)
        cbox(m, (w / 2 - 0.42, y + 0.03, d / 2 - 0.003), (w / 2 - 0.3, y + 0.05, d / 2), "steel_dark", 0.003)
    vx = -w / 2 + 0.35
    cbox(m, (vx - 0.09, h - 0.12, d / 2 - 0.16), (vx + 0.09, h - 0.06, d / 2 - 0.02), "machine_green", 0.01)
    cbox(m, (vx - 0.08, h - 0.16, d / 2 - 0.02), (vx + 0.08, h - 0.06, d / 2), "steel_dark", 0.008)
    cyl(m, (vx, h - 0.12, d / 2 - 0.2), "z", 0.2, 0.012, "steel", n=6)
    open_crate(m, (-w / 2 + 0.15, 0.15, -d / 2 + 0.12), (-w / 2 + 0.65, 0.4, d / 2 - 0.15), "crate_plastic")
    cbox(m, (-0.2, 0.15, -0.15), (0.25, 0.32, 0.12), "red_paint", 0.015)
    _full_collider(pc, p)


def build_board(pc: Piece, p: dict, spec: dict) -> None:
    """A board the game writes on (order, herbs, pose screen, photos): a framed panel with a `surface_game` quad, on a
    two-post stand (mount "stand") or flat on a wall (mount "wall", the back at z -d/2)."""
    m = pc.mesh
    w, d, h = _dims(p)
    style = p.get("style", "chalk")
    stand = p.get("mount", "stand") == "stand"
    bw, bh = p["board"]
    fr = p.get("frame", 0.05)
    post = 0.07 if stand else 0.0
    frame_role = {"chalk": "wood_dark", "screen": "plastic_dark", "cork": "wood_light"}[style]
    x0, x1 = -bw / 2, bw / 2
    y1 = h - (p.get("header", 0.0) if stand else 0.0)
    y0 = y1 - bh
    zc = 0.0 if stand else -d / 2 + 0.04
    zb, zf = zc - 0.025, zc + 0.03
    for (a0, a1, b0, b1) in ((x0, x1, y0, y0 + fr), (x0, x1, y1 - fr, y1), (x0, x0 + fr, y0 + fr, y1 - fr),
                             (x1 - fr, x1, y0 + fr, y1 - fr)):
        cbox(m, (a0, b0, zb), (a1, b1, zf), frame_role, 0.008)
    m.box((x0 + fr, y0 + fr, zb + 0.005), (x1 - fr, y1 - fr, zc + 0.01), "boards", faces="+x-x+y-y-z")
    surface(m, x0 + fr, x1 - fr, y0 + fr, y1 - fr, zc + 0.01)
    if style == "chalk":
        cbox(m, (x0 + 0.1, y0 - 0.04, zc), (x1 - 0.1, y0, zc + 0.08), "wood_dark", 0.008)
    if style == "screen":
        cbox(m, (x0 + 0.2, y0 + fr / 2 - 0.006, zf), (x0 + 0.26, y0 + fr / 2 + 0.006, zf + 0.004), "lamp_green", 0.002)
    if stand:
        for sx in (-1, 1):
            xa = sx * (w / 2 - post / 2)
            cbox(m, (xa - post / 2, 0, -0.035), (xa + post / 2, h, 0.035), frame_role if style != "screen" else "steel_dark",
                 0.01)
            cbox(m, (xa - post / 2, 0, -d / 2), (xa + post / 2, 0.06, d / 2), "steel_dark", 0.012)
        if p.get("header"):
            cbox(m, (-w / 2, h - p["header"], -0.03), (w / 2, h, 0.03), frame_role, 0.01)
        pc.collide_box((-w / 2, 0, -d / 2), (-w / 2 + post, h, d / 2))
        pc.collide_box((w / 2 - post, 0, -d / 2), (w / 2, h, d / 2))
        pc.collide_box((-w / 2 + post, y0, zb), (w / 2 - post, y1, zf))
    else:
        pc.collide_box((x0, y0, -d / 2), (x1, y1, d / 2))


def build_island(pc: Piece, p: dict, spec: dict) -> None:
    """The kitchen's assembly island: cabinets with doors both sides, a butcher-block top kept clear."""
    m = pc.mesh
    w, d, h = _dims(p)
    o = 0.05
    cbox(m, (-w / 2, h - 0.045, -d / 2), (w / 2, h, d / 2), "wood_light", 0.01)
    cbox(m, (-w / 2 + o, 0.1, -d / 2 + o), (w / 2 - o, h - 0.045, d / 2 - o), "cabinet", 0.01)
    m.box((-w / 2 + o + 0.05, 0, -d / 2 + o + 0.06), (w / 2 - o - 0.05, 0.1, d / 2 - o - 0.06), "metal")
    n = p.get("doors", 4)
    dw = (w - 2 * o - 0.04) / n
    for side in (1, -1):
        zf = side * (d / 2 - o)
        for i in range(n):
            x = -w / 2 + o + 0.02 + i * dw
            za, zb = (zf, zf + side * 0.012)
            cbox(m, (x + 0.01, 0.14, min(za, zb)), (x + dw - 0.01, h - 0.09, max(za, zb)), "cabinet", 0.006)
            hx = x + (dw - 0.03 if i % 2 == 0 else 0.03)
            zh = zf + side * 0.012
            cbox(m, (hx - 0.01, h - 0.3, min(zh, zh + side * 0.02)), (hx + 0.01, h - 0.16, max(zh, zh + side * 0.02)),
                 "steel", 0.003)
    _full_collider(pc, p)


def build_bun_shelf(pc: Piece, p: dict, spec: dict) -> None:
    """Metal shelving with bakery crates: one bun kind per shelf (round, sesame, long)."""
    m = pc.mesh
    w, d, h = _dims(p)
    tops = shelving(m, w, d, h, [0.15, 0.68, 1.21, h])
    kinds = p.get("kinds", ["round", "sesame", "long"])
    for li, kind in enumerate(kinds):
        y = tops[li]
        for c in range(3):
            cx0 = -w / 2 + 0.06 + c * (w - 0.12) / 3
            cx1 = cx0 + (w - 0.12) / 3 - 0.03
            cz0, cz1 = -d / 2 + 0.06, d / 2 - 0.05
            open_crate(m, (cx0, y, cz0), (cx1, y + 0.13, cz1), "crate_plastic")
            nx, nz = (2, 3) if kind == "long" else (3, 2)
            sx = (cx1 - cx0 - 0.03) / nx
            sz = (cz1 - cz0 - 0.03) / nz
            for i in range(nx):
                for k in range(nz):
                    bx = cx0 + 0.015 + (i + 0.5) * sx
                    bz = cz0 + 0.015 + (k + 0.5) * sz
                    if kind == "long":
                        cbox(m, (bx - sx / 2 + 0.01, y + 0.012, bz - 0.04), (bx + sx / 2 - 0.01, y + 0.08, bz + 0.04),
                             "bun_dark", 0.025)
                    else:
                        r = min(sx, sz) / 2 - 0.006
                        top = 0.085 if kind == "round" else 0.065
                        lathe(m, (bx, y + 0.012, bz), "y", [(0, r * 0.88), (top * 0.35, r), (top * 0.8, r * 0.7), (top, 0)],
                              "bun" if kind == "round" else "bun_sesame", n=7)
    _full_collider(pc, p)


def build_chest_freezer(pc: Piece, p: dict, spec: dict) -> None:
    """A chest freezer, enamel white; its lid is a leaf hinged along the back top edge."""
    m = pc.mesh
    w, d, h = _dims(p)
    lid_t = p.get("lid", 0.08)
    yb = h - lid_t
    m.box((-w / 2 + 0.04, 0, -d / 2 + 0.04), (w / 2 - 0.04, 0.06, d / 2 - 0.04), "rubber")
    zf = d / 2 - 0.025
    cbox(m, (-w / 2, 0.06, -d / 2), (w / 2, yb, zf), "enamel", 0.03)
    m.box((-w / 2 + 0.02, yb, -d / 2 + 0.02), (w / 2 - 0.02, yb + 0.006, zf - 0.02), "rubber")
    for i in range(4):
        y = 0.12 + i * 0.035
        m.box((w / 2 - 0.38, y, zf), (w / 2 - 0.08, y + 0.015, zf + 0.004), "steel_dark")
    cyl(m, (-w / 2 + 0.18, yb - 0.16, zf), "z", 0.02, 0.035, "steel", n=8, cap_roles=(None, "lamp_red"))
    lid = pc.leaf("lid", (0.0, yb, -d / 2))
    cbox(lid, (-w / 2, yb + 0.006, -d / 2), (w / 2, h - 0.0, d / 2 - 0.025), "enamel", 0.025)
    cbox(lid, (-0.25, yb - 0.04, d / 2 - 0.025), (0.25, yb + 0.05, d / 2), "steel", 0.008)
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, yb, zf))
    pc.collide_box((-w / 2, yb + 0.006, -d / 2), (w / 2, h, d / 2), parent=lid.name)


def build_grill(pc: Piece, p: dict, spec: dict) -> None:
    """A barrel grill on legs with a side shelf and two wheels under the left legs; the lid is a leaf hinged along the
    barrel's back."""
    m = pc.mesh
    w, d, h = _dims(p)
    r = 0.25
    cy = h - r
    bx0, bx1 = -w / 2 + 0.04, w / 2 - 0.36
    oct_lo = [(r * math.cos(t), cy + r * math.sin(t)) for t in
              (0, -math.pi / 4, -math.pi / 2, -3 * math.pi / 4, math.pi)]
    prism_zy(m, list(reversed(oct_lo)), bx0, bx1, "steel_dark")
    m.box((bx0 + 0.02, cy - 0.01, -r + 0.03), (bx1 - 0.02, cy, r - 0.03), "steel")
    for sx in (-1, 1):
        for sz in (-1, 1):
            lx = (bx0 + 0.025) if sx < 0 else (bx1 - 0.06)
            cbox(m, (lx - 0.025, 0, sz * (r - 0.03) - 0.025), (lx + 0.025, cy - r * 0.7, sz * (r - 0.03) + 0.025),
                 "steel_dark", 0.006)
    cbox(m, (bx0 + 0.05, 0.22, -r + 0.03), (bx1 - 0.05, 0.25, r - 0.03), "boards", 0.006)
    for i in range(4):
        sx0 = bx1 + 0.01 + i * 0.085
        m.box((sx0, cy - 0.03, -r + 0.02), (sx0 + 0.07, cy, r - 0.02), "wood_light")
    m.box((bx1, cy - 0.06, -r + 0.02), (w / 2, cy - 0.03, -r + 0.05), "steel_dark")
    m.box((bx1, cy - 0.06, r - 0.05), (w / 2, cy - 0.03, r - 0.02), "steel_dark")
    cbox(m, (w / 2 - 0.04, 0, -r + 0.02), (w / 2, cy - 0.03, -r + 0.06), "steel_dark", 0.006)
    cbox(m, (w / 2 - 0.04, 0, r - 0.06), (w / 2, cy - 0.03, r - 0.02), "steel_dark", 0.006)
    for sz in (-1, 1):  # wheels against the left legs' outer faces
        cyl(m, (-w / 2, 0.05, sz * (r - 0.03)), "x", 0.035, 0.05, "rubber", n=8)
    m.box((bx0 + 0.05, cy - 0.05, -d / 2), (bx1 - 0.05, cy - 0.02, -d / 2 + 0.02), "steel")
    for x in (bx0 + 0.08, bx1 - 0.08):
        m.box((x - 0.01, cy - 0.05, -d / 2 + 0.02), (x + 0.01, cy - 0.02, -r + 0.03), "steel_dark")
    lid = pc.leaf("lid", (0.0, cy, -r))
    oct_hi = [(r * math.cos(t), cy + r * math.sin(t)) for t in (0, math.pi / 4, math.pi / 2, 3 * math.pi / 4, math.pi)]
    prism_zy(lid, oct_hi, bx0, bx1, "steel_dark")
    for hx in (-0.2, 0.15):
        m_x = (bx0 + bx1) / 2 + hx
        m_x = min(max(m_x, bx0 + 0.05), bx1 - 0.05)
        lid.box((m_x - 0.015, cy + r * 0.62, r * 0.72), (m_x + 0.015, cy + r * 0.66, d / 2 - 0.02), "steel")
    cbox(lid, ((bx0 + bx1) / 2 - 0.22, cy + r * 0.6, d / 2 - 0.04), ((bx0 + bx1) / 2 + 0.22, cy + r * 0.68, d / 2),
         "wood_light", 0.008)
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, cy, d / 2))
    pc.collide_box((bx0, cy, -r), (bx1, cy + r, r), parent=lid.name)


def build_herb_bed(pc: Piece, p: dict, spec: dict) -> None:
    """A raised timber bed of herbs in rows (bushy, spiky, leafy), each row with a name stake facing the front."""
    m = pc.mesh
    w, d, h = _dims(p)
    wall_h, t = p.get("wall_h", 0.38), 0.05
    for i in range(2):
        y0 = i * wall_h / 2
        y1 = y0 + wall_h / 2 - 0.005
        cbox(m, (-w / 2, y0, d / 2 - t), (w / 2, y1, d / 2), "fence", 0.01)
        cbox(m, (-w / 2, y0, -d / 2), (w / 2, y1, -d / 2 + t), "fence", 0.01)
        cbox(m, (-w / 2, y0, -d / 2 + t), (-w / 2 + t, y1, d / 2 - t), "fence", 0.01)
        cbox(m, (w / 2 - t, y0, -d / 2 + t), (w / 2, y1, d / 2 - t), "fence", 0.01)
    for sx in (-1, 1):
        for sz in (-1, 1):
            cbox(m, (sx * (w / 2 - t) - 0.035 * (sx > 0) - 0.0, 0, sz * (d / 2 - t) - 0.035 * (sz > 0)),
                 (sx * (w / 2 - t) + 0.035 * (sx < 0), wall_h + 0.02, sz * (d / 2 - t) + 0.035 * (sz < 0)),
                 "wood_dark", 0.006)
    m.box((-w / 2 + t, wall_h - 0.06, -d / 2 + t), (w / 2 - t, wall_h - 0.04, d / 2 - t), "soil", faces="+y")
    rows = p.get("rows", 3)
    per = p.get("per_row", 6)
    kinds = [("herb", "bush"), ("herb_light", "spike"), ("herb_dark", "leafy")]
    ys = wall_h - 0.04
    for r_i in range(rows):
        z = -d / 2 + t + (r_i + 0.5) * (d - 2 * t) / rows
        role, shape = kinds[r_i % 3]
        for k in range(per):
            x = -w / 2 + t + 0.25 + k * (w - 2 * t - 0.5) / (per - 1)
            jit = ((k * 7 + r_i * 3) % 5 - 2) * 0.012
            if shape == "spike":
                lathe(m, (x + jit, ys, z), "y", [(0, 0.05), (0.04, 0.07), (h - ys, 0.0)], role, n=5, caps=(False, False))
            elif shape == "leafy":
                lathe(m, (x + jit, ys, z), "y", [(0, 0.06), (0.05, 0.12), (0.09, 0.1), (0.11, 0.0)], role, n=6,
                      caps=(False, False))
            else:
                lathe(m, (x + jit, ys, z), "y", [(0, 0.07), (0.06, 0.11), (0.12, 0.08), (0.14, 0.0)], role, n=6,
                      caps=(False, False))
        cbox(m, (w / 2 - t - 0.12, ys, z - 0.01), (w / 2 - t - 0.1, h - 0.06, z + 0.01), "wood_light", 0.003)
        cbox(m, (w / 2 - t - 0.17, h - 0.1, z + 0.0), (w / 2 - t - 0.05, h - 0.03, z + 0.012), "paper", 0.003)
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, wall_h + 0.02, d / 2))


def build_generator(pc: Piece, p: dict, spec: dict) -> None:
    """The generator: a skid, a yellow engine housing with louvres, a radiator grille, a control panel with gauges and
    a big stop button, a muffler and an exhaust stack with a rain cap, a red fuel tank and lifting eyes."""
    m = pc.mesh
    w, d, h = _dims(p)
    sk = 0.12
    for sz in (-1, 1):
        cbox(m, (-w / 2, 0, sz * d / 2 - (0.12 if sz > 0 else 0)), (w / 2, sk, sz * d / 2 + (0.12 if sz < 0 else 0)),
             "steel_dark", 0.012)
    m.box((-w / 2 + 0.04, sk - 0.03, -d / 2 + 0.12), (w / 2 - 0.04, sk, d / 2 - 0.12), "steel_dark")
    hx0, hx1, hy = -w / 2 + 0.3, w / 2 - 0.55, 1.12
    hz = d / 2 - 0.08
    cbox(m, (hx0, sk, -hz), (hx1, hy, hz), "machine", 0.045)
    for i in range(6):  # louvres on the front panel
        y = sk + 0.35 + i * 0.07
        cbox(m, (hx0 + 0.25, y, hz - 0.005), (hx1 - 0.55, y + 0.035, hz + 0.02), "steel_dark", 0.006)
    for x in (hx0 + 0.12, hx1 - 0.12):  # door seams and hinges
        m.box((x - 0.006, sk + 0.06, hz), (x + 0.006, hy - 0.06, hz + 0.004), "steel_dark")
    for sx in (hx0 + 0.32, hx1 - 0.6):
        m.box((sx - 0.012, sk + 0.18, hz), (sx + 0.012, sk + 0.28, hz + 0.01), "steel")
    cbox(m, (-w / 2 + 0.02, sk, -hz + 0.05), (hx0, hy - 0.06, hz - 0.05), "steel_dark", 0.02)
    for i in range(8):  # the radiator's grille
        y = sk + 0.08 + i * 0.1
        m.box((-w / 2, y, -hz + 0.1), (-w / 2 + 0.02, y + 0.045, hz - 0.1), "steel")
    px0 = hx1 + 0.03
    cbox(m, (px0, sk, -hz + 0.1), (w / 2 - 0.02, hy + 0.1, hz - 0.02), "machine_grey", 0.02)
    pz = hz - 0.02
    for i, (gx, gy) in enumerate(((0.12, 0.98), (0.3, 0.98), (0.12, 0.8))):
        cyl(m, (px0 + gx, gy, pz), "z", 0.03, 0.06, "steel_dark", n=8, c=0.008, cap_roles=(None, "enamel"))
        m.box((px0 + gx - 0.004, gy, pz + 0.03), (px0 + gx + 0.004, gy + 0.045, pz + 0.034),
              "lamp_red" if i == 0 else "steel_dark")
    cyl(m, (px0 + 0.3, 0.8, pz), "z", 0.045, 0.06, "warning", n=8, c=0.01, cap_roles=(None, "lamp_red"))
    cbox(m, (px0 + 0.08, 0.45, pz), (px0 + 0.38, 0.62, pz + 0.012), "warning", 0.004)
    for i in range(3):
        m.box((px0 + 0.1 + i * 0.1, 0.47, pz + 0.012), (px0 + 0.14 + i * 0.1, 0.6, pz + 0.016), "steel_dark")
    cyl(m, (px0 + 0.21, 0.28, pz), "z", 0.05, 0.05, "steel_dark", n=8, c=0.01, cap_roles=(None, "lamp_green"))
    cyl(m, (-0.55, hy, -0.12), "x", 0.75, 0.13, "steel", n=8, c=0.03)
    for x in (-0.48, 0.1):
        m.box((x, hy - 0.01, -0.2), (x + 0.04, hy + 0.06, -0.04), "steel_dark")
    sx, sz = -0.62, -0.12
    lathe(m, (sx, hy + 0.1, sz), "y", [(0, 0.07), (h - hy - 0.17, 0.07), (h - hy - 0.17, 0.0)], "steel_dark", n=8,
          caps=(False, False))
    lathe(m, (sx, h - 0.1, sz), "y", [(0, 0.0), (0.0, 0.1), (0.04, 0.12), (0.1, 0.0)], "steel_dark", n=8,
          caps=(False, False))
    for x in (hx0 + 0.2, hx1 - 0.2):
        lathe(m, (x, hy, 0.12), "y", [(0, 0.04), (0.06, 0.04), (0.06, 0.0)], "warning", n=6, caps=(False, False))
    cbox(m, (-0.2, hy, 0.05), (0.35, hy + 0.12, hz - 0.05), "red_paint", 0.03)
    cyl(m, (0.27, hy + 0.12, 0.2), "y", 0.04, 0.035, "steel_dark", n=6, c=0.008)
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, hy + 0.12, d / 2))
    pc.collide_box((sx - 0.12, hy, sz - 0.12), (sx + 0.12, h, sz + 0.12))


def build_switch(pc: Piece, p: dict, spec: dict) -> None:
    """A power switch with two state meshes, `<id>_on` (lever up, green lamp) and `<id>_off` (lever down, red lamp),
    the game shows one. Mount "wall": a box on a back plate with conduit to the floor; "post": on a floor post."""
    m = pc.mesh
    w, d, h = _dims(p)
    post = p.get("mount") == "post"
    by0 = p.get("box_y", 1.1)
    bh, bw = 0.45, 0.3
    by1 = by0 + bh
    if post:
        zb = -0.08
        cbox(m, (-w / 2, 0, -d / 2), (w / 2, 0.025, d / 2), "steel_dark", 0.006)
        cbox(m, (-0.04, 0, zb - 0.04), (0.04, h - 0.02, zb + 0.04), "machine_grey", 0.01)
        cbox(m, (-0.06, h - 0.02, zb - 0.06), (0.06, h, zb + 0.06), "steel_dark", 0.005)
        z0 = zb + 0.04
    else:
        z0 = -d / 2
        cbox(m, (-bw / 2, by0, z0), (bw / 2, by1, z0 + 0.012), "steel_dark", 0.004)
        cyl(m, (0.0, 0.0, z0 + 0.03), "y", by0, 0.018, "steel", n=6)
        m.box((-0.04, 0.0, z0), (0.04, 0.02, z0 + 0.05), "steel_dark")
        z0 += 0.012
    zf = z0 + 0.07
    kz = min(zf + 0.075, d / 2)
    cbox(m, (-bw / 2 + 0.015, by0 + 0.015, z0), (bw / 2 - 0.015, by1 - 0.015, zf), "switch_body", 0.015)
    m.box((-bw / 2 + 0.05, by0 + 0.05, zf), (bw / 2 - 0.05, by0 + 0.07, zf + 0.004), "warning")
    py = (by0 + by1) / 2
    cyl(m, (0.04, py, zf), "z", 0.02, 0.045, "steel_dark", n=8)
    lamp_x = -0.085
    for state, up, lamp_role, ly in (("on", True, "lamp_green", by1 - 0.07), ("off", False, "lamp_red", by0 + 0.12)):
        s = pc.leaf(state, (0.0, 0.0, 0.0))
        tip = by1 - 0.025 if up else by0 + 0.025
        lo, hi = (py, tip) if up else (tip, py)
        cbox(s, (0.015, lo, zf + 0.02), (0.065, hi, zf + 0.05), "steel", 0.008)
        ky = tip - 0.05 if up else tip
        cbox(s, (0.0, ky, zf + 0.02), (0.08, ky + 0.05, kz), "lamp_green" if up else "red_paint", 0.012)
        cyl(s, (lamp_x, ly, zf), "z", 0.025, 0.04, "steel_dark", n=8, cap_roles=(None, lamp_role))
    pc.collide_box((-bw / 2, by0, -d / 2 if not post else z0), (bw / 2, by1, kz))
    if post:
        pc.collide_box((-w / 2, 0, -d / 2), (w / 2, by0, d / 2))
        pc.collide_box((-0.06, by1, -0.14), (0.06, h, -0.02))
    else:
        pc.collide_box((-0.04, 0, z0 - 0.012), (0.04, by0, z0 + 0.05))


def build_computer(pc: Piece, p: dict, spec: dict) -> None:
    """A beige CRT computer with its keyboard and mouse; the screen is a game surface (the photo to print)."""
    m = pc.mesh
    w, d, h = _dims(p)
    bw = 0.44
    zf = 0.02
    cbox(m, (-0.17, 0, -d / 2), (0.17, 0.02, zf - 0.06), "plastic_light", 0.006)
    cbox(m, (-0.07, 0.02, -0.15), (0.07, 0.06, -0.05), "plastic_light", 0.01)
    cbox(m, (-0.16, 0.06, -d / 2), (0.16, h - 0.06, zf - 0.06), "plastic_light", 0.03)
    cbox(m, (-bw / 2, 0.05, zf - 0.07), (bw / 2, h, zf), "plastic_light", 0.025)
    m.box((-bw / 2 + 0.04, 0.09, zf - 0.005), (bw / 2 - 0.04, h - 0.04, zf + 0.0), "screen", faces="+x-x+y-y")
    surface(m, -bw / 2 + 0.05, bw / 2 - 0.05, 0.1, h - 0.05, zf)
    cbox(m, (bw / 2 - 0.07, 0.06, zf - 0.005), (bw / 2 - 0.05, 0.075, zf + 0.004), "lamp_green", 0.002)
    kz0 = zf + 0.05
    cbox(m, (-0.22, 0, kz0), (0.2, 0.025, d / 2), "plastic_light", 0.008)
    for r in range(4):
        m.box((-0.2, 0.025, kz0 + 0.015 + r * 0.032), (0.18, 0.033, kz0 + 0.04 + r * 0.032), "plastic_dark")
    cbox(m, (w / 2 - 0.06, 0, d / 2 - 0.12), (w / 2, 0.03, d / 2 - 0.02), "plastic_light", 0.012)
    cbox(m, (-w / 2, 0, kz0 + 0.0), (-w / 2 + 0.07, 0.07, kz0 + 0.07), "red_paint", 0.01)
    pc.collide_box((-bw / 2, 0, -d / 2), (bw / 2, h, zf))
    pc.collide_box((-w / 2, 0, zf), (w / 2, 0.07, d / 2))


def build_printer(pc: Piece, p: dict, spec: dict) -> None:
    """A photo printer: the body, a sloped paper tray at the back, an output tray at the front and the printed photo
    as its own mesh `<id>_photo` (the game shows it when a print is out)."""
    m = pc.mesh
    w, d, h = _dims(p)
    bh = 0.18
    zb = d / 2 - 0.08
    cbox(m, (-w / 2, 0, -d / 2 + 0.06), (w / 2, bh, zb), "plastic_light", 0.025)
    m.box((-w / 2 + 0.06, 0.07, zb), (w / 2 - 0.06, 0.09, zb + 0.004), "plastic_dark")
    cbox(m, (-w / 2 + 0.07, 0.045, zb - 0.02), (w / 2 - 0.07, 0.06, d / 2), "plastic_dark", 0.004)
    cbox(m, (w / 2 - 0.14, bh, zb - 0.1), (w / 2 - 0.04, bh + 0.01, zb - 0.03), "plastic_dark", 0.003)
    cbox(m, (w / 2 - 0.12, bh + 0.01, zb - 0.08), (w / 2 - 0.1, bh + 0.016, zb - 0.06), "lamp_green", 0.002)
    ang = math.radians(35)
    uy, uz = (0, math.cos(ang), -math.sin(ang)), (0, math.sin(ang), math.cos(ang))
    L = (h - bh + 0.04) / math.cos(ang)
    c = (0.0, bh - 0.02 + L / 2 * math.cos(ang), -d / 2 + 0.06 + 0.02 - L / 2 * math.sin(ang) + 0.0)
    depth_back = -d / 2 + 0.0
    zc = depth_back + L / 2 * math.sin(ang) + 0.004
    obox(m, (0.0, bh - 0.04 + L / 2 * math.cos(ang), zc), (1, 0, 0), uy, uz, (w / 2 - 0.08, L / 2 - 0.004, 0.004),
         "plastic_dark")
    obox(m, (0.0, bh - 0.035 + L / 2 * math.cos(ang) * 0.9, zc + 0.008), (1, 0, 0), uy, uz,
         (w / 2 - 0.1, L / 2 * 0.85, 0.002), "paper")
    ph = pc.leaf("photo", (0.0, 0.06, d / 2 - 0.06))
    ph.box((-0.09, 0.06, d / 2 - 0.16), (0.09, 0.064, d / 2 - 0.02), "paper")
    pc.collide_box((-w / 2, 0, -d / 2 + 0.06), (w / 2, bh, d / 2))
    pc.collide_box((-w / 2 + 0.08, bh, -d / 2), (w / 2 - 0.08, h, -d / 2 + 0.2))


def build_parts_shelf(pc: Piece, p: dict, spec: dict) -> None:
    """Car parts on metal shelving: tyres, a battery, a brake disc, oil cans, a headlamp, boxes, an exhaust pipe."""
    m = pc.mesh
    w, d, h = _dims(p)
    tops = shelving(m, w, d, h, [0.12, 0.62, 1.12, 1.62])
    y = tops[0]
    for i, x in enumerate((-0.45, 0.2)):
        for k in range(2 - i):
            lathe(m, (x, y + k * 0.205, 0.0), "y",
                  [(0, 0.12), (0.0, 0.2), (0.02, 0.22), (0.18, 0.22), (0.2, 0.2), (0.2, 0.12), (0.0, 0.12)],
                  "rubber", n=8, caps=(False, False))
    cbox(m, (0.55, y, -0.1), (0.85, y + 0.2, 0.08), "rubber", 0.012)
    for tx, role in ((0.6, "red_paint"), (0.8, "steel_dark")):
        cyl(m, (tx, y + 0.2, 0.0), "y", 0.03, 0.02, role, n=6)
    y = tops[1]
    lathe(m, (-0.6, y, 0.0), "y", [(0, 0.06), (0, 0.15), (0.02, 0.15), (0.02, 0.06), (0, 0.06)], "steel",
          n=10, caps=(False, False))
    for i in range(3):
        cyl(m, (-0.2 + i * 0.13, y, 0.05 - 0.04 * (i % 2)), "y", 0.22, 0.05, "red_paint" if i != 1 else "machine",
            n=8, c=0.01, cap_roles=(None, "steel"))
    cbox(m, (0.3, y, -0.18), (0.85, y + 0.3, 0.16), "cardboard", 0.012)
    y = tops[2]
    lathe(m, (-0.5, y + 0.1, 0.08), "z", [(0, 0.09), (0.08, 0.1), (0.1, 0.08)], "steel", n=8,
          cap_roles=("steel", "glass"))
    cbox(m, (-0.2, y, -0.18), (0.2, y + 0.24, 0.17), "cardboard", 0.012)
    cbox(m, (0.3, y, -0.15), (0.8, y + 0.15, 0.15), "crate_plastic", 0.012)
    y = tops[3]
    cyl(m, (-w / 2 + 0.06, y + 0.06, 0.0), "x", w - 0.12, 0.04, "steel", n=6)
    cyl(m, (-0.2, y + 0.06, 0.0), "x", 0.5, 0.09, "steel", n=8, c=0.02)
    _full_collider(pc, p)


def build_speaker(pc: Piece, p: dict, spec: dict) -> None:
    """A party speaker: a cabinet with a woofer, a tweeter, a port, a handle and feet."""
    m = pc.mesh
    w, d, h = _dims(p)
    zf = d / 2 - 0.01
    cbox(m, (-w / 2, 0.03, -d / 2), (w / 2, h - 0.04, zf), "plastic_dark", 0.03)
    for sx in (-1, 1):
        for sz in (-1, 1):
            cyl(m, (sx * (w / 2 - 0.06), 0, sz * (d / 2 - 0.07)), "y", 0.03, 0.03, "rubber", n=6)
    for cy, r in ((0.32, 0.19), (0.7, 0.07)):
        lathe(m, (0.0, cy, zf), "z", [(0, r + 0.01), (0.01, r + 0.01), (0.01, r - 0.01), (-0.04, r * 0.45),
                                      (-0.035, r * 0.3), (-0.01, r * 0.2), (-0.01, 0.0)],
              "rubber", n=12, caps=(False, False), band_roles=[None, None, "steel_dark", "steel_dark", "steel", "steel"])
    m.box((-0.12, 0.56, zf), (0.12, 0.6, zf + 0.004), "rubber")
    cbox(m, (-0.12, h - 0.04, -0.03), (0.12, h, 0.03), "rubber", 0.012)
    cbox(m, (w / 2 - 0.08, h - 0.1, zf), (w / 2 - 0.05, h - 0.085, zf + 0.004), "lamp_green", 0.002)
    _full_collider(pc, p)


def build_boiler(pc: Piece, p: dict, spec: dict) -> None:
    """A basement boiler: a plinth, a banded cylinder with a firebox door, a gauge, a flue and copper pipes."""
    m = pc.mesh
    w, d, h = _dims(p)
    cbox(m, (-w / 2, 0, -d / 2), (w / 2, 0.1, d / 2), "concrete", 0.02)
    r = min(w, d) / 2 - 0.12
    top = h - 0.3
    lathe(m, (0, 0.1, 0), "y", [(0, r - 0.02), (0.03, r), (top - 0.35, r), (top - 0.1, r * 0.75), (top - 0.1, 0.12)],
          "red_paint", n=10, caps=(True, False))
    for y in (0.4, 1.1, top - 0.4):
        lathe(m, (0, y, 0), "y", [(0, r), (0, r + 0.015), (0.04, r + 0.015), (0.04, r)], "steel_dark", n=10,
              caps=(False, False))
    lathe(m, (0, top, 0), "y", [(0, 0.12), (h - top, 0.12), (h - top, 0.0)], "steel", n=8, caps=(False, False))
    cbox(m, (-0.2, 0.25, r - 0.02), (0.2, 0.6, r + 0.06), "steel_dark", 0.02)
    cbox(m, (0.1, 0.4, r + 0.06), (0.16, 0.44, r + 0.1), "steel", 0.006)
    cyl(m, (0.0, 1.35, r - 0.02), "z", d / 2 - r + 0.02 - 0.03, 0.07, "steel", n=8, c=0.01, cap_roles=(None, "enamel"))
    m.box((-0.004, 1.35, d / 2 - 0.03), (0.004, 1.4, d / 2 - 0.026), "lamp_red")
    for sx in (-1, 1):
        x0 = r * 0.92 if sx > 0 else -w / 2
        cyl(m, (x0, 1.6 - (0.5 if sx < 0 else 0.0), -0.15), "x", w / 2 - r * 0.92, 0.04, "copper", n=8)
        m.box((sx * (w / 2 - 0.02) - 0.02, 0.1, -0.19), (sx * (w / 2 - 0.02) + 0.02, 1.64 - (0.5 if sx < 0 else 0.0),
                                                         -0.11), "copper")
    collide_lathe(pc, (0, 0.1, 0), "y", top - 0.1, r + 0.015)
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, 0.1, d / 2))
    collide_lathe(pc, (0, top - 0.1, 0), "y", h - top + 0.1, 0.12)


def build_pump(pc: Piece, p: dict, spec: dict) -> None:
    """A water pump on a plinth: a finned motor, a coupling, the volute with an inlet up and an outlet sideways."""
    m = pc.mesh
    w, d, h = _dims(p)
    pb = 0.15
    cbox(m, (-w / 2, 0, -d / 2), (w / 2, pb, d / 2), "concrete", 0.02)
    cy, r = pb + 0.3, 0.24
    mx0, mx1 = -w / 2 + 0.08, -0.05
    cyl(m, (mx0, cy, 0), "x", mx1 - mx0, r, "machine_green", n=10, c=0.03)
    for i in range(5):
        x = mx0 + 0.12 + i * 0.1
        lathe(m, (x, cy, 0), "x", [(0, r), (0, r + 0.02), (0.03, r + 0.02), (0.03, r)], "machine_green", n=10,
              caps=(False, False))
    cbox(m, (mx0 + 0.15, pb, -0.2), (mx1 - 0.1, cy - r + 0.05, 0.2), "steel_dark", 0.01)
    cyl(m, (mx1, cy, 0), "x", 0.15, 0.09, "steel", n=8)
    vx = 0.1
    cyl(m, (vx, cy, -0.2), "z", 0.4, 0.3 - 0.0, "machine_green", n=12, c=0.04)
    cbox(m, (vx - 0.2, pb, -0.15), (vx + 0.2, cy - 0.25, 0.15), "steel_dark", 0.01)
    cyl(m, (vx, cy + 0.28, 0), "y", h - cy - 0.32, 0.08, "steel", n=8)
    cyl(m, (vx, h - 0.04, 0), "y", 0.04, 0.12, "steel_dark", n=8, c=0.006)
    cyl(m, (vx + 0.28, cy - 0.05, 0), "x", w / 2 - vx - 0.32, 0.08, "steel", n=8)
    cyl(m, (w / 2 - 0.04, cy - 0.05, 0), "x", 0.04, 0.12, "steel_dark", n=8, c=0.006)
    cyl(m, (vx, cy, 0.2), "z", 0.04, 0.08, "steel", n=8, cap_roles=(None, "enamel"))
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, cy + 0.32, d / 2))
    pc.collide_box((vx - 0.12, cy + 0.32, -0.12), (vx + 0.12, h, 0.12))


def build_water_tank(pc: Piece, p: dict, spec: dict) -> None:
    """A water tank on legs: a banded cylinder, a dome with a hatch, a sight glass and an outlet with a valve."""
    m = pc.mesh
    w, d, h = _dims(p)
    r = min(w, d) / 2
    ly = 0.25
    for sx in (-1, 1):
        for sz in (-1, 1):
            cbox(m, (sx * r * 0.6 - 0.04, 0, sz * r * 0.6 - 0.04), (sx * r * 0.6 + 0.04, ly + 0.05, sz * r * 0.6 + 0.04),
                 "steel_dark", 0.008)
    top = h - 0.1
    prof = [(0, r * 0.9), (0.06, r - 0.02)]
    bands = [None]
    for y in (0.15, 0.6, 1.05):
        prof += [(y, r - 0.02), (y, r), (y + 0.05, r), (y + 0.05, r - 0.02)]
        bands += [None, "steel_dark", "steel_dark", "steel_dark"]
    prof += [(top - ly - 0.3, r - 0.02), (top - ly, r * 0.25)]
    bands += [None]
    lathe(m, (0, ly, 0), "y", prof, "machine_grey", n=12, caps=(True, False), band_roles=bands)
    lathe(m, (0, top, 0), "y", [(0, r * 0.25), (0.02, r * 0.25), (0.02, r * 0.2), (h - top, r * 0.2), (h - top, 0.0)],
          "steel_dark", n=8, caps=(False, False))
    m.box((0.25, ly + 0.25, r - 0.03), (0.31, ly + 1.2, r - 0.0), "steel_dark")
    m.box((0.265, ly + 0.3, r - 0.002), (0.295, ly + 1.15, r + 0.0), "water")
    cyl(m, (-0.3, ly + 0.15, r * 0.6), "z", r * 0.4, 0.05, "copper", n=8)
    cbox(m, (-0.36, ly + 0.09, r - 0.1), (-0.24, ly + 0.21, r - 0.04), "red_paint", 0.01)
    collide_lathe(pc, (0, 0, 0), "y", top, r)


def build_switchboard(pc: Piece, p: dict, spec: dict) -> None:
    """A fuse and breaker cabinet with its front open: rows of breakers, a meter, a main handle, a warning plate."""
    m = pc.mesh
    w, d, h = _dims(p)
    m.box((-w / 2 + 0.03, 0, -d / 2 + 0.03), (w / 2 - 0.03, 0.06, d / 2 - 0.03), "steel_dark")
    cbox(m, (-w / 2, 0.06, -d / 2), (w / 2, h, d / 2 - 0.02), "machine_grey", 0.02)
    zf = d / 2 - 0.02
    m.box((-w / 2 + 0.06, 0.3, zf - 0.03), (w / 2 - 0.06, h - 0.25, zf), "steel_dark", faces="+x-x+y-y")
    m.quad_z(-w / 2 + 0.06, w / 2 - 0.06, 0.3, h - 0.25, zf - 0.03, 1, "steel_dark")
    for row in range(5):
        y = 0.5 + row * 0.22
        m.box((-w / 2 + 0.08, y - 0.02, zf - 0.03), (w / 2 - 0.08, y + 0.1, zf - 0.02), "rubber")
        for i in range(6):
            x = -w / 2 + 0.11 + i * (w - 0.22 - 0.06) / 5
            m.box((x, y, zf - 0.02), (x + 0.05, y + 0.08, zf), "enamel")
            m.box((x + 0.018, y + (0.045 if (row + i) % 4 else 0.02), zf), (x + 0.032, y + (0.065 if (row + i) % 4 else 0.04),
                                                                           zf + 0.01), "red_paint" if (row + i) % 4 == 0 else "rubber")
    cyl(m, (-0.14, h - 0.16, zf), "z", 0.02, 0.06, "steel_dark", n=8, cap_roles=(None, "enamel"))
    cbox(m, (0.12, h - 0.22, zf), (0.2, h - 0.08, zf + 0.02), "red_paint", 0.008)
    m.box((-0.12, 0.12, zf), (0.12, 0.24, zf + 0.004), "warning")
    _full_collider(pc, p)


def build_cable_drum(pc: Piece, p: dict, spec: dict) -> None:
    """A wooden cable drum on its rim (axle along X) wound with orange cable, a loose end hanging down the front."""
    m = pc.mesh
    w, d, h = _dims(p)
    r = min(d, h) / 2
    fl = 0.05
    for x0 in (-w / 2, w / 2 - fl):
        cyl(m, (x0, r, 0), "x", fl, r, "wood_light", n=12, c=0.012)
        cyl(m, (x0 + (fl if x0 < 0 else -0.0) - (0.0 if x0 < 0 else 0.02), r, 0), "x", 0.02, 0.07, "steel_dark", n=8)
    cyl(m, (-w / 2 + fl, r, 0), "x", w - 2 * fl, r * 0.82, "cable", n=12)
    for i in range(4):
        x = -w / 2 + fl + 0.02 + i * (w - 2 * fl - 0.04) / 4
        lathe(m, (x, r, 0), "x", [(0, r * 0.82), (0, r * 0.84), (0.1, r * 0.84), (0.1, r * 0.82)], "cable", n=12,
              caps=(False, False))
    cbox(m, (0.05, 0.0, r * 0.82 - 0.02), (0.1, r, r * 0.82 + 0.03), "cable", 0.012)
    collide_lathe(pc, (-w / 2, r, 0), "x", w, r)


def build_enlarger(pc: Piece, p: dict, spec: dict) -> None:
    """A darkroom enlarger: a baseboard with an easel, a column at the back, the lamp head and a bellows lens."""
    m = pc.mesh
    w, d, h = _dims(p)
    cbox(m, (-w / 2, 0, -d / 2), (w / 2, 0.025, d / 2), "wood_light", 0.006)
    cbox(m, (-w / 2 + 0.06, 0.025, -d / 2 + 0.12), (w / 2 - 0.06, 0.035, d / 2 - 0.04), "enamel", 0.003)
    cyl(m, (0, 0.025, -d / 2 + 0.06), "y", h - 0.025, 0.025, "steel", n=8)
    cbox(m, (-0.05, 0.5, -d / 2 + 0.03), (0.05, 0.58, -d / 2 + 0.16), "steel_dark", 0.008)
    cbox(m, (-0.11, 0.5, -d / 2 + 0.1), (0.11, 0.68, 0.08), "plastic_dark", 0.02)
    lathe(m, (0, 0.5, -0.03), "y", [(0, 0.07), (-0.05, 0.055), (-0.08, 0.035), (-0.1, 0.03), (-0.1, 0.0)],
          "rubber", n=8, caps=(False, False), band_roles=[None, None, "steel"])
    cyl(m, (0, 0.68, -0.02), "y", 0.04, 0.05, "plastic_dark", n=8)
    cbox(m, (0.1, 0.55, -0.02), (0.14, 0.59, 0.02), "steel", 0.006)
    _full_collider(pc, p)


def build_tray_table(pc: Piece, p: dict, spec: dict) -> None:
    """The darkroom's wet bench: a sealed table with three developing trays (developer, stop, fixer) and tongs."""
    m = pc.mesh
    w, d, h = _dims(p)
    top = h - 0.06
    table_frame(m, w, d, top, 0.05, "plastic_dark", "steel_dark", leg=0.06, inset=0.03, apron=0.06)
    cbox(m, (-w / 2 + 0.1, 0.15, -d / 2 + 0.1), (w / 2 - 0.1, 0.18, d / 2 - 0.1), "steel_dark", 0.006)
    tw = (w - 0.2) / 3
    for i, (tray, liquid) in enumerate((("enamel", "developer"), ("red_paint", "water"), ("plastic_light", "water"))):
        x0 = -w / 2 + 0.06 + i * (tw + 0.04)
        open_crate(m, (x0, top, -d / 2 + 0.12), (x0 + tw - 0.02, h, d / 2 - 0.12), tray, wall=0.015)
        m.box((x0 + 0.015, h - 0.025, -d / 2 + 0.135), (x0 + tw - 0.035, h - 0.022, d / 2 - 0.135), liquid, faces="+y")
        obox(m, (x0 + tw / 2, h + 0.0 - 0.012, d / 2 - 0.2), (math.cos(0.3), 0, math.sin(0.3)), (0, 1, 0),
             (-math.sin(0.3), 0, math.cos(0.3)), (0.1, 0.006, 0.01), "steel") if i < 2 else None
    _full_collider(pc, p)


def build_toy_chest(pc: Piece, p: dict, spec: dict) -> None:
    """A painted wooden toy chest with rope handles; the lid is a leaf hinged at the back."""
    m = pc.mesh
    w, d, h = _dims(p)
    lid_t = 0.06
    yb = h - lid_t
    bw = w - 0.06
    cbox(m, (-bw / 2, 0, -d / 2 + 0.01), (bw / 2, yb, d / 2 - 0.01), "toy_paint", 0.015)
    for y in (0.06, yb - 0.08):
        m.box((-bw / 2 - 0.004, y, -d / 2 + 0.006), (bw / 2 + 0.004, y + 0.04, d / 2 - 0.006), "wood_light")
    for sx in (-1, 1):
        cbox(m, (sx * bw / 2 - (0.0 if sx > 0 else 0.03), yb - 0.17, -0.07), (sx * bw / 2 + (0.03 if sx > 0 else 0.0),
                                                                              yb - 0.14, 0.07), "cable", 0.008)
    lid = pc.leaf("lid", (0.0, yb, -d / 2))
    cbox(lid, (-bw / 2 - 0.01, yb, -d / 2), (bw / 2 + 0.01, h, d / 2), "toy_paint", 0.02)
    cbox(lid, (-0.04, yb - 0.05, d / 2 - 0.005), (0.04, yb + 0.03, d / 2), "steel", 0.004)
    pc.collide_box((-w / 2, 0, -d / 2), (w / 2, yb, d / 2))
    pc.collide_box((-bw / 2 - 0.01, yb, -d / 2), (bw / 2 + 0.01, h, d / 2), parent=lid.name)


def build_utility_pole(pc: Piece, p: dict, spec: dict) -> None:
    """A timber utility pole with a crossarm, braces, three insulators and step bolts."""
    m = pc.mesh
    w, d, h = _dims(p)
    r = d / 2
    lathe(m, (0, 0, 0), "y", [(0, r), (h - 0.05, r * 0.85), (h, r * 0.6), (h, 0.0)], "wood_dark", n=8, caps=(False, False))
    ay = h - 0.75
    cbox(m, (-w / 2, ay, -0.055), (w / 2, ay + 0.1, 0.055), "wood_dark", 0.012)
    for sx in (-1, 1):
        ang = math.atan2(0.5, 0.45)
        ux = (sx * math.cos(ang), math.sin(ang), 0.0)
        obox(m, (sx * 0.24, ay - 0.25, 0.0), ux, (-sx * math.sin(ang), math.cos(ang), 0.0), (0, 0, 1),
             (0.34, 0.02, 0.02), "steel_dark")
    for x in (-w / 2 + 0.12, 0.35, w / 2 - 0.12):
        lathe(m, (x, ay + 0.1, 0), "y", [(0, 0.03), (0.04, 0.05), (0.06, 0.035), (0.09, 0.05), (0.13, 0.03), (0.13, 0.0)],
              "insulator", n=6, caps=(False, False))
    pc.collide_box((-r, 0, -r), (r, h, r))
    pc.collide_box((-w / 2, ay, -0.055), (w / 2, ay + 0.1, 0.055))


def build_birdbath(pc: Piece, p: dict, spec: dict) -> None:
    """A cast-concrete birdbath: a stepped foot, a tapered pedestal and a bowl holding water."""
    m = pc.mesh
    w, d, h = _dims(p)
    R = min(w, d) / 2
    lathe(m, (0, 0, 0), "y", [(0, 0.2), (0.06, 0.2), (0.08, 0.15), (0.12, 0.09), (h - 0.24, 0.07), (h - 0.14, R - 0.04),
                              (h - 0.04, R), (h, R), (h, R - 0.05), (h - 0.08, R * 0.5), (h - 0.1, 0.0)],
          "concrete", n=12, caps=(True, False))
    lathe(m, (0, h - 0.05, 0), "y", [(0, R - 0.06), (0, 0.0)], "water", n=12, caps=(False, False))
    collide_lathe(pc, (0, 0, 0), "y", h - 0.14, 0.2)
    collide_lathe(pc, (0, h - 0.14, 0), "y", 0.14, R)


def build_bulkhead(pc: Piece, p: dict, spec: dict) -> None:
    """The outdoor stairwell's concrete surround: a 1 m wall round the 4 x 4 m opening, a coping, and an entry gap
    (spec `entry`: x from, x to on the +Z side) where the top flight starts."""
    m = pc.mesh
    w, d, h = _dims(p)
    t = 0.25
    e0, e1 = p.get("entry", [-1.75, -0.25])
    walls = [((-w / 2, 0, -d / 2), (w / 2, h - 0.06, -d / 2 + t)),
             ((-w / 2, 0, -d / 2 + t), (-w / 2 + t, h - 0.06, d / 2)),
             ((w / 2 - t, 0, -d / 2 + t), (w / 2, h - 0.06, d / 2)),
             ((-w / 2 + t, 0, d / 2 - t), (e0, h - 0.06, d / 2)),
             ((e1, 0, d / 2 - t), (w / 2 - t, h - 0.06, d / 2))]
    for lo, hi in walls:
        if hi[0] - lo[0] < 0.01:
            continue
        cbox(m, lo, (hi[0], h - 0.055, hi[2]), "concrete", 0.02)
        cbox(m, (lo[0], h - 0.06, lo[2]), (hi[0], h, hi[2]), "basement", 0.012)
        pc.collide_box(lo, (hi[0], h, hi[2]))


BUILDERS = {
    "box_stack": build_box_stack, "wine_rack": build_wine_rack, "table": build_table,
    "potting_bench": build_potting_bench, "workbench": build_workbench, "board": build_board, "island": build_island,
    "bun_shelf": build_bun_shelf, "chest_freezer": build_chest_freezer, "grill": build_grill, "herb_bed": build_herb_bed,
    "generator": build_generator, "switch": build_switch, "computer": build_computer, "printer": build_printer,
    "parts_shelf": build_parts_shelf, "speaker": build_speaker, "boiler": build_boiler, "pump": build_pump,
    "water_tank": build_water_tank, "switchboard": build_switchboard, "cable_drum": build_cable_drum,
    "enlarger": build_enlarger, "tray_table": build_tray_table, "toy_chest": build_toy_chest,
    "utility_pole": build_utility_pole, "birdbath": build_birdbath, "bulkhead": build_bulkhead,
}


# --- describe and check --------------------------------------------------------------------------------------------
def build_prop(p: dict, spec: dict) -> Piece:
    if p["type"] not in BUILDERS:
        raise ValueError(f"{p['id']}: unknown prop type {p['type']}")
    pc = Piece(p["id"], p["kind"])
    BUILDERS[p["type"]](pc, p, spec)
    pc.meshes = [m for m in pc.meshes if m.faces]
    for k, c in enumerate(pc.colliders):
        c["name"] = f"{pc.id}_col{k}-convcolonly"
    return pc


def _is_surface(spec: dict, role: str) -> bool:
    return spec["roles"][role]["material"] == SURFACE_MATERIAL


def describe(pc: Piece, spec: dict) -> dict:
    """kit_geom.describe, with the game surfaces' UV0 set to 0..1 over each quad and the surfaces listed."""
    d = kit_geom.describe(pc, spec)
    d["surfaces"] = []
    for m in d["meshes"]:
        for i, (face, role) in enumerate(zip(m["faces"], m["roles"])):
            if not _is_surface(spec, role):
                continue
            pts = [m["verts"][j] for j in face]
            x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
            y0, y1 = min(q[1] for q in pts), max(q[1] for q in pts)
            m["uv0"][i] = [[round((q[0] - x0) / (x1 - x0), 6), round((q[1] - y0) / (y1 - y0), 6)] for q in pts]
            d["surfaces"].append({"mesh": m["name"], "face": i, "z": [min(q[2] for q in pts), max(q[2] for q in pts)],
                                  "normal": [round(c, 4) for c in kit_geom.polygon_normal(pts)],
                                  "size_m": [round(x1 - x0, 4), round(y1 - y0, 4)], "corners": len(pts)})
    return d


def build_all(spec: dict) -> list[dict]:
    return [describe(build_prop(p, spec), spec) for p in spec["props"]]


def check_spec(spec: dict) -> list[str]:
    problems = [f"role {r}: redefines a kit role" for r in spec.get("clashes", [])]
    ids = [p["id"] for p in spec["props"]]
    problems += [f"{i}: the id is used twice" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for name, r in spec["roles"].items():
        if r["material"] not in spec["materials"]:
            problems.append(f"role {name}: no material {r['material']}")
    for p in spec["props"]:
        if p["type"] not in BUILDERS:
            problems.append(f"{p['id']}: unknown type {p['type']}")
        if p.get("kind") not in spec["budget_tris"]:
            problems.append(f"{p['id']}: kind {p.get('kind')} has no triangle budget")
        for key in ("w", "d", "h", "station", "chain", "room"):
            if key not in p:
                problems.append(f"{p['id']}: no {key}")
    return problems


def check_prop(d: dict, p: dict, spec: dict) -> list[str]:
    """Budget, size and pivot, collision, UV2, the game surface and the state meshes of one described prop."""
    pid = d["id"]
    problems = []
    budget = spec["budget_tris"][p["kind"]]
    if d["triangles"] > budget:
        problems.append(f"{pid}: {d['triangles']} triangles, over the {p['kind']} budget of {budget}")
    b = d["bounds_m"]
    want = [float(p["w"]), float(p["h"]), float(p["d"])]
    got = [b["max"][i] - b["min"][i] for i in range(3)]
    if any(abs(got[i] - want[i]) > SIZE_TOLERANCE_M for i in range(3)):
        problems.append(f"{pid}: size {[round(v, 3) for v in got]} (x, y, z) is not the spec's {want}")
    if abs(b["min"][1]) > 0.002:
        problems.append(f"{pid}: its lowest point is at y {b['min'][1]}, not on the floor")
    for i, axis in ((0, "x"), (2, "z")):
        if abs(b["min"][i] + b["max"][i]) > 2 * SIZE_TOLERANCE_M:
            problems.append(f"{pid}: not centred on its pivot along {axis} ({b['min'][i]}..{b['max'][i]})")
    if not d["colliders"]:
        problems.append(f"{pid}: no collision")
    for c in d["colliders"]:
        cb = kit_geom.bounds(c["points"])
        if any(cb["max"][i] - cb["min"][i] < 0.003 for i in range(3)):
            problems.append(f"{pid}: collider {c['name']} is flat")
    for m in d["meshes"]:
        if len(m["uv2"]) != len(m["faces"]):
            problems.append(f"{pid}: {m['name']} lacks UV2 on some faces")
        if any(not (-EPS <= c <= 1 + EPS) for face in m["uv2"] for uv in face for c in uv):
            problems.append(f"{pid}: {m['name']} has UV2 outside 0..1")
    if bool(p.get("surface")) != bool(d["surfaces"]):
        problems.append(f"{pid}: {len(d['surfaces'])} game surfaces, the spec says surface = {bool(p.get('surface'))}")
    for s in d["surfaces"]:
        if s["corners"] != 4 or s["z"][1] - s["z"][0] > EPS or s["normal"][2] <= 0:
            problems.append(f"{pid}: the game surface is not one flat quad facing +Z ({s})")
    for m in d["meshes"]:
        seen = [tuple(sorted(f)) for f in m["faces"]]
        twins = len(seen) - len(set(seen))
        if twins:
            problems.append(f"{pid}: {m['name']} has {twins} faces on the same vertices as another (Blender merges them)")
    names = {m["name"] for m in d["meshes"]}
    for node in p.get("nodes", []):
        if f"{pid}_{node}" not in names:
            problems.append(f"{pid}: no mesh {pid}_{node}")
    return problems


def prop_table(described: list[dict], spec: dict) -> list[dict]:
    props = {p["id"]: p for p in spec["props"]}
    rows = []
    for d in described:
        p = props[d["id"]]
        b = d["bounds_m"]
        rows.append({
            "id": d["id"], "kind": d["kind"], "triangles": d["triangles"],
            "budget": spec["budget_tris"][p["kind"]],
            "size_m": [round(b["max"][i] - b["min"][i], 3) for i in (0, 2, 1)],
            "chain": p["chain"], "station": p["station"], "room": p["room"], "count": p.get("count", 1),
            "colliders": len(d["colliders"]), "surfaces": len(d["surfaces"]),
            "nodes": [m["name"] for m in d["meshes"]],
        })
    return rows


def table_md(rows: list[dict]) -> str:
    lines = ["| prop | chain | station (room) | kind | triangles (budget) | w, d, h (m) | count | colliders | "
             "surface | nodes |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        extra = ", ".join(n.removeprefix(r["id"] + "_") for n in r["nodes"][1:]) or "-"
        lines.append(f"| {r['id']} | {r['chain']} | {r['station']} ({r['room']}) | {r['kind']} | {r['triangles']} "
                     f"({r['budget']}) | {', '.join(f'{v:g}' for v in r['size_m'])} | {r['count']} | {r['colliders']} | "
                     f"{'yes' if r['surfaces'] else '-'} | {extra} |")
    return "\n".join(lines) + "\n"
