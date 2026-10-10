"""The garden and the greenhouse in Godot for `tools/run.py garden --proof` (art #80, docs/house-garden.md): the request
of godot/garden/proof.gd. It starts from the outdoor proof's request (house_outdoor_scene.py: the plot, fence, stairs,
sky, backdrop) without the grey stand-ins the layout engine's house scene replaces, and adds the house scene
(res://import/house/house.tscn, with the greenhouse's glass walls and dressing), the glass roof from garden.json, the
garden's props and lights, the scatter plants (one MultiMesh per plant kind), the kinds that cast no shadow, the walks
(every garden path, the herb route from the kitchen), the glass roof's ray test and the pictures."""

from __future__ import annotations

from pathlib import Path

from . import house_outdoor_scene

EYE = 1.6
HOUSE = "res://import/house/house.tscn"
COVERED = {"house", "garage", "greenhouse", "terrace"}  # floor holes the house scene builds
# Stand-in lamps (#83 owns the light design): height above the prop's base, energy, range.
LAMPS = {"garden_post_lamp": (2.2, 1.6, 9.0), "path_light": (0.45, 0.5, 3.5), "string_lights": (-0.1, 0.9, 6.0)}
GREENHOUSE_LAMPS = [[62.5, 2.2, 12.0, 1.2, 8.0], [69.5, 2.2, 12.0, 1.2, 8.0]]
DRAW_CALL_LIMIT = 150


def roof_placed(garden: dict) -> list[list]:
    """garden.json's glass roof as the proof's placements: [id, [x, height, z], yaw]."""
    return [[r["id"], [r["x"], r["h"], r["y"]], r["turn"]] for r in garden["roof"]]


def props(garden: dict) -> list[list]:
    """The garden's fixed props: [res, [x, h, z], yaw]; each GLB is staged as prop_<id> (plants' hedge too)."""
    return [[f"res://import/prop_{p['id']}.glb", [p["at"][0], p["h"], p["at"][1]], p["yaw"]] for p in garden["props"]]


def plants(garden: dict) -> dict[str, list[list[float]]]:
    """res -> [[x, z, yaw, scale]] per scatter kind (staged as plant_<id>_<kind>)."""
    out: dict[str, list[list[float]]] = {}
    for q in garden["scatter"]:
        res = f"res://import/plant_{q['id']}_{q['kind']}.glb"
        out.setdefault(res, []).append([q["at"][0], q["at"][1], float(q["yaw"]), float(q["scale"])])
    return out


def no_shadow(garden: dict) -> list[str]:
    """The res of every prop and plant kind marked `shadow = false` in garden.toml (flat and small: their shadow
    passes cost the garden's draw calls and show little); the proof turns their shadow casting off."""
    out = {f"res://import/prop_{p['id']}.glb" for p in garden["props"] if not p["shadow"]}
    out |= {f"res://import/plant_{q['id']}_{q['kind']}.glb" for q in garden["scatter"] if not q["shadow"]}
    return sorted(out)


def lights(garden: dict) -> list[list[float]]:
    out = [list(map(float, lamp)) for lamp in GREENHOUSE_LAMPS]
    for p in garden["props"]:
        if p["light"] and p["id"] in LAMPS:
            h, energy, rng = LAMPS[p["id"]]
            out.append([p["at"][0], p["h"] + (h if h > 0 else p["size"][1] + h), p["at"][1], energy, rng])
    return out


def walks(garden_data: dict) -> dict:
    """Every garden path end to end and the herb route (the kitchen, the side door, the greenhouse's door and beds),
    a 0.8 m capsule with the doors' leaves open; all must arrive."""
    out = {}
    for p in garden_data["paths"]:
        out[p["id"]] = {"r": 0.4, "must_pass": True, "leaves": "open",
                        "points": [[float(x), 0.0, float(y)] for x, y in p["line"]]}
    rt = garden_data["route"]
    out[f"route_{rt['id']}"] = {"r": 0.4, "must_pass": True, "leaves": "open",
                                "points": [[float(x), 0.0, float(y)] for x, y in rt["points"]]}
    return out


def rays(layout_room: dict) -> dict:
    """The glass roof's ray test over the greenhouse's rect [x, y, w, d]: rays straight up from inside on a 0.5 m grid
    and along both gables 5 cm in; level rays from the middle out through both gables on both slopes below the roof's
    measured height; a control up from outside the greenhouse must hit nothing."""
    x, y, w, d = (float(v) for v in layout_room["rect"])
    return {"rect": [x, y, w, d], "step": 0.5, "inset": 0.05, "from_h": 2.45, "level_step": 0.25,
            "gable_tol": 0.35, "control": [x - 2.0, 0.5, y + d / 2]}


def shots(garden: dict, room: dict) -> list[list]:
    """[name, title, from, to] at dusk: the garden from the drop-off and from the paths at 1.6 m, the greenhouse
    outside and inside (the 5 beds and the board), and a top-down."""
    gx, gy, gw, gd = (float(v) for v in room["rect"])
    drop = next(p for p in garden["props"] if p["id"] == "garden_dropoff")
    dx, dy = drop["at"]
    return [
        ["dropoff", "the garden from the drop-off", [dx, EYE, dy + 1.5], [dx - 10.0, 1.0, dy - 14.0]],
        ["path_kitchen", "from the kitchen door down the path", [43.6, EYE, 39.0], [55.0, 1.2, 17.0]],
        ["path_loop_ne", "the loop's north-east corner", [75.8, EYE, 4.8], [60.0, 1.0, 22.0]],
        ["path_east", "the east spur to the greenhouse", [70.0, EYE, 25.0], [62.0, 1.6, 8.0]],
        ["greenhouse_out", "the greenhouse from the path", [53.5, EYE, 22.5], [gx + gw / 2, 2.6, gy + gd / 2]],
        ["greenhouse_in", "inside: the 5 herb beds and the board", [gx + gw - 2.5, 2.0, gy + 1.2],
         [gx + 4.0, 0.6, gy + 8.5]],
        ["gable_in", "inside under the west gable", [gx + gw - 1.5, 1.6, gy + gd / 2], [gx, 4.0, gy + gd / 2]],
        ["dusk_lawn", "the lawn and the trees", [47.0, EYE, 18.0], [70.0, 2.0, 30.0]],
        ["top_down", "top-down", [61.0, 52.0, 21.5], [61.0, 0.0, 21.0]],
    ]


def request(plot: dict, outdoor_doc: dict, outdoor_build: Path, pack: dict | None, garden: dict, garden_data: dict,
            layout_room: dict) -> dict:
    req = house_outdoor_scene.request(plot, outdoor_doc, outdoor_build, pack)
    req["blocks"] = [b for b in req["blocks"] if b["id"] not in COVERED]
    roof = roof_placed(garden)
    req["pieces"].update({i: f"res://import/kit_{i}.glb" for i in sorted({r[0] for r in roof})})
    req.update({"house": HOUSE, "roof": roof, "props": props(garden), "plants": plants(garden),
                "no_shadow": no_shadow(garden),
                "lights": req["lights"] + lights(garden), "walks": walks(garden_data), "strips": [],
                "views": shots(garden, layout_room), "rays": rays(layout_room),
                "draw_call_limit": DRAW_CALL_LIMIT})
    return req
