"""The alien pilot's colour slots (art #196, 2026-10-23): tools/blender/alien_colour_geom.py's slot uniforms and
per-texel recolour (CS6: every pick applied as picked, each region's median texel becoming the pick exactly), the
same constants in godot/alien/alien_static.gd and tools/web/alien_colour/colour.js, the JS maths run through node
when it is installed (the GDScript maths: test_alien_parse_godot.py, headless Godot), and the three.js GLSL's
recolour and its skin-mask gate against alien_static.gdshader's, statement by statement."""
from __future__ import annotations

import json
import math
import random
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import alien_colour_geom as G  # noqa: E402

BASES = {"skin": [0.375, 0.8039, 0.8039], "lips": [0.3765, 0.7961, 0.7961], "detail": [0.3922, 0.8039, 0.8039],
         "front": [0.7412, 0.8745, 0.8275], "gill_tips": [0.3216, 0.7255, 0.7333],
         "gill_whole": [0.3373, 0.7569, 0.7608]}  # the axolotl's build (the regions' medians)
# both heads' bases as v7's page reads them (<raw>/research/2026-10-22-roster/design/pilot3d/colour_slots/v7/web/
# heads.json, the texels' medians, `bases_from_texels`)
HEADS = {"axolotl": {"skin": [0.3959, 0.7946, 0.7919], "lips": [0.377, 0.7965, 0.7965], "front": [0.7393, 0.8762, 0.8284],
                     "detail": [0.3905, 0.8041, 0.8048], "gill_tips": [0.3199, 0.7263, 0.7334],
                     "gill_whole": [0.3359, 0.7554, 0.7612]},
         "chameleon": {"skin": [0.4349, 0.7493, 0.7431], "lips": [0.3804, 0.698, 0.6941],
                       "front": [0.7676, 0.8984, 0.8314], "detail": [0.3176, 0.6196, 0.6157],
                       "gill_tips": [0.3176, 0.6196, 0.6157], "gill_whole": [0.3176, 0.6196, 0.6157]}}
# 12 hues every 30 degrees, then the engineer's yellow, black, white and the acidic picks
PICKS = ["#ff0000", "#ff8000", "#ffff00", "#80ff00", "#00ff00", "#00ff80", "#00ffff", "#0080ff", "#0000ff",
         "#8000ff", "#ff00ff", "#ff0080", "#ffee00", "#000000", "#ffffff", "#39ff14", "#ff1493", "#14206e"]
GD = ROOT / "godot" / "alien" / "alien_static.gd"
SHADER = ROOT / "godot" / "alien" / "alien_static.gdshader"
JS = ROOT / "tools" / "web" / "alien_colour" / "colour.js"
# colour.js's GLSL names -> alien_static.gdshader's (csU(x), an sRGB uniform in OKLab, is Godot's oklab(x) on a
# linear uniform; csLin(uniform) is dropped first: Godot's source_color uniforms arrive linear)
JS_TO_GODOT = {"csLab": "oklab", "csLabLin": "oklab_linear", "csShift": "shift", "csU": "oklab",
               "csBaseSkin": "base_skin", "csSkin": "skin_color", "csFrontBase": "front_base", "csFront": "front_color",
               "csDetailBase": "detail_base", "csDetail": "detail_color", "csGillBase": "gill_base",
               "csGillColor": "gill_color", "csDetailOn": "detail_on", "csGillMode": "gill_mode",
               "csLipBase": "lip_base", "csLip": "lip_color"}
# per slot: the picks key, the texel's accent (lips, details, front) and gill weight in that region, the gill mode
REGION_TEXELS = {"skin": ("skin", (0, 0, 0), 0.0, "gradient", "skin"),
                 "lips": ("lips", (1, 0, 0), 0.0, "gradient", "lips"),
                 "detail": ("detail", (0, 1, 0), 0.0, "gradient", "detail"),
                 "gill_tips": ("detail", (0, 1, 0), 1.0, "gradient", "gill_tips"),
                 "gill_whole": ("detail", (0, 0, 0), 1.0, "whole", "gill_whole")}


def statements(src: str, head: str) -> list:
    """A GLSL function's body (from its head to the first closing brace at the line start) as whitespace-free
    statements."""
    body = src.split(head, 1)[1].split("\n}", 1)[0]
    return [re.sub(r"\s+", "", st) for st in body.split(";") if st.strip()]


def godot_names(js: str) -> str:
    js = re.sub(r"\bcsLin\((cs\w+)\)", r"\1", js)
    for a, b in JS_TO_GODOT.items():
        js = re.sub(rf"\b{a}\b", b, js)
    return js


class ColourSlotsTest(unittest.TestCase):
    def test_oklab_round_trip(self):
        for h in PICKS + ["#e39c8c", "#7f98a8"]:
            c = G.hexc(h)
            for x, y in zip(G.from_oklab(G.to_oklab(c)), c):
                self.assertAlmostEqual(x, y, delta=1e-4)
        L, a, b = G.to_oklab((1.0, 1.0, 1.0))
        self.assertAlmostEqual(L, 1.0, delta=1e-4)
        self.assertLess(abs(a) + abs(b), 1e-3)

    def test_picks_applied_as_picked(self):  # CS6: no guard rails in any slot
        for h in PICKS:
            u = G.slot_colours(BASES, {"skin": h, "lips": h, "detail": h})
            for k in ("skin_color", "lip_color", "detail_color", "gill_color"):
                self.assertEqual(G.hexs(u[k]), h, (h, k))
        for name in ("guard", "chroma_cap", "lip_contrast", "RAILS", "BANDS", "LIP_CONTRAST", "FRONT_SAT_GAIN"):
            self.assertFalse(hasattr(G, name), name)
        gd, js, sh = (p.read_text(encoding="utf-8") for p in (GD, JS, SHADER))
        for word in ("guard(", "RAILS", "BANDS", "LIP_CONTRAST", "lip_contrast", "lipContrast", "front_sat_max",
                     "FrontSatMax", "chroma_cap", "chromaCap"):
            for name, src in (("gd", gd), ("js", js), ("shader", sh)):
                self.assertNotIn(word, src, (name, word))

    def test_a_pick_reaches_its_region_exactly(self):
        """Every slot: the region's base texel (its median) becomes the picked colour, within 1/255."""
        for region, (key, acc, gill, mode, base) in REGION_TEXELS.items():
            for h in PICKS:
                u = G.slot_colours(BASES, {key: h, "gills": mode})
                got = G.texel(tuple(BASES[base]), acc, gill, u)
                for x, y in zip(got, G.hexc(h)):
                    self.assertAlmostEqual(x, y, delta=1 / 255, msg=(region, h, G.hexs(got)))

    def test_shading_kept_round_the_pick(self):
        """A texel lighter (darker) than its region's base stays lighter (darker) than the pick, unless the pick is
        white (black) already."""
        for h in PICKS:
            t = G.to_oklab(G.hexc(h))
            for dl in (-0.08, 0.06):
                b = G.to_oklab(tuple(BASES["gill_tips"]))
                x = (b[0] + dl, b[1] * 0.8, b[2] * 0.8)
                L = G.shift(x, b, t)[0]
                if 0.02 < t[0] < 0.98:
                    self.assertGreater(L - t[0] if dl > 0 else t[0] - L, 0.0, (h, dl))
                self.assertGreaterEqual(L, -1e-9)
                self.assertLessEqual(L, 1.0 + 1e-9)

    def test_region_median_reaches_the_pick(self):
        """CS6b: a synthetic region (texels spread round a base in L, a and b as the painted skin, a quarter of them a dark tail) keeps
        its median within 0.003 OKLab of every pick whose shifted texels stay inside the sRGB gamut, within 0.012
        (the albedo table's bound) of a pick on the gamut's edge, after `texel`."""
        rnd = random.Random(7)
        base = G.to_oklab(tuple(BASES["skin"]))
        tx = []
        for i in range(1200):
            dl = -rnd.uniform(0.2, 0.5) if i % 4 == 0 else rnd.gauss(0.0, 0.012)
            tx.append(G.from_oklab((base[0] + dl, base[1] + rnd.gauss(0.0, 0.012), base[2] + rnd.gauss(0.0, 0.012))))
        b = G.median_lab(tx)
        bases = {**BASES, "skin": b}
        inner = ["#e39c8c", "#a99cd8", "#e2c07a", "#6c87c6", "#8fb99f", "#a07596", "#7f98a8", "#808080", "#c04040"]
        for h in PICKS + inner:
            u = G.slot_colours(bases, {"skin": h})
            m = G.median_lab([G.texel(c, (0, 0, 0), 0.0, u) for c in tx])
            self.assertLess(G.delta_e(m, G.hexc(h)), 0.003 if h in inner else 0.012, (h, G.hexs(m)))

    def test_dark_picks_keep_the_mottling_relative(self):
        """CS6b: on a darker pick every offset shrinks with the lightness ratio (navy is not blotchy); lighter picks
        keep the darker offsets whole."""
        b = G.to_oklab(tuple(BASES["skin"]))
        x = (b[0] + 0.03, b[1] + 0.02, b[2] - 0.01)
        for h in ("#14206e", "#000000", "#0000ff", "#ffee00", "#ffffff"):
            t = G.to_oklab(G.hexc(h))
            y = G.shift(x, b, t)
            kr = min(1.0, t[0] / b[0])
            self.assertLessEqual(y[0] - t[0], 0.03 * kr + 1e-9, h)
            self.assertLessEqual(math.dist(y[1:], t[1:]), math.hypot(0.02, 0.01) * kr + 1e-9, h)
        dark = (b[0] - 0.1, b[1], b[2])
        self.assertAlmostEqual(G.shift(dark, b, G.to_oklab(G.hexc("#ffee00")))[0],
                               G.to_oklab(G.hexc("#ffee00"))[0] - 0.1, delta=1e-9)

    def test_front_modes(self):
        """CS6b: "keep" (the default) holds the build's two-tone against any skin, pale on dark skins; "follow"
        follows the skin down; a skin at its base gives the build's front in both."""
        L = lambda c: G.to_oklab(c)[0]  # noqa: E731
        d = L(tuple(BASES["front"])) - L(tuple(BASES["skin"]))
        self.assertGreater(d, 0.05)
        for mode in G.FRONT_MODES:
            u = G.slot_colours(BASES, {"skin": tuple(BASES["skin"]), "front": mode})
            self.assertLess(max(abs(x - y) for x, y in zip(u["front_color"], BASES["front"])), 1e-6, mode)
        for h in PICKS + ["#e9f5f0", "#f0f0f0", "#d8e8e0"]:
            keep = G.slot_colours(BASES, {"skin": h})["front_color"]
            self.assertEqual(keep, G.slot_colours(BASES, {"skin": h, "front": "keep"})["front_color"])
            if abs(L(G.hexc(h)) - (1.0 - 0.5 * d)) > 0.5 * G.FRONT_BAND:  # inside the band it passes the skin's L
                self.assertGreaterEqual(abs(L(keep) - L(G.hexc(h))), 0.5 * d - 2e-2, h)  # white caps it above
            if L(G.hexc(h)) < L(tuple(BASES["skin"])):
                self.assertGreaterEqual(L(keep), L(tuple(BASES["front"])) - 2e-3, h)  # pale on a dark skin
        navy = G.slot_colours(BASES, {"skin": "#14206e", "front": "follow"})["front_color"]
        self.assertLess(L(navy), 0.6)
        with self.assertRaises(ValueError):
            G.slot_colours(BASES, {"skin": "#14206e", "front": "pale"})

    def test_keep_front_is_continuous(self):
        """CS6c (PR #310's review): the "keep" front stepped from white to 1 - 1.5 d at skin L = 1 - d/2 (axolotl
        grey 239: L 1.0 -> 0.856; chameleon grey 232: 1.0 -> 0.791). Now blended over FRONT_BAND: on both heads, along
        the 256 greys and the tints from five hues to white, no step in the front's L above 0.02 between neighbours;
        no picks and a pick at the base stay exact."""
        L = lambda c: G.to_oklab(c)[0]  # noqa: E731
        hues = {"grey": None, "red": (1, 0, 0), "yellow": (1, 1, 0), "teal": (0, 1, 1), "blue": (0, 0, 1),
                "pink": (1, 0.08, 0.58)}
        for name, bases in HEADS.items():
            for hn, h in hues.items():
                ramp = [(i / 255,) * 3 if h is None else tuple(c + i / 255 * (1 - c) for c in h) for i in range(256)]
                fl = [L(G.slot_colours(bases, {"skin": c})["front_color"]) for c in ramp]
                worst = max(abs(fl[i + 1] - fl[i]) for i in range(255))
                self.assertLess(worst, 0.02, (name, hn))
            self.assertEqual(G.slot_colours(bases, {})["front_color"], tuple(bases["front"]), name)
            at = G.slot_colours(bases, {"skin": tuple(bases["skin"])})["front_color"]
            self.assertLess(max(abs(x - y) for x, y in zip(at, bases["front"])), 1e-6, name)
            d = L(tuple(bases["front"])) - L(tuple(bases["skin"]))
            for g in (0.0, 0.5, 0.8):  # away from the band the rule is CS6b's
                if abs(L((g,) * 3) - (1 - 0.5 * d)) > G.FRONT_BAND:
                    f = L(G.slot_colours(bases, {"skin": (g,) * 3})["front_color"])
                    self.assertGreaterEqual(abs(f - L((g,) * 3)), 0.5 * d - 2e-2, (name, g))

    def test_identity(self):
        u = G.slot_colours(BASES, {})
        for k, b in (("skin_color", "base_skin"), ("front_color", "front_base"), ("lip_color", "lip_base"),
                     ("detail_color", "detail_base"), ("gill_color", "gill_base")):
            self.assertEqual(tuple(u[k]), tuple(u[b]), k)
        # every texel unchanged within 1/255 (the shader's identity: the merged look)
        for h in PICKS + ["#5fcdcd", "#bddfd3", "#2a6e70", "#e9f5f0"]:
            for acc, gill in (((0, 0, 0), 0), ((1, 0, 0), 0), ((0, 1, 0), 0), ((0, 0, 1), 0), ((0, 1, 0), 1),
                              ((0.3, 0.5, 0.2), 0.4)):
                for mode in G.GILL_MODES:
                    um = G.slot_colours(BASES, {"gills": mode})
                    for x, y in zip(G.texel(G.hexc(h), acc, gill, um), G.hexc(h)):
                        self.assertAlmostEqual(x, y, delta=1 / 255, msg=(h, acc, gill, mode))

    def test_front_is_a_tinted_cream(self):
        cf = sum(v * v for v in G.to_oklab(tuple(BASES["front"]))[1:]) ** 0.5
        for h in PICKS:
            _, a, b = G.to_oklab(G.slot_colours(BASES, {"skin": h})["front_color"])
            self.assertLessEqual((a * a + b * b) ** 0.5, cf + 1e-3, h)

    def test_details_off_follow_the_skin(self):
        u = G.slot_colours(BASES, {"skin": "#e39c8c", "detail": "#ff0000", "detail_on": False})
        self.assertEqual(u["detail_on"], 0.0)
        u = G.slot_colours(BASES, {"skin": "#e39c8c"})
        self.assertEqual(u["detail_on"], 0.0)
        self.assertEqual(u["gill_mode"], 1.0)  # the gradient, the default
        for mode, v in (("skin", 0.0), ("gradient", 1.0), ("whole", 2.0)):
            self.assertEqual(G.slot_colours(BASES, {"gills": mode})["gill_mode"], v)
        self.assertEqual(G.slot_colours(BASES, {"gills": "whole"})["gill_base"], tuple(BASES["gill_whole"]))
        self.assertEqual(G.slot_colours(BASES, {})["gill_base"], tuple(BASES["gill_tips"]))
        no_gills = {k: v for k, v in BASES.items() if not k.startswith("gill")}
        self.assertEqual(G.slot_colours(no_gills, {})["gill_base"], tuple(BASES["detail"]))

    def test_bases_from_texels(self):
        teal, pale, black = (0.38, 0.8, 0.8), (0.8, 0.88, 0.85), (0.0, 0.0, 0.0)
        tx = [(teal, (0, 0, 0), 0)] * 3 + [(black, (0, 0, 0), 0)] * 5 + [(pale, (0, 0, 255), 0)] * 2 + \
             [((0.3, 0.7, 0.7), (0, 255, 0), 255)] * 2 + [((0.32, 0.72, 0.72), (0, 0, 0), 255)]
        b = G.bases_from_texels(tx)
        self.assertLess(max(abs(p - q) for p, q in zip(b["skin"], teal)), 1e-4)  # the unpainted gaps are no paint
        self.assertLess(max(abs(p - q) for p, q in zip(b["front"], pale)), 1e-4)
        self.assertLess(max(abs(p - q) for p, q in zip(b["gill_tips"], (0.3, 0.7, 0.7))), 1e-4)
        self.assertEqual(b["detail"], b["gill_tips"])  # no detail texel outside the gills: none of its own

    def test_gdscript_constants_match(self):
        src = GD.read_text(encoding="utf-8")
        self.assertIn("const GILL_MODES: PackedStringArray = [" + ", ".join(f'"{m}"' for m in G.GILL_MODES) + "]", src)
        m = re.search(r"const PALETTE: Array\[Color\] = \[(.*?)\]\n", src, re.S).group(1)
        self.assertEqual(len(re.findall(r"Color\(", m)), 4)  # CS6: the curated colours as picked, no guarded copy
        self.assertNotIn("PALETTE_288", src)
        gd = re.findall(r'\{"name": "([^"]+)", "picks": (\{[^}]*\})\}', src)
        self.assertEqual([n for n, _ in gd], [n for n, _ in G.PRESETS])
        for (_, gp), (_, p) in zip(gd, G.PRESETS):
            self.assertEqual(json.loads(gp), p)
        for k in ("gill_tips", "gill_whole"):
            self.assertIn(f'"{k}"', src)
        self.assertIn(f"const FRONT_BAND := {G.FRONT_BAND}", src)
        self.assertIn(f"export const FRONT_BAND = {G.FRONT_BAND};", JS.read_text(encoding="utf-8"))

    def test_presets_unchanged(self):  # CS6: the stored preset colours stay as merged in #304/#306
        self.assertEqual(G.PRESETS[1], ("coral reef", {"skin": "#e39c8c", "lips": "#a2575a", "detail": "#a2575a",
                                                       "detail_on": True}))
        self.assertEqual(G.PRESETS[7][1]["skin"], "#7f98a8")
        self.assertEqual(G.PRESETS[0], ("alien teal", {}))

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

    def test_glsl_matches_the_godot_shader(self):  # the browser's recolour statement by statement as Godot's
        js, gd = JS.read_text(encoding="utf-8"), SHADER.read_text(encoding="utf-8")
        renamed = godot_names(js)
        for head_gd, head_js in (("vec3 recolour(vec3 c, vec3 acc, float gill) {",
                                  "vec3 csRecolour(vec3 c, vec3 acc, float gill) {"),
                                 ("vec3 shift(vec3 x, vec3 b, vec3 t) {", "vec3 csShift(vec3 x, vec3 b, vec3 t) {"),
                                 ("vec3 oklab(vec3 c) {", "vec3 csLab(vec3 c) {"),
                                 ("vec3 oklab_linear(vec3 lab) {", "vec3 csLabLin(vec3 lab) {")):
            want = statements(gd, head_gd)
            got = statements(renamed, godot_names(head_js))
            self.assertEqual(got, want, head_gd)
        self.assertIn("vec3 csU(vec3 c) { return csLab(csLin(c)); }", js)  # three.js's uniforms are the sRGB numbers
        # every colour uniform reaches OKLab only through csU or csLin (sRGB numbers, never taken as linear)
        body = js.split("vec3 csRecolour(vec3 c, vec3 acc, float gill) {", 1)[1].split("\n}", 1)[0]
        colours = [n for n in JS_TO_GODOT.values() if n not in ("oklab", "oklab_linear", "shift")]
        js_names = {v: k for k, v in JS_TO_GODOT.items()}
        for n in colours:
            if n in ("detail_on", "gill_mode"):
                continue
            for m in re.finditer(rf"\b{js_names[n]}\b", body):
                self.assertRegex(body[:m.start()], r"\b(csU|csLin)\($", (n, body[max(0, m.start() - 20):m.end()]))
        self.assertIn("uniform vec3 gill_base : source_color", gd)  # Godot's are linear (source_color)
        flat = re.sub(r"\s+", "", js.split("export const MAP_FRAGMENT", 1)[1].split("`;", 1)[0])
        self.assertIn("vec4sampledDiffuseColor=texture2D(map,vMapUv);vec3csA=sampledDiffuseColor.rgb;"
                      "sampledDiffuseColor.rgb=mix(csA,csRecolour(csA,texture2D(csAccent,vMapUv).rgb,"
                      "texture2D(csGill,vMapUv).r),texture2D(csMask,vMapUv).r);diffuseColor*=sampledDiffuseColor;", flat)
        g = re.sub(r"\s+", "", gd)
        self.assertIn("vec3a=texture(albedo_tex,UV).rgb;", g)
        self.assertIn("vec3m=texture(mask_tex,UV).rgb;", g)
        self.assertIn("vec3c=mix(a,recolour(a,texture(accent_tex,UV).rgb,texture(gill_tex,UV).r),m.r);", g)
        self.assertNotIn(".a", "".join(statements(gd, "vec3 recolour(vec3 c, vec3 acc, float gill) {")))

    def test_js_matches(self):
        src = JS.read_text(encoding="utf-8")
        js = re.findall(r'\["([^"]+)", (\{[^}]*\})\]', src.split("export const PRESETS")[1].split("];")[0])
        self.assertEqual([n for n, _ in js], [n for n, _ in G.PRESETS])
        for (_, jp), (_, p) in zip(js, G.PRESETS):
            jp = json.loads(re.sub(r"(\w+):", r'"\1":', jp))
            self.assertEqual({("detail_on" if k == "detailOn" else k): v for k, v in jp.items()}, p)
        self.assertIn("export const GILL_MODES = [" + ", ".join(f'"{m}"' for m in G.GILL_MODES) + "]", src)
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        no_gills = {k: v for k, v in BASES.items() if not k.startswith("gill")}
        picks = [p for _, p in G.PRESETS] + [{"skin": h, "lips": h, "detail": h} for h in PICKS] + [
            {"skin": h} for h in PICKS] + [
            {"skin": "#e39c8c", "detail": "#ff0000", "detail_on": False, "gills": "skin"},
            {"skin": "#14206e", "lips": "#ffffff", "gills": "whole"}, {"skin": "#0000ff", "lips": "#0000ff"},
            {"gills": "fringe"}, {"front": "pale"}] + [{"skin": h, "front": "follow"} for h in PICKS] + [
            {"skin": h, "front": "keep"} for h in ("#ffffff", "#f0f0f0", "#d8e8e0", "#000000", "#e8e8e8", "#eeeeee",
                                                    "#f4f4f4", "#e8f0ff")]  # CS6c: inside the band too
        jpicks = [{("detailOn" if k == "detail_on" else k): v for k, v in p.items()} for p in picks]
        for bases in (BASES, no_gills, HEADS["chameleon"]):
            out = subprocess.run([node, str(JS), "--json", json.dumps({"bases": bases, "picks": jpicks})],
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            for p, got in zip(picks, json.loads(out.stdout)):
                if p.get("gills") == "fringe":  # an unknown gill mode: an error in JS as in Python
                    self.assertIn("unknown gills", got.get("error", ""))
                    continue
                if p.get("front") == "pale":
                    self.assertIn("unknown front", got.get("error", ""))
                    continue
                want = G.slot_colours(bases, p)
                self.assertEqual(sorted(want), sorted(got), p)
                for k, v in want.items():
                    for x, y in zip(v if isinstance(v, tuple) else (v,),
                                    got[k] if isinstance(got[k], list) else [got[k]]):
                        self.assertAlmostEqual(x, y, delta=1e-6, msg=(p, k))


if __name__ == "__main__":
    unittest.main()
