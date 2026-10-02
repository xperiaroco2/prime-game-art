"""`meshy`: the Meshy API client: estimate, run, balance and status of approved batches (docs/meshy.md)."""

from __future__ import annotations

import argparse

from .. import common
from . import _meshy_api as api
from . import _meshy_batch as batches
from . import _meshy_run as runs

NAME = "meshy"
HELP = "Meshy batches: estimate, run (approved only), balance, status"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="action", metavar="<action>", required=True)
    p = sub.add_parser("estimate", help="the credits a batch would spend, per item and in total (no network)")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")
    p = sub.add_parser("run", help="run an approved batch within its credit cap; resumes and skips finished items")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")
    p.add_argument("items", nargs="*", help="only these item ids (default: every item)")
    p.add_argument("--retry-failed", action="store_true", help="submit failed items again (spends credits again)")
    sub.add_parser("balance", help="the Meshy credit balance (needs MESHY_API_KEY; spends nothing)")
    p = sub.add_parser("status", help="each item's state from the raw folder (no network)")
    p.add_argument("batch", help="batches/<id>.toml or a batch id")


def run(args: argparse.Namespace) -> int:
    key = None
    try:
        if args.action == "estimate":
            return estimate(batches.load(args.batch))
        if args.action == "status":
            return status(batches.load(args.batch))
        if args.action == "balance":
            key = api.api_key()
            common.say(f"Meshy balance: {api.MeshyClient(key).balance()} credits")
            return 0
        batch = batches.load(args.batch)
        problems = batches.approval_problems(batch)
        if problems:
            raise common.Failure(f"batch {batch.id} may not run:\n  " + "\n  ".join(problems))
        key = api.api_key()
        return runs.Runner(batch, api.MeshyClient(key), retry_failed=args.retry_failed, only=args.items).run()
    except common.Failure as exc:
        raise common.Failure(api.redact(exc, key)) from None
    except Exception as exc:  # anything unexpected still leaves without the key or its traceback
        raise common.Failure(f"{type(exc).__name__}: {api.redact(exc, key)}") from None


def estimate(batch: batches.Batch) -> int:
    common.say(f"batch {batch.id}: {len(batch.items)} items")
    common.say(f"  {'item':10} {'kind':11} {'model':13} {'stages':28} credits")
    for item in batch.items:
        stages = " + ".join(f"{s.name} {s.credits}" for s in item.stages)
        common.say(f"  {item.id:10} {item.kind:11} {item.model or '-':13} {stages:28} {item.credits}")
    common.say(f"  total {batch.credits} credits; approved cap {batch.credit_cap}")
    problems = batches.approval_problems(batch)
    common.say("  approval: " + ("complete, within the cap" if not problems else "; ".join(problems)))
    return 0


def status(batch: batches.Batch) -> int:
    folder = runs.batch_dir(batch)
    common.say(f"batch {batch.id} in {folder}")
    total = 0
    for item in batch.items:
        common.say("  " + runs.item_status(batch, item))
        total += runs.spent(runs.read_state(batch, item))
    common.say(f"  {total} credits spent of the approved cap {batch.credit_cap}")
    return 0
