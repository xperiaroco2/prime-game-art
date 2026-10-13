"""`showroom`: how close Godot can make a character look to its Blender renders (art #140). Godot 4.7.2 renders one
character under up to six look variants (the frames stand as is, then AgX, sky reflections, SSAO, soft shadows,
subsurface scattering on the clay) in an off-screen window (never headless, never minimized): a face sheet (front and
three-quarter, the approved Blender sheet first) and a full-body sheet, and each variant's GPU time. `--write-presets`
writes the recommended look per graphics preset, godot/showroom/look_presets.json (docs/godot.md)."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .. import common
from . import _frames, _godot, _showroom

NAME = "showroom"
HELP = "Godot look variants of a character (AgX, reflections, SSAO, soft shadows, SSS) in an off-screen window; GPU ms"
TIMEOUT = 900
PRESETS_FILE = common.ROOT / "godot" / "showroom" / "look_presets.json"
DEFAULT_GLB = Path("assets/character/slice_m1/export/slice_m1.glb")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("glb", type=Path, nargs="?", default=DEFAULT_GLB, help=f"an exported character (default {DEFAULT_GLB.as_posix()})")
    parser.add_argument("--out", type=Path, help="output folder (default tools/out/showroom/<stem>/)")
    parser.add_argument("--variants", default="", help=f"comma list of {', '.join(v['id'] for v in _showroom.VARIANTS)} (default all)")
    parser.add_argument("--clip", default="Idle", help="the pose: time 0 of this animation (default Idle)")
    parser.add_argument("--hdri", type=Path, help=f"the studio sky (default <raw>/{_showroom.HDRI}; missing: a ProceduralSky)")
    parser.add_argument("--beside", type=Path, help="the approved Blender faces sheet whose crops lead the face sheet")
    parser.add_argument("--beside-rects", default=";".join(",".join(map(str, r)) for r in _showroom.APPROVED_RECTS),
                        help="the crops of --beside in pixels: 'x,y,w,h;x,y,w,h' (default: m1's row of the round-4 sheet)")
    parser.add_argument("--write-presets", action="store_true",
                        help=f"only write {PRESETS_FILE.relative_to(common.ROOT).as_posix()} (no Godot)")


def write_presets(timing: list | None = None) -> Path:
    problems = _showroom.preset_problems()
    if problems:
        raise common.Failure("; ".join(problems))
    PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_showroom.presets_document(timing), indent=1) + "\n"
    PRESETS_FILE.write_text(text, encoding="utf-8", newline="\n")
    return PRESETS_FILE


def run(args: argparse.Namespace) -> int:
    if args.write_presets:
        common.ok(f"wrote {write_presets().as_posix()}")
        return 0
    glb = args.glb if args.glb.is_file() else common.ROOT / args.glb
    if not glb.is_file() or glb.suffix.lower() != ".glb":
        raise common.Failure(f"no GLB {args.glb.as_posix()}")
    glb = glb.resolve()
    animations = _godot.expectations(glb)["animations"]
    by_label = {_frames.label(n): n for n in animations}
    if args.clip not in by_label:
        raise common.Failure(f"unknown clip {args.clip}; {glb.name} has: {', '.join(sorted(by_label))}")
    hdri = args.hdri or common.raw_dir() / _showroom.HDRI
    if not hdri.is_file():
        common.warn(f"no HDRI {hdri.as_posix()}: a ProceduralSky lights the studio")
    beside = ""
    if args.beside:
        if not args.beside.is_file():
            raise common.Failure(f"no approved sheet {args.beside.as_posix()}")
        beside = args.beside.resolve().as_posix()
    try:
        chosen = _showroom.variants(args.variants)
        spec = _showroom.spec(glb.stem, by_label[args.clip], hdri.resolve().as_posix() if hdri.is_file() else "",
                              chosen, beside, _frames.parse_rects(args.beside_rects) if beside else None)
    except ValueError as e:
        raise common.Failure(str(e)) from e
    out = (args.out or _showroom.OUT / glb.stem).resolve()
    shutil.rmtree(out / "shots", ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    spec_path = out / "showroom_spec.json"
    spec_path.write_text(json.dumps(spec, indent=1), encoding="utf-8")

    _godot.clear_staged({glb.stem})
    res_path = _godot.stage(glb, params=_godot.import_params(glb))
    import_lines = _godot.import_project()
    common.say(f"showroom: {len(chosen)} variants of {glb.name} in an off-screen Godot window -> {out.as_posix()}")
    w, h = _showroom.WINDOW
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", f"{w}x{h}", "-s", _showroom.SCRIPT, "--", res_path, out.as_posix(),
                                 spec_path.as_posix()], TIMEOUT)
    (out / "godot.log").write_text(output, encoding="utf-8")
    lines = _godot.noteworthy(output)
    errors = [ln for ln in output.splitlines() if "SHOWROOM error" in ln] + [ln for ln in lines if "ERROR" in ln]
    record_path = out / "showroom.json"
    if code != 0 or errors or not record_path.is_file():
        raise common.Failure(f"showroom.gd failed (exit code {code}): "
                             f"{'; '.join(errors[:5]) or 'see ' + (out / 'godot.log').as_posix()}")
    for line in import_lines + lines:
        common.warn(f"godot: {line}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    table = _showroom.gpu_table(record)
    (out / "gpu_ms.md").write_text("\n".join(table) + "\n", encoding="utf-8", newline="\n")
    common.ok(f"sheets {(out / 'face.png').as_posix()} and {(out / 'body.png').as_posix()} "
              f"(renderer {record.get('renderer', '?')}, sky {record.get('sky', '?')})")
    for line in table:
        common.say(f"verify: {line}")
    return 0
