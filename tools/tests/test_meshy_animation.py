"""Animation in the Meshy client (art #25): a rig of a local GLB, text to motion, an animation of a motion clip and
the animation library's listing, against the fake (no network)."""

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

from tests._meshy_fake import GLB, KEY, LIBRARY, PNG, FakeMeshy
from tests.test_meshy_batch import APPROVAL, parse


def animation_batch(**item_overrides: Any) -> dict[str, Any]:
    """A rig of a local GLB with its texture, a text-to-motion clip, an animation of it and two library actions."""
    items = [
        {"id": "man-rig", "kind": "rig", "params": {"height_meters": 1.95},
         "model": {"file": "raw:inputs/man.glb", "provenance": "own work: an assembled character"},
         "texture": {"file": "raw:inputs/man.png", "provenance": "own work: its flat colours baked"}},
        {"id": "crawl", "kind": "text_to_motion", "prompt": "a person crawls forward on hands and knees",
         "params": {"duration": 4, "mode": "prime"}},
        {"id": "man-crawl", "kind": "animate", "source": "man-rig", "motion": "crawl"},
        {"id": "man-lib", "kind": "animate", "source": "man-rig", "params": {"action_ids": [1, 16]}},
    ]
    for item in items:
        item.update(item_overrides.get(item["id"], {}))
    return {"id": "t-batch", "purpose": "tests", "credit_cap": 60, **APPROVAL, "items": items}


class BatchTest(unittest.TestCase):
    def refused(self, data: dict[str, Any]) -> str:
        with self.assertRaises(common.Failure) as ctx:
            parse(data)
        return str(ctx.exception)

    def test_credits_as_the_docs_price_them(self) -> None:
        batch = parse(animation_batch())
        self.assertEqual({i.id: i.credits for i in batch.items},
                         {"man-rig": 5, "crawl": 10, "man-crawl": 3, "man-lib": 6})
        swift = parse(animation_batch(crawl={"params": {"duration": 2.5, "mode": "swift"}}))
        self.assertEqual(swift.item("crawl").credits, 3)
        self.assertEqual(batch.item("man-crawl").depends, ["man-rig", "crawl"])
        self.assertEqual([i.role for i in batch.item("man-rig").inputs], ["model", "texture"])

    def test_text_to_motion_is_checked(self) -> None:
        for params, needle in (({"duration": 2.25}, "0.5 s steps"), ({"duration": 11}, "2 to 10"), ({}, "required"),
                               ({"duration": 4, "mode": "fast"}, "prime, swift"), ({"duration": 4, "fps": 30}, "fps")):
            with self.subTest(params=params):
                self.assertIn(needle, self.refused(animation_batch(crawl={"params": params})))
        self.assertIn("at most 400", self.refused(animation_batch(crawl={"prompt": "x" * 401})))

    def test_a_rig_takes_a_model_or_a_source(self) -> None:
        self.assertIn(".glb", self.refused(animation_batch(**{"man-rig": {"model": {"file": "raw:a.obj",
                                                                                     "provenance": "x"}}})))
        self.assertIn("not both", self.refused(animation_batch(**{"man-rig": {"source": "crawl"}})))
        self.assertIn("provenance", self.refused(animation_batch(**{"man-rig": {"model": {"file": "raw:a.glb"}}})))
        self.assertIn("texture_image_url", self.refused(animation_batch(
            **{"man-rig": {"params": {"texture_image_url": "data:x"}}})))

    def test_an_animation_takes_actions_or_a_motion(self) -> None:
        self.assertIn("only one of", self.refused(animation_batch(**{"man-crawl": {"params": {"action_ids": [1]}}})))
        self.assertIn("text_to_motion item", self.refused(animation_batch(**{"man-crawl": {"motion": "man-lib"}})))
        self.assertIn("unique", self.refused(animation_batch(**{"man-lib": {"params": {"action_ids": [1, 1]}}})))
        self.assertIn("motion_task_id", self.refused(animation_batch(
            **{"man-lib": {"params": {"action_ids": [1], "motion_task_id": "x"}}})))


class RunTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.raw = Path(self._tmp.name)
        self._env = mock.patch.dict(os.environ, {"ART_RAW_DIR": self._tmp.name})
        self._env.start()
        (self.raw / "inputs").mkdir()
        (self.raw / "inputs" / "man.glb").write_bytes(GLB + b"\x02\x00\x00\x00 the model")
        (self.raw / "inputs" / "man.png").write_bytes(PNG + b"palette")
        self.fake = FakeMeshy(balance=374)
        self.log: list[str] = []

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def run_batch(self, data: dict[str, Any]) -> int:
        return runs.Runner(parse(data), self.fake.client(log=self.log), raw=self.raw).run()

    def state(self, item: str) -> dict[str, Any]:
        return json.loads((self.raw / "t-batch" / item / "generation.json").read_text(encoding="utf-8"))

    def test_rig_motion_and_animations(self) -> None:
        self.assertEqual(self.run_batch(animation_batch()), 0, self.log)
        posts = self.fake.posts()
        self.assertEqual([url.rsplit("/", 1)[-1] for url, _ in posts],
                         ["rigging", "text-to-motion", "animations", "animations"])
        rig = posts[0][1]
        self.assertTrue(rig["model_url"].startswith("data:application/octet-stream;base64,"))
        self.assertTrue(rig["texture_image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(rig["height_meters"], 1.95)
        self.assertEqual(posts[1][1], {"prompt": "a person crawls forward on hands and knees", "duration": 4,
                                       "mode": "prime"})
        rig_id = next(t for t in self.fake.tasks if t.endswith("-rig"))
        motion_id = next(t for t in self.fake.tasks if t.endswith("-text_to_motion"))
        self.assertEqual(posts[2][1], {"rig_task_id": rig_id, "motion_task_id": motion_id})
        self.assertEqual(posts[3][1], {"rig_task_id": rig_id, "action_ids": [1, 16]})
        state = self.state("man-rig")
        self.assertNotIn("base64", json.dumps(state))  # the record keeps notes, never the data URIs
        self.assertEqual([i["role"] for i in state["inputs"]], ["model", "texture"])
        self.assertEqual(state["inputs"][0]["sha256"], inputs.sha256(self.raw / "inputs" / "man.glb"))
        crawl = self.state("crawl")
        self.assertEqual([f["name"] for f in crawl["files"]], ["text_to_motion-motion.fbx"])
        self.assertEqual(crawl["files"][0]["key"], "result.motion_url")
        spent = sum(runs.spent(self.state(i)) for i in ("man-rig", "crawl", "man-crawl", "man-lib"))
        self.assertEqual(spent, 5 + 10 + 3 + 6)
        self.assertEqual(self.fake.balance, 374 - spent)

    def test_a_model_that_is_no_glb_is_refused_before_anything_is_paid(self) -> None:
        (self.raw / "inputs" / "man.glb").write_bytes(b"not a model")
        with self.assertRaises(common.Failure) as ctx:
            self.run_batch(animation_batch())
        self.assertIn("binary glTF", str(ctx.exception))
        self.assertEqual(self.fake.posts(), [])

    def test_a_refused_rig_costs_nothing_and_its_followers_wait(self) -> None:
        self.fake.refuse["rig"] = 422
        self.assertEqual(self.run_batch(animation_batch()), 1)
        self.assertEqual(self.state("man-rig")["status"], "failed")
        self.assertEqual([url.rsplit("/", 1)[-1] for url, _ in self.fake.posts()], ["rigging", "text-to-motion"])
        self.assertEqual(self.fake.balance, 374 - 10)


class LibraryTest(unittest.TestCase):
    def test_the_listing_is_saved_with_its_query(self) -> None:
        fake = FakeMeshy()
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "library.json"
            buf = io.StringIO()
            with mock.patch.object(api, "api_key", return_value=KEY), \
                    mock.patch.object(api, "MeshyClient", side_effect=lambda key: fake.client()), \
                    contextlib.redirect_stdout(buf):
                code = cli.main(["meshy", "library", "--category", "WalkAndRun", "--out", str(out)])
            self.assertEqual(code, 0, buf.getvalue())
            saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["answer"], LIBRARY)
        self.assertEqual((saved["count"], saved["category"]), (3, "WalkAndRun"))
        self.assertIn("3 actions", buf.getvalue())
        method, url, headers, _ = fake.requests[0]
        self.assertEqual((method, url), ("GET", api.API_BASE + api.LIBRARY_PATH + "?category=WalkAndRun"))
        self.assertNotIn(KEY, buf.getvalue())
        self.assertEqual(fake.posts(), [])  # a listing submits nothing

    def test_an_answer_without_actions_fails(self) -> None:
        from runner.commands import meshy

        self.assertEqual(meshy.actions_of({"result": LIBRARY}), LIBRARY)
        with self.assertRaises(common.Failure):
            meshy.actions_of({"message": "nothing"})


class PricesTest(unittest.TestCase):
    def test_the_prices_of_the_docs(self) -> None:
        self.assertEqual((batches.RIG_CREDITS, batches.ANIMATION_CREDITS_PER_ACTION), (5, 3))
        self.assertEqual(batches.TEXT_TO_MOTION_CREDITS, {"prime": 10, "swift": 3})
        self.assertEqual(api.TASK_PATHS["text_to_motion"], "/openapi/v1/text-to-motion")


if __name__ == "__main__":
    unittest.main()
