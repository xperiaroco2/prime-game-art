"""A fake Meshy API for the tests: no network, instant time, scripted task lifecycles."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from runner.commands._meshy_api import Clock, MeshyClient, Response

KEY = "msy_TEST_secret_key_0123456789"
ASSETS = "https://assets.example.test"
COSTS = {"preview": 20, "refine": 10, "rig": 5, "animate": 3}


class FakeClock(Clock):
    def __init__(self) -> None:
        self.t = 1_790_000_000.0
        self.sleeps: list[float] = []
        super().__init__(now=lambda: self.t, sleep=self._sleep)

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class FakeMeshy:
    """Routes requests like api.meshy.ai. Each task needs `polls` GETs to finish; `fail` names stages that end
    FAILED; `interrupt_on` raises KeyboardInterrupt on the n-th GET of a task (counting all task GETs)."""

    def __init__(self, balance: int = 1000, polls: int = 2) -> None:
        self.balance = balance
        self.polls = polls
        self.tasks: dict[str, dict[str, Any]] = {}
        self.requests: list[tuple[str, str, dict[str, str], Any]] = []
        self.fail: set[str] = set()
        self.cost = dict(COSTS)
        self.interrupt_on: int | None = None
        self.task_gets = 0
        self.raise_on_post: Exception | None = None
        self.queue: list[Response] = []  # canned answers served first

    # --- helpers for tests --------------------------------------------------------------------------------------

    def posts(self) -> list[tuple[str, Any]]:
        return [(url, body) for method, url, _, body in self.requests if method == "POST"]

    def client(self, clock: FakeClock | None = None, log: list[str] | None = None) -> MeshyClient:
        sink = log if log is not None else []
        return MeshyClient(KEY, transport=self, clock=clock or FakeClock(), log=sink.append)

    # --- the transport ------------------------------------------------------------------------------------------

    def request(self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> Response:
        payload = json.loads(body) if body else None
        self.requests.append((method, url, dict(headers), payload))
        if self.queue:
            return self.queue.pop(0)
        parsed = urlparse(url)
        if url.startswith(ASSETS):
            return Response(200, {}, f"bytes of {parsed.path}".encode())
        if headers.get("Authorization") != f"Bearer {KEY}":
            return Response(401, {}, b'{"message": "Invalid API key"}')
        path = parsed.path
        if path == "/openapi/v1/balance":
            return self._json({"balance": self.balance})
        if method == "POST":
            if self.raise_on_post:
                raise self.raise_on_post
            return self._create(path, payload)
        task_id = path.rsplit("/", 1)[-1]
        if task_id in self.tasks:
            self.task_gets += 1
            if self.interrupt_on is not None and self.task_gets == self.interrupt_on:
                raise KeyboardInterrupt
            return self._json(self._advance(self.tasks[task_id]))
        return Response(404, {}, b'{"message": "Not found"}')

    @staticmethod
    def _json(data: Any) -> Response:
        return Response(200, {"content-type": "application/json"}, json.dumps(data).encode())

    def _create(self, path: str, payload: dict[str, Any]) -> Response:
        if path.endswith("/text-to-3d"):
            stage = payload["mode"]
        elif path.endswith("/rigging"):
            stage = "rig"
        else:
            stage = "animate"
        cost = self.cost[stage] * (len(payload.get("action_ids", [])) or 1 if stage == "animate" else 1)
        if self.balance < cost:
            return Response(402, {}, b'{"message": "Insufficient credits"}')
        task_id = f"task-{len(self.tasks) + 1}-{stage}"
        self.tasks[task_id] = {"id": task_id, "stage": stage, "gets": 0, "cost": cost, "payload": payload}
        return Response(202, {}, json.dumps({"result": task_id}).encode())

    def _advance(self, task: dict[str, Any]) -> dict[str, Any]:
        task["gets"] += 1
        tid, stage = task["id"], task["stage"]
        out: dict[str, Any] = {"id": tid, "type": stage, "created_at": 1, "started_at": 2, "finished_at": 0,
                               "progress": min(99, 50 * task["gets"]), "status": "IN_PROGRESS", "consumed_credits": 0,
                               "task_error": {"message": ""}}
        if task["gets"] < self.polls:
            return out
        if stage in self.fail:
            out.update(status="FAILED", task_error={"message": "the fake failed it"})
            return out
        if not task.get("charged"):
            self.balance -= task["cost"]
            task["charged"] = True
        out.update(status="SUCCEEDED", progress=100, finished_at=3, consumed_credits=task["cost"])
        base = f"{ASSETS}/tasks/{tid}/output"
        if stage in ("preview", "refine"):
            out["model_urls"] = {"glb": f"{base}/model.glb?Expires=9", "fbx": f"{base}/model.fbx?Expires=9"}
            out["thumbnail_url"] = f"{base}/preview.png?Expires=9"
            if stage == "refine":
                out["texture_urls"] = [{"base_color": f"{base}/texture_0.png?Expires=9"}]
                out["texture_image_url"] = "https://input.example.test/guide.png"  # an input, never downloaded
        elif stage == "rig":
            out["result"] = {"rigged_character_glb_url": f"{base}/Character_output.glb?Expires=9",
                             "rigged_character_fbx_url": f"{base}/Character_output.fbx?Expires=9",
                             "basic_animations": {"walking_glb_url": f"{base}/Animation_Walking_withSkin.glb?E=9"}}
        else:
            out["result"] = {"animation_glb_url": f"{base}/Animation.glb?E=9",
                             "animation_fbx_url": f"{base}/Animation.fbx?E=9"}
        return out
