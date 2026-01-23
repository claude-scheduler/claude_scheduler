#!/usr/bin/env python3

"""
Command Line Processor - Merged CLI framework for Claude Scheduler.

Extracted and modernized from lightControl's CommandLineProcessor and
CommandProcessorBase modules.
"""

import sys
import threading
import traceback

COMMAND_TOKEN = 0

_command_processor_singleton = None


class CommandLineProcessor:
    """
    Unified command line processor combining tokenization, dispatch,
    REPL loop, and thread-safe execution.
    """

    @classmethod
    def get_singleton(cls):
        """Return the singleton instance."""
        global _command_processor_singleton
        return _command_processor_singleton

    def __init__(self):
        global _command_processor_singleton

        self.command_buffer = ""
        self.tokenized_command_buffer = []
        self.command_vector = {}
        self.run_lock = threading.Lock()

        # Built-in commands
        self.commands = {
            "exit": self.exit_processor,
            "help": self.list_commands,
        }

        _command_processor_singleton = self

    def get_commands(self):
        """Return the command dictionary."""
        return self.commands

    def add_command(self, cmd, action):
        """Register a command handler."""
        self.commands[cmd] = action
        self.command_vector[cmd] = action

    def register_commands(self):
        """Register all commands with the command vector."""
        for cmd in self.commands:
            self.command_vector[cmd] = self.commands[cmd]

    def get_command_handler(self, command):
        """Get the handler for a command."""
        return self.command_vector.get(command, None)

    def tokenize_command_buffer(self):
        """Split the command buffer into tokens."""
        self.tokenized_command_buffer = self.command_buffer.split()

    def get_tokenized_command_buffer(self):
        """Return the tokenized command buffer."""
        return self.tokenized_command_buffer

    def get_token(self, token_index):
        """Get a specific token from the buffer."""
        return self.tokenized_command_buffer[token_index]

    def command_buffer_length(self):
        """Return the length of the command buffer."""
        return len(self.command_buffer)

    def run_command(self, command):
        """Execute a command string in a thread-safe manner."""
        self.run_lock.acquire()

        try:
            self.command_buffer = command

            if self.command_buffer_length():
                self.tokenize_command_buffer()
                self.process_command()
            else:
                print(f"\nunrecognized command: {command}\n")

        except Exception as e:
            print(f"Warning: unhandled exception while running command <{command}: {e}>")
            traceback.print_exc()

        self.run_lock.release()

    def start_processing(self):
        """Main REPL loop."""
        self.register_commands()

        while True:
            self.read_line()

            if self.command_buffer_length():
                self.tokenize_command_buffer()

                if not len(self.get_tokenized_command_buffer()):
                    print("huh?")
                    continue

                self.process_command()
            else:
                print("")

    def process_command(self):
        """Dispatch the current command to its handler."""
        command = self.get_token(COMMAND_TOKEN)
        command_handler = self.get_command_handler(command)

        if command_handler:
            command_handler(self)
            print("")
        else:
            print(f"\nunrecognized command: {command}\n")

    def read_line(self):
        """Read a line from stdin."""
        try:
            self.command_buffer = input("> ")
        except EOFError:
            self.command_buffer = "exit"

    # Built-in command handlers

    def exit_processor(self, processor):
        """Exit handler - override in subclass."""
        print("exiting command processor")
        sys.exit(0)

    def list_commands(self, processor):
        """List all available commands with usage info."""
        tokens = processor.get_tokenized_command_buffer()

        # help <command> - show detailed help for one command
        if len(tokens) > 1:
            cmd = tokens[1]
            handler = self.get_command_handler(cmd)
            if handler and handler.__doc__:
                print(f"\n{cmd}:")
                # Preserve relative indentation from docstring
                lines = handler.__doc__.split("\n")
                # Find minimum indentation (excluding empty lines)
                non_empty = [l for l in lines if l.strip()]
                if non_empty:
                    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
                else:
                    min_indent = 0
                for line in lines:
                    # Remove common indent, add our prefix
                    if line.strip():
                        print(f"  {line[min_indent:]}")
                    else:
                        print()
            elif handler:
                print(f"\n{cmd}: No detailed help available")
            else:
                print(f"\nUnknown command: {cmd}")
            return

        # help - list all commands with brief descriptions
        print("\nAvailable commands:\n" + ("=" * 50))
        for cmd in sorted(self.commands.keys()):
            handler = self.commands[cmd]
            # Extract first line of docstring as brief description
            if handler.__doc__:
                brief = handler.__doc__.strip().split("\n")[0]
                print(f"  {cmd:12} - {brief}")
            else:
                print(f"  {cmd}")
        print("=" * 50)
        print("\nType 'help <command>' for detailed usage")

    # Utility methods

    def print_error(self, msg):
        """Print an error message."""
        print(f"\nERROR: {msg}\n")

    def print_msg(self, msg):
        """Print a message."""
        print(f"\n{msg}")
