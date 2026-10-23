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
            mod = next(m for m in [S, *S.MODULES] if hasattr(m, piece["builder"]))   # as the harness looks it up
            parts = getattr(mod, piece["builder"])(piece.get("args", {}), SHIP)
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
        self.assertAlmostEqual(S.COR_X1, 9.107, places=2)  # lens step 1: to the lens's portal (rebuild A 8.024)
        self.assertEqual(S.N_MOD, 5)
        self.assertAlmostEqual(S.MOD_L, 1.038, places=3)
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

    def test_the_mouth_opens_wide_and_the_lens_window_band(self) -> None:
        """lens step 1: the window band's five facets (window, glass, sill strip) on the outer side, biased forward
        (+ aft round the outward axis, the west room mirrored), mullions between them, pilasters at its ends; the
        other seven facets plain panels; no shutters or wells."""
        self.assertEqual(S.THROAT_PROF[1][1], S.PROF[1][1])   # rebuild C: the throat bends where the corridors do
        ids = {p["id"] for p in INTERIOR["pieces"]}
        self.assertFalse({i for i in ids if any(w in i for w in ("shutter", "well"))})
        self.assertEqual(INTERIOR.get("shutter_closed", []), [])
        tv = S.tip_vertices()
        self.assertAlmostEqual(tv[3], -65.86, places=2)
        self.assertAlmostEqual(tv[8], 43.91, places=2)
        for sx in (1, -1):
            cx, cy = sx * S.TIP_C[0] + S.HALL_C[0], S.TIP_C[1] + S.HALL_C[1]
            near = [(pid, math.degrees(math.atan2(y - cy, sx * (x - cx))) - S.COR_ANG) for pid, (x, y, _), _ in
                    INTERIOR["place"] if math.hypot(x - cx, y - cy) < S.R_TIP + 0.01 and math.hypot(x - cx, y - cy) > 1.5]
            wins = sorted(round(a, 2) for pid, a in near if pid.startswith("tip_window"))
            self.assertEqual(len(wins), 5)
            self.assertEqual(len([1 for pid, _ in near if pid.startswith("tip_panel")]), S.TIP_N - 5)
            self.assertEqual(len([1 for pid, _ in near if pid == "tip_glass"]), 5)
            self.assertEqual(len([1 for pid, _ in near if pid == "tip_mullion"]), 4)
            self.assertGreater(min(wins), S.BAND["from_deg"] - 1.5)
            self.assertLess(max(wins), S.BAND["to_deg"] + 1.5)

    def test_the_lens_ceiling_slants_round_its_oculus(self) -> None:
        """lens step 1: the ceiling from 2.4455 at the corridor's side to 2.3545 at the outer wall (P's), the walls
        H_TIP high under it; details 1: the slab round the oculus (none over its clear disc, every room point outside
        the light ring under exactly one cell), the six lamps on the light ring, the ribs clear of it."""
        self.assertAlmostEqual(S.tip_clear(-S.RW_TIP + 0.2), 2.4455, places=3)
        self.assertAlmostEqual(S.tip_clear(S.RW_TIP - 0.2), 2.3545, places=3)
        self.assertLessEqual(S.H_TIP, min(S.tip_clear(t) for t in (-2.2, 0.0, 2.2)))
        cells = S.tip_ceiling_cells()

        def inside(p, poly):
            return all((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9
                       for a, b in zip(poly, poly[1:] + poly[:1]))
        self.assertEqual(S.OC_R, 0.7)
        inner = min(math.hypot(x, y) * math.cos(math.atan2(y, x) - S.oc_angle(k)) for k, c in enumerate(cells)
                    for x, y in c)
        self.assertGreater(inner, S.OC_WELL[0] + 1e-3)   # the slab starts outside the clear disc,
        self.assertLess(inner, S.OC_WELL[1] - 1e-3)      # and overlaps the well's lining (no gap round the oculus)
        for r in (0.0, 0.3, S.OC_R - 0.01):
            self.assertFalse(any(inside((r, 0.0), c) for c in cells))
        for p in ((-1.0, 1.0), (1.9, 0.0), (0.0, 1.2), (-1.3, -0.4), (1.05, 0.3), (0.85, 0.0), (0.0, -0.85)):
            self.assertEqual(sum(1 for c in cells if inside(p, c)), 1, p)
        # details 2: the light ring's warm strip is slim (7 cm) inside the dark channel, under the beam; no lamps
        parts = {q["name"]: q for q in S.tip_ceiling({}, None)}
        rs = [math.hypot(x, y) for x, y, _h in parts["band"]["verts"]]
        self.assertTrue(0.06 <= max(rs) - min(rs) <= 0.08, max(rs) - min(rs))
        cr = [math.hypot(x, y) for x, y, _h in parts["channel"]["verts"]]
        self.assertTrue(min(cr) < min(rs) and max(rs) < max(cr) < S.OC_BEAM[1] and min(cr) > S.OC_R + 0.03)
        self.assertFalse([1 for pid, *_r in INTERIOR["place"] if pid == "tip_lamp"])
        # D1 review: the fascia's foot OC_FASCIA (10 cm) under the walls' top everywhere round the slant
        rim = S.FLOOR + S.H_TIP
        self.assertAlmostEqual(min(h for _x, _y, h in parts["fascia"]["verts"]), rim - S.OC_FASCIA, places=6)
        self.assertAlmostEqual(max(h for _x, _y, h in parts["fascia"]["verts"] if h < rim - 0.05), rim - S.OC_FASCIA,
                               places=6)
        self.assertGreater(min(abs(x) - w for x, w in S.TIP_RIBS), S.OC_BEAM[1] + 0.05)
        parts = S.tip_ceiling({}, None)
        hs = [h for q in parts if q["name"] == "slab" for x, y, h in q["verts"] if abs(h - S.FLOOR - S.tip_clear(x)) < 1e-6]
        self.assertTrue(hs)

    def test_the_vault_door_and_shell(self) -> None:
        """lens step 1: the hall's back is the vault's door (one shut door piece on a flat chord over the two back
        facets, centred at 90 deg), the shell placed behind it; the vault's ceiling 2.3 m at the door, 1.6 at the
        back."""
        doors = [(x, y) for pid, (x, y, _), _ in INTERIOR["place"] if pid == "hall_door"]
        self.assertEqual(len(doors), 1)
        self.assertAlmostEqual(doors[0][0], 0.0, places=4)
        self.assertAlmostEqual(doors[0][1], 3.6, delta=0.03)
        self.assertEqual([k for *_a, k in S.hall_segments()].count("door"), 1)
        shells = [(x, y) for pid, (x, y, _), _ in INTERIOR["place"] if pid == "vault_shell"]
        self.assertEqual(shells, [(0.0, 3.85)])
        self.assertAlmostEqual(S.vault_top(0.0), 2.3)
        self.assertAlmostEqual(S.vault_top(S.VAULT_L), 1.6)

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
                 "opening": "hall_threshold", "door": "hall_floor_rim_back"}
        plates = [(pid, math.degrees(math.atan2(y - S.HALL_C[1], x - S.HALL_C[0]))) for pid, (x, y, _), _yaw
                  in INTERIOR["place"] if pid.startswith(("hall_floor_rim", "hall_flat_floor", "hall_threshold"))
                  and pid != "hall_floor_rim_throat"]
        segs = [s for s in S.hall_segments() if s[2] != "throat"]   # rebuild C: the throat's sub-facets' own rims
        self.assertEqual(len(plates), len(segs) + 1)   # lens step 1: the door's two back rim plates
        door = next(s for s in segs if s[2] == "door")
        segs = [s for s in segs if s[2] != "door"] + [(door[0], 90.0, "door"), (90.0, door[1], "door")]
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
        trunks = [pid for pid, *_ in place if pid == "hall_trunk"]
        self.assertEqual(trunks, [])   # lens step 1: the back's one trunk (90 deg) is the vault's door


if __name__ == "__main__":
    unittest.main()
