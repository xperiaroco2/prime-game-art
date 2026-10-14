"""The task props in the world look (art #82; props/tasks.toml `look = "fine"`, tools/blender/props_task_fine.py,
docs/props.md): every task-chain prop is on the fine pack, keeps the spec's size, pivot, budget and colliders, and
the state pieces the game shows or hides (the generator's and the switches' on and off, the printer's photo, the lids)
are there and differ. Pure Python (no Blender)."""

from __future__ import annotations

import unittest

from runner.commands import props as props_cmd

G = props_cmd.geom()
F = G.props_task_fine
SPEC = G.load_spec(props_cmd.SPEC)
PROPS = {p["id"]: p for p in SPEC["props"]}
BUILT = {p["id"]: G.describe(G.build_prop(p, SPEC), SPEC) for p in SPEC["props"]}

# The five task chains' props (#82); the car lift and its panel are the garage's (#79).
TASK_PROPS = {"delivery_box_stack", "wine_rack", "wine_rack_freestanding", "dining_table", "terrace_table",
              "garden_dropoff", "workbench", "order_board", "assembly_island", "bun_shelf", "meat_freezer", "bbq_grill",
              "herb_bed", "herb_board", "generator", "wall_switch", "wall_switch_post", "pose_screen", "computer_set",
              "photo_printer", "photo_board", "car_parts_shelf"}
STATES = {"generator": ("on", "off"), "wall_switch": ("on", "off"), "wall_switch_post": ("on", "off"),
          "photo_printer": ("photo",), "meat_freezer": ("lid",), "bbq_grill": ("lid",)}


def mesh(pid: str, node: str) -> dict:
    return next(m for m in BUILT[pid]["meshes"] if m["name"] == f"{pid}_{node}")


class FineTaskPropsTest(unittest.TestCase):
    def test_every_task_prop_is_in_the_world_look(self) -> None:
        self.assertEqual({pid for pid in TASK_PROPS if PROPS[pid].get("look") != "fine"}, set())

    def test_the_paint_map_is_clean(self) -> None:
        self.assertEqual(F.check_paints(SPEC), [])

    def test_each_is_on_the_fine_pack_and_checks_clean(self) -> None:
        for pid in sorted(TASK_PROPS):
            with self.subTest(pid):
                roles = {r for m in BUILT[pid]["meshes"] for r in m["roles"]}
                self.assertEqual(F.off_roles(roles, SPEC), [])
                self.assertEqual(G.check_prop(BUILT[pid], PROPS[pid], SPEC), [])

    def test_size_pivot_budget_and_colliders(self) -> None:
        for pid in sorted(TASK_PROPS):
            p, d = PROPS[pid], BUILT[pid]
            with self.subTest(pid):
                b = d["bounds_m"]
                for i, key in ((0, "w"), (1, "h"), (2, "d")):
                    self.assertAlmostEqual(b["max"][i] - b["min"][i], float(p[key]), delta=G.SIZE_TOLERANCE_M)
                self.assertAlmostEqual(b["min"][1], 0.0, delta=0.002)
                self.assertAlmostEqual(b["min"][0] + b["max"][0], 0.0, delta=2 * G.SIZE_TOLERANCE_M)
                self.assertAlmostEqual(b["min"][2] + b["max"][2], 0.0, delta=2 * G.SIZE_TOLERANCE_M)
                self.assertLessEqual(d["triangles"], SPEC["budget_tris"][p["kind"]])
                self.assertGreater(len(d["colliders"]), 0)

    def test_the_state_pieces_are_there_and_read_apart(self) -> None:
        for pid, nodes in STATES.items():
            with self.subTest(pid):
                self.assertEqual(set(PROPS[pid].get("nodes", [])), set(nodes))
                for node in nodes:
                    self.assertTrue(mesh(pid, node)["faces"])
        for pid in ("generator", "wall_switch", "wall_switch_post"):
            with self.subTest(pid):
                self.assertIn("signal_green", mesh(pid, "on")["roles"])
                self.assertNotIn("signal_red", mesh(pid, "on")["roles"])
                self.assertIn("signal_red", mesh(pid, "off")["roles"])
                self.assertNotIn("signal_green", mesh(pid, "off")["roles"])

    def test_the_boards_keep_one_flat_named_surface(self) -> None:
        for pid in ("order_board", "herb_board", "pose_screen", "photo_board", "computer_set"):
            with self.subTest(pid):
                (s,) = BUILT[pid]["surfaces"]
                self.assertEqual(s["corners"], 4)
                self.assertGreater(s["normal"][2], 0)
                self.assertEqual(SPEC["roles"]["game_surface"]["material"], G.SURFACE_MATERIAL)


if __name__ == "__main__":
    unittest.main()
