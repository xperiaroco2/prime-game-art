"""The animation review (tools/run.py anim-review; docs/animations.md): plays the Ultimate Modular pack's clips and the
Universal Animation Library's clips, retargeted, on an unmodified pack character, measures each clip and renders frame
strips (front and side), looping MP4 clips and side-by-side comparisons. Background Blender only.

Usage:
  blender -b --factory-startup --python-exit-code 1 --python anim_review.py -- clips --body men --character <glb>
      --ual <glb> --out <dir> [--clips pack:Walk,ual:Walk_Loop|all] [--no-video] [--no-strips] [--tag <chunk>]
  ... anim_review.py -- pairs --body men --character <glb> --ual <glb> --out <dir> --config <toml> [--only Walk,Run]
  ... anim_review.py -- sheets --out <dir> --names <file>   (review sheets: men and women strips of each clip)
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
from mathutils import Vector  # noqa: E402

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


def load_config(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


class Clip:
    """One clip on one character: its source ("pack" or "ual"), name, action, sampler and whether it loops."""

    def __init__(self, source, name, action, loop):
        self.source, self.name, self.action, self.loop = source, name, action, loop
        self.sampler = rc.Sampler(action)

    @property
    def key(self):
        return f"{self.source}:{self.name}"

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


def setup_characters(a, count=1):
    rc.new_scene()
    ar.setup(bpy.context.scene)
    chars = [rc.load_glb(a.character) for _ in range(count)]
    return chars


def retarget(a, char, names):
    """Bakes the named UAL clips onto char's armature; returns {name: action}."""
    if not names:
        return {}
    bmap = retarget_map.load()
    before = set(bpy.data.objects)
    src = rc.load_glb(a.ual)
    rt = rc.Retargeter(rc.Rig(src["arm"]), rc.Rig(char["arm"]), bmap)
    rt.set_soles(char["meshes"].values())
    out = {}
    for n in names:
        act, _ = rt.clip(src["actions"][n], "UAL|" + n, char["arm"])
        out[n] = act
    for o in set(bpy.data.objects) - before:
        bpy.data.objects.remove(o, do_unlink=True)
    rc.reset_pose(char["arm"])
    bpy.context.view_layer.update()
    return out


def clips_for(a, cfg, char, keys):
    loops = cfg["loops"]
    pack = {n: act for n, act in char["actions"].items()}
    ual_names = sorted({k.split(":", 1)[1] for k in keys if k.startswith("ual:")})
    ual = retarget(a, char, ual_names)
    out = []
    for k in keys:
        src, name = k.split(":", 1)
        if src == "pack":
            out.append(Clip("pack", name, pack[name], name in loops["pack"]))
        else:
            out.append(Clip("ual", name, ual[name], name.endswith("_Loop") or name in loops["ual"]))
    return out


def all_keys(a, char):
    import re
    ual_names = []
    if a.clips == "all" or "ual:" in a.clips:
        # the UAL clip names come from the file itself
        before = set(bpy.data.actions)
        objs = set(bpy.data.objects)
        src = rc.load_glb(a.ual)
        ual_names = sorted(src["actions"])
        for o in set(bpy.data.objects) - objs:
            bpy.data.objects.remove(o, do_unlink=True)
        for act in set(bpy.data.actions) - before:
            bpy.data.actions.remove(act)
    keys = [f"pack:{n}" for n in sorted(char["actions"])] + [f"ual:{n}" for n in ual_names]
    if a.clips != "all":
        want = a.clips.split(",")
        unknown = [w for w in want if w not in keys]
        if unknown:
            raise SystemExit(f"unknown clips {unknown}; known: {keys}")
        keys = want
    return [k for k in keys if not re.fullmatch(r"ual:.*\.\d{3}", k)]


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
        stem = f"{clip.source}_{clip.name}"
        src_label = "Ultimate Modular pack" if clip.source == "pack" else "UAL retargeted"
        title = f"{clip.name}  |  {src_label} on {a.body} ({char_name})  |  {clip.seconds:.2f} s"
        if not a.no_strips:
            path = os.path.join(a.out, "strips", a.body, stem + ".png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            strip(char, clip, a.body, path, title + "  |  top: front, bottom: right side")
            res["strip"] = path
        if not a.no_video:
            path = os.path.join(a.out, "clips", a.body, stem + ".mp4")
            video(char, clip, path, f"{clip.name} ({'pack' if clip.source == 'pack' else 'UAL'}, {a.body})")
            res["video"] = path
        res["seconds_spent"] = round(time.time() - t0, 1)
        results[clip.key] = res
        print("CLIP", a.body, clip.key, json.dumps({k: res[k] for k in ("seconds", "foot_sliding", "seconds_spent")}))
    os.makedirs(os.path.join(a.out, "metrics"), exist_ok=True)
    with open(os.path.join(a.out, "metrics", f"{a.body}{a.tag}.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)


def cmd_pairs(a):
    cfg = load_config(a.config)
    pairs = [p for p in cfg["pairs"] if not a.only or p["pack"] in a.only.split(",")]
    width = max(1 + len(p["ual"]) for p in pairs)
    chars = setup_characters(a, width)
    keys = sorted({f"pack:{p['pack']}" for p in pairs} | {f"ual:{u}" for p in pairs for u in p["ual"]})
    clips = {c.key: c for c in clips_for(a, cfg, chars[0], keys)}
    char_name = os.path.splitext(os.path.basename(a.character))[0]
    spacing = 1.45
    for p in pairs:
        row = [clips[f"pack:{p['pack']}"]] + [clips[f"ual:{u}"] for u in p["ual"]]
        k = len(row)
        for i, ch in enumerate(chars):
            rc.place(ch, x=(i - (k - 1) / 2) * spacing if i < k else 1000.0)
        # frame strip: a front and a side row per clip, at the same fractions of each clip's own length; the front
        # renders every clip at once and is cut into cells, the side renders each clip alone
        front_w = int(round(CELL[1] * spacing / BASE_HEIGHT / 2)) * 2
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
                ar.aim("side", Vector((0.0, 0.0, -FLOOR_PAD + BASE_HEIGHT / 2)), BASE_HEIGHT, front_w, CELL[1])
                rows[2 * i + 1].append(ar.render(os.path.join(TMP, "pair.png")))
            for ch in chars:
                for o in ch["meshes"].values():
                    o.hide_render = False
        names = "  vs  ".join(("pack " if c.source == "pack" else "UAL ") + c.name for c in row)
        body_img = ar.grid(rows)
        head = header(f"{names}  |  {a.body} ({char_name})  |  front and side rows in that order, at the same "
                      f"fractions of each clip", body_img.shape[1])
        out_png = os.path.join(a.out, "pairs", a.body, p["pack"] + ".png")
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
            t.data.body = ("pack " if clip.source == "pack" else "UAL ") + clip.name
            lbls.append(t)
        ar.VIEWS["pair"] = (84.0, 0.0, 0.0)
        height = 2.45
        w = int(round(480 * (k * spacing + 0.3) / height / 2) * 2)
        ar.aim("pair", Vector((0.0, 0.0, height / 2 - 0.12)), height, w, 480)

        def pose_frame(f, row=row):
            for i, clip in enumerate(row):
                clip.pose(chars[i]["arm"], clip.cycle_frame(f / FPS))

        out_mp4 = os.path.join(a.out, "pairs", a.body, p["pack"] + ".mp4")
        ar.render_video(out_mp4, w, 480, frames, pose_frame)
        for t in lbls:
            bpy.data.objects.remove(t, do_unlink=True)
        print("PAIR", a.body, p["pack"], out_mp4)


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


def main(argv):
    ap = argparse.ArgumentParser(prog="anim_review.py")
    ap.add_argument("mode", choices=["clips", "pairs", "sheets"])
    ap.add_argument("--body", choices=["men", "women"])
    ap.add_argument("--character")
    ap.add_argument("--ual")
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
    global TMP
    TMP = os.path.join(a.out, "tmp", f"{a.body or 'sheets'}{a.tag}")
    os.makedirs(TMP, exist_ok=True)
    {"clips": cmd_clips, "pairs": cmd_pairs, "sheets": cmd_sheets}[a.mode](a)


TMP = ""
main(sys.argv[sys.argv.index("--") + 1:])
