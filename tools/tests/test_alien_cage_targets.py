"""The alien cage's targets (art #196, H1: the chameleon's hybrid body). alien_cage.py runs inside Blender; its targets
loader and the S1c-to-new-skeleton remap are checked here with stub Blender modules: without a targets file every new
path is off (S4b's numbers stay), chameleon_h1.toml loads with its four-finger hand and two toe groups and keeps the
whole character under the height cap, and the remap's piecewise maps hit the new skeleton's stations. H2:
chameleon_h2.toml is H1's numbers (by `include`) with the projection onto the target on. H3: chameleon_h3.toml is
H2's with the shaping after the projection, the toes turned out and the new hand; the shaping is off by default. H4:
chameleon_h4.toml is H3's with the neck's back cleaned on the target, the trunk and chest shaped and the knee's and
hip's weights spread; all three are off by default. H4b: chameleon_h4b.toml is H4's with the feet rebuilt (the last
foot ring's columns: FOOT_END), the thumb along the palm's side and more of the target's relief on the trunk
(PROJECT_DETAIL); both new knobs are off by default."""
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
H2 = BLENDER / "alien_cage_targets" / "chameleon_h2.toml"
H3 = BLENDER / "alien_cage_targets" / "chameleon_h3.toml"
H3_KEYS = {"PROJECT_THICK", "PROJECT_NECK", "SCULPT_ARM", "SCULPT_DELTOID", "SCULPT_THIGH", "NECK_RELAX", "TOE",
           "TOE_LEN", "TOE_YAW", "HAND", "FINGER_R", "FINGER_RINGS", "THUMB_R0", "THUMB_R", "THUMB_OUT", "THUMB_LEN",
           "THUMB_DIR"}
H4 = BLENDER / "alien_cage_targets" / "chameleon_h4.toml"
H4_KEYS = {"TARGET_CLEAN", "SCULPT_ARM", "SCULPT_TRUNK", "TRUNK_X", "SCULPT_PEC", "TOE", "TOE_YAW", "THUMB_R0",
           "THUMB_OUT", "WEIGHT_ZONES"}
H4B = BLENDER / "alien_cage_targets" / "chameleon_h4b.toml"
H4B_KEYS = {"FOOT", "FOOT_END", "TOE", "TOE_YAW", "THUMB_DIR", "THUMB_OUT", "THUMB_LEN", "PROJECT_DETAIL", "PROJECT_THICK",
            "SCULPT_PEC"}


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
        self.assertFalse(c.PROJECT)
        self.assertEqual((c.SCULPT_ARM, c.SCULPT_DELTOID, c.SCULPT_THIGH, c.NECK_RELAX), ([], [], [], []))
        self.assertEqual(tuple(c.TOE_YAW), (0.0, 0.0, 0.0))
        self.assertEqual((c.SCULPT_TRUNK, c.SCULPT_PEC, c.WEIGHT_ZONES), ([], [], []))  # H4: off
        self.assertEqual((c.FOOT_END, c.PROJECT_DETAIL), ([], []))  # H4b: off
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

    def test_h2_is_h1_with_the_projection(self):
        h1 = _load()
        h1.apply_cage_targets(H1)
        c = self.c
        self.assertEqual(c.apply_cage_targets(H2), "chameleon_h2")
        self.assertTrue(c.PROJECT)
        self.assertFalse(h1.PROJECT)
        for k in h1.CAGE_KEYS:
            if not k.startswith("PROJECT"):
                self.assertEqual(getattr(c, k), getattr(h1, k), k)
        self.assertEqual(set(c.PROJECT_THICK), {"trunk", "arm", "leg"})
        self.assertTrue(all(0.8 <= v <= 1.3 for v in c.PROJECT_THICK.values()))
        full, zero = c.PROJECT_HAND
        self.assertGreater(full, zero)  # metres before the wrist: full further in, zero at the wrist
        full, zero = c.PROJECT_NECK
        self.assertGreater(full, zero)
        self.assertGreaterEqual(zero, 0.016)  # nothing moves within the ring's two steps (the weld)

    def test_h3_is_h2_with_the_shaping(self):
        h2 = _load()
        h2.apply_cage_targets(H2)
        c = self.c
        self.assertEqual(c.apply_cage_targets(H3), "chameleon_h3")
        for k in h2.CAGE_KEYS:
            if k not in H3_KEYS:
                self.assertEqual(getattr(c, k), getattr(h2, k), k)
        self.assertEqual(c.PROJECT_THICK["arm"], 1.0)
        self.assertEqual(len(c.TOE_YAW), 3)
        self.assertLess(c.TOE_YAW[0], 0.0)
        self.assertGreater(c.TOE_YAW[2], 0.0)  # the outer toe group turned out
        s = [r[0] for r in c.SCULPT_ARM]
        self.assertEqual(s, sorted(s))
        self.assertTrue(all(len(r) == 3 and r[1] >= 0 and r[2] >= 0 for r in c.SCULPT_ARM))
        s0, sp, s1, push = c.SCULPT_DELTOID
        self.assertTrue(s0 < sp < s1 and 0 < push < 0.03)
        z0, z1, margin, xmax = c.SCULPT_THIGH
        self.assertTrue(z0 < z1 and margin > 0 and 0.14 < xmax < 0.2)
        lo, hi, passes = c.NECK_RELAX
        self.assertGreater(lo, hi)
        self.assertGreaterEqual(hi, 0.012)  # the ring's weld does not move
        self.assertEqual(len(c.HAND), len(c.HAND_INNER))
        xs = [r[0] for r in c.HAND]
        self.assertEqual(xs, sorted(xs))
        self.assertTrue(0.3 <= (xs[1] + xs[2]) / 2 / xs[-1] <= 0.4)  # the thumb's root quad at about 35 % of the palm

    def test_h4_is_h3_with_the_close_range_fixes(self):
        h3 = _load()
        h3.apply_cage_targets(H3)
        c = self.c
        self.assertEqual(c.apply_cage_targets(H4), "chameleon_h4")
        for k in h3.CAGE_KEYS:
            if k not in H4_KEYS:
                self.assertEqual(getattr(c, k), getattr(h3, k), k)
        self.assertEqual(c.TARGET_CLEAN[:len(h3.TARGET_CLEAN)], h3.TARGET_CLEAN)  # H1's boxes kept, one added
        self.assertEqual(len(c.TARGET_CLEAN), len(h3.TARGET_CLEAN) + 1)
        x0, x1, y0, y1, z0, z1, _ = c.TARGET_CLEAN[-1]
        self.assertTrue(x1 > 0 and y1 > 0.1 and z0 < 1.3 < z1)  # the neck's back on the kept +x half
        zs = [r[0] for r in c.SCULPT_TRUNK]
        self.assertEqual(zs, sorted(zs))
        self.assertEqual(c.SCULPT_TRUNK[0][1:], [1.0, 1.0])  # nothing moves at the crotch or the armpits
        self.assertEqual(c.SCULPT_TRUNK[-1][1:], [1.0, 1.0])
        self.assertTrue(all(1.0 <= r[1] <= 1.12 and 1.0 <= r[2] <= 1.1 for r in c.SCULPT_TRUNK))
        x0, x1, z0, z1, push, edge = c.SCULPT_PEC
        self.assertTrue(0 <= x0 < x1 < 0.2 and z0 + edge < z1 and 0 < push <= 0.02)
        self.assertLess(c.TOE_YAW[2], h3.TOE_YAW[2])  # the outer toe group turned out less
        self.assertLess(c.THUMB_R0, h3.THUMB_R0)
        self.assertTrue(all(len(b) == 7 and b[0] < b[1] and b[4] < b[5] for b in c.WEIGHT_ZONES))

    def test_h4b_is_h4_with_the_feet_thumb_and_trunk(self):
        h4 = _load()
        h4.apply_cage_targets(H4)
        c = self.c
        self.assertEqual(c.apply_cage_targets(H4B), "chameleon_h4b")
        for k in h4.CAGE_KEYS:
            if k not in H4B_KEYS:
                self.assertEqual(getattr(c, k), getattr(h4, k), k)
        self.assertEqual(len(c.FOOT), len(h4.FOOT))
        self.assertGreater(c.FOOT[-1][0], h4.FOOT[-1][0])  # the toes split further back (y: + is the heel)
        self.assertEqual([r[0] for r in c.FOOT], sorted((r[0] for r in c.FOOT), reverse=True))
        u, top_mid, top_side, bottom_side = c.FOOT_END
        self.assertTrue(0 < u < 0.4)  # a slit, not H1's wedge quad (0.4)
        self.assertTrue(0 < top_side <= top_mid <= 1.0 and 0 < bottom_side <= 1.0)
        fwd = [r[0] for r in c.TOE]
        self.assertEqual(fwd, sorted(fwd))
        self.assertGreater(fwd[-1], h4.TOE[-1][0])  # longer toes
        widths = [r[1] for r in c.TOE]
        self.assertEqual(widths, sorted(widths, reverse=True))  # tapering to the tip
        self.assertLess(c.TOE_YAW[2], h4.TOE_YAW[2])  # nearly parallel
        dx, dy, dz = c.THUMB_DIR
        self.assertGreater(dx, h4.THUMB_DIR[0])  # more down the hand, less at the camera
        self.assertGreater(dy, h4.THUMB_DIR[1])
        self.assertGreater(c.THUMB_OUT, h4.THUMB_OUT)  # the root further out (a short one folds)
        self.assertGreater(c.THUMB_LEN, h4.THUMB_LEN)
        self.assertTrue(all(len(b) == 7 and b[0] < b[1] and b[2] < b[3] and b[4] < b[5] and 0 < b[6] <= 1.0
                            for b in c.PROJECT_DETAIL))
        self.assertTrue(all(b[3] < 0.1 for b in c.PROJECT_DETAIL))  # the back (+y) left out

    def test_detail_gain(self):
        c = self.c
        P = types.SimpleNamespace
        smooth = lambda t: max(0.0, min(1.0, t)) ** 2 * (3 - 2 * max(0.0, min(1.0, t)))  # noqa: E731
        c.smooth01 = getattr(c, "smooth01", smooth)
        self.assertEqual(c.detail_gain(P(x=0.1, y=0.0, z=1.0)), 0.0)  # off: no boxes
        c.PROJECT_DETAIL = [[0.0, 0.2, -0.3, 0.04, 0.8, 1.36, 0.8]]
        self.assertAlmostEqual(c.detail_gain(P(x=-0.1, y=-0.1, z=1.1)), 0.8)  # inside, mirrored in x
        self.assertEqual(c.detail_gain(P(x=0.1, y=0.1, z=1.1)), 0.0)  # the back
        mid = c.detail_gain(P(x=0.1, y=0.03, z=1.1))  # inside the soft edge
        self.assertTrue(0.0 < mid < 0.8)

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
