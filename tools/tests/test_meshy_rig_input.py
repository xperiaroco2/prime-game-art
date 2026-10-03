"""meshy rig-input (art #25): the GLB a rig input is made of holds one mesh and nothing else. Blender's glTF importer
adds an "Icosphere" of its own (its bone display shape) to every import, which no file of ours or Meshy's contains."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from runner import common
from runner.commands import _meshy_inputs as inputs
from runner.commands import meshy


def write_glb(path: Path, doc: dict) -> Path:
    body = json.dumps(doc).encode()
    body += b" " * (-len(body) % 4)
    data = b"glTF" + (2).to_bytes(4, "little") + (20 + len(body)).to_bytes(4, "little")
    data += len(body).to_bytes(4, "little") + b"JSON" + body
    path.write_bytes(data)
    return path


class GlbContentsTest(unittest.TestCase):
    def glb(self, tmp: str, doc: dict) -> Path:
        return write_glb(Path(tmp) / "x.glb", doc)

    def test_nodes_and_meshes_are_read_from_the_json_chunk(self) -> None:
        with TemporaryDirectory() as tmp:
            got = inputs.glb_contents(self.glb(tmp, {"nodes": [{"name": "m1_rex", "mesh": 0}],
                                                     "meshes": [{"name": "m1_rex"}]}))
            self.assertEqual(got, {"nodes": ["m1_rex"], "meshes": ["m1_rex"]})
            (Path(tmp) / "y.glb").write_bytes(b"not a glb at all, longer than twenty bytes")
            with self.assertRaises(common.Failure):
                inputs.glb_contents(Path(tmp) / "y.glb")


class RigInputRefusalTest(unittest.TestCase):
    """rig_input itself, with Blender replaced by a stub that writes the GLB and the JSON note."""

    def run_with(self, tmp: Path, doc: dict) -> Path:
        blend = tmp / "m1_rex.blend"
        blend.write_bytes(b"")
        out = tmp / "out"
        out.mkdir()
        glb = out / "m1_rex.glb"

        def fake_run_script(script: str, args: list[str], timeout: int) -> None:
            write_glb(glb, doc)
            (out / "m1_rex_texture.png").write_bytes(b"png")
            (out / "m1_rex.json").write_text(json.dumps({
                "glb": str(glb), "texture": str(out / "m1_rex_texture.png"), "glb_bytes": glb.stat().st_size,
                "triangles": 1, "height_m": 1.8, "palette_px": 4, "materials": ["Skin"]}), encoding="utf-8")

        with mock.patch.object(meshy.blender, "run_script", side_effect=fake_run_script):
            meshy.rig_input([blend], out)
        return glb

    def test_a_second_node_is_refused_and_the_glb_set_aside(self) -> None:
        with TemporaryDirectory() as tmp:
            doc = {"nodes": [{"name": "m1_rex", "mesh": 0}, {"name": "Icosphere", "mesh": 1}],
                   "meshes": [{"name": "m1_rex"}, {"name": "Icosphere"}]}
            with self.assertRaises(common.Failure) as caught:
                self.run_with(Path(tmp), doc)
            self.assertIn("Icosphere", str(caught.exception))
            self.assertFalse((Path(tmp) / "out" / "m1_rex.glb").exists())
            self.assertTrue((Path(tmp) / "out" / "m1_rex.glb.rejected").exists())

    def test_one_mesh_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            glb = self.run_with(Path(tmp), {"nodes": [{"name": "m1_rex", "mesh": 0}], "meshes": [{"name": "m1_rex"}]})
            self.assertTrue(glb.is_file())


if __name__ == "__main__":
    unittest.main()
