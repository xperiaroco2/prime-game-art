"""The lab-round template in a dry run (#46): node runs it with a fake agent(); skipped without node."""

import json
import re
import shutil
import subprocess
import unittest

from runner import common
from runner.commands import ab_tally

TEMPLATE = common.ROOT / "tools" / "workflows" / "art-lab-round.js"
HARNESS = common.ROOT / "tools" / "tests" / "fixtures" / "lab_round_dry.mjs"
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is not installed")
class LabRoundDryRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        done = subprocess.run([NODE, str(HARNESS), str(TEMPLATE)], capture_output=True, text=True, timeout=60,
                              encoding="utf-8")
        if done.returncode != 0:
            raise AssertionError(done.stderr[-2000:])
        cls.out = json.loads(done.stdout)

    def test_refuses_without_a_critic_model(self) -> None:
        missing, unknown, same, no_round = self.out["refusals"]
        self.assertIn("needs arg critic_model", missing)
        self.assertIn("needs arg critic_model", unknown)
        self.assertIn("differ from critic_model", same)
        self.assertIn("needs arg round", no_round)

    def test_single_critic_runs_on_the_launch_model(self) -> None:
        calls = self.out["launches"]["single"]["calls"]
        self.assertEqual([(c["label"], c["model"]) for c in calls], [("builder step 1", "opus"), ("critic", "sonnet")])

    def test_ab_rounds_alternate_the_labels_and_hide_the_models(self) -> None:
        for name, trial in (("round1", "A"), ("round2", "B")):
            with self.subTest(round=name):
                launch = self.out["launches"][name]
                models = {c["label"]: c["model"] for c in launch["calls"]}
                control = "B" if trial == "A" else "A"
                self.assertEqual((models[f"critic {trial}"], models[f"critic {control}"], models["judge"]),
                                 ("sonnet", "opus", "opus"))
                self.assertTrue(all(c["agentType"] == "art-reader" for c in launch["calls"][1:]))
                self.assertIsNone(re.search(r"sonnet|opus|haiku|trial|control|round \d", launch["judge_prompt"], re.I))
                record = launch["result"]["ab_record"]
                ab_tally.check(record)
                self.assertEqual(record["labels"], {trial: "trial", control: "control"})
                # the judge's pairs are cleaned: B1/A1 is turned around, a second use of B1 and an unknown id dropped
                self.assertEqual(record["pairs"], [{"a": "A1", "b": "B1"}])
                unjudged = [r["id"] for r in record["remarks"] if not r["judged"]]
                self.assertEqual(unjudged, ["A2"])


if __name__ == "__main__":
    unittest.main()
