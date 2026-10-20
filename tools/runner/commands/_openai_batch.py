"""OpenAI image batch files (batches/<id>.toml with `service = "openai-images"`): loading, validation, the approval
check and the dollar estimate. The schema mirrors the Meshy batches' (docs/openai-images.md)."""

from __future__ import annotations

import datetime as dt
import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import common
from . import _meshy_inputs as inputs

BATCHES = common.ROOT / "batches"
SERVICE = "openai-images"  # a batch for this client says so; `meshy` never takes one, nor this client a Meshy batch
EXAMPLE_PREFIX = "example-"
SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
KINDS = ("generate", "edit")  # POST /v1/images/generations (text) and /v1/images/edits (reference images)
# The engineer, 2026-10-20 (art #196, prime-game #1095): medium for exploration and variants, high for focused finals.
# No default: every batch says which it pays for.
QUALITIES = ("medium", "high")
# $ per 1M tokens (developers.openai.com/api/docs/models/gpt-image-2.5-sunburst, read 2026-10-20; Flare has the same
# token rates). Text output is not billed; this client prices every output token at the image rate, an upper bound.
PRICES = {"text_in": 5.0, "image_in": 8.0, "image_out": 30.0}
MODELS = {"gpt-image-2.5-sunburst": PRICES, "gpt-image-2.5-flare": PRICES}
# Output image tokens per image, measured (the docs give only a calculator): 1536x1024, gpt-image-2.5-sunburst,
# medium 343 and high 1372 (prime-game #1095, comment 6291051168, 2026-10-20). Other sizes scale with the pixel count.
MEASURED_OUTPUT = {"medium": 343, "high": 1372}
MEASURED_PIXELS = 1536 * 1024
# Image input tokens per reference image of an edit: the edit test (batch 2026-10-20-openai-edits-test, art #196)
# measured 416 for one 380x960 PNG crop; this client estimates with 1,500, since a larger reference may cost more.
INPUT_IMAGE_TOKENS = 1500
TEXT_CHARS_PER_TOKEN = 3  # an over-estimate of the prompt's tokens (English runs about 4 characters a token)
# The estimate is one measurement times this margin, so the cap check before a request stays on the safe side.
ESTIMATE_MARGIN = 2.0
# Sizes (the edits and generations reference, read 2026-10-20): WIDTHxHEIGHT, both multiples of 16, the long edge at
# most 3 times the short one and at most 3840, 655,360 to 8,294,400 pixels. `auto` is refused: the estimate needs it.
SIZE = re.compile(r"^(\d{2,4})x(\d{2,4})$")
PIXELS = (655_360, 8_294_400)
MAX_EDGE = 3840
MAX_N = 10
MAX_IMAGES = 16  # reference images of one edit
IMAGE_MAX_BYTES = 50 * 1024 * 1024 - 1  # "less than 50MB" each
PROMPT_MAX = 32_000
BACKGROUNDS = ("auto", "opaque", "transparent")
MODERATION = ("auto", "low")  # generations only: the edits reference lists no moderation field
SETTINGS = ("size", "n", "quality", "background", "moderation")
TOP_KEYS = {"id", "purpose", "service", "plan", "terms_url", "licence", "cost_cap_usd", "approved_by", "approved_at",
            "approval_ref", "model", "quality", "defaults", "variants", "items"}
ITEM_KEYS = {"id", "variant", "kind", "prompt", "images", *SETTINGS}
APPROVAL_FIELDS = ("approved_by", "approved_at", "approval_ref")


@dataclass
class Item:
    id: str
    variant: str
    kind: str
    prompt: str
    model: str
    quality: str
    size: str
    n: int = 1
    background: str = ""
    moderation: str = ""
    inputs: list[inputs.Input] = field(default_factory=list)

    @property
    def depends(self) -> list[str]:
        out: list[str] = []
        for inp in self.inputs:
            if inp.from_item and inp.from_item not in out:
                out.append(inp.from_item)
        return out

    def tokens(self) -> dict[str, int]:
        """The estimated tokens of the item's one request, the margin included."""
        width, height = (int(v) for v in self.size.split("x"))
        out = MEASURED_OUTPUT[self.quality] * width * height / MEASURED_PIXELS * self.n
        text = len(self.prompt) / TEXT_CHARS_PER_TOKEN
        image = INPUT_IMAGE_TOKENS * len(self.inputs)
        return {k: math.ceil(v * ESTIMATE_MARGIN) for k, v in (("text_in", text), ("image_in", image),
                                                               ("image_out", out))}

    @property
    def estimate_usd(self) -> float:
        return cost(self.tokens(), MODELS[self.model])


@dataclass
class Batch:
    path: Path
    id: str
    purpose: str
    plan: str
    terms_url: str
    licence: str
    cost_cap_usd: float
    approved_by: str
    approved_at: str
    approval_ref: str
    model: str
    quality: str
    items: list[Item]

    @property
    def estimate_usd(self) -> float:
        return sum(i.estimate_usd for i in self.items)

    def item(self, item_id: str) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise common.Failure(f"batch {self.id} has no item {item_id!r} (it has {', '.join(i.id for i in self.items)})")


def cost(tokens: dict[str, int], prices: dict[str, float] = PRICES) -> float:
    """$ of a request's tokens: text_in, image_in and image_out, each at its rate per 1M."""
    return sum(tokens.get(k, 0) * prices[k] for k in prices) / 1_000_000


def usage_tokens(usage: Any) -> dict[str, int]:
    """The billed tokens of an answer's `usage`: input split into text and image (all input at the image rate when the
    split is missing), every output token at the image rate."""
    if not isinstance(usage, dict):
        raise common.Failure("the answer has no usage block, so its cost is unknown")
    details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
    total_in = int(usage.get("input_tokens") or 0)
    text = int(details.get("text_tokens") or 0)
    image = int(details.get("image_tokens") or 0) if details else total_in
    if details and text + image < total_in:  # a part the split does not name is priced at the higher rate
        image += total_in - text - image
    return {"text_in": text, "image_in": image, "image_out": int(usage.get("output_tokens") or 0)}


def resolve(ref: str) -> Path:
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


def size_problem(size: Any) -> str:
    """Why a size is not one this client sends, or ''."""
    match = SIZE.match(size) if isinstance(size, str) else None
    if not match:
        return f"size {size!r} must be WIDTHxHEIGHT, for example \"1536x1024\" (auto is refused: the estimate needs it)"
    width, height = int(match[1]), int(match[2])
    if width % 16 or height % 16:
        return f"size {size}: both edges must be multiples of 16"
    if max(width, height) > 3 * min(width, height):
        return f"size {size}: the long edge may be at most 3 times the short one"
    if max(width, height) > MAX_EDGE or not PIXELS[0] <= width * height <= PIXELS[1]:
        return f"size {size}: edges at most {MAX_EDGE} and {PIXELS[0]:,} to {PIXELS[1]:,} pixels"
    return ""


def parse(data: dict[str, Any], path: Path) -> Batch:
    errors: list[str] = []

    def text(table: dict[str, Any], key: str, where: str, required: bool = True) -> str:
        value = table.get(key, "")
        if not isinstance(value, str) or (required and not value.strip()):
            errors.append(f"{where}: '{key}' must be a non-empty string")
            return ""
        return value.strip()

    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        errors.append(f"batch: no key {', '.join(unknown)} (it takes {', '.join(sorted(TOP_KEYS))})")
    if data.get("service") != SERVICE:
        errors.append(f"batch: service = \"{SERVICE}\" is required (it keeps OpenAI and Meshy batches apart)")
    batch_id = text(data, "id", "batch")
    if batch_id and not SLUG.match(batch_id):
        errors.append(f"batch: id {batch_id!r} must be lower-case letters, digits, '.', '_' or '-'")
    if batch_id and batch_id != path.stem:
        errors.append(f"batch: id {batch_id!r} differs from the file name {path.name}")
    cap = data.get("cost_cap_usd")
    if not isinstance(cap, (int, float)) or isinstance(cap, bool) or not cap > 0:
        errors.append("batch: 'cost_cap_usd' must be a positive number (the most dollars the approval covers)")
        cap = 0.0
    model = data.get("model")
    if model not in MODELS:
        errors.append(f"batch: 'model' must be one of {', '.join(MODELS)}")
        model = ""
    quality = data.get("quality")
    if quality not in QUALITIES:
        errors.append(f"batch: 'quality' is required, \"medium\" (exploration, variants) or \"high\" (a focused final)")
        quality = ""
    defaults, variants = data.get("defaults", {}), data.get("variants", {})
    if not isinstance(defaults, dict) or not isinstance(variants, dict):
        errors.append("batch: 'defaults' and 'variants' must be tables")
        defaults, variants = {}, {}
    for key in sorted(set(defaults) - set(SETTINGS) - {"quality"}):
        errors.append(f"defaults: no key {key} (it takes {', '.join(SETTINGS)})")
    if "quality" in defaults:
        errors.append("defaults: set 'quality' at the top of the batch (or on an item), not in defaults")

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
        kind = raw.get("kind")
        if kind not in KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(KINDS)}")
            continue
        for key in sorted(set(raw) - ITEM_KEYS):
            errors.append(f"{where}: no key {key} (an item takes {', '.join(sorted(ITEM_KEYS))})")
        variant = text(raw, "variant", where, required=False)
        vtable = variants.get(variant, {}) if variant else {}
        if variant and variant not in variants:
            errors.append(f"{where}: variant {variant!r} is not among [variants]")
        if not isinstance(vtable, dict):
            vtable = {}
        for key in sorted(set(vtable) - set(SETTINGS) - {"prompt"}):
            errors.append(f"variant {variant}: no key {key}")
        merged = {**defaults, **{k: v for k, v in vtable.items() if k != "prompt"},
                  **{k: v for k, v in raw.items() if k in SETTINGS}}
        prompt = str(raw.get("prompt") or vtable.get("prompt") or "").strip()
        if not prompt:
            errors.append(f"{where}: no prompt (set 'prompt' on the item or on its variant)")
        elif len(prompt) > PROMPT_MAX:
            errors.append(f"{where}: the prompt has {len(prompt)} characters, the API takes at most {PROMPT_MAX}")
        item_quality = merged.get("quality", quality)
        if item_quality not in QUALITIES:
            errors.append(f"{where}: quality {item_quality!r} is not one of {', '.join(QUALITIES)}")
            item_quality = quality or "medium"
        size = merged.get("size")
        problem = size_problem(size) if "size" in merged else "no size (set it in [defaults] or on the item)"
        if problem:
            errors.append(f"{where}: {problem}")
            size = "1024x1024"
        count = merged.get("n", 1)
        if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_N:
            errors.append(f"{where}: n must be 1 to {MAX_N}")
            count = 1
        background = merged.get("background", "")
        if background and background not in BACKGROUNDS:
            errors.append(f"{where}: background must be one of {', '.join(BACKGROUNDS)}")
        moderation = merged.get("moderation", "")
        if moderation and (moderation not in MODERATION or kind == "edit"):
            errors.append(f"{where}: moderation is {' or '.join(MODERATION)} on a generate item only")
        item = Item(item_id, variant, kind, prompt, model or "gpt-image-2.5-sunburst", item_quality, str(size), count,
                    str(background), str(moderation))
        item.inputs = inputs.parse(raw.get("images"), where, errors)
        if kind == "generate" and item.inputs:
            errors.append(f"{where}: a generate item takes no images (an edit does)")
        if kind == "edit" and not 1 <= len(item.inputs) <= MAX_IMAGES:
            errors.append(f"{where}: an edit takes 1 to {MAX_IMAGES} images in 'images'")
        for inp in item.inputs:
            if not inp.from_item:
                continue
            src = seen.get(inp.from_item)
            if src is None:
                errors.append(f"{where}: images from {inp.from_item!r}: not an earlier item of this batch")
            elif inp.pick is not None and inp.pick >= src.n:
                errors.append(f"{where}: pick {inp.pick} from {inp.from_item!r}, which makes {src.n} image(s)")
        seen[item_id] = item
        items.append(item)

    if errors:
        raise common.Failure(f"{path.name} is not a valid OpenAI image batch:\n  " + "\n  ".join(errors))
    return Batch(path=path, id=batch_id, purpose=str(data.get("purpose", "")).strip(),
                 plan=str(data.get("plan", "")).strip(), terms_url=str(data.get("terms_url", "")).strip(),
                 licence=str(data.get("licence", "")).strip(), cost_cap_usd=float(cap),
                 approved_by=str(data.get("approved_by", "")).strip(),
                 approved_at=str(data.get("approved_at", "")).strip(),
                 approval_ref=str(data.get("approval_ref", "")).strip(), model=str(model), quality=str(quality),
                 items=items)


def approval_problems(batch: Batch) -> list[str]:
    """Why the batch may not run; empty when it carries a complete approval and its estimate fits its dollar cap."""
    problems = [f"'{name}' is missing" for name in APPROVAL_FIELDS if not getattr(batch, name)]
    if batch.id.startswith(EXAMPLE_PREFIX):
        problems.insert(0, f"an {EXAMPLE_PREFIX}* batch only shows the schema and never runs")
    if batch.approved_at:
        try:
            dt.date.fromisoformat(batch.approved_at)
        except ValueError:
            problems.append(f"approved_at {batch.approved_at!r} is not a date like 2026-10-20")
    if batch.approval_ref and not batch.approval_ref.startswith("https://github.com/"):
        problems.append("approval_ref must link to the permission or the yes on GitHub (https://github.com/...)")
    for name in ("plan", "terms_url", "licence"):
        if not getattr(batch, name):
            problems.append(f"'{name}' is missing (it goes into every generation.json)")
    if batch.estimate_usd > batch.cost_cap_usd:
        problems.append(f"the estimate, ${batch.estimate_usd:.4f}, exceeds the cap of ${batch.cost_cap_usd:.2f}")
    return problems


def file_problems(inp: inputs.Input) -> list[str]:
    """Why a local reference image cannot be sent now: missing, not a PNG or JPEG, too big, or changed since the
    batch pinned its sha256."""
    path = inputs.resolve(inp.file)
    if not path.is_file():
        return [f"{inp.file}: {path} does not exist"]
    kind = inputs.sniff(path)
    if kind is None or kind != inputs.IMAGE_TYPES.get(path.suffix.lower()):
        return [f"{inp.file}: not a PNG or JPEG matching its extension"]
    if path.stat().st_size > IMAGE_MAX_BYTES:
        return [f"{inp.file}: {path.stat().st_size} bytes, the API takes images under 50 MB"]
    if inp.sha256 and inputs.sha256(path) != inp.sha256:
        return [f"{inp.file}: its sha256 is {inputs.sha256(path)}, the batch pinned {inp.sha256}"]
    return []
