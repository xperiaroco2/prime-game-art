"""The grips solved from the drawn spec (art #196, Hands H1g; tools/blender/alien_grip_solve.py): plain Python, a
synthetic hand (no raw files)."""
import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_grip_solve as G  # noqa: E402
import alien_hands_math as H  # noqa: E402
import alien_pose_math as A  # noqa: E402

# the synthetic left hand: the Hand bone at the origin along +y (metres), x its palm normal; fingers along +y at
# their z, each bone's x axis the hand's -z (the rig's bend axis), the thumb from the palm's thumb side
FZ = {"Index": 0.045, "Middle": 0.015, "Ring": -0.02}
SEG = 0.026
R = 0.013


def _m(origin, x, y):
    z = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    return [[x[0], y[0], z[0], origin[0]], [x[1], y[1], z[1], origin[1]], [x[2], y[2], z[2], origin[2]],
            [0.0, 0.0, 0.0, 1.0]]


def synthetic_dump() -> dict:
    rest = {"LeftHand": _m((0, 0, 0), (1, 0, 0), (0, 1, 0))}
    parent = {"LeftHand": None}
    bones, points, weights, dom = ["LeftHand"], [], [], []

    def ring(bi, c, axis_y, n=12, rad=R):  # points around a bone's axis (x, z circle)
        for k in range(n):
            a = 2 * math.pi * k / n
            points.append((c[0] + rad * math.cos(a), c[1] + axis_y, c[2] + rad * math.sin(a)))
            weights.append([[bi, 1.0]])
            dom.append(bi)
    for f, z in FZ.items():
        prev = "LeftHand"
        for i, s in enumerate(G.CHAIN[f]):
            b = f"Left{f}{s}"
            rest[b] = _m((0.006, 0.12 + SEG * i, z), (0, 0, -1), (0, 1, 0))
            parent[b] = prev
            prev = b
            bones.append(b)
            for j in range(4):
                ring(len(bones) - 1, (0.006, 0.12 + SEG * i, z), SEG * (j + 0.5) / 4)
    prev = "LeftHand"
    for i, s in enumerate(G.CHAIN["Thumb"]):
        b = f"LeftThumb{s}"
        rest[b] = _m((0.02, 0.03 + 0.025 * i, 0.06), (0, 0, -1), (0, 1, 0))
        parent[b] = prev
        prev = b
        bones.append(b)
        for j in range(4):
            ring(len(bones) - 1, (0.02, 0.03 + 0.025 * i, 0.06), 0.025 * (j + 0.5) / 4)
    for k in range(400):  # the palm: a slab x in [-0.015, 0.02], y in [0, 0.115], z in [-0.035, 0.06]
        y, z = 0.115 * (k % 20) / 19, -0.035 + 0.095 * (k // 20) / 19
        points.append((0.02, y, z))
        weights.append([[0, 1.0]])
        dom.append(0)
    return {"skel": {"rest": rest, "parent": parent},
            "skin": {"bones": bones, "points": points, "weights": weights, "dom": dom}}


def spec() -> dict:
    s = G.load_spec()
    s["solve"]["iters"] = 120
    return s


class GeometryTest(unittest.TestCase):
    def test_segment_distances(self):
        self.assertAlmostEqual(G.seg_point((0, 1, 0), (0, 0, 0), (2, 0, 0)), 1.0)
        self.assertAlmostEqual(G.seg_point((3, 0, 0), (0, 0, 0), (2, 0, 0)), 1.0)
        self.assertAlmostEqual(G.seg_seg((0, 0, 0), (1, 0, 0), (0.5, 1, -1), (0.5, 1, 1)), 1.0)
        self.assertAlmostEqual(G.seg_seg((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)), 1.0)
        self.assertAlmostEqual(G.seg_seg((0, 0, 0), (1, 0, 0), (0, 2, 0), (1, 2, 0)), 2.0)


class HandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dump = synthetic_dump()
        cls.hand = G.Hand(cls.dump, spec(), "S")

    def test_capsules_in_mm_from_the_tubes(self):
        ln, r = self.hand.cap["LeftIndexProximal"]
        self.assertAlmostEqual(ln, SEG * 1000, delta=0.01)
        self.assertAlmostEqual(r, R * 1000, delta=0.5)
        self.assertGreater(len(self.hand.palm_all), 400)  # the height field between the palm's points

    def test_pose_matches_the_rig(self):
        g = {"Index": [40, 50, 10, 5], "Middle": [30, 20, 5], "Ring": [10, 10, 0], "Thumb": [10, 20, 5],
             "ThumbTurn": [15, 30], "mirror": True}
        P = self.hand.pose(g)
        rig = A.Rig(self.dump["skel"])
        for b, q in A.grip_quats(g, "Left").items():
            if b in rig.rot:
                rig.local(b, q)
        W = rig.P()
        for b in ("LeftIndexDistal", "LeftThumbDistal", "LeftRingIntermediate"):
            for k in range(3):
                self.assertAlmostEqual(P[b][k][3], 1000 * W[b][k][3], delta=1e-6)
                for c in range(3):
                    self.assertAlmostEqual(P[b][k][c], W[b][k][c], delta=1e-9)

    def test_positive_curl_folds_toward_the_palm(self):
        tip = self.hand.capsules(self.hand.pose({"Index": [60, 60, 10]}))["LeftIndexDistal"][1]
        self.assertGreater(tip[0], 20.0)  # + x: the palm side

    def test_side_turn_is_mirrored(self):
        left = A.grip_quats({"Index": [0, 0, 0, 8], "mirror": True}, "Left")["LeftIndexProximal"]
        right = A.grip_quats({"Index": [0, 0, 0, 8], "mirror": True}, "Right")["RightIndexProximal"]
        self.assertAlmostEqual(left[3], -right[3])
        self.assertGreater(abs(left[3]), 0.05)

    def test_loose_solve_touches_the_palm_without_going_in(self):
        s = spec()
        res = G.solve([self.hand], s, "loose")
        rep = G.report([self.hand], s, "loose", res["grip"])["S"]
        for f, r in rep["palm"].items():
            self.assertGreaterEqual(r["intermediate"], -0.5, f)
            self.assertGreaterEqual(r["tip"], -0.5, f)
            self.assertLessEqual(r["tip"], 3.0, f)
        lim = s["grips"]["loose"]["limits"]["finger"]
        for f in G.FING:
            self.assertLessEqual(res["grip"][f][2], lim[2][1] + 0.5)
        H._check_grip("loose", res["grip"])  # alien_hands.toml's form


class SpecTest(unittest.TestCase):
    def test_spec_and_the_set_agree(self):
        s = G.load_spec()
        for name in ("loose", "relaxed"):
            g = s["grips"][name]
            for f in (*G.FING, "Thumb"):
                self.assertIn(f, g["starts"])
                self.assertIn(f if f == "Thumb" else "finger", g["limits"])
        hands = tomllib.loads((ROOT / "tools/blender/anim_sets/alien_hands.toml").read_text(encoding="utf-8"))
        for f in G.FING:  # the loose grip is solved (its side turn); the relaxed one is H1f's r2 again (H1h)
            self.assertEqual(len(hands["grips"]["loose"][f]), 4, f)
        self.assertLessEqual(max(hands["grips"]["loose"][f][2] for f in G.FING), 15.0)  # the tip joint <= 15


if __name__ == "__main__":
    unittest.main()
