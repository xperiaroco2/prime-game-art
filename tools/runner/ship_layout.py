"""The empty ship's layout (art #263, docs/ship.md): layouts/ship/ship.toml (the numbers) with the interior and exterior
lanes' piece lists and placements, and the plain-Python check of the rules `ship --check` holds: the footprint, the
corridor width, the tip rooms' outer wall, the station spots (inside their rooms, the wall spots' plain flat panels
and the free pass behind a player standing at each), every room and placed piece inside the hull, the head room, and
one entrance. Rooms are circles, axis-aligned rects or "strip"s (a straight corridor at any angle: `axis` [from, to],
`along` [u0, u1] its floor's ends measured from `from`, `width`). The least skin round every room comes from the
hull's own shape (tools/blender/ship_hull_shape.py, plain Python; [hull] shape names its variant).
Plan coordinates: x east, y south, h up (metres); Godot (x, h, y)."""

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
        # inside-1: the tip windows' shutters closed (`place` holds them open): the rows `pose(layout, "closed")` swaps in
        layout.setdefault("shutter_closed", [])
        layout["shutter_closed"] += [[p[0], list(p[1]), float(p[2])] for p in data.get("shutter_closed", [])]
    return layout


def pose(layout: dict[str, Any], shutters: str) -> dict[str, Any]:
    """The layout with the tip windows' shutters "open" (as loaded) or "closed": the closed rows replace every
    placement of a piece they place (the shutter panels)."""
    if shutters == "open":
        return layout
    ids = {p[0] for p in layout["shutter_closed"]}
    return {**layout, "place": [p for p in layout["place"] if p[0] not in ids] + layout["shutter_closed"]}


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


def strip_frame(room: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float], float, float, float]:
    """A strip room's (origin, unit along its axis, u0, u1, half width)."""
    (ax, ay), (bx, by) = room["axis"]
    n = math.hypot(bx - ax, by - ay)
    return (ax, ay), ((bx - ax) / n, (by - ay) / n), room["along"][0], room["along"][1], room["width"] / 2


def strip_point(room: dict[str, Any], u: float, v: float) -> tuple[float, float]:
    """The plan point u along a strip room's axis and v across it (+v to the axis's left in plan, x toward y)."""
    (ox, oy), (ux, uy), *_ = strip_frame(room)
    return ox + u * ux - v * uy, oy + u * uy + v * ux


def room_margin(room: dict[str, Any], pt: tuple[float, float]) -> float:
    """How far pt lies inside the room's floor (negative: outside)."""
    if room["shape"] == "circle":
        return room["radius"] - math.dist(pt, room["centre"])
    if room["shape"] == "strip":
        (ox, oy), (ux, uy), u0, u1, half = strip_frame(room)
        dx, dy = pt[0] - ox, pt[1] - oy
        u, v = dx * ux + dy * uy, -dx * uy + dy * ux
        return min(u - u0, u1 - u, half - abs(v))
    return min(pt[0] - room["x"][0], room["x"][1] - pt[0], pt[1] - room["y"][0], room["y"][1] - pt[1])


def boundary(room: dict[str, Any], wall: float, n: int = 48) -> list[tuple[float, float]]:
    """Points on the room's outer wall face."""
    if room["shape"] == "circle":
        r = room["radius"] + wall
        cx, cy = room["centre"]
        return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    if room["shape"] == "strip":
        _o, _u, u0, u1, half = strip_frame(room)
        pts = []
        for i in range(n // 4):
            s = i / (n // 4)
            u = u0 + (u1 - u0) * s
            pts += [strip_point(room, u, -half - wall), strip_point(room, u, half + wall)]
            v = -half + 2 * half * s
            pts += [strip_point(room, u0 - wall, v), strip_point(room, u1 + wall, v)]
        return pts
    (x0, x1), (y0, y1) = room["x"], room["y"]
    pts = []
    for i in range(n // 4):
        t = i / (n // 4)
        pts += [(x0 + (x1 - x0) * t, y0 - wall), (x0 + (x1 - x0) * t, y1 + wall)]
        pts += [(x0 - wall, y0 + (y1 - y0) * t), (x1 + wall, y0 + (y1 - y0) * t)]
    return pts


def nozzle_tip_y(layout: dict[str, Any]) -> float:
    """The farthest south a nozzle pod reaches: its placement's y + its args length + hull.pod_tail_m (pods point +y)."""
    pods = {p["id"]: p for p in layout["pieces"] if p.get("builder") in ("nozzle_pod", "pod_ring")}
    tips = [pl[1][1] + float(pods[pl[0]]["args"]["length"]) + layout["hull"]["pod_tail_m"]
            for pl in layout["place"] if pl[0] in pods]
    return max(tips, default=layout["hull"]["trail_y"])


def lengths(layout: dict[str, Any]) -> dict[str, float]:
    """North-south lengths: "body" the hull from its lead edge to its trail (no ramp, no nozzle pods; the one checked
    against [size] length_m), "nozzles" the body with the pods sticking out behind, "overall" the ramp's foot to the
    nozzles' tips."""
    ys = [p[1] for p in outline(layout)]
    lead, trail, foot = min(ys), max(max(ys), layout["hull"]["trail_y"]), layout["ramp"]["foot"][1]
    tip = max(trail, nozzle_tip_y(layout))
    return {"body": trail - lead, "nozzles": tip - lead, "overall": tip - min(lead, foot)}


def extent(layout: dict[str, Any]) -> tuple[float, float]:
    """(width east-west, length north-south): the hull and the tip shells' blades; the length with the nozzle pods,
    without the ramp (lengths() has the body alone and the overall)."""
    poly = outline(layout)
    pods = [r for r in layout["rooms"] if r["id"].startswith("tip")]
    xs = [p[0] for p in poly] + [r["centre"][0] + s * layout["hull"]["pod_radius_m"] for r in pods for s in (-1, 1)]
    return max(xs) - min(xs), lengths(layout)["nozzles"]


TOUCH_M = 0.05  # how far a linked room's edge must reach into the other


def _touch(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Two linked rooms share floor: some point of one's edge lies at least TOUCH_M inside the other (a rect's short end
    in a circle). The rooms overlap by 0.1 m by design; the margin keeps the test off floating-point luck."""
    for room, other in ((a, b), (b, a)):
        if room["shape"] == "strip":
            _o, _u, u0, u1, half = strip_frame(room)
            ends = [strip_point(room, u0, 0.0), strip_point(room, u1, 0.0),
                    strip_point(room, (u0 + u1) / 2, -half), strip_point(room, (u0 + u1) / 2, half)]
        elif room["shape"] == "rect":
            (x0, x1), (y0, y1) = room["x"], room["y"]
            ends = [(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)]
        else:
            continue
        for p in ends:
            if room_margin(other, p) >= TOUCH_M:
                return True
    return False


def check(layout: dict[str, Any]) -> list[str]:
    problems = []
    size = layout["size"]
    width, length = extent(layout)
    for name, got, want in (("width", width, size["width_m"]), ("length", length, size["length_m"])):
        if name == "width" and want < got <= size.get("span_max_m", want):
            continue  # the blades past the tip rooms (manager update 2, art #263: the span up to about 27.5 m)
        if name == "length" and want < got <= size.get("length_max_m", want):
            continue  # the nozzle pods behind the hull (the manager, art #263: their reach is open, up to 15 m)
        if abs(got - want) > size["tolerance_m"]:
            what = "length (with the nozzles, no ramp)" if name == "length" else name
            problems.append(f"footprint {what} {got:.2f} m, wants {want:g} +- {size['tolerance_m']:g}")
    by_id = rooms(layout)
    for r in layout["rooms"]:
        if r["id"].startswith("corridor"):
            if r["shape"] == "strip":
                w, run = r["width"], r["along"][1] - r["along"][0]
            else:
                w, run = r["y"][1] - r["y"][0], r["x"][1] - r["x"][0]
            want = size["corridor_width_m"]
            if abs(w - want) > 0.1:
                problems.append(f"{r['id']}: {w:.2f} m wide, wants about {want:g}")
            if run < 2.5:
                problems.append(f"{r['id']}: shorter than 2.5 m")
    # the tip rooms' outer walls at x +-tip_outer_m (5a mirrored; rebuild A: their centres at y 4.0, no window)
    for r in layout["rooms"]:
        if r["id"].startswith("tip"):
            outer = abs(r["centre"][0]) + r["radius"]
            if abs(outer - size["tip_outer_m"]) > 0.05:
                problems.append(f"{r['id']}: outer wall at {outer:.2f} m, wants {size['tip_outer_m']:g}")
    player = layout["player"]
    need = player["capsule_height_m"] + player["head_margin_m"]
    for r in layout["rooms"]:
        if r["clear_h"] < need:
            problems.append(f"{r['id']}: clear height {r['clear_h']:g} m < {need:g} m (capsule and margin)")
        if r["shape"] == "circle" and r["radius"] * 2 < 2 * player["capsule_radius_m"] + 2.0:
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
    problems += check_spots(layout)
    problems += hull_skin(layout)
    # inside the hull: every room's outer wall and every placed piece's origin (unless the piece may stand outside)
    poly = outline(layout)
    wall = layout["deck"]["wall_m"]
    for r in layout["rooms"]:
        pts = boundary(r, wall)
        if r.get("exit") and r["shape"] == "rect":  # the exit's own open edge meets the ramp, outside the hull by design
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
    # a piece placed only in the closed pose (shutter_closed) counts as placed
    unplaced = sorted(set(pieces) - {p[0] for p in layout["place"] + layout.get("shutter_closed", [])})
    if unplaced:
        problems.append(f"pieces never placed: {', '.join(unplaced)}")
    return problems


def hull_skin(layout: dict[str, Any]) -> list[str]:
    """Every room's sampled outer surface (walls, roofs, slabs) inside the hull's shape with at least its SKIN of hull
    (ship_hull_shape.clearance for [hull] shape): the problems, none when it holds."""
    import sys
    from pathlib import Path as _Path
    blender = str(_Path(__file__).resolve().parents[1] / "blender")
    if blender not in sys.path:
        sys.path.insert(0, blender)
    import ship_hull_shape
    _least, bad = ship_hull_shape.clearance(layout["hull"]["shape"])
    return [f"hull {layout['hull']['shape']}: {b}" for b in bad]


def _unit(v: list[float]) -> tuple[float, float]:
    n = math.hypot(v[0], v[1])
    return v[0] / n, v[1] / n


def in_rooms(layout: dict[str, Any], pt: tuple[float, float]) -> float:
    """How far pt lies inside the rooms' floor (the largest margin over all rooms; < 0 outside every room)."""
    return max(room_margin(r, pt) for r in layout["rooms"])


def to_local(pt: tuple[float, float], at: list[float], yaw: float) -> tuple[float, float]:
    """A plan point in the frame of a piece placed at `at` turned by yaw (plan angle a -> a - yaw)."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    dx, dy = pt[0] - at[0], pt[1] - at[1]
    return c * dx - s * dy, s * dx + c * dy


def spot_stand(layout: dict[str, Any], s: dict[str, Any]) -> tuple[float, float]:
    """Where a player stands to use a wall spot (the capsule's centre in front of the unit)."""
    n = _unit(s["normal"])
    d = s.get("depth_m", layout["stations"]["depth_m"]) + layout["player"]["capsule_radius_m"]
    return s["at"][0] + n[0] * d, s["at"][1] + n[1] * d


def check_spots(layout: dict[str, Any]) -> list[str]:
    """The station spots (5a mirrored): a floor spot's footprint inside its room; a wall spot on its room's wall, its
    plain panel free of every piece with a `foot` (trunks, cable bays, arches, pilasters), the player's stand inside the
    room and pass_m of free floor behind it (the capsule's width inside the rooms, clear of every floor spot)."""
    problems: list[str] = []
    st, by_id = layout["stations"], rooms(layout)
    rad = layout["player"]["capsule_radius_m"]
    feet = {p["id"]: p["foot"] for p in layout["pieces"] if p.get("foot")}
    floors = [s for s in st["spot"] if not s.get("normal")]
    for s in st["spot"]:
        room = by_id.get(s["room"])
        if room is None:
            problems.append(f"station {s['id']}: unknown room {s['room']}")
            continue
        if not s.get("normal"):
            margin = room_margin(room, tuple(s["at"]))
            if margin < st["radius_m"] - TOL:
                problems.append(f"station {s['id']}: {margin:.2f} m inside {room['id']}, wants >= {st['radius_m']:g}")
            continue
        n = _unit(s["normal"])
        wall = room_margin(room, (s["at"][0] + n[0] * 0.05, s["at"][1] + n[1] * 0.05))
        if not -0.2 <= wall <= 0.3:
            problems.append(f"station {s['id']}: {wall - 0.05:.2f} m from the wall of {room['id']}, wants it on the wall")
        t = (-n[1], n[0])
        half = st["plain_width_m"] / 2
        band = [(s["at"][0] + t[0] * u + n[0] * v, s["at"][1] + t[1] * u + n[1] * v)
                for u in [half * (k / 8 - 1) for k in range(17)] for v in (0.02, 0.15, 0.3)]
        hits = set()
        for pid, at, yaw in layout["place"]:
            f = feet.get(pid)
            if f is None:
                continue
            for q in band:
                lx, ly = to_local(q, at, yaw)
                if f[0] <= lx <= f[1] and f[2] <= ly <= f[3]:
                    hits.add(pid)
                    break
        for pid in sorted(hits):
            problems.append(f"station {s['id']}: {pid} sticks out over its plain wall ({st['plain_width_m']:g} m)")
        stand = spot_stand(layout, s)
        if in_rooms(layout, stand) < rad - TOL:
            problems.append(f"station {s['id']}: the player's stand ({stand[0]:.2f}, {stand[1]:.2f}) is not in the room")
        for k in range(9):
            v = rad + st["pass_m"] * k / 8
            c = (stand[0] + n[0] * v, stand[1] + n[1] * v)
            side = [(c[0] + t[0] * w, c[1] + t[1] * w) for w in (-rad, 0.0, rad)]
            if min(in_rooms(layout, q) for q in side) < -TOL:
                problems.append(f"station {s['id']}: the pass behind it leaves the rooms at ({c[0]:.2f}, {c[1]:.2f})")
                break
            near = [o["id"] for o in floors if math.hypot(c[0] - o["at"][0], c[1] - o["at"][1]) < st["radius_m"]]
            if near:
                problems.append(f"station {s['id']}: the pass behind it crosses {near[0]}")
                break
    return problems


def ascii_plan(layout: dict[str, Any], cell: float = 0.5) -> str:
    """A text plan, south at the top as in plan-3.jpg: '#' hull, '.' room floor, 'o' tip-room window side, '=' ramp,
    letters the station spots (C console, V vent, S socket, B breaker board, R renewer: the player's stand)."""
    poly = outline(layout)
    by_id = rooms(layout)
    marks = {"console": "C", "vent": "V", "socket": "S", "breaker": "B", "renewer": "R"}
    spots = [(marks.get(s["id"].split("_")[0], "*"), spot_stand(layout, s) if s.get("normal") else tuple(s["at"]))
             for s in layout["stations"]["spot"]]
    ramp = layout["ramp"]
    lines = []
    y = 7.5
    while y >= -7.5:
        row = []
        x = 13.5
        while x >= -13.5:  # south up and seen from above: east on the left
            ch = " "
            if inside(poly, (x, y)) or any(r["id"].startswith("tip") and room_margin(r, (x, y)) > -0.45
                                           for r in by_id.values()):
                ch = "#"
            if any(room_margin(r, (x, y)) > 0 for r in by_id.values()):
                ch = "."
            if abs(x) < ramp["width_m"] / 2 and ramp["foot"][1] <= y < ramp["hinge"][1]:
                ch = "="
            for mark, at in spots:
                if abs(at[0] - x) < cell / 2 + TOL and abs(at[1] - y) < cell / 2 + TOL:
                    ch = mark
            row.append(ch)
            x -= cell
        lines.append("".join(row).rstrip())
        y -= cell
    head = (f"ship plan v{layout['version']}: {cell:g} m cells, south at the top and east on the left (as plan-3.jpg, "
            "seen from above); # hull, . floor, = ramp, C console; where a player stands at V vent, S socket, B breaker, "
            "R renewer")
    return head + "\n" + "\n".join(lines) + "\n"
