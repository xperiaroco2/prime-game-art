"""Helpers for the frames command (docs/godot.md): which times of each animation a sheet shows, the spec
godot/frames/frames.gd reads, and the joint comparison between Godot's and Blender's poses. Pure standard library."""

from __future__ import annotations

from typing import Any

from .. import common

OUT = common.OUT / "frames"
SCRIPT = "res://frames/frames.gd"
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


def cycle(length: float, short: str, seam: dict[str, float] | None = None, fps: int = FPS,
          loop: bool | None = None) -> dict[str, Any]:
    """How a clip plays: a closed loop's last frame repeats its first, so one cycle is frames 0 to last - 1; an open
    loop's cycle is frames 0 to last, and the first comes round again one frame after the last (the pack's Run is
    0.83 s, not the 0.79 s of its keys); a one-off runs from its first frame to its last."""
    last = round(length * fps)
    loop = is_loop(short) if loop is None else loop
    open_cycle = loop and is_open(seam)
    frames = last + 1 if open_cycle or not loop else last
    if not loop:
        note = f"first to last frame, {length:.2f} s"
    else:
        note = f"one loop of {frames / fps:.2f} s" + (", its last key is not its first" if open_cycle else "")
    return {"loop": loop, "open_cycle": open_cycle, "cycle_s": round(frames / fps, 6) if loop else None,
            "video_frames": frames, "note": note}


def times(length: float, short: str, fps: int = FPS, open_cycle: bool = False, loop: bool | None = None) -> list[float]:
    """Evenly spaced sample times on whole frames (where the export's samples are exact): 12 for locomotion, else 8.
    A loop is cut into equal parts of its cycle (one frame longer than its keys when open_cycle); a one-off runs from
    its first frame to its last."""
    n = 12 if is_locomotion(short) else 8
    frames = round(length * fps) + (1 if open_cycle else 0)
    steps = n if (is_loop(short) if loop is None else loop) else n - 1
    return [round(round(i * frames / steps) / fps, 6) for i in range(n)]


def spec(character: str, animations: dict[str, float], compare: list[str], video: list[str],
         seams: dict[str, dict[str, float]] | None = None, fps: int = FPS,
         loops: set[str] | None = None, yaw_deg: float = YAW_DEG) -> dict[str, Any]:
    """The spec frames.gd reads: every animation (name -> length in seconds), sorted by name; seams from export.json;
    fps the export's (whole frames of a 30 fps animation set, art #33); `loops` the animations Godot loops because
    of their name (an animation set's _Loop clips), beside the pack's idles and locomotion. yaw_deg the clip sheets'
    camera (0 the front, 90 the character's left side, -90 its right, 180 its back); the studio light turns with it
    (light_turn_deg), so every view is lit as the three-quarter view is (art #196: a turnaround in Godot's look)."""
    clips = []
    for name in sorted(animations):
        short = label(name)
        loop = True if loops and name in loops else None
        how = cycle(animations[name], short, (seams or {}).get(name), fps, loop)
        clips.append({"name": name, "label": short, **how,
                      "times": times(animations[name], short, fps, open_cycle=how["open_cycle"], loop=how["loop"]),
                      "keep": short in compare, "video": short in video})
    return {"character": character, "cell": list(CELL), "yaw_deg": float(yaw_deg), "pitch_deg": PITCH_DEG,
            "light_turn_deg": float(yaw_deg) - YAW_DEG, "fps": fps, "clips": clips}


FACE_YAWS = (0.0, -YAW_DEG)  # the face close-up: front and three-quarter from the right, as the faces sheets
FACE_CELL = (316, 395)  # four cells (two approved, two Godot) make a sheet about 1284 px wide


def parse_rects(text: str) -> list[list[int]]:
    """'x,y,w,h;x,y,w,h' (pixels of the approved sheet) -> [[x, y, w, h], ...]; each a positive size."""
    rects = []
    for part in (p.strip() for p in text.split(";")):
        if not part:
            continue
        nums = [int(v) for v in part.split(",")]
        if len(nums) != 4 or nums[0] < 0 or nums[1] < 0 or nums[2] <= 0 or nums[3] <= 0:
            raise ValueError(f"not a rectangle x,y,w,h: {part!r}")
        rects.append(nums)
    return rects


def face_spec(character: str, clip: str, beside: str = "", rects: list[list[int]] | None = None,
              t: float = 0.0) -> dict[str, Any]:
    """The spec's `face` entry: Godot's close-ups of the head (FACE_YAWS) at time t of one animation, after the
    approved sheet's crops (`beside`, `rects`) when given, in one sheet `sheets/face.png`."""
    if beside and not rects:
        raise ValueError("an approved sheet needs its crop rectangles")
    title = f"{character}   face close-up at {label(clip)} {t:.2f} s"
    if beside:
        title += f"   left {len(rects or [])}: the approved sheet, right {len(FACE_YAWS)}: Godot"
    return {"clip": clip, "t": t, "yaws": list(FACE_YAWS), "pitch_deg": 0.0, "cell": list(FACE_CELL),
            "beside": beside, "beside_rects": (rects or []) if beside else [], "title": title}


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
