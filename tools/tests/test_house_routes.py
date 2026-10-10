"""The design doc's routes for the house walk (art #78): routes.toml against the layout, the dressing and the doc, and
the walks it becomes (tools/runner/house_routes.py)."""

from __future__ import annotations

import unittest

from runner import house_basement as B
from runner import house_dressing as hd
from runner import house_layout as H
from runner import house_routes as R

DATA = H.load()
SPEC = R.load(H.LAYOUT_DIR)
DRESSING = hd.load(H.LAYOUT_DIR / DATA["settings"].get("dressing_dir", "dressing"))
CAT = hd.catalogue(hd.spec_paths(DATA["settings"]))
BASEMENT = next(lv for lv in DATA["levels"] if lv["level"] == "basement")

# prime-game docs/design/house-map.md §7: route -> (length m, walking s); §6: the stations the routes start and end on
DOC = {"wine": (26, 5.9), "garage": (60, 13.4), "switches": (105, 23.4)}
SWITCHES = [(48.5, 19.5), (32, 44), (52, 48), (16, 32)]  # D, B, C, A


def plain(route: dict) -> list:
    return [p for p in route["points"] if p[0] != "stairs"]


class RoutesTest(unittest.TestCase):
    def test_the_doc_routes_with_their_figures(self):
        self.assertEqual(SPEC["speed"], 4.5)
        self.assertEqual({r["id"]: (r["doc_m"], r["doc_s"]) for r in SPEC["routes"]}, DOC)
        self.assertEqual(R.problems(DATA, SPEC), [])

    def test_ends_on_the_stations(self):
        by_id = {r["id"]: plain(r) for r in SPEC["routes"]}
        self.assertEqual(by_id["wine"][0][1:], [16, 26])
        self.assertEqual(by_id["garage"][0][0], "basement")
        sw = [tuple(p[1:]) for p in by_id["switches"]]
        self.assertEqual([sw[0], sw[-1]], [SWITCHES[0], SWITCHES[-1]])
        for s in SWITCHES[1:3]:
            self.assertIn(s, sw)

    def test_basement_legs_clear_the_props_and_pillars(self):
        blocks = [b for room in BASEMENT["rooms"] for b in B.blockers(DATA, DRESSING, CAT, room["id"], hd.BODY[0])]
        for r in SPEC["routes"]:
            pts = r["points"]
            for a, b in zip(pts, pts[1:]):
                if a[0] != "basement" or b[0] != "basement":
                    continue
                for name, box in blocks:
                    with self.subTest(route=r["id"], leg=(a[1:], b[1:]), prop=name):
                        self.assertGreaterEqual(B._seg_box(a[1:], b[1:], box), hd.RADIUS - 0.01)

    def test_walks_climb_the_real_flights(self):
        request = H.walk_request(DATA)
        walks = {w["name"]: w for w in R.walks(DATA, request, SPEC)}
        garage = walks["route:garage"]
        self.assertEqual(garage["speed"], 4.5)
        heights = [p[1] for p in garage["points"]]
        self.assertEqual((heights[0], heights[-1]), (-3.2, 0.0))
        self.assertIn(-1.6, heights)  # the outdoor stairs' landing
        self.assertGreater(garage["max_s"], 2 * 13.4)
        self.assertEqual({w["points"][0][1] for w in walks.values()}, {-3.2})
        # the plan's length is the doc's within the slack the time allows (1 s at 4.5 m/s), give or take the
        # climb the doc counts as 6 m: kept here as a measure, the walk judges the time
        for rid, (m, s) in DOC.items():
            self.assertLess(abs(R.plan_metres(walks[f"route:{rid}"]["points"]) - m), 10)

    def test_judge(self):
        w = {"doc_s": 10.0, "doc_m": 45.0, "points": [[0, 0, 0], [3, 0, 4]]}
        j = R.judge(w, {"seconds": 10.8, "arrived": True}, 1.0)
        self.assertEqual((j["pass"], j["time_ok"], j["delta_s"], j["plan_m"]), (True, True, 0.8, 5.0))
        j = R.judge(w, {"seconds": 11.5, "arrived": True}, 1.0)
        self.assertEqual((j["pass"], j["time_ok"]), (True, False))
        self.assertFalse(R.judge(w, {"seconds": 9.0, "arrived": False}, 1.0)["pass"])

    def test_problems_name_a_bad_point(self):
        bad = {"routes": [{"id": "x", "points": [["cellar", 1, 1], ["stairs", "nope", "up"]]}]}
        self.assertEqual(len(R.problems(DATA, bad)), 3)


if __name__ == "__main__":
    unittest.main()
