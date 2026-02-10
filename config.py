#!/usr/bin/env python3

"""
Scheduler Config - JSON-backed configuration with schema validation.

Provides global defaults for ClaudeTask execution (model, budget, etc.)
that can be overridden per-task via command flags.
"""

import json
import os
from typing import Dict, Any, Optional, Tuple

CONFIG_FILE = "claude_scheduler_config.json"

# Schema: key → (type, description)
CONFIG_SCHEMA: Dict[str, Tuple[type, str]] = {
    "model": (str, "Default Claude model (e.g. sonnet, claude-sonnet-4-5)"),
    "fallback_model": (str, "Fallback model if primary fails"),
    "permission_mode": (str, "Permission mode (default, acceptEdits, plan, bypassPermissions)"),
    "max_turns": (int, "Maximum conversation turns per task"),
    "max_budget_usd": (float, "Maximum budget in USD per task"),
}


class SchedulerConfig:
    """
    Schema-validated key-value config backed by a JSON file.
    """

    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self.load()

    def get(self, key: str) -> Optional[Any]:
        """Get a setting value, or None if unset."""
        return self._settings.get(key)

    def set(self, key: str, value: str) -> None:
        """
        Set a config value. Validates key against schema and coerces type.

        Args:
            key: Setting name (must be in CONFIG_SCHEMA)
            value: String value (will be coerced to the schema type)

        Raises:
            KeyError: Unknown setting key
            ValueError: Value cannot be coerced to expected type
        """
        if key not in CONFIG_SCHEMA:
            valid = ", ".join(sorted(CONFIG_SCHEMA.keys()))
            raise KeyError(f"Unknown setting: {key}. Valid settings: {valid}")

        expected_type, _ = CONFIG_SCHEMA[key]

        try:
            if expected_type is int:
                coerced = int(value)
            elif expected_type is float:
                coerced = float(value)
            else:
                coerced = str(value)
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid value for {key}: expected {expected_type.__name__}, got '{value}'"
            )

        self._settings[key] = coerced
        self.save()

    def clear(self, key: str) -> None:
        """
        Clear a setting (revert to SDK default).

        Args:
            key: Setting name (must be in CONFIG_SCHEMA)

        Raises:
            KeyError: Unknown setting key
        """
        if key not in CONFIG_SCHEMA:
            valid = ", ".join(sorted(CONFIG_SCHEMA.keys()))
            raise KeyError(f"Unknown setting: {key}. Valid settings: {valid}")

        self._settings.pop(key, None)
        self.save()

    def all(self) -> Dict[str, Any]:
        """Return a copy of all settings."""
        return dict(self._settings)

    def load(self) -> bool:
        """Load settings from JSON file."""
        if not os.path.exists(CONFIG_FILE):
            return False

        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)

            if isinstance(data, dict):
                # Only load keys that are in the schema
                for key, value in data.items():
                    if key in CONFIG_SCHEMA:
                        self._settings[key] = value
                return True

        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Failed to load config from {CONFIG_FILE}: {e}")

        return False

    def save(self) -> bool:
        """Save settings to JSON file."""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._settings, f, indent=2)
                f.write("\n")
            return True
        except Exception as e:
            print(f"Warning: Failed to save config to {CONFIG_FILE}: {e}")
            return False


# Singleton
_config: Optional[SchedulerConfig] = None


def get_config() -> SchedulerConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = SchedulerConfig()
    return _config
