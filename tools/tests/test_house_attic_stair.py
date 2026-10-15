"""The walkable attic stair under the long hatch (#183, the engineer's option B of prime-game PR #1043): the kit's
stair_attic, floor_boards_4x2_hatch and hatch_guard_attic, their place in layouts/house/attic.toml, and a sweep of the
game's standing capsule (1.8 m, radius 0.4: base_mode.tres) from the landing up into the attic: the steps under the
game's step height, the pitch under the 45 deg floor limit, and the capsule clear of the hatch's edges, the attic
floor above, the guard and the stair's own balustrades. Pure Python (the kit's geometry is built without Blender)."""
from __future__ import annotations

import math
import unittest

from runner import house_attic as A
from runner import house_layout as H
from runner.commands import _kit

G = _kit.geom()
SPEC = G.load_spec(_kit.SPEC)
PIECES = {p["id"]: p for p in SPEC["pieces"]}
DATA = H.load()
PLAN = H.plan(DATA)

CAPSULE_H = 1.8  # base_mode.tres capsule_height_m
CAPSULE_R = A.PLAYER_R  # 0.4, base_mode.tres capsule_radius_m
FLOOR_MAX_DEG = 45.0  # the controller's floor_max_angle (Godot's default)
MARGIN = 0.05  # the clearance the sweep asks for over touching


def level(name: str) -> dict:
    return next(lv for lv in DATA["levels"] if lv["level"] == name)


def stair() -> dict:
    return next(s for s in level("attic")["stairs"] if s["id"] == "attic_stair")


def hatch() -> list[float]:
    return H.hatch_hole(next(h for h in level("attic")["holes"] if h["id"] == "hatch"), DATA)


def surface(p: dict, u: float) -> float:
    """The walked collision's height at u metres along the run from the foot (the floor, the nosing ramp, the top)."""
    run, rise = float(p["run"]), float(p["rise"])
    if u < 0:
        return 0.0
    if u > run:
        return rise
    (_, _), (_, _), (_, _), (_, h0) = G.nosing_ramp(p)
    return h0 + u * (rise - h0) / run


def sphere_centre(p: dict, u: float, r: float) -> float:
    """The lowest height of the capsule's bottom sphere centre over the profile at u (resting on it, exact for a
    piecewise-linear profile sampled finely, the riser's top corner included)."""
    best = -1e9
    n = 80
    for i in range(n + 1):
        v = u - r + 2 * r * i / n
        best = max(best, surface(p, v) + math.sqrt(max(0.0, r * r - (v - u) ** 2)))
    if abs(u) <= r:  # the riser's top corner
        best = max(best, surface(p, 0.0) + math.sqrt(r * r - u * u))
    return best


def seg_rect_distance(ax: float, a0: float, a1: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """The distance from the vertical segment x = ax, y in [a0, a1] to the rectangle [x0, x1] x [y0, y1]."""
    dx = max(x0 - ax, 0.0, ax - x1)
    dy = max(y0 - a1, 0.0, a0 - y1)
    return math.hypot(dx, dy)


class AtticStairTest(unittest.TestCase):
    def test_the_steps_and_the_pitch_are_walkable(self) -> None:
        p = PIECES["stair_attic"]
        h, going, n = G.stair_numbers(p)
        self.assertAlmostEqual(h * n, float(p["rise"]))
        self.assertAlmostEqual(float(p["rise"]), SPEC["grid"]["floor_to_floor_m"])
        self.assertLessEqual(h, A.STEP_H - 0.05, "each riser under the game's step height")
        pitch = math.degrees(math.atan2(h, going))
        self.assertLessEqual(pitch, FLOOR_MAX_DEG - 3.0)
        ramp = G.nosing_ramp(p)
        self.assertLessEqual(ramp[3][1], A.STEP_H, "the ramp's first step")
        slope = math.degrees(math.atan2(ramp[2][1] - ramp[3][1], ramp[2][0] - ramp[3][0]))
        self.assertAlmostEqual(slope, pitch, places=6)
        self.assertGreaterEqual(float(p["width"]) - 2 * 0.06, 2 * CAPSULE_R + 0.15, "the clear width between the balustrades")

    def test_the_built_pieces_pass_the_kit_checks(self) -> None:
        for pid in ("stair_attic", "floor_boards_4x2_hatch", "hatch_guard_attic"):
            d = G.describe(G.build_piece(PIECES[pid], SPEC), SPEC)
            self.assertEqual(G.check_piece(d, PIECES[pid], SPEC), [], pid)
        d = G.describe(G.build_piece(PIECES["stair_attic"], SPEC), SPEC)
        ramps = [c for c in d["colliders"] if max(pt[1] for pt in c["points"]) < float(PIECES["stair_attic"]["rise"]) + 0.01]
        self.assertEqual(len(ramps), 1, "one walked ramp under the balustrades' walls")

    def test_the_stair_climbs_from_the_landing_to_the_hatch(self) -> None:
        st, (hx, hy, hw, hd) = stair(), hatch()
        x, y, w, d = st["rect"]
        self.assertEqual(st["climb"], "W")
        self.assertAlmostEqual(w, float(PIECES["stair_attic"]["run"]))
        self.assertAlmostEqual(d, float(PIECES["stair_attic"]["width"]))
        self.assertAlmostEqual(hx, x, msg="the top edge is the hatch's west edge")
        self.assertLess(hy, y)
        self.assertGreater(hy + hd, y + d)
        landing = next(r for r in level("upper")["rooms"] if r["id"] == "landing")["rect"]
        self.assertTrue(H.inside(landing, x, y) and H.inside(landing, x + w + 1.0, y + d))  # the foot and its approach
        well = next(h for h in level("upper")["holes"] if h["id"] == "main_stairs")["rect"]
        self.assertFalse(H.overlap(st["rect"], well), "the stair over the stairwell")
        half = SPEC["grid"]["door_w_m"] / 2
        for door in level("upper")["doors"]:  # the doors' openings (1.4 m) and 0.9 m before them stay clear
            dx, dy = door["at"]
            on_x_wall = abs(dx - landing[0]) < 1e-6 or abs(dx - landing[0] - landing[2]) < 1e-6
            box = [dx - 0.9, dy - half, 1.8, 2 * half] if on_x_wall else [dx - half, dy - 0.9, 2 * half, 1.8]
            self.assertFalse(H.overlap(st["rect"], box), door["names"])
        self.assertEqual([p for p in H.validate(DATA) if "attic_stair" in p or "hatch" in p], [])

    def test_the_capsule_climbs_standing_clear_of_the_hatch(self) -> None:
        """The section along the stair's axis: the capsule from 1 m before the foot to 1 m past the top, its bottom
        sphere resting on the walked profile; the attic slab over the foot (east of the hole) must stay MARGIN clear
        of it, and across the width the hole's edges, the guard and the balustrades too."""
        p, st, (hx, hy, hw, hd) = PIECES["stair_attic"], stair(), hatch()
        run, rise = float(p["run"]), float(p["rise"])
        slab = SPEC["grid"]["slab_m"]
        x, y, w, d = st["rect"]
        foot = x + w  # climbing west: u = foot - world x
        u_hole_end = foot - (hx + hw)  # the hole runs from u = u_hole_end to the top
        worst = 1e9
        u = -1.0
        while u <= run + 1.0 + 1e-9:
            c = sphere_centre(p, u, CAPSULE_R)
            top_c = c + CAPSULE_H - 2 * CAPSULE_R
            gap = seg_rect_distance(u, c, top_c, -10.0, u_hole_end, rise - slab, rise) - CAPSULE_R
            worst = min(worst, gap)
            u += 0.01
        self.assertGreaterEqual(worst, MARGIN, f"the capsule comes within {worst:.3f} m of the slab over the foot")
        cy = y + d / 2
        side = min(cy - CAPSULE_R - hy, hy + hd - (cy + CAPSULE_R))
        self.assertGreaterEqual(side, 0.1, "across the hole")
        inner = (d - 2 * 0.06) / 2 - CAPSULE_R  # the stair's balustrade walls over the stringers
        self.assertGreaterEqual(inner, 0.08)
        # the roof over the stair's top: the capsule's head under the roof's underside where it steps off
        pp = H.kit_geom().pitch(DATA["spec"])
        under = A.roof_top(DATA, cy) - pp["tv"] - 0.05
        self.assertGreater(under, CAPSULE_H + 0.5)

    def test_the_attic_side(self) -> None:
        z = A.load("attic")
        ax, ay = z["arrive"]
        hx, hy, hw, hd = hatch()
        self.assertLess(ax, hx - CAPSULE_R, "arrive is past the stair's top, on the attic floor")
        self.assertTrue(hy < ay < hy + hd)
        blocked = A.blocked_rects(z, DATA)
        self.assertEqual(len(blocked), 1)

    def test_the_hatch_pieces_are_merged(self) -> None:
        keep = DATA["settings"]["merge"]["keep"]
        for pid in ("stair_attic", "floor_boards_4x2_hatch", "hatch_guard_attic", "ladder_attic"):
            self.assertNotIn(pid, keep)
        names = [e.get("name") for e in next(lv for lv in PLAN["levels"] if lv["level"] == "attic")["extra"]]
        self.assertIn("attic_stair", names)
        self.assertNotIn("hatch_ladder", names)


if __name__ == "__main__":
    unittest.main()
