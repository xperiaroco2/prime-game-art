"""The House packages' game-facing contract (#107, tools/runner/house_contract.py): every node the game reads in the
committed room scenes and every collider their GLBs bring stay as pinned in layouts/house/export_contract.json (main
c0da2bc's export, before the merged shell). Only visual meshes may change: overrides of an instance's children that set
materials, shader parameters or visibility, and the merged_* / batch_* mesh nodes. Pure Python; skips when the
committed GLBs are LFS pointers."""

from __future__ import annotations

import json
import unittest

from runner import house_contract as C

PIN = C.ROOT / "layouts" / "house" / "export_contract.json"

SCENE = """[gd_scene format=3]

[ext_resource type="PackedScene" path="res://k/wall.glb" id="1"]
[ext_resource type="ShaderMaterial" path="res://k/kit_set.tres" id="2"]

[node name="Kitchen" type="Node3D"]
metadata/size_m = Vector2i(6, 4)

[node name="Shell" type="Node3D" parent="."]

[node name="wall_1" parent="Shell" instance=ExtResource("1")]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 2, 0, 0)
metadata/surface = "wood"

[node name="wall" parent="Shell/wall_1"]
surface_material_override/0 = ExtResource("2")

[node name="Doors" type="Node3D" parent="."]

[node name="Door1" type="Marker3D" parent="Doors"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0)
"""


class ContractRules(unittest.TestCase):
    def contract(self, text: str) -> dict:
        return C.scene_contract(text, lambda res: None)

    def test_visual_changes_are_not_game_facing(self):
        merged = SCENE.replace('[node name="wall" parent="Shell/wall_1"]\nsurface_material_override/0 = ExtResource("2")',
                               '[node name="wall" parent="Shell/wall_1"]\nvisible = false')
        merged += '\n[node name="merged_kit_set" type="MeshInstance3D" parent="Shell"]\nlayers = 1\n'
        self.assertEqual(self.contract(SCENE), self.contract(merged))

    def test_game_facing_changes_are_seen(self):
        base = self.contract(SCENE)
        for old, new in [("1, 0, 0)\n", "1.5, 0, 0)\n"),  # the door marker moved
                         ('"wood"', '"carpet"'),  # a footstep surface
                         ('[node name="wall" parent="Shell/wall_1"]', '[node name="wall" parent="Shell/wall_1"]\n'
                                                                       'metadata/x = 1')]:  # a child's non-visual property
            self.assertNotEqual(base, self.contract(SCENE.replace(old, new)), new)

    def test_an_unresolved_glb_is_named(self):
        self.assertEqual(self.contract(SCENE)["colliders"], ["Shell/wall_1 ? res://k/wall.glb"])


class CommittedPackages(unittest.TestCase):
    def test_every_game_facing_node_and_collider_is_unchanged(self):
        try:
            now = C.snapshot()
        except ValueError as e:  # an LFS pointer instead of a GLB
            self.skipTest(str(e))
        pin = json.loads(PIN.read_text(encoding="utf-8"))
        problems = []
        for pkg in sorted(set(pin) | set(now)):
            for scene in sorted(set(pin.get(pkg, {})) | set(now.get(pkg, {}))):
                a, b = pin.get(pkg, {}).get(scene), now.get(pkg, {}).get(scene)
                if a is None or b is None:
                    problems.append(f"{pkg}/{scene}: {'new' if a is None else 'missing'}")
                elif a["sha"] != b["sha"]:
                    groups = sorted(g for g in set(a["groups"]) | set(b["groups"])
                                    if a["groups"].get(g) != b["groups"].get(g))
                    problems.append(f"{pkg}/{scene}: changed in {groups} "
                                    f"(nodes {a['nodes']}->{b['nodes']}, colliders {a['colliders']}->{b['colliders']})")
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
