"""The animation review (tools/run.py anim-review; docs/animations.md): plays the Ultimate Modular pack's clips and the
Universal Animation Library's clips, retargeted, on an unmodified pack character, measures each clip and renders frame
strips (front and side), looping MP4 clips and side-by-side comparisons. Background Blender only.

Usage:
  blender -b --factory-startup --python-exit-code 1 --python anim_review.py -- clips --body men --character <glb>
      --ual <glb> --out <dir> [--clips pack:Walk,ual:Walk_Loop|all] [--no-video] [--no-strips] [--tag <chunk>]
  ... anim_review.py -- pairs --body men --character <glb> --ual <glb> --out <dir> --config <toml> [--only Walk,Run]
  ... anim_review.py -- sheets --out <dir> --names <file>   (review sheets: men and women strips of each clip)
  ... anim_review.py -- rates --body men --character <glb> --ual <glb> --ual-rm <glb> --out <dir>   (the game's speeds)
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
    char["ual_ratio"] = rt.ratio
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


# ------------------------------------------------------------------------------------------- the game's speeds
class Variant:
    """One lane of a rates row: a clip (or a cycle-synced blend of two UAL clips) played at the rate that makes its
    feet keep up with a treadmill moving at the row's speed."""

    def __init__(self, key, clips, speed, natural, rig):
        self.key = key
        kind, name = key.split(":", 1)
        self.parts = [clips[f"ual:{n}"] for n in name.split("+")] if kind == "blend" else [clips[key]]
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
        self.cadence = 2.0 / self.cycle * self.rate  # a loop is one stride: two steps
        self.step = speed / self.cadence

    def label(self):
        if len(self.parts) == 2:
            short = [c.name.replace("_Fwd_Loop", "").replace("_Loop", "") for c in self.parts]
            name = f"blend {short[0]} {1 - self.weight:.2f} + {short[1]} {self.weight:.2f}"
        else:
            name = ("pack " if self.parts[0].source == "pack" else "UAL ") + self.parts[0].name
        return f"{name}\nx{self.rate:.2f}, {self.cadence:.2f} steps/s, {self.step:.2f} m a step"

    def pose(self, arm, t):
        phase = (t * self.rate / self.cycle) % 1.0
        bases = []
        for clip, p0 in zip(self.parts, self.phase0):
            frame = clip.sampler.start + ((phase + p0) % 1.0) * clip.seconds * FPS
            bases.append(clip.sampler.basis(frame))
        if len(bases) == 1:
            rc.apply_basis(arm, bases[0])
            return
        a, b = bases
        out = {}
        for bone in set(a) | set(b):
            la, qa, sa = a.get(bone, Matrix.Identity(4)).decompose()
            lb, qb, sb = b.get(bone, Matrix.Identity(4)).decompose()
            if qa.dot(qb) < 0:
                qb = -qb
            out[bone] = Matrix.LocRotScale(la.lerp(lb, self.weight), qa.slerp(qb, self.weight),
                                           sa.lerp(sb, self.weight))
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
    ual = [c for c in clips.values() if c.source == "ual"]
    if ual:
        before = set(bpy.data.objects)
        rm = rc.load_glb(a.ual_rm)
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
    """Dark stripes across the floor every spacing_m metres; returns them and a function that moves them to where a
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
    rows = cfg["rates"]
    width = max(len(r["clips"]) for r in rows)
    chars = setup_characters(a, width)
    rig = rc.Rig(chars[0]["arm"])
    keys = set()
    for r in rows:
        for k in r["clips"]:
            kind, name = k.split(":", 1)
            keys |= {f"ual:{n}" for n in name.split("+")} if kind == "blend" else {k}
    clips = {c.key: c for c in clips_for(a, cfg, chars[0], sorted(keys))}
    natural, how = natural_speeds(a, chars[0], clips, rig)
    char_name = os.path.splitext(os.path.basename(a.character))[0]
    stripes, move = treadmill()
    view = (70.0, 0.0, -70.0)  # from the side and a little ahead, 20 degrees down, so the moving ground shows
    right = Vector((math.cos(math.radians(70.0)), -math.sin(math.radians(70.0)), 0.0))  # the picture's right
    ar.VIEWS["rates"] = view
    spacing, height = 2.4, 2.7  # lanes one behind the other along the picture's right
    report = {"body": a.body, "character": char_name, "natural_speed_m_s": {k: round(v, 3) for k, v in natural.items()},
              "natural_speed_from": how, "rows": {}}
    out_dir = os.path.join(a.out, "rates", a.body)
    os.makedirs(out_dir, exist_ok=True)
    for r in rows:
        lanes = [Variant(k, clips, r["speed"], natural, rig) for k in r["clips"]]
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
            "lanes": [{"clip": lane.key, "blend_weight": round(lane.weight, 3), "cycle_s": round(lane.cycle, 3),
                       "natural_speed_m_s": round(lane.natural, 3), "rate": round(lane.rate, 3),
                       "cadence_steps_s": round(lane.cadence, 2), "step_m": round(lane.step, 2)} for lane in lanes],
        }
        print("RATES", a.body, r["name"], json.dumps(report["rows"][r["name"]]["lanes"]))
    for ob in stripes:
        bpy.data.objects.remove(ob, do_unlink=True)
    with open(os.path.join(out_dir, "rates.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)


def main(argv):
    ap = argparse.ArgumentParser(prog="anim_review.py")
    ap.add_argument("mode", choices=["clips", "pairs", "sheets", "rates"])
    ap.add_argument("--body", choices=["men", "women"])
    ap.add_argument("--character")
    ap.add_argument("--ual")
    ap.add_argument("--ual-rm")
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
    {"clips": cmd_clips, "pairs": cmd_pairs, "sheets": cmd_sheets, "rates": cmd_rates}[a.mode](a)


TMP = ""
main(sys.argv[sys.argv.index("--") + 1:])
