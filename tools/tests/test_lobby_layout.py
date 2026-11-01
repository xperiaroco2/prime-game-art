"""The lobby hall's layout check (art #356, docs/lobby.md): plain Python, no Blender, no Godot. The ship's footprint
comes from the hull's outline (ship_hull_shape, plain Python) and a fixture of art #263's build report (the pods' and
the tail's bounds as built in ship/v5); a last test reads the real report when the raw folder has it."""

from __future__ import annotations

import copy
import math
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, lobby_layout  # noqa: E402

# ship/v5's build report, the bounds the footprint reads (Godot frame (x, h, y) at each piece's origin)
REPORT = {"nozzle_pod_outer": {"bounds": {"min": [-1.4626, -0.8626, 0.0], "max": [1.4626, 2.0626, 5.065]}},
          "nozzle_pod_mid": {"bounds": {"min": [-1.6686, -1.0686, 0.0], "max": [1.6686, 2.2686, 5.365]}},
          "skin_top": {"bounds": {"min": [-13.0555, 1.5124, -7.1], "max": [13.0555, 5.42, 12.7]}}}
PLACE = [["nozzle_pod_outer", [-3.0, 9.6, 2.0], 0.0], ["nozzle_pod_outer", [3.0, 9.6, 2.0], 0.0],
         ["nozzle_pod_mid", [0.0, 9.6, 2.55], 0.0]]


class LobbyLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.layout = lobby_layout.load()
        cls.outline = lobby_layout.hull_outline(cls.layout["ship"]["hull"])

    def fp(self, layout: dict) -> list:
        return lobby_layout.footprint(layout, self.outline, REPORT, PLACE)

    def test_accepts_the_layout(self) -> None:
        self.assertEqual(lobby_layout.check(self.layout, self.fp(self.layout)), [])

    def test_the_engineers_numbers(self) -> None:
        # step 5a (the engineer, art#356 comment 6536044954): the origin 2.5 m toward the window, the spawns with it
        self.assertEqual(self.layout["ship"]["origin"], [0.0, 0.0, -14.5])
        self.assertEqual(self.layout["floor"]["spawns_z"], 2.5)
        n = lobby_layout.ship_numbers(self.layout, self.fp(self.layout))
        self.assertAlmostEqual(n["nose_z"], -21.6, places=2)
        self.assertAlmostEqual(n["aft_z"], 0.46, delta=0.01)
        self.assertAlmostEqual(n["middle_z"], -10.57, delta=0.01)
        r, cz = lobby_layout.arc(self.layout)
        self.assertAlmostEqual(lobby_layout.arc_z(self.layout, 0.0), 16.0)
        self.assertAlmostEqual(lobby_layout.arc_z(self.layout, 20.0), 10.0)
        self.assertAlmostEqual(r, 36.333, places=3)

    def test_refuses_a_ship_on_the_spawns(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["ship"]["origin"] = [0.0, 0.0, -12.0]   # 2.5 m further south: the pods end at z +2.96, past the spawns
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("spawn x") and "from the ship" in p for p in problems), problems)

    def test_refuses_a_ship_near_a_wall(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["ship"]["origin"] = [5.0, 0.0, -14.5]
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("ship:") and "from E" in p for p in problems), problems)

    def test_refuses_a_door_on_a_pilaster(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["door"]["doors"][0] = ["D1", "W", 0.0]   # on the pilaster under the rib at z 0
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("D1: on the pilaster") for p in problems), problems)

    def test_refuses_the_drawings_wide_pilaster(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["hall"]["pilaster_w"] = 1.2   # the drawing's glyph: 0.1 m into D1 and D2
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p.startswith("D1: on the pilaster at 0.0") for p in problems), problems)

    def test_refuses_a_door_on_the_arch_and_a_corner(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["door"]["doors"][2] = ["D3", "N", -3.0]
        layout["door"]["doors"][3] = ["D4", "N", 19.5]
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any(p == "D3: on the arch" for p in problems), problems)
        self.assertTrue(any(p.startswith("D4: within") for p in problems), problems)

    def test_refuses_a_walk_point_under_the_ship(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["walk"]["points"] = [*layout["walk"]["points"], [0.0, -13.0]]
        problems = lobby_layout.check(layout, self.fp(layout))
        self.assertTrue(any("under the ship" in p for p in problems), problems)

    def test_refuses_a_placement_without_a_piece(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["place"].append(["balcony", [0.0, 0.0, 0.0], 0.0])
        self.assertIn("place: no piece 'balcony'", lobby_layout.check(layout, self.fp(layout)))

    def test_refuses_an_unknown_look_scheme(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["look"]["scheme"] = "S9"
        self.assertTrue(any("scheme S9" in p for p in lobby_layout.check(layout)))

    def test_refuses_a_bad_scheme_colour_material_and_grid_view(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["look"]["schemes"]["S2"]["accent"] = [0.3, 1.4, 0.2]
        layout["look"]["mats"]["lobby_panel"] = ["wallpaper", 1.0, 0.5, 0.0]
        layout["review"]["grid"] = ["corner_nw", "nowhere"]
        problems = lobby_layout.check(layout)
        self.assertTrue(any("look S2: accent" in p for p in problems), problems)
        self.assertTrue(any("material lobby_panel" in p for p in problems), problems)
        self.assertTrue(any("grid: nowhere" in p for p in problems), problems)

    def test_the_earth(self) -> None:
        """Step 3b: three variants (E2 by default since step 4, the engineer's pick), NASA's three maps at most 4096 x 2048, the grid's two views."""
        e = self.layout["earth"]
        self.assertEqual(e["variant"], "E2")
        self.assertEqual(sorted(e["variants"]), ["E1", "E2", "E3"])
        self.assertEqual(sorted(e["maps"]), ["clouds", "day", "night"])
        self.assertEqual(e["size"], [4096, 2048])
        self.assertEqual(e["grid"], ["spawn_eye", "corner_nw"])
        self.assertEqual(e["credit"], "Earth imagery: NASA")
        v = e["variants"]
        self.assertGreater(v["E1"]["radius_deg"], 3 * v["E3"]["radius_deg"])   # E1 huge, E3 a smaller disc
        self.assertEqual(v["E1"]["sun_energy"], 0.0)                             # E1: full night
        self.assertGreater(v["E2"]["sun_energy"], 0.0)                           # E2: the dawn
        self.assertGreater(v["E3"]["stars"], v["E1"]["stars"])                   # E3: more stars

    def test_the_earths_cap(self) -> None:
        """Step 5a4: the cap covers E2's subpoint and the 42 deg seen round it from D2, at Black Marble's resolution."""
        e = self.layout["earth"]
        cap = e["cap"]
        lat, lon = e["variants"]["E2"]["subpoint"]
        self.assertLessEqual(cap["lat"][0], lat - 42.0)
        self.assertGreaterEqual(cap["lat"][1], lat + 42.0)
        self.assertLessEqual(cap["lon"][0], lon - 56.0)    # 42 deg round [36, 12] spans 56 deg of longitude
        self.assertGreaterEqual(cap["lon"][1], lon + 56.0)
        nw = cap["maps"]["night"][0] / (cap["lon"][1] - cap["lon"][0])
        self.assertGreater(nw, 2.5 * e["size"][0] / 360.0)   # 2.5 times the global map's px a degree at least
        bad = copy.deepcopy(self.layout)
        bad["earth"]["cap"]["maps"]["night"] = [4096, 1024]
        bad["earth"]["cap"]["lat"] = [50.0, 40.0]
        problems = lobby_layout.check(bad)
        self.assertTrue(any("earth cap: lat" in p for p in problems), problems)

    def test_corner_nw_sees_the_cap(self) -> None:
        """Step 5a5's debug: the window's crop in corner_nw (x1180-1500, y360-590 at 1920 x 1080) sees the globe at about
        lat 43-61, lon -6..24 (Europe, head-on enough: mu 0.35-0.88), inside the cap, as the shader's debug paint showed;
        traced as earth_object.gdshader does (D2, E2's map frame)."""
        e, o = self.layout["earth"], lobby_layout.earth_object(self.layout, "E2", "D2")
        c, r, f = o["centre"], o["radius_m"], o["frame_dir"]
        sub = lambda a, b: [x - y for x, y in zip(a, b)]
        dot = lambda a, b: sum(x * y for x, y in zip(a, b))
        unit = lambda a: [x / math.sqrt(dot(a, a)) for x in a]
        cross = lambda a, b: [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
        comb = lambda *ps: [sum(k * v[i] for k, v in ps) for i in range(3)]
        p0, l0 = (math.radians(a) for a in e["variants"]["E2"]["subpoint"])
        s = [math.cos(p0) * math.cos(l0), math.sin(p0), -math.cos(p0) * math.sin(l0)]
        east, north = [-math.sin(l0), 0.0, -math.cos(l0)], [-math.sin(p0) * math.cos(l0), math.cos(p0), math.sin(p0) * math.sin(l0)]
        u0 = unit(sub([0.0, 1.0, 0.0], [x * f[1] for x in f]))
        r0 = unit(cross([-x for x in f], u0))
        view = next(v for v in self.layout["review"]["views"] if v[0] == "corner_nw")
        eye, fw = view[2], unit(sub(view[3], view[2]))
        rt = unit(cross(fw, [0.0, 1.0, 0.0]))
        up, t = cross(rt, fw), math.tan(math.radians(view[4]) / 2)
        cap = e["cap"]
        for px in (1180, 1340, 1500):
            for py in (360, 475, 590):
                v = unit(comb((1.0, fw), ((2 * px / 1920 - 1) * t * 1920 / 1080, rt), ((1 - 2 * py / 1080) * t, up)))
                oc = sub(c, eye)
                b = dot(v, oc)
                disc = b * b - (dot(oc, oc) - r * r)
                self.assertGreater(disc, 0.0, (px, py))   # the ray hits the globe
                n = unit(sub(comb((1.0, eye), (b - math.sqrt(disc), v)), c))
                g = unit(comb((dot(n, r0), east), (dot(n, u0), north), (dot(n, f), s)))
                lat, lon = math.degrees(math.asin(g[1])), math.degrees(math.atan2(-g[2], g[0]))
                self.assertTrue(cap["lat"][0] + cap["fade_deg"] < lat < cap["lat"][1] - cap["fade_deg"], (px, py, lat))
                self.assertTrue(cap["lon"][0] + cap["fade_deg"] < lon < cap["lon"][1] - cap["fade_deg"], (px, py, lon))
                self.assertTrue(40.0 < lat < 64.0 and -10.0 < lon < 28.0, (px, py, lat, lon))

    def test_the_night_look(self) -> None:
        """Step 5a5: every [earth.look] key the Earth object takes is a uniform of earth_object.gdshader; the new
        uniforms' defaults draw step 5a4's look; the layout's night: dark clouds, cities capped and as points."""
        src = (Path(__file__).resolve().parents[2] / "godot" / "lobby" / "earth_object.gdshader").read_text(encoding="utf-8")
        look = self.layout["earth"]["look"]
        for k in look:
            if not k.startswith(("glass_", "stars")):
                self.assertIsNotNone(re.search(rf"uniform (float|vec3) {k} ", src), k)
        for k, v in {"light_cap": "1000.0", "halo_energy": "0.0", "cloud_city": "0.0", "cloud_shade": "0.5",
                     "haze_energy": "0.0", "moon_knee": "0.0", "debug_mode": "0.0", "snow_cut": "0.0",
                     "moon_land": "0.0"}.items():
            self.assertIn(f"uniform float {k} = {v};", src)
        self.assertLess(look["cloud_energy"], 0.1)
        self.assertGreater(look["city_gamma"], 1.8)
        self.assertTrue(1.0 < look["light_cap"] < 4.0)
        self.assertLess(look["haze_energy"], 0.1)

    def test_the_snow_sets(self) -> None:
        """Step 5a6: three snow strengths, each only snow keys over [earth.look] (uniforms of earth_object.gdshader), the
        snow cut harder from N1 to N3, N3 with the land's moonlight almost off; N2 the default."""
        from runner.commands import lobby as cmd
        src = (Path(__file__).resolve().parents[2] / "godot" / "lobby" / "earth_object.gdshader").read_text(encoding="utf-8")
        sn = self.layout["earth"]["snow"]
        self.assertEqual(list(sn["sets"]), ["N1", "N2", "N3"])
        self.assertEqual(sn["set"], "N2")
        self.assertEqual(sn["grid"], ["corner_nw", "a_entrance", "spawn_eye"])
        views = [v[0] for v in self.layout["review"]["views"]]
        self.assertTrue(all(g in views for g in sn["grid"]))
        cuts = []
        for sid, s in sn["sets"].items():
            self.assertLessEqual(set(s["look"]), {"snow_cut", "moon_land", "moon_knee"}, sid)
            for k in s["look"]:
                self.assertIsNotNone(re.search(rf"uniform float {k} ", src), k)
            cuts.append(s["look"]["snow_cut"])
            look = cmd.earth_look(self.layout, sid)
            self.assertEqual({k: v for k, v in look.items() if k not in s["look"]},
                             {k: v for k, v in self.layout["earth"]["look"].items() if k not in s["look"]})
        self.assertEqual(cuts, sorted(cuts))
        self.assertTrue(0.0 < cuts[0] and cuts[-1] <= 1.0)
        self.assertGreater(sn["sets"]["N3"]["look"]["moon_land"], 0.5)
        self.assertEqual(cmd.earth_look(self.layout), cmd.earth_look(self.layout, "N2"))

    def test_e2s_sun_is_just_behind_the_limb(self) -> None:
        from runner.commands import lobby as cmd
        v = self.layout["earth"]["variants"]["E2"]
        c, s = cmd._dir(*v["centre"]), cmd._dir(*v["sun"])
        import math
        ang = math.degrees(math.acos(sum(a * b for a, b in zip(c, s))))
        self.assertLess(ang, v["radius_deg"])            # hidden by the planet
        self.assertGreater(ang, v["radius_deg"] - 4.0)   # but just below the limb

    def test_refuses_a_bad_earth(self) -> None:
        layout = copy.deepcopy(self.layout)
        layout["earth"]["variant"] = "E9"
        layout["earth"]["size"] = [8192, 4096]
        layout["earth"]["grid"] = ["spawn_eye", "nowhere"]
        layout["earth"]["variants"]["E3"]["radius_deg"] = 95.0
        layout["earth"]["variants"]["E2"]["subpoint"] = [120.0, 0.0]
        problems = lobby_layout.check(layout)
        for want in ("variant E9", "size 8192", "earth grid: nowhere", "E3: radius_deg", "E2: subpoint"):
            self.assertTrue(any(want in p for p in problems), (want, problems))

    def test_closeups_and_the_grey_teal(self) -> None:
        close = self.layout["review"]["closeups"]
        self.assertGreaterEqual(len(close), 9)   # step 2c: one close-up per fix at least
        layout = copy.deepcopy(self.layout)
        layout["review"]["closeups"][0][2] = [0.0, 1.7, 60.0]
        self.assertTrue(any(f"view {close[0][0]}" in p for p in lobby_layout.check(layout)))
        s4 = self.layout["look"]["schemes"]["S4"]
        for role in ("panel", "frame", "floor"):   # the teal stays on the grey side
            self.assertLess(max(s4[role]) - min(s4[role]), 0.1, role)
        self.assertGreater(min(s4["frame"]), 0.2)   # the frames a mid value, clearly lighter than black

    def test_less_copper_and_a_lighter_ceiling(self) -> None:
        """Step 3: the engineer's notes on 2c: a dark metal for the frames, the copper desaturated, the vault lighter."""
        self.assertEqual(self.layout["raw_dir"], "lobby/hall/v18")   # #366 c (#366: v17, step 5c: v16)
        mats = lobby_layout.look_materials(self.layout, "S4")
        metal, pil = mats["lobby_metal"]["rgb"], mats["lobby_pilaster"]["rgb"]
        self.assertLess(max(metal), max(pil))   # the frames' metal darker than the pilasters' shaft, same hue
        self.assertLess(max(metal) - min(metal), 0.06)
        cu = self.layout["look"]["schemes"]["S4"]["trim"]
        self.assertLess(max(cu) - min(cu), 0.35)   # desaturated (2c: 0.74 - 0.28 = 0.46)
        self.assertGreater(mats["lobby_vault"]["rgb"][0], 0.42)   # 2c: 0.392
        self.assertGreater(mats["lobby_floor_worn"]["roughness"], mats["lobby_floor"]["roughness"])

    def test_six_schemes_resolve_with_fixed_hazard_and_lamps(self) -> None:
        look = self.layout["look"]
        self.assertEqual(sorted(look["schemes"]), ["S1", "S2", "S3", "S4", "S5", "S6"])
        self.assertEqual(look["scheme"], "S4")   # the engineer's pick (step 2c)
        for sid in look["schemes"]:
            mats = lobby_layout.look_materials(self.layout, sid)
            self.assertNotIn("lobby_hazard", mats)   # yellow-black and red in every scheme: fixed in the builder
            self.assertNotIn("lobby_lamp", mats)
            self.assertGreater(mats["lobby_strip"]["emit"], 0.0)
            self.assertEqual(mats["lobby_strip"]["metallic"], 0.0)
            self.assertLessEqual(mats["lobby_floor"]["roughness"], 0.2)
            self.assertTrue(all(0.0 <= c <= 1.0 for m in mats.values() for c in m["rgb"]))
        s1 = lobby_layout.look_materials(self.layout, "S1")
        self.assertNotEqual(s1["lobby_panel"]["rgb"], s1["lobby_pilaster"]["rgb"])   # a scheme, not one metal

    def test_the_light_moods(self) -> None:
        """Step 4: three moods with the same keys, L2 darker and L3 brighter than L1, the rig's lamps; step 4b: L3 (the
        engineer's pick) by default."""
        li = self.layout["light"]
        self.assertEqual(li["mood"], "L3")
        self.assertEqual(sorted(li["moods"]), ["L1", "L2", "L3"])
        self.assertEqual(li["grid"], ["corner_nw", "spawn_eye", "c_back"])
        m = li["moods"]
        self.assertLess(m["L2"]["ambient_energy"], m["L1"]["ambient_energy"])
        self.assertLess(m["L1"]["ambient_energy"], m["L3"]["ambient_energy"])
        self.assertLess(m["L2"]["pendant_angle"], m["L3"]["pendant_angle"])   # L2's pools tighter
        for mood in m.values():
            self.assertGreater(mood["pendant_rgb"][0], mood["pendant_rgb"][2])   # the pendants warm
            self.assertGreater(mood["earth_rgb"][2], mood["earth_rgb"][0])       # the Earth's light cold
            self.assertGreater(mood["door_rgb"][0], 10 * mood["door_rgb"][1])    # the door lamps red
        from runner.commands import lobby as cmd
        rig = cmd.light_request(self.layout, "L1")["light"]
        self.assertEqual(len(rig["pendants"]), 9)
        self.assertEqual(len(rig["strips"]), 16)   # 6 + 6 side pilasters, 4 on the north wall
        self.assertEqual(len(rig["doors"]), 4)
        for x, y, z in rig["strips"] + rig["doors"]:
            self.assertTrue(lobby_layout.in_hall(self.layout, x, z, 0.2), (x, z))
        self.assertGreater(rig["earth_dir"][2], 0.9)   # toward the Earth: the window's side (+z)

    def test_the_step_4b_fixes(self) -> None:
        """Step 4b in L3: the ship's glow scaled down on the hall's side and the glow's threshold over 1, the vault's
        upward fill, longer strip streaks (more specular, no light size: a disc), a blurred, lighter Earth shadow, wider red door lamps, the window's cold spill;
        L1 and L2 keep step 4's look (the new lights off, the ship as built)."""
        m = self.layout["light"]["moods"]
        l3 = m["L3"]
        self.assertLess(l3["ship_emit"], 1.0)
        self.assertGreater(l3["glow_threshold"], 1.0)
        self.assertEqual(l3["glow_bloom"], 0.0)
        self.assertGreater(l3["fill_energy"], 0.0)
        self.assertGreater(l3["fill_rgb"][0], l3["fill_rgb"][2])     # the fill warm
        self.assertGreater(l3["window_rgb"][2], l3["window_rgb"][0])  # the spill cold
        self.assertGreater(l3["window_energy"], 0.0)
        self.assertGreater(l3["strip_specular"], m["L1"]["strip_specular"])
        self.assertLess(l3["pendant_specular"], m["L1"]["pendant_specular"])
        self.assertGreater(l3["earth_soft"], m["L1"]["earth_soft"])
        self.assertLess(l3["earth_shadow"], 1.0)
        self.assertGreater(l3["door_range"], m["L1"]["door_range"])
        for mid in ("L1", "L2"):
            self.assertEqual((m[mid]["fill_energy"], m[mid]["window_energy"], m[mid]["ship_emit"]), (0.0, 0.0, 1.0))
        from runner.commands import lobby as cmd
        rig = cmd.light_request(self.layout, "L3")["light"]
        self.assertEqual(len(rig["window"]), 3)
        for x, y, z in rig["window"]:
            self.assertTrue(lobby_layout.on_floor(self.layout, x, z), (x, z))
        for tid in self.layout["light"].get("trials", {}):
            self.assertEqual(cmd.light_request(self.layout, "L3", tid)["id"], tid)

    def test_the_light_check(self) -> None:
        bad = copy.deepcopy(self.layout)
        bad["light"]["mood"] = "L9"
        bad["light"]["moods"]["L2"]["pendant_angle"] = 80.0
        del bad["light"]["moods"]["L3"]["glow_bloom"]
        bad["light"]["corridor"][0] = [0.0, 5.0, -20.0]
        bad["video"]["keys"][3][0] = [30.0, 1.7, -21.5]
        bad["light"]["window"][0] = [0.0, 7.0, 30.0]
        bad["light"]["moods"]["L1"]["earth_shadow"] = 1.5
        bad["light"]["trials"] = {"T9": {"title": "x", "glow_power": 1.0}}
        problems = lobby_layout.check(bad, self.fp(bad))
        for want in ("mood L9", "L2: pendant_angle", "L3: keys differ", "corridor lamp", "video key 3", "window lamp",
                     "L1: earth_shadow", "trial T9"):
            self.assertTrue(any(want in p for p in problems), (want, problems))

    def test_the_ships_own_light(self) -> None:
        """Step 5a2/5a3: [light.ship]'s one switch K1 (neutral silver) of three sets (K2 warmer, K3 cooler), each keeping
        the hall's pendants off the ship but for a share, its own probe, a key, a rim, a back light from the north (the
        outline against the north wall) and a warm bounce from below; the request carries the set, the grid one variant
        per set; the check refuses a bad set."""
        from runner.commands import lobby as cmd
        sh = self.layout["light"]["ship"]
        self.assertEqual(sh["set"], "K1")
        self.assertEqual(sorted(sh["sets"]), ["K1", "K2", "K3"])
        k = sh["sets"]
        for st in k.values():
            self.assertLess(st["pendant_k"], 1.0)
            self.assertTrue(st["own_probe"])
            self.assertEqual(abs(st["back_dir"][0]), 180.0)   # from the north
            self.assertLess(st["bounce_dir"][1], 0.0)         # from below
            self.assertGreater(st["bounce_rgb"][0], st["bounce_rgb"][2])   # warm
        self.assertLess(max(k["K1"]["key_rgb"]) - min(k["K1"]["key_rgb"]), 0.05)   # K1 neutral, not blue-violet
        self.assertLessEqual(max(k["K1"]["ambient_rgb"]) - min(k["K1"]["ambient_rgb"]), 0.05)
        self.assertGreater(k["K2"]["pendant_k"], k["K1"]["pendant_k"])          # K2 warmer
        self.assertGreater(k["K2"]["key_rgb"][0], k["K2"]["key_rgb"][2])
        self.assertGreater(k["K2"]["bounce_energy"], k["K1"]["bounce_energy"])
        self.assertGreater(k["K3"]["key_rgb"][2], k["K3"]["key_rgb"][0])        # K3 cooler
        self.assertLess(k["K3"]["bounce_energy"], k["K1"]["bounce_energy"])
        rig = cmd.light_request(self.layout, "L3")["light"]
        self.assertEqual(rig["ship"]["id"], "K1")
        self.assertAlmostEqual(sum(c * c for c in rig["ship"]["key_dir"]), 1.0)
        self.assertEqual(rig["ship"]["probe"], sh["probe"])
        self.assertEqual(cmd.light_request(self.layout, "L3", ship="K3")["light"]["ship"]["id"], "K3")
        self.assertIn("ship_top", sh["grid"])
        self.assertEqual(len(rig["ship"]["back_dir"]), 3)

    def test_the_hall_side_fixes(self) -> None:
        """Step 5a3: the hanging lamps cast no shadow (the Earth's light laid them on the north wall as "trees"), the Earth's and the
        window spill's specular tamed, the north wall's negative wash off the ship, the package's kept nodes."""
        from runner.commands import lobby as cmd
        li = self.layout["light"]
        rig = cmd.light_request(self.layout, li["mood"])["light"]
        self.assertTrue(9.0 < rig["fixtures_below"] < 11.4)   # under the vault's ribs (11.4), over the lenses (9.15)
        self.assertLess(rig["earth_specular"], 0.5)          # Godot's default 0.5
        self.assertLess(rig["window_specular"], 0.5)
        self.assertTrue(0.0 < rig["wash"]["energy"] <= 0.5)  # subtle
        self.assertLess(rig["wash"]["at"][2], self.layout["ship"]["origin"][2] + 5.0)
        pk = self.layout["ship"]["package"]
        self.assertTrue({"Pieces", "Nose"} <= set(pk["keep"]))
        self.assertFalse({f.split(":")[0] for f in pk["free"] if ":" not in f} & set(pk["keep"]))
        self.assertNotIn("Clearing", pk["keep"])
        bad = copy.deepcopy(self.layout)
        bad["light"]["ship"]["set"] = "K9"
        bad["light"]["ship"]["grid"].append("nowhere")
        bad["light"]["ship"]["sets"]["K2"]["pendant_k"] = 1.5
        bad["light"]["ship"]["sets"]["K3"]["rim_rgb"] = [2.0, 0.0, 0.0]
        del bad["light"]["ship"]["sets"]["K1"]["key_dir"]
        bad["light"]["ship"]["probe"] = [[0.0, 4.0, 60.0], [32.0, 12.0, 36.0]]
        problems = lobby_layout.check(bad, self.fp(bad))
        for want in ("set K9", "grid: nowhere", "K2: pendant_k", "K3: rim_rgb", "K1: keys differ", "probe"):
            self.assertTrue(any(want in p for p in problems), (want, problems))

    def test_the_video(self) -> None:
        vd = self.layout["video"]
        self.assertEqual(vd["size"], [1280, 720])
        self.assertLessEqual(vd["max_mb"], 15)
        self.assertTrue(40.0 <= sum(k[2] for k in vd["keys"][1:]) <= 60.0)
        self.assertTrue(lobby_layout.in_corridor(self.layout, vd["keys"][0][0][0], vd["keys"][0][0][2]))  # the shut end
        self.assertGreater(vd["keys"][-1][1][2], 10.0)   # it ends toward the window and the Earth

    def test_the_views(self) -> None:
        names = [v[0] for v in self.layout["review"]["views"]]
        for want in ("corner_nw", "c_back", "spawn_eye", "spawn_ship", "door_d3", "door_d1", "arch", "rib",
                     "floor_ring"):
            self.assertIn(want, names)
        spawn = next(v for v in self.layout["review"]["views"] if v[0] == "spawn_eye")
        self.assertGreater(spawn[3][2], spawn[2][2])   # the spawns face the window (+z)

    def test_the_earth_as_an_object(self) -> None:
        """Step 4c: three distances; each fills E2's angle from the eye and stays outside the hall (step 5a7: F48 the
        default, the far distances tested below)."""
        e = self.layout["earth"]
        self.assertEqual(e["distance"], "H1")   # step 5c: F36 lowered (step 5b: F36, the engineer, 2026-10-31)
        self.assertEqual(list(e["distances"]), ["D1", "D2", "D3", "F48", "F36", "H1", "H2", "H3"])
        dists = [e["distances"][d]["distance_m"] for d in ("D1", "D2", "D3")]
        self.assertEqual(dists, sorted(dists))
        v = e["variants"][e["variant"]]
        for did in e["distances"]:
            o = lobby_layout.earth_object(self.layout, e["variant"], did)
            origin = e["far_eye"] if o["far"] else e["eye"]   # #366: a far distance placed from far_eye
            seen = math.degrees(math.asin(o["radius_m"] / math.dist(o["centre"], origin)))
            self.assertAlmostEqual(seen, e["distances"][did].get("radius_deg", v["radius_deg"]), places=6)
            self.assertGreater(o["far_m"], o["distance_m"] + o["radius_m"] * e["shell"])
        self.assertEqual(lobby_layout.earth_problems(self.layout, {v[0] for v in self.layout["review"]["views"]}), [])
        for d in ("glass", "back", "side"):
            self.assertIn(d, [g[0] for g in e["distance_views"]])
        self.assertAlmostEqual(e["video_keys"][0][0][2], self.layout["hall"]["zS"] + self.layout["hall"]["bulge"] - 1.5)

    def test_the_far_earth(self) -> None:
        """Step 5a7: F48 is D2's sphere traced from the spawn's eye (far_eye, spawn_eye's place) whatever the camera's
        place (#366: placed from far_eye, so D2's centre moved 2.5 m south with it); F36 a smaller radius at the same
        centre, its sun kept E2's angle behind the limb; the shader moves the shell with the camera and starts the ray
        at far_eye; the route's distances, keys and stills. The shader's source lines are pinned as strings (a guard
        that the far mode's two lines stay); test_the_far_earth_traced checks the numbers."""
        from runner.commands import lobby as cmd
        e = self.layout["earth"]
        d2, f48, f36 = (lobby_layout.earth_object(self.layout, "E2", d) for d in ("D2", "F48", "F36"))
        self.assertFalse(d2["far"])
        self.assertTrue(f48["far"] and f36["far"])
        self.assertEqual({k: f48[k] for k in ("radius_m", "frame_dir", "far_m")},
                         {k: d2[k] for k in ("radius_m", "frame_dir", "far_m")})
        shift = [b - a for a, b in zip(e["eye"], e["far_eye"])]
        for a, b, s in zip(f48["centre"], d2["centre"], shift):
            self.assertAlmostEqual(a, b + s, places=9)
        spawn = next(v for v in self.layout["review"]["views"] if v[0] == "spawn_eye")
        self.assertEqual(f48["far_eye"], spawn[2])
        self.assertEqual(f36["centre"], f48["centre"])
        self.assertAlmostEqual(f36["radius_deg"], 36.0)
        self.assertNotIn("sun_dir", f48)
        v = e["variants"]["E2"]
        u, s = lobby_layout.direction(*v["centre"]), lobby_layout.direction(*v["sun"])
        ang = lambda a, b: math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))
        self.assertAlmostEqual(v["radius_deg"] - ang(u, s), 36.0 - ang(u, f36["sun_dir"]), places=6)
        src = (Path(__file__).resolve().parents[2] / "godot" / "lobby" / "earth_object.gdshader").read_text(encoding="utf-8")
        self.assertIn("VERTEX += CAMERA_POSITION_WORLD - far_eye;", src)
        self.assertIn("vec3 eye = far_mode > 0.5 ? far_eye : cam;", src)
        self.assertIn("vec3 v = normalize(wpos - cam);", src)
        rt = e["route"]
        self.assertEqual(rt["distances"], ["F36", "H1", "H2", "H3"])   # step 5c (step 5a7: D2, F48, F36)
        self.assertEqual([p[0] for p in rt["points"]], ["spawn", "corner_nw", "glass", "arch", "par_spawn", "par_glass",
                                                        "far_back"])
        pa, pb = rt["points"][4], rt["points"][5]
        unit = lambda a: [x / math.sqrt(sum(y * y for y in a)) for x in a]
        self.assertEqual([round(x, 3) for x in unit([q - p for p, q in zip(pa[2], pa[3])])],
                         [round(x, 3) for x in unit([q - p for p, q in zip(pb[2], pb[3])])])
        self.assertTrue(all(k[0][1] == 1.6 for k in rt["keys"]))
        self.assertTrue(28.0 <= sum(k[2] for k in rt["keys"]) <= 32.0)
        self.assertEqual(cmd.parallax([[16, 300], [48, 300]], [[16, 300], [48, -1]], (1920, 1080), 70.0)["max_deg"], 0.0)
        self.assertGreater(cmd.parallax([[16, 300]], [[16, 340]], (1920, 1080), 70.0)["max_deg"], 2.0)
        bad = copy.deepcopy(self.layout)
        bad["earth"]["route"]["distances"].append("F9")
        bad["earth"]["route"]["keys"][1][0] = [30.0, 1.6, 0.0]
        q = lobby_layout.earth_problems(bad, {v[0] for v in self.layout["review"]["views"]})
        self.assertTrue(any("F9" in x for x in q) and any("outside the hall" in x for x in q))

    def test_the_lowered_earth(self) -> None:
        """Step 5c: H1..H3 are F36 turned down about the eye so the limb's highest point (traced from far_eye) sits at
        limb_deg; the size, the far mode and the sun's angle behind the limb kept; the sky's cubemap Earth turned with
        it in the request."""
        from runner.commands import lobby as cmd
        e = self.layout["earth"]
        f36 = lobby_layout.earth_object(self.layout, "E2", "F36")
        ang = lambda a, b: math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / math.sqrt(
            sum(x * x for x in a) * sum(y * y for y in b))))))
        rel = lambda o: [c - a for c, a in zip(o["centre"], e["far_eye"])]   # #366: from where the shader traces
        self.assertAlmostEqual(f36["limb_deg"], e["variants"]["E2"]["centre"][1] + 36.0, places=9)   # 14.0 (was 14.17)
        for did, limb in (("H1", 4.0), ("H2", -2.0), ("H3", -8.0)):
            o = lobby_layout.earth_object(self.layout, "E2", did)
            self.assertTrue(o["far"])
            self.assertEqual(e["distances"][did]["limb_deg"], limb)
            self.assertAlmostEqual(o["limb_deg"], limb, places=9)   # #366: exact (placed from eye: 4.05, -2.03, -8.10)
            self.assertAlmostEqual(o["radius_m"], f36["radius_m"], places=9)
            self.assertAlmostEqual(math.dist(o["centre"], e["far_eye"]), f36["distance_m"], places=6)
            self.assertAlmostEqual(ang(rel(o), o["sun_dir"]), ang(rel(f36), f36["sun_dir"]), places=6)
            self.assertAlmostEqual(o["centre"][0], 0.0, places=9)   # straight down, the azimuth kept
            drop = lobby_layout.earth_drop(self.layout, "E2", did)
            self.assertAlmostEqual(drop, e["variants"]["E2"]["centre"][1] + 36.0 - limb)
            try:   # the request reads the Earth's textures' paths in the raw folder
                req = cmd.earth_request(self.layout, "E2", distance=did)
            except common.Failure:
                continue
            self.assertAlmostEqual(ang(req["earth"]["centre"], rel(o)), 0.0, places=4)
            sky_sun = lobby_layout.pitch_down(lobby_layout.direction(*e["variants"]["E2"]["sun"]), drop)
            self.assertAlmostEqual(ang(req["earth"]["sun"], sky_sun), 0.0, places=4)   # the sky's E2 sun, turned down
        self.assertEqual(lobby_layout.earth_drop(self.layout, "E2", "F36"), 0.0)
        self.assertEqual(lobby_layout.pitch_down([0.0, 0.0, 1.0], 90.0)[1], -1.0)

    def test_refuses_a_limb_off_its_limb_deg(self) -> None:
        """#366: earth_problems compares each limb_deg with the limb as traced (lobby_layout.LIMB_TOL, 0.2 deg): a centre
        off south (azimuth 40) turned down about the east-west axis drops less than asked; a near distance is placed and
        traced from eye, exact."""
        views = {v[0] for v in self.layout["review"]["views"]}
        self.assertEqual(lobby_layout.LIMB_TOL, 0.2)
        bad = copy.deepcopy(self.layout)
        bad["earth"]["variants"]["E2"]["centre"][0] = 40.0
        q = lobby_layout.earth_problems(bad, views)
        self.assertTrue(any(x.startswith("earth H3: the limb's top traces at") for x in q), q)
        o = lobby_layout.earth_object(bad, "E2", "H3")
        self.assertGreater(abs(o["limb_deg"] + 8.0), 0.2)
        near = copy.deepcopy(self.layout)
        near["earth"]["distances"]["H1"]["far"] = False
        self.assertEqual([x for x in lobby_layout.earth_problems(near, views) if "limb" in x], [])

    def test_the_far_earth_traced(self) -> None:
        """#366 (the string pins above are only a guard): earth_object.gdshader's far mode in numbers. The fragment's
        ray starts at far_eye along the view ray v and hits the disc when the angle between v and (centre - far_eye) is
        below asin(radius / dist) (its `edge` < 0), so from any camera place the same v gives the same answer: H1's limb
        hit just under 4 deg, missed just over it, straight up the centre's azimuth."""
        e = self.layout["earth"]
        o = lobby_layout.earth_object(self.layout, "E2", "H1")
        sh = e["far_eye"]

        def edge(v: list[float]) -> float:   # the shader's `edge` (radians), its eye at far_eye in the far mode
            oc = [c - a for c, a in zip(o["centre"], sh)]
            dist = math.sqrt(sum(x * x for x in oc))
            alpha = math.asin(min(1.0, o["radius_m"] / dist))
            cos = sum(a * b / dist for a, b in zip(v, oc))
            return math.acos(max(-1.0, min(1.0, cos))) - alpha

        for el, hit in ((3.95, True), (4.05, False), (-30.0, True), (-50.0, True), (10.0, False)):
            v = lobby_layout.direction(0.0, el)
            self.assertEqual(edge(v) < 0.0, hit, el)
        for cam in ([0.0, 1.65, 2.5], [-12.0, 1.6, -20.0], [16.0, 1.6, 10.0]):   # the camera's place changes no ray
            v = lobby_layout.direction(0.0, 3.95)
            wpos = [c + 10.0 * x for c, x in zip(cam, v)]   # a shell fragment straight ahead of that camera
            vv = [w - c for w, c in zip(wpos, cam)]
            n = math.sqrt(sum(x * x for x in vv))
            self.assertLess(edge([x / n for x in vv]), 0.0)

    def test_refuses_an_earth_inside_the_hall(self) -> None:
        bad = copy.deepcopy(self.layout)
        bad["earth"]["distances"]["D1"]["distance_m"] = 40.0
        self.assertTrue(any("D1" in q and "hall's box" in q for q in lobby_layout.earth_problems(bad, {v[0] for v in self.layout["review"]["views"]})))
        bad["earth"]["distance"] = "D9"
        self.assertTrue(any("D9" in q for q in lobby_layout.earth_problems(bad, {v[0] for v in self.layout["review"]["views"]})))

    def test_glb_points_and_the_closed_nose(self) -> None:
        """Step 4c: the closed ship's footprint joins the shut jaws' vertices (read from the package's GLBs); step 5a:
        it holds every rule at the engineer's new place, so the package instance is used."""
        pk = self.layout["ship"]["package"]
        folder = common.raw_dir() / pk["dir"] / "assets" / "environment" / "ship"
        if not (folder / "jaw_lower.glb").is_file() or not (common.raw_dir() / self.layout["ship"]["pieces_dir"]).is_dir():
            self.skipTest(f"no {folder}")
        self.assertTrue(pk["use"])
        self.assertEqual(pk["free"], ["Clearing", "Environment", "Lights:DirectionalLight3D"])
        from runner.commands import lobby
        place, _drop, report, _ship = lobby.ship_scene(self.layout)
        fp = lobby_layout.footprint(self.layout, self.outline, report, place)
        cf = lobby_layout.closed_footprint(self.layout, fp, place)
        cn = lobby_layout.ship_numbers(self.layout, cf)
        self.assertAlmostEqual(cn["nose_z"], -26.99, places=2)
        self.assertAlmostEqual(cn["aft_z"], 0.46, delta=0.01)
        self.assertAlmostEqual(cn["middle_z"], -13.26, delta=0.01)   # the ring's centre
        self.assertAlmostEqual(lobby_layout.wall_gaps(self.layout, cf)["N"], 3.01, delta=0.01)
        spawn = min(lobby_layout.poly_dist(cf, (x, self.layout["floor"]["spawns_z"])) for x in self.layout["floor"]["spawns_x"])
        self.assertAlmostEqual(spawn, 2.04, delta=0.01)
        self.assertEqual(lobby_layout.check(self.layout, cf), [])
        moved = copy.deepcopy(self.layout)   # step 4c's place: the jaw 0.51 m from the north wall, refused
        moved["ship"]["origin"] = [0.0, 0.0, -17.0]
        cf = lobby_layout.closed_footprint(moved, lobby_layout.footprint(moved, self.outline, report, place), place)
        self.assertTrue(any(q.startswith("ship:") and "from N" in q for q in lobby_layout.check(moved, cf)))

    def test_glb_points_refuses_what_it_cannot_read(self) -> None:
        """#366: glb_points reads one level of TRS nodes with float positions; children, a matrix, a geometry extension
        or quantized positions are refused, a material extension is read past."""
        import json as js
        import struct
        import tempfile

        def glb(folder: Path, name: str, node: dict, ext: list | None = None, ctype: int = 5126) -> Path:
            gl = {"asset": {"version": "2.0"}, "nodes": [node], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
                  "accessors": [{"bufferView": 0, "componentType": ctype, "count": 1, "type": "VEC3"}],
                  "bufferViews": [{"buffer": 0, "byteLength": 12}], "buffers": [{"byteLength": 12}]}
            if ext:
                gl["extensionsUsed"] = ext
            j = js.dumps(gl).encode()
            j += b" " * (-len(j) % 4)
            b = struct.pack("<3f", 1.0, 2.0, 3.0)
            data = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(b)) + struct.pack("<II", len(j), 0x4E4F534A) + j \
                + struct.pack("<II", len(b), 0x004E4942) + b
            (folder / name).write_bytes(data)
            return folder / name

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ok = glb(d, "ok.glb", {"mesh": 0, "translation": [1.0, 0.0, 0.0]}, ["KHR_materials_emissive_strength"])
            self.assertEqual(lobby_layout.glb_points(ok), [(2.0, 2.0, 3.0)])
            for name, node, ext, ctype, want in (
                    ("kids.glb", {"mesh": 0, "children": [0]}, None, 5126, "children"),
                    ("matrix.glb", {"mesh": 0, "matrix": [1.0] * 16}, None, 5126, "matrix"),
                    ("draco.glb", {"mesh": 0}, ["KHR_draco_mesh_compression"], 5126, "extensions"),
                    ("quant.glb", {"mesh": 0}, None, 5123, "plain float")):
                with self.assertRaises(ValueError) as cm:
                    lobby_layout.glb_points(glb(d, name, node, ext, ctype))
                self.assertIn(want, str(cm.exception))

    def test_hull_outline_leaves_sys_path(self) -> None:
        """#366: the Blender folder is on sys.path only for the import."""
        folder = str(common.ROOT / "tools" / "blender")
        before = list(sys.path)
        lobby_layout.hull_outline(self.layout["ship"]["hull"])
        self.assertEqual(sys.path, before)   # another test module may have put the folder there itself: kept, not added
        if folder in before:
            sys.path.remove(folder)
            try:
                lobby_layout.hull_outline(self.layout["ship"]["hull"])
                self.assertNotIn(folder, sys.path)
            finally:
                sys.path.insert(before.index(folder), folder)

    def test_plan_draws_the_hall(self) -> None:
        plan = lobby_layout.ascii_plan(self.layout, self.fp(self.layout))
        for mark in ("A", "S", "s", "o", "W", "D", "#", "|"):
            self.assertIn(mark, plan)

    def test_the_built_report(self) -> None:
        path = common.raw_dir() / self.layout["ship"]["pieces_dir"] / "build_report.json"
        if not path.is_file():
            self.skipTest(f"no {path}")
        from runner.commands import lobby
        place, drop, report, ship = lobby.ship_scene(self.layout)
        fp = lobby_layout.footprint(self.layout, self.outline, report, place)
        self.assertEqual(lobby_layout.check(self.layout, fp), [])
        kept = {p[0] for p in place}
        self.assertFalse(kept & set(drop))
        self.assertIn("skin_top", kept)


class ShipLightCopiesTest(unittest.TestCase):
    """#366: hall.gd's _ship_light places the ship-only copies of the pendants and the Earth's light by their local
    transform under the same parent (_rig) as their sources. A global_transform there is identity off the tree (the
    shoot, the grids and the video set the scene up in SceneTree._initialize), which put the copies at the floor's
    centre aiming north in the shots while the export, assembled inside the tree, hung them under the pendants. The
    code path is pinned as source (a Godot run would need a window; docs/lobby.md "Follow-up #366")."""

    def test_the_copies_keep_their_source_lights_place(self) -> None:
        src = (common.ROOT / "godot" / "lobby" / "hall.gd").read_text(encoding="utf-8")
        body = src[src.index("func _ship_light("):]
        body = body[:body.index("\nfunc ", 1)]
        code = "\n".join(line.split("#")[0] for line in body.splitlines())   # the code, not its comments
        self.assertNotIn("global_transform", code, "a global transform read or set off the tree is identity")
        copy_loop = body[body.index("lt.duplicate()"):body.index("own_probe")]
        self.assertIn("_rig.add_child(copy)", copy_loop)
        self.assertIn("copy.transform = lt.transform", copy_loop)
        # the sources (the pendants' spots and the Earth's sun) are children of _rig too, placed locally
        setup = src[src.index('var hall_lights: Dictionary'):src.index("func _ship_light(")]
        for name, add in (("spot", "_rig.add_child(spot)"), ("sun", "_rig.add_child(sun)")):
            self.assertIn(add, setup, name)
        self.assertRegex(setup, r'hall_lights\["pendant"\]\.append\(spot\)')
        self.assertRegex(setup, r'hall_lights\["earth"\]\.append\(sun\)')
        self.assertEqual(len(re.findall(r'hall_lights\["(?:pendant|earth)"\]\.append', setup)), 2)


if __name__ == "__main__":
    unittest.main()
