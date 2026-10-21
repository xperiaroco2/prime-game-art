"""M11 (art #196, brief UPDATE 21): the upper lashes' plain geometry (tools/blender/alien_lashes_geom.py) and their
wiring in alien_lashes.py and godot/alien/alien.gd (read by pattern: the step needs Blender)."""
from __future__ import annotations

import importlib.util
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = ROOT / "tools" / "blender"
sys.path.insert(0, str(BLENDER))  # alien_lashes_geom imports alien_lids_geom
spec = importlib.util.spec_from_file_location("alien_lashes_geom", BLENDER / "alien_lashes_geom.py")
LL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LL)
import alien_lids_geom as LG  # noqa: E402

RHO, BEAD = (1.06, 1.13), 0.10  # bored's upper lid (alien_parts.EYES, LID_BEAD), S9's shells


def build(side=1.0, **kw):
    return LL.build(LL.merged(kw), RHO[0], RHO[1], BEAD, LG.CORNER, side)


class Geometry(unittest.TestCase):
    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(ValueError):
            LL.merged({"lenght_out": 0.6})

    def test_m15s_socket_has_its_own_defaults_under_the_spec(self):  # M15b
        self.assertEqual(LL.merged(), LL.LASHES)  # older kits (no route) build as before
        m15 = LL.merged(route="m15")
        self.assertEqual((m15["liner_t_in_deg"], m15["sink"]), (-42.0, 0.003))  # M17c: bored's liner as M15b's
        self.assertEqual({k: v for k, v in m15.items() if k not in ("liner_t_in_deg", "sink", "design")},
                         {k: v for k, v in LL.LASHES.items() if k not in ("liner_t_in_deg", "sink", "design")})
        self.assertEqual(LL.merged({"sink": 0.005}, "m15")["sink"], 0.005)  # an explicit spec still wins
        self.assertEqual(LL.merged(route="other"), LL.LASHES)
        for over in LL.SOCKET_LASHES.values():
            self.assertFalse(set(over) - set(LL.LASHES))

    def test_m17c_manic_has_its_own_liner_end_on_m15s_socket(self):
        """M17c (PR #259's review): on the 108 % unit bored keeps -42, manic ends shorter (its lid rests 50 degrees up,
        so the liner's inner end met the brow's skin); merged() is shallow, so the socket's "design" carries manic's
        whole entry: its lift, lean and last lash stay LASHES'."""
        m15 = LL.merged(route="m15")
        bored, manic = LL.for_design(m15, "bored"), LL.for_design(m15, "manic")
        self.assertEqual(bored["liner_t_in_deg"], -42.0)
        self.assertEqual(manic["liner_t_in_deg"], LL.MANIC_LINER_T_IN_DEG)
        self.assertEqual((bored["liner"], manic["liner"]), (LL.LASHES["liner"], LL.MANIC_LINER))  # one line at 3.5 m
        self.assertGreater(LL.MANIC_LINER_T_IN_DEG, -42.0)  # shorter than bored's ...
        self.assertLess(LL.MANIC_LINER_T_IN_DEG, -20.0)  # ... and longer than M17b's -20
        for k, v in LL.LASHES["design"]["manic"].items():
            self.assertEqual(manic[k], v)
        self.assertEqual(manic["lift_deg"], -30.0)
        self.assertEqual(LL.for_design(LL.merged(), "manic")["liner_t_in_deg"], LL.LASHES["liner_t_in_deg"])
        self.assertFalse(set(m15["design"]["manic"]) - set(LL.LASHES))

    def test_the_rim_point_lies_on_the_lid_roll(self):
        pt, n, p, hw = LL.rim(0.0, 0.0, RHO[0], RHO[1], BEAD, LG.CORNER)
        self.assertAlmostEqual(math.dist(pt, (0, 0, 0)), RHO[1] + BEAD, places=9)  # a=0: the roll's outer side
        self.assertAlmostEqual(p, 0.0, places=9)
        front = LL.rim(0.0, math.pi / 2, RHO[0], RHO[1], BEAD, LG.CORNER)
        self.assertLess(front[2], 0.0)  # the front edge reaches past the lid's edge (below elevation 0)
        self.assertAlmostEqual(math.hypot(*n), 1.0, places=9)

    def test_lashes_stand_off_the_dome_and_curl_up(self):
        v, f, rep = build()
        u = rep["u"]
        self.assertEqual(len(u), len(v))
        for p, uu in zip(v, u):
            if uu > 0.15:  # past the sunk root
                self.assertGreater(math.dist(p, (0, 0, 0)), RHO[1])  # never inside the lid or the ball
        sides = LL.LASHES["sides"]
        ring = sides * (LL.LASHES["seg"] + 1) + 2
        for i, lash in enumerate(rep["lashes"]):
            root = v[i * ring]
            tip = lash["tip"]
            self.assertGreater(tip[2], root[2])  # up the lid (+Z at the edge)

    def test_longer_and_winged_toward_the_temple(self):
        _, _, rep = build()
        ls = rep["lashes"]
        self.assertLess(ls[0]["len_r"], ls[-1]["len_r"])
        self.assertLess(ls[0]["width_r"], ls[-1]["width_r"])
        self.assertGreaterEqual(ls[0]["t_deg"], 0.0)  # el2: the lashes on the outer half
        v, _, rep2 = build()
        self.assertTrue(any(p[0] < 0.0 for p, uu in zip(v, rep2["u"]) if uu < 0.0))  # the liner runs to the nose side
        self.assertGreater(ls[-1]["t_deg"], 45.0)
        self.assertEqual(sum(1 for x in ls if x["wing"] > 0), LL.LASHES["wing"])
        self.assertGreater(ls[-1]["tip"][0], math.sin(math.radians(ls[-1]["t_deg"])) * (RHO[1] + BEAD))  # out past it
        gaps = [b["t_deg"] - a["t_deg"] for a, b in zip(ls, ls[1:])]
        self.assertGreater(gaps[0], gaps[-1])  # closer together toward the outer corner

    def test_the_right_eye_is_the_mirror(self):
        vl, fl, _ = build(1.0)
        vr, fr, _ = build(-1.0)
        for a, b in zip(vl, vr):
            self.assertEqual((-a[0], a[1], a[2]), b)
        self.assertEqual(tuple(reversed(fl[0])), fr[0])  # the winding reversed: the normals stay outward

    def test_the_liner_hugs_the_roll(self):
        v, _, rep = build()
        liner = [p for p, uu in zip(v, rep["u"]) if uu < 0.0]
        self.assertEqual(len(liner), rep["liner_verts"])
        for p in liner:
            d = math.dist(p, (0, 0, 0))
            self.assertGreater(d, RHO[0] - 0.01)
            self.assertLess(d, RHO[1] + BEAD + LL.LASHES["liner"] + 1e-9)
        _, _, none = build(liner=0.0)
        self.assertNotIn("liner_verts", none)

    def test_the_liner_swells_toward_the_temple(self):
        def thick(**kw):  # the liner's greatest reach off the roll's outer radius, nose half and temple half
            v, _, rep = build(**kw)
            pts = [p for p, uu in zip(v, rep["u"]) if uu < 0.0]
            nose = max(math.dist(p, (0, 0, 0)) for p in pts if p[0] < -0.5)
            temple = max(math.dist(p, (0, 0, 0)) for p in pts if p[0] > 0.6)
            return nose, temple
        even, swell = thick(liner=0.05, liner_out=1.0), thick(liner=0.05, liner_out=2.0)
        self.assertGreater(swell[1] - even[1], 3.0 * (swell[0] - even[0]))  # the swell sits at the temple end
        self.assertGreater(swell[1], even[1] + 0.01)

    def test_split_cuts_the_tubes_from_the_liner(self):
        v, f, rep = build()
        parts = LL.split(v, f, rep["u"])
        self.assertEqual(len(parts["lashes"][0]) + len(parts["liner"][0]), len(v))
        self.assertEqual(len(parts["lashes"][1]) + len(parts["liner"][1]), len(f))
        self.assertEqual(len(parts["liner"][0]), rep["liner_verts"])
        for vs, fs in parts.values():
            self.assertTrue(all(0 <= i < len(vs) for fc in fs for i in fc))
        none = build(liner=0.0)
        self.assertEqual(LL.split(*none[:2], none[2]["u"])["liner"], ([], []))


class Wiring(unittest.TestCase):
    src = (BLENDER / "alien_lashes.py").read_text(encoding="utf-8")
    gd = (ROOT / "godot" / "alien" / "alien.gd").read_text(encoding="utf-8")

    def test_the_socket_route_picks_the_defaults(self):  # M15b: the grid's variants too
        main = self.src[self.src.index("def main("):]
        self.assertIn("route = socket_route()", main)
        self.assertIn("LL.merged(json.loads(a.lashes) if a.lashes else None, route)", main)
        self.assertIn("LL.merged(vs, route)", main)

    def test_a_child_of_the_upper_lid_named_for_its_design(self):
        name = re.search(r'NAME = "([^"]+)"', self.src).group(1)
        self.assertTrue(name.startswith("eye_{d}_"))  # hidden with the parts by the gate; shown with its design
        self.assertNotIn("_lid_", name)  # alien.gd would give a _lid_ surface the lids' coral
        build = self.src[self.src.index("def _mesh_object"):self.src.index("def inside_count")]
        self.assertIn("ob.parent = lid", build)
        self.assertIn("ob.matrix_basis = Matrix.Identity(4)", build)
        self.assertIn('lid.name.replace("_lid_upper_", "_ball_")', build)  # sized on the ball's radius

    def test_the_liner_is_its_own_node_beside_the_tubes(self):
        liner = re.search(r'LINER_NAME = "([^"]+)"', self.src).group(1)
        self.assertEqual(liner, "eye_{d}_liner_{s}")
        self.assertNotIn("_lid_", liner)
        build = self.src[self.src.index("def make_set"):self.src.index("def inside_count")]
        self.assertIn("parts = LL.split(verts, faces, u)", build)
        self.assertIn('_mesh_object(liner_name, *parts["liner"]', build)

    def test_the_material_is_one_sided(self):
        mat = self.src[self.src.index("def lash_material"):self.src.index("def remove_old")]
        self.assertIn("mat.use_backface_culling = True", mat)  # the glTF exporter: doubleSided false

    def test_edges_and_a_touch_count_as_a_clip(self):
        clip = self.src[self.src.index("def clipping"):self.src.index("def main(")]
        for k in ("skin_edges", "ball_edges", "lower_edges", 'x["skin_least_mm"] < CLEAR_MM'):
            self.assertIn(k, clip)
        self.assertGreater(float(re.search(r"CLEAR_MM = ([0-9.]+)", self.src).group(1)), 0.0)
        main = self.src[self.src.index("def main("):]
        self.assertIn("any(clipping(x) for x in v.values())", main)

    def test_alien_gd_fades_the_tubes_and_keeps_the_liner(self):
        fade = float(re.search(r"const LASH_FADE_M := ([0-9.]+)", self.gd).group(1))
        margin = float(re.search(r"const LASH_FADE_MARGIN_M := ([0-9.]+)", self.gd).group(1))
        self.assertLessEqual(fade, 3.5)  # gone at the game's 3.5 m
        self.assertGreater(fade - margin, 1.2)  # whole at the 1.2 m view
        setup = self.gd[self.gd.index("func setup("):self.gd.index("func _textured_material(")]
        lashes = setup[setup.index('m.name.contains("_lashes_")'):]
        self.assertIn("lash_fade(m)", lashes[:200])
        liner = setup[setup.index('m.name.contains("_liner_")'):]
        self.assertNotIn("lash_fade", liner[:200])
        self.assertIn("VISIBILITY_RANGE_FADE_SELF", self.gd)

    def test_the_liner_keeps_a_least_screen_width_and_casts_no_shadow(self):
        sh = (ROOT / "godot" / "alien" / "alien_liner.gdshader").read_text(encoding="utf-8")
        self.assertIn("render_mode cull_back;", sh)
        self.assertIn("float grow = clamp((min_px * px - band_m) * grow_share, 0.0, max_grow_m);", sh)
        self.assertIn("VERTEX += NORMAL * grow", sh)
        self.assertIn('const LINER_SHADER: Shader = preload("res://alien/alien_liner.gdshader")', self.gd)
        setup = self.gd[self.gd.index("func setup("):self.gd.index("func _textured_material(")]
        liner = setup[setup.index('m.name.contains("_liner_"):  # M11b: the lash line'):]
        self.assertIn("m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF", liner[:300])
        self.assertIn('key = "alien_lash_liner"', setup)
        self.assertIn('_face_materials["alien_lash_liner"] = liner', self.gd)
        self.assertGreaterEqual(float(re.search(r"const LINER_MIN_PX := ([0-9.]+)", self.gd).group(1)), 1.5)

    def test_the_kit_is_refused_when_a_lash_clips(self):
        main = self.src[self.src.index("def main("):]
        self.assertIn("rep[\"clip\"] = clip_check(sets)", main)
        self.assertIn("if bad and not a.allow_clip:", main)
        self.assertLess(main.index("if bad and not a.allow_clip:"), main.index("export_scene.gltf"))
        self.assertEqual(re.search(r"STATES = (\([^)]*\))", self.src).group(1), '("open", "rest", "half", "closed")')

    def test_alien_gd_toggles_them_off_by_default(self):
        self.assertIn("var lashes: bool = false", self.gd)
        self.assertIn("func set_lashes(on: bool) -> void:", self.gd)
        self.assertIn('m.name.begins_with("eye_") and m.name.contains("_lashes_")', self.gd)
        self.assertIn('or mat.resource_name == "alien_lash"', self.gd)
        self.assertIn('_face_materials["alien_lash"] = lash', self.gd)
        setup = self.gd[self.gd.index("func setup("):self.gd.index("func _textured_material(")]
        self.assertIn("set_lashes(lashes)", setup)


if __name__ == "__main__":
    unittest.main()
