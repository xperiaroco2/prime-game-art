"""The jaw nose, b2 (art #263, docs/ship.md "The jaw nose"): the three poses, the open deck on the ground at the
ramp's slope (under 30 deg), the head room under the upper jaw, the check refusing a wrong pose, and the builders'
thin shells: closed, no line of sight from outside into the throat (rays from a ring of outside points); in every
pose of the swing no piece cuts through another; open, nothing stands in the walkway; the deck in its plane. Plain
Python, no Blender."""

from __future__ import annotations

import copy
import math
import collections
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl
from runner.commands import ship as ship_cmd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports every exterior module in its order)
import ship_hull_jaw as J  # noqa: E402

LAYOUT = sl.load()


class ShipJawPoseTest(unittest.TestCase):
    def test_three_poses_and_the_default(self) -> None:
        j = LAYOUT["jaw"]
        self.assertEqual(j["pose"], "open")            # the game and the walk get the open ramp
        self.assertEqual(sl.jaw_deg(LAYOUT, "closed"), {"jaw_lower": 0.0, "jaw_upper": 0.0})
        lo = {p: sl.jaw_deg(LAYOUT, p)["jaw_lower"] for p in sl.JAW_POSES}
        up = {p: sl.jaw_deg(LAYOUT, p)["jaw_upper"] for p in sl.JAW_POSES}
        self.assertTrue(lo["open"] < lo["half"] < lo["closed"] == 0.0)       # the lower jaw goes down
        self.assertTrue(0.0 == up["closed"] < up["half"] < up["open"] <= 5.0)  # the upper lifts a little
        self.assertEqual(sl.check_jaw(LAYOUT), [])

    def test_the_open_ramp(self) -> None:
        o = sl.jaw_numbers(LAYOUT, "open")
        ramp = LAYOUT["ramp"]
        run = ramp["hinge"][1] - ramp["foot"][1]
        self.assertAlmostEqual(o["length"], math.hypot(run, 1.2), delta=0.01)
        self.assertAlmostEqual(o["slope_deg"], math.degrees(math.atan2(1.2, run)), delta=0.05)
        self.assertLess(o["slope_deg"], 30.0)
        self.assertAlmostEqual(o["tip_h"], 0.0, delta=0.02)
        self.assertAlmostEqual(o["tip_y"], ramp["foot"][1], delta=0.05)
        c = sl.jaw_numbers(LAYOUT, "closed")
        self.assertAlmostEqual(c["tip_h"], LAYOUT["jaw"]["seam_h"], delta=1e-6)   # closed: the deck meets the seam

    def test_head_room_open(self) -> None:
        pl = LAYOUT["player"]
        self.assertGreaterEqual(sl.jaw_numbers(LAYOUT, "open")["head_room"],
                                pl["capsule_height_m"] + pl["head_margin_m"])

    def test_the_check_refuses(self) -> None:
        bad = copy.deepcopy(LAYOUT)
        bad["jaw"]["pose"] = "ajar"
        self.assertEqual(len(sl.check_jaw(bad)), 1)
        steep = copy.deepcopy(LAYOUT)
        steep["jaw"]["lower_deg"]["open"] = -50.0      # the deck through the ground, too steep
        self.assertTrue(any("ground" in p for p in sl.check_jaw(steep)))
        low = copy.deepcopy(LAYOUT)
        low["jaw"]["upper_deg"]["open"] = -6.0         # the roof down on the walkers' heads
        self.assertTrue(any("head room" in p or "over the deck" in p for p in sl.check_jaw(low)))

    def test_the_placements_carry_the_pose(self) -> None:
        rows = {r[0]: r for r in ship_cmd.places(LAYOUT)}
        self.assertEqual(rows["jaw_lower"][3], LAYOUT["jaw"]["lower_deg"]["open"])
        self.assertEqual(rows["jaw_upper"][3], LAYOUT["jaw"]["upper_deg"]["open"])
        self.assertEqual(len(rows["jaw_root"]), 3)
        self.assertEqual(rows["jaw_lower"][1], [0.0, 1.2, -8.1])      # Godot (x, h, y): at its hinge
        self.assertEqual(sorted(ship_cmd.jaw_request(LAYOUT)), sorted(sl.JAW_POSES))
        pieces = {p["id"]: p for p in LAYOUT["pieces"]}
        for pid in ("jaw_lower", "jaw_upper", "jaw_root"):
            self.assertTrue(pieces[pid]["collide"] and pieces[pid]["outside"] and pieces[pid]["grounded"], pid)
        for gone in ("ramp", "ramp_lights", "hazard_stripes", "mouth_tunnel"):
            self.assertNotIn(gone, pieces)


class ShipJawBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parts = {f.__name__: {p["name"]: p for p in f({}, LAYOUT)} for f in (J.jaw_upper, J.jaw_lower, J.jaw_root)}

    def test_the_parts_are_there(self) -> None:
        want = {"jaw_upper": {"upper_inner", "upper_rim", "upper_skirt_glow", "upper_ceiling", "upper_bulkhead",
                              "seam_glow", "ceiling_glow"},
                "jaw_lower": {"lower_inner", "lower_rail_glow", "lower_tip_glow", "lower_rim", "lower_deck", "lower_bulkhead",
                              "deck_ribs", "deck_edges"},
                "jaw_root": {"root_inner", "root_rim", "root_bulkhead", "root_lip", "root_hood", "root_lid"}}
        for pid, names in want.items():
            self.assertTrue(names <= set(self.parts[pid]), (pid, names - set(self.parts[pid])))
            self.assertTrue(any(n.endswith("_seam") for n in self.parts[pid]), pid)       # plated: the under-skin

    def test_closed_it_is_sealed(self) -> None:
        """No ray from a ring of outside points (and from under and over the nose) reaches the throat or the closed
        mouth: the shells, the tunnel's slab and the hull block every one."""
        leaks, n = seal_rays(LAYOUT)
        self.assertGreater(n, 900)
        self.assertEqual(leaks, [])

    def test_no_piece_cuts_another_in_the_swing(self) -> None:
        deg = sl.jaw_deg(LAYOUT, "open")
        lo, up = deg["jaw_lower"], deg["jaw_upper"]
        for k in range(6):
            got = clashes(LAYOUT, lo * k / 5, up * k / 5)
            self.assertEqual(collections.Counter((a, na, b, nb) for a, na, b, nb, _p in got), collections.Counter(),
                             f"step {k}/5: {got[:3]}")

    def test_open_the_walkway_is_clear(self) -> None:
        """Open, no vertex of any piece stands in the walkway over the deck (|x| 1.2, 2.25 m up) from the ramp's
        front to the throat."""
        j = J.jaw(LAYOUT)
        deg = sl.jaw_deg(LAYOUT, "open")
        hy, fh = j["lower_hinge"][1], j["floor_h"]
        fall = math.tan(math.radians(sl.jaw_numbers(LAYOUT, "open")["slope_deg"]))      # + falls forward
        for pid, ts in pieces(LAYOUT, deg["jaw_lower"], deg["jaw_upper"]).items():
            for t in ts:
                if t[3] in ("deck_ribs", "deck_edges", "tunnel_slab"):
                    continue
                for x, y, h in t[:3]:
                    if abs(x) < 1.2 and -11.5 < y < -7.0:
                        deck = fh if y >= hy else fh - (hy - y) * fall
                        self.assertFalse(deck + 0.03 < h < deck + 2.25, (pid, t[3], (x, y, h)))

    def test_open_the_tip_collides_only_from_above(self) -> None:
        """Open, every collider face of the ramp near its tip (where the capsule walks on, |x| 0.8, the front 0.5 m)
        looks up: b2's underside slivers and the tip's rim stopped the walk 12 cm short of the ramp (b3), and so did the
        deck plate's own underside and edges (b4: only its top face collides)."""
        j = J.jaw(LAYOUT)
        o = j["lower_hinge"]
        deg = sl.jaw_deg(LAYOUT, "open")["jaw_lower"]
        tip_y = J._pose((0.0, j["tip_y"], j["seam_h"]), o, deg)[1]
        for p in J.jaw_lower({}, LAYOUT):
            if p.get("nocol"):
                continue
            v = [J._pose((a[0] + o[0], a[1] + o[1], a[2] + o[2]), o, deg) for a in p["verts"]]
            for f in p["faces"]:
                q = [v[i] for i in f]
                if any(abs(x) < 0.8 and y < tip_y + 0.5 and h < 0.4 for x, y, h in q):
                    n = J.front_normal(q)
                    self.assertTrue(n[2] > 0.5, (p["name"], n))

    def test_the_open_deck_faces_up_in_godot(self) -> None:
        """Open, the deck's top (the only face of its collider) fronts up after make()'s mirror, and the belly's
        inner faces under it front up into the mouth: Godot's trimesh colliders are one-sided, and b3's inward shells
        let the capsule fall through the deck and stop at its tip (b4)."""
        j = J.jaw(LAYOUT)
        o = j["lower_hinge"]
        deg = sl.jaw_deg(LAYOUT, "open")["jaw_lower"]
        parts = {p["name"]: p for p in J.jaw_lower({}, LAYOUT)}
        for name in ("lower_deck", "lower_inner"):
            p = parts[name]
            self.assertFalse(p.get("nocol"), name)
            v = [J._pose((a[0] + o[0], a[1] + o[1], a[2] + o[2]), o, deg) for a in p["verts"]]
            ups = [J.front_normal([v[i] for i in f])[2] for f in p["faces"]]
            self.assertTrue(all(u > 0.3 for u in ups) if name == "lower_deck" else sum(ups) > 0, (name, min(ups)))
        self.assertTrue(parts["lower_deck_edge"].get("nocol"))

    def test_nothing_in_the_throat(self) -> None:
        """In every pose no face of a piece crosses into the throat room (inside its walls, floor to ceiling): the
        hulls' aft faces lie inside the hull, so they are left out."""
        import ship_hull_j as HJ
        deg = sl.jaw_deg(LAYOUT, "open")
        for k in (0, 5):
            for pid, ts in pieces(LAYOUT, deg["jaw_lower"] * k / 5, deg["jaw_upper"] * k / 5).items():
                for t in ts:
                    if t[3] == "tunnel_slab":
                        continue
                    for x, y, h in t[:3]:
                        if -7.1 < y < -3.3:
                            inside = HJ._tun_w(y)[0] - 0.02 - max(0.0, h - 2.65) * 0.65   # the chamfer over the bend
                            self.assertFalse(abs(x) < inside and 1.25 < h < 3.45, (pid, t[3], (x, y, h)))

    def test_the_deck_lies_in_its_plane(self) -> None:
        j = J.jaw(LAYOUT)
        o = j["lower_hinge"]
        deck = self.parts["jaw_lower"]["lower_deck"]
        pts = [(v[0] + o[0], v[1] + o[1], v[2] + o[2]) for v in deck["verts"]]
        on = [p for p in pts if abs(p[2] - (j["floor_h"] + j["deck_slope"] * (o[1] - p[1]))) < 1e-6]
        self.assertTrue(any(abs(p[1] - o[1]) < 1e-6 and abs(p[2] - j["floor_h"]) < 1e-6 for p in on))  # flush at the hinge
        self.assertLess(min(p[1] for p in on), j["tip_y"] + 0.06)                   # out to the tip (the walk starts there)
        self.assertLessEqual(max(p[2] for p in pts), j["seam_h"] + 1e-6)


# --- the seal and clash checks (flat skins: the plates sink inside the skin) ------------------------------------------
import ship_hull_shape as S  # noqa: E402

def tris(parts, o=(0, 0, 0), deg=0.0, piv=None):
    out = []
    for p in parts:
        v = [(a[0] + o[0], a[1] + o[1], a[2] + o[2]) for a in p["verts"]]
        if deg:
            v = [J._pose(a, piv, deg) for a in v]
        for f in p["faces"]:
            for i in range(1, len(f) - 1):
                out.append((v[f[0]], v[f[i]], v[f[i + 1]], p["name"]))
    return out

def hit(a, b, t, eps=1e-9):
    p0, p1, p2 = t[0], t[1], t[2]
    d = S._sub(b, a); e1 = S._sub(p1, p0); e2 = S._sub(p2, p0)
    h = S._cross(d, e2); det = S._dot(e1, h)
    if abs(det) < eps: return None
    f = 1 / det; s = S._sub(a, p0); u = f * S._dot(s, h)
    if u < 0 or u > 1: return None
    q = S._cross(s, e1); v = f * S._dot(d, q)
    if v < 0 or u + v > 1: return None
    tt = f * S._dot(e2, q)
    return (tt, u, v) if 0 < tt < 1 else None

def bbox(t):
    return [min(p[k] for p in t[:3]) for k in range(3)], [max(p[k] for p in t[:3]) for k in range(3)]

def pieces(layout, lower_deg=0.0, upper_deg=0.0):
    """Every piece's triangles in a pose, the skins flat (the tunnel's slab with the root's)."""
    j = J.jaw(layout)
    lo, up = j["lower_hinge"], j["upper_hinge"]
    old, J.PLATED = J.PLATED, False
    try:
        return {"lower": tris(J.jaw_lower({}, layout), lo, lower_deg, lo),
                "upper": tris(J.jaw_upper({}, layout), up, upper_deg, up),
                "root": tris(J.jaw_root({}, layout)) + SLAB}
    finally:
        J.PLATED = old


import ship_lib as _L  # noqa: E402
_bv, _bf = _L.box(-1.65, 1.65, -8.1, -7.1, 0.95, 1.188)
SLAB = tris([{"name": "tunnel_slab", "verts": _bv, "faces": _bf}])

def in_hull(p):
    return S.skin((p[0], p[1], p[2] - S.LIFT)) > 0.01

TARGETS = [(0, -7.6, 2.0), (0, -6.5, 2.2), (1.2, -7.8, 2.6), (-1.2, -7.0, 1.6), (0, -9.0, 2.0), (0.9, -10.5, 2.4)]

def seal_rays(layout):
    """Rays from a ring of outside points to points in the throat and the closed mouth: the unblocked ones."""
    tri = [t for ts in pieces(layout).values() for t in ts]
    boxes = [bbox(t) for t in tri]
    srcs = [(14 * math.cos(math.radians(a)), -8 + 14 * math.sin(math.radians(a)), h)
            for a in range(0, 360, 12) for h in (0.25, 1.0, 1.7, 3.2, 6.0)]
    srcs += [(x, y, 0.05) for x in (-1.5, 0, 1.5) for y in (-12, -10, -8.6, -7.9)]
    srcs += [(x, y, 9.0) for x in (-3, 0, 3) for y in (-11, -8, -6)]
    leaks = []
    for s in srcs:
        for t in TARGETS:
            lo = [min(s[k], t[k]) for k in range(3)]; hi = [max(s[k], t[k]) for k in range(3)]
            blocked = False
            for tr, (bl, bh) in zip(tri, boxes):
                if any(bh[k] < lo[k] or bl[k] > hi[k] for k in range(3)): continue
                if hit(s, t, tr): blocked = True; break
            if not blocked:
                n = int(math.dist(s, t) / 0.12)
                for i in range(1, n):
                    p = tuple(s[k] + (t[k] - s[k]) * i / n for k in range(3))
                    if p[1] > -7.3 and 0.6 < p[2] < 5.3 and in_hull(p): blocked = True; break
            if not blocked: leaks.append((s, t))
    return leaks, len(srcs) * len(TARGETS)

def clashes(layout, lower_deg, upper_deg, tol=0.003):
    """Edges of one piece crossing another's triangles (each strictly through, tol from the edges)."""
    pc = pieces(layout, lower_deg, upper_deg)
    out = []
    for a, b in (("lower", "root"), ("lower", "upper"), ("upper", "root"), ("root", "lower"), ("upper", "lower"), ("root", "upper")):
        tb = [(t, bbox(t)) for t in pc[b]]
        for t in pc[a]:
            ab_lo, ab_hi = bbox(t)
            cand = [x for x, (bl, bh) in tb if all(bh[k] >= ab_lo[k] - 1e-6 and bl[k] <= ab_hi[k] + 1e-6 for k in range(3))]
            if not cand: continue
            for i in range(3):
                p, q = t[i], t[(i + 1) % 3]
                L = math.dist(p, q)
                if L < 1e-6: continue
                for c in cand:
                    r = hit(p, q, c)
                    if not r: continue
                    tt, u, v = r
                    w = 1 - u - v
                    n = S._unit3(S._cross(S._sub(c[1], c[0]), S._sub(c[2], c[0])))
                    da, db = S._dot(S._sub(p, c[0]), n), S._dot(S._sub(q, c[0]), n)
                    if min(abs(da), abs(db)) < tol: continue
                    # distance of the hit from the triangle's edges, roughly
                    sz = max(math.dist(c[0], c[1]), math.dist(c[1], c[2]), math.dist(c[2], c[0]))
                    if min(u, v, w) * sz < tol: continue
                    out.append((a, t[3], b, c[3], tuple(round(p[k] + (q[k] - p[k]) * tt, 3) for k in range(3))))
    return out


if __name__ == "__main__":
    unittest.main()
