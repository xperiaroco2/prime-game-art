"""The clean throat (art #263, 2026-10-29; tools/blender/ship_interior_throat.py, docs/ship.md "The clean throat"):
the profile (vertical to 2.10, a 25 cm cove to the flat 2.30 ceiling; the tunnel keeps 1.45 / 0.55), the walls, the
ramp frame and the hall jambs in place of the gills, the arch and the corner pilasters, the west a mirror of the east,
every surface ending on one face, and the hull's sample derived from the profile. Plain Python."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import ship_hull_shape as H  # noqa: E402
import ship_interior as S  # noqa: E402
import ship_interior_throat as T  # noqa: E402

LAYOUT = tomllib.loads((ROOT / "layouts" / "ship" / "interior.toml").read_text(encoding="utf-8"))
PLACE = LAYOUT["place"]
THROAT = next(r for r in tomllib.loads((ROOT / "layouts" / "ship" / "ship.toml").read_text(encoding="utf-8"))["rooms"]
              if r["id"] == "throat")


def parts(builder, **args) -> dict:
    return {p["name"]: p for p in builder(args, {})}


class Profile(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(THROAT["chamfer"], [2.10, 0.25])                    # the engineer's yes: fold at 2.10
        self.assertEqual(THROAT["tunnel_chamfer"], [1.45, 0.55])             # the tunnel keeps its profile
        self.assertEqual((T.FOLD, T.COVE, T.CEIL), (2.10, 0.25, 2.30))
        self.assertEqual((S.TUN_BEND, S.TUN_IN), (1.45, 0.55))
        self.assertEqual(tuple(H.TUN_CH), (1.45, 0.55))
        self.assertGreater(T.FOLD - 1.95, 0.149)                             # 15 cm over the slits' top (1.95)
        self.assertAlmostEqual(T.S_F1, 1.668, places=3)                      # the frame's aft face on the wall
        self.assertAlmostEqual(T.JAMB_V, 0.131, places=3)                    # the jamb's end face's depth

    def test_hull_sample_from_the_profile(self):
        self.assertAlmostEqual(H.chamfer_outer(1.45, 0.55, 2.30), 0.389, places=3)   # the old hard-coded 0.38
        self.assertAlmostEqual(H.chamfer_outer(2.10, 0.25, 2.30), 0.080, places=3)
        src = (ROOT / "tools" / "blender" / "ship_hull_shape.py").read_text(encoding="utf-8")
        self.assertNotIn("ch_in - 0.17", src)


class Layout(unittest.TestCase):
    def test_pieces(self):
        ids = [p[0] for p in PLACE]
        for gone in ("th_gills_e", "th_gills_w", "th_arch"):
            self.assertNotIn(gone, ids)
        for pid in ("th_wall_e", "th_wall_w", "th_frame", "th_jambs", "throat_ceil"):
            self.assertEqual(ids.count(pid), 1, pid)
        e = next(p for p in PLACE if p[0] == "th_wall_e")
        w = next(p for p in PLACE if p[0] == "th_wall_w")
        self.assertEqual((e[1][0], e[1][1], e[2]), (-w[1][0], w[1][1], -w[2]))   # mirrored
        self.assertEqual(e[1][:2], THROAT["points"][1])                          # at the mouth's corner

    def test_no_pilaster_at_the_corners(self):
        for p in PLACE:
            if p[0].startswith("hall_pilaster"):
                for k in (THROAT["points"][2], THROAT["points"][3]):
                    self.assertGreater(math.dist(p[1][:2], k), 0.5, p)


class Walls(unittest.TestCase):
    def test_mirror(self):
        e, w = parts(T.th_wall, side="e"), parts(T.th_wall, side="w")
        # the gill set stands on the east wall only for now (test_ship_gillset); the rest is mirrored
        shared = [n for n in w if n != "band"]
        self.assertEqual(set(shared), {n for n in e if not n.startswith(("gill", "groove", "btn_")) and n != "band"})
        for n in shared:
            self.assertEqual(sorted((round(-x, 6), round(y, 6), round(h, 6)) for x, y, h in e[n]["verts"]),
                             sorted((round(x, 6), round(y, 6), round(h, 6)) for x, y, h in w[n]["verts"]), n)

    def test_flat_band_and_cove(self):
        p = parts(T.th_wall, side="e")
        band = p["band"]["verts"]
        self.assertTrue(all(abs(y) < 1e-9 for _x, y, _h in band))                          # flat, on the wall's line
        self.assertAlmostEqual(max(h for *_, h in band), S.FLOOR + T.FOLD - T.GAP_H, places=9)
        self.assertAlmostEqual(max(x for x, *_ in band), T.JAMB_U, places=9)              # to the jamb's end face
        self.assertEqual({round(h - S.FLOOR, 6) for x, y, h in band if x < T.S_F0},
                         {T.PLINTH_H, round(T.TUN_BEND - T.MOUTH_TOP, 6)})                 # under the tunnel: to its bend
        a, b, c = T.FRONT
        for x, y, h in p["cove"]["verts"]:
            self.assertGreaterEqual(h, S.FLOOR + T.FOLD - 1e-9)
            self.assertAlmostEqual(y, (h - S.FLOOR - T.FOLD) / (T.CEIL - T.FOLD) * T.COVE, places=9)   # the slope
            self.assertLessEqual(a * x + b * y, c + 1e-9)                                  # cut on the header plane
        self.assertGreater(max(h for *_, h in p["cove"]["verts"]), S.FLOOR + T.CEIL)       # on into the ceiling
        gap = p["fold_line"]["verts"]
        self.assertEqual({round(h - S.FLOOR, 6) for *_, h in gap}, {round(T.FOLD - T.GAP_H, 6), T.FOLD})

    def test_west_plain(self):
        names = parts(T.th_wall, side="w").keys()
        self.assertFalse([n for n in names if n.startswith(("gill", "groove", "btn_", "cover"))])   # the west later


class Corners(unittest.TestCase):
    def test_jamb(self):
        q = T.jamb_outline(1)
        k = tuple(S.TH_PTS[2])
        self.assertAlmostEqual(math.dist(q[-1], k), 0.0, places=9)                         # it reaches K
        self.assertAlmostEqual(T._uv(q[0])[0], T.JAMB_U, places=9)                          # the end face at s 3.88
        a, b, c = T.FRONT
        u, v = T._uv(q[1])
        self.assertAlmostEqual(a * u + b * v, c, places=9)                                  # its front on the header
        n = len(q)
        turns = [(q[(i + 1) % n][0] - q[i][0]) * (q[(i + 2) % n][1] - q[(i + 1) % n][1])
                 - (q[(i + 1) % n][1] - q[i][1]) * (q[(i + 2) % n][0] - q[(i + 1) % n][0]) for i in range(n)]
        self.assertTrue(all(t < 0 for t in turns) or all(t > 0 for t in turns))            # convex
        jb = parts(T.th_jambs)
        hs = [h for *_, h in jb["jamb_e"]["verts"]]
        self.assertEqual((min(hs), max(hs)), (S.FLOOR, S.FLOOR + S.H_HALL))                # the deck to the rim

    def test_ceiling_and_header(self):
        p = parts(S.throat_ceil)
        self.assertEqual(set(p), {"body", "spine", "header"})                              # no skin, trims, panels
        self.assertAlmostEqual(min(h for *_, h in p["body"]["verts"]), S.FLOOR + T.CEIL, places=9)
        self.assertGreaterEqual(min(h for *_, h in p["spine"]["verts"]), S.FLOOR + T.CEIL - 0.0021)
        self.assertAlmostEqual(min(h for *_, h in p["header"]["verts"]), S.FLOOR + T.CEIL, places=9)

    def test_frame(self):
        p = parts(T.th_frame)
        self.assertGreaterEqual(min(h for *_, h in p["bar"]["verts"]), S.FLOOR + T.CEIL - T.BAR - 1e-9)   # head room
        xs = [x for x, *_ in p["frame"]["verts"]]
        self.assertAlmostEqual(max(xs), -min(xs), places=9)                                # both sides alike
        for h in T.frame_heights():   # the trim's inner edge 8 cm in from the tunnel, the outer past the room's wall
            self.assertLess(T.x_tun(h) - T.TRIM, T.x_room(h))
        ys = {round(y, 6) for _x, y, _h in p["frame"]["verts"]}
        self.assertEqual(ys, {round(y, 6) for y in T.FRAME_Y})
        self.assertTrue(T.FRAME_Y[0] < S.TH_ROOF < T.FRAME_Y[1])                           # it straddles the roof line


if __name__ == "__main__":
    unittest.main()
