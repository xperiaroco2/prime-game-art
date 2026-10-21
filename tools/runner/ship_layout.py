"""The empty ship's layout (art #263, docs/ship.md): layouts/ship/ship.toml (the numbers) with the interior and exterior
lanes' piece lists and placements, and the plain-Python check of the rules `ship --check` holds: the footprint, the
corridor width, the station spots inside their rooms with walking room, every room and placed piece inside the hull,
the head room, and one entrance. Plan coordinates: x east, y south, h up (metres); Godot (x, h, y)."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path
from typing import Any

from . import common

SHIP = common.ROOT / "layouts" / "ship" / "ship.toml"
LANES = ("interior", "exterior")
TOL = 1e-6


def load(path: Path = SHIP) -> dict[str, Any]:
    """ship.toml with "pieces" (each with its "lane") and "place" ([piece, [x, y, h], yaw]) from both lane files."""
    with path.open("rb") as f:
        layout = tomllib.load(f)
    layout["pieces"], layout["place"] = [], []
    for lane in LANES:
        with (common.ROOT / layout[lane]).open("rb") as f:
            data = tomllib.load(f)
        for p in data.get("pieces", []):
            layout["pieces"].append({"lane": lane, "args": {}, "collide": False, "outside": False, **p})
        layout["place"] += [[p[0], list(p[1]), float(p[2])] for p in data.get("place", [])]
    return layout


def rooms(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in layout["rooms"]}


def outline(layout: dict[str, Any]) -> list[tuple[float, float]]:
    """The hull's footprint polygon: the core rows short of the first plate row, then the plate rows; lead edges from
    west to east, trail edges back (both halves)."""
    hull = layout["hull"]
    first_plate = min(r[0] for r in hull["plate"])
    rows = sorted([r for r in hull["core"] if r[0] < first_plate] + hull["plate"], key=lambda r: r[0])
    half = [(r[0], r[1], r[2]) for r in rows]
    full = [(-x, a, b) for x, a, b in reversed(half) if x > 0] + half
    return [(x, a) for x, a, _ in full] + [(x, b) for x, _, b in reversed(full)]


def inside(poly: list[tuple[float, float]], pt: tuple[float, float]) -> bool:
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def room_margin(room: dict[str, Any], pt: tuple[float, float]) -> float:
    """How far pt lies inside the room's floor (negative: outside)."""
    if room["shape"] == "circle":
        return room["radius"] - math.dist(pt, room["centre"])
    return min(pt[0] - room["x"][0], room["x"][1] - pt[0], pt[1] - room["y"][0], room["y"][1] - pt[1])


def boundary(room: dict[str, Any], wall: float, n: int = 48) -> list[tuple[float, float]]:
    """Points on the room's outer wall face."""
    if room["shape"] == "circle":
        r = room["radius"] + wall
        cx, cy = room["centre"]
        return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    (x0, x1), (y0, y1) = room["x"], room["y"]
    pts = []
    for i in range(n // 4):
        t = i / (n // 4)
        pts += [(x0 + (x1 - x0) * t, y0 - wall), (x0 + (x1 - x0) * t, y1 + wall)]
        pts += [(x0 - wall, y0 + (y1 - y0) * t), (x1 + wall, y0 + (y1 - y0) * t)]
    return pts


def extent(layout: dict[str, Any]) -> tuple[float, float]:
    """(width east-west, length north-south): the hull, the tip shells, the ramp's foot and the nozzles' tips."""
    poly = outline(layout)
    pods = [r for r in layout["rooms"] if r["shape"] == "circle" and r.get("window")]
    xs = [p[0] for p in poly] + [r["centre"][0] + s * layout["hull"]["pod_radius_m"] for r in pods for s in (-1, 1)]
    ys = [p[1] for p in poly] + [layout["ramp"]["foot"][1], layout["hull"]["stern_y"]]
    return max(xs) - min(xs), max(ys) - min(ys)


def _touch(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Two linked rooms share floor: some point of one's edge lies inside the other (a rect's short end in a circle)."""
    for room, other in ((a, b), (b, a)):
        if room["shape"] != "rect":
            continue
        (x0, x1), (y0, y1) = room["x"], room["y"]
        for p in ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)):
            if room_margin(other, p) > 0.1:
                return True
    return False


def check(layout: dict[str, Any]) -> list[str]:
    problems = []
    size = layout["size"]
    width, length = extent(layout)
    for name, got, want in (("width", width, size["width_m"]), ("length", length, size["length_m"])):
        if abs(got - want) > size["tolerance_m"]:
            problems.append(f"footprint {name} {got:.2f} m, wants {want:g} +- {size['tolerance_m']:g}")
    by_id = rooms(layout)
    for r in layout["rooms"]:
        if r["id"].startswith("corridor"):
            w = r["y"][1] - r["y"][0]
            if abs(w - 2.5) > 0.1:
                problems.append(f"{r['id']}: {w:.2f} m wide, wants about 2.5")
            if r["x"][1] - r["x"][0] < 4.0:
                problems.append(f"{r['id']}: shorter than 4 m")
    # the corridors run across the whole width: tip room to tip room
    xs = [r["centre"][0] + s * r["radius"] for r in layout["rooms"] if r.get("window") for s in (-1, 1)]
    if xs and max(xs) - min(xs) < size["width_m"] - 1.5:
        problems.append(f"tip rooms span {max(xs) - min(xs):.2f} m, not the whole width")
    player = layout["player"]
    need = player["capsule_height_m"] + player["head_margin_m"]
    for r in layout["rooms"]:
        if r["clear_h"] < need:
            problems.append(f"{r['id']}: clear height {r['clear_h']:g} m < {need:g} m (capsule and margin)")
        if r["shape"] == "circle" and min(r["radius"], 99) * 2 < 2 * player["capsule_radius_m"] + 2.0:
            problems.append(f"{r['id']}: too small to walk round in")
    # one entrance: exactly one room with an exit, the ramp's hinge on its north edge; every room reachable
    exits = [r for r in layout["rooms"] if r.get("exit")]
    if len(exits) != 1:
        problems.append(f"{len(exits)} rooms with an exit, wants exactly one (the mouth ramp)")
    else:
        m, ramp = exits[0], layout["ramp"]
        if abs(ramp["hinge"][1] - m["y"][0]) > 0.01 or not m["x"][0] <= ramp["hinge"][0] <= m["x"][1]:
            problems.append("the ramp's hinge is not on the mouth room's north edge")
        if ramp["foot"][1] >= ramp["hinge"][1] or abs(ramp["hinge"][0]) > 0.01:
            problems.append("the ramp does not run north from the ship's centre line")
        if abs(m["x"][1] - m["x"][0] - ramp["width_m"]) > 0.01:
            problems.append("the ramp is not as wide as the mouth")
        drop = layout["deck"]["floor_h"] - layout["deck"]["ground_h"]
        slope = math.degrees(math.atan2(drop, ramp["hinge"][1] - ramp["foot"][1]))
        if slope > 30.0:
            problems.append(f"the ramp's slope {slope:.1f} deg is over 30")
    for r in layout["rooms"]:
        if r.get("window", {}).get("exit"):
            problems.append(f"{r['id']}: its window is glass, not an exit")
    seen, todo = set(), ["hall"]
    while todo:
        rid = todo.pop()
        if rid in seen or rid not in by_id:
            continue
        seen.add(rid)
        for other in by_id[rid].get("links", []):
            if other not in by_id:
                problems.append(f"{rid}: links unknown room {other}")
            elif not _touch(by_id[rid], by_id[other]):
                problems.append(f"{rid} and {other} are linked but do not meet")
            todo.append(other)
    if seen != set(by_id):
        problems.append(f"rooms not reachable from the hall: {', '.join(sorted(set(by_id) - seen))}")
    # stations: inside their room with their footprint, at a wall where asked, walking room left
    st = layout["stations"]
    for s in st["spot"]:
        room = by_id.get(s["room"])
        if room is None:
            problems.append(f"station {s['id']}: unknown room {s['room']}")
            continue
        margin = room_margin(room, tuple(s["at"]))
        least = st["wall_depth_m"] / 2 if s.get("at_wall") else st["radius_m"]  # a wall unit stands against its wall
        if margin < least - TOL:
            problems.append(f"station {s['id']}: {margin:.2f} m inside {room['id']}, wants >= {least:g}")
        if room["shape"] == "rect":
            gaps = (s["at"][1] - room["y"][0], room["y"][1] - s["at"][1])
            if s.get("at_wall") and min(gaps) > st["wall_reach_m"]:
                problems.append(f"station {s['id']}: {min(gaps):.2f} m from a wall, wants <= {st['wall_reach_m']:g}")
            free = max(gaps) - st["radius_m"]
            if free < st["min_free_width_m"]:
                problems.append(f"station {s['id']}: {free:.2f} m free beside it, wants >= {st['min_free_width_m']:g}")
        elif room["radius"] - st["radius_m"] * 2 < st["min_free_width_m"]:
            problems.append(f"station {s['id']}: no walking room round it in {room['id']}")
    # inside the hull: every room's outer wall and every placed piece's origin (unless the piece may stand outside)
    poly = outline(layout)
    wall = layout["deck"]["wall_m"]
    for r in layout["rooms"]:
        pts = boundary(r, wall)
        if r.get("exit"):  # the exit's own open edge meets the ramp, outside the hull by design
            pts = [p for p in pts if p[1] > r["y"][0] + 0.05]
        out = [p for p in pts if not inside(poly, p)]
        if out:
            problems.append(f"{r['id']}: {len(out)} wall points outside the hull, e.g. ({out[0][0]:.2f}, {out[0][1]:.2f})")
    pieces = {p["id"]: p for p in layout["pieces"]}
    ids = [p["id"] for p in layout["pieces"]]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"piece {dup} defined twice")
    for pid, at, _yaw in layout["place"]:
        piece = pieces.get(pid)
        if piece is None:
            problems.append(f"placement of unknown piece {pid}")
        elif not piece["outside"] and not inside(poly, (at[0], at[1])):
            problems.append(f"{pid} at ({at[0]:g}, {at[1]:g}) stands outside the hull")
    unplaced = sorted(set(pieces) - {p[0] for p in layout["place"]})
    if unplaced:
        problems.append(f"pieces never placed: {', '.join(unplaced)}")
    return problems


def ascii_plan(layout: dict[str, Any], cell: float = 0.5) -> str:
    """A text plan, south at the top as in plan-3.jpg: '#' hull, '.' room floor, 'o' tip-room window side, '=' ramp,
    letters the station spots (C console, V vent, S socket, P panel, R renewer)."""
    poly = outline(layout)
    by_id = rooms(layout)
    marks = {"console": "C", "vent_w": "V", "vent_e": "V", "socket_w": "S", "socket_e": "S", "panel": "P", "renewer": "R"}
    ramp = layout["ramp"]
    lines = []
    y = 7.5
    while y >= -7.5:
        row = []
        x = 13.5
        while x >= -13.5:  # south up and seen from above: east on the left
            ch = " "
            if inside(poly, (x, y)) or any(r.get("window") and room_margin(r, (x, y)) > -0.45 for r in by_id.values()):
                ch = "#"
            if any(room_margin(r, (x, y)) > 0 for r in by_id.values()):
                ch = "."
            if abs(x) < ramp["width_m"] / 2 and ramp["foot"][1] <= y < ramp["hinge"][1]:
                ch = "="
            for s in layout["stations"]["spot"]:
                if abs(s["at"][0] - x) < cell / 2 + TOL and abs(s["at"][1] - y) < cell / 2 + TOL:
                    ch = marks.get(s["id"], "*")
            row.append(ch)
            x -= cell
        lines.append("".join(row).rstrip())
        y -= cell
    head = (f"ship plan v{layout['version']}: {cell:g} m cells, south at the top and east on the left (as plan-3.jpg, "
            "seen from above); # hull, . floor, = ramp, C console, V vent, S socket, P panel, R renewer")
    return head + "\n" + "\n".join(lines) + "\n"
