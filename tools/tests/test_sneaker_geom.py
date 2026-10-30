"""sneaker_geom (art #196, S1): the code-built sneaker's maths on synthetic feet, no Blender: the foot's frame, the
outline and opening, the mesh's size, closure and normals, parametric to the foot, the bend's weights, the toes' cap."""
import math
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import sneaker_geom as G  # noqa: E402


def synth_foot(scale: float = 1.0, wide: float = 1.0) -> G.Foot:
    """A chunky foot like the base body's (25 cm long, 15 cm wide, the toes 8 cm high, the ankle at 11.5 cm),
    scaled in length and height by scale and in width by wide."""
    pts = []
    L = 0.254 * scale
    for i in range(41):
        u = L * i / 40
        t = u / L
        half = (0.035 + 0.045 * math.sin(min(1, t / 0.85) * math.pi / 2) if t < 0.85
                else 0.08 * math.sqrt(max(0, 1 - ((t - 0.85) / 0.15) ** 2)))
        half *= min(1, 0.4 + t * 3) * wide
        top = (0.08 + 0.05 * math.exp(-((u / scale - 0.06) / 0.04) ** 2)) * scale
        for j in range(9):
            v = -half + 2 * half * j / 8
            for k in range(6):
                z = top * k / 5 * math.sqrt(max(0.05, 1 - (v / max(half, 1e-3)) ** 2))
                pts.append((u, v + 0.005 * wide, z))
    return G.Foot(pts, ball_u=0.2235 * scale, ankle_u=0.046 * scale, ankle_z=0.115 * scale)


def normal(sh, f):
    a, b, c = (sh.verts[i] for i in f[:3])
    return G._unit(G._cross(G._sub(b, a), G._sub(c, a)))


class FrameTest(unittest.TestCase):
    def test_frame_points_out_and_mirrors_the_right_foot(self):
        pts = [(0.11, y / 100, 0.0) for y in range(-12, 14)]
        left = G.frame((0.114, 0.09, 0.115), (0.114, -0.087, 0.026), pts)
        self.assertAlmostEqual(left.fwd[1], -1.0)
        self.assertGreater(left.out[0], 0.99)  # out: away from x = 0
        self.assertAlmostEqual(left.origin[1], 0.13, places=6)  # the hindmost point
        self.assertFalse(left.mirrored())
        right = G.frame((-0.114, 0.09, 0.115), (-0.114, -0.087, 0.026), [(-x, y, z) for x, y, z in pts])
        self.assertLess(right.out[0], -0.99)
        self.assertTrue(right.mirrored())
        q = (0.15, 0.0, 0.05)
        self.assertEqual(tuple(round(c, 9) for c in left.world(left.local(q))), q)

    def test_frame_refuses_coincident_bones(self):
        with self.assertRaises(ValueError):
            G.frame((0.1, 0.0, 0.1), (0.1, 0.0, 0.02), [(0.1, 0.0, 0.0)])


class CurveTest(unittest.TestCase):
    def test_hull_offset_and_resample(self):
        sq = [(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)]
        h = G.hull(sq)
        self.assertEqual(len(h), 4)
        self.assertGreater(G.area(h), 0)
        o = G.offset(h, 0.1)
        self.assertAlmostEqual(G.area(o), 1.44, places=6)  # corners pushed along the bisector by d / cos
        self.assertAlmostEqual(G.area(G.offset(h[::-1], 0.1)), -1.44, places=6)  # either winding grows
        r = G.resample(h, 16)
        self.assertEqual(len(r), 16)
        steps = [math.dist(r[i], r[(i + 1) % 16]) for i in range(16)]
        self.assertLess(max(steps) - min(steps), 1e-6)

    def test_resample_is_denser_at_the_ball(self):
        ring = [(math.cos(a) * 0.12 + 0.12, math.sin(a) * 0.05) for a in [2 * math.pi * i / 200 for i in range(200)]]
        r = G.resample(G.start_at_heel(ring), 40, dense_at=0.2)
        near = sum(abs(p[0] - 0.2) < 0.02 for p in r)
        far = sum(abs(p[0] - 0.08) < 0.02 for p in r)
        self.assertGreater(near, far)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.foot = synth_foot()
        cls.shoe = G.build(cls.foot)

    def test_budget_and_parts(self):
        sh = self.shoe
        self.assertTrue(1000 <= sh.tris <= 1910, sh.tris)  # E1j: at most S1's pair (2,920) plus 900 for the pair
        parts = Counter(sh.part)
        for p in ("sole", "upper", "lining", "bottom", "tongue", "eyelet", "lace"):
            self.assertGreater(parts[p], 0, p)
        self.assertEqual(sh.info["eyelets_per_side"], 5)
        self.assertEqual(len(sh.faces), len(sh.uvs))
        for f, uv in zip(sh.faces, sh.uvs):
            self.assertEqual(len(f), len(uv))
            self.assertTrue(all(-1e-9 <= c <= 1 + 1e-9 for p in uv for c in p))

    def test_fits_the_foot(self):
        sh, f = self.shoe, self.foot
        us = [q[0] for q in f.pts]
        self.assertGreater(sh.info["outline_len_m"], f.length + 0.01)  # the clearance and the toe room
        self.assertLess(sh.info["outline_len_m"], f.length + 0.03)
        # E1j2: a slimmer last than the soft foot (the dress shrinks the kept skin inside), its length kept
        k = G.Params().slim
        self.assertGreater(sh.info["outline_width_m"], k * f.width)
        self.assertLess(sh.info["outline_width_m"], k * f.width + 0.025)
        self.assertLess(sh.info["outline_width_m"], f.width)
        lo, hi = sh.info["rim_z_min_max"]
        self.assertLess(lo, f.ankle_z)  # a low top: the collar under the ankle
        self.assertGreater(min(q[0] for q in sh.verts), min(us) - 0.012)

    def test_normals_point_out(self):
        sh = self.shoe
        cnt = Counter()
        for f, part in zip(sh.faces, sh.part):
            n = normal(sh, f)
            c = [sum(sh.verts[i][k] for i in f) / len(f) for k in range(3)]
            if part == "sole":
                cnt["sole_out"] += n[0] * (c[0] - 0.12) + n[1] * c[1] > 0
                cnt["sole"] += 1
            if part == "bottom":
                cnt["down"] += n[2] < 0
                cnt["bottom"] += 1
        self.assertEqual(cnt["sole_out"], cnt["sole"])
        self.assertEqual(cnt["down"], cnt["bottom"])

    def test_shell_edges_shared_twice_but_the_lining(self):
        """The sole, the bottom and the upper are one closed skin up to the lining's lower edge: every edge of the
        shell is shared by two faces except that edge's ring."""
        sh = self.shoe
        edges = Counter()
        for f, part in zip(sh.faces, sh.part):
            if part in ("sole", "upper", "lining", "bottom"):
                for i in range(len(f)):
                    edges[tuple(sorted((f[i], f[(i + 1) % len(f)])))] += 1
        open_ = [e for e, k in edges.items() if k == 1]
        self.assertEqual(len(open_), sh.info["columns"])
        self.assertFalse([e for e, k in edges.items() if k > 2])

    def test_parametric_to_the_foot(self):
        big = G.build(synth_foot(scale=1.1, wide=1.1))
        self.assertGreater(big.info["outline_len_m"], self.shoe.info["outline_len_m"] + 0.02)
        self.assertGreater(big.info["outline_width_m"], self.shoe.info["outline_width_m"] + 0.012)
        self.assertGreater(big.info["rim_z_min_max"][1], self.shoe.info["rim_z_min_max"][1])  # the collar
        self.assertEqual(big.tris, self.shoe.tris)  # the same topology

    def test_symmetric_pair_from_merged_feet(self):
        a = synth_foot()
        b = G.merge(a, synth_foot())
        self.assertEqual(G.build(b).info["outline_len_m"], self.shoe.info["outline_len_m"])


class BendTest(unittest.TestCase):
    def test_toes_weight_blends_short_at_the_ball(self):
        self.assertEqual(G.toes_weight(0.18, 0.22, 0.025), 0.0)
        self.assertEqual(G.toes_weight(0.24, 0.22, 0.025), 1.0)
        self.assertAlmostEqual(G.toes_weight(0.22, 0.22, 0.025), 0.5)

    def test_soft_cap(self):
        self.assertEqual(G.soft_cap_deg(20, 32, 6), 20)
        self.assertLess(G.soft_cap_deg(57.5, 32, 6), 32)
        self.assertGreater(G.soft_cap_deg(57.5, 32, 6), 31.9)
        self.assertLess(G.soft_cap_deg(30, 32, 6), 30)
        self.assertGreater(G.soft_cap_deg(30, 32, 6), G.soft_cap_deg(28, 32, 6))  # monotone
        with self.assertRaises(ValueError):
            G.soft_cap_deg(10, 5, 6)

    def test_cap_quat_keeps_the_axis(self):
        a = math.radians(50) / 2
        q = (math.cos(a), math.sin(a), 0.0, 0.0)
        w, x, y, z = G.cap_quat(q, 32, 6)
        self.assertAlmostEqual(math.degrees(2 * math.acos(w)), G.soft_cap_deg(50, 32, 6), places=6)
        self.assertGreater(x, 0)
        self.assertAlmostEqual(y, 0)
        small = (math.cos(0.1), 0.0, math.sin(0.1), 0.0)
        self.assertEqual(G.cap_quat(small, 32, 6), small)


if __name__ == "__main__":
    unittest.main()


class SectionTest(unittest.TestCase):
    """E1, S1's collar shards: the collar's section comes from the foot's section points (any Foot, Toes or LowerLeg
    weight low on the leg) while the outline keeps the foot's own points."""

    def test_the_collar_takes_the_section_points(self):
        foot = synth_foot()
        sh0 = G.build(foot)
        # the ankle's mostly-shin skin round the heel at collar height, a little wider and further back than the
        # foot's own points there (the heel's section from u 0, v -4.4 to 5.4 cm)
        z = G.Params().heel_collar * foot.ankle_z
        ring = [(0.055 + 0.047 * math.cos(t / 16 * math.pi), 0.005 + 0.04 * math.sin(t / 16 * math.pi), z + dz)
                for t in range(32) for dz in (-0.004, 0.0, 0.008)]
        wide = G.Foot(foot.pts, foot.ball_u, foot.ankle_u, foot.ankle_z, foot.pts + ring)
        sh1 = G.build(wide)
        self.assertEqual(len(sh0.verts), len(sh1.verts))  # the same topology
        self.assertAlmostEqual(wide.length, foot.length)  # the outline is the foot's own
        self.assertAlmostEqual(wide.width, foot.width)
        r0 = G.rim_points(foot, G.Params(), G.outline(foot, G.Params()))[0]
        r1 = G.rim_points(wide, G.Params(), G.outline(wide, G.Params()))[0]
        # round the heel (the columns behind u 6 cm) the collar moves out toward the ankle's skin, never in; it
        # stays inside the shoe's outline, which is the foot's own
        heel = [(a, b) for a, b in zip(r0, r1) if a[0] < 0.06]
        self.assertGreater(len(heel), 4)
        d = [math.hypot(b[0] - 0.055, b[1] - 0.005) - math.hypot(a[0] - 0.055, a[1] - 0.005) for a, b in heel]
        self.assertGreaterEqual(min(d), -1e-4)
        self.assertGreater(max(d), 0.002)

    def test_merge_keeps_both_sections(self):
        a, b = synth_foot(), synth_foot()
        a.sect, b.sect = [(0.0, 0.0, 0.05)], [(0.01, 0.0, 0.05)]
        self.assertEqual(G.merge(a, b).section_pts, [(0.0, 0.0, 0.05), (0.01, 0.0, 0.05)])
        self.assertEqual(synth_foot().section_pts, synth_foot().pts)


class SlimTest(unittest.TestCase):
    """E1j2: the slim last, the collar's rim inside it, the tongue's back."""

    def test_slim_scales_about_the_middle_line(self):
        pts = [(u / 100, v / 100) for u in range(0, 21) for v in (-3, 7)]  # middle line at v = 0.02
        out = G.slim(pts, 0.5)
        for (u, v), (u2, v2) in zip(pts, out):
            self.assertAlmostEqual(u, u2)
            self.assertAlmostEqual(v2 - 0.02, 0.5 * (v - 0.02))
        self.assertEqual(G.slim(pts, 1.0), pts)
        graded = G.slim(pts, 0.5, 0.05, 0.15)  # 1 behind u0, 0.5 from u1 on
        for (u, v), (u2, v2) in zip(pts, graded):
            if u <= 0.05:
                self.assertAlmostEqual(v2, v)
            if u >= 0.15:
                self.assertAlmostEqual(v2 - 0.02, 0.5 * (v - 0.02))

    def test_inside_by_pushes_only_points_too_far_out(self):
        b, nin = (0.0, 0.05), (0.0, -1.0)
        self.assertEqual(G.inside_by(b, (0.01, 0.03), nin, 0.005), (0.01, 0.03))  # 2 cm inside: kept
        q = G.inside_by(b, (0.01, 0.06), nin, 0.005)  # 1 cm outside: to 5 mm inside
        self.assertAlmostEqual(q[0], 0.01)
        self.assertAlmostEqual(q[1], 0.045)

    def test_tongue_back_behind_the_slot_and_the_shoe_keeps_its_rim_inside(self):
        f = synth_foot()
        p = G.Params()
        tb = G.tongue_back_u(f, p)
        self.assertLess(tb, G.slot_rear(f, p) - 0.012)
        self.assertGreater(tb, f.ankle_u)
        sh = G.build(f, p)
        tongue = [sh.verts[i] for fi, part in enumerate(sh.part) if part == "tongue" for i in sh.faces[fi]]
        self.assertAlmostEqual(min(q[0] for q in tongue), tb, delta=0.004)
        # the collar's rim inside the outline: the shell is no wider at the rim than at the foot line
        self.assertLessEqual(max(abs(q[1]) for q in sh.verts if q[2] > 0.06),
                             max(abs(q[1]) for q in sh.verts if q[2] < 0.03) + 1e-6)

    def test_row_ks_put_the_first_row_on_the_toe_caps_edge(self):
        p = G.Params()
        b, o = (0.25, 0.0), (0.22, 0.0)
        even = G.row_ks(b, o, 0.04, 0.08, p, 0.0)
        self.assertEqual(even, [j / p.upper_rows for j in range(1, p.upper_rows + 1)])
        ks = G.row_ks(b, o, 0.04, 0.08, p, 0.02)
        a = G._ring_point(b, o, 0.04, 0.08, 0.0, p)
        pts = [G._ring_point(b, o, 0.04, 0.08, i * ks[0] / 100, p) for i in range(101)]
        arc = sum(math.dist(x, y) for x, y in zip(pts, pts[1:]))
        self.assertAlmostEqual(arc, 0.02, delta=0.001)
        self.assertEqual(ks[-1], 1.0)
        self.assertTrue(all(x < y for x, y in zip(ks, ks[1:])))
        self.assertEqual(G.row_ks(b, o, 0.04, 0.08, p, 0.0005), even)  # under a tenth of a row: the even rows
        self.assertIsNotNone(a)
