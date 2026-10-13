"""The showroom command (docs/godot.md, art #140): its variants, spec, GPU table and the recommended look presets,
and that the committed godot/showroom/look_presets.json is what `showroom --write-presets` writes."""

from __future__ import annotations

import json
import unittest

from runner import common, house_bake
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
        with self.assertRaisesRegex(ValueError, "at most 8"):
            _showroom.spec("m1", "Idle", "", _showroom.variants() * 2)

    def test_tuning_spec_is_wider(self) -> None:
        s = _showroom.spec("m1", "Idle", "", _showroom.variants("", "tune"), "C:/a.png", _showroom.APPROVED_RECTS)
        self.assertEqual((s["face_cols"], s["body_cols"]), (6, 4))
        self.assertEqual(s["variants"][3]["key_color"], _showroom.kelvin_rgb(4000))
        ladder = _showroom.spec("m1", "Idle", "", _showroom.variants(), "C:/a.png", _showroom.APPROVED_RECTS)
        self.assertEqual((ladder["face_cols"], ladder["face_cell"], ladder["body_cols"]), (4, [256, 320], 3))
        self.assertEqual(ladder["variants"][0]["key_color"], [1.0, 1.0, 1.0])


class TuningTest(unittest.TestCase):
    def test_every_tuning_variant_sets_every_key(self) -> None:
        self.assertLessEqual(len(_showroom.TUNING), _showroom.MAX_VARIANTS)
        for v in _showroom.TUNING:
            self.assertEqual(set(v) - {"id", "label"}, set(_showroom.KEYS), v["id"])
        self.assertEqual(len({v["id"] for v in _showroom.TUNING}), len(_showroom.TUNING))

    def test_the_base_is_variant_4(self) -> None:
        base = {k: v for k, v in _showroom.TUNING[0].items() if k not in ("id", "label")}
        self.assertEqual(base, {**_showroom._LIT_STEP1, "ssao": True}, "T1 is step 1's variant 4")
        self.assertEqual(_showroom.TUNING[1]["catch_size"], _showroom.CATCH_STEP1["catch_size"])

    def test_the_ladder_takes_the_recommendation(self) -> None:
        four = _showroom.variants("ssao")[0]
        t3, t6 = _showroom.variants("t3,t6", "tune")
        w3, w4 = _showroom.variants("w3,w4", "warm")
        for key in ("clay_specular", "key_energy", "key_kelvin", "agx_contrast", "exposure"):
            self.assertEqual(four[key], t3[key], key)
        for key in ("sky_contribution", "ambient_color", "ambient_energy"):
            self.assertEqual(four[key], w3[key], key)
        self.assertEqual(four["fill_energy"], w4["fill_energy"])
        env = _showroom.presets_document()["environment"]
        self.assertEqual(
            (env["ambient_light_sky_contribution"], env["ambient_light_color"], env["ambient_light_energy"]),
            (w3["sky_contribution"], w3["ambient_color"], w3["ambient_energy"]))
        self.assertEqual(_showroom.presets_document()["lights"]["fill"]["energy"], w4["fill_energy"])
        for key in ("eye_roughness", "catch_energy", "catch_size"):
            self.assertEqual(four[key], t6[key], key)
        materials = _showroom.presets_document()["materials"]
        self.assertEqual((materials["clay_metallic_specular"], materials["eye_roughness"]),
                         (four["clay_specular"], four["eye_roughness"]))

    def test_grids(self) -> None:
        self.assertEqual([v["id"] for v in _showroom.variants("t2,t1", "tune")], ["t1", "t2"])
        with self.assertRaisesRegex(ValueError, "unknown grid nope"):
            _showroom.variants("", "nope")
        with self.assertRaisesRegex(ValueError, "unknown variants stand"):
            _showroom.variants("stand", "tune")


class ColourTest(unittest.TestCase):
    def test_kelvin(self) -> None:
        self.assertEqual(_showroom.kelvin_rgb(0), [1.0, 1.0, 1.0])
        warm = _showroom.kelvin_rgb(4000)
        self.assertEqual(warm[0], 1.0)
        self.assertGreater(warm[1], warm[2])
        self.assertAlmostEqual(warm[1], 0.81, delta=0.02)
        self.assertAlmostEqual(warm[2], 0.65, delta=0.02)
        self.assertLess(_showroom.kelvin_rgb(3500)[2], warm[2], "lower is warmer")
        day = _showroom.kelvin_rgb(6600)
        self.assertGreater(min(day), 0.95)
        self.assertEqual(_showroom.kelvin_rgb(10)[2], 0.0)

    def test_layout(self) -> None:
        self.assertEqual(_showroom.layout(14, True), (4, list(_showroom.FACE_CELL)))
        self.assertEqual(_showroom.layout(18, True), (6, list(_showroom.FACE_CELL_WIDE)))
        self.assertEqual(_showroom.layout(6, False), (3, list(_showroom.BODY_CELL)))
        self.assertEqual(_showroom.layout(8, False), (4, list(_showroom.BODY_CELL_WIDE)))


def lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """A stand-in for house_bake.srgb_lab: the tests give CIELAB triples directly as 'pixels'."""
    return float(r), float(g), float(b)


class MeasuresTest(unittest.TestCase):
    def test_tone(self) -> None:
        self.assertEqual(_showroom.tone(80.0, 0.5, 1.0), "", "the grey background")
        self.assertEqual(_showroom.tone(95.0, -1.0, 2.0), "", "an eye white")
        self.assertEqual(_showroom.tone(45.0, -6.0, 25.0), "", "the olive shirt (hue over 85)")
        self.assertEqual(_showroom.tone(25.0, 12.0, 20.0), "hair")
        self.assertEqual(_showroom.tone(58.0, 12.0, 17.0), "hair", "pale but saturated brown")
        self.assertEqual(_showroom.tone(82.0, 5.0, 9.0), "skin")
        self.assertEqual(_showroom.tone(60.0, 6.0, 9.0), "skin", "skin in shade: mid and unsaturated")

    def test_face_measures(self) -> None:
        px = [(90, 4, 8)] * 50 + [(70, 4, 8)] * 50 + [(30, 10, 20)] * 40 + [(80, 0, 0)] * 60
        m = _showroom.face_measures(len(px), 1, px, lab)
        self.assertEqual(m["skin_L"], 80.0)
        self.assertEqual(m["shade"], 20.0)
        self.assertEqual(m["hair_L"], 30.0)
        self.assertAlmostEqual(m["skin_C"], 8.9, delta=0.05)
        few = _showroom.face_measures(10, 1, [(90, 4, 8)] * 10, lab)
        self.assertNotEqual(few["skin_L"], few["skin_L"], "too few samples: nan")

    def test_table_and_distance(self) -> None:
        blender = {"skin_L": 80.0, "skin_C": 12.0, "shade": 20.0, "hair_L": 30.0}
        pale = {"skin_L": 86.0, "skin_C": 8.0, "shade": 10.0, "hair_L": 50.0}
        self.assertEqual(_showroom.distance(pale, blender), 40.0)
        self.assertEqual(_showroom.mean_measures([blender, pale]),
                         {"skin_L": 83.0, "skin_C": 10.0, "shade": 15.0, "hair_L": 40.0})
        lines = _showroom.look_table(blender, [("T1 base", pale)])
        self.assertEqual(lines[2], "| Blender (approved) | 80.0 | 12.0 | 20.0 | 30.0 | 0 |")
        self.assertEqual(lines[3], "| T1 base | 86.0 (+6.0) | 8.0 (-4.0) | 10.0 (-10.0) | 50.0 (+20.0) | 40.0 |")


class WarmTest(unittest.TestCase):
    def test_every_warm_variant_sets_every_key_and_names_its_parent(self) -> None:
        self.assertLessEqual(len(_showroom.WARM), _showroom.MAX_VARIANTS)
        ids = [v["id"] for v in _showroom.WARM]
        self.assertEqual(len(set(ids)), len(ids))
        for i, v in enumerate(_showroom.WARM):
            self.assertEqual(set(v) - {"id", "label", "parent"}, set(_showroom.KEYS), v["id"])
            self.assertTrue(v["parent"] == "" or v["parent"] in ids[:i], f"{v['id']}: parent before it")

    def test_the_base_is_ladder_variant_5(self) -> None:
        base = {k: v for k, v in _showroom.WARM[0].items() if k not in ("id", "label", "parent")}
        self.assertEqual(base, {**_showroom._LIT_STEP2, "ssao": True, "soft_shadows": True}, "step 2's variant 5")

    def test_each_changes_its_parent(self) -> None:
        by_id = {v["id"]: v for v in _showroom.WARM}
        for v in _showroom.WARM[1:]:
            parent = by_id[v["parent"]]
            self.assertTrue(any(v[k] != parent[k] for k in _showroom.KEYS), v["id"])

    def test_pixel_change(self) -> None:
        a = [(10, 10, 10)] * 8
        b = [(10, 10, 10)] * 4 + [(10, 12, 10), (10, 13, 10), (0, 0, 0), (10, 10, 10)]
        self.assertEqual(_showroom.pixel_change(a, b, 2), 0.25, "only differences over 2 count")
        self.assertEqual(_showroom.pixel_change(a, b, 2, skip_rows=3), 0.5, "the label rows are skipped")
        self.assertEqual(_showroom.pixel_change(a, b, 2, skip_rows=9), 0.0)
        with self.assertRaisesRegex(ValueError, "shots of 8 and 2 pixels"):
            _showroom.pixel_change(a, a[:2], 2)

    def test_pixel_change_only(self) -> None:
        a = [(10, 10, 10)] * 8
        b = [(10, 10, 10)] * 4 + [(10, 12, 10), (10, 13, 10), (0, 0, 0), (10, 10, 10)]
        self.assertEqual(_showroom.pixel_change(a, b, 2, only=[0, 1, 2, 7]), 0.0, "the change outside is not counted")
        self.assertEqual(_showroom.pixel_change(a, b, 2, only=[5, 6]), 1.0)
        self.assertEqual(_showroom.pixel_change(a, b, 2, skip_rows=3, only=[1, 6, 7]), 0.5, "the label rows are skipped")
        self.assertEqual(_showroom.pixel_change(a, b, 2, only=[]), 0.0)

    def test_skin_pixels(self) -> None:
        skin, grey = (200, 160, 130), (128, 128, 128)
        px = [skin, grey, grey, skin]
        lab = house_bake.srgb_lab
        self.assertEqual(_showroom.tone(*lab(*skin)), "skin")
        self.assertEqual(_showroom.skin_pixels(2, 2, px, lab), [0, 3])

    def test_change_table(self) -> None:
        lines = _showroom.change_table([("W2 sky", "W1 base", [0.0, 0.004, 0.89]),
                                        ("W3 share", "W1 base", [0.42, 0.40, 0.81]),
                                        ("W9 none", "W1 base", [0.0, 0.0, 0.001])])
        self.assertEqual(lines[0], "| Variant | Against | Face front skin | Face 3/4 skin | Body shot | Reaches the face |")
        self.assertEqual(lines[2], "| W2 sky | W1 base | 0.0 % | 0.4 % | 89.0 % | no: the body only |")
        self.assertEqual(lines[3], "| W3 share | W1 base | 42.0 % | 40.0 % | 81.0 % | yes |")
        self.assertEqual(lines[4], "| W9 none | W1 base | 0.0 % | 0.0 % | 0.1 % | no: a no-op |")


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

    def test_shadow_filter_levels(self) -> None:
        levels = [p["project_settings"][_showroom.SHADOW_FILTER_SETTING] for p in _showroom.PRESETS.values()]
        self.assertEqual(levels, [2, 3, 4, 4])
        self.assertEqual(_showroom.SHADOW_FILTER[2], "low")
        bad = {n: {"effects": [], "project_settings": {_showroom.SHADOW_FILTER_SETTING: q}}
               for n, q in zip(["Low", "Medium", "High", "Ultra"], [3, 2, 4, 6])}
        self.assertEqual(_showroom.preset_problems(bad), ["Ultra: soft shadow filter 6 is not one of 0 to 5",
                                                          "Medium's soft shadow filter 2 is below Low's 3"])

    def test_the_presets_say_they_are_a_proposal(self) -> None:
        doc = _showroom.presets_document()
        self.assertEqual(next(iter(doc)), "status")
        self.assertTrue(doc["status"].startswith("PROPOSAL, NOT CHOSEN"))
        self.assertEqual(doc["environment"]["ambient_light_energy"], _showroom.variants("ssao")[0]["ambient_energy"])

    def test_docs_name_the_shadow_filter_levels(self) -> None:
        docs = (common.ROOT / "docs" / "godot.md").read_text(encoding="utf-8")
        for name, preset in _showroom.PRESETS.items():
            level = preset["project_settings"][_showroom.SHADOW_FILTER_SETTING]
            row = next(ln for ln in docs.splitlines() if ln.startswith(f"| {name} | "))
            self.assertIn(f"filter {level} ({_showroom.SHADOW_FILTER[level]})", row, name)

    def test_committed_file_is_current(self) -> None:
        path = common.ROOT / "godot" / "showroom" / "look_presets.json"
        committed = json.loads(path.read_text(encoding="utf-8"))
        timing = [{"id": k, "gpu_ms": v} for k, v in committed.get("measured_gpu_ms", {}).items()]
        self.assertEqual(committed, json.loads(json.dumps(_showroom.presets_document(timing or None))),
                         "run tools/run.py showroom --write-presets")


if __name__ == "__main__":
    unittest.main()
