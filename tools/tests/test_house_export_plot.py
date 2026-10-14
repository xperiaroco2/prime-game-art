"""Package 7's plot scene (art #128): the flat game names of the props (one rule for every package), the ground's
surface overrides and the scene's shape."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from runner import common, house_layout as H, house_outdoor
from runner import house_export_plot as P

DATA = H.load()
ORDER = ["props/task/v1", "props/library/v1", "props/zones/v1"]
IDS = {"props/task/v1": {"birdbath", "boiler"}, "props/library/v1": {"birdbath", "deckchair", "sofa"},
       "props/zones/v1": {"deckchair", "photo_backdrop"}}


def has(d: str, pid: str) -> bool:
    return pid in IDS.get(d, set())


class GameNames(unittest.TestCase):
    def test_the_first_source_keeps_the_plain_name_the_others_take_their_tag(self):
        self.assertEqual(P.game_name(ORDER, has, "props/task/v1", "birdbath"), "birdbath.glb")
        self.assertEqual(P.game_name(ORDER, has, "props/library/v1", "birdbath"), "birdbath_library.glb")
        self.assertEqual(P.game_name(ORDER, has, "props/library/v1", "deckchair"), "deckchair.glb")
        self.assertEqual(P.game_name(ORDER, has, "props/zones/v1", "deckchair"), "deckchair_zones.glb")
        self.assertEqual(P.game_name(ORDER, has, "props/zones/v1", "photo_backdrop"), "photo_backdrop.glb")

    def test_clashes_list_every_shared_basename_in_order(self):
        self.assertEqual(P.clashes(ORDER, IDS), {"birdbath": ["props/task/v1", "props/library/v1"],
                                                "deckchair": ["props/library/v1", "props/zones/v1"]})

    def test_the_order_starts_with_prop_dirs_so_merged_packages_keep_their_names(self):
        order = P.prop_order(DATA)
        self.assertEqual(order[:len(DATA["settings"]["prop_dirs"])], DATA["settings"]["prop_dirs"])
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(P.source_tag("props/zones/v1"), "zones")

    @unittest.skipUnless((common.raw_dir() / "props" / "zones" / "v1").is_dir(), "raw prop folders missing")
    def test_every_raw_prop_gets_a_unique_game_name(self):
        raw = common.raw_dir()
        order = P.prop_order(DATA)
        ids = {d: {f.stem for f in (raw / d).glob("*.glb")} for d in order}
        names = [P.game_name(order, lambda d, pid: pid in ids[d], d, pid) for d in order for pid in ids[d]]
        self.assertEqual(len(names), len(set(names)))
        for pid in ids[order[0]]:  # the task props (P2, P3, P5 shipped them): their names do not change
            self.assertEqual(P.game_name(order, lambda d, p: p in ids[d], order[0], pid), f"{pid}.glb")


class Ground(unittest.TestCase):
    def test_every_ground_node_carries_a_game_surface(self):
        got = P.ground_surfaces(house_outdoor.load())
        names = [n for n, _ in got]
        self.assertIn("ground_grass", names)
        self.assertIn("ground_concrete", names)
        self.assertIn("kerb", names)
        self.assertTrue({s for _, s in got} <= {"concrete", "wood", "carpet", "grass"})

    def test_transforms_turn_about_y_and_scale_evenly(self):
        self.assertEqual(P.tf(0, 1, 2, 3), "Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 2, 3)")
        self.assertIn("2, 0, 0, 0, 2, 0, 0, 0, 2", P.tf(0, 0, 0, 0, 2.0))


class SceneInstances(unittest.TestCase):
    """The plot scene itself (resolve() through to scene()), on a fake raw folder: a zones prop whose id the library
    also holds is instanced from its own unique game file, and a kit piece carries the set material (#132)."""

    def build(self, surfaces=None) -> dict:
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for rel in ("props/library/v4/deckchair.glb", "props/zones/v1/deckchair.glb",
                    "props/zones/v1/photo_backdrop.glb", f"{DATA['settings']['kit_dir']}/fence_t.glb"):
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_bytes(rel.encode())
        self.raw = tmp
        doc = {"fence": [{"piece": "fence_t", "at": [1, 0, 2], "yaw": 90}], "stairs": {"pieces": [], "rails": []},
               "props": []}
        zones = [[{"src": "zones", "id": "deckchair", "pos": [5, 0, 5], "yaw": 0},
                  {"src": "library", "id": "deckchair", "pos": [6, 0, 5], "yaw": 0},
                  {"src": "zones", "id": "photo_backdrop", "pos": [7, 0, 5], "yaw": 0}]]
        return P.scene(DATA, tmp, house_outdoor.load(), doc, {"roof": [], "props": [], "scatter": []}, zones,
                       surfaces=surfaces)

    def instanced(self, text: str, node: str) -> str:
        ids = dict((i, path) for path, i in re.findall(r'\[ext_resource type="PackedScene" path="([^"]+)" id="([^"]+)"\]',
                                                        text))
        got = re.search(rf'\[node name="{node}" parent="Dressing" instance=ExtResource\("([^"]+)"\)\]', text)
        self.assertIsNotNone(got, node)
        return ids[got.group(1)]

    def test_a_zones_prop_is_instanced_from_its_unique_game_file(self):
        out = self.build()
        text, props = out["text"], DATA["settings"]["export"]["prop_set"]
        self.assertTrue(self.instanced(text, "deckchair_1").endswith(f"/{props}/deckchair_zones.glb"))
        self.assertTrue(self.instanced(text, "deckchair_2").endswith(f"/{props}/deckchair.glb"))
        self.assertTrue(self.instanced(text, "photo_backdrop_1").endswith(f"/{props}/photo_backdrop.glb"))
        self.assertEqual(out["copies"][f"{props}/deckchair_zones.glb"], self.raw / "props/zones/v1/deckchair.glb")
        self.assertEqual(out["copies"][f"{props}/deckchair.glb"], self.raw / "props/library/v4/deckchair.glb")

    def test_a_kit_piece_carries_the_set_material_at_its_plan_pose(self):
        sets = {"fence_t": [{"node": "fence_t/mesh", "at": [1.0, 0.5, 0.0], "surfaces": [0, 2]}]}
        text = self.build(sets)["text"]
        node = text[text.index('[node name="mesh" parent="Shell/fence_t_1/fence_t"]'):].split("\n\n")[0]
        self.assertIn("surface_material_override/0 = ExtResource(", node)
        self.assertIn("surface_material_override/2 = ExtResource(", node)
        self.assertIn("instance_shader_parameters/plan_at = Vector4(1, 0.5, 1, 90)", node)  # local +X turns to -z
        self.assertNotIn("surface_material_override", self.build()["text"])


SCENE = Path(__file__).resolve().parents[2] / "assets" / "room" / "house_plot" / "export" / "outdoor.tscn"


@unittest.skipUnless(SCENE.is_file(), "the committed plot scene is missing")
class CommittedScene(unittest.TestCase):
    def test_the_plot_scene_has_its_groups_overrides_and_no_csg(self):
        text = SCENE.read_text(encoding="utf-8")
        self.assertNotIn("CSG", text)
        self.assertNotIn('parent="Placeholders"', text)
        for group in ("Ground", "Backdrop", "Shell", "Dressing"):
            self.assertIn(f'[node name="{group}"', text)
        for name, surface in P.ground_surfaces(house_outdoor.load()):
            self.assertIn(f'[node name="{name}" parent="Ground"]\nmetadata/surface = "{surface}"', text)
        self.assertIn('[editable path="Ground"]', text)
        self.assertGreater(text.count('parent="Shell"'), 50)
        self.assertGreater(text.count('parent="Dressing"'), 50)


if __name__ == "__main__":
    unittest.main()
