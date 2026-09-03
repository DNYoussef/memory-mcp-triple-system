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
