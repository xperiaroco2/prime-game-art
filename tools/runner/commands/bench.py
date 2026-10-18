"""`bench`: what a character costs in Godot 4.7.2 (art #212). N copies of a character GLB (default 10 and 20) stand in
a meeting ring playing their idle clip, under a directional light with 4 shadow splits and a shadowed omni lamp, at
1920x1080 in an off-screen window (never headless, never minimized). Per variant (the automatic LOD on and off,
full-mesh shadows or the low-poly shadow proxy, one GLB per face-morph count) it measures the median GPU and CPU ms,
the frame's primitives and draw calls and the video, texture and buffer memory; bench.json, bench.md and sheet.png in
its out folder. `--proxy-from` first makes the stand-in character in headless Blender (tools/blender/bench_proxy.py:
about --tris triangles, the head split off with 0, 32 and 64 face morphs, a shadow proxy, the 2048 bakes) and exports
it with `export --textured` (docs/godot.md, "Bench")."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .. import blender, common
from . import _bench, _frames, _godot

NAME = "bench"
HELP = "GPU/CPU ms, primitives and memory of N copies of a character in an off-screen Godot window (art #212)"
TIMEOUT = 1500
PROXY_TIMEOUT = 900
# Staged under their own names, so that the VRAM texture settings never reach the textures another command (godot-check,
# frames) extracts from the same GLB.
STAGE_PREFIX = "bench_"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("glb", type=Path, nargs="*", help="character GLBs to measure (one per face-morph count)")
    parser.add_argument("--proxy-from", type=Path,
                        help="make the stand-in from this character .blend first (its 2048 bakes beside it)")
    parser.add_argument("--tris", type=int, default=40000, help="the stand-in's triangles (default 40000)")
    parser.add_argument("--morphs", default="0,32,64", help="the stand-in's face morph counts (default 0,32,64)")
    parser.add_argument("--shadow-tris", type=int, default=7000, help="the shadow proxy's triangles (default 7000)")
    parser.add_argument("--copies", default="10,20", help="copy counts (default 10,20)")
    parser.add_argument("--clip", default="Idle", help="the clip every copy plays (default Idle)")
    parser.add_argument("--frames", type=int, default=_bench.FRAMES, help=f"measured frames per variant ({_bench.FRAMES})")
    parser.add_argument("--warmup", type=int, default=_bench.WARMUP, help=f"warm-up frames per GLB and count ({_bench.WARMUP})")
    parser.add_argument("--hand-lod-m", type=float, default=_bench.HAND_LOD_M,
                        help=f"where the hand-made LOD2 takes over in the 'hand' variant (default: the contract's LOD2, "
                             f"{_bench.HAND_LOD_M:g} m)")
    parser.add_argument("--budget-ms", type=float, default=_bench.BUDGET_MS,
                        help=f"the characters' GPU share the verdict holds them to (default {_bench.BUDGET_MS:g})")
    parser.add_argument("--out", type=Path, help="output folder (default tools/out/bench/run/)")


def make_proxy(blend: Path, out: Path, args: argparse.Namespace) -> list[Path]:
    """Runs bench_proxy.py, then `export --textured` on each saved stand-in; returns the GLBs."""
    from .export import export_one

    proxy_dir = out / "proxy"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    common.say(f"bench: the stand-in from {blend.as_posix()} in headless Blender -> {proxy_dir.as_posix()}")
    result = blender.run_script("bench_proxy.py", ["--blend", str(blend), "--out", str(proxy_dir), "--tris",
                                                   str(args.tris), "--morphs", args.morphs, "--shadow-tris",
                                                   str(args.shadow_tris)], timeout=PROXY_TIMEOUT)
    line = next((ln for ln in (result.stdout or "").splitlines() if ln.startswith("BENCH_PROXY ")), "")
    if not line:
        raise common.Failure("bench_proxy.py printed no BENCH_PROXY line")
    made = json.loads(line[len("BENCH_PROXY "):])
    (proxy_dir / "proxy.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    glbs = []
    for count in sorted(made["blends"], key=int):
        stand_in = Path(made["blends"][count])
        if not export_one(stand_in, out / "glb" / stand_in.stem, textured=True):
            common.warn(f"export of {stand_in.name} reported problems (see above); measured anyway")
        glbs.append(out / "glb" / stand_in.stem / f"{stand_in.stem}.glb")
    return glbs


def vram_textures(stems: set[str]) -> int:
    """Sets the textures Godot extracted from the staged GLBs to VRAM Compressed (_bench.vram_import); returns how
    many .import files changed."""
    changed = 0
    for path in sorted(_godot.IMPORT_DIR.glob("*.png.import")):
        if not any(path.name.startswith(f"{s}_") for s in stems):
            continue
        text = path.read_text(encoding="utf-8")
        new = _bench.vram_import(text, normal="nrm" in path.name.lower() or "normal" in path.name.lower())
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def run(args: argparse.Namespace) -> int:
    try:
        copies = _bench.parse_copies(args.copies)
    except ValueError as e:
        raise common.Failure(str(e)) from e
    out = (args.out or _bench.OUT / "run").resolve()
    out.mkdir(parents=True, exist_ok=True)
    paths = [p if p.is_file() else common.ROOT / p for p in args.glb]
    if args.proxy_from:
        if not args.proxy_from.is_file() or args.proxy_from.suffix.lower() != ".blend":
            raise common.Failure(f"no character .blend {args.proxy_from.as_posix()}")
        paths += make_proxy(args.proxy_from.resolve(), out, args)
    if not paths:
        raise common.Failure("give character GLBs or --proxy-from <character.blend>")
    for p in paths:
        if not p.is_file() or p.suffix.lower() != ".glb":
            raise common.Failure(f"no GLB {p.as_posix()}")
    stems: dict[str, Path] = {}
    for p in paths:  # a GLB's stem is its id, its staged name and its rows' prefix
        if p.stem.lower() in stems:
            raise common.Failure(f"two GLBs named {p.stem}: {stems[p.stem.lower()].as_posix()} and {p.as_posix()}; "
                                 "rename one")
        stems[p.stem.lower()] = p
    glbs = []
    _godot.clear_staged({STAGE_PREFIX + p.stem for p in paths})
    for p in paths:
        info = _bench.describe(_bench.glb_json(p))
        glbs.append({"id": p.stem, "path": p.resolve().as_posix(), "mb": p.stat().st_size / 1e6,
                     "res": _godot.stage(p.resolve(), STAGE_PREFIX + p.stem, _godot.import_params(p)), **info})
    try:
        spec = _bench.spec(glbs, copies, args.clip, args.frames, args.warmup, hand_lod_m=args.hand_lod_m)
    except ValueError as e:
        raise common.Failure(str(e)) from e
    shutil.rmtree(out / "shots", ignore_errors=True)
    (out / "shots").mkdir(parents=True)
    spec_path = out / "bench_spec.json"
    spec_path.write_text(json.dumps(spec, indent=1), encoding="utf-8")
    import_lines = _godot.import_project()
    if vram_textures({STAGE_PREFIX + p.stem for p in paths}):  # imported again with the textures as the game has them
        import_lines = _godot.import_project()
    w, h = _bench.WINDOW
    common.say(f"bench: {len(spec['variants'])} variants of {', '.join(g['id'] for g in glbs)} in an off-screen "
               f"{w}x{h} Godot window -> {out.as_posix()}")
    code, output = _godot.godot(["--path", _godot.PROJECT, "--audio-driver", "Dummy", "--position", _frames.POSITION,
                                 "--resolution", f"{w}x{h}", "-s", _bench.SCRIPT, "--", out.as_posix(),
                                 spec_path.as_posix()], TIMEOUT)
    (out / "godot.log").write_text(output, encoding="utf-8")
    errors = [ln for ln in output.splitlines() if "BENCH error" in ln]
    record_path = out / "bench.json"
    if code != 0 or errors or not record_path.is_file():
        raise common.Failure(f"bench.gd failed (exit code {code}): "
                             f"{'; '.join(errors[:5]) or 'see ' + (out / 'godot.log').as_posix()}")
    for line in import_lines + _godot.noteworthy(output):
        common.warn(f"godot: {line}")
    record = _bench.derive(json.loads(record_path.read_text(encoding="utf-8")))
    record["glbs"] = glbs
    record_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    lines = _bench.report(record, glbs, args.budget_ms)
    (out / "bench.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    common.ok(f"{(out / 'bench.md').as_posix()} and {(out / 'sheet.png').as_posix()} ({record.get('adapter', '?')})")
    for line in lines:
        if line.startswith("- ") and "budget" in line:
            common.say(f"verify: {line[2:]}")
    return 0
