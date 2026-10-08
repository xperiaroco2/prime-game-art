"""`workflow-check` (#56): every refusal has a bad fixture script; the good fixtures and the lab-round template pass."""

import shutil
import tempfile
import unittest
from pathlib import Path

from runner import cli, common
from runner.commands import _workflow_lint as lint
from runner.commands import workflow_check

FIXTURES = common.ROOT / "tools" / "tests" / "fixtures" / "workflows"
TEMPLATE = common.ROOT / "tools" / "workflows" / "art-lab-round.js"
HAS_NODE = shutil.which("node") is not None
GOOD = ("good.js", "good_meta_comment.js", "good_meta_no_semicolon.js", "good_opus_reader.js",
        "good_per_launch_model.js")  # pass every check, node's too

# fixture -> (line, a piece of the one refusal it must get)
BAD = {
    "no_meta.js": (1, "must start with `export const meta"),
    "meta_not_literal.js": (1, "`meta` must be a pure literal; found `describe`"),
    "no_agent_type.js": (13, "agent() has no agentType"),
    "bad_agent_type.js": (13, "agentType 'general-purpose' is not"),
    "general_no_reason.js": (16, "agent() has no agentType"),
    "effort_xhigh.js": (13, "effort 'xhigh' is not allowed"),
    "effort_max.js": (13, "effort 'max' is not allowed"),
    "reader_opus.js": (14, "an art-reader agent runs on Sonnet"),
    "reader_opus_no_reason.js": (15, "an art-reader agent runs on Sonnet"),
    "per_launch_model_unmarked.js": (14, "model must be a string literal"),
    "no_bounds.js": (14, "has no `BOUNDS: at most N tool calls`"),
    "bounds_over.js": (13, "allows 120 tool calls; at most 60"),
    "no_wait_rule.js": (16, "the agent prompt never states the 180 s wait rule"),
    "nondeterministic.js": (17, "Math.random() breaks resume"),
    "member_agent.js": (14, "a member call `x.agent(` is not checked"),
}


def static(name: str) -> list[tuple[int, str]]:
    return lint.check_text((FIXTURES / name).read_bytes().decode("utf-8"))


class StaticChecksTest(unittest.TestCase):
    def test_fixtures_are_lf(self) -> None:
        for path in [*FIXTURES.glob("*.js"), TEMPLATE]:
            with self.subTest(path=path.name):
                self.assertNotIn(b"\r", path.read_bytes())

    def test_good_fixtures_pass(self) -> None:
        for name in GOOD:
            with self.subTest(fixture=name):
                self.assertEqual(static(name), [])

    def test_template_passes(self) -> None:
        self.assertEqual(lint.check_text(TEMPLATE.read_text(encoding="utf-8")), [])

    def test_every_bad_fixture_gets_its_one_refusal(self) -> None:
        self.assertEqual(set(BAD) | set(GOOD) | {"syntax.js"}, {p.name for p in FIXTURES.glob("*.js")})
        for name, (line, piece) in BAD.items():
            with self.subTest(fixture=name):
                found = static(name)
                self.assertEqual(len(found), 1, found)
                self.assertEqual(found[0][0], line, found)
                self.assertIn(piece, found[0][1])

    def test_crlf_is_refused(self) -> None:
        text = (FIXTURES / "good.js").read_text(encoding="utf-8").replace("\n", "\r\n")
        self.assertEqual(lint.check_text(text), [(1, "line endings are not LF (CRLF is refused at resume)")])

    def test_general_agent_comment_needs_to_be_right_before(self) -> None:
        text = (FIXTURES / "good.js").read_text(encoding="utf-8").replace(
            "*/\nawait agent(", "*/\nconst published = 1;\nawait agent(")
        self.assertIn("agent() has no agentType", lint.check_text(text)[0][1])

    def test_each_marker_grants_only_its_own_exemption(self) -> None:
        text = (FIXTURES / "good_opus_reader.js").read_text(encoding="utf-8")
        for marker, refusal in (("per-launch-model", "an art-reader agent runs on Sonnet"),
                                ("general-agent", "an art-reader agent runs on Sonnet")):
            with self.subTest(marker=marker):
                found = lint.check_text(text.replace("/* opus-reader:", f"/* {marker}:"))
                self.assertEqual(len(found), 1, found)
                self.assertIn(refusal, found[0][1])
        per_launch = (FIXTURES / "good_per_launch_model.js").read_text(encoding="utf-8")
        found = lint.check_text(per_launch.replace("/* per-launch-model:", "/* opus-reader:"))
        self.assertIn("model must be a string literal", found[0][1])

    def test_a_marker_before_the_statement_counts(self) -> None:
        text = (FIXTURES / "good_opus_reader.js").read_text(encoding="utf-8")
        for start in ("verdict = await agent(", "let verdict = agent(", "await agent("):
            with self.subTest(start=start):
                self.assertEqual(lint.check_text(text.replace("const verdict = await agent(", start)), [])

    def test_bounds_in_a_template_expression_is_not_read(self) -> None:
        text = (FIXTURES / "good.js").read_text(encoding="utf-8").replace("at most 60 tool", "at most ${60} tool")
        self.assertIn("has no `BOUNDS", lint.check_text(text)[0][1])

    def test_non_literal_effort_is_refused(self) -> None:
        text = (FIXTURES / "good.js").read_text(encoding="utf-8").replace("effort: 'high'", "effort: level")
        self.assertIn("effort must be a string literal", lint.check_text(text)[0][1])

    def test_other_member_forms_of_date_now_are_refused(self) -> None:
        text = (FIXTURES / "good.js").read_text(encoding="utf-8")
        for expr, name in (("Date['now']()", "Date.now()"), ('Math["random"]()', "Math.random()"),
                           ("Date?.now()", "Date.now()")):
            with self.subTest(expr=expr):
                found = lint.check_text(text.replace("ratio: 4 / 2", f"ratio: {expr}"))
                self.assertEqual(found, [(17, f"{name} breaks resume; workflow scripts are deterministic")])

    def test_an_alias_of_date_passes(self) -> None:
        # the documented limit (docs/agents.md): the check reads tokens, not values
        text = (FIXTURES / "good.js").read_text(encoding="utf-8")
        self.assertEqual(lint.check_text(text.replace("ratio: 4 / 2", "ratio: D.now()") + "const D = Date;\n"), [])

    def test_module_copy_keeps_line_numbers(self) -> None:
        text = (FIXTURES / "good.js").read_text(encoding="utf-8")
        copy = lint.module_copy(text)
        self.assertEqual(copy.splitlines()[1:17], text.splitlines()[1:17])
        self.assertIsNone(lint.module_copy("// x\n" + text))

    def test_module_copy_ends_meta_with_a_semicolon(self) -> None:
        text = (FIXTURES / "good_meta_no_semicolon.js").read_text(encoding="utf-8")
        self.assertIn("null] }; async function __workflow_body__() {\n", lint.module_copy(text))
        self.assertEqual(lint.module_copy(text.replace("null] }", "null] };", 1)), lint.module_copy(text))

    def test_meta_end_skips_comments(self) -> None:
        text = (FIXTURES / "good_meta_comment.js").read_text(encoding="utf-8")
        self.assertEqual(text[:lint.meta_end(text)].splitlines()[-1], "};")
        self.assertIsNone(lint.meta_end("export const meta = { /* open"))


@unittest.skipUnless(HAS_NODE, "node is not installed")
class NodeCheckTest(unittest.TestCase):
    def test_syntax_error_is_refused_with_its_line(self) -> None:
        self.assertEqual(static("syntax.js"), [])
        found, note = workflow_check.check_file(FIXTURES / "syntax.js")
        self.assertIsNone(note)
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0][0], 17)
        self.assertTrue(found[0][1].startswith("node --check: "), found)

    def test_good_and_template_parse(self) -> None:
        for path in (*(FIXTURES / name for name in GOOD), TEMPLATE):
            with self.subTest(path=path.name):
                self.assertEqual(workflow_check.check_file(path), ([], None))


class CommandTest(unittest.TestCase):
    def test_exit_codes(self) -> None:
        self.assertEqual(cli.main(["workflow-check", str(TEMPLATE), str(FIXTURES / "good.js")]), 0)
        self.assertEqual(cli.main(["workflow-check", str(FIXTURES / "no_bounds.js")]), 1)

    def test_missing_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            found, _ = workflow_check.check_file(Path(tmp) / "absent.js")
        self.assertEqual(found, [(0, "no such file")])

    def test_missing_node_is_a_note(self) -> None:
        original = workflow_check.shutil.which
        workflow_check.shutil.which = lambda name: None
        try:
            found, note = workflow_check.check_file(FIXTURES / "syntax.js")
        finally:
            workflow_check.shutil.which = original
        self.assertEqual(found, [])
        self.assertIn("node --check skipped", note)


if __name__ == "__main__":
    unittest.main()
