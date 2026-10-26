"""The static head's liveliness proof's pure formulas (art #196, lively): tools/blender/alien_lively_geom.py (the
neck and crest weights, the gaze maths and its lid clamp, the skin added to a GLB, the PNG writer)."""
from __future__ import annotations

import json
import math
import random
import struct
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_lively_geom as G  # noqa: E402


def tiny_glb(n: int = 3) -> bytes:
    """A one-triangle-per-three-vertices GLB: POSITION only, one node, one scene."""
    pos = struct.pack(f"<{3 * n}f", *[float(i) for i in range(3 * n)])
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "m"}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3"}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos)}],
           "buffers": [{"byteLength": len(pos)}]}
    return G.write_glb(doc, pos)


class WeightTest(unittest.TestCase):
    def test_neck_weights_sum_and_ends(self):
        for y in (-1.0, -0.5, -0.45, -0.4, 0.0):
            w = G.neck_weights(y, -0.55, -0.47, -0.39)
            self.assertAlmostEqual(sum(w), 1.0)
        self.assertEqual(G.neck_weights(-1.0, -0.55, -0.47, -0.39), (1.0, 0.0, 0.0))
        self.assertEqual(G.neck_weights(0.0, -0.55, -0.47, -0.39), (0.0, 0.0, 1.0))
        self.assertAlmostEqual(G.neck_weights(-0.47, -0.55, -0.47, -0.39)[1], 1.0)

    def test_crest_split(self):
        for t in (-0.5, 0.0, 0.2, 0.5, 0.7, 1.0, 1.5):
            self.assertAlmostEqual(sum(G.crest_split(t)), 1.0)
        self.assertEqual(G.crest_split(0.0), (1.0, 0.0, 0.0))
        self.assertEqual(G.crest_split(0.5), (0.0, 1.0, 0.0))
        self.assertEqual(G.crest_split(1.0), (0.0, 0.0, 1.0))


class GazeTest(unittest.TestCase):
    def test_frame_is_orthonormal(self):
        f, s, u = G.eye_frame((0.3, -0.1, 0.9))
        for a, b in ((f, s), (f, u), (s, u)):
            self.assertAlmostEqual(sum(x * y for x, y in zip(a, b)), 0.0)
        self.assertGreater(s[0], 0.9)  # side toward +X
        self.assertGreater(u[1], 0.9)  # up toward +Y

    def test_gaze_dir_rest_and_turns(self):
        rest = (0.1, -0.05, 1.0)
        g = G.gaze_dir(rest, 0.0, 0.0)
        n = math.sqrt(sum(c * c for c in rest))
        for a, b in zip(g, rest):
            self.assertAlmostEqual(a, b / n)
        self.assertGreater(G.gaze_dir(rest, 0.3, 0.0)[0], g[0])  # yaw toward +X
        self.assertGreater(G.gaze_dir(rest, 0.0, 0.3)[1], g[1])  # pitch up

    def test_offsets(self):
        y, p = G.gaze_offsets((1.0, 0.0, 1.0))
        self.assertAlmostEqual(y, math.pi / 4)
        self.assertAlmostEqual(p, 0.0)
        self.assertAlmostEqual(G.gaze_offsets((0.0, 1.0, 1.0))[1], math.pi / 4)

    def test_clamp_ellipse(self):
        lim = {"pos_x": 20, "neg_x": 10, "up": 0, "down": 30}
        self.assertEqual(G.clamp_gaze(0.1, 0.1, lim), (0.1, 0.0))  # no room up: the pitch goes, the yaw is clamped alone
        lim = {"pos_x": 20, "neg_x": 10, "up": 5, "down": 30}
        y, p = G.clamp_gaze(math.radians(40), 0.0, lim)
        self.assertAlmostEqual(math.degrees(y), 20)
        y, p = G.clamp_gaze(-math.radians(30), -math.radians(60), lim)
        self.assertAlmostEqual((math.degrees(y) / 10) ** 2 + (math.degrees(p) / 30) ** 2, 1.0)
        self.assertEqual(G.clamp_gaze(0.01, 0.01, lim), (0.01, 0.01))

    def test_clamp_cap(self):
        lim = {"pos_x": 40, "neg_x": 8, "up": 0, "down": 40}
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(math.radians(60), 0.0, lim)[0]), 40)
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(math.radians(60), 0.0, lim, cap_deg=25)[0]), 25)
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(-math.radians(60), 0.0, lim, cap_deg=25)[0]), -8)
        self.assertAlmostEqual(math.degrees(G.clamp_gaze(0.0, -math.radians(60), lim, cap_deg=25)[1]), -25)

    def test_eye_offsets_invert_gaze_dir(self):
        rest = (-0.06077, -0.01519, 0.99804)  # the chameleon's left eye
        for yaw, pitch in ((0.0, 0.0), (0.3, -0.2), (-0.4, 0.1)):
            y, p = G.eye_offsets(rest, G.gaze_dir(rest, yaw, pitch))
            self.assertAlmostEqual(y, yaw)
            self.assertAlmostEqual(p, pitch)
        # straight ahead in the head's frame is a few degrees off this eye's rest gaze
        y, _ = G.eye_offsets(rest, (0.0, 0.0, 1.0))
        self.assertAlmostEqual(math.degrees(y), math.degrees(math.atan2(0.06077, 0.99804)), places=3)


class SkinTest(unittest.TestCase):
    def test_add_skin_round_trip(self):
        pos = {name: (0.0, 0.1 * k, 0.0) for k, name in enumerate(G.JOINTS)}
        infl = [[(0, 0.3), (1, 0.7)], [(2, 1.0)], [(2, 0.5), (3, 0.25), (4, 0.15), (5, 0.07), (1, 0.03)]]
        doc, binary = G.read_glb(G.add_skin(tiny_glb(), pos, infl))
        self.assertEqual(doc["nodes"][0]["skin"], 0)
        skin = doc["skins"][0]
        self.assertEqual([doc["nodes"][j]["name"] for j in skin["joints"]], list(G.JOINTS))
        self.assertIn(skin["joints"][0], doc["scenes"][0]["nodes"])
        self.assertEqual(doc["nodes"][skin["joints"][2]]["translation"], [0.0, 0.1, 0.0])  # Head relative to Neck
        attrs = doc["meshes"][0]["primitives"][0]["attributes"]
        for key in ("JOINTS_0", "WEIGHTS_0"):
            view = doc["bufferViews"][doc["accessors"][attrs[key]]["bufferView"]]
            self.assertEqual(view["byteOffset"] % 4, 0)
        wv = doc["bufferViews"][doc["accessors"][attrs["WEIGHTS_0"]]["bufferView"]]
        w = struct.unpack_from("<12f", binary, wv["byteOffset"])
        for k in range(3):
            self.assertAlmostEqual(sum(w[4 * k:4 * k + 4]), 1.0, places=6)
        jv = doc["bufferViews"][doc["accessors"][attrs["JOINTS_0"]]["bufferView"]]
        j = struct.unpack_from("<12H", binary, jv["byteOffset"])
        self.assertEqual(j[8:12], (2, 3, 4, 5))  # the four largest kept, the smallest dropped
        self.assertEqual(doc["buffers"][0]["byteLength"], len(binary))

    def test_refuses_a_count_mismatch(self):
        with self.assertRaises(ValueError):
            G.add_skin(tiny_glb(), {n: (0.0, 0.0, 0.0) for n in G.JOINTS}, [[(0, 1.0)]])

    def test_normalise_weights_float32_sum(self):
        w = G.normalise_weights([0.1, 0.2, 0.3, 0.4000001])
        self.assertAlmostEqual(sum(w), 1.0, places=6)


class PngTest(unittest.TestCase):
    def test_png_bytes(self):
        data = G.png_bytes(2, 1, bytes([255, 0, 0, 0, 255, 0]))
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        w, h = struct.unpack(">II", data[16:24])
        self.assertEqual((w, h), (2, 1))
        idat = data.index(b"IDAT")
        size = struct.unpack(">I", data[idat - 4:idat])[0]
        self.assertEqual(zlib.decompress(data[idat + 4:idat + 4 + size]), b"\0" + bytes([255, 0, 0, 0, 255, 0]))


class EyePitTest(unittest.TestCase):
    """The eye pit's fix (art #196): the eyeball's sphere fit and the projection of the old iris onto it."""

    def sphere_points(self, c, r, n=40):
        pts = []
        for i in range(n):
            z = -1.0 + 2.0 * (i + 0.5) / n
            a = i * 2.399963  # the golden angle: spread points
            s = math.sqrt(1.0 - z * z)
            pts.append((c[0] + r * s * math.cos(a), c[1] + r * s * math.sin(a), c[2] + r * z))
        return pts

    def test_fit_sphere_exact(self):
        c, r = G.fit_sphere(self.sphere_points((0.265, 0.266, 0.355), 0.186))
        for got, want in zip(c, (0.265, 0.266, 0.355)):
            self.assertAlmostEqual(got, want, places=9)
        self.assertAlmostEqual(r, 0.186, places=9)

    def test_fit_sphere_cap_only(self):
        # a cap of 60 degrees about +Z (the visible sclera ring the build fits) still gives the sphere
        pts = [p for p in self.sphere_points((0.0, 0.0, 0.0), 1.0, 400) if p[2] > 0.5]
        c, r = G.fit_sphere(pts)
        self.assertAlmostEqual(r, 1.0, places=9)
        self.assertAlmostEqual(math.dist(c, (0.0, 0.0, 0.0)), 0.0, places=9)

    def test_fit_sphere_degenerate(self):
        with self.assertRaises(ValueError):
            G.fit_sphere([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)])

    def test_pit_weight(self):
        self.assertEqual(G.pit_weight(0.1, 0.3, 0.5, 1.0, 0.1, 0.2), 1.0)
        self.assertEqual(G.pit_weight(0.6, 0.3, 0.5, 1.0, 0.1, 0.2), 0.0)
        self.assertEqual(G.pit_weight(0.1, 0.3, 0.5, 0.05, 0.1, 0.2), 0.0)  # next to the lid: never moved
        self.assertAlmostEqual(G.pit_weight(0.4, 0.3, 0.5, 1.0, 0.1, 0.2), 0.5)
        self.assertAlmostEqual(G.pit_weight(0.1, 0.3, 0.5, 0.15, 0.1, 0.2), 0.5)

    def test_capped_weight(self):
        self.assertEqual(G.capped_weight(1.0, 0.002, 1.0, 0.5, 0.004), 1.0)  # a small move: untouched
        self.assertAlmostEqual(G.capped_weight(1.0, 0.014, 1.0, 0.5, 0.004), 0.004 / 0.014)  # the absolute cap
        self.assertAlmostEqual(G.capped_weight(1.0, 0.004, 0.002, 0.5, 0.004), 0.25)  # half the room to the lid
        self.assertEqual(G.capped_weight(0.3, 0.004, 0.0, 0.5, 0.004), 0.0)  # touching a lid: never moved
        self.assertEqual(G.capped_weight(0.0, 0.01, 1.0, 0.5, 0.004), 0.0)
        self.assertEqual(G.capped_weight(0.7, 0.0, 1.0, 0.5, 0.004), 0.7)  # already on the sphere

    def test_project_on_sphere(self):
        dent = (0.0, 0.0, 0.97)  # 3 % of the radius inside the unit sphere
        self.assertEqual(G.project_on_sphere(dent, (0.0, 0.0, 0.0), 1.0, 0.0), dent)
        full = G.project_on_sphere(dent, (0.0, 0.0, 0.0), 1.0, 1.0)
        self.assertAlmostEqual(full[2], 1.0)
        half = G.project_on_sphere(dent, (0.0, 0.0, 0.0), 1.0, 0.5)
        self.assertAlmostEqual(half[2], 0.985)
        self.assertAlmostEqual(half[0], 0.0)

    def test_colour_distance(self):
        self.assertAlmostEqual(G.colour_distance((1.0, 1.0, 1.0), (0.0, 0.0, 0.0)), math.sqrt(3.0))
        self.assertEqual(G.colour_distance((0.5, 0.4, 0.3), (0.5, 0.4, 0.3)), 0.0)


class PatchTest(unittest.TestCase):
    """AL1 (PR #303 review minor 7): write_vec3's round trip through a 3-vertex GLB, the tangent fix, the gills' skin."""

    def test_write_vec3_round_trip(self):
        doc, binary = G.read_glb(tiny_glb(3))
        doc["accessors"][0]["min"], doc["accessors"][0]["max"] = [0.0] * 3, [8.0] * 3
        rows = [(0.5, -1.25, 2.0), (3.0, 4.5, -6.0), (0.1, 0.2, 0.3)]
        G.write_vec3(doc, binary, 0, rows)
        doc2, binary2 = G.read_glb(G.write_glb(doc, binary))
        back = G.read_vec3(doc2, binary2, 0)
        for r, b in zip(rows, back):
            for x, y in zip(r, b):
                self.assertAlmostEqual(x, y, places=6)
        self.assertEqual(doc2["accessors"][0]["min"], [min(r[k] for r in back) for k in range(3)])
        self.assertEqual(doc2["accessors"][0]["max"], [max(r[k] for r in back) for k in range(3)])
        with self.assertRaises(ValueError):
            G.write_vec3(doc, binary, 0, rows[:2])

    def test_orthogonal_tangent(self):
        t = G.orthogonal_tangent((0.0, 0.0, 1.0), (0.6, 0.0, 0.8, -1.0))
        self.assertAlmostEqual(t[0], 1.0, places=9)
        self.assertAlmostEqual(t[2], 0.0, places=9)
        self.assertEqual(t[3], -1.0)
        n = G._norm((0.3, -0.2, 0.9))
        t = G.orthogonal_tangent(n, (1.0, 0.0, 0.0, 1.0))
        self.assertAlmostEqual(sum(n[i] * t[i] for i in range(3)), 0.0, places=9)
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in t[:3])), 1.0, places=9)
        t = G.orthogonal_tangent((0.0, 1.0, 0.0), (0.0, 2.0, 0.0, 1.0))  # along n: some perpendicular
        self.assertAlmostEqual(t[1], 0.0, places=9)

    def test_stalk_weight(self):
        self.assertEqual(G.stalk_weight(0.0, 0.3, 1.0), 0.0)
        self.assertEqual(G.stalk_weight(0.3, 0.3, 1.0), 1.0)
        self.assertEqual(G.stalk_weight(0.3, 0.3, 0.2), 0.0)  # the thick skull never moves

    def test_stalk_weight_lifted(self):
        # the thick skull (no lift) never moves; a thick core out over the skull moves fully (AL4)
        self.assertEqual(G.stalk_weight_lifted(0.3, 0.3, 0.0, 0.0), 0.0)
        self.assertEqual(G.stalk_weight_lifted(0.3, 0.3, 0.0, G.LIFT_FULL), 1.0)
        self.assertEqual(G.stalk_weight_lifted(0.3, 0.3, 1.0, 0.0), 1.0)
        self.assertEqual(G.stalk_weight_lifted(0.0, 0.3, 1.0, 1.0), 0.0)  # the root band
        mid = G.stalk_weight_lifted(0.3, 0.3, 0.0, 0.5 * (G.LIFT_IN + G.LIFT_FULL))
        self.assertAlmostEqual(mid, 0.5)

    def test_smooth_within(self):
        # a chain 0-1-2-3 of stalk 0, then 4 of stalk 1: the step 1 -> 0 at vertex 2 softens, nothing leaks to 4
        vals = [0.0, 0.0, 1.0, 1.0, 1.0]
        edges = [(0, 1), (1, 2), (2, 3), (3, 4)]
        labels = [0, 0, 0, 0, 1]
        pinned = [True, False, False, False, False]
        w = G.smooth_within(vals, edges, labels, 0, pinned, passes=1, alpha=0.5)
        self.assertEqual(w[0], 0.0)  # pinned
        self.assertAlmostEqual(w[1], 0.25)  # 0.5 * 0 + 0.5 * mean(0, 1)
        self.assertAlmostEqual(w[2], 0.75)
        self.assertAlmostEqual(w[3], 1.0)  # its only same-label neighbour is 2 (1.0); vertex 4 does not count
        self.assertEqual(w[4], 1.0)  # another stalk's vertex is left as it was
        w = G.smooth_within(vals, edges, labels, 0, pinned, passes=200)
        self.assertLess(max(w[:4]), 0.01)  # pinned at 0: the chain settles to the pin

    def test_gill_skin(self):
        pos = {n: (0.0, 0.1 * k, 0.0) for k, n in enumerate(G.GILL_JOINTS)}
        out = G.add_skin(tiny_glb(3), pos, [[(2, 1.0)], [(3, 0.5), (2, 0.5)], [(8, 1.0)]],
                         joints=G.GILL_JOINTS, parents=G.GILL_PARENTS)
        doc, _ = G.read_glb(out)
        first = doc["skins"][0]["joints"][0]
        self.assertEqual(len(doc["skins"][0]["joints"]), 9)
        self.assertEqual(doc["nodes"][first + 2]["children"], [first + k for k in range(3, 9)])
        with self.assertRaises(ValueError):
            G.add_skin(tiny_glb(3), pos, [[(0, 1.0)]] * 3, joints=("A", "B"), parents=(1, -1))


class SpringTest(unittest.TestCase):
    """AL2: the poke test turns the gills as the controllers do, at the cap's eight limit corners."""

    @staticmethod
    def apply(m, v):
        return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]

    def test_spring_matrix_axes(self):
        a = math.radians(15.0)
        # yaw alone turns about +Y: +Z toward +X (Godot's and three.js's right-handed Ry)
        x, y, z = self.apply(G.spring_matrix(a, 0.0), [0.0, 0.0, 1.0])
        self.assertAlmostEqual(x, math.sin(a))
        self.assertAlmostEqual(y, 0.0)
        # pitch alone is Rx(-pitch): +Z tips up toward +Y
        x, y, z = self.apply(G.spring_matrix(0.0, a), [0.0, 0.0, 1.0])
        self.assertAlmostEqual((x, y), (0.0, math.sin(a)))

    def test_spring_matrix_is_ry_times_rx(self):
        m = G.spring_matrix(0.3, -0.2)
        for i in range(3):  # orthonormal
            for j in range(3):
                self.assertAlmostEqual(sum(m[k][i] * m[k][j] for k in range(3)), 1.0 if i == j else 0.0)
        # Ry(yaw) * Rx(-pitch): +X stays in the XZ plane (Rx leaves it, Ry turns it about Y)
        self.assertAlmostEqual(self.apply(m, [1.0, 0.0, 0.0])[1], 0.0)

    def test_corners_and_limits(self):
        self.assertEqual(len(set(G.SWING_CORNERS)), 8)
        self.assertNotIn((0, 0), G.SWING_CORNERS)
        self.assertLessEqual(G.SPRING_MAX_DEG, 15.0)
        self.assertLess(G.MOVED_EPS, G.POKE_TOL)
        self.assertLessEqual(G.TEST_W, 0.01)


class RunTest(unittest.TestCase):
    """The run's refusals (PR #303 review minors 1 and 7, PR #306 review major 1 and minor 9) and the controllers'
    shared defaults."""

    def test_glint_reach(self):
        # AL3: at rest the glint is where it was; at a head turn it slides to the reach, never under the lid
        rest, catch = (0.0, 0.0, 1.0), (-0.22, 0.40, 0.89)
        reach = G.catch_reach(rest, catch)
        cn = G._norm(catch)
        self.assertAlmostEqual(reach, math.acos(cn[2]) + G.CATCH_MARGIN, places=9)
        for a, b in zip(G.glint_dir(rest, catch, reach), cn):
            self.assertAlmostEqual(a, b, places=9)
        turned = (math.sin(0.7), 0.0, math.cos(0.7))  # the bead turned 40 degrees away from the catch's side
        g = G.glint_dir(turned, catch, reach)
        self.assertAlmostEqual(math.acos(sum(x * y for x, y in zip(turned, g))), reach, places=9)
        self.assertAlmostEqual(sum(x * x for x in g), 1.0, places=9)
        self.assertGreater(g[1], 0.0)  # still on the catch light's side (up)
        self.assertEqual(G.glint_dir(turned, catch, 0.0), cn)

    def test_controller_defaults_agree(self):
        # AL6 (PR #306 review): Godot and the web share one table of the controller's defaults (a lively.json without
        # a key, or without a controller, e.g. v2's) and the same constants; parsed from both files, not string-matched
        root = Path(__file__).resolve().parents[2]
        js = (root / "tools/web/lively/lively.js").read_text(encoding="utf-8")
        gd = (root / "godot/alien/alien_lively.gd").read_text(encoding="utf-8")
        import re
        want = {"gaze": "iris", "head_hz": 1.6, "yaw_deg": 35.0, "pitch_deg": 20.0, "neck_share": 0.4, "tilt": 0.0,
                "sclera_normal_map": 1.0}
        got_gd = json.loads(re.search(r"^const CONTROLLER_DEFAULTS := (\{.*\})$", gd, re.M).group(1))
        got_js = json.loads(re.search(r"^export const CONTROLLER_DEFAULTS = (\{.*\});$", js, re.M).group(1))
        self.assertEqual(got_gd, want)
        self.assertEqual(got_js, want)
        consts = {"CATCH_MARGIN": G.CATCH_MARGIN, "EYE_HZ": 9.0, "BREATH_S": 4.4}
        for name, value in consts.items():
            self.assertAlmostEqual(float(re.search(rf"const {name} := ([0-9.]+)", gd).group(1)), value)
            self.assertAlmostEqual(float(re.search(rf"\b{name} = ([0-9.]+)", js).group(1)), value)
        # both fall back the same way: no springs listed, none made
        self.assertIn('lively["rig"].get("springs", [])', gd)
        self.assertIn("(data.rig.springs || [])", js)

    def test_run_refusal(self):
        # PR #306 review: an untagged build is refused outright (it wrote into <out> itself, over the v2 chameleon's
        # lively.json and build.log); a tagged build whose folder exists; shots whose sheet_<tag>.jpg exists, even
        # with --no-build or --seconds 0; a video whose frame folder exists
        import tempfile
        import alien_lively_run as R
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertIn("untagged", R.run_refusal(d, "", True, False, 20.0))
            self.assertIn("untagged", R.run_refusal(d, "", True, True, 0.0))
            self.assertIsNone(R.run_refusal(d, "v9", True, True, 20.0))
            (d / "v9").mkdir()
            self.assertIn("new --tag", R.run_refusal(d, "v9", True, False, 20.0))
            self.assertIsNone(R.run_refusal(d, "v9", False, True, 20.0))  # a re-shoot of a build with no shots yet
            (d / "sheet_v9.jpg").write_bytes(b"x")
            for seconds in (0.0, 20.0):
                self.assertIn("sheet_v9.jpg", R.run_refusal(d, "v9", False, True, seconds))
            (d / "sheet_v7.jpg").write_bytes(b"x")  # a build whose folder is new, but its sheet is not
            self.assertIn("sheet_v7.jpg", R.run_refusal(d, "v7", True, True, 0.0))
            for name in ("eyes_pit_v5.jpg", "shots_v6.json"):  # AL7: the eye pit sheet and the shots JSON too
                (d / name).write_bytes(b"x")
            self.assertIn("eyes_pit_v5.jpg", R.run_refusal(d, "v5", False, True, 0.0))
            self.assertIn("shots_v6.json", R.run_refusal(d, "v6", True, True, 20.0))
            self.assertIsNone(R.run_refusal(d, "v5", True, False, 20.0))  # a build alone makes neither
            self.assertIsNone(R.run_refusal(d, "v9", False, False, 20.0))  # the validator alone
            (d / "sheet.jpg").write_bytes(b"x")
            self.assertIn("sheet.jpg", R.run_refusal(d, "", False, True, 0.0))
            (d / "video" / "lively_v8").mkdir(parents=True)
            self.assertIn("lively_v8", R.run_refusal(d, "v8", False, True, 20.0))
            self.assertIsNone(R.run_refusal(d, "v8", False, True, 0.0))


class RimCutTest(unittest.TestCase):
    """R1: the rim cut's pure maths (alien_lively_build.rim_cut): the curve's fit and one triangle's cut."""

    def test_fourier_fit_recovers_a_series(self):
        coef = [0.5, 0.1, -0.05, 0.0, 0.02]
        phi = [2 * math.pi * k / 60 for k in range(60)]
        got = G.fourier_fit(phi, [G.fourier_eval(coef, p) for p in phi], 2)
        for a, b in zip(got, coef):
            self.assertAlmostEqual(a, b, places=9)
        with self.assertRaises(ValueError):
            G.fourier_fit(phi[:5], [0.0] * 5, 2)

    def test_fourier_fit_smooths_a_sawtooth_and_drops_a_spur(self):
        """R2: an irregular sawtooth (steps in and out of uneven depth, as the rim's triangles leave them), not a
        Nyquist alternation, which no order below 40 can see."""
        rng = random.Random(7)
        phi = [2 * math.pi * k / 80 for k in range(80)]
        truth = [0.6 + 0.1 * math.cos(p) for p in phi]
        step = [rng.uniform(-0.02, 0.02) for _ in phi]
        val = [t + e for t, e in zip(truth, step)]
        val[10] += 0.5  # a junction's spur
        coef, keep = G.fourier_fit_trimmed(phi, val, 4)
        self.assertFalse(keep[10])
        self.assertEqual(sum(keep), 79)
        err = [G.fourier_eval(coef, p) - t for p, t in zip(phi, truth)]
        rms = math.sqrt(sum(e * e for e in err) / len(err))
        rms_in = math.sqrt(sum(e * e for k, e in enumerate(step) if k != 10) / 79)
        self.assertLess(rms, 0.55 * rms_in)  # the steps averaged out (about sqrt(9 / 79) of them stays, 0.45 here)
        self.assertLess(max(abs(e) for e in err), 0.012)  # and the spur left no bump

    def test_cut_one_corner_alone(self):
        pieces = G.cut_triangle((-1.0, 1.0, 3.0))
        self.assertEqual([s for _p, s in pieces], [-1, 1])
        corner, quad = pieces[0][0], pieces[1][0]
        self.assertEqual(corner[0], ("v", 0))
        self.assertEqual(corner[1], ("e", 0, 1, 0.5))
        self.assertEqual(corner[2], ("e", 0, 2, 0.25))
        self.assertEqual(quad, [("e", 0, 1, 0.5), ("v", 1), ("v", 2), ("e", 0, 2, 0.25)])

    def test_cut_keeps_the_winding(self):
        """Every piece turns the parent's way (its signed area in 2D positive for a counter-clockwise parent)."""
        tri = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]

        def at(ref):
            if ref[0] == "v":
                return tri[ref[1]]
            a, b, t = tri[ref[1]], tri[ref[2]], ref[3]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        for g in ((-1.0, 1.0, 3.0), (2.0, -1.0, 1.0), (1.0, 2.0, -0.5), (0.0, -1.0, 1.0), (1.0, 0.0, -2.0)):
            total = 0.0
            for poly, _s in G.cut_triangle(g):
                pts = [at(x) for x in poly]
                area = sum(pts[k][0] * pts[(k + 1) % len(pts)][1] - pts[(k + 1) % len(pts)][0] * pts[k][1]
                           for k in range(len(pts))) / 2
                self.assertGreater(area, 0.0, g)
                total += area
            self.assertAlmostEqual(total, 0.5, places=12)

    def test_cut_through_a_corner_and_no_cut(self):
        pieces = G.cut_triangle((0.0, -1.0, 1.0))
        self.assertEqual([s for _p, s in pieces], [-1, 1])
        self.assertEqual(pieces[0][0], [("v", 0), ("v", 1), ("e", 1, 2, 0.5)])
        self.assertEqual(G.cut_triangle((0.0, 1.0, 2.0)), [([("v", 0), ("v", 1), ("v", 2)], 1)])
        self.assertEqual(G.cut_triangle((0.0, -1.0, 0.0)), [([("v", 0), ("v", 1), ("v", 2)], -1)])
        self.assertEqual(G.cut_triangle((0.0, 0.0, 0.0)), [([("v", 0), ("v", 1), ("v", 2)], 0)])

    def test_replace_accessor_grows_the_rows(self):
        doc, binary = G.read_glb(tiny_glb(3))
        doc["accessors"][0]["min"], doc["accessors"][0]["max"] = [0, 0, 0], [0, 0, 0]
        G.replace_accessor(doc, binary, 0, [(0, 0, 0), (1, 2, 3), (-1, 5, 0), (2, 2, 2)])
        a = doc["accessors"][0]
        self.assertEqual(a["count"], 4)
        self.assertEqual((a["min"], a["max"]), ([-1, 0, 0], [2, 5, 3]))
        self.assertEqual(G.read_vec3(doc, binary, 0)[3], (2.0, 2.0, 2.0))
        doc["accessors"].append({"bufferView": 0, "componentType": 5123, "count": 3, "type": "SCALAR"})
        G.replace_accessor(doc, binary, 1, [0, 1, 2, 2, 1, 3], 5125)
        v = doc["bufferViews"][doc["accessors"][1]["bufferView"]]
        self.assertEqual((doc["accessors"][1]["count"], doc["accessors"][1]["componentType"], v["target"]), (6, 5125, 34963))
        self.assertEqual(struct.unpack_from("<6I", binary, v["byteOffset"]), (0, 1, 2, 2, 1, 3))
        self.assertEqual(doc["buffers"][0]["byteLength"], len(binary))

    def test_compact_buffers_drops_unused_views_and_keeps_the_data(self):
        """E1: after replace_accessor (the old views left unused) and with a sparse accessor and an image in views of
        odd lengths, compact_buffers leaves no view unused, every kept view's bytes as they were, 4-byte aligned."""
        doc, binary = G.read_glb(tiny_glb(3))
        doc["accessors"].append({"bufferView": 0, "componentType": 5123, "count": 3, "type": "SCALAR"})
        G.replace_accessor(doc, binary, 0, [(0, 0, 0), (1, 2, 3), (-1, 5, 0), (2, 2, 2)])
        G.replace_accessor(doc, binary, 1, [0, 1, 2, 2, 1, 3], 5125)  # view 0 is now unused

        def add_view(payload):
            binary.extend(bytes(-len(binary) % 4))
            doc["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(payload)})
            binary.extend(payload)
            return len(doc["bufferViews"]) - 1
        add_view(b"\x07" * 12)  # never used
        si, sv = add_view(struct.pack("<H", 1) + b"\x00"), add_view(struct.pack("<3f", 9, 8, 7))
        doc["accessors"][0]["sparse"] = {"count": 1, "indices": {"bufferView": si, "componentType": 5121},
                                         "values": {"bufferView": sv}}
        doc["images"] = [{"bufferView": add_view(b"PNG-ish!x"), "mimeType": "image/png"}]
        doc["buffers"][0]["byteLength"] = len(binary)

        def payloads(d, b):
            out = {}
            for k, a in enumerate(d["accessors"]):
                v = d["bufferViews"][a["bufferView"]]
                out[f"a{k}"] = bytes(b[v["byteOffset"]:v["byteOffset"] + v["byteLength"]])
                for part in ("indices", "values"):
                    if "sparse" in a:
                        v = d["bufferViews"][a["sparse"][part]["bufferView"]]
                        out[f"a{k}{part}"] = bytes(b[v["byteOffset"]:v["byteOffset"] + v["byteLength"]])
            v = d["bufferViews"][d["images"][0]["bufferView"]]
            out["image"] = bytes(b[v["byteOffset"]:v["byteOffset"] + v["byteLength"]])
            return out
        before = payloads(doc, binary)
        views_before = len(doc["bufferViews"])
        out = G.compact_buffers(doc, binary)
        self.assertEqual(payloads(doc, out), before)
        used = {a["bufferView"] for a in doc["accessors"]} | {doc["images"][0]["bufferView"]}
        used |= {doc["accessors"][0]["sparse"][p]["bufferView"] for p in ("indices", "values")}
        self.assertEqual(used, set(range(len(doc["bufferViews"]))))  # no unused view left
        self.assertEqual(len(doc["bufferViews"]), views_before - 2)  # the old shared view and the stray one
        self.assertTrue(all(v["byteOffset"] % 4 == 0 for v in doc["bufferViews"]))
        self.assertEqual(doc["buffers"][0]["byteLength"], len(out))
        self.assertLess(len(out), len(binary))
        doc2, bin2 = G.read_glb(G.write_glb(doc, out))  # and it round-trips as a GLB
        self.assertEqual(G.read_vec3(doc2, bin2, 0)[3], (2.0, 2.0, 2.0))


if __name__ == "__main__":
    unittest.main()
