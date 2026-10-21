"""M17 (art #196, brief UPDATE 36): the lids' baked AO (alien_m6.bake_parts_ao). The lids turn in the socket, so AO
baked with the skin at the rest pose rode on the manic upper lid into its closed state as a light diagonal band.
`LID_AO` picks how the lids are baked; the lid states are alien.gd's and the poses alien_lashes.py's. Plain Python:
the Blender and GDScript sources are read by pattern."""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
M6 = (ROOT / "tools" / "blender" / "alien_m6.py").read_text(encoding="utf-8")
LASHES = (ROOT / "tools" / "blender" / "alien_lashes.py").read_text(encoding="utf-8")
GD = (ROOT / "godot" / "alien" / "alien.gd").read_text(encoding="utf-8")


def consts(src: str) -> dict:
    tree = ast.parse(src)
    return {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper()
            and isinstance(n.value, (ast.Constant, ast.Tuple, ast.Dict, ast.List))}


class LidAo(unittest.TestCase):
    def setUp(self):
        self.c = consts(M6)

    def test_the_pick_is_a_known_mode(self):
        self.assertEqual(self.c["LID_AO_MODES"], ("rest", "states", "free"))
        self.assertIn(self.c["LID_AO"], self.c["LID_AO_MODES"])
        self.assertNotEqual(self.c["LID_AO"], "rest")  # the pick is pose-independent (the band's cause)

    def test_the_states_are_the_rigs(self):
        """Every lid state alien.gd's lid table has (bored's upper lid: open, rest, half, closed) is baked, and only
        those."""
        m = re.search(r'"bored": \{"upper": \{([^}]*)\}', GD)
        self.assertIsNotNone(m)
        gd = re.findall(r'"(\w+)":', m.group(1))
        self.assertEqual(sorted(gd), sorted(self.c["LID_STATES"]))

    def test_the_pose_is_the_lashes_pose(self):
        """The lids are posed as alien_lashes.py poses them (rotation_euler.x = -radians(EYES[...][state]))."""
        self.assertIn('rotation_euler.x = -math.radians(EYES[d]["upper"][st])', LASHES)
        self.assertIn("o.rotation_euler.x = -math.radians(EYES[d][lid][st])", M6)

    def test_the_kit_passes_the_mode(self):
        self.assertIn("bake_parts_ao(body, lid_ao=a.lid_ao)", M6)
        self.assertIn("default=LID_AO", M6)


if __name__ == "__main__":
    unittest.main()
