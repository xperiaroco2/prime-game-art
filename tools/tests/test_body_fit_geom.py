"""The bodies' station fit (art #196, step D3): body_fit_geom's helpers, a fit of a synthetic trunk to a synthetic
table (the error table goes to zero, the neck ring stays exact), the error summary's rules, the chest rounds' share,
and body_fit_run's B rest from a synthetic skeleton (the joints from fit.toml, the Neck and Head about B's ring, the
hands and feet scaled). Plain Python: no Blender, no raw files."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import body_fit_geom as F  # noqa: E402
import body_fit_run as RUN  # noqa: E402

DIMS = common.ROOT / "tools" / "blender" / "body_dims"


def cylinder(z0, z1, step, r_x, r_y, n=24, cy=0.0):
    """A ring stack (mm): vertices, edges (around and up), the top ring's indices."""
    verts, edges = [], []
    zs = [z0 + step * i for i in range(int(round((z1 - z0) / step)) + 1)]
    for k, z in enumerate(zs):
        for j in range(n):
            a = 2 * math.pi * j / n
            verts.append((r_x * math.sin(a), cy - r_y * math.cos(a), z))
            edges.append((k * n + j, k * n + (j + 1) % n))
            if k:
                edges.append(((k - 1) * n + j, k * n + j))
    return verts, edges, list(range((len(zs) - 1) * n, len(zs) * n))


def table(zs, half, front, back):
    return {"height_map": {"concept_z": [0.0, 745.0, 1390.0], "body_z": [0.0, 745.0, 1390.0]},
            "neck_ring": {"z": 1390.0}, "keys": {"armpit_z": 1300.0},
            "trunk": {"z": zs, "front_w": [2 * half] * len(zs), "front_y": [front] * len(zs),
                      "back_y": [back] * len(zs)},
            "legs": {"z": [100.0], "width": [100.0], "front_y": [-50.0], "back_y": [50.0]},
            "arms": {"s": [200.0, 300.0], "width": [80.0, 80.0], "s_armpit": 180.0, "s_wrist": 480.0},
            "fit": {"keep_front": []}}


BONES = {"LeftHand": {"head": [600.0, 0.0, 1300.0]}, "LeftFoot": {"head": [100.0, 0.0, 100.0]}}


class Helpers(unittest.TestCase):
    def test_ramp_interp_smooth(self):
        self.assertEqual((F.ramp(-1), F.ramp(0.5), F.ramp(2)), (0.0, 0.5, 1.0))
        self.assertAlmostEqual(F.interp([0, 10], [0, 100], 2.5), 25.0)
        self.assertEqual(F.interp([0, 10], [0, 100], -5), 0)
        self.assertEqual(F.smooth([0, 1, 2], [5, 5, 5], 3.0), [5.0, 5.0, 5.0])
        self.assertEqual(F.smooth([0, 1, 2], [5, None, 5], 3.0)[1], 5.0)

    def test_map_y_moves_front_and_back_apart(self):
        self.assertAlmostEqual(F.map_y(-100, 0, -100, 100, -120, 90), -120)
        self.assertAlmostEqual(F.map_y(100, 0, -100, 100, -120, 90), 90)
        self.assertAlmostEqual(F.map_y(-50, 0, -100, 100, -120, 90), -60)

    def test_keep_front_holds_inside_and_lets_go_at_the_bounds(self):
        zones = [[640.0, 1000.0]]
        self.assertEqual(F.keep_front(800, zones), 1.0)
        self.assertEqual(F.keep_front(640, zones), 0.0)
        self.assertEqual(F.keep_front(600, zones), 0.0)
        self.assertEqual(F.keep_front(1000, zones), 0.0)
        self.assertTrue(0 < F.keep_front(655, zones) < 1)
        self.assertEqual(F.keep_front(640, zones, 0.0), 1.0)

    def test_sections_cut_a_cylinder(self):
        v, e, _ = cylinder(0, 100, 10, 50, 40)
        pts = F.sections(v, e, lambda a, b: True, 2, [55.0])[0]
        self.assertEqual(len(pts), 24)
        self.assertAlmostEqual(max(abs(p[0]) for p in pts), 50.0, places=6)
        self.assertAlmostEqual(min(p[1] for p in pts), -40.0, places=6)

    def test_shares(self):
        self.assertEqual(F.arm_share({"LeftUpperArm": 0.6, "LeftIndexProximal": 0.6}), 1.0)
        self.assertEqual(F.arm_share({"LeftShoulder": 1.0}), 0.0)
        self.assertEqual(F.foot_share({"RightToes": 0.3, "RightFoot": 0.2}), 0.5)

    def test_chest_round_share(self):
        self.assertAlmostEqual(F.round_x(70, 70, 42, 0.45), 1.0)
        self.assertAlmostEqual(F.round_x(0, 70, 42, 0.45), 0.45 + 0.55 * math.exp(-0.5 * (70 / 42) ** 2))
        self.assertLess(F.round_x(200, 70, 42, 0.45), 0.01)
        ch = {"under_z": 1000.0, "top_z": 1100.0, "under_f": -60.0, "top_f": -60.0,
              "front": lambda z: -80.0 if 1020 < z < 1080 else -60.0}
        self.assertAlmostEqual(F.chest_excess(1050, ch), 20.0)
        self.assertEqual(F.chest_excess(990, ch), 0.0)


class Fit(unittest.TestCase):
    def test_a_trunk_fits_its_table_and_keeps_the_ring(self):
        v, e, ring = cylinder(760, 1390, 10, 100, 100)
        w = [{"Spine": 1.0}] * len(v)
        zs = [760.0 + 10 * i for i in range(63)]
        t = table(zs, 120.0, -110.0, 105.0)
        au = F.armpit_u(v, e, w, 1295.0)
        before = F.errors(v, w, e, t, BONES, au)["summary"]
        self.assertAlmostEqual(before["trunk.w"]["worst"], -40.0, delta=1.0)
        out = v
        for _ in range(2):
            out, rep = F.fit(out, w, e, t, BONES, au, ring)
        err = F.errors(out, w, e, t, BONES, au)
        s = err["summary"]
        for key in ("trunk.w", "trunk.front", "trunk.back"):
            self.assertEqual(s[key]["over"], [], key)
        for r in err["rows"]["trunk"]:  # exact below the armpit; the neck's widths come back over the ring's 75 mm
            if r["z"] < 1300:
                self.assertLess(max(abs(r["w"]), abs(r["front"]), abs(r["back"])), 1.0, r)
        for i in ring:
            self.assertEqual(out[i], v[i])
        rows = {r["z"]: r for r in err["rows"]["trunk"]}
        self.assertEqual(rows[1380.0]["rule"], "neck taper")
        self.assertEqual(rows[1310.0]["rule"], "shoulders (T arms)")
        self.assertGreater(max(math.dist(p, q) for p, q in zip(v, out)), 15.0)
        self.assertLess(rep["max_move_mm"], 10.0)  # the second pass only corrects the first

    def test_a_kept_front_stays_the_bodys(self):
        v, e, ring = cylinder(760, 1390, 10, 100, 100)
        w = [{"Spine": 1.0}] * len(v)
        zs = [760.0 + 10 * i for i in range(63)]
        t = table(zs, 100.0, -130.0, 100.0)
        t["fit"]["keep_front"] = [[850.0, 1100.0]]
        au = F.armpit_u(v, e, w, 1295.0)
        out = v
        for _ in range(2):
            out, _ = F.fit(out, w, e, t, BONES, au, ring)
        fronts = {round(p[2]): p[1] for p in out if abs(p[0]) < 1e-6 and p[1] < 0}
        self.assertAlmostEqual(fronts[980], -100.0, delta=0.5)
        self.assertAlmostEqual(fronts[800], -130.0, delta=1.0)
        rows = {r["z"]: r for r in F.errors(out, w, e, t, BONES, au)["rows"]["trunk"]}
        self.assertIsNone(rows[980.0]["front"])
        self.assertEqual(rows[980.0]["rule"], "front kept")

    def test_the_summary_names_stations_over_target(self):
        rows = {"trunk": [{"z": 1.0, "w": 6.0, "front": 1.0, "back": 0.0, "rule": ""},
                          {"z": 2.0, "w": -2.0, "front": None, "back": 9.0, "rule": "front kept"},
                          {"z": 3.0, "w": 50.0, "front": 0.0, "back": 0.0, "rule": "", "w_skip": True}],
                "legs": [{"z": 5.0, "w": 3.5, "front": 0.0, "back": 0.0, "rule": ""}], "arms": []}
        s = F.summarise(rows)
        self.assertEqual((s["trunk.w"]["worst"], s["trunk.w"]["over"]), (6.0, [1.0]))
        self.assertEqual(s["trunk.back"]["n"], 2)  # a rule skips the row, w_skip only its width
        self.assertEqual(s["legs.w"]["over"], [5.0])


def skeleton():
    """A small A skeleton (metres) with every kind of bone B1's map knows."""
    b = {"Hips": ((0, 0.036, 0.85), (0, 0.036, 0.95), None), "Spine": ((0, 0.03, 0.95), (0, 0.0, 1.03), "Hips"),
         "Chest": ((0, 0.0, 1.03), (0, -0.007, 1.149), "Spine"),
         "UpperChest": ((0, -0.007, 1.149), (0, 0.0414, 1.3392), "Chest"),
         "Neck": ((0, 0.0414, 1.3392), (0, 0.0174, 1.4383), "UpperChest"),
         "Head": ((0, 0.0174, 1.4383), (0, 0.0174, 1.60), "Neck")}
    for sd, sg in (("Left", 1), ("Right", -1)):
        b.update({f"{sd}Shoulder": ((sg * 0.031, -0.033, 1.316), (sg * 0.152, 0.065, 1.2765), "UpperChest"),
                  f"{sd}UpperArm": ((sg * 0.152, 0.065, 1.2765), (sg * 0.413, 0.07, 1.2765), f"{sd}Shoulder"),
                  f"{sd}LowerArm": ((sg * 0.413, 0.07, 1.2765), (sg * 0.644, 0.065, 1.2765), f"{sd}UpperArm"),
                  f"{sd}Hand": ((sg * 0.644, 0.065, 1.2765), (sg * 0.72, 0.06, 1.27), f"{sd}LowerArm"),
                  f"{sd}UpperLeg": ((sg * 0.1143, 0.036, 0.8409), (sg * 0.1143, 0.036, 0.518), "Hips"),
                  f"{sd}LowerLeg": ((sg * 0.1143, 0.036, 0.518), (sg * 0.1143, 0.0913, 0.115), f"{sd}UpperLeg"),
                  f"{sd}Foot": ((sg * 0.1143, 0.0913, 0.115), (sg * 0.1143, -0.053, 0.026), f"{sd}LowerLeg"),
                  f"{sd}Toes": ((sg * 0.1143, -0.053, 0.026), (sg * 0.1143, -0.18, 0.026), f"{sd}Foot")})
    return {n: {"head": list(h), "tail": list(t), "parent": p} for n, (h, t, p) in b.items()}


class BRest(unittest.TestCase):
    def test_b_rest_from_the_tables_and_fit_toml(self):
        s = tomllib.loads((DIMS / "fit.toml").read_text(encoding="utf-8"))["B"]
        ta, tb = F.load_table(DIMS / "A.toml"), F.load_table(DIMS / "B.toml")
        a = skeleton()
        rest, rep = RUN.b_rest(a, ta, tb, s)
        ring = tb["neck_ring"]["z"] / 1000
        self.assertAlmostEqual(rep["height_scale"], tb["neck_ring"]["z"] / ta["neck_ring"]["z"], places=6)
        self.assertAlmostEqual(rest["LeftUpperArm"]["head"][0], s["shoulder_joint_x"] / 1000, places=6)
        self.assertAlmostEqual(rest["RightUpperArm"]["head"][0], -s["shoulder_joint_x"] / 1000, places=6)
        self.assertAlmostEqual(rest["LeftUpperLeg"]["head"][0], s["hip_joint_x"] / 1000, places=6)
        self.assertAlmostEqual(rest["Neck"]["head"][2], ring - tb["neck_ring"]["neck_bone_below"] / 1000, places=6)
        self.assertAlmostEqual(rest["Head"]["head"][2], ring + tb["neck_ring"]["head_bone_above"] / 1000, places=6)
        self.assertEqual(rest["UpperChest"]["tail"], rest["Neck"]["head"])
        self.assertEqual(rest["Neck"]["tail"], rest["Head"]["head"])
        for sd in ("Left", "Right"):  # the feet: x and y about the ankle by fit.toml's scales, z by the height
            ank, ank_a = rest[f"{sd}Foot"]["head"], a[f"{sd}Foot"]["head"]
            toe, toe_a = rest[f"{sd}Toes"]["head"], a[f"{sd}Toes"]["head"]
            self.assertAlmostEqual((toe[1] - ank[1]) / (toe_a[1] - ank_a[1]), s["foot_scale_y"], places=6)
            self.assertAlmostEqual((toe[2] - ank[2]) / (toe_a[2] - ank_a[2]), rep["height_scale"], places=6)
            h, h_a = rest[f"{sd}Hand"], a[f"{sd}Hand"]
            self.assertAlmostEqual(math.dist(h["head"], h["tail"]) / math.dist(h_a["head"], h_a["tail"]),
                                   s["hand_scale"], places=6)

    def test_fit_toml_holds_both_bodies(self):
        s = tomllib.loads((DIMS / "fit.toml").read_text(encoding="utf-8"))
        self.assertEqual(s["A"]["keep_front"], [[640.0, 1000.0]])
        for k in ("shoulder_joint_x", "hip_joint_x", "hand_scale", "foot_scale_x", "foot_scale_y"):
            self.assertIn(k, s["B"])
        self.assertNotIn("height_scale", s["B"])


if __name__ == "__main__":
    unittest.main()
