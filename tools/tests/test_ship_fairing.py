"""The fairings under the lenses (art #263, details 3; docs/ship.md "Details 3"): one convex part round each fin root
between the lens's lower barrel and the fin's underside. Each lies on the lens's and the fin's skin, overlaps both,
covers the barrel's bulge past the root, stands out of them by MAX_OUT at most, ends flush on the fin's edge and stays
under the fin's edge (the edge light).
Plain Python, no Blender."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports the skin and the details in their order)
import ship_hull_shape as S  # noqa: E402

PARTS = {name: fac for name, fac, _bb in S.p_facets()}
POINTS = dict(S.p_parts())
MAX_OUT = 0.45   # details 3b: the farthest a fairing stands out of the lens, the fin and the body (lead 0.21, trail 0.38)


def _inside(p, fac, margin=0.0) -> bool:
    """p lies inside the convex part, at least `margin` from its every plane (a negative margin: up to that outside)."""
    return all(n[0] * p[0] + n[1] * p[1] + n[2] * p[2] <= d - margin for n, d, _poly in fac)


def _lens_r(g, h, lens) -> float:
    lo, hi = 0.5, 3.5
    for _ in range(40):
        m = (lo + hi) / 2
        if _inside((S.P_TIP[0] + m * math.cos(g), S.P_TIP[1] + m * math.sin(g), h), lens):
            lo = m
        else:
            hi = m
    return lo


def _out(p, fac) -> float:
    """How far p lies outside the convex part: its largest plane excess (0 or less inside; at most the distance)."""
    return max(n[0] * p[0] + n[1] * p[1] + n[2] * p[2] - d for n, d, _poly in fac)


class ShipFairingTest(unittest.TestCase):
    def test_four_fairings_mirrored(self) -> None:
        names = [n for n in POINTS if n.startswith("fair_")]
        self.assertEqual(sorted(names), ["fair_lead_e", "fair_lead_w", "fair_trail_e", "fair_trail_w"])
        for k in ("lead", "trail"):
            east, west = POINTS[f"fair_{k}_e"], POINTS[f"fair_{k}_w"]
            self.assertEqual([(-x, y, h) for x, y, h in east], list(west))

    def test_placement_on_the_lens_and_the_fin(self) -> None:
        """Every point lies on the east lens's or fin's skin (inside within 1 mm), the root's at the fin edge's bottom
        on the rim, the far one P_FAIR[1] m along the edge; the barrel from the root to P_FAIR[0] deg past it."""
        edges = S.p_edges()
        for k, deg, root, far in (("lead", S.P_LEAD_DEG, edges[1], edges[0]), ("trail", S.P_TRAIL_DEG, edges[2], edges[3])):
            pts = POINTS[f"fair_{k}_e"]
            for p in pts:
                self.assertTrue(_inside(p, PARTS["lens_e"], -1e-3) or _inside(p, PARTS["fin_e"], -1e-3), (k, p))
            self.assertAlmostEqual(math.dist(pts[0], (root[0], root[1], root[2] - root[3] / 2)), 0.0, places=6)
            self.assertAlmostEqual(math.dist(pts[0][:2], pts[1][:2]), S.P_FAIR[1], places=6)
            # the far point ends flush on the fin's edge-bottom surface: on the fin's skin, not inside it or past it
            self.assertLess(abs(_out(pts[1], PARTS["fin_e"])), 1e-3, (k, pts[1], _out(pts[1], PARTS["fin_e"])))
            ang = [math.degrees(math.atan2(y - S.P_TIP[1], x - S.P_TIP[0])) - S.p_axis_deg() for x, y, _h in pts[2:]]
            lo, hi = (deg - S.P_FAIR[0], deg) if k == "lead" else (deg, deg + S.P_FAIR[0])
            self.assertTrue(all(lo - 1e-6 <= a <= hi + 1e-6 for a in ang), (k, min(ang), max(ang)))
            self.assertAlmostEqual(min(p[2] for p in pts), S.BELLY, places=6)

    def test_it_overlaps_both_skins_and_adds_its_own(self) -> None:
        """A 6 cm grid through each fairing finds points 1 cm deep inside it and the lens, inside it and the fin, and
        inside it outside every other part (the new skin); none of it, neither a grid point nor one of its own points,
        stands more than MAX_OUT out of the lens, the fin and the body."""
        for name in ("fair_lead_e", "fair_trail_e"):
            fac = PARTS[name]
            pts = POINTS[name]
            lo = [min(p[i] for p in pts) for i in range(3)]
            hi = [max(p[i] for p in pts) for i in range(3)]
            hits = {"lens": 0, "fin": 0, "own": 0}
            base = [PARTS[n] for n in ("lens_e", "fin_e", "body")]
            worst = 0.0
            others = [f for n, f in PARTS.items() if n != name]
            steps = [max(1, int((hi[i] - lo[i]) / 0.06)) for i in range(3)]
            for i in range(steps[0] + 1):
                for j in range(steps[1] + 1):
                    for m in range(steps[2] + 1):
                        p = tuple(lo[a] + (hi[a] - lo[a]) * t / steps[a] for a, t in zip(range(3), (i, j, m)))
                        if not _inside(p, fac, 0.01):
                            continue
                        hits["lens"] += _inside(p, PARTS["lens_e"], 0.01)
                        hits["fin"] += _inside(p, PARTS["fin_e"], 0.01)
                        hits["own"] += not any(_inside(p, f, -0.01) for f in others)
                        worst = max(worst, min(_out(p, f) for f in base))
            self.assertLessEqual(worst, MAX_OUT, f"{name} stands {worst:.3f} m out of the lens, fin and body")
            # details 3c: the grid can miss the farthest point; the fairing's own hull points are its corners
            for p in pts:
                out = min(_out(p, f) for f in base)
                self.assertLessEqual(out, MAX_OUT, f"{name}: its point {p} stands {out:.3f} m out")
            for what, count in hits.items():
                self.assertGreater(count, 0, f"{name}: no overlap with the {what}")

    def test_the_barrel_no_longer_bulges_past_the_fin(self) -> None:
        """Past each root the lens's low barrel stands out of the other parts (the fairing, the fin) by 5 mm at most
        (before the fairing: 0.1 to 1 m): 5 mm under its surface lies inside another part."""
        lens = PARTS["lens_e"]
        others = [f for n, f in PARTS.items() if n.endswith("_e") and n != "lens_e"] + [PARTS["body"]]
        cx, cy = S.P_TIP
        for k, deg, sgn in (("lead", S.P_LEAD_DEG, -1), ("trail", S.P_TRAIL_DEG, 1)):
            for t in range(2, int(S.P_FAIR[0]) - 3, 2):
                g = math.radians(S.p_axis_deg() + deg + sgn * t)
                for h in (0.25, 0.4, 0.6, 0.8, 1.0, 1.1):
                    r = _lens_r(g, h, lens) - 0.005
                    p = (cx + r * math.cos(g), cy + r * math.sin(g), h)
                    self.assertTrue(any(_inside(p, f) for f in others), f"{k}: the barrel bulges at {t} deg, h {h}")

    def test_under_the_edge_light(self) -> None:
        """Every point stays 0.14 m and more under the fin edge's mid line (its 8 cm edge light runs on above). (The
        rooms' skin needs no test here: the union only grows, so a part added to it cannot thin any room's skin.)"""
        edges = S.p_edges()
        for k, root, far in (("lead", edges[1], edges[0]), ("trail", edges[2], edges[3])):
            dx, dy = far[0] - root[0], far[1] - root[1]
            ln2 = dx * dx + dy * dy
            for p in POINTS[f"fair_{k}_e"]:
                t = max(0.0, min(1.0, ((p[0] - root[0]) * dx + (p[1] - root[1]) * dy) / ln2))
                mid = root[2] + (far[2] - root[2]) * t   # the edge light: 8 cm high on the edge's mid line
                self.assertLess(p[2], mid - 0.04 - 0.1, f"{k}: the fairing reaches the edge light at {p}")


if __name__ == "__main__":
    unittest.main()
