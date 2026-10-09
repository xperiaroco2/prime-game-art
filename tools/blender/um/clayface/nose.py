"""The clay face kit's noses: the round ball and the long nose, seated over the mouth and kept off the pupils.
"""
import math

from mathutils import Matrix, Vector

from .kit import LAYOUT, LIP_W, NOSES, STATES, nose_axes
from .mesh import blob_bm, piece_coords, static_piece
from .mouth import mouth_extent


def build_nose(face, ctx, M, coll, moustache_z=None, k=None, axes=None, drop_extra=0.0):
    """Wave A's clay nose: its bottom just above the mouth's tallest state within the nose's width (or on the
    moustache's centre line); its top may overlap the eyes' lower edge where they meet (it stands in front).
    k overrides the nose's scale factor (NOSE_K x the loud scale; build_face lowers it when the nose meets a pupil)."""
    h, picks = face.h, face.picks
    N = dict(NOSES[picks["nose"]])
    # fixer: per-axis scale (nose_axes); k (a scalar) still overrides all three
    ks = tuple(axes) if axes is not None else ((k,) * 3 if k is not None else nose_axes(picks))
    kn = (ks[0] * ks[1] * ks[2]) ** (1.0 / 3.0)
    hx, hy, hz = (v * kk for v, kk in zip(N["half"], ks))
    for key, kk in (("lumps", kn), ("capsule", kn), ("drop", ks[2])):
        if N.get(key):
            N[key] = N[key] * kk
    N["drop"] = N.get("drop", 0.0) + drop_extra
    hi, _ = mouth_extent(ctx, M, half_x=hx + LIP_W)
    bottom = hi + LAYOUT["nose_clear"]
    if moustache_z is not None:
        bottom = max(bottom, moustache_z)
    cz = bottom - N["drop"] + hz * (0.95 if N["tilt"] else 1.0)
    p, _ = ctx.surf.hit(ctx.x, cz)
    depth = hy + N.get("capsule", 0.0)
    c = Vector((ctx.x, p.y - depth * (1.0 - N["embed"]), cz))
    rot = Matrix.Rotation(math.radians(N["tilt"]), 3, "X") if N["tilt"] else None
    bm = blob_bm(c, (hx, hy, hz), seg=14, rings=8, rot=rot, capsule=N.get("capsule", 0.0))
    lumps = (N["lumps"], 70.0, 5) if N.get("lumps") else None
    o, culled = static_piece(ctx, f"{h.id}_fb_nose", bm, [face.mats["nose"]], coll, sub=1, target=N["tris"], lumps=lumps)
    if N.get("seat_low"):  # round E: the lowest point (not the centre) sits at `bottom`, the ball's clearance
        low = min(p.z for p in piece_coords(o))
        for v in o.data.vertices:
            v.co.z += bottom - low
        o.data.update()
    face.meta["nose"] = {"kind": picks["nose"], "scale": round(kn, 3), "scale_xyz": [round(x, 3) for x in ks], "half_mm": [round(v * 1000, 1) for v in (hx, hy, hz)],
                         "bottom_above_mouth_top_mm": round((bottom - hi) * 1000, 1),
                         "culled_faces": culled}
    return face.add("nose", o, "nose")


def nose_meets_pupils(face):
    """True when the nose intersects a pupil at rest or in any look key (the pupils ride the look keys)."""
    from mathutils.bvhtree import BVHTree
    nose, pup = face.pieces["nose"], face.pieces.get("pupils")
    if pup is None:
        return False
    nt = BVHTree.FromPolygons(piece_coords(nose), [tuple(p.vertices) for p in nose.data.polygons])
    polys = [tuple(p.vertices) for p in pup.data.polygons]
    keys = [None] + [k for k in ("look_l", "look_r", "look_u", "look_d")
                     if pup.data.shape_keys and k in pup.data.shape_keys.key_blocks]
    return any(nt.overlap(BVHTree.FromPolygons(piece_coords(pup, k), polys)) for k in keys)


def settle_nose(face, step=0.0005, most=0.012):
    """Raises the nose in 0.5 mm steps until it touches no mouth or teeth state (a tilted or dropped nose can reach
    below the clearance computed for its centre). Records the raise in meta["nose"]["raised_mm"]."""
    from mathutils.bvhtree import BVHTree
    nose = face.pieces["nose"]
    trees = []
    for k in ("mouth", "teeth"):
        o = face.pieces.get(k)
        if o is None:
            continue
        polys = [tuple(p.vertices) for p in o.data.polygons]
        for key in [None] + [f"mouth_{s}" for s in STATES if s != "rest"]:
            trees.append(BVHTree.FromPolygons(piece_coords(o, key), polys))
    npolys = [tuple(p.vertices) for p in nose.data.polygons]
    raised = 0.0
    while raised < most:
        nt = BVHTree.FromPolygons(piece_coords(nose), npolys)
        if not any(nt.overlap(t) for t in trees):
            break
        for v in nose.data.vertices:
            v.co.z += step
        raised += step
    nose.data.update()
    face.meta["nose"]["raised_mm"] = round(raised * 1000, 1)
    return raised


def nose_eye_overlap(face, lay):
    """How far the nose's top rises above the eyes' lowest point (mm; > 0: it stands in front of the eyes)."""
    o = face.pieces["nose"]
    mw = o.matrix_world
    top = max((mw @ v.co).z for v in o.data.vertices)
    low = min(c.z - r for c, r in lay.values())
    return round((top - low) * 1000, 1)
