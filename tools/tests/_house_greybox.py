"""The game's House greybox, pinned (art #34): what the tests compare the art's House against, read once from the
game's checkout and committed as tools/tests/fixtures/house_greybox.json, so the tests stay green when the game adds
a marker and when D:/prime-game is missing (docs/house.md "The game's greybox, pinned").

The snapshot holds the game commit it was read at, the design doc's room table (docs/design/house-map.md: title ->
[x, y, w, d]) and per greybox room scene (levels/house/rooms/*.tscn, placed by levels/house/house.tscn) its root,
origin, `metadata/size_m`, the Doors, Stations and Markers (name -> [x, h, z, groups]) and the names of its Marker3D
doors and stations. Refresh it after the art takes a game change on purpose:

    $PYTHON_BIN tools/tests/_house_greybox.py [--game D:/prime-game]          # rewrite the snapshot
    $PYTHON_BIN tools/tests/_house_greybox.py --check [--game D:/prime-game]  # list the drift, write nothing

test_house_greybox.py fails when the live checkout removed or moved what the snapshot holds (new rooms, markers and
rows are allowed: the art takes them with the next refresh)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

GAME = Path("D:/prime-game")
SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "house_greybox.json"
NODE = re.compile(r'\[node name="(\w+)" type="(\w+)" parent="(\w+)"((?:[^\]\[]|\[[^\]]*\])*)\]\n'
                  r'(?:transform = Transform3D\(([^)]*)\))?')
GROUPS = ("doors", "stations", "markers")


def parse(text: str) -> dict:
    """A room scene's root, size_m and its Doors, Stations and Markers: name -> (x, h, z, groups)."""
    root = re.search(r'\[node name="(\w+)" type="Node3D"(?: unique_id=\d+)?\]', text).group(1)
    size = re.search(r"metadata/size_m = Vector2i\((\d+), (\d+)\)", text)
    out = {"root": root, "size": (int(size.group(1)), int(size.group(2))) if size else None,
           "doors": {}, "stations": {}, "markers": {}}
    for m in NODE.finditer(text):
        name, _, parent, rest, tf = m.groups()
        if parent in ("Doors", "Stations", "Markers"):
            pos = tuple(round(float(v), 3) for v in (tf or "0,0,0,0,0,0,0,0,0,0,0,0").split(",")[9:12])
            groups = re.search(r"groups=\[([^\]]*)\]", rest)
            out[parent.lower()][name] = (*pos, groups.group(1) if groups else "")
    return out


def read(game: Path = GAME) -> dict:
    """The snapshot read live from the game's checkout."""
    house = game / "levels" / "house"
    text = (house / "house.tscn").read_text(encoding="utf-8")
    ids = {v: k for k, v in re.findall(r'path="res://levels/house/rooms/(\w+)\.tscn" id="(\w+)"', text)}
    rooms = {}
    for m in re.finditer(r'\[node name="\w+" parent="\w+"[^\]]*instance=ExtResource\("(\w+)"\)\]\n'
                         r'(?:transform = Transform3D\(([^)]*)\))?', text):
        rid = ids[m.group(1)]
        scene = (house / "rooms" / f"{rid}.tscn").read_text(encoding="utf-8")
        rooms[rid] = parse(scene)
        rooms[rid]["origin"] = tuple(round(float(v), 3) for v in (m.group(2) or "0," * 11 + "0").split(",")[9:12])
        for parent in ("Doors", "Stations"):
            rooms[rid][f"{parent.lower()}_marker3d"] = sorted(
                re.findall(rf'\[node name="(\w+)" type="Marker3D" parent="{parent}"', scene))
    doc = (game / "docs" / "design" / "house-map.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([^|]+?) \| (\d+), (\d+) \| (\d+) x (\d+) m \|", doc, re.M)
    head = subprocess.run(["git", "-C", str(game), "rev-parse", "HEAD"], capture_output=True, text=True)
    return {"game_commit": head.stdout.strip() if head.returncode == 0 else "",
            "design_rooms": {t: [int(x), int(y), int(w), int(d)] for t, x, y, w, d in rows},
            "rooms": rooms}


def _tuples(room: dict) -> dict:
    out = dict(room)
    for k in ("root", "origin", "size"):
        out[k] = tuple(room[k]) if isinstance(room[k], list) else room[k]
    for k in GROUPS:
        out[k] = {n: tuple(v) for n, v in room[k].items()}
    return out


def load(path: Path = SNAPSHOT) -> dict:
    """The committed snapshot, with the positions as tuples (as parse() gives them)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data["rooms"] = {rid: _tuples(r) for rid, r in data["rooms"].items()}
    return data


def drift(pinned: dict, live: dict) -> list[str]:
    """What the live greybox removed or moved against the pinned one; additions are not drift."""
    out = []
    for title, rect in pinned["design_rooms"].items():
        if live["design_rooms"].get(title) != rect:
            out.append(f"design doc: {title} {rect} -> {live['design_rooms'].get(title, 'removed')}")
    for rid, old in pinned["rooms"].items():
        new = live["rooms"].get(rid)
        if new is None:
            out.append(f"{rid}: removed")
            continue
        new = _tuples(json.loads(json.dumps(new)))
        for k in ("root", "origin", "size"):
            if new[k] != old[k]:
                out.append(f"{rid}: {k} {old[k]} -> {new[k]}")
        for k in GROUPS:
            for name, at in old[k].items():
                if new[k].get(name) != at:
                    out.append(f"{rid}: {k}/{name} {at} -> {new[k].get(name, 'removed')}")
        for k in ("doors_marker3d", "stations_marker3d"):
            gone = sorted(set(old[k]) - set(new[k]))
            if gone:
                out.append(f"{rid}: {k} removed {gone}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--game", type=Path, default=GAME, help="the game's checkout (default D:/prime-game)")
    ap.add_argument("--check", action="store_true", help="list the drift against the snapshot, write nothing")
    args = ap.parse_args(argv)
    if not (args.game / "levels" / "house" / "house.tscn").is_file():
        print(f"house greybox: no game checkout at {args.game.as_posix()}")
        return 2
    live = read(args.game)
    if args.check:
        found = drift(load(), live)
        print("\n".join(found) or f"house greybox: no drift against {live['game_commit'][:8]}")
        return 1 if found else 0
    text = re.sub(r"\[\s+([^\[\]{}]*?)\s+\]", lambda m: "[" + re.sub(r"\s*\n\s*", " ", m.group(1)) + "]",
                  json.dumps(live, indent=1, sort_keys=True))  # a list of numbers or names on one line
    SNAPSHOT.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(f"house greybox: {len(live['rooms'])} rooms, {len(live['design_rooms'])} design rows at "
          f"{live['game_commit'][:8]} -> {SNAPSHOT.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
