"""The House map's light kit (art #83a, docs/house.md "Light"): `layouts/house/lights.toml` as fixtures with positions,
bake zones and presets, and the scenes the bake needs.

- `load` reads lights.toml; `validate` lists unknown types, colours, rooms and zones, rooms in two zones.
- `plan` places every fixture (a ceiling grid, wall slots clear of the doors, a floor grid inset from the walls, or the
  room's perimeter 2 m in) and the bake-only moon spots outside every `every`-th window of a level.
- `write` writes `lights/<level>.tscn` (the level's lights, plot coordinates) and `zones/<zone>.tscn` (the zone's
  room scenes, the level pieces standing in its rooms, its lights, and under `Above` its ceiling: the next level's
  rooms over it and `cover_tiles`, a bake-only slab where the yard lies over it): the input of a zone's LightmapGI bake.

Coordinates are the house layout's (house_layout.py): metres, x east, y south; Godot's x = x, z = y."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

from . import house_layout as H

LIGHTS = H.LAYOUT_DIR / "lights.toml"
MOUNTS = ("ceiling", "wall", "floor")
WALL_INSET = 0.15  # metres from the wall line to a wall fixture's light
FLOOR_INSET = 0.6  # metres from the walls to the floor grid's edge
PERIMETER_INSET = 2.0
DOOR_CLEAR = 1.2  # a wall fixture keeps this far from a door centre
BAKE_STATIC = 1  # Light3D.BAKE_STATIC: baked into the lightmap, not drawn in real time where a lightmap covers


def load(path: Path = LIGHTS) -> dict:
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def rooms_by_id(data: dict) -> dict:
    """room id -> (level, room)"""
    return {r["id"]: (lv, r) for lv in data["levels"] for r in lv["rooms"]}


def zone_rooms(lights: dict, data: dict) -> dict:
    """zone -> its room ids, in file order."""
    out = {}
    for name, z in lights["zones"].items():
        ids = [r["id"] for lv in data["levels"] if lv["level"] in z.get("levels", []) for r in lv["rooms"]]
        out[name] = ids + [r for r in z.get("rooms", []) if r not in ids]
    return out


def room_counts(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if isinstance(v, int) and not isinstance(v, bool)}


def validate(lights: dict, data: dict) -> list[str]:
    rooms = rooms_by_id(data)
    colors, types = lights["colors"], lights["types"]
    problems = []
    for t, spec in types.items():
        if spec.get("mount") not in MOUNTS:
            problems.append(f"type {t}: mount {spec.get('mount')!r} is not one of {MOUNTS}")
        if spec.get("light") not in ("omni", "spot"):
            problems.append(f"type {t}: light {spec.get('light')!r} is not omni or spot")
        if spec.get("color", "c2") not in colors:
            problems.append(f"type {t}: unknown colour {spec.get('color')!r}")
        if spec.get("light") == "spot" and "angle" not in spec:
            problems.append(f"type {t}: a spot needs an angle")
    for rid, entry in lights["rooms"].items():
        if rid not in rooms:
            problems.append(f"rooms.{rid}: no such room in the layout")
        for t in room_counts(entry):
            if t not in types:
                problems.append(f"rooms.{rid}: unknown fixture type {t}")
        if entry.get("color", "c2") not in colors:
            problems.append(f"rooms.{rid}: unknown colour {entry.get('color')!r}")
        if entry.get("place", "grid") not in ("grid", "perimeter"):
            problems.append(f"rooms.{rid}: place {entry.get('place')!r} is not grid or perimeter")
        for fx in entry.get("fixed", []):  # a practical at a kit socket (the dormer's lamp, art #77)
            if fx.get("type") not in types:
                problems.append(f"rooms.{rid}: the fixed fixture {fx.get('name')} has an unknown type {fx.get('type')!r}")
            elif rid in rooms and not H.inside(rooms[rid][1]["rect"], fx["at"][0], fx["at"][2]):
                problems.append(f"rooms.{rid}: the fixed fixture {fx.get('name')} at {fx['at']} is outside the room")
    levels = {lv["level"] for lv in data["levels"]}
    seen: dict = {}
    for name, z in lights["zones"].items():
        for lv in z.get("levels", []):
            if lv not in levels:
                problems.append(f"zones.{name}: no level {lv}")
        for r in z.get("rooms", []):
            if r not in rooms:
                problems.append(f"zones.{name}: no room {r}")
        if not 0 < z.get("texel_low", 0) <= z.get("texel_high", 0):
            problems.append(f"zones.{name}: needs 0 < texel_low <= texel_high")
    for name, ids in zone_rooms(lights, data).items():
        for r in ids:
            if r in seen:
                problems.append(f"room {r} is in zones {seen[r]} and {name}")
            seen[r] = name
    for rid in lights["rooms"]:
        if rid in rooms and rid not in seen:
            problems.append(f"rooms.{rid} has fixtures but no zone")
    for name, p in lights["presets"].items():
        if p.get("lightmap") not in ("texel_high", "texel_low"):
            problems.append(f"presets.{name}: lightmap {p.get('lightmap')!r} is not texel_high or texel_low")
    return problems


def grid(rect, n: int, inset: float = 0.0) -> list[tuple[float, float]]:
    """n points on a grid of cells in rect shrunk by inset, filled row by row; the column count follows the aspect."""
    x0, y0, w, d = rect[0] + inset, rect[1] + inset, rect[2] - 2 * inset, rect[3] - 2 * inset
    cols = max(1, min(n, round(math.sqrt(n * w / d))))
    rows = math.ceil(n / cols)
    pts = [(x0 + (i + 0.5) * w / cols, y0 + (j + 0.5) * d / rows) for j in range(rows) for i in range(cols)]
    return pts[:n]


def _ring(rect, inset: float):
    """The rect shrunk by inset as a closed path: (corners, perimeter length)."""
    x0, y0, x1, y1 = rect[0] + inset, rect[1] + inset, rect[0] + rect[2] - inset, rect[1] + rect[3] - inset
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], 2 * (x1 - x0 + y1 - y0)


def _along(corners, t: float) -> tuple[float, float]:
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        seg = abs(bx - ax) + abs(by - ay)
        if t <= seg:
            f = t / seg if seg else 0.0
            return ax + (bx - ax) * f, ay + (by - ay) * f
        t -= seg
    return corners[-1]


def perimeter(rect, n: int, inset: float, avoid: list[tuple[float, float]] = ()) -> list[tuple[float, float]]:
    """n points spaced evenly along the rect's edges inset; a point within DOOR_CLEAR of an avoided point moves on."""
    corners, length = _ring(rect, inset)
    pts = []
    for k in range(n):
        t = (k + 0.5) * length / n
        for _ in range(8):
            p = _along(corners, t % length)
            if all(math.dist(p, a) >= DOOR_CLEAR for a in avoid):
                break
            t += DOOR_CLEAR
        pts.append((round(p[0], 3), round(p[1], 3)))
    return pts


def plan(lights: dict, data: dict) -> list[dict]:
    """Every fixture and moon spot: name, room, level, zone, type, light, x, h (Godot y), y, color, energy, range,
    angle and aim (spots), glow, bake."""
    rooms = rooms_by_id(data)
    zone_of = {r: z for z, ids in zone_rooms(lights, data).items() for r in ids}
    colors, types = lights["colors"], lights["types"]
    out = []
    for rid, entry in lights["rooms"].items():
        lv, room = rooms[rid]
        counts = room_counts(entry)
        doors = [tuple(d["at"]) for d in lv.get("doors", []) if rid in d.get("rooms", [])]
        for mount in MOUNTS:
            kinds = [t for t, n in counts.items() if types[t]["mount"] == mount for _ in range(n)]
            if not kinds:
                continue
            if mount == "wall":
                pts = perimeter(room["rect"], len(kinds), WALL_INSET, doors)
            elif entry.get("place") == "perimeter":
                pts = perimeter(room["rect"], len(kinds), PERIMETER_INSET)
            else:
                pts = grid(room["rect"], len(kinds), FLOOR_INSET if mount == "floor" else 0.0)
            seen: dict = {}
            for t, (x, y) in zip(kinds, pts):
                spec = types[t]
                seen[t] = seen.get(t, 0) + 1
                h = lv["floor_y"] + spec["h"]
                f = {"name": f"{rid}_{t}_{seen[t]:02d}", "room": rid, "level": lv["level"], "zone": zone_of.get(rid),
                     "type": t, "light": spec["light"], "x": round(x, 3), "h": round(h, 3), "y": round(y, 3),
                     "color": colors[spec.get("color", entry.get("color", "c2"))], "energy": spec["energy"],
                     "range": spec["range"], "glow": bool(spec.get("glow")), "bake": True}
                if spec["light"] == "spot":
                    f["angle"] = spec["angle"]
                    f["aim"] = [f["x"], round(lv["floor_y"], 3), f["y"]]
                out.append(f)
        for fx in entry.get("fixed", []):  # at = [x, h over the room's floor, y]
            spec = types[fx["type"]]
            x, h, y = (float(v) for v in fx["at"])
            out.append({"name": f"{rid}_{fx['type']}_{fx['name']}", "room": rid, "level": lv["level"],
                        "zone": zone_of.get(rid), "type": fx["type"], "light": spec["light"], "x": round(x, 3),
                        "h": round(lv["floor_y"] + h, 3), "y": round(y, 3),
                        "color": colors[spec.get("color", entry.get("color", "c2"))], "energy": spec["energy"],
                        "range": spec["range"], "glow": bool(spec.get("glow")), "bake": True})
    out += moon_spots(lights, data, zone_of)
    return out


def moon_spots(lights: dict, data: dict, zone_of: dict) -> list[dict]:
    m = lights["moon"]
    out = []
    for lv in data["levels"]:
        rooms = {r["id"]: r for r in lv["rooms"]}
        for k, w in enumerate(lv.get("windows", [])):
            if k % m["every"]:
                continue
            x0, y0, wd, dp = rooms[w["room"]]["rect"]
            x, y = w["at"]
            nx = -1 if x == x0 else 1 if x == x0 + wd else 0
            ny = -1 if y == y0 else 1 if y == y0 + dp else 0
            out.append({"name": f"{w['room']}_moon_{k + 1:02d}", "room": w["room"], "level": lv["level"],
                        "zone": zone_of.get(w["room"]), "type": "moon", "light": "spot",
                        "x": x + nx * m["out"], "h": round(lv["floor_y"] + m["h"], 3), "y": y + ny * m["out"],
                        "aim": [x - nx * m["in"], round(lv["floor_y"] + 0.5, 3), y - ny * m["in"]],
                        "color": lights["colors"]["moon"], "energy": m["energy"], "range": m["range"],
                        "angle": m["angle"], "glow": False, "bake": True})
    return out


def _aim_basis(f: dict) -> list[float]:
    """Rows of a basis whose -Z points from the light to its aim (a Godot spot shines along -Z)."""
    d = [f["aim"][0] - f["x"], f["aim"][1] - f["h"], f["aim"][2] - f["y"]]
    n = math.sqrt(sum(c * c for c in d)) or 1.0
    z = [-c / n for c in d]
    up = [0.0, 0.0, 1.0] if abs(z[1]) > 0.99 else [0.0, 1.0, 0.0]
    x = [up[1] * z[2] - up[2] * z[1], up[2] * z[0] - up[0] * z[2], up[0] * z[1] - up[1] * z[0]]
    xn = math.sqrt(sum(c * c for c in x))
    x = [c / xn for c in x]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return [x[0], y[0], z[0], x[1], y[1], z[1], x[2], y[2], z[2]]


def light_node(f: dict, parent: str) -> str:
    basis = _aim_basis(f) if f["light"] == "spot" else [1, 0, 0, 0, 1, 0, 0, 0, 1]
    tf = "Transform3D(" + ", ".join(H._num(v) for v in basis + [f["x"], f["h"], f["y"]]) + ")"
    cls = "SpotLight3D" if f["light"] == "spot" else "OmniLight3D"
    lines = [f'[node name="{f["name"]}" type="{cls}" parent="{parent}"]', f"transform = {tf}",
             "light_color = Color(" + ", ".join(H._num(c) for c in f["color"]) + ", 1)",
             f"light_energy = {H._num(f['energy'])}", f"light_bake_mode = {BAKE_STATIC}"]
    if f["light"] == "spot":
        lines += [f"spot_range = {H._num(f['range'])}", f"spot_angle = {H._num(f['angle'])}"]
    else:
        lines.append(f"omni_range = {H._num(f['range'])}")
    lines += [f'metadata/fixture = "{f["type"]}"', f"metadata/glow = {'true' if f['glow'] else 'false'}"]
    return "\n".join(lines)


def write(lights: dict, data: dict, planned: dict, fixtures: list[dict], out: Path) -> dict:
    """lights/<level>.tscn and zones/<zone>.tscn into out (the scene_res folder); returns counts per level and zone."""
    st = data["settings"]
    kit_res, scene_res = st["kit_res"], st["scene_res"].rstrip("/")
    out = Path(out)
    (out / "lights").mkdir(parents=True, exist_ok=True)
    (out / "zones").mkdir(parents=True, exist_ok=True)
    summary = {"levels": {}, "zones": {}}
    for lv in data["levels"]:
        sc = H._Scene(f"{lv['node']}Lights")
        mine = [f for f in fixtures if f["level"] == lv["level"]]
        sc.nodes += [light_node(f, ".") for f in mine]
        (out / "lights" / f"{lv['level']}.tscn").write_text(sc.text(), encoding="utf-8", newline="\n")
        summary["levels"][lv["level"]] = len(mine)
    rooms = rooms_by_id(data)
    extras = {pl["level"]: pl["extra"] for pl in planned["levels"]}
    for zone, ids in zone_rooms(lights, data).items():
        sc = H._Scene(f"Zone_{zone}")
        sc.group("Rooms")
        sc.group("Pieces")
        sc.group("Lights")
        n_pieces = 0
        for rid in ids:
            lv, room = rooms[rid]
            rx, ry = room["rect"][0], room["rect"][1]
            sc.instance(room["node"], "Rooms", f"{scene_res}/{lv['level']}/{rid}.tscn", H._tf(0, rx, lv["floor_y"], ry))
        seen: dict = {}
        for lv_name in dict.fromkeys(rooms[r][0]["level"] for r in ids):
            lv = next(v for v in data["levels"] if v["level"] == lv_name)
            for p in extras[lv_name]:
                if not any(H.inside(rooms[r][1]["rect"], p["x"], p["y"]) for r in ids if rooms[r][0] is lv):
                    continue
                seen[p["id"]] = seen.get(p["id"], 0) + 1
                sc.instance(p.get("name", f"{p['id']}_{seen[p['id']]}"), "Pieces", kit_res.format(id=p["id"]),
                            H._tf(p["turn"], p["x"], p["h"], p["y"]))
                n_pieces += 1
        # the floor slabs above are the zone's ceiling: the next level's rooms over the zone's rooms (the bake keeps
        # them as occluders at a tiny texel scale)
        order = [v["level"] for v in data["levels"]]
        top = max(order.index(rooms[r][0]["level"]) for r in ids)
        above = []
        if top + 1 < len(order):  # the yard's own slab over the outer basement rooms is in their scenes (#108)
            up = data["levels"][top + 1]
            above = [r for r in up["rooms"] if r["kind"] != "area"
                     and any(H.overlap(r["rect"], rooms[i][1]["rect"]) for i in ids if rooms[i][1]["kind"] != "area")]
            if above:
                sc.group("Above")
            for r in above:
                sc.instance(r["node"], "Above", f"{scene_res}/{up['level']}/{r['id']}.tscn",
                            H._tf(0, r["rect"][0], up["floor_y"], r["rect"][1]))
        mine = [f for f in fixtures if f["zone"] == zone]
        sc.nodes += [light_node(f, "Lights") for f in mine]
        (out / "zones" / f"{zone}.tscn").write_text(sc.text(), encoding="utf-8", newline="\n")
        summary["zones"][zone] = {"rooms": len(ids), "pieces": n_pieces, "above": len(above), "lights": len(mine),
                                  "fixtures": sum(f["type"] != "moon" for f in mine)}
    return summary
