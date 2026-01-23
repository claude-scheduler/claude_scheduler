#!/usr/bin/env python3

"""
MCP Registry - Scrapes MCP server definitions from ~/.claude.json

Builds a registry of available MCPs by name for use in scheduled tasks.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

CLAUDE_CONFIG_PATH = Path.home() / ".claude.json"


class MCPRegistry:
    """
    Registry of MCP servers scraped from Claude Code's config.
    """

    def __init__(self):
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.server_sources: Dict[str, str] = {}  # Track where each MCP came from
        self._load_from_claude_config()

    def _load_from_claude_config(self):
        """Parse ~/.claude.json and extract all MCP server definitions."""
        if not CLAUDE_CONFIG_PATH.exists():
            print(f"Warning: {CLAUDE_CONFIG_PATH} not found")
            return

        try:
            with open(CLAUDE_CONFIG_PATH, "r") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse {CLAUDE_CONFIG_PATH}: {e}")
            return
        except Exception as e:
            print(f"Warning: Failed to read {CLAUDE_CONFIG_PATH}: {e}")
            return

        # Look for projects with mcpServers
        projects = config.get("projects", {})

        for project_path, project_config in projects.items():
            if not isinstance(project_config, dict):
                continue

            mcp_servers = project_config.get("mcpServers", {})
            if not isinstance(mcp_servers, dict):
                continue

            for server_name, server_config in mcp_servers.items():
                # First one wins - skip if already registered
                if server_name in self.servers:
                    continue

                if isinstance(server_config, dict) and server_config:
                    self.servers[server_name] = server_config
                    self.server_sources[server_name] = project_path

        print(f"Loaded {len(self.servers)} MCP server(s) from Claude config")

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Get an MCP server config by name."""
        return self.servers.get(name)

    def get_multiple(self, names: List[str]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
        """
        Get multiple MCP server configs by name.

        Returns:
            Tuple of (found_servers_dict, list_of_not_found_names)
        """
        found = {}
        not_found = []

        for name in names:
            if name in self.servers:
                found[name] = self.servers[name]
            else:
                not_found.append(name)

        return found, not_found

    def list_servers(self, verbose: bool = False) -> List[str]:
        """
        List all available MCP servers.

        Args:
            verbose: If True, include source project paths

        Returns:
            List of formatted strings describing each server
        """
        lines = []
        for name in sorted(self.servers.keys()):
            config = self.servers[name]
            server_type = config.get("type", "unknown")

            if server_type == "sse":
                detail = config.get("url", "")
            elif server_type == "stdio":
                detail = config.get("command", "")
            else:
                detail = str(config)

            if verbose:
                source = self.server_sources.get(name, "unknown")
                lines.append(f"  {name} ({server_type}): {detail}\n    Source: {source}")
            else:
                lines.append(f"  {name} ({server_type})")

        return lines

    def get_project_mcps(self, project_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all MCPs configured for a specific project path.

        Args:
            project_path: The project directory path

        Returns:
            Dict of MCP server configs for that project
        """
        if not CLAUDE_CONFIG_PATH.exists():
            return {}

        try:
            with open(CLAUDE_CONFIG_PATH, "r") as f:
                config = json.load(f)
        except Exception:
            return {}

        projects = config.get("projects", {})

        # Try exact match first
        if project_path in projects:
            return projects[project_path].get("mcpServers", {})

        # Try normalized path
        normalized = str(Path(project_path).resolve())
        if normalized in projects:
            return projects[normalized].get("mcpServers", {})

        return {}

    def reload(self):
        """Reload the registry from the config file."""
        self.servers.clear()
        self.server_sources.clear()
        self._load_from_claude_config()


# Global registry instance
_registry: Optional[MCPRegistry] = None


def get_registry() -> MCPRegistry:
    """Get or create the global MCP registry."""
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry
