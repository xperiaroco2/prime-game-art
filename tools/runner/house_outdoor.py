"""The House map outside the house (art #81a, #81c; docs/house-outdoor.md): the plot's ground, fence, street, path,
driveway and outdoor stairs, and the evening sky and backdrop, as data (`layouts/house/outdoor/*.toml`) and a
generator. Standard library only.

- `fence_plan` walks the plot polygon and fills each edge with kit v2 fence modules round the openings (the wicket,
  the gates), a post cap on every fence post and gate posts at the gates; `fence_openings` lists what is left open.
- `ground_cells` paints the ground's 1 m cells from the zones (a later zone wins) with holes where another package
  lays a floor at y 0 and at the outdoor stairs; `ground_meshes` turns them into one vertex-coloured mesh (unshared
  cell corners: sharp zone edges, smooth value noise inside a zone), a coarse skirt out to the backdrop and the kerb.
- `stairs_plan` puts the two half flights and the landing into the 4 x 4 m stairwell as a U and rails its free edges.
- `prop_problems` checks the dressing placements against the plot, the clearances and each other.
- `flat_meshes` rings the backdrop's flats round the plot; `house_sky` paints the sky and the flats' textures.
- `write` writes the plan (`outdoor.json`), `outdoor.glb`, `backdrop.glb`, `sky.png`, the flats' PNGs and a top-down
  `plan.png`.

Coordinates are the design doc's (x east, y south, metres); Godot's x = x, z = y; a kit piece runs along its local
+X with its exterior at local +Z (docs/kit.md), turned about +Y by `yaw` degrees (house_layout's convention)."""

from __future__ import annotations

import json
import math
import struct
import tomllib
from pathlib import Path

from . import house_sky as sky
from .common import ROOT

DATA = ROOT / "layouts" / "house" / "outdoor"
HOUSE_GROUND = "ground.toml"  # beside the outdoor folder: the outdoor stairs' owner (house_stairs)
STAIRS_ID = "outdoor_stairs"
EPS = 1e-6

# ---------------------------------------------------------------- data


def load(folder: Path = DATA) -> dict:
    with open(folder / "plot.toml", "rb") as f:
        plot = tomllib.load(f)
    with open(folder / "sky.toml", "rb") as f:
        plot["sky_cfg"] = tomllib.load(f)
    plot["stairs"].update(house_stairs(folder.parent / HOUSE_GROUND))
    return plot


def house_stairs(ground: Path) -> dict:
    """The outdoor stairwell's rect and entry from their one owner, the house layout's ground floor (art #78: the walk
    and the basement passage use it): the hole `outdoor_stairs` and the climb of its upper flight (the edge the player
    steps down from)."""
    with open(ground, "rb") as f:
        g = tomllib.load(f)
    hole = next(h for h in g.get("holes", []) if h["id"] == STAIRS_ID)
    flight = next(s for s in g.get("stairs", []) if s["id"] == STAIRS_ID)
    return {"rect": list(hole["rect"]), "entry": flight["climb"]}


def turn_for(ext: tuple[int, int]) -> int:
    """The Y rotation (degrees) that turns a piece's local +Z to the doc direction ext (dx, dy)."""
    return {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): -90}[ext]


def local_x(turn: int) -> tuple[int, int]:
    t = math.radians(turn)
    return round(math.cos(t)), round(-math.sin(t))


def place(piece: str, x: float, y: float, h: float, yaw: int, **extra) -> dict:
    return {"piece": piece, "at": [round(x, 4), round(h, 4), round(y, 4)], "yaw": yaw, **extra}


def in_rect(r, x: float, y: float) -> bool:
    return r[0] - EPS <= x <= r[0] + r[2] + EPS and r[1] - EPS <= y <= r[1] + r[3] + EPS


def rects_overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] - EPS and b[0] < a[0] + a[2] - EPS and a[1] < b[1] + b[3] - EPS and b[1] < a[1] + a[3] - EPS


# ---------------------------------------------------------------- the fence


def plot_edges(data: dict) -> list[tuple[tuple, tuple]]:
    """The plot's edges in the order a fence runs: each edge's right side (doc, y south) is outside the plot."""
    pts = [tuple(map(float, p)) for p in data["plot"]]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    if area > 0:  # clockwise on screen (y south): reverse, so the outside is on the right
        pts = pts[::-1]
    return list(zip(pts, pts[1:] + pts[:1]))


def fence_plan(data: dict) -> dict:
    """Every fence piece on the plot's edges, and per edge its spans along the edge: (from, to, kind)."""
    fc = data["fence"]
    pieces, spans, problems = [], [], []
    for a, b in plot_edges(data):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if (abs(dx) > EPS and abs(dy) > EPS) or abs(L - round(L)) > EPS:
            problems.append(f"fence: the edge {a}-{b} is not axis-aligned in whole metres")
            continue
        d = (round(dx / L), round(dy / L))
        ext = (-d[1], d[0])
        turn = turn_for(ext)
        at = lambda s: (a[0] + d[0] * s, a[1] + d[1] * s)  # noqa: E731
        ops = []
        for op in fc["openings"]:
            c = op["centre"]
            s = (c[0] - a[0]) * d[0] + (c[1] - a[1]) * d[1]
            off = (c[0] - a[0]) * ext[0] + (c[1] - a[1]) * ext[1]
            if abs(off) < EPS and -EPS <= s <= L + EPS:
                ops.append((s - op["width"] / 2, s + op["width"] / 2, op))
        ops.sort(key=lambda o: o[0])
        cursor, edge_spans = 0.0, []
        for s0, s1, op in ops + [(L, L, None)]:
            gap = s0 - cursor
            if gap < -EPS or abs(gap - round(gap)) > EPS:
                problems.append(f"fence: an opening at {op and op['id']} does not fall on whole metres or overlaps")
                gap = max(round(gap), 0)
            n2, n1 = divmod(int(round(gap)), 2)
            for k in range(n2 + n1):
                length = 2 if k < n2 else 1
                x, y = at(cursor)
                pieces.append(place(fc["module"] if length == 2 else fc["filler"], x, y, 0.0, turn))
                pieces.append(place(fc["cap"], x, y, fc["post_h"], turn))
                edge_spans.append((cursor, cursor + length, "fence"))
                cursor += length
            if op is None:
                break
            x, y = at(s0)
            pieces.append(place(op["piece"], x, y, 0.0, turn, opening=op["id"]))
            p0, p1 = op["passage"]
            edge_spans += [(s0, s0 + p0, "fence"), (s0 + p0, s0 + p1, op["id"]), (s0 + p1, s1, "fence")]
            if op.get("gate_posts"):
                for s in (s0, s1):
                    gx, gy = at(s)
                    pieces.append(place(fc["gate_post"], gx, gy, 0.0, turn, opening=op["id"]))
            else:
                pieces.append(place(fc["cap"], x, y, fc["post_h"], turn))
            cursor = s1
        spans.append({"from": list(a), "to": list(b), "spans": edge_spans})
    return {"pieces": pieces, "edges": spans, "problems": problems}


def fence_openings(fence: dict) -> list[dict]:
    """What the fence leaves open: every span that is not fence, with its doc end points, and any hole in the
    coverage (a span missing between two pieces) as `gap`."""
    out = []
    for e in fence["edges"]:
        a, b = e["from"], e["to"]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        cursor = 0.0
        for s0, s1, kind in sorted(e["spans"]):
            if s0 > cursor + EPS:
                out.append({"kind": "gap", "from": [a[0] + d[0] * cursor, a[1] + d[1] * cursor],
                            "to": [a[0] + d[0] * s0, a[1] + d[1] * s0]})
            if kind != "fence":
                out.append({"kind": kind, "from": [a[0] + d[0] * s0, a[1] + d[1] * s0],
                            "to": [a[0] + d[0] * s1, a[1] + d[1] * s1]})
            cursor = max(cursor, s1)
        if cursor < L - EPS:
            out.append({"kind": "gap", "from": [a[0] + d[0] * cursor, a[1] + d[1] * cursor], "to": list(b)})
    return out


# ---------------------------------------------------------------- the outdoor stairs


def stairs_plan(data: dict) -> dict:
    """The U stairs in their 4 x 4 m rect: flight A from the entry edge down to the landing, the landing on the far
    edge, flight B back under the entry's side down to the passage; the railings on the hole's free edges; the walk
    (doc x, height, doc y) from the yard to the passage."""
    st = data["stairs"]
    x0, y0, w, d = st["rect"]
    if (w, d) != (4, 4):
        return {"pieces": [], "rails": [], "walk": [], "flights": [], "problems": ["stairs: the U needs a 4 x 4 m rect"]}
    half = st["drop"] / 2
    x1, y1 = x0 + w, y0 + d
    if st["entry"] == "N":
        a = place(st["flight"], x0 + 2, y1 - 1, -half, 90)
        land = place(st["landing"], x0, y1 - 1, -half, 0)
        b = place(st["flight"], x0 + 2, y0, -2 * half, -90)
        rail = [(x0 + 2, y0), (x0, y0), (x0, y1), (x1, y1), (x1, y0)]
        walk = [(x0 + 3, y0 - 1.5, 0.0), (x0 + 3, y0 + 0.2, 0.0), (x0 + 3, y1 - 0.5, -half), (x0 + 1, y1 - 0.5, -half),
                (x0 + 1, y0 + 0.2, -2 * half), (x0 + 1, y0 - 0.5, -2 * half)]
        flights = [[x0 + 2, y0, 2, 3], [x0, y1 - 1, 4, 1], [x0, y0, 2, 3]]
    elif st["entry"] == "S":
        a = place(st["flight"], x0 + 4, y0 + 1, -half, -90)
        land = place(st["landing"], x0, y0, -half, 0)
        b = place(st["flight"], x0, y1, -2 * half, 90)
        rail = [(x0 + 2, y1), (x0, y1), (x0, y0), (x1, y0), (x1, y1)]
        walk = [(x0 + 3, y1 + 1.5, 0.0), (x0 + 3, y1 - 0.2, 0.0), (x0 + 3, y0 + 0.5, -half), (x0 + 1, y0 + 0.5, -half),
                (x0 + 1, y1 - 0.2, -2 * half), (x0 + 1, y1 + 0.5, -2 * half)]
        flights = [[x0 + 2, y0 + 1, 2, 3], [x0, y0, 4, 1], [x0, y0 + 1, 2, 3]]
    else:
        return {"pieces": [], "rails": [], "walk": [], "flights": [], "problems": [f"stairs: entry {st['entry']}?"]}
    rails = []
    for p, q in zip(rail, rail[1:]):
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = abs(dx) + abs(dy)
        u = (round(dx / L), round(dy / L))
        turn = turn_for((-u[1], u[0]))
        for k in range(int(L // 2)):
            rails.append(place(st["railing"], p[0] + u[0] * 2 * k, p[1] + u[1] * 2 * k, 0.0, turn))
    rails.append(place(st["railing_post"], rail[-1][0], rail[-1][1], 0.0, 0))
    return {"pieces": [a, land, b], "rails": rails, "walk": [[p[0], p[2], p[1]] for p in walk], "flights": flights,
            "problems": []}


# ---------------------------------------------------------------- the ground


def _seg_dist(px, py, a, b) -> float:
    ax, ay, bx, by = *a, *b
    vx, vy = bx - ax, by - ay
    t = 0.0 if vx == vy == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def zone_hit(z: dict, x: float, y: float) -> bool:
    if "rect" in z:
        r = z["rect"]
        return r[0] - EPS <= x < r[0] + r[2] - EPS and r[1] - EPS <= y < r[1] + r[3] - EPS
    line = z["line"]
    return any(_seg_dist(x, y, a, b) <= z["width"] / 2 + EPS for a, b in zip(line, line[1:]))


def holes(data: dict) -> list[dict]:
    return list(data["floor_holes"]) + [{"id": "outdoor_stairs", "rect": data["stairs"]["rect"]}]


def ground_cells(data: dict) -> dict[tuple[int, int], str]:
    """The paint of every ground cell (its north-west corner, in cells) that is not under a hole."""
    gx, gy, gw, gd = data["ground"]
    c = data["cell_m"]
    hs = [h["rect"] for h in holes(data)]
    cells = {}
    for j in range(int(round(gd / c))):
        for i in range(int(round(gw / c))):
            x, y = gx + (i + 0.5) * c, gy + (j + 0.5) * c
            if any(in_rect(r, x, y) for r in hs):
                continue
            paint = None
            for z in data["zones"]:
                if zone_hit(z, x, y):
                    paint = z["paint"]
            if paint:
                cells[(i, j)] = paint
    return cells


def _hash(ix: int, iy: int, seed: int) -> float:
    h = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def value_noise(x: float, y: float, seed: int) -> float:
    """2D value noise in world units (lattice 1), two octaves, 0..1."""
    total = 0.0
    for o, w in ((1.0, 0.67), (2.17, 0.33)):
        px, py = x * o, y * o
        ix, iy = math.floor(px), math.floor(py)
        fx, fy = sky.smooth(px - ix), sky.smooth(py - iy)
        a = _hash(ix, iy, seed) + (_hash(ix + 1, iy, seed) - _hash(ix, iy, seed)) * fx
        b = _hash(ix, iy + 1, seed) + (_hash(ix + 1, iy + 1, seed) - _hash(ix, iy + 1, seed)) * fx
        total += (a + (b - a) * fy) * w
    return total


def paint_at(data: dict, paint: str, x: float, y: float) -> tuple[float, float, float]:
    """The sRGB colour of a paint at a point: its hex times 1 +- vary by value noise of its feature size."""
    p = data["paints"][paint]
    base = sky.hex_rgb(p["hex"])
    n = value_noise(x / p["scale_m"], y / p["scale_m"], sum(map(ord, paint)))
    k = 1 + p["vary"] * (2 * n - 1)
    return tuple(min(1.0, c * k) for c in base)


class Mesh:
    def __init__(self, name: str, material: int) -> None:
        self.name, self.material = name, material
        self.pos, self.nrm, self.uv0, self.uv1, self.col, self.idx = [], [], [], [], [], []

    def quad(self, pts, normal, cols=None, uv1_of=None) -> None:
        """A quad of four Godot points (any order round it), facing `normal`."""
        base = len(self.pos)
        for k, p in enumerate(pts):
            self.pos.append(tuple(p))
            self.nrm.append(tuple(normal))
            ax = (0, 2) if abs(normal[1]) > 0.5 else ((2, 1) if abs(normal[0]) > 0.5 else (0, 1))
            self.uv0.append((p[ax[0]], -p[ax[1]] if ax[1] == 1 else p[ax[1]]))
            self.uv1.append(uv1_of(p) if uv1_of else (0.0, 0.0))
            self.col.append(tuple(cols[k]) + (1.0,) if cols else (1.0, 1.0, 1.0, 1.0))
        for tri in ((0, 1, 2), (0, 2, 3)):
            i = [base + t for t in tri]
            p0, p1, p2 = (self.pos[t] for t in i)
            e1 = [p1[q] - p0[q] for q in range(3)]
            e2 = [p2[q] - p0[q] for q in range(3)]
            cr = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
            if sum(cr[q] * normal[q] for q in range(3)) < 0:
                i = [i[0], i[2], i[1]]
            self.idx += i

    @property
    def tris(self) -> int:
        return len(self.idx) // 3


def ground_meshes(data: dict) -> list[Mesh]:
    """The ground (`ground-col`: Godot makes its trimesh collider), the skirt beyond and the kerb (`kerb-col`)."""
    gx, gy, gw, gd = data["ground"]
    c = data["cell_m"]
    uv = lambda p: ((p[0] - gx) / gw, (p[2] - gy) / gd)  # noqa: E731
    g = Mesh("ground-col", 0)
    for (i, j), paint in sorted(ground_cells(data).items()):
        xs, ys = gx + i * c, gy + j * c
        pts = [(xs, 0.0, ys), (xs + c, 0.0, ys), (xs + c, 0.0, ys + c), (xs, 0.0, ys + c)]
        g.quad(pts, (0, 1, 0), [paint_at(data, paint, p[0], p[2]) for p in pts], uv)
    cx, cy = data["sky_cfg"]["backdrop"]["centre"]
    R = data["skirt_m"]
    sx0, sy0, sx1, sy1 = cx - R, cy - R, cx + R, cy + R
    suv = lambda p: ((p[0] - sx0) / (2 * R), (p[2] - sy0) / (2 * R))  # noqa: E731
    s = Mesh("skirt", 0)
    for rx0, ry0, rx1, ry1 in ((sx0, sy0, sx1, gy), (sx0, gy + gd, sx1, sy1), (sx0, gy, gx, gy + gd),
                               (gx + gw, gy, sx1, gy + gd)):
        nx, ny = max(1, round((rx1 - rx0) / 8)), max(1, round((ry1 - ry0) / 8))
        for i in range(nx):
            for j in range(ny):
                xa, xb = rx0 + (rx1 - rx0) * i / nx, rx0 + (rx1 - rx0) * (i + 1) / nx
                ya, yb = ry0 + (ry1 - ry0) * j / ny, ry0 + (ry1 - ry0) * (j + 1) / ny
                pts = [(xa, 0.0, ya), (xb, 0.0, ya), (xb, 0.0, yb), (xa, 0.0, yb)]
                s.quad(pts, (0, 1, 0), [paint_at(data, "beyond", p[0], p[2]) for p in pts], suv)
    k = Mesh("kerb-col", 0)
    kb = data["kerb"]
    kc = sky.hex_rgb(data["paints"]["concrete"]["hex"])
    y0, y1, h = kb["y"] - kb["width"] / 2, kb["y"] + kb["width"] / 2, kb["height"]
    cuts = sorted([gx] + [v for gp in kb["gaps"] for v in gp] + [gx + gw])
    for xa, xb in zip(cuts[::2], cuts[1::2]):
        col = [kc] * 4
        k.quad([(xa, h, y0), (xb, h, y0), (xb, h, y1), (xa, h, y1)], (0, 1, 0), col)
        k.quad([(xa, 0, y0), (xb, 0, y0), (xb, h, y0), (xa, h, y0)], (0, 0, -1), col)
        k.quad([(xa, 0, y1), (xb, 0, y1), (xb, h, y1), (xa, h, y1)], (0, 0, 1), col)
        k.quad([(xa, 0, y0), (xa, 0, y1), (xa, h, y1), (xa, h, y0)], (-1, 0, 0), col)
        k.quad([(xb, 0, y0), (xb, 0, y1), (xb, h, y1), (xb, h, y0)], (1, 0, 0), col)
    return [g, s, k]


# ---------------------------------------------------------------- props


def prop_rects(data: dict) -> list[dict]:
    out = []
    for p in data["props"]:
        sx, _, sy = p["size"]
        if p.get("yaw", 0) % 180 == 90:
            sx, sy = sy, sx
        for x, y in p["at"]:
            out.append({"id": p["id"], "at": [x, y], "rect": [x - sx / 2, y - sy / 2, sx, sy]})
    return out


def prop_problems(data: dict) -> list[str]:
    """Each prop inside the ground, off the clearances, the holes and the fence line, and clear of the others."""
    probs, rs = [], prop_rects(data)
    g = data["ground"]
    fence_lines = []
    for a, b in plot_edges(data):
        fence_lines.append([min(a[0], b[0]) - 0.1, min(a[1], b[1]) - 0.1, abs(b[0] - a[0]) + 0.2,
                            abs(b[1] - a[1]) + 0.2])
    for r in rs:
        x, y, w, d = r["rect"]
        name = f"{r['id']} at {r['at']}"
        if not (in_rect(g, x, y) and in_rect(g, x + w, y + d)):
            probs.append(f"props: {name} leaves the ground")
        for c in data.get("clear", []):
            if rects_overlap(r["rect"], c["rect"]):
                probs.append(f"props: {name} blocks {c['id']}")
        for h in holes(data):
            if rects_overlap(r["rect"], h["rect"]):
                probs.append(f"props: {name} stands in the hole {h['id']}")
        if any(rects_overlap(r["rect"], f) for f in fence_lines):
            probs.append(f"props: {name} crosses the fence")
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            if rects_overlap(a["rect"], b["rect"]):
                probs.append(f"props: {a['id']} at {a['at']} overlaps {b['id']} at {b['at']}")
    return probs


# ---------------------------------------------------------------- the backdrop


def flat_meshes(cfg: dict) -> list[Mesh]:
    """One open ring per flat round the backdrop's centre, facing in, u round the ring, v down its height."""
    bd = cfg["backdrop"]
    cx, cy, n = *bd["centre"], int(bd["segments"])
    out = []
    for k, f in enumerate(bd["flats"]):
        m = Mesh(f"flat_{f['id']}", k)
        r, lo, hi = f["radius"], f["base"], f["height"]
        for s in range(n):
            t0, t1 = 2 * math.pi * s / n, 2 * math.pi * (s + 1) / n
            p = [(cx + r * math.cos(t0), lo, cy + r * math.sin(t0)), (cx + r * math.cos(t1), lo, cy + r * math.sin(t1)),
                 (cx + r * math.cos(t1), hi, cy + r * math.sin(t1)), (cx + r * math.cos(t0), hi, cy + r * math.sin(t0))]
            tm = (t0 + t1) / 2
            base = len(m.pos)
            m.quad(p, (-math.cos(tm), 0.0, -math.sin(tm)))
            # u round the ring, v from the top (glTF's UV origin is the image's top-left)
            for q, (u, v) in enumerate(((s / n, 1.0), ((s + 1) / n, 1.0), ((s + 1) / n, 0.0), (s / n, 0.0))):
                m.uv0[base + q] = (u, v)
                m.nrm[base + q] = (-math.cos(t0 if q in (0, 3) else t1), 0.0, -math.sin(t0 if q in (0, 3) else t1))
        out.append(m)
    return out


def flat_problems(cfg: dict, data: dict) -> list[str]:
    bd, probs = cfg["backdrop"], []
    if len(bd["flats"]) > 6:
        probs.append(f"backdrop: {len(bd['flats'])} flats (at most 6)")
    if list(cfg["sky"]["size"]) != [1024, 512]:
        probs.append("sky: the panorama must be 1024 x 512")
    cx, cy = bd["centre"]
    gx, gy, gw, gd = data["ground"]
    far = max(math.hypot(x - cx, y - cy) for x in (gx, gx + gw) for y in (gy, gy + gd))
    for f in bd["flats"]:
        if f["radius"] <= far + 1:
            probs.append(f"backdrop: the flat {f['id']} (r {f['radius']}) cuts the ground (its far corner at {far:.1f} m)")
        if f["radius"] >= data["skirt_m"]:
            probs.append(f"backdrop: the flat {f['id']} stands beyond the skirt")
        if f["radius"] < bd["fog_start_m"]:
            probs.append(f"backdrop: the flat {f['id']} is nearer than the fog's start")
    return probs


# ---------------------------------------------------------------- GLB


def glb_bytes(meshes: list[Mesh], materials: list[dict], images: list[bytes] | None = None) -> bytes:
    """A glTF 2.0 binary: one node per mesh with POSITION, NORMAL, TEXCOORD_0, TEXCOORD_1, COLOR_0 (VEC4 float) and
    uint32 indices; the materials as given (glTF dicts); `images` embedded PNGs (texture k = image k)."""
    blob, views, accessors = bytearray(), [], []

    def add(data: bytes, target: int | None) -> int:
        while len(blob) % 4:
            blob.append(0)
        view = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)}
        if target:
            view["target"] = target
        blob.extend(data)
        views.append(view)
        return len(views) - 1

    def acc(values, kind: str, comps: int, mn_mx: bool = False) -> int:
        flat = [c for v in values for c in v]
        view = add(struct.pack(f"<{len(flat)}f", *flat), 34962)
        a = {"bufferView": view, "componentType": 5126, "count": len(values), "type": kind}
        if mn_mx:
            a["min"] = [min(v[q] for v in values) for q in range(comps)]
            a["max"] = [max(v[q] for v in values) for q in range(comps)]
        accessors.append(a)
        return len(accessors) - 1

    gl_meshes, nodes = [], []
    for m in meshes:
        if not m.idx:
            continue
        attrs = {"POSITION": acc(m.pos, "VEC3", 3, True), "NORMAL": acc(m.nrm, "VEC3", 3),
                 "TEXCOORD_0": acc(m.uv0, "VEC2", 2), "TEXCOORD_1": acc(m.uv1, "VEC2", 2),
                 "COLOR_0": acc(m.col, "VEC4", 4)}
        iv = add(struct.pack(f"<{len(m.idx)}I", *m.idx), 34963)
        accessors.append({"bufferView": iv, "componentType": 5125, "count": len(m.idx), "type": "SCALAR"})
        gl_meshes.append({"name": m.name, "primitives": [{"attributes": attrs, "indices": len(accessors) - 1,
                                                          "material": m.material}]})
        nodes.append({"name": m.name, "mesh": len(gl_meshes) - 1})
    doc = {"asset": {"version": "2.0", "generator": "prime-game-art house_outdoor"},
           "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": gl_meshes,
           "materials": materials, "accessors": accessors, "bufferViews": views}
    if images:
        doc["images"] = [{"bufferView": add(png, None), "mimeType": "image/png"} for png in images]
        doc["textures"] = [{"source": k} for k in range(len(images))]
        doc["samplers"] = [{"wrapS": 10497, "wrapT": 33071}]
        for t in doc["textures"]:
            t["sampler"] = 0
    if any("extensions" in m for m in materials):
        doc["extensionsUsed"] = ["KHR_materials_unlit"]
    while len(blob) % 4:
        blob.append(0)
    doc["buffers"] = [{"byteLength": len(blob)}]
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


# ---------------------------------------------------------------- the plan


def plan(data: dict) -> dict:
    fence = fence_plan(data)
    stairs = stairs_plan(data)
    opens = fence_openings(fence)
    problems = fence["problems"] + stairs["problems"] + prop_problems(data) + flat_problems(data["sky_cfg"], data)
    want = sorted(op["id"] for op in data["fence"]["openings"])
    got = sorted(o["kind"] for o in opens)
    if got != want:
        problems.append(f"fence: open spans {got}, expected only {want}")
    return {"fence": fence, "openings": opens, "stairs": stairs, "props": prop_rects(data), "problems": problems}


def summary(data: dict, p: dict, meshes: list[Mesh]) -> dict:
    count: dict[str, int] = {}
    for pc in p["fence"]["pieces"] + p["stairs"]["pieces"] + p["stairs"]["rails"]:
        count[pc["piece"]] = count.get(pc["piece"], 0) + 1
    fence_m = sum(s1 - s0 for e in p["fence"]["edges"] for s0, s1, _ in e["spans"])
    return {"pieces": dict(sorted(count.items())), "fence_m": fence_m,
            "ground_tris": {m.name: m.tris for m in meshes}, "flats": len(data["sky_cfg"]["backdrop"]["flats"]),
            "problems": p["problems"]}


def plan_png(data: dict, p: dict, path: Path, ppm: int = 14, margin: float = 4.0) -> Path:
    """A top-down plan: the ground paints, the holes (grey: the house as a block), the fence (white, the openings
    green), the stairs (blue), the props (orange: lights, magenta: the rest)."""
    gx, gy, gw, gd = data["ground"]
    W, H = int((gw + 2 * margin) * ppm), int((gd + 2 * margin) * ppm)
    img = [bytearray(b"\x18\x1a\x22" * W) for _ in range(H)]

    def fill(x0, y0, x1, y1, rgb):
        a, b = int((x0 - gx + margin) * ppm), int((x1 - gx + margin) * ppm)
        c, d = int((y0 - gy + margin) * ppm), int((y1 - gy + margin) * ppm)
        px = bytes(rgb)
        for r in range(max(c, 0), min(max(d, c + 1), H)):
            for q in range(max(a, 0), min(max(b, a + 1), W)):
                img[r][q * 3:q * 3 + 3] = px

    c = data["cell_m"]
    for (i, j), paint in ground_cells(data).items():
        x, y = gx + i * c, gy + j * c
        fill(x, y, x + c, y + c, [sky.byte(v) for v in paint_at(data, paint, x + c / 2, y + c / 2)])
    for h in holes(data):
        r = h["rect"]
        fill(r[0], r[1], r[0] + r[2], r[1] + r[3], (70, 70, 76) if h["id"] != "outdoor_stairs" else (20, 30, 60))
    for fl in p["stairs"]["flights"]:
        fill(fl[0] + 0.1, fl[1] + 0.1, fl[0] + fl[2] - 0.1, fl[1] + fl[3] - 0.1, (60, 90, 170))
    for e in p["fence"]["edges"]:
        a, b = e["from"], e["to"]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        for s0, s1, kind in e["spans"]:
            pa = (a[0] + d[0] * s0, a[1] + d[1] * s0)
            pb = (a[0] + d[0] * s1, a[1] + d[1] * s1)
            col = (235, 230, 220) if kind == "fence" else (60, 220, 90)
            fill(min(pa[0], pb[0]) - 0.1, min(pa[1], pb[1]) - 0.1, max(pa[0], pb[0]) + 0.1, max(pa[1], pb[1]) + 0.1, col)
    lights = {pr["id"] for pr in data["props"] if pr.get("light")}
    for r in p["props"]:
        x, y, w, d = r["rect"]
        fill(x, y, x + w, y + d, (255, 170, 40) if r["id"] in lights else (220, 60, 200))
    return sky.write_png(path, W, H, [bytes(r) for r in img])


def write(data: dict, out: Path) -> dict:
    """Writes everything into `out`; returns the summary (its `problems` empty when the plan is clean)."""
    out.mkdir(parents=True, exist_ok=True)
    p = plan(data)
    meshes = ground_meshes(data)
    ground_mat = [{"name": "outdoor_ground-vcol", "pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.95}}]
    (out / "outdoor.glb").write_bytes(glb_bytes(meshes, ground_mat))
    cfg = data["sky_cfg"]
    w, h, rows = sky.sky_rows(cfg["sky"])
    sky.write_png(out / "sky.png", w, h, rows)
    seam = sky.seam_step(rows)
    images, mats, windows = [], [], {}
    for k, f in enumerate(cfg["backdrop"]["flats"]):
        fw, fh, rgba, placed = sky.flat_rows(f, int(cfg["backdrop"]["seed"]) + k)
        windows[f["id"]] = placed
        a = sky.png_bytes(fw, fh, rgba, 4)
        (out / f"flat_{f['id']}.png").write_bytes(a)
        images.append(a)
        mats.append({"name": f"flat_{f['id']}", "doubleSided": False,
                     "alphaMode": "BLEND" if f["profile"] == "haze" else "MASK",
                     "pbrMetallicRoughness": {"baseColorTexture": {"index": k}, "metallicFactor": 0.0},
                     "extensions": {"KHR_materials_unlit": {}}})
    flats = flat_meshes(cfg)
    (out / "backdrop.glb").write_bytes(glb_bytes(flats, mats, images))
    plan_png(data, p, out / "plan.png")
    s = summary(data, p, meshes)
    s["sky"] = {"size": [w, h], "seam_step": round(seam[0], 2), "inner_step": round(seam[1], 2)}
    s["windows"] = windows
    s["backdrop"] = {"flats": [f"flat_{f['id']}" for f in cfg["backdrop"]["flats"]], "gi_mode": "disabled",
                     "fog_start_m": cfg["backdrop"]["fog_start_m"], "tris": {m.name: m.tris for m in flats}}
    doc = {"summary": s, "fence": p["fence"]["pieces"], "openings": p["openings"], "stairs": p["stairs"],
           "props": p["props"], "lights": [r for r in p["props"] if r["id"] in
                                           {pr["id"] for pr in data["props"] if pr.get("light")}]}
    (out / "outdoor.json").write_text(json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
    return s
