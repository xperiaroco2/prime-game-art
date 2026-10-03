"""The parts catalogue, part 4: pictures for the review page (docs/catalogue.md), rendered to files only.

sheets/    every item alone, by slot and body type, labelled with its id (clothing in the neutral pose)
matrices/  each pair matrix as a coloured grid: the verdict's status colour, its word and its number in every cell
confirm/   sample pairs assembled with um/assemble.py (build_character, rest pose) and rendered front and side, with
           seam close-ups: the confirmation that the verdicts match what one sees
"""

import json
import math
import os

import bpy
from mathutils import Matrix, Vector

import catalogue_heads as ch
from um import assemble, poses
from um import packs as pk
from um import render as rd
from um.util import update

# Status colours (the dataviz status palette): a verdict is a state, and every cell also carries its word.
STATUS = {"ok": "#0ca30c", "ok_tucked": "#0ca30c", "ok_over": "#0ca30c", "needs_fix": "#fab219", "poke": "#ec835a",
          "gap": "#d03b3b"}
WORD = {"ok": "ok", "ok_tucked": "tucked", "ok_over": "over", "needs_fix": "fix", "poke": "poke", "gap": "gap"}
INK = "#1a1a19"
TITLES = {"bottom_shoes": "bottom (rows) x shoes (columns): the ankle seam",
          "top_bottom": "top (rows) x bottom (columns): the waist seam",
          "head_top": "skull (rows) x top (columns): the neck seam",
          "hair_skull": "hair (rows) x skull (columns): the scalp"}


def linear(hexcol):
    def ch_(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    h = hexcol.lstrip("#")
    return tuple(ch_(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def flat_material(name, hexcol):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*linear(hexcol), 1.0)
    return m


def new_coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def drop_coll(c):
    for o in list(c.objects):
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
    bpy.data.collections.remove(c)


def hide_all():
    for o in bpy.data.objects:
        o.hide_render = True


def bake(obj, coll, name, yaw=0.0):
    """A static copy of the evaluated (posed) mesh in world space, turned by yaw about its own vertical axis."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    me.transform(ev.matrix_world)
    if yaw:
        xs = [v.co.x for v in me.vertices]
        ys = [v.co.y for v in me.vertices]
        c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0))
        me.transform(Matrix.Translation(c) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Translation(-c))
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def frame_points(objs, coll):
    """A vertex-only mesh at the bound-box corners of text objects, so the camera fit includes the labels."""
    update()  # a new label's matrix_world is only right after an update
    corners = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    me = bpy.data.meshes.new("frame_pts")
    me.from_pydata(corners, [], [])
    fo = bpy.data.objects.new("frame_pts", me)
    coll.objects.link(fo)
    return fo


def label(text, loc, size, coll, hexcol=INK):
    t = rd.label(text, loc, size, coll)
    t.data.materials.clear()
    t.data.materials.append(flat_material("ink_" + hexcol.lstrip("#"), hexcol))
    return t


# ---------------------------------------------------------------- contact sheets

def lay_row(entries, coll, z_label, gap=0.12, yaw=0.0, x0=0.0, label_size=0.035):
    """entries: [(text, object)]; baked side by side from x0, each labelled below at z_label. Returns (objects, x)."""
    out, x = [], x0
    for text, obj in entries:
        b = bake(obj, coll, "sheet_" + text, yaw)
        xs = [v.co.x for v in b.data.vertices]
        w = max(xs) - min(xs)
        dx = x + max(w, 0.30) / 2 - (min(xs) + max(xs)) / 2
        b.data.transform(Matrix.Translation((dx, 0.0, 0.0)))
        lines = text.split("\n")
        for k, line in enumerate(lines):
            out.append(label(line, (x + max(w, 0.30) / 2, -0.4, z_label - k * label_size * 1.3), label_size, coll))
        out.append(b)
        x += max(w, 0.30) + gap
    return out, x


def render_sheet(path, objs, coll, height=1100, rot=(90, 0, 0)):
    texts = [o for o in objs if o.type == "FONT"]
    meshes = [o for o in objs if o.type == "MESH"]
    fo = frame_points(texts, coll)
    rd.render(path, meshes + [fo], rot, height=height, margin=1.03)


def sheets(lib, data, items, out, log):
    os.makedirs(out, exist_ok=True)
    made = []
    for g in ("M", "W"):  # clothing in the neutral pose (arms lowered), so the sheets read like outfits
        poses.apply(lib.rigs[g], {"neutral": {"down_deg": 70.0}})
    for slot in ("top", "bottom", "shoes"):
        coll = new_coll("sheet_" + slot)
        hide_all()
        objs = []
        for r, g in enumerate(("M", "W")):
            z = -r * {"top": 1.2, "bottom": 1.45, "shoes": 0.85}[slot]  # a row's height: the parts' span and labels
            row = []
            for pid in lib.of(slot, g):
                e = data["parts"][pid]
                row.append(("%s\n%d tris" % (pid, e["triangles"]), lib.parts[pid]))
            o, _ = lay_row(row, coll, 0.0, label_size=0.05 if slot != "shoes" else 0.03)
            for b in o:
                b.location.z += z if b.type == "FONT" else 0.0
                if b.type == "MESH":
                    b.data.transform(Matrix.Translation((0.0, 0.0, z)))
            low = min(v.co.z for b in o if b.type == "MESH" for v in b.data.vertices)
            for b in o:
                if b.type == "FONT":
                    b.location.z += low - z - 0.08
            objs += o
            top = max(v.co.z for b in o if b.type == "MESH" for v in b.data.vertices)
            t = label({"M": "men's", "W": "women's"}[g] + " " + slot + "s" * (slot != "shoes"), (0.0, -0.4, top + 0.05),
                      0.05, coll)
            t.data.align_x = "LEFT"
            objs.append(t)
        update()
        path = os.path.join(out, "sheet_%s.png" % slot)
        render_sheet(path, objs, coll, height={"top": 1000, "bottom": 1300, "shoes": 800}[slot])
        made.append(path)
        drop_coll(coll)
    for g in ("M", "W"):
        poses.apply(lib.rigs[g], {"neutral": {"down_deg": 0.0}})
        lib_rest(lib.rigs[g])
    groups = [("skulls", ("skull",), 30.0), ("hair", ("hair",), 30.0), ("face", ("facial_hair", "brows"), 15.0),
              ("headwear", ("headwear", "earrings", "accessory"), 30.0)]
    for name, kinds, yaw in groups:
        coll = new_coll("sheet_" + name)
        hide_all()
        ids = sorted(i for i, e in items.items() if e["kind"] in kinds)
        per_row = 8 if name != "face" else 9
        span = max(items[i]["bounds"]["max_m"][2] - items[i]["bounds"]["min_m"][2] for i in ids)
        objs, made_objs = [], []
        for r in range(0, len(ids), per_row):
            row = []
            for iid in ids[r:r + per_row]:
                e = items[iid]
                tag = e.get("skull_type", e.get("style", e.get("subkind", "")))
                twin = e.get("same_geometry_as")
                text = iid + "\n" + ", ".join(x for x in (tag.replace("_", "-") if tag else "", "%d tris" % e["triangles"],
                                                          ("= " + twin) if twin else "") if x)
                o = ch.item_object(lib.head(e["head"], e["source"]["body_type"]), e["_faces"], "it_" + iid, coll)
                made_objs.append(o)
                row.append((text, o))
            o, _ = lay_row(row, coll, 0.0, yaw=yaw, label_size=0.018, gap=0.08)
            dz = -(r // per_row) * (span + 0.12)  # a row: the group's tallest item and its labels
            for b in o:
                if b.type == "MESH":
                    b.data.transform(Matrix.Translation((0.0, 0.0, dz)))
            low = min(v.co.z for b in o if b.type == "MESH" for v in b.data.vertices)
            for b in o:
                if b.type == "FONT":
                    b.location.z = b.location.z + low - 0.03
            objs += o
        for o in made_objs:
            o.hide_render = True
        update()
        path = os.path.join(out, "sheet_%s.png" % name)
        render_sheet(path, objs, coll, height=1500)
        made.append(path)
        drop_coll(coll)
    log("sheets: %d" % len(made))
    return made


def lib_rest(arm):
    pk.reset_pose(arm)
    arm.data.pose_position = "REST"
    update()


# ---------------------------------------------------------------- matrices

def cell_text(name, c):
    v = c["verdict"]
    word = WORD[v]
    if name == "hair_skull":
        n = c["rays"]
        num = "h%d p%d z%d" % (n["hole"], n["poke"], n["zfight"])
        if v == "needs_fix":
            word = "inflate"
    else:
        num = "%+d mm" % round(c["overlap_mm"])
        if v == "needs_fix":
            word = "fix %d" % round(c["fix"]["drop_m"] * 1000)
    return word, num


def short(pid):
    return pid.split("_", 2)[2]


def render_matrix(path, name, g, m, title):
    coll = new_coll("matrix")
    hide_all()
    W, H = 1.0, 0.5
    me = bpy.data.meshes.new("cells")
    verts, faces, mats = [], [], []
    keys = sorted(set(STATUS.values()))
    cells = {(c["a"], c["b"]): c for c in m["cells"]}
    texts = []
    lab_w = 2.3
    for i, r in enumerate(m["rows"]):
        z = -i * H
        texts.append(label(r, (-lab_w / 2 - 0.05, 0.0, z - H * 0.62), 0.13, coll))
        for j, col in enumerate(m["cols"]):
            c = cells[(r, col)]
            x = j * W
            n = len(verts)
            verts += [(x + 0.02, 0.0, z - H + 0.02), (x + W - 0.02, 0.0, z - H + 0.02), (x + W - 0.02, 0.0, z - 0.02),
                      (x + 0.02, 0.0, z - 0.02)]
            faces.append((n, n + 1, n + 2, n + 3))
            mats.append(keys.index(STATUS[c["verdict"]]))
            word, num = cell_text(name, c)
            texts.append(label(word, (x + W / 2, -0.01, z - H * 0.45), 0.15, coll))
            texts.append(label(num, (x + W / 2, -0.01, z - H * 0.82), 0.11, coll))
    for j, col in enumerate(m["cols"]):
        texts.append(label(short(col), (j * W + W / 2, 0.0, 0.12), 0.13, coll))
    texts.append(label(title, (len(m["cols"]) * W / 2 - lab_w / 2, 0.0, 0.55), 0.2, coll))
    # legend
    zl = -len(m["rows"]) * H - 0.35
    legend = [("ok / tucked / over", "ok"), ("fix: an assembler fix closes it", "needs_fix"), ("poke", "poke"), ("gap", "gap")]
    x = -lab_w
    for text, v in legend:
        n = len(verts)
        verts += [(x, 0.0, zl - 0.25), (x + 0.3, 0.0, zl - 0.25), (x + 0.3, 0.0, zl), (x, 0.0, zl)]
        faces.append((n, n + 1, n + 2, n + 3))
        mats.append(keys.index(STATUS[v]))
        t = label(text, (x + 0.4, 0.0, zl - 0.2), 0.14, coll)
        t.data.align_x = "LEFT"
        texts.append(t)
        x += 0.5 + 0.085 * len(text)
    me.from_pydata(verts, [], faces)
    for k in keys:
        me.materials.append(flat_material("status_" + k.lstrip("#"), k))
    for p, mi in zip(me.polygons, mats):
        p.material_index = mi
    grid = bpy.data.objects.new("cells", me)
    coll.objects.link(grid)
    for t in texts:
        if t.data.align_x == "CENTER" and t.location.x < 0 and t.location.z < 0.1:
            t.data.align_x = "RIGHT"
            t.location.x = -0.08
    update()
    fo = frame_points(texts, coll)
    scene = bpy.context.scene
    sh = scene.display.shading
    old = (sh.light, tuple(scene.world.color))
    sh.light = "FLAT"
    scene.world.color = (1.0, 1.0, 1.0)
    rd.render(path, [grid, fo], (90, 0, 0), height=max(700, int(90 * (len(m["rows"]) + 3))), margin=1.02)
    sh.light, scene.world.color = old[0], old[1]
    drop_coll(coll)


def matrices(data, out, log):
    os.makedirs(out, exist_ok=True)
    made = []
    for name, per in data["matrices"].items():
        for g, m in per.items():
            rig = {"M": "men's", "W": "women's"}[g]
            title = "%s - %s (%s rig)" % (TITLES[name], rig, g)
            path = os.path.join(out, "matrix_%s_%s.png" % (name, g.lower()))
            render_matrix(path, name, g, m, title)
            made.append(path)
    log("matrices: %d" % len(made))
    return made


# ---------------------------------------------------------------- confirmation renders

# Defaults for the slots a sample pair does not set: a plain outfit of the body type and the final test's face set.
BASE = {
    "M": {"head": "skull_m_beach", "hair": "hair_m_business", "top": "top_m_casual", "bottom": "bottom_m_casual",
          "shoes": "shoes_m_casual", "skin": [0.494, 0.334, 0.191],
          "eyes": {"style": "dots"}, "brows": {"style": "bushy_low", "rgb": [0.04, 0.02, 0.01]},
          "mouth": {"style": "smirk", "lip": [0.03, 0.008, 0.006]}},
    "W": {"head": "skull_w_suit", "hair": "hair_w_casual_bob", "top": "top_w_suit", "bottom": "bottom_w_suit",
          "shoes": "shoes_w_suit", "skin": [0.617, 0.418, 0.238],
          "eyes": {"style": "sleepy", "iris": [0.16, 0.07, 0.02], "lash": [0.02, 0.01, 0.008]},
          "brows": {"style": "thin_arch", "rgb": [0.1, 0.012, 0.004]}, "mouth": {"style": "smile", "lip": [0.5, 0.04, 0.07]}},
}

# The sample: (matrix, body type of the rig, row id, column id, why). The verdict shown is read from the data.
SAMPLE = [
    ("bottom_shoes", "W", "bottom_w_casual", "shoes_w_soldier", "trousers tucked into boots"),
    ("bottom_shoes", "M", "bottom_m_business", "shoes_m_worker", "trousers worn over boots"),
    ("bottom_shoes", "W", "bottom_w_formal", "shoes_w_casual", "a dress over flats"),
    ("top_bottom", "M", "top_m_hoodie", "bottom_m_business", "a hoodie over trousers"),
    ("top_bottom", "W", "top_w_casual", "bottom_w_scifi", "a top tucked into leggings"),
    ("head_top", "W", "skull_w_suit", "top_w_soldier", "a women's head on a women's top"),
    ("hair_skull", "M", "hair_m_business", "skull_m_farmer", "shell hair on an open-top skull"),
    ("hair_skull", "W", "hair_w_casual_bob", "skull_w_formal", "shell hair on a full skull"),
    ("bottom_shoes", "W", "bottom_w_witch", "shoes_w_formal", "a knee-length skirt over low shoes"),
    ("top_bottom", "W", "top_w_worker", "bottom_w_punk", "the Worker top at the waist"),
    ("bottom_shoes", "M", "bottom_m_astronaut", "shoes_m_hoodie", "short space-suit legs over low shoes"),
    ("bottom_shoes", "M", "bottom_m_hoodie", "shoes_m_adventurer", "shorts with bare legs in boots"),
    ("top_bottom", "M", "top_m_farmer", "bottom_m_adventurer", "the Farmer top over cargo trousers"),
    ("top_bottom", "W", "top_w_punk", "bottom_w_suit", "a crop top over suit trousers"),
    ("head_top", "W", "skull_m_business", "top_w_casual", "a men's head on a women's top"),
    ("hair_skull", "M", "hair_m_punk_mohawk", "skull_m_business", "cap hair on a full skull"),
    ("bottom_shoes", "M", "bottom_m_astronaut", "shoes_m_farmer", "a small gap: extend_edge"),
    ("head_top", "M", "skull_w_suit", "top_m_beach", "a women's neck in a men's vest: extend_edge"),
    ("hair_skull", "W", "hair_w_punk_mohawk", "skull_w_formal", "cap hair on a full skull: inflate"),
]

SEAM = {"bottom_shoes": ("ankle", (0.0, 0.0, 0.26), 0.6), "top_bottom": ("waist", (0.0, 0.0, 1.05), 0.55),
        "head_top": ("neck", (0.0, -0.03, 1.53), 0.36), "hair_skull": ("head", (0.0, -0.05, 1.72), 0.42)}


def part_spec(data, items, pid):
    if pid in data["parts"]:
        f = next(fe for fe in data["files"] if any(p["id"] == pid for p in fe["parts"].values()))
        return {"file": f["file"], "object": next(p["object"] for p in f["parts"].values() if p["id"] == pid)}
    return items[pid]["recipe"]


OK = ("ok", "ok_tucked", "ok_over")


def verdict_of(data, name, g, a, b):
    for c in data["matrices"][name][g]["cells"]:
        if c["a"] == a and c["b"] == b:
            return c["verdict"]
    return None


def fill(data, items, g, fixed):
    """The slots a sample pair does not set, chosen so that every other seam is ok: the defaults (BASE) first, then
    the catalogue's parts in order. Only the pair under test may show a defect."""
    unique = lambda i: items[i].get("same_geometry_as", i)  # noqa: E731
    out = dict(fixed)
    if "head" not in out:
        out["head"] = BASE[g]["head"]
    skull = unique(out["head"])
    skull_g = items[out["head"]]["source"]["body_type"]
    if "hair" not in out:
        hairs = [BASE[g]["hair"]] + sorted(i for i, e in items.items() if e["kind"] == "hair")
        out["hair"] = next(h for h in hairs if verdict_of(data, "hair_skull", skull_g, unique(h), skull) in OK
                           and not items[h]["recipe_check"]["proposed_zones"])  # the assembler knows its zones
    cand = {s: [BASE[g][s]] + sorted(p for p in data["parts"] if p.startswith("%s_%s_" % (s, g.lower())))
            for s in ("top", "bottom", "shoes")}
    for top in ([out["top"]] if "top" in out else cand["top"]):
        if verdict_of(data, "head_top", g, skull, top) not in OK and "top" not in fixed:
            continue
        for bottom in ([out["bottom"]] if "bottom" in out else cand["bottom"]):
            if "top" not in fixed or "bottom" not in fixed:
                if verdict_of(data, "top_bottom", g, top, bottom) not in OK:
                    continue
            for shoes in ([out["shoes"]] if "shoes" in out else cand["shoes"]):
                if ("bottom" not in fixed or "shoes" not in fixed) and verdict_of(data, "bottom_shoes", g, bottom, shoes) not in OK:
                    continue
                return dict(out, top=top, bottom=bottom, shoes=shoes)
    raise RuntimeError("no compatible outfit around %s" % fixed)


def character(data, items, g, cid, slots, fix=None):
    """A recipe character (docs/assembly.md) from item and part ids; fix: a needs_fix cell's fix, applied."""
    b = dict(BASE[g], **fill(data, items, g, slots))
    head = dict(items[b["head"]]["recipe"])
    hair = {k: v for k, v in items[b["hair"]]["recipe"].items() if k in ("file", "object", "materials", "cut")}
    hair["inflate"] = 0.0
    rc = {"id": cid, "gender": g, "head": head, "hair": hair,
          "top": part_spec(data, items, b["top"]), "bottom": part_spec(data, items, b["bottom"]),
          "shoes": part_spec(data, items, b["shoes"]), "eyes": b["eyes"], "brows": b["brows"], "mouth": b["mouth"],
          "skin": b["skin"], "pose": {"neutral": {"down_deg": 0.0}}}
    head_g = items[b["head"]]["source"]["body_type"]
    hair_g = items[b["hair"]]["source"]["body_type"]
    rc["_sources"] = {"head": head_g, "hair": hair_g}
    rc["_outfit"] = {k: b[k] for k in ("head", "hair", "top", "bottom", "shoes")}
    if fix and fix["fix"] == "extend_edge":
        rc["extend"] = [{"part": fix["part"], "drop": fix["drop_m"]}]
    if fix and fix["fix"] == "inflate":
        rc["hair"]["inflate"] = fix["amount"]
    return rc


class CrossPacks:
    """um.packs.Packs that loads a head or hair from the other body type's pack (heads cross body types)."""

    def __init__(self, packs, rc):
        self.packs, self.rc, self.calls = packs, rc, []

    def load(self, gender, fname):
        n = len(self.calls)
        self.calls.append(fname)
        g = gender
        if n == 1:
            g = self.rc["_sources"]["head"]
        elif n == 2:
            g = self.rc["_sources"]["hair"]
        return self.packs.load(g, fname)


def build(lib, recipe, rc, coll):
    cp_ = CrossPacks(lib.packs, rc)  # load order in build_character: skeleton, head, hair, extras, top, bottom, shoes
    arm, parts, rep = assemble.build_character(cp_, recipe, rc, coll)
    return arm, parts, rep


def remove_character(arm, coll):
    acts = pk.own_actions(arm)
    root = arm.parent
    drop_coll(coll)
    for o in (arm, root):
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except ReferenceError:
            pass
    bpy.data.batch_remove(acts)


def confirm(lib, data, items, raw_recipe, out, log):
    os.makedirs(os.path.join(out, "work"), exist_ok=True)
    made, notes = [], []
    rd.setup_render()
    for k, (name, g, a, b, why) in enumerate(SAMPLE):
        c = next(x for x in data["matrices"][name][g]["cells"] if x["a"] == a and x["b"] == b)
        variants = [("as is", None)] + ([("with " + c["fix"]["fix"], c["fix"])] if c["verdict"] == "needs_fix" else [])
        for vi, (vname, fix) in enumerate(variants):
            slot_a = {"bottom_shoes": "bottom", "top_bottom": "top", "head_top": "head", "hair_skull": "hair"}[name]
            slot_b = {"bottom_shoes": "shoes", "top_bottom": "bottom", "head_top": "top", "hair_skull": "head"}[name]
            cid = "c%02d%s" % (k + 1, "f" if vi else "")
            rc = character(data, items, g, cid, {slot_a: a, slot_b: b}, fix)
            coll = new_coll(cid)
            hide_all()
            arm, parts, rep = build(lib, raw_recipe, rc, coll)
            update()
            seam, centre, extent = SEAM[name]
            title = "%s x %s: %s (%s)%s" % (a, b, WORD[c["verdict"]] if c["verdict"] != "needs_fix" else "fix",
                                           why, "" if not vi else " - " + vname)
            t = label(title, (0.0, -0.6, 2.08), 0.06, coll)
            fo = frame_points([t], coll)
            objs = list(parts.values())
            shots = []
            for view, rot in (("front", (90, 0, 0)), ("side", (90, 0, 90))):
                t.hide_render = view != "front"
                p = os.path.join(out, "work", "%s_%s.png" % (cid, view))
                rd.render(p, objs + ([fo] if view == "front" else []), rot, height=900, margin=1.04)
                shots.append(p)
            fo.hide_render = True
            t.hide_render = True
            views = (("front", (90, 0, 0)), ("side", (90, 0, 90)))
            states = (("rest", None), ("walk", {"action": "Walk", "frame": 6}))
            if name == "hair_skull":
                views = (("front", (90, 0, 0)), ("above", (40, 0, 150)))
                states = states[:1]
            for state, pose in states:
                if pose:
                    poses.apply(arm, pose)
                for view, rot in views:
                    p = os.path.join(out, "work", "%s_%s_%s_close.png" % (cid, view, state))
                    rd.render(p, objs, rot, height=900, centre=Vector(centre), extent=extent, width=900)
                    shots.append(p)
            path = os.path.join(out, "%s_%s_%s.png" % (cid, short(a), short(b)))
            rd.compose(shots, path)
            made.append(path)
            notes.append({"image": os.path.basename(path), "matrix": name, "body_type": g, "a": a, "b": b,
                          "verdict": c["verdict"], "variant": vname, "why": why, "outfit": rc["_outfit"],
                          "panels": "full front, full side, then the seam close: front and side at rest"
                                    + ("" if name == "hair_skull" else ", front and side walking (Walk f6)"),
                          "probe_rest": rep["probe_rest"], "seam_overlap_rest": rep["seam_overlap_rest"]})
            remove_character(arm, coll)
    with open(os.path.join(out, "confirm.json"), "w", encoding="utf-8") as fh:
        json.dump(notes, fh, indent=1, sort_keys=True)
    log("confirm: %d images" % len(made))
    return made


def run(lib, data, items, heads, coll, args, modes, log):
    rd.RES_PERCENT = args.res
    rd.setup_render()
    out = os.path.abspath(args.out)
    if "sheets" in modes:
        sheets(lib, data, items, os.path.join(out, "sheets"), log)
    if "matrices" in modes:
        matrices(data, os.path.join(out, "matrices"), log)
    if "confirm" in modes:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "..", "..", "recipes", "um_final_test.json"), encoding="utf-8") as fh:
            raw_recipe = json.load(fh)
        raw_recipe["characters"] = []
        confirm(lib, data, items, raw_recipe, os.path.join(out, "confirm"), log)
