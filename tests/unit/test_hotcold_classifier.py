"""
Unit tests for Hot/Cold Classifier.

Week 9 component - Tests lifecycle classification, storage savings.

Target: 7 tests, ~70 LOC
"""

import pytest
from datetime import datetime, timedelta
from src.lifecycle.hotcold_classifier import HotColdClassifier, LifecycleStage


class TestHotColdClassifier:
    """Test suite for HotColdClassifier."""

    @pytest.fixture
    def classifier(self):
        """Create HotColdClassifier instance."""
        return HotColdClassifier(
            active_days=7, demoted_days=30, access_threshold=3
        )

    def test_initialization(self, classifier):
        """Test HotColdClassifier initialization."""
        assert classifier.active_days == 7
        assert classifier.demoted_days == 30
        assert classifier.access_threshold == 3

    def test_classify_chunk_active(self, classifier):
        """Test classification of active chunk."""
        now = datetime.now()
        stage = classifier.classify_chunk(
            chunk_id="chunk-1",
            created_at=now - timedelta(days=3),
            last_accessed=now,
            access_count=10,
        )

        assert stage == LifecycleStage.ACTIVE

    def test_classify_chunk_demoted(self, classifier):
        """Test classification of demoted chunk."""
        now = datetime.now()
        stage = classifier.classify_chunk(
            chunk_id="chunk-2",
            created_at=now - timedelta(days=15),
            last_accessed=now - timedelta(days=5),
            access_count=2,
        )

        assert stage == LifecycleStage.DEMOTED

    def test_classify_chunk_archived(self, classifier):
        """Test classification of archived chunk."""
        now = datetime.now()
        stage = classifier.classify_chunk(
            chunk_id="chunk-3",
            created_at=now - timedelta(days=60),
            last_accessed=now - timedelta(days=30),
            access_count=1,
        )

        assert stage == LifecycleStage.ARCHIVED

    def test_classify_batch(self, classifier):
        """Test batch classification of multiple chunks."""
        now = datetime.now()
        chunks = [
            {
                "chunk_id": "chunk-1",
                "created_at": now - timedelta(days=3),
                "last_accessed": now,
                "access_count": 10,
            },
            {
                "chunk_id": "chunk-2",
                "created_at": now - timedelta(days=20),
                "last_accessed": now - timedelta(days=10),
                "access_count": 2,
            },
        ]

        classifications = classifier.classify_batch(chunks)

        assert len(classifications) == 2
        assert classifications["chunk-1"] == LifecycleStage.ACTIVE
        assert classifications["chunk-2"] == LifecycleStage.DEMOTED

    def test_get_indexing_strategy_active(self, classifier):
        """Test indexing strategy for active chunks."""
        strategy = classifier.get_indexing_strategy(LifecycleStage.ACTIVE)

        # get_indexing_strategy returns {"vector": ..., "graph": ..., "relational": ...}
        assert strategy["vector"] is True
        assert strategy["graph"] is True
        assert strategy["relational"] is True

    def test_calculate_storage_savings(self, classifier):
        """Test storage savings calculation."""
        classifications = {
            "chunk-1": LifecycleStage.ACTIVE,
            "chunk-2": LifecycleStage.DEMOTED,
            "chunk-3": LifecycleStage.ARCHIVED,
        }

        savings = classifier.calculate_storage_savings(classifications)

        assert savings["total_chunks"] == 3
        assert savings["active"] == 1
        assert savings["demoted"] == 1
        assert savings["archived"] == 1
        assert savings["vector_index_reduction"] > 0  # Should save some


# NASA Rule 10 Compliance Check
def test_nasa_rule_10_compliance():
    """Verify all HotColdClassifier methods are ≤60 LOC."""
    import ast

    with open("src/lifecycle/hotcold_classifier.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = node.end_lineno - node.lineno + 1
            assert func_lines <= 60, f"{node.name} exceeds 60 LOC ({func_lines})"
