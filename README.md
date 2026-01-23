# Claude Scheduler

<p align="center">
  <img src="images/claude_scheduler.jpg" alt="Claude Scheduler" width="300">
</p>

Schedule Claude Code agents to run at specific times or periodically, with optional MCP server access and granular permission control.

## Overview

Claude Scheduler is a command-line tool that lets you schedule Claude Code SDK tasks to run unattended. You can:

- Schedule one-time tasks at specific times (e.g., "2:30PM")
- Schedule recurring tasks at intervals (e.g., every 3600 seconds)
- Load MCP servers for tool access (email, calendars, task managers, etc.)
- Pre-authorize specific tools for unattended execution

## Installation

```bash
# Clone/download the project
cd claude_scheduler

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Run the scheduler
python3 main.py

# Schedule a task
> schedule 2:30PM --mcps lookout --allow Send Alice a dad joke

# List scheduled tasks
> list

# Exit (saves state)
> exit
```

## Commands

| Command | Description |
|---------|-------------|
| `schedule` | Schedule a task at a specific time |
| `periodic` | Schedule a recurring task |
| `list` | Show all scheduled tasks |
| `unschedule` | Remove a task by index |
| `save-prompt` | Save a task's prompt to a file |
| `mcps` | List available MCP servers |
| `save` | Save schedule to disk |
| `reload` | Reload schedule from disk |
| `help` | Show help (use `help <command>` for details) |
| `exit` | Save state and exit |

## Command Syntax

### schedule

Schedule a Claude task at a specific time.

```
schedule <HH:MMAM/PM> [options] <prompt...>
```

**Options:**
- `--mcps name1,name2` - Load specified MCP servers
- `--cwd /path` - Set working directory (inherits project context)
- `--prompt-file /path` - Read prompt from file (for long prompts)
- `--allow` - Pre-authorize all loaded MCPs for unattended execution
- `--allow patterns` - Pre-authorize specific tools only

**Examples:**

```bash
# Basic task (will prompt for permissions if needed)
> schedule 9:00AM Check the weather

# With MCP, authorize all its tools
> schedule 2:30PM --mcps lookout --allow Send Alice a dad joke

# Authorize only specific tool
> schedule 9:00AM --mcps lookout --allow lookout:read_inbox Check my morning emails

# Multiple specific tools
> schedule 10:00AM --mcps lookout --allow lookout:read_inbox,lookout:send_mail Read and reply to urgent emails

# Wildcard tool patterns
> schedule 3:00PM --mcps lookout --allow lookout:mail_* Handle all mail tasks

# Multiple MCPs, authorize only one
> schedule 12:00PM --mcps lookout,aidderall --allow aidderall Summarize my tasks

# Long prompt from file (bypasses shell line length limits)
> schedule 9:00AM --mcps lookout --allow --prompt-file ~/prompts/morning_briefing.txt
```

### periodic

Schedule a recurring Claude task.

```
periodic <seconds> [options] <prompt...>
```

**Examples:**

```bash
# Every hour, check tasks
> periodic 3600 --mcps aidderall --allow Summarize my open tasks

# Every 5 minutes, check for urgent emails
> periodic 300 --mcps lookout --allow lookout:read_inbox Check for urgent emails

# Long prompt from file
> periodic 900 --mcps lookout --allow --prompt-file ~/prompts/calendar_check.txt
```

### list

Show all scheduled tasks with their index, schedule, and options.

```
> list

Scheduled tasks:
  0> "Send Alice a dad joke" at 02:30PM (mcps=[lookout], allow=[lookout])
  1> "Check for urgent emails" every 300s (mcps=[lookout], allow=[lookout:read_inbox])
```

### unschedule

Remove a task by its index.

```
> unschedule 0
Removed task 0
```

### save-prompt

Save a task's prompt to a file. Useful for editing or recreating schedule entries.

```bash
# Save task 0's prompt to a file
> save-prompt 0 ~/prompts/morning_briefing.txt
Saved prompt to /Users/you/prompts/morning_briefing.txt (847 chars)

# Edit the file, then recreate the task
> unschedule 0
> schedule 9:00AM --mcps lookout --allow --prompt-file ~/prompts/morning_briefing.txt
```

### mcps

List available MCP servers loaded from `~/.claude.json`.

```
> mcps
Available MCP servers (3):
  (from ~/.claude.json)

  lookout (sse)

  aidderall (stdio)

  dataremote (stdio)

  Use 'mcps --verbose' for details

> mcps --verbose
# Shows full config including source project paths
```

### help

Get help on commands.

```
> help
Available commands:
==================================================
  exit         - Exit the scheduler, saving state.
  help         - List all available commands with usage info.
  list         - List all scheduled tasks.
  ...
==================================================

Type 'help <command>' for detailed usage

> help schedule
schedule:
  Schedule a Claude task at a specific time.
  Usage: schedule <HH:MMAM/PM> [options] <prompt...>
  ...
```

## Permission System

By default, Claude will prompt for permission when using tools. For scheduled/unattended tasks, you need to pre-authorize tools using `--allow`.

### Permission Patterns

**MCP Tools** (require colon):

| Pattern | Allows |
|---------|--------|
| `--allow` (no arg) | All tools from all loaded MCPs |
| `--allow lookout:` | All tools from `lookout` (trailing colon = all) |
| `--allow lookout:send_mail` | Only `send_mail` from `lookout` |
| `--allow lookout:mail_*` | Wildcard match (e.g., `mail_send`, `mail_read`) |
| `--allow lookout:,aidderall:` | Multiple MCPs |

**Built-in Tools**:

| Pattern | Allows |
|---------|--------|
| `--allow Bash` | Shell command execution |
| `--allow Edit` | File editing |
| `--allow Write` | File creation |
| `--allow Read` | File reading |
| `--allow Edit,Write` | Multiple built-in tools |

**Combined**:

```bash
# MCP + built-in tools
> schedule 9:00AM --mcps lookout --allow lookout:read_inbox,Bash Check mail and run cleanup
```

### Security Considerations

- Only pre-authorize the minimum tools needed for each task
- Use specific tool patterns (`lookout:send_mail`) rather than blanket (`lookout:`)
- Built-in tools like `Bash` are powerful - use with caution
- Tasks without `--allow` will prompt for permission (fails in unattended mode)

## Persistence

Task schedules are saved to `claude_schedule.pickle` on exit and restored on startup.

```bash
> exit
Saving schedule state...
Saved 2 task(s) to claude_schedule.pickle
Goodbye!

# Later...
$ python3 main.py
Claude Scheduler v1.0
========================================
Loaded 2 task(s) from claude_schedule.pickle
...
```

## MCP Server Configuration

MCP servers are loaded from your Claude Code config at `~/.claude.json`. Configure them in Claude Code first, then they'll be available in the scheduler.

The scheduler scrapes MCP configs from all projects in your Claude config - use the `mcps` command to see what's available.

## Running Tests

```bash
# Run all tests
python3 tests/test_parser.py

# Or with pytest (if installed)
python -m pytest tests/ -v
```

## Architecture

```
claude_scheduler/
├── main.py           # Entry point, CLI commands
├── command_line.py   # REPL command processor framework
├── scheduler.py      # Background task scheduler thread
├── claude_task.py    # ClaudeTask class (SDK integration)
├── mcp_registry.py   # MCP config loader from ~/.claude.json
└── tests/
    └── test_parser.py
```

## Security Notes

**Pickle files**: The schedule is persisted using Python's `pickle` module (`claude_schedule.pickle`). Pickle files can execute arbitrary code when loaded. **Never load pickle files from untrusted sources.** Only use pickle files you created yourself.

If you need to share schedules between machines, use `save-prompt` to export prompts as plain text files, then recreate tasks on the target machine.

## License

MIT
