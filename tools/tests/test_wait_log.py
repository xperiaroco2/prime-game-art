"""`wait` (#55): the exit marker, the summary, the deadline and its own exit codes, on small temporary logs."""

import codecs
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from runner.commands import wait


class FakeClock:
    """A clock that moves only when the command sleeps."""

    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


def run_wait(log: str, max_seconds: int = wait.DEFAULT_MAX, **kw: object) -> tuple[int, list[str], FakeClock]:
    fake = FakeClock()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = wait.main(log, max_seconds, clock=fake.clock, sleep=fake.sleep, now=lambda: 0.0, **kw)
    return code, out.getvalue().splitlines(), fake


class ExitMarkerTest(unittest.TestCase):
    def test_last_non_empty_line_is_the_marker(self) -> None:
        self.assertEqual(wait.exit_code(["a", "exit=3", "", "  "]), 3)

    def test_marker_inside_the_output_is_not_the_end(self) -> None:
        self.assertIsNone(wait.exit_code(["exit=0", "still working"]))

    def test_empty_log_is_running(self) -> None:
        self.assertIsNone(wait.exit_code([]))

    def test_not_a_marker(self) -> None:
        self.assertIsNone(wait.exit_code(["exit=ok"]))
        self.assertIsNone(wait.exit_code(["the exit=0"]))


class ReadLinesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "job.log"

    def test_half_written_line_is_left_out(self) -> None:
        self.path.write_bytes(b"one\r\ntwo\nexit=")
        self.assertEqual(wait.read_lines(self.path), ["one", "two"])

    def test_utf16_with_bom(self) -> None:
        self.path.write_bytes(codecs.BOM_UTF16_LE + "done\r\nexit=0\r\n".encode("utf-16-le"))
        self.assertEqual(wait.read_lines(self.path), ["done", "exit=0"])

    def test_missing_log(self) -> None:
        self.assertIsNone(wait.read_lines(self.path))


class SummaryTest(unittest.TestCase):
    def test_verify_lines_when_there_are_any(self) -> None:
        lines = ["== verify: selftest", "Ran 9 tests", "OK", "== verify: selftest green (1.0 s)",
                 "verify: green (selftest, manifest-check)", "exit=0"]
        self.assertEqual(
            wait.summary_lines(lines),
            ["== verify: selftest", "== verify: selftest green (1.0 s)", "verify: green (selftest, manifest-check)"],
        )

    def test_last_lines_otherwise(self) -> None:
        lines = [f"line {i}" for i in range(20)] + ["", "exit=1", ""]
        self.assertEqual(wait.summary_lines(lines), [f"line {i}" for i in range(12, 20)])


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "job.log"

    def test_finished_job_returns_its_code(self) -> None:
        self.path.write_text("work\nexit=5\n", encoding="utf-8")
        code, out, fake = run_wait(str(self.path))
        self.assertEqual(code, 5)
        self.assertEqual(out[0], "work")
        self.assertTrue(out[-1].startswith("wait: job.log finished: exit=5"))
        self.assertEqual(fake.slept, [])

    def test_running_job_times_out_with_124(self) -> None:
        self.path.write_text("work\n", encoding="utf-8")
        code, out, fake = run_wait(str(self.path), 10)
        self.assertEqual(code, wait.STILL_RUNNING)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("wait: still running after 10 s"))
        self.assertAlmostEqual(sum(fake.slept), 10.0)

    def test_missing_log_returns_2_after_the_grace(self) -> None:
        code, out, fake = run_wait(str(self.path))
        self.assertEqual(code, wait.MISSING)
        self.assertTrue(out[0].startswith("wait: no log at"))
        self.assertAlmostEqual(fake.t, wait.APPEAR_GRACE, delta=wait.POLL_SECONDS)

    def test_max_out_of_range(self) -> None:
        for bad in (0, wait.MAX_ALLOWED + 1):
            with self.subTest(max=bad):
                code, out, _ = run_wait(str(self.path), bad)
                self.assertEqual(code, wait.MISSING)
                self.assertTrue(out[0].startswith("wait: --max is 1 to 170 s"))

    def test_a_folder_is_not_a_log(self) -> None:
        code, out, _ = run_wait(self.dir.name)
        self.assertEqual(code, wait.MISSING)
        self.assertTrue(out[0].startswith("wait: cannot read"))

    def test_the_step_keeps_the_cache_warm(self) -> None:
        self.assertEqual(wait.DEFAULT_MAX, wait.MAX_ALLOWED)
        self.assertLessEqual(wait.MAX_ALLOWED + 94, wait.CACHE_TTL)  # prime-game#555's p95 overhead
        self.assertLessEqual(wait.MAX_ALLOWED + 10, wait.TOOL_CALL_MAX)  # room for start-up inside one call


class NativePathTest(unittest.TestCase):
    def test_git_bash_drive(self) -> None:
        self.assertEqual(wait.native_path("/c/x/y.log", windows=True), Path("C:/x/y.log"))

    def test_other_forms_kept(self) -> None:
        self.assertEqual(wait.native_path("/c/x/y.log", windows=False), Path("/c/x/y.log"))
        self.assertEqual(wait.native_path("D:/a b/y.log", windows=True), Path("D:/a b/y.log"))


if __name__ == "__main__":
    unittest.main()
