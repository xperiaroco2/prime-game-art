"""The alien clips fitted to a body with its own leg proportions (art #196, T2), in Blender: alien_char_build.py runs
it with `--leg-fit <donor.blend>` before the clip edits, alien_loco.py on the loops it appends from other files when
the build's char.json records a leg_fit.

The clips were made on the donor rig (S4b's body); their rotations are bone-local, so they carry over, but the feet
land elsewhere on legs of other proportions (M1f's: thigh 0.255 m against 0.323, shin 0.420 against 0.403, the ankle
1.9 cm lower, the foot 3.6 cm shorter). Two steps, per action:
1. the Root and Hips location keys (and the armature object's) scaled by the body's leg length over the donor's
   (alien_char_geom.leg_fit, slice --own-proportions' rule): the bob and the travel in proportion to the legs;
2. mode "lowest" (T2, the default): the foot match, per frame the Hips moved along the world's up so the lowest of
   the feet's points (each Foot and Toes bone's head, each Toes bone's tail) is as high as on the donor rig playing
   the unscaled clip, keyed on every frame. On M1f the scale alone left the jog's planted toes rising 4.6 cm over a
   stance of 4 frames (the donor's 1.4 cm), so a contact lasted 2 frames and the loco set's measure found no ground
   speed. With the match the contacts are found, but the feet's horizontal sweep still differs (the sprint measured
   4.60 m/s against the donor's 7.80, and slid 67 mm).
   mode "ik" (T3, `--leg-fit-mode ik`): the feet on the donor's paths. Per frame each ankle's target is its own
   rest place plus the donor's ankle move from rest scaled by the leg ratio (alien_char_geom.foot_target: a planted
   donor foot stays planted, the stride in proportion to the legs), the foot's world turn the donor's, and the thigh
   and shin solved to it (alien_char_geom.reach_knee, the knee in the clip's own bending plane); the UpperLeg,
   LowerLeg and Foot rotations keyed on every frame, the Toes as the clip has them, the Hips as step 1 left them. The
   report gives per action the ankles' worst miss, the frames out of reach, the knee's largest per-frame change
   against the donor's (a pop), the frames whose knee turned to the other side of the hip-ankle line (a flip) and the
   feet's lowest point against the donor's.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alien_char_geom as G  # noqa: E402
import alien_clip_edit as E  # noqa: E402
import slice_actions  # noqa: E402

FEET = ("LeftFoot", "LeftToes", "RightFoot", "RightToes")
TIPS = ("LeftToes", "RightToes")
LEGS = [(f"{s}UpperLeg", f"{s}LowerLeg", f"{s}Foot") for s in ("Left", "Right")]
MODES = ("lowest", "ik")


def _donor(path: str):
    with bpy.data.libraries.load(str(Path(path).resolve()), link=False) as (src, dst):
        dst.armatures = list(src.armatures)
    if len(dst.armatures) != 1:
        raise SystemExit(f"--leg-fit {path}: {len(dst.armatures)} armatures, expected one")
    obj = bpy.data.objects.new("leg_fit_donor", dst.armatures[0])
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _lowest(obj, f0: int, f1: int) -> list[float]:
    """Per frame the lowest of the feet's points (world z, m) of obj playing its assigned action."""
    scene, mw, out = bpy.context.scene, obj.matrix_world, []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        pts = [obj.pose.bones[b].head for b in FEET] + [obj.pose.bones[b].tail for b in TIPS]
        out.append(min((mw @ p).z for p in pts))
    return out


def _legs(obj, f0: int, f1: int) -> dict:
    """Per frame the legs' pose matrices (armature space) of obj playing its assigned action, and their parents'."""
    scene, pb, out = bpy.context.scene, obj.pose.bones, {}
    names = {n for leg in LEGS for n in leg} | {obj.data.bones[u].parent.name for u, _, _ in LEGS}
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        out[f] = {n: pb[n].matrix.copy() for n in names}
    return out


def _rotation_fcurves(act) -> dict:
    fcs = {}
    for bag in E._bags(act):
        for fc in bag.fcurves:
            if fc.data_path.endswith(".rotation_quaternion"):
                fcs[(fc.data_path.split('"')[1], fc.array_index)] = fc
    return fcs


def _ik(arm, donor, act, f0: int, f1: int, theirs: dict, scale: float) -> dict:
    """Mode "ik" on one action (step 1 done): the feet of arm on the donor's ankle paths (theirs: the donor's _legs
    on the unscaled clip); returns the action's measures (see the module)."""
    bones, dbones = arm.data.bones, donor.data.bones
    mw, dmw = arm.matrix_world, donor.matrix_world
    mwi = mw.inverted()
    rot, drot = mw.to_quaternion(), dmw.to_quaternion()
    roti = rot.inverted()
    E._assign(arm, act)
    mine = _legs(arm, f0, f1)
    arm.animation_data.action = None

    def rel(child):  # the child's rest relative to its parent's
        b = bones[child]
        return b.parent.matrix_local.inverted() @ b.matrix_local
    fcs = _rotation_fcurves(act)
    solved: dict[tuple[str, int], list[float]] = {}
    targets: dict[str, dict[int, Vector]] = {}
    rep = {"out_of_reach": 0, "knee_pop_deg": 0.0, "donor_knee_pop_deg": 0.0, "knee_flips": 0}
    for u, lo, ft in LEGS:
        own_rest = tuple(mw @ bones[ft].head_local)
        d_rest = tuple(dmw @ dbones[ft].head_local)
        own_rot = rot @ bones[ft].matrix_local.to_quaternion()
        d_rot_inv = (drot @ dbones[ft].matrix_local.to_quaternion()).inverted()
        la = (bones[lo].head_local - bones[u].head_local).length
        lb = (bones[ft].head_local - bones[lo].head_local).length
        prev, last_angle, last_dangle, last_pole = {}, None, None, None
        for f in range(f0, f1 + 1):
            r, t = mine[f], theirs[f]
            tgt = mwi @ Vector(G.foot_target(own_rest, d_rest, tuple(dmw @ t[ft].translation), scale))
            foot_q = roti @ (drot @ t[ft].to_quaternion()) @ d_rot_inv @ own_rot
            mu, ml = r[u], r[lo]
            hip, knee, ank = mu.translation, ml.translation, r[ft].translation
            k2, ok = G.reach_knee(tuple(hip), tuple(knee), tuple(tgt), la, lb,
                                  fallback_pole=None if last_pole is None else tuple(last_pole))
            knee2 = Vector(k2)
            rep["out_of_reach"] += 0 if ok else 1
            du = (knee - hip).rotation_difference(knee2 - hip)
            mu2 = Matrix.Translation(hip) @ (du.to_matrix() @ mu.to_3x3()).to_4x4()
            dl = (du @ (ank - knee)).rotation_difference(tgt - knee2)
            ml2 = Matrix.Translation(knee2) @ (dl.to_matrix() @ du.to_matrix() @ ml.to_3x3()).to_4x4()
            mf2 = Matrix.Translation(knee2 + (tgt - knee2).normalized() * lb) @ foot_q.to_matrix().to_4x4()
            targets.setdefault(ft, {})[f] = tgt
            ang = G.knee_angle(tuple(hip), tuple(knee2), tuple(tgt))
            dang = G.knee_angle(tuple(t[u].translation), tuple(t[lo].translation), tuple(t[ft].translation))
            if last_angle is not None:
                rep["knee_pop_deg"] = max(rep["knee_pop_deg"], abs(ang - last_angle))
                rep["donor_knee_pop_deg"] = max(rep["donor_knee_pop_deg"], abs(dang - last_dangle))
            axis = (tgt - hip).normalized()
            pole = (knee2 - hip) - axis * (knee2 - hip).dot(axis)
            if pole.length > 1e-4:
                if last_pole is not None and pole.dot(last_pole) < 0.0:
                    rep["knee_flips"] += 1
                last_pole = pole
            last_angle, last_dangle = ang, dang
            for name, m, par in ((u, mu2, r[bones[u].parent.name]), (lo, ml2, mu2), (ft, mf2, ml2)):
                q = (rel(name).inverted() @ par.inverted() @ m).to_quaternion().normalized()
                if name in prev and q.dot(prev[name]) < 0.0:
                    q = -q
                prev[name] = q
                for i in range(4):
                    if (name, i) not in fcs:
                        raise ValueError(f"{act.name}: {name} has no rotation keys")
                    solved.setdefault((name, i), []).extend((float(f), q[i]))
    for key, co in solved.items():  # the solved legs replace their channels whole, one linear key per frame
        fc = fcs[key]
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(co) // 2)
        fc.keyframe_points.foreach_set("co", co)
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        fc.update()
    E._assign(arm, act)  # the ankles measured on the re-evaluated rig
    after = _legs(arm, f0, f1)
    arm.animation_data.action = None
    miss = max((after[f][ft].translation - p).length for ft, per in targets.items() for f, p in per.items())
    rep["ankle_miss_mm"] = round(miss * 1000, 2)
    rep["knee_pop_deg"] = round(rep["knee_pop_deg"], 2)
    rep["donor_knee_pop_deg"] = round(rep["donor_knee_pop_deg"], 2)
    return rep


def fit(arm, donor_path: str, actions: list, mode: str = "lowest") -> dict:
    """Both steps on actions (bpy actions of arm, keyed for the donor's proportions); returns the report: leg_m,
    scale, donor, mode, keys (the scaled ones) and per action the foot match's Hips offset (min and max, cm) and
    miss, or with mode "ik" the IK's measures (see the module)."""
    if mode not in MODES:
        raise ValueError(f"leg fit mode {mode!r}: not one of {MODES}")
    donor = _donor(donor_path)
    rep = G.leg_fit({b.name: tuple(arm.matrix_world @ b.head_local) for b in arm.data.bones},
                    {b.name: tuple(b.head_local) for b in donor.data.bones})
    theirs = {}
    for act in actions:  # the donor on the clips as they were made
        f0, f1 = E._assign(donor, act)
        theirs[act.name] = (f0, f1, _lowest(donor, f0, f1), _legs(donor, f0, f1) if mode == "ik" else None)
    donor.animation_data.action = None
    keys = slice_actions.scale_leg_keys(actions, rep["scale"])
    up_h = (arm.data.bones["Hips"].matrix_local.to_3x3().inverted()
            @ (arm.matrix_world.to_3x3().normalized().inverted() @ Vector((0.0, 0.0, 1.0)))).normalized()
    match = {}
    for act in actions:
        f0, f1, low, legs = theirs[act.name]
        name = act.name.split("|", 1)[-1]
        if mode == "ik":
            m = _ik(arm, donor, act, f0, f1, legs, rep["scale"])
            E._assign(arm, act)
            m["lowest_vs_donor_mm"] = round(max(abs(a - t) for a, t in zip(_lowest(arm, f0, f1), low)) * 1000, 1)
            match[name] = m
            continue
        E._assign(arm, act)
        dz = [t - m for m, t in zip(_lowest(arm, f0, f1), low)]
        E._shift_hips(act, f0, f1, [up_h * d for d in dz], bake=True)
        after = _lowest(arm, f0, f1)
        match[name] = {
            "dz_cm": [round(min(dz) * 100, 2), round(max(dz) * 100, 2)],
            "miss_mm": round(max(abs(a - t) for a, t in zip(after, low)) * 1000, 2)}
    arm.animation_data.action = None
    data = donor.data
    bpy.data.objects.remove(donor)
    bpy.data.armatures.remove(data)
    return {**rep, "donor": str(donor_path), "mode": mode, "actions": len(actions), "keys": keys, "foot_match": match}
