"""The throat's gills (art #263, 2026-10-28; tools/blender/ship_interior_gills.py, docs/ship.md "The throat's
gills"): the slit's and the button's numbers, the row on design's spots, the west a mirror of the east, the vent
cabinets gone, the hall's two throat corners alike, the band up to the ceiling's edge. Plain Python."""

from __future__ import annotations

import math
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import ship_interior as S  # noqa: E402
import ship_interior_gills as G  # noqa: E402

PLACE = tomllib.loads((ROOT / "layouts" / "ship" / "interior.toml").read_text(encoding="utf-8"))["place"]
# design's row (drawing2, the throat's row, the east wall; the west mirrors x)
DESIGN = {1: (2.259, -5.248), 2: (2.375, -4.896), 3: (2.490, -4.545), 4: (2.606, -4.193), 5: (2.721, -3.842)}
BUTTON = (2.812, -3.566)   # the manager, 2026-10-28: s 3.72 (was 3.80), the seam clear to its right


def parts(side: str) -> dict:
    return {p["name"]: p for p in G.th_gills({"side": side}, {})}


def plan(s: float) -> tuple[float, float]:
    """The east wall's line at s from the mouth's corner, absolute plan."""
    m = (S.TH_PTS[1][0] + S.HALL_C[0], S.TH_PTS[1][1] + S.HALL_C[1])
    return m[0] + G.WALL_D[0] * s, m[1] + G.WALL_D[1] * s


def key(verts, sx: float = 1.0) -> list:
    return sorted((round(sx * x, 6), round(y, 6), round(h, 6)) for x, y, h in verts)


class SlitNumbers(unittest.TestCase):
    def test_slit(self):
        self.assertAlmostEqual(G.CHORD, 1.20)
        self.assertAlmostEqual(G.SAG, 0.16)
        self.assertAlmostEqual(G.arc_off(0.0), G.SAG, places=9)              # the arc sags 16 at the middle
        self.assertAlmostEqual(G.arc_off(G.CHORD / 2), 0.0, places=9)         # and meets the chord at its ends
        self.assertAlmostEqual(G.arc_off(G.TAU_C), G.CHAMFER, places=9)       # the tips cut at a 2 cm flat
        self.assertEqual((G.DEPTH, G.GAP, G.LIP_T), (0.18, 0.015, 0.06))
        self.assertAlmostEqual(G.LIP_T + G.FIL_D, G.DEPTH)                    # the filaments fill the recess behind the lip
        self.assertEqual((G.OPEN_DEG, G.GASP_DEG), (25.0, 8.0))
        n = G.numbers()
        self.assertAlmostEqual(n["t_lo"], 0.75)
        self.assertAlmostEqual(n["t_hi"], 1.95)
        self.assertLess(n["t_lo"], G.BEND)                                    # the slit crosses the bend: its top on the lean
        self.assertGreater(n["t_hi"], G.BEND)
        self.assertGreater(n["t_lo"], G.PLINTH_H)                             # and stays on the band
        self.assertLess(n["t_hi"], G.T_TOP)

    def test_filaments(self):
        fil = parts("e")["gill3_fil"]
        self.assertEqual(G.FILS, 24)
        self.assertEqual(len(fil["verts"]), 8 * G.FILS)
        checked = 0
        for j in range(G.FILS):
            box = fil["verts"][8 * j: 8 * j + 8]
            hs = sorted({round(v[2], 9) for v in box})
            if hs[-1] < S.FLOOR + G.BEND:   # a filament on the vertical part: 2 cm thick, 12 deep
                self.assertAlmostEqual(hs[-1] - hs[0], G.FIL_T, places=6)
                ys = [v[1] for v in box]
                self.assertAlmostEqual(max(ys) - min(ys), G.FIL_D - 0.002, places=6)
                checked += 1
        self.assertGreater(checked, 10)

    def test_lip_gap(self):
        lip = parts("e")["gill3_lip_lo"]
        uc = G.slit_chord(G.SLITS[2])
        rows = 0
        for tau in G.taus():   # the lip's free edge stands GAP in from the cut's arc, row by row
            if G.T_MID + tau > G.BEND or abs(tau) >= G.TAU_C - 1e-9:
                continue
            row = [v for v in lip["verts"] if abs(v[2] - (S.FLOOR + G.T_MID + tau)) < 1e-9]
            self.assertAlmostEqual(min(v[0] for v in row), uc - G.arc_off(tau) + G.GAP, places=6)
            rows += 1
        self.assertGreater(rows, 5)

    def test_row_on_designs_spots(self):
        self.assertEqual([round(b - a, 6) for a, b in zip(G.SLITS, G.SLITS[1:])], [0.37] * 4)
        for k, xy in DESIGN.items():
            self.assertLess(math.dist(plan(G.SLITS[k - 1]), xy), 0.002, k)
        self.assertLess(math.dist(plan(G.BUTTON_S), BUTTON), 0.002)
        self.assertLess(G.BUTTON_T, G.BEND)                                   # the button on the vertical part
        self.assertTrue(G.BAND[0] < G.SLITS[0] - G.SAG and G.BUTTON_S + G.OCT_FLATS / 2 + 0.1 < G.BAND[1])   # seam clear
        self.assertAlmostEqual(G.WALL_LEN, 4.051, places=3)

    def test_button(self):
        p = parts("e")
        floor = p["btn_floor"]["verts"]
        xs = [v[0] for v in floor]
        self.assertAlmostEqual(max(xs) - min(xs), G.OCT_FLATS, places=6)     # 16 across the flats
        self.assertAlmostEqual(min(v[1] for v in floor), -G.OCT_D, places=6)  # 3 deep
        dome = p["btn_dome"]["verts"]
        self.assertAlmostEqual(max(v[1] for v in dome), G.DOME_UP, places=6)  # 2.5 proud
        self.assertAlmostEqual(max(v[0] for v in dome) - min(v[0] for v in dome), 2 * G.DOME_R, places=3)
        r = [math.hypot(v[0] - G.BUTTON_S, v[2] - S.FLOOR - G.BUTTON_T) for v in p["btn_ring"]["verts"]]
        self.assertAlmostEqual(max(r) - min(r), G.RING_W, places=6)

    def test_working_lip(self):
        e, w = parts("e"), parts("w")
        for leaf, (origin, axis) in G.lip_hinges().items():
            self.assertEqual(e[f"gill3_lip_{leaf}"]["origin"], origin)
            self.assertAlmostEqual(math.hypot(*axis), 1.0)
        self.assertFalse([n for n in w if "_lip_" in n])                     # the west's lips are all shut, built in
        gd = (ROOT / "godot" / "ship" / "gill_row.gd").read_text(encoding="utf-8")
        hi = [float(x) for x in re.search(r"AXIS_HI := Vector3\(([^)]*)\)", gd).group(1).split(",")]
        for a, b in zip(hi, G.lip_hinges()["hi"][1]):
            self.assertAlmostEqual(a, b, places=6)
        self.assertIn(f"const OPEN_DEG := {G.OPEN_DEG}", gd)
        self.assertIn(f"const GASP_DEG := {G.GASP_DEG}", gd)


class Mirror(unittest.TestCase):
    def test_west_mirrors_east(self):
        e, w = parts("e"), parts("w")
        shared = [n for n in e if n in w]
        self.assertGreater(len(shared), 30)
        for n in shared:
            self.assertEqual(key(e[n]["verts"], -1.0), key(w[n]["verts"]), n)
        lips = [n for n in e if n.startswith(("gill3_lip_", "gill3_line_"))]
        self.assertEqual(key([v for n in lips for v in e[n]["verts"]], -1.0),
                         key(w["gill3_lip"]["verts"] + w["gill3_line"]["verts"]))

    def test_placed_mirrored(self):
        got = {p[0]: p for p in PLACE if p[0].startswith("th_gills_")}
        self.assertEqual(set(got), {"th_gills_e", "th_gills_w"})
        self.assertEqual(got["th_gills_e"][1], [1.65, -7.1, 0.0])
        self.assertEqual(got["th_gills_w"][1], [-1.65, -7.1, 0.0])
        self.assertAlmostEqual(got["th_gills_e"][2], -G.WALL_YAW, places=3)
        self.assertAlmostEqual(got["th_gills_w"][2], G.WALL_YAW, places=3)


class Layout(unittest.TestCase):
    def test_vents_and_old_modules_gone(self):
        ids = {p[0] for p in PLACE}
        self.assertFalse({i for i in ids if i.startswith("station_vent")})
        self.assertFalse({i for i in ids if i.startswith(("th_wall_", "th_channel", "th_cables", "th_clip"))})

    def test_corners_match(self):
        for piece in ("hall_rib", "hall_rib_strip", "hall_pilaster", "hall_pilaster_strip"):
            for x in (2.9152, -2.9152):
                n = sum(1 for p in PLACE if p[0] == piece and p[1][:2] == [x, -3.2522])
                self.assertEqual(n, 1, (piece, x))

    def test_hall_vertices_once(self):
        vs = S.hall_vertices()
        self.assertEqual(len(vs), len({round(v, 4) for v in vs}))


class Ceiling(unittest.TestCase):
    def test_band_meets_the_ceiling_edge(self):
        """The ceiling's edge runs TH_IN in from the wall's line at TH_H; the band's top reaches it and runs on into
        the ceiling all along the wall, but where the hall's header cuts it lower (the header covers that)."""
        a, b, c = S._wall_line(1, S.TH_IN)
        edge = [p for q in S.throat_pieces(S.TH_IN, S.TH_ROOF, None) for p in q if abs(a * p[0] + b * p[1] - c) < 1e-6]
        self.assertTrue(edge)
        top = G.point(0.0, G.T_TOP)
        self.assertAlmostEqual(top[1], S.TH_IN, places=9)
        self.assertAlmostEqual(top[2], S.FLOOR + S.TH_H, places=9)
        band = parts("e")["band"]["verts"]
        ha, hb, hc = G.header_clip()
        u_cut = (hc - hb * (S.TH_IN + G.T_OVER * G.LV)) / ha   # from here on the header's face cuts the band lower
        tops = sorted({round(v[0], 6) for v in band if v[2] >= S.FLOOR + S.TH_H - 1e-9})
        self.assertAlmostEqual(tops[0], G.S0, places=5)        # the top row's columns run unbroken from the roof line
        self.assertGreaterEqual(tops[-1], u_cut - 1e-6)
        self.assertLessEqual(max(b - a for a, b in zip(tops, tops[1:])), 0.37 + 1e-6)

    def test_plinth(self):
        p = parts("e")
        self.assertAlmostEqual(max(v[2] for v in p["plinth"]["verts"]) - S.FLOOR, G.PLINTH_H, places=9)
        self.assertLessEqual(max(v[2] for v in p["plinth_line"]["verts"]) - S.FLOOR, G.PLINTH_H)


if __name__ == "__main__":
    unittest.main()
