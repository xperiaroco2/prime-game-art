"""The assemble command without Blender: recipe lookup, refusals before Blender starts, the regression comparison."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import unittest
from unittest import mock

from runner import cli, common
from runner.commands import _assembly

from .test_assembly_recipe import FakeRaw, mini

REFERENCE = common.ROOT / "tools" / "tests" / "fixtures" / "assembly" / "final_test_reference.json"


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class FindRecipeTest(unittest.TestCase):
    def test_by_name_with_or_without_json(self) -> None:
        self.assertEqual(_assembly.find_recipe("um_final_test").name, "um_final_test.json")
        self.assertEqual(_assembly.find_recipe("um_final_test_neutral.json").name, "um_final_test_neutral.json")
        self.assertEqual(_assembly.find_recipe("recipes/um_final_test.json").name, "um_final_test.json")

    def test_an_unknown_recipe_names_the_recipes(self) -> None:
        code, out = run_cli("assemble", "no_such_recipe")
        self.assertEqual(code, 1)
        self.assertIn("recipes/ has: um_final_test.json, um_final_test_neutral.json", out)


class RefusalsTest(FakeRaw):
    """Each refusal happens before Blender starts (Blender is never needed here)."""

    def run_mini(self, *extra: str, data: dict | None = None) -> tuple[int, str]:
        path = self.write(data or mini())
        with mock.patch.dict(os.environ, {"ART_RAW_DIR": str(self.raw)}), \
                mock.patch("runner.blender.run_script", side_effect=AssertionError("Blender must not start")):
            return run_cli("assemble", str(path), *extra)

    def test_unknown_ids_and_modes(self) -> None:
        code, out = self.run_mini("--ids", "m9_test,x1")
        self.assertEqual(code, 1)
        self.assertIn("unknown ids x1; r.json has: m9_test", out)
        code, out = self.run_mini("--modes", "chars,video")
        self.assertEqual(code, 1)
        self.assertIn("unknown modes video", out)

    def test_res_bounds(self) -> None:
        code, out = self.run_mini("--res", "0")
        self.assertEqual(code, 1)
        self.assertIn("--res must be from 5 to 100", out)

    def test_a_comparison_with_no_character_fails(self) -> None:
        out, ref = self.raw / "out", self.raw / "reference.json"
        ref.write_text("{}", encoding="utf-8")

        def fake_blender(script: str, args: list[str], timeout: float) -> None:
            out.mkdir(exist_ok=True)
            (out / "build_report.json").write_text('{"characters": {}, "crossgender": {}}', encoding="utf-8")

        path = self.write(mini())
        with mock.patch.dict(os.environ, {"ART_RAW_DIR": str(self.raw)}), \
                mock.patch("runner.blender.run_script", side_effect=fake_blender):
            code, text = run_cli("assemble", str(path), "--modes", "crossgender", "--out", str(out), "--compare", str(ref))
        self.assertEqual(code, 1)
        self.assertIn("no character was built, so nothing was compared", text)

    def test_a_broken_recipe_lists_its_problems(self) -> None:
        data = mini()
        data["characters"][0]["shoes"]["object"] = "Punk_Shoes"
        code, out = self.run_mini(data=data)
        self.assertEqual(code, 1)
        self.assertIn("1 problem(s)", out)
        self.assertIn("'Punk_Shoes' is not an object in Men/Punk.glb; it has: Punk_Feet, Punk_Head", out)


class CompareTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ref = json.loads(REFERENCE.read_text(encoding="utf-8"))["characters"]
        # a report in the shape assemble writes, rebuilt from the reference
        self.report = {"characters": copy.deepcopy(self.ref)}

    def test_the_reference_holds_the_four_characters(self) -> None:
        self.assertEqual(sorted(self.ref), ["m1_rex", "m2_walt", "w1_ivy", "w2_nova"])
        self.assertEqual(self.ref["w1_ivy"]["triangles_total"], 8318)
        self.assertEqual(self.ref["w1_ivy"]["probe_posed"]["ankle_R"]["poke_through"], 42)

    def test_identical_reports_match(self) -> None:
        self.assertEqual(_assembly.compare(self.ref, self.report), [])
        self.assertEqual(_assembly.compare({"characters": self.ref}, self.report), [])

    def test_a_subset_of_characters_is_compared(self) -> None:
        del self.report["characters"]["m1_rex"]
        self.assertEqual(_assembly.compare(self.ref, self.report), [])

    def test_differences_outside_the_tolerances(self) -> None:
        walt = self.report["characters"]["m2_walt"]
        walt["triangles"]["hair"] += 2
        walt["height_m"] += 0.002
        walt["seam_overlap_rest"]["neck_mm"] += 0.5
        walt["probe_posed"]["neck"]["see_through"] += 3
        walt["probe_rest"]["waist"]["rays"] += 36
        problems = "\n".join(_assembly.compare(self.ref, self.report))
        for expected in ("m2_walt: triangles", "m2_walt: height_m", "m2_walt: seam neck_mm",
                         "m2_walt: probe_posed.neck.see_through", "m2_walt: probe_rest.waist cast"):
            self.assertIn(expected, problems)

    def test_within_the_tolerances(self) -> None:
        ivy = self.report["characters"]["w1_ivy"]
        ivy["posed_height_m"] += 0.001
        ivy["seam_overlap_rest"]["waist_mm"] += 0.2
        ivy["probe_posed"]["ankle_L"]["poke_through"] += 2
        self.assertEqual(_assembly.compare(self.ref, self.report), [])

    def test_feet_in_a_full_reference_report_is_shoes(self) -> None:
        full = {"characters": {"w2_nova": dict(copy.deepcopy(self.ref["w2_nova"]), objects={})}}
        tri = full["characters"]["w2_nova"]["triangles"]
        tri["feet"] = tri.pop("shoes")
        self.report["characters"] = {"w2_nova": self.report["characters"]["w2_nova"]}
        self.assertEqual(_assembly.compare(full, self.report), [])

    def test_an_unknown_character(self) -> None:
        self.report["characters"]["m3_new"] = self.report["characters"]["m1_rex"]
        self.assertIn("m3_new: not in the reference", _assembly.compare(self.ref, self.report))

    def test_summary_has_one_line_per_character(self) -> None:
        lines = _assembly.summary({"characters": {k: dict(v, seam_overlap_rest=v["seam_overlap_rest"]) for k, v in self.ref.items()}})
        self.assertEqual(len(lines), 4)
        self.assertIn("w1_ivy: height 1.845 m rest, 1.773 m posed; 8318 triangles", lines[2])
        self.assertIn("poke-through 0 rest, 53 posed", lines[2])


if __name__ == "__main__":
    unittest.main()
