"""The throat's gill set (art #263, 2026-10-29; tools/blender/ship_interior_gillset.py, godot/ship/gill_set.gd,
docs/ship.md "The gill set"): five static crescent niches on the east throat wall, the groove, the turn bars and the
button: their places and sizes (the chords shrinking from the mouth, the bottoms rising gently), nothing before s 1.70
or over the fold, the groove and the button clear of the holes, no colliders and no moving parts, the west wall the east's mirror,
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
        self.assertEqual(G.SLOTS, {1: 2.074, 2: 2.438, 3: 2.801, 4: 3.164, 5: 3.526})   # step 4: spread to the hall
        for sl in G.slits():
            lo, hi = sl.extent()
            self.assertAlmostEqual((lo + hi) / 2, sl.s_mid, delta=0.03, msg=sl.k)     # its middle on the old slot

    def test_sizes_shrink_from_the_mouth(self):
        rows = G.numbers()
        chords = [r["top"] - r["bottom"] for r in rows]
        self.assertTrue(1.02 <= chords[0] <= 1.12, chords)                             # step 4: the mouth side's 1.07
        self.assertTrue(0.68 <= chords[-1] <= 0.78, chords)                            # down to about 0.73
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

    def test_fat_and_open(self):
        """step 4 ("a bigger angle, more open", the picture's): the outer arc sags about 0.33 of the chord, the
        crescent about 0.2 of its height wide at the middle."""
        for r in G.numbers():
            self.assertTrue(0.18 <= r["width"] / r["chord"] <= 0.24, r)
        self.assertAlmostEqual(G.SAG_O / 1.2, 0.333, delta=0.02)

    def test_a_real_cut(self):
        """step 4 ("cut out of the wall, real gills"): 15 cm deep, the hall-side rim overhangs the floor, the lip
        bevelled, only the thin rim glows in the GLB."""
        self.assertAlmostEqual(G.DEPTH, 0.15, delta=0.03)
        for sl in G.slits():
            t, ul, ur = min(sl.rows(), key=lambda r: abs(r[0] - sl.t_mid))
            sec = sl.section(t, ul, ur)
            self.assertGreater(max(u for u, _t, _w in sec), ur + 0.03, sl.k)            # under the hall-side rim
            lip = sec[:G.PARTS["lip"][1] + 1]
            self.assertTrue(0.5 < -lip[-1][2] / (lip[-1][0] - lip[0][0]) < 2.5, lip)    # a bevel, about 45 deg
        self.assertEqual(G.NICHE_MAT["lip"], G.METAL)
        self.assertEqual([k for k, m in G.NICHE_MAT.items() if m.startswith("int_cyan")], ["edge"])

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
        self.assertGreater(c["hole_gap"], 0.04)                                        # the cuts nest, never touch
        self.assertGreater(c["button_hole"], 0.05)                                     # the button clear of slit 5
        self.assertGreater(c["button_end"], 0.005)                                     # and of the end frame
        self.assertGreater(c["groove_t_min"], T.PLINTH_H + 0.02)                       # above the plinth


class Wall(unittest.TestCase):
    def test_nothing_before_1_70_and_under_the_fold(self):
        for n, p in set_parts().items():
            pts = [uvw(v) for v in p["verts"]]
            self.assertGreaterEqual(min(u for u, _t, _w in pts), 1.70, n)
            self.assertLessEqual(max(t for _u, t, _w in pts), T.FOLD - T.GAP_H - 0.01, n)
            self.assertLessEqual(max(u for u, _t, _w in pts), G.END_U, n)

    def test_decor_static_east_only(self):
        e = set_parts("e")
        names = {f"gill{k}_{x}" for k in G.SLITS for x in ("lip", "scoop", "glow", "edge", "bar", "bar_glow")}
        self.assertEqual(set(e), names | {"groove", "groove_glow", "btn_bezel", "btn_ring", "btn_dome"})
        self.assertTrue(all(p.get("nocol") for p in e.values()))                       # no colliders on decor
        self.assertFalse([n for n, p in e.items() if p.get("origin")])                 # nothing moves

    def test_west_mirrors_every_part(self):
        """step 6: the west wall carries the same set, every part the east's mirror in x (faces turned back), so the
        groove sweeps round the mouth side there too and the button sits at the hall end."""
        e, w = set_parts("e"), set_parts("w")
        self.assertEqual(set(w), set(e))
        for n, p in e.items():
            self.assertEqual(w[n]["mat"], p["mat"], n)
            self.assertEqual([(round(-x, 6), round(y, 6), round(h, 6)) for x, y, h in p["verts"]],
                             [(round(x, 6), round(y, 6), round(h, 6)) for x, y, h in w[n]["verts"]], n)
            self.assertEqual([tuple(f[::-1]) for f in p["faces"]], [tuple(f) for f in w[n]["faces"]], n)


class GlowBalance(unittest.TestCase):
    """step 6 (the engineer: slits 1 and 2 "super"; 3-5's glowing rim a hair line in a big unlit lip)."""

    def widths(self, sl):
        w = sl.sag_o - sl.sag_i                                                      # the crescent at its middle
        j0, j1 = G.PARTS["edge"]
        return w * sl.profile[j0][0], w * (sl.profile[j1][0] - sl.profile[j0][0])  # lip, rim (m)

    def test_first_two_unchanged(self):
        for sl in G.slits()[:2]:
            self.assertEqual(sl.profile, G.PROFILE, sl.k)

    def test_rim_holds_its_width_lip_gives_way(self):
        lips, rims = zip(*(self.widths(sl) for sl in G.slits()))
        for k in range(2, 5):   # slits 3-5: the rim at least slit 2's, growing a little; the lip thinner each time
            self.assertGreaterEqual(rims[k], rims[1] - 1e-9, k)
            self.assertGreaterEqual(rims[k], rims[k - 1] - 1e-9, k)
            self.assertLess(lips[k], lips[k - 1], k)
        self.assertLess(rims[4], rims[0] * 1.6)                                       # never a fat band
        for sl in G.slits():    # the lip and rim together keep their share: the inner wall, floor and overhang stay
            self.assertAlmostEqual(sl.profile[G.PARTS["edge"][1]][0], G.PROFILE[G.PARTS["edge"][1]][0], 9)
            self.assertEqual(sl.profile[G.PARTS["edge"][1] + 1:], G.PROFILE[G.PARTS["edge"][1] + 1:])

    def test_rim_and_lip_as_built(self):
        """step 7: the approved widths (GLOW_K 1.6, the engineer's yes of 2026-10-30), mm, slits 1-5; both walls carry
        them (the west is the east's mirror, test_west_mirrors_every_part)."""
        lips, rims = zip(*(self.widths(sl) for sl in G.slits()))
        for got, want in ((rims, (11.0, 10.1, 11.7, 13.6, 16.0)), (lips, (24.2, 22.1, 17.6, 13.1, 8.0))):
            for k, (g, w) in enumerate(zip(got, want)):
                self.assertAlmostEqual(g * 1000, w, delta=0.1, msg=f"slit {k + 1}")

    def test_niches_behind_the_face(self):
        p = parts("e")
        for k in G.SLITS:
            ws = [uvw(v)[2] for x in G.PARTS for v in p[f"gill{k}_{x}"]["verts"]]
            self.assertLessEqual(max(ws), 1e-9)
            self.assertAlmostEqual(min(ws), -G.DEPTH, delta=0.01)
        for n in ("groove", "groove_glow") + tuple(f"gill{k}_bar_glow" for k in G.SLITS):
            ws = [uvw(v)[2] for v in p[n]["verts"]]
            self.assertGreaterEqual(min(ws), -1e-9, n)                                 # proud parts stay in front
        glow = [uvw(v)[2] for v in p["groove_glow"]["verts"]]
        self.assertGreater(min(glow), 0.001)                                           # no coplanar face on the band


class HallEnd(unittest.TestCase):
    def test_no_pillar_the_wall_runs_on(self):
        """step 4 (the engineer's walk: "the pillar has no purpose"): no free-standing jambs; each wall runs on to the
        hall's corner K and ends in a bevelled frame of the same warm metal."""
        self.assertEqual([p["name"] for p in T.th_jambs({}, {})], ["drop"])
        self.assertAlmostEqual(T.JAMB_U, T.WALL_LEN, delta=0.01)
        self.assertEqual(T.END_U, G.END_U)                                             # (literal: no import cycle)
        p = parts("e")
        band_u = max(uvw(v)[0] for v in p["band"]["verts"])
        self.assertAlmostEqual(band_u, T.JAMB_U, delta=1e-6)
        fr = [uvw(v) for v in p["end_frame"]["verts"]]
        self.assertAlmostEqual(min(u for u, _t, _w in fr), G.END_U, delta=1e-6)
        self.assertGreater(max(w for _u, _t, w in fr), T.PLINTH_W)                     # over the plinth
        self.assertIn(p["end_frame"]["mat"], ("int_silver_a", "int_silver_b", "int_silver_c"))


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


class CornerFlats(unittest.TestCase):
    """step 7: the front sockets' flats beside the throat's end frames read lit: their own matte clad, not the end
    frame's mirror-like int_silver_c, and a warm spot aimed at each."""

    def test_clad_is_matte_with_its_own_light_row(self):
        import tomllib
        clad = S.L.MATERIALS["int_silver_c__clad"]
        self.assertLessEqual(clad["metallic"], 0.3)
        self.assertGreaterEqual(clad["roughness"], 0.55)
        self.assertEqual(S.L.MATERIALS["int_silver_c"]["metallic"], 0.8)             # the end frame keeps its metal
        ship = tomllib.loads((ROOT / "layouts" / "ship" / "ship.toml").read_text(encoding="utf-8"))
        row = ship["light"]["mats"]["int_silver_c__clad"]                             # (the family's m 0.45 would win)
        self.assertLessEqual(row["m"], 0.3)
        inner = tomllib.loads((ROOT / "layouts" / "ship" / "interior.toml").read_text(encoding="utf-8"))
        piece = next(p for p in inner["pieces"] if p["id"] == "hall_panel_flat_sockf")
        self.assertEqual(piece["args"]["clad"], "int_silver_c__clad")
        aimed = [l for l in ship["light"]["lamps"] if len(l) > 11 and isinstance(l[11], list)
                 and abs(abs(l[11][0]) - 3.4376) < 1e-6 and abs(l[11][1] + 2.3137) < 1e-6]
        self.assertEqual(sorted(l[0] > 0 for l in aimed), [False, True])              # one spot per flat, mirrored
        self.assertEqual(aimed[0][:2], [-aimed[1][0], aimed[1][1]])


class Proof(unittest.TestCase):
    def test_three_cameras_and_the_clad_views(self):
        """step 7: the demo from the concept camera, the close one and the mouth (both rows); the clad's views on
        both sides."""
        sys.path.insert(0, str(ROOT / "tools"))
        from runner.commands import ship
        self.assertEqual(set(ship.GILL_SET["both"]), {"eye", "look", "fov"})
        names = [v[0] for v in ship.CLAD_VIEWS]
        self.assertEqual(names, ["clad_throat", "w_clad_throat", "clad_hall", "w_clad_hall", "play003", "w_play003"])
        self.assertIn("mouth_both", [v[0] for v in ship.GILL_AXIS_VIEWS])


if __name__ == "__main__":
    unittest.main()
