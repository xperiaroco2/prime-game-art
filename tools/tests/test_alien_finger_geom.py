"""The fingers rebuilt as smooth tubes (art #196, Hands H1i): tools/blender/alien_finger_geom.py on a synthetic finger."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_finger_geom as F  # noqa: E402

JOINTS = [(0.0, 0.0, 0.0), (0.028, 0.0, 0.0), (0.052, 0.0, 0.0), (0.073, 0.0, 0.0)]
UP = (0.0, 0.0, 1.0)
SPEC = {"root_at": 0.012, "taper": 0.12, "ramp": [0.0, 0.014]}
N = 16


def finger(bump=0.0009, ellipse=0.08):
    """Rings every 2 mm from -10 mm to 68 mm, 16 vertices each, a bumpy elliptical section of 15 mm; a tip vertex."""
    pos, adj = {}, {}
    rings = [k * 0.002 - 0.010 for k in range(40)]
    for a, s in enumerate(rings):
        for b in range(N):
            t = 2 * math.pi * b / N
            r = 0.015 * (1 + ellipse * math.cos(2 * t)) + bump * math.sin(s * 450 + t)
            pos[a * N + b] = (s, r * math.cos(t), r * math.sin(t))
    tip = len(pos)
    pos[tip] = (rings[-1] + 0.010, 0.0, 0.0)
    for a in range(len(rings)):
        for b in range(N):
            i = a * N + b
            nb = {a * N + (b + 1) % N, a * N + (b - 1) % N}
            if a > 0:
                nb.add((a - 1) * N + b)
            nb.add((a + 1) * N + b if a + 1 < len(rings) else tip)
            adj[i] = nb
    adj[tip] = {(len(rings) - 1) * N + b for b in range(N)}
    return pos, adj


class TubeTest(unittest.TestCase):
    def test_axis_straight(self):
        ax = F.Axis(JOINTS, UP)
        s, a, r = ax.closest((0.030, 0.0, 0.012))
        self.assertAlmostEqual(s, 0.030, delta=1e-4)
        self.assertAlmostEqual(r, 0.012, delta=1e-4)
        self.assertAlmostEqual(ax.joint_s[2], 0.052, delta=1e-4)

    def test_bumps_removed_length_kept(self):
        pos, adj = finger()
        share = {i: 1.0 for i in pos}
        new, tube, rep = F.tube_finger(pos, share, adj, JOINTS, UP, SPEC, 0.015)
        self.assertGreater(rep["wave_before_mm"], 0.5)
        self.assertLess(rep["wave_after_mm"], 0.1)
        tip_before = max(F.Axis(JOINTS, UP).closest(p)[0] for p in pos.values())
        tip_after = max(tube.ax.closest(new.get(i, p))[0] for i, p in pos.items())
        self.assertAlmostEqual(tip_after, tip_before, delta=0.0015)
        for i, p in pos.items():  # behind the knuckle nothing moves
            if p[0] <= 0.0:
                self.assertLess(math.dist(new.get(i, p), p), 1e-6)

    def test_ellipse_kept(self):
        pos, adj = finger(bump=0.0)
        new, tube, rep = F.tube_finger(pos, {i: 1.0 for i in pos}, adj, JOINTS, UP, SPEC, 0.015)
        self.assertAlmostEqual(math.hypot(tube.ea, tube.eb), 0.08, delta=0.02)
        self.assertLess(rep["wave_before_mm"], 0.1)

    def test_joint_weights(self):
        ax = F.Axis(JOINTS, UP)
        bones = ["P", "I", "D"]
        last = None
        for k in range(70):
            w = F.joint_weights(k * 0.001, ax.joint_s, bones, 0.014, 0.5)
            self.assertAlmostEqual(sum(w.values()), 1.0, places=6)
            if last is not None:  # the distal's share never falls along the finger
                self.assertGreaterEqual(w.get("D", 0) + 1e-9, last)
            last = w.get("D", 0)
        self.assertEqual(F.joint_weights(0.040, ax.joint_s, bones, 0.014, 0.5), {"I": 1.0})


if __name__ == "__main__":
    unittest.main()
