"""
Integration tests for mode detection.
MEM-CLEAN-007: Core path verification.

Tests the 3-mode classification system:
- Execution mode (5K tokens): "What is X?", "define", "explain"
- Planning mode (10K tokens): "How should", "design", "strategy"
- Brainstorming mode (20K tokens): "What if", "imagine", "explore"

NASA Rule 10 Compliant: All test methods <=60 LOC
"""
import pytest

from src.mcp.request_router import handle_detect_mode


class MockTool:
    """Minimal mock for mode detection (no services needed)."""

    pass


@pytest.fixture
def mock_tool():
    return MockTool()


class TestExecutionModeDetection:
    """Test execution mode patterns."""

    @pytest.mark.parametrize(
        "query,expected_mode",
        [
            ("What is ChromaDB?", "execution"),
            ("Define vector search", "execution"),
            ("Explain the Nexus processor", "execution"),
            ("Show me the config file", "execution"),
            ("Find all Python files", "execution"),
            ("Get the current status", "execution"),
        ],
    )
    def test_execution_patterns(self, mock_tool, query, expected_mode):
        """Execution patterns should detect execution mode."""
        result = handle_detect_mode({"query": query}, mock_tool)
        assert not result.get("isError", False)
        response_text = result["content"][0]["text"]
        assert expected_mode in response_text.lower()


class TestPlanningModeDetection:
    """Test planning mode patterns."""

    @pytest.mark.parametrize(
        "query,expected_mode",
        [
            ("How should I implement caching?", "planning"),
            ("What approach works best for indexing?", "planning"),
            ("Design a new retrieval pipeline", "planning"),
            ("Plan the migration strategy", "planning"),
            ("Recommend a solution for latency", "planning"),
        ],
    )
    def test_planning_patterns(self, mock_tool, query, expected_mode):
        """Planning patterns should detect planning mode."""
        result = handle_detect_mode({"query": query}, mock_tool)
        assert not result.get("isError", False)
        response_text = result["content"][0]["text"]
        assert expected_mode in response_text.lower()


class TestBrainstormingModeDetection:
    """Test brainstorming mode patterns."""

    @pytest.mark.parametrize(
        "query,expected_mode",
        [
            ("What if we used a different database?", "brainstorming"),
            ("Imagine we had unlimited compute", "brainstorming"),
            ("Explore alternative architectures", "brainstorming"),
            ("Could we use neural networks instead?", "brainstorming"),
            ("Ideas for improving search quality", "brainstorming"),
            ("Possibilities for scaling the system", "brainstorming"),
        ],
    )
    def test_brainstorming_patterns(self, mock_tool, query, expected_mode):
        """Brainstorming patterns should detect brainstorming mode."""
        result = handle_detect_mode({"query": query}, mock_tool)
        assert not result.get("isError", False)
        response_text = result["content"][0]["text"]
        assert expected_mode in response_text.lower()


class TestModeConfidence:
    """Test confidence scoring."""

    def test_clear_pattern_high_confidence(self, mock_tool):
        """Clear patterns should have high confidence."""
        result = handle_detect_mode({"query": "What is X?"}, mock_tool)
        response_text = result["content"][0]["text"]
        # Should mention confidence
        assert "confidence" in response_text.lower()
        assert "85%" in response_text or "0.85" in response_text

    def test_ambiguous_query_lower_confidence(self, mock_tool):
        """Ambiguous queries should have lower confidence."""
        result = handle_detect_mode({"query": "stuff about things"}, mock_tool)
        response_text = result["content"][0]["text"]
        # Should default to execution with lower confidence
        assert "execution" in response_text.lower()
        assert "50%" in response_text or "0.5" in response_text


class TestModeTokenBudgets:
    """Verify mode-specific token budget logic exists."""

    def test_mode_config_exists_in_processor(self):
        """NexusProcessor should have mode configuration."""
        from src.nexus.processing_utils import ProcessingUtilsMixin

        class TestProcessor(ProcessingUtilsMixin):
            pass

        processor = TestProcessor()
        for mode in ["execution", "planning", "brainstorming"]:
            config = processor._get_mode_config(mode)
            assert "core_k" in config
            assert "extended_k" in config
            assert config["core_k"] == 5  # Always 5 core

    def test_execution_mode_has_smallest_extended(self):
        """Execution mode should have smallest extended set."""
        from src.nexus.processing_utils import ProcessingUtilsMixin

        class TestProcessor(ProcessingUtilsMixin):
            pass

        processor = TestProcessor()
        exec_config = processor._get_mode_config("execution")
        plan_config = processor._get_mode_config("planning")
        brain_config = processor._get_mode_config("brainstorming")

        assert exec_config["extended_k"] <= plan_config["extended_k"]
        assert plan_config["extended_k"] <= brain_config["extended_k"]
