"""M6 (art #196): tools/blender/alien_lids_geom.py, the lid shells' rounded corners, the eye unit's size and the skin's
contact field, and the constants godot/alien/alien.gd shares with the shaders and tools/blender/alien_m6.py. Plain
Python: the module is read without Blender, the GDScript and the shaders by pattern."""
from __future__ import annotations

import importlib.util
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GD = ROOT / "godot" / "alien" / "alien.gd"
LIP = ROOT / "godot" / "alien" / "alien_lip.gdshader"
HUE = ROOT / "godot" / "alien" / "alien_hue.gdshader"
M6 = ROOT / "tools" / "blender" / "alien_m6.py"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "blender" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LG = load("alien_lids_geom")
E = load("alien_eyes_geom")


def gd_const_keys(text: str, name: str) -> set[str]:
    """The keys of a GDScript dictionary constant (one line or several; balanced braces)."""
    i = text.index(f"const {name} := {{") + len(f"const {name} := ")
    depth, j = 0, i
    while True:
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if depth == 0:
            break
    body = re.sub(r"#[^\n]*", "", text[i:j])
    return set(re.findall(r'"(\w+)":', body))


def uniforms(path: Path) -> set[str]:
    return set(re.findall(r"^(?:instance )?uniform \w+ (\w+)", path.read_text(encoding="utf-8"), re.M))


def s7_profile(rho_in, rho_out, bead, upper, span_deg=200.0, seg_p=12, rim_seg=5, bead_deg=26.0):
    """S7's lid_shell profile as it was written before M6 (in r), for the no-change check."""
    sgn = 1.0 if upper else -1.0
    re_ = rho_out + bead
    rm, hw = (re_ + rho_in) / 2, (re_ - rho_in) / 2
    bd = math.radians(bead_deg)
    prof = []
    for j in range(seg_p + 1):
        f = (1 - j / seg_p) ** (2 if bead else 1)
        p = math.radians(span_deg) * f
        swell = bead * (1 - LG.smoothstep(0.0, bd, p)) if bead else 0.0
        prof.append((rho_out + swell, sgn * p))
    for j in range(1, rim_seg):
        a = math.pi * j / rim_seg
        prof.append((rm + hw * math.cos(a), -sgn * (hw * math.sin(a)) / rm))
    for j in range(seg_p + 1):
        prof.append((rho_in, sgn * math.radians(span_deg) * (j / seg_p) ** (2 if bead else 1)))
    return prof


class Corners(unittest.TestCase):
    def test_no_shift_is_s7(self):
        for upper, rho, bead in ((True, (1.06, 1.13), 0.10), (False, (1.012, 1.05), 0.035), (True, (1.05, 1.095), 0.0)):
            got = LG.shell_profile(rho[0], rho[1], bead, upper, seg_p=18, rim_seg=8)
            want = s7_profile(rho[0], rho[1], bead, upper, seg_p=18, rim_seg=8)
            self.assertEqual(len(got), len(want))
            for (r1, p1, q1), (r2, p2) in zip(got, want):
                self.assertAlmostEqual(r1, r2, places=12)
                self.assertAlmostEqual(p1, p2, places=12)
                self.assertAlmostEqual(q1, p2, places=12)

    def test_weight_and_taper(self):
        tm = math.radians(89.0)
        c = LG.CORNER
        self.assertEqual(LG.corner_weight(0.0, tm, c), 0.0)
        self.assertEqual(LG.corner_weight(math.radians(c["from_deg"]), tm, c), 0.0)
        self.assertAlmostEqual(LG.corner_weight(tm, tm, c), 1.0)
        self.assertAlmostEqual(LG.bead_at(0.1, 0.0, tm, c), 0.1)
        self.assertAlmostEqual(LG.bead_at(0.1, tm, tm, c), 0.1 * c["bead_keep"])
        prev = 1.0
        for i in range(90):  # the swell never grows toward the pole
            b = LG.bead_at(0.1, math.radians(i), tm, c) / 0.1
            self.assertLessEqual(b, prev + 1e-12)
            prev = b
        # off: S7's shell at every latitude
        for t in (0.0, 0.7, tm):
            self.assertEqual(LG.bead_at(0.1, t, tm, LG.CORNER_OFF), 0.1)
            self.assertEqual(LG.edge_shift(t, tm, True, LG.CORNER_OFF), 0.0)

    def test_edges_bend_toward_each_other(self):
        tm = math.radians(89.0)
        self.assertLess(LG.edge_shift(tm, tm, True), 0.0)  # the upper lid's edge goes down
        self.assertGreater(LG.edge_shift(tm, tm, False), 0.0)  # the lower lid's up
        self.assertEqual(LG.edge_shift(0.0, tm, True), 0.0)

    def test_shift_fades_to_the_back(self):
        sh = math.radians(6.0)
        prof = LG.shell_profile(1.06, 1.13, 0.1, True, seg_p=18, rim_seg=8, shift=-sh, crowd=True)
        back = [(p, p0) for _, p, p0 in prof if abs(abs(p0) - math.radians(200.0)) < 1e-9]
        self.assertTrue(back)
        for p, p0 in back:
            self.assertAlmostEqual(p, p0, places=12)
        edge = [(p, p0) for _, p, p0 in prof if abs(p0) < 1e-12]
        for p, p0 in edge:
            self.assertAlmostEqual(p - p0, -sh, places=12)
        # crowd keeps the sampling of a beaded lid when the taper leaves no bead
        a = LG.shell_profile(1.06, 1.13, 0.0, True, crowd=True)
        b = LG.shell_profile(1.06, 1.13, 0.1, True)
        self.assertEqual([round(p0, 12) for _, _, p0 in a[:13]], [round(p0, 12) for _, _, p0 in b[:13]])

    def test_corner_no_longer_sticks_out(self):
        # S7's upper lid (bored: rho_out 1.13, bead 0.10) reached 0.1 r past the dome's outline at its corners
        s7 = LG.corner_overhang(1.13, 0.10, LG.CORNER_OFF)
        m6 = LG.corner_overhang(1.13, 0.10, LG.CORNER)
        self.assertGreater(s7, 0.09)
        self.assertLess(m6, 0.1 * s7)
        pts = LG.front_outline(1.13, 0.10, 6.0, True)
        xs = [abs(x) for x, _ in pts]
        self.assertLessEqual(max(xs), 1.13 + 1e-9 + 0.1 * LG.CORNER["bead_keep"])


class SizeAndContact(unittest.TestCase):
    def test_scale_about(self):
        self.assertEqual(LG.scale_about((1.0, 2.0, 3.0), (1.0, 2.0, 3.0), 0.5), (1.0, 2.0, 3.0))
        self.assertEqual(LG.scale_about((2.0, 2.0, 3.0), (1.0, 2.0, 3.0), 0.5), (1.5, 2.0, 3.0))
        self.assertTrue(0.8 <= LG.EYE_SCALE <= 1.0)

    def test_iris_keeps_the_cornea_rule(self):
        bored = {"limbus_deg": 27.0, "iris_deg": 25.0, "pupil_deg": 11.5, "limbus_soft_deg": 1.0}
        for k in (1.0, 0.95, 0.9, LG.IRIS_SCALE):
            got = LG.iris_look(bored, k)
            self.assertAlmostEqual(got["pupil_deg"], round(11.5 * k, 3))
            self.assertLessEqual(got["iris_deg"] + 0.9, got["limbus_deg"] - got["limbus_soft_deg"] + 0.05)

    def test_contact(self):
        r = LG.CONTACT["reach"]
        self.assertEqual(LG.contact(0.0), 1.0)
        self.assertEqual(LG.contact(r), 0.0)
        self.assertEqual(LG.contact(2 * r), 0.0)
        vals = [LG.contact(r * i / 20) for i in range(21)]
        self.assertTrue(all(a >= b for a, b in zip(vals, vals[1:])))


class Constants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = GD.read_text(encoding="utf-8")

    def test_lip_looks_are_uniforms(self):
        lip = uniforms(LIP)
        for name in ("LIP_LOOK", "LID_LOOK", "LIP_LOOK_M5"):
            missing = gd_const_keys(self.gd, name) - lip
            self.assertFalse(missing, f"{name}: not alien_lip uniforms: {missing}")

    def test_contact_keys_are_uniforms(self):
        missing = gd_const_keys(self.gd, "SKIN_CONTACT") - uniforms(HUE)
        self.assertFalse(missing, missing)

    def test_marker_matches_the_build(self):
        gd = re.search(r'const CONTACT_MARKER := \{"(\w+)": "(\w+)"\}', self.gd)
        py = re.search(r'CONTACT_MARKER = \{"(\w+)": "(\w+)"\}', M6.read_text(encoding="utf-8"))
        self.assertIsNotNone(gd)
        self.assertEqual(gd.groups(), py.groups())

    def test_m5_look_is_the_s9_lip(self):
        # lip_look "m5" must draw the lips and lids as before M6: the new lip shader terms are off at their defaults
        sh = LIP.read_text(encoding="utf-8")
        for name in ("ao_mix", "ao_occl", "drift", "sss", "transmit", "rim_value"):
            m = re.search(rf"^uniform float {name}\b[^=]*= ([0-9.]+);", sh, re.M)
            self.assertIsNotNone(m, name)
            self.assertEqual(float(m.group(1)), 0.0, name)
        self.assertNotIn("ao_mix", gd_const_keys(self.gd, "LIP_LOOK_M5"))

    def test_wet_rim_reach_unchanged_in_the_middle(self):
        # the lid's middle keeps S7's rim, so alien.gd EYE_LOOK's *_reach_deg stay valid
        tm = math.radians(89.0)
        self.assertEqual(LG.bead_at(0.10, 0.0, tm), 0.10)
        self.assertAlmostEqual(math.degrees(E.rim_reach(1.06, 1.13, LG.bead_at(0.10, 0.0, tm))), 4.3, delta=0.2)


if __name__ == "__main__":
    unittest.main()
