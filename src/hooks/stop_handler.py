#!/usr/bin/env python3
"""Stop hook handler -- generates session summary at session end.

Called by Claude Code's Stop lifecycle event.
Summarizes the session's observations into a structured summary,
stores it, and cleans up the current_session file.

Usage (from settings.local.json):
    "hooks": {
        "Stop": [{
            "type": "command",
            "command": "python D:/Projects/memory-mcp-triple-system/src/hooks/stop_handler.py"
        }]
    }

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.stores.kv_store import KVStore
from src.services.session_summarizer import SessionSummarizer


# Default paths
DEFAULT_DB = os.path.join(
    str(Path.home()), ".claude", "memory-mcp-data", "agent_kv.db"
)
SESSION_FILE = os.path.join(
    str(Path.home()), ".claude", "memory-mcp-data", "current_session.json"
)


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
    """Main entry point for Stop hook."""
    # Read hook payload from stdin (may be empty)
    try:
        raw = sys.stdin.read()
    except IOError:
        pass

    # Get session info
    session_info = get_current_session()
    session_id = session_info.get("session_id", "")

    if not session_id:
        return

    # Open store
    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        return

    store = KVStore(db_path)

    try:
        # Generate and store summary
        summarizer = SessionSummarizer(kv_store=store)
        summary = summarizer.summarize(session_id)

        if summary.observation_count > 0:
            summarizer.store_summary(summary)

            # Token economics: track summary cost
            summary_text = summary.to_text()
            est_tokens = len(summary_text) // 4
            store.set(
                f"economics:summary:{session_id}",
                json.dumps({
                    "session_id": session_id,
                    "summary_tokens": est_tokens,
                    "observation_count": summary.observation_count,
                    "duration_seconds": summary.duration_seconds,
                }),
            )

        # Clean up session file
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
        except OSError:
            pass

    except Exception:
        # Silent failure
        pass
    finally:
        store.close()


if __name__ == "__main__":
    main()
