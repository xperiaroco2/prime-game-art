"""The alien locomotion set plays in place (art #196, option A step 3b): alien_loco_math.in_place on a synthetic
travelling loop under a rotated Hips rest, and every clip of the built GLBs (the raw folder's step-3 build; skipped
when it is missing) keeps its hips within 0.3 m of the origin on the floor plane and at a standing or crouching
height. Step 3 wrote step 2's text-to-motion loops with their source's world travel and place (hips 2 to 15 m off):
the alien left every such treadmill reel."""
import json
import math
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_loco_math as L  # noqa: E402
import alien_stride_math as S  # noqa: E402

M = S.M
ID = (1.0, 0.0, 0.0, 0.0)
RAW = Path("D:/prime-art-raw")
XY_M = 0.3
HEIGHT_M = (0.3, 1.3)


def _skel() -> dict:
    """Root at the origin, the Hips 0.9 m up with a rest turned -90 degrees about x (its basis z points along the
    armature's -y, as the alien's does), one leg."""
    q = M.q_axis_angle((1.0, 0.0, 0.0), -90.0)
    rest = {"Root": S.m4((0.0, 0.0, 0.0), ID), "Hips": S.m4((0.0, 0.0, 0.9), q),
            "LeftUpperLeg": S.m4((0.1, 0.0, 0.9), q)}
    return S.prepare({"rest": rest, "parent": {"Root": None, "Hips": "Root", "LeftUpperLeg": "Hips"}})


def _travelling(skel: dict, T: int = 20) -> dict:
    """A loop whose hips start 5 m off and travel 2 m along the armature's -y with a 3 cm sway and a 4 cm bob."""
    q = M.q_axis_angle((0.0, 0.0, 1.0), 10.0)
    locs = []
    for f in range(T + 1):
        world = (4.0 + 0.03 * math.sin(2 * math.pi * f / T), -3.0 - 2.0 * f / T, 0.04 * math.cos(4 * math.pi * f / T))
        locs.append(tuple(sum(skel["rest"]["Hips"][r][c] * world[r] for r in range(3)) for c in range(3)))
    return {"name": "t", "fps": 24.0, "loc": {"Hips": locs},
            "rot": {"Hips": [q] * (T + 1), "LeftUpperLeg": [ID] * (T + 1)}}


class InPlace(unittest.TestCase):
    def test_travel_and_offset_go_height_and_rotations_stay(self):
        skel = _skel()
        clip = _travelling(skel)
        out, rep = L.in_place(skel, clip)
        self.assertTrue(rep["cut"])
        self.assertAlmostEqual(rep["travel_m"][1], -2.0, places=6)
        before, after = (S.tracks(skel, c, ["Hips", "LeftUpperLeg"]) for c in (clip, out))
        for f, (b, a) in enumerate(zip(before["Hips"], after["Hips"])):
            self.assertLess(math.hypot(a[0], a[1]), 0.035)
            self.assertAlmostEqual(a[2], b[2], places=9)
        self.assertLess(math.hypot(after["Hips"][-1][0] - after["Hips"][0][0],
                                   after["Hips"][-1][1] - after["Hips"][0][1]), 1e-9)
        self.assertEqual(out["rot"], clip["rot"])
        legs = [tuple(x - y for x, y in zip(lg, h)) for lg, h in zip(after["LeftUpperLeg"], after["Hips"])]
        legs0 = [tuple(x - y for x, y in zip(lg, h)) for lg, h in zip(before["LeftUpperLeg"], before["Hips"])]
        for a, b in zip(legs, legs0):
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, places=9)
        self.assertLess(L.hips_extent(skel, out)["max_xy_m"], XY_M)

    def test_a_loop_in_place_comes_back_unchanged(self):
        skel = _skel()
        clip, _ = L.in_place(skel, _travelling(skel))
        again, rep = L.in_place(skel, clip)
        self.assertFalse(rep["cut"])
        self.assertIs(again, clip)


def _glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + n]), data[20 + n + 8:]


def _rotate(q, v):
    """glTF quaternion (x, y, z, w) applied to v."""
    x, y, z, w = q
    t = (2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0]))
    return (v[0] + w * t[0] + y * t[2] - z * t[1], v[1] + w * t[1] + z * t[0] - x * t[2],
            v[2] + w * t[2] + x * t[1] - y * t[0])


def hips_per_clip(path: Path) -> dict:
    """{animation: (the hips' furthest distance from the origin on the floor plane, lowest, highest height)} from the
    Hips' translation keys under its ancestors' rest (the Root carries no motion in these GLBs)."""
    g, b = _glb(path)
    nodes = g["nodes"]
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    hips = next(i for i, n in enumerate(nodes) if n.get("name") == "Hips")

    def keys(acc):
        a = g["accessors"][acc]
        v = g["bufferViews"][a["bufferView"]]
        f = struct.unpack_from(f"<{a['count'] * 3}f", b, v.get("byteOffset", 0) + a.get("byteOffset", 0))
        return [f[k:k + 3] for k in range(0, len(f), 3)]
    out = {}
    for an in g["animations"]:
        ch = next(c for c in an["channels"] if c["target"]["node"] == hips and c["target"]["path"] == "translation")
        pts = []
        for p in keys(an["samplers"][ch["sampler"]]["output"]):
            i = hips
            while i in parent:
                i = parent[i]
                n = nodes[i]
                p = _rotate(n.get("rotation", (0, 0, 0, 1)), [x * s for x, s in zip(p, n.get("scale", (1, 1, 1)))])
                p = tuple(x + t for x, t in zip(p, n.get("translation", (0, 0, 0))))
            pts.append(p)
        out[an["name"]] = (max(math.hypot(p[0], p[2]) for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))
    return out


class BuiltSet(unittest.TestCase):
    def test_every_clip_keeps_the_hips_over_the_origin(self):
        cfg = L.load()
        base = RAW / cfg["set"]["raw_base"] / cfg["set"]["out"] / "build"
        glbs = [base / c / f"{c}_char.glb" for c in cfg["set"]["chars"]]
        if not all(p.exists() for p in glbs):
            self.skipTest(f"the built GLBs are missing under {base}")
        for p in glbs:
            clips = hips_per_clip(p)
            self.assertGreaterEqual(len(clips), len(L.expand(cfg)))
            for name, (xy, lo, hi) in clips.items():
                with self.subTest(glb=p.name, clip=name):
                    self.assertLess(xy, XY_M)
                    self.assertTrue(HEIGHT_M[0] < lo <= hi < HEIGHT_M[1], (lo, hi))


if __name__ == "__main__":
    unittest.main()
