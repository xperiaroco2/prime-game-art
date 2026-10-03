"""The `stylize-quaternius` command (art #14): its plan, presets, export check and gate verdicts in plain Python; the
Blender build on a small fixture with the Quaternius bone names (skipped without Blender); and every preset of the
real Superhero_Male_FullBody.gltf with all its gates (skipped when Blender or the file in the raw folder is
missing)."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import struct
import unittest
from pathlib import Path

from runner import blender, cli, common, pins
from runner.commands import _contract, _stylize, check

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


def glb(nodes: list[dict]) -> bytes:
    """A GLB with only a JSON chunk, enough for glb_meshes."""
    body = json.dumps({"asset": {"version": "2.0"}, "nodes": nodes}).encode("utf-8")
    body += b" " * (-len(body) % 4)
    return struct.pack("<4sII", b"glTF", 2, 20 + len(body)) + struct.pack("<I4s", len(body), b"JSON") + body


class PlanTest(unittest.TestCase):
    def plan(self, preset: str) -> dict:
        return _stylize.plan(preset, Path("in.gltf"), Path("out"))

    def test_only_the_issues_bones_grow_along_their_length(self) -> None:
        for preset, settings in _stylize.PRESETS.items():
            for region, (across, along) in settings["scale"].items():
                with self.subTest(preset=preset, region=region):
                    self.assertLessEqual(across, 1.0)
                    if region in _stylize.LENGTHENED:
                        self.assertGreater(along, 1.0)
                    else:
                        self.assertLessEqual(along, 1.0)

    def test_hands_feet_and_fingers_are_never_scaled(self) -> None:
        names = _stylize.source_names(_contract.load_map("quaternius"))
        kept = {names[b] for b in names if any(k in b for k in ("Hand", "Foot", "Toes", "Thumb", "Index", "Middle",
                                                                     "Ring", "Little"))}
        for preset in _stylize.PRESETS:
            with self.subTest(preset=preset):
                self.assertFalse(kept & set(self.plan(preset)["scale"]))

    def test_the_base_head_is_10_to_15_percent_bigger(self) -> None:
        self.assertTrue(1.10 <= _stylize.PRESETS["base"]["head"] <= 1.15)

    def test_lanky_is_longer_and_thinner_than_base(self) -> None:
        # The batch 2 review found the old presets 3.5 mm (median) from base: they only narrowed the widths.
        base, lanky = _stylize.PRESETS["base"]["scale"], _stylize.PRESETS["lanky"]["scale"]
        for region in _stylize.LENGTHENED:
            with self.subTest(region=region):
                self.assertGreaterEqual(lanky[region][1], base[region][1] * 1.08)
                self.assertLess(lanky[region][0], base[region][0])

    def test_bighead_has_a_clearly_bigger_head(self) -> None:
        self.assertGreaterEqual(_stylize.PRESETS["bighead"]["head"], _stylize.PRESETS["base"]["head"] + 0.1)

    def test_the_triangle_target_is_the_contracts_body_target(self) -> None:
        contract = _contract.load_contract()
        self.assertEqual(_stylize.TARGET_TRIANGLES, contract["budgets"]["body"]["triangles_target"])

    def test_bones_are_named_as_in_the_rig(self) -> None:
        plan = self.plan("base")
        self.assertEqual(plan["head_bone"], "Head")
        self.assertEqual(plan["neck_bone"], "neck_01")
        self.assertEqual(plan["scale"]["thigh_l"], [0.8, 1.1])
        self.assertEqual(plan["scale"]["neck_01"][1], 1.5)
        self.assertEqual(plan["fingers"]["Right"]["Thumb"], ["thumb_01_r", "thumb_02_r", "thumb_03_r"])
        self.assertEqual(plan["joints"]["knee"], ["calf_l", "calf_r"])
        self.assertEqual(plan["face_bones"], ["Jaw", "LeftEye", "RightEye"])

    def test_the_trunk_and_every_limb_get_a_smooth_tube_to_the_next_joint(self) -> None:
        tubes = self.plan("base")["tubes"]
        self.assertEqual(tubes[0]["name"], "trunk")
        self.assertEqual((tubes[0]["start"], tubes[0]["end"]), ("pelvis", "neck_01"))
        ends = {t["start"]: t["end"] for t in tubes[1:]}
        self.assertEqual(ends["upperarm_l"], "lowerarm_l")
        self.assertEqual(ends["lowerarm_r"], "hand_r")
        self.assertEqual(ends["calf_l"], "foot_l")
        self.assertEqual(ends["neck_01"], "Head")
        self.assertTrue(all(t["degree"] == 1 for t in tubes[1:]))  # limbs taper straight

    def test_one_palette_with_skin_and_briefs_in_their_own_cells(self) -> None:
        palette = self.plan("lanky")["palette"]
        self.assertEqual(set(palette["colours"]), {"skin", "briefs"})
        cells = [c["cell"] for c in palette["colours"].values()]
        self.assertEqual(len(set(cells)), len(cells))
        self.assertTrue(all(0 <= c < palette["cells"] ** 2 for c in cells))

    def test_only_presets_other_than_base_are_measured_against_base(self) -> None:
        def against(preset: str) -> str | None:
            return _stylize.plan(preset, Path("in.gltf"), Path("out"), base_positions=Path("base.npy"))["base_positions"]

        self.assertIsNone(against("base"))
        self.assertEqual(against("bighead"), "base.npy")

    def test_drops_the_face_meshes_and_names_the_body(self) -> None:
        plan = self.plan("lanky")
        self.assertEqual(plan["drop_objects"], ["Icosphere", "Eyes", "Eyebrows"])
        self.assertEqual(plan["body_name"], "Body")

    def test_refuses_an_unknown_preset(self) -> None:
        with self.assertRaises(common.Failure):
            self.plan("chunky")

    def test_the_default_source_and_output_are_in_the_raw_folder(self) -> None:
        self.assertEqual(SOURCE.name, "Superhero_Male_FullBody.gltf")
        self.assertEqual(_stylize.default_out(), common.raw_dir() / "restyled")

    def test_the_command_refuses_a_missing_source(self) -> None:
        code, output = run_cli("stylize-quaternius", "--source", str(OUT / "missing.gltf"))
        self.assertEqual(code, 1)
        self.assertIn("no Quaternius model", output)


class ExportCheckTest(unittest.TestCase):
    """The export check: a GLB may hold the body's mesh and nothing else (the batch 2 review's stray Icosphere)."""

    def setUp(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, nodes: list[dict]) -> Path:
        path = OUT / name
        path.write_bytes(glb(nodes))
        return path

    def test_reads_the_mesh_nodes_only(self) -> None:
        path = self.write("body.glb", [{"name": "Armature"}, {"name": "Body", "mesh": 0}, {"name": "root"}])
        self.assertEqual(_stylize.glb_meshes(path), ["Body"])
        self.assertEqual(_stylize.stray_meshes(_stylize.glb_meshes(path)), [])

    def test_any_other_mesh_is_stray(self) -> None:
        path = self.write("stray.glb", [{"name": "Body", "mesh": 0}, {"name": "Icosphere", "mesh": 1}])
        self.assertEqual(_stylize.stray_meshes(_stylize.glb_meshes(path)), ["Icosphere"])

    def test_refuses_a_file_that_is_not_a_glb(self) -> None:
        path = OUT / "not.glb"
        path.write_bytes(b"{}")
        with self.assertRaises(common.Failure):
            _stylize.glb_meshes(path)


def passing_info(preset: str = "base") -> dict:
    measure = {"meshes": ["Body"], "materials": ["Palette"], "height": 1.7498, "lowest": 0.0001,
               "soles_centre": [0.0, 0.0], "eye_height": 1.62, "head_ratio": 0.12833 * 1.125, "triangles": 6000,
               "bone_lengths_per_height": {b: 0.2 for b in _stylize.LANKY_BONES}}
    info = {"preset": preset, "source_head_ratio": 0.12833, "head_ratio_target": 1.125, "target_triangles": 6000,
            "check": {"results": [{"check": "triangles", "status": "pass", "detail": ""}]}, "measure": measure,
            "defects": {"open_edges": 0, "non_manifold_edges": 0,
                        "hands": {side: {"five_separate": True, "fingers_per_island": [[f] for f in _stylize.FINGERS]}
                                  for side in ("left", "right")}}}
    if preset != "base":
        info["shift_from_base"] = {"median": 0.02}
        info["base_measure"] = json.loads(json.dumps(measure))
        if preset == "lanky":
            measure["bone_lengths_per_height"] = {b: 0.21 for b in _stylize.LANKY_BONES}
            info["head_ratio_target"] = 1.1
            measure["head_ratio"] = 0.12833 * 1.1
        if preset == "bighead":
            info["head_ratio_target"] = 1.25
            measure["head_ratio"] = 0.12833 * 1.25
    return info


class GateVerdictTest(unittest.TestCase):
    """Which finished bodies stylize-quaternius refuses."""

    def test_a_good_body_passes(self) -> None:
        for preset in _stylize.PRESETS:
            with self.subTest(preset=preset):
                self.assertEqual(_stylize.gate_failures(passing_info(preset)), [])

    def failures(self, info: dict) -> str:
        return "\n".join(_stylize.gate_failures(info))

    def test_a_failed_contract_check(self) -> None:
        info = passing_info()
        info["check"]["results"].append({"check": "missing_bones", "status": "fail", "detail": "missing: Jaw"})
        self.assertIn("missing_bones", self.failures(info))

    def test_the_wrong_height_eyes_or_head(self) -> None:
        for key, value, words in (("height", 1.8, "height"), ("eye_height", 1.5, "eyes"),
                                  ("head_ratio", 0.12833, "head")):
            with self.subTest(key=key):
                info = passing_info()
                info["measure"][key] = value
                self.assertIn(words, self.failures(info))

    def test_a_stray_mesh_or_a_second_material(self) -> None:
        info = passing_info()
        info["measure"]["meshes"] = ["Body", "Icosphere"]
        info["measure"]["materials"] = ["Palette", "Skin"]
        self.assertIn("meshes", self.failures(info))
        self.assertIn("materials", self.failures(info))

    def test_fused_fingers_or_holes(self) -> None:
        info = passing_info()
        info["defects"]["hands"]["left"] = {"five_separate": False, "fingers_per_island": [["Index", "Middle"]]}
        info["defects"]["open_edges"] = 3
        self.assertIn("left hand", self.failures(info))
        self.assertIn("3 open edges", self.failures(info))

    def test_a_preset_that_changes_too_little(self) -> None:
        info = passing_info("lanky")
        info["shift_from_base"] = {"median": 0.0035}  # the batch 2 presets
        self.assertIn("changes too little", self.failures(info))

    def test_a_preset_never_measured_against_base(self) -> None:
        info = passing_info("bighead")
        del info["shift_from_base"]
        self.assertIn("not measured against base", self.failures(info))

    def test_lanky_limbs_no_longer_than_base(self) -> None:
        info = passing_info("lanky")
        info["measure"]["bone_lengths_per_height"]["LeftLowerLeg"] = 0.2
        self.assertIn("LeftLowerLeg", self.failures(info))

    def test_a_bighead_no_bigger_than_base(self) -> None:
        info = passing_info("bighead")
        info["base_measure"]["head_ratio"] = info["measure"]["head_ratio"]
        self.assertIn("head only", self.failures(info))


@unittest.skipUnless(HAVE_BLENDER, SKIP)
class FixtureTest(unittest.TestCase):
    """The build on the contract's box-per-bone fixture with Quaternius names: small, fast, without a face."""

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
        cls.out = OUT / "fixture" / "out"
        cls.code, cls.output = run_cli("stylize-quaternius", "--source", str(cls.fixture), "--preset", "lanky",
                                       "--out", str(cls.out), "--triangles", "600", "--no-gates")
        info = cls.out / "lanky" / "info.json"
        cls.info = json.loads(info.read_text(encoding="utf-8")) if info.is_file() else {}

    def test_exits_zero(self) -> None:
        self.assertEqual(self.code, 0, self.output)

    def test_writes_the_glb_with_only_the_body_and_the_working_blend(self) -> None:
        self.assertEqual(_stylize.glb_meshes(Path(self.info["glb"])), ["Body"])
        self.assertTrue(Path(self.info["blend"]).is_file())
        self.assertFalse(Path(self.info["blend"]).with_suffix(".blend1").exists())

    def test_adds_the_face_bones_and_decimates(self) -> None:
        self.assertEqual(sorted(self.info["face_bones"]), ["Jaw", "LeftEye", "RightEye"])
        self.assertLessEqual(self.info["triangles"], 600)

    def test_the_renamed_fixture_has_every_profile_bone(self) -> None:
        report = OUT / "fixture" / "check.json"
        with contextlib.redirect_stdout(io.StringIO()):
            check.run(argparse.Namespace(model=self.info["glb"], kind="body", slot=None, map=None, report=str(report)))
        results = {r["check"]: r["status"] for r in json.loads(report.read_text(encoding="utf-8"))["results"]}
        self.assertEqual(results["missing_bones"], "pass")
        self.assertEqual(results["extra_bones"], "pass")
        self.assertEqual(results["height"], "pass")


@unittest.skipUnless(HAVE_SOURCE, SKIP_SOURCE)
class RealSourceTest(unittest.TestCase):
    """Every preset of the real body with every gate (about a minute and a half)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = OUT / "real"
        shutil.rmtree(cls.root, ignore_errors=True)
        cls.code, cls.output = run_cli("stylize-quaternius", "--out", str(cls.root), "--cell", "128")
        cls.info = {}
        for preset in _stylize.PRESETS:
            path = cls.root / preset / "info.json"
            cls.info[preset] = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def test_exits_zero_with_every_gate_passing(self) -> None:
        self.assertEqual(self.code, 0, self.output)
        for preset, info in self.info.items():
            with self.subTest(preset=preset):
                self.assertEqual(_stylize.gate_failures(info), [])

    def test_is_175_cm_on_the_ground_centred_with_the_eyes_near_160(self) -> None:
        for preset, info in self.info.items():
            with self.subTest(preset=preset):
                measure = info["measure"]
                self.assertAlmostEqual(measure["height"], 1.75, delta=0.002)
                self.assertAlmostEqual(measure["lowest"], 0.0, delta=0.002)
                self.assertTrue(all(abs(v) < 0.01 for v in measure["soles_centre"]))
                self.assertAlmostEqual(measure["eye_height"], 1.6, delta=0.05)

    def test_the_contract_check_passes_without_a_failure(self) -> None:
        for preset, info in self.info.items():
            with self.subTest(preset=preset):
                failed = [r for r in info["check"]["results"] if r["status"] == "fail"]
                self.assertEqual(failed, [])
                self.assertEqual(info["check_exit_code"], 0)

    def test_one_body_mesh_one_palette_about_6000_triangles(self) -> None:
        for preset, info in self.info.items():
            with self.subTest(preset=preset):
                self.assertEqual(_stylize.glb_meshes(Path(info["glb"])), ["Body"])
                self.assertEqual(info["measure"]["materials"], ["Palette"])
                self.assertTrue(5400 <= info["measure"]["triangles"] <= 6600, info["measure"]["triangles"])

    def test_five_separate_fingers_and_a_closed_skin(self) -> None:
        for preset, info in self.info.items():
            with self.subTest(preset=preset):
                defects = info["defects"]
                self.assertEqual((defects["open_edges"], defects["non_manifold_edges"]), (0, 0))
                for hand in defects["hands"].values():
                    self.assertEqual(hand["fingers_per_island"], [[f] for f in sorted(_stylize.FINGERS)])

    def test_the_presets_really_differ_from_base(self) -> None:
        base = self.info["base"]["measure"]
        for preset in ("lanky", "bighead"):
            with self.subTest(preset=preset):
                self.assertGreaterEqual(self.info[preset]["shift_from_base"]["median"], _stylize.MIN_PRESET_SHIFT)
        lanky = self.info["lanky"]["measure"]["bone_lengths_per_height"]
        for bone in _stylize.LANKY_BONES:
            self.assertGreaterEqual(lanky[bone] / base["bone_lengths_per_height"][bone], _stylize.MIN_LANKY_GAIN)
        self.assertGreaterEqual(self.info["bighead"]["measure"]["head_ratio"] / base["head_ratio"],
                                _stylize.MIN_BIGHEAD_GAIN)

    def test_renders_every_gate(self) -> None:
        for preset in _stylize.PRESETS:
            folder = self.root / preset
            for name in ("sheet/sheet.png", "closeups/head.png", "closeups/hands.png", "poses.png", "lineup.png",
                         "lineup_x4.png", f"restyled_{preset}.blend"):
                with self.subTest(preset=preset, file=name):
                    self.assertTrue((folder / name).is_file())
        self.assertTrue((self.root / "lineup_x4.png").is_file())
