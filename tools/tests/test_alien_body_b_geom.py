"""Body type B's maths and target files (art #196, docs/decisions/2026-10-29-body-types.md):
tools/blender/alien_body_b_geom.py. Pure Python on a small synthetic rig; no Blender."""
from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_body_b_geom as G  # noqa: E402

TYPES = ROOT / "tools" / "blender" / "alien_body_types"
B3 = TYPES / "b3.toml"

# a small rig with body A's layout (front -y, z up): trunk, one arm and one leg per side
RIG = {
    "Root": ((0, 0, 0), (0, 0.9, 0), None),
    "Hips": ((0, 0.04, 0.82), (0, 0.013, 0.92), "Root"),
    "Spine": ((0, 0.007, 0.93), (0, -0.003, 1.03), "Hips"),
    "Chest": ((0, -0.004, 1.03), (0, -0.007, 1.15), "Spine"),
    "UpperChest": ((0, -0.007, 1.15), (0, 0.032, 1.32), "Chest"),
    "Neck": ((0, 0.041, 1.34), (0, 0.012, 1.44), "UpperChest"),
    "Head": ((0, 0.017, 1.44), (0, 0.015, 1.52), "Neck"),
}
for s, k in (("Left", 1), ("Right", -1)):
    RIG.update({
        f"{s}Shoulder": ((k * 0.031, -0.03, 1.316), (k * 0.17, 0.035, 1.316), "UpperChest"),
        f"{s}UpperArm": ((k * 0.152, 0.065, 1.2765), (k * 0.413, 0.073, 1.2765), f"{s}Shoulder"),
        f"{s}LowerArm": ((k * 0.413, 0.07, 1.2765), (k * 0.644, 0.063, 1.2765), f"{s}UpperArm"),
        f"{s}Hand": ((k * 0.644, 0.065, 1.2765), (k * 0.711, 0.065, 1.2765), f"{s}LowerArm"),
        f"{s}IndexProximal": ((k * 0.776, 0.007, 1.2685), (k * 0.805, 0.007, 1.2674), f"{s}Hand"),
        f"{s}UpperLeg": ((k * 0.114, 0.036, 0.841), (k * 0.114, 0.036, 0.518), "Hips"),
        f"{s}LowerLeg": ((k * 0.114, 0.036, 0.518), (k * 0.114, 0.082, 0.114), f"{s}UpperLeg"),
        f"{s}Foot": ((k * 0.114, 0.091, 0.115), (k * 0.114, -0.087, 0.026), f"{s}LowerLeg"),
        f"{s}Toes": ((k * 0.114, -0.087, 0.026), (k * 0.114, -0.181, 0.026), f"{s}Foot"),
    })
BONES = {n: {"head": h, "tail": t, "parent": p} for n, (h, t, p) in RIG.items()}


class BodyBGeomTest(unittest.TestCase):
    def setUp(self) -> None:
        self.t = G.load(B3)

    def test_every_target_file_loads(self) -> None:
        files = sorted(TYPES.glob("*.toml"))
        self.assertGreaterEqual(len(files), 3)
        for p in files:
            self.assertEqual(G.load(p)["name"], p.stem, p)

    def refused(self, edit, pattern: str) -> None:
        bad = copy.deepcopy(self.t)
        edit(bad)
        with self.assertRaisesRegex(ValueError, pattern):
            G.check(bad)

    def test_bad_targets_are_refused(self) -> None:
        self.refused(lambda d: d.pop("arms"), "missing keys")
        self.refused(lambda d: d.update(extra=1), "unknown keys")
        self.refused(lambda d: d["arms"].pop("hand_scale"), "arms keys")
        self.refused(lambda d: d["height"].update(scale=0.5), r"height.scale must be in")
        self.refused(lambda d: d["arms"].update(shift_in_m=0.2), "arms.shift_in_m")
        self.refused(lambda d: d["legs"].update(shift_out_m=-0.01), "legs.shift_out_m")
        self.refused(lambda d: d["profile"].update(scale=d["profile"]["scale"][:-1]), "differ in length")
        self.refused(lambda d: d["profile"]["z"].reverse(), "rise strictly")
        self.refused(lambda d: d["profile"]["scale"].__setitem__(0, 1.1), "start and end at 1.0")
        self.refused(lambda d: d["chest"].update(amount_m=0.2), "chest.amount_m")
        self.refused(lambda d: d["chest"].update(z=1.3), "reaches the neck lock")
        self.refused(lambda d: d["height"].update(lock_from_z=1.5), "lock_from_z")
        self.refused(lambda d: d["mask"].update(bones=[]), "mask.bones")
        self.refused(lambda d: d["arms"].update(upper_radial=True), "not a finite number")

    def test_the_rest_keeps_every_orientation_and_parent(self) -> None:
        r = G.rest(BONES, self.t)
        self.assertEqual(set(r), set(BONES))
        for n, b in BONES.items():
            self.assertLess(G.turn_deg(b, r[n]), 1e-6, n)
            self.assertEqual(r[n]["parent"], b["parent"])

    def test_the_rest_moves_the_joints_as_asked(self) -> None:
        r = G.rest(BONES, self.t)
        s = self.t["height"]["scale"]
        self.assertAlmostEqual(r["Hips"]["head"][2], s * 0.82, places=9)
        # the shoulder joints in: the collar shorter, then the shift
        want = 0.031 + self.t["arms"]["shoulder_axial"] * (0.152 - 0.031) - self.t["arms"]["shift_in_m"]
        self.assertAlmostEqual(r["LeftUpperArm"]["head"][0], want, delta=0.004)
        self.assertAlmostEqual(r["RightUpperArm"]["head"][0], -r["LeftUpperArm"]["head"][0], places=9)
        # the hip joints out a little, the legs scaled with the height
        self.assertAlmostEqual(r["LeftUpperLeg"]["head"][0], 0.114 + self.t["legs"]["shift_out_m"], places=9)
        self.assertAlmostEqual(r["LeftLowerLeg"]["head"][2], s * 0.518, delta=1e-4)
        # the head above the ring drops by the ring's drop: its size on the ring kept
        drop = (1 - s) * self.t["height"]["ring_z"]
        self.assertAlmostEqual(r["Head"]["head"][2], 1.44 - drop, places=9)

    def test_zmap_is_continuous_at_the_ring(self) -> None:
        ring = self.t["height"]["ring_z"]
        self.assertAlmostEqual(G.zmap(ring - 1e-9, self.t), G.zmap(ring + 1e-9, self.t), places=6)
        self.assertEqual(G.zmap(0.0, self.t), 0.0)

    def test_the_profile_is_smooth_and_one_outside(self) -> None:
        p = self.t["profile"]
        self.assertEqual(G.profile_scale(p["z"][0] - 0.01, p), 1.0)
        self.assertEqual(G.profile_scale(p["z"][-1] + 0.01, p), 1.0)
        for z, s in zip(p["z"], p["scale"]):
            self.assertAlmostEqual(G.profile_scale(z, p), s, places=9)
        zs = [0.6 + 0.0005 * i for i in range(1500)]
        vals = [G.profile_scale(z, p) for z in zs]
        self.assertLess(max(abs(b - a) for a, b in zip(vals, vals[1:])), 0.002)  # no step

    def test_a_vertex_on_one_bone_follows_its_map(self) -> None:
        r = G.rest(BONES, self.t)
        p = (0.53, 0.07 + 0.03, 1.2765)  # on the forearm's surface, 3 cm off its axis
        out, _, _ = G.deform([p, (0.114, 0.13, 0.0)], [{"LeftLowerArm": 1.0}, {"LeftFoot": 1.0}], BONES, self.t)
        def radial(q, b):
            axis = [b["tail"][i] - b["head"][i] for i in range(3)]
            n = math.sqrt(sum(c * c for c in axis))
            v = [q[i] - b["head"][i] for i in range(3)]
            a = sum(x * y / n for x, y in zip(v, axis))
            return math.sqrt(max(0.0, sum(x * x for x in v) - a * a))

        self.assertAlmostEqual(radial(out[0], r["LeftLowerArm"]) / radial(p, BONES["LeftLowerArm"]),
                               self.t["arms"]["lower_radial"], delta=0.01)
        self.assertAlmostEqual(min(q[2] for q in out), 0.0, places=9)  # the sole on the floor

    def test_the_ring_keeps_its_x_and_y(self) -> None:
        ring = self.t["height"]["ring_z"]
        pts = [(0.059 * math.cos(a / 4), 0.04 + 0.05 * math.sin(a / 4), ring) for a in range(25)]
        out, _, _ = G.deform(pts + [(0.1, 0.13, 0.0)], [{"Neck": 0.7, "UpperChest": 0.3}] * 25 + [{"LeftFoot": 1.0}],
                             BONES, self.t)
        for p, q in zip(pts, out):
            self.assertAlmostEqual(q[0], p[0], places=9)
            self.assertAlmostEqual(q[1], p[1], places=9)
        self.assertAlmostEqual(out[0][2], ring * self.t["height"]["scale"], delta=2e-3)  # the ring's drop

    def test_measure_and_ratios(self) -> None:
        a = {"height_m": 1.39, "waist_m": 0.2, "hips_m": 0.29}
        b = {"height_m": 1.325, "waist_m": 0.16, "hips_m": 0.33}
        r = G.ratios(a, b)
        self.assertEqual(r["waist_m"]["ratio"], 0.8)
        self.assertTrue(r["waist_m"]["met"])
        self.assertTrue(r["height_m"]["met"])
        self.assertTrue(r["hips_m"]["met"])
        self.assertFalse(G.ratios(a, {**b, "hips_m": 0.40})["hips_m"]["met"])


if __name__ == "__main__":
    unittest.main()
