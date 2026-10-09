"""The house layout engine (art #75, docs/house.md): the House map as data (`layouts/house/*.toml`) and a generator
that turns it into Godot scenes built from the House kit (`kits/house.json`).

- `load` reads the settings, the five level files and the kit spec.
- `validate` lists what breaks the grid rules: walls only on whole metres, door and window centres on whole metres,
  no opening within 1 m of a corner or across a wall junction, the storeys' rooms tiling the house footprint, stair
  tops landing on a hole (or a floor edge) at the right height.
- `plan` chooses the pieces: per wall run a door or window module at each opening's centre, then 2 m and 1 m fillers;
  corner fillers at outer corners, caps at free ends; floor tiles round holes; railings; parapets; stairs.
- `write_scenes` writes one `.tscn` per room and per level and `house.tscn`, instancing the kit GLBs by `res://`
  path, with the game's `Doors`, `Stations` and `Markers` Marker3D names.

Coordinates are the design doc's: metres, x east, y south, a rect is [x, y, width, depth] from its north-west corner;
Godot's x = x, z = y. A kit piece runs along its local +X with its exterior at local +Z (docs/kit.md)."""

from __future__ import annotations

import json
import math
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAYOUT_DIR = ROOT / "layouts" / "house"
EPS = 1e-6
KINDS = ("room", "open", "area")
CLIMB = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
FLOOR_TILES = {  # floor role -> pieces by footprint (width x depth)
    "boards": {(2, 2): "floor_boards_2x2", (2, 1): "floor_boards_2x1", (1, 1): "floor_boards_1x1"},
    "lino": {(2, 2): "floor_lino_2x2", (1, 1): "floor_lino_1x1"},
    "concrete": {(2, 2): "floor_concrete_2x2", (1, 1): "floor_concrete_1x1"},
    "roof": {(2, 2): "roof_flat_2x2", (1, 1): "roof_flat_1x1"},
}
OPENING_W = {"door": 2, "glass": 2, "gate8": 8, "window": 2}


# ---------------------------------------------------------------- loading

def load(folder: Path = LAYOUT_DIR) -> dict:
    """The settings of `house.toml`, the levels in order and the kit spec (pieces by id)."""
    folder = Path(folder)
    settings = tomllib.loads((folder / "house.toml").read_text(encoding="utf-8"))
    levels = [tomllib.loads((folder / f"{name}.toml").read_text(encoding="utf-8")) for name in settings["levels"]]
    spec_path = Path(settings["kit_spec"])
    spec = json.loads((spec_path if spec_path.is_absolute() else ROOT / spec_path).read_text(encoding="utf-8"))
    return {"settings": settings, "levels": levels, "spec": spec, "pieces": {p["id"]: p for p in spec["pieces"]}}


def family_of(level: dict, room: dict) -> str:
    if room["kind"] != "room":
        return "none"
    return room.get("walls", level.get("walls", "none"))


def piece_id(family: str, what: str, finish: str = "ext", length: int = 2) -> str | None:
    """The kit piece for a wall family: what is wall, door, window, gate8, glass, corner or end."""
    if family in ("storey", "knee"):
        if what == "wall":
            return f"wall_{family}_{length}m_{finish}"
        if what in ("door", "window"):
            return f"wall_{family}_2m_{what}_{finish}"
        if what == "gate8":
            return "garage_door_8m"
        if what in ("corner", "end"):
            return f"wall_{family}_{what}_{'ext' if family == 'knee' and what == 'end' else finish}"
    if family == "basement":
        return {"wall": f"wall_basement_{length}m", "door": "wall_basement_2m_door", "corner": "wall_basement_corner",
                "end": "wall_basement_end"}.get(what)
    if family == "glass":
        return {"wall": f"glass_wall_{length}m", "glass": "glass_door_2m", "door": "glass_door_2m"}.get(what)
    if family == "parapet":
        return {"wall": f"parapet_{length}m", "corner": "parapet_corner"}.get(what)
    return None


# ---------------------------------------------------------------- geometry helpers

def is_whole(v: float) -> bool:
    return abs(v - round(v)) < EPS


def inside(rect, x: float, y: float) -> bool:
    return rect[0] - EPS <= x <= rect[0] + rect[2] + EPS and rect[1] - EPS <= y <= rect[1] + rect[3] + EPS


def strictly_inside(rect, x: float, y: float) -> bool:
    return rect[0] + EPS < x < rect[0] + rect[2] - EPS and rect[1] + EPS < y < rect[1] + rect[3] - EPS


def overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] - EPS and b[0] < a[0] + a[2] - EPS and a[1] < b[1] + b[3] - EPS and b[1] < a[1] + a[3] - EPS


def turn_for(ext: tuple[int, int]) -> int:
    """The Y rotation (degrees) that turns a piece's local +Z to the doc direction ext (dx, dy)."""
    return {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): -90}[ext]


def axes(turn: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Local +X and +Z as doc (x, y) directions after a Y rotation."""
    t = math.radians(turn)
    return (round(math.cos(t)), round(-math.sin(t))), (round(math.sin(t)), round(math.cos(t)))


def pivot_for(rect, size_x: float, size_z: float, turn: int) -> tuple[float, float]:
    """The pivot that puts a piece's local footprint [0, size_x] x [0, size_z], turned, onto rect's corner."""
    ax, az = axes(turn)
    pts = [(ax[0] * a + az[0] * b, ax[1] * a + az[1] * b) for a in (0, size_x) for b in (0, size_z)]
    return rect[0] - min(p[0] for p in pts), rect[1] - min(p[1] for p in pts)


def quadrant_turn(q: tuple[int, int]) -> int:
    """Corner fillers sit in the local +X+Z quadrant: the turn that moves it to the doc quadrant q."""
    return {(1, 1): 0, (1, -1): 90, (-1, -1): 180, (-1, 1): -90}[q]


# ---------------------------------------------------------------- walls

def wall_edges(level: dict) -> dict:
    """Unit wall edges of a level: key (orient, line, start) -> {class, family, owner, out}. orient 'h' runs along x
    at doc y = line; 'v' along y at x = line. class is ext (one walled room) or int (two); out is the outside."""
    sides: dict = {}
    for room in level["rooms"]:
        fam = family_of(level, room)
        if fam == "none":
            continue
        x, y, w, d = room["rect"]
        for i in range(int(w)):
            sides.setdefault(("h", y, x + i), []).append((room, fam, (0, -1)))  # north side, outside is -y
            sides.setdefault(("h", y + d, x + i), []).append((room, fam, (0, 1)))
        for j in range(int(d)):
            sides.setdefault(("v", x, y + j), []).append((room, fam, (-1, 0)))
            sides.setdefault(("v", x + w, y + j), []).append((room, fam, (1, 0)))
    edges = {}
    for key, owners in sides.items():
        fams = {f for _, f, _ in owners}
        edges[key] = {"class": "ext" if len(owners) == 1 else "int", "family": owners[0][1], "owner": owners[0][0]["id"],
                      "out": owners[0][2] if len(owners) == 1 else None, "rooms": [o[0]["id"] for o in owners],
                      "mixed": len(fams) > 1 or len(owners) > 2}
    return edges


def node_edges(edges: dict) -> dict:
    """Grid node -> the unit directions of the wall edges that leave it."""
    nodes: dict = {}
    for (o, line, s) in edges:
        a, b = ((s, line), (s + 1, line)) if o == "h" else ((line, s), (line, s + 1))
        d = (1, 0) if o == "h" else (0, 1)
        nodes.setdefault(a, set()).add(d)
        nodes.setdefault(b, set()).add((-d[0], -d[1]))
    return nodes


def wall_runs(edges: dict) -> list[dict]:
    """Maximal straight runs of edges with one class, family, owner and outside."""
    runs, seen = [], set()
    for key in sorted(edges, key=lambda k: (k[0], k[1], k[2])):
        if key in seen:
            continue
        o, line, s = key
        e = edges[key]
        sig = (e["class"], e["family"], e["owner"], e["out"])
        end = s
        while (o, line, end + 1) in edges and (lambda f: (f["class"], f["family"], f["owner"], f["out"]))(
                edges[(o, line, end + 1)]) == sig:
            end += 1
        for k in range(s, end + 1):
            seen.add((o, line, k))
        runs.append({"orient": o, "line": line, "a": s, "b": end + 1, "class": e["class"], "family": e["family"],
                     "owner": e["owner"], "out": e["out"]})
    return runs


def openings_of(level: dict) -> list[dict]:
    """Doors (not gaps) and windows as openings: orient, line, centre, width, what."""
    out = []
    for d in level.get("doors", []):
        if d.get("kind", "door") == "gap":
            continue
        out.append({"x": d["at"][0], "y": d["at"][1], "w": OPENING_W[d.get("kind", "door")], "what": d.get("kind", "door"),
                    "src": d})
    for wdw in level.get("windows", []):
        out.append({"x": wdw["at"][0], "y": wdw["at"][1], "w": 2, "what": "window", "src": wdw})
    return out


def locate(op: dict, edges: dict) -> tuple | None:
    """The (orient, line, centre) of an opening: the wall line through its centre that has edges both sides."""
    x, y = op["x"], op["y"]
    if is_whole(y) and ("h", round(y), math.floor(x) - 1) in edges and ("h", round(y), math.floor(x)) in edges:
        return ("h", round(y), x)
    if is_whole(x) and ("v", round(x), math.floor(y) - 1) in edges and ("v", round(x), math.floor(y)) in edges:
        return ("v", round(x), y)
    return None


def fill_run(run: dict, openings: list[dict], junctions: set) -> tuple[list[tuple], list[str]]:
    """Modules (start, length, what) along a run: openings at their centres, then 2 m and 1 m fillers."""
    problems, mods = [], []
    ops = sorted(openings, key=lambda o: o["c"])
    for op in ops:
        a, b = op["c"] - op["w"] / 2, op["c"] + op["w"] / 2
        where = f"{op['what']} at {op['src']['at']}"
        if not is_whole(op["c"]):
            problems.append(f"{where}: the centre is not on a whole metre")
            continue
        if a < run["a"] - EPS or b > run["b"] + EPS:
            problems.append(f"{where}: within {op['w'] / 2:g} m of a corner or wall end (run {run['a']}..{run['b']})")
            continue
        if any(a + EPS < j < b - EPS for j in junctions):
            problems.append(f"{where}: a wall meets the opening's module")
            continue
        if mods and a < mods[-1][0] + mods[-1][1] - EPS:
            problems.append(f"{where}: overlaps the previous opening")
            continue
        mods.append((a, op["w"], op["what"]))
    out, pos = [], run["a"]
    for m in mods + [(run["b"], 0, None)]:
        gap = m[0] - pos
        while gap > EPS:
            step = 2 if gap >= 2 - EPS else 1
            out.append((pos, step, "wall"))
            pos += step
            gap -= step
        if m[2]:
            out.append(m)
        pos = m[0] + m[1]
    return out, problems


# ---------------------------------------------------------------- the plan

def level_rooms(level: dict) -> dict:
    return {r["id"]: r for r in level["rooms"]}


def plan(data: dict) -> dict:
    """Every piece instance per level and room ({id, x, y, h, turn} in doc coordinates, h above the level's floor)
    and the problems found while choosing them."""
    problems: list[str] = []
    out = {"levels": []}
    by_height: dict = {}
    for lv in data["levels"]:
        by_height.setdefault(round(lv["floor_y"], 3), []).append(lv)
    for lv in data["levels"]:
        pieces = {r["id"]: [] for r in lv["rooms"]}
        extra = []  # pieces of the level scene itself (stairs, railings), absolute heights
        markers = {r["id"]: [] for r in lv["rooms"]}
        edges = wall_edges(lv)
        for k, e in edges.items():
            if e["mixed"]:
                problems.append(f"{lv['level']}: the wall at {k} joins rooms of different wall families or more than two")
        nodes = node_edges(edges)
        ops = []
        for op in openings_of(lv):
            loc = locate(op, edges)
            if loc is None:
                problems.append(f"{lv['level']}: {op['what']} at {op['src']['at']} is not on a wall")
                continue
            ops.append({**op, "orient": loc[0], "line": loc[1], "c": loc[2]})
        for run in wall_runs(edges):
            o, line = run["orient"], run["line"]
            junc = {(n[0] if o == "h" else n[1]) for n, ds in nodes.items()
                    if (n[1] == line if o == "h" else n[0] == line) and any((d[1] if o == "h" else d[0]) for d in ds)}
            mine = [op for op in ops if op["orient"] == o and op["line"] == line and run["a"] <= op["c"] <= run["b"]
                    and not (op["c"] - op["w"] / 2 >= run["b"] - EPS or op["c"] + op["w"] / 2 <= run["a"] + EPS)]
            for op in mine:
                if op["what"] == "window" and run["class"] != "ext":
                    problems.append(f"{lv['level']}: the window at {op['src']['at']} is on an interior wall")
                if op["what"] == "window" and op["src"]["room"] != run["owner"] and run["class"] == "ext":
                    problems.append(f"{lv['level']}: the window at {op['src']['at']} is on {run['owner']}'s wall")
                op["used"] = True
            mods, probs = fill_run(run, mine, junc)
            problems += [f"{lv['level']}: {p}" for p in probs]
            ext = run["out"] or ((0, 1) if o == "h" else (1, 0))
            turn = turn_for(ext)
            ax, _ = axes(turn)
            fin = run["class"]
            for start, length, what in mods:
                pid = piece_id(run["family"], what, fin, int(length))
                if pid is None or pid not in data["pieces"]:
                    problems.append(f"{lv['level']}: no kit piece for a {length:g} m {what} in the {run['family']} family")
                    continue
                along = (1, 0) if o == "h" else (0, 1)
                forward = (ax[0] * along[0] + ax[1] * along[1]) > 0
                s = start if forward else start + length
                x, y = (s, line) if o == "h" else (line, s)
                pieces[run["owner"]].append({"id": pid, "x": x, "y": y, "h": 0.0, "turn": turn})
        for op in ops:
            if not op.get("used"):
                problems.append(f"{lv['level']}: {op['what']} at {op['src']['at']} is on no wall run")
        # corner fillers and free-end caps
        for n, ds in sorted(nodes.items()):
            fam_edges = [edges[_edge_from(n, d)] for d in ds]
            fam = fam_edges[0]["family"]
            owner = fam_edges[0]["owner"]
            if len(ds) == 2:
                d1, d2 = sorted(ds)
                if d1[0] * d2[0] + d1[1] * d2[1] != 0:
                    continue
                q = (-(d1[0] + d2[0]), -(d1[1] + d2[1]))
                probe = (n[0] + 0.25 * q[0], n[1] + 0.25 * q[1])
                walled = [r for r in lv["rooms"] if family_of(lv, r) != "none" and strictly_inside(r["rect"], *probe)]
                pid = piece_id(fam, "corner", "int" if walled else "ext")
                if pid and pid in data["pieces"]:
                    pieces[owner].append({"id": pid, "x": n[0], "y": n[1], "h": 0.0, "turn": quadrant_turn(q)})
            elif len(ds) == 1:
                (d,) = ds
                e = fam_edges[0]
                pid = piece_id(fam, "end", e["class"])
                if pid and pid in data["pieces"]:  # the cap closes a run that starts at the node going along d
                    pieces[owner].append({"id": pid, "x": n[0], "y": n[1], "h": 0.0, "turn": _turn_x(d)})
        # floors
        rooms = level_rooms(lv)
        holes = lv.get("holes", [])
        for room in lv["rooms"]:
            role = room.get("floor")
            if not role or room["kind"] == "area":
                continue
            if role not in FLOOR_TILES:
                problems.append(f"{lv['level']}: {room['id']} has an unknown floor {role}")
                continue
            blocked = set()
            for h in holes:
                r = h.get("rect") or _tile_rect(h, data)
                blocked |= _cells(r)
                if "tile" in h and inside(room["rect"], h["tile"][0] + 1, h["tile"][1] + 1):
                    pieces[room["id"]].append({"id": h["piece"], "x": h["tile"][0], "y": h["tile"][1], "h": 0.0, "turn": 0})
            if room["kind"] == "open":
                for other in by_height[round(lv["floor_y"], 3)]:
                    for r2 in other["rooms"]:
                        if r2 is not room and r2["kind"] == "room" and r2.get("floor"):
                            blocked |= _cells(r2["rect"])
            for t in tile_floor(room["rect"], blocked, FLOOR_TILES[role]):
                pieces[room["id"]].append(t)
        # railings: open rooms' free edges, holes' free edges
        wall_cells = {(k[0], k[1], k[2]) for k in edges}
        gaps = [d for d in lv.get("doors", []) if d.get("kind") == "gap"]
        for st in _all_stairs(data):
            rise = float(data["pieces"].get(st["piece"], {}).get("rise", 0))
            if abs(st["y"] + rise - lv["floor_y"]) < 1e-3:
                gaps.append({"at": None, "edge": stair_top_edge(st)})
        for room in lv["rooms"]:
            kind = room.get("railing")
            if room["kind"] == "open" and kind:
                extra += edge_rail(room["rect"], kind, wall_cells, gaps, lv["floor_y"], outward=True)
        for h in holes:
            if h.get("railing") and h.get("rect"):
                extra += edge_rail(h["rect"], "balcony", wall_cells, gaps, lv["floor_y"], outward=False)
        for st in lv.get("stairs", []):
            parts = st.get("below", [])
            for i, part in enumerate(parts + [st]):
                p = data["pieces"].get(part["piece"])
                if p is None:
                    problems.append(f"{lv['level']}: no kit piece {part['piece']}")
                    continue
                name = st["id"] if i == len(parts) else f"{st['id']}_{i + 1}"
                r = part["rect"]
                if p["type"] == "block":  # a landing: its long side along the rect's long side, top at y + height
                    turn = 0 if r[2] >= r[3] else _turn_x((0, 1))
                    x, y = pivot_for(r, float(p["size"][0]), float(p["size"][1]), turn)
                else:
                    turn = _turn_x(CLIMB[part["climb"]])
                    run, width = (1.38, 0.7) if p["type"] == "ladder" else (float(p["run"]), float(p["width"]))
                    x, y = pivot_for(r, run, width, turn)
                # A block is a floor piece: its top at the pivot (docs/kit.md), so it stands on y with its top at y + height.
                h = part["y"] + float(p["height"]) if p["type"] == "block" else part["y"]
                extra.append({"id": part["piece"], "x": x, "y": y, "h": h, "turn": turn, "name": name})
        for d in lv.get("doors", []):
            for rid, nm in d.get("names", {}).items():
                if rid in rooms:
                    markers[rid].append({"name": nm, "x": d["at"][0], "y": d["at"][1], "leaf": d.get("leaf", "none")})
        out["levels"].append({"level": lv["level"], "node": lv["node"], "floor_y": lv["floor_y"], "pieces": pieces,
                              "extra": extra, "doors": markers})
    return {**out, "problems": problems}


def _edge_from(n, d):
    if d[1] == 0:
        return ("h", n[1], n[0] if d[0] > 0 else n[0] - 1)
    return ("v", n[0], n[1] if d[1] > 0 else n[1] - 1)


def _turn_x(d) -> int:
    """The turn that points local +X along the doc direction d."""
    return {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): -90}[tuple(d)]


def _cells(rect) -> set:
    x, y, w, d = rect
    return {(i, j) for i in range(math.floor(x + EPS), math.ceil(x + w - EPS))
            for j in range(math.floor(y + EPS), math.ceil(y + d - EPS))}


def _tile_rect(h: dict, data: dict):
    return [h["tile"][0], h["tile"][1], 2, 2]


def hatch_hole(h: dict, data: dict):
    hx, hz, hw, hd = data["pieces"][h["piece"]]["hole"]
    return [h["tile"][0] + hx, h["tile"][1] + hz, hw, hd]


def tile_floor(rect, blocked: set, sizes: dict) -> list[dict]:
    """Greedy floor tiles on the room's 2 m grid (from its north-west corner): 2 x 2, then 2 x 1 both ways, then
    1 x 1, never on a blocked cell."""
    x0, y0, w, d = (int(v) for v in rect)
    free = {(i, j) for i in range(x0, x0 + w) for j in range(y0, y0 + d)} - blocked
    tiles = []
    shapes = [((2, 2), 0), ((2, 1), 0), ((1, 2), -90), ((1, 1), 0)]
    for (sw, sd), turn in shapes:
        pid = sizes.get((max(sw, sd), min(sw, sd)) if turn else (sw, sd))
        if pid is None:
            continue
        for j in range(y0, y0 + d):
            for i in range(x0, x0 + w):
                if (sw == 2 and (i - x0) % 2) or (sd == 2 and (j - y0) % 2):
                    continue
                cells = {(i + a, j + b) for a in range(sw) for b in range(sd)}
                if cells <= free:
                    free -= cells
                    px, py = pivot_for([i, j, sw, sd], max(sw, sd) if turn else sw, min(sw, sd) if turn else sd, turn)
                    tiles.append({"id": pid, "x": px, "y": py, "h": 0.0, "turn": turn})
    return tiles


def _all_stairs(data: dict) -> list[dict]:
    return [st for lv in data["levels"] for st in lv.get("stairs", [])]


def stair_top_edge(st: dict) -> tuple:
    """The top edge of a flight as (orient, line, a, b)."""
    x, y, w, d = st["rect"]
    return {"N": ("h", y, x, x + w), "S": ("h", y + d, x, x + w),
            "W": ("v", x, y, y + d), "E": ("v", x + w, y, y + d)}[st["climb"]]


def edge_rail(rect, kind: str, wall_cells: set, gaps: list, floor_y: float, outward: bool) -> list[dict]:
    """Railing (or parapet) modules along a rect's edges that have no wall, leaving gaps at stair tops and gap doors."""
    x, y, w, d = (int(v) for v in rect)
    sides = [("h", y, x, x + w, (0, -1)), ("h", y + d, x, x + w, (0, 1)), ("v", x, y, y + d, (-1, 0)),
             ("v", x + w, y, y + d, (1, 0))]
    out = []
    for o, line, a, b, outdir in sides:
        free = []
        for s in range(a, b):
            if (o, line, s) in wall_cells:
                continue
            mid = s + 0.5
            gap = False
            for g in gaps:
                if g.get("edge"):
                    go, gl, ga, gb = g["edge"]
                    gap |= go == o and abs(gl - line) < EPS and ga - EPS <= mid <= gb + EPS
                elif g.get("at"):
                    gx, gy = g["at"]
                    c = gx if o == "h" else gy
                    gap |= abs((gy if o == "h" else gx) - line) < EPS and abs(c - mid) < 1.0
            if not gap:
                free.append(s)
        for seg in _spans(free):
            if kind == "parapet":
                turn = turn_for(outdir if outward else (-outdir[0], -outdir[1]))
            else:
                turn = _turn_x((1, 0) if o == "h" else (0, 1))
            ax, _ = axes(turn)
            along = (1, 0) if o == "h" else (0, 1)
            fwd = ax[0] * along[0] + ax[1] * along[1] > 0
            pos = seg[0]
            while pos < seg[1]:
                step = 2 if seg[1] - pos >= 2 else 1
                s = pos if fwd else pos + step
                px, py = (s, line) if o == "h" else (line, s)
                pid = f"parapet_{step}m" if kind == "parapet" else f"railing_{kind}_{step}m"
                out.append({"id": pid, "x": px, "y": py, "h": floor_y, "turn": turn})
                pos += step
            if kind != "parapet":
                for e in seg:
                    px, py = (e, line) if o == "h" else (line, e)
                    out.append({"id": f"railing_{kind}_post", "x": px, "y": py, "h": floor_y, "turn": 0})
    if kind == "parapet":
        for (cx, cy), q in (((x, y), (-1, -1)), ((x + w, y), (1, -1)), ((x, y + d), (-1, 1)), ((x + w, y + d), (1, 1))):
            out.append({"id": "parapet_corner", "x": cx, "y": cy, "h": floor_y, "turn": quadrant_turn(q)})
    return out


def _spans(cells: list[int]) -> list[tuple[int, int]]:
    spans = []
    for c in sorted(cells):
        if spans and spans[-1][1] == c:
            spans[-1][1] = c + 1
        else:
            spans.append([c, c + 1])
    return [tuple(s) for s in spans]


# ---------------------------------------------------------------- validation

def validate(data: dict) -> list[str]:
    """Problems with the layout's data (empty: it holds)."""
    problems = []
    heights = {}
    ids = set()
    for lv in data["levels"]:
        name = lv["level"]
        heights.setdefault(round(lv["floor_y"], 3), []).append(lv)
        for r in lv["rooms"]:
            if r["id"] in ids:
                problems.append(f"{name}: room id {r['id']} is used twice")
            ids.add(r["id"])
            if r["kind"] not in KINDS:
                problems.append(f"{name}: {r['id']} has an unknown kind {r['kind']}")
            if not all(is_whole(v) for v in r["rect"]) or r["rect"][2] <= 0 or r["rect"][3] <= 0:
                problems.append(f"{name}: {r['id']}'s rect {r['rect']} is not whole metres")
        for d in lv.get("doors", []):
            if not all(is_whole(v) for v in d["at"]):
                problems.append(f"{name}: the door at {d['at']} is not on whole metres")
            if d.get("kind", "door") not in ("door", "glass", "gate8", "gap"):
                problems.append(f"{name}: the door at {d['at']} has an unknown kind {d.get('kind')}")
            if d.get("leaf", "none") not in ("none", "ajar", "kit"):
                problems.append(f"{name}: the door at {d['at']} has an unknown leaf {d.get('leaf')}")
            rooms = level_rooms(lv)
            for rid in d["rooms"]:
                r = rooms.get(rid) or _find_room(data, rid)
                if r is None:
                    problems.append(f"{name}: the door at {d['at']} names no room {rid}")
                elif r["kind"] == "room" and not (inside(r["rect"], *d["at"]) and not strictly_inside(r["rect"], *d["at"])):
                    problems.append(f"{name}: the door at {d['at']} is not on {rid}'s edge")
                elif r["kind"] == "open" and not inside(r["rect"], *d["at"]):
                    problems.append(f"{name}: the door at {d['at']} is not on {rid}'s edge")
        for wdw in lv.get("windows", []):
            if not all(is_whole(v) for v in wdw["at"]):
                problems.append(f"{name}: the window at {wdw['at']} is not on whole metres")
        fp = lv.get("footprint")
        if fp:
            walled = [r for r in lv["rooms"] if r["kind"] == "room" and overlap(r["rect"], fp)]
            area = sum(r["rect"][2] * r["rect"][3] for r in walled)
            if any(not (inside(fp, r["rect"][0], r["rect"][1]) and inside(fp, r["rect"][0] + r["rect"][2], r["rect"][1] + r["rect"][3]))
                   for r in walled) or abs(area - fp[2] * fp[3]) > EPS:
                problems.append(f"{name}: the rooms do not tile the footprint {fp} ({area:g} of {fp[2] * fp[3]:g} m2)")
    for h, lvs in heights.items():
        solid = [r for lv in lvs for r in lv["rooms"] if r["kind"] in ("room", "open")]
        for i, a in enumerate(solid):
            for b in solid[i + 1:]:
                if overlap(a["rect"], b["rect"]) and not ({a["kind"], b["kind"]} == {"room", "open"}):
                    problems.append(f"height {h:g}: {a['id']} and {b['id']} overlap")
    problems += check_stairs(data)
    problems += plan(data)["problems"]
    return problems


def _find_room(data: dict, rid: str):
    for lv in data["levels"]:
        for r in lv["rooms"]:
            if r["id"] == rid:
                return r
    return None


def check_stairs(data: dict) -> list[str]:
    """Each flight's rise ends on a level's floor, and its top edge lies on a hole's edge (with the hole over the top
    of the flight) or on the edge of a floor at that height that the flight stays outside of."""
    problems = []
    for lv in data["levels"]:
        for st in lv.get("stairs", []):
            p = data["pieces"].get(st["piece"])
            if p is None:
                continue
            top = round(st["y"] + float(p["rise"]), 3)
            tops = [L for L in data["levels"] if abs(L["floor_y"] - top) < 1e-3]
            if not tops:
                problems.append(f"{st['id']}: its top ({top:g} m) is at no level's floor")
                continue
            o, line, a, b = stair_top_edge(st)
            ok = False
            for L in tops:
                for h in L.get("holes", []):
                    r = h.get("rect") or hatch_hole(h, data)
                    on = _on_edge(r, o, line, a, b)
                    ok |= on and _strip_inside(st, r)
                for r in L["rooms"]:
                    if r["kind"] in ("room", "open") and r.get("floor") and _on_edge(r["rect"], o, line, a, b) \
                            and not overlap(st["rect"], r["rect"]):
                        ok = True
            if not ok:
                problems.append(f"{st['id']}: its top edge {o} {line:g} {a:g}..{b:g} lands on no hole or floor edge at {top:g} m")
    return problems


def _on_edge(r, o, line, a, b) -> bool:
    x, y, w, d = r
    if o == "h":
        return (abs(line - y) < EPS or abs(line - y - d) < EPS) and x - EPS <= a and b <= x + w + EPS
    return (abs(line - x) < EPS or abs(line - x - w) < EPS) and y - EPS <= a and b <= y + d + EPS


def _strip_inside(st: dict, r) -> bool:
    """The flight's top metre (or its whole length if shorter) lies under the hole."""
    x, y, w, d = st["rect"]
    k = min(1.0, d if st["climb"] in "NS" else w)
    strip = {"N": [x, y, w, k], "S": [x, y + d - k, w, k], "W": [x, y, k, d], "E": [x + w - k, y, k, d]}[st["climb"]]
    return inside(r, strip[0], strip[1]) and inside(r, strip[0] + strip[2], strip[1] + strip[3])


# ---------------------------------------------------------------- scenes

def _tf(turn: int, x: float, h: float, z: float) -> str:
    """A scene transform: Godot's text format lists the basis by rows (x.x, y.x, z.x, x.y, ...), then the origin."""
    ax, az = axes(turn)
    v = [ax[0], 0, az[0], 0, 1, 0, ax[1], 0, az[1], x, h, z]
    return "Transform3D(" + ", ".join(_num(n) for n in v) + ")"


def _num(n: float) -> str:
    n = round(float(n), 4)
    return str(int(n)) if n == int(n) else f"{n:g}"


class _Scene:
    def __init__(self, root: str):
        self.ext: dict[str, str] = {}
        self.nodes: list[str] = [f'[node name="{root}" type="Node3D"]']

    def res(self, path: str) -> str:
        if path not in self.ext:
            self.ext[path] = str(len(self.ext) + 1)
        return self.ext[path]

    def group(self, name: str, parent: str = ".") -> None:
        self.nodes.append(f'[node name="{name}" type="Node3D" parent="{parent}"]')

    def instance(self, name: str, parent: str, path: str, transform: str) -> None:
        self.nodes.append(f'[node name="{name}" parent="{parent}" instance=ExtResource("{self.res(path)}")]\n'
                          f"transform = {transform}")

    def marker(self, name: str, parent: str, x: float, h: float, z: float, group: str | None = None,
               meta: dict | None = None) -> None:
        g = f' groups=["{group}"]' if group else ""
        lines = [f'[node name="{name}" type="Marker3D" parent="{parent}"{g}]',
                 f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {_num(x)}, {_num(h)}, {_num(z)})"]
        for k, v in (meta or {}).items():
            lines.append(f"metadata/{k} = {json.dumps(v)}")
        self.nodes.append("\n".join(lines))

    def text(self) -> str:
        head = ["[gd_scene format=3]", ""]
        for path, rid in self.ext.items():
            head.append(f'[ext_resource type="PackedScene" path="{path}" id="{rid}"]')
        return "\n".join(head + [""] + [n + "\n" for n in self.nodes])


def write_scenes(data: dict, planned: dict, out: Path) -> dict:
    """One .tscn per room and level, and house.tscn, into out (the scene_res folder's files). Returns a summary."""
    st = data["settings"]
    kit_res, scene_res = st["kit_res"], st["scene_res"].rstrip("/")
    out = Path(out)
    summary = {"levels": {}, "instances": 0, "pieces": {}}
    house = _Scene("House")
    for lv, pl in zip(data["levels"], planned["levels"]):
        name = lv["level"]
        (out / name).mkdir(parents=True, exist_ok=True)
        level = _Scene(lv["node"] if name != "roof" else "RoofDeck")
        level.group("Rooms")
        count = 0
        for room in lv["rooms"]:
            rx, ry = room["rect"][0], room["rect"][1]
            sc = _Scene(room["node"])
            sc.group("Shell")
            seen: dict = {}
            for p in pl["pieces"][room["id"]]:
                seen[p["id"]] = seen.get(p["id"], 0) + 1
                sc.instance(f"{p['id']}_{seen[p['id']]}", "Shell", kit_res.format(id=p["id"]),
                            _tf(p["turn"], p["x"] - rx, p["h"], p["y"] - ry))
                summary["pieces"][p["id"]] = summary["pieces"].get(p["id"], 0) + 1
            count += len(pl["pieces"][room["id"]])
            sc.group("Doors")
            for dm in pl["doors"][room["id"]]:
                sc.marker(dm["name"], "Doors", dm["x"] - rx, 0, dm["y"] - ry,
                          meta={"leaf": dm["leaf"]} if dm["leaf"] != "none" else None)
            sc.group("Stations")
            for s in room.get("stations", []):
                sc.marker(s["name"], "Stations", *s["at"])
            sc.group("Markers")
            for m in room.get("markers", []):
                sc.marker(m["name"], "Markers", *m["at"], group=m.get("group"))
            phs = [p for p in lv.get("placeholders", []) if p.get("room") == room["id"]]
            if phs:
                sc.group("Placeholders")
                for p in phs:
                    sc.marker(p["name"], "Placeholders", p["at"][0] - rx, p["at"][1], p["at"][2] - ry, meta={"note": p["note"], **({"size": p["size"]} if "size" in p else {})})
            (out / name / f"{room['id']}.tscn").write_text(sc.text(), encoding="utf-8", newline="\n")
            level.instance(room["node"], "Rooms", f"{scene_res}/{name}/{room['id']}.tscn",
                           _tf(0, rx, lv["floor_y"], ry))
        level.group("Stairs")
        level.group("Railings")
        seen = {}
        for p in pl["extra"]:
            seen[p["id"]] = seen.get(p["id"], 0) + 1
            parent = "Stairs" if "name" in p else "Railings"
            level.instance(p.get("name", f"{p['id']}_{seen[p['id']]}"), parent, kit_res.format(id=p["id"]),
                           _tf(p["turn"], p["x"], p["h"], p["y"]))
            summary["pieces"][p["id"]] = summary["pieces"].get(p["id"], 0) + 1
        count += len(pl["extra"])
        (out / f"{name}.tscn").write_text(level.text(), encoding="utf-8", newline="\n")
        house.instance(level.nodes[0].split('"')[1], ".", f"{scene_res}/{name}.tscn", _tf(0, 0, 0, 0))
        summary["levels"][name] = {"rooms": len(lv["rooms"]), "instances": count}
        summary["instances"] += count
    (out / "house.tscn").write_text(house.text(), encoding="utf-8", newline="\n")
    return summary


# ---------------------------------------------------------------- the walk (godot/house/walk.gd)

WALK_LEVELS = ("ground", "upper")  # the storeys whose doors the capsule walks (#75a); stairs are walked on every level
DOOR_KINDS = ("door", "glass", "gate8")
STAIR_PIECES = ("stairs_main", "stairs_basement", "stairs_balcony", "stairs_outdoor_half")
TURN_IN = 0.2  # metres onto a U-turn's landing past a flight's top (or before the next one's foot)
WALK_SIDE = 1.0  # metres either side of a doorway's wall line


def _floored(level: dict, x: float, y: float):
    """The room with a floor (not an area) whose rect holds (x, y), or None."""
    for r in level["rooms"]:
        if r.get("floor") and strictly_inside(r["rect"], x, y):
            return r
    return None


def _door_normal(d: dict, level: dict) -> tuple[float, float]:
    """The unit step from the door's first room into its second, across the wall line through the door's centre."""
    x, y = d["at"]
    rooms = {r["id"]: r for r in level["rooms"]}
    rx, ry, w, h = rooms[d["rooms"][0]]["rect"]
    if abs(y - ry) < EPS and rx < x < rx + w:
        return (0.0, -1.0)
    if abs(y - (ry + h)) < EPS and rx < x < rx + w:
        return (0.0, 1.0)
    if abs(x - rx) < EPS and ry < y < ry + h:
        return (-1.0, 0.0)
    if abs(x - (rx + w)) < EPS and ry < y < ry + h:
        return (1.0, 0.0)
    raise ValueError(f"door {d['rooms']} at {d['at']} is not on {d['rooms'][0]}'s rect")


def walk_request(data: dict, levels=WALK_LEVELS) -> dict:
    """What godot/house/walk.gd walks and labels: one walk across every open doorway of the given levels (from its first
    room into its second, WALK_SIDE each side, in Godot's x, height, z), up and down every flight of stairs, a pad
    under every end that has no floor (the yard), the rooms with their titles for the top-down plan, and the doors left
    out because their kit piece holds a closed leaf (`leaf = "kit"`)."""
    by_name = {lv["level"]: lv for lv in data["levels"]}
    walks, pads, closed = [], [], []

    def end(level: dict, x: float, y: float) -> list[float]:
        if _floored(level, x, y) is None:
            pads.append([x, level["floor_y"], y])
        return [x, level["floor_y"], y]

    for name in levels:
        lv = by_name[name]
        for d in lv.get("doors", []):
            if d.get("kind", "door") not in DOOR_KINDS:
                continue
            if d.get("leaf") == "kit":  # the piece carries its own closed leaf (garage gate, greenhouse door)
                closed.append(f"{name}:{d['rooms'][0]}>{d['rooms'][1]}@{d['at'][0]:g},{d['at'][1]:g}")
                continue
            nx, ny = _door_normal(d, lv)
            x, y = d["at"]
            walks.append({"name": f"{name}:{d['rooms'][0]}>{d['rooms'][1]}@{x:g},{y:g}", "kind": d.get("kind", "door"),
                          "points": [end(lv, x - nx * WALK_SIDE, y - ny * WALK_SIDE),
                                     end(lv, x + nx * WALK_SIDE, y + ny * WALK_SIDE)]})
    for lv in data["levels"]:
        for st in lv.get("stairs", []):
            if st["piece"] not in STAIR_PIECES:
                continue
            rise = data["pieces"][st["piece"]]["rise"]
            # A U-turn's lower flights (`below`): their foot and top, then onto the landing and to the next foot.
            flights = [f for f in st.get("below", []) if "climb" in f] + [st]
            middle = []
            for i, f in enumerate(flights):
                fdx, fdy = CLIMB[f["climb"]]
                frx, fry, fw, fh = f["rect"]
                frun = fh if fdy else fw
                fc = (frx + fw / 2, fry + fh / 2)
                ffoot = (fc[0] - fdx * frun / 2, fc[1] - fdy * frun / 2)
                ftop = (fc[0] + fdx * frun / 2, fc[1] + fdy * frun / 2)
                fr = data["pieces"][f["piece"]]["rise"]
                if i:
                    middle.append([ffoot[0] - fdx * TURN_IN, f["y"], ffoot[1] - fdy * TURN_IN])
                middle.append([ffoot[0], f["y"], ffoot[1]])
                middle.append([ftop[0], f["y"] + fr, ftop[1]])
                if i < len(flights) - 1:
                    middle.append([ftop[0] + fdx * TURN_IN, f["y"] + fr, ftop[1] + fdy * TURN_IN])
            first = flights[0]
            dx, dy = CLIMB[st["climb"]]
            rx, ry, w, h = st["rect"]
            cx, cy = rx + w / 2, ry + h / 2
            run = h if dy else w
            top = (cx + dx * run / 2, cy + dy * run / 2)
            fdx, fdy = CLIMB[first["climb"]]
            foot = (middle[0][0], middle[0][2])
            low = next(v for v in data["levels"] if abs(v["floor_y"] - first["y"]) < EPS)
            high = next(v for v in data["levels"] if abs(v["floor_y"] - (st["y"] + rise)) < EPS)
            room = _floored(high, top[0] + dx * 0.05, top[1] + dy * 0.05)
            reach = 1.0
            if room is not None:  # stop short of the far wall: the capsule's radius plus half a wall
                rx2, ry2, w2, h2 = room["rect"]
                far = {(1, 0): rx2 + w2 - top[0], (-1, 0): top[0] - rx2, (0, 1): ry2 + h2 - top[1],
                       (0, -1): top[1] - ry2}[(dx, dy)]
                reach = max(0.1, min(1.0, far - 0.85))
            start = end(low, foot[0] - fdx * WALK_SIDE, foot[1] - fdy * WALK_SIDE)
            finish = end(high, top[0] + dx * reach, top[1] + dy * reach)
            up = [start] + middle + [finish]
            walks.append({"name": f"{st['id']}:up", "kind": "stairs", "points": up})
            walks.append({"name": f"{st['id']}:down", "kind": "stairs", "points": up[::-1]})
    rooms = [{"level": lv["level"], "id": r["id"], "title": r.get("title", r["id"]), "rect": r["rect"],
              "kind": r["kind"], "floor_y": lv["floor_y"]} for lv in data["levels"] for r in lv["rooms"]]
    unique = []
    for p in pads:
        if p not in unique:
            unique.append(p)
    return {"walks": walks, "pads": unique, "rooms": rooms, "closed": closed,
            "levels": {lv["level"]: {"node": lv["node"], "floor_y": lv["floor_y"]} for lv in data["levels"]}}
