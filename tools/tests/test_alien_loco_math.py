"""The alien locomotion set's plain parts (tools/blender/alien_loco_math.py, art #196 option A step 3)."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_loco_math as L  # noqa: E402

CFG = L.load()


class SetFile(unittest.TestCase):
    def setUp(self):
        self.jobs = L.expand(CFG)
        self.names = [j["name"] for j in self.jobs]

    def test_the_game_slots_are_made(self):
        for n in ("Walk", "Jog_Fwd", "Sprint_Fwd", "Crouch_Fwd", "Crouch_Run", "Strafe_Left", "Strafe_Right",
                  "Jog_Bwd"):
            self.assertIn(n, self.names)

    def test_the_jog_grid_is_six_variants_and_a_picked_default_after_them(self):
        grid = [j for j in self.jobs if j.get("grid") == "Jog_Fwd"]
        self.assertEqual(len(grid), 6)
        self.assertEqual({(j["arm_swing"], j["frames"]) for j in grid},
                         {(k, f) for k in (1.0, 0.75, 0.6) for f in (22, 21)})
        pick = self.jobs[self.names.index("Jog_Fwd")]
        self.assertEqual(pick["pick"], [j["name"] for j in grid])
        self.assertGreater(self.names.index("Jog_Fwd"), max(self.names.index(j["name"]) for j in grid))

    def test_speeds_and_mirrors_name_their_variants(self):
        self.assertEqual(L.speed_name("Jog_Bwd", 3.0, False), "Jog_Bwd__s30")
        self.assertEqual(L.speed_name("Strafe_Left__shuffle", 3.0, False), "Strafe_Left__shuffle_s30")
        self.assertEqual(L.speed_name("Jog_Bwd", 4.5, True), "Jog_Bwd")
        right = {j["name"]: j for j in self.jobs if j["base"] == "Strafe_Right"}
        self.assertEqual(right["Strafe_Right"]["mirror"], "Strafe_Left")
        self.assertEqual(right["Strafe_Right__s30"]["mirror"], "Strafe_Left__s30")
        self.assertEqual(right["Strafe_Right__s30"]["speed"], 3.0)
        for j in self.jobs:  # a mirror comes after the clip it mirrors
            if j.get("mirror"):
                self.assertLess(self.names.index(j["mirror"]), self.names.index(j["name"]))

    def test_a_mirror_of_an_unmade_clip_and_a_doubled_name_are_refused(self):
        with self.assertRaises(ValueError):
            L.expand({"clip": [{"name": "Strafe_Right", "mirror": "Strafe_Left"}]})
        with self.assertRaises(ValueError):
            L.expand({"clip": [{"name": "A", "source": "x"}, {"name": "A", "source": "y"}]})


class GameNumbers(unittest.TestCase):
    def test_the_footstep_interval_matches_the_game_clock(self):
        self.assertAlmostEqual(L.footstep_interval(4.5, CFG), 0.45)
        self.assertAlmostEqual(L.footstep_interval(7.0, CFG), 0.32)
        self.assertAlmostEqual(L.footstep_interval(3.0, CFG), 4.5 * 0.45 / 3.0)  # under the walk: the walk's stride
        self.assertEqual(L.footstep_interval(0.0, CFG), math.inf)

    def test_play_rows_give_the_rate_and_the_clamp(self):
        rows = L.play_rows(0.6385, 1.0, [2.0, 2.8], CFG)
        self.assertAlmostEqual(rows[0]["rate"], 3.132, places=3)
        self.assertTrue(rows[0]["in_clamp"])
        self.assertFalse(rows[1]["in_clamp"])  # 4.39: over the game's 4.0

    def test_a_stride_over_twice_either_way_is_flagged(self):
        self.assertTrue(L.stride_flag(2.04, CFG))
        self.assertFalse(L.stride_flag(1.96, CFG))
        self.assertTrue(L.stride_flag(0.45, CFG))
        self.assertFalse(L.stride_flag(None, CFG))

    def test_the_default_is_the_cadence_nearest_the_beat_its_tie_by_the_arm_swing(self):
        rows = [{"name": f"a{k}_f{f}", "c0": round(48 / f, 4), "slide_mm": 0.0, "arm_swing": k}  # 2 steps a loop
                for f in (22, 21) for k in (1.0, 0.75, 0.6)]
        best = L.pick_default(rows, 1 / 0.45, 5.0, 0.75)
        self.assertEqual(best["name"], "a0.75_f22")  # 2.18 nearer 2.22 than 2.29
        slid = [{**r, "slide_mm": 9.0} if r["name"].endswith("f22") else r for r in rows]
        self.assertTrue(L.pick_default(slid, 1 / 0.45, 5.0, 0.75)["name"].endswith("f21"))


class Reels(unittest.TestCase):
    def test_the_plan_pairs_the_capped_speed_beside_the_game_speed(self):
        plan = {r["name"]: r for r in L.reel_plan(L.expand(CFG))}
        self.assertEqual([c["speed"] for c in plan["Strafe_Left"]["clips"]], [3.0, 4.5])
        self.assertEqual(plan["Strafe_Left"]["view"], "front")
        self.assertEqual(plan["Jog_Bwd"]["view"], "side")
        self.assertFalse(plan["Jog_Fwd_grid"]["video"])
        self.assertEqual(len(plan["Jog_Fwd_grid"]["clips"]), 6)
        self.assertEqual(plan["Idle_to_Jog_Fwd"]["start"]["fade"], 0.15)
        self.assertIsNone(plan["Walk"]["clips"][0]["speed"])

    def test_the_timeline_places_contacts_and_beats_at_the_rate(self):
        info = {"fps": 24.0, "frames": 24, "v0": 2.25, "ground": [0.0, -2.25], "hips": [0.0, 0.0],
                "contacts": {"Left": [0], "Right": [12]}}
        tl = L.reel_timeline(info, 4.5, 2.0, CFG)
        self.assertAlmostEqual(tl["rate"], 2.0)
        self.assertEqual(tl["contacts"]["Left"], [0.0, 0.5, 1.0, 1.5, 2.0])
        self.assertEqual(tl["contacts"]["Right"], [0.25, 0.75, 1.25, 1.75])
        self.assertEqual(tl["beats"], [0.0, 0.45, 0.9, 1.35, 1.8])
        self.assertEqual(tl["dir"], [0.0, -1.0])
        own = L.reel_timeline(info, None, 2.0, CFG, offset=1.0)
        self.assertEqual(own["rate"], 1.0)
        self.assertEqual(own["contacts"]["Left"], [1.0, 2.0])
        self.assertEqual(own["beats"][0], 1.0)

    def test_blender_floor_vectors_turn_into_godot_ones(self):
        self.assertEqual(L.godot_xz((0.5, -2.0)), [0.5, 2.0])


if __name__ == "__main__":
    unittest.main()
