"""
Integration tests for VectorIndexer metadata filtering.
Tests ChromaDB metadata query capabilities with real vector operations.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.indexing.vector_indexer import VectorIndexer


class TestVectorIndexerIntegration:
    """Integration test suite for VectorIndexer metadata filtering."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for ChromaDB."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        # Cleanup
        try:
            shutil.rmtree(temp_path)
        except Exception:
            pass

    @pytest.fixture
    def indexer(self, temp_dir):
        """Create indexer instance with temporary ChromaDB directory."""
        indexer = VectorIndexer(
            persist_directory=temp_dir,
            collection_name="test_integration"
        )
        indexer.create_collection(vector_size=384)
        yield indexer
        # Cleanup
        try:
            indexer.client.delete_collection("test_integration")
        except Exception:
            pass

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks with varied metadata."""
        return [
            {
                'text': 'Document about Python programming',
                'file_path': '/docs/python/intro.md',
                'chunk_index': 0,
                'metadata': {'language': 'Python', 'topic': 'programming', 'level': 1}
            },
            {
                'text': 'Advanced Python concepts',
                'file_path': '/docs/python/advanced.md',
                'chunk_index': 0,
                'metadata': {'language': 'Python', 'topic': 'programming', 'level': 3}
            },
            {
                'text': 'JavaScript fundamentals',
                'file_path': '/docs/javascript/basics.md',
                'chunk_index': 0,
                'metadata': {'language': 'JavaScript', 'topic': 'programming', 'level': 1}
            },
            {
                'text': 'Database design patterns',
                'file_path': '/docs/database/patterns.md',
                'chunk_index': 0,
                'metadata': {'language': 'SQL', 'topic': 'database', 'level': 2}
            },
            {
                'text': 'More Python content',
                'file_path': '/docs/python/intro.md',
                'chunk_index': 1,
                'metadata': {'language': 'Python', 'topic': 'programming', 'level': 1}
            }
        ]

    @pytest.fixture
    def sample_embeddings(self):
        """Create sample embeddings (384-dimensional)."""
        # Create varied embeddings for different content
        return [
            [0.1] * 384,  # Python intro
            [0.2] * 384,  # Python advanced
            [0.3] * 384,  # JavaScript
            [0.4] * 384,  # Database
            [0.15] * 384  # More Python
        ]

    def test_metadata_filtering_exact_match(
        self,
        indexer,
        sample_chunks,
        sample_embeddings
    ):
        """Test filtering by exact metadata value."""
        # Index sample chunks
        indexer.index_chunks(sample_chunks, sample_embeddings)

        # Search with exact file_path filter
        query_emb = [0.12] * 384  # Similar to Python content
        results = indexer.search_similar(
            query_embedding=query_emb,
            top_k=5,
            where={"file_path": "/docs/python/intro.md"}
        )

        # Verify only matching chunks returned
        assert len(results) == 2  # Two chunks from intro.md
        for result in results:
            assert result['metadata']['file_path'] == "/docs/python/intro.md"

    def test_metadata_filtering_comparison(
        self,
        indexer,
        sample_chunks,
        sample_embeddings
    ):
        """Test filtering with comparison operators ($gte, $lt)."""
        # Index sample chunks
        indexer.index_chunks(sample_chunks, sample_embeddings)

        # Search for level >= 2
        query_emb = [0.2] * 384
        results = indexer.search_similar(
            query_embedding=query_emb,
            top_k=5,
            where={"level": {"$gte": 2}}
        )

        # Verify all results have level >= 2
        assert len(results) >= 2
        for result in results:
            assert result['metadata']['level'] >= 2

    def test_metadata_filtering_logical_and(
        self,
        indexer,
        sample_chunks,
        sample_embeddings
    ):
        """Test combining multiple conditions with $and."""
        # Index sample chunks
        indexer.index_chunks(sample_chunks, sample_embeddings)

        # Search for Python AND level 1
        query_emb = [0.1] * 384
        results = indexer.search_similar(
            query_embedding=query_emb,
            top_k=5,
            where={
                "$and": [
                    {"language": "Python"},
                    {"level": 1}
                ]
            }
        )

        # Verify all results match both conditions
        assert len(results) >= 1
        for result in results:
            assert result['metadata']['language'] == "Python"
            assert result['metadata']['level'] == 1

    def test_metadata_filtering_logical_or(
        self,
        indexer,
        sample_chunks,
        sample_embeddings
    ):
        """Test combining conditions with $or."""
        # Index sample chunks
        indexer.index_chunks(sample_chunks, sample_embeddings)

        # Search for language = Python OR JavaScript
        query_emb = [0.2] * 384
        results = indexer.search_similar(
            query_embedding=query_emb,
            top_k=5,
            where={
                "$or": [
                    {"language": "Python"},
                    {"language": "JavaScript"}
                ]
            }
        )

        # Verify all results are either Python or JavaScript
        assert len(results) >= 3
        for result in results:
            assert result['metadata']['language'] in ["Python", "JavaScript"]

    def test_metadata_filtering_with_search(
        self,
        indexer,
        sample_chunks,
        sample_embeddings
    ):
        """Test combining metadata filter with vector similarity search."""
        # Index sample chunks
        indexer.index_chunks(sample_chunks, sample_embeddings)

        # Search for Python content with similarity to advanced topics
        query_emb = [0.2] * 384  # Close to advanced Python embedding
        results_filtered = indexer.search_similar(
            query_embedding=query_emb,
            top_k=3,
            where={"language": "Python"}
        )

        # Search without filter for comparison
        results_unfiltered = indexer.search_similar(
            query_embedding=query_emb,
            top_k=3
        )

        # Verify filtered results are subset and all Python
        assert len(results_filtered) <= len(results_unfiltered)
        for result in results_filtered:
            assert result['metadata']['language'] == "Python"

        # Verify similarity ordering (first result should be closest)
        if len(results_filtered) >= 2:
            assert results_filtered[0]['distance'] <= results_filtered[1]['distance']
