"""The alien's game package (art #393), plain Python: the parts of `alien-package` that need no Godot or Blender.

- `clean`: the GLB with its review clips dropped (a `__` in the name: the loco set's variants and alternatives) and
  each kept clip renamed to its set name (`CharacterArmature|Idle_Loop` -> `Idle_Loop`, which Godot imports as `Idle`,
  looping), the binary compacted to what the kept parts use;
- `clip_rows`: per kept clip its length, frame rate, loop and ground speed at rate 1.0, measured from the GLB (forward
  kinematics of the feet: the median horizontal speed of a foot's ball while it stands on its lowest 2 cm);
- `heights`: the top of the skin, the eyes, the Head joint;
- `sockets`: the game's three sockets: Belt and Carry measured on slice_m1 (prime-game `character_rig.gd`, #1050)
  carried onto the alien's bones by its proportions, Hand in the alien's own idle hand (docs/godot.md,
  "The alien's game package").
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any

from . import _ragdoll as R

PREFIX = "CharacterArmature|"
VARIANT = "__"  # the loco set's variants and alternatives (anim_sets/alien_loco.toml)
GROUND_BAND_M = 0.02  # a foot stands while its ball is within this of its lowest in the clip
# The game's sockets on slice_m1 (prime-game client/player/character/character_rig.gd SOCKETS, #1050): name ->
# (slice bone, point in the bone's frame, fitted carrying).
SLICE_SOCKETS = {
    "Hand": ("Wrist.R", (0.0, 0.125, 0.0), False),
    "Belt": ("Hips", (0.19, 0.065, -0.06), False),
    "Carry": ("Chest", (0.015, -0.265, 0.525), True),
}
# Each socket's bone on the contract skeleton, by the humanoid profile (the ragdoll's table, _ragdoll._TRUNK: the
# rig's Torso is the Chest profile, its Chest the UpperChest).
ALIEN_BONES = {"Hand": "RightHand", "Belt": "Hips", "Carry": "UpperChest"}
# The game's bones (prime-game character_set.gd NEEDED_BONES, character_rig.gd CARRY_ROOT) on the contract skeleton.
GAME_BONES = {"Hips": "Hips", "Torso": "Chest", "Chest": "UpperChest", "Wrist.R": "RightHand"}
# The game's clips (prime-game client/player/avatar_clips.gd) and what each serves; the natural speed it assumes.
GAME_CLIPS = {
    "Idle": "standing; the base under the talk layer",
    "Jog_Fwd": "move forward (the game assumes 4.5 m/s at rate 1.0)",
    "Jog_Bwd": "move backward (the game assumes 4.5 m/s)",
    "Strafe_Left": "move left (the game assumes 4.5 m/s)",
    "Strafe_Right": "move right (the game assumes 4.5 m/s)",
    "Sprint_Fwd": "sprint forward (the game assumes 7.0 m/s)",
    "Crouch_Idle": "crouch, standing",
    "Crouch_Fwd": "crouch, moving (the game assumes 0.75 m/s)",
}
MISSING = ("Carry_Upper", "Pickup_One", "Putdown_One", "Pickup_Package", "Putdown_Package")
_NUM = {5126: ("f", 4), 5123: ("H", 2), 5125: ("I", 4), 5121: ("B", 1), 5122: ("h", 2), 5120: ("b", 1)}
_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def set_name(name: str) -> str:
    """A clip's set name: the armature prefix dropped."""
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


def kept(name: str) -> bool:
    return VARIANT not in set_name(name)


# ---- the cleaned GLB ------------------------------------------------------------------------------------------------

def clean(gltf: dict[str, Any], blob: bytes) -> tuple[dict[str, Any], bytes, list[str]]:
    """The GLB without its review clips, the kept ones under their set names, the binary compacted (every accessor,
    buffer view and the buffer rewritten to what meshes, skins, images and the kept clips use). Returns the new JSON,
    the new binary and the dropped clip names."""
    g = json.loads(json.dumps(gltf))
    dropped = [set_name(a["name"]) for a in g.get("animations", []) if not kept(a["name"])]
    g["animations"] = [a for a in g.get("animations", []) if kept(a["name"])]
    for a in g["animations"]:
        a["name"] = set_name(a["name"])
    if not g["animations"]:
        del g["animations"]
    for acc in g.get("accessors", []):
        if "sparse" in acc:
            raise ValueError("sparse accessors are not compacted")
    used_acc: list[int] = []

    def use(i: int) -> None:
        if i not in used_acc:
            used_acc.append(i)

    for mesh in g.get("meshes", []):
        for prim in mesh["primitives"]:
            for i in prim["attributes"].values():
                use(i)
            if "indices" in prim:
                use(prim["indices"])
            for target in prim.get("targets", []):
                for i in target.values():
                    use(i)
    for skin in g.get("skins", []):
        if "inverseBindMatrices" in skin:
            use(skin["inverseBindMatrices"])
    for a in g.get("animations", []):
        for s in a["samplers"]:
            use(s["input"])
            use(s["output"])
    acc_map = {old: new for new, old in enumerate(sorted(used_acc))}
    used_views = sorted({g["accessors"][i]["bufferView"] for i in acc_map if "bufferView" in g["accessors"][i]}
                        | {im["bufferView"] for im in g.get("images", []) if "bufferView" in im})
    view_map = {old: new for new, old in enumerate(used_views)}
    out = bytearray()
    views = []
    for old in used_views:
        v = dict(g["bufferViews"][old])
        start = v.get("byteOffset", 0)
        out.extend(b"\0" * (-len(out) % 4))
        v["byteOffset"] = len(out)
        out.extend(blob[start:start + v["byteLength"]])
        views.append(v)
    out.extend(b"\0" * (-len(out) % 4))
    accessors = []
    for old in sorted(acc_map):
        a = dict(g["accessors"][old])
        if "bufferView" in a:
            a["bufferView"] = view_map[a["bufferView"]]
        accessors.append(a)
    g["accessors"], g["bufferViews"] = accessors, views
    if out:
        g["buffers"] = [{"byteLength": len(out)}]
    else:  # glTF wants byteLength >= 1: no buffer at all
        g.pop("buffers", None)
    for mesh in g.get("meshes", []):
        for prim in mesh["primitives"]:
            prim["attributes"] = {k: acc_map[i] for k, i in prim["attributes"].items()}
            if "indices" in prim:
                prim["indices"] = acc_map[prim["indices"]]
            if "targets" in prim:
                prim["targets"] = [{k: acc_map[i] for k, i in t.items()} for t in prim["targets"]]
    for skin in g.get("skins", []):
        if "inverseBindMatrices" in skin:
            skin["inverseBindMatrices"] = acc_map[skin["inverseBindMatrices"]]
    for a in g.get("animations", []):
        for s in a["samplers"]:
            s["input"], s["output"] = acc_map[s["input"]], acc_map[s["output"]]
    for im in g.get("images", []):
        if "bufferView" in im:
            im["bufferView"] = view_map[im["bufferView"]]
    return g, bytes(out), dropped


def glb_bytes(gltf: dict[str, Any], blob: bytes) -> bytes:
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    b = blob + b"\0" * (-len(blob) % 4)
    total = 12 + 8 + len(js) + 8 + len(b)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(b), 0x004E4942) + b)


# ---- clips: forward kinematics of the feet --------------------------------------------------------------------------

def _sample(times: list[float], values: list[tuple[float, ...]], step: bool, t: float,
            rotation: bool) -> tuple[float, ...]:
    """A channel's value at t: LINEAR (rotations normalised lerp) or STEP (the key at or before t)."""
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    lo, hi = 0, len(times) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if times[mid] <= t:
            lo = mid
        else:
            hi = mid
    if step:
        return values[lo]
    u = (t - times[lo]) / ((times[hi] - times[lo]) or 1.0)
    a, b = values[lo], values[hi]
    if rotation and sum(x * y for x, y in zip(a, b)) < 0.0:
        b = tuple(-x for x in b)
    v = tuple(x + (y - x) * u for x, y in zip(a, b))
    if rotation:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        v = tuple(x / n for x in v)
    return v


def _channels(gltf: dict[str, Any], blob: bytes, anim: dict[str, Any]):
    """(node, path) -> (key times, values, STEP?); a CUBICSPLINE sampler is refused (three values a key)."""
    out = {}
    for ch in anim["channels"]:
        s = anim["samplers"][ch["sampler"]]
        mode = s.get("interpolation", "LINEAR")
        if mode not in ("LINEAR", "STEP"):
            raise ValueError(f"{anim.get('name')}: {mode} samplers are not read")
        out[(ch["target"]["node"], ch["target"]["path"])] = (
            [x[0] for x in R.accessor(gltf, blob, s["input"])], R.accessor(gltf, blob, s["output"]), mode == "STEP")
    return out


def _world(gltf: dict[str, Any], chans: dict):
    """bone, t -> the bone's head in skeleton space under the channels (a bone they leave alone at its rest);
    with matrix=True its whole transform."""
    nodes = gltf["nodes"]
    skel = R.skeleton(gltf)
    index = {nodes[j]["name"]: j for j in skel["joints"]}

    def local(j: int, t: float) -> list[list[float]]:
        n = nodes[j]
        tr, ro, sc = chans.get((j, "translation")), chans.get((j, "rotation")), chans.get((j, "scale"))
        return R.mat(_sample(*tr, t, False) if tr else n.get("translation", (0, 0, 0)),
                     _sample(*ro, t, True) if ro else n.get("rotation", (0, 0, 0, 1)),
                     _sample(*sc, t, False) if sc else n.get("scale", (1, 1, 1)))

    def world(bone: str, t: float, matrix: bool = False):
        chain, at = [], bone
        while at is not None:
            chain.append(index[at])
            at = skel["parents"][at]
        m = R.mat()
        for j in reversed(chain):
            m = R.mul(m, local(j, t))
        return m if matrix else R.apply(m, (0.0, 0.0, 0.0))

    return world


def clip_rows(gltf: dict[str, Any], blob: bytes) -> list[dict[str, Any]]:
    """Per clip: set name, Godot name, loop, seconds, fps (its keys' rate) and ground speed (m/s at rate 1.0, None for
    a clip whose feet never travel: an idle, a jump), from the feet's forward kinematics."""
    skel = R.skeleton(gltf)
    rows = []
    for anim in gltf.get("animations", []):
        name = set_name(anim["name"])
        chans = _channels(gltf, blob, anim)
        times: set[float] = set()
        step = math.inf
        for t, *_ in chans.values():
            times.update(t)
            if len(t) > 2:
                step = min(step, min((b - a for a, b in zip(t, t[1:]) if b > a), default=math.inf))
        frames = sorted(times)
        length = frames[-1] if frames else 0.0
        fps = round(1.0 / step) if step < math.inf else None
        godot, loops = name, False
        if name.endswith("_Loop"):
            godot, loops = name[:-5], True
        world = _world(gltf, chans)
        speeds = []
        for ball in ("LeftToes", "RightToes"):
            if ball not in skel["parents"] or len(frames) < 4:
                continue
            pts = [world(ball, t) for t in frames]
            low = min(p[1] for p in pts)
            for k in range(1, len(pts) - 1):
                if pts[k][1] <= low + GROUND_BAND_M:
                    dt = frames[k + 1] - frames[k - 1]
                    speeds.append(math.hypot(pts[k + 1][0] - pts[k - 1][0], pts[k + 1][2] - pts[k - 1][2]) / dt)
        speeds.sort()
        speed = speeds[len(speeds) // 2] if speeds else None
        rows.append({"set_name": name, "godot_name": godot, "loop": loops, "seconds": round(length, 4), "fps": fps,
                     "speed_m_s": round(speed, 2) if speed is not None and speed >= 0.2 else None})
    return rows


# ---- heights and sockets --------------------------------------------------------------------------------------------

def _pos(m: list[list[float]]) -> tuple[float, float, float]:
    return (m[0][3], m[1][3], m[2][3])


def _verts(gltf: dict[str, Any], blob: bytes, skel: dict[str, Any]) -> list[tuple[float, float, float]]:
    return [p for p, _ in R.vertices(gltf, blob, skel)]


def heights(gltf: dict[str, Any], blob: bytes) -> dict[str, float]:
    skel = R.skeleton(gltf)
    verts = _verts(gltf, blob, skel)
    g = skel["global"]
    eyes = [_pos(g[n])[1] for n in ("LeftEye", "RightEye") if n in g]
    return {"top_m": round(max(p[1] for p in verts), 3), "feet_m": round(min(p[1] for p in verts), 3),
            "eyes_m": round(sum(eyes) / len(eyes), 3) if eyes else None, "head_joint_m": round(_pos(g["Head"])[1], 3),
            "hips_joint_m": round(_pos(g["Hips"])[1], 3)}


def _band(verts, y: float, half: float = 0.02):
    return [p for p in verts if abs(p[1] - y) <= half and abs(p[0]) < 0.35]


def _outer_x(verts, y: float) -> float:
    """The trunk's outer left side (+X) at height y: the 98th percentile of x among the vertices near the middle
    (the hanging arms beyond 0.35 m are left out)."""
    xs = sorted(p[0] for p in _band(verts, y))
    return xs[int(0.98 * (len(xs) - 1))]


def _front_z(verts, y: float) -> float:
    """The trunk's front (+Z) at height y, within 0.12 m of the middle (the arms left out)."""
    zs = sorted(p[2] for p in _band(verts, y) if abs(p[0]) < 0.12)
    return zs[int(0.98 * (len(zs) - 1))]


def _mid_z(verts, y: float) -> float:
    zs = sorted(p[2] for p in _band(verts, y) if abs(p[0]) < 0.12)
    return (zs[int(0.02 * (len(zs) - 1))] + zs[int(0.98 * (len(zs) - 1))]) * 0.5


def _unit_scale(m: list[list[float]], what: str) -> None:
    for c in range(3):
        n = math.sqrt(sum(m[r][c] ** 2 for r in range(3)))
        if abs(n - 1.0) > 1e-3:
            raise ValueError(f"{what}: scale {n:.4f}; the sockets need unit-scale bones (rigid inverses)")


def _local(m: list[list[float]], p) -> tuple[float, ...]:
    _unit_scale(m, "a socket's bone")
    inv = R.rigid_inverse(m)
    return tuple(round(x, 4) for x in R.apply(inv, p))


def sockets(alien: tuple[dict, bytes], slice_m1: tuple[dict, bytes]) -> dict[str, dict[str, Any]]:
    """The game's sockets on the alien: each slice socket's point in skeleton space, carried over by the bodies'
    proportions, then written in the alien bone's frame.
    - Hand: the alien's own: the centre of the middle finger's curl on the Idle's first frame, the fitting pose (the
      item's bottom in the relaxed hand; slice_m1's point sits in a closed fist the alien does not make);
    - Belt: the same height over the Hips joint (scaled by the hips' heights), the same distance outside the trunk's
      left side and the same depth against the trunk's middle at that height;
    - Carry: the same height under the upper chest's joint (scaled by the chests' heights) and the same distance in
      front of the trunk's front at that height (the item's size does not scale), the same x."""
    ag, ab = alien
    sg, sb = slice_m1
    ask, ssk = R.skeleton(ag), R.skeleton(sg)
    aglob, sglob = ask["global"], ssk["global"]
    averts, sverts = _verts(ag, ab, ask), _verts(sg, sb, ssk)
    out = {}
    for name, (sbone, point, carrying) in SLICE_SOCKETS.items():
        p = R.apply(sglob[sbone], point)
        if name == "Hand":
            # the alien's idle hand is a relaxed half fist with no grip of its own: the item's bottom goes in the
            # middle finger's curl (its three joints' centre) at the fitting pose, the Idle's first frame
            idle = next(a for a in ag["animations"] if set_name(a["name"]) == "Idle_Loop")
            world = _world(ag, _channels(ag, ab, idle))
            heads = [world(b, 0.0) for b in ("RightMiddleProximal", "RightMiddleIntermediate", "RightMiddleDistal")]
            centre = tuple(sum(h[i] for h in heads) / 3.0 for i in range(3))
            hand = world("RightHand", 0.0, matrix=True)
            _unit_scale(hand, "RightHand at the Idle's first frame")
            q = R.apply(R.mul(aglob["RightHand"], R.rigid_inverse(hand)), centre)
            how = "the middle finger's curl centre at the Idle's first frame (the alien has no grip pose)"
        elif name == "Belt":
            sh, ah = _pos(sglob["Hips"]), _pos(aglob["Hips"])
            s = ah[1] / sh[1]
            y = ah[1] + (p[1] - sh[1]) * s
            dx = p[0] - _outer_x(sverts, p[1])
            dz = p[2] - _mid_z(sverts, p[1])
            q = (_outer_x(averts, y) + dx, y, _mid_z(averts, y) + dz)
            how = f"{dx * 100:+.1f} cm off the trunk's left side, {dz * 100:+.1f} cm against its middle in depth"
        else:
            sc, ac = _pos(sglob["Chest"]), _pos(aglob["UpperChest"])
            s = ac[1] / sc[1]
            y = ac[1] + (p[1] - sc[1]) * s
            dz = p[2] - _front_z(sverts, p[1])
            q = (p[0], y, _front_z(averts, y) + dz)
            how = f"{dz * 100:+.1f} cm in front of the trunk's front"
        bone = ALIEN_BONES[name]
        out[name] = {"bone": bone, "point": list(_local(aglob[bone], q)), "fitted_carrying": carrying,
                     "rest_skeleton_m": [round(x, 4) for x in q], "slice_rest_skeleton_m": [round(x, 4) for x in p],
                     "how": how}
    return out
