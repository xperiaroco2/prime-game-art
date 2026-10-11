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

PACKAGES = sorted((common.ROOT / "assets").glob("*/*/package.json"))
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
        self.assertEqual([t["title"] for t in req["tiles"]], ["attic"] + [v["title"] for v in views])
        self.assertTrue(all(t["scene"] == "res://levels/house/rooms/attic.tscn" for t in req["tiles"]))

    def test_tile_line_prints_counts_as_ints(self) -> None:
        room = R.tile_line({"title": "Kitchen", "door": "", "lights": 2.0, "draw_calls": 41.0}, "rooms")
        self.assertEqual(room, "  Kitchen: door -, 2 lights, 41 draw calls")
        kit = R.tile_line({"title": "Walls (12)", "pieces": 12, "draw_calls": 37.0}, "kit")
        self.assertEqual(kit, "  Walls (12): 12 pieces, 37 draw calls")


if __name__ == "__main__":
    unittest.main()
