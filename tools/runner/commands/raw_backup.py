"""`raw-backup`: copies chosen raw generations to the backup folder (the engineer's OneDrive), checking sha256."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .. import common, pins
from . import _meshy_batch as batches
from . import _meshy_run as runs

NAME = "raw-backup"
HELP = "copy finished items of a batch from the raw folder to the OneDrive backup, sha256-checked"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("batch", help="batches/<id>.toml or a batch id")
    parser.add_argument("items", nargs="*", help="item ids to copy (default: every finished item)")


def run(args: argparse.Namespace) -> int:
    batch = batches.load(args.batch)
    backup = common.raw_backup_dir()
    if backup is None:
        raise common.Failure(
            f"no backup folder: sign in to OneDrive on this PC (it sets %OneDrive%) or set {pins.RAW_BACKUP_ENV} "
            "to a folder outside every repository"
        )
    chosen = [batch.item(i) for i in args.items] if args.items else batch.items
    dest_batch = backup / batch.id
    copied = skipped = 0
    for item in chosen:
        state = runs.read_state(batch, item)
        if not state or state.get("status") != "done":
            if args.items:
                raise common.Failure(f"{item.id} is not finished ({(state or {}).get('status', 'not started')}); "
                                     "only finished items are backed up")
            continue
        src = runs.item_dir(batch, item)
        dest = dest_batch / item.id
        for entry in state.get("files", []):
            name = entry["name"]
            if not (src / name).is_file():
                raise common.Failure(f"{item.id}: {name} is missing in {src}")
            if runs.sha256(src / name) != entry["sha256"]:
                raise common.Failure(f"{item.id}: {name} no longer matches the sha256 in its generation.json")
            if (dest / name).is_file() and runs.sha256(dest / name) == entry["sha256"]:
                skipped += 1
                continue
            copy(src / name, dest / name)
            if runs.sha256(dest / name) != entry["sha256"]:
                raise common.Failure(f"{item.id}: the copy of {name} in {dest} does not match its sha256")
            copied += 1
        copy(src / runs.STATE, dest / runs.STATE)
        common.ok(f"{item.id} -> {dest}")
    log = runs.batch_dir(batch) / runs.LOG
    if log.is_file():
        copy(log, dest_batch / runs.LOG)
    common.say(f"raw-backup {batch.id}: {copied} files copied, {skipped} already there, in {dest_batch}")
    return 0


def copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    shutil.copyfile(src, part)
    part.replace(dest)
