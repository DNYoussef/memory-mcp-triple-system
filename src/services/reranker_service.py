"""
Cross-Encoder Reranker Service for Memory MCP.

MEM-QWEN-002: Adds precision refinement as Step 4.5 in NexusProcessor.
Uses cross-encoder models for query-document pair scoring.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import os
import sys
import io
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from loguru import logger

# Fix Windows encoding issues before importing sentence_transformers
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"
os.environ["WANDB_DISABLED"] = "true"
os.environ["WANDB_MODE"] = "disabled"
os.environ["WANDB_SILENT"] = "true"


class RerankerService:
    """
    Cross-encoder reranker for precision refinement.

    Scores query-document pairs using cross-attention for more accurate
    relevance ranking than bi-encoder similarity.

    Default model: cross-encoder/ms-marco-MiniLM-L-6-v2 (~22M params, ~400MB)
    """

    # Supported models (smaller to larger)
    MODELS = {
        "small": "cross-encoder/ms-marco-MiniLM-L-6-v2",  # 22M params, fastest
        "medium": "cross-encoder/ms-marco-MiniLM-L-12-v2",  # 33M params
        "large": "BAAI/bge-reranker-v2-m3",  # 568M params, best quality
    }

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_size: str = "small",
        device: Optional[str] = None,
        max_length: int = 512,
        batch_size: int = 32,
        enabled: bool = True
    ):
        """
        Initialize reranker service.

        Args:
            model_name: HuggingFace model name (overrides model_size)
            model_size: "small", "medium", or "large"
            device: "cuda" or "cpu" (auto-detect if None)
            max_length: Max tokens per document (truncate longer)
            batch_size: Batch size for inference
            enabled: Enable/disable reranking (for A/B testing)
        """
        self.model_name = model_name or self.MODELS.get(model_size, self.MODELS["small"])
        self.max_length = max_length
        self.batch_size = batch_size
        self.enabled = enabled
        self._model = None
        self._device = device

        logger.info(f"RerankerService initialized: model={self.model_name}, enabled={enabled}")

    @property
    def device(self) -> str:
        """Get device (lazy detection)."""
        if self._device is None:
            try:
                import torch
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"
        return self._device

    @property
    def model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None and self.enabled:
            self._model = self._load_model()
        return self._model

    def _load_model(self):
        """Load cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading cross-encoder: {self.model_name}")
            start = time.time()

            model = CrossEncoder(
                self.model_name,
                max_length=self.max_length,
                device=self.device
            )

            load_time = time.time() - start
            logger.info(f"Cross-encoder loaded in {load_time:.2f}s (device={self.device})")
            return model

        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")
            self.enabled = False
            return None

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 30
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Rerank documents using cross-encoder scoring.

        Args:
            query: Query text
            documents: List of documents with "text" and "id" keys
            top_k: Number of top results to return

        Returns:
            Tuple of (reranked documents, stats dict)
        """
        stats = {"rerank_enabled": self.enabled}

        if not self.enabled or not documents:
            stats["rerank_skipped"] = True
            return documents[:top_k], stats

        if self.model is None:
            logger.warning("Reranker model not loaded, skipping rerank")
            stats["rerank_skipped"] = True
            return documents[:top_k], stats

        start = time.time()

        # Prepare pairs for cross-encoder
        texts = [self._get_text(doc) for doc in documents]
        pairs = [(query, text) for text in texts]

        # Score with cross-encoder
        try:
            scores = self.model.predict(pairs, show_progress_bar=False)
        except Exception as e:
            logger.error(f"Rerank inference failed: {e}")
            stats["rerank_error"] = str(e)
            return documents[:top_k], stats

        # Attach scores and sort
        scored_docs = []
        for doc, score in zip(documents, scores):
            doc_copy = dict(doc)
            doc_copy["rerank_score"] = float(score)
            scored_docs.append(doc_copy)

        # Sort by rerank score (descending)
        scored_docs.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

        stats["rerank_ms"] = int((time.time() - start) * 1000)
        stats["rerank_input_count"] = len(documents)
        stats["rerank_output_count"] = min(top_k, len(scored_docs))
        stats["rerank_top_score"] = scored_docs[0]["rerank_score"] if scored_docs else 0.0

        logger.info(
            f"Rerank: {len(documents)} -> {stats['rerank_output_count']} "
            f"in {stats['rerank_ms']}ms (top_score={stats['rerank_top_score']:.2f})"
        )

        return scored_docs[:top_k], stats

    def _get_text(self, doc: Dict[str, Any]) -> str:
        """Extract text from document, truncating if needed."""
        text = doc.get("text", doc.get("document", ""))
        # Truncate to prevent excessive processing
        if len(text) > 2000:
            text = text[:2000]
        return text

    def merge_scores(
        self,
        documents: List[Dict[str, Any]],
        hybrid_weight: float = 0.5,
        rerank_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Merge hybrid scores with rerank scores.

        Args:
            documents: Documents with both hybrid_score and rerank_score
            hybrid_weight: Weight for original hybrid score
            rerank_weight: Weight for rerank score

        Returns:
            Documents with merged final_score
        """
        for doc in documents:
            hybrid = doc.get("hybrid_score", doc.get("score", 0.0))
            rerank = doc.get("rerank_score", 0.0)

            hybrid_normalized = max(0.0, min(1.0, float(hybrid)))
            # Normalize rerank score to 0-1 range (cross-encoder outputs unbounded)
            rerank_normalized = self._sigmoid(rerank)

            doc["final_score"] = hybrid_weight * hybrid_normalized + rerank_weight * rerank_normalized
            doc["score"] = doc["final_score"]
            doc["score_breakdown"] = doc.get("score_breakdown", {})
            doc["score_breakdown"]["hybrid"] = hybrid_normalized
            doc["score_breakdown"]["rerank"] = rerank

        # Re-sort by final score
        documents.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return documents

    def _sigmoid(self, x: float) -> float:
        """Sigmoid normalization for unbounded scores."""
        import math
        try:
            return 1 / (1 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    def is_available(self) -> bool:
        """Check if reranker is available and enabled."""
        return self.enabled and self.model is not None

    def get_info(self) -> Dict[str, Any]:
        """Get reranker service info."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "enabled": self.enabled,
            "available": self.is_available(),
            "max_length": self.max_length,
            "batch_size": self.batch_size
        }
