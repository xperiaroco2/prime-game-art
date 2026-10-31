"""The alien clips' contact table's flight rule (tools/blender/alien_contact.py, art #196 B1d)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_contact as C  # noqa: E402

# her Crouch_Fwd_Loop after B1c (b1c/run/proof): the shoes' and the bare body's lowest per frame, mm, the loop's
# repeated last frame left out
CROUCH_SHOES = [9, 1, 0, 1, 2, 4, 8, 16, 20, 29, 20, 20, 17, 15, 13, 12, 13, 16, 21, 29]
CROUCH_BARE = [15, 7, 5, 5, 7, 9, 14, 20, 25, 37, 37, 31, 25, 21, 18, 17, 19, 23, 27, 35]


class Flight(unittest.TestCase):
    def test_a_crouch_float_is_counted(self):
        # the old rule took every frame with the bare body up as flight: the float passed with 0 frames
        self.assertEqual(C.floated("Crouch_Fwd_Loop", CROUCH_SHOES, CROUCH_BARE),
                         sum(g > 5 for g in CROUCH_SHOES))
        self.assertGreater(C.floated("Crouch_Fwd_Loop", CROUCH_SHOES, CROUCH_BARE), 10)
        self.assertGreater(C.floated("Crouch_Run__s4b_Loop", CROUCH_SHOES, CROUCH_BARE), 10)

    def test_a_run_keeps_its_flight(self):
        shoes, bare = [0, 0, 40, 120, 60, 0], [0, 1, 45, 130, 70, 2]
        self.assertEqual(C.floated("Jog_Fwd_Loop", shoes, bare), 0)
        self.assertEqual(C.floated("Jog_Fwd_Loop", [0, 9, 40, 120, 60, 0], bare), 1)  # frame 1: the bare body down

    def test_the_gaits(self):
        for clip in ("Walk_Loop", "Crouch_Idle_Loop", "Crouch_Run_Loop", "Idle_Loop", "Talk_Upper_Loop"):
            self.assertFalse(C.can_fly(clip), clip)
        for clip in ("Jog_Fwd_Loop", "Sprint_Fwd_Loop", "Strafe_Left__w03_Loop", "Jump_Land", "Jog_Bwd__p2_Loop"):
            self.assertTrue(C.can_fly(clip), clip)
        with self.assertRaises(ValueError):
            C.floated("Walk_Loop", [0.0], [0.0, 0.0])

    def test_the_table_marks_the_float(self):
        js = lambda g: {"meshes": ["shoes"], "clips": {"Crouch_Fwd_Loop": [  # noqa: E731
            {"f": i, "hips": 500.0, "shoes": v} for i, v in enumerate(g + g[:1])]}}
        bare = {"meshes": ["body"], "clips": {"Crouch_Fwd_Loop": [
            {"f": i, "hips": 500.0, "body": v} for i, v in enumerate(CROUCH_BARE + CROUCH_BARE[:1])]}}
        row = C.table([("axolotl", bare, [js(CROUCH_SHOES)])])[2]
        self.assertIn("(no flight)", row)
        self.assertEqual(row.split("|")[6].strip(), str(sum(g > 5 for g in CROUCH_SHOES)))


if __name__ == "__main__":
    unittest.main()
