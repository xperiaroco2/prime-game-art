"""The basement's storage, darkroom and corridor (#170) and its plant rooms: the generator hall, the boiler, pump and
switch rooms, the passage, and the darkroom's central island (#172; docs/props.md "World look rules"): functional,
present-day working rooms. Their new props build at their size_m (never more than 15 mm over it), at their pivot and under their
class's triangle budget; the furniture collides with one box inside its size, the wall pieces stay inside their depth,
the flat, wall-sign and hanging pieces have no collider; each room's dressing keeps 0.3 m from every station and
spawn marker in it (read from layouts/house/basement.toml: the storage's six stations and ten package spawns, the
darkroom's PhotoBoard, the plant rooms' Generator and switches B to D, asserted), keeps its task props, leaves its doors' openings clear, keeps its prop count (never
emptier than before the pass) and main's big pieces, and keeps its Name label out of every piece and light fixture; the darkroom's island leaves a 1.2 m walk round it and the
door's line to the photo board clear.
Pure Python, no Blender."""

from __future__ import annotations

import json
import math
import sys
import tomllib
import unittest
from collections import Counter

from runner import common
from runner.commands import _props

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import prop_geom  # noqa: E402

LIB = _props.load()
KIT = json.loads((common.ROOT / LIB["kit_spec"]).read_text(encoding="utf-8"))
SPEC = prop_geom.lib_spec(LIB, KIT)
STYLE = prop_geom.Style.from_lib(LIB)
BY_ID = {p["id"]: p for p in LIB["prop"]}
LAYOUT = common.ROOT / "layouts" / "house"
HOUSE = tomllib.loads((LAYOUT / "house.toml").read_text(encoding="utf-8"))
TASKS = {t["id"]: t for t in tomllib.loads((common.ROOT / "props" / "tasks.toml").read_text(encoding="utf-8"))["props"]}
ROOMS = ("storage", "darkroom", "corridor", "generator_hall", "boiler_room", "pump_room", "switch_room", "passage")
DOORS = {"storage": 2, "darkroom": 1, "corridor": 2, "generator_hall": 5, "boiler_room": 1, "pump_room": 1,
         "switch_room": 1, "passage": 1}
# The [[props]] entries on main before the pass (fixtures not counted; the generated clutter blocks included).
BEFORE = {"storage": 155, "darkroom": 93, "corridor": 49,  # darkroom: main after #170
          "generator_hall": 140, "boiler_room": 105, "pump_room": 71, "switch_room": 60, "passage": 45}  # #172
# The stations and spawn markers each room keeps clear.
POINTS = {"storage": sorted(["Buns", "Meat", "WineRack", "Boxes", "SwitchA", "PartsShelf"]
                            + [f"Package{k:02d}" for k in range(1, 11)]),
          "darkroom": ["PhotoBoard"], "corridor": [], "generator_hall": ["Generator"], "boiler_room": ["SwitchB"],
          "pump_room": ["SwitchC"], "switch_room": ["SwitchD"], "passage": []}
# The task props (props/tasks.toml) each room keeps, by count (test_house_basement holds the same).
TASK_PROPS = {"storage": {"bun_shelf": 2, "meat_freezer": 1, "wine_rack": 1, "delivery_box_stack": 3, "wall_switch": 1,
                          "car_parts_shelf": 1},
              "darkroom": {"photo_board": 1, "enlarger": 2, "tray_table": 2}, "corridor": {},
              "generator_hall": {"generator": 1, "cable_drum": 3}, "boiler_room": {"boiler": 1, "wall_switch": 1},
              "pump_room": {"wall_switch": 1, "water_tank": 1, "pump": 1},
              "switch_room": {"wall_switch": 1, "switchboard": 3, "cable_drum": 2}, "passage": {}}
# Main's big pieces, replaced by better ones, never dropped: one of each id group at least (the darkroom's
# sideboards became dry benches).
BIG = {"storage": [("store_shelving", "store_shelving_b"), ("loaded_pallet",), ("store_workbench",), ("toolbox_cart",),
                   ("tool_wall",)],
       "darkroom": [("chem_shelf",), ("filing_cabinet",), ("desk",), ("stool",), ("lab_sink",), ("light_table",)],
       "corridor": [("store_shelving", "store_shelving_b"), ("radiator",), ("work_hooks",), ("shoe_rack",)],
       # #172: main's metal shelving became spares shelving, its sideboards tool chests and workbenches, the switch
       # room's shelving its electrical cabinets
       "generator_hall": [("parts_shelving",), ("toolbox_cart",), ("tool_wall",), ("tool_chest", "store_workbench"),
                          ("pallet",)],
       "boiler_room": [("store_shelving", "store_shelving_b"), ("toolbox_cart",), ("tool_wall",)],
       "pump_room": [("store_shelving", "store_shelving_b"), ("toolbox_cart",)],
       "switch_room": [("desk",), ("office_chair",), ("filing_cabinet",), ("elec_cabinet", "elec_cabinet_b")],
       "passage": [("store_shelving", "store_shelving_b")]}

SOLID = ("store_shelving", "store_shelving_b", "bread_rack", "pallet_jack", "loaded_pallet", "store_workbench",
         "step_ladder", "hand_trolley", "lab_sink", "light_table", "chem_shelf",
         # #172
         "control_desk", "drum_bund", "drum_bund_b", "tool_chest", "parts_shelving", "hw_cylinder", "expansion_vessel",
         "water_softener", "mop_sink", "pump_set", "pump_set_b", "elec_cabinet", "elec_cabinet_b", "lectern",
         "dev_bench", "cutting_table")
WALL_SOLID = ("work_hooks", "fire_extinguisher", "fuse_box", "fire_point", "wall_boiler", "wall_hose_reel",
              "meter_panel")  # the last four: #172
WALL = ("sign_staff", "sign_buns", "sign_meat", "sign_wine", "sign_parts", "sign_deliveries", "sign_way_out",
        "sign_darkroom", "clipboard",
        # #172
        "cable_tray", "isolator", "gen_log", "sign_ear", "sign_volt", "sign_no_smoking", "sign_generator", "sign_plant",
        "sign_first_aid", "insulated_pipes", "valve_panel", "sign_boiler", "pump_chart", "sign_pump", "first_aid_box",
        "sign_switch")
HUNG = ("aisle_sign_1", "aisle_sign_2", "aisle_sign_3", "print_line", "print_line_b")
FLAT = ("floor_bay", "floor_lane", "floor_hatch", "rubber_runner", "floor_gen_zone", "switch_mat")  # last two: #172
LOW = ("sump_cover",)  # #172: a 20 mm floor plate, walked over (no collider)
NEW = SOLID + WALL_SOLID + WALL + HUNG + FLAT + LOW
ISLAND = ("dev_bench", "cutting_table")  # #172: the darkroom's central island
WALK_M = 1.2  # the walk round the island
OVER_M = 0.015  # a prop may stand at most this far over its size_m
CLEAR_M = 0.3  # nothing of the dressing this close to a station's point or a spawn marker
DOOR_CLEAR_M = 1.4  # house_dressing.DOOR_CLEAR["door"]: the opening's clear width
DOOR_DEPTH_M = 0.8  # the floor kept free in front of a door, into the room
FACES = {"S": 0, "E": 90, "N": 180, "W": -90}  # house_dressing.FACES


def _build(pid: str) -> dict:
    return prop_geom.build(BY_ID[pid], SPEC, STYLE)


def _footprint(item: dict, built: dict) -> list[tuple[float, float]]:
    """The four room-local (x, z) corners of a placed prop's bounds."""
    b = built["bounds_m"]
    a = math.radians(float(item.get("yaw", FACES[item.get("face", "S")])))
    out = []
    for x in (b["min"][0], b["max"][0]):
        for z in (b["min"][2], b["max"][2]):
            out.append((item["at"][0] + x * math.cos(a) + z * math.sin(a),
                        item["at"][2] - x * math.sin(a) + z * math.cos(a)))
    return out


def _box_dist(fp: list[tuple[float, float]], x: float, z: float) -> float:
    xs, zs = [p[0] for p in fp], [p[1] for p in fp]
    dx = max(min(xs) - x, 0.0, x - max(xs))
    dz = max(min(zs) - z, 0.0, z - max(zs))
    return math.hypot(dx, dz)


def _basement() -> dict:
    return tomllib.loads((LAYOUT / "basement.toml").read_text(encoding="utf-8"))


def _dressing(rid: str) -> dict:
    return tomllib.loads((LAYOUT / "dressing" / f"{rid}.toml").read_text(encoding="utf-8"))


def _points(rid: str) -> tuple[dict, list[dict]]:
    """A room's record and every point it must keep clear, room-local: its stations and every room's spawn markers
    inside its rectangle."""
    lv = _basement()
    room = next(r for r in lv["rooms"] if r["id"] == rid)
    x0, z0, w, d = room["rect"]
    points = [{"name": s["name"], "at": s["at"]} for s in room.get("stations", [])]
    for r in lv["rooms"]:
        rx, rz = r["rect"][0], r["rect"][1]
        for mk in r.get("markers", []):
            gx, gz = rx + mk["at"][0], rz + mk["at"][2]
            if x0 <= gx <= x0 + w and z0 <= gz <= z0 + d:
                points.append({"name": mk["name"], "at": [gx - x0, 0.0, gz - z0]})
    return room, points


def _bounds(item: dict, built_cache: dict) -> dict:
    """A placed prop's local bounds: a task prop's w, d, h, a pack prop's size_m box, a procedural prop's build."""
    pid = item["id"]
    if pid not in BY_ID:
        t = TASKS[pid]
        z0 = 0.0 if t.get("pivot") == "wall" else -t["d"] / 2
        return {"bounds_m": {"min": [-t["w"] / 2, 0.0, z0], "max": [t["w"] / 2, t["h"], z0 + t["d"]]}}
    if "shape" not in BY_ID[pid]:
        x, y, z = _props.size_xyz(BY_ID[pid]["size_m"])
        z0 = 0.0 if BY_ID[pid].get("pivot") == "wall" else -z / 2
        y0 = -y if BY_ID[pid].get("pivot") == "ceiling" else 0.0
        return {"bounds_m": {"min": [-x / 2, y0, z0], "max": [x / 2, y0 + y, z0 + z]}}
    if pid not in built_cache:
        built_cache[pid] = _build(pid)
    return built_cache[pid]


class BasementPropsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {pid: _build(pid) for pid in NEW}
        cls.placed = {}
        for rid in ROOMS:
            cls.placed[rid] = []
            for item in _dressing(rid)["props"]:
                built = _bounds(item, cls.built)
                cls.placed[rid].append((item, built, _footprint(item, built)))

    def test_every_new_prop_builds_at_its_size(self):
        for pid in NEW:
            p, d = BY_ID[pid], self.built[pid]
            want = _props.size_xyz(p["size_m"])
            for got, w in zip(d["size_m"], want):
                msg = f"{pid}: built {d['size_m']}, want {want}"
                self.assertLessEqual(got, w + OVER_M, msg)
                self.assertGreaterEqual(got, w - max(0.03, 0.12 * w), msg)

    def test_every_new_prop_sits_at_its_pivot(self):
        for pid in NEW:
            p, b = BY_ID[pid], self.built[pid]["bounds_m"]
            lo, hi = b["min"], b["max"]
            self.assertAlmostEqual(lo[0] + hi[0], 0.0, places=3, msg=f"{pid}: not centred across")
            if pid in HUNG:
                self.assertEqual(p["pivot"], "ceiling", pid)
                self.assertAlmostEqual(hi[1], 0.0, places=4, msg=f"{pid}: its top is off the ceiling")
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=f"{pid}: not centred in depth")
                continue
            self.assertAlmostEqual(lo[1], 0.0, places=4, msg=f"{pid}: not on its base")
            if pid in WALL + WALL_SOLID:
                self.assertEqual(p["pivot"], "wall", pid)
                self.assertAlmostEqual(lo[2], 0.0, places=4, msg=f"{pid}: its back is off the wall")
            else:
                self.assertEqual(p.get("pivot", "floor"), "floor", pid)
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=f"{pid}: not centred in depth")

    def test_every_new_prop_keeps_its_class_budget(self):
        for pid in NEW:
            _, hi = LIB["budgets"][BY_ID[pid]["class"]]
            self.assertTrue(0 < self.built[pid]["triangles"] <= hi, f"{pid}: {self.built[pid]['triangles']}")

    def test_the_furniture_collides_with_one_box_inside_its_size(self):
        for pid in SOLID + WALL_SOLID:
            p, d = BY_ID[pid], self.built[pid]
            self.assertEqual(p["collision"], "box", pid)
            self.assertEqual(len(d["colliders"]), 1, pid)
            sx, sy, sz = _props.size_xyz(p["size_m"])
            for pt in d["colliders"][0]["points"]:
                self.assertLessEqual(abs(pt[0]), sx / 2 + OVER_M, pid)
                self.assertTrue(-1e-3 <= pt[1] <= sy + OVER_M, pid)
                if pid in WALL_SOLID:
                    self.assertTrue(-1e-3 <= pt[2] <= sz + OVER_M, pid)
                else:
                    self.assertLessEqual(abs(pt[2]), sz / 2 + OVER_M, pid)

    def test_the_flat_wall_and_hanging_pieces_have_no_collider(self):
        for pid in WALL + HUNG + FLAT + LOW:
            self.assertEqual(BY_ID[pid]["collision"], "none", pid)
            self.assertEqual(self.built[pid]["colliders"], [], pid)
        for pid in FLAT:
            self.assertLessEqual(self.built[pid]["size_m"][1], 0.015, f"{pid}: not floor-flat")

    def test_the_wall_pieces_stay_inside_their_depth(self):
        for pid in WALL + WALL_SOLID:
            depth = BY_ID[pid]["size_m"][1]
            b = self.built[pid]["bounds_m"]
            self.assertGreaterEqual(b["min"][2], -1e-4, f"{pid}: behind the wall")
            self.assertLessEqual(b["max"][2], depth + OVER_M, f"{pid}: deeper than its size")

    def test_the_rooms_points_are_known(self):
        for rid in ROOMS:
            _, points = _points(rid)
            self.assertEqual(sorted(p["name"] for p in points), POINTS[rid],
                             f"{rid}: its stations and spawn markers changed; the test below keeps them clear")

    def test_the_dressing_keeps_clear_of_every_station_and_spawn(self):
        for rid in ROOMS:
            _, points = _points(rid)
            for pt in points:
                for item, _, fp in self.placed[rid]:
                    if item.get("station") == pt["name"]:
                        continue
                    self.assertGreaterEqual(_box_dist(fp, pt["at"][0], pt["at"][2]), CLEAR_M,
                                            f"{rid}: {item['id']} at {item['at']} within {CLEAR_M} m of {pt['name']}")

    def test_the_task_props_are_kept(self):
        for rid, want in TASK_PROPS.items():
            got = Counter(item["id"] for item, _, _ in self.placed[rid] if item["id"] in TASKS)
            self.assertEqual(dict(got), want, rid)

    def test_the_doors_stay_clear(self):
        lv = _basement()
        for rid in ROOMS:
            room, _ = _points(rid)
            x0, z0, w, d = room["rect"]
            doors = [dr for dr in lv["doors"] if rid in dr["rooms"]]
            self.assertEqual(len(doors), DOORS[rid], rid)
            for dr in doors:
                x, z = dr["at"][0] - x0, dr["at"][1] - z0
                if abs(x) < 1e-6 or abs(x - w) < 1e-6:  # a west or east door: the opening runs along z
                    xa, xb = (0.0, DOOR_DEPTH_M) if abs(x) < 1e-6 else (w - DOOR_DEPTH_M, w)
                    zone = (xa, xb, z - DOOR_CLEAR_M / 2, z + DOOR_CLEAR_M / 2)
                else:  # a north or south door
                    za, zb = (0.0, DOOR_DEPTH_M) if abs(z) < 1e-6 else (d - DOOR_DEPTH_M, d)
                    zone = (x - DOOR_CLEAR_M / 2, x + DOOR_CLEAR_M / 2, za, zb)
                for item, _, fp in self.placed[rid]:
                    p = BY_ID.get(item["id"], {})
                    if item.get("collision", p.get("collision", "box")) == "none":
                        continue
                    if p.get("pivot") == "wall" and item["at"][1] >= 2.1:
                        continue
                    xs, zs = [q[0] for q in fp], [q[1] for q in fp]
                    inside = min(xs) < zone[1] and max(xs) > zone[0] and min(zs) < zone[3] and max(zs) > zone[2]
                    self.assertFalse(inside, f"{rid}: {item['id']} at {item['at']} stands in front of the door at "
                                             f"{dr['at']}")

    def test_the_rooms_are_hand_placed(self):
        """The clutter rules of the rooms are empty, so `house --clutter` never refills them."""
        from runner import house_clutter
        for rid in ROOMS:
            self.assertTrue(all(not v for v in house_clutter.RULES[rid].values()), rid)

    def test_the_rooms_are_never_emptier_than_before(self):
        for rid in ROOMS:  # props against props: placed holds the [[props]] entries only, never the fixtures
            dressing = _dressing(rid)
            self.assertEqual(len(self.placed[rid]), len(dressing["props"]), rid)
            self.assertGreaterEqual(len(dressing["props"]), BEFORE[rid], rid)

    def test_the_rooms_keep_mains_big_pieces(self):
        for rid, groups in BIG.items():
            ids = {item["id"] for item, _, _ in self.placed[rid]}
            for group in groups:
                self.assertTrue(ids & set(group), f"{rid}: none of {group} placed")

    def test_the_rooms_are_never_derelict(self):
        """The basement is clean and present-day: no barrels, pipe runs, jerrycans or old cardboard and wooden crates."""
        for rid in ROOMS:
            ids = {item["id"] for item, _, _ in self.placed[rid]}
            self.assertFalse(ids & {"barrel", "pipe_run", "jerrycan", "crate", "cardboard_box", "metal_shelving"}, rid)

    def test_the_name_label_sits_in_no_piece(self):
        h = HOUSE["export"]["label"]["h"]
        for rid in ROOMS:
            room, _ = _points(rid)
            w, d = room["rect"][2], room["rect"][3]
            lx, lz = ((room["label_at"][0] - room["rect"][0], room["label_at"][1] - room["rect"][1])
                      if room.get("label_at") else (w / 2, d / 2))
            for item, built, fp in self.placed[rid]:
                y0 = item["at"][1] + built["bounds_m"]["min"][1]
                y1 = item["at"][1] + built["bounds_m"]["max"][1]
                self.assertFalse(_box_dist(fp, lx, lz) < 0.2 and y0 - 0.3 < h < y1 + 0.3,
                                 f"{rid}: the Name label at ({lx}, {h}, {lz}) is inside {item['id']} at {item['at']}")
            for item in _dressing(rid).get("fixtures", []):  # nor on a light fixture (#165's label sat on a pendant)
                p = BY_ID[item["id"]]
                x, y, z = _props.size_xyz(p["size_m"])
                z0 = 0.0 if p.get("pivot") == "wall" else -z / 2
                y0 = -y if p.get("pivot") == "ceiling" else 0.0
                fp = _footprint(item, {"bounds_m": {"min": [-x / 2, y0, z0], "max": [x / 2, y0 + y, z0 + z]}})
                lo, hi = item["at"][1] + y0, item["at"][1] + y0 + y
                self.assertFalse(_box_dist(fp, lx, lz) < 0.2 and lo - 0.3 < h < hi + 0.3,
                                 f"{rid}: the Name label at ({lx}, {h}, {lz}) is on the fixture {item['id']} at "
                                 f"{item['at']}")


    def test_the_darkroom_island_leaves_the_walk_round_it(self):
        """#172: a 1.2 m walk between the island's benches and every other solid floor piece and wall face; the door's
        line to the photo board (x 8, a 0.6 m band) stays clear."""
        room, _ = _points("darkroom")
        w, d = room["rect"][2], room["rect"][3]
        island = [(it, fp) for it, _, fp in self.placed["darkroom"] if it["id"] in ISLAND]
        self.assertEqual(sorted(it["id"] for it, _ in island), sorted(ISLAND))
        others = [(it, fp) for it, _, fp in self.placed["darkroom"]
                  if it["id"] not in ISLAND + ("stool",) and it["at"][1] < 0.5
                  and BY_ID.get(it["id"], {}).get("collision", "box") != "none"
                  and BY_ID.get(it["id"], {}).get("pivot", "floor") == "floor"]
        self.assertGreater(len(others), 10)
        for it, fp in island:
            xs, zs = [p[0] for p in fp], [p[1] for p in fp]
            self.assertGreaterEqual(min(min(xs), w - max(xs), min(zs), d - max(zs)), WALK_M, it["id"])
            self.assertTrue(max(xs) < 8 - 0.3 or min(xs) > 8 + 0.3, f"{it['id']} on the door's line to the board")
            for ot, ofp in others:
                ox, oz = [p[0] for p in ofp], [p[1] for p in ofp]
                gap = math.hypot(max(min(ox) - max(xs), 0.0, min(xs) - max(ox)),
                                 max(min(oz) - max(zs), 0.0, min(zs) - max(oz)))
                self.assertGreaterEqual(gap, WALK_M - 1e-6, f"{it['id']} at {it['at']}: {ot['id']} at {ot['at']}")


if __name__ == "__main__":
    unittest.main()
