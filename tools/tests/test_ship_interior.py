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


def along(x: float, y: float) -> float:
    """rebuild A: a plan point's distance along its corridor's axis from the hall's centre (east or west)."""
    return abs(x - S.HALL_C[0]) * S.COR_DIR[0] + (y - S.HALL_C[1]) * S.COR_DIR[1]   # rebuild C: from the hall's centre


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
        hc = rooms["hall"]["centre"]   # rebuild C: the generator works round the hall's centre
        self.assertEqual(S.TIP_C, (rooms["tip_e"]["centre"][0] - hc[0], rooms["tip_e"]["centre"][1] - hc[1]))
        self.assertAlmostEqual(S.TIP_X, math.dist(rooms["tip_e"]["centre"], hc), places=9)
        self.assertEqual(S.H_COR, rooms["corridor_e"]["clear_h"])
        # rebuild A: the corridor's axis runs from the hall's centre through the tip room's
        (ax, ay), (bx, by) = rooms["corridor_e"]["axis"]
        self.assertEqual((ax, ay), tuple(hc))
        self.assertAlmostEqual(S.COR_ANG, math.degrees(math.atan2(by - ay, bx - ax)), places=9)
        self.assertAlmostEqual(math.degrees(math.atan2(*reversed(S.TIP_C))), S.COR_ANG, places=9)
        self.assertEqual(max(u for u, _ in S.PROF), rooms["corridor_e"]["width"] / 2)

    def test_the_openings_take_the_corridor(self) -> None:
        self.assertGreater(S.HCH, S.COR_HALF)              # the hall's chords
        self.assertGreater(S.TIP_CHORD_H, S.COR_HALF)      # the tip rooms' chords
        self.assertAlmostEqual(S.COR_X0, 3.918, places=2)  # the corridor modules run portal to portal (v2)
        self.assertAlmostEqual(S.COR_X1, 8.024, places=2)  # rebuild A: along the diagonal (v2 7.111)
        self.assertEqual(S.N_MOD, 4)
        self.assertAlmostEqual(S.MOD_L, 1.026, places=3)
        self.assertEqual(S.OPENINGS["corridor_w"], 180.0 - S.OPENINGS["corridor_e"])

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

    def test_the_mouth_opens_wide_and_the_tip_rooms_have_no_window(self) -> None:
        self.assertEqual(S.THROAT_PROF[1][1], S.PROF[1][1])   # rebuild C: the throat bends where the corridors do
        # rebuild A (the engineer, 2026-10-22): no tip windows; the window's segments are wall facets
        ids = {p["id"] for p in INTERIOR["pieces"]}
        self.assertFalse({i for i in ids if any(w in i for w in ("window", "shutter", "well", "sill", "glass"))})
        self.assertEqual(INTERIOR.get("shutter_closed", []), [])
        for sx in (1, -1):
            c = (sx * S.TIP_C[0] + S.HALL_C[0], S.TIP_C[1] + S.HALL_C[1])
            panels = [1 for pid, (x, y, _), _ in INTERIOR["place"] if pid.startswith("tip_panel")
                      and math.hypot(x - c[0], y - c[1]) < S.R_TIP]
            self.assertEqual(len(panels), S.TIP_N)

    def test_the_hall_openings_face_the_diagonal_corridors(self) -> None:
        """rebuild A: each corridor's opening and portal centred on its axis, the openings two facets' chord wide."""
        segs = S.hall_segments()
        self.assertAlmostEqual(sum(a1 - a0 for a0, a1, _ in segs), 360.0, places=6)
        for (a0, a1, _), (b0, _b1, _) in zip(segs, segs[1:] + segs[:1]):
            self.assertAlmostEqual(a1 % 360.0, b0 % 360.0, places=6)
        for a0, a1, k in segs:
            if k == "opening":
                self.assertAlmostEqual(a1 - a0, 45.0, places=6)
        portals = [math.degrees(math.atan2(y - S.HALL_C[1], x - S.HALL_C[0])) for pid, (x, y, _), _ in INTERIOR["place"]
                   if pid == "hall_portal"]
        self.assertEqual(sorted(round(a, 3) for a in portals),
                         sorted(round(S.OPENINGS[k], 3) for k in ("corridor_e", "corridor_w")))

    def test_arches_and_details_keep_off_the_station_spots(self) -> None:
        spots = SHIP["stations"]["spot"]
        r = SHIP["stations"]["radius_m"]
        for pid, (x, y, _), _yaw in INTERIOR["place"]:
            for s in spots:
                d = math.hypot(x - s["at"][0], y - s["at"][1])
                if pid == "cor_arch" and s.get("normal") and s["room"].startswith("corridor") and x * s["at"][0] > 0:
                    self.assertGreater(abs(along(x, y) - along(*s["at"])), SHIP["stations"]["plain_width_m"] / 2 + 0.15,
                                       (pid, x, s["id"]))
                if pid.startswith(("cup", "spill", "cable_coil", "floor_patch")):  # the small details
                    self.assertGreater(d, r + 0.4, (pid, x, y, s["id"]))

    def test_every_wall_facet_or_chord_has_a_floor_plate(self) -> None:
        """inside-fix (code review major 1): no dark gap at the wall where a player stands. rebuild A: every hall
        segment (facet, flat chord, opening) has exactly one plate centred on it, of its kind; every tip-room edge
        its rim plate (the door's three)."""
        kinds = {"facet": "hall_floor_rim", "flat": "hall_flat_floor", "flat_lo": "hall_flat_floor",
                 "opening": "hall_threshold"}
        plates = [(pid, math.degrees(math.atan2(y - S.HALL_C[1], x - S.HALL_C[0]))) for pid, (x, y, _), _yaw
                  in INTERIOR["place"] if pid.startswith(("hall_floor_rim", "hall_flat_floor", "hall_threshold"))
                  and pid != "hall_floor_rim_throat"]
        segs = [s for s in S.hall_segments() if s[2] != "throat"]   # rebuild C: the throat's sub-facets' own rims
        self.assertEqual(len(plates), len(segs))
        self.assertEqual(sum(1 for p in INTERIOR["place"] if p[0] == "hall_floor_rim_throat"), 2 * S.TH_SUBS // 2)
        for a0, a1, k in segs:
            mid = (a0 + a1) / 2
            hits = [pid for pid, a in plates if abs(((a - mid + 180) % 360) - 180) < 1e-3]
            self.assertEqual(len(hits), 1, (a0, a1, k, hits))
            self.assertTrue(hits[0].startswith(kinds[k]), (a0, a1, k, hits))
        self.assertEqual(len(S.tip_rim_polys()), len(S.tip_edges()) + 2)
        self.assertEqual(len(S.tip_edges()), S.TIP_N + 1)

    def test_the_tip_floor_plates_are_simple_polygons(self) -> None:
        """inside-fix: the door plate crossed itself (the black shard by the tip room's door)."""
        def cross(p, q, r):
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        signs = set()
        for poly in S.tip_rim_polys():
            n = len(poly)
            area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) / 2
            self.assertGreater(abs(area), 1e-3, poly)
            signs.add(area > 0)
            for i in range(n):
                for j in range(i + 2, n):
                    if (j + 1) % n == i:
                        continue
                    a, b, c, d = poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]
                    self.assertFalse(cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0,
                                     (i, j, poly))
        self.assertEqual(len(signs), 1)   # one winding: no plate faces down

    def test_corridor_cables_on_both_walls_off_the_breaker_board(self) -> None:
        """inside-fix: both corridor walls carry a cable bay, the front wall's beside the board's plain wall; the
        ceiling ribs only on the ceiling; no hall trunk at a station chord's end."""
        place = INTERIOR["place"]
        lo, hi = SP.BOARD_X
        for sgn in (1, -1):
            bays = [(pid, x, y) for pid, (x, y, _), _ in place if pid in ("cor_bay_in", "cor_bay_out")
                    and x * sgn > 0]
            self.assertEqual(len(bays), 2)
            back = [p for p, (x, y, _), yaw in place if p == "cor_channel" and x * sgn > 0]
            self.assertEqual(len(back), S.N_MOD)   # the back wall's bays, one per module
            ribs = [x for p, (x, y, _), _ in place if p == "cor_ceil_rib" and x * sgn > 0]
            self.assertEqual(len(ribs), len(SP.COR_RIBS))
        foot = SP.FOOT
        for pid, (x, y, _), _yaw in place:
            if pid.startswith("cor_bay"):
                x0, x1 = along(x, y) + foot[pid][0], along(x, y) + foot[pid][1]
                self.assertTrue(x1 <= lo + 1e-3 or x0 >= hi - 1e-3, (pid, x))
        ends = [a for a0, a1, k in S.hall_segments() if k == "flat" for a in (a0, a1)]
        trunks = [math.degrees(math.atan2(y, x)) for pid, (x, y, _), _yaw in place if pid == "hall_trunk"]
        self.assertEqual([round(a, 3) for a in trunks], [90.0])   # the back's one trunk, as v2
        for a in trunks:
            for f in ends:
                self.assertGreater(abs(((a - f + 180) % 360) - 180), 1.0, (a, f))


if __name__ == "__main__":
    unittest.main()
