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
        self.assertAlmostEqual(G.CHORD, 1.20)                                   # design's chord stays
        self.assertEqual((G.SAG, G.SAG_IN), (0.27, 0.06))                       # the concept's crescent
        for f in (G.arc_off, G.arc_in):
            self.assertAlmostEqual(f(G.CHORD / 2), 0.0, places=9)                # both arcs through the same tips
        self.assertAlmostEqual(G.width(0.0), 0.21, places=9)                    # 21 cm at the middle
        self.assertTrue(0.15 < G.width(0.0) / G.CHORD < 0.2)                    # about 1/6 of the chord
        self.assertAlmostEqual(G.width(G.TAU_C), G.TIP, places=6)               # the tips cut at a 1.2 cm flat
        self.assertTrue(G.SLOT[0] > G.LEAF_F > G.LEAF_B > G.FLANGE_B > G.SLOT[1] > G.POCKET_W > G.FIL_W > -G.DEPTH)
        n = G.numbers()
        self.assertAlmostEqual(n["t_lo"], 0.75)
        self.assertAlmostEqual(n["t_hi"], 1.95)
        self.assertLess(n["t_lo"], G.BEND)                                    # the slit crosses the bend: its top on the lean
        self.assertGreater(n["t_hi"], G.BEND)
        self.assertGreater(n["t_lo"], G.PLINTH_H)                             # and stays on the band
        self.assertLess(n["t_hi"], G.T_TOP)

    def test_filaments(self):
        fil = parts("e")["gill3_fil"]
        self.assertEqual(len(fil["verts"]), 8 * G.FILS)                       # 36 blades, none dropped
        uc = G.slit_chord(G.SLITS[2])
        for j in range(G.FILS):   # each blade inside the crescent (on the vertical part: x is u)
            box = fil["verts"][8 * j: 8 * j + 8]
            for x, _y, h in box:
                tau = h - S.FLOOR - G.T_MID
                if h < S.FLOOR + G.BEND:
                    self.assertGreater(x, uc - G.arc_off(tau) - 0.004)
                    self.assertLess(x, uc - G.arc_in(tau) + 0.004)

    def test_leaves(self):
        e = parts("e")
        uc = G.slit_chord(G.SLITS[2])
        a, b = e["gill3_leaf_a"]["verts"], e["gill3_leaf_b"]["verts"]
        lo = [v for v in a + b if v[2] < S.FLOOR + G.BEND - 1e-6]   # the vertical part: x is u, y is w
        self.assertTrue(lo)
        for x, y, h in lo:   # built open: both leaves out of the crescent, in their pockets under the band
            tau = h - S.FLOOR - G.T_MID
            self.assertTrue(x <= uc - G.arc_off(tau) + 1e-9 or x >= uc - G.arc_in(tau) - 1e-9, (x, h))
            self.assertTrue(G.POCKET_W < y < G.SLOT[0])
        for tau in (0.0, -0.3):   # shut (moved SLIDE together) they cover the crescent, the gap 2 * MEET
            h = S.FLOOR + G.T_MID + tau
            ra = [v[0] - G.SLIDE for v in a if abs(v[2] - h) < 1e-9 and v[1] == G.LEAF_F]
            rb = [v[0] + G.SLIDE for v in b if abs(v[2] - h) < 1e-9 and v[1] == G.LEAF_F]
            if not ra:
                continue
            self.assertLess(min(rb), uc - G.arc_off(tau))
            self.assertGreater(max(ra), uc - G.arc_in(tau))
            self.assertAlmostEqual(min(ra) - max(rb), 2 * G.MEET, places=9)
        for k in range(1, 5):   # open, a slit's leaves stay clear of the neighbours' crescents (2 cm)
            u_k, u_n = G.slit_chord(G.SLITS[k - 1]), G.slit_chord(G.SLITS[k])
            for tau in G.taus():
                self.assertLess(u_k - G.arc_in(tau) + G.TUCK + G.SLIDE, u_n - G.arc_off(tau) - 0.02)
                self.assertGreater(u_n - G.arc_off(tau) - G.TUCK - G.SLIDE, u_k - G.arc_in(tau) + 0.02)
        self.assertLess(G.OCT_D, -G.SLOT[0])                                  # slit 5's pocket passes behind the button
        for side in ("a", "b"):
            self.assertIn("origin", e[f"gill3_leaf_{side}"])
            self.assertEqual(e[f"gill3_seam_{side}"]["parent"], f"gill3_leaf_{side}")
        gd = (ROOT / "godot" / "ship" / "gill_row.gd").read_text(encoding="utf-8")
        self.assertIn(f"const SLIDE := {G.SLIDE:.3f}", gd)
        self.assertIn(f"const GASP_OPEN := {G.GASP_OPEN}", gd)

    def test_row_on_designs_spots(self):
        self.assertEqual([round(b - a, 6) for a, b in zip(G.SLITS, G.SLITS[1:])], [0.37] * 4)
        for k, xy in DESIGN.items():
            self.assertLess(math.dist(plan(G.SLITS[k - 1]), xy), 0.002, k)
        self.assertLess(math.dist(plan(G.BUTTON_S), BUTTON), 0.002)
        self.assertLess(G.BUTTON_T, G.BEND)                                   # the button on the vertical part
        self.assertTrue(G.BAND[0] < G.slit_chord(G.SLITS[0]) - G.SAG - G.RIM_W and G.BUTTON_S + G.OCT_FLATS / 2 + 0.1 < G.BAND[1])   # seam clear
        self.assertAlmostEqual(G.WALL_LEN, 4.051, places=3)

    def test_button(self):
        p = parts("e")
        floor = p["btn_floor"]["verts"]
        xs = [v[0] for v in floor]
        self.assertAlmostEqual(max(xs) - min(xs), G.OCT_FLATS, places=6)     # 24 across the flats
        self.assertAlmostEqual(min(v[1] for v in floor), -G.OCT_D, places=6)  # 2.5 deep
        dome = p["btn_dome"]["verts"]
        self.assertAlmostEqual(max(v[1] for v in dome), G.DOME_UP, places=6)  # 3.5 proud
        self.assertAlmostEqual(max(v[0] for v in dome) - min(v[0] for v in dome), 2 * G.DOME_R, places=3)
        r = [math.hypot(v[0] - G.BUTTON_S, v[2] - S.FLOOR - G.BUTTON_T) for v in p["btn_ring"]["verts"]]
        self.assertAlmostEqual(max(r) - min(r), G.RING_W, places=6)

class Mirror(unittest.TestCase):
    def test_west_mirrors_east(self):
        e, w = parts("e"), parts("w")
        shared = [n for n in e if n in w]
        self.assertGreater(len(shared), 30)
        for n in shared:
            self.assertEqual(key(e[n]["verts"], -1.0), key(w[n]["verts"]), n)
        self.assertEqual(set(e), set(w))
        for n in e:
            if "origin" in e[n]:
                self.assertEqual(w[n]["origin"], (-e[n]["origin"][0], *e[n]["origin"][1:]), n)

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

    def test_header_stops_at_the_ceiling(self):
        """Step 5: under the throat's ceiling the hall's header is only its skin on the hall face (by the corners),
        behind the band's cut 1 cm in, so no header face stands over the band's lean."""
        head = {q["name"]: q for q in S.throat_ceil({}, None)}["header"]["verts"]
        k, _v, m, dist = S.th_corner_chord()
        low = [v for v in head if v[2] < S.FLOOR + S.TH_H - 1e-6 and v[0] > 0]
        self.assertTrue(low)   # the skin is there
        for x, y, _h in low:
            self.assertLessEqual(m[0] * x + m[1] * y, dist - S.TH_HEAD_D + S.TH_SKIN + 5e-4)   # (the slabs mitre)
        ha, hb, hc = G.header_clip()   # the band's cut lies in front of the skin
        self.assertAlmostEqual(-(hc - (m[0] * G._MK[0] + m[1] * G._MK[1])), dist - S.TH_HEAD_D + 0.01, places=9)
        self.assertLess(S.TH_SKIN, 0.01)

    def test_cornice(self):
        """Step 5: the cornice along the band's top, from the roof line, its end cut on the header's face."""
        c = parts("e")["cornice"]["verts"]
        ha, hb, hc = G.header_clip()
        self.assertGreaterEqual(max(v[2] for v in c), S.FLOOR + S.TH_H)
        for x, y, _h in c:
            self.assertGreaterEqual(x, G.S0 - 1e-9)
            self.assertLessEqual(ha * x + hb * y, hc + 1e-6)

    def test_plinth(self):
        p = parts("e")
        self.assertAlmostEqual(max(v[2] for v in p["plinth"]["verts"]) - S.FLOOR, G.PLINTH_H, places=9)
        self.assertLessEqual(max(v[2] for v in p["plinth_line"]["verts"]) - S.FLOOR, G.PLINTH_H)
        self.assertGreaterEqual(G.LINE_H[1] - G.LINE_H[0], 0.024 - 1e-9)   # step 5: as thick as the concept's


if __name__ == "__main__":
    unittest.main()
