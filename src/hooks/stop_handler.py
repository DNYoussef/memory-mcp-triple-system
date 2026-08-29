#!/usr/bin/env python3
"""Stop hook handler -- generates a summary when Claude accepts a Stop event.

Called by Claude Code's Stop lifecycle event.
Summarizes the session's observations into a structured summary and stores it.
Per-session handoff files remain because Stop can fire more than once per session.

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

from src.stores.kv_store import KVStore  # noqa: E402
from src.services.session_summarizer import SessionSummarizer  # noqa: E402


# Default paths
DEFAULT_DB = os.path.join(str(Path.home()), ".claude", "memory-mcp-data", "agent_kv.db")


def _session_file(hook_session_id: str) -> str:
    return os.path.join(
        str(Path.home()),
        ".claude",
        "memory-mcp-data",
        f"current_session-{hook_session_id}.json",
    )


def get_current_session(hook_session_id: str) -> dict:
    """Read current session info from shared file."""
    try:
        path = _session_file(hook_session_id)
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def main():
    """Main entry point for Stop hook."""
    try:
        raw = sys.stdin.read()
        hook_payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_payload = {}

    hook_session_id = hook_payload.get("session_id", "")
    if not hook_session_id:
        return

    # Open store
    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        return

    try:
        store = KVStore(db_path)
    except Exception as exc:
        sys.stderr.write(f"stop_handler: KVStore init failed ({type(exc).__name__})\n")
        return

    try:
        session_info = get_current_session(hook_session_id)
        obs_session_id = session_info.get("session_id", "")
        if not obs_session_id:
            return

        summarizer = SessionSummarizer(kv_store=store)
        summary = summarizer.summarize(obs_session_id)

        if summary.observation_count > 0:
            summarizer.store_summary(summary)

            # Token economics: track summary cost
            summary_text = summary.to_text()
            est_tokens = len(summary_text) // 4
            store.set(
                f"economics:summary:{obs_session_id}",
                json.dumps(
                    {
                        "session_id": obs_session_id,
                        "summary_tokens": est_tokens,
                        "observation_count": summary.observation_count,
                        "duration_seconds": summary.duration_seconds,
                    }
                ),
            )

    except Exception:
        # Silent failure
        pass
    finally:
        try:
            store.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
