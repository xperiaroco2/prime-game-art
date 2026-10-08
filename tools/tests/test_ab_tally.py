"""`ab-tally` (#46): the counts per side, the misses, the $ and the stop rule of the art critic's A/B."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from runner import cli, common
from runner.commands import ab_tally

FIXTURES = common.ROOT / "tools" / "tests" / "fixtures" / "ab_tally"


def record(n: int) -> dict:
    return json.loads((FIXTURES / f"round{n}.json").read_text(encoding="utf-8"))


def clean_round(n: int, trial_invalid: int = 0) -> dict:
    """A round where both critics find the same two valid problems (one serious), plus trial_invalid wrong ones."""
    rec = copy.deepcopy(record(1))
    rec["round"] = n
    make = lambda i, side, verdict, severity: {"id": f"{side}{i}", "side": side, "variant": "v1", "text": "t",
                                              "critic_severity": severity, "verdict": verdict,
                                              "severity": severity, "reason": "r", "judged": True}
    rec["remarks"] = [make(1, "A", "valid", "serious"), make(2, "A", "valid", "minor"),
                      make(1, "B", "valid", "serious"), make(2, "B", "valid", "minor")]
    rec["remarks"] += [make(3 + i, "A", "invalid", "minor") for i in range(trial_invalid)]
    rec["pairs"] = [{"a": "A1", "b": "B1"}, {"a": "A2", "b": "B2"}]
    return rec


class TallyTest(unittest.TestCase):
    def test_counts_per_side(self) -> None:
        t = ab_tally.tally([record(1), record(2)])
        trial, control = t.sides["trial"], t.sides["control"]
        self.assertEqual((trial.model, control.model, t.judge_model), ("sonnet", "opus", "opus"))
        self.assertEqual((trial.remarks, trial.valid, trial.serious_valid, trial.invalid, trial.unsure,
                          trial.unjudged), (6, 3, 1, 2, 1, 1))
        self.assertEqual((control.remarks, control.valid, control.serious_valid, control.invalid, control.unsure),
                         (5, 4, 3, 0, 1))
        # round 1: the trial missed B2 (serious), the control missed A2 (minor); round 2: the trial missed A1
        self.assertEqual((trial.missed, trial.missed_serious, control.missed, control.missed_serious), (2, 2, 1, 0))
        self.assertAlmostEqual(trial.invalid_share, 100 * 2 / 6)
        self.assertEqual(t.extra_misses, 2)

    def test_dollars(self) -> None:
        t = ab_tally.tally([record(1), record(2)])
        self.assertEqual(ab_tally.dollars(t.sides["trial"].costs, 2), "$0.90, $0.45/round")
        self.assertEqual(ab_tally.dollars(t.judge_costs, 2), "$1.50, $1.50/round (1 of 2 rounds)")
        self.assertEqual(ab_tally.dollars([], 2), "-")

    def test_stop_rule(self) -> None:
        self.assertEqual(ab_tally.verdict(ab_tally.tally([record(1)])), "continue (1 of 6 rounds)")
        self.assertTrue(ab_tally.verdict(ab_tally.tally([record(1), record(2)])).startswith("stop: keep opus"))
        six = [clean_round(n) for n in range(1, 7)]
        self.assertTrue(ab_tally.verdict(ab_tally.tally(six)).startswith("after 6 rounds: keep sonnet"))
        noisy = [clean_round(n, trial_invalid=1) for n in range(1, 7)]  # 1 of 3 invalid: 33 points over 0
        advice = ab_tally.verdict(ab_tally.tally(noisy))
        self.assertTrue(advice.startswith("after 6 rounds: keep opus"), advice)
        self.assertIn("invalid share", advice)

    def test_a_valid_ratio_under_the_bar_keeps_the_control(self) -> None:
        rounds = [clean_round(n) for n in range(1, 7)]
        for rec in rounds[:2]:  # the trial finds nothing in two rounds: 8 valid of the control's 12
            rec["remarks"] = [r for r in rec["remarks"] if r["side"] == "B"]
            rec["pairs"] = []
            for r in rec["remarks"]:
                r["severity"] = "minor"  # no serious misses, so only the ratio decides
        advice = ab_tally.verdict(ab_tally.tally(rounds))
        self.assertIn("8 valid remarks against 12", advice)

    def test_bad_records_are_refused(self) -> None:
        cases = {
            "schema": lambda r: r.update(schema="x"),
            "labels must map": lambda r: r.update(labels={"A": "trial", "B": "trial"}),
            "unique string id": lambda r: r["remarks"].append(dict(r["remarks"][0])),
            "verdict": lambda r: r["remarks"][0].update(verdict="maybe"),
            "pair": lambda r: r["pairs"].append({"a": "A2", "b": "B9"}),
            "each in one pair": lambda r: r["pairs"].append({"a": "A2", "b": "B1"}),
            "cost_usd": lambda r: r.update(cost_usd={"critic": 1}),
        }
        for piece, spoil in cases.items():
            with self.subTest(piece=piece):
                rec = record(1)
                spoil(rec)
                with self.assertRaises(ValueError) as caught:
                    ab_tally.check(rec)
                self.assertIn(piece, str(caught.exception))

    def test_mixed_models_and_repeated_rounds_are_refused(self) -> None:
        other = record(2)
        other["models"]["trial"] = "haiku"
        with self.assertRaises(common.Failure):
            ab_tally.tally([record(1), other])
        with self.assertRaises(common.Failure):
            ab_tally.tally([record(1), record(1)])


class CommandTest(unittest.TestCase):
    def test_prints_the_table_and_the_verdict(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["ab-tally", str(FIXTURES / "round1.json"), str(FIXTURES / "round2.json")])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("trial    sonnet        6     3       1       2      1    33.3%      2              2", text)
        self.assertIn("1 remark(s) had no verdict", text)
        self.assertIn("verdict: stop: keep opus", text)

    def test_unreadable_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "judge.json"
            bad.write_text("{", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertNotEqual(cli.main(["ab-tally", str(bad)]), 0)


if __name__ == "__main__":
    unittest.main()
