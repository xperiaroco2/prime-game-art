"""Ear and nose accessories on the bean head (art #42 round 3): the pack's rings and studs follow the warped skull
(heads.bean_warp, push_out), but the kit builds its own ears (ears.build_ears) and nose (nose.build_nose) elsewhere, so
a ring hung where the pack's ear was. seat_accessories moves each side's ear pieces so their top passes through the
kit ear's lobe, and the nose pieces so their top passes through the kit nose's underside, then measures the gap.
"""
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import heads
from .kit import accessory_seat_ok, accessory_zone
from .mesh import piece_coords

PIERCE_M = 0.002  # the ring's top passes this far up through the lobe or the nose's underside
EAR_KEY = {"free": None, "tuck": "ears_tuck"}  # the ear state's shape key the lobe is read from ("hide": no ear)


def _pieces(o):
    """[(vertex indices, world centre)] of the object's loose pieces (heads.loose_pieces)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    mw = o.matrix_world
    out = []
    for faces in heads.loose_pieces(bm, mw):
        idx = sorted({v.index for f in faces for v in f.verts})
        out.append((idx, heads.piece_centre(faces, mw)))
    bm.free()
    return out


def _move(o, idx, d):
    """Moves the vertices idx of o (and the same vertices of every shape key) by the world vector d."""
    dl = o.matrix_world.inverted().to_3x3() @ d
    me = o.data
    for i in idx:
        me.vertices[i].co += dl
    if me.shape_keys:
        for kb in me.shape_keys.key_blocks:
            for i in idx:
                kb.data[i].co += dl
    me.update()


def _tree(o, key=None):
    pts = piece_coords(o, key)
    return BVHTree.FromPolygons(pts, [tuple(p.vertices) for p in o.data.polygons]), pts


def _gap(tree, pts):
    """(gap mm: the nearest vertex's distance to the surface, share of vertices inside it)."""
    best, inside = 1e9, 0
    for p in pts:
        loc, nrm, _i, dist = tree.find_nearest(p)
        if loc is None:
            continue
        best = min(best, dist)
        if (p - loc).dot(nrm) < 0.0:
            inside += 1
    return round(best * 1000, 2), round(inside / max(1, len(pts)), 3)


def classify(c, x, eye_z, nose_back_y):
    """"ear_l" / "ear_r" / "nose" / None for a piece centre c (world): kit.accessory_zone."""
    return accessory_zone(c, x, eye_z, nose_back_y)


class SeatError(RuntimeError):
    """A ring or stud left floating off or buried in the kit's ear or nose (kit.accessory_seat_ok)."""


def seat_accessories(face, h, objs, ear_state):
    """Seats the ear and nose pieces of objs (the recipe's extras) on the kit's ears and nose. Returns the report:
    per object and zone the move (mm) and the gap measure ({"gap_mm", "inside_share", "ok"}). Raises SeatError when
    a moved piece fails the measure (kit.accessory_seat_ok)."""
    ears, nose = face.pieces.get("ears"), face.pieces.get("nose")
    x, ez = h.x, h.eye_z()
    nose_pts = piece_coords(nose) if nose is not None else []
    nose_back_y = max(p.y for p in nose_pts) if nose_pts else -1e9
    key = EAR_KEY.get(ear_state)
    ear_pts = piece_coords(ears, key) if ears is not None and ear_state != "hide" else []
    ear_tree = _tree(ears, key)[0] if ear_pts else None
    nose_tree = _tree(nose)[0] if nose_pts else None
    rep = {}
    for o in objs:
        zones = {}
        for idx, c in _pieces(o):
            z = classify(c, x, ez, nose_back_y)
            if z:
                zones.setdefault(z, []).extend(idx)
        out = {}
        for z, idx in sorted(zones.items()):
            world = piece_coords(o)
            pts = [world[i] for i in idx]
            top = max(pts, key=lambda p: p.z)
            if z == "nose":
                if nose_tree is None:
                    out[z] = {"moved": False, "why": "no kit nose"}
                    continue
                low = min(nose_pts, key=lambda p: p.z)
                tx = min(max(top.x, x - 0.01), x + 0.01)
                hit = nose_tree.ray_cast(Vector((tx, low.y, low.z - 0.05)), Vector((0.0, 0.0, 1.0)))[0]
                target = (hit if hit is not None else low) + Vector((0.0, 0.0, PIERCE_M))
                tree = nose_tree
            else:
                if ear_tree is None:
                    out[z] = {"moved": False, "why": "the ears are hidden (%s)" % ear_state}
                    continue
                side = [p for p in ear_pts if (p.x > x) == (z == "ear_l")]
                lobe = min(side, key=lambda p: p.z)
                target = lobe + Vector((0.0, 0.0, PIERCE_M))
                tree = ear_tree
            d = target - top
            _move(o, idx, d)
            world = piece_coords(o)
            gap, inside = _gap(tree, [world[i] for i in idx])
            out[z] = {"moved": True, "move_mm": round(d.length * 1000, 1), "vertices": len(idx), "gap_mm": gap,
                      "inside_share": inside, "ok": accessory_seat_ok(gap, inside)}
        if out:
            rep[o.name] = out
    bad = ["%s %s: gap %s mm, inside %s" % (o, z, r["gap_mm"], r["inside_share"])
           for o, zs in rep.items() for z, r in zs.items() if r.get("moved") and not r["ok"]]
    if bad:
        raise SeatError("ear/nose accessories not seated on the kit: " + "; ".join(bad))
    return rep
