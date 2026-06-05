"""
Unit tests for VisualMemoryService.

MEM-QWEN-006: Tests for high-level visual memory service.

Tests:
1. Initialization
2. Screenshot ingestion
3. Diagram ingestion
4. Cross-modal search
5. Metadata handling (WHO/WHEN/PROJECT/WHY)
6. Error handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
from pathlib import Path

from src.services.visual_memory_service import VisualMemoryService


class TestVisualMemoryServiceInitialization:
    """Test VisualMemoryService initialization."""

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedder."""
        embedder = Mock()
        embedder.embed_image.return_value = [0.5] * 384
        embedder.embed_text.return_value = [0.5] * 384
        embedder.embed_multimodal.return_value = [0.5] * 384
        embedder.get_info.return_value = {"model": "mock"}
        return embedder

    @pytest.fixture
    def mock_indexer(self):
        """Create mock indexer."""
        indexer = Mock()
        indexer.add_visual.return_value = "mock-doc-id"
        indexer.search.return_value = []
        indexer.count.return_value = 0
        indexer.get_info.return_value = {"collection": "mock"}
        return indexer

    def test_initialization_enabled(self, mock_embedder, mock_indexer):
        """Test service initializes enabled."""
        service = VisualMemoryService(
            embedder=mock_embedder,
            indexer=mock_indexer,
            enabled=True
        )
        assert service.enabled == True

    def test_initialization_disabled(self, mock_embedder, mock_indexer):
        """Test service initializes disabled."""
        service = VisualMemoryService(
            embedder=mock_embedder,
            indexer=mock_indexer,
            enabled=False
        )
        assert service.enabled == False

    def test_visual_types_constant(self, mock_embedder, mock_indexer):
        """Test VISUAL_TYPES constant."""
        service = VisualMemoryService(
            embedder=mock_embedder,
            indexer=mock_indexer
        )
        assert "screenshot" in service.VISUAL_TYPES
        assert "diagram" in service.VISUAL_TYPES
        assert "photo" in service.VISUAL_TYPES


class TestVisualMemoryServiceIngestion:
    """Test ingestion methods."""

    @pytest.fixture
    def service(self):
        """Create service with mocks."""
        embedder = Mock()
        embedder.embed_image.return_value = [0.5] * 384
        embedder.embed_multimodal.return_value = [0.5] * 384

        indexer = Mock()
        indexer.add_visual.return_value = "generated-doc-id"

        return VisualMemoryService(
            embedder=embedder,
            indexer=indexer,
            enabled=True
        )

    @pytest.fixture
    def temp_image(self):
        """Create temporary image file."""
        temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp.write(b"fake image data")
        temp.close()
        yield temp.name
        try:
            Path(temp.name).unlink()
        except:
            pass

    def test_ingest_screenshot_success(self, service, temp_image):
        """Test successful screenshot ingestion."""
        result = service.ingest_screenshot(
            image_path=temp_image,
            title="Test Screenshot",
            context="A test screenshot"
        )

        assert result["success"] == True
        assert "doc_id" in result
        assert result["visual_type"] == "screenshot"

    def test_ingest_diagram_success(self, service, temp_image):
        """Test successful diagram ingestion."""
        result = service.ingest_diagram(
            image_path=temp_image,
            title="Test Diagram",
            context="Architecture diagram"
        )

        assert result["success"] == True
        assert result["visual_type"] == "diagram"

    def test_ingest_visual_generic(self, service, temp_image):
        """Test generic visual ingestion."""
        result = service.ingest_visual(
            image_path=temp_image,
            visual_type="chart",
            title="Test Chart"
        )

        assert result["success"] == True
        assert result["visual_type"] == "chart"

    def test_ingest_file_not_found(self, service):
        """Test ingestion with nonexistent file."""
        result = service.ingest_screenshot(
            image_path="/nonexistent/path/image.png",
            title="Test"
        )

        assert result["success"] == False
        assert "not found" in result["error"].lower()

    def test_ingest_disabled_service(self, temp_image):
        """Test ingestion when service disabled."""
        service = VisualMemoryService(
            embedder=Mock(),
            indexer=Mock(),
            enabled=False
        )

        result = service.ingest_screenshot(image_path=temp_image)

        assert result["success"] == False
        assert "disabled" in result["error"].lower()

    def test_ingest_uses_multimodal_with_context(self, service, temp_image):
        """Test that context triggers multimodal embedding."""
        service.ingest_screenshot(
            image_path=temp_image,
            title="Test",
            context="With context"
        )

        service.embedder.embed_multimodal.assert_called_once()
        service.embedder.embed_image.assert_not_called()

    def test_ingest_uses_image_without_context(self, service, temp_image):
        """Test that no context uses image-only embedding."""
        service.ingest_screenshot(
            image_path=temp_image,
            title="Test",
            context=""
        )

        service.embedder.embed_image.assert_called_once()

    def test_ingest_returns_timing(self, service, temp_image):
        """Test that ingestion returns timing info."""
        result = service.ingest_screenshot(image_path=temp_image)

        assert "embed_time_ms" in result

    def test_ingest_invalid_visual_type_falls_back(self, service, temp_image):
        """Test invalid visual type falls back to 'other'."""
        result = service.ingest_visual(
            image_path=temp_image,
            visual_type="invalid_type"
        )

        assert result["success"] == True
        assert result["visual_type"] == "other"


class TestVisualMemoryServiceMetadata:
    """Test metadata handling."""

    @pytest.fixture
    def service(self):
        """Create service with mocks."""
        embedder = Mock()
        embedder.embed_image.return_value = [0.5] * 384

        indexer = Mock()
        indexer.add_visual.return_value = "doc-id"

        return VisualMemoryService(
            embedder=embedder,
            indexer=indexer,
            enabled=True
        )

    @pytest.fixture
    def temp_image(self):
        """Create temporary image file."""
        temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp.write(b"fake image data")
        temp.close()
        yield temp.name
        try:
            Path(temp.name).unlink()
        except:
            pass

    def test_metadata_includes_who_when_project_why(self, service, temp_image):
        """Test default WHO/WHEN/PROJECT/WHY tagging."""
        service.ingest_screenshot(image_path=temp_image, title="Test")

        call_args = service.indexer.add_visual.call_args
        metadata = call_args.kwargs.get('metadata', call_args[1] if len(call_args) > 1 else {})

        # Check for WHO (agent)
        assert "agent.name" in metadata or any("agent" in str(k) for k in metadata.keys())
        # Check for WHEN (created_at)
        assert "created_at" in metadata
        # Check for PROJECT
        assert "project" in metadata
        # Check for WHY (intent)
        assert "intent" in metadata

    def test_metadata_preserves_custom_values(self, service, temp_image):
        """Test custom metadata is preserved."""
        service.ingest_screenshot(
            image_path=temp_image,
            title="Test",
            metadata={"custom_key": "custom_value"}
        )

        call_args = service.indexer.add_visual.call_args
        metadata = call_args.kwargs.get('metadata', {})

        assert "custom_key" in metadata
        assert metadata["custom_key"] == "custom_value"

    def test_metadata_includes_visual_type(self, service, temp_image):
        """Test metadata includes visual_type."""
        service.ingest_screenshot(image_path=temp_image)

        call_args = service.indexer.add_visual.call_args
        metadata = call_args.kwargs.get('metadata', {})

        assert "visual_type" in metadata
        assert metadata["visual_type"] == "screenshot"


class TestVisualMemoryServiceSearch:
    """Test search operations."""

    @pytest.fixture
    def service(self):
        """Create service with mocks."""
        embedder = Mock()
        embedder.embed_text.return_value = [0.5] * 384

        indexer = Mock()
        indexer.search.return_value = [
            {"id": "doc-1", "score": 0.9, "metadata": {"visual_type": "screenshot"}},
            {"id": "doc-2", "score": 0.8, "metadata": {"visual_type": "diagram"}},
        ]

        return VisualMemoryService(
            embedder=embedder,
            indexer=indexer,
            enabled=True
        )

    def test_search_visual_returns_results(self, service):
        """Test search returns results."""
        results = service.search_visual(query="test query", top_k=10)

        assert len(results) == 2

    def test_search_visual_passes_top_k(self, service):
        """Test search passes top_k to indexer."""
        service.search_visual(query="test", top_k=5)

        service.indexer.search.assert_called_once()
        call_args = service.indexer.search.call_args
        assert call_args.kwargs.get('top_k') == 5

    def test_search_visual_with_type_filter(self, service):
        """Test search with visual type filter."""
        service.search_visual(query="test", visual_type="screenshot")

        call_args = service.indexer.search.call_args
        assert call_args.kwargs.get('where') == {"visual_type": "screenshot"}

    def test_search_visual_disabled_returns_empty(self):
        """Test disabled service returns empty list."""
        service = VisualMemoryService(
            embedder=Mock(),
            indexer=Mock(),
            enabled=False
        )

        results = service.search_visual(query="test")

        assert results == []

    def test_search_visual_embedding_failure_returns_empty(self):
        """Test embedding failure returns empty list."""
        embedder = Mock()
        embedder.embed_text.return_value = [0.0] * 384  # Zero embedding

        service = VisualMemoryService(
            embedder=embedder,
            indexer=Mock(),
            enabled=True
        )

        results = service.search_visual(query="test")

        assert results == []


class TestVisualMemoryServiceHelpers:
    """Test helper methods."""

    @pytest.fixture
    def service(self):
        """Create service with mocks."""
        embedder = Mock()
        embedder.get_info.return_value = {"model": "mock"}

        indexer = Mock()
        indexer.count.return_value = 10
        indexer.get_info.return_value = {"collection": "mock"}
        indexer.get_by_id.return_value = {"id": "doc-1", "metadata": {}}
        indexer.delete.return_value = True

        return VisualMemoryService(
            embedder=embedder,
            indexer=indexer,
            enabled=True
        )

    def test_get_visual(self, service):
        """Test get_visual delegates to indexer."""
        result = service.get_visual("doc-1")

        service.indexer.get_by_id.assert_called_once_with("doc-1")
        assert result["id"] == "doc-1"

    def test_delete_visual(self, service):
        """Test delete_visual delegates to indexer."""
        result = service.delete_visual("doc-1")

        service.indexer.delete.assert_called_once_with("doc-1")
        assert result == True

    def test_get_stats(self, service):
        """Test get_stats returns statistics."""
        stats = service.get_stats()

        assert "enabled" in stats
        assert "total_visuals" in stats
        assert "embedder" in stats
        assert "indexer" in stats
        assert "visual_types" in stats

        assert stats["enabled"] == True
        assert stats["total_visuals"] == 10
