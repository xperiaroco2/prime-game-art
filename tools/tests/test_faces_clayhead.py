"""The clay face kit's bean head (faces/clay_head.json, um/heads.py bean_warp and flatten_nose, um/clayface/adapter.py):
the data's shape, its parity with the faces lab's params_r2.json, the builders' defaults against the data, and the
lab's order of operations in the adapter (docs/faces.md, "The bean head")."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

from runner.commands import _assembly

_assembly.recipe_module()  # puts tools/blender on the path
from um.clayface import kit as K  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = Path("D:/prime-art-raw")
UM = ROOT / "tools" / "blender" / "um"


def defaults(path, name):
    """The keyword defaults of function `name` in a module (read with ast: the module needs Blender)."""
    fn = next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == name)
    args = fn.args.args[len(fn.args.args) - len(fn.args.defaults):]
    return {a.arg: ast.literal_eval(d) for a, d in zip(args, fn.args.defaults)}


class HeadData(unittest.TestCase):
    def test_shape(self):
        H = K.HEAD
        self.assertEqual(H["schema"], "prime-game-art/faces/clay-head/1")
        self.assertEqual(H["order"], ["nose_flatten", "bean_warp", "rigid_face_skin", "clean_head", "jaw_morph",
                                      "scalp_lift", "push_out"])
        J = H["jaw_morph"]
        self.assertEqual(set(J), {"band_dz", "reach", "profile"})
        lo, mid, hi = J["band_dz"]
        self.assertTrue(lo < mid < hi < 0.0)
        prof = J["profile"]
        self.assertEqual(len(prof["r"]), len(prof["dz"]))
        self.assertTrue(all(len(row) == len(prof["az_deg"]) for row in prof["r"]))
        self.assertTrue(all(0.0 < r < 0.2 for row in prof["r"] for r in row))
        self.assertLessEqual(prof["dz"][0], lo)
        self.assertGreaterEqual(prof["dz"][-1], hi)
        self.assertAlmostEqual(360.0 / len(prof["az_deg"]), prof["az_deg"][1] - prof["az_deg"][0])
        self.assertEqual(set(H["scalp_lift"]), {"clear", "depth", "n_az", "n_el"})
        self.assertEqual(set(H["clean_head"]), {"neck_dz", "sphere", "voxel_m", "tris", "snap_tol", "crease_band",
                                                "crease_passes", "weight_blend_m", "small_piece_faces"})
        self.assertEqual(set(H["push_out"]), {"clear", "reach", "passes", "keep"})
        self.assertEqual(dict(H["bean_clay"]), {"strength": 1.0, "power": 2.5})
        self.assertEqual(set(H["bean"]), {"centre_dz", "centre_y", "ax", "ay", "az_top", "az_bottom", "power",
                                          "strength", "fade_z", "hair_k"})
        self.assertTrue(0.0 < H["bean"]["strength"] <= 1.0)
        self.assertGreater(H["bean"]["fade_z"][0], H["bean"]["fade_z"][1])
        self.assertIsInstance(H["bean"]["hair_k"], int)

    def test_builders_default_to_the_data(self):
        # heads.py's defaults are the lab's; the adapter passes the data: both must say the same
        bean = defaults(UM / "heads.py", "bean_warp")
        for k, v in K.HEAD["bean"].items():
            self.assertEqual(tuple(bean[k]) if isinstance(v, tuple) else bean[k], v, k)
        nose = defaults(UM / "heads.py", "flatten_nose")
        for k, v in K.HEAD["nose_flatten"].items():
            self.assertEqual(nose[k], v, k)
        self.assertEqual(defaults(UM / "clayface" / "face.py", "rigid_full_z")["margin"], K.HEAD["rigid_margin"])
        jaw = defaults(UM / "heads.py", "morph_jaw")
        self.assertEqual(tuple(jaw["band_dz"]), tuple(K.HEAD["jaw_morph"]["band_dz"]))
        self.assertEqual(jaw["reach"], K.HEAD["jaw_morph"]["reach"])
        for fn, key in (("clean_head", "clean_head"), ("push_out", "push_out"), ("lift_grid", "scalp_lift")):
            got = defaults(UM / "heads.py", fn)
            for k, v in K.HEAD[key].items():
                self.assertEqual(json.loads(json.dumps(got[k])), json.loads(json.dumps(v)), (fn, k))

    def test_the_head_is_in_the_kit_data_sha(self):
        self.assertIn(K.HEAD_SHA, [hashlib.sha256(K.HEAD_FILE.read_bytes()).hexdigest()[:16]])

    def test_adapter_runs_the_lab_order(self):
        src = (UM / "clayface" / "adapter.py").read_text(encoding="utf-8")
        body = src[src.index("def build("):]
        at = [body.index(s) for s in ("heads.flatten_nose(", "heads.bean_warp(", "fk.rigid_face_skin(",
                                    "heads.clean_head(", "heads.morph_jaw(", "heads.lift_grid(", "heads.lift_by(", "heads.push_out(",
                                    "build_face(")]
        self.assertEqual(at, sorted(at))
        self.assertNotIn("bean_warp", (UM / "heads.py").read_text(encoding="utf-8").split("def bean_warp")[0])


class LabParity(unittest.TestCase):
    """faces/clay_head.json against the lab file it was taken from (lab_source); skipped without the raw folder."""

    def test_params(self):
        src = K.HEAD["lab_source"]
        p = RAW / "research" / Path(src["path"]).relative_to("research")
        if not p.is_file():
            self.skipTest("no lab file %s" % p)
        if hashlib.sha256(p.read_bytes()).hexdigest() != src["sha256"]:
            self.skipTest("the lab file has moved on: re-sync faces/clay_head.json")
        lab = json.loads(p.read_text(encoding="utf-8"))
        for k in ("nose_flatten", "bean", "rigid_margin"):
            self.assertEqual(json.loads(json.dumps(K.HEAD[k])), lab[k], k)

    def test_clean_head_numbers(self):
        # the lab's round B clay head (clay_b/clay_parts.py build_head and push_out): its literal numbers
        src = K.HEAD["clean_head_source"]
        p = RAW / "research" / Path(src["code"]).relative_to("research")
        if not p.is_file():
            self.skipTest("no lab file %s" % p)
        if hashlib.sha256(p.read_bytes()).hexdigest() != src["code_sha256"]:
            self.skipTest("the lab file has moved on: re-sync faces/clay_head.json")
        code = p.read_text(encoding="utf-8")
        C = K.HEAD["clean_head"]
        self.assertIn('dict(ctx.P["bean"], strength=%s, power=%s)' % (K.HEAD["bean_clay"]["strength"],
                                                                     K.HEAD["bean_clay"]["power"]), code)
        for frag in ('B["radii"][3] + %s)' % C["neck_dz"], "u_segments=%d, v_segments=%d" % tuple(C["sphere"]),
                     "voxel_m\": %s" % C["voxel_m"], "np.abs(f - 1.0) < %s" % C["snap_tol"],
                     "(Pw[:, 2] > z_neck - %s) & (Pw[:, 2] < z_neck + %s)" % (-C["crease_band"][0], C["crease_band"][1]),
                     "range(%d)" % C["crease_passes"], "remove_small_components(head, %d)" % C["small_piece_faces"],
                     '"head": %d' % C["tris"], "HAIR_CLEAR = %s" % K.HEAD["push_out"]["clear"],
                     "reach=%s, passes=%d" % (K.HEAD["push_out"]["reach"], K.HEAD["push_out"]["passes"]),
                     "keep=%s" % K.HEAD["push_out"]["keep"],
                     "def lift_grid(o, head_bvh, centre, clear, depth=%s, n_az=%d, n_el=%d)"
                     % (K.HEAD["scalp_lift"]["depth"], K.HEAD["scalp_lift"]["n_az"], K.HEAD["scalp_lift"]["n_el"]),
                     "HAIR_CLEAR = %s" % K.HEAD["scalp_lift"]["clear"]):
            self.assertIn(frag.replace("\\", ""), code, frag)

    def test_jaw_source(self):
        # the lab's ONE head (clay_c/clay_head_c.py): its JAW_BAND and morph reach, and the head file sampled
        src = K.HEAD["jaw_source"]
        code = RAW / "research" / Path(src["code"]).relative_to("research")
        blend = RAW / "research" / Path(src["head"]).relative_to("research")
        if not code.is_file() or not blend.is_file():
            self.skipTest("no lab files")
        text = code.read_text(encoding="utf-8")
        self.assertIn("JAW_BAND = (%.3f, %.3f, %.3f)" % tuple(src["band_scaled_z"]), text)
        self.assertIn("reach=%s" % K.HEAD["jaw_morph"]["reach"], text)
        self.assertEqual(hashlib.sha256(blend.read_bytes()).hexdigest(), src["head_sha256"])


if __name__ == "__main__":
    unittest.main()
