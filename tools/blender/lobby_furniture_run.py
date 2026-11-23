"""The lobby's bar, mirror and match console (art #389, #390, #391): the driver (plain Python, outside Blender), as
pinball_run.py.
1. lobby_furniture_build.py in headless Blender per piece: <piece>.glb and <piece>.json into <out>/<piece>/;
2. glTF-Validator on each GLB;
3. the clearances in the hall: each piece's footprint (its bounds turned and placed by its spec's [placement]) against
   the hall's walls, the side walls' pilasters and the doors' openings (clearances.json);
4. the shots in our hall (godot/lobby_furniture/shots.gd, which extends the lobby's hall.gd) in an off-screen window
   (_godot.window()): per piece a 3/4 view, the front, the player's eye and close-ups, and a sheet with the concept.
Everything goes under <raw>/lobby/furniture/<tag>/.
--asset DIR packs an existing build instead (no build, no shots, nothing written under <raw>): per piece of PACKED in
--only, DIR/<piece>/ with export/<piece>.glb (copied unchanged; its textures are embedded), report.json (from the
build's <piece>.json, validator report, clearances.json and shots/shots.json, the markers as Godot placed them in the
hall), package.json, HANDOFF.md and manifest.toml; --approved LOGIN,DATE,PR_URL fills the manifest's approval.

    $PYTHON_BIN tools/blender/lobby_furniture_run.py [--tag v1] [--only bar,mirror] [--no-build] [--no-shots]
    $PYTHON_BIN tools/blender/lobby_furniture_run.py --tag v6 --only bar,match_console,mirror --asset assets/prop         --approved xperiaroco2,2026-11-23,<PR URL>
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common, lobby_layout  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402
from runner.commands import lobby as lobby_cmd  # noqa: E402

RAW = common.raw_dir()
BASE = RAW / "lobby" / "furniture"
CONCEPTS = RAW / "2026-11-22-lobby-bar-mirror-console-concepts"
PIECES = {"bar": ("bar_dims.toml", "bar2_galley"), "mirror": ("mirror_dims.toml", "mir3_fins"),
          "match_console": ("match_console_dims.toml", "con2_monolith"), "mug": ("mug_dims.toml", "mug3_stein")}
CONCEPT_DIRS = {"mug": RAW / "2026-11-23-lobby-mug-concepts"}   # the others: CONCEPTS
ON_BAR = {"mug"}   # placed on the bar's top (their spec's [placement] on_bar, in the bar's frame), no floor clearances
SCRIPT = "res://lobby_furniture/shots.gd"
PLINTH = 0.2   # a pilaster's plinth reaches 0.1 m beyond its shaft either side and out (measured on walls.glb, v20)


def dims(piece: str) -> dict:
    return tomllib.loads((Path(__file__).with_name(PIECES[piece][0])).read_text(encoding="utf-8"))


def placement(piece: str) -> tuple[list, float]:
    """The piece's origin (cm, the hall's frame) and yaw (degrees): its spec's, or on the bar's top."""
    pl = dims(piece)["placement"]
    if piece in ON_BAR:
        return [c * 100.0 for c in to_hall("bar", pl["on_bar"])], pl["yaw_deg"]
    return pl["origin"], pl["yaw_deg"]


def to_hall(piece: str, p) -> list[float]:
    """A point (cm, the piece's frame) in the hall's frame (m)."""
    o, yaw = placement(piece)
    a = math.radians(yaw)
    x, y, z = p
    hx = x * math.cos(a) + z * math.sin(a)
    hz = -x * math.sin(a) + z * math.cos(a)
    return [round((o[0] + hx) / 100.0, 4), round((o[1] + y) / 100.0, 4), round((o[2] + hz) / 100.0, 4)]


def footprint(piece: str, bounds: dict) -> tuple[list, list]:
    lo, hi = bounds["min"], bounds["max"]
    pts = [to_hall(piece, (x, 0.0, z)) for x in (lo[0], hi[0]) for z in (lo[2], hi[2])]
    return [min(p[0] for p in pts), max(p[0] for p in pts)], [min(p[2] for p in pts), max(p[2] for p in pts)]


def clearances(piece: str, bounds: dict, layout: dict) -> dict:
    """The gaps (m, negative: an overlap) from the piece's footprint to the walls, the side walls' pilasters (from the
    walls' faces out to pilaster_d, pilaster_w wide at each rib), the doors' openings (side doors: 1 m out from the
    wall) and the ship's footprint."""
    h = layout["hall"]
    (x0, x1), (z0, z1) = footprint(piece, bounds)
    out = {"footprint_x": [round(x0, 3), round(x1, 3)], "footprint_z": [round(z0, 3), round(z1, 3)],
           "west_wall": round(x0 - h["x0"], 3), "east_wall": round(h["x1"] - x1, 3), "south_wall": round(h["zS"] - z1, 3)}

    def gap(bx, bz) -> float:   # the gap between the footprint and a box (negative inside)
        dx = max(bx[0] - x1, x0 - bx[1])
        dz = max(bz[0] - z1, z0 - bz[1])
        return round(max(dx, dz) if dx < 0 or dz < 0 else math.hypot(dx, dz), 3)

    pw, pd = h["pilaster_w"] + PLINTH, h["pilaster_d"] + PLINTH / 2   # the pilasters with their plinths
    pil = [gap((h["x0"], h["x0"] + pd), (r - pw / 2, r + pw / 2)) for r in h["ribs"]]
    pil += [gap((h["x1"] - pd, h["x1"]), (r - pw / 2, r + pw / 2)) for r in h["ribs"]]
    out["pilasters"] = min(pil)
    dw = layout["door"]["w"]
    doors = []
    for _id, wall, at in layout["door"]["doors"]:
        if wall == "W":
            doors.append(gap((h["x0"], h["x0"] + 1.0), (at - dw / 2, at + dw / 2)))
        elif wall == "E":
            doors.append(gap((h["x1"] - 1.0, h["x1"]), (at - dw / 2, at + dw / 2)))
        else:
            doors.append(gap((at - dw / 2, at + dw / 2), (h["zN"], h["zN"] + 1.0)))
    out["doors"] = min(doors)
    return out


def mirror_style(style: str | None = None) -> str:
    """The mirror's style: the run's --style, else its spec's [style] pick."""
    return style or dims("mirror")["style"]["pick"]


def views(piece: str, b: dict, style: str | None = None) -> list:
    """Per piece: [name, title, eye, target, fov] in the hall's frame; the mirror's close-up captions follow its style
    (the run's --style or the spec's pick): fins for spikes and soft, slabs for flat, the frame for frame."""
    lo, hi = b["min"], b["max"]
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    w = hi[0] - lo[0]
    T = lambda p: to_hall(piece, p)   # noqa: E731
    if piece == "bar":
        k = dims("bar")["tap"]
        tap = (0.0, 110.0 + 20.0, k["at_z"])
        return [["bar_q34", "the bar, 3/4 front (the concept's side)", T((-380, 165, 420)), T((-20, 70, 0)), 45.0],
                ["bar_front", "the bar from the hall", T((0, 150, 330)), T((0, 70, 0)), 75.0],
                ["bar_eye", "the player's eye at the tap (1.65 m)", T((0, 165, 150)), T((0, 100, 0)), 75.0],
                ["bar_tap", "the tap close up", T((45, 150, 110)), T(tap), 35.0],
                ["bar_end", "an end and the plinth's glow", T((380, 60, 160)), T((260, 50, 20)), 40.0],
                ["bar_hall", "in the hall by the west wall, from its south end", T((-760, 260, 300)), T((0, 60, 0)), 55.0]]
    if piece == "mirror":
        side, top = {"frame": ("the frame's left side close up", "the frame's top right corner and light strip"),
                     "flat": ("the left slabs close up", "the slabs' tops")}.get(
            mirror_style(style), ("the left fins close up", "the fins' steel tips"))
        return [["mirror_q34", "the mirror, 3/4 (the concept's side)", T((-260, 165, 420)), T((0, 125, 0)), 50.0],
                ["mirror_front", "the mirror from the players' places", T((0, 165, 520)), T((0, 125, 0)), 50.0],
                ["mirror_eye", "a player's eye at MirrorPlace2 (1.65 m)", T((0, 165, 60)), T((0, 150, 0)), 75.0],
                ["mirror_fins", side, T((-90, 120, 150)), T((-135, 110, 6)), 40.0],
                ["mirror_tips", top, T((90, 220, 120)), T((130, 235, 6)), 35.0],
                ["mirror_hall", "on the west wall, between the pilaster and the corner", T((250, 380, 1100)), T((0, 120, 0)), 55.0]]
    if piece == "mug":   # close views (cm, the mug's frame: the holder's side +z, the handle +x on its right); the
        # empty mug 25 cm to its left
        return [["mug_q34", "the mug, 3/4 (the concept's side: the handle on the right)", T((-22, 28, 40)), T((1.5, 8.5, 0)), 30.0],
                ["mug_front", "from the holder's side", T((0, 12, 55)), T((1.5, 8.5, 0)), 25.0],
                ["mug_handle", "the handle's side", T((60, 14, 4)), T((2.5, 8.5, 0)), 25.0],
                ["mug_top", "the head from above", T((4, 55, 20)), T((0, 15, 0)), 25.0],
                ["mug_pair", "full and empty (the Beer node hidden)", T((-14, 32, 62)), T((-12, 8, 0)), 35.0],
                ["mug_bar", "on the bar by the tap, from the player's eye", T((-60, 55, 130)), T((-30, 5, 0)), 55.0]]
    s = dims("match_console")["screen"]
    return [["con_q34", "the console, 3/4 front", T((150, 165, 260)), T((0, 90, 0)), 45.0],
            ["con_front", "the console from the front", T((0, 120, 330)), T((0, 85, 0)), 45.0],
            ["con_eye", "the player's eye at 1 m (1.65 m)", T((0, 165, 100)), T((0, s["centre_y"], 15)), 75.0],
            ["con_screen", "the screen's frame and line", T((50, 130, 80)), T((40, 125, 15)), 35.0],
            ["con_base", "the base and its ring", T((110, 60, 140)), T((40, 10, 30)), 40.0],
            ["con_hall", "in the hall behind the spawns", T((400, 400, 900)), T((0, 80, 0)), 55.0]]


def request(layout: dict, out: Path, built: dict, style: str | None = None) -> tuple[dict, dict]:
    place = lobby_cmd.ship_scene(layout)[0]
    pieces = lobby_cmd.raw(layout) / "pieces"
    req, staged, _want = lobby_cmd.scene_request(layout, pieces, place, lobby_layout.ship_report(layout))
    vs, sheets = [], []
    for piece, b in built.items():
        staged[f"furn_{piece}"] = out / piece / f"{piece}.glb"
        req["pieces"][f"furn_{piece}"] = f"res://import/furn_{piece}.glb"
        o, yaw = placement(piece)
        req["place"].append([f"furn_{piece}", [c / 100.0 for c in o], yaw])
        if piece == "mug":   # an empty one beside it, its Beer hidden (shots.gd "hide")
            req["place"].append([f"furn_{piece}", to_hall("mug", (-25.0, 0.0, 0.0)), yaw])
            req.setdefault("hide", []).append([f"furn_{piece}", 1, "Beer"])
        v = views(piece, b, style)
        vs += v
        n = [x[0] for x in v]
        sheets.append([f"{piece}_sheet.png", (CONCEPT_DIRS.get(piece, CONCEPTS) / PIECES[piece][1] / "image-0.png").as_posix(),
                       [["concept", n[0]], [n[1], n[2]], [n[3], n[4]], [n[5]]]])
    req.update({"mode": "shoot", "watchdog_s": 540, "background": layout["review"]["background"],
                "top": layout["review"]["top"], "look": lobby_cmd.look_request(layout, layout["look"]["scheme"]),
                "furniture": {"views": vs, "sheets": sheets, "hide": req.pop("hide", [])}})
    if "earth" in layout:
        req["earth"] = lobby_cmd.earth_request(layout, layout["earth"]["variant"])["earth"]
    if "light" in layout:
        req["light"] = lobby_cmd.light_request(layout, layout["light"]["mood"])["light"]
    return req, staged


# The game packages (art #389, #390, #391): per piece its issue, title, what the game draws on its meshes, what its
# markers mean and the greybox it replaces in prime-game (levels/lobby/lobby.tscn, levels/lobby/match_console.tscn).
PACKED = {
    "bar": {
        "issue": 389, "title": "The lobby's bar",
        "meshes": {"bar": "the whole bar: the stone top, the shell, the steel sweep and the tap, the light lines, the "
                          "plinth's glow"},
        "markers": {"TapSpot": "where a player stands to draw a beer, on the floor 1.5 m out from the tap (the "
                               "greybox's `Tap`, group `spawn_tap`)",
                    "TapSpout": "the tap's spout, where the beer leaves it"},
        "greybox": "levels/lobby/lobby.tscn `Bar` (StaticBody3D at (-17, 0, -13), its box 1 x 1.1 x 6 m centred at "
                   "(0.5, 0.55, 3) inside it: the floor's middle at (-16.5, 0, -10)) and the marker `Tap` at "
                   "(-15, 0, -10)",
        "collision": "the greybox's box (1 x 1.1 x 6 m) still fits the counter; the tap reaches 1.6 m",
    },
    "match_console": {
        "issue": 391, "title": "The lobby's match console",
        "meshes": {"match_console": "the monolith: body, facets, steel lines, base plate and its light ring",
                   "ConsoleScreen": "the screen's surface: the game draws the match's screen on it (its material "
                                    "`match_console_screen` is a dark stand-in)"},
        "markers": {"Screen": "the screen's centre on its face (the greybox's `Screen` is at (0, 1.15, 0.16); here "
                              "z 0.162, the built screen's face)"},
        "greybox": "levels/lobby/match_console.tscn (StaticBody3D `MatchConsole`, its box 1.2 x 1.6 x 0.3 m, `Screen` "
                   "at (0, 1.15, 0.16)), instanced in levels/lobby/lobby.tscn as `MatchConsole` at (-7, 0, 7.2) "
                   "turned 180 degrees",
        "collision": "the greybox's box (1.2 x 1.6 x 0.3 m) covers the monolith's body; the round base plate (1.56 m "
                     "across, a few cm high) stays walkable",
    },
    "mirror": {
        "issue": 390, "title": "The lobby's mirror",
        "meshes": {"mirror": "the frame (style `frame`, the engineer's pick C): the back plate, the wide rounded steel "
                             "frame with its cyan line, the light bar over the glass",
                   "MirrorGlass": "the glass, 2 x 2.5 m: the game draws the reflection on it (its material "
                                  "`mirror_glass` is a bright stand-in)"},
        "markers": {"MirrorFace": "the glass's centre on its face, 1.25 m up"},
        "greybox": "levels/lobby/lobby.tscn `Mirror` (StaticBody3D at (-20, 0, 7), its box 0.2 x 2.5 x 2 m centred at "
                   "(0.1, 1.25, 1): the glass on the west wall at x -20..-19.8, z 7..9) and the markers "
                   "`MirrorPlace1..3` at (-19.2, 0, 7.2), (-19.2, 0, 8), (-19.2, 0, 8.8)",
        "collision": "the greybox's box reaches x -19.8 and z 7..9, 2.5 m up; the mirror reaches x -19.72 (0.14 m "
                     "out from its origin on the wall's panels) and z 6.9..9.1, 2.67 m up: a box 0.28 x 2.67 x 2.21 m "
                     "centred at (-19.86, 1.335, 8) holds it from the wall to the frame's front",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def glb_summary(path: Path) -> dict:
    """What the GLB holds as the game imports it: per node its kind (a mesh or a marker) and place (m), the triangles
    per mesh node, the materials, the embedded images."""
    g = _export.glb_json(path)
    acc = g.get("accessors", [])
    tris = []
    for m in g.get("meshes", []):
        n = 0
        for prim in m["primitives"]:
            if prim.get("mode", 4) == 4:
                n += acc[prim["indices"] if "indices" in prim else prim["attributes"]["POSITION"]]["count"] // 3
        tris.append(n)
    nodes = {}
    for nd in g.get("nodes", []):
        t = [round(c, 4) for c in nd.get("translation", [0.0, 0.0, 0.0])]
        if "mesh" in nd:
            nodes[nd["name"]] = {"kind": "mesh", "triangles": tris[nd["mesh"]], "at_m": t}
        else:
            nodes[nd["name"]] = {"kind": "marker", "at_m": t, "rotation_xyzw": nd.get("rotation", [0.0, 0.0, 0.0, 1.0])}
    return {"nodes": nodes, "roots": sorted(g["nodes"][i]["name"] for i in g["scenes"][g.get("scene", 0)]["nodes"]),
            "materials": [m["name"] for m in g.get("materials", [])], "images_embedded": len(g.get("images", [])),
            "triangles": sum(v["triangles"] for v in nodes.values() if v["kind"] == "mesh")}


def tscn_transform(origin_cm: list, yaw_deg: float) -> str:
    """The placement as a Godot .tscn Transform3D: the basis row by row (Godot writes a Basis by its rows; a yaw of +90
    degrees maps +Z to +X, as to_hall does and as the greybox's Glass marker reads), then the origin in m."""
    a = math.radians(yaw_deg)
    c, s = round(math.cos(a), 6) + 0.0, round(math.sin(a), 6) + 0.0
    n = [c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c] + [round(v / 100.0, 4) for v in origin_cm]
    return "Transform3D(" + ", ".join(f"{v + 0.0:g}" for v in n) + ")"


def write_asset(asset: Path, out: Path, tag: str, piece: str, approved: list | None = None) -> Path:
    """One piece's asset folder from the build in out (<raw>/lobby/furniture/<tag>/): export/<piece>.glb copied
    unchanged, report.json, package.json, HANDOFF.md, manifest.toml. Reads the build; writes nothing under <raw>."""
    asset = asset if asset.is_absolute() else ROOT / asset
    info, spec = PACKED[piece], dims(piece)
    src = out / piece / f"{piece}.glb"
    (asset / "export").mkdir(parents=True, exist_ok=True)
    glb = asset / "export" / f"{piece}.glb"
    shutil.copyfile(src, glb)
    digest = sha256(glb)
    if digest != sha256(src):
        raise SystemExit(f"{glb}: the copy differs from {src}")
    build = json.loads((out / piece / f"{piece}.json").read_text(encoding="utf-8"))
    issues = json.loads((out / piece / f"{piece}.validator.json").read_text(encoding="utf-8")).get("issues", {})
    validator = {k: issues.get(k, 0) for k in ("numErrors", "numWarnings", "numInfos", "numHints")}
    clear = json.loads((out / "clearances.json").read_text(encoding="utf-8")).get(piece)
    gl = glb_summary(glb)
    origin, yaw = placement(piece)
    markers = {n: v["at_m"] for n, v in gl["nodes"].items() if v["kind"] == "marker"}
    hall = {n: to_hall(piece, [c * 100.0 for c in p]) for n, p in markers.items()}
    shots = out / "shots" / "shots.json"
    godot = None
    if shots.is_file():   # the markers as Godot placed them in the hall in this build's shots (the same GLB)
        probe = json.loads(shots.read_text(encoding="utf-8"))["markers"]
        got = {n: probe[f"furn_{piece}/{n}"] for n in markers if f"furn_{piece}/{n}" in probe}
        err = max((max(abs(a - b) for a, b in zip(got[n], hall[n])) for n in got), default=None)
        godot = {"from": f"godot/lobby_furniture/shots.gd in an off-screen window (lobby_furniture_run.py --tag {tag}): "
                         "the GLB imported and placed in the hall by its spec's [placement]",
                 "markers_hall_m": got, "max_error_m": round(err, 4) if err is not None else None}
    style = mirror_style() if piece == "mirror" else None
    dest = asset.parent.relative_to(ROOT).as_posix()
    concept = f"{CONCEPTS.name}/{PIECES[piece][1]}/image-0.png"
    origin_text = ("on the floor at the glass's middle, on the wall's face" if piece == "mirror"
                   else "on the floor under the piece's middle")
    report = {
        "asset": piece,
        "built_by": f"tools/blender/lobby_furniture_build.py --piece {piece} (lobby_furniture_run.py --tag {tag}); "
                    f"packed unchanged from <raw>/lobby/furniture/{tag}/{piece}/{piece}.glb by "
                    f"lobby_furniture_run.py --tag {tag} --asset {dest}",
        "mesh": {"triangles": build["triangles"],
                 "triangles_by_mesh": {n: v["triangles"] for n, v in gl["nodes"].items() if v["kind"] == "mesh"},
                 "triangles_by_material": build["triangles_by_material"], "bounds_cm": build["bounds_cm"],
                 "materials": gl["materials"], "textures_embedded": gl["images_embedded"],
                 "origin": origin_text, "player_side": "+Z"},
        "style": style,
        "gltf": {"roots": gl["roots"], "nodes": gl["nodes"]},
        "markers_m": markers,
        "placement": {"origin_m": [c / 100.0 for c in origin], "yaw_deg": yaw, "tscn": tscn_transform(origin, yaw),
                      "markers_hall_m": hall},
        "clearances_m": clear,
        "gltf_validator": validator,
        "godot": godot,
        "review": f"<raw>/lobby/furniture/{tag}/shots/{piece}_sheet.png",
    }
    if piece == "mirror":
        report["placement"]["spots_m"] = [[c / 100.0 for c in s] for s in spec["placement"]["spots"]]
    (asset / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    package = {
        "format": 1, "name": piece, "kind": "prop", "version": tag, "glb": f"export/{piece}.glb",
        "files": {f"export/{piece}.glb": digest},
        "units": "m", "up": "+Y", "player_side": "+Z", "origin": origin_text,
        "meshes": {n: {"triangles": gl["nodes"][n]["triangles"], "what": w} for n, w in info["meshes"].items()},
        "markers": {n: {"at": markers[n], "what": w} for n, w in info["markers"].items()},
        "triangles": build["triangles"], "materials": gl["materials"], "textures_embedded": gl["images_embedded"],
        "placement": {"origin": [c / 100.0 for c in origin], "yaw_deg": yaw, "transform": tscn_transform(origin, yaw),
                      "markers": hall, "greybox": info["greybox"]},
    }
    if style:
        package["style"] = style
    (asset / "package.json").write_text(json.dumps(package, indent=1) + "\n", encoding="utf-8", newline="\n")
    (asset / "HANDOFF.md").write_text(handoff(piece, tag, glb, package, report, approved), encoding="utf-8",
                                      newline="\n")
    raws = [f"lobby/furniture/{tag}/{piece}/{piece}.glb", f"lobby/furniture/{tag}/{piece}/{piece}.json", concept]
    notes = (f"{info['title']} for prime-game's lobby hall (art#{info['issue']}): export/{piece}.glb, "
             f"{build['triangles']:,} triangles in the meshes {', '.join(info['meshes'])}, the markers "
             f"{', '.join(info['markers'])}, origin {origin_text}, the player side +Z; it replaces the greybox "
             f"{info['greybox'].split(' (')[0]} (HANDOFF.md). "
             + ("The style frame (the engineer's pick C of 2026-11-23): a wide rounded steel frame with a cyan line "
                "and a light bar over the glass, no fins. " if piece == "mirror" else "")
             + f"Built from code in headless Blender (tools/blender/lobby_furniture_build.py --piece {piece}, build "
             f"{tag}) from its drawing tools/blender/{PIECES[piece][0]}, after our own OpenAI concept image "
             f"<raw>/{concept} (no batch file in this repo; the raw folder {CONCEPTS.name}/ holds the generations "
             "and their log.csv, kept out of git), used only as a reference: the shapes are modelled by hand-written "
             "code and the textures made by code in Blender, and no image or mesh of the concept is in the files, "
             "hence own-work and ai_generated false. Without copper (the engineer, 2026-11-23): cold steel and cyan "
             "light lines. Approved by the engineer on 2026-11-23 (relayed by the director), in the hall with the "
             "teal strips R.")
    lines = [
        f"# {info['title']} (art #{info['issue']}).",
        f"# Packed by tools/blender/lobby_furniture_run.py --tag {tag} --asset {dest} from the build below, copied",
        "# unchanged; a rebuild changes the hashes below.",
        f'id = "{piece}"',
        'kind = "prop"',
        'slot = ""',
        f'title = "{info["title"]}"',
        f'notes = "{notes}"',
        'tools = ["blender 5.2.2", "prime-game-art lobby_furniture_build.py, lobby_furniture_run.py", '
        '"glTF-Validator 2.0.0-dev.3.10", "Godot 4.7.2 (shots)"]',
        'licence = "own-work"',
        'licence_url = "https://github.com/xperiaroco2/prime-game"',
        "public_repo_ok = true",
        "ai_generated = false",
        f'approved_by = ["{approved[0]}"]' if approved else "approved_by = []",
        f"approved_at = {approved[1]}" if approved else 'approved_at = ""',
        f'approval_pr = "{approved[2]}"' if approved else 'approval_pr = ""',
        "",
        "[source]",
        'service = "own"',
        'plan = "own-work"',
        'model_version = ""',
        "task_ids = []",
        f"generated_at = {datetime.date.fromtimestamp(src.stat().st_mtime).isoformat()}",
        f'url = "https://github.com/xperiaroco2/prime-game-art/issues/{info["issue"]}"',
    ]
    for r in raws:
        lines += ["", "[[raw]]", f'file = "{r}"', f'sha256 = "{sha256(RAW / r)}"']
    (asset / "manifest.toml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return asset


def handoff(piece: str, tag: str, glb: Path, package: dict, report: dict, approved: list | None) -> str:
    """HANDOFF.md for the game's session: files, meshes, markers, origin and axes, the greybox it replaces."""
    info, pl = PACKED[piece], package["placement"]
    v = report["gltf_validator"]
    f3 = lambda p: ", ".join(f"{c + 0.0:g}" for c in p)   # noqa: E731
    out = [f"# {info['title']}: handoff to the game (art#{info['issue']})", "",
           f"Built from code (`tools/blender/lobby_furniture_build.py --piece {piece}` from its drawing "
           f"`tools/blender/{PIECES[piece][0]}`), build `{tag}`, packed unchanged. "
           + (f"Approved by {approved[0]} on {approved[1]} ({approved[2]})." if approved else "Not approved yet."),
           "", "## Files", "", "| File | What |", "|---|---|",
           f"| `export/{piece}.glb` | One scene, {package['triangles']:,} triangles, {len(package['materials'])} "
           f"materials, {package['textures_embedded']} textures embedded, {glb.stat().st_size // 1024} KB. SHA-256 "
           f"`{package['files'][package['glb']]}` |",
           "| `package.json` | The meshes, markers, origin and placement, for code |",
           f"| `report.json` | Triangles per mesh and material, bounds, glTF-Validator ({v['numErrors']} errors, "
           f"{v['numWarnings']} warnings), the clearances in the hall, the markers as Godot placed them |", "",
           "## Nodes", "", "Units metres, +Y up, the player side +Z. The GLB's root nodes:", ""]
    for n, m in package["meshes"].items():
        out.append(f"- `{n}` (MeshInstance3D, {m['triangles']:,} triangles): {m['what']};")
    for n, m in package["markers"].items():
        out.append(f"- `{n}` (Node3D, a marker) at ({f3(m['at'])}): {m['what']}.")
    out += ["", f"**Origin:** {package['origin']}.", "", "## In the lobby", "",
            f"It replaces the greybox {info['greybox']}.", "",
            f"- Place the GLB's root at ({f3(pl['origin'])}) in the hall, turned {pl['yaw_deg']:g} degrees about +Y: "
            f"`{pl['transform']}`.",
            "- Its markers then land at (the hall's frame, m): "
            + "; ".join(f"`{n}` ({f3(p)})" for n, p in pl["markers"].items()) + ".",
            f"- Collision: {info['collision']}."]
    if piece == "mirror":
        out.append("- The players' places in front: " + ", ".join(f"({f3(s)})" for s in report["placement"]["spots_m"])
                   + " (the greybox's `MirrorPlace1..3`).")
        out.append("- The greybox's `Glass` marker (group `mirror_glass`, metadata `glass_size_m` (2, 2.5)) is what the "
                   "reflection reads: keep it with its group and metadata, at the GLB's `MirrorGlass` face (x -19.77 in "
                   "the hall instead of -19.79), or give `MirrorGlass` the group and the metadata instead.")
    if piece == "match_console":
        out.append("- `match_console.tscn` already stands at this transform in `lobby.tscn`: put the GLB in place of "
                   "its `Mesh`, keep `Shape`, and move `Screen` to the GLB's `Screen` (z 0.162 instead of 0.16), keeping its "
                   "group `match_console_screen`.")
    if piece == "bar":
        out.append("- The `Tap` marker (group `spawn_tap`) stays where it is: the GLB's `TapSpot` lands on it.")
    out += ["", "No label, no text, no copper. The look is approved: do not restyle it in the game.", ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--only", default=",".join(PIECES))
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--style", help="the mirror's variant (mirror_dims.toml [style]): spikes, soft, flat, frame")
    ap.add_argument("--asset", type=Path, help="pack the existing build into DIR/<piece>/ (e.g. assets/prop)")
    ap.add_argument("--approved", help="LOGIN,DATE,PR_URL: the manifest's approval (with --asset)")
    args = ap.parse_args()
    out = BASE / args.tag
    only = [p for p in args.only.split(",") if p]
    if args.asset:
        approved = args.approved.split(",", 2) if args.approved else None
        for piece in only:
            if piece not in PACKED:
                print(f"skip {piece}: not packed here (PACKED: {', '.join(PACKED)})", flush=True)
                continue
            folder = write_asset(args.asset / piece, out, args.tag, piece, approved)
            print(f"asset: {folder.relative_to(ROOT).as_posix()}", flush=True)
        return 0
    layout = lobby_layout.load()
    ok = True
    built, report = {}, {}
    for piece in only:
        folder = out / piece
        if not args.no_build:
            r = blender.run_script("lobby_furniture_build.py", ["--piece", piece, "--out", str(folder)]
                                   + (["--style", args.style] if args.style and piece == "mirror" else []), timeout=600)
            print(*[x for x in (r.stdout or "").splitlines() if x.startswith("FURNITURE_BUILD")], sep="\n", flush=True)
        passed, text = _export.verdict(_export.validate(folder / f"{piece}.glb", folder / f"{piece}.validator.json"))
        print(f"validator {piece}.glb: {text}", flush=True)
        ok = ok and passed
        b = json.loads((folder / f"{piece}.json").read_text(encoding="utf-8"))["bounds_cm"]
        built[piece] = b
        if piece in ON_BAR:
            continue
        cl = clearances(piece, b, layout)
        report[piece] = cl
        print(f"clearances {piece} (m): {cl}", flush=True)
        if min(cl["west_wall"], cl["east_wall"], cl["south_wall"]) < -0.001 or cl["pilasters"] < 0.0 or cl["doors"] < 0.0:
            print(f"CLASH {piece}: {cl}", flush=True)
            ok = False
    (out / "clearances.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    code = 0
    if not args.no_shots and built:
        req, staged = request(layout, out, built, args.style)
        for line in lobby_cmd._stage(staged)[:5]:
            print(f"  import: {line}")
        shots = out / "shots"
        shots.mkdir(parents=True, exist_ok=True)
        path = common.OUT / "lobby_furniture" / "shoot_request.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(req, indent=1), encoding="utf-8", newline="\n")
        code, output = _godot.window(["--path", str(_godot.PROJECT), "--audio-driver", "Dummy", "-s", SCRIPT, "--",
                                      path.as_posix(), shots.as_posix()], lobby_cmd.VIEW_SIZE, 600,
                                     log=out / "godot_shoot.log")
        (out / "godot_shoot.log").write_text(output, encoding="utf-8")
        print(*[x for x in output.splitlines() if x.startswith(("FURNITURE", "LOBBY")) or "SCRIPT ERROR" in x][:20],
              sep="\n")
        print(f"godot shots: exit {code} {shots.as_posix()}", flush=True)
    return 0 if ok and code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
