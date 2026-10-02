"""Running an approved batch: submit, poll, download, record. Idempotent and resumable.

Every item keeps its state in <raw>/<batch id>/<item id>/generation.json, written right after each submit, so an
interrupted run resumes by polling the task ids it already has instead of paying for a new task. A finished item
is skipped. One row per finished or failed item goes to <raw>/<batch id>/log.csv.
"""

from __future__ import annotations

import base64
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .. import common
from . import _meshy_inputs as inputs
from ._meshy_api import FINAL_STATUSES, MeshyClient, MeshyError
from ._meshy_batch import INPUT_COUNTS, Batch, Item, approval_problems

STATE = "generation.json"
LOG = "log.csv"
LOG_COLUMNS = ("time", "item", "variant", "kind", "status", "model", "tasks", "credits", "balance_before",
               "balance_after", "files")
TASK_FIELDS = ("id", "type", "status", "progress", "created_at", "started_at", "finished_at", "consumed_credits",
               "task_error")
# Where a task object keeps its result files (docs/meshy.md). image_url(s), reference_image_urls, texture_image_url
# and model_url are inputs (our own data URIs among them), not results.
RESULT_KEYS = ("model_urls", "texture_urls", "thumbnail_url", "thumbnail_urls", "alpha_thumbnail_url", "image_urls",
               "video_url", "result")
# A submit Meshy definitely refused for this item alone (bad input, wrong state, a failed pose estimate, a request
# too large): no task exists and nothing was charged. 401, 402 and 429 concern every item, so they stop the run.
REFUSALS = frozenset({400, 404, 409, 413, 422})
# Remesh takes these sources by task id (docs.meshy.ai/en/api/remesh); any other model goes as a GLB data URI.
REMESH_BY_TASK = ("text_to_3d", "image_to_3d")
GLB_MAGIC = b"glTF"
MODEL_MEDIA_TYPE = "application/octet-stream"  # what the remesh docs ask for in a model data URI


def batch_dir(batch: Batch, raw: Path | None = None) -> Path:
    return (raw or common.raw_dir()) / batch.id


def item_dir(batch: Batch, item: Item, raw: Path | None = None) -> Path:
    return batch_dir(batch, raw) / item.id


def read_state(batch: Batch, item: Item, raw: Path | None = None) -> dict[str, Any] | None:
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
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def spent(state: dict[str, Any] | None) -> int:
    """Credits an item has spent or committed: a task still in flight counts at least at its estimate, since Meshy
    reports consumed_credits only once it finishes and the cap check must not take it for free."""
    if not state:
        return 0
    total = 0
    for task in state.get("tasks", {}).values():
        credits = int(task.get("consumed_credits") or 0)
        if task.get("status") not in FINAL_STATUSES:
            credits = max(credits, int(task.get("estimated_credits") or 0))
        total += credits
    return total


def result_urls(task: dict[str, Any]) -> list[tuple[str, str]]:
    """(key path, URL) of every result file in a task object."""
    found: list[tuple[str, str]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, str):
            if value.startswith("https://"):
                found.append((path, value))
        elif isinstance(value, dict):
            for key, sub in value.items():
                walk(sub, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for n, sub in enumerate(value):
                walk(sub, f"{path}.{n}")

    for key in RESULT_KEYS:
        if key in task:
            walk(task[key], key)
    return found


def image_files(state: dict[str, Any]) -> list[dict[str, Any]]:
    """An image item's downloaded images in Meshy's image_urls order: entry n is image n, what `pick = n` takes."""
    found = []
    for entry in state.get("files", []):
        key = str(entry.get("key", ""))
        head, _, index = key.partition(".")
        if head == "image_urls" and index.isdigit():
            found.append((int(index), entry))
    return [entry for _, entry in sorted(found, key=lambda pair: pair[0])]


def file_names(stage: str, urls: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """(file name, URL): <stage>-<URL basename>, or <stage>-<key path><ext> when two basenames collide."""
    named: list[tuple[str, str]] = []
    bases = [Path(urlparse(url).path).name or "file" for _, url in urls]
    for (keypath, url), base in zip(urls, bases):
        if bases.count(base) > 1:
            base = re.sub(r"[^A-Za-z0-9._-]+", "_", keypath) + Path(base).suffix
        named.append((f"{stage}-{re.sub(r'[^A-Za-z0-9._-]+', '_', base)}", url))
    return named


class Runner:
    def __init__(self, batch: Batch, client: MeshyClient, raw: Path | None = None, retry_failed: bool = False,
                 only: list[str] | None = None) -> None:
        self.batch = batch
        self.client = client
        self.raw = raw or common.raw_dir()
        self.retry_failed = retry_failed
        self.only = set(only or [])
        self.log = client.log

    def now(self) -> str:
        return dt.datetime.fromtimestamp(self.client.clock.now(), dt.UTC).isoformat(timespec="seconds")

    # --- the batch ----------------------------------------------------------------------------------------------

    def run(self) -> int:
        problems = approval_problems(self.batch)
        if problems:
            raise common.Failure(f"batch {self.batch.id} may not run:\n  " + "\n  ".join(problems))
        unknown = self.only - {i.id for i in self.batch.items}
        if unknown:
            raise common.Failure(f"batch {self.batch.id} has no item {', '.join(sorted(unknown))}")
        self.preflight()
        failed = 0
        for item in self.batch.items:
            if self.only and item.id not in self.only:
                continue
            outcome = self.run_item(item)
            failed += outcome not in ("done", "skipped")
        self.log(f"meshy run {self.batch.id}: {self.total_spent()} credits spent in all, "
                 f"{'all items done' if not failed else f'{failed} item(s) not done'}")
        return 1 if failed else 0

    def total_spent(self) -> int:
        return sum(spent(read_state(self.batch, i, self.raw)) for i in self.batch.items)

    def preflight(self) -> None:
        """Every local input file of the items this run may submit exists, is a PNG or JPEG within the size limit
        and matches its pinned sha256; checked before the first paid call, so a typo cannot stop a batch midway."""
        problems = []
        for item in self.batch.items:
            if self.only and item.id not in self.only:
                continue
            status = (read_state(self.batch, item, self.raw) or {}).get("status")
            if status == "done" or (status == "failed" and not self.retry_failed):
                continue
            for inp in item.inputs:
                if not inp.from_item:
                    problems += [f"{item.id}: {problem}" for problem in inputs.file_problems(inp)]
        if problems:
            raise common.Failure(f"batch {self.batch.id}: input files are not ready, nothing was submitted:\n  "
                                 + "\n  ".join(problems))

    # --- one item -----------------------------------------------------------------------------------------------

    def run_item(self, item: Item) -> str:
        folder = item_dir(self.batch, item, self.raw)
        state_path = folder / STATE
        state = read_state(self.batch, item, self.raw)
        if state and state.get("status") == "done":
            self.log(f"{item.id}: done already, skipped")
            return "skipped"
        if state and state.get("status") == "failed":
            if not self.retry_failed:
                self.log(f"{item.id}: failed before ({state.get('error', '')}); --retry-failed submits it again")
                return "failed"
            tasks = state.get("tasks", {})
            state.setdefault("previous_tasks", []).extend(  # kept for the record; the succeeded stages are reused
                {"stage": k, **t} for k, t in tasks.items() if t.get("status") != "SUCCEEDED")
            state["tasks"] = {k: t for k, t in tasks.items() if t.get("status") == "SUCCEEDED"}
            state["status"] = "running"
            state.pop("error", None)

        sources, waiting = self.source_states(item)
        if waiting:
            self.log(f"{item.id}: waits for {', '.join(waiting)} (not done), skipped")
            return "waiting"

        state = state or self.new_state(item)
        todo = [s for s in item.stages if not state["tasks"].get(s.name, {}).get("id")]
        needed = sum(s.credits for s in todo)
        if self.total_spent() + needed > self.batch.credit_cap:
            raise common.Failure(
                f"{item.id}: {needed} more credits would pass the approved cap of {self.batch.credit_cap} "
                f"({self.total_spent()} spent already); stopped before submitting"
            )
        if state.get("balance_before") is None:
            state["balance_before"] = self.client.balance()
            write_state(state_path, state)
        if todo:
            balance = self.client.balance() if state["tasks"] else state["balance_before"]
            if balance < needed:
                raise common.Failure(f"{item.id}: needs {needed} credits, the Meshy balance is {balance}; stopped")

        results: dict[str, dict[str, Any]] = {}
        for stage in item.stages:
            record = state["tasks"].get(stage.name)
            if record and record.get("id"):
                self.log(f"{item.id}: {stage.name} task {record['id']} resumed")
            else:
                try:
                    payload, sent = self.payload(item, stage.name, stage.params, state, sources)
                except common.Failure as exc:  # an input that cannot be sent: nothing submitted, nothing paid
                    return self.finish(item, state, "failed", f"{stage.name} inputs: {exc}")
                if sent:
                    state["inputs"] = [rec for _, rec in sent]
                notes = {uri: inputs.note(n, rec) for n, (uri, rec) in enumerate(sent)}
                try:
                    task_id = self.client.create(stage.api, payload)
                except MeshyError as exc:
                    if exc.unsure:  # never resubmitted on its own: a human checks the dashboard, then --retry-failed
                        self.finish(item, state, "failed", f"{stage.name} submit unsure: {exc}")
                        raise
                    if exc.status in REFUSALS:  # this item's request is wrong; the next items may still run
                        return self.finish(item, state, "failed", f"{stage.name} refused: {exc}")
                    raise  # a bad key, no credits, the rate limit: every item would hit it, so the run stops
                record = {"id": task_id, "status": "PENDING", "submitted_at": self.now(),
                          "request": inputs.scrub(payload, notes), "estimated_credits": stage.credits}
                state["tasks"][stage.name] = record
                write_state(state_path, state)  # before polling: an interruption now resumes this task id
                self.log(f"{item.id}: {stage.name} task {task_id} submitted ({stage.credits} credits estimated)")
            data = self.client.wait(stage.api, record["id"])
            record.update({k: data[k] for k in TASK_FIELDS if k in data and k != "id"})
            record["polled_at"] = self.now()
            write_state(state_path, state)
            if data.get("status") != "SUCCEEDED":
                error = data.get("task_error")
                message = str((error.get("message") if isinstance(error, dict) else error) or data.get("status"))
                return self.finish(item, state, "failed", f"{stage.name} {data.get('status')}: {message}")
            results[stage.name] = data

        files = []
        for stage_name, data in results.items():
            urls = result_urls(data)
            for (key, _), (name, url) in zip(urls, file_names(stage_name, urls)):
                dest = folder / name
                self.client.download(url, dest)
                files.append({"name": name, "stage": stage_name, "key": key, "bytes": dest.stat().st_size,
                              "sha256": sha256(dest)})
                self.log(f"{item.id}: downloaded {name} ({files[-1]['bytes']} bytes)")
        state["files"] = files
        images = image_files(state)
        if images:
            self.log(f"{item.id}: {len(images)} image(s); pick " + ", ".join(
                f"{n} = {entry['name']}" for n, entry in enumerate(images)))
        return self.finish(item, state, "done")

    def finish(self, item: Item, state: dict[str, Any], status: str, error: str = "") -> str:
        state["status"] = status
        if error:
            state["error"] = error
        state["finished_at"] = self.now()
        try:
            state["balance_after"] = self.client.balance()
        except MeshyError as exc:
            state["balance_after"] = None
            self.log(f"{item.id}: could not read the balance after ({exc})")
        write_state(item_dir(self.batch, item, self.raw) / STATE, state)
        self.append_log(item, state)
        files = len(state.get("files", []))
        self.log(f"{item.id}: {status}" + (f", {files} files, {spent(state)} credits" if status == "done" else f": {error}"))
        return status

    def new_state(self, item: Item) -> dict[str, Any]:
        b = self.batch
        return {
            "batch": b.id,
            "batch_file": b.path.name,
            "item": item.id,
            "variant": item.variant,
            "kind": item.kind,
            "prompt": item.prompt,
            "source": item.source,
            "model_version": item.model,
            "parameters": {s.name: s.params for s in item.stages},
            "estimated_credits": item.credits,
            "plan": b.plan,
            "terms_url": b.terms_url,
            "licence": b.licence,
            "approval": {"by": b.approved_by, "at": b.approved_at, "ref": b.approval_ref, "credit_cap": b.credit_cap},
            "status": "running",
            "started_at": self.now(),
            "finished_at": None,
            "balance_before": None,
            "balance_after": None,
            "inputs": [],
            "tasks": {},
            "files": [],
        }

    def source_states(self, item: Item) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """The generation.json of every item this one depends on, and the ones not done yet."""
        states, waiting = {}, []
        for dep in item.depends:
            state = read_state(self.batch, self.batch.item(dep), self.raw)
            if not state or state.get("status") != "done":
                waiting.append(dep)
            else:
                states[dep] = state
        return states, waiting

    def model_task_id(self, source: str, sources: dict[str, dict[str, Any]]) -> str:
        """The task that made a model item's final model: the refine of a textured text-to-3D, else its last stage."""
        last = self.batch.item(source).stages[-1].name
        return str(sources[source]["tasks"][last]["id"])

    def payload(self, item: Item, stage: str, params: dict[str, Any], state: dict[str, Any],
                sources: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
        """The request body of a stage, and the inputs it sends as data URIs (uri, generation.json record)."""
        if stage == "preview":
            return {"mode": "preview", "prompt": item.prompt, **params}, []
        if stage == "refine":
            return {"mode": "refine", "preview_task_id": state["tasks"]["preview"]["id"], **params}, []
        if stage == "rig":
            return {"input_task_id": self.model_task_id(item.source, sources), **params}, []
        if stage == "animate":
            return {"rig_task_id": sources[item.source]["tasks"]["rig"]["id"], **params}, []
        if stage == "text_to_image":
            return {"prompt": item.prompt, **params}, []
        if stage == "remesh":
            src = self.batch.item(item.source)
            if src.kind in REMESH_BY_TASK:
                return {"input_task_id": self.model_task_id(item.source, sources), **params}, []
            sent = [self.model_input(item.source, sources[item.source])]
            return {"model_url": sent[0][0], **params}, sent
        sent = self.image_inputs(item, sources)
        uris = [uri for uri, _ in sent]
        if stage == "image_to_image":
            return {"prompt": item.prompt, "reference_image_urls": uris, **params}, sent
        if stage == "image_to_3d":
            return {"image_url": uris[0], **params}, sent
        if stage == "multi_image_to_3d":
            return {"image_urls": uris, **params}, sent
        raise common.Failure(f"unknown stage {stage}")  # pragma: no cover

    def image_inputs(self, item: Item, sources: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
        """Every image input as (data URI, record): local files as written, `from` inputs from the source's
        downloaded images (all of them, or image `pick`), each checked against the sha256 recorded for it."""
        sent = []
        for inp in item.inputs:
            if not inp.from_item:
                problems = inputs.file_problems(inp)
                if problems:
                    raise common.Failure("; ".join(problems))
                path = inputs.resolve(inp.file)
                kind = inputs.media_type(path)
                rec = inputs.record(path, kind, file=inp.file, provenance=inp.provenance)
                sent.append((inputs.data_uri(path, kind), rec))
                continue
            src = self.batch.item(inp.from_item)
            state = sources[inp.from_item]
            images = image_files(state)
            if inp.pick is not None and inp.pick >= len(images):
                raise common.Failure(f"pick {inp.pick} from {src.id}, which has {len(images)} image(s)")
            chosen = [(inp.pick, images[inp.pick])] if inp.pick is not None else list(enumerate(images))
            if not chosen:
                raise common.Failure(f"{src.id} has no downloaded image")
            task_id = state["tasks"][src.stages[-1].name]["id"]
            for n, entry in chosen:
                path = item_dir(self.batch, src, self.raw) / entry["name"]
                kind = self.checked(path, entry)
                rec = inputs.record(path, kind, **{"from": src.id, "pick": n, "file": entry["name"]},
                                    provenance=f"Meshy {src.kind} output: batch {self.batch.id}, item {src.id}, "
                                               f"task {task_id}, image {n}")
                sent.append((inputs.data_uri(path, kind), rec))
        low, high = INPUT_COUNTS[item.kind]
        if not low <= len(sent) <= high:
            raise common.Failure(f"{item.kind} takes {low} to {high} image(s); the inputs give {len(sent)}")
        return sent

    def model_input(self, source: str, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """The source's downloaded GLB (model_urls.glb) as a data URI, for a remesh Meshy cannot take by task id."""
        src = self.batch.item(source)
        entry = next((f for f in state.get("files", []) if f.get("key") == "model_urls.glb"), None)
        if entry is None:
            raise common.Failure(f"{source} has no downloaded model_urls.glb to remesh")
        path = item_dir(self.batch, src, self.raw) / entry["name"]
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise common.Failure(f"{path} is missing or no longer matches its generation.json")
        with path.open("rb") as f:
            if f.read(4) != GLB_MAGIC:
                raise common.Failure(f"{path.name} is not a binary glTF (GLB) file")
        task_id = state["tasks"][src.stages[-1].name]["id"]
        rec = inputs.record(path, MODEL_MEDIA_TYPE, **{"from": source, "file": entry["name"]},
                            provenance=f"Meshy {src.kind} output: batch {self.batch.id}, item {source}, task {task_id}")
        return f"data:{MODEL_MEDIA_TYPE};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}", rec

    @staticmethod
    def checked(path: Path, entry: dict[str, Any]) -> str:
        """The media type of a downloaded image that still matches its generation.json; PNG or JPEG only."""
        if not path.is_file() or sha256(path) != entry.get("sha256"):
            raise common.Failure(f"{path} is missing or no longer matches its generation.json")
        kind = inputs.sniff(path)
        if kind is None:
            raise common.Failure(f"{path.name} is not a PNG or JPEG image, which Meshy takes as input")
        if path.stat().st_size > inputs.IMAGE_MAX_BYTES:
            raise common.Failure(f"{path.name} is larger than {inputs.IMAGE_MAX_BYTES} bytes")
        return kind

    def append_log(self, item: Item, state: dict[str, Any]) -> None:
        path = batch_dir(self.batch, self.raw) / LOG
        new = not path.is_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new:
                writer.writerow(LOG_COLUMNS)
            writer.writerow([
                state["finished_at"], item.id, item.variant, item.kind, state["status"], state.get("model_version", ""),
                ";".join(f"{k}:{t.get('id', '')}" for k, t in state.get("tasks", {}).items()), spent(state),
                state.get("balance_before"), state.get("balance_after"), len(state.get("files", [])),
            ])


def item_status(batch: Batch, item: Item, raw: Path | None = None) -> str:
    """One line on an item, from its generation.json only (no network)."""
    state = read_state(batch, item, raw)
    if not state:
        return f"{item.id:10} {'not started':12} est. {item.credits} credits"
    status = str(state.get("status"))
    tasks = ", ".join(f"{k} {t.get('status', '?').lower()} {t.get('id', '')}" for k, t in state.get("tasks", {}).items())
    line = f"{item.id:10} {status:12} {spent(state)} credits; {tasks or 'no task yet'}"
    if status == "done":
        folder = item_dir(batch, item, raw)
        missing = [f["name"] for f in state.get("files", []) if not (folder / f["name"]).is_file()]
        line += f"; {len(state.get('files', []))} files" + (f", MISSING {', '.join(missing)}" if missing else "")
    if state.get("error"):
        line += f"; {state['error']}"
    return line
