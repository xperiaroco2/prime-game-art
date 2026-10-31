"""Gate 2's plain maths (tools/blender/garment_gate2_geom.py, art #196): expressions, masks, raster, overlap, edges."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import body_drawing as D  # noqa: E402
import garment_drawing as GD  # noqa: E402
import garment_gate2 as GG  # noqa: E402
import garment_gate2_geom as G  # noqa: E402
import garment_spec as S  # noqa: E402

SPEC = Path(__file__).resolve().parents[2] / "specs" / "dungarees_dims.toml"

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def square(w, h, x0, y0, x1, y1):
    m = bytearray(w * h)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            m[y * w + x] = 1
    return m


class ResolveTest(unittest.TestCase):
    dims = {"bib_top_z": {"cm": 119.95}, "waistband_h": {"cm": 4.0}, "waistband_top_z": {"cm": 99.82}}
    lm = {"crotch": 70.8, "waist": 100.5}

    def test_build_first_then_spec_then_landmark(self):
        build = {"waistband_top_z": {"cm": 93.3}, "waistband_h": {"cm": None}}
        self.assertAlmostEqual(G.resolve("waistband_top_z+1", build, self.dims, self.lm), 94.3)
        self.assertAlmostEqual(G.resolve("waistband_top_z-waistband_h", build, self.dims, self.lm), 89.3)
        self.assertAlmostEqual(G.resolve("spec:waistband_top_z - 1", build, self.dims, self.lm), 98.82)
        self.assertAlmostEqual(G.resolve("crotch-3", {}, self.dims, self.lm), 67.8)
        self.assertEqual(G.resolve(12, {}, self.dims, self.lm), 12.0)

    def test_unknown_name(self):
        with self.assertRaises(ValueError):
            G.resolve("nope+1", {}, self.dims, self.lm)


class MaskTest(unittest.TestCase):
    def test_opening_drops_thin_stripes_keeps_blocks(self):
        w, h = 20, 30
        m = square(w, h, 2, 2, 17, 15)                      # a block 14 rows high
        for y in (20, 24):                                   # stripes 1 row high
            for x in range(w):
                m[y * w + x] = 1
        o = G.opening(m, w, h, 0, 3)
        self.assertEqual(sum(o[20 * w:25 * w]), 0)
        self.assertEqual(sum(o), sum(square(w, h, 2, 2, 17, 15)))

    def test_closing_and_fill_holes(self):
        w, h = 20, 20
        m = square(w, h, 3, 3, 16, 16)
        m[10 * w + 10] = 0
        m[8 * w + 5] = 0
        self.assertEqual(sum(G.fill_holes(m, w, h)), 14 * 14)
        gap = square(w, h, 2, 2, 8, 17)
        gap = bytearray(a | b for a, b in zip(gap, square(w, h, 10, 2, 17, 17)))   # a 1-px gap at x 9
        self.assertEqual(G.closing(gap, w, h, 1, 0)[10 * w + 9], 1)

    def test_colour_rule_and_keep_large(self):
        denim, teal, grey, navy = (45, 60, 100), (60, 180, 170), (200, 200, 205), (40, 45, 95)
        rows = [[denim, teal, grey, navy]]
        w, h, m = G.colour_mask(rows, [0, 0, 4, 1], {"b_minus_r": 15, "b_minus_g": 6, "max": 215})
        self.assertEqual(list(m), [1, 0, 0, 1])
        big = square(10, 10, 0, 0, 5, 5)
        big[9 * 10 + 9] = 1
        self.assertEqual(sum(G.keep_large(big, 10, 10, 0.1)), 36)


class RasterTest(unittest.TestCase):
    def test_square_area(self):
        tris = [((2, 2), (12, 2), (12, 12)), ((2, 2), (12, 12), (2, 12))]
        self.assertEqual(sum(G.raster(tris, 20, 20)), 100)

    def test_depth_keeps_the_nearest(self):
        w = h = 10
        depth, owner = [1e9] * (w * h), bytearray(w * h)
        flat = [((0, 0, 5.0), (10, 0, 5.0), (10, 10, 5.0)), ((0, 0, 5.0), (10, 10, 5.0), (0, 10, 5.0))]
        # a tilted square, depth 0 at the left edge to 10 at the right: nearer than the flat one left of x = 5
        tilt = [((0, 0, 0.0), (10, 0, 10.0), (10, 10, 10.0)), ((0, 0, 0.0), (10, 10, 10.0), (0, 10, 0.0))]
        G.raster(flat, w, h, depth, owner, 1)
        G.raster(tilt, w, h, depth, owner, 2)
        for y in range(h):
            self.assertEqual([owner[y * w + x] for x in range(w)], [2] * 5 + [1] * 5)
        depth2, owner2 = [1e9] * (w * h), bytearray(w * h)
        G.raster(tilt, w, h, depth2, owner2, 2)   # the other order gives the same picture
        G.raster(flat, w, h, depth2, owner2, 1)
        self.assertEqual(owner2, owner)


class OverlapTest(unittest.TestCase):
    def test_iou_and_rows(self):
        w = h = 10
        a, b = square(w, h, 0, 0, 9, 4), square(w, h, 0, 0, 9, 9)
        o = G.overlap(a, b)
        self.assertAlmostEqual(o["iou"], 0.5)
        self.assertAlmostEqual(o["b_only"], 0.5)
        self.assertAlmostEqual(G.overlap(a, b, (0, 4), w)["iou"], 1.0)

    def test_edges_and_top(self):
        w = h = 10
        m = square(w, h, 3, 2, 6, 8)
        self.assertEqual(G.edges(m, w, h, 5, 0, 9), (3, 6))
        self.assertIsNone(G.edges(m, w, h, 9, 0, 9))
        self.assertEqual(G.top_row(m, w, h, 0, 9, 0, 9), 2)
        self.assertEqual(G.top_row(m, w, h, 0, 9, 0, 9, bottom=True), 8)

    def test_rows_to_heights(self):
        pairs = [(0.0, 945), (100.5, 440), (113.05, 372)]
        self.assertAlmostEqual(S.concept_row_to_z(pairs, 440), 100.5)
        self.assertAlmostEqual(S.concept_row_to_z(pairs, 406), (100.5 + 113.05) / 2)


class ConceptMapTest(unittest.TestCase):
    """The spec's placing on the concept (art #196, G2t3): her T-pose armpit against the concept's A-pose armpit
    skewed the band 113-125 cm (1 and 8.25 px/cm); it is left out of the mapping rows."""

    def setUp(self):
        self.spec = S.load_spec(SPEC)

    def test_unmapped_rows_left_out(self):
        pairs = S.concept_pairs(self.spec)
        self.assertNotIn(self.spec["body"]["landmarks_cm"]["armpit"], [z for z, _r in pairs])
        bad = dict(self.spec, concept=dict(self.spec["concept"], unmapped=["armpitt"]))
        with self.assertRaises(S.SpecError):
            S.concept_pairs(bad)

    def test_no_skewed_band(self):
        pairs = S.concept_pairs(self.spec)
        k = sorted((r0 - r1) / (z1 - z0) for (z0, r0), (z1, r1) in zip(pairs, pairs[1:]))
        med = k[len(k) // 2]
        for v in k:
            self.assertTrue(0.6 * med <= v <= 1.6 * med, (v, med))

    def test_bib_top_on_the_concepts(self):
        row = GD.concept_map(self.spec, "front")(0, self.spec["dims"]["bib_top_z"]["cm"])[1]
        self.assertAlmostEqual(row, 336, delta=1.0)   # the concept's bib top
        row = GD.concept_map(self.spec, "back")(0, self.spec["dims"]["back_top_z"]["cm"])[1]
        self.assertAlmostEqual(row, 342, delta=1.0)


class Gate2SpecTest(unittest.TestCase):
    def test_every_cross_reference_resolves(self):
        self.assertEqual(GG.check_gate2(S.load_spec(SPEC)), [])

    def test_misspelt_names_reported(self):
        spec = S.load_spec(SPEC)
        spec["gate2"]["stations"][0]["dim"] = "bib_top"
        spec["gate2"]["parts"]["bib"]["z"][1] = "bib_topz+1"
        spec["gate2"]["joins"][0]["on"] = "bibb"
        bad = " ".join(GG.check_gate2(spec))
        for word in ("'bib_top'", "bib_topz", "'bibb'"):
            self.assertIn(word, bad)

    def test_a_part_with_no_vertices_fails(self):
        spec = S.load_spec(SPEC)
        motion = {"parts": {n: {"verts": 0 if n == "bib" else 10} for n in spec["gate2"]["parts"]}, "clips": {}}
        rows = {r["check"]: r["pass"] for r in GG.motion_rows(spec, motion, None) if r["clip"] == "rest"}
        self.assertFalse(rows["part found: bib (vertices)"])
        self.assertTrue(rows["part found: waistband (vertices)"])

    def test_hand_mask_size_and_folder(self):
        import tempfile
        spec = S.load_spec(SPEC)
        box = spec["concept"]["boxes"]["front"]
        with tempfile.TemporaryDirectory() as td:
            D.Canvas(box[2] - box[0], box[3] - box[1], bg=(0, 0, 0)).save(Path(td) / "ok.png")
            D.Canvas(20, 20, bg=(0, 0, 0)).save(Path(td) / "small.png")
            spec["gate2"]["mask_front"] = "ok.png"
            w, h, m = GG.concept_garment(spec, None, "front", Path(td), Path(td))
            self.assertEqual((w, h, sum(m)), (box[2] - box[0], box[3] - box[1], 0))
            spec["gate2"]["mask_front"] = "small.png"
            with self.assertRaises(SystemExit):
                GG.concept_garment(spec, None, "front", Path(td), Path(td))

    def test_videos_of_this_build(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            (t / "char.blend").write_bytes(b"blend")
            (t / "char.glb").write_bytes(b"glb")
            (t / "other.blend").write_bytes(b"other")
            v = t / "video"
            v.mkdir()
            sha = G.file_sha256(t / "char.blend")
            src = {"glb": (t / "char.glb").as_posix(), "glb_sha256": G.file_sha256(t / "char.glb"),
                   "blend": None, "blend_sha256": None}
            (v / "spec.json").write_text(json.dumps({"video_camera": {"label": "torso"}, "source": src}))
            self.assertTrue(GG.video_source(v, t / "char.blend", sha)[0])
            self.assertFalse(GG.video_source(v, t / "other.blend", G.file_sha256(t / "other.blend"))[0])
            (v / "spec.json").write_text(json.dumps({"source": src}))
            self.assertFalse(GG.video_source(v, t / "char.blend", sha)[0])      # the whole-body camera
            (v / "spec.json").write_text(json.dumps({"video_camera": {"label": "torso"}}))
            self.assertFalse(GG.video_source(v, t / "char.blend", sha)[0])      # no build id

    def test_probe_of_another_build_refused(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            pr = Path(td) / "probe.json"
            pr.write_text(json.dumps({"blend_sha256": "aa"}))
            GG.build_of(pr, "aa", "--probe")
            with self.assertRaises(SystemExit):
                GG.build_of(pr, "bb", "--probe")


class MotionTest(unittest.TestCase):
    def test_classify(self):
        spans = [(1.30, -0.12, 0.11, 0), (1.10, -0.15, 0.0, 0), (1.12, -0.13, -0.12, 0), (1.30, -0.12, 0.11, 0)]
        self.assertEqual(G.classify([400, 5000, 80, 120], spans, 1.25, 300), ["strap", "panel", "hardware", "strap"])

    def test_verdict(self):
        self.assertTrue(G.verdict(2.9, 3.0))
        self.assertFalse(G.verdict(3.1, 3.0))
        self.assertIsNone(G.verdict(None, 3.0))
        self.assertTrue(G.verdict(0.85, 0.8, smaller_is_better=False))

    def test_stretch(self):
        rest = [[0, 0, 0], [0.01, 0, 0], [0.02, 0, 0]]
        now = [[0, 0, 0], [0.0102, 0, 0], [0.0202, 0, 0]]
        mx, p95 = G.stretch(rest, now, [[0, 1], [1, 2]])
        self.assertAlmostEqual(mx, 2.0, places=6)
        self.assertLessEqual(p95, mx)
        self.assertEqual(G.stretch(rest, now, []), (None, None))            # an empty part never passes
        self.assertEqual(G.stretch(rest, now, [[0, 0]]), (None, None))      # no edge over min_len

    @unittest.skipUnless(HAVE_NUMPY, "numpy (Blender's Python has it)")
    def test_stretch_numpy_like_lists(self):
        import numpy as np
        rng = np.random.default_rng(1)
        rest, now = rng.random((30, 3)), rng.random((30, 3))
        e = np.array([[i, i + 1] for i in range(29)])
        mx, p95 = G.stretch(rest, now, e)
        l0 = np.linalg.norm(rest[e[:, 0]] - rest[e[:, 1]], axis=1)
        r = np.abs(np.linalg.norm(now[e[:, 0]] - now[e[:, 1]], axis=1) / l0 - 1) * 100
        self.assertAlmostEqual(mx, float(r.max()), places=6)
        self.assertAlmostEqual(p95, float(np.percentile(r, 95)), places=6)



def disc(cx, cy, cz, r, t, axis, n=10):
    """A closed disc (two rims and two centres) of radius r and thickness t around axis 'x', 'y' or 'z'."""
    import math
    verts, tris = [], []
    for side in (-t / 2, t / 2):
        for k in range(n):
            a = 2 * math.pi * k / n
            u, v = r * math.cos(a), r * math.sin(a)
            verts.append({"x": (side, u, v), "y": (u, side, v), "z": (u, v, side)}[axis])
    verts += [{"x": (s, 0, 0), "y": (0, s, 0), "z": (0, 0, s)}[axis] for s in (-t / 2, t / 2)]
    for k in range(n):
        k2 = (k + 1) % n
        tris += [[k, k2, 2 * n, 0], [n + k, n + k2, 2 * n + 1, 0], [k, k2, n + k, 0], [k2, n + k2, n + k, 0]]
    return [[cx + p[0], cy + p[1], cz + p[2]] for p in verts], tris


def mesh(parts, materials=("cloth",)):
    vs, ts = [], []
    for v, t, mi in parts:
        o = len(vs)
        vs += v
        ts += [[a + o, b + o, c + o, mi] for a, b, c, _ in t]
    return {"name": "garment", "materials": list(materials), "vertices": vs, "tris": ts}


def panel(x0, x1, y, z0, z1, n=6):
    vs = [[x0 + (x1 - x0) * i / n, y, z0 + (z1 - z0) * j / n] for j in range(n + 1) for i in range(n + 1)]
    ts = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            ts += [[a, a + 1, a + n + 1, 0], [a + 1, a + n + 2, a + n + 1, 0]]
    return vs, ts


class HardwareTest(unittest.TestCase):
    def test_pieces(self):
        m = mesh([(*panel(-0.1, 0.1, -0.1, 0.9, 1.1), 0), (*disc(0.09, -0.11, 1.08, 0.008, 0.004, "y"), 1)],
                 ("cloth", "bronze"))
        ps = S.mesh_pieces(m)
        self.assertEqual([p["verts"] for p in ps], [49, 22])
        self.assertEqual(ps[1]["materials"], ["bronze"])
        self.assertAlmostEqual(ps[1]["centre"][2], 1.08, places=6)

    def test_disc_size_any_axis(self):
        for axis in ("x", "y", "z"):
            v, _t = disc(0.0, 0.0, 0.0, 0.009, 0.004, axis, n=16)
            d, th, _n = S.disc_size(v)
            self.assertAlmostEqual(th, 0.004, delta=2e-4, msg=axis)
            self.assertAlmostEqual(d, 0.018, delta=4e-4, msg=axis)   # a 16-gon: 0.018 at the corners

    def test_buttons_pocket_and_absent(self):
        spec = {"gate2": {"classify": {"hardware_max_verts": 60}}}
        bib = (*panel(-0.11, 0.11, -0.12, 0.92, 1.12), 0)
        buckles = [(*disc(x, -0.13, 1.10, 0.008, 0.004, "y"), 1) for x in (-0.09, 0.09)]
        sides = [(*disc(x, -0.04, 0.91, 0.009, 0.004, "x"), 1) for x in (-0.13, 0.13)]
        pocket = (*panel(-0.07, 0.07, -0.125, 1.0, 1.08, n=3), 0)
        probe = {"meshes": [mesh([bib, *buckles, *sides, pocket], ("cloth", "bronze"))]}
        hw = GD.mesh_hardware(spec, probe, 112.0, 93.0)
        self.assertEqual(len(hw["buckle_buttons"]), 2)
        self.assertEqual(len(hw["side_buttons"]), 2)
        self.assertAlmostEqual(hw["buckle_buttons"][0]["d"], 0.016, delta=4e-4)
        self.assertAlmostEqual(hw["side_buttons"][0]["z"], 0.91, places=6)
        self.assertAlmostEqual(hw["side_buttons"][0]["d"], 0.018, delta=4e-4)
        self.assertAlmostEqual(hw["pocket"]["w"], 0.14, places=6)
        self.assertAlmostEqual(hw["pocket"]["top"], 1.08, places=6)
        self.assertAlmostEqual(hw["pocket"]["bottom"], 1.0, places=6)
        none = GD.mesh_hardware(spec, {"meshes": [mesh([bib])]}, 112.0, 93.0)
        self.assertEqual((none["buckle_buttons"], none["side_buttons"], none["pocket"]), ([], [], None))

    def test_pocket_by_material(self):
        bib = (*panel(-0.11, 0.11, -0.12, 0.92, 1.12), 0)
        pocket = (*panel(-0.06, 0.06, -0.12, 1.0, 1.06, n=2), 1)
        hw = GD.mesh_hardware({}, {"meshes": [mesh([bib, pocket], ("cloth", "denim_pocket"))]}, 112.0, 93.0)
        self.assertAlmostEqual(hw["pocket"]["w"], 0.12, places=6)
        self.assertIn("denim_pocket", hw["pocket"]["how"])

    def test_empty_garment_all_absent(self):
        spec = S.load_spec(SPEC)
        body = S.Sections({"meshes": []})
        res = GD.measure_build(spec, {"meshes": [{"name": "garment", "materials": [], "vertices": [], "tris": []}]},
                               body)
        self.assertEqual(set(res), set(spec["dims"]))
        self.assertTrue(all(v["absent"] and v["cm"] is None for v in res.values()))

    def test_band_hugging_her_waist_is_found(self):
        # G3a: a band at the spec's 24.5 cm is widest behind the centre line, 12.2 cm off it; the old window
        # (|x| 12-15 cm, y < 0) missed it and read the yoke under it as the band's top
        spec = S.load_spec(SPEC)
        bib = (*panel(-0.10, 0.10, -0.12, 1.0, 1.198), 0)
        band = (*panel(0.115, 0.1225, 0.01, 0.958, 0.998, n=2), 0)
        yoke = (*panel(0.12, 0.125, -0.01, 0.90, 0.963, n=2), 0)
        res = GD.measure_build(spec, {"meshes": [mesh([bib, band, yoke])]}, S.Sections({"meshes": []}))
        self.assertAlmostEqual(res["waistband_top_z"]["cm"], 99.8, places=2)

    def test_bust_gap_against_her_front_over_11_cm(self):
        # G3a: the gap is to her front over |x| < 11 cm (the bust's peaks), as the drawing's lean B, not the cleavage
        spec = S.load_spec(SPEC)
        bib = (*panel(-0.11, 0.11, -0.140, 1.0, 1.198), 0)
        band = (*panel(0.115, 0.1225, 0.01, 0.958, 0.998, n=2), 0)
        cleavage = panel(-0.04, 0.04, -0.120, 1.08, 1.18)
        peaks = panel(0.06, 0.10, -0.132, 1.08, 1.18)
        body = S.Sections({"meshes": [{"name": "b", "vertices": cleavage[0] + peaks[0],
                                       "tris": cleavage[1] + [[a + len(cleavage[0]), b + len(cleavage[0]),
                                                               c + len(cleavage[0]), 0] for a, b, c, _ in peaks[1]]}]})
        res = GD.measure_build(spec, {"meshes": [mesh([bib, band])]}, body)
        self.assertAlmostEqual(res["bib_standoff_bust"]["cm"], 0.3, places=2)

    def test_absent_is_a_failure(self):
        spec = {"dims": {"buckle_d": {"cm": 1.6, "tol_cm": 0.3}, "strap_w": {"cm": 3.8, "tol_cm": 0.3}}}
        meas = {"buckle_d": {"cm": None, "how": "absent", "absent": True}}
        _md, rows = GD.table(spec, meas, "t")
        self.assertEqual([r[5] for r in rows], [False, None])


if __name__ == "__main__":
    unittest.main()
