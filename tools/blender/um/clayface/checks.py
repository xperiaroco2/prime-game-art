"""The clay face kit's measures for the check (faces --check): piece collisions, mouth clearances, the look's
sag and brows in the white.
"""
import math

import numpy as np

from .kit import BAD_PAIRS, LIP_W, MOUTHS, NOSES, STATES
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
    out = {}
    names = sorted(trees)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ca, cb = face.cat[a], face.cat[b]
            if (ca, cb) not in BAD_PAIRS and (cb, ca) not in BAD_PAIRS:
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
