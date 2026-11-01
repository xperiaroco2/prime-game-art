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

import alien_fist_envelope as E
import alien_fist_math as F
import alien_hands_math as H

FINGERS = ("Index", "Middle", "Ring")  # the alien's fingers (Little: bones kept, unweighted)
SEGS = ("Proximal", "Intermediate", "Distal")
THUMB_FIT = ("Proximal", "Distal")  # the metacarpal is the thenar pad, not a tube: pushed out, never pulled in
THUMB_ALL = ("Metacarpal", "Proximal", "Distal")
PROP = "fist_weights"
LAST = {}  # per side, the last envelope route's envelope, region and result (for review drivers)


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
            out[act.name] = [list(k) for k in F.weight_plan(entry[1], fist["grip"], fist["lead"])]
    return out


def _digits(arm, side, rest, dom, skin, fist) -> dict:
    """Each digit's stations in the fist grip's posed space: [(centre, radius), ...] root, joints, tip dome."""
    mm = 0.001
    Ma = arm.matrix_world
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
    return digits


def hand_frame(arm, side):
    """The hand's frame in world space: the wrist (the hand bone's head), u wrist -> the fingers' knuckles, w across
    the knuckles index -> ring, n = u x w on the right hand and its mirror on the left; the knuckle line's length."""
    Ma = arm.matrix_world
    h = Ma @ arm.data.bones[f"{side}Hand"].head_local
    kn = [Ma @ arm.data.bones[f"{side}{d}Proximal"].head_local for d in FINGERS]
    mid = sum(kn, Vector()) / len(kn)
    u = (mid - h).normalized()
    w = kn[0] - kn[-1]
    w = (w - u * w.dot(u)).normalized()
    n = u.cross(w) * (1.0 if side == "Right" else -1.0)
    return h, u, w, n, (mid - h).length


def _envelope_moves(arm, body, side, W8, rest, skin, digits, fist):
    """The envelope route (H1l, alien_fist_envelope.py): the fist's envelope from the fitted digits, the palm and the
    shifted thumb; the finger vertices shrink-wrapped onto it and relaxed along it, the rim pinned."""
    import numpy as np
    mm = 0.001
    h, u, w, n, ln = hand_frame(arm, side)
    shift = Vector(fist["thumb_shift_mm"]) * mm
    shift = u * shift.x + w * shift.y + n * shift.z
    th = digits["Thumb"]
    share = [i / (len(th) - 1) for i in range(len(th))]
    digits = dict(digits)
    digits["Thumb"] = [(_t(Vector(c) + shift * s), r) for (c, r), s in zip(th, share)]
    hand = [i for i, x in enumerate(W8) if x.get(f"{side}Hand", 0.0) >= 0.8]
    loc = np.array([[(rest[i] - h).dot(a) for a in (u, w, n)] for i in hand])
    loc = loc[(loc[:, 0] > 0.3 * ln) & (loc[:, 0] < 1.05 * ln)]
    lo, hi = np.percentile(loc, 3, axis=0), np.percentile(loc, 97, axis=0)
    half = (hi - lo) / 2 * fist["env_palm"]
    cen = (lo + hi) / 2
    centre = h + u * cen[0] + w * cen[1] + n * cen[2]
    palm = (tuple(centre), [tuple(u), tuple(w), tuple(n)], tuple(half), float(min(half) * 0.8))
    env = E.Envelope(digits, "Thumb", palm, fist["env_k_mm"] * mm, fist["env_k_core_mm"] * mm,
                     fist["env_k_thumb_mm"] * mm, fist["env_core"], fist["env_mode"], fist["env_inflate"],
                     fist["env_gap_mm"] * mm, fist["env_lip_mm"] * mm)
    names = {f"{side}{d}{s}" for d in FINGERS for s in SEGS} | {f"{side}Thumb{s}" for s in THUMB_FIT}
    fw = [sum(x for b, x in W8[i].items() if b in names) for i in range(len(W8))]
    region = {i for i, x in enumerate(fw) if x > 0.05}
    me = body.data
    rim = {v for e in me.edges for v in e.vertices if (e.vertices[0] in region) != (e.vertices[1] in region)} - region
    ids = sorted(region | rim)
    at = {v: k for k, v in enumerate(ids)}
    edges = np.array([(at[a], at[b]) for a, b in (e.vertices for e in me.edges) if a in at and b in at], dtype=np.int64)
    me.calc_loop_triangles()
    tris = np.array([[at[v] for v in t.vertices] for t in me.loop_triangles if all(v in at for v in t.vertices)],
                    dtype=np.int64)
    P = np.empty((len(ids), 3))
    S = np.empty((len(ids), 3))
    for k, i in enumerate(ids):
        acc = Vector((0, 0, 0))
        for b, x in W8[i].items():
            acc += (skin[b] @ rest[i]) * x
        P[k] = acc
        tw = W8[i].get(f"{side}ThumbDistal", 0.0) + 0.5 * W8[i].get(f"{side}ThumbProximal", 0.0)
        S[k] = acc + shift * tw
    wt = np.array([F.smoothstep((fw[i] - 0.05) / (fist["fade_to"] - 0.05)) if i in region else 0.0 for i in ids])
    # each vertex's digit: the one carrying most of its weight (press: it follows that digit's solid)
    bones = {d: {f"{side}{d}{s}" for s in (SEGS if d != "Thumb" else THUMB_FIT)} for d in env.names}
    owner = np.array([max(range(len(env.names)), key=lambda k: sum(x for b, x in W8[i].items() if b in bones[env.names[k]]))
                      for i in ids])
    X, st = E.wrap(env, P, wt, edges, fist["wrap_rounds"], fist["wrap_lambda"], start=S, owner=owner, tris=tris)
    met = E.metrics(env, X, tris, wt >= 0.999, owner)
    met0 = E.metrics(env, P + (env.project(S, 12, owner) - P) * wt[:, None], tris, wt >= 0.999, owner)  # bare wrap
    LAST[side] = {"env": env, "ids": ids, "P": P, "X": X, "tris": tris, "weight": wt, "owner": owner}
    moves = {i: tuple(X[k] - P[k]) for k, i in enumerate(ids) if np.linalg.norm(X[k] - P[k]) > 1e-6}
    st.update({"moved": len(moves), "surface_err_mm": st["off_surface_mm"], **met,
               "wrap_only": {k: met0[k] for k in ("folded", "min_edge_ratio")},
               "posed": {k: E.metrics(env, P, tris, wt >= 0.999, owner)[k] for k in ("min_edge_ratio", "edge_p1_ratio")},
               "palm_half_mm": [round(x * 1000, 1) for x in half]})
    return moves, st


def _contact_moves(arm, body, side, W8, rest, skin, digits, fist):
    """The contact route (H1q, alien_fist_envelope.contact): the bones curl the fist (`[fist] grip`); the morph only
    closes the side gaps between neighbouring digits and smooths the knuckle tops onto the digits' smooth union
    (`c_k_mm`, the thumb `c_k_thumb_mm`), its moves capped at `c_cap_mm` and smoothed as a field; the contact zones
    sink inside the volume."""
    import numpy as np
    mm = 0.001
    env = E.Envelope(digits, "Thumb", None, fist["c_k_mm"] * mm, 0.0, fist["c_k_thumb_mm"] * mm, 0.0, "merge")
    names = {f"{side}{d}{s}" for d in FINGERS for s in SEGS} | {f"{side}Thumb{s}" for s in THUMB_FIT}
    fw = [sum(x for b, x in W8[i].items() if b in names) for i in range(len(W8))]
    region = {i for i, x in enumerate(fw) if x > 0.05}
    me = body.data
    rim = {v for e in me.edges for v in e.vertices if (e.vertices[0] in region) != (e.vertices[1] in region)} - region
    ids = sorted(region | rim)
    at = {v: k for k, v in enumerate(ids)}
    edges = np.array([(at[a], at[b]) for a, b in (e.vertices for e in me.edges) if a in at and b in at], dtype=np.int64)
    me.calc_loop_triangles()
    tris = np.array([[at[v] for v in t.vertices] for t in me.loop_triangles if all(v in at for v in t.vertices)],
                    dtype=np.int64)
    P = np.empty((len(ids), 3))
    for k, i in enumerate(ids):
        acc = Vector((0, 0, 0))
        for b, x in W8[i].items():
            acc += (skin[b] @ rest[i]) * x
        P[k] = acc
    wt = np.array([F.smoothstep((fw[i] - 0.05) / (fist["fade_to"] - 0.05)) if i in region else 0.0 for i in ids])
    bones = {d: {f"{side}{d}{s}" for s in (SEGS if d != "Thumb" else THUMB_FIT)} for d in env.names}
    owner = np.array([max(range(len(env.names)), key=lambda k: sum(x for b, x in W8[i].items() if b in bones[env.names[k]]))
                      for i in ids])
    X, st = E.contact(env, P, wt, owner, edges, tris, fist["c_cap_mm"] * mm, fist["c_bury_mm"] * mm,
                      fist["c_hide_mm"] * mm, fist["c_smooth"], fist["c_lambda"])
    LAST[side] = {"env": env, "ids": ids, "P": P, "X": X, "tris": tris, "weight": wt, "owner": owner}
    moves = {i: tuple(X[k] - P[k]) for k, i in enumerate(ids) if np.linalg.norm(X[k] - P[k]) > 1e-6}
    st.update({"surface_err_mm": 0.0})
    return moves, st


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
    LAST.clear()
    for side in ("Left", "Right"):
        digits = _digits(arm, side, rest, dom, skin, fist)
        if fist["route"] == "contact":
            moves, st = _contact_moves(arm, body, side, W8, rest, skin, digits, fist)
        elif fist["route"] == "envelope":
            moves, st = _envelope_moves(arm, body, side, W8, rest, skin, digits, fist)
        else:
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
            st["verts"] = len(idx)
        inv_o = Mo.to_3x3().inverted()
        for i, m in moves.items():
            m3 = sum((skin[n].to_3x3() * x for n, x in W8[i].items()), Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0))))
            deltas[i] = inv_o @ (m3.inverted() @ Vector(m))
        stats[side] = {**st,
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
