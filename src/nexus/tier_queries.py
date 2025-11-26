"""
Tier Query Module: Queries for Vector, HippoRAG, and Bayesian tiers.

Extracted from processor.py for modularity.
NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict, Any, Optional
import re
from loguru import logger


class TierQueryMixin:
    """
    Mixin providing tier query methods for NexusProcessor.

    Requires:
        - self.vector_indexer
        - self.embedding_pipeline
        - self.graph_query_engine
        - self.probabilistic_query_engine
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
                results.append({
                    "text": result.get("document", ""),
                    "score": 1 - result.get("distance", 1.0),  # Distance -> similarity
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

            return results[:top_k]

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
