"""The static head's liveliness proof's pure formulas (art #196, lively): tools/blender/alien_lively_geom.py (the
neck and crest weights, the gaze maths and its lid clamp, the skin added to a GLB, the PNG writer)."""
from __future__ import annotations

import json
import math
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
        self.assertGreater(G.ROOT_BAND, G.POKE_TOL)


class RunTest(unittest.TestCase):
    """The run's refusals (PR #303 review minors 1 and 7): a tagged build whose folder exists, an untagged one whose GLB
    exists."""

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

    def test_glint_reach_in_shaders(self):
        # the clamp is the same text in the Godot shader and the web module, and the margins agree
        root = Path(__file__).resolve().parents[2]
        shader = (root / "godot/alien/alien_static.gdshader").read_text(encoding="utf-8")
        js = (root / "tools/web/lively/lively.js").read_text(encoding="utf-8")
        gd = (root / "godot/alien/alien_lively.gd").read_text(encoding="utf-8")
        clamp = "normalize(f * cos(reach) + normalize(cd - f * dot(cd, f)) * sin(reach))"
        self.assertIn(clamp, shader)
        self.assertIn(clamp, js)
        self.assertIn(f"const CATCH_MARGIN := {G.CATCH_MARGIN}", gd)
        self.assertIn(f"const CATCH_MARGIN = {G.CATCH_MARGIN};", js)

    def test_head_limits_in_controllers(self):
        # AL5: Godot and the web read the same controller keys (up and down pitch, the pitch's neck share, the tilt,
        # each falling back to AL4's) and roll the head the same way
        root = Path(__file__).resolve().parents[2]
        js = (root / "tools/web/lively/lively.js").read_text(encoding="utf-8")
        gd = (root / "godot/alien/alien_lively.gd").read_text(encoding="utf-8")
        for key in ("pitch_up_deg", "pitch_down_deg", "pitch_neck_share", "tilt"):
            self.assertIn(f'ctl.get("{key}"', gd)
            self.assertIn(f"ctl.{key} ??", js)
        self.assertIn("-tilt * _hy", gd)
        self.assertIn("-TILT * st.hy", js)
        self.assertIn("-pitch_down_limit, pitch_limit", gd)
        self.assertIn("-PITCH_DOWN, PITCH", js)

    def test_build_refusal(self):
        import tempfile
        sys.path.insert(0, str(ROOT / "tools" / "blender"))
        import alien_lively_run as R
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            glb = d / "axolotl_lively.glb"
            self.assertIsNone(R.build_refusal(d / "v9", d / "v9" / "axolotl_lively.glb", "v9"))
            self.assertIsNone(R.build_refusal(d, glb, ""))
            glb.write_bytes(b"x")
            self.assertIn("untagged", R.build_refusal(d, glb, ""))
            (d / "v9").mkdir()
            self.assertIn("new --tag", R.build_refusal(d / "v9", d / "v9" / "axolotl_lively.glb", "v9"))


if __name__ == "__main__":
    unittest.main()
