"""
Embedding Pipeline using Sentence-Transformers
Generates 384-dimensional embeddings for text chunks.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger


class EmbeddingPipeline:
    """Generates embeddings using Sentence-Transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding pipeline.

        Args:
            model_name: Sentence-Transformers model name
        """
        assert len(model_name) > 0, "Model name cannot be empty"

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        logger.info(
            f"Loaded model: {model_name} "
            f"(dim={self.embedding_dim})"
        )

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for texts.

        Args:
            texts: List of text strings

        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        assert len(texts) > 0, "Cannot encode empty list"
        assert all(len(t) > 0 for t in texts), "Texts cannot be empty"

        embeddings = self.model.encode(
            texts,
            show_progress_bar=len(texts) > 10,
            convert_to_numpy=True
        )

        logger.debug(f"Encoded {len(texts)} texts")
        return embeddings

    def encode_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for single text.

        Args:
            text: Text string

        Returns:
            numpy array of shape (embedding_dim,)
        """
        assert len(text) > 0, "Text cannot be empty"

        embedding = self.model.encode(
            text,
            convert_to_numpy=True
        )

        return embedding
