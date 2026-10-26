"""The strafe pilot P2's plain parts (art #196): facing, pitch and level_head (alien_stride_math), the absolute orient
and the travel trim, the set's new keys and its [[reel]] plan (alien_loco_math)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_alien_stride_orient import full, skeleton  # noqa: E402
from test_alien_stride_math import S, gait  # noqa: E402
import alien_loco_math as L  # noqa: E402


def looking_down(skel, clip, deg):
    """The clip with its head bowed deg degrees (the crouch's take)."""
    return S.pitch(skel, clip, deg, (("Head", 1.0),))


class Facing(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = full(self.skel, gait(self.skel))

    def test_the_rest_gait_looks_ahead_on_the_aim(self):
        f = S.facing(self.skel, self.clip)
        self.assertLess(abs(f["hips_yaw_deg"]), 0.5)
        self.assertLess(abs(f["head_yaw_deg"]), 0.5)
        self.assertLess(abs(f["head_pitch_deg"]), 0.5)

    def test_orient_reports_the_hips_and_keeps_the_head(self):
        out, _ = S.orient_warp(self.skel, self.clip, 60.0, 90.0)
        f = S.facing(self.skel, out)
        self.assertAlmostEqual(f["hips_yaw_deg"], 60.0, delta=0.5)
        self.assertLess(abs(f["head_yaw_deg"]), 1.0)

    def test_pitch_leans_the_front_down_and_follows_the_children(self):
        out = S.pitch(self.skel, self.clip, 20.0, (("Spine", 1.0),))
        f = S.facing(self.skel, out)
        self.assertAlmostEqual(f["chest_pitch_deg"], -20.0, delta=0.5)
        self.assertAlmostEqual(f["head_pitch_deg"], -20.0, delta=0.5)  # the head rides on the spine
        for b in ("Hips", "LeftFoot", "RightFoot"):  # below the chain: unchanged
            a, c = S.tracks(self.skel, self.clip, [b])[b], S.tracks(self.skel, out, [b])[b]
            self.assertLess(max(math.dist(x, y) for x, y in zip(a, c)), 1e-9, b)

    def test_level_head_brings_the_mean_pitch_to_the_target(self):
        bowed = looking_down(self.skel, self.clip, 45.0)
        self.assertAlmostEqual(S.facing(self.skel, bowed)["head_pitch_deg"], -45.0, delta=0.5)
        for target in (0.0, -5.0, -10.0):
            out, rep = S.level_head(self.skel, bowed, target)
            self.assertAlmostEqual(rep["head_pitch_after_deg"], target, delta=0.2, msg=target)
            self.assertAlmostEqual(rep["head_pitch_before_deg"], -45.0, delta=0.5)
            self.assertAlmostEqual(S.facing(self.skel, out)["chest_pitch_deg"], 0.0, delta=0.5)  # trunk kept


class AbsoluteOrient(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = full(self.skel, gait(self.skel))

    def test_headings_are_absolute_whatever_the_clip_s_own(self):
        # a take turned 20 degrees off the aim, head and all: the head is brought back first, then the hips and travel
        off, _ = S.orient_warp(self.skel, self.clip, 20.0, 20.0, split=())
        out, rep = L.orient(S, self.skel, off, {"hips": 60.0, "travel": 90.0})
        f = S.facing(self.skel, out)
        self.assertAlmostEqual(rep["aim_turn_deg"], -20.0, delta=0.5)
        self.assertAlmostEqual(f["hips_yaw_deg"], 60.0, delta=0.5)
        self.assertLess(abs(f["head_yaw_deg"]), 1.0)
        self.assertAlmostEqual(S.travel_heading_deg(S.measure(self.skel, out)), 90.0, delta=2.0)

    def test_the_trim_turns_the_feet_alone_onto_the_asked_travel(self):
        out0, _ = L.orient(S, self.skel, self.clip, {"hips": 60.0, "travel": 80.0})
        out, rep = L.trim_travel(S, self.skel, out0, 90.0)
        self.assertLess(abs(S._wrap(rep["after_deg"] - 90.0)), 1.0)
        a, b = S.facing(self.skel, out0), S.facing(self.skel, out)
        self.assertAlmostEqual(a["hips_yaw_deg"], b["hips_yaw_deg"], delta=0.1)  # hips and head kept
        self.assertAlmostEqual(a["head_yaw_deg"], b["head_yaw_deg"], delta=0.1)


class SetKeys(unittest.TestCase):
    def test_from_and_orient_pass_through_and_a_from_must_come_first(self):
        cfg = {"clip": [{"name": "A", "source": "x"},
                        {"name": "B", "from": "A", "speeds": [3.0], "orient": {"hips": 60.0, "travel": 90.0},
                         "cadence": 4.0, "head_level": -5.0, "lean_deg": 5.0}]}
        b = {j["name"]: j for j in L.expand(cfg)}["B"]
        self.assertEqual((b["from"], b["orient"]["hips"], b["cadence"], b["head_level"], b["lean_deg"]),
                         ("A", 60.0, 4.0, -5.0, 5.0))
        self.assertEqual(L.sources(L.expand(cfg)), ["x"])
        with self.assertRaises(ValueError):
            L.expand({"clip": [{"name": "B", "from": "A"}]})

    def test_the_real_set_has_the_p2_clips(self):
        jobs = {j["name"]: j for j in L.expand(L.load())}
        for n in ("Strafe_Left__h45", "Strafe_Left__h60", "Strafe_Left__h75", "Strafe_Left__100s", "Strafe_Left__s4b",
                  "Jog_Fwd_Left", "Jog_Fwd_Right", "Jog_Bwd__c20", "Jog_Bwd__c25", "Jog_Bwd__c30", "Jog_Bwd__s4b",
                  "Jog_Bwd_Left", "Jog_Bwd_Right"):
            self.assertIn(n, jobs)
        self.assertEqual(jobs["Strafe_Left"]["from"], "Jog_Fwd")
        self.assertEqual(jobs["Strafe_Left"]["orient"]["travel"], 90.0)
        self.assertEqual(jobs["Jog_Bwd"]["speed"], jobs["Jog_Bwd__c25"]["speed"])  # the 2.5 until he picks
        self.assertEqual(jobs["Jog_Bwd_Right"]["mirror"], "Jog_Bwd_Left")
        self.assertIsNotNone(jobs["Crouch_Run"]["head_level"])
        for n in ("Walk", "Jog_Fwd", "Sprint_Fwd"):  # approved: no P2 edit on them
            self.assertFalse(any(jobs[n].get(k) for k in ("orient", "head_level", "lean_deg", "cadence")), n)


class ReelPlan(unittest.TestCase):
    def test_explicit_reels_one_per_view(self):
        cfg = L.load()
        plan = {r["name"]: r for r in L.reel_plan(L.expand(cfg), cfg["reel"])}
        for v in ("front", "three_quarter", "back"):
            self.assertIn(f"Strafe_Left__{v}", plan)
            self.assertIn(f"Diagonal_45__{v}", plan)
        self.assertEqual(plan["Diagonal_45__front"]["clips"][0]["travel"], 45.0)
        with self.assertRaises(ValueError):
            L.reel_plan(L.expand(cfg), [{"name": "x", "views": ["front"], "clips": [{"clip": "Nope", "speed": 1.0}]}])
        with self.assertRaises(ValueError):
            L.reel_plan(L.expand(cfg), [{"name": "x", "views": ["top"], "clips": [{"clip": "Walk", "speed": 1.0}]}])

    def test_a_travel_sets_the_stripes_against_it(self):
        info = {"fps": 24.0, "frames": 24, "v0": 3.0, "ground": [-3.0, 0.0], "hips": [0.0, 0.0],
                "contacts": {"Left": [0], "Right": [12]}}
        cfg = L.load()
        self.assertEqual(L.reel_timeline(info, 3.0, 2.0, cfg)["dir"], [-1.0, 0.0])
        d = L.reel_timeline(info, 3.0, 2.0, cfg, travel_deg=45.0)["dir"]
        self.assertAlmostEqual(d[0], -math.sqrt(0.5), places=4)  # the ground runs back and right under a front-left
        self.assertAlmostEqual(d[1], -math.sqrt(0.5), places=4)  # travel (Godot: the character faces +Z, left +X)
        d = L.reel_timeline(info, 3.0, 2.0, cfg, travel_deg=0.0)["dir"]
        self.assertAlmostEqual(d[1], -1.0)


if __name__ == "__main__":
    unittest.main()
