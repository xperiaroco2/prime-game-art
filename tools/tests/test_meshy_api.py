"""The Meshy client: the key header, retries, polling backoff and key redaction (fake transport, no network)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from runner.commands import _meshy_api as api

from tests._meshy_fake import KEY, FakeClock, FakeMeshy


class ClientTest(unittest.TestCase):
    def test_balance_sends_the_key_as_bearer(self) -> None:
        fake = FakeMeshy(balance=777)
        self.assertEqual(fake.client().balance(), 777)
        method, url, headers, _ = fake.requests[0]
        self.assertEqual((method, url), ("GET", "https://api.meshy.ai/openapi/v1/balance"))
        self.assertEqual(headers["Authorization"], f"Bearer {KEY}")

    def test_submit_returns_the_task_id(self) -> None:
        fake = FakeMeshy()
        task_id = fake.client().create("text_to_3d", {"mode": "preview", "prompt": "a cube"})
        self.assertEqual(fake.requests[0][1], "https://api.meshy.ai/openapi/v2/text-to-3d")
        self.assertEqual(fake.requests[0][3], {"mode": "preview", "prompt": "a cube"})
        self.assertIn(task_id, fake.tasks)

    def test_poll_backs_off_until_the_task_finishes(self) -> None:
        fake = FakeMeshy(polls=6)
        clock = FakeClock()
        client = fake.client(clock)
        task_id = client.create("text_to_3d", {"mode": "preview", "prompt": "a cube"})
        data = client.wait("text_to_3d", task_id)
        self.assertEqual(data["status"], "SUCCEEDED")
        self.assertEqual(clock.sleeps, [5.0, 7.5, 11.25, 16.875, 25.3125])

    def test_poll_pauses_are_capped(self) -> None:
        fake = FakeMeshy(polls=12)
        clock = FakeClock()
        client = fake.client(clock)
        client.wait("text_to_3d", client.create("text_to_3d", {"mode": "preview", "prompt": "x"}))
        self.assertEqual(max(clock.sleeps), 60.0)

    def test_poll_gives_up_after_the_limit(self) -> None:
        fake = FakeMeshy(polls=10_000)
        client = fake.client()
        client.poll_limit = 300
        task_id = client.create("text_to_3d", {"mode": "preview", "prompt": "x"})
        with self.assertRaisesRegex(api.MeshyError, "resume"):
            client.wait("text_to_3d", task_id)

    def test_rate_limit_waits_for_retry_after(self) -> None:
        fake = FakeMeshy(balance=5)
        fake.queue = [api.Response(429, {"retry-after": "7"}, b'{"message": "Rate limit exceeded"}')]
        clock = FakeClock()
        self.assertEqual(fake.client(clock).balance(), 5)
        self.assertEqual(clock.sleeps, [7.0])

    def test_server_errors_retry_then_fail(self) -> None:
        fake = FakeMeshy()
        fake.queue = [api.Response(503, {}, b"down")] * 6
        with self.assertRaisesRegex(api.MeshyError, "HTTP 503"):
            fake.client().balance()
        self.assertEqual(len(fake.requests), 6)

    def test_submit_is_never_sent_twice_after_an_unsure_failure(self) -> None:
        for answer in (api.Response(502, {}, b"bad gateway"), TimeoutError("read timed out")):
            with self.subTest(answer=answer):
                fake = FakeMeshy()
                client = fake.client()
                if isinstance(answer, Exception):
                    fake.raise_on_post = answer
                else:
                    fake.queue = [answer]
                with self.assertRaisesRegex(api.MeshyError, "may have been created"):
                    client.create("text_to_3d", {"mode": "preview", "prompt": "x"})
                self.assertEqual(len(fake.posts()), 1)

    def test_submit_retries_a_rate_limit(self) -> None:
        fake = FakeMeshy()
        fake.queue = [api.Response(429, {}, b'{"message": "NoMoreConcurrentTasks"}')]
        task_id = fake.client().create("text_to_3d", {"mode": "preview", "prompt": "x"})
        self.assertEqual(len(fake.posts()), 2)
        self.assertIn(task_id, fake.tasks)

    def test_insufficient_credits_is_explained(self) -> None:
        fake = FakeMeshy(balance=3)
        with self.assertRaisesRegex(api.MeshyError, "not enough credits"):
            fake.client().create("text_to_3d", {"mode": "preview", "prompt": "x"})

    def test_download_writes_through_a_part_file(self) -> None:
        fake = FakeMeshy()
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "a" / "model.glb"
            fake.client().download("https://assets.example.test/x/model.glb?Expires=1", dest)
            self.assertEqual(dest.read_bytes(), b"bytes of /x/model.glb")
            self.assertFalse(dest.with_name("model.glb.part").exists())
            # result files are signed links: the key never goes to them
            self.assertNotIn("Authorization", fake.requests[-1][2])

    def test_refuses_plain_http(self) -> None:
        client = FakeMeshy().client()
        with self.assertRaises(api.MeshyError):
            client.download("http://assets.example.test/model.glb", Path("unused"))


class KeyTest(unittest.TestCase):
    def test_missing_key_gives_the_steps(self) -> None:
        with mock.patch.object(api.common, "env", return_value=None):
            with self.assertRaises(api.common.Failure) as caught:
                api.api_key()
        self.assertIn("SetEnvironmentVariable", str(caught.exception))
        self.assertIn("meshy.ai/developers", str(caught.exception))

    def test_redact(self) -> None:
        self.assertEqual(api.redact(f"Bearer {KEY} failed", KEY), f"Bearer {api.REDACTED} failed")
        self.assertEqual(api.redact("nothing here", KEY), "nothing here")
        self.assertEqual(api.redact("no key known", None), "no key known")

    def test_network_error_with_the_key_is_redacted(self) -> None:
        fake = FakeMeshy()
        fake.queue = []
        log: list[str] = []
        client = fake.client(log=log)
        client.transport = mock.Mock(request=mock.Mock(side_effect=OSError(f"proxy said Authorization: Bearer {KEY}")))
        with self.assertRaises(api.MeshyError) as caught:
            client.balance()
        self.assertNotIn(KEY, str(caught.exception))
        self.assertIn(api.REDACTED, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(log)
        self.assertFalse([line for line in log if KEY in line])

    def test_error_body_echoing_the_key_is_redacted(self) -> None:
        fake = FakeMeshy()
        fake.queue = [api.Response(400, {}, f'{{"message": "bad header Bearer {KEY}"}}'.encode())]
        with self.assertRaises(api.MeshyError) as caught:
            fake.client().balance()
        self.assertNotIn(KEY, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
