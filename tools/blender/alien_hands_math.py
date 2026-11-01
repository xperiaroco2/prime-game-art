"""The alien's hand shapes in the loco clips (art #196, Hands H1; pure Python, no bpy: tools/blender/alien_hands.py
is the Blender side).

The loco clips carry human mocap finger motion (UAL, text to motion): the fingers claw, splay and differ clip to clip,
and `hands_relax` / `finger_cap_deg` only cap it. Here every clip's finger channels are replaced by ready hand shapes:
the photo poses' grip library (`alien_poses.toml` `[grips]`, `alien_pose_math.grip_quats`) plus this file's own
(`relaxed`, `loose`), one grip per hand or a short set of keyed grips, from `anim_sets/alien_hands.toml`. Only the
finger bones (Thumb, Index, Middle, Ring, Little chains) are keyed; the arms and wrists keep the clip's motion.

The check: per grip and hand, on the character's own rest skeleton and skin (`alien_poses._dump`), how deep any
finger's skin goes into another finger's bones' tubes, into its own proximal tube (the tip folded into the base) and
into the palm's (`alien_pose_math.tube`), and the least gap between neighbouring fingers. The rest pose's numbers are
the measure's floor (the tubes are bounding shapes).
"""
from __future__ import annotations

import fnmatch
import math
import tomllib
from pathlib import Path

import alien_pose_math as A
import anim_edit_math as M

HERE = Path(__file__).resolve().parent
DATA = HERE / "anim_sets" / "alien_hands.toml"
PREFIX = "CharacterArmature|"
DIGITS = ("Thumb", "Index", "Middle", "Ring")  # the alien's four digits (Little: bones kept, unweighted)
CHAINS = {"Thumb": ("Metacarpal", "Proximal", "Distal"), "Index": ("Proximal", "Intermediate", "Distal"),
          "Middle": ("Proximal", "Intermediate", "Distal"), "Ring": ("Proximal", "Intermediate", "Distal"),
          "Little": ("Proximal", "Intermediate", "Distal")}
GRIP_KEYS = {"all", "Thumb", "Index", "Middle", "Ring", "Little", "ThumbTurn", "spread", "mirror", "note"}
CLIP_KEYS = {"grip", "Left", "Right", "keys", "note"}
SET_KEYS = {"poses", "skip", "default", "note"}
# [fist] (H1j): the run fist as a morph (alien_fist_shape.py); the defaults, every key optional but `grip`. The morph
# comes from the contact route (H1q, alien_fist_envelope.contact): the digits' fitted stations (band_mm), the finger
# weight it fades in by (fade_to), the digits' smooth union (c_k_mm, the thumb's c_k_thumb_mm), the moves' cap, a
# vertex this far inside a neighbour (or c_hide_mm inside the union) sinks, the moves' smoothing. The weight's path in
# a clip: the morph's lead over the grip (alien_fist_math.weight_plan, 1 = in step); the grip's own path into and out
# of the fist (stagger_keys): the fingers' tips at the fist by curl[0] of a ramp, their knuckles from curl[1]; the
# thumb from thumb[0] to thumb[1]; [1, 0] and [0, 1] = every joint in step
FIST_DEFAULTS = {"morph": "fist", "route": "contact", "band_mm": 2.0, "fade_to": 0.6,
                 "c_k_mm": 8.0, "c_k_thumb_mm": 6.0, "c_cap_mm": 9.0, "c_bury_mm": 0.5, "c_hide_mm": 3.0,
                 "c_smooth": 12, "c_lambda": 0.5,
                 "lead": 1.0, "curl": [1.0, 0.0], "thumb": [0.0, 1.0]}


class HandsError(ValueError):
    pass


def finger_bones(side: str) -> list:
    """Every finger bone of one hand (the five chains; the Little ones too, so no mocap is left on them)."""
    return [f"{side}{f}{s}" for f, segs in CHAINS.items() for s in segs]


def _check_grip(name: str, g: dict) -> None:
    bad = sorted(set(g) - GRIP_KEYS)
    if bad:
        raise HandsError(f"grip {name}: unknown keys {bad}")
    for k in ("all", "Thumb", "Index", "Middle", "Ring", "Little"):
        n = 3 if k == "Thumb" else (3, 4)  # a finger's optional 4th: its base's side turn (H1g, the solved grips)
        if k in g and (len(g[k]) not in ((n,) if isinstance(n, int) else n)
                       or not all(isinstance(x, (int, float)) for x in g[k])):
            raise HandsError(f"grip {name}: {k} needs three angles" + ("" if k == "Thumb" else " (or four)"))
    if "ThumbTurn" in g and len(g["ThumbTurn"]) != 2:
        raise HandsError(f"grip {name}: ThumbTurn needs [roll, swing]")


def load(path: Path = DATA, poses: Path | None = None) -> dict:
    """The hands file with its grips merged over the poses' (`[set] poses`, beside it), every nested key checked."""
    cfg = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    bad = sorted(set(cfg) - {"set", "grips", "clips", "fist"})
    if bad:
        raise HandsError(f"{path}: unknown tables {bad}")
    st = cfg.get("set", {})
    bad = sorted(set(st) - SET_KEYS)
    if bad:
        raise HandsError(f"{path}: [set] unknown keys {bad}")
    src = poses or Path(path).parent / st.get("poses", "alien_poses.toml")
    base = tomllib.loads(Path(src).read_text(encoding="utf-8")).get("grips", {})
    own = cfg.get("grips", {})
    clash = sorted(set(own) & set(base))
    if clash:
        raise HandsError(f"{path}: grips {clash} are the poses' already (reuse them, do not redefine)")
    grips = {**base, **own}
    for n, g in grips.items():
        _check_grip(n, g)
    default = st.get("default", "relaxed")
    if default not in grips:
        raise HandsError(f"{path}: [set] default grip {default!r} unknown")
    clips = cfg.get("clips", {})
    for pat, c in clips.items():
        bad = sorted(set(c) - CLIP_KEYS)
        if bad:
            raise HandsError(f"clips.{pat}: unknown keys {bad}")
        plan_of(c, grips, f"clips.{pat}")
    out = {"set": {"poses": str(src), "skip": list(st.get("skip", [])), "default": default},
           "grips": grips, "own": sorted(own), "clips": clips}
    if "fist" in cfg:  # H1j: the run fist as a morph on the fist grip
        fist = cfg["fist"]
        bad = sorted(set(fist) - set(FIST_DEFAULTS) - {"grip", "note"})
        if bad:
            raise HandsError(f"{path}: [fist] unknown keys {bad}")
        if fist.get("grip") not in grips:
            raise HandsError(f"{path}: [fist] grip {fist.get('grip')!r} unknown")
        out["fist"] = {**FIST_DEFAULTS, **{k: v for k, v in fist.items() if k != "note"}}
    return out


def plan_of(c: dict, grips: dict, where: str = "") -> dict:
    """A clip entry as {side: [(share, grip), ...]} (share 0..1 of the clip; one grip: held, share 0)."""
    out = {}
    keys = c.get("keys")
    if keys is not None and any(k in c for k in ("grip", "Left", "Right")):
        raise HandsError(f"{where}: `keys` or `grip`/`Left`/`Right`, not both")
    for side in A.SIDES:
        if keys is not None:
            rows = []
            for row in keys:
                if len(row) not in (2, 3):
                    raise HandsError(f"{where}: a key is [share, grip] or [share, left grip, right grip]")
                rows.append((float(row[0]), row[1] if len(row) == 2 else row[1 + A.SIDES.index(side)]))
            if not rows:
                raise HandsError(f"{where}: empty `keys`")
        else:
            spec = c.get(side, c.get("grip"))
            if spec is None:
                raise HandsError(f"{where}: needs `grip`, `Left` and `Right`, or `keys`")
            rows = [(0.0, spec)]
        shares = [s for s, _ in rows]
        if shares != sorted(shares) or not all(0.0 <= s <= 1.0 for s in shares):
            raise HandsError(f"{where}: key shares rise within 0..1, got {shares}")
        for _, g in rows:
            if g not in grips:
                raise HandsError(f"{where}: unknown grip {g!r}")
        out[side] = rows
    return out


def game_name(action: str) -> str:
    """An action's Godot name: no `CharacterArmature|` prefix, no `_Loop`."""
    n = action[len(PREFIX):] if action.startswith(PREFIX) else action
    return n[:-5] if n.endswith("_Loop") else n


def clip_plan(cfg: dict, action: str) -> tuple[str, dict] | None:
    """The entry an action takes: the first `[clips]` pattern (fnmatch, in file order) matching its game name, else
    the default grip; None for a skipped action (the photo poses keep their own grips)."""
    n = game_name(action)
    if any(fnmatch.fnmatchcase(n, p) for p in cfg["set"]["skip"]):
        return None
    for pat, c in cfg["clips"].items():
        if fnmatch.fnmatchcase(n, pat):
            return pat, plan_of(c, cfg["grips"], f"clips.{pat}")
    return "default", plan_of({"grip": cfg["set"]["default"]}, cfg["grips"])


def grip_pose(cfg: dict, grip: str, side: str) -> dict:
    """The grip's basis rotation on every finger bone of the hand (bones the grip leaves straight get identity)."""
    q = {b: (1.0, 0.0, 0.0, 0.0) for b in finger_bones(side)}
    q.update(A.grip_quats(cfg["grips"][grip], side))
    return q


def _seg(bone: str) -> str:
    return next(s for s in ("Metacarpal", "Proximal", "Intermediate", "Distal") if bone.endswith(s))


def stagger_keys(cfg: dict, s0: float, g0: str, s1: float, g1: str) -> list:
    """H1n: the extra keys [(share, part, grip)] of one ramp between two grips when one of them is the fist grip
    (`[fist] curl`): into the fist the fingers' tips curl first (Intermediate and Distal reach the fist grip at
    `curl[0]` of the ramp) and their knuckles follow (Proximal leaves the old grip at `curl[1]`), the thumb at
    `thumb` [from, to]; out of it the same path backwards. part: "finger_tip", "finger_base" or "thumb". In step
    (`curl` [1, 0], `thumb` [0, 1]): none. A plain crossfade between two clips in the game does not follow it."""
    fist = cfg.get("fist")
    if not fist or g0 == g1 or fist["grip"] not in (g0, g1):
        return []
    into = g1 == fist["grip"]
    tip_to, base_from = fist["curl"]
    t_from, t_to = fist["thumb"]
    span = s1 - s0
    out = []

    def at(x):
        return s0 + (x if into else 1.0 - x) * span

    if tip_to < 1.0:  # the tips: at the fist grip by tip_to into it, at the open grip from 1 - tip_to out of it
        out.append((at(tip_to), "finger_tip", g1 if into else g0))
    if base_from > 0.0:  # the knuckles: still open at base_from into it, already open from 1 - base_from out of it
        out.append((at(base_from), "finger_base", g0 if into else g1))
    if t_from > 0.0:
        out.append((at(t_from), "thumb", g0 if into else g1))
    if t_to < 1.0:
        out.append((at(t_to), "thumb", g1 if into else g0))
    return out


def keyed(cfg: dict, rows: list, side: str, frames: tuple[int, int]) -> dict:
    """{bone: [(frame, quat), ...]}: each key of a plan's rows at its frame (share of frames), plus the last frame
    holding the last grip, so a looping clip's seam closes on the first key's grip when it is the same. A ramp into or
    out of the fist grip takes the staggered path's extra keys (stagger_keys, H1n)."""
    f0, f1 = frames
    out = {b: [] for b in finger_bones(side)}
    part = {b: "thumb" if "Thumb" in b else "finger_base" if b.endswith("Proximal") else "finger_tip" for b in out}
    keys = []
    for k, (s, g) in enumerate(rows):
        if k:
            keys += [(x, p, gx) for x, p, gx in stagger_keys(cfg, rows[k - 1][0], rows[k - 1][1], s, g)]
        keys.append((s, None, g))
    poses = {}
    for s, p, g in keys:
        fr = round(f0 + s * (f1 - f0))
        if g not in poses:
            poses[g] = grip_pose(cfg, g, side)
        for b, q in poses[g].items():
            if p is None or part[b] == p:
                if out[b] and out[b][-1][0] == fr:
                    out[b][-1] = (fr, q)
                else:
                    out[b].append((fr, q))
    for b in out:
        if out[b][-1][0] < f1:
            out[b].append((f1, out[b][-1][1]))
    return out


# ---------------------------------------------------------------------------------------------- the check
def _digit(bone: str, side: str) -> str | None:
    for f in CHAINS:
        if bone.startswith(f"{side}{f}"):
            return f
    return None


def collisions(skel: dict, skin: dict, cfg: dict, grip: str, side: str) -> dict:
    """One grip on one hand at rest: per digit the deepest its skin goes into another digit's tubes (`into_finger_cm`)
    and its tip and middle into the palm's (`into_palm_cm`), a finger's distal skin into its own proximal tube
    (`self_cm`), and the least gap between neighbouring fingers' skin (`gap_cm`, Index-Middle, Middle-Ring)."""
    skin = A.prepare_skin(skin)
    r = A.Rig(skel)
    if grip:
        for b, q in grip_pose(cfg, grip, side).items():
            if b in r.rot:
                r.local(b, q)
    P = r.P()
    posed = A.Posed(skel, skin, P)
    pts = {f: posed.groups([f"{side}{f}{s}" for s in CHAINS[f]]) for f in DIGITS}
    tubes = {}
    for f in DIGITS:
        for s in CHAINS[f]:
            t = A.tube(skel, skin, f"{side}{f}{s}")
            if t:
                tubes[f"{side}{f}{s}"] = t
    palm = A.tube(skel, skin, f"{side}Hand")
    out = {"into_finger_cm": {}, "into_palm_cm": {}, "self_cm": {}, "gap_cm": {}}
    for f in DIGITS:
        deep = 0.0
        for g in DIGITS:
            if g == f:
                continue
            for b, t in tubes.items():
                if _digit(b, side) == g:
                    deep = max(deep, A.tube_depth(t, P, pts[f]))
        out["into_finger_cm"][f] = round(100 * deep, 2)
        far = posed.groups([f"{side}{f}{s}" for s in CHAINS[f][1:]])
        out["into_palm_cm"][f] = round(100 * (A.tube_depth(palm, P, far) if palm else 0.0), 2)
        prox = tubes.get(f"{side}{f}{CHAINS[f][0 if f != 'Thumb' else 1]}")
        dist = posed.group(f"{side}{f}Distal")
        out["self_cm"][f] = round(100 * (A.tube_depth(prox, P, dist) if prox else 0.0), 2)
    for a, b in (("Index", "Middle"), ("Middle", "Ring")):
        out["gap_cm"][f"{a}-{b}"] = round(100 * A.nearest_gap(pts[a], pts[b], reach=0.03, cell=0.01), 2)
    out["worst_cm"] = max([*out["into_finger_cm"].values(), *out["into_palm_cm"].values(), *out["self_cm"].values()])
    return out


def excess(row: dict, floor: dict) -> float:
    """How far a grip's worst depth goes past the rest pose's (the measure's floor), in cm; 0 when not past it."""
    worst = 0.0
    for k in ("into_finger_cm", "into_palm_cm", "self_cm"):
        for f, v in row[k].items():
            worst = max(worst, v - floor[k].get(f, 0.0))
    return round(worst, 2)


def table(rows: dict) -> list:
    """Markdown lines of a {clip: {side: grips, worst_cm, excess_cm}} table."""
    lines = ["| Clip | grips (L / R) | worst depth cm (L / R) | past rest cm (L / R) |", "|---|---|---|---|"]
    for clip, r in rows.items():
        lines.append(f"| {clip} | {' + '.join(r['Left']['grips'])} / {' + '.join(r['Right']['grips'])} | "
                     f"{r['Left']['worst_cm']} / {r['Right']['worst_cm']} | {r['Left']['excess_cm']} / "
                     f"{r['Right']['excess_cm']} |")
    return lines


def slerp_rows(a, b, t: float):
    """A key between two grips' quaternions (the review's in-between frames)."""
    return M.q_slerp(a, b, t)


def angle_deg(q) -> float:
    """A rotation's angle (degrees)."""
    return math.degrees(2.0 * math.acos(min(1.0, abs(q[0]))))
