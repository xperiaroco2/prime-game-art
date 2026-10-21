"""M13 (art #196, PR #246's review minor 2): alien_talk.gd's styled() and sample() in Godot 4.7.2, headless
(godot/alien/talk_check.gd): every rule a style claims triggers on LINE (the pout's merged flickers and half-open quick
A/E, its pucker in the pauses, its lag), frog and overbite stay snapped, a closed mouth only presses shut (minor 4),
and the fangs' heavier jaw (the slower opening, the forward thrust on A and E, the smaller bounce). Skips without
Godot."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import common, pins  # noqa: E402
from runner.commands import _godot  # noqa: E402

HAVE_GODOT = common.tool_path(pins.GODOT_ENV, None) is not None


@unittest.skipUnless(HAVE_GODOT, "needs Godot")
class TalkStyleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code, out = _godot.godot(["--headless", "--path", str(_godot.PROJECT), "-s", "res://alien/talk_check.gd"], 120)
        line = next((ln for ln in out.splitlines() if ln.startswith("TALK ")), None)
        if code != 0 or line is None:
            raise AssertionError(f"talk_check.gd: exit {code}\n{out[-2000:]}")
        cls.d = json.loads(line[5:])
        cls.open = cls.d["open"]

    def samples(self, design):
        return self.d["designs"][design]["samples"]

    def test_snapped_designs_follow_the_line(self):
        segs = [[s[0], s[1], s[2]] for s in self.d["segments"]]
        for design in ("frog", "overbite"):
            self.assertEqual(self.d["designs"][design]["styled"], segs, design)
            self.assertTrue(all(s[2] == 0 and s[3] == 0 and s[4] == 0 for s in self.samples(design)), design)

    def test_pout_merges_flickers(self):
        segs, runs = self.d["segments"], self.d["designs"]["pout"]["styled"]
        self.assertLess(len(runs), len(segs))
        merged = [s for s in segs if s[1] - s[0] < 70 and not any(abs(r[0] - s[0]) < 1e-6 for r in runs)]
        self.assertGreaterEqual(len(merged), 2, "the line has no flicker the pout merges")
        for s in merged:  # the run before it holds on through it
            self.assertTrue(any(r[0] < s[0] and abs(r[1] - s[1]) < 1e-6 for r in runs), s)

    def test_pout_shows_quick_open_phases_half_open(self):
        segs, runs = self.d["segments"], self.d["designs"]["pout"]["styled"]
        quick = [s for s in segs if s[2] in ("A", "E") and s[1] - s[0] < 85]
        self.assertTrue(quick, "the line has no quick A or E")
        for s in quick:
            r = next(r for r in runs if abs(r[0] - s[0]) < 1e-6)
            self.assertEqual(r[2], "small", s)

    def test_pout_lags_and_puckers_in_the_pauses(self):
        lag = self.d["styles"]["pout"]["lag_ms"]
        first = self.d["segments"][0]
        by_t = {s[0]: s for s in self.samples("pout")}
        self.assertEqual(by_t[first[0] + lag - 5][1], "rest")
        self.assertEqual(by_t[first[0] + lag + 5][1], first[2])
        pk = [s for s in self.samples("pout") if s[3] > 0.5]
        self.assertTrue(pk)
        self.assertTrue(all(s[1] in ("rest", "M") for s in pk))  # only in a silence

    def test_a_closed_mouth_only_presses_shut(self):
        for design in ("pout", "fangs"):
            ss = self.samples(design)
            closed = [s for s in ss if self.open[s[1]] == 0]
            self.assertTrue(all(s[2] <= 1e-12 for s in closed), design)
            self.assertTrue(any(s[2] < -1e-4 for s in closed), f"{design}: the closing never presses")
            self.assertTrue(any(s[2] > 1e-4 for s in ss if self.open[s[1]] > 0), f"{design}: no opening sag")

    def test_fangs_heavier_jaw(self):
        st = self.d["styles"]["fangs"]
        ss = self.samples("fangs")
        lag, rise = st["lag_ms"], st["rise"]["ms"]
        # "I" (A at 470 ms after a silence) shows small for its first rise ms, then A
        t0 = 470 + lag
        self.assertEqual(next(s for s in ss if s[0] == t0 + 10)[1], "small")
        self.assertEqual(next(s for s in ss if s[0] == t0 + rise + 10)[1], "A")
        thr = [s for s in ss if s[4] > 0]
        self.assertTrue(thr)
        amt = st["thrust"]["amount"]
        for a, b in zip(ss, ss[1:]):  # M13b (PR #248's minor 2): it eases in and out, never snaps
            self.assertLess(abs(b[4] - a[4]), 0.1 * amt, (a, b))
            if a[4] == 0 and b[4] > 0:
                self.assertIn(b[1], ("A", "E"), b)  # it starts only on A or E
        ae = [b for a, b in zip(ss, ss[1:]) if a[1] == "A" and b[1] == "E"]
        self.assertTrue(ae, "the line has no A -> E")
        self.assertTrue(all(b[4] > 0.9 * amt for b in ae), ae)  # A -> E holds the thrust
        self.assertAlmostEqual(max(s[4] for s in ss), st["thrust"]["amount"], places=5)
        pout = self.d["styles"]["pout"]
        self.assertLess(st["bounce"]["amp"], pout["bounce"]["amp"])  # less bounce than the pout
        self.assertLess(max(abs(s[2]) for s in ss), max(abs(s[2]) for s in self.samples("pout")))
        self.assertTrue(all(s[3] == 0 for s in ss))  # no pucker


    def test_tongue_lopsided_and_floppy(self):  # M14: the tongue's loose talk
        st = self.d["styles"]["tongue"]
        runs, pout = self.d["designs"]["tongue"]["styled"], self.d["designs"]["pout"]["styled"]
        self.assertEqual(len(runs), len(pout))  # the same merges, then every second run late
        late = [r[0] - p[0] for r, p in zip(runs, pout)]
        self.assertTrue(all(abs(d) < 1e-6 for d in late[0::2]))
        self.assertTrue(any(abs(d - st["lopside_ms"]) < 1e-6 for d in late[1::2]))
        for a, b in zip(runs, runs[1:]):  # no run overlaps the next
            self.assertLessEqual(a[1], b[0] + 1e-6)
        s = self.samples("tongue")
        fy = [x[6] for x in s]
        self.assertGreater(max(fy), 0.5 * st["flop"]["amp"] * 0.4)  # the tip left up after an opening
        self.assertLess(min(fy), 0.0)  # then it swings down past
        fx = {round(x[5], 6) for x in s if x[1] not in ("rest", "M")}
        self.assertTrue(any(v > 0 for v in fx) and any(v < 0 for v in fx), "it sways to both sides")
        for x in s:  # the sentence pause (after "you", before "mm") never sways
            if 3250 <= x[0] <= 3500:
                self.assertEqual(x[5], 0.0, x)
        for d in ("frog", "pout", "fangs"):  # the other styles have no flop
            self.assertTrue(all(x[5] == 0 and x[6] == 0 for x in self.samples(d)), d)


if __name__ == "__main__":
    unittest.main()
