"""#107: the draw-call count per view (house_bake.draw_calls, budget_warnings, draw_calls_md) and the merged shell's
hook in house_layout.write_scenes (hidden piece meshes, merged instances; every piece instance kept) and the batched
dressing's hook in house_dressing.scene_nodes (hidden prop visuals, batch instances; every prop instance kept)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import house_bake as B  # noqa: E402
from runner import house_dressing as D  # noqa: E402
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


class WalkCount(unittest.TestCase):
    """#185: `house --walk` counts its views on the --count code path."""

    def test_request_is_the_high_preset_over_the_glow_fixtures(self):
        lights = {"presets": {"high": {"sheen": "sheen12_shadow"}}}
        fx = [{"name": "a_bare_bulb_01", "light": "omni", "x": 1, "h": 2.5, "y": 3, "range": 5, "energy": 1, "glow": True},
              {"name": "a_tube_01", "light": "omni", "x": 0, "h": 2.5, "y": 0, "range": 4, "energy": 1, "glow": False},
              {"name": "a_spot_01", "light": "spot", "x": 4, "h": 2.6, "y": 5, "range": 6, "energy": 2, "glow": True,
               "angle": 40, "aim": [4, 0, 5]}]
        req = B.walk_count(lights, fx)
        self.assertEqual((req["n"], req["shadow"]), (12, True))
        self.assertEqual([g["name"] for g in req["glow"]], ["a_bare_bulb_01", "a_spot_01"])
        self.assertEqual(req["glow"][0]["at"], [1, 2.5, 3])
        self.assertEqual((req["glow"][1]["angle"], req["glow"][1]["aim"]), (40, [4, 0, 5]))

    def test_counts_become_the_count_table(self):
        c = {"front_door": {"baked": {"draw_calls_cached": 151.2}, "high": {"draw_calls_cached": 300,
                                                                            "shadow_draw_calls_redrawn": 800}},
             "kitchen": {"baked": {"draw_calls_cached": 90}, "high": {"draw_calls_cached": 200,
                                                                     "shadow_draw_calls_redrawn": 2500.4}}}
        table, names = B.walk_table(c)
        self.assertEqual(names, {"walk": ["front_door", "kitchen"]})
        self.assertEqual(table["walk"]["baked"], [{"dc": 151, "sdc": 0}, {"dc": 90, "sdc": 0}])
        self.assertEqual(B.budget_warnings({"baked": 150, "high_shadow": 2000}, table, names),
                         ["WARN draw calls: walk front_door baked 151 > 150",
                          "WARN draw calls: walk kitchen high_shadow 2500 > 2000"])


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


class BatchHook(unittest.TestCase):
    RS = [{"id": "chair", "kind": "props", "at": (1.0, 0.0, 2.0), "yaw": 90.0, "collision": "box", "size": [1, 1, 1]},
          {"id": "chair", "kind": "props", "at": (2.0, 0.0, 2.0), "yaw": 0.0, "collision": "box", "size": [1, 1, 1]},
          {"id": "desk", "kind": "props", "at": (3.0, 0.0, 1.0), "yaw": 0.0, "collision": "box", "size": [1, 1, 1],
           "station": "fix_pc"}]

    def scene(self, batch=None, overrides=None):
        sc = H._Scene("Room")
        D.scene_nodes(sc, self.RS, lambda pid: f"res://import/prop_{pid}.glb", overrides, batch)
        return sc.nodes

    def test_prop_instances_stay_and_the_batch_joins_their_group(self):
        seen = []

        def batch(parent, items):
            seen.append((parent, [n for _, n in items]))
            return {"hide": {n: ["chair"] for r, n in items if not r.get("station")},
                    "add": [("batch_dressing", "res://import/prop_batch_ground_room_dressing.glb")]}
        plain, nodes = self.scene(), self.scene(batch, lambda pid: [("chair", ["surface_material_override/0 = 1"])]
                                                if pid == "chair" else [])
        self.assertEqual(seen, [("Dressing", ["chair_1", "chair_2", "desk_1"])])
        for n in plain:  # every prop node with its metadata is still there
            self.assertIn(n, nodes)
        self.assertIn('[node name="chair" parent="Dressing/chair_1"]\nsurface_material_override/0 = 1\nvisible = false',
                      nodes)
        self.assertFalse(any(n.startswith('[node name="desk" parent="Dressing/desk_1"]') for n in nodes))
        self.assertTrue(nodes[-1].startswith('[node name="batch_dressing" parent="Dressing" instance=ExtResource('))

    def test_a_batch_with_a_key_gets_its_overrides(self):
        def batch(parent, items):  # the export's batch: a third item names the batch for the fine pack's overrides
            return {"hide": {}, "add": [("batch_dressing", "res://merged/batch_g_r_dressing.glb", "batch_g_r_dressing")]}

        def overrides(key):
            return [("merged_props", ["surface_material_override/1 = 2"])] if key == "batch_g_r_dressing" else []
        nodes = self.scene(batch, overrides)
        self.assertTrue(nodes[-2].startswith('[node name="batch_dressing" parent="Dressing" instance=ExtResource('))
        self.assertEqual(nodes[-1], '[node name="merged_props" parent="Dressing/batch_dressing"]\n'
                                    'surface_material_override/1 = 2')


if __name__ == "__main__":
    unittest.main()
