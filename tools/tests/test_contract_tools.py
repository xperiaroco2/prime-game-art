"""The commands contract, check and rename-bones end to end, in the pinned Godot and Blender. Skipped with a message
when a tool is missing. The fixtures are built by tools/blender/make_contract_fixture.py into tools/out/test-contract/.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runner import blender, cli, common, pins
from runner.commands import _contract

WORK = common.OUT / "test-contract"


def have(env_name: str, default: str | None) -> bool:
    path = common.tool_path(env_name, default)
    return bool(path and path.is_file())


HAVE_GODOT = have(pins.GODOT_ENV, None)
HAVE_BLENDER = have(pins.BLENDER_ENV, pins.BLENDER_DEFAULT)


def run_cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


@unittest.skipUnless(HAVE_GODOT, f"Godot {pins.GODOT} not found: set {pins.GODOT_ENV} to run the contract tests")
class ContractCommandTest(unittest.TestCase):
    def test_committed_contract_matches_godot(self) -> None:
        code, output = run_cli("contract", "--check")
        self.assertEqual(code, 0, output)
        self.assertIn("matches Godot 4.7.2", output)

    def test_check_fails_on_a_stale_file_and_changes_nothing(self) -> None:
        common.OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=common.OUT) as tmp:
            stale = Path(tmp) / "humanoid.json"
            text = _contract.HUMANOID_JSON.read_text(encoding="utf-8").replace('"name": "Jaw"', '"name": "Chin"')
            stale.write_text(text, encoding="utf-8")
            with mock.patch.object(_contract, "HUMANOID_JSON", stale):
                code, output = run_cli("contract", "--check")
            self.assertEqual(code, 1, output)
            self.assertIn("differs from Godot", output)
            self.assertEqual(stale.read_text(encoding="utf-8"), text)


@unittest.skipUnless(HAVE_BLENDER, f"Blender {pins.BLENDER} not found: set {pins.BLENDER_ENV} to run the check tests")
class CheckCommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(WORK, ignore_errors=True)
        WORK.mkdir(parents=True)
        mixamo = _contract.load_map("mixamo")
        to_mixamo = {target: "mixamorig:" + source for source, target in mixamo["rename"].items()}
        cls.good = cls.build("good.glb")
        cls.bad = cls.build(
            "bad.blend",
            defects=["extra_bone", "missing_bone", "five_weights", "ngon", "non_manifold", "too_tall", "backwards"],
        )
        cls.mixamo = cls.build(
            "mixamo.glb",
            names=to_mixamo,
            extra_leaves={"mixamorig:HeadTop_End": "Head", "mixamorig:LeftToe_End": "LeftToes"},
        )
        quaternius = _contract.load_map("quaternius")
        cls.quaternius = cls.build(
            "quaternius.glb",
            names={target: source for source, target in quaternius["rename"].items()},
            extra_leaves={"index_04_leaf_l": "LeftIndexDistal", "ball_leaf_l": "LeftToes"},
            weighted_leaves=["index_04_leaf_l"],
        )

    @staticmethod
    def build(name: str, **spec: object) -> Path:
        out = WORK / name
        spec_path = WORK / f"{out.stem}.spec.json"
        spec_path.write_text(
            json.dumps({"profile": _contract.HUMANOID_JSON.as_posix(), "out": out.as_posix(), **spec}), encoding="utf-8"
        )
        blender.run_script("make_contract_fixture.py", [spec_path.as_posix()])
        return out

    def check(self, model: Path, kind: str, *extra: str) -> tuple[int, dict, str]:
        report_path = WORK / "reports" / f"{model.stem}-{kind}-{'-'.join(extra) or 'plain'}.json"
        code, output = run_cli("check", model.as_posix(), "--kind", kind, "--report", report_path.as_posix(), *extra)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return code, report, output

    def statuses(self, report: dict) -> dict[str, str]:
        return {r["check"]: r["status"] for r in report["results"]}

    def test_the_good_fixture_passes_as_a_body(self) -> None:
        code, report, output = self.check(self.good, "body")
        self.assertEqual(code, 0, output)
        self.assertEqual(report["verdict"], "pass")
        self.assertEqual(report["summary"]["warn"], 0, output)
        self.assertEqual(report["measure"]["meshes"][0]["triangles"], 660)

    def test_the_broken_fixture_fails_on_each_defect(self) -> None:
        code, report, output = self.check(self.bad, "body")
        self.assertEqual(code, 1, output)
        statuses = self.statuses(report)
        for check in (
            "extra_bones",
            "missing_bones",
            "weights_per_vertex",
            "ngons",
            "non_manifold_edges",
            "height",
            "facing",
            "finger_chains",
        ):
            self.assertEqual(statuses[check], "fail", f"{check}\n{output}")

    def test_a_rigged_body_is_not_an_accessory(self) -> None:
        code, report, output = self.check(self.good, "accessory")
        self.assertEqual(code, 1, output)
        self.assertEqual(self.statuses(report)["rig"], "fail")

    def test_mixamo_names_pass_only_through_the_map(self) -> None:
        code, report, output = self.check(self.mixamo, "body")
        self.assertEqual(code, 1, output)
        self.assertEqual(self.statuses(report)["missing_bones"], "fail")
        code, report, output = self.check(self.mixamo, "body", "--map", "mixamo")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.statuses(report)["dropped_bones"], "warn")

    def test_rename_bones_then_check(self) -> None:
        renamed = WORK / "mixamo_renamed.glb"
        code, output = run_cli("rename-bones", self.mixamo.as_posix(), "--map", "mixamo", "--out", renamed.as_posix())
        self.assertEqual(code, 0, output)
        self.assertIn("renamed 54 bones, dropped 2", output)
        code, report, output = self.check(renamed, "body")
        self.assertEqual(code, 0, output)
        self.assertEqual(report["summary"]["warn"], 0, output)

    def test_quaternius_end_bones_go_and_their_weights_stay(self) -> None:
        code, report, output = self.check(self.quaternius, "body", "--map", "quaternius")
        self.assertEqual(code, 0, output)
        self.assertIn("weights move from index_04_leaf_l to index_03_l", output)
        renamed = WORK / "quaternius_renamed.glb"
        code, output = run_cli("rename-bones", self.quaternius.as_posix(), "--map", "quaternius", "--out", renamed.as_posix())
        self.assertEqual(code, 0, output)
        self.assertIn("dropped 2", output)
        self.assertIn("index_04_leaf_l -> index_03_l", output)
        code, report, output = self.check(renamed, "body")
        self.assertEqual(code, 0, output)
        self.assertEqual(report["summary"]["warn"], 0, output)

    def test_dropping_a_middle_bone_leaves_its_child_in_place(self) -> None:
        chain = self.build("chain.blend", connected=True)
        maps = WORK / "maps"
        maps.mkdir(exist_ok=True)
        (maps / "chain.toml").write_text(
            'source = "test"\nconfirmed = false\nprefix_pattern = ""\ndrop = ["LeftIndexIntermediate"]\n[rename]\n',
            encoding="utf-8",
        )
        renamed = WORK / "chain_renamed.blend"
        with mock.patch.object(_contract, "BONE_MAPS", maps):
            code, output = run_cli("rename-bones", chain.as_posix(), "--map", "chain", "--out", renamed.as_posix())
        self.assertEqual(code, 0, output)
        self.assertIn("LeftIndexIntermediate -> LeftIndexProximal", output)
        before = self.bones(self.check(chain, "body")[1])
        after = self.bones(self.check(renamed, "body")[1])
        self.assertNotIn("LeftIndexIntermediate", after)
        self.assertEqual(after["LeftIndexDistal"]["parent"], "LeftIndexProximal")
        for axis in range(3):
            self.assertAlmostEqual(after["LeftIndexDistal"]["head"][axis], before["LeftIndexDistal"]["head"][axis], 5)

    @staticmethod
    def bones(report: dict) -> dict[str, dict]:
        return {b["name"]: b for b in report["measure"]["armatures"][0]["bones"]}


if __name__ == "__main__":
    unittest.main()
