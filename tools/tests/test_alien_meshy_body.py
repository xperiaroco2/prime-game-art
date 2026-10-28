"""The Meshy body route (art #196, pilot M1): the plain maths of tools/blender/alien_meshy_body_geom.py, her target
file, the gills' decimation ratio and the new build flags being off by default. No Blender."""
import re
import sys
import unittest
from pathlib import Path

BL = Path(__file__).resolve().parents[1] / "blender"
sys.path.insert(0, str(BL))
import alien_char_geom as G  # noqa: E402
import alien_meshy_body_geom as M  # noqa: E402

AX = M.TARGETS / "axolotl_m1.toml"


class Maths(unittest.TestCase):
    def test_interp_extrapolates_straight(self):
        self.assertAlmostEqual(M.interp([0, 1], [0, 2], 0.5), 1.0)
        self.assertAlmostEqual(M.interp([0, 1, 2], [0, 2, 3], 3.0), 4.0)  # the last segment's slope
        self.assertAlmostEqual(M.interp([0, 1, 2], [0, 2, 3], -1.0), -2.0)
        with self.assertRaises(ValueError):
            M.interp([0], [0], 0.0)

    def test_z_maps_invert(self):
        wz = M.load(AX)["wrap_z"]
        for z in (0.0, 0.1, 0.5, 0.74, 1.2, 1.39, 1.5):
            self.assertAlmostEqual(M.z_to_meshy(wz, M.z_to_rig(wz, z)), z, places=9)
        self.assertAlmostEqual(M.z_to_rig(wz, 0.735), 0.748)  # her crotch

    def test_soft_shapes(self):
        box = [0, 1, 0, 1, 0, 1]
        self.assertEqual(M.soft_box((0.5, 0.5, 0.5), box, 0.1), 1.0)
        self.assertEqual(M.soft_box((1.2, 0.5, 0.5), box, 0.1), 0.0)
        self.assertTrue(0.0 < M.soft_box((1.05, 0.5, 0.5), box, 0.1) < 1.0)
        self.assertEqual(M.soft_sphere((0, 0, 0), (0, 0, 0), 0.1), 1.0)
        self.assertEqual(M.soft_sphere((0.1, 0, 0), (0, 0, 0), 0.1), 0.0)

    def test_hand_scale(self):
        w, s, b = 0.65, 0.66, 0.05
        self.assertEqual(M.hand_x(0.6, w, s, b), 0.6)
        xs = [M.hand_x(w + 0.01 * k, w, s, b) for k in range(30)]
        self.assertTrue(all(b_ > a_ for a_, b_ in zip(xs, xs[1:])))  # monotone: the hand never folds over
        # far past the blend the length scales by s; the blend itself costs half its width's shortening
        tip = M.hand_x(0.936, w, s, b) - w
        self.assertAlmostEqual(tip, (0.936 - w - b) * s + b * (1 + s) / 2, places=3)
        self.assertAlmostEqual(M.hand_factor(w, w, s, b), 1.0)
        self.assertAlmostEqual(M.hand_factor(w + b, w, s, b), s)

    def test_neck_and_bust(self):
        self.assertEqual(M.neck_factor(1.30, 1.33, 1.39, 0.9), 1.0)
        self.assertAlmostEqual(M.neck_factor(1.39, 1.33, 1.39, 0.9), 0.9)
        c = [0.062, 1.18]
        self.assertAlmostEqual(M.bust_push((0.062, -0.1, 1.18), (0, -1, 0), c, 0.01, 0.08), 0.01)
        self.assertAlmostEqual(M.bust_push((-0.062, -0.1, 1.18), (0, -1, 0), c, 0.01, 0.08), 0.01)  # mirrored
        self.assertEqual(M.bust_push((0.062, 0.1, 1.18), (0, 1, 0), c, 0.01, 0.08), 0.0)  # her back
        self.assertEqual(M.bust_push((0.062, -0.1, 1.30), (0, -1, 0), c, 0.01, 0.08), 0.0)  # past the radius

    def test_ratios(self):
        self.assertEqual(M.pre_ratio(100, 200), 1.0)
        self.assertAlmostEqual(M.pre_ratio(466000, 140000), 140000 / 466000)
        self.assertAlmostEqual(M.body_ratio(38444, 23000), 23000 / 38444)
        with self.assertRaises(ValueError):
            M.body_ratio(10, 0)
        # the gills: 14,262 of the r5 head's 40,000 triangles, 70 % kept
        r = G.gill_decimate_ratio(40000, 14262, 0.7)
        self.assertAlmostEqual(40000 * r, 40000 - 0.3 * 14262)
        self.assertEqual(G.gill_decimate_ratio(40000, 14262, 1.0), 1.0)
        for bad in ((40000, 14262, 0.0), (40000, 50000, 0.5), (0, 0, 0.5)):
            with self.assertRaises(ValueError):
                G.gill_decimate_ratio(*bad)

    def test_gill_check_rows(self):
        # R1: the gills' decimation is checked on the result: a moved vertex or a changed corner UV is counted
        before = [(0.0, 0.0, 1.0), (0.1, 0.2, 1.3)]
        self.assertEqual(G.missing_rows(before, before + [(9.0, 9.0, 9.0)]), 0)
        self.assertEqual(G.missing_rows(before, [(0.0, 0.0, 1.0), (0.1, 0.2, 1.3000001)]), 1)
        corners = [(0.0, 0.0, 1.0, 0.25, 0.5)]
        self.assertEqual(G.missing_rows(corners, [(0.0, 0.0, 1.0, 0.25, 0.51)]), 1)


class HerTargets(unittest.TestCase):
    def test_keys_and_numbers(self):
        t = M.load(AX)
        self.assertEqual(t["name"], "axolotl_m1")
        self.assertAlmostEqual(t["ring_z"], 1.390)  # H5's ring
        # the head about 10 % up: the weld scales the head's waist onto the ring's half-width (H5's 0.0567)
        self.assertTrue(1.08 <= t["ring_half_x"] / 0.0567 <= 1.12)
        self.assertTrue(20000 <= t["body_tris"] <= 25000)
        # under 60k with the head (40k less the bust below its cut, about 3k, and 30 % of its 14.3k gill triangles)
        self.assertLess(t["body_tris"] + 40000 - 3000 - 0.3 * 14262 + 500, 60000)
        xs = [p[0] for p in t["arm_x"]]
        self.assertEqual(xs, sorted(xs))
        self.assertTrue(0.5 < t["hand"]["scale"] < 1.0)
        self.assertEqual(len(t["smooth"]["spheres"]), 2)  # both nipples
        for b in t["smooth"]["boxes"] + t["weight_smooth"]["zones"]:
            self.assertTrue(b[0] < b[1] and b[2] < b[3] and b[4] < b[5])

    def test_unknown_or_missing_keys(self):
        text = AX.read_text(encoding="utf-8")
        tmp = Path(__file__).resolve().parents[1] / "out" / "test_meshy_body_bad.toml"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp.write_text(text + "\nbogus = 1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                M.load(tmp)
            tmp.write_text(text.replace("body_tris = ", "body_tri = "), encoding="utf-8")
            with self.assertRaises(ValueError):
                M.load(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    def test_nested_keys(self):
        # R1: every committed target file loads; a typo inside a nested table fails instead of doing nothing
        for f in sorted(M.TARGETS.glob("*.toml")):
            M.load(f)
        m1f = M.TARGETS / "axolotl_m1f.toml"
        text = m1f.read_text(encoding="utf-8")
        tmp = Path(__file__).resolve().parents[1] / "out" / "test_meshy_body_nested.toml"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            # a fingers key, a bend's key, a key inside fingers.shape
            for old, new in (("thumb_falloff = ", "thumb_fallof = "), ("[[bends]]\n", "[[bends]]\nchlid = 1\n"),
                             ("shape = { slim = ", "shape = { slimm = ")):
                self.assertIn(old, text)
                tmp.write_text(text.replace(old, new, 1), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "unknown keys in"):
                    M.load(tmp)
        finally:
            tmp.unlink(missing_ok=True)


class FlagsOff(unittest.TestCase):
    """The welds of the cage bodies (H1 to H5, the chameleon) are unchanged: the new flags default off."""

    def test_build_and_run(self):
        build = (BL / "alien_char_build.py").read_text(encoding="utf-8")
        run = (BL / "alien_char_run.py").read_text(encoding="utf-8")
        for src in (build, run):
            self.assertRegex(src, r'"--no-flare", action="store_true"')
            self.assertRegex(src, r'"--gill-ratio", type=float, default=1\.0')
        self.assertIn("if a.gill_ratio < 1.0:", build)
        self.assertIn("for v in [] if a.no_flare else body.data.vertices:", build)
        self.assertTrue(re.search(r'\["--no-flare"\] if args\.no_flare else \[\]', run))
        beside = (BL / "alien_body_beside.py").read_text(encoding="utf-8")
        self.assertIn('"--concept-panels", type=int, default=3', beside)


if __name__ == "__main__":
    unittest.main()
