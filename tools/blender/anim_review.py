"""The animation review (tools/run.py anim-review; docs/animations.md): plays the Ultimate Modular pack's clips and the
Universal Animation Library's clips, retargeted, on an unmodified pack character, measures each clip and renders frame
strips (front and side), looping MP4 clips and side-by-side comparisons. Background Blender only.

Usage:
  blender -b --factory-startup --python-exit-code 1 --python anim_review.py -- clips --body men --character <glb>
      --lib ual=<glb> [--lib ual2=<glb>] --out <dir> [--clips pack:Walk,ual:Walk_Loop|all] [--sources ual2]
      [--no-video] [--no-strips] [--tag <chunk>]
  ... anim_review.py -- pairs --body men --character <glb> --lib ual=<glb> ... --out <dir> --config <toml>
      [--only Walk,Run] [--sources ual2]
  ... anim_review.py -- sheets --out <dir> --names <file>   (review sheets: men and women strips of each clip)
  ... anim_review.py -- feet --body men --character <glb> --lib ual=<glb> ... --out <dir> [--only <row>]
      (close-ups of the feet: rigid shoes against the toe bones, art #25)
  ... anim_review.py -- rates --body men --character <glb> --lib ual=<glb> --lib-rm ual=<glb> ... --out <dir>
      [--sources ual2]   (the game's speeds)
Clip keys ("pack:Walk", "ual2:Walk_Carry_Loop", layered "base|upper", blends) are defined in anim_keys.py; "--ual" and
"--ual-rm" are short for "--lib ual=" and "--lib-rm ual=".
"""

import argparse
import json
import math
import os
import sys
import time
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import anim_keys  # noqa: E402
import anim_math as am  # noqa: E402
import anim_render as ar  # noqa: E402
import retarget_core as rc  # noqa: E402
import retarget_map  # noqa: E402
from anim_metrics import Measure, world_points  # noqa: E402

FPS = rc.FPS
STRIP_FRAMES = 12
CELL = (160, 240)
BASE_HEIGHT = 2.3  # metres shown in a strip cell, unless the clip needs more
FLOOR_PAD = 0.22  # metres below the floor for the time labels
HOLD = 0.5  # seconds a clip that does not loop holds its last frame in a video
LABELS = {"pack": "pack", "ual": "UAL"}  # short source names in pictures; main() adds the settings' libraries


def load_config(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


class Clip:
    """One clip on one character: its source ("pack", "ual", "ual2", ... or "layer"), name, action, sampler and whether
    it loops."""

    def __init__(self, source, name, action, loop, sampler=None, key=None):
        self.source, self.name, self.action, self.loop = source, name, action, loop
        self.sampler = sampler or rc.Sampler(action)
        self._key = key

    @property
    def key(self):
        return self._key or f"{self.source}:{self.name}"

    @property
    def label(self):
        """The clip's name with its source, as pictures show it ("UAL2 Walk_Carry_Loop")."""
        return self.name if self.source == "layer" else f"{LABELS.get(self.source, self.source)} {self.name}"

    @property
    def seconds(self):
        return self.sampler.seconds

    def frame_at(self, t):
        """The action frame at t seconds from the start (clamped to the clip)."""
        return self.sampler.start + min(max(t, 0.0), self.seconds) * FPS

    def cycle_frame(self, t):
        """The frame shown at t seconds of a looping playback: loops wrap, others hold their end for HOLD s."""
        if self.loop:
            return self.sampler.start + (t % self.seconds) * FPS if self.seconds > 0 else self.sampler.start
        return self.frame_at(t % (self.seconds + HOLD))

    def pose(self, arm, frame):
        rc.apply_basis(arm, self.sampler.basis(frame))


class Layered:
    """The sampler of a layered clip "base|upper": the base clip's frames with the upper clip's local transforms on the
    upper-body bones, the upper clip time-scaled to a whole number of its own loops per base loop. Duck-types
    rc.Sampler (start, end, frames, seconds, basis)."""

    def __init__(self, base, upper, bones):
        self.base, self.upper, self.bones = base.sampler, upper.sampler, bones
        self.start, self.end = self.base.start, self.base.end
        self.cycles = max(1, round(self.base.seconds / self.upper.seconds)) if self.upper.seconds > 0 else 1

    @property
    def frames(self):
        return self.base.frames

    @property
    def seconds(self):
        return self.base.seconds

    def basis(self, frame):
        out = dict(self.base.basis(frame))
        phase = ((frame - self.start) / self.frames * self.cycles) % 1.0 if self.frames > 0 else 0.0
        return overlay(out, self.upper.basis(self.upper.start + phase * self.upper.frames), self.bones)


def overlay(base, upper, bones):
    """base's basis matrices with upper's on `bones` (a bone the upper clip does not key goes to its rest)."""
    for b in bones:
        base[b] = upper.get(b, Matrix.Identity(4))
    return base


def upper_bones(arm, cfg):
    """The settings' [layer] bone and every bone below it: the bones an upper-body layer drives."""
    top = arm.data.bones[cfg.get("layer", {}).get("upper", "Torso")]
    return [top.name] + [b.name for b in top.children_recursive]


def setup_characters(a, count=1):
    """count copies of the body type's donor character, each given the assembler's toe bones (art #25) unless the
    settings say `toe_bones = false`: the pack's clips play on them as before (they key no toe)."""
    rc.new_scene()
    ar.setup(bpy.context.scene)
    toes = load_config(a.config).get("toe_bones", True)
    chars = []
    for _ in range(count):
        char = rc.load_glb(a.character)
        if toes:
            rc.add_toes(char)
        chars.append(char)
    return chars


def library_map(a, lib, variant="map"):
    """The bone map of a library: its settings' `map` (or `rigid_map` for the rigid-shoe variant), a file in
    tools/blender/retarget_maps/; UAL1 and UAL2 default to ual_um.toml and ual_um_rigid.toml."""
    entry = load_config(a.config).get("libraries", {}).get(lib, {})
    name = entry.get(variant, "ual_um_rigid.toml" if variant == "rigid_map" else None)
    return retarget_map.load(retarget_map.MAPS / name) if name else retarget_map.load()


def retarget(a, char, lib, names, variant="map"):
    """Bakes the named clips of a library ("ual", "ual2", ...) onto char's armature with the library's bone map (or
    its rigid-shoe map, variant "rigid_map"); returns {name: action}."""
    if not names:
        return {}
    bmap = library_map(a, lib, variant)
    before = set(bpy.data.objects)
    src = rc.load_glb(a.libs[lib])
    rt = rc.Retargeter(rc.Rig(src["arm"]), rc.Rig(char["arm"]), bmap)
    rt.set_soles(char["meshes"].values())
    char["ual_ratio"] = rt.ratio  # the same for every library on UAL1's rig
    out = {}
    tag = LABELS.get(lib, lib) + (" rigid" if variant == "rigid_map" else "")
    for n in names:
        act, _ = rt.clip(src["actions"][n], f"{tag}|{n}", char["arm"])
        out[n] = act
    for o in set(bpy.data.objects) - before:
        bpy.data.objects.remove(o, do_unlink=True)
    rc.reset_pose(char["arm"])
    bpy.context.view_layer.update()
    return out


def clips_for(a, cfg, char, keys):
    """A Clip per key (plain or layered "base|upper"), the library clips retargeted onto char."""
    loops = cfg["loops"]
    plain = list(dict.fromkeys(k for key in keys for k in anim_keys.needs(key)))
    baked = {"pack": dict(char["actions"])}
    for lib in a.libs:
        baked[lib] = retarget(a, char, lib, sorted({anim_keys.split(k)[1] for k in plain if k.startswith(lib + ":")}))
    made = {}
    for k in plain:
        src, name = anim_keys.split(k)
        if src not in baked:
            raise SystemExit(f"no source {src!r} for {k}; known: {sorted(baked)}")
        loop = name in loops.get(src, []) or (src != "pack" and name.endswith("_Loop"))
        made[k] = Clip(src, name, baked[src][name], loop)
    out = []
    for key in keys:
        base, upper = anim_keys.layer(key)
        if upper is None:
            out.append(made[key])
            continue
        b, u = made[base], made[upper]
        out.append(Clip("layer", f"{b.label} + {u.label} upper body", b.action, b.loop,
                        Layered(b, u, upper_bones(char["arm"], cfg)), key=key))
    return out


def all_keys(a, char):
    import re
    keys = [f"pack:{n}" for n in sorted(char["actions"])]
    for lib, path in a.libs.items():
        if a.clips == "all" or f"{lib}:" in a.clips:
            # a library's clip names come from the file itself
            before = set(bpy.data.actions)
            objs = set(bpy.data.objects)
            src = rc.load_glb(path)
            keys += [f"{lib}:{n}" for n in sorted(src["actions"]) if not re.fullmatch(r".*\.\d{3}", n)]
            for o in set(bpy.data.objects) - objs:
                bpy.data.objects.remove(o, do_unlink=True)
            for act in set(bpy.data.actions) - before:
                bpy.data.actions.remove(act)
    if a.clips != "all":
        want = a.clips.split(",")
        unknown = [w for w in want if any(k not in keys for k in anim_keys.needs(w))]
        if unknown:
            raise SystemExit(f"unknown clips {unknown}; known: {keys}")
        return want
    return [k for k in keys if a.sources is None or anim_keys.split(k)[0] in a.sources]


def bbox(char, clip, times):
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for t in times:
        clip.pose(char["arm"], clip.frame_at(t))
        bpy.context.view_layer.update()
        for obj in char["meshes"].values():
            pts = world_points(obj)
            lo = Vector(np.minimum(lo, pts.min(axis=0)))
            hi = Vector(np.maximum(hi, pts.max(axis=0)))
    return lo, hi


def framing(lo, hi, aspect):
    """The cell height in metres and the horizontal centres (x for front, y for side) for a clip's extent."""
    need = max(BASE_HEIGHT, hi.z + 0.25 + FLOOR_PAD, (hi.x - lo.x) * aspect * 1.1, (hi.y - lo.y) * aspect * 1.1)
    return need, (lo.x + hi.x) / 2, (lo.y + hi.y) / 2


def header(textline, width_px, height_px=40):
    """A one-line label rendered alone, as a picture width_px wide."""
    scene = bpy.context.scene
    hidden = [o for o in scene.objects if not o.hide_render]
    for o in hidden:
        o.hide_render = True
    t = ar.text("header", 0.1, "front", "LEFT")
    t.data.body = textline
    t.location = (1000.0, 0.0, 1000.0)
    bpy.context.view_layer.update()
    w = max(t.dimensions.x, 0.01)
    scale_h = 0.1 * 1.9  # text 0.1 tall in a picture ~1.9 text heights tall
    visible_w = scale_h * width_px / height_px
    if w > visible_w * 0.98:
        t.data.size = 0.1 * visible_w * 0.98 / w
        bpy.context.view_layer.update()
        w = t.dimensions.x
    centre = Vector((1000.0 + visible_w / 2 - 0.02 * visible_w, 0.0, 1000.0 + t.data.size * 0.32))
    ar.aim("front", centre, scale_h, width_px, height_px)
    img = ar.render(os.path.join(TMP, "header.png"))
    bpy.data.objects.remove(t, do_unlink=True)
    for o in hidden:
        o.hide_render = False
    return img


def strip(char, clip, body, out_png, title):
    n = STRIP_FRAMES
    times = [clip.seconds * i / (n - 1) for i in range(n)]
    lo, hi = bbox(char, clip, times)
    height, cx, cy = framing(lo, hi, CELL[1] / CELL[0])
    zc = -FLOOR_PAD + height / 2
    labels = {v: ar.text(f"lbl_{v}", 0.15 * height / BASE_HEIGHT, v) for v in ("front", "side")}
    rows = {"front": [], "side": []}
    for t in times:
        f = clip.frame_at(t)
        clip.pose(char["arm"], f)
        for v, lbl in labels.items():
            lbl.data.body = f"{t:.2f} s"
            lbl.hide_render = True
        for v in ("front", "side"):
            lbl = labels[v]
            lbl.hide_render = False
            if v == "front":
                lbl.location = (cx, lo.y - 0.3, -FLOOR_PAD * 0.85)
                centre = Vector((cx, 0.0, zc))
            else:
                lbl.location = (lo.x - 0.3, cy, -FLOOR_PAD * 0.85)
                centre = Vector((0.0, cy, zc))
            bpy.context.view_layer.update()
            ar.aim(v, centre, height, *CELL)
            rows[v].append(ar.render(os.path.join(TMP, "cell.png")))
            lbl.hide_render = True
    for lbl in labels.values():
        bpy.data.objects.remove(lbl, do_unlink=True)
    body_img = ar.grid([rows["front"], rows["side"]])
    head = header(title, body_img.shape[1])
    ar.save_png(ar.grid([[head], [body_img]]), out_png)


def video(char, clip, out_mp4, title, size=480):
    n = int(round(clip.seconds * FPS))
    frames = n if clip.loop else n + 1 + int(HOLD * FPS)
    times = [clip.seconds * i / 7 for i in range(8)]
    lo, hi = bbox(char, clip, times)
    ext = max(hi.x - lo.x, hi.y - lo.y, hi.z + 0.1) * 1.15
    height = max(BASE_HEIGHT, ext)
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, height / 2 - 0.15))
    ar.aim("three_quarter", centre, height, size, size)
    cam = bpy.context.scene.camera
    lbl = ar.text("vlabel", 0.055 * height / BASE_HEIGHT, "front", "LEFT")
    lbl.parent = cam
    lbl.rotation_euler = (0, 0, 0)
    lbl.location = (-height / 2 * 0.95, height / 2 * 0.88, -5)

    def pose_frame(f):
        t = f / FPS
        clip.pose(char["arm"], clip.cycle_frame(t))
        lbl.data.body = f"{title}   {min(t, clip.seconds) if not clip.loop else t % clip.seconds:.2f} s"

    ar.render_video(out_mp4, size, size, frames, pose_frame)
    bpy.data.objects.remove(lbl, do_unlink=True)


def measure(char, clip, meas):
    n = int(round(clip.seconds * FPS))
    frames = []
    for i in range(n + 1):
        clip.pose(char["arm"], clip.sampler.start + i)
        bpy.context.view_layer.update()
        frames.append(meas.frame())
    return meas.clip(frames, FPS, clip.loop)


def cmd_clips(a):
    cfg = load_config(a.config)
    (char,) = setup_characters(a)
    meas = Measure(char)  # before anything moves: the hinge axes come from the rest in world space
    keys = all_keys(a, char)
    clips = clips_for(a, cfg, char, keys)
    char_name = os.path.splitext(os.path.basename(a.character))[0]
    results = {}
    for clip in clips:
        t0 = time.time()
        res = measure(char, clip, meas)
        res.update({"source": clip.source, "clip": clip.name, "body": a.body, "character": char_name})
        stem = (f"{clip.source}_{clip.name}" if clip.source != "layer"
                else "layer_" + clip.key.replace(":", "_").replace("|", "+"))
        src_label = {"pack": "Ultimate Modular pack", "layer": "layered"}.get(
            clip.source, f"{LABELS.get(clip.source, clip.source)} retargeted")
        title = f"{clip.name}  |  {src_label} on {a.body} ({char_name})  |  {clip.seconds:.2f} s"
        if not a.no_strips:
            path = os.path.join(a.out, "strips", a.body, stem + ".png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            strip(char, clip, a.body, path, title + "  |  top: front, bottom: right side")
            res["strip"] = path
        if not a.no_video:
            path = os.path.join(a.out, "clips", a.body, stem + ".mp4")
            video(char, clip, path, f"{clip.label} ({a.body})")
            res["video"] = path
        res["seconds_spent"] = round(time.time() - t0, 1)
        results[clip.key] = res
        print("CLIP", a.body, clip.key, json.dumps({k: res[k] for k in ("seconds", "foot_sliding", "seconds_spent")}))
    os.makedirs(os.path.join(a.out, "metrics"), exist_ok=True)
    with open(os.path.join(a.out, "metrics", f"{a.body}{a.tag}.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)


def cmd_pairs(a):
    cfg = load_config(a.config)
    pairs = [p for p in anim_keys.pairs(cfg) if (not a.only or p["name"] in a.only.split(","))
             and anim_keys.selected(p["clips"], a.sources)]
    if not pairs:
        print("PAIRS none selected")
        return
    width = max(len(p["clips"]) for p in pairs)
    chars = setup_characters(a, width)
    keys = sorted({k for p in pairs for k in p["clips"]})
    clips = {c.key: c for c in clips_for(a, cfg, chars[0], keys)}
    char_name = os.path.splitext(os.path.basename(a.character))[0]
    spacing = 1.45
    for p in pairs:
        row = [clips[k] for k in p["clips"]]
        k = len(row)
        for i, ch in enumerate(chars):
            rc.place(ch, x=(i - (k - 1) / 2) * spacing if i < k else 1000.0)
        # frame strip: a front and a side row per clip, at the same fractions of each clip's own length; the front
        # renders every clip at once and is cut into cells, the side renders each clip alone
        front_w = int(round(CELL[1] * spacing / BASE_HEIGHT / 2)) * 2
        # the side cells are framed on each clip's own extent, so a fall or a lunge along Y stays in the picture
        side = [framing(*bbox(chars[i], clip, [clip.seconds * j / (STRIP_FRAMES - 1) for j in range(STRIP_FRAMES)]),
                        CELL[1] / front_w) for i, clip in enumerate(row)]
        rows = [[] for _ in range(2 * k)]
        for j in range(STRIP_FRAMES):
            for i, clip in enumerate(row):
                clip.pose(chars[i]["arm"], clip.frame_at(clip.seconds * j / (STRIP_FRAMES - 1)))
            bpy.context.view_layer.update()
            ar.aim("front", Vector((0.0, 0.0, -FLOOR_PAD + BASE_HEIGHT / 2)), BASE_HEIGHT, front_w * k, CELL[1])
            img = ar.render(os.path.join(TMP, "pair.png"))
            for i in range(k):
                rows[2 * i].append(img[:, i * front_w:(i + 1) * front_w])
            for i in range(k):
                for m, ch in enumerate(chars):
                    for o in ch["meshes"].values():
                        o.hide_render = m != i
                h, _, cy = side[i]
                ar.aim("side", Vector((0.0, cy, -FLOOR_PAD + h / 2)), h, front_w, CELL[1])
                rows[2 * i + 1].append(ar.render(os.path.join(TMP, "pair.png")))
            for ch in chars:
                for o in ch["meshes"].values():
                    o.hide_render = False
        names = "  vs  ".join(c.label for c in row)
        body_img = ar.grid(rows)
        head = header(f"{names}  |  {a.body} ({char_name})  |  front and side rows in that order, at the same "
                      f"fractions of each clip", body_img.shape[1])
        out_png = os.path.join(a.out, "pairs", a.body, p["name"] + ".png")
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        ar.save_png(ar.grid([[head], [body_img]]), out_png)
        # the looping side-by-side video: every clip loops on its own clock
        seconds = max(max(c.seconds + (0 if c.loop else HOLD) for c in row), 2.0)
        frames = int(round(seconds * FPS))
        lbls = []
        for i, clip in enumerate(row):
            t = ar.text(f"pl{i}", 0.085, "three_quarter")
            t.rotation_euler = (math.radians(84), 0, 0)
            t.location = ((i - (k - 1) / 2) * spacing, -0.6, 2.0)
            t.data.body = clip.label.replace(" + ", "\n+ ")
            lbls.append(t)
        ar.VIEWS["pair"] = (84.0, 0.0, 0.0)
        height = 2.45
        w = int(round(480 * (k * spacing + 0.3) / height / 2) * 2)
        ar.aim("pair", Vector((0.0, 0.0, height / 2 - 0.12)), height, w, 480)

        def pose_frame(f, row=row):
            for i, clip in enumerate(row):
                clip.pose(chars[i]["arm"], clip.cycle_frame(f / FPS))

        out_mp4 = os.path.join(a.out, "pairs", a.body, p["name"] + ".mp4")
        ar.render_video(out_mp4, w, 480, frames, pose_frame)
        for t in lbls:
            bpy.data.objects.remove(t, do_unlink=True)
        print("PAIR", a.body, p["name"], out_mp4)


def cmd_sheets(a):
    """Review sheets for the reviewer's eyes: for each clip, the men's and the women's strips stacked, three clips a
    sheet."""
    rc.new_scene()
    with open(a.names, encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    os.makedirs(os.path.join(a.out, "sheets"), exist_ok=True)
    per = 3
    for s in range(0, len(names), per):
        rows = []
        for stem in names[s:s + per]:
            for body in ("men", "women"):
                path = os.path.join(a.out, "strips", body, stem + ".png")
                if os.path.exists(path):
                    img = ar.read_png(path)
                    rows.append([img[::2, ::2]])
        if rows:
            out = os.path.join(a.out, "sheets", f"sheet_{s // per + 1:02d}.png")
            ar.save_png(ar.grid(rows, gap=6, shade=0.2), out)
            print("SHEET", out)


# ------------------------------------------------------------------------------------------------ the feet (art #25)
FEET_FRAMES = 12
FEET_CELL = (300, 210)  # pixels
FEET_VIEW_H = 0.42  # metres shown in a close-up cell (from FEET_BELOW under the floor), which follows the right shoe
FEET_BELOW = 0.05
FEET_VIDEO_H = 0.75  # metres shown in the looping close-up, which stays put


def right_shoe_y(char):
    """The middle (front to back) of the right shoe (x < 0 on a character at the origin) as posed."""
    from um import toes

    pts = world_points(toes.shoes_of(char["meshes"]))
    right = pts[pts[:, 0] < 0.0]
    return float((right[:, 1].min() + right[:, 1].max()) / 2) if len(right) else 0.0


def feet_box(char, clip, times):
    """The y range (front to back) of the shoes over the given times of a clip."""
    from um import toes

    shoes = toes.shoes_of(char["meshes"])
    lo, hi = 1e9, -1e9
    for t in times:
        clip.pose(char["arm"], clip.frame_at(t))
        bpy.context.view_layer.update()
        pts = world_points(shoes)
        lo, hi = min(lo, float(pts[:, 1].min())), max(hi, float(pts[:, 1].max()))
    return lo, hi


def cmd_feet(a):
    """Close-ups of the feet (art #25): each clip of the settings' [[feet]] rows played twice on the body type's donor
    with its toe bones, once retargeted with the library's rigid-shoe map (the toes kept at rest: the shoes of art #20
    and #24) and once with its map (the source's toes drive the toe bones). Per clip: a side-view strip of FEET_FRAMES
    frames (rigid shoes on top, toe bones below), a looping side-view clip of the two side by side and both lanes'
    measures with the toe tipping and the bend (feet/<body>/<row>_<clip>.png, .mp4 and <row>.json)."""
    cfg = load_config(a.config)
    rows = [r for r in cfg.get("feet", []) if not a.only or r["name"] in a.only.split(",")]
    if not rows:
        print("FEET none selected")
        return
    chars = setup_characters(a, 2)
    meas = [Measure(ch) for ch in chars]  # before anything moves: the hinge axes come from the rest in world space
    keys = list(dict.fromkeys(k for r in rows for k in r["clips"]))
    toe = {c.key: c for c in clips_for(a, cfg, chars[0], keys)}
    rigid = {}
    for lib in a.libs:
        names = sorted({anim_keys.split(k)[1] for k in keys if k.startswith(lib + ":")})
        for n, act in retarget(a, chars[0], lib, names, "rigid_map").items():
            src = f"{lib}_rigid"
            LABELS.setdefault(src, f"{LABELS.get(lib, lib)} rigid shoes")
            rigid[f"{lib}:{n}"] = Clip(src, n, act, toe[f"{lib}:{n}"].loop)
    char_name = os.path.splitext(os.path.basename(a.character))[0]
    out_dir = os.path.join(a.out, "feet", a.body)
    os.makedirs(out_dir, exist_ok=True)
    for r in rows:
        report = {}
        for key in r["clips"]:
            lanes = [rigid[key], toe[key]]
            for ch in chars:
                rc.place(ch)
            res = [measure(ch, clip, m) for ch, m, clip in zip(chars, meas, lanes)]
            report[key] = {"rigid_shoes": res[0], "toe_bones": res[1]}
            n = FEET_FRAMES
            times = [lanes[0].seconds * i / n for i in range(n)]  # one cycle; its end is its start again
            boxes = [feet_box(ch, clip, times) for ch, clip in zip(chars, lanes)]
            span = max(hi - lo for lo, hi in boxes) + 0.12
            grid_rows = []
            for i, (ch, clip) in enumerate(zip(chars, lanes)):
                for m_i, other in enumerate(chars):
                    for o in other["meshes"].values():
                        o.hide_render = m_i != i
                cells = []
                for t in times:
                    clip.pose(ch["arm"], clip.frame_at(t))
                    bpy.context.view_layer.update()
                    centre = Vector((0.0, right_shoe_y(ch), -FEET_BELOW + FEET_VIEW_H / 2))
                    ar.aim("side", centre, FEET_VIEW_H, *FEET_CELL)
                    cells.append(ar.render(os.path.join(TMP, "feet.png")))
                grid_rows.append(cells)
            for ch in chars:
                for o in ch["meshes"].values():
                    o.hide_render = False
            t_r, t_t = res[0].get("toe", {}), res[1].get("toe", {})
            title = (f"{lanes[1].label} on {a.body} ({char_name}), the right shoe from its side, {n} frames over "
                     f"{lanes[0].seconds:.2f} s"
                     f"  |  top: rigid shoes (toe bones at rest)  |  bottom: toe bones driven by the source's toes  |  "
                     f"front of the shoe at a 20 deg heel lift, tip down: {t_r.get('front_pitch_at_20_deg_lift')} vs "
                     f"{t_t.get('front_pitch_at_20_deg_lift')} deg; heel lift with the front level: "
                     f"{t_r.get('heel_lift_front_level_max_deg')} vs {t_t.get('heel_lift_front_level_max_deg')} deg")
            body_img = ar.grid(grid_rows)
            stem = f"{r['name']}_{key.replace(':', '_')}"
            ar.save_png(ar.grid([[header(title, body_img.shape[1])], [body_img]]), os.path.join(out_dir, stem + ".png"))
            # the looping close-up: both lanes side by side along the view (front to back), each on its own clock
            spacing = span + 0.25
            for i, ch in enumerate(chars):
                rc.place(ch, y=(i - 0.5) * spacing - (boxes[i][0] + boxes[i][1]) / 2)
            lbls = []
            for i, clip in enumerate(lanes):
                t = ar.text(f"fl{i}", 0.04, "side")
                t.location = (0.6, (i - 0.5) * spacing, FEET_VIDEO_H - FEET_BELOW - 0.07)
                t.data.body = ("rigid shoes" if i == 0 else "toe bones") + f": {clip.name}"
                lbls.append(t)
            seconds = max(max(c.seconds + (0 if c.loop else HOLD) for c in lanes), 2.0)
            height_px = 360
            width_px = int(round(height_px * (2 * spacing) / FEET_VIDEO_H / 2)) * 2
            ar.aim("side", Vector((0.0, 0.0, -FEET_BELOW + FEET_VIDEO_H / 2)), FEET_VIDEO_H, width_px, height_px)

            def pose_frame(f, lanes=lanes):
                for ch, clip in zip(chars, lanes):
                    clip.pose(ch["arm"], clip.cycle_frame(f / FPS))

            ar.render_video(os.path.join(out_dir, stem + ".mp4"), width_px, height_px, int(round(seconds * FPS)),
                            pose_frame)
            for t in lbls:
                bpy.data.objects.remove(t, do_unlink=True)
            print("FEET", a.body, key, json.dumps({"rigid": t_r, "toe": t_t}))
        with open(os.path.join(out_dir, r["name"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)


# ------------------------------------------------------------------------------------------- the game's speeds
class Variant:
    """One lane of a rates row: a clip (or a cycle-synced blend of two UAL clips) played at the rate that makes its
    feet keep up with a treadmill moving at the row's speed."""

    def __init__(self, key, clips, speed, natural, rig, bones=()):
        self.key = key
        base, upper = anim_keys.layer(key)
        kind = "blend" if base.startswith("blend:") else "clip"
        self.parts = [clips[k] for k in anim_keys.blend_parts(base)] if kind == "blend" else [clips[base]]
        # an upper-body layer plays one of its loops per stride, its left heel strike on the base's
        self.upper, self.bones = (clips[upper], list(bones)) if upper else (None, [])
        speeds = [natural[c.key] for c in self.parts]
        self.weight = 0.0
        if kind == "blend":
            (a, b), (va, vb) = self.parts, speeds
            sa, sb = va * a.seconds, vb * b.seconds  # stride lengths at 1.0x
            # the weight whose blended stride over the blended cycle gives the speed: (sa + w (sb - sa)) /
            # (ta + w (tb - ta)) = speed
            w = (speed * a.seconds - sa) / ((sb - sa) - speed * (b.seconds - a.seconds))
            self.weight = min(max(w, 0.0), 1.0)
        w = self.weight
        self.cycle = sum(c.seconds * k for c, k in zip(self.parts, (1 - w, w))) if kind == "blend" else \
            self.parts[0].seconds
        stride = sum(v * c.seconds * k for c, v, k in zip(self.parts, speeds, (1 - w, w))) if kind == "blend" else \
            speeds[0] * self.parts[0].seconds
        self.natural = stride / self.cycle
        self.rate = speed / self.natural
        self.phase0 = [foot_forward_phase(c, rig) for c in self.parts]
        self.upper_phase0 = foot_forward_phase(self.upper, rig) if self.upper else 0.0
        self.cadence = 2.0 / self.cycle * self.rate  # a loop is one stride: two steps
        self.step = speed / self.cadence

    def label(self):
        if len(self.parts) == 2:
            short = [c.name.replace("_Fwd_Loop", "").replace("_Loop", "") for c in self.parts]
            name = f"blend {short[0]} {1 - self.weight:.2f} + {short[1]} {self.weight:.2f}"
        else:
            name = self.parts[0].label
        if self.upper:
            name += f"\n+ {self.upper.label} upper body"
        return f"{name}\nx{self.rate:.2f}, {self.cadence:.2f} steps/s, {self.step:.2f} m a step"

    def pose(self, arm, t):
        phase = (t * self.rate / self.cycle) % 1.0
        bases = []
        for clip, p0 in zip(self.parts, self.phase0):
            frame = clip.sampler.start + ((phase + p0) % 1.0) * clip.seconds * FPS
            bases.append(clip.sampler.basis(frame))
        if len(bases) == 1:
            out = dict(bases[0])
        else:
            a, b = bases
            out = {}
            for bone in set(a) | set(b):
                la, qa, sa = a.get(bone, Matrix.Identity(4)).decompose()
                lb, qb, sb = b.get(bone, Matrix.Identity(4)).decompose()
                if qa.dot(qb) < 0:
                    qb = -qb
                out[bone] = Matrix.LocRotScale(la.lerp(lb, self.weight), qa.slerp(qb, self.weight),
                                               sa.lerp(sb, self.weight))
        if self.upper:
            u = self.upper.sampler
            out = overlay(out, u.basis(u.start + ((phase + self.upper_phase0) % 1.0) * u.frames), self.bones)
        rc.apply_basis(arm, out)


def foot_forward_phase(clip, rig, samples=60):
    """The phase (0..1) of a loop at which the left foot is furthest forward of the body: the heel strike that two
    clips are lined up on before they are blended."""
    best, best_i = -1e9, 0
    for i in range(samples):
        pose = rc.fk(rig, clip.sampler.basis(clip.sampler.start + clip.seconds * FPS * i / samples))
        foot, body = rig.W @ pose["Foot.L"].translation, rig.W @ pose["Body"].translation
        ahead = body.y - foot.y  # the front is -Y
        if ahead > best:
            best, best_i = ahead, i
    return best_i / samples


def natural_speeds(a, char, clips, rig):
    """Each clip's speed at 1.0x (m/s): for UAL clips the root-motion file's root travel, scaled to the body (the
    speed at which its planted feet stand still on the ground); otherwise the in-place ground speed of the feet."""
    out, how = {}, {}
    for lib, path in a.libs_rm.items():
        ual = [c for c in clips.values() if c.source == lib]
        if not ual:
            continue
        before = set(bpy.data.objects)
        rm = rc.load_glb(path)
        rm_rig = rc.Rig(rm["arm"])
        for c in ual:
            s = rc.Sampler(rm["actions"][c.name])
            p0 = rm_rig.W @ rc.fk(rm_rig, s.basis(s.start))["root"].translation
            p1 = rm_rig.W @ rc.fk(rm_rig, s.basis(s.end))["root"].translation
            travel = math.hypot(p1.x - p0.x, p1.y - p0.y)
            if travel > 0.05:
                out[c.key], how[c.key] = travel / s.seconds * char["ual_ratio"], "root motion"
        for o in set(bpy.data.objects) - before:
            bpy.data.objects.remove(o, do_unlink=True)
    for c in clips.values():
        if c.key not in out:
            feet = {s: [] for s in "LR"}
            for i in range(int(round(c.seconds * FPS)) + 1):
                pose = rc.fk(rig, c.sampler.basis(c.sampler.start + i))
                for s in "LR":
                    feet[s].append(tuple(rig.W @ pose[f"Foot.{s}"].translation))
            ground = am.foot_sliding(feet, FPS)["ground_speed_cm_s"]
            out[c.key], how[c.key] = (ground or 0.0) / 100, "feet"
    return out, how


def treadmill(spacing_m=1.0, width_m=40.0, count=60):
    """Light stripes across the floor every spacing_m metres; returns them and a function that moves them to where a
    floor moving at `speed` m/s toward +Y is at time t."""
    mat = ar.material("stripe", (0.85, 0.85, 0.80, 1.0))
    stripes = []
    for j in range(count):
        me = bpy.data.meshes.new(f"stripe{j}")
        h, d = width_m / 2, 0.05
        me.from_pydata([(-h, -d, 0.0), (h, -d, 0.0), (h, d, 0.0), (-h, d, 0.0)], [], [(0, 1, 2, 3)])
        me.materials.append(mat)
        ob = bpy.data.objects.new(f"stripe{j}", me)
        bpy.context.scene.collection.objects.link(ob)
        stripes.append(ob)

    def move(speed, t):
        shift = (speed * t) % spacing_m
        for j, ob in enumerate(stripes):
            ob.location = (0.0, (j - count / 2) * spacing_m + shift, 0.002)

    return stripes, move


def cmd_rates(a):
    """Locomotion at the game's speeds: every row of [[rates]] plays its clips side by side on a treadmill moving at
    the row's speed, each at the rate that matches its feet to the treadmill; an MP4 and a frame strip per row, and
    rates.json with each lane's rate, cadence and step length."""
    cfg = load_config(a.config)
    rows = [r for r in cfg["rates"] if anim_keys.selected(r["clips"], a.sources)]
    out_dir = os.path.join(a.out, "rates", a.body)
    os.makedirs(out_dir, exist_ok=True)
    if not rows:
        write_rates(out_dir, {"body": a.body, "rows": {}}, a.sources is not None)
        return
    width = max(len(r["clips"]) for r in rows)
    chars = setup_characters(a, width)
    rig = rc.Rig(chars[0]["arm"])
    keys = {k for r in rows for lane in r["clips"] for k in anim_keys.needs(lane)}
    clips = {c.key: c for c in clips_for(a, cfg, chars[0], sorted(keys))}
    bones = upper_bones(chars[0]["arm"], cfg)
    natural, how = natural_speeds(a, chars[0], clips, rig)
    char_name = os.path.splitext(os.path.basename(a.character))[0]
    stripes, move = treadmill()
    view = (70.0, 0.0, -70.0)  # from the side and a little ahead, 20 degrees down, so the moving ground shows
    right = Vector((math.cos(math.radians(70.0)), -math.sin(math.radians(70.0)), 0.0))  # the picture's right
    ar.VIEWS["rates"] = view
    spacing, height = 2.4, 2.7  # lanes one behind the other along the picture's right
    report = {"body": a.body, "character": char_name, "natural_speed_m_s": {k: round(v, 3) for k, v in natural.items()},
              "natural_speed_from": how, "rows": {}}
    for r in rows:
        lanes = [Variant(k, clips, r["speed"], natural, rig, bones) for k in r["clips"]]
        k = len(lanes)
        spots = [right * ((i - (k - 1) / 2) * spacing) for i in range(k)]
        for i, ch in enumerate(chars):
            rc.place(ch, *((spots[i].x, spots[i].y) if i < k else (1000.0, 0.0)))
        lbls = []
        for i, lane in enumerate(lanes):
            t = ar.text(f"rl{i}", 0.085, "rates")
            t.location = (spots[i].x, spots[i].y, 2.35)
            t.data.body = lane.label()
            lbls.append(t)
        w = int(round(480 * (k * spacing + 0.6) / height / 2) * 2)
        centre = Vector((0.0, 0.0, height / 2 - 0.25))
        title = ar.text("rtitle", 0.07, "rates", "LEFT")
        title.data.body = (f"Treadmill at {r['speed']} m/s ({r['label']}), {a.body} ({char_name}): "
                           "the stripes are the ground")
        cam = bpy.context.scene.camera
        title.parent = cam
        title.rotation_euler = (0, 0, 0)

        def pose_all(t, lanes=lanes, speed=r["speed"]):
            for i, lane in enumerate(lanes):
                lane.pose(chars[i]["arm"], t)
            move(speed, t)

        ar.aim("rates", centre, height, w, 480)
        title.location = (-(w / 480) * height / 2 * 0.97, height / 2 * 0.95, -5)
        out_mp4 = os.path.join(out_dir, r["name"] + ".mp4")
        ar.render_video(out_mp4, w, 480, int(round(r.get("seconds", 4.0) * FPS)), lambda f: pose_all(f / FPS))
        # a strip: 8 moments 0.1 s apart, as rendered in the video
        cells = []
        for j in range(8):
            pose_all(j * 0.1)
            bpy.context.view_layer.update()
            ar.aim("rates", centre, height, w, 480)
            cells.append(ar.render(os.path.join(TMP, "rate.png"))[::2, ::2])
        ar.save_png(ar.grid([cells[0:2], cells[2:4], cells[4:6], cells[6:8]], gap=4),
                    os.path.join(out_dir, r["name"] + ".png"))
        for t in lbls + [title]:
            bpy.data.objects.remove(t, do_unlink=True)
        report["rows"][r["name"]] = {
            "speed_m_s": r["speed"], "label": r["label"], "video": out_mp4,
            "lanes": [{"clip": lane.key, "upper_body": lane.upper.key if lane.upper else None,
                       "blend_weight": round(lane.weight, 3), "cycle_s": round(lane.cycle, 3),
                       "natural_speed_m_s": round(lane.natural, 3), "rate": round(lane.rate, 3),
                       "cadence_steps_s": round(lane.cadence, 2), "step_m": round(lane.step, 2)} for lane in lanes],
        }
        print("RATES", a.body, r["name"], json.dumps(report["rows"][r["name"]]["lanes"]))
    for ob in stripes:
        bpy.data.objects.remove(ob, do_unlink=True)
    write_rates(out_dir, report, a.sources is not None)


def write_rates(out_dir, report, some_rows):
    """rates/<body>/rates.json; a run over some sources (some_rows) keeps the other rows of an earlier report."""
    path = os.path.join(out_dir, "rates.json")
    old = None
    if some_rows and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, ValueError):
            old = None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(anim_keys.merge_rates(old, report), f, indent=1)


def main(argv):
    ap = argparse.ArgumentParser(prog="anim_review.py")
    ap.add_argument("mode", choices=["clips", "pairs", "sheets", "rates", "feet"])
    ap.add_argument("--body", choices=["men", "women"])
    ap.add_argument("--character")
    ap.add_argument("--ual", help="short for --lib ual=<glb>")
    ap.add_argument("--ual-rm", help="short for --lib-rm ual=<glb>")
    ap.add_argument("--lib", action="append", default=[], help="<key>=<glb>: a library's in-place file")
    ap.add_argument("--lib-rm", action="append", default=[], help="<key>=<glb>: a library's root-motion file")
    ap.add_argument("--sources", default="all", help="only these sources' clips, pairs and rates rows")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "anim_review.toml"))
    ap.add_argument("--clips", default="all")
    ap.add_argument("--only", default="")
    ap.add_argument("--names")
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--no-strips", action="store_true")
    a = ap.parse_args(argv)
    a.out = os.path.abspath(a.out)
    a.libs = dict(x.split("=", 1) for x in a.lib)
    a.libs_rm = dict(x.split("=", 1) for x in a.lib_rm)
    if a.ual:
        a.libs = {"ual": a.ual, **a.libs}
    if a.ual_rm:
        a.libs_rm = {"ual": a.ual_rm, **a.libs_rm}
    cfg = load_config(a.config)
    LABELS.update({k: v.get("label", k.upper()) for k, v in cfg.get("libraries", {}).items()})
    a.sources = anim_keys.parse_sources(a.sources, {"pack", *a.libs})
    global TMP
    TMP = os.path.join(a.out, "tmp", f"{a.body or 'sheets'}{a.tag}")
    os.makedirs(TMP, exist_ok=True)
    {"clips": cmd_clips, "pairs": cmd_pairs, "sheets": cmd_sheets, "rates": cmd_rates,
     "feet": cmd_feet}[a.mode](a)


TMP = ""
main(sys.argv[sys.argv.index("--") + 1:])
