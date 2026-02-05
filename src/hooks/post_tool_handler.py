#!/usr/bin/env python3
"""PostToolUse hook handler -- auto-captures tool invocations as observations.

Called by Claude Code's PostToolUse lifecycle event.
Reads tool name + result from stdin JSON, classifies, deduplicates,
stores as structured observation. Must be FAST (<100ms blocking).

Usage (from settings.local.json):
    "hooks": {
        "PostToolUse": [{
            "type": "command",
            "command": "python D:/Projects/memory-mcp-triple-system/src/hooks/post_tool_handler.py"
        }]
    }

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import os
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.stores.kv_store import KVStore
from src.services.observation_bridge import ObservationBridge


# Default paths
DEFAULT_DB = os.path.join(
    str(Path.home()), ".claude", "memory-mcp-data", "agent_kv.db"
)
SESSION_FILE = os.path.join(
    str(Path.home()), ".claude", "memory-mcp-data", "current_session.json"
)

# Privacy tag regex
PRIVATE_RE = re.compile(r"<private>.*?</private>", re.DOTALL)


def strip_private(text: str) -> str:
    """Remove <private>...</private> tagged content before storage."""
    return PRIVATE_RE.sub("[REDACTED]", text)


def get_current_session() -> dict:
    """Read current session info from shared file."""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def main():
    """Main entry point for PostToolUse hook."""
    # Read hook payload from stdin
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    # Extract tool info from payload
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    tool_result = payload.get("tool_output", payload.get("tool_result", ""))

    # Skip if no tool name
    if not tool_name:
        return

    # Check for errors
    is_error = False
    if isinstance(tool_result, str):
        is_error = "error" in tool_result.lower()[:200] or "Error" in tool_result[:200]

    # Strip private content
    if isinstance(tool_result, str):
        tool_result = strip_private(tool_result)

    # Get session info
    session_info = get_current_session()
    session_id = session_info.get("session_id", "")
    project = session_info.get("project", "")

    if not session_id:
        # No active session -- skip capture
        return

    # Open store and bridge
    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        return

    store = KVStore(db_path)
    bridge = ObservationBridge(kv_store=store)

    try:
        # Truncate large results to keep observations lean
        if isinstance(tool_result, str) and len(tool_result) > 500:
            tool_result = tool_result[:500] + "..."

        bridge.capture_tool_use(
            session_id=session_id,
            tool_name=tool_name,
            tool_input=tool_input if isinstance(tool_input, dict) else {},
            tool_result=str(tool_result) if tool_result else "",
            is_error=is_error,
            project=project,
        )
    except Exception:
        # Silent failure -- never block Claude Code
        pass
    finally:
        store.close()


if __name__ == "__main__":
    main()
