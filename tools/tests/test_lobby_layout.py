"""The lobby hall's layout check (art #356, docs/lobby.md): plain Python, no Blender, no Godot. The ship's footprint
comes from the hull's outline (ship_hull_shape, plain Python) and a fixture of art #263's build report (the pods' and
the tail's bounds as built in ship/v5); a last test reads the real report when the raw folder has it."""

from __future__ import annotations

import copy
import math
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
        self.assertEqual(self.layout["raw_dir"], "lobby/hall/v11")   # step 5a4
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
        """Step 4c: three distances, D2 by default; each fills E2's angle from the eye and stays outside the hall."""
        e = self.layout["earth"]
        self.assertEqual(e["distance"], "D2")
        self.assertEqual(list(e["distances"]), ["D1", "D2", "D3"])
        dists = [e["distances"][d]["distance_m"] for d in e["distances"]]
        self.assertEqual(dists, sorted(dists))
        v = e["variants"][e["variant"]]
        for did in e["distances"]:
            o = lobby_layout.earth_object(self.layout, e["variant"], did)
            seen = math.degrees(math.asin(o["radius_m"] / math.dist(o["centre"], e["eye"])))
            self.assertAlmostEqual(seen, v["radius_deg"], places=6)
            self.assertGreater(o["far_m"], o["distance_m"] + o["radius_m"] * e["shell"])
        self.assertEqual(lobby_layout.earth_problems(self.layout, {v[0] for v in self.layout["review"]["views"]}), [])
        for d in ("glass", "back", "side"):
            self.assertIn(d, [g[0] for g in e["distance_views"]])
        self.assertAlmostEqual(e["video_keys"][0][0][2], self.layout["hall"]["zS"] + self.layout["hall"]["bulge"] - 1.5)

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


if __name__ == "__main__":
    unittest.main()
