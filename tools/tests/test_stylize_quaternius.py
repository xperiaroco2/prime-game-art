"""The `stylize-quaternius` command: its plan in plain Python, the Blender script on a small fixture with the
Quaternius bone names (skipped without Blender), and the real Superhero_Male_FullBody.gltf (skipped when it is not in
the raw folder)."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import unittest
from pathlib import Path

from runner import blender, cli, common, pins
from runner.commands import _contract, _stylize

OUT = common.OUT / "tests" / "stylize"
HAVE_BLENDER = bool((path := common.tool_path(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)) and path.is_file())
SKIP = f"Blender {pins.BLENDER} not found at {path}; set {pins.BLENDER_ENV} or install it there"
SOURCE = _stylize.default_source()
HAVE_SOURCE = HAVE_BLENDER and SOURCE.is_file()
SKIP_SOURCE = SKIP if not HAVE_BLENDER else f"no Quaternius model at {SOURCE} (the raw folder): skipping the real run"


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class PlanTest(unittest.TestCase):
    def plan(self, preset: str) -> dict:
        return _stylize.plan(preset, Path("in.gltf"), Path("out.glb"), Path("info.json"))

    def test_presets_stay_in_the_issues_ranges(self) -> None:
        for preset, settings in _stylize.PRESETS.items():
            with self.subTest(preset=preset):
                for region in ("torso", "arm", "leg"):
                    self.assertTrue(0.8 <= settings["slim"][region] <= 0.85, region)  # 15 to 20 percent slimmer
                self.assertTrue(1.1 <= settings["head"] <= 1.15)  # 10 to 15 percent bigger
                self.assertGreater(settings["nose"], 0.0)
                self.assertGreater(settings["soften"], 0)

    def test_the_triangle_target_is_in_range_and_under_the_body_cap(self) -> None:
        self.assertTrue(7000 <= _stylize.TARGET_TRIANGLES <= 9000)
        self.assertLessEqual(_stylize.TARGET_TRIANGLES, 8000)

    def test_bones_are_named_as_in_the_rig(self) -> None:
        plan = self.plan("base")
        self.assertEqual(plan["head_bone"], "Head")
        self.assertEqual(plan["slim"]["spine_01"], 0.83)
        self.assertEqual(plan["slim"]["upperarm_l"], 0.83)
        self.assertEqual(plan["slim"]["calf_r"], 0.84)
        self.assertNotIn("hand_l", plan["slim"])  # hands, fingers and feet keep their size
        self.assertNotIn("foot_r", plan["slim"])
        self.assertEqual(plan["probe_bones"]["LeftIndexProximal"], "index_01_l")
        self.assertEqual(plan["probe_bones"]["RightThumbProximal"], "thumb_02_r")
        self.assertEqual(len(plan["probe_bones"]), 13)
        self.assertIn("pelvis", plan["soften_bones"])
        self.assertNotIn("Head", plan["soften_bones"])

    def test_drops_the_helper_and_the_face(self) -> None:
        self.assertEqual(self.plan("lanky")["drop_objects"], ["Icosphere", "Eyes", "Eyebrows"])

    def test_refuses_an_unknown_preset(self) -> None:
        with self.assertRaises(common.Failure):
            self.plan("chunky")

    def test_the_default_source_and_output_are_in_the_raw_folder(self) -> None:
        self.assertEqual(SOURCE.name, "Superhero_Male_FullBody.gltf")
        self.assertEqual(_stylize.default_out(), common.raw_dir() / "stylized")

    def test_the_command_refuses_a_missing_source(self) -> None:
        code, output = run_cli("stylize-quaternius", "--source", str(OUT / "missing.gltf"))
        self.assertEqual(code, 1)
        self.assertIn("no Quaternius model", output)


@unittest.skipUnless(HAVE_BLENDER, SKIP)
class FixtureTest(unittest.TestCase):
    """The contract's box-per-bone fixture with Quaternius names: small, fast, untextured."""

    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(OUT / "fixture", ignore_errors=True)
        (OUT / "fixture").mkdir(parents=True)
        cls.fixture = OUT / "fixture" / "quaternius_boxes.glb"
        quaternius = _contract.load_map("quaternius")
        spec = OUT / "fixture" / "spec.json"
        spec.write_text(json.dumps({
            "profile": _contract.HUMANOID_JSON.as_posix(), "out": cls.fixture.as_posix(),
            "names": _stylize.source_names(quaternius), "omit": ["Jaw", "LeftEye", "RightEye"],
        }), encoding="utf-8")
        blender.run_script("make_contract_fixture.py", [spec.as_posix()])
        cls.code, cls.output = run_cli("stylize-quaternius", "--source", str(cls.fixture), "--preset", "lanky",
                                       "--out", str(OUT / "fixture" / "out"), "--triangles", "600", "--cell", "128",
                                       "--no-check")
        info = OUT / "fixture" / "out" / "lanky" / "info.json"
        cls.info = json.loads(info.read_text(encoding="utf-8")) if info.is_file() else {}

    def test_exits_zero(self) -> None:
        self.assertEqual(self.code, 0, self.output)

    def test_keeps_every_bone(self) -> None:
        names = set(_stylize.source_names(_contract.load_map("quaternius")).values()) - {"Jaw"}
        self.assertEqual(set(self.info["bones"]), names)

    def test_is_175_cm_tall(self) -> None:
        self.assertAlmostEqual(self.info["height"], 1.75, delta=0.002)

    def test_decimates_to_the_target(self) -> None:
        self.assertLess(self.info["decimate_ratio"], 1.0)
        self.assertLessEqual(self.info["triangles"], 600)
        self.assertGreater(self.info["triangles"], 500)

    def test_every_probe_bone_still_moves_the_skin(self) -> None:
        self.assertEqual([label for label, moved in self.info["probe"].items() if moved <= 0], [])

    def test_untextured_gets_one_flat_skin_and_no_images(self) -> None:
        self.assertEqual(self.info["materials"], ["Skin"])
        self.assertEqual(self.info["images"], 0)

    def test_writes_the_sheet(self) -> None:
        self.assertTrue((OUT / "fixture" / "out" / "lanky" / "sheet" / "sheet.png").is_file())


@unittest.skipUnless(HAVE_SOURCE, SKIP_SOURCE)
class RealSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        out = OUT / "real"
        shutil.rmtree(out, ignore_errors=True)
        cls.code, cls.output = run_cli("stylize-quaternius", "--preset", "base", "--out", str(out), "--no-sheet")
        info, report = out / "base" / "info.json", out / "base" / "check" / "report.json"
        cls.info = json.loads(info.read_text(encoding="utf-8")) if info.is_file() else {}
        cls.report = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}

    def test_exits_zero(self) -> None:
        self.assertEqual(self.code, 0, self.output)

    def test_drops_the_eyes_and_eyebrows(self) -> None:
        self.assertEqual(sorted(name.split(".")[0] for name in self.info["dropped"]), ["Eyebrows", "Eyes"])
        self.assertEqual(self.info["meshes"], ["SuperHero_Male"])

    def test_decimates_into_the_range(self) -> None:
        self.assertTrue(7000 <= self.info["triangles"] <= 8000, self.info["triangles"])

    def test_has_flat_skin_and_shorts_without_textures(self) -> None:
        self.assertEqual(self.info["materials"], ["Shorts", "Skin"])
        self.assertEqual(self.info["images"], 0)
        hem, waist = self.info["shorts_faces_source"]["SuperHero_Male"]["band"]
        self.assertTrue(0.7 < hem < waist < 1.1, (hem, waist))

    def test_the_face_is_blank_and_the_nose_found(self) -> None:
        self.assertGreater(self.info["blank_face"]["smoothed"], 50)
        self.assertIsNotNone(self.info["blank_face"]["mouth"])
        self.assertIsNotNone(self.info["nose"]["tip"])

    def test_the_mouth_is_filled_not_pulled_in(self) -> None:
        # In profile the front between the chin and the philtrum stays near a straight line: collapsing the mouth
        # instead (the first version) left a notch of about 1 cm under the nose; filling it leaves about 3 mm.
        self.assertLess(self.info["blank_face"]["dent"], 0.006)

    def test_face_points_are_in_the_final_figures_metres(self) -> None:
        mouth, tip = self.info["blank_face"]["mouth"][2], self.info["nose"]["tip"][2]
        self.assertTrue(mouth < tip < self.info["eye_height"], (mouth, tip, self.info["eye_height"]))
        self.assertTrue(self.info["eye_height"] - 0.12 < mouth, mouth)

    def test_is_175_cm_with_the_eyes_near_160(self) -> None:
        self.assertAlmostEqual(self.info["height"], 1.75, delta=0.002)
        self.assertAlmostEqual(self.info["eye_height"], 1.6, delta=0.05)

    def test_the_rig_and_fingers_still_work(self) -> None:
        self.assertEqual(len(self.info["bones"]), 65)
        self.assertEqual([label for label, moved in self.info["probe"].items() if moved <= 0], [])

    def test_the_check_fails_only_on_the_missing_jaw_and_eyes(self) -> None:
        failed = {r["check"]: r["detail"] for r in self.report["results"] if r["status"] == "fail"}
        self.assertEqual(list(failed), ["missing_bones"], failed)
        for bone in ("Jaw", "LeftEye", "RightEye"):
            self.assertIn(bone, failed["missing_bones"])
        statuses = {r["check"]: r["status"] for r in self.report["results"]}
        for check in ("finger_chains", "weights_per_vertex", "unweighted_vertices", "weighted_bones", "facing",
                      "open_edges", "non_manifold_edges", "height", "feet_at_zero"):
            self.assertEqual(statuses[check], "pass", check)
