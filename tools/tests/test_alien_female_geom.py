"""The female body variant's maths and target file (art #196, clothes step 2): tools/blender/alien_female_geom.py."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_female_geom as G  # noqa: E402

F1 = ROOT / "tools" / "blender" / "alien_female_targets" / "f1.toml"


class FemaleGeomTest(unittest.TestCase):
    def setUp(self) -> None:
        self.t = G.load(F1)

    def test_every_target_file_loads(self) -> None:
        for p in sorted(F1.parent.glob("*.toml")):
            self.assertEqual(G.load(p)["name"], p.stem, p)

    def refused(self, edit, pattern: str) -> None:
        bad = copy.deepcopy(self.t)
        edit(bad)
        with self.assertRaisesRegex(ValueError, pattern):
            G.check(bad)

    def test_unknown_and_missing_nested_keys_are_refused(self) -> None:
        self.refused(lambda d: d["chest"].update(nipple_m=0.01), "chest keys")
        self.refused(lambda d: d["seat"].pop("ramp_m"), "seat keys")
        self.refused(lambda d: d.update(extra=1), "unknown keys")
        self.refused(lambda d: d.pop("waist"), "missing keys")
        self.refused(lambda d: d["hips"].update(amount_m=0.05), "max_delta_m")
        self.refused(lambda d: d["chest"].update(z=1.20), "box leaves")
        self.refused(lambda d: d["waist"].update(half_z="wide"), "not a number")
        self.refused(lambda d: d["mask"].update(bones=[]), "mask.bones")
        self.refused(lambda d: d.update(limits=3), "limits is not a table")

    def test_kernel_is_compact_and_smooth(self) -> None:
        self.assertEqual(G.kernel(0.0), 1.0)
        self.assertEqual(G.kernel(1.0), 0.0)
        self.assertEqual(G.kernel(-1.5), 0.0)
        self.assertLess(G.kernel(0.999), 1e-5)
        self.assertEqual((G.ramp(-1), G.ramp(0.5), G.ramp(2)), (0.0, 0.5, 1.0))

    def test_nothing_moves_outside_the_trunk_or_the_band(self) -> None:
        for x, f, z, w in ((0.1, 0.1, 1.40, 1.0), (0.1, 0.1, 0.40, 1.0), (0.3, 0.1, 1.1, 0.0),
                           (0.05, 0.08, 1.26, 1.0)):
            self.assertEqual(G.delta(x, f, z, w, self.t), (0.0, 0.0), (x, f, z, w))

    def test_chest_forward_on_the_front_seat_back_on_the_back(self) -> None:
        self.assertAlmostEqual(G.delta(0.058, 0.08, 1.12, 1.0, self.t)[1], 0.020, places=6)
        self.assertEqual(G.delta(0.058, -0.08, 1.12, 1.0, self.t)[1], 0.0)
        self.assertLess(G.delta(0.065, -0.10, 0.84, 1.0, self.t)[1], -0.017)
        self.assertGreater(G.delta(0.065, 0.10, 0.84, 1.0, self.t)[1], -1e-9)

    def test_hips_wider_waist_narrower_and_mirror_symmetric(self) -> None:
        dx = G.delta(0.135, 0.0, 0.87, 1.0, self.t)[0]
        self.assertAlmostEqual(dx, 0.022 - 0.010 * G.kernel(-0.13 / 0.07) * 0.135 / 0.106, places=6)
        self.assertLess(G.delta(0.106, 0.0, 1.00, 1.0, self.t)[0], 0.0)
        for p in ((0.09, 0.05, 1.1), (0.12, -0.07, 0.86), (0.03, 0.02, 0.95)):
            a, b = G.delta(*p, 0.8, self.t), G.delta(-p[0], p[1], p[2], 0.8, self.t)
            self.assertAlmostEqual(a[0], -b[0], places=12)
            self.assertAlmostEqual(a[1], b[1], places=12)
        self.assertEqual(G.delta(0.0, 0.0, 0.9, 1.0, self.t)[0], 0.0)

    def test_centre_line_and_report(self) -> None:
        chain = [(0.9, 0.01), (1.1, 0.03)]
        self.assertAlmostEqual(G.centre_f(1.0, chain), 0.02)
        self.assertEqual((G.centre_f(0.5, chain), G.centre_f(1.5, chain)), (0.01, 0.03))
        base = [(0.1, 0.0, 0.86), (0.0, 0.0, 1.8)]
        r = G.report(base, [(0.12, 0.0, 0.86), (0.0, 0.0, 1.8)])
        self.assertEqual((r["moved"], r["max_m"], r["top_z_m"]), (1, 0.02, [1.8, 1.8]))
        self.assertEqual(r["stations"]["0.86"]["female"]["half_x"], 0.12)
        with self.assertRaises(ValueError):
            G.report(base, base[:1])


if __name__ == "__main__":
    unittest.main()
