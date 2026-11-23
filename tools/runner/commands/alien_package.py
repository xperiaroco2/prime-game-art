"""`alien-package`: an alien character's game package (art #393; docs/godot.md, "The alien's game package"). From a
rigged alien GLB on the contract skeleton (one skinned mesh, `<name>_static_skin` and `<name>_body_skin`):
- `export/<id>.glb`: the review clips dropped, the kept ones under their set names, the binary compacted;
- `export/look/`: the approved static look (art #196) as the game loads it: alien_dress.gd, alien_static.gd and its
  shaders (preloads made relative), `<id>_look.json` (the inputs the review pages' shots used) and `<id>_mask.png`
  with a lossless `.import`;
- `export/<id>.ragdoll.json` (the contract rig's table, `_ragdoll`);
- `package.json` (files, the game's clips and bones, sockets, heights, clip speeds) and `HANDOFF.md`.
`--check DIR` then stages the package folder in godot/ and proves it in an off-screen window (godot/alien/
package_check.gd): the look from the package's own files, the game's clips and bones, the sockets, and a turnaround
diffed against the review page's. manifest.toml is written by hand (the provenance)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from .. import common
from . import _alien_package as P, _godot, _ragdoll, ragdoll

NAME = "alien-package"
HELP = "an alien character's game package: the GLB without review clips, its look, ragdoll, sockets; --check in Godot"

ALIEN = common.ROOT / "godot" / "alien"
LOOK_FILES = ("alien_static.gd", "alien_static.gdshader", "alien_static_288.gdshader", "alien_dress.gd")
SLICE = common.ROOT / "assets" / "character" / "slice_m1" / "export" / "slice_m1.glb"
MASK_IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=true
process/fix_alpha_border=false
process/premult_alpha=false
process/size_limit=0
detect_3d/compress_to=0
"""
TIMEOUT = 600


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("glb", type=Path, nargs="?", help="the rigged alien GLB (e.g. <raw>/recovered/.../chameleon.glb)")
    parser.add_argument("--name", help="the materials' name: <name>_static_skin, <name>_body_skin (e.g. chameleon)")
    parser.add_argument("--id", help="the asset id (e.g. alien_chameleon)")
    parser.add_argument("--asset", type=Path, required=True, help="the asset folder (assets/character/<id>)")
    parser.add_argument("--slice", type=Path, default=SLICE, help="the GLB the game's sockets were measured on")
    parser.add_argument("--check", type=Path, help="prove the asset folder's package in Godot; shots and report here")
    parser.add_argument("--compare", type=Path, help="--check: the review page's turnaround PNG to diff against")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def look_inputs(glb: Path, name: str) -> tuple[dict, bytes]:
    """The look file's inputs exactly as the review pages' shots took them (tools/blender/alien_look_run.py), and
    the mask PNG's bytes."""
    sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
    import alien_look_run as L  # plain Python; its stand-ins for the sidecar maps lost with D:
    images = L.glb_images(glb)
    missing = [k for k in (f"{name}_mask", f"{name}_body_albedo") if k not in images]
    if missing:
        raise common.Failure(f"{glb.name}: no embedded PNG {', '.join(missing)} (is '{name}' the materials' name?)")
    mask = images[f"{name}_mask"]
    look = {"mask": "", "base_skin": [round(x, 6) for x in L.median_rgb(images[f"{name}_body_albedo"])],
            "detail": L.DETAIL, "body_mask": [round(x, 6) for x in L.body_mask(mask)], "body_detail": L.DETAIL,
            "params": L.alive_params()}
    return look, mask


def write_look(look_dir: Path, asset_id: str, look: dict, mask: bytes) -> None:
    look_dir.mkdir(parents=True, exist_ok=True)
    for f in LOOK_FILES:
        text = (ALIEN / f).read_text(encoding="utf-8").replace('preload("res://alien/', 'preload("')
        (look_dir / f).write_text(text, encoding="utf-8", newline="\n")
    (look_dir / f"{asset_id}_mask.png").write_bytes(mask)
    (look_dir / f"{asset_id}_mask.png.import").write_text(MASK_IMPORT, encoding="utf-8", newline="\n")
    look = {**look, "mask": f"{asset_id}_mask.png"}
    (look_dir / f"{asset_id}_look.json").write_text(json.dumps(look, indent=1) + "\n", encoding="utf-8", newline="\n")


def files_list(asset: Path) -> list[dict]:
    export = asset / "export"
    return [{"name": p.relative_to(export).as_posix(), "bytes": p.stat().st_size, "sha256": _sha(p)}
            for p in sorted(export.rglob("*")) if p.is_file()]


def _row(r: dict) -> str:
    serves = P.GAME_CLIPS.get(r["godot_name"], "not played by the game yet")
    speed = f"{r['speed_m_s']:.2f}" if r["speed_m_s"] is not None else "-"
    return (f"| `{r['godot_name']}` | `{r['set_name']}` | {'LINEAR' if r['loop'] else 'none'} | {r['seconds']:.3f} | "
            f"{speed} | {serves} |")


def handoff(asset_id: str, pkg: dict, glb_bytes: int, dropped: list[str]) -> str:
    h, s, rows = pkg["heights"], pkg["sockets"], pkg["clip_rows"]
    game_rows = [r for r in rows if r["godot_name"] in P.GAME_CLIPS]
    extra = [r for r in rows if r["godot_name"] not in P.GAME_CLIPS]
    sock = "\n".join(f"| `{n}` | `{v['bone']}` | `Vector3({', '.join(f'{x:.4f}' for x in v['point'])})` | "
                     f"{'true' if v['fitted_carrying'] else 'false'} | {v['how']} |" for n, v in s.items())
    bones = "\n".join(f"| `{a}` | `{b}` |" for a, b in P.GAME_BONES.items())
    look_files = "\n".join(f"| `export/{f['name']}` | `{pkg['game_dir']}/{f['name']}` | {f['bytes']:,} |"
                           for f in pkg["files"])
    return f"""# {asset_id}: handoff to the game (art #393)

The base alien for M8 (prime-game#1095, the engineer's pick of 2026-11-24: the recovered chameleon, body A): the
chameleon man of art #196 rebuilt from the review page "Alien Bodies A: Step 1" (2026-10-28, recovered after the D:
loss, `docs/research/2026-11-18-d-loss.md`), one skinned mesh on the art contract's humanoid skeleton (59 bones: the
contract's 56 and three crest springs under `Head`) with its locomotion clips, the approved static look (art #196) as
a shader, the ragdoll data and the game's sockets. It replaces slice_m1 as the game's character.

Rest height {h['top_m']:.3f} m to the crest, feet at {abs(h['feet_m']):.3f} m, eyes at {h['eyes_m']:.3f} m, the `Head`
joint at {h['head_joint_m']:.3f} m, `Hips` at {h['hips_joint_m']:.3f} m. Not scaled: art #196 sized body A to its 1.95 m cap.
slice_m1 was scaled so its eyes are at 1.60 m (the game's camera); here the eyes are {(h['eyes_m'] - 1.6) * 100:.0f} cm higher and the crest
passes the game's 1.8 m capsule by {(h['top_m'] - 1.8) * 100:.0f} cm. The game decides: its camera and capsule follow these numbers, or
it scales the model by {1.6 / h['eyes_m']:.3f} at import (eyes at 1.60 m, the crest at {h['top_m'] * 1.6 / h['eyes_m']:.2f} m; the sockets and the
ragdoll are in the bones' frames and scale with it).

## Known deviations

- An older build than art #196's last polish (the walk hop, the crouch plant and the hands of art PRs #369, #371,
  #373): those builds were lost with D: and come back after M8.
- The look lacks what was lost with D: the stripes and colour accents (only the base teal is left), the thin parts'
  translucency (crest, gills, lips), the iris ring and the eye controller (the eyes do not look around or blink).
- No `Carry_Upper`, `Pickup_One`, `Putdown_One`, `Pickup_Package` or `Putdown_Package` (the engineer, 2026-11-24:
  skipped in M8). The game plays the base clip instead: the character holds an item with no arm pose of its own.
- The locomotion clips cover their own speeds at rate 1.0 (the table below), not the game's assumed ones.

## What to copy where

| From (this folder) | To (prime-game) | Bytes |
|---|---|---|
{look_files}

The GLB through LFS with its `.import` committed (prime-game `docs/ARCHITECTURE.md` 11.1 and 11.2); the mask keeps
the shipped `.import` (lossless, mipmaps, never VRAM-compressed: it is data, not colour, docs/godot.md "The colour
slots' masks"); the scripts and shaders as they are (their preloads are relative to `look/`). `package.json` lists
every file with its SHA-256; the credit draft is manifest.toml's `credit` (`public_repo_ok = true`,
`ai_generated = true`).

## Import settings (Godot 4.7.2)

- `animation/fps = 24` (the clips' key rate);
- the AnimationPlayer node's `optimizer/enabled = false`;
- clips named `*_Loop` import looping (LINEAR) without the suffix: the game sees the Godot names below.

## The look

The GLB's own materials are a fallback. The approved look is `look/alien_static.gdshader` on both surfaces:

```gdscript
const AlienDress = preload("res://{pkg['game_dir']}/look/alien_dress.gd")
var mats := AlienDress.dress_from(model, "res://{pkg['game_dir']}/look/{asset_id}_look.json")
AlienDress.AlienStatic.set_skin(mats, Color("e98a8c"))  # optional: a player's skin colour (sRGB)
```

`dress_from` swaps the materials of `*_static_skin` (the head) and `*_body_skin` (the body) for ShaderMaterials with
the look file's inputs (the base skin, the mask, the constant detail maps and the shader's levers, exactly as the
review page's shots). Without a pick the skin is the build's own teal.

## Sizes

- GLB {glb_bytes / 1e6:.2f} MB: one mesh of 2 surfaces on one skeleton of 59 bones, 6 embedded images (2048 px at most);
- in place: no root motion; the game moves the body (play a move clip at speed / its `speed_m_s`).

## The game's bones on this skeleton

The game is wired to slice_m1's Ultimate Modular names (prime-game `character_set.gd` `NEEDED_BONES`,
`character_rig.gd` `CARRY_ROOT`); this skeleton has the contract's names, matched by the humanoid profile (the
ragdoll's table: the rig's `Torso` is the `Chest` profile, its `Chest` the `UpperChest`):

| slice_m1 | {asset_id} |
|---|---|
{bones}

So `NEEDED_BONES` becomes `Hips, Chest, UpperChest, RightHand` and `CARRY_ROOT` `Chest`.

## Sockets

The game's three sockets (`character_rig.gd` `SOCKETS`), each a point in its bone's frame
(`tools/runner/commands/_alien_package.py` `sockets`): Belt and Carry are slice_m1's points (measured in #1050) carried
onto this body by its proportions; Hand is this body's own, in its relaxed idle hand (it has no grip pose: the item
stands in the curled fingers, not in a closed fist):

| Socket | Bone | Point | Fitted carrying | How |
|---|---|---|---|---|
{sock}

There is no `Carry_Upper`, so the Carry socket cannot be fitted on the carry pose: fit it on the Idle (the art's
proof does) or skip the carry layer.

## Clips

The clips the game plays ({len(game_rows)} of its 8 base clips are here):

| Godot name | Set name | Loop | s | m/s at rate 1 | Serves |
|---|---|---|---|---|---|
{chr(10).join(_row(r) for r in game_rows)}

Beside them (not played by the game yet):

| Godot name | Set name | Loop | s | m/s at rate 1 | Serves |
|---|---|---|---|---|---|
{chr(10).join(_row(r) for r in extra)}

The speeds are measured on the GLB (the median speed of a foot's ball while it stands). The game's `AvatarClips`
assumes 4.5 m/s for the jog, back and strafes, 7.0 for the sprint and 0.75 for the crouch: with these clips the
strafes and the back jog would slide unless the game divides by their own speeds.

Dropped from the source GLB: {len(dropped)} review variants (`{'`, `'.join(dropped)}`).

## Ragdoll (art #115)

Written by `tools/run.py ragdoll --asset`.
"""


def build(args: argparse.Namespace) -> int:
    glb = args.glb.resolve()
    if not glb.is_file():
        raise common.Failure(f"no GLB {args.glb.as_posix()}")
    if not args.name or not args.id:
        raise common.Failure("--name and --id are needed to build the package")
    asset = args.asset.resolve()
    export = asset / "export"
    if export.exists():
        shutil.rmtree(export)
    export.mkdir(parents=True)
    gltf, blob = _ragdoll.read_glb(glb)
    g2, b2, dropped = P.clean(gltf, blob)
    target = export / f"{args.id}.glb"
    target.write_bytes(P.glb_bytes(g2, b2))
    common.ok(f"{target.name}: {len(g2.get('animations', []))} clips kept, {len(dropped)} review clips dropped, "
              f"{target.stat().st_size / 1e6:.2f} MB")
    rows = P.clip_rows(g2, b2)
    names = {r["godot_name"] for r in rows}
    base = [c for c in P.GAME_CLIPS if c in names]
    lacking = [c for c in P.GAME_CLIPS if c not in names]
    if lacking:
        raise common.Failure(f"the game's base clips {', '.join(lacking)} are missing")
    look, mask = look_inputs(glb, args.name)
    write_look(export / "look", args.id, look, mask)
    common.ok(f"look/: {', '.join(LOOK_FILES)}, {args.id}_look.json, {args.id}_mask.png (+ .import)")
    data = _ragdoll.measure(target, args.id)
    skel = _ragdoll.skeleton(g2)
    problems = _ragdoll.check(data, skel["names"]) + _ragdoll.shapes_in_bounds(data, skel["global"])
    for p in problems:
        common.bad(f"ragdoll data: {p}")
    if problems:
        return 1
    _ragdoll.write(data, export / f"{args.id}.ragdoll.json")  # listed and copied with the rest
    slice_glb = args.slice if args.slice.is_file() else common.ROOT / args.slice
    pkg = {"asset": args.id, "game_dir": f"assets/characters/{args.id}", "files": files_list(asset),
           "game": {"clips": base, "missing_clips": list(P.MISSING), "bones": P.GAME_BONES},
           "sockets": P.sockets((g2, b2), _ragdoll.read_glb(slice_glb)), "heights": P.heights(g2, b2),
           "clip_rows": rows}
    (asset / "package.json").write_text(json.dumps(pkg, indent=1) + "\n", encoding="utf-8", newline="\n")
    (asset / "HANDOFF.md").write_text(handoff(args.id, pkg, target.stat().st_size, dropped), encoding="utf-8",
                                      newline="\n")
    ragdoll.put_in_asset(asset, data)  # the same file again, and HANDOFF.md's ragdoll section
    common.ok(f"package.json, HANDOFF.md, {args.id}.ragdoll.json ({len(data['bones'])} bodies, rig {data.get('rig', 'um')})")
    h = pkg["heights"]
    common.say(f"heights: top {h['top_m']} m, eyes {h['eyes_m']} m; sockets: "
               + "; ".join(f"{n} on {v['bone']} {v['point']}" for n, v in pkg["sockets"].items()))
    return 0


def check(asset: Path, out: Path, compare: Path | None) -> int:
    """Stages the asset's export/ and package.json as res://import/pkg_<id>/ and runs package_check.gd off-screen."""
    pkg = json.loads((asset / "package.json").read_text(encoding="utf-8"))
    asset_id = pkg["asset"]
    stage = _godot.IMPORT_DIR / f"pkg_{asset_id}"
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(asset / "export", stage)
    shutil.copyfile(asset / "package.json", stage / "package.json")
    glb = stage / f"{asset_id}.glb"
    (stage / f"{glb.name}.import").write_text(
        _godot.import_file({**_godot.IMPORT_PARAMS, "animation/fps": 24}, _godot.subresources()), encoding="utf-8",
        newline="\n")
    _godot.clear_staged(set())
    lines = _godot.import_project()
    for line in lines:
        common.warn(f"godot import: {line}")
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    job = {"dir": f"res://import/pkg_{asset_id}", "id": asset_id, "out": out.as_posix(),
           "compare": compare.resolve().as_posix() if compare else ""}
    job_path = out / "job.json"
    job_path.write_text(json.dumps(job, indent=1), encoding="utf-8")
    code, output = _godot.window(["--audio-driver", "Dummy", "--path", _godot.PROJECT, "-s", "res://alien/package_check.gd",
                                  "--", job_path.as_posix()], (1280, 720), TIMEOUT, log=out / "godot.log")
    (out / "godot.log").write_text(output, encoding="utf-8")
    for line in output.splitlines():
        if line.startswith("PKG"):
            (common.ok if line == "PKG ok" else common.bad)(line)
    for line in _godot.noteworthy(output):
        common.warn(f"godot: {line}")
    report_path = out / "report.json"
    if not report_path.is_file():
        raise common.Failure(f"package_check.gd wrote no report (exit {code}): see {(out / 'godot.log').as_posix()}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if "compare" in report:
        common.say(f"turnaround against the review page: {report['compare']}")
    return 0 if code == 0 and not report["failures"] else 1


def run(args: argparse.Namespace) -> int:
    code = 0
    if args.glb:
        code = build(args)
    if code == 0 and args.check:
        code = check(args.asset.resolve(), args.check, args.compare)
    return code
