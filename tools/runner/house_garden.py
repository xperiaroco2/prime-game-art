"""The garden and the greenhouse's roof (art #80, docs/house-garden.md): `layouts/house/outdoor/garden.toml` loaded and
checked (the path network, the fixed props, the clearances, the herb route), a seeded scatter of trees, bushes and
flower beds on a Poisson disc (Bridson), the greenhouse's glass pitched roof from kit v2's pieces with a check that
every gable meets a rafter on both slopes, a top-down plan and `garden.json` for the assembly. Pure Python.

Plan metres as #81a's (docs/house-outdoor.md): x east, y south; Godot x = x, z = y."""

from __future__ import annotations

import json
import math
import random
import tomllib
from pathlib import Path
from typing import Any

from . import common, house_layout as hl, house_outdoor as ho, house_sky

GARDEN = common.ROOT / "layouts" / "house" / "outdoor" / "garden.toml"
EPS = 1e-6
WALL_M = 0.2  # the greenhouse's glass walls (kit wall_t_m): scatter keeps this off the rect and its margin
RAFTER_M = 0.06  # a gable is closed on a slope when a glass roof bay's rafter lies this close to its plane
CANDIDATE_M = 0.4  # the scatter's candidate points: a dense Poisson disc
SAMPLE_M = 0.25  # the route's segments are checked at this step


def load(path: Path = GARDEN) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------- geometry

def seg_dist(px: float, py: float, a, b) -> float:
    return ho._seg_dist(px, py, a, b)


def line_dist(px: float, py: float, line) -> float:
    return min(seg_dist(px, py, a, b) for a, b in zip(line, line[1:]))


def rect_dist(rect, px: float, py: float) -> float:
    """The distance from a point to a rect [x, y, w, d] (0 inside)."""
    x, y, w, d = rect
    return math.hypot(max(x - px, 0.0, px - x - w), max(y - py, 0.0, py - y - d))


def _segs_cross(a, b, c, d) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return o1 * o2 < 0 and o3 * o4 < 0


def rect_line_dist(rect, line) -> float:
    """The least distance between a rect and a polyline (0 where they touch or cross)."""
    x, y, w, d = rect
    corners = [(x, y), (x + w, y), (x + w, y + d), (x, y + d)]
    edges = list(zip(corners, corners[1:] + corners[:1]))
    best = math.inf
    for a, b in zip(line, line[1:]):
        if rect_dist(rect, *a) == 0.0 or any(_segs_cross(a, b, c, e) for c, e in edges):
            return 0.0
        best = min(best, rect_dist(rect, *a), rect_dist(rect, *b), *(seg_dist(cx, cy, a, b) for cx, cy in corners))
    return best


def rects_overlap(a, b, margin: float = 0.0) -> bool:
    return (a[0] - margin < b[0] + b[2] - EPS and b[0] - margin < a[0] + a[2] - EPS
            and a[1] - margin < b[1] + b[3] - EPS and b[1] - margin < a[1] + a[3] - EPS)


def inside(outer, inner) -> bool:
    return (outer[0] - EPS <= inner[0] and inner[0] + inner[2] <= outer[0] + outer[2] + EPS
            and outer[1] - EPS <= inner[1] and inner[1] + inner[3] <= outer[1] + outer[3] + EPS)


# ---------------------------------------------------------------- props

def prop_rects(data: dict) -> list[dict]:
    """Every fixed prop's footprint rect; `solid` unless flat or hung (h) above a walking head."""
    out = []
    for p in data.get("props", []):
        sx, _, sy = p["size"]
        if p.get("yaw", 0) % 180 == 90:
            sx, sy = sy, sx
        for x, y in p["at"]:
            out.append({"id": p["id"], "src": p.get("src", ""), "at": [x, y], "yaw": p.get("yaw", 0),
                        "face": p.get("face"), "h": p.get("h", 0.0), "size": p["size"], "light": p.get("light", False),
                        "station": p.get("station"), "rect": [x - sx / 2, y - sy / 2, sx, sy],
                        "solid": not p.get("flat") and p.get("h", 0.0) < 1.8})
    return out


def blockers(data: dict, plot: dict) -> list[dict]:
    """What the scatter and the props avoid besides the paths: the greenhouse, the plot's floors and holes (house,
    terrace, garage, the outdoor stairs), the garden's and the plot's clearances."""
    out = [{"id": "greenhouse", "rect": data["greenhouse"]}]
    out += [{"id": h["id"], "rect": h["rect"]} for h in ho.holes(plot)]
    out += [{"id": c["id"], "rect": c["rect"]} for c in data.get("clear", []) + plot.get("clear", [])]
    return out


# ---------------------------------------------------------------- the scatter

def poisson(rng: random.Random, rect, r: float, k: int = 30) -> list[tuple[float, float]]:
    """Bridson's Poisson disc over rect [x, y, w, d] with the least distance r."""
    x0, y0, w, d = rect
    cell = r / math.sqrt(2)
    nx, ny = int(math.ceil(w / cell)), int(math.ceil(d / cell))
    grid: dict[tuple[int, int], tuple[float, float]] = {}
    first = (x0 + rng.random() * w, y0 + rng.random() * d)
    pts, active = [first], [first]
    grid[(int((first[0] - x0) / cell), int((first[1] - y0) / cell))] = first
    while active:
        i = rng.randrange(len(active))
        px, py = active[i]
        for _ in range(k):
            a, rr = rng.random() * math.tau, r * (1 + rng.random())
            qx, qy = px + rr * math.cos(a), py + rr * math.sin(a)
            if not (x0 <= qx < x0 + w and y0 <= qy < y0 + d):
                continue
            gx, gy = int((qx - x0) / cell), int((qy - y0) / cell)
            if any((o := grid.get((gx + u, gy + v))) and math.hypot(o[0] - qx, o[1] - qy) < r
                   for u in range(-2, 3) for v in range(-2, 3)):
                continue
            grid[(gx, gy)] = (qx, qy)
            pts.append((qx, qy))
            active.append((qx, qy))
            break
        else:
            active.pop(i)
    return pts if nx and ny else []


def scatter(data: dict, plot: dict) -> tuple[list[dict], list[str]]:
    """The seeded scatter: candidates on one dense Poisson disc (CANDIDATE_M apart) over the garden, shuffled per
    kind; per [[scatter]] kind in order, a candidate is taken while fewer than `count` are, when its footprint circle
    stays in the garden, `margin` off the paths' edges, the fixed props and the blockers, `spacing` from its own kind
    and radius plus margin from the plants placed before. Each takes a kind (cycled), a scale and a yaw. Same seed,
    same garden."""
    placed: list[dict] = []
    problems: list[str] = []
    gx, gy, gw, gd = data["rect"]
    fixed = [p for p in prop_rects(data) if p["solid"]]
    blocks = blockers(data, plot)
    cands = poisson(random.Random(f"{data['seed']}:candidates"), data["rect"], CANDIDATE_M)
    for sc in data.get("scatter", []):
        rng = random.Random(f"{data['seed']}:{sc['id']}")
        r, m, sp = float(sc["radius"]), float(sc["margin"]), float(sc["spacing"])
        order = list(cands)
        rng.shuffle(order)
        mine: list[dict] = []
        for x, y in order:
            if len(mine) == sc["count"]:
                break
            if not (gx + r <= x <= gx + gw - r and gy + r <= y <= gy + gd - r):
                continue
            if any(line_dist(x, y, p["line"]) < p["width"] / 2 + r + m for p in data["paths"]):
                continue
            if any(rect_dist(f["rect"], x, y) < r + m for f in fixed):
                continue
            if any(rect_dist(b["rect"], x, y) < r + m + (WALL_M if b["id"] == "greenhouse" else 0.0) for b in blocks):
                continue
            if any(math.hypot(q["at"][0] - x, q["at"][1] - y) < sp for q in mine):
                continue
            if any(math.hypot(q["at"][0] - x, q["at"][1] - y) < r + q["radius"] + max(m, q["margin"])
                   for q in placed):
                continue
            kind = sc["kinds"][len(mine) % len(sc["kinds"])]
            mine.append({"id": sc["id"], "kind": kind, "at": [round(x, 3), round(y, 3)],
                         "yaw": rng.randrange(0, 360, 15), "scale": rng.choice(sc["scales"]),
                         "radius": r, "margin": m, "size": sc["size"]})
        if len(mine) < sc["count"]:
            problems.append(f"scatter: {sc['id']}: room for {len(mine)} of {sc['count']} (spacing {sp:g} m)")
        placed += mine
    return placed, problems


# ---------------------------------------------------------------- the network and the route

def network_problems(data: dict) -> list[str]:
    """Each end's node on a path; the paths joined into one network (a path touches another at one of its points)."""
    probs = []
    paths = data["paths"]
    for e in data.get("ends", []):
        if min(line_dist(*e["node"], p["line"]) for p in paths) > EPS + 1e-3:
            probs.append(f"paths: {e['id']}'s node {e['node']} is on no path")
    joined, todo = {paths[0]["id"]}, True
    while todo:
        todo = False
        for p in paths:
            if p["id"] in joined:
                continue
            for q in paths:
                if q["id"] in joined and any(line_dist(*pt, q["line"]) < 1e-3 for pt in p["line"]) or (
                        q["id"] in joined and any(line_dist(*pt, p["line"]) < 1e-3 for pt in q["line"])):
                    joined.add(p["id"])
                    todo = True
                    break
    for p in paths:
        if p["id"] not in joined:
            probs.append(f"paths: {p['id']} does not join the network")
    return probs


def route(data: dict) -> dict:
    """The herb route's length, its time at the doc's speed and its gap to the doc's time."""
    rt = data["route"]
    pts = rt["points"]
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    t = length / float(rt["speed"])
    return {"id": rt["id"], "length_m": round(length, 2), "time_s": round(t, 2), "doc_m": rt["doc_m"],
            "doc_s": rt["doc_s"], "off_s": round(t - float(rt["doc_s"]), 2), "ok": abs(t - rt["doc_s"]) <= rt["tol_s"]}


def route_problems(data: dict) -> list[str]:
    """The route's time within tol_s of the doc's; its points inside the garden on the paths."""
    rep, probs = route(data), []
    if not rep["ok"]:
        probs.append(f"route: {rep['id']} {rep['length_m']} m, {rep['time_s']} s against the doc's {rep['doc_s']} s")
    pts = data["route"]["points"]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / SAMPLE_M))
        for i in range(n + 1):
            x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
            if not ho.in_rect(data["rect"], x, y) or rect_dist(data["greenhouse"], x, y) < 0.3:
                continue
            if min(line_dist(x, y, p["line"]) for p in data["paths"]) > 0.7:
                probs.append(f"route: ({x:.2f}, {y:.2f}) between {a} and {b} leaves the paths")
                break
    return probs


# ---------------------------------------------------------------- checks

def check(data: dict, plot: dict, placed: list[dict] | None = None) -> list[str]:
    """Every rule: props inside the garden or the plot, off the paths' 1.4 m (solid ones), the blockers (a station's
    prop may stand in its own clearance), each other and the fence; the network; the route; the plants' footprints."""
    probs = network_problems(data) + route_problems(data)
    props = prop_rects(data)
    blocks = blockers(data, plot)
    for p in props:
        name = f"{p['id']} at {p['at']}"
        if not inside(plot["ground"], p["rect"]):
            probs.append(f"props: {name} leaves the ground")
        if not p["solid"]:
            continue
        for path in data["paths"]:
            if rect_line_dist(p["rect"], path["line"]) < path["width"] / 2 - EPS:
                probs.append(f"props: {name} blocks the path {path['id']}")
        for b in blocks:
            if rects_overlap(p["rect"], b["rect"]) and not (p["station"] and b["id"].startswith("dropoff")):
                probs.append(f"props: {name} stands in {b['id']}")
    solid = [p for p in props if p["solid"]]
    for i, a in enumerate(solid):
        for b in solid[i + 1:]:
            if rects_overlap(a["rect"], b["rect"]):
                probs.append(f"props: {a['id']} at {a['at']} overlaps {b['id']} at {b['at']}")
    for q in placed or []:
        x, y = q["at"]
        if any(line_dist(x, y, p["line"]) < p["width"] / 2 + q["radius"] - EPS for p in data["paths"]):
            probs.append(f"scatter: {q['id']} at {q['at']} blocks a path")
    return probs


def ground_zone_problems(data: dict, plot: dict) -> list[str]:
    """Each garden path is registered as a plot.toml zone (same id, paint, line and width) so #81a paints it."""
    zones = {z.get("id"): z for z in plot.get("zones", [])}
    probs = []
    for p in data["paths"]:
        z = zones.get(p["id"])
        if not z or z.get("paint") != p["paint"] or z.get("width") != p["width"] or z.get("line") != p["line"]:
            probs.append(f"ground: plot.toml has no zone {p['id']} matching garden.toml's path")
    return probs


# ---------------------------------------------------------------- the glass roof

def glass_roof(data: dict, layout: dict) -> tuple[list[dict], list[str]]:
    """The greenhouse's glass pitched roof: kit_geom.attic_roof's layout over the rect with the glass pieces (eave,
    2 x 2 bays, ridge; glass has no verges, corners or ridge ends) pivoted on the glass walls' top, and with gables
    the glass gables: per 2 m slope row a triangle over bands as tall as one triangle's rise (house_layout's
    pitched_roof rule)."""
    spec, kit = layout["spec"], layout["pieces"]
    rf = data["roof"]
    x0, y0, w, d = (float(v) for v in rf["rect"])
    h0 = float(spec["grid"]["glass_wall_h_m"])
    r = float(spec["grid"]["gable_rise_per_m"])
    if int(d) % 4:
        return [], [f"roof: the glass roof's depth {d:g} m must be a multiple of 4 (2 m rows up each slope)"]
    names = {"roof_pitched_eave_2m": "glass_roof_eave_2m", "roof_pitched_2x2": "glass_roof_2x2",
             "roof_pitched_ridge_2m": "glass_roof_ridge_2m"}
    out = [{"id": names[pid], "x": x0 + off[0], "y": y0 + off[2], "h": h0 + off[1], "turn": int(round(deg))}
           for pid, deg, off in hl.kit_geom().attic_roof(spec, int(w), int(d)) if pid in names]
    for q in out:  # the bay whose far end meets a gable closes it with its second rafter (kit "_end" pieces)
        if q["id"] in BAYS and any(abs(bay_far_x(q) - gx) <= RAFTER_M for gx in (x0, x0 + w)):
            q["id"] += "_end"
    if rf.get("gables"):
        rows = list(range(0, int(d / 2), 2))
        for gx, turn in ((x0, hl.turn_for((-1, 0))), (x0 + w, hl.turn_for((1, 0)))):
            ax, _ = hl.axes(turn)
            for s in rows:
                for lo, south in ((s, True), (d - s - 2, False)):
                    up = south == (ax[1] > 0)
                    start = lo if ax[1] > 0 else lo + 2
                    for k in range(s // 2):
                        out.append({"id": "glass_gable_band_2m", "x": gx, "y": y0 + start, "h": h0 + k * 2 * r,
                                    "turn": turn})
                    out.append({"id": f"glass_gable_tri_2m_{'up' if up else 'down'}", "x": gx, "y": y0 + start,
                                "h": h0 + r * s, "turn": turn})
    missing = sorted({p["id"] for p in out} - set(kit))
    return out, [f"roof: no kit piece {', '.join(missing)}"] if missing else []


BAYS = ("glass_roof_2x2", "glass_roof_eave_2m")  # the glass roof's bays; "<bay>_end" adds a rafter at local x 2
BAY_M = 2.0


def bay_far_x(p: dict) -> float:
    """The world x of a bay's local x 2 end (its pivot, local x 0, is at p["x"])."""
    return p["x"] + BAY_M * round(math.cos(math.radians(p["turn"])))


def gable_gaps(data: dict, placed: list[dict]) -> list[str]:
    """A bay's rafter is at its local x 0 (an "_end" bay has a second one at its local x 2): list each (gable, slope)
    with no bay's rafter within RAFTER_M of the gable's plane (a slit between the gable's top and the pane above it,
    open to a level line-of-sight ray)."""
    x0, y0, w, d = data["roof"]["rect"]
    ridge = y0 + d / 2
    gaps = []
    for gx in (x0, x0 + w):
        for slope, north in (("north", True), ("south", False)):
            ok = any(p["id"].removesuffix("_end") in BAYS and (p["y"] <= ridge) == north
                     and (abs(p["x"] - gx) <= RAFTER_M
                          or (p["id"].endswith("_end") and abs(bay_far_x(p) - gx) <= RAFTER_M)) for p in placed)
            if not ok:
                gaps.append(f"roof: the gable at x {gx:g} has no rafter on the {slope} slope")
    return gaps


# ---------------------------------------------------------------- output

def plan_png(data: dict, plot: dict, placed: list[dict], path: Path, ppm: int = 20, margin: float = 4.0) -> Path:
    """Top-down: lawn, paths (gravel / worn), the greenhouse (pale), blockers (grey), trees (dark green canopy, brown
    trunk), bushes (green), flower beds (pink), props (magenta, lights orange, flat lilac), the herb route (white);
    outside the garden dimmed."""
    gx, gy, gw, gd = data["rect"]
    x0, y0 = gx - margin - 4, gy - margin
    W, H = int((gw + 2 * margin + 4) * ppm), int((gd + 2 * margin + 10) * ppm)
    paints = {k: tuple(int(c * 255) for c in house_sky.hex_rgb(v["hex"])) for k, v in plot["paints"].items()}
    px = [[paints["grass"]] * W for _ in range(H)]

    def fill(lo_x, lo_y, hi_x, hi_y, hit, colour):
        for j in range(max(0, int((lo_y - y0) * ppm)), min(H, int((hi_y - y0) * ppm) + 1)):
            for i in range(max(0, int((lo_x - x0) * ppm)), min(W, int((hi_x - x0) * ppm) + 1)):
                x, y = x0 + (i + 0.5) / ppm, y0 + (j + 0.5) / ppm
                if hit(x, y):
                    px[j][i] = colour

    def poly(line, half, colour):
        for a, b in zip(line, line[1:]):
            fill(min(a[0], b[0]) - half, min(a[1], b[1]) - half, max(a[0], b[0]) + half, max(a[1], b[1]) + half,
                 lambda x, y: seg_dist(x, y, a, b) <= half, colour)

    def box(rect, colour):
        fill(rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3], lambda x, y: ho.in_rect(rect, x, y), colour)

    def disc(at, rad, colour):
        fill(at[0] - rad, at[1] - rad, at[0] + rad, at[1] + rad,
             lambda x, y: math.hypot(x - at[0], y - at[1]) <= rad, colour)
    for p in data["paths"]:
        poly(p["line"], p["width"] / 2, paints[p["paint"]])
    for b in blockers(data, plot):
        box(b["rect"], (120, 120, 120))
    box(data["greenhouse"], (200, 215, 220))
    poly(data["route"]["points"], 0.08, (255, 255, 255))
    for q in placed:
        if q["id"] == "garden_tree":
            disc(q["at"], 1.5 * q["scale"], (30, 70, 40))
            disc(q["at"], q["radius"] / 3, (90, 60, 40))
        else:
            disc(q["at"], q["radius"], (60, 120, 60) if q["id"] == "bush" else (220, 90, 150))
    for p in prop_rects(data):
        box(p["rect"], (255, 160, 40) if p["light"] else (230, 40, 200) if p["solid"] else (180, 160, 200))
    rows = []
    for j, line in enumerate(px):
        y = y0 + (j + 0.5) / ppm
        row = bytearray()
        for i, c in enumerate(line):
            if not ho.in_rect(data["rect"], x0 + (i + 0.5) / ppm, y):
                c = tuple(int(v * 0.6) for v in c)
            row += bytes(c)
        rows.append(bytes(row))
    return house_sky.write_png(path, W, H, rows)


def build(data: dict, plot: dict, layout: dict) -> dict:
    placed, probs = scatter(data, plot)
    probs += check(data, plot, placed) + ground_zone_problems(data, plot)
    roof, roof_probs = glass_roof(data, layout)
    probs += roof_probs
    counts: dict[str, int] = {}
    for q in placed:
        counts[q["id"]] = counts.get(q["id"], 0) + 1
    return {"seed": data["seed"], "scatter": placed, "props": prop_rects(data), "roof": roof,
            "roof_gaps": gable_gaps(data, roof), "route": route(data), "counts": counts, "problems": probs}


def write(data: dict, plot: dict, layout: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rep = build(data, plot, layout)
    (out / "garden.json").write_text(json.dumps(rep, indent=1), encoding="utf-8", newline="\n")
    plan_png(data, plot, rep["scatter"], out / "plan.png")
    return rep
