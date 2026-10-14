"""The hallway's new props (#156, docs/props.md "World look rules"): every one builds at its size_m (never more than
15 mm over it), at its pivot and under its class's triangle budget; the console, the coat hooks, the bench and the
umbrella stand collide with one box inside their size, the mirror, the runner, the wall art and the detail layer have
no collider; the wall pieces stay inside their depth; the console's things stand on its top without touching; and
the dressing keeps 0.3 m from every station and spawn marker in the room (read from layouts/house/*.toml and
props/tasks.toml) and leaves the four doors' openings clear. Pure Python, no Blender."""

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
TASKS = tomllib.loads((common.ROOT / "props" / "tasks.toml").read_text(encoding="utf-8"))["props"]
DRESSING = tomllib.loads((LAYOUT / "dressing" / "hallway.toml").read_text(encoding="utf-8"))

SOLID = ("hall_console", "coat_hooks", "hall_bench", "umbrella_stand")
WALL = ("hall_mirror", "coat_hooks", "art_blueprint", "photo_row", "wall_calendar")
DETAIL = ("hall_doormat", "key_bowl", "parcels", "shoe_pairs", "sports_bag", "photo_row", "wall_calendar")
NEW = SOLID + DETAIL + ("hall_mirror", "hall_runner", "art_blueprint")
ON_CONSOLE = ("key_bowl", "mail_stack", "side_lamp")
OVER_M = 0.015  # a prop may stand at most this far over its size_m
TOP_MARGIN_M = 0.01  # a thing on the console keeps this far inside its top's edge
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


def _hallway() -> tuple[dict, list[dict]]:
    """The hallway's room record and every point it must keep clear, room-local: its stations, every level's
    spawn markers inside its rectangle and the task props placed in it."""
    ground = tomllib.loads((LAYOUT / "ground.toml").read_text(encoding="utf-8"))
    room = next(r for r in ground["rooms"] if r["id"] == "hallway")
    x0, z0, w, d = room["rect"]
    points = [{"name": s["name"], "at": s["at"]} for s in room.get("stations", [])]
    for r in ground["rooms"]:
        rx, rz = r["rect"][0], r["rect"][1]
        for mk in r.get("markers", []):
            gx, gz = rx + mk["at"][0], rz + mk["at"][2]
            if x0 <= gx <= x0 + w and z0 <= gz <= z0 + d:
                points.append({"name": mk["name"], "at": [gx - x0, 0.0, gz - z0]})
    for t in TASKS:
        if t.get("room") == "hallway":
            points.append({"name": t["id"], "at": t.get("at", [0.0, 0.0, 0.0])})
    return room, points


class HallwayPropsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {pid: _build(pid) for pid in NEW}
        cls.placed = []
        for item in DRESSING["props"]:
            if "size" in item:
                L, W, H = item["size"]
                built = {"bounds_m": {"min": [-L / 2, 0.0, -W / 2], "max": [L / 2, H, W / 2]}}
            elif "shape" not in BY_ID.get(item["id"], {"shape": ""}):  # a pack prop: its box from size_m
                x, y, z = _props.size_xyz(BY_ID[item["id"]]["size_m"])
                z0 = 0.0 if BY_ID[item["id"]].get("pivot") == "wall" else -z / 2
                built = {"bounds_m": {"min": [-x / 2, 0.0, z0], "max": [x / 2, y, z0 + z]}}
            else:
                built = cls.built.get(item["id"]) or _build(item["id"])
            cls.placed.append((item, built, _footprint(item, built)))

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
            lo, hi = LIB["budgets"][BY_ID[pid]["class"]]
            self.assertTrue(lo <= self.built[pid]["triangles"] <= hi, f"{pid}: {self.built[pid]['triangles']}")

    def test_the_furniture_collides_with_one_box_inside_its_size(self):
        for pid in SOLID:
            p, d = BY_ID[pid], self.built[pid]
            self.assertEqual(p["collision"], "box", pid)
            self.assertEqual(len(d["colliders"]), 1, pid)
            sx, sy, sz = _props.size_xyz(p["size_m"])
            for pt in d["colliders"][0]["points"]:
                self.assertLessEqual(abs(pt[0]), sx / 2 + 1e-4, pid)
                self.assertTrue(-1e-3 <= pt[1] <= sy + 1e-3, pid)
                if p["pivot"] == "wall":
                    self.assertTrue(-1e-4 <= pt[2] <= sz + 1e-4, pid)
                else:
                    self.assertLessEqual(abs(pt[2]), sz / 2 + 1e-4, pid)

    def test_the_detail_layer_and_the_flat_pieces_have_no_collider(self):
        for pid in DETAIL + ("hall_mirror", "hall_runner", "art_blueprint"):
            self.assertEqual(BY_ID[pid]["collision"], "none", pid)
            self.assertEqual(self.built[pid]["colliders"], [], pid)
        for pid in DETAIL:
            layer = BY_ID[pid].get("layer") or LIB["layers"].get(BY_ID[pid]["class"], LIB["layers"]["default"])
            self.assertEqual(layer, "detail", pid)

    def test_the_wall_pieces_stay_inside_their_depth(self):
        for pid in WALL:
            depth = BY_ID[pid]["size_m"][1]
            b = self.built[pid]["bounds_m"]
            self.assertGreaterEqual(b["min"][2], -1e-4, f"{pid}: behind the wall")
            self.assertLessEqual(b["max"][2], depth + 1e-4, f"{pid}: deeper than its size")

    def test_the_console_things_stand_on_its_top_apart(self):
        console = next(i for i in DRESSING["props"] if i["id"] == "hall_console")
        L, W, H = BY_ID["hall_console"]["size_m"]
        x0, x1 = console["at"][0] - L / 2 + TOP_MARGIN_M, console["at"][0] + L / 2 - TOP_MARGIN_M
        z0, z1 = console["at"][2] - W / 2 + TOP_MARGIN_M, console["at"][2] + W / 2 - TOP_MARGIN_M
        on = [(i, fp) for i, _, fp in self.placed if i["id"] in ON_CONSOLE]
        self.assertEqual(sorted(i["id"] for i, _ in on), sorted(ON_CONSOLE))
        for item, fp in on:
            self.assertAlmostEqual(item["at"][1], H, places=4, msg=f"{item['id']}: not on the top")
            for x, z in fp:
                self.assertTrue(x0 <= x <= x1 and z0 <= z <= z1, f"{item['id']}: ({x:.3f}, {z:.3f}) off the top")
        for k, (a, fa) in enumerate(on):
            for b, fb in on[k + 1:]:
                apart = (max(p[0] for p in fa) <= min(p[0] for p in fb) or max(p[0] for p in fb) <= min(p[0] for p in fa)
                         or max(p[1] for p in fa) <= min(p[1] for p in fb)
                         or max(p[1] for p in fb) <= min(p[1] for p in fa))
                self.assertTrue(apart, f"{a['id']} and {b['id']} overlap on the console")

    def test_the_dressing_keeps_clear_of_every_station_and_spawn(self):
        _, points = _hallway()
        for pt in points:
            for item, _, fp in self.placed:
                if item.get("station") == pt["name"]:
                    continue
                self.assertGreaterEqual(_box_dist(fp, pt["at"][0], pt["at"][2]), CLEAR_M,
                                        f"{item['id']} at {item['at']} within {CLEAR_M} m of {pt['name']}")

    def test_the_doors_stay_clear(self):
        room, _ = _hallway()
        x0, z0, w, d = room["rect"]
        ground = tomllib.loads((LAYOUT / "ground.toml").read_text(encoding="utf-8"))
        doors = [dr for dr in ground["doors"] if "hallway" in dr["rooms"]]
        self.assertEqual(len(doors), 4, "the hallway has four doors")
        for dr in doors:
            x, z = dr["at"][0] - x0, dr["at"][1] - z0
            if abs(x) < 1e-6 or abs(x - w) < 1e-6:  # a west or east door: the opening runs along z
                xa, xb = (0.0, DOOR_DEPTH_M) if abs(x) < 1e-6 else (w - DOOR_DEPTH_M, w)
                zone = (xa, xb, z - DOOR_CLEAR_M / 2, z + DOOR_CLEAR_M / 2)
            else:  # a north or south door
                za, zb = (0.0, DOOR_DEPTH_M) if abs(z) < 1e-6 else (d - DOOR_DEPTH_M, d)
                zone = (x - DOOR_CLEAR_M / 2, x + DOOR_CLEAR_M / 2, za, zb)
            for item, _, fp in self.placed:
                p = BY_ID.get(item["id"], {})
                if item.get("collision", p.get("collision", "box")) == "none":
                    continue
                if p.get("pivot") == "wall" and item["at"][1] >= 2.1:
                    continue
                xs, zs = [q[0] for q in fp], [q[1] for q in fp]
                inside = min(xs) < zone[1] and max(xs) > zone[0] and min(zs) < zone[3] and max(zs) > zone[2]
                self.assertFalse(inside, f"{item['id']} at {item['at']} stands in front of the door at {dr['at']}")


if __name__ == "__main__":
    unittest.main()
