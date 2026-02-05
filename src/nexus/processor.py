"""
Nexus Processor: Unified Multi-Tier RAG Retrieval Pipeline.

Implements 5.5-step SOP (MEM-QWEN-002):
1. Recall - Query all 3 tiers (Vector + HippoRAG + Bayesian)
2. Filter - Confidence threshold (>0.3)
3. Deduplicate - Cosine similarity (>0.95)
4. Rank - Weighted scoring (Vector 0.4 + HippoRAG 0.4 + Bayesian 0.2)
4.5 Rerank - Cross-encoder precision refinement (optional, MEM-QWEN-002)
5. Compress - Curated core pattern (mode-aware)

NASA Rule 10 Compliant: All methods <=60 LOC

Refactored: Extracted tier queries and utilities into separate modules.
See: tier_queries.py, processing_utils.py
"""

from typing import List, Dict, Any, Optional
from loguru import logger

# Import mixins for modular architecture (ISS-004 fix)
from .tier_queries import TierQueryMixin
from .processing_utils import ProcessingUtilsMixin, LostInMiddleMitigation


class NexusProcessor(TierQueryMixin, ProcessingUtilsMixin):
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
        reranker: Any = None,
        rlm_adapter: Any = None,
        bayesian_graph_sync: Any = None,
        confidence_threshold: float = 0.3,
        dedup_threshold: float = 0.95,
        weights: Optional[Dict[str, float]] = None,
        rerank_top_k: int = 30,
        rerank_enabled: bool = True,
        lost_in_middle_mitigation: LostInMiddleMitigation = LostInMiddleMitigation.EDGES
    ) -> None:
        """
        Initialize Nexus Processor with all 3 tier services.

        Args:
            vector_indexer: VectorIndexer instance (Week 6)
            graph_query_engine: GraphQueryEngine instance (Week 8)
            probabilistic_query_engine: ProbabilisticQueryEngine instance (Week 10)
            embedding_pipeline: EmbeddingPipeline instance (Week 6)
            reranker: RerankerService instance (MEM-QWEN-002)
            rlm_adapter: RLMNexusAdapter instance (RLM-008)
            bayesian_graph_sync: BayesianGraphSync instance (BAY-005 feedback loop)
            confidence_threshold: Minimum confidence for filtering (default: 0.3)
            dedup_threshold: Cosine similarity threshold for deduplication (default: 0.95)
            weights: Tier weights for ranking (default: {vector: 0.4, hipporag: 0.4, bayesian: 0.2})
            rerank_top_k: Number of candidates to pass through reranker (default: 30)
            rerank_enabled: Enable/disable reranking step (default: True)
            lost_in_middle_mitigation: Strategy for mitigating lost-in-middle (MEM-CHUNK-002)
        """
        self.vector_indexer = vector_indexer
        self.graph_query_engine = graph_query_engine
        self.probabilistic_query_engine = probabilistic_query_engine
        self.embedding_pipeline = embedding_pipeline
        self.reranker = reranker
        self.rlm_adapter = rlm_adapter
        self.bayesian_graph_sync = bayesian_graph_sync  # BAY-005: Feedback loop
        self.confidence_threshold = confidence_threshold
        self.dedup_threshold = dedup_threshold
        self.rerank_top_k = rerank_top_k
        self.rerank_enabled = rerank_enabled
        self.lost_in_middle_mitigation = lost_in_middle_mitigation  # MEM-CHUNK-002
        self.weights = weights or {
            "vector": 0.4,
            "hipporag": 0.4,
            "bayesian": 0.2
        }

        rerank_status = "enabled" if (reranker and rerank_enabled) else "disabled"
        feedback_status = "enabled" if bayesian_graph_sync else "disabled"
        mitigation_status = lost_in_middle_mitigation.value
        logger.info(
            f"NexusProcessor initialized with weights: {self.weights}, "
            f"rerank: {rerank_status}, bayesian_feedback: {feedback_status}, "
            f"lost_in_middle: {mitigation_status}"
        )

    def process(
        self,
        query: str,
        mode: str = "execution",
        top_k: int = 50,
        token_budget: int = 10000,
        use_rlm: bool = False
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

        if use_rlm:
            rlm_result = self._process_rlm(query, mode, top_k, token_budget)
            if rlm_result is not None:
                rlm_result["pipeline_stats"] = {
                    "rlm_ms": int((time.time() - start) * 1000)
                }
                rlm_result["total_ms"] = int((time.time() - start) * 1000)
                logger.info(
                    "RLM pipeline complete: "
                    f"{rlm_result['total_ms']}ms total "
                    f"({len(rlm_result['core'])} core + {len(rlm_result['extended'])} extended)"
                )
                return rlm_result

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

    def _process_rlm(
        self,
        query: str,
        mode: str,
        top_k: int,
        token_budget: int
    ) -> Optional[Dict[str, Any]]:
        """Execute RLM exploration as a NexusProcessor alternative."""
        adapter = self.rlm_adapter
        if adapter is None:
            try:
                from ..rlm.rlm_nexus_adapter import RLMNexusAdapter
                adapter = RLMNexusAdapter()
                self.rlm_adapter = adapter
            except Exception as exc:
                logger.warning(f"RLM adapter unavailable: {exc}")
                return None
        try:
            return adapter.explore(
                query,
                mode=mode,
                top_k=top_k,
                token_budget=token_budget,
            )
        except Exception as exc:
            logger.warning(f"RLM exploration failed: {exc}")
            return None

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

        # Combine tier scores into hybrid candidates
        combine_start = time.time()
        combined = self._combine_tier_scores(candidates)
        stats["combine_ms"] = int((time.time() - combine_start) * 1000)
        if not combined:
            return self._empty_result(mode), stats

        # Step 2: Filter
        filtered, stats = self._step_filter(combined, stats)
        if not filtered:
            return self._empty_result(mode), stats

        # Step 3-4: Deduplicate, Rank
        deduplicated, stats = self._step_deduplicate(filtered, stats)
        ranked, stats = self._step_rank(deduplicated, stats)

        # Step 4.5: Rerank with cross-encoder (MEM-QWEN-002)
        if self.reranker and self.rerank_enabled:
            reranked, stats = self._step_rerank(query, ranked, stats)
        else:
            reranked = ranked

        # Step 5: Compress
        result, stats = self._step_compress(reranked, mode, token_budget, stats)

        return result, stats

    def _candidate_key(self, candidate: Dict[str, Any]) -> str:
        """Build a stable key for combining tier scores."""
        candidate_id = candidate.get("id")
        if candidate_id:
            return str(candidate_id)

        metadata = candidate.get("metadata", {})
        file_path = metadata.get("file_path")
        if file_path:
            chunk_index = metadata.get("chunk_index", 0)
            return f"{file_path}::{chunk_index}"

        text = candidate.get("text", "")
        return text[:200] if text else "unknown"

    def _combine_tier_scores(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Combine tier-specific scores into hybrid candidates.

        Adds vector_score, graph_score, bayesian_score and hybrid score fields.
        """
        grouped: Dict[str, Dict[str, Any]] = {}

        for candidate in candidates:
            key = self._candidate_key(candidate)
            entry = grouped.setdefault(key, {
                "id": candidate.get("id", key),
                "text": candidate.get("text", ""),
                "metadata": candidate.get("metadata", {}),
                "vector_score": 0.0,
                "graph_score": 0.0,
                "bayesian_score": 0.0,
                "source_tiers": set()
            })

            tier = candidate.get("tier", "vector")
            score = float(candidate.get("score", 0.0))
            entry["source_tiers"].add(tier)

            if tier == "vector":
                entry["vector_score"] = max(entry["vector_score"], score)
            elif tier == "hipporag":
                entry["graph_score"] = max(entry["graph_score"], score)
            elif tier == "bayesian":
                entry["bayesian_score"] = max(entry["bayesian_score"], score)

            if not entry.get("text") and candidate.get("text"):
                entry["text"] = candidate["text"]
            if not entry.get("metadata") and candidate.get("metadata"):
                entry["metadata"] = candidate["metadata"]

        combined = []
        for entry in grouped.values():
            final_score = self._calculate_hybrid_score(
                vector_score=entry["vector_score"],
                graph_score=entry["graph_score"],
                bayesian_score=entry["bayesian_score"]
            )
            entry["score"] = final_score
            entry["hybrid_score"] = final_score
            entry["tier"] = "hybrid"
            entry["source_tiers"] = sorted(entry["source_tiers"])
            combined.append(entry)

        return combined

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

    def _step_rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Step 4.5: Rerank top candidates with cross-encoder (MEM-QWEN-002).

        Uses cross-encoder for more precise query-document relevance scoring.
        Only reranks top-k candidates to limit latency overhead.
        """
        import time
        start = time.time()

        # Limit candidates for reranking (latency optimization)
        candidates_to_rerank = candidates[:self.rerank_top_k]
        remaining = candidates[self.rerank_top_k:]

        # Call reranker service
        reranked, rerank_stats = self.reranker.rerank(
            query=query,
            documents=candidates_to_rerank,
            top_k=self.rerank_top_k
        )

        # Merge rerank scores with hybrid scores
        reranked = self.reranker.merge_scores(
            reranked,
            hybrid_weight=0.5,
            rerank_weight=0.5
        )

        # Append remaining candidates (not reranked) at lower priority
        result = reranked + remaining

        # Update stats
        stats["rerank_ms"] = int((time.time() - start) * 1000)
        stats.update(rerank_stats)

        logger.info(
            f"Rerank: {len(candidates_to_rerank)} candidates in {stats['rerank_ms']}ms"
        )

        return result, stats

    def _step_compress(self, ranked, mode, token_budget, stats):
        """Step 5: Compress to core + extended with lost-in-middle mitigation."""
        import time
        start = time.time()

        # Apply lost-in-middle mitigation before compression (MEM-CHUNK-002)
        if self.lost_in_middle_mitigation != LostInMiddleMitigation.NONE:
            ranked = self.apply_lost_in_middle_mitigation(
                ranked,
                self.lost_in_middle_mitigation
            )
            stats["mitigation_applied"] = self.lost_in_middle_mitigation.value

        result = self.compress(ranked, mode, token_budget)
        stats["compress_ms"] = int((time.time() - start) * 1000)
        logger.info(
            f"Compress: {len(ranked)} → {len(result['core']) + len(result['extended'])} "
            f"({stats['compress_ms']}ms, mitigation={self.lost_in_middle_mitigation.value})"
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

        P0-1 FIX: Pre-compute embeddings once, then compare vectors.
        Old: O(n^2) embedding calls (re-encoded per pair).
        New: O(n) embeddings + O(n^2) dot products (50x faster).

        Args:
            candidates: List of candidates from filter

        Returns:
            Deduplicated list (cosine <dedup_threshold)
        """
        import numpy as np

        if not candidates:
            return []

        texts = [c.get("text", "") for c in candidates]

        # Exact dedup pass (O(n), hash-based)
        seen_texts = {}
        exact_unique_indices = []
        for i, text in enumerate(texts):
            if text not in seen_texts:
                seen_texts[text] = i
                exact_unique_indices.append(i)

        if not exact_unique_indices:
            return []

        # Pre-compute all embeddings in one batch (O(n) encoding)
        unique_texts = [texts[i] for i in exact_unique_indices]
        embeddings = self._batch_encode_texts(unique_texts)

        if embeddings is None:
            # Fallback: no embedding pipeline, return exact-deduped only
            return [candidates[i] for i in exact_unique_indices]

        unique = self._near_dedup_by_vectors(
            candidates, exact_unique_indices, embeddings
        )

        logger.info(
            f"Deduplicate: {len(candidates)} -> {len(unique)} "
            f"({len(candidates) - len(unique)} duplicates removed)"
        )

        return unique

    def _near_dedup_by_vectors(
        self,
        candidates: List[Dict[str, Any]],
        exact_unique_indices: List[int],
        embeddings: List[List[float]],
    ) -> List[Dict[str, Any]]:
        """Compare pre-computed vectors to remove near-duplicates (O(n^2) dot products)."""
        final_indices = []
        for i, idx in enumerate(exact_unique_indices):
            is_duplicate = False
            for j in final_indices:
                sim = self._cosine_from_vectors(embeddings[i], embeddings[j])
                if sim >= self.dedup_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                final_indices.append(i)

        return [candidates[exact_unique_indices[i]] for i in final_indices]

    def _batch_encode_texts(
        self,
        texts: List[str]
    ) -> Optional[Any]:
        """Pre-compute embeddings for all texts in one batch call."""
        import numpy as np

        if self.embedding_pipeline is None:
            return None
        try:
            return self.embedding_pipeline.encode(texts)
        except Exception as e:
            logger.warning(f"Batch encoding failed: {e}")
            return None

    @staticmethod
    def _cosine_from_vectors(vec_a, vec_b) -> float:
        """Cosine similarity from pre-computed vectors. No re-encoding."""
        import numpy as np

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def rank(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 4: Rank by weighted sum of tier scores.

        Args:
            candidates: List of candidates from deduplicate

        Returns:
            Sorted list (highest score first) with hybrid_score added
        """
        if not candidates:
            return []

        for candidate in candidates:
            vector_score = float(candidate.get("vector_score", 0.0))
            graph_score = float(candidate.get("graph_score", 0.0))
            bayesian_score = float(candidate.get("bayesian_score", 0.0))

            if not any([vector_score, graph_score, bayesian_score]):
                tier = candidate.get("tier")
                base_score = float(candidate.get("score", 0.0))
                if tier == "vector":
                    vector_score = base_score
                elif tier == "hipporag":
                    graph_score = base_score
                elif tier == "bayesian":
                    bayesian_score = base_score

            final_score = self._calculate_hybrid_score(
                vector_score=vector_score,
                graph_score=graph_score,
                bayesian_score=bayesian_score
            )
            candidate["score"] = final_score
            candidate["hybrid_score"] = final_score
            candidate["score_breakdown"] = {
                "vector": vector_score,
                "graph": graph_score,
                "bayesian": bayesian_score
            }

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

    # ISS-004 FIX: The following methods are now provided by mixins:
    # - TierQueryMixin: _query_vector_tier, _query_hipporag_tier, _query_bayesian_tier, _extract_query_entity
    # - ProcessingUtilsMixin: _get_mode_config, _split_core_extended, _finalize_compression,
    #                         _calculate_cosine_similarity, _enforce_token_budget, _empty_result
    #
    # This reduces processor.py from ~720 LOC to ~380 LOC (47% reduction)
    # while maintaining full functionality through multiple inheritance.
