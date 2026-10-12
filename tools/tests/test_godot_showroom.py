"""The showroom command (docs/godot.md, art #140): its variants, spec, GPU table and the recommended look presets,
and that the committed godot/showroom/look_presets.json is what `showroom --write-presets` writes."""

from __future__ import annotations

import json
import unittest

from runner import common
from runner.commands import _showroom


class VariantsTest(unittest.TestCase):
    def test_every_variant_sets_every_key(self) -> None:
        for v in _showroom.VARIANTS:
            self.assertEqual(set(_showroom.KEYS) - set(v), set(), v["id"])
        self.assertLessEqual(len(_showroom.VARIANTS), 6)
        self.assertEqual(len({v["id"] for v in _showroom.VARIANTS}), len(_showroom.VARIANTS))

    def test_the_first_is_the_frames_stand(self) -> None:
        stand = _showroom.VARIANTS[0]
        self.assertEqual((stand["tonemap"], stand["ambient"], stand["reflections"]), ("linear", "color", False))
        self.assertFalse(any(stand[k] for k in _showroom.EFFECTS))

    def test_each_adds_to_the_one_before(self) -> None:
        for a, b in zip(_showroom.VARIANTS, _showroom.VARIANTS[1:]):
            self.assertTrue(all(b[k] for k in _showroom.EFFECTS if a[k]), f"{b['id']} drops an effect of {a['id']}")

    def test_the_catch_light_is_the_presets_catch_light(self) -> None:
        catch = _showroom.LOOK_LIGHTS["catch"]
        self.assertEqual(catch["type"].split(",")[0], "OmniLight3D")
        for v in _showroom.VARIANTS:
            if v["catch_light"]:
                self.assertEqual((v["catch_energy"], v["catch_specular"], v["catch_size"]),
                                 (catch["energy"], catch["specular"], catch["light_size"]), v["id"])
                self.assertGreater(v["catch_size"], 0.0, "a point light's glint on the eyes is under a pixel")

    def test_selection(self) -> None:
        self.assertEqual([v["id"] for v in _showroom.variants("sss,stand")], ["stand", "sss"])
        self.assertEqual(len(_showroom.variants("")), len(_showroom.VARIANTS))
        with self.assertRaisesRegex(ValueError, "unknown variants nope"):
            _showroom.variants("stand,nope")


class SpecTest(unittest.TestCase):
    def test_spec(self) -> None:
        s = _showroom.spec("m1", "CharacterArmature|Idle", "C:/s.hdr", _showroom.variants(), "C:/a.png",
                           _showroom.APPROVED_RECTS)
        self.assertEqual(s["beside_rects"], _showroom.APPROVED_RECTS)
        self.assertEqual(len(s["variants"]), 6)
        self.assertIn("approved Blender", s["face_title"])
        self.assertEqual(s["timing_size"], [1920, 1080])
        plain = _showroom.spec("m1", "Idle", "", _showroom.variants("stand"))
        self.assertEqual((plain["beside"], plain["beside_rects"]), ("", []))

    def test_spec_refuses(self) -> None:
        with self.assertRaisesRegex(ValueError, "crop rectangles"):
            _showroom.spec("m1", "Idle", "", _showroom.variants(), "C:/a.png", [])
        with self.assertRaisesRegex(ValueError, "no variants"):
            _showroom.spec("m1", "Idle", "", [])
        with self.assertRaisesRegex(ValueError, "at most 6"):
            _showroom.spec("m1", "Idle", "", _showroom.variants() * 2)


class TableTest(unittest.TestCase):
    def test_gpu_table(self) -> None:
        rows = [{**_showroom.VARIANTS[0], "gpu_ms": 1.0}, {**_showroom.VARIANTS[3], "gpu_ms": 1.75}]
        lines = _showroom.gpu_table({"timing": rows, "timing_window": [1920, 1080]})
        self.assertEqual(lines[0], "| Variant | Effects | GPU ms (1920x1080) | Step ms |")
        self.assertEqual(lines[2], "| 1 frames stand | linear | 1.00 |  |")
        self.assertEqual(lines[3], "| 4 +SSAO | reflections, catch_light, ssao, agx | 1.75 | +0.75 |")


class PresetsTest(unittest.TestCase):
    def test_presets_grow(self) -> None:
        self.assertEqual(_showroom.preset_problems(), [])
        bad = {"Low": {"effects": ["agx", "ssao"]}, "Medium": {"effects": ["agx"]},
               "High": {"effects": ["agx"]}, "Ultra": {"effects": ["agx"]}}
        self.assertEqual(_showroom.preset_problems(bad), ["Medium drops ssao that Low turns on"])
        self.assertIn("not Low, Medium, High, Ultra", _showroom.preset_problems({"Low": {"effects": []}})[0])

    def test_committed_file_is_current(self) -> None:
        path = common.ROOT / "godot" / "showroom" / "look_presets.json"
        committed = json.loads(path.read_text(encoding="utf-8"))
        timing = [{"id": k, "gpu_ms": v} for k, v in committed.get("measured_gpu_ms", {}).items()]
        self.assertEqual(committed, json.loads(json.dumps(_showroom.presets_document(timing or None))),
                         "run tools/run.py showroom --write-presets")


if __name__ == "__main__":
    unittest.main()
