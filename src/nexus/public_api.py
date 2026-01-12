"""Public API for Memory MCP queries."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from .processor import NexusProcessor
from ..mcp.tools.vector_search import VectorSearchTool
from ..services.graph_service import GraphService
from ..services.graph_query_engine import GraphQueryEngine
from ..services.entity_service import EntityService
from ..services.hipporag_service import HippoRagService
from ..bayesian.network_builder import NetworkBuilder
from ..bayesian.probabilistic_query_engine import ProbabilisticQueryEngine

logger = logging.getLogger(__name__)


class MemoryMCPQueryService:
    """Public API for external retrieval services."""

    def __init__(self, data_dir: str = "./data") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._config = _load_config()
        self._config.setdefault("storage", {})["data_dir"] = str(self._data_dir)
        self._vector_tool = VectorSearchTool(self._config)
        self._graph_service = GraphService(data_dir=str(self._data_dir))
        self._graph_query_engine = GraphQueryEngine(self._graph_service)
        self._entity_service = _init_entity_service()
        self._hipporag_service = self._init_hipporag()
        self._nexus = self._init_nexus()

    async def semantic_search(
        self,
        query: str,
        mode: str = "execution",
        top_k: int = 50,
        token_budget: int = 10000,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._nexus.process,
            query,
            mode,
            top_k,
            token_budget,
        )

    async def get_related_entities(self, entity_name: str) -> List[str]:
        return await asyncio.to_thread(
            self._get_related_entities_sync,
            entity_name,
        )

    async def store_context(
        self,
        content: str,
        metadata: Dict[str, Any],
        tags: Dict[str, str],
    ) -> str:
        return await asyncio.to_thread(
            self._store_context_sync,
            content,
            metadata,
            tags,
        )

    def _init_nexus(self) -> NexusProcessor:
        graph_query_engine = self._graph_query_engine
        bayesian_network = None
        try:
            builder = NetworkBuilder(max_nodes=1000)
            bayesian_network = builder.build_network(self._graph_service.graph)
        except Exception as exc:
            logger.warning("Failed to build Bayesian network: %s", exc)
        probabilistic_engine = ProbabilisticQueryEngine(network=bayesian_network)
        return NexusProcessor(
            vector_indexer=self._vector_tool.indexer,
            graph_query_engine=graph_query_engine,
            probabilistic_query_engine=probabilistic_engine,
            embedding_pipeline=self._vector_tool.embedder,
        )

    def _init_hipporag(self) -> Optional[HippoRagService]:
        if self._entity_service is None:
            return None
        return HippoRagService(self._graph_service, self._entity_service)

    def _get_related_entities_sync(self, entity_name: str) -> List[str]:
        normalized = entity_name.lower().replace(" ", "_")
        neighborhood = self._graph_query_engine.get_entity_neighborhood(
            normalized,
            hops=2,
        )
        entities = neighborhood.get("entities", [])
        return [e for e in entities if e != normalized]

    def _store_context_sync(
        self,
        content: str,
        metadata: Dict[str, Any],
        tags: Dict[str, str],
    ) -> str:
        enriched_metadata = _merge_tags(metadata, tags)
        embeddings = self._vector_tool.embedder.encode([content])
        chunk = {
            "text": content,
            "file_path": enriched_metadata.get("key", "manual_entry"),
            "chunk_index": 0,
            "metadata": enriched_metadata,
        }
        self._vector_tool.indexer.index_chunks([chunk], embeddings.tolist())
        return "stored"


def _init_entity_service() -> Optional[EntityService]:
    try:
        return EntityService()
    except Exception as exc:
        logger.warning("EntityService unavailable: %s", exc)
        return None


def _merge_tags(metadata: Dict[str, Any], tags: Dict[str, str]) -> Dict[str, Any]:
    merged = dict(metadata)
    merged.update(tags)
    return merged


def _load_config() -> Dict[str, Any]:
    from ..mcp.stdio_server import load_config

    return load_config()
