"""The strafe pilot's orientation warp (tools/blender/alien_stride_math.orient_warp, art #196): the hips turned toward
the travel, the chain above them twisted back so the head stays on the aim, the feet re-planted along the asked
travel; on test_alien_stride_math's synthetic gait with a full spine chain (Spine, Chest, UpperChest, Neck, Head),
no Blender."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_alien_stride_math import ID, M, S, gait, same_rot  # noqa: E402


def skeleton() -> dict:
    rest, parent = {}, {}

    def add(name, head, par, q=ID):
        rest[name] = S.m4(head, q)
        parent[name] = par
    add("Root", (0.0, 0.0, 0.0), None)
    add("Hips", (0.0, 0.0, 0.9), "Root")
    add("Spine", (0.0, 0.0, 1.0), "Hips")
    add("Chest", (0.0, 0.0, 1.15), "Spine")
    add("UpperChest", (0.0, 0.0, 1.3), "Chest")
    add("Neck", (0.0, 0.0, 1.5), "UpperChest")
    add("Head", (0.0, 0.0, 1.6), "Neck")
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        add(f"{side}UpperLeg", (0.1 * sx, 0.0, 0.9), "Hips")
        add(f"{side}LowerLeg", (0.1 * sx, 0.0, 0.5), f"{side}UpperLeg")
        add(f"{side}Foot", (0.1 * sx, 0.0, 0.1), f"{side}LowerLeg")
        add(f"{side}Toes", (0.1 * sx, -0.12, 0.02), f"{side}Foot")
        roll = M.q_axis_angle((0.0, 0.0, 1.0), -90.0 * sx)
        add(f"{side}UpperArm", (0.2 * sx, 0.0, 1.4), "UpperChest", roll)
        add(f"{side}LowerArm", (0.45 * sx, 0.0, 1.4), f"{side}UpperArm", roll)
        add(f"{side}Hand", (0.7 * sx, 0.0, 1.4), f"{side}LowerArm", roll)
    return S.prepare({"rest": rest, "parent": parent})


def full(skel, clip):
    """Every bone keyed (the gait leaves the spine chain unkeyed; orient_warp writes their rotations)."""
    T = S.frames(clip)
    out = S.copy_clip(clip)
    for b in skel["order"]:
        out["loc"].setdefault(b, [(0.0, 0.0, 0.0)] * (T + 1))
        out["rot"].setdefault(b, [ID] * (T + 1))
    return out


def ground_heading(skel, clip) -> float:
    g = S.measure(skel, clip)["ground_m_s"]
    return S.heading_deg((-g[0], -g[1]))  # the body travels against the ground under its planted feet


class OrientWarp(unittest.TestCase):
    def setUp(self):
        self.skel = skeleton()
        self.clip = full(self.skel, gait(self.skel))
        self.T = S.frames(self.clip)

    def test_zero_yaw_is_the_identity(self):
        out, rep = S.orient_warp(self.skel, self.clip, 0.0, 0.0)
        for f in range(self.T + 1):
            a, b = S.fk(self.skel, self.clip, f), S.fk(self.skel, out, f)
            for bone in self.skel["order"]:
                self.assertLess(math.dist(S.pos(a[bone]), S.pos(b[bone])), 1e-6, (f, bone))
                self.assertLess(same_rot(S.mat_q(a[bone]), S.mat_q(b[bone])), 1e-3, (f, bone))
        self.assertLess(rep["ankle_miss_mm"], 1e-3)

    def test_the_hips_turn_by_the_asked_yaw_and_the_head_stays_on_the_aim(self):
        for yaw, travel in ((45.0, 90.0), (60.0, 90.0), (75.0, 90.0), (-60.0, -90.0), (60.0, 0.0)):
            out, rep = S.orient_warp(self.skel, self.clip, yaw, travel)
            for f in range(self.T + 1):
                d_hips = S._wrap(S.hips_facing_deg(self.skel, out, f) - S.hips_facing_deg(self.skel, self.clip, f))
                d_head = S._wrap(S.bone_heading_deg(self.skel, out, f, "Head")
                                 - S.bone_heading_deg(self.skel, self.clip, f, "Head"))
                self.assertAlmostEqual(d_hips, yaw, delta=0.1, msg=(yaw, f))
                self.assertLess(abs(d_head), 1.0, (yaw, f))
            self.assertAlmostEqual(rep["hips_turn_deg"], yaw, delta=0.1)
            self.assertLess(abs(rep["head_turn_deg"]), 1.0)

    def test_the_split_spreads_the_twist_up_the_chain(self):
        out, _ = S.orient_warp(self.skel, self.clip, 60.0, 90.0)
        want = {"Spine": 48.0, "Chest": 33.0, "UpperChest": 15.0, "Neck": 0.0}
        for bone, deg in want.items():
            got = S._wrap(S.bone_heading_deg(self.skel, out, 3, bone)
                          - S.bone_heading_deg(self.skel, self.clip, 3, bone))
            self.assertAlmostEqual(got, deg, delta=0.2, msg=bone)
        half, rep = S.orient_warp(self.skel, self.clip, 60.0, 90.0, split=(("Spine", 0.25), ("Chest", 0.25)))
        self.assertAlmostEqual(rep["head_turn_deg"], 30.0, delta=0.2)  # half the twist back: the head turned 30

    def test_the_feet_travel_along_the_asked_direction(self):
        base = ground_heading(self.skel, self.clip)
        for yaw, travel in ((60.0, 90.0), (45.0, -90.0), (0.0, 30.0)):
            out, rep = S.orient_warp(self.skel, self.clip, yaw, travel)
            self.assertAlmostEqual(S._wrap(ground_heading(self.skel, out) - base), travel, delta=1.0, msg=(yaw, travel))
            self.assertLess(rep["ankle_miss_mm"], 1.0)
            # the ankles are the clip's own turned by travel_deg about the vertical, plus one constant per foot
            q = M.q_axis_angle(S.UP, travel)
            for side in S.SIDES:
                ft = f"{side}Foot"
                a, b = S.tracks(self.skel, self.clip, [ft])[ft], S.tracks(self.skel, out, [ft])[ft]
                d = [M._v_sub(r, M.q_rotate(q, p)) for p, r in zip(a, b)]
                for x in d:
                    self.assertLess(math.dist(x, d[0]), 1e-3, (yaw, travel, side))
                self.assertLess(abs(d[0][2]), 1e-6)

    def test_the_planted_feet_stay_planted(self):
        out, _ = S.orient_warp(self.skel, self.clip, 60.0, 90.0)
        h0, h1 = S.honest_slide(self.skel, self.clip), S.honest_slide(self.skel, out)
        for s in S.SIDES:
            self.assertLess(h1[s]["drift_mm"], h0[s]["drift_mm"] + 1.0, s)

    def test_the_whole_clip_turned(self):
        out, rep = S.orient_warp(self.skel, self.clip, 90.0, 90.0, split=())
        self.assertAlmostEqual(rep["head_turn_deg"], 90.0, delta=0.1)
        self.assertAlmostEqual(S._wrap(ground_heading(self.skel, out) - ground_heading(self.skel, self.clip)), 90.0,
                               delta=1.0)


if __name__ == "__main__":
    unittest.main()
