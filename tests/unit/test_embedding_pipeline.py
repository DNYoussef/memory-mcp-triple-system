"""
Unit tests for EmbeddingPipeline
Following TDD (London School) with proper test structure.
"""

import pytest
import numpy as np
from src.indexing.embedding_pipeline import EmbeddingPipeline

# Check if model is available
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    HAS_MODEL = True
except Exception:
    HAS_MODEL = False

# Skip all tests if model not available
pytestmark = pytest.mark.skipif(
    not HAS_MODEL,
    reason="Embedding model 'sentence-transformers/all-MiniLM-L6-v2' not downloaded. "
           "Run: python -c \"from sentence_transformers import SentenceTransformer; "
           "SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')\" to download."
)


class TestEmbeddingPipeline:
    """Test suite for EmbeddingPipeline."""

    @pytest.fixture
    def pipeline(self):
        """Create embedding pipeline instance."""
        return EmbeddingPipeline(model_name="all-MiniLM-L6-v2")

    def test_initialization(self, pipeline):
        """Test pipeline initialization."""
        assert pipeline.model_name == "all-MiniLM-L6-v2"
        assert pipeline.embedding_dim == 384

    def test_encode_single_text(self, pipeline):
        """Test encoding single text."""
        text = "This is a test sentence."
        embedding = pipeline.encode_single(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

    def test_encode_multiple_texts(self, pipeline):
        """Test encoding multiple texts."""
        texts = [
            "First sentence.",
            "Second sentence.",
            "Third sentence."
        ]
        embeddings = pipeline.encode(texts)

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 384)
        assert embeddings.dtype == np.float32

    def test_encode_empty_text_raises(self, pipeline):
        """Test that encoding empty text raises error."""
        with pytest.raises(AssertionError):
            pipeline.encode_single("")

    def test_encode_empty_list_raises(self, pipeline):
        """Test that encoding empty list raises error."""
        with pytest.raises(AssertionError):
            pipeline.encode([])

    def test_encode_list_with_empty_string_raises(self, pipeline):
        """Test that list with empty strings raises error."""
        with pytest.raises(AssertionError):
            pipeline.encode(["valid text", ""])

    def test_embedding_consistency(self, pipeline):
        """Test that same text produces same embedding."""
        text = "Consistency test sentence."
        embedding1 = pipeline.encode_single(text)
        embedding2 = pipeline.encode_single(text)

        np.testing.assert_array_almost_equal(embedding1, embedding2)

    def test_different_texts_different_embeddings(self, pipeline):
        """Test that different texts produce different embeddings."""
        text1 = "First text."
        text2 = "Completely different text."

        embedding1 = pipeline.encode_single(text1)
        embedding2 = pipeline.encode_single(text2)

        # Embeddings should not be identical
        assert not np.array_equal(embedding1, embedding2)
