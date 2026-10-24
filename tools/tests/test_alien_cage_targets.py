"""The alien cage's targets (art #196, H1: the chameleon's hybrid body). alien_cage.py runs inside Blender; its targets
loader and the S1c-to-new-skeleton remap are checked here with stub Blender modules: without a targets file every new
path is off (S4b's numbers stay), chameleon_h1.toml loads with its four-finger hand and two toe groups and keeps the
whole character under the height cap, and the remap's piecewise maps hit the new skeleton's stations."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import tomllib
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"
H1 = BLENDER / "alien_cage_targets" / "chameleon_h1.toml"


class _Any:
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
        spec = importlib.util.spec_from_file_location("alien_cage_h1", BLENDER / "alien_cage.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path[:] = path
        if "alien_parts_geom" in sys.modules and "mathutils" in stubs:
            del sys.modules["alien_parts_geom"]
        for name in stubs:
            del sys.modules[name]


class CageTargets(unittest.TestCase):
    def setUp(self):
        self.c = _load()  # a fresh module per test: the loader rewrites its constants

    def test_defaults_keep_s4b(self):
        c = self.c
        self.assertEqual(c.BODY_SCALE, 1.0)
        self.assertFalse(c.CAGE_REMAP)
        self.assertFalse(c.HAND_REL)
        self.assertIsNone(c.HAND_COLS)
        self.assertEqual(c.FINGERS, ("Index", "Middle", "Ring"))
        self.assertEqual(tuple(c.TOE_SET), (0, 1, 2))
        self.assertEqual(tuple(c.FINGER_CURL), (0.0, 0.0, 0.0))
        self.assertEqual(c.ARM_GUESS, (-0.01, 1.34))
        self.assertEqual(c.NECK_END_ELLIPSE, (0.0605, 0.047, 0.0565))
        self.assertEqual((c.TARGET_WELD, c.TARGET_MIRROR, c.TARGET_CLEAN), (0.0, "", []))
        self.assertEqual(c.NECK_END, 1.374)
        self.assertEqual(c.WRAP_X, [(0.15, 0.185), (0.413, 0.355), (0.605, 0.525)])

    def test_h1_loads(self):
        c = self.c
        self.assertEqual(c.apply_cage_targets(H1), "chameleon_h1")
        self.assertEqual(c.FINGERS, ("Index", "Middle", "Ring", "Little"))
        self.assertEqual(len(c.HAND_COLS), len(c.FINGERS) + 1)
        self.assertEqual(c.HAND_COLS, sorted(c.HAND_COLS))
        self.assertEqual(tuple(c.TOE_SET), (0, 2))
        self.assertTrue(c.CAGE_REMAP and c.HAND_REL)
        self.assertEqual(c.TARGET_MIRROR, "+x")  # the left half kept: the jagged seam is on the right
        self.assertEqual(len(c.HAND), len(c.HAND_INNER))
        self.assertTrue(all(len(b) == 7 for b in c.TARGET_CLEAN))
        # slender fingers: a subdivided finger's radius is about 0.7 of FINGER_R; 14 to 17 mm thick
        self.assertTrue(14.0 <= 2 * 0.7 * c.FINGER_R * 1000 <= 17.0)
        self.assertIsInstance(c.FINGER_RINGS[0][3], dict)

    def test_h1_height_under_the_cap(self):
        c = self.c
        c.apply_cage_targets(H1)
        contract = tomllib.loads((ROOT / "contract" / "contract.toml").read_text(encoding="utf-8"))
        cap = next(v for k, v in _walk(contract) if k == "head_top_max_m")
        ring_z, head_above_ring = 1.456, 1.9528 - 1.456  # the refit's ring and its welded top (refit_char)
        top = ring_z * c.BODY_SCALE + head_above_ring
        self.assertLess(top, cap)
        self.assertGreater(top, cap - 0.02)

    def test_unknown_key_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.toml"
            p.write_text('name = "bad"\nFINGER_RADIUS = 0.01\n', encoding="utf-8")
            with self.assertRaises(SystemExit):
                self.c.apply_cage_targets(p)

    def test_cols_must_match_fingers(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.toml"
            p.write_text('FINGERS = ["Index", "Middle", "Ring", "Little"]\nHAND_COLS = [-1, 0, 0.5, 1]\n',
                         encoding="utf-8")
            with self.assertRaises(SystemExit):
                self.c.apply_cage_targets(p)

    def test_pw(self):
        pw = self.c.pw
        t = [(0.0, 0.0), (1.0, 2.0), (2.0, 3.0)]
        self.assertAlmostEqual(pw(t, 0.5), 1.0)
        self.assertAlmostEqual(pw(t, 1.5), 2.5)
        self.assertAlmostEqual(pw(t, 3.0), 4.0)   # slope 1 past the end
        self.assertAlmostEqual(pw([(0.0, 0.0), (1.0, 2.0)], -1.0), -2.0)  # one segment: its slope

    def test_remap_hits_the_new_stations(self):
        c = self.c
        heads = {"LeftFoot": (0.11, 0.09, 0.135), "LeftLowerLeg": (0.11, 0.04, 0.53), "LeftUpperLeg": (0.11, 0.04, 0.89),
                 "Chest": (0, 0, 1.06), "UpperChest": (0, 0, 1.17), "LeftUpperArm": (0.19, 0.06, 1.29),
                 "LeftLowerArm": (0.49, 0.07, 1.29), "LeftHand": (0.767, 0.06, 1.29),
                 "LeftIndexProximal": (0.88, 0.02, 1.28), "LeftToes": (0.11, -0.123, 0.03),
                 "LeftToesTail": (0.11, -0.248, 0.03)}
        tz, tx, ty = c.remap_tables(heads, 1.4432, 0.008)
        self.assertAlmostEqual(c.pw(tz, c.REF_Z["LeftLowerLeg"]), 0.53)
        self.assertAlmostEqual(c.pw(tz, c.REF_RING[0]), 1.4432)
        self.assertAlmostEqual(c.pw(tz, 1.374), 1.4432 - 0.016)
        self.assertAlmostEqual(c.pw(tx, c.REF_X["LeftHand"]), 0.767)
        self.assertAlmostEqual(c.pw(ty, c.REF_FOOT_Y[1]), -0.123)
        wrist = c.WRIST_X
        c.remap_constants(tz, tx, ty)
        self.assertAlmostEqual(c.NECK_END, 1.4432 - 0.016)  # the neck's end stays two ring steps below the ring
        self.assertGreater(c.WRIST_X, wrist)
        self.assertEqual([r[0] for r in c.TRUNK], [r[0] for r in _load().TRUNK])
        zs = [r[1] for r in c.TRUNK]
        self.assertEqual(zs, sorted(zs))


def _walk(d, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _walk(v)
        else:
            yield k, v


if __name__ == "__main__":
    unittest.main()
