"""The run fist's shape key on an alien character (art #196, Hands H1j; inside Blender: the maths is alien_fist_math.py).

`add(cfg, arm)` poses the hands file's fist grip (`[fist] grip`), fits each digit's round-cone chain to its own tube
(stations at rest from the digit's vertices, carried to the pose by their bones), moves the finger vertices onto the
fist's surface (alien_fist_math.fist_moves), carries the moves back to rest by the inverse skinning and stores them as
the body's shape key `[fist] morph` (value 0). It also writes each action's weight keys into the body's custom
property `fist_weights` (JSON {action: [[share, weight], ...]}), which alien_loco._export turns into the GLB's weight
channels. alien_hands.py --apply calls it after the grips when the hands file has a `[fist]` table.
"""
from __future__ import annotations

import json

import bpy
from mathutils import Matrix, Vector

import alien_fist_math as F
import alien_hands_math as H

FINGERS = ("Index", "Middle", "Ring")  # the alien's fingers (Little: bones kept, unweighted)
SEGS = ("Proximal", "Intermediate", "Distal")
THUMB_FIT = ("Proximal", "Distal")  # the metacarpal is the thenar pad, not a tube: pushed out, never pulled in
THUMB_ALL = ("Metacarpal", "Proximal", "Distal")
PROP = "fist_weights"


def body_of(arm):
    return max((o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm), key=lambda o: len(o.data.vertices))


def _weights(o, arm):
    names = {vg.index: vg.name for vg in o.vertex_groups if vg.name in arm.data.bones}
    out = []
    for v in o.data.vertices:
        w = {names[g.group]: g.weight for g in v.groups if g.group in names and g.weight > 0}
        s = sum(w.values())
        out.append({k: x / s for k, x in w.items()} if s > 0 else {})
    return out


def _t(v):
    return (float(v[0]), float(v[1]), float(v[2]))


def plans(cfg) -> dict:
    """{action: [[share, weight], ...]} for every action the hands file plans (skipped actions: none, weight 0)."""
    fist = cfg["fist"]
    out = {}
    for act in bpy.data.actions:
        entry = H.clip_plan(cfg, act.name)
        if entry is not None:
            out[act.name] = [list(k) for k in F.weight_plan(entry[1], fist["grip"])]
    return out


def add(cfg, arm) -> dict:
    fist = cfg["fist"]
    mm = 0.001
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.matrix_basis = Matrix.Identity(4)
    for side in ("Left", "Right"):
        for b, q in H.grip_pose(cfg, fist["grip"], side).items():
            if b in arm.pose.bones:
                arm.pose.bones[b].rotation_quaternion = q
    bpy.context.view_layer.update()
    Ma = arm.matrix_world
    skin = {pb.name: Ma @ pb.matrix @ pb.bone.matrix_local.inverted() @ Ma.inverted() for pb in arm.pose.bones}
    body = body_of(arm)
    keys = body.data.shape_keys
    if keys and [k.name for k in keys.key_blocks] not in (["Basis"], ["Basis", fist["morph"]]):
        raise SystemExit(f"{body.name} has shape keys {[k.name for k in keys.key_blocks]}: only the fist's is allowed")
    Mo = body.matrix_world
    W8 = _weights(body, arm)
    rest = [Mo @ v.co for v in body.data.vertices]
    dom = [max(w, key=w.get) if w else "" for w in W8]
    nbr = {}
    for e in body.data.edges:
        a, b = e.vertices
        nbr.setdefault(a, set()).add(b)
        nbr.setdefault(b, set()).add(a)
    deltas, stats = {}, {}
    for side in ("Left", "Right"):
        digits = {}
        for d in FINGERS + ("Thumb",):
            segs = SEGS if d != "Thumb" else THUMB_FIT
            bones = [f"{side}{d}{s}" for s in segs]
            pts = {b: [_t(rest[i]) for i in range(len(rest)) if dom[i] == b] for b in bones}
            allp = [p for b in bones for p in pts[b]]
            st = []
            for j, b in enumerate(bones):
                bone = arm.data.bones[b]
                h, t = _t(Ma @ bone.head_local), _t(Ma @ bone.tail_local)
                c, r = F.stations(allp, h, t, [0.15 if j == 0 else 0.0], fist["band_mm"] * mm)[0]
                st.append((b, c, r))
            # the tip dome: its centre one end radius back from the farthest vertex along the distal bone, on the line
            # (and the taper) of the distal's head and middle stations (the dome itself has too few vertices per slice)
            b = bones[-1]
            bone = arm.data.bones[b]
            h, t = _t(Ma @ bone.head_local), _t(Ma @ bone.tail_local)
            ln = F._len(F._sub(t, h))
            u = F._mul(F._sub(t, h), 1.0 / ln)
            s_tip = max(F._dot(F._sub(p, h), u) for p in pts[b])
            (c0, r0), (cm, rm) = F.stations(allp, h, t, [0.0, 0.5], fist["band_mm"] * mm)
            print("FIST stations", side, d, [round(x[2] * 1000, 2) for x in st], round(r0 * 1000, 2),
                  round(rm * 1000, 2), round(ln * 1000, 1), round(s_tip * 1000, 1), flush=True)
            sm = 0.5 * ln
            r = rm
            for _ in range(3):
                x = (s_tip - r - sm) / sm  # past the middle station, in units of head -> middle
                r = rm + (rm - r0) * x
            c = F._add(cm, F._mul(F._sub(cm, c0), x))
            st.append((b, c, r))
            digits[d] = [(_t(skin[b] @ Vector(c)), r) for b, c, r in st]
        shape = F.Fist(digits, "Thumb", fist["k_mm"] * mm, fist["k_thumb_mm"] * mm)
        names = {f"{side}{d}{s}" for d in FINGERS for s in SEGS} | {f"{side}Thumb{s}" for s in THUMB_ALL}
        own = {f"{side}{d}{s}" for d in FINGERS for s in SEGS} | {f"{side}Thumb{s}" for s in THUMB_FIT}
        fw = {i: sum(x for n, x in W8[i].items() if n in names) for i in range(len(W8))}
        idx = [i for i, x in fw.items() if x > 0.05]
        posed = {}
        for i in idx:
            acc = Vector((0, 0, 0))
            for n, x in W8[i].items():
                acc += (skin[n] @ rest[i]) * x
            posed[i] = _t(acc)
        weight = {i: F.smoothstep((fw[i] - 0.05) / (fist["fade_to"] - 0.05)) for i in idx}
        moves, st = F.fist_moves(posed, weight, shape, {i: [j for j in nbr.get(i, ()) if j in posed] for i in idx},
                                 fist["pull_mm"] * mm, fist["hide_mm"] * mm, fist["relax"], fist["relax_lambda"],
                                 own={i for i in idx if dom[i] in own})
        inv_o = Mo.to_3x3().inverted()
        for i, m in moves.items():
            m3 = sum((skin[n].to_3x3() * x for n, x in W8[i].items()), Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0))))
            deltas[i] = inv_o @ (m3.inverted() @ Vector(m))
        stats[side] = {**st, "verts": len(idx),
                       "radii_mm": {d: [round(r * 1000, 2) for _, r in s] for d, s in digits.items()}}
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    if not body.data.shape_keys:
        body.shape_key_add(name="Basis", from_mix=False)
    kb = body.data.shape_keys.key_blocks.get(fist["morph"]) or body.shape_key_add(name=fist["morph"], from_mix=False)
    basis = body.data.shape_keys.key_blocks["Basis"]
    for i in range(len(body.data.vertices)):
        kb.data[i].co = basis.data[i].co + deltas.get(i, Vector((0, 0, 0)))
    kb.value = 0.0
    body[PROP] = json.dumps(plans(cfg))
    worst = max((s["surface_err_mm"] for s in stats.values()), default=0.0)
    print("FIST", body.name, json.dumps({s: {k: v for k, v in x.items() if k != "radii_mm"} for s, x in stats.items()}),
          flush=True)
    return {"body": body.name, "morph": fist["morph"], "deltas": len(deltas), "surface_err_mm": worst, "sides": stats,
            "max_delta_mm": round(max((d.length for d in deltas.values()), default=0.0) * 1000, 2)}
