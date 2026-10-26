"""The ship stations' shared metal shader (art#263): every copy byte-identical to godot/console/console_metal.gdshader
(the start console's, the crystal socket's, the breaker board's and the crystal charger's, in godot/ and in their asset
exports), and its noise for the dent and wave slopes (fix1): a smooth gradient noise, each slope behind its own guard,
the slope from the noise's exact derivative (option A, 2026-10-26), not a forward difference."""

from __future__ import annotations

import re
import unittest

from runner import common

MASTER = common.ROOT / "godot" / "console" / "console_metal.gdshader"
COPIES = (
    "assets/prop/start_console/export/console_metal.gdshader",
    "godot/socket/socket_metal.gdshader",
    "assets/prop/crystal_socket/export/socket_metal.gdshader",
    "godot/board/board_metal.gdshader",
    "assets/prop/breaker_board/export/board_metal.gdshader",
    "assets/prop/crystal_charger/export/console_metal.gdshader",
)


class MetalShaderTest(unittest.TestCase):
    def test_every_copy_is_the_same_bytes(self) -> None:
        master = MASTER.read_bytes()
        for rel in COPIES:
            self.assertEqual((common.ROOT / rel).read_bytes(), master, f"{rel} forked from {MASTER.name}")

    def test_no_other_copy_hides_elsewhere(self) -> None:
        """A shader file under godot/ or assets/ with the master's uniforms is one of the listed copies."""
        master = MASTER.read_bytes()
        listed = {MASTER.resolve(), *((common.ROOT / rel).resolve() for rel in COPIES)}
        for root in (common.ROOT / "godot", common.ROOT / "assets"):
            for path in root.rglob("*.gdshader"):
                if ".godot" in path.parts or "import" in path.relative_to(common.ROOT).parts[:2]:
                    continue
                text = path.read_bytes()
                if b"uniform float wave_scale" in text and b"uniform float edge_polish" in text:
                    self.assertIn(path.resolve(), listed, f"{path} is an unlisted copy")
                    self.assertEqual(text, master, path)

    def test_the_slopes_are_smooth_and_guarded(self) -> None:
        src = MASTER.read_text(encoding="utf-8")
        slope = src[src.index("vec3 slope("):src.index("void fragment()")]
        self.assertEqual(slope.count("gnoised("), 2)   # two octaves of the gradient noise with its derivative
        self.assertNotRegex(slope, r"\bnoise\(")       # not the value noise noise()
        # option A (2026-10-26): the exact derivative, no forward difference (four field() calls per slope, 64 hashes)
        for gone in ("float field(", "float gnoise(", "0.3 / s"):
            self.assertNotIn(gone, src)
        noised = src[src.index("vec4 gnoised("):src.index("vec3 slope(")]
        self.assertEqual(noised.count("ghash("), 8)     # one pass over the cell's corners
        self.assertIn("f * f * f * (f * (f * 6.0 - 15.0) + 10.0)", noised)   # the quintic fade: no crease in the slope
        self.assertIn("30.0 * f * f * (f * (f - 2.0) + 1.0)", noised)        # and its derivative
        self.assertIn("vec3 q = TURN * ((p + vec3(0.15 / s)) * s);", slope)  # at the old difference's midpoint
        self.assertRegex(src, r"if \(dent > 0\.0\) \{\s*bend \+= slope\(mpos, nm, dent_scale\) \* dent;")
        self.assertRegex(src, r"if \(wave > 0\.0\) \{\s*bend \+= slope\(mpos, nm, wave_scale\) \* wave;")
        # the console's defaults: both off, so its pixels skip the whole bend
        for name in ("dent", "wave", "shade"):
            self.assertRegex(src, rf"uniform float {name} : hint_range\([^)]*\) = 0\.0;")
        self.assertTrue(re.search(r"if \(dent > 0\.0 \|\| wave > 0\.0\)", src))

    def test_the_cost_harness_fits_the_shader(self) -> None:
        """godot/ship/metal_cost.gd drops slope()'s second-octave line and swaps gnoised() and slope() for FINITE."""
        src = MASTER.read_text(encoding="utf-8")
        tool = (common.ROOT / "godot" / "ship" / "metal_cost.gd").read_text(encoding="utf-8")
        line = re.search(r'^const TWO_OCTAVES = "(.*)"$', tool, re.M).group(1)
        self.assertIn(line.replace("\\t", "\t").replace("\\n", "\n"), src)
        finite = tool[tool.index('const FINITE = """'):]
        for fn in ("float gnoise(vec3 p)", "float field(vec3 p, float s)", "vec3 slope(vec3 p, vec3 nrm, float s)"):
            self.assertIn(fn, finite)


if __name__ == "__main__":
    unittest.main()
