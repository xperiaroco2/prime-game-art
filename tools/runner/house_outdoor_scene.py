"""The Godot proof's scene of the House map outside the house (art #81; docs/house-outdoor.md "The proof"): what
godot/outdoor/proof.gd builds, walks and shoots, as one JSON request. Standard library only.

The scene: kit v2 pieces placed by `house_outdoor.plan` (fence, gates, post caps, outdoor stairs, rails), the ground
and backdrop GLBs, the painted sky as a panorama, fog from the backdrop's `fog_start_m`, grey stand-in blocks for what
other packages build (the house, the terrace, the garage, the greenhouse), a pad under the stairs and the stairwell's
walls, the dressing placements as boxes and the lit props as warm lamps. Coordinates in the request are Godot's
(x east, y up, z = the doc's y south)."""

from __future__ import annotations

from pathlib import Path

# Grey stand-ins for what other packages build (the house #75a, the garage #79, the greenhouse #80): height in metres;
# a hole not named here gets a 0.3 m slab with its top at y 0 (the terrace). Placeholders only, never exported.
BLOCK_H = {"house": 6.4, "garage": 3.2, "greenhouse": 3.0}
PASSAGE = (58.0, 28.0, 8.0, 6.0)  # a temporary pad at -drop under the stairs until #75a's passage is on the branch
PIT_T = 0.2  # the stairwell's stand-in walls
LINTEL_CLEAR_M = 2.2
EYE = 1.6
FOG_END_M = 180.0
PROP_COLOURS = {"hedge": (0.16, 0.26, 0.17), "parked_car": (0.32, 0.2, 0.2), "stepping_stone": (0.45, 0.44, 0.42)}
LIGHTS = {"streetlight": (4.8, 3.0, 14.0), "path_light": (0.55, 0.6, 4.0)}  # height, energy, range (#83 owns the look)


def box(bid: str, x0: float, y0: float, x1: float, y1: float, h0: float, h1: float, colour) -> dict:
    """A box in doc coordinates (x0..x1 east, y0..y1 south, h0..h1 up) as the scene's centre and size."""
    return {"id": bid, "at": [round((x0 + x1) / 2, 4), round((h0 + h1) / 2, 4), round((y0 + y1) / 2, 4)],
            "size": [round(x1 - x0, 4), round(h1 - h0, 4), round(y1 - y0, 4)], "color": list(colour), "yaw": 0}


def stand_ins(data: dict) -> list[dict]:
    """The grey blocks of the other packages' buildings, the passage pad and the stairwell's walls (on the north side
    a wall under the upper flight's head and a lintel over the lower flight's foot, the passage door)."""
    grey = (0.42, 0.42, 0.44)
    out = []
    for hole in data["floor_holes"]:
        x, y, w, d = hole["rect"]
        h = BLOCK_H.get(hole["id"])
        out.append(box(hole["id"], x, y, x + w, y + d, 0.0 if h else -0.3, h or 0.0, grey))
    drop = float(data["stairs"]["drop"])
    px, py, pw, pd = PASSAGE
    out.append(box("passage_pad", px, py, px + pw, py + pd, -drop - 0.3, -drop, (0.36, 0.36, 0.37)))
    x, y, w, d = data["stairs"]["rect"]
    t, pit = PIT_T, (0.3, 0.3, 0.31)
    out.append(box("pit_w", x - t, y - t, x, y + d + t, -drop, 0.0, pit))
    out.append(box("pit_e", x + w, y - t, x + w + t, y + d + t, -drop, 0.0, pit))
    out.append(box("pit_s", x, y + d, x + w, y + d + t, -drop, 0.0, pit))
    out.append(box("pit_n", x + w / 2, y - t, x + w, y, -drop, -0.3, pit))
    out.append(box("pit_lintel", x, y - t, x + w / 2, y, -drop + LINTEL_CLEAR_M, 0.0, pit))
    return out


def prop_boxes(data: dict) -> list[dict]:
    """Every dressing placement as a box of its `size` (until #87's dressing library), turned by its `yaw`."""
    out = []
    for p in data["props"]:
        sx, sh, sy = p["size"]
        for x, y in p["at"]:
            b = box(p["id"], x - sx / 2, y - sy / 2, x + sx / 2, y + sy / 2, 0.0, sh,
                    PROP_COLOURS.get(p["id"], (0.24, 0.24, 0.26)))
            b["yaw"] = p.get("yaw", 0)
            out.append(b)
    return out


def lights(data: dict) -> list[list[float]]:
    """[x, height, y, energy, range] of every lit prop (warm stand-ins until #83's light design)."""
    out = []
    for p in data["props"]:
        if p.get("light") and p["id"] in LIGHTS:
            h, e, r = LIGHTS[p["id"]]
            out += [[x, h, y, e, r] for x, y in p["at"]]
    return out


def walks(data: dict, doc: dict) -> dict:
    """The capsule walks (0.8 m wide): round the plot's inside along the fence, through each opening onto the pavement
    with its leaves swung open, down the outdoor stairs to the passage pad (must arrive); and controls that must stop:
    through each opening with its leaves closed, out across the fence away from the openings."""
    x0, y0 = min(p[0] for p in data["plot"]), min(p[1] for p in data["plot"])
    x1, y1 = max(p[0] for p in data["plot"]), max(p[1] for p in data["plot"])
    m, ms = 1.0, 1.4  # in from the fence; on the street side past the mailbox
    out = {"perimeter": {"r": 0.4, "must_pass": True, "leaves": "closed", "points": [
        [x0 + m, 0.0, y0 + m], [x1 - m, 0.0, y0 + m], [x1 - m, 0.0, y1 - ms], [x0 + m, 0.0, y1 - ms],
        [x0 + m, 0.0, y0 + m]]}}
    kerb = float(data["kerb"]["y"])
    for o in doc["openings"]:
        cx = (o["from"][0] + o["to"][0]) / 2
        pts = [[cx, 0.0, y1 - 5.0], [cx, 0.0, y1], [cx, 0.0, kerb - 0.6]]
        out[f"{o['kind']}_closed"] = {"r": 0.4, "must_pass": False, "leaves": "closed", "points": pts}
        out[o["kind"]] = {"r": 0.4, "must_pass": True, "leaves": "open", "points": pts}
    out["stairs"] = {"r": 0.4, "must_pass": True, "points": [[float(c) for c in p] for p in doc["stairs"]["walk"]]}
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    for name, a, b in (("out_west", (x0 + 2, my), (x0 - 3, my)), ("out_north", (mx, y0 + 2), (mx, y0 - 3)),
                       ("out_east", (x1 - 2, my - 8), (x1 + 3, my - 8)),
                       ("out_south", (x0 + 15, y1 - 2), (x0 + 15, y1 + 1.5))):
        out[name] = {"r": 0.4, "must_pass": False, "points": [[a[0], 0.0, a[1]], [b[0], 0.0, b[1]]]}
    return out


def shots(data: dict, doc: dict) -> dict:
    """Two 360-degree strips (the yard, the street; four 90-degree views each) and the views as
    [name, title, from, to] or [name, title, from, to, leaves] (the wicket's and gates' leaves; open by default)."""
    kerb = float(data["kerb"]["y"])
    mid = {o["kind"]: (o["from"][0] + o["to"][0]) / 2 for o in doc["openings"]}
    wx, gx = mid["wicket"], mid["gates"]
    fy = max(p[1] for p in data["plot"])
    sx, sy, sw, _ = data["stairs"]["rect"]
    drop = float(data["stairs"]["drop"])
    cx, _ = data["sky_cfg"]["backdrop"]["centre"]
    return {
        "strips": [["strip_yard", "yard", [48.0, EYE, 52.0]], ["strip_street", "street", [40.0, EYE, kerb + 1.5]]],
        "views": [
            ["street", "the street: kerb, cars, lights, the fence", [5.0, 1.7, kerb + 3.0], [40.0, 1.5, fy - 2.0]],
            ["wicket", "the fence and the closed wicket from the pavement", [wx + 5.0, 1.7, kerb + 2.5], [wx, 1.0, fy],
             "closed"],
            ["gates", "the 8 m gates (open) and gate posts from the street", [gx - 7.0, 1.7, kerb + 3.0], [gx, 1.0, fy]],
            ["gates_in", "the gates and the drive from inside", [gx + 3.0, 1.7, fy - 9.0], [gx - 1.0, 1.0, fy]],
            ["stairs_top", "the outdoor stairs from the garden", [sx + sw + 1.0, 1.7, sy - 1.5],
             [sx + 1.0, -drop + 0.7, sy + 2.5]],
            ["stairs_bottom", "walked down: from the passage up the flights", [sx + 1.0, -drop + EYE, sy - 0.8],
             [sx + 1.0, -1.0, sy + 3.0]],
            ["lookout_south", "seam check: 9 m up, over the street to the flats", [cx, 9.0, fy - 14.0],
             [cx, 2.0, fy + 60.0]],
            ["lookout_north", "seam check: 9 m up, north to the flats", [cx, 9.0, 20.0], [cx, 2.0, -40.0]],
            ["aerial", "the plot from over the street (grey blocks: stand-ins)", [cx, 30.0, fy + 12.0],
             [cx, 0.0, 24.0]],
        ],
    }


def request(data: dict, doc: dict, build: Path, pack: dict | None = None) -> dict:
    """The request of godot/outdoor/proof.gd: the kit v2 pieces (staged as res://import/kit_<id>.glb) and their
    placements, the ground and backdrop (res://import/outdoor.glb, backdrop.glb), the sky, the fog, the blocks, the
    lights, the walks and the shots; `pack` is the kit's `set` pack for kit_materials.gd."""
    placed = [[p["piece"], p["at"], p["yaw"]] for p in doc["fence"]]
    placed += [[p["piece"], p["at"], p["yaw"]] for p in doc["stairs"]["pieces"] + doc["stairs"]["rails"]]
    req = {"pieces": {i: f"res://import/kit_{i}.glb" for i in sorted({p[0] for p in placed})}, "placed": placed,
           "ground": "res://import/outdoor.glb", "backdrop": "res://import/backdrop.glb",
           "sky": (build / "sky.png").as_posix(),
           "fog": [float(data["sky_cfg"]["backdrop"]["fog_start_m"]), FOG_END_M],
           "blocks": stand_ins(data) + prop_boxes(data), "lights": lights(data), "walks": walks(data, doc),
           **shots(data, doc)}
    if pack:
        req["pack"] = pack
    return req
