"""`stylize-quaternius`: stylizes the CC0 Quaternius base body toward our direction in headless Blender
(tools/blender/stylize_quaternius.py), one folder per preset: a GLB, info.json, the 8-view review sheet and a
`check --kind body --map quaternius` report. Outputs go to D:/prime-art-raw/stylized/<preset>/, never into git.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _review, _stylize, check

NAME = "stylize-quaternius"
HELP = "stylize the CC0 Quaternius base body (GLB, review sheet, check report) for each preset"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", type=Path, help="the Quaternius glTF (default the Superhero_Male_FullBody.gltf "
                                                    "of the Universal Base Characters in the raw folder)")
    parser.add_argument("--preset", choices=(*_stylize.PRESETS, "all"), default="all", help="which preset (default all)")
    parser.add_argument("--out", type=Path, help="root folder; each preset goes to <out>/<preset>/ "
                                                 "(default D:/prime-art-raw/stylized)")
    parser.add_argument("--triangles", type=int, default=_stylize.TARGET_TRIANGLES,
                        help=f"decimate to this many triangles when above it (default {_stylize.TARGET_TRIANGLES})")
    parser.add_argument("--cell", type=int, default=512, help="pixel size of one review-sheet view (default 512)")
    parser.add_argument("--no-sheet", action="store_true", help="no review sheet")
    parser.add_argument("--no-check", action="store_true", help="no contract check")


def stylize(preset: str, source: Path, out: Path, triangles: int = _stylize.TARGET_TRIANGLES) -> dict:
    """Runs tools/blender/stylize_quaternius.py for one preset into out; returns its info.json."""
    out.mkdir(parents=True, exist_ok=True)
    info_path, plan_path = out / "info.json", out / "plan.json"
    plan = _stylize.plan(preset, source, out / f"quaternius_{preset}.glb", info_path, target_triangles=triangles)
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if info_path.exists():
        info_path.unlink()
    blender.run_script("stylize_quaternius.py", [plan_path.as_posix()], timeout=1200)
    if not info_path.is_file():
        raise common.Failure(f"stylize_quaternius.py wrote no {info_path}")
    return json.loads(info_path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> int:
    source = (args.source or _stylize.default_source()).resolve()
    if not source.is_file():
        raise common.Failure(f"no Quaternius model at {source}; give --source or put the Universal Base Characters "
                             f"in {common.raw_dir() / 'quaternius'}")
    if args.cell < 64 or args.triangles < 100:
        raise common.Failure("--cell must be at least 64 and --triangles at least 100")
    root = (args.out or _stylize.default_out()).resolve()
    presets = tuple(_stylize.PRESETS) if args.preset == "all" else (args.preset,)
    for preset in presets:
        out = root / preset
        info = stylize(preset, source, out, args.triangles)
        probe = info["probe"]
        eyes = f"{info['eye_height']} m" if info["eye_height"] is not None else "an unknown height (no eye mesh)"
        dead = sorted(label for label, moved in probe.items() if moved <= 0)
        common.say(f"{preset}: {info['triangles_source']} -> {info['triangles']} triangles, height {info['height']} m, "
                   f"eyes at {eyes}, {len(info['bones'])} bones, materials "
                   f"{', '.join(info['materials'])}")
        common.say(f"  rig: {len(probe) - len(dead)} of {len(probe)} probe bones move the skin"
                   + (f"; NOT: {', '.join(dead)}" if dead else ""))
        common.say(f"  model: {info['glb']}")
        if not args.no_sheet:
            stats = _review.render(Path(info["glb"]), out / "sheet", args.cell)
            common.say(f"  sheet: {stats['sheet']}")
        if not args.no_check:
            report = out / "check" / "report.json"
            code = check.run(argparse.Namespace(model=info["glb"], kind="body", slot=None, map="quaternius",
                                                report=str(report)))
            unexpected = _stylize.unexpected_failures(json.loads(report.read_text(encoding="utf-8")))
            common.say(f"  check exit code {code} (the Quaternius rig has no {', '.join(_stylize.KNOWN_MISSING_BONES)}"
                       f" bones; only other failures fail this command)")
            if unexpected:
                raise common.Failure(f"{preset}: check failed beyond the known missing bones: "
                                     + "; ".join(unexpected))
        if dead:
            raise common.Failure(f"{preset}: the rig no longer moves the skin for {', '.join(dead)}")
    return 0
