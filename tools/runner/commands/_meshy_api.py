"""The Meshy HTTP API: the key, redaction, a swappable transport, and a small client with retries and polling.

Endpoints and behaviour are recorded in docs/meshy.md (read 2026-10-02). Nothing here spends credits by itself:
only `MeshyClient.create` submits a paid task, and only the batch runner calls it, after the approval checks.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .. import common, pins

API_BASE = "https://api.meshy.ai"
BALANCE_PATH = "/openapi/v1/balance"
# The create, retrieve path of each task kind; a task's retrieve URL is <path>/<id>.
TASK_PATHS = {
    "text_to_3d": "/openapi/v2/text-to-3d",
    "rig": "/openapi/v1/rigging",
    "animate": "/openapi/v1/animations",
}
FINAL_STATUSES = ("SUCCEEDED", "FAILED", "CANCELED")
REDACTED = "<MESHY_API_KEY redacted>"
USER_AGENT = "prime-game-art-runner"

KEY_STEPS = f"""{pins.MESHY_KEY_ENV} is not set. The engineer sets it once:
1. Sign in at https://www.meshy.ai on the paid plan (the API needs one) and open https://www.meshy.ai/developers > API Keys.
2. Create a key (optionally with a monthly credit limit) and copy it. Do not paste it into chat or any file.
3. In PowerShell: [Environment]::SetEnvironmentVariable("{pins.MESHY_KEY_ENV}", "<the key>", "User")
4. Run `tools\\run.cmd meshy balance` again (no restart needed: the runner reads the user environment)."""


class MeshyError(common.Failure):
    """A Meshy call failed; the message never contains the key."""

    def __init__(self, message: str, status: int = 0, unsure: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.unsure = unsure  # a submit whose task may exist although no id came back


def api_key() -> str:
    key = common.env(pins.MESHY_KEY_ENV)
    if not key:
        raise common.Failure(KEY_STEPS)
    return key.strip()


def redact(text: object, key: str | None) -> str:
    """str(text) with every occurrence of the key (and of its Bearer header) replaced."""
    out = str(text)
    if key:
        out = out.replace(key, REDACTED)
    return out


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None


class Transport(Protocol):
    """One HTTP exchange. Returns every status (errors included); raises only on a network failure."""

    def request(self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> Response: ...


class UrllibTransport:
    """The real transport: the standard library's urllib over HTTPS."""

    def request(self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> Response:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https only, see MeshyClient)
                return Response(resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read() or b"")


@dataclass
class Clock:
    """Time and sleep, injectable so tests run instantly."""

    now: Callable[[], float] = lambda: time.time()  # noqa: E731 (looked up per call, so tests can patch time)
    sleep: Callable[[float], None] = lambda seconds: time.sleep(seconds)  # noqa: E731


@dataclass
class MeshyClient:
    key: str
    transport: Transport = field(default_factory=UrllibTransport)
    clock: Clock = field(default_factory=Clock)
    base: str = API_BASE
    timeout: float = 60.0
    retries: int = 5
    poll_first: float = 5.0
    poll_factor: float = 1.5
    poll_max: float = 60.0
    poll_limit: float = 45 * 60.0
    log: Callable[[str], None] = common.say

    # --- plumbing -----------------------------------------------------------------------------------------------

    def _call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("https://") else self.base + path
        if not url.startswith("https://"):
            raise MeshyError(f"refusing a non-HTTPS URL: {redact(url, self.key)}")
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json", "User-Agent": USER_AGENT}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        # A submit is retried only when Meshy surely refused it (429); after a lost answer or a server error the
        # task may exist and cost credits, so a second POST could pay twice.
        safe = method != "POST"
        unsure = "; the task may have been created: check the Meshy dashboard before running the batch again"
        delay = 2.0
        for attempt in range(self.retries + 1):
            try:
                resp = self.transport.request(method, url, headers, body, self.timeout)
            except Exception as exc:  # a network failure: retry, then fail without the key or the chain
                if safe and attempt < self.retries:
                    self.log(f"  meshy: {method} {path} failed ({redact(exc, self.key)}), retry in {delay:.0f} s")
                    self.clock.sleep(delay)
                    delay = min(delay * 2, 60.0)
                    continue
                raise MeshyError(f"{method} {path}: {redact(exc, self.key)}{'' if safe else unsure}", unsure=not safe) from None
            if resp.status == 429 or (safe and resp.status >= 500):
                if attempt < self.retries:
                    wait = _retry_after(resp) or delay
                    self.log(f"  meshy: {method} {path} returned {resp.status}, retry in {wait:.0f} s")
                    self.clock.sleep(wait)
                    delay = min(delay * 2, 60.0)
                    continue
            if 200 <= resp.status < 300:
                try:
                    return resp.json()
                except ValueError:
                    raise MeshyError(f"{method} {path}: the answer is not JSON") from None
            tail = unsure if not safe and resp.status >= 500 else ""
            raise MeshyError(f"{method} {path}: HTTP {resp.status}{_explain(resp, self.key)}{tail}", resp.status, bool(tail))
        raise MeshyError(f"{method} {path}: gave up after {self.retries} retries")  # pragma: no cover

    # --- the API ------------------------------------------------------------------------------------------------

    def balance(self) -> int:
        data = self._call("GET", BALANCE_PATH)
        if not isinstance(data, dict) or not isinstance(data.get("balance"), (int, float)):
            raise MeshyError("the balance answer has no number in 'balance'")
        return int(data["balance"])

    def create(self, kind: str, payload: dict[str, Any]) -> str:
        """Submits a paid task and returns its id."""
        data = self._call("POST", TASK_PATHS[kind], payload)
        task_id = data.get("result") if isinstance(data, dict) else None
        if not isinstance(task_id, str) or not task_id:
            raise MeshyError(f"creating a {kind} task returned no task id")
        return task_id

    def task(self, kind: str, task_id: str) -> dict[str, Any]:
        data = self._call("GET", f"{TASK_PATHS[kind]}/{task_id}")
        if not isinstance(data, dict):
            raise MeshyError(f"task {task_id}: the answer is not an object")
        return data

    def wait(self, kind: str, task_id: str) -> dict[str, Any]:
        """Polls a task with growing pauses until it finishes; returns its last state."""
        start = self.clock.now()
        pause = self.poll_first
        last = -1
        while True:
            data = self.task(kind, task_id)
            status = str(data.get("status", ""))
            if status in FINAL_STATUSES:
                return data
            progress = int(data.get("progress") or 0)
            if progress != last:
                self.log(f"  meshy: {kind} {task_id} {status.lower()} {progress}%")
                last = progress
            if self.clock.now() - start > self.poll_limit:
                raise MeshyError(
                    f"task {task_id} still {status} after {self.poll_limit / 60:.0f} min; run the batch again later "
                    "to resume it"
                )
            self.clock.sleep(pause)
            pause = min(pause * self.poll_factor, self.poll_max)

    def download(self, url: str, dest: Path) -> None:
        """Fetches a result file (a signed asset URL, no key sent) into dest through a .part file."""
        if not url.startswith("https://"):
            raise MeshyError("refusing a non-HTTPS download URL")
        part = dest.with_name(dest.name + ".part")
        delay = 2.0
        for attempt in range(self.retries + 1):
            try:
                resp = self.transport.request("GET", url, {"User-Agent": USER_AGENT}, None, 300.0)
            except Exception as exc:
                resp = None
                error = redact(exc, self.key)
            else:
                error = f"HTTP {resp.status}"
                if 200 <= resp.status < 300:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    part.write_bytes(resp.body)
                    part.replace(dest)
                    return
                if 400 <= resp.status < 500 and resp.status != 429:
                    break
            if attempt < self.retries:
                self.log(f"  meshy: download of {dest.name} failed ({error}), retry in {delay:.0f} s")
                self.clock.sleep(delay)
                delay = min(delay * 2, 60.0)
        raise MeshyError(f"downloading {dest.name} failed ({error}); run the batch again to fetch fresh links")


def _retry_after(resp: Response) -> float | None:
    try:
        return max(1.0, float(resp.headers.get("retry-after", "")))
    except ValueError:
        return None


def _explain(resp: Response, key: str) -> str:
    hints = {
        401: "the key is wrong or revoked: create a new one (steps: `tools\\run.cmd meshy balance` without a key)",
        402: "not enough credits on the Meshy account",
        429: "rate or queue limit: wait and run the batch again",
    }
    text = ""
    try:
        data = resp.json()
        if isinstance(data, dict):
            text = str(data.get("message") or data.get("error") or "")
    except ValueError:
        text = resp.body[:200].decode("utf-8", "replace")
    parts = [p for p in (text.strip(), hints.get(resp.status, "")) if p]
    return redact(": " + "; ".join(parts), key) if parts else ""
