#!/usr/bin/env python3

"""
Claude Scheduler - Main entry point.

Schedule Claude agents to run at specific times or periodically.
"""

import os
import sys
import signal
import pickle
from typing import List, Tuple, Dict, Any, Optional

from command_line import CommandLineProcessor
from scheduler import (
    TaskScheduler,
    add_task,
    remove_task,
    get_schedule,
    set_schedule,
    stop_scheduler,
)
from claude_task import ClaudeTask
from mcp_registry import get_registry, MCPRegistry

SCHEDULE_STATE_FILE = "claude_schedule.pickle"


def parse_task_args(tokens: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse --mcps, --cwd, and --allow flags from command tokens.

    Args:
        tokens: List of command tokens (after the command name and time/period)

    Returns:
        Tuple of (options_dict, remaining_tokens)
        options_dict may contain:
          - 'mcps': list of MCP names to load
          - 'cwd': working directory path
          - 'allow': True (all loaded MCPs) or list of patterns
    """
    options = {}
    remaining = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        if token == "--mcps" and i + 1 < len(tokens):
            # Parse comma-separated MCP names
            options["mcps"] = [name.strip() for name in tokens[i + 1].split(",")]
            i += 2
        elif token == "--cwd" and i + 1 < len(tokens):
            options["cwd"] = tokens[i + 1]
            i += 2
        elif token == "--allow":
            # Check if next token is a pattern list or start of prompt
            # Valid patterns:
            #   - Contain ":" (MCP pattern: lookout: or lookout:send_mail)
            #   - Are built-in tool names: Bash, Edit, Write, Read
            BUILTIN_TOOLS = {"Bash", "Edit", "Write", "Read"}

            if i + 1 < len(tokens):
                next_token = tokens[i + 1]

                # Split potential patterns to check each one
                potential_patterns = [p.strip() for p in next_token.split(",")]

                # Pattern is valid if it contains ":" OR is a built-in tool name
                looks_like_pattern = (
                    not next_token.startswith("--") and
                    all(":" in p or p in BUILTIN_TOOLS for p in potential_patterns)
                )

                if looks_like_pattern and potential_patterns:
                    options["allow"] = potential_patterns
                    i += 2
                else:
                    # No valid pattern = allow all loaded MCPs
                    options["allow"] = True
                    i += 1
            else:
                # At end of tokens = allow all loaded MCPs
                options["allow"] = True
                i += 1
        else:
            remaining.append(token)
            i += 1

    return options, remaining


class ClaudeSchedulerCommandProcessor(CommandLineProcessor):
    """
    Command processor for the Claude Scheduler application.
    """

    def __init__(self, scheduler_thread: TaskScheduler, registry: MCPRegistry):
        super().__init__()

        self.scheduler_thread = scheduler_thread
        self.registry = registry

        # Register commands
        self.add_command("schedule", self.cmd_schedule)
        self.add_command("periodic", self.cmd_periodic)
        self.add_command("list", self.cmd_list)
        self.add_command("unschedule", self.cmd_unschedule)
        self.add_command("save", self.cmd_save)
        self.add_command("reload", self.cmd_reload)
        self.add_command("mcps", self.cmd_mcps)
        self.add_command("exit", self.cmd_exit)

    def _resolve_mcps(self, mcp_names: Optional[List[str]], cwd: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """
        Resolve MCP server configs from names and/or cwd.

        Args:
            mcp_names: List of MCP names to look up in registry
            cwd: If provided, also include MCPs from that project

        Returns:
            Dict of MCP server configs
        """
        result = {}

        # Get MCPs by name from registry
        if mcp_names:
            found, not_found = self.registry.get_multiple(mcp_names)
            result.update(found)

            if not_found:
                self.print_error(f"Unknown MCPs: {', '.join(not_found)}")
                self.print_msg("Use 'mcps' command to see available MCPs")

        # Get MCPs from project cwd
        if cwd:
            project_mcps = self.registry.get_project_mcps(cwd)
            # Project MCPs don't override explicitly named ones
            for name, config in project_mcps.items():
                if name not in result:
                    result[name] = config

        return result

    def _resolve_allowed_tools(
        self,
        allow: Optional[Any],
        mcp_servers: Dict[str, Dict[str, Any]]
    ) -> Optional[List[str]]:
        """
        Convert --allow option to allowed_tools list.

        Args:
            allow: True (all loaded MCPs), list of patterns, or None
            mcp_servers: Dict of loaded MCP server configs

        Returns:
            List of allowed tool patterns, or None if no permissions granted
        """
        if allow is None:
            return None

        if allow is True:
            # --allow with no argument = all loaded MCPs
            if mcp_servers:
                return list(mcp_servers.keys())
            else:
                self.print_error("--allow specified but no MCPs loaded")
                return None

        # --allow with explicit patterns
        if isinstance(allow, list):
            return allow

        return None

    def cmd_schedule(self, processor):
        """
        Schedule a Claude task at a specific time.

        Usage:

            schedule <HH:MMAM/PM> [options] <prompt...>

        Options:

            --mcps name1,name2     Load specified MCP servers
            --cwd /path            Set working directory
            --allow            Pre-authorize all loaded MCPs (unattended)
            --allow patterns   Pre-authorize specific tools

        Patterns:

            lookout:               All tools from lookout MCP
            lookout:send_mail      Specific MCP tool
            lookout:mail_*         MCP tool wildcard
            Bash,Edit,Write,Read   Built-in tools

        Examples:

            schedule 2:30PM --mcps lookout --allow Send dad joke to Alice
            schedule 9:00AM --mcps lookout --allow lookout:read_inbox Check mail
            schedule 10:00AM --allow Edit,Write Update the config file
        """
        tokens = processor.get_tokenized_command_buffer()

        if len(tokens) < 3:
            self.print_error("Usage: schedule <HH:MMAM/PM> [--mcps ...] [--allow ...] <prompt>")
            self.print_error("Example: schedule 2:30PM --mcps lookout --allow Send email")
            return

        try:
            schedule_time = tokens[1]

            # Parse options and prompt from remaining tokens
            options, prompt_tokens = parse_task_args(tokens[2:])

            if not prompt_tokens:
                self.print_error("No prompt provided")
                return

            prompt = " ".join(prompt_tokens)

            # Resolve MCPs
            mcp_servers = self._resolve_mcps(
                options.get("mcps"),
                options.get("cwd")
            )

            # Build allowed_tools from --allow
            allowed_tools = self._resolve_allowed_tools(
                options.get("allow"),
                mcp_servers
            )

            task = ClaudeTask(
                prompt=prompt,
                schedule_time=schedule_time,
                mcp_servers=mcp_servers if mcp_servers else None,
                cwd=options.get("cwd"),
                allowed_tools=allowed_tools
            )
            add_task(task)

            msg = f'Scheduled: "{prompt}" at {schedule_time}'
            if mcp_servers:
                msg += f'\n  MCPs: {", ".join(mcp_servers.keys())}'
            if allowed_tools:
                msg += f'\n  Pre-authorized: {", ".join(allowed_tools)}'
            if options.get("cwd"):
                msg += f'\n  Working dir: {options["cwd"]}'
            self.print_msg(msg)

        except Exception as e:
            self.print_error(f"Failed to schedule task: {e}")

    def cmd_periodic(self, processor):
        """
        Schedule a recurring Claude task.

        Usage:

            periodic <seconds> [options] <prompt...>

        Options:

            --mcps name1,name2     Load specified MCP servers
            --cwd /path            Set working directory
            --allow            Pre-authorize all loaded MCPs (unattended)
            --allow patterns   Pre-authorize specific tools

        Patterns:

            lookout:               All tools from lookout MCP
            lookout:send_mail      Specific MCP tool
            Bash,Edit,Write,Read   Built-in tools

        Examples:

            periodic 3600 --mcps aidderall --allow Summarize my tasks
            periodic 300 --mcps lookout --allow lookout:read_inbox Check for mail
        """
        tokens = processor.get_tokenized_command_buffer()

        if len(tokens) < 3:
            self.print_error("Usage: periodic <seconds> [--mcps ...] [--allow ...] <prompt>")
            self.print_error("Example: periodic 3600 --mcps lookout --allow Check my mail")
            return

        try:
            period = int(tokens[1])
            if period < 2:
                self.print_error("Period must be at least 2 seconds")
                return

            # Parse options and prompt from remaining tokens
            options, prompt_tokens = parse_task_args(tokens[2:])

            if not prompt_tokens:
                self.print_error("No prompt provided")
                return

            prompt = " ".join(prompt_tokens)

            # Resolve MCPs
            mcp_servers = self._resolve_mcps(
                options.get("mcps"),
                options.get("cwd")
            )

            # Build allowed_tools from --allow
            allowed_tools = self._resolve_allowed_tools(
                options.get("allow"),
                mcp_servers
            )

            task = ClaudeTask(
                prompt=prompt,
                periodic=True,
                period=period,
                mcp_servers=mcp_servers if mcp_servers else None,
                cwd=options.get("cwd"),
                allowed_tools=allowed_tools
            )
            add_task(task)

            msg = f'Scheduled: "{prompt}" every {period} seconds'
            if mcp_servers:
                msg += f'\n  MCPs: {", ".join(mcp_servers.keys())}'
            if allowed_tools:
                msg += f'\n  Pre-authorized: {", ".join(allowed_tools)}'
            if options.get("cwd"):
                msg += f'\n  Working dir: {options["cwd"]}'
            self.print_msg(msg)

        except ValueError:
            self.print_error("Period must be an integer")
        except Exception as e:
            self.print_error(f"Failed to schedule task: {e}")

    def cmd_list(self, processor):
        """
        List all scheduled tasks.
        Usage: list
        """
        tasks = get_schedule()

        if not tasks:
            self.print_msg("No tasks scheduled.")
            return

        self.print_msg("Scheduled tasks:")
        for i, task in enumerate(tasks):
            print(f"  {i}> {task}")

    def cmd_unschedule(self, processor):
        """
        Remove a scheduled task by index.
        Usage: unschedule <index>
        """
        tokens = processor.get_tokenized_command_buffer()

        if len(tokens) < 2:
            self.print_error("Usage: unschedule <index>")
            return

        try:
            index = int(tokens[1])
            if remove_task(index):
                self.print_msg(f"Removed task {index}")
            else:
                self.print_error(f"Invalid task index: {index}")

        except ValueError:
            self.print_error("Index must be an integer")
        except Exception as e:
            self.print_error(f"Failed to remove task: {e}")

    def cmd_save(self, processor):
        """
        Save the current schedule to disk.

        Usage:

            save
        """
        if save_schedule():
            self.print_msg("Schedule saved.")
        else:
            self.print_error("Failed to save schedule.")

    def cmd_reload(self, processor):
        """
        Reload the schedule from disk, discarding current in-memory schedule.

        Usage:

            reload
        """
        if load_schedule():
            self.print_msg("Schedule reloaded from disk.")
        else:
            self.print_msg("No saved schedule found or failed to load.")

    def cmd_mcps(self, processor):
        """
        List available MCP servers from Claude config.

        Usage:

            mcps [--verbose]

        Options:

            --verbose, -v    Show full config details and source paths
        """
        tokens = processor.get_tokenized_command_buffer()
        verbose = "--verbose" in tokens or "-v" in tokens

        servers = self.registry.list_servers(verbose=verbose)

        if not servers:
            self.print_msg("No MCP servers found in ~/.claude.json")
            self.print_msg("Configure MCPs in Claude Code first, then restart the scheduler.")
            return

        self.print_msg(f"Available MCP servers ({len(servers)}):")
        print(f"  (from ~/.claude.json)")
        print()
        for line in servers:
            print(line)
            print()

        if not verbose:
            print("  Use 'mcps --verbose' for details")

    def cmd_exit(self, processor):
        """
        Exit the scheduler, saving state.
        Usage: exit
        """
        self.print_msg("Stopping task scheduler...")
        stop_scheduler()
        self.scheduler_thread.join(timeout=5)

        self.print_msg("Saving schedule state...")
        save_schedule()

        self.print_msg("Goodbye!")
        sys.exit(0)


def load_schedule():
    """Load the schedule from the state file if it exists."""
    if os.path.exists(SCHEDULE_STATE_FILE):
        try:
            with open(SCHEDULE_STATE_FILE, "rb") as f:
                tasks = pickle.load(f)
                set_schedule(tasks)
                print(f"Loaded {len(tasks)} task(s) from {SCHEDULE_STATE_FILE}")
                return True
        except Exception as e:
            print(f"Warning: Failed to load schedule state: {e}")
    return False


def save_schedule():
    """Save the current schedule to the state file."""
    try:
        tasks = get_schedule()
        with open(SCHEDULE_STATE_FILE, "wb") as f:
            pickle.dump(tasks, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"\nSaved {len(tasks)} task(s) to {SCHEDULE_STATE_FILE}")
        return True
    except Exception as e:
        print(f"\nFailed to save state: {e}")
        return False


def graceful_shutdown(signum, frame):
    """Handle Ctrl+C by saving state and exiting cleanly."""
    print("\n\nInterrupted. Shutting down gracefully...")
    stop_scheduler()
    save_schedule()
    print("Goodbye!")
    sys.exit(0)


def main():
    """Main entry point."""
    # Register Ctrl+C handler for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)

    print("Claude Scheduler v1.0")
    print("=" * 40)

    # Load MCP registry from Claude config
    registry = get_registry()

    # Load saved schedule
    load_schedule()

    # Start the scheduler thread
    scheduler = TaskScheduler()
    print("Starting task scheduler...")
    scheduler.start()
    print("Task scheduler running.")
    print()
    print("Commands: schedule, periodic, list, unschedule, save, reload, mcps, help, exit")
    print("Options:  --mcps name1,name2  --cwd /path  --allow [patterns]")
    print()

    # Start the command processor
    cmd_processor = ClaudeSchedulerCommandProcessor(scheduler, registry)
    cmd_processor.start_processing()


if __name__ == "__main__":
    main()
