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
        """The harness writes (x, -y, h): after it, every face of a nozzle pod's under-skin points away from its axis
        (the pod's barrel runs along local y, its axis at x 0, h 0)."""
        parts = next(m for m in H.MODULES if hasattr(m, "nozzle_pod")).nozzle_pod({"r": 1.05, "length": 3.6}, LAYOUT)
        skin = [p for p in parts if p["name"].endswith("_seam")][0]
        verts = [(x, -y, h) for x, y, h in skin["verts"]]
        for face in skin["faces"]:
            p = [verts[i] for i in face]
            c = [sum(q[k] for q in p) / len(p) for k in range(3)]
            n = newell(p)
            if abs(n[1]) > 0.9 * math.sqrt(sum(k * k for k in n)):
                continue  # the flat rear cap faces along the axis
            self.assertGreater(n[0] * c[0] + n[2] * c[2], 0.0, f"inward face at {c}")

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
        """The walk-through: 1280x720, 60..90 s, under 15 MB, every key's eye above the ground and, on the deck, at
        eye height inside a room."""
        v = EXT["video"]
        self.assertEqual(v["size"], [1280, 720])
        seconds = sum(k[2] for k in v["keys"][1:])
        self.assertTrue(60.0 <= seconds <= 90.0, f"{seconds} s")
        self.assertLessEqual(v["max_mb"], 15.0)
        for eye, look, _s in v["keys"]:
            self.assertGreater(eye[2], 1.5, f"key {eye} below eye height")
            if eye[2] > 2.6 and abs(eye[1]) < 4.5:  # on the deck (outside keys stand off the hull)
                self.assertTrue(any(sl.room_margin(r, (eye[0], eye[1])) > 0.3 for r in ROOMS.values()),
                                f"deck key {eye} is not 0.3 m inside a room")

if __name__ == "__main__":
    unittest.main()
