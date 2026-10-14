"""verify's affected run (#159): the fast/heavy split, the area mapping, the change list and the parallel runner."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runner import common
from runner.commands import _testrun as tr

HAVE_GIT = bool(shutil.which("git"))


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=common.ROOT, capture_output=True, text=True, encoding="utf-8")
    return out.stdout.split()


class ClassifyTest(unittest.TestCase):
    def test_marker_and_helper_make_a_file_heavy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Built from pieces so that this file itself does not read as heavy.
            godot, blender = "have(pins." + "GODOT_ENV, None)", "common.tool_path(pins." + "BLENDER_ENV, None)"
            (root / "_fixture.py").write_text(f"HAVE = {godot}\n", encoding="utf-8")
            (root / "test_a.py").write_text(f"x = {blender}\n", encoding="utf-8")
            (root / "test_b.py").write_text("from . import _fixture as fx\n", encoding="utf-8")
            (root / "test_c.py").write_text("from ._fixture import HAVE\n", encoding="utf-8")
            (root / "test_d.py").write_text("import json\nfrom runner import common\n", encoding="utf-8")
            fast, heavy = tr.split(["test_a.py", "test_b.py", "test_c.py", "test_d.py"], root)
            self.assertEqual(heavy, ["test_a.py", "test_b.py", "test_c.py"])
            self.assertEqual(fast, ["test_d.py"])

    def test_classification_matches_the_measured_runs(self) -> None:
        # timings.json records, per file, whether its last full run started Blender or Godot (on the desktop, with
        # both installed): such a file must read as heavy, and a heavy file must have started one.
        data = json.loads(tr.TIMINGS.read_text(encoding="utf-8"))
        rows = {row["file"]: row for row in data["files"]}
        for path in tr.test_files():
            if path.name not in rows:
                continue
            with self.subTest(file=path.name):
                self.assertEqual(tr.is_heavy_file(path), rows[path.name]["launched"])

    def test_a_fast_file_that_starts_blender_is_red(self) -> None:
        def fake_run(cmd, env, **kwargs):
            Path(env[common.HEAVY_PROBE_ENV]).touch()
            return subprocess.CompletedProcess(cmd, 0, "", "Ran 1 test in 0.1s\n\nOK\n")

        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            fast = tr.run_file("test_zz_probe_fast.py", False)
            heavy = tr.run_file("test_zz_probe_heavy.py", True)
        self.assertTrue(fast.launched)
        self.assertNotEqual(fast.returncode, 0)
        self.assertIn("HEAVY_MARKERS", fast.output)
        self.assertEqual((heavy.launched, heavy.returncode), (True, 0))


class AreasTest(unittest.TestCase):
    areas = tr.load_areas()

    @unittest.skipUnless(HAVE_GIT, "needs git")
    def test_every_tracked_file_is_mapped(self) -> None:
        a = self.areas
        unmapped = [
            f for f in tracked_files()
            if not (f.startswith("tools/tests/test") or tr.matches(f, a.shared) or tr.matches(f, a.light)
                    or any(tr.matches(f, sources) for sources, _ in a.areas.values()))
        ]
        self.assertEqual(unmapped, [], "add these to tools/tests/areas.toml (an area, light or shared)")

    @unittest.skipUnless(HAVE_GIT, "needs git")
    def test_no_stale_pattern(self) -> None:
        files = tracked_files()
        names = [p.name for p in tr.test_files()]
        for area, (sources, tests) in self.areas.areas.items():
            for pattern in sources:
                with self.subTest(area=area, source=pattern):
                    self.assertTrue(any(tr.matches(f, [pattern]) for f in files))
            for pattern in tests:
                with self.subTest(area=area, test=pattern):
                    self.assertTrue(any(tr.matches(n, [pattern]) for n in names))


class SelectTest(unittest.TestCase):
    areas = tr.Areas(
        shared=["tools/runner/common.py", "tools/tests/_*.py"],
        light=["docs/*", "*.md"],
        areas={"anim": (["tools/blender/anim_*"], ["test_anim_*"]), "faces": (["faces/*"], ["test_faces_*"])},
    )
    heavy = ["test_anim_set_blender.py", "test_faces_blender.py"]

    def test_area_source_picks_its_heavy_tests(self) -> None:
        sel = tr.select(["tools/blender/anim_set.py", "docs/x.md"], self.areas, self.heavy)
        self.assertFalse(sel.full)
        self.assertEqual(list(sel.heavy), ["test_anim_set_blender.py"])
        self.assertIn("area anim", sel.heavy["test_anim_set_blender.py"][0])

    def test_light_paths_pick_nothing(self) -> None:
        sel = tr.select(["docs/agents.md", "README.md"], self.areas, self.heavy)
        self.assertEqual((sel.full, sel.heavy), (False, {}))

    def test_a_changed_test_file_runs_itself(self) -> None:
        sel = tr.select(["tools/tests/test_faces_blender.py", "tools/tests/test_anim_math.py"], self.areas, self.heavy)
        self.assertEqual(list(sel.heavy), ["test_faces_blender.py"])  # a fast file runs anyway

    def test_shared_module_runs_the_full_suite(self) -> None:
        for path in ("tools/runner/common.py", "tools/tests/_export_fixture.py"):
            with self.subTest(path=path):
                sel = tr.select(["faces/styles.json", path], self.areas, self.heavy)
                self.assertTrue(sel.full)
                self.assertEqual(sorted(sel.heavy), self.heavy)

    def test_unmapped_path_runs_the_full_suite(self) -> None:
        sel = tr.select(["tools/blender/new_thing.py"], self.areas, self.heavy)
        self.assertTrue(sel.full)
        self.assertIn("no area", sel.full_reason)

    def test_a_deleted_file_still_maps(self) -> None:
        # A deleted path is in the diff but not on disk; its area still applies, a deleted test file is not run.
        sel = tr.select(["faces/gone.json", "tools/tests/test_anim_gone_blender.py"], self.areas, self.heavy)
        self.assertEqual(list(sel.heavy), ["test_faces_blender.py"])


@unittest.skipUnless(HAVE_GIT, "needs git")
class ChangedFilesTest(unittest.TestCase):
    def git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.hooksPath=", *args],
                       cwd=root, check=True, capture_output=True)

    def test_branch_staged_unstaged_untracked_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.git(root, "init", "-q", "-b", "main")
            for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
                (root / name).write_text(name, encoding="utf-8")
            self.git(root, "add", ".")
            self.git(root, "commit", "-q", "-m", "base")
            self.git(root, "checkout", "-q", "-b", "task")
            (root / "a.txt").write_text("changed", encoding="utf-8")
            self.git(root, "rm", "-q", "b.txt")
            self.git(root, "commit", "-q", "-am", "task")
            self.git(root, "checkout", "-q", "main")
            (root / "z.txt").write_text("main moved on", encoding="utf-8")
            self.git(root, "add", "z.txt")
            self.git(root, "commit", "-q", "-m", "main")
            self.git(root, "checkout", "-q", "task")
            (root / "c.txt").write_text("unstaged", encoding="utf-8")
            self.git(root, "rm", "-q", "--cached", "d.txt")
            (root / "new.txt").write_text("untracked", encoding="utf-8")
            # z.txt changed on main after the merge base: not this branch's change.
            self.assertEqual(tr.changed_files("main", root), ["a.txt", "b.txt", "c.txt", "d.txt", "new.txt"])
            with self.assertRaises(common.Failure):
                tr.changed_files("no-such-ref", root)


class RunFilesTest(unittest.TestCase):
    def fake(self, red: set[str], ran: list[str]):
        def runner(name: str, heavy: bool, verbose: bool, env):
            ran.append(name)
            code = 1 if name in red else 0
            return tr.FileResult(name, heavy, code, 0.1, f"output of {name}\nRan 2 tests in 0.1s\n", tests=2)
        return runner

    def run_files(self, fast, heavy, red=()):
        ran: list[str] = []
        out = io.StringIO()
        with mock.patch.object(common, "heavy_lock", lambda what: contextlib.nullcontext()), \
                contextlib.redirect_stdout(out):
            results = tr.run_files(fast, heavy, workers=2, runner=self.fake(set(red), ran))
        return results, ran, out.getvalue()

    def test_green_runs_fast_then_heavy(self) -> None:
        results, ran, text = self.run_files(["test_a.py", "test_b.py"], ["test_h.py"])
        self.assertEqual(sorted(ran[:2]), ["test_a.py", "test_b.py"])
        self.assertEqual(ran[2], "test_h.py")
        self.assertTrue(all(r.returncode == 0 for r in results))
        self.assertIn("3 files, 6 tests", text)
        self.assertNotIn("output of", text)

    def test_a_red_fast_file_is_red_shows_its_output_and_skips_heavy(self) -> None:
        results, ran, text = self.run_files(["test_a.py", "test_b.py"], ["test_h.py"], red={"test_b.py"})
        self.assertNotIn("test_h.py", ran)
        self.assertEqual([r.name for r in results if r.returncode], ["test_b.py"])
        self.assertIn("RED", text)
        self.assertIn("output of test_b.py", text)
        self.assertNotIn("output of test_a.py", text)
        self.assertIn("did not run", text)

    def test_a_red_heavy_file_is_red(self) -> None:
        results, _, text = self.run_files(["test_a.py"], ["test_h.py"], red={"test_h.py"})
        self.assertEqual([r.name for r in results if r.returncode], ["test_h.py"])
        self.assertIn("output of test_h.py", text)

    def test_run_file_counts_tests_and_skips(self) -> None:
        done = subprocess.CompletedProcess([], 0, "", "....s\nRan 5 tests in 0.2s\n\nOK (skipped=1)\n")
        with mock.patch.object(subprocess, "run", return_value=done):
            res = tr.run_file("test_x.py", False)
        self.assertEqual((res.tests, res.skipped, res.returncode), (5, 1, 0))


if __name__ == "__main__":
    unittest.main()
