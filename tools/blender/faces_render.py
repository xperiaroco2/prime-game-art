"""The face kit's review sheets (docs/faces.md): every style family of faces/styles.json in every expression on the
review heads of faces/review.json, built with the assembler (tools/blender/um/), measured and rendered.

The runner calls it (tools/run.py faces); by hand, background only:
  blender -b --factory-startup --python-exit-code 1 --python tools/blender/faces_render.py -- \
      --styles faces/styles.json --review faces/review.json --raw D:/prime-art-raw --out tools/out/faces \
      [--families f1_dots,f3_almond] [--expressions neutral,closed] [--sheets close,distance,overview,strip|none]
      [--res 100]

Writes into --out: faces_report.json (per family and expression: triangles, materials and the skin clearance of each
part; the distance pixel sizes; the head-follow check of the frame strip) and the sheets: <family>_front.jpg,
<family>_threequarter.jpg (rows: expressions; columns: heads and skin tones), <family>_distance.png (the face at the
game's distances, nearest-neighbour enlarged), overview.jpg (every family, neutral), strip_<head>_<family>.jpg (frames
of a pack action); work/ holds the single renders.
"""

import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import faces_styles as fst  # noqa: E402
from um import assemble, heads as hd, poses  # noqa: E402
from um import facekit as fk  # noqa: E402
from um import packs as pk  # noqa: E402
from um import recipe as recipes  # noqa: E402
from um import render as rd  # noqa: E402
from um import zones  # noqa: E402
from um.materials import set_color  # noqa: E402
from um.util import tris, update  # noqa: E402

SPACING = 0.45  # metres between the review heads standing side by side
CELL_M = 0.32  # the close-up window, square, metres
CELL_Z = 1.705  # its centre height: chin to the top of a full skull's hair
PPM = 1200  # close-up pixels per metre at --res 100 (a 384 px cell)
YAW_34 = 35.0  # the three-quarter view: each head turned by this, the camera frontal
FACE_PARTS = ("eyes", "brows", "mouth")
BG = 0.8  # sheet background (display value)
SEP = 4  # pixels between cells


def show(name):
    """A label for a family id or an expression name (the default font draws no underscore)."""
    if name.startswith("talk_"):
        return "talk (%s)" % name[5:]
    return name.replace("_", " ")


def fam_title(fid, fam):
    return "%s %s" % (fid.split("_")[0].upper(), fam["name"])


def parse():
    p = argparse.ArgumentParser(prog="faces_render.py")
    p.add_argument("--styles", required=True)
    p.add_argument("--review", required=True)
    p.add_argument("--raw", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--families", default="")
    p.add_argument("--expressions", default="")
    p.add_argument("--sheets", default=",".join(fst.SHEETS))
    p.add_argument("--res", type=int, default=100)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


# ----------------------------------------------------------------------------------------------- images
def load_png(path):
    """(H, W, 4) float array, top row first."""
    im = bpy.data.images.load(path)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[::-1].copy()
    bpy.data.images.remove(im)
    return a


def save_image(arr, path, fmt="PNG", quality=90):
    h, w = arr.shape[:2]
    img = bpy.data.images.new("out", w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).ravel())
    img.filepath_raw = path
    img.file_format = fmt
    if fmt == "JPEG":
        scene = bpy.context.scene
        scene.render.image_settings.file_format = "JPEG"
        scene.render.image_settings.quality = quality
        img.save_render(path, scene=scene)
        scene.render.image_settings.file_format = "PNG"
    else:
        img.save()
    bpy.data.images.remove(img)
    print("SAVED", path, w, "x", h)


def canvas(h, w):
    a = np.ones((h, w, 4), dtype=np.float32)
    a[..., :3] = BG
    return a


def paste(dst, src, y, x):
    h, w = src.shape[:2]
    dst[y:y + h, x:x + w] = src


def grid(cells, col_heads, row_heads, head_h, label_w):
    """cells[r][c] (equal-sized arrays) under a heading strip, with a label column; returns the sheet."""
    ch, cw = cells[0][0].shape[:2]
    rows, cols = len(cells), len(cells[0])
    h = head_h + rows * (ch + SEP)
    w = label_w + cols * (cw + SEP)
    out = canvas(h, w)
    paste(out, col_heads, 0, 0)
    paste(out, row_heads, head_h, 0)
    for r in range(rows):
        for c in range(cols):
            paste(out, cells[r][c], head_h + r * (ch + SEP), label_w + c * (cw + SEP))
    return out


def nn_up(a, k):
    return np.repeat(np.repeat(a, k, axis=0), k, axis=1)


def fit_cell(a, h, w):
    """a centred on a background cell of h x w (cropped if larger)."""
    out = canvas(h, w)
    ah, aw = a.shape[:2]
    y0, x0 = max(0, (h - ah) // 2), max(0, (w - aw) // 2)
    sy, sx = max(0, (ah - h) // 2), max(0, (aw - w) // 2)
    hh, ww = min(h, ah), min(w, aw)
    out[y0:y0 + hh, x0:x0 + ww] = a[sy:sy + hh, sx:sx + ww]
    return out


# ----------------------------------------------------------------------------------------------- camera
class Shots:
    def __init__(self, out, res):
        self.out, self.res = out, res
        self.scene = bpy.context.scene
        self.cam = self.scene.camera
        self.n = 0

    def px(self, v):
        return max(1, int(round(v * self.res / 100.0)))

    def ortho(self, path, cx, cz, w_m, h_m, h_px, rot=(90.0, 0.0, 0.0)):
        """An orthographic render looking along +Y (rot: Euler degrees), w_m x h_m metres centred on (cx, cz)."""
        sc, cam = self.scene, self.cam
        cam.data.type = "ORTHO"
        cam.data.sensor_fit = "VERTICAL"
        cam.data.ortho_scale = h_m
        cam.rotation_euler = tuple(math.radians(a) for a in rot)
        cam.location = Vector((cx, -10.0, cz))
        sc.render.resolution_x = max(1, int(round(h_px * w_m / h_m)))
        sc.render.resolution_y = h_px
        sc.render.resolution_percentage = 100
        sc.render.use_border = False
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        self.n += 1
        return load_png(path)

    def text(self, path, items, w_px, h_px):
        """A strip of text on the background: items [(text, x_px, y_px, size_px, align)], top-left origin."""
        sc, cam = self.scene, self.cam
        objs = []
        mat = bpy.data.materials.get("label") or bpy.data.materials.new("label")
        mat.diffuse_color = (0.02, 0.02, 0.02, 1)
        for text, x, y, size, align in items:
            cu = bpy.data.curves.new("lbl", "FONT")
            cu.body, cu.size, cu.align_x, cu.align_y = text, size / 1000.0, align, "CENTER"
            cu.materials.append(mat)
            o = bpy.data.objects.new("lbl", cu)
            sc.collection.objects.link(o)
            o.parent = cam
            o.location = ((x - w_px / 2) / 1000.0, (h_px / 2 - y) / 1000.0, -5.0)
            objs.append(o)
        cam.data.type = "ORTHO"
        cam.data.sensor_fit = "VERTICAL"
        cam.data.ortho_scale = h_px / 1000.0
        cam.rotation_euler = (math.radians(90), 0, 0)
        cam.location = Vector((0.0, 400.0, 400.0))  # empty space
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w_px, h_px, 100
        sc.render.use_border = False
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        for o in objs:
            cu = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.curves.remove(cu)
        a = load_png(path)
        a[..., :3] = np.where(a[..., :3] > 0.5, BG, a[..., :3])  # the world grey becomes the sheet background
        return a

    def perspective(self, path, eye, target, fov_deg, w_px, h_px, window):
        """The game's view: a perspective camera at eye looking at target, rendered at w_px x h_px without
        anti-aliasing and cropped to the screen rectangle around window (world points)."""
        sc, cam = self.scene, self.cam
        cam.data.type = "PERSP"
        cam.data.sensor_fit = "VERTICAL"
        cam.data.angle = math.radians(fov_deg)
        cam.location = eye
        cam.rotation_euler = (target - eye).to_track_quat("-Z", "Y").to_euler()
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w_px, h_px, 100
        update()
        ps = [world_to_camera_view(sc, cam, p) for p in window]
        sc.render.use_border = True
        sc.render.use_crop_to_border = True
        sc.render.border_min_x = max(0.0, min(p.x for p in ps))
        sc.render.border_max_x = min(1.0, max(p.x for p in ps))
        sc.render.border_min_y = max(0.0, min(p.y for p in ps))
        sc.render.border_max_y = min(1.0, max(p.y for p in ps))
        aa = sc.display.render_aa
        sc.display.render_aa = "OFF"
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        sc.display.render_aa = aa
        sc.render.use_border = False
        self.n += 1
        return load_png(path)


# ----------------------------------------------------------------------------------------------- heads and faces
class Head:
    def __init__(self, i, rc, arm, parts, rep, coll):
        self.i, self.id, self.rc, self.arm, self.parts, self.coll = i, rc["id"], rc, arm, parts, coll
        self.root = arm.parent
        self.x = i * SPACING
        self.gender = rc["gender"]
        self.eyes_rest = {k: Vector(v) for k, v in rep["eye_centres"].items()}
        self.mouth_z = rep["mouth_centre_z"]
        self.skin = next(s.material for s in parts["head"].material_slots if s.material and s.material.name == self.id + "_skin")
        self.face = {}
        self.surf = None

    def place(self, yaw=0.0):
        pk.place(self.root, x=self.x, yaw=yaw)
        self.yaw = yaw

    def face_x(self):
        """The world x of the face's middle (8 cm in front of the Head bone, between the face and the hair) at the current yaw."""
        a = math.radians(getattr(self, "yaw", 0.0))
        return self.x + 0.08 * math.sin(a)

    def eyes_at(self):
        return {k: v + Vector((self.x, 0.0, 0.0)) for k, v in self.eyes_rest.items()}

    def clear_face(self):
        for o in list(self.face.values()):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(me)
        self.face = {}


def skull_out(surf, p, centre):
    """The skin's nearest point and its outward normal for a world point p."""
    loc, n, _, _ = surf.bvh.find_nearest(p)
    if n.dot(loc - centre) < 0:
        n = -n
    return loc, n


def clearance(builder, surf, centre):
    """Signed distances (m) of a part's vertices and face centres from the skin along the skin's outward normal:
    negative means under the skin (hidden there)."""
    bm = builder.bm
    pts = [v.co.copy() for v in bm.verts] + [f.calc_center_median() for f in bm.faces]
    out = []
    for p in pts:
        loc, n = skull_out(surf, p, centre)
        out.append((p - loc).dot(n))
    return out


def make_face(h, fid, fam, ename, review, skin_name):
    """Builds one family's face in one expression on head h (the character facing -Y at its place); returns the
    measurements per part."""
    h.clear_face()
    hcol = review["heads"][h.id]
    skin_rgb = review["skins"][skin_name]
    colors = {"iris": hcol["iris"], "brow": hcol["brow"], "lip": fst.lip_rgb(skin_rgb, fam["lip_tint"])}
    mouth_at = (h.x, h.mouth_z)
    builders = fk.family_face(h.surf, h.eyes_at(), mouth_at, fid, fam, fam["expressions"][ename], colors, h.skin, h.id)
    centre = Vector(zones.SKULL_CENTRE) + Vector((h.x, 0.0, 0.0))
    info = {}
    for part in FACE_PARTS:
        b = builders[part]
        if not b.bm.faces:
            raise RuntimeError(f"{fid}/{ename}: {h.id} got an empty {part}")
        d = clearance(b, h.surf, centre)
        o = b.to_object(f"{h.id}_{part}", h.parts["head"], h.arm, smooth=False)
        for c in list(o.users_collection):
            c.objects.unlink(o)
        h.coll.objects.link(o)
        h.face[part] = o
        vg = o.vertex_groups
        info[part] = {"triangles": tris(o), "materials": len(o.material_slots), "decal": b.decal,
                      "clearance_min_mm": round(min(d) * 1000, 2), "under_skin": sum(1 for x in d if x < 0), "samples": len(d),
                      "vertex_groups": [g.name for g in vg],
                      "armature": next((m.object.name for m in o.modifiers if m.type == "ARMATURE"), None)}
    set_skin(h, fid, fam, review, skin_name)
    update()
    return info


def set_skin(h, fid, fam, review, skin_name):
    rgb = review["skins"][skin_name]
    set_color(h.skin, rgb)
    lip = bpy.data.materials.get(f"{h.id}_{fid}_lip")
    if lip:
        set_color(lip, fst.lip_rgb(rgb, fam["lip_tint"]))


def variants(fam, exprs):
    """The distinct meshes a family needs per part: expressions whose values for that part are equal share one."""
    out = {}
    for part in FACE_PARTS:
        groups = {}
        for e in exprs:
            groups.setdefault(json.dumps(fam["expressions"][e].get(part, {}), sort_keys=True), []).append(e)
        out[part] = list(groups.values())
    return out


def solo(heads, keep):
    for h in heads:
        h.coll.hide_render = h not in keep


# ----------------------------------------------------------------------------------------------- sheets
def row_cells(shots, heads, path, ppm):
    """One render of every head side by side (front camera), cut into one square cell per head, each centred on its
    face (a turned head's face moves sideways)."""
    cell_px = shots.px(CELL_M * ppm)
    xs = [h.face_x() for h in heads]
    x0, x1 = min(xs) - SPACING / 2, max(xs) + SPACING / 2
    img = shots.ortho(path, (x0 + x1) / 2, CELL_Z, x1 - x0, CELL_M, cell_px)
    scale = img.shape[1] / (x1 - x0)
    cells = []
    for x in xs:
        left = int(round((x - x0) * scale)) - cell_px // 2
        cells.append(fit_cell(img[:, max(0, left):max(0, left) + cell_px], cell_px, cell_px))
    return cells


def heading(shots, path, labels, cell_w, label_w, h_px, size):
    items = [(t, label_w + i * (cell_w + SEP) + cell_w / 2, h_px / 2, size, "CENTER") for i, t in enumerate(labels)]
    return shots.text(path, items, label_w + len(labels) * (cell_w + SEP), h_px)


def side_labels(shots, path, labels, cell_h, w_px, size):
    items = [(t, 10, i * (cell_h + SEP) + cell_h / 2, size, "LEFT") for i, t in enumerate(labels)]
    return shots.text(path, items, w_px, len(labels) * (cell_h + SEP))


def main():
    args = parse()
    for name in ("EYE_KINDS", "EYE_SHAPES", "CLOSED_STYLES", "HAPPY_STYLES", "LIP_STYLES", "FAMILY_COLORS"):
        assert getattr(fk, name) == getattr(fst, name), f"faces_styles.{name} differs from facekit.{name}"
    styles = fst.load_styles(args.styles)
    review = fst.load_review(args.review, styles)
    fams = [f for f in args.families.split(",") if f] or list(styles["families"])
    unknown = [f for f in fams if f not in styles["families"]]
    if unknown:
        raise RuntimeError(f"unknown families {unknown}; known: {', '.join(styles['families'])}")
    exprs = [e for e in args.expressions.split(",") if e] or list(styles["expressions"])
    unknown = [e for e in exprs if e not in styles["expressions"]]
    if unknown:
        raise RuntimeError(f"unknown expressions {unknown}; known: {', '.join(styles['expressions'])}")
    sheets = [] if args.sheets == "none" else [s for s in args.sheets.split(",") if s]
    unknown = [s for s in sheets if s not in fst.SHEETS]
    if unknown:
        raise RuntimeError(f"unknown sheets {unknown}; known: {', '.join(fst.SHEETS)} or none")
    out = os.path.abspath(args.out)
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)

    recipe_path = os.path.join(os.path.dirname(os.path.abspath(args.review)), review["heads_recipe"])
    R = recipes.load(recipe_path, args.raw)
    assemble.check_styles(R)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rd.setup_render()
    shots = Shots(out, args.res)
    packs = pk.Packs({g: recipes.pack_dir(R, args.raw, g) for g in recipes.GENDERS})

    heads = []
    for i, rc in enumerate(R["characters"]):
        if rc["id"] not in review["heads"]:
            raise RuntimeError(f"head {rc['id']} of {review['heads_recipe']} has no colours in review.json")
        coll = bpy.data.collections.new(rc["id"])
        bpy.context.scene.collection.children.link(coll)
        arm, parts, rep = assemble.build_character(packs, R, rc, coll)
        for role in FACE_PARTS:  # the final test's face parts go; each family brings its own
            o = parts.pop(role)
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(me)
        h = Head(i, rc, arm, parts, rep, coll)
        h.place()
        poses.apply(arm, rc["pose"])
        h.surf = fk.Surface(parts["head"])
        heads.append(h)
        print("HEAD", h.id, "eyes", rep["eye_centres"], "mouth z", h.mouth_z)
    update()

    report = {"styles": os.path.basename(args.styles), "heads": [h.id for h in heads], "res": args.res,
              "families": {}, "distance": {}, "strip": {}}
    skins = list(review["skins"])
    ppm = PPM
    cell_px = shots.px(CELL_M * ppm)
    label_w = shots.px(250)
    head_h = shots.px(70)
    fsize = shots.px(34)

    for fid in fams:
        fam = styles["families"][fid]
        frep = {"name": fam["name"], "summary": fam["summary"], "variants": variants(fam, exprs), "expressions": {}}
        cells = {"front": [], "threequarter": []}
        for ename in exprs:
            erep = {}
            row = {"front": [], "threequarter": []}
            for h in heads:
                h.place()
                erep[h.id] = make_face(h, fid, fam, ename, review, skins[0])
            for skin in skins:
                for h in heads:
                    set_skin(h, fid, fam, review, skin)
                if "close" in sheets:
                    row["front"] += row_cells(shots, heads, os.path.join(work, f"{fid}_{ename}_{skin}_front.png"), ppm)
                    for h in heads:
                        h.place(yaw=YAW_34)
                    row["threequarter"] += row_cells(shots, heads, os.path.join(work, f"{fid}_{ename}_{skin}_34.png"), ppm)
                    for h in heads:
                        h.place()
            frep["expressions"][ename] = erep
            for view in cells:
                cells[view].append(row[view])
            print("FACE", fid, ename, {hid: {p: v["triangles"] for p, v in inf.items()} for hid, inf in erep.items()})
        if "close" in sheets:
            col_labels = [f"{review['heads'][h.id]['label']}, {skin}" for skin in skins for h in heads]
            for view, label in (("front", "front"), ("threequarter", "three-quarter")):
                top = heading(shots, os.path.join(work, f"{fid}_{view}_head.png"),
                              col_labels, cell_px, label_w, head_h, shots.px(24))
                side = side_labels(shots, os.path.join(work, f"{fid}_{view}_side.png"), [show(e) for e in exprs], cell_px, label_w, fsize)
                sheet = grid(cells[view], top, side, head_h, label_w)
                title = shots.text(os.path.join(work, f"{fid}_{view}_title.png"),
                                   [(f"{fam_title(fid, fam)}  ({label})", 12, shots.px(30), shots.px(34), "LEFT")],
                                   sheet.shape[1], shots.px(60))
                full = np.concatenate([title, sheet], axis=0)
                save_image(full, os.path.join(out, f"{fid}_{view}.jpg"), "JPEG")
            hero(shots, heads, fid, fam, review, out, work)
        report["families"][fid] = frep

    if "distance" in sheets:
        report["distance"] = distance_sheets(shots, heads, styles, review, fams, out, work)
    if "overview" in sheets:
        overview(shots, heads, styles, review, fams, out, work, ppm)
    if "beards" in sheets and review.get("facial_hair"):
        report["facial_hair"] = beards(shots, heads, styles, review, packs, out, work)
    if "strip" in sheets:
        report["strip"] = strips(shots, heads, styles, review, out, work)

    report["renders"] = shots.n
    with open(os.path.join(out, "faces_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("REPORT", os.path.join(out, "faces_report.json"), "renders", shots.n)


def hero(shots, heads, fid, fam, review, out, work):
    """The family's neutral face large: each hero head front and three-quarter (the look to judge)."""
    by_id = {h.id: h for h in heads}
    cells, labels = [], []
    win = 0.30
    px = shots.px(760)
    for hid, skin in review["distance_sheet"]["heads"]:
        h = by_id[hid]
        solo(heads, [h])
        make_face(h, fid, fam, "neutral", review, skin)
        for yaw, view in ((0.0, "front"), (YAW_34, "three-quarter")):
            h.place(yaw=yaw)
            cells.append(shots.ortho(os.path.join(work, f"{fid}_hero_{hid}_{yaw:g}.png"), h.face_x(), CELL_Z, win, win, px))
            labels.append(f"{review['heads'][hid]['label']}, {skin}, {view}")
        h.place()
    solo(heads, heads)
    top = heading(shots, os.path.join(work, f"{fid}_hero_head.png"), labels, px, 0, shots.px(60), shots.px(26))
    sheet = grid([cells], top, canvas(px + SEP, 0), shots.px(60), 0)
    title = shots.text(os.path.join(work, f"{fid}_hero_title.png"),
                       [(f"{fam_title(fid, fam)}: {fam['summary']}", 12, shots.px(30), shots.px(24), "LEFT")],
                       sheet.shape[1], shots.px(60))
    save_image(np.concatenate([title, sheet], axis=0), os.path.join(out, f"{fid}_hero.jpg"), "JPEG")


def face_pixels(a, bare, threshold=0.1):
    """How many screen pixels show the face: those whose display colour differs from the bare head's by more than
    threshold (0..1, largest channel)."""
    if a.shape != bare.shape:
        return None
    return int((np.abs(a[..., :3] - bare[..., :3]).max(axis=2) > threshold).sum())


def distance_sheets(shots, heads, styles, review, fams, out, work):
    cam = review["game_camera"]
    ds = review["distance_sheet"]
    dists = review["distances_m"]
    by_id = {h.id: h for h in heads}
    w_px, h_px = shots.px(cam["width"]), shots.px(cam["height"])
    target = shots.px(380)
    info = {"screen_px": [w_px, h_px], "fov_deg": cam["fov_deg"], "eye_height_m": cam["eye_height_m"], "per_distance": {}}
    for d in dists:
        ppm_d = fst.pixels_per_metre({**cam, "height": h_px}, d)
        info["per_distance"][str(d)] = {"pixels_per_m": round(ppm_d, 1), "head_px": round(0.25 * ppm_d, 1),
                                        "eye_px_per_cm": round(0.01 * ppm_d, 2)}
    def view(h, d, path):
        face_c = Vector((h.x, -0.144, CELL_Z))
        window = [face_c + Vector((dx, 0.0, dz)) for dx in (-CELL_M / 2, CELL_M / 2) for dz in (-CELL_M / 2, CELL_M / 2)]
        eye = Vector((h.x, -0.144 - d, cam["eye_height_m"]))
        return shots.perspective(path, eye, Vector((h.x, -0.144, 1.66)), cam["fov_deg"], w_px, h_px, window)

    # the bare heads (no face parts) at each distance: a face's screen pixels are where it differs from them
    bare = {}
    for hid, skin in ds["heads"]:
        h = by_id[hid]
        solo(heads, [h])
        h.clear_face()
        set_color(h.skin, review["skins"][skin])
        for d in dists:
            bare[(hid, d)] = view(h, d, os.path.join(work, f"bare_{hid}_{d}m.png"))
    solo(heads, heads)
    info["face_pixels"] = {}
    for fid in fams:
        fam = styles["families"][fid]
        crops = {}
        fp = info["face_pixels"][fid] = {}
        for hid, skin in ds["heads"]:
            h = by_id[hid]
            solo(heads, [h])
            for ename in ds["expressions"]:
                make_face(h, fid, fam, ename, review, skin)
                for d in dists:
                    a = view(h, d, os.path.join(work, f"{fid}_{hid}_{ename}_{d}m.png"))
                    crops[(hid, ename, d)] = a
                    fp[f"{hid}_{ename}_{d}m"] = face_pixels(a, bare[(hid, d)])
        solo(heads, heads)
        # how many pixels change when the face blinks or talks: whether the game can show it at that distance
        for hid, _ in ds["heads"]:
            for d in dists:
                for label, ename in (("blink", "closed"), ("talk", "talk_a")):
                    if ename in ds["expressions"] and "neutral" in ds["expressions"]:
                        fp[f"{hid}_{label}_change_{d}m"] = face_pixels(crops[(hid, ename, d)], crops[(hid, "neutral", d)])
        cells, col_labels = [], []
        for ename in ds["expressions"]:
            row = []
            for hid, skin in ds["heads"]:
                for d in dists:
                    a = crops[(hid, ename, d)]
                    k = max(1, int(round(target / a.shape[0])))
                    row.append(fit_cell(nn_up(a, k), target, target))
            cells.append(row)
        for hid, skin in ds["heads"]:
            for d in dists:
                a = crops[(hid, ds["expressions"][0], d)]
                col_labels.append(f"{review['heads'][hid]['label']}, {skin}: {d} m ({a.shape[0]} px tall window)")
        label_w, head_h = shots.px(200), shots.px(70)
        top = heading(shots, os.path.join(work, f"{fid}_dist_head.png"), col_labels, target, label_w, head_h, shots.px(15))
        side = side_labels(shots, os.path.join(work, f"{fid}_dist_side.png"), [show(e) for e in ds["expressions"]], target,
                           label_w, shots.px(24))
        sheet = grid(cells, top, side, head_h, label_w)
        title = shots.text(os.path.join(work, f"{fid}_dist_title.png"),
                           [(f"{fam_title(fid, fam)}: as a player sees it at {', '.join(str(d) for d in dists)} m "
                             f"(FOV {cam['fov_deg']:g}, {w_px}x{h_px}, no anti-aliasing; each crop "
                             f"{CELL_M:g} m square, enlarged with nearest neighbour)", 12, shots.px(30), shots.px(22), "LEFT")],
                           sheet.shape[1], shots.px(60))
        save_image(np.concatenate([title, sheet], axis=0), os.path.join(out, f"{fid}_distance.png"))
        info.setdefault("crop_px", {})[fid] = {f"{hid}_{d}m": list(crops[(hid, ds['expressions'][0], d)].shape[:2])
                                              for hid, _ in ds["heads"] for d in dists}
    return info


def overview(shots, heads, styles, review, fams, out, work, ppm):
    cell_px = shots.px(CELL_M * ppm)
    skin_of = review["overview_skins"]
    cols = []
    for fid in fams:
        fam = styles["families"][fid]
        for h in heads:
            make_face(h, fid, fam, "neutral", review, skin_of.get(h.id, list(review["skins"])[0]))
        cols.append(row_cells(shots, heads, os.path.join(work, f"overview_{fid}.png"), ppm))
    cells = [[cols[c][r] for c in range(len(fams))] for r in range(len(heads))]
    label_w, head_h = shots.px(250), shots.px(70)
    top = heading(shots, os.path.join(work, "overview_head.png"),
                  [fam_title(fid, styles["families"][fid]) for fid in fams], cell_px, label_w, head_h, shots.px(24))
    side = side_labels(shots, os.path.join(work, "overview_side.png"),
                       [f"{review['heads'][h.id]['label']}, {skin_of.get(h.id)}" for h in heads], cell_px, label_w, shots.px(20))
    save_image(grid(cells, top, side, head_h, label_w), os.path.join(out, "overview.jpg"), "JPEG")


HAIR_KEEP = {
    "all": lambda c: True,
    "chin": zones.CUT_ZONES["chin_tuft"],  # Punk's goatee in "Red"
    "lower_face": lambda c: c.z < 1.665 and c.y < -0.03,  # a beard below the cheekbones, in front of the ears
}


def beards(shots, heads, styles, review, packs, out, work):
    """The men's pack facial hair on a man's and a woman's review head (input for the engineer, not a decision)."""
    fh = review["facial_hair"]
    fid = fh["family"]
    fam = styles["families"][fid]
    by_id = {h.id: h for h in heads}
    px = shots.px(560)
    win = 0.26
    rows, rep = [], {}
    for hid, skin in fh["heads"]:
        h = by_id[hid]
        solo(heads, [h])
        make_face(h, fid, fam, "neutral", review, skin)
        skin_rgb = review["skins"][skin]
        made = []
        for i, spec in enumerate(fh["parts"]):
            keep = HAIR_KEEP[spec["zone"]]
            mats = set(spec["materials"])
            # the part is a region of a men's pack head, rebound to this head's rig (Head and Neck bones are shared)
            obj, info = assemble.take_part(packs, h.id, f"facial_hair_{i}", "M", spec, h.arm,
                                           keep=lambda m, c, mats=mats, keep=keep: m in mats and keep(c))
            hd.inflate(obj, h.arm, 0.004)
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            h.coll.objects.link(obj)
            rgb = [x * 0.55 for x in skin_rgb] if spec.get("stubble") else review["heads"][hid]["brow"]
            m = fk.tagged_material(h.id, f"facial_hair_{i}", rgb)
            for slot in obj.material_slots:
                slot.material = m
            made.append(obj)
            rep[f"{hid}_{i}"] = {"label": spec["label"], "triangles": tris(obj), "faces_kept": info["faces_kept"]}
        update()
        cells = []
        for k in range(-1, len(made)):
            for i, o in enumerate(made):
                o.hide_render = i != k
            cells.append(shots.ortho(os.path.join(work, f"beard_{hid}_{k + 1}.png"), h.x, 1.66, win, win, px))
        rows.append(cells)
        for o in made:
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(me)
    solo(heads, heads)
    labels = ["none"] + [p["label"] for p in fh["parts"]]
    label_w, head_h = shots.px(230), shots.px(60)
    top = heading(shots, os.path.join(work, "beards_head.png"), labels, px, label_w, head_h, shots.px(24))
    side = side_labels(shots, os.path.join(work, "beards_side.png"),
                       [f"{review['heads'][hid]['label']}, {skin}" for hid, skin in fh["heads"]], px, label_w, shots.px(22))
    sheet = grid(rows, top, side, head_h, label_w)
    title = shots.text(os.path.join(work, "beards_title.png"),
                       [("Facial hair from the men's pack on both body types (with " + fam_title(fid, fam)
                         + "), coloured like the brows: shown for the decision, not decided", 12, shots.px(30), shots.px(26), "LEFT")],
                       sheet.shape[1], shots.px(60))
    save_image(np.concatenate([title, sheet], axis=0), os.path.join(out, "facial_hair.jpg"), "JPEG")
    return rep


def render_clip(shots, h, act, path, loops):
    """The action played loops times as an H.264 MP4 (Blender's FFmpeg), the same fixed three-quarter window as the
    strip: the face has to stay on the head in motion, not only in frozen frames."""
    sc, cam = shots.scene, shots.cam
    pk.reset_pose(h.arm)
    ad = h.arm.animation_data or h.arm.animation_data_create()
    track = ad.nla_tracks.new()
    f0, f1 = (int(round(x)) for x in act.frame_range)
    strip = track.strips.new("clip", f0, act)
    strip.repeat = loops
    cam.data.type = "ORTHO"
    cam.data.sensor_fit = "VERTICAL"
    cam.data.ortho_scale = 0.64
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.location = Vector((h.face_x(), -10.0, 1.53))
    sc.render.resolution_x, sc.render.resolution_y = shots.px(480) // 2 * 2, shots.px(640) // 2 * 2
    sc.render.resolution_percentage = 100
    sc.render.use_border = False
    sc.frame_start, sc.frame_end = f0, f0 + loops * (f1 - f0) - 1
    sc.render.fps = 24
    st = sc.render.image_settings
    if hasattr(st, "media_type"):  # Blender 5: video output is a media type of its own
        st.media_type = "VIDEO"
    st.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.filepath = path
    bpy.ops.render.render(animation=True)
    if hasattr(st, "media_type"):
        st.media_type = "IMAGE"
    st.file_format = "PNG"
    ad.nla_tracks.remove(track)
    pk.reset_pose(h.arm)
    shots.n += sc.frame_end - sc.frame_start + 1
    print("CLIP", path, sc.frame_end - sc.frame_start + 1, "frames")


def strips(shots, heads, styles, review, out, work):
    st = review["strip"]
    by_id = {h.id: h for h in heads}
    rep = {}
    for hid, skin, fid in st["rows"]:
        h = by_id[hid]
        fam = styles["families"][fid]
        solo(heads, [h])
        make_face(h, fid, fam, "neutral", review, skin)
        h.place(yaw=YAW_34)
        act = pk.own_action(h.arm, st["action"])
        f0, f1 = (int(round(x)) for x in act.frame_range)
        frames = [int(round(f0 + (f1 - f0) * k / st["frames"])) for k in range(st["frames"])]
        cells, worst = [], 0.0
        head_pb = h.arm.pose.bones["Head"]
        ref = None
        for f in frames:
            poses.action_pose(h.arm, st["action"], f)
            # the face parts in the Head bone's space must not move: they are rigid on it
            dg = bpy.context.evaluated_depsgraph_get()
            hm = (h.arm.matrix_world @ head_pb.matrix).inverted()
            pts = []
            for part in FACE_PARTS:
                ev = h.face[part].evaluated_get(dg)
                me = ev.to_mesh()
                pts += [hm @ (ev.matrix_world @ v.co) for v in me.vertices]
                ev.to_mesh_clear()
            if ref is None:
                ref = pts
            else:
                worst = max(worst, max((a - b).length for a, b in zip(pts, ref)))
            hb = h.arm.matrix_world @ head_pb.head
            path = os.path.join(work, f"strip_{hid}_{fid}_{f:03d}.png")
            # a fixed window over the head and shoulders, so the head's motion shows against the frame
            img = shots.ortho(path, h.face_x(), 1.53, 0.48, 0.64, shots.px(600))
            cells.append(fit_cell(img, img.shape[0], img.shape[1]))
            print("STRIP", hid, fid, "frame", f, "head", [round(c, 3) for c in hb])
        clip = None
        if st.get("clip", True):
            clip = os.path.join(out, f"clip_{hid}_{fid}.mp4")
            render_clip(shots, h, act, clip, st.get("loops", 3))
        h.place()
        poses.apply(h.arm, h.rc["pose"])
        solo(heads, heads)
        label_w, head_h = shots.px(10), shots.px(60)
        top = heading(shots, os.path.join(work, f"strip_{hid}_{fid}_head.png"), [f"{st['action']} f{f}" for f in frames],
                      cells[0].shape[1], label_w, head_h, shots.px(22))
        side = canvas(cells[0].shape[0] + SEP, label_w)
        sheet = grid([cells], top, side, head_h, label_w)
        title = shots.text(os.path.join(work, f"strip_{hid}_{fid}_title.png"),
                           [(f"{fam_title(fid, fam)} on {review['heads'][hid]['label']} ({skin}): pack action {st['action']}, "
                             f"{len(frames)} frames, three-quarter view, fixed camera", 12, shots.px(30), shots.px(24), "LEFT")],
                           sheet.shape[1], shots.px(60))
        save_image(np.concatenate([title, sheet], axis=0), os.path.join(out, f"strip_{hid}_{fid}.jpg"), "JPEG")
        rep[f"{hid}_{fid}"] = {"action": st["action"], "frames": frames, "face_in_head_space_max_move_mm": round(worst * 1000, 4),
                               "clip": os.path.basename(clip) if clip else None}
    return rep


main()
