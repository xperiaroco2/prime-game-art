"""The first-person hands' clip spec (art#136, prime-game#1587; tools/blender/fp_hands.toml, docs/animations.md "The
first-person hands"): every clip names a pose that exists, every grip it names exists (this file's [grips] or
alien_hands.toml's), every key's fields are known with its times rising from 0 to the clip's end, the hits last at
most 0.5 s (GDD "Melee: any item hits": one swing each 0.5 s) with the contact inside, the loops are named _Loop and
have no keys, and the reel of fp_hands_run.py plays only clips that exist. Pure Python, no Blender."""

from __future__ import annotations

import ast
import tomllib
import unittest

from runner import common

BLENDER = common.ROOT / "tools" / "blender"
SPEC = tomllib.loads((BLENDER / "fp_hands.toml").read_text(encoding="utf-8"))
HANDS = tomllib.loads((BLENDER / "anim_sets" / "alien_hands.toml").read_text(encoding="utf-8"))
GRIPS = set(SPEC.get("grips", {})) | set(HANDS.get("grips", {}))
KEY_FIELDS = {"t", "ease", "R", "grip_R", "grip_L", "fist", "crystal", "shoulder_R", "shoulder_L"}
EASES = {"linear", "in", "out", "inout"}
HIT_MAX_S = 0.5


def reel() -> list[str]:
    """fp_hands_run.py's REEL clip names, read from its source (it imports the runner, which needs no Blender, but
    this keeps the test to the file's text)."""
    tree = ast.parse((BLENDER / "fp_hands_run.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "REEL" for t in node.targets):
            return [e.elts[0].value for e in node.value.elts]
    raise AssertionError("fp_hands_run.py has no REEL")


class FpHandsSpec(unittest.TestCase):
    def test_poses_and_grips_exist(self):
        for name, pose in SPEC["poses"].items():
            for k in ("grip_R", "grip_L"):
                if k in pose:
                    self.assertIn(pose[k], GRIPS, f"pose {name} {k}")
            if "R_c" in pose:
                self.assertIn("L_c", pose, f"pose {name}: both hands on the crystal")
                for k in ("R_c", "L_c"):
                    self.assertEqual(set(pose[k]), {"z", "toward", "r", "wrap"}, f"pose {name} {k}")
        for name, clip in SPEC["clips"].items():
            self.assertIn(clip["pose"], SPEC["poses"], name)

    def test_keys(self):
        for name, clip in SPEC["clips"].items():
            keys = clip.get("keys", [])
            if name.endswith("_Loop"):
                self.assertEqual(keys, [], f"{name}: a loop sways, it has no keys")
                self.assertTrue("sway" in clip or "run" in clip, name)
                continue
            self.assertTrue(keys, name)
            times = [k["t"] for k in keys]
            self.assertEqual(times[0], 0.0, name)
            self.assertAlmostEqual(times[-1], clip["seconds"], places=6, msg=name)
            self.assertEqual(times, sorted(set(times)), f"{name}: key times rise")
            for k in keys:
                self.assertLessEqual(set(k), KEY_FIELDS, f"{name} at {k['t']}")
                self.assertIn(k.get("ease", "inout"), EASES, name)
                for g in ("grip_R", "grip_L"):
                    if g in k:
                        self.assertIn(k[g], GRIPS, name)
                if isinstance(k.get("R"), str):
                    self.assertIn(k["R"], SPEC["poses"], name)

    def test_hits(self):
        hits = {n: c for n, c in SPEC["clips"].items() if "hit" in c}
        self.assertEqual(set(hits), {"Punch", "Crystal_Hit"})
        for name, clip in hits.items():
            self.assertLessEqual(clip["seconds"], HIT_MAX_S, name)
            self.assertTrue(0.0 < clip["hit"] < clip["seconds"], name)
            first, last = clip["keys"][0], clip["keys"][-1]
            self.assertEqual(set(first) - {"t", "ease"}, set(), f"{name} starts in its pose")
            self.assertLessEqual(set(last) - {"t", "ease", "fist"}, set(), f"{name} ends in its pose")
            self.assertEqual(last.get("fist", 0.0), 0.0, name)

    def test_reel(self):
        for name in reel():
            self.assertIn(name, SPEC["clips"])


if __name__ == "__main__":
    unittest.main()
