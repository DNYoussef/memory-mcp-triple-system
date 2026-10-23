"""E2E integration test for the auto-capture pipeline.

Tests the full lifecycle:
  SessionStart -> PostToolUse (capture) -> Stop (summarize)

All using real KVStore (in-memory SQLite) but mocking subprocess/stdin.
"""


import pytest

from src.stores.kv_store import KVStore
from src.models.observation_types import Session
from src.services.observation_bridge import ObservationBridge
from src.services.session_summarizer import SessionSummarizer


class TestAutoCapturePipeline:
    """Full E2E test of the auto-capture pipeline."""

    @pytest.fixture
    def store(self, tmp_path):
        db = str(tmp_path / "e2e_test.db")
        s = KVStore(db)
        yield s
        s.close()

    def test_full_session_lifecycle(self, store):
        """Simulate a complete session: start -> tool uses -> stop."""
        # === Phase 1: Session Start ===
        session = Session(
            project="test-project",
            branch="main",
            working_dir="/tmp/test",
        )
        store.create_session(session.to_dict())

        # Verify session was created
        retrieved = store.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved["project"] == "test-project"

        # === Phase 2: Simulate tool invocations ===
        bridge = ObservationBridge(kv_store=store)

        # Tool use 1: Read a file
        obs1 = bridge.capture_tool_use(
            session_id=session.session_id,
            tool_name="Read",
            tool_input={"file_path": "src/main.py"},
            tool_result="def main(): ...",
            project="test-project",
        )
        assert obs1 is not None
        assert obs1.obs_type.value == "tool_use"

        # Tool use 2: Edit a file
        obs2 = bridge.capture_tool_use(
            session_id=session.session_id,
            tool_name="Edit",
            tool_input={"file_path": "src/main.py"},
            tool_result="File updated successfully",
            project="test-project",
        )
        assert obs2 is not None
        assert obs2.obs_type.value == "code_change"

        # Tool use 3: Run a bash command
        obs3 = bridge.capture_tool_use(
            session_id=session.session_id,
            tool_name="Bash",
            tool_input={"command": "pytest tests/ -v"},
            tool_result="5 passed, 0 failed",
            project="test-project",
        )
        assert obs3 is not None

        # Tool use 4: An error
        obs4 = bridge.capture_tool_use(
            session_id=session.session_id,
            tool_name="Bash",
            tool_input={"command": "python broken.py"},
            tool_result="Error: ModuleNotFoundError: No module named 'foo'",
            is_error=True,
            project="test-project",
        )
        assert obs4 is not None
        assert obs4.obs_type.value == "error"

        # Verify observations stored
        obs_list = store.get_observations(session_id=session.session_id)
        assert len(obs_list) == 4

        # Verify tool count incremented
        session_data = store.get_session(session.session_id)
        assert session_data["tool_count"] == 4

        # === Phase 3: Session Stop (Summary) ===
        summarizer = SessionSummarizer(kv_store=store)
        summary = summarizer.summarize(session.session_id)

        assert summary.observation_count == 4
        assert summary.session_id == session.session_id
        assert len(summary.investigated) > 0  # Read is investigative
        assert len(summary.completed) > 0  # Edit is completion
        assert len(summary.learned) > 0  # Error is a learning

        # Store summary
        summarizer.store_summary(summary)

        # Verify session was closed with summary
        closed = store.get_session(session.session_id)
        assert closed["summary"] is not None
        assert "investigated" in closed["summary"].lower() or len(closed["summary"]) > 0

    def test_privacy_tag_stripping(self, store):
        """Test that <private> tags are stripped from observations."""
        session = Session(project="priv-test")
        store.create_session(session.to_dict())

        bridge = ObservationBridge(kv_store=store)
        obs = bridge.capture_tool_use(
            session_id=session.session_id,
            tool_name="Bash",
            tool_input={"command": "echo test"},
            tool_result="password is <private>secret123</private> done",
            project="priv-test",
        )
        assert obs is not None
        # The private content should be redacted in stored content
        assert "secret123" not in obs.content
        assert "[REDACTED]" in obs.content

    def test_deduplication(self, store):
        """Test that duplicate observations are skipped."""
        session = Session(project="dedup-test")
        store.create_session(session.to_dict())

        bridge = ObservationBridge(kv_store=store)

        # Same tool call twice
        obs1 = bridge.capture_tool_use(
            session_id=session.session_id,
            tool_name="Read",
            tool_input={"file_path": "same.py"},
            tool_result="same content",
            project="dedup-test",
        )
        obs2 = bridge.capture_tool_use(
            session_id=session.session_id,
            tool_name="Read",
            tool_input={"file_path": "same.py"},
            tool_result="same content",
            project="dedup-test",
        )

        assert obs1 is not None
        assert obs2 is None  # Deduped

        # Only 1 observation stored
        obs_list = store.get_observations(session_id=session.session_id)
        assert len(obs_list) == 1

    def test_date_filtered_observations(self, store):
        """Test observation timeline query with date filters."""
        session = Session(project="timeline-test")
        store.create_session(session.to_dict())

        # Insert obs with specific timestamps
        for i, ts in enumerate(
            [
                "2026-02-03T10:00:00Z",
                "2026-02-04T10:00:00Z",
                "2026-02-05T10:00:00Z",
            ]
        ):
            obs = {
                "observation_id": f"obs-{i}",
                "session_id": session.session_id,
                "obs_type": "tool_use",
                "concept": "implementation",
                "tool_name": "Read",
                "content": f"content-{i}",
                "metadata": "{}",
                "who": "test",
                "project": "timeline-test",
                "why": "testing",
                "entities": "[]",
                "created_at": ts,
            }
            store.store_observation(obs)

        # Query with date range
        results = store.get_observations(
            project="timeline-test",
            after="2026-02-04T00:00:00Z",
            before="2026-02-04T23:59:59Z",
        )
        assert len(results) == 1
        assert results[0]["content"] == "content-1"


# ---- A4/A6: decision capture from memory_store metadata, why, private tags ----

import io  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
from types import SimpleNamespace  # noqa: E402

STORE_TOOLS = ["mcp__memory-mcp__memory_store", "mcp__memory_mcp__memory_store"]
STORED_OK = [{"type": "text", "text": "Stored memory: x...\nTagged: WHO=a"}]


def _replay(tmp_path, monkeypatch, payload):
    """Run the real PostToolUse hook on one payload; return the KVStore path and session."""
    from src.hooks import post_tool_handler as h

    db = tmp_path / "agent_kv.db"
    store = KVStore(str(db))
    session = Session(project="p")
    store.create_session(session.to_dict())
    store.close()
    session_file = tmp_path / "current_session.json"
    session_file.write_text(json.dumps({"session_id": session.session_id}))
    monkeypatch.setattr(h, "_session_file", lambda _: str(session_file))
    monkeypatch.setenv("MEMORY_MCP_DB", str(db))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    return KVStore(str(db))


def _store_payload(tool, metadata, response=STORED_OK):
    return {
        "session_id": "hook-s",
        "tool_name": tool,
        "tool_input": {"text": "x" * 600, "metadata": metadata},
        "tool_response": response,
    }


@pytest.mark.parametrize("tool", STORE_TOOLS)
def test_t4a_memory_store_decision_is_captured_with_why(tmp_path, monkeypatch, tool):
    meta = {"type": "decision", "why": "chose X"}
    store = _replay(tmp_path, monkeypatch, _store_payload(tool, meta))
    rows = store.get_observations(obs_type="decision")
    store.close()
    assert len(rows) == 1 and rows[0]["why"] == "chose X"


@pytest.mark.parametrize("tool", STORE_TOOLS)
def test_t4b_failed_memory_store_stays_error(tmp_path, monkeypatch, tool):
    failed = {"content": [{"type": "text", "text": "boom"}], "isError": True}
    meta = {"type": "decision", "why": "chose X"}
    store = _replay(tmp_path, monkeypatch, _store_payload(tool, meta, failed))
    assert store.get_observations(obs_type="decision") == []
    assert len(store.get_observations(obs_type="error")) == 1
    store.close()


def test_t4b_bridge_error_outranks_decision(tmp_path):
    store = KVStore(str(tmp_path / "b.db"))
    obs = ObservationBridge(kv_store=store).capture_tool_use(
        session_id="s",
        tool_name=STORE_TOOLS[0],
        tool_input={},
        tool_result="boom",
        is_error=True,
        memory_meta={"type": "decision", "why": "w"},
    )
    store.close()
    assert obs.obs_type.value == "error"


def test_t4c_secret_in_why_is_redacted(tmp_path, monkeypatch):
    secret = "sk-abcdefghijklmnopqrstuvwx"
    meta = {"type": "decision", "why": f"token={secret}"}
    store = _replay(tmp_path, monkeypatch, _store_payload(STORE_TOOLS[0], meta))
    (row,) = store.get_observations(obs_type="decision")
    store.close()
    assert secret not in row["why"] and "[REDACTED]" in row["why"]


def test_t4d_private_tags_redacted_in_any_case(tmp_path):
    from src.hooks.post_tool_handler import strip_private

    bridge = ObservationBridge(kv_store=None)

    def both(text):
        return (
            strip_private(text),
            bridge._build_content("Bash", {"command": text}, ""),
        )

    # Closed spans in any case: the span goes, the text after it stays.
    for span in (
        "<PRIVATE>a1</PRIVATE>",
        "<Private>b1</Private>",
        "<private>d1</private>",
    ):
        for out in both(f"x {span} keep"):
            assert "[REDACTED]" in out and "1" not in out and "keep" in out
    # Unclosed uppercase tag: redacted through end of text.
    for out in both("x <PRIVATE>c1 tail"):
        assert "[REDACTED]" in out and "c1" not in out and "tail" not in out


def _router_tool(seen):
    class Ingest:
        def ingest(self, text, metadata, source):
            seen.append(metadata)
            return {"success": True, "chunk_ids": ["c1"], "warnings": []}

    return SimpleNamespace(config={}, _ingestion_service=Ingest())


def test_t6a_memory_store_schema_documents_tags():
    from src.mcp.tool_registry import _memory_store_tool

    props = _memory_store_tool()["inputSchema"]["properties"]["metadata"]
    assert {"who", "when", "project", "why"} <= set(props["properties"])


def test_t6b_autofill_is_reported_in_text():
    from src.mcp.request_router import handle_memory_store

    out = handle_memory_store(
        {"text": "hello", "metadata": {"project": "x"}}, _router_tool([])
    )
    text = out["content"][0]["text"]
    assert text.startswith("Stored memory: ")
    assert "\nAuto-filled: who, when, why" in text


def test_t6b_no_autofill_line_when_all_tags_given():
    from src.mcp.request_router import handle_memory_store

    meta = {"who": "me", "when": "now", "project": "x", "why": "y"}
    out = handle_memory_store({"text": "hello", "metadata": meta}, _router_tool([]))
    assert "Auto-filled" not in out["content"][0]["text"]


def test_t10_combined_decision_store_replay(tmp_path, monkeypatch):
    from src.mcp.request_router import handle_memory_store

    belief = {"claim": "x causes y", "confidence": 0.7}
    meta = {
        "who": "me",
        "when": "now",
        "project": "p",
        "why": "chose X",
        "type": "decision",
        "beliefs": [belief],
    }
    response = [
        {
            "type": "text",
            "text": "Stored memory: x...\nAuto-filled: when\n"
            "Warning: graph not persisted; will retry on next store",
        }
    ]
    payload = _store_payload(STORE_TOOLS[0], meta, response)
    store = _replay(tmp_path, monkeypatch, payload)
    rows = store.get_observations(obs_type="decision")
    saved = store.get("last_save_at:hook-s")
    store.close()
    assert len(rows) == 1 and rows[0]["why"] == "chose X"
    assert saved

    seen = []
    out = handle_memory_store(payload["tool_input"], _router_tool(seen))
    assert out["content"][0]["text"].startswith("Stored memory: ")
    assert seen[0]["beliefs"] == [belief]
