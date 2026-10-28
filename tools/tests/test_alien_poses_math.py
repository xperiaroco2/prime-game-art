"""The photo poses' pure maths (art #196, tools/blender/alien_pose_math.py): the bone split, the IK middle joint, the
limb's shared hinge, the frames, the hull and its margin, layer clips and pairs; and, when the step's skin dump is on
this machine (the newest step's), on the chameleon: every leg pose's contacts on the floor, measure() on a starting
pair, the centre of mass check and the heart's meet (skipped without the raw files)."""
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
POSES = RAW / "research/2026-10-22-roster/design/pilot3d/anim_bare/poses"


def _newest_dump() -> Path:
    """The newest step's chameleon skin dump (s1, s2, ... by number): the tests follow the current skeleton."""
    steps = [d for d in POSES.glob("s*") if d.name[1:].isdigit() and (d / "chameleon_dump.json").is_file()]
    return max(steps, key=lambda d: int(d.name[1:])) / "chameleon_dump.json" if steps else POSES / "none"


DUMP = _newest_dump()


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


class CentreOfMass(unittest.TestCase):
    def test_volume_weighted_posed_centroids(self):
        class Fake:
            tubes = {"a": {"centroid_local": (0.0, 0.0, 0.0), "volume": 3.0},
                     "b": {"centroid_local": (1.0, 0.0, 0.0), "volume": 1.0}}
        P = {"a": _eye(), "b": _eye(z=2.0)}  # b's centroid lands at (1, 0, 2)
        c = A.centre_of_mass(Fake(), P)
        for got, want in zip(c, (0.25, 0.0, 0.5)):
            self.assertAlmostEqual(got, want)

    def test_inside_margin_signs(self):
        sq = A.hull([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        self.assertAlmostEqual(A.inside_margin(sq, (0.5, 0.5)), 0.5)
        self.assertLess(A.inside_margin(sq, (1.5, 0.5)), 0.0)


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


class Variants(unittest.TestCase):
    def test_arms_for_picks_the_per_legs_variant(self):
        arms = {"HandsOnHips": "shared", f"HandsOnHips{A.VARIANT}Sit": "sit"}
        self.assertEqual(A.arms_for(arms, "HandsOnHips", "Sit"), "sit")
        self.assertEqual(A.arms_for(arms, "HandsOnHips", "Stand"), "shared")


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

    def test_a_character_table_merges_over_the_shared_data(self):
        """Round 3: `[chars.<char>]` overrides a setting for that character only; the shared data stays."""
        d = {"arms": {"X": {"both": {"a": 1, "b": 2}}}, "limits": {"c": 3},
             "chars": {"axolotl": {"arms": {"X": {"both": {"b": 5}}}}}}
        self.assertEqual(A.for_char(d, "axolotl")["arms"]["X"]["both"], {"a": 1, "b": 5})
        self.assertEqual(A.for_char(d, "chameleon")["arms"]["X"]["both"], {"a": 1, "b": 2})
        self.assertEqual(A.for_char(d, "")["limits"], {"c": 3})
        self.assertEqual(d["arms"]["X"]["both"]["b"], 2)


@unittest.skipUnless(DUMP.is_file(), "no step's skin dump is on this machine")
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

    def test_measure_on_a_starting_pair(self):
        """Stand+HandsOnHips: on the floor, the centre of mass inside the feet, every through pair read, the hands'
        contacts and waist marks within the limits."""
        lim = self.model.data["limits"]
        r = A.compose(self.model.legs("Stand"), self.model.arms("HandsOnHips"))
        m = A.measure(self.model, r, "Stand", "HandsOnHips")
        self.assertLessEqual(abs(m["floor_cm"]), lim["floor_cm"])
        self.assertGreater(m["com_margin_cm"], lim["com_margin_cm"])
        self.assertEqual(set(m["through_cm"]), {f"{a}>{b}" for a, b in lim["through_pairs"]})
        self.assertEqual(set(m["marks_cm"]), {"hand_Left@waist_Left", "hand_Right@waist_Right"})
        for k, v in m["contacts_cm"].items():
            self.assertLessEqual(v, lim["contact_gap_cm"], k)
        own = {f"{c['a']}@{c['mark']}": c.get("mark_cm", lim["mark_cm"])
               for c in self.model.data["arms"]["HandsOnHips"]["contacts"] if c.get("mark")}
        for k, v in m["marks_cm"].items():  # p3: the fist's knuckles, the contact's own limit
            self.assertLessEqual(v, own[k], k)
        self.assertEqual(m["fails"], [])  # review 2: the through limits too (the fingertips were 1.9 cm in)

    def test_a_variant_has_its_own_mark_limit(self):
        """A per-legs variant's palm-to-waist distance fails beyond variant_mark_cm, not mark_cm."""
        d = self.model.data
        r = A.compose(self.model.legs("Stand"), self.model.arms("HandsOnHips"))
        old = dict(d["limits"])
        cs = d["arms"]["HandsOnHips"]["contacts"]
        d["arms"]["HandsOnHips"]["contacts"] = [{k: v for k, v in c.items() if k != "mark_cm"} for c in cs]
        try:
            d["limits"]["mark_cm"] = d["limits"]["variant_mark_cm"] = 0.1
            self.assertTrue(any(f.startswith("mark") for f in A.measure(self.model, r, "Stand", "HandsOnHips", True)["fails"]))
            d["limits"]["variant_mark_cm"] = 50.0
            self.assertFalse(any(f.startswith("mark") for f in A.measure(self.model, r, "Stand", "HandsOnHips", True)["fails"]))
            self.assertTrue(any(f.startswith("mark") for f in A.measure(self.model, r, "Stand", "HandsOnHips")["fails"]))
        finally:
            d["limits"].clear()
            d["limits"].update(old)
            d["arms"]["HandsOnHips"]["contacts"] = cs

    def test_the_fist_akimbo_stays_on_the_waist_over_raised_thighs(self):
        """p3: the akimbo fist (`per_legs`) has a variant on every legs pose but the reference; on Squat and Sit, where
        the thighs rise to the hips, both fists stay on the waist (its marks measured, no thigh contact), neither in a
        thigh nor in the torso, no failure. thigh_side is off everywhere (`[thigh_hand]` has no legs)."""
        mo = self.model
        legs = {lg: mo.legs(lg) for lg in mo.data["legs"]}
        arms = {"HandsOnHips": mo.arms("HandsOnHips")}
        arms.update(mo.variants(legs, arms))
        self.assertEqual({k for k in arms if A.VARIANT in k},
                         {f"HandsOnHips{A.VARIANT}{lg}" for lg in legs if lg != mo.data["reference_legs"]})
        lim = mo.data["limits"]
        for lg in ("Squat", "Sit"):
            m = A.measure(mo, A.compose(legs[lg], arms[f"HandsOnHips{A.VARIANT}{lg}"]), lg, "HandsOnHips", True)
            self.assertEqual(set(m["marks_cm"]), {f"hand_{s}@waist_{s}" for s in A.SIDES}, lg)
            self.assertFalse([k for k in m["contacts_cm"] if "thigh" in k], lg)
            self.assertEqual(m["fails"], [], lg)
            for s in A.SIDES:
                for b in ("torso", f"thigh_{s}"):
                    self.assertLessEqual(m["through_cm"][f"hand_{s}>{b}"], lim["through_hand_cm"], (lg, s, b))
        self.assertFalse(any(A.thigh_side(mo.data, lg, s) for lg in legs for s in A.SIDES))
        th = {"thigh_hand": {"legs": ["Kneel"], "sides": {"Kneel": ["Left"]}}}
        self.assertTrue(A.thigh_side(th, "Kneel", "Left"))
        self.assertFalse(A.thigh_side(th, "Kneel", "Right"))

    def test_the_hand_library_four_shapes_mirrored_thumbs_straight_fists(self):
        """p3: every arm takes one of the four hand shapes; the fist's thumb turn (ThumbTurn) mirrors on the right
        hand (the thumb tips mirror images on the rest skeleton within 1 mm); a `fingers_dir = "forearm"` hand (the
        Victory's and the akimbo's fists) keeps its wrist straight (within 1 degree)."""
        d = self.model.data
        self.assertEqual(set(d["grips"]), {"fist", "point", "flat", "heart", "behind"})  # q3: the behind-head hand
        for am, spec in d["arms"].items():
            for side in ("Left", "Right", "both"):
                if isinstance(spec.get(side), dict):
                    self.assertIn(spec[side].get("grip", "flat"), d["grips"], (am, side))
        r = A.Rig(self.model.skel)
        for side in A.SIDES:
            self.model._fingers(r, side, "fist")
        tl, tr = (A.S.pos(r.P()[f"{s}ThumbDistal"]) for s in A.SIDES)
        self.assertLess(A.length(A.sub(tl, (-tr[0], tr[1], tr[2]))), 0.001)
        for side in A.SIDES:  # q3: the flat hand's `spread` mirrors too (q2's drew one hand's fingers apart)
            self.model._fingers(r, side, "flat")
        for f in ("Index", "Little"):
            tl, tr = (A.S.pos(r.P()[f"{s}{f}Distal"]) for s in A.SIDES)
            self.assertLess(A.length(A.sub(tl, (-tr[0], tr[1], tr[2]))), 0.001, f)
        for am, legs in (("Victory", "Stand"), ("HandsOnHips", "Stand")):
            P = A.compose(self.model.legs(legs), self.model.arms(am)).P()
            for s in A.SIDES:
                fa = A.norm(A.sub(A.S.pos(P[f"{s}Hand"]), A.S.pos(P[f"{s}LowerArm"])))
                self.assertGreater(A.dot(fa, A.axis(P, f"{s}Hand", 1)), math.cos(math.radians(1.0)), (am, s))

    def test_a_hand_reads_through_only_where_the_skins_touch(self):
        """Round 3: HandsBehindHead's hands 0.8 cm off the skull: a tube depth there is the proxy's (proxy_cm), not a
        through reading; the contacts within the limit and no failure."""
        m = A.measure(self.model, A.compose(self.model.legs("Stand"), self.model.arms("HandsBehindHead")), "Stand",
                      "HandsBehindHead")
        for s in ("Left", "Right"):
            self.assertLessEqual(m["through_cm"][f"hand_{s}>head"], self.model.data["limits"]["through_hand_cm"])
            self.assertGreater(m["contacts_cm"][f"hand_{s}~head"], A.TOUCH_CM)
        self.assertEqual(m["fails"], [])

    def test_a_hand_pushed_into_the_head_fails(self):
        """Review 3: a hand 3 cm deeper into the skull than HandsBehindHead's solve fails, read as through (its skin
        then touches the head's) and, with the touch rule forced on every reading, as through with no touch
        (proxy_cm past `proxy_hand_cm`): the gap rule never hides a deep hand."""
        mo = self.model

        def pushed():
            r = A.compose(mo.legs("Stand"), mo.arms("HandsBehindHead"))
            hp, hd = S.pos(r.P()["LeftHand"]), S.pos(r.P()["Head"])
            d = A.norm(A.sub(hd, hp))
            r.set_world("LeftHand", r.world_q("LeftHand"), at=A.add(hp, A.mul(A.norm((d[0], d[1], 0.0)), 0.03)))
            return A.measure(mo, r, "Stand", "HandsBehindHead")

        m = pushed()
        self.assertGreater(m["through_cm"]["hand_Left>head"], mo.data["limits"]["through_hand_cm"])
        self.assertIn("through hand_Left>head", " ".join(m["fails"]))
        old = A.TOUCH_CM
        try:
            A.TOUCH_CM = -1.0  # every hand reading goes to proxy_cm, as a deep hand with no skin near b's would
            m = pushed()
        finally:
            A.TOUCH_CM = old
        self.assertEqual(m["through_cm"]["hand_Left>head"], 0.0)
        self.assertGreater(m["proxy_cm"]["hand_Left>head"], mo.data["limits"]["proxy_hand_cm"])
        self.assertIn("through (no touch) hand_Left>head", " ".join(m["fails"]))

    def test_one_leg_tips_out_of_balance_when_pushed(self):
        """The centre of mass check reads a body shifted off its one foot as outside the support."""
        legs = self.model.legs("OneLeg")
        ok = A.measure(self.model, legs, "OneLeg", "Plane")["com_margin_cm"]
        legs.turn_world("Spine", A.turn_q(pitch=50.0))  # the upper body leant far forward over a fixed foot
        self.assertLess(A.measure(self.model, legs, "OneLeg", "Plane")["com_margin_cm"], ok)

    def test_meet_brings_the_heart_fingertips_together(self):
        """_meet: the index tips' skin within the heart's gap (the solve's own contact)."""
        r = A.compose(self.model.legs("Stand"), self.model.arms("Heart"))
        pz = A.Posed(self.model.skel, self.model.skin, r.P())
        gap = A.nearest_gap(pz.group("LeftIndexDistal"), pz.group("RightIndexDistal"), reach=0.3) * 100
        self.assertLessEqual(gap, self.model.data["limits"]["contact_gap_cm"])

    def test_solve_is_repeatable(self):
        a = self.model.arms("HandsOnHips")
        b = self.model.arms("HandsOnHips")
        self.assertEqual(a.rot["LeftHand"], b.rot["LeftHand"])
        self.assertEqual(a.rot["LeftIndexProximal"], b.rot["LeftIndexProximal"])


if __name__ == "__main__":
    unittest.main()
