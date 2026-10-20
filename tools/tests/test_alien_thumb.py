"""The thumb's blended skin weights (art #196, M10b and PR #245's review): alien_thumb's shares along the thumb, the
blend on single vertices, the axis parameter, the cage's weights kept for the texture masks, and the wiring."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"
spec = importlib.util.spec_from_file_location("alien_thumb_m10b", BLENDER / "alien_thumb.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

US = [i / 100 for i in range(101)]
WARM = {"Distal": 1.0, "Intermediate": 1.0, "Proximal": 0.8, "Metacarpal": 0.4}  # alien_texture's warm fingers


def warm(w: dict[str, float]) -> float:
    """alien_texture.group_weights' sum for one vertex (the first matching prefix per group)."""
    out = 0.0
    for name, x in w.items():
        for p, k in WARM.items():
            if p in name:
                out += x * k
                break
    return out


class SharesTest(unittest.TestCase):
    def test_they_add_up_and_are_never_negative(self):
        for u in US:
            sh = T.shares(u)
            self.assertAlmostEqual(sum(sh.values()), 1.0)
            self.assertTrue(all(x >= -1e-12 for x in sh.values()), (u, sh))

    def test_the_root_hangs_on_the_metacarpal_and_the_hand_only(self):
        sh = T.shares(0.0)
        self.assertEqual((sh["Proximal"], sh["Distal"]), (0.0, 0.0))
        self.assertAlmostEqual(sh["Hand"], T.HAND)

    def test_the_tip_follows_proximal_and_distal_the_curl(self):
        sh = T.shares(1.0)
        self.assertGreater(sh["Proximal"], 0.1)
        self.assertGreater(sh["Distal"], 0.1)

    def test_the_shares_grow_toward_the_tip_and_change_slowly(self):
        for s in ("Proximal", "Distal"):
            vals = [T.shares(u)[s] for u in US]
            self.assertEqual(vals, sorted(vals), s)
            steps = [abs(b - a) / 0.01 for a, b in zip(vals, vals[1:])]
            self.assertLess(max(steps), 1.0, s)  # per unit of u: no ring-by-ring step (the swelling's cause)


class BlendTest(unittest.TestCase):
    def test_the_thumb_weight_is_split_and_the_total_kept(self):
        w = {"LeftHand": 0.3, "LeftThumbMetacarpal": 0.5, "LeftThumbProximal": 0.2}
        out = T.blend(w, "Left", 0.8)
        self.assertAlmostEqual(sum(out.values()), 1.0)
        sh = T.shares(0.8)
        self.assertAlmostEqual(out["LeftThumbDistal"], 0.7 * sh["Distal"])
        self.assertAlmostEqual(out["LeftHand"], 0.3 + 0.7 * sh["Hand"])

    def test_other_groups_and_the_other_side_are_untouched(self):
        w = {"LeftIndexProximal": 0.1, "RightThumbDistal": 0.5, "LeftThumbDistal": 0.4}
        out = T.blend(w, "Left", 1.0)
        self.assertEqual(out["LeftIndexProximal"], 0.1)
        self.assertEqual(out["RightThumbDistal"], 0.5)
        self.assertEqual(T.blend({"LeftHand": 1.0}, "Left", 0.5), {"LeftHand": 1.0})

    def test_at_most_four_influences_on_a_thumb_vertex(self):
        for u in US:
            self.assertLessEqual(len(T.blend({"LeftThumbDistal": 1.0}, "Left", u)), 4)


class AxisTest(unittest.TestCase):
    def test_u_runs_from_the_root_blend_to_the_tip(self):
        pts = [(0.0, 0.0, 0.0), (0.0, 0.01, 0.0)] + [(0.01 * i, 0.0, 0.0) for i in range(1, 9)]
        tot = [0.5, 0.5] + [1.0] * 8
        u = T.axis_params(pts, tot)
        self.assertAlmostEqual(u[-1], 1.0)
        self.assertEqual(u[2:], sorted(u[2:]))
        self.assertTrue(all(0.0 <= x <= 1.0 for x in u))
        self.assertLess(u[0], 0.1)


class CageTest(unittest.TestCase):
    """A re-texture of a blended Body reads the cage's weights back (finding 6: the thumb tip's warm tint)."""

    def test_cage_view_undoes_the_blend(self):
        for w in ({"LeftThumbDistal": 1.0}, {"LeftHand": 0.6, "LeftThumbMetacarpal": 0.4},
                  {"LeftThumbProximal": 0.2, "LeftThumbDistal": 0.8}):
            new = T.blend(w, "Left", 0.9)
            keep = {k: w.get(f"Left{k}", 0.0) for k in T.CAGE_KEYS}
            back = T.cage_view(new, T.side_of(new), keep)
            self.assertEqual(set(back), set(w))
            for k, x in w.items():
                self.assertAlmostEqual(back[k], x)

    def test_the_tip_keeps_its_warm_tint(self):
        w = {"RightThumbDistal": 1.0}
        new = T.blend(w, "Right", 1.0)
        self.assertLess(warm(new), 0.6)  # the blended groups alone would lose most of the tint
        keep = {k: w.get(f"Right{k}", 0.0) for k in T.CAGE_KEYS}
        self.assertAlmostEqual(warm(T.cage_view(new, "Right", keep)), 1.0)

    def test_stored_reads_the_attributes_of_a_marked_mesh(self):
        class Attr:
            def __init__(self, vals):
                self.data = [type("D", (), {"value": v})() for v in vals]

        class Obj(dict):
            pass

        o = Obj()
        o.data = type("M", (), {})()
        vals = {"ThumbMetacarpal": [0.0, 0.4], "ThumbProximal": [0.0, 0.0], "ThumbDistal": [0.0, 0.6],
                "Hand": [1.0, 0.0]}
        o.data.attributes = {T.CAGE_ATTR.format(k): Attr(v) for k, v in vals.items()}
        self.assertIsNone(T.stored(o))  # no marker: the groups are the cage's
        o[T.MARKER] = json.dumps({})
        self.assertEqual(T.stored(o), {1: {"ThumbMetacarpal": 0.4, "ThumbProximal": 0.0, "ThumbDistal": 0.6,
                                           "Hand": 0.0}})


class WiringTest(unittest.TestCase):
    def test_alien_m6_applies_it_by_default(self):
        src = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")
        self.assertIn('"--thumb", choices=("blend", "segments"), default="blend"', src)
        self.assertIn("alien_thumb.apply(body)", src)

    def test_the_texture_masks_read_the_cage(self):
        src = (BLENDER / "alien_texture.py").read_text(encoding="utf-8")
        body = src[src.index("def group_weights"):src.index("def bbox")]
        self.assertIn("alien_thumb.stored(obj)", body)
        self.assertIn("alien_thumb.cage_view(", body)

    def test_the_kept_weights_never_reach_the_glb(self):
        src = (BLENDER / "export_glb.py").read_text(encoding="utf-8")
        self.assertIn('"export_attributes": False', src)


if __name__ == "__main__":
    unittest.main()
