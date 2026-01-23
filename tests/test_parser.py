#!/usr/bin/env python3

"""
Tests for command argument parsing.

Run with: python -m pytest tests/ -v
Or:       python tests/test_parser.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from main import parse_task_args


class TestParseTaskArgs(unittest.TestCase):
    """Test the parse_task_args function."""

    def test_basic_prompt_only(self):
        """Prompt with no options."""
        options, remaining = parse_task_args(["Send", "an", "email"])
        self.assertEqual(options, {})
        self.assertEqual(remaining, ["Send", "an", "email"])

    def test_mcps_single(self):
        """Single MCP server."""
        options, remaining = parse_task_args(["--mcps", "lookout", "Send", "email"])
        self.assertEqual(options["mcps"], ["lookout"])
        self.assertEqual(remaining, ["Send", "email"])

    def test_mcps_multiple(self):
        """Multiple MCP servers comma-separated."""
        options, remaining = parse_task_args(["--mcps", "lookout,aidderall", "Send", "email"])
        self.assertEqual(options["mcps"], ["lookout", "aidderall"])
        self.assertEqual(remaining, ["Send", "email"])

    def test_cwd(self):
        """Working directory option."""
        options, remaining = parse_task_args(["--cwd", "/some/path", "Do", "stuff"])
        self.assertEqual(options["cwd"], "/some/path")
        self.assertEqual(remaining, ["Do", "stuff"])

    def test_allow_no_arg_uppercase_prompt(self):
        """--allow with no argument, prompt starts with uppercase."""
        options, remaining = parse_task_args(["--mcps", "lookout", "--allow", "Send", "email"])
        self.assertEqual(options["allow"], True)
        self.assertEqual(remaining, ["Send", "email"])

    def test_allow_no_arg_lowercase_prompt(self):
        """--allow with no argument, prompt starts with lowercase (not an MCP name)."""
        # "send" is not in --mcps, so it's treated as prompt, not pattern
        options, remaining = parse_task_args(["--mcps", "lookout", "--allow", "send", "an", "email"])
        self.assertEqual(options["allow"], True)
        self.assertEqual(remaining, ["send", "an", "email"])

    def test_allow_all_from_one_mcp(self):
        """--allow with trailing colon = all tools from that MCP."""
        options, remaining = parse_task_args(["--mcps", "lookout", "--allow", "lookout:", "Send", "email"])
        self.assertEqual(options["allow"], ["lookout:"])
        self.assertEqual(remaining, ["Send", "email"])

    def test_allow_specific_tool(self):
        """--allow with specific tool pattern (mcp:tool)."""
        options, remaining = parse_task_args(["--mcps", "lookout", "--allow", "lookout:send_mail", "Send", "email"])
        self.assertEqual(options["allow"], ["lookout:send_mail"])
        self.assertEqual(remaining, ["Send", "email"])

    def test_allow_multiple_patterns(self):
        """--allow with multiple comma-separated patterns."""
        options, remaining = parse_task_args(
            ["--mcps", "lookout", "--allow", "lookout:send_mail,lookout:read_inbox", "Check", "mail"]
        )
        self.assertEqual(options["allow"], ["lookout:send_mail", "lookout:read_inbox"])
        self.assertEqual(remaining, ["Check", "mail"])

    def test_allow_wildcard(self):
        """--allow with wildcard pattern."""
        options, remaining = parse_task_args(["--mcps", "lookout", "--allow", "lookout:mail_*", "Handle", "mail"])
        self.assertEqual(options["allow"], ["lookout:mail_*"])
        self.assertEqual(remaining, ["Handle", "mail"])

    def test_all_options_combined(self):
        """All options together."""
        options, remaining = parse_task_args(
            ["--mcps", "lookout,aidderall", "--cwd", "/project", "--allow", "lookout:", "Do", "work"]
        )
        self.assertEqual(options["mcps"], ["lookout", "aidderall"])
        self.assertEqual(options["cwd"], "/project")
        self.assertEqual(options["allow"], ["lookout:"])
        self.assertEqual(remaining, ["Do", "work"])

    def test_allow_at_end(self):
        """--allow at end of command with no argument."""
        options, remaining = parse_task_args(["--mcps", "lookout", "Send", "email", "--allow"])
        self.assertEqual(options["allow"], True)
        self.assertEqual(remaining, ["Send", "email"])

    def test_allow_before_other_flag(self):
        """--allow followed by another flag (no arg)."""
        options, remaining = parse_task_args(["--allow", "--cwd", "/path", "Do", "stuff"])
        self.assertEqual(options["allow"], True)
        self.assertEqual(options["cwd"], "/path")
        self.assertEqual(remaining, ["Do", "stuff"])

    def test_lowercase_prompt_not_in_mcps(self):
        """Lowercase word after --allow NOT in --mcps is treated as prompt."""
        # "check" is not in --mcps list, so it's part of the prompt
        options, remaining = parse_task_args(["--mcps", "lookout", "--allow", "check", "my", "email"])
        self.assertEqual(options["allow"], True)
        self.assertEqual(remaining, ["check", "my", "email"])

    def test_pattern_requires_colon(self):
        """Patterns must contain ':' - MCP name alone is not enough."""
        # "aidderall" without colon is treated as prompt start
        options, remaining = parse_task_args(["--mcps", "lookout,aidderall", "--allow", "aidderall", "Do", "stuff"])
        self.assertEqual(options["allow"], True)  # No valid pattern, so True
        self.assertEqual(remaining, ["aidderall", "Do", "stuff"])

    def test_pattern_with_colon_recognized(self):
        """Pattern with colon is properly recognized."""
        options, remaining = parse_task_args(["--mcps", "lookout,aidderall", "--allow", "aidderall:", "Do", "stuff"])
        self.assertEqual(options["allow"], ["aidderall:"])
        self.assertEqual(remaining, ["Do", "stuff"])

    def test_builtin_tool_recognized(self):
        """Built-in tool names (Bash, Edit, etc.) are recognized as patterns."""
        options, remaining = parse_task_args(["--allow", "Bash", "Run", "a", "command"])
        self.assertEqual(options["allow"], ["Bash"])
        self.assertEqual(remaining, ["Run", "a", "command"])

    def test_builtin_tools_multiple(self):
        """Multiple built-in tools comma-separated."""
        options, remaining = parse_task_args(["--allow", "Edit,Write,Read", "Update", "files"])
        self.assertEqual(options["allow"], ["Edit", "Write", "Read"])
        self.assertEqual(remaining, ["Update", "files"])

    def test_mixed_mcp_and_builtin(self):
        """Mix of MCP patterns and built-in tools."""
        options, remaining = parse_task_args(["--mcps", "lookout", "--allow", "lookout:,Bash", "Do", "stuff"])
        self.assertEqual(options["allow"], ["lookout:", "Bash"])
        self.assertEqual(remaining, ["Do", "stuff"])


class TestClaudeTaskAllowedTools(unittest.TestCase):
    """Test the ClaudeTask.is_tool_allowed method."""

    def setUp(self):
        from claude_task import ClaudeTask
        self.ClaudeTask = ClaudeTask

    def test_no_allowed_tools(self):
        """No tools allowed by default."""
        task = self.ClaudeTask("test prompt")
        self.assertFalse(task.is_tool_allowed("lookout", "send_mail"))

    def test_wildcard_all(self):
        """Wildcard '*' allows all tools."""
        task = self.ClaudeTask("test", allowed_tools=["*"])
        self.assertTrue(task.is_tool_allowed("lookout", "send_mail"))
        self.assertTrue(task.is_tool_allowed("aidderall", "anything"))

    def test_wildcard_star(self):
        """'*' allows all MCP tools."""
        task = self.ClaudeTask("test", allowed_tools=["*"])
        self.assertTrue(task.is_tool_allowed("lookout", "send_mail"))
        self.assertTrue(task.is_tool_allowed("aidderall", "task_list"))

    def test_trailing_colon_allows_all_tools(self):
        """Trailing colon allows all tools from that MCP."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:"])
        self.assertTrue(task.is_tool_allowed("lookout", "send_mail"))
        self.assertTrue(task.is_tool_allowed("lookout", "read_inbox"))
        self.assertFalse(task.is_tool_allowed("aidderall", "task_list"))

    def test_explicit_wildcard_allows_all_tools(self):
        """Explicit wildcard (mcp:*) allows all tools from that MCP."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:*"])
        self.assertTrue(task.is_tool_allowed("lookout", "send_mail"))
        self.assertTrue(task.is_tool_allowed("lookout", "read_inbox"))
        self.assertFalse(task.is_tool_allowed("aidderall", "task_list"))

    def test_specific_tool(self):
        """Specific tool pattern allows only that tool."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:send_mail"])
        self.assertTrue(task.is_tool_allowed("lookout", "send_mail"))
        self.assertFalse(task.is_tool_allowed("lookout", "read_inbox"))
        self.assertFalse(task.is_tool_allowed("aidderall", "send_mail"))

    def test_wildcard_pattern(self):
        """Wildcard in tool name matches multiple tools."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:mail_*"])
        self.assertTrue(task.is_tool_allowed("lookout", "mail_send"))
        self.assertTrue(task.is_tool_allowed("lookout", "mail_read"))
        self.assertFalse(task.is_tool_allowed("lookout", "calendar_view"))

    def test_multiple_patterns(self):
        """Multiple patterns combined."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:send_mail", "aidderall:"])
        self.assertTrue(task.is_tool_allowed("lookout", "send_mail"))
        self.assertFalse(task.is_tool_allowed("lookout", "read_inbox"))
        self.assertTrue(task.is_tool_allowed("aidderall", "task_list"))
        self.assertTrue(task.is_tool_allowed("aidderall", "anything"))

    def test_no_allowed_tools_returns_none(self):
        """No allowed_tools = no SDK restrictions."""
        task = self.ClaudeTask("test")
        self.assertIsNone(task.get_sdk_allowed_tools())

    def test_sdk_conversion_trailing_colon(self):
        """Trailing colon converts to mcp__name__* format."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:"])
        sdk_tools = task.get_sdk_allowed_tools()
        self.assertEqual(sdk_tools, ["mcp__lookout__*"])

    def test_sdk_conversion_specific_tool(self):
        """Specific tool converts to mcp__name__tool format."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:send_mail"])
        sdk_tools = task.get_sdk_allowed_tools()
        self.assertEqual(sdk_tools, ["mcp__lookout__send_mail"])

    def test_sdk_conversion_wildcard(self):
        """Wildcard pattern preserved in SDK format."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:mail_*"])
        sdk_tools = task.get_sdk_allowed_tools()
        self.assertEqual(sdk_tools, ["mcp__lookout__mail_*"])

    def test_sdk_conversion_builtin(self):
        """Built-in tools pass through unchanged."""
        task = self.ClaudeTask("test", allowed_tools=["Bash", "Edit"])
        sdk_tools = task.get_sdk_allowed_tools()
        self.assertEqual(sdk_tools, ["Bash", "Edit"])

    def test_sdk_conversion_mixed(self):
        """Mix of MCP and built-in tools."""
        task = self.ClaudeTask("test", allowed_tools=["lookout:", "Bash"])
        sdk_tools = task.get_sdk_allowed_tools()
        self.assertEqual(sdk_tools, ["mcp__lookout__*", "Bash"])

    def test_sdk_conversion_star_returns_none(self):
        """'*' pattern returns None (no restrictions)."""
        task = self.ClaudeTask("test", allowed_tools=["*"])
        sdk_tools = task.get_sdk_allowed_tools()
        self.assertIsNone(sdk_tools)

    def test_sdk_conversion_empty_returns_none(self):
        """No allowed_tools returns None."""
        task = self.ClaudeTask("test")
        sdk_tools = task.get_sdk_allowed_tools()
        self.assertIsNone(sdk_tools)


if __name__ == "__main__":
    unittest.main(verbosity=2)
