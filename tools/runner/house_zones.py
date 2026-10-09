"""The House map's chill zone and photo gazebo as data (art #81b, map #73): layouts/house/outdoor/zones/*.toml placed and
checked. Plain Python, standard library only: the zone files list the props (their sizes from props/tasks.toml and
props/zones.toml), the kit's gazebo and placeholders for pieces another package owns; this module resolves each
placement (plan point, height, yaw), lists the kit's gazebo pieces and the hooks of its string lights, and checks the
plan's acceptance: every piece inside the zone, the stations at the design doc's points, the photo zone's 4 m opening,
the light fixtures' counts (inventory.md section 8), no two pieces on the same ground and a free walk from the
approach to every station.

Plan metres: x east, y south; Godot puts a plan point (x, y) at (x, height, y). A yaw turns a prop's front (+Z) about
+Y: its front then points along (sin yaw, cos yaw) in the plan (yaw 90 east, 180 north, -90 west).
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path
from typing import Any

from . import common

ZONES = common.ROOT / "layouts" / "house" / "outdoor" / "zones"
SPECS = {"tasks": common.ROOT / "props" / "tasks.toml", "zones": common.ROOT / "props" / "zones.toml"}
KIT = common.ROOT / "kits" / "house.json"
OPENING_M = 4.0  # the photo zone's opening (inventory.md section 4)
STATIONS = {"Grill": (8.0, 50.0), "Speaker": (12.0, 55.0), "PoseScreen": (9.0, 11.0)}  # inventory.md section 7
FIXTURES = {"photo_zone": {"string_lights": 4, "lantern": 6}, "chill_zone": {"string_lights": 3, "lantern": 6}}
PLAYER_R = 0.35  # the walk check's player radius
GRID = 0.1
RAIL_T = 0.1


def _props() -> dict[str, dict]:
    out = {}
    for src, path in SPECS.items():
        with path.open("rb") as f:
            for p in tomllib.load(f)["props"]:
                out[p["id"]] = {**p, "src": src}
    return out


def front(yaw: float) -> tuple[float, float]:
    a = math.radians(yaw)
    return math.sin(a), math.cos(a)


def turn(lx: float, lz: float, yaw: float) -> tuple[float, float]:
    """A local (x, z) offset turned by yaw about +Y, as a plan (dx, dy) (kit_geom.rot_y)."""
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    return lx * c + lz * s, -lx * s + lz * c


def load(path: Path) -> dict[str, Any]:
    with Path(path).open("rb") as f:
        z = tomllib.load(f)
    props = _props()
    gz = z.get("gazebo")
    items = []
    for i, it in enumerate(z.get("items", [])):
        it = dict(it, index=i)
        spec = props.get(it["id"])
        if "size" in it:
            it["w"], it["d"], it["h"] = (float(v) for v in it["size"])
        elif spec and spec["src"] == it["src"]:
            it["w"], it["d"], it["h"] = float(spec["w"]), float(spec["d"]), float(spec["h"])
            it["type"] = spec["type"]
            it["spec"] = spec
        if "gazebo_edge" in it and gz:
            c0, c1 = gazebo_corner(gz, it["gazebo_edge"]), gazebo_corner(gz, it["gazebo_edge"] + 1)
            it["at"] = [(c0[0] + c1[0]) / 2, (c0[1] + c1[1]) / 2]
            it["yaw"] = math.degrees(math.atan2(-(c1[1] - c0[1]), c1[0] - c0[0]))
            it["y"] = float(it["hook_h"])
        elif "face" in it:
            dx, dy = it["face"][0] - it["at"][0], it["face"][1] - it["at"][1]
            it["yaw"] = math.degrees(math.atan2(dx, dy))
        it.setdefault("yaw", 0.0)
        it.setdefault("y", 0.0)
        items.append(it)
    z["items"] = items
    z["name"] = Path(path).stem
    return z


def load_all() -> list[dict[str, Any]]:
    return [load(p) for p in sorted(ZONES.glob("*.toml"))]


# --- the gazebo -----------------------------------------------------------------------------------------------------
def gazebo_corner(gz: dict, k: int, radius: float | None = None) -> tuple[float, float]:
    """Corner k of the gazebo's hexagon in the plan (kit_geom.gazebo_corner turned by the gazebo's yaw)."""
    r = float(radius if radius is not None else gz["post_radius"])
    dx, dy = turn(r, 0.0, 60.0 * k + float(gz["yaw"]))
    return float(gz["centre"][0]) + dx, float(gz["centre"][1]) + dy


def gazebo_pieces(gz: dict) -> list[dict]:
    """The kit's gazebo (kit_geom.gazebo: six deck sectors, sector 0 open, six roof sectors) and the finial."""
    out = [{"piece": "gazebo_sector_open" if k == 0 else "gazebo_sector", "yaw": 60.0 * k + gz["yaw"]} for k in range(6)]
    out += [{"piece": "gazebo_roof_sector", "yaw": 60.0 * k + gz["yaw"]} for k in range(6)]
    out.append({"piece": "gazebo_finial", "yaw": float(gz["yaw"])})
    for o in out:
        o["at"] = [float(gz["centre"][0]), float(gz["centre"][1])]
        o["y"] = 0.0
    return out


def gazebo_opening(gz: dict) -> float:
    """The clear width of the gazebo's open sector between its two posts."""
    c0, c1 = gazebo_corner(gz, 0), gazebo_corner(gz, 1)
    return math.dist(c0, c1) - float(gz["post"])


# --- footprints -------------------------------------------------------------------------------------------------------
def rect(cx, cy, w, d, yaw) -> list[tuple[float, float]]:
    """The four plan corners of a w (local x) by d (local z) footprint at (cx, cy) turned by yaw."""
    out = []
    for lx, lz in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
        dx, dy = turn(lx, lz, yaw)
        out.append((cx + dx, cy + dy))
    return out


def obstacles(it: dict) -> list[list[tuple[float, float]]]:
    """What a placed piece blocks on the ground: its footprint; a pole set only its two poles; a hung strand nothing."""
    if "w" not in it or it.get("type") == "string_lights_hang":
        return []
    x, y = it["at"]
    if it.get("type") == "string_lights_poles":
        half = float(it["spec"]["span"]) / 2
        out = []
        for s in (-1, 1):
            dx, dy = turn(s * half, 0.0, it["yaw"])
            out.append(rect(x + dx, y + dy, it["d"], it["d"], it["yaw"]))
        return out
    return [rect(x, y, it["w"], it["d"], it["yaw"])]


def zone_walls(z: dict) -> list[list[tuple[float, float]]]:
    """The photo zone's railing round its rectangle, the opening left out, and the gazebo's posts and closed rails."""
    out = []
    x0, y0, w, d = (float(v) for v in z["rect"])
    if "railing" in z:
        op = z["opening"]
        sides = {"north": ((x0, y0), (x0 + w, y0)), "south": ((x0, y0 + d), (x0 + w, y0 + d)),
                 "west": ((x0, y0), (x0, y0 + d)), "east": ((x0 + w, y0), (x0 + w, y0 + d))}
        for name, (a, b) in sides.items():
            runs = [(a, b)]
            if name == op["side"]:
                along = 1 if a[0] == b[0] else 0
                p, q = list(a), list(b)
                p[along], q[along] = op["from"], op["to"]
                runs = [(a, tuple(p)), (tuple(q), b)]
            for s, e in runs:
                lo = (min(s[0], e[0]) - RAIL_T / 2, min(s[1], e[1]) - RAIL_T / 2)
                hi = (max(s[0], e[0]) + RAIL_T / 2, max(s[1], e[1]) + RAIL_T / 2)
                if max(hi[0] - lo[0], hi[1] - lo[1]) > RAIL_T + 1e-6:
                    out.append([(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])])
    gz = z.get("gazebo")
    if gz:
        ps = float(gz["post"])
        for k in range(6):
            cx, cy = gazebo_corner(gz, k)
            out.append(rect(cx, cy, ps, ps, 60.0 * k + gz["yaw"]))
            if k:  # sector 0 is the open one
                c0, c1 = gazebo_corner(gz, k), gazebo_corner(gz, k + 1)
                yaw = math.degrees(math.atan2(-(c1[1] - c0[1]), c1[0] - c0[0]))
                out.append(rect((c0[0] + c1[0]) / 2, (c0[1] + c1[1]) / 2, math.dist(c0, c1), 0.08, yaw))
    return out


def _axes(poly):
    for i in range(len(poly)):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
        yield -(by - ay), bx - ax


def overlap(a, b, margin: float = 0.0) -> bool:
    """Two convex plan polygons overlap by more than margin (separating axes)."""
    for nx, ny in list(_axes(a)) + list(_axes(b)):
        n = math.hypot(nx, ny) or 1.0
        pa = [(x * nx + y * ny) / n for x, y in a]
        pb = [(x * nx + y * ny) / n for x, y in b]
        if min(pa) >= max(pb) - margin or min(pb) >= max(pa) - margin:
            return False
    return True


def _near(px, py, poly, r) -> bool:
    """The point is inside the polygon or within r of it."""
    inside = True
    for i in range(len(poly)):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
        if (bx - ax) * (py - ay) - (by - ay) * (px - ax) < 0:
            inside = False
            break
    if inside:
        return True
    for i in range(len(poly)):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
        L = (bx - ax) ** 2 + (by - ay) ** 2 or 1e-9
        t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L))
        if math.hypot(px - ax - t * (bx - ax), py - ay - t * (by - ay)) < r:
            return True
    return False


def _ccw(poly):
    area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))
    return poly if area > 0 else list(reversed(poly))


def walk(z: dict) -> dict[str, bool]:
    """Whether a player (radius PLAYER_R) can walk from the approach to within reach of every station: a grid search
    over the zone and a 2 m margin round it, every piece's and wall's ground footprint blocking."""
    x0, y0, w, d = (float(v) for v in z["rect"])
    blocks = [_ccw(p) for it in z["items"] for p in obstacles(it)] + [_ccw(p) for p in zone_walls(z)]
    nx, ny = int((w + 4) / GRID), int((d + 4) / GRID)

    def cell(i, j):
        return x0 - 2 + (i + 0.5) * GRID, y0 - 2 + (j + 0.5) * GRID

    boxes = [(min(q[0] for q in b) - PLAYER_R, min(q[1] for q in b) - PLAYER_R,
              max(q[0] for q in b) + PLAYER_R, max(q[1] for q in b) + PLAYER_R) for b in blocks]

    def blocked(px, py):
        return any(bx[0] <= px <= bx[2] and bx[1] <= py <= bx[3] and _near(px, py, b, PLAYER_R)
                   for b, bx in zip(blocks, boxes))

    free = [[not blocked(*cell(i, j)) for j in range(ny)] for i in range(nx)]
    view = z["views"][0]["eye"]
    si = min(max(int((view[0] - x0 + 2) / GRID), 0), nx - 1)
    sj = min(max(int((view[1] - y0 + 2) / GRID), 0), ny - 1)
    if not free[si][sj]:  # the approach eye may be outside the margin: start from the margin's nearest free cell
        si, sj = min(((i, j) for i in range(nx) for j in range(ny) if free[i][j] and (i in (0, nx - 1) or j in (0, ny - 1))),
                     key=lambda c: math.dist(cell(*c), view[:2]))
    seen = {(si, sj)}
    todo = [(si, sj)]
    while todo:
        i, j = todo.pop()
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < nx and 0 <= b < ny and free[a][b] and (a, b) not in seen:
                seen.add((a, b))
                todo.append((a, b))
    out = {}
    for it in z["items"]:
        if it.get("station"):
            reach = max(it["w"], it["d"]) / 2 + 0.8
            out[it["station"]] = any(math.dist(cell(i, j), it["at"]) <= reach for i, j in seen)
    return out


# --- the checks -------------------------------------------------------------------------------------------------------
def check(z: dict) -> list[str]:
    problems = []
    name = z["name"]
    x0, y0, w, d = (float(v) for v in z["rect"])
    for it in z["items"]:
        tag = f"{name}: {it['id']} #{it['index']}"
        if "w" not in it:
            problems.append(f"{tag}: no size (not in props/{it['src']}.toml and no size given)")
            continue
        for poly in obstacles(it) or [rect(*it["at"], it["w"], it["d"], it["yaw"])]:
            for px, py in poly:
                if not (x0 - 1e-6 <= px <= x0 + w + 1e-6 and y0 - 1e-6 <= py <= y0 + d + 1e-6):
                    problems.append(f"{tag}: ({px:.2f}, {py:.2f}) is outside the zone {z['rect']}")
                    break
        if it.get("station"):
            want = STATIONS.get(it["station"])
            if want is None or math.dist(want, it["at"]) > 0.01:
                problems.append(f"{tag}: station {it['station']} at {it['at']}, the design doc says {want}")
    placed = [(it, p) for it in z["items"] for p in obstacles(it)]
    walls = zone_walls(z)
    for a in range(len(placed)):
        for b in range(a + 1, len(placed)):
            if placed[a][0]["index"] != placed[b][0]["index"] and overlap(placed[a][1], placed[b][1], 0.01):
                problems.append(f"{name}: {placed[a][0]['id']} #{placed[a][0]['index']} and {placed[b][0]['id']} "
                                f"#{placed[b][0]['index']} overlap")
        for wall in walls:
            if overlap(placed[a][1], wall, 0.01):
                problems.append(f"{name}: {placed[a][0]['id']} #{placed[a][0]['index']} stands in a railing or post")
                break
    if "opening" in z:
        op = z["opening"]
        if abs(float(op["to"]) - float(op["from"]) - OPENING_M) > 0.01:
            problems.append(f"{name}: the opening is {op['to'] - op['from']} m, the plan says {OPENING_M} m")
    counts = {"string_lights": 0, "lantern": 0}
    for it in z["items"]:
        if it["id"].startswith("string_lights"):
            counts["string_lights"] += 1
        elif it["id"] == "lantern":
            counts["lantern"] += 1
    if counts != FIXTURES.get(z["zone"], counts):
        problems.append(f"{name}: fixtures {counts}, inventory.md section 8 says {FIXTURES[z['zone']]}")
    for station, ok in walk(z).items():
        if not ok:
            problems.append(f"{name}: no free walk from the approach to the station {station}")
    return problems


def placements(z: dict) -> list[dict]:
    """Every piece as the assembly places it: id, source, Godot position (x, height, plan y), yaw, station."""
    out = []
    for it in z["items"]:
        out.append({"id": it["id"], "src": it["src"], "pos": [round(it["at"][0], 4), round(it["y"], 4),
                                                              round(it["at"][1], 4)],
                    "yaw": round(it["yaw"], 3), "station": it.get("station", ""),
                    "size": [it.get("w"), it.get("d"), it.get("h")]})
    if z.get("gazebo"):
        for g in gazebo_pieces(z["gazebo"]):
            out.append({"id": g["piece"], "src": "kit", "pos": [g["at"][0], g["y"], g["at"][1]],
                        "yaw": round(g["yaw"], 3), "station": "", "size": None})
    return out
