"""The attic's old things and hiding spots and the free roof's stations and lookout (art #77, map #73): the data in
layouts/house/dressing/attic_roof/attic.toml, checked in pure Python (docs/house.md, "The attic and the free roof").

- `load(name)`: a dressing file with every item's footprint (w along its local X, d along Z, h) from the dressing
  library (props/library.toml, #87) or its own `size` (a placeholder for the hero props); its `[roof]` table holds the
  roof's items, the walk's start outside the dormer and the lookout.
- `roof_zone(z, data)`: the roof as a zone of its own: the roof's outline (the footprint and its 0.5 m overhang), its
  items; the dormers and the chimneys stand on it.
- `check(z, data)`: the items inside the floor, off each other and the kept-free rects, under the attic's roof, the
  inventory's counts; every hiding spot reachable for a pick-up; the roof's stations reachable from the dormer.
- `reach(z, data)`: per hiding spot, a point a player (radius PLAYER_R) can walk to from the ladder, within REACH_M of
  the spot in plan and with a clear line of sight from the eye (EYE_M) to it.
- `lookout(rz, data)`: from each lookout eye on the roof, the share of the plot's fence openings in view, and which
  windows of the house can be seen (the design doc: "the roof sees the yard, not inside").
- `roof_top(data, y)`: the roof's top over the attic floor at plan y (where a player on the roof stands).
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
OVERHANG = 0.5  # the roof's eave and verge pieces reach 0.5 m out of the footprint (kits/house.json)
EDGE_M = 0.2  # a player's axis keeps this far inside the roof's outline (the eave is a real edge: a fall)
FLAT_H = 0.1  # lower than this is walked over (rugs, the picture frames' depth is not their height)
STATION_TOL = 0.01  # a roof station's height in the layout against roof_top
CASEMENT_DEG = 80.0  # the dormer's casement, open outward (kit_geom.build_dormer)
# inventory.md section 6: the attic's props (light fixtures: #83a). The roof's: the deck's vents, antenna and water tank
# went with the deck (art #77; the free roof's vent pipes and aerial are kit pieces, its craft); the Loot crate stays.
COUNTS = {
    "attic": {"trunk": 6, "sheeted_furniture": 5, "old_wardrobe": 2, "mannequin": 1, "standing_mirror": 1,
              "rocking_horse": 1, "rolled_carpet": 3, "old_bicycle": 1, "cardboard_box": 10, "crate": 5,
              "picture_frame": 6, "potted_plant": 1, "rug": 2},
    "roof": {"loot_crate": 1},
}
MIN_SPOTS = 10  # the brief: about 12


def _library() -> dict[str, list[float]]:
    with LIBRARY.open("rb") as f:
        return {p["id"]: [float(v) for v in p["size_m"]] for p in tomllib.load(f)["prop"]}


def _items(raw: list[dict], lib: dict) -> list[dict]:
    items = []
    for i, it in enumerate(raw):
        it = dict(it, index=i)
        size = it.get("size") or lib.get(it["id"])
        if size:
            it["w"], it["d"], it["h"] = (float(v) for v in size)
        it.setdefault("yaw", 0.0)
        it.setdefault("src", "library")
        items.append(it)
    return items


def load(name: str, folder: Path = DRESSING) -> dict[str, Any]:
    with (Path(folder) / f"{name}.toml").open("rb") as f:
        z = tomllib.load(f)
    lib = _library()
    z["items"] = _items(z.get("items", []), lib)
    if "roof" in z:
        z["roof"] = dict(z["roof"], items=_items(z["roof"].get("items", []), lib))
    z["name"] = name
    return z


def footprint(it: dict) -> list[tuple[float, float]]:
    return _ccw(rect(it["at"][0], it["at"][1], it["w"], it["d"], it["yaw"]))


def _box(x0, y0, w, d) -> list[tuple[float, float]]:
    return [(x0, y0), (x0 + w, y0), (x0 + w, y0 + d), (x0, y0 + d)]


def _level(data: dict, name: str) -> dict:
    return next(lv for lv in data["levels"] if lv["level"] == name)


def _roof(data: dict) -> dict:
    return _level(data, "attic")["roofs"][0]


def roof_top(data: dict, y: float) -> float:
    """The attic roof's top over the attic floor at plan y: the knee wall, the pitch from the nearer eave wall's line,
    the slab's top (kit_geom.pitch: its underside u under the line r * z, its vertical thickness tv). Past the eave
    (the overhang) it keeps falling."""
    pp = house_layout.kit_geom().pitch(data["spec"])
    _, y0, _, d = (float(v) for v in _roof(data)["rect"])
    a = min(y - y0, y0 + d - y)
    return float(data["spec"]["grid"]["knee_h_m"]) + pp["r"] * a + pp["u"] + pp["tv"]


def _piece_size(data: dict, pid: str) -> tuple[float, float, float]:
    kp = data["pieces"].get(pid, {})
    if "size" in kp:
        s = [float(v) for v in kp["size"]]
        return s[0], s[1], s[2] if len(s) > 2 else 2.0
    w = float(kp.get("width", 1.0))
    return w, float(kp.get("depth", w)), float(kp.get("height", 2.0))


def chimneys(data: dict) -> list[dict]:
    """The attic level's free kit pieces (the chimneys, from their pivot at the north-west corner): each a poly and h
    (its top over the attic floor)."""
    out = []
    for fp in _level(data, "attic").get("pieces", []):
        w, d, h = _piece_size(data, fp["piece"])
        x, y = float(fp["at"][0]), float(fp["at"][2])
        out.append({"poly": _box(x, y, w, d), "h": h, "id": fp["piece"], "index": None})
    return out


def dormers(data: dict) -> list[dict]:
    """Each dormer as planned (house_layout.dormer_cut): its body's plan polygon (the front wall and the cheeks: local
    x 0..W, z 0..L), its top over the attic floor (its ridge), the open casement leaf's plan polygon, the window's
    centre on the front, a point 1 m out of it (plan) and the sill over the attic floor."""
    planned = house_layout.plan(data)
    lv = next(L for L in planned["levels"] if L["level"] == "attic")
    kg = house_layout.kit_geom()
    out = []
    for dm in _level(data, "attic").get("dormers", []):
        pid = dm.get("piece", "dormer_gable")
        dd = kg.dormer_dims(data["pieces"][pid], data["spec"])
        W, L, ww = dd["W"], dd["L"], dd["ww"]
        for p in (p for ps in lv["pieces"].values() for p in ps if p["id"] == pid):
            ax, az = house_layout.axes(p["turn"])

            def world(lx, lz, p=p, ax=ax, az=az):
                return (p["x"] + ax[0] * lx + az[0] * lz, p["y"] + ax[1] * lx + az[1] * lz)
            a = math.radians(CASEMENT_DEG)  # the leaf: from its jamb at local x (W - ww) / 2 out towards local -Z
            hx = (W - ww) / 2
            tip = (hx + ww * math.cos(a), -ww * math.sin(a))
            n = (0.03 * math.sin(a), 0.03 * math.cos(a))
            leaf = [world(hx - n[0], -n[1]), world(tip[0] - n[0], tip[1] - n[1]),
                    world(tip[0] + n[0], tip[1] + n[1]), world(hx + n[0], n[1])]
            out.append({"id": dm["id"], "piece": pid, "body": _ccw([world(0, 0), world(W, 0), world(W, L), world(0, L)]),
                        "leaf": _ccw(leaf), "top": p["h"] + dd["hr"], "window": world(W / 2, 0),
                        "out": world(W / 2, -1.0), "sill": p["h"] + dd["sill"]})
    return out


def roof_zone(z: dict, data: dict) -> dict:
    """The roof as a walkable zone from the attic dressing's [roof] table: the roof's outline, its items, arrive."""
    x, y, w, d = (float(v) for v in _roof(data)["rect"])
    rf = z["roof"]
    return {"room": "roof", "name": "roof", "rect": [x - OVERHANG, y - OVERHANG, w + 2 * OVERHANG, d + 2 * OVERHANG],
            "items": rf["items"], "arrive": rf["arrive"], "lookout": rf.get("lookout"), "clear": rf.get("clear", [])}


def solids(z: dict, data: dict) -> list[dict]:
    """What stands in the way (in the attic or on the roof): the items (not the flat ones), the chimneys and, on the
    roof, the dormers' bodies and open casements. Each: poly, h (its top over the attic floor; a roof item's over the
    roof's top), id, index."""
    out = [{"poly": footprint(it), "h": it["h"], "id": it["id"], "index": it["index"]}
           for it in z["items"] if "w" in it and it["h"] >= FLAT_H]
    out += chimneys(data)
    if z["room"] == "roof":
        for dm in dormers(data):
            out.append({"poly": dm["body"], "h": dm["top"], "id": dm["piece"], "index": None})
            out.append({"poly": dm["leaf"], "h": dm["top"], "id": f"{dm['piece']} casement", "index": None})
    return out


def floor_rect(z: dict) -> tuple[float, float, float, float]:
    """The floor's free rectangle (x0, y0, x1, y1): inside the walls (attic) or the roof's edge (roof)."""
    m = WALL_HALF if z["room"] == "attic" else EDGE_M
    x, y, w, d = (float(v) for v in z["rect"])
    return x + m, y + m, x + w - m, y + d - m


def blocked_rects(z: dict, data: dict) -> list[list[tuple[float, float]]]:
    """Floor nobody stands on: the hatch's hole in the attic."""
    out = []
    if z["room"] == "attic":
        for h in _level(data, "attic").get("holes", []):
            if "tile" in h:
                out.append(_box(float(h["tile"][0]), float(h["tile"][1]), 2.0, 2.0))
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


def _station(data: dict, name: str) -> tuple[float, float, float] | None:
    """A station of the attic room in plan metres and its height over the attic floor (the layout's marker)."""
    room = next(r for r in _level(data, "attic")["rooms"] if r["id"] == "attic")
    s = next((s["at"] for s in room.get("stations", []) if s["name"] == name), None)
    return (room["rect"][0] + float(s[0]), room["rect"][1] + float(s[2]), float(s[1])) if s else None


def _station_problems(data: dict, name: str, at: list[float]) -> list[str]:
    st = _station(data, name)
    if st is None or math.dist(st[:2], at) > 1e-6:
        return [f"the {name} station {list(at)} is not the layout's {name} station"]
    if abs(st[2] - roof_top(data, st[1])) > STATION_TOL:
        return [f"the layout's {name} station stands {st[2]:.3f} m up, the roof's top there is {roof_top(data, st[1]):.3f}"]
    return []


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
        return problems
    # the roof: the walk starts outside a dormer's window; the stations are the layout's and reachable from there
    dms = dormers(data)
    if not any(math.dist(dm["out"], z["arrive"]) <= 0.6 for dm in dms):
        problems.append(f"the roof's walk starts at {z['arrive']}, not outside a dormer's window")
    seen, cell = walkable(z, data)
    if not seen:
        problems.append(f"no roof to stand on at the walk's start {z['arrive']}")
    for it in z["items"]:
        if it.get("station"):
            problems += _station_problems(data, it["station"], it["at"])
            r = max(it["w"], it["d"]) / 2 + 0.8
            if not any(math.dist(cell(*c), it["at"]) <= r for c in seen):
                problems.append(f"the {it['station']} station ({it['id']}) is out of reach from the dormer")
    lk = z.get("lookout")
    if lk:
        if not any(math.dist(cell(*c), lk["station"]) <= 0.5 for c in seen):
            problems.append("the Lookout station's point is out of reach from the dormer")
        problems += _station_problems(data, "Lookout", lk["station"])
        view = lookout(z, data)
        if not view or math.dist(view[0]["eye"], lk["station"]) > 1e-6:
            problems.append("the lookout's station is not its first eye")
        elif not lk.get("open"):  # a shortfall recorded as open for the engineer is reported, not failed
            problems += not_met(z, view)
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
    """Per eye (EYE_M over the roof's top there): the share of each fence opening's sample points in view, the house's
    windows in view (ground and upper floors, basement), an outbuilding's (the garage's, across the yard: reported, as
    from the yard) and the attic's. Blockers (the roof options lab's variant A): the house under the attic floor, the
    attic and its roof as one solid with the 0.5 m overhang, the chimneys, the dormers, the roof's items."""
    fy = float(_level(data, "attic")["floor_y"])
    x0, y0, w, d = (float(v) for v in _roof(data)["rect"])
    blocks = [(s["poly"], fy + s["h"]) for s in chimneys(data)]
    blocks += [(dm["body"], fy + dm["top"]) for dm in dormers(data)]
    blocks += [(footprint(it), fy + roof_top(data, it["at"][1]) + it["h"]) for it in z["items"] if "w" in it]
    boxes = [(min(p[0] for p in b), min(p[1] for p in b), max(p[0] for p in b), max(p[1] for p in b)) for b, _ in blocks]

    def blocked(p) -> bool:
        x, y, h = p
        if x0 - WALL_HALF <= x <= x0 + w + WALL_HALF and y0 - WALL_HALF <= y <= y0 + d + WALL_HALF and h < fy:
            return True  # the house under the attic floor
        if x0 - OVERHANG <= x <= x0 + w + OVERHANG and y0 - OVERHANG <= y <= y0 + d + OVERHANG \
                and fy <= h < fy + roof_top(data, y):
            return True  # the attic and its roof, the overhang included
        return any(h < top and bx[0] <= x <= bx[2] and bx[1] <= y <= bx[3] and _near(x, y, b, 0.0)
                   for (b, top), bx in zip(blocks, boxes))

    def visible(eye, t) -> bool:
        n = max(1, int(math.dist(eye, t) / 0.05))
        return not any(blocked([eye[i] + (t[i] - eye[i]) * k / n for i in range(3)]) for k in range(1, n))

    def on_house(p) -> bool:  # a window in the house's walls (under the roof), not an outbuilding's (the garage)
        return x0 - 0.3 <= p[0] <= x0 + w + 0.3 and y0 - 0.3 <= p[1] <= y0 + d + 0.3

    targets = _targets(z["lookout"]["see"])
    wins = _windows(data)
    out = []
    for ex, ey in z["lookout"]["eyes"]:
        eye = (float(ex), float(ey), fy + roof_top(data, float(ey)) + EYE_M)
        see = {k: sum(visible(eye, t) for t in pts) / len(pts) for k, pts in targets.items()}
        seen = {lv: [(lab, pts[0]) for lab, pts in ws if any(visible(eye, p) for p in pts)] for lv, ws in wins.items()}
        below = [(lab, p) for lv in ("basement", "ground", "upper") for lab, p in seen.get(lv, [])]
        out.append({"eye": [float(ex), float(ey)], "eye_h": round(eye[2], 3), "see": {k: round(v, 3) for k, v in see.items()},
                    "house_windows": [lab for lab, p in below if on_house(p)],
                    "other_windows": [lab for lab, p in below if not on_house(p)],
                    "attic_windows": [lab for lab, _ in seen.get("attic", [])]})
    return out


def not_met(z: dict, view: list[dict]) -> list[str]:
    """The acceptance from the station's eye (the first): every `see` opening at least half in view."""
    own = view[0]
    return [f"the lookout sees {100 * own['see'][t]:.0f} % of the {t} from its station {own['eye']}, less than half"
            for t in z["lookout"]["see"] if own["see"][t] < 0.5]


def report(data: dict | None = None) -> dict[str, Any]:
    data = data or house_layout.load()
    attic = load("attic")
    roof = roof_zone(attic, data)
    view = lookout(roof, data)
    seen, _ = walkable(roof, data)
    dms = [{"id": dm["id"], "window": [round(v, 2) for v in dm["window"]], "sill": round(dm["sill"], 3),
            "roof_top_outside": round(roof_top(data, dm["out"][1]), 3)} for dm in dormers(data)]
    return {"attic": {"items": len(attic["items"]), "spots": reach(attic, data), "problems": check(attic, data)},
            "roof": {"items": len(roof["items"]), "walkable_m2": round(len(seen) * GRID * GRID, 1), "dormers": dms,
                     "lookout": view, "problems": check(roof, data), "not_met": not_met(roof, view),
                     "open": roof["lookout"].get("open", "")}}
