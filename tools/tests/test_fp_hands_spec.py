"""The first-person hands' clip spec (art#136, prime-game#1587; tools/blender/fp_hands.toml, docs/animations.md "The
first-person hands"): every clip names a pose that exists, every grip it names exists (this file's [grips] or
alien_hands.toml's), every key's fields are known with its times rising from 0 to the clip's end, the hits last at
most 0.5 s (GDD "Melee: any item hits": one swing each 0.5 s) with the contact inside, the loops are named _Loop and
have no keys, and the reel of fp_hands_run.py plays only clips that exist. Since the viewmodel rebuild (the
engineer's direction of 2026-11-11): every key pose has a target frame, its fitted values (fp_hands_fit.json) bend no
wrist past [view] bend_max_deg, and every mix in a key names poses that exist. Pure Python, no Blender."""

from __future__ import annotations

import ast
import json
import tomllib
import unittest

from runner import common

BLENDER = common.ROOT / "tools" / "blender"
SPEC = tomllib.loads((BLENDER / "fp_hands.toml").read_text(encoding="utf-8"))
HANDS = tomllib.loads((BLENDER / "anim_sets" / "alien_hands.toml").read_text(encoding="utf-8"))
GRIPS = set(SPEC.get("grips", {})) | set(HANDS.get("grips", {}))
FITTED = json.loads((BLENDER / "fp_hands_fit.json").read_text(encoding="utf-8"))
POSES = {n: dict(p) for n, p in SPEC["poses"].items()}
for _n, _f in FITTED["poses"].items():
    POSES.setdefault(_n, {}).update(_f)
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
        for name, pose in POSES.items():
            for k in ("grip_R", "grip_L"):
                if k in pose:
                    self.assertIn(pose[k], GRIPS, f"pose {name} {k}")
            if "R_c" in pose:
                self.assertIn("L_c", pose, f"pose {name}: both hands on the crystal")
                for k in ("R_c", "L_c"):
                    self.assertLessEqual({"z", "toward", "r", "wrap"}, set(pose[k]), f"pose {name} {k}")
                    self.assertLessEqual(set(pose[k]), {"z", "toward", "r", "wrap", "bend"}, f"pose {name} {k}")
        for name, clip in SPEC["clips"].items():
            self.assertIn(clip["pose"], POSES, name)

    def test_fitted(self):
        view = SPEC["view"]
        self.assertEqual(set(view["targets"]), set(FITTED["poses"]), "every target frame has its fitted pose")
        bend = view["bend_max_deg"]
        for name, pose in FITTED["poses"].items():
            for k in ("R", "R_c", "L_c"):
                if k in pose:
                    self.assertIn("bend", pose[k], f"{name} {k}: a viewmodel pose sets its wrist's bend")
                    for b in pose[k]["bend"]:
                        self.assertLessEqual(abs(b), bend + 1e-6, f"{name} {k}: the wrist bent past {bend} degrees")

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
                for f in ("R", "crystal"):
                    v = k.get(f)
                    if isinstance(v, str):
                        self.assertIn(v, POSES, name)
                    elif isinstance(v, dict) and "mix" in v:
                        self.assertIn(v["mix"][0], POSES, name)
                        self.assertIn(v["mix"][1], POSES, name)

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
