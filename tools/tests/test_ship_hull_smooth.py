"""The manta's smooth skin (tools/blender/ship_hull_smooth.py, art #263 v2): plain geometry, no Blender. Every grid
variant keeps the mirrored rooms inside, the outer wing thins and curls up to the tips at +-13.75, the window bands and
the mouth's recess are open, the surfaces are closed where they meet, and the faces point outward after the harness's
mirror."""

from __future__ import annotations

import math
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))

import ship_hull_smooth as S  # noqa: E402

SKIN = S.skin(S.VARIANTS[S.DEFAULT])


class SmoothSkin(unittest.TestCase):
    def test_every_variant_clears_the_rooms(self) -> None:
        for name, var in S.VARIANTS.items():
            self.assertEqual(S.clearance(var), [], f"variant {name}")

    def test_the_outer_wing_thins_and_curls_up(self) -> None:
        for name, var in S.VARIANTS.items():
            m = S.measures(var)
            self.assertTrue(0.9 <= m["thick_11.5"] <= 1.5, f"{name}: the wing past the tip room {m['thick_11.5']:.2f}")
            self.assertLess(m["thick_12.5"], m["thick_11.5"], name)
            self.assertGreater(m["tip_h"], S._spline(var["edge"], S.TIP_X) + 1.0, f"{name}: the tip curls up")
            self.assertGreater(m["band_gap"], 0.1, f"{name}: the window band inside the outline")
        top = SKIN["top"][0]
        self.assertLess(abs(max(abs(p[0]) for p in top) - S.SPAN_X), 0.05)

    def test_the_window_bands_and_the_mouth_are_open(self) -> None:
        verts, faces = SKIN["top"]
        for side in (1, -1):
            x = side * (S.TIP_X + S.pod_r((S.SILL + S.HEAD) / 2))
            hit = [f for f in faces if self._inside(verts, f, x, 0.0)]
            self.assertEqual(hit, [], f"the top covers the window at ({x:.2f}, 0)")
        bv, bf = SKIN["belly"]
        self.assertEqual([f for f in bf if self._inside(bv, f, 0.0, S.MOUTH_Y - 0.4)], [], "the belly under the nose")
        mv, mf = SKIN["mouth"]
        for f in mf:
            c = [sum(mv[i][k] for i in f) / len(f) for k in range(3)]
            if abs(c[1] - S.MOUTH_Y) < 1e-6 and abs(c[0]) < S.MOUTH_HW:
                self.assertFalse(S.MOUTH_SILL < c[2] < S.MOUTH_TOP, f"the mouth's opening is closed at {c}")

    def test_the_top_and_the_belly_meet_at_the_edge(self) -> None:
        """Every open edge of the top (outside the window bands) is an edge of the belly or of the recess."""
        tv, tf = SKIN["top"]
        bv, bf = SKIN["belly"]
        rv, rf = SKIN["brow"]

        def open_edges(verts, faces):
            c = Counter()
            for f in faces:
                for a, b in zip(f, f[1:] + f[:1]):
                    c[frozenset((tuple(round(v, 4) for v in verts[a][:2]), tuple(round(v, 4) for v in verts[b][:2])))] += 1
            return {e for e, n in c.items() if n == 1}
        top = open_edges(tv, tf)
        low = open_edges(bv, bf) ^ open_edges(rv, rf)
        rest = [e for e in top - low if not any(math.hypot(abs(p[0]) - S.TIP_X, p[1]) < 3.2 for p in e)]
        self.assertEqual(rest, [], "open top edges with no belly under them")
        for (x, y, h), (bx, by, bh) in zip(tv, bv):
            if abs(y - S.lead(x, S.VARIANTS[S.DEFAULT])) < 1e-6:
                self.assertAlmostEqual(h, bh, places=3, msg=f"the blade at ({x:.2f}, {y:.2f})")

    def test_faces_point_outward_after_the_mirror(self) -> None:
        parts = {p["name"]: p for part in ("top", "belly")
                 for p in S.smooth_skin({"part": part}, {})}
        for name, want in (("skin_top", 1), ("skin_belly", -1)):
            p = parts[name]
            self.assertTrue(p["smooth"])
            verts = [(x, -y, h) for x, y, h in p["verts"]]
            for f in p["faces"][::50]:
                n = self._newell([verts[i] for i in f])
                self.assertGreater(n[2] * want, 0, f"{name} face {f} points the wrong way")

    def test_the_footprint_rows_follow_the_skin(self) -> None:
        import tomllib
        with (ROOT / "layouts" / "ship" / "ship.toml").open("rb") as f:
            hull = tomllib.load(f)["hull"]
        self.assertEqual([list(map(float, r)) for r in hull["core"] + hull["plate"]],
                         [list(map(float, r)) for r in S.outline_rows(S.VARIANTS[S.DEFAULT])])

    @staticmethod
    def _newell(p):
        n = [0.0, 0.0, 0.0]
        for a, b in zip(p, p[1:] + p[:1]):
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        return n

    @staticmethod
    def _inside(verts, f, x, y):
        poly = [verts[i][:2] for i in f]
        c = False
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if (a[1] > y) != (b[1] > y) and x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                c = not c
        return c


if __name__ == "__main__":
    unittest.main()
