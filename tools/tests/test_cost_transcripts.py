"""`cost` (#55): the project folder's name, and per-agent calls, context, rewrites and list $ on synthetic transcripts
(tools/tests/fixtures/cost/; no real transcript enters git)."""

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from runner import common
from runner.commands import cost

FIXTURE = common.ROOT / "tools" / "tests" / "fixtures" / "cost" / "C--fixture-repo"
WORKTREE = FIXTURE.with_name("C--fixture-repo-wt-60")  # a worktree session, and s2 again


def by_label(report: dict) -> dict[str, dict]:
    return {a["label"]: a for a in report["agents"]}


class ProjectFolderTest(unittest.TestCase):
    def test_key_follows_the_drive(self) -> None:
        self.assertEqual(cost.project_key("C:\\prime-game-art"), "C--prime-game-art")
        self.assertEqual(cost.project_key("D:\\prime-game-art"), "D--prime-game-art")
        self.assertEqual(cost.project_key("D:/prime-game-art"), "D--prime-game-art")

    def test_folder_under_the_claude_home(self) -> None:
        home = Path("H")
        self.assertEqual(
            cost.project_folder(Path("D:/prime-game-art"), home), home / "projects" / "D--prime-game-art"
        )

    def test_worktree_folders_follow_the_main_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "projects"
            for name in ("C--x-wt-61", "C--x-wt-60", "C--xy", "C--x-other"):
                (projects / name).mkdir(parents=True)
            (projects / "C--x-wt-62").write_text("not a folder", encoding="utf-8")
            folders = cost.project_folders(Path("C:/x"), Path(tmp))
            # the main folder comes first even when it is missing: run() keeps only the folders that exist
            self.assertEqual([f.name for f in folders], ["C--x", "C--x-wt-60", "C--x-wt-61"])
            self.assertEqual(cost.project_folders(Path("C:/x"), Path(tmp) / "none"),
                             [Path(tmp) / "none" / "projects" / "C--x"])

    def test_main_checkout_is_a_repo_root(self) -> None:
        self.assertTrue((cost.main_checkout() / ".git").exists())


class ReadTest(unittest.TestCase):
    def test_one_call_per_message_id_without_synthetic_lines(self) -> None:
        calls, title = cost.read_transcript(FIXTURE / "s1.jsonl")
        self.assertEqual(title, "art manager")
        self.assertEqual([c["output"] for c in calls], [200, 50, 10])
        self.assertEqual(calls[0]["t1"] - calls[0]["t0"], 5)


class CollectTest(unittest.TestCase):
    def test_every_agent_with_its_figures(self) -> None:
        report = cost.collect(FIXTURE, [], None)
        agents = by_label(report)
        self.assertEqual(sorted(agents), ["art manager", "build:55", "main"])

        manager = agents["art manager"]
        self.assertEqual((manager["model"], manager["calls"]), ("claude-opus-5-5", 3))
        self.assertEqual((manager["first_context"], manager["avg_context"], manager["peak_context"]),
                         (30002, 40335, 60001))
        self.assertEqual((manager["rewrites"], manager["rewrite_tokens"]), (1, 60000))
        self.assertAlmostEqual(manager["usd"], (8 + 150000 + 4000 + 4 + 5000 + 6000 + 1000 + 4 + 300000 + 200) / 1e6)

        sub = agents["build:55"]
        self.assertEqual((sub["type"], sub["agent"], sub["session"]), ("art-writer", "a1", "s1"))
        self.assertEqual(sub["rewrites"], 0)  # a gap over 5 minutes, but under REWRITE_MIN written
        self.assertAlmostEqual(sub["usd"], (6 + 80000 + 100 + 2 + 100000 + 4000 + 100) / 1e6)  # a 1-hour write

        total = report["total"]
        self.assertEqual((total["agents"], total["calls"], total["rewrites"]), (3, 7, 1))
        self.assertEqual(total["unpriced"], ["claude-future-9"])

    def test_session_prefix(self) -> None:
        report = cost.collect(FIXTURE, ["s2"], None)
        self.assertEqual([a["session"] for a in report["agents"]], ["s2"])
        self.assertAlmostEqual(report["agents"][0]["usd"], 10 / 1e6 + 4.0)  # the unknown model at the first prices

    def test_since_keeps_the_gap_before_the_window(self) -> None:
        report = cost.collect(FIXTURE, ["s1"], cost.parse_time("2026-10-08T10:05:00Z"))
        agents = by_label(report)
        self.assertEqual((agents["art manager"]["calls"], agents["art manager"]["rewrites"]), (1, 1))
        self.assertEqual(agents["build:55"]["calls"], 1)

    def test_worktree_folder_is_read_and_a_repeated_call_counts_once(self) -> None:
        report = cost.collect([FIXTURE, WORKTREE, FIXTURE], [], None)
        self.assertEqual(report["folders"], [str(FIXTURE), str(WORKTREE)])
        agents = by_label(report)
        self.assertEqual(sorted(agents), ["art manager", "build:55", "main", "worktree session"])
        self.assertEqual(agents["main"]["calls"], 2)  # s2 is in both folders
        self.assertEqual(report["total"]["calls"], 7 + 4)

    def test_a_one_hour_write_is_a_rewrite_only_after_an_hour(self) -> None:
        wt = by_label(cost.collect(WORKTREE, ["s3"], None))["worktree session"]
        self.assertEqual((wt["calls"], wt["rewrites"], wt["rewrite_tokens"]), (4, 2, 130000))
        call = {"write": 70000, "write_1h": 50000}
        self.assertEqual([cost.expired_write(call, gap) for gap in (300, 301, 3600, 3601)], [0, 20000, 20000, 70000])

    def test_bad_time(self) -> None:
        with self.assertRaises(common.Failure):
            cost.parse_time("yesterday")


class RunTest(unittest.TestCase):
    def test_prints_rows_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "cost.json"
            args = argparse.Namespace(since=None, session=[], project=FIXTURE, json=out_file)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cost.run(args), 0)
            text = out.getvalue()
            self.assertIn("build:55", text)
            self.assertIn("total: 3 agents, 7 calls, 1 rewrites", text)
            self.assertIn("claude-future-9", text)
            self.assertEqual(json.loads(out_file.read_text(encoding="utf-8"))["total"]["calls"], 7)

    def test_empty_folder_prints_the_total_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            out_file = Path(tmp) / "cost.json"
            args = argparse.Namespace(since=None, session=[], project=empty, json=out_file)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cost.run(args), 0)
            text = out.getvalue()
            self.assertIn("no API calls", text)
            self.assertIn("total: 0 agents, 0 calls", text)
            self.assertEqual(json.loads(out_file.read_text(encoding="utf-8"))["agents"], [])

    def test_missing_folder(self) -> None:
        args = argparse.Namespace(since=None, session=[], project=FIXTURE / "nothing", json=Path("unused"))
        with self.assertRaises(common.Failure):
            cost.run(args)


if __name__ == "__main__":
    unittest.main()
