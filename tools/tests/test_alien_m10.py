"""M10 (art #196, brief UPDATE 12): the socket stage off (M9's skull change rejected), the lids' flare that closes the
gap to the unchanged socket skin (alien_lids_geom.flare_at, lid_gap, auto_flare), the lips' plumpness
(alien_lips_geom `plump`) and the lid marker alien.gd reads the rim reaches from (PR #243's review minor 1). Plain
Python; the Blender scripts are read by pattern."""
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
LP = load("alien_lips_geom")


def sphere_points(rho: float, n_t: int = 24, n_p: int = 60, p_min_deg: float = 30.0, p_max_deg: float = 180.0):
    """Points at radius rho over the upper half of a lid's local frame (latitude t, elevation p), from p_min_deg
    behind the edge (the bowl; the eye's opening is in front)."""
    pts = []
    for i in range(n_t):
        t = math.radians(-85.0 + 170.0 * (i + 0.5) / n_t)
        for j in range(n_p):
            p = math.radians(p_min_deg + (p_max_deg - p_min_deg) * (j + 0.5) / n_p)
            pts.append((rho * math.sin(t), -rho * math.cos(t) * math.cos(p), rho * math.cos(t) * math.sin(p)))
    return pts


class Flare(unittest.TestCase):
    def test_off_is_s9s_shell(self):
        for flare in (None, LG.FLARE_OFF):
            with self.subTest(flare=flare):
                self.assertEqual(LG.shell_profile(1.06, 1.13, 0.1, True, seg_p=18, rim_seg=8, flare=flare),
                                 LG.shell_profile(1.06, 1.13, 0.1, True, seg_p=18, rim_seg=8))

    def test_only_the_outer_surface_behind_the_edge_swells(self):
        f = dict(LG.FLARE_OFF, amount=0.05)
        a = LG.shell_profile(1.06, 1.13, 0.1, True, seg_p=18, rim_seg=8)
        b = LG.shell_profile(1.06, 1.13, 0.1, True, seg_p=18, rim_seg=8, flare=f)
        self.assertEqual(len(a), len(b))
        n_out = 19  # seg_p + 1 outer samples come first
        for (ra, pa, _), (rb, pb, _) in zip(a[n_out:], b[n_out:]):  # the rim and the inner surface
            self.assertEqual((ra, pa), (rb, pb))
        for (ra, pa, _), (rb, _pb, _) in zip(a[:n_out], b[:n_out]):
            want = 0.05 * LG.smoothstep(math.radians(25.0), math.radians(70.0), abs(pa))
            self.assertAlmostEqual(rb - ra, want, places=12)
        self.assertEqual(LG.flare_at(math.radians(20.0), f), 0.0)  # the edge, the bead and the wet strip
        self.assertAlmostEqual(LG.flare_at(math.radians(90.0), f), 0.05)

    def test_a_dome_inside_a_wider_bowl_has_a_gap_the_flare_closes(self):
        pts = sphere_points(1.20)
        gaps = LG.lid_gap(pts, 1.13, 0.1, True, None)
        self.assertTrue(gaps)
        self.assertAlmostEqual(max(g for _, g, _ in gaps), 0.07, delta=0.002)
        f = LG.auto_flare(pts, 1.13, 0.1, True)
        self.assertAlmostEqual(f["amount"], 0.0725 + LG.FLARE_MARGIN, delta=LG.FLARE_STEP + 1e-9)
        self.assertLessEqual(max(g for _, g, _ in LG.lid_gap(pts, 1.13, 0.1, True, f)), -LG.FLARE_MARGIN)

    def test_a_pole_fade_raises_the_amount_so_it_is_off(self):
        pts = sphere_points(1.20)
        self.assertEqual(LG.FLARE_POLE_FADE, 0.0)
        plain = LG.auto_flare(pts, 1.13, 0.1, True)["amount"]
        faded = LG.auto_flare(pts, 1.13, 0.1, True, base=dict(LG.FLARE_OFF, pole_fade=0.5))["amount"]
        self.assertGreater(faded, plain + 0.03)
        f = dict(LG.FLARE_OFF, amount=0.1, pole_fade=0.5)
        self.assertAlmostEqual(LG.flare_at(math.radians(90.0), f, 0.0), 0.1)
        self.assertAlmostEqual(LG.flare_at(math.radians(90.0), f, math.radians(89.0)), 0.05)

    def test_both_lids_of_a_design_share_one_amount(self):
        src = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")
        self.assertIn('shared = max(out[f"{dname}_{lid}"]["amount"] for lid in ("upper", "lower"))', src)
        self.assertIn('f["amount"] = shared', src)

    def test_the_ramp_sits_behind_the_front_outline(self):
        # the upper bored lid rests at 6 degrees: the dome turns away from a front view at local p = 84
        f = LG.flare_base(6.0)
        self.assertEqual((f["from_deg"], f["to_deg"]), (79.0, 169.0))  # M10b: the ramp 90 degrees long
        self.assertEqual(f["amount"], 0.0)
        self.assertEqual(LG.flare_base(-50.0)["from_deg"], 35.0)  # the manic lower lid
        f["amount"] = 0.1
        self.assertEqual(LG.flare_at(math.radians(78.0), f), 0.0)  # the dome's visible front keeps its size

    def test_a_dome_already_in_the_skin_needs_none(self):
        pts = sphere_points(1.10)
        self.assertEqual(LG.auto_flare(pts, 1.13, 0.0, True)["amount"], 0.0)

    def test_the_lower_lid_reads_the_lower_half(self):
        pts = [(x, y, -z) for x, y, z in sphere_points(1.20)]
        self.assertEqual(LG.lid_gap(pts, 1.05, 0.0, True, None), [])
        self.assertTrue(LG.lid_gap(pts, 1.05, 0.0, False, None))


class Plump(unittest.TestCase):
    SS = [i / 10 - 1 for i in range(21)]

    def edges(self):
        top = [0.010 + 0.004 * (1 - s * s) for s in self.SS]
        bot = [0.010 for _ in self.SS]
        return top, bot

    def test_plump_one_is_m8bs(self):
        top, bot = self.edges()
        self.assertEqual(LP.LIP_SHAPE["plump"], 1.0)
        p = dict(LP.LIP_SHAPE)
        p.pop("plump")
        self.assertEqual(LP.closed_edges(self.SS, top, bot, "u", LP.LIP_SHAPE),
                         LP.closed_edges(self.SS, top, bot, "u", p))

    def test_thicker_with_the_line_bow_and_taper_kept(self):
        top, bot = self.edges()
        for lip in ("u", "l"):
            a_t, a_b = LP.closed_edges(self.SS, top, bot, lip, LP.LIP_SHAPE)
            b_t, b_b = LP.closed_edges(self.SS, top, bot, lip, LP.merged({"plump": 1.15}))
            if lip == "u":
                self.assertEqual(a_b, b_b)  # the lip line (the upper lip's bottom) stays
            else:
                self.assertEqual(a_t, b_t)  # the lower lip's top stays
            for s, ta, ba, tb, bb in zip(self.SS, a_t, a_b, b_t, b_b):
                with self.subTest(lip=lip, s=s):
                    self.assertAlmostEqual((tb - bb) / (ta - ba), 1.15, places=9)  # bow and taper scale alike

    def test_rings_plumper_too(self):
        a = LP.ring_width(math.pi / 2, 0.004, 0.004, 1.0, "A", LP.LIP_SHAPE)
        b = LP.ring_width(math.pi / 2, 0.004, 0.004, 1.0, "A", LP.merged({"plump": 1.3}))
        self.assertAlmostEqual(b / a, 1.3, places=9)


class Wiring(unittest.TestCase):
    def test_the_socket_stage_is_opt_in(self):
        src = (BLENDER / "alien_socket.py").read_text(encoding="utf-8")
        self.assertIn("--opt-in-rejected-m9", src)
        self.assertRegex(src, r"if not a\.opt_in_rejected_m9:\s+raise SystemExit\(REJECTED\)")
        m6 = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")
        self.assertRegex(m6, r"if a\.socket:.*\n\s+if not a\.opt_in_rejected_m9:\s+raise SystemExit")

    def test_m6_flares_and_marks_the_lids(self):
        m6 = (BLENDER / "alien_m6.py").read_text(encoding="utf-8")
        self.assertIn('p.add_argument("--flare", default="off"', m6)  # M10b: the collar's pick
        self.assertIn("LG.auto_flare(", m6)
        self.assertIn("flare=flare.get(", m6)
        self.assertIn('LIDS_MARKER = "prime_lids"', m6)
        gd = (ROOT / "godot" / "alien" / "alien.gd").read_text(encoding="utf-8")
        self.assertIn('const LIDS_MARKER := "prime_lids"', gd)
        self.assertIn("_read_lid_reach(mat)", gd)
        self.assertTrue(re.search(r'set_shader_parameter\("upper_reach_deg", float\(_lid_reach', gd))

    def test_the_parts_geom_passes_the_flare(self):
        src = (BLENDER / "alien_parts_geom.py").read_text(encoding="utf-8")
        self.assertIn("flare=flare, t=t)", src)  # M10b: the row's latitude for the pole fade


if __name__ == "__main__":
    unittest.main()
