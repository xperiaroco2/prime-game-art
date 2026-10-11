"""The House export (tools/runner/house_export.py, docs/house.md "The export", art #119): the room scenes carry the
game's node names, `metadata/size_m`, the `Name` label and the Doors, Stations and Markers of the game's greybox rooms
(D:/prime-game/levels/house/rooms/*.tscn, read only; skipped when missing) with exactly the known differences of the
plan's mapping.md; no CSG, no GridMap, real-time lights without shadows, every path under res://assets/environment/.
Pure Python: the scenes are built in memory, no GLB is copied."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from runner import house_attic as HA
from runner import house_dressing as HD
from runner import house_export as X
from runner import house_layout as H
from runner import house_lights as HL

DATA = H.load()
PLAN = H.plan(DATA)
GAME = Path("D:/prime-game/levels/house")
# mapping.md's known differences (2026-10-11), waiting on the game's answers G1 and G2 (prime-game #523; art task A4):
# the attic is the free-roof attic on the whole footprint and holds the roof's stations; the art moved three door
# markers onto the whole-metre wall grid and the storage's Package07 to the shelf it sits on.
KNOWN = {
    "roof": "game only",
    "attic": {"origin", "size", "doors", "stations", "markers"},
    "garage": {"doors": {"Door3"}},
    "landing": {"doors": {"Door6"}},
    "study": {"doors": {"Door1"}},
    "storage": {"markers": {"Package07"}},
}
NODE = re.compile(r'\[node name="(\w+)" type="(\w+)" parent="(\w+)"((?:[^\]\[]|\[[^\]]*\])*)\]\n'
                  r'(?:transform = Transform3D\(([^)]*)\))?')


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


def game_rooms() -> dict:
    house = (GAME / "house.tscn").read_text(encoding="utf-8")
    ids = dict(re.findall(r'path="res://levels/house/rooms/(\w+)\.tscn" id="(\w+)"', house))
    ids = {v: k for k, v in ids.items()}
    out = {}
    for m in re.finditer(r'\[node name="\w+" parent="\w+"[^\]]*instance=ExtResource\("(\w+)"\)\]\n'
                         r'(?:transform = Transform3D\(([^)]*)\))?', house):
        rid = ids[m.group(1)]
        out[rid] = parse((GAME / "rooms" / f"{rid}.tscn").read_text(encoding="utf-8"))
        out[rid]["origin"] = tuple(round(float(v), 3) for v in (m.group(2) or "0," * 11 + "0").split(",")[9:12])
    return out


def diff(game: dict, art: dict) -> dict:
    """What differs between a game room and an art room: field -> True, or for a marker group the names that differ."""
    out = {}
    for k in ("root", "origin", "size"):
        if game[k] != art[k]:
            out[k] = True
    for k in ("doors", "stations", "markers"):
        names = {n for n in game[k].keys() | art[k].keys() if game[k].get(n) != art[k].get(n)}
        if names:
            out[k] = names
    return out


class HouseExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenes = X.scenes(DATA, PLAN, {}, [])
        cls.unplaced = cls.scenes.pop("")
        cls.art = {}
        for lv in DATA["levels"]:
            for r in lv["rooms"]:
                cls.art[r["id"]] = dict(parse(cls.scenes[r["id"]]["text"]),
                                        origin=(r["rect"][0], lv["floor_y"], r["rect"][1]))

    def test_every_room_has_its_scene_size_and_label(self):
        self.assertEqual(len(self.scenes), sum(len(lv["rooms"]) for lv in DATA["levels"]))
        for rid, s in self.scenes.items():
            self.assertIn("metadata/size_m = Vector2i(", s["text"], rid)
            self.assertIn('[node name="Name" type="Label3D" parent="."]', s["text"], rid)
        self.assertEqual(self.unplaced, [])

    def test_against_the_games_greybox(self):
        if not (GAME / "house.tscn").is_file():
            self.skipTest("the game repo is not at D:/prime-game")
        game = game_rooms()
        found = {rid: "game only" for rid in game.keys() - self.art.keys()}
        found |= {rid: "art only" for rid in self.art.keys() - game.keys()}
        for rid in game.keys() & self.art.keys():
            d = diff(game[rid], self.art[rid])
            if d:
                found[rid] = d
        expected = {rid: (set(v) if rid == "attic" else v) for rid, v in KNOWN.items()}
        found = {rid: (set(v) if rid == "attic" else v) for rid, v in found.items()}
        self.assertEqual(found, expected)
        self.assertEqual(len(game), 35)

    def test_dressed_scenes_are_game_safe(self):
        paths = [p for p in HD.spec_paths(DATA["settings"]) if p.is_file()]
        rep = HD.check(DATA, HD.load(H.LAYOUT_DIR / DATA["settings"]["dressing_dir"]), HD.catalogue(paths))
        lights = HL.load(H.LAYOUT_DIR / "lights.toml")
        scenes = X.scenes(DATA, PLAN, rep["rooms"], HL.plan(lights, DATA), have=lambda pid: pid != "door_leaf")
        scenes.pop("")
        omni = 0
        for rid, s in scenes.items():
            t = s["text"]
            self.assertNotRegex(t, r'type="(CSG\w+|GridMap|CollisionPolygon3D|RigidBody3D|SpotLight3D)"', rid)
            for path in re.findall(r'path="([^"]+)"', t):
                self.assertRegex(path, r"^res://assets/environment/house_(kit|props)/\w+\.glb$", rid)
            omni += t.count('type="OmniLight3D"')
            self.assertEqual(t.count('type="OmniLight3D"'), t.count("shadow_enabled = false"), rid)
        fixtures = [f for f in HL.plan(lights, DATA) if f["type"] != "moon"]
        self.assertEqual(omni, len(fixtures))
        self.assertIn('[node name="door_leaf_1" type="Marker3D" parent="Placeholders"]', scenes["hallway"]["text"])

    def test_attic_holds_its_old_things(self):
        z = HA.load("attic")
        dz = X.attic_dressing(z)
        self.assertEqual(len(dz["resolved"]), len(z["items"]))
        rx, ry, w, d = z["rect"]
        for r in dz["resolved"]:
            x, h, y = r["at"]
            self.assertTrue(0 <= x <= w and 0 <= y <= d and h == 0, r)
        scenes = X.scenes(DATA, PLAN, {"attic": dz}, [], have=lambda pid: pid != "old_wardrobe")
        t = scenes["attic"]["text"]
        self.assertIn('[node name="trunk_1" parent="Dressing"', t)
        self.assertIn('[node name="old_wardrobe_1" type="Marker3D" parent="Placeholders"]', t)

    def test_packages_split_the_rooms(self):
        pk = X.packages(DATA)
        seen = [r["id"] for n in pk for _, r in X.rooms_of(DATA, pk[n])]
        self.assertEqual(sorted(seen), sorted(self.art))  # every room in exactly one package
        self.assertEqual(X.rooms_of(DATA, pk[1]), [])

    def test_write_copies_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw, out = Path(tmp) / "raw", Path(tmp) / "out"
            kit = raw / DATA["settings"]["kit_dir"]
            (kit / "textures").mkdir(parents=True)
            ground = X.scenes(DATA, PLAN, {}, [], X.packages(DATA)[2])
            ground.pop("")
            for pid in {pid for s in ground.values() for pid in s["kit"]}:
                (kit / f"{pid}.glb").write_bytes(b"glTF")
            for t in X.settings(DATA)["kit_textures"]:
                (kit / "textures" / t).write_bytes(b"png")
            summary = X.write(DATA, PLAN, {}, [], out, raw, {}, 2)
            self.assertIn("levels/house/rooms/wc.tscn", summary["files"])
            glb = out / "assets/environment/house_kit" / f"{self.scenes['wc']['kit'][0]}.glb"
            self.assertTrue(glb.is_file())
            self.assertIn('nodes/root_type=""', (glb.parent / (glb.name + ".import")).read_text(encoding="utf-8"))
            self.assertTrue((out / "package.json").is_file())


if __name__ == "__main__":
    unittest.main()
