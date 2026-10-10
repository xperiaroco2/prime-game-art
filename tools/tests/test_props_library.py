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

    def test_at_most_six_materials(self) -> None:
        self.assertLessEqual(len(set(LIB["materials"].values())), 6)

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
