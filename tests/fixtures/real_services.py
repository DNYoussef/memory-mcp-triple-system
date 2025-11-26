"""
Real Service Fixtures for Integration Tests (ISS-047)

Provides fixtures that use real ChromaDB, NetworkX, and embedding models
instead of mocks. These enable true integration testing.

Usage:
    from tests.fixtures.real_services import (
        real_chromadb_client,
        real_vector_indexer,
        real_graph_service,
        real_embedding_pipeline
    )
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator, List, Dict, Any


# Sample test documents for indexing
SAMPLE_DOCUMENTS = [
    {
        "text": "NASA Rule 10 states that all functions must be 60 lines or less. This promotes readable and maintainable code.",
        "metadata": {"file_path": "/docs/nasa_rules.md", "chunk_index": 0, "topic": "coding_standards"}
    },
    {
        "text": "Memory MCP Triple System uses a three-tier architecture: Vector, Graph, and Bayesian for intelligent retrieval.",
        "metadata": {"file_path": "/docs/architecture.md", "chunk_index": 0, "topic": "architecture"}
    },
    {
        "text": "ChromaDB is a vector database that enables semantic similarity search using embeddings.",
        "metadata": {"file_path": "/docs/chromadb.md", "chunk_index": 0, "topic": "database"}
    },
    {
        "text": "HippoRAG combines hippocampal indexing theory with retrieval-augmented generation for better context.",
        "metadata": {"file_path": "/docs/hipporag.md", "chunk_index": 0, "topic": "retrieval"}
    },
    {
        "text": "Bayesian networks enable probabilistic reasoning over uncertain relationships in knowledge graphs.",
        "metadata": {"file_path": "/docs/bayesian.md", "chunk_index": 0, "topic": "inference"}
    }
]


@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """Create temporary directory for test data."""
    temp_dir = Path(tempfile.mkdtemp(prefix="memory_mcp_test_"))
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def real_chromadb_client(temp_data_dir: Path):
    """
    Real ChromaDB client with ephemeral storage.

    Uses temporary directory that's cleaned up after test.
    """
    import chromadb

    persist_dir = temp_data_dir / "chroma_test"
    persist_dir.mkdir(parents=True, exist_ok=True)

    # Use new PersistentClient API (ChromaDB 0.4+)
    client = chromadb.PersistentClient(path=str(persist_dir))

    yield client

    # Cleanup
    try:
        client.reset()
    except Exception:
        pass


@pytest.fixture
def real_embedding_pipeline():
    """
    Real EmbeddingPipeline with sentence-transformers.

    Uses a small model for fast test execution.
    """
    from src.indexing.embedding_pipeline import EmbeddingPipeline

    # Use small model for tests
    pipeline = EmbeddingPipeline(model_name="all-MiniLM-L6-v2")
    return pipeline


@pytest.fixture
def real_vector_indexer(temp_data_dir: Path):
    """
    Real VectorIndexer with ephemeral ChromaDB collection.
    """
    from src.indexing.vector_indexer import VectorIndexer

    persist_dir = temp_data_dir / "vector_test"
    persist_dir.mkdir(parents=True, exist_ok=True)

    indexer = VectorIndexer(
        persist_directory=str(persist_dir),
        collection_name="test_collection"
    )

    yield indexer

    # Cleanup
    try:
        indexer.client.reset()
    except Exception:
        pass


@pytest.fixture
def real_graph_service(temp_data_dir: Path):
    """
    Real GraphService with NetworkX graph.
    """
    from src.services.graph_service import GraphService

    data_dir = temp_data_dir / "graph_test"
    data_dir.mkdir(parents=True, exist_ok=True)

    service = GraphService(data_dir=str(data_dir))
    return service


@pytest.fixture
def real_graph_query_engine(real_graph_service):
    """
    Real GraphQueryEngine with NetworkX backend.
    """
    from src.services.graph_query_engine import GraphQueryEngine

    engine = GraphQueryEngine(graph_service=real_graph_service)
    return engine


@pytest.fixture
def sample_documents() -> List[Dict[str, Any]]:
    """Sample documents for testing."""
    return SAMPLE_DOCUMENTS.copy()


@pytest.fixture
def indexed_documents(real_vector_indexer, real_embedding_pipeline, sample_documents):
    """
    Fixture that indexes sample documents and returns the indexer.

    Use this when you need pre-indexed data for search tests.
    """
    # Transform sample_documents to chunk format expected by index_chunks
    chunks = []
    for i, doc in enumerate(sample_documents):
        chunks.append({
            "text": doc["text"],
            "file_path": doc["metadata"].get("file_path", f"/test/doc_{i}.md"),
            "chunk_index": i,
            "metadata": doc["metadata"]
        })

    # Generate embeddings
    texts = [chunk["text"] for chunk in chunks]
    embeddings = real_embedding_pipeline.encode(texts)

    # Index chunks using batch API
    real_vector_indexer.index_chunks(chunks, embeddings.tolist())

    return real_vector_indexer


@pytest.fixture
def populated_graph(real_graph_service, sample_documents):
    """
    Fixture that populates graph with entities from sample documents.
    """
    # Add entities and relationships
    entities = [
        ("NASA Rule 10", "concept"),
        ("Memory MCP", "system"),
        ("ChromaDB", "database"),
        ("HippoRAG", "algorithm"),
        ("Bayesian", "method"),
        ("Vector", "tier"),
        ("Graph", "tier"),
    ]

    for entity, entity_type in entities:
        real_graph_service.add_entity(entity, entity_type)

    # Add relationships
    relationships = [
        ("Memory MCP", "uses", "ChromaDB"),
        ("Memory MCP", "uses", "HippoRAG"),
        ("Memory MCP", "uses", "Bayesian"),
        ("Memory MCP", "has_tier", "Vector"),
        ("Memory MCP", "has_tier", "Graph"),
        ("HippoRAG", "retrieves_from", "Graph"),
    ]

    for source, rel_type, target in relationships:
        real_graph_service.add_relationship(source, rel_type, target)

    return real_graph_service


@pytest.fixture
def real_nexus_processor(real_vector_indexer, real_graph_query_engine, real_embedding_pipeline):
    """
    Real NexusProcessor with all three tiers wired.
    """
    from src.nexus.processor import NexusProcessor
    from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine

    # Create Bayesian engine (no network for tests)
    bayesian_engine = ProbabilisticQueryEngine(timeout_seconds=1.0)

    processor = NexusProcessor(
        vector_indexer=real_vector_indexer,
        graph_query_engine=real_graph_query_engine,
        probabilistic_query_engine=bayesian_engine,
        embedding_pipeline=real_embedding_pipeline
    )

    return processor
