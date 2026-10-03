"""`stylize-quaternius`: restyles the CC0 Quaternius base body into our base body in headless Blender (art #14), one
folder per preset under D:/prime-art-raw/restyled/<preset>/ (never in git):

1. tools/blender/stylize_quaternius.py builds the body and saves build/stage_<preset>.blend (the rig's own names);
2. `rename-bones --map quaternius` turns it into restyled_<preset>.glb and the working copy restyled_<preset>.blend;
3. the export check: the GLB may hold no mesh but the body (_stylize.ALLOWED_MESHES);
4. the gates: the 8-view sheet, `check --kind body`, and tools/blender/restyle_gates.py (measurements, the defect
   check, head and hand close-ups, the pose sheet, the 20 m line-up next to mannequin-lanky and quaternius-base);
5. the verdict (_stylize.gate_failures): any failed gate fails the command.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import blender, common
from . import _review, _stylize, check, rename_bones

NAME = "stylize-quaternius"
HELP = "restyle the CC0 Quaternius base body into our base body (GLB, .blend, sheets and gates) for each preset"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", type=Path, help="the Quaternius glTF (default the Superhero_Male_FullBody.gltf "
                                                    "of the Universal Base Characters in the raw folder)")
    parser.add_argument("--preset", choices=(*_stylize.PRESETS, "all"), default="all",
                        help="which preset (default all; lanky and bighead are measured against base's last build)")
    parser.add_argument("--out", type=Path, help="root folder; each preset goes to <out>/<preset>/ "
                                                 "(default D:/prime-art-raw/restyled)")
    parser.add_argument("--triangles", type=int, default=_stylize.TARGET_TRIANGLES,
                        help=f"decimate to this many triangles when above it (default {_stylize.TARGET_TRIANGLES})")
    parser.add_argument("--cell", type=int, default=512, help="pixel size of one sheet or close-up view (default 512)")
    parser.add_argument("--no-gates", action="store_true", help="build only: no sheet, check, close-ups or poses")


def build(preset: str, source: Path, out: Path, triangles: int) -> dict:
    """Runs the Blender build and the rename for one preset; returns build.json with the output paths added."""
    base_positions = out.parent / "base" / "build" / "normalized.npy"
    plan = _stylize.plan(preset, source, out, target_triangles=triangles, base_positions=base_positions)
    build_dir = Path(plan["info"]).parent
    build_dir.mkdir(parents=True, exist_ok=True)
    plan_path = build_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    info_path = Path(plan["info"])
    if info_path.exists():
        info_path.unlink()
    blender.run_script("stylize_quaternius.py", [plan_path.as_posix()], timeout=1800)
    if not info_path.is_file():
        raise common.Failure(f"stylize_quaternius.py wrote no {info_path}")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    glb, blend = out / f"restyled_{preset}.glb", out / f"restyled_{preset}.blend"
    for target in (glb, blend):
        rename_bones.run(argparse.Namespace(model=plan["stage_blend"], map="quaternius", out=str(target)))
    blend1 = blend.with_suffix(".blend1")
    if blend1.exists():
        blend1.unlink()
    info.update({"glb": glb.as_posix(), "blend": blend.as_posix(), "head_ratio_target": plan["head_ratio"],
                 "target_triangles": triangles})
    return info


def gates(preset: str, out: Path, info: dict, cell: int, base_glb: Path | None) -> dict:
    """The sheet, the contract check and the Blender gates for one preset; returns their results."""
    glb = Path(info["glb"])
    results: dict = {"sheet": _review.render(glb, out / "sheet", cell)["sheet"]}
    report = out / "check" / "report.json"
    results["check_exit_code"] = check.run(argparse.Namespace(model=str(glb), kind="body", slot=None, map=None,
                                                              report=str(report)))
    results["check"] = json.loads(report.read_text(encoding="utf-8"))
    refs = _stylize.default_references()
    lineup = [{"label": f"restyled {preset}", "path": glb.as_posix()},
              *({"label": label, "path": path.as_posix()} for label, path in refs.items())]
    results.update(run_gates(glb, out, ["measure", "defects", "closeups", "poses", "lineup"], cell,
                             base_glb if base_glb and base_glb != glb else None, lineup, out / "lineup.png"))
    base_info = out.parent / "base" / "info.json"
    if preset != "base" and base_info.is_file():
        results["base_measure"] = json.loads(base_info.read_text(encoding="utf-8")).get("measure")
    return results


def run_gates(glb: Path | None, out: Path, tasks: list[str], cell: int, base_glb: Path | None, lineup: list[dict],
              lineup_out: Path) -> dict:
    spec_path, result_path = out / "build" / "gates_spec.json", out / "build" / "gates.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec = {"model": glb.as_posix() if glb else None, "out": out.as_posix(), "tasks": tasks, "cell": cell,
            "base_model": base_glb.as_posix() if base_glb else None, "lineup": lineup,
            "lineup_out": lineup_out.as_posix(), "result": result_path.as_posix()}
    spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    if result_path.exists():
        result_path.unlink()
    blender.run_script("restyle_gates.py", [spec_path.as_posix()], timeout=1800)
    return json.loads(result_path.read_text(encoding="utf-8"))


def report(preset: str, info: dict) -> None:
    common.say(f"{preset}: {info['triangles_source']} -> {info['triangles']} triangles; model {info['glb']}")
    measure = info.get("measure")
    if measure:
        shift = info.get("shift_from_base")
        common.say(f"  height {measure['height']} m, lowest {measure['lowest']} m, soles centred at "
                   f"{measure['soles_centre']}, eyes {measure.get('eye_height')} m, head {measure.get('head_ratio')}"
                   f" of the height (target {info['head_ratio_target']} x the source's "
                   f"{info['source_head_ratio']})" + (f"; each vertex {shift['median'] * 1000:.1f} mm (median) "
                                                    f"from base's" if shift and "median" in shift else ""))
    defects = info.get("defects")
    if defects:
        hands = ", ".join(f"{side} {hand['islands']}" for side, hand in defects["hands"].items())
        common.say(f"  defects: finger islands {hands}; {defects['open_edges']} open, "
                   f"{defects['non_manifold_edges']} non-manifold edges, {defects['connected_parts']} parts")
    for key in ("sheet",):
        if key in info:
            common.say(f"  {key}: {info[key]}")
    for key, path in (info.get("closeups") or {}).items():
        common.say(f"  {key} close-up: {path}")
    if info.get("poses"):
        common.say(f"  poses: {info['poses']['sheet']}")
    if info.get("lineup"):
        common.say(f"  line-up: {info['lineup']['lineup_x4']}")


def run(args: argparse.Namespace) -> int:
    source = (args.source or _stylize.default_source()).resolve()
    if not source.is_file():
        raise common.Failure(f"no Quaternius model at {source}; give --source or put the Universal Base Characters "
                             f"in {common.raw_dir() / 'quaternius'}")
    if args.cell < 64 or args.triangles < 100:
        raise common.Failure("--cell must be at least 64 and --triangles at least 100")
    root = (args.out or _stylize.default_out()).resolve()
    presets = tuple(_stylize.PRESETS) if args.preset == "all" else (args.preset,)
    base_glb = root / "base" / "restyled_base.glb"
    failures: list[str] = []
    for preset in presets:
        out = root / preset
        info = build(preset, source, out, args.triangles)
        stray = _stylize.stray_meshes(_stylize.glb_meshes(Path(info["glb"])))
        if stray:
            raise common.Failure(f"{preset}: the GLB holds meshes other than the body: {', '.join(stray)}")
        if not args.no_gates:
            info.update(gates(preset, out, info, args.cell, base_glb if base_glb.is_file() else None))
        (out / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        report(preset, info)
        if not args.no_gates:
            failures += [f"{preset}: {f}" for f in _stylize.gate_failures(info)]
    if len(presets) > 1 and not args.no_gates:
        refs = _stylize.default_references()
        entries = [{"label": f"restyled {p}", "path": (root / p / f"restyled_{p}.glb").as_posix()} for p in presets]
        entries += [{"label": label, "path": path.as_posix()} for label, path in refs.items()]
        result = run_gates(None, root, ["lineup"], args.cell, None, entries, root / "lineup.png")
        common.say(f"line-up of every preset: {result['lineup']['lineup_x4']}")
    if failures:
        raise common.Failure("gates failed:\n  " + "\n  ".join(failures))
    return 0
