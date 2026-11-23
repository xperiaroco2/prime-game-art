"""The alien's game package (art #393; tools/runner/commands/_alien_package.py, alien_package.py): the GLB clean-up on a
small built GLB (review clips dropped, names, the binary compacted and still readable), the feet's ground speed, and
the committed package (its files' hashes, the look file's inputs, the look scripts' relative preloads, the manifest's
CC-BY clip credit). No Godot or Blender needed; the committed GLB is read when Git LFS has it."""

import json
import math
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common  # noqa: E402
from runner.commands import _alien_package as P, _manifest, _ragdoll as R, alien_package  # noqa: E402

ASSET = common.ROOT / "assets" / "character" / "alien_chameleon"
GLB = ASSET / "export" / "alien_chameleon.glb"
HAVE_GLB = GLB.is_file() and GLB.stat().st_size > 100_000  # not a Git LFS pointer


def _pack(values: list[tuple[float, ...]]) -> bytes:
    return b"".join(struct.pack("<" + "f" * len(v), *v) for v in values)


def toy() -> tuple[dict, bytes]:
    """A skeleton Root > Hips > LeftToes, one triangle skinned to Hips, and two clips: `Walk_Loop`, whose toe slides
    back at 2 m/s on the floor for the first half and swings up for the second, and a review variant."""
    blob = bytearray()
    accessors, views = [], []

    def add(values, kind, minmax=False):
        data = _pack(values)
        blob.extend(b"\0" * (-len(blob) % 4))
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)})
        blob.extend(data)
        acc = {"bufferView": len(views) - 1, "componentType": 5126, "count": len(values), "type": kind}
        if minmax:
            acc["min"] = [min(v[i] for v in values) for i in range(len(values[0]))]
            acc["max"] = [max(v[i] for v in values) for i in range(len(values[0]))]
        accessors.append(acc)
        return len(accessors) - 1

    pos = add([(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0)], "VEC3", True)
    joints_data = struct.pack("<4H", 1, 0, 0, 0) * 3
    blob.extend(b"\0" * (-len(blob) % 4))
    views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(joints_data)})
    blob.extend(joints_data)
    accessors.append({"bufferView": len(views) - 1, "componentType": 5123, "count": 3, "type": "VEC4"})
    joints = len(accessors) - 1
    weights = add([(1.0, 0.0, 0.0, 0.0)] * 3, "VEC4")
    ibm = add([(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)] * 3, "MAT4")
    times = [k / 24.0 for k in range(25)]
    t_in = add([(t,) for t in times], "SCALAR", True)
    # the toe in the hips' frame: back along -Z at 2 m/s on the floor for 0.5 s, then forward 0.1 m up
    toe = [(0.1, -0.9, 0.5 - 2.0 * t) if t <= 0.5 else (0.1, -0.8, -0.5 + 2.0 * (t - 0.5)) for t in times]
    t_out = add(toe, "VEC3")
    v_out = add([(0.1, -0.9, 0.3)] * 25, "VEC3")
    gltf = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "CharacterArmature", "children": [1, 3]}, {"name": "Root", "children": [2]},
                  {"name": "Hips", "translation": [0.0, 0.9, 0.0], "children": [4]},
                  {"name": "body", "mesh": 0, "skin": 0}, {"name": "LeftToes", "translation": [0.1, -0.9, 0.0]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": pos, "JOINTS_0": joints, "WEIGHTS_0": weights}}]}],
        "skins": [{"joints": [1, 2, 4], "inverseBindMatrices": ibm}],
        "animations": [
            {"name": "CharacterArmature|Walk_Loop", "samplers": [{"input": t_in, "output": t_out}],
             "channels": [{"sampler": 0, "target": {"node": 4, "path": "translation"}}]},
            {"name": "CharacterArmature|Walk__v2_Loop", "samplers": [{"input": t_in, "output": v_out}],
             "channels": [{"sampler": 0, "target": {"node": 4, "path": "translation"}}]},
        ],
        "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}],
    }
    return gltf, bytes(blob)


class CleanTest(unittest.TestCase):
    def test_review_clips_dropped_and_the_rest_renamed(self):
        g, b = toy()
        g2, b2, dropped = P.clean(g, b)
        self.assertEqual(dropped, ["Walk__v2_Loop"])
        self.assertEqual([a["name"] for a in g2["animations"]], ["Walk_Loop"])
        self.assertLess(len(b2), len(b))
        self.assertEqual(len(g2["accessors"]), len(g["accessors"]) - 1)
        self.assertEqual(g["animations"][0]["name"], "CharacterArmature|Walk_Loop", "the input is left as it was")

    def test_the_compacted_glb_reads_the_same(self):
        g, b = toy()
        g2, b2, _ = P.clean(g, b)
        prim, prim2 = g["meshes"][0]["primitives"][0], g2["meshes"][0]["primitives"][0]
        for key in ("POSITION", "JOINTS_0", "WEIGHTS_0"):
            self.assertEqual(R.accessor(g2, b2, prim2["attributes"][key]), R.accessor(g, b, prim["attributes"][key]))
        self.assertEqual(R.accessor(g2, b2, g2["skins"][0]["inverseBindMatrices"]),
                         R.accessor(g, b, g["skins"][0]["inverseBindMatrices"]))
        for view in g2["bufferViews"]:
            self.assertEqual(view["byteOffset"] % 4, 0)
        data = P.glb_bytes(g2, b2)
        self.assertEqual(struct.unpack_from("<I", data, 8)[0], len(data))

    def test_sparse_accessors_are_refused(self):
        g, b = toy()
        g["accessors"][0]["sparse"] = {}
        with self.assertRaises(ValueError):
            P.clean(g, b)


class ClipRowsTest(unittest.TestCase):
    def test_ground_speed_from_the_planted_toe(self):
        g, b = P.clean(*toy())[:2]
        (row,) = P.clip_rows(g, b)
        self.assertEqual((row["set_name"], row["godot_name"], row["loop"], row["fps"]), ("Walk_Loop", "Walk", True, 24))
        self.assertAlmostEqual(row["speed_m_s"], 2.0, places=2)
        self.assertAlmostEqual(row["seconds"], 1.0)

    def test_step_and_cubic_samplers(self):
        self.assertEqual(P._sample([0.0, 1.0], [(0.0,), (1.0,)], True, 0.6, False), (0.0,))
        self.assertEqual(P._sample([0.0, 1.0], [(0.0,), (1.0,)], False, 0.5, False), (0.5,))
        g, b = P.clean(*toy())[:2]
        g["animations"][0]["samplers"][0]["interpolation"] = "CUBICSPLINE"
        with self.assertRaises(ValueError):
            P.clip_rows(g, b)

    def test_sockets_refuse_a_scaled_bone(self):
        with self.assertRaises(ValueError):
            P._local(R.mat(s=(1.2, 1.2, 1.2)), (0.0, 0.0, 0.0))


@unittest.skipUnless(HAVE_GLB, "needs alien_chameleon.glb (Git LFS)")
class CommittedPackageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg = json.loads((ASSET / "package.json").read_text(encoding="utf-8"))

    def test_files_match_their_hashes(self):
        listed = {f["name"] for f in self.pkg["files"]}
        on_disk = {p.relative_to(ASSET / "export").as_posix() for p in (ASSET / "export").rglob("*") if p.is_file()}
        self.assertEqual(listed, on_disk)
        for f in self.pkg["files"]:
            path = ASSET / "export" / f["name"]
            self.assertEqual(path.stat().st_size, f["bytes"], f["name"])
            self.assertEqual(R.sha256(path), f["sha256"], f["name"])

    def test_the_game_clips_and_bones_are_there(self):
        g, b = R.read_glb(GLB)
        names = {a["name"] for a in g["animations"]}
        self.assertFalse([n for n in names if P.VARIANT in n or n.startswith(P.PREFIX)])
        for clip in self.pkg["game"]["clips"]:
            self.assertIn(clip + ("" if clip in ("Jump_Start", "Jump_Land") else "_Loop"), names)
        self.assertEqual(set(self.pkg["game"]["clips"]), set(P.GAME_CLIPS))
        bones = set(R.skeleton(g)["names"])
        self.assertLessEqual(set(P.GAME_BONES.values()) | {s["bone"] for s in self.pkg["sockets"].values()}, bones)

    def test_heights_and_speeds(self):
        h = self.pkg["heights"]
        self.assertTrue(1.7 <= h["top_m"] <= 1.95, h)
        self.assertAlmostEqual(h["feet_m"], 0.0, delta=0.01)
        speeds = {r["godot_name"]: r["speed_m_s"] for r in self.pkg["clip_rows"]}
        self.assertAlmostEqual(speeds["Sprint_Fwd"], 7.0, delta=0.5)  # the set fitted it to 7.0 (alien_loco.toml)
        self.assertIsNone(speeds["Idle"])

    def test_the_look_file_is_the_review_pages_inputs(self):
        look = json.loads((ASSET / "export" / "look" / "alien_chameleon_look.json").read_text(encoding="utf-8"))
        self.assertEqual(look["mask"], "alien_chameleon_mask.png")
        self.assertTrue((ASSET / "export" / "look" / "alien_chameleon_mask.png.import").is_file())
        sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
        import alien_look_run as L
        self.assertEqual(look["params"], L.alive_params())
        self.assertEqual(look["detail"], L.DETAIL)
        for c in look["base_skin"]:
            self.assertTrue(0.0 <= c <= 1.0)

    def test_the_look_scripts_preload_relative_paths(self):
        for f in alien_package.LOOK_FILES:
            text = (ASSET / "export" / "look" / f).read_text(encoding="utf-8")
            self.assertNotIn("res://alien/", text, f)
        self.assertIn('preload("alien_static.gdshader")', (ASSET / "export" / "look" / "alien_static.gd").read_text())

    def test_sockets_in_their_bones_frames(self):
        for name, s in self.pkg["sockets"].items():
            self.assertEqual(s["bone"], P.ALIEN_BONES[name])
            self.assertLess(math.dist(s["point"], (0, 0, 0)), 0.7, name)


class ManifestTest(unittest.TestCase):
    def setUp(self):
        import tomllib
        with open(ASSET / "manifest.toml", "rb") as fh:
            self.data = tomllib.load(fh)
        self.sources = {p.stem: tomllib.loads(p.read_text(encoding="utf-8")) for p in (common.ROOT / "sources").glob("*.toml")}

    def test_the_manifest_passes(self):
        self.assertEqual(_manifest.validate(self.data, "character", "alien_chameleon", self.sources), [])

    def test_a_cc_by_clip_needs_its_credit(self):
        clip = next(c for c in self.data["clips"] if c["licence"] == "CC-BY-4.0")
        del clip["credit"]
        errors = _manifest.validate(self.data, "character", "alien_chameleon", self.sources)
        self.assertTrue(any("needs credit" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
