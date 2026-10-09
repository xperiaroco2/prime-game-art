"""The house layout engine (tools/runner/house_layout.py, docs/house.md): the layout data holds the grid rules, the
rooms match the design doc, the wall modules, corners, floors, railings and stairs land where the kit's conventions
say, and the scenes carry the game's marker names. Pure Python; the checks against the game's design doc and greybox
skip when D:/prime-game is missing."""

from __future__ import annotations

import copy
import re
import tempfile
import unittest
from pathlib import Path

from runner import house_layout as H

DATA = H.load()
PLAN = H.plan(DATA)
GAME = Path("D:/prime-game")
DOC = GAME / "docs" / "design" / "house-map.md"
GREYBOX = GAME / "levels" / "house" / "rooms"


def level(name: str) -> dict:
    return next(lv for lv in DATA["levels"] if lv["level"] == name)


def planned(name: str) -> dict:
    return next(lv for lv in PLAN["levels"] if lv["level"] == name)


def one_room(w: int = 6, d: int = 4, **extra) -> dict:
    """A data set with one 6 x 4 storey room at (0, 0)."""
    data = {"settings": DATA["settings"], "spec": DATA["spec"], "pieces": DATA["pieces"]}
    lv = {"level": "t", "node": "T", "floor_y": 0.0, "walls": "storey",
          "rooms": [{"id": "r", "node": "R", "title": "R", "rect": [0, 0, w, d], "kind": "room", "floor": "boards"}],
          "doors": [], "windows": [], **extra}
    data["levels"] = [lv]
    return data


def covered(piece: dict, size: tuple[float, float]) -> set:
    """The 1 m cells a floor tile covers, from its pivot and turn."""
    ax, az = H.axes(piece["turn"])
    pts = [(piece["x"] + ax[0] * a + az[0] * b, piece["y"] + ax[1] * a + az[1] * b) for a in (0, size[0]) for b in (0, size[1])]
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
    return {(i, j) for i in range(round(x0), round(x1)) for j in range(round(y0), round(y1))}


class LayoutDataTest(unittest.TestCase):
    def test_the_layout_holds_the_rules(self) -> None:
        self.assertEqual(H.validate(DATA), [])

    def test_35_rooms_once_each(self) -> None:
        ids = [r["id"] for lv in DATA["levels"] for r in lv["rooms"]]
        self.assertEqual(len(ids), 35)
        self.assertEqual(len(set(ids)), 35)

    def test_the_kit_path_is_one_setting(self) -> None:
        self.assertEqual(DATA["settings"]["kit_dir"], "kits/house/v1")
        self.assertIn("{id}", DATA["settings"]["kit_res"])

    def test_every_planned_piece_is_in_the_kit(self) -> None:
        ids = {p["id"] for lv in PLAN["levels"] for ps in lv["pieces"].values() for p in ps}
        ids |= {p["id"] for lv in PLAN["levels"] for p in lv["extra"]}
        self.assertEqual(ids - set(DATA["pieces"]), set())

    def test_windows_and_door_leaves_are_the_defaults(self) -> None:
        windows = {lv["level"]: len(lv.get("windows", [])) for lv in DATA["levels"]}
        self.assertEqual((windows["ground"] - 5, windows["upper"]), (16, 16))  # Q7 B; the garage's 5 apart
        ajar = sorted(tuple(d["rooms"]) for lv in DATA["levels"] for d in lv.get("doors", []) if d.get("leaf") == "ajar")
        self.assertEqual(ajar, [("dining_room", "terrace"), ("garage", "yard"), ("hallway", "path")])  # Q9 B

    def test_the_pantry_stairs_are_a_marked_placeholder(self) -> None:
        st = next(s for s in level("ground")["stairs"] if s["id"] == "pantry_stairs")
        self.assertTrue(st["placeholder"])
        self.assertEqual(H.stair_top_edge(st), ("h", 25, 26, 28))

    @unittest.skipUnless(DOC.is_file(), "the game's design doc is missing")
    def test_rooms_match_the_design_doc(self) -> None:
        rows = re.findall(r"^\| ([^|]+?) \| (\d+), (\d+) \| (\d+) x (\d+) m \|", DOC.read_text(encoding="utf-8"), re.M)
        doc = {t: [int(x), int(y), int(w), int(d)] for t, x, y, w, d in rows}
        ours = {r["title"]: r["rect"] for lv in DATA["levels"] for r in lv["rooms"]}
        self.assertEqual(len(doc), 35)
        self.assertEqual(ours, doc)

    @unittest.skipUnless(GREYBOX.is_dir(), "the game's greybox rooms are missing")
    def test_door_markers_match_the_greybox(self) -> None:
        for lv in DATA["levels"]:
            for room in lv["rooms"]:
                text = (GREYBOX / f"{room['id']}.tscn").read_text(encoding="utf-8")
                theirs = sorted(re.findall(r'\[node name="(\w+)" type="Marker3D" parent="Doors"', text))
                ours = sorted(d["names"][room["id"]] for L in DATA["levels"] for d in L.get("doors", [])
                              if room["id"] in d.get("names", {}))
                self.assertEqual(ours, theirs, room["id"])
                stations = sorted(re.findall(r'\[node name="(\w+)" type="Marker3D" parent="Stations"', text))
                self.assertEqual(sorted(s["name"] for s in room.get("stations", [])), stations, room["id"])


class RuleTest(unittest.TestCase):
    def test_a_door_off_the_grid_is_refused(self) -> None:
        data = one_room(doors=[{"at": [2.5, 0], "rooms": ["r"], "names": {}}])
        self.assertTrue(any("whole metres" in p for p in H.validate(data)))

    def test_a_door_across_a_room_corner_is_refused(self) -> None:
        data = one_room(w=8)
        data["levels"][0]["rooms"] = [{"id": "a", "node": "A", "title": "A", "rect": [0, 0, 4, 4], "kind": "room"},
                                      {"id": "b", "node": "B", "title": "B", "rect": [4, 0, 4, 4], "kind": "room"}]
        data["levels"][0]["doors"] = [{"at": [4, 0], "rooms": ["a"], "names": {}}]
        self.assertTrue(any("corner" in p for p in H.validate(data)))

    def test_a_wall_meeting_a_door_is_refused(self) -> None:
        data = one_room(w=8)
        data["levels"][0]["rooms"] = [{"id": "a", "node": "A", "title": "A", "rect": [0, 0, 8, 4], "kind": "room"},
                                      {"id": "b", "node": "B", "title": "B", "rect": [0, 4, 4, 4], "kind": "room"},
                                      {"id": "c", "node": "C", "title": "C", "rect": [4, 4, 4, 4], "kind": "room"}]
        data["levels"][0]["doors"] = [{"at": [4, 4], "rooms": ["a", "b"], "names": {}}]
        self.assertTrue(any("meets the opening" in p for p in H.validate(data)))

    def test_rooms_must_tile_the_footprint(self) -> None:
        data = copy.deepcopy(DATA)
        lv = next(L for L in data["levels"] if L["level"] == "ground")
        lv["rooms"] = [r for r in lv["rooms"] if r["id"] != "wc"]
        lv["doors"] = [d for d in lv["doors"] if "wc" not in d["rooms"]]
        lv["windows"] = [w for w in lv["windows"] if w["room"] != "wc"]
        self.assertTrue(any("tile the footprint" in p for p in H.validate(data)))

    def test_a_stair_off_its_hole_is_refused(self) -> None:
        data = copy.deepcopy(DATA)
        st = next(s for L in data["levels"] for s in L.get("stairs", []) if s["id"] == "main_stairs")
        st["rect"] = [30, 30, 2, 6]
        self.assertTrue(any(p.startswith("main_stairs") for p in H.check_stairs(data)))


class PlanTest(unittest.TestCase):
    def test_walls_face_out_and_corners_fill_the_notches(self) -> None:
        data = one_room(windows=[{"at": [3, 0], "room": "r"}], doors=[{"at": [6, 2], "rooms": ["r"], "names": {}}])
        ps = H.plan(data)["levels"][0]["pieces"]["r"]
        walls = [p for p in ps if p["id"].startswith("wall_") and "corner" not in p["id"]]
        north = sorted((p["x"], p["id"]) for p in walls if p["y"] == 0 and p["turn"] == 180)
        # the north run goes west from each pivot: pivots at the modules' east ends; 1 m filler, window 2..4, 2 m
        self.assertEqual(north, [(2, "wall_storey_2m_ext"), (4, "wall_storey_2m_window_ext"), (6, "wall_storey_2m_ext")])
        east = sorted((p["y"], p["id"]) for p in walls if p["x"] == 6 and p["turn"] == 90)  # turn 90 runs north
        self.assertEqual(east, [(1, "wall_storey_1m_ext"), (3, "wall_storey_2m_door_ext"), (4, "wall_storey_1m_ext")])
        self.assertTrue(all(p["turn"] == -90 for p in walls if p["x"] == 0 and p["y"] < 4))
        self.assertTrue(all(p["turn"] == 0 for p in walls if p["y"] == 4 and p["x"] < 6))
        corners = sorted((p["x"], p["y"], p["turn"]) for p in ps if "corner" in p["id"])
        self.assertEqual(corners, [(0, 0, 180), (0, 4, -90), (6, 0, 90), (6, 4, 0)])  # as the kit proof places them

    def test_the_walls_cover_each_run_once(self) -> None:
        lv = planned("ground")
        total = sum(DATA["pieces"][p["id"]].get("length", 0) for ps in lv["pieces"].values() for p in ps
                    if DATA["pieces"][p["id"]]["kind"] in ("wall", "glass", "garage"))
        edges = H.wall_edges(level("ground"))
        self.assertEqual(total, len(edges))

    def test_floors_cover_each_free_cell_once(self) -> None:
        sizes = {p["id"]: (p["size"][0], p["size"][1]) for p in DATA["spec"]["pieces"] if "size" in p}
        for name in ("ground", "upper"):
            lv = planned(name)
            for room in level(name)["rooms"]:
                if room["kind"] != "room":
                    continue
                cells = [c for p in lv["pieces"][room["id"]] if p["id"] in sizes for c in covered(p, sizes[p["id"]])]
                self.assertEqual(len(cells), len(set(cells)), room["id"])
                holes = set()
                for h in level(name).get("holes", []):
                    holes |= H._cells(h["rect"])
                expect = H._cells(room["rect"]) - holes
                self.assertEqual(set(cells), expect, room["id"])

    def test_the_hatch_tile_is_in_the_attic_floor(self) -> None:
        tiles = [p for p in planned("attic")["pieces"]["attic"] if p["id"] == "floor_boards_2x2_hatch"]
        self.assertEqual([(t["x"], t["y"]) for t in tiles], [(27, 28)])
        self.assertEqual(H.hatch_hole(level("attic")["holes"][0], DATA), [27.6, 28.3, 0.8, 1.4])

    def test_stairs_climb_from_their_rect(self) -> None:
        extra = {p.get("name"): p for p in planned("upper")["extra"]}
        self.assertEqual((extra["main_stairs"]["x"], extra["main_stairs"]["y"], extra["main_stairs"]["turn"]), (26, 36, 90))
        self.assertEqual((extra["balcony_stairs"]["x"], extra["balcony_stairs"]["y"], extra["balcony_stairs"]["turn"]),
                         (40, 15, -90))

    def test_the_balcony_rail_leaves_the_stair_top_open(self) -> None:
        rails = [p for p in planned("upper")["extra"] if p["id"].startswith("railing_balcony_") and p["y"] == 21]
        spans = sorted((p["x"], p["id"]) for p in rails if "post" not in p["id"])
        self.assertNotIn(38, [x for x, _ in spans])
        self.assertTrue(spans)

    def test_the_roof_deck_skips_the_attic_and_has_a_parapet(self) -> None:
        roof = planned("roof")
        tiles = [p for p in roof["pieces"]["roof"] if p["id"].startswith("roof_flat")]
        area = sum(4 if p["id"].endswith("2x2") else 1 for p in tiles)
        self.assertEqual(area, 26 * 22 - 20 * 14)
        self.assertEqual(sum(1 for p in roof["extra"] if p["id"] == "parapet_corner"), 4)


class SceneTest(unittest.TestCase):
    def test_scenes_carry_the_pieces_and_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = H.write_scenes(DATA, PLAN, Path(tmp))
            files = sorted(p.relative_to(tmp).as_posix() for p in Path(tmp).rglob("*.tscn"))
            self.assertEqual(len(files), 35 + 5 + 1)
            dining = (Path(tmp) / "ground" / "dining_room.tscn").read_text(encoding="utf-8")
            for name in ("Door1", "Door2", "Door3", "Door4", "DiningTable", "Circle01"):
                self.assertIn(f'[node name="{name}" type="Marker3D"', dining)
            self.assertIn('groups=["spawn_circle"]', dining)
            self.assertIn('path="res://import/kit_wall_storey_2m_door_int.glb"', dining)
            ground = (Path(tmp) / "ground.tscn").read_text(encoding="utf-8")
            self.assertIn('path="res://import/house/ground/dining_room.tscn"', ground)
            self.assertIn("Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 30, 0, 24)", ground)
            self.assertNotIn("\r", dining)
            self.assertEqual(summary["instances"], sum(len(v) for lv in PLAN["levels"] for v in lv["pieces"].values())
                             + sum(len(lv["extra"]) for lv in PLAN["levels"]))

    def test_a_turned_transform(self) -> None:
        self.assertEqual(H._tf(90, 1, 2, 3), "Transform3D(0, 0, -1, 0, 1, 0, 1, 0, 0, 1, 2, 3)")


class WalkRequestTest(unittest.TestCase):
    REQ = H.walk_request(DATA)

    def test_every_door_of_the_walked_levels_is_crossed(self) -> None:
        doors = [(lv["level"], tuple(d["at"])) for lv in DATA["levels"] if lv["level"] in H.WALK_LEVELS
                 for d in lv.get("doors", []) if d.get("kind", "door") in H.DOOR_KINDS]
        walks = [w for w in self.REQ["walks"] if w["kind"] != "stairs"]
        self.assertEqual(len(walks), len(doors))
        for w, (name, (x, y)) in zip(walks, doors):
            a, b = w["points"]
            self.assertEqual(((a[0] + b[0]) / 2, (a[2] + b[2]) / 2), (x, y), w["name"])
            self.assertAlmostEqual(abs(a[0] - b[0]) + abs(a[2] - b[2]), 2 * H.WALK_SIDE, msg=w["name"])
            self.assertTrue(w["name"].startswith(f"{name}:"))

    def test_a_door_walk_starts_in_its_first_room(self) -> None:
        w = next(w for w in self.REQ["walks"] if w["name"].startswith("ground:dining_room>terrace"))
        self.assertEqual(w["points"], [[36.0, 0.0, 25.0], [36.0, 0.0, 23.0]])

    def test_each_flight_is_walked_up_and_down(self) -> None:
        stairs = {w["name"]: w["points"] for w in self.REQ["walks"] if w["kind"] == "stairs"}
        self.assertEqual(sorted(stairs), sorted(f"{s}:{d}" for s in ("main_stairs", "pantry_stairs", "balcony_stairs")
                                                for d in ("up", "down")))
        up = stairs["main_stairs:up"]
        self.assertEqual(up[1], [27.0, 0.0, 36.0])
        self.assertEqual(up[2], [27.0, 3.2, 30.0])
        self.assertEqual(stairs["main_stairs:down"], up[::-1])
        # The pantry's 1 m landing: the end stops short of its north wall (capsule radius and half a wall).
        self.assertAlmostEqual(stairs["pantry_stairs:up"][-1][2], 24.85)

    def test_ends_without_a_floor_get_a_pad(self) -> None:
        self.assertIn([39.0, 0.0, 14.0], self.REQ["pads"])  # the balcony stairs' foot in the yard
        self.assertNotIn([27.0, 0.0, 37.0], self.REQ["pads"])  # the hallway has a floor


if __name__ == "__main__":
    unittest.main()
