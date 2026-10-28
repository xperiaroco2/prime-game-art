"""The gills' animation controller (art #263 gills step 11; docs/ship.md "The gills' animation"): the constants at the
top of `godot/ship/vent_anim.gd` agree with the gills' builder (`ship_interior_gills`: four ribs, RIB_ROCK_DEG, the
bar's green band), the ribs stay clear of each other and the casing at every pair of angles the controller can give
(the builder's own test checks the extremes), the timings and the demo are the brief's, the runner offers
`--vent-anim` with a fixed clock, and `godot/ship/vent_anim_check.gd` passes headless (the states, the signals, the six
clicks from a real foot band, the stillness, the pose before the clamp on every step; gills step 13: the release at
GREEN's ends, the latched marker, hold to 0 without a release, `fixed` with `problem` kept, a release after `problem`
cleared, hold jitter, restore()). The Godot part skips without Godot."""


from __future__ import annotations

import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))

import ship_interior_gills as G  # noqa: E402
from runner import common, pins  # noqa: E402

SCRIPT = ROOT / "godot" / "ship" / "vent_anim.gd"
GODOT = common.tool_path(pins.GODOT_ENV, None)


def consts() -> dict:
    out = {}
    for m in re.finditer(r"^const (\w+) := (.+?)(?:\s+#.*)?$", SCRIPT.read_text(encoding="utf-8"), re.M):
        try:
            out[m.group(1)] = ast.literal_eval(m.group(2).strip())
        except (ValueError, SyntaxError):
            pass
    return out


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


def gap(a, b) -> float:
    """The separating gap between two convex polygons along their edges' normals (> 0: apart)."""
    best = -1e9
    for poly in (a, b):
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            n = (q[1] - p[1], p[0] - q[0])
            ln = (n[0] ** 2 + n[1] ** 2) ** 0.5 or 1.0
            n = (n[0] / ln, n[1] / ln)
            pa = [x * n[0] + y * n[1] for x, y in a]
            pb = [x * n[0] + y * n[1] for x, y in b]
            best = max(best, min(pb) - max(pa), min(pa) - max(pb))
    return best


class VentAnimTest(unittest.TestCase):
    def setUp(self) -> None:
        self.c = consts()

    def test_matches_the_builder(self) -> None:
        c = self.c
        self.assertEqual(c["RIBS"], G.COVERS)
        self.assertEqual(c["ROCK_DEG"], G.RIB_ROCK_DEG)
        span = G.BAR_H[1] - G.BAR_H[0]
        self.assertAlmostEqual(c["GREEN"][0], (G.BAR_GREEN[0] - G.BAR_H[0]) / span, places=3)
        self.assertAlmostEqual(c["GREEN"][1], (G.BAR_GREEN[1] - G.BAR_H[0]) / span, places=3)
        self.assertLess(c["GREEN"][1], c["TOP"])
        self.assertEqual(c["STEPS"], 6)

    def test_amplitudes_within_the_range(self) -> None:
        c = self.c
        self.assertAlmostEqual(sum(c["SHUDDER_MIX"]), 1.0)
        self.assertLessEqual(c["BREATH_DEG"], c["ROCK_DEG"] / 2)
        self.assertLessEqual(abs(c["HOLD_DEG"]), c["ROCK_DEG"])
        self.assertLessEqual(max(abs(k[1]) for k in c["COUGH"]), c["ROCK_DEG"])
        self.assertEqual(c["COUGH"][0], [0.0, 0.0])
        self.assertEqual(c["COUGH"][-1][1], 0.0)
        self.assertAlmostEqual(c["COUGH"][-1][0], c["COUGH_S"])

    def test_ribs_clear_at_every_angle_pair(self) -> None:
        """The wave and the shudder put neighbours at different angles: every pair in ROCK_DEG's range (1 deg steps)
        keeps 2 cm between neighbouring ribs and the end ribs 2 cm off the casing."""
        rows = {i: G.rib_rows(G.cover_u(i), G.cover_u(i) + G.COVER_W)[:len(G.RIB_HS)] for i in range(G.COVERS)}
        r = int(self.c["ROCK_DEG"])
        degs = [float(d) for d in range(-r, r + 1)]
        least = 9.0
        for i in range(G.COVERS - 1):
            for k in range(0, len(G.RIB_HS), 9):
                h = rows[i][k][0]
                for d1 in degs:
                    a = hull2([G.rock((u, v, h), i, d1)[:2] for u, v in rows[i][k][1]])
                    for d2 in degs:
                        b = hull2([G.rock((u, v, h), i + 1, d2)[:2] for u, v in rows[i + 1][k][1]])
                        least = min(least, gap(a, b))
        self.assertGreater(least, 0.02)
        for d in degs:
            for k in range(0, len(G.RIB_HS), 9):
                h = rows[0][k][0]
                self.assertGreater(min(G.rock((u, v, h), 0, d)[0] for u, v in rows[0][k][1]), G.BAND[0] + 0.02)
                last = G.COVERS - 1
                self.assertLess(max(G.rock((u, v, h), last, d)[0] for u, v in rows[last][k][1]), G.FIXED[0] - 0.02)

    def test_timings_and_particles(self) -> None:
        c = self.c
        self.assertTrue(3.5 <= c["BREATH_PERIOD_S"] <= 5.0)
        self.assertTrue(3.0 <= c["SHUDDER_HZ"][0] <= 6.0)
        self.assertTrue(30.0 <= c["DEMO_S"] <= 40.0)                 # gills step 12: at most 40 s
        self.assertEqual(len(c["DEMO_RELEASES"]), len(c["DEMO_HOLD"]))
        held = [h[2] for h in c["DEMO_HOLD"]]
        self.assertTrue(c["GREEN"][0] < held[0] < c["GREEN"][1])      # released in the green: the exhale
        self.assertLess(held[1], c["GREEN"][0])                         # released too early
        self.assertTrue(c["GREEN"][1] < held[2] < c["TOP"])             # past the green: missed
        self.assertEqual(held[3], 1.0)                                  # held to the top: thrown
        self.assertEqual(c["DEMO_HEARD"], ["fixed", "too_early", "missed", "thrown"])
        for a, b in zip(c["DEMO_RELEASES"], c["DEMO_RELEASES"][1:]):
            self.assertLess(a, b)
        # the exhale: the peak at ROCK_DEG, the settle under it, the mist landing on the peak
        self.assertLess(c["EXHALE_SETTLE_DEG"], c["ROCK_DEG"])
        self.assertTrue(c["EXHALE_SETTLE_DEG"] > c["ROCK_DEG"] - 1.0)  # a tiny overshoot
        self.assertLess(c["EXHALE_OUT_S"], 0.4)                         # quick out ...
        self.assertGreater(c["EXHALE_BACK_S"], 4 * c["EXHALE_OUT_S"])   # ... slow back
        self.assertLess(c["EXHALE_MIST_AT_S"], c["EXHALE_OUT_S"])
        for name in ("STEAM_PER_SLOT", "MIST_PER_SLOT", "COUGH_PER_SLOT"):
            self.assertLessEqual(c[name], 16, name)

    def test_runner_offers_the_clip(self) -> None:
        from runner.commands import ship
        self.assertEqual(ship.VENT_ANIM["size"], (1280, 720))
        self.assertLessEqual(ship.VENT_ANIM["max_mb"], 15)
        text = (ROOT / "tools" / "runner" / "commands" / "ship.py").read_text(encoding="utf-8")
        self.assertIn('"--vent-anim"', text)
        self.assertIn('"--fixed-fps"', text)

    @unittest.skipUnless(GODOT, "needs Godot")
    def test_state_machine_headless(self) -> None:
        res = subprocess.run([str(GODOT), "--headless", "--path", str(ROOT / "godot"), "-s",
                              "res://ship/vent_anim_check.gd"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=170)
        out = (res.stdout or "") + (res.stderr or "")
        self.assertEqual(res.returncode, 0, out[-3000:])
        self.assertIn("VENT_ANIM_CHECK pass", out)
        self.assertNotIn("SCRIPT ERROR", out)


if __name__ == "__main__":
    unittest.main()
