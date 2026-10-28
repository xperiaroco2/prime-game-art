"""Lens room C, step 1 (art #263, docs/ship.md "Lens room C"): the charger's alcove and conduits against the design's
cm drawing, the east lounge inside its room with its floor lights uncovered, the path from the door to the charger
clear, colliders only on the sofa's base and the table. Plain Python (the builders' parts, no Blender)."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))
import ship_interior as S  # noqa: E402
import ship_interior_lens as LN  # noqa: E402
import ship_interior_place as SP  # noqa: E402
from runner import ship_layout  # noqa: E402

with (ROOT / "layouts" / "ship" / "interior.toml").open("rb") as _f:
    INTERIOR = tomllib.load(_f)
LAYOUT = ship_layout.load()
PIECES = {p["id"]: p for p in INTERIOR["pieces"]}
SPOTS = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
TIP_E = next(r for r in LAYOUT["rooms"] if r["id"] == "tip_e")
LOUNGE = [p for p in PIECES if p.startswith("lounge_")]


def parts(pid: str) -> dict:
    piece = PIECES[pid]
    mod = next(m for m in [S, *S.MODULES] if hasattr(m, piece["builder"]))
    return {p["name"]: p for p in getattr(mod, piece["builder"])(piece.get("args", {}), LAYOUT)}


def bounds(verts) -> list[tuple[float, float]]:
    return [(min(v[i] for v in verts), max(v[i] for v in verts)) for i in range(3)]


def world(at, yaw, x, y) -> tuple[float, float]:
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return at[0] + c * x + s * y, at[1] - s * x + c * y


def footprint(pid: str, step: int = 1):
    """Every placement's plan points of a piece (its vertices, every step-th) in the world."""
    verts = [v for p in parts(pid).values() for v in p["verts"]][::step]
    return [[world(at, yaw, v[0], v[1]) for v in verts] for name, at, yaw in INTERIOR["place"] if name == pid]


def seg_dist(p, a, b) -> float:
    ax, ay, bx, by = *a, *b
    t = max(0.0, min(1.0, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    return math.hypot(p[0] - ax - t * (bx - ax), p[1] - ay - t * (by - ay))


class LensAlcoveTest(unittest.TestCase):
    def test_the_alcove_matches_the_drawing(self) -> None:
        p = parts("lens_alcove")
        cm = lambda b: [(round(lo * 100, 2), round(hi * 100, 2)) for lo, hi in b]   # noqa: E731
        (x0, x1), (y0, y1), (h0, h1) = bounds([v for q in p.values() for v in q["verts"]])
        self.assertAlmostEqual(-x0, 0.47, places=3)          # the jambs' face d 46 and their plates' 1 cm
        self.assertAlmostEqual(y1, 0.60, places=4)
        self.assertAlmostEqual(-y0, 0.60, places=4)
        self.assertAlmostEqual(h1 - S.FLOOR, 2.26, places=4)  # the lintel's top
        back = cm(bounds(p["back"]["verts"]))
        self.assertEqual(back[0], (-10.0, -0.0))             # the back panel's face at d 10
        self.assertEqual(back[1], (-46.0, 46.0))
        lintel = cm(bounds(p["lintel"]["verts"]))
        self.assertEqual(lintel[0][0], -46.0)
        self.assertEqual(lintel[1], (-60.0, 60.0))
        self.assertEqual([round(h - S.FLOOR * 100, 2) for h in lintel[2]], [200.0, 226.0])
        for k in (0, 1):
            j = cm(bounds(p[f"jamb{k}"]["verts"]))
            self.assertEqual(j[0][0], -46.0)                 # face d 46
            self.assertEqual(sorted(abs(v) for v in j[1]), [46.0, 60.0])
            self.assertEqual(round(j[2][1] - S.FLOOR * 100, 2), 200.0)
            # the cheek splays: u 46 at the back (d 10), 50 at the front (d 46)
            pts = {(round(-v[0] * 100, 2), round(abs(v[1]) * 100, 2)) for v in p[f"jamb{k}"]["verts"]}
            self.assertIn((10.0, 46.0), pts)
            self.assertIn((46.0, 50.0), pts)
            corner = {(round(abs(v[1]) * 100, 2), round((v[2] - S.FLOOR) * 100, 2)) for v in p[f"corner{k}"]["verts"]}
            self.assertEqual(corner, {(50.0, 182.0), (50.0, 200.0), (34.0, 200.0)})

    def test_the_conduits_match_the_drawing(self) -> None:
        K = LN.CONDUIT
        for side in "ew":
            for s in (-1, 1):
                low, high = LN.conduit_paths(side, s)
                for path, h, sign in ((low, K["low"], -1), (high, K["high"], 1)):
                    self.assertTrue(all(abs(-x * 100 - K["d"]) < 1e-9 for x, _, _ in path))   # axis d 21
                    self.assertAlmostEqual(abs(path[0][1]) * 100, LN.ALCOVE["jamb_out"] - 1.0)  # from inside the jamb
                    self.assertAlmostEqual((path[0][2] - S.FLOOR) * 100, h)
                    self.assertAlmostEqual(abs(path[-1][1]) * 100, K["u"])                     # axis u 68
                    self.assertAlmostEqual(abs(path[-2][1]) * 100, K["u"])                     # the elbow r 8 ends
                    self.assertAlmostEqual((path[-2][2] - S.FLOOR) * 100, h + sign * K["bend"])
                self.assertLess(low[-1][2], S.FLOOR)                                           # into the deck
                self.assertGreater(high[-1][2], S.FLOOR + LN.ceiling_h(s * K["u"], side))       # into the ceiling
        p = parts("lens_conduits_e")
        r = max(math.hypot(v[0] + K["d"] / 100, v[1] - K["u"] / 100) for v in p["tubes"]["verts"]
                if v[2] < S.FLOOR + 0.5 and v[1] > 0)
        self.assertAlmostEqual(r * 100, K["r"], places=3)                                     # Ø 11
        self.assertAlmostEqual(LN.ceiling_h(68, "e"), LN.ceiling_h(-68, "w"))

    def test_the_spots_reach_and_stand(self) -> None:
        for sid in ("renewer_e", "renewer_w"):
            self.assertAlmostEqual(SPOTS[sid]["depth_m"], LN.REACH / 100)
            stand = ship_layout.spot_stand(LAYOUT, SPOTS[sid])
            self.assertIn([round(stand[0], 3), round(stand[1], 3), 1.2], LAYOUT["walk"]["points"])
        # the alcove sits on each renewer's vertex, facing the room along its normal
        for sid, pid in (("renewer_e", "lens_alcove"), ("renewer_w", "lens_alcove")):
            at = SPOTS[sid]["at"]
            near = [q for q in INTERIOR["place"] if q[0] == pid and math.hypot(q[1][0] - at[0], q[1][1] - at[1]) < 1e-3]
            self.assertEqual(len(near), 1, sid)
            nx, ny = world([0, 0], near[0][2], -1.0, 0.0)
            self.assertAlmostEqual(nx, SPOTS[sid]["normal"][0], places=3)
            self.assertAlmostEqual(ny, SPOTS[sid]["normal"][1], places=3)


class LensLoungeTest(unittest.TestCase):
    def test_the_items_stand_where_the_drawing_puts_them(self) -> None:
        want = {"lounge_table": (10.297, 0.375), "lounge_lamp": (11.706, -0.307), "lounge_speaker": (12.183, 0.254),
                "lounge_plant": (12.414, 0.954)}
        for pid, (x, y) in want.items():
            (at,) = [q[1] for q in INTERIOR["place"] if q[0] == pid]
            self.assertAlmostEqual(at[0], x, delta=0.0011, msg=pid)
            self.assertAlmostEqual(at[1], y, delta=0.0011, msg=pid)

    def test_the_sofa_runs_over_six_facets(self) -> None:
        mods = [q for q in INTERIOR["place"] if q[0] == "lounge_sofa_base"]
        self.assertEqual(len(mods), 6)
        c = TIP_E["centre"]
        th = sorted(round(math.degrees(math.atan2(at[1] - c[1], at[0] - c[0])) - S.COR_ANG, 2) for _, at, _ in mods)
        for got, k in zip(th, range(6)):
            self.assertAlmostEqual(got, LN.facet_mid(-109.77 + S.TIP_STEP * k + 1), delta=0.02)
        p = parts("lounge_sofa_fore")
        self.assertAlmostEqual(max(v[2] for v in p["spine"]["verts"]) - S.FLOOR, 0.88)
        self.assertAlmostEqual(max(v[2] for v in p["seat"]["verts"]) - S.FLOOR, 0.44)
        self.assertAlmostEqual(max(v[2] for v in p["back"]["verts"]) - S.FLOOR, 0.80)
        self.assertAlmostEqual(max(v[2] for v in p["arm"]["verts"]) - S.FLOOR, 0.58)
        self.assertAlmostEqual(-min(v[0] for v in parts("lounge_sofa_base")["base"]["verts"]), 0.76)

    def test_the_lounge_stays_inside_tip_e(self) -> None:
        c = TIP_E["centre"]
        for pid in LOUNGE:
            for pts in footprint(pid):
                worst = max(math.hypot(x - c[0], y - c[1]) for x, y in pts)
                self.assertLess(worst, S.R_TIP + 0.001, pid)
        # tip_w keeps no lounge piece
        self.assertFalse([q for q in INTERIOR["place"] if q[0].startswith("lounge_") and q[1][0] < 0])

    def test_the_floor_lights_stay_uncovered(self) -> None:
        c = TIP_E["centre"]
        lights = [at for pid, at, _ in INTERIOR["place"] if pid == "tip_light" and at[0] > 0]
        self.assertEqual(len(lights), 8)
        for pid in ("lounge_sofa_base", "lounge_sofa_fore", "lounge_sofa_mid", "lounge_sofa_aft", "lounge_table"):
            for pts in footprint(pid):
                for lt in lights:
                    self.assertGreater(min(math.hypot(x - lt[0], y - lt[1]) for x, y in pts), 0.08, pid)
        self.assertTrue(all(abs(math.hypot(at[0] - c[0], at[1] - c[1]) - 1.08) < 0.01 for at in lights))

    def test_the_path_to_the_charger_is_clear(self) -> None:
        rad = LAYOUT["player"]["capsule_radius_m"]
        c = TIP_E["centre"]
        a = math.radians(180.0 + S.COR_ANG)
        door = (c[0] + 1.3 * math.cos(a), c[1] + 1.3 * math.sin(a))
        stand = ship_layout.spot_stand(LAYOUT, SPOTS["renewer_e"])
        for pid in ("lounge_sofa_base", "lounge_sofa_fore", "lounge_sofa_mid", "lounge_sofa_mid_dark",
                    "lounge_sofa_aft", "lounge_table"):
            for pts in footprint(pid):
                self.assertGreater(min(seg_dist(q, door, stand) for q in pts), rad, pid)

    def test_colliders_only_on_the_base_and_the_table(self) -> None:
        self.assertEqual({p for p in LOUNGE if PIECES[p]["collide"]}, {"lounge_sofa_base", "lounge_table"})
        self.assertTrue(PIECES["lens_alcove"]["collide"])
        self.assertFalse(PIECES["lens_conduits_e"]["collide"] or PIECES["lens_conduits_w"]["collide"])

    def test_no_trunk_behind_the_sofa(self) -> None:
        c = TIP_E["centre"]
        for pid, at, _ in INTERIOR["place"]:
            if pid.startswith("tip_trunk") and at[0] > 0:
                th = math.degrees(math.atan2(at[1] - c[1], at[0] - c[0])) - S.COR_ANG
                self.assertFalse(SP.SOFA_LO - 0.1 <= th <= SP.SOFA_HI + 0.1, (pid, th))


if __name__ == "__main__":
    unittest.main()
