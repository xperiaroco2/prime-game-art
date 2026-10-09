"""The House map outside the house (layouts/house/outdoor/, tools/runner/house_outdoor.py, docs/house-outdoor.md):
the fence closes the plot but for the wicket and the gates (Q4), the ground has holes only where a floor or the
stairwell is, the U stairs connect the yard to the passage, the props keep the clearances, the sky has no seam and
the backdrop's flats stand between the street and the skirt. Pure Python, no Blender or Godot."""

from __future__ import annotations

import copy
import json
import math
import struct
import tempfile
import tomllib
import unittest
from pathlib import Path

from runner import house_outdoor as ho
from runner import house_sky as sky
from runner.common import ROOT

DATA = ho.load()
PLAN = ho.plan(DATA)
SPEC = {p["id"]: p for p in json.loads((ROOT / "kits" / "house.json").read_text(encoding="utf-8"))["pieces"]}


class FenceTest(unittest.TestCase):
    def test_the_plan_is_clean(self) -> None:
        self.assertEqual(PLAN["problems"], [])

    def test_only_the_wicket_and_the_gates_are_open(self) -> None:
        opens = {o["kind"]: o for o in PLAN["openings"]}
        self.assertEqual(sorted(opens), ["gates", "wicket"])
        w, g = opens["wicket"], opens["gates"]
        self.assertEqual({w["from"][1], w["to"][1], g["from"][1], g["to"][1]}, {60.0})
        self.assertAlmostEqual((w["from"][0] + w["to"][0]) / 2, 30.0)  # Q4: the wicket centred on x 30
        self.assertAlmostEqual((g["from"][0] + g["to"][0]) / 2, 64.0)  # and the gates on x 64
        self.assertAlmostEqual(abs(g["to"][0] - g["from"][0]), 7.8)  # 8 m gates, leaves between their posts

    def test_the_fence_runs_round_the_whole_plot(self) -> None:
        self.assertAlmostEqual(sum(s1 - s0 for e in PLAN["fence"]["edges"] for s0, s1, _ in e["spans"]), 280.0)
        for pc in PLAN["fence"]["pieces"]:
            self.assertIn(pc["piece"], SPEC, pc)
            x, _, z = pc["at"]
            self.assertTrue(x in (0, 80) or z in (0, 60), pc)
            self.assertAlmostEqual(x, round(x))

    def test_a_missing_module_shows_as_a_gap(self) -> None:
        fence = copy.deepcopy(PLAN["fence"])
        fence["edges"][0]["spans"].pop(3)
        self.assertIn("gap", [o["kind"] for o in ho.fence_openings(fence)])

    def test_every_fence_post_has_a_cap(self) -> None:
        posts = {(p["at"][0], p["at"][2]) for p in PLAN["fence"]["pieces"]
                 if p["piece"] in ("fence_2m", "fence_1m", "fence_wicket_2m")}
        caps = {(p["at"][0], p["at"][2]) for p in PLAN["fence"]["pieces"] if p["piece"] == "fence_post_cap"}
        self.assertEqual(posts, caps)
        self.assertEqual(sum(p["piece"] == "gate_post" for p in PLAN["fence"]["pieces"]), 2)


class GroundTest(unittest.TestCase):
    CELLS = ho.ground_cells(DATA)

    def test_no_cell_under_a_floor_or_the_stairwell(self) -> None:
        for (i, j) in self.CELLS:
            x, y = i + 0.5, j + 0.5
            for h in ho.holes(DATA):
                self.assertFalse(ho.in_rect(h["rect"], x, y), (h["id"], x, y))

    def test_the_paints_and_the_zones(self) -> None:
        self.assertEqual(set(self.CELLS.values()) - set(DATA["paints"]), set())
        self.assertEqual(self.CELLS[(29, 50)], "paving")  # the path
        self.assertEqual(self.CELLS[(63, 55)], "concrete")  # the driveway
        self.assertEqual(self.CELLS[(10, 64)], "asphalt")  # the street
        self.assertEqual(self.CELLS[(5, 5)], "grass")
        self.assertEqual(len(self.CELLS), 80 * 66 - sum(h["rect"][2] * h["rect"][3] for h in ho.holes(DATA)))

    def test_the_holes_cover_the_layout_engines_floors(self) -> None:
        ground = ROOT / "layouts" / "house" / "ground.toml"
        if not ground.exists():
            self.skipTest("the house layout (#75a) is not on this branch")
        with open(ground, "rb") as f:
            level = tomllib.load(f)
        rects = [h["rect"] for h in ho.holes(DATA)]
        for room in level["rooms"]:
            if room.get("kind") != "area":
                x, y, w, d = room["rect"]
                self.assertTrue(any(ho.in_rect(r, x, y) and ho.in_rect(r, x + w, y + d) for r in rects), room["id"])

    def test_the_meshes(self) -> None:
        meshes = {m.name: m for m in ho.ground_meshes(DATA)}
        self.assertEqual(meshes["ground-col"].tris, 2 * len(self.CELLS))
        self.assertTrue(all(abs(p[1]) < 1e-9 for p in meshes["ground-col"].pos))  # one flat sheet: nothing z-fights
        self.assertTrue(all(0 <= u <= 1 and 0 <= v <= 1 for u, v in meshes["ground-col"].uv1))
        self.assertAlmostEqual(max(p[1] for p in meshes["kerb-col"].pos), DATA["kerb"]["height"])
        for m in meshes.values():  # every triangle faces its normal
            for t in range(m.tris):
                a, b, c = (m.pos[m.idx[3 * t + k]] for k in range(3))
                n = m.nrm[m.idx[3 * t]]
                e1, e2 = [b[q] - a[q] for q in range(3)], [c[q] - a[q] for q in range(3)]
                cr = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
                self.assertGreater(sum(cr[q] * n[q] for q in range(3)), 0, m.name)


class StairsTest(unittest.TestCase):
    def ends(self, pc: dict) -> tuple:
        """A flight's foot and top: (doc x, height, doc y) at the middle of its width."""
        p = SPEC[pc["piece"]]
        lx = ho.local_x(pc["yaw"])
        lz = ho.local_x(pc["yaw"] - 90)  # local +Z in doc (x, y)
        x, h, y = pc["at"]
        mx, my = x + lz[0] * p["width"] / 2, y + lz[1] * p["width"] / 2
        return (mx, h, my), (mx + lx[0] * p["run"], h + p["rise"], my + lx[1] * p["run"])

    def test_the_u_connects_the_yard_to_the_passage(self) -> None:
        for entry in ("N", "S"):
            data = copy.deepcopy(DATA)
            data["stairs"]["entry"] = entry
            st = ho.stairs_plan(data)
            self.assertEqual(st["problems"], [])
            a, land, b = st["pieces"]
            foot_a, top_a = self.ends(a)
            foot_b, top_b = self.ends(b)
            x0, y0, w, d = data["stairs"]["rect"]
            self.assertAlmostEqual(top_a[1], 0.0)  # flight A starts at the yard
            self.assertAlmostEqual(top_a[2], y0 if entry == "N" else y0 + d)  # on the entry edge
            self.assertAlmostEqual(foot_a[1], land["at"][1])  # and lands on the landing's top
            self.assertAlmostEqual(top_b[1], land["at"][1])
            self.assertAlmostEqual(foot_b[1], -data["stairs"]["drop"])  # flight B ends on the passage's floor
            self.assertAlmostEqual(foot_b[2], top_a[2])  # under the entry edge
            for p in (foot_a, top_a, foot_b, top_b):
                self.assertTrue(ho.in_rect(data["stairs"]["rect"], p[0], p[2]), (entry, p))
            self.assertAlmostEqual(sum(f[2] * f[3] for f in st["flights"]), w * d)
            self.assertEqual(st["walk"][0][1], 0.0)
            self.assertEqual(st["walk"][-1][1], -data["stairs"]["drop"])

    def test_the_rails_leave_only_the_entry_open(self) -> None:
        st = PLAN["stairs"]
        rails = [r for r in st["rails"] if r["piece"] == DATA["stairs"]["railing"]]
        self.assertEqual(len(rails) * 2, 14)  # 16 m of edge less the 2 m entry
        x0, y0, _, _ = DATA["stairs"]["rect"]
        for r in rails:  # nothing starts into the entry span (x0+2..x0+4 on the north edge)
            lx = ho.local_x(r["yaw"])
            mid = (r["at"][0] + lx[0], r["at"][2] + lx[1])
            self.assertFalse(abs(mid[1] - y0) < 1e-6 and x0 + 2 < mid[0] < x0 + 4, r)


class PropsTest(unittest.TestCase):
    def test_a_car_in_front_of_the_gates_is_refused(self) -> None:
        data = copy.deepcopy(DATA)
        next(p for p in data["props"] if p["id"] == "parked_car")["at"].append([64, 63.3])
        self.assertTrue(any("gates_approach" in p for p in ho.prop_problems(data)))

    def test_the_street_has_its_q16_furniture(self) -> None:
        n = {p["id"]: len(p["at"]) for p in DATA["props"]}
        self.assertEqual(n["streetlight"], 5)
        self.assertGreaterEqual(n["parked_car"], 1)
        self.assertEqual(n["hydrant"], 1)


class SkyTest(unittest.TestCase):
    CFG = DATA["sky_cfg"]

    def test_the_sizes_and_the_flats(self) -> None:
        self.assertEqual(self.CFG["sky"]["size"], [1024, 512])
        self.assertLessEqual(len(self.CFG["backdrop"]["flats"]), 6)
        self.assertEqual(self.CFG["backdrop"]["fog_start_m"], 35.0)
        self.assertEqual(ho.flat_problems(self.CFG, DATA), [])

    def test_the_colours_at_the_horizon_and_the_zenith(self) -> None:
        def srgb(e):
            return tuple(sky.byte(sky.to_srgb(c)) for c in sky.stop_colour(self.CFG["sky"]["stops"], e))
        self.assertEqual(srgb(0), (0xE0, 0x90, 0x6C))
        self.assertEqual(srgb(90), (0x2D, 0x2A, 0x55))
        self.assertGreater(sum(srgb(2)), sum(srgb(30)))  # the warm band is the brightest, low and narrow

    def test_no_seam_where_the_panorama_wraps(self) -> None:
        cfg = copy.deepcopy(self.CFG["sky"])
        cfg["size"] = [256, 128]
        cfg["stars"]["count"] = 0  # single random pixels, not a seam; the clouds and the gradient must wrap
        w, h, rows = sky.sky_rows(cfg)
        wrap, inner = sky.seam_step(rows)
        self.assertLessEqual(wrap, inner * 2 + 1.0)

    def test_png_round_trip_and_the_windows(self) -> None:
        flat = copy.deepcopy(self.CFG["backdrop"]["flats"][0])
        flat["texture"] = [512, 64]
        flat["windows"]["count"] = 5
        w, h, rgba, emit, placed = sky.flat_rows(flat, 3)
        self.assertEqual(placed, 5)
        with tempfile.TemporaryDirectory() as tmp:
            path = sky.write_png(Path(tmp) / "f.png", w, h, rgba, 4)
            self.assertEqual(sky.read_png(path), (w, h, 4, rgba))
        self.assertEqual(rgba[0][3::4].count(0) > 0, True)  # the silhouette leaves sky above it
        self.assertEqual(set(rgba[-1][3::4]), {255})  # and is solid at its foot


class GlbTest(unittest.TestCase):
    def test_the_backdrop_glb(self) -> None:
        cfg = DATA["sky_cfg"]
        meshes = ho.flat_meshes(cfg)
        mats = [{"name": m.name, "extensions": {"KHR_materials_unlit": {}}} for m in meshes]
        data = ho.glb_bytes(meshes, mats)
        magic, version, total = struct.unpack("<III", data[:12])
        self.assertEqual((magic, version, total), (0x46546C67, 2, len(data)))
        n = struct.unpack("<I", data[12:16])[0]
        doc = json.loads(data[20:20 + n])
        self.assertEqual([nd["name"] for nd in doc["nodes"]], [f"flat_{f['id']}" for f in cfg["backdrop"]["flats"]])
        self.assertEqual(doc["extensionsUsed"], ["KHR_materials_unlit"])
        for m, f in zip(meshes, cfg["backdrop"]["flats"]):
            cx, cy = cfg["backdrop"]["centre"]
            r = {round(math.hypot(p[0] - cx, p[2] - cy), 6) for p in m.pos}
            self.assertEqual(r, {f["radius"]})


if __name__ == "__main__":
    unittest.main()
