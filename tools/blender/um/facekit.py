"""Scripted face parts: eyes, mouths and brows, built on the surface of a bald head.

Everything is built in world space while the rig is in its rest pose at the origin, then stored in the head's local
space as its own mesh object, weighted 100 % to the Head bone and deformed by the same Armature modifier.
The face looks toward -Y; +X is the character's left.

Ported unchanged from the final character test's facekit.py (art #17); the face kit task (art #21) owns its styles.
"""
import math
import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

FWD = Vector((0.0, -1.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))

# The styles eyes(), brows() and mouth() know; a recipe naming another one is refused before anything is built.
EYE_STYLES = ("googly", "dots", "sleepy", "cartoon")
MOUTH_STYLES = ("o", "smile", "grin", "smirk")


def material(name, rgb, rough=1.0):
    """Flat colour; decals get roughness 1 so Workbench adds no specular sheen, eyes keep a little gloss."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    m.roughness = rough
    m.metallic = 0.0
    return m


class Surface:
    """Ray casts against the head in world space (rest pose)."""

    def __init__(self, head):
        mw = head.matrix_world
        me = head.data
        verts = [mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        self.bvh = BVHTree.FromPolygons(verts, polys)

    def hit(self, x, z):
        loc, nrm, _, _ = self.bvh.ray_cast(Vector((x, -2.0, z)), Vector((0.0, 1.0, 0.0)))
        if loc is None:
            raise RuntimeError("no face surface at x=%.3f z=%.3f" % (x, z))
        if nrm.dot(FWD) < 0:
            nrm = -nrm
        return loc, nrm

    def frame(self, x, z, blend=0.5):
        """Surface point and an orthonormal frame (right, up, out) with out between the normal and -Y."""
        p, n = self.hit(x, z)
        out = (n * blend + FWD * (1.0 - blend)).normalized()
        right = UP.cross(out).normalized()  # +X when out = -Y
        up = out.cross(right).normalized()
        if up.z < 0:
            up = -up
        return p, right, up, out


class Builder:
    """Accumulates geometry with per-face material slots."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def slot(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def ellipsoid(self, c, right, up, out, rx, ry, rd, mat, seg=14, rings=6, theta=(0.0, 2 * math.pi), phi=(0.0, math.pi)):
        """phi = 0 is the pole facing out of the face; theta runs around it (0 = right, pi/2 = up)."""
        mi = self.slot(mat)
        bm = self.bm
        full = abs(theta[1] - theta[0] - 2 * math.pi) < 1e-6
        nt = seg if full else seg + 1
        grid = []
        for r in range(rings + 1):
            ph = phi[0] + (phi[1] - phi[0]) * r / rings
            row = []
            if r == 0 and phi[0] == 0.0:
                row = [bm.verts.new(c + out * rd)] * nt
            else:
                for s in range(nt):
                    th = theta[0] + (theta[1] - theta[0]) * s / (seg)
                    d = (right * (rx * math.cos(th)) + up * (ry * math.sin(th))) * math.sin(ph) + out * (rd * math.cos(ph))
                    row.append(bm.verts.new(c + d))
            grid.append(row)
        for r in range(rings):
            for s in range(seg):
                a, b = grid[r][s], grid[r][(s + 1) % nt]
                cc, dd = grid[r + 1][(s + 1) % nt], grid[r + 1][s]
                vs = [a, dd, cc, b]
                uniq = []
                for v in vs:
                    if v not in uniq:
                        uniq.append(v)
                if len(uniq) >= 3:
                    f = bm.faces.new(uniq)
                    f.material_index = mi
                    f.normal_update()
                    if f.normal.dot(f.calc_center_median() - c) < 0:  # outward from the ellipsoid centre
                        f.normal_flip()
        return self

    def drape_patch(self, surf, rows, lift, mat):
        """rows: a grid (list of rows) of (x, z) world points; each is projected onto the face and lifted off it."""
        mi = self.slot(mat)
        g, outs = [], []
        for row in rows:
            out = []
            for (x, z) in row:
                p, right, up, o = surf.frame(x, z, blend=0.6)
                out.append(self.bm.verts.new(p + o * lift))
                outs.append(o)
            g.append(out)
        away = sum(outs, Vector()).normalized()
        for r in range(len(g) - 1):
            for s in range(len(g[r]) - 1):
                vs = []
                for v in (g[r][s], g[r + 1][s], g[r + 1][s + 1], g[r][s + 1]):
                    if v not in vs:
                        vs.append(v)
                if len(vs) < 3:
                    continue
                f = self.bm.faces.new(vs)
                f.material_index = mi
                f.normal_update()
                if f.normal.dot(away) < 0:  # decals face away from the head
                    f.normal_flip()
        return self

    def ribbon(self, surf, pts, widths, lift, mat, across=3):
        """A strip along pts (x, z) with half-widths, draped on the face."""
        n = len(pts)
        rows = []
        for k in range(across):
            t = -1.0 + 2.0 * k / (across - 1)
            row = []
            for i in range(n):
                a = Vector(pts[max(i - 1, 0)]); b = Vector(pts[min(i + 1, n - 1)])
                tan = (b - a).normalized()
                nrm = Vector((-tan.y, tan.x))
                p = Vector(pts[i]) + nrm * (widths[i] * t)
                row.append((p.x, p.y))
            rows.append(row)
        return self.drape_patch(surf, rows, lift, mat)

    def lens(self, surf, cx, cz, xs, top, bottom, lift, mat, steps=4):
        """A filled region between top(x) and bottom(x) curves, offsets from (cx, cz), draped."""
        rows = []
        for k in range(steps + 1):
            t = k / steps
            rows.append([(cx + x, cz + top(x) * (1 - t) + bottom(x) * t) for x in xs])
        return self.drape_patch(surf, rows, lift, mat)

    def disc(self, surf, cx, cz, rx, rz, lift, mat, seg=20, rings=3, lower_only=False):
        rows = []
        th0, th1 = (math.pi, 2 * math.pi) if lower_only else (0.0, 2 * math.pi)
        for k in range(rings + 1):
            t = k / rings
            rows.append([(cx + rx * t * math.cos(th0 + (th1 - th0) * s / seg), cz + rz * t * math.sin(th0 + (th1 - th0) * s / seg)) for s in range(seg + 1)])
        return self.drape_patch(surf, rows, lift, mat)

    def to_object(self, name, head, arm, bone="Head", smooth=True):
        bm = self.bm
        inv = head.matrix_world.inverted()
        for v in bm.verts:
            v.co = inv @ v.co
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me); bm.free()
        for m in self.mats:
            me.materials.append(m)
        for p in me.polygons:
            p.use_smooth = smooth  # flat matches the pack's faceted meshes (recipes "face_shading")
        ob = bpy.data.objects.new(name, me)
        head.users_collection[0].objects.link(ob)
        ob.parent = arm
        ob.matrix_parent_inverse = head.matrix_parent_inverse.copy()
        ob.matrix_basis = head.matrix_basis.copy()
        vg = ob.vertex_groups.new(name=bone)
        vg.add(list(range(len(me.vertices))), 1.0, "REPLACE")
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        return ob


# ----------------------------------------------------------------------------------------------- eyes
def eyes(surf, centers, style, colors, skin):
    """centers: {"L": Vector, "R": Vector} world eye centres taken from the source head's eye faces."""
    b = Builder()
    white = material("eye_white", (0.92, 0.92, 0.9), 0.3)
    black = material("eye_black", (0.01, 0.01, 0.012), 0.3)
    iris = material("iris_" + style, colors.get("iris", (0.1, 0.25, 0.6)), 0.3)
    lash = material("lash_" + style, colors.get("lash", (0.02, 0.012, 0.01)))
    for side, c in centers.items():
        sx = 1.0 if side == "L" else -1.0  # +X outward for the left eye
        p, right, up, out = surf.frame(c.x, c.z, blend=0.35)
        if style == "googly":
            r = 0.0185
            cc = p + out * 0.002
            b.ellipsoid(cc, right, up, out, r, r, 0.012, white)
            pc = cc + out * 0.0118 + up * -0.004 + right * (-0.0025 * sx)
            b.ellipsoid(pc, right, up, out, 0.0085, 0.0085, 0.0032, black)
            b.ellipsoid(pc + out * 0.0024 + up * 0.0034 + right * (0.0025 * sx), right, up, out, 0.0022, 0.0022, 0.001, white, seg=10, rings=4)
        elif style == "dots":
            cc = p + out * 0.0006
            b.ellipsoid(cc, right, up, out, 0.0074, 0.0104, 0.0036, black)
            b.ellipsoid(cc + out * 0.0031 + up * 0.0036 + right * (0.0024 * sx), right, up, out, 0.0029, 0.0029, 0.001, white, seg=10, rings=4)
        elif style == "sleepy":
            cc = p + out * 0.0008
            rx, ry, rd = 0.0150, 0.0098, 0.0050
            b.ellipsoid(cc, right, up, out, rx, ry, rd, white)
            ic = cc + out * (rd - 0.0012) + up * -0.0008
            b.ellipsoid(ic, right, up, out, 0.0068, 0.0068, 0.0018, iris)
            b.ellipsoid(ic + out * 0.0012, right, up, out, 0.003, 0.003, 0.0012, black, seg=10, rings=4)
            # heavy upper lid in skin colour covering the upper ~45 % of the eye
            lc = cc + up * 0.0006
            b.ellipsoid(lc, right, up, out, rx * 1.1, ry * 1.18, rd * 1.2, skin, theta=(0.0, math.pi))
            # lash line along the lid edge and a small outer flick
            b.ellipsoid(lc + out * 0.0004, right, up, out, rx * 1.16, 0.0016, rd * 1.3, lash)
            fc = lc + right * (rx * 1.15 * sx) + up * 0.0018
            b.ellipsoid(fc, right * sx, up, out, 0.0042, 0.0012, 0.0025, lash, seg=10, rings=4)
        elif style == "cartoon":
            cc = p + out * 0.0008
            rx, ry, rd = 0.0128, 0.0168, 0.0058
            b.ellipsoid(cc, right, up, out, rx, ry, rd, white)
            ic = cc + out * (rd - 0.0014) + up * -0.0016
            b.ellipsoid(ic, right, up, out, 0.0084, 0.0098, 0.0026, iris)
            b.ellipsoid(ic + out * 0.0014, right, up, out, 0.0044, 0.0052, 0.0016, black, seg=10, rings=4)
            b.ellipsoid(ic + out * 0.0032 + up * 0.0042 + right * (0.0032 * sx), right, up, out, 0.0024, 0.0024, 0.0008, white, seg=10, rings=4)
            # upper lash band hugging the top of the eye, with an outer flick
            b.ellipsoid(cc + out * 0.0003, right, up, out, rx * 1.12, ry * 1.1, rd * 1.12, lash, theta=(math.radians(18), math.radians(162)), phi=(math.radians(58), math.radians(100)))
            fc = cc + right * (rx * 1.02 * sx) + up * (ry * 0.62)
            b.ellipsoid(fc, (right * sx + up * 0.6).normalized(), up, out, 0.0048, 0.0013, 0.003, lash, seg=10, rings=4)
        else:
            raise ValueError("unknown eye style " + style)
    return b


# ----------------------------------------------------------------------------------------------- brows
BROWS = {
    # x runs from the inner end (negative) to the outer end, relative to the eye centre; z above it; half-widths
    "raised_thick": dict(pts=[(-0.016, 0.031), (-0.006, 0.0355), (0.006, 0.0375), (0.018, 0.033)], w=[0.0040, 0.0052, 0.0050, 0.0030]),
    "bushy_low": dict(pts=[(-0.017, 0.0205), (-0.006, 0.0225), (0.006, 0.0235), (0.018, 0.0200)], w=[0.0055, 0.0062, 0.0060, 0.0040]),
    "thin_arch": dict(pts=[(-0.013, 0.0185), (-0.004, 0.0225), (0.006, 0.0245), (0.016, 0.0205)], w=[0.0021, 0.0024, 0.0020, 0.0011]),
    "soft_arch": dict(pts=[(-0.014, 0.0235), (-0.004, 0.0275), (0.007, 0.0290), (0.017, 0.0255)], w=[0.0026, 0.0030, 0.0027, 0.0015]),
}


def brows(surf, centers, style, rgb):
    b = Builder()
    mat = material("brow_" + style, rgb)
    spec = BROWS[style]
    for side, c in centers.items():
        sx = 1.0 if side == "L" else -1.0
        dense, wd = [], []
        pts = spec["pts"]; ws = spec["w"]
        for i in range(len(pts) - 1):
            for k in range(4):
                t = k / 4
                x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
                z = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t
                dense.append((c.x + sx * x, c.z + z)); wd.append(ws[i] + (ws[i + 1] - ws[i]) * t)
        dense.append((c.x + sx * pts[-1][0], c.z + pts[-1][1])); wd.append(ws[-1])
        b.ribbon(surf, dense, wd, 0.0012, mat)
    return b


# ----------------------------------------------------------------------------------------------- mouths
def mouth(surf, cx, cz, style, colors):
    b = Builder()
    dark = material("mouth_dark", (0.07, 0.012, 0.015))
    lip = material("lip_" + style, colors.get("lip", (0.32, 0.07, 0.07)))
    tongue = material("tongue", (0.55, 0.12, 0.13))
    teeth = material("teeth", (0.95, 0.95, 0.92))
    n = 17
    if style == "o":
        b.disc(surf, cx, cz, 0.0115, 0.0145, 0.0011, lip)
        b.disc(surf, cx, cz, 0.0082, 0.0112, 0.0016, dark)
        b.disc(surf, cx, cz - 0.0035, 0.0058, 0.0050, 0.0020, tongue, lower_only=True)
    elif style == "smile":
        w = 0.0205
        xs = [-w + 2 * w * i / (n - 1) for i in range(n)]
        top = lambda x: 0.0075 * (x / w) ** 2 + 0.0008
        bot = lambda x: 0.0075 * (x / w) ** 2 - 0.0060 * (1 - (x / w) ** 2) ** 0.8
        b.lens(surf, cx, cz, xs, top, bot, 0.0011, lip)
        mid = lambda x: 0.0075 * (x / w) ** 2 - 0.0016 * (1 - (x / w) ** 2)
        b.lens(surf, cx, cz, [x * 0.92 for x in xs], mid, lambda x: mid(x) - 0.0009 * (1 - (x / w) ** 2) ** 0.5, 0.0016, dark, steps=1)
    elif style == "grin":
        w = 0.0215
        xs = [-w + 2 * w * i / (n - 1) for i in range(n)]
        top = lambda x: 0.0045 * (x / w) ** 2 + 0.0035
        bot = lambda x: 0.0045 * (x / w) ** 2 + 0.0035 - 0.0155 * (1 - (x / w) ** 2) ** 0.75
        b.lens(surf, cx, cz, xs, top, bot, 0.0011, dark)
        tw = w * 0.86
        txs = [-tw + 2 * tw * i / (n - 1) for i in range(n)]
        b.lens(surf, cx, cz, txs, lambda x: top(x) - 0.0007, lambda x: top(x) - 0.0007 - 0.0042 * (1 - (x / w) ** 2) ** 0.3, 0.0017, teeth)
        b.disc(surf, cx, cz - 0.0080, 0.0082, 0.0034, 0.0016, tongue)
    elif style == "smirk":
        x0, x1 = -0.0175, 0.0165
        pts, ws = [], []
        for i in range(n):
            t = i / (n - 1)
            x = x0 + (x1 - x0) * t
            pts.append((cx + x, cz + 0.0062 * t ** 2.4 - 0.0008 * math.sin(math.pi * t)))
            ws.append(0.0016 + 0.0016 * math.sin(math.pi * min(1.0, t * 1.15)))
        b.ribbon(surf, pts, ws, 0.0012, lip)
        # a little dimple tick at the raised corner
        b.ribbon(surf, [(cx + x1 + 0.0012, cz + 0.0078), (cx + x1 + 0.0026, cz + 0.0050), (cx + x1 + 0.0024, cz + 0.0026)], [0.0005, 0.0008, 0.0004], 0.0012, lip)
    else:
        raise ValueError("unknown mouth style " + style)
    return b
