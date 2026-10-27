"""The strafe pilot P4's edits (art #196; plain Python): even_steps (the other foot's contact at half the cycle),
arms_carry (the wrists on a running carriage, the arms' lengths kept, the swing against the leg) and the real set's P4
back clips."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_alien_stride_orient import full, skeleton  # noqa: E402
from test_alien_stride_math import S, gait  # noqa: E402
import alien_loco_math as L  # noqa: E402


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class EvenSteps(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        clip = full(self.skel, gait(self.skel))
        T = S.frames(clip)
        # an uneven gait: the right foot's contact pulled earlier by a warp the other way
        self.uneven = {**clip, "loc": {}, "rot": {}}
        warp = [(u + 0.12 * T * math.sin(math.pi * u / T) ** 2) % T for u in range(T)]
        for ch in ("loc", "rot"):
            for b, v in clip[ch].items():
                rows = []
                for t in warp:
                    i, fr = S.M.split_index(t, T)
                    a, c = v[i], v[(i + 1) % T]
                    rows.append(tuple(x + (y - x) * fr for x, y in zip(a, c)))
                rows.append(rows[0])
                self.uneven[ch][b] = rows if ch == "loc" else [S.M.q_norm(q) for q in rows]

    def test_the_other_contact_moves_to_half_and_the_seam_stays(self):
        T = S.frames(self.uneven)
        before = S.measure(self.skel, self.uneven)["contacts"]["Right"]
        out, rep = S.even_steps(self.skel, self.uneven, "Left")
        after = S.measure(self.skel, out)["contacts"]["Right"]
        gap = lambda c: min(abs(s - T / 2.0) for s in c)  # noqa: E731
        self.assertLess(gap(after), gap(before))
        self.assertLessEqual(gap(after), 1.0)
        self.assertEqual(S.frames(out), T)
        self.assertEqual(rep["start_after"], after)
        for b, v in out["rot"].items():  # frame 0 kept: the loop still starts on the left contact
            self.assertLess(S.M.q_angle(S.M.q_norm(v[0]), S.M.q_norm(self.uneven["rot"][b][0])), 1e-6)

    def test_an_even_gait_comes_back_unchanged(self):
        clip = full(self.skel, gait(self.skel))
        T = S.frames(clip)
        start = S.measure(self.skel, clip)["contacts"]["Right"]
        out, rep = S.even_steps(self.skel, clip, "Left")
        if min(abs(s - T / 2.0) for s in start) == 0:  # no warp asked: every frame the same
            for b, v in clip["rot"].items():
                for f in range(T + 1):
                    self.assertLess(S.M.q_angle(S.M.q_norm(v[f]), S.M.q_norm(out["rot"][b][f])), 1e-6)
        self.assertEqual(rep["start_after"], S.measure(self.skel, out)["contacts"]["Right"])


class ArmsCarry(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip, _ = S.stride(self.skel, full(self.skel, gait(self.skel)), speed=1.6)

    def test_the_wrists_reach_their_targets_with_the_arms_lengths_kept(self):
        out, rep = S.arms_carry(self.skel, self.clip, side_m=0.18, front_m=0.15, dz_m=0.0, swing_m=0.0)
        names = [f"{s}{x}" for s in S.SIDES for x in S.ARM] + ["Spine"]
        a, b = S.tracks(self.skel, self.clip, names), S.tracks(self.skel, out, names)
        for s in S.SIDES:
            for f in range(S.frames(out) + 1):
                self.assertAlmostEqual(dist(b[f"{s}UpperArm"][f], b[f"{s}LowerArm"][f]),
                                       dist(a[f"{s}UpperArm"][f], a[f"{s}LowerArm"][f]), places=6)
                self.assertAlmostEqual(dist(b[f"{s}LowerArm"][f], b[f"{s}Hand"][f]),
                                       dist(a[f"{s}LowerArm"][f], a[f"{s}Hand"][f]), places=6)
                self.assertLess(dist(b[f"{s}UpperArm"][f], a[f"{s}UpperArm"][f]), 1e-6)  # the shoulder stays
        for s in S.SIDES:
            self.assertAlmostEqual(rep[s]["midline_m"], 0.18, places=3)
            self.assertAlmostEqual(rep[s]["wrist_dz_m"][0], 0.0, places=3)
            self.assertAlmostEqual(rep[s]["wrist_front_m"][1], 0.15, places=3)
        self.assertEqual(S.tracks(self.skel, out, ["LeftFoot"])["LeftFoot"],
                         S.tracks(self.skel, self.clip, ["LeftFoot"])["LeftFoot"])  # the legs untouched

    def test_the_hand_swings_against_its_own_leg(self):
        out, _ = S.arms_carry(self.skel, self.clip, swing_m=0.05)
        P = [S.fk(self.skel, out, f) for f in range(S.frames(out))]
        for s in S.SIDES:
            hand, foot = [], []
            for p in P:
                front = S._body_axes(self.skel, p)[0]
                hand.append(S.M._v_dot(S.M._v_sub(S.pos(p[f"{s}Hand"]), S.pos(p["Spine"])), front))
                foot.append(S.M._v_dot(S.M._v_sub(S.pos(p[f"{s}Foot"]), S.pos(p["Hips"])), front))
            mh, mf = sum(hand) / len(hand), sum(foot) / len(foot)
            self.assertLess(sum((h - mh) * (x - mf) for h, x in zip(hand, foot)), 0.0)


class RealSet(unittest.TestCase):
    def test_the_real_set_has_the_p4_back_clips(self):
        cfg = L.load()
        jobs = {j["name"]: j for j in L.expand(cfg)}
        for n in ("Jog_Bwd", "Jog_Bwd_Left"):
            self.assertTrue(jobs[n]["even_steps"])
            ac = jobs[n]["arms_carry"]
            self.assertGreaterEqual(math.hypot(ac["side_m"], ac["front_m"]), 0.22)
            self.assertGreater(ac["side_m"], 0.0)  # never across the midline
        for n in ("Jog_Bwd__p3", "Jog_Bwd_Left__p3"):  # P3's, the reels' before rows
            self.assertFalse(jobs[n].get("even_steps"))
            self.assertFalse(jobs[n].get("arms_carry"))
        plan = {r["name"]: r for r in L.reel_plan(L.expand(cfg), cfg["reel"])}
        self.assertEqual(plan["Jog_Bwd__front"]["clips"][0]["clip"], "Jog_Bwd__p3")
        self.assertEqual(plan["Jog_Bwd_Left__back"]["clips"][0]["clip"], "Jog_Bwd_Left__p3")


if __name__ == "__main__":
    unittest.main()
