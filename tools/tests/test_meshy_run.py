"""Running batches against the fake Meshy: submit, poll, download, records, refusals, the cap, resume, redaction."""

from __future__ import annotations

import contextlib
import csv
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
from runner.commands import _meshy_run as runs

from tests._meshy_fake import KEY, FakeMeshy
from tests.test_meshy_batch import batch_data, parse


class RunTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.raw = Path(self._tmp.name)
        self.fake = FakeMeshy(balance=1000)
        self.log: list[str] = []

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def runner(self, data: dict[str, Any] | None = None, **kwargs: Any) -> runs.Runner:
        batch = parse(data or batch_data())
        return runs.Runner(batch, self.fake.client(log=self.log), raw=self.raw, **kwargs)

    def state(self, item: str) -> dict[str, Any]:
        return json.loads((self.raw / "t-batch" / item / "generation.json").read_text(encoding="utf-8"))

    def log_rows(self) -> list[dict[str, str]]:
        with (self.raw / "t-batch" / "log.csv").open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    # --- the happy path -----------------------------------------------------------------------------------------

    def test_runs_every_kind_and_records_it(self) -> None:
        self.assertEqual(self.runner().run(), 0)
        posts = self.fake.posts()
        self.assertEqual([url.rsplit("/", 1)[-1] for url, _ in posts],
                         ["text-to-3d", "text-to-3d", "text-to-3d", "text-to-3d", "rigging", "animations"])
        preview_id = next(t for t in self.fake.tasks if t.endswith("-preview"))
        self.assertEqual(posts[0][1], {"mode": "preview", "prompt": "a cartoon human", "ai_model": "meshy-7.1",
                                       "topology": "triangle"})
        self.assertEqual(posts[1][1], {"mode": "refine", "preview_task_id": preview_id, "enable_pbr": False})

        state = self.state("a-1")
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["prompt"], "a cartoon human")
        self.assertEqual(state["model_version"], "meshy-7.1")
        self.assertEqual(state["plan"], "Meshy Pro (monthly)")
        self.assertEqual(state["terms_url"], "https://www.meshy.ai/terms-of-use")
        self.assertEqual(state["licence"], "owned by the customer on a paid plan (Meshy terms 3.2)")
        self.assertEqual(state["balance_before"], 1000)
        self.assertEqual(state["balance_after"], 970)
        self.assertEqual(state["tasks"]["preview"]["consumed_credits"], 20)
        self.assertEqual(state["tasks"]["refine"]["status"], "SUCCEEDED")
        self.assertTrue(state["started_at"] and state["finished_at"])
        self.assertEqual(state["approval"]["ref"], batch_data()["approval_ref"])
        names = sorted(f["name"] for f in state["files"])
        self.assertEqual(names, ["preview-model.fbx", "preview-model.glb", "preview-preview.png", "refine-model.fbx",
                                 "refine-model.glb", "refine-preview.png", "refine-texture_0.png"])
        for entry in state["files"]:
            data = (self.raw / "t-batch" / "a-1" / entry["name"]).read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(entry["bytes"], len(data))
        self.assertFalse(list((self.raw / "t-batch").rglob("*.part")))

        rig = self.state("a-1-rig")
        refine_id = state["tasks"]["refine"]["id"]
        self.assertEqual(rig["tasks"]["rig"]["request"], {"input_task_id": refine_id, "height_meters": 1.8})
        self.assertIn("rig-Character_output.glb", [f["name"] for f in rig["files"]])
        walk = self.state("a-1-walk")
        self.assertEqual(walk["tasks"]["animate"]["request"]["rig_task_id"], rig["tasks"]["rig"]["id"])
        self.assertEqual(walk["tasks"]["animate"]["consumed_credits"], 6)

        rows = self.log_rows()
        self.assertEqual([r["item"] for r in rows], ["a-1", "b-1", "a-1-rig", "a-1-walk"])
        self.assertEqual({r["status"] for r in rows}, {"done"})
        self.assertEqual(rows[0]["credits"], "30")
        self.assertEqual(rows[0]["balance_before"], "1000")

    def test_second_run_skips_finished_items(self) -> None:
        self.runner().run()
        before = len(self.fake.requests)
        self.assertEqual(self.runner().run(), 0)
        self.assertEqual(len(self.fake.posts()), 6)
        self.assertEqual(len(self.fake.requests), before)  # not even a balance read
        self.assertEqual(len(self.log_rows()), 4)

    def test_only_chosen_items(self) -> None:
        self.assertEqual(self.runner(only=["b-1"]).run(), 0)
        self.assertEqual(len(self.fake.posts()), 2)
        self.assertFalse((self.raw / "t-batch" / "a-1").exists())

    def test_rig_waits_for_its_source(self) -> None:
        self.assertEqual(self.runner(only=["a-1-rig"]).run(), 1)
        self.assertEqual(self.fake.posts(), [])

    # --- refusals -----------------------------------------------------------------------------------------------

    def test_refuses_a_batch_without_approval(self) -> None:
        for name in ("approved_by", "approved_at", "approval_ref"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(common.Failure, "may not run"):
                    self.runner(batch_data(**{name: ""})).run()
        self.assertEqual(self.fake.requests, [])
        self.assertFalse(any(self.raw.iterdir()))

    def test_refuses_an_estimate_over_the_cap(self) -> None:
        with self.assertRaisesRegex(common.Failure, "exceeds the approved cap"):
            self.runner(batch_data(credit_cap=55)).run()
        self.assertEqual(self.fake.requests, [])

    def test_stops_when_real_spending_would_pass_the_cap(self) -> None:
        self.fake.cost["preview"] = 40  # Meshy charged more than the estimate
        data = batch_data(credit_cap=60, items=batch_data()["items"][:2])
        data["items"][1]["preview"] = {"ai_model": "meshy-7.1"}
        with self.assertRaisesRegex(common.Failure, "pass the approved cap of 60"):
            self.runner(data).run()
        self.assertEqual(len(self.fake.posts()), 2)  # a-1 only; b-1 was never submitted
        self.assertFalse((self.raw / "t-batch" / "b-1").exists())

    def test_stops_when_the_balance_is_too_low(self) -> None:
        self.fake.balance = 25
        with self.assertRaisesRegex(common.Failure, "the Meshy balance is 25"):
            self.runner().run()
        self.assertEqual(self.fake.posts(), [])

    # --- interruption and failure -------------------------------------------------------------------------------

    def test_resumes_an_interrupted_item_from_its_task_id(self) -> None:
        data = batch_data(items=batch_data()["items"][:1])
        self.fake.interrupt_on = 3  # preview polls twice; the first refine poll is interrupted
        with self.assertRaises(KeyboardInterrupt):
            self.runner(data).run()
        state = self.state("a-1")
        self.assertEqual(state["status"], "running")
        self.assertEqual(set(state["tasks"]), {"preview", "refine"})
        refine_id = state["tasks"]["refine"]["id"]

        self.fake.interrupt_on = None
        self.assertEqual(self.runner(data).run(), 0)
        self.assertEqual(len(self.fake.posts()), 2)  # nothing submitted twice
        state = self.state("a-1")
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["tasks"]["refine"]["id"], refine_id)
        self.assertEqual(state["balance_before"], 1000)
        self.assertEqual(len(state["files"]), 7)
        self.assertTrue(any("resumed" in line for line in self.log))

    def test_failed_task_is_recorded_and_retried_only_on_request(self) -> None:
        data = batch_data(items=batch_data()["items"][:1])
        self.fake.fail = {"refine"}
        self.assertEqual(self.runner(data).run(), 1)
        state = self.state("a-1")
        self.assertEqual(state["status"], "failed")
        self.assertIn("the fake failed it", state["error"])
        self.assertEqual(self.log_rows()[0]["status"], "failed")

        self.fake.fail = set()
        self.assertEqual(self.runner(data).run(), 1)  # a failed item is not resubmitted silently
        self.assertEqual(len(self.fake.posts()), 2)

        self.assertEqual(self.runner(data, retry_failed=True).run(), 0)
        posts = self.fake.posts()
        self.assertEqual(len(posts), 3)  # only the refine again; the preview is reused
        self.assertEqual(posts[2][1]["mode"], "refine")
        self.assertEqual(self.state("a-1")["status"], "done")

    def test_an_unsure_submit_is_not_repeated_without_retry_failed(self) -> None:
        data = batch_data(items=batch_data()["items"][:1])
        self.fake.raise_on_post = TimeoutError("read timed out")
        with self.assertRaisesRegex(api.MeshyError, "may have been created"):
            self.runner(data).run()
        self.assertEqual(self.state("a-1")["status"], "failed")
        self.fake.raise_on_post = None
        self.assertEqual(self.runner(data).run(), 1)
        self.assertEqual(len(self.fake.posts()), 1)
        self.assertEqual(self.runner(data, retry_failed=True).run(), 0)
        self.assertEqual(len(self.fake.posts()), 3)

    def test_a_refused_submit_fails_its_item_and_the_run_goes_on(self) -> None:
        self.fake.refuse = {"preview": 400}
        data = batch_data(items=batch_data()["items"][:2])
        self.assertEqual(self.runner(data).run(), 1)
        state = self.state("a-1")
        self.assertEqual(state["status"], "failed")
        self.assertIn("preview refused: POST /openapi/v2/text-to-3d: HTTP 400", state["error"])
        self.assertEqual(state["tasks"], {})
        self.assertEqual([r["item"] for r in self.log_rows()], ["a-1", "b-1"])
        self.assertEqual([r["status"] for r in self.log_rows()], ["failed", "failed"])
        self.assertEqual(self.fake.tasks, {})

        self.fake.refuse = {"rig": 422}  # a failed pose estimate: the animation after it waits, the run ends
        self.assertEqual(self.runner(retry_failed=True).run(), 1)
        self.assertEqual(self.state("a-1")["status"], "done")
        self.assertEqual(self.state("b-1")["status"], "done")
        self.assertIn("rig refused", self.state("a-1-rig")["error"])
        self.assertFalse((self.raw / "t-batch" / "a-1-walk").exists())

    def test_a_bad_key_or_no_credits_stops_the_run(self) -> None:
        self.fake.refuse = {"preview": 402}
        with self.assertRaisesRegex(api.MeshyError, "HTTP 402"):
            self.runner().run()
        self.assertFalse((self.raw / "t-batch" / "b-1").exists())

    def test_status_lines(self) -> None:
        batch = parse(batch_data())
        self.assertIn("not started", runs.item_status(batch, batch.item("a-1"), self.raw))
        self.runner().run()
        (self.raw / "t-batch" / "a-1" / "refine-model.glb").unlink()
        line = runs.item_status(batch, batch.item("a-1"), self.raw)
        self.assertIn("done", line)
        self.assertIn("MISSING refine-model.glb", line)


class FileNamesTest(unittest.TestCase):
    def test_collisions_fall_back_to_the_key_path(self) -> None:
        urls = [("result.a", "https://x.test/1/model.glb"), ("result.b", "https://x.test/2/model.glb")]
        self.assertEqual([n for n, _ in runs.file_names("rig", urls)], ["rig-result.a.glb", "rig-result.b.glb"])

    def test_inputs_are_not_results(self) -> None:
        task = {"texture_image_url": "https://in.test/a.png", "model_urls": {"glb": "https://x.test/m.glb"}}
        self.assertEqual(runs.result_urls(task), [("model_urls.glb", "https://x.test/m.glb")])


class CommandTest(unittest.TestCase):
    def test_the_command_never_prints_the_key(self) -> None:
        boom = OSError(f"connection reset while sending Bearer {KEY}")
        out = io.StringIO()
        with (
            mock.patch.object(api.common, "env", side_effect=lambda name: KEY if name == "MESHY_API_KEY" else None),
            mock.patch.object(api.UrllibTransport, "request", side_effect=boom),
            mock.patch("time.sleep"),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            code = cli.main(["meshy", "balance"])
        self.assertEqual(code, 1)
        self.assertNotIn(KEY, out.getvalue())
        self.assertIn(api.REDACTED, out.getvalue())

    def test_run_refuses_before_reading_the_key(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "t-batch.toml"
            path.write_text('id = "t-batch"\ncredit_cap = 10\n[[items]]\nid = "a"\nvariant = "a"\nkind = "text_to_3d"\n'
                            'prompt = "x"\n', encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(api, "api_key") as key, contextlib.redirect_stdout(out):
                code = cli.main(["meshy", "run", str(path)])
            self.assertEqual(code, 1)
            key.assert_not_called()
            self.assertIn("'approved_by' is missing", out.getvalue())
            self.assertIn("exceeds the approved cap of 10", out.getvalue())

    def test_status_command_reads_the_raw_folder(self) -> None:
        with TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"ART_RAW_DIR": tmp}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(["meshy", "status", "2026-10-b1-bodies"])
        self.assertEqual(code, 0)
        self.assertIn("v3-4", out.getvalue())
        self.assertIn("0 credits spent of the approved cap 360", out.getvalue())


if __name__ == "__main__":
    unittest.main()
