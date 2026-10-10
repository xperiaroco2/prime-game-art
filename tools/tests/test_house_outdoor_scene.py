"""The Godot proof's request of the House map's plot (tools/runner/house_outdoor_scene.py, godot/outdoor/proof.gd,
docs/house-outdoor.md "The proof"): every placed piece is a kit v2 piece, the stand-ins stay off the walks, the walks
cross the openings and end at the passage pad, the controls cross the fence away from the openings. Pure Python."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runner import house_outdoor as ho
from runner import house_outdoor_scene as hs
from runner.common import ROOT

DATA = ho.load()
SPEC = {p["id"] for p in json.loads((ROOT / "kits" / "house.json").read_text(encoding="utf-8"))["pieces"]}


def _doc() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        ho.write(DATA, Path(tmp))
        return json.loads((Path(tmp) / "outdoor.json").read_text(encoding="utf-8"))


DOC = _doc()
REQ = hs.request(DATA, DOC, Path("D:/build"), {"textures": "t", "roughness": [1, 1, 1], "normal_strength": [1, 1, 1]})


def _in_box(b: dict, p: list[float], margin: float) -> bool:
    return all(abs(p[i] - b["at"][i]) <= b["size"][i] / 2 + margin for i in (0, 2)) and \
        b["at"][1] - b["size"][1] / 2 < p[1] + 1.8 and p[1] < b["at"][1] + b["size"][1] / 2 - 0.05


class SceneRequestTest(unittest.TestCase):
    def test_every_placed_piece_is_a_kit_piece(self) -> None:
        self.assertTrue(set(REQ["pieces"]) <= SPEC, set(REQ["pieces"]) - SPEC)
        self.assertEqual({p[0] for p in REQ["placed"]}, set(REQ["pieces"]))
        self.assertEqual(len(REQ["placed"]), len(DOC["fence"]) + len(DOC["stairs"]["pieces"]) + len(DOC["stairs"]["rails"]))

    def test_the_request_is_json(self) -> None:
        self.assertEqual(json.loads(json.dumps(REQ))["fog"][0], DATA["sky_cfg"]["backdrop"]["fog_start_m"])

    def test_walks_that_must_arrive_touch_no_block(self) -> None:
        for name, w in REQ["walks"].items():
            if not w["must_pass"]:
                continue
            for p in w["points"]:
                hit = [b["id"] for b in REQ["blocks"] if _in_box(b, p, w["r"])]
                self.assertEqual(hit, [], f"{name} at {p}")

    def test_the_openings_and_the_stairs_are_walked(self) -> None:
        self.assertTrue({"perimeter", "wicket", "gates", "stairs"} <= set(REQ["walks"]))
        drop = DATA["stairs"]["drop"]
        end = REQ["walks"]["stairs"]["points"][-1]
        self.assertAlmostEqual(end[1], -drop)
        pad = next(b for b in REQ["blocks"] if b["id"] == "passage_pad")
        self.assertAlmostEqual(pad["at"][1] + pad["size"][1] / 2, -drop)
        self.assertTrue(abs(end[0] - pad["at"][0]) < pad["size"][0] / 2 and abs(end[2] - pad["at"][2]) < pad["size"][2] / 2)
        fy = max(p[1] for p in DATA["plot"])
        for kind in ("wicket", "gates"):
            pts = REQ["walks"][kind]["points"]
            self.assertLess(pts[0][2], fy)
            self.assertGreater(pts[-1][2], fy)
            self.assertLess(pts[-1][2], DATA["kerb"]["y"])  # on the pavement, short of the kerb

    def test_controls_cross_the_fence_away_from_the_openings(self) -> None:
        controls = {k: w for k, w in REQ["walks"].items() if not w["must_pass"]}
        self.assertEqual(REQ["walks"]["wicket_closed"]["leaves"], "closed")
        self.assertEqual(REQ["walks"]["gates"]["leaves"], "open")
        controls = {k: w for k, w in controls.items() if k.startswith("out_")}
        self.assertEqual(len(controls), 4)
        xs = [p[0] for p in DATA["plot"]]
        ys = [p[1] for p in DATA["plot"]]
        for name, w in controls.items():
            (ax, _, ay), (bx, _, by) = w["points"]
            inside = min(xs) < ax < max(xs) and min(ys) < ay < max(ys)
            outside = not (min(xs) < bx < max(xs) and min(ys) < by < max(ys))
            self.assertTrue(inside and outside, name)
            for o in DOC["openings"]:
                self.assertFalse(min(o["from"][0], o["to"][0]) - 1 < bx < max(o["from"][0], o["to"][0]) + 1
                                 and by > max(ys), name)

    def test_shots_have_a_view_of_each_proof_subject(self) -> None:
        names = {v[0] for v in REQ["views"]}
        self.assertTrue({"street", "wicket", "gates", "stairs_top", "stairs_bottom"} <= names)
        self.assertEqual([s[0] for s in REQ["strips"]], ["strip_yard", "strip_street"])


if __name__ == "__main__":
    unittest.main()
