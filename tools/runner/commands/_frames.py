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
COMPARE = ("Idle", "Walk", "Wave")
VIDEO = ("Idle", "Walk", "Run", "Wave", "Punch_Right", "Interact")
# Godot and Blender agree on a joint's position within this on a whole frame. With Godot's animation optimizer off
# (_godot.PLAYER_OPTIONS) every joint of every clip agrees within 0.02 mm (the JSON's 0.01 mm rounding); a wrong pose
# (a channel left from another action, a wrong rest, a dropped key) differs by millimetres to decimetres.
JOINT_TOLERANCE_M = 0.001


def label(name: str) -> str:
    return name[len(PREFIX) :] if name.startswith(PREFIX) else name


def is_locomotion(short: str) -> bool:
    return short.startswith(("Walk", "Run"))


def is_loop(short: str) -> bool:
    """Cycles: the idles and the locomotion (their last frame repeats the first)."""
    return short.startswith("Idle") or is_locomotion(short)


def times(length: float, short: str, fps: int = FPS) -> list[float]:
    """Evenly spaced sample times on whole frames (where the export's samples are exact): 12 for locomotion, else 8.
    A loop's last frame repeats its first, so a loop is cut into equal parts; a one-off runs from its first frame to
    its last."""
    n = 12 if is_locomotion(short) else 8
    frames = round(length * fps)
    steps = n if is_loop(short) else n - 1
    return [round(round(i * frames / steps) / fps, 6) for i in range(n)]


def spec(character: str, animations: dict[str, float], compare: list[str], video: list[str]) -> dict[str, Any]:
    """The spec frames.gd reads: every animation (name -> length in seconds), sorted by name."""
    clips = []
    for name in sorted(animations):
        short = label(name)
        clips.append({"name": name, "label": short, "loop": is_loop(short), "times": times(animations[name], short),
                      "keep": short in compare, "video": short in video})
    return {"character": character, "cell": list(CELL), "yaw_deg": YAW_DEG, "pitch_deg": PITCH_DEG, "fps": FPS,
            "clips": clips}


def _dist(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def compare_joints(godot: dict[str, Any], blender: dict[str, Any]) -> dict[str, Any]:
    """Per clip: the largest distance between Godot's and Blender's position of any joint at any of the clip's times,
    which joint and when, and the largest per time. godot is frames.json, blender the compare script's joints."""
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
                      "joints": len(frames[0]) if frames else 0, "missing_in_godot": missing,
                      "match": worst <= JOINT_TOLERANCE_M and not missing}
    return out
