"""The House kit (kits/house.json, docs/kit.md): the spec on its grid, every piece's geometry, collision, UV2 and
budget, the paint's sRGB encoding, the rays and the GLB and Godot assertions. Pure Python (tools/blender/kit_geom.py
needs no Blender); the check of the built GLBs skips when they are missing."""

from __future__ import annotations

import copy
import unittest

from runner.commands import _export, _kit

G = _kit.geom()
SPEC = G.load_spec(_kit.SPEC)
KIT = {d["id"]: d for d in G.build_kit(SPEC)}
PIECES = {p["id"]: p for p in SPEC["pieces"]}
OUT = _kit.default_out(SPEC)

# #74's piece list: every kind of piece the issue asks for, by type.
REQUIRED_TYPES = {"wall", "corner", "end", "gable", "floor", "ceiling", "block", "parapet", "stairs", "stairs_open",
                  "ladder", "railing", "fence", "wicket", "gates", "glass", "garage_door"}


class SpecTest(unittest.TestCase):
    def test_the_spec_is_clean(self) -> None:
        self.assertEqual(G.check_spec(SPEC), [])

    def test_every_kind_of_piece_is_there(self) -> None:
        self.assertEqual(REQUIRED_TYPES - {p["type"] for p in SPEC["pieces"]}, set())

    def test_the_grid_of_the_engineer(self) -> None:
        g = SPEC["grid"]
        self.assertEqual((g["floor_to_floor_m"], g["knee_h_m"], g["door_w_m"], g["gate_w_m"]), (3.2, 2.2, 1.4, 8.0))
        self.assertAlmostEqual(g["door_h_m"], 2.15, delta=0.05)
        self.assertEqual(g["modules_m"], [1, 2])

    def test_wall_openings_by_name(self) -> None:
        for p in SPEC["pieces"]:
            if p["type"] == "wall" and p.get("opening"):
                self.assertIn(p["opening"], G.openings(SPEC["grid"]), p["id"])

    def test_check_spec_finds_faults(self) -> None:
        bad = copy.deepcopy(SPEC)
        bad["pieces"].append(copy.deepcopy(bad["pieces"][0]))
        wall = next(p for p in bad["pieces"] if p["type"] == "wall")
        wall["length"] = 3
        bad["grid"]["slab_m"] = 0.3
        problems = "\n".join(G.check_spec(bad))
        self.assertIn("the id is used twice", problems)
        self.assertIn("is not a [1, 2] m module", problems)
        self.assertIn("slab_m + storey_wall_h_m", problems)

    def test_off_grid_size_is_refused(self) -> None:
        bad = copy.deepcopy(SPEC)
        floor = next(p for p in bad["pieces"] if p["type"] == "floor")
        floor["size"] = [2.5, floor["size"][1]]
        self.assertTrue(any("not whole metres" in s for s in G.check_spec(bad)))

    def test_the_line_up_shows_every_piece_once(self) -> None:
        ids = [i for g in _kit.lineup_groups(SPEC["pieces"]) for i in g[1]]
        self.assertEqual(sorted(ids), sorted(PIECES))
        self.assertEqual([g for g in _kit.lineup_groups(SPEC["pieces"]) if g[0] == "other"], [])


class PieceTest(unittest.TestCase):
    def test_every_piece_passes_its_checks(self) -> None:
        problems = [s for pid, d in KIT.items() for s in G.check_piece(d, PIECES[pid], SPEC)]
        self.assertEqual(problems, [])

    def test_within_budget_and_collided(self) -> None:
        for pid, d in KIT.items():
            self.assertLessEqual(d["triangles"], SPEC["budget_tris"][d["kind"]], pid)
            self.assertTrue(d["colliders"], pid)
            for c in d["colliders"]:
                self.assertGreaterEqual(len(c["points"]), 4, c["name"])
                self.assertTrue(c["name"].endswith("-convcolonly"), c["name"])

    def test_uv2_is_one_island_per_face_inside_the_unit_square(self) -> None:
        for d in KIT.values():
            for m in d["meshes"]:
                self.assertEqual(len(m["uv2"]), len(m["faces"]), m["name"])
                for face, uvs in zip(m["faces"], m["uv2"]):
                    self.assertEqual(len(face), len(uvs))
                    for u, v in uvs:
                        self.assertTrue(-1e-6 <= u <= 1 + 1e-6 and -1e-6 <= v <= 1 + 1e-6, m["name"])

    def test_storey_wall_is_on_the_grid(self) -> None:
        wall = next(d for pid, d in KIT.items() if PIECES[pid]["type"] == "wall" and PIECES[pid].get("length") == 2
                    and not PIECES[pid].get("opening"))
        b = wall["bounds_m"]
        self.assertAlmostEqual(b["min"][0], 0.0, delta=0.08)
        self.assertAlmostEqual(b["max"][0], 2.0, delta=0.12)
        self.assertAlmostEqual(b["min"][1], 0.0, places=4)

    def test_flight_climbs_one_storey(self) -> None:
        p = PIECES["stairs_main"]
        h, going, n = G.stair_numbers(p)
        self.assertAlmostEqual(h * n, float(p["rise"]))
        self.assertAlmostEqual(going * (n - 1), float(p["run"]))
        self.assertAlmostEqual(float(p["rise"]), SPEC["grid"]["floor_to_floor_m"])
        poly = G.ramp_poly(p)
        self.assertEqual(poly[1], (float(p["run"]), 0))
        self.assertEqual(poly[2], (float(p["run"]), float(p["rise"])))

    def test_flat_collider_is_refused(self) -> None:
        d = copy.deepcopy(KIT["stairs_main"])
        d["colliders"][0]["points"] = [[x, 0.0, z] for x, _, z in d["colliders"][0]["points"]]
        self.assertTrue(any("is flat" in s for s in G.check_piece(d, PIECES["stairs_main"], SPEC)))

    def test_over_budget_is_refused(self) -> None:
        d = copy.deepcopy(KIT["stairs_main"])
        d["triangles"] = SPEC["budget_tris"][d["kind"]] + 1
        self.assertTrue(any("over the" in s for s in G.check_piece(d, PIECES["stairs_main"], SPEC)))


class PaintTest(unittest.TestCase):
    def test_srgb_round_trip(self) -> None:
        for c in (0.0, 0.002, 0.04, 0.2, 0.5, 1.0):
            self.assertAlmostEqual(G.srgb_to_linear(G.linear_to_srgb(c)), c, places=6)

    def test_role_colour_is_srgb_divided_by_the_texture_mean(self) -> None:
        # a textured role: its linear paint divided by TEX_MEAN, encoded back to sRGB
        r = G.role_colour(SPEC, "wall_int")
        lin = G.srgb_to_linear(0x3a / 255) / G.TEX_MEAN
        self.assertAlmostEqual(r[0], G.linear_to_srgb(lin), places=4)
        self.assertEqual(r[3], 1.0)
        # an untextured role keeps its hex as it is
        role = next(k for k, v in SPEC["roles"].items() if not SPEC["materials"][v["material"]].get("source"))
        h = SPEC["roles"][role]["hex"].lstrip("#")
        self.assertAlmostEqual(G.role_colour(SPEC, role)[1], int(h[2:4], 16) / 255, places=4)


def gltf_of(d: dict) -> dict:
    """A minimal glTF JSON that holds the described piece as check_glb wants it."""
    attrs = {"TEXCOORD_0": 0, "TEXCOORD_1": 1, "COLOR_0": 2, "NORMAL": 3, "POSITION": 4}
    meshes = [{"primitives": [{"attributes": dict(attrs)}]} for _ in d["meshes"]]
    nodes = [{"name": m["name"], "mesh": i} for i, m in enumerate(d["meshes"])]
    nodes += [{"name": c["name"]} for c in d["colliders"]]
    return {"nodes": nodes, "meshes": meshes, "materials": [{"name": "kit_plaster-vcol"}]}


class GlbTest(unittest.TestCase):
    D = KIT["stairs_main"]

    def test_a_good_file_passes(self) -> None:
        self.assertEqual(_kit.check_glb(gltf_of(self.D), self.D, len(SPEC["materials"])), [])

    def test_faults_are_found(self) -> None:
        g = gltf_of(self.D)
        del g["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_1"]
        g["materials"].append({"name": "kit_wood"})
        g["nodes"] = [n for n in g["nodes"] if "-convcolonly" not in n["name"]]
        problems = "\n".join(_kit.check_glb(g, self.D, 1))
        self.assertIn("lacks TEXCOORD_1", problems)
        self.assertIn("lacks the -vcol suffix", problems)
        self.assertIn("no collider node", problems)
        self.assertIn("2 materials, the kit has 1", problems)

    @unittest.skipUnless((OUT / "stairs_main.glb").is_file(), f"needs the built kit in {OUT.as_posix()}")
    def test_the_built_files_pass(self) -> None:
        problems = []
        for pid, d in KIT.items():
            glb = OUT / f"{pid}.glb"
            if glb.is_file():
                problems += _kit.check_glb(_export.glb_json(glb), d, len(SPEC["materials"]))
        self.assertEqual(problems, [])


def dump_of(d: dict) -> dict:
    """What check/kit.gd reports for a good import of the described piece."""
    surface = {"material": "kit_plaster", "uv2": True, "color": True, "vertex_colour_albedo": True,
               "vertex_colour_srgb": True}
    meshes = [{"name": m["name"], "triangles": m["triangles"], "surfaces": [dict(surface)]} for m in d["meshes"]]
    bodies = [{"name": c["name"], "shapes": [{"class": "ConvexPolygonShape3D", "points": len(c["points"])}]}
              for c in d["colliders"]]
    return {"meshes": meshes, "bodies": bodies, "bounds": copy.deepcopy(d["bounds_m"]),
            "hits": [[0.0, 0.0, 0.0] for _ in d["colliders"]]}


class GodotTest(unittest.TestCase):
    D = KIT["wall_storey_2m_door_int"]

    def test_a_good_import_passes(self) -> None:
        self.assertEqual(_kit.evaluate(dump_of(self.D), self.D), [])

    def test_faults_are_found(self) -> None:
        dump = dump_of(self.D)
        dump["meshes"][0]["surfaces"][0]["vertex_colour_srgb"] = False
        dump["meshes"][0]["surfaces"][0]["uv2"] = False
        dump["bounds"]["max"][1] += 0.5
        dump["hits"][0] = None
        dump["bodies"][0]["shapes"][0]["class"] = "ConcavePolygonShape3D"
        problems = "\n".join(_kit.evaluate(dump, self.D))
        self.assertIn("sRGB vertex colours", problems)
        self.assertIn("has no UV2", problems)
        self.assertIn("size, pivot or Y up", problems)
        self.assertIn("hit nothing", problems)
        self.assertIn("no closed convex shape", problems)

    def test_an_error_is_reported(self) -> None:
        self.assertEqual(_kit.evaluate({"error": "no scene"}, self.D), ["wall_storey_2m_door_int: no scene"])

    def test_every_collider_gets_a_ray_from_outside_into_it(self) -> None:
        for d in KIT.values():
            rays = _kit.rays(d)
            self.assertEqual(len(rays), len(d["colliders"]))
            for (start, end), c in zip(rays, d["colliders"]):
                b = G.bounds(c["points"])
                axis = next(i for i in range(3) if start[i] != end[i])
                self.assertLess(start[axis], b["min"][axis])
                self.assertTrue(all(b["min"][i] - 1e-4 <= end[i] <= b["max"][i] + 1e-4 for i in range(3)))


class TableTest(unittest.TestCase):
    def test_one_row_per_piece(self) -> None:
        rows = G.piece_table(list(KIT.values()))
        md = _kit.table_md(rows, SPEC["budget_tris"])
        self.assertEqual(len(md.strip().splitlines()), len(KIT) + 4)  # the UV2 note, a blank line, the header
        self.assertIn("| stairs_main | stairs |", md)


if __name__ == "__main__":
    unittest.main()


class VersionTwoTest(unittest.TestCase):
    """Art #86: v1's ids stay, the new pieces, the material pack, the seams and the assemblies that must close."""

    V1_IDS = {"wall_storey_2m_ext", "wall_knee_2m_door_int", "floor_boards_2x2", "roof_flat_2x2", "parapet_corner",
              "stairs_main", "ladder_attic", "fence_gates_8m", "glass_door_2m", "garage_door_8m", "gable_tri_2m_up"}

    def test_v1_ids_stay_and_v2_appends(self) -> None:
        self.assertEqual(SPEC["version"], 2)
        ids = [p["id"] for p in SPEC["pieces"]]
        self.assertEqual(self.V1_IDS - set(ids), set())
        self.assertLess(ids.index("garage_door_8m"), ids.index("pillar_concrete"))

    def test_the_new_pieces_are_there(self) -> None:
        for pid in ("pillar_concrete", "roof_pitched_2x2", "roof_pitched_ridge_2m", "glass_roof_2x2", "porch_2x2",
                    "chimney_stack", "cornice_bracket", "fence_post_cap", "gate_post", "gazebo_sector",
                    "gazebo_roof_sector", "wall_knee_end_int", "glass_corner", "glass_end", "slab_edge_2m"):
            self.assertIn(pid, KIT)

    def test_pillar_is_storey_high_and_centred(self) -> None:
        b = KIT["pillar_concrete"]["bounds_m"]
        self.assertEqual((b["min"], b["max"]), ([-0.2, 0.0, -0.2], [0.2, 3.0, 0.2]))

    def test_pitch_is_the_spec_parameter(self) -> None:
        pp = G.pitch(SPEC)
        self.assertAlmostEqual(pp["deg"], 35.0, delta=0.1)
        s2 = copy.deepcopy(SPEC)
        s2["grid"]["gable_rise_per_m"] = 0.35
        d = G.describe(G.build_piece(PIECES["roof_pitched_2x2"], s2), s2)
        self.assertLess(d["bounds_m"]["max"][1], KIT["roof_pitched_2x2"]["bounds_m"]["max"][1] - 0.6)

    def test_knee_door_casing_stays_under_the_wall_top(self) -> None:
        self.assertLessEqual(KIT["wall_knee_2m_door_int"]["bounds_m"]["max"][1], 2.2 + 1e-6)

    def test_ext_end_cap_runs_over_the_slab_band(self) -> None:
        self.assertAlmostEqual(KIT["wall_storey_end_ext"]["bounds_m"]["min"][1], -SPEC["grid"]["slab_m"])
        self.assertAlmostEqual(KIT["wall_storey_end_int"]["bounds_m"]["min"][1], 0.0)

    def test_pack_alpha_and_exported_materials(self) -> None:
        self.assertEqual(G.export_materials(SPEC), ["set", "metal", "glass"])
        self.assertEqual([G.layer_alpha(SPEC, m) for m in ("plaster", "wood", "concrete", "metal")], [1.0, 0.75, 0.5, 1.0])
        self.assertEqual(G.role_colour(SPEC, "boards")[3], 0.75)
        bad = copy.deepcopy(SPEC)
        bad["materials"]["metal"]["pack"] = "set"
        self.assertIn("material metal: not a layer of pack set", G.check_spec(bad))

    def test_no_faces_back_to_back_at_seams(self) -> None:
        self.assertEqual(G.seam_problems(SPEC, KIT), [])

    def test_v1_floor_sides_would_fail_the_seam_check(self) -> None:
        d = copy.deepcopy(KIT["floor_boards_2x2"])
        side = [[2, -0.2, 0], [2, 0, 0], [2, 0, 2], [2, -0.2, 2]]
        other = [[0, -0.2, 0], [0, 0, 0], [0, 0, 2], [0, -0.2, 2]]
        m = d["meshes"][0]
        n = len(m["verts"])
        m["verts"] += side + other
        m["faces"] += [[n, n + 1, n + 2, n + 3], [n + 4, n + 5, n + 6, n + 7]]
        problems = G.seam_problems({"pieces": [PIECES["floor_boards_2x2"]], "grid": SPEC["grid"]},
                                   {"floor_boards_2x2": d})
        self.assertTrue(problems and "back to back" in problems[0])

    def test_the_attic_roof_closes_over_its_span(self) -> None:
        self.assertEqual(G.closure_problems(SPEC, KIT), [])
        placed = G.attic_roof(SPEC, 20, 14)
        self.assertEqual(sum(1 for q in placed if q[0] == "roof_pitched_2x1"), 20)

    def test_a_missing_panel_is_found(self) -> None:
        kit = dict(KIT)
        holed = copy.deepcopy(kit["roof_pitched_2x2"])
        holed["meshes"][0]["faces"] = []
        kit["roof_pitched_2x2"] = holed
        self.assertTrue(G.closure_problems(SPEC, kit, step=0.5))

    def test_the_gazebo_closes(self) -> None:
        self.assertEqual(G.gazebo_problems(SPEC, KIT), [])
        b = KIT["gazebo_roof_sector"]["bounds_m"]
        self.assertAlmostEqual(b["max"][0], 3.0)

    def test_porch_has_its_lamp_socket(self) -> None:
        x, y, z = KIT["porch_2x2"]["sockets"]["lamp"]
        self.assertTrue(0 < x < 2 and 2.15 < y < 2.6 and 0.1 < z < 2.1)

    def test_table_reports_uv2_density(self) -> None:
        rows = G.piece_table([KIT["pillar_concrete"]])
        self.assertGreater(rows[0]["uv2_per_m"], 0.05)
        self.assertIn("UV2 per m", _kit.table_md(rows, SPEC["budget_tris"]))

    def test_a_partial_build_keeps_the_other_rows(self) -> None:  # kit --only (#108): house --bake reads them all
        import json
        import tempfile
        from pathlib import Path

        from runner.commands import kit
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pieces.json"
            path.write_text(json.dumps([{"id": "a", "v": 1}, {"id": "b", "v": 1}, {"id": "c", "v": 1}]), encoding="utf-8")
            rows = kit.merge_rows(path, [{"id": "b", "v": 2}, {"id": "d", "v": 2}], ["a", "b", "c", "d"])
            self.assertEqual([(r["id"], r["v"]) for r in rows], [("a", 1), ("b", 2), ("c", 1), ("d", 2)])
            self.assertEqual(kit.merge_rows(Path(tmp) / "none.json", rows[:1], ["a"]), rows[:1])
