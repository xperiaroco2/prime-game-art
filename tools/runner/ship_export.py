"""The ship's game-ready package (`ship --export DIR`, art #335, docs/ship.md "The export"): plain Python, no Godot.

godot/ship/export_scene.gd assembles the night ship in the art's Godot project (the pieces staged as
res://import/ship_<id>.glb) and saves it as res://import/ship_export/ship.tscn with its shared .tres files; this
module turns that into the package, shaped like the game's tree (its ARCHITECTURE 11.1):

  assets/environment/ship/<id>.glb (+ a minimal .import, 11.2), metal.gdshader, night_sky.gdshader,
                          console_metal.gdshader, charger_traces.gdshader, materials/metal_<name>.tres,
                          night_sky.tres, night_env.tres
  levels/ship/ship.tscn   the pieces at their placements, the night lights, environment and probes, Stations, Markers
  package.json            files with SHA-256 and bytes, the station spots, the spawn, the open questions

relocate() moves every res:// path from the art project's to the package's and drops the uids (the game's editor
writes its own)."""

from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path

from . import house_export

FORMAT = 1
ASSET_DIR = "assets/environment/ship"
MATERIAL_DIR = f"{ASSET_DIR}/materials"
SCENE = "levels/ship/ship.tscn"
BUILT = "ship_export"  # godot/import/ship_export/: export_scene.gd's output
# the art shaders the scene uses (their path in the godot/ project -> the package's file beside the pieces); lens room
# C: the lens bronze (ship.gd LENS_BRONZE: lens_bronze, lens_bronze2, lens_edge) is the console's console_metal.gdshader,
# shipped as a copy; the lens alcoves' charger traces (ship.gd TRACE_MAT, lens_trace) are charger/traces.gdshader
# the charger's electricity (charger/zap.gd, bound at run time: the arcs and sparks, and the lens_conduits pieces'
# int_cyan__lens_core cores' pulses) ships its two shaders beside them for the game's copy of zap.gd
SHADERS = {"ship/metal.gdshader": "metal.gdshader", "ship/night_sky.gdshader": "night_sky.gdshader",
           "console/console_metal.gdshader": "console_metal.gdshader",
           "charger/traces.gdshader": "charger_traces.gdshader",
           "charger/arc.gdshader": "charger_arc.gdshader", "charger/conduit.gdshader": "charger_conduit.gdshader"}
CONSOLE_YAW = 180.0  # the console's front (+Z, the button) faces the mouth (-Z): assets/prop/start_console/HANDOFF.md
# spot id prefix -> (the station package that goes there, the kind); the vents are ship pieces in the scene
PACKAGES = {"console": ("start_console", "console"), "vent": ("ship:station_vent_{side}", "vent"),
            "socket": ("crystal_socket", "socket"), "breaker": ("breaker_board", "breaker"),
            "renewer": ("crystal_charger", "renewer")}
QUESTIONS = [
    "S1: Stations holds Marker3D spots only (+Z the spot's normal into the room, origin on the deck at the wall's face "
    "or the console's middle): the station packages (start_console, crystal_socket with energy_crystal at its "
    "crystal_anchor, breaker_board, crystal_charger) get their look from their own GDScript (apply()), which an asset "
    "may not carry (11.1), so the game's station scenes instance them at the markers. Each package's HANDOFF.md "
    "'Placement' holds its own offset (the breaker board 0.07 m out along the normal).",
    "S2: the throat vents (VentE, VentW) are part of the ship: the pieces station_vent_e and station_vent_w under "
    "Pieces, calm (the heat panel hidden). Their states (slats, the heat and cool panels and their well lights) are "
    "art code today (godot/ship/vent_anim.gd, vent_glow.gd): the game's vent station drives the nodes by name.",
    "S3: the look the art sets by code is baked into the scene as overrides inside each piece's instance (the glTF "
    "materials' night values, the outside pieces' render layer 2, the vents' well lights), every piece an editable "
    "instance; the shared metal is metal.gdshader with one .tres per metal. The shaders are art code shipped as files "
    "(as the House's kit_set.gdshader): who owns them?",
    "S4: the nav lamps' blink (red, green and the white tail flash) is a script in the art's shots; the scene holds "
    "their static glow. The game adds the blink if it wants it.",
    "S5: the strip lights are many OmniLight3D nodes (no shadows) under Lights, placed per glowing cell by the art's "
    "look; a baked light or fewer lights is the game's call against its budget (HANDOFF 'Cost').",
    "S6: the pieces' colliders are the GLBs' own -col trimesh hints (StaticBody3D on layer 1); the game's `colliders` "
    "writes its wrappers on import (11.2).",
    "Imports: each GLB's .import holds only 11.2's options; the game's editor regenerates the .import files (and the "
    "uids) on its first import: commit the regenerated ones.",
]
_UID = re.compile(r' uid="uid://[a-z0-9]+"')
_PIECE = re.compile(r"res://import/ship_([a-z0-9_]+\.(?:glb|png))")  # a piece, a texture its import extracted


def station_name(spot: str) -> str:
    """The game's node name of a spot: console -> Console, vent_e -> VentE, socket_fw -> SocketFW."""
    head, *rest = spot.split("_")
    return head.capitalize() + "".join(r.upper() for r in rest)


def stations(layout: dict) -> list[dict]:
    """Every station spot as {name, spot, package, kind, at (Godot x, h, z: on the deck), yaw (deg, +Z the normal)}."""
    floor_h = float(layout["deck"]["floor_h"])
    out = []
    for s in layout["stations"]["spot"]:
        prefix, _, side = s["id"].partition("_")
        package, kind = PACKAGES[prefix]
        yaw = (math.degrees(math.atan2(s["normal"][0], s["normal"][1])) if "normal" in s else CONSOLE_YAW)
        out.append({"name": station_name(s["id"]), "spot": s["id"], "package": package.format(side=side), "kind": kind,
                    "at": [round(s["at"][0], 4), floor_h, round(s["at"][1], 4)], "yaw": round(yaw, 3),
                    "room": s["room"]})
    return out


def relocate(text: str) -> str:
    """A scene or resource saved in the art project, with its paths moved to the package's and its uids dropped."""
    text = text.replace(f"res://import/{BUILT}/", f"res://{MATERIAL_DIR}/")
    text = _PIECE.sub(lambda m: f"res://{ASSET_DIR}/{m.group(1)}", text)
    for src, name in SHADERS.items():
        text = text.replace(f"res://{src}", f"res://{ASSET_DIR}/{name}")
    return _UID.sub("", text)


def leftovers(text: str) -> list[str]:
    """What a relocated text must not hold: an art-project path, a script, a sub-resource path of an imported file,
    any res:// path outside the package."""
    bad = []
    for pat, why in ((r"res://import/", "an art-project import path"), (r'"res://ship/', "an art-project ship path"),
                     (r'type="Script"', "a script"), (r"^script = ", "a script"), (r'path="[^"]*::', "a sub-resource path"),
                     (rf'"res://(?!{ASSET_DIR}/|{SCENE.rsplit("/", 1)[0]}/)', "a path outside the package")):
        if re.search(pat, text, re.M):
            bad.append(why)
    return bad


def write(layout: dict, pieces: Path, built: Path, shaders: Path, out: Path) -> dict:
    """Writes the package into out from the pieces folder, export_scene.gd's folder (built) and the godot/ project
    (shaders: SHADERS' paths are under it); returns the summary that also goes to out/package.json. ValueError on a
    missing file or a leftover."""
    out = Path(out)
    ids = sorted({p["id"] for p in layout["pieces"]})
    lost = [i for i in ids if not (pieces / f"{i}.glb").is_file()]
    if lost:
        raise ValueError(f"{len(lost)} pieces not built (ship --build), e.g. {lost[0]}")
    if not (built / "ship.tscn").is_file():
        raise ValueError(f"no {built.as_posix()}/ship.tscn (export_scene.gd)")
    files: dict[str, dict] = {}

    def add(rel: str) -> None:
        files[rel] = {"sha256": house_export.sha256(out / rel), "bytes": (out / rel).stat().st_size}

    for pid in ids:
        rel = f"{ASSET_DIR}/{pid}.glb"
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pieces / f"{pid}.glb", out / rel)
        (out / f"{rel}.import").write_text(house_export.import_text(out / rel), encoding="utf-8", newline="\n")
        add(rel)
    for src, name in SHADERS.items():
        rel = f"{ASSET_DIR}/{name}"
        (out / rel).write_text((shaders / src).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        add(rel)
    texts = {f"{MATERIAL_DIR}/{f.name}": f for f in sorted(built.glob("*.tres"))}
    # the textures the pieces' import extracted beside them (the vents' normal maps) that the scene's materials use:
    # shipped from the art project's import (built's parent), where they are res://import/ship_<piece>_<image>.png
    for name in sorted({m.group(1) for f in [*texts.values(), built / "ship.tscn"]
                        for m in _PIECE.finditer(f.read_text(encoding="utf-8")) if m.group(1).endswith(".png")}):
        rel = f"{ASSET_DIR}/{name}"
        shutil.copyfile(built.parent / f"ship_{name}", out / rel)
        (out / f"{rel}.import").write_text(house_export.import_text(out / rel), encoding="utf-8", newline="\n")
        add(rel)
    texts[SCENE] = built / "ship.tscn"
    for rel, src in texts.items():
        text = relocate(src.read_text(encoding="utf-8"))
        bad = leftovers(text)
        if bad:
            raise ValueError(f"{rel}: {', '.join(bad)}")
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text, encoding="utf-8", newline="\n")
        add(rel)
    walk = layout["walk"]["points"][0]
    summary = {"format": FORMAT, "name": "ship", "version": layout["version"], "scene": f"res://{SCENE}",
               "root": "Ship", "pieces": len(ids), "placements": len(layout["place"]),
               "stations": stations(layout),
               "spawn": {"node": "Markers/Spawn", "at": [walk[0], walk[2], walk[1]], "yaw": 180.0},
               "files": files, "bytes": sum(f["bytes"] for f in files.values()), "questions": QUESTIONS}
    (out / "package.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    return summary
