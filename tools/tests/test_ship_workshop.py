"""The west lens room's workshop, step 1 (art #263, docs/ship.md "The west lens room's workshop"): its pieces against
the design's cm drawing, inside tip_w, the floor lights uncovered, the path from the door to the charger clear, clear
of the charger's alcove, the colliders. Plain Python (the builders' parts, no Blender)."""

from __future__ import annotations

import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "blender"))
sys.path.insert(0, str(ROOT / "tools"))
import ship_interior as S  # noqa: E402
import ship_interior_workshop as WS  # noqa: E402
from runner import ship_layout  # noqa: E402

with (ROOT / "layouts" / "ship" / "interior.toml").open("rb") as _f:
    INTERIOR = tomllib.load(_f)
LAYOUT = ship_layout.load()
PIECES = {p["id"]: p for p in INTERIOR["pieces"]}
SPOTS = {s["id"]: s for s in LAYOUT["stations"]["spot"]}
TIP_W = next(r for r in LAYOUT["rooms"] if r["id"] == "tip_w")
C = TIP_W["centre"]
ROOM = 180.0 + S.COR_ANG
SHOP = sorted(p for p in PIECES if p.startswith("ws_"))
FLOOR_ITEMS = ("ws_bench_open_top", "ws_bench_open_low", "ws_cabinet", "ws_rug")
_CACHE: dict = {}


def parts(pid: str) -> dict:
    if pid not in _CACHE:
        piece = PIECES[pid]
        mod = next(m for m in [S, *S.MODULES] if hasattr(m, piece["builder"]))
        _CACHE[pid] = {p["name"]: p for p in getattr(mod, piece["builder"])(piece.get("args", {}), LAYOUT)}
    return _CACHE[pid]


def verts(pid: str, names=None) -> list:
    return [v for n, p in parts(pid).items() if names is None or n in names for v in p["verts"]]


def world(at, yaw, x, y) -> tuple[float, float]:
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return at[0] + c * x + s * y, at[1] - s * x + c * y


def footprint(pid: str, step: int = 1):
    vs = verts(pid)[::step]
    return [[world(at, yaw, v[0], v[1]) for v in vs] for name, at, yaw in INTERIOR["place"] if name == pid]


def a_w(x, y) -> float:
    """A world point's angle in the west room's frame (deg, -180..180)."""
    return (math.degrees(math.atan2(y - C[1], x - C[0])) + ROOM + 180.0) % 360.0 - 180.0


def seg_dist(p, a, b) -> float:
    ax, ay, bx, by = *a, *b
    t = max(0.0, min(1.0, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    return math.hypot(p[0] - ax - t * (bx - ax), p[1] - ay - t * (by - ay))


def light_bars():
    """The west room's floor lights as (centre, unit along, half length, half width) (floor_light: 0.72 x 0.14)."""
    out = []
    for pid, at, yaw in INTERIOR["place"]:
        if pid == "tip_light" and at[0] < 0:
            ux, uy = world((0.0, 0.0), yaw, 1.0, 0.0)
            out.append((at, (ux, uy), 0.36, 0.07))
    return out


def bar_gap(p, bar) -> float:
    """A point's distance outside a light bar's rectangle (negative inside)."""
    (cx, cy, _), (ux, uy), hl, hw = bar
    dx, dy = p[0] - cx, p[1] - cy
    u, v = abs(dx * ux + dy * uy) - hl, abs(-dx * uy + dy * ux) - hw
    return math.hypot(max(u, 0.0), max(v, 0.0)) if max(u, v) > 0 else max(u, v)


class WorkshopDrawingTest(unittest.TestCase):
    def test_the_items_stand_where_the_drawing_puts_them(self) -> None:
        want = {"ws_robot": (-11.043, 0.302, 31.2), "ws_lamp": (-10.458, -0.612, -0.1)}
        for pid, (x, y, rot) in want.items():
            (q,) = [q for q in INTERIOR["place"] if q[0] == pid]
            self.assertAlmostEqual(q[1][0], x, delta=0.0011, msg=pid)
            self.assertAlmostEqual(q[1][1], y, delta=0.0011, msg=pid)
            self.assertAlmostEqual((q[2] - 90.0 + 180.0) % 360.0 - 180.0, rot, delta=0.1, msg=pid)   # its +90 frame
        cradles = sorted((q[1][0], q[1][1], (q[2] - 90.0) % 360.0) for q in INTERIOR["place"] if q[0] == "ws_cradle")
        for got, want_c in zip(cradles, sorted([(-12.211, 1.131, 87.7), (-12.113, 1.776, 109.6)])):
            for g, w in zip(got, want_c):
                self.assertAlmostEqual(g, w, delta=0.1)
            self.assertAlmostEqual(got[0], want_c[0], delta=0.0011)
            self.assertAlmostEqual(got[1], want_c[1], delta=0.0011)

    def test_the_bench_and_the_cabinet_run_over_their_facets(self) -> None:
        bench = sorted(round(a_w(*at[:2]), 2) for pid, at, _ in INTERIOR["place"] if pid.startswith("ws_bench"))
        cab = sorted(round(a_w(*at[:2]), 2) for pid, at, _ in INTERIOR["place"] if pid == "ws_cabinet")
        self.assertEqual(len(bench), 4)
        self.assertEqual(len(cab), 2)
        for got, k in zip(bench, range(4)):
            self.assertAlmostEqual(got, 21.95 + S.TIP_STEP * (k + 0.5), delta=0.02)
        for got, k in zip(cab, range(2)):
            self.assertAlmostEqual(got, -21.95 + S.TIP_STEP * (k + 0.5), delta=0.02)
        top = max(v[2] for v in verts("ws_bench_open_top", {"top"})) - S.FLOOR
        self.assertAlmostEqual(top, 0.90)
        self.assertAlmostEqual(-min(v[0] for v in verts("ws_bench_open_top", {"top", "nosing"})), 0.55)
        self.assertAlmostEqual(max(v[2] for v in verts("ws_cabinet", {"top"})) - S.FLOOR, 0.55)
        self.assertAlmostEqual(-min(v[0] for v in verts("ws_cabinet", {"top", "nosing"})), 0.59)   # the drawing: 60
        # the open drawers, one per bench module, 25 cm out: spare eyes (top, a_w 32.9), parts (low 54.9, top 76.8),
        # spare arms (low 98.8)
        opened = {pid: round(a_w(*at[:2]), 1) for pid, at, _ in INTERIOR["place"] if pid.startswith("ws_drawer")}
        self.assertEqual(opened, {"ws_drawer_eyes": 32.9, "ws_drawer_parts_a": 54.9, "ws_drawer_parts_b": 76.8,
                                  "ws_drawer_limbs": 98.8})
        self.assertAlmostEqual(-min(v[0] for v in verts("ws_drawer_eyes", {"front"})), 0.775)

    def test_the_robot_and_its_hoist(self) -> None:
        body = verts("ws_robot_body")
        c = WS.RC
        self.assertAlmostEqual(c[2] - S.FLOOR, 1.45)
        self.assertAlmostEqual(max(math.dist(v, c) for v in body), 0.30, places=4)          # the sphere Ø 60
        eye = verts("ws_robot", {"eye_ring"})
        self.assertAlmostEqual(max(math.hypot(v[1], v[2] - c[2]) for v in eye), 0.095, places=4)   # D16 + its bezel
        self.assertLess(max(v[0] for v in eye), -0.25)                                       # toward the room (-x)
        low = min(v[2] for v in verts("ws_robot", {"claws"})) - S.FLOOR
        self.assertAlmostEqual(low, 0.95, delta=0.01)                                        # the hands hang to 95
        clamp = verts("ws_hoist", {"clamp", "jaws"})
        self.assertAlmostEqual(min(v[2] for v in clamp) - S.FLOOR, 1.77, delta=0.005)
        self.assertAlmostEqual(max(v[2] for v in verts("ws_hoist", {"clamp"})) - S.FLOOR, 1.88, places=4)   # step 2: the claw's hub 183..188
        knob = verts("ws_robot", {"knob"})
        self.assertGreater(max(v[2] for v in knob), min(v[2] for v in clamp))                # the jaws hold the knob

    def test_the_robot_reads_as_the_concept(self) -> None:
        """Step 2: thin side shells opened 30..40 deg, every part of the bays' mechanism inside the shells' sphere, the
        arms below the body, the cables hanging out of the bays."""
        self.assertTrue(30.0 <= WS.ROBOT["open"] <= 40.0)
        self.assertLessEqual(WS.ROBOT["panel"], 32.0)                         # step 3: 0.8 of step 2's 40 or less
        self.assertGreater(WS.ROBOT["lift"], 0.0)                             # on hinge arms, off the body
        c = WS.RC
        mech = verts("ws_robot", {"gears", "hubs", "motors", "rods", "mounts", "chips", "core_light"})
        self.assertLess(max(math.dist(v, c) for v in mech), WS.MECH_R)
        arms = verts("ws_robot", {"arms", "claws"})
        self.assertLess(min(v[2] for v in arms), c[2] - WS.RR - 0.15)          # 15 cm and more below the body
        hang = verts("ws_robot", {"cables_b", "cables_c", "cables_d"})
        self.assertLess(min(v[2] for v in hang), c[2] - WS.RR - 0.05)          # the loose cables under it
        names = {p for p in parts("ws_robot")}
        self.assertTrue({"panels", "panel_liners", "hinge_arms", "eye_trim", "eye_iris_mid", "eye_glint", "core_light"} <= names)

    def test_step4_polish(self) -> None:
        """Step 4: the shells closer to the body, the iris's five bands on one level (no steps), olive front panels, the
        parts trays on a lighter foam with their own small lights."""
        self.assertLessEqual(WS.ROBOT["lift"], 0.03)                          # 5 cm read as headphones from the front
        bands = ("eye_iris", "eye_iris_out", "eye_iris_mid", "eye_iris_in", "eye_inner")
        p = parts("ws_robot")
        mats = [p[n]["mat"] for n in bands]
        self.assertEqual(len(set(mats)), 5)
        for m in mats:
            self.assertIn(m, LAYOUT["light"]["mats"])
        es = [LAYOUT["light"]["mats"][m]["e"] for m in mats]
        self.assertEqual(es, sorted(es))                                       # brighter inward
        # the bands' tops on one level: neighbours' shared edges meet (the eye looks along -x)
        for a, b in zip(bands, bands[1:]):
            r0 = min(math.hypot(v[1], v[2] - WS.RC[2]) for v in p[a]["verts"] if v[0] < -0.2)
            near = [-v[0] for v in p[a]["verts"] if abs(math.hypot(v[1], v[2] - WS.RC[2]) - r0) < 1e-4]
            far = [-v[0] for v in p[b]["verts"] if abs(math.hypot(v[1], v[2] - WS.RC[2]) - r0) < 1e-4]
            self.assertAlmostEqual(max(near), max(far), places=5)
        for pid in ("ws_bench_open_top", "ws_cabinet"):
            self.assertEqual(parts(pid)["panels"]["mat"], "ws_olive")
        self.assertEqual(parts("ws_drawer_parts_a")["insert"]["mat"], "ws_foam2")
        self.assertEqual(parts("ws_drawer_eyes")["insert"]["mat"], "ws_foam")
        shop = [l for l in LAYOUT["light"]["lamps"] if len(l) > 8 and l[8] == "shop" and len(l) < 11]
        for pid in ("ws_drawer_parts_a", "ws_drawer_parts_b"):
            at = next(at for q, at, _ in INTERIOR["place"] if q == pid)
            self.assertTrue(any(abs(math.dist(l[:2], at[:2]) - 0.5125) < 0.01 for l in shop), pid)


    def test_the_rail_hangs_under_the_ceiling(self) -> None:
        rail = verts("ws_rail", {"rail"})
        self.assertAlmostEqual(min(v[2] for v in rail) - S.FLOOR, 2.14)   # step 2: 14 cm under the drawing's 228
        rs = [math.hypot(v[0], v[1]) for v in rail]
        self.assertAlmostEqual((min(rs) + max(rs)) / 2, 1.05, places=3)
        for v in rail:
            self.assertLess(v[2], S.FLOOR + S.tip_clear(v[0]) - 0.15)   # 15.7..17.5 cm under it: the hangers show
        need = LAYOUT["player"]["capsule_height_m"]
        self.assertGreater(min(v[2] for v in verts("ws_hoist")) - S.FLOOR, need - 0.05)   # the claw: over the robot
        self.assertGreater(min(v[2] for v in rail) - S.FLOOR, need + 0.3)                # a 1.8 m capsule passes
        self.assertGreaterEqual(min(rs), S.OC_BEAM[1] + 0.02)   # clear of the oculus's light ring
        tops = max(v[2] - (S.FLOOR + S.tip_clear(v[0])) for v in verts("ws_rail", {"hangers"}))
        self.assertGreater(tops, 0.0)                               # the hangers reach into the ceiling


class WorkshopRoomTest(unittest.TestCase):
    def test_everything_stays_inside_tip_w(self) -> None:
        for pid in SHOP:
            for pts in footprint(pid, 3):
                worst = max(math.hypot(x - C[0], y - C[1]) for x, y in pts)
                self.assertLess(worst, S.R_TIP + 0.001, pid)
        self.assertFalse([q for q in INTERIOR["place"] if q[0].startswith("ws_") and q[1][0] > 0])

    def test_the_floor_lights_stay_uncovered(self) -> None:
        bars = light_bars()
        self.assertEqual(len(bars), 8)
        for pid in FLOOR_ITEMS:
            for pts in footprint(pid):
                for bar in bars:
                    self.assertGreater(min(bar_gap(p, bar) for p in pts), 0.008, pid)
        # the open drawers float over the bars' outer ends (h 10+), never over their middles at r 1.08
        for pid in ("ws_drawer_eyes", "ws_drawer_limbs", "ws_drawer_parts_a", "ws_drawer_parts_b"):
            for pts in footprint(pid, 5):
                for (cx, cy, _), _, _, _ in bars:
                    self.assertGreater(min(math.hypot(x - cx, y - cy) for x, y in pts), 0.1, pid)

    def test_the_path_to_the_charger_is_clear(self) -> None:
        rad = LAYOUT["player"]["capsule_radius_m"]
        a = math.radians(-S.COR_ANG)
        door = (C[0] + 1.3 * math.cos(a), C[1] + 1.3 * math.sin(a))
        stand = ship_layout.spot_stand(LAYOUT, SPOTS["renewer_w"])
        for pid in FLOOR_ITEMS + ("ws_drawer_eyes", "ws_drawer_limbs", "ws_drawer_parts_a", "ws_drawer_parts_b", "ws_cradle",
                    "ws_robot_body", "ws_robot"):
            for pts in footprint(pid, 3):
                self.assertGreater(min(seg_dist(q, door, stand) for q in pts), rad, pid)

    def test_clear_of_the_charger_alcove(self) -> None:
        ren = a_w(*SPOTS["renewer_w"]["at"])
        self.assertAlmostEqual(ren, -87.82, delta=0.05)
        for pid in SHOP:
            for pts in footprint(pid, 3):
                self.assertGreater(min(a_w(x, y) for x, y in pts), -24.0, pid)   # the alcove spans -105..-70

    def test_no_trunk_and_the_wall_pieces(self) -> None:
        self.assertFalse([q for q in INTERIOR["place"] if q[0].startswith("tip_trunk")])
        walls = {round(a_w(*at[:2]), 1): pid for pid, at, _ in INTERIOR["place"]
                 if at[0] < 0 and pid.startswith(("tip_window", "tip_panel"))}
        self.assertEqual({walls[a] for a in (76.8, 98.8)}, {"tip_panel_low_a", "tip_panel_low_b"})
        self.assertEqual({walls[a] for a in (32.9, 54.9)}, {"tip_window_lounge_a", "tip_window_lounge_b"})
        self.assertEqual({walls[a] for a in (-11.0, 11.0)}, {"tip_window_a", "tip_window_b"})

    def test_colliders(self) -> None:
        self.assertEqual({p for p in SHOP if PIECES[p]["collide"]},
                         {"ws_bench_open_top", "ws_bench_open_low", "ws_cabinet", "ws_robot_body"})

    def test_the_room_reads_green(self) -> None:
        shop = [l for l in LAYOUT["light"]["lamps"] if len(l) > 8 and l[8] == "shop"]
        self.assertGreaterEqual(len(shop), 3)
        for l in shop:
            self.assertLess(math.hypot(l[0] - C[0], l[1] - C[1]), S.R_TIP)
            self.assertGreater(l[6], l[5] * (1.2 if len(l) > 11 else 1.5))   # green over red (the lamp's: a pale work light)
            # step 2: green pools, no washes: above the deck, short ranges (only the bench lamp's aimed spot reaches the
            # robot), the bench lamp's aim at the robot's bays
            h = l[2] - S.FLOOR - LAYOUT["deck"]["lift_m"]
            self.assertTrue(0.3 < h < 1.9, l)
            self.assertLessEqual(l[4], 1.6 if len(l) > 11 else 1.0, l)
        aimed = [l for l in shop if len(l) > 11]
        self.assertEqual(len(aimed), 1)
        at = next(at for pid, at, _ in INTERIOR["place"] if pid == "ws_robot")
        self.assertLess(math.dist(aimed[0][11][:2], at[:2]), 0.05)
        self.assertAlmostEqual(aimed[0][11][2] - S.FLOOR - LAYOUT["deck"]["lift_m"], WS.ROBOT["h"] * 0.01 - 0.07, delta=0.05)
        # the room's own fill stays a neutral cool grey (step 1's mint flooded the walls green)
        fill = next(l for l in LAYOUT["light"]["lamps"] if len(l) > 8 and l[8] == "tip" and l[0] < -11.5)
        self.assertLess(fill[6], fill[7])
        mats = LAYOUT["light"]["mats"]
        for name in ("ws_green__strip", "ws_green__handle", "ws_green__rim", "ws_green__lamp", "ws_green__sleep",
                     "ws_green__liner", "ws_cyan__eye", "ws_cyan__pupil", "ws_cyan__core", "ws_glint", "ws_cyan__iris"):
            self.assertEqual(mats[name]["l"], 0.0, name)


if __name__ == "__main__":
    unittest.main()
