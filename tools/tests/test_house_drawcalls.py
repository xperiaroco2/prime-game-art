"""#107: the draw-call count per view (house_bake.draw_calls, budget_warnings, draw_calls_md) and the merged shell's
hook in house_layout.write_scenes (hidden piece meshes, merged instances; every piece instance kept)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import house_bake as B  # noqa: E402
from runner import house_layout as H  # noqa: E402

ROWS = [{"label": "ground_realtime", "zone": "ground", "mode": "realtime"},
        {"label": "ground_high_baked", "zone": "ground", "mode": "baked"},
        {"label": "ground_high_sheen12_shadow", "zone": "ground", "mode": "sheen12_shadow"}]


def shot(row, cam, dc, sdc):
    return {"row": row, "cam": cam, "draw_calls_cached": dc, "shadow_draw_calls_redrawn": sdc}


class DrawCalls(unittest.TestCase):
    def setUp(self):
        self.shots = [shot("ground_realtime", 0, 999, 0), shot("ground_high_baked", 1, 120.4, 0),
                      shot("ground_high_baked", 0, 160.6, 0), shot("ground_high_sheen12_shadow", 0, 500, 900),
                      shot("ground_high_sheen12_shadow", 1, 300, 1200)]

    def test_kinds_and_order(self):
        t = B.draw_calls(self.shots, ROWS)
        self.assertEqual(t, {"ground": {"baked": [{"dc": 161, "sdc": 0}, {"dc": 120, "sdc": 0}],
                                        "high": [{"dc": 500, "sdc": 900}, {"dc": 300, "sdc": 1200}]}})

    def test_warnings_name_the_view_and_the_limit(self):
        t = B.draw_calls(self.shots, ROWS)
        w = B.budget_warnings({"baked": 150, "high": 400, "high_shadow": 1000}, t, {"ground": ["E1 a", "seam"]})
        self.assertEqual(w, ["WARN draw calls: ground E1 a baked 161 > 150",
                             "WARN draw calls: ground E1 a high 500 > 400",
                             "WARN draw calls: ground seam high_shadow 1200 > 1000"])

    def test_table_reads_before_to_after(self):
        t = B.draw_calls(self.shots, ROWS)
        md = B.draw_calls_md(t, {"ground": ["E1 a", "seam"]}, {"baked": 150},
                             {"ground": {"baked": [{"dc": 400, "sdc": 0}]}})
        self.assertIn("| ground | E1 a | 400 -> 161 | 500 | 900 |", md)
        self.assertIn("| ground | seam | 120 | 300 | 1200 |", md)


class MergeHook(unittest.TestCase):
    def test_pieces_stay_hidden_meshes_and_merged_instances_join_the_shell(self):
        data = H.load()
        planned = H.plan(data)
        calls = []

        def merge(level, rid, pieces):
            calls.append((level, rid, len(pieces)))
            hide = {pieces[0]["node"]} if pieces else set()
            return {"hide": hide, "add": [("merged_shell", f"res://import/kit_shell_m_{level}_{rid}.glb")]}
        with tempfile.TemporaryDirectory() as tmp:
            plain = H.write_scenes(data, planned, Path(tmp) / "a")
            merged = H.write_scenes(data, planned, Path(tmp) / "b", merge=merge)
            self.assertEqual(plain["pieces"], merged["pieces"])
            text = (Path(tmp) / "b" / "ground" / "kitchen.tscn").read_text(encoding="utf-8")
            plain_text = (Path(tmp) / "a" / "ground" / "kitchen.tscn").read_text(encoding="utf-8")
        self.assertTrue(calls)
        self.assertIn('[node name="merged_shell" parent="Shell" instance=ExtResource(', text)
        self.assertIn("\nvisible = false", text)
        for line in plain_text.splitlines():  # every node of the plain scene is still there
            if line.startswith("[node "):
                self.assertIn(line, text)


if __name__ == "__main__":
    unittest.main()
