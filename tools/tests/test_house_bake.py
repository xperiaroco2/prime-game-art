"""The pure parts of the House's lightmap bake (tools/runner/house_bake.py, #83)."""

import struct
import tempfile
import time
import tomllib
import unittest
import zlib
from pathlib import Path
from unittest import mock

from runner import common, house_bake as B, house_layout
from runner.commands import _house_bake

LIGHTS = common.ROOT / "layouts" / "house" / "lights.toml"


def at(hour: int) -> float:
    return time.mktime((2026, 10, 10, hour, 30, 0, 0, 0, -1))


def png(path: Path, width: int, rows: list[bytes], filters: list[int]) -> None:
    """A tiny RGB PNG with the given (already filtered) rows and filter bytes."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    raw = b"".join(bytes([f]) + r for f, r in zip(filters, rows))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, len(rows), 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class NightWindow(unittest.TestCase):
    def test_night_hours_only(self):
        self.assertTrue(B.editor_allowed(at(0)))
        self.assertTrue(B.editor_allowed(at(7)))
        self.assertFalse(B.editor_allowed(at(8)))
        self.assertFalse(B.editor_allowed(at(23)))

    def test_a_grant_opens_the_day_until_its_end(self):
        grant = "until 2026-10-10 15:00\nthe engineer said yes"
        self.assertTrue(B.editor_allowed(at(14), grant))
        self.assertFalse(B.editor_allowed(at(15), grant))

    def test_a_bad_grant_is_no_grant(self):
        self.assertIsNone(B.granted_until("until tomorrow"))
        self.assertIsNone(B.granted_until(None))
        self.assertFalse(B.editor_allowed(at(12), "until tomorrow"))


class Staging(unittest.TestCase):
    def test_used_glbs(self):
        text = ('[ext_resource type="PackedScene" path="res://import/kit_floor_boards_2x2.glb" id="1"]\n'
                '[ext_resource type="PackedScene" path="res://import/prop_sofa.glb" id="2"]\n'
                '[ext_resource type="PackedScene" path="res://import/house/ground/kitchen.tscn" id="3"]\n')
        self.assertEqual(B.used_glbs([text, text]), {"kit_floor_boards_2x2", "prop_sofa"})

    def test_uv2_table_and_hints(self):
        table = B.uv2_table([{"id": "floor_boards_2x2", "uv2_per_m": 0.22321}, {"id": "x", "uv2_per_m": 0}])
        self.assertEqual(table, {"floor_boards_2x2": 0.22321})
        self.assertEqual(B.size_hint(8, 0.22321), 36)
        self.assertEqual(B.size_hint(8, 0.25), 32)
        self.assertEqual(B.size_hint(8, 0.22321, B.ABOVE_OTHER_K), 4)

    def test_import_params(self):
        self.assertEqual(B.PROP_IMPORT["meshes/light_baking"], 2)  # Static Lightmaps: Godot unwraps UV2
        self.assertEqual(B.KIT_IMPORT["meshes/light_baking"], 1)  # Static: the kit's own UV2 is kept
        self.assertEqual(B.PROP_TEXEL_PER_M, 5.0)

    def test_build_args(self):
        bake = {"denoiser": True, "bounce_indirect_energy": 1.0, "bounces": 3}
        args = B.build_args("ground", "high", 12.0, bake, "u.json", "b.json")
        self.assertEqual(args, ["zone=ground", "tag=high", "texel=12", "denoiser=1", "energy=1", "bounces=3", "above=1",
                                "merge=0", "lights=static", "uv2=u.json", "bake=b.json"])
        self.assertIn("lights=dynamic", B.build_args("ground", "x", 8.0, bake, "u", "b", lights="dynamic"))
        with self.assertRaises(ValueError):
            B.build_args("ground", "x", 8.0, bake, "u", "b", lights="baked")


class Cameras(unittest.TestCase):
    def test_views_stay_inside_their_rooms(self):
        data = house_layout.load()
        cams = B.views(data, ["living_room", "kitchen"])
        self.assertEqual(len(cams), 3)
        rooms = {r["id"]: r["rect"] for lv in data["levels"] for r in lv["rooms"]}
        for cam, rid in zip(cams, ["living_room", "kitchen", "living_room"]):
            x, z, w, d = rooms[rid]
            self.assertTrue(x < cam[0] < x + w and z < cam[2] < z + d, (rid, cam))
            self.assertTrue(x < cam[3] < x + w and z < cam[5] < z + d, (rid, cam))

    def test_wall_camera_faces_the_north_wall(self):
        data = house_layout.load()
        cams = B.views(data, ["living_room", "kitchen"], ["kitchen"])
        self.assertEqual(len(cams), 4)
        self.assertEqual(B.view_names(["living_room", "kitchen"], ["kitchen"]),
                         ["E1 living_room", "E1 kitchen", "wall kitchen", "seam"])
        x, z, w, d = next(r["rect"] for lv in data["levels"] for r in lv["rooms"] if r["id"] == "kitchen")
        eye, look = cams[2][:3], cams[2][3:]
        self.assertTrue(x < eye[0] < x + w and z < eye[2] < z + d)
        self.assertTrue(z < look[2] < eye[2], cams[2])
        self.assertEqual(cams[3], B.views(data, ["living_room"])[1])

    def test_unknown_room(self):
        with self.assertRaises(ValueError):
            B.views(house_layout.load(), ["nowhere"])
        with self.assertRaises(ValueError):
            B.views(house_layout.load(), ["kitchen"], ["nowhere"])


class Measures(unittest.TestCase):
    def test_read_png_undoes_every_filter(self):
        want = [bytes([10, 20, 30, 200, 100, 50]), bytes([0, 0, 0, 255, 255, 255]), bytes([7, 8, 9, 9, 8, 7]),
                bytes([1, 2, 3, 4, 5, 6]), bytes([90, 80, 70, 60, 50, 40])]
        filtered, prev = [], bytes(6)
        for f, row in enumerate(want):  # filters 0..4 in turn
            out = bytearray(6)
            for i in range(6):
                a = row[i - 3] if i >= 3 else 0
                b = prev[i]
                c = prev[i - 3] if i >= 3 else 0
                p = a + b - c
                pred = [0, a, b, (a + b) // 2,
                        a if abs(p - a) <= abs(p - b) and abs(p - a) <= abs(p - c) else b if abs(p - b) <= abs(p - c)
                        else c][f]
                out[i] = (row[i] - pred) & 255
            filtered.append(bytes(out))
            prev = row
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.png"
            png(path, 2, filtered, [0, 1, 2, 3, 4])
            w, h, px = B.read_png(path)
        self.assertEqual((w, h), (2, 5))
        self.assertEqual(px, [tuple(r[i:i + 3]) for r in want for i in (0, 3)])

    def test_lab_and_frame_numbers(self):
        self.assertAlmostEqual(B.srgb_lab(255, 255, 255)[0], 100.0, places=1)
        self.assertAlmostEqual(B.srgb_lab(0, 0, 0)[0], 0.0, places=3)
        self.assertGreater(abs(complex(*B.srgb_lab(200, 40, 40)[1:])), 60)
        m = B.measures(4, 1, [(0, 0, 0), (0, 0, 0), (255, 255, 255), (200, 40, 40)], grid=4)
        self.assertEqual(m["dark_pct"], 50.0)
        self.assertGreater(m["C_p90"], 60)


class Grid(unittest.TestCase):
    def setUp(self):
        self.lights = tomllib.loads(LIGHTS.read_text(encoding="utf-8"))

    def test_tags(self):
        self.assertEqual(B.variant_tag(12.0, True, 1.5), "t12_d1_e15")
        self.assertEqual(B.variant_tag(8.0, False, 1.0, merge=True), "t8_d0_e10_m")

    def test_the_preset_is_one_variant_with_the_shared_bake(self):
        (v,) = B.variants(self.lights, "ground", "high")
        self.assertEqual((v["tag"], v["texel"], v["merge"]), ("high", self.lights["zones"]["ground"]["texel_high"], False))
        self.assertEqual(v["bake"], self.lights["bake"])
        self.assertIsNot(v["bake"], self.lights["bake"])

    def test_the_grid_is_texel_by_denoiser_by_energy(self):
        vs = B.variants(self.lights, "ground", "high", grid=True)
        self.assertEqual(len(vs), 12)
        self.assertEqual(len({v["tag"] for v in vs}), 12)
        self.assertEqual({v["texel"] for v in vs}, {8.0, 12.0, 16.0})
        self.assertEqual({(v["bake"]["denoiser"], v["bake"]["bounce_indirect_energy"]) for v in vs},
                         {(True, 1.0), (True, 1.5), (False, 1.0), (False, 1.5)})
        for v in vs:  # the rest of [bake] is shared
            self.assertEqual(v["bake"]["quality"], self.lights["bake"]["quality"])
            self.assertLessEqual(v["bake"]["bounce_indirect_energy"], 1.5)  # the lab's ceiling
        self.assertEqual(self.lights["bake"]["bounce_indirect_energy"], 1.5)  # the grid did not change lights.toml

    def test_merge_marks_every_variant(self):
        self.assertTrue(all(v["merge"] and v["tag"].endswith("_m")
                            for v in B.variants(self.lights, "ground", "low", grid=True, merge=True)))

    def test_sheet_about_1280_px(self):
        self.assertEqual(B.sheet_layout(2, 3), {"tile": [426, 239], "per_line": 1})
        grid = B.sheet_layout(13, 3)  # real time and the 12 variants
        self.assertEqual(grid["per_line"], 2)
        self.assertLessEqual(grid["tile"][0] * 3 * 2, 1280)
        self.assertGreater(grid["tile"][0] * 3 * 2, 1200)

    def test_numbers_against_real_time(self):
        m = lambda lum: {"L_mean": lum, "dark_pct": 10.0, "C_p90": 20.0}
        md = B.numbers_md("ground", {"ground_realtime": [m(40.0), m(50.0)], "ground_high_baked": [m(30.0), m(45.0)]},
                          "ground_realtime", ["E1 kitchen", "seam"])
        self.assertIn("| ground_high_baked | 30.0 / 10.0 / 20.0 | 45.0 / 10.0 / 20.0 | -10.0 / -5.0 (-7.5) |", md)
        self.assertIn("| ground_realtime | 40.0 / 10.0 / 20.0 | 50.0 / 10.0 / 20.0 |  |", md)

    def test_numbers_against_several_references(self):
        m = lambda lum: {"L_mean": lum, "dark_pct": 10.0, "C_p90": 20.0}
        table = {"g_realtime": [m(40.0)], "g_realtime_shadow": [m(30.0)], "g_x_baked": [m(31.0)]}
        md = B.numbers_md("g", table, ["g_realtime", "g_realtime_shadow"], ["seam"])
        self.assertIn("dL* vs g_realtime (per camera; mean) | dL* vs g_realtime_shadow (per camera; mean) |", md)
        self.assertIn("| g_x_baked | 31.0 / 10.0 / 20.0 | -9.0 (-9.0) | +1.0 (+1.0) |", md)
        self.assertIn("| g_realtime_shadow | 30.0 / 10.0 / 20.0 | -10.0 (-10.0) |  |", md)


class Diagnostic(unittest.TestCase):
    """#83b: the diagnostic bakes and their shot rows."""

    def setUp(self):
        self.lights = tomllib.loads(LIGHTS.read_text(encoding="utf-8"))

    def test_four_bakes_at_the_high_texel(self):
        vs = B.diag_variants(self.lights, "ground")
        texel = self.lights["zones"]["ground"]["texel_high"]
        self.assertEqual(len({v["tag"] for v in vs}), 4)
        self.assertTrue(all(v["texel"] == texel and not v["merge"] for v in vs))
        base, b0, ld, old = vs
        self.assertEqual((base["bake"]["denoiser"], base["bake"]["bounce_indirect_energy"]), (False, 1.5))
        self.assertEqual(base["bake"], self.lights["bake"])  # #83b's default is the chosen settings
        self.assertEqual(b0["bake"], {**base["bake"], "bounces": 0})
        self.assertEqual((ld["lights"], ld["bake"]), ("dynamic", base["bake"]))
        self.assertEqual(old["bake"], {**self.lights["bake"], **B.BEFORE_83B})
        self.assertEqual(old["tag"], "t8_d1_e15_old")
        self.assertEqual([v["lights"] for v in (base, b0, old)], ["static"] * 3)

    def test_rows_and_modes(self):
        rows = B.shot_rows("ground", B.diag_variants(self.lights, "ground"))
        self.assertEqual([r["mode"] for r in rows], ["realtime", "realtime_shadow", "realtime_shadow_nospec", "baked",
                                                     "baked", "hybrid", "hybrid_nospec", "baked"])
        self.assertEqual(rows[0]["label"], "ground_realtime")
        self.assertEqual(rows[1]["label"], "ground_realtime_shadow")
        self.assertEqual(rows[6]["label"], "ground_t8_d0_e15_ld_hybrid_nospec")
        self.assertEqual(len({r["label"] for r in rows}), len(rows))
        self.assertLessEqual(len(rows), 8)  # the brief's bound: about 8 rows of three cameras

    def test_the_preset_and_grid_rows(self):
        sheen = self.lights["presets"]["high"]["sheen"]  # #83c: the preset's sheen row follows the bake
        rows = B.shot_rows("ground", B.variants(self.lights, "ground", "high"))
        self.assertEqual(rows[:2], [{"label": "ground_realtime", "tag": "high", "mode": "realtime"},
                                    {"label": "ground_high_baked", "tag": "high", "mode": "baked"}])
        self.assertEqual(rows[2], {"label": f"ground_high_{sheen}", "tag": "high", "mode": sheen,
                                   "sheen": B.sheen_mode(sheen)})
        rows = B.shot_rows("ground", B.variants(self.lights, "ground", "high", reference=True))
        self.assertEqual([r["label"] for r in rows],
                         ["ground_realtime", "ground_high_baked", f"ground_high_{sheen}",
                          "ground_high_ld_hybrid_nospec"])
        grid = B.variants(self.lights, "ground", "high", grid=True, reference=True)
        self.assertEqual(len(grid), 13)
        self.assertEqual(grid[-1], {**grid[0], "tag": grid[0]["tag"] + "_ld", "lights": "dynamic",
                                    "modes": ["hybrid_nospec"]})
        self.assertNotIn("lights", grid[0])  # the reference is a copy

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            B.shot_rows("ground", [{"tag": "x", "modes": ["daylight"]}])

    def test_references_put_the_right_one_first(self):
        rows = [{**r, "zone": "ground"} for r in B.shot_rows("ground", B.diag_variants(self.lights, "ground"))]
        self.assertEqual(_house_bake.references("ground", rows, True),
                         ["ground_t8_d0_e15_ld_hybrid_nospec", "ground_realtime", "ground_realtime_shadow",
                          "ground_realtime_shadow_nospec", "ground_t8_d0_e15_ld_hybrid"])
        rows = [{**r, "zone": "ground"} for r in
                B.shot_rows("ground", B.variants(self.lights, "ground", "high", reference=True))]
        self.assertEqual(_house_bake.references("ground", rows, False),
                         ["ground_high_ld_hybrid_nospec", "ground_realtime"])


class EditorRefusedByDay(unittest.TestCase):
    """The editor parts refuse outside the night window before any Godot run; a real bake is never run here."""

    def test_bake_refused_at_noon(self):
        boom = mock.Mock(side_effect=AssertionError("no Godot run by day"))
        with mock.patch.object(_house_bake.time, "time", return_value=at(12)),                 mock.patch.object(B, "grant_text", return_value=None),                 mock.patch.object(_house_bake._godot, "godot", boom),                 mock.patch.object(_house_bake, "stage", boom):
            with self.assertRaises(common.Failure) as caught:
                _house_bake.run({}, {"zones": {"ground": {}}}, ["ground"], "high", None, False, {}, grid=True)
        self.assertIn("00:00 and 08:00", str(caught.exception))
        boom.assert_not_called()

    def test_unknown_zone(self):
        with self.assertRaises(common.Failure):
            _house_bake.run({}, {"zones": {}}, ["nowhere"], "high", None, True, {})


class Project(unittest.TestCase):
    def test_the_bake_scripts_and_plugin_are_in_the_godot_project(self):
        g = common.ROOT / "godot"
        for rel in ("house/zone_build.gd", "house/bake_shots.gd", "addons/lmbake/lmbake.gd", "addons/lmbake/plugin.cfg"):
            self.assertTrue((g / rel).is_file(), rel)
        self.assertIn('"res://addons/lmbake/plugin.cfg"', (g / "project.godot").read_text(encoding="utf-8"))
        build = (g / "house/zone_build.gd").read_text(encoding="utf-8")
        self.assertIn("0.1", build)  # ABOVE_OTHER_K
        self.assertIn("texel / 5.0", build)  # PROP_TEXEL_PER_M


if __name__ == "__main__":
    unittest.main()
