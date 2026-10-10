"""The clay face kit's measures for the check (faces --check): piece collisions, mouth clearances, the look's
sag and brows in the white.
"""
import math

import numpy as np

from .kit import EYEBALL, BAD_PAIRS, LIP_W, MOUTHS, NOSES, STATES, STRICT_NOSE_PAIRS, STRICT_NOSES
from .mesh import piece_coords
from .mouth import mouth_extent


def collisions(face):
    """Intersecting triangle pairs between pieces that must never touch (BAD_PAIRS), over every mouth state (mouth,
    teeth) and every blink step (lids), in the rest pose. Returns {"nose|mouth": n, ...} (empty when clean)."""
    from mathutils.bvhtree import BVHTree
    trees = {}
    for name, o in face.pieces.items():
        polys = [tuple(p.vertices) for p in o.data.polygons]
        cat = face.cat[name]
        if cat in ("mouth", "teeth", "fhair"):
            keys = [None] + [f"mouth_{s}" for s in STATES if s != "rest"]
        elif cat == "lid":
            keys = [None, "blink_half", "blink"]
        else:
            keys = [None]
        trees[name] = [BVHTree.FromPolygons(piece_coords(o, k), polys) for k in keys]
    bad = BAD_PAIRS | (STRICT_NOSE_PAIRS if face.picks.get("nose") in STRICT_NOSES else set())
    out = {}
    names = sorted(trees)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ca, cb = face.cat[a], face.cat[b]
            if (ca, cb) not in bad and (cb, ca) not in bad:
                continue
            same_state = {ca, cb} <= {"mouth", "teeth", "fhair"}
            n = 0
            for ia, ta in enumerate(trees[a]):
                for ib, tb in enumerate(trees[b]):
                    if same_state and ia != ib:
                        continue
                    n += len(ta.overlap(tb))
            if n:
                out[f"{ca}|{cb}"] = n
    return out


def mouth_clearances(face, ctx):
    """Millimetres between the nose's lowest point and the mouth's highest (every state, under the nose), and between
    a moustache's lowest point and the lip below it."""
    out = {}
    pts = {k: piece_coords(o) for k, o in face.pieces.items() if k in ("nose", "fhair")}
    M = MOUTHS[face.picks["mouth"]]
    hi, _ = mouth_extent(ctx, M, half_x=NOSES[face.picks["nose"]]["half"][0] + LIP_W)
    out["nose_above_mouth_mm"] = round((min(p.z for p in pts["nose"]) - hi) * 1000, 2)
    return out


def look_sag(face):
    """The deepest a pupil vertex sinks below the eye white's surface when the look keys blend (weights 0..1 in
    steps of 0.25, yaw and pitch combined), in mm (< 0: every pupil vertex stays above the white)."""
    o = face.pieces["pupils"]
    basis = np.array([tuple(p) for p in piece_coords(o)])
    keys = {k: np.array([tuple(p) for p in piece_coords(o, k)]) - basis for k in ("look_l", "look_r", "look_u", "look_d")}
    half = len(basis) // 2
    worst = -1.0
    steps = [0.0, 0.25, 0.5, 0.75, 1.0]
    for yk in ("look_l", "look_r"):
        for pk in ("look_u", "look_d"):
            for a in steps:
                for b in steps:
                    p = basis + keys[yk] * a + keys[pk] * b
                    for side, sl in (("L", slice(0, half)), ("R", slice(half, None))):
                        c, r = face.eye_centres[side]
                        d = np.linalg.norm(p[sl] - np.array(tuple(c)), axis=1)
                        worst = max(worst, float((r - d.min()) * 1000))
    return round(worst, 3)


def brow_in_white(face):
    """Brow vertices inside an eyeball below its resting lid edge (the white that shows): must be 0."""
    o = face.pieces["brows"]
    up = math.radians(face.meta["eyes"]["up_edge"])
    n = 0
    for p in piece_coords(o):
        for c, r in face.eye_centres.values():
            d = p - c
            if d.length < r and math.atan2(d.z, max(1e-9, math.hypot(d.x, d.y))) < up:
                n += 1
    return n


BROW_SEEN_MIN = 0.25  # art #42 round 3: at least this share of each brow's vertices seen from the front
BROW_EYE_CLEAR_MIN_MM = -3.0  # ... and its lowest front point over an eye at most this far below the lid's top


def brow_visibility(face, occluders):
    """art #42 round 3 (w3's brows sank behind the eyes under the formal updo): per side the share of brow vertices
    seen from straight in front (a ray from 0.5 m in front of each vertex meets none of the occluders, the eye whites,
    lids, pupils and nose first: the head, hair and headwear objects given) and the brow-to-eye clearance (mm: the
    lowest front brow vertex over an eye above that eye's resting upper lid top, c.z + r x lid_scale; < 0: the brow
    sinks into the lid). ok: both sides seen at least BROW_SEEN_MIN and the clearance above BROW_EYE_CLEAR_MIN_MM."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    o = face.pieces.get("brows")
    if o is None:
        return {"ok": True, "brows": False}
    objs = [p for p in occluders if p is not None] + [face.pieces[k] for k in ("whites", "pupils", "lids", "nose")
                                                       if k in face.pieces]
    trees = [BVHTree.FromPolygons(piece_coords(p), [tuple(f.vertices) for f in p.data.polygons]) for p in objs]
    x = face.h.x
    out = {}
    clear = 1e9
    for side, sel in (("L", lambda q: q.x > x), ("R", lambda q: q.x <= x)):
        pts = [q for q in piece_coords(o) if sel(q)]
        seen = 0
        for q in pts:
            start = Vector((q.x, q.y - 0.5, q.z))
            if not any(t.ray_cast(start, Vector((0.0, 1.0, 0.0)), 0.5 - 0.0015)[0] is not None for t in trees):
                seen += 1
            for c, r in face.eye_centres.values():
                if abs(q.x - c.x) < r and q.y < c.y:  # over this eye, in front of its centre: above the lid's top
                    clear = min(clear, q.z - (c.z + r * EYEBALL["lid_scale"]))
        out[side] = round(seen / max(1, len(pts)), 3)
    res = {"seen_share": out, "eye_clear_mm": round(clear * 1000, 2)}
    res["ok"] = min(out.values()) >= BROW_SEEN_MIN and clear * 1000 > BROW_EYE_CLEAR_MIN_MM
    return res
