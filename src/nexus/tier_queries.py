"""
Tier Query Module: Queries for Vector, HippoRAG, and Bayesian tiers.

Extracted from processor.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC

BAY-002/BAY-005: Includes feedback loop to update graph edges from Bayesian posteriors.
"""

from typing import List, Dict, Any, Optional
import re
from loguru import logger
from ..services.entity_service import load_spacy_model


class TierQueryMixin:
    """
    Mixin providing tier query methods for NexusProcessor.

    Requires:
        - self.vector_indexer
        - self.embedding_pipeline
        - self.graph_query_engine
        - self.probabilistic_query_engine
        - self.bayesian_graph_sync (optional, BAY-002/BAY-005)
    """

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
                # ISS-021 FIX: Normalize L2 distance to [0,1] similarity
                # L2 distance can be > 1, so use max(0, 1 - d/2) to ensure [0,1] range
                distance = result.get("distance", 1.0)
                similarity = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
                results.append({
                    "text": result.get("document", ""),
                    "score": similarity,
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
        BAY-002/BAY-005: Includes feedback loop to update graph edges.

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
            query_entity = self._extract_query_entity(query)

            # Query Bayesian network
            raw_results = self.probabilistic_query_engine.query_conditional(
                network=None,  # Network passed separately in production
                query_vars=[query_entity],
                evidence=None
            )

            if raw_results is None:
                logger.debug("Bayesian tier timeout/skip")
                return None

            # BAY-002/BAY-005: Feedback loop - update graph from Bayesian inference
            self._apply_bayesian_feedback(raw_results)

            # Convert to standard format
            # MEM-001: prob_dist contains {'probabilities': {...}, 'entropy': float}
            # We need to iterate over probabilities, not the outer dict
            results = []
            for var, var_result in raw_results.get("results", {}).items():
                # Extract probabilities dict and entropy from var_result
                if isinstance(var_result, dict):
                    prob_dist = var_result.get("probabilities", var_result)
                    entropy = var_result.get("entropy", 0.0)
                else:
                    prob_dist = {}
                    entropy = 0.0

                for state, prob in prob_dist.items():
                    # MEM-001: Skip metadata keys like 'entropy', 'probabilities'
                    if state in ("entropy", "probabilities"):
                        continue
                    if isinstance(state, (int, str)) and isinstance(prob, (int, float)):
                        results.append({
                            "text": f"{var}={state}",
                            "score": float(prob),
                            "tier": "bayesian",
                            "metadata": {
                                "variable": var,
                                "state": state,
                                "entropy": entropy
                            },
                            "id": f"bayesian_{var}_{state}"
                        })

            return results[:top_k]

        except Exception as e:
            logger.warning(f"Bayesian tier query failed (expected): {e}")
            return None

    def _apply_bayesian_feedback(
        self,
        inference_results: Dict[str, Any]
    ) -> None:
        """
        BAY-002: Apply feedback loop to update graph edges from Bayesian inference.

        Called after successful Bayesian query to propagate posteriors back to graph.
        Uses formula: new_confidence = 0.7 * prior + 0.3 * posterior

        Args:
            inference_results: Results from ProbabilisticQueryEngine

        NASA Rule 10: 20 LOC (<=60)
        """
        # Check if bayesian_graph_sync is available (optional dependency)
        sync = getattr(self, 'bayesian_graph_sync', None)
        if sync is None:
            logger.debug("Bayesian feedback loop skipped (sync not configured)")
            return

        try:
            sync_result = sync.update_graph_from_inference(inference_results)
            if sync_result.get("edges_updated", 0) > 0:
                logger.info(
                    f"BAY-002 feedback: {sync_result['edges_updated']} edges updated"
                )
        except Exception as e:
            logger.warning(f"Bayesian feedback loop failed: {e}")

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
        if not query or not query.strip():
            return "unknown"

        # Prefer spaCy entity spans when available
        try:
            nlp = load_spacy_model()
            doc = nlp(query)
            if doc.ents:
                longest = max(doc.ents, key=lambda ent: len(ent.text))
                return longest.text
        except Exception as e:
            logger.debug(f"spaCy entity extraction failed, using regex: {e}")

        # Find capitalized phrases (2+ adjacent capitalized words)
        cap_phrase_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        phrases = re.findall(cap_phrase_pattern, query)
        if phrases:
            return max(phrases, key=len)

        # Find single capitalized words (excluding sentence starters)
        words = query.split()
        cap_words = [w for i, w in enumerate(words)
                     if w[0].isupper() and (i > 0 or len(words) == 1)]
        if cap_words:
            return max(cap_words, key=len)

        # Fallback: first word
        return words[0] if words else "unknown"
