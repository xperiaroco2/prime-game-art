"""The garment spec's loader and ratio maths (art #196, Gate 1): tools/blender/garment_spec.py and
specs/dungarees_dims.toml. Plain Python; no Blender, no raw files."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))

import garment_spec as S  # noqa: E402

SPEC = ROOT / "specs" / "dungarees_dims.toml"
LM = {"waist": 100.0, "collarbone": 125.0, "crotch": 70.0, "bust_w": 26.0}


class RatioMaths(unittest.TestCase):
    def test_height_between_landmarks(self):
        d = {"between": ["waist", "collarbone"], "ratio": 0.78, "cm": 0}
        self.assertAlmostEqual(S.at_ratio(LM, d), 119.5)
        self.assertAlmostEqual(S.ratio_of(LM, d, 119.5), 0.78)

    def test_height_past_a_landmark(self):
        d = {"between": ["crotch", "waist"], "ratio": 1.1, "cm": 0}
        self.assertAlmostEqual(S.at_ratio(LM, d), 103.0)

    def test_size_of_a_landmark(self):
        d = {"of": "bust_w", "ratio": 0.5, "cm": 0}
        self.assertEqual(S.kind(d), "size")
        self.assertAlmostEqual(S.at_ratio(LM, d), 13.0)
        self.assertAlmostEqual(S.ratio_of(LM, d, 6.5), 0.25)

    def test_fixed(self):
        d = {"cm": 3.8}
        self.assertEqual(S.kind(d), "fixed")
        self.assertEqual(S.at_ratio(LM, d), 3.8)

    def test_coinciding_landmarks_refused(self):
        with self.assertRaises(S.SpecError):
            S.ratio_of({"a": 1.0, "b": 1.0}, {"between": ["a", "b"], "ratio": 0.5}, 1.0)

    def test_within(self):
        d = {"cm": 10.0, "tol_cm": 0.5}
        self.assertTrue(S.within(d, 10.4))
        self.assertFalse(S.within(d, 10.6))
        self.assertIsNone(S.within(d, None))

    def test_lean(self):
        self.assertAlmostEqual(S.lean_deg(-0.11, 1.0, -0.11, 0.9), 0.0)
        self.assertGreater(S.lean_deg(-0.16, 1.1, -0.12, 0.93), 10)     # top forward


class Sections(unittest.TestCase):
    def probe(self):
        # a 1 x 1 m square tube, x and y in [-0.5, 0.5], z 0..1 (four quads as eight triangles)
        v = [[-.5, -.5, 0], [.5, -.5, 0], [.5, .5, 0], [-.5, .5, 0], [-.5, -.5, 1], [.5, -.5, 1], [.5, .5, 1], [-.5, .5, 1]]
        t = []
        for a in range(4):
            b = (a + 1) % 4
            t += [[a, b, b + 4, 0], [a, b + 4, a + 4, 0]]
        return {"bones": {}, "meshes": [{"name": "m", "materials": [""], "vertices": v, "tris": t}]}

    def test_one_closed_piece(self):
        sec = S.Sections(self.probe(), ["m"])
        pieces = sec.pieces(0.5)
        self.assertEqual(len(pieces), 1)
        lo, hi = S.trunk_x(sec, 0.5)
        self.assertAlmostEqual(lo, -0.5)
        self.assertAlmostEqual(hi, 0.5)

    def test_plane_on_a_vertex_row(self):
        sec = S.Sections(self.probe(), ["m"])       # z = 1.0 lies on the top vertices: moved up, no crossing
        self.assertEqual(sec.pieces(1.0), [])


class SpecFile(unittest.TestCase):
    def test_dungarees_spec_is_consistent(self):
        spec = S.load_spec(SPEC)
        self.assertEqual(S.check_spec(spec), [])
        self.assertEqual(spec["dims"]["bib_lean_deg"]["choice"], "B")
        for name in S.HEIGHTS:
            self.assertIn(name, spec["concept"]["rows"])

    def test_heights_ordered(self):
        spec = S.load_spec(SPEC)
        d = {k: v["cm"] for k, v in spec["dims"].items()}
        self.assertGreater(d["bib_top_z"], d["pocket_top_z"])
        self.assertGreater(d["pocket_bottom_z"], d["waistband_top_z"])
        self.assertGreater(d["waistband_top_z"], d["side_button_z"])
        self.assertGreater(d["hem_z"] - d["ankle_strip_h"], 10.0)

    def broken(self, text: str, extra: str = ""):
        good = SPEC.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.toml"
            p.write_text(good.replace(text, extra) if text else good + extra, encoding="utf-8")
            return S.load_spec(p)

    def test_cm_and_ratio_disagree(self):
        spec = S.load_spec(SPEC)
        spec["dims"]["bib_top_z"]["cm"] += 0.5
        self.assertEqual(len(S.check_spec(spec)), 1)

    def test_unknown_landmark_refused(self):
        with self.assertRaises(S.SpecError):
            self.broken('between = ["waist", "collarbone"]\nratio = 0.78',
                        'between = ["waist", "elbow"]\nratio = 0.78')

    def test_missing_tolerance_refused(self):
        with self.assertRaises(S.SpecError):
            self.broken("", '\n[dims.extra]\nwhat = "x"\ncm = 1.0\n')

    def test_missing_landmark_refused(self):
        with self.assertRaises(S.SpecError):
            self.broken("knee_w = 11.11\n")


if __name__ == "__main__":
    unittest.main()
