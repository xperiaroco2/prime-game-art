"""The ragdoll data (art #115; docs/contract.md, "Ragdoll"): measured from slice_m1's GLB in plain Python, its schema
and values (every body on a bone of the skeleton, sizes positive and inside the body, limits in range, the collision
rule), the shipped copy matching a fresh measure, and the package listing it. No Godot needed."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common  # noqa: E402
from runner.commands import _ragdoll, ragdoll  # noqa: E402

ASSET = common.ROOT / "assets" / "character" / "slice_m1"
GLB = ASSET / "export" / "slice_m1.glb"
DATA = ASSET / "export" / "slice_m1.ragdoll.json"
HAVE_GLB = GLB.is_file() and GLB.stat().st_size > 100_000  # not a Git LFS pointer


@unittest.skipUnless(HAVE_GLB, "needs slice_m1.glb (Git LFS)")
class MeasureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = _ragdoll.measure(GLB)
        gltf, _ = _ragdoll.read_glb(GLB)
        cls.skel = _ragdoll.skeleton(gltf)

    def test_schema_and_values(self) -> None:
        self.assertEqual(_ragdoll.check(self.data, self.skel["names"]), [])
        self.assertEqual(_ragdoll.shapes_in_bounds(self.data, self.skel["global"]), [])

    def test_the_bodies(self) -> None:
        names = [b["bone"] for b in self.data["bones"]]
        self.assertEqual(len(names), 16)
        self.assertTrue(set(names) <= set(self.skel["names"]))
        for side in ("L", "R"):
            for part in ("UpperArm", "LowerArm", "Wrist", "UpperLeg", "LowerLeg", "Foot"):
                self.assertIn(f"{part}.{side}", names)
        roots = [b["bone"] for b in self.data["bones"] if b["parent"] is None]
        self.assertEqual(roots, ["Body"])
        self.assertAlmostEqual(sum(b["mass_share"] for b in self.data["bones"]), 1.0, delta=0.01)
        # fingers and toes are not simulated: they follow a body
        for name in self.skel["names"]:
            if name.startswith(("Index", "Thumb", "Toe")):
                self.assertNotIn(name, names)
                self.assertIn(self.data["followers"].get(name), names)

    def test_collision_rule(self) -> None:
        c = self.data["collision"]
        self.assertEqual((c["layer"], c["layer_name"], c["mask"], c["mask_names"]), (3, "downed", [1], ["world"]))

    def test_the_check_finds_broken_data(self) -> None:
        broken = copy.deepcopy(self.data)
        broken["bones"][1]["bone"] = "NoSuchBone"
        knee = next(b for b in broken["bones"] if b["bone"] == "LowerLeg.L")
        knee["joint"]["max_deg"] = 300.0
        problems = _ragdoll.check(broken, self.skel["names"])
        self.assertTrue(any("NoSuchBone" in p for p in problems), problems)
        self.assertTrue(any("hinge limits" in p for p in problems), problems)

    def test_the_shipped_copy_is_a_fresh_measure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / DATA.name
            _ragdoll.write(_ragdoll.measure(GLB), fresh)
            self.assertEqual(json.loads(DATA.read_text(encoding="utf-8")), json.loads(fresh.read_text(encoding="utf-8")),
                             "re-run: tools/run.py ragdoll assets/character/slice_m1/export/slice_m1.glb "
                             "--asset assets/character/slice_m1")


class PackageTest(unittest.TestCase):
    def test_the_package_lists_the_data(self) -> None:
        pkg = json.loads((ASSET / "package.json").read_text(encoding="utf-8"))
        row = next((f for f in pkg["files"] if f["name"] == DATA.name), None)
        self.assertIsNotNone(row)
        self.assertEqual(row["sha256"], _ragdoll.sha256(DATA))
        self.assertEqual(row["bytes"], DATA.stat().st_size)

    def test_the_handoff_says_how_the_game_builds_the_bones(self) -> None:
        text = (ASSET / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("## Ragdoll (art #115)"), 1)
        self.assertIn("godot/ragdoll/builder.gd", text)
        self.assertIn(DATA.name, text)

    def test_put_in_asset_replaces_its_section(self) -> None:
        data = json.loads(DATA.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            asset = Path(tmp)
            (asset / "package.json").write_text(json.dumps({"asset": "slice_m1", "files": []}), encoding="utf-8")
            (asset / "HANDOFF.md").write_text("# slice_m1\n\n## Clips\n\nx\n\n## Ragdoll (art #115)\n\nold\n\n## Last\n\ny\n",
                                              encoding="utf-8")
            ragdoll.put_in_asset(asset, data)
            ragdoll.put_in_asset(asset, data)
            text = (asset / "HANDOFF.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("## Ragdoll (art #115)"), 1)
            self.assertNotIn("\nold\n", text)
            self.assertIn("## Last", text)
            files = json.loads((asset / "package.json").read_text(encoding="utf-8"))["files"]
            self.assertEqual([f["name"] for f in files], [DATA.name])


if __name__ == "__main__":
    unittest.main()


class ContractRigTest(unittest.TestCase):
    """The contract's humanoid skeleton (the aliens, art #393): the plan names its bones and keeps the UM plan's shapes,
    shares and joints; a recovered alien GLB, when present, measures and checks clean."""

    def test_the_rig_is_told_from_the_names(self) -> None:
        self.assertEqual(_ragdoll.rig_of(["Root", "Body", "Torso", "Wrist.R"]), "um")
        self.assertEqual(_ragdoll.rig_of(["Hips", "Spine", "Chest", "RightHand", "LeftUpperLeg"]), "contract")
        with self.assertRaises(ValueError):
            _ragdoll.rig_of(["Hips", "Spine"])

    def test_the_contract_plan(self) -> None:
        um, con = _ragdoll.plan("um"), _ragdoll.plan("contract")
        self.assertEqual(len(um), len(con))
        names = [b["bone"] for b in con]
        self.assertEqual(names[:4], ["Hips", "Spine", "Chest", "Neck"])
        self.assertIn("LeftHand", names)
        self.assertIn("RightFoot", names)
        seen: set[str] = set()
        for u, c in zip(um, con):
            self.assertEqual(c["bone"], c["profile"], "the contract's bones are the profile names")
            for k in ("profile", "shape", "mass_share", "joint"):
                self.assertEqual(u[k], c[k], k)
            if c["parent"] is not None:
                self.assertIn(c["parent"], seen)
            seen.add(c["bone"])
        self.assertEqual(next(b for b in con if b["bone"] == "LeftUpperArm")["parent"], "Chest")
        self.assertEqual(next(b for b in con if b["bone"] == "RightUpperLeg")["parent"], "Hips")

    def test_a_recovered_alien(self) -> None:
        glb = common.raw_dir() / "recovered" / "artifact-Ff1dvJw6uG541Z6qvTnNcT" / "glb" / "chameleon.glb"
        if not glb.is_file():
            self.skipTest("needs the recovered chameleon.glb in the raw folder")
        data = _ragdoll.measure(glb)
        gltf, _ = _ragdoll.read_glb(glb)
        skel = _ragdoll.skeleton(gltf)
        self.assertEqual(data["rig"], "contract")
        self.assertEqual(_ragdoll.check(data, skel["names"]) + _ragdoll.shapes_in_bounds(data, skel["global"]), [])
        self.assertEqual(data["unweighted_or_above_hips"], {})
