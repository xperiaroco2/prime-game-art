"""M9 (art #196): the standard eye mount's pure parts in tools/blender/alien_lids_geom.py (SOCKET, socket_weight,
rim_bump, eye_offset, socket_warp, set_socket) and how tools/blender/alien_socket.py and alien_m6.py use them. Plain
Python: the module is read without Blender, the Blender scripts by pattern."""
from __future__ import annotations

import importlib.util
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, BLENDER / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LG = load("alien_lids_geom")


class SocketWeight(unittest.TestCase):
    def test_full_inside_none_outside_and_monotone(self):
        s = LG.SOCKET
        self.assertEqual(LG.socket_weight(0.0, s["inner"], s["outer"]), 1.0)
        self.assertEqual(LG.socket_weight(s["inner"], s["inner"], s["outer"]), 1.0)
        self.assertEqual(LG.socket_weight(s["outer"], s["inner"], s["outer"]), 0.0)
        self.assertEqual(LG.socket_weight(9.0, s["inner"], s["outer"]), 0.0)
        ws = [LG.socket_weight(s["inner"] + i * 0.05, s["inner"], s["outer"]) for i in range(20)]
        self.assertTrue(all(a >= b for a, b in zip(ws, ws[1:])))

    def test_clamp_takes_floats(self):
        self.assertEqual([LG.clamp01(x) for x in (-1.0, 0.25, 2.0)], [0.0, 0.25, 1.0])


class RimBump(unittest.TestCase):
    def test_peak_and_reach(self):
        self.assertEqual(LG.rim_bump(1.1, 1.1, 0.14), 1.0)
        self.assertEqual(LG.rim_bump(1.1 + 0.14, 1.1, 0.14), 0.0)
        self.assertEqual(LG.rim_bump(0.9, 1.1, 0.14), 0.0)
        self.assertGreater(LG.rim_bump(1.15, 1.1, 0.14), 0.5)


class EyeOffset(unittest.TestCase):
    def test_back_and_inward_on_both_sides(self):
        fwd = (0.138, -0.99, -0.016)  # the left socket's forward axis (M7's kit)
        o = LG.eye_offset(fwd, 1.0, 0.02, 0.016)
        self.assertLess(o[0], -0.016)  # inward (toward x = 0) and the sink's own inward part
        self.assertGreater(o[1], 0.019)  # back into the head (+y: the character faces -y)
        r = LG.eye_offset((-0.138, -0.99, -0.016), -1.0, 0.02, 0.016)
        self.assertAlmostEqual(r[0], -o[0])
        self.assertAlmostEqual(r[1], o[1])


class SocketWarp(unittest.TestCase):
    def setUp(self):
        self.c, self.r0 = (0.076, -0.06, 1.553), 0.0424
        self.off = LG.eye_offset((0.138, -0.99, -0.016), 1.0, 0.02, 0.016)

    def test_the_bowl_follows_the_eye_exactly(self):
        """A skin point inside `inner` keeps its place relative to the eye: its distance to the new centre is k
        times its distance to the old one, so the smaller lids meet it as the full-size lids met the old bowl."""
        k = LG.SOCKET["scale"]
        p = (self.c[0] - 0.045, self.c[1] - 0.02, self.c[2] + 0.01)
        q = LG.socket_warp(p, self.c, self.off, k, self.r0)
        c1 = tuple(a + b for a, b in zip(self.c, self.off))
        self.assertAlmostEqual(math.dist(q, c1), k * math.dist(p, self.c), places=9)

    def test_far_skin_stays(self):
        p = (0.0, -0.07, 1.45)  # the mouth's region
        self.assertEqual(LG.socket_warp(p, self.c, self.off, 0.76, self.r0), p)

    def test_no_fold_along_a_ray(self):
        """Along a ray out of the socket the warped distance from the new centre never decreases."""
        k = 0.76
        c1 = tuple(a + b for a, b in zip(self.c, self.off))
        for d in ((0.0, -1.0, 0.0), (-0.7, -0.7, 0.0), (0.0, -0.6, 0.8), (0.6, -0.6, -0.5)):
            n = math.sqrt(sum(x * x for x in d))
            prev = -1.0
            for i in range(1, 120):
                t = i * 0.001
                p = tuple(ci + t * di / n for ci, di in zip(self.c, d))
                q = LG.socket_warp(p, self.c, self.off, k, self.r0)
                proj = sum((qi - ci) * di / n for qi, ci, di in zip(q, c1, d))
                self.assertGreater(proj, prev - 1e-12, (d, t))
                prev = proj


class SetSocket(unittest.TestCase):
    def test_override_and_refusals(self):
        s = LG.set_socket({"scale": "0.7"})
        self.assertEqual(s["scale"], 0.7)
        self.assertEqual(s["sink"], LG.SOCKET["sink"])
        with self.assertRaises(SystemExit):
            LG.set_socket({"size": 0.7})
        with self.assertRaises(SystemExit):
            LG.set_socket({"outer": 1.0})
        with self.assertRaises(SystemExit):
            LG.set_socket({"scale": 2.0})

    def test_the_mount_keeps_the_eye_inside_the_head(self):
        """M7's kit: the lid's outer x 0.0764 + 0.0518 r, the head's half width 0.099 m at the eye's height; the
        chosen mount puts the lid inside it (the sink's own inward part 0.138 of the sink)."""
        s = LG.SOCKET
        x = 0.0764 - s["inward"] - 0.138 * s["sink"] + s["scale"] * 0.0518
        self.assertLess(x, 0.099)


class Wiring(unittest.TestCase):
    def test_socket_script_and_m6(self):
        sock = (BLENDER / "alien_socket.py").read_text(encoding="utf-8")
        m6 = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")
        self.assertIn('MARKER = "prime_socket"', sock)
        self.assertIn("LG.set_socket(spec)", sock)
        self.assertIn("LG.socket_weight(", sock)
        self.assertIn("alien_socket.apply(", m6)
        self.assertIn("alien_socket.MARKER in body.keys()", m6)
        self.assertRegex(m6, re.compile(r"k, sink = 1\.0, 0\.0"))


if __name__ == "__main__":
    unittest.main()
