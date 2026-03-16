"""
Embedding Pipeline -- auto-selects API or local model.

Set EMBEDDING_MODE=api to use OpenAI/LiteLLM API embeddings (no local model).
Set EMBEDDING_MODE=local (default) to use sentence-transformers locally.

API mode saves ~500MB Docker image and ~256MB RAM.
"""

import os
from typing import List
import numpy as np
from loguru import logger

EMBEDDING_MODE = os.environ.get("EMBEDDING_MODE", "local")


class EmbeddingPipeline:
    """Generates embeddings -- API or local, same interface."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if len(model_name) == 0:
            raise ValueError("Model name cannot be empty")

        self.model_name = model_name
        self._api_mode = EMBEDDING_MODE == "api"

        if self._api_mode:
            from .embedding_pipeline_api import EmbeddingPipelineAPI
            api_model = os.environ.get("EMBEDDING_API_MODEL", "text-embedding-3-small")
            api_dim = int(os.environ.get("EMBEDDING_API_DIMENSIONS", "384"))
            self._delegate = EmbeddingPipelineAPI(
                model_name=api_model,
                dimensions=api_dim,
            )
            self.embedding_dim = api_dim
            logger.info(f"Embedding mode: API ({api_model}, dim={api_dim})")
        else:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            self._delegate = None
            logger.info(f"Embedding mode: local ({model_name}, dim={self.embedding_dim})")

    def encode(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        if len(texts) == 0:
            raise ValueError("Cannot encode empty list")
        if not all(len(t) > 0 for t in texts):
            raise ValueError("Texts cannot be empty")

        if self._delegate:
            return self._delegate.encode(texts)

        embeddings = self.model.encode(
            texts,
            show_progress_bar=len(texts) > 10,
            convert_to_numpy=True,
        )
        logger.debug(f"Encoded {len(texts)} texts")
        return embeddings

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Batch alias for encode."""
        return self.encode(texts)

    def encode_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text."""
        if len(text) == 0:
            raise ValueError("Text cannot be empty")

        if self._delegate:
            return self._delegate.encode_single(text)

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding
