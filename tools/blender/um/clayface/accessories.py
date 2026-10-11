"""Ear and nose accessories on the bean head (art #42 round 3): the pack's rings and studs follow the warped skull
(heads.bean_warp, push_out), but the kit builds its own ears (ears.build_ears) and nose (nose.build_nose) elsewhere, so
a ring hung where the pack's ear was. seat_accessories hangs each side's ear ring in the vertical plane of the kit
ear's yaw with its piercing point (the top of its centre line) on the lobe's centre (round 4: kit.lobe_centre,
ear_plane, hang_normal, ring_frame), swung out until it clears the head (kit.swing_order, ring_clear_ok), and moves the
nose pieces so their top passes through the kit nose's underside, then measures the gap, and for the ear rings the
piercing point's distance, the plane's angle and the share inside the head (kit.accessory_ring_ok).
"""
import math

import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from .. import heads
from .kit import (ACC_LOBE_FREE_MM, accessory_ring_ok, accessory_seat_ok, accessory_zone, ear_plane, hang_normal,
                  lobe_centre, plane_angle_deg, ring_clear_ok, ring_frame, swing_order)
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


def _turn(o, idx, rot, pivot, d):
    """Turns the vertices idx of o (and of every shape key) by the world 3x3 rot about the world pivot, then moves them
    by the world vector d."""
    mw = o.matrix_world
    inv = mw.inverted()
    me = o.data
    lists = [me.vertices] + ([kb.data for kb in me.shape_keys.key_blocks] if me.shape_keys else [])
    for data in lists:
        for i in idx:
            p = mw @ data[i].co
            data[i].co = inv @ (rot @ (p - pivot) + pivot + d)
    me.update()


def ring_measure(pts, lobe, hang_n):
    """(piercing point's distance to the lobe's centre in mm, the ring plane's angle to the ear's hanging plane in
    degrees)."""
    f = ring_frame(pts)
    return (round((Vector(f["pierce"]) - Vector(lobe)).length * 1000, 2),
            round(plane_angle_deg(f["normal"], hang_n), 1))


def _head_mm(tree, p):
    """p's distance to the head's surface in mm, negative inside."""
    loc, nrm, _i, dist = tree.find_nearest(p)
    if loc is None:
        return 1e9
    return dist * 1000 * (-1.0 if (p - loc).dot(nrm) < 0.0 else 1.0)


def _inside(tree, pts):
    """The share of pts inside the head."""
    return round(sum(1 for p in pts if _head_mm(tree, p) < 0.0) / max(1, len(pts)), 3)


def seat_ring(o, idx, side_pts, out_x, head_tree):
    """Hangs the ring idx of o from the ear side's lobe: its plane turned to the vertical plane of the ear's yaw
    (kit.hang_normal), its piercing point on the lobe's centre (the ear's lowest band off the head), then the smallest
    swing of its bottom out and push out (kit.swing_order) that clears the head (kit.ring_clear_ok). out_x: +1 for the
    left ear, -1 for the right. Returns the lobe centre, the hanging normal and the seat's numbers."""
    head_mm = [_head_mm(head_tree, p) for p in side_pts]
    lobe = Vector(lobe_centre(side_pts, head_mm=head_mm))
    ear_n = Vector(ear_plane(side_pts))
    if ear_n.x * out_x < 0.0:
        ear_n = -ear_n
    hn = Vector(hang_normal(ear_n))
    world = piece_coords(o)
    f = ring_frame([world[i] for i in idx])
    rn = Vector(f["normal"])
    if rn.dot(hn) < 0.0:
        rn = -rn
    rot = rn.rotation_difference(hn).to_matrix()
    c = Vector(f["centre"])
    _turn(o, idx, rot, c, Vector((0.0, 0.0, 0.0)))
    world = piece_coords(o)
    d = lobe - Vector(ring_frame([world[i] for i in idx])["pierce"])
    _turn(o, idx, Matrix.Identity(3), c, d)
    world = piece_coords(o)
    pts = [world[i] for i in idx]
    f = ring_frame(pts)
    piv, up = Vector(f["pierce"]), Vector(f["pierce"]) - Vector(f["centre"])
    axis = up.cross(hn).normalized()
    if (Matrix.Rotation(0.1, 3, axis) @ -up).dot(hn) < 0.0:
        axis = -axis
    best = None
    for swing, push in swing_order():
        R = Matrix.Rotation(math.radians(swing), 3, axis)
        share = _inside(head_tree, [R @ (p - piv) + piv + hn * (push / 1000) for p in pts])
        if best is None or share < best[0]:
            best = (share, swing, push, R)
        if ring_clear_ok(share):
            best = (share, swing, push, R)
            break
    share, swing, push, R = best
    _turn(o, idx, R, piv, hn * (push / 1000))
    return lobe, hn, {"turn_deg": round(math.degrees(rn.angle(hn)), 1), "move_mm": round(d.length * 1000, 1),
                      "swing_deg": swing, "push_mm": push,
                      "lobe_free": sum(1 for m in head_mm if m >= ACC_LOBE_FREE_MM)}


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
    head_tree = _tree(h.parts["head"])[0]
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
                lobe, hang_n, seat = seat_ring(o, idx, side, 1.0 if z == "ear_l" else -1.0, head_tree)
                world = piece_coords(o)
                pts = [world[i] for i in idx]
                gap, inside = _gap(ear_tree, pts)
                pierce, plane = ring_measure(pts, lobe, hang_n)
                head_in = _inside(head_tree, pts)
                out[z] = dict(seat, moved=True, vertices=len(idx), gap_mm=gap, inside_share=inside,
                              lobe_centre=[round(v, 4) for v in lobe], pierce_mm=pierce, plane_deg=plane,
                              head_inside=head_in,
                              ok=accessory_seat_ok(gap, inside) and accessory_ring_ok(pierce, plane, head_in))
                continue
            d = target - top
            _move(o, idx, d)
            world = piece_coords(o)
            gap, inside = _gap(tree, [world[i] for i in idx])
            out[z] = {"moved": True, "move_mm": round(d.length * 1000, 1), "vertices": len(idx), "gap_mm": gap,
                      "inside_share": inside, "ok": accessory_seat_ok(gap, inside)}
        if out:
            rep[o.name] = out
    bad = ["%s %s: gap %s mm, inside %s, pierce %s mm, plane %s deg, in head %s"
           % (o, z, r["gap_mm"], r["inside_share"], r.get("pierce_mm"), r.get("plane_deg"), r.get("head_inside"))
           for o, zs in rep.items() for z, r in zs.items() if r.get("moved") and not r["ok"]]
    if bad:
        raise SeatError("ear/nose accessories not seated on the kit: " + "; ".join(bad))
    return rep
