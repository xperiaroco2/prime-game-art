"""The House map's procedural props (props/tasks.toml, docs/props.md): the spec, every prop's size, pivot, budget,
collision and UV2, the game surfaces, the state meshes and the hinged lids, and the stations of the five task
chains. Pure Python (tools/blender/props_task.py needs no Blender)."""

from __future__ import annotations

import copy
import unittest

from runner.commands import props as props_cmd

G = props_cmd.geom()
SPEC = G.load_spec(props_cmd.SPEC)
PROPS = {p["id"]: p for p in SPEC["props"]}
BUILT = {d["id"]: d for d in G.build_all(SPEC)}

# inventory.md section 7: the game markers whose props #82 builds (the car and its lift wait for #79).
STATIONS = {"WineRack", "Boxes", "DiningTable", "TerraceTable", "GardenDropOff", "Workbench", "Generator", "SwitchA",
            "SwitchB", "SwitchC", "SwitchD", "OrderBoard", "Buns", "Meat", "Grill", "HerbBoard", "HerbBeds",
            "PoseScreen", "Printer", "PhotoBoard", "PartsShelf", "Speaker"}
# The manager's list of room-defining props no other package owns.
ROOM_PROPS = {"boiler", "pump", "water_tank", "switchboard", "cable_drum", "enlarger", "tray_table", "toy_chest",
              "utility_pole", "birdbath", "bulkhead_stairs"}
BOARDS = {"order_board", "herb_board", "pose_screen", "photo_board"}


class SpecTest(unittest.TestCase):
    def test_the_spec_is_clean(self) -> None:
        self.assertEqual(G.check_spec(SPEC), [])

    def test_every_station_has_a_prop(self) -> None:
        covered = {s.strip() for p in SPEC["props"] for s in p["station"].split(",")}
        self.assertEqual(STATIONS - covered, set())

    def test_the_room_defining_props_are_there(self) -> None:
        self.assertEqual(ROOM_PROPS - set(PROPS), set())

    def test_wall_props_have_a_free_standing_variant(self) -> None:
        self.assertEqual(PROPS["wall_switch"]["mount"], "wall")
        self.assertEqual(PROPS["wall_switch_post"]["mount"], "post")
        self.assertEqual(PROPS["wine_rack"]["mount"], "wall")
        self.assertEqual(PROPS["wine_rack_freestanding"]["mount"], "floor")

    def test_prop_roles_keep_the_kit_roles(self) -> None:
        self.assertEqual(SPEC["clashes"], [])
        self.assertIn("trim", SPEC["roles"])
        self.assertEqual(SPEC["roles"]["game_surface"]["material"], G.SURFACE_MATERIAL)

    def test_a_clash_with_a_kit_role_is_reported(self) -> None:
        spec = copy.deepcopy(SPEC)
        spec["clashes"] = ["trim"]
        self.assertIn("role trim: redefines a kit role", G.check_spec(spec))


class PropTest(unittest.TestCase):
    def test_every_prop_passes_its_checks(self) -> None:
        for pid, d in BUILT.items():
            self.assertEqual(G.check_prop(d, PROPS[pid], SPEC), [], pid)

    def test_a_wrong_size_is_reported(self) -> None:
        p = dict(PROPS["generator"], w=2.0)
        self.assertTrue(any("is not the spec's" in s for s in G.check_prop(BUILT["generator"], p, SPEC)))

    def test_pivot_on_the_floor_and_centred(self) -> None:
        for pid, d in BUILT.items():
            b = d["bounds_m"]
            self.assertAlmostEqual(b["min"][1], 0.0, delta=0.002, msg=pid)
            self.assertAlmostEqual(b["min"][0] + b["max"][0], 0.0, delta=0.02, msg=pid)
            self.assertAlmostEqual(b["min"][2] + b["max"][2], 0.0, delta=0.02, msg=pid)

    def test_boards_have_one_flat_game_surface_with_uv_0_to_1(self) -> None:
        for pid in BOARDS | {"computer_set"}:
            d = BUILT[pid]
            self.assertEqual(len(d["surfaces"]), 1, pid)
            s = d["surfaces"][0]
            self.assertEqual(s["corners"], 4, pid)
            self.assertGreater(s["normal"][2], 0, pid)
            mesh = next(m for m in d["meshes"] if m["name"] == s["mesh"])
            uvs = sorted(tuple(uv) for uv in mesh["uv0"][s["face"]])
            self.assertEqual(uvs, [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)], pid)
        for pid, d in BUILT.items():
            if pid not in BOARDS | {"computer_set"}:
                self.assertEqual(d["surfaces"], [], pid)

    def test_the_board_surface_is_the_planned_size(self) -> None:
        for pid in BOARDS:
            bw, bh = PROPS[pid]["board"]
            fr = PROPS[pid].get("frame", 0.05)
            self.assertEqual(BUILT[pid]["surfaces"][0]["size_m"], [round(bw - 2 * fr, 4), round(bh - 2 * fr, 4)], pid)

    def test_switches_have_two_state_meshes(self) -> None:
        for pid in ("wall_switch", "wall_switch_post"):
            names = {m["name"]: m for m in BUILT[pid]["meshes"]}
            on, off = names[f"{pid}_on"], names[f"{pid}_off"]
            self.assertIn("lamp_green", on["roles"])
            self.assertNotIn("lamp_red", on["roles"])
            self.assertIn("lamp_red", off["roles"])
            self.assertNotIn("lamp_green", off["roles"])
            # the lever points up when on, down when off
            self.assertGreater(max(v[1] for v in on["verts"]), max(v[1] for v in off["verts"]))

    def test_lids_are_leaves_hinged_at_the_back(self) -> None:
        for pid in ("meat_freezer", "bbq_grill", "toy_chest"):
            lid = next(m for m in BUILT[pid]["meshes"] if m["name"] == f"{pid}_lid")
            self.assertLess(lid["origin"][2], 0.0, pid)
            self.assertTrue(any(c["parent"] == lid["name"] for c in BUILT[pid]["colliders"]), pid)

    def test_the_printer_has_its_photo(self) -> None:
        self.assertIn("photo_printer_photo", {m["name"] for m in BUILT["photo_printer"]["meshes"]})

    def test_rays_cross_every_collider_off_its_centre(self) -> None:
        for pid, d in BUILT.items():
            rays = props_cmd.rays(d)
            self.assertEqual(len(rays), len(d["colliders"]), pid)
            for (start, end), c in zip(rays, d["colliders"]):
                lo = [min(p[i] for p in c["points"]) for i in range(3)]
                hi = [max(p[i] for p in c["points"]) for i in range(3)]
                self.assertTrue(all(lo[i] < end[i] < hi[i] for i in range(3)), (pid, c["name"]))
                self.assertTrue(any(start[i] < lo[i] for i in range(3)), (pid, c["name"]))

    def test_the_table_lists_every_prop(self) -> None:
        rows = G.prop_table(list(BUILT.values()), SPEC)
        md = G.table_md(rows)
        for pid in PROPS:
            self.assertIn(f"| {pid} |", md)


class SurfaceMaterialTest(unittest.TestCase):
    def test_the_surface_material_follows_the_spec(self) -> None:
        with_it = {"materials": [{"name": "kit_wood-vcol"}, {"name": "surface_game-vcol"}]}
        without = {"materials": [{"name": "kit_wood-vcol"}]}
        board, table = PROPS["order_board"], PROPS["dining_table"]
        self.assertEqual(props_cmd.check_surface_material(with_it, board, G.SURFACE_MATERIAL), [])
        self.assertEqual(props_cmd.check_surface_material(without, table, G.SURFACE_MATERIAL), [])
        self.assertEqual(len(props_cmd.check_surface_material(without, board, G.SURFACE_MATERIAL)), 1)
        self.assertEqual(len(props_cmd.check_surface_material(with_it, table, G.SURFACE_MATERIAL)), 1)


if __name__ == "__main__":
    unittest.main()
