"""M13 (art #196): the fangs mouth mg2's two lower fangs (tools/blender/alien_fangs_geom.py) and its lip shape. Plain
Python: blunt round tips (never a point), a gentle even curve, a closed mesh, the axis in front of the lips above the
root and behind the lower lip's front below it; the lip shape thinner and wider than the frog's."""
from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

BL = Path(__file__).resolve().parents[2] / "tools" / "blender"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, BL / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FG = load("alien_fangs_geom")
LP = load("alien_lips_geom")


class ShapeTest(unittest.TestCase):
    def test_blunt_and_tapering(self):
        p = FG.merged()
        r = [FG.radius_at(i / 20, p) for i in range(21)]
        self.assertTrue(all(a >= b for a, b in zip(r, r[1:])))  # a cone, no waist
        self.assertAlmostEqual(r[0], p["radius"])
        self.assertGreaterEqual(r[-1], 0.4 * p["radius"])  # a round, blunt tip: never a point
        self.assertLess((1 - p["root"]) * p["length"], 0.016)  # short: under 16 mm shows above the lips
        self.assertLess(p["length"] / (2 * p["radius"]), 3.0)  # stubby: cute-tough, not a tusk

    def test_merged(self):
        q = FG.merged({"length": 0.012})
        self.assertEqual(q["length"], 0.012)
        self.assertEqual(FG.FANG["length"], FG.merged()["length"])

    def test_spine_curves_in_gently(self):
        p = FG.merged({"curve": 0.1, "lean": 0.05})
        ys = [-0.03] * (FG.ROWS + 1)
        for side in (1.0, -1.0):
            pts = FG.spine(0.04 * side, 1.40, 1.414, ys, p, side)
            self.assertAlmostEqual(pts[0][0], 0.04 * side)
            self.assertLess(abs(pts[-1][0]), 0.04)  # the tip toward the centre line
            self.assertLess(pts[-1][1], pts[0][1])  # and a little forward
            turns = []
            for a, b, c in zip(pts, pts[1:], pts[2:]):
                u = [b[i] - a[i] for i in range(3)]
                v = [c[i] - b[i] for i in range(3)]
                cos = sum(x * y for x, y in zip(u, v)) / (math.hypot(*u) * math.hypot(*v))
                turns.append(math.degrees(math.acos(max(-1.0, min(1.0, cos)))))
            self.assertLess(max(turns), 3.0)  # an even curve, no kink
            self.assertLess(sum(turns), 25.0)  # slightly curved

    def test_mesh_is_closed(self):
        p = FG.merged()
        pts = FG.spine(0.04, 1.40, 1.414, [-0.03] * (FG.ROWS + 1), p, 1.0)
        verts, faces = FG.mesh(pts, p)
        edges = {}
        for f in faces:
            for a, b in zip(f, f[1:] + f[:1]):
                k = (min(a, b), max(a, b))
                edges[k] = edges.get(k, 0) + 1
        self.assertTrue(all(n == 2 for n in edges.values()))  # watertight: every edge between two faces
        top = max(v[2] for v in verts)
        self.assertGreater(top, pts[-1][2])  # the round cap past the last ring
        self.assertLess(top - pts[-1][2], FG.radius_at(1.0, p) * 1.01)


class AxisTest(unittest.TestCase):
    def test_in_front_above_the_root_and_behind_below(self):
        p = FG.merged()
        n = FG.ROWS
        zs = [1.40 + p["length"] * i / n for i in range(n + 1)]
        z_root = zs[0] + p["root"] * p["length"]
        # the lower lip's front up to the root, the upper lip's above it (2 mm further back), the skin past the lips
        fronts = [-0.030 if z < z_root else (-0.028 if z < zs[0] + 0.8 * p["length"] else None) for z in zs]
        skin = [-0.020] * (n + 1)
        radii = [FG.radius_at(i / n, p) for i in range(n + 1)]
        ys = FG.axis_depths(zs, fronts, skin, radii, p, z_root)
        for z, y, f, r in zip(zs, ys, fronts, radii):
            h = r * p["flat"]
            if z > z_root + 0.2 * p["length"] and f is not None:
                self.assertLessEqual(y, f - 0.6 * h)  # before the upper lip, never in it
            if z < z_root - 0.2 * p["length"]:
                self.assertGreater(y, f - 0.4 * h)  # the root behind the lower lip's front
        for a, b, c in zip(ys, ys[1:], ys[2:]):
            self.assertLess(abs(a - 2 * b + c), 0.004)  # smooth (no step)

    def test_an_opening_is_bridged(self):
        p = FG.merged()
        zs = [0.0, 0.002, 0.004, 0.006, 0.008]
        fronts = [-0.03, None, None, None, -0.02]
        ys = FG.axis_depths(zs, fronts, [0.0] * 5, [0.003] * 5, dict(p, length=0.008), -1.0)
        self.assertTrue(all(-0.035 < y < -0.02 for y in ys))  # between the lips, not sunk to the skin


    def test_straight_axis_clears_and_never_kinks(self):  # O's fangs beside the ring
        p = FG.merged()
        n = FG.ROWS
        zs = [1.40 + p["length"] * i / n for i in range(n + 1)]
        z_root = zs[0] + p["root"] * p["length"]
        fronts = [None if i < 9 else -0.034 for i in range(n + 1)]  # the ring's side, then the cheek falling away
        skin = [-0.025 + 0.0004 * i for i in range(n + 1)]
        radii = [FG.radius_at(i / n, p) for i in range(n + 1)]
        ys = FG.axis_depths(zs, fronts, skin, radii, p, z_root, straight=True)
        d = [b - a for a, b in zip(ys, ys[1:])]
        self.assertLess(max(d) - min(d), 1e-9)  # one straight line
        for z, y, f, s, r in zip(zs, ys, fronts, skin, radii):
            if z > z_root:
                self.assertLessEqual(y, min(f if f is not None else s, s) - p["out"] * r * p["flat"] + 1e-9)


class FangLipsTest(unittest.TestCase):
    def test_thin_wide_calm(self):
        f, frog = LP.LIP_SHAPE_FANGS, LP.LIP_SHAPE
        self.assertLess(f["upper"], frog["upper"])
        self.assertLess(f["lower"], frog["lower"])
        self.assertLess(f["bow"], frog["bow"])  # a flat calm line
        self.assertGreater(f["width"], frog["width"])
        self.assertEqual(set(f["ring_param"]), {"A", "E", "O"})
        self.assertEqual(LP.merged_fangs(None), f)
        self.assertEqual(LP.merged_fangs({"upper": 0.6})["upper"], 0.6)
        self.assertEqual(LP.CONTACT_UV_MOUTH2[1], ("pout", "fangs"))


if __name__ == "__main__":
    unittest.main()
