#!/usr/bin/env python3
"""Deny the first edit attempt until recall succeeds, then fail open."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.stores.kv_store import DEFAULT_DB_NAME, KVStore  # noqa: E402


DEFAULT_DB = os.path.join(
    str(Path.home()), ".claude", "memory-mcp-data", DEFAULT_DB_NAME
)
EDIT_TOOLS = {"Write", "Edit", "NotebookEdit", "apply_patch"}


def _deny(reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    data = (json.dumps(output) + "\n").encode("utf-8", "replace")
    sys.stdout.buffer.write(data)
    sys.stdout.flush()


def _retrieval_remedy(payload: dict) -> str:
    if "turn_id" in payload:
        return (
            "Call mcp__memory_mcp__unified_search"
            '(query="<this task, in your own words>"), then retry.'
        )
    return (
        'Call ToolSearch("select:mcp__memory-mcp__unified_search") then '
        'unified_search(query="<this task, in your own words>"), then retry.'
    )


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        return

    session_id = payload.get("session_id", "")
    if not session_id or payload.get("tool_name") not in EDIT_TOOLS:
        return
    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        return

    store = None
    try:
        store = KVStore(db_path)
        marker = store.get(f"prompt_marker:{session_id}")
        if not marker or store.get(f"recall:{session_id}:{marker}"):
            return
        nudge_key = f"recall_nudge:{session_id}:{marker}"
        if store.get(nudge_key):
            return
        if not store.set(nudge_key, "1", ttl=86400):
            sys.stderr.write(
                "pre_tool_memory_gate: nudge write failed, allowing to avoid deadlock\n"
            )
            return
        _deny(
            "Memory gate: no successful retrieval recorded yet this prompt. "
            + _retrieval_remedy(payload)
        )
    except Exception as exc:
        sys.stderr.write(
            f"pre_tool_memory_gate: getting out of the way ({type(exc).__name__})\n"
        )
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
