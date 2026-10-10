"""How full a House room reads (art #104, pass 2; docs/house.md "Fill"): pure-Python measures of a room's dressing.

- wall lining: the share of the room's free wall length (its wall faces minus door openings, windows and the stairs'
  and holes' openings) with a piece standing against it: a floor piece (not `clutter`, not LOOSE) at least LINE_H
  tall whose footprint comes within LINE_GAP of the wall face with its back to that wall, or a wall-mounted piece of furniture (upper cabinets,
  a tool wall); its footprint's projection on the wall counts;
- floor: the share of the floor (stairs and holes left out) under the footprints of floor furniture (not `clutter`,
  at least FLOOR_H tall: rugs and floor clutter do not count);
- heights: the bands a room has pieces in: F floor (a top between 0.1 and 0.75 m), S surfaces (a non-clutter top
  between 0.75 and 1.25 m), T tall (a non-clutter top at 1.6 m or more, or wall shelving from 1.2 m up);
- stories: the STORIES groupings found (an anchor with each other part within STORY_R), and the room's lamps.
"""
from __future__ import annotations

from . import house_clutter as hc
from . import house_dressing as hd

LINE_GAP = 0.3  # a piece lines the wall when its footprint comes this close to the wall face
LINE_H = 0.4
FLOOR_H = 0.3
WINDOW_HALF = 1.0  # a window is 2 m wide: its wall length is not free wall
SMALL = {"wc", "bathroom", "pantry", "boiler_room", "pump_room", "switch_room", "darkroom", "passage", "corridor"}
TARGET = {"wall": 55, "wall_small": 40, "floor": 18}  # per cent (brief #104 pass 2)
# floor pieces that stand free rather than line a wall
LOOSE = {"potted_plant", "planter_pot", "stool", "bean_bag", "trash_bin", "dining_chair", "office_chair",
         "terrace_chair", "balcony_chair", "deckchair", "floor_lamp", "coat_rack", "tripod_camera"}
WALL_SHELVING = {"wall_shelf", "kitchen_upper", "tool_wall", "jar_shelf", "towel_rack"}
LAMPS = {"table_lamp", "floor_lamp", "wall_sconce", "pendant_shade", "chandelier", "bare_bulb", "cage_lamp",
         "industrial_pendant", "fluorescent_tube", "lantern", "string_lights", "safelight_red"}
STORY_R = 2.0
# story -> (the anchor id, then each other part: a tuple of ids any of which will do)
STORIES = {
    "reading corner": ("armchair", ("floor_lamp", "table_lamp"), ("small_table", "tray_table", "nightstand"),
                       ("book_stack", "book_row")),
    "laundry pile": ("laundry_basket", ("laundry_pile",)),
    "half-packed box": ("open_box", ("book_stack", "paper_stack", "laundry_pile", "cardboard_box")),
    "boots by the door": ("boots", ("shoe_rack", "doormat", "coat_rack", "shoes")),
    "drying rack": ("drying_rack", ("laundry_basket", "laundry_pile")),
    "toy spill": ("toy_spill", ("toy_chest", "toy_blocks")),
    "work bench": ("workbench", ("toolbox_cart", "tool_wall", "crate")),
    "kitchen prep": ("kitchen_counter", ("cooking_pot",), ("plate_stack", "cup_set", "fruit_bowl")),
    "wardrobe spill": ("wardrobe", ("laundry_pile", "shoes", "open_box")),
    "desk work": ("desk", ("office_chair", "dining_chair", "stool"), ("paper_stack", "book_stack"),
                  ("table_lamp", "filing_cabinet")),
    "store stack": ("crate", ("cardboard_box",), ("barrel", "jerrycan", "wine_bottle_crate", "fuel_barrel")),
}


def _resolved(dressing: dict, cat: dict) -> list[dict]:
    out = []
    for kind, it in hd.items(dressing):
        r = hd.resolve(it, cat)
        r["fp"], r["span"], r["kind"] = hd.footprint(r), hd.span(r), kind
        r["class"] = cat.get(it["id"], {}).get("class", "")
        out.append(r)
    return out


def _union(spans: list) -> float:
    total, end = 0.0, None
    for a, b in sorted(spans):
        if end is None or a > end:
            total += b - a
            end = b
        elif b > end:
            total += b - end
            end = b
    return total


def _clip(spans: list, free: list) -> list:
    return [(max(a, f0), min(b, f1)) for a, b in spans for f0, f1 in free if min(b, f1) > max(a, f0)]


def free_wall(level: dict, room: dict, sh: dict) -> dict:
    """side -> the free wall spans (doors already cut by the shell; windows, stairs and holes cut here)."""
    out = {}
    blocks = sh["stairs"] + sh["holes"]
    for side, spans in hc.wall_spans(sh, corner=0.0).items():
        spans = [tuple(s) for s in spans]
        for x, z in hc._windows(level, room):
            if hc._side_of((x, z), sh["w"], sh["d"])[0] == side:
                c = x if side in "NS" else z
                spans = hc._cut(spans, c - WINDOW_HALF, c + WINDOW_HALF)
        sb = hc._strip_box(side, LINE_GAP + 0.3, sh["w"], sh["d"])
        for b in blocks:
            if hc._ov(sb, b):
                spans = hc._cut(spans, b[0], b[2]) if side in "NS" else hc._cut(spans, b[1], b[3])
        out[side] = spans
    return out


def _lines(r: dict) -> bool:
    if r["kind"] != "props" or r["class"] == "clutter" or r["id"] in LOOSE:
        return False
    if r["pivot"] == "wall":
        return r["id"] in WALL_SHELVING or r["size"][2] >= LINE_H
    return r["span"][0] < 0.3 and r["span"][1] - r["span"][0] >= LINE_H


def _backs_onto(r: dict, side: str) -> bool:
    """The piece's back is towards the side's wall (it faces away from it); a piece turned off the four faces may
    line any wall."""
    face = next((f for f, y in hd.FACES.items() if abs((r["yaw"] - y + 180) % 360 - 180) < 1e-6), None)
    return face is None or face == hc.SIDE_FACE[side]


def metrics(level: dict, room: dict, dressing: dict, cat: dict, levels: list, floor: bool = True) -> dict:
    """The room's fill measures (see the module's doc); floor=False skips the floor's grid (its share reads 0)."""
    sh = hd.shell(level, room, levels)
    w, d, t = sh["w"], sh["d"], hd.WALL_T
    res = _resolved(dressing, cat)
    free = free_wall(level, room, sh)
    total = sum(b - a for s in free.values() for a, b in s)
    lined = 0.0
    face = {"N": lambda fp: fp[1] - t, "S": lambda fp: d - t - fp[3], "W": lambda fp: fp[0] - t,
            "E": lambda fp: w - t - fp[2]}
    for side, spans in free.items():
        proj = [(r["fp"][0], r["fp"][2]) if side in "NS" else (r["fp"][1], r["fp"][3])
                for r in res if _lines(r) and face[side](r["fp"]) < LINE_GAP and _backs_onto(r, side)]
        lined += _union(_clip(proj, spans))
    # the floor on a 0.1 m grid
    c = hd.CELL
    nx, nz = (int(round(w / c)), int(round(d / c))) if floor else (0, 0)
    void = sh["stairs"] + sh["holes"]
    furn = [r["fp"] for r in res if r["kind"] == "props" and r["class"] != "clutter" and r["pivot"] == "floor"
            and r["span"][0] < 0.3 and r["span"][1] - r["span"][0] >= FLOOR_H]
    cells = covered = 0
    for i in range(nx):
        x = (i + 0.5) * c
        for j in range(nz):
            z = (j + 0.5) * c
            if any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in void):
                continue
            cells += 1
            covered += any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in furn)
    bands = ""
    if any(0.1 < r["span"][1] <= 0.75 and r["pivot"] == "floor" for r in res if r["kind"] == "props"):
        bands += "F"
    if any(0.75 < r["span"][1] <= 1.25 and r["class"] != "clutter" for r in res if r["kind"] == "props"):
        bands += "S"
    if any((r["span"][1] >= 1.6 and r["class"] != "clutter" and r["pivot"] != "ceiling")
           or (r["id"] in WALL_SHELVING and r["span"][0] >= 1.2) for r in res if r["kind"] == "props"):
        bands += "T"
    small = room["id"] in SMALL
    return {"room": room["id"], "free_wall_m": round(total, 2), "lined_m": round(lined, 2),
            "wall_pct": round(100 * lined / total, 1) if total else 100.0,
            "floor_pct": round(100 * covered / cells, 1) if cells else 0.0, "heights": bands,
            "stories": stories(res), "lamps": sum(1 for r in res if r["id"] in LAMPS),
            "items": sum(1 for r in res if r["kind"] == "props"), "small": small,
            "wall_target": TARGET["wall_small" if small else "wall"], "floor_target": TARGET["floor"]}


def stories(res: list) -> list[str]:
    """The STORIES groupings among resolved items: an anchor with every part within STORY_R of it."""
    found = []
    for name, (anchor, *parts) in STORIES.items():
        for a in (r for r in res if r["id"] == anchor):
            x, z = a["at"][0], a["at"][2]
            if all(any(r["id"] in ids and hd.box_dist(r["fp"], x, z) <= STORY_R for r in res if r is not a)
                   for ids in parts):
                found.append(name)
                break
    return found


def passes(m: dict) -> list[str]:
    """The targets a room's measures miss (empty when it meets them all)."""
    miss = []
    if m["wall_pct"] < m["wall_target"]:
        miss.append(f"wall {m['wall_pct']:g}% < {m['wall_target']}%")
    if m["floor_pct"] < m["floor_target"]:
        miss.append(f"floor {m['floor_pct']:g}% < {m['floor_target']}%")
    if m["heights"] != "FST":
        miss.append(f"heights {m['heights'] or '-'}")
    if len(m["stories"]) < 2:
        miss.append(f"{len(m['stories'])} stories")
    return miss


def table(data: dict, dressings: dict, cat: dict, rooms=None) -> list[dict]:
    """The measures of every room in rooms (default: house_clutter.RULES) that has a dressing."""
    rooms = rooms or hc.RULES
    out = []
    for lv in data["levels"]:
        for room in lv["rooms"]:
            if room["id"] in rooms and room["id"] in dressings:
                out.append(metrics(lv, room, dressings[room["id"]], cat, data["levels"]))
    return out


def fmt(m: dict) -> str:
    miss = passes(m)
    return (f"{m['room']}: wall {m['wall_pct']:g}% of {m['free_wall_m']:g} m, floor {m['floor_pct']:g}%, "
            f"heights {m['heights'] or '-'}, {len(m['stories'])} stories, {m['lamps']} lamps, {m['items']} items"
            + (f" (misses: {'; '.join(miss)})" if miss else ""))
