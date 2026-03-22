"""Tests for the shared MemoryIngestionService."""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from src.services.memory_ingestion_service import MemoryIngestionService


@pytest.fixture
def mock_services():
    """Create mock service dependencies."""
    embedder = MagicMock()
    embedder.encode.return_value = [np.zeros(384)]

    indexer = MagicMock()
    indexer.index_chunks.return_value = None

    graph_service = MagicMock()
    graph_service.add_chunk_node.return_value = True
    graph_service.save_graph.return_value = None

    entity_service = MagicMock()
    entity_service.add_entities_to_graph.return_value = {
        "entities_added": 3,
        "relationships_created": 3,
        "entity_types": ["PERSON", "ORG", "GPE"],
    }

    classifier = MagicMock()
    classifier.classify.return_value = {
        "tier": "hot",
        "decay_score": 1.0,
        "lifecycle_stage": "active",
    }

    lifecycle_manager = MagicMock()
    event_log = MagicMock()

    return {
        "embedder": embedder,
        "indexer": indexer,
        "graph_service": graph_service,
        "entity_service": entity_service,
        "classifier": classifier,
        "lifecycle_manager": lifecycle_manager,
        "event_log": event_log,
    }


@pytest.fixture
def service(mock_services):
    return MemoryIngestionService(**mock_services)


def test_ingest_returns_success(service):
    result = service.ingest("Test memory text", {"who": "test"})
    assert result["success"] is True
    assert result["text_length"] == 16
    assert "chunk_id" in result
    assert len(result["chunk_id"]) == 32


def test_ingest_calls_embedder(service, mock_services):
    service.ingest("Hello world", {})
    mock_services["embedder"].encode.assert_called_once_with(["Hello world"])


def test_ingest_calls_indexer_with_chunk_id(service, mock_services):
    result = service.ingest("Test text", {})
    call_args = mock_services["indexer"].index_chunks.call_args
    chunk = call_args[0][0][0]
    assert chunk["id"] == result["chunk_id"]
    assert chunk["text"] == "Test text"


def test_ingest_calls_graph_population(service, mock_services):
    result = service.ingest("David built GuardSpine", {})
    mock_services["graph_service"].add_chunk_node.assert_called_once()
    mock_services["entity_service"].add_entities_to_graph.assert_called_once()
    mock_services["graph_service"].save_graph.assert_called_once()
    assert result["entities"]["entities_added"] == 3


def test_ingest_calls_classifier(service, mock_services):
    result = service.ingest("Important data", {})
    mock_services["classifier"].classify.assert_called_once()
    assert result["lifecycle_tier"] == "hot"


def test_ingest_calls_lifecycle_maintenance(service, mock_services):
    service.ingest("Some text", {})
    mock_services["lifecycle_manager"].demote_stale_chunks.assert_called_once()
    mock_services["lifecycle_manager"].archive_demoted_chunks.assert_called_once()


def test_ingest_graceful_without_entity_service(mock_services):
    """Entity extraction failure should not break ingestion."""
    mock_services["entity_service"] = None
    svc = MemoryIngestionService(**mock_services)
    result = svc.ingest("No entities here", {})
    assert result["success"] is True
    assert result["entities"]["entities_added"] == 0


def test_ingest_graceful_without_classifier(mock_services):
    """Missing classifier defaults to hot tier."""
    mock_services["classifier"] = None
    svc = MemoryIngestionService(**mock_services)
    result = svc.ingest("Unclassified", {})
    assert result["success"] is True
    assert result["lifecycle_tier"] == "hot"


def test_chunk_id_is_deterministic(service):
    """Same input + timestamp produces same chunk_id."""
    id1 = MemoryIngestionService._make_chunk_id("text", "http", "2026-01-01T00:00:00")
    id2 = MemoryIngestionService._make_chunk_id("text", "http", "2026-01-01T00:00:00")
    assert id1 == id2


def test_chunk_id_differs_for_different_input(service):
    """Different text produces different chunk_id."""
    id1 = MemoryIngestionService._make_chunk_id("text1", "http", "2026-01-01T00:00:00")
    id2 = MemoryIngestionService._make_chunk_id("text2", "http", "2026-01-01T00:00:00")
    assert id1 != id2


def test_metadata_has_lifecycle_fields(service):
    """Ingested metadata must include lifecycle fields."""
    result = service.ingest("Test", {})
    meta = result["metadata"]
    assert "lifecycle_tier" in meta
    assert "decay_score" in meta
    assert "stage" in meta
    assert "last_accessed" in meta
    assert "access_count" in meta
    assert meta["access_count"] == 0
