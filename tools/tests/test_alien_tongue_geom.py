"""M14 (art #196): the tongue mouth mt2's tongue and teeth (tools/blender/alien_tongue_geom.py, plain Python): the
spine wraps over the lip and hangs, the section and the round tip, the flop weight, the mesh's topology, the
teeth's places."""

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

BL = Path(__file__).resolve().parents[1] / "blender"
spec = importlib.util.spec_from_file_location("alien_tongue_geom", BL / "alien_tongue_geom.py")
TG = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TG)


def edge_counts(faces):
    edges = {}
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            k = (min(a, b), max(a, b))
            edges[k] = edges.get(k, 0) + 1
    return edges


class TongueTest(unittest.TestCase):
    def build(self, shape):
        p = TG.merged()
        sp = p["shapes"][shape]
        pts2, s_top = TG.spine2d((0.006, 0.005), p, sp)
        pts = TG.world_spine(pts2, s_top, 0.01, 0.0, 0.0, sp)
        verts, faces, flop = TG.tongue_mesh(pts, [q[2] for q in pts2], s_top, p, sp)
        return p, sp, pts2, s_top, pts, verts, faces, flop

    def test_every_shape_has_a_tongue(self):
        self.assertEqual(set(TG.TONGUE["shapes"]), {"rest", "M", "small", "A", "E", "O"})

    def test_spine_lies_on_the_roll_then_hangs(self):
        for shape in TG.TONGUE["shapes"]:
            _p, sp, pts2, _s, *_r = self.build(shape)
            self.assertAlmostEqual(pts2[0][1], 0.005 - TG.TONGUE["dip"], places=6, msg=shape)  # the root dips
            top = min(pts2, key=lambda q: abs(q[0]))
            self.assertAlmostEqual(top[1], 0.005, places=3, msg=shape)  # on the roll's top
            self.assertLess(pts2[0][0], 0.0)  # behind the roll's centre
            ss = [q[2] for q in pts2]
            self.assertTrue(all(b > a for a, b in zip(ss, ss[1:])), shape)
            for f, u, _s2 in [q for q in pts2 if q[0] >= 0.0]:  # past its top never inside the roll
                self.assertGreaterEqual((f / 0.006) ** 2 + (u / 0.005) ** 2, 1.0 - 2e-3, shape)  # chords of the sampled arc
            if sp["wrap"] >= 80:  # past the front, going down
                self.assertLess(pts2[-1][1], 0.0, shape)

    def test_section_and_tip(self):
        p = TG.merged()
        L = 0.05
        w0, _h0 = TG.profile(0.0, L, p)
        wm, hm = TG.profile(0.6 * L, L, p)
        self.assertAlmostEqual(w0, p["width"] / 2 * p["root_w"], places=6)  # a spatula: narrower at the root
        self.assertGreater(wm, w0)
        self.assertAlmostEqual(hm, p["thick"] / 2)
        self.assertAlmostEqual(TG.profile(L, L, p)[0], 0.0, places=6)  # the round tip closes

    def test_tip_plump_in_profile(self):  # M14b (PR #251's review): no knife-thin blade
        p = TG.merged()
        L = 0.05
        tip = 0.45 * p["width"]
        at = lambda q: TG.profile(L - tip + q * tip, L, p)  # noqa: E731
        self.assertGreaterEqual(at(0.8)[1], 0.35 * p["thick"])
        for k in range(1, 20):  # never below the floor before the last station, never thicker than wide
            w, h = at(k / 20)
            self.assertGreaterEqual(h, min(w, p["tip"]["floor"] * p["thick"] / 2) - 1e-9)
            self.assertLessEqual(h, w + 1e-9)
        self.assertAlmostEqual(at(1.0)[0], 0.0, places=6)  # the round tip closes
        self.assertAlmostEqual(at(1.0)[1], 0.0, places=6)
        verts = self.build("A")[-3]  # the built tongue: the second-to-last ring at least half the thickness
        K = TG.AROUND
        ring = verts[(TG.STATIONS - 1) * K:TG.STATIONS * K]
        thick = max(math.dist(ring[k], ring[K - k]) for k in range(1, K // 2))  # top to underside, beside the groove
        self.assertGreater(thick, 0.5 * p["thick"] * (1 + p["flat"]) / 2 * 0.9)

    def test_shape_width_and_teeth_per_shape(self):
        p = TG.merged()
        self.assertLess(TG.shape_params(p, "O")["width"], p["width"] * 0.85)
        self.assertEqual(TG.shape_params(p, "A")["width"], p["width"])
        t = TG.merged_teeth()
        a, r = TG.teeth_for(t, "A"), TG.teeth_for(t, "rest")
        self.assertEqual(len(a["lower"]), 2, "the sheet's A shows two lower teeth")
        self.assertEqual(r["lower"], TG.TEETH["lower"])
        self.assertNotIn("per_shape", a)

    def test_flop_weight_zero_inside_one_at_tip(self):
        *_r, verts, faces, flop = self.build("A")
        self.assertEqual(len(verts), len(flop))
        self.assertEqual(min(flop), 0.0)
        self.assertAlmostEqual(max(flop), 1.0)
        self.assertEqual(flop[0], 0.0)  # the root ring
        n = (TG.STATIONS + 1) * TG.AROUND + 2
        self.assertEqual(len(verts), n)
        self.assertEqual({i for f in faces for i in f}, set(range(n)))

    def test_closed_mesh(self):  # every edge in exactly two faces
        *_r, faces, _flop = self.build("rest")
        self.assertTrue(all(v == 2 for v in edge_counts(faces).values()))

    def test_slant_moves_the_tip_sideways(self):
        _p, sp, _pts2, _s, pts, *_r = self.build("E")
        self.assertGreater(sp["slant"], 0)
        self.assertGreater(pts[-1][0], pts[0][0] + 0.002)
        _p, sp, _pts2, _s, pts, *_r = self.build("O")
        self.assertAlmostEqual(pts[-1][0], pts[0][0], places=9)

    def test_merged_overrides_by_shape(self):
        p = TG.merged({"width": 0.03, "shapes": {"A": {"hang": 0.0}}})
        self.assertEqual(p["width"], 0.03)
        self.assertEqual(p["shapes"]["A"]["hang"], 0.0)
        self.assertEqual(p["shapes"]["A"]["wrap"], TG.TONGUE["shapes"]["A"]["wrap"])
        self.assertEqual(TG.TONGUE["width"], TG.merged()["width"])
        self.assertNotEqual(TG.TONGUE["shapes"]["A"]["hang"], 0.0)


class TeethTest(unittest.TestCase):
    def test_gappy_uneven_teeth(self):
        t = TG.merged_teeth()
        self.assertEqual(len(t["upper"]), 2)
        self.assertEqual(len(t["lower"]), 1)
        (xa, wa, _ha, _ta), (xb, wb, _hb, _tb) = t["upper"]
        self.assertGreater(xb - wb / 2 - (xa + wa / 2), 0.008, "a gap between the upper teeth")
        self.assertNotEqual(wa, wb)

    def test_boxes_hang_from_their_edges(self):
        t = TG.merged_teeth()
        boxes = TG.tooth_boxes(lambda lip, x: 0.01 if lip == "upper" else -0.01, lambda lip, x, z: 0.002, 0.02, t,
                               cx=0.001)
        self.assertEqual(len(boxes), 3)
        for b in boxes:
            top, bot = b["centre"][2] + b["h"] / 2, b["centre"][2] - b["h"] / 2
            if b["lip"] == "upper":  # tucked into the upper lip, hanging into the opening
                self.assertAlmostEqual(top, 0.01 + t["tuck"], places=6)
                self.assertLess(bot, 0.01)
            else:
                self.assertAlmostEqual(bot, -0.01 - t["tuck"], places=6)
                self.assertGreater(top, -0.01)
            self.assertLessEqual(b["visible_mm"], t["max_open"] * 20 + 1e-6)
            self.assertAlmostEqual(b["centre"][1], 0.002 + t["depth"] / 2)  # its front where edge_y says
        self.assertEqual(TG.tooth_boxes(lambda lip, x: 0.0, lambda lip, x, z: 0.0, 0.0, t), [])  # a closed mouth

    def test_tooth_mesh_closed(self):
        verts, faces = TG.tooth_mesh((0.0, 0.0, 0.0), 0.01, 0.006, 0.008, 5.0, 0.45)
        self.assertTrue(all(v == 2 for v in edge_counts(faces).values()))
        zs = [v[2] for v in verts]
        tilt = math.radians(5.0)  # a tilted rounded box: between its height and its tilted bounding box
        self.assertGreaterEqual(max(zs) - min(zs), 0.008 * math.cos(tilt) - 1e-6)
        self.assertLessEqual(max(zs) - min(zs), 0.008 * math.cos(tilt) + 0.01 * math.sin(tilt) + 1e-6)


if __name__ == "__main__":
    unittest.main()
