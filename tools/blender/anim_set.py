"""Builds an animation set (art #33; docs/animations.md, "Animation sets"): every clip of a set's settings
(tools/blender/anim_sets/<set>.toml, checked by anim_set_cfg.py) from its source clip, retargeted as the animation
review does it (anim_review.clips_for, with the travel kept), through its edit steps (anim_edit.apply), baked onto the
body type's donor and saved as a character the export accepts. The runner calls it (tools/run.py anim-set); the
review builds the same clips in its own process (anim_review.clips_for, "mvp:<clip>" keys) through build_clips().

Usage (background Blender only):
  blender -b --factory-startup --python-exit-code 1 --python anim_set.py -- --set <toml> --body men
      --character <glb> --lib ual=<glb> [--lib ual2=<glb> ...] --raw <dir> --out <dir> [--clips A,B|all] [--no-save]

Writes <out>/<stem>_<body>.blend (the donor's armature and meshes with the set's exported actions only, transforms
applied, scene at 30 fps) and <out>/build_report.json (per clip: source, frames, seconds, loop, needs, every step's
report, the travel and heading left, the lowest vertex; the upper-body layer's bone list).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import anim_edit as ae  # noqa: E402
import anim_edit_math as em  # noqa: E402
import anim_set_cfg as asc  # noqa: E402
import retarget_core as rc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK_TOLERANCE_M = 1e-4  # the posed character before and after the transforms are applied (as um/blendfile.py)
OPEN_SEAM_MM, OPEN_SEAM_DEG = 0.5, 0.5  # a looping source whose last frame is further from its first is open


def load_set(path: str) -> dict:
    """A set's settings; a relative path is relative to tools/blender."""
    return asc.load(path if os.path.isabs(path) else os.path.join(HERE, path))


def _r(x, digits=3):
    return None if x is None else round(float(x), digits)


def _summary(fr: ae.Frames, target: ae.Target, lowest: bool) -> dict:
    """What is left of a built clip's travel and heading, and its lowest vertex."""
    poses = fr.poses()
    path = [ae._xy(ae._world(fr.rig, P, ae.BODY)) for P in poses]
    yaws = em.unwrap([ae._facing(fr.rig, P) for P in poses])
    times = [k / fr.fps for k in range(len(path))]
    d, speed = em.lsq_direction(path, times)
    moving = speed * fr.seconds > 0.02
    out = {"travel_left_m": _r(math.dist(path[0], path[-1])),
           "travel_dir_deg": _r(em.yaw_of(d), 1) if moving else None,
           "facing_start_deg": _r(yaws[0], 1), "facing_end_deg": _r(yaws[-1], 1),
           "yaw_drift_deg": _r(yaws[-1] - yaws[0], 1),
           "body_height_m": [_r(min(ae._world(fr.rig, P, ae.BODY).z for P in poses)),
                             _r(max(ae._world(fr.rig, P, ae.BODY).z for P in poses))]}
    if moving:
        out["crab_deg"] = _r(em.wrap(em.circular_mean(yaws) - em.yaw_of(d)), 1)
    # where the hips and the head face on average (0: the game's aim, -Y): a strafe or a crawl turned off its aim
    # shows here (art #33's review: the strafe's hips 20 degrees towards its travel, its head 18 the other way)
    out["facing_mean_deg"] = _r(em.circular_mean(yaws), 1)
    out["head_facing_mean_deg"] = _r(em.circular_mean([_head_yaw(fr.rig, P) for P in poses]), 1)
    if fr.loop and len(poses) > 2:
        # the loop's real seam: the step from its last distinct frame onto its first (the last frame is the first by
        # construction, so a seam of 0 says nothing) against the median frame step, over the joints' world positions
        heads = [[fr.rig.W @ P[n].translation for n in fr.rig.order] for P in poses]
        steps = [max((a - b).length for a, b in zip(heads[k], heads[k + 1])) for k in range(len(heads) - 1)]
        median = sorted(steps)[len(steps) // 2]
        out["seam_step_ratio"] = _r(steps[-1] / median, 2) if median > 0 else None
    if lowest:
        lows = ae._lows(fr, target)
        under = run = 0
        for z in lows:
            run = run + 1 if z < -0.01 else 0
            under = max(under, run)
        out.update(lowest_cm=_r(100 * min(lows), 2), lowest_at_s=_r(lows.index(min(lows)) / fr.fps, 3),
                   highest_low_cm=_r(100 * max(lows), 2), frames_under_1cm_in_a_row=under)
    return out


def _head_yaw(rig, P) -> float:
    R = ae._turn_of(rig, P, "Head")
    return em.facing_yaw(tuple(R @ Vector((0.0, -1.0, 0.0))), tuple(R @ Vector((1.0, 0.0, 0.0))))


def close_open_loop(fr: ae.Frames) -> tuple[ae.Frames, dict | None]:
    """A looping source whose last frame is not its first (an open cycle: UAL's loops end one frame before their first
    pose comes round again) gets its first frame appended, so its loop is closed and one frame longer, as the clip
    edits and Godot's LOOP_LINEAR expect; a seam smaller than half the clip's median frame step is a closed loop's
    small error, and its last frame becomes its first instead. The seam is measured as the export measures it: the
    joints' world positions (mm) and the bones' armature-space rotations (degrees). Returns the frames and the seam it
    had (None: already closed)."""
    poses = fr.poses()
    heads = [[fr.rig.W @ P[n].translation for n in fr.rig.order] for P in poses]

    def step(a, b):
        mm = max((p - q).length for p, q in zip(heads[a], heads[b])) * 1000
        deg = max(min(x, 360 - x) for x in (math.degrees(poses[a][n].to_quaternion().rotation_difference(
            poses[b][n].to_quaternion()).angle) for n in fr.rig.order))
        return mm, deg

    mm, deg = step(0, -1)
    if mm <= OPEN_SEAM_MM and deg <= OPEN_SEAM_DEG:
        return fr, None
    steps = sorted(step(k, k + 1)[0] for k in range(len(poses) - 1))
    median = steps[len(steps) // 2] if steps else 0.0
    seam = {"position_mm": _r(mm, 2), "rotation_deg": _r(deg, 2), "median_step_mm": _r(median, 2)}
    if median > 0 and mm >= 0.5 * median:  # open: the first pose comes round one frame after the last
        return fr.copy([*fr.basis, {n: m.copy() for n, m in fr.basis[0].items()}]), {**seam, "frames_added": 1}
    out = fr.copy()
    out.basis[-1] = {n: m.copy() for n, m in fr.basis[0].items()}
    return out, {**seam, "frames_added": 0}


def recentre(fr: ae.Frames) -> tuple[ae.Frames, float]:
    """A set's clips stand over the origin, where the game's body is: a loop's Body is centred on it over the cycle, a
    one-shot's first frame stands on it (Root moves; a cycle cut from a travelling clip, such as the strafe cut 1.8 s
    in, would otherwise play metres away). Returns the frames and how far they moved (m)."""
    path = ae._body_path(fr)
    pts = path[:-1] if fr.loop and len(path) > 1 else path[:1]
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    moved = math.hypot(cx, cy)
    if moved < 1e-4:
        return fr, 0.0
    out = fr.copy()
    ae._move_world(out, [Matrix.Translation((-cx, -cy, 0.0))] * len(out.basis))
    return out, _r(moved)


def build_clips(set_cfg: dict, char: dict, names, body: str, resolve, target: ae.Target | None = None,
                lowest: bool = False, log=print) -> dict:
    """Builds the clips `names` ("all" or a list) of a set on char (a donor with the toe bones) and the clips they are
    made `from`: {name: Frames}, each with info["report"]. resolve(char, keys) gives {clip key: a clip with a `sampler`
    and `loop`} for the sources (anim_review.clips_for). A step that fails raises anim_edit.EditError naming the clip."""
    table = asc.clips(set_cfg)
    order = asc.closure(set_cfg, names)
    keys = asc.sources(set_cfg, names)
    src = resolve(char, keys) if keys else {}
    target = target or ae.Target(char)
    target.upper = set_cfg.get("upper", target.upper)
    out = {}
    for name in order:
        c = table[name]
        t0 = time.time()
        opened = None
        if "source" in c:
            clip = src[c["source"]]
            fr = ae.Frames.from_sampler(clip.sampler, target.rig, clip.loop)
            if fr.loop:
                fr, opened = close_open_loop(fr)
        else:
            base = out[c["from"]]
            keep = {k: base.info[k] for k in ("speed_m_s", "speed_from", "travel_m") if k in base.info}
            fr = ae.Frames(base.rig, [{n: m.copy() for n, m in b.items()} for b in base.basis], base.fps, base.loop, keep)
        try:
            fr = ae.apply(fr, c["edits"], target, body)
        except ae.EditError as e:
            raise ae.EditError(f"{name}: {e}") from e
        if c["loop"] and not fr.loop:
            raise ae.EditError(f"{name}: loop = true, but neither its source nor a cycle step closes it")
        fr.loop = c["loop"]
        fr, moved = recentre(fr)
        rep = {"source": c.get("source"), "from": c.get("from"), "export": c["export"], "loop": fr.loop,
               "frames": fr.frames, "seconds": _r(fr.seconds), "speed_m_s": asc.speed_of(c),
               "measured_speed_m_s": _r(fr.info.get("speed_m_s")), "needs": c["needs"], "steps": fr.info["steps"]}
        if opened:
            rep["source_open_seam"] = opened
        rep["recentred_m"] = moved
        rep.update(_summary(fr, target, lowest))
        rep["seconds_spent"] = _r(time.time() - t0, 1)
        fr.info["report"] = rep
        out[name] = fr
        log(f"SETCLIP {body} {name} " + json.dumps({k: rep[k] for k in ("frames", "seconds", "loop", "travel_left_m")}))
    return out


def bake(char: dict, built: dict, names: list[str]) -> dict:
    """Bakes the named clips onto char's armature as actions named exactly so (another action of that name is renamed
    out of the way first): {name: action}."""
    arm = char["arm"]
    out = {}
    for name in names:
        old = bpy.data.actions.get(name)
        if old is not None:
            old.name = "~" + name
        act = built[name].to_action(arm, name)
        if act.name != name:
            raise RuntimeError(f"baked {name} as {act.name}")
        out[name] = act
    return out


def _sample(arm, parts, action, frame):
    """World bone heads and tails and deformed vertices with action at frame (as um/blendfile.py)."""
    import numpy as np
    from anim_metrics import world_points

    ad = arm.animation_data or arm.animation_data_create()
    ad.action = action
    ad.action_slot = action.slots[0]
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    pts = [tuple(mw @ pb.head) for pb in arm.pose.bones] + [tuple(mw @ pb.tail) for pb in arm.pose.bones]
    pts = np.array(pts)
    pts = np.concatenate([pts] + [world_points(o) for o in parts])
    ad.action = None
    rc.reset_pose(arm)
    bpy.context.view_layer.update()
    return pts


def _fcurves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def save(char: dict, actions: dict, path: str, fps: int) -> dict:
    """Saves the donor with only `actions` as a character the export accepts (export_glb.py): one armature, the meshes
    parented to it with one Armature modifier each, no RootNode, no empty, no assigned action, every transform applied
    (location keys times the armature's world scale, as um/blendfile.save_character does), a scene at `fps` covering
    the longest action. Checks a few poses before and after within 0.1 mm. Changes char in place: call it last."""
    import numpy as np

    arm = char["arm"]
    root = char["root"]
    rc.place(char)  # back at the origin, facing -Y
    if arm.animation_data:
        for track in list(arm.animation_data.nla_tracks):
            arm.animation_data.nla_tracks.remove(track)
        arm.animation_data.action = None
    rc.reset_pose(arm)
    parts = sorted(char["meshes"].values(), key=lambda o: o.name)
    for o in parts:
        mods = [m.type for m in o.modifiers]
        if o.parent is not arm or mods != ["ARMATURE"] or o.modifiers[0].object is not arm:
            raise RuntimeError(f"{o.name}: not a part skinned to {arm.name} ({o.parent}, {mods})")
    bpy.context.view_layer.update()
    acts = list(actions.values())
    checks = [(a, int(a.frame_range[0] + (a.frame_range[1] - a.frame_range[0]) * f)) for a in acts[:4]
              for f in (0.0, 0.5)]
    before = [_sample(arm, parts, a, f) for a, f in checks]
    m = arm.matrix_world.copy()
    scale = m.to_scale()
    if max(scale) - min(scale) > 1e-4:
        raise RuntimeError(f"the armature's scale {tuple(scale)} is not uniform")
    for o in parts:
        o.data.transform(o.matrix_world)
        o.data.update()
    arm.parent = None
    arm.data.transform(m)
    arm.matrix_basis = Matrix.Identity(4)
    for o in parts:
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_basis = Matrix.Identity(4)
    for act in acts:
        for fc in _fcurves(act):
            if fc.data_path.endswith(".location"):
                for k in fc.keyframe_points:
                    k.co.y *= scale.x
                    k.handle_left.y *= scale.x
                    k.handle_right.y *= scale.x
                fc.update()
    bpy.context.view_layer.update()
    after = [_sample(arm, parts, a, f) for a, f in checks]
    error = max(float(np.linalg.norm(p - q, axis=1).max()) for p, q in zip(before, after))
    if error > CHECK_TOLERANCE_M:
        raise RuntimeError(f"applying the transforms moved the posed character by {error * 1000:.3f} mm")
    # the file holds the character and the set's actions only: every other object (the RootNode, the review's camera,
    # lights and floor) and every other action (the pack's, the retargeted sources) goes. A partial write
    # (bpy.data.libraries.write) of a new scene crashed Blender 5.2.2 in BKE_view_layer_copy_data, so the whole
    # file is saved as a copy.
    keep = {arm, *parts}
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    for act in list(bpy.data.actions):
        if act not in acts:
            bpy.data.actions.remove(act)
    for extra in list(bpy.data.scenes)[1:]:
        bpy.data.scenes.remove(extra)
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    scene.frame_start = int(min(a.frame_range[0] for a in acts))
    scene.frame_end = int(max(a.frame_range[1] for a in acts))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), copy=True, compress=True)
    print("SAVED", path)
    return {"blend": path.replace("\\", "/"), "transform_check_max_error_mm": round(error * 1000, 4),
            "actions": {a.name: [int(a.frame_range[0]), int(a.frame_range[1])] for a in acts},
            "armature": arm.name, "bones": len(arm.data.bones), "parts": [o.name for o in parts]}


def main(argv):
    import anim_review as rv

    ap = argparse.ArgumentParser(prog="anim_set.py")
    ap.add_argument("--set", required=True, help="the set's settings (tools/blender/anim_sets/<set>.toml)")
    ap.add_argument("--body", choices=["men", "women"], required=True)
    ap.add_argument("--character", required=True)
    ap.add_argument("--lib", action="append", default=[], help="<key>=<glb>: a library's in-place file")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--config", default=os.path.join(HERE, "anim_review.toml"))
    ap.add_argument("--clips", default="all")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-save", action="store_true", help="build and report only")
    a = ap.parse_args(argv)
    a.libs = dict(x.split("=", 1) for x in a.lib)
    cfg = rv.load_config(a.config)
    rv.LABELS.update({k: v.get("label", k.upper()) for k, v in cfg.get("libraries", {}).items()})
    set_cfg = load_set(a.set)
    errors = asc.check(set_cfg, {"pack", *a.libs})
    if errors:
        raise SystemExit("the set's settings: " + "; ".join(errors))
    t0 = time.time()
    (char,) = rv.setup_characters(a)
    target = ae.Target(char)
    target.measure  # noqa: B018 (built in the rest pose, before anything moves)

    def resolve(ch, keys):
        return {c.key: c for c in rv.clips_for(a, cfg, ch, keys, in_place=False)}

    names = "all" if a.clips == "all" else a.clips.split(",")
    built = build_clips(set_cfg, char, names, a.body, resolve, target, lowest=True)
    wanted = asc.closure(set_cfg, names) if names == "all" else names
    export = [n for n in asc.exported(set_cfg) if n in wanted]
    report = {"set": a.set.replace("\\", "/"), "title": set_cfg.get("title"), "body": a.body,
              "character": a.character.replace("\\", "/"), "fps": rc.FPS, "upper": target.upper,
              "upper_bones": target.upper_bones(), "exported": export,
              "clips": {n: built[n].info["report"] for n in wanted}}
    os.makedirs(a.out, exist_ok=True)
    if not a.no_save:
        acts = bake(char, built, export)
        report["saved"] = save(char, acts, os.path.join(a.out, f"{set_cfg.get('stem', 'set')}_{a.body}.blend"),
                               rc.FPS)
    report["seconds_spent"] = _r(time.time() - t0, 1)
    with open(os.path.join(a.out, "build_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print("BUILT", a.body, len(built), "clips", os.path.join(a.out, "build_report.json"))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
