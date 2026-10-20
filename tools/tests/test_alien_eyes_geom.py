"""The M4 eyes' pure parts (art #196): tools/blender/alien_eyes_geom.py (the wet line's profile, the cornea's
optics) and its agreement with godot/alien/alien_eye.gdshader's defaults."""
from __future__ import annotations

import ast
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_eyes_geom as E  # noqa: E402



def parts_constants() -> dict:
    """alien_parts.py's EYES and LID_BEAD, read from its source (the module needs bpy)."""
    tree = ast.parse((ROOT / "tools" / "blender" / "alien_parts.py").read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("EYES", "LID_BEAD"):
                out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


_P = parts_constants()
# alien_parts.EYES' lid radii and LID_BEAD per design and lid, as (rho_in, rho_out, bead, upper)
LIDS = [(*d[lid]["rho"], _P["LID_BEAD"][lid], lid == "upper") for d in _P["EYES"].values() for lid in ("upper", "lower")]


class WetLineTest(unittest.TestCase):
    def test_the_lids_are_read(self):
        self.assertEqual(len(LIDS), 4)
        self.assertIn((1.06, 1.13, 0.10, True), LIDS)

    def test_the_strip_stays_between_the_ball_and_the_lid(self):
        for rho_in, rho_out, bead, upper in LIDS:
            rm, hw = E.rim(rho_in, rho_out, bead)
            for rho, p in E.wet_profile(rho_in, rho_out, bead, upper):
                self.assertGreater(rho, 1.0, "never inside the ball")
                self.assertLessEqual(rho, rm, "never past the rim's middle (the strip lies beyond the lid's edge)")
                if p == 0.0:
                    self.assertLess(rho, rho_in, "at the edge, under the lid's inner surface")
                under = E.rim_lower_surface(abs(p), rm, hw)
                if under is not None:
                    self.assertLess(rho, under, "under the rim, below its surface")

    def test_it_runs_from_beyond_the_rim_to_the_lid_edge(self):
        for rho_in, rho_out, bead, upper in LIDS:
            prof = E.wet_profile(rho_in, rho_out, bead, upper)
            rm, hw = E.rim(rho_in, rho_out, bead)
            reach = hw / rm
            self.assertAlmostEqual(abs(prof[0][1]), reach + math.radians(E.WET["beyond_deg"]))
            self.assertEqual(prof[-1][1], 0.0)
            sgn = 1.0 if upper else -1.0
            self.assertTrue(all(sgn * p <= 0.0 for _, p in prof), "on the open eye's side of the edge")

    def test_lid_point_matches_lid_shell(self):
        # lid_shell: d = (sin t, -cos t cos p, cos t sin p) times rho
        x, y, z = E.lid_point(1.1, 0.3, -0.2)
        self.assertAlmostEqual(math.hypot(x, y, z), 1.1)
        self.assertAlmostEqual(y, -1.1 * math.cos(-0.2) * math.cos(0.3))


    def test_the_rim_reach_is_at_rim_v(self):
        nb = E.WET["seg_beyond"]
        for rho_in, rho_out, bead, upper in LIDS:
            prof = E.wet_profile(rho_in, rho_out, bead, upper)
            self.assertAlmostEqual(abs(prof[nb][1]), E.rim_reach(rho_in, rho_out, bead))
            self.assertAlmostEqual(nb / (len(prof) - 1), E.rim_v())
            rhos = [r for r, _ in prof]
            self.assertEqual(rhos, sorted(rhos), "rising evenly toward the lid's edge: no wall under the rim")
            self.assertLess(rhos[-1] - 1.0, 0.02, "close to the ball")

    def test_the_shader_fades_at_the_rim(self):
        text = (ROOT / "godot" / "alien" / "alien_wet.gdshader").read_text(encoding="utf-8")
        m = re.search(r"uniform float rim_v\b[^=]*=\s*([0-9.]+);", text)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(float(m.group(1)), E.rim_v())


def eye_look() -> dict:
    """alien.gd EYE_LOOK's plain numbers per design, by pattern."""
    gd = (ROOT / "godot" / "alien" / "alien.gd").read_text(encoding="utf-8")
    block = re.search(r"^const EYE_LOOK := \{(.*?)^\}", gd, re.S | re.M).group(1)
    parts = re.split(r'^\t"(\w+)": \{', block, flags=re.M)[1:]  # [design, its text, design, its text]
    return {d: {k: float(v) for k, v in re.findall(r'"(\w+)": (-?\d+(?:\.\d+)?)', text)}
            for d, text in zip(parts[::2], parts[1::2])}


def shader_default(name: str) -> float:
    text = (ROOT / "godot" / "alien" / "alien_eye.gdshader").read_text(encoding="utf-8")
    return float(re.search(rf"uniform float {name}\b[^=]*=\s*([0-9.]+);", text).group(1))


class EyeLookTest(unittest.TestCase):
    def test_the_designs_are_read(self):
        look = eye_look()
        self.assertEqual(sorted(look), ["bored", "manic"])
        self.assertEqual(look["bored"]["iris_deg"], 25.0)

    def test_the_iris_ends_inside_the_cornea(self):
        # in_c (the cornea) fades from limbus_deg - limbus_soft_deg to limbus_deg: the iris' and pupil's soft edge must
        # end before it, or the white paints over the iris' rim
        for design, v in eye_look().items():
            with self.subTest(design=design):
                edge = v.get("edge_deg", shader_default("edge_deg"))
                soft = v.get("limbus_soft_deg", shader_default("limbus_soft_deg"))
                self.assertLessEqual(max(v["iris_deg"], v["pupil_deg"]) + edge, v["limbus_deg"] - soft)

    def test_the_rim_reach_matches_the_lids(self):
        # M9b: the kit's lids are S9's slimmed by alien_lids_geom.LIDS (alien_m6.py on a mounted kit)
        import alien_lids_geom as LG
        eyes, beads = _P["EYES"], _P["LID_BEAD"]
        for design, v in eye_look().items():
            for lid in ("upper", "lower"):
                with self.subTest(design=design, lid=lid):
                    rho, bead = LG.slim(eyes[design][lid]["rho"], beads[lid], LG.LIDS)
                    want = math.degrees(E.rim_reach(*rho, bead))
                    self.assertAlmostEqual(v[f"{lid}_reach_deg"], want, delta=0.06)


class CorneaTest(unittest.TestCase):
    def test_the_sphere_meets_the_limbus_and_the_apex(self):
        for lim, bulge in ((27.0, 0.12), (21.0, 0.12), (30.0, 0.05)):
            zc, rc = E.cornea_sphere(lim, bulge)
            self.assertAlmostEqual(zc + rc, 1.0 + bulge)
            a = math.radians(lim)
            self.assertAlmostEqual(math.hypot(math.sin(a), math.cos(a) - zc), rc)

    def test_the_cornea_magnifies_and_keeps_the_order(self):
        c = dict(E.CORNEA)
        xs = [math.sin(math.radians(d)) for d in (2.0, 6.0, 11.5, 20.0, 25.0)]
        rhos = [E.front_rho(x, c) for x in xs]
        self.assertEqual(rhos, sorted(rhos), "monotone: the pupil stays inside the iris")
        for x, r in zip(xs, rhos):
            self.assertLess(r, x, "a convex cornea magnifies: the plane radius is smaller than it looks")
            self.assertGreater(r, 0.5 * x)

    def test_refract_bends_toward_the_normal(self):
        n = (math.sin(0.3), 0.0, math.cos(0.3))
        r = E.refract((0.0, 0.0, -1.0), n, 1.0 / 1.336)
        self.assertAlmostEqual(math.hypot(*r), 1.0)
        self.assertGreater(r[0], -0.3 / 1.336 * 2)
        self.assertLess(r[0], 0.0, "bent toward the axis' side of the normal")


class ShaderDefaultsTest(unittest.TestCase):
    def test_the_shader_defaults_match_the_module(self):
        text = (ROOT / "godot" / "alien" / "alien_eye.gdshader").read_text(encoding="utf-8")

        def uniform(name: str) -> float:
            m = re.search(rf"uniform float {name}\b[^=]*=\s*([0-9.]+);", text)
            self.assertIsNotNone(m, name)
            return float(m.group(1))

        for k in ("limbus_deg", "bulge", "iris_depth", "ior"):
            self.assertAlmostEqual(uniform(k), E.CORNEA[k], msg=k)


if __name__ == "__main__":
    unittest.main()
