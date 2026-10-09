"""The House kit's geometry (art #74, docs/kit.md): every piece of kits/house.json as plain lists, standard library only,
so that the runner and the tests use it without Blender and tools/blender/kit_build.py only turns it into objects.

Axes are Godot's (metres, +Y up). A wall runs along +X from its pivot (the grid node), centred on the grid line, its
exterior (ext, "pos") side at +Z; a floor spans +X/+Z from its pivot with its top at y 0; a flight of stairs climbs
along +X across +Z [0, width]. Faces are planar polygons wound counter-clockwise seen from outside, each with a role
(a paint colour on one of the kit's materials). Faces where pieces meet (wall ends, wall tops under a slab) are left
out, so that neighbours snap without overlapping faces (no z-fighting).

Collision: closed convex hulls (8 corner points for a box), each exported as its own `<name>-convcolonly` node that
Godot turns into a StaticBody3D with a ConvexPolygonShape3D; group "solid" blocks movement and sight, group "glass"
blocks movement (a pane; the game decides whether sight passes).

UV0 is a box projection in metres (the textures tile per metre, so that they run on across neighbours on the grid);
UV2 (the lightmap UV) packs every face as its own island, uniformly scaled, with a margin.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

TEX_MEAN = 0.92  # the linear mean of every detail texture kit_build.py writes; vertex colours are divided by it
UV2_MARGIN_M = 0.12  # the gap around each lightmap island, in metres before the uniform scale
EPS = 1e-6

# The openings of the wall pieces, from the grid (kits/house.json "grid").
def openings(g: dict) -> dict:
    return {
        "door": {"w": g["door_w_m"], "y0": 0.0, "y1": g["door_h_m"], "casing": True},
        "window": {"w": g["window_w_m"], "y0": g["window_sill_m"], "y1": g["window_sill_m"] + g["window_h_m"], "casing": True},
        "window_knee": {"w": g["window_w_m"], "y0": g["window_sill_m"], "y1": g["window_sill_m"] + 0.8, "casing": True},
        "window_basement": {"w": g["window_w_m"], "y0": 2.2, "y1": 2.7, "casing": False},
    }


def load_spec(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def role_colour(spec: dict, role: str) -> list[float]:
    """The role's vertex colour (linear RGBA): its paint, divided by the detail texture's mean where it has one."""
    r = spec["roles"][role]
    mat = spec["materials"][r["material"]]
    h = r["hex"].lstrip("#")
    lin = [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]
    div = TEX_MEAN if mat.get("source") else 1.0
    return [round(min(1.0, c / div), 5) for c in lin] + [1.0]


# --- geometry helpers ----------------------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def polygon_normal(pts) -> tuple:
    """Newell's normal (not normalised) of a planar polygon."""
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return tuple(n)


class Mesh:
    """One exported mesh object: polygons with roles. origin is the object's pivot in piece coordinates (a leaf's hinge)."""

    def __init__(self, name: str, origin=(0.0, 0.0, 0.0)):
        self.name = name
        self.origin = tuple(origin)
        self.verts: list[tuple] = []
        self.faces: list[list[int]] = []
        self.roles: list[str] = []
        self._index: dict = {}

    def _v(self, p) -> int:
        key = tuple(round(c, 6) for c in p)
        if key not in self._index:
            self._index[key] = len(self.verts)
            self.verts.append(key)
        return self._index[key]

    def poly(self, pts, normal, role: str) -> None:
        """Adds a polygon, reversing it if needed so that it faces along normal."""
        pts = list(pts)
        if _dot(polygon_normal(pts), normal) < 0:
            pts.reverse()
        self.faces.append([self._v(p) for p in pts])
        self.roles.append(role)

    def box(self, lo, hi, role: str, faces: str = "+x-x+y-y+z-z", roles: dict | None = None) -> None:
        """An axis-aligned box; faces names the sides to emit ("+x", "-y", ...), roles overrides a side's role."""
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        if x1 - x0 < EPS or y1 - y0 < EPS or z1 - z0 < EPS:
            return
        sides = {
            "+x": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
            "-x": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
            "+y": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "-y": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
            "+z": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
            "-z": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
        }
        for key, (pts, n) in sides.items():
            if key in faces:
                self.poly(pts, n, (roles or {}).get(key, role))

    def quad_z(self, x0, x1, y0, y1, z, sign, role) -> None:
        """A rectangle in the plane z facing +Z (sign 1) or -Z (sign -1)."""
        if x1 - x0 > EPS and y1 - y0 > EPS:
            self.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], (0, 0, sign), role)

    def prism(self, poly2d, z0, z1, role: str, caps: tuple = ("-z", "+z"), cap_roles: dict | None = None,
              edges: list[bool] | None = None) -> None:
        """A convex polygon in XY (counter-clockwise) extruded over z0..z1; edges[i] emits the side after vertex i."""
        n = len(poly2d)
        if "-z" in caps:
            self.poly([(x, y, z0) for x, y in poly2d], (0, 0, -1), (cap_roles or {}).get("-z", role))
        if "+z" in caps:
            self.poly([(x, y, z1) for x, y in poly2d], (0, 0, 1), (cap_roles or {}).get("+z", role))
        for i in range(n):
            if edges is not None and not edges[i]:
                continue
            (ax, ay), (bx, by) = poly2d[i], poly2d[(i + 1) % n]
            if math.hypot(bx - ax, by - ay) < EPS:
                continue
            out = (by - ay, -(bx - ax), 0.0)  # the outward side of a counter-clockwise polygon
            self.poly([(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)], out, role)

    def triangles(self) -> int:
        return sum(len(f) - 2 for f in self.faces)


def box_points(lo, hi) -> list[list[float]]:
    return [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def prism_points(poly2d, z0, z1) -> list[list[float]]:
    return [[x, y, z] for x, y in poly2d for z in (z0, z1)]


class Piece:
    def __init__(self, pid: str, kind: str):
        self.id = pid
        self.kind = kind
        self.meshes: list[Mesh] = [Mesh(pid)]
        self.colliders: list[dict] = []

    @property
    def mesh(self) -> Mesh:
        return self.meshes[0]

    def leaf(self, name: str, origin) -> Mesh:
        m = Mesh(f"{self.id}_{name}", origin)
        self.meshes.append(m)
        return m

    def collide(self, points, group: str = "solid", parent: str | None = None) -> None:
        self.colliders.append({"group": group, "parent": parent, "points": [[round(c, 6) for c in p] for p in points]})

    def collide_box(self, lo, hi, group: str = "solid", parent: str | None = None) -> None:
        if all(hi[i] - lo[i] > EPS for i in range(3)):
            self.collide(box_points(lo, hi), group, parent)


# --- piece builders ------------------------------------------------------------------------------------------------
CASING_W, CASING_P = 0.08, 0.02  # door and window casings: width and how far they stand off the wall
SKIRT_H, SKIRT_P = 0.1, 0.015
FRAME_W, FRAME_D = 0.05, 0.03  # the window frame inside the reveal: width, half depth


def build_wall(pc: Piece, p: dict, spec: dict) -> None:
    g = spec["grid"]
    fin = spec["finishes"][p["finish"]]
    neg, pos = fin["neg"], fin["pos"]
    L, H, h2 = float(p["length"]), float(p["height"]), g["wall_t_m"] / 2
    skirting = p.get("skirting", fin["skirting"])
    band = p.get("band", fin["band"])
    m = pc.mesh
    op = openings(g)[p["opening"]] if p.get("opening") else None
    if op:
        x0, x1, y0, y1 = (L - op["w"]) / 2, (L + op["w"]) / 2, op["y0"], op["y1"]
        if y1 >= H - EPS:
            raise ValueError(f"{pc.id}: the opening's head {y1} m reaches the wall's height {H} m")
        rects = [(0, x0, 0, H), (x1, L, 0, H), (x0, x1, 0, y0), (x0, x1, y1, H)]
    else:
        rects = [(0, L, 0, H)]
    for xa, xb, ya, yb in rects:
        if xb - xa > EPS and yb - ya > EPS:
            m.quad_z(xa, xb, ya, yb, -h2, -1, neg)
            m.quad_z(xa, xb, ya, yb, h2, 1, pos)
            pc.collide_box((xa, ya, -h2), (xb, yb, h2))
    if band:  # the exterior skin runs down over the slab's edge, so the facade is continuous between storeys
        sl = g["slab_m"]
        m.quad_z(0, L, -sl, 0, h2, 1, pos)
        pc.collide_box((0, -sl, 0), (L, 0, h2))
    if op:
        m.poly([(x0, y0, -h2), (x0, y1, -h2), (x0, y1, h2), (x0, y0, h2)], (1, 0, 0), neg)
        m.poly([(x1, y0, -h2), (x1, y1, -h2), (x1, y1, h2), (x1, y0, h2)], (-1, 0, 0), neg)
        m.poly([(x0, y1, -h2), (x1, y1, -h2), (x1, y1, h2), (x0, y1, h2)], (0, -1, 0), neg)
        if y0 > EPS:
            m.poly([(x0, y0, -h2), (x1, y0, -h2), (x1, y0, h2), (x0, y0, h2)], (0, 1, 0), neg)
        if op["casing"]:
            for s in (-1, 1):
                za, zb = sorted((s * h2, s * (h2 + CASING_P)))
                out = "+z" if s > 0 else "-z"
                ylo = y0 - CASING_W if y0 > EPS else 0.0
                m.box((x0 - CASING_W, ylo, za), (x0, y1 + CASING_W, zb), "trim", f"{out}-x+x+y-y")
                m.box((x1, ylo, za), (x1 + CASING_W, y1 + CASING_W, zb), "trim", f"{out}-x+x+y-y")
                m.box((x0, y1, za), (x1, y1 + CASING_W, zb), "trim", f"{out}+y-y")
                if y0 > EPS:
                    m.box((x0, y0 - CASING_W, za), (x1, y0, zb), "trim", f"{out}+y-y")
        if y0 > EPS:  # a window: a frame inside the reveal and the pane
            fw, fd = FRAME_W, FRAME_D
            m.box((x0, y0, -fd), (x0 + fw, y1, fd), "trim", "+x-z+z")
            m.box((x1 - fw, y0, -fd), (x1, y1, fd), "trim", "-x-z+z")
            m.box((x0 + fw, y0, -fd), (x1 - fw, y0 + fw, fd), "trim", "+y-z+z")
            m.box((x0 + fw, y1 - fw, -fd), (x1 - fw, y1, fd), "trim", "-y-z+z")
            m.box((x0 + fw, y0 + fw, -0.004), (x1 - fw, y1 - fw, 0.004), "glass", "-z+z")
            pc.collide_box((x0, y0, -fd), (x1, y1, fd), "glass")
    if skirting:
        cut = (x0 - (CASING_W if op["casing"] else 0), x1 + (CASING_W if op["casing"] else 0)) if op and y0 < EPS else None
        segs = [(0, cut[0]), (cut[1], L)] if cut else [(0, L)]
        for s, role in ((-1, neg), (1, pos)):
            if role != "wall_int":
                continue
            za, zb = sorted((s * h2, s * (h2 + SKIRT_P)))
            out = "+z" if s > 0 else "-z"
            for xa, xb in segs:
                ends = ("-x" if xa > EPS else "") + ("+x" if xb < L - EPS else "")
                m.box((xa, 0, za), (xb, SKIRT_H, zb), "trim", out + "+y" + ends)


def build_corner(pc: Piece, p: dict, spec: dict) -> None:
    """The outer-corner filler: the h2 x h2 notch two walls leave at an outer corner, in the +X+Z quadrant."""
    g = spec["grid"]
    fin = spec["finishes"][p["finish"]]
    h2, H = g["wall_t_m"] / 2, float(p["height"])
    ylo = -g["slab_m"] if fin["band"] else 0.0
    pc.mesh.box((0, ylo, 0), (h2, H, h2), fin["pos"], "+x+z")
    pc.collide_box((0, ylo, 0), (h2, H, h2))
    if fin["skirting"] and fin["pos"] == "wall_int":
        pc.mesh.box((h2, 0, 0), (h2 + SKIRT_P, SKIRT_H, h2 + SKIRT_P), "trim", "+x+z+y")
        pc.mesh.box((0, 0, h2), (h2, SKIRT_H, h2 + SKIRT_P), "trim", "+z+y")


def build_end(pc: Piece, p: dict, spec: dict) -> None:
    """A cap closing a free wall end at x 0 (it stands 2 cm out of the wall run, so it overlaps no wall face)."""
    g = spec["grid"]
    fin = spec["finishes"][p["finish"]]
    h2, H = g["wall_t_m"] / 2, float(p["height"])
    lo, hi = (-0.02, 0, -h2), (0, H, h2)
    pc.mesh.box(lo, hi, fin["neg"], "-x+y+z-z", {"+z": fin["pos"]})
    pc.collide_box(lo, hi)


def build_gable(pc: Piece, p: dict, spec: dict) -> None:
    g = spec["grid"]
    fin = spec["finishes"][p["finish"]]
    L, R, h2 = float(p["length"]), float(p["rise"]), g["wall_t_m"] / 2
    poly = [(0, 0), (L, 0), (L, R)] if p["up"] == "+x" else [(0, 0), (L, 0), (0, R)]
    edges = [False, False, True] if p["up"] == "+x" else [False, True, False]
    pc.mesh.prism(poly, -h2, h2, fin["neg"], cap_roles={"-z": fin["neg"], "+z": fin["pos"]}, edges=edges)
    pc.collide(prism_points(poly, -h2, h2))


def build_floor(pc: Piece, p: dict, spec: dict) -> None:
    g = spec["grid"]
    w, d = (float(v) for v in p["size"])
    th = float(p.get("thick", g["slab_m"]))
    top, bottom = p["top"], p["bottom"]
    m = pc.mesh
    hole = p.get("hole")
    if hole:
        hx, hz, hw, hd = hole
        rects = [(0, w, 0, hz), (0, w, hz + hd, d), (0, hx, hz, hz + hd), (hx + hw, w, hz, hz + hd)]
    else:
        rects = [(0, w, 0, d)]
    for xa, xb, za, zb in rects:
        if xb - xa > EPS and zb - za > EPS:
            m.box((xa, -th, za), (xb, 0, zb), top, "+y-y", {"-y": bottom})
            pc.collide_box((xa, -th, za), (xb, 0, zb))
    # the outer edges (seen at a stairwell, a balcony or a hatch) and the hole's reveal
    m.box((0, -th, 0), (w, 0, d), bottom, "+x-x+z-z")
    if hole:
        hx, hz, hw, hd = hole
        x1, z1 = hx + hw, hz + hd
        m.poly([(hx, -th, hz), (hx, 0, hz), (hx, 0, z1), (hx, -th, z1)], (1, 0, 0), bottom)
        m.poly([(x1, -th, hz), (x1, 0, hz), (x1, 0, z1), (x1, -th, z1)], (-1, 0, 0), bottom)
        m.poly([(hx, -th, hz), (x1, -th, hz), (x1, 0, hz), (hx, 0, hz)], (0, 0, 1), bottom)
        m.poly([(hx, -th, z1), (x1, -th, z1), (x1, 0, z1), (hx, 0, z1)], (0, 0, -1), bottom)
        t = 0.06  # a trim frame on the floor around the hatch
        m.box((hx - t, 0, hz - t), (x1 + t, 0.015, hz), "trim", "+y-z+x-x")
        m.box((hx - t, 0, z1), (x1 + t, 0.015, z1 + t), "trim", "+y+z+x-x")
        m.box((hx - t, 0, hz), (hx, 0.015, z1), "trim", "+y-x")
        m.box((x1, 0, hz), (x1 + t, 0.015, z1), "trim", "+y+x")


def build_ceiling(pc: Piece, p: dict, spec: dict) -> None:
    w, d = (float(v) for v in p["size"])
    lo, hi = (0, -0.02, 0), (w, 0, d)
    pc.mesh.box(lo, hi, "ceiling", "-y+x-x+z-z")
    pc.collide_box(lo, hi)


def build_block(pc: Piece, p: dict, spec: dict) -> None:
    w, d = (float(v) for v in p["size"])
    lo, hi = (0, -float(p["height"]), 0), (w, 0, d)
    pc.mesh.box(lo, hi, p["side"], "+y+x-x+z-z", {"+y": p["top"]})
    pc.collide_box(lo, hi)


def build_parapet(pc: Piece, p: dict, spec: dict) -> None:
    g = spec["grid"]
    L, H, h2, rs = float(p["length"]), g["parapet_h_m"], g["wall_t_m"] / 2, g["roof_slab_m"]
    m = pc.mesh
    m.quad_z(0, L, 0, H, -h2, -1, "wall_ext")
    m.quad_z(0, L, -rs, H, h2, 1, "wall_ext")
    c = 0.14
    m.box((0, H, -c), (L, H + 0.06, c), "concrete", "+y+z-z")
    m.poly([(0, H, -c), (L, H, -c), (L, H, -h2), (0, H, -h2)], (0, -1, 0), "concrete")
    m.poly([(0, H, h2), (L, H, h2), (L, H, c), (0, H, c)], (0, -1, 0), "concrete")
    pc.collide_box((0, -rs, -h2), (L, H, h2))
    pc.collide_box((0, H, -c), (L, H + 0.06, c))


def build_parapet_corner(pc: Piece, p: dict, spec: dict) -> None:
    g = spec["grid"]
    H, h2, rs, c = g["parapet_h_m"], g["wall_t_m"] / 2, g["roof_slab_m"], 0.14
    m = pc.mesh
    m.box((0, -rs, 0), (h2, H, h2), "wall_ext", "+x+z")
    m.box((0, H, 0), (c, H + 0.06, c), "concrete", "+y+x+z")
    m.poly([(h2, H, 0), (c, H, 0), (c, H, c), (h2, H, c)], (0, -1, 0), "concrete")
    m.poly([(0, H, h2), (h2, H, h2), (h2, H, c), (0, H, c)], (0, -1, 0), "concrete")
    pc.collide_box((0, -rs, 0), (h2, H, h2))
    pc.collide_box((0, H, 0), (c, H + 0.06, c))


def stair_numbers(p: dict) -> tuple[float, float, int]:
    """(riser height, going, risers): n risers climb the rise; n - 1 treads cover the run, the last riser meets the
    upper floor at x = run."""
    n = int(p["risers"])
    return float(p["rise"]) / n, float(p["run"]) / (n - 1), n


def ramp_poly(p: dict) -> list[tuple]:
    """The walkable collision of a flight: through the nosings from the second step up to the upper floor's edge."""
    h, gq, n = stair_numbers(p)
    run, rise = float(p["run"]), float(p["rise"])
    return [(0, 0), (run, 0), (run, rise), (gq, 2 * h)]


def build_stairs(pc: Piece, p: dict, spec: dict) -> None:
    h, gq, n = stair_numbers(p)
    w = float(p["width"])
    m = pc.mesh
    for i in range(1, n):
        xa, xb, top = (i - 1) * gq, i * gq, i * h
        m.poly([(xa, top, 0), (xb, top, 0), (xb, top, w), (xa, top, w)], (0, 1, 0), p["tread"])
        m.poly([(xa, top - h, 0), (xa, top, 0), (xa, top, w), (xa, top - h, w)], (-1, 0, 0), p["body"])
        m.quad_z(xa, xb, 0, top, 0, -1, p["body"])
        m.quad_z(xa, xb, 0, top, w, 1, p["body"])
        if i == n - 1:
            m.poly([(xb, 0, 0), (xb, top, 0), (xb, top, w), (xb, 0, w)], (1, 0, 0), p["body"])
    pc.collide(prism_points(ramp_poly(p), 0, w))


def build_stairs_open(pc: Piece, p: dict, spec: dict) -> None:
    """The external balcony stairs: open treads on two metal stringers, a handrail on each side."""
    h, gq, n = stair_numbers(p)
    w, run, rise = float(p["width"]), float(p["run"]), float(p["rise"])
    s = h / gq
    m = pc.mesh
    st = 0.06
    for i in range(1, n):
        m.box(((i - 1) * gq, i * h - 0.05, st), (i * gq, i * h, w - st), "boards")
    stringer = [(0, 0), ((0.3 - h) / s, 0), (run, rise - 0.3), (run, rise), (0, h)]
    rail = [(0, h + 0.9), (run, rise + 0.9), (run, rise + 0.95), (0, h + 0.95)]
    rail = [rail[0], rail[1], rail[2], rail[3]]
    for za, zb in ((0, st), (w - st, w)):
        m.prism(stringer, za, zb, "metal")
        m.prism([(x, y) for x, y in [(0, h + 0.9), (run, rise + 0.9), (run, rise + 0.95), (0, h + 0.95)]],
                za + 0.005, zb - 0.005, "metal")
        for xp in (0.15, run / 2, run - 0.15):
            yb = h + xp * s
            m.box((xp - 0.025, yb, za + 0.01), (xp + 0.025, yb + 0.9, zb - 0.01), "metal", "+x-x+z-z")
        pc.collide(prism_points([(0, h), (run, rise), (run, rise + 0.95), (0, h + 0.95)], za, zb))
    pc.collide(prism_points(ramp_poly(p), st, w - st))
    del rail


def build_ladder(pc: Piece, p: dict, spec: dict) -> None:
    """The pull-down attic ladder: foot at the pivot, climbing along +X to the hatch's edge at (run, rise)."""
    wd, run, rise = float(p["width"]), float(p["run"]), float(p["rise"])
    m = pc.mesh
    rail = [(0, 0), (0.08, 0), (run + 0.08, rise), (run, rise)]
    for za, zb in ((0, 0.05), (wd - 0.05, wd)):
        m.prism(rail, za, zb, "trim")
    steps = 11
    for k in range(1, steps):
        y = k * rise / steps
        x = y * run / rise + 0.01
        m.box((x, y - 0.03, 0.05), (x + 0.1, y, wd - 0.05), "trim", "+x-x+y-y")
    pc.collide(prism_points([(0, 0), (0.12, 0), (run + 0.12, rise), (run, rise)], 0, wd))


def build_post(pc: Piece, p: dict, spec: dict) -> None:
    ps, H = float(p["post"]), float(p["height"])
    lo, hi = (-ps / 2, 0, -ps / 2), (ps / 2, H, ps / 2)
    pc.mesh.box(lo, hi, p["role"], "+x-x+y+z-z")
    pc.collide_box(lo, hi)


def build_railing(pc: Piece, p: dict, spec: dict) -> None:
    """A railing module: its post at x 0 (the next module's post, or a *_post piece, closes it), rails between."""
    L, H, role = float(p["length"]), float(p["height"]), p["role"]
    ps, bar, pitch = float(p["post"]), float(p["bar"]), float(p["pitch"])
    m = pc.mesh
    m.box((-ps / 2, 0, -ps / 2), (ps / 2, H, ps / 2), role, "+x-x+y+z-z")
    m.box((ps / 2, H - 0.05, -ps / 2), (L - ps / 2, H, ps / 2), role, "+y-y+z-z")
    m.box((ps / 2, 0.08, -bar * 0.75), (L - ps / 2, 0.12, bar * 0.75), role, "+y-y+z-z")
    k = 1
    while k * pitch < L - pitch / 2 + EPS:
        x = k * pitch
        m.box((x - bar / 2, 0.12, -bar / 2), (x + bar / 2, H - 0.05, bar / 2), role, "+x-x+z-z")
        k += 1
    pc.collide_box((0, 0, -ps / 2), (L, H, ps / 2))


def _fence_boards(m: Mesh, xa: float, xb: float, y0: float, y1: float, role: str = "fence") -> None:
    x = xa + 0.01
    while x + 0.12 <= xb - 0.01 + EPS:
        m.box((x, y0, 0.0), (x + 0.12, y1, 0.02), role, "+x-x+y+z-z")
        x += 0.14


def build_fence(pc: Piece, p: dict, spec: dict) -> None:
    g = spec["grid"]
    L, H = float(p["length"]), g["fence_h_m"]
    m = pc.mesh
    m.box((-0.05, 0, -0.05), (0.05, H + 0.1, 0.05), "fence", "+x-x+y+z-z")
    for y in (0.3, 1.4):
        m.box((0.05, y, -0.04), (L - 0.05, y + 0.08, 0.0), "fence", "+y-y-z")
    _fence_boards(m, 0.05, L - 0.05, 0.05, H)
    pc.collide_box((0, 0, -0.05), (L, H + 0.1, 0.05))


def build_wicket(pc: Piece, p: dict, spec: dict) -> None:
    """A 2 m fence module with a 1.4 m wicket between gate posts at 0.25 and 1.75; the leaf hinges at x 0.31."""
    g = spec["grid"]
    L, H, dw = float(p["length"]), g["fence_h_m"], g["door_w_m"]
    x0, x1 = (L - dw) / 2, (L + dw) / 2
    m = pc.mesh
    m.box((-0.05, 0, -0.05), (0.05, H + 0.1, 0.05), "fence", "+x-x+y+z-z")
    for xc in (x0 - 0.05, x1 + 0.05):
        m.box((xc - 0.05, 0, -0.05), (xc + 0.05, H + 0.2, 0.05), "fence", "+x-x+y+z-z")
        pc.collide_box((xc - 0.05, 0, -0.05), (xc + 0.05, H + 0.2, 0.05))
    for xa, xb in ((0.05, x0 - 0.1), (x1 + 0.1, L - 0.05)):
        for y in (0.3, 1.4):
            m.box((xa, y, -0.04), (xb, y + 0.08, 0.0), "fence", "+y-y-z")
        _fence_boards(m, xa, xb, 0.05, H)
        pc.collide_box((xa, 0, -0.05), (xb, H, 0.05))
    pc.collide_box((-0.05, 0, -0.05), (0.05, H + 0.1, 0.05))
    leaf = pc.leaf("leaf", (x0 + 0.01, 0, 0))
    for y in (0.3, 1.3):
        leaf.box((x0 + 0.01, y, -0.04), (x1 - 0.01, y + 0.08, 0.0), "fence", "+y-y-z+x-x")
    _fence_boards(leaf, x0 + 0.01, x1 - 0.01, 0.1, H - 0.1)
    pc.collide_box((x0 + 0.01, 0.1, -0.04), (x1 - 0.01, H - 0.1, 0.02), parent=leaf.name)


def build_gates(pc: Piece, p: dict, spec: dict) -> None:
    """The driveway gates: a post at x 0 and two metal leaves hinged at x 0.1 and L - 0.1."""
    g = spec["grid"]
    L, H = float(p["length"]), g["fence_h_m"]
    m = pc.mesh
    m.box((-0.075, 0, -0.075), (0.075, H + 0.2, 0.075), "metal", "+x-x+y+z-z")
    pc.collide_box((-0.075, 0, -0.075), (0.075, H + 0.2, 0.075))
    half = L / 2
    for name, xa, xb, hinge in (("leaf_l", 0.1, half - 0.02, 0.1), ("leaf_r", half + 0.02, L - 0.1, L - 0.1)):
        lf = pc.leaf(name, (hinge, 0, 0))
        lf.box((xa, 0.1, -0.025), (xa + 0.06, H, 0.025), "metal", "+x-x+y-y+z-z")
        lf.box((xb - 0.06, 0.1, -0.025), (xb, H, 0.025), "metal", "+x-x+y-y+z-z")
        for ya in (0.1, H - 0.06):
            lf.box((xa + 0.06, ya, -0.025), (xb - 0.06, ya + 0.06, 0.025), "metal", "+y-y+z-z")
        x = xa + 0.06 + 0.12
        while x < xb - 0.06 - 0.06:
            lf.box((x - 0.0125, 0.16, -0.0125), (x + 0.0125, H - 0.06, 0.0125), "metal", "+x-x+z-z")
            x += 0.12
        pc.collide_box((xa, 0.1, -0.025), (xb, H, 0.025), parent=lf.name)


def build_glass(pc: Piece, p: dict, spec: dict) -> None:
    """A greenhouse glass wall: a concrete kerb, metal mullions (one at x 0, one mid-way), a top beam and panes."""
    g = spec["grid"]
    L, H, h2 = float(p["length"]), g["glass_wall_h_m"], g["wall_t_m"] / 2
    m = pc.mesh
    kerb, mw, beam = 0.3, 0.03, 0.06
    door = p.get("opening") == "door"
    x0, x1 = ((L - g["door_w_m"]) / 2, (L + g["door_w_m"]) / 2) if door else (None, None)
    kerbs = [(0, x0), (x1, L)] if door else [(0, L)]
    for xa, xb in kerbs:
        ends = ("-x" if xa > EPS else "") + ("+x" if xb < L - EPS else "")
        m.box((xa, 0, -h2), (xb, kerb, h2), "concrete", "+y+z-z" + ends)
        pc.collide_box((xa, 0, -h2), (xb, kerb, h2))
    posts = [0.0] + ([x0 - mw, x1 + mw] if door else ([L / 2] if L > 1.5 else []))
    for xc in posts:
        yb = 0.0 if door and xc != 0.0 else kerb
        m.box((xc - mw, yb, -mw), (xc + mw, H, mw), "metal", "+x-x+y+z-z")
        pc.collide_box((xc - mw, yb, -mw), (xc + mw, H, mw))
    m.box((mw, H - beam, -0.04), (L - mw, H, 0.04), "metal", "+y-y+z-z")
    pc.collide_box((0, H - beam, -0.04), (L, H, 0.04))
    if door:
        head = g["door_h_m"]
        m.box((x0, head, -mw), (x1, head + beam, mw), "metal", "+y-y+z-z")
        panes = [(mw, x0 - 2 * mw, kerb), (x1 + 2 * mw, L - mw, kerb), (x0, x1, head + beam)]
        leaf = pc.leaf("leaf", (x0 + 0.01, 0, 0))
        la, lb, lt = x0 + 0.01, x1 - 0.01, head - 0.01
        leaf.box((la, 0.01, -0.02), (la + 0.06, lt, 0.02), "metal")
        leaf.box((lb - 0.06, 0.01, -0.02), (lb, lt, 0.02), "metal")
        leaf.box((la + 0.06, 0.01, -0.02), (lb - 0.06, 0.2, 0.02), "metal", "+y-y+z-z")
        leaf.box((la + 0.06, lt - 0.06, -0.02), (lb - 0.06, lt, 0.02), "metal", "+y-y+z-z")
        leaf.box((la + 0.06, 0.2, -0.004), (lb - 0.06, lt - 0.06, 0.004), "glass", "-z+z")
        pc.collide_box((la, 0.01, -0.02), (lb, lt, 0.02), "glass", parent=leaf.name)
    else:
        panes = [(a + mw, b - mw, kerb) for a, b in zip(posts, posts[1:] + [L])]
    for xa, xb, yb in panes:
        m.box((xa, yb, -0.004), (xb, H - beam, 0.004), "glass", "-z+z")
        pc.collide_box((xa, yb, -0.004), (xb, H - beam, 0.004), "glass")


def build_garage_door(pc: Piece, p: dict, spec: dict) -> None:
    """The garage's 8 m door: the header of the storey wall above a sectional panel (its own node, "door")."""
    g = spec["grid"]
    L, H, dh, h2 = float(p["length"]), float(p["height"]), float(p["door_h"]), g["wall_t_m"] / 2
    m = pc.mesh
    m.quad_z(0, L, dh, H, -h2, -1, "wall_int")
    m.quad_z(0, L, dh, H, h2, 1, "wall_ext")
    m.quad_z(0, L, -g["slab_m"], 0, h2, 1, "wall_ext")
    m.poly([(0, dh, -h2), (L, dh, -h2), (L, dh, h2), (0, dh, h2)], (0, -1, 0), "wall_int")
    pc.collide_box((0, dh, -h2), (L, H, h2))
    door = pc.leaf("door", (0, dh, 0))
    door.box((0, 0, -0.03), (L, dh, 0.03), "metal", "+z-z")
    for k in range(1, 4):
        y = k * dh / 4
        door.box((0, y - 0.015, 0.03), (L, y + 0.015, 0.036), "metal", "+z+y-y")
    pc.collide_box((0, 0, -0.03), (L, dh, 0.03), parent=door.name)


BUILDERS = {
    "wall": build_wall, "corner": build_corner, "end": build_end, "gable": build_gable, "floor": build_floor,
    "ceiling": build_ceiling, "block": build_block, "parapet": build_parapet, "parapet_corner": build_parapet_corner,
    "stairs": build_stairs, "stairs_open": build_stairs_open, "ladder": build_ladder, "post": build_post,
    "railing": build_railing, "fence": build_fence, "wicket": build_wicket, "gates": build_gates,
    "glass": build_glass, "garage_door": build_garage_door,
}


# --- UVs -----------------------------------------------------------------------------------------------------------
def _axis(n) -> int:
    a = [abs(c) for c in n]
    return a.index(max(a))


def project(p, n) -> tuple[float, float]:
    """Box projection in metres by the face's dominant axis."""
    ax = _axis(n)
    if ax == 0:
        return (p[2] if n[0] < 0 else -p[2], p[1])
    if ax == 1:
        return (p[0], p[2] if n[1] < 0 else -p[2])
    return (p[0] if n[2] > 0 else -p[0], p[1])


def uv0(mesh: Mesh, spec: dict) -> list[list[list[float]]]:
    out = []
    for face, role in zip(mesh.faces, mesh.roles):
        tile = spec["materials"][spec["roles"][role]["material"]].get("tile_m", 1.0)
        pts = [mesh.verts[i] for i in face]
        n = polygon_normal(pts)
        out.append([[round(c / tile, 5) for c in project(p, n)] for p in pts])
    return out


def uv2(mesh: Mesh, margin: float = UV2_MARGIN_M) -> list[list[list[float]]]:
    """Every face its own island (projected in metres), shelf-packed into the unit square at one uniform scale."""
    islands = []
    for face in mesh.faces:
        pts = [mesh.verts[i] for i in face]
        n = polygon_normal(pts)
        q = [project(p, n) for p in pts]
        lo = (min(a for a, _ in q), min(b for _, b in q))
        hi = (max(a for a, _ in q), max(b for _, b in q))
        islands.append(([(a - lo[0], b - lo[1]) for a, b in q], hi[0] - lo[0], hi[1] - lo[1]))
    if not islands:
        return []
    area = sum((w + 2 * margin) * (h + 2 * margin) for _, w, h in islands)
    width = max(max(w for _, w, _ in islands) + 2 * margin, math.sqrt(area) * 1.15)
    order = sorted(range(len(islands)), key=lambda i: -islands[i][2])
    place, x, y, row = {}, 0.0, 0.0, 0.0
    for i in order:
        _, w, h = islands[i]
        if x + w + 2 * margin > width + EPS:
            x, y, row = 0.0, y + row, 0.0
        place[i] = (x + margin, y + margin)
        x += w + 2 * margin
        row = max(row, h + 2 * margin)
    scale = 1.0 / max(width, y + row)
    return [[[round((a + place[i][0]) * scale, 6), round((b + place[i][1]) * scale, 6)] for a, b in islands[i][0]]
            for i in range(len(islands))]


# --- the kit -------------------------------------------------------------------------------------------------------
def build_piece(p: dict, spec: dict) -> Piece:
    if p["type"] not in BUILDERS:
        raise ValueError(f"{p['id']}: unknown piece type {p['type']}")
    pc = Piece(p["id"], p["kind"])
    BUILDERS[p["type"]](pc, p, spec)
    for k, c in enumerate(pc.colliders):
        c["name"] = f"{pc.id}_{'glass' if c['group'] == 'glass' else 'col'}{k}-convcolonly"
    return pc


def bounds(points) -> dict:
    pts = list(points)
    return {"min": [round(min(p[i] for p in pts), 4) for i in range(3)],
            "max": [round(max(p[i] for p in pts), 4) for i in range(3)]}


def describe(pc: Piece, spec: dict) -> dict:
    """The piece as kit_build.py builds it and the piece table reports it."""
    meshes = []
    for m in pc.meshes:
        meshes.append({
            "name": m.name, "origin": list(m.origin), "verts": [list(v) for v in m.verts], "faces": m.faces,
            "roles": m.roles, "uv0": uv0(m, spec), "uv2": uv2(m), "triangles": m.triangles(),
        })
    verts = [v for m in pc.meshes for v in m.verts]
    return {
        "id": pc.id, "kind": pc.kind, "meshes": meshes, "colliders": pc.colliders,
        "triangles": sum(m.triangles() for m in pc.meshes),
        "bounds_m": bounds(verts),
        "collision_bounds_m": bounds(p for c in pc.colliders for p in c["points"]),
        "roles": sorted({r for m in pc.meshes for r in m.roles}),
    }


def build_kit(spec: dict) -> list[dict]:
    return [describe(build_piece(p, spec), spec) for p in spec["pieces"]]


# --- checks --------------------------------------------------------------------------------------------------------
def nominal_size(p: dict, spec: dict) -> dict:
    """The grid footprint a piece is placed by: (length along X, depth along Z) in metres, or None for a node piece."""
    if "length" in p:
        return {"x": float(p["length"]), "z": None}
    if "size" in p:
        return {"x": float(p["size"][0]), "z": float(p["size"][1])}
    if "run" in p:
        return {"x": float(p["run"]), "z": float(p["width"])}
    return {"x": None, "z": None}


def check_spec(spec: dict) -> list[str]:
    problems = []
    g = spec["grid"]
    if abs(g["slab_m"] + g["storey_wall_h_m"] - g["floor_to_floor_m"]) > EPS:
        problems.append("grid: slab_m + storey_wall_h_m is not floor_to_floor_m")
    ids = [p["id"] for p in spec["pieces"]]
    for pid in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"{pid}: the id is used twice")
    for name, r in spec["roles"].items():
        if r["material"] not in spec["materials"]:
            problems.append(f"role {name}: no material {r['material']}")
    for p in spec["pieces"]:
        if p["type"] not in BUILDERS:
            problems.append(f"{p['id']}: unknown type {p['type']}")
        if p.get("kind") not in spec["budget_tris"]:
            problems.append(f"{p['id']}: kind {p.get('kind')} has no triangle budget")
        size = nominal_size(p, spec)
        for axis in ("x", "z"):
            v = size[axis]
            if v is not None and p["type"] not in ("ladder",) and abs(v - round(v)) > EPS:
                problems.append(f"{p['id']}: its {axis} size {v} m is not whole metres")
        if "length" in p and p["type"] in ("wall", "parapet", "railing", "fence", "glass", "gable") \
                and int(p["length"]) not in g["modules_m"]:
            problems.append(f"{p['id']}: length {p['length']} m is not a {g['modules_m']} m module")
        for key in ("finish",):
            if key in p and p[key] not in spec["finishes"]:
                problems.append(f"{p['id']}: no finish {p[key]}")
    return problems


def check_piece(d: dict, p: dict, spec: dict) -> list[str]:
    """Grid, collision and budget checks of one described piece (pure Python; the GLB and Godot checks are separate)."""
    problems = []
    pid = d["id"]
    budget = spec["budget_tris"][p["kind"]]
    if d["triangles"] > budget:
        problems.append(f"{pid}: {d['triangles']} triangles, over the {p['kind']} budget of {budget}")
    if not d["colliders"]:
        problems.append(f"{pid}: no collision")
    for c in d["colliders"]:
        pts = c["points"]
        lo, hi = bounds(pts)["min"], bounds(pts)["max"]
        if any(hi[i] - lo[i] < 0.003 for i in range(3)):
            problems.append(f"{pid}: collider {c['name']} is flat ({lo} .. {hi})")
    for m in d["meshes"]:
        if len(m["uv2"]) != len(m["faces"]):
            problems.append(f"{pid}: {m['name']} lacks UV2 on some faces")
        for face in m["uv2"]:
            if any(not (-EPS <= c <= 1 + EPS) for uv in face for c in uv):
                problems.append(f"{pid}: {m['name']} has UV2 outside 0..1")
                break
    size = nominal_size(p, spec)
    b = d["bounds_m"]
    if size["x"] is not None and p["type"] not in ("ladder",):
        lo_ok = b["min"][0] >= -0.08 - EPS
        # a module may stop short of its end node by up to 0.12 m (the next module's post closes it)
        hi_ok = b["max"][0] <= size["x"] + 0.08 + EPS and b["max"][0] >= size["x"] - 0.12 - EPS
        if not (lo_ok and hi_ok):
            problems.append(f"{pid}: x extent {b['min'][0]}..{b['max'][0]} m is not on its {size['x']} m module")
    if size["z"] is not None and p["type"] in ("floor", "ceiling", "block", "stairs", "stairs_open"):
        if abs(b["min"][2]) > EPS or abs(b["max"][2] - size["z"]) > EPS:
            problems.append(f"{pid}: z extent {b['min'][2]}..{b['max'][2]} m is not its {size['z']} m depth")
    return problems


def piece_table(described: list[dict]) -> list[dict]:
    rows = []
    for d in described:
        b = d["bounds_m"]
        rows.append({
            "id": d["id"], "kind": d["kind"], "triangles": d["triangles"],
            "size_m": [round(b["max"][i] - b["min"][i], 3) for i in range(3)],
            "bounds_m": b, "colliders": len(d["colliders"]),
            "glass_colliders": sum(1 for c in d["colliders"] if c["group"] == "glass"),
            "nodes": [m["name"] for m in d["meshes"]],
        })
    return rows
