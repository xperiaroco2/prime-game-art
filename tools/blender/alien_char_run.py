"""The pilot heads on the shared alien body (art #196, step B1): builds each character in headless Blender
(alien_char_build.py), checks it with glTF-Validator, shoots the proof in an off-screen Godot window
(godot/alien/char_shots.gd through the runner's _godot.window()) and encodes the videos with Blender's FFmpeg.
godot-check runs separately (`tools/run.sh godot-check --strict-contract --humanoid --textured <glb>`).

    $PYTHON_BIN tools/blender/alien_char_run.py [--heads chameleon,axolotl] [--tag body_v1] [--no-build]
        [--no-shots] [--seconds 20] [--clip-edits tools/blender/anim_sets/alien.toml]

Into <raw>/research/2026-10-22-roster/design/pilot3d/<tag>/<head>/ (the build) and <tag>/ (the sheets, the gate,
the seams, the line-up, char_<head>.mp4). A run never overwrites: a build whose head folder exists is refused, and
shots whose `shots.json` exists. Long: run it in the background.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from runner import blender, common  # noqa: E402
from runner.commands import _export, _godot  # noqa: E402
import alien_colour_slots as CS  # noqa: E402

RAW = common.raw_dir()
PILOT = RAW / "research" / "2026-10-22-roster" / "design" / "pilot3d"
BODY = RAW / "review" / "char" / "alien-parts-kit" / "S4b" / "build" / "alien_body.blend"  # the shared body (S4b)
# B4: the merged colour slots' newest proof (CS6b, PR #312; v7): its maps (the masks as v4 made them, byte for byte),
# its region medians (<head>_regions.json: the slots' bases and the body's paint) and its shader params
SLOTS = CS.OUT
REGIONS = SLOTS / "maps"
FIX = {"shadow_quality": 5}  # B3/B4: the soft shadow filter at ultra by default (soft low draws a knit pattern)
HDRI = RAW / "env" / "polyhaven" / "studio_small_09" / "studio_small_09_2k.hdr"  # CC0, sources/polyhaven_hdris_2k.toml
LINEUP = RAW / "research" / "2026-10-22-roster" / "design" / "final"
# the merged lively builds (PR #302 chameleon v6, PR #306 axolotl v6a, the default gill lift)
HEADS = {"chameleon": {"lively": PILOT / "lively" / "v6", "sheet": "m01-chameleon.jpg", "preset": 4},
         "axolotl": {"lively": PILOT / "lively" / "axolotl_v6a", "sheet": "w01-axolotl.jpg", "preset": 1}}


def refusal(out: Path, heads: list[str], build: bool, shots: bool) -> str | None:
    """Why a run must not start (a run never overwrites in the raw folder), or None."""
    for h in heads if build else []:
        if (out / h / f"{h}_char.glb").exists():
            return f"{out / h} holds a build: pick a new --tag"
    if shots and (out / "shots.json").exists():
        return f"{out / 'shots.json'} exists: pick a new --tag"
    return None


def bases(head: str) -> dict:
    """The slots' bases wholesale as the colour slots proof takes them (`alien_colour_slots.bases`: every region's
    median, gill_tips and gill_whole included), and the body's paint (body_skin, body_front): the same skin and front
    medians, so the body is a typical head skin texel to the slots' recolour. The neck still shows a step where the
    head's own paint differs from its median: the chameleon's cobalt back under a pick (r5)."""
    out = CS.bases(CS.BUILD, REGIONS, head)
    out["body_skin"], out["body_front"] = out["skin"], out["front"]
    return out


def eye_mask(lv: Path, static: Path, h: str) -> Path:
    """The eye mask that goes with the lively build lv: its own when it wrote one (lively.json "mask", the rim cut's
    repainted mask, art #196 R2), else the static head's."""
    name = json.loads((lv / "lively.json").read_text(encoding="utf-8")).get("mask")
    return lv / name if name else static / f"{h}_mask.png"


def head_job(h: str, hd: Path, b: dict, slots_job: dict) -> dict:
    """One head's entry in a Godot job (char_shots.gd, clip_reels.gd): its built character in hd, staged; the eye
    mask and sclera from the character's own lively build (char.json "lively", R2); the uncut static v5 head of the
    whole-head gate keeps its own mask ("static_mask")."""
    static = PILOT / "static_v5" / h
    char = json.loads((hd / "char.json").read_text(encoding="utf-8"))
    lv = Path(char["lively"]).parent
    return {
        "char": _godot.stage(hd / f"{h}_char.glb", f"char_{h}"),
        "static": _godot.stage(static / f"{h}_static.glb", f"static_{h}"),
        "lively": str(hd / f"{h}_char_lively.json"), "sclera": str(lv / f"{h}_sclera.png"),
        "mask": str(eye_mask(lv, static, h)), "static_mask": str(static / f"{h}_mask.png"),
        "detail": str(static / f"{h}_detail.png"),
        "plain": str(static / f"{h}_albedo_plain.png"), "accent": str(SLOTS / "maps" / f"{h}_accent.png"),
        "gill": str(SLOTS / "maps" / f"{h}_gill.png"), "body_albedo": str(hd / f"{h}_body_albedo.png"),
        "body_mask": str(hd / f"{h}_body_mask.png"), "body_detail": str(hd / f"{h}_body_detail.png"),
        "body_accent": str(hd / f"{h}_body_accent.png"), "bases": b, "params": slots_job[h]["params"],
        "fit": char["fit"], "cut_z": char["fit"]["dst"][2], "band": char["neck_band"],
        "sheet2d": str(LINEUP / HEADS[h]["sheet"]), "preset": HEADS[h]["preset"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heads", default="chameleon,axolotl")
    ap.add_argument("--tag", default="body_v1")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--clip-edits", default="", help="A1: the alien's clip edits, e.g. tools/blender/anim_sets/alien.toml")
    ap.add_argument("--shots-sub", default="", help="B3: the shots into this subfolder of the tag (a trial)")
    ap.add_argument("--fix", default="{}", help="B3: JSON render settings after the front isolation sheet "
                    "(shadow_quality 0-5, default 5; taa, angular_deg, sss_scale)")
    args = ap.parse_args()
    heads = args.heads.split(",")
    out = PILOT / args.tag
    shots_out = out / args.shots_sub if args.shots_sub else out
    why = refusal(out, heads, not args.no_build, False) or refusal(shots_out, [], False, not args.no_shots)
    if why:
        print(why, flush=True)
        return 2
    ok = True
    slots_job = json.loads((SLOTS / "job.json").read_text(encoding="utf-8"))["heads"]
    job = {"hdri": str(HDRI), "seconds": args.seconds, "out": str(shots_out), "fix": {**FIX, **json.loads(args.fix)}, "heads": {}}
    for h in heads:
        hd = out / h
        static = PILOT / "static_v5" / h
        lv = HEADS[h]["lively"]
        b = bases(h)
        if not args.no_build:
            hd.mkdir(parents=True, exist_ok=True)
            (hd / "bases.json").write_text(json.dumps(b, indent=1), encoding="utf-8", newline="\n")
            res = blender.run_script("alien_char_build.py", [
                "--head", h, "--lively", str(lv / f"{h}_lively.glb"), "--lively-json", str(lv / "lively.json"),
                "--body", str(BODY), "--albedo", str(static / f"{h}_albedo.png"), "--mask", str(eye_mask(lv, static, h)),
                "--accent", str(SLOTS / "maps" / f"{h}_accent.png"),
                "--detail", str(static / f"{h}_detail.png"), "--bases", str(hd / "bases.json"),
                "--out", str(hd), *(["--clip-edits", str(Path(args.clip_edits).resolve())] if args.clip_edits else [])],
                timeout=1500)
            (hd / "build.log").write_text((res.stdout or "") + (res.stderr or ""), encoding="utf-8", newline="\n")
            print(*[x for x in (res.stdout or "").splitlines() if x.startswith("CHAR ")], sep="\n", flush=True)
            if res.returncode != 0:
                print(f"build {h}: exit {res.returncode} (see {hd / 'build.log'})", flush=True)
                return 1
        glb = hd / f"{h}_char.glb"
        verdict_ok, text = _export.verdict(_export.validate(glb, hd / f"{h}_char.validator.json"))
        print(f"validator {glb.name}: {text}", flush=True)
        ok &= verdict_ok
        job["heads"][h] = head_job(h, hd, b, slots_job)
    if args.no_shots:
        return 0 if ok else 1
    out = shots_out
    out.mkdir(parents=True, exist_ok=True)
    (out / "job.json").write_text(json.dumps(job, indent=1), encoding="utf-8", newline="\n")
    _godot.import_project()
    code, output = _godot.window(["--path", str(_godot.PROJECT), "-s", "res://alien/char_shots.gd", "--",
                                  str(out / "job.json")], (1280, 720), 1500)
    (out / "godot_shots.log").write_text(output, encoding="utf-8", newline="\n")
    print(f"godot shots: exit {code}", *[x for x in output.splitlines() if "CHAR" in x or "ERROR" in x][-12:],
          sep="\n", flush=True)
    if code != 0:
        return 1
    if args.seconds > 0:
        for h in heads:
            blender.run_script("encode_clips.py", ["--frames", str(out / "video" / f"char_{h}"), "--out", str(out),
                                                   "--fps", "24", "--repeat", "1"], timeout=900)
            clip = out / f"char_{h}.mp4"
            print(f"video {clip} {clip.stat().st_size // 1024 if clip.exists() else 0} KB", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
