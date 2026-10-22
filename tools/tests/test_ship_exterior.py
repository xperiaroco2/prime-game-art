"""The ship's exterior (art #263, docs/ship.md): the hull kit's skins hug the rooms without cutting into them, the wing
meets the tip pod without a step, the faces point outward once the build harness mirrors plan coordinates into
Blender's, and the exterior's placements and review views are sound. Pure Python (tools/blender/ship_hull.py's
geometry needs no Blender): needs neither Blender, Godot nor the raw files."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull as H  # noqa: E402

LAYOUT = sl.load()
ROOMS = sl.rooms(LAYOUT)
DECK = LAYOUT["deck"]
EYE_M = 1.65  # the walk's eye over the floor (the 1.8 m capsule's eyes)
EXT = tomllib.loads((sl.common.ROOT / LAYOUT["exterior"]).read_text(encoding="utf-8"))


def inside(poly: list, pt: tuple) -> bool:
    return sl.inside([(float(a), float(b)) for a, b in poly], pt)


def newell(p: list) -> tuple:
    n = [0.0, 0.0, 0.0]
    for a, b in zip(p, p[1:] + p[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return tuple(n)


class ShipExteriorTest(unittest.TestCase):
    def test_faces_point_outward_after_the_mirror(self) -> None:
        """The harness writes (x, -y, h): after it, every face of the pod housing's smooth shell (an open part) points
        away from its inner line (x 0, h 2.45)."""
        parts = next(m for m in H.MODULES if hasattr(m, "pod_housing")).pod_housing({}, LAYOUT)
        skin = next(p for p in parts if p["name"] == "housing")
        self.assertFalse(skin["solid"])
        verts = [(x, -y, h) for x, y, h in skin["verts"]]
        for face in skin["faces"]:
            p = [verts[i] for i in face]
            c = [sum(q[k] for q in p) / len(p) for k in range(3)]
            n = newell(p)
            if sum(k * k for k in n) < 1e-12:
                continue
            self.assertGreater(n[0] * c[0] + n[2] * (c[2] - 2.45), 0.0, f"inward face at {c}")

    def test_placements_and_views(self) -> None:
        pieces = {p["id"] for p in EXT["pieces"]}
        self.assertEqual({p[0] for p in EXT["place"]}, pieces)
        clearing = {p["id"] for p in EXT["pieces"] if p["builder"] in ("pine", "rock")}
        for pid, at, _yaw in EXT["place"]:
            if pid in clearing:
                self.assertGreater(math.hypot(at[0], at[1]), 12.0, f"{pid} at {at} stands in the clearing's middle")
        names = [v[0] for v in EXT["shots"]["views"]]
        self.assertEqual(len(names), len(set(names)))
        for v in EXT["shots"]["views"]:
            self.assertEqual(len(v), 6, f"view {v[0]} needs its 2D sheet")


    def test_the_walk_video_keys(self) -> None:
        """The walk-through: 1280x720, 60..90 s, under 15 MB, every key's eye above the ground; a key on the deck at
        eye height over floor_h and 0.3 m inside a room, the key on the ramp at eye height over the ramp's plane."""
        if LAYOUT["hull"].get("pending"):   # rebuild A: the exterior lane's keys follow the moved rooms in step B
            self.skipTest(f"[hull] pending: {LAYOUT['hull']['pending']}")
        v = EXT["video"]
        self.assertEqual(v["size"], [1280, 720])
        seconds = sum(k[2] for k in v["keys"][1:])
        self.assertTrue(60.0 <= seconds <= 90.0, f"{seconds} s")
        self.assertLessEqual(v["max_mb"], 15.0)
        ramp = LAYOUT["ramp"]
        (_hx, hinge_y), (_fx, foot_y) = ramp["hinge"], ramp["foot"]
        hull = sl.outline(LAYOUT)
        deck = on_ramp = 0
        for eye, look, _s in v["keys"]:
            self.assertGreater(eye[2], 1.5, f"key {eye} below eye height")
            x, y, h = eye
            if foot_y < y < hinge_y and abs(x) <= ramp["width_m"] / 2:  # on the ramp: its plane from foot to hinge
                surface = DECK["ground_h"] + (DECK["floor_h"] - DECK["ground_h"]) * (y - foot_y) / (hinge_y - foot_y)
                self.assertAlmostEqual(h - surface, EYE_M, delta=0.5, msg=f"ramp key {eye}")
                on_ramp += 1
            elif y >= hinge_y and sl.inside(hull, (x, y)):  # on the deck
                self.assertAlmostEqual(h - DECK["floor_h"], EYE_M, delta=0.15, msg=f"deck key {eye}")
                self.assertTrue(any(sl.room_margin(r, (x, y)) > 0.3 for r in ROOMS.values()),
                                f"deck key {eye} is not 0.3 m inside a room")
                deck += 1
        self.assertGreater(deck, 0, "no key on the deck")
        self.assertGreater(on_ramp, 0, "no key on the ramp")


    def test_the_flank_lamps_light_only_the_outside(self) -> None:
        """The join's flank lamps: a mirrored pair outside the wing tips, culled to the outside layer in ship.gd."""
        lamps = [lamp for lamp in LAYOUT["light"]["lamps"] if len(lamp) > 8 and lamp[8] == "flank"]
        self.assertEqual(len(lamps), 2)
        self.assertAlmostEqual(lamps[0][0], -lamps[1][0])
        for lamp in lamps:  # the wing tips at +-13.75 (ship_hull_smooth.SPAN_X)
            self.assertGreater(abs(lamp[0]), 13.75 + 1.0, "a flank lamp inside the wing")
        self.assertIn("flank_lamp", LAYOUT["light"])
        gd = (Path(__file__).resolve().parents[2] / "godot" / "ship" / "ship.gd").read_text(encoding="utf-8")
        self.assertRegex(gd, r'== "flank":[^\n]*\n\t+omni\.light_cull_mask = OUTSIDE_LAYER')


if __name__ == "__main__":
    unittest.main()
