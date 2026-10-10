"""The House's clutter layer (art #104, tools/runner/house_clutter.py): seeded, current in the dressing files,
non-solid, on hosts, walls and floors where the rules put it, and the rooms' checks still hold."""
from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import house_clutter as hc  # noqa: E402
from runner import house_dressing as hd  # noqa: E402
from runner import house_layout as hl  # noqa: E402

DATA = hl.load()
CAT = hd.catalogue(hd.spec_paths(DATA["settings"]))
FOLDER = hl.LAYOUT_DIR / DATA["settings"]["dressing_dir"]
GEN = hc.generate(DATA, FOLDER, CAT)
ROOMS = {r["id"]: (lv, r) for lv in DATA["levels"] for r in lv["rooms"]}


class Clutter(unittest.TestCase):
    def test_every_rule_room_is_generated(self) -> None:
        self.assertEqual(set(GEN), set(hc.RULES))
        self.assertGreaterEqual(sum(len(v[2]) for v in GEN.values()), 150)

    def test_the_blocks_are_current_and_seeded(self) -> None:
        again = hc.generate(DATA, FOLDER, CAT)
        for rid, (path, text, _) in GEN.items():
            self.assertEqual(text, again[rid][1], rid)
            self.assertEqual(path.read_text(encoding="utf-8"), text, f"{rid}: run `house --clutter`")
            self.assertEqual(hc.strip(text).count(hc.MARK), 0)

    def test_clutter_is_known_and_never_solid(self) -> None:
        for rid, (_, _, items) in GEN.items():
            for it in items:
                self.assertIn(it["id"], CAT, rid)
                self.assertFalse(hd.solid(hd.resolve(it, CAT)), f"{rid}: {it}")

    def test_items_rest_on_a_host_a_wall_or_the_floor(self) -> None:
        for rid, (_, text, items) in GEN.items():
            base = tomllib.loads(hc.strip(text))
            hosts = []
            for it in base.get("props", []):
                if it["id"] in hc.HOSTS and not it.get("station"):
                    r = hd.resolve(it, CAT)
                    hosts.append((hd.footprint(r), hd.span(r)[1]))
            for it in items:
                r = hd.resolve(it, CAT)
                fp, h = hd.footprint(r), it["at"][1]
                if r["pivot"] == "wall":
                    self.assertEqual(h, hc.WALL_H[it["id"]], f"{rid}: {it}")
                elif h > 0:
                    self.assertTrue(any(abs(top - h) < 1e-3 and hb[0] <= fp[0] and hb[1] <= fp[1] and fp[2] <= hb[2]
                                        and fp[3] <= hb[3] for hb, top in hosts), f"{rid}: {it} floats")

    def test_wall_items_keep_off_windows_and_doors(self) -> None:
        for rid, (_, _, items) in GEN.items():
            lv, room = ROOMS[rid]
            sh = hd.shell(lv, room, DATA["levels"])
            wins = hc._windows(lv, room)
            for it in items:
                r = hd.resolve(it, CAT)
                if r["pivot"] != "wall":
                    continue
                fp = hd.footprint(r)
                for wx, wz in wins:
                    self.assertGreaterEqual(hd.box_dist(fp, wx, wz), hc.WINDOW_HALF - 0.5 - 1e-6, f"{rid}: {it}")
                for dr in sh["doors"]:
                    self.assertGreaterEqual(hd.box_dist(fp, *dr["at"]), dr["clear"] / 2, f"{rid}: {it}")

    def test_strip_and_block_round_trip(self) -> None:
        items = [{"id": "cup_set", "at": [1.0, 0.9, 2.5], "face": "N"}]
        text = 'room = "x"\n' + "\n" + hc.block(items)
        self.assertEqual(hc.strip(text), 'room = "x"\n')
        self.assertEqual(tomllib.loads(text)["props"], items)

    def test_the_dressed_rooms_still_hold(self) -> None:
        dressings = hd.load(FOLDER)
        rep = hd.check(DATA, {rid: dressings[rid] for rid in GEN}, CAT)
        self.assertEqual(rep["problems"], [])


if __name__ == "__main__":
    unittest.main()
