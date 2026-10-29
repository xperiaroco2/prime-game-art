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

    def test_the_chest_line_leaves_the_crease_tangent(self):
        ch = {"under_z": 1000.0, "top_z": 1100.0, "under_f": -100.0, "top_f": -80.0}
        self.assertAlmostEqual(F.chest_line(1000, ch), -100.0)
        self.assertAlmostEqual(F.chest_line(1100, ch), -80.0)
        self.assertLess(F.chest_line(1001, ch) - F.chest_line(1000, ch), 0.01)  # no kink at the crease
        top = (F.chest_line(1100, ch) - F.chest_line(1099, ch))
        self.assertAlmostEqual(top, 0.2, delta=0.01)  # the straight line's slope at the upper chest

    def test_the_trim_moves_the_rounds_by_the_front_error_only(self):
        ch = {"under_z": 1000.0, "top_z": 1100.0, "front": lambda z: -100.0, "centre_x": 70.0, "sigma_x": 40.0,
              "floor": 0.4}
        rows = [{"z": float(z), "front": 4.0} for z in range(1005, 1100, 5)]
        body = {"Chest": 1.0}
        verts = [(70.0, -100.0, 1050.0), (70.0, -100.0, 950.0), (70.0, 50.0, 1050.0), (300.0, -100.0, 1050.0)]
        out = F.chest_trim(verts, [body, body, body, {"LeftUpperArm": 1.0}], rows, ch)
        self.assertAlmostEqual(out[0][1], -104.0, delta=0.3)  # the apex 4 mm forward
        self.assertEqual(out[1:], verts[1:])  # under the crease, the back, the arm


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
        rest, rep, vb = RUN.b_rest(a, ta, tb, s)
        ls = RUN.limb_scales(ta, tb)
        self.assertEqual(vb, [])
        ring = tb["neck_ring"]["z"] / 1000
        self.assertAlmostEqual(rep["height_scale"], tb["neck_ring"]["z"] / ta["neck_ring"]["z"], places=6)
        self.assertAlmostEqual(rest["LeftUpperArm"]["head"][0], s["shoulder_joint_x"] / 1000, places=6)
        self.assertAlmostEqual(rest["RightUpperArm"]["head"][0], -s["shoulder_joint_x"] / 1000, places=6)
        self.assertAlmostEqual(rest["LeftUpperLeg"]["head"][0], s["hip_joint_x"] / 1000, places=6)
        self.assertAlmostEqual(rest["Neck"]["head"][2], ring - tb["neck_ring"]["neck_bone_below"] / 1000, places=6)
        self.assertAlmostEqual(rest["Head"]["head"][2], ring + tb["neck_ring"]["head_bone_above"] / 1000, places=6)
        self.assertEqual(rest["UpperChest"]["tail"], rest["Neck"]["head"])
        self.assertEqual(rest["Neck"]["tail"], rest["Head"]["head"])
        for sd in ("Left", "Right"):  # the feet: x and y about the ankle by the tables' ratios, z by the height
            ank, ank_a = rest[f"{sd}Foot"]["head"], a[f"{sd}Foot"]["head"]
            toe, toe_a = rest[f"{sd}Toes"]["head"], a[f"{sd}Toes"]["head"]
            self.assertAlmostEqual((toe[1] - ank[1]) / (toe_a[1] - ank_a[1]), ls["foot_length"], places=6)
            self.assertAlmostEqual((toe[2] - ank[2]) / (toe_a[2] - ank_a[2]), rep["height_scale"], places=6)
            h, h_a = rest[f"{sd}Hand"], a[f"{sd}Hand"]
            self.assertAlmostEqual(math.dist(h["head"], h["tail"]) / math.dist(h_a["head"], h_a["tail"]),
                                   ls["hand_length"], places=6)

    def test_fit_toml_holds_both_bodies(self):
        s = tomllib.loads((DIMS / "fit.toml").read_text(encoding="utf-8"))
        self.assertEqual(s["A"]["keep_front"], [[640.0, 1000.0]])
        for k in ("shoulder_joint_x", "hip_joint_x", "neck_base"):
            self.assertIn(k, s["B"])
        for k in ("height_scale", "hand_scale", "foot_scale_x", "foot_scale_y"):  # from the tables now
            self.assertNotIn(k, s["B"])
        self.assertEqual(set(s["B"]["neck_base"]), {"length", "collar", "power", "ease", "max_ratio"})

    def test_limb_scales_from_the_tables(self):
        ls = RUN.limb_scales(F.load_table(DIMS / "A.toml"), F.load_table(DIMS / "B.toml"))
        want = {"hand_length": 0.960, "hand_width": 0.878, "foot_length": 0.850, "foot_width": 0.911}
        for k, v in want.items():
            self.assertAlmostEqual(ls[k], v, delta=0.0015)

    def test_hands_scale_along_and_across_the_hand_bone(self):
        rest = {n: dict(r) for n, r in skeleton().items()}
        h = rest["LeftHand"]["head"]
        p = (h[0] + 0.1, h[1] + 0.02, h[2] - 0.01)  # 0.1 m past the wrist along x, off the axis a little
        u = [rest["LeftHand"]["tail"][i] - rest["LeftHand"]["head"][i] for i in range(3)]
        n = math.sqrt(sum(c * c for c in u))
        out = RUN.hands([p, (0.0, 0.0, 1.0)], [{"LeftMiddle1": 1.0}, {"Spine": 1.0}], rest, 0.9, 0.8)
        d = [out[0][i] - h[i] for i in range(3)]
        d0 = [p[i] - h[i] for i in range(3)]
        along, along0 = (sum(d[i] * u[i] for i in range(3)) / n, sum(d0[i] * u[i] for i in range(3)) / n)
        self.assertAlmostEqual(along / along0, 0.9, places=6)
        across = math.dist(d, [along * c / n for c in u])
        across0 = math.dist(d0, [along0 * c / n for c in u])
        self.assertAlmostEqual(across / across0, 0.8, places=6)
        self.assertEqual(out[1], (0.0, 0.0, 1.0))  # off the hand: unmoved
        self.assertAlmostEqual(math.dist(rest["LeftHand"]["head"], rest["LeftHand"]["tail"]) / n, 0.9, places=6)


class Gaps(unittest.TestCase):
    def test_a_dash_band_keeps_the_body_shape_moved_by_its_ends(self):
        zs = [0.0, 10.0, 20.0, 30.0, 40.0]
        own = [0.0, 5.0, 9.0, 5.0, 0.0]
        raw = {0.0: 1.0, 10.0: None, 20.0: None, 30.0: None, 40.0: 3.0}
        out = F.fill_gaps(zs, own, lambda z: {0.0: 1.0, 40.0: 3.0}[z], raw)
        self.assertEqual(out[0], 1.0)
        self.assertEqual(out[-1], 3.0)
        self.assertAlmostEqual(out[2], 9.0 + 2.0)  # own + the ends' error (1 and 3) halfway: never 0, never a line
        self.assertAlmostEqual(out[1], 5.0 + 1.5)

    def test_the_tables_dash_bands_are_not_values(self):
        for name in ("A", "B"):
            t = F.load_table(DIMS / f"{name}.toml")
            z0, z1 = t["body"]["side_back_hidden_z"]
            tg = F.targets(t | {"fit": {}}, F.frame_of(t | {"fit": {}}, {"LeftHand": {"head": [600.0, 0, 0]},
                                                                         "LeftFoot": {"head": [0, 0, 100.0]}}, 200.0))
            hidden = [z for z, v in tg["raw"]["trunk_back"].items() if v is None and z0 <= z <= z1]
            self.assertTrue(hidden, name)


class NeckBase(unittest.TestCase):
    NB = {"length": 60.0, "collar": 6.0, "power": 1.5, "ease": 20.0}

    def test_the_slope_meets_the_ring_with_a_vertical_tangent(self):
        f = lambda z: F.neck_base_half(z, 1324.7, 56.7, 185.0, self.NB)  # noqa: E731
        self.assertEqual(f(1324.7), 56.7)
        self.assertEqual(f(1320.0), 56.7)  # the collar
        self.assertAlmostEqual(f(1324.7 - 60.0), 185.0)
        hs = [f(1324.7 - d) for d in range(0, 61, 5)]
        self.assertEqual(hs, sorted(hs))  # widening downwards, no step
        self.assertLess(f(1324.7 - 12) - f(1324.7 - 7), f(1324.7 - 50) - f(1324.7 - 45))  # steeper lower down

    def test_only_a_body_with_high_shoulders_gets_it(self):
        bones = {"LeftHand": {"head": [600.0, 0, 0]}, "LeftFoot": {"head": [0, 0, 100.0]}}
        for name, on in (("A", False), ("B", True)):
            t = F.load_table(DIMS / f"{name}.toml") | {"fit": {"neck_base": self.NB}}
            self.assertEqual(bool(F.frame_of(t, bones, 200.0)["neck_base"]), on, name)


class ArmFollow(unittest.TestCase):
    """D3d: the arms follow the trunk's centre shift over the armpit (B's chest sits ahead of A's)."""

    def test_the_shift_is_the_middle_of_front_and_back_over_the_span(self):
        c = lambda v: (lambda z: v)  # noqa: E731
        r = {"f0": c(-100.0), "b0": c(100.0), "f1": c(-150.0), "b1": c(70.0)}
        self.assertAlmostEqual(F.arm_dy(r, 1100.0), -40.0)
        lin = {"f0": c(0.0), "b0": c(0.0), "f1": lambda z: -(z - 1000.0), "b1": lambda z: -(z - 1000.0)}
        self.assertAlmostEqual(F.arm_dy(lin, 1000.0, span=80.0), -40.0)  # the mean over the span

    def test_only_b_follows(self):
        s = tomllib.loads((DIMS / "fit.toml").read_text(encoding="utf-8"))
        self.assertTrue(s["B"]["arm_follow"])
        self.assertFalse(s["A"].get("arm_follow", False))

    def test_the_arm_bones_and_the_shoulders_tails_move(self):
        rest = {"LeftShoulder": {"head": (0.02, 0.0, 1.3), "tail": (0.12, 0.0, 1.3), "parent": "UpperChest"},
                "LeftUpperArm": {"head": (0.12, 0.0, 1.3), "tail": (0.2, 0.0, 1.1), "parent": "LeftShoulder"},
                "LeftIndexProximal": {"head": (0.3, 0.0, 0.8), "tail": (0.3, 0.0, 0.77), "parent": "LeftHand"},
                "UpperChest": {"head": (0.0, 0.0, 1.2), "tail": (0.0, 0.0, 1.3), "parent": "Chest"},
                "LeftUpperLeg": {"head": (0.1, 0.0, 0.8), "tail": (0.1, 0.0, 0.45), "parent": "Hips"}}
        out = RUN.arms_moved(rest, -40.0)
        self.assertEqual(out["LeftShoulder"]["head"], rest["LeftShoulder"]["head"])
        self.assertAlmostEqual(out["LeftShoulder"]["tail"][1], -0.04)
        for n in ("LeftUpperArm", "LeftIndexProximal"):
            for k in ("head", "tail"):
                self.assertAlmostEqual(out[n][k][1], rest[n][k][1] - 0.04)
                self.assertEqual(out[n][k][0::2], rest[n][k][0::2])
        self.assertEqual(out["UpperChest"], rest["UpperChest"])
        self.assertEqual(out["LeftUpperLeg"], rest["LeftUpperLeg"])
        self.assertAlmostEqual(out["LeftShoulder"]["tail"][1], out["LeftUpperArm"]["head"][1])


class ShoulderLift(unittest.TestCase):
    """D3d: B's shoulder tops raised in z toward the concept's slope; the ring and everything low never move."""

    TABLE = {"neck_ring": {"z": 1300.0, "half_x": 50.0},
             "trunk": {"z": [1200.0, 1250.0, 1300.0], "front_w": [400.0, 300.0, 100.0]}}

    def test_the_concept_top_inverts_the_half_widths(self):
        self.assertAlmostEqual(F.concept_top(self.TABLE, 150.0, 1190.0, 1300.0), 1250.0)
        self.assertAlmostEqual(F.concept_top(self.TABLE, 100.0, 1190.0, 1300.0), 1275.0)
        self.assertAlmostEqual(F.concept_top(self.TABLE, 300.0, 1190.0, 1300.0), 1190.0)  # wider than any: z_low

    def test_the_ring_and_low_vertices_stay_and_the_top_rises_toward_the_concept(self):
        verts = [(50.0 * math.cos(a), 50.0 * math.sin(a), 1300.0) for a in (0.0, 1.0, 2.0)]
        verts += [(float(x), 0.0, 1220.0) for x in range(60, 200, 10)] + [(100.0, 0.0, 1100.0)]
        sl = {"share": 0.5, "reach": 110.0, "sigma": 8.0, "x_in": 20.0, "x_out": 30.0, "x_end": 200.0, "depth": 60.0}
        out, rep = F.shoulder_lift(verts, [0, 1, 2], self.TABLE, sl)
        self.assertEqual(out[:3], verts[:3])
        self.assertEqual(out[-1], verts[-1])
        top = {round(p[0]): p[2] for p in out[3:-1]}
        self.assertGreater(top[110], 1220.0 + 5.0)  # the concept's top over x 110 is 1270
        self.assertLessEqual(max(top.values()), 1220.0 + 0.5 * (1300.0 - 1220.0))  # at most half way to the ring
        self.assertGreater(rep["max_lift_mm"], 0.0)

    def test_the_smooth_lift_ignores_a_notch_in_the_top(self):
        verts = [(50.0 * math.cos(a), 50.0 * math.sin(a), 1300.0) for a in (0.0, 1.0, 2.0)]
        verts += [(float(x), 0.0, 1220.0 - (12.0 if x == 110 else 0.0)) for x in range(60, 200, 10)]
        sl = {"share": 0.5, "reach": 110.0, "sigma": 25.0, "x_in": 20.0, "x_out": 30.0, "x_end": 200.0,
              "depth": 60.0, "smooth_env": True}
        def notch(s):
            out, _ = F.shoulder_lift(verts, [0, 1, 2], self.TABLE, s)
            lift = {round(p[0]): q[2] - p[2] for p, q in zip(verts[3:], out[3:])}
            return lift[110] - (lift[100] + lift[120]) / 2
        self.assertLess(notch(sl), 4.0)  # the lift at the notch stays near its neighbours'

    def test_taubin_moves_only_the_shared_vertices_and_flattens_a_spike(self):
        verts = [(float(i), 0.0, 5.0 if i == 2 else 0.0) for i in range(5)]
        edges = [(i, i + 1) for i in range(4)]
        out = F.taubin(verts, edges, {1: 1.0, 2: 1.0, 3: 1.0}, 4)
        self.assertEqual(out[0], verts[0])
        self.assertEqual(out[4], verts[4])
        self.assertLess(out[2][2], 3.0)


if __name__ == "__main__":
    unittest.main()
