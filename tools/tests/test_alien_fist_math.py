"""The run fist's morph maths (art #196, H1j): tools/blender/alien_fist_math.py. Plain Python."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import alien_fist_math as F  # noqa: E402


class WeightsTest(unittest.TestCase):
    def test_plan(self):
        self.assertEqual(F.weight_plan({"Left": [(0.0, "loose")], "Right": [(0.0, "loose")]}, "loose"), [(0.0, 1.0)])
        keys = F.weight_plan({"Left": [(0.0, "relaxed"), (0.5, "loose")],
                              "Right": [(0.0, "relaxed"), (0.5, "loose")]}, "loose")
        self.assertEqual(keys, [(0.0, 0.0), (0.5, 1.0)])
        self.assertEqual(F.weight_at(keys, 0.25), 0.5)
        self.assertEqual(F.weight_at(keys, 0.9), 1.0)
        with self.assertRaises(ValueError):
            F.weight_plan({"Left": [(0.0, "loose")], "Right": [(0.0, "relaxed")]}, "loose")

    def test_weight_plan_lead(self):
        """H1m: the morph reaches 1 at the lead's share of a ramp into the fist, and leaves 1 as late out of it."""
        plan = {s: [(0.0, "relaxed"), (0.5, "loose"), (0.75, "loose"), (1.0, "relaxed")] for s in ("Left", "Right")}
        keys = F.weight_plan(plan, "loose", 0.5)
        self.assertEqual(keys, [(0.0, 0.0), (0.25, 1.0), (0.5, 1.0), (0.75, 1.0), (0.875, 1.0), (1.0, 0.0)])
        self.assertEqual(F.weight_at(keys, 0.125), 0.5)
        self.assertEqual(F.weight_at(keys, 0.3), 1.0)
        self.assertGreater(F.weight_at(keys, 0.9), F.weight_at(F.weight_plan(plan, "loose"), 0.9))
        self.assertEqual(F.weight_plan(plan, "loose", 1.0), F.weight_plan(plan, "loose"))
        with self.assertRaises(ValueError):
            F.weight_plan(plan, "loose", 0.0)

    def test_key_weights_into_glb(self):
        times = [0.0, 0.5, 1.0]
        bin_ = bytearray(struct.pack("<3f", *times) + struct.pack("<12f", *([0, 0, 0, 1] * 3)))
        gltf = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(bin_)}],
                "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 12},
                                {"buffer": 0, "byteOffset": 12, "byteLength": 48}],
                "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "SCALAR", "min": [0],
                               "max": [1]}, {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC4"}],
                "nodes": [{"name": "Body", "mesh": 0}, {"name": "Bone"}],
                "meshes": [{"name": "Body", "extras": {"targetNames": ["fist"]},
                            "primitives": [{"attributes": {}, "targets": [{"POSITION": 1}]}]}],
                "animations": [{"name": n, "samplers": [{"input": 0, "output": 1}],
                                "channels": [{"sampler": 0, "target": {"node": 1, "path": "rotation"}}]}
                               for n in ("Jog", "Walk")]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.glb"
            F._write_glb(p, gltf, bin_)
            got = F.key_weights(p, "fist", {"Jog": [(0.0, 1.0)]})
            self.assertEqual(got, {"Jog": [1.0, 1.0], "Walk": [0.0, 0.0]})
            g2, b2 = F._glb(p)
            ch = g2["animations"][0]["channels"][-1]
            self.assertEqual(ch["target"], {"node": 0, "path": "weights"})
            acc = g2["accessors"][g2["animations"][0]["samplers"][ch["sampler"]]["output"]]
            bv = g2["bufferViews"][acc["bufferView"]]
            self.assertEqual(struct.unpack_from("<3f", b2, bv["byteOffset"]), (1.0, 1.0, 1.0))
            self.assertEqual(g2["meshes"][0]["weights"], [0.0])
            with self.assertRaises(ValueError):  # twice: refused
                F.key_weights(p, "fist", {})
            g2["meshes"][0]["extras"]["targetNames"] = ["fist", "other"]
            F._write_glb(p, g2, b2)
            with self.assertRaises(ValueError):
                F.key_weights(p, "fist", {})
        json.dumps(got)


if __name__ == "__main__":
    unittest.main()
