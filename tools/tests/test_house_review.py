"""The committed House packages and their look-approval sheet (`house --package-sheet`,
tools/runner/commands/_house_review.py, docs/house.md "The export", art #124): every file a committed package.json
lists has a committed copy with its sha256 under a set manifest's export/ folder, the kit's families take every piece,
and the sheet's request covers the package. Pure Python: no Godot; the export folders hold LFS files, so a checkout
without their content (a pointer file) skips the hash test."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runner import common, house_export as X, house_layout as H
from runner.commands import _house_review as R

PACKAGES = [path for path, _ in R.house_packages(common.ROOT)]
FAMILIES = X.settings(H.load())["kit_families"]


def _lfs_pointer(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(40).startswith(b"version https://git-lfs")


class FamiliesTest(unittest.TestCase):
    def test_first_match_wins_and_the_rest_go_last(self) -> None:
        got = R.families(["wall_storey_2m_door_ext", "wall_storey_2m_ext", "roof_vent", "odd_piece"], FAMILIES)
        self.assertEqual(got["openings"], ["wall_storey_2m_door_ext"])
        self.assertEqual(got["walls"], ["wall_storey_2m_ext"])
        self.assertEqual(got["roof"], ["roof_vent"])
        self.assertEqual(got[list(FAMILIES)[-1]], ["odd_piece"])

    def test_kit_request_tiles_every_piece_once(self) -> None:
        kit = next((p for p in PACKAGES if json.loads(p.read_text(encoding="utf-8"))["package"] == 1), None)
        if kit is None:
            self.skipTest("package 1 is not committed")
        package = json.loads(kit.read_text(encoding="utf-8"))
        req = R.request(package, FAMILIES)
        self.assertEqual(req["mode"], "kit")
        self.assertEqual(req["sheet"], "p1_kit")
        pieces = [pid for tile in req["tiles"] for pid in tile["pieces"]]
        glbs = [f for f in package["files"] if f.endswith(".glb")]
        self.assertEqual(len(pieces), len(glbs))
        self.assertEqual(len(set(pieces)), len(pieces))


class HousePackagesTest(unittest.TestCase):
    def test_a_package_json_without_a_number_is_not_a_house_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, data in (("room/house_ground", {"package": 2, "files": {}}),
                              ("character/slice_m1", {"asset": "slice_m1", "files": [{"name": "slice_m1.glb"}]})):
                (root / "assets" / rel).mkdir(parents=True)
                (root / "assets" / rel / "package.json").write_text(json.dumps(data), encoding="utf-8")
            got = R.house_packages(root)
            self.assertEqual([(p.parent.name, d["package"]) for p, d in got], [("house_ground", 2)])
            self.assertEqual(R.neighbours(root, {"package": 4, "rooms": {"balcony": {}}},
                                          [{"room": "balcony", "with": [{"room": "hall"}]}]), [])


class CommittedTest(unittest.TestCase):
    def test_every_package_file_has_a_committed_copy(self) -> None:
        if not PACKAGES:
            self.skipTest("no package committed")
        exports = list((common.ROOT / "assets").glob("*/*/export/**/*.glb"))
        if any(_lfs_pointer(p) for p in exports[:3]):
            self.skipTest("the LFS files are pointers here")
        files = R.committed(common.ROOT)
        for path in PACKAGES:
            package = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(package=package["name"]):
                missing = [rel for rel, sha in package["files"].items() if sha not in files]
                self.assertEqual(missing, [])

    def test_stage_names_what_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.glb"
            src.write_bytes(b"glb")
            package = {"files": {"assets/environment/x/a.glb": "1" * 64, "levels/r.tscn": "2" * 64}}
            missing = R.stage(package, {"1" * 64: src}, Path(tmp) / "out")
            self.assertEqual(missing, ["levels/r.tscn"])
            self.assertEqual((Path(tmp) / "out/assets/environment/x/a.glb").read_bytes(), b"glb")

    def test_room_request_names_every_room_scene(self) -> None:
        package = {"package": 2, "name": "ground", "rooms": {"wc": {}, "pantry": {}}, "files": {}}
        req = R.request(package, FAMILIES)
        self.assertEqual(req["mode"], "rooms")
        self.assertEqual(req["eye"], 1.6)
        self.assertEqual([t["scene"] for t in req["tiles"]],
                         ["res://levels/house/rooms/wc.tscn", "res://levels/house/rooms/pantry.tscn"])

    def test_views_follow_their_room_and_stand_over_the_roof(self) -> None:
        from runner import house_attic, house_layout
        data = house_layout.load()
        views = R.views(data)
        roof = [v for v in views if v["title"].startswith("roof:")]
        self.assertTrue(roof and all(v["room"] == "attic" and v["sun"] for v in roof))
        at = next(v for v in data["settings"]["export"]["sheet_views"] if v["title"] == roof[0]["title"])["at"]
        self.assertAlmostEqual(roof[0]["eye"][1], house_attic.roof_top(data, at[1]) + 1.6, places=2)
        package = {"package": 5, "name": "attic", "rooms": {"attic": {}}, "files": {}}
        req = R.request(package, FAMILIES, extra=views)
        attic = [v["title"] for v in views if v["room"] == "attic"]
        self.assertEqual([t["title"] for t in req["tiles"]], ["attic"] + attic)
        self.assertTrue(all(t["scene"] == "res://levels/house/rooms/attic.tscn" for t in req["tiles"]))

    def test_balcony_view_looks_down_the_external_stairs(self) -> None:
        from runner import house_layout
        views = [v for v in R.views(house_layout.load()) if v["room"] == "balcony"]
        self.assertEqual(len(views), 2)
        self.assertTrue(all(v["look"][1] < 0.0 for v in views))  # the flight's foot is under the balcony's floor
        # the flight is the yard's (P2): the yard joins in place, its origin 30 m west, 3.2 m down, 21 m north
        self.assertEqual(views[0]["with"], [{"room": "yard", "scene": "res://levels/house/rooms/yard.tscn",
                                             "offset": [-30.0, -3.2, -21.0]}])
        package = {"package": 4, "name": "upper", "rooms": {"landing": {}, "balcony": {}}, "files": {}}
        req = R.request(package, FAMILIES, extra=views)
        self.assertEqual([t["title"] for t in req["tiles"]], ["landing", "balcony"] + [v["title"] for v in views])
        self.assertEqual(req["tiles"][-1]["scene"], "res://levels/house/rooms/balcony.tscn")
        self.assertEqual([p["package"] for p in R.neighbours(R.common.ROOT, {"package": 4, "rooms": {"balcony": {}}},
                                                             views)], [2])

    def test_the_plot_package_shows_its_views_with_its_rooms_at_their_corners(self) -> None:
        from runner import house_layout
        views = R.views(house_layout.load())
        plot = [v for v in views if v["room"] == "plot"]
        self.assertEqual(len(plot), 6)
        self.assertEqual(plot[0]["eye"], [30.0, 1.6, 57.0])  # plan metres, 1.6 m over the ground
        package = {"package": 7, "name": "outdoor", "rooms": {"greenhouse": {}, "garden": {}}, "files": {},
                   "plot": {"scene": "res://levels/house/outdoor.tscn"}}
        req = R.request(package, FAMILIES, extra=views)
        self.assertEqual([t["title"] for t in req["tiles"]], [v["title"] for v in plot])
        tile = req["tiles"][0]
        self.assertEqual(tile["scene"], "res://levels/house/outdoor.tscn")
        self.assertNotIn("rooms_at", tile)
        self.assertEqual(tile["rooms"], [{"scene": "res://levels/house/rooms/greenhouse.tscn", "at": [58, 0, 6]},
                                         {"scene": "res://levels/house/rooms/garden.tscn", "at": [46, 0, 2]}])

    def test_tile_line_prints_counts_as_ints(self) -> None:
        room = R.tile_line({"title": "Kitchen", "door": "", "lights": 2.0, "draw_calls": 41.0}, "rooms")
        self.assertEqual(room, "  Kitchen: door -, 2 lights, 41 draw calls")
        kit = R.tile_line({"title": "Walls (12)", "pieces": 12, "draw_calls": 37.0}, "kit")
        self.assertEqual(kit, "  Walls (12): 12 pieces, 37 draw calls")


class ContextTest(unittest.TestCase):
    """#144: a room tile stages the rooms owning walls on its sides and the slab over it, as context."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = H.load()
        cls.ctx = R.context(cls.data)

    def _rooms(self, room: str, why: str) -> list[str]:
        return [c["room"] for c in self.ctx[room] if c["why"] == why]

    def test_the_kitchen_gets_its_neighbours_walls_and_the_upper_floor_over_it(self) -> None:
        # a shared wall belongs to the first of its two rooms in ground.toml: the dining room's and the stairs' walls
        # bound the kitchen, the kitchen owns the one it shares with the hallway
        self.assertEqual(self._rooms("kitchen", "walls"), ["dining_room", "stairs"])
        self.assertEqual(self._rooms("kitchen", "ceiling"), ["study", "bathroom", "guest_room"])
        study = next(c for c in self.ctx["kitchen"] if c["room"] == "study")
        self.assertEqual(study["offset"], [0.0, 3.2, -6.0])  # its corner 6 m north, its floor one storey up
        self.assertEqual(self._rooms("hallway", "walls"), ["living_room", "stairs", "kitchen"])

    def test_the_slab_over_a_room_comes_from_the_next_level_up_and_the_top_has_its_own_roof(self) -> None:
        self.assertEqual(self._rooms("bedroom", "ceiling"), ["attic"])
        self.assertEqual(self.ctx["attic"], [])
        # the basement's ceiling: the ground floor's rooms with a floor over it, not the yard's areas
        self.assertIn("kitchen", self._rooms("boiler_room", "ceiling"))
        self.assertNotIn("yard", [c["room"] for cs in self.ctx.values() for c in cs])
        # the terrace (an open room) sits under the balcony
        self.assertEqual(self._rooms("terrace", "ceiling"), ["balcony"])

    def test_areas_get_no_context_and_no_room_is_its_own(self) -> None:
        self.assertNotIn("yard", self.ctx)
        for room, cs in self.ctx.items():
            self.assertNotIn(room, [c["room"] for c in cs])

    def test_room_tiles_carry_their_staged_context_and_skip_their_with_rooms(self) -> None:
        package = {"package": 2, "name": "ground", "rooms": {"kitchen": {}}, "files": {}}
        have = {"levels/house/rooms/dining_room.tscn", "levels/house/rooms/study.tscn"}
        req = R.request(package, FAMILIES, ctx=self.ctx, have=have)
        tile = req["tiles"][0]
        self.assertEqual([(c["room"], c["scene"]) for c in tile["context"]],
                         [("dining_room", "res://levels/house/rooms/dining_room.tscn"),
                          ("study", "res://levels/house/rooms/study.tscn")])
        views = [{"room": "kitchen", "title": "kitchen: east", "eye": [1, 1.6, 1], "look": [2, 1, 2], "sun": False,
                  "with": [{"room": "study", "scene": "res://levels/house/rooms/study.tscn", "offset": [0, 3.2, -6]}]}]
        req = R.request(package, FAMILIES, extra=views, ctx=self.ctx, have=have)
        self.assertEqual([c["room"] for c in req["tiles"][1]["context"]], ["dining_room"])
        self.assertNotIn("context", R.request(package, FAMILIES)["tiles"][0])

    def test_neighbours_find_the_packages_holding_the_context_rooms(self) -> None:
        package = {"package": 2, "name": "ground", "rooms": {"kitchen": {}}, "files": {}}
        got = [p["package"] for p in R.neighbours(R.common.ROOT, package, [], self.ctx)]
        if not got:
            self.skipTest("the upper package is not committed")
        self.assertEqual(got, [4])

    def test_tile_line_adds_the_context_draw_calls(self) -> None:
        room = R.tile_line({"title": "Kitchen", "door": "", "lights": 2.0, "draw_calls": 41.0,
                            "context_draw_calls": 30.0}, "rooms")
        self.assertEqual(room, "  Kitchen: door -, 2 lights, 41 draw calls (+30 context)")


if __name__ == "__main__":
    unittest.main()
