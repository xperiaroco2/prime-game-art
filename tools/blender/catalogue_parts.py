"""The parts catalogue, part 1: the pack files, their characters and their four parts, loaded once onto one rig per
body type and measured in the rest pose (docs/catalogue.md).

Every part of a body type is rebound (um/rebind.py) onto that body type's skeleton file (Business Man for the men,
Suit for the women, as in the assembler's recipes) and parented to its armature, so all parts of a body type share
one rest pose and their numbers compare directly. Heads cross body types: each head is rebound onto both rigs.
World space: metres, +Z up, the face toward -Y, +X the character's left.
"""

import json
import struct

import bpy
from mathutils import Vector

from um import fit
from um.packs import attach, discard
from um.rebind import rebind
from um.util import base_name, tris, update

GENDERS = ("M", "W")
SKELETON = {"M": "Business Man.glb", "W": "Suit.glb"}

# The character name of every pack file, used in ids. The women's "Animated Woman.glb" is the Casual character and
# "Animated Woman-nIItLV9nxS.glb" the Formal one (their objects are Casual_* and Formal_*): two different characters.
CHARACTER = {
    "M": {"Adventurer.glb": "adventurer", "Astronaut.glb": "astronaut", "Beach Character.glb": "beach",
          "Business Man.glb": "business", "Casual Character.glb": "casual", "Farmer.glb": "farmer",
          "Hoodie Character.glb": "hoodie", "King.glb": "king", "Punk.glb": "punk", "Swat.glb": "swat",
          "Worker.glb": "worker"},
    "W": {"Adventurer.glb": "adventurer", "Animated Woman.glb": "casual", "Animated Woman-nIItLV9nxS.glb": "formal",
          "Medieval.glb": "medieval", "Punk.glb": "punk", "Sci Fi Character.glb": "scifi", "Soldier.glb": "soldier",
          "Suit.glb": "suit", "Witch.glb": "witch", "Worker.glb": "worker"},
}

# Object name suffix -> slot. A pack character has exactly one object per slot; other mesh objects are props.
SLOT_SUFFIX = (("_Head", "head"), ("_Body", "top"), ("_Legs", "bottom"), ("_Pants", "bottom"), ("_Feet", "shoes"))
SLOTS = ("head", "top", "bottom", "shoes")

# Things built into a part's mesh that a menu should know about (seen on the renders, checked by the bounds: the
# women's Adventurer top reaches 0.20 m behind the body, the men's 0.07 m).
BUILT_IN = {"top_w_adventurer": ["backpack"]}

NECK_REACH = 0.10  # a top's neck ring: its vertices within this horizontal distance of the Neck bone
LEG_REACH = 0.13  # a bottom's leg: its vertices within this horizontal distance of the Foot bone (as um/fit.py)


def mm(x):
    return round(x * 1000.0, 1)


def m4(x):
    return round(x, 4)


def slot_of(name):
    return next((slot for suffix, slot in SLOT_SUFFIX if name.endswith(suffix)), None)


def part_id(slot, g, char):
    return "%s_%s_%s" % (slot, g.lower(), char)


def world_verts(obj):
    mw = obj.matrix_world
    return [mw @ v.co for v in obj.data.vertices]


def bounds(pts):
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return {"min_m": [m4(x) for x in lo], "max_m": [m4(x) for x in hi]}


def glb_json(path):
    """The JSON chunk of a GLB file (pure Python)."""
    with open(path, "rb") as fh:
        head = fh.read(20)
        return json.loads(fh.read(struct.unpack("<I", head[12:16])[0]))


def node_colours(js):
    """{node name: [(material name, rgb)]}: the materials of each mesh node's primitives in order, with the glTF
    baseColorFactor (linear). The importer's viewport colour cannot be trusted: on meshes with a COLOR_0 attribute
    (white in these packs) it leaves Blender's default 0.8 grey (the men's Business and Casual trousers)."""
    out = {}
    for n in js.get("nodes", []):
        if "mesh" not in n:
            continue
        seen, mats = set(), []
        for p in js["meshes"][n["mesh"]]["primitives"]:
            i = p.get("material")
            if i is None or i in seen:
                continue
            seen.add(i)
            m = js["materials"][i]
            f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])
            mats.append((m["name"], [round(c, 3) for c in f[:3]]))
        out[n["name"]] = mats
    return out


def materials(obj, colours=None):
    """[{name, rgb, triangles}] in slot order; rgb (linear) is the GLB's baseColorFactor of the material of that name
    on the object's source node (colours, from node_colours; equal names are taken in order), else the viewport
    colour."""
    me = obj.data
    count = [0] * len(me.materials)
    for p in me.polygons:
        count[p.material_index] += len(p.vertices) - 2
    pool = list(colours or [])
    out = []
    for i, m in enumerate(me.materials):
        if m is None:
            continue
        name = base_name(m.name)
        k = next((j for j, (n, _) in enumerate(pool) if n == name), None)
        rgb = pool.pop(k)[1] if k is not None else [round(c, 3) for c in m.diffuse_color[:3]]
        out.append({"name": name, "rgb": rgb, "triangles": count[i]})
    return out


class Library:
    """Every pack file loaded: rigs[g] (the skeleton file's armature), parts[part_id] = object on its rig, heads on both
    rigs (heads[g][head_id]), the files' table of contents, and the props found."""

    def __init__(self, packs, coll):
        self.packs = packs
        self.coll = coll
        self.rigs, self.parts, self.heads, self.files, self.info = {}, {}, {"M": {}, "W": {}}, [], {}
        self.colours = {}  # part or head id -> node_colours() of its source object

    def load_all(self):
        for g in GENDERS:
            sk = self.packs.load(g, SKELETON[g])
            discard(sk, keep=[sk["arm"], sk["root"]])
            sk["arm"].name = "rig_" + g
            sk["arm"].data.pose_position = "REST"
            self.rigs[g] = sk["arm"]
        update()
        for g in GENDERS:
            names = CHARACTER[g]
            found = sorted(p.name for p in self.packs.folders[g].glob("*.glb"))
            unknown = [f for f in found if f not in names]
            missing = [f for f in names if f not in found]
            if unknown or missing:
                raise RuntimeError("pack %s: unknown files %s, missing files %s (update CHARACTER)" % (g, unknown, missing))
            for fname in found:
                self._load_file(g, fname)
        update()

    def _load_file(self, g, fname):
        char = CHARACTER[g][fname]
        src = self.packs.load(g, fname)
        colours = node_colours(glb_json(self.packs.folders[g] / fname))
        placed, entry = [], {"body_type": g, "file": fname, "character": char, "parts": {}, "props": []}
        for name in sorted(src["meshes"]):
            obj = src["meshes"][name]
            slot = slot_of(name)
            if slot is None:
                entry["props"].append(name)
                continue
            if slot in entry["parts"]:
                raise RuntimeError("%s/%s has two %s objects" % (g, fname, slot))
            pid = part_id(slot, g, char)
            entry["parts"][slot] = {"id": pid, "object": name}
            self.colours[pid] = colours.get(name, [])
            if slot == "head":  # heads cross body types: one copy per rig, both rebound from the source rest
                for tg in GENDERS:
                    o = obj
                    if tg != g:
                        o = obj.copy()
                        o.data = obj.data.copy()
                        self.coll.objects.link(o)
                    placed.append((o, tg, pid))
                    self.heads[tg][pid] = o
            else:
                placed.append((obj, g, pid))
                self.parts[pid] = obj
        for o, tg, pid in placed:
            rebind(o, src["arm"], self.rigs[tg])
            attach(o, self.rigs[tg])
            o.name = "%s@%s" % (pid, tg)
            for c in list(o.users_collection):
                c.objects.unlink(o)
            self.coll.objects.link(o)
        discard(src, keep=[o for o, _, _ in placed])
        self.files.append(entry)
        if len(entry["parts"]) != 4:
            raise RuntimeError("%s/%s: parts %s, expected head, top, bottom and shoes" % (g, fname, sorted(entry["parts"])))

    def of(self, slot, g):
        """Part ids of a slot and body type, sorted."""
        return sorted(pid for pid in self.parts if pid.startswith(slot + "_" + g.lower() + "_"))

    def head(self, pid, g):
        return self.heads[g][pid]


def foot_centre(arm, side):
    return arm.matrix_world @ arm.data.bones["Foot." + side].head_local


def neck_point(arm):
    return arm.matrix_world @ arm.data.bones["Neck"].head_local


def top_seams(obj, arm):
    lo, hi = fit.zspan(obj)
    n = neck_point(arm)
    ring = [p for p in world_verts(obj) if Vector((p.x - n.x, p.y - n.y)).length < NECK_REACH and p.z > n.z - 0.15]
    return {"upper_edge_m": m4(hi), "lower_edge_m": m4(lo), "neck_ring_top_m": m4(max(p.z for p in ring)) if ring else None}


def leg_lows(obj, arm):
    pts = world_verts(obj)
    out = {}
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        c = foot_centre(arm, side)
        leg = [p for p in pts if p.x * sgn > 0 and Vector((p.x - c.x, p.y - c.y)).length < LEG_REACH]
        out[side] = min(p.z for p in leg) if leg else None
    return out


def bottom_seams(obj, arm):
    lo, hi = fit.zspan(obj)
    legs = leg_lows(obj, arm)
    return {"upper_edge_m": m4(hi), "lower_edge_m": m4(lo),
            "leg_lower_edge_m": {s: (m4(v) if v is not None else None) for s, v in legs.items()}}


def collars(obj, arm):
    pts = fit.shoe_points(obj)
    out = {}
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        top = fit.collar_heights([p for p in pts if p.x * sgn > 0], foot_centre(arm, side))
        vals = [t for t in top if t is not None]
        out[side] = {"min_m": m4(min(vals)), "max_m": m4(max(vals)), "sectors_m": [m4(t) if t is not None else None for t in top]}
    return out


def shoe_seams(obj, arm):
    lo, hi = fit.zspan(obj)
    return {"top_edge_m": m4(hi), "collar": collars(obj, arm)}


def inventory(lib):
    """{part_id: {...}} for tops, bottoms and shoes (heads are described by catalogue_heads)."""
    out, verts = {}, {}
    for pid, obj in sorted(lib.parts.items()):
        slot, g = pid.split("_")[0], pid.split("_")[1].upper()
        arm = lib.rigs[g]
        pts = world_verts(obj)
        entry = {"slot": slot, "body_type": g, "triangles": tris(obj), "vertices": len(obj.data.vertices),
                 "materials": materials(obj, lib.colours[pid]), "bounds": bounds(pts)}
        if pid in BUILT_IN:
            entry["built_in"] = BUILT_IN[pid]
        if slot == "top":
            entry["seams"] = top_seams(obj, arm)
        elif slot == "bottom":
            entry["seams"] = bottom_seams(obj, arm)
        elif slot == "shoes":
            entry["seams"] = shoe_seams(obj, arm)
        out[pid] = entry
        verts[pid] = pts
    for pid in sorted(out):  # equal meshes of the same slot and body type: the later points at the first
        e = out[pid]
        twin = next((q for q in sorted(out) if q < pid and "same_geometry_as" not in out[q] and out[q]["slot"] == e["slot"]
                     and out[q]["body_type"] == e["body_type"] and same_mesh(verts[q], verts[pid])), None)
        if twin:
            e["same_geometry_as"] = twin
    return out


def same_mesh(a, b, tol=0.0005):
    """True when two vertex sets are equal within tol (each point of one has a point of the other that close; the
    counts match). A rounded hash is not enough: rebinding leaves points near rounding boundaries."""
    from mathutils.kdtree import KDTree
    if len(a) != len(b):
        return False
    for x, y in ((a, b), (b, a)):
        kd = KDTree(len(y))
        for i, p in enumerate(y):
            kd.insert(p, i)
        kd.balance()
        if any(kd.find(p)[2] > tol for p in x):
            return False
    return True


def copy_part(obj, name, coll):
    """A linked-free copy of a part on the same rig (its own mesh data), for destructive fits."""
    o = obj.copy()
    o.data = obj.data.copy()
    o.name = name
    coll.objects.link(o)
    return o


def remove(obj):
    me = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)
