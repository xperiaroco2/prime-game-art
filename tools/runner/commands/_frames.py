"""Helpers for the frames command (docs/godot.md): which times of each animation a sheet shows, the spec
godot/frames/frames.gd reads, and the joint comparison between Godot's and Blender's poses. Pure standard library."""

from __future__ import annotations

from typing import Any

from .. import common

OUT = common.OUT / "frames"
SCRIPT = "res://frames/frames.gd"
POSITION = "-30000,-30000"  # off-screen, like the game's tools\run.cmd shot
WINDOW = (480, 600)
CELL = (320, 400)
YAW_DEG = 35.0  # the three-quarter view: from the front, turned toward the character's left (+X)
PITCH_DEG = 8.0
FPS = 24
PREFIX = "CharacterArmature|"
VIDEO = ("Idle", "Walk", "Run", "Wave", "Punch_Right", "Interact")
# Godot and Blender agree on a joint's position within this on a whole frame. With Godot's animation optimizer off
# (_godot.PLAYER_OPTIONS) every joint of every clip agrees within 0.02 mm (the JSON's 0.01 mm rounding); a wrong pose
# (a channel left from another action, a wrong rest, a dropped key) differs by millimetres to decimetres.
JOINT_TOLERANCE_M = 0.001
# A cycle is closed when its last key repeats its first within these (the pack's closed cycles: under 0.05 deg).
SEAM_MM = 0.5
SEAM_DEG = 0.5


def label(name: str) -> str:
    return name[len(PREFIX) :] if name.startswith(PREFIX) else name


def is_locomotion(short: str) -> bool:
    return short.startswith(("Walk", "Run"))


def is_loop(short: str) -> bool:
    """Cycles: the idles and the locomotion."""
    return short.startswith("Idle") or is_locomotion(short)


def is_open(seam: dict[str, float] | None) -> bool:
    """A cycle whose last key does not repeat its first (export.json's seams; unknown counts as closed)."""
    return bool(seam) and (seam["position_mm"] > SEAM_MM or seam["rotation_deg"] > SEAM_DEG)


def cycle(length: float, short: str, seam: dict[str, float] | None = None, fps: int = FPS) -> dict[str, Any]:
    """How a clip plays: a closed loop's last frame repeats its first, so one cycle is frames 0 to last - 1; an open
    loop's cycle is frames 0 to last, and the first comes round again one frame after the last (the pack's Run is
    0.83 s, not the 0.79 s of its keys); a one-off runs from its first frame to its last."""
    last = round(length * fps)
    loop = is_loop(short)
    open_cycle = loop and is_open(seam)
    frames = last + 1 if open_cycle or not loop else last
    if not loop:
        note = f"first to last frame, {length:.2f} s"
    else:
        note = f"one loop of {frames / fps:.2f} s" + (", its last key is not its first" if open_cycle else "")
    return {"loop": loop, "open_cycle": open_cycle, "cycle_s": round(frames / fps, 6) if loop else None,
            "video_frames": frames, "note": note}


def times(length: float, short: str, fps: int = FPS, open_cycle: bool = False) -> list[float]:
    """Evenly spaced sample times on whole frames (where the export's samples are exact): 12 for locomotion, else 8.
    A loop is cut into equal parts of its cycle (one frame longer than its keys when open_cycle); a one-off runs from
    its first frame to its last."""
    n = 12 if is_locomotion(short) else 8
    frames = round(length * fps) + (1 if open_cycle else 0)
    steps = n if is_loop(short) else n - 1
    return [round(round(i * frames / steps) / fps, 6) for i in range(n)]


def spec(character: str, animations: dict[str, float], compare: list[str], video: list[str],
         seams: dict[str, dict[str, float]] | None = None) -> dict[str, Any]:
    """The spec frames.gd reads: every animation (name -> length in seconds), sorted by name; seams from export.json."""
    clips = []
    for name in sorted(animations):
        short = label(name)
        how = cycle(animations[name], short, (seams or {}).get(name))
        clips.append({"name": name, "label": short, **how,
                      "times": times(animations[name], short, open_cycle=how["open_cycle"]),
                      "keep": short in compare, "video": short in video})
    return {"character": character, "cell": list(CELL), "yaw_deg": YAW_DEG, "pitch_deg": PITCH_DEG, "fps": FPS,
            "clips": clips}


def _dist(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def compare_joints(godot: dict[str, Any], blender: dict[str, Any]) -> dict[str, Any]:
    """Per clip: the largest distance between Godot's and Blender's position of any joint or axis point ("<bone>+x",
    "<bone>+y": 10 cm from the joint, turned with the bone, so a leaf bone's rotation counts too) at any of the clip's
    times, which one and when, and the largest per time. godot is frames.json, blender the compare script's joints."""
    out: dict[str, Any] = {}
    for short, frames in blender["joints"].items():
        clip = godot["clips"][short]
        worst, where, per_time = 0.0, "", []
        for i, (g, b) in enumerate(zip(clip["joints"], frames)):
            top = 0.0
            for bone, pos in b.items():
                if bone in g:
                    d = _dist(pos, g[bone])
                    top = max(top, d)
                    if d > worst:
                        worst, where = d, f"{bone} at {clip['times'][i]:.3f} s"
            per_time.append(round(top * 1000, 3))
        missing = sorted(set(frames[0]) - set(clip["joints"][0])) if frames else []
        out[short] = {"max_mm": round(worst * 1000, 3), "where": where, "per_time_mm": per_time,
                      "joints": sum("+" not in k for k in frames[0]) if frames else 0,
                      "axis_points": sum("+" in k for k in frames[0]) if frames else 0, "missing_in_godot": missing,
                      "match": worst <= JOINT_TOLERANCE_M and not missing}
    return out
