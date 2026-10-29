"""The throat's gill set (art #263, 2026-10-29; tools/blender/ship_interior_gillset.py, godot/ship/gill_set.gd,
docs/ship.md "The gill set"): five static crescent niches on the east throat wall, the groove, the turn bars and the
button: their places and sizes (the chords shrinking from the mouth, the bottoms rising gently), nothing before s 1.70
or over the fold, the groove and the button clear of the holes, no colliders and no moving parts, the west wall plain,
and the controller's demo (gill_set.gd's rules mirrored in plain Python). Plain Python."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import ship_interior as S  # noqa: E402
import ship_interior_gillset as G  # noqa: E402
import ship_interior_throat as T  # noqa: E402

GD = (ROOT / "godot" / "ship" / "gill_set.gd").read_text(encoding="utf-8")
SET = ("gill", "groove", "btn_")


def parts(side: str = "e") -> dict:
    return {p["name"]: p for p in T.th_wall({"side": side}, {})}


def set_parts(side: str = "e") -> dict:
    return {n: p for n, p in parts(side).items() if n.startswith(SET)}


def uvw(p) -> tuple[float, float, float]:
    """A piece point (x, y, h) back to the wall's (u, t, w) (below the fold)."""
    x, y, h = p
    return x, h - S.FLOOR, y


class Slits(unittest.TestCase):
    def test_places(self):
        self.assertEqual(G.SLOTS, {1: 1.95, 2: 2.32, 3: 2.69, 4: 3.06, 5: 3.43})
        for sl in G.slits():
            lo, hi = sl.extent()
            self.assertAlmostEqual((lo + hi) / 2, sl.s_mid, delta=0.03, msg=sl.k)     # its middle on the old slot

    def test_sizes_shrink_from_the_mouth(self):
        rows = G.numbers()
        chords = [r["top"] - r["bottom"] for r in rows]
        self.assertTrue(1.12 <= chords[0] <= 1.21, chords)                             # the mouth side's about 1.20
        self.assertTrue(0.74 <= chords[-1] <= 0.84, chords)                            # down to about 0.80
        self.assertTrue(all(a > b + 0.05 for a, b in zip(chords, chords[1:])), chords)  # each a little shorter
        bottoms = [r["bottom"] for r in rows]
        self.assertTrue(all(0.0 <= b - a <= 0.03 for a, b in zip(bottoms, bottoms[1:])), bottoms)   # rising gently
        leans = [sl.lean for sl in G.slits()]
        self.assertTrue(all(0 < x <= 10 for x in leans) and leans == sorted(leans))   # lean back, fanning a little

    def test_crescent_bulges_to_the_mouth(self):
        for sl in G.slits():
            (ub, _tb), (ut, _tt) = sl.tips()
            lo, _hi = sl.extent()
            self.assertLess(lo, min(ub, ut) - 0.1, sl.k)                               # the outer arc toward the ramp
            self.assertGreater(ut, ub)                                                 # the top leans toward the hall

    def test_bars_over_their_slits(self):
        for sl in G.slits():
            u, t = sl.bar()
            self.assertGreater(t - G.BAR_FRAME[1] / 2, sl.t_mid + sl.half + 0.015, sl.k)
            self.assertLess(t + G.BAR_FRAME[1] / 2, G.FOLD_T - 0.015, sl.k)
        bars = [sl.bar() for sl in G.slits()]
        self.assertTrue(all(b[0] - a[0] > G.BAR_FRAME[0] + 0.1 for a, b in zip(bars, bars[1:])))

    def test_clearances(self):
        c = G.clearances()
        self.assertGreater(c["groove_hole"], 0.04)                                     # the groove crosses no slit
        self.assertGreater(c["column_gap"], 0.0)
        self.assertGreater(c["button_hole"], 0.05)                                     # the button clear of slit 5
        self.assertGreater(c["button_jamb"], 0.04)                                     # and of the jamb's end face
        self.assertGreater(c["groove_t_min"], T.PLINTH_H + 0.02)                       # above the plinth


class Wall(unittest.TestCase):
    def test_nothing_before_1_70_and_under_the_fold(self):
        for n, p in set_parts().items():
            pts = [uvw(v) for v in p["verts"]]
            self.assertGreaterEqual(min(u for u, _t, _w in pts), 1.70, n)
            self.assertLessEqual(max(t for _u, t, _w in pts), T.FOLD - T.GAP_H - 0.01, n)
            self.assertLessEqual(max(u for u, _t, _w in pts), T.JAMB_U - 0.04, n)

    def test_decor_static_east_only(self):
        e = set_parts("e")
        names = {f"gill{k}_{x}" for k in G.SLITS for x in ("scoop", "glow", "edge", "bar", "bar_glow")}
        self.assertEqual(set(e), names | {"groove", "groove_glow", "btn_bezel", "btn_ring", "btn_dome"})
        self.assertTrue(all(p.get("nocol") for p in e.values()))                       # no colliders on decor
        self.assertFalse([n for n, p in e.items() if p.get("origin")])                 # nothing moves
        self.assertEqual(set_parts("w"), {})                                           # the west plain for now

    def test_niches_behind_the_face(self):
        p = parts("e")
        for k in G.SLITS:
            ws = [uvw(v)[2] for x in ("scoop", "glow", "edge") for v in p[f"gill{k}_{x}"]["verts"]]
            self.assertLessEqual(max(ws), 1e-9)
            self.assertAlmostEqual(min(ws), -G.DEPTH, delta=0.01)
        for n in ("groove", "groove_glow") + tuple(f"gill{k}_bar_glow" for k in G.SLITS):
            ws = [uvw(v)[2] for v in p[n]["verts"]]
            self.assertGreaterEqual(min(ws), -1e-9, n)                                 # proud parts stay in front
        glow = [uvw(v)[2] for v in p["groove_glow"]["verts"]]
        self.assertGreater(min(glow), 0.001)                                           # no coplanar face on the band


class Lamps(unittest.TestCase):
    def test_throat_floor_lights_light_nothing(self):
        """step 2: the throat's floor lights (th_light) glow in their own amber, which lights nothing (its pools painted
        the set's plinth); int_amber stays the ship's."""
        import tomllib
        ship = tomllib.loads((ROOT / "layouts" / "ship" / "ship.toml").read_text(encoding="utf-8"))
        inter = tomllib.loads((ROOT / "layouts" / "ship" / "interior.toml").read_text(encoding="utf-8"))
        self.assertEqual(ship["light"]["mats"]["int_amber_throat"].get("l"), 0.0)
        self.assertEqual(ship["light"]["mats"]["int_amber"].get("l"), 2.0)
        piece = next(p for p in inter["pieces"] if p["id"] == "th_light")
        self.assertEqual(piece["args"]["mat"], "int_amber_throat")
        th = [q for q in inter["place"] if q[0] == "th_light"]
        self.assertEqual(len(th), 4)
        self.assertTrue(all(-7.0 < q[1][1] < -3.0 and abs(q[1][0]) < 3.0 for q in th))   # all in the throat


class Controller(unittest.TestCase):
    def const(self, name: str) -> float:
        return float(re.search(rf"^const {name} := ([-0-9.]+)", GD, re.M).group(1))

    def test_names_and_rules(self):
        self.assertEqual(self.const("STEP_S"), 0.6)
        self.assertIn("const ORDER: Array = [0, 1, 2, 3, 4, 3, 2, 1]", GD)
        for n in ("gill%d_%s", "gill%d_bar_glow", "GPUParticles3D", "func press()", "func step(", "func pose("):
            self.assertIn(n, GD)
        self.assertNotIn("rotation", GD)                                               # nothing turns

    def test_demo(self):
        """gill_set.gd's demo, replayed: its presses open slits, one shuts an open one again, all five end open."""
        events = [float(t) for t in re.findall(r"\[([0-9.]+), \"press\"\]", GD)]
        order = [0, 1, 2, 3, 4, 3, 2, 1]
        opened = [False] * 5
        shut_again = 0
        for t in events:
            k = order[int(t // 0.6) % 8]
            shut_again += opened[k]
            opened[k] = not opened[k]
        self.assertEqual(opened, [True] * 5)
        self.assertGreaterEqual(shut_again, 1)
        self.assertLess(max(events), self.const("DEMO_S") - 4.0)                       # the cloud holds a while


if __name__ == "__main__":
    unittest.main()
