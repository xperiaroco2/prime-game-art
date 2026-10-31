"""The alien clip edits' pure maths (tools/blender/alien_clip_edit.py, art #196 A1) and the settings file."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_clip_edit as E  # noqa: E402

SETTINGS = ROOT / "tools" / "blender" / "anim_sets" / "alien.toml"


def angle(q):
    return 2.0 * math.degrees(math.acos(min(1.0, abs(q[0]))))


class CapTurn(unittest.TestCase):
    def test_caps_a_fist_and_keeps_the_axis(self):
        q = E.axis_turn((0.0, 0.0, 1.0), 80.0)
        c = E.cap_turn(q, 22.0)
        self.assertAlmostEqual(angle(c), 22.0, places=6)
        self.assertAlmostEqual(c[1], 0.0)
        self.assertAlmostEqual(c[2], 0.0)
        self.assertGreater(c[3], 0.0)

    def test_leaves_a_small_turn_and_the_negative_hemisphere(self):
        q = E.axis_turn((1.0, 2.0, 0.5), 10.0)
        self.assertEqual(E.cap_turn(q, 22.0), q)
        neg = tuple(-x for x in E.axis_turn((0.0, 1.0, 0.0), 60.0))
        self.assertAlmostEqual(angle(E.cap_turn(neg, 30.0)), 30.0, places=6)
        self.assertEqual(E.cap_turn(q, 0.0), q)

    def test_axis_turn_composes(self):
        a = E.axis_turn((0.0, 0.0, 1.0), 30.0)
        self.assertAlmostEqual(angle(E.q_mul(a, a)), 60.0, places=6)


class Lift(unittest.TestCase):
    def test_no_frame_stays_under(self):
        low = [0.01, 0.0, -0.02, -0.08, -0.03, 0.0, 0.02, 0.02, 0.02]
        lift = E.lift_profile(low)
        self.assertTrue(all(z + l >= -1e-9 for z, l in zip(low, lift)))
        self.assertEqual(E.lift_profile([0.0, 0.1, 0.2]), [0.0, 0.0, 0.0])

    def test_constant_sink_lifts_evenly(self):
        self.assertTrue(all(abs(x - 0.012) < 1e-12 for x in E.lift_profile([-0.012] * 7)))


# B1 (art #196, the Walk hop): body B13's Walk_Loop after the leg fit, the lowest skin point per frame (mm; the last
# frame is the first again), from D:/prime-art-raw/2026-10-31-hop/stages.json
WALK_LEG_FIT_MM = [-3.7, -8.1, -22.1, -30.3, -29.4, -13.2, 0.5, 2.2, 2.7, 2.1, 1.7, 1.4, 1.1, 0.3, -0.5, -1.3, -5.2,
                   -8.1, -21.9, -29.6, -29.6, -13.3, -2.2, -0.6, 0.7, 1.2, 1.5, 1.8, 2.1, 1.8, 1.2, -0.2, -3.7]


class FloorRule(unittest.TestCase):
    """The floor rule: a lift puts the lowest point on the floor and never floats a frame that was on it."""

    def after(self, reach):
        low = [x / 1000.0 for x in WALK_LEG_FIT_MM]
        return low, [z + l for z, l in zip(low, E.lift_profile(low, reach=reach, wrap=True))]

    def test_reach_two_floated_the_walk(self):  # the hop the engineer saw: up to 21 mm
        low, after = self.after(2)
        self.assertGreaterEqual(len(E.floated_frames(low, after)), 10)
        self.assertGreater(max(after), 0.02)

    def test_reach_zero_floats_no_frame(self):
        low, after = self.after(0)
        self.assertEqual(E.floated_frames(low, after), [])
        self.assertTrue(all(a >= -1e-9 for a in after))
        self.assertTrue(all(abs(a) < 1e-9 for z, a in zip(low, after) if z < 0))  # a sunk frame lands on the floor

    def test_flight_is_not_a_float(self):  # a run's frame already off the floor before is real flight
        self.assertEqual(E.floated_frames([-0.01, 0.08, 0.004], [0.0, 0.08, 0.004]), [])
        self.assertEqual(E.floated_frames([0.0, 0.001], [0.006, 0.001]), [0])

    def test_the_soles_count(self):  # the sneakers' heel dips under the bare foot at heel strike
        self.assertEqual(E.lowest_of([[0.0, 0.002, 0.01], [-0.0065, 0.003, 0.009]]), [-0.0065, 0.002, 0.009])

    def test_the_alien_loco_clips_lift_per_frame(self):
        toml = Path(E.__file__).resolve().parent / "anim_sets" / "alien.toml"
        for clip in ("Walk_Loop", "Jog_Fwd_Loop", "Sprint_Fwd_Loop", "Idle_Loop", "Crouch_Fwd_Loop", "Jump_Land"):
            cfg = E.settings(str(toml), clip)
            self.assertIs(cfg.get("floor"), True, clip)
            self.assertEqual(int(cfg.get("floor_reach", 2)), 0, clip)


class SoleRule(unittest.TestCase):
    """B1b (art #196): the soles on the floor at the foot, not the Hips, over every clip the game plays on the ground."""

    TOML = str(Path(E.__file__).resolve().parent / "anim_sets" / "alien.toml")

    def test_every_ground_clip_is_covered(self):  # B1 left the loco set's derived clips 5 to 19 mm under the floor
        names = ["Walk_Loop", "Jog_Fwd_Loop", "Jog_Fwd_Left_Loop", "Strafe_Left__w03_Loop", "Jog_Bwd__p2_Loop",
                 "Crouch_Fwd__ual_Loop", "Crouch_Run_Loop", "Idle_Loop", "Jump_Land", "Jump_Start", "Jump_Air_Loop"]
        got = E.ground_clips(names, self.TOML)
        self.assertEqual(got, names[:-2])  # not Jump_Start ("ground": its tuck) nor Jump_Air (held off the floor)

    def test_a_foot_rises_by_its_own_need_only(self):  # the trailing toe stays down, nothing floats
        heel = [0.0, -0.019, -0.012, -0.003, 0.0, 0.04]
        self.assertEqual(E.foot_raise(heel), [0.0, 0.019, 0.012, 0.003, 0.0, 0.0])
        after = [z + r for z, r in zip(heel, E.foot_raise(heel))]
        self.assertEqual(E.floated_frames(heel, after), [])
        self.assertTrue(all(abs(a) < 1e-12 for z, a in zip(heel, after) if z < 0))

    def test_raised_ankle_keeps_the_leg(self):  # a striking leg: the ankle up 19 mm, the hip kept
        hip, knee, ank = (0.1, 0.0, 0.85), (0.1, -0.12, 0.47), (0.1, -0.2, 0.07)
        lift = (0.0, 0.0, 0.019)
        k2 = E.raise_knee(hip, knee, ank, lift)
        a2 = tuple(a + d for a, d in zip(ank, lift))
        self.assertAlmostEqual(math.dist(hip, k2), math.dist(hip, knee), places=9)  # the thigh's length
        self.assertAlmostEqual(math.dist(k2, a2), math.dist(knee, ank), places=9)  # the shin's length
        self.assertAlmostEqual(k2[0], 0.1, places=9)  # the knee in the leg's own plane
        self.assertLess(k2[1], knee[1])  # the knee bends a little more forward

    def test_the_build_floors_at_the_foot(self):  # the Hips lift at reach 0 jerked the chameleon's Walk
        for clip in ("Walk_Loop", "Jog_Fwd_Loop", "Sprint_Fwd_Loop", "Idle_Loop", "Crouch_Fwd_Loop", "Jump_Land"):
            self.assertIs(E.settings(self.TOML, clip).get("floor_feet"), True, clip)

    def test_no_raise_no_change(self):
        hip, knee, ank = (0.1, 0.0, 0.85), (0.1, -0.12, 0.47), (0.1, -0.2, 0.07)
        for a, b in zip(E.raise_knee(hip, knee, ank, (0.0, 0.0, 0.0)), knee):
            self.assertAlmostEqual(a, b, places=9)


class A2Maths(unittest.TestCase):
    def test_arm_axis_signs(self):
        # the character faces -Y, its left is +X; a hand hangs along -Z
        down = (0.0, 0.0, -1.0)
        out_left = E.q_rotate(E.axis_turn((0.0, -1.0, 0.0), 1.0 * 10.0), down)  # abduct, the left arm (sign +1)
        self.assertGreater(out_left[0], 0.15)
        out_right = E.q_rotate(E.axis_turn((0.0, -1.0, 0.0), -1.0 * 10.0), down)  # the right arm (sign -1)
        self.assertLess(out_right[0], -0.15)
        fwd = E.q_rotate(E.axis_turn((1.0, 0.0, 0.0), -12.0), down)  # swing +12: about +X by a negative angle
        self.assertLess(fwd[1], -0.2)
        face = E.q_rotate(E.axis_turn((1.0, 0.0, 0.0), -10.0), (0.0, -1.0, 0.0))  # head_up: the face (-Y) goes up
        self.assertGreater(face[2], 0.15)

    def test_loop_lift_wraps(self):
        low = [-0.03, -0.01, 0.0, 0.01, 0.0, 0.0, 0.0, -0.02, -0.03]  # the last frame is the first again
        lift = E.lift_profile(low, wrap=True)
        self.assertEqual(lift[0], lift[-1])
        self.assertTrue(all(z + l >= -1e-9 for z, l in zip(low, lift)))

    def test_cut_frames(self):
        straight = [False, False, True, True, True, False, False, False]
        self.assertEqual(E.cut_frames(straight, 3), (1, 5, 1))
        self.assertIsNone(E.cut_frames([True, False, False], 3))
        self.assertIsNone(E.cut_frames([False, True, True], 3))

    def test_two_bone_keeps_lengths_and_ankle(self):
        hip, knee, ankle = (0.1, 0.0, 0.5), (0.1, -0.35, 0.35), (0.1, 0.0, 0.05)
        new_hip = (0.1, 0.0, 0.6)
        k2 = E.two_bone(hip, knee, ankle, new_hip)
        d = lambda a, b: math.dist(a, b)  # noqa: E731
        self.assertAlmostEqual(d(k2, new_hip), d(knee, hip), places=6)
        self.assertAlmostEqual(d(k2, ankle), d(ankle, knee), places=6)
        self.assertLess(k2[1], 0.0)  # the knee stays forward


class A3Maths(unittest.TestCase):
    def test_two_bone_with_pole_turn(self):
        hip, knee, ankle = (0.1, 0.0, 0.5), (0.1, -0.35, 0.35), (0.1, 0.0, 0.05)
        new_hip = (0.1, 0.0, 0.6)
        seen = []

        def toward_x(axis, pole):  # the knee turned in toward -X (the body's middle for a left leg)
            seen.append(tuple(axis))
            return E.q_rotate(E.axis_turn(axis, 20.0), pole)
        k0 = E.two_bone(hip, knee, ankle, new_hip)
        k2 = E.two_bone(hip, knee, ankle, new_hip, toward_x)
        self.assertEqual(len(seen), 1)
        d = lambda a, b: math.dist(a, b)  # noqa: E731
        self.assertAlmostEqual(d(k2, new_hip), d(knee, hip), places=6)
        self.assertAlmostEqual(d(k2, ankle), d(ankle, knee), places=6)
        self.assertLess(k2[0], k0[0] - 0.02)  # the knee turned toward -X, the body's middle (k0 0.100, k2 -0.008)
        self.assertLess(k2[1], 0.0)

    def test_floor_lift_reach_zero_is_exact(self):
        low = [0.01, -0.02, 0.0, -0.05, 0.03]
        self.assertEqual(E.lift_profile(low, reach=0), [0.0, 0.02, 0.0, 0.05, 0.0])

    def test_ground_lift_fades_into_the_tuck(self):
        lift = E.ground_lift([-0.05, -0.04, -0.2, -0.2, -0.2, -0.2], 1, 3)
        self.assertEqual(lift[:2], [0.05, 0.04])
        self.assertTrue(lift[1] > lift[2] > lift[3] > lift[4] == 0.0 == lift[5])

    def test_sway_one_period_clean_seam(self):
        s = E.sway(9)
        self.assertAlmostEqual(s[0], 0.0)
        self.assertAlmostEqual(s[-1], 0.0, places=9)
        self.assertAlmostEqual(s[2], 1.0)
        self.assertAlmostEqual(s[6], -1.0)

    def test_repeat_keys(self):
        plan = E.repeat_keys([0.0, 5.0, 10.0], 0.0, 10.0, 3)
        self.assertEqual(plan, [(0.0, 0), (5.0, 1), (10.0, 0), (15.0, 1), (20.0, 0), (25.0, 1), (30.0, 2)])
        self.assertEqual(E.repeat_keys([0.0, 10.0], 0.0, 10.0, 1), [(0.0, 0), (10.0, 1)])


class Settings(unittest.TestCase):
    def test_a3_floor_modes_and_idle(self):
        self.assertEqual(E.settings(str(SETTINGS), "Jump_Start")["floor"], "ground")
        idle = E.settings(str(SETTINGS), "Idle_Loop")
        self.assertGreater(idle["repeat"], 1)
        self.assertGreater(idle["sway_cm"], 0.0)
        for c in ("Crouch_Idle_Loop", "Crouch_Fwd_Loop"):
            self.assertEqual(E.settings(str(SETTINGS), c)["floor_reach"], 0)

    def test_every_clip_reads(self):
        for clip in ("Idle_Loop", "Walk_Loop", "Jump_Air_Loop", "Jump_Start"):
            cfg = E.settings(str(SETTINGS), clip)
            self.assertTrue(set(cfg) <= set(E.KEYS))
        self.assertFalse(E.settings(str(SETTINGS), "Jump_Air_Loop")["floor"])
        self.assertEqual(E.settings(str(SETTINGS), "Idle_Loop")["abduct_deg"], 6.0)

    def test_unlisted_clip_is_untouched_and_sprint_listed(self):
        self.assertEqual(E.settings(str(SETTINGS), "Some_Other_Clip"), {})
        self.assertEqual(E.settings(str(SETTINGS), "Sprint_Fwd_Loop")["finger_cap_deg"], 50.0)


if __name__ == "__main__":
    unittest.main()
