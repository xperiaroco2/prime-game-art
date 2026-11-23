"""The lobby's bar, mirror and match console (art #389, #390, #391): their specs against the game's greybox (sizes,
markers, placement), no copper in their looks (the engineer, 2026-11-23), the placement maths and the clearance check
(tools/blender/lobby_furniture_run.py). Plain Python: no Blender or Godot; the build's numbers are checked when a raw
build is present."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))

from runner import common, lobby_layout  # noqa: E402
import lobby_furniture_run as R  # noqa: E402

LAYOUT = lobby_layout.load()


def coppery(look: list) -> bool:
    """A metal whose red stands well over its blue: copper, bronze or brass."""
    (r, _g, b), metal = look[0], look[1]
    return metal >= 0.5 and r - b > 0.12


class SpecsTest(unittest.TestCase):
    def test_the_bar_is_the_greybox(self):
        s = R.dims("bar")
        self.assertEqual((s["size"]["length"], s["size"]["depth"], s["size"]["height"]), (600.0, 100.0, 110.0))
        p = s["placement"]
        self.assertEqual(R.to_hall("bar", (0, 0, 0)), [-16.5, 0.0, -10.0])   # the greybox's box middle
        # the tap spot is the greybox's Tap marker, straight out from the tap
        self.assertEqual(R.to_hall("bar", (0, 0, 150)), [p["tap_spot"][0] / 100, 0.0, p["tap_spot"][2] / 100])
        self.assertEqual(R.footprint("bar", {"min": [-300, 0, -50], "max": [300, 110, 50]}), ([-17.0, -16.0], [-13.0, -7.0]))

    def test_the_mirror_is_the_greybox_glass(self):
        s = R.dims("mirror")
        self.assertEqual((s["glass"]["w"], s["glass"]["h"]), (200.0, 250.0))
        hall = R.to_hall("mirror", (0, 0, 0))
        self.assertAlmostEqual(hall[2], 8.0)
        self.assertGreater(hall[0], LAYOUT["hall"]["x0"])   # on the wall's panels, not in the wall
        for spot in s["placement"]["spots"]:   # the players' places stand in front of the glass
            self.assertGreater(spot[0] / 100, hall[0] + 0.5)
            self.assertLess(abs(spot[2] / 100 - 8.0), s["glass"]["w"] / 200)

    def test_the_console_is_the_greybox(self):
        s = R.dims("match_console")
        b, sc = s["body"], s["screen"]
        self.assertEqual((b["w"], b["h"], b["d"]), (120.0, 160.0, 30.0))
        self.assertEqual(sc["centre_y"], 115.0)   # the greybox's Screen marker at y 1.15
        self.assertEqual(R.to_hall("match_console", (0, 0, 0)), [-7.0, 0.0, 7.2])
        self.assertAlmostEqual(R.to_hall("match_console", (0, 0, 16))[2], 7.04)   # the screen faces -z, as placed

    def test_no_copper(self):
        for piece in R.PIECES:
            for key, look in R.dims(piece)["look"].items():
                self.assertFalse(coppery(look), f"{piece} {key} {look}")


class MugTest(unittest.TestCase):
    """The mug against its contract with the game (the shared note art-mug-392/contract.md)."""

    def test_the_contract_sizes(self):
        s = R.dims("mug")
        rings = s["body"]["rings"]
        self.assertEqual(rings[0][0], 0.0)                     # the origin under the base
        self.assertEqual(rings[-1][0], 15.0)                   # 15 cm tall
        self.assertLessEqual(max(r for _y, r, _f in rings), 4.6)   # 9 cm across (4.5 + the rim's 0.05 flare)
        xs = [x for x, _y in s["handle"]["path"]]
        self.assertLessEqual(max(xs) + s["handle"]["width"] / 2, 8.1)   # the handle reaches x 8 cm
        self.assertGreater(min(xs), 0.0)                       # on +x
        ys = [y for _x, y in s["handle"]["path"]]
        self.assertLessEqual(min(ys), 4.0)                     # the opening spans y 3.5 .. 12.5
        self.assertGreaterEqual(max(ys), 12.5)

    def test_the_grip_is_on_the_handle_bar(self):
        s = R.dims("mug")
        x, y, z = s["grip"]["at"]
        bar = [p for p in s["handle"]["path"] if 4.5 < p[1] < 11.5]
        self.assertTrue(bar)
        self.assertLess(min(abs(x - px) for px, _py in bar), 0.2)
        self.assertTrue(3.5 < y < 12.5)
        self.assertEqual(z, 0.0)

    def test_the_mug_stands_on_the_bar(self):
        on = R.dims("mug")["placement"]["on_bar"]
        self.assertEqual(on[1], R.dims("bar")["size"]["height"])
        self.assertLess(abs(on[0]), R.dims("bar")["size"]["length"] / 2)


class ClearanceTest(unittest.TestCase):
    def test_a_piece_on_a_pilaster_clashes(self):
        b = {"min": [-147.0, 0.0, 0.0], "max": [147.0, 262.0, 14.0]}
        ok = R.clearances("mirror", b, LAYOUT)
        self.assertGreater(ok["pilasters"], 0.0)
        wide = R.clearances("mirror", {"min": [-200.0, 0.0, 0.0], "max": [200.0, 262.0, 14.0]}, LAYOUT)
        self.assertLess(wide["pilasters"], 0.0)   # 2 m from z 8 reaches the pilaster's plinth at z 6.5

    def test_the_bar_clears_the_doors_and_walls(self):
        cl = R.clearances("bar", {"min": [-300.0, 0.0, -50.0], "max": [300.0, 160.0, 50.0]}, LAYOUT)
        self.assertGreater(min(cl["west_wall"], cl["pilasters"], cl["doors"]), 1.0)


BUILD = next((R.BASE / t for t in ("v3", "v2", "v1") if (R.BASE / t / "clearances.json").is_file()), None)


@unittest.skipUnless(BUILD, "needs a raw build (<raw>/lobby/furniture/v*)")
class BuildTest(unittest.TestCase):
    def test_built_pieces_fit_and_carry_their_markers(self):
        cl = json.loads((BUILD / "clearances.json").read_text(encoding="utf-8"))
        for piece, c in cl.items():
            self.assertGreaterEqual(min(c["west_wall"], c["east_wall"], c["south_wall"]), 0.0, piece)
            self.assertGreater(c["pilasters"], 0.0, piece)
            rep = json.loads((BUILD / piece / f"{piece}.json").read_text(encoding="utf-8"))
            self.assertLessEqual(rep["triangles"], 8000, piece)
        mug = BUILD / "mug" / "mug.json"
        if mug.is_file():
            rep = json.loads(mug.read_text(encoding="utf-8"))
            self.assertEqual(rep["meshes"], ["Mug", "Beer"])
            self.assertIn("Grip", rep["markers"])
            self.assertLessEqual(rep["triangles"], 2000)
            self.assertFalse([m for m in rep["triangles_by_material"] if "copper" in m], piece)
        markers = {p: json.loads((BUILD / p / f"{p}.json").read_text(encoding="utf-8"))["markers"] for p in cl}
        self.assertIn("TapSpot", markers.get("bar", {"TapSpot": 1}))
        self.assertIn("Screen", markers.get("match_console", {"Screen": 1}))


if __name__ == "__main__":
    unittest.main()
