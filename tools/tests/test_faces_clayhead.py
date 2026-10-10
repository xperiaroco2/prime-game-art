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
        self.assertEqual(H["order"], ["nose_flatten", "bean_warp", "rigid_face_skin", "clean_head", "push_out"])
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
        for fn in ("clean_head", "push_out"):
            got = defaults(UM / "heads.py", fn)
            for k, v in K.HEAD[fn].items():
                self.assertEqual(json.loads(json.dumps(got[k])), json.loads(json.dumps(v)), (fn, k))

    def test_the_head_is_in_the_kit_data_sha(self):
        self.assertIn(K.HEAD_SHA, [hashlib.sha256(K.HEAD_FILE.read_bytes()).hexdigest()[:16]])

    def test_adapter_runs_the_lab_order(self):
        src = (UM / "clayface" / "adapter.py").read_text(encoding="utf-8")
        body = src[src.index("def build("):]
        at = [body.index(s) for s in ("heads.flatten_nose(", "heads.bean_warp(", "fk.rigid_face_skin(",
                                    "heads.clean_head(", "heads.push_out(", "build_face(")]
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
                     "keep=%s" % K.HEAD["push_out"]["keep"]):
            self.assertIn(frag.replace("\\", ""), code, frag)


if __name__ == "__main__":
    unittest.main()
