"""
Processing Utilities: Helper functions for NexusProcessor.

Extracted from processor.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC

MEM-CHUNK-002: Added Lost-in-the-Middle mitigation strategies.
"""

from typing import List, Dict, Any, Optional
from enum import Enum
import numpy as np
from loguru import logger


class LostInMiddleMitigation(Enum):
    """
    Lost-in-the-Middle mitigation strategies (MEM-CHUNK-002).

    NONE: No reordering, standard descending relevance.
    EDGES: High relevance at edges (start/end), medium in middle.
    INTERLEAVE: Alternate high/medium relevance throughout.
    REVERSE_MIDDLE: Highest at start, then reverse-sorted middle, highest at end.
    """
    NONE = "none"
    EDGES = "edges"
    INTERLEAVE = "interleave"
    REVERSE_MIDDLE = "reverse_middle"


class ProcessingUtilsMixin:
    """
    Mixin providing utility methods for NexusProcessor.

    Requires:
        - self.embedding_pipeline (optional, for cosine similarity)
    """

    def _calculate_hybrid_score(
        self,
        vector_score: float = 0.0,
        graph_score: float = 0.0,
        bayesian_score: float = 0.0
    ) -> float:
        """Calculate weighted hybrid score from tier scores.

        Single source of truth for the scoring formula.
        Used by both _combine_tier_scores() and rank().
        """
        return (
            self.weights.get("vector", 0.4) * vector_score +
            self.weights.get("hipporag", 0.4) * graph_score +
            self.weights.get("bayesian", 0.2) * bayesian_score
        )

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

    def apply_lost_in_middle_mitigation(
        self,
        results: List[Dict[str, Any]],
        strategy: LostInMiddleMitigation = LostInMiddleMitigation.EDGES
    ) -> List[Dict[str, Any]]:
        """
        Apply Lost-in-the-Middle mitigation reordering (MEM-CHUNK-002).

        LLMs tend to miss content in the middle of context windows.
        This method reorders results to place high-relevance content
        at positions that get more attention (start and end).

        Args:
            results: Ranked results (already sorted by relevance desc)
            strategy: Mitigation strategy to apply

        Returns:
            Reordered results with high relevance at edges

        NASA Rule 10: 35 LOC
        """
        if not results or len(results) <= 2:
            return results

        if strategy == LostInMiddleMitigation.NONE:
            return results

        if strategy == LostInMiddleMitigation.EDGES:
            return self._reorder_edges(results)

        if strategy == LostInMiddleMitigation.INTERLEAVE:
            return self._reorder_interleave(results)

        if strategy == LostInMiddleMitigation.REVERSE_MIDDLE:
            return self._reorder_reverse_middle(results)

        return results

    def _reorder_edges(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Reorder with high relevance at edges (MEM-CHUNK-002).

        Pattern: [1, 3, 5, 7, ..., 8, 6, 4, 2]
        Places odd-ranked items at start, even-ranked at end (reversed).

        NASA Rule 10: 20 LOC
        """
        n = len(results)
        reordered = []

        # First half: odd positions (0, 2, 4, ...)
        for i in range(0, n, 2):
            reordered.append(results[i])

        # Second half: even positions reversed (n-1, n-3, ...)
        for i in range(n - 1 if n % 2 == 0 else n - 2, 0, -2):
            reordered.append(results[i])

        logger.debug(f"Lost-in-middle EDGES reorder: {n} items")
        return reordered

    def _reorder_interleave(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Interleave high and medium relevance throughout (MEM-CHUNK-002).

        Pattern: [1, 6, 2, 7, 3, 8, 4, 9, 5, 10]
        Alternates between top half and bottom half.

        NASA Rule 10: 25 LOC
        """
        n = len(results)
        mid = (n + 1) // 2
        top_half = results[:mid]
        bottom_half = results[mid:]

        reordered = []
        for i in range(max(len(top_half), len(bottom_half))):
            if i < len(top_half):
                reordered.append(top_half[i])
            if i < len(bottom_half):
                reordered.append(bottom_half[i])

        logger.debug(f"Lost-in-middle INTERLEAVE reorder: {n} items")
        return reordered

    def _reorder_reverse_middle(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Keep start, reverse middle, keep end (MEM-CHUNK-002).

        Pattern: [1, 4, 3, 2, 5] for 5 items
        First stays first, last stays last, middle is reversed.
        This pushes medium relevance toward edges of the middle section.

        NASA Rule 10: 20 LOC
        """
        n = len(results)
        if n <= 3:
            return results

        first = [results[0]]
        last = [results[-1]]
        middle = results[1:-1]
        middle_reversed = list(reversed(middle))

        reordered = first + middle_reversed + last
        logger.debug(f"Lost-in-middle REVERSE_MIDDLE reorder: {n} items")
        return reordered

    def get_position_weights(
        self,
        length: int,
        edge_boost: float = 0.1
    ) -> List[float]:
        """
        Get position-based relevance weight adjustments (MEM-CHUNK-002).

        Boosts edge positions (start/end) with extra weight to
        compensate for LLM attention patterns.

        Args:
            length: Number of items
            edge_boost: Extra weight for edge positions (default 0.1 = 10%)

        Returns:
            List of position weights (1.0 base + boost for edges)

        NASA Rule 10: 20 LOC
        """
        if length == 0:
            return []

        weights = [1.0] * length

        # Boost first and last positions
        weights[0] += edge_boost
        if length > 1:
            weights[-1] += edge_boost

        # Slight boost for near-edge positions
        if length > 2:
            weights[1] += edge_boost * 0.5
            weights[-2] += edge_boost * 0.5

        return weights
