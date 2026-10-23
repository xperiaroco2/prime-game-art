"""The alien pilot's colour slots (art #196, 2026-10-23): tools/blender/alien_colour_geom.py's guard rails and slot
uniforms, and the same constants in godot/alien/alien_static.gd and tools/web/alien_colour/colour.js, the JS maths
run through node when it is installed (the GDScript maths: test_alien_parse_godot.py, headless Godot), and the
three.js GLSL's recolour and its skin-mask gate against alien_static.gdshader's, statement by statement."""
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
SHADER = ROOT / "godot" / "alien" / "alien_static.gdshader"
# colour.js's GLSL names -> alien_static.gdshader's
JS_TO_GODOT = {"csHsv": "rgb2hsv", "csRgb": "hsv2rgb", "csSrgb": "to_srgb", "csLin": "to_linear", "csTurn": "turn",
               "csBaseSkin": "base_skin", "csSkin": "skin_color", "csFrontBase": "front_base", "csFront": "front_color",
               "csFrontSatMax": "front_sat_max", "csDetailBase": "detail_base", "csDetail": "detail_color",
               "csDetailOn": "detail_on", "csGillMode": "gill_mode", "csLipBase": "lip_base", "csLip": "lip_color"}


def statements(src: str, head: str) -> list:
    """A GLSL function's body (from its head to the first closing brace at the line start) as whitespace-free
    statements."""
    body = src.split(head, 1)[1].split("\n}", 1)[0]
    return [re.sub(r"\s+", "", st) for st in body.split(";") if st.strip()]
JS = ROOT / "tools" / "web" / "alien_colour" / "colour.js"


class ColourSlotsTest(unittest.TestCase):
    def test_oklab_round_trip(self):
        for h in BAD + ["#e39c8c", "#7f98a8"]:
            c = G.hexc(h)
            for x, y in zip(G.from_oklab(G.to_oklab(c)), c):
                self.assertAlmostEqual(x, y, delta=1e-4)
        L, a, b = G.to_oklab((1.0, 1.0, 1.0))
        self.assertAlmostEqual(L, 1.0, delta=1e-4)
        self.assertLess(abs(a) + abs(b), 1e-3)

    def test_rails_hold_on_bad_picks(self):
        for slot in ("skin", "lips", "detail"):
            for h in BAD:
                L, a, b = G.to_oklab(G.guard(slot, G.hexc(h)))
                cmax, lo, hi = G.RAILS[slot][:3]
                self.assertLessEqual(L, hi + 0.003, (slot, h))
                self.assertGreaterEqual(L, lo - 0.003, (slot, h))
                self.assertLessEqual((a * a + b * b) ** 0.5, cmax + 0.002, (slot, h))

    def test_hue_kept(self):
        """v2: the cap keeps the OKLCh hue (CS1's CIELAB cut turned navy violet: #14206e -> #534d7a)."""
        for slot in ("skin", "lips", "detail"):
            for h in BAD + ["#0000ff", "#000080", "#ff0000", "#00ff00"]:
                c = G.hexc(h)
                _, a0, b0 = G.to_oklab(c)
                _, a, b = G.to_oklab(G.guard(slot, c))
                if (a0 * a0 + b0 * b0) ** 0.5 < 0.02 or (a * a + b * b) ** 0.5 < 0.01:
                    continue  # a grey has no hue
                d = abs((G.math.degrees(G.math.atan2(b, a) - G.math.atan2(b0, a0)) + 180) % 360 - 180)
                self.assertLess(d, 1.5, (slot, h))
        navy = G.guard("skin", G.hexc("#14206e"))
        self.assertGreater(navy[2], navy[0] + 0.15)  # still blue, not violet: blue well above red

    def test_acid_band_is_lower(self):
        self.assertAlmostEqual(G.chroma_cap("skin", 125.0, 0.75), 0.108 * 0.7)
        self.assertAlmostEqual(G.chroma_cap("skin", 341.0, 0.75), 0.108 * 0.8)  # hot pink
        self.assertEqual(G.chroma_cap("skin", 200.0, 0.75), 0.108)  # teal
        self.assertAlmostEqual(G.chroma_cap("skin", 200.0, 0.44), 0.108 * 0.431 / 0.603)  # a dark skin
        self.assertAlmostEqual(G.chroma_cap("detail", 200.0, 0.871), 0.113 * 0.129 / 0.259)  # a light detail
        self.assertEqual(G.chroma_cap("lips", 200.0, 0.5), 0.113)
        L, a, b = G.to_oklab(G.guard("skin", G.hexc("#39ff14")))  # neon green: its OKLCh hue 142 deg, in the band
        _, a0, b0 = G.to_oklab(G.hexc("#39ff14"))
        cap = G.chroma_cap("skin", G.math.degrees(G.math.atan2(b0, a0)), L)
        self.assertLess(cap, 0.09)
        self.assertLessEqual((a * a + b * b) ** 0.5, cap + 0.002)

    def test_inside_the_rails_unchanged(self):
        for _, p in G.PRESETS:
            for slot in ("skin", "lips", "detail"):
                if slot in p:
                    self.assertEqual(G.hexs(G.guard(slot, G.hexc(p[slot]))), p[slot])
        self.assertEqual(G.guard("skin", tuple(BASES["skin"])), tuple(BASES["skin"]))  # the build's teal passes

    def test_lip_contrast(self):
        for h in BAD + ["#e39c8c"]:
            u = G.slot_colours(BASES, {"skin": h, "lips": h})
            self.assertGreaterEqual(G.delta_e(u["lip_color"], u["skin_color"]), G.LIP_CONTRAST - 0.01, h)

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
            L, a, b = G.to_oklab(u["front_color"])
            self.assertGreaterEqual(L, 0.842)
            self.assertLessEqual((a * a + b * b) ** 0.5, 0.045)

    def test_details_off_follow_the_skin(self):
        u = G.slot_colours(BASES, {"skin": "#e39c8c", "detail": "#ff0000", "detail_on": False})
        self.assertEqual(u["detail_on"], 0.0)
        u = G.slot_colours(BASES, {"skin": "#e39c8c"})
        self.assertEqual(u["detail_on"], 0.0)
        self.assertEqual(u["gill_mode"], 1.0)  # the gradient, the default
        for mode, v in (("skin", 0.0), ("gradient", 1.0), ("whole", 2.0)):
            self.assertEqual(G.slot_colours(BASES, {"gills": mode})["gill_mode"], v)

    def test_gdscript_constants_match(self):
        src = GD.read_text(encoding="utf-8")
        for slot, r in G.RAILS.items():
            self.assertIn(f'"{slot}": [' + ", ".join("null" if x is None else str(x) for x in r) + "]", src)
        self.assertIn("const BANDS: Array = [" + ", ".join(f"[{c}, {h}, {k}]" for c, h, k in G.BANDS) + "]", src)
        self.assertIn(f"const LIP_CONTRAST: float = {G.LIP_CONTRAST}", src)
        self.assertIn(f"const FRONT_SAT_GAIN: float = {G.FRONT_SAT_GAIN}", src)
        self.assertIn("const GILL_MODES: PackedStringArray = [" + ", ".join(f'"{m}"' for m in G.GILL_MODES) + "]", src)
        # PR #304's re-review: PALETTE is exactly the skin guard of PALETTE_288, as hexs gives it
        m288 = re.search(r"const PALETTE_288: Array\[Color\] = \[(.*?)\]\n", src, re.S).group(1)
        p288 = [tuple(float(x) for x in c.split(",")) for c in re.findall(r"Color\(([^)]*)\)", m288)]
        m = re.search(r"const PALETTE: Array\[Color\] = \[(.*?)\]\n", src, re.S).group(1)
        pal = re.findall(r'Color\("(#[0-9a-f]{6})"\)', m)
        self.assertEqual(len(p288), 4)
        self.assertEqual(pal, [G.hexs(G.guard("skin", c)) for c in p288])
        gd = re.findall(r'\{"name": "([^"]+)", "picks": (\{[^}]*\})\}', src)
        self.assertEqual([n for n, _ in gd], [n for n, _ in G.PRESETS])
        for (_, gp), (_, p) in zip(gd, G.PRESETS):
            self.assertEqual(json.loads(gp), p)

    def test_gill_modes_validated(self):  # PR #304's review: an unknown gill mode is an error everywhere
        with self.assertRaises(ValueError):
            G.slot_colours(BASES, {"gills": "fringe"})
        self.assertIn("if gm < 0:\n\t\tpush_error(", GD.read_text(encoding="utf-8"))
        self.assertIn("if (!GILL_MODES.includes(gills)) throw new Error(", JS.read_text(encoding="utf-8"))

    def test_accent_without_gills_warns(self):  # PR #304's re-review: never a silent "gradient" for "skin"/"whole"
        gd = GD.read_text(encoding="utf-8")
        self.assertIn("elif accent != null:  # v4: without the gills' texture", gd)
        self.assertIn('push_warning("alien_static: %s: an accent mask without the gill texture', gd)
        js = JS.read_text(encoding="utf-8")
        self.assertIn('console.warn("colour.js: an accent mask without the gill texture', js)
        self.assertIn("if (gillUrl) gillTex = await dataTexture(THREE, gillUrl);", js)

    def test_glsl_matches_the_godot_shader(self):  # PR #304's review: the browser gated by the skin mask as Godot
        js, gd = JS.read_text(encoding="utf-8"), SHADER.read_text(encoding="utf-8")
        want = statements(gd, "vec3 recolour(vec3 c, vec3 acc, float gill) {")
        renamed = js
        for a, b in JS_TO_GODOT.items():
            renamed = re.sub(rf"\b{a}\b", b, renamed)
        got = statements(renamed, "vec3 csRecolour(vec3 c, vec3 acc, float gill) {")
        self.assertEqual(got, want)
        self.assertIn("vec3 b = rgb2hsv(to_srgb(base_c));", gd)  # Godot's uniforms are linear (source_color)
        self.assertIn("b = csHsv(b); t = csHsv(t);", js)  # three.js's are the sRGB numbers
        flat = re.sub(r"\s+", "", js.split("export const MAP_FRAGMENT", 1)[1].split("`;", 1)[0])
        self.assertIn("vec4sampledDiffuseColor=texture2D(map,vMapUv);vec3csA=sampledDiffuseColor.rgb;"
                      "sampledDiffuseColor.rgb=mix(csA,csRecolour(csA,texture2D(csAccent,vMapUv).rgb,"
                      "texture2D(csGill,vMapUv).r),texture2D(csMask,vMapUv).r);diffuseColor*=sampledDiffuseColor;", flat)
        g = re.sub(r"\s+", "", gd)
        self.assertIn("vec3a=texture(albedo_tex,UV).rgb;", g)
        self.assertIn("vec3m=texture(mask_tex,UV).rgb;", g)
        self.assertIn("vec3c=mix(a,recolour(a,texture(accent_tex,UV).rgb,texture(gill_tex,UV).r),m.r);", g)
        self.assertNotIn(".a", "".join(want))  # v3: no alpha read: the gills are their own texture

    def test_js_matches(self):
        src = JS.read_text(encoding="utf-8")
        js = re.findall(r'\["([^"]+)", (\{[^}]*\})\]', src.split("export const PRESETS")[1].split("];")[0])
        self.assertEqual([n for n, _ in js], [n for n, _ in G.PRESETS])
        for (_, jp), (_, p) in zip(js, G.PRESETS):
            jp = json.loads(re.sub(r"(\w+):", r'"\1":', jp))
            self.assertEqual({("detail_on" if k == "detailOn" else k): v for k, v in jp.items()}, p)
        rails = re.search(r"export const RAILS = \{(.*?)\};", src, re.S).group(1)
        for slot, r in G.RAILS.items():
            self.assertIn(f"{slot}: [" + ", ".join("null" if x is None else f"{x:g}" for x in r) + "]", rails)
        self.assertIn("export const BANDS = [" + ", ".join(f"[{c:g}, {h:g}, {k}]" for c, h, k in G.BANDS) + "]", src)
        self.assertIn(f"export const LIP_CONTRAST = {G.LIP_CONTRAST};", src)
        self.assertIn("export const GILL_MODES = [" + ", ".join(f'"{m}"' for m in G.GILL_MODES) + "]", src)
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        picks = [p for _, p in G.PRESETS] + [{"skin": h, "lips": h, "detail": h} for h in BAD] + [
            {"skin": "#e39c8c", "detail": "#ff0000", "detail_on": False, "gills": "skin"},
            {"skin": "#14206e", "lips": "#ffffff", "gills": "whole"}, {"skin": "#0000ff", "lips": "#0000ff"},
            {"gills": "fringe"}]
        jpicks = [{("detailOn" if k == "detail_on" else k): v
                   for k, v in p.items()} for p in picks]
        out = subprocess.run([node, str(JS), "--json", json.dumps({"bases": BASES, "picks": jpicks})],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        for p, got in zip(picks, json.loads(out.stdout)):
            if p.get("gills") == "fringe":  # an unknown gill mode: an error in JS as in Python
                self.assertIn("unknown gills", got.get("error", ""))
                continue
            want = G.slot_colours(BASES, p)
            for k, v in want.items():
                for x, y in zip(v if isinstance(v, tuple) else (v,), got[k] if isinstance(got[k], list) else [got[k]]):
                    self.assertAlmostEqual(x, y, delta=1e-6, msg=(p, k))


if __name__ == "__main__":
    unittest.main()
