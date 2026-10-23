"""The throat vents (art #263 step 2, station 1, way A; docs/ship.md "Station 1: the throat vents"): the built parts
(the blades, the well's glows, the marker, the colliders; the Meshy body is imported from its GLB) inside the unit box
(the spot's plain band, its own 0.6 m depth, the height), the leaves' names, materials and origins (each blade's on
the caps' axis, the marker's at the bar's bottom), the blades inside the frame's opening and depth all the way, their
calm reach past the frame and their seams calm and closed, the blade's UVs, the west piece the east one's mirror, and
`ship --check` holding a station piece to its spot and depth. Pure Python: needs neither Blender, Godot nor the raw
files (the motion proof on the GLBs: `ship --motion DIR`)."""

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


def build(side: str, meshes: bool = True) -> dict[str, dict]:
    """The piece's parts by their suffix; meshes: only those built here (not the imported body)."""
    pid = f"station_vent_{side}"
    parts = {p["name"][len(pid) + 1:]: p for p in V.station_vent({"id": pid, "side": side}, LAYOUT)}
    return {k: p for k, p in parts.items() if "verts" in p or not meshes}


def tris(p: dict) -> int:
    return sum(len(f) - 2 for f in p["faces"])


def turn(pt, origin, a):
    """pt turned by a about the axis along u through origin (positive: the tip swings out and up, closed to calm)."""
    _, v, h = (pt[k] - origin[k] for k in range(3))
    c, s = math.cos(a), math.sin(a)
    return (pt[0], origin[1] + v * c - h * s, origin[2] + v * s + h * c)


def front_span(p: dict, a: float = 0.0) -> dict[float, tuple[float, float]]:
    """A blade turned by a from closed: per section (its u), the lowest and highest h (seen straight from the front)."""
    by: dict[float, list[float]] = {}
    for q in p["verts"]:
        x, _, h = turn(q, p["origin"], a)
        by.setdefault(round(x, 4), []).append(h)
    return {x: (min(hs), max(hs)) for x, hs in by.items()}


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

    def test_budget_names_and_materials(self):
        parts = build("e", meshes=False)
        built = sum(tris(p) for n, p in parts.items() if "verts" in p and "-convcolonly" not in n)
        self.assertLessEqual(built, 2000, built)   # the body adds its 4,000 baked triangles
        self.assertTrue(parts["body"]["glb"].replace("\\", "/").endswith("body4k_r2/body.glb"), parts["body"])
        for name in [f"slat{k}" for k in range(1, V.SLATS + 1)] + ["marker", "heat", "cool", "col0-convcolonly",
                                                                    "col1-convcolonly"]:
            self.assertIn(name, parts)
        self.assertNotIn("lamp", parts)            # the lamp, band and hand are faces of the body now
        self.assertEqual(parts["heat"]["mat"], "int_halo__vent_heat")
        self.assertEqual(parts["cool"]["mat"], "int_cyan__vent_cool")
        self.assertEqual(parts["marker"]["mat"], "glow_nav_white__vent_marker")
        self.assertEqual(set(V.L.MATERIALS[V.BLADE]["tex"]), {"albedo", "rough", "metal"})
        for k in range(1, V.SLATS + 1):
            p = parts[f"slat{k}"]
            self.assertEqual(p["mat"], V.BLADE)
            self.assertEqual([len(u) for u in p["uv"]], [len(f) for f in p["faces"]], k)
            self.assertTrue(all(0.0 <= c <= 1.0 for u in p["uv"] for xy in u for c in xy), k)

    def test_leaves_origins(self):
        parts = build("e")
        for k in range(1, V.SLATS + 1):
            o = parts[f"slat{k}"]["origin"]
            self.assertAlmostEqual(o[0], (V.CAP_U[0] + V.CAP_U[1]) / 2, places=6)
            self.assertAlmostEqual(o[1], V.PIVOT_V, places=6)
            self.assertAlmostEqual(o[2], V.FLOOR + V.PIVOT_TOP - (k - 1) * V.PITCH, places=6)
        self.assertAlmostEqual(math.hypot(*V.UPPER[0]), V.NOSE_R, places=6)   # the root round the caps' axis
        m = parts["marker"]
        self.assertAlmostEqual(m["origin"][2], min(h for _, _, h in m["verts"]), places=6)
        self.assertAlmostEqual(m["origin"][2] + V.MARK_TRAVEL + V.MARK_H, V.FLOOR + V.GLASS_H[1], places=6)

    def test_blades_in_the_frame(self):
        """From closed to calm every blade stays inside the unit's depth and in front of the cool glow; whatever of it
        is behind the frame's face stays inside the opening's height."""
        for k, p in build("e").items():
            if not k.startswith("slat"):
                continue
            for q in p["verts"]:
                for a in (V.OPEN_RAD * t / 4 for t in range(5)):
                    x, y, h = turn(q, p["origin"], a)
                    self.assertTrue(V.COOL_V + 0.002 < y <= V.UNIT[3] + 1e-6, (k, a, y))
                    if y < V.BOX_FACE:
                        self.assertTrue(V.FLOOR + V.OPEN_H[0] < h < V.FLOOR + V.OPEN_H[1], (k, a, h))

    def test_calm_reach_past_the_frame(self):
        """Calm, the blades stick out about 19 cm past the frame's face (side_left)."""
        p = build("e")["slat4"]
        reach = max(turn(q, p["origin"], V.OPEN_RAD)[1] for q in p["verts"]) - V.BOX_FACE
        self.assertTrue(0.17 <= reach <= 0.20, reach)

    def test_seams_calm_and_closed(self):
        """Straight from the front, between each blade's lowest point and the next one's top along its full-size part
        (the ends taper into the caps): a wide lit band calm (front_ortho), a narrow lit seam closed (front_closed),
        never an overlap."""
        parts = build("e")
        u0, u1 = V.CAP_U[0] + 0.012, V.CAP_U[1] - 0.012
        full = {round(u0 + (t + 1) / 2 * (u1 - u0), 4) for t, sc, _ in V.STATIONS if sc >= 0.9}
        for k in range(1, V.SLATS):
            for a, lo, hi in ((0.0, 0.005, 0.03), (V.OPEN_RAD, 0.035, 0.07)):
                up, down = front_span(parts[f"slat{k}"], a), front_span(parts[f"slat{k + 1}"], a)
                gaps = [up[x][0] - down[x][1] for x in up if x in full]
                self.assertTrue(lo <= min(gaps) and max(gaps) <= hi, (k, a, min(gaps), max(gaps)))

    def test_west_mirrors_east(self):
        e, w = build("e"), build("w")
        self.assertEqual(set(e), set(w))
        for name in e:
            self.assertEqual([(-x, y, h) for x, y, h in e[name]["verts"]], w[name]["verts"])
        self.assertGreater(e["marker"]["verts"][0][0], 0)   # the column on +u (toward the hall) east
        self.assertTrue(build("w", meshes=False)["body"]["mirror_u"])

    def test_check_holds_the_spot(self):
        self.assertEqual(ship_layout.check_units(LAYOUT), [])
        depth = {s["id"]: s.get("depth_m") for s in LAYOUT["stations"]["spot"] if s.get("normal")}
        self.assertEqual({k for k, d in depth.items() if d == 0.6}, {"vent_e", "vent_w"})
        self.assertEqual((depth["vent_e"], depth["vent_w"], LAYOUT["stations"]["depth_m"]), (0.6, 0.6, 0.5))
        bad = copy.deepcopy(LAYOUT)
        for p in bad["pieces"]:
            if p["id"] == "station_vent_e":
                p["unit"] = [-0.9, 0.78, -0.01, 0.62, -0.02, 2.4]
        for q in bad["place"]:
            if q[0] == "station_vent_w":
                q[2] += 5.0
        found = " ".join(ship_layout.check_units(bad))
        for word in ("along the wall", "0..0.6", "clear", "not on its spot"):
            self.assertIn(word, found)


if __name__ == "__main__":
    unittest.main()
