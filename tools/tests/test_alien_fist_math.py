"""The run fist's morph maths (art #196, H1j): tools/blender/alien_fist_math.py. Plain Python."""
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_fist_math as F  # noqa: E402

MM = 0.001


def _tube(x0: float, r: float, n_ring: int = 16, n_len: int = 21, length: float = 0.06):
    """A cylinder of radius r along +Y at x = x0 (rings of n_ring vertices), its points and ring neighbours."""
    pts, nbr = [], {}
    for j in range(n_len):
        for k in range(n_ring):
            a = 2 * math.pi * k / n_ring
            pts.append((x0 + r * math.cos(a), length * j / (n_len - 1), r * math.sin(a)))
    for j in range(n_len):
        for k in range(n_ring):
            i = j * n_ring + k
            ns = {j * n_ring + (k + 1) % n_ring, j * n_ring + (k - 1) % n_ring}
            if j:
                ns.add(i - n_ring)
            if j < n_len - 1:
                ns.add(i + n_ring)
            nbr[i] = ns
    return pts, nbr


class SdfTest(unittest.TestCase):
    def test_round_cone(self):
        a, b = (0, 0, 0), (0, 0.05, 0)
        self.assertAlmostEqual(F.round_cone((0.01, 0.025, 0), a, b, 0.01, 0.01), 0.0, places=9)
        self.assertAlmostEqual(F.round_cone((0, -0.02, 0), a, b, 0.01, 0.01), 0.01, places=9)
        # a taper: the side at mid length lies at the mean radius (nearly, the side's slope is small)
        self.assertAlmostEqual(F.round_cone((0.009, 0.025, 0), a, b, 0.010, 0.008), 0.0, places=4)
        self.assertAlmostEqual(F.round_cone((0, 0.058, 0), a, b, 0.010, 0.008), 0.0, places=9)

    def test_smin_fills_between(self):
        f = F.Fist({"A": [((0, 0, 0), 0.01), ((0, 0.05, 0), 0.01)], "B": [((0.021, 0, 0), 0.01),
                    ((0.021, 0.05, 0), 0.01)]}, "", 14 * MM, 0)
        # the valley above the 1 mm gap between two tubes is inside the smooth union, but not inside either tube
        p = (0.0105, 0.025, 0.006)
        self.assertGreater(min(f.digit("A", p), f.digit("B", p)), 0)
        self.assertLess(f.sd(p), 0)
        q = f.project(p)
        self.assertLess(abs(f.sd(q)), 1e-6)
        # a chain is a plain union: a bent joint's outside stays the tube's, no bulge
        g = F.Fist({"A": [((0, 0, 0), 0.01), ((0, 0.03, 0), 0.01), ((0.03, 0.03, 0), 0.01)]}, "", 14 * MM, 0)
        self.assertAlmostEqual(g.sd((-0.00707, 0.03707, 0)), 0.0, places=4)


class MovesTest(unittest.TestCase):
    def test_two_fingers_close_and_stay_smooth(self):
        r, gap = 10 * MM, 1 * MM
        a, na = _tube(0.0, r)
        b, nb = _tube(2 * r + gap, r)
        pts = a + b
        nbr = {**na, **{i + len(a): {j + len(a) for j in ns} for i, ns in nb.items()}}
        posed = dict(enumerate(pts))
        f = F.Fist({"A": [((0, 0, 0), r), ((0, 0.06, 0), r)],
                    "B": [((2 * r + gap, 0, 0), r), ((2 * r + gap, 0.06, 0), r)]}, "", 14 * MM, 0)
        moves, st = F.fist_moves(posed, {i: 1.0 for i in posed}, f, nbr, 2 * MM, 4 * MM, relax=2)
        self.assertGreater(st["moved"], 0)
        self.assertLessEqual(st["surface_err_mm"], 0.3)
        # the outward sides (away from the other tube) do not move: each tube keeps its own surface
        far = [i for i, p in posed.items() if p[0] < -0.9 * r and 0.01 < p[1] < 0.05]
        self.assertTrue(far)
        self.assertTrue(all(F._len(moves.get(i, (0, 0, 0))) < 0.05 * MM for i in far))
        # the vertex on the top of the gap's valley is lifted onto the web (the gap closed from above)
        top = max((i for i, p in posed.items() if i < len(a) and p[2] > 0 and abs(p[1] - 0.03) < 1e-9),
                  key=lambda i: posed[i][0])
        self.assertGreater(F._len(moves[top]), 0.5 * MM)

    def test_weight_fades_and_buried_hide(self):
        f = F.Fist({"A": [((0, 0, 0), 0.01), ((0, 0.05, 0), 0.01)]}, "", 14 * MM, 0)
        posed = {0: (0.007, 0.025, 0.0), 1: (0.002, 0.025, 0.0), 2: (0.007, 0.025, 0.0)}
        moves, st = F.fist_moves(posed, {0: 1.0, 1: 1.0, 2: 0.5}, f, {}, 2 * MM, 4 * MM, relax=0)
        self.assertAlmostEqual(F._len(moves[0]), 0.003, places=5)  # 3 mm deep: pushed out onto the surface
        self.assertAlmostEqual(F._len(moves[2]), 0.0015, places=5)  # half weighted: half way
        self.assertLess(f.sd(F._add(posed[1], moves[1])), -0.5 * MM)  # 8 mm deep: moved, but kept 2 mm under it
        self.assertEqual(st["hidden"], 1)


class WeightsTest(unittest.TestCase):
    def test_plan(self):
        self.assertEqual(F.weight_plan({"Left": [(0.0, "loose")], "Right": [(0.0, "loose")]}, "loose"), [(0.0, 1.0)])
        keys = F.weight_plan({"Left": [(0.0, "relaxed"), (0.5, "loose")],
                              "Right": [(0.0, "relaxed"), (0.5, "loose")]}, "loose")
        self.assertEqual(keys, [(0.0, 0.0), (0.5, 1.0)])
        self.assertEqual(F.weight_at(keys, 0.25), 0.5)
        self.assertEqual(F.weight_at(keys, 0.9), 1.0)
        with self.assertRaises(ValueError):
            F.weight_plan({"Left": [(0.0, "loose")], "Right": [(0.0, "relaxed")]}, "loose")

    def test_weight_plan_lead(self):
        """H1m: the morph reaches 1 at the lead's share of a ramp into the fist, and leaves 1 as late out of it."""
        plan = {s: [(0.0, "relaxed"), (0.5, "loose"), (0.75, "loose"), (1.0, "relaxed")] for s in ("Left", "Right")}
        keys = F.weight_plan(plan, "loose", 0.5)
        self.assertEqual(keys, [(0.0, 0.0), (0.25, 1.0), (0.5, 1.0), (0.75, 1.0), (0.875, 1.0), (1.0, 0.0)])
        self.assertEqual(F.weight_at(keys, 0.125), 0.5)
        self.assertEqual(F.weight_at(keys, 0.3), 1.0)
        self.assertGreater(F.weight_at(keys, 0.9), F.weight_at(F.weight_plan(plan, "loose"), 0.9))
        self.assertEqual(F.weight_plan(plan, "loose", 1.0), F.weight_plan(plan, "loose"))
        with self.assertRaises(ValueError):
            F.weight_plan(plan, "loose", 0.0)

    def test_key_weights_into_glb(self):
        times = [0.0, 0.5, 1.0]
        bin_ = bytearray(struct.pack("<3f", *times) + struct.pack("<12f", *([0, 0, 0, 1] * 3)))
        gltf = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(bin_)}],
                "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 12},
                                {"buffer": 0, "byteOffset": 12, "byteLength": 48}],
                "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "SCALAR", "min": [0],
                               "max": [1]}, {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC4"}],
                "nodes": [{"name": "Body", "mesh": 0}, {"name": "Bone"}],
                "meshes": [{"name": "Body", "extras": {"targetNames": ["fist"]},
                            "primitives": [{"attributes": {}, "targets": [{"POSITION": 1}]}]}],
                "animations": [{"name": n, "samplers": [{"input": 0, "output": 1}],
                                "channels": [{"sampler": 0, "target": {"node": 1, "path": "rotation"}}]}
                               for n in ("Jog", "Walk")]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.glb"
            F._write_glb(p, gltf, bin_)
            got = F.key_weights(p, "fist", {"Jog": [(0.0, 1.0)]})
            self.assertEqual(got, {"Jog": [1.0, 1.0], "Walk": [0.0, 0.0]})
            g2, b2 = F._glb(p)
            ch = g2["animations"][0]["channels"][-1]
            self.assertEqual(ch["target"], {"node": 0, "path": "weights"})
            acc = g2["accessors"][g2["animations"][0]["samplers"][ch["sampler"]]["output"]]
            bv = g2["bufferViews"][acc["bufferView"]]
            self.assertEqual(struct.unpack_from("<3f", b2, bv["byteOffset"]), (1.0, 1.0, 1.0))
            self.assertEqual(g2["meshes"][0]["weights"], [0.0])
            with self.assertRaises(ValueError):  # twice: refused
                F.key_weights(p, "fist", {})
            g2["meshes"][0]["extras"]["targetNames"] = ["fist", "other"]
            F._write_glb(p, g2, b2)
            with self.assertRaises(ValueError):
                F.key_weights(p, "fist", {})
        json.dumps(got)


if __name__ == "__main__":
    unittest.main()
