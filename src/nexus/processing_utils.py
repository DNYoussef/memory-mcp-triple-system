"""
Processing Utilities: Helper functions for NexusProcessor.

Extracted from processor.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict, Any, Optional
import numpy as np
from loguru import logger


class ProcessingUtilsMixin:
    """
    Mixin providing utility methods for NexusProcessor.

    Requires:
        - self.embedding_pipeline (optional, for cosine similarity)
    """

    def _get_mode_config(self, mode: str) -> Dict[str, int]:
        """Get mode-specific core/extended split configuration."""
        configs = {
            "execution": {"core_k": 5, "extended_k": 0},
            "planning": {"core_k": 5, "extended_k": 15},
            "brainstorming": {"core_k": 5, "extended_k": 25}
        }
        return configs.get(mode, configs["execution"])

    def _split_core_extended(self, results: List[Dict], config: Dict) -> tuple:
        """Split results into core and extended."""
        core = results[:config["core_k"]]
        extended = results[config["core_k"]:config["core_k"] + config["extended_k"]]
        return core, extended

    def _finalize_compression(
        self,
        core: List[Dict],
        extended: List[Dict],
        all_results: List[Dict],
        mode: str,
        budget: int
    ) -> Dict[str, Any]:
        """Finalize compression with budget enforcement and metrics."""
        # Enforce token budget
        total_tokens, truncated = self._enforce_token_budget(core, extended, budget)

        if truncated:
            extended = truncated
            total_tokens = sum(len(r.get("text", "").split()) for r in core + extended)

        # Calculate compression ratio
        original = sum(len(r.get("text", "").split()) for r in all_results)
        ratio = total_tokens / original if original > 0 else 1.0

        logger.info(
            f"Compressed {len(all_results)} -> {len(core) + len(extended)} "
            f"({ratio:.1%}, {total_tokens} tokens)"
        )

        return {
            "core": core,
            "extended": extended,
            "token_count": total_tokens,
            "compression_ratio": ratio,
            "mode": mode
        }

    def _calculate_cosine_similarity(self, text1: str, text2: str) -> float:
        """
        B3.2 FIX: Calculate cosine similarity between two texts.

        Uses embedding-based cosine similarity when pipeline available,
        falls back to word-based Jaccard for offline mode.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Cosine similarity (0-1)

        NASA Rule 10: 30 LOC
        """
        if not text1 or not text2:
            return 0.0

        # Use embeddings for accurate cosine similarity
        if self.embedding_pipeline is not None:
            try:
                emb1 = self.embedding_pipeline.encode_single(text1)
                emb2 = self.embedding_pipeline.encode_single(text2)

                # Actual cosine similarity: dot(a,b) / (|a| * |b|)
                dot_product = np.dot(emb1, emb2)
                norm1 = np.linalg.norm(emb1)
                norm2 = np.linalg.norm(emb2)

                if norm1 > 0 and norm2 > 0:
                    return float(dot_product / (norm1 * norm2))
                return 0.0
            except Exception as e:
                logger.debug(f"Embedding similarity failed, using Jaccard: {e}")

        # Fallback: Jaccard similarity (offline mode)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _enforce_token_budget(
        self,
        core: List[Dict[str, Any]],
        extended: List[Dict[str, Any]],
        token_budget: int
    ) -> tuple:
        """
        Enforce token budget by truncating extended.

        Args:
            core: Core results (never truncated)
            extended: Extended results (truncate if needed)
            token_budget: Maximum tokens

        Returns:
            (total_tokens, truncated_extended)
        """
        # Calculate core tokens (never truncated)
        core_tokens = sum(len(r.get("text", "").split()) for r in core)

        if core_tokens >= token_budget:
            logger.warning(
                f"Core alone exceeds budget ({core_tokens} > {token_budget})"
            )
            return core_tokens, []

        # Calculate available budget for extended
        available = token_budget - core_tokens
        extended_tokens = 0
        truncated = []

        for result in extended:
            result_tokens = len(result.get("text", "").split())

            if extended_tokens + result_tokens <= available:
                truncated.append(result)
                extended_tokens += result_tokens
            else:
                logger.debug(
                    f"Truncated extended at {len(truncated)} results "
                    f"(budget exceeded)"
                )
                break

        total_tokens = core_tokens + extended_tokens
        return total_tokens, truncated

    def _empty_result(self, mode: str) -> Dict[str, Any]:
        """
        Return empty result structure.

        Args:
            mode: Query mode

        Returns:
            Empty result dict
        """
        return {
            "core": [],
            "extended": [],
            "token_count": 0,
            "compression_ratio": 0.0,
            "mode": mode,
            "pipeline_stats": {},
            "total_ms": 0
        }
