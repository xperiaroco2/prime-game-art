"""M9b (art #196): the slim lid shells (alien_lids_geom.LIDS, slim, set_lids), the pale skin round the mounted eye
(SOCKET light_in/light_out, eye_light) and the mouth mount (alien_lips_geom.MOUTH_MOUNT, mouth_mount), and how the
Blender scripts use them (read by pattern). Plain Python."""
from __future__ import annotations

import ast
import importlib.util
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
LP = load("alien_lips_geom")


def parts_constants() -> dict:
    tree = ast.parse((BLENDER / "alien_parts.py").read_text(encoding="utf-8"))
    return {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("EYES", "LID_BEAD")}


P = parts_constants()


class Slim(unittest.TestCase):
    def test_s9_is_exact(self):
        for d in P["EYES"].values():
            for lid in ("upper", "lower"):
                rho, bead = LG.slim(d[lid]["rho"], P["LID_BEAD"][lid], LG.LIDS_S9)
                self.assertEqual(rho, tuple(d[lid]["rho"]))
                self.assertEqual(bead, P["LID_BEAD"][lid])

    def test_thinner_with_the_inner_radius_kept(self):
        for d in P["EYES"].values():
            for lid in ("upper", "lower"):
                rho0, bead0 = d[lid]["rho"], P["LID_BEAD"][lid]
                rho, bead = LG.slim(rho0, bead0, LG.LIDS)
                self.assertEqual(rho[0], rho0[0])
                self.assertLess(rho[1] - rho[0], rho0[1] - rho0[0])
                self.assertGreater(rho[1], rho[0])
                self.assertLess(bead, bead0)

    def test_the_blink_still_seals(self):
        # the closed upper lid slides over the lower: its inner surface stays outside the lower shell
        for name, d in P["EYES"].items():
            up, _ = LG.slim(d["upper"]["rho"], P["LID_BEAD"]["upper"], LG.LIDS)
            lo, _ = LG.slim(d["lower"]["rho"], P["LID_BEAD"]["lower"], LG.LIDS)
            with self.subTest(design=name):
                self.assertGreater(up[0], lo[1])
                self.assertLess(d["upper"]["closed"], d["lower"]["closed"])

    def test_a_rolled_rim_remains(self):
        # the rim's swell is at least the slim shell's own thickness: a soft roll at the edge, not a cut sheet
        rho, bead = LG.slim(P["EYES"]["bored"]["upper"]["rho"], P["LID_BEAD"]["upper"], LG.LIDS)
        self.assertGreaterEqual(bead, rho[1] - rho[0])

    def test_set_lids(self):
        self.assertEqual(LG.set_lids({}), LG.LIDS)
        self.assertEqual(LG.set_lids({"thin": 0.3})["thin"], 0.3)
        with self.assertRaises(SystemExit):
            LG.set_lids({"thick": 0.3})
        with self.assertRaises(SystemExit):
            LG.set_lids({"rim": 0.0})


class EyeLight(unittest.TestCase):
    def test_full_near_none_far_front_only(self):
        s = LG.SOCKET
        self.assertEqual(LG.eye_light(1.0, 1.0, s["light_in"], s["light_out"]), 1.0)
        self.assertEqual(LG.eye_light(s["light_out"], 1.0, s["light_in"], s["light_out"]), 0.0)
        self.assertAlmostEqual(LG.eye_light(1.0, -0.5, s["light_in"], s["light_out"]), 0.0, places=9)
        mid = LG.eye_light((s["light_in"] + s["light_out"]) / 2, 1.0, s["light_in"], s["light_out"])
        self.assertAlmostEqual(mid, 0.5, places=6)

    def test_the_light_reaches_past_the_socket_rim(self):
        # the pale reaches beyond the soft rim (at rim_at new lid radii, S9's lid about 1.23 ball radii)
        s = LG.SOCKET
        self.assertGreater(s["light_in"], s["rim_at"] * 1.23)
        self.assertLess(s["light_out"], s["outer"] / s["scale"] + 0.5)

    def test_set_socket_refuses_a_reversed_light(self):
        with self.assertRaises(SystemExit):
            LG.set_socket({"light_in": 2.0, "light_out": 1.5})


class MouthMount(unittest.TestCase):
    def test_constant_and_centred(self):
        node = (0.0, -0.08022, 1.47227)
        c, hw, hh, front = LP.mouth_mount(node)
        self.assertEqual(c[0], 0.0)
        self.assertAlmostEqual(c[2], node[2] + LP.MOUTH_MOUNT["dz"])
        self.assertAlmostEqual(front, node[1] + LP.MOUTH_MOUNT["front"])
        self.assertEqual((hw, hh), (LP.MOUTH_MOUNT["half_w"], LP.MOUTH_MOUNT["half_h"]))
        # M8b's frog rest box on its kit (measured 2026-10-20): within 1.5 mm, so the frog skin reads as before
        lo, hi = (-0.04281, -0.10006, 1.44871), (0.04007, -0.05279, 1.49036)
        self.assertLess(abs(hw - (hi[0] - lo[0]) / 2), 0.0015)
        self.assertLess(abs(hh - (hi[2] - lo[2]) / 2), 0.0015)
        self.assertLess(abs(c[2] - (hi[2] + lo[2]) / 2), 0.0015)
        self.assertLess(abs(front - lo[1]), 0.0015)

    def test_the_scripts_use_the_mount_not_a_mouth_piece(self):
        for name in ("alien_detail.py", "alien_texture.py"):
            src = (BLENDER / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertNotIn('objects["mouth_frog_rest"]', src)
                self.assertIn("mouth_mount(", src)
                self.assertIn('objects["Mouth"]', src)


class Wiring(unittest.TestCase):
    def test_m6_and_socket(self):
        m6 = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")
        self.assertIn("--lids", m6)
        self.assertIn("LG.slim(", m6)
        sock = (BLENDER / "alien_socket.py").read_text(encoding="utf-8")
        self.assertIn("raise_light(", sock)
        self.assertIn('uv_layers["masks"]', sock)


if __name__ == "__main__":
    unittest.main()
