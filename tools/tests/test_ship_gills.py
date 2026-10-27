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


def build(side: str, hinge: str = "hall") -> dict[str, dict]:
    pid = f"station_vent_{side}"
    return {p["name"][len(pid) + 1:]: p for p in G.station_gills({"id": pid, "side": side, "hinge": hinge}, LAYOUT)}


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
        self.assertEqual((G.COVERS, G.PITCH, G.DRAWING_COVER_W, G.PROUD), (4, 0.3175, 0.30, 0.03))
        self.assertEqual((G.BAND, G.FIXED, G.CROWN_TOP), ((-0.80, 0.80), (0.47, 0.80), 2.05))
        self.assertAlmostEqual(G.BAND[0] + G.COVERS * G.PITCH, G.FIXED[0], places=3)
        self.assertEqual((G.BAR_W, G.BAR_H, G.BAR_GREEN), (0.05, (1.36, 1.88), (1.78, 1.84)))
        self.assertEqual((round(2 * G.LAMP_R, 3), G.LAMP_H), (0.172, (1.92, 2.02)))
        for i in range(G.COVERS):   # step 4: each rib centred in its pitch cell, narrower than the drawing's 30 cm
            cell = G.BAND[0] + i * G.PITCH
            self.assertAlmostEqual(G.cover_u(i) - cell, cell + G.PITCH - G.cover_u(i) - G.COVER_W)
            self.assertLess(G.COVER_W, G.DRAWING_COVER_W)

    def test_cover_outline(self):
        """Shut, each cover is COVER_W x 137 from the front; step 4: PROUD at its foot, 15..20 cm at mid-height,
        BEND_PROUD at its top, one smooth arch with its crown (ARCH: C1, no kink at the bend)."""
        self.assertAlmostEqual(G.cover_front(G.COVER_H[0]), G.PROUD)
        self.assertAlmostEqual(G.cover_front(G.PEAK_H), G.PEAK)
        self.assertTrue(0.15 <= G.PEAK <= 0.20)
        self.assertAlmostEqual(G.cover_front(G.COVER_H[1]), G.BEND_PROUD)
        self.assertAlmostEqual(G.rib_proud(G.CROWN_TOP), G.CROWN_PROUD)
        for k in range(1, len(G.ARCH) - 1):   # the slope is the same either side of every knot
            h = G.ARCH[k][0]
            self.assertAlmostEqual(G.arch(h - 1e-6)[1], G.arch(h + 1e-6)[1], places=3)
        hs = [G.BEND + (G.CROWN_TOP - G.BEND) * k / 40 for k in range(41)]
        self.assertGreaterEqual(min(G.rib_proud(h) for h in hs), 0.03)   # the crown stays proud of the leaning wall
        for hinge in ("hall", "mouth"):
            for i in range(G.COVERS):
                v, _ = G.cover_mesh(i, 0.0, hinge)
                us, hs = [p[0] for p in v], [p[2] for p in v]
                self.assertAlmostEqual(min(us), G.cover_u(i), places=6)
                self.assertAlmostEqual(max(us), G.cover_u(i) + G.COVER_W, places=6)
                self.assertAlmostEqual(min(hs), G.COVER_H[0], places=6)
                self.assertAlmostEqual(max(hs), G.COVER_H[1], places=6)
                self.assertGreater(min(p[1] for p in v), 0.0)   # never into the plate

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

    def test_hinges_on_the_cover_edges(self):
        for hinge, edge in (("hall", G.COVER_W), ("mouth", 0.0)):
            parts = build("e", hinge)
            for i in range(G.COVERS):
                p = parts[f"cover{i + 1}"]
                o = p["origin"]
                self.assertAlmostEqual(o[0], G.cover_u(i) + edge, places=9)
                self.assertAlmostEqual(o[1], G.PROUD / 2)
                self.assertEqual(parts[f"lip{i + 1}"]["parent"], f"station_vent_e_cover{i + 1}")
                # built at CALM_DEG: the hinge edge stays put, the free edge stands out into the throat
                free = G.cover_u(i) + G.COVER_W - edge
                far = max(p["verts"], key=lambda q: abs(q[0] - o[0]))
                self.assertAlmostEqual(abs(far[0] - o[0]), abs(free - o[0]) * math.cos(math.radians(G.CALM_DEG)),
                                       delta=0.02)
                self.assertGreater(far[1], 0.8 * G.COVER_W * math.sin(math.radians(G.CALM_DEG)))

    def test_hinge_choice(self):
        self.assertEqual(G.hinge_side({"hinge": "mouth"}), "mouth")
        with self.assertRaises(ValueError):
            G.hinge_side({"hinge": "up"})
        was = os.environ.pop("SHIP_GILLS_HINGE", None)
        try:
            self.assertEqual(G.hinge_side({}), G.HINGE)
        finally:
            if was is not None:
                os.environ["SHIP_GILLS_HINGE"] = was

    def test_ribs_convex_edges_set_back(self):
        """Step 3: each cover's section is convex across its width, its two edges SETBACK behind the crest (at least
        EDGE_MIN out of the wall) and inside its 30 cm; the crown continues the cover's top section."""
        for h in G.COVER_HS:
            f = G.cover_front(h)
            sec = G.cover_section(0.0, G.COVER_W, f)
            front = [p for p in sec if p[1] > G.edge_front(f) - G.CH - 1e-9]
            self.assertAlmostEqual(max(v for _, v in sec), f, places=6)
            self.assertAlmostEqual(G.edge_front(f), max(f - G.SETBACK, G.EDGE_MIN), places=9)
            self.assertTrue(all(0.0 <= u <= G.COVER_W for u, _ in sec))
            edges = [v for u, v in front if u < 1e-9 or u > G.COVER_W - 1e-9]
            self.assertTrue(edges and max(edges) <= f - min(G.SETBACK, f - G.EDGE_MIN) + 1e-9, h)
        mid = G.cover_section(0.0, G.COVER_W, G.cover_front(sum(G.COVER_H) / 2))
        self.assertGreaterEqual(max(v for _, v in mid) - mid[3][1] - G.CH, G.SETBACK - 1e-9)   # mid-height: 5 cm
        rows = G.rib_crown_rows(0.0, G.COVER_W, G.CALM_DEG)
        self.assertEqual((rows[0][1], rows[0][2]), (0.0, G.COVER_W))
        self.assertAlmostEqual(rows[0][3], G.cover_front(G.COVER_H[1]), places=2)
        self.assertAlmostEqual(rows[-1][2] - rows[-1][1], G.COVER_W - 2 * G.CROWN_INSET)
        self.assertEqual((rows[0][5], rows[-1][5]), (G.CALM_DEG, 0.0))   # its foot turned as the calm cover

    def test_window_and_seams(self):
        """Step 4: one window through the plate over the well; a red seam on the well's back in each of the five gaps
        (clear of the shut ribs), behind the cyan; every part inside the band and the hull."""
        self.assertEqual(len(G.gap_u()), G.COVERS + 1)
        for k in range(G.COVERS + 1):
            a, b = G.seam(k)
            self.assertTrue(G.WIN_U[0] <= a < b <= G.WIN_U[1], k)
            for i in range(G.COVERS):
                self.assertTrue(b < G.cover_u(i) or a > G.cover_u(i) + G.COVER_W, (k, i))
        for side in "ew":
            s = -1.0 if side == "w" else 1.0
            parts = build(side)
            self.assertEqual(sorted(n for n in parts if n.startswith("seam")), [f"seam{k}" for k in range(1, 6)])
            self.assertFalse([n for n in parts if n.startswith("jamb")])
            for k in range(1, 6):
                self.assertLess(max(p[1] for p in parts[f"seam{k}"]["verts"]), -G.WELL_MIN)
            for name, p in parts.items():
                if name.startswith(("cover", "lip", "flank", "crown", "seam", "band", "cool", "fixed")):
                    for x, v, z in p["verts"]:
                        u, d, h = s * x, -v, z - S.FLOOR
                        if d > 0:   # as the well: inside the hull, or inside the old wall's 20 cm body where the
                            #             hull's face itself is thin (the mouth end's foot)
                            self.assertTrue(G.skin_at(LAYOUT, side, u, d, h) > 0.0 or d <= 0.2 + 1e-6,
                                            f"{side} {name} {u:.2f} {h:.2f}")
                        self.assertTrue(G.BAND_PLATE[0] - 1e-6 <= u <= G.BAND_PLATE[1] + 1e-6, f"{side} {name} {u}")

    def test_gaps(self):
        """Step 4 (option A): the slots between ribs 8..10 cm at the peak shut and calm, wider at the exhale."""
        for deg in (0.0, G.CALM_DEG):
            self.assertTrue(0.08 <= G.neighbour_gap(deg) <= 0.10, (deg, G.neighbour_gap(deg)))
        self.assertGreater(G.neighbour_gap(G.OPEN_DEG), G.neighbour_gap(0.0))

    def test_covers_clear_of_the_well(self):
        """Every cover (its lit chamfers and flank liners too) stays in front of the wall's face through 0..70 deg."""
        for hinge in ("hall", "mouth"):
            for deg in range(0, 71, 10):
                for i in range(G.COVERS):
                    for mesh in (G.cover_mesh, G.lip_mesh, G.flank_mesh):
                        self.assertGreater(min(p[1] for p in mesh(i, deg, hinge)[0]), 0.0, (hinge, deg, i))

    def test_calm_choice(self):
        self.assertEqual(G.calm_deg({"calm": 22}), 22.0)
        with self.assertRaises(ValueError):
            G.calm_deg({"calm": 80})
        was = os.environ.pop("SHIP_GILLS_CALM", None)
        try:
            self.assertEqual(G.calm_deg({}), G.CALM_DEG)
        finally:
            if was is not None:
                os.environ["SHIP_GILLS_CALM"] = was

    def test_covers_clear_at_mixed_angles(self):
        """Step 3: neighbours at different angles (the calm wave, the slam one after another, the exhale) never
        touch, at the foot, the bow and the top of the convex ribs, while they stay within NEIGHBOUR_DEG of each other
        (the animation's rule: a rib's deep middle near its hinge swings into its shut neighbour's edge from 22 deg)."""
        angles = range(0, 71, 4)
        for hinge in ("hall", "mouth"):
            for h in (G.COVER_H[0], sum(G.COVER_H) / 2, G.COVER_H[1]):
                for da in angles:
                    for db in (d for d in angles if abs(d - da) <= G.NEIGHBOUR_DEG):
                        secs = []
                        for i, deg in ((1, da), (2, db)):
                            sec = G.cover_section(G.cover_u(i), G.cover_u(i) + G.COVER_W, G.cover_front(h))
                            secs.append(hull2([G.rot(p, G.hinge_u(i, hinge), G.swing(hinge) * deg) for p in sec]))
                        self.assertTrue(apart(*secs, 0.002), f"{hinge} h {h:.2f} {da}/{db} deg")

    def test_covers_clear_through_the_swing(self):
        """Neighbouring covers at the same angle, 0 to the exhale's 70 deg, never touch (plan sections at the bow)."""
        h = sum(G.COVER_H) / 2
        for hinge in ("hall", "mouth"):
            for deg in range(0, 71, 2):
                secs = []
                for i in range(G.COVERS):
                    hu, sw = G.hinge_u(i, hinge), G.swing(hinge)
                    sec = G.cover_section(G.cover_u(i), G.cover_u(i) + G.COVER_W, G.cover_front(h))
                    secs.append(hull2([G.rot(p, hu, sw * deg) for p in sec]))
                for a, b in zip(secs, secs[1:]):
                    self.assertTrue(apart(a, b, 0.002), f"{hinge} {deg} deg")

    def test_well_inside_the_hull(self):
        """Every point of the well (walls, glows, honeycomb) keeps SKIN_M of hull behind it, or stays inside the old
        wall's 20 cm body where the hull is thinner than that at the wall's face (the mouth end, the foot)."""
        for side in "ew":
            s = -1.0 if side == "w" else 1.0
            parts = build(side)
            for name in ("well", "cool", "heat", "mesh"):
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
