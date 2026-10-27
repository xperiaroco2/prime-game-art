"""The photo poses' pure maths (art #196, tools/blender/alien_pose_math.py): the bone split, the IK middle joint, the
limb's shared hinge, the frames, the hull and its margin, layer clips and pairs; and, when the step's skin dump is on
this machine, every leg pose's contacts on the floor on the chameleon (skipped without the raw files)."""
from __future__ import annotations

import json
import math
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_pose_math as A  # noqa: E402
import alien_stride_math as S  # noqa: E402

RAW = Path(os.environ.get("PRIME_ART_RAW", "D:/prime-art-raw"))
DUMP = RAW / "research/2026-10-22-roster/design/pilot3d/anim_bare/poses/s1/chameleon_dump.json"


def _eye(x=0.0, y=0.0, z=0.0):
    return [[1.0, 0.0, 0.0, x], [0.0, 1.0, 0.0, y], [0.0, 0.0, 1.0, z], [0.0, 0.0, 0.0, 1.0]]


def _leg_skel():
    """A hip, a knee and an ankle along -Z (bone y down: rest rotation x -> x, y -> -z, z -> y)."""
    def down(z):
        return [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, -1.0, 0.0, z], [0.0, 0.0, 0.0, 1.0]]
    return {"rest": {"Hips": _eye(z=1.0), "LeftUpperLeg": down(0.9), "LeftLowerLeg": down(0.5),
                     "LeftFoot": down(0.1)},
            "parent": {"Hips": None, "LeftUpperLeg": "Hips", "LeftLowerLeg": "LeftUpperLeg",
                       "LeftFoot": "LeftLowerLeg"}}


class Split(unittest.TestCase):
    def test_owner(self):
        for b in ("Root", "Hips", "Spine", "LeftUpperLeg", "RightToes", "LeftFoot"):
            self.assertEqual(A.owner(b), "legs", b)
        for b in ("Chest", "UpperChest", "Neck", "Head", "LeftShoulder", "RightIndexDistal", "Jaw", "Crest1"):
            self.assertEqual(A.owner(b), "arms", b)

    def test_groups(self):
        self.assertEqual(A.group_of("LeftIndexDistal"), "hand_Left")
        self.assertEqual(A.group_of("RightLowerArm"), "forearm_Right")
        self.assertEqual(A.group_of("LeftShoulder"), "upperarm_Left")
        self.assertEqual(A.group_of("LeftEye"), "head")
        self.assertEqual(A.group_of("Spine"), "torso")
        self.assertEqual(A.group_of("RightToes"), "foot_Right")


class Geometry(unittest.TestCase):
    def test_ik_mid_lengths_and_pole(self):
        root, goal = (0.0, 0.0, 1.0), (0.0, -0.3, 0.3)
        m = A.ik_mid(root, goal, 0.4, 0.4, (0.0, -1.0, 0.0))
        self.assertAlmostEqual(math.dist(root, m), 0.4, places=6)
        self.assertAlmostEqual(math.dist(m, goal), 0.4, places=6)
        mid = tuple((a + b) / 2 for a, b in zip(root, goal))
        self.assertLess(m[1], mid[1])  # on the pole's side (-Y)

    def test_ik_mid_out_of_reach_stays_straight(self):
        m = A.ik_mid((0, 0, 0), (0, 0, -2.0), 0.4, 0.4, (0, -1, 0))
        self.assertAlmostEqual(m[2], -0.4, places=3)

    def test_frame_q_maps_pair(self):
        q = A.frame_q((1, 0, 0), (0, 0, -1), (0, 0, 1), (0, 1, 0))
        for a, b in (((1, 0, 0), (0, 0, 1)), ((0, 0, -1), (0, 1, 0))):
            r = A.M.q_rotate(q, a)
            for x, y in zip(r, b):
                self.assertAlmostEqual(x, y, places=6)

    def test_turn_q_signs(self):
        up = (0.0, 0.0, 1.0)
        self.assertLess(A.M.q_rotate(A.turn_q(pitch=30), up)[1], 0)  # leans forward (-Y)
        self.assertGreater(A.M.q_rotate(A.turn_q(roll=30), up)[0], 0)  # toward the left (+X)
        self.assertLess(A.M.q_rotate(A.turn_q(roll=30, side="Right"), up)[0], 0)

    def test_body_axes(self):
        self.assertEqual(A.body("Left", (1, 1, 1)), (1.0, -1, 1))
        self.assertEqual(A.body("Right", (1, 1, 1)), (-1.0, -1, 1))

    def test_hull_and_margin(self):
        poly = A.hull([(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)])
        self.assertEqual(len(poly), 4)
        self.assertAlmostEqual(A.inside_margin(poly, (0.5, 0.5)), 0.5)
        self.assertAlmostEqual(A.inside_margin(poly, (1.5, 0.5)), -0.5)

    def test_nearest_gap(self):
        self.assertAlmostEqual(A.nearest_gap([(0, 0, 0)], [(0.03, 0.04, 0)], reach=0.1), 0.05)
        self.assertEqual(A.nearest_gap([(0, 0, 0)], [(1, 0, 0)], reach=0.1), 0.1)


class TubeVolumes(unittest.TestCase):
    """tube() and tube_depths() on known geometry: a cylinder of radius 0.1 m along a bone's y, 0.8 m long."""

    @classmethod
    def setUpClass(cls):
        pts = [(0.1 * math.cos(2 * math.pi * k / 48), 0.8 * (j + 0.5) / 40, 0.1 * math.sin(2 * math.pi * k / 48))
               for j in range(40) for k in range(48)]
        cls.skel = {"rest": {"Spine": _eye()}, "parent": {"Spine": None}}
        cls.t = A.tube(cls.skel, {"points": pts, "by_bone": {"Spine": list(range(len(pts)))}}, "Spine")

    def test_radius_is_the_surface(self):
        for row in self.t["radius"]:
            for r in row:
                self.assertAlmostEqual(r, 0.1, places=6)

    def test_depth_inside_outside_and_moved(self):
        P = {"Spine": _eye()}
        d = A.tube_depths(self.t, P, [(0.0, 0.4, 0.0), (0.06, 0.4, 0.0), (0.2, 0.4, 0.0), (0.0, -0.1, 0.0)])
        self.assertAlmostEqual(d[0], 0.1, places=6)
        self.assertAlmostEqual(d[1], 0.04, places=6)
        self.assertEqual(d[2:], [0.0, 0.0])
        self.assertAlmostEqual(A.tube_depth(self.t, {"Spine": _eye(x=0.05)}, [(0.0, 0.4, 0.0)]), 0.05, places=6)
        self.assertEqual(A.tube_depth(self.t, P, [(0.0, 0.05, 0.0)], first=3), 0.0)  # slice 0 skipped


class RigAndLayers(unittest.TestCase):
    def test_limb_shares_a_hinge_and_reaches(self):
        r = A.Rig(_leg_skel())
        hip = r.head("LeftUpperLeg")
        goal = (0.0, -0.3, 0.3)
        knee = A.ik_mid(hip, goal, 0.4, 0.4, (0.0, -1.0, 0.0))
        r.limb("LeftUpperLeg", "LeftLowerLeg", A.sub(knee, hip), A.sub(goal, knee))
        P = r.P()
        self.assertLess(math.dist(S.pos(P["LeftFoot"]), goal), 1e-6)
        self.assertAlmostEqual(A.dot(A.axis(P, "LeftUpperLeg", 0), A.axis(P, "LeftLowerLeg", 0)), 1.0, places=6)
        self.assertGreater(A.axis(P, "LeftUpperLeg", 0)[0], 0.99)  # the knee's hinge stays left-right: no sideways bend

    def test_set_world_round_trip(self):
        r = A.Rig(_leg_skel())
        q = A.turn_q(pitch=20, yaw=10)
        r.set_world("LeftLowerLeg", A.M.q_mul(q, r.rest_q("LeftLowerLeg")))
        got = r.world_q("LeftLowerLeg")
        want = A.M.q_mul(q, r.rest_q("LeftLowerLeg"))
        self.assertGreater(abs(sum(a * b for a, b in zip(got, want))), 1 - 1e-9)

    def test_palm_centre_and_a_landmark_riding_on_the_spine(self):
        P = {"LeftHand": _eye(0.2, 0.0, 1.0), "LeftMiddleProximal": _eye(0.2, -0.1, 0.9)}
        self.assertEqual(A.palm_centre(P, "Left"), (0.2, -0.05, 0.95))
        from types import SimpleNamespace
        model = SimpleNamespace(skel={"rest": {"Spine": _eye(z=1.0)}}, marks={"waist_Left": (0.15, 0.0, 1.0)})
        q = A.turn_q(yaw=90)  # the Spine turned a quarter about up, and lifted 0.1
        m = A.M.mat_mul(_eye(z=1.1), [list(r) + [0.0] for r in A.rot3(q)] + [[0.0, 0.0, 0.0, 1.0]])
        got = A.mark_posed(model, {"Spine": m}, "waist_Left")
        want = A.add((0.0, 0.0, 1.1), A.M.q_rotate(q, (0.15, 0.0, 0.0)))
        self.assertLess(math.dist(got, want), 1e-9)

    def test_compose_takes_each_layer_bones_only(self):
        skel = _leg_skel()
        skel["rest"]["Chest"] = _eye(z=1.2)
        skel["parent"]["Chest"] = "Hips"
        legs, arms = A.Rig(skel), A.Rig(skel)
        legs.rot["LeftUpperLeg"] = legs.rot["Chest"] = A.turn_q(pitch=10)
        arms.rot["Chest"] = arms.rot["LeftUpperLeg"] = A.turn_q(roll=10)
        pair = A.compose(legs, arms)
        self.assertEqual(pair.rot["LeftUpperLeg"], legs.rot["LeftUpperLeg"])
        self.assertEqual(pair.rot["Chest"], arms.rot["Chest"])
        clip = A.layer_clip(pair, "arms", "PoseArms_X_Loop", frames=3)
        self.assertEqual(sorted(clip["rot"]), ["Chest"])
        self.assertEqual(len(set(clip["rot"]["Chest"])), 1)  # held: identical keys
        self.assertEqual(S.frames(clip), 2)


class Silhouettes(unittest.TestCase):
    def test_mask_diff_and_flip(self):
        a = [0b1100, 0b1100]
        self.assertEqual(A.mask_diff(a, a), 0.0)
        self.assertEqual(A.mask_diff(a, [0b0011, 0b0011]), 1.0)
        self.assertAlmostEqual(A.mask_diff(a, [0b1000, 0b1000]), 0.5)
        self.assertEqual(A.hflip([0b1100, 0b0001], 4), [0b0011, 0b1000])
        self.assertEqual(A.mask_diff([0], [0]), 0.0)

    def test_table_finds_the_least_distinct_parts(self):
        # legs L1, L2 differ in one pixel of four; arms A1, A2 differ fully; L1's right view is A's left mirrored
        m = {}
        for lg, base in (("L1", 0b1111), ("L2", 0b1110)):
            for am, top in (("A1", 0b1000), ("A2", 0b0001)):
                for face in A.FACINGS:
                    m[(lg, am, face)] = [top, base]
        m[("L1", "A1", "right")] = A.hflip(m[("L1", "A1", "left")], 4)
        t = A.silhouette_table(m, ["L1", "L2"], ["A1", "A2"], 4, lopsided=("A1",))
        self.assertEqual(t["legs"]["front"][0]["a"], "L1")
        self.assertAlmostEqual(t["legs"]["front"][0]["min"], 0.2)
        self.assertGreater(t["arms"]["front"][0]["min"], 0.3)
        self.assertEqual(t["lr"]["L1+A1"]["diff"], 0.0)
        self.assertTrue(t["lr"]["L1+A1"]["lopsided"])
        self.assertGreater(t["lr"]["L2+A2"]["diff"], 0.0)


class GlbClips(unittest.TestCase):
    def _glb(self, path, values):
        import struct
        times = struct.pack("<2f", 0.0, 1.0)
        vals = struct.pack("<8f", *values)
        bn = times + vals
        js = {"asset": {"version": "2.0"}, "nodes": [{"name": "Hips"}], "buffers": [{"byteLength": len(bn)}],
              "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 8},
                              {"buffer": 0, "byteOffset": 8, "byteLength": 32}],
              "accessors": [{"bufferView": 0, "componentType": 5126, "count": 2, "type": "SCALAR"},
                            {"bufferView": 1, "componentType": 5126, "count": 2, "type": "VEC4"}],
              "animations": [{"name": "Idle", "samplers": [{"input": 0, "output": 1}],
                              "channels": [{"sampler": 0, "target": {"node": 0, "path": "rotation"}}]}]}
        j = json.dumps(js).encode()
        j += b" " * (-len(j) % 4)
        body = struct.pack("<I4s", len(j), b"JSON") + j + struct.pack("<I4s", len(bn), b"BIN\0") + bn
        Path(path).write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)

    def test_same_keys_same_hash_and_a_change_shows(self):
        import tempfile
        import alien_poses as AP
        with tempfile.TemporaryDirectory() as d:
            self._glb(Path(d) / "a.glb", [0, 0, 0, 1, 0, 0, 0, 1])
            self._glb(Path(d) / "b.glb", [0, 0, 0, 1, 0, 0, 0, 1])
            self._glb(Path(d) / "c.glb", [0, 0, 0, 1, 0, 0, 0.1, 1])
            a, b, c = (AP.glb_clips(Path(d) / f"{k}.glb") for k in "abc")
        self.assertEqual(a, b)
        self.assertNotEqual(a["Idle"], c["Idle"])


class BuiltData(unittest.TestCase):
    def test_the_check_composes_from_the_builds_own_data(self):
        """verify went red when the TOML changed after the newest build: the reference follows the build's data."""
        import tempfile
        import alien_poses_run as PR
        cfg = A.load()
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(PR.built_data(Path(d), cfg), (cfg, ""))  # an older build: the TOML's
            old = json.loads(json.dumps(cfg))
            old["arms"]["Heart"]["both"]["offset"] = [0.4, 1.9, 0.9]
            (Path(d) / "pose_data.json").write_text(json.dumps(old), encoding="utf-8")
            built, stale = PR.built_data(Path(d), cfg)
        self.assertEqual(built["arms"]["Heart"]["both"]["offset"], [0.4, 1.9, 0.9])
        self.assertEqual(stale, "arms")


@unittest.skipUnless(DUMP.is_file(), "the s1 skin dump is not on this machine")
class OnTheChameleon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dump = json.loads(DUMP.read_text(encoding="utf-8"))
        cls.model = A.Model(dump["skel"], dump["skin"], A.load())

    def test_every_leg_pose_touches_the_floor(self):
        lim = self.model.data["limits"]["floor_cm"]
        for name in self.model.data["legs"]:
            r = self.model.legs(name)
            pz = A.Posed(self.model.skel, self.model.skin, r.P())
            low = pz.lowest(list(self.model.skin["by_group"]))
            self.assertLessEqual(abs(low * 100), lim, name)

    def test_solve_is_repeatable(self):
        a = self.model.arms("HandsOnHips")
        b = self.model.arms("HandsOnHips")
        self.assertEqual(a.rot["LeftHand"], b.rot["LeftHand"])
        self.assertEqual(a.rot["LeftIndexProximal"], b.rot["LeftIndexProximal"])


if __name__ == "__main__":
    unittest.main()
