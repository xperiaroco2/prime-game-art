"""The alien pilot's colour slots (art #196, 2026-10-23): tools/blender/alien_colour_geom.py's guard rails and slot
uniforms, and the same constants and maths in godot/alien/alien_static.gd and tools/web/alien_colour/colour.js
(the JS run through node when it is installed)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_colour_geom as G  # noqa: E402

BASES = {"skin": [0.375, 0.8039, 0.8039], "lips": [0.3765, 0.7961, 0.7961], "detail": [0.3098, 0.7098, 0.7176],
         "front": [0.7176, 0.8667, 0.8314]}  # the axolotl's build
BAD = ["#39ff14", "#ff1493", "#ffff00", "#00e5ff", "#ff7a00", "#ffffff", "#000000", "#14206e"]
GD = ROOT / "godot" / "alien" / "alien_static.gd"
JS = ROOT / "tools" / "web" / "alien_colour" / "colour.js"


class ColourSlotsTest(unittest.TestCase):
    def test_lab_round_trip(self):
        for h in BAD + ["#e39c8c", "#7f98a8"]:
            c = G.hexc(h)
            for x, y in zip(G.from_lab(G.to_lab(c)), c):
                self.assertAlmostEqual(x, y, delta=1e-4)

    def test_rails_hold_on_bad_picks(self):
        for slot in ("skin", "lips", "detail"):
            for h in BAD:
                L, a, b = G.to_lab(G.guard(slot, G.hexc(h)))
                cmax, lo, hi = G.RAILS[slot]
                self.assertLessEqual(L, hi + 0.5, (slot, h))
                self.assertGreaterEqual(L, lo - 0.5, (slot, h))
                self.assertLessEqual((a * a + b * b) ** 0.5, cmax + 0.5, (slot, h))

    def test_acid_band_is_lower(self):
        self.assertAlmostEqual(G.chroma_cap("skin", 125.0), 40.0 * 0.7)
        self.assertEqual(G.chroma_cap("skin", 200.0), 40.0)  # teal
        L, a, b = G.to_lab(G.guard("skin", G.hexc("#39ff14")))  # neon green: its hue 136 deg, in the band
        _, a0, b0 = G.to_lab(G.hexc("#39ff14"))
        cap = G.chroma_cap("skin", G.math.degrees(G.math.atan2(b0, a0)))
        self.assertLess(cap, 32.0)
        self.assertLessEqual((a * a + b * b) ** 0.5, cap + 0.5)

    def test_inside_the_rails_unchanged(self):
        for _, p in G.PRESETS:
            for slot in ("skin", "lips", "detail"):
                if slot in p:
                    self.assertEqual(G.hexs(G.guard(slot, G.hexc(p[slot]))), p[slot])
        self.assertEqual(G.guard("skin", tuple(BASES["skin"])), tuple(BASES["skin"]))  # the build's teal passes

    def test_lip_contrast(self):
        for h in BAD + ["#e39c8c"]:
            u = G.slot_colours(BASES, {"skin": h, "lips": h})
            self.assertGreaterEqual(G.delta_e(u["lip_color"], u["skin_color"]), G.LIP_CONTRAST - 0.5, h)

    def test_identity(self):
        u = G.slot_colours(BASES, {})
        self.assertEqual(u["skin_color"], u["base_skin"])
        self.assertEqual(u["front_color"], u["front_base"])
        self.assertEqual(u["front_sat_max"], 1.0)
        for k, b in (("lip_color", "lip_base"), ("detail_color", "detail_base")):
            for x, y in zip(u[k], u[b]):
                self.assertAlmostEqual(x, y, delta=1e-6)

    def test_front_is_a_tinted_cream(self):
        for _, p in G.PRESETS[1:]:
            u = G.slot_colours(BASES, p)
            L, a, b = G.to_lab(u["front_color"])
            self.assertGreaterEqual(L, 81.5)
            self.assertLessEqual((a * a + b * b) ** 0.5, 16.5)

    def test_details_off_follow_the_skin(self):
        u = G.slot_colours(BASES, {"skin": "#e39c8c", "detail": "#ff0000", "detail_on": False})
        self.assertEqual(u["detail_on"], 0.0)
        u = G.slot_colours(BASES, {"skin": "#e39c8c"})
        self.assertEqual(u["detail_on"], 0.0)
        self.assertEqual(u["gills_detail"], 1.0)

    def test_gdscript_constants_match(self):
        src = GD.read_text(encoding="utf-8")
        for slot, (c, lo, hi) in G.RAILS.items():
            self.assertIn(f'"{slot}": [{c}, {lo}, {hi}]', src)
        self.assertIn(f"const ACID: Array[float] = [{G.ACID[0]}, {G.ACID[1]}, {G.ACID[2]}]", src)
        self.assertIn(f"const LIP_CONTRAST: float = {G.LIP_CONTRAST}", src)
        self.assertIn(f"const FRONT_SAT_GAIN: float = {G.FRONT_SAT_GAIN}", src)
        gd = re.findall(r'\{"name": "([^"]+)", "picks": (\{[^}]*\})\}', src)
        self.assertEqual([n for n, _ in gd], [n for n, _ in G.PRESETS])
        for (_, gp), (_, p) in zip(gd, G.PRESETS):
            self.assertEqual(json.loads(gp), p)

    def test_js_matches(self):
        src = JS.read_text(encoding="utf-8")
        js = re.findall(r'\["([^"]+)", (\{[^}]*\})\]', src.split("export const PRESETS")[1].split("];")[0])
        self.assertEqual([n for n, _ in js], [n for n, _ in G.PRESETS])
        for (_, jp), (_, p) in zip(js, G.PRESETS):
            jp = json.loads(re.sub(r"(\w+):", r'"\1":', jp))
            self.assertEqual({("detail_on" if k == "detailOn" else k): v for k, v in jp.items()}, p)
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        picks = [p for _, p in G.PRESETS] + [{"skin": h, "lips": h, "detail": h} for h in BAD] + [
            {"skin": "#e39c8c", "detail": "#ff0000", "detail_on": False, "gills_detail": False}]
        jpicks = [{("detailOn" if k == "detail_on" else "gillsDetail" if k == "gills_detail" else k): v
                   for k, v in p.items()} for p in picks]
        out = subprocess.run([node, str(JS), "--json", json.dumps({"bases": BASES, "picks": jpicks})],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        for p, got in zip(picks, json.loads(out.stdout)):
            want = G.slot_colours(BASES, p)
            for k, v in want.items():
                for x, y in zip(v if isinstance(v, tuple) else (v,), got[k] if isinstance(got[k], list) else [got[k]]):
                    self.assertAlmostEqual(x, y, delta=1e-6, msg=(p, k))


if __name__ == "__main__":
    unittest.main()
