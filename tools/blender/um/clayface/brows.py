"""The clay face kit's brows: clay sausages by expression, fitted under the hairline and the fringe, lowered or
shortened under hanging locks and tucked behind them (the per-hair brow_tuck flag, faces/clay_hair.json).
"""
import math

import numpy as np
from mathutils import Vector

from .kit import (
    BROWS, BROW_GAP_K, BROW_HAIR_CLEAR, BROW_LOCK_BEHIND, BROW_LOCK_LID_MARGIN, BROW_PAD_CAP, BROW_PAD_HH_MIN,
    BROW_PAD_TOL, BROW_TUCK_BEHIND, BROW_TUCK_CLEAR, BROW_TUCK_MAX, BROW_TUCK_ROUNDS,
    BROW_TUCK_SKIN_TOL, EYEBALL, LAYOUT, LIDS, LOUD_BROW_HH, NO_BROW_TUCK, loud_k)
from .mesh import FWD, Part, piece_coords, static_piece


def build_brows(face, ctx, lay, coll):
    h, picks = face.h, face.picks
    B = dict(BROWS[picks["brows"]])
    kb = loud_k(picks, "brows")
    if kb != 1.0:  # a loud brow: deeper, a little thicker and longer
        B.update(hh=B["hh"] * min(kb, LOUD_BROW_HH), depth=B["depth"] * kb, len=B["len"] * (1.0 + (kb - 1.0) * 0.35))
    hair_line = hairline_fn(face, ctx, lay)
    mid_x = sum(c.x for c, _ in lay.values()) / len(lay)
    bm_ = face.meta.setdefault("brow_fit", {"gap_widened_mm": 0.0, "lowered_for_hair": 0, "squeezed": 0})
    lift = LAYOUT["brow_lift"]
    part = Part()

    def station(x, z, hh, ang):
        dz, dx = hh * math.cos(ang), -hh * math.sin(ang)
        t, b = (x + dx, z + dz), (x - dx, z - dz)
        return (ctx.on(*t, -0.001), ctx.on(*b, -0.001), ctx.on(*t, lift + B["depth"]), ctx.on(*b, lift + B["depth"]))

    base_B = B
    # round E fix 3 (brief5): no lowering or shortening under locks any more; the built brow is tucked (tuck_brows)
    for side, (c, r) in lay.items():
        s = 1.0 if side == "L" else -1.0
        B = dict(base_B)
        one = B.pop("one", None)
        if one and one["side"] == side:  # ONE RAISED: this brow up and arched, the other normal
            B.update({k: v for k, v in one.items() if k != "side"})
        a0 = B["angle"]
        ln = max(B["len"] * 2 * r, 0.02)
        cx = c.x + s * 0.12 * r
        # a gap of at least BROW_GAP_K x the brow's full height between the two inner ends
        gap_half = s * (cx - s * ln / 2 - mid_x)
        if gap_half < BROW_GAP_K * B["hh"]:
            cx += s * (BROW_GAP_K * B["hh"] - gap_half)
            bm_["gap_widened_mm"] = round(max(bm_["gap_widened_mm"], (BROW_GAP_K * B["hh"] - gap_half) * 1000), 2)
        cz = c.z + r * EYEBALL["lid_scale"] + LAYOUT["brow_gap"] + B["hh"] + B["raise"]
        up_outer = 0.0
        if picks.get("asym") == "brow" and side == "L":
            cz += 0.002
            up_outer = 0.08
        ang = -s * math.radians(a0)
        ca = math.cos(ang)

        def at_t(t, count=False, dz=0.0, end_k=1.0, fit=False):
            """The station at t (-1 inner end, +1 outer end): x, z, half height; dz lowers it (never into the white)."""
            x = cx + s * t * ln / 2
            z = cz - t * math.sin(math.radians(a0)) * ln / 2 + B["arch"] * (1.0 - t * t)
            z += up_outer * max(0.0, s * (x - c.x) - 0.02) if up_outer else 0.0
            hh = B["hh"] * (1.0 - 0.18 * t * t)
            if B.get("taper"):  # thick inner end, thin outer end (t = +1 is the outer end)
                hh = B["hh"] * (1.0 - B["taper"] * max(0.0, t) ** 1.3 - 0.12 * max(0.0, -t) ** 2)
            hh *= end_k
            # never into the white that the resting lid leaves showing (a low inner end over alert lids)
            dx = x - c.x
            vis = c.z + math.sqrt(max(0.0, r * r - dx * dx)) * math.sin(math.radians(LIDS[picks["lid"]])) + 0.002
            # never up against the fringe or hairline (iterator round 2: brows pressed to the hair read as goggles)
            hz = hair_line(x)
            if hz is not None and z + hh * ca > hz - BROW_HAIR_CLEAR:
                z -= z + hh * ca - (hz - BROW_HAIR_CLEAR)
                if count:
                    bm_["lowered_for_hair"] += 1
            if dz > 0.0:  # round E fix 2: lowered under a lock, never closer than 1 mm to the lid gap below
                z = max(z - dz, min(z, vis + hh * ca))
            if fit:  # a brow fitted under locks keeps BROW_LOCK_LID_MARGIN over the lid gap (its rounded mesh sags)
                vis += BROW_LOCK_LID_MARGIN
            low = z - hh * ca
            if low < vis:
                z += vis - low
                if count:
                    face.meta["brow_lifted"] = face.meta.get("brow_lifted", 0) + 1
                if hz is not None and z + hh * ca > hz - BROW_HAIR_CLEAR:  # squeezed between the white and the hair
                    hh = max(0.55 * hh, (hz - BROW_HAIR_CLEAR - vis) / (2 * ca))
                    z = vis + hh * ca
                    if count:
                        bm_["squeezed"] += 1
            return x, z, hh

        t_a, t_b, dz = -1.0, 1.0, 0.0
        fitted = dz > 0.0 or t_a > -1.0 or t_b < 1.0
        sts = []
        n = 5
        xzh, fit_k = [], []
        for k in range(n):
            u = k / (n - 1)
            t = t_a + (t_b - t_a) * u
            # a cut end tapers like a natural end (0.82 of the height at the very end)
            ek = 1.0
            if (k == 0 and t_a > -1.0) or (k == n - 1 and t_b < 1.0):
                ek = 0.82 / max(0.5, 1.0 - 0.18 * t * t)
            c0 = (bm_["lowered_for_hair"], bm_["squeezed"])
            xzh.append(at_t(t, count=True, dz=dz, end_k=ek, fit=fitted))
            if (bm_["lowered_for_hair"], bm_["squeezed"]) != c0:
                fit_k.append(k)
        # brief6 (w3's spikes under the formal updo): stations under a fringe are lowered / squeezed under the hair,
        # but a station in a column where a lock hangs in front keeps its full height and stood up out of the squeezed
        # pad as a thin spike (the inner tips, above the lid domes). The pad's top edge is the highest top of the
        # stations fitted under the hair; with BROW_PAD_CAP no station of that side rises above it (its height shrinks
        # from the top, its lower edge stays: never into the white).
        tops = [z + hh * ca for _, z, hh in xzh]
        pad_top = max(tops[k] for k in fit_k) if fit_k else None
        pads = face.meta.setdefault("brow_pad", {})
        pads[side] = {"top": pad_top, "fitted": len(fit_k), "capped": 0, "cap_mm_max": 0.0}
        if pad_top is not None and BROW_PAD_CAP:
            for k, (x, z, hh) in enumerate(xzh):
                over = z + hh * ca - pad_top
                if over > 1e-6:
                    low = z - hh * ca
                    hh2 = max(BROW_PAD_HH_MIN * hh, (pad_top - low) / (2 * ca))
                    xzh[k] = (x, pad_top - hh2 * ca, hh2)
                    pads[side]["capped"] += 1
                    pads[side]["cap_mm_max"] = round(max(pads[side]["cap_mm_max"], over * 1000), 2)
        sts = [station(x, z, hh, ang) for x, z, hh in xzh]
        part.prism(sts, face.mats["brow"])
    o, _ = static_piece(ctx, f"{h.id}_fb_brows", part.bm, part.mats, coll, sub=1, target=128, cull=False)  # round C: 140 -> 128
    tuck_brows(face, o, ctx)
    return face.add("brows", o, "brow")


def brow_above_pad(face):
    """brief6, the updo list: brow vertices (the built mesh, after the tuck) that rise more than BROW_PAD_TOL above the
    pad's top edge of their side (the highest top of the stations fitted under the hair; sides with no fitted station
    are not measured). -> {"points", "mm_max", "sides_fitted"}"""
    pads = face.meta.get("brow_pad") or {}
    bo = face.pieces.get("brows")
    res = {"points": 0, "mm_max": 0.0, "sides_fitted": sum(1 for v in pads.values() if v.get("top") is not None)}
    if bo is None or not res["sides_fitted"]:
        return res
    co = piece_coords(bo)
    cx = sum(q.x for q in co) / len(co)
    for q in co:
        pt = (pads.get("L") if q.x > cx else pads.get("R")) or {}
        if pt.get("top") is None:
            continue
        over = q.z - pt["top"]
        if over > BROW_PAD_TOL:
            res["points"] += 1
            res["mm_max"] = round(max(res["mm_max"], over * 1000), 2)
    return res


def hair_bvh(face):
    """The worn hair as a BVH in the face's space (mapped back like hairline_fn: h.hair_unscale), or None."""
    from mathutils.bvhtree import BVHTree
    hp = face.h.parts.get("hair") if hasattr(face.h, "parts") else None
    if hp is None:
        return None
    co = np.empty(len(hp.data.vertices) * 3, np.float64)
    hp.data.vertices.foreach_get("co", co)
    M = np.array(hp.matrix_world, dtype=np.float64)
    Q = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    un = getattr(face.h, "hair_unscale", None)
    if un is not None:
        Q = un(Q)
    return BVHTree.FromPolygons([Vector(q) for q in Q], [tuple(p.vertices) for p in hp.data.polygons])


def brow_tucked_by(face):
    """True when the worn hair tucks the brows (faces/clay_hair.json brow_tuck; an unlisted hair tucks)."""
    hp = face.h.parts.get("hair") if hasattr(face.h, "parts") else None
    if hp is None:
        return False
    worn = getattr(face.h, "worn", None) or getattr(face.h, "hair_worn", None)
    return worn is None or worn.split("@")[0] not in NO_BROW_TUCK


def skin_depth(ctx, q):
    """How far q stands in front of the head's skin along FWD (m; negative: under the skin), None off the head."""
    try:
        sp = ctx.surf.hit(q.x, q.z)[0]
    except RuntimeError:
        return None
    if sp is None:
        return None
    return (q - Vector((q.x, sp.y, q.z))).dot(FWD)


def hair_visible_at(ctx, q):
    """True when a hair surface point q is not under the skin (BROW_TUCK_SKIN_TOL; None tol = always)."""
    if ctx is None or BROW_TUCK_SKIN_TOL is None:
        return True
    d = skin_depth(ctx, q)
    return d is None or d > -BROW_TUCK_SKIN_TOL


def tuck_brows(face, o, ctx=None):
    """Round E fix 3 (brief5): the built brow tucked behind the worn hair's locks, like the tucked ears. Only depth
    moves (along -FWD), so the brow keeps its outline, length and place from the front; where no lock is in a vertex's
    column, nothing moves.
    1. Flatten: a vertex with hair in its column (a ray from BROW_TUCK_BEHIND behind it, forward 6 cm) is pressed
       back to BROW_TUCK_CLEAR behind that hair's first (rear) surface, at most BROW_TUCK_MAX: the brow sits behind
       the lock (pressed into the forehead where the lock lies on it).
    2. Seal: the check's poke test (no hair in front within 5 cm, hair within BROW_TUCK_BEHIND behind) at every
       vertex, triangle centre and edge midpoint; a poking point's vertices are all pressed by its need, in rounds.
    meta brow_tuck: pressed vertices, the most pressed (mm), rounds, sides, points still poking."""
    meta = {"verts": 0, "pressed_mm_max": 0.0, "rounds": 0, "sides": 0, "poke_left": 0}
    face.meta["brow_tuck"] = meta
    if not brow_tucked_by(face):
        return
    ht = hair_bvh(face)
    if ht is None:
        return
    me = o.data
    mw = o.matrix_world
    P = [mw @ v.co for v in me.vertices]
    P0 = [q.copy() for q in P]
    polys = [tuple(p.vertices) for p in me.polygons]
    back = -FWD

    def press(j, n):
        done = (P[j] - P0[j]).dot(back)
        P[j] = P[j] + back * max(0.0, min(n, BROW_TUCK_MAX - done))

    for j, q in enumerate(P0):  # 1. flatten under the lock (the first hair surface that is not under the skin)
        start, gone, hit = q + back * BROW_TUCK_BEHIND, 0.0, (None, None, None, None)
        for _ in range(8):
            hit = ht.ray_cast(start, FWD, 0.06 - gone)
            if hit[0] is None or hair_visible_at(ctx, hit[0]):
                break
            gone += hit[3] + 1e-5
            start = hit[0] + FWD * 1e-5
            hit = (None, None, None, None)
        if hit[0] is None:
            continue
        n = BROW_TUCK_BEHIND - (gone + hit[3]) + BROW_TUCK_CLEAR  # how far q is in front of the rear surface, plus the clearance
        if n > 0.0:
            press(j, n)

    def need(q):
        if ht.ray_cast(q + FWD * 1e-5, FWD, 0.05)[0] is not None:
            return 0.0
        if ctx is not None and BROW_TUCK_SKIN_TOL is not None:
            dq = skin_depth(ctx, q)
            if dq is not None and dq < -BROW_TUCK_SKIN_TOL:
                return 0.0  # under the skin: hidden
        hb = ht.ray_cast(q + back * 1e-5, back, BROW_TUCK_BEHIND)
        if hb[0] is None or not hair_visible_at(ctx, hb[0]):
            return 0.0
        return hb[3] + BROW_TUCK_CLEAR

    def points():
        for i, q in enumerate(P):
            yield q, (i,)
        for poly in polys:
            vs = [P[j] for j in poly]
            yield sum(vs, Vector()) / len(vs), poly
            for j in range(len(poly)):
                yield (vs[j] + vs[(j + 1) % len(vs)]) / 2, (poly[j], poly[(j + 1) % len(poly)])
    left = 0
    for rnd in range(BROW_TUCK_ROUNDS + 1):  # 2. seal what still pokes
        push = {}
        for q, vs in points():
            n = need(q)
            if n > 0.0:
                for j in vs:
                    push[j] = max(push.get(j, 0.0), n)
        left = len(push)
        if not push or rnd == BROW_TUCK_ROUNDS:
            break
        meta["rounds"] = rnd + 1
        for j, n in push.items():
            press(j, n)
    moved = [i for i in range(len(P)) if (P[i] - P0[i]).length > 1e-7]
    meta["poke_left"] = left
    if not moved:
        return
    inv = mw.inverted()
    for i in moved:
        me.vertices[i].co = inv @ P[i]
    me.update()
    meta["verts"] = len(moved)
    meta["pressed_mm_max"] = round(max((P0[i] - P[i]).length for i in moved) * 1000, 2)
    cx = sum(q.x for q in P0) / len(P0)
    meta["sides"] = len({P0[i].x > cx for i in moved})


# art #42 round 3 (w3's brows sank 17 mm below the lid's top under hair_w_formal_updo): a lock whose tip ends up to
# this many eye radii above the eye line hangs past the brow, so it is a strand (the brow keeps its height and is
# tucked behind it), not a fringe the brow is lowered and squeezed under (round C's 0.5: 7 lowered, 3 squeezed on w3;
# 1.2: 2 lowered, none squeezed, the brow's front 2.5 mm under the lid's top, as built)
BROW_STRAND_TOP_R = 1.2


def hairline_fn(face, ctx, lay):
    """x -> the lowest z of the hair hanging over the forehead above the eyes near x (None where no hair is there).
    The hair counts where it lies at or in front of the forehead skin (within 6 mm behind it). A face built on an
    unscaled proxy of an x1.3-baked head (clay_cast) gets h.hair_unscale to map the library hair back."""
    hp = face.h.parts.get("hair") if hasattr(face.h, "parts") else None
    # the fixer (2026-10-07, the critic: m3's brows vanished under the hard hat's brim, whose fit ignored it): a worn
    # headwear (h.headwear, set by clay_cast) counts as a fringe too, so the brows come down under its brim; it never
    # counts as a hanging lock (the brows do not cross a hat)
    hw = getattr(face.h, "headwear", None)
    if hp is None and hw is None:
        return lambda x: None
    un = getattr(face.h, "hair_unscale", None)

    def pts(o):
        if o is None:
            return np.zeros((0, 3))
        co = np.empty(len(o.data.vertices) * 3, np.float64)
        o.data.vertices.foreach_get("co", co)
        M = np.array(o.matrix_world, dtype=np.float64)
        Q = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        return un(Q) if un is not None else Q
    P = pts(hp)
    PW = np.concatenate([P, pts(hw)]) if hw is not None else P
    cs = list(lay.values())
    ez = max(c.z for c, _ in cs)
    r = max(r_ for _, r_ in cs)
    cy = min(c.y for c, _ in cs)
    x0, x1 = min(c.x for c, _ in cs) - 2.5 * r, max(c.x for c, _ in cs) + 2.5 * r
    sel = PW[(PW[:, 2] > ez + 0.5 * r) & (PW[:, 2] < ez + 0.09) & (PW[:, 1] < cy + 2.0 * r) & (PW[:, 0] > x0) & (PW[:, 0] < x1)]
    keep = []
    for v in sel:
        try:
            sk = ctx.on(float(v[0]), float(v[2]), 0.0)
        except RuntimeError:  # beside the face: no forehead skin behind this hair point
            continue
        if v[1] <= sk.y + 0.006:
            keep.append(v)
    if not keep:
        return lambda x: None
    K = np.array(keep)
    # Round C: a strand that hangs on down past the eyes in front of the face (a face-framing lock, not a fringe) does
    # not push the brow down: on such columns the brow keeps its own height and the strand crosses over it (round C's
    # first sheets: under the formal updo's locks the brows were squeezed to stubs on 320 of 320 women's faces).
    low = P[(P[:, 2] > ez - 0.035) & (P[:, 2] <= ez + BROW_STRAND_TOP_R * r) & (P[:, 1] < cy + 2.0 * r) & (P[:, 0] > x0) & (P[:, 0] < x1)]
    S = []
    for v in low:
        try:
            sk = ctx.on(float(v[0]), float(v[2]), 0.0)
        except RuntimeError:
            continue
        if v[1] <= sk.y + 0.006:
            S.append(v)
    S = np.array(S) if S else np.zeros((0, 3))
    face.meta["brow_strand_points"] = int(len(S))
    face.meta["brow_fringe_points"] = {"hair_and_hat_in_band": int(len(sel)), "in_front_of_forehead": int(len(K)),
                                       "hat": int(len(pts(hw))) if hw is not None else 0}

    def at(x):
        if len(S) and (np.abs(S[:, 0] - x) < 0.006).any():
            return None
        near = K[np.abs(K[:, 0] - x) < 0.006]
        return float(near[:, 2].min()) if len(near) else None
    return at


def hair_lock_test(face):
    """Round E fix 2 (brief3): station (4 corners: top and bottom at the skin, top and bottom at the front) -> True
    when the brow there pokes out of the hair: a point of the station (5 x 4 over its height and depth) that has no hair
    in front of it (within 5 cm) but hair right behind it (within BROW_LOCK_BEHIND), the check's test (face_sheets
    stage_check). None when no hair is worn. The hair is mapped back like hairline_fn (h.hair_unscale)."""
    from mathutils.bvhtree import BVHTree
    hp = face.h.parts.get("hair") if hasattr(face.h, "parts") else None
    if hp is None:
        return None
    co = np.empty(len(hp.data.vertices) * 3, np.float64)
    hp.data.vertices.foreach_get("co", co)
    M = np.array(hp.matrix_world, dtype=np.float64)
    Q = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    un = getattr(face.h, "hair_unscale", None)
    if un is not None:
        Q = un(Q)
    ht = BVHTree.FromPolygons([Vector(q) for q in Q], [tuple(p.vertices) for p in hp.data.polygons])
    back = -FWD

    def pokes(st):
        ts, bs, tf, bf = st
        for u in (0.0, 0.25, 0.5, 0.75, 1.0):
            sk, fr = ts.lerp(bs, u), tf.lerp(bf, u)
            for d in (0.0, 0.33, 0.67, 1.0):
                p = sk.lerp(fr, d)
                if ht.ray_cast(p + FWD * 1e-5, FWD, 0.05)[0] is not None:
                    continue
                if ht.ray_cast(p + back * 1e-5, back, BROW_LOCK_BEHIND)[0] is not None:
                    return True
        return False
    return pokes
