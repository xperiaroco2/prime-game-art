"""Running an approved OpenAI image batch: one request per item, the images saved as PNG, everything recorded.

Every item keeps its state in <raw>/<batch id>/<item id>/generation.json, written before its request (so an
interrupted run knows a request may have been billed) and after it. A done item is skipped; one row per finished or
failed item goes to <raw>/<batch id>/log.csv. The dollar cap is checked before every request: what the batch has
spent (the answers' usage at the model's rates, plus the estimate of every request whose answer was lost) plus this
request's estimate must stay within `cost_cap_usd`.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from .. import common
from . import _meshy_inputs as inputs
from . import _openai_api as api
from . import _openai_batch as batches

STATE = "generation.json"
LOG = "log.csv"
LOG_COLUMNS = ("time", "item", "variant", "kind", "status", "model", "quality", "size", "images", "input_tokens",
               "output_tokens", "cost_usd", "seconds", "request_id", "files")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
# A request OpenAI refused for this item alone (a bad field, a moderation block, a too-large file): nothing was made
# or billed, and the next items may still run. 401, 403 and a 429 that outlasts the retries stop the run.
REFUSALS = frozenset({400, 404, 409, 413, 415, 422})


def batch_dir(batch: batches.Batch, raw: Path | None = None) -> Path:
    return (raw or common.raw_dir()) / batch.id


def item_dir(batch: batches.Batch, item: batches.Item, raw: Path | None = None) -> Path:
    return batch_dir(batch, raw) / item.id


def read_state(batch: batches.Batch, item: batches.Item, raw: Path | None = None) -> dict[str, Any] | None:
    path = item_dir(batch, item, raw) / STATE
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise common.Failure(f"{path} is not valid JSON ({exc}); fix or move it before running again") from None


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(path)


def spent(state: dict[str, Any] | None) -> float:
    """$ an item has spent or may have spent: its billed requests, and the estimate of every request without an
    answer (still in flight when the run stopped, or lost), which may have been billed."""
    if not state:
        return 0.0
    total = 0.0
    for attempt in state.get("requests", []):
        if attempt.get("cost_usd") is not None:
            total += float(attempt["cost_usd"])
        elif attempt.get("outcome") in (None, "sent", "unsure"):
            total += float(attempt.get("estimated_usd") or 0.0)
    return total


def png_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(PNG_MAGIC) or data[12:16] != b"IHDR":
        raise common.Failure("an answer image is not a PNG")
    return struct.unpack(">II", data[16:24])


class Runner:
    def __init__(self, batch: batches.Batch, client: api.OpenAIClient, raw: Path | None = None,
                 retry_failed: bool = False, only: list[str] | None = None) -> None:
        self.batch = batch
        self.client = client
        self.raw = raw or common.raw_dir()
        self.retry_failed = retry_failed
        self.only = set(only or [])
        self.log = client.log

    def now(self) -> str:
        return dt.datetime.fromtimestamp(self.client.clock.now(), dt.UTC).isoformat(timespec="seconds")

    def total_spent(self) -> float:
        return sum(spent(read_state(self.batch, i, self.raw)) for i in self.batch.items)

    def run(self) -> int:
        problems = batches.approval_problems(self.batch)
        if problems:
            raise common.Failure(f"batch {self.batch.id} may not run:\n  " + "\n  ".join(problems))
        unknown = self.only - {i.id for i in self.batch.items}
        if unknown:
            raise common.Failure(f"batch {self.batch.id} has no item {', '.join(sorted(unknown))}")
        self.preflight()
        failed = 0
        todo = [i for i in self.batch.items if not self.only or i.id in self.only]
        for n, item in enumerate(todo, 1):
            self.log(f"[{n}/{len(todo)}] {item.id}")
            outcome = self.run_item(item)
            failed += outcome not in ("done", "skipped")
        self.log(f"openai-images run {self.batch.id}: ${self.total_spent():.4f} spent of the cap "
                 f"${self.batch.cost_cap_usd:.2f}; " + ("all items done" if not failed else f"{failed} item(s) not done"))
        return 1 if failed else 0

    def preflight(self) -> None:
        """Every local reference image of the items this run may send exists, fits and matches its pinned sha256;
        checked before the first paid request."""
        problems = []
        for item in self.batch.items:
            if self.only and item.id not in self.only:
                continue
            status = (read_state(self.batch, item, self.raw) or {}).get("status")
            if status == "done" or (status == "failed" and not self.retry_failed):
                continue
            for inp in item.inputs:
                if not inp.from_item:
                    problems += [f"{item.id}: {p}" for p in batches.file_problems(inp)]
        if problems:
            raise common.Failure(f"batch {self.batch.id}: input files are not ready, nothing was sent:\n  "
                                 + "\n  ".join(problems))

    # --- one item -----------------------------------------------------------------------------------------------

    def run_item(self, item: batches.Item) -> str:
        folder = item_dir(self.batch, item, self.raw)
        state = read_state(self.batch, item, self.raw)
        if state and state.get("status") == "done":
            self.log(f"{item.id}: done already, skipped")
            return "skipped"
        if state and state.get("status") == "running":  # the last run stopped during the request: it may be billed
            for attempt in state.get("requests", []):
                if attempt.get("outcome") == "sent":
                    attempt["outcome"] = "unsure"
            state["status"] = "failed"
            state["error"] = "the run stopped while the request was out: it may have been billed"
            write_state(folder / STATE, state)
        if state and state.get("status") == "failed":
            if not self.retry_failed:
                self.log(f"{item.id}: failed before ({state.get('error', '')}); --retry-failed sends it again")
                return "failed"
            state.pop("error", None)
        waiting = [d for d in item.depends
                   if (read_state(self.batch, self.batch.item(d), self.raw) or {}).get("status") != "done"]
        if waiting:
            self.log(f"{item.id}: waits for {', '.join(waiting)} (not done), skipped")
            return "waiting"

        estimate = item.estimate_usd
        already = self.total_spent()
        if already + estimate > self.batch.cost_cap_usd:
            raise common.Failure(f"{item.id}: its estimate ${estimate:.4f} would pass the cap of "
                                 f"${self.batch.cost_cap_usd:.2f} (${already:.4f} spent already); stopped before "
                                 "sending")
        state = state or self.new_state(item)
        try:
            fields, files, sent = self.request(item)
        except common.Failure as exc:  # an input that cannot be sent: nothing sent, nothing paid
            return self.finish(item, state, "failed", f"inputs: {exc}")
        state["inputs"] = sent
        attempt = {"sent_at": self.now(), "endpoint": api.EDITS_PATH if item.kind == "edit" else api.GENERATIONS_PATH,
                   "request": self.recorded(fields, sent), "estimated_usd": round(estimate, 6),
                   "estimated_tokens": item.tokens(), "outcome": "sent"}
        state.setdefault("requests", []).append(attempt)
        state["status"] = "running"
        write_state(folder / STATE, state)  # before the call: an interruption now counts the request as maybe billed
        self.log(f"{item.id}: {item.kind} {item.model} {item.quality} {item.size} x{item.n}, estimate ${estimate:.4f}"
                 f" (cap ${self.batch.cost_cap_usd:.2f}, spent ${already:.4f}); waiting for the answer")
        try:
            answer = (self.client.edit(fields, files) if item.kind == "edit"
                      else self.client.generate({**dict(fields), "n": item.n}))  # JSON takes n as a number
        except api.OpenAIError as exc:
            attempt["outcome"] = "unsure" if exc.unsure else "error"
            attempt["status"] = exc.status
            if not exc.unsure:
                attempt["cost_usd"] = 0.0
            attempt["finished_at"] = self.now()
            if exc.unsure:
                self.finish(item, state, "failed", f"request unsure: {exc}")
                raise
            if exc.status in REFUSALS:
                return self.finish(item, state, "failed", f"refused: {exc}")
            self.finish(item, state, "failed", str(exc))
            raise
        tokens = batches.usage_tokens(answer.body.get("usage"))
        cost = batches.cost(tokens, batches.MODELS[item.model])
        attempt.update({"outcome": "answered", "finished_at": self.now(), "seconds": round(answer.seconds, 1),
                        "attempts": answer.attempts, "request_id": answer.request_id, "usage": answer.body.get("usage"),
                        "billed_tokens": tokens, "cost_usd": round(cost, 6),
                        "answer": {k: v for k, v in answer.body.items() if k != "usage"}})
        saved = []
        for n, data in enumerate(answer.images):
            try:
                width, height = png_size(data)
            except common.Failure as exc:
                return self.finish(item, state, "failed", f"image {n}: {exc} (paid ${cost:.4f})")
            dest = folder / f"image-{n}.png"
            part = dest.with_name(dest.name + ".part")
            part.write_bytes(data)
            part.replace(dest)
            saved.append({"name": dest.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                          "width": width, "height": height})
            self.log(f"{item.id}: saved {dest} ({width}x{height}, {len(data)} bytes)")
        state["files"] = saved
        state["cost_usd"] = round(spent(state), 6)
        return self.finish(item, state, "done")

    def request(self, item: batches.Item) -> tuple[list[tuple[str, str]], list[api.FilePart], list[dict[str, Any]]]:
        """The request's fields (also the JSON body of a generation), an edit's image parts, and each image's
        generation.json record."""
        fields: list[tuple[str, str]] = [("model", item.model), ("prompt", item.prompt), ("size", item.size),
                                         ("quality", item.quality), ("n", str(item.n)), ("output_format", "png")]
        if item.background:
            fields.append(("background", item.background))
        if item.moderation:
            fields.append(("moderation", item.moderation))
        files, sent = [], []
        for n, inp in enumerate(item.inputs):
            if inp.from_item:
                src = self.batch.item(inp.from_item)
                state = read_state(self.batch, src, self.raw) or {}
                images = state.get("files", [])
                picks = [inp.pick] if inp.pick is not None else list(range(len(images)))
                for pick in picks:
                    if pick >= len(images):
                        raise common.Failure(f"pick {pick} from {src.id}, which saved {len(images)} image(s)")
                    entry = images[pick]
                    path = item_dir(self.batch, src, self.raw) / entry["name"]
                    if not path.is_file() or inputs.sha256(path) != entry["sha256"]:
                        raise common.Failure(f"{path} is missing or no longer matches its generation.json")
                    rec = inputs.record(path, "image/png", **{"from": src.id, "pick": pick, "file": entry["name"]},
                                        provenance=f"OpenAI {src.kind} output: batch {self.batch.id}, item {src.id}, "
                                                   f"image {pick}")
                    files.append(api.FilePart("image[]", path.name, "image/png", path.read_bytes()))
                    sent.append(rec)
                continue
            problems = batches.file_problems(inp)
            if problems:
                raise common.Failure("; ".join(problems))
            path = inputs.resolve(inp.file)
            kind = inputs.sniff(path) or "image/png"
            files.append(api.FilePart("image[]", path.name, kind, path.read_bytes()))
            sent.append(inputs.record(path, kind, file=inp.file, provenance=inp.provenance))
        if len(files) > batches.MAX_IMAGES:
            raise common.Failure(f"an edit takes at most {batches.MAX_IMAGES} images; the inputs give {len(files)}")
        return fields, files, sent

    @staticmethod
    def recorded(fields: list[tuple[str, Any]], sent: list[dict[str, Any]]) -> dict[str, Any]:
        """The request as generation.json keeps it: its fields (the key travels only in the header) and a note per
        image part."""
        body: dict[str, Any] = {k: v for k, v in fields}
        if sent:
            body["image[]"] = [f"<input {n}: {r['media_type']}, {r['bytes']} bytes, sha256 {r['sha256']}>"
                               for n, r in enumerate(sent)]
        return body

    def finish(self, item: batches.Item, state: dict[str, Any], status: str, error: str = "") -> str:
        state["status"] = status
        if error:
            state["error"] = error
        state["finished_at"] = self.now()
        state["cost_usd"] = round(spent(state), 6)
        write_state(item_dir(self.batch, item, self.raw) / STATE, state)
        self.append_log(item, state)
        last = (state.get("requests") or [{}])[-1]
        if status == "done":
            usage = last.get("billed_tokens", {})
            self.log(f"{item.id}: done in {last.get('seconds')} s, {len(state.get('files', []))} image(s), "
                     f"{usage.get('text_in', 0)} text + {usage.get('image_in', 0)} image input and "
                     f"{usage.get('image_out', 0)} output tokens, ${last.get('cost_usd', 0):.4f}; batch spent "
                     f"${self.total_spent():.4f} of ${self.batch.cost_cap_usd:.2f}")
        else:
            self.log(f"{item.id}: {status}: {error}")
        return status

    def new_state(self, item: batches.Item) -> dict[str, Any]:
        b = self.batch
        return {
            "batch": b.id, "batch_file": b.path.name, "service": batches.SERVICE, "item": item.id,
            "variant": item.variant, "kind": item.kind, "prompt": item.prompt, "model": item.model,
            "quality": item.quality, "size": item.size, "n": item.n, "estimated_usd": round(item.estimate_usd, 6),
            "prices_per_million": batches.MODELS[item.model], "plan": b.plan, "terms_url": b.terms_url,
            "licence": b.licence, "ai_generated": True,
            "approval": {"by": b.approved_by, "at": b.approved_at, "ref": b.approval_ref,
                         "cost_cap_usd": b.cost_cap_usd},
            "status": "running", "started_at": self.now(), "finished_at": None, "cost_usd": 0.0,
            "inputs": [], "requests": [], "files": [],
        }

    def append_log(self, item: batches.Item, state: dict[str, Any]) -> None:
        path = batch_dir(self.batch, self.raw) / LOG
        new = not path.is_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        last = (state.get("requests") or [{}])[-1]
        usage = last.get("usage") or {}
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            if new:
                writer.writerow(LOG_COLUMNS)
            writer.writerow([state["finished_at"], item.id, item.variant, item.kind, state["status"], item.model,
                             item.quality, item.size, len(item.inputs), usage.get("input_tokens", ""),
                             usage.get("output_tokens", ""), f"{state.get('cost_usd', 0):.6f}",
                             last.get("seconds", ""), last.get("request_id", ""), len(state.get("files", []))])


def item_status(batch: batches.Batch, item: batches.Item, raw: Path | None = None) -> str:
    """One line on an item, from its generation.json only (no network)."""
    state = read_state(batch, item, raw)
    if not state:
        return f"{item.id:10} {'not started':12} est. ${item.estimate_usd:.4f}"
    status = str(state.get("status"))
    line = f"{item.id:10} {status:12} ${spent(state):.4f}"
    if status == "done":
        folder = item_dir(batch, item, raw)
        missing = [f["name"] for f in state.get("files", []) if not (folder / f["name"]).is_file()]
        line += f"; {len(state.get('files', []))} image(s)" + (f", MISSING {', '.join(missing)}" if missing else "")
    if state.get("error"):
        line += f"; {state['error']}"
    return line
