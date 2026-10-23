"""The hull's details on the hull J (art #263 rebuild B; docs/ship.md "The hull's details"): the canopies sit on the
hull with a low collar, the nozzle pods stay out of the hall and end where J's do, and no blade, stripe, tip window,
pod housing, hatch, seam line or scratch is left. Plain Python, no Blender."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

from runner import ship_layout as sl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender"))
import ship_hull  # noqa: E402,F401  (imports the skin and the details in their order)
import ship_hull_detail as D  # noqa: E402
import ship_hull_j as J  # noqa: E402
import ship_hull_shape as S  # noqa: E402

LAYOUT = sl.load()
HALL = next(r for r in LAYOUT["rooms"] if r["id"] == "hall")


def verts(parts):
    return [v for p in parts for v in p["verts"]]


class ShipHullDetailTest(unittest.TestCase):
    def test_the_cockpits_fit_under_their_glass(self) -> None:
        """details 1: each canopy holds a seat (pan, back, headrest, armrests), a console with three screens, all
        under the glass (2 cm clear), the screens glowing cyan, the glass the lighter canopy glass."""
        for side in (-1.0, 1.0):
            parts = {p["name"]: p for p in D.cockpit(side)}
            self.assertEqual(set(parts), {"canopy_floor", "canopy_glow", "canopy_seat", "canopy_pads", "canopy_screen"})
            for name, p in parts.items():
                for x, y, h in p["verts"]:
                    self.assertLess(h, D.glass_h(side, x, y) - 0.02, f"{name} through the glass at ({x:.2f}, {y:.2f})")
            self.assertEqual(len(parts["canopy_screen"]["verts"]), 3 * 8)
            self.assertEqual(parts["canopy_screen"]["mat"], "ext_screen")
            self.assertEqual(parts["canopy_seat"]["mat"], "ext_seat")
            seat = [y for _x, y, _h in parts["canopy_seat"]["verts"]]
            self.assertLess(min(seat), D.CANOPY["y"] - 0.4, "no console ahead of the seat (-y)")
            # the canopy fix: the seat low (its pan 0.22 over the floor, was 0.30) and near upright, so it reads as a seat from the ground; a pilot's head
            # (the headrest's top) still under the glass
            self.assertLessEqual(D.SEAT["recline"], 25.0)
            _t, _r, _g, deck, _o = D._canopy_frame(side)
            cx, cy = side * D.CANOPY["x"], D.CANOPY["y"]
            pan = [h - deck(x, y) for x, y, h in parts["canopy_seat"]["verts"] if abs(y - cy) < 0.2 and abs(x - cx) < 0.2]
            self.assertLess(max(pan), 0.23, "the seat's pan stands too high over the floor")
            head = max(parts["canopy_pads"]["verts"], key=lambda v: v[2])
            self.assertGreater(head[2] - deck(head[0], head[1]), 0.7, "the headrest too low for a seated pilot")
            glass = D.canopy({"side": side, "part": "glass"}, LAYOUT)
            self.assertEqual(glass[0]["mat"], "glass_canopy")

    def test_the_oculus_frame_rings_the_cut(self) -> None:
        """details 1: the oculus's ring frame on each lens, round its centre, over the cut's edge and out onto the
        plates, on the hull's top."""
        frame = next(p for p in D.lens_frames({}, LAYOUT) if p["name"] == "oculus_frame")
        for sx in (1, -1):
            cx, cy = sx * S.P_TIP[0], S.P_TIP[1]
            rs = [math.hypot(x - cx, y - cy) for x, y, _h in frame["verts"] if x * sx > 0]
            self.assertLess(min(rs), S.P_OCULUS_R)
            self.assertGreater(max(rs), S.P_OCULUS_R + 0.12)
            self.assertLess(max(rs), S.P_OCULUS_R + 0.25)
    def test_the_canopies_sit_on_the_hull(self) -> None:
        for side in (-1.0, 1.0):
            for part in ("glass", "fairing", "glow"):
                for x, y, h in verts(D.canopy({"side": side, "part": part}, LAYOUT)):
                    top = D.skin_h(x, y)
                    if top is not None:
                        self.assertGreater(h, top - 0.1, f"canopy {part} under the hull at ({x:.2f}, {y:.2f})")
            glass = verts(D.canopy({"side": side, "part": "glass"}, LAYOUT))
            # details 1: 0.85 high (was 0.75 under a 0.95 cap), room over the pilot's seat
            self.assertLess(max(h for _x, _y, h in glass) - D.skin_h(side * D.CANOPY["x"], D.CANOPY["y"]), 1.05)

    def test_the_pods_stay_out_of_the_hall_and_end_as_ps(self) -> None:
        pods = {p["id"]: p for p in LAYOUT["pieces"] if p["builder"] in ("nozzle_pod", "pod_ring")}
        build = {"nozzle_pod": D.nozzle_pod, "pod_ring": D.pod_ring}
        hx, hy = HALL["centre"]
        ends = []
        for pid, at, yaw in LAYOUT["place"]:
            if pid in pods:
                c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
                for x, y, _h in verts(build[pods[pid]["builder"]](pods[pid]["args"], LAYOUT)):
                    px, py = at[0] + c * x - s * y, at[1] + s * x + c * y   # every vertex where it is placed
                    self.assertGreater(math.hypot(px - hx, py - hy), HALL["radius"] + 0.2, f"{pid} in the hall")
            if pid in pods and pods[pid]["builder"] == "nozzle_pod":
                ends.append(at[1] + float(pods[pid]["args"]["length"]) + LAYOUT["hull"]["pod_tail_m"])
        self.assertEqual(len(ends), 3)
        self.assertAlmostEqual(max(ends), max(S.pod_ends()), delta=0.01)
        self.assertAlmostEqual(min(ends), min(S.pod_ends()), delta=0.01)

    def test_the_pod_tail_is_the_builders(self) -> None:
        ring = verts(D.pod_ring({"r": 1.05, "length": 3.25}, LAYOUT))
        self.assertAlmostEqual(max(y for _x, y, _h in ring) - 3.25, LAYOUT["hull"]["pod_tail_m"], delta=0.01)

    def test_no_strips_windows_hatches_seams_or_scratches(self) -> None:
        builders = {p["builder"] for p in LAYOUT["pieces"]}
        for gone in ("lead_blade", "smooth_stripes", "smooth_window", "window_frame", "pod_housing", "hatches",
                     "seam_lines", "hull_skin", "smooth_skin"):
            self.assertNotIn(gone, builders)
            self.assertFalse(hasattr(D, gone), gone)


    def test_the_throats_covered_part_cuts_only_the_belly(self) -> None:
        # rebuild F: the room cut takes J's belly out of the throat's covered part (between the walls' outer faces,
        # roof line to the hall's corners) and leaves every top facet whole (a sliver of it once went: a hole)
        cut = S.cutters()
        sides, ky = cut["notch"][:2], S.TH_PTS[2][1]
        surf = S.surface()
        for poly, _n, kind in surf:
            if kind != "belly":
                continue
            c = [sum(p[i] for p in poly) / len(poly) for i in range(3)]
            inside = all(S._dot(n, c) <= d for n, d in sides) and S.TH_ROOF_Y <= c[1] <= ky and c[2] > S.SLAB
            self.assertFalse(inside, f"a belly facet in the throat at ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")
        # lens step 2 (P, a union of parts): no hole in the top over the throat's covered part: every plan point
        # there lies under a top face
        tops = [poly for poly, n, kind in surf if kind == "top" and n[2] > 0.05]
        (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
        for i in range(1, 10):
            y = S.TH_ROOF_Y + (ky - S.TH_ROOF_Y) * i / 10
            xw = mx + (kx - mx) * (y - my) / (ky - my) + S.WALL
            for j in range(-4, 5):
                x = xw * j / 5
                self.assertTrue(any(sl.inside([(q[0], q[1]) for q in poly], (x, y)) for poly in tops),
                                f"no top face over ({x:.2f}, {y:.2f})")

    def test_the_outside_is_all_silver_and_every_strip_plated(self) -> None:
        # the engineer, 2026-10-22: the belly's leg_metal plates and the open slivers (the dark under-skin through
        # them) read as black patches and streaks; the top and the belly are in v1's silvers only, and every piece of
        # every facet is a plate (a sliver laid flush), so no outer facet shows the under-skin
        silvers = {"hull_silver", "ext_silver_b", "ext_silver_c"}
        for kind in ("top", "belly"):
            self.assertLessEqual(set(J.MATS[kind]), silvers, kind)
            mats = {p["mat"] for p in J.j_skin({"part": kind}, LAYOUT) if not p["name"].endswith("_seam")}
            self.assertLessEqual(mats, silvers, kind)
        slivers = 0
        for poly, n, kind in S.surface():
            if kind not in ("top", "belly"):
                continue
            qs = J.plates(poly, n)
            self.assertAlmostEqual(sum(S.area(q) for q in qs), S.area(poly), delta=1e-4 + 1e-3 * S.area(poly))
            for q in qs:
                if J.width(q) <= J.SLIVER:   # a sliver is laid flush: its face is its outline, no inset to flip
                    slivers += 1
                    self.assertEqual(J.lay(q)[0][:len(q)], [tuple(x) for x in q])
        self.assertGreater(slivers, 0)   # the cut makes slivers on J: they are laid, not left open

    def test_the_plates_run_in_rows_across_the_facets(self) -> None:
        # lens polish: every face is covered by its cells' pieces; a piece's edge is flush only on a facet edge whose
        # neighbour bends less than the zone's crease; the lens's rim has its three bands and seams every 36 deg; a lens
        # plate's pieces share one silver and the lens parts are shaded smooth
        # fix 2 step 3: a plate's pieces on coplanar faces are merged (skin_faces), so the area is checked per plane
        surf = S.surface()
        pieces = J.skin_pieces()
        faces = J.skin_faces()
        self.assertEqual(len(faces), len(pieces))

        def plane(i):
            u = S._unit3(surf[i][1])
            return tuple(round(t, 4) for t in u), round(S._dot(u, surf[i][0][0]), 3)
        area: dict = {}
        for (_k, _zone, _cell, i, q, flags), fs in zip(pieces, faces):
            self.assertEqual(i, fs[0])
            self.assertEqual({plane(f) for f in fs}, {plane(i)})
            area[plane(i)] = area.get(plane(i), 0.0) + S.area(q)
            self.assertEqual(len(flags), len(q))
        want: dict = {}
        for i, (poly, _n, _kind) in enumerate(surf):
            want[plane(i)] = want.get(plane(i), 0.0) + S.area(poly)
        for key, a in want.items():
            self.assertAlmostEqual(area.get(key, 0.0), a, delta=1e-4 + 1e-3 * a)
        edges = J.Edges(surf)
        for (_k, zone, _cell, i, q, flags), fs in list(zip(pieces, faces))[::7]:
            for (a, b), seam in zip(zip(q, q[1:] + q[:1]), flags):
                if not seam:
                    m = tuple(0.5 * (a[t] + b[t]) for t in range(3))
                    hits = [edges.bend(f, m) for f in fs if edges.bend(f, m)[0]]
                    self.assertTrue(hits)
                    self.assertLessEqual(max(bd for _o, bd in hits), J.CREASE[zone])
        rim = {c[3] for _k, z, c, *_ in pieces if z == "lens" and c[2] == "rim"}
        self.assertEqual(rim, {0, 1, 2})
        self.assertLessEqual(len({c[4] for _k, z, c, *_ in pieces if z == "lens" and c[2] == "rim"}), 10)
        self.assertLess(len({p[2] for p in pieces}), len(pieces) / 4)   # plates span facets: fewer cells than pieces
        parts = J.j_skin({"part": "top"}, LAYOUT)
        lens = [p for p in parts if p["name"].endswith("_lens")]
        self.assertTrue(lens)
        self.assertTrue(all(p["smooth_deg"] == J.CREASE["lens"] for p in lens))

    def test_the_seam_corners_end_on_their_fold_and_keep_the_groove(self) -> None:
        """details 3b/3c/3d (lay_seams, corner_slides): where a seam ends on a flush edge (a facet fold), the plate's
        corner lies on that flush edge (within 1e-6 m), so the pieces on both sides of the fold end on its line; every
        group of corners at one point sliding one way ends at one point within 0.1 mm, short edges included (3c's
        per-piece cap left 450 groups over 0.1 mm apart, up to 6.5 cm: black wedges); each corner's groove is its
        slide * sin, the slide at most SLIDE_MAX INSET and its own _slide_cap. The limits, counted: corners of 25 to
        155 deg between edges of 0.25 m and more keep a groove of 0.9 INSET but for at most 25 (3d: 23, in groups
        with a short member; 3b: 186), none under 0.25 INSET; near-straight or needle corners (sin under 1 /
        SLIDE_MAX) taper to SLIDE_MAX INSET * sin; corners stopped short by their group's cap are counted."""
        ends: dict = {}
        corners = wide = folds = capped = 0
        narrow = []
        for (_k, _zone, _cell, _i, q, flags), slides in zip(J.skin_pieces(), J.skin_slides()):
            if J.width(q) <= J.SLIVER:
                continue
            v, f = J.lay_seams(q, flags, slides)
            top = [v[x] for x in f[0]]
            self.assertEqual(len(top), len(q))
            for j in range(len(q)):
                a, b, c = q[j - 1], q[j], q[(j + 1) % len(q)]
                if flags[j - 1] == flags[j]:
                    continue
                corners += 1
                seam, flush = ((a, b), (b, c)) if flags[j - 1] else ((b, c), (a, b))
                self.assertLess(J._off_segment(top[j], *flush), 1e-6, (q[j], top[j]))
                way, want = J._corner(q, flags, j)
                key = (tuple(round(t, 4) for t in b), tuple(round(t, 2) for t in way))
                ends.setdefault(key, []).append(top[j])
                s = slides[j]
                self.assertLessEqual(s, min(J.SLIDE_MAX * J.INSET, J._slide_cap(q, flags, j)) + 1e-12)
                u, w = S._unit3(S._sub(a, b)), S._unit3(S._sub(c, b))
                deg = math.degrees(math.acos(max(-1.0, min(1.0, S._dot(u, w)))))
                sin = math.sin(math.radians(deg))
                groove = self._off_line(top[j], *seam)
                self.assertAlmostEqual(groove, s * sin, delta=1e-6)
                folds += sin < 1.0 / J.SLIDE_MAX
                capped += s < want - 1e-9
                if 25 <= deg <= 155 and min(math.dist(a, b), math.dist(b, c)) >= 0.25:
                    wide += 1
                    self.assertGreater(groove, 0.25 * J.INSET, (round(deg, 1), b))
                    if groove < 0.9 * J.INSET:
                        narrow.append((round(deg, 1), round(groove, 4), b))
        # fix 2 step 3: a plate's coplanar pieces merge (J.merge_coplanar), so the seam corners on the surface's
        # fragment edges are gone: 3138 corners (3d: over 5000), 1416 wide, 238 near-straight or needle, 419 capped
        # (3d: 747), 1 narrow (3d: 23), 1270 shared groups
        self.assertGreater(corners, 2500)
        self.assertGreater(wide, 1000)
        self.assertGreater(folds, 100)    # near-straight or needle corners, SLIDE_MAX INSET * sin
        self.assertLess(capped, 600)      # corners stopped short by their group's cap
        self.assertLessEqual(len(narrow), 5, f"{len(narrow)} seam corners taper the groove")
        shared = [g for g in ends.values() if len(g) > 1]
        self.assertGreater(len(shared), 1000)
        for g in shared:
            self.assertLess(max(math.dist(g[0], t) for t in g), 1e-4, g)   # 0.1 mm

    @staticmethod
    def _off_line(p, a, b) -> float:
        ab = S._sub(b, a)
        c = S._cross(ab, S._sub(p, a))
        return math.sqrt(S._dot(c, c) / S._dot(ab, ab))

    def test_the_jamb_caps(self) -> None:
        caps = J.jamb_caps()
        self.assertEqual(len(caps), 8)
        (mx, my), (kx, ky) = S.TH_PTS[1], S.TH_PTS[2]
        k = 1.0 / ((ky - my) / math.hypot(kx - mx, ky - my))
        y = S.TH_ROOF_Y + J.CAP_BACK
        xi = mx + (kx - mx) * (y - my) / (ky - my)
        xo = xi + S.WALL * k + 0.02
        x_ceil = xi - S.TH_CH[1] * k   # the upper cap's inner edge follows the chamfer in to the ceiling
        for side in (1, -1):
            mine = [(v, f) for v, f in caps if all(side * x > 0 for x, _y, _h in v)]
            self.assertEqual(len(mine), 4)
            normals = []
            for v, faces in mine:
                self.assertGreaterEqual(len(v), 3)
                lo = xi if len(v) == 4 else x_ceil   # the lower cap: walls' inner face to past the notch's side
                for x, _y, _h in v:
                    self.assertGreaterEqual(side * x, lo - 1e-9)
                    self.assertLessEqual(side * x, xo + 1e-9)
                normals.append(S._newell([v[i] for i in faces[0]])[1])
            self.assertEqual(sorted(n > 0 for n in normals), [False, False, True, True], "both windings per side")

    def test_the_jamb_caps_stay_under_the_roof(self) -> None:
        """fix 2 (item 6): past the notch's side the roof line falls under the cap's top; the cap's upper outer
        corner stood out of the roof's plates (the dark triangle by each canopy fairing). Every cap corner lies at
        least CAP_SKIN under each roof face over the cap's line."""
        caps = J.jamb_caps()
        y = S.TH_ROOF_Y + J.CAP_BACK
        roofs = J._roof_planes(y, 0.0, 3.0, steps=60)
        self.assertTrue(roofs)
        for v, _f in caps:
            for x, yy, h in v:
                for n, d in roofs:
                    self.assertLessEqual(S._dot(n, (abs(x), yy, h)), d - J.CAP_SKIN + 1e-6)
        upper = [v for v, _f in caps if len(v) > 4]
        self.assertEqual(len(upper), 4)
        self.assertTrue(all(max(h for _x, _y, h in v) > S.TH_TOP for v in upper), "still up under the lintel")

    def test_the_fairings_plates_follow_the_lens_sectors(self) -> None:
        """fix 2 (item 4): the fairings' plates are the lens rim's lowest band's sectors, one seam family for every
        facet (the per-facet plan family switched round the bend: seams stopped on a fold and restarted offset);
        each piece lies in its sector, mirrored on the west."""
        surf = S.surface()
        fair = [(c, i, q) for _k, _z, c, i, q, _f in J.skin_pieces() if c[0] == "fair"]
        self.assertTrue(fair)
        self.assertEqual({c[1] for c, _i, _q in fair}, {1, -1})
        for c, i, q in fair:
            self.assertTrue(S.p_fair_face(*surf[i][:2]))
            sx, k = c[1], c[2]
            g0 = S.p_axis_deg() + k * J.LENS_SECTOR
            for p in q:
                g = math.degrees(math.atan2(p[1] - S.P_TIP[1], sx * p[0] - S.P_TIP[0]))
                off = (g - g0) % 360.0
                self.assertTrue(off <= J.LENS_SECTOR + 1e-3 or off >= 360.0 - 1e-3, (c, p, off))

    def test_the_folds_sink_along_one_miter(self) -> None:
        """fix 2 (item 4, step 1): a point on a fold sinks along one line for every face there, by exactly 1 in each
        face's own plane (two faces) and by the cap at most."""
        a = S._unit3((0.0, 0.0, 1.0))
        b = S._unit3((0.0, math.sin(math.radians(40)), math.cos(math.radians(40))))
        for own in (a, b):
            m = J.miter([a, b], own)
            self.assertAlmostEqual(S._dot(m, a), 1.0, places=9)
            self.assertAlmostEqual(S._dot(m, b), 1.0, places=9)
        self.assertEqual(J.miter([a], a), a)
        sharp = S._unit3((0.0, math.sin(math.radians(170)), math.cos(math.radians(170))))
        self.assertLessEqual(math.sqrt(S._dot(*(J.miter([a, sharp], a),) * 2)), J.MITER_MAX + 1e-9)
        pieces, faces = J.skin_miters()
        self.assertEqual(len(pieces), len(J.skin_pieces()))
        self.assertEqual(len(faces), len(S.surface()))

    def test_the_nozzle_throats_are_smooth(self) -> None:
        """fix 2 (item 5): the throat (the dark dish) is shaded smooth across its radial facets, sharp at its crease."""
        for args in ({"r": 1.42, "length": 4.665}, {"r": 1.62, "length": 4.965}):
            throat = next(p for p in D.nozzle_pod(args, LAYOUT) if p["name"] == "pod_throat")
            self.assertEqual(throat["smooth_deg"], D.THROAT_SMOOTH_DEG)
            self.assertGreater(D.THROAT_SMOOTH_DEG, 360.0 / D.POD_SEGS)
            # no flat disc across the nozzle: the bell, the throat and the lights' rings have no end caps (an n-gon of
            # POD_SEGS corners); the bell's and the throat's caps z-fought in one plane over the whole nozzle
            parts = D.nozzle_pod(args, LAYOUT) + D.pod_ring(args, LAYOUT)
            for p in parts:
                if p["name"] in ("pod_bell", "pod_throat", "pod_band", "pod_inner_ring"):
                    self.assertFalse([f for f in p["faces"] if len(f) >= D.POD_SEGS], p["name"])

    def test_merged_plate_pieces_stay_convex(self) -> None:
        """fix 2 step 3 (item 4): merge_coplanar joins only what stays convex: two squares side by side become one
        rectangle, an L of three stays in convex pieces of the same total area."""
        n = (0.0, 0.0, 1.0)

        def sq(x: float, y: float) -> list:
            return [(x, y, 0.0), (x + 1.0, y, 0.0), (x + 1.0, y + 1.0, 0.0), (x, y + 1.0, 0.0)]

        def convex(q: list) -> bool:
            turns = [S._dot(S._cross(S._sub(q[i], q[i - 1]), S._sub(q[(i + 1) % len(q)], q[i])), n)
                     for i in range(len(q))]
            return all(t >= -1e-9 for t in turns) or all(t <= 1e-9 for t in turns)

        two = J.merge_coplanar([(0, sq(0, 0)), (1, sq(1, 0))], n)
        self.assertEqual(len(two), 1)
        self.assertAlmostEqual(S.area(two[0][1]), 2.0, places=6)
        ell = J.merge_coplanar([(0, sq(0, 0)), (1, sq(1, 0)), (2, sq(0, 1))], n)
        self.assertGreater(len(ell), 1)
        self.assertAlmostEqual(sum(S.area(q) for _f, q in ell), 3.0, places=6)
        for _faces, q in ell + two:
            self.assertTrue(convex(q), q)


if __name__ == "__main__":
    unittest.main()
