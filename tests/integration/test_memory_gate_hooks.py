"""Hermetic state-machine tests for the Claude memory gate hooks."""

import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.models.observation_types import Session
from src.services.observation_bridge import ObservationBridge
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


def test_prompt_marker_and_recall_gate_are_prompt_scoped_and_one_shot(
    tmp_path, monkeypatch
):
    from src.hooks import pre_tool_memory_gate, prompt_marker_handler

    db_path = _db(tmp_path, monkeypatch)
    session_id = "hook-session-a"

    _invoke(prompt_marker_handler, {"session_id": session_id}, monkeypatch)
    store = KVStore(str(db_path))
    marker = store.get(f"prompt_marker:{session_id}")
    assert marker
    store.close()

    edit_payload = {"session_id": session_id, "tool_name": "Edit"}
    stdout, _ = _invoke(pre_tool_memory_gate, edit_payload, monkeypatch)
    decision = json.loads(stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "successful retrieval" in decision["permissionDecisionReason"]

    store = KVStore(str(db_path))
    assert store.get(f"recall_nudge:{session_id}:{marker}") == "1"
    store.close()

    stdout, _ = _invoke(pre_tool_memory_gate, edit_payload, monkeypatch)
    assert stdout == "", "the retry must fail open instead of denying forever"

    _invoke(prompt_marker_handler, {"session_id": session_id}, monkeypatch)
    store = KVStore(str(db_path))
    next_marker = store.get(f"prompt_marker:{session_id}")
    assert next_marker and next_marker != marker
    store.set(f"recall:{session_id}:{marker}", "1", ttl=86400)
    store.close()

    stdout, _ = _invoke(pre_tool_memory_gate, edit_payload, monkeypatch)
    assert json.loads(stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    store = KVStore(str(db_path))
    store.set(f"recall:{session_id}:{next_marker}", "1", ttl=86400)
    store.close()

    stdout, _ = _invoke(pre_tool_memory_gate, edit_payload, monkeypatch)
    assert stdout == ""

    session_without_nudge = "non-edit-session"
    _invoke(prompt_marker_handler, {"session_id": session_without_nudge}, monkeypatch)
    stdout, _ = _invoke(
        pre_tool_memory_gate,
        {"session_id": session_without_nudge, "tool_name": "Read"},
        monkeypatch,
    )
    assert stdout == ""
    store = KVStore(str(db_path))
    assert store.keys(f"recall_nudge:{session_without_nudge}:") == []
    store.close()

    stdout, _ = _invoke(
        pre_tool_memory_gate,
        {"session_id": "session-without-marker", "tool_name": "Write"},
        monkeypatch,
    )
    assert stdout == "", "no marker is a fail-open path"


def test_post_tool_handler_records_receipts_and_dirty_save_timestamps(
    tmp_path, monkeypatch
):
    from src.hooks import post_tool_handler

    db_path = _db(tmp_path, monkeypatch)
    session_id = "hook-session-b"
    marker = "marker-b"
    store = KVStore(str(db_path))
    store.set(f"prompt_marker:{session_id}", marker, ttl=86400)
    store.close()

    success_with_error_words = {
        "session_id": session_id,
        "tool_name": "mcp__memory-mcp__unified_search",
        "tool_input": {"query": "failed error handling"},
        "tool_response": [
            {"type": "text", "text": "results about failed error handling"}
        ],
    }
    _invoke(post_tool_handler, success_with_error_words, monkeypatch)

    store = KVStore(str(db_path))
    assert store.get(f"recall:{session_id}:{marker}") == "1"
    store.delete(f"recall:{session_id}:{marker}")
    store.close()

    failed = dict(success_with_error_words)
    failed["tool_response"] = {"content": [], "isError": True}
    _invoke(post_tool_handler, failed, monkeypatch)
    store = KVStore(str(db_path))
    assert store.get(f"recall:{session_id}:{marker}") is None
    store.close()

    edit = {
        "session_id": session_id,
        "tool_name": "Edit",
        "tool_input": {"file_path": "sample.py"},
        "tool_response": {"success": True},
    }
    _invoke(post_tool_handler, edit, monkeypatch)
    store = KVStore(str(db_path))
    last_edit = store.get(f"last_edit_at:{session_id}")
    assert last_edit
    store.close()

    saved = {
        "session_id": session_id,
        "tool_name": "mcp__memory-mcp__memory_store",
        "tool_input": {"text": "fixed the error after the build failed"},
        "tool_response": [{"type": "text", "text": "Stored memory: fixed the error"}],
    }
    failed_save = dict(saved)
    failed_save["tool_response"] = [
        {"type": "text", "text": "Error: Empty text provided"}
    ]
    _invoke(post_tool_handler, failed_save, monkeypatch)
    store = KVStore(str(db_path))
    assert store.get(f"last_save_at:{session_id}") is None
    store.close()

    _invoke(post_tool_handler, saved, monkeypatch)
    store = KVStore(str(db_path))
    last_save = store.get(f"last_save_at:{session_id}")
    store.close()
    assert last_save and last_save >= last_edit


def test_stop_gate_dirty_save_skip_and_internal_session_id(tmp_path, monkeypatch):
    from src.hooks import stop_handler

    db_path = _db(tmp_path, monkeypatch)
    hook_session_id = "hook-session-c"
    obs_session_id = "observation-session-c"
    handoff = tmp_path / "handoff.json"
    handoff.write_text(
        json.dumps({"session_id": obs_session_id, "project": "gate-test"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(stop_handler, "_session_file", lambda _: str(handoff))

    seen = []

    class _Summary:
        observation_count = 0

    class _Summarizer:
        def __init__(self, kv_store):
            pass

        def summarize(self, session_id):
            seen.append(session_id)
            return _Summary()

    monkeypatch.setattr(stop_handler, "SessionSummarizer", _Summarizer)
    store = KVStore(str(db_path))
    store.set(f"skip:{hook_session_id}", "proactive waiver", ttl=86400)
    store.close()
    _invoke(stop_handler, {"session_id": hook_session_id}, monkeypatch)
    store = KVStore(str(db_path))
    assert store.get(f"skip:{hook_session_id}") == "proactive waiver"
    store.delete(f"skip:{hook_session_id}")
    store.close()

    dirty_at = datetime.now(timezone.utc) - timedelta(seconds=3)
    store = KVStore(str(db_path))
    store.set(f"last_edit_at:{hook_session_id}", dirty_at.isoformat(), ttl=86400)
    store.close()

    with pytest.raises(SystemExit) as exc:
        _invoke(stop_handler, {"session_id": hook_session_id}, monkeypatch)
    assert exc.value.code == 2

    store = KVStore(str(db_path))
    saved_at = (dirty_at + timedelta(seconds=1)).isoformat()
    store.set(f"last_save_at:{hook_session_id}", saved_at, ttl=86400)
    store.close()
    _invoke(stop_handler, {"session_id": hook_session_id}, monkeypatch)
    assert seen[-1] == obs_session_id
    assert handoff.exists(), "Stop fires per turn and must not delete the handoff"

    store = KVStore(str(db_path))
    waived_edit_at = (dirty_at + timedelta(seconds=2)).isoformat()
    store.set(f"last_edit_at:{hook_session_id}", waived_edit_at, ttl=86400)
    store.set(f"skip:{hook_session_id}", "test waiver", ttl=86400)
    store.close()
    _invoke(
        stop_handler,
        {"session_id": hook_session_id, "stop_hook_active": True},
        monkeypatch,
    )
    store = KVStore(str(db_path))
    assert store.get(f"skip:{hook_session_id}") is None
    assert store.get(f"last_save_at:{hook_session_id}") >= waived_edit_at
    store.close()


def test_stop_gate_does_not_consume_skip_when_delete_fails(tmp_path, monkeypatch):
    from src.hooks import stop_handler

    db_path = _db(tmp_path, monkeypatch)
    session_id = "hook-session-d"
    handoff = tmp_path / "handoff.json"
    handoff.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(stop_handler, "_session_file", lambda _: str(handoff))
    dirty_at = datetime.now(timezone.utc).isoformat()
    store = KVStore(str(db_path))
    store.set(f"last_edit_at:{session_id}", dirty_at, ttl=86400)
    store.set(f"skip:{session_id}", "test waiver", ttl=86400)
    store.close()
    monkeypatch.setattr(KVStore, "delete", lambda self, key: False)

    _invoke(
        stop_handler,
        {"session_id": session_id, "stop_hook_active": True},
        monkeypatch,
    )
    store = KVStore(str(db_path))
    assert store.get(f"last_save_at:{session_id}") is None
    store.close()


def test_session_start_uses_per_hook_handoff_and_always_emits_health(
    tmp_path, monkeypatch
):
    from src.hooks import session_start_handler

    db_path = _db(tmp_path, monkeypatch)
    monkeypatch.setattr(
        session_start_handler,
        "get_project_info",
        lambda: {"project": "gate-test", "branch": "main", "cwd": str(tmp_path)},
    )
    monkeypatch.setattr(
        session_start_handler,
        "_session_file",
        lambda hook_id: str(tmp_path / f"current_session-{hook_id}.json"),
    )

    stdout, _ = _invoke(session_start_handler, {"session_id": "hook-one"}, monkeypatch)
    assert stdout.rstrip().endswith("## Memory Store: ARMED")
    _invoke(session_start_handler, {"session_id": "hook-two"}, monkeypatch)

    first = json.loads((tmp_path / "current_session-hook-one.json").read_text())
    second = json.loads((tmp_path / "current_session-hook-two.json").read_text())
    assert first["session_id"] != second["session_id"]
    assert first["session_id"] not in {"hook-one", "hook-two"}
    assert second["session_id"] not in {"hook-one", "hook-two"}

    missing = tmp_path / "missing.db"
    monkeypatch.setenv("MEMORY_MCP_DB", str(missing))
    stdout, _ = _invoke(
        session_start_handler, {"session_id": "hook-three"}, monkeypatch
    )
    assert "Memory Store: DOWN (no database)" in stdout

    monkeypatch.setenv("MEMORY_MCP_DB", str(db_path))
    monkeypatch.setattr(
        session_start_handler,
        "KVStore",
        lambda _: (_ for _ in ()).throw(RuntimeError("broken store")),
    )
    stdout, _ = _invoke(session_start_handler, {"session_id": "hook-four"}, monkeypatch)
    assert "Memory Store: DOWN (RuntimeError)" in stdout


def test_prompt_injection_is_read_only_gate_state(tmp_path, monkeypatch):
    from src.hooks import user_prompt_memory_handler

    db_path = _db(tmp_path, monkeypatch)
    project_dir = tmp_path / "gate-project"
    project_dir.mkdir()
    store = KVStore(str(db_path))
    session = Session(project="gate-project")
    store.create_session(session.to_dict())
    ObservationBridge(kv_store=store).capture_tool_use(
        session_id=session.session_id,
        tool_name="Bash",
        tool_input={"command": "alpha canary command"},
        tool_result="done",
        project="gate-project",
    )
    store.close()

    stdout, _ = _invoke(
        user_prompt_memory_handler,
        {
            "session_id": "hook-session-e",
            "prompt": "alpha task",
            "cwd": str(project_dir),
        },
        monkeypatch,
    )
    context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
    assert "alpha canary command" in context
    store = KVStore(str(db_path))
    assert store.keys("recall:") == []
    store.close()


def test_claude_md_documents_the_one_shot_gate_and_stop_waiver():
    claude_md = Path(__file__).resolve().parents[2] / "CLAUDE.md"
    text = claude_md.read_text(encoding="utf-8")
    assert "## Memory recall and save nudges" in text
    assert "The first Write/Edit/NotebookEdit attempt each prompt is denied" in text
    assert 'kv_set(key="skip:<session_id>", value="<reason>", ttl=86400)' in text
    assert "The edit denial is one-shot to prevent a hook deadlock" in text
    assert "Each\nsession-end attempt is blocked" in text
