"""The pure math of the clip edits (tools/blender/anim_edit_math.py, art #33) on synthetic data; no Blender needed."""

from __future__ import annotations

import math
import random
import sys
import unittest

from runner import common

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import anim_edit_math as em  # noqa: E402

FPS = 30


class CheckStepsTest(unittest.TestCase):
    def test_good_steps_pass(self) -> None:
        steps = [
            {"op": "heading", "travel": "back"},
            {"op": "cycle", "min_s": 0.6, "max_s": 1.0, "within": [0.3, 3.7]},
            {"op": "stride", "speed_m_s": 4.5, "cadence": 2.8},
            {"op": "retime", "speed_m_s": 7, "natural_m_s": 9.0},
            {"op": "trim", "start_s": 0.13, "end_s": 1.73},
            {"op": "turn", "total_deg": 90},
            {"op": "mirror"}, {"op": "reverse"},
            {"op": "floor", "mode": "hips", "from_s": 1.2},
            {"op": "in_place", "mode": "path", "smooth_s": 0.5},
            {"op": "arm_offset", "abduct_deg": "auto", "body": "women"},
            {"op": "hand_spacing", "gap_m": 0.4, "at": "mean"},
            {"op": "hand_spacing", "min_gap_cm": 1.0, "deg": 4.5},
        ]
        self.assertEqual(em.check_steps(steps), [])

    def test_bad_steps_are_named(self) -> None:
        cases = [
            ({"op": "explode"}, "unknown op"),
            ({"op": "trim", "start_s": 0.1, "stop": 1}, "unknown parameter 'stop'"),
            ({"op": "retime"}, "exactly one of seconds, rate, speed_m_s"),
            ({"op": "retime", "seconds": 1.0, "rate": 1.2}, "exactly one of seconds, rate, speed_m_s"),
            ({"op": "retime", "rate": "fast"}, "rate must be a number"),
            ({"op": "retime", "rate": True}, "rate must be a number"),
            ({"op": "retime", "rate": 0}, "rate must be > 0"),
            ({"op": "stride", "speed_m_s": 4.5}, "exactly one of cadence, rate"),
            ({"op": "stride", "cadence": 2.8}, "missing 'speed_m_s'"),
            ({"op": "cycle", "min_s": 1.0}, "missing 'max_s'"),
            ({"op": "cycle", "min_s": 1.0, "max_s": 2.0, "within": [3, 1]}, "within must be a range"),
            ({"op": "heading"}, "exactly one of travel, facing"),
            ({"op": "heading", "travel": "up"}, "travel must be a string"),
            ({"op": "mirror", "body": "kids"}, "body must be one of"),
            ({"op": "trim", "start_s": 1.0, "end_s": 0.5}, "end_s must be after start_s"),
            ({"op": "arm_offset", "abduct_deg": "some"}, "abduct_deg must be a number_or_auto"),
            ({"op": "arm_offset", "axis": "back"}, "axis must be a string in ['out', 'swing']"),
            ({"op": "hand_spacing", "gap_m": 0.4, "min_gap_cm": 1}, "exactly one of min_gap_cm, gap_m"),
        ]
        for step, text in cases:
            with self.subTest(step=step):
                errors = em.check_steps([step])
                self.assertTrue(any(text in e for e in errors), errors)
        self.assertEqual(em.check_steps("trim"), ["the edits must be a list of steps"])
        self.assertIn("step 2", em.check_steps([{"op": "mirror"}, {"op": "nope"}])[0])

    def test_params_fill_defaults(self) -> None:
        p = em.params({"op": "cycle", "min_s": 1, "max_s": 2, "body": "men"})
        self.assertEqual((p["max_raw_seam_deg"], p["within"]), (15.0, None))
        self.assertNotIn("body", p)


class TimeMapTest(unittest.TestCase):
    def test_trim_indices(self) -> None:
        t = em.trim_times(120, FPS, 0.13, 1.73)  # the turn: 48 frames from frame 3.9
        self.assertEqual(len(t), 49)
        self.assertAlmostEqual(t[0], 3.9)
        self.assertAlmostEqual(t[-1], 51.9)
        self.assertEqual(em.trim_times(30, FPS, 0.5)[-1], 30.0)  # to the end
        self.assertEqual(len(em.trim_times(30, FPS, 0.5, 9.0)), 16)  # an end past the clip stops at the end
        with self.assertRaises(ValueError):
            em.trim_times(30, FPS, 2.0, 3.0)

    def test_retime_open_and_closed(self) -> None:
        m, eff = em.retime_count(28, 2.8 / (2 * FPS / 28))  # the Jog: 28 frames, 2.14 steps/s to 2.8
        self.assertEqual((m, round(eff, 3)), (21, 1.333))
        times = em.retime_times(28, 21)
        self.assertEqual((times[0], times[-1], len(times)), (0.0, 28.0, 22))  # a closed loop stays closed
        self.assertAlmostEqual(times[1], 28 / 21)
        m, eff = em.retime_count(60, 60 / 40.5)  # an open clip: whole frames, the ends kept
        self.assertEqual(m, 40)
        self.assertAlmostEqual(eff, 1.5)
        self.assertEqual(em.retime_times(60, 40)[-1], 60.0)
        self.assertEqual(em.split_index(27.5, 28), (27, 0.5))
        self.assertEqual(em.neighbours(0, 28, closed=True), (27, 0, 1, 2))  # over a loop's seam
        self.assertEqual(em.neighbours(27, 28, closed=True), (26, 27, 28, 1))
        self.assertEqual(em.neighbours(27, 28, closed=False), (26, 27, 28, 28))

    def test_catmull_rom(self) -> None:
        for f in (0.0, 0.25, 0.5, 0.9):
            w = em.catmull_rom(f)
            self.assertAlmostEqual(sum(w), 1.0)
            self.assertAlmostEqual(sum(wk * x for wk, x in zip(w, (-1, 0, 1, 2))), f)  # a straight line stays
        self.assertEqual(em.catmull_rom(0.0), (0.0, 1.0, 0.0, 0.0))
        w = em.catmull_rom(0.5)  # a sine between samples: far closer than the linear blend
        xs = [math.sin(0.4 * k) for k in (-1, 0, 1, 2)]
        exact = math.sin(0.2)
        self.assertLess(abs(sum(a * b for a, b in zip(w, xs)) - exact), abs((xs[1] + xs[2]) / 2 - exact) / 3)
        self.assertEqual(em.split_index(28.0, 28), (27, 1.0))


class QuaternionTest(unittest.TestCase):
    def test_slerp_and_hemisphere(self) -> None:
        a = em.q_axis_angle((0, 0, 1), 10)
        b = em.q_axis_angle((0, 0, 1), 50)
        mid = em.q_slerp(a, tuple(-c for c in b), 0.5)  # b on the other hemisphere: still the short way
        self.assertAlmostEqual(em.q_angle(mid, em.q_axis_angle((0, 0, 1), 30)), 0.0, places=4)
        self.assertEqual(em.q_hemi((-1.0, 0, 0, 0), (1.0, 0, 0, 0)), (1.0, 0, 0, 0))
        v = em.q_rotate(em.q_axis_angle((0, 0, 1), 90), (1.0, 0.0, 0.0))
        for got, want in zip(v, (0.0, 1.0, 0.0)):
            self.assertAlmostEqual(got, want)


def sines(period_s: float, seconds: float, noise: float, seed: int = 1) -> list:
    rng = random.Random(seed)
    out = []
    for i in range(int(seconds * FPS) + 1):
        t = i / FPS
        w = 2 * math.pi * t / period_s
        out.append([math.sin(w) + rng.gauss(0, noise), math.cos(w) + rng.gauss(0, noise),
                    0.5 * math.sin(2 * w + 0.3) + rng.gauss(0, noise)])
    return out


class CycleTest(unittest.TestCase):
    def test_best_cycle_finds_the_period(self) -> None:
        for period, lo, hi in ((1.33, 1.0, 2.0), (0.93, 0.6, 1.2)):
            with self.subTest(period=period):
                f = sines(period, 4.0, 0.01)
                i, j, _ = em.best_cycle(f, [[c * 3 for c in v] for v in em.central_diff(f)], FPS, lo, hi)
                self.assertLessEqual(abs((j - i) - period * FPS), 1.0, (i, j))

    def test_best_cycle_respects_within(self) -> None:
        f = sines(1.33, 4.0, 0.01, seed=2)
        i, j, _ = em.best_cycle(f, em.central_diff(f), FPS, 1.0, 2.0, within=[2.0, 3.9])
        self.assertGreaterEqual(i, 60)
        self.assertLessEqual(j, 117)
        with self.assertRaises(ValueError):
            em.best_cycle(f, em.central_diff(f), FPS, 1.0, 2.0, within=[3.0, 3.5])

    def test_closing_ramps(self) -> None:
        pts = [(0.1 * k, 0.0, 1.0 + 0.01 * k) for k in range(11)]
        closed = em.close_vectors(pts)
        self.assertEqual(closed[0], pts[0])
        for a, b in zip(closed[-1], closed[0]):
            self.assertAlmostEqual(a, b)
        qs = [em.q_axis_angle((0, 0, 1), 3 * k) for k in range(11)]
        cq = em.close_quats(qs)
        self.assertAlmostEqual(em.q_angle(cq[0], qs[0]), 0.0, places=4)
        self.assertAlmostEqual(em.q_angle(cq[-1], cq[0]), 0.0, places=3)
        self.assertAlmostEqual(em.q_angle(cq[5], em.q_axis_angle((0, 0, 1), 0)), 0.0, places=3)  # 15 - 30 * 5/10


class PathTest(unittest.TestCase):
    def test_linear_drift_and_moving_average(self) -> None:
        pts = [(0.0, -0.1 * k) for k in range(11)]
        drift = em.linear_drift(pts)
        self.assertEqual(drift[0], (0.0, 0.0))
        self.assertAlmostEqual(drift[-1][1], -1.0)
        self.assertAlmostEqual(drift[5][1], -0.5)
        avg = em.moving_average([(float(k % 2),) for k in range(10)], 1)
        self.assertAlmostEqual(avg[4][0], 2 / 3)  # (1 + 0 + 1) / 3 at an even index
        self.assertAlmostEqual(avg[0][0], 0.5)  # the window shrinks at the ends
        off = em.path_offsets([(0.0, -0.1 * k) for k in range(31)], FPS, 0.2)
        self.assertEqual(off[0], (0.0, 0.0))
        self.assertAlmostEqual(off[15][1], -1.5, places=6)
        self.assertAlmostEqual(em.moving_speed([(0.0, -0.1 * k) for k in range(31)], FPS), 3.0)

    def test_least_squares_direction_and_angles(self) -> None:
        rng = random.Random(3)
        ang = math.radians(19.8)  # the crawl heads 19.8 degrees to its left of straight
        times = [i / FPS for i in range(120)]
        pts = [(0.82 * t * math.sin(ang) + rng.gauss(0, 0.01), -0.82 * t * math.cos(ang) + rng.gauss(0, 0.01))
               for t in times]
        d, speed = em.lsq_direction(pts, times)
        self.assertAlmostEqual(em.yaw_of(d), 19.8, delta=0.3)
        self.assertAlmostEqual(speed, 0.82, delta=0.01)
        self.assertAlmostEqual(em.signed_angle_2d((0, -1), (1, 0)), 90.0)
        self.assertEqual((em.yaw_of((1, 0)), em.yaw_of((0, 1)), em.yaw_of((-1, 0))), (90.0, 180.0, -90.0))
        self.assertEqual(em.wrap(270.0), -90.0)
        self.assertEqual(em.unwrap([170.0, -170.0, -150.0]), [170.0, 190.0, 210.0])
        self.assertAlmostEqual(em.circular_mean([170.0, -170.0]), 180.0)
        # facing: upright, bent forward on all fours (forward axis points down) and lying on the back
        self.assertAlmostEqual(em.facing_yaw((0, -1, 0), (1, 0, 0)), 0.0)
        self.assertAlmostEqual(em.facing_yaw((0, 0, -1), (1, 0, 0)), 0.0)
        self.assertAlmostEqual(em.facing_yaw((0, 0, 1), (0, 1, 0)), 90.0)

    def test_turn_correction(self) -> None:
        yaws = [109.0 * min(1.0, k / 30) for k in range(40)]
        corr = em.turn_correction(yaws, 90.0)
        self.assertEqual(corr[0], 0.0)
        self.assertAlmostEqual(yaws[-1] + corr[-1], 90.0)
        self.assertAlmostEqual(yaws[15] + corr[15], 45.0)
        with self.assertRaises(ValueError):
            em.turn_correction([0.0, 0.3], 90.0)


class StrideTest(unittest.TestCase):
    def test_stride_numbers(self) -> None:
        # UAL's Jog_Fwd_Loop on the men: 28 frames (0.93 s), one contact window per foot, 5.95 m/s in place
        mask = [i < 9 for i in range(28)]
        self.assertEqual(em.contact_windows(mask, cyclic=True), [list(range(9))])
        c0 = em.natural_cadence(2, 28 / FPS)
        self.assertAlmostEqual(c0, 2.14, places=2)
        m, eff = em.stride_rate(28, c0, cadence=2.8)
        self.assertEqual((m, round(eff, 3)), (21, 1.333))
        s = em.stride_scale(4.5, eff, 5.95)
        self.assertAlmostEqual(s, 0.567, places=3)
        self.assertEqual(em.stride_fit(s), "warn")
        self.assertAlmostEqual(4.5 / (c0 * eff), 1.575, places=2)  # the step at 4.5 m/s
        self.assertEqual(em.stride_fit(1.0), "ok")
        self.assertEqual(em.stride_fit(1.5), "ok")
        # the backward jog jogs almost in place (0.29 to 0.5 m/s): about 8x longer steps, beyond the limit
        m, eff = em.stride_rate(30, 2.6, cadence=2.8)
        self.assertEqual(em.stride_fit(em.stride_scale(4.5, eff, 0.5)), "fail")
        self.assertEqual(em.stride_rate(28, c0, rate=1.0), (28, 1.0))

    def test_contact_windows_wrap_in_a_loop(self) -> None:
        mask = [True, True, False, False, True, False, True]
        self.assertEqual(em.contact_windows(mask, cyclic=True), [[6, 0, 1], [4]])
        self.assertEqual(em.contact_windows(mask, cyclic=False), [[0, 1], [4], [6]])
        feet = {"L": [(0.0, 0.1 * i, 0.02) for i in range(10)], "R": [(0.2, 0.1 * i, 0.3) for i in range(10)]}
        v = em.ground_velocity(em.contact_velocities(feet, FPS))
        self.assertAlmostEqual(v[1], 3.0)

    def test_foot_scaling_along_an_axis(self) -> None:
        o = em.scale_offset((0.1, 0.8), (0.0, 1.0), 0.5)
        self.assertEqual(o, (0.1, 0.4))  # across the axis unchanged
        o = em.scale_offset((0.3, 0.3), (math.sqrt(0.5), math.sqrt(0.5)), 2.0)
        self.assertAlmostEqual(o[0], 0.6)

    def test_plant_line(self) -> None:
        pts = [(0.01 * (i % 3), 0.1 * i + 0.002 * i * i) for i in range(20)]  # a sliding, wobbling contact
        win = list(range(5, 12))
        out = em.plant(pts, [win], (0.0, 3.0), FPS, blend=2, cyclic=False)
        anchor = pts[8]
        for i in win:  # a straight line at the ground's 3 m/s, through the window's middle
            self.assertAlmostEqual(out[i][1], anchor[1] + 0.1 * (i - 8))
            self.assertAlmostEqual(out[i][0], anchor[0])
        self.assertEqual(out[0], pts[0])
        line3 = anchor[1] + 0.1 * (3 - 8)
        self.assertAlmostEqual(out[3][1], pts[3][1] + (line3 - pts[3][1]) / 3)  # 2 frames before: a third of the way
        out = em.plant(pts[:10], [[8, 9, 0, 1]], (0.0, 3.0), FPS, blend=1, cyclic=True)  # over a loop's seam
        self.assertAlmostEqual(out[0][1] - out[9][1], 0.1)


class IkTest(unittest.TestCase):
    def test_reachable_goal(self) -> None:
        H, K, A = (0.0, 0.0, 1.0), (0.0, -0.05, 0.55), (0.0, 0.0, 0.1)
        goal = (0.1, -0.2, 0.3)
        K2, A2, miss = em.two_bone_ik(H, K, A, goal, (0.0, -1.0, 0.0))
        self.assertLess(miss, 1e-9)
        for a, b in zip(A2, goal):
            self.assertAlmostEqual(a, b)
        self.assertAlmostEqual(math.dist(H, K2), math.dist(H, K))
        self.assertAlmostEqual(math.dist(K2, A2), math.dist(K, A))
        self.assertLess(K2[1], -0.1)  # bent towards the pole (the front)

    def test_unreachable_goal(self) -> None:
        H, K, A = (0.0, 0.0, 1.0), (0.0, -0.05, 0.55), (0.0, 0.0, 0.1)
        L = math.dist(H, K) + math.dist(K, A)
        goal = (0.0, 0.0, -0.2)
        K2, A2, miss = em.two_bone_ik(H, K, A, goal, (0.0, -1.0, 0.0))
        self.assertAlmostEqual(miss, 1.2 - L, places=5)
        self.assertLess(abs(K2[1]), 0.002)  # straight (to the reach limit of 1e-6 of the leg)
        self.assertAlmostEqual(A2[2], 1.0 - L, places=5)


class FloorTest(unittest.TestCase):
    def test_floor_profile(self) -> None:
        depths = [0.0] * 30
        depths[15] = 0.04  # one frame 4 cm deep
        lift = em.floor_profile(depths, 10, 29, fade=3)
        self.assertAlmostEqual(lift[15], 0.04)  # the running max and the smoothing keep the peak
        self.assertGreater(lift[14], 0.0)
        self.assertEqual(lift[0], 0.0)
        depths = [0.0] * 10 + [0.03] * 20
        lift = em.floor_profile(depths, 10, 29, fade=3)
        self.assertAlmostEqual(lift[10], 0.03)
        self.assertAlmostEqual(lift[9], 0.03 * 0.75)  # faded in before the window
        self.assertAlmostEqual(lift[7], 0.0075)
        self.assertEqual(lift[6], 0.0)
        for i in range(10, 30):
            self.assertGreaterEqual(lift[i] + 1e-12, depths[i])


class SearchTest(unittest.TestCase):
    def test_angle_search(self) -> None:
        calls = []

        def ok(a):
            calls.append(a)
            return a >= 6.3

        angle, found = em.search_angle(ok, 0.0, 12.0, 0.5)
        self.assertTrue(found)
        self.assertTrue(6.3 <= angle <= 6.8)
        self.assertLess(len(calls), 10)
        self.assertEqual(em.search_angle(lambda a: True, 0.0, 12.0), (0.0, True))
        self.assertEqual(em.search_angle(lambda a: False, 0.0, 12.0), (12.0, False))


def rot_x(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]]


def from_quat(q, t=(0, 0, 0)):
    w, x, y, z = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y), t[0]],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x), t[1]],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y), t[2]], [0, 0, 0, 1]]


class MirrorTest(unittest.TestCase):
    def setUp(self) -> None:
        # an armature space turned like ours (the RootNode's -90 degrees about X) and scaled 100
        W = [[100 * v for v in row[:3]] + [row[3]] for row in rot_x(-90)]
        self.S = em.mat_mul(em.mat_mul(em.mat_inv(W), [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]), W)
        rng = random.Random(5)
        self.rest = {
            "Arm.L": from_quat(em.q_axis_angle((0.2, 1, 0.1), 40), (0.002, 0.014, 0.0)),
            "Arm.R": from_quat(em.q_axis_angle((-0.3, 0.2, 1), -70), (-0.0021, 0.014, 0.0)),  # another roll
            "Spine": from_quat(em.q_axis_angle((1, 0, 0), 5), (0.0, 0.01, 0.0)),
        }
        self.pose = {n: from_quat(em.q_norm(tuple(rng.uniform(-1, 1) for _ in range(4))),
                                  tuple(rng.uniform(-0.01, 0.01) for _ in range(3))) for n in self.rest}
        self.pairs = em.mirror_pairs(self.rest)
        self.C = {b: em.mirror_correction(self.S, self.rest[b], self.rest[m]) for b, m in self.pairs.items()}

    def mirror(self, pose):
        return {b: em.mirror_pose(self.S, pose[m], self.C[b]) for b, m in self.pairs.items()}

    def assertSame(self, a, b, places=9):
        for ra, rb in zip(a, b):
            for x, y in zip(ra, rb):
                self.assertAlmostEqual(x, y, places=places)

    def test_pairs(self) -> None:
        self.assertEqual(self.pairs, {"Arm.L": "Arm.R", "Arm.R": "Arm.L", "Spine": "Spine"})
        with self.assertRaises(ValueError):
            em.mirror_pairs(["Arm.L", "Spine"])

    def test_mirror_twice_is_identity_and_rest_is_kept(self) -> None:
        twice = self.mirror(self.mirror(self.pose))
        for n in self.rest:
            self.assertSame(twice[n], self.pose[n])
        rest = self.mirror(self.rest)
        for n in self.rest:
            self.assertSame(rest[n], self.rest[n])

    def test_a_proper_rotation(self) -> None:
        for m in self.mirror(self.pose).values():
            self.assertAlmostEqual(em.det3(m), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
