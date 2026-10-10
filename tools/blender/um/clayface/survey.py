"""The clay face kit's many-face check (faces --kit-check, docs/faces.md): n random faces per body type on a repo
head (the recipe's first character of that body type, built by the assembler with the kit), each under a random hair
item of faces/clay_hair.json, measured in the rest pose at head scale 1. Ported from the faces lab's stage_check
(D:/prime-art-raw/research/2026-10-05-faces/lab/clay_e/face_sheets.py, round E5: the visible-poke test, a seed per
body type, the updo list).

Per body type: collisions (BAD_PAIRS, every mouth state and blink step), brows in the visible white, visible pokes
(a brow point in front of the hair with visible hair right behind it), ears against the hair (in the item's ear
state), the nose above the mouth, the look's sag, the moustache seat (nose clearance), noses meeting a pupil and
triangles. The runner judges the numbers (tools/runner/commands/faces.py kit_problems).
"""
import random
import time

import bpy
from mathutils.bvhtree import BVHTree

from .. import assemble, heads, zones
from ..util import update
from . import checks, kit
from .adapter import KitHead
from .brows import brow_above_pad, hair_visible_at, skin_depth
from .face import build_face
from .mesh import FWD, piece_coords

SEEDS = {"M": 500, "W": 501}  # the lab's per-body-type seeds (500 + the body type's index)
UPDO = "hair_w_formal_updo"
TOP = 8  # the worst faces listed per measure


def hair_items(gender):
    """The hair items of a body type, sorted by id (the lab's draw order)."""
    return sorted(i for i, v in kit.HAIR_ITEMS.items() if v.get("kind", "hair") == "hair" and v.get("body_type") == gender)


def draw(gender, n, hairs):
    """The n faces of a body type: [(index, picks, hair id)], as the lab draws them (picks, then a hair; a forbidden
    hair x brow pair takes the next allowed hair, no draw)."""
    rng = random.Random(SEEDS[gender])
    out = []
    for i in range(n):
        p = kit.random_picks(rng, gender)
        style = hairs[rng.randrange(len(hairs))]
        if not kit.hair_brow_ok(style, p):
            k0 = hairs.index(style)
            style = next(hairs[(k0 + j) % len(hairs)] for j in range(1, len(hairs))
                         if kit.hair_brow_ok(hairs[(k0 + j) % len(hairs)], p))
        out.append((i, p, style))
    return out


def wear(packs, rc, arm, parts, coll, item):
    """Replaces parts["hair"] with the hair item (taken as the assembler takes a recipe hair)."""
    old = parts.pop("hair", None)
    if old is not None:
        me = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    v = kit.HAIR_ITEMS[item]
    spec = {"file": v["file"], "object": v["object"], "materials": v["materials"], "gender": v["body_type"]}
    mats = set(spec["materials"])
    obj, _ = assemble.take_part(packs, rc["id"], "hair", rc["gender"], spec, arm,
                                keep=lambda m, c: m in mats and not zones.BROW_ZONE(c))
    heads.inflate(obj, arm, v.get("inflate", 0.0))
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    parts["hair"] = obj
    update()
    return obj


def _tree(o, coords):
    return BVHTree.FromPolygons(coords, [tuple(q.vertices) for q in o.data.polygons])


def _points(o, co):
    """Every vertex, and every polygon's centre and edge midpoints (the lab's built-mesh test)."""
    pts = list(co)
    for q in o.data.polygons:
        vs = [co[j] for j in q.vertices]
        c = vs[0].copy()
        for v in vs[1:]:
            c += v
        pts.append(c / len(vs))
        pts += [(vs[j] + vs[(j + 1) % len(vs)]) / 2 for j in range(len(vs))]
    return pts


def visible_pokes(face, ht):
    """Brow points that poke out of the hair visibly: no hair in front, hair right behind (8 mm) that is not under the
    skin, and the point itself not under the skin (the lab's e5 poke test)."""
    bo = face.pieces["brows"]
    ctx = face.ctx

    def poke(bp):
        if ht.ray_cast(bp + FWD * 1e-5, FWD, 0.05)[0] is not None:
            return False
        hit = ht.ray_cast(bp - FWD * 1e-5, -FWD, 0.008)[0]
        if hit is None:
            return False
        d = skin_depth(ctx, bp)
        if d is not None and d < -0.0005:
            return False
        return hair_visible_at(ctx, hit)

    return sum(poke(bp) for bp in _points(bo, piece_coords(bo)))


def ear_overlap(face, ht, item):
    eo = face.pieces["ears"]
    st = kit.ear_state(item)
    co = piece_coords(eo, {"hide": "ears_hide", "tuck": "ears_tuck"}.get(st))
    return st, len(ht.overlap(_tree(eo, co)))


def _count(d, k, n=1):
    d[k] = d.get(k, 0) + n


def _top(lst, entry, key):
    lst.append(entry)
    lst.sort(key=lambda e: -e[key])
    del lst[TOP:]


def measure(face, item, ht):
    """One face's numbers."""
    m = {"collisions": checks.collisions(face), "brow_in_white": checks.brow_in_white(face),
         "nose_above_mouth_mm": checks.mouth_clearances(face, face.ctx)["nose_above_mouth_mm"],
         "look_sag_mm": checks.look_sag(face), "tris": face.meta["tris_total"],
         "meets_pupils": bool(face.meta["nose"].get("meets_pupils")), "pokes": 0, "ear_overlap": 0}
    m["ear_state"] = kit.ear_state(item)
    if ht is not None:
        m["pokes"] = visible_pokes(face, ht)
        m["ear_state"], m["ear_overlap"] = ear_overlap(face, ht, item)
    ms = face.meta.get("moustache_seat")
    if ms:
        m["moustache"] = {"nose_clear_mm": ms.get("nose_clear_mm", 99.0), "cannot_clear": ms.get("cannot_clear", 0),
                          "squash_min": ms.get("squash_min", 1.0)}
    bt = face.meta.get("brow_tuck") or {}
    m["brow_tucked_verts"] = bt.get("verts", 0)
    m["brow_above_pad"] = brow_above_pad(face)["points"]
    # art #42 round 3: the brows seen from the front over the eyes (w3's brows sank behind them under the updo)
    m["brow_vis"] = checks.brow_visibility(face, [face.h.parts["head"], face.h.parts.get("hair")])
    return m


def add(stats, i, p, item, m):
    stats["faces"] += 1
    _count(stats["hairs_seen"], item)
    stats["tris_max"] = max(stats["tris_max"], m["tris"])
    stats["tris_sum"] += m["tris"]
    stats["nose_above_mouth_mm_min"] = min(stats["nose_above_mouth_mm_min"], m["nose_above_mouth_mm"])
    stats["look_sag_mm_max"] = max(stats["look_sag_mm_max"], m["look_sag_mm"])
    for cat in ("mouth", "nose", "facial_hair", "brows", "eye_size", "loud"):
        _count(stats["picks_seen"].setdefault(cat, {}), str(p.get(cat)))
    who = {"i": i, "hair": item, "brows": p["brows"], "eye_size": p["eye_size"], "mouth": p["mouth"], "nose": p["nose"],
           "facial_hair": p.get("facial_hair")}
    if m["collisions"]:
        stats["faces_with_collision"] += 1
        for k in m["collisions"]:
            _count(stats["pairs"], k)
        _top(stats["collision_top"], dict(who, pairs=m["collisions"], n=sum(m["collisions"].values())), "n")
    if m["brow_in_white"]:
        stats["brow_in_white_faces"] += 1
        _top(stats["brow_in_white_top"], dict(who, n=m["brow_in_white"]), "n")
    if m["pokes"]:
        stats["pokes"] += 1
        stats["poke_points"] += m["pokes"]
        _count(stats["pokes_by_hair"], item)
        _top(stats["poke_top"], dict(who, n=m["pokes"], tucked=m["brow_tucked_verts"]), "n")
    if m["ear_overlap"]:
        stats["ear_hair_overlap_faces"] += 1
        _count(stats["ear_hair_by"], item)
    _count(stats["ear_states"], m["ear_state"])
    stats["meets_pupils_faces"] += int(m["meets_pupils"])
    stats["brow_tuck_faces"] += int(m["brow_tucked_verts"] > 0)
    ms = m.get("moustache")
    if ms:
        mst = stats["moustache_seat"]
        mst["faces"] += 1
        mst["overlap_faces"] += int(ms["nose_clear_mm"] <= 0.0)
        mst["cannot_clear_faces"] += int(ms["cannot_clear"] > 0)
        mst["nose_clear_mm_min"] = min(mst["nose_clear_mm_min"], ms["nose_clear_mm"])
        mst["squash_min"] = min(mst["squash_min"], ms["squash_min"])
    bv = m["brow_vis"]
    if bv.get("brows", True) is not False:
        stats["brow_eye_clear_mm_min"] = min(stats["brow_eye_clear_mm_min"], bv["eye_clear_mm"])
        stats["brow_seen_min"] = min(stats["brow_seen_min"], min(bv["seen_share"].values()))
    if not bv["ok"]:
        stats["brow_hidden_faces"] += 1
        _count(stats["brow_hidden_by"], item)
        _top(stats["brow_hidden_top"], dict(who, seen=bv["seen_share"], eye_clear_mm=bv["eye_clear_mm"],
                                            n=-bv["eye_clear_mm"]), "n")
    if item == UPDO:
        stats["updo"].append({"i": i, "brows": p["brows"], "pokes": m["pokes"], "brow_above_pad": m["brow_above_pad"]})


def new_stats(head_id, n):
    return {"head": head_id, "faces": 0, "requested": n, "faces_with_collision": 0, "pairs": {}, "collision_top": [],
            "brow_in_white_faces": 0, "brow_in_white_top": [], "pokes": 0, "poke_points": 0, "pokes_by_hair": {},
            "poke_top": [], "ear_hair_overlap_faces": 0, "ear_hair_by": {}, "ear_states": {},
            "nose_above_mouth_mm_min": 99.0, "look_sag_mm_max": -9.0, "meets_pupils_faces": 0, "brow_tuck_faces": 0,
            "tris_max": 0, "tris_sum": 0, "hairs_seen": {}, "picks_seen": {}, "updo": [],
            "brow_hidden_faces": 0, "brow_hidden_by": {}, "brow_hidden_top": [], "brow_eye_clear_mm_min": 99.0,
            "brow_seen_min": 1.0,
            "moustache_seat": {"faces": 0, "overlap_faces": 0, "cannot_clear_faces": 0, "nose_clear_mm_min": 99.0,
                               "squash_min": 1.0}}


def run_body(packs, recipe, rc, n, log=print):
    """The check for one body type on rc's head. Returns its stats."""
    g = rc["gender"]
    coll = bpy.data.collections.new(rc["id"] + "_check")
    bpy.context.scene.collection.children.link(coll)
    arm, parts, rep = assemble.build_character(packs, recipe, rc, coll, face="kit")
    for role in ("eyes", "face"):  # the recipe's own kit face: the check builds its own
        o = parts.pop(role)
        bpy.data.objects.remove(o, do_unlink=True)
    eyes_at = {k: tuple(v) for k, v in rep["eye_centres"].items()}
    skin_mat = bpy.data.materials[rc["id"] + "_skin"]
    skin = tuple(rc["skin"]) if rc.get("skin") else tuple(skin_mat.diffuse_color[:3])
    hairs = hair_items(g)
    faces = draw(g, n, hairs)
    stats = new_stats(rc["id"], n)
    stats["hair_items"] = len(hairs)
    t0 = time.time()
    for item in hairs:  # grouped by hair: each hair is taken once
        mine = [f for f in faces if f[2] == item]
        if not mine:
            continue
        hp = wear(packs, rc, arm, parts, coll, item)
        ht = _tree(hp, piece_coords(hp))
        for i, p, _ in mine:
            h = KitHead(rc["id"], arm, parts, coll, eyes_at, item, skin_mat)
            face = build_face(h, p, skin, coll=coll, bind=False)
            add(stats, i, p, item, measure(face, item, ht))
            face.remove()
        log("CHECK %s %s: %d faces, %.0f s" % (g, item, len(mine), time.time() - t0))
    stats["tris_mean"] = round(stats.pop("tris_sum") / max(1, stats["faces"]), 1)
    stats["seconds"] = round(time.time() - t0, 1)
    return stats
