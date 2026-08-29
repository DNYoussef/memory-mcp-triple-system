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
import hashlib
import os
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.stores.kv_store import KVStore  # noqa: E402
from src.services.observation_bridge import ObservationBridge  # noqa: E402


# Default paths
DEFAULT_DB = os.path.join(str(Path.home()), ".claude", "memory-mcp-data", "agent_kv.db")
# Privacy tag regex
PRIVATE_RE = re.compile(r"<private>.*?</private>", re.DOTALL)
PRIVATE_OPEN_RE = re.compile(r"<private>.*$", re.DOTALL)
SECRET_PATTERNS = [
    re.compile(
        r"""(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PRIVATE[_-]?KEY)[A-Z0-9_]*)\s*[:=]\s*(?:"(?:\\.|[^"\\])*(?:"|$)|'(?:\\.|[^'\\])*(?:'|$)|[^\s,;]+)"""
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(?:Bearer|Basic|Digest)\s+[A-Za-z0-9+/=._~-]{8,}\b"),
    re.compile(r"(?i)\bAuthorization\s*:\s*.+"),
]
SECRET_KEY_SUBSTRINGS = (
    "APIKEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PRIVATEKEY",
    "AUTHORIZATION",
    "AUTH",
    "CREDENTIAL",
)
TRAILING_SECRET_PATTERNS = (
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]*$"),
    re.compile(r"(?i)\b(?:Bearer|Basic|Digest)\s+\S*$"),
)


def strip_private(text: str) -> str:
    """Remove private tags and common secret tokens before storage."""
    redacted = PRIVATE_RE.sub("[REDACTED]", text)
    redacted = PRIVATE_OPEN_RE.sub("[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}=[REDACTED]", redacted)
    for pattern in SECRET_PATTERNS[1:]:
        redacted = pattern.sub("[REDACTED]", redacted)
    for pattern in TRAILING_SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _looks_like_secret_key(key) -> bool:
    """Bias toward over-redaction for arbitrary field names."""
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^A-Z0-9]", "", key.upper())
    return any(word in normalized for word in SECRET_KEY_SUBSTRINGS)


def _redact_structured(obj, budget: int = 500):
    """Build a bounded, redacted preview before Python stringification."""
    if isinstance(obj, str):
        return strip_private(obj[:budget])
    if isinstance(obj, dict):
        result = {}
        remaining = budget
        for key, value in obj.items():
            if isinstance(key, str) and strip_private(key) != key:
                suffix = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
                output_key = f"[REDACTED_KEY_{suffix}]"
            else:
                output_key = key
            if isinstance(key, str) and _looks_like_secret_key(key):
                output_value = "[REDACTED]"
            elif remaining > 0:
                output_value = _redact_structured(value, remaining)
            else:
                output_value = "[TRUNCATED]"
            result[output_key] = output_value
            remaining = max(
                0,
                remaining - len(str(output_key)) - len(str(output_value)) - 4,
            )
        return result
    if isinstance(obj, list):
        result = []
        remaining = budget
        for value in obj:
            if remaining > 0:
                output_value = _redact_structured(value, remaining)
            else:
                output_value = "[TRUNCATED]"
            result.append(output_value)
            remaining = max(0, remaining - len(str(output_value)) - 2)
        return result
    return obj


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
    """Main entry point for PostToolUse hook."""
    # Read hook payload from stdin
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    raw_tool_result = payload.get("tool_response")
    if raw_tool_result is None:
        raw_tool_result = payload.get("tool_output")
    if raw_tool_result is None:
        raw_tool_result = payload.get("tool_result", "")
    tool_result = raw_tool_result

    # Skip if no tool name
    if not tool_name:
        return

    hook_session_id = payload.get("session_id", "")
    if not hook_session_id:
        return

    db_path = os.environ.get("MEMORY_MCP_DB", DEFAULT_DB)
    if not os.path.exists(db_path):
        return

    if isinstance(tool_result, (dict, list)):
        tool_result = str(_redact_structured(tool_result))
    elif isinstance(tool_result, str):
        tool_result = strip_private(tool_result)

    if isinstance(raw_tool_result, dict):
        is_error = bool(
            raw_tool_result.get("isError", raw_tool_result.get("success") is False)
        )
    elif isinstance(raw_tool_result, str):
        is_error = "error" in tool_result.lower()[:200]
    else:
        is_error = False

    if isinstance(tool_input, (dict, list)):
        tool_input = _redact_structured(tool_input)

    try:
        store = KVStore(db_path)
    except Exception as exc:
        sys.stderr.write(
            f"post_tool_handler: KVStore init failed ({type(exc).__name__})\n"
        )
        return

    try:
        session_info = get_current_session(hook_session_id)
        obs_session_id = session_info.get("session_id", "")
        if obs_session_id:
            bridge = ObservationBridge(kv_store=store)
            if isinstance(tool_result, str) and len(tool_result) > 500:
                tool_result = tool_result[:500] + "..."
            bridge.capture_tool_use(
                session_id=obs_session_id,
                tool_name=tool_name,
                tool_input=tool_input if isinstance(tool_input, dict) else {},
                tool_result=str(tool_result) if tool_result else "",
                is_error=is_error,
                project=session_info.get("project", ""),
            )
    except Exception:
        # Silent failure -- never block Claude Code
        pass
    finally:
        try:
            store.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
