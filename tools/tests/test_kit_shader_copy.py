"""The shipped copy of the kit's set shader (assets/kit/house_kit/export/kit_set.gdshader, the game's package) has not
drifted from its source, godot/kit/kit_set.gdshader (house_export.SHADER_SRC, the walk's and the proof's shader): a
change to the source must be shipped with a re-export of the kit's files (docs/house.md "The export")."""

from __future__ import annotations

import unittest
from pathlib import Path

from runner import house_export as X

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "assets" / "kit" / "house_kit" / "export" / X.KIT_SHADER


class KitShaderCopy(unittest.TestCase):
    def test_the_shipped_shader_is_its_source(self):
        self.assertTrue(X.SHADER_SRC.is_file(), X.SHADER_SRC)
        self.assertTrue(SHIPPED.is_file(), SHIPPED)
        src = X.SHADER_SRC.read_bytes().replace(b"\r\n", b"\n")
        shipped = SHIPPED.read_bytes().replace(b"\r\n", b"\n")
        if src != shipped:
            a, b = src.decode("utf-8").splitlines(), shipped.decode("utf-8").splitlines()
            line = next((i for i, (x, y) in enumerate(zip(a, b), 1) if x != y), min(len(a), len(b)) + 1)
            self.fail(f"{SHIPPED.relative_to(ROOT).as_posix()} differs from {X.SHADER_SRC.relative_to(ROOT).as_posix()} from line {line}; "
                      "re-export the kit's files (docs/house.md \"The export\") or put the source back")


if __name__ == "__main__":
    unittest.main()
