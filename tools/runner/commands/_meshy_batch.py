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
from . import _meshy_inputs as inputs

BATCHES = common.ROOT / "batches"
KINDS = ("text_to_3d", "rig", "animate", "text_to_image", "image_to_image", "image_to_3d", "multi_image_to_3d", "remesh")
IMAGE_KINDS = ("text_to_image", "image_to_image")  # make images; another item takes them with `from`
MODEL_KINDS = ("text_to_3d", "image_to_3d", "multi_image_to_3d", "remesh")  # make a model; rig and remesh take it
EXAMPLE_PREFIX = "example-"  # batches/example-*.toml show the schema and never run
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
# Image modes (docs.meshy.ai/en/api/text-to-image, /image-to-image, /pricing, read 2026-10-03): credits per image.
TEXT_TO_IMAGE_CREDITS = {"nano-banana": 3, "nano-banana-2": 6, "nano-banana-pro": 9, "gpt-image-2": 9,
                         "gpt-image-2-5-flare": 9, "gpt-image-2-5-sunburst": 9}
IMAGE_TO_IMAGE_CREDITS = {"nano-banana": 3, "nano-banana-2": 6, "nano-banana-pro": 9, "gpt-image-2": 12,
                          "gpt-image-2-5-flare": 12, "gpt-image-2-5-sunburst": 12}
IMAGE_CREDITS = {"text_to_image": TEXT_TO_IMAGE_CREDITS, "image_to_image": IMAGE_TO_IMAGE_CREDITS}
# generate_multi_view returns three images. The docs price "per image" and do not say whether a multi-view task
# costs once or three times, so the estimate charges three (an upper bound); generation.json records what Meshy took.
MULTI_VIEW_IMAGES = 3
GPT_ONLY_ASPECT_RATIOS = ("3:2", "2:3")
# Image-to-3D and multi-image-to-3D (docs.meshy.ai/en/api/pricing, read 2026-10-03): the mesh as for a text-to-3D
# preview (PREVIEW_CREDITS, the same ultra-geometry surcharge), plus the texture as for a refine (REFINE_CREDITS)
# unless should_texture is false. meshy-6-lite textures at 2k only; multi-image-to-3D has no meshy-t2.
LITE_MODEL = "meshy-6-lite"
MULTI_IMAGE_MODELS = ("meshy-6-lite", "meshy-6", "meshy-7.1")
MULTI_IMAGE_GEOMETRY = ("standard", "2k")  # 2k needs meshy-7.1 or latest (docs.meshy.ai, read 2026-10-03)
REMESH_CREDITS = 5
# How many input images each kind takes (after a `from` without `pick` expands to every image of its source).
INPUT_COUNTS = {"image_to_image": (1, 5), "image_to_3d": (1, 1), "multi_image_to_3d": (1, 4)}
# The keys an item of each kind may have besides id, variant and kind.
ITEM_KEYS = {"text_to_3d": {"prompt", "preview", "refine", "texture"}, "rig": {"source", "params"},
             "animate": {"source", "params"}, "text_to_image": {"prompt", "params"},
             "image_to_image": {"prompt", "params", "images"}, "image_to_3d": {"params", "images"},
             "multi_image_to_3d": {"params", "images"}, "remesh": {"source", "params"}}

APPROVAL_FIELDS = ("approved_by", "approved_at", "approval_ref")
# Keys the runner fills in itself; a batch may not set them.
RESERVED = {"preview": {"mode", "prompt"}, "refine": {"mode", "preview_task_id"}, "rig": {"input_task_id", "model_url"},
            "animate": {"rig_task_id"}, "text_to_image": {"prompt"},
            "image_to_image": {"prompt", "reference_image_urls", "input_task_id"},
            "image_to_3d": {"image_url", "input_task_id"}, "multi_image_to_3d": {"image_urls", "input_task_id"},
            "remesh": {"input_task_id", "model_url"}}
# The request parameters the docs list for each image-mode kind (read 2026-10-03, docs/meshy.md). Meshy may ignore
# what it does not know, so a misspelt key would pay for a generation without the setting; any other key is refused.
IMAGE_3D_PARAMS = {"ai_model", "geometry_resolution", "should_texture", "enable_pbr", "texture_resolution",
                   "texture_prompt", "should_remesh", "topology", "target_polycount", "pose_mode", "image_enhancement",
                   "remove_lighting", "save_pre_remeshed_model", "target_formats", "symmetry_mode", "moderation"}
KNOWN_PARAMS = {
    "text_to_image": {"ai_model", "generate_multi_view", "pose_mode", "aspect_ratio", "remove_background"},
    "image_to_image": {"ai_model", "generate_multi_view", "aspect_ratio", "remove_background"},
    "image_to_3d": IMAGE_3D_PARAMS | {"model_type"},
    "multi_image_to_3d": IMAGE_3D_PARAMS,
    "remesh": {"target_formats", "topology", "target_polycount"},
}
# Image parameters this client cannot fill in yet: they would need an input of their own.
UNSUPPORTED = {"image_to_3d": {"texture_image_url"}, "multi_image_to_3d": {"texture_image_url", "texture_image_urls"}}


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
    inputs: list[inputs.Input] = field(default_factory=list)
    images: int = 0  # images the item makes (text_to_image, image_to_image): 3 for a multi-view set, else 1
    textured: bool = False  # the item makes a textured model (what rigging needs)

    @property
    def credits(self) -> int:
        return sum(s.credits for s in self.stages)

    @property
    def depends(self) -> list[str]:
        """The earlier items this one needs done first: its source and its `from` inputs."""
        out = [self.source] if self.source else []
        for inp in self.inputs:
            if inp.from_item and inp.from_item not in out:
                out.append(inp.from_item)
        return out

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
        if not kind:
            continue
        unknown = sorted(set(raw) - {"id", "variant", "kind"} - ITEM_KEYS[kind])
        if unknown:
            errors.append(f"{where}: {kind} has no key {', '.join(unknown)} (it takes "
                          f"{', '.join(sorted(ITEM_KEYS[kind]))}; API parameters go in "
                          f"{'preview or refine' if kind == 'text_to_3d' else 'params'})")
        # A follow-up item inherits its variant from its source or its first `from` input.
        variant = text(raw, "variant", where, required=kind == "text_to_3d")
        vtable = variants.get(variant, {}) if isinstance(variants.get(variant, {}), dict) else {}
        prompt = str(raw.get("prompt") or vtable.get("prompt") or "").strip() if "prompt" in ITEM_KEYS[kind] else ""
        source = str(raw.get("source") or "").strip()
        kdefaults = defaults.get(kind, {}) if isinstance(defaults.get(kind, {}), dict) else {}
        item = Item(item_id, variant, kind, prompt, source)
        try:
            if kind == "text_to_3d":
                _text_to_3d(item, raw, kdefaults, vtable, where, errors)
            elif kind in ("rig", "animate"):
                _follow_up(item, raw, kdefaults, seen, where, errors)
            elif kind in IMAGE_KINDS:
                _image(item, raw, kdefaults, seen, where, errors)
            elif kind in ("image_to_3d", "multi_image_to_3d"):
                _image_to_model(item, raw, kdefaults, seen, where, errors)
            else:
                _remesh(item, raw, kdefaults, seen, where, errors)
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
    item.textured = texture


def _follow_up(item: Item, raw: dict[str, Any], kdefaults: dict[str, Any], seen: dict[str, Item], where: str,
               errors: list[str]) -> None:
    params = _params(item, raw, kdefaults, where, errors)
    wanted = MODEL_KINDS if item.kind == "rig" else ("rig",)
    src = _source(item, seen, wanted, where, errors)
    if src is not None and item.kind == "rig" and src.kind == "remesh":
        errors.append(f"{where}: Meshy rigs textured models only, and the docs do not say a remesh keeps the "
                      f"texture; rig the remesh's source {src.source!r} instead")
    elif src is not None and item.kind == "rig" and not src.textured:
        errors.append(f"{where}: Meshy rigs textured models only; source {item.source!r} makes no texture "
                      "(texture = false or should_texture = false)")
    if item.kind == "rig":
        credits = RIG_CREDITS
    else:
        chosen = [name for name in ("action_id", "action_ids", "motion_task_id") if name in params]
        if len(chosen) > 1:  # the animation docs: exactly one of them
            errors.append(f"{where}: set only one of {', '.join(chosen)}")
        ids = params.get("action_ids", [params["action_id"]] if "action_id" in params else [])
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            errors.append(f"{where}: an animate item needs params.action_ids, a list of 1 to 10 integers")
            ids = []
        elif len(ids) > 10:
            errors.append(f"{where}: Meshy takes at most 10 action_ids per animation task")
        credits = ANIMATION_CREDITS_PER_ACTION * max(1, len(ids))
    item.stages.append(Stage(item.kind, item.kind, params, credits))


def _params(item: Item, raw: dict[str, Any], kdefaults: dict[str, Any], where: str, errors: list[str]) -> dict[str, Any]:
    """The item's API parameters: [defaults.<kind>.params], then the item's params; reserved keys refused."""
    params = {**_table(kdefaults.get("params"), "defaults params"), **_table(raw.get("params"), "params")}
    _check_reserved(params, item.kind, where, errors)
    for key in sorted(UNSUPPORTED.get(item.kind, set()) & params.keys()):
        errors.append(f"{where}: '{key}' is not supported by this client yet (it would need an image input)")
    known = KNOWN_PARAMS.get(item.kind)
    if known is not None:
        for key in sorted(params.keys() - known - RESERVED[item.kind] - UNSUPPORTED.get(item.kind, set())):
            errors.append(f"{where}: params.{key} is not among the {item.kind} parameters in the docs (docs/meshy.md); fix "
                          "the spelling, or re-read the docs and add it to KNOWN_PARAMS")
    return params


def _source(item: Item, seen: dict[str, Item], wanted: tuple[str, ...], where: str, errors: list[str]) -> Item | None:
    """The earlier item named by 'source', of one of the wanted kinds; the item inherits its variant."""
    src = seen.get(item.source)
    if not item.source:
        errors.append(f"{where}: 'source' must name an earlier {' or '.join(wanted)} item of this batch")
        return None
    if src is None:
        errors.append(f"{where}: source {item.source!r} is not an earlier item of this batch")
        return None
    if src.kind not in wanted:
        errors.append(f"{where}: source {item.source!r} is a {src.kind} item, a {item.kind} needs a "
                      f"{' or '.join(wanted)} item")
        return None
    if not item.variant:
        item.variant = src.variant
    return src


def _inputs(item: Item, raw: dict[str, Any], seen: dict[str, Item], where: str, errors: list[str]) -> None:
    """The item's `images`: each `from` names an earlier image item and a valid `pick`; the count fits the kind."""
    item.inputs = inputs.parse(raw.get("images"), where, errors)
    low, high = INPUT_COUNTS[item.kind]
    count = 0
    for inp in item.inputs:
        if not inp.from_item:
            count += 1
            continue
        src = seen.get(inp.from_item)
        if src is None:
            errors.append(f"{where}: images from {inp.from_item!r}: not an earlier item of this batch")
            continue
        if src.kind not in IMAGE_KINDS:
            errors.append(f"{where}: images from {inp.from_item!r}: {src.kind} makes no image to take "
                          f"({' or '.join(IMAGE_KINDS)} items do)")
            continue
        if inp.pick is not None:
            if inp.pick >= src.images:
                errors.append(f"{where}: pick {inp.pick} from {inp.from_item!r}, which makes {src.images} image(s): "
                              f"pick 0 to {src.images - 1}")
            count += 1
        elif high == 1 and src.images > 1:
            errors.append(f"{where}: {inp.from_item!r} makes {src.images} images; set 'pick' (0 to "
                          f"{src.images - 1}) to choose one")
            count += 1
        else:
            count += src.images
        if not item.variant:
            item.variant = src.variant
    if not low <= count <= high:
        errors.append(f"{where}: {item.kind} takes {low} to {high} image(s) in 'images'; these give {count}")


def _image(item: Item, raw: dict[str, Any], kdefaults: dict[str, Any], seen: dict[str, Item], where: str,
           errors: list[str]) -> None:
    if not item.prompt:
        errors.append(f"{where}: no prompt (set 'prompt' on the item or on its variant)")
    params = _params(item, raw, kdefaults, where, errors)
    if item.kind == "image_to_image":
        _inputs(item, raw, seen, where, errors)
    model = params.get("ai_model")
    prices = IMAGE_CREDITS[item.kind]
    if not isinstance(model, str) or model not in prices:
        errors.append(f"{where}: params.ai_model must be one of {', '.join(prices)} (Meshy requires it; prices "
                      "in docs/meshy.md)")
    multi = params.get("generate_multi_view", False)
    if not isinstance(multi, bool):
        errors.append(f"{where}: generate_multi_view must be true or false")
        multi = False
    if multi and "aspect_ratio" in params:
        errors.append(f"{where}: Meshy refuses aspect_ratio together with generate_multi_view; remove aspect_ratio")
    if params.get("aspect_ratio") in GPT_ONLY_ASPECT_RATIOS and not str(model).startswith("gpt-"):
        errors.append(f"{where}: aspect_ratio {params['aspect_ratio']} is for the gpt-image models only")
    item.images = MULTI_VIEW_IMAGES if multi else 1
    item.stages.append(Stage(item.kind, item.kind, params, prices.get(str(model), 0) * item.images))


def _image_to_model(item: Item, raw: dict[str, Any], kdefaults: dict[str, Any], seen: dict[str, Item], where: str,
                    errors: list[str]) -> None:
    params = _params(item, raw, kdefaults, where, errors)
    _inputs(item, raw, seen, where, errors)
    if len(str(params.get("texture_prompt", ""))) > PROMPT_MAX:
        errors.append(f"{where}: texture_prompt is longer than {PROMPT_MAX} characters")
    textured = params.get("should_texture", True)
    if not isinstance(textured, bool):
        errors.append(f"{where}: should_texture must be true or false")
        textured = True
    item.textured = textured
    item.stages.append(Stage(item.kind, item.kind, params, image_model_credits(item.kind, params, where, errors)))


def _remesh(item: Item, raw: dict[str, Any], kdefaults: dict[str, Any], seen: dict[str, Item], where: str,
            errors: list[str]) -> None:
    params = _params(item, raw, kdefaults, where, errors)
    src = _source(item, seen, ("text_to_3d", "image_to_3d", "multi_image_to_3d"), where, errors)
    # The docs' Remesh task lists model_urls but no texture_urls, so a remesh does not count as textured: a rig
    # of one is refused until a live run shows that the texture survives.
    item.textured = False
    item.stages.append(Stage("remesh", "remesh", params, REMESH_CREDITS))


def image_model_credits(kind: str, params: dict[str, Any], where: str = "", errors: list[str] | None = None) -> int:
    """Credits of an image-to-3D or multi-image-to-3D task: the mesh, plus the texture unless should_texture = false."""
    errors = errors if errors is not None else []
    model = str(params.get("ai_model", "latest"))
    if kind == "multi_image_to_3d":
        resolved = LATEST_MODEL if model == "latest" else model
        if resolved not in MULTI_IMAGE_MODELS:
            errors.append(f"{where}: multi-image-to-3D takes ai_model {', '.join(MULTI_IMAGE_MODELS)} or latest, "
                          f"not {model!r}")
            return 0
        geometry = str(params.get("geometry_resolution", "standard"))
        if geometry not in MULTI_IMAGE_GEOMETRY:
            errors.append(f"{where}: multi-image-to-3D takes geometry_resolution "
                          f"{' or '.join(MULTI_IMAGE_GEOMETRY)}, not {geometry!r}")
        elif geometry == "2k" and resolved != LATEST_MODEL:
            errors.append(f"{where}: multi-image-to-3D geometry_resolution 2k requires ai_model {LATEST_MODEL} or "
                          f"latest, not {model!r}")
    mesh = preview_credits(params, where, errors)
    if params.get("should_texture", True) is False:
        return mesh
    texture = refine_credits(params, where, errors)
    resolved = SMART_TOPOLOGY_MODEL if model == "latest" and params.get("model_type") == "smart-topology" else model
    if resolved == LITE_MODEL and str(params.get("texture_resolution", "2k")) != "2k":
        errors.append(f"{where}: {LITE_MODEL} textures at 2k only (the pricing page lists no 4k or 8k for it)")
    return mesh + texture


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
    if batch.id.startswith(EXAMPLE_PREFIX):
        problems.insert(0, f"an {EXAMPLE_PREFIX}* batch only shows the schema and never runs; copy it to a new batch "
                           "file for the engineer's approval")
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
