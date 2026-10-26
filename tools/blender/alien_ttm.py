"""The text-to-motion locomotion candidates on the alien (art #196, option A step 2): bakes Meshy text-to-motion clips
(SMPL-H FBX files) onto a built alien character's contract skeleton with retarget_core's Retargeter and the map
retarget_maps/smpl_contract.toml (FK legs: the leg solve needs no IK bones, see the map's head), cuts each into its
best loop (alien_stride_math.cycle), measures it (alien_stride_math.measure and alien_ttm_math), mirrors the best
left strafe into a right one, ranks the candidates per slot by the numbers alone and renders the sheets.

    $PYTHON_BIN tools/blender/alien_ttm.py --blend <char.blend> --raw D:/prime-art-raw --out <dir> [--items a,b]
        [--no-sheets]

Into <dir>: candidates.json (rest check, per candidate its numbers, faults and the ranking per slot), one sheet per
candidate (<name>.png: 8 frames over its loop, side view, strafes from the front), overview.png (every candidate a
row, in candidates.json's order) and <char>_ttm.blend: the character with the actions CharacterArmature|TM_<item>
(the whole bake, at the character's own fps) and CharacterArmature|TM_<item>_Loop (the cut loop). The build's .blend
is only read. Without bpy the file starts Blender on itself (runner.blender, background).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alien_stride_math as S  # noqa: E402
import alien_ttm_math as T  # noqa: E402

MAP = HERE / "retarget_maps" / "smpl_contract.toml"
FBX = "text_to_motion-clip.fbx"
# (name, slot, raw folder): the seven clips of batch 2026-10-25-alien-locomotion-ttm, then the older baseline rows
ITEMS = [(i, slot, f"2026-10-25-alien-locomotion-ttm/{i}") for i, slot in (
    ("jog-fwd-a", "jog"), ("jog-fwd-b", "jog"), ("strafe-left-shuffle", "strafe"), ("strafe-left-cross", "strafe"),
    ("backward-run-a", "backward"), ("backward-run-b", "backward"), ("crouch-run", "crouch"))] + [
    ("b6-backward-run", "backward", "2026-10-b6-anim-rerolls/backward-run"),
    ("b6-strafe-left-r2", "strafe", "2026-10-b6-anim-rerolls/strafe-left-r2"),
    ("b5-strafe-left", "strafe", "2026-10-b5-anim-mvp/strafe-left")]
BASELINE = ("b5-", "b6-")  # the older batches' rows
LOOP_S = (0.5, 1.8)  # the loop's length bounds (s): one cycle of two steps for a run or a strafe


def _top_group(obj, v):
    names = {g.index: g.name for g in obj.vertex_groups}
    best = max(v.groups, key=lambda g: g.weight, default=None)
    return names.get(best.group) if best is not None else None


def body_shape(arm, skel) -> tuple[dict, dict]:
    """From the character's meshes at rest: the torso's section (alien_ttm_math.torso_shape) and the soles, per foot
    and toe bone the vertices within 1.5 cm of that side's lowest, in the bone's rest frame."""
    meshes = [o for o in arm.children if o.type == "MESH"]
    torso, feet = [], {}
    for o in meshes:
        for v in o.data.vertices:
            g = _top_group(o, v)
            p = tuple(o.matrix_world @ v.co)
            if g in T.TORSO_BONES:
                torso.append(p)
            elif g in ("LeftFoot", "RightFoot", "LeftToes", "RightToes"):
                feet.setdefault(g, []).append(p)
    soles = {}
    for side in S.SIDES:
        bones = [b for b in (f"{side}Foot", f"{side}Toes") if b in feet]
        low = min(p[2] for b in bones for p in feet[b])
        for b in bones:
            inv = S.rigid_inv(skel["rest"][b])
            pts = [p for p in feet[b] if p[2] < low + 0.015]
            soles[b] = [tuple(sum(inv[i][k] * p[k] for k in range(3)) + inv[i][3] for i in range(3)) for p in pts]
    return T.torso_shape(torso), {b: v for b, v in soles.items() if v}


def bake(arm, bmap, path: Path, name: str, fps: int, meshes) -> tuple:
    """One FBX clip retargeted onto arm at fps frames per second as the action PREFIX + name; (action, report)."""
    import bpy
    import anim_libs
    import retarget_core as rc
    import retarget_smpl
    from alien_stride import PREFIX
    before = set(bpy.data.objects)
    src = retarget_smpl.import_fbx(str(path))
    bpy.context.scene.render.fps = fps  # the import sets the source's 30
    srig = rc.Rig(src["arm"])
    sampler = anim_libs.Shifted(src["action"], retarget_smpl.TOP,
                                retarget_smpl.floor_offset(srig, src["floor_shift_m"]))
    rt = rc.Retargeter(srig, rc.Rig(arm), bmap)
    rt.set_soles(meshes)
    rest = rt.rest_error()
    seconds = sampler.frames / rc.FPS
    n = int(math.floor(seconds * fps + 1e-6))
    frames = [rt.solve(rc.fk(srig, sampler.basis(sampler.start + k * rc.FPS / fps)))[1] for k in range(n + 1)]
    act = rc.bake(arm, PREFIX + name, frames)
    rep = {"source_s": round(seconds, 3), "frames": n, "ik_miss_mm": round(rt.miss_mm, 2), "rest_check": rest,
           "translation_scale": round(rt.ratio, 4), "floor_shift_m": round(src["floor_shift_m"], 4)}
    for o in set(bpy.data.objects) - before:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.actions.remove(src["action"])
    return act, rep


def numbers(skel, clip, cyc, shape, soles, slot, extra: dict) -> dict:
    m = S.measure(skel, clip)
    want, speed = T.SLOTS[slot]
    c = {"slot": slot, **extra, "v0": m["v0"], "c0": m["c0"], "stride_m": m["stride_m"], "cycle_s": m["cycle_s"],
         "steps_in_loop": sum(len(v) for v in m["contacts"].values()), **T.direction(skel, clip, m),
         "seam_cut_deg": cyc["seam_deg"], "seam_after_deg": round(S.seam_deg(clip), 3),
         "foot_slide_mm": m["foot_slide_mm"], **T.floor(T.sole_heights(skel, clip, soles)),
         "hands_cm": T.hands_into_torso(skel, clip, shape), "hips_height": T.hips_height(skel, clip),
         "hips_m_s": m["hips_m_s"], "ground_m_s": m["ground_m_s"], "game_speed": speed, "rate_at_speed": round(speed / m["v0"], 3) if m["v0"] else None, "cut": cyc}
    c["cadence_at_speed"] = round(c["rate_at_speed"] * m["c0"], 3) if m["c0"] and c["rate_at_speed"] else None
    c["faults"], c["score"] = T.faults(c, slot)
    return c


def _cut(skel, clip, bounds):
    for foot, (lo, hi) in (("Left", bounds), ("Left", (LOOP_S[0], 3.0)), ("Right", (LOOP_S[0], 3.0))):
        try:
            return S.cycle(skel, clip, foot=foot, min_s=lo, max_s=hi, loop=False)
        except ValueError:
            continue
    raise ValueError(f"{clip['name']}: no loop found")


def _blender_main(argv: list[str]) -> None:
    import bpy
    import retarget_map
    from alien_stride import PREFIX, _armature, sample, sheet, skeleton, write
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--items", default="")
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 beside the saved file
    arm = _armature()
    fps = bpy.context.scene.render.fps
    skel = S.prepare(skeleton(arm))
    shape, soles = body_shape(arm, skel)
    bmap = retarget_map.load(MAP)
    meshes = [o for o in arm.children if o.type == "MESH"]
    pick = set(a.items.split(",")) if a.items else None
    cands, loops, report = {}, {}, {"blend": a.blend, "fps": fps, "map": bmap["title"], "torso": shape,
                                     "soles": {b: len(v) for b, v in soles.items()}, "bakes": {}}
    for name, slot, rel in ITEMS:
        if pick and name not in pick:
            continue
        act, rep = bake(arm, bmap, Path(a.raw) / rel / FBX, "TM_" + name, fps, meshes)
        report["bakes"][name] = rep
        clip = sample(arm, act)
        heights = T.sole_heights(skel, clip, soles)
        dz = T.floor_fit(heights)
        clip = T.shift_hips(skel, clip, -dz)
        clip["name"] = "TM_" + name
        write(arm, clip, clip["name"])  # the bake, its planted level on the floor
        whole = S.measure(skel, clip)
        rep.update({"floor_fit_mm": round(dz * 1000.0, 1), "whole_v0": whole["v0"], "whole_c0": whole["c0"],
                    "whole_hips_m_s": whole["hips_m_s"], "whole_ground_m_s": whole["ground_m_s"]})
        loop, cyc = _cut(skel, clip, T.loop_bounds(whole["c0"], LOOP_S))
        dz2 = T.floor_fit(T.sole_heights(skel, loop, soles))  # the loop's own planted level on the floor too
        loop = T.shift_hips(skel, loop, -dz2)
        loop["name"] = f"TM_{name}_Loop"
        cands[name] = numbers(skel, loop, cyc, shape, soles, slot,
                              {"hover_before_fit_mm": round((dz + dz2) * 1000.0, 1),
                               "floor_drift_mm": round(T.floor_drift(heights, fps) * 1000.0, 1)})
        loops[name] = write(arm, loop, loop["name"])
        print("CAND", name, json.dumps({k: cands[name][k] for k in ("v0", "c0", "travel_deg", "yaw_wobble_deg",
                                                                     "seam_cut_deg", "score", "faults")}), flush=True)
    lefts = sorted((c["score"], n) for n, c in cands.items() if c["slot"] == "strafe")
    new_lefts = [n for _, n in lefts if not n.startswith(BASELINE)]
    # the best left strafe mirrored, and the best new one too when a baseline row ranks first
    for best in dict.fromkeys([n for n in [lefts[0][1] if lefts else None, new_lefts[0] if new_lefts else None] if n]):
        src = sample(arm, loops[best])
        mir = S.mirror(skel, src)
        mir["name"] = "TM_" + best.replace("left", "right") + "-mirror_Loop"
        right = mir["name"][3:-5]
        cands[right] = numbers(skel, mir, {**cands[best]["cut"], "mirror_of": best}, shape, soles, "strafe_right",
                               {k: cands[best][k] for k in ("hover_before_fit_mm", "floor_drift_mm")})
        loops[right] = write(arm, mir, mir["name"])
        print("CAND", right, json.dumps({k: cands[right][k] for k in ("v0", "c0", "travel_deg", "score", "faults")}),
              flush=True)
    report["candidates"] = cands
    report["ranking"] = {k: [{"name": n, "score": s, "faults": f} for n, s, f in v]
                         for k, v in T.rank(cands).items()}
    report["order"] = list(cands)
    # the saved file: the character and its new actions, the sheets' camera and floor not yet made
    S_path = out / f"{Path(a.blend).stem}_ttm.blend"
    for act in bpy.data.actions:
        act.use_fake_user = True
    arm.animation_data.action = None
    bpy.ops.wm.save_as_mainfile(filepath=str(S_path), copy=True, compress=True)
    report["saved_blend"] = str(S_path)
    (out / "candidates.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    if not a.no_sheets:
        for n, act in loops.items():
            view = "front" if cands[n]["slot"].startswith("strafe") else "side"
            sheet(arm, [act], out / f"{n}.png", views=[view], follow=True)
        sheet(arm, list(loops.values()), out / "overview.png", follow=True,
              views=["front" if cands[n]["slot"].startswith("strafe") else "side" for n in loops])
    print("DONE", S_path, flush=True)


def main() -> int:
    sys.path.insert(0, str(HERE.parent))
    from runner import blender
    res = blender.run_script(Path(__file__).resolve(), sys.argv[1:], timeout=1800)
    print(*[x for x in (res.stdout or "").splitlines() if x.split(" ", 1)[0] in ("CAND", "DONE")], sep="\n", flush=True)
    if res.returncode:
        print((res.stdout or "")[-3000:], (res.stderr or "")[-3000:], sep="\n", flush=True)
    return res.returncode


if __name__ == "__main__":
    if "bpy" in sys.modules:
        _blender_main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    else:
        sys.exit(main())
