"""The alien locomotion clip tool's pure maths (tools/blender/alien_stride_math.py, art #196 option A step 1) on a
synthetic biped with a made-up gait: measure, stride (retime and stride length with planted feet), cycle, arm swing,
mirror and the side-name rule, no Blender."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_stride_math as S  # noqa: E402

M = S.M
X = (1.0, 0.0, 0.0)
ID = (1.0, 0.0, 0.0, 0.0)


def skeleton() -> dict:
    rest, parent = {}, {}

    def add(name, head, par, q=ID):
        rest[name] = S.m4(head, q)
        parent[name] = par
    add("Root", (0.0, 0.0, 0.0), None)
    add("Hips", (0.0, 0.0, 0.9), "Root")
    add("Spine", (0.0, 0.0, 1.0), "Hips")
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        add(f"{side}UpperLeg", (0.1 * sx, 0.0, 0.9), "Hips")
        add(f"{side}LowerLeg", (0.1 * sx, 0.0, 0.5), f"{side}UpperLeg")
        add(f"{side}Foot", (0.1 * sx, 0.0, 0.1), f"{side}LowerLeg")
        add(f"{side}Toes", (0.1 * sx, -0.12, 0.02), f"{side}Foot")
        roll = M.q_axis_angle((0.0, 0.0, 1.0), -90.0 * sx)  # the arms carry rolls, the right one an extra one
        if side == "Right":
            roll = M.q_mul(roll, M.q_axis_angle((0.0, 1.0, 0.0), 15.0))
        add(f"{side}UpperArm", (0.2 * sx, 0.0, 1.4), "Spine", roll)
        add(f"{side}LowerArm", (0.45 * sx, 0.0, 1.4), f"{side}UpperArm", roll)
        add(f"{side}Hand", (0.7 * sx, 0.0, 1.4), f"{side}LowerArm", roll)
    return S.prepare({"rest": rest, "parent": parent})


def in_bone(skel, bone, q):
    """A world-axis turn q as bone's basis (its rest rotation's frame)."""
    r = S.mat_q(skel["rest"][bone])
    return M.q_norm(M.q_mul(M.q_mul(M.q_conj(r), q), r))


def gait(skel, T=24, frames=None, fps=24.0, name="Walk_Loop") -> dict:
    """In place: the thigh swings 25 degrees about X (positive: the foot back, +Y), the knee bends up to 50 degrees in
    the swing; the arms swing against the legs; one step per foot per T frames."""
    frames = T if frames is None else frames
    clip = {"name": name, "fps": fps, "loc": {}, "rot": {}}
    for f in range(frames + 1):
        for side, ph in (("Left", 0.0), ("Right", math.pi)):
            p = 2 * math.pi * f / T + ph
            a, b = 25.0 * math.sin(p), 60.0 * max(0.0, -math.cos(p))
            turns = {"UpperLeg": a, "LowerLeg": b, "Foot": 0.0, "Toes": 0.0, "UpperArm": -30.0 * math.sin(p),
                     "LowerArm": -10.0 - 10.0 * math.sin(p), "Hand": 5.0 * math.cos(p)}
            turns["Foot"] = -(a + b)  # the foot kept level: the toes land with the heel
            for part, deg in turns.items():
                bone = f"{side}{part}"
                clip["rot"].setdefault(bone, []).append(in_bone(skel, bone, M.q_axis_angle(X, deg)))
        for bone in ("Root", "Hips", "Spine"):
            clip["rot"].setdefault(bone, []).append(ID)
    clip["loc"] = {b: [(0.0, 0.0, 0.0)] * (frames + 1) for b in skel["order"]}
    return clip


def same_rot(a, b):
    return M.q_angle(M.q_norm(a), M.q_norm(b))


class Names(unittest.TestCase):
    def test_the_side_rule(self):
        self.assertEqual(S.mirror_name("LeftUpperArm"), "RightUpperArm")
        self.assertEqual(S.mirror_name("RightToes"), "LeftToes")
        self.assertEqual(S.mirror_name("Hips"), "Hips")
        self.assertEqual(S.mirror_name("Crest1"), "Crest1")
        self.assertEqual(S.mirror_clip_name("Strafe_Left_Loop"), "Strafe_Right_Loop")
        self.assertEqual(S.mirror_clip_name("Turn_Right"), "Turn_Left")
        with self.assertRaises(ValueError):
            S.mirror_pairs(["Hips", "LeftHand"])


class FillGaps(unittest.TestCase):
    def test_short_breaks_close_long_ones_stay(self):
        T, F = True, False
        self.assertEqual(S.fill_gaps([T, T, F, T, F, F, F, T], gap=2), [T, T, T, T, F, F, F, T])
        self.assertEqual(S.fill_gaps([F, T, T, F, F, F, T, F], gap=2), [T, T, T, F, F, F, T, T])  # over the seam
        self.assertEqual(S.fill_gaps([F, T, T, F, F, F, T, F], gap=2, cyclic=False), [F, T, T, F, F, F, T, F])


class Measure(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = gait(self.skel)

    def test_fk_puts_the_rest_where_it_was(self):
        clip = gait(self.skel)
        for v in clip["rot"].values():
            v[0] = ID
        poses = S.fk(self.skel, {**clip, "rot": {b: [ID] for b in clip["rot"]},
                                 "loc": {b: [(0, 0, 0)] for b in clip["rot"]}}, 0)
        self.assertAlmostEqual(S.pos(poses["LeftToes"])[1], -0.12)
        self.assertAlmostEqual(S.pos(poses["RightHand"])[0], -0.7)

    def test_one_step_per_foot(self):
        m = S.measure(self.skel, self.clip)
        self.assertEqual([len(m["contacts"][s]) for s in S.SIDES], [1, 1])
        self.assertAlmostEqual(m["c0"], 2.0)
        self.assertGreater(m["ground_m_s"][1], 0.0)  # the treadmill runs backward under a forward gait
        self.assertTrue(1.8 < m["v0"] < 2.3, m["v0"])
        self.assertAlmostEqual(m["stride_m"], m["v0"] / 2.0, places=3)
        self.assertLess(m["seam_deg"], 1e-6)

    def test_game_table(self):
        rows = S.game_table({"Jog_Fwd_Loop": {"v0": 4.0, "c0": 2.0}})
        walk = next(r for r in rows if r["what"] == "walk")
        self.assertAlmostEqual(walk["rate"], 1.125)
        self.assertAlmostEqual(walk["cadence"], 2.25)
        self.assertEqual(walk["beat_s"], 0.45)
        self.assertEqual({r["clip"] for r in rows}, {"Jog_Fwd_Loop"})


class Stride(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = gait(self.skel)

    def test_retime_and_shorter_stride_keep_the_feet_planted(self):
        out, rep = S.stride(self.skel, self.clip, cadence=2.4, scale=0.8)
        self.assertEqual(rep["intervals"], [24, 20])
        self.assertAlmostEqual(rep["after"]["c0"], 2.4)
        self.assertEqual([len(rep["after"]["contacts"][s]) for s in S.SIDES], [1, 1])
        self.assertLess(rep["ankle_miss_mm"], 1.0)
        self.assertLessEqual(rep["planted_slide_mm"], S.SLIDE_BOUND_MM)
        self.assertLess(abs(rep["after"]["v0"] / (rep["before"]["v0"] * 1.2 * 0.8) - 1.0), 0.1)
        self.assertLess(S.seam_deg(out), 1e-9)

    def test_speed_sets_the_scale_for_rate_one(self):
        out, rep = S.stride(self.skel, self.clip, cadence=2.0, speed=1.6)
        self.assertAlmostEqual(rep["rate_eff"], 1.0)
        self.assertAlmostEqual(rep["scale"], 1.6 / rep["before"]["v0"], places=3)
        self.assertLess(abs(rep["after"]["v0"] / 1.6 - 1.0), 0.1)
        self.assertLessEqual(rep["planted_slide_mm"], S.SLIDE_BOUND_MM)

    def test_retime_there_and_back(self):
        fast, r = S.retime(self.clip, 1.5)
        back, _ = S.retime(fast, 1.0 / r)
        self.assertEqual(S.frames(back), 24)
        worst = max(same_rot(a, b) for k in self.clip["rot"] for a, b in zip(self.clip["rot"][k], back["rot"][k]))
        self.assertLess(worst, 1.0)


class Roll(unittest.TestCase):
    """A foot that rolls over its toes: the toes planted on the moving ground while the ankle rises and swings about
    them; the plant hands over from the ankle to the toes with no slide."""
    def setUp(self):
        self.fps, self.v = 24.0, (0.0, 2.4)
        self.toe, self.ankle, self.mask_a, self.mask_t = [], [], [], []
        for f in range(12):
            g = (0.0, 0.1 * f)  # the ground's travel, 2.4 m/s at 24 fps
            tilt = math.radians(max(0, f - 4) * 8.0)  # the heel lifts from frame 5
            self.toe.append((g[0], g[1] - 0.12) if f < 9 else (0.0, g[1] - 0.12 + 0.05 * (f - 8)))
            self.ankle.append((self.toe[-1][0], self.toe[-1][1] + 0.12 * math.cos(tilt)))
            self.mask_a.append(f < 5)
            self.mask_t.append(f < 9)

    def test_no_slide_through_the_roll(self):
        self.assertLess(S.pivot_slide_mm(self.ankle, self.toe, self.mask_a, self.mask_t, self.v, self.fps), 1e-9)

    def test_a_sliding_toe_is_seen_and_planted(self):
        toe = [(x, y + 0.004 * max(0, f - 4)) for f, (x, y) in enumerate(self.toe)]  # 4 mm a frame after the heel
        ankle = [(a[0], a[1] + t[1] - t0[1]) for a, t, t0 in zip(self.ankle, toe, self.toe)]
        self.assertAlmostEqual(S.pivot_slide_mm(ankle, toe, self.mask_a, self.mask_t, self.v, self.fps), 16.0,
                               places=6)
        goals = S.plant_foot(ankle, toe, ankle, self.mask_a, self.mask_t, self.v, self.fps, blend=0)
        for f in range(9):
            self.assertLess(math.dist(goals[f], self.ankle[f]), 1e-9, f)


class Cycle(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()

    def test_a_closed_loop_starts_on_the_foot(self):
        clip = gait(self.skel)
        out, rep = S.cycle(self.skel, clip, foot="Right")
        self.assertTrue(rep["closed"])
        m = S.measure(self.skel, out)
        self.assertEqual(m["contacts"]["Right"], [0])
        self.assertLess(S.seam_deg(out), 1e-9)
        self.assertEqual(S.frames(out), 24)

    def test_a_travelling_loop_keeps_its_travel_when_turned_to_the_contact(self):
        # a root-motion loop (step 2's bakes): the frames before the contact go to the end one loop's travel on, so
        # the turned loop covers the same ground (step 3 found its speed collapsed to the wobble without this)
        clip = gait(self.skel)
        clip["loc"]["Hips"] = [(0.0, -0.05 * f, 0.0) for f in range(25)]
        out, rep = S.cycle(self.skel, clip, foot="Right")
        self.assertGreater(rep["start"], 0)
        a, b = (S.pos(S.fk(self.skel, out, f)["Hips"]) for f in (0, 24))
        self.assertAlmostEqual(b[1] - a[1], -1.2, places=6)
        steps = [S.pos(S.fk(self.skel, out, f + 1)["Hips"])[1] - S.pos(S.fk(self.skel, out, f)["Hips"])[1]
                 for f in range(24)]
        self.assertTrue(all(abs(s + 0.05) < 1e-6 for s in steps))  # no jump back at the old seam
        self.assertEqual(S.measure(self.skel, out)["hips_m_s"], S.measure(self.skel, clip)["hips_m_s"])
        starts = set()
        for k in range(24):  # the loop rolled to every phase: the end frame a loop on, never the start's copy
            rolled = S.copy_clip(clip)
            for ch in (rolled["loc"], rolled["rot"]):
                for bone, v in ch.items():
                    ch[bone] = v[k:-1] + v[:k] + [v[k]]
            rolled["loc"]["Hips"] = [(0.0, -0.05 * f, 0.0) for f in range(25)]
            turned, rk = S.cycle(self.skel, rolled, foot="Right")
            starts.add(rk["start"])
            a, b = (S.pos(S.fk(self.skel, turned, f)["Hips"]) for f in (0, 24))
            self.assertAlmostEqual(b[1] - a[1], -1.2, places=6)
        self.assertGreater(len(starts), 10)  # (b5's strafe on the alien starts on 0: checked in alien_loco's build)

    def test_a_travelling_loop_strided_keeps_its_seam(self):
        # stride's end frame: the start's feet a loop on, else the legs reach back a whole loop at the seam (step 3:
        # the strafes' mirrors showed a 108 degree seam)
        clip = gait(self.skel)
        clip["loc"]["Hips"] = [(0.0, -0.05 * f, 0.0) for f in range(25)]
        loop, _ = S.cycle(self.skel, clip, foot="Left")
        out, rep = S.stride(self.skel, loop, scale=1.5)
        self.assertLess(S.seam_deg(out), 1e-6)
        self.assertLess(S.seam_deg(S.mirror(self.skel, out)), 1e-6)

    def test_an_open_clip_is_cut_on_a_contact_with_no_seam(self):
        clip = gait(self.skel, T=24, frames=40, name="Walk_Start")
        self.assertGreater(S.seam_deg(clip), 5.0)
        out, rep = S.cycle(self.skel, clip, foot="Right", min_s=0.8, max_s=1.2)
        self.assertFalse(rep["closed"])
        self.assertEqual(rep["intervals"], 24)
        self.assertLess(rep["seam_deg"], 0.01)
        self.assertLess(rep["seam_after_deg"], 1e-6)
        self.assertEqual(S.measure(self.skel, out)["contacts"]["Right"], [0])


class ArmSwing(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = gait(self.skel)

    def test_one_leaves_the_clip(self):
        out, _ = S.arm_swing(self.clip, 1.0)
        worst = max(same_rot(a, b) for k in self.clip["rot"] for a, b in zip(self.clip["rot"][k], out["rot"][k]))
        self.assertLess(worst, 1e-6)

    def test_zero_holds_the_mean_and_half_halves(self):
        still, rep0 = S.arm_swing(self.clip, 0.0)
        for s in S.SIDES:
            for p in S.ARM:
                v = still["rot"][f"{s}{p}"]
                self.assertLess(max(same_rot(v[0], q) for q in v), 1e-6)
        _, rep = S.arm_swing(self.clip, 0.5)
        for b, (before, after) in rep["swing_deg"].items():
            self.assertAlmostEqual(after, before * 0.5, delta=0.3, msg=b)
        self.assertEqual(rep0["swing_deg"]["LeftUpperArm"][1], 0.0)
        # the legs are not touched
        self.assertEqual(still["rot"]["LeftUpperLeg"], self.clip["rot"]["LeftUpperLeg"])


class Mirror(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = gait(self.skel, name="Strafe_Left_Loop")
        for f in range(S.frames(self.clip) + 1):  # an asymmetric touch: the left hand turned in, the root moving left
            self.clip["rot"]["LeftHand"][f] = M.q_mul(self.clip["rot"]["LeftHand"][f],
                                                      M.q_axis_angle((0.3, 0.2, 0.9), 20.0))
            self.clip["loc"]["Root"][f] = (0.05 * f, 0.0, 0.0)

    def test_twice_is_the_clip(self):
        once = S.mirror(self.skel, self.clip)
        self.assertEqual(once["name"], "Strafe_Right_Loop")
        twice = S.mirror(self.skel, once)
        self.assertEqual(twice["name"], "Strafe_Left_Loop")
        for b in self.clip["rot"]:
            for a, c in zip(self.clip["rot"][b], twice["rot"][b]):
                self.assertLess(same_rot(a, c), 1e-6, b)
            for a, c in zip(self.clip["loc"][b], twice["loc"][b]):
                self.assertLess(math.dist(a, c), 1e-9, b)

    def test_the_sides_swap_in_the_world(self):
        once = S.mirror(self.skel, self.clip)
        a = S.tracks(self.skel, self.clip, ["LeftHand", "RightToes", "Hips"])
        b = S.tracks(self.skel, once, ["RightHand", "LeftToes", "Hips"])
        for (n1, t1), (n2, t2) in zip(a.items(), b.items()):
            for p, q in zip(t1, t2):
                self.assertLess(math.dist((-p[0], p[1], p[2]), q), 1e-9, (n1, n2))
        self.assertLess(b["Hips"][-1][0], -1.0)  # the root's travel flips on X


if __name__ == "__main__":
    unittest.main()
