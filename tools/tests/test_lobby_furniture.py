"""The lobby's bar, mirror and match console (art #389, #390, #391): their specs against the game's greybox (sizes,
markers, placement), no copper in their looks (the engineer, 2026-11-23), the placement maths and the clearance check
(tools/blender/lobby_furniture_run.py). Plain Python: no Blender or Godot; the build's numbers are checked when a raw
build is present."""

import json
import sys
import tomllib
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


class CaptionTest(unittest.TestCase):
    B = {"min": [-110.0, 0.0, 0.0], "max": [110.0, 267.0, 14.0]}

    def test_the_mirror_captions_follow_its_style(self):
        titles = lambda style: " ".join(v[1] for v in R.views("mirror", self.B, style))   # noqa: E731
        self.assertNotIn("fin", titles("frame"))
        self.assertIn("the frame's left side", titles("frame"))
        self.assertIn("fins", titles("spikes"))
        self.assertEqual(R.mirror_style(), R.dims("mirror")["style"]["pick"])


ASSETS = common.ROOT / "assets" / "prop"
# the game's greybox (prime-game levels/lobby/lobby.tscn, match_console.tscn), m: where each package's markers land
GREYBOX = {"bar": {"TapSpot": [-15.0, 0.0, -10.0]}, "match_console": {"Screen": [-7.0, 1.15, 7.04]},
           "mirror": {"MirrorFace": [-19.77, 1.25, 8.0]}}


class PackageTest(unittest.TestCase):
    """The committed game packages (art #389, #390, #391), packed by lobby_furniture_run.py --asset."""

    def load(self, piece: str) -> tuple[dict, dict, dict]:
        a = ASSETS / piece
        return (json.loads((a / "package.json").read_text(encoding="utf-8")),
                json.loads((a / "report.json").read_text(encoding="utf-8")),
                tomllib.loads((a / "manifest.toml").read_text(encoding="utf-8")))

    def test_the_glbs_carry_their_meshes_and_markers(self):
        want = {"bar": ({"bar"}, {"TapSpot", "TapSpout"}),
                "match_console": ({"match_console", "ConsoleScreen"}, {"Screen"}),
                "mirror": ({"mirror", "MirrorGlass"}, {"MirrorFace"})}
        for piece, (meshes, markers) in want.items():
            glb = ASSETS / piece / "export" / f"{piece}.glb"
            g = R.glb_summary(glb)
            self.assertEqual({n for n, v in g["nodes"].items() if v["kind"] == "mesh"}, meshes, piece)
            self.assertEqual({n for n, v in g["nodes"].items() if v["kind"] == "marker"}, markers, piece)
            self.assertEqual(set(g["roots"]), meshes | markers, piece)
            pkg, rep, _man = self.load(piece)
            self.assertEqual(pkg["files"][f"export/{piece}.glb"], R.sha256(glb), piece)
            self.assertEqual(set(pkg["meshes"]), meshes, piece)
            self.assertEqual(set(pkg["markers"]), markers, piece)
            self.assertEqual(g["triangles"], pkg["triangles"], piece)
            self.assertEqual(rep["mesh"]["triangles"], pkg["triangles"], piece)
            self.assertLessEqual(pkg["triangles"], 8000, piece)
            self.assertFalse([m for m in g["materials"] if "copper" in m or "bronze" in m], piece)
            self.assertEqual(rep["gltf_validator"]["numErrors"], 0, piece)
            self.assertEqual(rep["gltf_validator"]["numWarnings"], 0, piece)

    def test_the_markers_land_on_the_greybox(self):
        for piece, marks in GREYBOX.items():
            pkg, rep, _man = self.load(piece)
            o, yaw = R.placement(piece)
            self.assertEqual(pkg["placement"]["origin"], [c / 100.0 for c in o], piece)
            self.assertEqual(pkg["placement"]["yaw_deg"], yaw, piece)
            self.assertEqual(pkg["placement"]["transform"], R.tscn_transform(o, yaw), piece)
            for n, at in marks.items():
                for a, b in zip(pkg["placement"]["markers"][n], at):
                    self.assertAlmostEqual(a, b, delta=0.003, msg=f"{piece} {n}")
            self.assertIsNotNone(rep["godot"], piece)   # Godot's import in the shots placed them where we compute
            self.assertLessEqual(rep["godot"]["max_error_m"], 0.002, piece)
        self.assertEqual(R.tscn_transform([-700.0, 0.0, 720.0], 180.0), "Transform3D(-1, 0, 0, 0, 1, 0, 0, 0, -1, -7, 0, 7.2)")
        self.assertEqual(self.load("mirror")[0]["style"], "frame")

    def test_the_manifests(self):
        for piece in GREYBOX:
            _pkg, _rep, man = self.load(piece)
            self.assertEqual(man["id"], piece)
            self.assertEqual(man["kind"], "prop")
            self.assertEqual(man["licence"], "own-work")
            self.assertIs(man["public_repo_ok"], True)
            self.assertIs(man["ai_generated"], False)
            self.assertEqual(man["approved_by"], ["xperiaroco2"])
            self.assertEqual(str(man["approved_at"]), "2026-11-23")
            self.assertRegex(man["approval_pr"], r"^https://github.com/xperiaroco2/prime-game-art/pull/\d+$")
            raws = [r["file"] for r in man["raw"]]
            self.assertIn(f"lobby/furniture/v6/{piece}/{piece}.glb", raws)
            self.assertTrue(any(r.startswith("2026-11-22-lobby-bar-mirror-console-concepts/") for r in raws), piece)
            handoff = (ASSETS / piece / "HANDOFF.md").read_text(encoding="utf-8")
            for n in R.PACKED[piece]["meshes"] | R.PACKED[piece]["markers"]:
                self.assertIn(f"`{n}`", handoff, piece)


if __name__ == "__main__":
    unittest.main()
