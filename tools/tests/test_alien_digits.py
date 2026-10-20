"""The alien's longer, slimmer digits and the mouth-free AO (art #196, M7). alien_cage.py runs inside Blender; its
digit helpers are loaded here with stub Blender modules. The AO bakes (alien_ao, alien_detail, alien_texture) show
the eyes alone: a mouth piece in the bake left a black band on the skin round the smaller mouth shapes."""
from __future__ import annotations

import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"


class _Any:
    """A stand-in for mathutils' classes: module-level defaults such as Vector((0, 0, 1)) only need to construct."""

    def __init__(self, *args, **kwargs):
        pass


def _load():
    stubs = {}
    for name in ("bmesh", "bpy", "mathutils"):
        if name not in sys.modules:
            stubs[name] = sys.modules[name] = types.ModuleType(name)
    for cls in ("Vector", "Matrix"):
        setattr(sys.modules["mathutils"], cls, getattr(sys.modules["mathutils"], cls, _Any))
    path = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("alien_cage_m7", BLENDER / "alien_cage.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path[:] = path
        if "alien_parts_geom" in sys.modules and "mathutils" in stubs:
            del sys.modules["alien_parts_geom"]  # built on the stubs: never reused by another test
        for name in stubs:
            del sys.modules[name]


class AlienDigits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = _load()

    def setUp(self):
        self.saved = {k: getattr(self.c, k) for k in self.c.DIGITS}

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(self.c, k, v)

    def test_the_pick_is_longer_and_slimmer_than_s9(self):
        c = self.c
        self.assertAlmostEqual(c.FINGER_K, 0.82 * 1.2, places=4)  # S9: 0.82
        self.assertAlmostEqual(c.FINGER_R, 0.0208 * 0.8, places=5)  # S9: 0.0208
        self.assertAlmostEqual(c.THUMB_LEN, 0.062 * 1.2, places=4)
        self.assertAlmostEqual(c.THUMB_R, 0.0215 * 0.8, places=5)
        self.assertEqual((c.TOE_LEN, c.TOE_THICK), (1.2, 0.8))
        self.assertLessEqual(c.FINGER_K, 1.0)  # the mesh's joints never pass the bones'
        self.assertEqual(c.THUMB_R0, 0.0215)  # the thumb's root keeps S9's size

    def test_thumb_thins_past_its_root_only(self):
        c = self.c
        end = c.THUMB_R / c.THUMB_R0
        self.assertEqual(c.thumb_thin(0.0), 1.0)
        self.assertEqual(c.thumb_thin(0.2), 1.0)
        self.assertAlmostEqual(c.thumb_thin(0.56), end)
        self.assertAlmostEqual(c.thumb_thin(1.0), end)
        ts = [i / 100 for i in range(101)]
        ks = [c.thumb_thin(t) for t in ts]
        for a, b in zip(ks, ks[1:]):  # monotone: no bulge on the way
            self.assertLessEqual(b, a + 1e-12)

    def test_toe_rings(self):
        c = self.c
        fwd, sw, sh = c.toe_ring(0, 0.014, 1.04, 1.0)
        self.assertAlmostEqual(fwd, 0.014 * c.TOE_LEN)
        self.assertAlmostEqual(sw, 1.04 * (1 + (c.TOE_THICK - 1) * 0.5))  # the first ring by half the thinning
        fwd, sw, sh = c.toe_ring(3, 0.045, 0.48, 0.46)
        self.assertAlmostEqual(sh, 0.46 * c.TOE_THICK)

    def test_set_digits(self):
        c = self.c
        c.set_digits({"FINGER_K": 0.82, "TOE_LEN": "1.0"})
        self.assertEqual((c.FINGER_K, c.TOE_LEN), (0.82, 1.0))
        with self.assertRaises(SystemExit):
            c.set_digits({"FINGER_LEN": 1.0})

    def test_finger_k_matches_the_detail_sculpt(self):
        detail = (BLENDER / "alien_detail.py").read_text(encoding="utf-8")
        self.assertEqual(float(re.search(r"^FINGER_K = ([0-9.]+)", detail, re.M).group(1)), self.c.FINGER_K)


class AlienAoShowsNoMouth(unittest.TestCase):
    def test_no_mouth_piece_in_any_ao_bake(self):
        for name in ("alien_ao.py", "alien_detail.py", "alien_texture.py"):
            text = (BLENDER / name).read_text(encoding="utf-8")
            m = re.search(r"^SHOWN = \(([^)]*)\)", text, re.M)
            self.assertIsNotNone(m, name)
            shown = re.findall(r'"([^"]+)"', m.group(1))
            self.assertEqual(shown, ["eye_bored_"], name)
            self.assertFalse([s for s in shown if "mouth" in s], name)


if __name__ == "__main__":
    unittest.main()
