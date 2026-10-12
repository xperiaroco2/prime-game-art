"""The House export (tools/runner/house_export.py, docs/house.md "The export", art #119): the room scenes carry the
game's node names, `metadata/size_m`, the `Name` label and the Doors, Stations and Markers of the game's greybox rooms
(D:/prime-game/levels/house/rooms/*.tscn, read only; skipped when missing) with exactly the known differences of the
plan's mapping.md; no CSG, no GridMap, real-time lights without shadows, every path under res://assets/environment/.
Pure Python: the scenes are built in memory, no GLB is copied."""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from runner import house_attic as HA
from runner import house_dressing as HD
from runner import house_export as X
from runner import house_layout as H
from runner import common, house_lights as HL
from runner.commands import _house_export

DATA = H.load()
PLAN = H.plan(DATA)
GAME = Path("D:/prime-game/levels/house")
# mapping.md's known differences (2026-10-11), waiting on the game's answers G1 and G2 (prime-game #523; art task A4):
# the attic is the free-roof attic on the whole footprint and holds the roof's stations; the art moved three door
# markers onto the whole-metre wall grid and the storage's Package07 to the shelf it sits on. The game's three
# provisional spawn_zone markers (prime-game #651, #681: Zone01 in the yard, Zone02 in the garden, Zone03 on the
# landing) came after the art's rooms and are not in them yet.
KNOWN = {
    "roof": "game only",
    "attic": {"origin": True, "size": True, "doors": {"Door1"}, "stations": {"Loot", "HidingSpots", "Lookout"},
              "markers": {"Knife3"}},
    "garage": {"doors": {"Door3"}},
    "garden": {"markers": {"Zone02"}},
    "landing": {"doors": {"Door6"}, "markers": {"Zone03"}},
    "yard": {"markers": {"Zone01"}},
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
        self.assertEqual(found, KNOWN)
        self.assertEqual(len(game), 35)

    def test_dressed_scenes_are_game_safe(self):
        rep = dressed()
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

    def test_the_free_roof_and_the_attic_carry_surfaces(self):
        """#126: the attic's library props keep their collision (frames and rugs none), its rolled carpets are
        carpet, the roof's pieces a ray from over the ridge meets are tagged and stay so over a rug, and the check
        rays the roof's rect with its margin."""
        dz = X.attic_dressing(HA.load("attic"))
        coll = {r["id"]: r["collision"] for r in dz["resolved"]}
        self.assertEqual((coll["picture_frame"], coll["rug"]), ("none", "none"))
        self.assertNotEqual(coll["trunk"], "none")
        pk = X.packages(DATA)[5]
        built = X.scenes(DATA, PLAN, {"attic": dz}, [], pk)
        built.pop("")
        attic = built["attic"]
        self.assertFalse([n for n in attic["hide"] if n.startswith(("picture_frame", "rug_"))], attic["hide"])
        self.assertRegex(attic["text"], r'\[node name="rolled_carpet_1" parent="Dressing"[^\[]*metadata/surface = "carpet"')
        for pid in ("roof_pitched_2x2", "roof_pitched_eave_2m", "roof_pitched_ridge_2m", "chimney_attic",
                    "chimney_attic_n", "dormer_gable"):
            self.assertIn(X.surface_of(DATA, pid), X.SURFACES, pid)
        roofs = re.findall(r'\[node name="(roof_pitched\w+)" parent="Shell"[^\n]*\n[^\n]*\nmetadata/surface = "concrete"',
                           attic["text"])
        self.assertTrue(roofs)
        self.assertIsNone(X.prop_surface(DATA, "crate"))
        req = X.check_request(DATA, built, {pid for b in built.values() for pid in b["kit"]})
        room = next(r for r in req["rooms"] if r["id"] == "attic")
        x, y, w, d = (float(v) for v in next(lv for lv in DATA["levels"] if lv["level"] == "attic")["roofs"][0]["rect"])
        m = X.ROOF_MARGIN
        self.assertEqual(room["roof"], [x - m, y - m, w + 2 * m, d + 2 * m])
        self.assertEqual(room["roof_rect"], [x, y, w, d])
        self.assertGreater(room["roof_from"], 6.0)
        self.assertEqual(room["roof_pieces"], list(X.ROOF_PIECES))
        shell = re.findall(r'\[node name="([a-z_]+?)(?:_\d+)?" parent="Shell"', attic["text"])
        self.assertTrue([n for n in shell if n.startswith(X.ROOF_PIECES) and n.startswith("roof_pitched")])
        self.assertFalse([n for n in shell if n.startswith("floor") and n.startswith(X.ROOF_PIECES)])

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

    def test_floors_carry_the_games_surfaces(self):
        rep = dressed()
        scenes = X.scenes(DATA, PLAN, rep["rooms"], [])
        scenes.pop("")
        found = set()
        for rid, s in scenes.items():
            for m in re.finditer(r'\[node name="(\w+)" parent="Shell" instance=[^\]]*\]\n[^\n]*((?:\nmetadata/[^\n]*)*)',
                                 s["text"]):
                name, meta = m.groups()
                surface = re.search(r'metadata/surface = "(\w+)"', meta)
                if name.startswith(("floor_", "slab_", "stairs_")):
                    self.assertTrue(surface, f"{rid}: {name}")
                if surface:
                    self.assertIn(surface.group(1), X.SURFACES, f"{rid}: {name}")
                    self.assertIn(name, s["walkable"], rid)
                    found.add(surface.group(1))
        self.assertEqual(found, {"wood", "concrete", "carpet"})  # grass: the plot's ground (package 7's set)
        self.assertIn('metadata/surface = "carpet"', scenes["living_room"]["text"])  # under its rug
        self.assertEqual(X.surface_of(DATA, "floor_lino_2x2"), "concrete")
        self.assertEqual(X.surface_of(DATA, "ground_tile"), "grass")
        self.assertIsNone(X.surface_of(DATA, "wall_storey_2m_int"))

    def test_check_request_keeps_the_packages_walks(self):
        built = X.scenes(DATA, PLAN, {}, [], X.packages(DATA)[2])
        built.pop("")
        req = X.check_request(DATA, built, {pid for s in built.values() for pid in s["kit"]})
        names = [w["name"] for w in req["walks"]]
        self.assertTrue(names and not any("garage" in n for n in names), names)
        self.assertIn("ground:garage>yard@54,44", req["outside"])
        self.assertEqual({r["id"] for r in req["rooms"]}, set(built))
        self.assertTrue(all(v in X.SURFACES for v in req["pieces"].values()))

    def test_packages_1_2_7_8_write_with_their_lamps_and_warn_on_stale_files(self):
        lights = HL.plan(HL.load(H.LAYOUT_DIR / "lights.toml"), DATA)
        with tempfile.TemporaryDirectory() as tmp:
            raw = fake_raw(Path(tmp) / "raw")
            for n in (1, 2, 7, 8):
                out = Path(tmp) / f"p{n}"
                summary = X.write(DATA, PLAN, {}, lights, out, raw, {}, n)
                rooms = {r["id"] for _, r in X.rooms_of(DATA, X.packages(DATA)[n])}
                self.assertEqual(set(summary["rooms"]), rooms, n)
                lamps = sum(1 for f in lights if f["room"] in rooms and f["type"] != "moon")
                self.assertIn(f"({lamps} in this package)", summary["questions"][-1], n)
                self.assertTrue(any(".import files" in q for q in summary["questions"]), n)
                self.assertEqual(summary["stale"], [], n)
                files = set(summary["files"])
                if n == 1:
                    self.assertIn("assets/environment/house_kit/set_d.png", files)
                    self.assertEqual(summary["surfaces"]["floor_boards_2x2"], "wood")
                if n == 7:
                    self.assertIn("assets/environment/house_outdoor/outdoor.glb", files)
                    self.assertIn("assets/environment/house_garden/rose.glb", files)
                    self.assertIn("plot", summary)
                    self.assertTrue(summary["plot"]["scene"].startswith("res://"))
                if n == 8:
                    self.assertEqual(rooms, set())
                    self.assertIn("assets/environment/house_props/task_box.glb", files)
            old = Path(tmp) / "p2" / "assets/environment/house_kit/old_piece.glb"
            old.write_bytes(b"glTF")
            summary = X.write(DATA, PLAN, {}, lights, Path(tmp) / "p2", raw, {}, 2)
            self.assertEqual(summary["stale"], ["assets/environment/house_kit/old_piece.glb"])
            self.assertTrue(old.is_file())  # warned, never deleted


def dressed() -> dict:
    paths = [p for p in HD.spec_paths(DATA["settings"]) if p.is_file()]
    return HD.check(DATA, HD.load(H.LAYOUT_DIR / DATA["settings"]["dressing_dir"]), HD.catalogue(paths))


def fake_raw(raw: Path) -> Path:
    """Stand-in raw files: every kit piece the house uses and its textures, a task prop, the sets' files."""
    kit = raw / DATA["settings"]["kit_dir"]
    (kit / "textures").mkdir(parents=True)
    every = X.scenes(DATA, PLAN, {}, [])
    every.pop("")
    for pid in {pid for s in every.values() for pid in s["kit"]} | {"floor_boards_2x2"}:
        (kit / f"{pid}.glb").write_bytes(b"glTF")
    for t in X.settings(DATA)["kit_textures"]:
        (kit / "textures" / t).write_bytes(b"png")
    task = raw / DATA["settings"]["prop_dirs"][0]
    task.mkdir(parents=True)
    (task / "task_box.glb").write_bytes(b"glTF")
    for sid, s in X.settings(DATA)["sets"].items():
        (raw / s["dir"]).mkdir(parents=True, exist_ok=True)
        for pat in s["files"]:
            (raw / s["dir"] / pat.replace("*", "rose" if sid == "house_garden" else "a")).write_bytes(b"x")
    garden = raw / X.settings(DATA)["plot"]["garden"]  # the garden's build, empty: the plot scene's input (#128)
    garden.parent.mkdir(parents=True, exist_ok=True)
    garden.write_text('{"roof": [], "props": [], "scatter": []}', encoding="utf-8")
    return raw


class PackageLines(unittest.TestCase):
    def test_the_report_counts_misses_and_names_hits_without_a_surface(self):
        pkg = {"pieces": {"floor_a": True, "wall_b": False}, "rays": 6, "surfaces": {"wood": 4, "none": 2},
               "walks": [{"arrived": True}, {"arrived": False}], "roof_rays": 5,
               "roof_surfaces": {"concrete": 2, "none": 1, "miss": 2},
               "none_at": {"Attic/Dressing/crate_1/Body": "attic roof", "Boiler/Dressing/boiler_1/Body": "boiler_room",
                           "Boiler/Dressing/boiler_1/Body2": "boiler_room", "Boiler/Fixtures/lamp_2": "boiler_room",
                           "Loose/Body": "attic"}}
        lines = _house_export.package_lines(pkg)
        self.assertEqual(lines, [
            '  package: 1/2 kit GLBs with a surface hold a collider; 6 rays down, surfaces hit {"none": 2, "wood": 4}; '
            "1/2 walks of the 1.36 m capsule arrive",
            '  roof: 5 rays down from over the ridge, first hits {"concrete": 2, "miss": 2, "none": 1} (miss: past the '
            "eaves)",
            "  hits without a surface (not the shell): attic: Loose/Body; attic roof: crate_1; boiler_room: boiler_1, "
            "lamp_2"])

    def test_the_plot_line_counts_its_rays_by_surface(self):
        lines = _house_export.package_lines({"rays": 0, "surfaces": {}, "plot_rays": 4,
                                             "plot_surfaces": {"grass": 2, "hole": 1, "concrete": 1}})
        self.assertEqual(lines[1], '  plot: 4 rays down over the ground, surfaces hit {"concrete": 1, "grass": 2, '
                                   "\"hole\": 1} (hole: another package's floor)")

    def test_no_roof_and_no_unknown_surface_print_no_line(self):
        lines = _house_export.package_lines({"rays": 2, "surfaces": {"wood": 2}, "roof_rays": 0, "none_at": {}})
        self.assertEqual(len(lines), 1)


# A room that breaks every rule of the export check: a floor without a surface (the ray finds it), a walkable piece
# and a prop with a collider listed but holding none, a CSG box, a wall across the capsule's walk, and a roof over
# x 2..6 only (with a crate on it), so the roof's rays over x 0..2 fall through the hole onto floor_ok.
BROKEN = """[gd_scene format=3]

[sub_resource type="BoxShape3D" id="floor"]
size = Vector3(2, 0.2, 4)

[sub_resource type="BoxShape3D" id="wall"]
size = Vector3(0.2, 3, 4)

[sub_resource type="BoxShape3D" id="roof"]
size = Vector3(4, 0.2, 4)

[sub_resource type="BoxShape3D" id="crate"]
size = Vector3(1, 0.4, 1)

[node name="Bad" type="Node3D"]
metadata/size_m = Vector2i(6, 4)

[node name="Shell" type="Node3D" parent="."]

[node name="floor_ok" type="Node3D" parent="Shell"]
metadata/surface = "wood"

[node name="Body" type="StaticBody3D" parent="Shell/floor_ok"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 1, -0.1, 2)

[node name="Shape" type="CollisionShape3D" parent="Shell/floor_ok/Body"]
shape = SubResource("floor")

[node name="floor_bare" type="Node3D" parent="Shell"]

[node name="Body" type="StaticBody3D" parent="Shell/floor_bare"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 3, -0.1, 2)

[node name="Shape" type="CollisionShape3D" parent="Shell/floor_bare/Body"]
shape = SubResource("floor")

[node name="floor_hollow" type="Node3D" parent="Shell"]
metadata/surface = "wood"

[node name="roof_slab" type="Node3D" parent="Shell"]
metadata/surface = "concrete"

[node name="Body" type="StaticBody3D" parent="Shell/roof_slab"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 4, 3.2, 2)

[node name="Shape" type="CollisionShape3D" parent="Shell/roof_slab/Body"]
shape = SubResource("roof")

[node name="Dressing" type="Node3D" parent="."]

[node name="crate_1" type="Node3D" parent="Dressing"]

[node name="Wall" type="StaticBody3D" parent="Dressing"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 3.5, 1.5, 2)

[node name="Shape" type="CollisionShape3D" parent="Dressing/Wall"]
shape = SubResource("wall")

[node name="RoofCrate" type="StaticBody3D" parent="Dressing"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 5, 3.5, 2)

[node name="Shape" type="CollisionShape3D" parent="Dressing/RoofCrate"]
shape = SubResource("crate")

[node name="Box" type="CSGBox3D" parent="Dressing"]
"""


def _glb(nodes: list[dict], meshes: list[dict], materials: list[str]) -> bytes:
    """A GLB with only its JSON chunk (enough for house_export.set_surfaces)."""
    doc = json.dumps({"scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
                      "materials": [{"name": m} for m in materials]}).encode()
    doc += b" " * (-len(doc) % 4)
    return b"glTF" + (2).to_bytes(4, "little") + (20 + len(doc)).to_bytes(4, "little") \
        + len(doc).to_bytes(4, "little") + b"JSON" + doc


class WallPaints(unittest.TestCase):
    """#132: the kit's set material with the house's paints travels with the room scenes."""

    def test_set_surfaces_reads_the_stand_in_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = Path(tmp) / "wall.glb"
            glb.write_bytes(_glb([{"name": "wall", "mesh": 0}, {"name": "leaf", "mesh": 1, "translation": [0.5, 0, 0]},
                                  {"name": "wall_col0-convcolonly", "mesh": 2}],
                                 [{"primitives": [{"material": 0}, {"material": 1}]},
                                  {"primitives": [{"material": 1}]}, {"primitives": [{}]}],
                                 ["kit_glass-vcol", "kit_set-vcol"]))
            self.assertEqual(X.set_surfaces(glb), [{"node": "wall", "at": [0, 0, 0], "surfaces": [1]},
                                                   {"node": "leaf", "at": [0.5, 0, 0], "surfaces": [0]}])
            glb.write_bytes(b"glTF")
            self.assertEqual(X.set_surfaces(glb), [])
            glb.write_bytes(_glb([{"name": "wall", "mesh": 0, "rotation": [0, 0.7071, 0, 0.7071]}],
                                 [{"primitives": [{"material": 0}]}], ["kit_set-vcol"]))
            with self.assertRaises(ValueError):
                X.set_surfaces(glb)

    def test_the_scene_puts_the_material_on_every_set_surface_with_its_plan_pose(self):
        lv, room = next((lv, r) for lv in DATA["levels"] for r in lv["rooms"] if r["id"] == "kitchen")
        pl = PLAN["levels"][DATA["levels"].index(lv)]
        pieces = pl["pieces"]["kitchen"]
        surfaces = {p["id"]: [{"node": p["id"], "at": [0, 0, 0], "surfaces": [0]}] for p in pieces}
        text = X.room_scene(DATA, lv, dict(room, _doors=pl["doors"]["kitchen"]), pieces, [], [], [],
                            surfaces=surfaces)
        mat = X.material_res(DATA)
        self.assertIn(f'[ext_resource type="ShaderMaterial" path="{mat}"', text)
        self.assertEqual(text.count("surface_material_override/0"), len(pieces))
        p = pieces[0]
        name = f"{p['id']}_1"
        at = [p["x"], lv["floor_y"] + p["h"], p["y"], p["turn"] % 360]
        self.assertIn(f'[node name="{p["id"]}" parent="Shell/{name}"]', text)
        self.assertIn("instance_shader_parameters/plan_at = Vector4(" + ", ".join(H._num(v) for v in at) + ")", text)

    def test_the_material_holds_every_painted_room(self):
        text = X.material_text(DATA)
        paints = H.paint_request(DATA)
        self.assertIn('path="res://assets/environment/house_kit/kit_set.gdshader"', text)
        self.assertIn(f"shader_parameter/paint_count = {len(paints['rooms'])}", text)
        rects = re.search(r"paint_rect = PackedVector4Array\(([^)]*)\)", text).group(1).split(", ")
        self.assertEqual(len(rects), 64)
        kitchen = next(r for r in paints["rooms"] if r["room"] == "kitchen")
        k = paints["rooms"].index(kitchen)
        self.assertEqual([float(v) for v in rects[4 * k:4 * k + 4]], [float(v) for v in kitchen["rect"]])
        request = X.check_request(DATA, {"kitchen": {}}, {"wall_2m"})
        self.assertEqual(request["material"], X.material_res(DATA))
        self.assertEqual(request["rooms"][0]["paint"]["hex"], kitchen["hex"])
        # the check compares the band and the plaster's source colour too (#133's minor): the request carries them
        self.assertEqual(request["rooms"][0]["paint"]["band"], kitchen["band"])
        self.assertEqual(request["rooms"][0]["paint"]["from"], paints["from"])
        bands = re.search(r"paint_band = PackedVector2Array\(([^)]*)\)", text).group(1).split(", ")
        self.assertEqual([float(v) for v in bands[2 * k:2 * k + 2]], [float(v) for v in kitchen["band"]])
        self.assertIn(f"paint_from = Vector3({', '.join(X._f(c) for c in paints['from'])})", text)


PAINTED = """[gd_scene format=3]

[ext_resource type="Shader" path="res://kit_set.gdshader" id="1"]

[sub_resource type="StandardMaterial3D" id="stand"]
resource_name = "kit_set"

[sub_resource type="BoxMesh" id="box"]
material = SubResource("stand")

[sub_resource type="ShaderMaterial" id="set"]
shader = ExtResource("1")
{paint}

[node name="{name}" type="Node3D"]
metadata/size_m = Vector2i(4, 4)

[node name="Shell" type="Node3D" parent="."]

[node name="wall_ok" type="MeshInstance3D" parent="Shell"]
transform = Transform3D(0, 0, 1, 0, 1, 0, -1, 0, 0, 1, 0, 2)
mesh = SubResource("box")
surface_material_override/0 = SubResource("set")
instance_shader_parameters/plan_at = Vector4(11, 0, 22, 90)

[node name="wall_bare" type="MeshInstance3D" parent="Shell"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 3, 0, 2)
mesh = SubResource("box")

[node name="wall_moved" type="MeshInstance3D" parent="Shell"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 2, 0, 3)
mesh = SubResource("box")
surface_material_override/0 = SubResource("set")
instance_shader_parameters/plan_at = Vector4(11, 0, 22, 0)
"""


@unittest.skipUnless(common.tool_path("GODOT_BIN", None), "Godot not found (GODOT_BIN)")
class BrokenFixture(unittest.TestCase):
    def test_the_check_names_every_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rooms = folder / "levels/house/rooms"
            rooms.mkdir(parents=True)
            (rooms / "bad.tscn").write_text(BROKEN, encoding="utf-8", newline="\n")
            request = {"rooms": [{"id": "bad", "rect": [0, 0, 6, 4], "floor_y": 0.0, "floor": True,
                                  "scene": "res://levels/house/rooms/bad.tscn",
                                  "walkable": ["floor_ok", "floor_bare", "floor_hollow"], "hide": ["crate_1"],
                                  "roof": [-1, 0, 7, 4], "roof_rect": [0, 0, 6, 4], "roof_from": 6.0,
                                  "roof_pieces": list(X.ROOF_PIECES)}],
                       "pieces": {}, "walks": [{"name": "through_wall", "kind": "door",
                                                "points": [[1.0, 0.0, 2.0], [3.0, 0.0, 2.0], [5.5, 0.0, 2.0]]}],
                       "pads": [[5.5, 0.0, 2.0]]}
            summary = {"rooms": {"bad": {"node": "Bad", "kit": 3}}, "check": request}
            with contextlib.redirect_stdout(io.StringIO()):
                code, problems = _house_export.run(folder, summary)
            text = "\n".join(problems)
            self.assertEqual(code, 1, text)
            self.assertIn("bad: Shell/floor_hollow has no layer-1 StaticBody3D", text)
            self.assertIn("bad: Dressing/crate_1 has no layer-1 StaticBody3D", text)
            self.assertNotRegex(text, r"bad: [^\n]*floor_ok")
            self.assertRegex(text, r"bad: no known surface \(none\) under [\d.]+, [\d.]+ on Bad/Shell/floor_bare/Body")
            self.assertIn("walk through_wall", text)
            self.assertIn("bad: CSGBox3D Box", text)
            # the hole over x 0..2: its 4 x 8 rays fall onto floor_ok, one problem; over the slab and its crate none
            self.assertIn("bad roof: a hole at 0.25, 0.25, 32 rays meet Bad/Shell/floor_ok/Body", text)
            self.assertEqual(len(re.findall(r"bad roof: ", text)), 1, text)
            report = json.loads((folder / "_check/load.json").read_text(encoding="utf-8"))
            self.assertGreater(report["package"]["surfaces"].get("wood", 0), 0)
            # the roof's 14 x 8 rays: 16 miss west of the rect, 32 fall through the hole onto floor_ok, 4 meet the
            # crate (no surface), 60 the slab; the crate is named with its room's roof, the bare floor with its room
            pkg = report["package"]
            self.assertEqual(pkg["roof_rays"], 112)
            self.assertEqual(pkg["roof_surfaces"], {"miss": 16, "wood": 32, "none": 4, "concrete": 60})
            self.assertEqual(pkg["none_at"].get("Bad/Dressing/RoofCrate"), "bad roof")
            self.assertEqual(pkg["none_at"].get("Bad/Shell/floor_bare/Body"), "bad")


    def test_the_check_names_walls_without_their_paint(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "kit_set.gdshader").write_text(X.SHADER_SRC.read_text(encoding="utf-8"), encoding="utf-8",
                                                     newline="\n")
            rooms = folder / "levels/house/rooms"
            rooms.mkdir(parents=True)
            req = H.paint_request(DATA)
            first = req["rooms"][0]
            to = ", ".join(str(v) for v in first["to"])
            src = ", ".join(str(v) for v in req["from"])

            def paint(band: list, source: str) -> str:
                return (f"shader_parameter/paint_count = 1\nshader_parameter/paint_from = Vector3({source})\n"
                        f"shader_parameter/paint_rect = PackedVector4Array(10, 20, 14, 24)\n"
                        f"shader_parameter/paint_band = PackedVector2Array({band[0]}, {band[1]})\n"
                        f"shader_parameter/paint_to = PackedVector3Array({to})")
            # good: rect, band, source and colour; banded: the band of another level; sourced: another source colour
            scenes = {"painted": "", "good": paint(first["band"], src),
                      "banded": paint([first["band"][0] + 3.0, first["band"][1] + 3.0], src),
                      "sourced": paint(first["band"], "0.5, 0.5, 0.5")}
            for rid, text in scenes.items():
                (rooms / f"{rid}.tscn").write_text(PAINTED.format(paint=text, name=rid.title()), encoding="utf-8",
                                                   newline="\n")
            want = X.check_request(DATA, {first["room"]: {}}, set())["rooms"][0]["paint"]
            self.assertEqual((want["band"], want["from"]), (first["band"], req["from"]))
            paint_ = dict(want, rect=[10, 20, 14, 24])
            request = {"rooms": [{"id": rid, "rect": [10, 20, 4, 4], "floor_y": 0.0, "floor": False,
                                  "scene": f"res://levels/house/rooms/{rid}.tscn", "walkable": [], "hide": [],
                                  "paint": paint_} for rid in scenes],
                       "pieces": {}, "walks": [], "pads": [], "material": ""}
            summary = {"rooms": {rid: {"node": rid.title(), "kit": 0} for rid in scenes}, "check": request}
            with contextlib.redirect_stdout(io.StringIO()):
                code, problems = _house_export.run(folder, summary)
            text = "\n".join(problems)
            self.assertEqual(code, 1, text)
            self.assertIn("painted: 2 kit surfaces without the kit's set material at their plan place, e.g. "
                          "Shell/wall_bare surface 0", text)
            self.assertIn(f"painted: the walls do not carry the paint {want['hex']}", text)
            self.assertIn("good: 2 kit surfaces without", text)
            self.assertNotIn("good: the walls", text)
            self.assertIn("banded: the walls do not carry the paint", text)
            self.assertIn("sourced: the walls do not carry the paint", text)
            report = json.loads((folder / "_check/load.json").read_text(encoding="utf-8"))
            self.assertEqual(report["package"]["paints"]["painted"], ["good"])
            self.assertEqual(report["package"]["paints"]["surfaces"], 12)



if __name__ == "__main__":
    unittest.main()
