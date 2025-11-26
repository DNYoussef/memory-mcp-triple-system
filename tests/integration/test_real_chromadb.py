"""
Real ChromaDB Integration Tests (ISS-047)
Tests vector operations with real ChromaDB instead of mocks.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.fixtures.real_services import (
    temp_data_dir, real_chromadb_client, real_embedding_pipeline,
    real_vector_indexer, sample_documents, indexed_documents
)


class TestVectorIndexerRealChromaDB:
    """Test VectorIndexer with real ChromaDB."""

    def test_add_document_persists_to_chromadb(self, real_vector_indexer, real_embedding_pipeline):
        """Verify documents are actually persisted to ChromaDB."""
        # Add a document using index_chunks API
        text = "Test document for ChromaDB"
        embedding = real_embedding_pipeline.encode([text])[0]

        chunk = {
            "text": text,
            "file_path": "/test/doc.md",
            "chunk_index": 0,
            "metadata": {"source": "test"}
        }
        real_vector_indexer.index_chunks([chunk], [embedding.tolist()])

        # Verify it exists
        count = real_vector_indexer.collection.count()
        assert count >= 1, "Document not persisted to ChromaDB"

    def test_search_returns_similar_documents(self, indexed_documents, real_embedding_pipeline):
        """Test semantic search returns relevant results."""
        query = "What is NASA Rule 10?"
        query_embedding = real_embedding_pipeline.encode([query])[0]

        results = indexed_documents.search_similar(
            query_embedding=query_embedding,
            top_k=3
        )

        assert len(results) > 0, "No search results returned"
        # First result should be about NASA rules
        assert "NASA" in results[0].get("document", "") or results[0].get("distance", 1) < 0.5

    def test_delete_document_removes_from_chromadb(self, real_vector_indexer, real_embedding_pipeline):
        """Verify document deletion works."""
        # Add then delete using index_chunks API
        text = "Document to delete"
        embedding = real_embedding_pipeline.encode([text])[0]

        chunk = {
            "text": text,
            "file_path": "/test/delete.md",
            "chunk_index": 0,
            "metadata": {}
        }
        real_vector_indexer.index_chunks([chunk], [embedding.tolist()])

        initial_count = real_vector_indexer.collection.count()
        # Get the IDs from collection and delete one
        all_ids = real_vector_indexer.collection.get()["ids"]
        if all_ids:
            real_vector_indexer.delete_chunks([all_ids[0]])
        final_count = real_vector_indexer.collection.count()

        assert final_count == initial_count - 1

    def test_embedding_dimensions_match(self, real_embedding_pipeline):
        """Verify embeddings have correct dimensions."""
        text = "Test text"
        embedding = real_embedding_pipeline.encode([text])[0]

        # all-MiniLM-L6-v2 produces 384-dim embeddings
        assert len(embedding) == 384, f"Expected 384 dims, got {len(embedding)}"

    def test_batch_indexing(self, real_vector_indexer, real_embedding_pipeline, sample_documents):
        """Test batch document indexing."""
        texts = [doc["text"] for doc in sample_documents[:3]]
        embeddings = real_embedding_pipeline.encode(texts)

        # Create chunks for batch indexing
        chunks = []
        for i, text in enumerate(texts):
            chunks.append({
                "text": text,
                "file_path": f"/test/batch_{i}.md",
                "chunk_index": i,
                "metadata": {"batch": True}
            })

        # Index all at once using batch API
        real_vector_indexer.index_chunks(chunks, embeddings.tolist())

        count = real_vector_indexer.collection.count()
        assert count >= 3


class TestVectorSearchToolRealChromaDB:
    """Test VectorSearchTool with real ChromaDB."""

    def test_execute_returns_real_results(self, indexed_documents, real_embedding_pipeline, temp_data_dir):
        """Test VectorSearchTool.execute() with real data."""
        from src.mcp.tools.vector_search import VectorSearchTool

        config = {
            "embeddings": {"model": "all-MiniLM-L6-v2"},
            "storage": {
                "vector_db": {
                    "persist_directory": str(temp_data_dir / "vector_test"),
                    "collection_name": "test_collection"
                }
            }
        }

        tool = VectorSearchTool(config)
        tool._indexer = indexed_documents  # Use pre-indexed data
        tool._embedder = real_embedding_pipeline

        results = tool.execute("What is ChromaDB?", limit=3)

        assert len(results) > 0, "VectorSearchTool returned no results"
        assert "text" in results[0] or "score" in results[0]
