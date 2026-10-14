"""The dressing library's geometry (tools/blender/prop_geom.py, docs/props.md): every procedural prop of
props/library.toml builds at its inventory size, under its class's triangle maximum, in its own paints, at its pivot,
with its collider and (fixtures) its light anchor; the primitives are closed; the pack paint clusters dark to light.
Pure Python, no Blender."""

from __future__ import annotations

import json
import sys
import unittest

from runner import common
from runner.commands import _props

sys.path.insert(0, str(common.ROOT / "tools" / "blender"))
import kit_geom  # noqa: E402
import prop_geom  # noqa: E402

LIB = _props.load()
KIT = json.loads((common.ROOT / LIB["kit_spec"]).read_text(encoding="utf-8"))
SPEC = prop_geom.lib_spec(LIB, KIT)
STYLE = prop_geom.Style.from_lib(LIB)
PROC = [p for p in LIB["prop"] if p["route"] == "proc"]


def _edges(m: kit_geom.Mesh) -> dict:
    count: dict = {}
    for f in m.faces:
        for i in range(len(f)):
            e = tuple(sorted((f[i], f[(i + 1) % len(f)])))
            count[e] = count.get(e, 0) + 1
    return count


class PrimitiveTest(unittest.TestCase):
    def assert_closed(self, m: kit_geom.Mesh) -> None:
        self.assertTrue(all(n == 2 for n in _edges(m).values()), "every edge has two faces")

    def test_soft_box_is_closed(self):
        m = kit_geom.Mesh("t")
        prop_geom.cbox(m, (0, 0, 0), (1, 0.5, 0.3), "wood_mid")
        self.assertEqual(len(m.faces), 26)
        self.assert_closed(m)

    def test_cylinder_tube_and_blob_are_closed(self):
        for build in (lambda m: prop_geom.cyl(m, "y", (0, 0), 0.3, 0, 1, "stone", 8),
                      lambda m: prop_geom.cyl(m, "x", (0, 0), 0.3, 0, 1, "stone", 8, r1=0.0),
                      lambda m: prop_geom.tube(m, "z", (0, 0), 0.2, 0.3, 0, 0.2, "rubber", 10),
                      lambda m: prop_geom.blob(m, (0, 0.5, 0), 0.4, 0.5, 0.3, "mustard", 8, 5),
                      lambda m: prop_geom.bar(m, (0, 0, 0), (0.3, 1, 0.2), 0.05, "fence"),
                      lambda m: prop_geom.rod(m, (0, 0, 0), (0, 1, 0), 0.05, "fence")):
            m = kit_geom.Mesh("t")
            build(m)
            self.assert_closed(m)

    def test_faces_point_outward(self):
        m = kit_geom.Mesh("t")
        prop_geom.cyl(m, "y", (0, 0), 0.3, 0, 1, "stone", 8)
        for f in m.faces:
            pts = [m.verts[i] for i in f]
            n = kit_geom.polygon_normal(pts)
            c = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            self.assertGreater(n[0] * c[0] + n[1] * (c[1] - 0.5) + n[2] * c[2], 0)


class LibraryGeometryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = {p["id"]: prop_geom.build(p, SPEC, STYLE) for p in PROC}

    def test_every_shape_has_a_builder(self):
        self.assertEqual(sorted({p["shape"] for p in PROC} - set(prop_geom.BUILDERS)), [])

    def test_size_matches_the_inventory(self):
        for p in PROC:
            d = self.built[p["id"]]
            want = _props.size_xyz(p["size_m"])
            for err, w in zip(prop_geom.size_error(d, p), want):
                self.assertLessEqual(abs(err), max(0.03, 0.12 * w), f"{p['id']}: built {d['size_m']}, want {want}")

    def test_budget_and_paints(self):
        for p in PROC:
            d = self.built[p["id"]]
            self.assertLessEqual(d["triangles"], LIB["budgets"][p["class"]][1], p["id"])
            self.assertLessEqual(set(d["roles"]), set(p["roles"]), p["id"])
            mats = {SPEC["roles"][r]["material"] for r in d["roles"]}
            self.assertLessEqual(len(mats), LIB["max_materials"], p["id"])

    def test_pivot(self):
        for p in PROC:
            b = self.built[p["id"]]["bounds_m"]
            lo, hi = b["min"], b["max"]
            self.assertAlmostEqual(lo[0] + hi[0], 0.0, places=3, msg=p["id"])
            if p["pivot"] == "ceiling":
                self.assertAlmostEqual(hi[1], 0.0, places=4, msg=p["id"])
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=p["id"])
            elif p["pivot"] == "wall":
                self.assertAlmostEqual(lo[1], 0.0, places=4, msg=p["id"])
                self.assertAlmostEqual(lo[2], 0.0, places=4, msg=p["id"])
            else:
                self.assertAlmostEqual(lo[1], 0.0, places=4, msg=p["id"])
                self.assertAlmostEqual(lo[2] + hi[2], 0.0, places=3, msg=p["id"])

    def test_colliders_and_lights(self):
        for p in PROC:
            d = self.built[p["id"]]
            self.assertEqual(bool(d["colliders"]), p["collision"] != "none", p["id"])
            for c in d["colliders"]:
                self.assertTrue(c["name"].startswith(f"{p['id']}_col") and c["name"].endswith("-convcolonly"))
            lit = any(prop_geom.is_emissive(SPEC, r) for r in d["roles"])
            self.assertEqual(d["light_anchor"] is not None, lit, p["id"])
            if p["class"] == "fixture":
                self.assertTrue(lit, f"{p['id']}: a fixture carries its bulb")

    def test_uvs_cover_every_face(self):
        for p in PROC:
            m = self.built[p["id"]]["meshes"][0]
            self.assertEqual(len(m["uv0"]), len(m["faces"]))
            self.assertEqual(len(m["uv2"]), len(m["faces"]))
            self.assertTrue(all(0.0 <= c <= 1.0 for f in m["uv2"] for uv in f for c in uv), p["id"])

    def test_builds_are_deterministic(self):
        p = next(p for p in PROC if p["id"] == "bookcase")
        self.assertEqual(prop_geom.build(p, SPEC)["meshes"][0]["verts"], self.built["bookcase"]["meshes"][0]["verts"])


class PackPaintTest(unittest.TestCase):
    def test_clusters_are_numbered_dark_to_light(self):
        cols = [(0.9, 0.9, 0.9), (0.02, 0.02, 0.02), (0.85, 0.88, 0.9), (0.3, 0.1, 0.05), (0.03, 0.01, 0.02)]
        labels = prop_geom.cluster(cols, [1.0] * len(cols), 3)
        self.assertEqual(labels[1], labels[4])
        self.assertEqual(labels[0], labels[2])
        self.assertEqual((labels[1], labels[3], labels[0]), (0, 1, 2))

    def test_pack_piece_fits_and_paints(self):
        p = {"id": "t", "size_m": [1.0, 0.5, 2.0], "roles": ["wood_dark", "cream"], "stretch": True, "yaw_deg": 90,
             "pivot": "floor", "collision": "box"}
        cube = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
        faces = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
        rgb = [(0.01, 0.01, 0.01)] * 3 + [(0.8, 0.8, 0.7)] * 3
        pc = prop_geom.pack_piece(p, [{"verts": cube, "faces": faces, "rgb": rgb, "area": [1.0] * 6}], SPEC)
        prop_geom.finish(pc, p, SPEC)
        d = prop_geom.describe(pc, SPEC)
        self.assertEqual(d["size_m"], [1.0, 2.0, 0.5])
        self.assertEqual(pc.mesh.roles, ["wood_dark"] * 3 + ["cream"] * 3)
        self.assertEqual(len(d["colliders"]), 1)



class CleanTest(unittest.TestCase):
    def test_drops_degenerate_and_duplicate_faces(self):
        m = kit_geom.Mesh("t")
        m.verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (2.0, 0.0, 0.0)]
        m.faces = [[0, 1, 2, 3], [3, 2, 1, 0], [0, 1, 1, 2], [0, 1, 4], [0, 0, 1]]
        m.roles = ["a", "b", "c", "d", "e"]
        self.assertEqual(prop_geom.clean(m), 3)
        self.assertEqual(m.faces, [[0, 1, 2, 3], [0, 1, 2]])  # the twin, the flat triangle, the 2-corner face go
        self.assertEqual(m.roles, ["a", "c"])



class FinePackTest(unittest.TestCase):
    """The world look's fine pack in the spec (docs/decisions/2026-10-13-house-world-look.md): one exported material,
    the layer in vertex alpha in steps of 1/16, the paint not divided by a detail mean."""

    def test_fine_roles_export_as_one_material(self) -> None:
        fine_roles = [r for r, v in LIB["roles"].items() if v["material"] == "fine"]
        self.assertGreaterEqual(len(fine_roles), 8)
        self.assertEqual({kit_geom.export_material(SPEC, SPEC["roles"][r]["material"]) for r in fine_roles}, {"fine"})
        self.assertNotIn("fine", SPEC["materials"])

    def test_the_layer_is_the_vertex_alpha(self) -> None:
        names = [layer["name"] for layer in LIB["fine"]["layers"]]
        for role in ("wood_front", "worktop_stone", "steel_warm", "rubber_black"):
            k = names.index(LIB["roles"][role]["layer"])
            self.assertAlmostEqual(kit_geom.role_colour(SPEC, role)[3], 1.0 - k / 16, places=5)
        # the set pack keeps its 0.25 step
        self.assertEqual(kit_geom.layer_alpha(SPEC, "wood"), 0.75)

    def test_the_fine_paint_is_the_hex(self) -> None:
        # no division by a detail mean: the fine shader scales its detail itself
        self.assertEqual(kit_geom.role_colour(SPEC, "steel_warm")[:3], [round(0xc4 / 255, 5), round(0xbc / 255, 5),
                                                                        round(0xb0 / 255, 5)])

    def test_layer_values_and_glass_tint(self) -> None:
        steel = SPEC["materials"]["fine_steel"]
        self.assertEqual((steel["pack"], steel["metallic"], steel["roughness"]), ("fine", 0.6, 0.42))
        self.assertEqual(SPEC["materials"]["fine_wood_front"]["fine_source"], "Wood092")
        glass = SPEC["materials"]["glass_tint"]
        self.assertEqual((glass["alpha"], glass["metallic"], glass["roughness"]), (0.38, 0.15, 0.05))
        self.assertEqual(SPEC["packs"]["fine"]["layers"][0], "fine_wood_front")

    def test_the_plants_library_has_no_fine_pack(self) -> None:
        plain = dict(LIB)
        plain.pop("fine")
        spec = prop_geom.lib_spec(plain, KIT)
        self.assertNotIn("fine", spec["packs"])



KITCHEN = ["fridge", "kitchen_counter", "kitchen_sink", "kitchen_upper", "stove"]


class WorldLookBuilderTest(unittest.TestCase):
    """The world look's style and shared builders (docs/decisions/2026-10-13-house-world-look.md) and the kitchen's
    C2-white props built through them."""

    @classmethod
    def setUpClass(cls) -> None:
        props = {p["id"]: p for p in LIB["prop"]}
        cls.props = {pid: props[pid] for pid in KITCHEN}
        cls.built = {pid: prop_geom.build(p, SPEC, STYLE) for pid, p in cls.props.items()}

    def test_style_reads_the_library(self) -> None:
        s = LIB["style"]
        self.assertEqual((STYLE.bevel, STYLE.bevel_small, STYLE.handle_r, STYLE.plinth, STYLE.worktop),
                         (s["bevel_m"], s["bevel_small_m"], s["handle_radius_m"], s["plinth_m"], s["worktop_m"]))
        self.assertAlmostEqual(STYLE.reach, s["front_thickness_m"] + s["handle_standoff_m"] + s["handle_radius_m"])
        self.assertEqual(prop_geom.Style.from_lib({}), prop_geom.Style())

    def test_the_backsplash_runs_are_exact_tiled_strips(self) -> None:
        props = {p["id"]: p for p in LIB["prop"]}
        for pid, length in (("backsplash_l", 2.7), ("backsplash_r", 2.2)):
            p = props[pid]
            d = prop_geom.build(p, SPEC, STYLE)
            self.assertEqual(prop_geom.size_error(d, p), [0.0, 0.0, 0.0], pid)
            self.assertEqual(d["size_m"][0], length)
            self.assertEqual(d["roles"], ["steel_warm", "tile_splash"])
            self.assertEqual((d["colliders"], p["pivot"], _props.prop_layer(LIB, p)), ([], "wall", "base"))
            self.assertAlmostEqual(d["bounds_m"]["min"][2], 0.0)  # the back on the wall

    def test_front_frame(self) -> None:
        rails, (a, b) = prop_geom.front_frame(0.0, 0.5, 0.0, 0.7, 0.003)
        self.assertEqual(len(rails), 4)
        self.assertEqual([round(v, 4) for v in (*a, *b)], [0.06, 0.06, 0.44, 0.64])
        for lo, hi in rails:  # inside the seam gap
            self.assertTrue(0.003 <= lo[0] < hi[0] <= 0.497 and 0.003 <= lo[1] < hi[1] <= 0.697)
        _, (a, _) = prop_geom.front_frame(0.0, 0.2, 0.0, 0.16, 0.003)  # a small front: narrower rails
        self.assertEqual([round(v, 4) for v in a], [0.036, 0.036])  # 18 % of the width

    def test_handle_span(self) -> None:
        (x0, y0), (x1, y1) = prop_geom.handle_span(0.0, 0.5, 0.0, 0.7, True, "v")
        self.assertEqual([round(v, 4) for v in (x0, y0, x1, y1)], [0.46, 0.48, 0.46, 0.64])
        self.assertEqual(prop_geom.handle_span(0.0, 0.5, 0.0, 0.7, False, "v", low=True)[0], (0.04, 0.06))
        (x0, y0), (x1, y1) = prop_geom.handle_span(0.0, 1.0, 0.6, 0.76, True, "h")
        self.assertEqual((round(y0, 4), round(y1, 4)), (0.68, 0.68))
        self.assertAlmostEqual(x0 + x1, 1.0)

    def test_round_rect(self) -> None:
        pts = prop_geom.round_rect(-0.3, 0.3, -0.2, 0.2, 0.05, 6)
        self.assertEqual(len(pts), 4 * 7)
        self.assertEqual(max(x for x, _ in pts), 0.3)
        self.assertEqual(min(z for _, z in pts), -0.2)
        front = prop_geom.round_rect(-0.3, 0.3, -0.2, 0.2, 0.05, 6, front_only=True)
        self.assertEqual(len(front), 2 * 7 + 2)
        self.assertIn((-0.3, -0.2), front)
        self.assertIn((0.3, -0.2), front)
        m = kit_geom.Mesh("t")
        prop_geom.rslab(m, -0.3, 0.3, 0.0, 1.0, -0.2, 0.2, 0.05, "enamel_white", bottom=True)
        self.assertTrue(all(n == 2 for n in _edges(m).values()), "a closed slab")

    def test_grate_bars(self) -> None:
        bars = prop_geom.grate_bars(0.1, 0.0, 0.15, 0.27, cross=3)
        self.assertEqual(len(bars), 4 + 3 + 1)
        zs = [a[1] for a, b, _ in bars[4:7]]
        self.assertEqual([round(z, 4) for z in zs], [-0.135, 0.0, 0.135])
        for a, b, _ in bars:
            for x, z in (a, b):
                self.assertTrue(-0.05 - 1e-9 <= x <= 0.25 + 1e-9 and -0.27 - 1e-9 <= z <= 0.27 + 1e-9)

    def test_kitchen_props_stay_inside_their_size(self) -> None:
        # round 2's fixes: counter and sink tops, handles and pulls inside size_m (they stood 5 to 10 mm proud)
        for pid, p in self.props.items():
            want = _props.size_xyz(p.get("built_size_m", p["size_m"]))
            for got, w in zip(self.built[pid]["size_m"], want):
                self.assertLessEqual(got, w + 1e-4, f"{pid}: built {self.built[pid]['size_m']}, want {want}")
                self.assertGreaterEqual(got, w - 0.015, f"{pid}: built {self.built[pid]['size_m']}, want {want}")

    def test_kitchen_props_on_the_fine_pack(self) -> None:
        for pid, d in self.built.items():
            mats = {kit_geom.export_material(SPEC, SPEC["roles"][r]["material"]) for r in d["roles"]}
            self.assertLessEqual(mats, {"fine", "glass_tint"}, pid)
            lo, hi = LIB["budgets"][self.props[pid]["class"]]
            self.assertTrue(lo <= d["triangles"] <= hi, f"{pid}: {d['triangles']} triangles, class {lo} to {hi}")

    def test_stove_colliders_leave_the_hood_gap(self) -> None:
        cols = self.built["stove"]["colliders"]
        self.assertEqual(len(cols), 2)
        tops = sorted(max(q[1] for q in c["points"]) for c in cols)
        bottoms = sorted(min(q[1] for q in c["points"]) for c in cols)
        self.assertAlmostEqual(tops[0], 1.04, places=3)  # the stove with its backguard
        self.assertAlmostEqual(bottoms[1], 1.45, places=3)  # the hood
        self.assertEqual(len(self.built["fridge"]["colliders"]), 1)


LIVING = ("sofa", "armchair", "bookcase", "tv_cabinet", "fireplace", "coffee_table", "sideboard", "dresser", "rug",
          "small_table")


class LivingRoomTest(unittest.TestCase):
    """The living room's pieces in the world look (#150): procedural, every paint on the fine pack."""

    def test_the_pieces_are_proc_on_the_fine_pack(self) -> None:
        props = {p["id"]: p for p in LIB["prop"]}
        for pid in LIVING:
            p = props[pid]
            self.assertEqual(p["route"], "proc", pid)
            pc = prop_geom.build_proc(p, STYLE)
            used = set(pc.mesh.roles)
            self.assertTrue(used <= set(p["roles"]), (pid, sorted(used - set(p["roles"]))))
            self.assertEqual({LIB["roles"][r]["material"] for r in used}, {"fine"}, pid)

    def test_the_soft_layers_are_textured(self) -> None:
        layers = {x["name"]: x for x in LIB["fine"]["layers"]}
        for name, src in (("fabric", "Fabric036"), ("weave", "Fabric061"), ("carpet", "Carpet016")):
            self.assertEqual(layers[name]["source"], src)
        names = [x["name"] for x in LIB["fine"]["layers"]]
        self.assertEqual(names[:9], ["wood_front", "worktop_wood", "stone", "tile", "enamel", "steel", "chrome",
                                     "gloss", "paint"])  # the kitchen's GLBs keep their layer indices

    def test_book_runs_stay_on_their_shelf(self) -> None:
        m = kit_geom.Mesh("books")
        prop_geom.book_run(m, -0.4, 0.4, 0.5, -0.15, 0.24, 0.3, ["book_cream", "book_teal"], prop_geom.seed("x"))
        self.assertTrue(m.verts)
        self.assertLessEqual(max(v[0] for v in m.verts), 0.4 + 1e-6)
        self.assertGreaterEqual(min(v[1] for v in m.verts), 0.5 - 1e-6)
        self.assertLessEqual(max(v[1] for v in m.verts), 0.8 + 1e-6)


if __name__ == "__main__":
    unittest.main()
