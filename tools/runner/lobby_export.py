"""The lobby hall's game-ready package (`lobby --export DIR`, art #356 step 5b, docs/lobby.md "The export"): plain
Python, no Godot.

godot/lobby/export_scene.gd assembles the hall in the art's Godot project (the pieces staged as
res://import/lobby_<id>.glb, the Earth's textures as res://import/lobby_earth/, art #263's ship package as
res://import/ship_pkg/) and saves it as res://import/lobby_export/lobby_hall.tscn with its shared .tres files; this
module turns that into the package, shaped like the game's tree (its ARCHITECTURE 11.1), as the ship's export
(ship_export.py):

  assets/environment/lobby/<id>.glb (+ a minimal .import, 11.2), earth_sky.gdshader, earth_object.gdshader,
                           window_glass.gdshader, earth/earth_<map>.jpg (+ .import), materials/lobby_env.tres,
                           earth_object.tres, window_glass.tres
  levels/lobby/lobby_hall.tscn   the hall, the ship instanced from res://levels/ship/ship.tscn (the ship package,
                                 never copied), the Earth, the light rig, probes and the ten spawn markers
  levels/lobby/lobby_hall.gd     the root's level script (step 5c2): frees the ship package's switched-off nodes on
                                 _ready and has the reflection probes capture again (godot/lobby/lobby_hall.gd)
  package.json             files with SHA-256 and bytes, the spawns, the ship package it needs, the open questions

relocate() moves every res:// path from the art project's to the package's (the ship package's to its own game
paths) and drops the uids."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import house_export

FORMAT = 1
ASSET_DIR = "assets/environment/lobby"
EARTH_DIR = f"{ASSET_DIR}/earth"
MATERIAL_DIR = f"{ASSET_DIR}/materials"
SCENE = "levels/lobby/lobby_hall.tscn"
SHIP_SCENE = "levels/ship/ship.tscn"
LEVEL_SCRIPT = "levels/lobby/lobby_hall.gd"   # the package's one script, on the scene's root (step 5c2)
LEVEL_SCRIPT_SRC = "lobby/lobby_hall.gd"      # its source under godot/
SHIP_PREFIXES = ("assets/environment/ship/", "levels/ship/")
BUILT = "lobby_export"   # godot/import/lobby_export/: export_scene.gd's output
EARTH_STAGE = "lobby_earth"   # godot/import/lobby_earth/: the Earth's textures, staged with the package's .import
SHIP_STAGE = "ship_pkg"       # godot/import/ship_pkg/: lobby.py stage_package
SHADERS = {"lobby/earth_sky.gdshader": "earth_sky.gdshader", "lobby/earth_object.gdshader": "earth_object.gdshader",
           "lobby/window_glass.gdshader": "window_glass.gdshader"}
SPAWN_YAW = 180.0   # a marker's forward (-Z) turned to +Z: the window (south)
# the Earth's textures: imported VRAM compressed (BPTC/BC7 on desktop, high quality) with mipmaps
EARTH_IMPORT = ["compress/mode=2", "compress/high_quality=true", "mipmaps/generate=true"]
CREDIT = "Earth imagery: NASA"
QUESTIONS = [
    "L1: the ship is an instance of the ship package's res://levels/ship/ship.tscn (assets/environment/ship/HANDOFF.md), "
    "never a copy: the game needs the ship package at its paths. What the hall must not have is saved switched off "
    "(a packed scene cannot remove a node of an instance: Ship/Clearing hidden and disabled, Ship/Environment's "
    "WorldEnvironment on the hall's environment, the suns under Ship/Lights hidden), and the root's level script "
    "res://levels/lobby/lobby_hall.gd frees them on _ready (its ship_free paths) and has the reflection probes capture "
    "again a frame later, as the art's assembly does. Keep the script on LobbyHall; a game script for the lobby "
    "extends it and calls super._ready().",
    "L2: the jaw nose is saved shut (jaw_lower and jaw_upper at 0 deg) by overrides; Ship/Nose/AnimationPlayer still "
    "holds open/close: the lobby never plays them. Its pose is the scene's, so nothing needs to run at load.",
    "L3: behind the shut nose and the closed doors the package's whole interior is still drawn when in view (about "
    "3200 draw calls in the views that see the ship, HANDOFF 'Cost'); an occluder or hiding Ship's interior pieces in "
    "the lobby is the game's call.",
    "L4: the ten spawn markers (Markers/Spawn0..9) stand at z 2.5, 0.76 m outside the floor ring (r 15 round the "
    "closed ship's middle, z -13.26); the ring is the floor's inlay only, no rule of the game.",
    "L5: the Earth is the object Earth/EarthObject (earth_object.gdshader in far mode: every ray from far_eye, the shell "
    "follows the camera), so it stays at infinity: never parent it to anything that moves, never scale it; the camera's "
    "far plane must reach LobbyHall's metadata camera_far_m. The sky (lobby_env.tres) draws the stars and, in its "
    "cubemap pass, the Earth for the probes and reflections.",
    "L6: the glow surfaces (the hall's lamps, strips, ring and the ship's glow times ship_emit 0.3) are material "
    "overrides inside the pieces' instances; the ship's meshes draw on render layer 11 (ship light K1: the hall's "
    "pendants and Earth light skip it, its own key, rim, back and bounce suns light only it): a player model must stay "
    "off layer 11.",
    "L7: the positional shadow atlas: the art's shots use 4096 with every quadrant subdivided 4 (the pendants' "
    "shadowed spots); the game's project settings decide (HANDOFF 'Light').",
    "L8: the credit line \"Earth imagery: NASA\" goes in the game's credits (NASA-PD, sources/nasa_earth_lobby.toml).",
    "Imports: each file's .import holds only the package's options; the game's editor regenerates the .import files "
    "(and the uids) on its first import: commit the regenerated ones.",
]
_UID = re.compile(r' uid="uid://[a-z0-9]+"')
_PIECE = re.compile(r"res://import/lobby_([a-z0-9_]+\.(?:glb|png))")  # a piece, a texture its import extracted


def earth_import_text() -> str:
    return "\n".join(["[remap]", "", 'importer="texture"', 'type="CompressedTexture2D"', "", "[params]", "",
                      *EARTH_IMPORT]) + "\n"


def relocate(text: str) -> str:
    """A scene or resource saved in the art project, with its paths moved to the package's and its uids dropped."""
    text = text.replace(f"res://import/{BUILT}/", f"res://{MATERIAL_DIR}/")
    text = text.replace(f"res://import/{EARTH_STAGE}/", f"res://{EARTH_DIR}/")
    text = text.replace(f"res://import/{SHIP_STAGE}/", "res://")
    text = text.replace(f"res://{LEVEL_SCRIPT_SRC}", f"res://{LEVEL_SCRIPT}")
    text = _PIECE.sub(lambda m: f"res://{ASSET_DIR}/{m.group(1)}", text)
    for src, name in SHADERS.items():
        text = text.replace(f"res://{src}", f"res://{ASSET_DIR}/{name}")
    return _UID.sub("", text)


def leftovers(text: str, level_script: bool = False) -> list[str]:
    """What a relocated text must not hold: an art-project path, a script, a sub-resource path of an imported file,
    any res:// path outside the package and the ship package. level_script (the scene): LEVEL_SCRIPT, used once, is
    allowed and required."""
    allowed = "|".join(re.escape(p) for p in (f"{ASSET_DIR}/", "levels/lobby/", *SHIP_PREFIXES))
    bad = []
    if level_script:
        ext = re.search(rf'^\[ext_resource type="Script" path="res://{re.escape(LEVEL_SCRIPT)}" id="([^"]+)"\]\n?',
                        text, re.M)
        use = rf'^script = ExtResource\("{re.escape(ext.group(1))}"\)\n?' if ext else None
        if not ext or len(re.findall(use, text, re.M)) != 1:
            bad.append("no level script on the root")
        else:
            text = re.sub(use, "", text.replace(ext.group(0), "", 1), count=1, flags=re.M)
    for pat, why in ((r"res://import/", "an art-project import path"), (r'"res://lobby/', "an art-project lobby path"),
                     (r'type="Script"', "a script"), (r"^script = ", "a script"), (r'path="[^"]*::', "a sub-resource path"),
                     (rf'"res://(?!{allowed})', "a path outside the package")):
        if re.search(pat, text, re.M) and why not in bad:
            bad.append(why)
    return bad


def spawns(layout: dict) -> list[dict]:
    """The ten spawn markers: name, at (x, y, z), yaw (deg; the marker's -Z forward then faces +Z, the window)."""
    z = float(layout["floor"]["spawns_z"])
    return [{"name": f"Spawn{i}", "at": [float(x), 0.0, z], "yaw": SPAWN_YAW}
            for i, x in enumerate(layout["floor"]["spawns_x"])]


def piece_ids(layout: dict) -> list[str]:
    """The hall's pieces, each GLB once (the door is placed four times)."""
    return sorted(p["id"] for p in layout["pieces"])


def write(layout: dict, pieces: Path, built: Path, shaders: Path, earth: dict[str, Path], ship_meta: dict,
          ship_dir: str, out: Path) -> dict:
    """Writes the package into out from the pieces folder, export_scene.gd's folder (built), the godot/ project
    (shaders: SHADERS' paths are under it) and the Earth's textures (map -> its JPEG); returns the summary that also
    goes to out/package.json. ValueError on a missing file or a leftover."""
    out = Path(out)
    ids = piece_ids(layout)
    lost = [i for i in ids if not (pieces / f"{i}.glb").is_file()]
    if lost:
        raise ValueError(f"{len(lost)} pieces not built (lobby --build), e.g. {lost[0]}")
    if not (built / "lobby_hall.tscn").is_file():
        raise ValueError(f"no {built.as_posix()}/lobby_hall.tscn (export_scene.gd)")
    files: dict[str, dict] = {}

    def add(rel: str) -> None:
        files[rel] = {"sha256": house_export.sha256(out / rel), "bytes": (out / rel).stat().st_size}

    def copy(src: Path, rel: str, import_text: str | None) -> None:
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / rel)
        if import_text is not None:
            (out / f"{rel}.import").write_text(import_text, encoding="utf-8", newline="\n")
        add(rel)

    for pid in ids:
        rel = f"{ASSET_DIR}/{pid}.glb"
        copy(pieces / f"{pid}.glb", rel, None)
        (out / f"{rel}.import").write_text(house_export.import_text(out / rel), encoding="utf-8", newline="\n")
    for name, src in sorted(earth.items()):
        copy(src, f"{EARTH_DIR}/{name}", earth_import_text())
    for src, name in SHADERS.items():
        rel = f"{ASSET_DIR}/{name}"
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text((shaders / src).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        add(rel)
    texts = {f"{MATERIAL_DIR}/{f.name}": f for f in sorted(built.glob("*.tres"))}
    # the textures the pieces' import extracted that the scene's material overrides use (res://import/lobby_<file>.png)
    for name in sorted({m.group(1) for f in [*texts.values(), built / "lobby_hall.tscn"]
                        for m in _PIECE.finditer(f.read_text(encoding="utf-8")) if m.group(1).endswith(".png")}):
        rel = f"{ASSET_DIR}/{name}"
        copy(built.parent / f"lobby_{name}", rel, None)
        (out / f"{rel}.import").write_text(house_export.import_text(out / rel), encoding="utf-8", newline="\n")
    texts[SCENE] = built / "lobby_hall.tscn"
    if not (shaders / LEVEL_SCRIPT_SRC).is_file():
        raise ValueError(f"no level script {(shaders / LEVEL_SCRIPT_SRC).as_posix()}")
    (out / LEVEL_SCRIPT).parent.mkdir(parents=True, exist_ok=True)
    (out / LEVEL_SCRIPT).write_text((shaders / LEVEL_SCRIPT_SRC).read_text(encoding="utf-8"), encoding="utf-8",
                                    newline="\n")
    add(LEVEL_SCRIPT)
    for rel, src in texts.items():
        text = relocate(src.read_text(encoding="utf-8"))
        bad = leftovers(text, level_script=rel == SCENE)
        if bad:
            raise ValueError(f"{rel}: {', '.join(bad)}")
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text, encoding="utf-8", newline="\n")
        add(rel)
    e = layout["earth"]
    summary = {"format": FORMAT, "name": "lobby", "version": layout["version"], "scene": f"res://{SCENE}",
               "root": "LobbyHall", "level_script": f"res://{LEVEL_SCRIPT}", "pieces": ids, "placements": len(layout["place"]) + len(layout["door"]["doors"]),
               "spawns": spawns(layout),
               "ship": {"node": "Ship", "scene": f"res://{SHIP_SCENE}", "package": ship_dir,
                        "package_version": ship_meta.get("version"), "package_bytes": ship_meta.get("bytes"),
                        "origin": layout["ship"]["origin"], "switched_off": layout["ship"]["package"].get("free", [])},
               "earth": {"node": "Earth/EarthObject", "variant": e["variant"], "distance": e["distance"],
                         "snow": e.get("snow", {}).get("set"), "credit": CREDIT, "licence": "NASA-PD",
                         "source": "sources/nasa_earth_lobby.toml"},
               "light": {"mood": layout["light"]["mood"], "ship": layout["light"]["ship"]["set"]},
               "files": files, "bytes": sum(f["bytes"] for f in files.values()), "questions": QUESTIONS}
    (out / "package.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    return summary
