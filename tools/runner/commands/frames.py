"""`frames`: motion frame sheets of an exported character rendered by Godot 4.7.2 itself in an off-screen window (never
headless, never minimized), one labelled sheet per animation; optionally Blender's renders of the same frames beside
Godot's with a joint-by-joint comparison, and short looping MP4 clips (docs/godot.md)."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .. import blender, common
from . import _frames, _godot

NAME = "frames"
HELP = "Godot-rendered motion frame sheets of an exported character (off-screen window); Blender comparison; MP4 clips"
TIMEOUT = 1800


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("glb", type=Path, help="a GLB from `export` (its .export.json beside it names the .blend)")
    parser.add_argument("--out", type=Path, help="output folder (default tools/out/frames/<stem>/)")
    parser.add_argument("--clips", default="", help="comma list of animations without the CharacterArmature| prefix (default: all)")
    parser.add_argument("--compare", default="all",
                        help="clips Blender renders beside Godot's frames, joints compared (default all the rendered clips; '' for none)")
    parser.add_argument("--video", default="", help=f"clips to encode as looping MP4 (e.g. {','.join(_frames.VIDEO)}; default none)")
    parser.add_argument("--blend", type=Path, help="the character .blend for the comparison (default: the one the export names)")


def run(args: argparse.Namespace) -> int:
    glb = args.glb if args.glb.is_file() else common.ROOT / args.glb
    if not glb.is_file() or glb.suffix.lower() != ".glb":
        raise common.Failure(f"no GLB {args.glb.as_posix()}")
    glb = glb.resolve()
    expect = _godot.expectations(glb)
    animations = expect["animations"]
    wanted = [c for c in args.clips.split(",") if c]
    by_label = {_frames.label(n): n for n in animations}
    unknown = [c for c in wanted if c not in by_label]
    compare = [c for c in args.compare.split(",") if c and c != "all"]
    video = [c for c in args.video.split(",") if c]
    unknown += [c for c in compare + video if c not in by_label]
    if unknown:
        raise common.Failure(f"unknown clips {', '.join(unknown)}; {glb.name} has: {', '.join(sorted(by_label))}")
    if wanted:
        animations = {by_label[c]: animations[by_label[c]] for c in dict.fromkeys(wanted + compare + video)}
    if args.compare == "all":
        compare = sorted(_frames.label(n) for n in animations)
    out = (args.out or _frames.OUT / glb.stem).resolve()
    for sub in ("sheets", "frames", "video", "compare", "clips"):
        shutil.rmtree(out / sub, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    spec = _frames.spec(glb.stem, animations, compare, video, expect.get("seams"), expect.get("fps", _frames.FPS),
                        set(expect.get("loop_suffix", [])))
    for clip in spec["clips"]:
        if clip["open_cycle"]:
            common.warn(f"{clip['label']}: its last key does not repeat its first; one cycle is {clip['cycle_s']:.3f} s, "
                        f"one frame longer than its keys")
    spec_path = out / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=1), encoding="utf-8")

    _godot.clear_staged({glb.stem})
    res_path = _godot.stage(glb, params=_godot.import_params(glb))
    import_lines = _godot.import_project()
    common.say(f"frames: {len(spec['clips'])} animations of {glb.name} in an off-screen Godot window -> {out.as_posix()}")
    w, h = _frames.WINDOW
    code, output = _godot.godot(["--path", _godot.PROJECT, "--position", _frames.POSITION, "--resolution", f"{w}x{h}",
                                 "-s", _frames.SCRIPT, "--", res_path, out.as_posix(), spec_path.as_posix()], TIMEOUT)
    (out / "godot.log").write_text(output, encoding="utf-8")
    lines = _godot.noteworthy(output)
    errors = [ln for ln in output.splitlines() if "FRAMES error" in ln] + [ln for ln in lines if "ERROR" in ln]
    record_path = out / "frames.json"
    if code != 0 or errors or not record_path.is_file():
        raise common.Failure(f"frames.gd failed (exit code {code}): {'; '.join(errors[:5]) or 'see ' + (out / 'godot.log').as_posix()}")
    renderer = next((ln.split("FRAMES renderer ", 1)[1] for ln in output.splitlines() if "FRAMES renderer " in ln), "?")
    common.ok(f"{len(spec['clips'])} sheets in {(out / 'sheets').as_posix()} (renderer {renderer})")
    for line in import_lines + lines:
        common.warn(f"godot: {line}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    actions = expect.get("actions", {})  # Blender's action of each Godot animation (a loop suffix dropped, art #33)
    for clip in record.get("clips", {}).values():
        clip["action"] = actions.get(clip["name"], clip["name"])
    record_path.write_text(json.dumps(record, indent=1), encoding="utf-8")

    failed = False
    if compare:
        failed |= not _compare(args, glb, out, compare, record)
    if video:
        folders = [str(out / "video" / c) for c in video]
        blender.run_script("encode_clips.py", ["--frames", *folders, "--out", str(out / "clips"), "--fps", str(_frames.FPS)],
                           timeout=TIMEOUT)
        for c in video:
            clip = out / "clips" / f"{c}.mp4"
            if not clip.is_file():
                raise common.Failure(f"encode_clips.py wrote no {clip}")
            common.ok(f"clip {clip.as_posix()} ({clip.stat().st_size // 1024} KB)")
    return 1 if failed else 0


def _compare(args: argparse.Namespace, glb: Path, out: Path, compare: list[str], record: dict) -> bool:
    blend = args.blend
    if blend is None:
        info = glb.with_name(f"{glb.stem}.export.json")
        if info.is_file():
            blend = Path(json.loads(info.read_text(encoding="utf-8"))["blend"])
    if blend is None or not blend.is_file():
        raise common.Failure(f"no character .blend for the comparison ({blend}); pass --blend or --compare ''")
    folder = out / "compare"
    blender.run_script("compare_frames.py", ["--blend", str(blend), "--frames", str(out / "frames.json"),
                                             "--clips", ",".join(compare), "--out", str(folder)], timeout=TIMEOUT)
    joints = json.loads((folder / "blender_joints.json").read_text(encoding="utf-8"))
    result = _frames.compare_joints(record, joints)
    (folder / "compare.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    good = True
    for short, r in result.items():
        text = (f"{short}: {r['joints']} joints and {r['axis_points']} axis points at {len(r['per_time_mm'])} times, "
                f"Godot and Blender within {r['max_mm']:.3f} mm "
                f"(worst {r['where']}; allowed {_frames.JOINT_TOLERANCE_M * 1000:.0f} mm) -> {(folder / (short + '.png')).as_posix()}")
        (common.ok if r["match"] else common.bad)(text)
        good &= r["match"]
    return good
