#!/usr/bin/env python3

"""
Claude Task - Task type for spawning Claude agents via the Agent SDK.
"""

import asyncio
import fnmatch
import threading
from typing import Dict, Any, Optional, List
from scheduler import TaskSchedulerTask

try:
    from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock, ResultMessage
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False
    print("Warning: claude-code-sdk not installed. ClaudeTask will not function.")


class ClaudeTask(TaskSchedulerTask):
    """
    A task that spawns a Claude agent at the scheduled time.
    """

    def __init__(
        self,
        prompt: str,
        schedule_time: str = "12:00PM",
        periodic: bool = False,
        period: int = 60,
        mcp_servers: Optional[Dict[str, Dict[str, Any]]] = None,
        cwd: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None
    ):
        """
        Initialize a Claude task.

        Args:
            prompt: The prompt to send to Claude
            schedule_time: Time in HH:MMAM/PM format (e.g., "2:30PM")
            periodic: If True, run every `period` seconds instead of at a fixed time
            period: Interval in seconds for periodic tasks
            mcp_servers: Dict of MCP server configs to pass to the agent
            cwd: Working directory for the agent (inherits that project's context)
            allowed_tools: List of pre-authorized tool patterns for unattended execution
                Patterns:
                  - "*" - all tools (no restrictions)
                  - "lookout:" - all tools from lookout MCP
                  - "lookout:send_mail" - specific MCP tool
                  - "lookout:mail_*" - MCP tool wildcard
                  - "Bash" - allow bash commands
                  - "Edit", "Write", "Read" - file operations
        """
        super().__init__(schedule_time=schedule_time)
        self.prompt = prompt
        self.set_periodic(periodic)
        self.set_period(period)

        # MCP and environment options
        self.mcp_servers = mcp_servers or {}
        self.cwd = cwd
        self.allowed_tools = allowed_tools or []

    def __repr__(self):
        prompt_preview = self.prompt[:40] + "..." if len(self.prompt) > 40 else self.prompt

        # Build suffix with options
        suffix_parts = []
        if self.mcp_servers:
            mcp_names = ", ".join(self.mcp_servers.keys())
            suffix_parts.append(f"mcps=[{mcp_names}]")
        if self.cwd:
            suffix_parts.append(f"cwd={self.cwd}")
        if self.allowed_tools:
            # Show "all" if wildcard, otherwise show patterns
            if self.allowed_tools == ["*"]:
                suffix_parts.append("allow=[all MCPs]")
            else:
                suffix_parts.append(f"allow=[{', '.join(self.allowed_tools)}]")

        suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""

        if self.is_periodic():
            import time
            return f'"{prompt_preview}" every {self.period}s{suffix}'
        else:
            import time
            return f'"{prompt_preview}" at {time.strftime("%I:%M%p", self.time)}{suffix}'

    def get_mcp_names(self) -> List[str]:
        """Return list of MCP server names configured for this task."""
        return list(self.mcp_servers.keys())

    def is_tool_allowed(self, mcp_name: str, tool_name: str) -> bool:
        """
        Check if a specific MCP tool is pre-authorized.

        Args:
            mcp_name: Name of the MCP server (e.g., "lookout")
            tool_name: Name of the tool (e.g., "send_mail")

        Returns:
            True if the tool matches any allowed pattern

        Pattern syntax:
            - "*" = all MCP tools
            - "lookout:" = all tools from lookout (trailing colon)
            - "lookout:*" = all tools from lookout (explicit wildcard)
            - "lookout:send_mail" = specific tool
            - "lookout:mail_*" = wildcard match
        """
        if not self.allowed_tools:
            return False

        full_tool = f"{mcp_name}:{tool_name}"

        for pattern in self.allowed_tools:
            # "*" = all MCP tools
            if pattern == "*":
                return True

            # "lookout:" = all tools from lookout (trailing colon means all)
            if pattern.endswith(":") and pattern[:-1] == mcp_name:
                return True

            # "lookout:*" or "lookout:send_mail" or "lookout:mail_*"
            if ":" in pattern:
                if fnmatch.fnmatch(full_tool, pattern):
                    return True

        return False

    def get_sdk_allowed_tools(self) -> Optional[List[str]]:
        """
        Convert allowed_tools patterns to SDK format.

        Our format:           SDK format:
        lookout:              mcp__lookout__*
        lookout:send_mail     mcp__lookout__send_mail
        lookout:mail_*        mcp__lookout__mail_*
        Bash                  Bash
        Edit                  Edit

        Returns:
            List of SDK-formatted tool patterns, or None if no restrictions
        """
        if not self.allowed_tools:
            return None

        sdk_tools = []
        for pattern in self.allowed_tools:
            if pattern == "*":
                # Allow everything - return None to not restrict
                return None

            if ":" in pattern:
                # MCP pattern: lookout:send_mail or lookout:
                parts = pattern.split(":", 1)
                mcp_name = parts[0]
                tool_part = parts[1] if parts[1] else "*"
                sdk_tools.append(f"mcp__{mcp_name}__{tool_part}")
            else:
                # Built-in tool name: Bash, Edit, Write, Read
                sdk_tools.append(pattern)

        return sdk_tools if sdk_tools else None

    def execute(self):
        """Spawn async execution in background thread (non-blocking)."""
        if not CLAUDE_SDK_AVAILABLE:
            print("[ClaudeTask] Error: claude-code-sdk not available")
            return

        # Run in separate thread so scheduler isn't blocked
        thread = threading.Thread(
            target=lambda: asyncio.run(self._run_agent()),
            daemon=True
        )
        thread.start()

    def _build_runtime_context(self) -> str:
        """Build runtime context to prepend to the prompt."""
        import time
        from datetime import datetime

        lines = ["[Context]"]

        # Current date/time - human readable with day of week
        now = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y, %I:%M %p")
        lines.append(f"Current time: {time_str}")

        # Working directory
        if self.cwd:
            lines.append(f"Working directory: {self.cwd}")

        # Available MCP servers
        if self.mcp_servers:
            mcp_names = ", ".join(self.mcp_servers.keys())
            lines.append(f"Available MCPs: {mcp_names}")

        lines.append("")
        lines.append("[Task]")

        return "\n".join(lines)

    async def _run_agent(self):
        """Run the Claude agent with the configured prompt."""
        prompt_preview = self.prompt[:50] + "..." if len(self.prompt) > 50 else self.prompt
        print(f"[ClaudeTask] Starting: {prompt_preview}")

        if self.mcp_servers:
            print(f"[ClaudeTask] MCPs: {', '.join(self.mcp_servers.keys())}")
        if self.cwd:
            print(f"[ClaudeTask] Working dir: {self.cwd}")
        if self.allowed_tools:
            if self.allowed_tools == ["*"]:
                print(f"[ClaudeTask] Pre-authorized: all MCP tools")
            else:
                print(f"[ClaudeTask] Pre-authorized: {', '.join(self.allowed_tools)}")

        try:
            # Build options
            options_kwargs = {}

            # Set allowed_tools for granular permissions
            sdk_allowed = self.get_sdk_allowed_tools()
            if sdk_allowed:
                options_kwargs["allowed_tools"] = sdk_allowed
                print(f"[ClaudeTask] SDK allowed_tools: {sdk_allowed}")

            if self.mcp_servers:
                options_kwargs["mcp_servers"] = self.mcp_servers

            if self.cwd:
                options_kwargs["cwd"] = self.cwd

            options = ClaudeCodeOptions(**options_kwargs)

            # Prepend runtime context to prompt
            full_prompt = self._build_runtime_context() + self.prompt

            async for message in query(prompt=full_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"[Claude] {block.text}")
                elif isinstance(message, ResultMessage):
                    print(f"[ClaudeTask] Completed. Cost: ${message.total_cost_usd:.4f}")

        except Exception as e:
            print(f"[ClaudeTask] Error: {e}")
