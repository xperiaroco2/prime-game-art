"""The House dressing library's mapping file (props/library.toml, docs/props.md): the glTF reader, the pure checks of
the library (classes, budgets, paints, licences, pack scales) and, when the raw packs are on disk, the recorded
measures of every pack file."""

from __future__ import annotations

import copy
import json
import struct
import unittest

from runner import common
from runner.commands import _props

LIB = _props.load()
SOURCES = _props.sources_index()
KIT = json.loads((common.ROOT / LIB["kit_spec"]).read_text(encoding="utf-8"))
PROPS = {p["id"]: p for p in LIB["prop"]}


def _glb(gltf: dict) -> bytes:
    body = json.dumps(gltf).encode("utf-8")
    body += b" " * (-len(body) % 4)
    return struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(body)) + struct.pack("<II", len(body), 0x4E4F534A) + body


CUBE = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"children": [1], "scale": [2.0, 2.0, 2.0]},
                  {"mesh": 0, "translation": [1.0, 0.0, 0.0], "rotation": [0.0, 0.7071068, 0.0, 0.7071068]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [{"count": 8, "min": [0.0, 0.0, 0.0], "max": [1.0, 0.5, 0.25]}, {"count": 36}]}


class GltfReaderTest(unittest.TestCase):
    def test_bounds_follow_the_node_transforms(self) -> None:
        m = _props.measure(_props.read_gltf_bytes(_glb(CUBE)))
        # the box 1 x 0.5 x 0.25 turned 90 degrees about Y, moved 1 m along X, scaled 2: 0.5 x 1 x 2
        self.assertEqual(m["size"], [0.5, 1.0, 2.0])
        self.assertEqual(m["min"], [2.0, 0.0, -2.0])
        self.assertEqual(m["triangles"], 12)

    def test_an_empty_scene_measures_zero(self) -> None:
        empty = {"asset": {"version": "2.0"}, "scenes": [{"nodes": []}]}
        self.assertEqual(_props.measure(empty)["triangles"], 0)


class LibraryTest(unittest.TestCase):
    def test_the_library_is_clean(self) -> None:
        self.assertEqual(_props.check(LIB, SOURCES, KIT), [])

    def test_at_most_max_materials(self) -> None:
        self.assertLessEqual(len(set(LIB["materials"].values())), LIB["max_materials"])

    def test_every_pack_is_cc0_and_public(self) -> None:
        for p in LIB["prop"]:
            if p["route"] == "pack":
                rec = SOURCES[p["source"]]
                self.assertEqual((rec["licence"], rec["public_repo_ok"], rec["ai_generated"]),
                                 ("CC0-1.0", True, False), p["id"])

    def test_no_task_or_hero_prop_is_here(self) -> None:
        for pid in ("generator", "wall_switch", "car", "car_lift", "order_board", "assembly_island", "mannequin",
                    "rocking_horse", "gazebo", "garden_tree"):
            self.assertNotIn(pid, PROPS)
            self.assertIn(pid, LIB["skip"])

    def test_wall_and_ceiling_props(self) -> None:
        self.assertEqual(PROPS["picture_frame"]["pivot"], "wall")
        self.assertEqual(PROPS["bare_bulb"]["pivot"], "ceiling")
        for p in LIB["prop"]:
            if p["class"] == "fixture":
                self.assertIn("emissive", {LIB["roles"].get(r, {}).get("material") for r in p["roles"]}, p["id"])

    def test_a_wrong_scale_is_found(self) -> None:
        lib = copy.deepcopy(LIB)
        sofa = next(p for p in lib["prop"] if p["id"] == "sofa")
        sofa.pop("stretch")
        sofa["scale"] = 1.0
        self.assertTrue(any("sofa: scaled" in s for s in _props.check(lib, SOURCES, KIT)))

    def test_a_distorting_stretch_is_found(self) -> None:
        lib = copy.deepcopy(LIB)
        sofa = next(p for p in lib["prop"] if p["id"] == "sofa")
        sofa["size_m"] = [2.0, 0.3, 0.85]
        self.assertTrue(any("distorts" in s for s in _props.check(lib, SOURCES, KIT)))

    def test_a_private_source_is_refused(self) -> None:
        sources = copy.deepcopy(SOURCES)
        sources["kaykit_furniture_bits"]["public_repo_ok"] = False
        self.assertTrue(any("not public_repo_ok" in s for s in _props.check(LIB, sources, KIT)))

    def test_an_unknown_role_and_material(self) -> None:
        lib = copy.deepcopy(LIB)
        lib["prop"][0]["roles"] = ["no_such_role"]
        lib["materials"]["plaster"] = "velvet"
        problems = _props.check(lib, SOURCES, KIT)
        self.assertTrue(any("no_such_role" in s for s in problems))
        self.assertTrue(any("velvet" in s for s in problems))


@unittest.skipUnless(_props.env_dir().is_dir(), "the raw packs are not on this machine")
class RawTest(unittest.TestCase):
    def test_the_recorded_measures_match_the_files(self) -> None:
        problems, found = _props.remeasure(LIB, _props.env_dir())
        self.assertEqual(problems, [])
        self.assertEqual(found, sum(p["route"] == "pack" for p in LIB["prop"]))


if __name__ == "__main__":
    unittest.main()


def _problems(edit) -> list[str]:
    lib = copy.deepcopy(LIB)
    edit(lib)
    return _props.check(lib, SOURCES, KIT)


class WorldLookTest(unittest.TestCase):
    """The world look's rules (docs/decisions/2026-10-13-house-world-look.md): the hero class, [layers], [style],
    [fine] and the fine pack's roles."""

    def test_the_hero_class_and_the_direction(self) -> None:
        self.assertEqual(LIB["budgets"]["hero"], [1500, 4000])
        self.assertEqual(LIB["style"]["direction"], "C2-white")
        names = [layer["name"] for layer in LIB["fine"]["layers"]]
        self.assertEqual([layer.get("source") for layer in LIB["fine"]["layers"][:4]],
                         ["Wood092", "Wood049", "Concrete034", "Tiles107"])
        for role, layer in (("wood_front", "wood_front"), ("worktop_wood", "worktop_wood"),
                            ("worktop_stone", "stone"), ("tile_splash", "tile"), ("enamel_white", "enamel"),
                            ("steel_warm", "steel"), ("chrome", "chrome")):
            self.assertEqual((LIB["roles"][role]["material"], LIB["roles"][role]["layer"]), ("fine", layer))
            self.assertIn(layer, names)
        self.assertEqual(LIB["material_props"]["glass_tint"], {"roughness": 0.05, "metallic": 0.15, "alpha": 0.38})
        self.assertEqual(LIB["roles"]["glass_tint"]["hex"], "#86918b")
        steel = LIB["fine"]["layers"][names.index("steel")]
        chrome = LIB["fine"]["layers"][names.index("chrome")]
        self.assertEqual((steel["metallic"], steel["roughness"], LIB["roles"]["steel_warm"]["hex"]),
                         (0.6, 0.42, "#c4bcb0"))
        self.assertEqual((chrome["metallic"], chrome["roughness"]), (0.8, 0.2))

    def test_layers_default_by_class(self) -> None:
        self.assertEqual(_props.prop_layer(LIB, {"class": "clutter"}), "detail")
        self.assertEqual(_props.prop_layer(LIB, {"class": "room"}), "base")
        self.assertEqual(_props.prop_layer(LIB, {"class": "clutter", "layer": "base"}), "base")
        self.assertTrue(all(_props.prop_layer(LIB, p) == "detail" for p in LIB["prop"] if p["class"] == "clutter"))

    def test_a_detail_prop_has_no_collider(self) -> None:
        def edit(lib):
            next(p for p in lib["prop"] if p["id"] == "armchair")["layer"] = "detail"
        self.assertIn("prop armchair: a detail-layer prop has no collider (the presets never change what blocks)",
                      _problems(edit))

    def test_an_unknown_layer_is_refused(self) -> None:
        def edit(lib):
            next(p for p in lib["prop"] if p["id"] == "armchair")["layer"] = "ultra"
            lib["layers"]["clutter"] = "fine"
            lib["layers"]["giant"] = "base"
        problems = _problems(edit)
        self.assertIn("prop armchair: layer 'ultra' is not one of ('base', 'detail')", problems)
        self.assertIn("layers: clutter = 'fine' is not one of ('base', 'detail')", problems)
        self.assertIn("layers: giant is not a class in [budgets]", problems)

    def test_the_style_is_checked(self) -> None:
        def edit(lib):
            lib["style"]["plinth_m"] = -0.1
            lib["style"]["bevel_small_m"] = 0.05
            lib["style"]["handle"] = "knob"
            lib["style"]["segments"] = 4
            lib["style"]["floor_shade"] = [1.5]
            lib["style"]["paints"].append("unobtainium")
        problems = _problems(edit)
        for text in ("style: plinth_m must be a length in metres (0 to 2), not -0.1",
                     "style: bevel_small_m is over bevel_m", "style: handle 'knob' is not one of ('bar',)",
                     "style: segments must be a whole number from 6 to 32",
                     "style: floor_shade must be [factor 0..1, height in metres]",
                     "style: paint 'unobtainium' is no role"):
            self.assertIn(text, problems)

    def test_the_fine_pack_is_checked(self) -> None:
        def edit(lib):
            lib["fine"]["tiers"] = {"high": 512, "low": 1000}
            lib["fine"]["layers"].append({"name": "stone", "roughness": 0.5})
            lib["fine"]["layers"].append({"name": "marble", "source": "Marble999", "roughness": 0.3,
                                          "normal_strength": 0.2})
            lib["fine"]["layers"].append({"name": "satin", "roughness": 1.5, "normal_strength": 0.2})
            lib["roles"]["wood_front"]["layer"] = "walnut"
            lib["roles"]["wood_mid"]["layer"] = "wood_front"
            lib["material_props"]["glass_tint"]["alpha"] = 2
            lib["material_props"]["plaster"] = {"roughness": 0.5}
        problems = _problems(edit)
        for text in ("fine: tiers must be high > low, powers of two of at least 64 px, not {'high': 512, 'low': 1000}",
                     "fine: layer stone twice",
                     "fine: layer marble: Marble999 is not in the source record's raw files",
                     "fine: layer satin: roughness 1.5 is not 0 to 1",
                     "fine: flat layer satin has a normal_strength but no source",
                     "role wood_front: layer 'walnut' is not a layer of [fine]",
                     "role wood_mid: a layer belongs to roles on the fine pack",
                     "material_props: glass_tint.alpha = 2 (roughness, metallic, alpha: 0 to 1)",
                     "material_props: plaster is not in new_materials"):
            self.assertIn(text, problems)

    def test_at_most_sixteen_fine_layers(self) -> None:
        def edit(lib):
            lib["fine"]["layers"] += [{"name": f"flat{k}", "roughness": 0.5} for k in range(10)]
        self.assertIn("fine: 19 layers (1 to 16: the vertex alpha holds them)", _problems(edit))

    def test_textured_layers_come_first(self) -> None:
        def edit(lib):
            lib["fine"]["layers"].append({"name": "late", "source": "Wood092", "roughness": 0.5,
                                          "normal_strength": 0.2})
        self.assertIn("fine: the textured layers come first, at most four (the shader's four detail channels)",
                      _problems(edit))
