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
    def test_the_wing_encloses_the_corridor(self) -> None:
        cor = ROOMS["corridor_e"]
        wall, bottom = DECK["wall_m"], DECK["floor_h"] - DECK["slab_m"]
        top = DECK["floor_h"] + cor["clear_h"] + DECK["slab_m"]
        half = cor["y"][1] + wall
        for x in (3.7, 4.8, 5.9, 7.0, 8.0, 9.0):
            rows = H._wing_rows(x)
            for corner in ((-half, bottom), (half, bottom), (-half, top - 0.01), (half, top - 0.01)):
                self.assertTrue(inside(rows, corner), f"x {x}: corridor corner {corner} outside the wing")

    def test_the_wing_meets_the_pod(self) -> None:
        rows = H._wing_rows(H.POD_X)
        pod = {round(h, 3): r for r, h in H.POD if r > 0}
        for y, h in rows:
            if round(h, 3) in pod and abs(abs(y) - pod[round(h, 3)]) > 1e-6:
                self.assertAlmostEqual(abs(y), pod[round(h, 3)], places=6, msg=f"step at h {h}")

    def test_the_pod_clears_the_tip_room(self) -> None:
        room = ROOMS["tip_e"]
        wall_out = room["radius"] + DECK["wall_m"]
        rim = DECK["floor_h"] + room["clear_h"]
        for (r0, h0), (r1, h1) in zip(H.POD, H.POD[1:]):
            for t in (0.0, 0.5, 1.0):
                r, h = r0 + (r1 - r0) * t, h0 + (h1 - h0) * t
                if DECK["floor_h"] - DECK["slab_m"] <= h <= rim:
                    self.assertGreaterEqual(r, wall_out + 0.02, f"the pod cuts the tip room's wall at h {h:.2f}")
        self.assertGreater(H.POD[-1][1], DECK["floor_h"] + room["apex_h"] + 0.25)
        self.assertLessEqual(H.POD_X + max(r for r, _ in H.POD), LAYOUT["size"]["width_m"] / 2 + LAYOUT["size"]["tolerance_m"])

    def test_the_drum_clears_the_hall(self) -> None:
        hall = ROOMS["hall"]
        outer = hall["radius"] + DECK["wall_m"]
        rim = DECK["floor_h"] + hall["clear_h"] + DECK["slab_m"]
        for r, h in H.DRUM:
            if DECK["floor_h"] <= h <= rim:
                self.assertGreaterEqual(r, outer, f"the drum cuts the hall's wall at h {h}")
        self.assertGreater(H.DRUM[-1][1], DECK["floor_h"] + hall["apex_h"] + DECK["slab_m"])

    def test_faces_point_outward_after_the_mirror(self) -> None:
        """The harness writes (x, -y, h): after it, every drum face's normal points away from the drum's axis."""
        parts = H.hull_drum({}, LAYOUT)
        skin = [p for p in parts if p["name"].endswith("_seam")][0]
        verts = [(x, -y, h) for x, y, h in skin["verts"]]
        for face in skin["faces"]:
            p = [verts[i] for i in face]
            c = [sum(q[k] for q in p) / len(p) for k in range(3)]
            n = newell(p)
            self.assertGreater(n[0] * c[0] + n[1] * c[1] + n[2] * (c[2] - 2.6), 0.0, f"inward face at {c}")

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


    def test_the_blades_stay_outside_the_rooms_and_the_mouth(self) -> None:
        """The knife-edge flanges along the chines never reach into a room or over the mouth and ramp, and stay
        within the footprint's length."""
        mouth = next(r for r in LAYOUT["rooms"] if r["id"] == "mouth")
        half_ramp = LAYOUT["ramp"]["width_m"] / 2
        for side in (1.0, -1.0):
            for edge in ("lead", "trail"):
                (part,) = H.blade({"side": side, "edge": edge}, LAYOUT)
                for x, y, h in part["verts"]:
                    self.assertGreater(abs(x), max(half_ramp, abs(mouth["x"][0])), f"{edge} blade over the mouth")
                    self.assertTrue(-7.05 < y < 7.0, f"{edge} blade at y {y:.2f} beyond the footprint")
                    for room in ROOMS.values():
                        if room["id"] == "mouth":
                            continue
                        self.assertFalse(sl.room_margin(room, (x, y)) > 0.0 and h < DECK["floor_h"] + room["clear_h"],
                                         f"{edge} blade vertex ({x:.2f}, {y:.2f}, {h:.2f}) inside {room['id']}")

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
