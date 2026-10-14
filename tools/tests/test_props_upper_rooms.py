"""The upper floor's landing and bathroom (#162, docs/props.md "World look rules"): their new props build at their
size_m (never more than 15 mm over it), at their pivot and under their class's triangle budget; the furniture
collides with one box inside its size, the wall pieces and the flat pieces have no collider and the wall pieces stay
inside their depth; each room's dressing keeps 0.3 m from every station and spawn marker in it (read from
layouts/house/upper.toml and props/tasks.toml: none today, asserted), leaves its doors' openings, the attic hatch's
ladder and the stairs' top clear, keeps its prop count (never emptier than before the pass) and keeps its Name label
out of every piece. Pure Python, no Blender."""

from __future__ import annotations

import json
import math
import sys
import tomllib
import unittest

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
TASKS = tomllib.loads((common.ROOT / "props" / "tasks.toml").read_text(encoding="utf-8"))["props"]
ROOMS = ("landing", "bathroom")
DOORS = {"landing": 6, "bathroom": 1}
# The [[props]] entries on main before #162's pass (fixtures not counted; the test counts the same after it).
BEFORE = {"landing": 66, "bathroom": 40}
# The big furniture main's landing had (a sitting area: armchairs and a rug) that the pass keeps (round 2): one of
# each id group at least.
BIG = {"landing": [("sofa", "armchair"), ("rug",)]}

SOLID = ("bath_tub", "bath_vanity", "bath_shelf")
WALL = ("towel_rail", "art_bubbles", "bath_tiles", "bath_tiles_short", "bath_tiles_shower")
FLAT = WALL + ("bath_mat", "landing_runner")
NEW = SOLID + FLAT
OVER_M = 0.015  # a prop may stand at most this far over its size_m
CLEAR_M = 0.3  # nothing of the dressing this close to a station's point or a spawn marker
DOOR_CLEAR_M = 1.4  # house_dressing.DOOR_CLEAR["door"]: the opening's clear width
DOOR_DEPTH_M = 0.8  # the floor kept free in front of a door, into the room
FACES = {"S": 0, "E": 90, "N": 180, "W": -90}  # house_dressing.FACES
# The landing's walk ways kept free of solid props (room-local x0, x1, z0, z1): round the attic hatch's ladder (the
# hatch's hole centres at plan (28, 29), attic.toml) and the stairs' top (they climb east onto the landing at x 4).
KEEP_FREE = {"landing": [(1.0, 3.5, 3.0, 6.0), (4.0, 5.5, 8.0, 10.0)]}


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


def _upper() -> dict:
    return tomllib.loads((LAYOUT / "upper.toml").read_text(encoding="utf-8"))


def _points(rid: str) -> tuple[dict, list[dict]]:
    """A room's record and every point it must keep clear, room-local: its stations, every room's spawn markers
    inside its rectangle and the task props placed in it."""
    ground = _upper()
    room = next(r for r in ground["rooms"] if r["id"] == rid)
    x0, z0, w, d = room["rect"]
    points = [{"name": s["name"], "at": s["at"]} for s in room.get("stations", [])]
    for r in ground["rooms"]:
        rx, rz = r["rect"][0], r["rect"][1]
        for mk in r.get("markers", []):
            gx, gz = rx + mk["at"][0], rz + mk["at"][2]
            if x0 <= gx <= x0 + w and z0 <= gz <= z0 + d:
                points.append({"name": mk["name"], "at": [gx - x0, 0.0, gz - z0]})
    for t in TASKS:
        if rid in [r.strip() for r in str(t.get("room", "")).split(",")]:
            points.append({"name": t["id"], "at": t.get("at", [0.0, 0.0, 0.0])})
    return room, points


class UpperRoomsPropsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {pid: _build(pid) for pid in NEW}
        cls.placed = {}
        for rid in ROOMS:
            dressing = tomllib.loads((LAYOUT / "dressing" / f"{rid}.toml").read_text(encoding="utf-8"))
            cls.placed[rid] = []
            for item in dressing["props"]:
                if "size" in item:
                    L, W, H = item["size"]
                    built = {"bounds_m": {"min": [-L / 2, 0.0, -W / 2], "max": [L / 2, H, W / 2]}}
                elif "shape" not in BY_ID.get(item["id"], {"shape": ""}):  # a pack prop: its box from size_m
                    x, y, z = _props.size_xyz(BY_ID[item["id"]]["size_m"])
                    z0 = 0.0 if BY_ID[item["id"]].get("pivot") == "wall" else -z / 2
                    built = {"bounds_m": {"min": [-x / 2, 0.0, z0], "max": [x / 2, y, z0 + z]}}
                else:
                    built = cls.built.get(item["id"]) or _build(item["id"])
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
            self.assertAlmostEqual(lo[1], 0.0, places=4, msg=f"{pid}: not on its base")
            if pid in WALL:
                self.assertEqual(p["pivot"], "wall", pid)
                self.assertAlmostEqual(lo[2], 0.0, places=4, msg=f"{pid}: its back is off the wall")
            else:
                self.assertEqual(p["pivot"], "floor", pid)
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=f"{pid}: not centred in depth")

    def test_every_new_prop_keeps_its_class_budget(self):
        for pid in NEW:
            _, hi = LIB["budgets"][BY_ID[pid]["class"]]  # under the minimum is only a note (simple is fine)
            self.assertTrue(0 < self.built[pid]["triangles"] <= hi, f"{pid}: {self.built[pid]['triangles']}")

    def test_the_furniture_collides_with_one_box_inside_its_size(self):
        for pid in SOLID:
            p, d = BY_ID[pid], self.built[pid]
            self.assertEqual(p["collision"], "box", pid)
            self.assertEqual(len(d["colliders"]), 1, pid)
            sx, sy, sz = _props.size_xyz(p["size_m"])
            for pt in d["colliders"][0]["points"]:
                self.assertLessEqual(abs(pt[0]), sx / 2 + OVER_M, pid)
                self.assertTrue(-1e-3 <= pt[1] <= sy + OVER_M, pid)
                self.assertLessEqual(abs(pt[2]), sz / 2 + OVER_M, pid)

    def test_the_flat_pieces_have_no_collider(self):
        for pid in FLAT:
            self.assertEqual(BY_ID[pid]["collision"], "none", pid)
            self.assertEqual(self.built[pid]["colliders"], [], pid)
        for pid in ("bath_tiles", "bath_tiles_short", "bath_tiles_shower"):
            self.assertEqual(BY_ID[pid].get("layer"), "base", pid)  # the tiled walls read on Low

    def test_the_wall_pieces_stay_inside_their_depth(self):
        for pid in WALL:
            depth = BY_ID[pid]["size_m"][1]
            b = self.built[pid]["bounds_m"]
            self.assertGreaterEqual(b["min"][2], -1e-4, f"{pid}: behind the wall")
            self.assertLessEqual(b["max"][2], depth + OVER_M, f"{pid}: deeper than its size")

    def test_the_rooms_have_no_station_or_spawn_today(self):
        for rid in ROOMS:
            _, points = _points(rid)
            self.assertEqual([p["name"] for p in points], [],
                             f"{rid} has no station, spawn marker or task prop today (#162); a new one must be kept "
                             "clear by the test below")

    def test_the_dressing_keeps_clear_of_every_station_and_spawn(self):
        for rid in ROOMS:
            _, points = _points(rid)
            for pt in points:
                for item, _, fp in self.placed[rid]:
                    if item.get("station") == pt["name"]:
                        continue
                    self.assertGreaterEqual(_box_dist(fp, pt["at"][0], pt["at"][2]), CLEAR_M,
                                            f"{rid}: {item['id']} at {item['at']} within {CLEAR_M} m of {pt['name']}")

    def test_the_doors_stay_clear(self):
        ground = _upper()
        for rid in ROOMS:
            room, _ = _points(rid)
            x0, z0, w, d = room["rect"]
            doors = [dr for dr in ground["doors"] if rid in dr["rooms"]]
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
        """#162: the clutter rules of the two rooms are empty, so `house --clutter` never refills them."""
        from runner import house_clutter
        for rid in ROOMS:
            self.assertTrue(all(not v for v in house_clutter.RULES[rid].values()), rid)

    def test_the_walk_ways_stay_free(self):
        for rid, zones in KEEP_FREE.items():
            for x0, x1, z0, z1 in zones:
                for item, _, fp in self.placed[rid]:
                    p = BY_ID.get(item["id"], {})
                    if item.get("collision", p.get("collision", "box")) == "none" or p.get("pivot") == "wall":
                        continue
                    xs, zs = [q[0] for q in fp], [q[1] for q in fp]
                    inside = min(xs) < x1 and max(xs) > x0 and min(zs) < z1 and max(zs) > z0
                    self.assertFalse(inside, f"{rid}: {item['id']} at {item['at']} in the walk way {(x0, x1, z0, z1)}")

    def test_the_rooms_are_never_emptier_than_before(self):
        for rid in ROOMS:  # props against props: placed holds the [[props]] entries only, never the fixtures
            dressing = tomllib.loads((LAYOUT / "dressing" / f"{rid}.toml").read_text(encoding="utf-8"))
            self.assertEqual(len(self.placed[rid]), len(dressing["props"]), rid)
            self.assertGreaterEqual(len(dressing["props"]), BEFORE[rid], rid)

    def test_the_landing_keeps_mains_big_furniture(self):
        for rid, groups in BIG.items():
            ids = {item["id"] for item, _, _ in self.placed[rid]}
            for group in groups:
                self.assertTrue(ids & set(group), f"{rid}: none of {group} placed (main had them; round 2)")

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


if __name__ == "__main__":
    unittest.main()
