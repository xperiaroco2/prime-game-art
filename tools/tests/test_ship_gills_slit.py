"""The gills pilot (art #263): `station_gills_slit`, one slit cut into the hall's back wall (tools/blender/
ship_gills_slit.py): its size against the brief, the lip clear of the opening through its swing, the comb inside the
cavity, the fault seam behind the shut lip, the hand inside its recess, the meshes well formed, the cavity inside the
hull's skin, ship.gd's turn opening the lip outward. Pure Python: needs neither Blender, Godot nor the raw files."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))
import ship_interior as S  # noqa: E402,F401
import ship_gills_slit as P  # noqa: E402
import ship_interior_gills as GL  # noqa: E402
import ship_interior_geom as G  # noqa: E402
from runner import ship_layout  # noqa: E402

LAYOUT = ship_layout.load()


def build(side: str = "e") -> dict[str, dict]:
    pid = f"station_vent_{side}"
    return {p["name"][len(pid) + 1:]: p for p in P.station_gills_slit({"id": pid, "side": side}, LAYOUT)}


def inside(poly, q, eps: float = 1e-9) -> bool:
    s = 1.0 if G.area2(poly) > 0 else -1.0
    return all(s * ((b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])) >= -eps
               for a, b in zip(poly, poly[1:] + poly[:1]))


def turn(y: float, v: float, deg: float) -> tuple[float, float]:
    """A lip point (slit-local y, v) swung deg open about the hinge (y 0, v LIP_HINGE_V)."""
    a = math.radians(deg)
    w = v - P.LIP_HINGE_V
    return y * math.cos(a) + w * math.sin(a), P.LIP_HINGE_V - y * math.sin(a) + w * math.cos(a)


class SlitTest(unittest.TestCase):
    def test_size(self):
        xs = [p[0] for p in P.opening()]
        self.assertTrue(0.55 <= max(xs) - min(xs) <= 0.60)
        self.assertTrue(P.convex(P.opening()) and P.convex(P.lip_outline()))
        self.assertAlmostEqual(min(P.lower(x) for x in P.knots()), -P.SLIT_D, places=6)
        u, h = P.xf(0.0, -P.SLIT_D / 2)
        self.assertTrue(1.3 <= h <= 1.5, h)   # chest to eye height
        self.assertLess(P.xf(-0.29, 0.0)[1], P.xf(0.29, 0.0)[1])   # rising toward the door

    def test_lip_clear_through_its_swing(self):
        lo = P.lip_outline()
        hole = P.opening()
        pts = [(x, y, P.lip_back(y)) for x, y in P.shrink(lo, P.LIP_TAPER)]
        pts += [(x, y, P.lip_front(y) - P.LIP_CH) for x, y in lo]
        pts += [(x, y, P.lip_front(y)) for x, y in P.shrink(lo, P.LIP_CH)]
        for x, y, _ in pts[len(lo):2 * len(lo)]:
            self.assertTrue(inside(hole, (x, y)))
        for deg in [P.OPEN_DEG["open"] * k / 20 for k in range(21)]:
            for x, y, v in pts:
                y2, v2 = turn(y, v, deg)
                f = P.face_v(*P.xf(x, y2))   # the slit plate's leaning face there
                if v2 >= f:
                    continue
                room = P.grow(hole, max(0.0, P.HOLE_CH + v2 - f)) if v2 - f > -P.HOLE_CH else hole
                self.assertTrue(inside(room, (x, y2), 1e-7), (deg, x, y, v, y2, v2))

    def test_shut_gap_and_fault(self):
        lo = P.lip_outline()
        for x in P.knots(P.SLIT_W / 2 - P.CLEAR):
            self.assertAlmostEqual(min(y for xx, y in lo if abs(xx - x) < 1e-9) - P.lower(x), P.GAP, places=6)
        self.assertLess(P.FAULT_V[1], P.LIP_BACK[1])
        self.assertGreater(P.FAULT_V[0], -P.CAVITY_D)
        self.assertGreater(P.FAULT_H[1], P.GAP)   # it shows through the gap

    def test_comb_inside_the_cavity(self):
        hole = P.shrink(P.opening(), 0.001)
        c, s = math.cos(math.radians(P.TILT_DEG)), math.sin(math.radians(P.TILT_DEG))
        for u, v, h in build()["comb"]["verts"]:   # every filament's surface, 1 mm clear of the cavity's walls
            du, dh = u - P.HINGE[0], h - S.FLOOR - P.HINGE[1]
            x, y = du * c + dh * s, -du * s + dh * c
            self.assertTrue(inside(hole, (x, y)), (x, y))
            self.assertTrue(-P.CAVITY_D < v < -P.HOLE_CH, v)
        self.assertEqual(len(P.comb_paths()), P.COMB_N)

    def test_hand_inside_its_recess(self):
        oct_ = P.shrink(P.octagon(P.HAND_C[0], P.HAND_C[1], *P.HAND_OCT), 0.0105)
        for shape in P.hand_shapes():
            self.assertTrue(P.convex(shape))
            for q in shape:
                self.assertTrue(inside(oct_, q), q)
        self.assertEqual(len(P.hand_shapes()), 4)   # the palm and three fingers

    def test_meshes(self):
        parts = build()
        for name in ("panel", "lip", "comb", "comb_deep", "fault", "cavity", "hand", "hand_bezel", "hand_recess", "lines"):
            self.assertIn(name, parts)
        for name, p in parts.items():
            n = len(p["verts"])
            for f in p["faces"]:
                self.assertTrue(len(set(f)) == len(f) >= 3 and max(f) < n, (name, f))
        u, v, h = parts["lip"]["origin"]
        self.assertAlmostEqual(u, P.HINGE[0])
        self.assertAlmostEqual(v, P.LIP_HINGE_V)
        self.assertAlmostEqual(h, S.FLOOR + P.HINGE[1])
        west = build("w")
        for a, b in zip(parts["lip"]["verts"], west["lip"]["verts"]):
            self.assertAlmostEqual(a[0], -b[0])
        tris = sum(len(f) - 2 for p in parts.values() for f in p["faces"])
        self.assertLess(tris, 20000)

    def test_cavity_inside_the_skin(self):
        for x, y in P.opening():
            u, h = P.xf(x, y)
            self.assertGreaterEqual(GL.room(LAYOUT, "e", u, h), P.CAVITY_D + P.CUP_T)

    def test_turn_opens_outward(self):
        ax, ay, az, deg = P.lip_turn(P.OPEN_DEG["open"])
        a = math.radians(deg)
        k = (ax, ay, az)
        p = (math.sin(math.radians(P.TILT_DEG)) * 0.1, -math.cos(math.radians(P.TILT_DEG)) * 0.1, 0.0)  # under the hinge
        kxp = (k[1] * p[2] - k[2] * p[1], k[2] * p[0] - k[0] * p[2], k[0] * p[1] - k[1] * p[0])
        z = p[2] * math.cos(a) + kxp[2] * math.sin(a)
        self.assertLess(z, -0.05)   # Godot's -z is the wall's v: out into the hall
        st = P.slit_states()
        self.assertEqual(set(st), {"slit_shut", "slit_half", "slit_open"})
        self.assertIn("fault", st["slit_shut"]["show"])
        self.assertIn("comb", st["slit_open"]["show"])
        for s in st.values():
            for o in s["omni"]:
                self.assertEqual(len(o), 9)


if __name__ == "__main__":
    unittest.main()
