"""The basement's level-design checks (art #78, docs/house.md "The basement").

- The intended dead ends (the design doc's section 8): the darkroom, the boiler room, the pump room and the switch room
  each have exactly one door and no stairs.
- Sight lines, on the floor plan in the doc's metres at eye height (1.6 m): a pillar (a free layout piece in
  `house_dressing.PIECE_HALF`) or a dressing prop whose top reaches the line's height blocks it. `clear` is the
  smallest gap between the line and a blocker (negative: blocked).
  - the generator hall from the passage: from 1 m inside the passage door to 1 m inside each of the hall's other doors,
    to the generator and to the hall's four corners (0.5 m in), and from each door to the generator;
  - each switch from 0.8 m inside each door of its room (the switch box sits at 1.1 to 1.55 m: a prop taller than
    1.1 m blocks it).
Pure Python on the layout and dressing data; the `house` command writes the rows to tools/out/house/basement.json.
"""

from __future__ import annotations

import math

from . import house_dressing as hd

LEVEL = "basement"
DEAD_ENDS = ("darkroom", "boiler_room", "pump_room", "switch_room")
EYE = 1.6
SWITCH_LOW = 1.1  # the switch box's bottom (props/tasks.toml wall_switch box_y)
DOOR_IN = 1.0
SWITCH_DOOR_IN = 0.8


def _level(data: dict) -> dict:
    return next(lv for lv in data["levels"] if lv["level"] == LEVEL)


def _room(lv: dict, rid: str) -> dict:
    return next(r for r in lv["rooms"] if r["id"] == rid)


def dead_ends(data: dict) -> dict:
    """room id -> (door count, stair count) for the intended dead ends."""
    lv = _level(data)
    out = {}
    for rid in DEAD_ENDS:
        rect = _room(lv, rid)["rect"]
        doors = [d for d in lv.get("doors", []) if rid in d["rooms"]]
        stairs = [s for L in data["levels"] for st in L.get("stairs", []) for s in [st] + list(st.get("below", []))
                  if abs(s["y"] - lv["floor_y"]) < 0.01 and _overlap(s["rect"], rect)]
        out[rid] = (len(doors), len(stairs))
    return out


def _overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _inside(rect, door: dict, depth: float) -> tuple[float, float]:
    """A point `depth` metres from the door's centre into the room."""
    x, y = door["at"]
    rx, ry, w, d = rect
    if y == ry:
        return x, y + depth
    if y == ry + d:
        return x, y - depth
    if x == rx:
        return x + depth, y
    return x - depth, y


def _seg_box(a, b, box) -> float:
    """The smallest distance between segment a-b and an axis-aligned box (x0, y0, x1, y1); 0 if they cross."""
    (ax, ay), (bx, by) = a, b
    x0, y0, x1, y1 = box
    n = max(2, int(math.hypot(bx - ax, by - ay) / 0.05))
    best = math.inf
    for i in range(n + 1):
        t = i / n
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        dx = max(x0 - px, 0.0, px - x1)
        dy = max(y0 - py, 0.0, py - y1)
        best = min(best, math.hypot(dx, dy))
    return best


def blockers(data: dict, dressings: dict, cat: dict, rid: str, low: float) -> list[tuple[str, tuple]]:
    """(name, doc-space box) of the room's pillars and of its props whose top reaches `low` metres (ceiling and
    floor-hugging items aside)."""
    lv = _level(data)
    rx, ry = _room(lv, rid)["rect"][:2]
    out = []
    for fp in lv.get("pieces", []):
        half = hd.PIECE_HALF.get(fp["piece"])
        if half and fp.get("room") == rid:
            x, y = fp["at"][0], fp["at"][2]
            out.append((f"{fp['piece']} ({x:g}, {y:g})", (x - half, y - half, x + half, y + half)))
    for kind, it in hd.items(dressings.get(rid, {})):
        r = hd.resolve(it, cat)
        if kind != "props" or r["pivot"] == "ceiling":
            continue
        h0, h1 = hd.span(r)
        if h1 >= low and h0 < EYE:
            f = hd.footprint(r)
            out.append((f"{r['id']} {it['at']}", (f[0] + rx, f[1] + ry, f[2] + rx, f[3] + ry)))
    return out


def _row(name: str, a, b, blocks) -> dict:
    gaps = [(_seg_box(a, b, box), who) for who, box in blocks]
    clear, who = min(gaps) if gaps else (math.inf, "-")
    return {"line": name, "from": [round(a[0], 2), round(a[1], 2)], "to": [round(b[0], 2), round(b[1], 2)],
            "length": round(math.hypot(b[0] - a[0], b[1] - a[1]), 1), "clear": round(clear, 2) if gaps else None,
            "nearest": who}


def hall_sight(data: dict, dressings: dict, cat: dict) -> list[dict]:
    """The generator hall's sight lines from the passage door and from each door to the generator."""
    lv = _level(data)
    hall = _room(lv, "generator_hall")
    rect = hall["rect"]
    doors = [d for d in lv["doors"] if "generator_hall" in d["rooms"]]
    passage = next(d for d in doors if "passage" in d["rooms"])
    other = {next(r for r in d["rooms"] if r != "generator_hall"): d for d in doors if d is not passage}
    gen = next(s for s in hall["stations"] if s["name"] == "Generator")
    g = (rect[0] + gen["at"][0], rect[1] + gen["at"][2])
    x0, y0, w, d = rect
    corners = {"NW": (x0 + 0.5, y0 + 0.5), "NE": (x0 + w - 0.5, y0 + 0.5), "SW": (x0 + 0.5, y0 + d - 0.5),
               "SE": (x0 + w - 0.5, y0 + d - 0.5)}
    # the generator is the target, not a blocker, of the lines that end at it
    blocks = blockers(data, dressings, cat, "generator_hall", EYE)
    no_gen = [b for b in blocks if not b[0].startswith("generator ")]
    p = _inside(rect, passage, DOOR_IN)
    rows = [_row(f"passage door -> {rid} door", p, _inside(rect, dr, DOOR_IN), blocks) for rid, dr in other.items()]
    rows.append(_row("passage door -> generator", p, g, no_gen))
    rows += [_row(f"passage door -> {k} corner", p, c, blocks) for k, c in corners.items()]
    rows += [_row(f"{rid} door -> generator", _inside(rect, dr, DOOR_IN), g, no_gen) for rid, dr in other.items()]
    return rows


def switch_sight(data: dict, dressings: dict, cat: dict) -> list[dict]:
    """Each switch prop from each door of its room: the line to the switch box's centre."""
    lv = _level(data)
    rows = []
    for room in lv["rooms"]:
        for kind, it in hd.items(dressings.get(room["id"], {})):
            if kind != "props" or it["id"] != "wall_switch":
                continue
            r = hd.resolve(it, cat)
            f = hd.footprint(r)
            rx, ry = room["rect"][:2]
            s = ((f[0] + f[2]) / 2 + rx, (f[1] + f[3]) / 2 + ry)
            blocks = [b for b in blockers(data, dressings, cat, room["id"], SWITCH_LOW)
                      if not b[0].startswith("wall_switch ")]
            for dr in lv["doors"]:
                if room["id"] in dr["rooms"]:
                    a = _inside(room["rect"], dr, SWITCH_DOOR_IN)
                    rows.append(_row(f"{room['id']}: door ({dr['at'][0]}, {dr['at'][1]}) -> {it.get('station')}",
                                     a, s, blocks))
    return rows


# ---------------------------------------------------------------- the review pictures

REVIEW = "basement_review.toml"
SHOT_IN = 0.3  # a room's shot stands this far inside its door (the frame stays out of the picture)
LOOK_H = 1.2
FAR_EDGE_H = (0.2, 2.6)  # the hall's far wall band measured for L*, above the floor
PLAN_MARGIN = 1.0


def lamps(data: dict, dressings: dict, cat: dict, spec: dict) -> list[dict]:
    """A real-time lamp stand-in per light fixture of the basement's dressing (basement_review.toml `lamps` by id): at a
    ceiling pivot `drop` below it, at a wall pivot `out` off the wall towards the fixture's front and `up` above it."""
    lv = _level(data)
    out = []
    for room in lv["rooms"]:
        rx, ry = room["rect"][:2]
        for it in dressings.get(room["id"], {}).get("fixtures", []):
            r = hd.resolve(it, cat)
            k = spec.get("lamps", {}).get(r["id"])
            if k is None:
                continue
            x, h, z = r["at"]
            if r["pivot"] == "wall":
                t = math.radians(r["yaw"])
                x, z, h = x + k.get("out", 0.2) * math.sin(t), z + k.get("out", 0.2) * math.cos(t), h + k.get("up", 0.0)
            elif r["pivot"] == "ceiling":
                h -= k.get("drop", 0.3)
            out.append({"id": r["id"], "room": room["id"], "pos": [round(rx + x, 3), round(lv["floor_y"] + h, 3),
                                                                  round(ry + z, 3)],
                        "color": list(k["color"]), "energy": float(k["energy"]), "range": float(k["range"]),
                        "shadow": bool(k.get("shadow", True))})
    return out


def shots(data: dict, spec: dict) -> list[dict]:
    """The review's eye-height shots: each from SHOT_IN inside the door its room shares with `from`, at 1.6 m."""
    lv = _level(data)
    fy = lv["floor_y"]
    out = []
    for s in spec.get("shots", []):
        room = _room(lv, s["room"])
        door = next((d for d in lv["doors"] if set(d["rooms"]) == {s["room"], s["from"]}), None)
        if door is None:
            raise ValueError(f"basement review: {s['room']} has no door to {s['from']}")
        rect = room["rect"]
        px, py = _inside(rect, door, SHOT_IN)
        lx, ly = s.get("look", (rect[0] + rect[2] / 2, rect[1] + rect[3] / 2))
        out.append({"name": f"{s['room']}_from_{s['from']}",
                    "title": s.get("title", f"{room['title'].lower()} from the {s['from'].replace('_', ' ')} door"),
                    "from": [px, fy + EYE, py], "to": [lx, fy + LOOK_H, ly]})
    return out


def review_request(data: dict, dressings: dict, cat: dict, spec: dict, routes: list[dict] | None = None) -> dict:
    """What godot/house/basement.gd lights, shoots and measures: the lamps, the shots, the plan's rooms and rect, the
    level nodes to hide for the plan, the far edge (the hall's west wall from the passage) and the route lines."""
    lv = _level(data)
    fy = lv["floor_y"]
    rects = [r["rect"] for r in lv["rooms"]]
    x0, y0 = min(r[0] for r in rects) - PLAN_MARGIN, min(r[1] for r in rects) - PLAN_MARGIN
    x1 = max(r[0] + r[2] for r in rects) + PLAN_MARGIN
    y1 = max(r[1] + r[3] for r in rects) + PLAN_MARGIN
    hall = _room(lv, "generator_hall")["rect"]
    wx = round(hall[0] + hd.WALL_T + 0.02, 3)
    shot_list = shots(data, spec)
    far = next((s["name"] for s in shot_list if s["name"] == "generator_hall_from_passage"), None)
    lines = [f"{r['name']}: {r['seconds']:g} s walked, the doc {r['doc_s']:g} s ({r['delta_s']:+g} s)"
             for r in routes or []]
    return {"exposure": float(spec.get("exposure", 1.0)), "ambient": list(spec.get("ambient", [0.5, 0.5, 0.5])),
            "ambient_energy": float(spec.get("ambient_energy", 0.05)), "fov": float(spec.get("fov", 75.0)),
            "lamps": lamps(data, dressings, cat, spec), "shots": shot_list,
            "rooms": [{"title": r["title"], "rect": r["rect"]} for r in lv["rooms"]],
            "plan": {"rect": [x0, y0, x1 - x0, y1 - y0], "floor_y": fy},
            "hide": [L["node"] if L["level"] != "roof" else "RoofDeck" for L in data["levels"] if L["level"] != LEVEL],
            "far_edge": {"shot": far, "a": [wx, fy + FAR_EDGE_H[0], hall[1] + 0.5],
                         "b": [wx, fy + FAR_EDGE_H[1], hall[1] + hall[3] - 0.5],
                         "min_lstar": float(spec.get("far_edge_min_lstar", 12.0))},
            "lines": lines}
