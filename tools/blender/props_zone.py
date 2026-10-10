"""The chill zone's and the photo gazebo's props (art #81b, map #73; props/zones.toml, docs/props.md): deckchair, fire
pit, bean bag, cooler, photo backdrop, camera tripod, lantern and the string-light sets. Plain Python like
props_task.py, whose primitives, spec loading and checks they share; props_task registers these builders in its
BUILDERS, so the `props` command builds them with `--spec props/zones.toml`.

Light fixtures put their bulbs on the `emissive` material (roles `bulb`, `ember`) and name their light anchors as
sockets `light_<k>`: the assembly puts a baked light there (inventory.md section 8). A strand hung from two hooks
(mount "hang") has its pivot in the middle of the hook line and hangs below it.
"""

from __future__ import annotations

import math

import props_task as pt
from kit_geom import Mesh, Piece

FIT_LIMIT = 0.06  # fit() rescales a prop to its spec's bounds by at most this share per axis


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def bar(m: Mesh, p0, p1, half_w: float, half_t: float, role: str, side=(1.0, 0.0, 0.0)) -> None:
    """A square-ish bar from p0 to p1: width half_w along `side` (made square to the bar), thickness half_t."""
    u = _unit(tuple(p1[i] - p0[i] for i in range(3)))
    w = _unit(_cross(u, side))
    v = _cross(w, u)
    length = math.dist(p0, p1)
    centre = tuple((p0[i] + p1[i]) / 2 for i in range(3))
    pt.obox(m, centre, u, v, w, (length / 2, half_w, half_t), role)


def bulb(m: Mesh, c, r: float, role: str = "bulb") -> None:
    """An octahedral bulb (8 triangles), a little taller than wide."""
    top, bot = (c[0], c[1] + r * 1.3, c[2]), (c[0], c[1] - r * 1.3, c[2])
    ring = [(c[0] + r, c[1], c[2]), (c[0], c[1], c[2] + r), (c[0] - r, c[1], c[2]), (c[0], c[1], c[2] - r)]
    for i in range(4):
        a, b = ring[i], ring[(i + 1) % 4]
        for apex, s in ((top, 1), (bot, -1)):
            mid = tuple((a[k] + b[k]) / 2 - c[k] for k in range(3))
            m.poly([a, b, apex], (mid[0], s * r, mid[2]), role)


def strand(m: Mesh, bulbs_m: Mesh, x0: float, x1: float, y: float, sag: float, n_bulbs: int, segs: int = 10) -> list:
    """A cable from (x0, y) to (x1, y) at z 0 sagging by `sag` (a parabola), bulbs hanging under it; returns the
    bulbs' centres."""
    def at(t):
        return (x0 + (x1 - x0) * t, y - sag * 4 * t * (1 - t), 0.0)
    for i in range(segs):
        bar(m, at(i / segs), at((i + 1) / segs), 0.008, 0.008, "cable_black", side=(0.0, 0.0, 1.0))
    centres = []
    for k in range(n_bulbs):
        x, yy, z = at((k + 0.5) / n_bulbs)
        c = (x, yy - 0.036, 0.0)  # the bulb's top touches the cable
        bulb(bulbs_m, c, 0.025)
        centres.append(c)
    return centres


def fit(pc: Piece, p: dict) -> None:
    """Scales and moves every mesh, collider and socket so the prop's bounds are exactly the spec's w, h, d, the
    footprint centred on the pivot and the lowest point on the floor (a hung prop: the highest at y 0). The builders
    aim at the bounds; this only absorbs the slant of bars and the lathes' facets, at most FIT_LIMIT per axis."""
    verts = [v for m in pc.meshes for v in m.verts]
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    want = (float(p["w"]), float(p["h"]), float(p["d"]))
    k = [want[i] / (hi[i] - lo[i]) for i in range(3)]
    if any(abs(s - 1) > FIT_LIMIT for s in k):
        raise ValueError(f"{p['id']}: built {[round(hi[i] - lo[i], 3) for i in range(3)]}, the spec says {want}")
    y0 = -want[1] if p.get("mount") == "hang" else 0.0
    target_lo = (-want[0] / 2, y0, -want[2] / 2)

    def f(v):
        return tuple(round(target_lo[i] + (v[i] - lo[i]) * k[i], 6) for i in range(3))

    for m in pc.meshes:
        m.verts = [f(v) for v in m.verts]
        m._index = {v: i for i, v in enumerate(m.verts)}
        m.origin = f(m.origin)
    for c in pc.colliders:
        c["points"] = [list(f(q)) for q in c["points"]]
    for name, s in pc.sockets.items():
        pc.sockets[name] = [round(c, 4) for c in f(s)]


# --- the chill zone ----------------------------------------------------------------------------------------------------
def build_deckchair(pc: Piece, p: dict, spec: dict) -> None:
    """A folding deckchair seen from the side (z, y): a back frame leaning back to the top bar, a front leg carrying
    the sling's front bar, arm rails between them; the sling in five stripes sags between the two bars."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    xr = w / 2 - 0.022
    top, front = (-d / 2 + 0.02, h - 0.02), (d / 2 - 0.08, 0.42)
    for sx in (-1, 1):
        x = sx * xr
        bar(m, (x, 0.0, -0.08), (x, h - 0.04, -d / 2 + 0.03), 0.02, 0.016, "wood_light")   # back frame
        bar(m, (x, 0.0, d / 2 - 0.03), (x, 0.44, d / 2 - 0.09), 0.02, 0.016, "wood_light")  # front leg
        bar(m, (x, 0.4, d / 2 - 0.08), (x, 0.47, -0.3), 0.016, 0.014, "wood_dark")          # arm rail
        bar(m, (x, 0.03, d / 2 - 0.05), (x, 0.03, -0.1), 0.014, 0.012, "wood_dark")          # foot rail
    pt.cyl(m, (-w / 2, top[1], top[0]), "x", w, 0.02, "wood_dark", n=6)
    pt.cyl(m, (-w / 2 + 0.03, front[1], front[0]), "x", w - 0.06, 0.018, "wood_dark", n=6)
    sling = [top, (-0.42, 0.62), (-0.2, 0.36), (0.05, 0.27), (0.3, 0.31), front]
    stripes = ["stripe_teal", "stripe_cream", "stripe_mustard", "stripe_cream", "stripe_teal"]
    sw = (2 * xr - 0.06) / len(stripes)
    for k, role in enumerate(stripes):
        x0 = -xr + 0.03 + k * sw
        for (z0, y0), (z1, y1) in zip(sling, sling[1:]):
            bar(m, (x0 + sw / 2, y0 - 0.025, z0), (x0 + sw / 2, y1 - 0.025, z1), sw / 2 - 0.002, 0.005, role,
                side=(1.0, 0.0, 0.0))
    prof = [(d / 2, 0.0), (d / 2 - 0.08, 0.46), (-d / 2, h), (-0.06, 0.0)]
    pc.collide([(x, y, z) for x in (-w / 2, w / 2) for z, y in prof])


def build_fire_pit(pc: Piece, p: dict, spec: dict) -> None:
    """A ring of stones (two courses) round a bed of ash and embers, with three logs leaning into a tepee."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    r = w / 2
    pt.lathe(m, (0, 0, 0), "y", [(0.0, r - 0.02), (0.1, r), (0.14, r - 0.03), (0.24, r - 0.05), (0.27, r - 0.09),
                                (0.26, r - 0.15), (0.2, r - 0.17), (0.04, r - 0.18)], "stone", n=12,
             caps=(True, False), band_roles=[None, "stone_dark", None, "stone_dark", None, None, "stone_dark"])
    pt.lathe(m, (0, 0.04, 0), "y", [(0.0, r - 0.18), (0.02, r - 0.22), (0.05, 0.22), (0.07, 0.0)], "ash", n=12,
             caps=(False, False), band_roles=[None, None, "ember"])
    for k in range(3):
        a = math.radians(30 + 120 * k)
        foot = (0.3 * math.cos(a), 0.06, 0.3 * math.sin(a))
        bar(m, foot, (0.02 * math.cos(a), h - 0.045, 0.02 * math.sin(a)), 0.035, 0.035, "log_bark",
            side=(-math.sin(a), 0.0, math.cos(a)))
    for k in range(5):
        a = math.radians(72 * k + 10)
        bulb(m, (0.14 * math.cos(a), 0.1, 0.14 * math.sin(a)), 0.04, "ember")
    pc.sockets["light_0"] = [0.0, 0.3, 0.0]
    pt.collide_lathe(pc, (0, 0, 0), "y", 0.27, r)


def build_bean_bag(pc: Piece, p: dict, spec: dict) -> None:
    """A slouched bean bag: a lathed sack with a dent in its top and a seam band."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    r = w / 2
    pt.lathe(m, (0, 0, 0), "y", [(0.0, r * 0.82), (0.05, r * 0.96), (0.2, r), (0.38, r * 0.9), (0.52, r * 0.62),
                                (h, r * 0.3), (h - 0.08, 0.0)], "bean_rust", n=12, caps=(True, False),
             band_roles=[None, None, "bean_seam", None, None, None])
    pt.collide_lathe(pc, (0, 0, 0), "y", 0.5, r)


def build_cooler(pc: Piece, p: dict, spec: dict) -> None:
    """A red cooler box with a pale lid, side grips, a latch and a drain plug."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    bw = w / 2 - 0.035
    pt.cbox(m, (-bw, 0.0, -d / 2), (bw, h - 0.06, d / 2), "cooler_red", 0.03)
    pt.cbox(m, (-bw - 0.005, h - 0.065, -d / 2), (bw + 0.005, h, d / 2), "cooler_lid", 0.02)
    for sx in (-1, 1):
        gx0, gx1 = sorted((sx * bw, sx * (bw + 0.035)))
        pt.cbox(m, (gx0, h - 0.16, -0.09), (gx1, h - 0.12, 0.09), "cooler_lid", 0.008)
    pt.cbox(m, (-0.05, h - 0.12, d / 2 - 0.004), (0.05, h - 0.04, d / 2), "cooler_lid", 0.006)
    pt.cyl(m, (bw - 0.07, 0.05, d / 2 - 0.004), "z", 0.004, 0.018, "rubber", n=6)
    pt._full_collider(pc, p)


def build_string_lights_poles(pc: Piece, p: dict, spec: dict) -> None:
    """A string-light set for open ground: two weighted poles `span` apart, the strand between them with `bulbs`
    bulbs; sockets light_0..2 at a quarter, half and three quarters of the span."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    half = float(p["span"]) / 2
    bulbs_m = pc.leaf("bulbs", (0.0, 0.0, 0.0))
    for sx in (-1, 1):
        x = sx * half
        pt.cbox(m, (x - d / 2, 0.0, -d / 2), (x + d / 2, 0.07, d / 2), "steel_dark", 0.015)
        m.box((x - 0.035, 0.07, -0.035), (x + 0.035, h - 0.07, 0.035), "steel", "+x-x+z-z")
        m.box((x - 0.05, h - 0.07, -0.05), (x + 0.05, h, 0.05), "steel_dark", "+x-x+y+z-z")
        pc.collide_box((x - d / 2, 0.0, -d / 2), (x + d / 2, h, d / 2))
    centres = strand(m, bulbs_m, -half + 0.035, half - 0.035, h - 0.15, float(p["sag"]), int(p["bulbs"]))
    for k, t in enumerate((0.25, 0.5, 0.75)):
        c = centres[min(len(centres) - 1, int(t * len(centres)))]
        pc.sockets[f"light_{k}"] = [round(v, 4) for v in c]


def build_lantern(pc: Piece, p: dict, spec: dict) -> None:
    """A square metal lantern: a base, four corner posts, glass panes, a pyramid top and a bail; a candle inside."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    s, g = w / 2, w / 2 - 0.02
    pt.cbox(m, (-s, 0.0, -s), (s, 0.025, s), "steel_dark", 0.006)
    y1 = 0.2
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.box((sx * g - 0.008, 0.025, sz * g - 0.008), (sx * g + 0.008, y1, sz * g + 0.008), "steel_dark")
    m.box((-g + 0.008, 0.03, -g + 0.008), (g - 0.008, y1 - 0.005, g - 0.008), "glass", "+x-x+z-z")
    pt.cbox(m, (-s + 0.01, y1, -s + 0.01), (s - 0.01, y1 + 0.02, s - 0.01), "steel_dark", 0.005)
    pt.lathe(m, (0, y1 + 0.02, 0), "y", [(0.0, s - 0.02), (0.045, 0.03), (0.05, 0.0)], "steel_dark", n=4,
             caps=(False, False))
    for sx in (-1, 1):
        m.box((sx * 0.06 - 0.005, y1 + 0.05, -0.005), (sx * 0.06 + 0.005, h - 0.01, 0.005), "steel")
    m.box((-0.065, h - 0.01, -0.005), (0.065, h, 0.005), "steel")
    pt.cyl(m, (0, 0.025, 0), "y", 0.07, 0.025, "stripe_cream", n=6)
    bulbs_m = pc.leaf("bulbs", (0.0, 0.0, 0.0))
    bulb(bulbs_m, (0.0, 0.12, 0.0), 0.014)
    pc.sockets["light_0"] = [0.0, 0.12, 0.0]
    pt._full_collider(pc, p)


# --- the photo gazebo --------------------------------------------------------------------------------------------------
def build_backdrop(pc: Piece, p: dict, spec: dict) -> None:
    """A painted photo backdrop on two stands with a crossbar: ink blue with a low sun and gold and teal bands
    (a sunset, the yard's dusk); the cloth faces +Z."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    xs = w / 2 - 0.03
    for sx in (-1, 1):
        x = sx * xs
        pt.cbox(m, (x - 0.03, 0.0, -d / 2), (x + 0.03, 0.04, d / 2), "steel_dark", 0.01)
        m.box((x - 0.02, 0.04, -0.02), (x + 0.02, h - 0.04, 0.02), "steel", "+x-x+z-z")
    pt.cyl(m, (-w / 2, h - 0.04, 0.0), "x", w, 0.02, "steel_dark", n=6)
    x0, x1, yb, yt, z = -xs + 0.04, xs - 0.04, 0.12, h - 0.06, 0.03
    m.box((x0, yb, z - 0.01), (x1, yt, z), "backdrop_ink", "+x-x+y-y-z")
    bands = [(yb, 0.42, "backdrop_teal"), (0.42, 0.5, "backdrop_gold"), (0.5, 0.95, "backdrop_ink"),
             (0.95, 1.0, "backdrop_gold"), (1.0, yt, "backdrop_ink")]
    for y0, y1, role in bands:
        m.quad_z(x0, x1, y0, y1, z, 1, role)
    sun = [(0.55 * math.cos(math.pi * k / 10), 1.0 + 0.55 * math.sin(math.pi * k / 10)) for k in range(11)]
    m.poly([(x, y, z + 0.004) for x, y in sun], (0, 0, 1), "backdrop_sun")
    for k in range(3):
        y = 1.12 + 0.12 * k
        hw = math.sqrt(max(0.0, 0.55 ** 2 - (y + 0.04 - 1.0) ** 2))
        m.quad_z(-hw, hw, y, y + 0.04, z + 0.006, 1, "backdrop_ink")
    pc.collide_box((x0, yb, -0.02), (x1, yt, z))
    for sx in (-1, 1):
        pc.collide_box((sx * xs - 0.03, 0.0, -d / 2), (sx * xs + 0.03, h - 0.04, d / 2))


def build_tripod_camera(pc: Piece, p: dict, spec: dict) -> None:
    """A camera on a tripod: three legs, a centre column, a pan head and the camera with its lens towards +Z."""
    m = pc.mesh
    w, d, h = pt._dims(p)
    head = 1.28
    r = 0.25  # three legs at 120 degrees: the footprint is about 1.5 r by 1.73 r (the spec's w and d)
    feet = [(r * math.cos(math.radians(a)), 0.0, r * math.sin(math.radians(a))) for a in (180, 300, 60)]
    for f in feet:
        bar(m, (f[0], 0.02, f[2]), (f[0] * 0.08, head - 0.08, f[2] * 0.08), 0.012, 0.012, "steel_dark",
            side=(-f[2], 0.0, f[0]))
        pt.cbox(m, (f[0] - 0.02, 0.0, f[2] - 0.02), (f[0] + 0.02, 0.025, f[2] + 0.02), "rubber", 0.006)
    m.box((-0.015, 0.7, -0.015), (0.015, head, 0.015), "steel", "+x-x+z-z")
    pt.cbox(m, (-0.04, head, -0.04), (0.04, head + 0.04, 0.04), "steel_dark", 0.008)
    pt.cbox(m, (-0.08, head + 0.04, -0.045), (0.08, head + 0.15, 0.04), "plastic_dark", 0.015)
    pt.cyl(m, (0.02, head + 0.095, 0.04), "z", 0.1, 0.038, "rubber", n=10, c=0.006)
    pt.cbox(m, (-0.03, head + 0.15, -0.03), (0.03, h, 0.03), "plastic_dark", 0.008)
    m.quad_z(-0.07, -0.03, head + 0.11, head + 0.135, 0.0405, 1, "stripe_cream")
    pc.collide([(f[0], 0.0, f[2]) for f in feet] + [(-0.08, head + 0.15, -0.045), (0.08, head + 0.15, -0.045),
                                                     (0.08, head + 0.15, 0.14), (-0.08, head + 0.15, 0.14)])


def build_string_lights_hang(pc: Piece, p: dict, spec: dict) -> None:
    """A strand hung between two hooks `span` apart (a gazebo's posts): small hook plates at the ends, the cable
    sagging by `sag`, `bulbs` bulbs; its pivot is the middle of the hook line (y 0 at the top)."""
    m = pc.mesh
    half = float(p["span"]) / 2
    bulbs_m = pc.leaf("bulbs", (0.0, 0.0, 0.0))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * half, sx * (half - 0.03)))
        m.box((x0, -0.04, -0.03), (x1, 0.0, 0.03), "steel_dark")
        pc.collide_box((x0, -0.04, -0.03), (x1, 0.0, 0.03))
    centres = strand(m, bulbs_m, -half + 0.03, half - 0.03, -0.02, float(p["sag"]), int(p["bulbs"]), segs=8)
    pc.sockets["light_0"] = [round(v, 4) for v in centres[len(centres) // 2]]


BUILDERS = {
    "deckchair": build_deckchair, "fire_pit": build_fire_pit, "bean_bag": build_bean_bag, "cooler": build_cooler,
    "string_lights_poles": build_string_lights_poles, "lantern": build_lantern, "backdrop": build_backdrop,
    "tripod_camera": build_tripod_camera, "string_lights_hang": build_string_lights_hang,
}
FITTED = set(BUILDERS)  # props_task.build_prop calls fit() on these after the builder
