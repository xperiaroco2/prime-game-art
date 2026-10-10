"""The attic's old things and hiding spots and the roof deck's dressing and lookout (art #77, map #73): the data in
layouts/house/dressing/attic_roof/attic.toml and roof.toml, checked in pure Python (docs/house.md, "The attic and the roof deck").

- `load(name)`: a dressing file with every item's footprint (w along its local X, d along Z, h) from the dressing
  library (props/library.toml, #87) or its own `size` (a placeholder for the hero props).
- `check(z, data)`: the items inside the floor, off each other and the kept-free rects, under the attic's roof, the
  inventory's counts; every hiding spot reachable for a pick-up; the roof's stations reachable.
- `reach(z, data)`: per hiding spot, a point a player (radius PLAYER_R) can walk to from the ladder, within REACH_M of
  the spot in plan and with a clear line of sight from the eye (EYE_M) to it.
- `lookout(z, data)`: from each lookout eye, the share of the plot's fence openings in view over the parapet, and which
  windows of the house can be seen (the design doc: "the roof sees the yard, not inside").
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path
from typing import Any

from . import common, house_layout
from .house_zones import _ccw, _near, overlap, rect

DRESSING = common.ROOT / "layouts" / "house" / "dressing" / "attic_roof"  # not the rooms' format (#75b): kept apart
LIBRARY = common.ROOT / "props" / "library.toml"
PLOT = common.ROOT / "layouts" / "house" / "outdoor" / "plot.toml"
PLAYER_R = 0.4  # the brief's 0.4 m player capsule, taken as its radius (stricter than the zones' 0.35)
REACH_M = 1.0  # pick-up reach in plan from the capsule's axis
EYE_M = 1.6
SPOT_MAX_H = 2.0  # no spot above a standing player's reach
GRID = 0.1
WALL_HALF = 0.1
PARAPET_HALF = 0.14  # the parapet's cap (kit_geom.build_parapet)
FLAT_H = 0.1  # lower than this is walked over (rugs, the picture frames' depth is not their height)
# inventory.md section 6: the attic's and the roof deck's props (light fixtures: #83a)
COUNTS = {
    "attic": {"trunk": 6, "sheeted_furniture": 5, "old_wardrobe": 2, "mannequin": 1, "standing_mirror": 1,
              "rocking_horse": 1, "rolled_carpet": 3, "old_bicycle": 1, "cardboard_box": 10, "crate": 5,
              "picture_frame": 6, "potted_plant": 1, "rug": 2},
    "roof": {"roof_vent": 4, "antenna": 1, "loot_crate": 1, "roof_water_tank": 1},
}
MIN_SPOTS = 10  # the brief: about 12


def _library() -> dict[str, list[float]]:
    with LIBRARY.open("rb") as f:
        return {p["id"]: [float(v) for v in p["size_m"]] for p in tomllib.load(f)["prop"]}


def load(name: str, folder: Path = DRESSING) -> dict[str, Any]:
    with (Path(folder) / f"{name}.toml").open("rb") as f:
        z = tomllib.load(f)
    lib = _library()
    items = []
    for i, it in enumerate(z.get("items", [])):
        it = dict(it, index=i)
        size = it.get("size") or lib.get(it["id"])
        if size:
            it["w"], it["d"], it["h"] = (float(v) for v in size)
        it.setdefault("yaw", 0.0)
        it.setdefault("src", "library")
        items.append(it)
    z["items"] = items
    z["name"] = name
    return z


def footprint(it: dict) -> list[tuple[float, float]]:
    return _ccw(rect(it["at"][0], it["at"][1], it["w"], it["d"], it["yaw"]))


def _box(x0, y0, w, d) -> list[tuple[float, float]]:
    return [(x0, y0), (x0 + w, y0), (x0 + w, y0 + d), (x0, y0 + d)]


def _level(data: dict, name: str) -> dict:
    return next(lv for lv in data["levels"] if lv["level"] == name)


def solids(z: dict, data: dict) -> list[dict]:
    """What stands on the floor: the items (not the flat ones) and, on the roof, the layout's free kit pieces (the
    chimneys, from their pivot at the north-west corner). Each: poly, h (top above the floor), id, index."""
    out = [{"poly": footprint(it), "h": it["h"], "id": it["id"], "index": it["index"]}
           for it in z["items"] if "w" in it and it["h"] >= FLAT_H]
    for fp in _level(data, z["room"]).get("pieces", []):
        size = data["pieces"].get(fp["piece"], {}).get("size", [1, 1, 2])
        x, y = float(fp["at"][0]), float(fp["at"][2])
        out.append({"poly": _box(x, y, float(size[0]), float(size[1])), "h": float(size[2]) if len(size) > 2 else 2.0,
                    "id": fp["piece"], "index": None})
    return out


def floor_rect(z: dict) -> tuple[float, float, float, float]:
    """The floor's free rectangle (x0, y0, x1, y1): inside the walls (attic) or the parapet (roof)."""
    m = WALL_HALF if z["room"] == "attic" else PARAPET_HALF
    x, y, w, d = (float(v) for v in z["rect"])
    return x + m, y + m, x + w - m, y + d - m


def blocked_rects(z: dict, data: dict) -> list[list[tuple[float, float]]]:
    """Floor nobody stands on: the hatch's hole in the attic, the attic itself on the roof (with its walls)."""
    out = []
    if z["room"] == "attic":
        for h in _level(data, "attic").get("holes", []):
            if "tile" in h:
                out.append(_box(float(h["tile"][0]), float(h["tile"][1]), 2.0, 2.0))
    if "hole" in z:
        x, y, w, d = (float(v) for v in z["hole"])
        out.append(_box(x - WALL_HALF, y - WALL_HALF, w + 2 * WALL_HALF, d + 2 * WALL_HALF))
    return out


def roof_line(z: dict, data: dict, y: float) -> float:
    """The attic roof's underside above the attic floor at plan y (the kit's pitch from the eaves)."""
    r = float(data["spec"]["grid"]["gable_rise_per_m"])
    _, y0, _, d = (float(v) for v in z["rect"])
    a = max(0.0, min(y - y0, y0 + d - y))
    return float(z.get("eave_h", 2.2)) + r * a - (r * 0.1 + 0.02)


def walkable(z: dict, data: dict) -> tuple[set, Any]:
    """The grid cells a player can reach from z["arrive"], and the cell centre function."""
    x0, y0, x1, y1 = floor_rect(z)
    nx, ny = int((x1 - x0) / GRID), int((y1 - y0) / GRID)
    blocks = [s["poly"] for s in solids(z, data)] + blocked_rects(z, data)
    boxes = [(min(p[0] for p in b) - PLAYER_R, min(p[1] for p in b) - PLAYER_R,
              max(p[0] for p in b) + PLAYER_R, max(p[1] for p in b) + PLAYER_R) for b in blocks]

    def cell(i, j):
        return x0 + (i + 0.5) * GRID, y0 + (j + 0.5) * GRID

    def free(i, j):
        px, py = cell(i, j)
        if not (x0 + PLAYER_R <= px <= x1 - PLAYER_R and y0 + PLAYER_R <= py <= y1 - PLAYER_R):
            return False
        return not any(bx[0] <= px <= bx[2] and bx[1] <= py <= bx[3] and _near(px, py, b, PLAYER_R)
                       for b, bx in zip(blocks, boxes))

    ok = {(i, j) for i in range(nx) for j in range(ny) if free(i, j)}
    ax, ay = z["arrive"]
    start = min(ok, key=lambda c: math.dist(cell(*c), (ax, ay))) if ok else None
    if start is None or math.dist(cell(*start), (ax, ay)) > 0.5:
        return set(), cell
    seen, todo = {start}, [start]
    while todo:
        i, j = todo.pop()
        for c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if c in ok and c not in seen:
                seen.add(c)
                todo.append(c)
    return seen, cell


def _clear_line(a, b, blockers: list[dict], step: float = 0.05) -> bool:
    """No blocker's box (plan polygon from the floor to its h) cuts the segment a -> b (x, y, height)."""
    n = max(1, int(math.dist(a, b) / step))
    for k in range(1, n):
        t = k / n
        p = [a[i] + (b[i] - a[i]) * t for i in range(3)]
        for s in blockers:
            if p[2] < s["h"] and s["bx"][0] <= p[0] <= s["bx"][2] and s["bx"][1] <= p[1] <= s["bx"][3] \
                    and _near(p[0], p[1], s["poly"], 0.0):
                return False
    return True


def _host(z: dict, spot: dict):
    cands = [it for it in z["items"] if it["id"] == spot.get("in") and "w" in it]
    return min(cands, key=lambda it: math.dist(it["at"], spot["at"]))["index"] if cands else None


def reach(z: dict, data: dict) -> list[dict]:
    seen, cell = walkable(z, data)
    sol = solids(z, data)
    for s in sol:
        s["bx"] = (min(p[0] for p in s["poly"]), min(p[1] for p in s["poly"]),
                   max(p[0] for p in s["poly"]), max(p[1] for p in s["poly"]))
    out = []
    for sp in z.get("spots", []):
        sx, sy = (float(v) for v in sp["at"])
        h = float(sp["h"])
        host = _host(z, sp)
        blockers = [s for s in sol if s["index"] is None or s["index"] != host]
        near = sorted((math.dist(cell(*c), (sx, sy)), cell(*c)) for c in seen)
        stand = None
        if h <= SPOT_MAX_H:
            for dist, (px, py) in near:
                if dist > REACH_M:
                    break
                if _clear_line((px, py, EYE_M), (sx, sy, h + 0.05), blockers):
                    stand = [round(px, 2), round(py, 2)]
                    break
        out.append({"name": sp["name"], "at": [sx, sy], "h": h, "in": sp.get("in"), "host": host,
                    "stand": stand, "reachable": stand is not None})
    return out


def check(z: dict, data: dict) -> list[str]:
    problems = []
    x0, y0, x1, y1 = floor_rect(z)
    counts: dict[str, int] = {}
    for it in z["items"]:
        counts[it["id"]] = counts.get(it["id"], 0) + 1
        if "w" not in it:
            problems.append(f"{it['id']} #{it['index']}: no size (not in the library and no `size`)")
            continue
        poly = footprint(it)
        if any(not (x0 - 1e-6 <= p[0] <= x1 + 1e-6 and y0 - 1e-6 <= p[1] <= y1 + 1e-6) for p in poly):
            problems.append(f"{it['id']} at {it['at']}: outside the floor")
        for b in blocked_rects(z, data) + [_box(*r) for r in z.get("clear", [])]:
            if it["h"] >= FLAT_H and overlap(poly, _ccw(b), 0.01):
                problems.append(f"{it['id']} at {it['at']}: on the hole or a kept-free floor {b[0]}")
        if z["room"] == "attic":
            low = min(roof_line(z, data, p[1]) for p in poly)
            if it["h"] > low - 0.02:
                problems.append(f"{it['id']} at {it['at']}: {it['h']} m tall under a {low:.2f} m roof")
    sol = solids(z, data)
    for i, a in enumerate(sol):
        for b in sol[i + 1:]:
            if overlap(a["poly"], b["poly"], 0.01):
                problems.append(f"{a['id']} and {b['id']} overlap")
    want = COUNTS.get(z["room"], {})
    for pid in sorted(set(want) | set(counts)):
        if want.get(pid, 0) != counts.get(pid, 0):
            problems.append(f"{pid}: {counts.get(pid, 0)} placed, the inventory has {want.get(pid, 0)}")
    if z["room"] == "attic":
        spots = reach(z, data)
        if len(spots) < MIN_SPOTS:
            problems.append(f"{len(spots)} hiding spots, fewer than {MIN_SPOTS}")
        problems += [f"hiding spot {s['name']}: no pick-up from anywhere a player stands" for s in spots
                     if not s["reachable"]]
        problems += [f"hiding spot {s['name']}: no `{s['in']}` holds it" for s in spots if s["host"] is None]
    else:
        seen, cell = walkable(z, data)
        for it in z["items"]:
            if it.get("station"):
                r = max(it["w"], it["d"]) / 2 + 0.8
                if not any(math.dist(cell(*c), it["at"]) <= r for c in seen):
                    problems.append(f"the {it['station']} station ({it['id']}) is out of reach from the roof door")
        lk = z.get("lookout")
        if lk:
            if not any(math.dist(cell(*c), lk["station"]) <= 0.5 for c in seen):
                problems.append("the Lookout station's point is out of reach from the roof door")
            lv = _level(data, "roof")
            room = next(r for r in lv["rooms"] if r["id"] == z["room"])
            marker = next((s["at"] for s in room.get("stations", []) if s["name"] == "Lookout"), None)
            at = (room["rect"][0] + marker[0], room["rect"][1] + marker[2]) if marker else None
            if at is None or math.dist(at, lk["station"]) > 1e-6:
                problems.append(f"the lookout's station {lk['station']} is not the layout's Lookout station")
            view = lookout(z, data)
            own = next((v for v in view if math.dist(v["eye"], lk["station"]) < 1e-6), None)
            if own is None:
                problems.append("the lookout's station is not one of its eyes")
            for t in lk["see"] if own else []:
                if own["see"][t] < 0.5:
                    problems.append(f"the lookout sees less than half of the {t} from its station")
            for v in view:
                if v["house_windows"]:
                    problems.append(f"the lookout eye {v['eye']} sees into the house: {v['house_windows']}")
    return problems


# --- the lookout ---------------------------------------------------------------------------------------------------


def _targets(names: list[str]) -> dict[str, list[tuple[float, float, float]]]:
    with PLOT.open("rb") as f:
        plot = tomllib.load(f)
    post_h = float(plot["fence"].get("post_h", 1.8))
    out = {}
    for op in plot["fence"]["openings"]:
        if op["id"] in names:
            cx, cy = (float(v) for v in op["centre"])
            w = float(op["width"])
            out[op["id"]] = [(cx - w / 2 + w * (k + 0.5) / 9, cy, h) for k in range(9) for h in (0.2, 1.0, post_h - 0.1)]
    return out


def _windows(data: dict) -> dict[str, list[tuple[str, tuple[float, float, float]]]]:
    """Points just outside each window's glass, by level: (label, (x, y, height above the ground))."""
    g = data["spec"]["grid"]
    sill, wh = float(g["window_sill_m"]), float(g["window_h_m"])
    out: dict[str, list] = {}
    for lv in data["levels"]:
        rooms = {r["id"]: r for r in lv["rooms"]}
        for w in lv.get("windows", []):
            x, y = (float(v) for v in w["at"])
            rx, ry, rw, rd = (float(v) for v in rooms[w["room"]]["rect"])
            nx = -1 if x == rx else 1 if x == rx + rw else 0
            ny = -1 if y == ry else 1 if y == ry + rd else 0
            top = sill + (0.8 if lv["walls"] == "knee" else wh)
            px, py = x + nx * 0.12, y + ny * 0.12
            out.setdefault(lv["level"], []).append(
                (f"{w['room']} ({x:g}, {y:g})", [(px, py, lv["floor_y"] + hh) for hh in (sill + 0.1, (sill + top) / 2, top - 0.1)]))
        for rf in lv.get("roofs", []):
            for x, y in rf.get("windows", []):
                nx = -1 if float(x) == float(rf["rect"][0]) else 1
                base = lv["floor_y"] + float(g["knee_h_m"]) + float(g["gable_window_sill_m"])
                pts = [(float(x) + nx * 0.12, float(y), base + f * float(g["gable_window_h_m"])) for f in (0.1, 0.5, 0.9)]
                out.setdefault(lv["level"], []).append((f"gable ({x:g}, {y:g})", pts))
    return out


def lookout(z: dict, data: dict) -> list[dict]:
    """Per eye: the share of each fence opening's sample points in view, the house's windows (ground and upper
    floors, basement) and the attic's windows in view. Blockers: the parapet's cap, the deck's slab, the attic (up to
    its roof line), the roof's items and chimneys."""
    fy = float(_level(data, "roof")["floor_y"])
    dx0, dy0, dw, dd = (float(v) for v in z["rect"])
    ax0, ay0, aw, ad = (float(v) for v in z["hole"])
    cap = fy + float(data["spec"]["grid"]["parapet_h_m"]) + 0.06
    slab = float(data["spec"]["grid"]["roof_slab_m"])
    attic = load("attic") if (DRESSING / "attic.toml").is_file() else {"rect": z["hole"], "eave_h": 2.2}
    sol = solids(z, data)

    def blocked(p) -> bool:
        x, y, h = p
        inside = dx0 - PARAPET_HALF <= x <= dx0 + dw + PARAPET_HALF and dy0 - PARAPET_HALF <= y <= dy0 + dd + PARAPET_HALF
        if inside:
            edge = min(abs(x - dx0), abs(x - dx0 - dw), abs(y - dy0), abs(y - dy0 - dd))
            if edge <= PARAPET_HALF and fy - slab <= h < cap:
                return True
            if fy - slab <= h < fy:
                return True
        if ax0 - WALL_HALF <= x <= ax0 + aw + WALL_HALF and ay0 - WALL_HALF <= y <= ay0 + ad + WALL_HALF:
            if fy <= h < fy + roof_line({**attic, "rect": z["hole"]}, data, y) + 0.2:
                return True
        return any(fy <= h < fy + s["h"] and _near(x, y, s["poly"], 0.0) for s in sol)

    def visible(eye, t) -> bool:
        n = max(1, int(math.dist(eye, t) / 0.05))
        return not any(blocked([eye[i] + (t[i] - eye[i]) * k / n for i in range(3)]) for k in range(1, n))

    targets = _targets(z["lookout"]["see"])
    wins = _windows(data)
    out = []
    for ex, ey in z["lookout"]["eyes"]:
        eye = (float(ex), float(ey), fy + EYE_M)
        see = {k: sum(visible(eye, t) for t in pts) / len(pts) for k, pts in targets.items()}
        seen = {lv: [lab for lab, pts in ws if any(visible(eye, p) for p in pts)] for lv, ws in wins.items()}
        out.append({"eye": [float(ex), float(ey)], "see": {k: round(v, 3) for k, v in see.items()},
                    "house_windows": [w for lv in ("basement", "ground", "upper") for w in seen.get(lv, [])],
                    "attic_windows": seen.get("attic", [])})
    return out


def report(data: dict | None = None) -> dict[str, Any]:
    data = data or house_layout.load()
    attic, roof = load("attic"), load("roof")
    return {"attic": {"items": len(attic["items"]), "spots": reach(attic, data), "problems": check(attic, data)},
            "roof": {"items": len(roof["items"]), "lookout": lookout(roof, data), "problems": check(roof, data)}}
