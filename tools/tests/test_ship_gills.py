"""The ray's gills (art #263, gills step 2; docs/ship.md "Station 1 rebuilt: the ray's gills"): `station_gills`
against the design drawing in cm (prime-game-design ideas/ship-components/vent-wall/drawing/drawing.js): the covers'
outline, pitch and proud, the slits, the fifth arch, the bar and the lamp; the west piece the east one's mirror; each
cover's hinge on its edge (either side) and its free edge swinging out; neighbouring covers clear of each other through
the swing; the well never past the hull's skin. Pure Python: needs neither Blender, Godot nor the raw files."""

from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))
import ship_interior as S  # noqa: E402,F401  (ship_interior imports the gills at its end)
import ship_interior_gills as G  # noqa: E402
from runner import ship_layout  # noqa: E402

LAYOUT = ship_layout.load()


def build(side: str) -> dict[str, dict]:
    pid = f"station_vent_{side}"
    return {p["name"][len(pid) + 1:]: p for p in G.station_gills({"id": pid, "side": side}, LAYOUT)}


def hull2(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def apart(a, b, gap: float = 0.0) -> bool:
    """Two convex polygons more than gap apart along some edge normal (the separating axis test)."""
    for poly in (a, b):
        for p, q in zip(poly, poly[1:] + poly[:1]):
            nx, ny = q[1] - p[1], p[0] - q[0]
            ln = math.hypot(nx, ny)
            pa = [(x * nx + y * ny) / ln for x, y in a]
            pb = [(x * nx + y * ny) / ln for x, y in b]
            if min(pb) - max(pa) > gap or min(pa) - max(pb) > gap:
                return True
    return False


class ShipGillsTest(unittest.TestCase):
    def test_drawing_numbers(self):
        self.assertEqual((G.DRAWING_COVER_W, G.PROUD), (0.30, 0.035))
        self.assertEqual((G.BAND, G.FIXED, G.CROWN_TOP, G.RIB_H), ((-0.80, 0.80), (0.52, 0.80), 2.05, (0.08, 2.05)))
        # step 7: the concept's 4 ribs of 22 cm, 12 cm slots, an equal end gap at both ends of the rib band
        self.assertEqual((G.COVERS, G.COVER_W, G.SLOT_W), (4, 0.22, 0.12))
        self.assertAlmostEqual(G.cover_u(0) - G.BAND[0], G.END_GAP, places=9)
        self.assertAlmostEqual(G.FIXED[0] - G.cover_u(G.COVERS - 1) - G.COVER_W, G.END_GAP, places=9)
        self.assertGreaterEqual(G.END_GAP, 0.035)
        self.assertGreaterEqual(G.FIXED[1] - G.FIXED[0] - 2 * G.CH, 2 * G.HAND_HW)   # the scanner fits the fifth arch
        self.assertEqual((G.BAR_W, G.BAR_H, G.BAR_GREEN), (0.05, (1.36, 1.88), (1.78, 1.84)))
        self.assertEqual((round(2 * G.LAMP_R, 3), G.LAMP_H), (0.172, (1.92, 2.02)))
        for i in range(1, G.COVERS):   # every slot SLOT_W, the ribs narrower than the drawing's 30 cm
            self.assertAlmostEqual(G.cover_u(i) - G.cover_u(i - 1) - G.COVER_W, G.SLOT_W, places=9)
        self.assertLess(G.COVER_W, G.DRAWING_COVER_W)

    def test_rib_profile(self):
        """Step 6: one profile from the foot to the top (the concept's chunky bow): PROUD at the foot, LOW at LOW_H (the
        fuller lower bow), PEAK at PEAK_H, CROWN_PROUD at the top; one C2 quintic, the proud rising to the bend and
        falling after it, no dip; never steeper than the leaning wall at the top."""
        self.assertAlmostEqual(G.cover_front(G.RIB_H[0]), G.PROUD)
        self.assertAlmostEqual(G.cover_front(G.LOW_H), G.LOW)
        self.assertAlmostEqual(G.cover_front(G.PEAK_H), G.PEAK)
        self.assertAlmostEqual(G.rib_proud(G.CROWN_TOP), G.CROWN_PROUD)
        self.assertGreaterEqual(G.LOW, 0.13)    # the lower half bows too (step 5: 7.7 cm at 0.74, step 6: 12.5)
        n = 400
        hs = [G.RIB_H[0] + (G.CROWN_TOP - G.RIB_H[0]) * k / n for k in range(n + 1)]
        pr = [G.rib_proud(h) for h in hs]
        top = max(range(n + 1), key=lambda k: pr[k])
        self.assertTrue(G.PEAK_H <= hs[top] <= G.BEND + 0.01, hs[top])
        self.assertTrue(all(b >= a for a, b in zip(pr[:top], pr[1:top + 1])))     # rising to the bend
        self.assertTrue(all(b <= a for a, b in zip(pr[top:], pr[top + 1:])))      # falling over the leaning wall
        self.assertTrue(0.19 <= max(pr) <= 0.20, max(pr))   # step 7: the fuller ")", about 20 cm at the bend
        self.assertLessEqual(G.ARCH_TOP_SLOPE, G.IN / (G.TOP - G.BEND))
        self.assertGreaterEqual(min(G.rib_proud(h) for h in hs if h >= G.BEND), 0.04)

    def test_one_rib_piece(self):
        """Step 6 (the manager's decision): each rib one piece from its foot to its rounded top, one profile: its full
        width at every row under the rounded top (no width change), rows at most 6 cm apart, its crest's and edges'
        proud out of the wall changing at most half as fast as the height between rows (no step, groove or collar at the bend); its back RIB_SINK into
        the wall's face at every row (no gap behind its flanks); no crown pieces left."""
        parts = build("e")
        self.assertFalse([n for n in parts if n.startswith("crown") and n not in ("crown5", "crown5_edge")])
        self.assertFalse([n for n in parts if n.startswith("flank") and n.endswith("u")])
        self.assertIn(G.BEND, G.RIB_HS)
        for i in range(G.COVERS):
            u0, u1 = G.cover_u(i), G.cover_u(i) + G.COVER_W
            rows = G.rib_rows(u0, u1)
            main = rows[:len(G.RIB_HS)]
            for h, sec, b, f, e in main:
                self.assertAlmostEqual(min(u for u, _ in sec), u0, places=9)
                self.assertAlmostEqual(max(u for u, _ in sec), u1, places=9)
                self.assertAlmostEqual(min(v for _, v in sec), G.wall_back(h), places=9)
                self.assertAlmostEqual(max(v for _, v in sec), f, places=6)
            for (ha, _, ba, fa, ea), (hb, _, bb, fb, eb) in zip(main, main[1:]):   # out of the wall's face
                self.assertLessEqual(hb - ha, 0.06)
                self.assertLessEqual(abs((fb - bb) - (fa - ba)), 0.5 * (hb - ha), (i, ha))
                self.assertLessEqual(abs((eb - bb) - (ea - ba)), 0.5 * (hb - ha), (i, ha))
            v, _ = G.cover_mesh(i)
            self.assertAlmostEqual(min(p[2] for p in v), G.RIB_H[0], places=9)
            self.assertTrue(G.RIB_H[1] - 0.002 <= max(p[2] for p in v) <= G.RIB_H[1], max(p[2] for p in v))
            self.assertGreater(len(rows), len(main))   # the rounded top

    def test_mirror(self):
        e, w = build("e"), build("w")
        self.assertEqual(set(e), set(w))
        for name, p in e.items():
            q = w[name]
            self.assertEqual(len(p["verts"]), len(q["verts"]), name)
            for a, b in zip(p["verts"], q["verts"]):
                self.assertAlmostEqual(a[0], -b[0], places=9)
                self.assertEqual(a[1:], b[1:])
            if "origin" in p:
                self.assertAlmostEqual(p["origin"][0], -q["origin"][0])

    def test_rib_origin_on_its_axis(self):
        """Each rib's origin the foot of its rocking axis (its back's middle); its lips and both flank liners its
        children, so the motion step rocks them together."""
        parts = build("e")
        for i in range(G.COVERS):
            a0, a1 = G.rib_axis(i)
            o = parts[f"cover{i + 1}"]["origin"]
            self.assertAlmostEqual(o[0], G.cover_u(i) + G.COVER_W / 2, places=9)
            self.assertAlmostEqual(o[1], G.wall_back(G.RIB_H[0]))
            self.assertAlmostEqual(o[2], S.FLOOR + G.RIB_H[0])
            self.assertAlmostEqual(a1[1], G.wall_back(G.RIB_H[1]))
            for child in (f"lip{i + 1}", f"flank{i + 1}", f"flank{i + 1}b"):
                self.assertEqual(parts[child]["parent"], f"station_vent_e_cover{i + 1}", child)
        self.assertEqual(parts["flank1"]["mat"], "int_cyan__vent_flank")
        self.assertEqual(parts["flank1b"]["mat"], "int_cyan__vent_flank2")

    def test_ribs_convex_edges_set_back(self):
        """Step 3: each rib's section is convex across its width, its two edges SETBACK behind the crest (at least
        EDGE_MIN out of its back) and inside its width; step 6: its flanks square to the wall (no undercut)."""
        self.assertEqual(G.UNDERCUT, 0.0)
        for h in G.RIB_HS:
            f, b = G.cover_front(h), G.wall_back(h)
            sec = G.rib_section(0.0, G.COVER_W, f, b)
            self.assertAlmostEqual(max(v for _, v in sec), f, places=6)
            self.assertAlmostEqual(G.edge_front(f, b), max(f - G.SETBACK, b + G.EDGE_MIN - 0.006), places=9)
            self.assertTrue(all(0.0 <= u <= G.COVER_W for u, _ in sec))

    def test_window_and_seams(self):
        """Step 4: one window through the plate over the well; a red seam on the well's back in each gap (clear of the
        ribs), behind the cyan; every part inside the band and the hull."""
        self.assertEqual(len(G.gap_u()), G.COVERS + 1)
        for k in range(G.COVERS + 1):
            a, b = G.seam(k)
            self.assertTrue(G.WIN_U[0] <= a < b <= G.WIN_U[1], k)
            for i in range(G.COVERS):
                self.assertTrue(b < G.cover_u(i) or a > G.cover_u(i) + G.COVER_W, (k, i))
        for side in "ew":
            s = -1.0 if side == "w" else 1.0
            parts = build(side)
            self.assertEqual(sorted(n for n in parts if n.startswith("seam")),
                             sorted(f"seam{k}" for k in range(1, G.COVERS + 2)))
            for k in range(1, G.COVERS + 2):
                self.assertLess(max(p[1] for p in parts[f"seam{k}"]["verts"]), -G.WELL_MIN)
            for name, p in parts.items():
                if name.startswith(("cover", "lip", "flank", "crown", "seam", "band", "cool", "fixed")):
                    for x, v, z in p["verts"]:
                        u, d, h = s * x, -v, z - S.FLOOR
                        if d > 0:   # as the well: inside the hull, or inside the old wall's 20 cm body
                            self.assertTrue(G.skin_at(LAYOUT, side, u, d, h) > 0.0 or d <= 0.2 + 1e-6,
                                            f"{side} {name} {u:.2f} {h:.2f}")
                        self.assertTrue(G.BAND_PLATE[0] - 1e-6 <= u <= G.BAND_PLATE[1] + 1e-6, f"{side} {name} {u}")

    def test_gaps(self):
        """Step 6: the slot between ribs 0.44..0.6 of a rib's width (the concept's 0.45..0.6) and over 9 cm, the same
        at every height (the ribs' flanks square and parallel)."""
        for h in (0.3, G.LOW_H, G.PEAK_H):
            g = G.neighbour_gap(h)
            self.assertTrue(0.09 <= g and 0.44 <= g / G.COVER_W <= 0.6, (h, g))
            self.assertAlmostEqual(g, G.PITCH - G.COVER_W, places=6)

    def test_glow_bands_and_slots(self):
        """Step 7: the well's back full of cyan (0.25..0.4 low, fading up from 40 cm), the lowest band a darker pocket
        under it; the ribs' flank fronts still the brightest (the slot's edges); the slots lit on up the leaning wall to
        SLOT_TOP between the ribs (never more than 4 mm under one), the cool's children."""
        es = [b[3] for b in G.COOL_BANDS + G.SLOT_BANDS]
        self.assertEqual(es[1:], sorted(es[1:], reverse=True))
        self.assertTrue(0.25 <= es[0] < es[1] <= 0.40, es)
        self.assertGreater(G.FLANK_E, max(es))
        self.assertTrue(G.FLANK2_E < G.FLANK_E)
        self.assertEqual(G.COOL_BANDS[0][0], G.WELL_H[0])
        self.assertEqual(G.COOL_BANDS[-1][1], G.WELL_H[1])
        parts = build("e")
        for name in ["cool" + b[2] for b in G.COOL_BANDS[1:]] + ["slots6", "slots7"]:
            self.assertEqual(parts[name]["parent"], "station_vent_e_cool", name)
        self.assertEqual(parts["heat_slots"]["parent"], "station_vent_e_heat")
        self.assertAlmostEqual(max(p[2] for p in parts["slots7"]["verts"]) - S.FLOOR, G.SLOT_TOP)
        for k in range(G.COVERS + 1):
            for h in (G.BEND, 1.7, G.SLOT_TOP):
                lo, hi = G.slot_span(k, h)
                self.assertGreater(hi - lo, G.END_GAP - 0.01 if k in (0, G.COVERS) else 0.09, (k, h))
                for i in range(G.COVERS):
                    c0, c1 = G.cover_u(i), G.cover_u(i) + G.COVER_W
                    self.assertLessEqual(min(hi, c1) - max(lo, c0), 0.0041, (k, i, h))

    def test_hood_and_sill(self):
        """Step 7: the arched hood over the slots: its lip an arch over the rib band, lowest at the ends, stepping up
        over the fifth arch above its lamp; every rib runs on up into it (its top above the lip) and its crest stays
        1 cm behind the hood's face there (the rib flows in, no square-cut top shows); the ribs' and the fifth arch's
        feet seated on the bronze sill."""
        mid = (G.BAND[0] + G.FIXED[0]) / 2
        self.assertAlmostEqual(G.hood_lip(mid), G.HOOD_HI, places=6)
        self.assertAlmostEqual(G.hood_lip(G.BAND[0]), G.HOOD_LO, places=6)
        self.assertAlmostEqual(G.hood_lip(G.HOOD_U[1]), G.HOOD_LIP5, places=6)
        self.assertGreater(G.HOOD_LIP5, G.LAMP_H[1] + 0.03)
        us = G.hood_us()
        self.assertEqual(us, sorted(us))
        for i in range(G.COVERS):
            for u in (G.cover_u(i), G.cover_u(i) + G.COVER_W / 2, G.cover_u(i) + G.COVER_W):
                h0 = G.hood_lip(u)
                self.assertLess(h0, G.RIB_H[1] - G.TOP_R - 0.05, (i, u))
                h1 = h0 + (G.HOOD_R + 0.002) * G.LEAN_H   # over the nose, every row up to the rounded top under the hood's face
                for k in range(11):
                    h = h1 + (G.RIB_H[1] - h1) * k / 10
                    crest = (G.cover_front(h) - G.V.cv(h)) * G.NORM_V   # out of the leaning wall's face
                    self.assertLess(crest, G.hood_front(u, h) - 0.008, (i, u, h))
        self.assertLessEqual(G.RIB_H[0], G.SILL_H - 0.005)
        self.assertGreaterEqual(G.SILL_P, max(G.PROUD, G.edge_front(G.PROUD, G.wall_back(G.RIB_H[0]))) + 0.01)
        parts = build("e")
        for name in ("hood", "hood_edge", "sill"):
            self.assertIn(name, parts)
        for k in range(1, G.COVERS + 2):
            for st in G.FLOOR_STEPS:
                p = parts[f"{st[0]}{k}"]
                self.assertEqual(p["parent"], "station_vent_e_cool")
                self.assertTrue(all(S.FLOOR < z < S.FLOOR + 0.004 for _, _, z in p["verts"]))
        es = [st[1] for st in G.FLOOR_STEPS]
        self.assertEqual(es, sorted(es))   # the edge faded: dimmest outside

    def test_rock_clear(self):
        """The motion built in (option b): a rib rocked +-RIB_ROCK_DEG about its axis stays 2 cm clear of its
        neighbours (rocked either way or not), its back never lifts off the wall's face (no gap opens) and digs at most
        3 cm into the wall (into the well's window or the leaning wall's 20 cm body)."""
        rows = {i: G.rib_rows(G.cover_u(i), G.cover_u(i) + G.COVER_W)[:len(G.RIB_HS)] for i in range(G.COVERS)}
        for deg in (-G.RIB_ROCK_DEG, G.RIB_ROCK_DEG):
            for i in range(G.COVERS):
                for h, sec, b, f, e in rows[i]:
                    for u, v in sec:
                        if v < b + 1e-9:   # the back's points
                            p = G.rock((u, v, h), i, deg)
                            self.assertLessEqual(p[1], G.wall_v(p[2]) + 0.0005, (deg, i, h, u))
                            self.assertGreaterEqual(p[1], G.wall_v(p[2]) - 0.03, (deg, i, h, u))
            for i in (0, G.COVERS - 1):   # step 7: the end ribs 2 cm clear of the casing at either end
                for k in range(0, len(G.RIB_HS), 5):
                    h = rows[i][k][0]
                    us = [G.rock((u, v, h), i, deg)[0] for u, v in rows[i][k][1]]
                    self.assertGreater(min(us), G.BAND[0] + 0.02 if i == 0 else -9.0, (deg, i, h))
                    self.assertLess(max(us), G.FIXED[0] - 0.02 if i else 9.0, (deg, i, h))
            for i in range(G.COVERS - 1):
                for d2 in (-deg, 0.0, deg):
                    for k in range(0, len(G.RIB_HS), 5):
                        h = rows[i][k][0]
                        a = [G.rock((u, v, h), i, deg) for u, v in rows[i][k][1]]
                        c = [G.rock((u, v, h), i + 1, d2) for u, v in rows[i + 1][k][1]]
                        self.assertTrue(apart(hull2([p[:2] for p in a]), hull2([p[:2] for p in c]), 0.02),
                                        (deg, d2, i, h))

    def test_well_inside_the_hull(self):
        """Every point of the well (walls, glows, honeycomb) keeps SKIN_M of hull behind it, or stays inside the old
        wall's 20 cm body where the hull is thinner than that at the wall's face (the mouth end, the foot)."""
        for side in "ew":
            s = -1.0 if side == "w" else 1.0
            parts = build(side)
            for name in ["well", "heat"] + ["cool" + b[2] for b in G.COOL_BANDS]:
                for x, v, z in parts[name]["verts"]:
                    u, d, h = s * x, -v, z - S.FLOOR
                    skin = G.skin_at(LAYOUT, side, u, d, h)
                    self.assertTrue(skin >= G.SKIN_M - 0.005 or d <= 0.2 + 1e-6,
                                    f"{side} {name} u {u:.2f} h {h:.2f} d {d:.3f}: hull {skin:.3f}")
                    self.assertLessEqual(d, G.WELL_D + 0.011)

    def test_lit_well_depth(self):
        w = G.well_depth(LAYOUT, "e")
        flat = [d for row in w["d"] for d in row]
        self.assertAlmostEqual(max(flat), G.WELL_D)
        self.assertGreaterEqual(min(flat), G.WELL_MIN)


if __name__ == "__main__":
    unittest.main()
