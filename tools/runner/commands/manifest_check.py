"""`manifest-check`: validates every assets/<kind>/<id>/manifest.toml and every sources/<id>.toml against the schema in
docs/manifest.md."""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import common
from . import _manifest

NAME = "manifest-check"
HELP = "validate every assets/**/manifest.toml and sources/*.toml (docs/manifest.md)"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root", type=Path, default=common.ROOT, help="the tree whose assets/ and sources/ are checked (default: the repo)"
    )
    parser.add_argument(
        "--hashes", action="store_true", help="also check each [[raw]] file's sha256 in the raw folder (ART_RAW_DIR)"
    )


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    manifests, errors = _manifest.find(root)
    failed = len(errors)
    for line in errors:
        common.bad(line)
    for path in manifests:
        rel = path.relative_to(root).as_posix()
        data, problem = _manifest.load(path)
        problems = [problem] if problem else _manifest.validate(data or {}, path.parent.parent.name, path.parent.name)
        if not problem and args.hashes:
            problems += _manifest.check_raw_hashes(data or {}, common.raw_dir())
        if problems:
            failed += 1
            common.bad(rel, "\n".join(problems))
        else:
            common.ok(rel)
    sources = _manifest.find_sources(root)
    for path in sources:
        rel = path.relative_to(root).as_posix()
        data, problem = _manifest.load(path)
        problems = [problem] if problem else _manifest.validate_source(data or {}, path.stem)
        if not problem and args.hashes:
            problems += _manifest.check_raw_hashes(data or {}, common.raw_dir())
        if problems:
            failed += 1
            common.bad(rel, "\n".join(problems))
        else:
            common.ok(rel)
    if not manifests and not errors and not sources:
        common.say(f"manifest-check: no manifests under {(root / 'assets').as_posix()} yet")
        return 0
    counted = f"{len(manifests)} manifest(s), " + (f"{len(sources)} source record(s), " if sources else "")
    common.say(f"manifest-check: {counted}{failed} problem(s)")
    if failed:
        raise common.Failure("fix the manifests and source records above (schema: docs/manifest.md)")
    return 0
