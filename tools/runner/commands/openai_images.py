"""`openai-images`: OpenAI image batches (GPT Image 2.5): estimate, run (approved only, within the dollar cap) and
status (docs/openai-images.md)."""

from __future__ import annotations

import argparse

from .. import common
from . import _openai_api as api
from . import _openai_batch as batches
from . import _openai_run as runs

NAME = "openai-images"
HELP = "OpenAI image batches: estimate (no network), run (approved, within the dollar cap), status"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="action", metavar="<action>", required=True)
    p = sub.add_parser("estimate", help="the tokens and dollars a batch would spend, per item and in total (no network)")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")
    p = sub.add_parser("run", help="run an approved batch within its dollar cap; skips finished items")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")
    p.add_argument("items", nargs="*", help="only these item ids (default: every item)")
    p.add_argument("--retry-failed", action="store_true", help="send failed items again (spends again)")
    p = sub.add_parser("status", help="each item's state from the raw folder (no network)")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")


def run(args: argparse.Namespace) -> int:
    key = None
    try:
        batch = batches.load(args.batch)
        if args.action == "estimate":
            return estimate(batch)
        if args.action == "status":
            return status(batch)
        problems = batches.approval_problems(batch)
        if problems:
            raise common.Failure(f"batch {batch.id} may not run:\n  " + "\n  ".join(problems))
        key = api.api_key()
        return runs.Runner(batch, api.OpenAIClient(key), retry_failed=args.retry_failed, only=args.items).run()
    except common.Failure as exc:
        raise common.Failure(api.redact(exc, key)) from None
    except Exception as exc:  # anything unexpected still leaves without the key or its traceback
        raise common.Failure(f"{type(exc).__name__}: {api.redact(exc, key)}") from None


def estimate(batch: batches.Batch) -> int:
    common.say(f"batch {batch.id}: {len(batch.items)} items, {batch.model}, quality {batch.quality} by default")
    common.say(f"  {'item':12} {'kind':9} {'quality':7} {'size':10} {'n':>2} {'inputs':>6} {'text in':>8} "
               f"{'image in':>8} {'out':>7}  estimate")
    problems: list[str] = []
    for item in batch.items:
        t = item.tokens()
        common.say(f"  {item.id:12} {item.kind:9} {item.quality:7} {item.size:10} {item.n:>2} {item.image_count:>6} "
                   f"{t['text_in']:>8} {t['image_in']:>8} {t['image_out']:>7}  ${item.estimate_usd:.4f}")
        for n, inp in enumerate(item.inputs):
            if inp.from_item:
                common.say(f"      input {n}: {inp.describe()}")
                continue
            trouble = batches.file_problems(inp)
            problems += [f"{item.id}: {p}" for p in trouble]
            if trouble:
                common.say(f"      input {n}: {inp.file}: NOT READY")
            else:
                path = batches.inputs.resolve(inp.file)
                pin = "pinned" if inp.sha256 else "not pinned"
                common.say(f"      input {n}: {inp.file}: {path.stat().st_size} bytes, sha256 "
                           f"{batches.inputs.sha256(path)} ({pin})")
    common.say(f"  total ${batch.estimate_usd:.4f} (each request at {batches.ESTIMATE_MARGIN:g} times the measured "
               f"tokens); cap ${batch.cost_cap_usd:.2f}")
    approval = batches.approval_problems(batch)
    common.say("  approval: " + ("complete, within the cap" if not approval else "; ".join(approval)))
    for problem in problems:
        common.say(f"  not ready: {problem}")
    return 0


def status(batch: batches.Batch) -> int:
    common.say(f"batch {batch.id} in {runs.batch_dir(batch)}")
    for item in batch.items:
        common.say("  " + runs.item_status(batch, item))
    common.say(f"  ${runs.batch_spent(batch):.4f} spent of the cap ${batch.cost_cap_usd:.2f} (every generation.json "
               "in the folder)")
    return 0
