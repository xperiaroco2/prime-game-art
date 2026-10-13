"""The House's room scenes split the props by layer and carry the fine pack (#147; docs/house.md "The export",
docs/props.md "World look rules"): the base layer's props under `Dressing`, the detail layer's under `Detail` (a
graphics preset hides that one node), the props' `kit_fine` surfaces on the shipped tier's shared material, and the
shipped copy of the fine pack's shader equal to its source (godot/props/prop_fine.gdshader)."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import house_dressing as hd  # noqa: E402
from runner import house_export as X  # noqa: E402
from runner import house_layout as hl  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "assets" / "prop" / "house_props" / "export" / X.FINE_SHADER


def _scene(resolved, overrides=None) -> str:
    sc = hl._Scene("Kitchen")
    hd.scene_nodes(sc, resolved, lambda pid: f"res://p/{pid}.glb", overrides)
    return sc.text()


def _parents(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r'\[node name="([^"]+)" parent="([^"]+)" instance=', text)}


class Layers(unittest.TestCase):
    def test_the_library_gives_each_prop_its_layer(self):
        cat = hd.catalogue([ROOT / "props" / "tasks.toml", ROOT / "props" / "library.toml"])
        clutter = [i for i, e in cat.items() if e["class"] == "clutter"]
        self.assertTrue(clutter)
        self.assertTrue(all(cat[i]["layer"] == hd.DETAIL for i in clutter))
        self.assertEqual(cat["backsplash_l"]["layer"], hd.BASE)
        self.assertEqual(cat["fridge"]["layer"], hd.BASE)
        self.assertEqual(cat["assembly_island"]["layer"], hd.BASE)
        self.assertTrue(all(e["collision"] == "none" for e in cat.values() if e["layer"] == hd.DETAIL))

    def test_detail_props_go_under_their_own_node(self):
        cat = {"fridge": {"size": [0.8, 0.7, 1.9], "layer": hd.BASE, "collision": "box"},
               "cup": {"size": [0.1, 0.1, 0.1], "layer": hd.DETAIL, "collision": "none"}}
        resolved = [dict(hd.resolve({"id": i, "at": [1.0, 0.0, 1.0]}, cat), kind="props") for i in ("fridge", "cup", "cup")]
        text = _scene(resolved + [dict(hd.resolve({"id": "lamp", "at": [1, 2, 1]}, {}), kind="fixtures")])
        self.assertEqual(_parents(text), {"fridge_1": "Dressing", "cup_1": "Detail", "cup_2": "Detail",
                                          "lamp_1": "Fixtures"})
        self.assertIn('[node name="Detail" type="Node3D" parent="."]', text)

    def test_no_detail_node_without_detail_props(self):
        resolved = [dict(hd.resolve({"id": "fridge", "at": [1.0, 0.0, 1.0]}, {}), kind="props")]
        self.assertNotIn('name="Detail"', _scene(resolved))

    def test_overrides_land_under_the_instance(self):
        resolved = [dict(hd.resolve({"id": "stove", "at": [1.0, 0.0, 1.0]}, {}), kind="props")]
        text = _scene(resolved, lambda pid: [("stove/body", ["surface_material_override/0 = X"])])
        self.assertIn('[node name="body" parent="Dressing/stove_1/stove"]\nsurface_material_override/0 = X', text)


class FinePack(unittest.TestCase):
    FINE = {"layers": [{"name": "wood_front", "roughness": 0.6, "normal_strength": 0.45},
                       {"name": "steel", "metallic": 0.6, "roughness": 0.42}],
            "tiers": {"low": {"size": 512, "detail_mean": {"wood_front": 0.25}}}}

    def test_a_tier_material_holds_the_pack(self):
        data = {"settings": {"export": {"asset_res": "res://assets/environment/{set}/{id}.glb",
                                        "prop_set": "house_props"}}}
        text = X.fine_material_text(data, self.FINE, "low")
        self.assertIn('path="res://assets/environment/house_props/prop_fine.gdshader"', text)
        for k in X.FINE_TEXTURES:
            self.assertIn(f'path="res://assets/environment/house_props/fine/low/fine_{k}.png"', text)
        rough = re.search(r"layer_roughness = PackedFloat32Array\(([^)]*)\)", text).group(1).split(", ")
        self.assertEqual(len(rough), X.FINE_LAYERS)
        self.assertEqual(rough[:2], ["0.6", "0.42"])
        self.assertIn("layer_metallic = PackedFloat32Array(0, 0.6,", text)
        self.assertIn("layer_gain = Vector4(4, 2, 2, 2)", text)

    def test_fine_surfaces_of_a_built_prop(self):
        raw = Path("D:/prime-art-raw/props/library/v1/fridge.glb")
        if not raw.is_file():
            self.skipTest("no raw build of the fridge")
        found = X.set_surfaces(raw, X.FINE_MATERIAL, posed=False)
        self.assertTrue(found and all(s["surfaces"] for s in found), found)

    def test_the_shipped_shader_is_its_source(self):
        self.assertTrue(SHIPPED.is_file(), f"{SHIPPED.relative_to(ROOT).as_posix()} is missing")
        src = X.FINE_SHADER_SRC.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(SHIPPED.read_bytes().replace(b"\r\n", b"\n"), src,
                         f"{SHIPPED.relative_to(ROOT).as_posix()} differs from its source: re-export the props' "
                         "package (docs/house.md \"The export\") or put the source back")


if __name__ == "__main__":
    unittest.main()
