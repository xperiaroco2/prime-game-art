"""The hand and wrist rebuilt in place: the maths (tools/blender/alien_hand_geom.py; art #196, Hands H1b)."""
import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_hand_geom as G  # noqa: E402
import alien_hand_run as RUN  # noqa: E402

N = 16


def tube(radius, s_values):
    """A tube along +x: rings of N vertices; radius(s) -> (half width along y, half thickness along z)."""
    pos, edges = {}, []
    for r, s in enumerate(s_values):
        a, b = radius(s)
        for k in range(N):
            t = 2 * math.pi * k / N
            pos[r * N + k] = [s, a * math.cos(t), b * math.sin(t)]
            edges.append((r * N + k, r * N + (k + 1) % N))
            if r:
                edges.append(((r - 1) * N + k, r * N + k))
    return pos, edges


class Basics(unittest.TestCase):
    def test_ease_is_monotone_with_flat_ends(self):
        ys = [G.ease(2.0, 5.0, t / 20) for t in range(21)]
        self.assertEqual((ys[0], ys[-1]), (2.0, 5.0))
        self.assertTrue(all(b >= a for a, b in zip(ys, ys[1:])))

    def test_slice_extents_of_an_ellipse(self):
        pos, edges = tube(lambda s: (0.03, 0.02), [k * 0.01 for k in range(5)])
        cu, cv, hu, hv = G.slice_extents(pos, edges, [0, 0, 0], G.frame([1, 0, 0], [0, 1, 0]), 0.015)
        self.assertAlmostEqual(hu, 0.03, places=4)
        self.assertAlmostEqual(hv, 0.02, places=4)
        self.assertAlmostEqual(cu, 0.0, places=6)

    def test_section_fold(self):
        ring = [(math.cos(2 * math.pi * k / 24), math.sin(2 * math.pi * k / 24)) for k in range(24)]
        self.assertLess(G.section(ring)["fold_mm"], 1e-6)
        dented = ring + [(0.0, 0.5)]
        self.assertAlmostEqual(G.section(dented)["fold_mm"], 500.0, delta=5)

    def test_taubin_holds_the_held(self):
        pos, edges = tube(lambda s: (0.03, 0.03), [k * 0.01 for k in range(5)])
        pos[2 * N][1] += 0.01
        adj = G.adjacency(None, edges)
        new = G.taubin(pos, adj, {i for i in pos if N <= i < 4 * N}, 10)
        self.assertEqual(new[0], pos[0])
        self.assertLess(abs(new[2 * N][1] - 0.03), 0.01)

    def test_row_gaps(self):
        self.assertEqual(G.row_gaps([0.0, 0.002, 0.007], -0.001, 0.008), 5.0)


class Band(unittest.TestCase):
    def test_pinch_and_lump_become_the_spec_profile(self):
        def r(s):  # a forearm 30 mm, a neck before the joint, a lump after it, the palm 45 x 25 mm
            base = 0.030 if s < 0.02 else 0.030 + (s - 0.02) * 0.5
            bump = -0.010 * math.exp(-((s + 0.01) / 0.006) ** 2) + 0.012 * math.exp(-((s - 0.008) / 0.006) ** 2)
            return min(0.045, base + bump), 0.025
        ss = [k * 0.003 for k in range(-20, 21)]
        pos, edges = tube(r, ss)
        adj = G.adjacency(None, edges)
        w = {i: {"LeftLowerArm": 1.0} for i in pos}
        spec = {"s_fore": -0.035, "s_palm": 0.04, "wrist_width_ratio": 0.95, "wrist_thick_ratio": 0.9, "taubin": 40}
        fr = G.frame([1, 0, 0], [0, 1, 0])
        new, rep = G.wrist_band(pos, w, adj, [0, 0, 0], fr, "Left", spec)
        after = dict(pos)
        after.update(new)
        widths = [G.slice_extents(after, edges, [0, 0, 0], fr, s)[2] for s in [k * 0.005 for k in range(-6, 8)]]
        fallen = widths[:7]
        self.assertTrue(all(b <= a + 5e-4 for a, b in zip(fallen, fallen[1:])), widths)
        self.assertAlmostEqual(widths[6], 0.95 * 0.030, delta=0.002)
        self.assertTrue(all(i not in new for i in pos if pos[i][0] <= -0.035 or pos[i][0] >= 0.04))


class Finger(unittest.TestCase):
    def test_bulges_go_and_the_tip_is_a_dome(self):
        def r(s):
            v = 0.015 - 0.04 * max(0.0, s - 0.01) + 0.003 * math.exp(-((s - 0.03) / 0.004) ** 2)
            return v, v
        ss = [k * 0.004 for k in range(0, 21)]
        pos, _ = tube(r, ss)
        share = {i: 1.0 for i in pos}
        spec = {"root_at": 0.01, "taper": 0.1, "ramp": [0.0, 0.008]}
        new, rep = G.finger(pos, share, [[0, 0, 0], [0.04, 0, 0], [0.08, 0, 0]], spec)
        radii = {}
        for i, p in new.items():
            radii.setdefault(round(pos[i][0], 4), []).append(math.hypot(p[1], p[2]))
        mid = [sum(v) / len(v) for s, v in sorted(radii.items()) if 0.012 <= s <= 0.05]
        self.assertTrue(all(b <= a + 2e-4 for a, b in zip(mid, mid[1:])), mid)
        self.assertGreater(min(mid), 0.015 * 0.85)


class Spec(unittest.TestCase):
    def test_the_spec_holds_every_key(self):
        spec = tomllib.loads((ROOT / "tools/blender/body_dims/hand_dims.toml").read_text())
        for k in ("s_fore", "s_palm", "wrist_width_ratio", "wrist_thick_ratio", "taubin", "row_gap_max_mm",
                  "fold_max_mm", "taper_monotone"):
            self.assertIn(k, spec["wrist"])
        self.assertLess(spec["wrist"]["s_fore"], 0)
        self.assertGreater(spec["wrist"]["s_palm"], 0)
        for g in ("fingers", "thumb"):
            self.assertEqual(set(spec[g]), {"root_at", "taper", "ramp"})

    def test_monotone_check(self):
        rows = [[-30, 70, 60], [-15, 68, 58], [0, 66, 55], [15, 75, 58], [30, 90, 62]]
        self.assertTrue(RUN.monotone_ok(rows, -30, 30))
        self.assertFalse(RUN.monotone_ok(rows[:2] + [[0, 72, 55]] + rows[3:], -30, 30))


class Transfer(unittest.TestCase):
    def test_nearest_within_tolerance_across_a_cell_border(self):
        # H1b's rounded keys missed a point whose copy fell on the other side of a rounding border
        pts = {7: (0.12345, 0.5, 1.0), 8: (0.2, 0.5, 1.0)}
        grid = G.grid_index(pts, RUN.TRANSFER_TOL)
        self.assertEqual(G.grid_nearest(grid, (0.1234499, 0.5, 1.0), RUN.TRANSFER_TOL)[0], 7)
        i, d = G.grid_nearest(grid, (0.12365, 0.5, 1.0), RUN.TRANSFER_TOL)
        self.assertIsNone(i)
        self.assertAlmostEqual(d, 0.0002, places=6)
        self.assertEqual(G.grid_nearest(grid, (0.5, 0.5, 1.0), RUN.TRANSFER_TOL), (None, None))


if __name__ == "__main__":
    unittest.main()
