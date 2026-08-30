"""Compatibility checks using captured Codex lifecycle hook payloads."""

import io
import json
import sys
from datetime import datetime, timezone

import pytest

from src.stores.kv_store import KVStore


class _HookStdout:
    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, text):
        return self.buffer.write(text.encode("utf-8"))

    def flush(self):
        pass

    def text(self):
        return self.buffer.getvalue().decode("utf-8")


def _db(tmp_path, monkeypatch):
    path = tmp_path / "agent_kv.db"
    KVStore(str(path)).close()
    monkeypatch.setenv("MEMORY_MCP_DB", str(path))
    return path


def _invoke(module, payload, monkeypatch):
    stdout = _HookStdout()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    module.main()
    return stdout.text(), stderr.getvalue()


def test_codex_apply_patch_is_gated_and_recorded(tmp_path, monkeypatch):
    from src.hooks import post_tool_handler, pre_tool_memory_gate, session_start_handler

    db_path = _db(tmp_path, monkeypatch)
    session_id = "codex-edit-session"
    marker = "codex-edit-marker"
    handoff = tmp_path / "codex-handoff.json"
    monkeypatch.setattr(
        session_start_handler,
        "get_project_info",
        lambda: {"project": "codex-test", "branch": "main", "cwd": str(tmp_path)},
    )
    monkeypatch.setattr(session_start_handler, "_session_file", lambda _: str(handoff))
    stdout, _ = _invoke(
        session_start_handler,
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "turn_id": "codex-turn-start",
        },
        monkeypatch,
    )
    start_output = json.loads(stdout)["hookSpecificOutput"]
    assert start_output["hookEventName"] == "SessionStart"
    assert start_output["additionalContext"].endswith("## Memory Store: ARMED")

    store = KVStore(str(db_path))
    store.set(f"prompt_marker:{session_id}", marker, ttl=86400)
    store.close()
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": session_id,
        "turn_id": "codex-turn-edit",
        "tool_name": "apply_patch",
        "tool_input": {"command": "*** Begin Patch"},
    }

    stdout, _ = _invoke(pre_tool_memory_gate, payload, monkeypatch)
    decision = json.loads(stdout)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert "mcp__memory_mcp__unified_search" in decision["permissionDecisionReason"]

    store = KVStore(str(db_path))
    store.set(f"recall:{session_id}:{marker}", "1", ttl=86400)
    store.close()
    stdout, _ = _invoke(pre_tool_memory_gate, payload, monkeypatch)
    assert stdout == ""

    payload.update(
        {
            "hook_event_name": "PostToolUse",
            "tool_response": "Done!",
        }
    )
    _invoke(post_tool_handler, payload, monkeypatch)
    store = KVStore(str(db_path))
    assert store.get(f"last_edit_at:{session_id}")
    store.delete(f"last_edit_at:{session_id}")
    store.close()

    payload["tool_response"] = {"content": [], "isError": True}
    _invoke(post_tool_handler, payload, monkeypatch)
    store = KVStore(str(db_path))
    assert store.get(f"last_edit_at:{session_id}") is None
    store.close()


def test_codex_normalized_memory_tools_credit_recall_and_save(tmp_path, monkeypatch):
    from src.hooks import post_tool_handler

    db_path = _db(tmp_path, monkeypatch)
    session_id = "codex-memory-session"
    marker = "codex-memory-marker"
    store = KVStore(str(db_path))
    store.set(f"prompt_marker:{session_id}", marker, ttl=86400)
    store.close()
    base = {
        "hook_event_name": "PostToolUse",
        "session_id": session_id,
        "tool_response": {
            "content": [{"type": "text", "text": "results"}],
            "isError": False,
        },
    }

    _invoke(
        post_tool_handler,
        {**base, "tool_name": "mcp__memory_mcp__unified_search"},
        monkeypatch,
    )
    saved = {
        **base,
        "tool_name": "mcp__memory_mcp__memory_store",
        "tool_response": {
            "content": [{"type": "text", "text": "Stored memory: codex result"}],
            "isError": False,
        },
    }
    _invoke(post_tool_handler, saved, monkeypatch)

    store = KVStore(str(db_path))
    assert store.get(f"recall:{session_id}:{marker}") == "1"
    assert store.get(f"last_save_at:{session_id}")
    store.close()


def test_codex_stop_emits_json_on_success_and_exact_remedy_on_block(
    tmp_path, monkeypatch
):
    from src.hooks import stop_handler

    codex_stop = {
        "hook_event_name": "Stop",
        "turn_id": "codex-turn-stop",
        "stop_hook_active": False,
    }
    stdout, _ = _invoke(stop_handler, codex_stop, monkeypatch)
    assert json.loads(stdout) == {}

    missing = tmp_path / "missing.db"
    monkeypatch.setenv("MEMORY_MCP_DB", str(missing))
    stdout, stderr = _invoke(
        stop_handler, {**codex_stop, "session_id": "missing-db"}, monkeypatch
    )
    assert json.loads(stdout) == {}
    assert "memory database is unavailable" in stderr

    db_path = _db(tmp_path, monkeypatch)
    session_id = "codex-stop-session"
    monkeypatch.setattr(stop_handler, "_session_file", lambda _: str(missing))
    stdout, _ = _invoke(
        stop_handler, {**codex_stop, "session_id": session_id}, monkeypatch
    )
    assert json.loads(stdout) == {}

    with monkeypatch.context() as scoped:
        scoped.setenv("MEMORY_MCP_DB", str(db_path))
        scoped.setattr(
            stop_handler,
            "KVStore",
            lambda _: (_ for _ in ()).throw(RuntimeError("broken store")),
        )
        stdout, _ = _invoke(
            stop_handler,
            {**codex_stop, "session_id": "broken-store"},
            scoped,
        )
        assert json.loads(stdout) == {}

    handoff = tmp_path / "handoff.json"
    handoff.write_text(
        json.dumps({"session_id": "observation-session"}), encoding="utf-8"
    )
    monkeypatch.setattr(stop_handler, "_session_file", lambda _: str(handoff))

    class _Summary:
        observation_count = 0

    class _Summarizer:
        def __init__(self, kv_store):
            pass

        def summarize(self, observation_session_id):
            assert observation_session_id == "observation-session"
            return _Summary()

    monkeypatch.setattr(stop_handler, "SessionSummarizer", _Summarizer)
    stdout, _ = _invoke(
        stop_handler, {**codex_stop, "session_id": session_id}, monkeypatch
    )
    assert json.loads(stdout) == {}

    monkeypatch.setattr(
        stop_handler,
        "SessionSummarizer",
        lambda **_: (_ for _ in ()).throw(RuntimeError("broken summary")),
    )
    stdout, _ = _invoke(
        stop_handler, {**codex_stop, "session_id": session_id}, monkeypatch
    )
    assert json.loads(stdout) == {}

    store = KVStore(str(db_path))
    store.set(
        f"last_edit_at:{session_id}",
        datetime.now(timezone.utc).isoformat(),
        ttl=86400,
    )
    store.close()
    with pytest.raises(SystemExit) as exc:
        _invoke(stop_handler, {**codex_stop, "session_id": session_id}, monkeypatch)
    assert exc.value.code == 2
    stdout = sys.stdout.text()
    stderr = sys.stderr.getvalue()
    assert stdout == ""
    assert "ToolSearch" not in stderr
    assert "mcp__memory_mcp__memory_store" in stderr
    assert "mcp__memory_mcp__kv_set" in stderr
    store = KVStore(str(db_path))
    assert store.get(f"stop_nudge:{session_id}") == "1"
    store.close()

    claude_session = "claude-stop-session"
    store = KVStore(str(db_path))
    store.set(
        f"last_edit_at:{claude_session}",
        datetime.now(timezone.utc).isoformat(),
        ttl=86400,
    )
    store.close()
    with pytest.raises(SystemExit) as exc:
        _invoke(
            stop_handler,
            {"hook_event_name": "Stop", "session_id": claude_session},
            monkeypatch,
        )
    assert exc.value.code == 2
    stderr = sys.stderr.getvalue()
    assert "ToolSearch" in stderr
    assert "mcp__memory-mcp__memory_store" in stderr
    assert "mcp__memory-mcp__kv_set" in stderr
