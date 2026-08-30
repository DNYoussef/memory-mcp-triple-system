#!/usr/bin/env python3
"""Assign a fresh marker to each UserPromptSubmit event."""

import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.stores.kv_store import DEFAULT_DB_NAME, KVStore  # noqa: E402


DEFAULT_DB = os.path.join(
    str(Path.home()), ".claude", "memory-mcp-data", DEFAULT_DB_NAME
)


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        return

    session_id = payload.get("session_id", "")
    if not session_id:
        return
    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        return

    store = None
    try:
        store = KVStore(db_path)
        marker = secrets.token_hex(8)
        if not store.set(f"prompt_marker:{session_id}", marker, ttl=86400):
            sys.stderr.write(
                "prompt_marker_handler: marker write failed, KV store may be degraded\n"
            )
    except Exception as exc:
        sys.stderr.write(f"prompt_marker_handler: skipped ({type(exc).__name__})\n")
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
