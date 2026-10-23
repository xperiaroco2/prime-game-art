"""The throat vents (art #263 step 2, station 1; docs/ship.md "Station 1: the throat vents"): the builder's geometry
inside its unit box (the spot's plain band, depth and height), the hero budget, the leaves' names and origins (each
slat's on its upper edge, the marker's at the bar's bottom), the open slats inside the frame's depth, the west piece
the east one's mirror, and `ship --check` holding a station piece to its spot. Pure Python: needs neither Blender,
Godot nor the raw files (the motion proof on the GLBs: `ship --motion DIR`)."""

from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))
import ship_interior_vent as V  # noqa: E402
from runner import ship_layout  # noqa: E402

LAYOUT = ship_layout.load()


def build(side: str) -> dict[str, dict]:
    pid = f"station_vent_{side}"
    return {p["name"][len(pid) + 1:]: p for p in V.station_vent({"id": pid, "side": side}, LAYOUT)}


def tris(p: dict) -> int:
    return sum(len(f) - 2 for f in p["faces"])


def turn(pt, origin, a):
    """pt turned by a about the axis along u through origin (positive: the lower edge swings out, +v)."""
    _, v, h = (pt[k] - origin[k] for k in range(3))
    c, s = math.cos(a), math.sin(a)
    return (pt[0], origin[1] + v * c - h * s, origin[2] + v * s + h * c)


class ShipVentTest(unittest.TestCase):
    def test_inside_the_unit_box(self):
        u0, u1, v0, v1, h0, h1 = V.UNIT
        for side in "ew":
            for name, p in build(side).items():
                for x, y, h in p["verts"]:
                    self.assertTrue(u0 - 1e-6 <= x <= u1 + 1e-6 and v0 - 1e-6 <= y <= v1 + 1e-6, (side, name, x, y))
                    self.assertTrue(V.FLOOR + h0 - 1e-6 <= h <= V.FLOOR + h1 + 1e-6, (side, name, h))

    def test_inside_the_wall_face(self):
        """Only the backs sink into the wall (2 cm at most); nothing else stands behind the wall's face."""
        for name, p in build("e").items():
            for x, y, h in p["verts"]:
                self.assertGreaterEqual(y, V.cv(h - V.FLOOR) - 0.0201, (name, y, h))

    def test_budget_and_names(self):
        parts = build("e")
        visible = sum(tris(p) for n, p in parts.items() if "-convcolonly" not in n)
        self.assertTrue(1200 <= visible <= 4000, visible)
        for k in range(1, V.SLATS + 1):
            self.assertIn(f"slat{k}", parts)
        for name in ("marker", "lamp", "heat", "cool", "band", "hand", "col0-convcolonly", "col1-convcolonly"):
            self.assertIn(name, parts)
        self.assertEqual(parts["heat"]["mat"], "int_halo__vent_heat")
        self.assertEqual(parts["cool"]["mat"], "int_cyan__vent_cool")
        self.assertEqual(parts["lamp"]["mat"], "glow_nav_red__vent_lamp")
        self.assertEqual(parts["hand"]["mat"], "int_cyan__vent_hand")
        self.assertEqual(parts["band"]["mat"], "glow_nav_green__vent_band")
        self.assertEqual(parts["marker"]["mat"], "glow_nav_white__vent_marker")

    def test_leaves_origins(self):
        parts = build("e")
        for k in range(1, V.SLATS + 1):
            p = parts[f"slat{k}"]
            o = p["origin"]
            top = max(h for _, _, h in p["verts"])
            self.assertLess(abs(top - o[2]), V.NOSE_R + 0.001, k)   # the origin on the nose's axis, under its top
            near = [q for q in p["verts"] if q[2] > top - 0.003]
            self.assertTrue(all(abs(q[1] - o[1]) < 0.01 for q in near), k)
        m = parts["marker"]
        self.assertAlmostEqual(m["origin"][2], min(h for _, _, h in m["verts"]), places=6)
        self.assertAlmostEqual(m["origin"][2] + V.MARK_TRAVEL + V.MARK_H, V.FLOOR + V.GLASS_H[1], places=6)

    def test_open_slats_in_the_frame(self):
        """Turned fully open, every slat stays within the unit's depth, in front of the heat panel, inside the
        opening's height."""
        for k, p in build("e").items():
            if not k.startswith("slat"):
                continue
            for q in p["verts"]:
                for a in (V.OPEN_RAD * t / 4 for t in range(5)):
                    x, y, h = turn(q, p["origin"], a)
                    self.assertTrue(V.COOL_V + 0.002 < y <= V.UNIT[3], (k, a, y))
                    self.assertTrue(V.FLOOR + V.OPEN_H[0] < h < V.FLOOR + V.OPEN_H[1], (k, a, h))

    def test_lit_slits_when_shut(self):
        """Shut (t 0), a lit slit shows under each slat straight on: its tail ends above the next slat's nose, widest
        mid-blade (a crescent) and over 2.5 cm at its ends."""
        parts = build("e")
        for k in range(1, V.SLATS):
            upper, lower = parts[f"slat{k}"], parts[f"slat{k + 1}"]
            def loops(p):   # the slat's sections along u, left to right: their h values
                by = {}
                for x, _, h in p["verts"]:
                    by.setdefault(round(x, 4), []).append(h)
                return [by[x] for x in sorted(by)]
            a, b = loops(upper), loops(lower)

            def gap(i):
                return min(a[i]) - max(b[i])
            end, mid = 0, len(a) // 2
            self.assertGreater(gap(end), 0.025, k)
            self.assertGreater(gap(mid), gap(end) + 0.03, k)

    def test_west_mirrors_east(self):
        e, w = build("e"), build("w")
        self.assertEqual(set(e), set(w))
        for name in e:
            self.assertEqual([(-x, y, h) for x, y, h in e[name]["verts"]], w[name]["verts"])
        self.assertGreater(e["lamp"]["verts"][0][0], 0)   # the column on +u (toward the hall) east

    def test_check_holds_the_spot(self):
        self.assertEqual(ship_layout.check_units(LAYOUT), [])
        bad = copy.deepcopy(LAYOUT)
        for p in bad["pieces"]:
            if p["id"] == "station_vent_e":
                p["unit"] = [-0.9, 0.78, -0.01, 0.6, -0.02, 2.4]
        for q in bad["place"]:
            if q[0] == "station_vent_w":
                q[2] += 5.0
        found = " ".join(ship_layout.check_units(bad))
        for word in ("along the wall", "from the wall", "clear", "not on its spot"):
            self.assertIn(word, found)


if __name__ == "__main__":
    unittest.main()
