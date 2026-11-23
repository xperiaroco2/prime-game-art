"""The first-person hands' clip spec (art#136, prime-game#1587; tools/blender/fp_hands.toml, docs/animations.md "The
first-person hands"): every clip names a pose that exists, every grip it names exists (this file's [grips] or
alien_hands.toml's), every key's fields are known with its times rising from 0 to the clip's end, the hits last at
most 0.5 s (GDD "Melee: any item hits": one swing each 0.5 s) with the contact inside, the loops are named _Loop and
have no keys, and the reel of fp_hands_run.py plays only clips that exist. Since the viewmodel rebuild (the
engineer's direction of 2026-11-11): every key pose has a target frame, its fitted values (fp_hands_fit.json) bend no
wrist past [view] bend_max_deg, and every mix in a key names poses that exist. Since 2026-11-19 a crystal pose set from
the eye (the crystal hit's, Gate R's card) has its cap in the frame and only the known fields, and Crystal_Hit's
contact key is such a pose (its target frame was lost with D:). Pure Python, no Blender."""

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
                    self.assertLessEqual(set(pose[k]), {"z", "toward", "r", "wrap", "bend", "seat", "roll", "roll_span",
                                                        "thumb_front"}, f"pose {name} {k}")
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

    def test_crystal_from_eye(self):
        seen = 0
        for name, pose in POSES.items():
            c = pose.get("crystal")
            if not isinstance(c, dict) or "cap" not in c:
                continue
            seen += 1
            self.assertLessEqual({"cap", "dist", "tilt"}, set(c), name)
            self.assertLessEqual(set(c), {"cap", "dist", "tilt", "lean", "yaw"}, name)
            self.assertTrue(all(0.0 <= x <= 100.0 for x in c["cap"]), f"{name}: the cap in the frame")
            self.assertTrue(0.2 <= c["dist"] <= 0.8, f"{name}: the cap's distance from the eye")
        self.assertGreaterEqual(seen, 2, "the crystal hit's windup and contact are set from the eye")
        hit = {k["t"]: k for k in SPEC["clips"]["Crystal_Hit"]["keys"]}
        contact = hit[SPEC["clips"]["Crystal_Hit"]["hit"]].get("crystal")
        self.assertIn("cap", POSES[contact]["crystal"], "the contact key is a pose from the eye")
        self.assertNotIn("crystal_hit", SPEC["view"]["targets"], "the lost AI frame is no target")

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


    def test_rest_grid_frame(self):
        """fp_hands_run.rest_R (art#136 q2's rest grid): a place in the frame gives the wrist where the hands'
        camera draws it, the fingers and the back's normal unit and square, the back toward the eye untipped, and
        `tip` takes the fingers away from the eye."""
        import importlib.util
        import math
        spec = importlib.util.spec_from_file_location("fp_hands_run", BLENDER / "fp_hands_run.py")
        run = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run)
        fov = float(SPEC["view"]["fov_deg"])
        th = math.tan(math.radians(fov) / 2.0)
        for cell in ({"place": [53, 99, 0.5], "angle": 135}, {"place": [79, 99, 0.45], "angle": 125, "tip": 30,
                                                             "roll": 20, "lean": 5}):
            R = run.rest_R(cell, fov)
            p, f, n = R["p"], R["f"], R["n"]
            self.assertAlmostEqual(50 + 50 * p[0] / (p[1] * th * 16 / 9), cell["place"][0], delta=0.1)
            self.assertAlmostEqual(50 - 50 * p[2] / (p[1] * th), cell["place"][1], delta=0.1)
            self.assertAlmostEqual(math.hypot(*f), 1.0, delta=1e-3)
            self.assertAlmostEqual(math.hypot(*n), 1.0, delta=1e-3)
            self.assertAlmostEqual(sum(a * b for a, b in zip(f, n)), 0.0, delta=1e-3)
        flat = run.rest_R({"place": [53, 99, 0.5], "angle": 135}, fov)
        self.assertLess(sum(a * b for a, b in zip(flat["n"], flat["p"])), 0.0)   # the back faces the eye
        tipped = run.rest_R({"place": [53, 99, 0.5], "angle": 135, "tip": 30}, fov)
        self.assertGreater(tipped["f"][1], flat["f"][1] + 0.3)

    def test_grips_human(self):
        """Every grip of fp_hands.toml stays inside a human hand's joints (fp_hands_run.GRIP_LIMITS, art#136
        2026-11-20), and the limits refuse f2's twisted rest: spread 50 and the thumb bent back."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("fp_hands_run", BLENDER / "fp_hands_run.py")
        run = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run)
        self.assertEqual(run.grips_errors(SPEC), [])
        f2 = {"Index": [6, 10, 8], "spread": 50, "Thumb": [20, 5, 10], "ThumbTurn": [30, -30]}
        errors = run.grip_errors("f2", f2)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("spread" in e for e in errors) and any("swing" in e for e in errors), errors)
        over = {"grips": {"rest": {"spread": 50}}}
        self.assertEqual(len(run.grips_errors(SPEC, over)), 1)

    def test_mug(self):
        """The M8 beer mug (art#392): the mug clips hold the committed mug by its Grip, the mug pose is placed from
        the eye with the left fist as at rest, the clips sway about the idle's pivot (the left as Idle's), the search
        ranges rise, and the mug GLB has the contract's nodes."""
        mug, pose = SPEC["mug"], POSES["mug"]
        self.assertEqual(mug["bone"], "RightHand")
        self.assertGreater(mug["scale"], 0.0)
        self.assertLessEqual({"grip", "out"}, set(pose["mug"]))
        self.assertLessEqual({"t", "around"}, set(pose["hand"]))
        self.assertEqual(pose["L"], POSES["idle"]["L"], "the left fist as at rest")
        self.assertEqual((pose["grip_L"], pose["fist_L"]), (POSES["idle"]["grip_L"], POSES["idle"]["fist_L"]))
        for axis in ("x", "y", "z"):
            lo, hi, step = SPEC["mug"]["fit"][axis]
            self.assertTrue(lo < hi and step > 0, axis)
        mugs = {n: c for n, c in SPEC["clips"].items() if c["pose"] == "mug"}
        self.assertEqual(set(mugs), {"Mug_Idle_Loop", "Mug_Run_Loop"})
        for name, twin in (("Mug_Idle_Loop", "Idle_Loop"), ("Mug_Run_Loop", "Run_Loop")):
            c, t = mugs[name], SPEC["clips"][twin]
            self.assertEqual(c["pivot"], "idle", name)
            self.assertEqual(c["seconds"], t["seconds"], name)
            self.assertEqual((c.get("sway"), c.get("run")), (t.get("sway"), t.get("run")), name)
        glb = common.ROOT / mug["glb"]
        data = glb.read_bytes()
        n = int.from_bytes(data[12:16], "little")
        nodes = {x["name"]: x for x in json.loads(data[20:20 + n])["nodes"]}
        self.assertEqual(set(nodes), {"Mug", "Beer", "Grip"})
        grip = nodes["Grip"]
        self.assertEqual([round(v, 3) for v in grip["translation"]], [0.074, 0.08, 0.0])
        x, y, z, w = grip["rotation"]   # +90 degrees about +Y: the Grip's -Z along the mug's -X (toward its axis)
        self.assertAlmostEqual(abs(y), abs(w), places=4)
        self.assertAlmostEqual(y * w * 2.0, 1.0, places=4)
        self.assertEqual((round(x, 6), round(z, 6)), (0.0, 0.0))

    def test_the_committed_hands_carry_the_mug(self):
        """fp_hands.glb itself: the mug's socket and clips beside every clip and socket the engineer approved (g5)."""
        glb = common.ROOT / "assets" / "body" / "fp_hands" / "export" / "fp_hands.glb"
        data = glb.read_bytes()
        if data[:4] != b"glTF":
            self.skipTest("fp_hands.glb is an LFS pointer here")
        n = int.from_bytes(data[12:16], "little")
        doc = json.loads(data[20:20 + n])
        self.assertEqual({a["name"] for a in doc["animations"]},
                         {"Idle_Loop", "Run_Loop", "Punch", "Crystal_Idle_Loop", "Crystal_Run_Loop", "Crystal_Hit",
                          "Mug_Idle_Loop", "Mug_Run_Loop"})
        self.assertLessEqual({"CrystalSocket", "MugSocket"}, {x.get("name") for x in doc["nodes"]})


if __name__ == "__main__":
    unittest.main()
