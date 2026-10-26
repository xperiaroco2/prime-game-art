"""The alien locomotion tool's step 4b additions (tools/blender/alien_stride_math.py, art #196): the honest foot slide
(height and speed only), the knee bend and its floor in `stride`, the arms given another loop's swing; on the
synthetic biped of test_alien_stride_math, no Blender."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_alien_stride_math import M, S, gait, same_rot, skeleton  # noqa: E402


class HonestSlide(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = gait(self.skel)

    def test_a_planted_gait_has_no_drift(self):
        out, _ = S.stride(self.skel, self.clip, cadence=2.4, scale=0.8)
        h = S.honest_slide(self.skel, out)
        for s in S.SIDES:
            self.assertGreater(h[s]["runs"], 0)
            self.assertLess(h[s]["drift_mm"], 2.0, s)

    def test_a_foot_dragged_on_the_floor_is_seen(self):
        out, _ = S.stride(self.skel, self.clip, cadence=2.4, scale=0.8)
        T = S.frames(out)
        # the left foot slides 1 mm a frame sideways all loop long (slow: under 0.5 m/s, so still a planted run)
        drag = S.copy_clip(out)
        drag["loc"]["Hips"] = [(x + 0.001 * f, y, z) for f, (x, y, z) in enumerate(out["loc"]["Hips"])]
        drag["loc"]["Hips"][T] = drag["loc"]["Hips"][0]
        h = S.honest_slide(self.skel, drag, ground=S.measure(self.skel, out)["ground_m_s"])
        self.assertGreater(h["Left"]["drift_mm"], 3.0)


class KneeBend(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = gait(self.skel)

    def test_the_gait_s_straight_stance_and_bent_swing(self):
        kb = S.knee_bend(self.skel, self.clip)
        for s in S.SIDES:
            self.assertLess(kb[s]["min_deg"], 1.0)  # the made-up gait locks the knee at the stance
            self.assertGreaterEqual(kb[s]["swing_min_deg"], kb[s]["min_deg"])

    def test_the_floor_bends_every_swing_frame_and_keeps_the_plant(self):
        out, rep = S.stride(self.skel, self.clip, scale=1.6, bend_min_deg=20.0)
        plain, _ = S.stride(self.skel, self.clip, scale=1.6)

        def straight(c, side):  # frames whose knee bends under 19.5 degrees
            tr = S.tracks(self.skel, c, [f"{side}{x}" for x in S.LEG])
            return sum(S._angle(M._v_sub(tr[f"{side}LowerLeg"][f], tr[f"{side}UpperLeg"][f]),
                                M._v_sub(tr[f"{side}Foot"][f], tr[f"{side}LowerLeg"][f])) < 19.5
                       for f in range(S.frames(c)))
        for s in S.SIDES:  # the swing frames bent; the stance keeps the gait's own straight knee
            self.assertLess(straight(out, s), straight(plain, s), s)
        self.assertLess(rep["ankle_miss_mm"], 1.0)  # the planted frames reach their goals
        self.assertGreater(max(rep["knee_floor_mm"].values()), 0.0)

    def test_the_floor_draws_the_ankle_toward_the_hip(self):
        H, K, A = (0.0, 0.0, 0.9), (0.0, 0.0, 0.5), (0.0, 0.0, 0.1)
        goal = (0.0, -0.8, 0.9)  # out of reach in front
        g = S._knee_floor(H, K, A, goal, 30.0)
        reach = math.sqrt(0.4 * 0.4 * 2 + 2 * 0.4 * 0.4 * math.cos(math.radians(30.0)))
        self.assertAlmostEqual(math.dist(g, H), reach, places=6)
        self.assertAlmostEqual(g[2], 0.9)  # along the hip's line: the same height here
        self.assertEqual(S._knee_floor(H, K, A, (0.0, -0.3, 0.5), 30.0), (0.0, -0.3, 0.5))  # bent enough: kept


class ArmsFrom(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = gait(self.skel)

    def test_a_still_armed_clip_takes_the_donor_s_swing(self):
        still, _ = S.arm_swing(self.clip, 0.0)
        out, rep = S.arms_from(still, self.clip, k=1.0, w=1.0)
        for s in S.SIDES:
            for p in S.ARM:
                b = f"{s}{p}"
                worst = max(same_rot(a, q) for a, q in zip(out["rot"][b], self.clip["rot"][b]))
                self.assertLess(worst, 0.5, b)
        self.assertEqual(out["rot"]["LeftUpperLeg"], still["rot"]["LeftUpperLeg"])

    def test_k_scales_the_swing_and_the_loop_stays_closed(self):
        still, _ = S.arm_swing(self.clip, 0.0)
        half = gait(self.skel, T=24)
        out, rep = S.arms_from(still, half, k=0.5, w=1.0)
        _, full = S.arms_from(still, half, k=1.0, w=1.0)
        for b, (_, after) in rep["swing_deg"].items():
            self.assertAlmostEqual(after, full["swing_deg"][b][1] * 0.5, delta=0.5, msg=b)
        self.assertLess(S.seam_deg(out), 1e-9)


if __name__ == "__main__":
    unittest.main()
