"""Fits the first-person hands' key poses to their target frames (art#136): runs inside headless Blender.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/fp_hands_fit.py -- \
        --raw D:/prime-art-raw --out <dir> [--masks-only] [--only POSE ...] [--evals N]

The engineer rejected the first build (art PR #378, 2026-11-11: a broken, twisted wrist, the crystal burning the hands
white, a strange hold) and picked the way games make first-person hands: the hands on their own camera ([view]
fov_deg), each key pose matched to an approved target frame ([view] targets). This script reads each target frame,
finds its skin (the teal hand), the striped sleeve and the glowing crystal by colour, and searches the pose whose
render from the hands' camera covers the same pixels (the overlap, intersection over union, per part):

- a free hand (idle, fist_out): the wrist's place, the hand's turn and the wrist's bend (at most [view]
  bend_max_deg, so the wrist stays straight);
- the crystal held (crystal): first the crystal's place and turn on its glow, then per hand where its palm lies on
  the crystal (height, side, the fingers' direction, the roll) and the wrist's bend; fit_hold then seats the palm
  and curls each digit onto the surface;
- the crystal hit's contact (crystal_hit): the crystal's place and turn, the hands carried with it.

Writes <out>/fit.json (each pose's fitted fields, in fp_hands.toml's shape, and its overlap per part), the target
masks and an overlay per pose (<out>/fit_<pose>.png: the target's parts in red, the fit's in green, both yellow).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fp_hands_build as B  # noqa: E402

W, H = 192, 108          # the masks' size (the targets are 1536 x 864: 8 x 8 pixel blocks)
PARTS = ("skin", "sleeve", "crystal")
WEIGHT = {"skin": 1.0, "sleeve": 0.6, "crystal": 1.0}
HIT_ACROSS_DEG = 25.0  # the crystal hit's contact turns about the axes across the view at most this much
WRAP_TILT_DEG = 30.0   # a held hand's length is tangent to the crystal within this much: its fingers wrap round it


# ------------------------------------------------------------------------------------------- target masks
def load_rgb(path: Path) -> np.ndarray:
    im = bpy.data.images.load(str(path))
    w, h = im.size
    px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]  # top row first
    bpy.data.images.remove(im)
    return px.reshape(H, h // H, W, w // W, 3).mean(axis=(1, 3))


def grow(seed: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """The pixels of `allowed` connected to `seed` (4-neighbour flood fill)."""
    out = seed & allowed
    while True:
        nxt = out.copy()
        nxt[1:] |= out[:-1]
        nxt[:-1] |= out[1:]
        nxt[:, 1:] |= out[:, :-1]
        nxt[:, :-1] |= out[:, 1:]
        nxt &= allowed
        if (nxt == out).all():
            return out
        out = nxt


def shrink(m: np.ndarray, n: int) -> np.ndarray:
    for _ in range(n):
        k = m.copy()
        k[1:] &= m[:-1]
        k[:-1] &= m[1:]
        k[:, 1:] &= m[:, :-1]
        k[:, :-1] &= m[:, 1:]
        m = k
    return m


def widen(m: np.ndarray, n: int) -> np.ndarray:
    for _ in range(n):
        k = m.copy()
        k[1:] |= m[:-1]
        k[:-1] |= m[1:]
        k[:, 1:] |= m[:, :-1]
        k[:, :-1] |= m[:, 1:]
        m = k
    return m


def target_masks(rgb: np.ndarray, empty: np.ndarray) -> dict:
    """The arm is what differs from the empty hall ([view] background, the render the frames were made over); of it
    the crystal is the bright cyan glow, the skin the teal, the sleeve the rest."""
    fg = np.abs(rgb - empty).max(axis=2) > 0.16
    fg = widen(shrink(fg, 1), 1)                           # no single-pixel seams from the edits' small shifts
    seed = np.zeros_like(fg)
    seed[-1] = True
    seed[:, 0] = seed[:, -1] = True
    seed[: H // 3] = False
    fg = grow(seed, fg)                                    # the arm enters from the frame's bottom or sides
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    crystal = fg & (b > 0.66) & (b - r > 0.25) & (mx - mn > 0.3)
    skin = fg & ~crystal & (g - r > 0.08) & (b - r > 0.06) & (np.abs(g - b) < 0.2)
    sleeve = fg & ~crystal & ~skin
    return {"skin": skin, "sleeve": sleeve, "crystal": crystal}


def save_mask_png(path: Path, layers: list) -> None:
    """layers: (mask, rgb) drawn in order on black."""
    img = np.zeros((H, W, 4), dtype=np.float32)
    img[..., 3] = 1.0
    for m, c in layers:
        img[m, :3] += np.array(c, dtype=np.float32)
    img = np.clip(img, 0, 1)[::-1]
    im = bpy.data.images.new(path.stem, W, H)
    im.pixels = img.ravel()
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


# ---------------------------------------------------------------------------------------------- render masks
class Eye:
    """The hands' camera: vertical field of view `fov`, 16:9, at the origin looking along +y, z up."""

    def __init__(self, fov_deg: float):
        self.t = math.tan(math.radians(fov_deg) / 2.0)

    def splat(self, pts: np.ndarray, grow_px: int) -> np.ndarray:
        m = np.zeros((H, W), dtype=bool)
        if len(pts) == 0:
            return m
        y = pts[:, 1]
        ok = y > 0.02
        x, y, z = pts[ok, 0], y[ok], pts[ok, 2]
        u = ((0.5 + 0.5 * x / (y * self.t * W / H)) * W).astype(int)
        v = ((0.5 - 0.5 * z / (y * self.t)) * H).astype(int)
        keep = (u >= 0) & (u < W) & (v >= 0) & (v < H)
        m[v[keep], u[keep]] = True
        for _ in range(grow_px):
            n = m.copy()
            n[1:] |= m[:-1]
            n[:-1] |= m[1:]
            n[:, 1:] |= m[:, :-1]
            n[:, :-1] |= m[:, 1:]
            m = n
        return m


def mesh_points(obj) -> np.ndarray:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ev.matrix_world, dtype=np.float32)
    ev.to_mesh_clear()
    return co @ M[:3, :3].T + M[:3, 3]


def dense(obj) -> np.ndarray:
    """The rest mesh's triangle middles and edge middles besides its vertices, as barycentric picks, so a splat
    of a large, sparse mesh (the sleeve) fills its silhouette."""
    me = obj.data
    me.calc_loop_triangles()
    tris = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    return tris.reshape(-1, 3)


class Scene:
    def __init__(self, rig, body, top, crystal_meshes, sock, eye: Eye):
        self.rig, self.body, self.top, self.eye = rig, body, top, eye
        self.tri = {"skin": dense(body), "sleeve": dense(top)}
        self.sock = sock
        loc = []
        for o in crystal_meshes:
            glow = {i for i, m in enumerate(o.data.materials) if m and any(k in m.name.lower() for k in ("shell", "core", "light"))}
            me = o.data
            rel = sock.matrix_world.inverted() @ o.matrix_world
            for poly in me.polygons:
                if not glow or poly.material_index in glow:
                    for i in poly.vertices:
                        loc.append(rel @ me.vertices[i].co)
        self.crystal_local = np.array([tuple(v) for v in loc], dtype=np.float32)
        self.crystal_materials = sorted({m.name for o in crystal_meshes for m in o.data.materials if m})

    def fill(self, pts: np.ndarray, tri: np.ndarray) -> np.ndarray:
        a, b, c = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
        return np.concatenate([pts, (a + b + c) / 3, (a + b) / 2, (b + c) / 2, (a + c) / 2])

    def render(self, s: B.State, crystal: bool) -> dict:
        B.pose_now(self.rig, s)
        out = {"skin": self.eye.splat(self.fill(mesh_points(self.body), self.tri["skin"]), 1),
               "sleeve": self.eye.splat(self.fill(mesh_points(self.top), self.tri["sleeve"]), 1)}
        if crystal:
            M = np.array(s.crystal, dtype=np.float32)
            pts = self.crystal_local @ M[:3, :3].T + M[:3, 3]
            out["crystal"] = self.eye.splat(pts, 1)
        else:
            out["crystal"] = np.zeros((H, W), dtype=bool)
        # what is in front hides what is behind: the hands over the crystal is close enough for a silhouette
        out["crystal"] &= ~out["skin"]
        out["sleeve"] &= ~out["skin"]
        return out


def iou(a: np.ndarray, b: np.ndarray) -> float:
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def score(got: dict, want: dict, parts) -> tuple[float, dict]:
    each = {p: round(iou(got[p], want[p]), 4) for p in parts}
    return sum(WEIGHT[p] * each[p] for p in parts) / sum(WEIGHT[p] for p in parts), each


# --------------------------------------------------------------------------------------------- the search
def search(f, x0: list, step: list, lo: list, hi: list, evals: int) -> tuple[list, float]:
    """A pattern search for the largest f(x) within [lo, hi]: each coordinate tried up and down by its step, the
    steps halved when no move helps."""
    x = [min(max(v, l), h) for v, l, h in zip(x0, lo, hi)]
    best = f(x)
    n = 1
    st = list(step)
    while n < evals and max(s / s0 for s, s0 in zip(st, step)) > 1 / 32:
        moved = False
        for i in range(len(x)):
            for sgn in (1, -1):
                y = list(x)
                y[i] = min(max(y[i] + sgn * st[i], lo[i]), hi[i])
                if y[i] == x[i]:
                    continue
                v = f(y)
                n += 1
                if v > best + 1e-6:
                    x, best, moved = y, v, True
                    break
        if not moved:
            st = [s / 2 for s in st]
    return x, best


def rotvec(rx, ry, rz) -> Quaternion:
    v = Vector((rx, ry, rz))
    ang = v.length
    return Quaternion((1, 0, 0, 0)) if ang < 1e-9 else Quaternion(v.normalized(), math.radians(ang))


def vec(v) -> list:
    return [round(float(c), 4) for c in v]


def fit_free(sc: Scene, poses: B.Poses, name: str, want: dict, evals: int, bend_max: float) -> tuple[dict, dict]:
    spec = dict(poses.cfg["poses"][name]["R"])
    p0, q0 = B.V(spec["p"]), B.hand_q(spec["f"], spec["n"])
    b0 = spec.get("bend", [0.0, 0.0])

    def make(x):
        q = rotvec(x[3], x[4], x[5]) @ q0
        m = q.to_matrix()
        return {"p": vec(p0 + Vector(x[:3])), "f": vec(m.col[1]), "n": vec(m.col[2]), "bend": [round(x[6], 2), round(x[7], 2)]}

    def f(x):
        s = poses.state(name, {"R": make(x)})
        return score(sc.render(s, False), want, ("skin", "sleeve"))[0]

    x0 = [0, 0, 0, 0, 0, 0, b0[0], b0[1]]
    step = [0.03, 0.04, 0.03, 12, 12, 12, 8, 8]
    lo = [-0.2, -0.15, -0.2, -60, -60, -90, -bend_max, -bend_max]
    hi = [0.2, 0.3, 0.2, 60, 60, 90, bend_max, bend_max]
    x, _ = search(f, x0, step, lo, hi, evals)
    R = make(x)
    s = poses.state(name, {"R": R})
    got = sc.render(s, False)
    return {"R": R}, {"overlap": score(got, want, ("skin", "sleeve"))[1], "render": got}


MID = Vector((0.0, 0.0, 0.17))   # the crystal's middle in its own space (the tip at the origin, 0.35 m long)


def crystal_spec(base: dict, x) -> dict:
    """The crystal `base` turned about its middle by the rotation vector x[3:6] (degrees) and its middle moved by
    x[0:3] (m)."""
    m0 = B.crystal_matrix(base)
    c0 = m0 @ MID
    up0, front0 = B.V(base["up"]).normalized(), B.V(base["front"]).normalized()
    q = rotvec(x[3], x[4], x[5])
    c = c0 + Vector(x[:3])
    tip = c + q @ (m0.translation - c0)
    return {"p": vec(tip), "up": vec(q @ up0), "front": vec(q @ front0)}


def fit_crystal_frame(sc: Scene, poses: B.Poses, want: dict, evals: int, parts, across: float = 150.0) -> dict:
    """The crystal's place and turn (the hands carried with it). `across`: the most it turns about the axes across
    the view (x and z, degrees); the swing's turn about the view's own axis (y) is free."""
    base = poses.cfg["poses"]["crystal"]["crystal"]

    def f(x):
        s = poses.state("crystal", {"crystal": crystal_spec(base, x)})
        return score(sc.render(s, True), want, parts)[0]

    # a coarse grid of turns about the view's axis (y) and across it (x), then the pattern search from the best
    best = None
    for ry in range(-90, 91, 15):
        for rx, rz in ((-40, 0), (0, 0), (40, 0), (0, -40), (0, 40)):
            if max(abs(rx), abs(rz)) > across:
                continue
            x = [0, 0, 0, rx, ry, rz]
            v = f(x)
            if best is None or v > best[0]:
                best = (v, x)
    x, _ = search(f, best[1], [0.04, 0.05, 0.04, 12, 12, 12],
                  [-0.25, -0.15, -0.25, -across, -150, -across], [0.25, 0.4, 0.25, across, 150, across], evals)
    return crystal_spec(base, x)


def fit_held_hand(sc: Scene, poses: B.Poses, side: str, want: dict, evals: int, bend_max: float) -> dict:
    """One hand on the crystal: its palm's height on the crystal and its side (the azimuth about the crystal's
    axis), the fingers wrapping round it across its front (the hand's length tangent to the crystal, tilted at most
    WRAP_TILT_DEG off that: never along the crystal, a claw), the roll and the wrist's bend."""
    key = "R_c" if side == "Right" else "L_c"
    h0 = dict(poses.cfg["poses"]["crystal"][key])
    t0 = B.V(h0["toward"])
    t0.z = 0.0
    t0.normalize()
    az0 = math.degrees(math.atan2(t0.y, t0.x))
    b0 = h0.get("bend", [0.0, 0.0])

    def make(x):
        az = math.radians(az0 + x[1])
        t = Vector((math.cos(az), math.sin(az), 0.0))
        tang = Vector((0.0, 0.0, 1.0)).cross(t)
        if tang.y > 0:  # the fingers wrap round the crystal's front (-y), the side that faces the eye
            tang = -tang
        w = Matrix.Rotation(math.radians(x[2]), 3, t) @ tang
        return {"z": round(float(h0["z"]) + x[0], 4), "toward": vec(t), "r": h0["r"], "wrap": vec(w),
                "bend": [round(x[4], 2), round(x[5], 2)]}, x[3]

    def f(x):
        h, roll = make(x)
        poses.fit[side]["roll"] = roll
        s = poses.state("crystal", {key: h})
        return score(sc.render(s, True), want, ("skin", "sleeve"))[0]

    best = None
    for daz in range(-150, 181, 30):  # the side of the crystal first, coarse
        x = [0.0, float(daz), 0.0, 0.0, b0[0], b0[1]]
        v = f(x)
        if best is None or v > best[0]:
            best = (v, x)
    x, _ = search(f, best[1], [0.03, 15, 10, 8, 8, 8],
                  [-0.22, -200, -WRAP_TILT_DEG, -20, -bend_max, -bend_max], [0.14, 200, WRAP_TILT_DEG, 20, bend_max, bend_max], evals)
    h, roll = make(x)
    poses.fit[side]["roll"] = roll
    poses.cfg["poses"]["crystal"][key] = h
    return h


def compare(out: Path, raw: Path, view: dict, states: dict, crystal_objs) -> None:
    """Each fitted pose rendered (Workbench) from the hands' camera over its target frame: compare_<pose>.png."""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.render.resolution_x, sc.render.resolution_y = 768, 432
    sc.render.film_transparent = True
    cd = bpy.data.cameras.new("vm")
    cd.sensor_fit = "VERTICAL"
    cd.angle_y = math.radians(float(view["fov_deg"]))
    cd.clip_start = 0.01
    cam = bpy.data.objects.new("vm", cd)
    sc.collection.objects.link(cam)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam
    rig = None
    for name, (s, held) in states.items():
        for o in crystal_objs:
            o.hide_render = not held
        B.pose_now(SCENE[0].rig, s)
        if held:
            SCENE[0].sock.matrix_world  # the socket follows the Crystal bone
        tmp = out / f"_render_{name}.png"
        sc.render.filepath = str(tmp)
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(str(tmp))
        r = np.array(im.pixels[:], dtype=np.float32).reshape(432, 768, 4)
        bpy.data.images.remove(im)
        tg = bpy.data.images.load(str(raw / view["targets"][name]))
        tg.scale(768, 432)
        t = np.array(tg.pixels[:], dtype=np.float32).reshape(432, 768, 4)
        bpy.data.images.remove(tg)
        a = r[..., 3:4] * 0.65
        both = np.concatenate([t, t * (1 - a) + r * a], axis=1)
        both[..., 3] = 1.0
        img = bpy.data.images.new(name, 1536, 432)
        img.pixels = both.ravel()
        img.filepath_raw = str(out / f"compare_{name}.png")
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)


SCENE = []


# ---------------------------------------------------------------------------------------------------- main
def main(argv) -> None:
    ap = argparse.ArgumentParser(prog="fp_hands_fit.py")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--masks-only", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--evals", type=int, default=400)
    ap.add_argument("--write", action="store_true", help="also write tools/blender/fp_hands_fit.json, which the build reads")
    a = ap.parse_args(argv)
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads(B.CFG.read_text(encoding="utf-8"))
    view = cfg["view"]
    wants = {}
    rgbs = {name: load_rgb(raw / rel) for name, rel in view["targets"].items()}
    empty = load_rgb(raw / view["background"])
    for name, rgb in rgbs.items():
        wants[name] = target_masks(rgb, empty)
        m = wants[name]
        save_mask_png(out / f"mask_{name}.png", [(m["sleeve"], (0.2, 0.2, 0.9)), (m["skin"], (0.1, 0.9, 0.6)),
                                                  (m["crystal"], (0.6, 0.9, 1.0))])
    report = {"targets": {n: {p: int(m[p].sum()) for p in PARTS} for n, m in wants.items()}}
    if a.masks_only:
        print("FP_FIT " + json.dumps(report))
        return
    hands = tomllib.loads(B.HANDS.read_text(encoding="utf-8"))
    grips = dict(hands.get("grips", {}))
    grips.update(cfg.get("grips", {}))
    arm, body, top, sock, _, _ = B.cut(cfg, raw)
    rig = B.Rig(arm, cfg)
    poses = B.Poses(cfg, grips)
    B.pose_now(rig, poses.state("crystal"))
    crystal_objs, crystal_meshes = B.load_crystal(raw / cfg["source"]["crystal"], sock)
    bpy.context.view_layer.update()
    sc = Scene(rig, body, top, crystal_meshes, sock, Eye(float(view["fov_deg"])))
    SCENE.append(sc)
    report["crystal_materials"] = sc.crystal_materials
    bend = float(view["bend_max_deg"])
    only = set(a.only or view["targets"].keys())
    fitted, shown = {}, {}
    for name in ("idle", "fist_out"):
        if name in only:
            fitted[name], info = fit_free(sc, poses, name, wants[name], a.evals, bend)
            shown[name] = info.pop("render")
            report[name] = info
    if "crystal" in only or "crystal_hit" in only:
        cr = fit_crystal_frame(sc, poses, wants["crystal"], a.evals, ("crystal",))
        poses.cfg["poses"]["crystal"]["crystal"] = cr
        for side in B.SIDES:
            fit_held_hand(sc, poses, side, wants["crystal"], a.evals, bend)
        solid = B.Solid(crystal_meshes, sock)
        report["hold_fit"] = B.fit_hold(rig, poses, body, solid, roll_span=15)
        s = poses.state("crystal")
        got = sc.render(s, True)
        shown["crystal"] = got
        pc = poses.cfg["poses"]["crystal"]
        fitted["crystal"] = {"crystal": pc["crystal"], "R_c": pc["R_c"], "L_c": pc["L_c"]}
        report["crystal"] = {"overlap": score(got, wants["crystal"], PARTS)[1]}
        if "crystal_hit" in only:
            # the hit: the hold swung across the view (a turn about the view's axis, at most HIT_ACROSS_DEG
            # about the others), fitted on the crystal: the grips stay as held
            hit = fit_crystal_frame(sc, poses, wants["crystal_hit"], a.evals, ("crystal",), across=HIT_ACROSS_DEG)
            s = poses.state("crystal", {"crystal": hit})
            got = sc.render(s, True)
            shown["crystal_hit"] = got
            fitted["crystal_hit"] = {"crystal": hit}
            report["crystal_hit"] = {"overlap": score(got, wants["crystal_hit"], PARTS)[1]}
        report["hold_fit_values"] = {sd: {k: v for k, v in poses.fit[sd].items()} for sd in B.SIDES}
    states = {}
    if "idle" in fitted:
        states["idle"] = (poses.state("idle", fitted["idle"]), False)
    if "fist_out" in fitted:
        states["fist_out"] = (poses.state("fist_out", fitted["fist_out"]), False)
    if "crystal" in fitted:
        states["crystal"] = (poses.state("crystal"), True)
    if "crystal_hit" in fitted:
        states["crystal_hit"] = (poses.state("crystal", {"crystal": fitted["crystal_hit"]["crystal"]}), True)
    compare(out, raw, view, states, crystal_objs)
    for name, got in shown.items():
        want = wants[name]
        tw = want["skin"] | want["sleeve"] | want["crystal"]
        gw = got["skin"] | got["sleeve"] | got["crystal"]
        save_mask_png(out / f"fit_{name}.png", [(tw, (0.9, 0.0, 0.0)), (gw, (0.0, 0.9, 0.0))])
    report["fitted"] = fitted
    (out / "fit.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    if a.write:
        doc = {"source": "fp_hands_fit.py: the target frames of [view] targets, the hands' camera at [view] fov_deg",
               "poses": fitted, "hold_roll": {sd: round(poses.fit[sd]["roll"], 2) for sd in B.SIDES},
               "overlap": {n: report[n]["overlap"] for n in fitted}}
        B.FITTED.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print("FP_FIT " + json.dumps({k: v for k, v in report.items() if k not in ("fitted", "hold_fit")}, default=str))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
