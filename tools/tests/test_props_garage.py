"""The garage (#79, package P6; docs/props.md "The garage"): its new props build at their size_m (never more than
15 mm over it), at their pivot and under their class's triangle budget, with the colliders they name; the car and the
lift are separate pieces (the static posts, the moving arms and the car on the CarLift station) and the raised car's
underside stands at the car repair ADR's 1.4 m (RD2) over the arms' pads; the dressing keeps 0.3 m from the garage's
three stations and two spawn markers (read from layouts/house/ground.toml, counted); and from the lift panel's eye
points no ray reaches the space under the raised car (the car repair's RD2: the holder has no view of who is under
it). Pure Python, no Blender."""

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
TASKS = {t["id"]: t for t in tomllib.loads((common.ROOT / "props" / "tasks.toml").read_text(encoding="utf-8"))["props"]}

SOLID = ("garage_car", "lift_posts", "lift_arms", "lift_panel", "tyre_rack", "steel_cupboard")
WALL = ("part_picture",)
FLAT = ("floor_lift_zone",)
NEW = SOLID + WALL + FLAT
COLLIDERS = {"garage_car": 2, "lift_posts": 3, "lift_arms": 2, "lift_panel": 1, "tyre_rack": 1, "steel_cupboard": 1}
MOVING = ("lift_arms", "garage_car")  # the CarLift station's pieces the game raises and drops together
OVER_M = 0.015
CLEAR_M = 0.3
POINTS = ["CarLift", "Circle04", "Knife2", "LiftPanel", "Workbench"]
SILL_M = 0.16  # the car's sills' underside on its wheels (params.sill)
RAISED_UNDERSIDE_M = 1.4  # the car repair ADR's RD2: the raised car's underside
RAISE_M = RAISED_UNDERSIDE_M - SILL_M  # 1.24 m: HANDOFF.md's lift_raise_m
EYE_HEIGHTS = (1.0, 1.3, 1.6)  # crouched (the ADR's 1.0 m eye) to standing (1.6 m)
EYE_REACH_M = 0.75  # the holder's eye points: the station marker and a half ring this far round it, the panel's side
UNDER_HEIGHTS = (0.15, 0.5, 0.9, 1.25)  # a lying, crouched and kneeling fitter under the raised car
FACES = {"S": 0, "E": 90, "N": 180, "W": -90}  # house_dressing.FACES


def _build(pid: str) -> dict:
    return prop_geom.build(BY_ID[pid], SPEC, STYLE)


def _garage() -> tuple[dict, list[dict]]:
    lv = tomllib.loads((LAYOUT / "ground.toml").read_text(encoding="utf-8"))
    room = next(r for r in lv["rooms"] if r["id"] == "garage")
    x0, z0, w, d = room["rect"]
    points = [{"name": s["name"], "at": s["at"]} for s in room.get("stations", [])]
    for r in lv["rooms"]:
        for mk in r.get("markers", []):
            gx, gz = r["rect"][0] + mk["at"][0], r["rect"][1] + mk["at"][2]
            if x0 <= gx <= x0 + w and z0 <= gz <= z0 + d:
                points.append({"name": mk["name"], "at": [gx - x0, 0.0, gz - z0]})
    return room, points


def _dressing() -> list[dict]:
    return tomllib.loads((LAYOUT / "dressing" / "garage.toml").read_text(encoding="utf-8"))["props"]


def _yaw(item: dict) -> float:
    return math.radians(float(item.get("yaw", FACES[item.get("face", "S")])))


def _to_room(item: dict, p, lift: float = 0.0) -> tuple[float, float, float]:
    a = _yaw(item)
    return (item["at"][0] + p[0] * math.cos(a) + p[2] * math.sin(a), item["at"][1] + p[1] + lift,
            item["at"][2] - p[0] * math.sin(a) + p[2] * math.cos(a))


def _to_local(item: dict, q, lift: float = 0.0) -> tuple[float, float, float]:
    a = _yaw(item)
    dx, dz = q[0] - item["at"][0], q[2] - item["at"][2]
    return (dx * math.cos(a) - dz * math.sin(a), q[1] - item["at"][1] - lift, dx * math.sin(a) + dz * math.cos(a))


def _local_bounds(item: dict) -> tuple[list, list]:
    if item["id"] in BY_ID:
        b = _build(item["id"])["bounds_m"]
        return b["min"], b["max"]
    t = TASKS[item["id"]]
    z0 = 0.0 if t.get("pivot") == "wall" else -t["d"] / 2
    return [-t["w"] / 2, 0.0, z0], [t["w"] / 2, t["h"], z0 + t["d"]]


def _footprint(item: dict) -> list[tuple[float, float]]:
    lo, hi = _local_bounds(item)
    return [(p[0], p[2]) for p in (_to_room(item, (x, 0.0, z)) for x in (lo[0], hi[0]) for z in (lo[2], hi[2]))]


def _box_dist(fp, x: float, z: float) -> float:
    xs, zs = [p[0] for p in fp], [p[1] for p in fp]
    return math.hypot(max(min(xs) - x, 0.0, x - max(xs)), max(min(zs) - z, 0.0, z - max(zs)))


def _hits(lo, hi, a, b) -> bool:
    """The segment a -> b meets the box lo..hi (slab test)."""
    t0, t1 = 0.0, 1.0
    for i in range(3):
        d = b[i] - a[i]
        if abs(d) < 1e-12:
            if a[i] < lo[i] or a[i] > hi[i]:
                return False
            continue
        u, v = (lo[i] - a[i]) / d, (hi[i] - a[i]) / d
        t0, t1 = max(t0, min(u, v)), min(t1, max(u, v))
        if t0 > t1:
            return False
    return True


class GaragePropsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {pid: _build(pid) for pid in NEW}

    def test_every_new_prop_builds_at_its_size(self):
        for pid in NEW:
            want, got = _props.size_xyz(BY_ID[pid]["size_m"]), self.built[pid]["size_m"]
            for g, w in zip(got, want):
                self.assertLessEqual(g, w + OVER_M, f"{pid}: built {got}, want {want}")
                self.assertGreaterEqual(g, w - max(0.03, 0.12 * w), f"{pid}: built {got}, want {want}")

    def test_every_new_prop_sits_at_its_pivot(self):
        for pid in NEW:
            lo, hi = self.built[pid]["bounds_m"]["min"], self.built[pid]["bounds_m"]["max"]
            self.assertAlmostEqual(lo[0] + hi[0], 0.0, places=3, msg=pid)
            self.assertAlmostEqual(lo[1], 0.0, places=4, msg=pid)
            if pid in WALL:
                self.assertEqual(BY_ID[pid]["pivot"], "wall", pid)
                self.assertAlmostEqual(lo[2], 0.0, places=4, msg=pid)
            else:
                self.assertEqual(BY_ID[pid]["pivot"], "floor", pid)
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=pid)

    def test_every_new_prop_keeps_its_class_budget(self):
        for pid in NEW:
            _, top = LIB["budgets"][BY_ID[pid]["class"]]
            self.assertTrue(0 < self.built[pid]["triangles"] <= top, f"{pid}: {self.built[pid]['triangles']}")

    def test_the_colliders(self):
        for pid, n in COLLIDERS.items():
            self.assertEqual(BY_ID[pid]["collision"], "box", pid)
            self.assertEqual(len(self.built[pid]["colliders"]), n, pid)
            sx, sy, sz = _props.size_xyz(BY_ID[pid]["size_m"])
            for c in self.built[pid]["colliders"]:
                for pt in c["points"]:
                    self.assertLessEqual(abs(pt[0]), sx / 2 + OVER_M, pid)
                    self.assertTrue(-1e-3 <= pt[1] <= sy + OVER_M, pid)
                    self.assertLessEqual(abs(pt[2]), sz / 2 + OVER_M, pid)
        for pid in WALL + FLAT:
            self.assertEqual(self.built[pid]["colliders"], [], pid)
            self.assertEqual(BY_ID[pid].get("layer"), "base", pid)

    def test_the_dressing_blocks_are_the_builders_colliders(self):
        """house_dressing's capsule grid uses an item's `blocks` instead of its size box: they must be its real
        colliders' footprints (every collider that reaches the capsule's heights, 0.3 to 1.8 m)."""
        blocked = [i for i in _dressing() if "blocks" in i]
        self.assertEqual(sorted(i["id"] for i in blocked), ["lift_arms", "lift_posts"])
        for item in blocked:
            want = []
            for c in self.built[item["id"]]["colliders"]:
                xs, ys, zs = zip(*c["points"])
                if min(ys) < 1.8 and max(ys) > 0.3:
                    want.append([round(min(xs), 2), round(min(zs), 2), round(max(xs), 2), round(max(zs), 2)])
            self.assertEqual(sorted(want), sorted([round(v, 2) for v in b] for b in item["blocks"]), item["id"])
        self.assertEqual({i["id"] for i in _dressing() if i.get("assembly") == "car_lift"},
                         {"lift_posts", "lift_arms", "garage_car"})

    def test_the_car_and_the_lift_are_separate_pieces(self):
        items = {i["id"]: i for i in _dressing() if i.get("station") == "CarLift"}
        self.assertEqual(sorted(items), ["floor_lift_zone", "garage_car", "lift_arms", "lift_posts"])
        car, arms = items["garage_car"], items["lift_arms"]
        self.assertEqual((car["at"][0], car["at"][2], car["face"]), (arms["at"][0], arms["at"][2], arms["face"]))
        # the car's lowest collider (its sills) rests on the arms' pads
        car_lo = min(pt[1] for c in self.built["garage_car"]["colliders"] for pt in c["points"]) + car["at"][1]
        self.assertAlmostEqual(car_lo, SILL_M, places=3)
        mesh = self.built["lift_arms"]["meshes"][0]
        pads = {v for f, r in zip(mesh["faces"], mesh["roles"]) if r == "rubber_black" for v in f}
        self.assertAlmostEqual(arms["at"][1] + max(mesh["verts"][v][1] for v in pads), SILL_M, places=3)
        # raised, the car's underside is RD2's 1.4 m and its roof stays under the 3 m ceiling
        self.assertAlmostEqual(car_lo + RAISE_M, RAISED_UNDERSIDE_M, places=3)
        self.assertLess(self.built["garage_car"]["bounds_m"]["max"][1] + RAISE_M, 2.95)
        # a crouched player (the ADR's 1.2 m capsule) fits under the raised arms and car, between the posts
        half = self.built["garage_car"]["bounds_m"]["max"][0]
        arms_lo = min(v[1] for v in mesh["verts"] if abs(v[0]) < half) + arms["at"][1] + RAISE_M
        self.assertGreater(min(arms_lo, RAISED_UNDERSIDE_M), 1.2)

    def test_the_stations_and_spawns_stay_clear(self):
        _, points = _garage()
        self.assertEqual(sorted(p["name"] for p in points), POINTS)
        for pt in points:
            for item in _dressing():
                if item.get("station") == pt["name"]:
                    continue
                d = _box_dist(_footprint(item), pt["at"][0], pt["at"][2])
                self.assertGreaterEqual(d, CLEAR_M, f"{item['id']} at {item['at']} within {CLEAR_M} m of {pt['name']}")

    def test_no_ray_from_the_panel_reaches_under_the_raised_car(self):
        room, _ = _garage()
        st = {s["name"]: s["at"] for s in room["stations"]}
        items = _dressing()
        panel = next(i for i in items if i["id"] == "lift_panel")
        car = next(i for i in items if i["id"] == "garage_car")
        # the holder's eye points: the marker and a half ring round it on the panel's front side
        px, pz = st["LiftPanel"][0], st["LiftPanel"][2]
        fx, fz = px - panel["at"][0], pz - panel["at"][2]
        f = math.hypot(fx, fz)
        eyes = [(px, h, pz) for h in EYE_HEIGHTS]
        for k in range(9):
            a = math.atan2(fz / f, fx / f) + math.radians(-90 + 22.5 * k)
            eyes += [(px + EYE_REACH_M * math.cos(a), h, pz + EYE_REACH_M * math.sin(a)) for h in EYE_HEIGHTS]
        # the space under the raised car: a grid inside its body's footprint, from the floor to under the sills
        b = self.built["garage_car"]["bounds_m"]
        under = [_to_room(car, (x, y, z)) for x in (b["min"][0] + 0.3, 0.0, b["max"][0] - 0.3)
                 for z in [b["min"][2] + 0.5 + k * (b["max"][2] - b["min"][2] - 1.0) / 6 for k in range(7)]
                 for y in UNDER_HEIGHTS]
        # the occluders: every solid prop's colliders, the moving pieces raised
        boxes = []
        for item in items:
            if item["id"] not in BY_ID or BY_ID[item["id"]]["collision"] == "none":
                continue
            lift = RAISE_M if item["id"] in MOVING else 0.0
            for c in _build(item["id"])["colliders"]:
                lo = [min(pt[i] for pt in c["points"]) for i in range(3)]
                hi = [max(pt[i] for pt in c["points"]) for i in range(3)]
                boxes.append((item, lift, lo, hi))
        seen = []
        for e in eyes:
            for u in under:
                if not any(_hits(lo, hi, _to_local(it, e, lift), _to_local(it, u, lift)) for it, lift, lo, hi in boxes):
                    seen.append((tuple(round(v, 2) for v in e), tuple(round(v, 2) for v in u)))
        self.assertEqual(len(eyes) * len(under), 30 * 84)
        self.assertEqual(seen[:5], [], f"{len(seen)} rays from the panel reach under the car")


if __name__ == "__main__":
    unittest.main()
