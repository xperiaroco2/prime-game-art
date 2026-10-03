"""Scripted face parts: eyes, mouths and brows, built on the surface of a bald head.

Everything is built in world space while the rig is in its rest pose at the origin, then stored in the head's local
space as its own mesh object, weighted 100 % to the Head bone and deformed by the same Armature modifier.
The face looks toward -Y; +X is the character's left.

Two layers. The final test's four styles (eyes(), brows(), mouth(); EYE_STYLES, BROWS, MOUTH_STYLES) are kept as
they were ported by art #17, for its recipes. The style families of the face kit (art #21, docs/faces.md) are data in
faces/styles.json: family_face() turns one family and one expression into eyes, brows and mouth Builders, from a few
part kinds (dome eyes with lids, draped decals, slab brows, a parametric mouth) shared by every family.
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


# =============================================================================================== style families
# The face kit's style families (art #21, docs/faces.md). A family (faces/styles.json, checked by
# tools/blender/faces_styles.py) is one design language: an eye kind with its sizes, depth and colours, brow strokes
# and a mouth; an expression is a few numbers (lid openness and tilt, brow raise, mouth shape) that every family
# interprets the same way. Units are metres. Eye-local coordinates are normalized: u runs outward (toward the temple)
# on both eyes, v up, and the eye's outline is the unit circle.

# Eye kinds: "dot" (a dark dome, no white), "ball" (a white dome with a pupil), "toon" (a tall white dome with a large
# iris), "almond" (an almond opening on a dome, cut by skin lids), "painted" (the almond drawn flat on the skin).
EYE_KINDS = ("dot", "ball", "toon", "almond", "painted")
EYE_SHAPES = ("ellipse", "almond")
CLOSED_STYLES = ("lid", "arc")
HAPPY_STYLES = ("lid", "arc")
LIP_STYLES = ("none", "rim", "full")
FAMILY_COLORS = ("white", "pupil", "highlight", "lash", "line", "dark", "teeth", "tongue", "dot")


def tagged_material(tag, name, rgb, rough=1.0):
    """A material named <tag>_<name> (tag: a character or a family), so two faces never share a colour by accident
    (the final test's material() reuses one per style name)."""
    return material("%s_%s" % (tag, name) if tag else name, rgb, rough)


class Dome:
    """The front of an ellipsoid centred at c with semi-axes rx along R, ry along U and rd along O; (u, v) in the unit
    disc. scale grows the ellipsoid about c (a lid over the eyeball), lift moves along O."""

    def __init__(self, c, R, U, O, rx, ry, rd):
        self.c, self.R, self.U, self.O = c, R, U, O
        self.rx, self.ry, self.rd = rx, ry, rd

    @staticmethod
    def edge(u):
        return math.sqrt(max(0.0, 1.0 - u * u))

    def point(self, u, v, scale=1.0, lift=0.0):
        w = math.sqrt(max(0.0, 1.0 - u * u - v * v))
        return self.c + self.R * (self.rx * scale * u) + self.U * (self.ry * scale * v) + self.O * (self.rd * scale * w + lift)

    def away(self, p):
        return p - self.c


class Drape:
    """Points draped on the head: (u, v) scaled by (rx, ry) from (cx, cz), u mirrored by sx so that it runs outward,
    projected onto the skin and lifted off it along the blended normal. With rx = ry = 1, u and v are metres."""

    def __init__(self, surf, cx, cz, sx=1.0, rx=1.0, ry=1.0, lift=0.0):
        self.surf, self.cx, self.cz, self.sx, self.rx, self.ry, self.lift = surf, cx, cz, sx, rx, ry, lift

    @staticmethod
    def edge(u):
        return math.sqrt(max(0.0, 1.0 - u * u))

    def point(self, u, v, scale=1.0, lift=0.0):
        p, _, _, o = self.surf.frame(self.cx + self.sx * self.rx * u * scale, self.cz + self.ry * v * scale, blend=0.6)
        return p + o * (self.lift + lift)

    @staticmethod
    def away(p):
        return FWD


def _region_grid(m, u0, u1, lo, hi, cols, rows, scale, lift, clip):
    grid = []
    for i in range(cols + 1):
        u = u0 + (u1 - u0) * i / cols
        a, b = lo(u), hi(u)
        if clip:
            e = m.edge(u)
            a, b = max(a, -e), min(b, e)
        if b < a:
            a = b = (a + b) / 2
        grid.append([m.point(u, a + (b - a) * j / rows, scale, lift) for j in range(rows + 1)])
    return grid


def _area(ps):
    a = (ps[1] - ps[0]).cross(ps[2] - ps[0]).length
    if len(ps) == 4:
        a += (ps[2] - ps[0]).cross(ps[3] - ps[0]).length
    return a / 2


class FamilyBuilder(Builder):
    """Builder plus the face kit's parametric patches: region() (a patch between two curves on a Dome or a Drape),
    blob() (an ellipse on one) and slab() (a region with a thickness and side walls)."""

    def _vert(self, cache, p):
        k = (round(p.x, 7), round(p.y, 7), round(p.z, 7))
        if k not in cache:
            cache[k] = self.bm.verts.new(p)
        return cache[k]

    def _face(self, vs, mi, outward):
        uniq = []
        for v in vs:
            if v not in uniq:
                uniq.append(v)
        if len(uniq) < 3 or _area([v.co for v in uniq]) < 1e-11:
            return 0
        try:
            f = self.bm.faces.new(uniq)
        except ValueError:  # the face exists already
            return 0
        f.material_index = mi
        f.normal_update()
        if f.normal.dot(outward(f.calc_center_median())) < 0:
            f.normal_flip()
        return 1

    def _grid_faces(self, pts, mi, away, cache):
        grid = [[self._vert(cache, p) for p in col] for col in pts]
        n = 0
        for i in range(len(grid) - 1):
            for j in range(len(grid[i]) - 1):
                n += self._face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), mi, away)
        return grid, n

    def region(self, m, u0, u1, lo, hi, mat, cols=12, rows=3, scale=1.0, lift=0.0, clip=True):
        """The patch of m between lo(u) and hi(u) for u from u0 to u1 (clipped to m's outline unless clip is False);
        degenerate quads are dropped and faces point away from the head. Returns the number of faces."""
        pts = _region_grid(m, u0, u1, lo, hi, cols, rows, scale, lift, clip)
        return self._grid_faces(pts, self.slot(mat), m.away, {})[1]

    def blob(self, m, cu, cv, ru, rv, mat, lo=None, hi=None, cols=8, rows=2, scale=1.0, lift=0.0):
        """An ellipse (centre cu, cv; radii ru, rv in m's units) on m, cut by the curves lo(u) and hi(u) if given."""
        def lo_f(u):
            d = cv - rv * math.sqrt(max(0.0, 1.0 - ((u - cu) / ru) ** 2))
            return d if lo is None else max(d, lo(u))

        def hi_f(u):
            d = cv + rv * math.sqrt(max(0.0, 1.0 - ((u - cu) / ru) ** 2))
            return d if hi is None else min(d, hi(u))
        return self.region(m, cu - ru, cu + ru, lo_f, hi_f, mat, cols, rows, scale, lift, clip=True)

    def slab(self, m, u0, u1, lo, hi, mat, thick, cols=10, rows=1, lift=0.0):
        """region() raised by thick, with side walls down to lift: a stroke with depth (a flat decal when thick is 0)."""
        mi = self.slot(mat)
        top = _region_grid(m, u0, u1, lo, hi, cols, rows, 1.0, lift + thick, False)
        top_v, n = self._grid_faces(top, mi, m.away, {})
        if thick <= 0:
            return n
        base = _region_grid(m, u0, u1, lo, hi, cols, rows, 1.0, lift, False)
        ring = [(i, 0) for i in range(cols + 1)] + [(cols, j) for j in range(1, rows + 1)]
        ring += [(i, rows) for i in range(cols - 1, -1, -1)] + [(0, j) for j in range(rows - 1, 0, -1)]
        bcache = {}
        centre = sum((p for col in top for p in col), Vector()) / sum(len(col) for col in top)
        for k in range(len(ring)):
            (i0, j0), (i1, j1) = ring[k], ring[(k + 1) % len(ring)]
            vs = (top_v[i0][j0], top_v[i1][j1], self._vert(bcache, base[i1][j1]), self._vert(bcache, base[i0][j0]))
            n += self._face(vs, mi, lambda fc: fc - centre)  # walls face outward from the stroke
        return n


def _get(params, key, side, default):
    """An expression value for one side: key_l / key_r win over key."""
    if side is not None and key + "_" + side.lower() in params:
        return params[key + "_" + side.lower()]
    return params.get(key, default)


def _lerp_poly(pts, x):
    """Piecewise-linear y at x over pts [(x, y), ...] sorted by x (held flat beyond the ends)."""
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / ((x1 - x0) or 1.0)
    return pts[-1][1]


# ----------------------------------------------------------------------------------------------- family eyes
def eye_curves(E, X, side):
    """(top0, bot0, top, bot, open): the eye's full opening and what the lids leave visible, normalized curves of u."""
    if E["shape"] == "almond":
        T, B, S = E["top"], E["bottom"], E.get("slant", 0.0)
        pt, pb = E.get("top_pow", 0.7), E.get("bottom_pow", 0.8)
        top0 = lambda u: T * max(0.0, 1.0 - u * u) ** pt + S * u  # noqa: E731
        bot0 = lambda u: -B * max(0.0, 1.0 - u * u) ** pb + S * u  # noqa: E731
    else:
        top0 = Dome.edge
        bot0 = lambda u: -Dome.edge(u)  # noqa: E731
    openv = max(0.0, min(1.0, E.get("rest_open", 1.0) * _get(X, "open", side, 1.0)))
    tilt = _get(X, "tilt", side, 0.0)
    lower = _get(X, "lower", side, 0.0)

    def top(u):
        k = max(0.0, min(1.0, openv + tilt * u))
        return bot0(u) + (top0(u) - bot0(u)) * k

    def bot(u):
        return bot0(u) + (top(u) - bot0(u)) * lower * math.sqrt(max(0.0, 1.0 - u * u))
    return top0, bot0, top, bot, openv


def _family_eye(b, surf, c, side, E, X, mats):
    sx = 1.0 if side == "L" else -1.0
    sc = _get(X, "scale", side, 1.0)
    rx, ry = E["w"] * sc, E["h"] * sc
    cx, cz = c.x + sx * E.get("dx", 0.0), c.z + E.get("dz", 0.0)
    flat = E["kind"] == "painted"
    if flat:
        m = Drape(surf, cx, cz, sx, rx, ry, lift=E.get("lift", 0.0008))
    else:
        p, right, up, out = surf.frame(cx, cz, blend=0.35)
        rd = E["depth"] * sc
        m = Dome(p + out * (E["protrude"] * sc - rd), right * sx, up, out, rx, ry, rd)
    top0, bot0, top, bot, openv = eye_curves(E, X, side)
    lid_scale = E.get("lid_scale", 1.05)
    lash_w = E.get("lash", 0.0) / ry  # normalized half-width
    lower = _get(X, "lower", side, 0.0)
    cols = E.get("cols", 12)
    edge_lo = lambda u: -Dome.edge(u)  # noqa: E731

    def band(curve, w, mat, u0=-1.0, u1=1.0, scale=1.0, lift=0.0, grow=0.5, on=None):
        """A band of half-width w (normalized) along curve, growing toward the outer end by grow."""
        wf = lambda u: w * (1.0 - grow / 2 + grow * (u - u0) / (u1 - u0))  # noqa: E731
        return b.region(on or m, u0, u1, lambda u: curve(u) - wf(u), lambda u: curve(u) + wf(u), mat, cols, 1, scale, lift, clip=False)

    arc_w = E.get("arc", 0.0012) / ry
    happy_arc = lower >= 0.3 and E.get("happy", "lid") == "arc"
    if (openv <= 0.0 and E.get("closed", "lid") == "arc") or (openv > 0.0 and happy_arc):
        # closed and happy eyes drawn as curved strokes on the skin
        if openv > 0.0:
            curve = lambda u: -0.3 + 0.62 * max(0.0, 1.0 - u * u) ** 0.8  # noqa: E731
        else:
            curve = lambda u: 0.05 - 0.42 * max(0.0, 1.0 - u * u) ** 0.8  # noqa: E731
        dm = m if flat else Drape(surf, cx, cz, sx, rx, ry, lift=E.get("arc_lift", 0.0012))
        band(curve, arc_w, mats["lash"] if E.get("lash", 0.0) > 0 else mats["line"], -1.05, 1.05, grow=0.2, on=dm)
        return {"stroke": True}
    if openv <= 0.0:  # a closed lid over the whole eye, the lash line low on it
        b.region(m, -1.0, 1.0, edge_lo, Dome.edge, mats["skin"], cols, 4, lid_scale)
        closed = lambda u: 0.5 * (top0(u) + bot0(u)) - 0.35 * max(0.0, 1.0 - u * u) ** 0.8  # noqa: E731
        band(closed, max(lash_w, arc_w) * 0.8, mats["lash"] if lash_w > 0 else mats["line"], -0.97, 0.97, lid_scale + 0.03)
        return {"closed": True}

    look = _get(X, "look", side, [0.0, 0.0])
    lu, lv = look[0] * sx, look[1]
    # the eyeball (the white, or the dark dot itself) where the lids leave it visible, with a margin under the lids
    ball = mats["dot"] if E["kind"] == "dot" else mats["white"]
    if flat:
        b.region(m, -1.0, 1.0, bot, top, ball, cols, 3)
    else:
        b.region(m, -1.0, 1.0, lambda u: max(bot0(u), bot(u) - 0.12), lambda u: min(top0(u), top(u) + 0.12), ball, cols, 4)
    # iris, pupil and highlights, cut by the lids
    iv = E.get("iris_v", 0.0) + lv
    if E.get("iris", 0.0) > 0:
        ri = E["iris"]
        b.blob(m, lu, iv, ri / rx, ri / ry, mats["iris"], bot, top, cols=10, rows=3, lift=0.0004)
    if E.get("pupil", 0.0) > 0:
        rp = E["pupil"] * X.get("pupil", 1.0)
        b.blob(m, lu, iv, rp / rx, rp / ry, mats["pupil"], bot, top, cols=10, rows=2, lift=0.0008)
    for hx, hz, hr in E.get("highlights", []):  # offsets from the iris centre: world x (+ = the character's left), up
        hu, hv = lu + hx * sx, iv + hz
        if bot(hu) + 0.05 < hv < top(hu) - 0.05:
            b.blob(m, hu, hv, hr / rx, hr / ry, mats["highlight"], bot, top, cols=6, rows=1, lift=0.0012)
    # lids: skin above and below the visible opening (3D eyes; painted eyes simply stop there)
    if not flat:
        b.region(m, -1.0, 1.0, top, Dome.edge, mats["skin"], cols, 3, lid_scale)
        b.region(m, -1.0, 1.0, edge_lo, bot, mats["skin"], cols, 2, lid_scale)
    # the lash line along the upper lid, with an outer flick
    if lash_w > 0:
        band(top, lash_w, mats["lash"], -0.98, 1.0, 1.0 if flat else lid_scale + 0.03, 0.0004 if flat else 0.0,
             grow=E.get("lash_grow", 0.8))
        fl = E.get("flick", 0.0)
        if fl > 0:
            fv, fu1 = top(0.999), 1.0 + fl / rx
            lift = (E.get("lift", 0.0008) + 0.0004) if flat else E.get("flick_lift", 0.0015)
            fm = Drape(surf, cx, cz, sx, rx, ry, lift=lift)
            taper = lambda u: lash_w * 0.9 * max(0.05, 1.0 - (u - 0.95) / (fu1 - 0.95))  # noqa: E731
            b.region(fm, 0.95, fu1, lambda u: fv + (u - 0.95) * E.get("flick_rise", 0.5) - taper(u),
                     lambda u: fv + (u - 0.95) * E.get("flick_rise", 0.5) + taper(u), mats["lash"], 4, 1, clip=False)
    return {"open": openv}


# ----------------------------------------------------------------------------------------------- family brows
def brow_line(Bw, X, side):
    """The brow's centre line [(x outward, z above the eye centre)] in this expression, and its half-widths."""
    pts = [tuple(p) for p in Bw["pts"]]
    n = len(pts)
    raise_, inner, arch = _get(X, "raise", side, 0.0), _get(X, "inner", side, 0.0), _get(X, "arch", side, 0.0)
    shaped = [(x, z + raise_ + inner * (1.0 - i / (n - 1)) + arch * math.sin(math.pi * i / (n - 1))) for i, (x, z) in enumerate(pts)]
    return shaped, [(pts[i][0], Bw["w"][i]) for i in range(n)]


def _family_brow(b, surf, c, side, Bw, X, mat):
    sx = 1.0 if side == "L" else -1.0
    shaped, widths = brow_line(Bw, X, side)
    m = Drape(surf, c.x, c.z, sx, lift=Bw.get("lift", 0.0010))
    zc = lambda u: _lerp_poly(shaped, u)  # noqa: E731
    wf = lambda u: _lerp_poly(widths, u)  # noqa: E731
    return b.slab(m, shaped[0][0], shaped[-1][0], lambda u: zc(u) - wf(u), lambda u: zc(u) + wf(u), mat,
                  Bw.get("thick", 0.0), cols=Bw.get("cols", 10), rows=1)


# ----------------------------------------------------------------------------------------------- family mouths
def _family_mouth(b, surf, mx, mz, Mf, X, mats):
    W = Mf["w"] * X.get("w", 1.0)
    mid, corner, side = X.get("mid", 0.0), X.get("corner", Mf.get("corner", 0.0)), X.get("side", 0.0)
    gap, skew, rnd = X.get("gap", 0.0), X.get("skew", 0.0), X.get("round", 0.7)
    m = Drape(surf, mx + X.get("shift", 0.0), mz + Mf.get("dz", 0.0), 1.0, lift=Mf.get("lift", 0.0010))
    cols = Mf.get("cols", 16)
    q = lambda x: max(0.0, 1.0 - (x / W) ** 2)  # noqa: E731
    M = lambda x: mid + (corner - mid) * min(1.0, (x / W) ** 2) + side * (x / W)  # noqa: E731
    lips = Mf.get("lips", "none")
    if gap <= 0.0005:
        line = Mf.get("line", 0.0012)
        e = lambda x: line * (0.35 + 0.65 * q(x) ** 0.5)  # noqa: E731
        if lips == "full":
            bow = lambda x: 1.0 - 0.3 * math.exp(-(x / (0.16 * W)) ** 2)  # noqa: E731
            b.region(m, -W, W, M, lambda x: M(x) + Mf["lip_up"] * q(x) ** 0.6 * bow(x), mats["lip"], cols, 1, clip=False)
            b.region(m, -W * 0.92, W * 0.92, lambda x: M(x) - Mf["lip_lo"] * q(x / 0.92) ** 0.5, M, mats["lip"], cols, 1, clip=False)
        b.region(m, -W, W, lambda x: M(x) - e(x), lambda x: M(x) + e(x), mats[Mf.get("line_color", "line")], cols, 1,
                 lift=0.0004, clip=False)
        return {"open": False}
    env = lambda x: q(x) ** rnd  # noqa: E731
    T = lambda x: M(x) + gap * (1 + skew) / 2 * env(x)  # noqa: E731
    Bf = lambda x: M(x) - gap * (1 - skew) / 2 * env(x)  # noqa: E731
    if lips in ("rim", "full"):
        up = Mf["lip_up"] if lips == "full" else Mf["rim"]
        lo_ = Mf["lip_lo"] if lips == "full" else Mf["rim"]
        Wr = W * 1.08
        qr = lambda x: max(0.0, 1.0 - (x / Wr) ** 2)  # noqa: E731
        Mr = lambda x: mid + (corner - mid) * min(1.0, (x / W) ** 2) + side * max(-1.0, min(1.0, x / W))  # noqa: E731
        Tr = lambda x: Mr(x) + gap * (1 + skew) / 2 * env(x) + up * (0.35 + 0.65 * qr(x) ** 0.5) * qr(x) ** 0.3  # noqa: E731
        Br = lambda x: Mr(x) - gap * (1 - skew) / 2 * env(x) - lo_ * (0.35 + 0.65 * qr(x) ** 0.5) * qr(x) ** 0.3  # noqa: E731
        b.region(m, -Wr, Wr, Br, Tr, mats["lip"], cols, 2, clip=False)
    b.region(m, -W, W, Bf, T, mats["dark"], cols, 2, lift=0.0004, clip=False)
    if Mf.get("teeth", 0.0) > 0 and X.get("teeth", gap >= 0.004):
        th = Mf["teeth"]
        b.region(m, -W * 0.8, W * 0.8, lambda x: max(Bf(x), T(x) - th * q(x) ** 0.3), lambda x: T(x) - 0.0003, mats["teeth"], cols, 1,
                 lift=0.0008, clip=False)
    if Mf.get("tongue", False) and gap >= 0.006:
        b.region(m, -W * 0.55, W * 0.55, lambda x: Bf(x) + 0.0003,
                 lambda x: min(T(x) - 0.001, Bf(x) + 0.42 * gap * q(x / 0.55) ** 0.5), mats["tongue"], cols, 1, lift=0.0007, clip=False)
    return {"open": True}


def family_materials(fam_id, fam, tag, colors, skin):
    """The materials of one face: the family's fixed colours (named after the family) and the character's own (named
    after tag): iris, brow and lip; the skin is the character's skin material (lids take its colour)."""
    fc = fam["colors"]
    mats = {n: tagged_material(fam_id, n, fc[n], 0.3 if n in ("white", "pupil", "highlight", "dot") else 1.0) for n in FAMILY_COLORS}
    mats.update({"iris": tagged_material(tag, fam_id + "_iris", colors["iris"], 0.3),
                 "brow": tagged_material(tag, fam_id + "_brow", colors["brow"]),
                 "lip": tagged_material(tag, fam_id + "_lip", colors["lip"]),
                 "skin": skin})
    return mats


def family_face(surf, eyes_at, mouth_at, fam_id, fam, expr, colors, skin, tag):
    """One family's face in one expression: {"eyes", "brows", "mouth"} FamilyBuilders (to_object() makes each a part
    weighted to the Head bone). eyes_at: {"L", "R"} world eye centres of the source head; mouth_at: (x, z) in world;
    fam: a checked family of faces/styles.json; expr: the expression merged over the shared library
    ({"eyes": {...}, "brows": {...}, "mouth": {...}}); colors: the character's "iris", "brow" and "lip" rgb."""
    mats = family_materials(fam_id, fam, tag, colors, skin)
    eyes_b, brows_b, mouth_b = FamilyBuilder(), FamilyBuilder(), FamilyBuilder()
    shapes = []
    # inset moves both eyes and their brows toward the face's midline (the pack's eye centres are set wide)
    inset = fam["eyes"].get("inset", 0.0)
    mid_x = sum(c.x for c in eyes_at.values()) / len(eyes_at)
    for side, c in sorted(eyes_at.items()):
        if inset:
            c = Vector((c.x - math.copysign(inset, c.x - mid_x), c.y, c.z))
        shapes.append(_family_eye(eyes_b, surf, c, side, fam["eyes"], expr.get("eyes", {}), mats))
        _family_brow(brows_b, surf, c, side, fam["brows"], expr.get("brows", {}), mats["brow"])
    _family_mouth(mouth_b, surf, mouth_at[0], mouth_at[1], fam["mouth"], expr.get("mouth", {}), mats)
    # decals lie on the skin (brows, mouths, painted eyes, eyes drawn as strokes); dome eyes sink into it by design
    eyes_b.decal = fam["eyes"]["kind"] == "painted" or all(sh.get("stroke") for sh in shapes)
    brows_b.decal = mouth_b.decal = True
    return {"eyes": eyes_b, "brows": brows_b, "mouth": mouth_b}


def rigid_face_skin(head, front_y, z_full, z_free, bone="Head"):
    """Gives the face's skin to the Head bone alone, so that rigid face parts (weighted 100 % to Head) cannot slide
    against it when the neck moves. The pack heads weight part of the lower face to Neck as well (up to 15 % around
    the mouth): in the pack's Run and Punch actions a rigid mouth then sinks up to 0.6 mm toward the skin.

    Every vertex in front of front_y (world y, rest pose; the face looks toward -Y) at or above z_full moves the
    weight of its other bones to bone; between z_full and z_free (below it, toward the chin) the share moved fades to
    0, so the jaw and the neck still blend as before. Returns (vertices changed, the largest weight moved)."""
    vg = head.vertex_groups
    hi = vg[bone].index
    mw = head.matrix_world
    changed, most = 0, 0.0
    for v in head.data.vertices:
        p = mw @ v.co
        if p.y > front_y or p.z <= z_free:
            continue
        s = 1.0 if p.z >= z_full else (p.z - z_free) / (z_full - z_free)
        others = [(g.group, g.weight) for g in v.groups if g.group != hi and g.weight > 0.0]
        moved = sum(w * s for _, w in others)
        if moved <= 1e-6:
            continue
        own = next((g.weight for g in v.groups if g.group == hi), 0.0)
        for gi, w in others:
            vg[gi].add([v.index], w * (1.0 - s), "REPLACE")
        vg[hi].add([v.index], own + moved, "REPLACE")
        changed += 1
        most = max(most, moved)
    return changed, most
