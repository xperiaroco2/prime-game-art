"""The image modes: text-to-image, image-to-image, image-to-3D, multi-image-to-3D and remesh items; local file inputs
as data URIs, `from` and `pick`, prices, and runs against the fake Meshy (no network)."""

from __future__ import annotations

import base64
import contextlib
import hashlib
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

from tests._meshy_fake import KEY, PNG, FakeMeshy
from tests.test_meshy_batch import APPROVAL, parse

JPEG = b"\xff\xd8\xff\xe0"
FRONT = "own work: Blender render of the mannequin, front"


def image_batch(items: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "t-batch",
        "purpose": "tests",
        "credit_cap": 500,
        **APPROVAL,
        "variants": {"c": {"prompt": "a cartoon human concept sheet"}},
        "defaults": {"text_to_image": {"params": {"ai_model": "nano-banana-pro", "remove_background": True}},
                     "image_to_3d": {"params": {"ai_model": "meshy-7.1", "should_remesh": True,
                                                "target_polycount": 7000}},
                     "multi_image_to_3d": {"params": {"ai_model": "meshy-7.1"}}},
        "items": items,
    }
    data.update(overrides)
    return data


CONCEPT = {"id": "c1", "variant": "c", "kind": "text_to_image",
           "params": {"generate_multi_view": True, "pose_mode": "t-pose"}}
CHAIN = [
    CONCEPT,
    {"id": "c1-mq", "variant": "c", "kind": "image_to_image", "prompt": "restyle the mannequin",
     "params": {"ai_model": "gpt-image-2"},
     "images": [{"file": "raw:renders/front.png", "provenance": FRONT}, {"from": "c1", "pick": 2}]},
    {"id": "c1-front", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 1}]},
    {"id": "c1-body", "kind": "multi_image_to_3d", "images": [{"from": "c1"}, {"file": "raw:renders/back.jpg",
                                                                              "provenance": "own work: back"}]},
    {"id": "c1-body-quads", "kind": "remesh", "source": "c1-body", "params": {"topology": "quad"}},
    {"id": "c1-front-low", "kind": "remesh", "source": "c1-front", "params": {"target_polycount": 3000}},
    {"id": "c1-body-rig", "kind": "rig", "source": "c1-body", "params": {"height_meters": 1.75}},
]


class ImageEstimateTest(unittest.TestCase):
    def credits(self, item: dict[str, Any]) -> int:
        return parse(image_batch([CONCEPT, item] if "images" in item else [item])).items[-1].credits

    def test_prices_per_kind_and_model(self) -> None:
        cases = [
            ({"id": "x", "kind": "text_to_image", "prompt": "p", "params": {"ai_model": "nano-banana"}}, 3),
            ({"id": "x", "kind": "text_to_image", "prompt": "p", "params": {"ai_model": "nano-banana-2"}}, 6),
            ({"id": "x", "kind": "text_to_image", "prompt": "p", "params": {"ai_model": "gpt-image-2"}}, 9),
            ({"id": "x", "kind": "text_to_image", "prompt": "p",
              "params": {"ai_model": "nano-banana-pro", "generate_multi_view": True}}, 27),
            ({"id": "x", "kind": "image_to_image", "prompt": "p", "params": {"ai_model": "nano-banana-pro"},
              "images": [{"from": "c1", "pick": 0}]}, 9),
            ({"id": "x", "kind": "image_to_image", "prompt": "p", "params": {"ai_model": "gpt-image-2"},
              "images": [{"from": "c1", "pick": 0}]}, 12),
            ({"id": "x", "kind": "image_to_image", "prompt": "p",
              "params": {"ai_model": "gpt-image-2", "generate_multi_view": True}, "images": [{"from": "c1"}]}, 36),
            ({"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 0}]}, 30),
            ({"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 0}],
              "params": {"should_texture": False}}, 20),
            ({"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 0}],
              "params": {"texture_resolution": "8k"}}, 35),
            ({"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 0}],
              "params": {"ai_model": "meshy-6-lite"}}, 15),
            ({"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 0}],
              "params": {"ai_model": "latest", "model_type": "smart-topology", "texture_resolution": "8k"}}, 20),
            ({"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 0}],
              "params": {"geometry_resolution": "2k"}}, 35),
            ({"id": "x", "kind": "multi_image_to_3d", "images": [{"from": "c1"}]}, 30),
            ({"id": "x", "kind": "multi_image_to_3d", "images": [{"from": "c1"}],
              "params": {"ai_model": "meshy-6", "should_texture": False}}, 20),
        ]
        for item, credits in cases:
            with self.subTest(item=item):
                self.assertEqual(self.credits(item), credits)

    def test_remesh_and_mixed_total(self) -> None:
        batch = parse(image_batch(CHAIN))
        per_item = {i.id: i.credits for i in batch.items}
        self.assertEqual(per_item, {"c1": 27, "c1-mq": 12, "c1-front": 30, "c1-body": 30, "c1-body-quads": 5,
                                    "c1-front-low": 5, "c1-body-rig": 5})
        self.assertEqual(batch.credits, 114)
        self.assertEqual(batch.item("c1").images, 3)
        self.assertEqual(batch.item("c1-front").variant, "c")  # inherited through `from`
        self.assertEqual(batch.item("c1-body-rig").variant, "c")
        self.assertEqual(batch.item("c1-mq").depends, ["c1"])
        self.assertTrue(batch.item("c1-body-quads").textured)

    def test_inputs_are_parsed(self) -> None:
        item = parse(image_batch(CHAIN)).item("c1-mq")
        self.assertEqual(item.inputs, [inputs.Input(file="raw:renders/front.png", provenance=FRONT),
                                       inputs.Input(from_item="c1", pick=2)])


class ImageValidationTest(unittest.TestCase):
    def assert_invalid(self, items: list[dict[str, Any]], message: str) -> None:
        with self.assertRaisesRegex(common.Failure, message):
            parse(image_batch(items))

    def test_rejects_broken_items(self) -> None:
        pick = {"from": "c1", "pick": 0}
        cases = [
            ([{"id": "x", "kind": "text_to_image", "prompt": "p", "params": {"ai_model": "dall-e"}}],
             "ai_model must be one of"),
            ([{"id": "x", "kind": "text_to_image", "params": {"ai_model": "nano-banana"}}], "no prompt"),
            ([{"id": "x", "kind": "text_to_image", "prompt": "p",
               "params": {"generate_multi_view": True, "aspect_ratio": "1:1"}}], "aspect_ratio together"),
            ([{"id": "x", "kind": "text_to_image", "prompt": "p", "params": {"aspect_ratio": "3:2"}}],
             "gpt-image models only"),
            ([{"id": "x", "kind": "text_to_image", "prompt": "p", "params": {"prompt": "q"}}],
             "filled in by the runner"),
            ([{"id": "x", "kind": "text_to_image", "prompt": "p", "param": {}}], "has no key param"),
            ([{"id": "x", "kind": "text_to_image", "prompt": "p", "params": {"remove_backround": True}}],
             "params.remove_backround is not among the text_to_image parameters"),
            ([CONCEPT, {"id": "x", "kind": "image_to_image", "prompt": "p", "images": [pick],
                        "params": {"pose_mode": "t-pose"}}], "params.pose_mode is not among the image_to_image"),
            ([CONCEPT, {"id": "x", "kind": "multi_image_to_3d", "images": [pick],
                        "params": {"model_type": "smart-topology"}}], "params.model_type is not among the multi_image_to_3d"),
            ([CONCEPT, {"id": "m", "kind": "image_to_3d", "images": [pick]},
              {"id": "x", "kind": "remesh", "source": "m", "params": {"target_polycont": 5}}], "params.target_polycont"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "prompt": "p", "images": [pick]}], "has no key prompt"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": 3}]}],
             "pick 3 from 'c1', which makes 3 image"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [{"from": "c1"}]}], "set 'pick'"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [pick, pick]}], "takes 1 to 1 image"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": []}], "takes 1 to 1 image"),
            ([CONCEPT, {"id": "x", "kind": "multi_image_to_3d", "images": [{"from": "c1"}, pick, pick]}],
             "takes 1 to 4 image.*give 5"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [{"from": "nope"}]}], "not an earlier item"),
            ([CONCEPT, {"id": "m", "kind": "image_to_3d", "images": [pick]},
              {"id": "x", "kind": "image_to_3d", "images": [{"from": "m"}]}], "image_to_3d makes no image"),
            ([{"id": "x", "kind": "image_to_3d", "images": [{"file": "a.png"}]}], "'provenance' must say"),
            ([{"id": "x", "kind": "image_to_3d", "images": [{"file": "a.webp", "provenance": "p"}]}],
             "not a .png, .jpg or .jpeg"),
            ([{"id": "x", "kind": "image_to_3d", "images": [{"file": "a.png", "provenance": "p", "sha256": "abc"}]}],
             "64 lower-case hex"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [{"file": "a.png", "from": "c1"}]}],
             "exactly one of 'file' and 'from'"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [{"from": "c1", "pick": -1}]}],
             "image index"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": "c1"}], "must be a list"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [pick], "params": {"image_url": "https://a"}}],
             "filled in by the runner"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [pick],
                        "params": {"texture_image_url": "https://a"}}], "not supported by this client yet"),
            ([CONCEPT, {"id": "x", "kind": "multi_image_to_3d", "images": [pick], "params": {"ai_model": "meshy-t2"}}],
             "multi-image-to-3D takes ai_model"),
            ([CONCEPT, {"id": "x", "kind": "multi_image_to_3d", "images": [pick],
                        "params": {"geometry_resolution": "4k"}}], "takes geometry_resolution standard or 2k"),
            ([CONCEPT, {"id": "x", "kind": "multi_image_to_3d", "images": [pick],
                        "params": {"geometry_resolution": "2k", "ai_model": "meshy-6"}}],
             "geometry_resolution 2k requires ai_model meshy-7.1"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [pick],
                        "params": {"ai_model": "meshy-6-lite", "texture_resolution": "4k"}}], "textures at 2k only"),
            ([CONCEPT, {"id": "x", "kind": "image_to_3d", "images": [pick], "params": {"texture_prompt": "t" * 801}}],
             "texture_prompt is longer"),
            ([CONCEPT, {"id": "x", "kind": "remesh", "source": "c1"}], "a remesh needs a text_to_3d or"),
            ([CONCEPT, {"id": "x", "kind": "remesh", "source": "c1", "params": {"model_url": "https://a"}}],
             "filled in by the runner"),
            ([CONCEPT, {"id": "m", "kind": "image_to_3d", "images": [pick], "params": {"should_texture": False}},
              {"id": "r", "kind": "rig", "source": "m"}], "textured models only"),
            ([CONCEPT, {"id": "r", "kind": "rig", "source": "c1"}], "a rig needs a text_to_3d or image_to_3d"),
        ]
        for items, message in cases:
            with self.subTest(message=message):
                self.assert_invalid(items, message)

    def test_rig_takes_every_textured_model_kind(self) -> None:
        batch = parse(image_batch(CHAIN + [{"id": "q-rig", "kind": "rig", "source": "c1-body-quads"},
                                           {"id": "f-rig", "kind": "rig", "source": "c1-front"}]))
        self.assertEqual([i.credits for i in batch.items[-3:]], [5, 5, 5])

    def test_example_batch_never_runs(self) -> None:
        batch = batches.load("example-image-modes")
        self.assertEqual({i.kind for i in batch.items},
                         {"text_to_image", "image_to_image", "image_to_3d", "multi_image_to_3d", "remesh", "rig"})
        self.assertFalse(batch.approved_by or batch.approved_at or batch.approval_ref)
        self.assertIn("never runs", batches.approval_problems(batch)[0])
        approved = batches.parse({**image_batch(CHAIN), "id": "example-x"}, Path("example-x.toml"))
        self.assertIn("never runs", batches.approval_problems(approved)[0])  # even with approval fields


class InputFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.raw = Path(self._tmp.name)
        self._env = mock.patch.dict(os.environ, {"ART_RAW_DIR": self._tmp.name})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.raw / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_raw_prefix_absolute_and_repository_paths(self) -> None:
        self.assertEqual(inputs.resolve("raw:renders/a.png"), self.raw / "renders" / "a.png")
        self.assertEqual(inputs.resolve(str(self.raw / "b.png")), self.raw / "b.png")
        self.assertEqual(inputs.resolve("batches/c.png"), common.ROOT / "batches" / "c.png")

    def test_file_problems(self) -> None:
        good = self.write("a.png", PNG + b"pixels")
        self.write("fake.png", b"GIF89a")
        self.write("swapped.jpg", PNG + b"pixels")
        self.write("big.png", PNG + b"\0" * inputs.IMAGE_MAX_BYTES)
        sha = hashlib.sha256(good.read_bytes()).hexdigest()
        cases = {
            "raw:a.png": [],
            "raw:missing.png": ["does not exist"],
            "raw:fake.png": ["not a PNG or JPEG"],
            "raw:swapped.jpg": ["image/png file with a .jpg name"],
            "raw:big.png": ["at most 20971520 bytes"],
        }
        for ref, wanted in cases.items():
            with self.subTest(ref=ref):
                found = inputs.file_problems(inputs.Input(file=ref, provenance="p"))
                self.assertEqual(len(found), len(wanted))
                for message, problem in zip(wanted, found):
                    self.assertIn(message, problem)
        self.assertEqual(inputs.file_problems(inputs.Input(file="raw:a.png", provenance="p", sha256=sha)), [])
        changed = inputs.file_problems(inputs.Input(file="raw:a.png", provenance="p", sha256="0" * 64))
        self.assertIn("the batch approved " + "0" * 64, changed[0])

    def test_data_uri_and_scrub(self) -> None:
        path = self.write("j.jpg", JPEG + b"jpeg body")
        uri = inputs.data_uri(path, inputs.media_type(path))
        self.assertTrue(uri.startswith("data:image/jpeg;base64,"))
        self.assertEqual(base64.b64decode(uri.split(",", 1)[1]), path.read_bytes())
        rec = inputs.record(path, "image/jpeg", file="raw:j.jpg", provenance="p")
        body = {"image_urls": [uri, "data:image/png;base64,AAAA"], "ai_model": "meshy-7.1"}
        scrubbed = inputs.scrub(body, {uri: inputs.note(0, rec)})
        self.assertEqual(scrubbed["image_urls"][0],
                         f"<data URI of input 0: image/jpeg, {path.stat().st_size} bytes, sha256 {rec['sha256']}>")
        self.assertEqual(scrubbed["image_urls"][1], "<data URI, 26 characters>")
        self.assertEqual(scrubbed["ai_model"], "meshy-7.1")


class ImageRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.raw = Path(self._tmp.name)
        self._env = mock.patch.dict(os.environ, {"ART_RAW_DIR": self._tmp.name})
        self._env.start()
        self.front = self.raw / "renders" / "front.png"
        self.front.parent.mkdir(parents=True)
        self.front.write_bytes(PNG + b"front render")
        self.back = self.raw / "renders" / "back.jpg"
        self.back.write_bytes(JPEG + b"back render")
        self.fake = FakeMeshy(balance=1000)
        self.log: list[str] = []

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def runner(self, items: list[dict[str, Any]] | None = None, **kwargs: Any) -> runs.Runner:
        batch = parse(image_batch(items or CHAIN, **kwargs.pop("batch", {})))
        return runs.Runner(batch, self.fake.client(log=self.log), raw=self.raw, **kwargs)

    def state(self, item: str) -> dict[str, Any]:
        return json.loads((self.raw / "t-batch" / item / "generation.json").read_text(encoding="utf-8"))

    def posted(self, endpoint: str) -> list[dict[str, Any]]:
        return [body for url, body in self.fake.posts() if url.endswith(endpoint)]

    def test_the_whole_chain(self) -> None:
        self.assertEqual(self.runner().run(), 0)
        self.assertEqual([url.split("/openapi/")[1] for url, _ in self.fake.posts()],
                         ["v1/text-to-image", "v1/image-to-image", "v1/image-to-3d", "v1/multi-image-to-3d",
                          "v1/remesh", "v1/remesh", "v1/rigging"])

        # text to image: the prompt and parameters, three images downloaded in Meshy's order, pick addresses them
        self.assertEqual(self.posted("/text-to-image")[0],
                         {"prompt": "a cartoon human concept sheet", "ai_model": "nano-banana-pro",
                          "remove_background": True, "generate_multi_view": True, "pose_mode": "t-pose"})
        concept = self.state("c1")
        images = runs.image_files(concept)
        self.assertEqual([f["key"] for f in images], ["image_urls.0", "image_urls.1", "image_urls.2"])
        self.assertEqual([f["name"] for f in images], [f"text_to_image-image_urls.{n}.png" for n in range(3)])
        self.assertEqual(concept["tasks"]["text_to_image"]["consumed_credits"], 27)
        self.assertTrue(any("pick 0 = text_to_image-image_urls.0.png" in line for line in self.log))

        # image to image: a local file and a picked image, both as data URIs, recorded with sha256 and provenance
        body = self.posted("/image-to-image")[0]
        self.assertEqual(body["prompt"], "restyle the mannequin")
        refs = body["reference_image_urls"]
        self.assertEqual(base64.b64decode(refs[0].split(",", 1)[1]), self.front.read_bytes())
        self.assertTrue(refs[0].startswith("data:image/png;base64,"))
        picked = self.raw / "t-batch" / "c1" / images[2]["name"]
        self.assertEqual(base64.b64decode(refs[1].split(",", 1)[1]), picked.read_bytes())
        self.assertIn(b"/2/image.png", picked.read_bytes())  # image 2 of the set, not another one
        mq = self.state("c1-mq")
        self.assertEqual(mq["inputs"][0]["file"], "raw:renders/front.png")
        self.assertEqual(mq["inputs"][0]["provenance"], FRONT)
        self.assertEqual(mq["inputs"][0]["sha256"], hashlib.sha256(self.front.read_bytes()).hexdigest())
        self.assertEqual((mq["inputs"][1]["from"], mq["inputs"][1]["pick"]), ("c1", 2))
        self.assertEqual(mq["inputs"][1]["sha256"], images[2]["sha256"])
        self.assertIn(concept["tasks"]["text_to_image"]["id"], mq["inputs"][1]["provenance"])
        recorded = mq["tasks"]["image_to_image"]["request"]["reference_image_urls"]
        self.assertTrue(recorded[0].startswith("<data URI of input 0: image/png"))

        # image to 3D: one picked view; multi-image to 3D: every view, then a local JPEG
        front = self.posted("/image-to-3d")[0]
        self.assertEqual(base64.b64decode(front["image_url"].split(",", 1)[1]),
                         (self.raw / "t-batch" / "c1" / images[1]["name"]).read_bytes())
        self.assertEqual({k: v for k, v in front.items() if k != "image_url"},
                         {"ai_model": "meshy-7.1", "should_remesh": True, "target_polycount": 7000})
        multi = self.posted("/multi-image-to-3d")[0]["image_urls"]
        self.assertEqual(len(multi), 4)
        self.assertTrue(multi[3].startswith("data:image/jpeg;base64,"))
        body_state = self.state("c1-body")
        self.assertEqual([(i.get("from"), i.get("pick")) for i in body_state["inputs"]],
                         [("c1", 0), ("c1", 1), ("c1", 2), (None, None)])
        self.assertIn("multi_image_to_3d-model.glb", [f["name"] for f in body_state["files"]])

        # remesh: a multi-image model goes as its GLB, an image-to-3D model by task id
        quads = self.posted("/remesh")[0]
        self.assertTrue(quads["model_url"].startswith("data:application/octet-stream;base64,"))
        self.assertEqual(quads["topology"], "quad")
        glb = self.raw / "t-batch" / "c1-body" / "multi_image_to_3d-model.glb"
        self.assertEqual(base64.b64decode(quads["model_url"].split(",", 1)[1]), glb.read_bytes())
        self.assertEqual(self.state("c1-body-quads")["inputs"][0]["from"], "c1-body")
        low = self.posted("/remesh")[1]
        self.assertEqual(low, {"input_task_id": self.state("c1-front")["tasks"]["image_to_3d"]["id"],
                               "target_polycount": 3000})
        self.assertIn("remesh-model.glb", [f["name"] for f in self.state("c1-front-low")["files"]])

        # rig of a multi-image model by its task id
        self.assertEqual(self.posted("/rigging")[0],
                         {"input_task_id": body_state["tasks"]["multi_image_to_3d"]["id"], "height_meters": 1.75})

        # no data URI and no key in any record
        for path in (self.raw / "t-batch").rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(";base64,", text, path)
            self.assertNotIn(KEY, text, path)
        for item in ("c1", "c1-mq", "c1-front", "c1-body", "c1-body-quads", "c1-front-low", "c1-body-rig"):
            state = self.state(item)
            self.assertEqual(state["status"], "done", item)
            for entry in state["files"]:
                data = (self.raw / "t-batch" / item / entry["name"]).read_bytes()
                self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())

        # a second run pays for nothing and sends nothing
        before = len(self.fake.requests)
        self.assertEqual(self.runner().run(), 0)
        self.assertEqual(len(self.fake.requests), before)

    def test_remesh_of_a_text_to_3d_model_uses_its_refine(self) -> None:
        items = [{"id": "t", "variant": "c", "kind": "text_to_3d"}, {"id": "t-remesh", "kind": "remesh", "source": "t"}]
        self.assertEqual(self.runner(items).run(), 0)
        refine = self.state("t")["tasks"]["refine"]["id"]
        self.assertEqual(self.posted("/remesh"), [{"input_task_id": refine}])

    def test_a_missing_input_file_stops_the_run_before_any_call(self) -> None:
        self.back.unlink()
        with self.assertRaisesRegex(common.Failure, r"nothing was submitted:\n  c1-body: raw:renders/back.jpg"):
            self.runner().run()
        self.assertEqual(self.fake.requests, [])

    def test_a_pinned_sha256_must_match(self) -> None:
        items = [{"id": "f", "kind": "image_to_3d",
                  "images": [{"file": "raw:renders/front.png", "provenance": FRONT, "sha256": "a" * 64}]}]
        with self.assertRaisesRegex(common.Failure, "the batch approved a{64}"):
            self.runner(items).run()
        self.assertEqual(self.fake.requests, [])
        items[0]["images"][0]["sha256"] = hashlib.sha256(self.front.read_bytes()).hexdigest()
        self.assertEqual(self.runner(items).run(), 0)

    def test_an_item_waits_for_its_from_source(self) -> None:
        self.assertEqual(self.runner(only=["c1-front"]).run(), 1)
        self.assertEqual(self.fake.posts(), [])
        self.assertTrue(any("c1-front: waits for c1" in line for line in self.log))

    def test_a_changed_source_image_fails_only_its_item(self) -> None:
        self.assertEqual(self.runner(only=["c1"]).run(), 0)
        (self.raw / "t-batch" / "c1" / "text_to_image-image_urls.1.png").write_bytes(PNG + b"edited")
        self.assertEqual(self.runner(only=["c1-front", "c1-body"]).run(), 1)
        self.assertIn("image_to_3d inputs:", self.state("c1-front")["error"])
        self.assertIn("no longer matches", self.state("c1-front")["error"])
        self.assertEqual(self.state("c1-front")["tasks"], {})
        self.assertEqual(len(self.fake.posts()), 1)  # c1 only; c1-body fails the same way, nothing is submitted

    def test_an_interrupted_image_item_resumes_without_resending(self) -> None:
        items = [CONCEPT, CHAIN[2]]
        self.assertEqual(self.runner(items, only=["c1"]).run(), 0)
        self.fake.interrupt_on = self.fake.task_gets + 1  # the first poll of c1-front
        with self.assertRaises(KeyboardInterrupt):
            self.runner(items).run()
        self.assertEqual(self.state("c1-front")["status"], "running")
        self.fake.interrupt_on = None
        self.assertEqual(self.runner(items).run(), 0)
        self.assertEqual(len(self.posted("/image-to-3d")), 1)
        self.assertEqual(self.state("c1-front")["inputs"][0]["pick"], 1)

    def test_a_request_too_large_fails_its_item_and_the_run_goes_on(self) -> None:
        self.fake.refuse = {"multi_image_to_3d": 413}
        self.assertEqual(self.runner().run(), 1)
        self.assertIn("refused", self.state("c1-body")["error"])
        self.assertEqual(self.state("c1-front-low")["status"], "done")
        self.assertFalse((self.raw / "t-batch" / "c1-body-rig").exists())  # waits for its source

    def test_the_cap_with_mixed_kinds(self) -> None:
        items = [CONCEPT, CHAIN[2], CHAIN[5]]  # 27 + 30 + 5 = 62
        with self.assertRaisesRegex(common.Failure, "exceeds the approved cap of 61"):
            self.runner(items, batch={"credit_cap": 61}).run()
        self.assertEqual(self.fake.requests, [])

        self.fake.cost["text_to_image"] = 12  # Meshy charged 36 for the multi-view set, 9 over the estimate
        with self.assertRaisesRegex(common.Failure, r"c1-front-low: 5 more credits would pass the approved cap of 66 "
                                                    r"\(66 spent already\)"):
            self.runner(items, batch={"credit_cap": 66}).run()
        self.assertEqual(len(self.fake.posts()), 2)
        self.assertEqual(runs.spent(self.state("c1")), 36)
        self.assertFalse((self.raw / "t-batch" / "c1-front-low").exists())

    def test_status_lines_for_image_items(self) -> None:
        self.runner(only=["c1"]).run()
        batch = parse(image_batch(CHAIN))
        self.assertIn("3 files", runs.item_status(batch, batch.item("c1"), self.raw))
        self.assertIn("not started", runs.item_status(batch, batch.item("c1-mq"), self.raw))


class LongErrorTest(unittest.TestCase):
    def test_a_refusal_quoting_our_data_uri_is_cut_short(self) -> None:
        fake = FakeMeshy()
        echo = "invalid image_url: data:image/png;base64," + "A" * 100_000
        fake.queue = [api.Response(400, {}, json.dumps({"message": echo}).encode())]
        with self.assertRaises(api.MeshyError) as caught:
            fake.client().create("image_to_3d", {"image_url": "data:image/png;base64,AAAA"})
        self.assertEqual(caught.exception.status, 400)
        self.assertLess(len(str(caught.exception)), 400)


class ImageCommandTest(unittest.TestCase):
    def test_estimate_of_the_example_batch(self) -> None:
        out = io.StringIO()
        with TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"ART_RAW_DIR": tmp}), \
                contextlib.redirect_stdout(out):
            code = cli.main(["meshy", "estimate", "example-image-modes"])
        text = out.getvalue()
        self.assertEqual(code, 0)
        for kind in ("text_to_image", "image_to_image", "image_to_3d", "multi_image_to_3d", "remesh"):
            self.assertIn(kind, text)
        self.assertIn("makes 3 images", text)
        self.assertIn("input 0: from c1-concept (all its images)", text)
        self.assertIn("never runs", text)
        self.assertIn("input files: 3 not ready", text)

    def test_estimate_prints_the_sha256_to_pin(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "front.png").write_bytes(PNG + b"x")
            batch_file = Path(tmp) / "t-batch.toml"
            batch_file.write_text(
                'id = "t-batch"\ncredit_cap = 30\n[[items]]\nid = "a"\nkind = "image_to_3d"\n'
                'images = [{ file = "raw:front.png", provenance = "own work" }]\n', encoding="utf-8")
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"ART_RAW_DIR": tmp}), contextlib.redirect_stdout(out):
                code = cli.main(["meshy", "estimate", str(batch_file)])
        self.assertEqual(code, 0)
        sha = hashlib.sha256(PNG + b"x").hexdigest()
        self.assertIn(f"raw:front.png (own work): 9 bytes, sha256 {sha} (not pinned)", out.getvalue())
        self.assertIn("input files: every one is ready to send", out.getvalue())

    def test_run_refuses_the_example_before_reading_the_key(self) -> None:
        out = io.StringIO()
        with mock.patch("runner.commands._meshy_api.api_key") as key, contextlib.redirect_stdout(out):
            code = cli.main(["meshy", "run", "example-image-modes"])
        self.assertEqual(code, 1)
        key.assert_not_called()
        self.assertIn("never runs", out.getvalue())


if __name__ == "__main__":
    unittest.main()
