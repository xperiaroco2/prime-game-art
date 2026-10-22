"""The OpenAI image client: the batch schema, the dollar cap, multipart encoding, retries, and the key kept out of
every log and generation.json (a fake transport, no network)."""

from __future__ import annotations

import argparse
import base64
import contextlib
import csv
import email.parser
import email.policy
import io
import json
import math
import struct
import tomllib
import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from runner import cli, common
from runner.commands import _openai_api as api
from runner.commands import _openai_batch as batches
from runner.commands import _openai_run as runs
from runner.commands import openai_images
from runner.commands._meshy_api import Clock, Response

KEY = "sk-proj-TEST_secret_openai_key_0123456789"
MASKED = "sk-proj-****************************6789"  # how OpenAI's own 401 message shows a key


def jpeg(width: int, height: int) -> bytes:
    """The header of a baseline JPEG, an APP0 segment and then the frame (SOF0) with its size; enough to measure."""
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + b"\xff" + sof + b"\xff\xd9"  # one fill byte before the frame


def png(width: int = 4, height: int = 2) -> bytes:
    """A real, tiny PNG."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + b"\x80" * (width * 3) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


USAGE = {"input_tokens": 1500, "input_tokens_details": {"text_tokens": 300, "image_tokens": 1200},
         "output_tokens": 343, "total_tokens": 1843}


def ok_answer(n: int = 1, usage: dict[str, Any] | None = None) -> Response:
    body = {"created": 1, "data": [{"b64_json": base64.b64encode(png()).decode()} for _ in range(n)],
            "usage": usage or USAGE, "size": "1536x1024", "quality": "medium", "output_format": "png"}
    return Response(200, {"x-request-id": "req_123"}, json.dumps(body).encode())


class FakeClock(Clock):
    def __init__(self) -> None:
        self.t = 1_790_000_000.0
        self.sleeps: list[float] = []
        super().__init__(now=lambda: self.t, sleep=self._sleep)

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class FakeOpenAI:
    """Answers each POST from a queue (default: a good answer), records every request."""

    def __init__(self, queue: list[Any] | None = None) -> None:
        self.queue = list(queue or [])
        self.requests: list[tuple[str, str, dict[str, str], bytes]] = []
        self.clock = FakeClock()

    def request(self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> Response:
        self.requests.append((method, url, headers, body or b""))
        assert timeout < 170
        self.clock.t += 30
        item = self.queue.pop(0) if self.queue else ok_answer()
        if isinstance(item, Exception):
            raise item
        return item

    def client(self, logs: list[str] | None = None) -> api.OpenAIClient:
        sink = logs if logs is not None else []
        return api.OpenAIClient(KEY, transport=self, clock=self.clock, log=sink.append)


def batch_data(**over: Any) -> dict[str, Any]:
    data = {"id": "t-batch", "service": "openai-images", "purpose": "a test", "plan": "OpenAI API, prepaid",
            "terms_url": "https://openai.com/policies/services-agreement/", "licence": "owned by the customer",
            "cost_cap_usd": 1.0, "approved_by": "xperiaroco2", "approved_at": "2026-10-20",
            "approval_ref": "https://github.com/xperiaroco2/prime-game-art/issues/196", "model": "gpt-image-2.5-sunburst",
            "quality": "medium", "defaults": {"size": "1536x1024"},
            "items": [{"id": "g1", "kind": "generate", "prompt": "a teal vinyl toy head, front view"}]}
    data.update(over)
    return data


def parse(**over: Any) -> batches.Batch:
    return batches.parse(batch_data(**over), Path("t-batch.toml"))


def errors_of(**over: Any) -> str:
    with unittest.TestCase().assertRaises(common.Failure) as ctx:
        parse(**over)
    return str(ctx.exception)


class SchemaTest(unittest.TestCase):
    def test_a_minimal_batch_parses(self) -> None:
        batch = parse()
        item = batch.items[0]
        self.assertEqual((item.kind, item.quality, item.size, item.n, item.model),
                         ("generate", "medium", "1536x1024", 1, "gpt-image-2.5-sunburst"))
        self.assertEqual(batches.approval_problems(batch), [])

    def test_quality_is_required_and_only_medium_or_high(self) -> None:
        data = batch_data()
        del data["quality"]
        with self.assertRaisesRegex(common.Failure, "'quality' is required"):
            batches.parse(data, Path("t-batch.toml"))
        self.assertIn("'quality' is required", errors_of(quality="low"))
        self.assertIn("quality 'max' is not one of medium, high",
                      errors_of(items=[{"id": "g1", "kind": "generate", "prompt": "x", "quality": "max"}]))
        self.assertEqual(parse(items=[{"id": "g1", "kind": "generate", "prompt": "x", "quality": "high"}])
                         .items[0].quality, "high")

    def test_the_dollar_cap_is_required(self) -> None:
        data = batch_data()
        del data["cost_cap_usd"]
        with self.assertRaisesRegex(common.Failure, "cost_cap_usd"):
            batches.parse(data, Path("t-batch.toml"))
        self.assertIn("cost_cap_usd", errors_of(cost_cap_usd=0))

    def test_service_model_size_and_unknown_keys(self) -> None:
        self.assertIn('service = "openai-images" is required', errors_of(service="meshy"))
        self.assertIn("'model' must be one of", errors_of(model="gpt-image-1"))
        # the standing permission names Sunburst only; Flare needs the engineer's own yes and a code change
        self.assertIn("'model' must be one of gpt-image-2.5-sunburst", errors_of(model="gpt-image-2.5-flare"))
        self.assertIn("auto is refused", errors_of(defaults={"size": "auto"}))
        self.assertIn("multiples of 16", errors_of(defaults={"size": "1000x1000"}))
        self.assertIn("3 times", errors_of(defaults={"size": "3840x1024"}))
        self.assertIn("no key credit_cap", errors_of(credit_cap=5))
        self.assertIn("no key seed", errors_of(items=[{"id": "g1", "kind": "generate", "prompt": "x", "seed": 1}]))
        self.assertIn("kind must be", errors_of(items=[{"id": "g1", "kind": "text_to_image", "prompt": "x"}]))

    def test_images_go_with_edits_only(self) -> None:
        image = {"file": "raw:a.png", "provenance": "own render"}
        self.assertIn("takes no images",
                      errors_of(items=[{"id": "g1", "kind": "generate", "prompt": "x", "images": [image]}]))
        self.assertIn("1 to 16 images", errors_of(items=[{"id": "e1", "kind": "edit", "prompt": "x"}]))
        self.assertIn("moderation", errors_of(items=[{"id": "e1", "kind": "edit", "prompt": "x", "images": [image],
                                                     "moderation": "low"}]))
        batch = parse(items=[{"id": "e1", "kind": "edit", "prompt": "x", "images": [image]},
                             {"id": "e2", "kind": "edit", "prompt": "y", "images": [{"from": "e1", "pick": 0}]}])
        self.assertEqual(batch.items[1].depends, ["e1"])
        self.assertIn("makes 1 image", errors_of(items=[
            {"id": "e1", "kind": "edit", "prompt": "x", "images": [image]},
            {"id": "e2", "kind": "edit", "prompt": "y", "images": [{"from": "e1", "pick": 1}]}]))

    def test_variants_and_defaults_merge(self) -> None:
        batch = parse(defaults={"size": "1024x1024", "n": 2}, variants={"v": {"prompt": "from the variant",
                                                                              "size": "1024x1536"}},
                      items=[{"id": "g1", "kind": "generate", "variant": "v"},
                             {"id": "g2", "kind": "generate", "variant": "v", "n": 1, "prompt": "own"}])
        self.assertEqual([(i.prompt, i.size, i.n) for i in batch.items],
                         [("from the variant", "1024x1536", 2), ("own", "1024x1536", 1)])

    def test_estimate_scales_with_quality_size_and_inputs(self) -> None:
        medium = parse().items[0]
        high = parse(quality="high").items[0]
        self.assertEqual(medium.tokens()["image_out"], 686)  # 343 measured, times the margin 2
        self.assertEqual(high.tokens()["image_out"], 2744)
        square = parse(defaults={"size": "1024x1024"}).items[0]
        self.assertLess(square.tokens()["image_out"], medium.tokens()["image_out"])
        self.assertAlmostEqual(batches.cost({"text_in": 1_000_000, "image_in": 1_000_000, "image_out": 1_000_000}),
                               43.0)

    def test_reference_images_are_priced_by_their_pixels(self) -> None:
        with TemporaryDirectory() as tmp:
            measured, large, small, photo = (Path(tmp) / n for n in ("m.png", "l.png", "s.png", "p.jpg"))
            measured.write_bytes(png(380, 960))
            large.write_bytes(png(1536, 1024))
            small.write_bytes(png(8, 8))
            photo.write_bytes(jpeg(1536, 1024))
            self.assertEqual(batches.image_pixels(measured), 380 * 960)
            self.assertEqual(batches.image_pixels(photo), 1536 * 1024)
            self.assertIsNone(batches.image_pixels(Path(tmp) / "missing.png"))

            def image_in(path: Path) -> int:
                item = parse(items=[{"id": "e1", "kind": "edit", "prompt": "x",
                                     "images": [{"file": str(path), "provenance": "own render"}]}]).items[0]
                return item.tokens()["image_in"]

            self.assertEqual(image_in(measured), 416 * 2)  # the measurement, times the margin
            self.assertEqual(image_in(large), math.ceil(416 * 1536 * 1024 / (380 * 960) * 2))
            self.assertEqual(image_in(photo), image_in(large))
            self.assertEqual(image_in(small), 416 * 2)  # never below the measured 416
            self.assertEqual(image_in(Path(tmp) / "missing.png"), batches.UNREAD_INPUT_TOKENS * 2)

    def test_a_from_input_without_pick_counts_every_source_image(self) -> None:
        image = {"file": "raw:a.png", "provenance": "own render"}
        batch = parse(items=[{"id": "e1", "kind": "edit", "prompt": "x", "images": [image], "n": 3,
                              "size": "1024x1024"},
                             {"id": "e2", "kind": "edit", "prompt": "y", "images": [{"from": "e1"}]},
                             {"id": "e3", "kind": "edit", "prompt": "y", "images": [{"from": "e1", "pick": 2}]}])
        e2, e3 = batch.items[1], batch.items[2]
        self.assertEqual((e2.image_count, e3.image_count), (3, 1))
        self.assertEqual(e2.input_pixels(), [1024 * 1024] * 3)
        self.assertAlmostEqual(e2.tokens()["image_in"], 3 * e3.tokens()["image_in"], delta=2)  # each rounded up
        self.assertIn("1 to 16 images", errors_of(items=[
            {"id": "e1", "kind": "edit", "prompt": "x", "images": [image], "n": 10, "size": "1024x1024"},
            {"id": "e2", "kind": "edit", "prompt": "y", "images": [{"from": "e1"}, {"from": "e1"}]}]))

    def test_usage_is_priced_per_kind(self) -> None:
        tokens = batches.usage_tokens(USAGE)
        self.assertEqual(tokens, {"text_in": 300, "image_in": 1200, "image_out": 343})
        self.assertAlmostEqual(batches.cost(tokens), (300 * 5 + 1200 * 8 + 343 * 30) / 1e6)
        # without the split, all input at the image rate (an upper bound)
        self.assertEqual(batches.usage_tokens({"input_tokens": 50, "output_tokens": 9})["image_in"], 50)

    def test_the_meshy_client_refuses_an_openai_batch(self) -> None:
        from runner.commands import _meshy_batch
        with self.assertRaisesRegex(common.Failure, "run it with tools/run.py openai-images"):
            _meshy_batch.parse(batch_data(), Path("t-batch.toml"))


class MultipartTest(unittest.TestCase):
    def test_fields_and_files_round_trip(self) -> None:
        image = png()
        body, content_type = api.encode_multipart(
            [("model", "gpt-image-2.5-sunburst"), ("prompt", 'six heads, "quoted", ünïcode\nline two')],
            [api.FilePart("image[]", "a.png", "image/png", image), api.FilePart("image[]", "b.png", "image/png", b"x")],
            boundary="BOUNDARY42")
        self.assertEqual(content_type, "multipart/form-data; boundary=BOUNDARY42")
        self.assertTrue(body.startswith(b"--BOUNDARY42\r\n"))
        self.assertTrue(body.endswith(b"--BOUNDARY42--\r\n"))
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            f"Content-Type: {content_type}\r\n\r\n".encode() + body)
        parts = list(message.iter_parts())
        self.assertEqual([p.get_param("name", header="content-disposition") for p in parts],
                         ["model", "prompt", "image[]", "image[]"])
        self.assertEqual(parts[1].get_payload(decode=True).decode("utf-8"), 'six heads, "quoted", ünïcode\nline two')
        self.assertEqual(parts[2].get_filename(), "a.png")
        self.assertEqual(parts[2].get_content_type(), "image/png")
        self.assertEqual(parts[2].get_payload(decode=True), image)

    def test_a_quote_cannot_break_out_of_a_file_name(self) -> None:
        body, _ = api.encode_multipart([], [api.FilePart("image[]", 'a"; name="x.png', "image/png", b"1")], "B")
        self.assertIn(b'filename="a%22; name=%22x.png"', body)

    def test_a_random_boundary_each_time(self) -> None:
        self.assertNotEqual(api.encode_multipart([("a", "b")], [])[1], api.encode_multipart([("a", "b")], [])[1])


class ClientTest(unittest.TestCase):
    def test_generate_sends_json_with_the_bearer_key(self) -> None:
        fake = FakeOpenAI()
        answer = fake.client().generate({"model": "m", "prompt": "p", "n": 1})
        method, url, headers, body = fake.requests[0]
        self.assertEqual((method, url), ("POST", "https://api.openai.com/v1/images/generations"))
        self.assertEqual(headers["Authorization"], f"Bearer {KEY}")
        self.assertEqual(json.loads(body), {"model": "m", "prompt": "p", "n": 1})
        self.assertEqual(answer.images, [png()])
        self.assertEqual(answer.body["data"][0]["b64_json"], f"<{len(png())} bytes>")
        self.assertEqual(answer.request_id, "req_123")

    def test_only_sure_refusals_are_retried_with_backoff(self) -> None:
        # a 429 (not insufficient_quota) and a 503 with Retry-After: OpenAI refused them, nothing was made or billed
        fake = FakeOpenAI([Response(429, {"retry-after": "7"}, b'{"error": {"message": "slow down"}}'),
                           Response(429, {}, b'{"error": {"message": "slow down"}}'),
                           Response(503, {"retry-after": "3"}, b"")])
        logs: list[str] = []
        answer = fake.client(logs).edit([("model", "m")], [])
        self.assertEqual(answer.attempts, 4)
        self.assertEqual(fake.clock.sleeps, [7.0, 4.0, 3.0])
        self.assertEqual(fake.requests[0][1], "https://api.openai.com/v1/images/edits")

    def test_a_server_error_is_unsure_and_not_resent(self) -> None:
        # a 502, 504 or 524 may come after the image was made and billed; so may a 500 or a 503 without Retry-After
        for status in (500, 502, 503, 504, 524):
            with self.subTest(status=status):
                fake = FakeOpenAI([Response(status, {}, b"<html>bad gateway</html>")])
                with self.assertRaises(api.OpenAIError) as ctx:
                    fake.client().generate({})
                self.assertTrue(ctx.exception.unsure)
                self.assertEqual(ctx.exception.status, status)
                self.assertEqual(len(fake.requests), 1)
                self.assertEqual(fake.clock.sleeps, [])

    def test_a_malformed_2xx_is_unsure_and_not_resent(self) -> None:
        answers = {"not JSON": b"<html>ok</html>", "no data": b'{"created": 1}', "no b64": b'{"data": [{}]}',
                   "bad base64": b'{"data": [{"b64_json": "not base64!"}]}'}
        for what, body in answers.items():
            with self.subTest(what=what):
                fake = FakeOpenAI([Response(200, {}, body)])
                with self.assertRaises(api.OpenAIError) as ctx:
                    fake.client().generate({})
                self.assertTrue(ctx.exception.unsure)
                self.assertEqual(len(fake.requests), 1)

    def test_the_hook_runs_before_every_http_attempt(self) -> None:
        fake = FakeOpenAI([Response(429, {}, b"{}"), Response(429, {}, b"{}")])
        seen: list[tuple[int, int]] = []

        def before(attempt: int) -> None:
            seen.append((attempt, len(fake.requests)))
            if attempt == 3:
                raise api.CapReached("cap")
        with self.assertRaises(api.CapReached):
            fake.client().generate({}, before=before)
        self.assertEqual(seen, [(1, 0), (2, 1), (3, 2)])
        self.assertEqual(len(fake.requests), 2)

    def test_no_balance_is_not_retried(self) -> None:
        fake = FakeOpenAI([Response(429, {}, b'{"error": {"message": "You exceeded your current quota", '
                                             b'"code": "insufficient_quota"}}')])
        with self.assertRaisesRegex(api.OpenAIError, "insufficient_quota") as ctx:
            fake.client().generate({})
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(ctx.exception.status, 429)

    def test_a_lost_answer_is_unsure_and_not_resent(self) -> None:
        fake = FakeOpenAI([TimeoutError("timed out")])
        with self.assertRaises(api.OpenAIError) as ctx:
            fake.client().generate({})
        self.assertTrue(ctx.exception.unsure)
        self.assertEqual(len(fake.requests), 1)

    def test_redact_scrubs_the_key_and_its_masked_form(self) -> None:
        text = f"Incorrect API key provided: {MASKED}. Also {KEY} and sk-abc_DEF-123."
        out = api.redact(text, KEY)
        for secret in (KEY, MASKED, "sk-abc_DEF-123", "****"):
            self.assertNotIn(secret, out)
        self.assertEqual(out.count(api.REDACTED), 3)
        self.assertEqual(api.redact(f"no key at hand: {MASKED}", None), f"no key at hand: {api.REDACTED}")
        self.assertEqual(api.redact("task-1234 and disk-5678 stay", None), "task-1234 and disk-5678 stay")

    def test_errors_never_carry_the_key(self) -> None:
        fake = FakeOpenAI([Response(401, {}, json.dumps({"error": {"message": f"Incorrect API key provided: {KEY}",
                                                                   "code": "invalid_api_key"}}).encode())])
        with self.assertRaises(api.OpenAIError) as ctx:
            fake.client().generate({})
        self.assertNotIn(KEY, str(ctx.exception))
        self.assertIn(api.REDACTED, str(ctx.exception))


class RunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw = self.root / "raw"
        self.ref = self.root / "ref.png"
        self.ref.write_bytes(png(8, 8))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def edit_batch(self, **over: Any) -> batches.Batch:
        image = {"file": str(self.ref), "provenance": "own render", "sha256": runs.inputs.sha256(self.ref)}
        items = [{"id": "e1", "kind": "edit", "prompt": "six talk shapes", "images": [image]},
                 {"id": "e2", "kind": "edit", "prompt": "again", "images": [{"from": "e1", "pick": 0}]}]
        return parse(items=items, **over)

    def runner(self, batch: batches.Batch, fake: FakeOpenAI, logs: list[str], **kw: Any) -> runs.Runner:
        return runs.Runner(batch, fake.client(logs), raw=self.raw, **kw)

    def test_a_run_saves_pngs_records_and_chains(self) -> None:
        fake, logs = FakeOpenAI(), []
        batch = self.edit_batch()
        self.assertEqual(self.runner(batch, fake, logs).run(), 0)
        self.assertEqual(len(fake.requests), 2)
        state = json.loads((self.raw / "t-batch" / "e1" / "generation.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["files"][0]["name"], "image-0.png")
        self.assertEqual((state["files"][0]["width"], state["files"][0]["height"]), (4, 2))
        self.assertEqual((self.raw / "t-batch" / "e1" / "image-0.png").read_bytes(), png())
        request = state["requests"][0]
        self.assertEqual(request["endpoint"], "/v1/images/edits")
        self.assertEqual(request["request"]["quality"], "medium")
        self.assertEqual(request["seconds"], 30)
        self.assertAlmostEqual(state["cost_usd"], (300 * 5 + 1200 * 8 + 343 * 30) / 1e6)
        self.assertTrue(state["ai_generated"])
        self.assertEqual(state["inputs"][0]["sha256"], runs.inputs.sha256(self.ref))
        # e2 sent e1's saved image as its reference
        self.assertIn(png(), fake.requests[1][3])
        rows = (self.raw / "t-batch" / "log.csv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(rows[0].split(","), list(runs.LOG_COLUMNS))
        self.assertEqual(len(rows), 3)
        # a second run skips both and sends nothing
        self.assertEqual(self.runner(batch, fake, logs).run(), 0)
        self.assertEqual(len(fake.requests), 2)

    def test_the_cap_is_checked_before_every_http_attempt(self) -> None:
        batch = parse()
        batch.cost_cap_usd = batch.items[0].estimate_usd * 1.5
        other = self.raw / "t-batch" / "old-item" / "generation.json"  # an item no longer in the batch file

        class Spender(FakeOpenAI):
            def request(inner, *args: Any) -> Response:  # noqa: N805
                answer = super().request(*args)
                # while the first attempt is out, spend appears in the batch folder (a removed item's record)
                runs.write_state(other, {"status": "done", "requests": [{"cost_usd": batch.cost_cap_usd}]})
                return answer

        fake, logs = Spender([Response(429, {}, b'{"error": {"message": "slow down"}}')]), []
        with self.assertRaisesRegex(api.CapReached, "before HTTP attempt 2"):
            self.runner(batch, fake, logs).run()
        self.assertEqual(len(fake.requests), 1)  # the retry was never sent
        state = runs.read_state(batch, batch.items[0], self.raw)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["requests"][0]["cost_usd"], 0.0)  # the 429 was refused, not billed
        self.assertAlmostEqual(runs.batch_spent(batch, self.raw), batch.cost_cap_usd)

    def test_a_second_run_of_one_batch_is_refused(self) -> None:
        batch = parse()
        lock = self.raw / "t-batch" / runs.LOCK
        lock.parent.mkdir(parents=True)
        lock.write_text("pid 1, since then\n", encoding="utf-8")
        fake = FakeOpenAI()
        with self.assertRaisesRegex(common.Failure, "another run of this batch"):
            self.runner(batch, fake, []).run()
        self.assertEqual(fake.requests, [])
        lock.unlink()
        self.assertEqual(self.runner(batch, fake, []).run(), 0)
        self.assertFalse(lock.exists())  # released after the run

    def test_a_server_error_counts_the_estimate_and_stops(self) -> None:
        batch = self.edit_batch()
        fake = FakeOpenAI([Response(502, {}, b"bad gateway")])
        with self.assertRaises(api.OpenAIError):
            self.runner(batch, fake, []).run()
        self.assertEqual(len(fake.requests), 1)
        state = runs.read_state(batch, batch.items[0], self.raw)
        self.assertEqual((state["status"], state["requests"][0]["outcome"]), ("failed", "unsure"))
        self.assertAlmostEqual(runs.spent(state), batch.items[0].estimate_usd, places=6)

    def test_a_malformed_200_counts_the_estimate_and_stops(self) -> None:
        batch = self.edit_batch()
        fake = FakeOpenAI([Response(200, {}, b'{"created": 1, "data": []}')])
        with self.assertRaises(api.OpenAIError):
            self.runner(batch, fake, []).run()
        state = runs.read_state(batch, batch.items[0], self.raw)
        self.assertEqual((state["status"], state["requests"][0]["outcome"]), ("failed", "unsure"))
        self.assertAlmostEqual(runs.spent(state), batch.items[0].estimate_usd, places=6)

    def test_a_missing_usage_block_saves_the_images_and_counts_the_estimate(self) -> None:
        for what, extra in {"missing": {}, "unreadable": {"usage": {"input_tokens": "lots"}}}.items():
            with self.subTest(usage=what), TemporaryDirectory() as tmp:
                raw = Path(tmp)
                batch = parse()
                body = {"created": 1, "data": [{"b64_json": base64.b64encode(png()).decode()}], **extra}
                fake = FakeOpenAI([Response(200, {}, json.dumps(body).encode())])
                self.assertEqual(runs.Runner(batch, fake.client([]), raw=raw).run(), 0)
                state = runs.read_state(batch, batch.items[0], raw)
                self.assertEqual(state["status"], "done")
                self.assertEqual((raw / "t-batch" / "g1" / "image-0.png").read_bytes(), png())
                self.assertEqual(state["requests"][0]["priced_from"], "estimate")
                self.assertAlmostEqual(state["cost_usd"], batch.items[0].estimate_usd, places=6)

    def test_an_unexpected_failure_never_leaves_the_item_running(self) -> None:
        batch = parse()
        fake = FakeOpenAI()
        with mock.patch.object(runs, "png_size", side_effect=RuntimeError("disk gone")):
            with self.assertRaises(RuntimeError):
                self.runner(batch, fake, []).run()
        state = runs.read_state(batch, batch.items[0], self.raw)
        self.assertEqual(state["status"], "failed")  # answered, so billed, but never priced: the estimate counts
        self.assertAlmostEqual(runs.spent(state), batch.items[0].estimate_usd, places=6)
        self.assertFalse((self.raw / "t-batch" / runs.LOCK).exists())

    def test_a_from_input_without_pick_sends_every_image(self) -> None:
        image = {"file": str(self.ref), "provenance": "own render", "sha256": runs.inputs.sha256(self.ref)}
        batch = parse(items=[{"id": "e1", "kind": "edit", "prompt": "x", "images": [image], "n": 2},
                             {"id": "e2", "kind": "edit", "prompt": "y", "images": [{"from": "e1"}]}])
        fake = FakeOpenAI([ok_answer(n=2), ok_answer()])
        self.assertEqual(self.runner(batch, fake, []).run(), 0)
        self.assertEqual(fake.requests[1][3].count(b'name="image[]"'), 2)
        state = runs.read_state(batch, batch.items[1], self.raw)
        self.assertEqual([r["pick"] for r in state["inputs"]], [0, 1])
        self.assertEqual(state["requests"][0]["estimated_tokens"], batch.items[1].tokens())
        rows = list(csv.DictReader(io.StringIO((self.raw / "t-batch" / "log.csv").read_text(encoding="utf-8"))))
        self.assertEqual([(r["item"], r["images"], r["files"]) for r in rows], [("e1", "1", "2"), ("e2", "2", "1")])

    def test_the_command_redacts_the_key_and_its_masked_form(self) -> None:
        batch = self.edit_batch()
        args = argparse.Namespace(action="run", batch="t-batch", items=[], retry_failed=False)
        leak = json.dumps({"error": {"message": f"Incorrect API key provided: {MASKED}; was {KEY}",
                                     "code": "invalid_api_key"}}).encode()
        fake, logs = FakeOpenAI([Response(401, {}, leak)]), []
        client = fake.client(logs)  # the real client on the fake transport, made before OpenAIClient is patched
        out = io.StringIO()
        with mock.patch.object(batches, "load", return_value=batch), \
                mock.patch.object(api, "api_key", return_value=KEY), \
                mock.patch.object(api, "OpenAIClient", side_effect=lambda key: client), \
                mock.patch.object(common, "raw_dir", return_value=self.raw), contextlib.redirect_stdout(out):
            with self.assertRaises(common.Failure) as ctx:
                openai_images.run(args)
            # an unexpected error carrying both forms leaves through the command's own redact
            with mock.patch.object(runs.Runner, "run", side_effect=RuntimeError(f"boom {KEY} {MASKED}")):
                with self.assertRaises(common.Failure) as crash:
                    openai_images.run(args)
        self.assertEqual(len(fake.requests), 1)
        for text in (str(ctx.exception), str(crash.exception), out.getvalue(), *logs):
            self.assertNotIn(KEY, text)
            self.assertNotIn(MASKED, text)
            self.assertNotIn("****", text)
        self.assertIn(api.REDACTED, str(ctx.exception))
        self.assertEqual(str(crash.exception), f"RuntimeError: boom {api.REDACTED} {api.REDACTED}")
        for path in self.raw.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes(), path.name)
                self.assertNotIn(MASKED.encode(), path.read_bytes(), path.name)

    def test_the_cap_is_checked_before_every_request(self) -> None:
        batch = self.edit_batch()
        cap = batch.items[0].estimate_usd + batch.items[1].estimate_usd
        batch.cost_cap_usd = cap  # the estimate fits ...
        expensive = {"input_tokens": 1000, "input_tokens_details": {"text_tokens": 0, "image_tokens": 1000},
                     "output_tokens": int(cap / 30 * 1e6)}  # ... but item 1 really spends the whole cap
        fake, logs = FakeOpenAI([ok_answer(usage=expensive)]), []
        with self.assertRaisesRegex(common.Failure, "would pass the cap"):
            self.runner(batch, fake, logs).run()
        self.assertEqual(len(fake.requests), 1)

    def test_a_batch_over_its_cap_sends_nothing(self) -> None:
        batch = self.edit_batch(cost_cap_usd=0.001)
        fake = FakeOpenAI()
        with self.assertRaisesRegex(common.Failure, "exceeds the cap"):
            self.runner(batch, fake, []).run()
        self.assertEqual(fake.requests, [])

    def test_a_changed_input_sends_nothing(self) -> None:
        batch = self.edit_batch()
        self.ref.write_bytes(png(9, 9))
        fake = FakeOpenAI()
        with self.assertRaisesRegex(common.Failure, "not ready"):
            self.runner(batch, fake, []).run()
        self.assertEqual(fake.requests, [])

    def test_an_unsure_request_counts_its_estimate_and_stops(self) -> None:
        batch = self.edit_batch()
        fake, logs = FakeOpenAI([ConnectionResetError("reset")]), []
        with self.assertRaises(api.OpenAIError):
            self.runner(batch, fake, logs).run()
        state = runs.read_state(batch, batch.items[0], self.raw)
        self.assertEqual(state["status"], "failed")
        self.assertAlmostEqual(runs.spent(state), batch.items[0].estimate_usd, places=6)
        # a rerun does not resend it without --retry-failed
        self.assertEqual(self.runner(batch, fake, logs, only=["e1"]).run(), 1)
        self.assertEqual(len(fake.requests), 1)

    def test_a_refusal_fails_the_item_only(self) -> None:
        batch = parse(items=[{"id": "g1", "kind": "generate", "prompt": "x"},
                             {"id": "g2", "kind": "generate", "prompt": "y"}])
        fake = FakeOpenAI([Response(400, {}, b'{"error": {"message": "blocked", "code": "moderation_blocked"}}')])
        self.assertEqual(self.runner(batch, fake, []).run(), 1)
        self.assertEqual(len(fake.requests), 2)
        self.assertEqual(runs.read_state(batch, batch.items[0], self.raw)["cost_usd"], 0.0)
        self.assertEqual(runs.read_state(batch, batch.items[1], self.raw)["status"], "done")

    def test_the_key_is_never_logged_or_recorded(self) -> None:
        batch = self.edit_batch()
        leak = json.dumps({"error": {"message": f"bad key {KEY}"}}).encode()
        fake, logs = FakeOpenAI([Response(429, {}, leak), ok_answer(), Response(401, {}, leak)]), []
        with self.assertRaises(api.OpenAIError) as ctx:
            self.runner(batch, fake, logs).run()
        self.assertNotIn(KEY, str(ctx.exception))
        self.assertTrue(logs)
        self.assertFalse([line for line in logs if KEY in line])
        files = list(self.raw.rglob("*"))
        self.assertTrue(any(f.name == "generation.json" for f in files))
        for path in files:
            if path.is_file():
                self.assertNotIn(KEY.encode(), path.read_bytes(), path.name)
        for request in fake.requests:  # the key travels in the header only
            self.assertNotIn(KEY.encode(), request[3])

    def test_a_generation_records_the_json_it_sent(self) -> None:
        batch = parse()
        fake = FakeOpenAI()
        self.assertEqual(self.runner(batch, fake, []).run(), 0)
        sent = json.loads(fake.requests[0][3])
        state = runs.read_state(batch, batch.items[0], self.raw)
        self.assertEqual(state["requests"][0]["request"], sent)
        self.assertEqual(sent["n"], 1)
        self.assertEqual(sent["quality"], "medium")

    def test_the_estimate_command(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["openai-images", "estimate", "batches/2026-10-20-openai-edits-test.toml"])
        self.assertEqual(code, 0)
        self.assertIn("approval: complete, within the cap", out.getvalue())


class OneImagePerConceptTest(unittest.TestCase):
    """#276: n > 1 is warned about in estimate and run, never refused."""

    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.raw = Path(self.tmp.name) / "raw"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def batch(self) -> batches.Batch:
        return parse(items=[{"id": "g1", "kind": "generate", "prompt": "one concept"},
                            {"id": "g3", "kind": "generate", "prompt": "three of one", "n": 3}])

    def test_only_items_with_n_over_one_are_warned(self) -> None:
        warnings = batches.n_warnings(self.batch().items)
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith("WARNING g3: n = 3"))
        self.assertIn("one image per concept", warnings[0])
        self.assertIn('docs/openai-images.md, "One image per concept"', warnings[0])
        self.assertEqual(batches.n_warnings(parse().items), [])

    def test_the_estimate_warns_and_still_succeeds(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = openai_images.estimate(self.batch())
        self.assertEqual(code, 0)
        lines = [line for line in out.getvalue().splitlines() if "WARNING" in line]
        self.assertEqual(len(lines), 1)
        self.assertIn("g3", lines[0])

    def test_a_run_warns_and_still_sends_every_item(self) -> None:
        fake, logs = FakeOpenAI([ok_answer(), ok_answer(3)]), []
        runner = runs.Runner(self.batch(), fake.client(logs), raw=self.raw)
        self.assertEqual(runner.run(), 0)
        self.assertEqual(len(fake.requests), 2)
        warned = [line for line in logs if line.startswith("WARNING")]
        self.assertEqual(len(warned), 1)
        self.assertIn("g3", warned[0])
        # a run of the n = 1 item alone warns about nothing
        logs.clear()
        runs.Runner(self.batch(), fake.client(logs), raw=self.raw, only=["g1"]).run()
        self.assertFalse([line for line in logs if line.startswith("WARNING")])
        # a rerun of the whole batch sends nothing (both done), so it warns about nothing
        logs.clear()
        runs.Runner(self.batch(), fake.client(logs), raw=self.raw).run()
        self.assertEqual(len(fake.requests), 2)
        self.assertFalse([line for line in logs if line.startswith("WARNING")])

    def test_n_from_the_defaults_or_a_variant_is_warned(self) -> None:
        batch = parse(defaults={"size": "1024x1024", "n": 3}, variants={"v": {"prompt": "from the variant", "n": 2}},
                      items=[{"id": "d3", "kind": "generate", "prompt": "from the defaults"},
                             {"id": "v2", "kind": "generate", "variant": "v"},
                             {"id": "i1", "kind": "generate", "prompt": "own", "n": 1}])
        warnings = batches.n_warnings(batch.items)
        self.assertEqual([w.split(":")[0] for w in warnings], ["WARNING d3", "WARNING v2"])


class RepositoryBatchesTest(unittest.TestCase):
    def test_every_committed_openai_batch_is_valid_and_approved(self) -> None:
        found = 0
        for path in sorted(batches.BATCHES.glob("*.toml")):
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            if data.get("service") != batches.SERVICE:
                continue
            found += 1
            with self.subTest(batch=path.name):
                batch = batches.load(path)
                self.assertEqual(batches.approval_problems(batch), [])
                self.assertNotIn("api_key", str(data).lower())
        self.assertGreaterEqual(found, 1)


if __name__ == "__main__":
    unittest.main()
