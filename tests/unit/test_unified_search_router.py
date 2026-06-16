"""
Unit tests for UnifiedSearchRouter.

MEM-QWEN-006: Tests for unified text+visual search routing.

Tests:
1. Initialization
2. Unified search
3. Text-only search
4. Visual-only search
5. Result merging and weighting
6. Error handling
"""

import pytest
from unittest.mock import Mock

from src.services.unified_search_router import UnifiedSearchRouter


class TestUnifiedSearchRouterInitialization:
    """Test UnifiedSearchRouter initialization."""

    @pytest.fixture
    def mock_nexus(self):
        """Create mock NexusProcessor."""
        nexus = Mock()
        nexus.process.return_value = {
            "core": [{"text": "text result", "score": 0.9}],
            "extended": [],
        }
        return nexus

    @pytest.fixture
    def mock_visual_service(self):
        """Create mock VisualMemoryService."""
        service = Mock()
        service.enabled = True
        service.search_visual.return_value = [
            {"id": "visual-1", "score": 0.8, "metadata": {"visual_type": "screenshot"}}
        ]
        service.get_stats.return_value = {"enabled": True, "total_visuals": 5}
        return service

    def test_initialization_default_weights(self, mock_nexus):
        """Test default weights."""
        router = UnifiedSearchRouter(nexus_processor=mock_nexus)

        assert router.text_weight == 0.7
        assert router.visual_weight == 0.3

    def test_initialization_custom_weights(self, mock_nexus):
        """Test custom weights."""
        router = UnifiedSearchRouter(
            nexus_processor=mock_nexus, visual_weight=0.5, text_weight=0.5
        )

        assert router.text_weight == 0.5
        assert router.visual_weight == 0.5

    def test_initialization_without_visual_service(self, mock_nexus):
        """Test initialization without visual service."""
        router = UnifiedSearchRouter(nexus_processor=mock_nexus)

        assert router.visual_service is None

    def test_initialization_with_visual_service(self, mock_nexus, mock_visual_service):
        """Test initialization with visual service."""
        router = UnifiedSearchRouter(
            nexus_processor=mock_nexus, visual_memory_service=mock_visual_service
        )

        assert router.visual_service is mock_visual_service


class TestUnifiedSearchRouterSearch:
    """Test unified search method."""

    @pytest.fixture
    def router(self):
        """Create router with mocks."""
        nexus = Mock()
        nexus.process.return_value = {
            "core": [
                {"text": "text result 1", "score": 0.9},
                {"text": "text result 2", "score": 0.7},
            ],
            "extended": [],
        }

        visual_service = Mock()
        visual_service.enabled = True
        visual_service.search_visual.return_value = [
            {"id": "visual-1", "score": 0.85, "metadata": {"visual_type": "screenshot"}}
        ]

        return UnifiedSearchRouter(
            nexus_processor=nexus,
            visual_memory_service=visual_service,
            visual_weight=0.3,
            text_weight=0.7,
        )

    def test_search_returns_all_sections(self, router):
        """Test search returns all result sections."""
        results = router.search(query="test", mode="execution")

        assert "query" in results
        assert "mode" in results
        assert "text_results" in results
        assert "visual_results" in results
        assert "unified_results" in results
        assert "stats" in results

    def test_search_includes_text_results(self, router):
        """Test search includes text results."""
        results = router.search(query="test")

        assert len(results["text_results"]) == 2

    def test_search_includes_visual_results(self, router):
        """Test search includes visual results."""
        results = router.search(query="test")

        assert len(results["visual_results"]) == 1

    def test_search_unified_merges_results(self, router):
        """Test unified results merge text and visual."""
        results = router.search(query="test")

        # Should have both text and visual in unified
        sources = [r["source"] for r in results["unified_results"]]
        assert "text" in sources
        assert "visual" in sources

    def test_search_applies_weights(self, router):
        """Test search applies weights to scores."""
        results = router.search(query="test")

        for result in results["unified_results"]:
            if result["source"] == "text":
                # Original score * text_weight
                assert result["score"] == result["original_score"] * 0.7
            elif result["source"] == "visual":
                # Original score * visual_weight
                assert result["score"] == result["original_score"] * 0.3

    def test_search_sorts_by_weighted_score(self, router):
        """Test unified results are sorted by weighted score."""
        results = router.search(query="test")

        scores = [r["score"] for r in results["unified_results"]]
        assert scores == sorted(scores, reverse=True)

    def test_search_text_only(self, router):
        """Test search with include_visual=False."""
        results = router.search(query="test", include_visual=False)

        assert len(results["text_results"]) > 0
        assert len(results["visual_results"]) == 0

    def test_search_visual_only(self, router):
        """Test search with include_text=False."""
        results = router.search(query="test", include_text=False)

        assert len(results["text_results"]) == 0
        assert len(results["visual_results"]) > 0

    def test_search_respects_top_k(self, router):
        """Test search respects top_k limit."""
        results = router.search(query="test", top_k=2)

        assert len(results["unified_results"]) <= 2

    def test_search_includes_stats(self, router):
        """Test search includes statistics."""
        results = router.search(query="test")

        assert "text_count" in results["stats"]
        assert "visual_count" in results["stats"]
        assert "unified_count" in results["stats"]


class TestUnifiedSearchRouterTextOnlySearch:
    """Test text-only search method."""

    @pytest.fixture
    def router(self):
        """Create router with mock nexus."""
        nexus = Mock()
        nexus.process.return_value = {
            "core": [{"text": "result", "score": 0.9}],
            "extended": [],
        }

        return UnifiedSearchRouter(nexus_processor=nexus)

    def test_search_text_only_method(self, router):
        """Test search_text_only method."""
        results = router.search_text_only(query="test", mode="execution")

        assert len(results) == 1
        assert results[0]["text"] == "result"

    def test_search_text_only_passes_mode(self, router):
        """Test search_text_only passes mode to processor."""
        router.search_text_only(query="test", mode="planning")

        router.nexus_processor.process.assert_called_once()
        call_args = router.nexus_processor.process.call_args
        assert call_args.kwargs.get("mode") == "planning"


class TestUnifiedSearchRouterVisualOnlySearch:
    """Test visual-only search method."""

    @pytest.fixture
    def router_with_visual(self):
        """Create router with visual service."""
        nexus = Mock()

        visual_service = Mock()
        visual_service.enabled = True
        visual_service.search_visual.return_value = [{"id": "visual-1", "score": 0.8}]

        return UnifiedSearchRouter(
            nexus_processor=nexus, visual_memory_service=visual_service
        )

    @pytest.fixture
    def router_without_visual(self):
        """Create router without visual service."""
        return UnifiedSearchRouter(nexus_processor=Mock())

    def test_search_visual_only_method(self, router_with_visual):
        """Test search_visual_only method."""
        results = router_with_visual.search_visual_only(query="test")

        assert len(results) == 1

    def test_search_visual_only_with_type_filter(self, router_with_visual):
        """Test search_visual_only with type filter."""
        router_with_visual.search_visual_only(query="test", visual_type="screenshot")

        router_with_visual.visual_service.search_visual.assert_called_once()
        call_args = router_with_visual.visual_service.search_visual.call_args
        assert call_args.kwargs.get("visual_type") == "screenshot"

    def test_search_visual_only_without_service(self, router_without_visual):
        """Test search_visual_only without visual service returns empty."""
        results = router_without_visual.search_visual_only(query="test")

        assert results == []

    def test_search_visual_only_disabled_service(self):
        """Test search_visual_only with disabled service returns empty."""
        visual_service = Mock()
        visual_service.enabled = False

        router = UnifiedSearchRouter(
            nexus_processor=Mock(), visual_memory_service=visual_service
        )

        results = router.search_visual_only(query="test")

        assert results == []


class TestUnifiedSearchRouterHelpers:
    """Test helper methods."""

    @pytest.fixture
    def router_with_visual(self):
        """Create router with visual service."""
        visual_service = Mock()
        visual_service.enabled = True
        visual_service.get_stats.return_value = {"total": 10}

        return UnifiedSearchRouter(
            nexus_processor=Mock(),
            visual_memory_service=visual_service,
            visual_weight=0.3,
            text_weight=0.7,
        )

    @pytest.fixture
    def router_without_visual(self):
        """Create router without visual service."""
        return UnifiedSearchRouter(nexus_processor=Mock())

    def test_get_info_with_visual(self, router_with_visual):
        """Test get_info with visual service."""
        info = router_with_visual.get_info()

        assert info["text_weight"] == 0.7
        assert info["visual_weight"] == 0.3
        assert info["visual_enabled"] is True
        assert info["visual_stats"] is not None

    def test_get_info_without_visual(self, router_without_visual):
        """Test get_info without visual service."""
        info = router_without_visual.get_info()

        assert info["visual_enabled"] is False
        assert info["visual_stats"] is None

    def test_visual_available_true(self, router_with_visual):
        """Test _visual_available returns True when available."""
        assert router_with_visual._visual_available() is True

    def test_visual_available_false_no_service(self, router_without_visual):
        """Test _visual_available returns False without service."""
        assert router_without_visual._visual_available() is False

    def test_visual_available_false_disabled(self):
        """Test _visual_available returns False when disabled."""
        visual_service = Mock()
        visual_service.enabled = False

        router = UnifiedSearchRouter(
            nexus_processor=Mock(), visual_memory_service=visual_service
        )

        assert router._visual_available() is False


class TestUnifiedSearchRouterMergeResults:
    """Test result merging logic."""

    @pytest.fixture
    def router(self):
        """Create basic router."""
        return UnifiedSearchRouter(
            nexus_processor=Mock(), visual_weight=0.3, text_weight=0.7
        )

    def test_merge_empty_lists(self, router):
        """Test merging empty lists."""
        result = router._merge_results([], [], top_k=10)

        assert result == []

    def test_merge_text_only(self, router):
        """Test merging with only text results."""
        text_results = [{"text": "a", "score": 0.9}]

        result = router._merge_results(text_results, [], top_k=10)

        assert len(result) == 1
        assert result[0]["source"] == "text"

    def test_merge_visual_only(self, router):
        """Test merging with only visual results."""
        visual_results = [{"id": "v1", "score": 0.8}]

        result = router._merge_results([], visual_results, top_k=10)

        assert len(result) == 1
        assert result[0]["source"] == "visual"

    def test_merge_applies_weights(self, router):
        """Test weights are applied during merge."""
        text_results = [{"text": "a", "score": 1.0}]
        visual_results = [{"id": "v1", "score": 1.0}]

        result = router._merge_results(text_results, visual_results, top_k=10)

        text_item = next(r for r in result if r["source"] == "text")
        visual_item = next(r for r in result if r["source"] == "visual")

        assert text_item["score"] == 0.7  # 1.0 * 0.7
        assert visual_item["score"] == 0.3  # 1.0 * 0.3

    def test_merge_sorts_descending(self, router):
        """Test merged results sorted by score descending."""
        text_results = [{"text": "low", "score": 0.3}, {"text": "high", "score": 0.9}]
        visual_results = [{"id": "v1", "score": 0.5}]

        result = router._merge_results(text_results, visual_results, top_k=10)

        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_merge_respects_top_k(self, router):
        """Test merge respects top_k limit."""
        text_results = [{"text": f"t{i}", "score": 0.9} for i in range(5)]
        visual_results = [{"id": f"v{i}", "score": 0.8} for i in range(5)]

        result = router._merge_results(text_results, visual_results, top_k=3)

        assert len(result) == 3


class TestUnifiedSearchRouterErrorHandling:
    """Test error handling."""

    def test_text_search_error_returns_empty(self):
        """Test text search error returns empty list."""
        nexus = Mock()
        nexus.process.side_effect = Exception("Text search failed")

        router = UnifiedSearchRouter(nexus_processor=nexus)

        results = router._search_text("test", "execution", 10)

        assert results == []

    def test_visual_search_error_returns_empty(self):
        """Test visual search error returns empty list."""
        visual_service = Mock()
        visual_service.enabled = True
        visual_service.search_visual.side_effect = Exception("Visual search failed")

        router = UnifiedSearchRouter(
            nexus_processor=Mock(), visual_memory_service=visual_service
        )

        results = router._search_visual("test", 10)

        assert results == []
