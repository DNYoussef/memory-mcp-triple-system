"""
API-Based Embedding Pipeline using LiteLLM/OpenRouter.
Replaces local sentence-transformers with API calls to OpenAI text-embedding-3-small.
Saves ~500MB Docker image size and ~256MB RAM.

Drop-in replacement for EmbeddingPipeline -- same interface.
"""

import os
from typing import List
import numpy as np
import urllib.request
import json
from loguru import logger


class EmbeddingPipelineAPI:
    """Generates embeddings via API instead of local model."""

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_base: str = None,
        api_key: str = None,
        dimensions: int = 384,
    ):
        self.model_name = model_name
        self.api_base = api_base or os.environ.get(
            "EMBEDDING_API_BASE",
            os.environ.get("LITELLM_BASE_URL", "https://openrouter.ai/api") + "/v1",
        )
        self.api_key = api_key or os.environ.get(
            "EMBEDDING_API_KEY",
            os.environ.get("LITELLM_API_KEY", os.environ.get("OPENROUTER_API_KEY", "")),
        )
        self.dimensions = dimensions
        self.embedding_dim = dimensions

        logger.info(
            f"API embedding: model={model_name} dim={dimensions} base={self.api_base[:40]}..."
        )

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Call embedding API and return vectors."""
        url = f"{self.api_base.rstrip('/')}/embeddings"

        payload = json.dumps({
            "model": self.model_name,
            "input": texts,
            "dimensions": self.dimensions,
            "encoding_format": "float",
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Sort by index to preserve order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for texts via API.

        Args:
            texts: List of text strings

        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        if len(texts) == 0:
            raise ValueError("Cannot encode empty list")
        if not all(len(t) > 0 for t in texts):
            raise ValueError("Texts cannot be empty")

        # Batch in chunks of 100 (API limit)
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            embeddings = self._call_api(batch)
            all_embeddings.extend(embeddings)

        logger.debug(f"Encoded {len(texts)} texts via API")
        return np.array(all_embeddings)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Alias for encode (API is already batched)."""
        return self.encode(texts)

    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text."""
        result = self.encode([text])
        return result[0]
