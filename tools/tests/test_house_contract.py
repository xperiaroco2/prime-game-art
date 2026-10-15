"""The House packages' game-facing contract (#107, tools/runner/house_contract.py): every node the game reads in the
committed room scenes and every collider their GLBs bring stay as pinned in layouts/house/export_contract.json (main
c0da2bc's export, before the merged shell). Only visual meshes may change: overrides of an instance's children that set
materials, shader parameters or visibility, and the merged_* / batch_* mesh nodes. Pure Python; skips when the
committed GLBs are LFS pointers."""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

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

MERGED_NODES = """
[node name="merged_kit_set" type="MeshInstance3D" parent="Shell"]
layers = 1

[node name="merged_kit_set_shadow" parent="Shell" instance=ExtResource("1")]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)

[node name="shadow" parent="Shell/merged_kit_set_shadow"]
cast_shadow = 3
gi_mode = 0

[node name="Dressing" type="Node3D" parent="."]

[node name="batch_dressing" parent="Dressing" instance=ExtResource("1")]

[node name="merged_props" parent="Dressing/batch_dressing"]
cast_shadow = 0
surface_material_override/0 = ExtResource("2")
"""


def collider_glb(path: Path) -> Path:
    """A GLB with one trimesh collider node (`wall-colonly`) of one triangle."""
    blob = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 0, 1)
    j = {"asset": {"version": "2.0"}, "nodes": [{"name": "wall-colonly", "mesh": 0}],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
         "bufferViews": [{"buffer": 0, "byteLength": len(blob)}], "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(j).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(blob), b"BIN\0") + blob
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
    return path


class ContractRules(unittest.TestCase):
    def contract(self, text: str) -> dict:
        return C.scene_contract(text, lambda res: None)

    def test_visual_changes_are_not_game_facing(self):
        merged = SCENE.replace('[node name="wall" parent="Shell/wall_1"]\nsurface_material_override/0 = ExtResource("2")',
                               '[node name="wall" parent="Shell/wall_1"]\nvisible = false')
        merged += '\n[node name="merged_kit_set" type="MeshInstance3D" parent="Shell"]\nlayers = 1\n'
        self.assertEqual(self.contract(SCENE), self.contract(merged))
        # #185: a shadow proxy and the merged mesh's cast_shadow override are visual too
        merged += ('\n[node name="shell_m" parent="Shell/merged_kit_set"]\ncast_shadow = 0\n'
                   '\n[node name="merged_kit_set_shadow" parent="Shell" instance=ExtResource("1")]\n'
                   '\n[node name="shadow" parent="Shell/merged_kit_set_shadow"]\ncast_shadow = 3\ngi_mode = 0\n')
        self.assertEqual(self.contract(SCENE), self.contract(merged))

    def test_game_facing_changes_are_seen(self):
        base = self.contract(SCENE)
        for old, new in [("1, 0, 0)\n", "1.5, 0, 0)\n"),  # the door marker moved
                         ('"wood"', '"carpet"'),  # a footstep surface
                         ('[node name="wall" parent="Shell/wall_1"]', '[node name="wall" parent="Shell/wall_1"]\n'
                                                                       'metadata/x = 1')]:  # a child's non-visual property
            self.assertNotEqual(base, self.contract(SCENE.replace(old, new)), new)

    def test_game_facing_nodes_under_a_merged_or_batch_node_are_seen(self):
        """#185's review: only the merged and batch meshes and their drawing overrides are left out, not whatever sits
        under them: a collider instance, a door, station or marker, a footstep surface, a non-drawing override."""
        base = SCENE + MERGED_NODES
        before = self.contract(base)
        for parent in ("Shell/merged_kit_set", "Shell/merged_kit_set_shadow", "Dressing/batch_dressing"):
            for name, section in [
                    ("wall_9", f'[node name="wall_9" parent="{parent}" instance=ExtResource("1")]\n'
                               'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 4, 0, 0)\n'),  # a collider
                    ("Door2", f'[node name="Door2" type="Marker3D" parent="{parent}"]\n'),
                    ("fix_pc", f'[node name="fix_pc" type="Marker3D" parent="{parent}"]\nmetadata/station = "fix_pc"\n'),
                    ("Spawn", f'[node name="Spawn" type="Marker3D" parent="{parent}"]\n'),
                    ("shell_m", f'[node name="shell_m" parent="{parent}"]\nmetadata/surface = "wood"\n'),
                    ("shadow", f'[node name="shadow" parent="{parent}"]\ncast_shadow = 3\nscript = null\n')]:
                got = self.contract(base + "\n" + section)
                self.assertNotEqual(before, got, f"{parent}/{name}")
                self.assertIn(f"{parent}/{name} ", "\n".join(got["nodes"]), f"{parent}/{name}")
        # a game-facing node named like a merged mesh, and a merged mesh given a footstep surface, are seen too
        for section in ['[node name="merged_door" type="Marker3D" parent="Doors"]\n',
                        '[node name="batch_x" type="StaticBody3D" parent="Dressing"]\n',
                        '[node name="merged_floor" parent="Shell" instance=ExtResource("1")]\nmetadata/surface = "tile"\n',
                        '[node name="merged_wall" parent="Shell" groups=["spawn_x"] instance=ExtResource("1")]\n']:
            self.assertNotEqual(before, self.contract(base + "\n" + section), section)

    def test_a_collider_under_a_merged_node_is_in_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            glb = collider_glb(Path(tmp) / "wall.glb")
            text = SCENE + MERGED_NODES + '\n[node name="wall_9" parent="Dressing/batch_dressing" instance=ExtResource("1")]\n'
            got = C.scene_contract(text, lambda res: glb)
        self.assertEqual([c.split(" ", 1)[0] for c in got["colliders"]],
                         ["Shell/wall_1", "Dressing/batch_dressing/wall_9"])
        self.assertIn("wall-colonly", got["colliders"][1])

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
