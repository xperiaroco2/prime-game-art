"""`slice`: the game's slice character (art #42 part C; docs/godot.md, "The slice character"). One cast character in
the clay look with the face kit and its baked textures, carrying an animation set's clips for its body type minus the
settings' `exclude`: assemble, put the clips on (tools/blender/slice_actions.py), `export --textured`, `godot-check
--strict-contract --humanoid --textured`, `frames` of the review clips, an eight-view turnaround, and the asset folder
(the GLB, manifest.toml with per-clip provenance, package.json, HANDOFF.md)."""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from .. import blender, common, pins
from . import _anim, _anim_set, _godot, _slice, export

NAME = "slice"
HELP = "build the slice character: a clay cast member with the animation set's clips, exported, checked, its asset folder"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--settings", type=Path, default=_slice.SETTINGS, help="default recipes/slice_character.toml")
    parser.add_argument("--cast", help="the cast id (default: the settings' cast)")
    parser.add_argument("--anim-set", type=Path,
                        help="the set's build folder holding <body>/<stem>_<body>.blend (default <raw>/anim-sets/<set>)")
    parser.add_argument("--blend", type=Path, help="a saved character to use instead of assembling one")
    parser.add_argument("--out", type=Path, help="work folder (default tools/out/slice/<cast>/)")
    parser.add_argument("--asset", type=Path, help="also write the asset folder here (assets/character/slice_<cast>)")
    parser.add_argument("--review", type=Path, help="copy the review sheets here")
    parser.add_argument("--no-frames", action="store_true", help="skip frames and the turnaround")


def _runner(*args: str) -> int:
    """Runs another runner command in its own process (its output goes to this one's)."""
    cmd = [sys.executable, str(common.ROOT / "tools" / "run.py"), *args]
    common.say("$ " + " ".join(cmd[2:]))
    return subprocess.run(cmd, cwd=common.ROOT).returncode


def _load_dir(folder: Path) -> dict[str, dict]:
    out = {}
    for path in sorted(folder.glob("*.toml")):
        with open(path, "rb") as fh:
            out[path.stem] = tomllib.load(fh)
    return out


def _generations(raw: Path, tm_files: dict[str, str]) -> dict[str, dict]:
    out = {}
    for clip, rel in tm_files.items():
        gen = raw / Path(rel).parent / "generation.json"
        if gen.is_file():
            out[clip] = json.loads(gen.read_text(encoding="utf-8"))
    return out


def _raw_files(raw: Path, recipe: dict, char: dict, rows: list[dict], anim_glb: Path) -> list[tuple[str, str]]:
    """The raw files the character is made from: the cast's pack files, the set's GLB, the Meshy clips' FBX."""
    pack = recipe["packs"][char["gender"]]
    files = {f"{pack}/{recipe['skeleton'][char['gender']]}"}
    for slot in char.values():
        if isinstance(slot, dict) and isinstance(slot.get("file"), str):
            files.add(f"{pack}/{slot['file']}")
    files.add(anim_glb.relative_to(raw).as_posix())
    files |= {r["raw"] for r in rows if r.get("raw")}
    return [(f, _slice.sha256(raw / f)) for f in sorted(files) if (raw / f).is_file()]


def _body_credit(gender: str) -> str:
    """The credit of the Ultimate Modular pack the cast member's body comes from (its source record)."""
    with open(common.ROOT / "sources" / f"{_slice.PACK_RECORDS[gender]}.toml", "rb") as fh:
        return _slice.source_credit(tomllib.load(fh))


def known_deviations(found: list[str]) -> str:
    """HANDOFF.md's section on the contract checks the export does not pass (the open height decision, #42)."""
    if not found:
        return "None: `godot-check --strict-contract --humanoid --textured` passes every check."
    lines = "\n".join(f"- {d}" for d in found)
    return f"""`godot-check --strict-contract --humanoid --textured` passes every check but these
(the contract v1 body gates):

{lines}

The clay look's head is 1.3 times the pack's, with hair on top, so the body is taller than the contract's 1.70 to
1.80 m and the eyes sit above the camera's 1.6 m. **Open: the engineer decides** (art PR #139, docs/godot.md "Open: the
height"): widen the contract's window for the clay look (a contract change), scale the export, or let the game scale
the body. Do not import before the decision; this section is rewritten with it."""


def handoff(asset_id: str, cast: str, rows: list[dict], left: list[tuple[str, str]], glb: Path, info: dict,
            textures: dict, found: list[str]) -> str:
    mb = glb.stat().st_size / 1e6
    tex = textures.get("images", [])
    return f"""# {asset_id}: handoff to the game (art #42 part C)

The slice character for M6.2: cast `{cast}` in the clay look with the clay face kit, the textures baked and embedded,
carrying {len(rows)} clips of the MVP animation set on the same skeleton. **Not approved yet**: the game takes it once
manifest.toml's approval fields are set (the engineer approves the look on the review page).

## Known deviations

{known_deviations(found)}

## What to copy where

| From (this folder) | To (prime-game) | Size | LFS |
|---|---|---|---|
| `export/{glb.name}` | `{_slice.game_dir(asset_id)}/{glb.name}` | {mb:.2f} MB | yes (one object) |

The path is prime-game's `docs/ARCHITECTURE.md` section 11.1 (`assets/characters/<id>/<id>.glb`, `<id>` the manifest's
`id`); the PR shape is its section 11.2: the GLB through LFS, its `.import` committed, `docs/credits/{asset_id}.md`
and `tools/run.sh credits`. `package.json` lists the file with its SHA-256; the credit draft is the manifest's
`credit` (`public_repo_ok = true`, `ai_generated = true`) and the per-clip table below (the Meshy clips are owned
output of the Pro plan, `ai_generated = true`).

**The game's import check.** `tools/assets/asset_contract.json` (section 11.3) still lists `Knockdown`, `Crawl` and
`Getup_Fours`, the slice's provisional list; this GLB leaves them out on purpose (the knockdown is a ragdoll,
prime-game#522 and art #115). The import PR edits the contract's clip list to the clips below that the avatar maps.

One GLB holds the body and the clips: the contract (docs/contract.md, "Animation") wants one shared library on the
contract skeleton, and the slice has one body, so the clips ride with it; the game can save the AnimationPlayer's
library as a `.res` and share it once a second body arrives.

## Import settings (Godot 4.7.2)

- `animation/fps = 30` (the set's rate; at another rate Godot resamples the clips);
- the AnimationPlayer node's `optimizer/enabled = false` (with the optimizer the joints drift up to 17 mm);
- clips named `*_Loop` import looping (LINEAR) without the suffix: the game sees the Godot names below.

## Sizes

- GLB {mb:.2f} MB, {len(info.get('parts', {}))} parts on one skeleton of {len(info.get('bones', []))} bones,
  {len(tex)} embedded images ({sum(i.get('bytes', 0) for i in tex) / 1e6:.2f} MB), height {info.get('height_m', '?')} m;
- in place: no root motion; the game moves the body (the locomotion clips' `speed_m_s` is the ground speed at rate
  1.0: play at speed / speed_m_s).

## Clips

{_slice.clip_table(rows)}

Upper-body layers (`layer = upper`: carry, push, talk, knife) export every bone; the game masks them with the bone
filter `Torso` and every bone below it, over the idle or the locomotion (carry idle = Idle + Carry_Upper; carry walk =
Jog_Fwd + Carry_Upper).

## Left off

{chr(10).join(f'- `{n}`: {why}' for n, why in left)}
"""


def run(args: argparse.Namespace) -> int:
    settings = _slice.load_settings(args.settings)
    cfg = _anim.load_config()
    set_path, set_data = _anim_set.load(cfg, settings["set"])
    errors = _slice.check_settings(settings, set_data)
    for e in errors:
        common.bad(f"settings: {e}")
    if errors:
        return 1
    cast = args.cast or settings["cast"]
    recipe_path = common.ROOT / "recipes" / f"{settings['recipe']}.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    char = next((c for c in recipe["characters"] if c["id"] == cast), None)
    if char is None:
        common.bad(f"{settings['recipe']} has no cast member {cast!r}")
        return 1
    body = {"M": "men", "W": "women"}[char["gender"]]
    raw = common.raw_dir()
    out = (args.out or common.ROOT / "tools" / "out" / "slice" / cast).resolve()
    asset_id = f"slice_{cast}"

    kept, left = _slice.selection(set_data, settings.get("exclude", {}))
    tm_files = cfg["libraries"]["tm"]["clips"]
    rows = _slice.clip_rows(set_data, kept, body, _load_dir(_slice.SOURCES), _load_dir(_slice.BATCHES), tm_files,
                            _generations(raw, tm_files))
    rows, private = _slice.split_public(rows)
    left += private
    common.say(f"slice {asset_id}: {len(rows)} clips of {set_path.name} on {body}; left off {len(left)}")

    anim_dir = (args.anim_set or raw / "anim-sets" / settings["set"]) / body
    stem = f"{set_data.get('stem', 'set')}_{body}"
    anim_blend, anim_glb = anim_dir / f"{stem}.blend", anim_dir / f"{stem}.glb"
    if not anim_blend.is_file():
        common.bad(f"no {anim_blend}", f"tools/run.py anim-set --set {settings['set']} --body {body} --out <dir>")
        return 1

    blend = args.blend
    if blend is None:
        if _runner("assemble", settings["recipe"], "--ids", cast, "--look", "clay", "--bake", "--blend", "--modes",
                   "none", "--out", str(out / "assemble")):
            return 1
        blend = out / "assemble" / "blend" / f"{cast}.blend"
    sliced = out / "blend" / f"{asset_id}.blend"
    blender.run_script("slice_actions.py", ["--character", str(blend), "--anim", str(anim_blend), "--clips",
                                            ",".join(r["name"] for r in rows), "--out", str(sliced), "--json",
                                            str(out / "blend" / f"{asset_id}.actions.json")], timeout=900)
    common.ok(f"{len(rows)} clips on {sliced}")
    exp = out / "export"
    if not export.export_one(sliced, exp, textured=True):
        return 1
    glb = exp / f"{asset_id}.glb"
    failed = bool(_runner("godot-check", str(glb), "--strict-contract", "--humanoid", "--textured", "--out",
                          str(out / "godot-check")))
    sheets = []
    if not args.no_frames:
        names = ",".join(_godot.godot_name(n)[0] for n in settings.get("review_clips", []))
        failed |= bool(_runner("frames", str(glb), "--clips", names, "--compare", names, "--out", str(out / "frames")))
        sheets += sorted((out / "frames" / "sheets").glob("*.png"))
        failed |= bool(_runner("render", str(glb), "--pose", kept[0], "--cell", "320", "--out", str(out / "turnaround")))
        sheets += sorted((out / "turnaround").glob("*.png"))
    if args.review and sheets:
        args.review.mkdir(parents=True, exist_ok=True)
        for s in sheets:
            shutil.copy2(s, args.review / f"{s.parent.name}_{s.name}")
        common.ok(f"{len(sheets)} review images -> {args.review}")

    info = json.loads((exp / f"{asset_id}.export.json").read_text(encoding="utf-8"))
    tex_path = exp / f"{asset_id}.textures.json"
    textures = json.loads(tex_path.read_text(encoding="utf-8")) if tex_path.is_file() else {}
    fps = info.get("fps", 30)
    lengths = {n: round((r[1] - r[0]) / fps, 3) for n, r in info.get("actions", {}).items() if isinstance(r, list)}
    for r in rows:
        if r["name"] in lengths:
            r["seconds"] = lengths[r["name"]]
    (out / "clips.json").write_text(json.dumps({"rows": rows, "left": left}, indent=1), encoding="utf-8")
    check_report = out / "godot-check" / asset_id / "report.json"
    found = (_slice.deviations(json.loads(check_report.read_text(encoding="utf-8")).get("checks", []))
             if check_report.is_file() else ["`godot-check` did not write its report"])
    if args.asset:
        asset = args.asset.resolve()
        (asset / "export").mkdir(parents=True, exist_ok=True)
        shipped = asset / "export" / glb.name
        shutil.copy2(glb, shipped)
        tools = [f"blender {pins.BLENDER}",
                 "prime-game-art assemble (clay look, bake, face kit), anim-set, slice", "Godot 4.7.2 (checks)"]
        text = _slice.manifest_toml(asset_id, cast, settings["recipe"], rows, _raw_files(raw, recipe, char, rows,
                                    anim_glb), tools, datetime.date.today().isoformat(), left,
                                    (_body_credit(char["gender"]),))
        (asset / "manifest.toml").write_text(text, encoding="utf-8", newline="\n")
        pkg = _slice.package_json(asset_id, {glb.name: shipped}, _slice.game_dir(asset_id))
        (asset / "package.json").write_text(json.dumps(pkg, indent=1) + "\n", encoding="utf-8", newline="\n")
        (asset / "HANDOFF.md").write_text(handoff(asset_id, cast, rows, left, shipped, info, textures, found),
                                          encoding="utf-8", newline="\n")
        common.ok(f"asset folder {asset}")
    return 1 if failed else 0
