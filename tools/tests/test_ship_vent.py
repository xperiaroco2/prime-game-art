"""The throat vents (art #263 step 2, station 1, way B; docs/ship.md "Station 1: the throat vents"): the built parts
(the well's glows, the marker, the colliders; ship_vent_b.py's body and its blade's seven copies are imported from
their GLBs) inside the unit box (the spot's plain band, its own 0.6 m depth, the height), the leaves' names, materials
and origins (each blade's on the caps' axis, the marker's at the bar's bottom), the blades' boxes inside the depth all
the way, their calm reach past the frame and their seams calm and closed (the blade cleaner's numbers), the west
piece the east one's mirror, and
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
            for name, p in build(side, meshes=False).items():
                if name.startswith("slat"):
                    pts = [turn(q, p["origin"], a) for q in p["hull"] for a in (0.0, V.OPEN_RAD)]
                else:
                    pts = p.get("verts", [])
                for x, y, h in pts:
                    self.assertTrue(u0 - 1e-6 <= x <= u1 + 1e-6 and v0 - 1e-6 <= y <= v1 + 1e-6, (side, name, x, y))
                    self.assertTrue(V.FLOOR + h0 - 1e-6 <= h <= V.FLOOR + h1 + 1e-6, (side, name, h))

    def test_inside_the_wall_face(self):
        """vents-b4: the vent sits RECESS into the wall: its backs at most RECESS + 2 cm behind the wall's face, the
        well's glow panels in front of it (b3: the backs on the face)."""
        self.assertTrue(0.05 <= V.RECESS <= 0.10, V.RECESS)
        for name, p in build("e").items():
            for x, y, h in p["verts"]:
                self.assertGreaterEqual(y, V.cv(h - V.FLOOR) - V.RECESS - 0.0201, (name, y, h))
                if name in ("heat", "cool"):
                    self.assertGreater(y, 0.0, (name, y))

    def test_recess_in_the_plan(self):
        """vents-b4: one recess for both vents (ship.toml's spots), the unit's back that far behind the face."""
        spots = [s for s in V.S._SHIP["stations"]["spot"] if s["id"].startswith("vent_")]
        self.assertEqual({s["recess_m"] for s in spots}, {V.RECESS})
        self.assertAlmostEqual(V.UNIT[2], -0.01 - V.RECESS, places=6)
        self.assertAlmostEqual(V.UNIT[3], 0.60 - V.RECESS, places=6)

    def test_light_pieces(self):
        """The look step: every light a clean emissive piece over the body's painted one, off its surface."""
        if not (V.raw_root() / V.LIGHTS).is_file():
            self.skipTest("no raw lights.json")
        parts = build("e", meshes=False)
        want = {"lamp": "glow_nav_red__vent_lamp", "hand": "glow_cyan__vent_hand", "screen": "int_dark__vent_screen",
                "bar": "glow_amber__vent_bar", "bar_top": "glow_amber__vent_bar", "bar_hot": "glow_nav_white__vent_bar_hot",
                "band": "glow_nav_green__vent_band"}
        for name, mat in want.items():
            self.assertEqual(parts[name]["mat"], mat)
        strips = [p for n, p in parts.items() if n.startswith("strip")]
        self.assertGreaterEqual(len(strips), 6)
        centres = [[sum(c) / len(p["verts"]) for c in zip(*p["verts"])] for p in strips]
        for i, a in enumerate(centres):   # one strip per place (no two pieces z-fighting)
            for b in centres[i + 1:]:
                self.assertGreater(math.dist(a, b), 0.03)
        for name in ("bar", "bar_top", "bar_hot", "band"):   # on the glass, behind the sliding marker
            self.assertLess(max(y for _, y, _ in parts[name]["verts"]), min(y for _, y, _ in parts["marker"]["verts"]))
        scr, hand = parts["screen"]["verts"], parts["hand"]["verts"]
        for k in (0, 2):   # the outline inside its screen, in front of it
            self.assertGreaterEqual(min(p[k] for p in hand), min(p[k] for p in scr))
            self.assertLessEqual(max(p[k] for p in hand), max(p[k] for p in scr))
        self.assertGreater(min(y for _, y, _ in hand), max(y for _, y, _ in scr))
        # vents-b4: the hand centred on its screen (within 1.5 cm), its box 70..85 % of the screen's height
        hx = [p[0] for p in hand]
        hz = [p[2] for p in hand]
        sx, sz = [p[0] for p in scr], [p[2] for p in scr]
        self.assertLess(abs((min(hx) + max(hx)) / 2 - (min(sx) + max(sx)) / 2), 0.015)
        self.assertLess(abs((min(hz) + max(hz)) / 2 - (min(sz) + max(sz)) / 2), 0.015)
        self.assertTrue(0.70 <= (max(hz) - min(hz)) / (max(sz) - min(sz)) <= 0.85)

    def test_hand_has_a_thumb_and_three_fingers(self):
        """vents-b4: one closed smooth silhouette: three fingers' tips of one length (a scan across them meets
        three separate fingers), the thumb out past the palm's side and lower, the stroke even and unfolded."""
        pts = V.hand_outline()
        self.assertGreater(len(pts), 120)
        self.assertLess(max(math.dist(a, b) for a, b in zip(pts, pts[1:] + pts[:1])), 0.11)   # closed, no jump
        self.assertAlmostEqual(max(y for _, y in pts), V.HAND_TIP, delta=0.002)
        for cx in V.HAND_FINGERS:                            # each finger reaches the tip line
            self.assertLess(V._hand_field(cx, V.HAND_TIP - 0.01), 0.0)
        row = [V._hand_field(-0.6 + i * 0.005, 1.4) < 0 for i in range(241)]
        self.assertEqual(sum(1 for a, b in zip(row, row[1:]) if b and not a), 3)   # three fingers across
        thumb = min(pts)
        self.assertLess(thumb[0], -0.8)                      # the thumb out past the palm's side
        self.assertLess(max(y for x, y in pts if x < -0.55), 1.1)   # and well under the fingers' tips
        st = V.hand_stroke(pts)
        for (o, i), p in zip(st, pts):                       # even: every pair HAND_W apart across the line
            self.assertAlmostEqual(math.dist(o, i), V.HAND_W, places=6)
        for j in range(len(st) - 1):                        # unfolded: no side runs backwards against the line
            t = (pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1])
            for k in (0, 1):
                d = (st[j + 1][k][0] - st[j][k][0], st[j + 1][k][1] - st[j][k][1])
                self.assertGreater(d[0] * t[0] + d[1] * t[1], 0.0, (j, k))

    def test_budget_names_and_materials(self):
        parts = build("e", meshes=False)
        built = sum(tris(p) for n, p in parts.items() if "verts" in p and "-convcolonly" not in n)
        self.assertLessEqual(built, 2700, built)   # vents-b4: the hand's smooth stroke about 1,800 (b3 2,000 in all)
        self.assertTrue(parts["body"]["glb"].replace("\\", "/").endswith(V.BODY), parts["body"])
        for name in [f"slat{k}" for k in range(1, V.SLATS + 1)] + ["marker", "heat", "cool", "col0-convcolonly",
                                                                    "col1-convcolonly"]:
            self.assertIn(name, parts)
        self.assertEqual(parts["heat"]["mat"], "int_halo__vent_heat")
        self.assertEqual(parts["cool"]["mat"], "int_cyan__vent_cool")
        self.assertEqual(parts["marker"]["mat"], "glow_nav_white__vent_marker")
        for k in range(1, V.SLATS + 1):   # one blade, seven copies, each turned to closed
            p = parts[f"slat{k}"]
            self.assertTrue(p["glb"].replace("\\", "/").endswith(V.BLADE_GLB), p["glb"])
            self.assertAlmostEqual(p["rot_u"], -V.OPEN_RAD, places=9)
            self.assertEqual(p["offset"], p["origin"])
            self.assertEqual(len(p["hull"]), 8)

    def test_leaves_origins(self):
        parts = build("e", meshes=False)
        for k in range(1, V.SLATS + 1):
            o = parts[f"slat{k}"]["origin"]
            self.assertAlmostEqual(o[0], (V.CAP_U[0] + V.CAP_U[1]) / 2, places=6)
            self.assertAlmostEqual(o[1], V.PIVOT_V - V.RECESS, places=6)
            self.assertAlmostEqual(o[2], V.FLOOR + V.PIVOT_TOP - (k - 1) * V.PITCH, places=6)
        # the root's back about 3 cm behind the caps' axis (step 4: the 22 deg calm tilt adds 2.4 mm)
        self.assertAlmostEqual(V.BLADE_BOX[1][0], -0.03, delta=0.005)
        m = parts["marker"]
        self.assertAlmostEqual(m["origin"][2], min(h for _, _, h in m["verts"]), places=6)
        self.assertAlmostEqual(m["origin"][2] + V.MARK_TRAVEL + V.MARK_H, V.FLOOR + V.GLASS_H[1], places=6)

    def test_blades_in_the_frame(self):
        """From closed to calm every blade's box stays inside the unit's depth and in front of the cool glow."""
        for k, p in build("e", meshes=False).items():
            if not k.startswith("slat"):
                continue
            for q in p["hull"]:
                for a in (V.OPEN_RAD * t / 4 for t in range(5)):
                    x, y, h = turn(q, p["origin"], a)
                    self.assertTrue(V.COOL_V + 0.002 - V.RECESS < y <= V.UNIT[3] + 1e-6, (k, a, y))

    def test_calm_reach_past_the_frame(self):
        """Calm, the blades stick out about 19 cm past the frame's face (side_left)."""
        p = build("e", meshes=False)["slat4"]
        reach = max(turn(q, p["origin"], V.OPEN_RAD)[1] for q in p["hull"]) - (V.BOX_FACE - V.RECESS)
        self.assertTrue(0.14 <= reach <= 0.20, reach)   # vents-b3: the frame's face 2.5 cm prouder (0.44)

    def test_seams_calm_and_closed(self):
        """Straight from the front (the blade cleaner's numbers, the slices' median): a lit band of about a third of
        the pitch calm (front_ortho), a narrow lit seam closed (front_closed), the closed turn short of a cut."""
        self.assertTrue(0.05 <= V.BLADE_SEAMS["calm"] <= 0.075, V.BLADE_SEAMS)   # vents-b3: standing open
        self.assertTrue(-0.02 <= V.BLADE_SEAMS["closed"] <= 0.0, V.BLADE_SEAMS)   # shut: a real overlap
        self.assertGreaterEqual(V.CLOSED_DEG, 15.0)                               # a slam that reads

        self.assertLess(V.CLOSED_DEG, V.BLADE_SEAMS["first_cut_deg"] - 1.0)
        self.assertAlmostEqual(math.degrees(V.OPEN_RAD), V.CLOSED_DEG, places=9)

    def test_west_mirrors_east(self):
        e, w = build("e"), build("w")
        self.assertEqual(set(e), set(w))
        for name in e:
            self.assertEqual([(-x, y, h) for x, y, h in e[name]["verts"]], w[name]["verts"])
        ea, wa = build("e", meshes=False), build("w", meshes=False)
        for k in range(1, V.SLATS + 1):
            pe, pw = ea[f"slat{k}"], wa[f"slat{k}"]
            self.assertEqual([(-x, y, h) for x, y, h in pe["hull"]], pw["hull"])
            self.assertEqual((pe["mirror_u"], pw["mirror_u"]), (False, True))
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
        for word in ("along the wall", "..0.6", "clear", "not on its spot"):
            self.assertIn(word, found)


if __name__ == "__main__":
    unittest.main()
