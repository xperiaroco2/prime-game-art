"""The strafe pilot P3's edits (art #196; plain Python): lift_hips (the hips' height on the kept feet, the bob, the
flight), pin_feet, arms_in, arms_from's phase, orient's whole turn, the legs' room, and the real set's P3 clips."""
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


class LiftHips(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = full(self.skel, gait(self.skel))

    def test_lowered_hips_keep_the_feet_and_bend_the_knees(self):
        out, rep = S.lift_hips(self.skel, self.clip, lift_m=-0.03)
        legs = ["LeftFoot", "RightFoot", "LeftToes", "RightToes", "Hips"]
        a, b = S.tracks(self.skel, self.clip, legs), S.tracks(self.skel, out, legs)
        for f in range(S.frames(self.clip) + 1):
            for p in legs[:4]:
                self.assertLess(dist(a[p][f], b[p][f]), 1e-6)
            self.assertAlmostEqual(b["Hips"][f][2] - a["Hips"][f][2], -0.03, places=6)
        def bend(clip, f):  # the left knee on frame f (a bent knee: a straight one has no plane to bend in)
            t = S.tracks(self.skel, clip, ["LeftUpperLeg", "LeftLowerLeg", "LeftFoot"])
            return S._angle(S.M._v_sub(t["LeftLowerLeg"][f], t["LeftUpperLeg"][f]),
                            S.M._v_sub(t["LeftFoot"][f], t["LeftLowerLeg"][f]))
        self.assertGreater(bend(out, 12), bend(self.clip, 12) + 2.0)
        self.assertEqual(rep["lift_m"], -0.03)

    def test_a_flight_raises_the_whole_body_at_the_handover(self):
        out, rep = S.lift_hips(self.skel, self.clip, flight_m=0.02)
        legs = ["LeftFoot", "RightFoot", "Hips"]
        a, b = S.tracks(self.skel, self.clip, legs), S.tracks(self.skel, out, legs)
        rises = [b["Hips"][f][2] - a["Hips"][f][2] for f in range(S.frames(self.clip))]
        self.assertGreater(max(rises), 0.015)
        self.assertGreaterEqual(min(rises), -1e-9)
        for f in range(S.frames(self.clip)):  # the feet rise with the hips: a hop, the legs' pose unchanged
            for p in legs[:2]:
                self.assertAlmostEqual(b[p][f][2] - a[p][f][2], rises[f], places=6)


class PinAndArms(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip, _ = S.stride(self.skel, full(self.skel, gait(self.skel)), speed=1.6)

    def test_pin_feet_never_adds_drift_and_keeps_the_hips(self):
        out, rep = S.pin_feet(self.skel, self.clip)
        for s in ("Left", "Right"):
            before, after = rep["drift_mm"][s]
            self.assertLessEqual(after, before + 0.1)
        a, b = S.tracks(self.skel, self.clip, ["Hips"]), S.tracks(self.skel, out, ["Hips"])
        self.assertLess(max(dist(x, y) for x, y in zip(a["Hips"], b["Hips"])), 1e-9)

    def test_pin_run_keeps_the_correction_continuous_when_the_anchor_switches(self):
        # P5's review: the ankle slides 3 mm a frame while down, then the toe (sliding 1 mm a frame) takes over; each
        # anchor is held still, and the correction never jumps at the switch (it fell to 0 there: 12 mm in a frame)
        run = list(range(10))
        tr = {"A": [(0.003 * f, 0.0, 0.0) for f in run], "T": [(0.1 + 0.001 * f, 0.0, 0.0) for f in run]}
        masks = {"A": [f < 5 for f in run], "T": [True] * 10}
        c = S._pin_run(run, masks, tr, (0.0, 0.0), "A", "T")
        for f in run:
            p = "A" if f < 5 else "T"
            self.assertAlmostEqual(tr[p][f][0] + c[f][0], tr[p][0 if f < 5 else 5][0] + c[0 if f < 5 else 5][0])
        self.assertAlmostEqual(c[0][0], 0.0)
        self.assertLessEqual(max(abs(c[f + 1][0] - c[f][0]) for f in run[:-1]), 0.003 + 1e-12)
        self.assertAlmostEqual(c[5][0], c[4][0])

    def test_pin_feet_takes_out_a_known_ankle_slide_without_a_jump(self):
        masks, _, step = S._honest_down(self.skel, self.clip)
        T = S.frames(self.clip)
        down = [masks["LeftFoot"][f] or masks["LeftToes"][f] for f in range(T)]
        run = max(S.M.contact_windows(down, cyclic=True), key=len)
        slid = S.copy_clip(self.clip)  # the left thigh turned 0.6 degrees more each planted frame: the ankle slides
        for k, f in enumerate(run):
            for g in ([f, T] if f == 0 else [f]):
                q = slid["rot"]["LeftUpperLeg"][g]
                slid["rot"]["LeftUpperLeg"][g] = S.M.q_mul(q, S.M.q_axis_angle((1.0, 0.0, 0.0), 0.6 * k))
        out, rep = S.pin_feet(self.skel, slid)
        before, after = rep["drift_mm"]["Left"]
        self.assertGreater(before, 3.0)
        self.assertLess(after, 0.5 * before)
        a = S.tracks(self.skel, out, ["LeftFoot"])["LeftFoot"]
        jumps = [math.hypot(a[f + 1][0] - a[f][0] - step[0], a[f + 1][1] - a[f][1] - step[1]) * 1000.0
                 for f in run[:-1]]
        self.assertLess(max(jumps), 3.0)

    def test_arms_in_brings_the_hands_toward_the_torso(self):
        h0 = S.hand_clearance(self.skel, self.clip)
        h1 = S.hand_clearance(self.skel, S.arms_in(self.skel, self.clip, 30.0))
        for s in ("Left", "Right"):
            self.assertLess(h1[s], h0[s] - 0.02)

    def test_arms_from_with_half_a_phase_is_the_donor_half_a_loop_on(self):
        donor = self.clip
        out, rep = S.arms_from(self.clip, donor, k=1.0, w=1.0, phase=0.5)
        T = S.frames(self.clip)
        for f in (0, 3, 7):
            q, d = out["rot"]["LeftUpperArm"][f], donor["rot"]["LeftUpperArm"][(f + T // 2) % T]
            self.assertLess(S.M.q_angle(S.M.q_norm(q), S.M.q_norm(d)), 0.5)
        self.assertEqual(rep["phase"], 0.5)

    def test_leg_spacing_grows_with_the_stride_widening(self):
        wide, _ = S.stride(self.skel, full(self.skel, gait(self.skel)), speed=1.6, widen_m=0.03)
        a, b = S.leg_spacing(self.skel, self.clip), S.leg_spacing(self.skel, wide)
        self.assertGreater(b["ankle_min_m"], a["ankle_min_m"] + 0.05)
        self.assertEqual(set(S.elbow_bend(self.skel, self.clip)), {"Left", "Right"})


class WholeTurn(unittest.TestCase):
    def test_the_whole_turn_sets_the_travel_and_keeps_the_pose(self):
        skel = skeleton()
        clip, _ = S.stride(skel, full(skel, gait(skel)), speed=1.6)
        out, rep = L.orient(S, skel, clip, {"whole": True, "travel": 30.0})
        self.assertAlmostEqual(S.travel_heading_deg(S.measure(skel, out)), 30.0, delta=0.5)
        f0, f1 = S.facing(skel, clip), S.facing(skel, out)
        self.assertAlmostEqual(S._wrap(f1["hips_yaw_deg"] - f0["hips_yaw_deg"]), rep["whole_turn_deg"], delta=0.5)
        self.assertAlmostEqual(S._wrap(f1["head_yaw_deg"] - f0["head_yaw_deg"]), rep["whole_turn_deg"], delta=0.5)
        self.assertEqual([round(v["min_deg"], 1) for v in S.knee_bend(skel, clip).values()],
                         [round(v["min_deg"], 1) for v in S.knee_bend(skel, out).values()])


class RealSet(unittest.TestCase):
    def test_the_real_set_has_the_p3_clips(self):
        cfg = L.load()
        jobs = {j["name"]: j for j in L.expand(cfg)}
        self.assertNotIn("Strafe_Left__100s", jobs)  # dropped (P2's critic)
        for n in ("Crouch_Fwd", "Crouch_Run"):
            self.assertTrue(jobs[n]["orient"]["whole"])
        for n in ("Jog_Bwd", "Jog_Bwd__c20", "Jog_Bwd__c25", "Jog_Bwd__c30", "Jog_Bwd_Left"):
            self.assertTrue(jobs[n]["pin"])
            self.assertEqual(jobs[n]["arms_from"]["phase"], 0.5)
        for n in ("Strafe_Left", "Jog_Fwd_Left"):
            self.assertGreater(jobs[n]["lift_m"], 0.0)
            self.assertGreater(jobs[n]["arms_in_deg"], 0.0)
        plan = {r["name"] for r in L.reel_plan(L.expand(cfg), cfg["reel"])}
        self.assertTrue({"Crouch_facing__front", "Jog_Bwd__front", "Jog_Bwd_Left__back"} <= plan)


if __name__ == "__main__":
    unittest.main()
