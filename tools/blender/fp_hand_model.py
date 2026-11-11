"""The detailed first-person hand (art#136, xperiaroco2/prime-game#1587, concept A): runs inside headless Blender.

    blender -b --factory-startup --python-exit-code 1 --python tools/blender/fp_hand_model.py -- \
        --raw D:/prime-art-raw --out <dir> [--low-mm 3.0] [--high-mm 0.7] [--tex 2048] [--no-bake] [--renders]

Builds the hand of specs/fp_hand_dims.toml as a signed distance field: round cones and ellipsoids per bone (forearm,
palm, three fingers, thumb), the palm's parts blended soft, each finger webbed onto the palm and its joints blended,
neighbouring digits joined by a tight crease where they touch (the fist). The arm mesh is the field's surface (surface
nets on a `--low-mm` grid, relaxed and projected back onto it); its normal map is baked from a `--high-mm` surface of
the same field with the creases carved in; its base colour is computed per texel from the baked positions and normals
(the character's hand teal, the palm and fingertips lighter, the knuckles a touch deeper, the creases and the field's
own occlusion a little darker). Weights come from the same parts (each part's bone, blended by distance). The fist is
a finger pose of the rig plus a corrective morph `fist`: the skinned vertices projected onto the field posed with the
same bones (linear skinning alone thins each bent joint's inner side).

Writes <out>/fp_hand_char.blend: the character build (spec [hand] character) with its body meshes replaced by the two
first-person arms (one mesh with the morph; the left the right's mirror, its UVs shared) and its hand and finger bones
moved to the model's joints (same names; Little kept, unweighted), the striped top kept for fp_hands_build.py's cut;
<out>/textures/; <out>/model.json (counts, the spec's sizes measured, the fist's fit); --renders: <out>/renders/, the
concept's four views rendered at its scale beside it (compare.png) with the silhouette overlap per view.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import sys
import time
import tomllib
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import alien_pose_math as PM  # noqa: E402

SPEC = ROOT / "specs" / "fp_hand_dims.toml"
SIDES = ("Right", "Left")
DIGITS = ("index", "middle", "ring")
RIG = {"index": "Index", "middle": "Middle", "ring": "Ring", "thumb": "Thumb"}
PHAL = {"finger": ("Proximal", "Intermediate", "Distal"), "thumb": ("Metacarpal", "Proximal", "Distal")}
T0 = time.time()


def log(msg: str) -> None:
    print(f"FPH {time.time() - T0:6.1f}s {msg}", flush=True)


# ------------------------------------------------------------------------------------------------ the field
def smin(a, b, k):
    """Polynomial smooth minimum: k the blend's width (mm); at most k/4 of swelling where a == b."""
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def round_cone(p, a, b, r1, r2):
    """Exact distance to a cone between spheres (a, r1) and (b, r2) (Inigo Quilez's sdRoundCone)."""
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - y[:, None] * ba
    x2 = (xv * xv).sum(1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2
    d_b = np.sqrt(x2 + z2) * il2 - r2
    d_a = np.sqrt(x2 + y2) * il2 - r1
    d_m = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d_b, np.where(np.sign(y) * a2 * y2 < k, d_a, d_m))


class Part:
    """One primitive in the hand's space (mm), owned by a bone (its side's prefix left out): a round cone (a, b, r1,
    r2) squashed along `flat` (unit) by `s`, or an ellipsoid (c, radii along u, v, w)."""

    def __init__(self, kind, owner, sigma, **kw):
        self.kind, self.owner, self.sigma = kind, owner, sigma
        self.kw = {k: (np.array(v, float) if isinstance(v, (list, tuple)) else v) for k, v in kw.items()}

    def __call__(self, p):
        k = self.kw
        if self.kind == "cone":
            s = k.get("s", 1.0)
            if s != 1.0:
                n = k["flat"] / np.linalg.norm(k["flat"])
                c = (k["a"] + k["b"]) * 0.5
                q = p + ((p - c) @ n)[:, None] * n * (1.0 / s - 1.0)
                return round_cone(q, k["a"], k["b"], k["r1"], k["r2"]) * s
            return round_cone(p, k["a"], k["b"], k["r1"], k["r2"])
        if self.kind == "lathe":   # the forearm: an ellipse (half width a, half depth b) round a centre line, per u
            u = p[:, 0]
            a = np.interp(u, k["u"], k["a"])
            b = np.interp(u, k["u"], k["b"])
            c = np.interp(u, k["u"], k["c"])
            pw = np.interp(u, k["u"], k["p"])
            e = (np.abs((p[:, 1] - c) / a) ** pw + np.abs(p[:, 2] / b) ** pw) ** (1.0 / pw)
            d = (e - 1.0) * np.minimum(a, b)
            d = np.maximum(np.maximum(d, k["u"][0] - u), u - k["u"][-1])
            if "cut" in k:
                d = np.maximum(d, np.maximum(k["cut"][0] - u, u - k["cut"][1]))
            return d
        q = (p - k["c"]) / k["r"]
        k0 = np.linalg.norm(q, axis=1)
        k1 = np.linalg.norm(q / k["r"], axis=1)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def interp(xs, ys, x):
    return float(np.interp(x, xs, ys))


class Hand:
    """The hand of the spec as parts, joints and bones, all in the hand's space (mm)."""

    def __init__(self, spec: dict):
        self.spec = spec
        h, fa, pa = spec["hand"], spec["forearm"], spec["palm"]
        self.parts: dict[str, list[Part]] = {"arm": [], "palm": [], "mound": []}
        self.joints = {}   # bone (no side) -> (head, tail, z) in the hand's space
        W = np.array([0.0, 0.0, 1.0])
        # the forearm and the upper arm's stub: elliptic round cones along -u (depth / width as the squash along w)
        us, wid, dep, cv = fa["u"], fa["width"], fa["depth"], fa["centre_v"]
        stub_end = -float(h["forearm_len_mm"]) - float(h["upper_stub_mm"])
        # one profile from the upper arm's stub through the wrist to the knuckles (the forearm's stations, then the
        # palm's outline without the thumb's mound and its thickness), so the wrist is one smooth taper, never a seam
        # between a forearm's end and a palm; the cross-section a rounded ellipse, flatter (a superellipse) in the palm
        th = pa["thickness"]
        lo_v = [-40.0, -57.0, -70.0, -82.0, -84.0]
        hi_v = [40.0, 45.0, 48.0, 49.0, 47.5]
        pu = list(us) + list(pa["u"])
        half_w = [x / 2 for x in wid] + [(b - a) / 2 for a, b in zip(lo_v, hi_v)]
        half_d = [x / 2 for x in dep] + [x / 2 for x in th]
        mid = list(cv) + [(a + b) / 2 for a, b in zip(lo_v, hi_v)]
        power = [2.0] * len(us) + [2.3, 2.6, 2.8, 2.8, 2.8]
        end = float(pa["u"][-1]) + 16.0
        uu = np.arange(stub_end, end + 1.0, 1.0)
        prof = {}
        for key, ys in (("a", half_w), ("b", half_d), ("c", mid), ("p", power)):
            y = np.interp(uu, pu, ys)
            ker = np.ones(25) / 25.0   # the stations' corners smoothed: one soft taper, no rings
            y = np.convolve(np.pad(y, 12, mode="edge"), ker, mode="valid")
            if key in ("a", "b"):   # the end domed under the fingers' roots, never a flat cut
                t = np.clip((uu - (end - 22.0)) / 22.0, 0.0, 1.0)
                y = np.maximum(y * np.sqrt(1.0 - t * t), 1.0)
            prof[key] = y
        # its weights: the upper arm's stub, the forearm to the wrist, the hand past it (the same profile cut at the
        # wrist: the union is the profile itself)
        self.parts["arm"].append(Part("lathe", "LowerArm", 10.0, u=uu, cut=[-1e9, 0.0], **prof))
        self.parts["arm"].append(Part("lathe", "Hand", 8.0, u=uu, cut=[0.0, 1e9], **prof))
        self.parts["arm"].append(Part("cone", "UpperArm", 10.0, a=[stub_end, 0.0, 0.0],
                                      b=[-float(h["forearm_len_mm"]) - 6.0, 0.0, 0.0], r1=0.1, r2=0.1))
        fingers = spec["fingers"]
        # the thumb's mound and the little side's on the palm's side
        self.parts["mound"].append(Part("ell", "ThumbMetacarpal", 4.0, c=[40.0, 36.0, -8.0], r=[34.0, 24.0, 19.0]))
        self.parts["mound"].append(Part("ell", "Hand", 4.0, c=[56.0, -52.0, -6.0], r=[34.0, 17.0, 15.0]))
        # the fingers: three round cones each (proximal, intermediate, distal), the knuckle a little fuller
        for name in DIGITS:
            f = fingers[name]
            r = 0.5 * float(f["width"])
            s = float(f["thickness"]) / float(f["width"])
            ku, tu = float(f["knuckle_u"]), float(f["tip_u"]) - r * s ** 0.3
            v0, v1 = f["centre_v"]
            a = np.array([ku, v0 + (v0 - v1) * (f["crotch_u"] - ku) / (tu - f["crotch_u"]), 1.0])
            b = np.array([tu, v1, -1.0])
            pts = [a]
            acc = 0.0
            for share in f["phalanx"]:
                acc += share
                pts.append(a + (b - a) * acc)
            radii = [r * 0.99, r * 1.0, r * 0.99, r * 0.98]
            self.parts[name] = []
            for i, ph in enumerate(PHAL["finger"]):
                self.parts[name].append(Part("cone", RIG[name] + ph, 2.2, a=pts[i], b=pts[i + 1], r1=radii[i],
                                             r2=radii[i + 1], flat=W, s=s))
                y = pts[i + 1] - pts[i]
                self.joints[RIG[name] + ph] = (pts[i], pts[i + 1], -W)
        # the thumb: its metacarpal inside the mound, then two phalanges to the tip
        t = fingers["thumb"]
        r = 0.5 * float(t["width"])
        a = np.array([float(t["base_u"]), t["centre_v"][0], float(t["palmar_w"])])
        b = np.array([float(t["tip_u"]) - r, t["centre_v"][1] + 1.0, float(t["palmar_w"]) + 2.0])
        pts = [a]
        acc = 0.0
        for share in t["phalanx"]:
            acc += share
            p = a + (b - a) * acc
            if acc < 0.999:
                p[1] = t["centre_v"][1] - 5.0 * (1.0 - acc) / 0.6   # the thumb out at the side by its middle
            pts.append(p)
        radii = [r * 1.12, r * 1.02, r * 1.0, r * 0.98]
        self.parts["thumb"] = []
        for i, ph in enumerate(PHAL["thumb"]):
            self.parts["thumb"].append(Part("cone", "Thumb" + ph, 2.6, a=pts[i], b=pts[i + 1], r1=radii[i],
                                            r2=radii[i + 1], flat=W, s=0.94))
            y = pts[i + 1] - pts[i]
            z = np.array([0.44, -0.9, 0.0])
            self.joints["Thumb" + ph] = (pts[i], pts[i + 1], z)
        self.creases = self._creases()

    # ---------------------------------------------------------------------------------------------- evaluation
    def fields(self, p, deltas=None):
        """{part group: distance} at points p, each part moved by its bone's delta (hand space, 4x4 numpy) if any."""
        cache = {}

        def ev(part):
            if deltas and part.owner in deltas:
                key = part.owner
                if key not in cache:
                    inv = np.linalg.inv(deltas[key])
                    cache[key] = p @ inv[:3, :3].T + inv[:3, 3]
                return part(cache[key])
            return part(p)

        out = {}
        arm = None
        base = np.minimum(ev(self.parts["arm"][0]), ev(self.parts["arm"][1]))
        for part in self.parts["mound"]:
            base = smin(base, ev(part), 14.0)
        out["base"] = base
        for name in DIGITS + ("thumb",):
            out[name] = [ev(part) for part in self.parts[name]]
        return out

    def sdf(self, p, deltas=None, parts=False):
        F = self.fields(p, deltas)
        B = F["base"]
        total = B
        soft = None
        for name in DIGITS:
            P1, I1, D1 = F[name]
            total = np.minimum(total, smin(B, P1, 10.0))
            chain = np.minimum(np.minimum(P1, I1), D1)
            soft = chain if soft is None else smin(soft, chain, 3.0)
        M, Tp, Td = F["thumb"]
        total = np.minimum(total, smin(B, smin(M, Tp, 6.0), 12.0))
        soft = smin(soft, np.minimum(np.minimum(M, Tp), Td), 3.0)
        total = np.minimum(total, soft)
        return (total, F) if parts else total

    # ------------------------------------------------------------------------------------------------ creases
    def _creases(self):
        """The creases as lines (each: a point, the line's axis across the skin, a side's normal and its width
        along the hand): the fingers' palm side at each joint and the finger's root, faint wrinkles over the back of
        the middle knuckles, two palm lines, the wrist. Returned as a list of dicts for `crease`."""
        out = []
        W = np.array([0.0, 0.0, 1.0])
        for name in DIGITS + ("thumb",):
            parts = self.parts[name]
            for i, part in enumerate(parts):
                a, b = part.kw["a"], part.kw["b"]
                t = (b - a) / np.linalg.norm(b - a)
                r = float(part.kw["r1"])
                if name == "thumb" and i == 0:
                    continue
                # the joint's palm crease at its head (the finger's root crease sits a little past the knuckle)
                at = a + t * (r * 0.55 if i == 0 else 0.0)
                out.append({"p": at, "t": t, "side": -W, "r": r, "depth": 1.0, "w": 1.0, "face": 0.3})
                if i == 1 and name != "thumb":   # the wrinkles over the middle knuckle's back
                    for k, off in enumerate((-3.2, 0.0, 3.2)):
                        out.append({"p": a + t * off, "t": t, "side": W, "r": r, "depth": 0.4 if k != 1 else 0.55,
                                    "w": 0.8, "face": 0.55})
        # the palm lines (palm side): across under the fingers, and round the thumb's mound
        out.append({"line": [[78.0, -86.0], [74.0, -45.0], [70.0, -10.0], [62.0, 18.0]], "side": -W, "depth": 0.8,
                    "w": 1.3})
        out.append({"line": [[22.0, 22.0], [40.0, 18.0], [58.0, 22.0], [72.0, 34.0]], "side": -W, "depth": 0.6,
                    "w": 1.3})
        out.append({"line": [[-3.0, -40.0], [-3.0, 0.0], [-3.0, 44.0]], "side": -W, "depth": 0.6, "w": 1.0})
        return out

    def crease(self, p, n=None):
        """The creases' depth (mm, carved inward) at points p: a soft groove per line, on its side of the hand."""
        spec = self.spec["skin"]
        depth, width = float(spec["crease_depth_mm"]), float(spec["crease_width_mm"])
        out = np.zeros(len(p))
        for c in self.creases:
            if "line" in c:
                ln = np.array(c["line"])
                best = np.full(len(p), 1e9)
                for q0, q1 in zip(ln[:-1], ln[1:]):
                    d = q1 - q0
                    t = np.clip(((p[:, :2] - q0) @ d) / float(d @ d), 0.0, 1.0)
                    best = np.minimum(best, np.linalg.norm(p[:, :2] - (q0 + t[:, None] * d), axis=1))
                side = np.clip((p @ c["side"] + 4.0) / 10.0, 0.0, 1.0)
                g = np.exp(-(best / (0.5 * width * c["w"])) ** 2) * side
                # fade at the line's ends
                out += depth * c["depth"] * g
                continue
            rel = p - c["p"]
            ax = rel @ c["t"]
            radial = rel - ax[:, None] * c["t"]
            rn = np.linalg.norm(radial, axis=1) + 1e-9
            facing = (radial @ c["side"]) / rn
            g = np.exp(-(ax / (0.5 * width * c["w"])) ** 2) * np.clip((facing - c["face"]) / 0.35, 0.0, 1.0)
            g *= np.exp(-np.maximum(rn - c["r"] * 1.15, 0.0) / 2.0)
            out += depth * c["depth"] * g
        return out


def grad(fn, p, eps=0.25):
    g = np.empty_like(p)
    for i in range(3):
        e = np.zeros(3)
        e[i] = eps
        g[:, i] = (fn(p + e) - fn(p - e)) / (2 * eps)
    return g


def project(p, fn, iters=4):
    for _ in range(iters):
        d = fn(p)
        g = grad(fn, p)
        p = p - (d / np.maximum((g * g).sum(1), 1e-6))[:, None] * g
    return p


# ------------------------------------------------------------------------------------------- surface nets
def grid_eval(fn, lo, hi, h, chunk=1_500_000):
    n = (np.ceil((np.array(hi) - np.array(lo)) / h)).astype(int) + 1
    xs = [lo[i] + h * np.arange(n[i]) for i in range(3)]
    F = np.empty(tuple(n), np.float32)
    per = max(1, chunk // int(n[1] * n[2]))
    Y, Z = np.meshgrid(xs[1], xs[2], indexing="ij")
    for i0 in range(0, n[0], per):
        X = xs[0][i0:i0 + per]
        P = np.stack(np.broadcast_arrays(X[:, None, None], Y[None], Z[None]), -1).reshape(-1, 3)
        F[i0:i0 + per] = fn(P).reshape(len(X), n[1], n[2])
    return F


def surface_nets(F, lo, h):
    """Quads over the zero level of the grid F (corner values; lo the first corner, h the step): one vertex per
    cell the surface crosses (the mean of its edges' crossings), one quad per crossed interior edge, facing out."""
    ins = F < 0
    nx, ny, nz = F.shape
    cells = np.zeros((nx - 1, ny - 1, nz - 1), np.int8)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                cells += ins[dx:nx - 1 + dx, dy:ny - 1 + dy, dz:nz - 1 + dz]
    active = (cells > 0) & (cells < 8)
    cid = np.full(active.shape, -1, np.int64)
    nv = int(active.sum())
    cid[active] = np.arange(nv)
    acc = np.zeros((nv, 3))
    cnt = np.zeros(nv)
    faces = []
    shape = F.shape
    for ax in range(3):
        o1, o2 = {0: (1, 2), 1: (2, 0), 2: (0, 1)}[ax]
        s0 = [slice(None)] * 3
        s1 = [slice(None)] * 3
        s0[ax] = slice(0, shape[ax] - 1)
        s1[ax] = slice(1, shape[ax])
        f0, f1 = F[tuple(s0)], F[tuple(s1)]
        cross = (f0 < 0) != (f1 < 0)
        e = np.argwhere(cross)
        a, b = f0[cross], f1[cross]
        t = a / (a - b)
        pos = e.astype(np.float64)
        pos[:, ax] += t
        for d1 in (0, 1):
            for d2 in (0, 1):
                c = e.copy()
                c[:, o1] -= d1
                c[:, o2] -= d2
                ok = (c[:, o1] >= 0) & (c[:, o1] < shape[o1] - 1) & (c[:, o2] >= 0) & (c[:, o2] < shape[o2] - 1)
                ids = cid[c[ok, 0], c[ok, 1], c[ok, 2]]
                np.add.at(acc, ids, pos[ok])
                np.add.at(cnt, ids, 1)
        inner = (e[:, o1] >= 1) & (e[:, o1] < shape[o1] - 1) & (e[:, o2] >= 1) & (e[:, o2] < shape[o2] - 1)
        e, inside_low = e[inner], (a < 0)[inner]
        quad = []
        for d1, d2 in ((1, 1), (0, 1), (0, 0), (1, 0)):
            c = e.copy()
            c[:, o1] -= d1
            c[:, o2] -= d2
            quad.append(cid[c[:, 0], c[:, 1], c[:, 2]])
        quad = np.stack(quad, 1)
        quad[~inside_low] = quad[~inside_low][:, ::-1]
        faces.append(quad)
    verts = np.array(lo) + h * acc / cnt[:, None]
    return verts, np.concatenate(faces)


def edges_of(faces):
    e = np.concatenate([faces[:, [i, (i + 1) % 4]] for i in range(4)])
    e.sort(1)
    return np.unique(e, axis=0)


def relax(v, faces, fn, iters=6):
    """Even quads: tangential smoothing, each step projected back onto the surface."""
    E = edges_of(faces)
    for _ in range(iters):
        s = np.zeros_like(v)
        c = np.zeros(len(v))
        np.add.at(s, E[:, 0], v[E[:, 1]])
        np.add.at(s, E[:, 1], v[E[:, 0]])
        np.add.at(c, E[:, 0], 1)
        np.add.at(c, E[:, 1], 1)
        lap = s / np.maximum(c, 1)[:, None] - v
        n = grad(fn, v)
        n /= np.maximum(np.linalg.norm(n, axis=1), 1e-9)[:, None]
        lap -= (lap * n).sum(1)[:, None] * n
        v = project(v + 0.5 * lap, fn, 2)
    return v


def make_mesh(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


# ----------------------------------------------------------------------------------------------- the rig
class Space:
    """The hand's space (mm) in the character's armature (m), right side: the wrist the RightHand head, u along the
    forearm (elbow to wrist), w up (the T-pose's palm faces down), v = w x u (toward the thumb, the front)."""

    def __init__(self, arm):
        b = arm.data.bones
        wrist = b["RightHand"].head_local.copy()
        u = (wrist - b["RightLowerArm"].head_local).normalized()
        w = Vector((0, 0, 1))
        w = (w - u * w.dot(u)).normalized()
        v = w.cross(u)
        R = Matrix((u, v, w)).transposed()
        self.R = R
        self.M = Matrix.Translation(wrist) @ R.to_4x4() @ Matrix.Diagonal((0.001, 0.001, 0.001, 1.0))
        self.Mi = self.M.inverted()
        self.np = np.array(self.M)
        self.npi = np.array(self.Mi)

    def pt(self, p, left=False):
        q = self.M @ Vector(tuple(float(x) for x in p))
        return Vector((-q.x, q.y, q.z)) if left else q

    def dir(self, d, left=False):
        q = self.R @ Vector(tuple(float(x) for x in d))
        return Vector((-q.x, q.y, q.z)) if left else q


def set_bones(arm, hand: Hand, sp: Space):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for side in SIDES:
        for name in hand.joints:
            eb[side + name].use_connect = False
    for side in SIDES:
        left = side == "Left"
        for name, (hd, tl, z) in hand.joints.items():
            b = eb[side + name]
            b.head, b.tail = sp.pt(hd, left), sp.pt(tl, left)
            b.align_roll(sp.dir(z, left))
    bpy.ops.object.mode_set(mode="OBJECT")


def weights(hand: Hand, v):
    """Per vertex the bones (no side) and weights: each part's own distance through exp(-d / sigma), the largest four
    kept and normalised."""
    names, cols = [], []
    elbow = -float(hand.spec["hand"]["forearm_len_mm"])
    for group in hand.parts.values():
        for part in group:
            if part.owner == "UpperArm":   # the stub: by the distance past the elbow along the arm
                d = np.maximum(v[:, 0] - (elbow - 10.0), 0.0) * 0.6
            else:
                d = np.maximum(part(v), 0.0)
            w = np.exp(-d / part.sigma)
            if part.owner in names:
                i = names.index(part.owner)
                cols[i] = np.maximum(cols[i], w)
            else:
                names.append(part.owner)
                cols.append(w)
    W = np.stack(cols, 1)
    order = np.argsort(-W, 1)[:, :4]
    top = np.take_along_axis(W, order, 1)
    top[top < 0.01] = 0.0
    top /= top.sum(1, keepdims=True)
    return names, order, top


# --------------------------------------------------------------------------------------- skin and baking
def char_skin(body, arm) -> list:
    """The character's hand albedo (sRGB median under its right hand's vertices), from its skin texture."""
    groups = {g.index: g.name for g in body.vertex_groups}
    hand = set()
    for v in body.data.vertices:
        if v.groups:
            g = max(v.groups, key=lambda x: x.weight)
            n = groups[g.group]
            if n.startswith("Right") and (n == "RightHand" or any(n.startswith("Right" + f) for f in PM.FINGERS)):
                hand.add(v.index)
    me = body.data
    uv = me.uv_layers.active.data
    samples = {}
    for poly in me.polygons:
        mat = me.materials[poly.material_index]
        if mat is None or not mat.use_nodes:
            continue
        img = next((n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and
                    n.image.colorspace_settings.name == "sRGB"), None)
        if img is None:
            continue
        for li in poly.loop_indices:
            if me.loops[li].vertex_index in hand:
                samples.setdefault(img.name, []).append(tuple(uv[li].uv))
    if not samples:
        return [0.36, 0.62, 0.60]
    name = max(samples, key=lambda k: len(samples[k]))
    img = bpy.data.images[name]
    w, h = img.size
    px = np.array(img.pixels[:], np.float32).reshape(h, w, img.channels)
    uvs = np.array(samples[name])
    x = np.clip((uvs[:, 0] % 1.0) * w, 0, w - 1).astype(int)
    y = np.clip((uvs[:, 1] % 1.0) * h, 0, h - 1).astype(int)
    rgb = px[y, x, :3]
    return [round(float(c), 4) for c in np.median(rgb, 0)]


def srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, float), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def shade(base, dv=0.0, ds=0.0):
    h, s, v = colorsys.rgb_to_hsv(*base)
    return np.array(colorsys.hsv_to_rgb(h, max(0.0, s * (1.0 - ds)), min(1.0, v + dv)))


def setup_cycles(samples=1):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    return sc


def new_image(name, tex, float_buffer=False, colour=(0, 0, 0, 0), non_color=False):
    img = bpy.data.images.new(name, tex, tex, alpha=True, float_buffer=float_buffer)
    img.generated_color = colour
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def bake_to(ob, img, kind, **kw):
    mat = ob.data.materials[0]
    nodes = mat.node_tree.nodes
    node = nodes.get("_bake") or nodes.new("ShaderNodeTexImage")
    node.name = "_bake"
    node.image = img
    nodes.active = node
    for n in nodes:
        n.select = n.name == node.name
    res = bpy.ops.object.bake(type=kind, margin=8, use_clear=False, **kw)
    px = np.array(img.pixels[:], np.float32).reshape(-1, 4)
    log(f"bake {kind} into {img.name}: {res}, max {px.max(0).round(3).tolist()}, uv {ob.data.uv_layers.active.name if ob.data.uv_layers.active else None}, sel {ob.select_get()}, active {bpy.context.view_layer.objects.active.name}")


def emit_material(name, link):
    """A material that emits an attribute (link(nodes, links) -> the colour socket)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(link(nt.nodes, nt.links), em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def bake_maps(hand: Hand, low, out: Path, tex: int, high_mm: float, base_srgb):
    """The normal map (from a fine surface with the creases) and the base colour (per texel, from the low mesh's
    baked positions and normals). Returns the two images and a few numbers."""
    stats = {}
    sc = setup_cycles(1)
    sc.render.bake.use_selected_to_active = False
    # positions and normals of the low mesh per texel (emission, mapped into 0..1)
    def pos_link(nodes, links):
        geo = nodes.new("ShaderNodeNewGeometry")
        mp = nodes.new("ShaderNodeVectorMath")
        mp.operation = "MULTIPLY_ADD"
        mp.inputs[1].default_value = (1 / 800,) * 3
        mp.inputs[2].default_value = (0.5,) * 3
        links.new(geo.outputs["Position"], mp.inputs[0])
        return mp.outputs[0]

    def nrm_link(nodes, links):
        geo = nodes.new("ShaderNodeNewGeometry")
        mp = nodes.new("ShaderNodeVectorMath")
        mp.operation = "MULTIPLY_ADD"
        mp.inputs[1].default_value = (0.5,) * 3
        mp.inputs[2].default_value = (0.5,) * 3
        links.new(geo.outputs["Normal"], mp.inputs[0])
        return mp.outputs[0]

    bpy.ops.object.select_all(action="DESELECT")
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    keep = list(low.data.materials)
    imgs = {}
    for key, link in (("pos", pos_link), ("nrm", nrm_link)):
        low.data.materials.clear()
        low.data.materials.append(emit_material("_" + key, link))
        imgs[key] = new_image("_" + key, tex, float_buffer=True, non_color=True)
        bake_to(low, imgs[key], "EMIT")
    log("baked positions and normals")
    px = {k: np.array(im.pixels[:], np.float32).reshape(tex, tex, 4) for k, im in imgs.items()}
    cover = px["pos"][..., :3].sum(-1) > 0.01   # baked texels (the image starts black; a position is never 0)
    P = (px["pos"][..., :3][cover].astype(np.float64) - 0.5) * 800.0
    N = px["nrm"][..., :3][cover].astype(np.float64) * 2.0 - 1.0
    N /= np.maximum(np.linalg.norm(N, axis=1), 1e-9)[:, None]
    # the colour: palm and fingertips lighter, knuckles deeper, creases and occlusion a little darker
    sk = hand.spec["skin"]
    base = np.array(base_srgb)
    c_palm = shade(base, sk["palm_lighter"], sk["palm_paler"])
    c_tip = shade(base, sk["tip_lighter"], sk["palm_paler"] * 0.5)
    c_knk = shade(base, -sk["knuckle_deeper"], -0.04)
    palm = np.clip((-N[:, 2] + 0.15) / 0.75, 0.0, 1.0) ** 1.5
    tip = np.zeros(len(P))
    knk = np.zeros(len(P))
    for name in DIGITS + ("thumb",):
        parts = hand.parts[name]
        a, b = parts[-1].kw["a"], parts[-1].kw["b"]
        L = np.linalg.norm(b - a)
        t = (b - a) / L
        ax = (P - a) @ t
        rad = np.linalg.norm((P - a) - ax[:, None] * t, axis=1)
        near = np.exp(-np.maximum(rad - parts[-1].kw["r1"] * 1.2, 0) / 3.0)
        tip = np.maximum(tip, np.clip((ax - 0.15 * L) / (0.85 * L + parts[-1].kw["r2"]), 0.0, 1.0) * near)
        if name != "thumb":
            for part in parts[:2]:
                j = part.kw["a"]
                d = np.linalg.norm(P - j, axis=1)
                knk = np.maximum(knk, np.exp(-(d / (part.kw["r1"] * 1.1)) ** 2) * np.clip(N[:, 2], 0.0, 1.0))
    col = base[None, :] * np.ones((len(P), 1))
    col = col + (c_palm - col) * palm[:, None]
    col = col + (c_tip - col) * (0.85 * tip)[:, None]
    col = col + (c_knk - col) * (0.8 * knk)[:, None]
    groove = np.clip(hand.crease(P, N) / float(sk["crease_depth_mm"]), 0.0, 1.0)
    # the field's own occlusion (the webs, the thumb's root): how much of a few steps along the normal is free
    fn = hand.sdf
    occ = np.zeros(len(P))
    for i, hstep in enumerate((3.0, 7.0, 14.0)):
        d = np.empty(len(P))
        for s in range(0, len(P), 400_000):
            d[s:s + 400_000] = fn(P[s:s + 400_000] + N[s:s + 400_000] * hstep)
        occ += (hstep - np.clip(d, 0.0, hstep)) / hstep * (0.5 ** i)
    ao = 1.0 - 0.32 * np.clip(occ / 1.75, 0.0, 1.0)
    lin = srgb_to_lin(col) * (ao * (1.0 - 0.10 * groove))[:, None]
    out_rgb = np.zeros((tex, tex, 4), np.float32)
    out_rgb[..., 3] = 1.0
    out_rgb[..., :3] = base
    out_rgb[cover, :3] = lin_to_srgb(lin)
    stats["colours_srgb"] = {"base": [round(float(x), 3) for x in base], "palm": [round(float(x), 3) for x in c_palm],
                             "tip": [round(float(x), 3) for x in c_tip], "knuckle": [round(float(x), 3) for x in c_knk]}
    stats["occlusion_min"] = round(float(ao.min()), 3)
    (out / "textures").mkdir(parents=True, exist_ok=True)
    col_img = bpy.data.images.new("fp_hand_basecolor", tex, tex, alpha=False)
    col_img.pixels = out_rgb.ravel()
    col_img.filepath_raw = str(out / "textures" / "fp_hand_basecolor.png")
    col_img.file_format = "PNG"
    col_img.save()
    log("base colour written")
    # the normal map: a fine surface of the field with the creases, baked onto the low mesh
    def detailed(p):
        return fn(p) + hand.crease(p)
    lo, hi = [-90.0, -105.0, -48.0], [222.0, 105.0, 48.0]
    F = grid_eval(detailed, lo, hi, high_mm)
    hv, hf = surface_nets(F, lo, high_mm)
    del F
    high = make_mesh("_high", hv, hf)
    stats["high_quads"] = len(hf)
    log(f"high surface {len(hf)} quads")
    nrm_img = new_image("fp_hand_normal", tex, colour=(0.5, 0.5, 1.0, 1.0), non_color=True)
    low.data.materials.clear()
    for m in keep:
        low.data.materials.append(m)
    bpy.ops.object.select_all(action="DESELECT")
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    sc.render.bake.use_selected_to_active = True
    sc.render.bake.cage_extrusion = 2.0
    sc.render.bake.max_ray_distance = 5.0
    sc.render.bake.normal_space = "TANGENT"
    bake_to(low, nrm_img, "NORMAL")
    sc.render.bake.use_selected_to_active = False
    nrm_img.filepath_raw = str(out / "textures" / "fp_hand_normal.png")
    nrm_img.file_format = "PNG"
    nrm_img.save()
    bpy.data.objects.remove(high, do_unlink=True)
    for im in imgs.values():
        bpy.data.images.remove(im)
    log("normal map written")
    col_img = bpy.data.images.load(str(out / "textures" / "fp_hand_basecolor.png"))
    nrm_img = bpy.data.images.load(str(out / "textures" / "fp_hand_normal.png"))
    nrm_img.colorspace_settings.name = "Non-Color"
    return col_img, nrm_img, stats


def skin_material(base_srgb, col_img=None, nrm_img=None, roughness=0.42):
    mat = bpy.data.materials.new("fp_hand_skin")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Base Color"].default_value = (*srgb_to_lin(base_srgb), 1.0)
    if col_img is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = col_img
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if nrm_img is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = nrm_img
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# ------------------------------------------------------------------------------------------------ the fist
def fist_grip(spec: dict) -> dict:
    f = spec["fist"]
    g = {"mirror": True, "Little": [0.0, 0.0, 0.0]}
    for name in DIGITS:
        g[RIG[name]] = list(f["curl_deg"][name])
    g["Thumb"] = [float(x) for x in f["thumb"]["curl"]]
    g["ThumbTurn"] = [float(x) for x in f["thumb"]["turn"]]
    return g


def pose_grip(arm, grip: dict | None, side="Right"):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        if pb.name.startswith(side):
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
    if grip:
        for b, q in PM.grip_quats(grip, side).items():
            if b in arm.pose.bones:
                arm.pose.bones[b].rotation_quaternion = q
    bpy.context.view_layer.update()


def deltas_hand(arm, sp: Space, side="Right") -> dict:
    """Per bone (no side) its pose's delta in the hand's space (4x4 numpy)."""
    out = {}
    for pb in arm.pose.bones:
        if not pb.name.startswith(side):
            continue
        D = pb.matrix @ pb.bone.matrix_local.inverted()
        out[pb.name[len(side):]] = np.array(sp.Mi @ D @ sp.M)
    return out


def corrective(hand: Hand, arm, ob, sp: Space, right_n: int, spec: dict) -> dict:
    """The morph `fist`: the right arm's skinned vertices in the fist projected onto the field posed with the same
    bones, carried back through each vertex's skinning matrix into the rest."""
    pose_grip(arm, fist_grip(spec))
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    posed = np.array([v.co[:] for v in me.vertices[:right_n]])
    ev.to_mesh_clear()
    rest = np.array([v.co[:] for v in ob.data.vertices[:right_n]])
    D = deltas_hand(arm, sp)
    ph = posed @ sp.npi[:3, :3].T + sp.npi[:3, 3]
    cav = spec["fist"].get("cavity")
    if cav:   # the fist's tunnel (between the tucked tips, the palm and the thumb) filled: no dark hole from the side
        fill = Part("ell", "Hand", 1.0, c=cav["c"], r=cav["r"])
        fn = lambda p: smin(hand.sdf(p, D), fill(p), 8.0)  # noqa: E731
    else:
        fn = lambda p: hand.sdf(p, D)  # noqa: E731
    target = project(ph.copy(), fn, 5)
    move = target - ph
    depth = fn(ph)
    keep = np.clip((depth + 14.0) / 8.0, 0.0, 1.0)   # deep inside the fist (a palm under curled fingers): left to the
    move *= keep[:, None]                            # skinning, hidden there; a soft edge between
    deep = keep < 0.5
    # the move smoothed over the mesh (no ragged edge between moved and kept vertices)
    E = np.array([e.vertices[:] for e in ob.data.edges])
    E = E[(E < right_n).all(1)]
    for _ in range(4):
        sm = np.zeros_like(move)
        c = np.zeros(len(move))
        np.add.at(sm, E[:, 0], move[E[:, 1]])
        np.add.at(sm, E[:, 1], move[E[:, 0]])
        np.add.at(c, E[:, 0], 1)
        np.add.at(c, E[:, 1], 1)
        move = 0.5 * move + 0.5 * sm / np.maximum(c, 1)[:, None]
    m = np.linalg.norm(move, axis=1)
    cap = 10.0
    move *= np.minimum(1.0, cap / np.maximum(m, 1e-9))[:, None]
    ta = (ph + move) @ sp.np[:3, :3].T + sp.np[:3, 3]
    # each vertex's skinning matrix (armature space), inverted
    bones = {pb.name: np.array(pb.matrix @ pb.bone.matrix_local.inverted()) for pb in arm.pose.bones}
    names = {g.index: g.name for g in ob.vertex_groups}
    key = np.zeros((right_n, 3))
    for i, v in enumerate(ob.data.vertices[:right_n]):
        Mv = np.zeros((4, 4))
        tw = 0.0
        for g in v.groups:
            Mv += g.weight * bones[names[g.group]]
            tw += g.weight
        Mv /= max(tw, 1e-9)
        key[i] = (np.linalg.inv(Mv) @ np.append(ta[i], 1.0))[:3]
    pose_grip(arm, None)
    sk = ob.data.shape_keys.key_blocks["fist"]
    co = np.array([v.co[:] for v in sk.data])
    co[:right_n] = key
    sk.data.foreach_set("co", co.ravel())
    return {"moved_mm_p50": round(float(np.median(m)), 2), "moved_mm_p99": round(float(np.percentile(m, 99)), 2),
            "capped": int((m > cap).sum()), "deep_kept": int(deep.sum())}


def fit_thumb(hand: Hand, arm, sp: Space, spec: dict) -> dict:
    """The fist's thumb: the turn [roll, swing] and three curls that lay its last phalanx across the front of the
    index's and the middle finger's curled middle phalanges (its pad between them, at the two radii off their axes,
    pointing across the hand toward the ring finger) without entering them: a coarse search, then a descent."""
    g = fist_grip(spec)
    mods = [m for o in arm.children for m in o.modifiers]
    for m in mods:
        m.show_viewport = False
    rT = float(hand.parts["thumb"][2].kw["r1"]) * 0.94
    pose_grip(arm, g)
    D = deltas_hand(arm, sp)
    tt = spec["fist"].get("thumb_target", {})
    part = hand.parts[tt.get("finger", "index")][1]
    M = (D[part.owner] @ np.append((part.kw["a"] + part.kw["b"]) * 0.5, 1.0))[:3]
    M[0] += float(tt.get("du", -8.0))   # the pad on the index's curled middle phalanx toward the palm
    out_dir = np.array(tt.get("dir", [0.25, 0.0, -1.0]), float)
    out_dir /= np.linalg.norm(out_dir)
    rf = 0.5 * float(spec["fingers"]["middle"]["width"]) * float(spec["fingers"]["middle"]["thickness"]) / float(
        spec["fingers"]["middle"]["width"])
    target = M + out_dir * (rf + rT - 2.0)
    across = np.array([0.0, -1.0, 0.0])

    def cost(x):
        roll, swing, c0, c1, c2 = x
        pose_grip(arm, dict(g, ThumbTurn=[roll, swing], Thumb=[c0, c1, c2]))
        D = deltas_hand(arm, sp)
        pts = []
        for k, part in enumerate(hand.parts["thumb"][1:]):
            Dm = D[part.owner]
            for s_ in np.linspace(0.4 if k == 0 else 0.0, 1.0, 4):
                p = part.kw["a"] + (part.kw["b"] - part.kw["a"]) * s_
                pts.append((Dm @ np.append(p, 1.0))[:3])
        pts = np.array(pts)
        F = hand.fields(pts, D)
        fing = np.minimum.reduce([np.minimum.reduce(F[n]) for n in DIGITS] + [F["base"]])
        r_here = np.array([rT] * 8)
        pen = np.clip(r_here - 2.0 - fing, 0.0, None)
        pad = pts[-3:-1].mean(0)
        d = pts[-1] - pts[-4]
        d /= max(np.linalg.norm(d), 1e-9)
        c = 3.0 * float(pen.sum()) + float(np.linalg.norm(pad - target)) + 30.0 * (1.0 - float(d @ across))
        return c, float(pen.max()), float(np.linalg.norm(pad - target)), float(d @ across)

    best = None
    for roll in range(-90, 91, 30):
        for swing in range(0, 111, 15):
            for c0 in (0, 20, 40):
                for c1 in (0, 30, 60):
                    for c2 in (0, 40, 80):
                        x = [float(roll), float(swing), float(c0), float(c1), float(c2)]
                        c = cost(x)
                        if best is None or c[0] < best[1][0]:
                            best = (x, c)
    x, c = best
    step = 12.0
    while step >= 1.0:
        moved = False
        for i in range(5):
            for sgn in (1.0, -1.0):
                y = list(x)
                y[i] += sgn * step
                cy = cost(y)
                if cy[0] < c[0]:
                    x, c, moved = y, cy, True
        if not moved:
            step *= 0.5
    for m in mods:
        m.show_viewport = True
    pose_grip(arm, None)
    x = [round(v, 1) for v in x]
    spec["fist"]["thumb"]["turn"] = x[:2]
    spec["fist"]["thumb"]["curl"] = x[2:]
    return {"turn": x[:2], "curl": x[2:], "deepest_mm": round(c[1], 1), "pad_to_target_mm": round(c[2], 1),
            "across": round(c[3], 2), "target": [round(float(t), 1) for t in target]}


# ---------------------------------------------------------------------------------------------- measures
def measure(hand: Hand, v, top_bone, spec: dict, tag: str) -> dict:
    """The spec's sizes on the build (the hand's space, mm): the forearm, the palm, the tips; `tag` 'open'."""
    out = {}
    fa = spec["forearm"]
    rows = []
    for u, w, d in zip(fa["u"], fa["width"], fa["depth"]):
        if u < -float(spec["hand"]["forearm_len_mm"]):
            continue
        s = v[np.abs(v[:, 0] - u) < 1.6]
        if len(s):
            rows.append({"u": u, "width": [w, round(float(np.ptp(s[:, 1])), 1)], "depth": [d, round(float(np.ptp(s[:, 2])), 1)]})
    out["forearm"] = rows
    pa = spec["palm"]
    thumb_far = np.array([b.startswith("Thumb") and b != "ThumbMetacarpal" for b in top_bone])
    rows = []
    for u, a, b in zip(pa["u"], pa["v_min"], pa["v_max"]):
        m = np.abs(v[:, 0] - u) < 1.6
        if u > 70:
            m &= ~np.array([bn.startswith("Thumb") for bn in top_bone])
        else:
            m &= ~thumb_far
        s = v[m]
        rows.append({"u": u, "v_min": [a, round(float(s[:, 1].min()), 1)], "v_max": [b, round(float(s[:, 1].max()), 1)],
                     "thickness": [pa["thickness"][pa["u"].index(u)], round(float(np.ptp(s[:, 2])), 1)]})
    out["palm"] = rows
    tips = {}
    for name in DIGITS + ("thumb",):
        f = spec["fingers"][name]
        own = np.array([bn.startswith(RIG[name]) for bn in top_bone])
        s = v[own]
        i = np.argmax(s[:, 0])
        tips[name] = {"tip_u": [f["tip_u"], round(float(s[i, 0]), 1)]}
        if name != "thumb":
            near = s[s[:, 0] > s[i, 0] - 25]
            tips[name]["width"] = [f["width"], round(float(np.ptp(near[:, 1])), 1)]
            tips[name]["thickness"] = [f["thickness"], round(float(np.ptp(near[:, 2])), 1)]
    out["fingers"] = tips
    return out


def check(m: dict, spec: dict) -> list:
    tol, pct = float(spec["hand"]["tol_mm"]), float(spec["hand"]["tol_pct"]) / 100.0
    bad = []

    def one(where, pair):
        want, got = pair
        if abs(got - want) > max(tol, abs(want) * pct):
            bad.append(f"{where}: {got} mm, spec {want}")
    for r in m["open"]["forearm"]:
        one(f"forearm u {r['u']} width", r["width"])
        one(f"forearm u {r['u']} depth", r["depth"])
    for r in m["open"]["palm"]:
        one(f"palm u {r['u']} v_min", r["v_min"])
        one(f"palm u {r['u']} v_max", r["v_max"])
    for n, r in m["open"]["fingers"].items():
        for k, pair in r.items():
            one(f"{n} {k}", pair)
    for k, pair in m.get("fist", {}).items():
        one(f"fist {k}", pair)
    return bad


# ----------------------------------------------------------------------------------------------- renders
VIEWS = {   # per concept view: the camera's direction toward it (hand space), its up, mirrored for the compare
    "back": {"to": (0, 0, 1), "up": (-1, 0, 0), "fist": False, "mirror": False},
    "palm": {"to": (0, 0, -1), "up": (-1, 0, 0), "fist": False, "mirror": True},
    "fist_back": {"to": (0, 0, 1), "up": (-1, 0, 0), "fist": True, "mirror": False},
    "fist_side": {"to": (0, 1, 0), "up": (-1, 0, 0), "fist": True, "mirror": True},
    "fist_3q": {"to": (-0.35, 0.55, 0.75), "up": (-1, 0, 0.4), "fist": True, "mirror": False},
    "fist_fp": {"to": (-0.85, 0.3, 0.45), "up": (0.3, 0, 1), "fist": True, "mirror": False},
    "open_3q": {"to": (-0.35, 0.55, 0.75), "up": (-1, 0, 0.4), "fist": False, "mirror": False},
}


def stage(ob, samples: int):
    """The review scene: Cycles, a grey world, an orthographic camera with a soft key, fill and rim on it."""
    sc = setup_cycles(samples)
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not ob:
            o.hide_render = True
    world = bpy.data.worlds.new("grey")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
    bg.inputs["Strength"].default_value = 0.3
    sc.world = world
    cam_d = bpy.data.cameras.new("rcam")
    cam_d.type = "ORTHO"
    cam_d.clip_start, cam_d.clip_end = 0.01, 3.0
    cam = bpy.data.objects.new("rcam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for name, (loc, energy, size) in {"key": ((-0.9, 1.1, 1.6), 150.0, 1.2), "fill": ((1.2, -0.2, 1.4), 35.0, 1.6),
                                      "rim": ((0.3, 1.4, -1.2), 60.0, 0.8)}.items():
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = energy, size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.parent = cam
        lo.location = loc
        lo.rotation_euler = (Vector(loc) - Vector((0.0, 0.0, -0.4))).to_track_quat("Z", "Y").to_euler()
    return sc, cam


def shoot(sc, cam, sp: Space, vw: dict, centre, path: Path, size=(384, 1024), ortho=0.512) -> None:
    sc.render.resolution_x, sc.render.resolution_y = size
    cam.data.ortho_scale = ortho
    to = np.array(vw["to"], float)
    up = np.array(vw["up"], float)
    pos = sp.pt(np.array(centre, float) + to * 400.0)
    back = sp.dir(to).normalized()
    upv = sp.dir(up)
    upv = (upv - back * upv.dot(back)).normalized()
    right = upv.cross(back)
    cam.matrix_world = Matrix.Translation(pos) @ Matrix((right, upv, back)).transposed().to_4x4()
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def renders(out: Path, arm, ob, sp: Space, spec: dict, concept: Path, samples: int) -> dict:
    sc, cam = stage(ob, samples)
    (out / "renders").mkdir(parents=True, exist_ok=True)
    centre_u = (512 - spec["hand"]["wrist_row"]) / spec["hand"]["px_per_mm"]
    files = {}
    key = ob.data.shape_keys.key_blocks["fist"]
    for name, vw in VIEWS.items():
        pose_grip(arm, fist_grip(spec) if vw["fist"] else None)
        key.value = 1.0 if vw["fist"] else 0.0
        f = out / "renders" / f"{name}.png"
        shoot(sc, cam, sp, vw, [centre_u if not name.endswith("3q") else 95.0, 0.0, 0.0], f)
        files[name] = f
    key.value = 0.0
    pose_grip(arm, None)
    return compare(out, files, concept, spec)


def fist_grid(out: Path, hand: Hand, arm, ob, sp: Space, spec: dict, variants: list, right_n: int, samples: int) -> list:
    """A variant grid of fists (the curls and the thumb per variant), each with its own corrective morph, shot from
    the thumb's side, the back and three-quarters behind (as the player sees a punch): grid.png, a row per variant."""
    sc, cam = stage(ob, samples)
    d = out / "grid"
    d.mkdir(parents=True, exist_ok=True)
    key = ob.data.shape_keys.key_blocks["fist"]
    rows = []
    for k, var in enumerate(variants):
        if "curl" in var:
            spec["fist"]["curl_deg"] = var["curl"]
        if "target" in var:
            spec["fist"]["thumb_target"] = var["target"]
        if "thumb" in var:
            spec["fist"]["thumb"] = dict(var["thumb"])
        else:
            var["thumb_fit"] = fit_thumb(hand, arm, sp, spec)
        var["morph"] = corrective(hand, arm, ob, sp, right_n, spec)
        pose_grip(arm, fist_grip(spec))
        key.value = 1.0
        files = []
        for vn in ("fist_side", "fist_3q", "fist_fp"):
            f = d / f"{k:02d}_{vn}.png"
            vw = dict(VIEWS[vn])
            shoot(sc, cam, sp, vw, [100.0, 0.0, 0.0], f, (320, 320), 0.24)
            files.append(f)
        key.value = 0.0
        pose_grip(arm, None)
        rows.append(files)
        log(f"grid {k} {var}")
    tiles = []
    for files in rows:
        ims = []
        for f in files:
            im = bpy.data.images.load(str(f))
            px = np.array(im.pixels[:], np.float32).reshape(320, 320, 4)
            a = px[..., 3:4]
            px[..., :3] = px[..., :3] * a + 0.5 * (1 - a)
            px[..., 3] = 1.0
            px[:, :2] = 0.2
            ims.append(px)
        tiles.append(np.concatenate(ims, 1))
    sheet = np.concatenate(tiles[::-1], 0)   # Blender's rows start at the bottom: the first variant on top
    sheet[::320] = 0.2
    img = bpy.data.images.new("grid", sheet.shape[1], sheet.shape[0])
    img.pixels = sheet.ravel()
    img.filepath_raw = str(d / "grid.png")
    img.file_format = "PNG"
    img.save()
    return variants


def compare(out: Path, files: dict, concept: Path, spec: dict) -> dict:
    """The four renders placed on the concept's frame at its scale (compare.png: the concept above, the build below,
    and an overlay row: the concept's outline in red over the build), and per view the silhouettes' overlap."""
    cim = bpy.data.images.load(str(concept))
    W, H = cim.size
    con = np.array(cim.pixels[:], np.float32).reshape(H, W, 4)[::-1]   # top row first
    cmask = (con[..., 1] - con[..., 0]) > 0.12
    build = np.zeros_like(con)
    build[..., :3] = con[0, 0, :3]
    build[..., 3] = 1.0
    bmask = np.zeros((H, W), bool)
    stats = {}
    first_row = 120
    for i, (name, f) in enumerate(list(files.items())[:4]):
        im = bpy.data.images.load(str(f))
        w, h = im.size
        px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)[::-1]
        bpy.data.images.remove(im)
        if VIEWS[name]["mirror"]:
            px = px[:, ::-1]
        x0 = int(spec["hand"]["centre_col"][i]) - w // 2
        a0, a1 = max(0, x0), min(W, x0 + w)
        sub = px[:, a0 - x0:a1 - x0]
        al = sub[..., 3:4]
        build[:, a0:a1, :3] = sub[..., :3] * al + build[:, a0:a1, :3] * (1 - al)
        bmask[:, a0:a1] |= sub[..., 3] > 0.5
        pc = cmask[first_row:, a0:a1]
        pb = bmask[first_row:, a0:a1]
        inter, union = (pc & pb).sum(), (pc | pb).sum()
        stats[name] = {"iou": round(float(inter / max(union, 1)), 3), "concept_px": int(pc.sum()), "build_px": int(pb.sum())}
    edge = cmask ^ np.roll(cmask, 1, 0) | cmask ^ np.roll(cmask, 1, 1)
    over = build.copy()
    over[edge, :3] = (0.9, 0.1, 0.1)
    sheet = np.concatenate([con, build, over], 0)
    img = bpy.data.images.new("compare", W, H * 3, alpha=True)
    img.pixels = sheet[::-1].ravel()
    img.filepath_raw = str(out / "renders" / "compare.png")
    img.file_format = "PNG"
    img.save()
    return stats


# -------------------------------------------------------------------------------------------------- main
def main(argv) -> None:
    ap = argparse.ArgumentParser(prog="fp_hand_model.py")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--low-mm", type=float, default=3.0)
    ap.add_argument("--high-mm", type=float, default=0.7)
    ap.add_argument("--tex", type=int, default=2048)
    ap.add_argument("--no-bake", action="store_true")
    ap.add_argument("--renders", action="store_true")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--fist-grid", default="", help="a JSON list of fist variants: render grid/grid.png and stop")
    a = ap.parse_args(argv)
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    spec = tomllib.loads(SPEC.read_text(encoding="utf-8"))
    hand = Hand(spec)
    stats = {"spec": str(SPEC.relative_to(ROOT)).replace("\\", "/")}
    bpy.ops.wm.open_mainfile(filepath=str(raw / spec["hand"]["character"]))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = bpy.data.objects["axolotl_char"]
    base = char_skin(body, arm)
    stats["skin_base_srgb"] = base
    for name in ("axolotl_char", "body_removed", "garment", "shoes"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    sp = Space(arm)
    log("rig read")
    # the low mesh
    h = a.low_mm
    lo = [-float(spec["hand"]["forearm_len_mm"]) - float(spec["hand"]["upper_stub_mm"]) - 50.0, -110.0, -55.0]
    hi = [222.0, 110.0, 55.0]
    F = grid_eval(hand.sdf, lo, hi, h)
    v, f = surface_nets(F, lo, h)
    v = project(v, hand.sdf, 4)
    v = relax(v, f, hand.sdf, 6)
    E = edges_of(f)
    stats["low"] = {"verts": len(v), "quads": len(f), "tris": 2 * len(f), "euler": int(len(v) - len(E) + len(f))}
    log(f"low surface {stats['low']}")
    low = make_mesh("fp_arm_R", v, f)
    bpy.ops.object.select_all(action="DESELECT")
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    low.data.materials.append(skin_material(base))
    if not a.no_bake:
        col_img, nrm_img, bst = bake_maps(hand, low, out, a.tex, a.high_mm, base)
        stats["bake"] = bst
        low.data.materials.clear()
        low.data.materials.append(skin_material(base, col_img, nrm_img, float(spec["skin"]["roughness"])))
    # weights (rest, hand space)
    names, order, top = weights(hand, v)
    top_bone = [names[order[i, 0]] for i in range(len(v))]
    groups = {}
    for j, n in enumerate(names):
        groups[n] = low.vertex_groups.new(name="Right" + n)
    for i in range(len(v)):
        for k in range(4):
            if top[i, k] > 0:
                groups[names[order[i, k]]].add([i], float(top[i, k]), "REPLACE")
    # into the armature's space; the left arm the mirror
    low.data.transform(sp.M)
    left = low.copy()
    left.data = low.data.copy()
    bpy.context.scene.collection.objects.link(left)
    left.data.transform(Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0)))
    left.data.flip_normals()
    for g in left.vertex_groups:
        g.name = "Left" + g.name[len("Right"):]
    right_n = len(low.data.vertices)
    bpy.ops.object.select_all(action="DESELECT")
    low.select_set(True)
    left.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.join()
    ob = low
    ob.name = ob.data.name = "fp_arms"
    set_bones(arm, hand, sp)
    ob.parent = arm
    ob.matrix_parent_inverse = Matrix.Identity(4)
    mod = ob.modifiers.new("rig", "ARMATURE")
    mod.object = arm
    ob.shape_key_add(name="Basis")
    ob.shape_key_add(name="fist", from_mix=False)
    if a.fist_grid:
        variants = json.loads(Path(a.fist_grid).read_text(encoding="utf-8"))
        res = fist_grid(out, hand, arm, ob, sp, spec, variants, right_n, a.samples)
        (out / "grid" / "grid.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        return
    if spec["fist"]["thumb"].get("fit", True):
        stats["fist_thumb"] = fit_thumb(hand, arm, sp, spec)
        log(f"thumb fitted {stats['fist_thumb']}")
    stats["fist_morph"] = corrective(hand, arm, ob, sp, right_n, spec)
    stats["fist_grip"] = fist_grip(spec)
    log(f"fist morph {stats['fist_morph']}")
    # the spec's sizes on the build: open (rest) and the fist (posed, morphed)
    m = {"open": measure(hand, v, top_bone, spec, "open")}
    pose_grip(arm, fist_grip(spec))
    ob.data.shape_keys.key_blocks["fist"].value = 1.0
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    pf = np.array([x.co[:] for x in me.vertices[:right_n]])
    ev.to_mesh_clear()
    ob.data.shape_keys.key_blocks["fist"].value = 0.0
    pose_grip(arm, None)
    pf = pf @ sp.npi[:3, :3].T + sp.npi[:3, 3]
    hp = pf[pf[:, 0] > 0]
    fs = spec["fist"]
    m["fist"] = {"width": [fs["width"], round(float(np.ptp(hp[:, 1])), 1)],
                 "thumb_low_u": [fs["thumb_low_u"], round(float(hp[:, 0].max()), 1)],
                 "depth": [fs["depth"], round(float(np.ptp(hp[:, 2])), 1)]}
    fingers_only = pf[[(not b.startswith("Thumb")) and b not in ("Hand", "LowerArm", "UpperArm") for b in top_bone]]
    m["fist"]["length"] = [fs["length"], round(float(fingers_only[:, 0].max()), 1)]
    stats["measured"] = m
    stats["off_spec"] = check(m, spec)
    stats["tris_per_arm"] = 2 * len(f)
    if a.renders:
        stats["views"] = renders(out, arm, ob, sp, spec, raw / spec["hand"]["concept"], a.samples)
        log(f"renders {stats['views']}")
        for o in list(bpy.data.objects):
            if o.type in ("CAMERA", "LIGHT"):
                bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "fp_hand_char.blend"), compress=True)
    (out / "model.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print("FP_HAND " + json.dumps({k: stats[k] for k in ("low", "off_spec", "tris_per_arm")}))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
