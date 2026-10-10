"""The chill zone's and the photo gazebo's props (props/zones.toml, art #81b; docs/props.md): the spec, every prop's
size, pivot, budget, collision and UV2, the fixtures' bulbs and light sockets, and the hung strand's pivot. Pure
Python (tools/blender/props_zone.py needs no Blender)."""

from __future__ import annotations

import unittest

from runner import common
from runner.commands import props as props_cmd

G = props_cmd.geom()
SPEC = G.load_spec(common.ROOT / "props" / "zones.toml")
PROPS = {p["id"]: p for p in SPEC["props"]}
BUILT = {d["id"]: d for d in G.build_all(SPEC)}
# The #81b brief: deckchair, fire pit, bean bag, cooler, photo backdrop, camera tripod, lantern, string-light sets.
WANTED = {"deckchair", "fire_pit", "bean_bag", "cooler_box", "photo_backdrop", "tripod_camera", "lantern",
          "string_lights_set", "string_lights_gazebo"}
FIXTURES = {"lantern": 1, "string_lights_set": 3, "string_lights_gazebo": 1, "fire_pit": 1}  # light sockets


class ZoneSpecTest(unittest.TestCase):
    def test_the_spec_is_clean(self) -> None:
        self.assertEqual(G.check_spec(SPEC), [])

    def test_the_brief_props_are_there(self) -> None:
        self.assertEqual(WANTED - set(PROPS), set())

    def test_every_prop_passes_its_checks(self) -> None:
        for p in SPEC["props"]:
            with self.subTest(prop=p["id"]):
                self.assertEqual(G.check_prop(BUILT[p["id"]], p, SPEC), [])

    def test_the_raw_folder_is_the_zones_one(self) -> None:
        self.assertEqual(props_cmd.default_out(SPEC).parts[-2:], ("zones", "v1"))

    def test_the_emissive_material_is_exported(self) -> None:
        self.assertIn("emissive", SPEC["materials"])
        self.assertTrue(SPEC["materials"]["emissive"]["emission"].startswith("#"))


class FixtureTest(unittest.TestCase):
    def test_fixtures_have_bulbs_and_light_sockets(self) -> None:
        for pid, n in FIXTURES.items():
            with self.subTest(prop=pid):
                d = BUILT[pid]
                self.assertEqual(sorted(d["sockets"]), [f"light_{k}" for k in range(n)])
                roles = {r for m in d["meshes"] for r in m["roles"]}
                self.assertTrue(roles & {"bulb", "ember"})

    def test_light_sockets_are_inside_the_prop(self) -> None:
        for pid in FIXTURES:
            b = BUILT[pid]["bounds_m"]
            for name, s in BUILT[pid]["sockets"].items():
                with self.subTest(prop=pid, socket=name):
                    self.assertTrue(all(b["min"][i] - 1e-3 <= s[i] <= b["max"][i] + 1e-3 for i in range(3)))

    def test_the_hung_strand_hangs_from_its_pivot(self) -> None:
        b = BUILT["string_lights_gazebo"]["bounds_m"]
        self.assertAlmostEqual(b["max"][1], 0.0, places=3)
        self.assertAlmostEqual(b["min"][1], -float(PROPS["string_lights_gazebo"]["h"]), places=2)

    def test_a_floor_check_still_catches_a_hung_prop_set_on_the_floor(self) -> None:
        p = dict(PROPS["string_lights_gazebo"], mount="floor")
        self.assertTrue(any("not on the floor" in s for s in G.check_prop(BUILT[p["id"]], p, SPEC)))


if __name__ == "__main__":
    unittest.main()
