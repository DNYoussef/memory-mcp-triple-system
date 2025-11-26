"""
Nexus Processor: Unified Multi-Tier RAG Retrieval Pipeline.

Implements 5-step SOP:
1. Recall - Query all 3 tiers (Vector + HippoRAG + Bayesian)
2. Filter - Confidence threshold (>0.3)
3. Deduplicate - Cosine similarity (>0.95)
4. Rank - Weighted scoring (Vector 0.4 + HippoRAG 0.4 + Bayesian 0.2)
5. Compress - Curated core pattern (mode-aware)

NASA Rule 10 Compliant: All methods ≤60 LOC
"""

from typing import List, Dict, Any, Optional
import numpy as np
from loguru import logger


class NexusProcessor:
    """
    5-step SOP pipeline with curated core pattern.

    Steps:
    1. Recall (query all tiers, top-50 candidates)
    2. Filter (confidence >0.3)
    3. Deduplicate (cosine >0.95)
    4. Rank (weighted sum)
    5. Compress (curated core: top-5 + extended: 15-25)
    """

    def __init__(
        self,
        vector_indexer: Any = None,
        graph_query_engine: Any = None,
        probabilistic_query_engine: Any = None,
        embedding_pipeline: Any = None,
        confidence_threshold: float = 0.3,
        dedup_threshold: float = 0.95,
        weights: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Initialize Nexus Processor with all 3 tier services.

        Args:
            vector_indexer: VectorIndexer instance (Week 6)
            graph_query_engine: GraphQueryEngine instance (Week 8)
            probabilistic_query_engine: ProbabilisticQueryEngine instance (Week 10)
            embedding_pipeline: EmbeddingPipeline instance (Week 6)
            confidence_threshold: Minimum confidence for filtering (default: 0.3)
            dedup_threshold: Cosine similarity threshold for deduplication (default: 0.95)
            weights: Tier weights for ranking (default: {vector: 0.4, hipporag: 0.4, bayesian: 0.2})
        """
        self.vector_indexer = vector_indexer
        self.graph_query_engine = graph_query_engine
        self.probabilistic_query_engine = probabilistic_query_engine
        self.embedding_pipeline = embedding_pipeline
        self.confidence_threshold = confidence_threshold
        self.dedup_threshold = dedup_threshold
        self.weights = weights or {
            "vector": 0.4,
            "hipporag": 0.4,
            "bayesian": 0.2
        }

        logger.info(
            f"NexusProcessor initialized with weights: {self.weights}"
        )

    def process(
        self,
        query: str,
        mode: str = "execution",
        top_k: int = 50,
        token_budget: int = 10000
    ) -> Dict[str, Any]:
        """
        Full 5-step SOP pipeline.

        Args:
            query: User query text
            mode: execution/planning/brainstorming
            top_k: Number of candidates to recall per tier
            token_budget: Maximum tokens in final result

        Returns:
            {
                core: [top-5 chunks],
                extended: [next 15-25 chunks],
                token_count: int,
                compression_ratio: float,
                mode: str,
                pipeline_stats: {recall, filter, dedup, rank, compress times}
            }
        """
        import time
        start = time.time()

        # Execute 5-step pipeline
        result, stats = self._execute_pipeline(query, mode, top_k, token_budget)

        # Add timing metadata
        result["pipeline_stats"] = stats
        result["total_ms"] = int((time.time() - start) * 1000)

        logger.info(
            f"Pipeline complete: {result['total_ms']}ms total "
            f"({len(result['core'])} core + {len(result['extended'])} extended)"
        )

        return result

    def _execute_pipeline(
        self,
        query: str,
        mode: str,
        top_k: int,
        token_budget: int
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Execute 5-step pipeline and return result with stats."""
        import time
        stats = {}

        # Step 1: Recall
        candidates, stats = self._step_recall(query, top_k, stats)
        if not candidates:
            return self._empty_result(mode), stats

        # Step 2: Filter
        filtered, stats = self._step_filter(candidates, stats)
        if not filtered:
            return self._empty_result(mode), stats

        # Step 3-5: Deduplicate, Rank, Compress
        deduplicated, stats = self._step_deduplicate(filtered, stats)
        ranked, stats = self._step_rank(deduplicated, stats)
        result, stats = self._step_compress(ranked, mode, token_budget, stats)

        return result, stats

    def _step_recall(self, query: str, top_k: int, stats: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Step 1: Recall candidates."""
        import time
        start = time.time()
        candidates = self.recall(query, top_k=top_k)
        stats["recall_ms"] = int((time.time() - start) * 1000)
        logger.info(f"Recall: {len(candidates)} candidates in {stats['recall_ms']}ms")
        return candidates, stats

    def _step_filter(self, candidates: List[Dict[str, Any]], stats: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Step 2: Filter by confidence."""
        import time
        start = time.time()
        filtered = self.filter_by_confidence(candidates)
        stats["filter_ms"] = int((time.time() - start) * 1000)
        logger.info(f"Filter: {len(candidates)} → {len(filtered)} ({stats['filter_ms']}ms)")
        return filtered, stats

    def _step_deduplicate(self, filtered, stats):
        """Step 3: Deduplicate."""
        import time
        start = time.time()
        deduplicated = self.deduplicate(filtered)
        stats["dedup_ms"] = int((time.time() - start) * 1000)
        logger.info(f"Deduplicate: {len(filtered)} → {len(deduplicated)} ({stats['dedup_ms']}ms)")
        return deduplicated, stats

    def _step_rank(self, deduplicated, stats):
        """Step 4: Rank by weighted sum."""
        import time
        start = time.time()
        ranked = self.rank(deduplicated)
        stats["rank_ms"] = int((time.time() - start) * 1000)
        logger.info(f"Rank: Weighted scoring in {stats['rank_ms']}ms")
        return ranked, stats

    def _step_compress(self, ranked, mode, token_budget, stats):
        """Step 5: Compress to core + extended."""
        import time
        start = time.time()
        result = self.compress(ranked, mode, token_budget)
        stats["compress_ms"] = int((time.time() - start) * 1000)
        logger.info(
            f"Compress: {len(ranked)} → {len(result['core']) + len(result['extended'])} "
            f"({stats['compress_ms']}ms)"
        )
        return result, stats

    def recall(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Step 1: Query all 3 tiers (Vector + HippoRAG + Bayesian).

        Args:
            query: User query text
            top_k: Number of candidates per tier

        Returns:
            List of candidates with keys:
                - text: Chunk content
                - score: Tier-specific score (0-1)
                - tier: "vector" | "hipporag" | "bayesian"
                - metadata: Additional metadata
        """
        candidates = []

        # Query Vector tier
        vector_results = self._query_vector_tier(query, top_k)
        candidates.extend(vector_results)
        logger.debug(f"Vector tier: {len(vector_results)} results")

        # Query HippoRAG tier
        hipporag_results = self._query_hipporag_tier(query, top_k)
        candidates.extend(hipporag_results)
        logger.debug(f"HippoRAG tier: {len(hipporag_results)} results")

        # Query Bayesian tier (optional, may return None)
        bayesian_results = self._query_bayesian_tier(query, top_k)
        if bayesian_results:
            candidates.extend(bayesian_results)
            logger.debug(f"Bayesian tier: {len(bayesian_results)} results")
        else:
            logger.debug("Bayesian tier: No results (skipped or timeout)")

        logger.info(f"Recall: {len(candidates)} total candidates from all tiers")
        return candidates

    def filter_by_confidence(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Step 2: Filter by confidence threshold.

        Args:
            candidates: List of candidates from recall

        Returns:
            Filtered list (confidence >= threshold)
        """
        filtered = [
            c for c in candidates
            if c.get("score", 0.0) >= self.confidence_threshold
        ]

        logger.debug(
            f"Filter: {len(candidates) - len(filtered)} candidates "
            f"removed (confidence <{self.confidence_threshold})"
        )

        return filtered

    def deduplicate(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Step 3: Remove duplicates by cosine similarity.

        Args:
            candidates: List of candidates from filter

        Returns:
            Deduplicated list (cosine <dedup_threshold)
        """
        if not candidates:
            return []

        # Keep first occurrence of each unique chunk
        unique = []
        seen_texts = set()

        for candidate in candidates:
            text = candidate.get("text", "")

            # Check for exact duplicates first
            if text in seen_texts:
                continue

            # Check for near-duplicates (cosine similarity)
            is_duplicate = False
            for existing in unique:
                similarity = self._calculate_cosine_similarity(
                    text, existing.get("text", "")
                )
                if similarity >= self.dedup_threshold:
                    is_duplicate = True
                    logger.debug(
                        f"Duplicate found (cosine={similarity:.3f}): "
                        f"{text[:50]}... == {existing.get('text', '')[:50]}..."
                    )
                    break

            if not is_duplicate:
                unique.append(candidate)
                seen_texts.add(text)

        logger.info(
            f"Deduplicate: {len(candidates)} → {len(unique)} "
            f"({len(candidates) - len(unique)} duplicates removed)"
        )

        return unique

    def rank(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 4: Rank by weighted sum of tier scores.

        Args:
            candidates: List of candidates from deduplicate

        Returns:
            Sorted list (highest score first) with hybrid_score added
        """
        for candidate in candidates:
            tier = candidate.get("tier", "vector")
            tier_score = candidate.get("score", 0.0)
            weight = self.weights.get(tier, 0.4)

            # Hybrid score = tier_weight * tier_score
            candidate["hybrid_score"] = weight * tier_score
            candidate["tier_weight"] = weight

        # Sort by hybrid score (descending)
        ranked = sorted(
            candidates,
            key=lambda x: x.get("hybrid_score", 0.0),
            reverse=True
        )

        logger.info(
            f"Rank: Top score = {ranked[0].get('hybrid_score', 0.0):.3f} "
            f"(tier={ranked[0].get('tier', 'unknown')})"
        )

        return ranked

    def compress(
        self,
        ranked_results: List[Dict[str, Any]],
        mode: str,
        token_budget: int = 10000
    ) -> Dict[str, Any]:
        """
        Step 5: Compress to curated core + extended.

        Insight #1: Bigger windows make you dumber.
        Beyond curated core, more tokens reduce precision.

        Args:
            ranked_results: Ranked candidates
            mode: execution/planning/brainstorming
            token_budget: Hard limit (10k tokens max)

        Returns:
            {
                core: [top-5 highest-confidence],
                extended: [next 15-25],
                token_count: int,
                compression_ratio: float,
                mode: str
            }
        """
        # Get mode-specific configuration
        config = self._get_mode_config(mode)

        # Split into core and extended
        core, extended = self._split_core_extended(ranked_results, config)

        # Enforce token budget and calculate metrics
        return self._finalize_compression(
            core, extended, ranked_results, mode, token_budget
        )

    def _get_mode_config(self, mode: str) -> Dict[str, int]:
        """Get mode-specific core/extended split configuration."""
        configs = {
            "execution": {"core_k": 5, "extended_k": 0},
            "planning": {"core_k": 5, "extended_k": 15},
            "brainstorming": {"core_k": 5, "extended_k": 25}
        }
        return configs.get(mode, configs["execution"])

    def _split_core_extended(self, results, config):
        """Split results into core and extended."""
        core = results[:config["core_k"]]
        extended = results[config["core_k"]:config["core_k"] + config["extended_k"]]
        return core, extended

    def _finalize_compression(self, core, extended, all_results, mode, budget):
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
            f"Compressed {len(all_results)} → {len(core) + len(extended)} "
            f"({ratio:.1%}, {total_tokens} tokens)"
        )

        return {
            "core": core,
            "extended": extended,
            "token_count": total_tokens,
            "compression_ratio": ratio,
            "mode": mode
        }

    # Helper Methods

    def _query_vector_tier(
        self,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Query Vector tier (ChromaDB).

        Args:
            query: User query text
            top_k: Number of results

        Returns:
            List of results with tier="vector"
        """
        if not self.vector_indexer or not self.embedding_pipeline:
            logger.warning("Vector tier not available (indexer or embeddings missing)")
            return []

        try:
            # Generate query embedding
            query_embedding = self.embedding_pipeline.encode([query])[0]

            # Search vector index
            raw_results = self.vector_indexer.search_similar(
                query_embedding=query_embedding,
                top_k=top_k
            )

            # Convert to standard format
            results = []
            for result in raw_results:
                results.append({
                    "text": result.get("document", ""),
                    "score": 1 - result.get("distance", 1.0),  # Distance → similarity
                    "tier": "vector",
                    "metadata": result.get("metadata", {}),
                    "id": result.get("id", "")
                })

            return results

        except Exception as e:
            logger.error(f"Vector tier query failed: {e}")
            return []

    def _query_hipporag_tier(
        self,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Query HippoRAG tier (Multi-hop graph reasoning).

        Args:
            query: User query text
            top_k: Number of results

        Returns:
            List of results with tier="hipporag"
        """
        if not self.graph_query_engine:
            logger.warning("HippoRAG tier not available (graph query engine missing)")
            return []

        try:
            # Query graph with multi-hop reasoning
            raw_results = self.graph_query_engine.retrieve_multi_hop(
                query=query,
                top_k=top_k,
                max_hops=3
            )

            # Convert to standard format
            results = []
            for result in raw_results:
                results.append({
                    "text": result.get("text", result.get("content", "")),
                    "score": result.get("ppr_score", result.get("score", 0.5)),
                    "tier": "hipporag",
                    "metadata": result.get("metadata", {}),
                    "id": result.get("chunk_id", result.get("id", ""))
                })

            return results

        except Exception as e:
            logger.error(f"HippoRAG tier query failed: {e}")
            return []

    def _query_bayesian_tier(
        self,
        query: str,
        top_k: int
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Query Bayesian tier (Probabilistic inference).

        Note: Bayesian tier may timeout or be skipped for simple queries.

        Args:
            query: User query text
            top_k: Number of results (unused, Bayesian returns all states)

        Returns:
            List of results with tier="bayesian" or None if skipped/timeout
        """
        if not self.probabilistic_query_engine:
            logger.warning("Bayesian tier not available (query engine missing)")
            return None

        try:
            # B3.3 FIX: Extract entities properly (capitalized phrases)
            # Uses same logic as entity_extraction MCP tool
            query_entity = self._extract_query_entity(query)

            # Query Bayesian network
            raw_results = self.probabilistic_query_engine.query_conditional(
                network=None,  # Network passed separately in production
                query_vars=[query_entity],
                evidence=None
            )

            if raw_results is None:
                # Timeout or skip
                logger.debug("Bayesian tier timeout/skip")
                return None

            # Convert to standard format
            results = []
            for var, prob_dist in raw_results.get("results", {}).items():
                for state, prob in prob_dist.items():
                    if isinstance(state, (int, str)):  # Skip metadata
                        results.append({
                            "text": f"{var}={state}",
                            "score": float(prob),
                            "tier": "bayesian",
                            "metadata": {
                                "variable": var,
                                "state": state,
                                "entropy": prob_dist.get("entropy", 0.0)
                            },
                            "id": f"bayesian_{var}_{state}"
                        })

            return results[:top_k]  # Limit to top_k

        except Exception as e:
            logger.warning(f"Bayesian tier query failed (expected): {e}")
            return None

    def _extract_query_entity(self, query: str) -> str:
        """
        B3.3 FIX: Extract entity from query using capitalized phrase detection.

        Instead of just taking the first word, this looks for:
        1. Capitalized phrases (e.g., "John Smith", "New York City")
        2. Falls back to longest capitalized word
        3. Falls back to first word if no capitalized words found

        Args:
            query: Input query text

        Returns:
            Extracted entity string

        NASA Rule 10: 25 LOC
        """
        import re

        if not query or not query.strip():
            return "unknown"

        # Find capitalized phrases (2+ adjacent capitalized words)
        cap_phrase_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        phrases = re.findall(cap_phrase_pattern, query)
        if phrases:
            # Return longest capitalized phrase
            return max(phrases, key=len)

        # Find single capitalized words (excluding sentence starters)
        words = query.split()
        cap_words = [w for i, w in enumerate(words)
                     if w[0].isupper() and (i > 0 or len(words) == 1)]
        if cap_words:
            return max(cap_words, key=len)

        # Fallback: first word
        return words[0] if words else "unknown"

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
