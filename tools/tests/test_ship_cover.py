"""The gill cover pilot (art #263, 2026-10-29; tools/blender/ship_interior_cover.py, godot/ship/gill_cover.gd,
docs/ship.md "The gill cover pilot"): one rigid curved cover on the clean east wall: its size and place, the hinge on
its outer edge as the moving parts' origin, the pocket cut into the band under it, and no point of the plate behind
the wall's face over the whole swing (0..35 deg, the open swing's overshoot included). Plain Python."""

from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import ship_interior as S  # noqa: E402
import ship_interior_cover as C  # noqa: E402
import ship_interior_throat as T  # noqa: E402

GD = (ROOT / "godot" / "ship" / "gill_cover.gd").read_text(encoding="utf-8")


def parts(side: str = "e") -> dict:
    return {p["name"]: p for p in T.th_wall({"side": side}, {})}


def gd_const(name: str) -> float:
    return float(re.search(rf"^const {name} := ([-0-9.]+)", GD, re.M).group(1))


def wall(p) -> tuple[float, float, float]:
    """A piece point (x, y, h) back to the wall's (u, t, w) (below the fold)."""
    x, y, h = p
    return x, h - S.FLOOR, y


class Cover(unittest.TestCase):
    def test_size_and_place(self):
        plate = [wall(v) for v in parts()["cover3_plate"]["verts"]]
        us, ts = [p[0] for p in plate], [p[1] for p in plate]
        self.assertAlmostEqual(max(ts) - min(ts), 2 * C.HALF, places=6)
        self.assertTrue(1.15 < max(ts) - min(ts) <= 1.20)                              # about 120 cm tall
        self.assertTrue(0.25 <= C.WIDTH <= 0.30 + 1e-9)                                     # 25-30 cm wide
        self.assertAlmostEqual((min(ts) + max(ts)) / 2, C.T_MID, places=6)
        self.assertAlmostEqual(C.U_HINGE + C.WIDTH / 2, 2.69, places=9)                # the middle slit's place
        self.assertGreater(min(us), T.S_F1 + 0.1)                                      # clear of the frame
        self.assertLess(max(us), T.JAMB_U - 0.5)                                       # and of the jamb (the button)
        self.assertGreater(min(ts), T.PLINTH_H + 0.1)
        self.assertLess(max(ts) + 0.1, T.FOLD)

    def test_hinge_on_the_outer_edge(self):
        p = parts()
        axis = T.point(C.AXIS_U, C.T_MID, C.AXIS_W)
        for n in ("cover3_plate", "cover3_rim", "cover3_knuckle"):
            self.assertEqual(p[n]["origin"], axis, n)
        for n in ("cover3_hinge", "cover3_pocket", "cover3_glow"):
            self.assertIsNone(p[n].get("origin"), n)
        plate = [wall(v) for v in p["cover3_plate"]["verts"]]
        self.assertAlmostEqual(min(u for u, _t, _w in plate), C.U_HINGE, places=6)    # the edge toward the ramp
        self.assertTrue(all(u > C.AXIS_U for u, _t, _w in plate))                      # all on the hall's side
        self.assertGreater(C.AXIS_W, C.KNUCKLE_R)                                      # the knuckles clear the wall

    def test_rests_on_the_wall_shut(self):
        plate = [wall(v) for v in parts()["cover3_plate"]["verts"]]
        self.assertAlmostEqual(min(w for *_, w in plate), C.W_REST, places=9)          # no face on the wall's plane
        self.assertGreater(C.W_REST, 0.002)                                            # (no z-fighting at 0 deg)
        mid = [(u, w) for u, t, w in plate if abs(t - C.T_MID) < 0.02]
        self.assertGreater(max(w for _u, w in mid), C.BULGE)                           # domed out
        edge = max(mid)                                                                # the open edge stands off
        self.assertGreater(edge[1], 0.01)

    def test_no_wall_intersection_over_the_swing(self):
        plate = [wall(v) for v in parts()["cover3_plate"]["verts"]]
        knuckle = [wall(v) for v in parts()["cover3_knuckle"]["verts"]]
        for deg in [d * 0.5 for d in range(int(C.MAX_DEG * 2) + 1)]:
            for u, t, w in plate + knuckle:
                _u, _t, w2 = C.turn((u, t, w), deg)
                self.assertGreater(w2, 0.0015, (deg, u, t, w))
        self.assertGreaterEqual(C.MAX_DEG, gd_const("OPEN_DEG") * 1.1)                 # the overshoot inside the sweep

    def test_open_swing_overshoot_and_gasp(self):
        z, w0 = gd_const("SPRING_Z"), gd_const("SPRING_W")
        over = math.exp(-math.pi * z / math.sqrt(1 - z * z))
        a0 = gd_const("GASP_DEG")
        peak = gd_const("OPEN_DEG") + (gd_const("OPEN_DEG") - a0) * over
        self.assertTrue(gd_const("OPEN_DEG") < peak < C.MAX_DEG, peak)                 # a small overshoot, in the sweep
        self.assertTrue(0.05 < over < 0.15, over)
        self.assertTrue(6.0 <= a0 <= 10.0 and 25.0 <= gd_const("OPEN_DEG") <= 32.0)
        self.assertGreater(w0, 5.0)

    def test_pocket_in_the_band(self):
        p = parts()
        band = [wall(v) for v in p["band"]["verts"]]
        self.assertTrue(all(abs(w) < 1e-9 for *_, w in band))
        rows = C.hole_rows()
        for t, ul, ur in rows:   # the hole: inside the plate's outer arc, a hair past its open edge
            self.assertGreater(ul, C.outer(t) + 0.01)
            self.assertLess(ur, C.inner(t) + C.EDGE_GAP + 1e-9)                         # past the open edge mid-height,
        self.assertGreater(rows[len(rows) // 2][2], C.inner(C.T_MID) + 0.005)
        for t, ul, ur in (rows[0], rows[-1]):                                           # under the plate at the tips
            self.assertLess(ur, C.inner(t))
        floor = [wall(v) for v in p["cover3_glow"]["verts"]]
        self.assertTrue(all(abs(w + C.POCKET_D) < 1e-9 for *_, w in floor))
        self.assertGreater(C.POCKET_D, 0.03)
        self.assertLess(C.POCKET_D, 0.2)                                               # in front of the wall's back
        # the band's quads leave the hole open: no band quad's centre inside the hole
        for i in range(0, len(band), 4):
            u = sum(q[0] for q in band[i:i + 4]) / 4
            t = sum(q[1] for q in band[i:i + 4]) / 4
            if abs(t - C.T_MID) < C.HOLE_HALF:
                self.assertFalse(C.HOLE_L(t) + 1e-6 < u < C.HOLE_R(t) - 1e-6, (u, t))

    def test_east_only(self):
        e, w = parts("e"), parts("w")
        self.assertEqual(sorted(n for n in e if n.startswith("cover3_")),
                         ["cover3_glow", "cover3_hinge", "cover3_knuckle", "cover3_plate", "cover3_pocket", "cover3_rim"])
        self.assertFalse([n for n in w if n.startswith("cover")])

    def test_controller_never_turns_inward(self):
        # every write to the angle is the gasp's (>= 0), the spring's (>= its start) or the cough's outward shudder
        self.assertIn("absf(sin(_cough_t", GD)
        self.assertNotIn("angle = -", GD)

    def test_controller_names(self):
        for part in ("plate", "rim", "knuckle", "glow"):
            self.assertIn(f'"{part}"', GD)
        self.assertIn("cover%d_%s", GD)


if __name__ == "__main__":
    unittest.main()
