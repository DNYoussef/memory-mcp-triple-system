"""
Path utilities for cross-platform portability.

This module provides helper functions to avoid hardcoded paths.
"""

import os
from pathlib import Path


def get_user_home() -> Path:
    """Get user home directory."""
    return Path.home()


def get_project_root() -> Path:
    """Get memory-mcp-triple-system root directory."""
    return Path(__file__).parent.parent


def get_claude_plugins_dir() -> Path:
    """Get claude-code-plugins directory (from env or default)."""
    default = get_user_home() / "claude-code-plugins"
    return Path(os.environ.get("CLAUDE_PLUGINS_DIR", default))


def get_connascence_dir() -> Path:
    """Get connascence analyzer directory (from env or default)."""
    default = get_user_home() / "Desktop" / "connascence"
    return Path(os.environ.get("CONNASCENCE_DIR", default))


def get_memory_mcp_dir() -> Path:
    """Get memory-mcp-triple-system directory."""
    return get_project_root()


# Location constants for knowledge base population
# These use environment variables with sensible defaults
PROJECT_LOCATIONS = {
    "connascence-analyzer": get_connascence_dir(),
    "memory-mcp-triple-system": get_memory_mcp_dir(),
    "ruv-sparc-three-loop-system": get_claude_plugins_dir() / "ruv-sparc-three-loop-system",
}


def get_location(project_name: str) -> str:
    """Get project location as string (for knowledge base metadata)."""
    return str(PROJECT_LOCATIONS.get(project_name, get_user_home() / project_name))
