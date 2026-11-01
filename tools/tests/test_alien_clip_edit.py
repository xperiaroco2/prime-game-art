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

    def test_a_sideways_lift_keeps_the_leg(self):  # B1i: the cross push's path, the ankle out and up
        hip, knee, ank = (0.1, 0.0, 0.85), (0.1, -0.12, 0.47), (0.1, -0.2, 0.07)
        lift = (0.019, 0.0, 0.004)
        k2 = E.raise_knee(hip, knee, ank, lift)
        a2 = tuple(a + d for a, d in zip(ank, lift))
        self.assertAlmostEqual(math.dist(hip, k2), math.dist(hip, knee), places=9)
        self.assertAlmostEqual(math.dist(k2, a2), math.dist(knee, ank), places=9)
        self.assertGreater(k2[0], 0.1 + 0.001)  # the knee follows the ankle out of the old plane
        self.assertLess(k2[0], a2[0])
        # the knee in the plane of the moved leg (hip to the new ankle) and the clip's own bend (the pole)
        ax = tuple(b - a for a, b in zip(hip, ank))
        kv = tuple(b - a for a, b in zip(hip, knee))
        t = sum(x * y for x, y in zip(kv, ax)) / sum(x * x for x in ax)
        pole = tuple(k - t * a for k, a in zip(kv, ax))
        u, v = tuple(b - a for a, b in zip(hip, a2)), tuple(b - a for a, b in zip(hip, k2))
        det = (u[0] * (v[1] * pole[2] - v[2] * pole[1]) - u[1] * (v[0] * pole[2] - v[2] * pole[0])
               + u[2] * (v[0] * pole[1] - v[1] * pole[0]))
        self.assertAlmostEqual(det, 0.0, places=12)

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



class B1kPlant(unittest.TestCase):
    """B1k (art #196, the crouch's lift-off slide): each foot planted on its own through its stance, its drift on the
    contact patch's own points held back, eased in before its landing and out after its lift-off (plant_offsets)."""

    V = 0.01  # the ground's travel a frame (an in-place clip)

    def rolling(self, n=12, start=4, dtheta=0.08, slip=0.0):
        """A flat sole of 121 points (1 mm apart, behind its tip) whose tip travels with the ground (plus slip a
        frame), flat on frames before start, then rolling up about its tip by dtheta a frame: (frames_xy, patches,
        lows), the patch as _foot_lows makes it (the points within PLANT_PATCH_M over the lowest)."""
        frames, patches, lows = [], [], []
        for i in range(n):
            th = max(0, i - start + 1) * dtheta
            tip = self.V * i + slip * max(0, i - start)
            pts = [(0.08, tip - d * math.cos(th), d * math.sin(th)) for d in (k / 1000 for k in range(121))]
            low = min(z for _, _, z in pts)
            frames.append([(x, y) for x, y, _ in pts])
            patches.append([j for j, (_, _, z) in enumerate(pts) if z <= low + E.PLANT_PATCH_M])
            lows.append(low)
        return frames, patches, lows

    def crouch(self, drag=0.03):
        """13 frames of an in-place crouch, the ground travelling V a frame: the left foot hovers 12 mm in its stance
        (0-5), stays the lower foot while it lifts off (6-8: 2-6 mm up, dragged drag a frame off the ground) and
        swings (9-12); the right foot swings forward 50 mm up, then hovers 15 mm from frame 9 on. (lows, steps)."""
        ll = [0.012] * 6 + [0.006, 0.002, 0.004] + [0.03, 0.05, 0.05, 0.04]
        rl = [0.05] * 9 + [0.015] * 4
        ls = [None] + [(0.0, self.V)] * 5 + [(0.0, self.V + drag)] * 3 + [(0.0, -0.05)] * 4
        rs = [None] + [(0.0, -0.05)] * 8 + [(0.0, self.V)] * 4
        return {"Left": ll, "Right": rl}, {"Left": ls, "Right": rs}

    def test_a_rolling_sole_steps_with_the_ground(self):
        frames, patches, lows = self.rolling()
        steps = E.patch_steps(frames, patches)
        self.assertIsNone(steps[0])
        for j in range(1, len(steps)):
            self.assertLess(math.hypot(steps[j][0], steps[j][1] - self.V), 0.0005, j)
        fr, pa, _ = self.rolling(slip=0.004)  # a toe slipping 4 mm a frame steps off the ground by that
        self.assertAlmostEqual(E.patch_steps(fr, pa)[8][1] - self.V, 0.004, delta=0.0005)
        g = E.ground_step({"Left": lows, "Right": [0.05] * len(lows)}, {"Left": steps, "Right": [None] * len(lows)})
        self.assertAlmostEqual(g[1], self.V, delta=0.0005)
        self.assertEqual(E.ground_step({"Left": [0.0], "Right": [0.1]}, {"Left": [None], "Right": [None]}),
                         (0.0, 0.0))

    def test_the_lift_off_stands_still_until_the_other_lands(self):
        lows, steps = self.crouch()
        off, low = E.plant_offsets(lows, steps, (0.0, self.V), True)
        after = {s: [z + o[2] for z, o in zip(lows[s], off[s])] for s in lows}
        self.assertEqual(low["Left"], list(range(9)))
        self.assertEqual(low["Right"], list(range(9, 13)))
        for i in range(9):
            self.assertAlmostEqual(after["Left"][i], 0.0, msg=i)  # planted through the lift-off
        for j in range(1, 9):  # its steps after: the ground's travel, no slide
            dy = steps["Left"][j][1] + off["Left"][j][1] - off["Left"][j - 1][1]
            self.assertAlmostEqual(dy, self.V, msg=j)
        self.assertAlmostEqual(off["Left"][8][1], -0.09)  # three frames of 3 cm drag held back
        self.assertAlmostEqual(off["Left"][9][1], -0.09 * 0.75)  # eased out over the swing
        self.assertAlmostEqual(off["Left"][10][1], -0.09 * 0.25)
        self.assertEqual(off["Left"][11], (0.0, 0.0, 0.0))
        self.assertTrue(all(z >= 0.0 for v in after.values() for z in v))
        self.assertTrue(all(min(a, b) <= E.PLANT_ON_M for a, b in zip(after["Left"], after["Right"])))  # no float
        self.assertAlmostEqual(after["Right"][8], 0.05 - 0.75 * 0.015)  # its landing eased in
        self.assertAlmostEqual(after["Right"][7], 0.05 - 0.25 * 0.015)
        self.assertEqual(off["Right"][3], (0.0, 0.0, 0.0))  # mid-swing: its own height and place
        moved = {s: [None if st is None else (st[0] + off[s][j][0] - off[s][j - 1][0],
                                              st[1] + off[s][j][1] - off[s][j - 1][1])
                     for j, st in enumerate(steps[s])] for s in steps}
        self.assertLess(max(E.plant_slides(after, moved, (0.0, self.V), low).values()), 1e-9)
        b1e = {"Left": [0.0] * 9 + lows["Left"][9:], "Right": lows["Right"]}  # B1e's landing: the drag on the floor
        self.assertAlmostEqual(max(E.plant_slides(b1e, steps, (0.0, self.V)).values()), 0.03)

    def test_a_hold_past_the_cap_is_not_made(self):
        lows, steps = self.crouch(drag=0.06)  # three frames of 6 cm: an 18 cm hold, the clip's own slide
        unheld = {}
        off, low = E.plant_offsets(lows, steps, (0.0, self.V), True, unheld=unheld)
        self.assertEqual(unheld, {"Left": [0], "Right": []})
        self.assertTrue(all(o[:2] == (0.0, 0.0) for o in off["Left"][:9]))  # lowered, not held
        self.assertAlmostEqual(lows["Left"][7] + off["Left"][7][2], 0.0)

    def test_a_foot_on_the_floor_and_a_flight(self):
        lows = {"Left": [0.0, 0.0, 0.0, 0.0003], "Right": [0.03, 0.0, 0.02, 0.04]}
        steps = {"Left": [None] + [(0.0, 0.013)] * 3, "Right": [None] + [(0.0, -0.05)] * 3}
        off, low = E.plant_offsets(lows, steps, (0.0, self.V), True)
        self.assertEqual(low, {"Left": [], "Right": []})  # on the floor: the clip's own, its slide not touched
        self.assertTrue(all(o == (0.0, 0.0, 0.0) for v in off.values() for o in v))
        off, low = E.plant_offsets({"Left": [-0.004, 0.05], "Right": [0.06, 0.08]}, steps, (0.0, 0.0), False)
        self.assertAlmostEqual(off["Left"][0][2], 0.004)  # a flight: only a sunk foot raised, by its own need
        self.assertEqual(off["Left"][1], (0.0, 0.0, 0.0))
        self.assertEqual(off["Right"], [(0.0, 0.0, 0.0)] * 2)
        off, _ = E.plant_offsets({"Left": [1.0, 1.0], "Right": [1.0, 1.0]}, steps, (0.0, 0.0), True)
        self.assertEqual(off["Left"], [(0.0, 0.0, 0.0)] * 2)  # no foot near the floor

    def test_a_whole_loop_closes(self):
        lows = {"Left": [0.002] * 9, "Right": [0.002] * 9}  # an idle hovering 2 mm, the left drifting 1 mm a frame
        steps = {"Left": [(0.0, 0.001)] * 9, "Right": [(0.0, 0.0)] * 9}
        off, low = E.plant_offsets(lows, steps, (0.0, 0.0), True, wrap=True)
        self.assertEqual(off["Left"][-1], off["Left"][0])
        dy = [steps["Left"][j][1] + off["Left"][j][1] - off["Left"][j - 1][1] for j in range(1, 9)]
        self.assertLess(max(abs(d - dy[0]) for d in dy), 1e-12)  # held evenly around the seam
        self.assertTrue(all(abs(o[2] + 0.002) < 1e-12 for o in off["Right"]))

    def test_no_flight_clips(self):
        self.assertFalse(E.can_fly("Crouch_Fwd_Loop"))
        self.assertFalse(E.can_fly("Crouch_Idle_Loop"))
        self.assertTrue(E.can_fly("Sprint_Fwd_Loop"))
        for clip in ("Crouch_Run_Loop", "Crouch_Run__p2_Loop", "Crouch_Run__s4b_Loop"):  # B1i: a run flies
            self.assertTrue(E.can_fly(clip), clip)


class B1fCross(unittest.TestCase):
    """B1f, B1g (art #196): the shoes moved apart by their real overlap (convex hulls) plus a clearance."""

    @staticmethod
    def box(u0, u1, a0, a1, b0, b1):
        """An axis box as hull planes (nu, na, nb, d): nu*u + na*a + nb*b <= d."""
        return [(1, 0, 0, u1), (-1, 0, 0, -u0), (0, 1, 0, a1), (0, -1, 0, -a0), (0, 0, 1, b1), (0, 0, -1, -b0)]

    def depth(self, swing, planted):
        sb, pb = [self.bounds(swing), self.bounds(planted)]
        box = (max(sb[0], pb[0]), min(sb[1], pb[1]), max(sb[2], pb[2]), min(sb[3], pb[3]))
        return E.cross_depth(E.hull_gaps(swing, planted), box)

    @staticmethod
    def bounds(planes):
        get = {(na, nb): d for _, na, nb, d in planes}
        return (-get[(-1, 0)], get[(1, 0)], -get[(0, -1)], get[(0, 1)])

    def test_slab(self):
        h = self.box(-0.05, 0.04, 0.0, 0.25, 0.0, 0.08)
        self.assertEqual(E.hull_slab(h, 0.1, 0.04), (-0.05, 0.04))
        self.assertIsNone(E.hull_slab(h, 0.3, 0.04))
        wedge = [(1, 0, 1, 0.1), (-1, 0, 0, 0.0), (0, 1, 0, 1), (0, -1, 0, 1), (0, 0, -1, 0.0)]  # u <= 0.1 - b
        lo, hi = E.hull_slab(wedge, 0.0, 0.04)
        self.assertAlmostEqual(hi, 0.06)

    def test_overlap_plus_clear(self):
        planted = self.box(-0.05, 0.04, 0.0, 0.25, 0.0, 0.08)  # outer side at u = 0.04
        swing = self.box(0.02, 0.12, 0.10, 0.30, 0.03, 0.10)  # inner side at u = 0.02: 2 cm into it
        d = self.depth(swing, planted)
        self.assertAlmostEqual(d[0], 0.02)
        self.assertAlmostEqual(E.cross_overlap(d), 0.02)
        self.assertAlmostEqual(E.cross_need(d, 0.005), 0.025)

    def test_no_overlap_no_need(self):
        planted = self.box(-0.05, 0.04, 0.0, 0.25, 0.0, 0.08)
        for swing in (self.box(0.06, 0.16, 0.10, 0.30, 0.03, 0.10),  # 2 cm out: clear
                      self.box(0.042, 0.14, 0.10, 0.30, 0.03, 0.10),  # 2 mm out: within the clearance, still none
                      self.box(0.0, 0.10, 0.10, 0.30, 0.0805, 0.20),  # over it by 0.5 mm
                      self.box(0.0, 0.10, 0.2502, 0.40, 0.0, 0.08)):  # in front of it by 0.2 mm
            d = self.depth(swing, planted)
            self.assertEqual(E.cross_need(d, 0.005), 0.0, swing)
            self.assertEqual(E.cross_overlap(d), 0.0, swing)

    def test_a_slanted_hull_fine(self):
        # the planted shoe's outer side leans: u <= 0.04 - 0.25 * (b - 0.04); the swinging shoe's inner side at
        # u = 0.035 from b = 0.06 up: the overlap is at b = 0.06, 0.04 - 0.005 - 0.035 = 0 ... 0.5 mm deeper at 0.058
        planted = [(1, 0, 0.25, 0.04 + 0.25 * 0.04), (-1, 0, 0, 0.05), (0, 1, 0, 0.25), (0, -1, 0, 0.0),
                   (0, 0, 1, 0.08), (0, 0, -1, 0.0)]
        swing = self.box(0.035, 0.12, 0.10, 0.30, 0.058, 0.10)
        d = E.cross_depth(E.hull_gaps(swing, planted), (0.10, 0.25, 0.058, 0.08))
        self.assertAlmostEqual(d[0], 0.04 - 0.25 * 0.018 - 0.035, places=6)

    def test_crossed_way_out(self):
        planted = self.box(-0.05, 0.04, 0.0, 0.25, 0.0, 0.08)
        swing = self.box(-0.10, -0.02, 0.10, 0.30, 0.03, 0.10)  # mostly inward of its far side: across is shorter
        d = self.depth(swing, planted)
        self.assertAlmostEqual(E.cross_overlap(d), 0.03)  # -0.02 + 0.05
        self.assertEqual(E.cross_need(d, 0.005), 0.0)

    def test_bump_covers_the_need_and_eases(self):
        need = [0.0] * 5 + [0.01, 0.02, 0.01] + [0.0] * 5
        b = E.cross_bump(need)
        self.assertTrue(all(x >= n - 1e-12 for x, n in zip(b, need)))
        self.assertAlmostEqual(max(b), 0.02)
        self.assertEqual(b[:3], [0.0] * 3)  # nothing beyond 2 frames of the overlap
        self.assertEqual(b[-3:], [0.0] * 3)
        self.assertAlmostEqual(b[4], 0.01 * 0.75)  # one frame before the overlap: its first frame eased
        steps = [abs(a - c) for a, c in zip(b, b[1:])]
        self.assertLessEqual(max(steps), 0.0101)

    def test_bump_wraps_the_seam(self):
        need = [0.01] + [0.0] * 9 + [0.01]  # a loop: the last frame is the first
        b = E.cross_bump(need, wrap=True)
        self.assertAlmostEqual(b[-1], b[0])
        self.assertAlmostEqual(b[1], 0.0075)
        self.assertAlmostEqual(b[9], 0.0075)  # the frame before the seam eases in too

    def test_only_the_swinging_foot_moves(self):
        lows = {"Left": [0.0, 0.0, 0.05], "Right": [0.06, 0.02, 0.0]}
        p = E.cross_pushes(lows, [0.025, 0.0, 0.01], reach=0)
        self.assertEqual(p["Left"], [0.0, 0.0, 0.01])  # the left foot planted on frames 0-1
        self.assertEqual(p["Right"], [0.025, 0.0, 0.0])

    def test_no_overlap_exactly_zero(self):
        lows = {"Left": [0.0, 0.0, 0.0, 0.01, 0.03, 0.0], "Right": [0.02, 0.01, 0.0, 0.0, 0.0, 0.0]}
        for wrap in (False, True):
            p = E.cross_pushes(lows, [0.0] * 6, wrap=wrap)
            self.assertEqual(p, {"Left": [0.0] * 6, "Right": [0.0] * 6})
            self.assertEqual(E.cross_lifts(lows, [0.0] * 6, wrap=wrap), p)

    def test_both_standing_split(self):
        # his Jog_Bwd: both soles at 0.0 on frame 2, 0.9 mm overlap; each foot takes half, held over its stance
        lows = {"Left": [0.0, 0.0, 0.0, 0.02, 0.04, 0.02], "Right": [0.04, 0.01, 0.0, 0.0, 0.0, 0.0]}
        p = E.cross_pushes(lows, [0.0, 0.0, 0.0059, 0.0, 0.0, 0.0])
        self.assertAlmostEqual(p["Left"][2] + p["Right"][2], 0.0059)
        self.assertEqual(p["Left"][0], p["Left"][2])  # the left stance 0-2 held
        self.assertEqual(set(p["Right"][2:]), {0.00295})  # the right stance 2-5 held
        self.assertEqual(E.cross_slide_mm(lows, p), {"Left": 0.0, "Right": 0.0})

    def test_slide_measured(self):
        lows = {"Left": [0.0, 0.0, 0.0], "Right": [0.05, 0.05, 0.05]}
        self.assertEqual(E.cross_slide_mm(lows, {"Left": [0.0, 0.001, 0.003], "Right": [0.0, 0.02, 0.0]}),
                         {"Left": 3.0, "Right": 0.0})

    def test_a_planted_foot_never_slides(self):
        # Jog_Bwd: the right foot lands into the left shoe on frame 3 and stands on 3-5; the left one lifts
        lows = {"Right": [0.03, 0.02, 0.01, 0.0004, 0.0, 0.0, 0.02, 0.04],
                "Left": [0.0, 0.0, 0.0, 0.0, 0.01, 0.03, 0.0, 0.0]}
        p = E.cross_pushes(lows, [0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(p["Right"][3], p["Right"][4])  # held over the stance
        self.assertEqual(p["Right"][4], p["Right"][5])
        self.assertAlmostEqual(p["Right"][3], 0.0075)  # the eased need reaching the landing
        self.assertAlmostEqual(p["Right"][2], 0.01)
        self.assertAlmostEqual(p["Right"][6], 0.0075 * 0.75)  # eased out in the swing after it
        self.assertEqual(p["Left"], [0.0] * 8)
        self.assertEqual(E.cross_slide_mm(lows, p)["Right"], 0.0)

    def test_capped(self):
        lows = {"Left": [0.0, 0.0], "Right": [0.05, 0.05]}
        self.assertEqual(E.cross_pushes(lows, [0.09, 0.09], reach=0)["Right"], [E.CROSS_MAX_M] * 2)

    def test_crossed_step_lifted_in_the_air_only(self):
        lows = {"Left": [0.0, 0.0, 0.0, 0.0, 0.0], "Right": [0.0, 0.02, 0.04, 0.02, 0.0]}
        lf = E.cross_lifts(lows, [0.0, 0.0, 0.03, 0.0, 0.0])
        self.assertEqual(lf["Left"], [0.0] * 5)
        self.assertEqual(lf["Right"][0], 0.0)  # standing: never lifted
        self.assertEqual(lf["Right"][4], 0.0)
        self.assertAlmostEqual(lf["Right"][2], 0.03)
        self.assertAlmostEqual(lf["Right"][1], 0.0225)
        self.assertEqual(E.cross_lifts(lows, [0.0, 0.0, 0.11, 0.0, 0.0])["Right"], [0.0] * 5)  # an X: left as it is

    def test_settings_key(self):
        self.assertEqual(E.cross_clear_cm(str(SETTINGS), "Walk_Loop"), 0.5)
        self.assertEqual(E.cross_clear_cm(str(SETTINGS), "Strafe_Left__p2_Loop"), 0.5)  # unlisted: [defaults]


if __name__ == "__main__":
    unittest.main()
