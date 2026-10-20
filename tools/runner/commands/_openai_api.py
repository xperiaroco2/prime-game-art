"""The OpenAI Images API: the key, redaction, multipart encoding by hand, and a small client with retries.

Endpoints and fields as read on 2026-10-20 (docs/openai-images.md): `POST /v1/images/generations` (JSON) and
`POST /v1/images/edits` (multipart/form-data, the images as repeated `image[]` file parts). GPT image models always
answer with base64 (`data[i].b64_json`) and a `usage` block. Nothing here spends money by itself: only `generate` and
`edit` make a paid call, and only the batch runner calls them, after the approval and dollar-cap checks.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import common
from ._meshy_api import Clock, Response, Transport, UrllibTransport

API_BASE = "https://api.openai.com"
GENERATIONS_PATH = "/v1/images/generations"
EDITS_PATH = "/v1/images/edits"
KEY_ENV = "OPENAI_API_KEY"  # the Windows user environment (or the process's); never printed, logged or committed
REDACTED = "<OPENAI_API_KEY redacted>"
USER_AGENT = "prime-game-art-runner"
# Every HTTP call stays under the 170 s a workflow agent's tool call may block (CLAUDE.md, "Shell"); the docs say a
# complex prompt may take up to 2 minutes. A long batch runs in the background and prints progress per item.
CALL_TIMEOUT = 160.0

KEY_STEPS = f"""{KEY_ENV} is not set. The engineer sets it once:
1. Sign in at https://platform.openai.com, top up the prepaid balance, open API keys and create a key; copy it.
   Do not paste it into chat or any file.
2. In PowerShell: [Environment]::SetEnvironmentVariable("{KEY_ENV}", "<the key>", "User")
3. Run `tools\\run.cmd openai-images estimate <batch>` and then the run (no restart needed: the runner reads the user
   environment)."""


class OpenAIError(common.Failure):
    """An OpenAI call failed; the message never contains the key.

    `status` is the HTTP status (0: no answer); `unsure` marks a call whose request may have been served and billed
    although no answer came back (a lost connection or a timeout); `code` is OpenAI's error code, if any."""

    def __init__(self, message: str, status: int = 0, unsure: bool = False, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.unsure = unsure
        self.code = code


def api_key() -> str:
    key = common.env(KEY_ENV)
    if not key:
        raise common.Failure(KEY_STEPS)
    return key.strip()


def redact(text: object, key: str | None) -> str:
    """str(text) with every occurrence of the key replaced."""
    out = str(text)
    if key:
        out = out.replace(key, REDACTED)
    return out


# --- multipart/form-data, by hand (RFC 7578) -------------------------------------------------------------------------

@dataclass
class FilePart:
    name: str  # the form field, `image[]` for each image of an edit
    filename: str
    content_type: str
    data: bytes


def _quote(value: str) -> str:
    """A header parameter value: quotes and line breaks may not break out of it."""
    return value.replace("\\", "\\\\").replace('"', "%22").replace("\r", "%0D").replace("\n", "%0A")


def encode_multipart(fields: list[tuple[str, str]], files: list[FilePart],
                     boundary: str | None = None) -> tuple[bytes, str]:
    """The body and the Content-Type header of a multipart/form-data request: text fields first, then files."""
    boundary = boundary or f"prime-art-{secrets.token_hex(16)}"
    dash = f"--{boundary}".encode("ascii")
    for _, value in fields:
        if dash in value.encode("utf-8"):
            raise common.Failure("a form field contains the multipart boundary")  # pragma: no cover (random boundary)
    out = bytearray()
    for name, value in fields:
        out += dash + b"\r\n"
        out += f'Content-Disposition: form-data; name="{_quote(name)}"\r\n\r\n'.encode("utf-8")
        out += value.encode("utf-8") + b"\r\n"
    for part in files:
        if dash in part.data:
            raise common.Failure(f"{part.filename} contains the multipart boundary; run again (it is random)")
        out += dash + b"\r\n"
        out += (f'Content-Disposition: form-data; name="{_quote(part.name)}"; filename="{_quote(part.filename)}"\r\n'
                f"Content-Type: {part.content_type}\r\n\r\n").encode("utf-8")
        out += part.data + b"\r\n"
    out += dash + b"--\r\n"
    return bytes(out), f"multipart/form-data; boundary={boundary}"


# --- the client ----------------------------------------------------------------------------------------------------

@dataclass
class Answer:
    """A successful images call: the decoded images in data order, the answer without them, and the call's facts."""

    images: list[bytes]
    body: dict[str, Any]  # the answer with each b64_json replaced by a note
    seconds: float
    attempts: int
    request_id: str


@dataclass
class OpenAIClient:
    key: str
    transport: Transport = field(default_factory=UrllibTransport)
    clock: Clock = field(default_factory=Clock)
    base: str = API_BASE
    timeout: float = CALL_TIMEOUT
    retries: int = 4
    log: Callable[[str], None] = common.say

    def generate(self, payload: dict[str, Any]) -> Answer:
        body = json.dumps(payload).encode("utf-8")
        return self._post(GENERATIONS_PATH, body, "application/json")

    def edit(self, fields: list[tuple[str, str]], files: list[FilePart]) -> Answer:
        body, content_type = encode_multipart(fields, files)
        return self._post(EDITS_PATH, body, content_type)

    def _post(self, path: str, body: bytes, content_type: str) -> Answer:
        url = self.base + path
        if not url.startswith("https://"):
            raise OpenAIError(f"refusing a non-HTTPS URL: {redact(url, self.key)}")
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": content_type, "Accept": "application/json",
                   "User-Agent": USER_AGENT}
        delay = 2.0
        for attempt in range(1, self.retries + 2):
            start = self.clock.now()
            try:
                resp = self.transport.request("POST", url, headers, body, self.timeout)
            except Exception as exc:  # no answer: the image may have been made and billed, so never resent on its own
                raise OpenAIError(f"POST {path}: no answer ({redact(exc, self.key)}); the request may have been "
                                  "served and billed: check the usage page before running the item again",
                                  unsure=True) from None
            seconds = self.clock.now() - start
            code = _code(resp)
            retry = (resp.status == 429 and code != "insufficient_quota") or resp.status >= 500
            if retry and attempt <= self.retries:
                wait = min(60.0, _retry_after(resp) or delay)
                self.log(f"  openai: POST {path} returned {resp.status}{f' ({code})' if code else ''}, retry in "
                         f"{wait:.0f} s")
                self.clock.sleep(wait)
                delay = min(delay * 2, 30.0)
                continue
            if 200 <= resp.status < 300:
                return _answer(resp, path, seconds, attempt)
            raise OpenAIError(f"POST {path}: HTTP {resp.status}{_explain(resp, self.key)}", resp.status, code=code)
        raise OpenAIError(f"POST {path}: gave up after {self.retries} retries")  # pragma: no cover


def _answer(resp: Response, path: str, seconds: float, attempts: int) -> Answer:
    try:
        data = resp.json()
    except ValueError:
        raise OpenAIError(f"POST {path}: the answer is not JSON") from None
    if not isinstance(data, dict) or not isinstance(data.get("data"), list) or not data["data"]:
        raise OpenAIError(f"POST {path}: the answer holds no images in 'data'")
    images, kept = [], []
    for n, entry in enumerate(data["data"]):
        b64 = entry.get("b64_json") if isinstance(entry, dict) else None
        if not isinstance(b64, str):
            raise OpenAIError(f"POST {path}: image {n} has no b64_json")
        try:
            raw = base64.b64decode(b64, validate=True)
        except ValueError:
            raise OpenAIError(f"POST {path}: image {n} is not valid base64") from None
        images.append(raw)
        kept.append({**{k: v for k, v in entry.items() if k != "b64_json"}, "b64_json": f"<{len(raw)} bytes>"})
    body = {**{k: v for k, v in data.items() if k != "data"}, "data": kept}
    return Answer(images, body, seconds, attempts, resp.headers.get("x-request-id", ""))


def _retry_after(resp: Response) -> float | None:
    try:
        return max(1.0, float(resp.headers.get("retry-after", "")))
    except ValueError:
        return None


def _error(resp: Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {}
    error = data.get("error") if isinstance(data, dict) else None
    return error if isinstance(error, dict) else {}


def _code(resp: Response) -> str:
    return str(_error(resp).get("code") or "") if resp.status >= 400 else ""


def _explain(resp: Response, key: str) -> str:
    hints = {
        401: "the key is wrong or revoked: create a new one and set it again (`openai-images` without a key prints "
             "the steps)",
        403: "the key may not use this model or endpoint (organization verification, project limits)",
        429: "rate limit or no balance left: top up or wait, then run the batch again",
    }
    error = _error(resp)
    text = str(error.get("message") or "")[:300]
    if not error:
        text = resp.body[:200].decode("utf-8", "replace")
    code = str(error.get("code") or "")
    parts = [p for p in (text.strip(), f"code {code}" if code else "", hints.get(resp.status, "")) if p]
    return redact(": " + "; ".join(parts), key) if parts else ""
