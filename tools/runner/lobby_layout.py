"""The lobby hall's layout (art #356, docs/lobby.md): layouts/lobby/hall.toml loaded and checked in plain Python, and
its text plan. Positions are in the game's lobby frame (levels/lobby/lobby.tscn): x east, z south, y up, the floor at
y 0. The ship is art #263's (layouts/ship, its built pieces): its plan (x, y, h) lands at origin + (x, h, y)."""

from __future__ import annotations

import json
import math
import sys
import tomllib
from pathlib import Path
from typing import Any

from . import common

HALL = common.ROOT / "layouts" / "lobby" / "hall.toml"
EPS = 1e-6


def load(path: Path = HALL) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


# --- the hall's shape ----------------------------------------------------------------------------------------------
def arc(layout: dict[str, Any]) -> tuple[float, float]:
    """The window arc's radius and its centre's z: the circle through (x0, zS), (x1, zS) and (0, zS + bulge)."""
    h = layout["hall"]
    half = (h["x1"] - h["x0"]) / 2
    r = (half * half + h["bulge"] ** 2) / (2 * h["bulge"])
    return r, h["zS"] + h["bulge"] - r


def arc_z(layout: dict[str, Any], x: float) -> float:
    r, cz = arc(layout)
    return cz + math.sqrt(max(0.0, r * r - x * x))


def vault_y(layout: dict[str, Any], x: float) -> float:
    """The vault's height over x: a segmental arc across the hall from the walls' top to the apex at x 0."""
    h = layout["hall"]
    half, rise = (h["x1"] - h["x0"]) / 2, h["apex"] - h["wall"]
    rv = (half * half + rise * rise) / (2 * rise)
    return h["apex"] - rv + math.sqrt(max(0.0, rv * rv - x * x))


def mullion_angles(layout: dict[str, Any]) -> list[float]:
    """The mullions' angles from the arc's centre (0 = south), even along the arc's angle (drawing.js plan())."""
    r, _cz = arc(layout)
    a0 = math.asin(layout["hall"]["x1"] / r)
    n = layout["window"]["panes"]
    return [-a0 + 2 * a0 * i / n for i in range(n + 1)]


def in_hall(layout: dict[str, Any], x: float, z: float, margin: float = 0.0) -> bool:
    """Whether (x, z) is on the hall's floor (not the corridor) with margin to every wall and the window."""
    h = layout["hall"]
    if not (h["x0"] + margin <= x <= h["x1"] - margin and z >= h["zN"] + margin):
        return False
    r, cz = arc(layout)
    return z <= h["zS"] - margin or math.hypot(x, z - cz) <= r - margin


def in_corridor(layout: dict[str, Any], x: float, z: float, margin: float = 0.0) -> bool:
    a, h = layout["arch"], layout["hall"]
    return abs(x) <= a["w"] / 2 - margin and h["zN"] - a["depth"] + margin <= z <= h["zN"] + margin


def on_floor(layout: dict[str, Any], x: float, z: float, margin: float = 0.0) -> bool:
    return in_hall(layout, x, z, margin) or in_corridor(layout, x, z, margin)


def pilasters(layout: dict[str, Any]) -> list[tuple[str, float]]:
    h = layout["hall"]
    return [("W", z) for z in h["ribs"]] + [("E", z) for z in h["ribs"]] + [("N", x) for x in h["north_pilasters"]]


def wall_span(layout: dict[str, Any], wall: str) -> tuple[float, float]:
    h = layout["hall"]
    return (h["x0"], h["x1"]) if wall == "N" else (h["zN"], h["zS"])


def door_segment(layout: dict[str, Any], door: list) -> tuple[tuple[float, float], tuple[float, float]]:
    """A door's opening on its wall's inner face as two plan points (x, z)."""
    h, w = layout["hall"], layout["door"]["w"] / 2
    _id, wall, at = door
    if wall == "N":
        return (at - w, h["zN"]), (at + w, h["zN"])
    x = h["x0"] if wall == "W" else h["x1"]
    return (x, at - w), (x, at + w)


# --- the ship ------------------------------------------------------------------------------------------------------
def ship_report(layout: dict[str, Any]) -> dict[str, Any]:
    path = common.raw_dir() / layout["ship"]["pieces_dir"] / "build_report.json"
    return json.loads(path.read_text(encoding="utf-8"))["pieces"]


def ship_layout_data() -> dict[str, Any]:
    from . import ship_layout
    return ship_layout.load()


def hull_outline(name: str) -> list[tuple[float, float]]:
    sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
    import ship_hull_shape  # plain Python (math, tomllib)
    return [(float(x), float(y)) for x, y in ship_hull_shape.outline(name)]


def _hull2d(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The convex hull (Andrew's monotone chain), counter-clockwise."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def footprint(layout: dict[str, Any], outline: list[tuple[float, float]], report: dict[str, Any],
              place: list) -> list[tuple[float, float]]:
    """The ship's footprint in the lobby (x, z), convex: the hull's outline, every placed pod's bounds and the tail
    (the tail piece's bounds aft of the outline, as wide as the pods), moved by the ship's origin."""
    s = layout["ship"]
    pts = list(outline)
    pod_x = []
    for pid, at, _yaw in place:
        if pid in s["pods"]:
            b = report[pid]["bounds"]   # Godot frame (x, h, y) at the piece's origin
            xs = (at[0] + b["min"][0], at[0] + b["max"][0])
            ys = (at[1] + b["min"][2], at[1] + b["max"][2])
            pts += [(x, y) for x in xs for y in ys]
            pod_x += list(xs)
    if s.get("tail") and pod_x:
        b = report[s["tail"]]["bounds"]
        aft = max(y for _x, y in outline)
        if b["max"][2] > aft:
            w = max(abs(x) for x in pod_x)
            pts += [(-w, aft), (w, aft), (-w, b["max"][2]), (w, b["max"][2])]
    ox, oz = s["origin"][0], s["origin"][2]
    return [(x + ox, y + oz) for x, y in _hull2d(pts)]


def ship_place(layout: dict[str, Any], ship: dict[str, Any]) -> list:
    """The ship's placements kept in the lobby (its lanes minus the dropped clearing), plan [x, y, h] as given."""
    s = layout["ship"]
    lanes = {p["id"]: p["lane"] for p in ship["pieces"]}
    return [p for p in ship["place"] if lanes.get(p[0]) in s["lanes"] and p[0] not in s["drop"]]


def ship_numbers(layout: dict[str, Any], fp: list[tuple[float, float]]) -> dict[str, float]:
    north, south = min(z for _x, z in fp), max(z for _x, z in fp)
    return {"nose_z": north, "aft_z": south, "middle_z": (north + south) / 2,
            "half_span": max(abs(x) for x, _z in fp)}


# --- geometry ------------------------------------------------------------------------------------------------------
def _seg_dist(p, a, b) -> float:
    ax, az = b[0] - a[0], b[1] - a[1]
    t = 0.0 if ax == 0 and az == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * az) / (ax * ax + az * az)))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * az)


def _inside(poly, p) -> bool:
    n, hit = len(poly), False
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            hit = not hit
    return hit


def poly_dist(poly, p) -> float:
    """The distance from p to the polygon (0 inside)."""
    if _inside(poly, p):
        return 0.0
    return min(_seg_dist(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def _sample(a, b, step: float = 0.1):
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def wall_gaps(layout: dict[str, Any], fp: list[tuple[float, float]]) -> dict[str, float]:
    """The footprint's least distance to each wall's inner face, the window and each door's opening."""
    h = layout["hall"]
    r, cz = arc(layout)
    edge = [q for i in range(len(fp)) for q in _sample(fp[i], fp[(i + 1) % len(fp)])]
    gaps = {"W": min(x - h["x0"] for x, _z in edge), "E": min(h["x1"] - x for x, _z in edge),
            "N": min(z - h["zN"] for _x, z in edge),
            "window": min(min(h["zS"] - z, r - math.hypot(x, z - cz)) if z <= h["zS"] else r - math.hypot(x, z - cz)
                          for x, z in edge)}
    for d in layout["door"]["doors"]:
        a, b = door_segment(layout, d)
        gaps[d[0]] = min(poly_dist(fp, q) for q in _sample(a, b))
    return gaps


# --- the check -----------------------------------------------------------------------------------------------------
ROLES = ("panel", "frame", "trim", "floor", "accent")


def look_materials(layout: dict[str, Any], scheme: str) -> dict[str, dict[str, Any]]:
    """The scheme's materials by name: sRGB colour (the role's times the lightness), metallic, roughness, emission."""
    look = layout["look"]
    sc = look["schemes"][scheme]
    out = {}
    for name, (role, k, rough, emit) in look["mats"].items():
        metallic = 0.0 if role == "accent" else sc["trim_metallic"] if role == "trim" else sc["metallic"]
        out[name] = {"rgb": [round(min(1.0, c * k), 4) for c in sc[role]], "metallic": metallic, "roughness": rough,
                     "emit": emit}
    return out


def check(layout: dict[str, Any], fp: list[tuple[float, float]] | None = None) -> list[str]:
    """Every rule of docs/lobby.md "The check"; fp: the ship's footprint (footprint(); None skips the ship's rules)."""
    p: list[str] = []
    h, a, dr, fl, win = layout["hall"], layout["arch"], layout["door"], layout["floor"], layout["window"]
    if not (h["x1"] > h["x0"] and h["zS"] > h["zN"] and h["bulge"] > 0):
        p.append("hall: the walls' faces are not a box with a window bulging south")
    r, cz = arc(layout)
    for x, want in ((h["x0"], h["zS"]), (h["x1"], h["zS"]), (0.0, h["zS"] + h["bulge"])):
        if abs(arc_z(layout, x) - want) > 1e-6:
            p.append(f"window: the arc misses ({x}, {want})")
    if not h["apex"] > h["wall"]:
        p.append("vault: the apex is not above the walls")
    if abs(vault_y(layout, h["x0"]) - h["wall"]) > 1e-6 or abs(vault_y(layout, 0.0) - h["apex"]) > 1e-6:
        p.append("vault: its arc does not spring from the walls' top to the apex")
    if not 0 < win["sill"] < win["transom"] < h["wall"]:
        p.append("window: sill, transom and head out of order")
    ids = {q["id"] for q in layout.get("pieces", [])}
    for pid, _at, _yaw in layout.get("place", []):
        if pid not in ids:
            p.append(f"place: no piece {pid!r}")
    if not layout.get("place") or "door" not in ids:
        p.append("pieces: no placements or no door piece")
    # ribs and pilasters
    ribs = h["ribs"]
    if sorted(ribs) != ribs or len(set(ribs)) != len(ribs):
        p.append("ribs: not in order from north to south")
    for z in ribs:
        if not (h["zN"] + h["pilaster_w"] / 2 <= z + EPS and z + h["pilaster_w"] / 2 <= h["zS"] + EPS):
            p.append(f"rib z {z}: its pilasters are not on the side walls")
    for x in h["north_pilasters"]:
        if not (h["x0"] + h["pilaster_w"] / 2 <= x <= h["x1"] - h["pilaster_w"] / 2):
            p.append(f"north pilaster x {x}: not on the north wall")
        if abs(x) - h["pilaster_w"] / 2 < a["w"] / 2 + h["door_clear_m"]:
            p.append(f"north pilaster x {x}: on the arch")
    # the arch and the corridor
    if not (0 < a["w"] < h["x1"] - h["x0"] and 0 < a["h"] < h["wall"] and a["depth"] > 0):
        p.append("arch: its size does not fit the north wall")
    if a["h"] + a["frame"] > h["wall"]:
        p.append("arch: its frame passes the wall's top")
    # doors
    clear, corner = h["door_clear_m"], h["corner_clear_m"]
    pil = pilasters(layout)
    if dr["lamp"] <= dr["h"] or dr["lamp"] + 0.3 > h["wall"]:
        p.append("door: the lamp is not between the door's head and the wall's top")
    if dr["h"] > h["wall"] - 1 or dr["w"] <= 0:
        p.append("door: its size does not fit a wall")
    ids = [d[0] for d in dr["doors"]]
    if len(set(ids)) != len(ids):
        p.append("doors: two doors share an id")
    for did, wall, at in dr["doors"]:
        lo, hi = at - dr["w"] / 2, at + dr["w"] / 2
        if wall not in ("N", "W", "E"):
            p.append(f"{did}: no wall {wall!r} (N, W or E; the south is the window)")
            continue
        s0, s1 = wall_span(layout, wall)
        if lo < s0 + corner - EPS or hi > s1 - corner + EPS:
            p.append(f"{did}: within {corner} m of a corner of the {wall} wall")
        for pw, pat in pil:
            if pw == wall and lo - clear < pat + h["pilaster_w"] / 2 - EPS and hi + clear > pat - h["pilaster_w"] / 2 + EPS:
                p.append(f"{did}: on the pilaster at {pat} (within {clear} m)")
        if wall == "N" and lo - clear < a["w"] / 2 + a["frame"] and hi + clear > -a["w"] / 2 - a["frame"]:
            p.append(f"{did}: on the arch")
        for other, ow, oat in dr["doors"]:
            if other < did and ow == wall and abs(oat - at) < dr["w"] + clear:
                p.append(f"{did}: overlaps {other}")
    # spawns
    for x in fl["spawns_x"]:
        if not in_hall(layout, x, fl["spawns_z"], layout["walk"]["r"]):
            p.append(f"spawn x {x}: not on the hall's floor")
    # walk points and views
    for i, (x, z) in enumerate(layout["walk"]["points"]):
        if not on_floor(layout, x, z, layout["walk"]["r"]):
            p.append(f"walk point {i} ({x}, {z}): not on the floor with the capsule's radius")
        if fp and poly_dist(fp, (x, z)) < layout["walk"]["r"]:
            p.append(f"walk point {i} ({x}, {z}): under the ship")
    for v in layout["review"]["views"] + layout["review"].get("closeups", []):
        eye = v[2]
        if not on_floor(layout, eye[0], eye[2]) or not 0 < eye[1] < h["wall"]:
            p.append(f"view {v[0]}: its eye is not inside the hall")
    names = {v[0] for v in layout["review"]["views"]}
    for g in layout["review"].get("grid", []):
        if g not in names:
            p.append(f"grid: {g} is no view")
    # the Earth (step 3b): one variant switch, textures no larger than 4096 x 2048, every variant's numbers in range
    p += earth_problems(layout, names)
    # the light (step 4): one mood switch, every mood the same keys in range, the rig's spots inside the hall; the video
    p += light_problems(layout, names)
    # the look: one scheme switch, every scheme's role colours in 0..1, every material a role with its numbers
    look = layout["look"]
    if look["scheme"] not in look["schemes"]:
        p.append(f"look: scheme {look['scheme']} is not in [look.schemes]")
    for sid, sc in look["schemes"].items():
        for role in ROLES:
            c = sc.get(role)
            if not isinstance(c, list) or len(c) != 3 or not all(0.0 <= x <= 1.0 for x in c):
                p.append(f"look {sid}: {role} is not an sRGB colour in 0..1")
        for k in ("metallic", "trim_metallic"):
            if not 0.0 <= sc.get(k, -1.0) <= 1.0:
                p.append(f"look {sid}: {k} is not in 0..1")
    for m, v in look["mats"].items():
        if (not m.startswith("lobby_") or len(v) != 4 or v[0] not in ROLES or not 0.0 < v[1] <= 1.5
                or not 0.0 <= v[2] <= 1.0 or not 0.0 <= v[3] <= 5.0):
            p.append(f"look: material {m} {v} (a lobby_ material: [role, lightness 0..1.5, roughness, emission 0..5])")
    # the ship
    if fp:
        n = ship_numbers(layout, fp)
        for x in fl["spawns_x"]:
            d = poly_dist(fp, (x, fl["spawns_z"]))
            if d < fl["spawn_ship_m"] - EPS:
                p.append(f"spawn x {x}: {d:.2f} m from the ship (at least {fl['spawn_ship_m']})")
        for wall, d in wall_gaps(layout, fp).items():
            if d < fl["ship_wall_m"] - EPS:
                p.append(f"ship: {d:.2f} m from {wall} (at least {fl['ship_wall_m']})")
        if fl["ring_r"] < max(math.hypot(x, z - n["middle_z"]) for x, z in fp) - 1.0:
            p.append("ring: the ship reaches more than 1 m past the floor ring")
        if not in_hall(layout, 0.0, n["middle_z"] - fl["ring_r"]) or not in_hall(layout, fl["ring_r"], n["middle_z"]):
            p.append("ring: not on the hall's floor")
    return p


# --- the text plan -------------------------------------------------------------------------------------------------
def ascii_plan(layout: dict[str, Any], fp: list[tuple[float, float]] | None, cell: float = 1.0) -> str:
    """North up, 1 m cells: # wall, | pilaster, W window, D door, A the arch and corridor, S the ship, o the ring,
    s a spawn, . floor."""
    h, a = layout["hall"], layout["arch"]
    n = ship_numbers(layout, fp) if fp else None
    rows = []
    z = h["zN"] - a["depth"] - 1
    zmax = h["zS"] + h["bulge"] + 1
    while z <= zmax + EPS:
        line = []
        x = h["x0"] - 1
        while x <= h["x1"] + 1 + EPS:
            c = " "
            if in_corridor(layout, x, z):
                c = "A"
            elif in_hall(layout, x, z) and in_hall(layout, x, z, 0.5):
                c = "."
                if n and abs(math.hypot(x, z - n["middle_z"]) - layout["floor"]["ring_r"]) < cell / 2:
                    c = "o"
                if fp and poly_dist(fp, (x, z)) == 0.0:
                    c = "S"
                if abs(z - layout["floor"]["spawns_z"]) < cell / 2 and any(abs(x - sx) < cell / 2 for sx in layout["floor"]["spawns_x"]):
                    c = "s"
            elif in_hall(layout, x, z, -0.6):   # the walls' and the window's own cells
                c = "W" if z > h["zS"] else "#"
                for did, wall, at in layout["door"]["doors"]:
                    (x0, z0), (x1, z1) = door_segment(layout, [did, wall, at])
                    if min(x0, x1) - 0.6 <= x <= max(x0, x1) + 0.6 and min(z0, z1) - 0.6 <= z <= max(z0, z1) + 0.6:
                        c = "D"
                for wall, at in pilasters(layout):
                    if (wall == "N" and abs(x - at) < cell / 2 and z < h["zN"] + 0.6) or \
                       (wall != "N" and abs(z - at) < cell / 2 and abs(x) > h["x1"] - 0.6):
                        c = "|" if c == "#" else c
            line.append(c)
            x += cell
        rows.append("".join(line).rstrip())
        z += cell
    head = (f"lobby hall v{layout['version']}: {h['x1'] - h['x0']:.0f} x {h['zS'] - h['zN']:.0f} m, the window arc "
            f"r {arc(layout)[0]:.2f} m; north up, 1 m cells (x {h['x0'] - 1:.0f}..{h['x1'] + 1:.0f})")
    if n:
        head += (f"\nship: nose z {n['nose_z']:.2f}, aft z {n['aft_z']:.2f}, middle z {n['middle_z']:.2f}, "
                 f"half span {n['half_span']:.2f} m")
    return head + "\n" + "\n".join(rows) + "\n"


EARTH_MAX = (4096, 2048)
EARTH_MAPS = ("night", "day", "clouds")


def earth_problems(layout: dict[str, Any], views: set[str]) -> list[str]:
    """[earth]: the variant switch names a variant, the maps are night, day and clouds, the size at most 4096 x 2048,
    the grid's views exist, and each variant's centre, radius, subpoint and sun are angles in range."""
    e = layout.get("earth")
    if e is None:
        return []
    p: list[str] = []
    if e["variant"] not in e["variants"]:
        p.append(f"earth: variant {e['variant']} is not in [earth.variants]")
    if sorted(e["maps"]) != sorted(EARTH_MAPS):
        p.append(f"earth: maps must be {', '.join(EARTH_MAPS)}")
    w, h = e["size"]
    if not (0 < w <= EARTH_MAX[0] and 0 < h <= EARTH_MAX[1] and w == 2 * h):
        p.append(f"earth: size {w} x {h} is not an equirectangular 2:1 of at most {EARTH_MAX[0]} x {EARTH_MAX[1]}")
    for g in e["grid"]:
        if g not in views:
            p.append(f"earth grid: {g} is no view")
    for vid, v in e["variants"].items():
        az, el = v["centre"]
        if not (-180 <= az <= 180 and -90 <= el <= 90):
            p.append(f"earth {vid}: centre {v['centre']} is not [azimuth, elevation] in degrees")
        if not 1.0 <= v["radius_deg"] <= 80.0:
            p.append(f"earth {vid}: radius_deg {v['radius_deg']} is not within 1..80")
        lat, lon = v["subpoint"]
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            p.append(f"earth {vid}: subpoint {v['subpoint']} is not [lat, lon]")
        if not (-180 <= v["sun"][0] <= 180 and -90 <= v["sun"][1] <= 90) or v["sun_energy"] < 0 or v["stars"] < 0:
            p.append(f"earth {vid}: sun, sun_energy or stars out of range")
    return p


LIGHT_KEYS = ("exposure", "ambient_rgb", "ambient_energy", "probe_intensity", "pendant_rgb", "pendant_energy",
              "pendant_range", "pendant_angle", "bulb_emit", "strip_rgb", "strip_energy", "strip_range", "strip_emit",
              "door_rgb", "door_energy", "door_range", "door_emit", "corridor_rgb", "corridor_energy", "corridor_range",
              "earth_rgb", "earth_energy", "earth_dir", "dawn_rgb", "dawn_energy", "dawn_dir", "glow_intensity",
              "glow_bloom", "glow_threshold", "ssao_intensity",
              # step 4b: the glow's HDR scale and luminance cap, the ship's own glow surfaces' emission factor (applied
              # by hall.gd per instance, never in the ship's files), the pendants' upward fill on the vault, the strips'
              # specular and size (longer reflections on the floor), the Earth's soft, lighter shadow, its cold spill
              "glow_hdr_scale", "glow_cap", "ship_emit", "fill_rgb", "fill_energy", "fill_range", "fill_angle",
              "strip_specular", "strip_size", "earth_soft", "earth_shadow", "window_rgb", "window_energy",
              "window_range", "pendant_specular")


def light_problems(layout: dict[str, Any], views: set[str]) -> list[str]:
    """[light]: the mood switch names a mood, every mood has exactly LIGHT_KEYS with colours in 0..1, energies, ranges and
    angles in range; the pendants over the floor under the vault, the corridor's lamps in the corridor; [video]'s keys
    inside the hall or the corridor, its size, fps and length within the walk-through's limits."""
    li = layout.get("light")
    if li is None:
        return []
    p: list[str] = []
    h = layout["hall"]
    if li["mood"] not in li["moods"]:
        p.append(f"light: mood {li['mood']} is not in [light.moods]")
    for g in li["grid"]:
        if g not in views:
            p.append(f"light grid: {g} is no view")
    for mid, m in li["moods"].items():
        if sorted(m) != sorted(("title",) + LIGHT_KEYS):
            p.append(f"light {mid}: keys differ from the moods' set ({', '.join(sorted(set(m) ^ set(('title',) + LIGHT_KEYS)))})")
            continue
        for k in LIGHT_KEYS:
            v = m[k]
            if k.endswith("_rgb"):
                if len(v) != 3 or not all(0.0 <= c <= 1.0 for c in v):
                    p.append(f"light {mid}: {k} {v} is not a colour in 0..1")
            elif k.endswith("_dir"):
                if not (-180 <= v[0] <= 180 and -90 <= v[1] <= 90):
                    p.append(f"light {mid}: {k} {v} is not [azimuth, elevation]")
            elif not 0.0 <= v <= (90.0 if k.endswith("_angle") else 40.0):
                p.append(f"light {mid}: {k} {v} out of range")
        if not 10.0 <= m["pendant_angle"] <= 70.0:
            p.append(f"light {mid}: pendant_angle {m['pendant_angle']} is not within 10..70 (the shade's rim)")
        if not 10.0 <= m["fill_angle"] <= 85.0:
            p.append(f"light {mid}: fill_angle {m['fill_angle']} is not within 10..85")
        if not 0.0 <= m["earth_shadow"] <= 1.0:
            p.append(f"light {mid}: earth_shadow {m['earth_shadow']} is not an opacity in 0..1")
    for tid, tr in li.get("trials", {}).items():
        extra = sorted(set(tr) - set(("title",) + LIGHT_KEYS))
        if extra or "title" not in tr:
            p.append(f"light trial {tid}: needs a title and only the moods' keys ({', '.join(extra)})")
    for x, y, z in li.get("window", []):
        if not on_floor(layout, x, z) or not 0 < y < h["wall"]:
            p.append(f"light: window lamp ({x}, {y}, {z}) is not inside the hall")
    if not 0.0 <= li.get("window_tilt", 0.0) <= 80.0:
        p.append(f"light: window_tilt {li['window_tilt']} is not within 0..80")
    for x in li["pendants_x"]:
        for z in li["pendants_z"]:
            if not on_floor(layout, x, z):
                p.append(f"light: pendant ({x}, {z}) is not over the floor")
    if not 0 < li["strip_y"] < h["wall"]:
        p.append(f"light: strip_y {li['strip_y']} is not on the walls")
    for x, y, z in li["corridor"]:
        if not in_corridor(layout, x, z) or not 0 < y < layout["arch"]["h"]:
            p.append(f"light: corridor lamp ({x}, {y}, {z}) is not in the corridor")
    vd = layout.get("video")
    if vd:
        if vd["size"] != [1280, 720] or not 12 <= vd["fps"] <= 30 or vd["max_mb"] > 15:
            p.append("video: 1280 x 720, 12..30 fps and at most 15 MB")
        seconds = sum(k[2] for k in vd["keys"][1:])
        if not 40.0 <= seconds <= 60.0:
            p.append(f"video: {seconds:.1f} s is not within 40..60 s")
        for i, (eye, _look, _s) in enumerate(vd["keys"]):
            if not (on_floor(layout, eye[0], eye[2]) or in_corridor(layout, eye[0], eye[2])) or not 1.0 < eye[1] < 2.2:
                p.append(f"video key {i}: its eye {eye} is not at eye height in the hall or the corridor")
    return p
