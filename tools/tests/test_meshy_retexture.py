"""Retexture in the Meshy client (art #196 M3b): our own GLB painted from one style (a text prompt, one style image
or 1 to 4 views) on its own UV; the batch checks, the price, the run against the fake (no network) and the retexture
input's GLB check."""

from __future__ import annotations

import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from runner import cli, common
from runner.commands import _meshy_api as api
from runner.commands import _meshy_batch as batches
from runner.commands import _meshy_inputs as inputs
from runner.commands import _meshy_run as runs
from runner.commands import meshy

from tests._meshy_fake import GLB, PNG, FakeMeshy
from tests.test_meshy_batch import APPROVAL, parse
from tests.test_meshy_rig_input import write_glb

MODEL = {"file": "raw:inputs/body.glb", "provenance": "own work: the alien kit's Body, rest pose, its texture UV"}
STYLE = {"file": "raw:inputs/style.png", "provenance": "own Meshy image-to-image output (a paintover of our render)"}


def retexture_batch(**item_overrides: Any) -> dict[str, Any]:
    """Three retextures of one GLB: from a style image, from a text prompt, and from three views on meshy-7."""
    items = [
        {"id": "rt-image", "kind": "retexture", "model": MODEL, "images": [STYLE],
         "params": {"ai_model": "meshy-7", "texture_resolution": "4k"}},
        {"id": "rt-text", "kind": "retexture", "model": MODEL, "prompt": "soft smooth toy-like teal skin",
         "params": {"ai_model": "meshy-7", "texture_resolution": "4k"}},
        {"id": "rt-views", "kind": "retexture", "model": MODEL, "multiview": True,
         "images": [STYLE, {**STYLE, "file": "raw:inputs/side.png"}, {**STYLE, "file": "raw:inputs/back.png"}],
         "params": {"ai_model": "meshy-7", "texture_resolution": "8k", "target_formats": ["glb"]}},
    ]
    for item in items:
        item.update(item_overrides.get(item["id"], {}))
        for key, value in list(item.items()):
            if value is None:
                del item[key]
    return {"id": "t-batch", "purpose": "tests", "credit_cap": 60, **APPROVAL, "items": items}


class BatchTest(unittest.TestCase):
    def refused(self, data: dict[str, Any]) -> str:
        with self.assertRaises(common.Failure) as ctx:
            parse(data)
        return str(ctx.exception)

    def test_priced_as_the_docs_say(self) -> None:
        batch = parse(retexture_batch())
        self.assertEqual({i.id: i.credits for i in batch.items}, {"rt-image": 10, "rt-text": 10, "rt-views": 15})
        self.assertEqual(batches.RETEXTURE_CREDITS, {"2k": 10, "4k": 10, "8k": 15})
        self.assertEqual(api.TASK_PATHS["retexture"], "/openapi/v1/retexture")
        item = batch.item("rt-image")
        self.assertEqual([i.role for i in item.inputs], ["model", "image"])
        self.assertEqual(item.model, "meshy-7")
        # our UV and the PBR maps unless the batch says otherwise (the API's defaults are false for both)
        self.assertEqual((item.stages[0].params["enable_original_uv"], item.stages[0].params["enable_pbr"]), (True, True))
        off = parse(retexture_batch(**{"rt-image": {"params": {"enable_pbr": False}}})).item("rt-image")
        self.assertIs(off.stages[0].params["enable_pbr"], False)
        self.assertTrue(batch.item("rt-views").multiview)

    def test_exactly_one_style(self) -> None:
        self.assertIn("not both", self.refused(retexture_batch(**{"rt-image": {"prompt": "teal"}})))
        self.assertIn("needs a style", self.refused(retexture_batch(**{"rt-image": {"images": None}})))
        self.assertIn("multiview = true", self.refused(retexture_batch(**{"rt-views": {"multiview": None}})))
        self.assertIn("needs 1 to 4 views", self.refused(retexture_batch(**{"rt-text": {"multiview": True}})))
        self.assertIn("at most 800", self.refused(retexture_batch(**{"rt-text": {"prompt": "x" * 801}})))

    def test_models_and_parameters_are_checked(self) -> None:
        self.assertIn("needs 'model'", self.refused(retexture_batch(**{"rt-text": {"model": None}})))
        self.assertIn(".glb", self.refused(retexture_batch(**{"rt-text": {"model": {**MODEL, "file": "raw:a.obj"}}})))
        self.assertIn("meshy-7.1", self.refused(retexture_batch(**{"rt-text": {"params": {"ai_model": "meshy-7.1"}}})))
        self.assertIn("explicitly", self.refused(retexture_batch(**{"rt-views": {"params": {"ai_model": "latest"}}})))
        self.assertIn("2k only", self.refused(retexture_batch(
            **{"rt-text": {"params": {"ai_model": "meshy-6-lite", "texture_resolution": "4k"}}})))
        self.assertIn("HTTP 400", self.refused(retexture_batch(
            **{"rt-text": {"params": {"ai_model": "meshy-6-lite", "remove_lighting": False}}})))
        self.assertIn("hd_texture", self.refused(retexture_batch(**{"rt-text": {"params": {"hd_texture": True}}})))
        self.assertIn("filled in by the runner", self.refused(retexture_batch(
            **{"rt-text": {"params": {"image_style_url": "https://x"}}})))
        self.assertIn("true or false", self.refused(retexture_batch(
            **{"rt-text": {"params": {"enable_original_uv": "yes"}}})))


class RunTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.raw = Path(self._tmp.name)
        self._env = mock.patch.dict(os.environ, {"ART_RAW_DIR": self._tmp.name})
        self._env.start()
        (self.raw / "inputs").mkdir()
        (self.raw / "inputs" / "body.glb").write_bytes(GLB + b"\x02\x00\x00\x00 the body")
        for name in ("style", "side", "back"):
            (self.raw / "inputs" / f"{name}.png").write_bytes(PNG + name.encode())
        self.fake = FakeMeshy(balance=100)
        self.log: list[str] = []

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def run_batch(self, data: dict[str, Any]) -> int:
        return runs.Runner(parse(data), self.fake.client(log=self.log), raw=self.raw).run()

    def state(self, item: str) -> dict[str, Any]:
        return json.loads((self.raw / "t-batch" / item / "generation.json").read_text(encoding="utf-8"))

    def test_each_style_goes_where_the_docs_say(self) -> None:
        self.assertEqual(self.run_batch(retexture_batch()), 0, self.log)
        posts = self.fake.posts()
        self.assertEqual([url.rsplit("/", 1)[-1] for url, _ in posts], ["retexture"] * 3)
        image, text, views = (body for _, body in posts)
        self.assertTrue(image["model_url"].startswith("data:application/octet-stream;base64,"))
        self.assertTrue(image["image_style_url"].startswith("data:image/png;base64,"))
        self.assertEqual({k for k in image if k not in ("model_url", "image_style_url")},
                         {"ai_model", "texture_resolution", "enable_original_uv", "enable_pbr"})
        self.assertIs(image["enable_original_uv"], True)
        self.assertEqual(text["text_style_prompt"], "soft smooth toy-like teal skin")
        self.assertNotIn("image_style_url", text)
        self.assertEqual(len(views["multiview_image_urls"]), 3)
        self.assertNotIn("image_style_url", views)
        state = self.state("rt-image")
        self.assertNotIn("base64", json.dumps(state))  # the record keeps notes, never the data URIs
        self.assertEqual([(i.get("role"), Path(i["path"]).name) for i in state["inputs"]],
                         [("model", "body.glb"), ("style", "style.png")])
        self.assertEqual(state["inputs"][0]["sha256"], inputs.sha256(self.raw / "inputs" / "body.glb"))
        keys = {f["key"]: f["name"] for f in state["files"]}
        # every PBR map and the model downloaded; the echoed inputs are not
        self.assertEqual(set(keys), {"model_urls.glb", "model_urls.fbx", "thumbnail_url",
                                     "texture_urls.0.base_color", "texture_urls.0.metallic",
                                     "texture_urls.0.normal", "texture_urls.0.roughness"})
        self.assertEqual(keys["texture_urls.0.normal"], "retexture-texture_urls.0.normal.png")
        self.assertEqual(sum(runs.spent(self.state(i)) for i in ("rt-image", "rt-text", "rt-views")), 35)
        self.assertEqual(self.fake.balance, 100 - 35)

    def test_a_changed_model_is_refused_before_anything_is_paid(self) -> None:
        data = retexture_batch(**{"rt-image": {"model": {**MODEL, "sha256": "0" * 64}}})
        with self.assertRaises(common.Failure) as ctx:
            self.run_batch(data)
        self.assertIn("the batch approved", str(ctx.exception))
        self.assertEqual(self.fake.posts(), [])

    def test_the_estimate_names_the_style(self) -> None:
        path = self.raw / "t-batch.toml"
        path.write_text("", encoding="utf-8")
        buf = io.StringIO()
        with mock.patch.object(batches, "load", return_value=parse(retexture_batch())), contextlib.redirect_stdout(buf):
            self.assertEqual(cli.main(["meshy", "estimate", str(path)]), 0)
        out = buf.getvalue()
        self.assertIn("total 35 credits; approved cap 60", out)
        self.assertIn("input 1 as image_style_url", out)
        self.assertIn("3 view input(s) as multiview_image_urls", out)
        self.assertIn("text_style_prompt ('soft smooth toy-like teal skin')", out)
        self.assertIn("every one is ready to send", out)


class InputCheckTest(unittest.TestCase):
    def doc(self, **extra: Any) -> dict[str, Any]:
        prim = {"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "material": 0}
        return {"nodes": [{"mesh": 0}], "meshes": [{"primitives": [prim]}], **extra}

    def problems(self, doc: dict[str, Any]) -> list[str]:
        with TemporaryDirectory() as tmp:
            return meshy.retexture_problems(write_glb(Path(tmp) / "x.glb", doc))

    def test_only_the_mesh_and_its_uv(self) -> None:
        self.assertEqual(self.problems(self.doc()), [])
        bad = self.doc()
        bad["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_1"] = 3
        self.assertIn("attributes", self.problems(bad)[0])
        self.assertIn("skins", self.problems(self.doc(skins=[{"joints": [0]}]))[0])
        self.assertIn("images", self.problems(self.doc(images=[{"uri": "a.png"}]))[0])
        two = self.doc()
        two["nodes"].append({"name": "Icosphere"})
        self.assertIn("2 nodes", self.problems(two)[0])
        morph = self.doc()
        morph["meshes"][0]["primitives"][0]["targets"] = [{"POSITION": 4}]
        self.assertIn("morph", self.problems(morph)[0])


if __name__ == "__main__":
    unittest.main()
