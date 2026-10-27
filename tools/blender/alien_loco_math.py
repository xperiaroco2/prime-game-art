"""The alien locomotion set's plain parts (art #196, option A step 3; no Blender): the set file
(anim_sets/alien_loco.toml) expanded into the clips to make, the game's rates and footstep beat at its speeds, the
stride flag, the jog grid's default picked by the numbers, and the treadmill reels' plan. tools/blender/alien_loco.py
uses it inside Blender (the clips) and outside (the reels); tools/tests/test_alien_loco_math.py tests it."""
from __future__ import annotations

import math
import tomllib
from pathlib import Path

SET = Path(__file__).resolve().parent / "anim_sets" / "alien_loco.toml"
LOOP = "_Loop"  # Godot imports <name>_Loop as <name>, looping (_godot.LOOP_WORDS)
REEL_S = 4.0  # a reel's length (s)


def load(path: Path | str = SET) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def speed_name(name: str, speed: float, first: bool) -> str:
    """The clip fitted to `speed`: the name itself for the first speed, else <name>__s<speed x 10> (a name that is
    already a variant: <name>_s<..>)."""
    if first:
        return name
    return f"{name}{'_' if '__' in name else '__'}s{round(speed * 10):d}"


def grid_name(name: str, arm: float, frames: int) -> str:
    return f"{name}__arm{round(arm * 100):d}_f{frames:d}"


P3_KEYS = ("lift_m", "bob_m", "flight_m", "widen_m", "arms_in_deg", "pin")  # the strafe pilot P3's keys (alien_loco._make)
P4_KEYS = ("even_steps", "arms_carry")  # P4's: the backpedal's even steps and running arms (alien_loco._make)


def expand(cfg: dict) -> list[dict]:
    """The clips to make, in an order where each clip's inputs come first: per clip its name (the game's, or a
    variant's), base (the [[clip]]/[[grid]] name), source or mirror (the clip it mirrors), speed (None: its own),
    frames (None: unchanged), arm_swing, play_at; a grid's default {"name", "pick": [the variants]} after them."""
    jobs: list[dict] = []
    by_base: dict[str, list[dict]] = {}
    for g in cfg.get("grid", []):
        speed = (g.get("speeds") or [None])[0]
        names = []
        for fr in g["frames"]:
            for k in g["arm_swing"]:
                j = {"name": grid_name(g["name"], k, fr), "base": g["name"], "source": g["source"], "speed": speed,
                     "frames": fr, "arm_swing": k, "play_at": list(g.get("play_at", [])), "grid": g["name"]}
                jobs.append(j)
                names.append(j["name"])
        jobs.append({"name": g["name"], "base": g["name"], "pick": names, "speed": speed,
                     "default_arm_swing": g.get("default_arm_swing", 1.0), "play_at": list(g.get("play_at", []))})
    for c in cfg.get("clip", []):
        made = []
        if "mirror" in c:
            if c["mirror"] not in by_base:
                raise ValueError(f"{c['name']}: mirrors {c['mirror']}, which is not made before it")
            for src in by_base[c["mirror"]]:
                made.append({**src, "name": c["name"] + src["name"][len(c["mirror"]):], "base": c["name"],
                             "mirror": src["name"], "source": None, "play_at": list(c.get("play_at", []))})
        else:
            speeds = c.get("speeds") or [None]
            for i, s in enumerate(speeds):
                made.append({"name": speed_name(c["name"], s, i == 0) if s is not None else c["name"],
                             "base": c["name"], "source": c.get("source"), "from": c.get("from"), "speed": s,
                             "frames": c.get("frames"), "orient": c.get("orient"), "cadence": c.get("cadence"),
                             "lean_deg": c.get("lean_deg"), "head_level": c.get("head_level"),
                             "reel": c.get("reel"),
                             "arm_swing": c.get("arm_swing", 1.0), "play_at": list(c.get("play_at", [])),
                             "max_scale": c.get("max_scale"), "bend_min_deg": c.get("bend_min_deg"),
                             "arms_from": c.get("arms_from"),
                             **{k: c.get(k) for k in P3_KEYS + P4_KEYS}})
        by_base[c["name"]] = made
        jobs.extend(made)
    seen = set()
    for j in jobs:
        if j["name"] in seen:
            raise ValueError(f"two clips named {j['name']}")
        if j.get("from") and j.get("even_steps"):  # _make moves the contacts only on a source's cycle
            raise ValueError(f"{j['name']}: even_steps needs a source, not from = {j['from']}")
        if j.get("from") and j["from"] not in seen:
            raise ValueError(f"{j['name']}: made from {j['from']}, which is not made before it")
        seen.add(j["name"])
    return jobs


def cadence_rate(name: str, cadence: float, c0: float | None) -> float:
    """A clip's playback rate for its asked `cadence` (steps/s): cadence / c0, its measured cadence at rate 1; a clip
    with no measured cadence (no steps found) cannot take one."""
    if not c0:
        raise ValueError(f"{name}: cadence = {cadence} asked, but the clip has no measured cadence (c0 = {c0})")
    return cadence / c0


AIM_TOL_DEG = 0.5  # orient: a clip whose head looks further off the aim is first turned whole onto it
LEAN_SPLIT = (("Spine", 0.4), ("Chest", 0.35), ("UpperChest", 0.25))  # lean_deg: the trunk's forward lean, shared


def orient(S, skel: dict, clip: dict, o: dict) -> tuple[dict, dict]:
    """orient_warp with absolute headings (degrees, 0 at the aim -Y, positive toward the left): o = {hips, travel,
    split?}: the hips' mean heading turned to `hips`, the feet's travel to `travel`, whatever the clip's own (a mocap
    take's hips sit off its travel); split: [[bone, share], ...] (default orient_warp's); whole = true instead: the
    clip turned as a whole until its feet travel along `travel` (default 0, the aim; P3: the crouch, its take turned
    13 degrees, the head with it)."""
    fac = S.facing(skel, clip)
    aim = 0.0
    if o.get("whole"):  # the whole clip turned so its feet travel along `travel` (default 0), its pose unchanged
        t0 = S.travel_heading_deg(S.measure(skel, clip))
        turn = S._wrap(o.get("travel", 0.0) - t0)
        out, rep = S.orient_warp(skel, clip, turn, turn, split=())
        return out, {**rep, "asked": dict(o), "whole_turn_deg": round(turn, 2), "travel_before_deg": round(t0, 2),
                     "head_before_deg": fac["head_yaw_deg"], "hips_before_deg": fac["hips_yaw_deg"]}
    if abs(fac["head_yaw_deg"]) > AIM_TOL_DEG:  # first the whole clip turned so its head looks along the aim (a take's
        aim = -fac["head_yaw_deg"]               # head sits off its hips' and its travel's own heading)
        clip, _ = S.orient_warp(skel, clip, aim, aim, split=())
        fac = S.facing(skel, clip)
    m = S.measure(skel, clip)
    travel0 = S.travel_heading_deg(m)
    hip_yaw = S._wrap(o["hips"] - fac["hips_yaw_deg"])
    travel = S._wrap(o["travel"] - travel0)
    split = tuple(tuple(x) for x in o["split"]) if o.get("split") else S.ORIENT_SPLIT
    out, rep = S.orient_warp(skel, clip, hip_yaw, travel, split=split)
    return out, {**rep, "asked": dict(o), "aim_turn_deg": round(aim, 2), "travel_before_deg": round(travel0, 2),
                 "hips_before_deg": fac["hips_yaw_deg"]}


def sources(jobs: list[dict]) -> list[str]:
    return sorted({j["source"] for j in jobs if j.get("source")})


MIN_FOOTSTEP_MPS = 0.5  # footstep_cadence.gd MIN_SPEED_MPS: no footsteps below it


def footstep_interval(speed: float, cfg: dict) -> float:
    """The game's footstep interval (s) at `speed` (footstep_cadence.gd interval_s): the stride lerped between the
    walk's and the sprint's by speed, over the speed."""
    s = cfg["set"]
    if speed < MIN_FOOTSTEP_MPS:
        return math.inf
    t = min(1.0, max(0.0, (speed - s["walk_mps"]) / (s["sprint_mps"] - s["walk_mps"])))
    stride = s["walk_mps"] * s["walk_interval_s"] + t * (s["sprint_mps"] * s["sprint_interval_s"]
                                                         - s["walk_mps"] * s["walk_interval_s"])
    return stride / speed


def play_rows(v0: float, c0: float | None, play_at: list[float], cfg: dict) -> list[dict]:
    """At each speed the game plays the clip: its rate (speed / v0, the game's TimeScale), inside the clamp or not,
    the cadence seen (rate x c0), the step interval beside the game's footstep beat."""
    lo, hi = cfg["set"]["rate_clamp"]
    rows = []
    for sp in play_at:
        rate = sp / v0 if v0 else math.inf
        cad = None if c0 is None else rate * c0
        beat = footstep_interval(sp, cfg)
        rows.append({"speed": sp, "rate": round(rate, 3), "in_clamp": lo <= rate <= hi,
                     "cadence": None if cad is None else round(cad, 3),
                     "step_s": None if not cad else round(1.0 / cad, 3), "beat_s": round(beat, 3)})
    return rows


def capped_rate(speed: float, v0: float, max_scale: float, rate: float | None = None,
                intervals: int | None = None) -> float | None:
    """The playback rate a stride fit needs so its stride scale stays at most max_scale: the rest of the speed goes
    into the cadence (rate = speed / (v0 x max_scale)); `rate` (or None, 1.0) when the scale is already within it.
    With the loop's frame `intervals`, the whole-frame rounding of the retime (anim_edit_math.retime_count) is
    counted too (PR #326's follow-up: Jog_Bwd__s4b's capped 1.3075 rounded to 1.3, the scale 1.509 over its 1.5): a
    rounded count over the cap is floored to the largest count within it and its exact rate T / T2 returned."""
    r = 1.0 if rate is None else rate
    if speed / (v0 * r) <= max_scale:
        out = rate
    else:
        out = r = speed / (v0 * max_scale)
    if intervals is None or out is None:
        return out
    t2 = max(1, round(intervals / r))
    if speed * t2 / (intervals * v0) > max_scale + 1e-12:  # the rounded count lengthens the loop past the cap
        t2 = max(1, math.floor(max_scale * intervals * v0 / speed + 1e-9))
    return intervals / t2


def check_max_scale(name: str, scale: float, max_scale: float | None) -> None:
    """Refuses a stride scaled over its clip's max_scale (after the retime's whole-frame rounding)."""
    if max_scale is not None and scale > max_scale + 1e-6:
        raise ValueError(f"{name}: the stride scaled {scale:.4f}x, over its max_scale {max_scale}")


def stride_flag(scale: float | None, cfg: dict) -> bool:
    """A stride scaled over the set's bound (2x) either way is flagged."""
    if not scale:
        return False
    b = cfg["set"]["stride_flag"]
    return scale > b or scale < 1.0 / b


def pick_default(rows: list[dict], beat_cadence: float, slide_bound_mm: float, default_arm: float) -> dict:
    """The grid's default: among the variants whose planted feet stay within the slide bound (none: all of them), the
    cadence (c0, steps/s at rate 1) nearest the footstep beat's; a tie (the arm swing does not move the cadence) to
    the arm swing nearest default_arm. rows: {"name", "c0", "slide_mm", "arm_swing"}."""
    ok = [r for r in rows if r["slide_mm"] <= slide_bound_mm] or rows
    return min(ok, key=lambda r: (round(abs(r["c0"] - beat_cadence), 6), abs(r["arm_swing"] - default_arm)))


VIEWS = ("front", "three_quarter", "back", "side")  # treadmill_reels.gd's cameras (side: from the character's left)


def reel_plan(jobs: list[dict], reels: list[dict] | None = None) -> list[dict]:
    """With the set's [[reel]] entries (P2): those, one reel per view (<name>__<view>), each clip at its speed, an
    optional travel (degrees, the stripes' heading: a clip carried along another direction than its own, the game's
    pure side clip on a diagonal) and label; their clips must be made by the set. Without them, the old plan (steps 3
    and 4b): the treadmill reels: per game slot one reel at its speed (side view); a clip with one speed variant
    (<name>__s<..>: a strafe at 3.0 beside 4.5, Jog_Bwd at 3.0 beside 2.5) as a pair (strafes seen from the front); the
    jog grid as a 2x3 sheet (no video); Idle -> Jog_Fwd at 4.5 with the game's 0.15 s cross-fade (its sheet: 8 frames
    around the switch)."""
    if reels:
        names = {j["name"] for j in jobs}
        out = []
        for r in reels:
            for c in r["clips"]:
                if c["clip"] not in names:
                    raise ValueError(f"reel {r['name']}: {c['clip']} is not made by the set")
            for v in r["views"]:
                if v not in VIEWS:
                    raise ValueError(f"reel {r['name']}: no camera {v}")
                out.append({"name": f"{r['name']}__{v}", "view": v, "video": r.get("video", True),
                            "cols": r.get("cols", 3), "clips": [dict(c) for c in r["clips"]]})
        return out
    names = {j["name"]: j for j in jobs}
    reels = []
    for j in jobs:
        if j.get("grid") or j["name"] != j["base"]:
            continue
        variants = [v for v in names.values() if v["base"] == j["name"] and v["name"] != j["name"]
                    and not v.get("grid") and v.get("speed") is not None]
        view = "front" if j["name"].startswith("Strafe") else "side"
        if len(variants) == 1:
            reels.append({"name": j["name"], "view": view, "video": True,
                          "clips": [{"clip": j["name"], "speed": j["speed"]},
                                    {"clip": variants[0]["name"], "speed": variants[0]["speed"]}]})
        else:
            sp = j["speed"] if j["speed"] is not None else (j["play_at"] or [None])[0]
            if j["name"] == "Walk":
                sp = None  # at its own speed: the game never plays it
            reels.append({"name": j["name"], "view": view, "video": True, "clips": [{"clip": j["name"], "speed": sp}]})
    grid = [j for j in jobs if j.get("grid")]
    if grid:
        reels.append({"name": grid[0]["grid"] + "_grid", "view": "side", "video": False, "cols": 3,
                      "clips": [{"clip": j["name"], "speed": j["speed"]} for j in grid]})
    if "Jog_Fwd" in names:
        reels.append({"name": "Idle_to_Jog_Fwd", "view": "side", "video": True, "seconds": 3.0,
                      "start": {"from": "Idle", "to": "Jog_Fwd", "at": 1.0, "fade": 0.15},
                      "clips": [{"clip": "Jog_Fwd", "speed": names["Jog_Fwd"]["speed"]}]})
    return reels


def godot_xz(v) -> list[float]:
    """A horizontal Blender vector (x, y) as Godot's (x, z): glTF's +Y up turns Blender's -Y forward into Godot's +Z."""
    return [round(v[0], 5), round(-v[1], 5)]


def reel_timeline(info: dict, speed: float | None, seconds: float, cfg: dict, offset: float = 0.0,
                  travel_deg: float | None = None) -> dict:
    """One clip on the treadmill: its rate at `speed` (None: its own v0, rate 1), the stripes' direction (Godot x, z:
    the planted feet's way relative to the hips, ground minus hips), the game's footstep interval at that speed and
    the reel times (s) of the beats and of each foot's contacts, the clip starting at `offset`. info: loco.json's
    "reel" entry (fps, frames, v0, ground, hips, contacts in clip frames)."""
    v0 = info["v0"]
    sp = v0 if speed is None else speed
    rate = sp / v0
    length = info["frames"] / info["fps"]
    rel = (info["ground"][0] - info["hips"][0], info["ground"][1] - info["hips"][1])
    n = math.hypot(*rel)
    d = [round(rel[0] / n, 5), round(rel[1] / n, 5)] if n > 1e-9 else [0.0, -1.0]
    if travel_deg is not None:  # the ground against a travel of this heading (Godot x, z: Blender's (x, -y))
        h = math.radians(travel_deg)
        d = [round(-math.sin(h), 5), round(-math.cos(h), 5)]
    contacts = {}
    for side, frames in info["contacts"].items():
        ts = []
        k = 0
        while offset + k * length / rate <= seconds:
            ts += [round(offset + (c / info["fps"] + k * length) / rate, 4) for c in frames]
            k += 1
        contacts[side] = sorted(t for t in ts if t <= seconds)
    beat = footstep_interval(sp, cfg)
    beats = [round(offset + i * beat, 4) for i in range(int((seconds - offset) / beat) + 1)] if beat < math.inf else []
    return {"speed": round(sp, 4), "rate": round(rate, 4), "dir": d, "beat_s": round(beat, 4), "length_s": round(length, 4),
            "contacts": contacts, "beats": beats}


IN_PLACE_TRAVEL_M = 0.01  # a loop whose hips travel more than this per loop is cut in place
IN_PLACE_OFFSET_M = 0.05  # ... and one whose hips' mean sits further than this off the origin, recentred


def in_place(skel: dict, clip: dict, bone: str = "Hips") -> tuple[dict, dict]:
    """The loop with its hips' horizontal travel and offset taken off (the game moves the body; its clips play in
    place, as the UAL loops do): per frame the hips' armature-space x, y lose the loop's linear travel and then its
    mean, so they sway about the origin; height, every rotation and the other bones' bases stay. A loop already in
    place (travel and offset under the bounds above) comes back unchanged. Returns (clip, report: the travel and
    the offset removed, m)."""
    import alien_stride_math as S
    skel = S.prepare(skel)
    T = S.frames(clip)
    track = S.tracks(skel, clip, [bone])[bone]
    d = (track[T][0] - track[0][0], track[T][1] - track[0][1])
    flat = [(p[0] - f / T * d[0], p[1] - f / T * d[1]) for f, p in enumerate(track)]
    mean = (sum(p[0] for p in flat[:-1]) / T, sum(p[1] for p in flat[:-1]) / T)
    rep = {"travel_m": [round(x, 4) for x in d], "offset_m": [round(x, 4) for x in mean]}
    if math.hypot(*d) <= IN_PLACE_TRAVEL_M and math.hypot(*mean) <= IN_PLACE_OFFSET_M:
        return clip, {**rep, "cut": False}
    out = S.copy_clip(clip)
    locs = []
    for f in range(T + 1):
        poses = S.fk(skel, clip, f)
        m = [list(r) for r in poses[bone]]
        m[0][3] -= f / T * d[0] + mean[0]
        m[1][3] -= f / T * d[1] + mean[1]
        locs.append(S.basis_of(skel, {**poses, bone: m}, bone)[0])
    out["loc"] = {**out["loc"], bone: locs}
    return out, {**rep, "cut": True}


def hips_extent(skel: dict, clip: dict, bone: str = "Hips") -> dict:
    """The hips over the loop in armature space: the furthest horizontal distance from the origin and the lowest and
    highest height (m)."""
    import alien_stride_math as S
    track = S.tracks(S.prepare(skel), clip, [bone])[bone]
    return {"max_xy_m": round(max(math.hypot(p[0], p[1]) for p in track), 4),
            "z_m": [round(min(p[2] for p in track), 4), round(max(p[2] for p in track), 4)]}


TRIM_TOL_DEG = 0.5  # trim_travel: the measured travel within this of the asked


def trim_travel(S, skel: dict, clip: dict, want_deg: float, passes: int = 3) -> tuple[dict, dict]:
    """The feet's tracks alone turned (orient_warp with no hip yaw and no chain: the hips, the trunk and the feet's own
    rotation kept) until the planted feet's measured travel is `want_deg`: after orient_warp the feet roll heel to toe
    along their own heading, which pulls the measured travel a few degrees toward the hips (P2: 85 for an asked 90),
    and the stride's re-plant follows that axis. Returns (the clip, the report: the travel before, after, the turns)."""
    t0 = S.travel_heading_deg(S.measure(skel, clip))
    out, turns, t = clip, [], t0
    for _ in range(passes):
        miss = S._wrap(want_deg - t)
        if abs(miss) <= TRIM_TOL_DEG:
            break
        out, _ = S.orient_warp(skel, out, 0.0, miss, split=(), feet_yaw=0.0)
        turns.append(round(miss, 2))
        t = S.travel_heading_deg(S.measure(skel, out))
    return out, {"want_deg": want_deg, "before_deg": round(t0, 2), "after_deg": round(t, 2), "turns_deg": turns}
