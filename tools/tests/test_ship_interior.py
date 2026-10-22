"""The ship's INTERIOR pieces (art #263, docs/ship.md): layouts/ship/interior.toml is what ship_interior_place.py
writes from the numbers; every placed piece has a builder that returns a valid mesh; the numbers keep the openings
wide enough, the head room, the corridor's arches clear of the station spots and the cups off them. Pure Python: needs
neither Blender, Godot nor the raw files."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
import ship_interior as S  # noqa: E402
import ship_interior_place as SP  # noqa: E402

with (ROOT / "layouts" / "ship" / "interior.toml").open("rb") as _f:
    INTERIOR = tomllib.load(_f)
with (ROOT / "layouts" / "ship" / "ship.toml").open("rb") as _f:
    SHIP = tomllib.load(_f)


class ShipInteriorTest(unittest.TestCase):
    def test_the_file_is_generated(self) -> None:
        self.assertEqual((ROOT / "layouts" / "ship" / "interior.toml").read_text(encoding="utf-8"), SP.render())

    def test_every_piece_builds_a_valid_mesh(self) -> None:
        for piece in INTERIOR["pieces"]:
            parts = getattr(S, piece["builder"])(piece.get("args", {}), SHIP)
            self.assertTrue(parts, piece["id"])
            for p in parts:
                n = len(p["verts"])
                self.assertTrue(p["faces"], piece["id"])
                self.assertTrue(all(0 <= i < n for f in p["faces"] for i in f), piece["id"])
                self.assertIn(p["mat"], S.L.MATERIALS, piece["id"])

    def test_every_placement_names_a_piece(self) -> None:
        ids = {p["id"] for p in INTERIOR["pieces"]}
        self.assertEqual({p[0] for p in INTERIOR["place"]} - ids, set())
        self.assertEqual(ids - {p[0] for p in INTERIOR["place"]}, set())

    def test_the_numbers_match_ship_toml(self) -> None:
        rooms = {r["id"]: r for r in SHIP["rooms"]}
        self.assertEqual(S.FLOOR, SHIP["deck"]["floor_h"])
        self.assertEqual(S.R_HALL, rooms["hall"]["radius"])
        self.assertEqual((S.H_HALL, S.APEX_HALL), (rooms["hall"]["clear_h"], rooms["hall"]["apex_h"]))
        self.assertEqual((S.H_TIP, S.APEX_TIP), (rooms["tip_e"]["clear_h"], rooms["tip_e"]["apex_h"]))
        self.assertEqual(S.TIP_X, rooms["tip_e"]["centre"][0])
        self.assertEqual(S.H_COR, rooms["corridor_e"]["clear_h"])
        win = rooms["tip_e"]["window"]
        self.assertEqual((S.WIN_HALF, S.SILL, S.HEAD), (win["half_angle_deg"], win["sill_h"], win["head_h"]))
        half = (rooms["corridor_e"]["y"][1] - rooms["corridor_e"]["y"][0]) / 2
        self.assertEqual(max(u for u, _ in S.PROF), half)

    def test_the_openings_take_the_corridor(self) -> None:
        self.assertGreater(S.HCH, 1.25)                    # the hall's chords
        self.assertGreater(S.TIP_CHORD_H, 1.25)            # the tip rooms' chords
        self.assertAlmostEqual(S.COR_X0, 3.353, places=2)  # the corridor modules run portal to portal
        self.assertAlmostEqual(S.COR_X1, 8.936, places=2)

    def test_head_room(self) -> None:
        pl = SHIP["player"]
        need = pl["capsule_height_m"] + pl["head_margin_m"]
        self.assertGreaterEqual(min(v for _, v in S.PROF if v > 0) + 0.0, 1.45)
        self.assertGreaterEqual(S.H_COR, need)
        # at the capsule's edge next to a wall (0.4 m in), the slanted wall leaves the head room
        u_in = 1.25 - pl["capsule_radius_m"]
        (u0, v0), (u1, v1) = (abs(S.PROF[1][0]), S.PROF[1][1]), (abs(S.PROF[2][0]), S.PROF[2][1])
        v_at = v0 + (v1 - v0) * (u0 - u_in) / (u0 - u1) if u_in > u1 else v1
        self.assertGreaterEqual(v_at, pl["capsule_height_m"])

    def test_the_mouth_opens_wide_and_the_window_has_few_mullions(self) -> None:
        # hall_out-2: the mouth's portal and arch take the mouth room's full width and height (inside 3-1)
        mouth = {r["id"]: r for r in SHIP["rooms"]}["mouth"]
        top = max(v for _, v in S.MOUTH_PROF)
        self.assertAlmostEqual(top, mouth["clear_h"], places=3)
        self.assertGreaterEqual(min(v for _, v in S.MOUTH_PROF if v > 0), top - 0.4)
        self.assertGreaterEqual(2 * max(u for u, _ in S.MOUTH_PROF), mouth["x"][1] - mouth["x"][0] - 0.11)
        ids = {p[0] for p in INTERIOR["place"]}
        self.assertTrue({"mouth_portal", "mouth_arch"} <= ids)
        # tip-3: a few thin mullions, the view nearly uninterrupted
        self.assertLessEqual(len(S.MULLIONS), 4)

    def test_arches_and_details_keep_off_the_station_spots(self) -> None:
        spots = SHIP["stations"]["spot"]
        r = SHIP["stations"]["radius_m"]
        for pid, (x, y, _), _yaw in INTERIOR["place"]:
            for s in spots:
                d = math.hypot(x - s["at"][0], y - s["at"][1])
                if pid == "cor_arch" and s.get("at_wall"):
                    self.assertGreater(abs(x - s["at"][0]), r + 0.09, (pid, x, s["id"]))
                if pid.startswith(("cup", "spill", "cable_coil", "floor_patch")):  # the small details
                    self.assertGreater(d, r + 0.4, (pid, x, y, s["id"]))


if __name__ == "__main__":
    unittest.main()
