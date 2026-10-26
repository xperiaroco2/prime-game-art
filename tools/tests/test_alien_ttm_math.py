"""The text-to-motion candidates' pure measures on the alien (tools/blender/alien_ttm_math.py, art #196 option A step
2) on step 1's synthetic biped: directions and yaw wobble, the torso and the hands, the soles and the floor fit, the
loop bounds, the faults and the ranking per slot, no Blender."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_stride_math as S  # noqa: E402
import alien_ttm_math as T  # noqa: E402
from test_alien_stride_math import skeleton  # noqa: E402

M = S.M
Z = (0.0, 0.0, 1.0)


def clip(n=24, hips=None, hips_rot=None, extra=None) -> dict:
    """A clip of n intervals at 24 fps: the Hips' basis location and rotation per frame, other bones at rest."""
    hips = hips or (lambda f: (0.0, 0.0, 0.0))
    hips_rot = hips_rot or (lambda f: (1.0, 0.0, 0.0, 0.0))
    c = {"name": "t", "fps": 24, "loc": {"Hips": [hips(f) for f in range(n + 1)]},
         "rot": {"Hips": [hips_rot(f) for f in range(n + 1)]}}
    for b, (loc, rot) in (extra or {}).items():
        c["loc"][b] = [loc(f) for f in range(n + 1)]
        c["rot"][b] = [rot(f) for f in range(n + 1)]
    return c


def good(slot="jog", **over) -> dict:
    c = {"slot": slot, "v0": 4.5, "c0": 2.2, "travel_deg": T.SLOTS[slot][0], "yaw_wobble_deg": 4.0,
         "seam_cut_deg": 3.0, "foot_slide_mm": {"Left": 5.0, "Right": 5.0}, "floor_min_mm": -2.0,
         "floor_planted_mm": 0.0, "floor_drift_mm": 5.0, "hands_cm": {"Left": -3.0, "Right": -4.0},
         "steps_in_loop": 2, "hips_height": 0.95}
    c.update(over)
    return c


class Angles(unittest.TestCase):
    def test_wrap_and_yaw(self):
        self.assertAlmostEqual(T.wrap(190.0), -170.0)
        self.assertAlmostEqual(T.wrap(-180.0), 180.0)
        self.assertAlmostEqual(T.yaw((0.0, -1.0)), 0.0)  # the front
        self.assertAlmostEqual(T.yaw((1.0, 0.0)), 90.0)  # the character's left
        self.assertAlmostEqual(abs(T.yaw((0.0, 1.0))), 180.0)

    def test_unwrap(self):
        self.assertEqual([round(a) for a in T.unwrap([170.0, -170.0, -150.0])], [170, 190, 210])

    def test_facing_follows_a_turn_to_the_left(self):
        sk = skeleton()
        c = clip(hips_rot=lambda f: M.q_axis_angle(Z, 30.0 + f))
        face = T.facing(sk, c)
        self.assertAlmostEqual(face[0], 30.0, places=6)
        self.assertAlmostEqual(face[-1], 54.0, places=6)

    def test_direction_of_a_strafe_and_a_backward_run(self):
        sk = skeleton()
        c = clip(hips_rot=lambda f: M.q_axis_angle(Z, 3.0 * math.sin(f / 24 * 2 * math.pi)))
        left = T.direction(sk, c, {"hips_m_s": (1.0, 0.0), "ground_m_s": (0.0, 0.0)})
        self.assertAlmostEqual(left["travel_deg"], 90.0, delta=0.5)
        self.assertAlmostEqual(left["yaw_wobble_deg"], 6.0, delta=0.1)
        back = T.direction(sk, c, {"hips_m_s": (0.2, 2.0), "ground_m_s": (0.2, 0.0)})
        self.assertAlmostEqual(abs(back["travel_deg"]), 180.0, delta=0.5)
        still = T.direction(sk, c, {"hips_m_s": (0.0, 0.0), "ground_m_s": (0.0, 0.0)})
        self.assertIsNone(still["travel_deg"])


class Torso(unittest.TestCase):
    def test_ellipse(self):
        self.assertAlmostEqual(T.ellipse_inside_cm(0.0, 0.0, 0.2, 0.1), 10.0)
        self.assertAlmostEqual(T.ellipse_inside_cm(0.2, 0.0, 0.2, 0.1), 0.0, places=9)
        self.assertAlmostEqual(T.ellipse_inside_cm(0.0, -0.15, 0.2, 0.1), -5.0, places=9)

    def test_shape_and_hands(self):
        pts = [(0.15 * math.cos(a / 10), 0.1 * math.sin(a / 10), z / 10) for a in range(63) for z in range(9, 15)]
        shape = T.torso_shape(pts)
        self.assertAlmostEqual(shape["a"], 0.15, delta=0.01)
        self.assertAlmostEqual(shape["b"], 0.1, delta=0.01)
        rest, parent = {}, {}
        for name, head, par in (("Root", (0, 0, 0), None), ("Hips", (0, 0, 0.9), "Root"),
                                ("Chest", (0, 0, 1.1), "Hips")):
            rest[name], parent[name] = S.m4(head, (1.0, 0.0, 0.0, 0.0)), par
        for side, sx in (("Left", 1.0), ("Right", -1.0)):  # hands hung straight from the chest, 0.7 m out
            for part, dx in (("Hand", 0.0), ("MiddleProximal", 0.08), ("MiddleDistal", 0.12)):
                rest[f"{side}{part}"] = S.m4((sx * (0.7 + dx), 0.0, 1.4), (1.0, 0.0, 0.0, 0.0))
                parent[f"{side}{part}"] = "Chest" if part == "Hand" else f"{side}Hand"
        sk = S.prepare({"rest": rest, "parent": parent})
        shape["z1"] = 1.3
        self.assertEqual(T.hands_into_torso(sk, clip(), shape), {"Left": None, "Right": None})  # above the band
        shape["z1"] = 1.5
        far = T.hands_into_torso(sk, clip(), shape)
        self.assertAlmostEqual(far["Left"], -55.0, delta=0.5)  # the wrist 0.7 m out, the half-width 0.15 m
        # the left hand moved to 5 cm left of the middle, 20 cm lower: 10 cm inside; the chest turned 90 degrees
        # about Z carries it along, so read in the chest's rest frame it stays 10 cm inside
        c = clip(extra={"LeftHand": (lambda f: (-0.65, 0.0, -0.2), lambda f: (1.0, 0.0, 0.0, 0.0)),
                        "Chest": (lambda f: (0.0, 0.0, 0.0), lambda f: M.q_axis_angle(Z, 90.0))})
        near = T.hands_into_torso(sk, c, shape)
        self.assertAlmostEqual(near["Left"], 10.0, delta=0.5)


class Floor(unittest.TestCase):
    def test_soles_fit_and_drift(self):
        sk = skeleton()
        soles = {"LeftFoot": [(0.0, 0.0, -0.1)], "RightFoot": [(0.0, 0.0, -0.1)]}  # 10 cm under the ankles
        c = clip(hips=lambda f: (0.0, 0.0, 0.03))  # the whole body 3 cm up: a hover
        h = T.sole_heights(sk, c, soles)
        self.assertAlmostEqual(h[0], 0.03, places=9)
        self.assertAlmostEqual(T.floor_fit(h), 0.03, places=9)
        fixed = T.shift_hips(sk, c, -T.floor_fit(h))
        self.assertAlmostEqual(T.floor(T.sole_heights(sk, fixed, soles))["floor_planted_mm"], 0.0, places=6)
        rising = clip(n=72, hips=lambda f: (0.0, 0.0, f / 72 * 0.06))
        self.assertAlmostEqual(T.floor_drift(T.sole_heights(sk, rising, soles), 24), 0.04, delta=0.002)

    def test_shift_hips_with_a_turned_rest(self):
        # a Blender bone's rest points its Y axis along the bone: the Hips' rest is turned 90 degrees about X
        rest = {"Root": S.m4((0, 0, 0), (1.0, 0.0, 0.0, 0.0)),
                "Hips": S.m4((0.0, 0.0, 0.9), M.q_axis_angle((1.0, 0.0, 0.0), 90.0))}
        sk = S.prepare({"rest": rest, "parent": {"Root": None, "Hips": "Root"}})
        up = T.shift_hips(sk, clip(), 0.05)
        self.assertEqual([round(x, 9) for x in S.pos(S.fk(sk, up, 3)["Hips"])], [0.0, 0.0, 0.95])

    def test_a_cut_loop_keeps_its_travel_with_a_turned_rest(self):
        # alien_stride_math._close (step 1's cycle): the Hips' basis z is the floor's -Y when its rest is turned 90
        # degrees about X; a forward run's travel there is kept, only its wobble beside the trend closed
        rest = {"Root": S.m4((0, 0, 0), (1.0, 0.0, 0.0, 0.0)),
                "Hips": S.m4((0.0, 0.0, 0.9), M.q_axis_angle((1.0, 0.0, 0.0), 90.0))}
        sk = S.prepare({"rest": rest, "parent": {"Root": None, "Hips": "Root"}})
        c = clip(hips=lambda f: (0.0, 0.02 * math.sin(f / 24 * 6.28) + 0.01 * f / 24, 0.2 * f / 24))
        out = S._close(c, 0, 24, sk)
        a, b = (S.pos(S.fk(sk, out, f)["Hips"]) for f in (0, 24))
        self.assertAlmostEqual(b[1] - a[1], -0.2, places=9)  # the travel along the front, kept
        self.assertAlmostEqual(b[2] - a[2], 0.0, places=9)  # the height drift, closed
        lost = S._close(c, 0, 24)  # read as if the basis were the floor's axes: the travel would be closed away
        self.assertAlmostEqual(lost["loc"]["Hips"][24][2], lost["loc"]["Hips"][0][2], places=9)

    def test_hips_height_and_loop_bounds(self):
        sk = skeleton()
        self.assertAlmostEqual(T.hips_height(sk, clip(hips=lambda f: (0.0, 0.0, -0.27))), 0.7)
        self.assertEqual(T.loop_bounds(2.0, (0.5, 1.8)), (0.75, 1.3))
        self.assertEqual(T.loop_bounds(None, (0.5, 1.8)), (0.5, 1.8))


class Ranking(unittest.TestCase):
    def test_a_clean_candidate_has_no_fault(self):
        f, s = T.faults(good(), "jog")
        self.assertEqual(f, [])
        self.assertLess(s, 3.0)

    def test_faults_are_named(self):
        f, _ = T.faults(good("strafe", travel_deg=50.0, hands_cm={"Left": 2.0, "Right": -1.0}, steps_in_loop=1,
                             v0=1.0), "strafe")
        text = " ".join(f)
        for word in ("40 deg off", "2.0 cm into the torso", "1 steps", "rate 4.50"):
            self.assertIn(word, text)
        f, _ = T.faults(good("crouch", hips_height=0.97, v0=2.8), "crouch")
        self.assertTrue(any("not a crouch" in x for x in f))
        self.assertEqual(T.faults(good(c0=None), "jog"), (["no steps or no travel found"], 99.0))

    def test_rank_per_slot(self):
        r = T.rank({"a": good(), "b": good(travel_deg=40.0), "c": good("backward", travel_deg=-178.0)})
        self.assertEqual([x[0] for x in r["jog"]], ["a", "b"])
        self.assertEqual([x[0] for x in r["backward"]], ["c"])
        self.assertEqual(r["backward"][0][2], [])


if __name__ == "__main__":
    unittest.main()
