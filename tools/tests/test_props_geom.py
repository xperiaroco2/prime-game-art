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
        cls.built = {p["id"]: prop_geom.build(p, SPEC) for p in PROC}

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


if __name__ == "__main__":
    unittest.main()


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
