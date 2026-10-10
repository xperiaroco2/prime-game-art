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
        # a gable window (art #77): in a gable band, sill and height from the band's foot
        "window_gable": {"w": g["window_w_m"], "y0": g["gable_window_sill_m"],
                         "y1": g["gable_window_sill_m"] + g["gable_window_h_m"], "casing": True},
    }


def load_spec(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def role_colour(spec: dict, role: str) -> list[float]:
    """The role's vertex colour, sRGB-encoded RGBA: its paint, divided (in linear) by the detail texture's mean where it
    has one. sRGB because the kit's materials carry Godot's `-vcol` suffix, which makes the importer read COLOR_0 as
    sRGB (docs/kit.md, "Paint")."""
    r = spec["roles"][role]
    mat = spec["materials"][r["material"]]
    h = r["hex"].lstrip("#")
    lin = [srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]
    div = TEX_MEAN if mat.get("source") else 1.0
    return [round(linear_to_srgb(min(1.0, c / div)), 5) for c in lin] + [layer_alpha(spec, r["material"])]


def layer_alpha(spec: dict, material: str) -> float:
    """The vertex colour's alpha: which layer of its pack a material is (look.md section 5: plaster, wood and concrete
    share one `set` material; the shader picks the layer's detail by alpha: 1.0, 0.75, 0.5, 0.25). 1.0 unpacked."""
    pack = spec["materials"][material].get("pack")
    if not pack:
        return 1.0
    return round(1.0 - 0.25 * spec["packs"][pack]["layers"].index(material), 5)


def export_material(spec: dict, material: str) -> str:
    """The material a kit material is exported as: its pack, or itself."""
    return spec["materials"][material].get("pack", material)


def export_materials(spec: dict) -> list[str]:
    out = []
    for name in spec["materials"]:
        e = export_material(spec, name)
        if e not in out:
            out.append(e)
    return out


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
        self.sockets: dict[str, list[float]] = {}  # named points a fixture or prop hangs from (the porch's lamp)

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
                # the casing stops at the wall's top (a knee wall's door head leaves only 5 cm; v1 stood above it)
                ytop = min(y1 + CASING_W, H)
                top = "+y" if ytop < H - EPS else ""
                m.box((x0 - CASING_W, ylo, za), (x0, ytop, zb), "trim", f"{out}-x+x{top}-y")
                m.box((x1, ylo, za), (x1 + CASING_W, ytop, zb), "trim", f"{out}-x+x{top}-y")
                m.box((x0, y1, za), (x1, ytop, zb), "trim", f"{out}{top}-y")
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
    ylo = -g["slab_m"] if p.get("band", fin["band"]) else 0.0  # the wall's band runs over the slab's edge; so does its cap
    lo, hi = (-0.02, ylo, -h2), (0, H, h2)
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
    # no outer side faces: two tiles would put them back to back at every seam (v1); a free edge (a stairwell, a
    # balcony) is closed by a slab_edge piece. The hole's reveal is the tile's own.
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
    """Only an underside: `thick` under the pivot (default 0.02, a plaster ceiling) in `role`; the collider fills it.
    The yard slab over the basement (#108) is 0.2 m of bare concrete whose top is the yard's ground sheet (no top
    face, so nothing z-fights with it)."""
    w, d = (float(v) for v in p["size"])
    lo, hi = (0, -float(p.get("thick", 0.02)), 0), (w, 0, d)
    pc.mesh.box(lo, hi, p.get("role", "ceiling"), "-y")
    pc.collide_box(lo, hi)


def build_beam(pc: Piece, p: dict, spec: dict) -> None:
    """A downstand beam under a slab (#108): along +X over `length`, centred on z 0, `width` wide, its top at y 0 (the
    slab's underside) and `depth` deep; no end faces (it runs into a wall or the next module)."""
    L, hw, dp = float(p["length"]), float(p["width"]) / 2, float(p["depth"])
    lo, hi = (0, -dp, -hw), (L, 0, hw)
    pc.mesh.box(lo, hi, p.get("role", "basement"), "-y+z-z")
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
    """A ladder or a ship stair: foot at the pivot, climbing along +X to the top edge at (run, rise), its width along
    +Z. The pull-down attic ladder takes the defaults (11 rungs, 0.1 m deep, no handrails); the dormer's climb-out
    stair (art #77) sets `steps`, `tread` (each tread's depth, centred on the slope's line, so the collision's ramp
    runs through the treads) and `handrail` (a rail 0.9 m over each stringer). The collision is a slab under the
    slope's line from (0, 0) to (run, rise), cut plumb at x = run."""
    wd, run, rise = float(p["width"]), float(p["run"]), float(p["rise"])
    steps, tread = int(p.get("steps", 11)), float(p.get("tread", 0.1))
    stair = tread > 0.1
    st, deep, back = (0.06, 0.22, tread / 2) if stair else (0.05, 0.08, 0.0)  # stringer: thickness, depth, offset
    m = pc.mesh
    rail = [(-back, 0), (deep - back, 0), (run + deep - back, rise), (run - back, rise)]
    for za, zb in ((0, st), (wd - st, wd)):
        m.prism(rail, za, zb, "trim")
    for k in range(1, steps):
        y = k * rise / steps
        x = y * run / rise + 0.01 - back
        m.box((x, y - 0.03, st), (x + tread, y, wd - st), "trim", "+x-x+y-y")
    if p.get("handrail"):
        for za, zb in ((0, st), (wd - st, wd)):
            m.prism([(0, 0.85), (run, rise + 0.85), (run, rise + 0.9), (0, 0.9)], za, zb, "metal")
            for t in (0.1, 0.5, 0.9):
                x, y = run * t, rise * t
                m.box((x, y, za), (x + 0.04, y + 0.86, zb), "metal", "+x-x+z-z")
    # the slab ends plumb at the top edge: nothing pokes past it (through the dormer's window, art #77)
    pc.collide(prism_points([(0, 0), (deep + 0.04, 0), (run, rise * (1 - (deep + 0.04) / run)), (run, rise)], 0, wd))


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


# --- version 2 (art #86): rotated parts, pillars, pitched and glass roofs, porch, chimney, gazebo, node pieces -------
def rot_y(p, deg: float) -> tuple:
    """Godot's rotation about +Y by deg (a +90 deg turn takes +X to -Z)."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


def place(p, deg: float = 0.0, offset=(0.0, 0.0, 0.0)) -> tuple:
    q = rot_y(p, deg)
    return (q[0] + offset[0], q[1] + offset[1], q[2] + offset[2])


def merge(dst: Mesh, src: Mesh, deg: float = 0.0, offset=(0.0, 0.0, 0.0)) -> None:
    """Appends src's faces to dst, turned by deg about +Y and moved by offset."""
    for face, role in zip(src.faces, src.roles):
        dst.faces.append([dst._v(place(src.verts[i], deg, offset)) for i in face])
        dst.roles.append(role)


def _outward_sides(m: Mesh, poly, lift, role, edges=None, edge_roles=None) -> None:
    """The sides of a convex polygon extruded by lift(point2d, t) (t 0 and 1 the two ends); each side faces away from
    the polygon's centroid."""
    n = len(poly)
    cx, cy = sum(a for a, _ in poly) / n, sum(b for _, b in poly) / n
    cen = lift((cx, cy), 0.5)
    for i in range(n):
        if edges is not None and not edges[i]:
            continue
        a, b = poly[i], poly[(i + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < EPS:
            continue
        pts = [lift(a, 0), lift(b, 0), lift(b, 1), lift(a, 1)]
        mid = [sum(p[k] for p in pts) / 4 for k in range(3)]
        m.poly(pts, _sub(mid, cen), (edge_roles or {}).get(i, role))


def prism_x(m: Mesh, poly_zy, x0, x1, role, caps: str = "-x+x", cap_role=None, edges=None, edge_roles=None) -> None:
    """A convex polygon in the ZY plane (points (z, y)) extruded along X over x0..x1."""
    if "-x" in caps:
        m.poly([(x0, y, z) for z, y in poly_zy], (-1, 0, 0), cap_role or role)
    if "+x" in caps:
        m.poly([(x1, y, z) for z, y in poly_zy], (1, 0, 0), cap_role or role)
    _outward_sides(m, poly_zy, lambda q, t: (x0 + (x1 - x0) * t, q[1], q[0]), role, edges, edge_roles)


def prism_y(m: Mesh, poly_xz, y0, y1, role, caps: str = "", cap_role=None, edges=None) -> None:
    """A convex polygon in the XZ plane extruded along Y over y0..y1."""
    if "-y" in caps:
        m.poly([(x, y0, z) for x, z in poly_xz], (0, -1, 0), cap_role or role)
    if "+y" in caps:
        m.poly([(x, y1, z) for x, z in poly_xz], (0, 1, 0), cap_role or role)
    _outward_sides(m, poly_xz, lambda q, t: (q[0], y0 + (y1 - y0) * t, q[1]), role, edges)


def prism_x_points(poly_zy, x0, x1) -> list[list[float]]:
    return [[x, y, z] for z, y in poly_zy for x in (x0, x1)]


def prism_y_points(poly_xz, y0, y1) -> list[list[float]]:
    return [[x, y, z] for x, z in poly_xz for y in (y0, y1)]


def chamfered_square(half: float, ch: float) -> list[tuple]:
    h, c = half, half - ch
    return [(c, -h), (h, -c), (h, c), (c, h), (-c, h), (-h, c), (-h, -c), (-c, -h)]


def build_pillar(pc: Piece, p: dict, spec: dict) -> None:
    """A free-standing pillar centred on its grid node, floor (y 0) to the slab's underside; chamfered edges."""
    half, H = float(p["section"]) / 2, float(p["height"])
    poly = chamfered_square(half, float(p.get("chamfer", 0.03)))
    prism_y(pc.mesh, poly, 0.0, H, p.get("role", "concrete"))
    pc.collide(prism_y_points(poly, 0.0, H))


def pitch(spec: dict) -> dict:
    """The pitched roofs' planes (docs/kit.md, "Pitched roofs"): rise r per metre (grid gable_rise_per_m, shared with
    the gables; Q2); the slab's underside lies u under the line y = r * z that the gables' tops follow from the eave
    wall's grid node (2 cm under the knee wall's inner top edge, so the slab hides the wall's and the gables' tops);
    tv is the slab's vertical thickness."""
    g = spec["grid"]
    r, h2 = g["gable_rise_per_m"], g["wall_t_m"] / 2
    t = g["pitched_roof_t_m"]
    return {"r": r, "u": -(r * h2 + 0.02), "tv": t * math.sqrt(1 + r * r), "t": t,
            "deg": round(math.degrees(math.atan(r)), 2)}


def glass_rise(spec: dict) -> float:
    """The greenhouse glass roof's rise per metre (grid glass_rise_per_m): its own pitch since the house roof went to
    0.35 (art #77, Q2 B); a spec without it keeps the shared gable_rise_per_m."""
    g = spec["grid"]
    return float(g.get("glass_rise_per_m", g["gable_rise_per_m"]))


def build_pitched(pc: Piece, p: dict, spec: dict) -> None:
    """A pitched roof slab (the attic): x over p["x"] along the eave, z over p["z"] up the slope (horizontal metres from
    the eave wall's grid line). Pivot: the eave wall's grid node at the knee wall's top. Plumb-cut ends; p["ends"] names
    the open ends it closes with a trim board (eave "-z", verge "-x" or "+x"); the others meet neighbours."""
    pp = pitch(spec)
    r, u, tv = pp["r"], pp["u"], pp["tv"]
    (x0, x1), (z0, z1) = p["x"], p["z"]
    ends = p.get("ends", "")
    prof = [(z0, u + r * z0), (z1, u + r * z1), (z1, u + tv + r * z1), (z0, u + tv + r * z0)]
    prism_x(pc.mesh, prof, x0, x1, p.get("under", "boards"), caps="".join(e for e in ("-x", "+x") if e in ends),
            cap_role="trim", edges=[True, "+z" in ends, False, "-z" in ends], edge_roles={1: "trim", 3: "trim"})
    pantile_courses(pc.mesh, x0, x1, z0, z1, lambda z: u + tv + r * z, ends)
    pc.collide(prism_x_points(prof, x0, x1))
    if "-z" in ends and p.get("overhang"):
        gutter(pc.mesh, x0, x1, z0, u + tv + r * z0 - GUTTER_DROP, ends)
        snow_guard(pc.mesh, x0, x1, lambda z: u + tv + r * z, ends)


SNOW_GUARD_Z, SNOW_GUARD_H, SNOW_GUARD_STEP = -0.2, 0.12, 0.5  # its line on the eave's overhang (z from the eave
# wall's line), the rail's top over the slab's top, the brackets' spacing along the eave


def snow_guard(m: Mesh, x0, x1, base, ends: str = "") -> None:
    """The snow guard on an eave piece (art #77): a zinc rail SNOW_GUARD_H over the slab's top at z SNOW_GUARD_Z (on
    the overhang, above the gutter), on metal brackets every SNOW_GUARD_STEP from the tiles. No collider."""
    z, yt = SNOW_GUARD_Z, base(SNOW_GUARD_Z) + SNOW_GUARD_H
    m.box((x0, yt - 0.025, z - 0.01), (x1, yt, z + 0.01), "zinc",
          "+y-y+z-z" + "".join(e for e in ("-x", "+x") if e in ends))
    xb = math.floor(x0 / SNOW_GUARD_STEP) * SNOW_GUARD_STEP + SNOW_GUARD_STEP / 2
    while xb < x1 - 0.03:
        if xb > x0 + 0.03:
            m.box((xb - 0.01, base(z) + 0.02, z - 0.03), (xb + 0.01, yt - 0.025, z + 0.012), "metal", "+x-x+z-z")
        xb += SNOW_GUARD_STEP


GUTTER_R, GUTTER_DROP, GUTTER_SEGS = 0.065, 0.04, 6  # the half-round gutter's radius, its rim under the slab's top


def gutter_axis(spec: dict, z0: float = -0.5) -> tuple[float, float]:
    """(z, y) of the eave's gutter axis (its rim's middle) in the pitched pieces' frame, the eave's plumb end at z0."""
    pp = pitch(spec)
    return z0 - GUTTER_R - 0.01, pp["u"] + pp["tv"] + pp["r"] * z0 - GUTTER_DROP


def gutter(m: Mesh, x0, x1, z0, y, ends: str = "") -> None:
    """A half-round zinc gutter along x over x0..x1 in front of the eave's plumb end at z0, its rim at y: the outer and
    inner skins, a bracket strap to the fascia every metre (at the half metres) and an end cap on each named end."""
    zc = z0 - GUTTER_R - 0.01
    def ring(rad):
        return [(zc + rad * math.cos(a), y + rad * math.sin(a))
                for a in (math.pi + math.pi * i / GUTTER_SEGS for i in range(GUTTER_SEGS + 1))]
    arc = ring(GUTTER_R)
    for skin, sign in ((arc, 1.0), (ring(GUTTER_R - 0.004), -1.0)):  # the inner skin 4 mm in: no doubled faces
        for (za, ya), (zb, yb) in zip(skin, skin[1:]):
            out = (0.0, sign * ((ya + yb) / 2 - y), sign * ((za + zb) / 2 - zc))
            m.poly([(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)], out, "zinc")
    for side, x in (("-x", x0), ("+x", x1)):
        if side in ends:
            m.poly([(x, yy, zz) for zz, yy in arc], (-1 if side == "-x" else 1, 0, 0), "zinc")
    xb = math.floor(x0) + 0.5
    while xb < x1 - 0.05:
        if xb > x0 + 0.05:
            m.box((xb - 0.015, y - GUTTER_R - 0.008, zc - GUTTER_R), (xb + 0.015, y - GUTTER_R, zc + GUTTER_R), "metal",
                  "+x-x-y+z-z")
            m.box((xb - 0.015, y - 0.02, zc + GUTTER_R), (xb + 0.015, y + 0.01, z0), "metal", "+x-x+y-y")
        xb += 1.0


def tube(m: Mesh, a, b, rad: float, role: str, sides: int = 6) -> None:
    """A tube of `sides` facets of radius rad from a to b (the downpipes' runs); open ends."""
    d = _sub(b, a)
    ln = math.sqrt(_dot(d, d))
    d = tuple(v / ln for v in d)
    ref = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 0.0, 1.0)
    e1 = _cross(d, ref)
    n1 = math.sqrt(_dot(e1, e1))
    e1 = tuple(v / n1 for v in e1)
    e2 = _cross(d, e1)
    ring = [tuple(math.cos(2 * math.pi * k / sides) * e1[i] + math.sin(2 * math.pi * k / sides) * e2[i]
                  for i in range(3)) for k in range(sides)]
    for k in range(sides):
        r0, r1 = ring[k], ring[(k + 1) % sides]
        pts = [tuple(a[i] + rad * r0[i] for i in range(3)), tuple(a[i] + rad * r1[i] for i in range(3)),
               tuple(b[i] + rad * r1[i] for i in range(3)), tuple(b[i] + rad * r0[i] for i in range(3))]
        m.poly(pts, tuple(r0[i] + r1[i] for i in range(3)), role)


def build_downpipe(pc: Piece, p: dict, spec: dict) -> None:
    """A downpipe from the eave's gutter to the ground (art #77): in the pitched pieces' frame (x along the eave, z up
    the slope from the eave wall's grid line, y 0 the knee wall's top), at x 0: an outlet under the gutter, a swan
    neck back to the wall, the stack down the wall's face p["drop"] metres under the knee wall's top (the House: the
    attic's floor_y 6.4 + the knee 2.2), wall clips every 1.5 m and a shoe kicking out at the foot."""
    g = spec["grid"]
    zg, yg = gutter_axis(spec)
    zw = -g["wall_t_m"] / 2 - 0.02 - DOWNPIPE_R  # the stack's axis off the wall's face
    drop = float(p["drop"])
    m = pc.mesh
    y1 = yg - GUTTER_R - 0.08
    pts = [(0.0, yg - GUTTER_R + 0.01, zg), (0.0, y1, zg), (0.0, y1 - abs(zg - zw), zw), (0.0, -drop + 0.12, zw),
           (0.0, -drop + 0.04, zw - 0.1)]
    for a, b in zip(pts, pts[1:]):
        tube(m, a, b, DOWNPIPE_R, "zinc")
    y = -0.6
    while y > -drop + 0.4:
        m.box((-0.02, y - 0.02, zw - DOWNPIPE_R - 0.005), (0.02, y + 0.02, -g["wall_t_m"] / 2), "metal", "+x-x+y-y-z")
        y -= 1.5
    pc.collide_box((-DOWNPIPE_R, -drop, zw - DOWNPIPE_R), (DOWNPIPE_R, y1 - abs(zg - zw), zw + DOWNPIPE_R))


DOWNPIPE_R = 0.04


TILE_COURSE, TILE_W, TILE_LIP = 1 / 3, 1 / 3, 0.03  # the pantiles' course and tile (horizontal m) and the lip's lift
TILE_ROLES = ("tile", "tile", "tile_b", "tile", "tile_c", "tile", "tile_b")  # the clay's spread, picked per tile
# The pantile's S across its width (fractions of TILE_W, lift in m over the course's plane): the edge under the
# neighbour's roll, the pan's hollow, the roll's crown, the edge again. Three facets a tile: the relief reads as the
# look round's S at street distance (art #77).
TILE_S = ((0.0, 0.02), (0.45, 0.0), (0.78, 0.045), (1.0, 0.02))
TILE_MOSS = 3  # the eave's wear: every TILE_MOSS-th tile of the second course from the eave, all of the first


def tile_lift(x: float) -> float:
    """The pantile's S lift at x (horizontal m from the eave wall's grid node along the eave)."""
    f = x / TILE_W - math.floor(x / TILE_W + 1e-9)
    for (fa, ha), (fb, hb) in zip(TILE_S, TILE_S[1:]):
        if f <= fb + 1e-9:
            return ha + (hb - ha) * (f - fa) / (fb - fa)
    return TILE_S[-1][1]


def _tile_xs(xa: float, xb: float) -> list[float]:
    """xa, the S's facet breaks strictly inside (xa, xb), xb."""
    j = math.floor(xa / TILE_W + 1e-6)
    inner = [(j + f) * TILE_W for f, _ in TILE_S[1:-1]]
    return [xa] + [x for x in inner if xa + EPS < x < xb - EPS] + [xb]


def _cuts(a: float, b: float, step: float) -> list[float]:
    """a, the multiples of step strictly inside (a, b), b: a piece's span cut on the kit-wide tile grid."""
    out, k = [a], math.floor(a / step + 1e-6) + 1
    while k * step < b - EPS:
        out.append(k * step)
        k += 1
    return out + [b]


def pantile_courses(m: Mesh, x0, x1, z0, z1, base, ends: str = "") -> None:
    """The pantile covering of a pitched slab (art #77, docs/kit.md "The free roof"): courses TILE_COURSE deep up the
    slope, each tile TILE_W wide, on the grid of multiples from the eave wall's line, so neighbouring panels meet. A
    course's lower edge stands TILE_LIP over the slab's top base(z) and its upper edge sinks under the next course's
    lip: the stepped shadow lines of the look round's courses. Every tile takes one of TILE_ROLES (the clay's colour
    spread: vertex colours of one material). The plumb ends named in ends ("-z" eave, "+z", "-x" or "+x" verges)
    close the step."""
    zs, xs = _cuts(z0, z1, TILE_COURSE), _cuts(x0, x1, TILE_W)
    for za, zb in zip(zs, zs[1:]):
        k = math.floor((za + 1e-6) / TILE_COURSE)
        ce = (k + 1) * TILE_COURSE

        def y(z, ce=ce):
            return base(z) + TILE_LIP * (ce - z) / TILE_COURSE
        ya, yb = y(za), y(zb)
        lip = abs(za - k * TILE_COURSE) < 1e-6 or (za == z0 and "-z" in ends)
        tail = zb == z1 and "+z" in ends and yb - base(zb) > EPS
        for xa, xb in zip(xs, xs[1:]):
            j = math.floor((xa + 1e-6) / TILE_W)
            role = TILE_ROLES[(k * 5 + j * 3) % len(TILE_ROLES)]
            if "-z" in ends and k * TILE_COURSE < -EPS and (k * TILE_COURSE < z0 + TILE_COURSE - EPS or j % TILE_MOSS == 0):
                role = "tile_moss"
            for sa, sb in zip(_tile_xs(xa, xb), _tile_xs(xa, xb)[1:]):
                ha, hb = tile_lift(sa), tile_lift(sb)
                fn = tuple(-v for v in polygon_normal([(sa, ya + ha, za), (sb, ya + hb, za), (sb, yb + hb, zb)]))
                m.poly([(sa, ya + ha, za), (sb, ya + hb, za), (sb, yb + hb, zb), (sa, yb + ha, zb)], fn, role)
                if lip:
                    m.poly([(sa, base(za), za), (sb, base(za), za), (sb, ya + hb, za), (sa, ya + ha, za)], (0, 0, -1), role)
                if tail:
                    m.poly([(sa, base(zb), zb), (sb, base(zb), zb), (sb, yb + hb, zb), (sa, yb + ha, zb)], (0, 0, 1), "trim")
        for side, x in (("-x", x0), ("+x", x1)):
            if side in ends:
                h = tile_lift(x)
                pts = [(x, base(za), za), (x, base(zb), zb), (x, yb + h, zb), (x, ya + h, za)]
                pts = [q for i, q in enumerate(pts) if math.dist(q, pts[i - 1]) > EPS]
                m.poly(pts, (-1 if side == "-x" else 1, 0, 0), "trim")


def build_ridge(pc: Piece, p: dict, spec: dict) -> None:
    """The ridge cap: two boards over the apex along x over p["x"]. Pivot: the gables' apex (y = r * run above the
    knee wall's top, on the ridge line); the roof's top meets there at u + tv."""
    pp = pitch(spec)
    r, y0 = pp["r"], pp["u"] + pp["tv"]
    x0, x1 = p["x"]
    c, k = RIDGE_BED, 0.05
    caps = "".join(e for e in ("-x", "+x") if e in p.get("ends", ""))
    for s in (-1, 1):  # the mortar bed
        prof = [(0, y0), (s * c, y0 - r * c), (s * c, y0 - r * c + k), (0, y0 + k)]
        prism_x(pc.mesh, prof, x0, x1, "concrete", caps=caps, edges=[False, True, True, False])
    # the half-round clay cap on the bed, its feet sunk into the mortar
    a0 = math.radians(RIDGE_FOOT_DEG)
    arc = [(RIDGE_R * math.cos(a), y0 + RIDGE_R * math.sin(a))
           for a in (-a0 + (math.pi + 2 * a0) * i / RIDGE_SEGS for i in range(RIDGE_SEGS + 1))]
    prism_x(pc.mesh, arc, x0, x1, "tile", caps=caps, edges=[True] * RIDGE_SEGS + [False])
    h = RIDGE_R * 0.71
    pc.collide(prism_x_points([(-c, y0 - r * c), (c, y0 - r * c), (c, y0 - r * c + k), (h, y0 + h), (0, y0 + RIDGE_R),
                               (-h, y0 + h), (-c, y0 - r * c + k)], x0, x1))


RIDGE_BED, RIDGE_R, RIDGE_SEGS, RIDGE_FOOT_DEG = 0.17, 0.12, 8, 14.0  # the mortar bed's half width; the clay cap


GLASS_BAR, GLASS_LIFT = 0.05, 0.06  # the glass roof's rafter width and the pane's height over the gables' line


def build_glass_roof(pc: Piece, p: dict, spec: dict) -> None:
    """A greenhouse glass roof bay: a metal rafter along its x0 edge (the next bay's rafter closes x1), a pane over the
    rest; "+x" in p["ends"] adds a closing rafter along x1 (the end bay whose x1 meets a glass gable: the pane lies
    GLASS_LIFT over the gable's top, and only a rafter fills that slit); p["gutter"] hangs a gutter at z0 (the eave
    bay). Pivot as build_pitched's, on the glass wall's top; the pane lies GLASS_LIFT over the line y = r * z (r: the
    glass pitch, glass_rise)."""
    r = glass_rise(spec)
    (x0, x1), (z0, z1) = p["x"], p["z"]
    m = pc.mesh
    ends = p.get("ends", "")
    raf = [(z0, r * z0), (z1, r * z1), (z1, r * z1 + GLASS_LIFT), (z0, r * z0 + GLASS_LIFT)]
    prism_x(m, raf, x0, x0 + GLASS_BAR, "metal", caps="+x", edges=[True, False, False, "-z" in ends])
    pc.collide(prism_x_points(raf, x0, x0 + GLASS_BAR))
    xe = x1
    if "+x" in ends:
        xe = x1 - GLASS_BAR
        prism_x(m, raf, xe, x1, "metal", caps="-x+x", edges=[True, False, False, "-z" in ends])
        pc.collide(prism_x_points(raf, xe, x1))
    lift = GLASS_LIFT
    pane = [(z0, r * z0 + lift), (z1, r * z1 + lift), (z1, r * z1 + lift + 0.008), (z0, r * z0 + lift + 0.008)]
    prism_x(m, pane, x0 + GLASS_BAR, xe, "glass", caps="", edges=[True, False, True, False])
    pc.collide(prism_x_points([(z0, r * z0 + lift - 0.004), (z1, r * z1 + lift - 0.004),
                               (z1, r * z1 + lift + 0.012), (z0, r * z0 + lift + 0.012)], x0 + GLASS_BAR, xe), "glass")
    if p.get("gutter"):
        y = r * z0 + lift
        lo, hi = (x0, y - 0.12, z0 - 0.12), (x1, y - 0.02, z0)
        m.box(lo, hi, "metal", "+y-y-z+z")
        pc.collide_box(lo, hi)


def build_glass_ridge(pc: Piece, p: dict, spec: dict) -> None:
    """The glass roof's ridge beam over x over p["x"]; pivot at the glass gables' apex (as build_ridge's)."""
    x0, x1 = p["x"]
    lo, hi = (x0, 0.0, -0.05), (x1, GLASS_LIFT + 0.08, 0.05)
    pc.mesh.box(lo, hi, "metal", "+y-y+z-z" + "".join(e for e in ("-x", "+x") if e in p.get("ends", "")))
    pc.collide_box(lo, hi)


def build_glass_gable(pc: Piece, p: dict, spec: dict) -> None:
    """A greenhouse gable in glass on the glass wall's top beam: a triangle (p["up"] "+x" or "-x") or a band (p["band"]:
    a rectangle as tall as the triangle's rise) of one pane, a mullion at x 0 (as the glass walls) and mid-way, a sloped
    bar on a triangle's top (the end bay's rafter), a transom on a band's top."""
    g = spec["grid"]
    L = float(p["length"])
    R = L * glass_rise(spec)
    m = pc.mesh
    mw = 0.03
    up = p.get("up", "+x")
    band = p.get("band", False)

    def top(x):
        return R if band else (R * x / L if up == "+x" else R * (1 - x / L))
    if band:
        poly = [(0, 0), (L, 0), (L, R), (0, R)]
    else:
        poly = [(0, 0), (L, 0), (L, R)] if up == "+x" else [(0, 0), (L, 0), (0, R)]
    m.prism(poly, -0.004, 0.004, "glass", edges=[False] * len(poly))
    pc.collide(prism_points(poly, -0.006, 0.006), "glass")
    for xc in (0.0, L / 2):
        h = top(xc)
        if h > 0.05:
            m.box((xc - mw, 0, -mw), (xc + mw, h, mw), "metal", "+x-x+z-z")
            pc.collide_box((xc - mw, 0, -mw), (xc + mw, h, mw))
    if band:
        m.box((mw, R - 0.03, -mw), (L - mw, R + 0.03, mw), "metal", "+y-y+z-z")
        pc.collide_box((0, R - 0.03, -mw), (L, R + 0.03, mw))
    else:
        bar = [(0, -0.05), (L, R - 0.05), (L, R), (0, 0)] if up == "+x" else [(0, R - 0.05), (L, -0.05), (L, 0), (0, R)]
        m.prism(bar, -mw, mw, "metal", edges=[True, False, True, False])
        pc.collide(prism_points(bar, -mw, mw))


def build_porch(pc: Piece, p: dict, spec: dict) -> None:
    """A porch roof on two posts against an exterior wall: x over 0..length along the wall from its grid node, out
    along +Z from the wall's exterior face for depth; a lean-to slab from height at the wall to front_height; a lamp
    rod under the slab's middle (socket "lamp": where a porch_lamp hangs)."""
    g = spec["grid"]
    h2 = g["wall_t_m"] / 2
    L, D, hw, hf, t = (float(p[k]) for k in ("length", "depth", "height", "front_height", "thick"))
    m = pc.mesh
    za, zb = h2, h2 + D
    prof = [(za, hw - t), (zb, hf - t), (zb, hf), (za, hw)]
    prism_x(m, prof, 0.0, L, "boards", caps="-x+x", cap_role="trim", edges=[True, True, True, False],
            edge_roles={1: "trim", 2: "roof"})
    pc.collide(prism_x_points(prof, 0.0, L))

    def under(z):
        return hw - t + (hf - hw) * (z - za) / D
    ps = float(p.get("post", 0.12))
    zc = zb - 0.12
    for xc in (0.12, L - 0.12):
        poly = [(xc - ps / 2, zc - ps / 2), (xc + ps / 2, zc - ps / 2), (xc + ps / 2, zc + ps / 2), (xc - ps / 2, zc + ps / 2)]
        prism_y(m, poly, 0.0, under(zc + ps / 2), "trim")
        pc.collide(prism_y_points(poly, 0.0, under(zc + ps / 2)))
    xm, zm = L / 2, za + D * 0.6
    y1 = under(zm)
    m.box((xm - 0.06, y1 - 0.02, zm - 0.06), (xm + 0.06, y1, zm + 0.06), "metal", "+x-x-y+z-z")
    m.box((xm - 0.012, y1 - 0.3, zm - 0.012), (xm + 0.012, y1 - 0.02, zm + 0.012), "metal", "+x-x-y+z-z")
    pc.sockets["lamp"] = [round(xm, 4), round(y1 - 0.3, 4), round(zm, 4)]


BRICK_BAND = 0.15  # a chimney's brick course band (two courses of 75 mm) and its colour spread
BRICK_ROLES = ("brick", "brick_b", "brick", "brick_c", "brick_b")
CHIMNEY_POT, CHIMNEY_CAP, CHIMNEY_CORBEL = 0.4, 0.1, 0.15  # the clay pots' height, the cap's and the corbel band's
LEAD_ON_TILES = 0.06  # the lead's lift over the slab's top: it lies on the pantiles (lip 0.03 + the S's 0.045 crest)


def frustum(m: Mesh, c, y0, y1, r0, r1, role: str, sides: int = 8, top: str | None = None) -> None:
    """A vertical frustum about (c[0], c[1]) (x, z) from radius r0 at y0 to r1 at y1; top: the role of a cap disk at
    y1 (none: open)."""
    ring = [(math.cos(2 * math.pi * (k + 0.5) / sides), math.sin(2 * math.pi * (k + 0.5) / sides)) for k in range(sides)]
    for k in range(sides):
        (ax, az), (bx, bz) = ring[k], ring[(k + 1) % sides]
        pts = [(c[0] + r0 * ax, y0, c[1] + r0 * az), (c[0] + r0 * bx, y0, c[1] + r0 * bz),
               (c[0] + r1 * bx, y1, c[1] + r1 * bz), (c[0] + r1 * ax, y1, c[1] + r1 * az)]
        pts = [q for i, q in enumerate(pts) if math.dist(q, pts[i - 1]) > EPS]
        m.poly(pts, (ax + bx, 0.0, az + bz), role)
    if top:
        m.poly([(c[0] + r1 * x, y1, c[1] + r1 * z) for x, z in ring], (0, 1, 0), top)


def chimney_roof(p: dict, spec: dict):
    """The roof's slab top over the attic floor at the chimney piece's local z (p["roof"]: eave_d, the horizontal
    distance from the eave wall's line at z 0, and down, the face towards the eave, "+z" or "-z"), or None."""
    rf = p.get("roof")
    if not rf:
        return None
    pp, knee = pitch(spec), float(spec["grid"]["knee_h_m"])
    s = -1.0 if rf["down"] == "+z" else 1.0
    return lambda z: knee + pp["u"] + pp["tv"] + pp["r"] * (float(rf["eave_d"]) + s * z)


def build_chimney(pc: Piece, p: dict, spec: dict) -> None:
    """A chimney stack (art #77, docs/kit.md "The free roof"): x, z over 0..width from its grid node; the body
    plastered under the roof (in the attic) and brick-coursed over it (bands of BRICK_BAND in BRICK_ROLES), a
    projecting corbel band, a concrete cap and two clay pots whose rims reach p["height"]. With p["roof"] (the slope it
    passes, chimney_roof): lead flashing on the tiles: the apron on the eave-side face, the back gutter on the
    ridge-side face and a strip up each side. p["aerial"]: a TV aerial on a mast strapped to the +x face."""
    S, H = float(p["width"]), float(p["height"])
    m = pc.mesh
    cap1 = H - CHIMNEY_POT
    cap0, o, c = cap1 - CHIMNEY_CAP, 0.06, 0.035
    cb0 = cap0 - CHIMNEY_CORBEL
    top = chimney_roof(p, spec)
    yb = 0.0 if top is None else min(top(0.0), top(S)) - 0.02
    if yb > 0:
        m.box((0, 0, 0), (S, yb, S), "wall_ext", "+x-x+z-z")
    ys = [yb] + [k * BRICK_BAND for k in range(math.floor(yb / BRICK_BAND) + 1, math.ceil(cb0 / BRICK_BAND))
                 if yb + EPS < k * BRICK_BAND < cb0 - EPS] + [cb0]
    for i, (ya, yz) in enumerate(zip(ys, ys[1:])):
        k = round(ya / BRICK_BAND)
        m.box((0, ya, 0), (S, yz, S), "brick", "+x-x+z-z",
              {f: BRICK_ROLES[(k * 2 + j * 3) % len(BRICK_ROLES)] for j, f in enumerate(("+x", "-x", "+z", "-z"))})
    m.box((-c, cb0, -c), (S + c, cap0, S + c), "brick_b", "+x-x-y+z-z")
    m.box((-o, cap0, -o), (S + o, cap1, S + o), "concrete", "+x-x+y-y+z-z")
    for xc in (S * 0.3, S * 0.7):  # the clay pots: a tapered body, a rolled rim, the dark flue inside
        frustum(m, (xc, S / 2), cap1, H - 0.06, 0.12, 0.09, "tile_c")
        frustum(m, (xc, S / 2), H - 0.06, H, 0.105, 0.105, "tile_c")
        frustum(m, (xc, S / 2), H - 0.06, H - 0.03, 0.09, 0.09, "metal", top="metal")  # the soot-dark flue
        pc.collide_box((xc - 0.12, cap1, S / 2 - 0.12), (xc + 0.12, H, S / 2 + 0.12))
    pc.collide_box((0, 0, 0), (S, cb0, S))
    pc.collide_box((-o, cb0, -o), (S + o, cap1, S + o))
    if top is not None:
        _chimney_lead(m, p, S, lambda z: top(z) + LEAD_ON_TILES)
    if p.get("aerial"):
        _aerial(m, S, cb0, H)


def _chimney_lead(m: Mesh, p: dict, S: float, yf) -> None:
    """The chimney's lead flashing over the tile line yf(z): an upstand LEAD_UP on each face, the apron's skirt down
    the slope from the eave-side face, the back gutter's tray up the slope from the ridge-side face, a lip on the
    tiles along each side."""
    up, sk, lip, g = 0.15, 0.18, 0.1, 0.012
    zd = S if p["roof"]["down"] == "+z" else 0.0
    zu, sd = S - zd, (1.0 if zd == S else -1.0)  # sd: the eave side's direction along z
    for z, sgn, run in ((zd, sd, sk), (zu, -sd, 0.3)):  # the apron (down the slope), the back gutter (up)
        zf = z + sgn * g
        m.poly([(-g, yf(z), zf), (S + g, yf(z), zf), (S + g, yf(z) + up, zf), (-g, yf(z) + up, zf)], (0, 0, sgn), "lead")
        z2 = z + sgn * run
        m.poly([(-g - 0.06, yf(z), zf), (S + g + 0.06, yf(z), zf), (S + g + 0.06, yf(z2), z2), (-g - 0.06, yf(z2), z2)],
               (0, 1, 0), "lead")
    for x, sx in ((-g, -1.0), (S + g, 1.0)):
        m.poly([(x, yf(0.0), 0.0), (x, yf(S), S), (x, yf(S) + up, S), (x, yf(0.0) + up, 0.0)], (sx, 0, 0), "lead")
        m.poly([(x, yf(0.0), 0.0), (x + sx * lip, yf(0.0), 0.0), (x + sx * lip, yf(S), S), (x, yf(S), S)], (0, 1, 0),
               "lead")


def _aerial(m: Mesh, S: float, y0: float, H: float) -> None:
    """A TV aerial: a mast beside the chimney's +x face from y0 - 0.6 to H + 1.3 with two straps round the stack, a
    boom along z at the top and five directors across it, shortening towards the front."""
    mx, mz, r = S + 0.04, S / 2, 0.022
    tube(m, (mx, y0 - 0.6, mz), (mx, H + 1.3, mz), r, "metal")
    for ys in (y0 - 0.5, y0 - 0.1):
        m.box((-0.01, ys, -0.01), (S + 0.06, ys + 0.03, S + 0.01), "zinc", "+x-x+y-y+z-z")
    yb = H + 1.2
    tube(m, (mx, yb, mz - 0.25), (mx, yb, mz + 0.85), 0.012, "metal", sides=4)
    for i in range(5):
        z, half = mz - 0.15 + 0.22 * i, 0.32 - 0.04 * i
        m.box((mx - half, yb - 0.006, z - 0.006), (mx + half, yb + 0.006, z + 0.006), "zinc", "+x-x+y-y+z-z")


VENT_R, VENT_H = 0.055, 0.45  # a roof vent pipe's radius and its height over the slab's top at its axis


def build_vent(pc: Piece, p: dict, spec: dict) -> None:
    """A soil vent pipe through the pantiles (art #77): over 0..width x 0..width from its pivot, the pipe's axis at
    the middle, y 0 the slab's top there (the layout's h); a lead slate on the tiles (down: the eave side, as the
    chimney's p["roof"]["down"]), the pipe from under the tiles to VENT_H and a cowl: a flared hood with a cone."""
    w = float(p["width"])
    m = pc.mesh
    c = (w / 2, w / 2)
    r = pitch(spec)["r"]
    s = -1.0 if p["down"] == "+z" else 1.0

    def y(z):
        return LEAD_ON_TILES + s * r * (z - w / 2)
    m.poly([(0, y(0), 0), (w, y(0), 0), (w, y(w), w), (0, y(w), w)], (0, 1, 0), "lead")
    frustum(m, c, y(w / 2) - 0.02, y(w / 2) + 0.05, VENT_R + 0.03, VENT_R + 0.005, "lead", sides=6)
    frustum(m, c, -0.15, VENT_H - 0.06, VENT_R, VENT_R, "metal", sides=6)
    frustum(m, c, VENT_H - 0.06, VENT_H, VENT_R, VENT_R + 0.035, "metal", sides=6)
    frustum(m, c, VENT_H, VENT_H + 0.07, VENT_R + 0.035, 0.0, "metal", sides=6)
    pc.collide_box((c[0] - VENT_R, -0.15, c[1] - VENT_R), (c[0] + VENT_R, VENT_H + 0.07, c[1] + VENT_R))


def dormer_dims(p: dict, spec: dict) -> dict:
    """A gable dormer's heights (art #77) in its panel frame (see build_dormer): the main roof's underside u + r z and
    top u + tv + r z, the dormer's ridge hr (where its ridge meets the main roof's top at z L), its eave he (rise
    p["rise"] per metre over the half width), the window's sill (p["sill"] over the roof's top at the front) and head,
    where a cheek's top meets the main roof's underside (zc) and where the dormer roof's eave meets its top (ze)."""
    pp = pitch(spec)
    r, u, tv = pp["r"], pp["u"], pp["tv"]
    (x0, x1), (z0, z1) = p["x"], p["z"]
    W, L = x1 - x0, z1 - z0
    hr = u + tv + r * L
    he = hr - float(p["rise"]) * W / 2
    sill = u + tv + float(p["sill"])
    ww, wh = (float(v) for v in p["window"])
    ye = hr - float(p["rise"]) * (W / 2 + DORMER_OVER)
    return {"r": r, "u": u, "tv": tv, "W": W, "L": L, "hr": hr, "he": he, "ye": ye, "sill": sill, "head": sill + wh,
            "ww": ww, "zc": (he - u) / r, "ze": (ye - u - tv) / r}


DORMER_WALL, DORMER_CHEEK, DORMER_SLAB, DORMER_OVER = 0.15, 0.1, 0.1, 0.1
DORMER_CASEMENT_DEG = 95.0  # the casement's leaf swung just past square to the front: clear of the crouched climb-out
# (it hinges on the opening's local +x jamb, the world-west one in the House's south dormer: away from the Lookout)


def _rot_box(m: Mesh, pc: Piece, hinge, ang: float, lo, hi, role: str, collide: bool = False) -> None:
    """A box in a casement leaf's frame (x from the hinge along the leaf, y up, z its thickness) turned ang degrees
    out about the vertical hinge: the leaf points (cos, 0, -sin), towards -Z (outside)."""
    a = math.radians(ang)
    d, n = (math.cos(a), 0.0, -math.sin(a)), (math.sin(a), 0.0, math.cos(a))

    def P(x, y, z):
        return (hinge[0] + x * d[0] + z * n[0], hinge[1] + y, hinge[2] + x * d[2] + z * n[2])
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    neg = tuple(-v for v in d), tuple(-v for v in n)
    faces = [([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], d),
             ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], neg[0]),
             ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0.0, 1.0, 0.0)),
             ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0.0, -1.0, 0.0)),
             ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], n),
             ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], neg[1])]
    for pts, nn in faces:
        m.poly([P(*q) for q in pts], nn, role)
    if collide:
        pc.collide([list(P(x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])


def build_dormer(pc: Piece, p: dict, spec: dict) -> None:
    """A gable dormer (art #77, docs/kit.md "The free roof"): it replaces a 2 m panel column of the pitched roof over
    p["z"] (house_layout.dormer_cut). Frame as build_pitched's: x along the eave, z up the slope from the dormer's
    front, the pivot on the knee wall's top line lifted r * z0 (the main roof's underside at u + r z). A plastered
    front wall with the window opening (p["window"] w x h, the sill p["sill"] over the roof's top) and a white
    casement open DORMER_CASEMENT_DEG outward on the +x jamb, a boarded front gable, plastered cheeks down to the main roof, the
    dormer's own roof (rise p["rise"] per metre) whose valleys meet the main roof, and the main roof's slab of the
    column behind (from ze to the far end). Socket "lamp": the practical lamp under the dormer's ridge."""
    dd = dormer_dims(p, spec)
    r, u, tv, W, L, hr, he, ye = (dd[k] for k in ("r", "u", "tv", "W", "L", "hr", "he", "ye"))
    m = pc.mesh
    t, c, sl, ov = DORMER_WALL, DORMER_CHEEK, DORMER_SLAB, DORMER_OVER
    wx0, wx1, sill, head = (W - dd["ww"]) / 2, (W + dd["ww"]) / 2, dd["sill"], dd["head"]
    # the front wall round the opening (the band over the head has no top: the gable sits on it)
    for lo, hi, sides in (((0, u, 0), (W, sill, t), "+x-x+y-y+z-z"), ((0, head, 0), (W, he, t), "+x-x-y+z-z"),
                          ((0, sill, 0), (wx0, head, t), "+x-x+y-y+z-z"), ((wx1, sill, 0), (W, head, t), "+x-x+y-y+z-z")):
        m.box(lo, hi, "wall_ext", sides)
        pc.collide_box(lo, hi)
    # the boarded front gable (no bottom face: it would coincide with the wall band's top, a duplicate Godot drops)
    tri = [(0.0, he), (W, he), (W / 2, hr)]
    m.prism(tri, 0.0, t, "trim", edges=[False, True, True])
    pc.collide(prism_points(tri, 0.0, t))
    # the plastered cheeks: from the main roof's underside up to the eave line
    prof = [(0.0, u), (dd["zc"], he), (0.0, he)]
    for x0, x1 in ((0.0, c), (W - c, W)):
        prism_x(m, prof, x0, x1, "wall_ext")
        pc.collide(prism_x_points(prof, x0, x1))
    # the dormer's roof: two slabs from the ridge to the eave (overhanging ov), back to the valleys that meet the main
    # roof's top at the ridge's far end
    k = float(p["rise"])
    for side in (0, 1):
        def X(x, s=side):
            return x if s == 0 else W - x
        top = [(X(-ov), ye, -ov), (X(-ov), ye, dd["ze"]), (X(W / 2), hr, L), (X(W / 2), hr, -ov)]
        bot = [(x, y - sl, z) for x, y, z in top]
        nrm = (-k if side == 0 else k, 1.0, 0.0)
        _dormer_tiles(m, dd, k, side)
        m.poly(bot, tuple(-v for v in nrm), "boards")
        m.poly([top[0], top[3], bot[3], bot[0]], (0.0, 0.0, -1.0), "trim")  # the barge board's edge
        m.poly([top[0], top[1], bot[1], bot[0]], (-1.0 if side == 0 else 1.0, 0.0, 0.0), "trim")  # the fascia's edge
        pc.collide([list(q) for q in top + bot])
    tube(m, (W / 2, hr + 0.02, -ov), (W / 2, hr + 0.02, L), 0.07, "tile")  # the half-round ridge tile over the apex
    # the main roof behind the cheeks: the column's slab from ze to the far end (round the valleys)
    z0 = dd["ze"]
    slab = [(z0, u + r * z0), (L, u + r * L), (L, u + tv + r * L), (z0, u + tv + r * z0)]
    prism_x(m, slab, 0.0, W, "boards", caps="", edges=[True, False, True, True], edge_roles={2: "tile", 3: "trim"})
    pc.collide(prism_x_points(slab, 0.0, W))
    # the sills and the open casement
    m.box((wx0 - 0.05, sill - 0.03, -0.08), (wx1 + 0.05, sill, 0.0), "metal")
    m.box((wx0, sill - 0.03, t), (wx1, sill, t + 0.15), "trim")
    hinge, ang, fw, ft = (wx1, sill, 0.0), 180.0 - DORMER_CASEMENT_DEG, 0.05, 0.05  # the leaf: from wx1 out, away
    lw, lh = wx1 - wx0, head - sill
    for lo, hi in (((0, 0, -ft), (fw, lh, 0)), ((lw - fw, 0, -ft), (lw, lh, 0)), ((fw, 0, -ft), (lw - fw, fw, 0)),
                   ((fw, lh - fw, -ft), (lw - fw, lh, 0))):
        _rot_box(m, pc, hinge, ang, lo, hi, "trim")
    _rot_box(m, pc, hinge, ang, (fw, fw, -ft / 2 - 0.004), (lw - fw, lh - fw, -ft / 2 + 0.004), "glass", collide=True)
    pc.sockets["lamp"] = [round(W / 2, 4), round(he - 0.1, 4), round(min(dd["ze"], 1.2), 4)]


def _dormer_tiles(m: Mesh, dd: dict, k: float, side: int) -> None:
    """One slope of the dormer's roof as pantile courses (art #77): pantile_courses laid in the slope's own frame (a
    along its eave = the dormer's z, b up the slope from its eave = x + DORMER_OVER, base ye + k b), the tiles past
    the valley (the line from (b 0, a ze) to the ridge's far end (b W/2 + over, a L)) dropped, then mirrored in place."""
    ov, W, L, ze, ye = DORMER_OVER, dd["W"], dd["L"], dd["ze"], dd["ye"]
    bm = W / 2 + ov
    tmp = Mesh("dormer_tiles")
    pantile_courses(tmp, -ov, L, 0.0, bm, lambda b: ye + k * b, "-z-x")  # no ridge tails: both slopes' coincide

    def world(q):
        x = q[2] - ov
        return (x if side == 0 else W - x, q[1], q[0])
    for f, role in zip(tmp.faces, tmp.roles):
        pts = [tmp.verts[i] for i in f]
        ac, bc = sum(q[0] for q in pts) / len(pts), sum(q[2] for q in pts) / len(pts)
        if ac > ze + (L - ze) * bc / bm + 0.05:
            continue
        n = polygon_normal(pts)
        m.poly([world(q) for q in pts], (n[2] if side == 0 else -n[2], n[1], n[0]), role)


def build_bracket(pc: Piece, p: dict, spec: dict) -> None:
    """A cornice bracket under the roof deck's overhang (Q3): on an exterior wall's face, centred on x 0, its top
    against the slab's underside at y 0, reaching p["reach"] out from the wall's face."""
    h2 = spec["grid"]["wall_t_m"] / 2
    reach, drop, w = float(p["reach"]), float(p["drop"]), float(p["width"]) / 2
    prof = [(h2, 0.0), (h2 + reach, 0.0), (h2 + reach, -0.12), (h2 + 0.15, -drop), (h2, -drop)]
    prism_x(pc.mesh, prof, -w, w, p.get("role", "trim"), edges=[False, True, True, True, False])
    pc.collide(prism_x_points(prof, -w, w))


def build_cap(pc: Piece, p: dict, spec: dict) -> None:
    """A post's cap: a slab and a low pyramid, centred on x, z 0 at the post's top (y 0)."""
    hw, slab, peak = float(p["width"]) / 2, float(p["slab"]), float(p["peak"])
    m = pc.mesh
    m.box((-hw, 0, -hw), (hw, slab, hw), p["role"], "+x-x-y+z-z")
    corners = [(-hw, slab, -hw), (hw, slab, -hw), (hw, slab, hw), (-hw, slab, hw)]
    apex = (0.0, slab + peak, 0.0)
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        m.poly([a, b, apex], ((a[0] + b[0]) / 2, hw, (a[2] + b[2]) / 2), p["role"])
    pc.collide(box_points((-hw, 0, -hw), (hw, slab, hw)) + [list(apex)])


def build_gate_post(pc: Piece, p: dict, spec: dict) -> None:
    """A gate post centred on its grid node: a plastered body, a concrete cap with a low pyramid."""
    hw, H = float(p["width"]) / 2, float(p["height"])
    m = pc.mesh
    m.box((-hw, 0, -hw), (hw, H, hw), "wall_ext", "+x-x+z-z")
    pc.collide_box((-hw, 0, -hw), (hw, H, hw))
    cap = Piece(pc.id + "_cap", pc.kind)
    build_cap(cap, {"width": 2 * hw + 0.06, "slab": 0.06, "peak": 0.09, "role": "concrete"}, spec)
    merge(m, cap.mesh, 0.0, (0.0, H, 0.0))
    pc.collide([[q[0], q[1] + H, q[2]] for q in cap.colliders[0]["points"]])


def gazebo_corner(R: float, k: int) -> tuple:
    """The k-th corner of the gazebo's hexagon of circumradius R: corner 0 on +X, corner k is corner 0 turned by
    k * 60 deg about +Y, so six instances of a sector at k * 60 deg close the ring."""
    return rot_y((R, 0.0, 0.0), 60.0 * k)


def build_gazebo_sector(pc: Piece, p: dict, spec: dict) -> None:
    """One sixth of the hexagonal gazebo, pivot at its centre: the deck's triangle, the post near corner 0 and (unless
    p["open"], the entrance) the rail from post 0 to post 1. Six instances at k * 60 deg about +Y make the gazebo."""
    R, dh, ph = float(p["radius"]), float(p["deck_h"]), float(p["post_h"])
    m = pc.mesh
    c0, c1 = gazebo_corner(R, 0), gazebo_corner(R, 1)
    tri = [(0.0, 0.0), (c0[0], c0[2]), (c1[0], c1[2])]
    prism_y(m, tri, 0.0, dh, "trim", caps="+y", cap_role="boards", edges=[False, True, False])
    pc.collide(prism_y_points(tri, 0.0, dh))
    ps, rp = float(p.get("post", 0.14)), R - 0.12
    q0, q1 = gazebo_corner(rp, 0), gazebo_corner(rp, 1)
    post = [(q0[0] - ps / 2, -ps / 2), (q0[0] + ps / 2, -ps / 2), (q0[0] + ps / 2, ps / 2), (q0[0] - ps / 2, ps / 2)]
    prism_y(m, post, dh, dh + ph, "trim")
    pc.collide(prism_y_points(post, dh, dh + ph))
    if p.get("open"):
        return
    span = math.dist((q0[0], q0[2]), (q1[0], q1[2]))
    deg = math.degrees(math.atan2(-(q1[2] - q0[2]), q1[0] - q0[0]))
    rail = Mesh("rail")
    a, b = ps / 2, span - ps / 2
    rail.box((a, 0.85, -0.04), (b, 0.91, 0.04), "trim", "+y-y+z-z")
    rail.box((a, 0.08, -0.03), (b, 0.14, 0.03), "trim", "+y-y+z-z")
    x = a + 0.18
    while x < b - 0.1:
        rail.box((x - 0.02, 0.14, -0.02), (x + 0.02, 0.85, 0.02), "trim", "+x-x+z-z")
        x += 0.2
    merge(m, rail, deg, (q0[0], dh, q0[2]))
    pc.collide([list(place(q, deg, (q0[0], dh, q0[2]))) for q in box_points((a, 0.08, -0.04), (b, 0.91, 0.04))])


def build_gazebo_roof(pc: Piece, p: dict, spec: dict) -> None:
    """One sixth of the gazebo's roof, pivot at the gazebo's centre: a triangle from the eave edge (corners 0 and 1 of
    radius p["radius"] at eave_h) up to the apex at apex_h, its underside p["thick"] lower, a fascia on the eave."""
    R, ye, ya, tv = (float(p[k]) for k in ("radius", "eave_h", "apex_h", "thick"))
    m = pc.mesh
    c0, c1 = gazebo_corner(R, 0), gazebo_corner(R, 1)
    top = [(0.0, ya, 0.0), (c0[0], ye, c0[2]), (c1[0], ye, c1[2])]
    bot = [(q[0], q[1] - tv, q[2]) for q in top]
    out = ((c0[0] + c1[0]) / 2, 0.0, (c0[2] + c1[2]) / 2)
    m.poly(top, (out[0] * 0.3, 1.0, out[2] * 0.3), "roof")
    m.poly(bot, (-out[0] * 0.3, -1.0, -out[2] * 0.3), "boards")
    m.poly([top[1], top[2], bot[2], bot[1]], out, "trim")
    pc.collide([list(q) for q in top + bot])


def build_finial(pc: Piece, p: dict, spec: dict) -> None:
    """The gazebo's finial on the roof's apex (pivot at the apex)."""
    hw = float(p["width"]) / 2
    m = pc.mesh
    m.box((-hw, -0.1, -hw), (hw, 0.05, hw), p["role"], "+x-x+z-z")
    cap = Piece(pc.id + "_cap", pc.kind)
    build_cap(cap, {"width": 2 * hw + 0.02, "slab": 0.02, "peak": float(p["peak"]), "role": p["role"]}, spec)
    merge(m, cap.mesh, 0.0, (0.0, 0.05, 0.0))
    pc.collide(box_points((-hw, -0.1, -hw), (hw, 0.05, hw)) + [[0.0, 0.07 + float(p["peak"]), 0.0]])


def build_glass_node(pc: Piece, p: dict, spec: dict) -> None:
    """Glass-wall node pieces: "corner" fills the outer corner's notch of the kerb and the top beam (as build_corner);
    "end" caps a free kerb end at x 0 (2 cm proud, as build_end); "post" is a lone mullion on a node (the far end of a
    run, whose last module has no post at x = length)."""
    g = spec["grid"]
    h2, H, kerb, mw, beam = g["wall_t_m"] / 2, g["glass_wall_h_m"], 0.3, 0.03, 0.06
    m = pc.mesh
    what = p["node"]
    if what == "corner":
        m.box((0, 0, 0), (h2, kerb, h2), "concrete", "+x+z+y")
        pc.collide_box((0, 0, 0), (h2, kerb, h2))
        m.box((mw, H - beam, 0.0), (0.04, H, 0.04), "metal", "+x+z+y-y")
        m.box((0.0, H - beam, mw), (mw, H, 0.04), "metal", "+z+y-y")
        pc.collide_box((0, H - beam, 0), (0.04, H, 0.04))
    elif what == "end":
        m.box((-0.02, 0, -h2), (0, kerb, h2), "concrete", "-x+y+z-z")
        pc.collide_box((-0.02, 0, -h2), (0, kerb, h2))
    else:
        m.box((-mw, kerb, -mw), (mw, H, mw), "metal", "+x-x+y+z-z")
        pc.collide_box((-mw, kerb, -mw), (mw, H, mw))


def build_slab_edge(pc: Piece, p: dict, spec: dict) -> None:
    """Closes a slab's free edge (a stairwell, a balcony, a hatch's side): a face along +X at z 0 facing -Z, the slab on
    the +Z side, from its top (y 0) down by p["thick"]; floor tiles have no side faces (they met back to back)."""
    L, th = float(p["length"]), float(p["thick"])
    pc.mesh.quad_z(0, L, -th, 0, 0, -1, p["role"])
    pc.collide_box((0, -th, 0), (L, 0, 0.02))


BUILDERS = {
    "wall": build_wall, "corner": build_corner, "end": build_end, "gable": build_gable, "floor": build_floor,
    "ceiling": build_ceiling, "block": build_block, "parapet": build_parapet, "parapet_corner": build_parapet_corner,
    "stairs": build_stairs, "stairs_open": build_stairs_open, "ladder": build_ladder, "post": build_post,
    "railing": build_railing, "fence": build_fence, "wicket": build_wicket, "gates": build_gates,
    "glass": build_glass, "garage_door": build_garage_door,
    # version 2 (art #86)
    "pillar": build_pillar, "pitched": build_pitched, "ridge": build_ridge, "glass_roof": build_glass_roof,
    "glass_ridge": build_glass_ridge, "glass_gable": build_glass_gable, "porch": build_porch, "chimney": build_chimney,
    "dormer": build_dormer, "downpipe": build_downpipe, "vent": build_vent,
    "bracket": build_bracket, "cap": build_cap, "gate_post": build_gate_post, "gazebo_sector": build_gazebo_sector,
    "gazebo_roof": build_gazebo_roof, "finial": build_finial, "glass_node": build_glass_node, "slab_edge": build_slab_edge,
    "beam": build_beam,  # #108
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
    return uv2_pack(mesh, margin)[0]


def uv2_pack(mesh: Mesh, margin: float = UV2_MARGIN_M) -> tuple[list, float]:
    """Every face its own island (projected in metres), shelf-packed into the unit square at one uniform scale; returns
    the UVs and that scale (UV units per metre: the lightmap's texels per metre are the mesh's lightmap size times it)."""
    islands = []
    for face in mesh.faces:
        pts = [mesh.verts[i] for i in face]
        n = polygon_normal(pts)
        q = [project(p, n) for p in pts]
        lo = (min(a for a, _ in q), min(b for _, b in q))
        hi = (max(a for a, _ in q), max(b for _, b in q))
        islands.append(([(a - lo[0], b - lo[1]) for a, b in q], hi[0] - lo[0], hi[1] - lo[1]))
    if not islands:
        return [], 0.0
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
            for i in range(len(islands))], scale


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
        uvs, scale = uv2_pack(m)
        meshes.append({
            "name": m.name, "origin": list(m.origin), "verts": [list(v) for v in m.verts], "faces": m.faces,
            "roles": m.roles, "uv0": uv0(m, spec), "uv2": uvs, "uv2_per_m": round(scale, 5), "triangles": m.triangles(),
        })
    verts = [v for m in pc.meshes for v in m.verts]
    return {
        "id": pc.id, "kind": pc.kind, "meshes": meshes, "colliders": pc.colliders,
        "triangles": sum(m.triangles() for m in pc.meshes),
        "bounds_m": bounds(verts),
        "collision_bounds_m": bounds(p for c in pc.colliders for p in c["points"]),
        "roles": sorted({r for m in pc.meshes for r in m.roles}),
        "sockets": pc.sockets,
    }


def build_kit(spec: dict) -> list[dict]:
    return [describe(build_piece(p, spec), spec) for p in spec["pieces"]]


# --- checks --------------------------------------------------------------------------------------------------------
def nominal_size(p: dict, spec: dict) -> dict:
    """The grid footprint a piece is placed by: (length along X, depth along Z) in metres, or None for a node piece."""
    if "x" in p:  # a span piece (roofs): its spans, which may stand out of the grid (eaves, verges)
        return {"x": float(p["x"][1] - p["x"][0]), "z": float(p["z"][1] - p["z"][0]) if "z" in p else None}
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
            if v is not None and p["type"] not in ("ladder",) and not p.get("overhang") and abs(v - round(v)) > EPS:
                problems.append(f"{p['id']}: its {axis} size {v} m is not whole metres")
        if "length" in p and p["type"] in ("wall", "parapet", "railing", "fence", "glass", "gable") \
                and int(p["length"]) not in g["modules_m"]:
            problems.append(f"{p['id']}: length {p['length']} m is not a {g['modules_m']} m module")
        for key in ("finish",):
            if key in p and p[key] not in spec["finishes"]:
                problems.append(f"{p['id']}: no finish {p[key]}")
    for name, m in spec["materials"].items():
        pack = m.get("pack")
        if pack and (pack not in spec.get("packs", {}) or name not in spec["packs"][pack]["layers"]):
            problems.append(f"material {name}: not a layer of pack {pack}")
    for pack, d in spec.get("packs", {}).items():
        if not 1 <= len(d["layers"]) <= 4:
            problems.append(f"pack {pack}: {len(d['layers'])} layers (1 to 4: the vertex alpha holds them)")
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
    if "x" in p:  # a span piece: nothing outside its spans (a glass eave's gutter hangs 0.12 m before z0; p["reach_m"]:
        # what may stand out before z0 and beside the x span, a dormer's overhangs and its open casement)
        z, reach = p.get("z"), float(p.get("reach_m", 0.0))
        if z is not None and (b["min"][2] < z[0] - (0.12 if p.get("gutter") else reach) - EPS or b["max"][2] > z[1] + EPS):
            problems.append(f"{pid}: z extent {b['min'][2]}..{b['max'][2]} m leaves its span {z}")
        if b["min"][0] < p["x"][0] - reach - EPS or b["max"][0] > p["x"][1] + reach + EPS:
            problems.append(f"{pid}: x extent {b['min'][0]}..{b['max'][0]} m leaves its span {p['x']}")
    elif size["x"] is not None and p["type"] not in ("ladder",):
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
            "uv2_per_m": min(m["uv2_per_m"] for m in d["meshes"]),
            "glass_colliders": sum(1 for c in d["colliders"] if c["group"] == "glass"),
            "nodes": [m["name"] for m in d["meshes"]],
        })
    return rows


# --- seams: neighbours on the grid must not put faces back to back (art #86, v1's floor tiles did) ------------------
def _plane_key(pts):
    n = polygon_normal(pts)
    ln = math.sqrt(_dot(n, n))
    if ln < EPS:
        return None
    n = tuple(c / ln for c in n)
    return n, _dot(n, pts[0])


def _clip(subject, clip):
    """Sutherland-Hodgman: the convex polygon subject clipped by the convex polygon clip (both counter-clockwise, 2D)."""
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9

    def cut(p, q, a, b):
        dx, dy = q[0] - p[0], q[1] - p[1]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            return q
        t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
        return (p[0] + t * dx, p[1] + t * dy)
    out = list(subject)
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        src, out = out, []
        for j in range(len(src)):
            p, q = src[j], src[(j + 1) % len(src)]
            if inside(q, a, b):
                if not inside(p, a, b):
                    out.append(cut(p, q, a, b))
                out.append(q)
            elif inside(p, a, b):
                out.append(cut(p, q, a, b))
        if not out:
            return []
    return out


def _area2(poly) -> float:
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2


def _flat(pts, n):
    ax = _axis(n)
    keep = [i for i in range(3) if i != ax]
    q = [(p[keep[0]], p[keep[1]]) for p in pts]
    return q if _area2(q) > 0 else q[::-1]


def coplanar_overlaps(faces_a, faces_b, min_area: float = 1e-4) -> list[tuple]:
    """Pairs of faces (index in a, index in b) that lie in one plane and overlap by more than min_area m2: faces that
    z-fight or sit back to back where two pieces meet."""
    planes = {}
    for j, pts in enumerate(faces_b):
        k = _plane_key(pts)
        if k:
            planes.setdefault(_axis(k[0]), []).append((j, k, pts))
    hits = []
    for i, pts in enumerate(faces_a):
        k = _plane_key(pts)
        if not k:
            continue
        for j, kb, pb in planes.get(_axis(k[0]), []):
            if abs(abs(_dot(k[0], kb[0])) - 1) > 1e-6:
                continue
            if abs(kb[1] * _dot(k[0], kb[0]) - k[1]) > 1e-4:
                continue
            inter = _clip(_flat(pts, k[0]), _flat(pb, k[0]))
            if len(inter) >= 3 and abs(_area2(inter)) > min_area:
                hits.append((i, j))
    return hits


def face_points(d: dict, deg: float = 0.0, offset=(0.0, 0.0, 0.0)) -> list[list[tuple]]:
    out = []
    for m in d["meshes"]:
        o = m["origin"]
        for f in m["faces"]:
            out.append([place((m["verts"][i][0] + o[0], m["verts"][i][1] + o[1], m["verts"][i][2] + o[2]), deg, offset)
                        for i in f])
    return out


RUN_TYPES = ("wall", "parapet", "railing", "fence", "glass", "slab_edge", "beam")


def seam_offsets(p: dict) -> list[tuple]:
    """Where the next copy of a piece snaps on (a run along +X, a floor along +X and +Z, a roof slab along its spans)."""
    if p["type"] in RUN_TYPES:
        return [(float(p["length"]), 0.0, 0.0)]
    if p["type"] in ("floor", "ceiling") and "size" in p:
        return [(float(p["size"][0]), 0.0, 0.0), (0.0, 0.0, float(p["size"][1]))]
    if p["type"] in ("pitched", "glass_roof") and not p.get("ends"):
        dz = p["z"][1] - p["z"][0]
        return [(p["x"][1] - p["x"][0], 0.0, 0.0), ("pitch", dz)]
    if p["type"] in ("ridge", "glass_ridge") and not p.get("ends"):
        return [(p["x"][1] - p["x"][0], 0.0, 0.0)]
    return []


def seam_problems(spec: dict, described: dict) -> list[str]:
    """Snaps a copy of every run, floor and roof module onto its neighbour node and refuses faces back to back."""
    problems = []
    r = spec["grid"]["gable_rise_per_m"]
    for p in spec["pieces"]:
        d = described.get(p["id"])
        if d is None:
            continue
        a = face_points(d)
        for off in seam_offsets(p):
            if off[0] == "pitch":
                off = (0.0, (glass_rise(spec) if p["type"] == "glass_roof" else r) * off[1], off[1])
            hits = coplanar_overlaps(a, face_points(d, 0.0, off))
            if hits:
                problems.append(f"{p['id']}: {len(hits)} faces back to back with its neighbour at {list(off)}")
    return problems


# --- assemblies the checks and the proof share (pieces placed as (id, degrees about +Y, offset)) --------------------
def attic_roof(spec: dict, span_x: int, span_z: int, rise: float | None = None) -> list[tuple]:
    """The attic's pitched roof over span_x x span_z metres (grid lines; the eave walls at z 0 and span_z, the gables at
    x 0 and span_x; pivots at the knee walls' top, y 0): panels 2 m along the eave, 2 m and 1 m up the slope, eaves,
    verges, the corners between them and the ridge; the far slope is the near one turned 180 deg. `rise` overrides the
    kit's gable_rise_per_m (the greenhouse's glass roof passes glass_rise)."""
    run = span_z / 2
    r = spec["grid"]["gable_rise_per_m"] if rise is None else rise
    if run != int(run):
        raise ValueError("the attic's depth must be an even number of metres (the ridge on a grid line)")
    rows, z = [], 0
    while z < run:
        step = 2 if run - z >= 2 else 1
        rows.append((z, step))
        z += step
    out = []
    for side in (0, 1):
        deg = 180.0 * side

        def at(x, z):  # a pivot on the slope: lifted r per metre up it; the far slope mirrored through the centre
            return (span_x - x, r * z, span_z - z) if side else (x, r * z, z)
        for x in range(0, span_x, 2):
            out.append(("roof_pitched_eave_2m", deg, at(x, 0)))
            for z, step in rows:
                out.append((f"roof_pitched_2x{step}", deg, at(x, z)))
        for z, step in rows:
            out.append((f"roof_pitched_verge_{step}_l", deg, at(0, z)))
            out.append((f"roof_pitched_verge_{step}_r", deg, at(span_x, z)))
        out.append(("roof_pitched_corner_l", deg, at(0, 0)))
        out.append(("roof_pitched_corner_r", deg, at(span_x, 0)))
    for x in range(0, span_x, 2):
        out.append(("roof_pitched_ridge_2m", 0.0, (x, r * run, run)))
    out.append(("roof_pitched_ridge_end_l", 0.0, (0, r * run, run)))
    out.append(("roof_pitched_ridge_end_r", 0.0, (span_x, r * run, run)))
    return out


def gazebo(prefix: str = "gazebo") -> list[tuple]:
    """The gazebo: six deck sectors (sector 0 the open entrance), six roof sectors and the finial."""
    out = [(f"{prefix}_sector_open" if k == 0 else f"{prefix}_sector", 60.0 * k, (0.0, 0.0, 0.0)) for k in range(6)]
    out += [(f"{prefix}_roof_sector", 60.0 * k, (0.0, 0.0, 0.0)) for k in range(6)]
    return out


def _ray_hits_up(tris, x, z, y0) -> bool:
    return _ray_up(tris, x, z, y0) is not None


def _ray_up(tris, x, z, y0):
    """The lowest height above y0 where a vertical ray at (x, z) meets one of the triangles, or None."""
    best = None
    for a, b, c in tris:
        # barycentric test in XZ, then the hit's height above y0
        d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d
        l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d
        l3 = 1 - l1 - l2
        y = l1 * a[1] + l2 * b[1] + l3 * c[1]
        if min(l1, l2, l3) >= -1e-9 and y > y0 and (best is None or y < best):
            best = y
    return best


def assembly_tris(placed: list[tuple], described: dict) -> list[tuple]:
    tris = []
    for pid, deg, off in placed:
        for f in face_points(described[pid], deg, off):
            for k in range(1, len(f) - 1):
                tris.append((f[0], f[k], f[k + 1]))
    return tris


def closure_problems(spec: dict, described: dict, span_x: int = 20, span_z: int = 14, step: float = 0.25) -> list[str]:
    """The attic's roof closes over its span: a ray straight up from every step-metre point inside the walls hits the
    roof; the roof's underside stays under the gables' sloped top (no gap at the gable) at every point of the slope."""
    problems = []
    placed = attic_roof(spec, span_x, span_z)
    missing = sorted({pid for pid, _, _ in placed if pid not in described})
    if missing:
        return [f"attic roof: no piece {', '.join(missing)}"]
    tris = assembly_tris(placed, described)
    misses = []
    n = int(round(span_x / step))
    m = int(round(span_z / step))
    for i in range(n + 1):
        for j in range(m + 1):
            x, z = min(max(i * step, 0.11), span_x - 0.11), min(max(j * step, 0.11), span_z - 0.11)
            if not _ray_hits_up(tris, x + 1e-4, z + 1e-4, 0.0):
                misses.append((round(x, 2), round(z, 2)))
    if misses:
        problems.append(f"attic roof: {len(misses)} rays up miss the roof, e.g. {misses[:4]}")
    r = pitch(spec)["r"]
    gaps = []
    for x in (0.0, float(span_x)):  # the gables' planes: the underside measured against the gables' sloped top
        for k in range(1, int(span_z / 0.05)):
            z = k * 0.05 + 1e-4
            under = _ray_up(tris, x + 1e-4, z, -1.0)
            top = r * min(z, span_z - z)
            if under is None or under > top - 0.01:
                gaps.append((x, round(z, 2), None if under is None else round(under - top, 3)))
    if gaps:
        problems.append(f"attic roof: at {len(gaps)} points of the gables the underside is not under their top, "
                        f"e.g. {gaps[:4]}")
    return problems


def gazebo_problems(spec: dict, described: dict) -> list[str]:
    placed = gazebo()
    missing = sorted({pid for pid, _, _ in placed if pid not in described})
    if missing:
        return [f"gazebo: no piece {', '.join(missing)}"]
    roof = [t for t in assembly_tris([q for q in placed if "roof" in q[0]], described)]
    deck = [t for t in assembly_tris([q for q in placed if "roof" not in q[0]], described)]
    misses = []
    for i in range(-24, 25):
        for j in range(-24, 25):
            x, z = i * 0.1 + 1e-4, j * 0.1 + 1e-4
            if math.hypot(x, z) > 2.3:
                continue
            if not _ray_hits_up(roof, x, z, 2.0):
                misses.append(("roof", round(x, 2), round(z, 2)))
            if not _ray_hits_up(deck, x, z, -1.0):
                misses.append(("deck", round(x, 2), round(z, 2)))
    return [f"gazebo: {len(misses)} rays up miss, e.g. {misses[:4]}"] if misses else []
