"""Batch files (batches/<id>.toml): loading, validation, the approval check and the credit estimate.

The schema is documented in docs/meshy.md. A batch is plain data: prompts, parameters and the engineer's approval.
"""

from __future__ import annotations

import datetime as dt
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import common

BATCHES = common.ROOT / "batches"
KINDS = ("text_to_3d", "rig", "animate")
SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
PROMPT_MAX = 800  # characters, for prompt and texture_prompt (docs.meshy.ai, read 2026-10-02)

# Credits per call (docs.meshy.ai/en/api/pricing, read 2026-10-02). "latest" resolves to meshy-7.1 there.
PREVIEW_CREDITS = {"meshy-7.1": 20, "meshy-6": 20, "meshy-6-lite": 5, "meshy-t2": 5}
LATEST_MODEL = "meshy-7.1"
SMART_TOPOLOGY_MODEL = "meshy-t2"
ULTRA_GEOMETRY_SURCHARGE = 5  # geometry_resolution 2k or 4k (meshy-7.1 only)
REFINE_CREDITS = {"2k": 10, "4k": 10, "8k": 15}
RIG_CREDITS = 5
ANIMATION_CREDITS_PER_ACTION = 3

APPROVAL_FIELDS = ("approved_by", "approved_at", "approval_ref")
# Keys the runner fills in itself; a batch may not set them.
RESERVED = {"preview": {"mode", "prompt"}, "refine": {"mode", "preview_task_id"}, "rig": {"input_task_id", "model_url"},
            "animate": {"rig_task_id"}}


@dataclass
class Stage:
    """One paid Meshy task of an item: its name (preview, refine, rig, animate), API kind and request body.
    A body that needs an earlier task id gets it at run time (see _meshy_run)."""

    name: str
    api: str
    params: dict[str, Any]
    credits: int


@dataclass
class Item:
    id: str
    variant: str
    kind: str
    prompt: str
    source: str
    stages: list[Stage] = field(default_factory=list)

    @property
    def credits(self) -> int:
        return sum(s.credits for s in self.stages)

    @property
    def model(self) -> str:
        for stage in self.stages:
            if "ai_model" in stage.params:
                return str(stage.params["ai_model"])
        return ""


@dataclass
class Batch:
    path: Path
    id: str
    purpose: str
    plan: str
    terms_url: str
    licence: str
    credit_cap: int
    approved_by: str
    approved_at: str
    approval_ref: str
    items: list[Item]

    @property
    def credits(self) -> int:
        return sum(i.credits for i in self.items)

    def item(self, item_id: str) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise common.Failure(f"batch {self.id} has no item {item_id!r} (it has {', '.join(i.id for i in self.items)})")


def resolve(ref: str) -> Path:
    """A batch path, or a bare batch id looked up in batches/."""
    path = Path(ref)
    if path.suffix != ".toml":
        path = BATCHES / f"{ref}.toml"
    elif not path.is_absolute() and not path.exists():
        path = common.ROOT / path
    if not path.is_file():
        raise common.Failure(f"no batch file {ref} (looked for {path})")
    return path


def load(ref: str | Path) -> Batch:
    path = resolve(str(ref))
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise common.Failure(f"{path.name}: not valid TOML: {exc}") from None
    return parse(data, path)


def parse(data: dict[str, Any], path: Path) -> Batch:
    errors: list[str] = []

    def text(table: dict[str, Any], key: str, where: str, required: bool = True) -> str:
        value = table.get(key, "")
        if not isinstance(value, str) or (required and not value.strip()):
            errors.append(f"{where}: '{key}' must be a non-empty string")
            return ""
        return value.strip()

    batch_id = text(data, "id", "batch")
    if batch_id and not SLUG.match(batch_id):
        errors.append(f"batch: id {batch_id!r} must be lower-case letters, digits, '.', '_' or '-'")
    if batch_id and batch_id != path.stem:
        errors.append(f"batch: id {batch_id!r} differs from the file name {path.name}")
    cap = data.get("credit_cap")
    if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
        errors.append("batch: 'credit_cap' must be a positive integer (the most credits the approval covers)")
        cap = 0
    variants = data.get("variants", {})
    defaults = data.get("defaults", {})
    if not isinstance(variants, dict) or not isinstance(defaults, dict):
        errors.append("batch: 'variants' and 'defaults' must be tables")
        variants, defaults = {}, {}

    items: list[Item] = []
    seen: dict[str, Item] = {}
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        errors.append("batch: no [[items]]")
        raw_items = []
    for n, raw in enumerate(raw_items, 1):
        where = f"item {n}"
        if not isinstance(raw, dict):
            errors.append(f"{where}: must be a table")
            continue
        item_id = text(raw, "id", where)
        where = f"item {item_id or n}"
        if item_id and not SLUG.match(item_id):
            errors.append(f"{where}: id must be lower-case letters, digits, '.', '_' or '-'")
        if item_id in seen:
            errors.append(f"{where}: the id is used twice")
        kind = text(raw, "kind", where)
        if kind and kind not in KINDS:
            errors.append(f"{where}: kind {kind!r} is not one of {', '.join(KINDS)}")
            continue
        # A rig or animation item inherits its variant from its source.
        variant = text(raw, "variant", where, required=kind == "text_to_3d")
        vtable = variants.get(variant, {}) if isinstance(variants.get(variant, {}), dict) else {}
        prompt = str(raw.get("prompt") or vtable.get("prompt") or "").strip()
        source = str(raw.get("source") or "").strip()
        kdefaults = defaults.get(kind, {}) if isinstance(defaults.get(kind, {}), dict) else {}
        item = Item(item_id, variant, kind, prompt, source)
        try:
            if kind == "text_to_3d":
                _text_to_3d(item, raw, kdefaults, vtable, where, errors)
            elif kind in ("rig", "animate"):
                _follow_up(item, raw, kdefaults, seen, where, errors)
        except (TypeError, ValueError) as exc:
            errors.append(f"{where}: {exc}")
        seen[item_id] = item
        items.append(item)

    if errors:
        raise common.Failure(f"{path.name} is not a valid batch:\n  " + "\n  ".join(errors))
    return Batch(
        path=path,
        id=batch_id,
        purpose=str(data.get("purpose", "")).strip(),
        plan=str(data.get("plan", "")).strip(),
        terms_url=str(data.get("terms_url", "")).strip(),
        licence=str(data.get("licence", "")).strip(),
        credit_cap=cap,
        approved_by=str(data.get("approved_by", "")).strip(),
        approved_at=str(data.get("approved_at", "")).strip(),
        approval_ref=str(data.get("approval_ref", "")).strip(),
        items=items,
    )


def _table(value: Any, where: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be a table")
    return dict(value)


def _check_reserved(params: dict[str, Any], stage: str, where: str, errors: list[str]) -> None:
    for key in sorted(RESERVED[stage] & params.keys()):
        errors.append(f"{where}: '{key}' in {stage} is filled in by the runner, remove it")


def _text_to_3d(item: Item, raw: dict[str, Any], kdefaults: dict[str, Any], vtable: dict[str, Any], where: str,
                errors: list[str]) -> None:
    if not item.prompt:
        errors.append(f"{where}: no prompt (set 'prompt' on the item or on its variant)")
    elif len(item.prompt) > PROMPT_MAX:
        errors.append(f"{where}: the prompt has {len(item.prompt)} characters, Meshy takes at most {PROMPT_MAX}")
    preview = {**_table(kdefaults.get("preview"), "defaults preview"), **_table(vtable.get("preview"), "variant preview"),
               **_table(raw.get("preview"), "preview")}
    refine = {**_table(kdefaults.get("refine"), "defaults refine"), **_table(vtable.get("refine"), "variant refine"),
              **_table(raw.get("refine"), "refine")}
    _check_reserved(preview, "preview", where, errors)
    _check_reserved(refine, "refine", where, errors)
    texture = raw.get("texture", kdefaults.get("texture", True))
    if not isinstance(texture, bool):
        errors.append(f"{where}: 'texture' must be true or false")
        texture = True
    if len(str(refine.get("texture_prompt", ""))) > PROMPT_MAX:
        errors.append(f"{where}: texture_prompt is longer than {PROMPT_MAX} characters")
    item.stages.append(Stage("preview", "text_to_3d", preview, preview_credits(preview, where, errors)))
    if texture:
        item.stages.append(Stage("refine", "text_to_3d", refine, refine_credits(refine, where, errors)))


def _follow_up(item: Item, raw: dict[str, Any], kdefaults: dict[str, Any], seen: dict[str, Item], where: str,
               errors: list[str]) -> None:
    params = {**_table(kdefaults.get("params"), "defaults params"), **_table(raw.get("params"), "params")}
    _check_reserved(params, item.kind, where, errors)
    wanted = "text_to_3d" if item.kind == "rig" else "rig"
    src = seen.get(item.source)
    if not item.source:
        errors.append(f"{where}: 'source' must name an earlier {wanted} item of this batch")
    elif src is None:
        errors.append(f"{where}: source {item.source!r} is not an earlier item of this batch")
    elif src.kind != wanted:
        errors.append(f"{where}: source {item.source!r} is a {src.kind} item, a {item.kind} needs a {wanted} item")
    elif item.kind == "rig" and not any(s.name == "refine" for s in src.stages):
        errors.append(f"{where}: Meshy rigs textured models only; source {item.source!r} has texture = false")
    if not item.variant and src is not None:
        item.variant = src.variant
    if item.kind == "rig":
        credits = RIG_CREDITS
    else:
        ids = params.get("action_ids", [params["action_id"]] if "action_id" in params else [])
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            errors.append(f"{where}: an animate item needs params.action_ids, a list of 1 to 10 integers")
            ids = []
        elif len(ids) > 10:
            errors.append(f"{where}: Meshy takes at most 10 action_ids per animation task")
        credits = ANIMATION_CREDITS_PER_ACTION * max(1, len(ids))
    item.stages.append(Stage(item.kind, item.kind, params, credits))


def preview_credits(params: dict[str, Any], where: str = "", errors: list[str] | None = None) -> int:
    model = str(params.get("ai_model", "latest"))
    if params.get("model_type") == "smart-topology" and model == "latest":
        model = SMART_TOPOLOGY_MODEL
    if model == "latest":
        model = LATEST_MODEL
    if model not in PREVIEW_CREDITS:
        if errors is not None:
            errors.append(f"{where}: no known price for ai_model {model!r}: add it to PREVIEW_CREDITS from the "
                          "Meshy pricing page and docs/meshy.md")
        return 0
    extra = ULTRA_GEOMETRY_SURCHARGE if str(params.get("geometry_resolution", "standard")) in ("2k", "4k") else 0
    return PREVIEW_CREDITS[model] + extra


def refine_credits(params: dict[str, Any], where: str = "", errors: list[str] | None = None) -> int:
    resolution = str(params.get("texture_resolution", "2k"))
    if resolution not in REFINE_CREDITS:
        if errors is not None:
            errors.append(f"{where}: texture_resolution {resolution!r} is not one of {', '.join(REFINE_CREDITS)}")
        return 0
    return REFINE_CREDITS[resolution]


def approval_problems(batch: Batch) -> list[str]:
    """Why the batch may not run; empty when it carries a complete approval within its cap."""
    problems = [f"'{name}' is missing" for name in APPROVAL_FIELDS if not getattr(batch, name)]
    if batch.approved_at:
        try:
            dt.date.fromisoformat(batch.approved_at)
        except ValueError:
            problems.append(f"approved_at {batch.approved_at!r} is not a date like 2026-10-02")
    if batch.approval_ref and not batch.approval_ref.startswith("https://github.com/"):
        problems.append("approval_ref must link to the engineer's yes on GitHub (https://github.com/...)")
    for name in ("plan", "terms_url", "licence"):
        if not getattr(batch, name):
            problems.append(f"'{name}' is missing (it goes into every generation.json)")
    if batch.credits > batch.credit_cap:
        problems.append(f"the estimate, {batch.credits} credits, exceeds the approved cap of {batch.credit_cap}")
    return problems
