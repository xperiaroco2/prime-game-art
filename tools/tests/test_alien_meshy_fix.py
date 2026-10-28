"""M1b (art #196): the plain maths of tools/blender/alien_meshy_fix_geom.py (the fingers' labels, lines, chain
weights, creases and rolls; the joints' rings; the arms' profile), her M1b target file, and M1's file unchanged by
the new optional keys. No Blender."""
import math
import sys
import unittest
from pathlib import Path

BL = Path(__file__).resolve().parents[1] / "blender"
sys.path.insert(0, str(BL))
import alien_meshy_body_geom as M  # noqa: E402
import alien_meshy_fix_geom as F  # noqa: E402


def comb(n_fingers=2, length=10, palm=4):
    """A toy hand along x: a palm strip (x 0..palm-1, one column of vertices per finger) and fingers past it."""
    x, adj, vid = {}, {}, {}
    k = 0
    for f in range(n_fingers):
        for i in range(palm + length):
            vid[f, i] = k
            x[k] = float(i)
            k += 1
    for (f, i), v in vid.items():
        for g, j in ((f, i + 1), (f + 1, i)):
            if (g, j) in vid and (j < palm or g == f):
                adj.setdefault(v, []).append(vid[g, j])
                adj.setdefault(vid[g, j], []).append(v)
    return x, adj, vid


class Fingers(unittest.TestCase):
    def test_label_each_free_finger(self):
        x, adj, vid = comb()
        lab, stop = F.label_fingers(x, adj, step=0.5, min_part=2)
        self.assertEqual(len(stop), 2)
        tips = {lab[vid[0, 13]], lab[vid[1, 13]]}
        self.assertEqual(len(tips), 2)  # one tip each
        for f in range(2):
            for i in range(4, 14):
                self.assertEqual(lab[vid[f, i]], lab[vid[f, 13]])  # the whole free finger, its own label
            for i in range(0, 3):
                self.assertNotIn(vid[f, i], lab)  # the palm: no finger's
        self.assertTrue(all(2.5 <= v <= 3.5 for v in stop.values()))  # stopped at the web

    def test_fit_line(self):
        pts = [(0.01 * i, 0.002 * i + 0.1, 1.2) for i in range(10)]
        c, d = F.fit_line(pts)
        n = math.sqrt(1 + 0.04)
        for a, b in zip(d, (1 / n, 0.2 / n, 0.0)):
            self.assertAlmostEqual(a, b, places=6)
        self.assertAlmostEqual(F.off_line((0.05, 0.11, 1.2), c, d), 0.0, places=9)
        self.assertGreater(F.along(pts[-1], c, d), F.along(pts[0], c, d))

    def test_chain_weights(self):
        js, h = [0.0, 0.03, 0.055], [0.008, 0.004, 0.0035]
        for s in (-0.02, -0.004, 0.0, 0.02, 0.03, 0.05, 0.07):
            w = F.chain_weights(s, js, h)
            self.assertEqual(len(w), 4)
            self.assertAlmostEqual(sum(w), 1.0)
            self.assertTrue(sum(v > 1e-9 for v in w) <= 2)  # never more than two bones at once
        self.assertEqual(F.chain_weights(-0.02, js, h)[0], 1.0)  # the palm
        self.assertEqual(F.chain_weights(0.015, js, h)[1], 1.0)  # mid proximal
        self.assertAlmostEqual(F.chain_weights(0.03, js, h)[2], 0.5)  # on the joint: half each
        self.assertEqual(F.chain_weights(0.07, js, h)[3], 1.0)  # the tip

    def test_ownership_smooth(self):
        a, b = F.ownership(0.01, 0.003), F.ownership(0.03, 0.003)
        self.assertGreater(a, b)
        self.assertLess(a / b, 100.0)  # no step: a Gaussian's ratio here would be e^8

    def test_pick_crease(self):
        samples = [(0.002 * i, 0.016 - (0.004 if i == 7 else 0.0)) for i in range(20)]
        self.assertAlmostEqual(F.pick_crease(samples, 0.015, 0.005), 0.014)
        flat = [(0.002 * i, 0.016 - 0.0001 * i) for i in range(20)]  # thinning to the tip: no crease
        self.assertEqual(F.pick_crease(flat, 0.015, 0.005), 0.015)

    def test_keep_roll_z(self):
        z = F.keep_roll_z([0.0, 0.0, -1.0], [1.0, 0.0, -0.2])
        self.assertAlmostEqual(sum(a * b for a, b in zip(z, [1.0, 0.0, -0.2])), 0.0)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in z)), 1.0)
        self.assertLess(z[2], -0.9)  # still pointing down
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in F.keep_roll_z([1.0, 0, 0], [1.0, 0, 0]))), 1.0)

    def test_names(self):
        self.assertEqual(F.chain_names("Left", "Thumb"), ["LeftThumbMetacarpal", "LeftThumbProximal", "LeftThumbDistal"])
        self.assertEqual(F.chain_names("Right", "Ring")[1], "RightRingIntermediate")


class Rings(unittest.TestCase):
    def test_share(self):
        self.assertEqual(F.ring_share(-0.1, 0.05), 0.0)
        self.assertEqual(F.ring_share(0.1, 0.05), 1.0)
        self.assertAlmostEqual(F.ring_share(0.01, 0.05, 0.01), 0.5)

    def test_blend(self):
        old = {"LeftUpperLeg": 0.7, "LeftLowerLeg": 0.3}
        fam = {"LeftLowerLeg", "LeftFoot"}
        w = F.ring_blend(old, fam, "LeftUpperLeg", "LeftLowerLeg", 0.5, 1.0)
        self.assertAlmostEqual(w["LeftLowerLeg"], 0.5)
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertEqual(F.ring_blend(old, fam, "LeftUpperLeg", "LeftLowerLeg", 0.9, 0.0), old)  # blend 0: the old
        # a side holding none takes the named bone; other groups keep their proportions
        w = F.ring_blend({"Hips": 0.5, "Spine": 0.5}, {"LeftUpperLeg"}, "Hips", "LeftUpperLeg", 0.4, 1.0)
        self.assertAlmostEqual(w["LeftUpperLeg"], 0.4)
        self.assertAlmostEqual(w["Hips"], 0.3)

    def test_profile(self):
        st = [[0.17, 1.0], [0.3, 1.4], [0.69, 1.0]]
        self.assertEqual(F.profile(st, 0.1), 1.0)
        self.assertAlmostEqual(F.profile(st, 0.235), 1.2)
        self.assertEqual(F.profile(st, 0.8), 1.0)


class Targets(unittest.TestCase):
    def test_m1b_file(self):
        t = M.load(M.TARGETS / "axolotl_m1b.toml")
        self.assertEqual(t["name"], "axolotl_m1b")
        self.assertEqual(set(t) & M.KEYS_M1B, M.KEYS_M1B)
        prof = t["arm_thicken"]["profile"]
        self.assertEqual([p[0] for p in prof], sorted(p[0] for p in prof))
        self.assertEqual(prof[0][1], 1.0)  # the torso keeps its size
        self.assertEqual(prof[-1][1], 1.0)  # the hands keep theirs
        self.assertLess(max(p[1] for p in prof), 1.5)
        self.assertEqual({b["child"] for b in t["bends"]}, {"UpperArm", "LowerArm", "UpperLeg", "LowerLeg"})
        m1 = M.load(M.TARGETS / "axolotl_m1.toml")
        for k in M.KEYS:  # M1's numbers, the fixes only on top
            if k != "name":
                self.assertEqual(t[k], m1[k], k)

    def test_m1_has_no_fix(self):
        self.assertFalse(set(M.load(M.TARGETS / "axolotl_m1.toml")) & M.KEYS_M1B)
        src = (BL / "alien_meshy_body.py").read_text(encoding="utf-8")
        self.assertIn("if not any(k in T for k in M.KEYS_M1B | M.KEYS_M1C | M.KEYS_M2B):", src)
        self.assertIn('ap.add_argument("--from-body", default=""', src)


class M1c(unittest.TestCase):
    """M1c: the thumb's soft base, the fingers' base band, the notch's pick and her M1c file."""

    def test_thumb_share(self):
        f = [0.006, 0.030]
        self.assertEqual(F.thumb_share(0.0, f), 1.0)
        self.assertEqual(F.thumb_share(0.006, f), 1.0)
        self.assertEqual(F.thumb_share(0.030, f), 0.0)
        xs = [F.thumb_share(0.006 + k * 0.001, f) for k in range(25)]
        self.assertEqual(xs, sorted(xs, reverse=True))  # falls off monotonically
        steps = [a - b for a, b in zip(xs, xs[1:])]
        self.assertLess(max(steps), 0.07)  # no step: at most 7 % per mm

    def test_split_palm(self):
        rest, h = F.split_palm([2.0, 1.0], 1.0, 0.25)
        self.assertAlmostEqual(sum(rest) + h + 0.25, 1.0)
        self.assertAlmostEqual(rest[0], 0.75 * 0.5)
        self.assertAlmostEqual(h, 0.75 * 0.25)
        rest, h = F.split_palm([5.0], 1.0, 1.0)  # on the thumb's line: all the thumb's
        self.assertEqual((rest, h), ([0.0], 0.0))

    def test_base_band(self):
        self.assertTrue(F.in_base_band(0.010, 0.008, 0.006))
        self.assertFalse(F.in_base_band(0.015, 0.008, 0.006))

    def test_notch_pick(self):
        self.assertEqual(F.notch_pick([(0.1, (0, 0, 1)), (0.4, (1, 0, 0)), (-0.2, (0, 1, 0))]), (1, 0, 0))

    def test_m1c_file(self):
        t = M.load(M.TARGETS / "axolotl_m1c.toml")
        b = M.load(M.TARGETS / "axolotl_m1b.toml")
        self.assertEqual(t["name"], "axolotl_m1c")
        self.assertIn("notch", t)
        self.assertEqual(set(t["fingers"]) - set(b["fingers"]), M.FINGER_KEYS_M1C)
        lo, hi = t["fingers"]["thumb_falloff"]
        self.assertLess(lo, hi)
        x0, x1, y0, y1, z0, z1 = t["notch"]["box"]
        self.assertTrue(x0 < x1 and y0 < y1 and z0 < 0.45 < z1)  # the notch at about z 0.45 (M1b's close-ups)
        for k in set(b) - {"name", "fingers"}:  # M1b's numbers, M1c's only on top
            self.assertEqual(t[k], b[k], k)
        for k, v in b["fingers"].items():
            if k not in ("thumb_half", "sigma"):
                self.assertEqual(t["fingers"][k], v, k)

    def test_m1_m1b_have_no_m1c(self):
        for n in ("axolotl_m1.toml", "axolotl_m1b.toml"):
            t = M.load(M.TARGETS / n)
            self.assertFalse(set(t) & M.KEYS_M1C, n)
            self.assertFalse(set(t.get("fingers", {})) & M.FINGER_KEYS_M1C, n)

    def test_m2_file(self):
        """M2 (the chameleon): his target file loads; his skeleton is H4b's, his ring H4b's, the fingers and bends
        the axolotl's final M1c numbers; the wrap and arm maps increase; no chest push."""
        t = M.load(M.TARGETS / "chameleon_m2.toml")
        c = M.load(M.TARGETS / "axolotl_m1c.toml")
        self.assertEqual(t["name"], "chameleon_m2")
        self.assertIn("chameleon_t/", t["meshy"])
        self.assertTrue(t["rig_body"].endswith("h4b/body2/alien_body.blend"))
        self.assertIn("shift_y", t)
        self.assertAlmostEqual(t["ring_z"], 1.443, places=3)
        self.assertEqual(t["fingers"], c["fingers"])
        self.assertEqual(t["bends"], c["bends"])
        self.assertEqual(t["bust"]["push"], 0.0)
        self.assertEqual(t["smooth_after"]["spheres"], [])
        for pairs in (t["wrap_z"], t["arm_x"]):
            for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
                self.assertTrue(a0 < a1 and b0 < b1)
        self.assertLess(t["neck_scale_from_z"], t["ring_z"])
        self.assertLess(t["body_tris"], 31800)  # his head with its bridge is about 28,100 of the 60,000

    def test_axolotl_files_have_no_m2(self):
        for n in ("axolotl_m1.toml", "axolotl_m1b.toml", "axolotl_m1c.toml"):
            self.assertFalse(set(M.load(M.TARGETS / n)) & M.KEYS_M2, n)
        src = (BL / "alien_meshy_body.py").read_text(encoding="utf-8")
        self.assertIn('if "shift_y" in T:', src)

    def test_finger_radial(self):
        """M2b: 1 at the web, 1 - slim past the ramp, the tip's last tip_len a further 1 - tip."""
        sh = {"slim": 0.15, "ramp": 0.012, "tip": 0.12, "tip_len": 0.016}
        self.assertAlmostEqual(F.finger_radial(0.0, 0.0, 0.08, sh), 1.0)
        self.assertAlmostEqual(F.finger_radial(0.04, 0.0, 0.08, sh), 0.85)
        self.assertAlmostEqual(F.finger_radial(0.079, 0.0, 0.08, sh), 0.85 * 0.88)
        ks = [F.finger_radial(s / 1000, 0.0, 0.08, sh) for s in range(81)]
        self.assertTrue(all(a >= b - 1e-12 for a, b in zip(ks, ks[1:])))  # never wider toward the tip

    def test_finger_point(self):
        """M2b: the offset from the slice's centre scaled; the centre moved toward the web by the length factor."""
        q = F.finger_point([0.05, 0.01, 0.0], [0.05, 0.0, 0.0], [0.0, 0.0, 0.0], 0.8, 0.85)
        for a_, b_ in zip(q, [0.0425, 0.008, 0.0]):
            self.assertAlmostEqual(a_, b_)
        self.assertEqual(F.finger_point([1.0, 2.0, 3.0], [1.0, 2.0, 2.5], [0.0, 0.0, 0.0], 1.0, 1.0), [1.0, 2.0, 3.0])

    def test_seat_y(self):
        """M2b: in front of the line unchanged; far behind it the depth scaled; continuous at the line."""
        self.assertEqual(F.seat_y(0.05, 0.08, 1.0, 0.7, 0.01), 0.05)
        self.assertAlmostEqual(F.seat_y(0.14, 0.08, 1.0, 0.7, 0.01), 0.08 + 0.06 * 0.7)
        self.assertAlmostEqual(F.seat_y(0.08 + 1e-6, 0.08, 1.0, 0.7, 0.01), 0.08 + 1e-6, places=9)
        self.assertAlmostEqual(F.seat_y(0.14, 0.08, 0.0, 0.7, 0.01), 0.14)

    def test_m2b_file(self):
        """M2b: M2's file plus the fixes; each fix key at the level the build reads it (M2 lost arm_thicken inside
        the last [[bends]])."""
        t = M.load(M.TARGETS / "chameleon_m2b.toml")
        m2 = M.load(M.TARGETS / "chameleon_m2.toml")
        self.assertEqual(t["name"], "chameleon_m2b")
        self.assertTrue({"seat", "arm_thicken", "smooth_rest"} <= set(t))
        self.assertEqual(set(t) - set(m2), {"seat", "arm_thicken", "smooth_rest"})
        for b in t["bends"]:
            self.assertFalse(set(b) & (M.KEYS | M.KEYS_M1B | M.KEYS_M2B))
        self.assertEqual(set(t["fingers"]) - set(m2["fingers"]), M.FINGER_KEYS_M2B)
        self.assertEqual(t["fingers"]["shape"]["thumb_shorten"], 0.15)
        self.assertTrue(set(t["smooth_rest"]) - {"spheres"} <= M.SMOOTH_KEYS_M2B)
        self.assertNotIn("mu", t["smooth"])  # a first build's Taubin there pinched a facet
        self.assertEqual(t["bends"], m2["bends"])
        for k in ("meshy", "rig_body", "shift_y", "wrap_z", "arm_x", "ring_z", "ring_half_x", "body_tris"):
            self.assertEqual(t[k], m2[k], k)
        for b in t["smooth_rest"]["boxes"]:
            self.assertIn(len(b), (7, 8))
            self.assertTrue(b[0] < b[1] and b[2] < b[3] and b[4] < b[5])
            self.assertLessEqual(b[5], t["ring_z"] + 0.01)
        self.assertLess(t["seat"]["depth"], 1.0)

    def test_older_files_have_no_m2b(self):
        for n in ("axolotl_m1.toml", "axolotl_m1b.toml", "axolotl_m1c.toml", "chameleon_m2.toml"):
            t = M.load(M.TARGETS / n)
            self.assertFalse(set(t) & M.KEYS_M2B, n)
            self.assertFalse(set(t.get("fingers", {})) & M.FINGER_KEYS_M2B, n)
            self.assertFalse(set(t.get("smooth_rest", {})) & M.SMOOTH_KEYS_M2B, n)
            self.assertNotIn("mu", t["smooth"], n)
        src = (BL / "alien_meshy_body.py").read_text(encoding="utf-8")
        self.assertIn('if "boxes" in cfg:', src)  # the ring held only for M2b's boxes
        self.assertIn('if "shape" in cfg:', src)

    def test_clip_view_outside(self):
        src = (BL / "alien_body_clip_bends.py").read_text(encoding="utf-8")
        self.assertIn("v, turned = clear_view(sc, c, v,", src)

    def test_clip_filter(self):
        src = (BL / "alien_body_clip_bends.py").read_text(encoding="utf-8")
        self.assertIn('return "__" not in n and not n.startswith(("TM_", "MC_"))', src)


if __name__ == "__main__":
    unittest.main()
