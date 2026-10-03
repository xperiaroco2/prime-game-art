"""meshy rig-input (art #25): the GLB a rig input is made of holds one mesh and nothing else. Blender's glTF importer
adds an "Icosphere" of its own (its bone display shape) to every import, which no file of ours or Meshy's contains."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runner import common
from runner.commands import _meshy_inputs as inputs


class GlbContentsTest(unittest.TestCase):
    def glb(self, tmp: str, doc: dict) -> Path:
        body = json.dumps(doc).encode()
        body += b" " * (-len(body) % 4)
        data = b"glTF" + (2).to_bytes(4, "little") + (20 + len(body)).to_bytes(4, "little")
        data += len(body).to_bytes(4, "little") + b"JSON" + body
        path = Path(tmp) / "x.glb"
        path.write_bytes(data)
        return path

    def test_nodes_and_meshes_are_read_from_the_json_chunk(self) -> None:
        with TemporaryDirectory() as tmp:
            got = inputs.glb_contents(self.glb(tmp, {"nodes": [{"name": "m1_rex", "mesh": 0}],
                                                     "meshes": [{"name": "m1_rex"}]}))
            self.assertEqual(got, {"nodes": ["m1_rex"], "meshes": ["m1_rex"]})
            (Path(tmp) / "y.glb").write_bytes(b"not a glb at all, longer than twenty bytes")
            with self.assertRaises(common.Failure):
                inputs.glb_contents(Path(tmp) / "y.glb")


if __name__ == "__main__":
    unittest.main()
