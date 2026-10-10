"""The House map's dressing (art #75b, docs/house.md "Dressing"): the props and light fixtures of each room as data
(`layouts/house/dressing/<room>.toml`), their sizes and pivots from the prop catalogues (the task props'
`props/tasks.toml`, #82, and the dressing library's `props/library.toml`, #87), the checks and the scene nodes.

Pure Python. The checks, per room, in room-local metres (x east, z south from the room's north-west corner):
- every id is known (a catalogue entry, or its own `size`), `face` or `yaw` valid, the footprint inside the room's
  wall faces (a wall prop's back on one), no two solid props overlapping;
- no solid prop within 1 m of a station marker unless it is that station's (`station = "<marker>"`), none within
  0.5 m of a spawn marker;
- the capsule (1.36 m wide, the walk's) reaches, on a 0.1 m grid with the props in place, every door, stair foot,
  station and spawn marker that it reaches in the empty room; what the empty room itself blocks is a note.
"""
from __future__ import annotations

import math
import tomllib
from collections import deque
from pathlib import Path

from . import house_layout as hl

FACES = {"S": 0, "E": 90, "N": 180, "W": -90}  # front (+Z) towards: the Y rotation, degrees (house_layout.turn_for)
PIVOTS = ("floor", "wall", "ceiling")
WALL_T = 0.1  # half the kit's wall: a wall's face is 0.1 m off its grid line
DOOR_CLEAR = {"door": 1.4, "glass": 1.4, "gap": 1.4, "gate8": 7.6}  # the opening's clear width
DOOR_HEAD = 2.15
RADIUS = 0.68  # half the walk's capsule (1.36 m)
BODY = (0.3, 1.8)  # a solid prop spanning any of these heights stands in the capsule's way
ENTRY = 0.8  # a door's or stair foot's target: metres from its line into the room
CELL = 0.1
STATION_CLEAR = 1.0
STATION_REACH = 2.0  # a station counts as reached from a capsule centre this close to its marker
SPAWN_CLEAR = 0.5
TOL = 0.02
PIECE_HALF = {"pillar_concrete": 0.2}  # free layout pieces that block the capsule: half their square section (kit v2)


# ---------------------------------------------------------------- loading

def catalogue(paths) -> dict:
    """id -> size [L along X, W along Z, H], pivot, collision, class, spec; later files win. Missing files are skipped."""
    cat: dict = {}
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        for e in data.get("prop", []):  # the dressing library (#87)
            cat[e["id"]] = {"size": list(e["size_m"]), "pivot": e.get("pivot", "floor"),
                            "collision": e.get("collision", "box"), "class": e.get("class", ""), "spec": p.name}
        for e in data.get("props", []):  # the task props (#82): w x d x h, on the floor unless wall-mounted
            if all(k in e for k in ("w", "d", "h")):
                cat[e["id"]] = {"size": [e["w"], e["d"], e["h"]],
                                "pivot": "wall" if e.get("mount") == "wall" else "floor",
                                "collision": "box", "class": e.get("kind", ""), "spec": p.name}
    return cat


def spec_paths(settings: dict, root: Path = hl.ROOT, extra=()) -> list[Path]:
    paths = [Path(s) if Path(s).is_absolute() else root / s for s in settings.get("prop_specs", [])]
    return paths + [Path(e) for e in extra]


def load(folder: Path) -> dict:
    """room id -> the dressing file's data (`props`, `fixtures`), from every <room>.toml in folder."""
    out = {}
    for f in sorted(Path(folder).glob("*.toml")):
        d = tomllib.loads(f.read_text(encoding="utf-8"))
        d["file"] = f.name
        out[d.get("room", f.stem)] = d
    return out


def items(dressing: dict) -> list[tuple[str, dict]]:
    return [("props", it) for it in dressing.get("props", [])] + [("fixtures", it) for it in dressing.get("fixtures", [])]


def resolve(item: dict, cat: dict) -> dict:
    """The item with its size, pivot, collision and yaw filled from the catalogue (the item's own keys win)."""
    spec = cat.get(item["id"], {})
    r = dict(item)
    r["known"] = bool(spec) or "size" in item
    r["size"] = list(item.get("size", spec.get("size", [0.5, 0.5, 0.5])))
    r["pivot"] = item.get("pivot", spec.get("pivot", "floor"))
    r["collision"] = item.get("collision", spec.get("collision", "box"))
    r["yaw"] = float(item["yaw"]) if "yaw" in item else float(FACES.get(item.get("face", "S"), 0))
    return r


# ---------------------------------------------------------------- geometry

def _rot(yaw: float, a: float, b: float) -> tuple[float, float]:
    """Local (x, z) to room (x, z) offsets after a Y rotation (house_layout.axes, unrounded)."""
    t = math.radians(yaw)
    return a * math.cos(t) + b * math.sin(t), -a * math.sin(t) + b * math.cos(t)


def local_box(r: dict) -> tuple[float, float, float, float, float, float]:
    """The prop's local box: x0, x1, y0, y1, z0, z1 about its pivot."""
    L, W, H = r["size"]
    y0, y1 = (-H, 0.0) if r["pivot"] == "ceiling" else (0.0, H)
    z0, z1 = (0.0, W) if r["pivot"] == "wall" else (-W / 2, W / 2)
    return -L / 2, L / 2, y0, y1, z0, z1


def footprint(r: dict) -> tuple[float, float, float, float]:
    """The room-local AABB (x0, z0, x1, z1) of the turned footprint."""
    x0, x1, _, _, z0, z1 = local_box(r)
    pts = [_rot(r["yaw"], a, b) for a in (x0, x1) for b in (z0, z1)]
    x, z = r["at"][0], r["at"][2]
    return (x + min(p[0] for p in pts), z + min(p[1] for p in pts),
            x + max(p[0] for p in pts), z + max(p[1] for p in pts))


def span(r: dict) -> tuple[float, float]:
    _, _, y0, y1, _, _ = local_box(r)
    return r["at"][1] + y0, r["at"][1] + y1


def solid(r: dict) -> bool:
    h0, h1 = span(r)
    return r["collision"] != "none" and h0 < BODY[1] and h1 > BODY[0]


def box_dist(b, x: float, z: float) -> float:
    dx = max(b[0] - x, 0.0, x - b[2])
    dz = max(b[1] - z, 0.0, z - b[3])
    return math.hypot(dx, dz)


def _overlap(a, b, tol=TOL) -> bool:
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


# ---------------------------------------------------------------- the room's shell

def _walled_room(level: dict, x: float, y: float) -> bool:
    return any(r["kind"] == "room" and hl.strictly_inside(r["rect"], x, y) for r in level["rooms"])


def shell(level: dict, room: dict, levels: list[dict]) -> dict:
    """Room-local walls (boxes, door openings cut out), walled edges, doors, holes and stairs of a room."""
    rx, ry, w, d = room["rect"]
    walled_room = room["kind"] == "room"
    # unit segments per edge: (edge, i) walled?
    edges = {"N": (w, lambda i: (rx + i + 0.5, ry - 0.5)), "S": (w, lambda i: (rx + i + 0.5, ry + d + 0.5)),
             "W": (d, lambda i: (rx - 0.5, ry + i + 0.5)), "E": (d, lambda i: (rx + w + 0.5, ry + i + 0.5))}
    doors = []
    for door in level.get("doors", []):
        if room["id"] not in door["rooms"]:
            continue
        x, y = door["at"]
        if y in (ry, ry + d) and rx < x < rx + w:
            side = "N" if y == ry else "S"
        elif x in (rx, rx + w) and ry < y < ry + d:
            side = "W" if x == rx else "E"
        else:
            side = None
        if side:
            doors.append({"side": side, "at": (x - rx, y - ry), "kind": door["kind"],
                          "clear": DOOR_CLEAR.get(door["kind"], 1.4)})
    walls, walled = [], {}
    for side, (n, nb) in edges.items():
        segs = [i for i in range(int(n)) if walled_room or _walled_room(level, *nb(i))]
        walled[side] = len(segs) > 0
        cuts = [(dr["at"][0] if side in "NS" else dr["at"][1], dr["clear"]) for dr in doors if dr["side"] == side]
        for i in segs:
            parts = [(float(i), float(i + 1))]
            for c, cw in cuts:
                parts = [q for a, b in parts for q in ((a, min(b, c - cw / 2)), (max(a, c + cw / 2), b)) if q[1] > q[0]]
            for a, b in parts:
                line = {"N": 0.0, "S": d, "W": 0.0, "E": w}[side]
                walls.append((a, line - WALL_T, b, line + WALL_T) if side in "NS" else (line - WALL_T, a, line + WALL_T, b))
    rect = room["rect"]

    def local(rr):
        return (rr[0] - rx, rr[1] - ry, rr[0] + rr[2] - rx, rr[1] + rr[3] - ry)

    holes = [local(h["rect"]) for h in level.get("holes", []) if "rect" in h and hl.overlap(h["rect"], rect)]
    stairs, feet = [], []
    # free kit pieces that stand in the capsule's way (the basement's pillars, art #78), centred on their `at`
    for fp in level.get("pieces", []):
        half = PIECE_HALF.get(fp["piece"])
        if half and fp.get("room") == room["id"]:
            px, py = fp["at"][0], fp["at"][2]
            stairs.append(local([px - half, py - half, 2 * half, 2 * half]))
    fy = level["floor_y"]
    for lv in levels:
        for st in lv.get("stairs", []):
            for s in [st] + list(st.get("below", [])):
                if not (fy - 0.01 <= s["y"] < fy + 2.0) or not hl.overlap(s["rect"], rect):
                    continue
                stairs.append(local(s["rect"]))
                if s.get("climb") and abs(s["y"] - fy) < 0.01:
                    dx, dy = hl.CLIMB[s["climb"]]
                    sx, sy, sw, sd = s["rect"]
                    fx = sx + sw / 2 - dx * (sw / 2 + ENTRY)
                    fz = sy + sd / 2 - dy * (sd / 2 + ENTRY)
                    if hl.inside(rect, fx, fz):
                        feet.append({"name": f"{st['id']} foot", "at": (fx - rx, fz - ry)})
            # a flight from the level below whose top lands here: its target half a metre past the top edge
            if st.get("climb") and fy - 3.3 < st["y"] < fy - 0.01 and hl.overlap(st["rect"], rect):
                dx, dy = hl.CLIMB[st["climb"]]
                sx, sy, sw, sd = st["rect"]
                tx = sx + sw / 2 + dx * (sw / 2 + 0.5)
                tz = sy + sd / 2 + dy * (sd / 2 + 0.5)
                if hl.inside(rect, tx, tz):
                    feet.append({"name": f"{st['id']} top", "at": (tx - rx, tz - ry)})
    return {"w": w, "d": d, "walls": walls, "walled": walled, "doors": doors, "holes": holes, "stairs": stairs,
            "feet": feet}


# ---------------------------------------------------------------- reachability

def _grid(sh: dict, blocks: list) -> tuple[int, int, list[list[bool]]]:
    nx, nz = int(round(sh["w"] / CELL)), int(round(sh["d"] / CELL))
    free = [[all(box_dist(b, (i + 0.5) * CELL, (j + 0.5) * CELL) >= RADIUS for b in blocks) for j in range(nz)]
            for i in range(nx)]
    return nx, nz, free


def _reach(nx: int, nz: int, free, start: tuple[float, float]) -> set:
    seeds = _near(nx, nz, free, start, 0.15)
    seen, todo = set(seeds), deque(seeds)
    while todo:
        i, j = todo.popleft()
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < nx and 0 <= b < nz and free[a][b] and (a, b) not in seen:
                seen.add((a, b))
                todo.append((a, b))
    return seen


def _near(nx: int, nz: int, free, at, radius: float) -> list[tuple[int, int]]:
    out = []
    for i in range(max(0, int((at[0] - radius) / CELL) - 1), min(nx, int((at[0] + radius) / CELL) + 2)):
        for j in range(max(0, int((at[1] - radius) / CELL) - 1), min(nz, int((at[1] + radius) / CELL) + 2)):
            if free[i][j] and math.hypot((i + 0.5) * CELL - at[0], (j + 0.5) * CELL - at[1]) <= radius:
                out.append((i, j))
    return out


def targets(room: dict, sh: dict) -> list[dict]:
    out = []
    for dr in sh["doors"]:
        x, z = dr["at"]
        nx, nz = {"N": (0, 1), "S": (0, -1), "W": (1, 0), "E": (-1, 0)}[dr["side"]]
        out.append({"name": f"door {dr['side']} ({x:g}, {z:g})", "at": (x + nx * ENTRY, z + nz * ENTRY), "r": 0.15})
    out += [{"name": f["name"], "at": f["at"], "r": 0.15} for f in sh["feet"]]
    out += [{"name": f"station {s['name']}", "at": (s["at"][0], s["at"][2]), "r": STATION_REACH}
            for s in room.get("stations", [])]
    out += [{"name": f"marker {m['name']}", "at": (m["at"][0], m["at"][2]), "r": 1.0}
            for m in room.get("markers", []) if str(m.get("group", "")).startswith("spawn")]
    return out


# ---------------------------------------------------------------- the checks

def check_room(level: dict, room: dict, dressing: dict, cat: dict, levels: list[dict]) -> dict:
    """Problems, notes and counts of one room's dressing (see the module's doc)."""
    where = f"{dressing.get('file', room['id'])}"
    problems, notes = [], []
    sh = shell(level, room, levels)
    w, d = sh["w"], sh["d"]
    res = []
    for kind, it in items(dressing):
        name = f"{where}: {kind} {it.get('id')} at {it.get('at')}"
        if "id" not in it or len(it.get("at", [])) != 3:
            problems.append(f"{name}: needs an id and at = [x, h, z]")
            continue
        r = resolve(it, cat)
        r["kind"] = kind
        if not r["known"]:
            problems.append(f"{name}: unknown prop id (not in the catalogues; give it a size)")
        if "face" in it and it["face"] not in FACES:
            problems.append(f"{name}: face must be one of N, E, S, W")
        if r["pivot"] not in PIVOTS:
            problems.append(f"{name}: pivot must be one of {', '.join(PIVOTS)}")
        fp = footprint(r)
        if not it.get("outside"):
            lo = [WALL_T if sh["walled"][s] else 0.0 for s in "WN"]
            hi = [w - (WALL_T if sh["walled"]["E"] else 0.0), d - (WALL_T if sh["walled"]["S"] else 0.0)]
            if fp[0] < lo[0] - TOL or fp[1] < lo[1] - TOL or fp[2] > hi[0] + TOL or fp[3] > hi[1] + TOL:
                problems.append(f"{name}: outside the room's wall faces ({_fmt(fp)})")
            if r["pivot"] == "wall" and not (abs(fp[0] - lo[0]) < 0.03 or abs(fp[1] - lo[1]) < 0.03
                                             or abs(fp[2] - hi[0]) < 0.03 or abs(fp[3] - hi[1]) < 0.03):
                problems.append(f"{name}: a wall prop whose back is not on a wall face")
        h0, h1 = span(r)
        for dr in sh["doors"]:
            if r["pivot"] == "wall" and h0 < DOOR_HEAD and box_dist(fp, *dr["at"]) < dr["clear"] / 2 - TOL:
                problems.append(f"{name}: on the door opening at {dr['at']}")
        r["fp"] = fp
        res.append(r)
    solids = [r for r in res if solid(r)]
    for i, a in enumerate(solids):
        for b in solids[i + 1:]:
            (a0, a1), (b0, b1) = span(a), span(b)
            if a0 < b1 - TOL and b0 < a1 - TOL and _overlap(a["fp"], b["fp"]):
                problems.append(f"{where}: {a['id']} at {a['at']} overlaps {b['id']} at {b['at']}")
    for s in room.get("stations", []):
        sx, sz = s["at"][0], s["at"][2]
        for r in solids:
            if r.get("station") != s["name"] and box_dist(r["fp"], sx, sz) < STATION_CLEAR - TOL:
                problems.append(f"{where}: {r['id']} at {r['at']} within {STATION_CLEAR:g} m of station {s['name']}")
    stations = {s["name"] for s in room.get("stations", [])}
    waived = set()  # spawn markers the game's greybox puts at a station's own prop
    for m in room.get("markers", []):
        if str(m.get("group", "")).startswith("spawn"):
            for r in solids:
                dist = box_dist(r["fp"], m["at"][0], m["at"][2])
                if dist < SPAWN_CLEAR - TOL:
                    if r.get("station") in stations:
                        waived.add(f"marker {m['name']}")
                    msg = f"{where}: {r['id']} at {r['at']} {dist:.2f} m from spawn marker {m['name']}"
                    (notes if r.get("station") in stations else problems).append(
                        msg + (" (the station's own prop: the game's greybox puts them together)" if r.get("station") in stations else ""))
    # the capsule on the grid: the empty room, then with the props
    base = sh["walls"] + sh["holes"] + sh["stairs"]
    nx, nz, empty = _grid(sh, base)
    _, _, dressed = _grid(sh, base + [r["fp"] for r in solids])
    tg = targets(room, sh)
    reach = {}
    if tg:
        root = tg[0]["at"]
        e_set, d_set = _reach(nx, nz, empty, root), _reach(nx, nz, dressed, root)
        for t in tg:
            e_ok = bool(set(_near(nx, nz, empty, t["at"], t["r"])) & e_set)
            d_ok = bool(set(_near(nx, nz, dressed, t["at"], t["r"])) & d_set)
            reach[t["name"]] = d_ok
            if not e_ok:
                notes.append(f"{where}: {t['name']}: the capsule does not reach it from {tg[0]['name']} even in the empty room (the shell's)")
            elif not d_ok and t["name"] in waived:
                notes.append(f"{where}: {t['name']}: not reached, it is at the station's own prop")
            elif not d_ok:
                problems.append(f"{where}: {t['name']}: the props cut the capsule's path from {tg[0]['name']}")
    placed = [r for r in res if r["kind"] == "props"]
    return {"room": room["id"], "file": where, "props": len(placed), "fixtures": len(res) - len(placed),
            "solid": len(solids), "reach": reach, "problems": problems, "notes": notes, "resolved": res}


def _fmt(b) -> str:
    return ", ".join(f"{v:.2f}" for v in b)


def check(data: dict, dressings: dict, cat: dict) -> dict:
    """Every dressing file against its room: {"rooms": {id: report}, "problems": [...], "notes": [...]}."""
    out = {"rooms": {}, "problems": [], "notes": []}
    found = set()
    for lv in data["levels"]:
        for room in lv["rooms"]:
            if room["id"] in dressings:
                found.add(room["id"])
                rep = check_room(lv, room, dressings[room["id"]], cat, data["levels"])
                out["rooms"][room["id"]] = rep
                out["problems"] += rep["problems"]
                out["notes"] += rep["notes"]
    for rid in sorted(set(dressings) - found):
        out["problems"].append(f"{dressings[rid].get('file', rid)}: no room {rid!r} in the layout")
    return out


# ---------------------------------------------------------------- scene nodes

def tf_yaw(yaw: float, x: float, h: float, z: float) -> str:
    t = math.radians(yaw)
    c, s = math.cos(t), math.sin(t)
    return "Transform3D(" + ", ".join(hl._num(n) for n in (c, 0, s, 0, 1, 0, -s, 0, c, x, h, z)) + ")"


def scene_nodes(sc, resolved: list[dict], res_of) -> list[str]:
    """Adds the Dressing and Fixtures groups to a room scene (house_layout._Scene); res_of(id) is the GLB's res://
    path or None, where a named placeholder box of the prop's size stands in. Returns the placeholder ids."""
    placeholders, seen = [], {}
    for group in ("props", "fixtures"):
        rs = [r for r in resolved if r["kind"] == group]
        if not rs:
            continue
        parent = "Dressing" if group == "props" else "Fixtures"
        sc.group(parent)
        for r in rs:
            seen[r["id"]] = seen.get(r["id"], 0) + 1
            name = f"{r['id']}_{seen[r['id']]}"
            x, h, z = r["at"]
            meta = [f'metadata/prop = "{r["id"]}"'] + ([f'metadata/station = "{r["station"]}"'] if r.get("station") else [])
            path = res_of(r["id"])
            if path:
                sc.nodes.append("\n".join([f'[node name="{name}" parent="{parent}" instance=ExtResource("{sc.res(path)}")]',
                                           f"transform = {tf_yaw(r['yaw'], x, h, z)}"] + meta))
                continue
            placeholders.append(r["id"])
            x0, x1, y0, y1, z0, z1 = local_box(r)
            ox, oz = _rot(r["yaw"], (x0 + x1) / 2, (z0 + z1) / 2)
            L, W, H = r["size"]
            sc.nodes.append("\n".join([
                f'[node name="{name}" type="CSGBox3D" parent="{parent}"]',
                f"transform = {tf_yaw(r['yaw'], x + ox, h + (y0 + y1) / 2, z + oz)}",
                f"size = Vector3({hl._num(L)}, {hl._num(H)}, {hl._num(W)})",
                f"use_collision = {'false' if r['collision'] == 'none' else 'true'}",
                "metadata/placeholder = true"] + meta))
    return placeholders
