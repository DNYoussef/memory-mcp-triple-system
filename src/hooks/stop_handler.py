#!/usr/bin/env python3
"""Stop hook handler -- generates a summary when Claude accepts a Stop event.

Called by Claude Code's Stop lifecycle event.
Summarizes the session's observations into a structured summary and stores it.
Per-session handoff files remain because Stop can fire more than once per session.

Usage (from settings.json):
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
from datetime import datetime, timezone
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
        skip_key = f"skip:{hook_session_id}"
        last_edit = store.get(f"last_edit_at:{hook_session_id}")
        if last_edit and store.get(skip_key) is not None and store.delete(skip_key):
            now_iso = datetime.now(timezone.utc).isoformat()
            if not store.set(f"last_save_at:{hook_session_id}", now_iso, ttl=86400):
                sys.stderr.write(
                    "stop_handler: skip-consumption save write failed, "
                    "KV store may be degraded\n"
                )

        if not hook_payload.get("stop_hook_active"):
            last_save = store.get(f"last_save_at:{hook_session_id}")
            if last_edit and (not last_save or last_edit > last_save):
                sys.stderr.write(
                    "Memory gate: this session has an edit newer than your last "
                    "saved memory. Load a remedy with ToolSearch, then call "
                    "mcp__memory-mcp__memory_store("
                    'text="<distilled lesson or decision>") or '
                    'mcp__memory-mcp__kv_set(key="skip:'
                    + hook_session_id
                    + '", value="<reason>", ttl=86400) before stopping.\n'
                )
                sys.exit(2)

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
