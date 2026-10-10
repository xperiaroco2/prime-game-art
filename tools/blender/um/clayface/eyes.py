"""The clay face kit's eyes: touching eyeballs sunk into the head, the pupils, the clay lids, the blink and the
look shape keys.
"""
import math

import bmesh
from mathutils import Euler, Matrix, Vector

from .kit import EYEBALL, LAYOUT, LIDS, LOOK, PUPILS, PUPIL_EXP, eye_radius
from .mesh import FWD, Part, X, Z, add_keys, data_object, lid_part, lid_rotation, static_piece
from .mouth import outline


def eye_layout(ctx, picks):
    r = eye_radius(picks)
    out = {}
    for side, s in (("L", 1.0), ("R", -1.0)):
        x = ctx.x + s * (LAYOUT["eye_gap"] / 2 + r)
        z = ctx.ez + (0.0015 if picks.get("asym") == "eye" and side == "R" else 0.0)
        p, _ = ctx.surf.hit(x, z)
        out[side] = (Vector((x, p.y - r * LAYOUT["eye_embed"], z)), r)
    return out


def pupil_part_b(c, out, rr, aw, ah, mat, seg, rings):
    """lab_face_r2.pupil_part with a superellipse outline (iterator round 2, the look critic: turned 25 degrees, the
    12-segment pill read as a squared rectangle, its two long straight sides catching a light patch): seg points
    evenly round a rounded oval of angular half width aw and half height ah on the sphere of radius rr round c."""
    right = Z.cross(out).normalized()
    up = out.cross(right).normalized()
    part = Part()
    bm = part.bm
    mi = part.slot(mat)
    e = PUPIL_EXP if ah > aw * 1.05 else 2.0

    def outline(t, k):
        ct, st_ = math.cos(t), math.sin(t)
        return (aw * math.copysign(abs(ct) ** (2.0 / e), ct) * k, ah * math.copysign(abs(st_) ** (2.0 / e), st_) * k)

    def on(x, z):
        d = (out + right * math.tan(x) + up * math.tan(z)).normalized()
        return c + d * rr

    centre = bm.verts.new(c + out * rr)
    rows = []
    for k in range(1, rings + 1):
        f = k / rings
        rows.append([bm.verts.new(on(*outline(2 * math.pi * s_ / seg + math.pi / seg, f))) for s_ in range(seg)])
    made = []
    for s_ in range(seg):
        made.append(bm.faces.new((centre, rows[0][s_], rows[0][(s_ + 1) % seg])))
    for k in range(rings - 1):
        for s_ in range(seg):
            made.append(bm.faces.new((rows[k][s_], rows[k + 1][s_], rows[k + 1][(s_ + 1) % seg], rows[k][(s_ + 1) % seg])))
    for f_ in made:
        f_.material_index = mi
        f_.normal_update()
        if f_.normal.dot(f_.calc_center_median() - c) < 0:
            f_.normal_flip()
    return part


def lid_states(c, verts, edge_rest, edge_half, edge_closed, side, tilt=0.0, closed_puff=1.0):
    """Lid vertices (built unrotated round c) at rest, half closed and closed: rigid rotations about the eye centre,
    exact at each step (a stepped blink never blends two of them). closed_puff scales the closed lid about the eye
    centre (the upper lid: it closes OVER the lower one)."""
    out = {}
    for k, e in (("rest", edge_rest), ("blink_half", edge_half), ("blink", edge_closed)):
        t = tilt if k == "rest" else (tilt * 0.5 if k == "blink_half" else 0.0)
        R = Euler(lid_rotation(e, t, side), "XYZ").to_matrix()
        f = closed_puff if k == "blink" else 1.0
        out[k] = [c + (R @ (v - c)) * f for v in verts]
    return out


def lid_k_out(seg, rings):
    """How far a lid shell's vertices are pushed out so its flat facets never come nearer the eye than its scale."""
    EB = EYEBALL
    dphi = (math.pi / 2 - EB["lid_line_rad"]) / rings
    dth = (math.pi + 2 * EB["lid_back_margin"]) / seg
    return 1.0 / (math.cos(dphi / 2) * math.cos(dth / 2))


def build_eyes(face, ctx, coll):
    h, picks, m = face.h, face.picks, face.mats
    EB = EYEBALL
    lay = eye_layout(ctx, picks)
    up = LIDS[picks["lid"]]
    closed = EB["closed_edge"]
    lo = EB["lo_edge"]
    pu_w, pu_h = PUPILS[picks["pupil"]]
    face.meta["eyes"] = {"r": lay["L"][1], "up_edge": up}
    face.eye_centres = {k: (c.copy(), r) for k, (c, r) in lay.items()}
    face.meta["look"] = {"yaw": LOOK["yaw"], "pitch_up": min(LOOK["pitch_up"], max(0.0, up - 8.0)),
                         "pitch_down": LOOK["pitch_down"]}
    # whites: one sphere each, the part inside the head culled
    bm = bmesh.new()
    wb = Part()
    wb.bm.free()
    wb.bm = bm
    for side, (c, r) in lay.items():
        wb.ellipsoid(c, X, Z, FWD, r, r, r, m["white"], seg=EB["white_seg"], rings=EB["white_rings"])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    whites, culled = static_piece(ctx, f"{h.id}_fb_whites", bm, wb.mats, coll, sub=0)
    face.add("whites", whites, "eye")
    face.meta["whites_culled_faces"] = culled
    # pupils: caps on the eyes facing -Y, look keys = rotations about each eye centre
    pv, pf, base = [], [], 0
    centres = []
    for side, (c, r) in lay.items():
        rr = r * (1.0 + EB["pupil_lift_frac"]) + EB["pupil_lift"]
        pw = max(pu_w * r, 0.003)
        ph = max(pu_h * r, pw)
        part = pupil_part_b(c, FWD, rr, math.asin(min(0.95, pw / rr)), math.asin(min(0.95, ph / rr)), m["pupil"],
                            EB["pupil_seg"], EB["pupil_rings"])
        part.bm.verts.index_update()
        vs = [v.co.copy() for v in part.bm.verts]
        fs = [tuple(v.index + base for v in f.verts) for f in part.bm.faces]
        part.bm.free()
        pv += vs
        pf += fs
        centres += [c] * len(vs)
        base += len(vs)
        face.meta["eyes"][f"pupil_{side}_mm"] = [round(2 * pw * 1000, 1), round(2 * ph * 1000, 1)]
    L = face.meta["look"]
    rots = {"look_l": Matrix.Rotation(math.radians(L["yaw"]), 3, "Z"),
            "look_r": Matrix.Rotation(math.radians(-L["yaw"]), 3, "Z"),
            "look_u": Matrix.Rotation(math.radians(-L["pitch_up"]), 3, "X"),
            "look_d": Matrix.Rotation(math.radians(L["pitch_down"]), 3, "X")}
    pupils = data_object(f"{h.id}_fb_pupils", pv, pf, [0] * len(pf), [m["pupil"]], coll)
    add_keys(pupils, {k: [c + R @ (v - c) for v, c in zip(pv, centres)] for k, R in rots.items()}, None)
    face.add("pupils", pupils, "pupil")
    # lids: upper (skin, crease band) and lower (skin, lower crease), unrotated shells, rest / half / closed keys
    lv, lfc, lfm, base = [], [], [], 0
    states = {"rest": [], "blink_half": [], "blink": []}
    # Iterator round 1 (resumed): where the closed lids overlap, the two coarse shells crossed each other facet by
    # facet and the overlap band read as a row of stitches. The closed upper lid now puffs out about the eye centre
    # until its nearest facet clears the lower lid's farthest vertex by 1.2 % of r (a closed lid bulges a little).
    puff = EB["lid_lo_scale"] * lid_k_out(EB["lo_seg"], EB["lo_rings"]) * 1.012 / EB["lid_scale"]
    face.meta["eyes"]["closed_upper_puff"] = round(puff, 4)
    for side, (c, r) in lay.items():
        ov = EB["closed_overlap"]
        for pole, scale, seg, rings, e_rest, e_closed, cp in (
                (Z, EB["lid_scale"], EB["lid_seg"], EB["lid_rings"], up, closed - ov, puff),
                (-Z, EB["lid_lo_scale"], EB["lo_seg"], EB["lo_rings"], lo, closed + ov, 1.0)):
            EBl = {"lid_line_rad": EB["lid_line_rad"], "lid_back_margin": EB["lid_back_margin"], "lid_seg": seg,
                   "lid_rings": rings}
            part = lid_part(c, r, scale, pole, m["skin"], m["crease"], EBl)
            bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-7)
            part.bm.verts.index_update()
            # a coarse shell's flat facets dip inside its sphere by 1 - cos(half the facet angle): push the shell's
            # vertices out so that no facet comes nearer the eye than scale x r (else white and pupil poke through)
            dphi = (math.pi / 2 - EB["lid_line_rad"]) / rings
            dth = (math.pi + 2 * EB["lid_back_margin"]) / seg
            k_out = 1.0 / (math.cos(dphi / 2) * math.cos(dth / 2))
            for v in part.bm.verts:
                d = v.co - c
                if d.length > r * 1.02:
                    v.co = c + d * k_out
            face.meta["eyes"]["lid_inflate"] = round(k_out, 4)
            vs = [v.co.copy() for v in part.bm.verts]
            mi = {0: 0, 1: 1}
            for f in part.bm.faces:
                lfc.append(tuple(v.index + base for v in f.verts))
                lfm.append(mi.get(f.material_index, 1))
            part.bm.free()
            st = lid_states(c, vs, e_rest, (e_rest + e_closed) / 2, e_closed, side, closed_puff=cp)
            for k in states:
                states[k] += st[k]
            base += len(vs)
    lids = data_object(f"{h.id}_fb_lids", states["rest"], lfc, lfm, [m["skin"], m["crease"]], coll)
    add_keys(lids, states, "rest")
    face.add("lids", lids, "lid")
    return lay
