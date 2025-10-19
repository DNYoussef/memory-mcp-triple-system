"""
Unit tests for RAPTOR Hierarchical Clusterer.

Week 9 component - Tests GMM clustering, BIC validation, hierarchy building.

Target: 10 tests, ~100 LOC
"""

import pytest
import numpy as np
from src.clustering.raptor_clusterer import RAPTORClusterer


class TestRAPTORClusterer:
    """Test suite for RAPTORClusterer."""

    @pytest.fixture
    def clusterer(self):
        """Create RAPTORClusterer instance."""
        return RAPTORClusterer(min_clusters=2, max_clusters=5)

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for testing."""
        return [
            {"text": "Python programming language"},
            {"text": "Machine learning algorithms"},
            {"text": "JavaScript web development"},
            {"text": "Deep learning neural networks"},
            {"text": "React frontend framework"},
        ]

    @pytest.fixture
    def sample_embeddings(self):
        """Create sample embeddings (2 distinct clusters)."""
        return [
            [0.1, 0.2, 0.3, 0.4],  # Cluster 1
            [0.15, 0.25, 0.35, 0.45],  # Cluster 1
            [0.5, 0.6, 0.7, 0.8],  # Cluster 2
            [0.12, 0.22, 0.32, 0.42],  # Cluster 1
            [0.55, 0.65, 0.75, 0.85],  # Cluster 2
        ]

    def test_initialization(self, clusterer):
        """Test RAPTORClusterer initialization."""
        assert clusterer.min_clusters == 2
        assert clusterer.max_clusters == 5
        assert clusterer.bic_threshold == -1000.0
        assert clusterer.random_state == 42

    def test_cluster_chunks_creates_clusters(
        self, clusterer, sample_chunks, sample_embeddings
    ):
        """Test that cluster_chunks creates valid clusters."""
        result = clusterer.cluster_chunks(sample_chunks, sample_embeddings)

        assert result["num_clusters"] >= 2
        assert result["num_clusters"] <= 5
        assert len(result["cluster_assignments"]) == 5
        assert len(result["cluster_summaries"]) == result["num_clusters"]
        assert 0 <= result["quality_score"] <= 1.0
        assert result["bic_score"] < 0  # BIC is negative

    def test_cluster_chunks_quality_score(
        self, clusterer, sample_chunks, sample_embeddings
    ):
        """Test that clustering achieves good quality score."""
        result = clusterer.cluster_chunks(sample_chunks, sample_embeddings)

        # Should achieve good separation with 2 distinct clusters
        assert result["quality_score"] > 0.5  # Reasonable quality
        assert result["num_clusters"] == 2  # Should detect 2 clusters

    def test_cluster_chunks_empty_input(self, clusterer):
        """Test cluster_chunks with empty input."""
        result = clusterer.cluster_chunks([], [])

        assert result["num_clusters"] == 0
        assert result["cluster_assignments"] == []
        assert result["cluster_summaries"] == []
        assert result["quality_score"] == 0.0
        assert result["bic_score"] == 0.0

    def test_build_hierarchy_creates_tree(self, clusterer, sample_chunks, sample_embeddings):
        """Test that build_hierarchy creates valid tree structure."""
        clusters = clusterer.cluster_chunks(sample_chunks, sample_embeddings)
        hierarchy = clusterer.build_hierarchy(clusters, max_depth=3)

        assert hierarchy["level"] == 0
        assert "summary" in hierarchy
        assert hierarchy["num_nodes"] == clusters["num_clusters"]
        assert len(hierarchy["children"]) == clusters["num_clusters"]

    def test_build_hierarchy_single_cluster(self, clusterer):
        """Test hierarchy building with single cluster."""
        clusters = {
            "num_clusters": 1,
            "cluster_summaries": ["Single summary"],
        }

        hierarchy = clusterer.build_hierarchy(clusters)

        assert hierarchy["level"] == 0
        assert hierarchy["summary"] == "Single summary"
        assert hierarchy["num_nodes"] == 1
        assert hierarchy["children"] == []

    def test_build_hierarchy_empty_clusters(self, clusterer):
        """Test hierarchy building with empty clusters."""
        clusters = {"cluster_summaries": []}
        hierarchy = clusterer.build_hierarchy(clusters)

        assert hierarchy["level"] == 0
        assert hierarchy["summary"] == ""
        assert hierarchy["num_nodes"] == 0
        assert hierarchy["children"] == []

    def test_select_optimal_clusters_range(self, clusterer):
        """Test that optimal cluster selection respects min/max range."""
        # Create embeddings with 3 clear clusters
        X = np.array([
            [0.1, 0.2],
            [0.15, 0.25],
            [0.5, 0.6],
            [0.55, 0.65],
            [0.9, 0.95],
            [0.85, 0.9],
        ])

        optimal_k = clusterer._select_optimal_clusters(X)

        assert optimal_k >= clusterer.min_clusters
        assert optimal_k <= clusterer.max_clusters

    def test_generate_summary_truncates(self, clusterer):
        """Test that summary generation truncates long text."""
        long_texts = ["A" * 100, "B" * 100, "C" * 100]
        summary = clusterer._generate_summary(long_texts)

        # Should truncate to 200 chars + "..."
        assert len(summary) <= 203  # 200 + "..."
        assert "..." in summary or len(summary) == 200

    def test_generate_summary_empty(self, clusterer):
        """Test summary generation with empty input."""
        summary = clusterer._generate_summary([])
        assert summary == ""


# NASA Rule 10 Compliance Check
def test_nasa_rule_10_compliance():
    """Verify all RAPTORClusterer methods are ≤60 LOC."""
    import ast

    with open("src/clustering/raptor_clusterer.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = node.end_lineno - node.lineno + 1
            assert func_lines <= 60, f"{node.name} exceeds 60 LOC ({func_lines})"
