"""The clay face kit's facial hair: rolled clay strands (brush, handlebar and droopy moustaches, a goatee), the
goatee settled under the lip and the moustache seated under the nose (variant a: the ball raised onto it).
"""
import math
import random

import bmesh
from mathutils import Vector

from .. import clay as cl
from .kit import (
    FACIAL_HAIR, GOATEE_LIP_GAP, LAYOUT, LIP_W, MOUSTACHE_VARIANT, MOUTH_K, NOSE_PUPIL_SHRINK_MIN,
    NOSE_RAISE_FOR_MOUSTACHE, NOSE_RAISE_ON_TOP, STATES, loud_k)
from .mesh import FWD, X, Z, add_keys, data_object, piece_coords
from .mouth import lip_top_at, mouth_extent, outer2d
from .nose import nose_meets_pupils


def strand(ctx, pts, radii, lift_k=0.55, ring=6, wobble=0.08, seed=0, free_from=None):
    """A rolled clay strand: a tube along the points (face-plane (x, z), or 3D Vectors from index free_from on), its
    centre lifted off the skin by lift_k x its radius; pointed tips. Returns (verts, faces)."""
    rng = random.Random(seed)
    cs = []
    for i, (p, r) in enumerate(zip(pts, radii)):
        if isinstance(p, Vector):
            cs.append(p)
        else:
            cs.append(ctx.on(p[0], p[1], r * lift_k))
    verts, faces = [], []
    n = len(cs)
    rings_ = []
    for i in range(n):
        t = (cs[min(n - 1, i + 1)] - cs[max(0, i - 1)]).normalized()
        out = FWD - t * FWD.dot(t)
        if out.length < 1e-6:
            out = Z - t * Z.dot(t)
        out.normalize()
        b = t.cross(out).normalized()
        r = radii[i] * (1.0 + rng.uniform(-wobble, wobble))
        if i in (0, n - 1):
            rings_.append([len(verts)])
            verts.append(cs[i] + t * (r * (0.6 if i else -0.6)))
            continue
        row = []
        for k in range(ring):
            a = 2 * math.pi * k / ring
            row.append(len(verts))
            verts.append(cs[i] + (out * math.cos(a) + b * math.sin(a)) * r)
        rings_.append(row)
    for i in range(n - 1):
        A, B = rings_[i], rings_[i + 1]
        if len(A) == 1:
            for k in range(ring):
                faces.append((A[0], B[(k + 1) % ring], B[k]))
        elif len(B) == 1:
            for k in range(ring):
                faces.append((A[k], A[(k + 1) % ring], B[0]))
        else:
            for k in range(ring):
                faces.append((A[k], A[(k + 1) % ring], B[(k + 1) % ring], B[k]))
    return verts, faces


def moustache_line(ctx, M):
    """The moustache's centre line at the mouth's middle: the lip's highest point there, a clearance and a radius."""
    top = lip_top_at(ctx, M, ctx.mx)
    return top + LAYOUT["moustache_clear"]


def build_facial_hair(face, ctx, M, coll):
    h, picks = face.h, face.picks
    kinds = FACIAL_HAIR[picks.get("facial_hair", "none")]
    if not kinds:
        return None, None
    mx, mz = ctx.mx, ctx.mz
    clear = LAYOUT["moustache_clear"]
    kf = loud_k(picks, "facial_hair")
    wmax = max(M["w"] * st.get("w", 1.0) for st in M["states"].values()) * MOUTH_K + LIP_W * MOUTH_K
    allv, allf = [], []
    centre_z = None
    seed = 0
    goatee = None  # (first vertex, vertex count, {state: shift}) when a goatee is built

    def put(pts, radii, **kw):
        nonlocal seed
        # keep every station's lower surface above the lip (every state) by the clearance
        fixed = []
        radii = [r * kf for r in radii]
        for (x, z), r in zip(pts, radii):
            lt = lip_top_at(ctx, M, x)
            if lt is not None:
                z = max(z, lt + clear + r)
            fixed.append((x, z))
        vs, fs = strand(ctx, fixed, radii, seed=seed, **kw)
        seed += 1
        b = len(allv)
        allv.extend(vs)
        allf.extend(tuple(i + b for i in f) for f in fs)
        return fixed

    base = moustache_line(ctx, M)
    for kind in kinds:
        if kind == "brush":
            W = max(0.026, M["w"] * MOUTH_K * 1.05)
            thin = MOUSTACHE_VARIANT == "b"  # brief3 (b): a thin low bridge in the middle, the top row starts off-centre
            for s in (1.0, -1.0):
                put([(mx + s * 0.0015, base + (0.0026 if thin else 0.004)), (mx + s * 0.35 * W, base + 0.0036),
                     (mx + s * 0.7 * W, base + 0.002), (mx + s * 1.0 * W, base - 0.0005), (mx + s * 1.12 * W, base - 0.002)],
                    [0.0022 if thin else 0.0035, 0.0036 if thin else 0.004, 0.0039, 0.0032, 0.002])
                if thin:
                    put([(mx + s * 0.3 * W, base + 0.0095), (mx + s * 0.5 * W, base + 0.0092), (mx + s * 0.7 * W, base + 0.008),
                         (mx + s * 0.88 * W, base + 0.0055), (mx + s * 0.98 * W, base + 0.003)],
                        [0.0022, 0.003, 0.0032, 0.0027, 0.0017])
                else:
                    put([(mx + s * 0.002, base + 0.0105), (mx + s * 0.32 * W, base + 0.0102), (mx + s * 0.62 * W, base + 0.0085),
                         (mx + s * 0.88 * W, base + 0.0055), (mx + s * 0.98 * W, base + 0.003)],
                        [0.0028, 0.0034, 0.0033, 0.0027, 0.0017])
            centre_z = base + 0.0045
        elif kind == "handlebar":
            W = max(0.025, M["w"] * MOUTH_K * 1.0)
            for s in (1.0, -1.0):
                thin = MOUSTACHE_VARIANT == "b"  # brief3 (b): thinner and lower in the middle
                put([(mx + s * 0.001, base + (0.003 if thin else 0.0045)), (mx + s * 0.35 * W, base + 0.0042), (mx + s * 0.75 * W, base + 0.004),
                     (mx + s * 1.05 * W, base + 0.0065), (mx + s * 1.22 * W, base + 0.0125), (mx + s * 1.2 * W, base + 0.0185),
                     (mx + s * 1.1 * W, base + 0.0195)],
                    [0.0024 if thin else 0.0042, 0.004 if thin else 0.0045, 0.0038, 0.003, 0.0024, 0.0019, 0.0012])
            centre_z = base + 0.0045
        elif kind == "droopy":
            W = max(0.024, M["w"] * MOUTH_K * 0.95)
            for s in (1.0, -1.0):  # thick at the lip, thinning down the chin, the corner rounded (not a frame of tubes)
                xo = mx + s * (wmax + 0.0015 + 0.0072 * kf)
                put([(mx + s * 0.001, base + 0.0055), (mx + s * 0.45 * W, base + 0.0052), (mx + s * 0.82 * W, base + 0.0042),
                     (xo - s * 0.0035, base + 0.0012), (xo, base - 0.0035), (xo + s * 0.0012, mz - 0.009),
                     (xo + s * 0.0015, mz - 0.018), (xo + s * 0.001, mz - 0.025)],
                    [0.0062, 0.0072, 0.0072, 0.007, 0.0064, 0.0055, 0.0042, 0.0024])
            centre_z = base + 0.005
        elif kind == "goatee":
            # Iterator round 1: one tapered clay lump (a teardrop with three shallow grooves) under the lower lip,
            # not three pellets. It hangs from just below the lowest mouth state and leans out with the chin.
            # Iterator round 1 (resumed): the lump hung below the LOWEST mouth state (the open "a"), so at rest it
            # sat on the chin's underside, far from the lip. It now hangs 1.5 mm under the lower lip of each mouth
            # state: shape keys mouth_<state> move it down with the lip (it rides the jaw); never above its rest.
            def low_at(st_name):
                zs = [z for x, z in outer2d(M, M["states"][st_name], mx, mz) if abs(x - mx) <= 0.012]
                return min(zs)
            _, lo_all = mouth_extent(ctx, M, half_x=0.012)
            lo_lip = min(low_at(sn) for sn in STATES)
            buck = min(0.0, lo_all - lo_lip)  # buck teeth hanging below every lip state
            lo_rest = low_at("rest") + buck
            top = lo_rest - GOATEE_LIP_GAP
            face.meta["goatee_geo_mm"] = {"mouth_z": round(mz * 1000, 1), "lip_low_rest": round(lo_rest * 1000, 1),
                                          "lip_low_all": round(lo_lip * 1000, 1), "buck": round(buck * 1000, 1),
                                          "top": round(top * 1000, 1)}
            # a tuft hanging from under the lip (the bean's chin is short: a round lump read as a pellet)
            hx_, hy_, hz_ = 0.0125 * kf, 0.0078 * kf, 0.0115 * kf  # iterator round 2: 23 mm long (was 33)
            cz_ = top - hz_
            # laid ON the chin: its long axis runs from the skin point under the lip down the chin's slope (the
            # chin falls back under the mouth; a lump hung plumb sank its top into the skin and showed only its tip)
            def frame(t):
                p_top, p_bot = ctx.on(mx, t, 0.0), ctx.on(mx, t - 2.0 * hz_, 0.0)
                up_ = (p_top - p_bot).normalized()
                fwd_ = (FWD - up_ * FWD.dot(up_)).normalized()
                return (p_top + p_bot) * 0.5 + fwd_ * hy_ * 0.45, up_, fwd_
            pc, up_ax, fwd_ax = frame(top)
            shifts = {}
            for sn in STATES:
                if sn == "rest":
                    continue
                top_s = min(top, low_at(sn) + buck - GOATEE_LIP_GAP)
                shifts[sn] = frame(top_s)[0] - pc
            # Iterator round 2 (the look critic: a black bead under the lip): a FLAT tapered wedge, widest along the lower
            # lip line and narrowing to a pointed tip down the chin, lying close on the chin (depth 4.5 mm at the top).
            bm = bmesh.new()
            n_r, n_s = 10, 6
            wtop, dtop = 0.0125 * kf, 0.0048 * kf
            rows_ = []
            z_top = top - 0.001
            for i in range(n_s):
                t = i / (n_s - 1)  # 0 at the lip line, 1 near the tip
                a_ = wtop * (1.0 - t ** 1.4) ** 0.9 * (1.0 - 0.55 * t) + 0.0012  # a soft shield, not a triangle
                b_ = dtop * (1.0 - 0.55 * t) + 0.0006
                # each row sits on the chin itself (a straight wedge on the curved chin sank its top under the skin)
                zt = z_top - 2.0 * hz_ * t
                sp = ctx.on(mx, zt, 0.0)
                ct = ctx.on(mx, zt, b_ * 0.6 + 0.0012)  # clear of the clay skin's own lumps
                out_t = (ct - sp).normalized()
                row = []
                for k in range(n_r):
                    ang_ = 2 * math.pi * k / n_r
                    x, y = math.cos(ang_), math.sin(ang_)
                    flat = 0.35 if y > 0 else 1.0  # the back (against the chin) is flat
                    groove = 1.0 - 0.08 * max(0.0, math.cos(3.0 * ang_)) if y < 0 else 1.0
                    row.append(bm.verts.new(ct + X * (x * a_ * groove) + out_t * (-y * b_ * flat * groove)))
                rows_.append(row)
            top_c = bm.verts.new(ctx.on(mx, top, dtop * 0.5 + 0.0012))
            tip = bm.verts.new(ctx.on(mx, z_top - 2.0 * hz_ - 0.004, 0.0009))
            for k in range(n_r):
                j = (k + 1) % n_r
                bm.faces.new((top_c, rows_[0][j], rows_[0][k]))
                for i in range(n_s - 1):
                    bm.faces.new((rows_[i][k], rows_[i][j], rows_[i + 1][j], rows_[i + 1][k]))
                bm.faces.new((rows_[-1][k], rows_[-1][j], tip))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            # slide it up the chin until its highest point sits at `top` (1.5 mm under the lowest lip at rest)
            k_up = (top - max(v.co.z for v in bm.verts)) / max(up_ax.z, 0.3)
            for v in bm.verts:
                v.co += up_ax * k_up
            b = len(allv)
            bm.verts.index_update()
            allv.extend(v.co.copy() for v in bm.verts)
            allf.extend(tuple(v.index + b for v in f.verts) for f in bm.faces)
            goatee = (b, len(bm.verts), shifts)
            bm.free()
    o = data_object(f"{h.id}_fb_fhair", allv, allf, [0] * len(allf), [face.mats["fhair"]], coll)
    cl.lump(o, 0.0004, freq=90.0, seed=31)
    cl.smooth_shade(o.data)
    if goatee is not None:
        g0, gn, shifts = goatee
        base = [v.co.copy() for v in o.data.vertices]
        keys = {}
        for sn, d in shifts.items():
            keys[f"mouth_{sn}"] = [c + d if g0 <= i < g0 + gn else c for i, c in enumerate(base)]
        add_keys(o, keys, None)
        face.meta["goatee_drop_mm"] = {sn: round(-d.z * 1000, 1) for sn, d in shifts.items()}
        mo = face.pieces.get("mouth")
        if mo is not None:
            mzs = [(mo.matrix_world @ v.co).z for v in mo.data.vertices]
            gzs = [(o.matrix_world @ o.data.vertices[i].co).z for i in range(g0, g0 + gn)]
            face.meta.setdefault("goatee_geo_mm", {}).update(
                mouth_piece_low=round(min(mzs) * 1000, 1), goatee_high=round(max(gzs) * 1000, 1),
                goatee_low=round(min(gzs) * 1000, 1))
        face.goatee_range = (g0, gn)
    face.add("fhair", o, "fhair")
    return o, centre_z


def settle_goatee(face, step=0.0005, most=0.008):
    """Lowers the goatee in 0.5 mm steps (basis and every mouth key alike) until it touches no mouth or teeth state,
    state by state (on a head whose chin falls away fast a lump laid under the lip can still meet the lip's
    underside). Records meta["goatee_lowered_mm"]."""
    from mathutils.bvhtree import BVHTree
    rng_ = getattr(face, "goatee_range", None)
    if rng_ is None:
        return 0.0
    g0, gn = rng_
    o = face.pieces["fhair"]
    polys = [tuple(p.vertices) for p in o.data.polygons if g0 <= p.vertices[0] < g0 + gn]  # the goatee's own faces
    keys = [None] + [f"mouth_{s}" for s in STATES if s != "rest"]
    others = []
    for k in ("mouth", "teeth"):
        m = face.pieces.get(k)
        if m is not None:
            mp = [tuple(p.vertices) for p in m.data.polygons]
            others.append({key: BVHTree.FromPolygons(piece_coords(m, key), mp) for key in keys})
    lowered = 0.0
    while lowered < most:
        hit = False
        for key in keys:
            t = BVHTree.FromPolygons(piece_coords(o, key), polys)
            if any(t.overlap(oth[key]) for oth in others):
                hit = True
                break
        if not hit:
            break
        for kb in o.data.shape_keys.key_blocks:
            for i in range(g0, g0 + gn):
                kb.data[i].co.z -= step
        for i in range(g0, g0 + gn):
            o.data.vertices[i].co.z -= step
        lowered += step
    o.data.update()
    face.meta["goatee_lowered_mm"] = round(lowered * 1000, 1)
    return lowered


def lift_moustache(face, ctx, step=0.0005, most=0.004, ramp=0.008):
    """Lifts a moustache's end off a mouth state it meets, as settle_goatee lowers the goatee (art #42 part B): the
    stations keep the lip outline's top clear (build_facial_hair put), but not the lip's own thickness at a raised
    corner beyond them; on the repo's head a loud brush met the smirk's raised corner in state e (kit-check M: 5 faces,
    4 triangle pairs each, 26 mm out from the middle). Per side that touches, the moustache's vertices from `ramp`
    inside the innermost touching point outward rise in 0.5 mm steps (a linear ramp from 0 to the full step; basis
    and every key alike) until no state touches, at most `most`. The goatee is not touched. Records
    meta["moustache_lift_mm"] ({"L"|"R": mm}, empty when nothing touched)."""
    from mathutils.bvhtree import BVHTree
    o = face.pieces.get("fhair")
    mo = face.pieces.get("mouth")
    face.meta["moustache_lift_mm"] = {}
    if o is None or mo is None:
        return {}
    g0, gn = getattr(face, "goatee_range", None) or (0, 0)
    mine = [q for q in o.data.polygons if not g0 <= q.vertices[0] < g0 + gn]
    if not mine:
        return {}
    polys = [tuple(q.vertices) for q in mine]
    keys = [None] + [f"mouth_{s}" for s in STATES if s != "rest"]
    others = []
    for k in ("mouth", "teeth"):
        m = face.pieces.get(k)
        if m is not None:
            mp = [tuple(q.vertices) for q in m.data.polygons]
            others.append({key: BVHTree.FromPolygons(piece_coords(m, key), mp) for key in keys})
    mx = ctx.mx
    inv = o.matrix_world.inverted()
    lifted = {}

    def touching():
        """The innermost |x - mx| of the touching moustache faces per side ({1.0 | -1.0: offset})."""
        out = {}
        for key in keys:
            co = piece_coords(o, key)
            t = BVHTree.FromPolygons(co, polys)
            for oth in others:
                for a, _b in t.overlap(oth[key]):
                    c = sum((co[j] for j in polys[a]), co[polys[a][0]] * 0) / len(polys[a])
                    s_ = 1.0 if c.x >= mx else -1.0
                    out[s_] = min(out.get(s_, 1.0), abs(c.x - mx))
        return out

    hit = touching()
    while hit:
        for s_, x0 in hit.items():
            if lifted.get(s_, 0.0) >= most - 1e-9:
                continue
            up = (inv.to_3x3() @ Vector((0.0, 0.0, step)))
            for i, v in enumerate(o.data.vertices):
                if g0 <= i < g0 + gn:
                    continue
                d = (o.matrix_world @ v.co).x - mx
                if d * s_ <= 0:
                    continue
                w = min(1.0, max(0.0, (abs(d) - (x0 - ramp)) / ramp))
                if w <= 0.0:
                    continue
                v.co += up * w
                if o.data.shape_keys:
                    for kb in o.data.shape_keys.key_blocks:
                        kb.data[i].co += up * w
            lifted[s_] = lifted.get(s_, 0.0) + step
        o.data.update()
        if all(lifted.get(s_, 0.0) >= most - 1e-9 for s_ in hit):
            break
        hit = touching()
    face.meta["moustache_lift_mm"] = {("L" if s_ > 0 else "R"): round(v_ * 1000, 1) for s_, v_ in lifted.items()}
    return lifted


def seat_moustache(face, ctx, M=None, bin_w=0.001):
    """Round E fix (2026-10-09, brief2 FIX 1): every moustache sits as one piece BELOW the nose. The nose is built on
    the moustache's centre line, so its underside sank into the moustache (the ball split the brush into two pads).
    The moustache keeps its lower edge (above the upper lip by moustache_clear, as before) and its height shrinks per
    1 mm column of x until every vertex stays moustache_clear under the nose's actual underside (vertical rays into the
    nose from a ring of offsets, then checked as a 3D distance both ways). The squash is eroded and blurred across
    columns, so the moustache dips smoothly under the nose and stays one piece. The goatee is not touched.
    Records meta["moustache_seat"]: squash_min (1 = untouched), columns squashed, nose clearance mm (unscaled)."""
    from mathutils.bvhtree import BVHTree
    o, nose = face.pieces.get("fhair"), face.pieces.get("nose")
    if o is None or nose is None:
        return None
    g0, gn = getattr(face, "goatee_range", None) or (0, 0)
    me = o.data
    idx = [i for i in range(len(me.vertices)) if not (g0 <= i < g0 + gn)]
    if not idx:
        return None
    clear = LAYOUT["moustache_clear"]
    mw = o.matrix_world
    mwi = mw.inverted()
    npolys = [tuple(p.vertices) for p in nose.data.polygons]
    ncoords = piece_coords(nose)
    nt = BVHTree.FromPolygons(ncoords, npolys)
    mpolys = [tuple(p.vertices) for p in me.polygons if not (g0 <= p.vertices[0] < g0 + gn)]
    blocks = list(me.shape_keys.key_blocks) if me.shape_keys else []
    info = {"squash_min": 1.0, "columns": 0, "cannot_clear": 0, "passes": 0}
    for pass_ in range(0 if MOUSTACHE_VARIANT == "a" else 5):
        W = piece_coords(o)
        ring = clear + 0.0005
        offs = [(0.0, 0.0)] + [(ring * math.cos(a), ring * math.sin(a)) for a in [k * math.pi / 4 for k in range(8)]]
        z0 = min(W[i].z for i in idx) - 0.01
        lim = {}
        for i in idx:
            p = W[i]
            hz = None
            for dx, dy in offs:
                hit = nt.ray_cast(Vector((p.x + dx, p.y + dy, z0)), Vector((0.0, 0.0, 1.0)), 0.2)
                if hit[0] is not None:
                    hz = hit[0].z if hz is None else min(hz, hit[0].z)
            ce = clear * (1.0 + 0.25 * pass_)
            z = p.z if hz is None else min(p.z, hz - ce)
            # beside a steep nose side the vertical gap is not the distance: step down until it is clear in 3D
            for _ in range(80):
                if nt.find_nearest(Vector((p.x, p.y, z)), ce)[0] is None:
                    break
                z -= 0.00025
            if z < p.z - 1e-7:
                lim[i] = z
        col = lambda x: int(math.floor((x - ctx.x) / bin_w))  # noqa: E731
        piv = {}
        for i in idx:
            if W[i].z >= ctx.mz:  # the upper lip's moustache (a droopy's legs below the mouth keep their own)
                c = col(W[i].x)
                piv[c] = min(piv.get(c, 9.0), W[i].z)
        need = {}
        for i, lz in lim.items():
            c = col(W[i].x)
            zb = piv.get(c)
            if zb is None or W[i].z <= lz:
                continue
            f = (lz - zb) / max(W[i].z - zb, 1e-6)
            if f < 0.05:
                info["cannot_clear"] += 1
                f = 0.05
            need[c] = min(need.get(c, 1.0), f)
        if not need:
            break
        cols = sorted(piv)
        if M is not None and pass_ == 0:
            # first SEAT it lower: per column down toward the upper lip (its top over every state + moustache_clear),
            # as far as the nose needs, smoothed across columns; what is still too high is then squashed
            want = {}
            for i, lz in lim.items():
                c = col(W[i].x)
                want[c] = max(want.get(c, 0.0), W[i].z - lz)
            room = {}
            for c in cols:
                lt = lip_top_at(ctx, M, ctx.x + (c + 0.5) * bin_w)
                room[c] = max(0.0, piv[c] - (lt + clear)) if lt is not None else 0.0
            wd = {c: max(want.get(c + d, 0.0) for d in range(-3, 4)) for c in cols}
            drop = {c: min(room[c], sum(wd.get(c + d, 0.0) for d in range(-2, 3)) / 5.0) for c in cols}
            info["lowered_mm_max"] = round(max(drop.values()) * 1000, 2)
            for i in idx:
                dzc = drop.get(col(W[i].x), 0.0)
                w_ = min(1.0, max(0.0, (W[i].z - (ctx.mz - 0.006)) / 0.006))  # a droopy's legs keep their ends
                if dzc * w_ > 0:
                    dv = mwi.to_3x3() @ Vector((0.0, 0.0, -dzc * w_))
                    me.vertices[i].co += dv
                    for kb in blocks:
                        kb.data[i].co += dv
            me.update()
            continue
        ero = {c: min(need.get(c + d, 1.0) for d in range(-3, 4)) for c in cols}
        fs_ = {c: sum(ero.get(c + d, 1.0) for d in range(-2, 3)) / 5.0 for c in cols}
        info["squash_min"] = round(min(info["squash_min"], min(fs_.values())), 3)
        info["columns"] = max(info["columns"], sum(v < 0.999 for v in fs_.values()))
        info["passes"] = pass_ + 1
        newz = {}
        for i in idx:
            c = col(W[i].x)
            f, zb = fs_.get(c, 1.0), piv.get(c)
            if zb is None or f >= 0.999 or W[i].z <= zb:
                continue
            newz[i] = zb + (W[i].z - zb) * f
        for i, z in newz.items():
            dz = (mwi.to_3x3() @ Vector((0.0, 0.0, z - W[i].z)))
            me.vertices[i].co += dz
            for kb in blocks:
                kb.data[i].co += dz
        me.update()
        # the 3D check both ways (vertex to surface): done when every moustache vertex and every nose vertex is clear
        W = piece_coords(o)
        mt = BVHTree.FromPolygons(W, mpolys)
        d1 = min(nt.find_nearest(W[i])[3] for i in idx)
        d2 = min(mt.find_nearest(p)[3] for p in ncoords)
        info["nose_clear_mm"] = round(min(d1, d2) * 1000, 2)
        if min(d1, d2) >= clear and not nt.overlap(mt):
            break
    # where the squash cannot clear it (the nose's underside within moustache_clear of the moustache's lower edge, or
    # the nose's open back over it), the nose rises in 0.25 mm steps (at most NOSE_RAISE_FOR_MOUSTACHE), as settle_nose
    def worst():
        W_ = piece_coords(o)
        nc = piece_coords(nose)
        nt_ = BVHTree.FromPolygons(nc, npolys)
        mt_ = BVHTree.FromPolygons(W_, mpolys)
        d1_ = min((nt_.find_nearest(W_[i])[3], i) for i in idx)
        d2_ = min(mt_.find_nearest(q)[3] for q in nc)
        return min(d1_[0], d2_), bool(nt_.overlap(mt_)), W_[d1_[1]], nc
    d, ov, wp, nc = worst()
    low = min(q.z for q in nc)
    info["worst_at_mm"] = [round((wp.x - ctx.x) * 1000, 1), round((wp.z - low) * 1000, 1)]
    raised = 0.0
    cap = NOSE_RAISE_ON_TOP if MOUSTACHE_VARIANT == "a" else NOSE_RAISE_FOR_MOUSTACHE
    if MOUSTACHE_VARIANT == "a":  # (a): the ball's underside up to the moustache's top under it (it sits ON it)
        nx = [q.x for q in nc]
        x0_, x1_ = min(nx), max(nx)
        Wm = piece_coords(o)
        tops = [Wm[i].z for i in idx if x0_ <= Wm[i].x <= x1_ and Wm[i].z >= ctx.mz]
        if tops:
            up = max(0.0, max(tops) - min(q.z for q in nc) - 0.001)  # 1 mm sunk into the moustache's top
            up = min(cap, math.ceil(up / 0.00025) * 0.00025)
            for v in nose.data.vertices:
                v.co.z += up
            nose.data.update()
            raised += up
            d, ov, wp, nc = worst()
    while (d < clear or ov) and raised < cap - 1e-9:
        for v in nose.data.vertices:
            v.co.z += 0.00025
        nose.data.update()
        raised += 0.00025
        d, ov, wp, nc = worst()
    info["pupil_shrink"] = 1.0
    if MOUSTACHE_VARIANT == "a" and raised > 0 and nose_meets_pupils(face):
        V0 = [v.co.copy() for v in nose.data.vertices]
        lo = min(V0, key=lambda c: c.z)
        anc = Vector((sum(c.x for c in V0) / len(V0), sum(c.y for c in V0) / len(V0), lo.z))
        k = 1.0
        while k > NOSE_PUPIL_SHRINK_MIN + 1e-9 and nose_meets_pupils(face):
            k = round(k - 0.05, 2)
            for v, c in zip(nose.data.vertices, V0):
                v.co = anc + (c - anc) * k
            nose.data.update()
        info["pupil_shrink"] = k
        face.meta["nose"]["pupil_shrink_a"] = k
        d, ov, wp, nc = worst()
    info["nose_raised_mm"] = round(raised * 1000, 2)
    info["nose_clear_mm"] = round(0.0 if ov else d * 1000, 2)
    if raised > 0:
        face.meta["nose"]["raised_mm"] = round(face.meta["nose"].get("raised_mm", 0.0) + raised * 1000, 2)
        face.meta["nose"]["meets_pupils"] = bool(nose_meets_pupils(face))
    face.meta["moustache_seat"] = info
    return info
