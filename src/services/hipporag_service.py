"""
HippoRagService - Graph-based retrieval using Personalized PageRank.

Implements HippoRAG (NeurIPS'24) for multi-hop reasoning and context-aware
retrieval. Uses knowledge graph + PPR instead of flat vector similarity.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple
from loguru import logger

from .graph_service import GraphService
from .entity_service import EntityService


@dataclass
class QueryEntity:
    """Query entity with graph node mapping."""
    text: str
    type: str
    node_id: Optional[str]
    confidence: float


@dataclass
class RetrievalResult:
    """HippoRAG retrieval result."""
    chunk_id: str
    text: str
    score: float
    rank: int
    entities: List[str]
    metadata: Dict[str, Any]


class HippoRagService:
    """
    HippoRAG retrieval service using graph-based multi-hop reasoning.

    Based on NeurIPS'24 paper: Hippocampal Indexing for RAG.
    Uses Personalized PageRank on knowledge graph for context-aware retrieval.
    """

    def __init__(
        self,
        graph_service: GraphService,
        entity_service: EntityService
    ):
        """
        Initialize HippoRAG service with dependencies.

        Args:
            graph_service: GraphService instance for graph operations
            entity_service: EntityService instance for entity extraction

        Raises:
            ValueError: If dependencies are None or invalid
        """
        if graph_service is None:
            raise ValueError("graph_service cannot be None")

        if entity_service is None:
            raise ValueError("entity_service cannot be None")

        self.graph_service = graph_service
        self.entity_service = entity_service

        # Initialize graph query engine (Day 2)
        from .graph_query_engine import GraphQueryEngine
        self.graph_query_engine = GraphQueryEngine(graph_service)

        logger.info("HippoRagService initialized")

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.85
    ) -> List[RetrievalResult]:
        """
        Retrieve top-K chunks using HippoRAG (graph-based retrieval).

        Args:
            query: User query text
            top_k: Number of results to return
            alpha: PPR damping factor (default: 0.85)

        Returns:
            List of RetrievalResult objects sorted by relevance
        """
        logger.info(f"HippoRAG retrieve: '{query}' (top_k={top_k})")

        try:
            # Step 1: Extract entities from query
            query_entities = self._extract_query_entities(query)
            if not query_entities:
                logger.warning(f"No entities extracted from query: {query}")
                return []

            # Step 2: Match entities to graph nodes
            query_nodes = self._match_entities_to_nodes(query_entities)
            if not query_nodes:
                logger.warning("No query entities found in graph")
                return []

            # Step 3: Run PPR and rank chunks
            ranked_chunks = self._run_ppr_and_rank(query_nodes, alpha, top_k)
            if not ranked_chunks:
                logger.warning("No chunks ranked")
                return []

            # Step 4: Format results
            results = self._format_retrieval_results(
                ranked_chunks,
                query_nodes
            )

            logger.info(f"Retrieved {len(results)} chunks for query")
            return results

        except Exception as e:
            logger.error(f"Retrieve failed: {e}")
            return []

    def _run_ppr_and_rank(
        self,
        query_nodes: List[str],
        alpha: float,
        top_k: int
    ) -> List[Tuple[str, float]]:
        """
        Run Personalized PageRank and rank chunks.

        Args:
            query_nodes: List of query node IDs
            alpha: PPR damping factor
            top_k: Number of results to return

        Returns:
            List of (chunk_id, score) tuples
        """
        # Run PPR
        ppr_scores = self.graph_query_engine.personalized_pagerank(
            query_nodes=query_nodes,
            alpha=alpha
        )

        if not ppr_scores:
            logger.warning("PPR returned no scores")
            return []

        # Rank chunks
        ranked_chunks = self.graph_query_engine.rank_chunks_by_ppr(
            ppr_scores=ppr_scores,
            top_k=top_k
        )

        return ranked_chunks

    def _format_retrieval_results(
        self,
        ranked_chunks: List[Tuple[str, float]],
        query_nodes: List[str]
    ) -> List[RetrievalResult]:
        """
        Format ranked chunks as RetrievalResult objects.

        Args:
            ranked_chunks: List of (chunk_id, score) tuples
            query_nodes: List of query entity IDs

        Returns:
            List of RetrievalResult objects
        """
        results: List[RetrievalResult] = []

        for rank, (chunk_id, score) in enumerate(ranked_chunks, 1):
            # Get chunk metadata
            node_data = self.graph_service.get_node(chunk_id)
            chunk_text = node_data.get('metadata', {}).get('text', '')

            result = RetrievalResult(
                chunk_id=chunk_id,
                text=chunk_text,
                score=float(score),
                rank=rank,
                entities=query_nodes,
                metadata=node_data.get('metadata', {})
            )
            results.append(result)

        return results

    def _extract_query_entities(self, query: str) -> List[str]:
        """
        Extract entities from query using EntityService.

        Args:
            query: Query text

        Returns:
            List of normalized entity IDs
        """
        if not query or not query.strip():
            logger.debug("Empty query provided")
            return []

        try:
            # Extract entities using spaCy NER
            entities = self.entity_service.extract_entities(query)

            # Normalize entity texts to IDs
            entity_ids = [
                self._normalize_entity_text(ent['text'])
                for ent in entities
            ]

            logger.debug(f"Extracted {len(entity_ids)} entities from query")
            return entity_ids

        except Exception as e:
            logger.error(f"Failed to extract query entities: {e}")
            return []

    def _match_entities_to_nodes(
        self,
        entities: List[str]
    ) -> List[str]:
        """
        Match extracted entities to graph nodes.

        Args:
            entities: List of normalized entity IDs

        Returns:
            List of matched node IDs
        """
        matched_nodes = []

        for entity_id in entities:
            # Check for exact match in graph
            node = self.graph_service.get_node(entity_id)

            if node is not None:
                matched_nodes.append(entity_id)
                logger.debug(f"Exact match found: {entity_id}")
            else:
                logger.debug(f"No match for entity: {entity_id}")

        logger.debug(f"Matched {len(matched_nodes)} entities to graph nodes")
        return matched_nodes

    def _normalize_entity_text(self, text: str) -> str:
        """
        Normalize entity text for ID generation.

        Args:
            text: Entity text

        Returns:
            Normalized text (lowercase, no spaces)
        """
        return text.lower().replace(' ', '_').replace('.', '')

    def retrieve_multi_hop(
        self,
        query: str,
        max_hops: int = 3,
        top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        Retrieve using multi-hop graph traversal.

        Combines PPR with multi-hop BFS for better coverage.

        Args:
            query: User query text
            max_hops: Maximum hops to traverse
            top_k: Number of results

        Returns:
            List of RetrievalResult dicts
        """
        logger.info(
            f"Multi-hop retrieve: '{query}' "
            f"(max_hops={max_hops}, top_k={top_k})"
        )

        try:
            # Extract and match entities
            query_nodes = self._get_query_nodes(query)
            if not query_nodes:
                return []

            # Expand with multi-hop search
            expanded_entities = self._expand_entities_multi_hop(
                query_nodes, max_hops
            )
            if not expanded_entities:
                return []

            # Run PPR and rank chunks
            results = self._ppr_rank_and_format(
                expanded_entities, top_k
            )

            logger.info(
                f"Multi-hop retrieve found {len(results)} chunks "
                f"using {len(expanded_entities)} entities"
            )
            return results

        except Exception as e:
            logger.error(f"Multi-hop retrieve failed: {e}")
            return []

    def _get_query_nodes(self, query: str) -> List[str]:
        """
        Extract entities from query and match to graph nodes.

        Args:
            query: User query text

        Returns:
            List of matched node IDs
        """
        query_entities = self._extract_query_entities(query)
        if not query_entities:
            logger.warning(f"No entities extracted from query: {query}")
            return []

        query_nodes = self._match_entities_to_nodes(query_entities)
        if not query_nodes:
            logger.warning("No query entities found in graph")
            return []

        return query_nodes

    def _expand_entities_multi_hop(
        self,
        query_nodes: List[str],
        max_hops: int
    ) -> List[str]:
        """
        Expand entities using multi-hop search.

        Args:
            query_nodes: Starting nodes
            max_hops: Maximum hops

        Returns:
            List of expanded entity IDs
        """
        multi_hop_result = self.graph_query_engine.multi_hop_search(
            start_nodes=query_nodes,
            max_hops=max_hops
        )

        expanded_entities = multi_hop_result['entities']
        if not expanded_entities:
            logger.warning("Multi-hop search found no entities")
            return []

        return expanded_entities

    def _ppr_rank_and_format(
        self,
        expanded_entities: List[str],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Run PPR, rank chunks, and format results.

        Args:
            expanded_entities: Expanded entity nodes
            top_k: Number of results

        Returns:
            List of RetrievalResult objects
        """
        # Run PPR on expanded entity set
        ppr_scores = self.graph_query_engine.personalized_pagerank(
            query_nodes=expanded_entities,
            alpha=0.85
        )

        if not ppr_scores:
            logger.warning("PPR returned no scores")
            return []

        # Rank chunks
        ranked_chunks = self.graph_query_engine.rank_chunks_by_ppr(
            ppr_scores=ppr_scores,
            top_k=top_k
        )

        if not ranked_chunks:
            logger.warning("No chunks ranked")
            return []

        # Format results
        return self._format_retrieval_results(
            ranked_chunks,
            expanded_entities
        )
