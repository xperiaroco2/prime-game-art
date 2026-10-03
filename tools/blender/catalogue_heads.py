"""The parts catalogue, part 2: every pack head split into what a menu can offer (docs/catalogue.md).

A pack head is one mesh whose material regions are the skin, eyes, brows, hair, facial hair, hats and earrings, and
some materials mix things (women's "Brown" holds the eyes and, on Formal and Medieval, the brows; Punk "Red" includes a
goatee; King's and the men's Adventurer's hair include beards and moustaches; the men's Farmer and Worker "Eyebrows"
also hold the scalp cap of their open-top skulls). So regions are found by material AND by geometry: each material's
faces are split into connected pieces, and each piece is classified by its material's role and its position on the
head (um/zones.py's brow box and our facial-hair box). Items are the pieces grouped by kind; each item gets a stable id
and an extraction recipe in the assembler's terms (file, object, materials, cut zones), checked face by face.
"""

import hashlib

import bmesh

import catalogue_parts as cp
from um import zones
from um.util import base_name, tris

# Material roles that hold for every head.
MATERIAL_ROLE = {"Skin": "skull", "Skin_Darker": "skull", "Eye": "eyes", "Eyebrows": "brows",
                 "Moustache": "facial_hair", "Earrings": "accessory"}
EYE_MATERIAL = {"M": "Eye", "W": "Brown"}

# Per head: materials that are headwear, an accessory or the neck's closing ring rather than hair ("*" = every
# material: a helmet that is the whole head). Read off the pack renders, checked by the pieces' positions.
HEAD_ROLE = {
    ("M", "astronaut"): {"*": "headwear"},
    ("M", "swat"): {"*": "headwear"},
    ("M", "farmer"): {"Beige": "headwear", "Red": "headwear"},
    ("M", "king"): {"Gold": "headwear"},
    ("M", "worker"): {"Worker_Yellow": "headwear"},
    ("W", "worker"): {"Worker_Yellow": "headwear"},
    ("W", "witch"): {"Purple": "headwear", "Gold": "headwear"},
    ("W", "medieval"): {"DarkBrown": "headwear", "Black": "neck_ring"},
    ("W", "scifi"): {"Blue": "accessory", "Black": "neck_ring"},
    ("W", "punk"): {"Black": "by_position"},  # the neck's closing ring and a nose ring share the material
}

# Readable suffixes of item ids (an id is <kind>_<m|w>_<character>[_<descriptor>]).
DESCRIPTOR = {
    "hair_m_punk": "mohawk", "hair_w_punk": "mohawk", "hair_m_farmer": "buzz", "hair_m_worker": "buzz",
    "hair_m_king": "long", "hair_w_formal": "updo", "hair_w_casual": "bob", "hair_w_suit": "bob",
    "headwear_m_farmer": "cowboy_hat", "headwear_m_king": "crown", "headwear_m_worker": "hard_hat",
    "headwear_w_worker": "hard_hat", "headwear_w_witch": "hat", "headwear_w_medieval": "hood",
    "headwear_m_astronaut": "space_helmet", "headwear_m_swat": "helmet",
    "accessory_w_scifi": "headset", "accessory_w_punk": "nose_ring",
}


# The facial-hair box (a piece's centre, or a face's centre for the assembler's cut zones): below the cheekbones, in
# front of the jaw, inside the jaw's width. The moustache box: the upper lip.
def FACIAL_HAIR(c):
    return c.z < 1.655 and c.y < -0.09 and abs(c.x) < 0.07


def MOUSTACHE(c):
    return 1.605 < c.z < 1.655 and c.y < -0.13 and abs(c.x) < 0.065


def BROWS(c):
    return zones.BROW_ZONE(c) and c.z > BROW_Z_MIN


BROW_Z_MIN = 1.698  # between the women's eye centres (about 1.690) and brow centres (about 1.705) in "Brown"
BROW_PIECE_TRIS = 64  # a brow piece has 12 to 40 triangles; a fringe piece whose centre falls in the brow box, hundreds


def brow_piece(pc):
    return zones.BROW_ZONE(pc.centre) and pc.triangles <= BROW_PIECE_TRIS


# Cut zones the catalogue's recipes may name: um/zones.py's own, plus these proposed ones (not yet in um/zones.py;
# docs/catalogue.md). A cut removes the faces whose centre is inside.
PROPOSED_ZONES = {
    "facial_hair": FACIAL_HAIR,
    "not_facial_hair": lambda c: not FACIAL_HAIR(c),
    "moustache": MOUSTACHE,
    "not_moustache": lambda c: not MOUSTACHE(c),
    "not_chin_tuft": lambda c: not zones.CUT_ZONES["chin_tuft"](c),
    "not_brows": lambda c: not BROWS(c),
    "brows": BROWS,
    "not_brow_zone": lambda c: not zones.BROW_ZONE(c),
}
ALL_ZONES = dict(zones.CUT_ZONES, **PROPOSED_ZONES)
CUT_CANDIDATES = ([], ["chin_tuft"], ["facial_hair"], ["not_facial_hair", "moustache"], ["not_facial_hair"],
                  ["not_moustache"], ["not_chin_tuft"], ["not_brow_zone"], ["not_brows"], ["brows"])


class Piece:
    def __init__(self, material, faces, pts, tri):
        self.material, self.faces, self.triangles = material, faces, tri
        self.lo = [min(p[i] for p in pts) for i in range(3)]
        self.hi = [max(p[i] for p in pts) for i in range(3)]
        self.centre = type(pts[0])([(a + b) / 2 for a, b in zip(self.lo, self.hi)])
        self.kind = self.sub = None


def pieces(obj):
    """Connected pieces per material (flat-shaded imports split every vertex, so faces are joined by shared world
    positions, rounded to 0.01 mm), largest material index first-seen order, deterministic."""
    me, mw = obj.data, obj.matrix_world
    key = [tuple(round(c, 5) for c in (mw @ v.co)) for v in me.vertices]
    parent = list(range(len(me.polygons)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first = {}
    for p in me.polygons:
        for vi in p.vertices:
            k = (p.material_index, key[vi])
            if k in first:
                a, b = find(p.index), find(first[k])
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                first[k] = p.index
    groups = {}
    for p in me.polygons:
        groups.setdefault(find(p.index), []).append(p.index)
    names = [base_name(m.name) if m else "" for m in me.materials]
    out = []
    for root in sorted(groups):
        faces = groups[root]
        pts = [mw @ me.vertices[vi].co for fi in faces for vi in me.polygons[fi].vertices]
        tri = sum(len(me.polygons[fi].vertices) - 2 for fi in faces)
        out.append(Piece(names[me.polygons[root].material_index], faces, pts, tri))
    return out


def classify(g, char, pc):
    """Sets pc.kind (skull, eyes, brows, hair, facial_hair, headwear, accessory, neck_ring) and pc.sub."""
    roles = HEAD_ROLE.get((g, char), {})
    role = roles.get("*") or roles.get(pc.material) or MATERIAL_ROLE.get(pc.material)
    c = pc.centre
    if pc.material == EYE_MATERIAL["W"] and g == "W" and role is None:
        role = "brows" if pc.hi[2] > zones.EYE_Z_MAX else "eyes"  # Formal and Medieval: brows above the eyes
    if role == "by_position":
        role = "neck_ring" if pc.hi[2] < 1.58 and abs(c.x) < 0.01 else "accessory"
    if role == "brows" and not zones.BROW_ZONE(c):
        role = "hair"  # the men's Farmer and Worker scalp cap is in "Eyebrows"
    if role is None:  # a hair material
        if brow_piece(pc):
            role = "brows"
        elif FACIAL_HAIR(c):
            role = "facial_hair"
        else:
            role = "hair"
    pc.kind = role
    if role == "facial_hair":
        h = pc.hi[2] - pc.lo[2]
        pc.sub = "moustache" if MOUSTACHE(c) and h < 0.035 else "beard"
    if role == "skull" and pc.material == "Skin_Darker":
        pc.sub = "stubble"


def signature(obj, faces):
    """Geometry hash of an item (its faces' world vertices rounded to 1 mm, order-free): equal items share it."""
    me, mw = obj.data, obj.matrix_world
    pts = sorted(tuple(round(x, 3) for x in (mw @ me.vertices[vi].co)) for fi in faces for vi in me.polygons[fi].vertices)
    return hashlib.sha1(repr(pts).encode()).hexdigest()[:12]


def face_centres(obj):
    me, mw = obj.data, obj.matrix_world
    return [mw @ p.center for p in me.polygons]


def recipe_faces(obj, centres, mats, role, cuts):
    """The faces the assembler keeps for an extras/hair spec (um/assemble.py's filter, face centres in world space)."""
    me = obj.data
    names = [base_name(m.name) if m else "" for m in me.materials]
    zs = [ALL_ZONES[z] for z in cuts]
    return {p.index for p in me.polygons if names[p.material_index] in mats
            and (role != "hair" or not zones.BROW_ZONE(centres[p.index])) and not any(z(centres[p.index]) for z in zs)}


# Zones tested on whole pieces: a piece is inside when its centre is; the brow box also asks for a brow's size.
PIECE_ZONES = {"brows": lambda pc: brow_piece(pc) and pc.centre.z > BROW_Z_MIN,
               "not_brows": lambda pc: not (brow_piece(pc) and pc.centre.z > BROW_Z_MIN),
               "not_brow_zone": lambda pc: not brow_piece(pc)}


def piece_in(name, pc):
    return PIECE_ZONES[name](pc) if name in PIECE_ZONES else ALL_ZONES[name](pc.centre)


def piece_recipe_faces(pcs, mats, role, cuts):
    """The same filter applied to whole pieces (PIECE_ZONES; the hair role leaves out brow pieces): what the assembler
    would keep if its zones tested connected pieces instead of single faces (docs/catalogue.md, a proposed change)."""
    return {f for pc in pcs if pc.material in mats and (role != "hair" or not brow_piece(pc))
            and not any(piece_in(z, pc) for z in cuts) for f in pc.faces}


def find_cut(obj, centres, pcs, faces, mats, role):
    """The first cut list (CUT_CANDIDATES) that keeps exactly the item's faces when zones test pieces, preferring one
    that is also exact face by face (today's assembler). Returns (cuts, piece mismatch, face mismatch)."""
    best = None
    for cuts in CUT_CANDIDATES:
        by_piece = len(piece_recipe_faces(pcs, mats, role, cuts) ^ faces)
        by_face = len(recipe_faces(obj, centres, mats, role, cuts) ^ faces)
        if best is None or (by_piece, by_face) < best[1:]:
            best = (cuts, by_piece, by_face)
        if by_piece == 0 and by_face == 0:
            break
    return best


def item_id(kind, g, char):
    base = "%s_%s_%s" % (kind, g.lower(), char)
    return base + ("_" + DESCRIPTOR[base] if base in DESCRIPTOR else "")


def analyse(lib, file_entries):
    """Returns (heads, items): per head its skull, regions and items; items {id: {...}} with recipes."""
    heads, items = {}, {}
    skin_top = {}
    for fe in file_entries:
        g, char = fe["body_type"], fe["character"]
        hp = fe["parts"]["head"]
        obj = lib.head(hp["id"], g)
        pcs = pieces(obj)
        for pc in pcs:
            classify(g, char, pc)
        skull = [pc for pc in pcs if pc.kind in ("skull", "neck_ring")]
        skin = [pc for pc in pcs if pc.kind == "skull"]
        top = max(pc.hi[2] for pc in skin) if skin else None
        skin_top[hp["id"]] = top
        heads[hp["id"]] = {"g": g, "char": char, "file": fe["file"], "object": hp["object"], "obj": obj, "pieces": pcs,
                           "materials": cp.materials(obj, lib.colours[hp["id"]]), "triangles": tris(obj),
                           "bounds": cp.bounds(cp.world_verts(obj)), "skin_top": top, "neck_bottom": min(pc.lo[2] for pc in skull) if skull else None}
    # skull type: full when the skin reaches the body type's highest skull top (within 5 mm), else open-top
    for hid, h in heads.items():
        tops = [v["skin_top"] for v in heads.values() if v["g"] == h["g"] and v["skin_top"] is not None]
        if h["skin_top"] is None:
            h["skull_type"] = "none"
        else:
            h["skull_type"] = "full" if h["skin_top"] >= max(tops) - 0.005 else "open_top"
    for hid in sorted(heads):
        h = heads[hid]
        g, char, obj = h["g"], h["char"], h["obj"]
        centres = face_centres(obj)
        groups = {}
        for pc in h["pieces"]:
            if pc.kind in ("eyes",):
                continue
            if pc.kind in ("skull", "neck_ring"):
                groups.setdefault("skull", []).append(pc)
                if pc.sub == "stubble":
                    groups.setdefault("stubble", []).append(pc)
            elif pc.kind == "facial_hair":
                groups.setdefault(pc.sub, []).append(pc)
            elif pc.kind == "accessory":
                groups.setdefault("earrings" if pc.material == "Earrings" else "accessory", []).append(pc)
            else:
                groups.setdefault(pc.kind, []).append(pc)
        if "beard" in groups and all(abs(pc.centre.x) < 0.025 for pc in groups["beard"]):
            groups["goatee"] = groups.pop("beard")  # only chin pieces: a goatee
        h["items"] = []
        for kind in sorted(groups):
            pcs = groups[kind]
            faces = {f for pc in pcs for f in pc.faces}
            mats = sorted({pc.material for pc in pcs})
            rgb = {m["name"]: m["rgb"] for m in h["materials"]}
            iid = item_id(kind, g, char)
            entry = {"kind": "facial_hair" if kind in ("moustache", "beard", "goatee", "stubble") else kind,
                     "head": hid, "source": {"body_type": g, "file": h["file"], "object": h["object"]},
                     "materials": mats, "colours": [{"name": m, "rgb": rgb[m]} for m in mats], "pieces": len(pcs), "triangles": sum(pc.triangles for pc in pcs),
                     "bounds": {"min_m": [round(min(pc.lo[i] for pc in pcs), 4) for i in range(3)],
                                "max_m": [round(max(pc.hi[i] for pc in pcs), 4) for i in range(3)]},
                     "geometry": signature(obj, faces)}
            if kind in ("moustache", "beard", "goatee", "stubble"):
                entry["subkind"] = kind
            if kind == "skull":
                skin_mats = sorted({pc.material for pc in pcs if pc.kind == "skull" and pc.material == "Skin"})
                as_skin = sorted({pc.material for pc in pcs if pc.material != "Skin"})
                entry["skull_type"] = h["skull_type"]
                entry["skin_top_m"] = round(h["skin_top"], 4)
                entry["neck_bottom_m"] = round(h["neck_bottom"], 4)
                entry["recipe"] = {"file": h["file"], "object": h["object"], "keep": skin_mats,
                                   "eye_materials": [EYE_MATERIAL[g]]}
                if as_skin:
                    entry["recipe"]["as_skin"] = as_skin
                rings = sorted({pc.material for pc in pcs if pc.kind == "neck_ring"})
                if rings:
                    entry["recipe"]["straighten"] = rings
                entry["recipe_check"] = {"faces": len(faces), "mismatch_by_face": 0, "mismatch_by_piece": 0}
            elif kind == "stubble":
                entry["painted"] = True
                entry["recipe"] = {"note": "a colour region of the skull: keep Skin_Darker out of as_skin to show it",
                                   "file": h["file"], "object": h["object"], "materials": mats}
                entry["recipe_check"] = {"faces": len(faces), "mismatch_by_face": 0, "mismatch_by_piece": 0}
            else:
                role = "hair" if kind == "hair" else kind
                cuts, by_piece, by_face = find_cut(obj, centres, h["pieces"], faces, set(mats), role)
                entry["recipe"] = {"role": role, "file": h["file"], "object": h["object"], "materials": mats, "cut": cuts}
                entry["recipe_check"] = {"faces": len(faces), "mismatch_by_face": by_face, "mismatch_by_piece": by_piece,
                                         "proposed_zones": sorted(z for z in cuts if z in PROPOSED_ZONES)}
            if kind == "hair":
                entry["source_skull_type"] = h["skull_type"]
                entry["style"] = {"open_top": "cap", "full": "shell"}.get(h["skull_type"], "helmet")
            entry["_faces"] = faces
            items[iid] = entry
            h["items"].append(iid)
    # equal geometry (within 0.5 mm, catalogue_parts.same_mesh): the later id points at the first
    from catalogue_parts import same_mesh
    pts = {}
    for iid, e in items.items():
        o, me = heads[e["head"]]["obj"], heads[e["head"]]["obj"].data
        pts[iid] = [o.matrix_world @ me.vertices[vi].co for fi in sorted(e["_faces"]) for vi in me.polygons[fi].vertices]
    for iid in sorted(items):
        e = items[iid]
        twin = next((q for q in sorted(items) if q < iid and "same_geometry_as" not in items[q]
                     and items[q]["kind"] == e["kind"] and same_mesh(pts[q], pts[iid])), None)
        if twin:
            e["same_geometry_as"] = twin
    return heads, items


def head_record(hid, h):
    regions = {}
    for pc in h["pieces"]:
        r = regions.setdefault((pc.kind, pc.sub or "", pc.material), {"kind": pc.kind, "material": pc.material,
                                                                      "pieces": 0, "triangles": 0})
        if pc.sub:
            r["subkind"] = pc.sub
        r["pieces"] += 1
        r["triangles"] += pc.triangles
    out = {"source": {"body_type": h["g"], "file": h["file"], "object": h["object"]}, "skull_type": h["skull_type"],
           "skin_top_m": round(h["skin_top"], 4) if h["skin_top"] is not None else None,
           "neck_bottom_m": round(h["neck_bottom"], 4) if h["neck_bottom"] is not None else None,
           "materials": h["materials"], "triangles": h["triangles"], "bounds": h["bounds"],
           "regions": [regions[k] for k in sorted(regions)], "items": sorted(h["items"])}
    return out


def item_object(head_obj, faces, name, coll):
    """A copy of the head keeping only faces (same rig, Armature modifier kept)."""
    o = head_obj.copy()
    o.data = head_obj.data.copy()
    o.name = name
    coll.objects.link(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    gone = [f for f in bm.faces if f.index not in faces]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o
