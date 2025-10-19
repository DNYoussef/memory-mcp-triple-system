"""
Unit tests for Error Attribution.

Tests error classification logic:
- Context bugs (wrong store, wrong mode, wrong lifecycle)
- Model bugs (correct context, wrong output)
- System errors (timeout, exception)
"""

import pytest
from unittest.mock import Mock
from src.debug.error_attribution import (
    ErrorAttribution,
    ErrorType,
    ContextBugType
)


class MockQueryTrace:
    """Mock QueryTrace for testing."""

    def __init__(
        self,
        query: str,
        stores_queried=None,
        mode_detected=None,
        error=None,
        error_type=None,
        output=None
    ):
        self.query = query
        self.stores_queried = stores_queried or []
        self.mode_detected = mode_detected
        self.error = error
        self.error_type = error_type
        self.output = output


class TestErrorAttribution:
    """Test suite for ErrorAttribution class."""

    @pytest.fixture
    def attribution(self):
        """Create ErrorAttribution instance."""
        return ErrorAttribution()

    def test_classify_wrong_store(self, attribution):
        """Test classifying wrong store queried."""
        # "What's my X?" should use KV, not vector
        trace = MockQueryTrace(
            query="What's my coding style?",
            stores_queried=["vector"],  # Wrong! Should be KV
            error="Not found"
        )

        error_type = attribution.classify_failure(trace)
        context_bug_type = attribution.classify_context_bug(trace)

        assert error_type == ErrorType.CONTEXT_BUG
        assert context_bug_type == ContextBugType.WRONG_STORE_QUERIED

    def test_classify_wrong_mode(self, attribution):
        """Test classifying wrong mode detected."""
        # Query with "P(" should be planning mode, not execution
        trace = MockQueryTrace(
            query="P(bug|change)?",
            mode_detected="execution",  # Wrong! Should be planning
            stores_queried=["vector", "hipporag"],
            error="Verification failed"
        )

        error_type = attribution.classify_failure(trace)
        context_bug_type = attribution.classify_context_bug(trace)

        assert error_type == ErrorType.CONTEXT_BUG
        assert context_bug_type == ContextBugType.WRONG_MODE_DETECTED

    def test_classify_model_bug(self, attribution):
        """Test classifying model bug (correct context, wrong output)."""
        # Correct store and mode, but wrong output
        trace = MockQueryTrace(
            query="What is NASA Rule 10?",
            stores_queried=["vector", "hipporag"],  # Correct
            mode_detected="execution",  # Correct
            output="NASA Rule 10 is about testing",  # Wrong (model error)
            error="Output incorrect"
        )

        error_type = attribution.classify_failure(trace)

        assert error_type == ErrorType.MODEL_BUG  # Not context bug

    def test_classify_system_error(self, attribution):
        """Test classifying system error (timeout)."""
        trace = MockQueryTrace(
            query="What is NASA Rule 10?",
            stores_queried=["vector"],
            error="timeout: Query took >1s"  # System error
        )

        error_type = attribution.classify_failure(trace)

        assert error_type == ErrorType.SYSTEM_ERROR

    def test_get_statistics(self, attribution):
        """Test error statistics aggregation."""
        stats = attribution.get_statistics(days=30)

        # Should return statistics structure
        assert "total_queries" in stats
        assert "failed_queries" in stats
        assert "failure_breakdown" in stats
        assert "context_bug_breakdown" in stats

        # Breakdown should have all categories
        assert "context_bugs" in stats["failure_breakdown"]
        assert "model_bugs" in stats["failure_breakdown"]
        assert "system_errors" in stats["failure_breakdown"]

        # Context bug breakdown
        assert "wrong_store_queried" in stats["context_bug_breakdown"]
        assert "wrong_mode_detected" in stats["context_bug_breakdown"]
        assert "wrong_lifecycle_filter" in stats["context_bug_breakdown"]
        assert "retrieval_ranking_error" in stats["context_bug_breakdown"]

    def test_wrong_store_detection_kv(self, attribution):
        """Test detection of queries that should use KV store."""
        # "What's my X?" pattern should use KV
        test_cases = [
            "What's my coding style?",
            "What is my name?",
            "Whats my email?"
        ]

        for query in test_cases:
            trace = MockQueryTrace(query=query, stores_queried=["vector"])
            assert attribution._is_wrong_store(trace), f"Should detect wrong store for: {query}"

    def test_wrong_store_detection_vector(self, attribution):
        """Test detection of queries that should use vector store."""
        # "What about X?" pattern should use vector
        test_cases = [
            "What about machine learning?",
            "What about NASA Rule 10?"
        ]

        for query in test_cases:
            trace = MockQueryTrace(query=query, stores_queried=["kv"])
            assert attribution._is_wrong_store(trace), f"Should detect wrong store for: {query}"

    def test_wrong_mode_detection_planning(self, attribution):
        """Test detection of planning queries in wrong mode."""
        # Queries with "P(" notation should be planning mode
        test_cases = [
            "P(bug|feature change)?",
            "what is p(success)?"
        ]

        for query in test_cases:
            trace = MockQueryTrace(query=query, mode_detected="execution")
            assert attribution._is_wrong_mode(trace), f"Should detect wrong mode for: {query}"

    def test_correct_classification(self, attribution):
        """Test queries with correct routing."""
        # KV query with KV store
        trace = MockQueryTrace(
            query="What's my coding style?",
            stores_queried=["kv"],
            mode_detected="execution"
        )
        assert not attribution._is_wrong_store(trace)

        # Vector query with vector store
        trace2 = MockQueryTrace(
            query="What about NASA Rule 10?",
            stores_queried=["vector"],
            mode_detected="execution"
        )
        assert not attribution._is_wrong_store(trace2)

    def test_pre_classified_error(self, attribution):
        """Test handling of pre-classified errors."""
        trace = MockQueryTrace(
            query="test",
            error_type="context_bug"
        )

        error_type = attribution.classify_failure(trace)
        assert error_type == ErrorType.CONTEXT_BUG

    def test_empty_statistics_without_db(self, attribution):
        """Test statistics return empty structure without database."""
        stats = attribution.get_statistics(days=7)

        # Should return structure with zeros
        assert stats["total_queries"] == 0
        assert stats["failed_queries"] == 0
        assert stats["failure_breakdown"]["context_bugs"] == 0
