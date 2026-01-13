"""
Phase 5 Integration Tests - Algorithm Fixes Validation

Tests that algorithm fixes are properly implemented:
1. B3.1: Similarity scores in [0, 1] range
2. B3.2: Cosine similarity with embeddings
3. B3.3: Entity extraction handles multi-word entities
"""

import sys
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestB31SimilarityScores:
    """Test B3.1: Similarity scores normalized to [0, 1] range."""

    def test_vector_search_scores_normalized(self, tmp_path):
        """Verify vector search returns scores in [0, 1]."""
        from src.mcp.tools.vector_search import VectorSearchTool

        persist_dir = tmp_path / "chroma"
        persist_dir.mkdir()

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': str(persist_dir),
                    'collection_name': 'test_b31'
                }
            },
            'chunking': {'min_chunk_size': 50, 'max_chunk_size': 200}
        }

        tool = VectorSearchTool(config)

        # Index documents with varying semantic distance
        docs = [
            "Machine learning algorithms for data science",
            "Cooking recipes for pasta dishes",
            "Quantum physics and string theory",
            "Python programming best practices"
        ]

        # Use index_chunks API with proper chunk format
        chunks = [
            {'text': text, 'file_path': 'test.md', 'chunk_index': i}
            for i, text in enumerate(docs)
        ]
        embeddings = [tool.embedder.encode_single(text).tolist() for text in docs]
        tool.indexer.index_chunks(chunks, embeddings)

        # Query that's semantically distant from some docs
        results = tool.execute("machine learning python", limit=4)

        # All scores must be in [0, 1]
        for result in results:
            score = result['score']
            assert 0.0 <= score <= 1.0, f"Score {score} out of range"
            assert isinstance(score, float), "Score must be float"


class TestB32CosineSimilarity:
    """Test B3.2: Proper cosine similarity calculation."""

    def test_cosine_similarity_with_embeddings(self):
        """Verify cosine similarity uses embeddings when available."""
        from src.nexus.processor import NexusProcessor
        from src.indexing.embedding_pipeline import EmbeddingPipeline

        embedder = EmbeddingPipeline(model_name='all-MiniLM-L6-v2')
        processor = NexusProcessor(embedding_pipeline=embedder)

        # Similar texts should have high similarity
        text1 = "Machine learning is a type of artificial intelligence"
        text2 = "AI and machine learning are related technologies"
        sim_high = processor._calculate_cosine_similarity(text1, text2)

        # Dissimilar texts should have lower similarity
        text3 = "Cooking pasta requires boiling water"
        sim_low = processor._calculate_cosine_similarity(text1, text3)

        assert sim_high > sim_low, "Similar texts should score higher"
        assert 0.0 <= sim_high <= 1.0, f"High sim {sim_high} out of range"
        assert 0.0 <= sim_low <= 1.0, f"Low sim {sim_low} out of range"

    def test_cosine_similarity_fallback_jaccard(self):
        """Verify Jaccard fallback works when no embedder."""
        from src.nexus.processor import NexusProcessor

        processor = NexusProcessor()  # No embedding pipeline

        # Test with overlapping words
        text1 = "machine learning python"
        text2 = "machine learning java"
        sim = processor._calculate_cosine_similarity(text1, text2)

        # Jaccard: intersection=2, union=4 -> 0.5
        assert 0.4 <= sim <= 0.6, f"Expected ~0.5, got {sim}"


class TestB33EntityExtraction:
    """Test B3.3: Entity extraction handles multi-word entities."""

    def test_extracts_capitalized_phrases(self):
        """Verify multi-word capitalized phrases are extracted."""
        from src.nexus.processor import NexusProcessor

        processor = NexusProcessor()

        # Test with multi-word entities
        query = "What is the relationship between John Smith and New York City?"
        entity = processor._extract_query_entity(query)

        # Should extract a multi-word entity
        assert " " in entity or entity in ["John Smith", "New York City"], \
            f"Expected multi-word entity, got '{entity}'"

    def test_extracts_single_capitalized_word(self):
        """Verify single capitalized words work."""
        from src.nexus.processor import NexusProcessor

        processor = NexusProcessor()

        query = "Tell me about Microsoft and its products"
        entity = processor._extract_query_entity(query)

        assert entity == "Microsoft", f"Expected 'Microsoft', got '{entity}'"

    def test_fallback_to_first_word(self):
        """Verify fallback to first word when no capitalized words."""
        from src.nexus.processor import NexusProcessor

        processor = NexusProcessor()

        query = "what is machine learning"
        entity = processor._extract_query_entity(query)

        assert entity == "what", f"Expected 'what', got '{entity}'"

    def test_handles_empty_query(self):
        """Verify empty query returns 'unknown'."""
        from src.nexus.processor import NexusProcessor

        processor = NexusProcessor()

        assert processor._extract_query_entity("") == "unknown"
        assert processor._extract_query_entity("   ") == "unknown"


class TestVersionUpdated:
    """Test version is updated to 1.4.0."""

    def test_version_is_1_4_0(self):
        """Verify version is 1.4.0 for Phase 5."""
        from src import __version__
        assert __version__ == "1.4.0", f"Expected 1.4.0, got {__version__}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
