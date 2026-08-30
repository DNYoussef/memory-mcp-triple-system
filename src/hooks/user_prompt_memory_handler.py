#!/usr/bin/env python3
"""Inject relevant recent observations at UserPromptSubmit without gate writes."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.stores.kv_store import KVStore  # noqa: E402


DEFAULT_DB = os.path.join(str(Path.home()), ".claude", "memory-mcp-data", "agent_kv.db")


def _emit(context: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    data = (json.dumps(output) + "\n").encode("utf-8", "replace")
    sys.stdout.buffer.write(data)
    sys.stdout.flush()


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        return

    prompt = payload.get("prompt", "")
    if not prompt:
        return
    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        return

    store = None
    try:
        store = KVStore(db_path)
        project = os.path.basename(payload.get("cwd", os.getcwd()))
        recent = store.get_observations(project=project, limit=8)
        words = [word.lower() for word in prompt.split() if len(word) > 3]
        hits = [
            observation
            for observation in recent
            if any(
                word
                in (
                    observation.get("content", "") + observation.get("tool_name", "")
                ).lower()
                for word in words
            )
        ]
        if hits:
            lines = ["## Possibly relevant prior activity"]
            for observation in hits[:5]:
                timestamp = observation.get("created_at", "")[:16]
                lines.append(
                    f"  [{timestamp}] {observation.get('tool_name', '')}: "
                    f"{observation.get('content', '')[:120]}"
                )
            _emit("\n".join(lines))
    except Exception as exc:
        sys.stderr.write(
            f"user_prompt_memory_handler: skipped ({type(exc).__name__})\n"
        )
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
