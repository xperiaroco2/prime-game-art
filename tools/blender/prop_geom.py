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

import kit_geom
from kit_geom import EPS, Mesh, Piece

CH = 0.004  # the chamfer of the soft boxes, metres (2 to 5 mm reads as clay in the lightmap)
UV2_MARGIN = 0.02  # the lightmap island margin as a share of the prop's largest size
LIGHT_ANCHOR = "LightAnchor"


# --- the spec: kit materials and roles plus the library's ---------------------------------------------------------
def lib_spec(lib: dict, kit: dict) -> dict:
    """A kit_geom-style spec: the kit's materials named by the library's [materials] table (plus the new ones, such
    as emissive, which have no detail texture), the kit's roles and the library's roles mapped to kit materials."""
    used = set(lib["materials"].values())
    mats = {}
    for name in sorted(used):
        if name in kit["materials"]:
            mats[name] = dict(kit["materials"][name])
        elif name in lib.get("new_materials", []):
            mats[name] = {"tile_m": 1.0, "roughness": 0.5, "emissive": name == "emissive"}
        else:
            raise ValueError(f"[materials] names {name!r}, which the kit lacks and new_materials does not add")
    for name, m in kit["materials"].items():
        mats.setdefault(name, dict(m))
    roles = {r: dict(v) for r, v in kit["roles"].items()}
    for r, v in lib["roles"].items():
        roles[r] = {"material": lib["materials"][v["material"]], "hex": v["hex"]}
    return {"materials": mats, "roles": roles}


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
        tube(m, "y", (dx, dz), L / 2 * 0.52, L / 2 - 0.012, h * i, h * (i + 1) - 0.004, R[0], 12)


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


def build_proc(p: dict) -> Piece:
    if p["shape"] not in BUILDERS:
        raise ValueError(f"{p['id']}: no builder for shape {p['shape']!r}")
    pc = Piece(p["id"], "prop")
    L, W, H = p["size_m"]
    BUILDERS[p["shape"]](pc.mesh, (L, W, H), list(p["roles"]), dict(p.get("params", {})), seed(p["id"]))
    return pc


def _move(m: Mesh, d) -> None:
    m.verts = [(round(v[0] + d[0], 6), round(v[1] + d[1], 6), round(v[2] + d[2], 6)) for v in m.verts]
    m._index = {v: i for i, v in enumerate(m.verts)}


def finish(pc: Piece, p: dict, spec: dict) -> None:
    """Moves the prop to its pivot, adds its collider (box, hull or none) and its light anchor (the centre of its
    emissive faces)."""
    m = pc.mesh
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
    if col == "box":
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


def build(p: dict, spec: dict) -> dict:
    """A procedural prop, finished and described."""
    pc = build_proc(p)
    finish(pc, p, spec)
    return describe(pc, spec)


def size_error(d: dict, p: dict) -> list[float]:
    """The built size minus the inventory size per glTF axis (x, y, z)."""
    want = (p["size_m"][0], p["size_m"][2], p["size_m"][1])
    return [round(d["size_m"][i] - want[i], 4) for i in range(3)]
