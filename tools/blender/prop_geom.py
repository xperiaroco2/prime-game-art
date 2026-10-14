"""The House dressing library's geometry (art #87, docs/props.md): pure Python, no Blender, Godot axes (metres, +Y up,
the front faces +Z). It builds every procedural prop of props/library.toml from its `shape` and `params`, turns a pack
prop's imported faces into the library's paint (clustered colours to roles), places the pivot, adds the collider and
describes the result for prop_lib.py (the Blender side) and the tests.

Builders work in the floor frame: x across the prop's L (centred), y from the floor up to H, z across its W (centred),
the front at +z. `finish` moves the prop to its pivot (floor, wall or ceiling) from its measured bounds. A builder takes
the prop's roles by position (`R[0]` the body, the last usually the hardware); a taste change is a role or a hex in the
mapping file, never code. The mesh, UV0 and UV2 helpers are kit_geom's.
"""

from __future__ import annotations

import math
import random
import zlib
from dataclasses import dataclass

import kit_geom
from kit_geom import EPS, Mesh, Piece

CH = 0.004  # the chamfer of the soft boxes, metres (2 to 5 mm reads as clay in the lightmap)
UV2_MARGIN = 0.02  # the lightmap island margin as a share of the prop's largest size
LIGHT_ANCHOR = "LightAnchor"
FINE = "fine"  # the world look's shared textured pack (props/library.toml [fine])
FINE_STEP = 1.0 / 16  # its layer k has vertex alpha 1 - k/16


# --- the spec: kit materials and roles plus the library's ---------------------------------------------------------
def lib_spec(lib: dict, kit: dict) -> dict:
    """A kit_geom-style spec: the kit's materials named by the library's [materials] table (plus the new ones, such
    as emissive, which have no detail texture), the kit's roles and the library's roles mapped to kit materials, and
    the kit's packs (v2: plaster, wood and concrete export as one `kit_set-vcol` material, the layer in vertex alpha).
    The world look's fine pack (`[fine]`, docs/decisions/2026-10-13-house-world-look.md) becomes the pack `fine`: one
    spec material `fine_<layer>` per layer (its roughness, metallic, normal strength and texture `fine_source`), the
    layer in vertex alpha in steps of 1/16, exported as one `kit_fine-vcol`; its roles point at their layer's
    material. Its paint is not divided by a detail mean: the fine shader scales the detail itself (`layer_gain`)."""
    used = set(lib["materials"].values())
    fine = lib.get("fine")
    mats = {}
    for name in sorted(used):
        if fine is not None and name == FINE:
            continue
        if name in kit["materials"]:
            mats[name] = dict(kit["materials"][name])
        elif name in lib.get("new_materials", []):
            mats[name] = {"tile_m": 1.0, "roughness": 0.5, "emissive": name == "emissive"}
            mats[name].update(lib.get("material_props", {}).get(name, {}))
        else:
            raise ValueError(f"[materials] names {name!r}, which the kit lacks and new_materials does not add")
    for name, m in kit["materials"].items():
        mats.setdefault(name, dict(m))
    packs = {k: dict(v) for k, v in kit.get("packs", {}).items()}
    if fine is not None:
        for layer in fine["layers"]:
            mats[f"{FINE}_{layer['name']}"] = {
                "pack": FINE, "tile_m": 1.0, "roughness": layer["roughness"], "metallic": layer.get("metallic", 0.0),
                "normal_strength": layer.get("normal_strength", 0.0), "fine_source": layer.get("source", "")}
        packs[FINE] = {"layers": [f"{FINE}_{layer['name']}" for layer in fine["layers"]], "alpha_step": FINE_STEP}
    roles = {r: dict(v) for r, v in kit["roles"].items()}
    for r, v in lib["roles"].items():
        target = lib["materials"][v["material"]]
        if fine is not None and target == FINE:
            target = f"{FINE}_{v['layer']}"
        roles[r] = {"material": target, "hex": v["hex"]}
    return {"materials": mats, "roles": roles, "packs": packs}


def is_emissive(spec: dict, role: str) -> bool:
    m = spec["materials"][spec["roles"][role]["material"]]
    return bool(m.get("emissive"))


def luminance(hex_or_rgb) -> float:
    if isinstance(hex_or_rgb, str):
        h = hex_or_rgb.lstrip("#")
        rgb = [kit_geom.srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]
    else:
        rgb = hex_or_rgb
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


# --- vector helpers ----------------------------------------------------------------------------------------------
def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _norm(a):
    n = math.sqrt(kit_geom._dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > EPS else (0.0, 1.0, 0.0)


def _ax(axis: str, a: float, u: float, v: float) -> tuple:
    """A point from its coordinate a along axis and (u, v) across it: y -> (x, z), x -> (y, z), z -> (x, y)."""
    if axis == "y":
        return (u, a, v)
    if axis == "x":
        return (a, u, v)
    return (u, v, a)


# --- primitives --------------------------------------------------------------------------------------------------
def cbox(m: Mesh, lo, hi, role: str, c: float = CH) -> None:
    """A closed box with chamfered edges and corners (26 faces); a plain box when it is thinner than 3 chamfers."""
    if min(hi[i] - lo[i] for i in range(3)) < 3 * c:
        m.box(lo, hi, role)
        return

    def pt(k, ax):
        p = [hi[i] if k[i] else lo[i] for i in range(3)]
        for i in range(3):
            if i != ax:
                p[i] += -c if k[i] else c
        return tuple(p)

    for ax in range(3):
        o = [i for i in range(3) if i != ax]
        for s in (0, 1):
            pts = []
            for a, b in ((0, 0), (1, 0), (1, 1), (0, 1)):
                k = [0, 0, 0]
                k[ax], k[o[0]], k[o[1]] = s, a, b
                pts.append(pt(k, ax))
            n = [0, 0, 0]
            n[ax] = 1 if s else -1
            m.poly(pts, n, role)
    for a1, a2 in ((0, 1), (0, 2), (1, 2)):
        t = 3 - a1 - a2
        for s1 in (0, 1):
            for s2 in (0, 1):
                pts = []
                for st, ax in ((0, a1), (0, a2), (1, a2), (1, a1)):
                    k = [0, 0, 0]
                    k[a1], k[a2], k[t] = s1, s2, st
                    pts.append(pt(k, ax))
                n = [0, 0, 0]
                n[a1], n[a2] = (1 if s1 else -1), (1 if s2 else -1)
                m.poly(pts, n, role)
    for k in ((x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)):
        m.poly([pt(k, 0), pt(k, 1), pt(k, 2)], tuple(1 if s else -1 for s in k), role)


def box(m: Mesh, lo, hi, role: str, faces: str = "+x-x+y-y+z-z") -> None:
    m.box(lo, hi, role, faces)


def cyl(m: Mesh, axis: str, c, r0: float, a0: float, a1: float, role: str, n: int = 8, r1: float | None = None,
        caps=(True, True), cap_role: str | None = None, flip: bool = False, sq: float = 1.0, phase: float | None = None
        ) -> None:
    """A cylinder or frustum along axis from a0 (radius r0) to a1 (radius r1), centred on c (the two other
    coordinates); sq squashes the second cross coordinate; flip turns the sides inward (the inside of a shell)."""
    r1 = r0 if r1 is None else r1
    ph = math.pi / n if phase is None else phase
    ring = [(math.cos(ph + 2 * math.pi * i / n), math.sin(ph + 2 * math.pi * i / n) * sq) for i in range(n)]
    lo = [_ax(axis, a0, c[0] + r0 * u, c[1] + r0 * v) for u, v in ring]
    hi = [_ax(axis, a1, c[0] + r1 * u, c[1] + r1 * v) for u, v in ring]
    sgn = -1 if flip else 1
    up = 1 if a1 >= a0 else -1
    for i in range(n):
        j = (i + 1) % n
        nrm = _ax(axis, 0.0, (ring[i][0] + ring[j][0]) * sgn, (ring[i][1] + ring[j][1]) * sgn)
        if r1 < EPS:
            m.poly([lo[i], lo[j], hi[0]], nrm, role)
        elif r0 < EPS:
            m.poly([lo[0], hi[j], hi[i]], nrm, role)
        else:
            m.poly([lo[i], lo[j], hi[j], hi[i]], nrm, role)
    if caps[0] and r0 > EPS:
        m.poly(lo, _ax(axis, -up * sgn, 0.0, 0.0), cap_role or role)
    if caps[1] and r1 > EPS:
        m.poly(hi, _ax(axis, up * sgn, 0.0, 0.0), cap_role or role)


def tube(m: Mesh, axis: str, c, r_in: float, r_out: float, a0: float, a1: float, role: str, n: int = 10,
         cap_role: str | None = None) -> None:
    """A hollow cylinder (a tyre, a ring, a shade): outer and inner walls and two annular caps."""
    cyl(m, axis, c, r_out, a0, a1, role, n, caps=(False, False))
    cyl(m, axis, c, r_in, a0, a1, role, n, caps=(False, False), flip=True)
    ph = math.pi / n
    for a, s in ((a0, -1), (a1, 1)):
        for i in range(n):
            t0, t1 = ph + 2 * math.pi * i / n, ph + 2 * math.pi * (i + 1) / n
            pts = [_ax(axis, a, c[0] + r * math.cos(t), c[1] + r * math.sin(t))
                   for r, t in ((r_in, t0), (r_out, t0), (r_out, t1), (r_in, t1))]
            m.poly(pts, _ax(axis, s, 0.0, 0.0), cap_role or role)


def blob(m: Mesh, c, rx: float, ry: float, rz: float, role: str, n: int = 8, k: int = 5, ry_bottom: float | None = None,
         floor: float | None = None) -> None:
    """An ellipsoid (k latitude bands, n segments); ry_bottom gives the lower half another radius, floor flattens it."""
    rb = ry if ry_bottom is None else ry_bottom
    rings = []
    for j in range(1, k):
        lat = -math.pi / 2 + math.pi * j / k
        ryj = rb if lat < 0 else ry
        y = c[1] + ryj * math.sin(lat)
        if floor is not None:
            y = max(y, floor)
        rings.append([(c[0] + rx * math.cos(lat) * math.cos(2 * math.pi * i / n), y,
                       c[2] + rz * math.cos(lat) * math.sin(2 * math.pi * i / n)) for i in range(n)])
    bottom = (c[0], c[1] - rb if floor is None else max(c[1] - rb, floor), c[2])
    top = (c[0], c[1] + ry, c[2])
    for i in range(n):
        j = (i + 1) % n
        m.poly([bottom, rings[0][j], rings[0][i]], (0, -1, 0), role)
        m.poly([top, rings[-1][i], rings[-1][j]], (0, 1, 0), role)
        for b in range(len(rings) - 1):
            a, d = rings[b], rings[b + 1]
            mid = _mul(_add(_add(a[i], a[j]), _add(d[i], d[j])), 0.25)
            out = (mid[0] - c[0], (mid[1] - c[1]) * 0.1, mid[2] - c[2])
            m.poly([a[i], a[j], d[j], d[i]], out, role)


def _frame(d, ref=None):
    d = _norm(d)
    if ref is None:
        ref = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _norm(kit_geom._cross(d, ref))
    v = _norm(kit_geom._cross(u, d))
    return d, u, v


def bar(m: Mesh, p0, p1, w: float, role: str, h: float | None = None, caps: bool = True, ref=None) -> None:
    """A beam of w x h section from p0 to p1 (legs, rails, frames at any angle); w lies along (p1 - p0) x ref."""
    h = w if h is None else h
    d, u, v = _frame(kit_geom._sub(p1, p0), ref)
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    a = [_add(p0, _add(_mul(u, cu * w / 2), _mul(v, cv * h / 2))) for cu, cv in corners]
    b = [_add(p1, _add(_mul(u, cu * w / 2), _mul(v, cv * h / 2))) for cu, cv in corners]
    for i in range(4):
        j = (i + 1) % 4
        nrm = _add(_mul(u, corners[i][0] + corners[j][0]), _mul(v, corners[i][1] + corners[j][1]))
        m.poly([a[i], a[j], b[j], b[i]], nrm, role)
    if caps:
        m.poly(a, _mul(d, -1), role)
        m.poly(b, d, role)


def rod(m: Mesh, p0, p1, r: float, role: str, n: int = 6, caps: bool = True) -> None:
    """A round bar from p0 to p1."""
    d, u, v = _frame(kit_geom._sub(p1, p0))
    ring = [(math.cos(2 * math.pi * i / n + math.pi / n), math.sin(2 * math.pi * i / n + math.pi / n)) for i in range(n)]
    a = [_add(p0, _add(_mul(u, r * cu), _mul(v, r * sv))) for cu, sv in ring]
    b = [_add(p1, _add(_mul(u, r * cu), _mul(v, r * sv))) for cu, sv in ring]
    for i in range(n):
        j = (i + 1) % n
        nrm = _add(_mul(u, ring[i][0] + ring[j][0]), _mul(v, ring[i][1] + ring[j][1]))
        m.poly([a[i], a[j], b[j], b[i]], nrm, role)
    if caps:
        m.poly(a, _mul(d, -1), role)
        m.poly(b, d, role)


def slab_xz(m: Mesh, pts, y0: float, y1: float, role: str, bottom: bool = False) -> None:
    """A flat polygon in XZ (convex or nearly so) extruded from y0 to y1: rugs, stones, decals."""
    top = [(x, y1, z) for x, z in pts]
    m.poly(top, (0, 1, 0), role)
    if bottom:
        m.poly([(x, y0, z) for x, z in pts], (0, -1, 0), role)
    cx = sum(x for x, _ in pts) / len(pts)
    cz = sum(z for _, z in pts) / len(pts)
    for i in range(len(pts)):
        (ax_, az), (bx, bz) = pts[i], pts[(i + 1) % len(pts)]
        out = ((ax_ + bx) / 2 - cx, 0.0, (az + bz) / 2 - cz)
        m.poly([(ax_, y0, az), (bx, y0, bz), (bx, y1, bz), (ax_, y1, az)], out, role)


def lump(cx: float, cz: float, rx: float, rz: float, n: int, rng: random.Random, jitter: float = 0.12) -> list:
    return [(cx + rx * (1 - jitter * rng.random()) * math.cos(2 * math.pi * i / n),
             cz + rz * (1 - jitter * rng.random()) * math.sin(2 * math.pi * i / n)) for i in range(n)]


def loft(m: Mesh, lo_rect, hi_rect, role: str, inner: float = 0.0, top: bool = False, inner_role: str | None = None
         ) -> None:
    """A tapered box from the rectangle lo_rect (x0, x1, z0, z1, y) up to hi_rect; inner > 0 makes it an open shell
    of that wall thickness (a tray, a planter, a barrow), top closes it."""
    def ring(r, d=0.0):
        x0, x1, z0, z1, y = r
        return [(x0 + d, y, z0 + d), (x1 - d, y, z0 + d), (x1 - d, y, z1 - d), (x0 + d, y, z1 - d)]

    lo, hi = ring(lo_rect), ring(hi_rect)
    cx = (lo_rect[0] + lo_rect[1]) / 2
    cz = (lo_rect[2] + lo_rect[3]) / 2
    for i in range(4):
        j = (i + 1) % 4
        mid = _mul(_add(lo[i], lo[j]), 0.5)
        out = (mid[0] - cx, 0.0, mid[2] - cz)
        m.poly([lo[i], lo[j], hi[j], hi[i]], out, role)
    m.poly(lo, (0, -1, 0), role)
    if inner > 0:
        ilo = ring((lo_rect[0], lo_rect[1], lo_rect[2], lo_rect[3], lo_rect[4] + inner), inner)
        ihi = ring(hi_rect, inner)
        ir = inner_role or role
        for i in range(4):
            j = (i + 1) % 4
            mid = _mul(_add(ilo[i], ilo[j]), 0.5)
            m.poly([ilo[i], ilo[j], ihi[j], ihi[i]], (cx - mid[0], 0.0, cz - mid[2]), ir)
            m.poly([hi[i], hi[j], ihi[j], ihi[i]], (0, 1, 0), role)
        m.poly(ilo, (0, 1, 0), ir)
    elif top:
        m.poly(hi, (0, 1, 0), role)


def bulb(m: Mesh, c, r: float, role: str, h: float | None = None) -> None:
    """A small bulb or flame: an octahedron (8 triangles)."""
    h = r if h is None else h
    pts = [(c[0] + r, c[1], c[2]), (c[0], c[1], c[2] + r), (c[0] - r, c[1], c[2]), (c[0], c[1], c[2] - r)]
    top, bot = (c[0], c[1] + h, c[2]), (c[0], c[1] - h, c[2])
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mid = _mul(_add(a, b), 0.5)
        out = (mid[0] - c[0], 0.0, mid[2] - c[2])
        m.poly([a, b, top], _add(out, (0, 0.5 * r, 0)), role)
        m.poly([a, b, bot], _add(out, (0, -0.5 * r, 0)), role)


# --- generic builders --------------------------------------------------------------------------------------------
def _r(R: list, i: int) -> str:
    return R[min(i, len(R) - 1)]


def _handle(m: Mesh, x: float, y: float, z: float, vertical: bool, role: str, size: float = 0.1) -> None:
    if vertical:
        box(m, (x - 0.01, y - size / 2, z), (x + 0.01, y + size / 2, z + 0.02), role, "+x-x+y-y+z")
    else:
        box(m, (x - size / 2, y - 0.01, z), (x + size / 2, y + 0.01, z + 0.02), role, "+x-x+y-y+z")


def build_cabinet(m, s, R, prm, rng):
    """Cupboards, counters, wardrobes, dressers: params doors, drawers, plinth or legs, top (a role), cornice, sink.
    Roles: R[0] body and fronts, the `top` role for the worktop, the last role the handles (and the sink)."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, hw = R[0], R[-1]
    front_t = 0.02
    y0 = 0.0
    if prm.get("legs"):
        y0 = 0.12 if H > 0.6 else 0.08
        for sx in (-1, 1):
            for sz in (-1, 1):
                x, z = sx * (hx - 0.05), sz * (hz - 0.06)
                box(m, (x - 0.02, 0, z - 0.02), (x + 0.02, y0, z + 0.02), body, "+x-x+z-z")
    elif prm.get("plinth"):
        y0 = 0.08
        box(m, (-hx + 0.02, 0, -hz + 0.02), (hx - 0.02, y0, hz - 0.06), body, "+x-x+z-z")
    y1 = H
    if prm.get("top"):
        top_role = prm["top"]
        cbox(m, (-hx, H - 0.035, -hz), (hx, H, hz), top_role)
        y1 = H - 0.035
    elif prm.get("cornice"):
        cbox(m, (-hx, H - 0.06, -hz), (hx, H, hz), body)
        y1 = H - 0.06
    inset = 0.015 if (prm.get("cornice") or prm.get("top")) else 0.0
    cbox(m, (-hx + inset, y0, -hz + (0.0 if inset == 0 else 0.01)), (hx - inset, y1, hz - front_t), body)
    zf = hz - front_t
    gap = 0.006
    drawers, doors = int(prm.get("drawers", 0)), int(prm.get("doors", 0))
    ya, yb = y0 + 0.01, y1 - 0.01
    fronts = []  # (x0, x1, y0, y1, kind)
    if drawers and doors:
        band = min(0.16, (yb - ya) * 0.25)
        for i in range(drawers):
            fronts.append((-hx + inset, hx - inset, yb - band * (i + 1), yb - band * i, "drawer"))
        yb -= band * drawers
    if drawers and not doors:
        hgt = (yb - ya) / drawers
        for i in range(drawers):
            fronts.append((-hx + inset, hx - inset, ya + hgt * i, ya + hgt * (i + 1), "drawer"))
    if doors:
        wd = (L - 2 * inset) / doors
        for i in range(doors):
            fronts.append((-hx + inset + wd * i, -hx + inset + wd * (i + 1), ya, yb, f"door{i}"))
    for x0, x1, f0, f1, kind in fronts:
        cbox(m, (x0 + gap, f0 + gap, zf), (x1 - gap, f1 - gap, hz), body, c=0.003)
        if kind == "drawer":
            _handle(m, (x0 + x1) / 2, (f0 + f1) / 2, hz, False, hw, min(0.14, (x1 - x0) * 0.3))
        else:
            i = int(kind[4:])
            right = i < doors / 2 if doors > 1 else False
            hxp = x1 - 0.05 if right else x0 + 0.05
            hy = f1 - 0.12 if f1 - f0 > 1.0 else (f0 + f1) / 2 if H < 1.0 else f0 + (f1 - f0) * 0.55
            _handle(m, hxp, hy, hz, True, hw, 0.12 if f1 - f0 > 0.4 else 0.06)
    if prm.get("sink"):
        sx0, sx1 = 0.0, hx - 0.08
        box(m, (sx0, H, -hz + 0.08), (sx1, H + 0.008, hz - 0.08), hw, "+x-x+y+z-z")
        box(m, (sx0 + 0.03, H + 0.008, -hz + 0.11), (sx1 - 0.03, H + 0.009, hz - 0.11), _r(R, 1), "+y")
        rod(m, ((sx0 + sx1) / 2, H, -hz + 0.05), ((sx0 + sx1) / 2, H + 0.08, -hz + 0.05), 0.012, hw, 6)


def build_table(m, s, R, prm, rng):
    """Tables: params legs (4), top (thickness), shelf. Roles: R[0] the top, R[1] the legs if given."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    t = float(prm.get("top", 0.04))
    legs = _r(R, 1)
    cbox(m, (-hx, H - t, -hz), (hx, H, hz), R[0])
    lw = 0.05 if H > 0.5 else 0.045
    ins = 0.04
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * (hx - ins - lw / 2), sz * (hz - ins - lw / 2)
            box(m, (x - lw / 2, 0, z - lw / 2), (x + lw / 2, H - t, z + lw / 2), legs, "+x-x+z-z-y")
    ap = min(0.08, H * 0.2)
    box(m, (-hx + ins, H - t - ap, hz - ins - 0.02), (hx - ins, H - t, hz - ins), R[0], "+z-z-y")
    box(m, (-hx + ins, H - t - ap, -hz + ins), (hx - ins, H - t, -hz + ins + 0.02), R[0], "+z-z-y")
    if prm.get("shelf"):
        box(m, (-hx + ins, 0.12, -hz + ins), (hx - ins, 0.14, hz - ins), R[0])


def build_shelving(m, s, R, prm, rng):
    """Bookcases: params shelves, items (books), back. Roles: R[0] the case, R[1:] the books' paints."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    t = 0.025
    n = int(prm.get("shelves", 4))
    for sx in (-1, 1):
        cbox(m, (sx * hx - (t if sx > 0 else 0), 0, -hz), (sx * hx + (0 if sx > 0 else t), H, hz), R[0])
    cbox(m, (-hx, H - t, -hz), (hx, H, hz), R[0])
    if prm.get("back", 1):
        box(m, (-hx + t, 0, -hz), (hx - t, H - t, -hz + 0.012), R[0], "+z-z")
    box(m, (-hx + t, 0, -hz), (hx - t, 0.07, hz - 0.01), R[0], "+y+z")
    step = (H - t - 0.07) / n
    for i in range(n):
        y = 0.07 + step * i
        if i:
            box(m, (-hx + t, y - 0.02, -hz + 0.012), (hx - t, y, hz - 0.01), R[0], "+y-y+z")
        if prm.get("items") == "books":
            x = -hx + t + 0.02
            paints = R[1:] or R[:1]
            while True:
                bw = 0.025 + 0.03 * rng.random()
                if x + bw > hx - t - 0.03:
                    break
                if rng.random() < 0.12:
                    x += bw
                    continue
                bh = min(step - 0.04, 0.16 + 0.12 * rng.random())
                bd = min(W - 0.06, 0.16 + 0.06 * rng.random())
                box(m, (x, y, -hz + 0.02), (x + bw - 0.003, y + bh, -hz + 0.02 + bd), rng.choice(paints), "+x-x+y+z")
                x += bw


def build_bench(m, s, R, prm, rng):
    """Benches: params back (a backrest), slats (seat slats; 0 for a solid seat), cushion. Roles: R[0] the seat (and
    slats), R[1] the ends (back: cast frames) or the cushion."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    seat_h = 0.45 if prm.get("back") else H - (0.08 if prm.get("cushion") else 0.0)
    slats = int(prm.get("slats", 0))
    frame = _r(R, 1)
    if prm.get("back"):
        for x in (-hx + 0.04, hx - 0.04):
            bar(m, (x, 0, hz - 0.06), (x, seat_h, hz - 0.08), 0.04, frame)
            bar(m, (x, 0, -hz + 0.06), (x, H, -hz + 0.02), 0.04, frame)
            bar(m, (x, seat_h - 0.03, hz - 0.04), (x, seat_h - 0.03, -hz + 0.1), 0.04, frame)
            bar(m, (x, 0.65, -hz + 0.12), (x, 0.65, hz - 0.08), 0.035, frame)
        for i in range(slats):
            z0 = -hz + 0.1 + (W - 0.16) * i / slats
            box(m, (-hx, seat_h - 0.015, z0 + 0.008), (hx, seat_h + 0.015, z0 + (W - 0.16) / slats - 0.008), R[0])
        for i in range(3):
            y = seat_h + 0.12 + 0.11 * i
            z = -hz + 0.1 - (y - seat_h) * 0.15
            box(m, (-hx, y, z - 0.02), (hx, y + 0.08, z), R[0])
        return
    cbox(m, (-hx, seat_h - 0.05, -hz), (hx, seat_h, hz), R[0])
    for sx in (-1, 1):
        box(m, (sx * hx - (0.05 if sx > 0 else 0), 0, -hz + 0.02), (sx * hx + (0 if sx > 0 else 0.05), seat_h - 0.05,
                                                                   hz - 0.02), R[0], "+x-x+z-z")
    box(m, (-hx + 0.05, seat_h - 0.15, hz - 0.04), (hx - 0.05, seat_h - 0.05, hz - 0.02), R[0], "+z-y")
    if prm.get("cushion"):
        cbox(m, (-hx + 0.03, seat_h, -hz + 0.03), (hx - 0.03, H, hz - 0.03), frame, c=0.02)


# --- one builder per prop ----------------------------------------------------------------------------------------
def build_antenna(m, s, R, prm, rng):
    L, W, H = s
    box(m, (-0.1, 0, -0.1), (0.1, 0.02, 0.1), R[0])
    rod(m, (0, 0.02, 0), (0, H, 0), 0.02, R[0], 6)
    y = H - 0.3
    bar(m, (0, y, -W / 2), (0, y, W / 2), 0.025, R[0])
    for i in range(5):
        z = -W / 2 + 0.05 + (W - 0.1) * i / 4
        half = L / 2 * (1 - 0.12 * i)
        bar(m, (-half, y + 0.02, z), (half, y + 0.02, z), 0.012, R[0])
    bar(m, (-0.2, y - 0.4, 0), (0.2, y - 0.4, 0), 0.015, R[0])


def build_backdrop_panel(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    for x in (-hx + 0.02, hx - 0.02):
        bar(m, (x, 0, 0), (x, H, 0), 0.035, R[0])
        bar(m, (x, 0.02, -hz), (x, 0.02, hz), 0.035, R[0])
    bar(m, (-hx, H - 0.02, 0), (hx, H - 0.02, 0), 0.035, R[0])
    cbox(m, (-hx + 0.06, 0.1, -0.012), (hx - 0.06, H - 0.04, 0.012), R[1], c=0.003)


def build_bare_bulb(m, s, R, prm, rng):
    L, W, H = s
    cyl(m, "y", (0, 0), 0.035, H - 0.02, H, R[1], 8)
    rod(m, (0, 0.12, 0), (0, H - 0.02, 0), 0.005, R[1], 4)
    cyl(m, "y", (0, 0), 0.018, 0.09, 0.13, R[1], 8)
    blob(m, (0, 0.055, 0), L / 2, 0.045, L / 2, R[0], 8, 5, ry_bottom=0.055)


def build_bean_bag(m, s, R, prm, rng):
    L, W, H = s
    blob(m, (0, H * 0.4, 0), L / 2, H * 0.6, W / 2, R[0], 12, 6, ry_bottom=H * 0.5, floor=0.0)


def build_bicycle(m, s, R, prm, rng):
    L, W, H = s
    frame, tyre, steel = R[0], R[1], R[2]
    rw = 0.33
    rear, front = (-L / 2 + rw, rw), (L / 2 - rw, rw)
    for cx, cy in (rear, front):
        tube(m, "z", (cx, cy), rw - 0.035, rw, -0.02, 0.02, tyre, 12)
        cyl(m, "z", (cx, cy), 0.03, -0.04, 0.04, steel, 6)
    bb = (-0.05, 0.3)
    seat = (-0.22, 0.85)
    head = (0.36, 0.86)
    head_lo = (0.4, 0.72)
    for a, b in ((rear, bb), (bb, seat), (seat, head), (bb, head_lo), (head, head_lo), (rear, (seat[0] + 0.03, seat[1] - 0.08))):
        bar(m, (a[0], a[1], 0), (b[0], b[1], 0), 0.03, frame)
    bar(m, (head_lo[0], head_lo[1], 0), (front[0], front[1], 0), 0.025, frame)
    bar(m, (head[0], head[1], 0), (head[0] - 0.02, H - 0.02, 0), 0.025, steel)
    rod(m, (head[0] - 0.02, H - 0.02, -W / 2), (head[0] - 0.02, H - 0.02, W / 2), 0.012, steel, 6)
    box(m, (seat[0] - 0.12, seat[1] + 0.03, -0.06), (seat[0] + 0.06, seat[1] + 0.07, 0.06), tyre)
    bar(m, (bb[0], bb[1], -0.08), (bb[0], bb[1], 0.08), 0.02, steel)
    bar(m, (bb[0] - 0.08, bb[1] - 0.12, 0.09), (bb[0] + 0.08, bb[1] + 0.12, 0.09), 0.02, steel)


def build_birdbath(m, s, R, prm, rng):
    L, W, H = s
    body, top = R[0], _r(R, 1)
    cyl(m, "y", (0, 0), 0.16, 0, 0.08, top, 10)
    cyl(m, "y", (0, 0), 0.09, 0.08, H - 0.15, body, 10, r1=0.065)
    cyl(m, "y", (0, 0), 0.1, H - 0.15, H - 0.04, body, 12, r1=L / 2, caps=(True, False))
    tube(m, "y", (0, 0), L / 2 - 0.04, L / 2, H - 0.04, H, body, 12)
    cyl(m, "y", (0, 0), L / 2 - 0.04, H - 0.07, H - 0.03, top, 12, caps=(False, True))


def build_boiler(m, s, R, prm, rng):
    L, W, H = s
    grey, red, dark = R[0], R[1], R[2]
    box(m, (-0.5, 0, -W / 2), (0.5, 0.1, W / 2), dark)
    cyl(m, "y", (0, 0), 0.45, 0.1, 1.75, grey, 12)
    cyl(m, "y", (0, 0), 0.45, 1.75, 1.92, grey, 12, r1=0.18, caps=(False, True))
    cyl(m, "y", (0, 0), 0.1, 1.92, H, dark, 8)
    cbox(m, (-0.18, 0.25, 0.38), (0.18, 0.6, 0.5), dark)
    _handle(m, 0.12, 0.42, 0.5, True, grey, 0.08)
    cyl(m, "z", (0.25, 1.25), 0.07, 0.4, 0.5, dark, 8)
    for y in (0.5, 1.45):
        rod(m, (0.4, y, 0), (L / 2 - 0.06, y, 0), 0.045, red, 8)
        rod(m, (L / 2 - 0.06, y - 0.045, 0), (L / 2 - 0.06, H, 0), 0.045, red, 8) if y > 1 else \
            rod(m, (L / 2 - 0.06, y - 0.045, 0), (L / 2 - 0.06, H - 0.3, 0), 0.045, red, 8)
    rod(m, (-0.4, 0.8, 0), (-L / 2, 0.8, 0), 0.04, red, 8)
    for y in (0.6, 1.2):
        tube(m, "y", (0, 0), 0.45, 0.47, y, y + 0.04, dark, 12)


def build_bottle_crate(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, glass = R[0], R[1]
    ch = H * 0.6
    box(m, (-hx, 0, -hz), (hx, 0.015, hz), wood)
    for sx in (-1, 1):
        box(m, (sx * hx - (0.015 if sx > 0 else 0), 0, -hz), (sx * hx + (0 if sx > 0 else 0.015), ch, hz), wood)
    for sz in (-1, 1):
        box(m, (-hx + 0.015, 0, sz * hz - (0.015 if sz > 0 else 0)), (hx - 0.015, ch * 0.75, sz * hz + (0 if sz > 0 else 0.015)), wood)
    nx, nz = 4, 3
    for i in range(nx):
        for k in range(nz):
            x = -hx + 0.015 + (L - 0.03) * (i + 0.5) / nx
            z = -hz + 0.015 + (W - 0.03) * (k + 0.5) / nz
            r = min((L - 0.03) / nx, (W - 0.03) / nz) * 0.42
            cyl(m, "y", (x, z), r, 0.015, H * 0.68, glass, 6, caps=(False, False))
            cyl(m, "y", (x, z), r, H * 0.68, H * 0.78, glass, 6, r1=r * 0.35, caps=(False, False))
            cyl(m, "y", (x, z), r * 0.35, H * 0.78, H, glass, 6, caps=(False, True))


def build_cabinet_metal(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, dark = R[0], R[1]
    box(m, (-hx + 0.02, 0, -hz + 0.02), (hx - 0.02, 0.08, hz - 0.03), dark, "+x-x+z-z")
    cbox(m, (-hx, 0.08, -hz), (hx, H, hz - 0.02), body)
    for i in range(2):
        x0 = -hx + 0.02 + (L - 0.04) * i / 2
        x1 = x0 + (L - 0.04) / 2
        cbox(m, (x0 + 0.004, 0.12, hz - 0.02), (x1 - 0.004, H - 0.05, hz), body, c=0.003)
        _handle(m, x1 - 0.05 if i == 0 else x0 + 0.05, 1.1, hz, True, dark, 0.14)
        for k in range(4):
            y = 0.3 + 0.06 * k
            box(m, (x0 + 0.06, y, hz), (x1 - 0.06, y + 0.025, hz + 0.008), dark, "+y+z-y")
    box(m, (-0.1, 1.6, hz), (0.1, 1.68, hz + 0.006), _r(R, 0), "+y+z-y+x-x")
    for x in (-0.2, 0.0, 0.2):
        cyl(m, "y", (x, 0), 0.03, H - 0.01, H, dark, 6, caps=(False, True))


def build_cable_drum(m, s, R, prm, rng):
    L, W, H = s
    wood, cable = R[0], R[1]
    cyl(m, "y", (0, 0), L / 2, 0, 0.06, wood, 14)
    cyl(m, "y", (0, 0), L / 2, H - 0.06, H, wood, 14)
    cyl(m, "y", (0, 0), L * 0.36, 0.06, H - 0.06, cable, 12, caps=(False, False))
    cyl(m, "y", (0, 0), 0.08, H - 0.0, H + 0.0, wood, 6, caps=(False, False))


def build_cage_lamp(m, s, R, prm, rng):
    L, W, H = s
    hz = W / 2
    lamp, metal = R[0], R[1]
    box(m, (-0.04, -0.0, -hz), (0.04, H, -hz + 0.015), metal)
    cyl(m, "z", (0, H / 2), 0.03, -hz + 0.015, -hz + 0.06, metal, 8)
    blob(m, (0, H / 2, -hz + 0.11), 0.045, 0.045, 0.05, lamp, 8, 4)
    r = L / 2 - 0.005
    for z in (-hz + 0.06, hz - 0.01):
        tube(m, "z", (0, H / 2), r - 0.006, r, z, z + 0.008, metal, 10)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        x, y = r * math.cos(a) * 0.97, H / 2 + r * math.sin(a) * 0.97
        bar(m, (x, y, -hz + 0.06), (x, y, hz - 0.002), 0.006, metal)


def build_cardboard_box(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    cbox(m, (-hx, 0, -hz), (hx, H - 0.004, hz), R[0], c=0.006)
    box(m, (-0.03, H - 0.006, -hz - 0.002), (0.03, H, hz + 0.002), R[0], "+y+z-z")
    box(m, (-hx, H - 0.006, -0.002), (hx, H - 0.004, 0.002), R[0], "+y")


def build_chandelier(m, s, R, prm, rng):
    L, W, H = s
    lamp, metal = R[0], R[1]
    cyl(m, "y", (0, 0), 0.06, H - 0.03, H, metal, 8)
    rod(m, (0, 0.3, 0), (0, H - 0.03, 0), 0.008, metal, 4)
    cyl(m, "y", (0, 0), 0.03, 0.18, 0.32, metal, 6, r1=0.08)
    cyl(m, "y", (0, 0), 0.04, 0.0, 0.18, metal, 6, r1=0.02)
    arms = 6
    ra = L / 2 - 0.04
    for k in range(arms):
        a = 2 * math.pi * k / arms
        x, z = ra * math.cos(a), ra * math.sin(a) / math.sin(math.pi / 3)
        bar(m, (0, 0.24, 0), (x * 0.6, 0.18, z * 0.6), 0.018, metal)
        bar(m, (x * 0.6, 0.18, z * 0.6), (x, 0.24, z), 0.018, metal)
        cyl(m, "y", (x, z), 0.035, 0.24, 0.29, metal, 6, r1=0.04)
        bulb(m, (x, 0.34, z), 0.022, lamp, 0.05)


def build_coat_rack(m, s, R, prm, rng):
    L, W, H = s
    wood, coat_a, coat_b = R[0], _r(R, 1), _r(R, 2)
    rod(m, (0, 0.02, 0), (0, H - 0.04, 0), 0.025, wood, 8)
    blob(m, (0, H - 0.04, 0), 0.04, 0.04, 0.04, wood, 6, 4)
    for a in range(4):
        ang = math.pi / 4 + a * math.pi / 2
        bar(m, (0, 0.15, 0), (math.copysign(L / 2 - 0.02, math.cos(ang)), 0.0, math.copysign(W / 2 - 0.02, math.sin(ang))),
            0.03, wood)
        bar(m, (0, H - 0.2, 0), (0.12 * math.cos(ang), H - 0.12, 0.12 * math.sin(ang)), 0.02, wood)
    blob(m, (0.12, 1.25, 0.05), 0.13, 0.3, 0.1, coat_a, 8, 5)
    blob(m, (-0.13, 1.2, -0.04), 0.12, 0.33, 0.1, coat_b, 8, 5)


def build_deckchair(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, a, b = R[0], _r(R, 1), _r(R, 2)
    for x in (-hx + 0.02, hx - 0.02):
        bar(m, (x, 0, hz - 0.1), (x, H - 0.02, -hz + 0.05), 0.035, wood)
        bar(m, (x, 0, -hz + 0.12), (x, 0.42, hz), 0.035, wood)
    bar(m, (-hx, H - 0.04, -hz + 0.06), (hx, H - 0.04, -hz + 0.06), 0.03, wood)
    bar(m, (-hx, 0.4, hz - 0.03), (hx, 0.4, hz - 0.03), 0.03, wood)
    path = [(H - 0.06, -hz + 0.08), (0.22, 0.1), (0.38, hz - 0.06)]
    stripes = [a, b, a, b, a]
    for k, role in enumerate(stripes):
        x0 = -hx + 0.05 + (L - 0.1) * k / len(stripes)
        x1 = -hx + 0.05 + (L - 0.1) * (k + 1) / len(stripes)
        for (y0, z0), (y1, z1) in zip(path, path[1:]):
            bar(m, ((x0 + x1) / 2, y0, z0), ((x0 + x1) / 2, y1, z1), x1 - x0, role, 0.008, caps=False)


def build_enlarger(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    dark, grey, wood = R[0], R[1], R[2]
    cbox(m, (-hx, 0, -hz), (hx, 0.03, hz), wood)
    rod(m, (0, 0.03, -hz + 0.06), (0, H, -hz + 0.06), 0.022, grey, 8)
    cbox(m, (-0.04, 0.45, -hz + 0.03), (0.04, 0.55, -hz + 0.12), grey)
    cbox(m, (-0.11, 0.5, -hz + 0.1), (0.11, 0.66, 0.12), dark)
    cyl(m, "y", (0, 0.0), 0.08, 0.66, 0.74, dark, 8, r1=0.06)
    cyl(m, "y", (0, 0.0), 0.08, 0.38, 0.5, dark, 8, r1=0.1)
    cyl(m, "y", (0, 0.0), 0.03, 0.32, 0.38, grey, 8)


def build_filing_cabinet(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, dark = R[0], R[1]
    cbox(m, (-hx, 0, -hz), (hx, H, hz - 0.015), body)
    n = 4
    for i in range(n):
        y0 = 0.03 + (H - 0.06) * i / n
        y1 = 0.03 + (H - 0.06) * (i + 1) / n
        cbox(m, (-hx + 0.02, y0 + 0.005, hz - 0.015), (hx - 0.02, y1 - 0.005, hz), body, c=0.003)
        _handle(m, 0, y1 - 0.09, hz, False, dark, 0.14)
        box(m, (-0.05, y1 - 0.05, hz), (0.05, y1 - 0.025, hz + 0.004), dark, "+y-y+z+x-x")


def build_fireplace(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    brick, trim, dark = R[0], R[1], R[2]
    pw = 0.36
    mantel = H - 0.1
    for sx in (-1, 1):
        x0, x1 = (-hx + 0.05, -hx + 0.05 + pw) if sx < 0 else (hx - 0.05 - pw, hx - 0.05)
        cbox(m, (x0, 0.04, -hz), (x1, mantel, hz - 0.12), brick)
    cbox(m, (-hx + 0.05 + pw, 0.8, -hz), (hx - 0.05 - pw, mantel, hz - 0.12), brick)
    box(m, (-hx + 0.05 + pw, 0.04, -hz), (hx - 0.05 - pw, 0.8, -hz + 0.05), dark, "+z+y-x+x")
    cbox(m, (-hx, mantel, -hz), (hx, mantel + 0.06, hz - 0.06), trim)
    box(m, (-hx + 0.1, mantel + 0.06, -hz), (hx - 0.1, H, -hz + 0.04), trim, "+y+z+x-x")
    cbox(m, (-hx + 0.1, 0, -hz), (hx - 0.1, 0.04, hz), trim)
    for k in range(5):
        x = -0.25 + 0.125 * k
        bar(m, (x, 0.08, -hz + 0.12), (x, 0.08, hz - 0.2), 0.015, dark)
    bar(m, (-0.3, 0.12, hz - 0.2), (0.3, 0.12, hz - 0.2), 0.015, dark)
    bar(m, (-0.25, 0.05, -hz + 0.18), (0.25, 0.15, -hz + 0.18), 0.05, dark)


def build_fluorescent(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    tube_r, metal = R[0], R[1]
    cbox(m, (-hx, H - 0.03, -hz), (hx, H, hz), metal, c=0.003)
    for sx in (-1, 1):
        box(m, (sx * hx - (0.04 if sx > 0 else 0), H * 0.25, -0.02), (sx * hx + (0 if sx > 0 else 0.04), H - 0.03, 0.02), metal)
    cyl(m, "x", (H * 0.45, 0), 0.016, -hx + 0.04, hx - 0.04, tube_r, 6)


def build_ground_decal(m, s, R, prm, rng):
    L, W, H = s
    slab_xz(m, lump(0, 0, L / 2, W / 2, 14, rng, 0.15), 0, H, R[0])


def build_hose_reel(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    hose, frame = R[0], R[1]
    cy = 0.28
    for z in (-hz + 0.015, hz - 0.015):
        bar(m, (-hx + 0.02, 0, z), (0, cy, z), 0.025, frame)
        bar(m, (hx - 0.02, 0, z), (0, cy, z), 0.025, frame)
        bar(m, (0, cy, z), (-0.05, H - 0.02, z), 0.022, frame)
    rod(m, (-0.05, H - 0.02, -hz), (-0.05, H - 0.02, hz), 0.015, frame, 6)
    cyl(m, "z", (0, cy), 0.2, -hz + 0.04, -hz + 0.05, frame, 12)
    cyl(m, "z", (0, cy), 0.2, hz - 0.05, hz - 0.04, frame, 12)
    cyl(m, "z", (0, cy), 0.16, -hz + 0.05, hz - 0.05, hose, 12, caps=(False, False))
    rod(m, (0, cy, -hz), (0, cy, hz), 0.02, frame, 6)
    rod(m, (0.12, cy - 0.12, hz - 0.06), (hx - 0.03, 0.02, hz - 0.06), 0.015, hose, 5)


def build_hydrant(m, s, R, prm, rng):
    L, W, H = s
    red, grey = R[0], R[1]
    cyl(m, "y", (0, 0), 0.12, 0, 0.06, grey, 10)
    cyl(m, "y", (0, 0), 0.09, 0.06, H - 0.18, red, 10)
    tube(m, "y", (0, 0), 0.09, 0.105, H - 0.3, H - 0.26, red, 10)
    cyl(m, "y", (0, 0), 0.1, H - 0.18, H - 0.08, red, 10, r1=0.04, caps=(True, False))
    cyl(m, "y", (0, 0), 0.03, H - 0.08, H, grey, 6)
    cyl(m, "x", (0.45, 0), 0.04, -L / 2, L / 2, grey, 8)
    cyl(m, "z", (0, 0.45), 0.05, 0, W / 2, red, 8)


def build_jerrycan(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    body = R[0]
    bh = H - 0.08
    cbox(m, (-hx, 0, -hz), (hx, bh, hz), body, c=0.012)
    for sz in (-1, 1):
        z = sz * hz
        bar(m, (-hx + 0.05, 0.06, z), (hx - 0.05, bh - 0.06, z), 0.025, body, 0.006)
        bar(m, (-hx + 0.05, bh - 0.06, z), (hx - 0.05, 0.06, z), 0.025, body, 0.006)
    for x in (-0.09, -0.02, 0.05):
        bar(m, (x, bh, -0.025), (x, H - 0.01, -0.025), 0.02, body, 0.03)
    bar(m, (-0.1, H - 0.015, -0.025), (0.06, H - 0.015, -0.025), 0.02, body, 0.03)
    cyl(m, "y", (hx - 0.05, 0), 0.025, bh, H - 0.02, body, 6)


def build_log_stack(m, s, R, prm, rng):
    L, W, H = s
    bark, cut = R[0], _r(R, 1)
    rows = 5
    r = min(L / 14, H / (2 + (rows - 1) * math.sqrt(3)))
    for row in range(rows):
        n = 7 if row % 2 == 0 else 6
        y = r + row * r * math.sqrt(3)
        for i in range(n):
            x = -L / 2 + r + 2 * r * i + (r if row % 2 else 0)
            rr = r * (0.92 + 0.08 * rng.random())
            cyl(m, "z", (x, y), rr, -W / 2 + 0.03 * rng.random(), W / 2 - 0.03 * rng.random(), bark, 5,
                cap_role=cut, phase=rng.random())


def build_mailbox(m, s, R, prm, rng):
    L, W, H = s
    body, post = R[0], R[1]
    top = H - 0.2
    bar(m, (0, 0, 0), (0, top, 0), 0.07, post)
    cbox(m, (-L / 2, top, -W / 2), (L / 2, top + 0.12, W / 2), body)
    cyl(m, "x", (top + 0.1, 0), W / 2, -L / 2, L / 2, body, 10, sq=0.8)
    box(m, (L / 2, top + 0.04, -0.02), (L / 2 + 0.01, top + 0.2, 0.0), post)
    box(m, (-0.08, top + 0.05, W / 2), (0.08, top + 0.07, W / 2 + 0.005), post, "+y-y+z")


def build_path_light(m, s, R, prm, rng):
    L, W, H = s
    lamp, metal = R[0], R[1]
    cyl(m, "y", (0, 0), 0.06, 0, 0.02, metal, 8)
    cyl(m, "y", (0, 0), 0.025, 0.02, H - 0.15, metal, 6)
    cyl(m, "y", (0, 0), 0.055, H - 0.15, H - 0.06, lamp, 8)
    cyl(m, "y", (0, 0), L / 2, H - 0.06, H, metal, 8, r1=0.03)


def build_pegboard(m, s, R, prm, rng):
    L, W, H = s
    hx = L / 2
    board, dark, red = R[0], R[1], R[2]
    zb = -W / 2
    box(m, (-hx, 0, zb), (hx, H, zb + 0.015), board, "+x-x+y-y+z")
    for x in (-hx + 0.03, hx - 0.03):
        box(m, (x - 0.02, 0, zb + 0.015), (x + 0.02, H, zb + 0.03), board, "+x-x+y-y+z")
    z0 = zb + 0.015
    tools = 9
    for i in range(tools):
        x = -hx + 0.2 + (L - 0.4) * i / (tools - 1)
        y = 0.35 + (0.45 if i % 2 else 0.0) + 0.1 * rng.random()
        kind = i % 3
        box(m, (x - 0.004, y + 0.22, z0), (x + 0.004, y + 0.24, z0 + 0.08), dark, "+x-x+y-y+z")
        if kind == 0:
            box(m, (x - 0.015, y - 0.05, z0 + 0.01), (x + 0.015, y + 0.18, z0 + 0.04), red)
            box(m, (x - 0.06, y + 0.18, z0 + 0.01), (x + 0.06, y + 0.22, z0 + 0.04), dark)
        elif kind == 1:
            bar(m, (x, y - 0.1, z0 + 0.02), (x, y + 0.2, z0 + 0.02), 0.025, dark, 0.012)
            box(m, (x - 0.03, y + 0.17, z0 + 0.01), (x + 0.03, y + 0.22, z0 + 0.03), dark)
        else:
            box(m, (x - 0.07, y - 0.2, z0 + 0.008), (x + 0.07, y + 0.12, z0 + 0.012), dark, "+z-z+x-x-y")
            box(m, (x - 0.03, y + 0.12, z0 + 0.005), (x + 0.03, y + 0.22, z0 + 0.03), red)


def build_pendant_industrial(m, s, R, prm, rng):
    L, W, H = s
    lamp, shade = R[0], R[1]
    cyl(m, "y", (0, 0), 0.04, H - 0.02, H, shade, 8)
    rod(m, (0, 0.2, 0), (0, H - 0.02, 0), 0.006, shade, 4)
    cyl(m, "y", (0, 0), 0.05, 0.16, 0.22, shade, 8)
    cyl(m, "y", (0, 0), L / 2, 0.0, 0.16, shade, 12, r1=0.055, caps=(False, False))
    cyl(m, "y", (0, 0), L / 2 - 0.006, 0.0, 0.155, shade, 12, r1=0.05, caps=(False, False), flip=True)
    blob(m, (0, 0.08, 0), 0.05, 0.05, 0.05, lamp, 8, 4)


def build_pendant_shade(m, s, R, prm, rng):
    L, W, H = s
    lamp, shade = R[0], R[1]
    cyl(m, "y", (0, 0), 0.04, H - 0.02, H, shade, 8)
    rod(m, (0, 0.2, 0), (0, H - 0.02, 0), 0.006, shade, 4)
    tube(m, "y", (0, 0), L / 2 - 0.01, L / 2, 0.0, 0.22, shade, 12)
    blob(m, (0, 0.11, 0), 0.05, 0.06, 0.05, lamp, 8, 4)


def build_picnic_table(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood = R[0]
    for k in range(4):
        z0 = -0.2 + 0.1 * k
        box(m, (-hx, H - 0.03, z0 + 0.005), (hx, H, z0 + 0.095), wood)
    for sz in (-1, 1):
        box(m, (-hx + 0.05, H * 0.55, sz * hz - (0.14 if sz > 0 else 0)), (hx - 0.05, H * 0.55 + 0.03,
                                                                            sz * hz + (0 if sz > 0 else 0.14)), wood)
    for x in (-hx + 0.2, hx - 0.2):
        bar(m, (x, 0, -hz + 0.1), (x, H - 0.03, 0.05), 0.05, wood, 0.035)
        bar(m, (x, 0, hz - 0.1), (x, H - 0.03, -0.05), 0.05, wood, 0.035)
        box(m, (x - 0.025, H * 0.55 - 0.05, -hz + 0.02), (x + 0.025, H * 0.55, hz - 0.02), wood)


def build_picture_frame(m, s, R, prm, rng):
    L, W, H = s
    hx = L / 2
    wood, mat, pic = R[0], R[1], R[2]
    zb, zf = -W / 2, W / 2
    fw = 0.04
    box(m, (-hx, 0, zb), (hx, fw, zf), wood, "+x-x+y-y+z")
    box(m, (-hx, H - fw, zb), (hx, H, zf), wood, "+x-x+y-y+z")
    box(m, (-hx, fw, zb), (-hx + fw, H - fw, zf), wood, "+x-x+z")
    box(m, (hx - fw, fw, zb), (hx, H - fw, zf), wood, "+x-x+z")
    box(m, (-hx + fw, fw, zb), (hx - fw, H - fw, zb + 0.012), mat, "+z")
    box(m, (-hx + 0.09, H * 0.25, zb + 0.012), (hx - 0.09, H * 0.5, zb + 0.014), pic, "+z+y")
    box(m, (-hx + 0.09, H * 0.5, zb + 0.012), (hx - 0.09, H - 0.09, zb + 0.013), mat, "+z")
    blob(m, (0.08, H * 0.62, zb + 0.014), 0.04, 0.04, 0.002, wood, 6, 3)


def build_pipe(m, s, R, prm, rng):
    L, W, H = s
    pipe, metal = R[0], R[1]
    hx = L / 2
    r = H / 2 * 0.65
    cyl(m, "x", (H / 2, 0), r, -hx, hx, pipe, 8)
    n = int(prm.get("flanges", 2))
    for i in range(n):
        x = -hx + L * (i + 1) / (n + 1)
        cyl(m, "x", (H / 2, 0), H / 2, x - 0.02, x + 0.02, metal, 8)
    for x in (-hx + 0.15, hx - 0.15):
        box(m, (x - 0.02, 0, -0.03), (x + 0.02, H / 2 - r + 0.01, 0.03), metal)
    if prm.get("valve"):
        cyl(m, "y", (0, 0), 0.02, H / 2, H, metal, 6)
        tube(m, "y", (0, 0), 0.07, 0.085, H - 0.02, H, pipe, 8)


def build_porch_lamp(m, s, R, prm, rng):
    L, W, H = s
    lamp, metal = R[0], R[1]
    zb = -W / 2
    box(m, (-0.05, 0.03, zb), (0.05, 0.22, zb + 0.02), metal)
    bar(m, (0, 0.1, zb + 0.02), (0, 0.1, 0.0), 0.025, metal)
    zc = zb + 0.02 + (W - 0.02) / 2 + 0.01
    hw = min(L, W - 0.02) / 2 - 0.02
    box(m, (-hw - 0.01, 0.0, zc - hw - 0.01), (hw + 0.01, 0.04, zc + hw + 0.01), metal)
    box(m, (-hw + 0.01, 0.04, zc - hw + 0.01), (hw - 0.01, H - 0.1, zc + hw - 0.01), lamp)
    for sx in (-1, 1):
        for sz in (-1, 1):
            bar(m, (sx * hw, 0.04, zc + sz * hw), (sx * hw, H - 0.1, zc + sz * hw), 0.012, metal)
    cyl(m, "y", (0, zc), (hw + 0.03) * math.sqrt(2), H - 0.1, H - 0.02, metal, 4, r1=0.02, phase=math.pi / 4)
    cyl(m, "y", (0, zc), 0.015, H - 0.02, H, metal, 4)


def build_post_lamp(m, s, R, prm, rng):
    L, W, H = s
    lamp, metal = R[0], R[1]
    hw = L / 2 - 0.03
    cyl(m, "y", (0, 0), 0.12, 0, 0.25, metal, 8, r1=0.06)
    cyl(m, "y", (0, 0), 0.04, 0.25, H - 0.38, metal, 8)
    box(m, (-hw, H - 0.38, -hw), (hw, H - 0.34, hw), metal)
    box(m, (-hw + 0.02, H - 0.34, -hw + 0.02), (hw - 0.02, H - 0.12, hw - 0.02), lamp)
    for sx in (-1, 1):
        for sz in (-1, 1):
            bar(m, (sx * hw, H - 0.34, sz * hw), (sx * hw, H - 0.12, sz * hw), 0.014, metal)
    cyl(m, "y", (0, 0), L / 2 * math.sqrt(2) * 0.97, H - 0.12, H - 0.03, metal, 4, r1=0.02, phase=math.pi / 4)
    cyl(m, "y", (0, 0), 0.015, H - 0.03, H, metal, 4)


def build_potting_bench(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, soil, pot = R[0], R[1], R[2]
    top = 0.75
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * (hx - 0.05), sz * (hz - 0.05)
            box(m, (x - 0.03, 0, z - 0.03), (x + 0.03, top - 0.03, z + 0.03), wood, "+x-x+z-z")
    for k in range(4):
        z0 = -hz + W * k / 4
        box(m, (-hx, top - 0.03, z0 + 0.006), (hx, top, z0 + W / 4 - 0.006), wood)
    for k in range(2):
        z0 = -hz + 0.04 + (W - 0.08) * k / 2
        box(m, (-hx + 0.08, 0.15, z0 + 0.006), (hx - 0.08, 0.17, z0 + (W - 0.08) / 2 - 0.006), wood)
    box(m, (-hx, top, -hz), (hx, H, -hz + 0.025), wood)
    for x in (-0.5, -0.2, 0.35):
        cyl(m, "y", (x, 0.05), 0.075, top, top + 0.13, pot, 7, r1=0.095, cap_role=soil)
    cbox(m, (0.3, 0.17, -0.2), (0.75, 0.42, 0.15), soil, c=0.03)


def build_pump(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    green, grey, dark = R[0], R[1], R[2]
    box(m, (-hx + 0.05, 0, -hz), (hx - 0.15, 0.08, hz), dark)
    cyl(m, "x", (0.38, 0), 0.26, -hx + 0.1, -0.05, green, 12)
    for k in range(5):
        x = -hx + 0.18 + 0.1 * k
        tube(m, "x", (0.38, 0), 0.26, 0.28, x, x + 0.02, green, 12)
    cyl(m, "x", (0.38, 0), 0.09, -0.05, 0.08, grey, 8)
    cyl(m, "x", (0.38, 0), 0.32, 0.08, 0.32, green, 12)
    for x in (-0.4, 0.2):
        box(m, (x - 0.1, 0.08, -0.2), (x + 0.1, 0.14, 0.2), dark)
    cyl(m, "y", (0.2, 0), 0.07, 0.7, H, grey, 8)
    cyl(m, "y", (0.2, 0), 0.1, H - 0.04, H, grey, 8)
    cyl(m, "x", (0.38, 0), 0.07, 0.32, hx, grey, 8)
    cyl(m, "x", (0.38, 0), 0.1, hx - 0.04, hx, grey, 8)
    cyl(m, "z", (-0.3, 0.68), 0.06, -0.02, 0.06, dark, 8)


def build_rolled_carpet(m, s, R, prm, rng):
    L, W, H = s
    r = min(W, H) / 2
    tube(m, "x", (r, 0), r * 0.25, r, -L / 2 + 0.01, L / 2 - 0.01, R[0], 10)
    for x in (-L / 4, L / 4):
        cyl(m, "x", (r, 0), r + 0.004, x - 0.02, x + 0.02, R[0], 10, caps=(False, False))
    box(m, (-L / 2 + 0.01, 0.0, r * 0.6), (-L / 2 + 0.25, 0.008, r + 0.02), R[0], "+y+x+z-z")


def build_roof_vent(m, s, R, prm, rng):
    L, W, H = s
    metal = R[0]
    box(m, (-L / 2, 0, -W / 2), (L / 2, 0.025, W / 2), metal)
    cyl(m, "y", (0, 0), 0.24, 0.0, 0.08, metal, 10, r1=0.17, caps=(False, False))
    cyl(m, "y", (0, 0), 0.17, 0.08, H - 0.14, metal, 10, caps=(False, True))
    for k in range(3):
        a = 2 * math.pi * k / 3
        bar(m, (0.15 * math.cos(a), H - 0.15, 0.15 * math.sin(a)), (0.15 * math.cos(a), H - 0.08, 0.15 * math.sin(a)), 0.02, metal)
    cyl(m, "y", (0, 0), 0.3, H - 0.08, H, metal, 10, r1=0.05)


def build_rug(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    base, pattern = R[0], _r(R, 1)
    box(m, (-hx, 0, -hz), (hx, H * 0.6, hz), base, "+x-x+y+z-z")
    b, w = 0.12, 0.08
    for x0, x1, z0, z1 in ((-hx + b, hx - b, -hz + b, -hz + b + w), (-hx + b, hx - b, hz - b - w, hz - b),
                           (-hx + b, -hx + b + w, -hz + b + w, hz - b - w), (hx - b - w, hx - b, -hz + b + w, hz - b - w)):
        box(m, (x0, H * 0.6, z0), (x1, H, z1), pattern, "+x-x+y+z-z")
    slab_xz(m, [(0, -hz * 0.45), (hx * 0.4, 0), (0, hz * 0.45), (-hx * 0.4, 0)], H * 0.6, H, pattern)


def build_safelight(m, s, R, prm, rng):
    L, W, H = s
    lamp, metal = R[0], R[1]
    zb = -W / 2
    box(m, (-0.03, H - 0.04, zb), (0.03, H, zb + 0.04), metal)
    cbox(m, (-L / 2, 0.0, zb + 0.03), (L / 2, H - 0.04, W / 2 - 0.01), metal)
    box(m, (-L / 2 + 0.025, 0.025, W / 2 - 0.01), (L / 2 - 0.025, H - 0.065, W / 2), lamp, "+z+x-x+y-y")


def build_sconce(m, s, R, prm, rng):
    L, W, H = s
    lamp, metal = R[0], R[1]
    zb = -W / 2
    cyl(m, "z", (0, 0.065), 0.065, zb, zb + 0.015, metal, 8, phase=0.0)
    bar(m, (0, 0.08, zb + 0.015), (0, 0.1, 0.0), 0.015, metal)
    cyl(m, "y", (0, 0.0), 0.03, 0.08, 0.11, metal, 8)
    cyl(m, "y", (0, 0.0), 0.04, 0.11, H, lamp, 10, r1=L / 2, sq=W / L * 0.98)


def build_sheeted(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    cloth = R[0]
    cbox(m, (-hx + 0.02, 0, -hz + 0.02), (hx - 0.02, H * 0.55, hz), cloth, c=0.08)
    cbox(m, (-hx + 0.04, 0, -hz), (hx - 0.04, H, -hz + 0.32), cloth, c=0.1)
    for sx in (-1, 1):
        cbox(m, (sx * hx - (0.24 if sx > 0 else 0), 0, -hz + 0.05), (sx * hx + (0 if sx > 0 else 0.24), H * 0.72, hz - 0.03),
             cloth, c=0.08)
    blob(m, (0.0, H * 0.55, 0.1), hx * 0.6, 0.05, hz * 0.5, cloth, 8, 3)


def build_shelving_jars(m, s, R, prm, rng):
    build_shelving(m, s, [R[0]], {"shelves": 5, "back": 1}, rng)
    L, W, H = s
    hx = L / 2
    wood, glass, fill = R[0], R[1], R[2]
    step = (H - 0.025 - 0.07) / 5
    for i in range(5):
        y = 0.07 + step * i
        n = 6
        for k in range(n):
            x = -hx + 0.1 + (L - 0.2) * k / (n - 1)
            h = 0.12 + 0.08 * rng.random()
            r = 0.04 + 0.015 * rng.random()
            cyl(m, "y", (x, 0.0), r, y, y + h, glass, 6, caps=(False, False))
            cyl(m, "y", (x, 0.0), r * 0.85, y, y + h * (0.4 + 0.4 * rng.random()), fill, 6, caps=(False, True))
            cyl(m, "y", (x, 0.0), r * 1.05, y + h, y + h + 0.02, wood, 6, caps=(False, True))


def build_shelving_metal(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    metal, box_role = R[0], R[1]
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * (hx - 0.02), sz * (hz - 0.02)
            box(m, (x - 0.02, 0, z - 0.02), (x + 0.02, H, z + 0.02), metal, "+x-x+z-z+y")
    shelves = 5
    for i in range(shelves):
        y = 0.08 + (H - 0.12) * i / (shelves - 1)
        box(m, (-hx, y, -hz), (hx, y + 0.03, hz), metal, "+x-x+y-y+z-z")
        if i == shelves - 1:
            continue
        x = -hx + 0.06
        gap = (H - 0.12) / (shelves - 1) - 0.06
        while x < hx - 0.3:
            bw = 0.3 + 0.25 * rng.random()
            if x + bw > hx - 0.05:
                break
            bh = gap * (0.55 + 0.4 * rng.random())
            bd = W * (0.6 + 0.3 * rng.random())
            cbox(m, (x, y + 0.03, -hz + 0.04), (x + bw, y + 0.03 + bh, -hz + 0.04 + bd), box_role, c=0.006)
            x += bw + 0.04 + 0.1 * rng.random()


def build_shelving_pots(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, pot, plant = R[0], R[1], R[2]
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * (hx - 0.03), sz * (hz - 0.03)
            box(m, (x - 0.025, 0, z - 0.025), (x + 0.025, H - 0.3 if sz > 0 else H, z + 0.025), wood, "+x-x+z-z+y")
    tiers = 3
    for i in range(tiers):
        y = 0.3 + (H - 0.55) * i / (tiers - 1)
        for k in range(2):
            z0 = -hz + W * k / 2
            box(m, (-hx, y - 0.025, z0 + 0.008), (hx, y, z0 + W / 2 - 0.008), wood, "+x-x+y-y+z-z")
        for k in range(4):
            x = -hx + 0.25 + (L - 0.5) * k / 3 + 0.05 * (rng.random() - 0.5)
            ph = 0.12
            cyl(m, "y", (x, 0.0), 0.07, y, y + ph, pot, 5, r1=0.09, caps=(False, True), cap_role=plant)
            blob(m, (x, y + ph + 0.06, 0.0), 0.09, 0.08, 0.09, plant, 5, 3)


def build_shoe_rack(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, shoe = R[0], R[1]
    for sx in (-1, 1):
        cbox(m, (sx * hx - (0.02 if sx > 0 else 0), 0, -hz), (sx * hx + (0 if sx > 0 else 0.02), H, hz), wood)
    cbox(m, (-hx + 0.02, H - 0.02, -hz), (hx - 0.02, H, hz), wood)
    for y0, y1 in ((0.04, 0.1), (0.24, 0.3)):
        for k in range(3):
            z = -hz + 0.04 + (W - 0.08) * k / 2
            yy = y1 - (y1 - y0) * k / 2
            bar(m, (-hx + 0.02, yy, z), (hx - 0.02, yy, z), 0.015, wood)
    for i, y in enumerate((0.07, 0.27)):
        for k in range(3):
            x = -hx + 0.08 + 0.23 * k
            for dx in (0.0, 0.1):
                bar(m, (x + dx, y + 0.06, -hz + 0.05), (x + dx, y + 0.03, hz - 0.03), 0.08, shoe, 0.07)


def build_standing_mirror(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, glass = R[0], R[1]
    for x in (-hx + 0.03, hx - 0.03):
        bar(m, (x, 0.02, 0), (x, H - 0.06, 0), 0.04, wood)
        bar(m, (x, 0.02, -hz), (x, 0.02, hz), 0.05, wood, 0.04)
        blob(m, (x, H - 0.04, 0), 0.03, 0.04, 0.03, wood, 6, 3)
    bar(m, (-hx + 0.05, 0.25, 0), (hx - 0.05, 0.25, 0), 0.03, wood)
    tilt = math.radians(6)
    y0, y1 = 0.35, H - 0.1
    fx = hx - 0.07
    zc = lambda y: -(y - (y0 + y1) / 2) * math.tan(tilt)  # noqa: E731
    for a, b in (((-fx, y0), (fx, y0)), ((fx, y0), (fx, y1)), ((fx, y1), (-fx, y1)), ((-fx, y1), (-fx, y0))):
        bar(m, (a[0], a[1], zc(a[1])), (b[0], b[1], zc(b[1])), 0.05, wood, 0.035)
    bar(m, (0, y0, zc(y0) - 0.012), (0, y1, zc(y1) - 0.012), 2 * fx - 0.04, wood, 0.01, ref=(0, 0, 1))
    bar(m, (0, y0, zc(y0) + 0.0), (0, y1, zc(y1) + 0.0), 2 * fx - 0.04, glass, 0.008, ref=(0, 0, 1))


def build_stepping_stones(m, s, R, prm, rng):
    L, W, H = s
    n = 4
    for i in range(n):
        cx = -L / 2 + L * (i + 0.5) / n
        slab_xz(m, lump(cx, 0.04 * (rng.random() - 0.5), L / n / 2 * 0.9, W / 2 * 0.95, 8, rng, 0.08), 0, H * (0.7 + 0.3 * rng.random()), R[0])


def build_streetlight(m, s, R, prm, rng):
    L, W, H = s
    metal, lamp = R[0], R[1]
    cyl(m, "y", (0, 0), 0.17, 0, 0.5, metal, 8, r1=0.1)
    cyl(m, "y", (0, 0), 0.075, 0.5, H - 0.55, metal, 8, r1=0.05)
    tube(m, "y", (0, 0), 0.05, 0.09, H - 0.6, H - 0.55, metal, 8)
    cyl(m, "y", (0, 0), 0.05, H - 0.55, H - 0.45, metal, 8, r1=0.09)
    blob(m, (0, H - 0.3, 0), 0.15, 0.15, 0.15, lamp, 10, 5)
    cyl(m, "y", (0, 0), L / 2, H - 0.2, H - 0.12, metal, 10, r1=L / 2)
    cyl(m, "y", (0, 0), L / 2, H - 0.12, H - 0.02, metal, 10, r1=0.05)
    cyl(m, "y", (0, 0), 0.02, H - 0.02, H, metal, 4)


def build_string_lights(m, s, R, prm, rng):
    L, W, H = s
    lamp, wire = R[0], R[1]
    seg = 12
    sag = H * 0.55
    pts = [(-L / 2 + L * i / seg, H - sag * (1 - (2 * i / seg - 1) ** 2), 0.0) for i in range(seg + 1)]
    for a, b in zip(pts, pts[1:]):
        bar(m, a, b, 0.006, wire, caps=False)
    for i in range(1, seg):
        x, y, z = pts[i]
        bulb(m, (x, y - 0.025, z), W / 2 * 0.8, lamp, 0.02)


def build_tank_roof(m, s, R, prm, rng):
    L, W, H = s
    grey, dark = R[0], R[1]
    r = L / 2 - 0.03
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * r * 0.7, sz * r * 0.7
            bar(m, (x, 0, z), (x, 0.6, z), 0.06, dark)
    for a, b in (((-r * 0.7, -r * 0.7), (r * 0.7, -r * 0.7)), ((r * 0.7, r * 0.7), (-r * 0.7, r * 0.7)),
                 ((r * 0.7, -r * 0.7), (r * 0.7, r * 0.7)), ((-r * 0.7, r * 0.7), (-r * 0.7, -r * 0.7))):
        bar(m, (a[0], 0.58, a[1]), (b[0], 0.58, b[1]), 0.05, dark)
        bar(m, (a[0], 0.05, a[1]), (b[0], 0.55, b[1]), 0.03, dark)
    cyl(m, "y", (0, 0), r, 0.6, H - 0.18, grey, 12)
    for y in (0.85, 1.3):
        tube(m, "y", (0, 0), r, L / 2, y, y + 0.04, dark, 12)
    cyl(m, "y", (0, 0), r, H - 0.18, H - 0.03, grey, 12, r1=0.12, caps=(False, False))
    cyl(m, "y", (0, 0), 0.12, H - 0.03, H, dark, 8)


def build_tank_upright(m, s, R, prm, rng):
    L, W, H = s
    grey, dark = R[0], R[1]
    r = L / 2 - 0.08
    cyl(m, "y", (0, 0), r - 0.05, 0, 0.1, dark, 12)
    cyl(m, "y", (0, 0), r, 0.1, H - 0.25, grey, 12)
    cyl(m, "y", (0, 0), r, H - 0.25, H - 0.08, grey, 12, r1=0.25, caps=(False, False))
    cyl(m, "y", (0, 0), 0.08, H - 0.08, H, dark, 8)
    for y in (0.5, 1.2):
        tube(m, "y", (0, 0), r, r + 0.02, y, y + 0.05, dark, 12)
    for y in (0.4, 1.4):
        rod(m, (r - 0.02, y, 0), (L / 2, y, 0), 0.04, dark, 6)
    cyl(m, "z", (0, 0.9), 0.06, r - 0.05, W / 2, dark, 8)


def build_toolbox_cart(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    red, dark = R[0], R[1]
    bx = hx - 0.05
    cbox(m, (-bx, 0.1, -hz), (bx, H - 0.04, hz - 0.015), red)
    cbox(m, (-bx, H - 0.04, -hz), (bx, H, hz), dark)
    n = 5
    for i in range(n):
        y0 = 0.12 + (H - 0.18) * i / n
        y1 = 0.12 + (H - 0.18) * (i + 1) / n
        box(m, (-bx + 0.02, y0 + 0.006, hz - 0.015), (bx - 0.02, y1 - 0.006, hz), red)
        box(m, (-bx + 0.06, y1 - 0.04, hz), (bx - 0.06, y1 - 0.025, hz + 0.015), dark, "+y-y+z+x-x")
    for sx in (-1, 1):
        for sz in (-1, 1):
            cyl(m, "x", (0.05, sz * (hz - 0.07)), 0.05, sx * (bx - 0.07) - 0.02, sx * (bx - 0.07) + 0.02, dark, 8)
    rod(m, (bx, 0.75, -0.12), (hx, 0.75, -0.12), 0.012, dark, 6)
    rod(m, (bx, 0.75, 0.12), (hx, 0.75, 0.12), 0.012, dark, 6)
    rod(m, (hx, 0.75, -0.13), (hx, 0.75, 0.13), 0.014, dark, 6)


def build_towel_rack(m, s, R, prm, rng):
    L, W, H = s
    metal, towel = R[0], R[1]
    hx = L / 2
    zc = 0.0
    for x in (-hx + 0.02, hx - 0.02):
        rod(m, (x, 0.02, zc), (x, H - 0.02, zc), 0.015, metal, 6)
        for y in (0.15, H - 0.15):
            rod(m, (x, y, -W / 2), (x, y, zc), 0.01, metal, 4)
    for k in range(4):
        y = 0.25 + (H - 0.4) * k / 3
        rod(m, (-hx + 0.02, y, zc), (hx - 0.02, y, zc), 0.01, metal, 6, caps=False)
    y = 0.25 + (H - 0.4) * 2 / 3
    box(m, (-hx + 0.08, y - 0.4, zc + 0.012), (hx - 0.12, y + 0.015, zc + 0.022), towel)
    box(m, (-hx + 0.08, y - 0.3, zc - 0.022), (hx - 0.12, y + 0.015, zc - 0.012), towel)
    box(m, (-hx + 0.08, y + 0.012, zc - 0.022), (hx - 0.12, y + 0.022, zc + 0.022), towel, "+y")


def build_tray_table(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    top, tray, dark = R[0], R[1], R[2]
    t = H - 0.05
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * (hx - 0.05), sz * (hz - 0.05)
            box(m, (x - 0.025, 0, z - 0.025), (x + 0.025, t - 0.03, z + 0.025), dark, "+x-x+z-z")
    loft(m, (-hx, hx, -hz, hz, t - 0.03), (-hx, hx, -hz, hz, t + 0.01), top, inner=0.02)
    box(m, (-hx + 0.06, 0.15, -hz + 0.06), (hx - 0.06, 0.17, hz - 0.06), top)
    for k in range(3):
        x0 = -hx + 0.1 + (L - 0.2) * k / 3
        x1 = x0 + (L - 0.2) / 3 - 0.06
        loft(m, (x0, x1, -0.2, 0.2, t - 0.01), (x0 - 0.01, x1 + 0.01, -0.21, 0.21, H), tray, inner=0.008)


def build_trunk(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, metal, wood = R[0], R[1], R[2]
    bh = H * 0.72
    cbox(m, (-hx + 0.01, 0, -hz + 0.01), (hx - 0.01, bh, hz - 0.01), body)
    cbox(m, (-hx + 0.01, bh, -hz + 0.01), (hx - 0.01, H - 0.01, hz - 0.01), body, c=0.03)
    for x in (-hx * 0.55, hx * 0.55):
        box(m, (x - 0.025, 0, -hz), (x + 0.025, H, hz), metal, "+x-x+y+z-z")
    for y in (0.06, bh - 0.06):
        box(m, (-hx + 0.01, y - 0.025, hz - 0.01), (hx - 0.01, y + 0.025, hz + 0.004), wood, "+y-y+z")
    box(m, (-0.04, bh - 0.08, hz - 0.01), (0.04, bh + 0.02, hz + 0.008), metal, "+x-x+y-y+z")
    for sx in (-1, 1):
        box(m, (sx * hx - (0.01 if sx > 0 else 0), bh - 0.12, -0.08), (sx * hx + (0 if sx > 0 else 0.01), bh - 0.08, 0.08), metal)


def build_toy_chest(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, lid, stripe = R[0], R[1], R[2]
    bh = H - 0.1
    cbox(m, (-hx + 0.02, 0, -hz + 0.02), (hx - 0.02, bh, hz - 0.02), wood)
    cbox(m, (-hx, bh, -hz), (hx, bh + 0.05, hz), lid, c=0.01)
    for y in (0.1, bh - 0.1):
        box(m, (-hx + 0.02, y - 0.02, hz - 0.02), (hx - 0.02, y + 0.02, hz - 0.012), stripe, "+y-y+z")
    cbox(m, (-0.25, bh + 0.05, -0.1), (-0.17, bh + 0.1, -0.02), stripe, c=0.006)
    cbox(m, (0.1, bh + 0.05, 0.0), (0.16, bh + 0.1, 0.06), lid, c=0.006)


def build_tripod_camera(m, s, R, prm, rng):
    L, W, H = s
    dark, grey = R[0], R[1]
    top = H - 0.24
    for k in range(3):
        a = math.pi / 2 + 2 * math.pi * k / 3
        bar(m, (0, top, 0), (L / 2 / math.cos(math.pi / 6) * 0.97 * math.cos(a), 0, W / 1.5 * 0.97 * math.sin(a)), 0.022, dark)
    cyl(m, "y", (0, 0), 0.02, top - 0.25, top + 0.05, grey, 6)
    cbox(m, (-0.04, top + 0.05, -0.04), (0.04, top + 0.08, 0.04), dark)
    cbox(m, (-0.09, top + 0.08, -0.06), (0.09, top + 0.2, 0.05), dark)
    cyl(m, "z", (0.0, top + 0.14), 0.045, 0.05, 0.16, grey, 8)
    cbox(m, (-0.03, top + 0.2, -0.04), (0.03, H, 0.02), dark)


def build_tyre_stack(m, s, R, prm, rng):
    L, W, H = s
    n = 4
    h = H / n
    for i in range(n):
        dx, dz = 0.02 * (rng.random() - 0.5), 0.02 * (rng.random() - 0.5)
        y0, y1, ro, ri = h * i, h * (i + 1) - 0.004, L / 2 - 0.012, L / 2 * 0.52
        tube(m, "y", (dx, dz), ri, ro * 0.9, y0, y1, R[0], 12)
        cyl(m, "y", (dx, dz), ro * 0.9, y0, (y0 + y1) / 2, R[0], 12, r1=ro, caps=(False, False))
        cyl(m, "y", (dx, dz), ro, (y0 + y1) / 2, y1, R[0], 12, r1=ro * 0.9, caps=(False, False))


def build_utility_pole(m, s, R, prm, rng):
    L, W, H = s
    wood, metal = R[0], R[1]
    cyl(m, "y", (0, 0), L / 2 * 0.98, 0, H - 0.05, wood, 8, r1=L / 2 * 0.6, phase=0.0)
    cyl(m, "y", (0, 0), L / 2 * 0.65, H - 0.05, H, metal, 8, r1=L / 2 * 0.3)
    for k in range(12):
        y = 2.4 + 0.42 * k
        a = math.pi * (k % 2) + 0.3
        rr = L / 2 * (0.8 - 0.2 * y / H)
        rod(m, (rr * 0.5 * math.cos(a), y, rr * 0.5 * math.sin(a)), (L / 2 * math.cos(a), y, L / 2 * math.sin(a)), 0.012, metal, 4)
    for y in (H - 0.6, H - 1.2):
        tube(m, "y", (0, 0), L / 2 * 0.6, L / 2 * 0.68, y, y + 0.05, metal, 8)
    for k in range(3):
        a = 2 * math.pi * k / 3
        cyl(m, "y", (L / 2 * 0.62 * math.cos(a), L / 2 * 0.62 * math.sin(a)), 0.025, H - 0.4, H - 0.25, metal, 6)


def build_washing_line(m, s, R, prm, rng):
    L, W, H = s
    hx = L / 2
    metal = R[0]
    cloths = R[1:] or R[:1]
    for x in (-hx + 0.03, hx - 0.03):
        rod(m, (x, 0, 0), (x, H, 0), 0.025, metal, 6)
        bar(m, (x, H - 0.05, -W / 2), (x, H - 0.05, W / 2), 0.02, metal)
    seg = 8
    sag = 0.08
    pts = [(-hx + 0.03 + (L - 0.06) * i / seg, H - 0.06 - sag * (1 - (2 * i / seg - 1) ** 2), 0.0) for i in range(seg + 1)]
    for a, b in zip(pts, pts[1:]):
        bar(m, a, b, 0.006, metal, caps=False)
    items = 5
    for k in range(items):
        t = (k + 0.7) / (items + 0.4)
        x = -hx + 0.3 + (L - 0.6) * t
        u = (x + hx - 0.03) / (L - 0.06) * 2 - 1
        y = H - 0.06 - sag * (1 - u * u)
        w = 0.35 + 0.2 * rng.random()
        h = 0.4 + 0.25 * rng.random()
        box(m, (x - w / 2, y - h, -0.006), (x + w / 2, y, 0.006), cloths[k % len(cloths)])


def build_wheelbarrow(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    tray, tyre, wood = R[0], R[1], R[2]
    loft(m, (-0.3, 0.2, -0.17, 0.17, 0.32), (-0.42, 0.42, -hz, hz, H), tray, inner=0.012)
    wr = 0.18
    wx = hx - wr
    tube(m, "z", (wx, wr), 0.07, wr, -0.045, 0.045, tyre, 10)
    rod(m, (wx, wr, -0.07), (wx, wr, 0.07), 0.015, tray, 6)
    for sz in (-1, 1):
        z = sz * 0.16
        bar(m, (wx, wr, z * 0.5), (-hx, 0.55, z * 1.3), 0.04, wood)
        bar(m, (-0.25, 0.4, z), (-0.3, 0.0, z * 1.1), 0.03, tray)


def build_wheelie_bin(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, dark, tyre = R[0], R[1], R[2]
    top = H - 0.08
    loft(m, (-hx + 0.06, hx - 0.06, -hz + 0.12, hz - 0.06, 0.04), (-hx + 0.02, hx - 0.02, -hz + 0.06, hz - 0.02, top),
         body, top=True)
    cbox(m, (-hx, top, -hz + 0.04), (hx, top + 0.04, hz), body, c=0.008)
    bar(m, (-hx + 0.08, H - 0.02, -hz + 0.02), (hx - 0.08, H - 0.02, -hz + 0.02), 0.03, dark)
    for sx in (-1, 1):
        bar(m, (sx * (hx - 0.1), top, -hz + 0.07), (sx * (hx - 0.1), H - 0.02, -hz + 0.02), 0.03, dark)
        cyl(m, "x", (0.1, -hz + 0.1), 0.1, sx * hx - 0.05 * sx - 0.03, sx * hx - 0.05 * sx + 0.03, tyre, 10)
    rod(m, (-hx + 0.05, 0.1, -hz + 0.1), (hx - 0.05, 0.1, -hz + 0.1), 0.015, dark, 6)
    box(m, (-0.1, top - 0.05, hz - 0.02), (0.1, top, hz + 0.0), dark, "+z+y-y+x-x")


def build_window_box(m, s, R, prm, rng):
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, soil, plant, flower = R[0], R[1], R[2], R[3]
    bh = H * 0.7
    loft(m, (-hx + 0.02, hx - 0.02, -hz + 0.02, hz - 0.02, 0.0), (-hx, hx, -hz, hz, bh), wood, inner=0.02)
    box(m, (-hx + 0.02, bh - 0.04, -hz + 0.02), (hx - 0.02, bh - 0.03, hz - 0.02), soil, "+y")
    for k in range(5):
        x = -hx + 0.12 + (L - 0.24) * k / 4
        blob(m, (x, bh - 0.02 + 0.04, 0.0), 0.09, 0.05, hz * 0.7, plant, 6, 3)
        bulb(m, (x + 0.03, bh + 0.06, 0.03), 0.03, flower, 0.025)


# --- small clutter (art #104: the lived-in layer; boxes and cylinders, class `clutter`) ---------------------------
def build_book_stack(m, s, R, prm, rng):
    """Books lying in a stack, each a little smaller and turned off the last."""
    L, W, H = s
    n = int(prm.get("books", 3))
    y = 0.0
    for i in range(n):
        t = H / n
        sx, sz = L * (1 - 0.08 * i) / 2, W * (1 - 0.06 * i) / 2
        dx = (rng.random() - 0.5) * 0.02
        cbox(m, (-sx + dx, y, -sz), (sx + dx, y + t - 0.002, sz), _r(R, i % len(R)), c=0.003)
        y += t


def build_book_row(m, s, R, prm, rng):
    """Books standing in a row on a shelf (spines to the front), heights and widths varied."""
    L, W, H = s
    x = -L / 2
    i = 0
    while x < L / 2 - 0.02:
        t = min(0.025 + rng.random() * 0.03, L / 2 - x)
        h = H * (0.72 + rng.random() * 0.28)
        box(m, (x, 0, -W / 2), (x + t - 0.002, h, W / 2 - rng.random() * 0.03), _r(R, i % len(R)), "+x-x+y+z")
        x += t
        i += 1


def build_wall_shelf(m, s, R, prm, rng):
    """A plank on two brackets with a row of books and a jar on it (wall pivot: the back at -z)."""
    L, W, H = s
    hz = W / 2
    wood = R[0]
    box(m, (-L / 2, 0.06, -hz), (L / 2, 0.085, hz), wood)
    for sx in (-1, 1):
        x = sx * L * 0.36
        box(m, (x - 0.012, 0.0, -hz), (x + 0.012, 0.06, -hz + W * 0.75), _r(R, -1))
    x = -L / 2 + 0.06
    i = 0
    while x < L * 0.18:
        t = 0.03 + rng.random() * 0.02
        box(m, (x, 0.085, -hz + 0.02), (x + t - 0.003, 0.085 + (H - 0.085) * (0.7 + rng.random() * 0.3), hz - 0.03),
            _r(R, 1 + i % max(1, len(R) - 2)), "+x-x+y+z")
        x += t
        i += 1
    cyl(m, "y", (L * 0.32, 0.0), min(0.05, W * 0.3), 0.085, 0.085 + (H - 0.085) * 0.6, _r(R, 2), 8)


def build_cup_set(m, s, R, prm, rng):
    """Two cups (and their saucers) side by side."""
    L, W, H = s
    r = min(L / 4, W / 2) * 0.62
    for sx in (-1, 1):
        x = sx * L / 4
        cyl(m, "y", (x, 0.0), r * 1.45, 0.0, 0.01, R[0], 10)
        cyl(m, "y", (x, 0.0), r, 0.01, H, R[0], 10, r1=r * 1.1, caps=(True, False))
        cyl(m, "y", (x, 0.0), r * 0.92, H - 0.012, H - 0.004, _r(R, 1), 10, caps=(False, True))


def build_plate_stack(m, s, R, prm, rng):
    L, W, H = s
    n = int(prm.get("plates", 4))
    r = min(L, W) / 2
    for i in range(n):
        y0 = H * i / n
        cyl(m, "y", (0.0, 0.0), r * 0.7, y0, y0 + H / n * 0.4, R[0], 12, r1=r, caps=(True, False))
        cyl(m, "y", (0.0, 0.0), r, y0 + H / n * 0.4, y0 + H / n * 0.9, R[0], 12, caps=(False, True))


def build_bottles(m, s, R, prm, rng):
    """Three bottles of different heights in a row."""
    L, W, H = s
    n = int(prm.get("bottles", 3))
    r = min(L / n, W) / 2 * 0.85
    for i in range(n):
        x = -L / 2 + L * (i + 0.5) / n
        h = H * (0.8 + 0.2 * ((i * 7) % n) / max(1, n - 1)) if n > 1 else H
        role = _r(R, i % len(R))
        cyl(m, "y", (x, 0.0), r, 0.0, h * 0.62, role, 8)
        cyl(m, "y", (x, 0.0), r, h * 0.62, h * 0.78, role, 8, r1=r * 0.38, caps=(False, False))
        cyl(m, "y", (x, 0.0), r * 0.38, h * 0.78, h, role, 6, caps=(False, True))


def build_cooking_pot(m, s, R, prm, rng):
    L, W, H = s
    r = min(L * 0.8, W) / 2
    metal = R[0]
    cyl(m, "y", (0.0, 0.0), r, 0.0, H * 0.78, metal, 12, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), r * 1.02, H * 0.78, H * 0.84, metal, 12, r1=r * 0.6, caps=(False, False))
    cyl(m, "y", (0.0, 0.0), r * 0.6, H * 0.84, H * 0.86, metal, 12, caps=(False, True))
    cyl(m, "y", (0.0, 0.0), 0.02, H * 0.86, H, _r(R, 1), 6)
    for sx in (-1, 1):
        box(m, (sx * r - (0.0 if sx > 0 else L / 2 - r), H * 0.6, -0.02), (sx * r + (L / 2 - r if sx > 0 else 0.0), H * 0.68, 0.02), _r(R, 1))


def build_paper_stack(m, s, R, prm, rng):
    L, W, H = s
    n = int(prm.get("sheets", 3))
    for i in range(n):
        y0 = H * i / n
        dx, dz = (rng.random() - 0.5) * 0.03, (rng.random() - 0.5) * 0.03
        box(m, (-L / 2 * 0.94 + dx, y0, -W / 2 * 0.94 + dz), (L / 2 * 0.94 + dx, y0 + H / n, W / 2 * 0.94 + dz), _r(R, i % len(R)))


def build_wall_clock(m, s, R, prm, rng):
    """A round clock: rim, face, two hands (wall pivot: the back at -z)."""
    L, W, H = s
    r = min(L, H) / 2
    zb, zf = -W / 2, W / 2
    tube(m, "z", (0.0, r), r * 0.86, r, zb, zf, R[0], 16)
    cyl(m, "z", (0.0, r), r * 0.86, zb, zf - 0.012, _r(R, 1), 16, caps=(True, True))
    box(m, (-0.008, r, zf - 0.012), (0.008, r + r * 0.6, zf - 0.006), _r(R, 2), "+z+x-x+y")
    box(m, (0.0, r - 0.008, zf - 0.012), (r * 0.45, r + 0.008, zf - 0.006), _r(R, 2), "+z+y-y+x")


def build_basket(m, s, R, prm, rng):
    """A woven basket: a flared shell, its rim and two handles."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    cyl(m, "y", (0.0, 0.0), hx * 0.85, 0.0, H * 0.92, R[0], 10, r1=hx, sq=hz / hx, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), hx * 0.82, 0.02, H * 0.92, R[0], 10, r1=hx * 0.96, sq=hz / hx, caps=(True, False), flip=True)
    cyl(m, "y", (0.0, 0.0), hx, H * 0.92, H, _r(R, 1), 10, sq=hz / hx, caps=(False, False))
    cyl(m, "y", (0.0, 0.0), hx * 0.94, H * 0.92, H, _r(R, 1), 10, sq=hz / hx, caps=(False, False), flip=True)
    for sx in (-1, 1):
        box(m, (sx * hx * 0.98 - 0.015, H * 0.7, -0.05), (sx * hx * 0.98 + 0.015, H * 0.84, 0.05), _r(R, 1))


def build_shoes(m, s, R, prm, rng):
    """A pair of shoes: sole, upper and the heel's block each."""
    L, W, H = s
    for sx in (-1, 1):
        x = sx * L / 4
        sw = L / 2 * 0.96
        box(m, (x - sw / 2, 0.0, -W / 2), (x + sw / 2, 0.02, W / 2), _r(R, 1))
        cbox(m, (x - sw / 2 * 0.9, 0.02, -W / 2 * 0.95), (x + sw / 2 * 0.9, H * 0.55, W / 2 * 0.6), R[0], c=0.006)
        cbox(m, (x - sw / 2 * 0.9, 0.02, -W / 2 * 0.95), (x + sw / 2 * 0.9, H, -W / 2 * 0.3), R[0], c=0.006)


def build_toy_blocks(m, s, R, prm, rng):
    """A few coloured blocks, two of them stacked."""
    L, W, H = s
    a = min(H / 2, L / 3, W / 2)
    spots = [(-L / 2 + a / 2, -W / 4, 0.0), (-L / 2 + a / 2, -W / 4, a), (0.05, W / 4 - a / 2, 0.0),
             (L / 2 - a / 2, -W / 2 + a / 2, 0.0), (L / 2 - a * 0.7, W / 2 - a / 2, 0.0)]
    for i, (x, z, y) in enumerate(spots):
        cbox(m, (x - a / 2, y, z - a / 2), (x + a / 2, y + a - 0.003, z + a / 2), _r(R, i % len(R)), c=0.004)


def build_vase_flowers(m, s, R, prm, rng):
    L, W, H = s
    r = min(L, W) / 2
    cyl(m, "y", (0.0, 0.0), r * 0.6, 0.0, H * 0.45, R[0], 8, r1=r * 0.42, caps=(True, False))
    for i in range(3):
        a = 2 * math.pi * i / 3
        x, z = math.cos(a) * r * 0.62, math.sin(a) * r * 0.62
        rod(m, (0.0, H * 0.4, 0.0), (x, H * 0.82, z), 0.006, _r(R, 1), 4)
        blob(m, (x, H * 0.88, z), r * 0.38, H * 0.1, r * 0.38, _r(R, 2), 6, 3)


def build_fruit_bowl(m, s, R, prm, rng):
    L, W, H = s
    r = min(L, W) / 2
    cyl(m, "y", (0.0, 0.0), r * 0.45, 0.0, H * 0.5, R[0], 12, r1=r, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), r * 0.4, 0.01, H * 0.5, R[0], 12, r1=r * 0.94, caps=(False, False), flip=True)
    for i in range(4):
        a = 2 * math.pi * i / 4 + 0.4
        blob(m, (math.cos(a) * r * 0.42, H * 0.62, math.sin(a) * r * 0.42), r * 0.26, H * 0.36, r * 0.26,
             _r(R, 1 + i % max(1, len(R) - 1)), 6, 3)


def build_laundry_basket(m, s, R, prm, rng):
    """A wicker basket heaped with clothes: the tapered body, its rim and three folds of laundry over the top."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, cloth = R[0], _r(R, 1)
    hb = H * 0.72
    cyl(m, "y", (0.0, 0.0), hx * 0.88, 0.0, hb, body, 10, r1=hx, sq=hz / hx, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), hx * 0.97, hb - 0.03, hb, body, 10, sq=hz / hx, caps=(False, True))
    blob(m, (-0.06, hb, 0.02), hx * 0.62, H - hb, hz * 0.7, cloth, 8, 4, ry_bottom=0.04)
    blob(m, (0.1, hb + 0.01, -0.04), hx * 0.45, (H - hb) * 0.75, hz * 0.6, _r(R, 2), 8, 4, ry_bottom=0.04)
    bar(m, (hx * 0.55, hb + 0.02, hz * 0.3), (hx * 0.9, hb * 0.55, hz * 0.55), 0.08, cloth, 0.03)


def build_laundry_pile(m, s, R, prm, rng):
    """A heap of clothes on the floor: four flattened lumps in two fabrics, one shirt sleeve trailing."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    blob(m, (-hx * 0.3, 0.0, 0.0), hx * 0.62, H, hz * 0.85, R[0], 10, 4, floor=0.0)
    blob(m, (hx * 0.35, 0.0, -hz * 0.2), hx * 0.55, H * 0.7, hz * 0.7, _r(R, 1), 8, 4, floor=0.0)
    blob(m, (hx * 0.1, H * 0.45, hz * 0.25), hx * 0.4, H * 0.5, hz * 0.45, _r(R, 2), 8, 4, floor=H * 0.45)
    bar(m, (hx * 0.45, 0.02, hz * 0.35), (hx * 0.95, 0.02, hz * 0.85), 0.12, _r(R, 1), 0.04)


def build_drying_rack(m, s, R, prm, rng):
    """A folding clothes airer: two A-frames of tube, eight rails, and towels and shirts hung over them."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    metal = R[0]
    for x in (-hx + 0.02, hx - 0.02):
        for z in (-hz + 0.02, hz - 0.02):
            rod(m, (x, 0.0, z), (x, H - 0.02, 0.0), 0.012, metal, 5)
        rod(m, (x, H * 0.35, -hz * 0.62), (x, H * 0.35, hz * 0.62), 0.008, metal, 4)
    rod(m, (-hx + 0.02, H - 0.02, 0.0), (hx - 0.02, H - 0.02, 0.0), 0.012, metal, 5)
    rails = []
    for f in (0.35, 0.62, 0.85):
        for sz in (-1, 1):
            z = sz * (hz - 0.02) * (1 - f)
            rails.append((H * f, z))
            rod(m, (-hx + 0.02, H * f, z), (hx - 0.02, H * f, z), 0.006, metal, 4, caps=False)
    hang = ((-hx * 0.55, 0.42, H * 0.85, -1, _r(R, 1)), (hx * 0.15, 0.5, H * 0.62, 1, _r(R, 2)),
            (hx * 0.62, 0.3, H * 0.85, 1, _r(R, 3)), (-hx * 0.15, 0.36, H * 0.62, -1, _r(R, 2)))
    for x, w, y, sz, role in hang:
        z = sz * (hz - 0.02) * (1 - y / H)
        drop = min(0.45, y - 0.1)
        box(m, (x - w / 2, y - drop, z - 0.012), (x + w / 2, y + 0.01, z + 0.012), role)


def build_open_box(m, s, R, prm, rng):
    """A half-packed cardboard box: four flaps open and leaning out, books and a folded cloth inside."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    card = R[0]
    hb = H * 0.66
    t = 0.012
    box(m, (-hx, 0.0, -hz), (hx, t, hz), card, "-y+y")
    box(m, (-hx, 0.0, -hz), (hx, hb, -hz + t), card)
    box(m, (-hx, 0.0, hz - t), (hx, hb, hz), card)
    box(m, (-hx, 0.0, -hz + t), (-hx + t, hb, hz - t), card)
    box(m, (hx - t, 0.0, -hz + t), (hx, hb, hz - t), card)
    fl = H - hb
    for sz in (-1, 1):
        z0 = sz * hz
        box(m, (-hx + 0.01, hb, min(z0, z0 + sz * t)), (hx - 0.01, hb + fl * 0.8, max(z0, z0 + sz * t)), card)
    for sx in (-1, 1):
        x0 = sx * hx
        box(m, (min(x0, x0 + sx * t), hb, -hz + 0.01), (max(x0, x0 + sx * t), H, hz - 0.01), card)
    cbox(m, (-hx + 0.04, t, -hz + 0.04), (0.02, hb + 0.04, hz * 0.4), _r(R, 1), c=0.01)
    cbox(m, (0.04, t, -hz + 0.05), (hx - 0.04, hb * 0.82, hz - 0.05), _r(R, 2), c=0.01)


def build_boots(m, s, R, prm, rng):
    """A pair of tall boots: sole, foot and shaft each, the right one slumped against the left."""
    L, W, H = s
    sw = L / 2 * 0.9
    for i, sx in enumerate((-1, 1)):
        x = sx * L / 4
        box(m, (x - sw / 2, 0.0, -W / 2), (x + sw / 2, 0.025, W / 2), _r(R, 1))
        cbox(m, (x - sw / 2 * 0.92, 0.025, -W / 2 * 0.95), (x + sw / 2 * 0.92, 0.12, W / 2 * 0.9), R[0], c=0.01)
        top = H if i == 0 else H * 0.8
        cbox(m, (x - sw / 2 * 0.9, 0.08, -W / 2 * 0.95), (x + sw / 2 * 0.9, top, -W / 2 * 0.95 + sw * 0.95), R[0],
             c=0.01)


def build_toy_spill(m, s, R, prm, rng):
    """A kid's toys spilled on the floor: blocks, a ball, a toy truck and a picture book."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    a = 0.07
    spots = [(-hx + 0.08, -hz + 0.12, 0.0), (-hx + 0.08, -hz + 0.12, a), (-hx + 0.22, -hz + 0.1, 0.0),
             (0.05, hz - 0.1, 0.0), (hx - 0.3, -hz + 0.08, 0.0), (-0.1, -0.05, 0.0)]
    for i, (x, z, y) in enumerate(spots):
        box(m, (x - a / 2, y, z - a / 2), (x + a / 2, y + a - 0.003, z + a / 2), _r(R, i % len(R)))
    r = min(H / 2, 0.09)
    blob(m, (hx - r - 0.02, r, hz - r - 0.02), r, r, r, _r(R, 1), 8, 5)
    tx, tz = -hx + 0.3, hz - 0.15
    cbox(m, (tx - 0.12, 0.03, tz - 0.06), (tx + 0.12, 0.09, tz + 0.06), _r(R, 2), c=0.006)
    cbox(m, (tx + 0.04, 0.09, tz - 0.055), (tx + 0.12, 0.14, tz + 0.055), _r(R, 3), c=0.006)
    for wx in (tx - 0.08, tx + 0.08):
        cyl(m, "z", (wx, 0.03), 0.03, tz - 0.07, tz + 0.07, R[0], 6)
    box(m, (0.12, 0.0, -hz + 0.05), (0.36, 0.02, -hz + 0.23), _r(R, 3))


def build_radiator(m, s, R, prm, rng):
    """A painted column radiator on two wall brackets: columns, top and bottom headers, a valve (wall pivot)."""
    L, W, H = s
    hx = L / 2
    paint, metal = R[0], _r(R, 1)
    zb = -W / 2
    n = max(4, int(L / 0.09))
    pitch = (L - 0.04) / n
    for i in range(n):
        x = -hx + 0.02 + pitch * (i + 0.5)
        box(m, (x - pitch * 0.32, 0.04, zb + 0.02), (x + pitch * 0.32, H - 0.04, zb + W - 0.005), paint)
    cbox(m, (-hx + 0.02, 0.0, zb + 0.03), (hx - 0.02, 0.05, zb + W - 0.015), paint, c=0.008)
    cbox(m, (-hx + 0.02, H - 0.05, zb + 0.03), (hx - 0.02, H, zb + W - 0.015), paint, c=0.008)
    for x in (-hx * 0.6, hx * 0.6):
        box(m, (x - 0.02, H * 0.6, zb), (x + 0.02, H * 0.66, zb + 0.03), metal)
    cyl(m, "x", (0.03, zb + W * 0.55), 0.018, -hx, -hx + 0.02, metal, 6)


# --- the world look: the style and the shared builders (docs/decisions/2026-10-13-house-world-look.md) --------------
# Ported from the kitchen pilot's round 2 (the lab's kp_r2_build.py, direction C2-white). Every hard-surface prop of
# a room is made of these parts with one Style, so a room has one handle, one plinth and one worktop line. Paints are
# the fine pack's roles (props/library.toml [roles], `material = "fine"`), named here by what they are.
@dataclass(frozen=True)
class Style:
    """props/library.toml [style] in metres: bevels, round segments, the bar handle, fronts, plinth, worktop."""
    bevel: float = 0.010
    bevel_small: float = 0.003
    segments: int = 16
    handle_r: float = 0.007
    standoff: float = 0.03
    gap: float = 0.003
    front_t: float = 0.019
    plinth: float = 0.1
    plinth_setback: float = 0.075
    worktop: float = 0.9
    worktop_t: float = 0.03

    @classmethod
    def from_lib(cls, lib: dict) -> "Style":
        s = lib.get("style", {})
        return cls(**{f: s[k] for k, f in STYLE_KEYS.items() if k in s})

    @property
    def reach(self) -> float:
        """How far a front with its bar handle stands out of the body it hangs on."""
        return self.front_t + self.standoff + self.handle_r


STYLE_KEYS = {"bevel_m": "bevel", "bevel_small_m": "bevel_small", "segments": "segments",
              "handle_radius_m": "handle_r", "handle_standoff_m": "standoff", "front_gap_m": "gap",
              "front_thickness_m": "front_t", "plinth_m": "plinth", "plinth_setback_m": "plinth_setback",
              "worktop_m": "worktop", "worktop_thickness_m": "worktop_t"}


def _style(prm: dict) -> Style:
    return prm.get("style") or Style()


def front_frame(x0: float, x1: float, y0: float, y1: float, gap: float, rail: float = 0.06) -> tuple[list, tuple]:
    """A framed (shaker) front inside its seam gap: the four rails as ((x, y), (x, y)) rectangles (bottom, top, left,
    right) and the centre panel's rectangle. The rail narrows on a small front (18 % of the width, 25 % of the
    height)."""
    f = min(rail, (x1 - x0) * 0.18, (y1 - y0) * 0.25)
    rails = [((x0 + gap, y0 + gap), (x1 - gap, y0 + f)), ((x0 + gap, y1 - f), (x1 - gap, y1 - gap)),
             ((x0 + gap, y0 + f), (x0 + f, y1 - f)), ((x1 - f, y0 + f), (x1 - gap, y1 - f))]
    return rails, ((x0 + f, y0 + f), (x1 - f, y1 - f))


def handle_span(x0: float, x1: float, y0: float, y1: float, hinge_left: bool, handle: str, low: bool = False,
                inset: float = 0.04, length: float = 0.16) -> tuple[tuple, tuple]:
    """The bar handle's two ends (x, y) on a front: `v` upright on the side away from the hinge, near the top (`low`:
    near the bottom, a wall cabinet's door); `h` level across the middle of a drawer."""
    if handle == "v":
        hx = x1 - inset if hinge_left else x0 + inset
        ya, yb = (y0 + 0.06, y0 + 0.06 + length) if low else (y1 - 0.06 - length, y1 - 0.06)
        return (hx, ya), (hx, yb)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = min(length, (x1 - x0) * 0.4)
    return (cx - w, cy), (cx + w, cy)


def grate_bars(xc: float, zc: float, hw: float, hd: float, cross: int = 3) -> list[tuple]:
    """A burner grate's bars as ((x, z), (x, z), width): the frame, `cross` cross bars evenly between its ends and
    a spine along z."""
    x0, x1, z0, z1 = xc - hw, xc + hw, zc - hd, zc + hd
    bars = [((x0, z0), (x1, z0), 0.012), ((x0, z1), (x1, z1), 0.012), ((x0, z0), (x0, z1), 0.012),
            ((x1, z0), (x1, z1), 0.012)]
    for k in range(cross):
        z = z0 + (z1 - z0) * (k + 1) / (cross + 1)
        bars.append(((x0, z), (x1, z), 0.01))
    bars.append(((xc, z0), (xc, z1), 0.01))
    return bars


def round_rect(x0: float, x1: float, z0: float, z1: float, r: float, n: int = 6, front_only: bool = False) -> list:
    """A rectangle in XZ with rounded corners (n segments a quarter; `front_only`: only the two at +z), as points in
    order round the outline: the plan of an appliance's body or a door with soft vertical edges."""
    pts = []
    for cx, cz, a0, rounded in ((x1 - r, z1 - r, 0.0, True), (x0 + r, z1 - r, 90.0, True),
                                (x0 + r, z0 + r, 180.0, not front_only), (x1 - r, z0 + r, 270.0, not front_only)):
        if not rounded:
            pts.append((x0 if a0 == 180.0 else x1, z0))
            continue
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((round(cx + r * math.cos(a), 6), round(cz + r * math.sin(a), 6)))
    return pts


def rslab(m: Mesh, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, r: float, role: str, n: int = 6,
          front_only: bool = False, bottom: bool = False) -> None:
    """An upright slab from y0 to y1 on a round_rect plan."""
    slab_xz(m, round_rect(x0, x1, z0, z1, r, n, front_only), y0, y1, role, bottom)


def bar_handle(m: Mesh, st: Style, p0, p1, z: float, role: str = "chrome", standoff: float | None = None) -> None:
    """The one handle: a round bar from p0 to p1 (x, y) on two standoffs out of the front plane z (facing +z). It
    reaches z + standoff + the bar's radius."""
    so = st.standoff if standoff is None else standoff
    zz = z + so - st.handle_r
    rod(m, (p0[0], p0[1], zz), (p1[0], p1[1], zz), st.handle_r, role, 8)
    for t in (0.08, 0.92):
        x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
        cyl(m, "z", (x, y), st.handle_r * 0.85, z, zz, role, 6, caps=(False, False))


def front(m: Mesh, st: Style, x0: float, x1: float, y0: float, y1: float, z: float, role: str, hinge_left: bool = True,
          handle: str | None = "v", low: bool = False, glass: str | None = None, line: str | None = None,
          hinge_role: str = "steel_black") -> float:
    """A door or drawer front on the plane z (its back), facing +z, inside a seam gap: a bevelled slab with a raised
    centre panel (`line`: a thin outline round the panel in that paint), or with `glass` a framed door with a pane in
    that paint. Its bar handle (`v`, `h` or None, see handle_span) and, on an upright handle's door, two hinge barrels.
    Returns the front's face plane (z + front_t)."""
    g, t = st.gap, st.front_t
    rails, (a, b) = front_frame(x0, x1, y0, y1, g)
    if glass:
        for lo, hi in rails:
            cbox(m, (lo[0], lo[1], z), (hi[0], hi[1], z + t), role, st.bevel_small)
        box(m, (a[0], a[1], z + 0.006), (b[0], b[1], z + 0.009), glass, "+z-z")
    else:
        cbox(m, (x0 + g, y0 + g, z), (x1 - g, y1 - g, z + t), role, st.bevel_small)
        box(m, (a[0], a[1], z + t), (b[0], b[1], z + t + 0.004), role, "+x-x+y-y+z")
        if line:
            box(m, (a[0] - 0.008, a[1] - 0.008, z + t), (b[0] + 0.008, b[1] + 0.008, z + t + 0.001), line, "+z")
    if handle:
        p0, p1 = handle_span(x0, x1, y0, y1, hinge_left, handle, low)
        bar_handle(m, st, p0, p1, z + t)
    if handle == "v":
        hx = x0 + g + 0.002 if hinge_left else x1 - g - 0.002
        for yy in (y0 + 0.07, y1 - 0.11):
            cyl(m, "y", (hx, z + 0.002), 0.005, yy, yy + 0.04, hinge_role, 6)
    return z + t


def plinth(m: Mesh, st: Style, x0: float, x1: float, z0: float, z1: float, role: str = "rubber_black") -> None:
    """The kick: one height (st.plinth) under every floor unit; its front z1 sits st.plinth_setback behind the fronts."""
    box(m, (x0, 0.0, z0), (x1, st.plinth, z1), role, "+x-x+z")


def worktop(m: Mesh, st: Style, x0: float, x1: float, z0: float, z1: float, role: str, y: float | None = None,
            t: float | None = None, upstand: float = 0.0) -> None:
    """A worktop slab from y - t to y (default the style's worktop line and thickness), bevelled, with an optional
    upstand along its back edge z0."""
    y = st.worktop if y is None else y
    t = st.worktop_t if t is None else t
    cbox(m, (x0, y - t, z0), (x1, y, z1), role, st.bevel_small)
    if upstand:
        box(m, (x0, y, z0), (x1, y + upstand, z0 + 0.012), role, "+x-x+y+z")


def backsplash(m: Mesh, st: Style, L: float, H: float, role: str = "tile_splash", cap: str = "steel_warm") -> None:
    """A wall strip behind a run (back at z = 0, bottom centre on the worktop): one tiled slab and a steel cap."""
    cbox(m, (-L / 2, 0.0, 0.0), (L / 2, H, 0.012), role, st.bevel_small)
    box(m, (-L / 2, H, 0.0), (L / 2, H + 0.008, 0.016), cap, "+x-x+y+z")


def burner(m: Mesh, st: Style, x: float, z: float, y: float, r: float, role: str = "steel_black",
           cap: str = "rubber_black") -> None:
    """A gas burner on a hob at height y: the spill ring, the crown and the cap."""
    n = st.segments
    cyl(m, "y", (x, z), r, y, y + 0.006, role, n, caps=(False, True))
    cyl(m, "y", (x, z), r * 0.55, y + 0.006, y + 0.018, role, n, caps=(False, True))
    cyl(m, "y", (x, z), r * 0.35, y + 0.018, y + 0.024, cap, 8, caps=(False, True))


def burner_grate(m: Mesh, xc: float, zc: float, hw: float, hd: float, y0: float, y1: float,
                 role: str = "steel_black", cross: int = 3) -> None:
    """A cast-iron pan grate over a pair of burners: bars at y1 (grate_bars) on four corner feet from y0."""
    for (a, b, w) in grate_bars(xc, zc, hw, hd, cross):
        bar(m, (a[0], y1, a[1]), (b[0], y1, b[1]), w, role)
    for x in (xc - hw, xc + hw):
        for z in (zc - hd, zc + hd):
            box(m, (x - 0.008, y0, z - 0.008), (x + 0.008, y1, z + 0.008), role, "+x-x+z-z")


def tap(m: Mesh, st: Style, x: float, z: float, y: float, role: str = "chrome",
        levers: tuple = ("paint_red", "paint_blue")) -> None:
    """A pillar tap on a deck at height y: the base, the column, a swan neck toward +z (0.15 m out, 0.315 m up) and
    two lever valves with a hot and a cold dot."""
    n = 10
    cyl(m, "y", (x, z), 0.024, y, y + 0.02, role, n)
    cyl(m, "y", (x, z), 0.014, y + 0.02, y + 0.24, role, n, caps=(False, False))
    prev = (x, y + 0.24, z)
    for i in range(1, 6):
        a = math.pi * i / 5
        p = (x, y + 0.24 + 0.075 * math.sin(a), z + 0.075 - 0.075 * math.cos(a))
        rod(m, prev, p, 0.011, role, n - 2)
        prev = p
    rod(m, prev, (prev[0], prev[1] - 0.04, prev[2]), 0.012, role, n - 2)
    for dx, dot in zip((-0.075, 0.075), levers):
        cyl(m, "y", (x + dx, z), 0.018, y, y + 0.045, role, n)
        bar(m, (x + dx, y + 0.05, z), (x + dx, y + 0.06, z + 0.07), 0.012, role, 0.008)
        cyl(m, "z", (x + dx, y + 0.052), 0.008, z - 0.004, z + 0.006, dot, 6)


def _boxes(prm: dict) -> list:
    """The builder's own collider boxes (build_proc reads them back; empty: one box round the prop)."""
    return prm.setdefault("_boxes", [])


def build_kitchen_counter(m, s, R, prm, rng):
    """A C2-white floor unit (per 1 m) or with `sink` the sink unit: plinth, carcass, stone worktop (the backsplash
    is the wall's, so no upstand) and a steel edge trim, a drawer over two doors (the sink unit: two doors, a steel bowl and drainer, a pillar tap).
    Fronts and handles end inside the worktop's edge, so the unit stays inside size_m."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    sink = bool(prm.get("sink"))
    tt = st.worktop_t
    zf = hz - st.reach - 0.002  # the fronts' back: the handles end 2 mm inside the worktop's edge
    plinth(m, st, -hx + 0.01, hx - 0.01, -hz + 0.02, zf + st.front_t - st.plinth_setback)
    sx0, sx1 = -0.08, hx - 0.07  # the sink's cut-out in the worktop
    z0, z1 = -hz + 0.1, hz - 0.08
    if sink:  # the carcass stops under the bowl; side panels close the ends up to the worktop
        cbox(m, (-hx + 0.008, st.plinth, -hz), (hx - 0.008, H - 0.19, zf), "wood_front", st.bevel)
        for xa, xb in ((-hx + 0.008, -hx + 0.026), (hx - 0.026, hx - 0.008)):
            cbox(m, (xa, H - 0.2, -hz), (xb, H - tt, zf), "wood_front", st.bevel_small)
        box(m, (-hx + 0.026, H - 0.2, -hz), (hx - 0.026, H - tt, -hz + 0.018), "wood_front", "+z")
        for a, b, c, d in ((-hx, sx0, -hz, hz), (sx1, hx, -hz, hz), (sx0, sx1, -hz, z0), (sx0, sx1, z1, hz)):
            worktop(m, st, a, b, c, d, "worktop_stone", y=H)
    else:
        cbox(m, (-hx + 0.008, st.plinth, -hz), (hx - 0.008, H - tt, zf), "wood_front", st.bevel)
        worktop(m, st, -hx, hx, -hz, hz, "worktop_stone", y=H)
    box(m, (-hx, H - tt - 0.004, hz - 0.004), (hx, H - tt, hz), "steel_warm", "+y-y+z")
    yt = H - tt - 0.004
    if not sink:
        front(m, st, -hx + 0.01, hx - 0.01, yt - 0.16, yt, zf, "wood_front", True, "h", line="wood_front_dark")
        yt -= 0.16
    front(m, st, -hx + 0.01, 0.0, st.plinth + 0.005, yt, zf, "wood_front", True, line="wood_front_dark")
    front(m, st, 0.0, hx - 0.01, st.plinth + 0.005, yt, zf, "wood_front", False, line="wood_front_dark")
    _boxes(prm).append(((-hx, 0.0, -hz), (hx, H, hz)))
    if not sink:
        return
    steel = "steel_warm"
    loft(m, (sx0 + 0.03, sx1 - 0.03, z0 + 0.03, z1 - 0.03, H - 0.18), (sx0 + 0.02, sx1 - 0.02, z0 + 0.02, z1 - 0.02, H),
         steel, inner=0.006, inner_role=steel)
    for lo, hi in (((sx0, H, z0), (sx1, H + 0.008, z0 + 0.02)), ((sx0, H, z1 - 0.02), (sx1, H + 0.008, z1)),
                   ((sx0, H, z0 + 0.02), (sx0 + 0.02, H + 0.008, z1 - 0.02)),
                   ((sx1 - 0.02, H, z0 + 0.02), (sx1, H + 0.008, z1 - 0.02))):
        box(m, lo, hi, steel, "+x-x+y+z-z")
    cyl(m, "y", ((sx0 + sx1) / 2, (z0 + z1) / 2), 0.03, H - 0.176, H - 0.174, "steel_black", 10, caps=(False, True))
    box(m, (-hx + 0.04, H, z0), (sx0 - 0.01, H + 0.006, z1), steel, "+x-x+y+z-z")  # the drainer and its ribs
    for k in range(7):
        x = -hx + 0.07 + k * 0.055
        box(m, (x, H + 0.006, z0 + 0.03), (x + 0.012, H + 0.01, z1 - 0.03), steel, "+x-x+y+z-z")
    tap(m, st, (sx0 + sx1) / 2, -hz + 0.055, H)


def build_backsplash(m, s, R, prm, rng):
    """A tiled wall strip behind a worktop run (the world look; its size: the run's length, the strip with its cap
    16 mm deep, its height plus the 8 mm cap): authored at the wall, the bottom on the worktop line."""
    st = _style(prm)
    L, W, H = s
    backsplash(m, st, L, H - 0.008, R[0], R[-1])


def build_kitchen_upper(m, s, R, prm, rng):
    """A C2-white wall cabinet (per 1 m, wall pivot): carcass, a dark crown, a shelf with plates and glasses behind
    two tinted-glass doors whose handles sit low; everything inside the 0.35 m depth."""
    st = _style(prm)
    L, W, H = s
    hx = L / 2
    zf = W - st.reach - 0.002
    p = 0.018  # an open carcass (back, sides, bottom, top) so the glass doors show what is inside
    cbox(m, (-hx, 0.0, 0.0), (hx, H, p), "wood_front", st.bevel_small)
    for xa, xb in ((-hx, -hx + p), (hx - p, hx)):
        cbox(m, (xa, 0.0, p), (xb, H, zf), "wood_front", st.bevel_small)
    for ya, yb in ((0.0, p), (H - 0.04 - p, H - 0.04)):
        cbox(m, (-hx + p, ya, p), (hx - p, yb, zf), "wood_front", st.bevel_small)
    cbox(m, (-hx, H - 0.04, 0.0), (hx, H, W), "wood_front_dark", st.bevel_small)
    for i in range(6):
        x = -hx + 0.1 + i * 0.03
        cyl(m, "x", (p + 0.1, 0.15), 0.1, x, x + 0.012, "porcelain_white", 10)
    for i in range(4):
        x = 0.1 + i * 0.09
        cyl(m, "y", (x, 0.15), 0.03, 0.37, 0.465, "glass_tint", 10, r1=0.034)
    box(m, (-hx + 0.02, 0.36, 0.02), (hx - 0.02, 0.37, zf - 0.02), "wood_front", "+y-y+z")
    top = H - 0.045
    front(m, st, -hx + 0.004, 0.0, 0.004, top, zf, "wood_front", True, low=True, glass="glass_tint")
    front(m, st, 0.0, hx - 0.004, 0.004, top, zf, "wood_front", False, low=True, glass="glass_tint")


def build_stove(m, s, R, prm, rng):
    """The C2-white range (hero): cream enamel body on the plinth, a steel hob with four burners under two cast-iron
    grates, a backguard with a clock, a control panel of five knobs, the oven door with its window and the rack
    behind it, a storage drawer, and the steel hood with its flue up to `hood_top` (wall side). The stove's own box
    and the hood's are its colliders."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    hood_top = prm.get("hood_top", 1.9)
    body, steel = "enamel_cream", "steel_warm"
    so = 0.035
    zf = hz - 0.03 - so - 0.001  # the oven door's back: its handle ends 1 mm inside the hob's edge
    plinth(m, st, -hx + 0.02, hx - 0.02, -hz + 0.02, zf + 0.03 - st.plinth_setback)
    cbox(m, (-hx, st.plinth, -hz), (hx, H - 0.03, zf), body, st.bevel)
    cbox(m, (-hx, H - 0.03, -hz), (hx, H, hz), steel, st.bevel_small)
    cbox(m, (-hx, H, -hz), (hx, H + 0.14, -hz + 0.04), body, st.bevel_small)  # the backguard and its clock
    box(m, (-0.08, H + 0.05, -hz + 0.04), (0.08, H + 0.11, -hz + 0.043), "glass_dark", "+z")
    for sx in (-1, 1):
        for sz in (-1, 1):
            burner(m, st, sx * 0.165, sz * 0.14, H, 0.075 if sz < 0 else 0.06)
        burner_grate(m, sx * 0.165, 0.0, 0.15, 0.27, H, H + 0.03)
    cbox(m, (-hx + 0.01, H - 0.14, zf), (hx - 0.01, H - 0.035, zf + 0.025), steel, st.bevel_small)
    for k in range(5):
        x = -0.26 + k * 0.13
        cyl(m, "z", (x, H - 0.088), 0.03, zf + 0.025, zf + 0.03, "steel_black", st.segments)
        cyl(m, "z", (x, H - 0.088), 0.02, zf + 0.03, zf + 0.055, "rubber_black", st.segments)
        box(m, (x - 0.004, H - 0.088, zf + 0.055), (x + 0.004, H - 0.07, zf + 0.057), "porcelain_white", "+z")
    y0, y1 = 0.2, H - 0.16
    cbox(m, (-hx + 0.012, y0, zf), (hx - 0.012, y1, zf + 0.03), body, st.bevel_small)
    wx = 0.24
    box(m, (-wx, y0 + 0.12, zf + 0.03), (wx, y1 - 0.1, zf + 0.032), "glass_dark", "+z")
    box(m, (-wx - 0.015, y0 + 0.105, zf + 0.03), (wx + 0.015, y0 + 0.12, zf + 0.034), steel, "+y-y+z")
    box(m, (-wx - 0.015, y1 - 0.1, zf + 0.03), (wx + 0.015, y1 - 0.085, zf + 0.034), steel, "+y-y+z")
    for k in range(9):  # the oven rack seen through the window
        x = -0.2 + k * 0.05
        bar(m, (x, 0.42, -hz + 0.1), (x, 0.42, zf - 0.02), 0.005, "chrome")
    box(m, (-hx + 0.02, y0 - 0.006, zf + 0.002), (hx - 0.02, y0, zf + 0.026), "rubber_black", "+y-y+z")
    bar_handle(m, st, (-0.27, y1 - 0.05), (0.27, y1 - 0.05), zf + 0.03, standoff=so)
    front(m, st, -hx + 0.012, hx - 0.012, st.plinth + 0.005, y0 - 0.012, zf, body, True, "h")
    zb = -hz  # the hood: canopy, flue, light strip, grease filter, rivets and a switch
    loft(m, (-hx, hx, zb, zb + 0.5, 1.45), (-0.13, 0.13, zb, zb + 0.24, 1.66), steel, top=True)
    box(m, (-0.13, 1.66, zb), (0.13, hood_top, zb + 0.24), steel, "+x-x+y+z")
    box(m, (-hx + 0.04, 1.446, zb + 0.06), (hx - 0.04, 1.45, zb + 0.44), "steel_black", "-y")
    for k in range(7):
        z = zb + 0.08 + k * 0.05
        box(m, (-hx + 0.06, 1.441, z), (hx - 0.06, 1.446, z + 0.012), steel, "-y+z-z")
    box(m, (-0.2, 1.441, zb + 0.455), (0.2, 1.447, zb + 0.48), "glass_tint", "-y")
    for k in range(8):
        x = -hx + 0.06 + k * 0.083
        cyl(m, "z", (x, 1.47), 0.006, zb + 0.5, zb + 0.504, "chrome", 6, caps=(False, True))
    cyl(m, "z", (0.28, 1.5), 0.012, zb + 0.46, zb + 0.49, "steel_black", 8)
    _boxes(prm).extend([((-hx, 0.0, -hz), (hx, H + 0.14, hz)), ((-hx, 1.45, zb), (hx, hood_top, zb + 0.5))])


def build_fridge(m, s, R, prm, rng):
    """The C2-white fridge (hero): warm-white enamel body and two doors on the plinth line, gaskets, long chrome pulls,
    hinge covers, a top grille, a kick plate with vents, a water dispenser and a badge; the handles and hinges end
    inside size_m."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2 - 0.006, W / 2
    body = prm.get("body", "enamel_white")
    hf = hz - 0.062  # the doors' face: the pulls end inside size_m
    zf = hf - 0.04
    plinth(m, st, -hx + 0.02, hx - 0.02, -hz + 0.02, hf - st.plinth_setback)
    n = st.segments
    rslab(m, -hx, hx, st.plinth, H, -hz, zf, 0.025, body, 8)  # soft vertical edges, as a real appliance
    split = 1.15
    for y0, y1, low in ((st.plinth + 0.005, split, False), (split + 0.012, H - 0.05, True)):
        rslab(m, -hx + 0.004, hx - 0.004, y0, y1, zf, hf, 0.018, body, 8, front_only=True, bottom=True)
        for lo, hi in (((-hx + 0.004, y0 + 0.004), (hx - 0.004, y0 + 0.012)), ((-hx + 0.004, y1 - 0.012),
                       (hx - 0.004, y1 - 0.004)), ((-hx + 0.004, y0 + 0.012), (-hx + 0.012, y1 - 0.012)),
                       ((hx - 0.012, y0 + 0.012), (hx - 0.004, y1 - 0.012))):  # the gasket round the door
            box(m, (lo[0], lo[1], zf - 0.004), (hi[0], hi[1], zf), "rubber_black", "+x-x+y-y+z")
        hy0, hy1 = (y0 + 0.05, y0 + 0.4) if low else (y1 - 0.5, y1 - 0.05)
        hxp = hx - 0.06
        rod(m, (hxp, hy0, hf + 0.048), (hxp, hy1, hf + 0.048), 0.012, "chrome", n)
        for yy in (hy0 + 0.02, hy1 - 0.02):
            cyl(m, "z", (hxp, yy), 0.01, hf, hf + 0.048, "chrome", 12, caps=(False, False))
            cyl(m, "z", (hxp, yy), 0.016, hf, hf + 0.004, "chrome", 12, caps=(False, True))
    cbox(m, (-hx + 0.01, 0.0, hf - 0.08), (hx - 0.01, st.plinth - 0.004, hf - 0.06), "steel_warm", st.bevel_small)
    for k in range(5):
        box(m, (-hx + 0.08, 0.02 + k * 0.016, hf - 0.06), (hx - 0.08, 0.027 + k * 0.016, hf - 0.058), "rubber_black",
            "+z+y-y")
    cbox(m, (-hx + 0.004, H - 0.044, zf), (hx - 0.004, H - 0.004, zf + 0.02), "steel_warm", st.bevel_small)
    for k in range(24):
        x = -hx + 0.05 + k * ((2 * hx - 0.1) / 23)
        box(m, (x - 0.008, H - 0.036, zf + 0.02), (x + 0.008, H - 0.012, zf + 0.021), "rubber_black", "+z")
    for y0, y1, x1 in ((H - 0.09, H - 0.046, 0.05), (split - 0.02, split + 0.03, 0.04),
                       (st.plinth + 0.01, st.plinth + 0.05, 0.04)):
        rslab(m, -hx - 0.004, -hx + x1, y0, y1, zf - 0.01, hf + 0.004, 0.008, "chrome", 6, front_only=True,
              bottom=True)
    box(m, (-0.08, H - 0.12, hf), (0.08, H - 0.1, hf + 0.003), "chrome", "+x-x+y-y+z")
    cbox(m, (-0.22, 1.32, hf - 0.012), (-0.02, 1.58, hf + 0.004), "steel_black", st.bevel_small)
    box(m, (-0.19, 1.36, hf + 0.004), (-0.05, 1.5, hf + 0.006), "glass_dark", "+z")
    cyl(m, "y", (-0.12, hf - 0.002), 0.012, 1.48, 1.5, "chrome", 8)
    box(m, (-0.21, 1.33, hf + 0.004), (-0.03, 1.336, hf + 0.03), "steel_black", "+y-y+z+x-x")
    for k in range(6):  # side ribs
        y = 0.2 + k * 0.27
        for sx in (-1, 1):
            box(m, (sx * hx - (0.002 if sx < 0 else 0.0), y, -hz + 0.05), (sx * hx + (0.002 if sx > 0 else 0.0),
                y + 0.004, zf - 0.05), "steel_black", "+x" if sx > 0 else "-x")
    for b in range(4):  # the dispenser's buttons and the temperature panel's
        cyl(m, "z", (-0.19 + b * 0.045, 1.63), 0.01, hf, hf + 0.004, "steel_black", 12, caps=(False, True))


# ---- The living room in the world look (#150): upholstery, shelving with books, a mantel, a TV unit.

def cushion(m: Mesh, lo, hi, role: str, soft: float = 0.03) -> None:
    """An upholstered block: a box with a soft chamfer (`soft`, at most a third of its smallest side)."""
    c = min(soft, *((hi[i] - lo[i]) / 3.1 for i in range(3)))
    cbox(m, lo, hi, role, c)


def leg(m: Mesh, x: float, z: float, y0: float, y1: float, r: float, role: str, taper: float = 0.7, n: int = 8) -> None:
    """A round furniture leg from y0 up to y1, tapering to `taper` of its radius at the foot."""
    cyl(m, "y", (x, z), r * taper, y0, y1, role, n, r1=r)


def book_run(m: Mesh, x0: float, x1: float, y: float, z0: float, depth: float, h_max: float, paints: list,
             rng: random.Random, gap: float = 0.12, lie: float = 0.1) -> None:
    """Books on a shelf from x0 to x1 at y, spines at the front z0 + depth: standing books of varied width, height
    and depth (`gap`: the chance of a gap, `lie`: of a short stack lying flat), never past x1 or h_max."""
    x = x0
    while x < x1 - 0.03:
        r = rng.random()
        if r < gap:
            x += 0.03 + 0.05 * rng.random()
            continue
        if r < gap + lie and x1 - x > 0.26:  # a few books lying flat
            w = 0.18 + 0.05 * rng.random()
            yy = y
            for _ in range(2 + int(rng.random() * 2)):
                t = 0.025 + 0.015 * rng.random()
                if yy + t > y + h_max:
                    break
                box(m, (x, yy, z0 + depth - w * 0.95), (x + w, yy + t - 0.002, z0 + depth), rng.choice(paints),
                    "+x-x+y+z")
                yy += t
            x += w + 0.01
            continue
        bw = min(0.022 + 0.026 * rng.random(), x1 - x)
        bh = min(h_max, 0.17 + 0.11 * rng.random())
        bd = min(depth, 0.15 + 0.07 * rng.random())
        box(m, (x, y, z0 + depth - bd), (x + bw - 0.002, y + bh, z0 + depth), rng.choice(paints), "+x-x+y+z")
        x += bw


def build_sofa(m, s, R, prm, rng):
    """An upholstered sofa (or with `seats` 1 an armchair) in the world look: tapered wood legs, a base, arms and a
    back in linen (`body`, default `upholstery`), loose seat and back cushions, woven throw pillows (`pillows`,
    painted in turn from `pillow_paints`) and with `throw` a blanket (`throw_paint`) over the left arm. Colliders: the seat and the back."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    n = int(prm.get("seats", 3))
    up = prm.get("body", "upholstery")
    arm_w = float(prm.get("arm", 0.17 if n > 1 else 0.15))
    ya, ys, yc = 0.1, 0.4, 0.52  # the base's bottom, the seat deck, the seat cushions' top
    back_d = 0.2
    for sx in (-1, 1):
        for sz in (-1, 1):
            leg(m, sx * (hx - 0.07), sz * (hz - 0.07), 0.0, ya + 0.01, 0.022, "wood_front_dark")
    cushion(m, (-hx + arm_w - 0.01, ya, -hz + 0.02), (hx - arm_w + 0.01, ys, hz - 0.03), up, 0.025)
    arm_h = min(H - 0.18, 0.64)
    for sx in (-1, 1):
        x0, x1 = (-hx, -hx + arm_w) if sx < 0 else (hx - arm_w, hx)
        cushion(m, (x0, ya, -hz), (x1, arm_h, hz), up, 0.05)
    cushion(m, (-hx + arm_w - 0.02, ya, -hz), (hx - arm_w + 0.02, H - 0.06, -hz + back_d), up, 0.05)
    xs = [-hx + arm_w + (L - 2 * arm_w) * k / n for k in range(n + 1)]
    for a, b in zip(xs, xs[1:]):
        cushion(m, (a + 0.006, ys, -hz + back_d - 0.02), (b - 0.006, yc, hz - 0.01), up, 0.04)
        cushion(m, (a + 0.01, yc, -hz + back_d - 0.06), (b - 0.01, H, -hz + back_d + 0.1), up, 0.06)
    paints = list(prm.get("pillow_paints", ["cushion_rust", "cushion_mustard"]))
    for k in range(int(prm.get("pillows", 2))):
        sx = -1 if k % 2 == 0 else 1
        cx = sx * (hx - arm_w - 0.2) if n > 1 else 0.0
        r = min(0.19, (H - yc) / 2 - 0.01)  # a plump square pillow leaning on the back cushions
        zc = -hz + back_d + 0.16
        cushion(m, (cx - r, H - 2 * r - 0.004, zc - 0.065), (cx + r, H - 0.004, zc + 0.065), paints[k % len(paints)],
                0.055)
    if prm.get("throw"):  # a folded blanket over the left arm: over the top and down both sides
        z0, z1 = -0.18, 0.22
        tp = prm.get("throw_paint", "throw_cream")
        cushion(m, (-hx, arm_h - 0.004, z0), (-hx + arm_w + 0.012, arm_h + 0.02, z1), tp, 0.008)
        cushion(m, (-hx, arm_h - 0.3, z0), (-hx + 0.016, arm_h, z1), tp, 0.006)
        cushion(m, (-hx + arm_w - 0.004, yc + 0.02, z0), (-hx + arm_w + 0.012, arm_h, z1), tp, 0.006)
    _boxes(prm).extend([((-hx, 0.0, -hz), (hx, yc, hz)), ((-hx, yc, -hz), (hx, H, -hz + back_d + 0.1))])


def build_bookcase(m, s, R, prm, rng):
    """A bookcase in the wood fronts: plinth, bevelled sides and a top with a small cornice, a dark back, `shelves`
    shelves of books (book_run) over a cupboard of two doors `doors_h` high (0: none)."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    t = 0.022
    body = prm.get("body", "wood_front")
    dh = float(prm.get("doors_h", 0.72))
    zf = hz - st.reach - 0.002
    plinth(m, st, -hx + t, hx - t, -hz + 0.02, zf + st.front_t - 0.03, body)
    for sx in (-1, 1):
        cbox(m, (hx - t if sx > 0 else -hx, 0, -hz), (hx if sx > 0 else -hx + t, H - 0.03, zf + st.front_t),
             body, st.bevel_small)
    cbox(m, (-hx, H - 0.03, -hz), (hx, H, hz), body, st.bevel_small)
    box(m, (-hx + t, st.plinth, -hz), (hx - t, H - 0.03, -hz + 0.01), "wood_front_dark", "+z")
    y = st.plinth
    if dh:
        cbox(m, (-hx + t, st.plinth, -hz + 0.01), (hx - t, dh, zf), body, st.bevel_small)
        front(m, st, -hx + t, 0.0, st.plinth + 0.004, dh, zf, body, True, line="wood_front_dark")
        front(m, st, 0.0, hx - t, st.plinth + 0.004, dh, zf, body, False, line="wood_front_dark")
        y = dh
    n = int(prm.get("shelves", 4))
    step = (H - 0.03 - y) / n
    paints = ["book_cream", "book_teal", "book_mustard", "book_red", "book_navy", "book_sage", "book_grey",
              "book_cream"]
    for i in range(n):
        y0 = y + step * i
        cbox(m, (-hx + t, y0, -hz + 0.01), (hx - t, y0 + t, zf + st.front_t), body, st.bevel_small)
        book_run(m, -hx + t + 0.012, hx - t - 0.012, y0 + t, -hz + 0.02, min(0.24, zf + hz - 0.03),
                 step - t - 0.025, paints, rng)


def build_tv_unit(m, s, R, prm, rng):
    """A low TV unit in the wood fronts on steel legs (two doors either side of an open shelf with a set-top box),
    an oak top and a flat TV on a pedestal: black frame, dark glass screen. The TV's top is the prop's height."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    uh = float(prm.get("unit_h", 0.42))
    zf = hz - st.reach - 0.002
    for sx in (-1, 1):
        for sz in (-1, 1):
            leg(m, sx * (hx - 0.06), sz * (hz - 0.08), 0.0, 0.1, 0.014, "steel_black", 0.8)
    cbox(m, (-hx + 0.005, 0.1, -hz), (hx - 0.005, uh - 0.03, zf), "wood_front", st.bevel)
    worktop(m, st, -hx, hx, -hz, hz, "worktop_wood", y=uh)
    ow = 0.42  # the open middle shelf
    front(m, st, -hx + 0.01, -ow / 2, 0.104, uh - 0.034, zf, "wood_front", True, "h", line="wood_front_dark")
    front(m, st, ow / 2, hx - 0.01, 0.104, uh - 0.034, zf, "wood_front", False, "h", line="wood_front_dark")
    box(m, (-ow / 2, 0.12, zf - 0.32), (ow / 2, uh - 0.05, zf + 0.001), "wood_front_dark", "+z+y-y+x-x")
    cbox(m, (-0.13, 0.12, zf - 0.24), (0.13, 0.165, zf - 0.04), "rubber_black", 0.004)  # the set-top box
    box(m, (0.07, 0.14, zf - 0.04), (0.1, 0.146, zf - 0.039), "chrome", "+z")
    tw = min(L - 0.3, 1.1)
    td = 0.035
    cbox(m, (-0.16, uh, -0.1), (0.16, uh + 0.012, 0.08), "steel_black", 0.003)  # the pedestal
    box(m, (-0.03, uh + 0.012, -0.05), (0.03, uh + 0.08, -0.02), "steel_black", "+x-x+z-z")
    y0 = uh + 0.06
    cbox(m, (-tw / 2, y0, -0.06), (tw / 2, H, -0.06 + td), "rubber_black", 0.004)
    box(m, (-tw / 2 + 0.008, y0 + 0.012, -0.06 + td), (tw / 2 - 0.008, H - 0.008, -0.06 + td + 0.002), "glass_dark",
        "+z")
    cbox(m, (-tw / 2 + 0.1, y0 + 0.08, -0.1), (tw / 2 - 0.1, H - 0.08, -0.06), "rubber_black", 0.01)  # the back
    _boxes(prm).extend([((-hx, 0.0, -hz), (hx, uh, hz)), ((-tw / 2, uh, -0.1), (tw / 2, H, -0.06 + td + 0.002))])


def build_mantel_fireplace(m, s, R, prm, rng):
    """A fireplace in the world look: a light stone surround (legs with bases, a header with a moulding), a wood
    mantel shelf, a dark stone hearth, a black steel firebox with a grate and three logs."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    hearth_h = 0.05
    ox, oy = 0.42, 0.72  # the opening's half width and height
    mantel_y = H - 0.07
    zb = -hz + 0.02
    zs = hz - 0.16  # the surround's face
    cbox(m, (-hx + 0.02, 0.0, -hz), (hx - 0.02, hearth_h, hz), "stone_dark", st.bevel)
    for sx in (-1, 1):
        x0, x1 = (-hx + 0.1, -ox) if sx < 0 else (ox, hx - 0.1)
        cbox(m, (x0, hearth_h, zb), (x1, mantel_y - 0.12, zs), "stone_light", st.bevel)
        cbox(m, (x0 - 0.015, hearth_h, zb), (x1 + 0.015, hearth_h + 0.12, zs + 0.015), "stone_light", st.bevel_small)
    cbox(m, (-ox - 0.01, oy, zb), (ox + 0.01, mantel_y - 0.12, zs), "stone_light", st.bevel)
    cbox(m, (-hx + 0.08, mantel_y - 0.12, zb), (hx - 0.08, mantel_y - 0.06, zs + 0.03), "stone_light", st.bevel_small)
    cbox(m, (-hx + 0.09, mantel_y - 0.06, zb), (hx - 0.09, mantel_y, zs + 0.012), "stone_light", st.bevel_small)
    cbox(m, (-hx, mantel_y, -hz), (hx, H, zs + 0.08), "wood_front_dark", st.bevel)
    zi = zb + 0.01  # the firebox: steel back, sides and top, a stone floor inside the opening
    box(m, (-ox, hearth_h, zi), (ox, oy, zi + 0.01), "steel_black", "+z")
    for sx in (-1, 1):
        box(m, (sx * ox - (0.01 if sx > 0 else 0), hearth_h, zi), (sx * ox + (0 if sx > 0 else 0.01), oy, zs),
            "steel_black", "-x" if sx > 0 else "+x")
    box(m, (-ox, oy - 0.01, zi), (ox, oy, zs), "steel_black", "-y")
    box(m, (-ox, hearth_h, zi), (ox, hearth_h + 0.004, zs), "stone_dark", "+y")
    cbox(m, (-ox + 0.006, oy - 0.03, zs - 0.006), (ox - 0.006, oy, zs + 0.006), "steel_black", 0.003)  # the lintel
    yg = hearth_h + 0.1  # the grate: two rails on four feet and five bars
    for sx in (-1, 1):
        rod(m, (sx * 0.24, yg, zi + 0.08), (sx * 0.24, yg, zs - 0.08), 0.008, "steel_black")
        for zz in (zi + 0.1, zs - 0.1):
            rod(m, (sx * 0.24, hearth_h, zz), (sx * 0.24, yg, zz), 0.008, "steel_black", caps=False)
    for k in range(5):
        z = zi + 0.1 + (zs - zi - 0.2) * k / 4
        rod(m, (-0.26, yg + 0.008, z), (0.26, yg + 0.008, z), 0.006, "steel_black")
    for p0, p1, r in (((-0.22, yg + 0.05, zi + 0.12), (0.2, yg + 0.05, zi + 0.18), 0.045),
                      ((-0.2, yg + 0.05, zs - 0.14), (0.22, yg + 0.06, zs - 0.18), 0.042),
                      ((-0.12, yg + 0.13, zi + 0.16), (0.16, yg + 0.12, zs - 0.16), 0.04)):
        rod(m, p0, p1, r, "wood_front_dark", 8)
    _boxes(prm).extend([((-hx, 0.0, -hz), (hx, hearth_h, hz)), ((-hx + 0.08, hearth_h, -hz), (-ox, H, zs + 0.08)),
                        ((ox, hearth_h, -hz), (hx - 0.08, H, zs + 0.08)), ((-hx, oy, -hz), (hx, H, zs + 0.08))])


def build_coffee_table(m, s, R, prm, rng):
    """A coffee table: a bevelled oak top on an apron, four tapered legs and a lower shelf in the wood fronts."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    tt = 0.035
    i = 0.06
    cbox(m, (-hx, H - tt, -hz), (hx, H, hz), "worktop_wood", st.bevel_small)
    for sx in (-1, 1):
        for sz in (-1, 1):
            leg(m, sx * (hx - i), sz * (hz - i), 0.0, H - tt, 0.022, "wood_front_dark", 0.6)
    for x0, x1, z0, z1 in ((-hx + i, hx - i, -hz + i - 0.012, -hz + i + 0.008),
                           (-hx + i, hx - i, hz - i - 0.008, hz - i + 0.012),
                           (-hx + i - 0.012, -hx + i + 0.008, -hz + i, hz - i),
                           (hx - i - 0.008, hx - i + 0.012, -hz + i, hz - i)):
        box(m, (x0, H - tt - 0.07, z0), (x1, H - tt, z1), "wood_front_dark", "+x-x-y+z-z")
    cbox(m, (-hx + i - 0.01, 0.1, -hz + i - 0.01), (hx - i + 0.01, 0.12, hz - i + 0.01), "wood_front", st.bevel_small)


def build_sideboard(m, s, R, prm, rng):
    """A sideboard or a chest of drawers in the wood fronts: an oak top, a carcass on four tapered legs, `doors`
    doors or `drawers` drawers (raised panels, a dark line, the bar handle)."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    lh = 0.14
    zf = hz - st.reach - 0.002
    for sx in (-1, 1):
        for sz in (-1, 1):
            leg(m, sx * (hx - 0.06), sz * (hz - 0.07), 0.0, lh + 0.01, 0.018, "wood_front_dark", 0.6)
    cbox(m, (-hx + 0.01, lh, -hz), (hx - 0.01, H - 0.03, zf), "wood_front", st.bevel)
    worktop(m, st, -hx, hx, -hz, hz, "worktop_wood", y=H)
    y0, y1 = lh + 0.006, H - 0.034
    if prm.get("drawers"):
        n = int(prm["drawers"])
        for k in range(n):
            a, b = y0 + (y1 - y0) * k / n, y0 + (y1 - y0) * (k + 1) / n
            front(m, st, -hx + 0.012, hx - 0.012, a, b, zf, "wood_front", True, "h", line="wood_front_dark")
    else:
        n = int(prm.get("doors", 3))
        xs = [-hx + 0.012 + (L - 0.024) * k / n for k in range(n + 1)]
        for k, (a, b) in enumerate(zip(xs, xs[1:])):
            front(m, st, a, b, y0, y1, zf, "wood_front", k < n / 2, line="wood_front_dark")


def build_side_table(m, s, R, prm, rng):
    """A round side table: an oak top with an undercut edge on three splayed, tapered legs and a ring."""
    L, W, H = s
    r = min(L, W) / 2
    n = 20
    cyl(m, "y", (0.0, 0.0), r, H - 0.03, H, "worktop_wood", n)
    cyl(m, "y", (0.0, 0.0), r - 0.012, H - 0.034, H - 0.03, "worktop_wood", n, caps=(True, False))
    for k in range(3):
        a = math.radians(90 + 120 * k)
        top = (math.cos(a) * r * 0.55, H - 0.034, math.sin(a) * r * 0.55)
        foot = (math.cos(a) * r * 0.8, 0.0, math.sin(a) * r * 0.8)
        rod(m, foot, top, 0.016, "wood_front_dark", 8)
    tube(m, "y", (0.0, 0.0), r * 0.62, r * 0.62 + 0.012, H * 0.3, H * 0.3 + 0.012, "wood_front_dark", 16)


def build_carpet_rug(m, s, R, prm, rng):
    """A rug on the carpet layer: a field with a light border band and an inner frame, short fringes at both ends
    (`fringe`). `motif` (#162, a hallway runner): instead of the inner frame, small squares of the border's paint
    every `motif` metres down the middle, a soft pattern rather than lines along the length."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    field, border = prm.get("field", "carpet_field"), prm.get("border", "carpet_border")
    box(m, (-hx, 0, -hz), (hx, H * 0.7, hz), field, "+x-x+y+z-z")
    b, w = 0.1, 0.07
    for x0, x1, z0, z1 in ((-hx + b, hx - b, -hz + b, -hz + b + w), (-hx + b, hx - b, hz - b - w, hz - b),
                           (-hx + b, -hx + b + w, -hz + b + w, hz - b - w), (hx - b - w, hx - b, -hz + b + w, hz - b - w)):
        box(m, (x0, H * 0.7, z0), (x1, H, z1), border, "+x-x+y+z-z")
    step = float(prm.get("motif", 0.0))
    i = b + w + 0.14
    if step > 0:
        n = max(1, int((L - 2 * i) / step))
        for k in range(n):
            cx, q = -(n - 1) * step / 2 + k * step, min(0.07, hz / 4)
            box(m, (cx - q, H * 0.7, -q), (cx + q, H * 0.85, q), border, "+x-x+y+z-z")
    else:
        for x0, x1, z0, z1 in ((-hx + i, hx - i, -hz + i, -hz + i + 0.025), (-hx + i, hx - i, hz - i - 0.025, hz - i),
                               (-hx + i, -hx + i + 0.025, -hz + i + 0.025, hz - i - 0.025),
                               (hx - i - 0.025, hx - i, -hz + i + 0.025, hz - i - 0.025)):
            box(m, (x0, H * 0.7, z0), (x1, H * 0.85, z1), border, "+x-x+y+z-z")
    if prm.get("fringe", True):  # the fringes lie inside the box: the rug's ends are short of size_m by 5 cm
        for sx in (-1, 1):
            z = -hz + 0.03
            while z < hz - 0.04:
                xa, xb = sorted((sx * hx, sx * (hx - 0.05)))
                box(m, (xa, 0, z), (xb, H * 0.75, z + 0.012), border, "+y")
                z += 0.045


# ---- The living room's detail layer (#150): the small things on its tables, mantel and floor (class clutter).

def build_living_tray(m, s, R, prm, rng):
    """A low oak tray with two pillar candles and a stoneware bowl, a TV remote lying beside it at +x."""
    L, W, H = s
    hz, x0 = W / 2, -L / 2
    x1 = L / 2 - 0.075  # the tray's east edge; the remote lies past it
    box(m, (x0, 0, -hz), (x1, 0.008, hz), "worktop_wood")
    for a, b, c, d in ((x0, x1, -hz, -hz + 0.01), (x0, x1, hz - 0.01, hz), (x0, x0 + 0.01, -hz + 0.01, hz - 0.01),
                       (x1 - 0.01, x1, -hz + 0.01, hz - 0.01)):
        box(m, (a, 0.008, c), (b, 0.032, d), "worktop_wood", "+x-x+y+z-z")
    for cx, cz, r, h in ((x0 + 0.06, -0.04, 0.034, H - 0.006), (x0 + 0.13, 0.045, 0.03, H * 0.68)):
        cyl(m, "y", (cx, cz), r, 0.008, h, "enamel_cream", 14)
        cyl(m, "y", (cx, cz), 0.0025, h, h + 0.006, "steel_black", 4)
    cyl(m, "y", (x1 - 0.08, 0.0), 0.035, 0.008, 0.055, "stone_dark", 14, r1=0.06, caps=(True, False))
    cyl(m, "y", (x1 - 0.08, 0.0), 0.05, 0.02, 0.05, "stone_light", 14, r1=0.055, caps=(True, False))
    rx0, rx1 = L / 2 - 0.05, L / 2
    cbox(m, (rx0, 0, -0.085), (rx1, 0.018, 0.085), "rubber_black", 0.006)
    box(m, (rx0 + 0.016, 0.018, -0.07), (rx0 + 0.034, 0.021, -0.055), "paint_red", "+y+x-x+z-z")
    for k in range(4):
        z = -0.035 + k * 0.03
        box(m, (rx0 + 0.01, 0.018, z), (rx1 - 0.01, 0.0205, z + 0.018), "steel_black", "+y+x-x+z-z")


def build_magazine_fan(m, s, R, prm, rng):
    """Four magazines fanned out on a table: glossy covers of different colours over cream page edges."""
    L, W, H = s
    covers = [r for r in R if r.startswith("book_")] or ["book_red"]
    w, d, t = L - 0.09, W - 0.06, H / 4
    for k in range(4):
        x, z, y = -L / 2 + k * 0.03, -W / 2 + k * 0.02, k * t
        box(m, (x, y, z), (x + w, y + t * 0.75, z + d), "book_cream", "+x-x+z-z-y")
        box(m, (x, y + t * 0.75, z), (x + w, y + t, z + d), covers[(k * 3 + 1) % len(covers)])
        box(m, (x + 0.02, y + t, z + 0.02), (x + w * 0.6, y + t + 0.0005, z + 0.05), "book_cream", "+y")


def build_mantel_clock(m, s, R, prm, rng):
    """A mantel clock: a walnut case on a stepped plinth, a round enamel dial in a brass bezel, black hands."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    cbox(m, (-hx, 0, -hz), (hx, 0.025, hz), "wood_front_dark", 0.005)
    cbox(m, (-hx + 0.02, 0.025, -hz + 0.01), (hx - 0.02, H * 0.55, hz - 0.01), "wood_front_dark", 0.006)
    r = min(hx - 0.03, H * 0.42)
    yc = H - r - 0.004
    cyl(m, "z", (0.0, yc), r, -hz + 0.01, hz - 0.012, "wood_front_dark", 16)
    tube(m, "z", (0.0, yc), r * 0.78, r * 0.9, hz - 0.012, hz - 0.002, "steel_warm", 12)
    cyl(m, "z", (0.0, yc), r * 0.78, hz - 0.012, hz - 0.008, "enamel_white", 16, caps=(False, True))
    box(m, (-0.003, yc, hz - 0.008), (0.003, yc + r * 0.55, hz - 0.006), "steel_black", "+z")
    box(m, (0.0, yc - 0.003, hz - 0.007), (r * 0.42, yc + 0.003, hz - 0.005), "steel_black", "+z")
    for k in range(12):
        a = math.radians(30 * k)
        x, y = math.sin(a) * r * 0.66, yc + math.cos(a) * r * 0.66
        box(m, (x - 0.003, y - 0.003, hz - 0.008), (x + 0.003, y + 0.003, hz - 0.0065), "steel_black", "+z")


def build_standing_frame(m, s, R, prm, rng):
    """A small photo frame standing on its strut: an oak frame, a cream mat and a landscape photo in two bands."""
    L, W, H = s
    hx, f, t = L / 2, 0.018, 0.014
    z1 = W / 2
    z0 = z1 - t
    for lo, hi in (((-hx, 0, z0), (hx, f, z1)), ((-hx, H - f, z0), (hx, H, z1)),
                   ((-hx, f, z0), (-hx + f, H - f, z1)), ((hx - f, f, z0), (hx, H - f, z1))):
        box(m, lo, hi, "worktop_wood")
    box(m, (-hx + f, f, z0 + 0.002), (hx - f, H - f, z1 - 0.004), "book_cream")
    m2 = 0.02
    box(m, (-hx + f + m2, f + m2, z1 - 0.004), (hx - f - m2, (H - f) * 0.55, z1 - 0.0035), "book_sage", "+z")
    box(m, (-hx + f + m2, (H - f) * 0.55, z1 - 0.004), (hx - f - m2, H - f - m2, z1 - 0.0035), "book_teal", "+z")
    rod(m, (0.0, 0.0, -W / 2), (0.0, H * 0.6, z0), 0.004, "wood_front_dark", 4)


def build_throw_basket(m, s, R, prm, rng):
    """A woven basket of oak bands with a cream throw folded into it, one fold hanging over its front rim."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    hb = H * 0.62  # the basket's rim
    box(m, (-hx + 0.01, 0, -hz + 0.01), (hx - 0.01, 0.015, hz - 0.01), "wood_front_dark")
    n = 5
    for k in range(n):
        y0, y1 = 0.01 + k * (hb - 0.01) / n, 0.01 + (k + 1) * (hb - 0.01) / n
        role = "worktop_wood" if k % 2 == 0 else "wood_front"
        inset = 0.0 if k % 2 == 0 else 0.004
        for lo, hi in (((-hx + inset, y0, -hz + inset), (hx - inset, y1, -hz + 0.012)),
                       ((-hx + inset, y0, hz - 0.012), (hx - inset, y1, hz - inset)),
                       ((-hx + inset, y0, -hz + 0.012), (-hx + 0.012, y1, hz - 0.012)),
                       ((hx - 0.012, y0, -hz + 0.012), (hx - inset, y1, hz - 0.012))):
            box(m, lo, hi, role, "+x-x+y+z-z")
    box(m, (-hx + 0.02, hb - 0.03, -hz + 0.02), (hx - 0.02, hb, hz - 0.02), "throw_cream", "+y")
    for dx, y0, y1 in ((0.0, hb, hb + 0.07), (0.02, hb + 0.07, hb + 0.13)):
        box(m, (-hx + 0.04 + dx, y0, -hz + 0.035), (hx - 0.05 + dx, y1, hz - 0.01), "throw_cream", "+x-x+z-z")
    cushion(m, (-hx + 0.025, hb + 0.13, -hz + 0.035), (hx - 0.065, H, hz - 0.01), "throw_cream", 0.025)
    cushion(m, (-hx + 0.08, hb * 0.35, hz - 0.012), (hx - 0.1, hb + 0.02, hz), "throw_cream", 0.004)


def build_candle_pair(m, s, R, prm, rng):
    """Two brass candlesticks of different heights with cream taper candles."""
    L, W, H = s
    for x, h in ((-L / 2 + 0.05, H - 0.004), (L / 2 - 0.05, H * 0.8)):
        stick = h - 0.16
        cyl(m, "y", (x, 0.0), 0.045, 0.0, 0.012, "steel_warm", 12)
        cyl(m, "y", (x, 0.0), 0.03, 0.012, 0.03, "steel_warm", 12, r1=0.012, caps=(False, False))
        cyl(m, "y", (x, 0.0), 0.009, 0.03, stick - 0.02, "steel_warm", 6)
        cyl(m, "y", (x, 0.0), 0.012, stick - 0.04, stick - 0.03, "steel_warm", 8)
        cyl(m, "y", (x, 0.0), 0.012, stick - 0.02, stick, "steel_warm", 10, r1=0.022)
        cyl(m, "y", (x, 0.0), 0.011, stick, h - 0.008, "enamel_cream", 8, r1=0.009)
        cyl(m, "y", (x, 0.0), 0.002, h - 0.008, h, "steel_black", 3)


# ---- The living room's round 2 (#150): plants, a table lamp, the games console, games, slippers, a laptop, ceramics,
# books, candles and framed art (the art drawn as flat painted shapes: no image texture, no outside picture).

def _leaf(m: Mesh, x: float, y: float, z: float, size: float, role: str, n: int = 6, k: int = 3) -> None:
    """A leaf as a flat ellipsoid, long along the way it points out from the stem (x or z)."""
    long_x = abs(x) >= abs(z)
    blob(m, (x, y, z), size if long_x else size * 0.55, size * 0.22, size * 0.55 if long_x else size, role, n, k)


def build_house_plant(m, s, R, prm, rng):
    """A potted house plant: a tapered ceramic pot (`pot`) with soil, stems and a crown of leaves in two greens; with
    `tall` a fiddle-leaf fig: a trunk with leaves all the way up. A tall plant's collider is its pot."""
    L, W, H = s
    r = min(L, W) / 2
    pot = prm.get("pot", "enamel_white")
    tall = bool(prm.get("tall"))
    ph = H * (0.28 if tall else 0.36)
    pr = r * (0.55 if tall else 0.62)
    cyl(m, "y", (0.0, 0.0), pr * 0.78, 0.0, ph, pot, 12, r1=pr, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), pr * 0.97, ph - 0.004, ph - 0.004, "soil_dark", 12, caps=(False, True))
    n = int(prm.get("leaves", 12 if tall else 7))
    size = r * (0.42 if tall else 0.5)
    if tall:
        rod(m, (0.0, ph - 0.02, 0.0), (0.02, H * 0.9, -0.01), 0.012, "wood_front_dark", 5)
    for i in range(n):
        a = i * math.pi / 2 + 0.3 * (i // 4 - 1) if tall else i * 2.39996 + rng.random() * 0.3
        t = (i + 1) / n
        y = ph + (H - ph - size * 0.3) * (0.25 + 0.75 * t if tall else 0.45 + 0.55 * rng.random())
        d = (r - size) * ((0.92 + 0.08 * rng.random()) if tall else (0.85 + 0.15 * rng.random()))
        x, z = math.cos(a) * d, math.sin(a) * d
        if not tall:
            rod(m, (0.0, ph, 0.0), (x * 0.7, y, z * 0.7), 0.004, "leaf_dark", 4)
        _leaf(m, x, y, z, size, "leaf_green" if i % 3 else "leaf_dark", 8)
    if tall:
        _boxes(prm).append(((-pr, 0.0, -pr), (pr, ph, pr)))


def build_side_lamp(m, s, R, prm, rng):
    """A table lamp: a round glazed ceramic base (`base`), a brass neck and a linen drum shade."""
    L, W, H = s
    r = min(L, W) / 2
    base = prm.get("base", "book_teal")
    cyl(m, "y", (0.0, 0.0), r * 0.42, 0.0, 0.012, "steel_warm", 12)
    blob(m, (0.0, 0.012 + H * 0.2, 0.0), r * 0.55, H * 0.2, r * 0.55, base, 10, 5)
    cyl(m, "y", (0.0, 0.0), 0.012, 0.012 + H * 0.38, H * 0.6, "steel_warm", 6)
    sy = H * 0.56
    cyl(m, "y", (0.0, 0.0), r, sy, H, "upholstery_light", 16, r1=r * 0.72, caps=(False, False))
    cyl(m, "y", (0.0, 0.0), r * 0.98, sy, H, "throw_cream", 16, r1=r * 0.7, caps=(False, False), flip=True)


def build_game_console(m, s, R, prm, rng):
    """A present-day games console lying flat (white shell, black core, a blue light) with two controllers beside
    it, one white, one black."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    cx1 = hx - 0.01
    cx0 = cx1 - 0.3
    cbox(m, (cx0, 0.0, -hz), (cx1, H * 0.8, hz - 0.12), "enamel_white", 0.008)
    box(m, (cx0 + 0.02, H * 0.3, hz - 0.12), (cx1 - 0.02, H * 0.5, hz - 0.118), "rubber_black", "+z")
    box(m, (cx0 + 0.03, H * 0.5, hz - 0.12), (cx0 + 0.07, H * 0.56, hz - 0.1185), "paint_blue", "+z")
    for k, (body, grip) in enumerate((("enamel_white", "rubber_black"), ("rubber_black", "steel_black"))):
        x = -hx + 0.09 + k * 0.17
        z = hz - 0.06 + (0.01 if k else 0.0)
        cbox(m, (x - 0.055, 0.0, z - 0.03), (x + 0.055, 0.03, z + 0.025), body, 0.008)
        for sx in (-1, 1):
            blob(m, (x + sx * 0.05, 0.016, z + 0.025), 0.025, 0.016, 0.03, body, 6, 3)
        for sx in (-1, 1):
            cyl(m, "y", (x + sx * 0.022, z + 0.008), 0.008, 0.03, 0.036, grip, 6)
        box(m, (x - 0.012, 0.03, z - 0.02), (x + 0.012, 0.031, z - 0.008), "paint_blue", "+y")


def build_board_games(m, s, R, prm, rng):
    """A stack of board-game boxes: white boxes under coloured lids, each with a band across its top and side."""
    L, W, H = s
    lids = [r for r in ("paint_red", "book_navy", "book_mustard", "book_teal", "paint_blue") if r in R] or ["paint_red"]
    n = int(prm.get("boxes", 3))
    t = H / n
    y = 0.0
    for k in range(n):
        f = 1.0 - 0.12 * k * rng.random()
        hx, hz = L / 2 * f - 0.005 * k, W / 2 * f
        dx, dz = (rng.random() - 0.5) * 0.01, (rng.random() - 0.5) * 0.01
        lid, band = lids[(k + 1) % len(lids)], lids[(k + 2) % len(lids)]
        box(m, (dx - hx, y, dz - hz), (dx + hx, y + t * 0.3, dz + hz), "art_white", "+x-x-y+z-z")
        cbox(m, (dx - hx, y + t * 0.3, dz - hz), (dx + hx, y + t - 0.001, dz + hz), lid, 0.003)
        box(m, (dx - hx * 0.6, y + t - 0.001, dz - hz), (dx - hx * 0.2, y + t, dz + hz), band, "+y")
        box(m, (dx - hx * 0.6, y + t * 0.3, dz + hz), (dx - hx * 0.2, y + t - 0.001, dz + hz + 0.0008), band, "+z")
        y += t


def build_slippers(m, s, R, prm, rng):
    """A pair of felt slippers side by side, the left one a little ahead: soles, a closed toe, a soft heel."""
    L, W, H = s
    upper = prm.get("upper", "cushion_teal")
    for k, sx in enumerate((-1, 1)):
        x = sx * L / 4
        z0, z1 = -W / 2 + (0.0 if k else 0.025), W / 2 - (0.025 if k else 0.0)
        w = L / 2 - 0.02
        cushion(m, (x - w / 2, 0.0, z0), (x + w / 2, 0.022, z1), "throw_cream", 0.008)
        cushion(m, (x - w / 2 + 0.004, 0.02, z1 - (z1 - z0) * 0.55), (x + w / 2 - 0.004, H, z1 - 0.004), upper, 0.025)
        cushion(m, (x - w / 2 + 0.006, 0.02, z0 + 0.004), (x + w / 2 - 0.006, H * 0.55, z0 + 0.03), upper, 0.01)


def build_laptop(m, s, R, prm, rng):
    """A closed laptop in warm aluminium with a tablet lying on it, its dark screen up."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    cbox(m, (-hx, 0.0, -hz), (hx, H * 0.45, hz), "steel_warm", 0.004)
    box(m, (-hx + 0.01, H * 0.2, hz), (hx - 0.01, H * 0.24, hz + 0.0008), "steel_black", "+z")
    tx0, tz0 = -hx + 0.06, -hz + 0.035
    cbox(m, (tx0, H * 0.45, tz0), (tx0 + L * 0.68, H - 0.0006, tz0 + W * 0.75), "rubber_black", 0.003)
    box(m, (tx0 + 0.008, H - 0.0006, tz0 + 0.008), (tx0 + L * 0.68 - 0.008, H, tz0 + W * 0.75 - 0.008),
        "glass_dark", "+y")


def build_ceramic(m, s, R, prm, rng):
    """Stoneware for a shelf or a table: `kind` vase (a bellied vase with dried grass stems and seed heads) or bowl
    (a wide glazed bowl with three wooden balls)."""
    L, W, H = s
    r = min(L, W) / 2
    body = prm.get("body", "stone_dark")
    glaze = prm.get("glaze", "book_mustard")
    if prm.get("kind", "vase") == "bowl":
        cyl(m, "y", (0.0, 0.0), r * 0.45, 0.0, H * 0.75, body, 14, r1=r, caps=(True, False))
        cyl(m, "y", (0.0, 0.0), r * 0.4, 0.012, H * 0.75, glaze, 14, r1=r * 0.95, caps=(True, False), flip=True)
        for k in range(3):
            a = k * 2.1 + 0.3
            blob(m, (math.cos(a) * r * 0.3, H * 0.62, math.sin(a) * r * 0.3), r * 0.24, r * 0.24, r * 0.24,
                 "worktop_wood", 8, 4)
        return
    vh = H * 0.5
    cyl(m, "y", (0.0, 0.0), r * 0.55, 0.0, vh * 0.45, body, 12, r1=r * 0.68, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), r * 0.68, vh * 0.45, vh * 0.85, body, 12, r1=r * 0.3, caps=(False, False))
    cyl(m, "y", (0.0, 0.0), r * 0.3, vh * 0.85, vh, glaze, 12, r1=r * 0.34, caps=(False, True))
    for k in range(5):
        a = k * 2 * math.pi / 5 + rng.random() * 0.3
        d = r * (0.8 + 0.15 * rng.random()) - 0.014
        top = (math.cos(a) * d, H * (0.82 + 0.15 * rng.random()), math.sin(a) * d)
        rod(m, (0.0, vh * 0.9, 0.0), top, 0.003, "worktop_wood", 4)
        blob(m, (top[0], top[1] - 0.02, top[2]), 0.014, 0.035, 0.014, "throw_cream", 5, 3)


def build_coffee_books(m, s, R, prm, rng):
    """Three large hardcover books stacked a little askew (cream page blocks inset in their covers), a small brass
    dish on top."""
    L, W, H = s
    covers = [r for r in R if r.startswith("book_") and r != "book_cream"] or ["book_navy"]
    n = 3
    t = (H - 0.012) / n
    y = 0.0
    for k in range(n):
        f = 1.0 - 0.1 * k
        hx, hz = L / 2 * f, W / 2 * f
        dx = (rng.random() - 0.5) * 0.03
        c = covers[(k * 2 + 1) % len(covers)]
        box(m, (dx - hx, y, -hz), (dx + hx, y + 0.004, hz), c)
        box(m, (dx - hx + 0.004, y + 0.004, -hz + 0.004), (dx + hx - 0.006, y + t - 0.004, hz - 0.004), "book_cream",
            "+x+z-z")
        box(m, (dx - hx, y + 0.004, -hz), (dx - hx + 0.004, y + t - 0.004, hz), c, "-x+z-z")
        box(m, (dx - hx, y + t - 0.004, -hz), (dx + hx, y + t, hz), c, "+y+x-x+z-z")
        y += t
    cyl(m, "y", (0.0, 0.0), 0.035, y, H, "steel_warm", 12, r1=0.05)


def build_candle_jars(m, s, R, prm, rng):
    """Three scented candles in stoneware jars of different heights, cream wax and a black wick each."""
    L, W, H = s
    r = min(W / 2, L / 6) - 0.004
    for k, f in enumerate((1.0, 0.72, 0.85)):
        x = -L / 2 + r + 0.004 + k * (L - 2 * r - 0.008) / 2
        h = H * f
        jar = ("stone_light", "stone_dark", "stone_light")[k]
        cyl(m, "y", (x, 0.0), r, 0.0, h - 0.012, jar, 10, caps=(True, False))
        cyl(m, "y", (x, 0.0), r * 0.86, h - 0.016, h - 0.016, "enamel_cream", 10, caps=(False, True))
        tube(m, "y", (x, 0.0), r * 0.86, r, h - 0.012, h - 0.002, jar, 10)
        cyl(m, "y", (x, 0.0), 0.0018, h - 0.016, h - 0.006, "steel_black", 3)


def _art(m: Mesh, kind: str, x0: float, x1: float, y0: float, y1: float, z: float, rng: random.Random) -> None:
    """The picture inside a frame, drawn as flat painted shapes in layers toward +z: `kind` abstract (mid-century
    shapes), city (a skyline poster at sunset), photos (a grid of six holiday photos), score (a game night's score
    sheet with tallies and the winner ringed) or burger (the House kitchen's burger poster)."""
    w, h = x1 - x0, y1 - y0
    zz = [z]

    step = 0.0003  # one layer in front of the last; shapes that never overlap share a layer (lay=False)

    def q(a, b, c, d, role, lay=True):
        zz[0] += step if lay else 0.0
        box(m, (x0 + a * w, y0 + b * h, zz[0] - step), (x0 + c * w, y0 + d * h, zz[0]), role, "+z")

    def disk(cx, cy, r, role, n=14):  # r in metres
        zz[0] += step
        cyl(m, "z", (x0 + cx * w, y0 + cy * h), r, zz[0] - step, zz[0], role, n, caps=(False, True))

    if kind == "abstract":
        q(0, 0, 1, 1, "art_white")
        disk(0.33, 0.58, 0.27 * h, "book_mustard", 20)
        q(0.5, 0.0, 0.78, 0.5, "art_terracotta")
        disk(0.64, 0.5, 0.14 * w, "art_terracotta", 20)
        q(0.08, 0.12, 0.42, 0.2, "book_navy")
        disk(0.86, 0.8, 0.08 * h, "book_teal", 14)
        q(0.84, 0.08, 0.9, 0.6, "book_sage")
    elif kind == "city":
        q(0, 0, 1, 1, "art_sky")
        q(0, 0.14, 1, 0.55, "art_pink")
        disk(0.68, 0.55, 0.14 * h, "book_mustard", 16)
        x, lit = 0.04, []
        zz[0] += step
        while x < 0.92:
            bw = 0.06 + 0.05 * rng.random()
            bh = 0.3 + 0.42 * rng.random()
            q(x, 0.14, min(x + bw, 0.96), 0.14 + bh, rng.choice(["book_navy", "book_teal", "book_grey"]), False)
            lit += [(x + 0.015 + (bw - 0.04) * rng.random(), 0.2 + (bh - 0.1) * rng.random()) for _ in range(2)]
            x += bw + 0.01
        zz[0] += step
        for wx, wy in lit:
            q(wx, wy, wx + 0.015, wy + 0.025, "book_mustard", False)
        q(0, 0, 1, 0.14, "art_white")
        q(0.08, 0.05, 0.55, 0.09, "book_navy")
        q(0.62, 0.05, 0.9, 0.08, "book_grey")
    elif kind == "photos":
        q(0, 0, 1, 1, "art_white")
        skies, grounds = ["art_sky", "art_pink", "book_cream"], ["leaf_green", "book_sage", "art_terracotta", "book_navy"]
        for i in range(3):
            for j in range(2):
                a, b = 0.05 + i * 0.32, 0.07 + j * 0.47
                q(a, b, a + 0.26, b + 0.4, rng.choice(skies))
                q(a, b, a + 0.26, b + 0.17, rng.choice(grounds))
                disk(a + 0.06 + 0.14 * rng.random(), b + 0.28, 0.035 * h, rng.choice(["book_mustard", "art_white"]), 8)
    elif kind == "score":
        q(0, 0, 1, 1, "art_white")
        q(0, 0.84, 1, 1, "paint_red")
        q(0.08, 0.89, 0.5, 0.95, "art_white")
        zz[0] += step
        for c in (0.3, 0.53, 0.76):
            q(c - 0.004, 0.06, c + 0.004, 0.84, "book_grey", False)
        for r in range(5):
            y = 0.2 + r * 0.13
            q(0.04, y - 0.003, 0.96, y + 0.003, "book_grey", False)
            q(0.06, y + 0.03, 0.22, y + 0.07, "book_navy", False)
            for c in (0.3, 0.53, 0.76):
                for k in range(1 + int(rng.random() * 4)):
                    q(c + 0.03 + k * 0.03, y + 0.02, c + 0.037 + k * 0.03, y + 0.1, "steel_black", False)
        zz[0] += step
        tube(m, "z", (x0 + 0.65 * w, y0 + 0.73 * h), 0.06 * h, 0.075 * h, zz[0] - step, zz[0], "paint_red", 14)
    elif kind == "still_life":  # #153: a mid-century still-life print: a jug, a bottle, a bowl of lemons on a table
        q(0, 0, 1, 1, "book_cream")
        q(0, 0, 1, 0.3, "book_navy")
        q(0, 0.3, 1, 0.33, "art_terracotta")
        q(0.12, 0.33, 0.34, 0.7, "book_teal")
        disk(0.23, 0.7, 0.11 * w, "book_teal", 18)
        q(0.33, 0.48, 0.38, 0.62, "book_teal")
        q(0.16, 0.4, 0.3, 0.43, "art_white", False)
        q(0.44, 0.33, 0.52, 0.78, "book_sage")
        q(0.465, 0.78, 0.495, 0.9, "book_sage")
        q(0.455, 0.5, 0.505, 0.6, "art_white")
        disk(0.74, 0.36, 0.17 * w, "art_white", 20)
        q(0.56, 0.2, 0.92, 0.36, "book_navy")
        for cx, cy in ((0.66, 0.42), (0.75, 0.44), (0.84, 0.42), (0.7, 0.5), (0.8, 0.5)):
            disk(cx, cy, 0.045 * w, "book_mustard", 12)
        q(0.62, 0.36, 0.86, 0.38, "art_white")
        disk(0.86, 0.82, 0.07 * h, "art_pink", 14)
    elif kind == "delivery":  # #153: the House's street map with a delivery route dotted to the door and a pin
        q(0, 0, 1, 1, "art_white")
        q(0, 0.86, 1, 1, "book_navy")
        q(0.08, 0.9, 0.6, 0.95, "art_white", False)
        q(0.7, 0.9, 0.92, 0.94, "book_mustard", False)
        q(0.06, 0.52, 0.42, 0.8, "book_sage")
        q(0.58, 0.06, 0.94, 0.3, "book_sage", False)
        q(0, 0.36, 1, 0.42, "art_sky")
        zz[0] += step
        for c in (0.18, 0.5, 0.8):
            q(c - 0.012, 0.0, c + 0.012, 0.86, "book_grey", False)
        for r in (0.22, 0.62):
            q(0.0, r - 0.01, 1.0, r + 0.01, "book_grey", False)
        zz[0] += step
        pts = [(0.18, 0.06), (0.18, 0.22), (0.5, 0.22), (0.5, 0.62), (0.8, 0.62), (0.8, 0.74)]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(2, int((abs(bx - ax) * w + abs(by - ay) * h) / 0.03))
            for k in range(n):
                t = k / n
                px, py = ax + (bx - ax) * t, ay + (by - ay) * t
                q(px - 0.008, py - 0.006, px + 0.008, py + 0.006, "paint_red", False)
        disk(0.8, 0.78, 0.04 * w, "paint_red", 14)
        disk(0.8, 0.78, 0.016 * w, "art_white", 10)
        q(0.66, 0.66, 0.74, 0.72, "art_bun")
    elif kind == "gazebo":  # #153: a strip of four photos from the yard's photo gazebo: plasticine people posing
        q(0, 0, 1, 1, "art_white")
        backs = ("art_sky", "art_pink", "book_mustard", "book_sage")
        heads = ("art_bun", "art_pink", "book_cream", "art_terracotta")
        for i in range(4):
            b0 = 0.03 + (3 - i) * 0.24
            q(0.08, b0, 0.92, b0 + 0.21, backs[i])
            for j, cx in enumerate((0.3, 0.7) if i != 2 else (0.25, 0.5, 0.75)):
                body = ("book_navy", "paint_red", "book_teal", "art_terracotta")[(i + j) % 4]
                q(cx - 0.12, b0, cx + 0.12, b0 + 0.08 + 0.02 * (j % 2), body, False)
                disk(cx, b0 + 0.13 + 0.01 * ((i + j) % 2), 0.13 * w, heads[(i + j) % 4], 10)
            if i == 1:  # someone holds up a burger
                disk(0.5, b0 + 0.17, 0.07 * w, "art_patty", 10)
    elif kind == "blueprint":  # #156: the House's generator as a blueprint: grid, outlines, wheels, dimensions, title
        q(0, 0, 1, 1, "blueprint_blue")
        zz[0] += step
        for i in range(1, 10):
            q(i / 10 - 0.0015, 0, i / 10 + 0.0015, 1, "art_sky", False)
            q(0, i / 10 - 0.002, 1, i / 10 + 0.002, "art_sky", False)
        zz[0] += step
        t = 0.006

        def rect(a, b, c, d):  # an outline
            q(a, b, c, b + t, "art_white", False)
            q(a, d - t, c, d, "art_white", False)
            q(a, b + t, a + t * h / w, d - t, "art_white", False)
            q(c - t * h / w, b + t, c, d - t, "art_white", False)

        rect(0.15, 0.3, 0.65, 0.62)  # the body
        rect(0.22, 0.62, 0.55, 0.74)  # the fuel tank
        q(0.47, 0.74, 0.52, 0.78, "art_white", False)  # its cap
        rect(0.45, 0.38, 0.6, 0.55)  # the panel
        for cx in (0.49, 0.56):
            q(cx - 0.015, 0.42, cx + 0.015, 0.46, "art_white", False)
        q(0.5, 0.49, 0.55, 0.52, "book_mustard", False)  # the spark mark
        for x in (0.11, 0.69):  # the frame's tubes
            q(x - t * h / w / 2, 0.2, x + t * h / w / 2, 0.68, "art_white", False)
        q(0.11, 0.68 - t, 0.69, 0.68, "art_white", False)
        q(0.12, 0.08, 0.68, 0.08 + t / 2, "art_white", False)  # the dimension lines with their ticks
        q(0.765, 0.3, 0.765 + t * h / w / 2, 0.74, "art_white", False)
        for a in (0.12, 0.68):
            q(a - 0.002, 0.06, a + 0.002, 0.1, "art_white", False)
        for b in (0.3, 0.74):
            q(0.75, b - 0.002, 0.78, b + 0.002, "art_white", False)
        rect(0.72, 0.03, 0.97, 0.17)  # the title block
        q(0.74, 0.12, 0.93, 0.14, "art_white", False)
        q(0.74, 0.07, 0.86, 0.085, "art_white", False)
        q(0.05, 0.88, 0.5, 0.93, "art_white", False)  # the heading
        q(0.05, 0.84, 0.3, 0.86, "art_white", False)
        for cx, cy, r in ((0.24, 0.2, 0.07), (0.56, 0.2, 0.07), (0.3, 0.46, 0.09)):  # the wheels, the engine
            tube(m, "z", (x0 + cx * w, y0 + cy * h), r * h - 0.004, r * h, zz[0] - step, zz[0], "art_white", 12)
    elif kind == "calendar":  # #156: a wall calendar: the month's picture (a burger), the month bar, days marked
        q(0, 0, 1, 1, "art_white")
        q(0.05, 0.56, 0.95, 0.95, "art_sky")
        disk(0.5, 0.74, 0.2 * w, "art_bun", 18)
        q(0.24, 0.7, 0.76, 0.73, "leaf_green")
        q(0.25, 0.655, 0.75, 0.7, "art_patty")
        q(0.27, 0.6, 0.73, 0.655, "art_bun")
        q(0.05, 0.47, 0.95, 0.52, "paint_red")
        q(0.1, 0.485, 0.4, 0.505, "art_white", False)
        zz[0] += step
        for r in range(5):
            for c in range(7):
                x, y = 0.07 + c * 0.125, 0.05 + (4 - r) * 0.08
                q(x, y, x + 0.1, y + 0.06, "book_cream", False)
        zz[0] += step
        for (c, r), role in (((5, 1), "book_mustard"), ((2, 3), "art_sky"), ((6, 3), "leaf_green")):
            x, y = 0.07 + c * 0.125, 0.05 + (4 - r) * 0.08
            q(x + 0.01, y + 0.01, x + 0.09, y + 0.05, role, False)
        x, y = 0.07 + 3 * 0.125, 0.05 + 2 * 0.08
        tube(m, "z", (x0 + (x + 0.05) * w, y0 + (y + 0.03) * h), 0.045 * w, 0.06 * w, zz[0], zz[0] + step,
             "paint_red", 12)
        zz[0] += step
    elif kind == "family":  # #156: a family portrait: two to four plasticine people, heads and shoulders, bead eyes
        q(0, 0, 1, 1, rng.choice(("art_sky", "book_sage", "art_pink", "book_cream")))
        n = 2 + int(rng.random() * 3)
        k0 = int(rng.random() * 5)
        bodies = ("book_navy", "paint_red", "book_teal", "book_mustard", "art_terracotta")
        heads = ("art_bun", "art_pink", "book_cream", "art_terracotta")
        lift = [0.08 * ((j + k0) % 2) for j in range(n)]
        zz[0] += step
        for j in range(n):
            cx, bw = (j + 0.5) / n, 0.36 / n + 0.04
            q(cx - bw, 0, cx + bw, 0.28 + lift[j], bodies[(j + k0) % 5], False)
        for j in range(n):
            disk((j + 0.5) / n, 0.44 + lift[j], (0.11 if n > 2 else 0.15) * min(w, h), heads[(j + k0) % 4], 12)
        zz[0] += step
        for j in range(n):
            cx, cy = (j + 0.5) / n, 0.46 + lift[j]
            for dx in (-0.035, 0.035):
                q(cx + dx - 0.01, cy - 0.01, cx + dx + 0.01, cy + 0.01, "steel_black", False)
    elif kind == "wash":  # #158: the WC's joke print: a plasticine person scrubbing up in suds, rated five stars
        q(0, 0, 1, 1, "art_sky")
        q(0.08, 0.05, 0.92, 0.2, "art_white")
        for k in range(5):
            disk(0.18 + 0.16 * k, 0.125, 0.05 * w, "book_mustard", 10)
        q(0.28, 0.22, 0.72, 0.46, "book_teal")
        disk(0.5, 0.58, 0.16 * min(w, h), "art_pink", 16)
        zz[0] += step
        for dx in (-0.06, 0.06):
            q(0.5 + dx - 0.015, 0.6 - 0.015, 0.5 + dx + 0.015, 0.6 + 0.015, "steel_black", False)
        q(0.45, 0.51, 0.55, 0.53, "art_terracotta", False)
        for cx, cy, r in ((0.18, 0.4, 0.09), (0.82, 0.44, 0.1), (0.26, 0.8, 0.07), (0.74, 0.8, 0.08),
                          (0.12, 0.6, 0.05), (0.88, 0.64, 0.06), (0.5, 0.86, 0.05)):
            disk(cx, cy, r * w, "art_white", 12)
        q(0.6, 0.27, 0.84, 0.36, "book_sage")
    elif kind == "bubbles":  # #162: the bathroom's joke print: a plasticine person deep in bubbles, a duck on watch
        q(0, 0, 1, 1, "book_teal")
        q(0.06, 0.06, 0.94, 0.94, "art_sky")
        q(0.78, 0.7, 0.84, 0.94, "steel_black")
        q(0.7, 0.66, 0.88, 0.7, "steel_black")
        for k in range(4):
            q(0.72 + 0.04 * k, 0.5 + 0.03 * (k % 2), 0.735 + 0.04 * k, 0.62, "art_white", False)
        disk(0.4, 0.5, 0.13 * min(w, h), "art_pink", 16)
        zz[0] += step
        for dx in (-0.05, 0.05):
            q(0.4 + dx - 0.014, 0.53 - 0.014, 0.4 + dx + 0.014, 0.53 + 0.014, "steel_black", False)
        q(0.36, 0.44, 0.44, 0.46, "art_terracotta", False)
        q(0.1, 0.12, 0.9, 0.36, "art_white")
        q(0.14, 0.06, 0.18, 0.12, "steel_black", False)
        q(0.82, 0.06, 0.86, 0.12, "steel_black", False)
        for cx, cy, r in ((0.16, 0.38, 0.07), (0.3, 0.4, 0.08), (0.52, 0.39, 0.07), (0.62, 0.42, 0.06),
                          (0.22, 0.48, 0.05), (0.58, 0.55, 0.04), (0.12, 0.6, 0.03), (0.66, 0.3, 0.05)):
            disk(cx, cy, r * w, "art_white", 12)
        disk(0.76, 0.42, 0.06 * w, "book_mustard", 12)
        disk(0.8, 0.48, 0.04 * w, "book_mustard", 12)
        q(0.835, 0.465, 0.87, 0.485, "art_terracotta")
        q(0.2, 0.18, 0.8, 0.22, "book_sage")
    elif kind == "rocket":  # #166: a kids' room poster: a rocket climbing past a ringed planet into the stars
        q(0, 0, 1, 1, "book_navy")
        for k in range(14):
            sx, sy = rng.random() * 0.9 + 0.03, rng.random() * 0.9 + 0.05
            q(sx, sy, sx + 0.018, sy + 0.012, "art_white", False)
        disk(0.76, 0.78, 0.13 * w, "book_mustard", 18)
        q(0.56, 0.765, 0.96, 0.795, "art_terracotta")
        disk(0.5, 0.12, 0.09 * w, "book_mustard", 12)
        disk(0.5, 0.15, 0.055 * w, "paint_red", 12)
        q(0.4, 0.2, 0.6, 0.6, "art_white")
        for k, (a, b) in enumerate(((0.42, 0.58), (0.44, 0.56), (0.465, 0.535))):
            q(a, 0.6 + 0.05 * k, b, 0.65 + 0.05 * k, "paint_red" if k else "art_white")
        q(0.3, 0.2, 0.4, 0.32, "paint_red", False)
        q(0.6, 0.2, 0.7, 0.32, "paint_red", False)
        disk(0.5, 0.46, 0.06 * w, "art_sky", 14)
        q(0.4, 0.26, 0.6, 0.28, "paint_red")
    elif kind == "dino":  # #166: a kids' room poster: a friendly long-necked dinosaur under the sun, a volcano behind
        q(0, 0, 1, 1, "art_sky")
        disk(0.82, 0.8, 0.09 * w, "book_mustard", 16)
        for k, (a, b) in enumerate(((0.05, 0.4), (0.1, 0.35), (0.15, 0.3))):
            q(a, 0.25 + 0.12 * k, b, 0.37 + 0.12 * k, "book_grey" if k < 2 else "art_terracotta")
        q(0, 0, 1, 0.26, "leaf_green")
        disk(0.55, 0.36, 0.17 * w, "book_teal", 20)
        q(0.42, 0.14, 0.48, 0.32, "book_teal", False)
        q(0.62, 0.14, 0.68, 0.32, "book_teal", False)
        q(0.66, 0.38, 0.74, 0.62, "book_teal", False)
        q(0.66, 0.6, 0.84, 0.68, "book_teal", False)
        q(0.22, 0.3, 0.42, 0.36, "book_teal", False)
        q(0.14, 0.27, 0.24, 0.31, "book_teal", False)
        for k in range(5):
            q(0.44 + 0.05 * k, 0.5 + 0.012 * (2 - abs(k - 2)), 0.47 + 0.05 * k, 0.55 + 0.012 * (2 - abs(k - 2)),
              "book_mustard", False)
        zz[0] += step
        q(0.78, 0.635, 0.8, 0.655, "steel_black", False)
        q(0.74, 0.61, 0.82, 0.62, "art_terracotta", False)
    elif kind == "drawing":  # #166: a child's crayon drawing: a sun, a house or a burger, plasticine people, grass
        q(0, 0, 1, 1, "art_white")
        disk(0.15, 0.8, 0.08 * w, "book_mustard", 12)
        for a, b, c, d in ((0.04, 0.78, 0.07, 0.82), (0.23, 0.78, 0.26, 0.82), (0.13, 0.62, 0.17, 0.66),
                           (0.13, 0.94, 0.17, 0.98)):
            q(a, b, c, d, "book_mustard", False)
        q(0, 0, 1, 0.12, "leaf_green")
        if rng.random() < 0.5:
            q(0.38, 0.12, 0.68, 0.42, "book_red")
            for k in range(4):
                q(0.35 + 0.04 * k, 0.42 + 0.06 * k, 0.71 - 0.04 * k, 0.48 + 0.06 * k, "book_navy", False)
            q(0.49, 0.12, 0.57, 0.28, "wood_front_dark", False)
            q(0.41, 0.28, 0.47, 0.36, "art_sky", False)
            q(0.59, 0.28, 0.65, 0.36, "art_sky", False)
        else:
            q(0.36, 0.42, 0.7, 0.62, "art_bun")
            q(0.34, 0.34, 0.72, 0.42, "art_patty")
            q(0.35, 0.31, 0.71, 0.34, "leaf_green")
            q(0.36, 0.22, 0.7, 0.31, "art_bun")
        for k, (cx, body) in enumerate(((0.8, "book_teal"), (0.9, "paint_red"))):
            q(cx - 0.035, 0.12, cx + 0.035, 0.3 - 0.04 * k, body, False)
            disk(cx, 0.36 - 0.04 * k, 0.045 * w, "art_pink", 10)
    elif kind == "certificate":  # #166: a framed certificate: a cream sheet, a title, lines of text, a red seal
        q(0, 0, 1, 1, "book_cream")
        q(0.04, 0.05, 0.96, 0.95, "book_mustard")
        q(0.06, 0.08, 0.94, 0.92, "book_cream")
        q(0.2, 0.74, 0.8, 0.84, "book_navy")
        for k in range(4):
            q(0.18, 0.6 - 0.09 * k, 0.82 - 0.08 * (k % 2), 0.625 - 0.09 * k, "book_grey", False)
        disk(0.78, 0.22, 0.09 * min(w, h), "paint_red", 14)
        q(0.74, 0.08, 0.76, 0.16, "paint_red", False)
        q(0.8, 0.08, 0.82, 0.16, "paint_red", False)
        q(0.14, 0.18, 0.5, 0.195, "steel_black", False)
    else:  # burger
        q(0, 0, 1, 1, "book_navy")
        q(0.15, 0.82, 0.85, 0.9, "art_white")
        q(0.3, 0.75, 0.7, 0.78, "book_mustard")
        disk(0.5, 0.44, 0.33 * w, "art_bun", 20)
        q(0.1, 0.1, 0.9, 0.44, "book_navy")
        q(0.15, 0.4, 0.85, 0.45, "leaf_green")
        q(0.19, 0.35, 0.81, 0.4, "book_mustard")
        q(0.18, 0.26, 0.82, 0.35, "art_patty")
        q(0.2, 0.16, 0.8, 0.26, "art_bun")
        for k in range(5):
            sx, sy = 0.32 + 0.09 * k, 0.55 + 0.06 * ((k * 2) % 3)
            q(sx, sy, sx + 0.025, sy + 0.015, "art_white")
        disk(0.84, 0.66, 0.08 * w, "paint_red", 12)
        q(0.8, 0.645, 0.88, 0.675, "art_white")


def _framed(m: Mesh, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, f: float, mat: float, fr: str,
            kind: str, rng: random.Random) -> None:
    """One frame from (x0, y0) to (x1, y1), its back at z0 and its face at z1: a `fr` frame `f` wide, a white mat
    `mat` wide and the picture `kind` (see _art)."""
    box(m, (x0 + f, y0 + f, z0), (x1 - f, y1 - f, z1 - 0.008), "art_white", "+z")
    for lo, hi in (((x0, y0, z0), (x1, y0 + f, z1)), ((x0, y1 - f, z0), (x1, y1, z1)),
                   ((x0, y0 + f, z0), (x0 + f, y1 - f, z1)), ((x1 - f, y0 + f, z0), (x1, y1 - f, z1))):
        box(m, lo, hi, fr, "+x-x+y-y+z")
    _art(m, kind, x0 + f + mat, x1 - f - mat, y0 + f + mat, y1 - f - mat, z1 - 0.008, rng)


def build_framed_art(m, s, R, prm, rng):
    """A framed picture for the wall (wall pivot: the back at -z): a `frame_paint` frame `frame` wide, a white mat
    `mat` wide and the picture `art` (see _art), drawn by this repo."""
    L, W, H = s
    hx = L / 2
    _framed(m, -hx, hx, 0.0, H, -W / 2, W / 2, float(prm.get("frame", 0.03)), float(prm.get("mat", 0.0)),
            prm.get("frame_paint", "wood_front_dark"), prm.get("art", "abstract"), rng)


# ---- The dining room in the world look (#153): the chairs, the pendant, the display cabinet and its detail layer.

def build_dining_chair(m, s, R, prm, rng):
    """A present-day dining chair: an oak frame (`wood`) of tapered front legs, back legs rising into the back posts,
    rails and low stretchers, a back of a wide top rail and a lower rail with three slats between them, and an
    upholstered seat pad (`seat`). Colliders: the seat and the back."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, seat = prm.get("wood", "worktop_wood"), prm.get("seat", "upholstery")
    ys = 0.42  # the frame's top under the pad
    xl, zb = hx - 0.028, -hz + 0.03
    for sx in (-1, 1):
        leg(m, sx * xl, hz - 0.028, 0.0, ys, 0.02, wood, 0.7, 10)
        rod(m, (sx * xl, 0.0, zb + 0.01), (sx * xl, ys, zb), 0.019, wood, 10)
        rod(m, (sx * xl, ys, zb), (sx * (xl - 0.004), H - 0.012, -hz + 0.02), 0.017, wood, 10)
        box(m, (sx * xl - 0.012, ys - 0.07, zb), (sx * xl + 0.012, ys - 0.005, hz - 0.028), wood, "+x-x-y")
        box(m, (sx * xl - 0.009, 0.16, zb), (sx * xl + 0.009, 0.185, hz - 0.028), wood, "+x-x+y-y")
    box(m, (-xl, ys - 0.07, hz - 0.04), (xl, ys - 0.005, hz - 0.016), wood, "+z-z-y")
    box(m, (-xl, ys - 0.07, zb - 0.012), (xl, ys - 0.005, zb + 0.012), wood, "+z-z-y")
    cushion(m, (-hx + 0.006, ys - 0.005, -hz + 0.05), (hx - 0.006, ys + 0.05, hz - 0.004), seat, 0.02)
    zr = -hz + 0.006
    cbox(m, (-xl + 0.01, H - 0.11, zr), (xl - 0.01, H - 0.02, zr + 0.03), wood, 0.004)
    cbox(m, (-xl + 0.01, ys + 0.15, zr + 0.004), (xl - 0.01, ys + 0.19, zr + 0.028), wood, 0.004)
    for k in (-1, 0, 1):
        x = k * (xl - 0.01) / 2.4
        box(m, (x - 0.017, ys + 0.19, zr + 0.009), (x + 0.017, H - 0.11, zr + 0.023), wood, "+x-x+z-z")
    _boxes(prm).extend([((-hx, 0.0, -hz), (hx, ys + 0.05, hz)), ((-hx, ys, -hz), (hx, H, -hz + 0.06))])


def build_pendant_trio(m, s, R, prm, rng):
    """A present-day pendant over a long table: a slim black steel canopy bar on the ceiling, three drops and three
    domed shades (black outside, warm brass inside) with a warm bulb in each (the light anchor). Ceiling pivot."""
    L, W, H = s
    hx = L / 2
    lamp = R[0]
    cbox(m, (-hx + 0.05, H - 0.03, -0.035), (hx - 0.05, H, 0.035), "steel_black", 0.004)
    r = min(W / 2, (L - 0.1) / 6) - 0.005
    sh = 0.2  # the shade's height
    for k in (-1, 0, 1):
        x = k * (L - 2 * r - 0.02) / 2
        rod(m, (x, sh + 0.04, 0.0), (x, H - 0.03, 0.0), 0.003, "steel_black", 3, caps=False)
        cyl(m, "y", (x, 0.0), 0.022, sh, sh + 0.05, "steel_black", 6, r1=0.016, caps=(False, True))
        cyl(m, "y", (x, 0.0), r, 0.0, sh, "steel_black", 12, r1=r * 0.3, caps=(False, True))
        cyl(m, "y", (x, 0.0), r * 0.97, 0.002, sh - 0.004, "steel_warm", 12, r1=r * 0.28, caps=(False, True),
            flip=True)
        bulb(m, (x, 0.06, 0.0), 0.035, lamp, 0.045)


def build_display_cabinet(m, s, R, prm, rng):
    """A tall display cabinet in the wood fronts: plinth, carcass and top, two panelled doors below, two framed glass
    doors (`glass`) above a dark back: white plates standing in a rail, a stack of bowls and a jug on the lowest
    shelf, stemmed glasses and a decanter above. Collider: the body."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, glass = prm.get("body", "wood_front"), prm.get("glass", "glass_tint")
    t = 0.022
    zf = hz - st.reach - 0.002
    yb = 0.86  # the base's top: the glass doors start here
    plinth(m, st, -hx + t, hx - t, -hz + 0.02, zf - st.plinth_setback, "wood_front_dark")
    for sx in (-1, 1):
        cbox(m, (hx - t if sx > 0 else -hx, 0.0, -hz), (hx if sx > 0 else -hx + t, H - 0.03, zf + st.front_t), body,
             st.bevel_small)
    cbox(m, (-hx, H - 0.03, -hz), (hx, H, zf + st.front_t + 0.01), body, st.bevel_small)
    box(m, (-hx + t, st.plinth, -hz), (hx - t, H - 0.03, -hz + 0.012), "wood_front_dark", "+z")
    cbox(m, (-hx + t, st.plinth, -hz + 0.012), (hx - t, yb, zf), body, st.bevel_small)
    front(m, st, -hx + t, 0.0, st.plinth + 0.004, yb - 0.004, zf, body, True, line="wood_front_dark")
    front(m, st, 0.0, hx - t, st.plinth + 0.004, yb - 0.004, zf, body, False, line="wood_front_dark")
    zi0, zi1 = -hz + 0.012, zf - 0.006  # the glass part's inside
    cbox(m, (-hx + t, yb, zi0), (hx - t, yb + t, zf), body, st.bevel_small)
    n = 3
    step = (H - 0.03 - yb - t) / n
    for i in range(n):
        y = yb + t + step * i
        if i:
            box(m, (-hx + t, y - 0.016, zi0), (hx - t, y, zi1), body, "+y-y+z")
        if i == 0:  # plates standing in a rail at the back, each a little in front of the last, inside the sides
            box(m, (-hx + t, y, zi0 + 0.052), (hx - t, y + 0.012, zi0 + 0.062), "wood_front_dark", "+y+z-z")
            pr = 0.1
            for k in range(6):
                x = -hx + t + pr + 0.01 + k * (L - 2 * t - 2 * pr - 0.02) / 5
                z = zi0 + 0.004 + 0.007 * k
                cyl(m, "z", (x, y + pr + 0.004), pr, z, z + 0.01, "porcelain_white", 14)
            for j in range(3):
                cyl(m, "y", (-hx + 0.2, zi1 - 0.1), 0.05 - 0.003 * j, y + j * 0.03, y + j * 0.03 + 0.028,
                    "enamel_white", 12, r1=0.075 - 0.003 * j)
            cyl(m, "y", (hx - 0.2, zi1 - 0.09), 0.055, y, y + 0.14, "book_teal", 12, r1=0.045)
            cyl(m, "y", (hx - 0.2, zi1 - 0.09), 0.045, y + 0.14, y + 0.18, "book_teal", 12, r1=0.05)
        else:  # stemmed glasses in two rows, on the top shelf a decanter
            for row, zc in enumerate((zi0 + 0.07, zi1 - 0.06)):
                for k in range(4 - row):
                    x = -hx + 0.12 + (k + 0.5 * row) * (L - 0.34) / 3
                    cyl(m, "y", (x, zc), 0.028, y, y + 0.006, "chrome", 8)
                    cyl(m, "y", (x, zc), 0.005, y + 0.006, y + 0.07, "chrome", 4)
                    cyl(m, "y", (x, zc), 0.012, y + 0.07, y + 0.15, "chrome", 8, r1=0.032, caps=(False, False))
            if i == 2:
                cyl(m, "y", (hx - 0.14, zi1 - 0.1), 0.055, y, y + 0.14, "glass_dark", 10, r1=0.06)
                cyl(m, "y", (hx - 0.14, zi1 - 0.1), 0.016, y + 0.14, y + 0.22, "glass_dark", 8)
    front(m, st, -hx + t, 0.0, yb + t + 0.004, H - 0.034, zf, body, True, glass=glass)
    front(m, st, 0.0, hx - t, yb + t + 0.004, H - 0.034, zf, body, False, glass=glass)
    _boxes(prm).append(((-hx, 0.0, -hz), (hx, H, zf + st.front_t)))


# The dining room's detail layer (class clutter): the set table, the sideboard's things, homework and the mail.

def _plate(m: Mesh, x: float, z: float, y: float, r: float, role: str, h: float = 0.022) -> None:
    """A plate: a foot rising into the rim, the well inside it."""
    cyl(m, "y", (x, z), r * 0.62, y, y + h, role, 16, r1=r, caps=(True, False))
    cyl(m, "y", (x, z), r * 0.6, y + h * 0.4, y + h, role, 16, r1=r * 0.94, caps=(True, False), flip=True)


def _tumbler(m: Mesh, x: float, z: float, y: float, r: float, h: float, role: str = "glass_tint") -> None:
    """A drinking glass: a thick base and the open sides, outside and in."""
    cyl(m, "y", (x, z), r * 0.92, y, y + 0.012, role, 12, r1=r * 0.94)
    cyl(m, "y", (x, z), r * 0.94, y + 0.012, y + h, role, 12, r1=r, caps=(False, False))
    cyl(m, "y", (x, z), r * 0.86, y + 0.012, y + h, role, 12, r1=r * 0.92, caps=(False, False), flip=True)


def build_place_setting(m, s, R, prm, rng):
    """One place at the table, its diner at +z: a slate placemat (`mat`), a dinner plate with a side plate on it, a
    folded linen napkin (`napkin`) with a fork on the left, a knife and a spoon on the right, a water glass at the top
    right."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    box(m, (-hx, 0.0, -hz), (hx, 0.004, hz), prm.get("mat", "stone_dark"), "+x-x+y+z-z")
    _plate(m, 0.0, 0.02, 0.004, 0.13, "porcelain_white")
    _plate(m, 0.0, 0.02, 0.022, 0.085, "enamel_white", 0.016)
    cbox(m, (-hx + 0.015, 0.004, -0.07), (-hx + 0.075, 0.016, 0.12), prm.get("napkin", "throw_cream"), 0.003)
    box(m, (-hx + 0.04, 0.016, -0.05), (-hx + 0.05, 0.019, 0.1), "chrome", "+y+x-x+z-z")
    box(m, (-hx + 0.034, 0.016, -0.08), (-hx + 0.056, 0.019, -0.05), "chrome", "+y+x-x+z-z")
    for x, z0, z1 in ((0.155, -0.08, 0.13), (0.19, -0.05, 0.13)):
        box(m, (x - 0.006, 0.004, z0), (x + 0.006, 0.007, z1), "chrome", "+y+x-x+z-z")
    _tumbler(m, hx - 0.045, -hz + 0.04, 0.004, 0.035, H - 0.004)


def build_serving_board(m, s, R, prm, rng):
    """The middle of the table: an oak bread board with a scored loaf and a bread knife, a glass water jug, a salt
    and a pepper mill."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    bx0, bx1 = -hx, -hx + 0.4
    rslab(m, bx0, bx1 - 0.06, 0.0, 0.022, -hz, hz, 0.03, "worktop_wood")
    box(m, (bx1 - 0.062, 0.0, -0.025), (bx1, 0.022, 0.025), "worktop_wood", "+x+y+z-z")
    blob(m, (bx0 + 0.15, 0.022 + 0.05, -0.01), 0.12, 0.055, 0.075, "art_bun", 8, 4, floor=0.022)
    for k in range(3):
        x = bx0 + 0.08 + k * 0.06
        box(m, (x, 0.12, -0.05), (x + 0.012, 0.124, 0.03), "book_cream", "+y")
    box(m, (bx0 + 0.04, 0.022, hz - 0.06), (bx0 + 0.22, 0.025, hz - 0.035), "chrome", "+y+x-x+z-z")
    cbox(m, (bx0 + 0.22, 0.022, hz - 0.064), (bx0 + 0.33, 0.04, hz - 0.03), "wood_front_dark", 0.004)
    jx, jz = hx - 0.09, -0.03
    cyl(m, "y", (jx, jz), 0.07, 0.0, 0.012, "glass_tint", 10, r1=0.07)
    cyl(m, "y", (jx, jz), 0.07, 0.012, H - 0.01, "glass_tint", 10, r1=0.055, caps=(False, False))
    cyl(m, "y", (jx, jz), 0.062, 0.012, H - 0.01, "glass_tint", 10, r1=0.05, caps=(False, False), flip=True)
    box(m, (jx - 0.01, H - 0.035, jz + 0.05), (jx + 0.01, H, jz + 0.075), "glass_tint", "+x-x+y+z")
    for k, role in enumerate(("wood_front_dark", "steel_black")):
        x = hx - 0.22 + k * 0.06
        cyl(m, "y", (x, hz - 0.05), 0.022, 0.0, 0.12, role, 8, r1=0.018, caps=(True, False))
        blob(m, (x, 0.13, hz - 0.05), 0.02, 0.016, 0.02, role, 6, 3)


def build_fruit_dish(m, s, R, prm, rng):
    """A wide stoneware fruit bowl (light outside, white glaze inside) heaped with apples, oranges, pears and a
    bunch of bananas."""
    L, W, H = s
    r = min(L, W) / 2
    hb = H * 0.42
    cyl(m, "y", (0.0, 0.0), r * 0.42, 0.0, hb, "stone_light", 12, r1=r, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), r * 0.38, 0.012, hb, "enamel_white", 12, r1=r * 0.95, caps=(True, False), flip=True)
    fruit = (("paint_red", 0.042), ("art_bun", 0.045), ("leaf_green", 0.04), ("paint_red", 0.042), ("art_bun", 0.045),
             ("leaf_green", 0.04))
    for k, (role, fr) in enumerate(fruit):
        a = k * 2 * math.pi / 5
        d = 0.0 if k == 5 else r * 0.52
        y = hb - 0.01 + (0.03 if k == 5 else 0.0)
        blob(m, (math.cos(a) * d, y, math.sin(a) * d), fr, fr * (1.2 if role == "leaf_green" else 0.95), fr, role,
             6, 4)
    for k in range(3):  # the bananas lie across the top
        z = -0.02 + k * 0.022
        blob(m, (0.02, H - 0.025 - 0.006 * k, z), r * 0.6, 0.017, 0.017, "book_mustard", 6, 3)


def build_flower_vase(m, s, R, prm, rng):
    """Tulips in a glazed ceramic vase (`glaze`): a cylinder vase, green stems, a few long leaves and closed heads in
    pink, red and white."""
    L, W, H = s
    r = min(L, W) / 2
    vh = H * 0.42
    vr = r * 0.42
    cyl(m, "y", (0.0, 0.0), vr, 0.0, vh, prm.get("glaze", "book_teal"), 10, r1=vr * 0.88)
    heads = ("art_pink", "paint_red", "art_white", "art_pink", "paint_red", "art_white")
    for k, role in enumerate(heads):
        a = k * 2.39996 + rng.random() * 0.4
        d = (r - 0.03) * (0.4 + 0.6 * rng.random())
        top = (math.cos(a) * d, H - 0.05 - 0.07 * rng.random(), math.sin(a) * d)
        rod(m, (0.0, vh - 0.02, 0.0), top, 0.003, "leaf_green", 4)
        blob(m, (top[0], top[1] + 0.012, top[2]), 0.022, 0.032, 0.022, role, 6, 3)
    for k in range(4):
        a = k * math.pi / 2 + 0.4
        _leaf(m, math.cos(a) * (r - 0.012) * 0.6, vh + 0.06, math.sin(a) * (r - 0.012) * 0.6, 0.06, "leaf_dark", 6)


def build_wine_rack(m, s, R, prm, rng):
    """A small black steel wine rack on a sideboard: two rows of three bottles lying with their necks out (dark glass,
    cream and white labels, red, black and gold capsules) in the frame's two hoops."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    br = min(L / 6, H / 4) - 0.006
    caps = ("paint_red", "steel_black", "book_mustard")
    for row in range(2):
        y = br + 0.012 + row * (2 * br + 0.012)
        for k in range(3):
            x = -hx + 0.006 + br + k * (L - 0.012 - 2 * br) / 2
            z0, z1 = -hz, hz - 0.1
            cyl(m, "z", (x, y), br, z0, z1, "glass_dark", 8)
            cyl(m, "z", (x, y), br, z1, z1 + 0.04, "glass_dark", 8, r1=br * 0.35, caps=(False, False))
            cyl(m, "z", (x, y), br * 0.35, z1 + 0.04, hz - 0.035, "glass_dark", 6, caps=(False, False))
            cyl(m, "z", (x, y), br * 0.37, hz - 0.035, hz, caps[(k + row) % 3], 6, caps=(False, True))
            cyl(m, "z", (x, y), br * 1.01, z1 - 0.12, z1 - 0.04, "book_cream" if (k + row) % 2 else "art_white", 8,
                caps=(False, False))
    for z in (-hz + 0.04, hz - 0.14):
        box(m, (-hx, 0.0, z - 0.004), (hx, 0.008, z + 0.004), "steel_black", "+y+z-z")
        box(m, (-hx, H - 0.008, z - 0.004), (hx, H, z + 0.004), "steel_black", "+y-y+z-z")
        for x in (-hx, hx - 0.008):
            box(m, (x, 0.0, z - 0.004), (x + 0.008, H, z + 0.004), "steel_black", "+x-x+z-z")


def build_homework(m, s, R, prm, rng):
    """Homework left at the end of the table: an open exercise book with ruled lines and a few written ones, a pencil
    case with pencils beside it, a calculator and an eraser."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    bx0, bz0 = -hx, -hz + 0.02
    for k in range(2):  # the two open pages
        a = bx0 + k * 0.17
        box(m, (a, 0.0, bz0), (a + 0.168, 0.008, bz0 + 0.23), "art_white", "+x-x+y+z-z")
        for j in range(9):
            z = bz0 + 0.03 + j * 0.021
            box(m, (a + 0.012, 0.008, z), (a + 0.156, 0.0082, z + 0.0015), "art_sky", "+y")
            if j < 6 - 3 * k:
                box(m, (a + 0.016, 0.0083, z + 0.004), (a + 0.04 + 0.1 * rng.random(), 0.0085, z + 0.012),
                    "book_navy", "+y")
    box(m, (bx0 + 0.168, 0.0, bz0), (bx0 + 0.172, 0.009, bz0 + 0.23), "paint_red", "+y")
    px = bx0 + 0.37
    cushion(m, (px, 0.0, -hz + 0.03), (px + 0.065, 0.04, -hz + 0.23), "book_navy", 0.015)
    for k, role in enumerate(("book_mustard", "paint_red", "leaf_green")):
        x = px + 0.08 + k * 0.014
        cyl(m, "z", (x, 0.004), 0.004, -hz + 0.04 + k * 0.02, -hz + 0.2, role, 6)
        cyl(m, "z", (x, 0.004), 0.004, -hz + 0.2, -hz + 0.215, "book_cream", 6, r1=0.0005)
    cx = hx - 0.05
    cbox(m, (cx - 0.04, 0.0, hz - 0.15), (cx + 0.04, 0.014, hz - 0.01), "rubber_black", 0.003)
    box(m, (cx - 0.03, 0.014, hz - 0.14), (cx + 0.03, 0.0145, hz - 0.11), "glass_dark", "+y")
    for i in range(4):
        for j in range(4):
            x, z = cx - 0.032 + i * 0.016, hz - 0.1 + j * 0.02
            box(m, (x, 0.014, z), (x + 0.012, 0.0155, z + 0.014), "art_white" if i < 3 else "book_mustard", "+y")
    cbox(m, (bx0 + 0.25, 0.0, hz - 0.05), (bx0 + 0.3, 0.012, hz - 0.025), "art_pink", 0.003)


def build_mail_stack(m, s, R, prm, rng):
    """The day's mail on the sideboard: envelopes laid a little askew with red stamps, and on top a burger place's
    delivery flyer (navy, a bun-coloured burger, a red price disc)."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    y = 0.0
    for k, role in enumerate(("art_white", "book_cream", "art_sky", "art_white")):
        dx = (rng.random() - 0.5) * 0.04
        w, d = hx - 0.012 - 0.01 * k, hz - 0.01 - 0.008 * k
        box(m, (dx - w, y, -d), (dx + w, y + 0.004, d), role, "+x-x+y+z-z")
        box(m, (dx + w * 0.4, y + 0.004, -d + 0.015), (dx + w * 0.75, y + 0.0045, -d + 0.035), "paint_red", "+y")
        y += 0.0045
    box(m, (-hx + 0.03, y, -hz + 0.03), (hx - 0.04, y + 0.002, hz - 0.01), "book_navy", "+x-x+y+z-z")
    yy = y + 0.002
    cyl(m, "y", (-0.03, 0.0), 0.06, yy, yy + 0.0005, "art_bun", 16, caps=(False, True))
    box(m, (-0.09, yy + 0.0005, -0.012), (0.03, yy + 0.001, 0.012), "art_patty", "+y")
    cyl(m, "y", (0.08, -0.05), 0.025, yy, yy + 0.001, "paint_red", 12, caps=(False, True))
    box(m, (-0.11, yy, 0.07), (0.1, yy + 0.0005, 0.085), "art_white", "+y")


# ---- The hallway in the world look (#156): the entrance console under an arched mirror, the coat hooks, the bench,
# the umbrella stand, the shoes, keys, parcels and the sports bag, a row of small frames.

def _shoe(m: Mesh, x: float, y: float, z: float, ln: float, w: float, h: float, upper: str, sole: str,
          accent: str | None = None) -> None:
    """One shoe along z, its toe toward +z: a sole, the upper's heel block, a rounded toe, the dark opening and an
    `accent` heel tab."""
    hl = ln / 2
    box(m, (x - w / 2, y, z - hl), (x + w / 2, y + 0.022, z + hl), sole)
    cushion(m, (x - w / 2 + 0.004, y + 0.02, z - hl + 0.006), (x + w / 2 - 0.004, y + h, z + 0.02), upper, 0.025)
    blob(m, (x, y + 0.02, z + hl * 0.42), w / 2 - 0.004, h * 0.5, hl * 0.56, upper, 8, 3, floor=y + 0.02)
    box(m, (x - w / 2 + 0.014, y + h, z - hl + 0.025), (x + w / 2 - 0.014, y + h + 0.002, z - 0.01), "rubber_black",
        "+y")
    if accent:
        box(m, (x - 0.012, y + h - 0.035, z - hl), (x + 0.012, y + h + 0.004, z - hl + 0.006), accent, "+x-x+y-z")


def _shoe_pair(m: Mesh, x: float, y: float, z: float, ln: float, w: float, h: float, upper: str, sole: str,
               accent: str | None = None) -> None:
    """A pair side by side, the right one a little forward."""
    for k, sx in enumerate((-1, 1)):
        _shoe(m, x + sx * (w / 2 + 0.01), y, z - 0.01 + 0.02 * k, ln - 0.02, w, h, upper, sole, accent)


def build_hall_console(m, s, R, prm, rng):
    """A slim entrance console: an oak top over a drawer box with two drawers (raised panels, the bar handle) on four
    tapered oak legs, a low oak shelf with two woven baskets. Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    top, body = prm.get("top", "worktop_wood"), prm.get("body", "wood_front")
    yd = H - 0.2  # the drawer box's underside
    zf = hz - st.reach - 0.002
    for sx in (-1, 1):
        for sz in (-1, 1):
            leg(m, sx * (hx - 0.07), sz * (hz - 0.075), 0.0, yd + 0.01, 0.02, top, 0.65, 10)
    cbox(m, (-hx + 0.03, yd, -hz + 0.01), (hx - 0.03, H - 0.03, zf), body, st.bevel_small)
    worktop(m, st, -hx, hx, -hz, hz, top, y=H)
    for a, b, left in ((-hx + 0.03, 0.0, True), (0.0, hx - 0.03, False)):
        front(m, st, a, b, yd + 0.004, H - 0.034, zf, body, left, "h", line="wood_front_dark")
    ys = 0.14  # the shelf
    cbox(m, (-hx + 0.05, ys, -hz + 0.04), (hx - 0.05, ys + 0.022, hz - 0.05), top, st.bevel_small)
    yb = ys + 0.022
    for x in (-L * 0.21, L * 0.21):
        bw = L * 0.17
        cushion(m, (x - bw, yb, -hz + 0.07), (x + bw, yb + 0.2, hz - 0.08), "throw_cream", 0.012)
        box(m, (x - bw + 0.012, yb + 0.2, -hz + 0.082), (x + bw - 0.012, yb + 0.201, hz - 0.092), "upholstery", "+y")
        box(m, (x - 0.05, yb + 0.15, hz - 0.08), (x + 0.05, yb + 0.17, hz - 0.079), "upholstery", "+z")


def build_hall_mirror(m, s, R, prm, rng):
    """An arched mirror for the wall (wall pivot, the back at z 0): a slim warm brass frame (`frame_paint`, `frame`
    wide) round a pane on the gloss layer (`glass`)."""
    L, W, H = s
    hx = L / 2
    f = float(prm.get("frame", 0.025))
    fr, gl = prm.get("frame_paint", "steel_warm"), prm.get("glass", "mirror_glass")
    a, yc, n, zp = hx - f, H - hx, 24, W * 0.55
    ao = [(hx * math.cos(math.pi * i / n), yc + hx * math.sin(math.pi * i / n)) for i in range(n + 1)]
    ai = [(a * math.cos(math.pi * i / n), yc + a * math.sin(math.pi * i / n)) for i in range(n + 1)]
    m.poly([(-a, f, zp), (a, f, zp)] + [(x, y, zp) for x, y in ai], (0, 0, 1), gl)
    box(m, (-hx, 0.0, 0.0), (hx, f, W), fr, "+x-x+y-y+z")
    for sx in (-1, 1):
        x0, x1 = sorted((sx * hx, sx * a))
        box(m, (x0, f, 0.0), (x1, yc, W), fr, "+x-x+z")
    for i in range(n):
        (o0, p0), (o1, p1) = ao[i], ao[i + 1]
        (i0, j0), (i1, j1) = ai[i], ai[i + 1]
        m.poly([(i0, j0, W), (o0, p0, W), (o1, p1, W), (i1, j1, W)], (0, 0, 1), fr)
        m.poly([(o0, p0, 0.0), (o1, p1, 0.0), (o1, p1, W), (o0, p0, W)], (o0 + o1, p0 + p1 - 2 * yc, 0), fr)
        m.poly([(i0, j0, zp), (i1, j1, zp), (i1, j1, W), (i0, j0, W)], (-(i0 + i1), -(j0 + j1 - 2 * yc), 0), fr)


def _coat(m: Mesh, x: float, hem: float, ysh: float, z: float, role: str, trim: str) -> None:
    """A coat hanging from a hook at its collar (ysh: the shoulders' top), its back at z: the body, the shoulders,
    the collar, two sleeves, a placket and two pocket flaps in `trim`."""
    cushion(m, (x - 0.19, hem, z), (x + 0.19, ysh - 0.05, z + 0.12), role, 0.045)
    blob(m, (x, ysh - 0.07, z + 0.06), 0.21, 0.07, 0.065, role, 10, 4)
    blob(m, (x, ysh - 0.015, z + 0.07), 0.08, 0.035, 0.05, role, 8, 3)
    for sx in (-1, 1):
        cushion(m, (x + sx * 0.2 - 0.04, ysh - 0.62, z + 0.03), (x + sx * 0.2 + 0.04, ysh - 0.08, z + 0.12), role, 0.03)
    box(m, (x - 0.006, hem + 0.06, z + 0.1205), (x + 0.006, ysh - 0.14, z + 0.1215), trim, "+z")
    for sx in (-1, 1):
        y = hem + (ysh - hem) * 0.38
        box(m, (x + sx * 0.1 - 0.05, y, z + 0.1205), (x + sx * 0.1 + 0.05, y + 0.02, z + 0.1215), trim, "+z")


def build_coat_hooks(m, s, R, prm, rng):
    """Wall hooks by the front door (wall pivot, the back at z 0, the lowest hem at y 0): an oak rail with six black
    hooks under an oak hat shelf on two black brackets, a long navy coat, a camel coat in front of it, a mustard scarf
    with navy stripes and a cream tote bag on the hooks, a cap on the shelf. Collider: one box round the coats."""
    L, W, H = s
    hx = L / 2
    wood = prm.get("wood", "worktop_wood")
    yt = H - 0.07  # the shelf's top
    yr = yt - 0.3  # the rail's bottom
    cbox(m, (-hx, yr, 0.0), (hx, yr + 0.12, 0.022), wood, 0.003)
    cbox(m, (-hx, yt - 0.024, 0.0), (hx, yt, W), wood, 0.003)
    for sx in (-1, 1):
        x = sx * (hx - 0.09)
        box(m, (x - 0.01, yt - 0.2, 0.0), (x + 0.01, yt - 0.024, 0.012), "steel_black", "+x-x-y+z")
        rod(m, (x, yt - 0.19, 0.012), (x, yt - 0.03, W * 0.6), 0.008, "steel_black", 6)
    yh = yr + 0.06
    for k in range(6):
        x = -hx + 0.1 + k * (L - 0.2) / 5
        rod(m, (x, yh, 0.022), (x, yh + 0.03, 0.07), 0.006, "steel_black", 6)
        blob(m, (x, yh + 0.032, 0.073), 0.01, 0.01, 0.01, "steel_black", 6, 3)
    ysh = yh + 0.01
    _coat(m, -hx + 0.25, 0.0, ysh, 0.025, prm.get("coat", "coat_navy"), "steel_black")
    _coat(m, -hx + 0.62, 0.24, ysh, 0.06, prm.get("coat2", "coat_camel"), "wood_front_dark")
    xs = hx - 0.42  # the scarf
    for k, (a, b, lo) in enumerate(((-0.07, -0.005, 0.38), (0.005, 0.07, 0.46))):
        z0 = 0.03 + 0.012 * k
        cushion(m, (xs + a, lo, z0), (xs + b, yh + 0.03, z0 + 0.03), "cushion_mustard", 0.01)
        for y in (lo + 0.05, lo + 0.1):
            box(m, (xs + a, y, z0 + 0.0305), (xs + b, y + 0.022, z0 + 0.0312), "book_navy", "+z")
    xt = hx - 0.14  # the tote bag
    cushion(m, (xt - 0.12, 0.34, 0.03), (xt + 0.12, 0.68, 0.1), "throw_cream", 0.015)
    box(m, (xt - 0.12, 0.42, 0.1005), (xt + 0.12, 0.47, 0.1012), "book_navy", "+z")
    for dx in (-0.07, 0.07):
        rod(m, (xt + dx, 0.68, 0.065), (xt + dx * 0.15, yh + 0.025, 0.06), 0.006, "throw_cream", 5)
    xc, zc = -hx + 0.3, W * 0.42  # the cap on the shelf
    blob(m, (xc, yt, zc), 0.09, 0.065, 0.085, prm.get("cap", "book_teal"), 10, 4, floor=yt)
    box(m, (xc - 0.07, yt, zc + 0.04), (xc + 0.07, yt + 0.01, zc + 0.14), prm.get("cap", "book_teal"), "+x-x+y+z-z")
    _boxes(prm).append(((-hx, 0.0, 0.0), (hx, H, 0.22)))


def build_hall_bench(m, s, R, prm, rng):
    """A hall bench: two oak side panels, an oak seat board with a seat pad (`pad`), a back rail, a slatted shoe
    shelf low between the sides with white trainers and brown ankle boots on it. Collider: one box."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood = prm.get("wood", "worktop_wood")
    yt = H - 0.05  # the board's top under the pad
    for sx in (-1, 1):
        x0, x1 = sorted((sx * hx, sx * (hx - 0.03)))
        cbox(m, (x0, 0.0, -hz), (x1, yt - 0.03, hz), wood, 0.004)
    cbox(m, (-hx, yt - 0.03, -hz), (hx, yt, hz), wood, 0.004)
    cushion(m, (-hx + 0.02, yt, -hz + 0.02), (hx - 0.02, H, hz - 0.02), prm.get("pad", "cushion_teal"), 0.02)
    box(m, (-hx + 0.03, yt - 0.13, -hz + 0.005), (hx - 0.03, yt - 0.03, -hz + 0.025), wood, "+z-z-y")
    ys, sw = 0.07, (W - 0.04) / 4
    for k in range(4):
        z0 = -hz + 0.02 + k * sw
        box(m, (-hx + 0.03, ys, z0 + 0.006), (hx - 0.03, ys + 0.018, z0 + sw - 0.006), wood, "+y-y+z-z")
    y = ys + 0.018
    _shoe_pair(m, -L * 0.22, y, 0.01, 0.28, 0.085, 0.085, "art_white", "enamel_white", "paint_red")
    _shoe_pair(m, L * 0.22, y, 0.01, 0.28, 0.09, 0.15, "art_patty", "rubber_black")


def build_umbrella_stand(m, s, R, prm, rng):
    """A round black steel umbrella stand with a warm brass rim, a red and a navy umbrella in it (folded canopies, a
    chrome shaft, a dark wooden crook handle). Collider: one box."""
    L, W, H = s
    r = min(L, W) / 2
    hs = H * 0.54
    cyl(m, "y", (0.0, 0.0), r * 0.94, 0.0, hs, "steel_black", 14, r1=r, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), r * 0.94 - 0.006, 0.02, hs, "steel_black", 14, r1=r - 0.006, caps=(True, False), flip=True)
    tube(m, "y", (0.0, 0.0), r - 0.007, r, hs, hs + 0.006, "steel_warm", 14)
    for x, z, role, top, sx in ((-0.035, 0.03, "paint_red", H - 0.024, 1), (0.04, -0.025, "book_navy", H - 0.11, -1)):
        cyl(m, "y", (x, z), 0.004, 0.02, 0.08, "steel_black", 6, r1=0.01)
        cyl(m, "y", (x, z), 0.01, 0.08, 0.4, role, 10, r1=0.04, caps=(False, False))
        cyl(m, "y", (x, z), 0.04, 0.4, 0.58, role, 10, r1=0.012, caps=(False, False))
        cyl(m, "y", (x, z), 0.006, 0.58, top - 0.08, "chrome", 6)
        rod(m, (x, top - 0.08, z), (x, top - 0.02, z), 0.009, "wood_front_dark", 6)
        pts = [(x + sx * (0.035 - 0.035 * math.cos(math.pi * k / 5)), top - 0.02 + 0.035 * math.sin(math.pi * k / 5))
               for k in range(6)]
        for (a, b), (c, d) in zip(pts, pts[1:]):
            rod(m, (a, b, z), (c, d, z), 0.009, "wood_front_dark", 6)


def build_key_bowl(m, s, R, prm, rng):
    """A low stoneware bowl (dark outside, teal glaze inside) by the door with a ring of keys, a car fob and a red
    key tag in it."""
    L, W, H = s
    r = min(L, W) / 2
    hb = 0.05
    cyl(m, "y", (0.0, 0.0), r * 0.55, 0.0, hb, "stone_dark", 16, r1=r, caps=(True, False))
    cyl(m, "y", (0.0, 0.0), r * 0.5, 0.008, hb, "book_teal", 16, r1=r * 0.94, caps=(True, False), flip=True)
    yk = 0.025
    tube(m, "y", (-0.01, 0.0), 0.012, 0.016, yk, yk + 0.004, "chrome", 10)
    box(m, (0.004, yk, -0.004), (0.045, yk + 0.003, 0.004), "steel_warm", "+y+x-x+z-z")
    cbox(m, (0.03, yk, -0.01), (0.05, yk + 0.005, 0.01), "steel_warm", 0.001)
    box(m, (-0.014, yk, 0.012), (-0.006, yk + 0.003, 0.048), "chrome", "+y+x-x+z-z")
    cbox(m, (-0.055, yk, -0.022), (-0.022, yk + 0.018, 0.004), "rubber_black", 0.004)
    cbox(m, (0.0, yk, -0.05), (0.028, yk + 0.004, -0.02), "paint_red", 0.001)


def build_parcels(m, s, R, prm, rng):
    """Two delivery parcels by the door: a kraft box with a taped top and a shipping label (the burger delivery's
    bun logo, address lines), a smaller box on it with its own tape and a red label."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    y1 = H * 0.6
    x1, z1 = hx, hz
    cbox(m, (-hx, 0.0, -hz), (x1, y1, z1), "kraft", 0.004)
    box(m, (-hx, y1, -0.025), (x1, y1 + 0.001, 0.025), "kraft_tape", "+y")
    for x in (-hx, x1):
        box(m, (x - 0.0005, y1 - 0.08, -0.025), (x + 0.0005, y1, 0.025), "kraft_tape", "+x-x")
    zl = z1 + 0.0005
    box(m, (0.0, y1 * 0.3, z1), (x1 - 0.05, y1 * 0.8, zl), "art_white", "+z")
    for k in range(3):
        y = y1 * (0.36 + 0.08 * k)
        box(m, (0.09, y, zl), (x1 - 0.08 - 0.03 * k, y + 0.012, zl + 0.0004), "book_navy", "+z")
    cyl(m, "z", (0.045, y1 * 0.66), 0.028, zl, zl + 0.0004, "art_bun", 14, caps=(False, True))
    box(m, (0.017, y1 * 0.64, zl), (0.073, y1 * 0.66, zl + 0.0007), "art_patty", "+z")
    a0, a1, b0, b1 = -hx + 0.05, 0.12, -hz + 0.06, hz - 0.09
    cbox(m, (a0, y1, b0), (a1, H, b1), "kraft", 0.004)
    box(m, ((a0 + a1) / 2 - 0.02, H, b0), ((a0 + a1) / 2 + 0.02, H + 0.0008, b1), "kraft_tape", "+y")
    box(m, (a0 + 0.03, y1 + 0.03, b1), (a0 + 0.13, y1 + 0.09, b1 + 0.0005), "paint_red", "+z")


def build_shoe_pairs(m, s, R, prm, rng):
    """Shoes in pairs by the door, toes to +z: black running trainers with a mustard heel tab and a child's blue
    trainers with a red one."""
    L, W, H = s
    hx = L / 2
    _shoe_pair(m, -hx + 0.1, 0.0, 0.0, W, 0.09, H, "rubber_black", "enamel_white", "book_mustard")
    _shoe_pair(m, hx - 0.08, 0.0, -0.03, W * 0.72, 0.07, H * 0.8, "paint_blue", "enamel_white", "paint_red")


def build_sports_bag(m, s, R, prm, rng):
    """A navy sports holdall on the floor (red end panels, a black zip and carry handles) with a white cycling helmet
    on it (vents, a dark visor)."""
    L, W, H = s
    hx = L / 2
    r = W / 2 - 0.005
    cyl(m, "x", (r, 0.0), r, -hx + 0.025, hx - 0.025, "book_navy", 14, caps=(False, False))
    for a0, a1 in ((-hx, -hx + 0.025), (hx - 0.025, hx)):
        cyl(m, "x", (r, 0.0), r * 0.96, a0, a1, "paint_red", 14)
    box(m, (-hx + 0.06, 2 * r - 0.002, -0.008), (hx - 0.06, 2 * r + 0.004, 0.008), "steel_black", "+y+z-z")
    for z in (-0.04, 0.04):
        pts = [(-0.24, 2 * r - 0.01), (-0.2, 2 * r + 0.05), (-0.06, 2 * r + 0.05), (-0.02, 2 * r - 0.01)]
        for (a, b), (c, d) in zip(pts, pts[1:]):
            rod(m, (a, b, z), (c, d, z), 0.007, "rubber_black", 5)
    xh, yb = hx - 0.17, 2 * r - 0.03
    blob(m, (xh, yb, 0.0), 0.13, H - yb, 0.11, "art_white", 12, 5, floor=yb)
    for k in (-1, 0, 1):
        box(m, (xh - 0.05, H - 0.012 - 0.01 * abs(k), k * 0.035 - 0.008), (xh + 0.05, H - 0.004 - 0.01 * abs(k),
            k * 0.035 + 0.008), "rubber_black", "+y+x-x+z-z")
    box(m, (xh + 0.1, yb + 0.02, -0.06), (xh + 0.135, yb + 0.05, 0.06), "glass_dark", "+x+y-y+z-z")


def build_photo_row(m, s, R, prm, rng):
    """A row of three small frames (wall pivot): two family portraits of plasticine people in black and white
    frames and six holiday photos in an oak frame between them."""
    L, W, H = s
    hx, z0, z1 = L / 2, -W / 2, W / 2
    _framed(m, -hx, -hx + 0.24, 0.0, H, z0, z1, 0.015, 0.02, "steel_black", "family", rng)
    _framed(m, -0.17, 0.17, 0.04, H - 0.03, z0, z1, 0.018, 0.015, "worktop_wood", "photos", rng)
    _framed(m, hx - 0.24, hx, 0.02, H - 0.02, z0, z1 - 0.004, 0.015, 0.02, "art_white", "family", rng)



# A salon hang of six frames (#156 round 2, the hallway's far wall): (x0, x1, y0, y1) as fractions of the prop's
# width and height, the frame's paint and the picture (see _art); gaps of 0.04 of the width and height.
GALLERY = ((0.0, 0.3, 0.4, 1.0, "steel_black", "city"), (0.34, 0.66, 0.55, 1.0, "worktop_wood", "family"),
           (0.7, 1.0, 0.45, 1.0, "art_white", "abstract"), (0.0, 0.3, 0.0, 0.36, "worktop_wood", "photos"),
           (0.34, 0.66, 0.0, 0.51, "steel_black", "still_life"), (0.7, 1.0, 0.0, 0.41, "steel_black", "family"))


def build_gallery_wall(m, s, R, prm, rng):
    """A gallery wall (wall pivot: the backs at -z): six frames hung salon-style, a skyline poster, two family
    portraits of plasticine people, a mid-century print, a grid of holiday photos and a still life, drawn by this
    repo (see _art)."""
    L, W, H = s
    hx, z0, z1 = L / 2, -W / 2, W / 2
    for a, b, c, d, fr, kind in GALLERY:
        _framed(m, -hx + a * L, -hx + b * L, c * H, d * H, z0, z1, 0.02, 0.03, fr, kind, rng)


# ---- The ground floor's small rooms in the world look (#158): the WC, the pantry and the stairs.

def build_wc_toilet(m, s, R, prm, rng):
    """A present-day close-coupled toilet (front +z, its back on the wall at -z): a porcelain foot and bowl, a white
    seat and closed lid on a chrome hinge bar, a rounded cistern with a chrome dual-flush button. Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    por, seat = prm.get("body", "porcelain_white"), prm.get("seat", "enamel_white")
    ct, yp, n = 0.17, 0.4, 20
    pr, sq = hx - 0.012, 1.3
    zc = hz - pr * sq - 0.004
    cyl(m, "y", (0.0, zc - 0.03), pr * 0.6, 0.0, yp - 0.14, por, n, r1=pr * 0.72, sq=1.4)
    cyl(m, "y", (0.0, zc), pr * 0.74, yp - 0.14, yp - 0.02, por, n, r1=pr * 0.98, sq=sq)
    cyl(m, "y", (0.0, zc), pr * 0.98, yp - 0.02, yp, por, n, r1=pr, sq=sq)
    cyl(m, "y", (0.0, zc), pr, yp, yp + 0.018, seat, n, sq=sq)
    cyl(m, "y", (0.0, zc), pr * 0.97, yp + 0.018, yp + 0.04, seat, n, r1=pr * 0.93, sq=sq)
    rod(m, (-0.08, yp + 0.02, zc - pr * sq + 0.01), (0.08, yp + 0.02, zc - pr * sq + 0.01), 0.008, "chrome", 8)
    cbox(m, (-hx, yp - 0.04, -hz), (hx, H - 0.025, -hz + ct), por, st.bevel)
    cbox(m, (-hx, H - 0.025, -hz), (hx, H - 0.006, -hz + ct + 0.006), por, st.bevel_small)
    cyl(m, "y", (0.0, -hz + ct / 2), 0.03, H - 0.006, H, "chrome", 14)
    box(m, (-0.002, H - 0.0005, -hz + ct / 2 - 0.028), (0.002, H, -hz + ct / 2 + 0.028), "steel_black", "+y")


def build_wc_vanity(m, s, R, prm, rng):
    """A small vanity unit (front +z): an oak drawer box on a plinth, a stone top, a round porcelain sit-on basin
    with a chrome drain and a pillar tap behind it. Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, top = prm.get("body", "wood_front"), prm.get("top", "worktop_stone")
    yt = 0.75
    zf = hz - st.reach - 0.002
    plinth(m, st, -hx + 0.02, hx - 0.02, -hz + 0.02, zf - 0.04)
    cbox(m, (-hx, st.plinth, -hz), (hx, yt - 0.03, zf), body, st.bevel_small)
    front(m, st, -hx + 0.004, hx - 0.004, st.plinth + 0.004, 0.42, zf, body, True, "h", line="wood_front_dark")
    front(m, st, -hx + 0.004, hx - 0.004, 0.42, yt - 0.034, zf, body, True, "h", line="wood_front_dark")
    worktop(m, st, -hx, hx, -hz, hz, top, y=yt)
    r, zb = min(hx, hz) - 0.03, 0.03
    cyl(m, "y", (0.0, zb), r * 0.8, yt, yt + 0.13, "porcelain_white", 20, r1=r, caps=(True, False))
    cyl(m, "y", (0.0, zb), r * 0.72, yt + 0.02, yt + 0.13, "porcelain_white", 20, r1=r - 0.012, caps=(True, False),
        flip=True)
    tube(m, "y", (0.0, zb), r - 0.012, r, yt + 0.128, yt + 0.13, "porcelain_white", 20)
    cyl(m, "y", (0.0, zb), 0.02, yt + 0.021, yt + 0.024, "chrome", 10)
    tap(m, st, 0.0, -hz + 0.045, yt)


def build_mirror_cabinet(m, s, R, prm, rng):
    """A mirror cabinet for the wall over the basin (wall pivot, the back at z 0): a white body with two mirrored
    doors and a slim shelf under it with a soap pump and a toothbrush mug."""
    st = _style(prm)
    L, W, H = s
    hx = L / 2
    body = prm.get("body", "enamel_white")
    yb, d = 0.12, W - 0.03
    cbox(m, (-hx, yb, 0.0), (hx, H, d - 0.02), body, st.bevel_small)
    for a, b in ((-hx, 0.0), (0.0, hx)):
        cbox(m, (a + 0.002, yb + 0.004, d - 0.02), (b - 0.002, H - 0.004, d - 0.003), body, st.bevel_small)
        box(m, (a + 0.014, yb + 0.016, d - 0.003), (b - 0.014, H - 0.016, d), "mirror_glass", "+z")
    cbox(m, (-hx + 0.04, 0.0, 0.0), (hx - 0.04, 0.012, W), "steel_warm", 0.002)
    cyl(m, "y", (-hx + 0.12, W * 0.55), 0.03, 0.012, 0.13, "book_teal", 12)
    cyl(m, "y", (-hx + 0.12, W * 0.55), 0.008, 0.13, 0.155, "chrome", 8)
    rod(m, (-hx + 0.12, 0.15, W * 0.55), (-hx + 0.12, 0.15, W * 0.55 + 0.03), 0.006, "chrome", 6)
    cyl(m, "y", (hx - 0.12, W * 0.55), 0.032, 0.012, 0.1, "porcelain_white", 12, r1=0.036)
    for dx, role in ((-0.008, "paint_red"), (0.01, "book_teal")):
        rod(m, (hx - 0.12 + dx, 0.06, W * 0.55), (hx - 0.12 + dx * 2, 0.17, W * 0.55 - 0.005), 0.005, role, 6)


def build_towel_ring(m, s, R, prm, rng):
    """A chrome towel ring on a wall rose (wall pivot) with a folded hand towel hanging through it."""
    L, W, H = s
    towel = prm.get("towel", "cushion_teal")
    yr = H - 0.025
    cyl(m, "z", (0.0, yr), 0.025, 0.0, 0.012, "chrome", 12)
    rod(m, (0.0, yr, 0.01), (0.0, yr, 0.04), 0.007, "chrome", 8)
    r, yc, zc, n = 0.075, yr - 0.08, 0.045, 12
    pts = [(r * math.cos(2 * math.pi * k / n), yc + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
    for (a, b), (c, d) in zip(pts, pts[1:]):
        rod(m, (a, b, zc), (c, d, zc), 0.006, "chrome", 4)
    hw = L / 2 - 0.01
    cushion(m, (-hw, 0.0, zc - 0.012), (-0.002, yc - r + 0.01, zc + 0.012), towel, 0.006)
    cushion(m, (0.002, 0.03, zc - 0.012), (hw, yc - r + 0.01, zc + 0.012), towel, 0.006)
    rod(m, (-hw * 0.9, yc - r + 0.004, zc), (hw * 0.9, yc - r + 0.004, zc), 0.014, towel, 8)
    box(m, (-hw, 0.04, zc + 0.012), (-0.002, 0.055, zc + 0.0125), "throw_cream", "+z")


def build_roll_holder(m, s, R, prm, rng):
    """A chrome toilet-roll holder (wall pivot): a back plate, an arm with a roll on it and the paper's end hanging,
    and a little shelf on top with a spare roll."""
    L, W, H = s
    hx = L / 2
    yr, rr = 0.075, 0.055
    cbox(m, (-hx, yr - 0.02, 0.0), (-hx + 0.025, yr + 0.02, 0.012), "chrome", 0.002)
    rod(m, (-hx + 0.012, yr, 0.012), (-hx + 0.012, yr, rr + 0.012), 0.006, "chrome", 6)
    rod(m, (-hx + 0.012, yr, rr + 0.012), (hx - 0.01, yr, rr + 0.012), 0.006, "chrome", 6)
    tube(m, "x", (yr, rr + 0.012), 0.02, rr, -hx + 0.02, hx - 0.012, "art_white", 14)
    box(m, (-hx + 0.022, 0.0, 2 * rr + 0.008), (hx - 0.014, yr, 2 * rr + 0.012), "art_white", "+z-z+x-x")
    cbox(m, (-hx, yr + rr + 0.004, 0.0), (hx, yr + rr + 0.012, W), "chrome", 0.002)
    cyl(m, "y", (0.0, W / 2), 0.05, yr + rr + 0.012, H, "art_white", 12)


def build_pedal_bin(m, s, R, prm, rng):
    """A small brushed-steel pedal bin with a black lid and a black pedal at the front."""
    L, W, H = s
    r = min(L, W - 0.03) / 2
    zc = -0.015
    cyl(m, "y", (0.0, zc), r * 0.94, 0.0, H - 0.03, "steel_warm", 16, r1=r)
    cyl(m, "y", (0.0, zc), r, H - 0.03, H, "steel_black", 16, r1=r * 0.82)
    cbox(m, (-0.06, 0.0, zc + r * 0.9), (0.06, 0.02, W / 2), "rubber_black", 0.003)
    cbox(m, (-0.02, 0.0, zc + r * 0.85), (0.02, 0.06, zc + r * 0.98), "steel_black", 0.002)


def build_toilet_brush(m, s, R, prm, rng):
    """A toilet brush in a steel holder: a black handle with a chrome knob."""
    L, W, H = s
    r = min(L, W) / 2
    cyl(m, "y", (0.0, 0.0), r * 0.9, 0.0, 0.14, "steel_warm", 12, r1=r)
    tube(m, "y", (0.0, 0.0), r * 0.8, r, 0.14, 0.145, "steel_black", 12)
    rod(m, (0.0, 0.12, 0.0), (0.0, H - 0.02, 0.0), 0.009, "rubber_black", 8)
    cyl(m, "y", (0.0, 0.0), 0.016, H - 0.02, H, "chrome", 10)


def build_reed_diffuser(m, s, R, prm, rng):
    """A reed diffuser: a dark glass bottle with a chrome collar and a fan of reeds."""
    L, W, H = s
    cyl(m, "y", (0.0, 0.0), 0.03, 0.0, 0.08, "glass_dark", 12, r1=0.026)
    cyl(m, "y", (0.0, 0.0), 0.01, 0.08, 0.1, "chrome", 10)
    hx = L / 2 - 0.004
    for k in range(7):
        a = 2 * math.pi * k / 7 + 0.3
        x, z = hx * math.cos(a), hx * math.sin(a) * 0.9
        rod(m, (0.0, 0.09, 0.0), (x, H - 0.03 * (k % 3), z), 0.0025, "wood_front_dark", 4, caps=False)


def build_washing_machine(m, s, R, prm, rng):
    """A front-loading washer (or with `dryer` its matching dryer): a white enamel body, a control strip with a
    detergent drawer, a dark display and a chrome dial, a round door (chrome ring, dark glass or the dryer's white
    door) with a handle and a kick panel. Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    body = prm.get("body", "enamel_white")
    dryer = bool(prm.get("dryer"))
    zf = hz - 0.02
    cbox(m, (-hx, 0.0, -hz), (hx, H, zf), body, st.bevel)
    yp = H - 0.13
    box(m, (-hx + 0.02, yp, zf), (hx - 0.02, yp + 0.004, zf + 0.004), "steel_warm", "+z+y-y")
    cbox(m, (-hx + 0.03, yp + 0.025, zf), (-hx + 0.2, H - 0.025, zf + 0.012), body, st.bevel_small)
    box(m, (-hx + 0.05, yp + 0.03, zf + 0.012), (-hx + 0.18, yp + 0.04, zf + 0.0125), "steel_black", "+z")
    box(m, (0.0, yp + 0.04, zf), (0.14, H - 0.04, zf + 0.004), "glass_dark", "+z+x-x+y-y")
    cyl(m, "z", (hx - 0.09, yp + 0.065), 0.032, zf, zf + 0.018, "chrome", 16)
    cyl(m, "z", (hx - 0.09, yp + 0.065), 0.024, zf + 0.018, zf + 0.02, "steel_black", 16)
    yc, ro = 0.42, min(hx - 0.07, 0.22)
    ri = ro - 0.04
    tube(m, "z", (0.0, yc), ri, ro, zf, zf + 0.016, "chrome", 28)
    cyl(m, "z", (0.0, yc), ri, zf, zf + 0.01, "enamel_white" if dryer else "glass_dark", 28, caps=(False, True))
    cbox(m, (ro - 0.03, yc - 0.06, zf + 0.012), (ro + 0.01, yc + 0.06, zf + 0.02), "steel_black", 0.003)
    box(m, (-hx + 0.03, 0.03, zf), (hx - 0.03, 0.1, zf + 0.004), body, "+z+x-x+y-y")
    if dryer:
        for k in range(6):
            x = -0.15 + 0.06 * k
            box(m, (x, 0.05, zf + 0.004), (x + 0.03, 0.08, zf + 0.0045), "steel_black", "+z")


def _stock(m: Mesh, kind: str, x0: float, x1: float, y: float, z0: float, z1: float, hmax: float) -> None:
    """One shelf of a pantry's stock along x from x0 to x1, standing on y, from the back z0 to the front z1, under
    hmax: `jars` (glass jars of pasta, rice and lentils with coloured lids), `tins`, `boxes` (cereal and pasta
    boxes), `bottles` (sauces and oil), `buns` (bags of burger buns) or `baskets` (wicker baskets of potatoes and
    onions)."""
    zc = (z0 + z1) / 2 + 0.02
    x = x0
    k = 0
    if kind == "jars":
        while x < x1 - 0.1:
            r, h = 0.045 + 0.01 * (k % 2), min(hmax, 0.13 + 0.025 * ((k * 5) % 3))
            fill = ("art_bun", "art_white", "art_terracotta", "book_mustard", "art_patty")[k % 5]
            cyl(m, "y", (x + r, zc), r - 0.004, y + 0.003, y + h * 0.78, fill, 8)
            cyl(m, "y", (x + r, zc), r, y, y + h - 0.02, "glass_tint", 8, caps=(False, False))
            cyl(m, "y", (x + r, zc), r + 0.002, y + h - 0.02, y + h, ("steel_warm", "paint_red", "book_cream")[k % 3], 8)
            x += 2 * r + 0.012
            k += 1
    elif kind == "tins":
        while x < x1 - 0.08:
            r, h = 0.037, 0.11
            for j in range(2 if k % 3 else 1):
                yy = y + j * (h + 0.002)
                cyl(m, "y", (x + r, zc), r, yy, yy + h, "steel_warm", 8)
                cyl(m, "y", (x + r, zc), r + 0.001, yy + 0.015, yy + h - 0.015,
                    ("paint_red", "leaf_green", "book_mustard", "book_navy", "art_terracotta")[(k + j) % 5], 8,
                    caps=(False, False))
            x += 2 * r + 0.008
            k += 1
    elif kind == "boxes":
        while x < x1 - 0.06:
            w, h = 0.07 + 0.015 * (k % 2), min(hmax, 0.24 + 0.03 * (k % 3))
            role = ("book_mustard", "paint_red", "book_teal", "book_cream", "paint_blue", "kraft")[k % 6]
            box(m, (x, y, z0 + 0.02), (x + w, y + h, z1 - 0.01), role, "+x-x+y+z")
            box(m, (x + 0.008, y + h * 0.35, z1 - 0.01), (x + w - 0.008, y + h * 0.75, z1 - 0.0095),
                "art_white" if k % 2 else "art_bun", "+z")
            x += w + 0.006
            k += 1
    elif kind == "bottles":
        while x < x1 - 0.07:
            r, h = 0.03 + 0.005 * (k % 2), min(hmax, 0.2 + 0.04 * (k % 3))
            role = ("paint_red", "book_mustard", "glass_dark", "art_white", "leaf_dark")[k % 5]
            cyl(m, "y", (x + r, zc), r, y, y + h * 0.7, role, 8)
            cyl(m, "y", (x + r, zc), r, y + h * 0.7, y + h * 0.88, role, 8, r1=0.012, caps=(False, False))
            cyl(m, "y", (x + r, zc), 0.013, y + h * 0.88, y + h, "steel_black" if k % 2 else "art_white", 6)
            x += 2 * r + 0.012
            k += 1
    elif kind == "buns":
        while x < x1 - 0.2:
            w = 0.2
            cbox(m, (x, y, z0 + 0.03), (x + w, y + 0.085, z1 - 0.02), "glass_tint", 0.01)
            for j in range(2):
                for i in range(2):
                    blob(m, (x + 0.05 + 0.1 * i, y + 0.035, zc - 0.05 + 0.1 * j), 0.045, 0.035, 0.045, "art_bun", 7, 3,
                         floor=y)
            x += w + 0.015
    else:  # baskets
        while x < x1 - 0.25:
            w = min(0.32, x1 - x)
            hb = min(hmax - 0.05, 0.16)
            cushion(m, (x, y, z0 + 0.03), (x + w, y + hb, z1 - 0.02), "throw_cream", 0.012)
            for i in range(5):
                bx = x + 0.05 + (w - 0.1) * i / 4
                for j, dz in enumerate((-0.07, 0.04)):
                    role = ("kraft", "book_mustard", "book_red")[(k + i + j) % 3 if k % 2 else 0]
                    blob(m, (bx, y + hb + 0.012, zc + dz), 0.04, 0.03, 0.035, role, 6, 3)
            x += w + 0.02
            k += 1


def build_pantry_shelf(m, s, R, prm, rng):
    """A pantry shelving unit (front +z): white enamel sides and top, a back panel, oak shelves stocked from the
    bottom up by `stock` (see _stock: baskets, bottles, boxes, jars, tins, buns). Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, shelf = prm.get("body", "enamel_white"), prm.get("shelf", "worktop_wood")
    stock = list(prm.get("stock", ["baskets", "bottles", "boxes", "jars", "tins"]))
    t = 0.022
    for sx in (-1, 1):
        x0, x1 = (hx - t, hx) if sx > 0 else (-hx, -hx + t)
        cbox(m, (x0, 0.0, -hz), (x1, H - 0.025, hz), body, st.bevel_small)
    cbox(m, (-hx, H - 0.025, -hz), (hx, H, hz), body, st.bevel_small)
    box(m, (-hx + t, 0.0, -hz), (hx - t, H - 0.025, -hz + 0.008), body, "+z")
    box(m, (-hx + t, 0.0, hz - 0.04), (hx - t, 0.06, hz - 0.03), body, "+z+y")
    y0, n = 0.06, len(stock)
    step = (H - 0.025 - y0) / n
    for i, kind in enumerate(stock):
        y = y0 + step * i
        cbox(m, (-hx + t, y, -hz + 0.008), (hx - t, y + t, hz - 0.01), shelf, st.bevel_small)
        _stock(m, kind, -hx + t + 0.015, hx - t - 0.015, y + t, -hz + 0.02, hz - 0.02, step - t - 0.03)


def build_veg_rack(m, s, R, prm, rng):
    """A two-tier oak vegetable rack (front +z): four legs, two trays with low rails, potatoes in the lower one and
    onions (gold and red) in the upper. Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood = prm.get("body", "worktop_wood")
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0 = hx - 0.03 if sx > 0 else -hx
            z0 = hz - 0.03 if sz > 0 else -hz
            cbox(m, (x0, 0.0, z0), (x0 + 0.03, H, z0 + 0.03), wood, st.bevel_small)
    for yt, roles in ((0.08, ("kraft", "kraft_tape")), (H * 0.52, ("book_mustard", "book_red"))):
        cbox(m, (-hx + 0.03, yt, -hz + 0.03), (hx - 0.03, yt + 0.015, hz - 0.03), wood, st.bevel_small)
        for z in (-hz + 0.03, hz - 0.045):
            cbox(m, (-hx + 0.03, yt, z), (hx - 0.03, yt + 0.09, z + 0.015), wood, st.bevel_small)
        nx, nz = 6, 2
        for i in range(nx):
            for j in range(nz):
                x = -hx + 0.08 + (L - 0.16) * i / (nx - 1) + 0.01 * rng.random()
                z = -hz + 0.09 + (W - 0.18) * j / (nz - 1)
                rx = 0.035 + 0.008 * rng.random()
                blob(m, (x, yt + 0.015 + rx * 0.8, z), rx, rx * 0.8, rx * 0.9, roles[(i + j) % 2], 6, 4)


def build_step_stool(m, s, R, prm, rng):
    """A folding two-step stool (front +z): a white steel frame, two treads with black grips. Collider: one box."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    frame = prm.get("body", "enamel_white")
    for sx in (-1, 1):
        x = sx * (hx - 0.012)
        rod(m, (x, 0.0, hz - 0.012), (x, H - 0.02, -hz + 0.1), 0.012, frame, 8)
        rod(m, (x, 0.0, -hz + 0.012), (x, H - 0.02, -hz + 0.1), 0.012, frame, 8)
        cbox(m, (x - 0.012, 0.0, hz - 0.03), (x + 0.012, 0.015, hz), "rubber_black", 0.003)
        cbox(m, (x - 0.012, 0.0, -hz), (x + 0.012, 0.015, -hz + 0.03), "rubber_black", 0.003)
    for y, z0, z1 in ((H * 0.48, 0.0, hz - 0.03), (H - 0.03, -hz + 0.02, -hz + 0.24)):
        cbox(m, (-hx + 0.01, y, z0), (hx - 0.01, y + 0.03, z1), frame, 0.004)
        cbox(m, (-hx + 0.03, y + 0.03, z0 + 0.02), (hx - 0.03, y + 0.034, z1 - 0.02), "rubber_black", 0.001)


def build_broom_set(m, s, R, prm, rng):
    """A broom leaning on the wall (the back at -z) and a dustpan with its brush on the floor beside it."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    xb = -hx + 0.14
    cbox(m, (xb - 0.13, 0.0, hz - 0.1), (xb + 0.13, 0.06, hz - 0.04), "book_teal", 0.004)
    box(m, (xb - 0.12, 0.06, hz - 0.095), (xb + 0.12, 0.09, hz - 0.045), "rubber_black", "+y+x-x+z-z")
    rod(m, (xb, 0.09, hz - 0.07), (xb, H - 0.02, -hz + 0.015), 0.012, "steel_warm", 8)
    cyl(m, "y", (xb, -hz + 0.015), 0.014, H - 0.02, H, "book_teal", 8)
    xp = hx - 0.12
    cbox(m, (xp - 0.11, 0.0, -0.06), (xp + 0.11, 0.008, 0.12), "book_teal", 0.002)
    box(m, (xp - 0.115, 0.008, -0.06), (xp - 0.11, 0.05, 0.08), "book_teal", "+x-x+y")
    box(m, (xp + 0.11, 0.008, -0.06), (xp + 0.115, 0.05, 0.08), "book_teal", "+x-x+y")
    box(m, (xp - 0.11, 0.008, -0.064), (xp + 0.11, 0.07, -0.06), "book_teal", "+z-z+y")
    rod(m, (xp, 0.04, -0.064), (xp, 0.07, -0.19), 0.012, "book_teal", 6)
    cbox(m, (xp - 0.1, 0.075, -0.02), (xp + 0.1, 0.1, 0.03), "book_teal", 0.003)
    box(m, (xp - 0.095, 0.05, -0.012), (xp + 0.095, 0.075, 0.022), "rubber_black", "+x-x+z-z")


def build_drink_crates(m, s, R, prm, rng):
    """Two stacked plastic drinks crates (a red under a teal), the top one full of bottles: necks and caps over
    its rim. Collider: one box."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    hc = H * 0.4
    for k, role in enumerate(("paint_red", "book_teal")):
        y0 = k * hc
        cbox(m, (-hx, y0, -hz), (hx, y0 + 0.02, hz), role, 0.004)
        for x0 in (-hx, hx - 0.012):
            cbox(m, (x0, y0, -hz), (x0 + 0.012, y0 + hc, hz), role, 0.003)
        for z0 in (-hz, hz - 0.012):
            cbox(m, (-hx + 0.012, y0, z0), (hx - 0.012, y0 + hc, z0 + 0.012), role, 0.003)
            box(m, (-0.07, y0 + hc - 0.07, z0 - 0.0005 if z0 < 0 else z0 + 0.012),
                (0.07, y0 + hc - 0.04, z0 if z0 < 0 else z0 + 0.0125), "steel_black", "-z" if z0 < 0 else "+z")
    nx, nz = 4, 3
    for i in range(nx):
        for j in range(nz):
            x = -hx + 0.012 + (L - 0.024) * (i + 0.5) / nx
            z = -hz + 0.012 + (W - 0.024) * (j + 0.5) / nz
            cyl(m, "y", (x, z), 0.028, hc + 0.02, H - 0.06, "glass_dark", 6, r1=0.012, caps=(False, False))
            cyl(m, "y", (x, z), 0.012, H - 0.06, H - 0.012, "glass_dark", 6, caps=(False, False))
            cyl(m, "y", (x, z), 0.014, H - 0.012, H, ("paint_red", "steel_warm", "book_mustard")[(i + j) % 3], 6,
                caps=(False, True))


def build_stair_runner(m, s, R, prm, rng):
    """A stair runner for one of the kit's half flights (floor pivot; the foot's riser at +z, climbing toward -z):
    `risers` risers of `rise` / risers and treads of `run` / (risers - 1) (kit_geom.stair_numbers), a wool runner
    6 mm proud on every tread and riser with cream edge stripes, and a warm brass stair rod at each tread's back."""
    L, W, H = s
    n, rise, run = int(prm.get("risers", 9)), float(prm.get("rise", 1.6)), float(prm.get("run", 3.0))
    h, g, t = rise / n, run / (n - 1), 0.006
    hr, e = L / 2 - 0.02, 0.04
    body, edge = prm.get("body", "carpet_navy"), prm.get("edge", "carpet_border")
    zf = run / 2
    for i in range(1, n + 1):
        za = zf - (i - 1) * g
        for a, b, role in ((-hr, -hr + e, edge), (-hr + e, hr - e, body), (hr - e, hr, edge)):
            box(m, (a, (i - 1) * h, za), (b, i * h + (t if i < n else 0.0), za + t), role, "+x-x+z")
            if i < n:
                box(m, (a, i * h, za - g), (b, i * h + t, za), role, "+x-x+y")
        if i < n:
            cyl(m, "x", (i * h + 0.011, za - g + 0.012), 0.007, -hr - 0.018, hr + 0.018, "steel_warm", 6)


# Frames going up a stair wall (#158): (x0, x1) fractions of the width, the frame's height (m), its paint and its
# picture (see _art); the centres follow the flight's pitch.
STAIR_FRAMES = ((0.0, 0.16, 0.3, "steel_black", "family"), (0.2, 0.4, 0.4, "worktop_wood", "photos"),
                (0.44, 0.58, 0.3, "art_white", "family"), (0.62, 0.8, 0.38, "steel_black", "gazebo"),
                (0.84, 1.0, 0.32, "worktop_wood", "family"))


def build_stair_gallery(m, s, R, prm, rng):
    """Family photos going up the stairs (wall pivot: the backs at -z): five frames (STAIR_FRAMES) whose centres
    climb at `pitch` (the flight's rise per run) from the left: plasticine family portraits, holiday photos and a
    photo strip from the yard's gazebo, drawn by this repo (see _art)."""
    L, W, H = s
    hx, z0, z1 = L / 2, -W / 2, W / 2
    pitch = float(prm.get("pitch", 1.6 / 3.0))
    for a, b, fh, fr, kind in STAIR_FRAMES:
        yc = pitch * (a + b) / 2 * L
        _framed(m, -hx + a * L, -hx + b * L, yc - fh / 2, yc + fh / 2, z0, z1, 0.018, 0.02, fr, kind, rng)


# ---- The upper floor's bathroom in the world look (#162).

def build_bath_tub(m, s, R, prm, rng):
    """A present-day built-in bath (front +z, its back on the wall at -z, the shower end at -x): a white apron on a
    recessed kick, a rim round a porcelain well, a wall mixer and a slide-rail shower at the shower end, a hinged
    glass screen with a chrome edge on the rim over the shower end, two bottles and a rubber duck on the rim.
    Collider: the tub's box (the screen and the shower rise above it)."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, well = prm.get("body", "enamel_white"), prm.get("well", "porcelain_white")
    yr, rw, yf = 0.56, 0.07, 0.14
    plinth(m, st, -hx + 0.02, hx - 0.02, -hz + 0.02, hz - 0.05)
    box(m, (-hx + 0.01, st.plinth, -hz), (hx - 0.01, yr - 0.03, hz - 0.01), body, "+x-x+z")
    for lo, hi in (((-hx, yr - 0.03, -hz), (hx, yr, -hz + rw)), ((-hx, yr - 0.03, hz - rw), (hx, yr, hz)),
                   ((-hx, yr - 0.03, -hz + rw), (-hx + rw, yr, hz - rw)), ((hx - rw, yr - 0.03, -hz + rw),
                                                                         (hx, yr, hz - rw))):
        cbox(m, lo, hi, body, st.bevel_small)
    i0, i1, k0, k1 = -hx + rw, hx - rw, -hz + rw, hz - rw
    box(m, (i0, yf - 0.01, k0), (i1, yf, k1), well, "+y")
    box(m, (i0 - 0.005, yf, k0), (i0, yr - 0.03, k1), well, "+x")
    box(m, (i1, yf, k0), (i1 + 0.005, yr - 0.03, k1), well, "-x")
    box(m, (i0, yf, k0 - 0.005), (i1, yr - 0.03, k0), well, "+z")
    box(m, (i0, yf, k1), (i1, yr - 0.03, k1 + 0.005), well, "-z")
    cyl(m, "y", (i0 + 0.25, 0.0), 0.022, yf, yf + 0.003, "chrome", 10)
    xs = -hx + 0.3  # the mixer and the shower rail at the shower end, on the wall
    cyl(m, "z", (xs, yr + 0.2), 0.03, -hz, -hz + 0.05, "chrome", 12)
    rod(m, (xs - 0.08, yr + 0.2, -hz + 0.04), (xs + 0.08, yr + 0.2, -hz + 0.04), 0.012, "chrome", 8)
    rod(m, (xs, yr + 0.18, -hz + 0.05), (xs, yr + 0.18, -hz + 0.17), 0.011, "chrome", 8)
    rod(m, (xs, yr + 0.18, -hz + 0.17), (xs, yr + 0.14, -hz + 0.17), 0.011, "chrome", 8)
    rod(m, (xs, yr + 0.35, -hz + 0.035), (xs, H - 0.2, -hz + 0.035), 0.011, "chrome", 8)
    for y in (yr + 0.35, H - 0.2):
        rod(m, (xs, y, -hz), (xs, y, -hz + 0.035), 0.01, "chrome", 6)
    rod(m, (xs, H - 0.2, -hz + 0.035), (xs, H - 0.04, -hz + 0.2), 0.01, "chrome", 6)
    cyl(m, "y", (xs, -hz + 0.22), 0.1, H - 0.04, H, "chrome", 16)
    cyl(m, "y", (xs, -hz + 0.22), 0.088, H - 0.041, H - 0.04, "steel_black", 16, caps=(True, False))
    rod(m, (xs, yr + 0.55, -hz + 0.05), (xs + 0.04, yr + 0.62, -hz + 0.08), 0.014, "chrome", 8)
    zs, x1 = hz - rw / 2, -hx + 0.85  # the screen on the rim's front edge
    box(m, (-hx + 0.03, yr, zs - 0.004), (x1, H - 0.08, zs + 0.004), "glass_tint")
    rod(m, (-hx + 0.015, yr, zs), (-hx + 0.015, H - 0.08, zs), 0.012, "chrome", 8)
    for y in (yr + 0.002, H - 0.082):
        box(m, (-hx + 0.03, y - 0.002, zs - 0.006), (x1, y + 0.002, zs + 0.006), "chrome")
    box(m, (x1 - 0.004, yr, zs - 0.006), (x1, H - 0.08, zs + 0.006), "chrome")
    for dx, role, h in ((0.0, "book_teal", 0.2), (0.07, "art_white", 0.16)):  # bottles in the far corner
        x = hx - rw / 2 - 0.02 - dx
        cyl(m, "y", (x, -hz + rw / 2), 0.026, yr, yr + h, role, 8)
        cyl(m, "y", (x, -hz + rw / 2), 0.01, yr + h, yr + h + 0.03, "steel_black", 6)
    xd, zd = hx - 0.3, hz - rw / 2  # the duck on the front rim
    blob(m, (xd, yr + 0.035, zd), 0.045, 0.035, 0.03, "book_mustard", 8, 4)
    blob(m, (xd + 0.03, yr + 0.085, zd), 0.026, 0.026, 0.026, "book_mustard", 8, 4)
    box(m, (xd + 0.05, yr + 0.078, zd - 0.008), (xd + 0.075, yr + 0.088, zd + 0.008), "art_terracotta")
    _boxes(prm).append(((-hx, 0.0, -hz), (hx, yr, hz)))


def build_towel_rail(m, s, R, prm, rng):
    """A heated towel rail (wall pivot, the back at z 0): two chrome uprights on wall brackets, bars up the ladder,
    the valves at the foot, a bath towel over an upper bar and a hand towel over a low one."""
    L, W, H = s
    hx, zr = L / 2, W - 0.03
    for sx in (-1, 1):
        x = sx * (hx - 0.02)
        rod(m, (x, 0.08, zr), (x, H, zr), 0.014, "chrome", 10)
        for y in (0.18, H - 0.1):
            rod(m, (x, y, 0.0), (x, y, zr), 0.009, "chrome", 6)
        cyl(m, "y", (x, zr), 0.016, 0.0, 0.08, "chrome", 8)
    y = 0.16
    while y < H - 0.02:
        rod(m, (-hx + 0.03, y, zr), (hx - 0.03, y, zr), 0.009, "chrome", 6, caps=False)
        y += 0.075
    big, small = prm.get("towel", "cushion_teal"), prm.get("hand", "throw_cream")
    for (y0, y1, a, b, role) in ((0.42, 0.92, -hx + 0.05, hx - 0.05, big), (0.12, 0.47, -hx + 0.12, hx - 0.12, small)):
        cushion(m, (a, y0, zr + 0.016), (b, y1 + 0.02, zr + 0.03), role, 0.006)
        cushion(m, (a, y0 + 0.12, zr - 0.03), (b, y1 + 0.02, zr - 0.016), role, 0.006)
        rod(m, (a + 0.01, y1 + 0.02, zr), (b - 0.01, y1 + 0.02, zr), 0.022, role, 8)


def build_bath_shelf(m, s, R, prm, rng):
    """An open oak shelf unit for the bathroom (front +z): two sides, five shelves, rolled towels at the foot, a
    basket of spares, a row of bath bottles, folded towels and a small plant on top. Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood, t = prm.get("body", "wood_front"), 0.02
    Hs = H - 0.24  # the unit's top; the plant stands on it
    for xa, xb in ((-hx, -hx + t), (hx - t, hx)):
        cbox(m, (xa, 0.0, -hz), (xb, Hs, hz), wood, st.bevel_small)
    ys = [0.04, 0.36, 0.68, 0.94, Hs - t]
    for y in ys:
        cbox(m, (-hx + t, y, -hz), (hx - t, y + t, hz), wood, st.bevel_small)
    a, b = -hx + t + 0.01, hx - t - 0.01
    for k, role in enumerate(("cushion_teal", "throw_cream", "cushion_teal")):  # rolled towels
        x = a + 0.07 + k * 0.14
        if x + 0.065 < b:
            cyl(m, "z", (x, ys[0] + t + 0.065), 0.065, -hz + 0.02, hz - 0.02, role, 10)
    cbox(m, (a + 0.02, ys[1] + t, -hz + 0.03), (b - 0.02, ys[1] + t + 0.2, hz - 0.03), "kraft", 0.01)
    box(m, (a + 0.04, ys[1] + t + 0.2, -hz + 0.05), (b - 0.04, ys[1] + t + 0.205, hz - 0.05), "throw_cream", "+y")
    _stock(m, "bottles", a, b, ys[2] + t, -hz + 0.02, hz - 0.02, ys[3] - ys[2] - t - 0.03)
    for j, role in enumerate(("throw_cream", "cushion_teal", "throw_cream", "art_white")):  # folded towels
        y0 = ys[3] + t + j * 0.05
        cushion(m, (a + 0.03, y0, -hz + 0.03), (b - 0.03, y0 + 0.048, hz - 0.03), role, 0.008)
    pr = min(hz, 0.09)
    cyl(m, "y", (0.0, 0.0), pr * 0.8, Hs, Hs + 0.11, "stone_light", 10, r1=pr)
    for i in range(5):
        an = i * 2.39996
        _leaf(m, math.cos(an) * 0.05, Hs + 0.15 + 0.03 * (i % 2), math.sin(an) * 0.05, 0.06, "leaf_green", 6)


# ---- The upper floor's bedroom and guest room (#164) in the world look.

def build_made_bed(m, s, R, prm, rng):
    """A made-up bed (front +z = the foot, the headboard at -z): an oak frame on short legs, an upholstered
    headboard (`head`) or with `head_wood` an oak panel, a white mattress, a duvet (`duvet`) draped down the sides
    with its white sheet turned down, pillows, upright scatter cushions (`cushions`) and a throw (`throw`) across
    the foot. Collider: one box round the bed."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    wood = prm.get("frame", "worktop_wood")
    duvet, throw = prm.get("duvet", "throw_cream"), prm.get("throw", "cushion_rust")
    yl, yb, ym = 0.08, 0.3, 0.5  # the legs' top, the base's top (the mattress's foot), the mattress's top
    for sx in (-1, 1):
        for z in (-hz + 0.14, hz - 0.06):
            leg(m, sx * (hx - 0.06), z, 0.0, yl + 0.01, 0.025, "wood_front_dark", 0.8)
    cbox(m, (-hx + 0.01, yl, -hz + 0.08), (hx - 0.01, yb, hz), wood, 0.012)
    hb = 0.09  # the headboard's depth
    if prm.get("head_wood"):
        cbox(m, (-hx, 0.0, -hz), (hx, H, -hz + hb), wood, 0.012)
        box(m, (-hx + 0.06, H * 0.55, -hz + hb), (hx - 0.06, H * 0.55 + 0.012, -hz + hb + 0.004), "wood_front_dark",
            "+y+z")
    else:
        head = prm.get("head", "upholstery_light")
        cbox(m, (-hx, 0.0, -hz), (hx, yb + 0.05, -hz + hb), wood, 0.01)
        n = max(2, int(L / 0.45))
        xs = [-hx + L * k / n for k in range(n + 1)]
        for a, b in zip(xs, xs[1:]):  # padded channels
            cushion(m, (a + 0.004, yb + 0.05, -hz + 0.01), (b - 0.004, H, -hz + hb + 0.02), head, 0.045)
    cushion(m, (-hx + 0.03, yb, -hz + hb + 0.01), (hx - 0.03, ym, hz - 0.02), "art_white", 0.04)
    zt = -hz + hb + 0.5  # the duvet's top edge, the sheet turned down over it
    cushion(m, (-hx, yb - 0.04, zt), (hx, ym + 0.08, hz - 0.005), duvet, 0.05)
    cushion(m, (-hx + 0.005, ym + 0.05, zt - 0.02), (hx - 0.005, ym + 0.1, zt + 0.2), "art_white", 0.02)
    spots = list(prm.get("spots", []))  # #166: a fun duvet: little squares of these paints over its top
    if spots:
        z, k = zt + 0.3, 0
        while z < hz - 0.7:
            x = -hx + 0.14 + 0.09 * (k % 2)
            while x < hx - 0.12:
                box(m, (x - 0.035, ym + 0.078, z - 0.035), (x + 0.035, ym + 0.084, z + 0.035), spots[k % len(spots)],
                    "+y")
                x += 0.18
                k += 1
            z += 0.17
    n = 2 if L > 1.3 else 1
    pw = (L - 0.16) / n
    for k in range(n):  # pillows lying against the headboard
        a = -hx + 0.08 + k * pw
        cushion(m, (a + 0.02, ym - 0.01, -hz + hb + 0.03), (a + pw - 0.02, ym + 0.15, -hz + hb + 0.4), "art_white",
                0.06)
    paints = list(prm.get("cushions", ["cushion_teal", "cushion_mustard"]))
    cw = 0.42 if n > 1 else 0.38
    cx = [(-0.25, 0.25)[k] * (L / 1.8) for k in range(2)] if n > 1 else [0.0]
    for k, x in enumerate(cx):  # upright scatter cushions in front of the pillows
        cushion(m, (x - cw / 2, ym + 0.06, -hz + hb + 0.4), (x + cw / 2, min(H - 0.05, ym + 0.46), -hz + hb + 0.53),
                paints[k % len(paints)], 0.06)
    if n > 1:  # a lumbar cushion in the middle
        cushion(m, (-0.22, ym + 0.08, -hz + hb + 0.55), (0.22, ym + 0.3, -hz + hb + 0.66), throw, 0.05)
    t0 = hz - 0.6  # the throw across the foot and down over the end
    cushion(m, (-hx - 0.0, ym + 0.07, t0), (hx, ym + 0.11, hz), throw, 0.015)
    cushion(m, (-hx, yb - 0.02, hz - 0.03), (hx, ym + 0.1, hz), throw, 0.01)


def build_wardrobe_modern(m, s, R, prm, rng):
    """A present-day wardrobe: an oak plinth and top, a `body` carcass, `doors` full-height doors (raised panels, long
    upright bar handles); with `mirror` the middle door is a framed mirror. Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    oak, body = prm.get("trim", "worktop_wood"), prm.get("body", "enamel_white")
    zf = hz - st.reach - 0.002
    yp = 0.08
    cbox(m, (-hx + 0.04, 0.0, -hz + 0.02), (hx - 0.04, yp, zf - 0.04), oak, st.bevel_small)
    cbox(m, (-hx + 0.01, yp, -hz), (hx - 0.01, H - 0.035, zf), body, st.bevel)
    worktop(m, st, -hx, hx, -hz, hz, oak, y=H, t=0.035)
    n = int(prm.get("doors", 3))
    xs = [-hx + 0.012 + (L - 0.024) * k / n for k in range(n + 1)]
    mid = n // 2 if prm.get("mirror") else -1
    for k, (a, b) in enumerate(zip(xs, xs[1:])):
        front(m, st, a, b, yp + 0.006, H - 0.04, zf, body, k < n / 2 or (n % 2 and k == n // 2),
              glass="mirror_glass" if k == mid else None, line=None if k == mid else "wood_front_dark")


def build_bedside_set(m, s, R, prm, rng):
    """A bedside's small things: a glass of water, a phone on its white charging cable, a paperback."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    _tumbler(m, -hx + 0.04, -hz + 0.05, 0.0, 0.035, H - 0.005)
    cyl(m, "y", (-hx + 0.04, -hz + 0.05), 0.029, 0.012, H * 0.7, "glass_tint", 10)
    px, pz = 0.02, hz - 0.06  # the phone, face up
    box(m, (px - 0.036, 0.0, pz - 0.055), (px + 0.036, 0.009, pz + 0.055), "rubber_black")
    box(m, (px - 0.032, 0.009, pz - 0.05), (px + 0.032, 0.0095, pz + 0.05), "glass_dark", "+y")
    rod(m, (px, 0.004, pz - 0.055), (px + 0.03, 0.004, -hz + 0.01), 0.003, "art_white", 4)
    box(m, (hx - 0.11, 0.0, -hz + 0.01), (hx - 0.005, 0.022, -hz + 0.15), prm.get("book", "book_teal"))
    box(m, (hx - 0.106, 0.004, -hz + 0.014), (hx - 0.002, 0.018, -hz + 0.146), "art_white", "+x+z")


def build_dresser_set(m, s, R, prm, rng):
    """A dresser top's things: a brass tray with three perfume bottles, a white jewellery dish and a hairbrush."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    tx = -hx + 0.12
    box(m, (-hx, 0.0, -hz), (tx + 0.12, 0.012, hz - 0.03), "steel_warm")
    for k, (x, r, h, cap) in enumerate(((-hx + 0.05, 0.026, H - 0.03, "steel_warm"), (-hx + 0.12, 0.03, H - 0.06,
                                         "rubber_black"), (-hx + 0.19, 0.022, H - 0.05, "chrome"))):
        z = -hz + 0.06 + 0.04 * (k % 2)
        cyl(m, "y", (x, z), r, 0.012, 0.012 + h * 0.75, "glass_tint", 10)
        cyl(m, "y", (x, z), r * 0.45, 0.012 + h * 0.75, 0.012 + h, cap, 8)
    cyl(m, "y", (hx - 0.08, -hz + 0.06), 0.05, 0.0, 0.025, "porcelain_white", 14, r1=0.04)
    box(m, (hx - 0.16, 0.0, hz - 0.06), (hx - 0.01, 0.025, hz - 0.02), "wood_front_dark")
    box(m, (hx - 0.11, 0.025, hz - 0.055), (hx - 0.015, 0.035, hz - 0.025), "rubber_black", "+x-x+y+z-z")


def build_curtains(m, s, R, prm, rng):
    """Floor-length curtains for one window (wall pivot, the back at z 0): a black rod on two brackets with round
    finials, a gathered panel (`cloth`) at each side of the window, `panel` wide, in soft vertical folds."""
    L, W, H = s
    hx = L / 2
    cloth, pw = prm.get("cloth", "throw_cream"), float(prm.get("panel", 0.38))
    yr, zr = H - 0.04, W - 0.035
    rod(m, (-hx + 0.03, yr, zr), (hx - 0.03, yr, zr), 0.012, "steel_black", 8)
    for sx in (-1, 1):
        cyl(m, "x", (yr, zr), 0.025, *sorted((sx * (hx - 0.03), sx * hx)), "steel_black", 8)
        rod(m, (sx * (hx - 0.12), yr, 0.0), (sx * (hx - 0.12), yr, zr), 0.008, "steel_black", 6)
        k, r = 5, pw / 10
        for i in range(k):
            x = sx * (hx - 0.05 - r - i * 2 * r * 0.95)
            z = zr - 0.02 - (0.025 if i % 2 else 0.0)
            cyl(m, "y", (x, z), r, 0.01, yr - 0.02, cloth, 7, r1=r * 0.9)


def build_suitcase(m, s, R, prm, rng):
    """An upright hard-shell suitcase (`shell`): ribbed sides, four spinner wheels, a top carry handle, a pulled-down
    telescopic handle and a white luggage tag on the side; a burger sticker on the front."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    sh = prm.get("shell", "coat_navy")
    yw, yt = 0.06, H - 0.06  # the wheels' top, the shell's top
    for sx in (-1, 1):
        for sz in (-1, 1):
            cyl(m, "x", (0.025, sz * (hz - 0.04)), 0.025, *sorted((sx * (hx - 0.06), sx * (hx - 0.03))), "rubber_black", 8)
    cushion(m, (-hx, yw, -hz + 0.01), (hx, yt, hz - 0.01), sh, 0.05)
    box(m, (-hx - 0.0, yw + 0.02, -0.006), (hx, yt - 0.02, 0.006), "steel_black", "+x-x+y")
    for x in (-hx * 0.5, 0.0, hx * 0.5):
        box(m, (x - 0.015, yw + 0.06, hz - 0.012), (x + 0.015, yt - 0.06, hz), sh, "+x-x+y-y+z")
    for sx in (-1, 1):
        rod(m, (sx * 0.1, yt, -hz + 0.05), (sx * 0.1, H - 0.012, -hz + 0.05), 0.008, "chrome", 6)
    box(m, (-0.12, H - 0.025, -hz + 0.03), (0.12, H, -hz + 0.07), "rubber_black")
    box(m, (-0.07, yt, 0.0), (0.07, yt + 0.03, 0.03), "rubber_black")
    box(m, (hx, yt - 0.18, -0.03), (hx + 0.004, yt - 0.08, 0.03), "art_white", "+x+y-y+z-z")
    cyl(m, "z", (hx * 0.4, yt - 0.14), 0.045, hz - 0.004, hz + 0.0, "art_bun", 12)
    cyl(m, "z", (hx * 0.4, yt - 0.14), 0.035, hz - 0.002, hz + 0.002, "art_patty", 12)


def build_towel_stack(m, s, R, prm, rng):
    """Fresh towels for a guest: three folded towels (`paints` in turn), a rolled flannel and a wrapped soap."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    paints = list(prm.get("paints", ["cushion_teal", "throw_cream", "art_white"]))
    th = (H - 0.05) / 3
    for k in range(3):
        d = 0.01 * (k % 2)
        cushion(m, (-hx + d, k * th, -hz + d), (hx - 0.06 + d, (k + 1) * th - 0.003, hz - d), paints[k % len(paints)],
                0.012)
    y = 3 * th
    cyl(m, "z", (hx - 0.04, 0.035), 0.033, -hz + 0.03, hz - 0.03, paints[0], 10)
    box(m, (-0.07, y, -0.05), (0.03, y + 0.035, 0.03), "art_white")
    box(m, (-0.03, y, -0.051), (-0.01, y + 0.036, 0.031), "paint_red", "+y+z-z")


def build_storage_boxes(m, s, R, prm, rng):
    """A tidy stack of lidded storage boxes (kraft bodies, `lid` lids) with white label plates and dark hand holes:
    one wide box at the foot, two on it and a shoebox on top. Collider: one box."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    lid = prm.get("lid", "art_white")
    h1 = H * 0.42
    h2 = H * 0.35
    rows = [((-hx, hx), -hz, hz, 0.0, h1), ((-hx + 0.01, -0.01), -hz + 0.02, hz - 0.03, h1, h1 + h2),
            ((0.01, hx - 0.02), -hz + 0.03, hz - 0.02, h1, h1 + h2), ((-hx * 0.7, hx * 0.1), -hz + 0.06, hz - 0.12, h1 + h2,
                                                                         H)]
    for k, ((x0, x1), z0, z1, y0, y1) in enumerate(rows):
        box(m, (x0 + 0.01, y0, z0 + 0.01), (x1 - 0.01, y1 - 0.03, z1 - 0.01), "kraft")
        cbox(m, (x0, y1 - 0.035, z0), (x1, y1, z1), lid if k != 3 else "book_teal", 0.006)
        xm = (x0 + x1) / 2
        box(m, (xm - 0.07, (y0 + y1) / 2 - 0.02, z1 - 0.01), (xm + 0.07, (y0 + y1) / 2 + 0.03, z1 - 0.008), "art_white",
            "+z")
        box(m, (xm - 0.05, y1 - 0.08, z1 - 0.01), (xm + 0.05, y1 - 0.055, z1 - 0.009), "rubber_black", "+z")


def build_clothes_rail(m, s, R, prm, rng):
    """A guest's clothes rail in black steel: two uprights on foot bars, a top rail with shirts and a jacket on
    hangers (`paints` in turn), a low oak shelf with two pairs of shoes. Collider: one box."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    for sx in (-1, 1):
        x = sx * (hx - 0.02)
        rod(m, (x, 0.02, 0.0), (x, H - 0.02, 0.0), 0.014, "steel_black", 8)
        rod(m, (x, 0.02, -hz + 0.02), (x, 0.02, hz - 0.02), 0.016, "steel_black", 8)
    rod(m, (-hx + 0.02, H - 0.03, 0.0), (hx - 0.02, H - 0.03, 0.0), 0.012, "steel_black", 8)
    cbox(m, (-hx + 0.04, 0.16, -hz + 0.1), (hx - 0.04, 0.185, hz - 0.1), "worktop_wood", 0.004)
    _shoe_pair(m, -hx * 0.45, 0.185, 0.0, 0.27, 0.085, 0.09, "book_cream", "rubber_black")
    _shoe_pair(m, hx * 0.4, 0.185, 0.0, 0.28, 0.09, 0.1, "coat_camel", "wood_front_dark", "paint_red")
    paints = list(prm.get("paints", ["art_white", "book_sage", "coat_navy", "cushion_teal", "coat_camel"]))
    n = int(prm.get("hangers", 6))
    yh = H - 0.03
    for k in range(n):
        x = -hx + 0.14 + (L - 0.28) * k / max(1, n - 1)
        role = paints[k % len(paints)]
        long = role in ("coat_navy", "coat_camel")
        rod(m, (x, yh, 0.0), (x, yh - 0.06, 0.0), 0.004, "chrome", 4)
        rod(m, (x, yh - 0.14, -0.2), (x, yh - 0.14, 0.2), 0.007, "wood_front", 6)
        bot = yh - (0.95 if long else 0.7)
        cushion(m, (x - 0.025, bot, -0.21), (x + 0.025, yh - 0.1, 0.21), role, 0.012)
        box(m, (x - 0.03, yh - 0.16, -0.06), (x + 0.03, yh - 0.1, 0.06), role)


# ---- The kids' room and the study (#166) ------------------------------------------------------------------------

def build_toy_cubby(m, s, R, prm, rng):
    """A low cube storage unit for a kids' room: a `body` carcass of `cols` x `rows` open cubes on a dark plinth under
    an oak top; fabric bins (`bins` paints, a white label and a hand hole each) in most cubes, books in the others.
    Collider: one box."""
    st = _style(prm)
    L, W, H = s
    hx, hz = L / 2, W / 2
    body, top = prm.get("body", "enamel_white"), prm.get("trim", "worktop_wood")
    t, yp, yt = 0.02, 0.05, H - 0.03
    box(m, (-hx + 0.03, 0.0, -hz + 0.02), (hx - 0.03, yp, hz - 0.03), "rubber_black")
    for sx in (-1, 1):
        cbox(m, (hx - t if sx > 0 else -hx, yp, -hz), (hx if sx > 0 else -hx + t, yt, hz), body, st.bevel_small)
    box(m, (-hx + t, yp, -hz), (hx - t, yt, -hz + 0.01), body, "+z")
    cols, rows = int(prm.get("cols", 3)), int(prm.get("rows", 2))
    cw, ch = (L - 2 * t) / cols, (yt - yp) / rows
    for i in range(1, cols):
        x = -hx + t + cw * i
        box(m, (x - t / 2, yp, -hz + 0.01), (x + t / 2, yt, hz), body, "+x-x+z")
    for j in range(rows):
        y = yp + ch * j
        box(m, (-hx + t, y, -hz + 0.01), (hx - t, y + t, hz), body, "+y+z")
    worktop(m, st, -hx, hx, -hz, hz, top, y=H, t=0.03)
    bins = list(prm.get("bins", ["book_red", "book_mustard", "book_teal", "book_sage"]))
    books = ["book_cream", "book_teal", "book_mustard", "book_red", "book_navy", "book_sage"]
    for j in range(rows):
        for i in range(cols):
            x0, x1 = -hx + t + cw * i + t / 2, -hx + t + cw * (i + 1) - t / 2
            y0 = yp + ch * j + t
            k = i + j * cols
            if k % 3 == 1:
                book_run(m, x0 + 0.01, x1 - 0.01, y0, -hz + 0.02, W - 0.06, ch - t - 0.03, books, rng)
                continue
            y1 = y0 + (ch - t) * 0.85
            cushion(m, (x0 + 0.012, y0, -hz + 0.03), (x1 - 0.012, y1, hz - 0.012), bins[k % len(bins)], 0.02)
            xm = (x0 + x1) / 2
            box(m, (xm - 0.06, y0 + 0.08, hz - 0.012), (xm + 0.06, y0 + 0.12, hz - 0.008), "art_white", "+z")
            box(m, (xm - 0.045, y1 - 0.07, hz - 0.012), (xm + 0.045, y1 - 0.045, hz - 0.009), "rubber_black", "+z")


def build_pin_board(m, s, R, prm, rng):
    """A cork pin board in an oak frame for a study wall (wall pivot, the back at z 0): the House generator's
    blueprint, a delivery schedule (a ruled sheet, its rows ticked off), sticky notes and a family photo, each held by
    a red pin."""
    L, W, H = s
    hx = L / 2
    f = 0.03
    for lo, hi in (((-hx, 0, 0), (hx, f, W)), ((-hx, H - f, 0), (hx, H, W)), ((-hx, f, 0), (-hx + f, H - f, W)),
                   ((hx - f, f, 0), (hx, H - f, W))):
        box(m, lo, hi, prm.get("frame_paint", "worktop_wood"), "+x-x+y-y+z")
    z = W - 0.012
    box(m, (-hx + f, f, 0.0), (hx - f, H - f, z), "kraft", "+z")
    pins = []
    bx0, bx1, by0, by1 = -hx + 0.07, -hx + 0.07 + L * 0.42, H * 0.3, H - 0.07
    _art(m, "blueprint", bx0, bx1, by0, by1, z, rng)
    pins += [(bx0 + 0.02, by1 - 0.02), (bx1 - 0.02, by1 - 0.02)]
    sx0, sx1, sy0, sy1 = bx1 + 0.06, bx1 + 0.06 + L * 0.24, H * 0.18, H - 0.09
    box(m, (sx0, sy0, z), (sx1, sy1, z + 0.002), "art_white", "+z")
    box(m, (sx0 + 0.02, sy1 - 0.06, z + 0.002), (sx1 - 0.02, sy1 - 0.03, z + 0.003), "book_navy", "+z")
    rows = int((sy1 - sy0 - 0.1) / 0.045)
    for k in range(rows):
        y = sy1 - 0.1 - 0.045 * k
        box(m, (sx0 + 0.05, y, z + 0.002), (sx1 - 0.02, y + 0.008, z + 0.003), "book_grey", "+z")
        if k < rows - 2:
            box(m, (sx0 + 0.02, y - 0.004, z + 0.002), (sx0 + 0.036, y + 0.012, z + 0.003), "leaf_green", "+z")
    pins.append(((sx0 + sx1) / 2, sy1 - 0.015))
    notes = ["book_mustard", "art_pink", "book_sage", "art_sky", "book_mustard"]
    nx0 = sx1 + 0.05
    for k, role in enumerate(notes):
        x = nx0 + 0.1 * (k % 2)
        y = H - 0.17 - 0.12 * (k // 2) - 0.02 * (k % 2)
        if x + 0.08 > hx - f - 0.02 or y < f + 0.3:
            continue
        box(m, (x, y, z), (x + 0.08, y + 0.08, z + 0.002), role, "+z")
        box(m, (x + 0.012, y + 0.04, z + 0.002), (x + 0.068, y + 0.046, z + 0.003), "steel_black", "+z")
        pins.append((x + 0.04, y + 0.068))
    px0, px1 = hx - f - 0.2, hx - f - 0.04
    box(m, (px0, f + 0.06, z), (px1, f + 0.24, z + 0.002), "art_white", "+z")
    _art(m, "family", px0 + 0.012, px1 - 0.012, f + 0.09, f + 0.228, z + 0.002, rng)
    pins.append(((px0 + px1) / 2, f + 0.225))
    for x, y in pins:
        cyl(m, "z", (x, y), 0.007, z + 0.004, W, "paint_red", 8, caps=(False, True))


def build_monitor_set(m, s, R, prm, rng):
    """A desk's work things (desk-top pivot): a slim monitor on its stand showing a delivery map, a keyboard, a mouse
    on its pad, a mug and a notepad with a pen."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    zb = -hz + 0.1
    box(m, (-0.11, 0.0, zb - 0.08), (0.11, 0.012, zb + 0.06), "steel_black")
    box(m, (-0.025, 0.012, zb - 0.03), (0.025, 0.2, zb - 0.01), "metal_grey")
    sw = min(hx - 0.05, 0.3)
    box(m, (-sw, 0.12, zb - 0.01), (sw, H, zb + 0.015), "steel_black")
    box(m, (-sw + 0.012, 0.135, zb + 0.015), (sw - 0.012, H - 0.012, zb + 0.016), "art_sky", "+z")
    for a, b, c, d, role in ((0.1, 0.25, 0.55, 0.9, "art_white"), (0.6, 0.55, 0.92, 0.9, "art_white"),
                             (0.6, 0.12, 0.92, 0.48, "book_mustard"), (0.1, 0.06, 0.55, 0.18, "book_navy")):
        x0, x1 = -sw + 0.012 + a * (2 * sw - 0.024), -sw + 0.012 + c * (2 * sw - 0.024)
        y0, y1 = 0.135 + b * (H - 0.147), 0.135 + d * (H - 0.147)
        box(m, (x0, y0, zb + 0.016), (x1, y1, zb + 0.017), role, "+z")
    for k in range(6):
        x = -sw + 0.05 + 0.04 * k
        box(m, (x, 0.32, zb + 0.017), (x + 0.025, 0.33, zb + 0.018), "paint_red" if k % 2 else "book_teal", "+z")
    zk = hz - 0.13
    cbox(m, (-0.22, 0.0, zk - 0.07), (0.22, 0.018, zk + 0.07), "steel_black", 0.004)
    box(m, (-0.205, 0.018, zk - 0.055), (0.205, 0.022, zk + 0.055), "metal_grey", "+y")
    box(m, (0.24, 0.0, zk - 0.1), (hx - 0.01, 0.003, zk + 0.08), "rubber_black")
    blob(m, ((0.24 + hx) / 2, 0.012, zk), 0.03, 0.016, 0.05, "steel_black", 8, 4, floor=0.0)
    cyl(m, "y", (-hx + 0.06, zk - 0.04), 0.04, 0.0, 0.1, "porcelain_white", 12)
    cyl(m, "y", (-hx + 0.06, zk - 0.04), 0.034, 0.09, 0.095, "wood_dark", 12, caps=(False, True))
    box(m, (-hx + 0.03, 0.0, hz - 0.04), (-hx + 0.18, 0.012, hz - 0.002), "art_white")
    rod(m, (-hx + 0.05, 0.016, hz - 0.03), (-hx + 0.17, 0.016, hz - 0.012), 0.004, "book_navy", 6)


def build_toy_set(m, s, R, prm, rng):
    """A kids' room's toys on a shelf or the floor: a toy rocket on its fins, a dump truck and a ball."""
    L, W, H = s
    hx, hz = L / 2, W / 2
    rx, rz = -hx + 0.07, 0.0
    cyl(m, "y", (rx, rz), 0.045, 0.04, H * 0.66, "art_white", 8)
    cyl(m, "y", (rx, rz), 0.045, H * 0.66, H, "paint_red", 8, r1=0.004)
    cyl(m, "z", (rx, H * 0.5), 0.022, 0.044, 0.05, "art_sky", 10, caps=(False, True))
    for x0, z0, x1, z1 in ((rx - 0.07, rz - 0.006, rx - 0.04, rz + 0.006), (rx + 0.04, rz - 0.006, rx + 0.07, rz + 0.006),
                           (rx - 0.006, rz + 0.04, rx + 0.006, rz + 0.065)):
        box(m, (x0, 0.0, z0), (x1, 0.11, z1), "paint_red")
    tx = 0.04
    for x in (tx - 0.09, tx + 0.09):
        for z in (-hz + 0.03, hz - 0.03):
            cyl(m, "z", (x, 0.035), 0.035, z - 0.015, z + 0.015, "rubber_black", 8)
    box(m, (tx - 0.13, 0.03, -hz + 0.045), (tx + 0.13, 0.06, hz - 0.045), "book_grey")
    cbox(m, (tx + 0.05, 0.06, -hz + 0.05), (tx + 0.13, 0.15, hz - 0.05), "paint_blue", 0.01)
    box(m, (tx + 0.125, 0.1, -hz + 0.07), (tx + 0.131, 0.14, hz - 0.07), "glass_dark", "+x")
    loft(m, (tx - 0.13, tx + 0.04, -hz + 0.05, hz - 0.05, 0.06), (tx - 0.15, tx + 0.04, -hz + 0.045, hz - 0.045, 0.14),
         "book_mustard", inner=0.01)
    blob(m, (hx - 0.075, 0.075, 0.0), 0.075, 0.075, 0.075, "book_teal", 10, 5)


BUILDERS = {name[6:]: fn for name, fn in dict(globals()).items() if name.startswith("build_") and callable(fn)}


# --- extras for pack props -----------------------------------------------------------------------------------------
def extra_wall_mirror(m, p, bounds_lo, bounds_hi, R):
    """A mirror on the wall above a basin: a frame in the hardware's paint, a dark back and the glass."""
    H = p["size_m"][2]
    y0 = bounds_hi[1] + 0.25
    zb = bounds_lo[2]
    w = min(0.5, bounds_hi[0] - bounds_lo[0])
    cbox(m, (-w / 2, y0, zb), (w / 2, H, zb + 0.025), _r(R, 1))
    box(m, (-w / 2 + 0.03, y0 + 0.03, zb + 0.025), (w / 2 - 0.03, H - 0.03, zb + 0.032), "glass", "+z")


def extra_hood(m, p, bounds_lo, bounds_hi, R):
    """A cooker hood above a stove: a sloped canopy and its flue up to 1.9 m, in the stove's dark paint."""
    zb = bounds_lo[2]
    w = bounds_hi[0] - bounds_lo[0]
    loft(m, (-w / 2, w / 2, zb, zb + 0.5, 1.45), (-0.12, 0.12, zb, zb + 0.22, 1.62), _r(R, 1), top=True)
    box(m, (-0.12, 1.62, zb), (0.12, 1.9, zb + 0.22), _r(R, 1), "+x-x+y+z")


EXTRAS = {"wall_mirror": extra_wall_mirror, "hood": extra_hood}


# --- pack props: imported faces to paint ----------------------------------------------------------------------------
def cluster(colours: list, weights: list, k: int, iters: int = 12) -> list[int]:
    """k-means of linear RGB colours (weighted by face area); returns each colour's cluster index, the clusters
    numbered dark to light. Deterministic: the seeds are the weighted luminance quantiles."""
    if not colours:
        return []
    k = max(1, min(k, len(set(tuple(round(c, 4) for c in col) for col in colours))))
    order = sorted(range(len(colours)), key=lambda i: luminance(colours[i]))
    total = sum(weights) or 1.0
    seeds, acc, q = [], 0.0, 0
    for i in order:
        acc += weights[i]
        while q < k and acc >= total * (q + 0.5) / k:
            seeds.append(list(colours[i]))
            q += 1
    while len(seeds) < k:
        seeds.append(list(colours[order[-1]]))
    cent = seeds
    labels = [0] * len(colours)
    for _ in range(iters):
        for i, c in enumerate(colours):
            labels[i] = min(range(k), key=lambda j: sum((c[t] - cent[j][t]) ** 2 for t in range(3)))
        for j in range(k):
            w = sum(weights[i] for i in range(len(colours)) if labels[i] == j)
            if w > 0:
                cent[j] = [sum(colours[i][t] * weights[i] for i in range(len(colours)) if labels[i] == j) / w
                           for t in range(3)]
    rank = sorted(range(k), key=lambda j: luminance(cent[j]))
    remap = {j: r for r, j in enumerate(rank)}
    return [remap[label] for label in labels]


def pack_piece(p: dict, parts: list[dict], spec: dict) -> Piece:
    """A pack prop from its imported files (parts: verts in Godot axes, faces, linear RGB and area per face), stacked,
    turned by yaw_deg, scaled (uniform `scale`, or fitted per axis with `stretch`), painted by clustered colour."""
    verts, faces, cols, areas = [], [], [], []
    top = None
    for part in parts:
        vs = part["verts"]
        if top is not None and vs:
            dy = top - min(v[1] for v in vs)
            vs = [(v[0], v[1] + dy, v[2]) for v in vs]
        base = len(verts)
        verts += vs
        faces += [[base + i for i in f] for f in part["faces"]]
        cols += part["rgb"]
        areas += part["area"]
        if vs:
            top = max(v[1] for v in vs)
    a = math.radians(p.get("yaw_deg", 0))
    ca, sa = math.cos(a), math.sin(a)
    verts = [(x * ca + z * sa, y, -x * sa + z * ca) for x, y, z in verts]
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    want = p.get("pack_size_m", p["size_m"])
    want = (want[0], want[2], want[1])
    if p.get("stretch"):
        f = [want[i] / max(hi[i] - lo[i], EPS) for i in range(3)]
    else:
        f = [p["scale"]] * 3
    verts = [tuple(v[i] * f[i] for i in range(3)) for v in verts]
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    d = (-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2)  # the floor frame, so that extras can use the sizes
    verts = [(v[0] + d[0], v[1] + d[1], v[2] + d[2]) for v in verts]
    roles = list(p["roles"])
    dark_to_light = sorted(roles, key=lambda r: luminance(spec["roles"][r]["hex"]))
    if p.get("paint"):  # the roles of the source's colour clusters, dark to light (when luminance order is wrong)
        dark_to_light = list(p["paint"])
    labels = cluster(cols, areas, len(roles))
    k = max(labels) + 1 if labels else 1
    pick = [dark_to_light[round(j * (len(roles) - 1) / max(k - 1, 1))] if k < len(roles) else dark_to_light[j]
            for j in range(k)]
    pc = Piece(p["id"], "prop")
    m = pc.mesh
    for face, label in zip(faces, labels):
        pts = [verts[i] for i in face]
        if len({tuple(round(c, 6) for c in q) for q in pts}) < 3:
            continue
        m.poly(pts, kit_geom.polygon_normal(pts), pick[label])
    for name in p.get("extras", []):
        lo = [min(v[i] for v in m.verts) for i in range(3)]
        hi = [max(v[i] for v in m.verts) for i in range(3)]
        EXTRAS[name](m, p, lo, hi, roles)
    return pc


# --- the prop ------------------------------------------------------------------------------------------------------
def seed(pid: str) -> random.Random:
    return random.Random(zlib.crc32(pid.encode("utf-8")))


def build_proc(p: dict, style: Style | None = None) -> Piece:
    """A procedural prop from its builder; `style` is the library's [style] (Style.from_lib) for the world look's
    builders. A builder may name its own collider boxes (`_boxes`), which `finish` uses for `collision = "box"`."""
    if p["shape"] not in BUILDERS:
        raise ValueError(f"{p['id']}: no builder for shape {p['shape']!r}")
    pc = Piece(p["id"], "prop")
    L, W, H = p["size_m"]
    prm = dict(p.get("params", {}))
    prm["style"] = style or Style()
    BUILDERS[p["shape"]](pc.mesh, (L, W, H), list(p["roles"]), prm, seed(p["id"]))
    pc.part_boxes = prm.get("_boxes", [])
    return pc


def _move(m: Mesh, d) -> None:
    m.verts = [(round(v[0] + d[0], 6), round(v[1] + d[1], 6), round(v[2] + d[2], 6)) for v in m.verts]
    m._index = {v: i for i, v in enumerate(m.verts)}


MIN_FACE_AREA_M2 = 1e-10  # a face below this is degenerate: Blender's glTF export drops it, Godot never sees it


def clean(m: Mesh) -> int:
    """Drops repeated corners from every face, the faces left with under 3 corners or no area (a cone's point cap, a
    zero-length rod's end) and a second face on the same corners (two parts touching: Blender keeps the first), so
    the description counts the triangles the GLB holds. Returns the faces dropped."""
    faces, roles, seen = [], [], set()
    for f, r in zip(m.faces, m.roles):
        g = [v for k, v in enumerate(f) if v != f[k - 1]] if len(f) > 1 else list(f)
        key = frozenset(g)
        if len(key) < 3 or len(key) != len(g) or key in seen:
            continue
        n = kit_geom.polygon_normal([m.verts[v] for v in g])  # twice the vector area
        if 0.25 * sum(c * c for c in n) < MIN_FACE_AREA_M2 ** 2:
            continue
        seen.add(key)
        faces.append(g)
        roles.append(r)
    dropped = len(m.faces) - len(faces)
    m.faces, m.roles = faces, roles
    return dropped


def finish(pc: Piece, p: dict, spec: dict) -> None:
    """Drops degenerate faces (clean), moves the prop to its pivot, adds its collider (box, hull or none) and its
    light anchor (the centre of its emissive faces)."""
    m = pc.mesh
    clean(m)
    lo = [min(v[i] for v in m.verts) for i in range(3)]
    hi = [max(v[i] for v in m.verts) for i in range(3)]
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    pivot = p.get("pivot", "floor")
    if pivot == "wall":
        d = (-cx, -lo[1], -lo[2])
    elif pivot == "ceiling":
        d = (-cx, -hi[1], -cz)
    else:
        d = (-cx, -lo[1], -cz)
    _move(m, d)
    col = p.get("collision", "box")
    if col == "box" and getattr(pc, "part_boxes", None):
        for blo, bhi in pc.part_boxes:
            pc.collide_box([blo[i] + d[i] for i in range(3)], [bhi[i] + d[i] for i in range(3)])
    elif col == "box":
        pc.collide_box([lo[i] + d[i] for i in range(3)], [hi[i] + d[i] for i in range(3)])
    elif col == "hull":
        pc.collide([list(v) for v in m.verts])
    elif col != "none":
        raise ValueError(f"{p['id']}: unknown collision {col!r}")
    for k, c in enumerate(pc.colliders):
        c["name"] = f"{pc.id}_col{k}-convcolonly"
    lit = {i for f, r in zip(m.faces, m.roles) if is_emissive(spec, r) for i in f}
    pc.light_anchor = None
    if lit:
        pts = [m.verts[i] for i in lit]
        pc.light_anchor = [round(sum(q[i] for q in pts) / len(pts), 4) for i in range(3)]


def describe(pc: Piece, spec: dict) -> dict:
    """kit_geom.describe with the prop's lightmap margin and its light anchor."""
    verts = [v for m in pc.meshes for v in m.verts]
    b = kit_geom.bounds(verts)
    size = max(b["max"][i] - b["min"][i] for i in range(3))
    meshes = [{"name": m.name, "origin": list(m.origin), "verts": [list(v) for v in m.verts], "faces": m.faces,
               "roles": m.roles, "uv0": kit_geom.uv0(m, spec), "uv2": kit_geom.uv2(m, max(0.002, UV2_MARGIN * size)),
               "triangles": m.triangles()} for m in pc.meshes]
    cpts = [q for c in pc.colliders for q in c["points"]]
    out = {"id": pc.id, "kind": pc.kind, "meshes": meshes, "colliders": pc.colliders,
           "triangles": sum(m.triangles() for m in pc.meshes), "bounds_m": b,
           "collision_bounds_m": kit_geom.bounds(cpts) if cpts else None,
           "roles": sorted({r for m in pc.meshes for r in m.roles})}
    out["light_anchor"] = getattr(pc, "light_anchor", None)
    out["size_m"] = [round(out["bounds_m"]["max"][i] - out["bounds_m"]["min"][i], 4) for i in range(3)]
    return out


def build(p: dict, spec: dict, style: Style | None = None) -> dict:
    """A procedural prop, finished and described."""
    pc = build_proc(p, style)
    finish(pc, p, spec)
    return describe(pc, spec)


def size_error(d: dict, p: dict) -> list[float]:
    """The built size minus the inventory size per glTF axis (x, y, z); `built_size_m` when fixed parts reach past
    the inventory's box (the stove's hood, the sink's tap)."""
    size = p.get("built_size_m", p["size_m"])
    want = (size[0], size[2], size[1])
    return [round(d["size_m"][i] - want[i], 4) for i in range(3)]
