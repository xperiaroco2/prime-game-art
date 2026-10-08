"""The lean workflow agent types in .claude/agents/ (docs/agents.md, #44) keep to their allowlists."""

import unittest

from runner import common

AGENTS = common.ROOT / ".claude" / "agents"
READER_TOOLS = {"Read", "Grep", "Glob", "Bash", "PowerShell", "WebFetch", "WebSearch", "TaskStop"}
EXPECTED = {
    "art-reader": ("sonnet", READER_TOOLS),
    "art-writer": ("opus", READER_TOOLS | {"Edit", "Write"}),
}
ALWAYS_DISALLOWED = {"NotebookEdit", "Agent", "Skill"}


def front_matter(name: str) -> dict[str, str]:
    lines = (AGENTS / f"{name}.md").read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise AssertionError(f"{name}.md has no front matter")
    fields = {}
    for line in lines[1:lines.index("---", 1)]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def tool_set(value: str) -> set[str]:
    return {t.strip() for t in value.split(",") if t.strip()}


class AgentTypesTest(unittest.TestCase):
    def test_only_the_known_types(self) -> None:
        self.assertEqual({p.stem for p in AGENTS.glob("*.md")}, set(EXPECTED))

    def test_each_type_keeps_its_model_and_allowlist(self) -> None:
        for name, (model, tools) in EXPECTED.items():
            with self.subTest(name=name):
                fields = front_matter(name)
                self.assertEqual(fields.get("name"), name)
                self.assertEqual(fields.get("model"), model)
                self.assertEqual(tool_set(fields.get("tools", "")), tools)
                self.assertTrue(fields.get("description"))

    def test_no_type_widens_permissions_or_spawns(self) -> None:
        for name in EXPECTED:
            with self.subTest(name=name):
                fields = front_matter(name)
                self.assertLessEqual(ALWAYS_DISALLOWED, tool_set(fields.get("disallowedTools", "")))
                for key in ("permissionMode", "effort", "memory", "mcpServers"):
                    self.assertNotIn(key, fields)

    def test_the_reader_cannot_edit(self) -> None:
        disallowed = tool_set(front_matter("art-reader").get("disallowedTools", ""))
        self.assertLessEqual({"Edit", "Write"}, disallowed)


if __name__ == "__main__":
    unittest.main()
