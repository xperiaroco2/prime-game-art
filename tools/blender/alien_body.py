"""The alien parts kit's body (art #196, step S1): the Universal Base Characters male body (Quaternius, CC0) refitted by
measurement to the approved u1 turnaround, with four fingers, three-toe paddle feet and no head (the neck ends in a
standard ring the separate head welds to), on the contract skeleton with Universal Animation Library clips.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/alien_body.py -- \
        --body <Superhero_Male_FullBody.gltf> --clips <UAL1_Standard.glb> --map contract/bone_maps/quaternius.toml \
        --out <dir> [--targets tools/blender/alien_body_targets/chameleon_a.toml]

The targets file holds a concept's numbers (bands, bone lengths and radii, fingers, toes, ring height, neck flare,
Z_ANCHORS mapping u1's fixed heights onto the target's): u1.toml (the default) rebuilds S1c exactly; chameleon_a.toml
is the A chameleon body (the refit route of the bodies_a pilot), measured by alien_body_measure.py. Its new paths:
FINGERS 5 keeps the Little finger, TOE_CENTRES with two entries gives the chameleon's two toe groups, NECK_FLARE the
neck's concave sweep into the trapezius, CROTCH_SMOOTH flattens the base's bulge.

Writes <out>/alien_body.blend (a saved character for `tools/run.py export`), <out>/neck_ring.json and
<out>/fit.json (the measured widths before and after against the targets).

How the fit works (no sculpting, all by numbers; the constants are at the top):
1. Rest rebuild. Each bone b gets an affine map M_b = T(new head) * S_b * T(-old head). S_b scales along world axes
   (the body is in a T-pose, so arms run along X, legs and spine along Z): one factor along the bone (its new length)
   and two across it (its thickness). Fingers scale along their own bone instead (the thumb runs diagonally): shorter
   and thicker (FINGER_LEN, FINGER_THICK), the thumb's root slim (THUMB_ROOT), the index and ring bases spread from
   the middle finger. A child's new head is its parent's map of its old head. Every vertex moves by the weight blend
   of its bones' maps, the same blend its skin uses, so joints stay where they bend. Then the soles go to z = 0.
2. Bands, tubes and seat. The trunk and neck are scaled per height in width (X) and depth (Y) to the u1 targets
   (BANDS; the per-centimetre measures smoothed over height and read between their samples), blended by how much of
   each vertex the trunk bones carry; a soft forward bulge gives the u1 belly. The thigh-calf and upper arm-forearm
   chains are relaxed into smooth tubes (`tubify`: no knee caps, calf or biceps bulges). The seat is pressed to u1's
   depth.
3. Smoothing. A volume-keeping Taubin smooth over the body (not the hands) relaxes the muscle relief. Then the trunk
   between TRUNK_Z is refitted (`trunk_fit`): each section's radius, around a smoothed centre line, moves to a radius
   field over height and angle smoothed along the height, so the trunk is one continuous soft form (no rows on the
   back or waist, no ledge under the chest, no belly crease; one smooth side curve of belly and seat). The neck is
   narrowed to u1 above 1.29 m and laid on the NECK ellipse at the cut.
4. Hands: the Little finger's mesh is removed and its hole closed; its bones stay, unweighted. The hand's skin
   weights are blended with their neighbours' (soft, round bends in a fist) and the palm and fingers get their own
   volume-keeping smooth (no knuckle, tendon or pad relief). Feet: the forefoot is cut at the ball and rebuilt as a
   rounded three-toe paddle whose toe ends round off on a quarter ellipse seen from the side (full, not pinched).
5. The neck is cut below RING_Z and closed by two standard rings of RING_N vertices at equal angles on an ellipse,
   zipped to the cut: the standard neck ring (neck_ring.json: positions, the loop below, the weights).
6. Bones renamed to the contract (the bone map), the leaf bones dropped, Jaw and eye bones added (unweighted).
7. The clips: Universal Animation Library actions (the same 65-bone rig) copied key for key into new actions with
   their own slot on CharacterArmature, the bone names renamed to the contract and the clips to the game's names.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tomllib

import bmesh
import bpy
from mathutils import Matrix, Vector

# The refit's targets (the u1 numbers of S1/S1c, or another concept's): a TOML file in alien_body_targets/, chosen
# by --targets (default u1.toml); its upper-case keys become this module's constants (apply_targets).
TARGETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alien_body_targets")
TARGET_KEYS = ("PX_M", "BANDS", "LENGTH", "RADIUS", "FINGERS", "FINGER_LEN", "FINGER_THICK", "FINGER_SPREAD",
               "HAND_SCALE", "THUMB_ROOT", "FOOT_WIDTH", "TUBE_KEEP", "TUBE_SIGMA", "TOE_HALF", "TOE_LEN", "TOE_H",
               "GROOVE", "TOE_CENTRES", "TOE_SEMI", "NOTCHES", "NOTCH_W", "TOE_SPLAY", "TRUNK_Z", "RING_Z", "NECK",
               "BELLY", "NECK_FLARE", "NECK_FLARE_Z", "Z_ANCHORS", "CROTCH_SMOOTH")
TAUBIN = 80                # iterations of the lambda/mu smooth over the body (not the hands)
FOOT_RINGS = 12            # rings of the rebuilt forefoot (packed towards the toe end)
TOE_END = 0.4              # the last part of the toes' length that rounds off (a quarter ellipse seen from the side)
TOE_TIP = 0.2              # the last ring's height against the paddle's: a small cap closes a round nose
TRUNK_FADE = 0.08
TRUNK_SIGMA = 0.05         # m: the Gaussian along the height that smooths the trunk's radius field (rows, ledges, creases)
TRUNK_BINS = 18            # angle bins over the half section (the body is mirrored)
TRUNK_KEEP = 0.1           # each vertex keeps this power of its own radius against its bin's mean
HAND_TAUBIN = 30           # iterations of the volume-keeping smooth over the hands (palm and fingers)
HAND_WEIGHT_SMOOTH = 6     # passes that blend the hand's skin weights with their neighbours' (soft, rounded bends)
RING_N = 24
RING_STEP = 0.008


def apply_targets(path):
    """Loads a targets file into the module's constants: BANDS widths or depths of 0 become None (not constrained),
    the pairs become tuples. Returns the file's name key."""
    with open(path, "rb") as fh:
        t = tomllib.load(fh)
    missing = [k for k in TARGET_KEYS if k not in t]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")
    g = globals()
    for k in TARGET_KEYS:
        v = t[k]
        if k == "BANDS":
            v = [(b[0], b[1] or None, b[2] or None) for b in v]
        elif k in ("THUMB_ROOT", "TRUNK_Z", "NECK"):
            v = tuple(v)
        g[k] = v
    return t.get("name", os.path.basename(path))


def Z(h):
    """A height of u1's body (the code's fixed heights: seat, belly, neck) on this target's, by Z_ANCHORS."""
    pts = Z_ANCHORS
    for (a0, b0), (a1, b1) in zip(pts, pts[1:]):
        if h <= a1 or a1 == pts[-1][0]:
            return b0 + (b1 - b0) * (h - a0) / (a1 - a0)
    return h


apply_targets(os.path.join(TARGETS_DIR, "u1.toml"))
CLIPS = {  # the game's name: the Universal Animation Library's
    "Idle_Loop": "Idle_Loop", "Walk_Loop": "Walk_Loop", "Jog_Fwd_Loop": "Jog_Fwd_Loop",
    "Sprint_Fwd_Loop": "Sprint_Loop", "Crouch_Idle_Loop": "Crouch_Idle_Loop", "Crouch_Fwd_Loop": "Crouch_Fwd_Loop",
    "Jump_Start": "Jump_Start", "Jump_Air_Loop": "Jump_Loop", "Jump_Land": "Jump_Land",
    "Talk_Upper_Loop": "Idle_Talking_Loop",
}
TRUNK = ("pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "Head")


def kind(name):
    base = name[:-2] if name[-2:] in ("_l", "_r") else name
    for f in ("thumb", "index", "middle", "ring", "pinky"):
        if base.startswith(f):
            return "finger"
    return base


def axis_of(bone_name):
    """The world axis a bone runs along in the T-pose: 0 X (arms, hands, fingers), 1 Y (feet), 2 Z (trunk, legs)."""
    k = kind(bone_name)
    if k in ("clavicle", "upperarm", "lowerarm", "hand", "finger"):
        return 0
    if k in ("foot", "ball"):
        return 1
    return 2


def weights_of(obj):
    names = [g.name for g in obj.vertex_groups]
    out = []
    for v in obj.data.vertices:
        ws = {names[g.group]: g.weight for g in v.groups if g.weight > 1e-4}
        s = sum(ws.values()) or 1.0
        out.append({k: w / s for k, w in ws.items()})
    return out


def dominant(ws):
    return max(ws.items(), key=lambda kv: kv[1])[0] if ws else None


def radial(obj, ws, bones, name):
    """The median distance of the bone's dominant vertices from its axis line."""
    b = bones[name]
    h, t = b["head"], b["tail"]
    d = (t - h).normalized()
    rs = []
    for v, w in zip(obj.data.vertices, ws):
        if dominant(w) == name:
            p = v.co - h
            rs.append((p - d * p.dot(d)).length)
    rs.sort()
    return rs[len(rs) // 2] if rs else None


def band_measure(obj, ws, z, half=0.012):
    xs, ys = [], []
    for v, w in zip(obj.data.vertices, ws):
        if abs(v.co.z - z) < half and sum(w.get(n, 0) for n in TRUNK) > 0.8:
            xs.append(v.co.x)
            ys.append(v.co.y)
    if len(xs) < 16:
        return None
    return max(xs) - min(xs), max(ys) - min(ys), (max(ys) + min(ys)) / 2


def lerp_bands(z, idx):
    pts = [(b[0], b[idx]) for b in BANDS if b[idx] is not None]
    if z <= pts[0][0] or z >= pts[-1][0]:
        return None
    for (z0, a), (z1, b) in zip(pts, pts[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return a + (b - a) * t
    return None


def boundary_loop(bm, zmin):
    """The longest closed boundary loop whose vertices all lie above zmin near the body's centre line (the neck cut)."""
    edges = [e for e in bm.edges if e.is_boundary and all(v.co.z > zmin and abs(v.co.x) < 0.15 for v in e.verts)]
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen, best = set(), []
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v in adj[cur] if v is not prev]
            if not nxt or nxt[0] is start or nxt[0] in seen:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        if len(loop) > len(best):
            best = loop
    return best


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def interp(arr, t, step):
    """Linear interpolation in a profile sampled every step metres."""
    x = max(0.0, min(len(arr) - 1.0, t / step))
    i = min(len(arr) - 2, int(x)) if len(arr) > 1 else 0
    if len(arr) == 1:
        return arr[0]
    f = x - i
    return arr[i] * (1 - f) + arr[i + 1] * f


def tubify(me, ws, pts, names, fade_in, fade_out, step=0.02):
    """Relaxes a limb into a smooth tube: each vertex's distance from the chain's axis (the polyline pts) moves to
    the limb's radius profile smoothed along its length (TUBE_SIGMA), keeping TUBE_KEEP of its own deviation from the
    ring's mean, so knee caps, calf and biceps bulges flatten while the taper stays. The strength fades over fade_in
    metres from the chain's start and fade_out before its end, and with the square of the chain's weight."""
    segs = [(a, b, (b - a).length) for a, b in zip(pts, pts[1:])]
    total = sum(L for _, _, L in segs)
    sel = []
    for i, (v, w) in enumerate(zip(me.vertices, ws)):
        cw = sum(w.get(n, 0.0) for n in names)
        if cw < 0.3:
            continue
        best, acc = None, 0.0
        for a, b, L in segs:
            d = (b - a) / L
            t = max(0.0, min(L, (v.co - a).dot(d)))
            p = a + d * t
            r = (v.co - p).length
            if best is None or r < best[0]:
                best = (r, acc + t, p)
            acc += L
        sel.append((i, cw, best))
    nb = int(total / step) + 2
    sums, cnt = [0.0] * nb, [0] * nb
    for _, cw, (r, t, _) in sel:
        if cw > 0.8:
            k = min(nb - 1, int(round(t / step)))
            sums[k] += r
            cnt[k] += 1
    raw = [sums[k] / cnt[k] if cnt[k] else None for k in range(nb)]
    known = [k for k in range(nb) if raw[k] is not None]
    raw = [raw[k] if raw[k] is not None else raw[min(known, key=lambda j: abs(j - k))] for k in range(nb)]
    sg = TUBE_SIGMA / step
    smooth = []
    for k in range(nb):
        g = [math.exp(-0.5 * ((j - k) / sg) ** 2) for j in range(nb)]
        smooth.append(sum(gj * rj for gj, rj in zip(g, raw)) / sum(g))
    for i, cw, (r, t, p) in sel:
        if r < 1e-5:
            continue
        target = interp(smooth, t, step) * (r / interp(raw, t, step)) ** TUBE_KEEP
        k = cw ** 2 * smoothstep(t / fade_in) * (1 - smoothstep((t - (total - fade_out)) / fade_out))
        co = me.vertices[i].co
        me.vertices[i].co = p + (co - p) * ((r + (target - r) * k) / r)
    return {"length": round(total, 4), "radius_raw": [round(x, 4) for x in raw],
            "radius_smooth": [round(x, 4) for x in smooth]}


def at_cm(table, z):
    """A table sampled per centimetre of height (keys rounded to 0.01 m), read between its samples (linear), so a
    scale taken from it leaves no 1 cm steps (S1b's per-centimetre lookup left rows on the back)."""
    a, b = round(math.floor(z * 100) / 100, 2), round(math.ceil(z * 100) / 100, 2)
    if a not in table or b not in table or a == b:
        return table.get(a, table.get(b, table.get(round(z, 2))))
    t = (z - a) / (b - a)
    va, vb = table[a], table[b]
    if isinstance(va, tuple):
        return tuple(x + (y - x) * t for x, y in zip(va, vb))
    return va + (vb - va) * t


def gauss2(grid, sz, sa):
    """A separable Gaussian over a (height x angle) grid; the angle axis is mirrored at both ends (0 and pi)."""
    nz, na = len(grid), len(grid[0])

    def g1(vals, sig, mirror):
        out, n = [], len(vals)
        for k in range(n):
            acc = tot = 0.0
            for j in range(-int(3 * sig) - 1, int(3 * sig) + 2):
                i = k + j
                if mirror:
                    i = -i - 1 if i < 0 else (2 * n - i - 1 if i >= n else i)
                    i = max(0, min(n - 1, i))
                elif not 0 <= i < n:
                    continue
                w = math.exp(-0.5 * (j / sig) ** 2)
                acc += w * vals[i]
                tot += w
            out.append(acc / tot)
        return out
    rows = [g1(r, sa, True) for r in grid]
    cols = [g1([rows[i][j] for i in range(nz)], sz, False) for j in range(na)]
    return [[cols[j][i] for j in range(na)] for i in range(nz)]


def trunk_fit(verts, tws, step=0.01):
    """Refits the trunk's horizontal sections: around a centre line (the middle of the front and back midline,
    smoothed), each trunk vertex's distance moves to a radius field over (height, angle) smoothed by TRUNK_SIGMA along
    the height, keeping TRUNK_KEEP of its own deviation from its bin's mean. The strength is the cube of the trunk
    bones' weight (the arm and leg roots keep their shape) and fades over TRUNK_FADE at both ends of TRUNK_Z."""
    z0, z1 = TRUNK_Z
    lo, hi = z0 - 0.05, z1 + 0.05
    nz = int(round((hi - lo) / step)) + 1

    def zi(z):
        return (z - lo) / step
    mid = [[] for _ in range(nz)]
    for v, tw in zip(verts, tws):
        if tw > 0.95 and lo <= v.co.z <= hi and abs(v.co.x) < 0.03:
            mid[min(nz - 1, int(round(zi(v.co.z))))].append(v.co.y)
    cy = [(max(m) + min(m)) / 2 if m else None for m in mid]
    known = [k for k in range(nz) if cy[k] is not None]
    cy = [cy[k] if cy[k] is not None else cy[min(known, key=lambda j: abs(j - k))] for k in range(nz)]
    cy = [c[0] for c in gauss2([[c] for c in cy], TRUNK_SIGMA / step, 1.0)]

    def polar(co):
        c = interp(cy, co.z - lo, step)
        dy = co.y - c
        return c, math.hypot(co.x, dy), math.atan2(abs(co.x), -dy)
    na = TRUNK_BINS
    sums = [[0.0] * na for _ in range(nz)]
    cnt = [[0] * na for _ in range(nz)]
    for v, tw in zip(verts, tws):
        if tw > 0.95 and lo <= v.co.z <= hi:
            _, r, a = polar(v.co)
            k, j = min(nz - 1, int(round(zi(v.co.z)))), min(na - 1, int(a / math.pi * na))
            sums[k][j] += r
            cnt[k][j] += 1
    cells = [(k, j) for k in range(nz) for j in range(na) if cnt[k][j]]
    raw = [[sums[k][j] / cnt[k][j] if cnt[k][j] else None for j in range(na)] for k in range(nz)]
    for k in range(nz):
        for j in range(na):
            if raw[k][j] is None:
                kk, jj = min(cells, key=lambda c: (abs(c[0] - k) * 3) ** 2 + (c[1] - j) ** 2)
                raw[k][j] = sums[kk][jj] / cnt[kk][jj]
    smooth = gauss2(raw, TRUNK_SIGMA / step, 1.0)

    def field(grid, z, a):
        x = max(0.0, min(nz - 1.0, zi(z)))
        y = max(0.0, min(na - 1.0, a / math.pi * na - 0.5))
        k, j = min(nz - 2, int(x)), min(na - 2, int(y))
        fx, fy = x - k, y - j
        return ((grid[k][j] * (1 - fy) + grid[k][j + 1] * fy) * (1 - fx)
                + (grid[k + 1][j] * (1 - fy) + grid[k + 1][j + 1] * fy) * fx)
    moved, worst = 0, 0.0
    for v, tw in zip(verts, tws):
        z = v.co.z
        if not (z0 < z < z1) or tw < 0.3:
            continue
        c, r, a = polar(v.co)
        if r < 1e-5:
            continue
        target = field(smooth, z, a) * (r / field(raw, z, a)) ** TRUNK_KEEP
        k = tw ** 3 * smoothstep((z - z0) / TRUNK_FADE) * (1 - smoothstep((z - (z1 - TRUNK_FADE)) / TRUNK_FADE))
        f = (r + (target - r) * k) / r
        worst = max(worst, abs(target - r) * k)
        v.co.x *= f
        v.co.y = c + (v.co.y - c) * f
        moved += 1
    return {"moved": moved, "largest_move_m": round(worst, 4), "centre_y": [round(c, 4) for c in cy[::5]]}


def taubin(verts, weights, iters, lam=0.5, mu=-0.53):
    """A volume-keeping smooth (lambda/mu): each pass pulls a vertex towards its neighbours' mean by lam times its
    weight, then pushes it back by mu, which removes small bumps without shrinking the body."""
    nbrs = [[e.other_vert(v) for e in v.link_edges] for v in verts]
    for _ in range(iters):
        for f in (lam, mu):
            new = []
            for v, w, nb in zip(verts, weights, nbrs):
                if not nb or w <= 0:
                    new.append(v.co.copy())
                    continue
                avg = sum((n.co for n in nb), Vector()) / len(nb)
                new.append(v.co + (avg - v.co) * (f * w))
            for v, c in zip(verts, new):
                v.co = c


def main():
    p = argparse.ArgumentParser(prog="alien_body.py")
    p.add_argument("--body", required=True)
    p.add_argument("--clips", required=True)
    p.add_argument("--map", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--targets", default=os.path.join(TARGETS_DIR, "u1.toml"), help="the refit's targets (TOML)")
    args = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
    report = {"source": args.body, "clips_source": args.clips, "targets": args.targets,
              "target": apply_targets(args.targets)}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.body, merge_vertices=True)  # one vertex per position: no seams to tear
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("SuperHero"))
    for o in list(bpy.data.objects):
        if o not in (arm, body):
            bpy.data.objects.remove(o)
    # Bake the object transforms so the armature and the mesh live in world space.
    for o in (arm, body):
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    body.parent = arm
    body.matrix_parent_inverse = Matrix.Identity(4)

    bones = {b.name: {"head": b.head_local.copy(), "tail": b.tail_local.copy(),
                      "parent": b.parent.name if b.parent else None} for b in arm.data.bones}
    ws = weights_of(body)
    report["before"] = {"verts": len(body.data.vertices), "tris": sum(len(f.vertices) - 2 for f in body.data.polygons)}

    # 1. The rest rebuild.
    meas = {}
    scales = {}
    aniso = {}
    for name in bones:
        k = kind(name)
        ax = axis_of(name)
        if k == "finger":  # scaled along the bone's own direction (the thumb runs diagonally, not along X)
            s_len, s_rad = HAND_SCALE * FINGER_LEN, HAND_SCALE * FINGER_THICK
            if name[:-2] == "thumb_01":  # the thumb's root in the palm stays slim (no pad bulging out of the palm)
                s_len, s_rad = HAND_SCALE * THUMB_ROOT[0], HAND_SCALE * THUMB_ROOT[1]
            d = (bones[name]["tail"] - bones[name]["head"]).normalized()
            m3 = Matrix.Identity(3) * s_rad
            for i in range(3):
                for j in range(3):
                    m3[i][j] += (s_len - s_rad) * d[i] * d[j]
            aniso[name] = m3
        elif k == "hand":
            s_len, s_rad = HAND_SCALE, HAND_SCALE
        elif k in ("foot", "ball"):
            s_len, s_rad = LENGTH[k], FOOT_WIDTH
        else:
            s_len = LENGTH.get(k, LENGTH.get(name, 1.0))
            s_rad = 1.0
            if k in RADIUS:
                r = radial(body, ws, bones, name)
                meas[name] = r
                s_rad = max(0.5, min(1.2, RADIUS[k] / r)) if r else 1.0
        s = [s_rad, s_rad, s_rad]
        s[ax] = s_len
        if k in ("foot", "ball"):  # feet: longer forward and taller, wider in X
            s = [FOOT_WIDTH, s_len, s_len]
        if k == "ball":
            s = [FOOT_WIDTH, s_len, 1.0]
        if name == "neck_01":
            s = [1.0, 1.0, s_len]
        scales[name] = s
    report["radius_measured"] = meas
    new_head, maps = {}, {}
    order = []
    def visit(n):
        order.append(n)
        for c in [c for c, b in bones.items() if b["parent"] == n]:
            visit(c)
    for root in [n for n, b in bones.items() if b["parent"] is None]:
        visit(root)
    for n in order:
        b = bones[n]
        par = b["parent"]
        nh = maps[par] @ b["head"] if par else b["head"].copy()
        if n[:-2] in ("index_01", "ring_01") or (FINGERS == 5 and n[:-2] == "pinky_01"):  # spread: keep gaps
            mid = maps[par] @ bones[f"middle_01{n[-2:]}"]["head"]
            nh.y += (nh.y - mid.y) * FINGER_SPREAD
        new_head[n] = nh
        lin = aniso[n].to_4x4() if n in aniso else Matrix.Diagonal((*scales[n], 1.0))
        maps[n] = Matrix.Translation(nh) @ lin @ Matrix.Translation(-b["head"])
    me = body.data
    newco = []
    for v, w in zip(me.vertices, ws):
        acc = Vector((0, 0, 0))
        for n, wt in w.items():
            acc += wt * (maps[n] @ v.co) if n in maps else wt * v.co
        newco.append(acc)
    for v, c in zip(me.vertices, newco):
        v.co = c
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        eb.use_connect = False
    for eb in arm.data.edit_bones:
        b = bones[eb.name]
        d = b["tail"] - b["head"]
        L = (maps[eb.name] @ b["tail"] - new_head[eb.name]).length
        roll = eb.roll
        eb.head = new_head[eb.name]
        eb.tail = new_head[eb.name] + d.normalized() * L
        eb.roll = roll
    bpy.ops.object.mode_set(mode="OBJECT")
    # Floor: soles at z = 0 (the rebuild shortened the legs, so the body floats).
    lowest = min(v.co.z for v in me.vertices)
    for v in me.vertices:
        v.co.z -= lowest
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        eb.head.z -= lowest
        eb.tail.z -= lowest
    bpy.ops.object.mode_set(mode="OBJECT")
    report["floor_shift"] = lowest

    # 2. Bands: trunk and neck width and depth.
    ws = weights_of(body)
    me = body.data
    zs = sorted({round(v.co.z, 2) for v in me.vertices})
    cur = {}
    for z in zs:
        m = band_measure(body, ws, z, 0.01)
        if m:
            cur[z] = m
    band_report = {}
    # The per-centimetre measures smoothed over height (a 3 cm Gaussian), so the band scales leave no ridges.
    raw_cur = dict(cur)
    for z in raw_cur:
        ws_ = [(math.exp(-0.5 * ((z2 - z) / 0.03) ** 2), m) for z2, m in raw_cur.items() if abs(z2 - z) < 0.1]
        tot = sum(w for w, _ in ws_)
        cur[z] = tuple(sum(w * m[i] for w, m in ws_) / tot for i in range(3))
    for v, w in zip(me.vertices, ws):
        s = sum(w.get(n, 0) for n in TRUNK)
        if v.co.z > Z(0.80):  # the seat: the thighs carry the buttocks
            s = min(1.0, s + sum(w.get(n, 0) for n in ("thigh_l", "thigh_r")) * min(1.0, (v.co.z - Z(0.80)) / 0.06))
        if s < 0.05:
            continue
        z = round(v.co.z, 2)
        if z not in cur:
            continue
        cw, cd, cy = cur[z] if v.co.z > Z(1.25) else at_cm(cur, v.co.z)  # the neck keeps S1b's sampling (its ring)
        tw, td = lerp_bands(v.co.z, 1), lerp_bands(v.co.z, 2)
        # Outside the trunk the arms and the outer thighs keep their shape (a soft falloff, never a cut).
        s *= max(0.0, min(1.0, (0.85 * cw - abs(v.co.x)) / (0.3 * cw)))
        if tw:
            v.co.x *= 1 + s * (min(1.25, max(0.6, tw / cw)) - 1)
        if td:
            v.co.y = cy + (v.co.y - cy) * (1 + s * (min(1.25, max(0.6, td / cd)) - 1))
        # The belly: a soft forward bulge below the chest (front is -Y).
        if Z(0.8) < v.co.z < Z(1.1) and v.co.y < cy:
            t = (v.co.z - Z(0.8)) / (Z(1.1) - Z(0.8))
            fall = math.sin(math.pi * t) ** 2 * math.exp(-(v.co.x / 0.09) ** 2)
            v.co.y -= s * BELLY * fall
    # 2b. The limbs become smooth tubes (no knee bumps, calf or biceps bulges).
    report["tubes"] = {}
    for side in "lr":
        for chain, fin, fout in ((("thigh", "calf"), 0.12, 0.05), (("upperarm", "lowerarm"), 0.06, 0.03)):
            names = [f"{c}_{side}" for c in chain]
            bs = [arm.data.bones[n] for n in names]
            pts = [bs[0].head_local.copy(), bs[1].head_local.copy(), bs[1].tail_local.copy()]
            report["tubes"][names[0]] = tubify(me, ws, pts, names, fin, fout)
    # 2c. The seat: the buttocks pressed into u1's depth (the front line plus the band depth) and smoothed below.
    front = {}
    for v in me.vertices:
        if Z(0.6) < v.co.z < Z(1.05) and abs(v.co.x) < 0.2:
            k = round(v.co.z, 2)
            front[k] = min(front.get(k, 9.0), v.co.y)
    for v in me.vertices:
        z = v.co.z
        if not (Z(0.66) < z < Z(1.02) and abs(v.co.x) < 0.2):
            continue
        depth = lerp_bands(z, 2) or (BANDS[0][2] if z < BANDS[0][0] else None)
        if depth is None or round(z, 2) not in front:
            continue
        yb = at_cm(front, z) + depth
        if v.co.y > yb:
            zw = smoothstep((z - Z(0.66)) / 0.1) * (1 - smoothstep((z - Z(0.94)) / 0.08))
            v.co.y = yb + (v.co.y - yb) * (1 - 0.75 * zw)
    ws = weights_of(body)
    for b in BANDS:
        band_report[str(b[0])] = {"target": [b[1], b[2]], "after": band_measure(body, ws, b[0])}
    report["bands"] = band_report

    # 3-5 in bmesh.
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    deform = bm.verts.layers.deform.verify()
    gi = {g.name: g.index for g in body.vertex_groups}
    def wsum(v, names):
        d = v[deform]
        return sum(d.get(gi[n], 0.0) for n in names if n in gi)
    # 3. The muscle relief (pecs, abs, ribs, clavicles, shoulder blades, glutes, knees) smoothed away by a Taubin
    # smooth over the whole body, fading out over the hands (their fingers keep their shape and gaps).
    hand_names = [n for n in gi if kind(n) in ("hand", "finger")]
    allv = list(bm.verts)
    taubin(allv, [1.0 - min(1.0, 1.5 * wsum(v, hand_names)) for v in allv], TAUBIN)
    # The trunk: one continuous soft form. Its sections are refitted to a radius field smoothed along the height, so
    # the rows on the back and waist, the ledge under the chest and the belly crease go, and the side silhouette of
    # the belly and seat is one smooth curve; a short Taubin blends the refit's edges.
    tws = [wsum(v, TRUNK) for v in allv]
    report["trunk"] = trunk_fit(allv, tws)
    z0, z1 = TRUNK_Z
    taubin(allv, [(tw ** 2 if z0 - 0.04 < v.co.z < z1 + 0.01 else 0.0) for v, tw in zip(allv, tws)], 10)
    # The crotch (CROTCH_SMOOTH > 0): the base's bulge in front smoothed flat by a plain (shrinking) Laplacian
    # around the midline between Z(0.70) and Z(0.84), fading out sideways and at both ends.
    if CROTCH_SMOOTH:
        zc0, zc1 = Z(0.70), Z(0.84)
        cv = [v for v in allv if zc0 < v.co.z < zc1 + 0.06 and abs(v.co.x) < 0.1]
        cw_ = [math.exp(-(v.co.x / 0.045) ** 2) * smoothstep((v.co.z - zc0) / 0.04)
               * (1 - smoothstep((v.co.z - zc1) / 0.06)) for v in cv]
        for _ in range(CROTCH_SMOOTH):
            new = [sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges) for v in cv]
            for v, n, w in zip(cv, new, cw_):
                v.co = v.co + (n - v.co) * 0.5 * w
        report["crotch_smoothed"] = len(cv)
    # The neck: narrowed to u1's width above 1.30 m and, near the cut, laid exactly on the NECK ellipse, so the cut is
    # an even convex loop and the zip to the standard ring is clean.
    zcut = RING_Z - 2 * RING_STEP
    top = [v for v in bm.verts if zcut - 0.025 < v.co.z < zcut + 0.02 and wsum(v, ["neck_01", "Head"]) > 0.5]
    ncy = (max(v.co.y for v in top) + min(v.co.y for v in top)) / 2
    nax = (max(v.co.x for v in top) - min(v.co.x for v in top)) / 2
    nay = (max(v.co.y for v in top) - min(v.co.y for v in top)) / 2
    report["neck_before"] = {"centre_y": ncy, "semi_axes": [nax, nay]}
    for v in bm.verts:
        z = v.co.z
        if z < Z(1.29):
            continue
        dx, dy = v.co.x, v.co.y - ncy
        r = math.hypot(dx, dy)
        if r > 0.14 or r < 1e-6:
            continue
        w = smoothstep((z - Z(1.29)) / (Z(1.36) - Z(1.29))) * (1 - smoothstep((r - 0.085) / 0.05))
        dx *= 1 + w * (NECK[0] / nax - 1)
        dy *= 1 + w * (NECK[1] / nay - 1)
        pw = smoothstep((z - (zcut - 0.03)) / 0.02)
        if pw > 0:
            phi = math.atan2(dx, -dy)
            re = 1.0 / math.sqrt((math.sin(phi) / NECK[0]) ** 2 + (math.cos(phi) / NECK[1]) ** 2)
            rn = math.hypot(dx, dy)
            rt = rn + (re - rn) * pw
            dx, dy = dx * rt / rn, dy * rt / rn
        v.co.x, v.co.y = dx, ncy + dy
    # The neck's flare (NECK_FLARE > 0, the A concepts): under the ring the neck widens in a concave sweep into the
    # trapezius, never a tube. Per centimetre between NECK_FLARE_Z and the cut, the neck's half width (the outermost
    # x of its vertices, the arms' left out) moves to NECK[0] + (NECK_FLARE - NECK[0]) * t ** 2 with
    # t = (zcut - z) / (zcut - NECK_FLARE_Z): slow under the ring, fast towards the shoulders. The depth takes a third
    # of the width's factor; the factors are smoothed over the height and fade in over 3 cm under NECK_FLARE_Z.
    if NECK_FLARE > 0:
        zf, span = NECK_FLARE_Z, zcut - NECK_FLARE_Z
        arm_names = [n for n in gi if kind(n) in ("upperarm", "lowerarm")]
        sel = [v for v in bm.verts if zf - 0.03 < v.co.z < zcut and abs(v.co.x) < 0.22
               and wsum(v, ["neck_01", "Head", "spine_03", "clavicle_l", "clavicle_r"]) > 0.3
               and wsum(v, arm_names) < 0.15]
        cur_hw = {}
        for v in sel:
            k = round(v.co.z, 2)
            cur_hw[k] = max(cur_hw.get(k, 0.0), abs(v.co.x))
        ks = sorted(cur_hw)
        fac = {}
        for k in ks:
            t = max(0.0, min(1.0, (zcut - k) / span))
            fac[k] = max(0.92, min(1.8, (NECK[0] + (NECK_FLARE - NECK[0]) * t * t) / max(cur_hw[k], 1e-4)))
        sm = {k: sum(math.exp(-0.5 * ((k2 - k) / 0.012) ** 2) * fac[k2] for k2 in ks)
              / sum(math.exp(-0.5 * ((k2 - k) / 0.012) ** 2) for k2 in ks) for k in ks}
        for v in sel:
            f = at_cm(sm, v.co.z) or 1.0
            k = smoothstep((v.co.z - (zf - 0.03)) / 0.03) * (1 - smoothstep((v.co.z - (zcut - 0.012)) / 0.012))
            k *= 1 - smoothstep((wsum(v, arm_names) - 0.05) / 0.1)
            v.co.x *= 1 + k * (f - 1)
            v.co.y = ncy + (v.co.y - ncy) * (1 + k * (f - 1) / 3)
        taubin(sel, [0.6] * len(sel), 8)
        report["neck_flare"] = {"half_width_before": {str(k): round(cur_hw[k], 4) for k in ks},
                                "factor": {str(k): round(sm[k], 3) for k in ks}}
    # Hands: remove the Little finger (FINGERS 4).
    pinky = [f"pinky_{i:02d}_{s}" for i in (1, 2, 3) for s in "lr"] + ["pinky_04_leaf_l", "pinky_04_leaf_r"]
    gone = [v for v in bm.verts if wsum(v, pinky) > 0.5] if FINGERS == 4 else []
    report["pinky_removed_verts"] = len(gone)
    bmesh.ops.delete(bm, geom=gone, context="VERTS")
    holes = [e for e in bm.edges if e.is_boundary and abs(e.verts[0].co.x) > 0.5] if gone else []
    filled = bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    newf = filled["faces"]
    bmesh.ops.triangulate(bm, faces=[f for f in newf if len(f.verts) > 4])
    hand_rim = {v for e in holes for v in e.verts if e.is_valid}
    near = {v for v in bm.verts if v.is_valid and any((v.co - r.co).length < 0.02 for r in hand_rim)}
    for _ in range(4):
        bmesh.ops.smooth_vert(bm, verts=list(near), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for v in bm.verts if gone else []:
        d = v[deform]
        for side in "lr":
            hw = 0.0
            for n in pinky:
                if n.endswith(side) and n in gi and gi[n] in d:
                    hw += d[gi[n]]
                    del d[gi[n]]
            if hw > 0:
                d[gi[f"hand_{side}"]] = d.get(gi[f"hand_{side}"], 0.0) + hw
    # Clean soft hands: the skin weights blended with their neighbours' (so the thick fingers bend in a soft round
    # curve and do not crush into a knot), then a volume-keeping smooth over the palm and fingers (no knuckle,
    # tendon or pad relief); separate fingers stay separate, as the smooth follows the mesh's edges.
    hand_v = [v for v in bm.verts if v.is_valid and wsum(v, hand_names) > 0.3]
    hand_g = {gi[n] for n in hand_names}
    for _ in range(HAND_WEIGHT_SMOOTH):
        new = []
        for v in hand_v:
            acc = {}
            nbs = [e.other_vert(v) for e in v.link_edges]
            for src, f in [(v, 0.5)] + [(n, 0.5 / len(nbs)) for n in nbs]:
                for g, w in src[deform].items():
                    acc[g] = acc.get(g, 0.0) + f * w
            new.append(acc)
        for v, acc in zip(hand_v, new):
            d = v[deform]
            keep = sum(w for g, w in d.items() if g not in hand_g)  # the wrist's forearm weights stay as they were
            mix = {g: w for g, w in acc.items() if g in hand_g}
            tot = sum(mix.values()) or 1.0
            for g in [g for g in d.keys() if g in hand_g]:
                del d[g]
            for g, w in mix.items():
                d[g] = w / tot * (1.0 - keep)
    taubin(hand_v, [min(1.0, 2 * wsum(v, hand_names)) for v in hand_v], HAND_TAUBIN)
    # Feet: the forefoot is cut off at the ball and rebuilt as a rounded three-toe paddle. The cut's loop (sorted by
    # angle around its centre) is extruded into FOOT_RINGS rings, each column keeping its place across (u) and up (h)
    # the section while the section widens to TOE_HALF, lowers to TOE_H, rounds off at the end, and reaches further
    # under each of the three toes than at the notches between them; the last ring is capped. The new vertices blend
    # from the cut's weights to the toe bone.
    foot_info = {}
    for side in "lr":
        sx = 1 if side == "l" else -1
        names = [f"foot_{side}", f"ball_{side}", f"ball_leaf_{side}"]
        toes = [v for v in bm.verts if v.is_valid and wsum(v, names[1:]) > 0.25]
        yball = max(v.co.y for v in toes)
        ytip = min(v.co.y for v in toes)
        ycut = yball + 0.01
        faces = [f for f in bm.faces if all(v.co.z < 0.16 and v.co.x * sx > 0.02 and v.co.y < ycut + 0.06
                                            for v in f.verts)]
        geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + faces
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, ycut, 0), plane_no=(0, -1, 0), clear_outer=True)
        edges = [e for e in bm.edges if e.is_boundary and all(abs(v.co.y - ycut) < 1e-4 and v.co.x * sx > 0
                                                               for v in e.verts)]
        cut = list({v for e in edges for v in e.verts})
        if len(cut) < 12 or any(sum(1 for e in v.link_edges if e in edges) != 2 for v in cut):
            raise SystemExit(f"foot {side}: the cut at the ball is not one clean loop ({len(cut)} vertices)")
        xc = (max(v.co.x for v in cut) + min(v.co.x for v in cut)) / 2
        hw0 = (max(v.co.x for v in cut) - min(v.co.x for v in cut)) / 2
        zt0, zb0 = max(v.co.z for v in cut), min(v.co.z for v in cut)
        zc = (zt0 + zb0) / 2
        cut.sort(key=lambda v: math.atan2(v.co.z - zc, v.co.x - xc))
        L = ycut - ytip + 0.01
        cols = [((v.co.x - xc) / hw0, (v.co.z - zb0) / (zt0 - zb0), dict(v[deform])) for v in cut]
        toe_g = gi[f"ball_{side}"]
        prev = cut
        for k in range(1, FOOT_RINGS + 1):
            s = 1 - (1 - k / FOOT_RINGS) ** 1.6  # rings packed towards the end, where the nose rounds off
            g = smoothstep(s / 0.6)
            width = hw0 + (TOE_HALF - hw0) * g
            height = zt0 + (TOE_H - zt0) * smoothstep(s / 0.5)
            # A full, round toe end seen from the side: over the last TOE_END of the length the section shrinks on a
            # quarter ellipse to TOE_TIP of its height, around a centre a third up, so the top comes down and the
            # sole lifts into a rounded nose (no thin pinched tip).
            te = max(0.0, (s - (1 - TOE_END)) / TOE_END)
            end = math.sqrt(1 - (1 - TOE_TIP ** 2) * te * te)
            tw = smoothstep(s / 0.5)
            ring = []
            for u, h, w in cols:
                scal = max(math.sqrt(max(0.0, 1 - ((u - ci) / TOE_SEMI) ** 2)) for ci in TOE_CENTRES)
                reach = L - TOE_LEN * (1 - scal) * g
                notch = max(math.exp(-((u - n) / NOTCH_W) ** 2) for n in NOTCHES) * smoothstep((s - 0.35) / 0.3)
                hs = (height - zb0) * (1 - 0.2 * g * u * u)
                z = zb0 + hs / 3 + (h - 1 / 3) * hs * end - GROOVE * notch * h
                splay = TOE_SPLAY * smoothstep((s - 0.3) / 0.7) * max(-1.0, min(1.0, u / max(TOE_SEMI, 0.2)))
                nv = bm.verts.new((xc + u * width * (1 - 0.1 * (1 - end)) + splay, ycut - s * reach, z))
                d = nv[deform]
                for gidx, wt in w.items():
                    d[gidx] = wt * (1 - tw)
                d[toe_g] = d.get(toe_g, 0.0) + tw
                ring.append(nv)
            n = len(ring)
            for i in range(n):
                bm.faces.new((prev[i], prev[(i + 1) % n], ring[(i + 1) % n], ring[i]))
            prev = ring
        cap = bm.faces.new(prev)
        bmesh.ops.triangulate(bm, faces=[cap], quad_method="BEAUTY", ngon_method="BEAUTY")
        new = [v for v in bm.verts if v.co.y < ycut - 1e-4 and v.co.x * sx > 0.02 and v.co.z < 0.1]
        taubin(new, [0.5] * len(new), 6)
        foot_info[side] = {"centre_x": xc, "half_width_ball": hw0, "half_width_toes": TOE_HALF, "cut_y": ycut,
                           "length_from_cut": L, "cut_count": len(cut)}
    report["feet"] = foot_info
    # 5. The neck ring: cut below RING_Z, build two standard rings of RING_N vertices at equal angles on an ellipse
    # (RING_Z - RING_STEP and RING_Z, quads between them) and zip the cut's uneven edge to the lower one.
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, zcut), plane_no=(0, 0, 1), clear_outer=True)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    cut = boundary_loop(bm, zcut - 0.003)
    report["ring_from_cut"] = len(cut)
    cy, (ax, ay) = ncy, NECK  # the cut lies on the NECK ellipse (step 3)
    taper = 0.98  # the neck narrows slightly towards the head
    # Angles: 0 at the front (-Y), growing towards the character's left (+X).
    ang = lambda co: math.atan2(co.x, -(co.y - cy)) % (2 * math.pi)
    cut.sort(key=lambda v: ang(v.co))
    rings = []
    for level, z in enumerate((RING_Z - RING_STEP, RING_Z)):
        kx, ky = ax * taper ** (level + 1), ay * taper ** (level + 1)
        rings.append([bm.verts.new((kx * math.sin(2 * math.pi * k / RING_N), cy - ky * math.cos(2 * math.pi * k / RING_N), z))
                      for k in range(RING_N)])
    lower, ring_v = rings
    for k in range(RING_N):
        bm.faces.new((lower[k], lower[(k + 1) % RING_N], ring_v[(k + 1) % RING_N], ring_v[k]))
    M, N = len(cut), RING_N
    angA = [ang(v.co) for v in cut]
    angB = [2 * math.pi * k / N for k in range(N)]
    i = j = 0
    while i < M or j < N:
        a_next = angA[(i + 1) % M] + (2 * math.pi if i + 1 >= M else 0)
        b_next = angB[(j + 1) % N] + (2 * math.pi if j + 1 >= N else 0)
        if j >= N or (i < M and a_next <= b_next):
            bm.faces.new((cut[i % M], cut[(i + 1) % M], lower[j % N]))
            i += 1
        else:
            bm.faces.new((cut[i % M], lower[(j + 1) % N], lower[j % N]))
            j += 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Weights: both rings share Neck and Head, so the head's ring can copy them exactly.
    ring_w = {"neck_01": 0.7, "Head": 0.3}
    for v in lower + ring_v:
        d = v[deform]
        for n, w in ring_w.items():
            d[gi[n]] = w
    ring = {
        "count": RING_N, "z": RING_Z, "step": RING_STEP, "centre": [0.0, cy],
        "semi_axes": [ax * taper ** 2, ay * taper ** 2],
        "order": "index k at angle 2*pi*k/count from the front (-Y in Blender, +Z in glTF), towards the character's left (+X)",
        "axes": "Blender (Z up, front -Y); glTF/Godot: (x, z, -y)",
        "loop": [[round(c, 5) for c in v.co] for v in ring_v],
        "loop_below": [[round(c, 5) for c in v.co] for v in lower],
        "weights": {"Neck": ring_w["neck_01"], "Head": ring_w["Head"]},
        "cut_count": report["ring_from_cut"],
    }
    bm.to_mesh(me)
    bm.free()
    wf = weights_of(body)  # the trunk and neck measured again at the end (before the contract names)
    report["bands_final"] = {str(b[0]): {"target": [b[1], b[2]], "after": band_measure(body, wf, b[0])} for b in BANDS}

    # 6. The contract skeleton.
    with open(args.map, "rb") as fh:
        bmap = tomllib.load(fh)
    for leaf in bmap["drop"]:
        if leaf not in arm.data.bones:
            continue
        parent = arm.data.bones[leaf].parent.name
        g, pg = body.vertex_groups.get(leaf), body.vertex_groups.get(parent)
        if g:
            for v in me.vertices:
                for e in v.groups:
                    if e.group == g.index and e.weight > 0:
                        pg.add([v.index], e.weight, "ADD")
            body.vertex_groups.remove(g)
    bpy.ops.object.mode_set(mode="EDIT")
    for leaf in bmap["drop"]:
        if leaf in arm.data.edit_bones:
            arm.data.edit_bones.remove(arm.data.edit_bones[leaf])
    head = arm.data.edit_bones["Head"]
    hz = head.head.z
    for name, off in (("Jaw", (0, -0.03, 0.0)), ("LeftEye", (0.035, -0.08, 0.17)), ("RightEye", (-0.035, -0.08, 0.17))):
        eb = arm.data.edit_bones.new(name)
        eb.head = head.head + Vector(off)
        eb.tail = eb.head + Vector((0, -0.04, 0)) if name != "Jaw" else eb.head + Vector((0, -0.08, -0.03))
        eb.parent = head
    bpy.ops.object.mode_set(mode="OBJECT")
    for old, new in bmap["rename"].items():
        if old in arm.data.bones:
            arm.data.bones[old].name = new
        g = body.vertex_groups.get(old)
        if g:
            g.name = new
    # Little fingers (FINGERS 4): their groups stay present and empty.
    for v in me.vertices if FINGERS == 4 else []:
        for g in body.vertex_groups:
            if "Little" in g.name:
                g.remove([v.index])
    arm.name = "CharacterArmature"
    arm.data.name = "CharacterArmature"
    body.name = "Body"
    body.data.name = "Body"
    body.modifiers.clear()
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    # One material, no texture: S2's hue shader replaces it in Godot.
    mat = bpy.data.materials.new("M_AlienBody")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.16, 0.42, 0.40, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.6
    me.materials.clear()
    me.materials.append(mat)
    for poly in me.polygons:
        poly.use_smooth = True

    # 7. The clips.
    keep = set(bpy.data.actions)
    before_objs = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=args.clips)
    for o in set(bpy.data.objects) - before_objs:
        bpy.data.objects.remove(o)
    found = {}
    rename = bmap["rename"]
    for act in list(bpy.data.actions):
        if act in keep:
            continue
        src = act.name.split("|")[-1]
        game = next((g for g, s in CLIPS.items() if s == src), None)
        if not game:
            bpy.data.actions.remove(act)
            continue
        # The imported action's slot belongs to the imported armature, which the exporter does not bind to this
        # one; so each clip becomes a new action with its own slot on CharacterArmature (as retarget_core.bake does),
        # its F-curves copied key for key with the bone names renamed to the contract.
        clip = bpy.data.actions.new(f"CharacterArmature|{game}")
        slot = clip.slots.new(id_type="OBJECT", name=arm.name)
        bag = clip.layers.new("Layer").strips.new(type="KEYFRAME").channelbags.new(slot)
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        path = fc.data_path
                        if not path.startswith('pose.bones["'):
                            continue
                        bname = path.split('"')[1]
                        if bname in bmap["drop"]:
                            continue
                        new_name = rename.get(bname, bname)
                        nf = bag.fcurves.new(path.replace(f'"{bname}"', f'"{new_name}"', 1), index=fc.array_index,
                                             group_name=new_name)
                        n = len(fc.keyframe_points)
                        nf.keyframe_points.add(n)
                        for attr in ("co", "handle_left", "handle_right"):
                            buf = [0.0] * (2 * n)
                            fc.keyframe_points.foreach_get(attr, buf)
                            nf.keyframe_points.foreach_set(attr, buf)
                        ip = [0] * n
                        fc.keyframe_points.foreach_get("interpolation", ip)
                        nf.keyframe_points.foreach_set("interpolation", ip)
                        nf.update()
        clip.use_fake_user = True
        bpy.data.actions.remove(act)
        act = clip
        found[game] = [act.frame_range[0], act.frame_range[1]]
    report["clips"] = found
    report["clips_missing"] = [g for g in CLIPS if g not in found]
    # The exporter's ACTIONS mode binds an unassigned action through the armature's animation data: assign each clip
    # once (as anim_set.py samples them), then leave the data in place with no action.
    ad = arm.animation_data or arm.animation_data_create()
    for name in found:
        clip = bpy.data.actions[f"CharacterArmature|{name}"]
        ad.action = clip
        ad.action_slot = clip.slots[0]
    ad.action = None

    me.calc_loop_triangles()
    report["after"] = {"verts": len(me.vertices), "tris": len(me.loop_triangles),
                       "height": max(v.co.z for v in me.vertices),
                       "bones": {b.name: [round(c, 4) for c in b.head_local] for b in arm.data.bones}}
    with open(f"{args.out}/neck_ring.json", "w", encoding="utf-8") as fh:
        json.dump(ring, fh, indent=1)
    with open(f"{args.out}/fit.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=lambda o: list(o) if hasattr(o, "__iter__") else str(o))
    bpy.ops.wm.save_as_mainfile(filepath=f"{args.out}/alien_body.blend")


if __name__ == "__main__":
    main()
