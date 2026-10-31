"""The alien's loco hand shapes (art #196, Hands H1; tools/blender/alien_hands_math.py, no bpy): the hands file and
its checks, the clip plans, the keys, the grips shared with the photo poses (alien_pose_math.grip_quats, the poses'
`_fingers` unchanged), and the finger collision measure on a small synthetic hand."""
from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_hands_math as H  # noqa: E402
import alien_pose_math as A  # noqa: E402
import anim_edit_math as M  # noqa: E402


def _cfg(text: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "hands.toml"
        p.write_text(text, encoding="utf-8")
        return H.load(p, poses=H.HERE / "anim_sets" / "alien_poses.toml")


class File(unittest.TestCase):
    def setUp(self):
        self.cfg = H.load()

    def test_grips_reuse_the_poses(self):
        for g in ("fist", "point", "flat", "heart", "relaxed", "loose"):
            self.assertIn(g, self.cfg["grips"])
        self.assertEqual(self.cfg["own"], ["loose", "relaxed"])
        self.assertEqual(self.cfg["set"]["default"], "relaxed")

    def test_plans_per_clip(self):
        def grips(action):
            pat, plan = H.clip_plan(self.cfg, action)
            return [g for _, g in plan["Left"]], [g for _, g in plan["Right"]]
        self.assertEqual(grips("CharacterArmature|Idle_Loop"), (["relaxed"], ["relaxed"]))
        self.assertEqual(grips("CharacterArmature|Walk_Loop"), (["relaxed"], ["relaxed"]))
        self.assertEqual(grips("CharacterArmature|Talk_Upper_Loop"), (["relaxed"], ["relaxed"]))
        self.assertEqual(grips("CharacterArmature|Crouch_Fwd_Loop"), (["relaxed"], ["relaxed"]))
        self.assertEqual(grips("CharacterArmature|Jog_Fwd_Loop"), (["loose"], ["loose"]))
        self.assertEqual(grips("CharacterArmature|Sprint_Fwd__s80_Loop"), (["loose"], ["loose"]))
        self.assertEqual(grips("CharacterArmature|Jump_Air_Loop")[0], ["flat"])
        self.assertEqual(grips("CharacterArmature|Jump_Start")[0], ["relaxed", "relaxed", "flat"])
        self.assertIsNone(H.clip_plan(self.cfg, "CharacterArmature|PoseArms_Heart_Loop"))
        self.assertIsNone(H.clip_plan(self.cfg, "CharacterArmature|PoseLegs_Sit_Loop"))

    def test_game_name(self):
        self.assertEqual(H.game_name("CharacterArmature|Jog_Fwd_Loop"), "Jog_Fwd")
        self.assertEqual(H.game_name("Jump_Start"), "Jump_Start")


class Checks(unittest.TestCase):
    def test_unknown_keys_and_grips(self):
        with self.assertRaises(H.HandsError):
            _cfg('[grips.relaxed]\nall = [1, 2, 3]\ncurl = 3\n')
        with self.assertRaises(H.HandsError):
            _cfg('[grips.relaxed]\nall = [1, 2]\n')
        with self.assertRaises(H.HandsError):
            _cfg('[grips.relaxed]\nall = [1, 2, 3]\n[clips.Idle]\ngrip = "nope"\n')
        with self.assertRaises(H.HandsError):
            _cfg('[grips.relaxed]\nall = [1, 2, 3]\n[clips.Idle]\nhand = "relaxed"\n')
        with self.assertRaises(H.HandsError):
            _cfg('[set]\nmode = 1\n[grips.relaxed]\nall = [1, 2, 3]\n')
        with self.assertRaises(H.HandsError):  # a poses grip is reused, never redefined
            _cfg('[grips.relaxed]\nall = [1, 2, 3]\n[grips.fist]\nall = [1, 2, 3]\n')

    def test_keys(self):
        with self.assertRaises(H.HandsError):
            _cfg('[grips.relaxed]\nall = [1, 2, 3]\n[clips.Idle]\ngrip = "relaxed"\nkeys = [[0, "relaxed"]]\n')
        with self.assertRaises(H.HandsError):  # shares rise within 0..1
            _cfg('[grips.relaxed]\nall = [1, 2, 3]\n[clips.Idle]\nkeys = [[0.5, "relaxed"], [0.2, "fist"]]\n')
        cfg = _cfg('[grips.relaxed]\nall = [1, 2, 3]\n[clips.Idle]\nkeys = [[0, "relaxed", "fist"]]\n')
        plan = H.clip_plan(cfg, "Idle")[1]
        self.assertEqual(plan["Left"], [(0.0, "relaxed")])
        self.assertEqual(plan["Right"], [(0.0, "fist")])

    def test_left_right(self):
        cfg = _cfg('[grips.relaxed]\nall = [1, 2, 3]\n[clips.Idle]\nLeft = "fist"\nRight = "relaxed"\n')
        plan = H.clip_plan(cfg, "Idle")[1]
        self.assertEqual((plan["Left"][0][1], plan["Right"][0][1]), ("fist", "relaxed"))


class Keys(unittest.TestCase):
    def test_keyed_frames_and_hold(self):
        cfg = H.load()
        rows = [(0.0, "relaxed"), (0.6, "relaxed"), (1.0, "flat")]
        k = H.keyed(cfg, rows, "Left", (1, 21))
        self.assertEqual([f for f, _ in k["LeftIndexProximal"]], [1, 13, 21])
        held = H.keyed(cfg, [(0.0, "relaxed")], "Right", (0, 30))
        self.assertEqual([f for f, _ in held["RightRingDistal"]], [0, 30])
        self.assertEqual(held["RightRingDistal"][0][1], held["RightRingDistal"][1][1])

    def test_every_finger_bone_keyed(self):
        cfg = H.load()
        k = H.keyed(cfg, [(0.0, "relaxed")], "Left", (0, 10))
        self.assertEqual(len(k), 15)  # five chains of three: no mocap left on any finger, the Little's too
        self.assertIn("LeftLittleDistal", k)
        self.assertAlmostEqual(H.angle_deg(k["LeftLittleDistal"][0][1]), 18.0, places=4)  # H1b: the Little as the Ring
        rel = H.grip_pose(cfg, "relaxed", "Left")
        self.assertAlmostEqual(H.angle_deg(rel["LeftMiddleIntermediate"]), 24.0, places=4)


class SharedWithPoses(unittest.TestCase):
    def test_grip_quats_mirror(self):
        g = H.load()["grips"]["relaxed"]
        L, R = A.grip_quats(g, "Left"), A.grip_quats(g, "Right")
        for f in ("Index", "Ring"):  # the spread mirrored: one sign means together on both hands
            ql, qr = L[f"Left{f}Proximal"], R[f"Right{f}Proximal"]
            self.assertAlmostEqual(ql[0], qr[0], places=9)
            self.assertAlmostEqual(ql[1], qr[1], places=9)
            self.assertAlmostEqual(ql[3], -qr[3], places=9)

    def test_fist_unchanged(self):
        """The poses' fist through grip_quats is the curl and the thumb turn p3 composed in `_fingers`."""
        g = A.load_data()["grips"]["fist"] if hasattr(A, "load_data") else H.load()["grips"]["fist"]
        q = A.grip_quats(g, "Left")
        want = M.q_mul(M.q_axis_angle((0.0, 0.0, 1.0), 60.0), M.q_mul(M.q_axis_angle((0.0, 1.0, 0.0), 30.0),
                                                                     M.q_axis_angle((1.0, 0.0, 0.0), 40.0)))
        for a, b in zip(q["LeftThumbMetacarpal"], M.q_norm(want)):
            self.assertAlmostEqual(a, b, places=9)
        self.assertAlmostEqual(H.angle_deg(q["LeftIndexProximal"]), 100.0, places=6)


def _hand():
    """A synthetic left hand along +X: a palm bone and two fingers of three bones, each skin a ring of points."""
    def rest(x, y, z):  # bone y along +X: x -> -y? keep it simple: rows of a rotation taking local y to world x
        return [[0.0, 1.0, 0.0, x], [-1.0, 0.0, 0.0, y], [0.0, 0.0, 1.0, z], [0.0, 0.0, 0.0, 1.0]]
    bones = {"LeftHand": (rest(0.0, 0.0, 0.0), None)}
    for f, y in (("Index", -0.02), ("Middle", 0.02)):
        prev = "LeftHand"
        for i, s in enumerate(("Proximal", "Intermediate", "Distal")):
            bones[f"Left{f}{s}"] = (rest(0.08 + 0.03 * i, y, 0.0), prev)
            prev = f"Left{f}{s}"
    skel = {"rest": {b: r for b, (r, _) in bones.items()}, "parent": {b: p for b, (_, p) in bones.items()}}
    names = list(bones)
    pts, ws, dom = [], [], []
    for b, (r, _) in bones.items():
        x0, y0 = r[0][3], r[1][3]
        length, rad = (0.08, 0.03) if b == "LeftHand" else (0.03, 0.009)
        for k in range(10):
            for a in range(12):
                t = 2 * math.pi * a / 12
                pts.append((x0 + length * (k + 0.5) / 10, y0 + rad * math.cos(t), rad * math.sin(t)))
                ws.append([(names.index(b), 1.0)])
                dom.append(names.index(b))
    return skel, {"bones": names, "points": pts, "weights": ws, "dom": dom}


class Collisions(unittest.TestCase):
    def test_rest_clear_and_a_crossing_finger(self):
        skel, skin = _hand()
        cfg = {"grips": {"cross": {"Index": [0, 0, 0], "Middle": [0, 0, 0]}, "flat": {"all": [0, 0, 0]}}}
        rest = H.collisions(skel, skin, cfg, "", "Left")
        self.assertEqual(rest["into_finger_cm"]["Index"], 0.0)
        self.assertGreater(rest["gap_cm"]["Index-Middle"], 1.5)  # 4 cm apart, 0.9 cm radii: 2.2 cm
        # the index's base turned 40 degrees about z toward the middle finger (either way: the sign is the rest's)
        deep = 0.0
        for sign in (-1.0, 1.0):
            r = A.Rig(skel)
            r.local("LeftIndexProximal", M.q_axis_angle((0.0, 0.0, 1.0), 40.0 * sign))
            posed = A.Posed(skel, A.prepare_skin(skin), r.P())
            pts = posed.groups(["LeftIndexIntermediate", "LeftIndexDistal"])
            for b in ("LeftMiddleProximal", "LeftMiddleIntermediate", "LeftMiddleDistal"):
                deep = max(deep, A.tube_depth(A.tube(skel, A.prepare_skin(skin), b), r.P(), pts))
        self.assertGreater(deep, 0.0)
        self.assertEqual(H.excess({"into_finger_cm": {"Index": 1.0}, "into_palm_cm": {}, "self_cm": {}},
                                  {"into_finger_cm": {"Index": 0.25}, "into_palm_cm": {}, "self_cm": {}}), 0.75)


if __name__ == "__main__":
    unittest.main()
