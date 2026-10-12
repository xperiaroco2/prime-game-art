"""The pinned game greybox (tools/tests/_house_greybox.py, tools/tests/fixtures/house_greybox.json; art #34): the
snapshot loads and holds what the House tests compare against, its drift rule allows additions and names removals
and moves, and against the live checkout D:/prime-game (skipped when missing) nothing pinned was removed or moved.
A new room, marker or design row in the game is not drift: the art takes it with the next refresh
(`$PYTHON_BIN tools/tests/_house_greybox.py`, docs/house.md "The game's greybox, pinned")."""

from __future__ import annotations

import copy
import json
import unittest

from . import _house_greybox as G


class PinnedGreybox(unittest.TestCase):
    def test_the_snapshot_holds_the_house(self):
        snap = G.load()
        self.assertEqual(len(snap["game_commit"]), 40)
        self.assertEqual(len(snap["rooms"]), 35)
        self.assertEqual(len(snap["design_rooms"]), 35)
        kitchen = snap["rooms"]["kitchen"]
        self.assertEqual(kitchen["root"], "Kitchen")
        self.assertIsInstance(kitchen["origin"], tuple)
        self.assertTrue(all(isinstance(v, tuple) and len(v) == 4 for v in kitchen["doors"].values()))
        self.assertEqual(sorted(kitchen["doors"]), kitchen["doors_marker3d"])

    def test_drift_allows_additions_and_names_removals_and_moves(self):
        pinned = json.loads(G.SNAPSHOT.read_text(encoding="utf-8"))
        live = copy.deepcopy(pinned)
        live["rooms"]["kitchen"]["markers"]["Zone99"] = [1.0, 0.0, 1.0, "\"spawn_zone\""]
        live["rooms"]["new_room"] = copy.deepcopy(live["rooms"]["kitchen"])
        live["design_rooms"]["New room"] = [0, 0, 2, 2]
        self.assertEqual(G.drift(G.load(), live), [])
        door = sorted(live["rooms"]["kitchen"]["doors"])[0]
        live["rooms"]["kitchen"]["doors"][door][0] += 1.0
        del live["rooms"]["garage"]
        live["design_rooms"].pop("Kitchen")
        found = G.drift(G.load(), live)
        self.assertEqual(len(found), 3, found)
        self.assertTrue(any(f.startswith(f"kitchen: doors/{door} ") for f in found), found)
        self.assertIn("garage: removed", found)
        self.assertTrue(any(f.startswith("design doc: Kitchen ") for f in found), found)

    @unittest.skipUnless((G.GAME / "levels" / "house" / "house.tscn").is_file(), "the game repo is not at D:/prime-game")
    def test_the_live_greybox_keeps_what_is_pinned(self):
        found = G.drift(G.load(), G.read())
        self.assertEqual(found, [], "the game removed or moved pinned greybox data; take it on purpose, then refresh "
                                    "with $PYTHON_BIN tools/tests/_house_greybox.py")


if __name__ == "__main__":
    unittest.main()
