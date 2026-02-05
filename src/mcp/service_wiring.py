"""
Service Wiring Module - Dependency injection and initialization.

Handles production feature wiring (C3.2-C3.6) and NexusProcessor integration.
Extracted from stdio_server.py as part of MEM-CLEAN-003.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml
from loguru import logger

from ..universal_components import (
    init_connascence_bridge,
    init_memory_client,
    init_tagger,
    init_telemetry_bridge,
)

from .tools.vector_search import VectorSearchTool
from ..nexus.processor import NexusProcessor

# Phase 6: Production wiring imports (C3.2-C3.6)
from ..stores.event_log import EventLog
from ..stores.kv_store import KVStore
from ..debug.query_trace import QueryTrace
from ..lifecycle.hotcold_classifier import HotColdClassifier
from ..memory.lifecycle_manager import MemoryLifecycleManager
from .obsidian_client import ObsidianMCPClient

# ISS-003 fix: Import Graph and Bayesian engines for full architecture wiring
from ..services.graph_service import GraphService
from ..services.graph_query_engine import GraphQueryEngine
from ..services.entity_service import EntityService
from ..services.hipporag_service import HippoRagService
from ..bayesian.probabilistic_query_engine import ProbabilisticQueryEngine
from ..bayesian.network_builder import NetworkBuilder

# Beads integration for task management
from ..integrations.beads_bridge import BeadsBridge

# MEM-QWEN-002: Cross-encoder reranker for precision refinement
from ..services.reranker_service import RerankerService

# MEM-QWEN-005: Visual Memory Sidecar
from ..services.qwen3vl_embedder import Qwen3VLEmbedder
from ..services.visual_memory_service import VisualMemoryService
from ..indexing.visual_indexer import VisualMemoryIndexer
from ..services.unified_search_router import UnifiedSearchRouter

REQUIRED_TAGS = ["who", "when", "project", "why"]

# P0-2 FIX: Lazy service instances (no import-time side effects)
_tagger = None
_memory_client = None
_telemetry_bridge = None
_connascence_bridge = None


def get_tagger():
    """Lazy init tagger (only when first accessed)."""
    global _tagger
    if _tagger is None:
        _tagger = init_tagger()
    return _tagger


def get_memory_client():
    """Lazy init memory client (only when first accessed)."""
    global _memory_client
    if _memory_client is None:
        _memory_client = init_memory_client()
    return _memory_client


def get_telemetry_bridge():
    """Lazy init telemetry bridge (only when first accessed)."""
    global _telemetry_bridge
    if _telemetry_bridge is None:
        _telemetry_bridge = init_telemetry_bridge()
    return _telemetry_bridge


def get_connascence_bridge():
    """Lazy init connascence bridge (only when first accessed)."""
    global _connascence_bridge
    if _connascence_bridge is None:
        _connascence_bridge = init_connascence_bridge()
    return _connascence_bridge


class NexusSearchTool:
    """
    Wrapper around NexusProcessor for MCP integration.

    Routes vector_search calls through NexusProcessor's 5-step SOP pipeline.
    Falls back to direct VectorSearchTool if NexusProcessor fails.

    Phase 6: Includes production wiring for EventLog, KVStore, QueryTrace,
    LifecycleManager, and ObsidianClient.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize Nexus search tool with production features."""
        self.config = config
        self.vector_search_tool = VectorSearchTool(config)
        self._nexus_processor: Optional[NexusProcessor] = None

        # Phase 6: Production wiring (C3.2-C3.6)
        self._init_production_features(config)

        logger.info("NexusSearchTool initialized with production features")

    def _init_production_features(self, config: Dict[str, Any]) -> None:
        """Initialize production features (C3.2-C3.6). NASA Rule 10: 25 LOC"""
        import os
        data_dir = Path(config.get('storage', {}).get('data_dir', './data'))
        data_dir.mkdir(parents=True, exist_ok=True)

        # C3.3: Event logging
        self.event_log = EventLog(db_path=str(data_dir / "events.db"))

        # C3.4: KV store for session state
        self.kv_store = KVStore(db_path=str(data_dir / "kv_store.db"))

        # C3.5: Lifecycle manager with hot/cold classifier
        self.hot_cold_classifier = HotColdClassifier()
        self.lifecycle_manager = MemoryLifecycleManager(
            vector_indexer=self.vector_search_tool.indexer,
            kv_store=self.kv_store
        )

        # C3.2: Obsidian client (lazy init)
        vault_path = (
            os.environ.get('OBSIDIAN_VAULT_PATH') or
            config.get('obsidian', {}).get('vault_path') or
            config.get('storage', {}).get('obsidian_vault')
        )
        self._obsidian_client: Optional[ObsidianMCPClient] = None
        self._vault_path = vault_path

        # ISS-035: Entity extraction and graph persistence
        self._init_graph_services(data_dir, os)

        logger.info(f"Production features initialized: data_dir={data_dir}")

    def _init_graph_services(self, data_dir: Path, os_module) -> None:
        """Initialize graph and HippoRAG services. NASA Rule 10: 25 LOC"""
        self.graph_service = GraphService(data_dir=str(data_dir))

        # Load existing graph if present
        graph_file = data_dir / 'graph.json'
        if graph_file.exists():
            self.graph_service.load_graph(graph_file)
            logger.info(f"Loaded existing graph: {self.graph_service.get_node_count()} nodes")

        # Initialize entity service for NER extraction
        try:
            self.entity_service = EntityService()
            logger.info("EntityService initialized for graph population")
            self.hipporag_service = HippoRagService(
                graph_service=self.graph_service,
                entity_service=self.entity_service
            )
        except Exception as e:
            logger.warning(f"EntityService init failed (graph features disabled): {e}")
            self.entity_service = None
            self.hipporag_service = None

        # Beads task management integration
        beads_binary = os_module.environ.get('BEADS_BINARY', 'bd')
        self.beads_bridge = BeadsBridge(beads_binary=beads_binary, cache_ttl=60)
        logger.info(f"BeadsBridge initialized: binary={beads_binary}")

        # MEM-QWEN-005: Visual Memory Sidecar (lazy init)
        self._visual_service: Optional[VisualMemoryService] = None
        self._unified_router: Optional[UnifiedSearchRouter] = None
        self._visual_config = self.config.get('visual_memory', {})

    @property
    def visual_service(self) -> Optional[VisualMemoryService]:
        """MEM-QWEN-005: Lazy load VisualMemoryService."""
        if self._visual_service is None and self._visual_config.get('enabled', False):
            self._init_visual_memory()
        return self._visual_service

    @property
    def unified_router(self) -> Optional[UnifiedSearchRouter]:
        """MEM-QWEN-005: Lazy load UnifiedSearchRouter."""
        if self._unified_router is None and self._visual_config.get('enabled', False):
            self._init_visual_memory()
        return self._unified_router

    def _init_visual_memory(self) -> None:
        """MEM-QWEN-005: Initialize Visual Memory Sidecar."""
        try:
            embedder_config = self._visual_config.get('embedder', {})
            indexer_config = self._visual_config.get('indexer', {})
            router_config = self._visual_config.get('router', {})

            # Initialize Qwen3-VL embedder
            self._qwen_embedder = Qwen3VLEmbedder(
                model_name=embedder_config.get('model_name'),
                device=embedder_config.get('device'),
                use_mrl=embedder_config.get('use_mrl', True),
                target_dim=embedder_config.get('target_dim', 384),
                enabled=True
            )

            # Initialize visual memory indexer
            self._visual_indexer = VisualMemoryIndexer(
                persist_directory=indexer_config.get('persist_directory', './chroma_visual'),
                collection_name=indexer_config.get('collection_name', 'visual_memories')
            )

            # Initialize visual memory service
            self._visual_service = VisualMemoryService(
                embedder=self._qwen_embedder,
                indexer=self._visual_indexer,
                enabled=True
            )

            # Initialize unified search router
            self._unified_router = UnifiedSearchRouter(
                nexus_processor=self.nexus_processor,
                visual_memory_service=self._visual_service,
                visual_weight=router_config.get('visual_weight', 0.3),
                text_weight=router_config.get('text_weight', 0.7)
            )

            logger.info("Visual Memory Sidecar initialized successfully")

        except Exception as e:
            logger.warning(f"Visual Memory Sidecar init failed (disabled): {e}")
            self._visual_service = None
            self._unified_router = None

    @property
    def obsidian_client(self) -> Optional[ObsidianMCPClient]:
        """C3.2: Lazy load ObsidianClient."""
        if self._obsidian_client is None and self._vault_path:
            try:
                self._obsidian_client = ObsidianMCPClient(
                    vault_path=self._vault_path,
                    chunker=self.vector_search_tool.chunker,
                    embedder=self.vector_search_tool.embedder,
                    indexer=self.vector_search_tool.indexer
                )
                logger.info(f"ObsidianClient initialized: {self._vault_path}")
            except Exception as e:
                logger.warning(f"ObsidianClient init failed: {e}")
        return self._obsidian_client

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """C3.3: Log event to event store."""
        from ..stores.event_log import EventType
        try:
            event_type_map = {
                "vector_search": EventType.QUERY_EXECUTED,
                "memory_store": EventType.CHUNK_ADDED,
                "chunk_added": EventType.CHUNK_ADDED,
                "chunk_updated": EventType.CHUNK_UPDATED,
                "chunk_deleted": EventType.CHUNK_DELETED,
                "query_executed": EventType.QUERY_EXECUTED,
                "entity_consolidated": EventType.ENTITY_CONSOLIDATED,
                "lifecycle_transition": EventType.LIFECYCLE_TRANSITION
            }
            enum_type = event_type_map.get(event_type, EventType.QUERY_EXECUTED)
            self.event_log.log_event(event_type=enum_type, data=data)
        except Exception as e:
            logger.warning(f"Event logging failed: {e}")

    def get_session_preference(self, key: str, default: str = "") -> str:
        """C3.4: Get session preference from KV store."""
        try:
            value = self.kv_store.get(f"session:{key}")
            return value if value is not None else default
        except Exception as e:
            logger.warning(f"Failed to get session preference {key}: {e}")
            return default

    def create_query_trace(self, query: str, mode: str) -> QueryTrace:
        """C3.6: Create query trace for debugging."""
        trace = QueryTrace.create(
            query=query,
            user_context={"mode": mode, "source": "mcp_stdio"}
        )
        trace.mode_detected = mode
        return trace

    @property
    def nexus_processor(self) -> Optional[NexusProcessor]:
        """Lazy load NexusProcessor with all 3 tiers."""
        if self._nexus_processor is None:
            self._nexus_processor = self._init_nexus_processor()
        return self._nexus_processor

    def _init_nexus_processor(self) -> Optional[NexusProcessor]:
        """Initialize NexusProcessor with Vector + Graph + Bayesian + Reranker."""
        try:
            # MEM-003: Reuse self.graph_service instead of creating new instance
            # This ensures NexusProcessor uses the same graph that was loaded from graph.json
            graph_query_engine = GraphQueryEngine(graph_service=self.graph_service)

            # ISS-018 fix: Build Bayesian network from knowledge graph
            bayesian_network = self._build_bayesian_network(self.graph_service)

            probabilistic_engine = ProbabilisticQueryEngine(
                timeout_seconds=1.0,
                network=bayesian_network
            )

            # MEM-QWEN-002: Initialize cross-encoder reranker
            reranker = self._init_reranker()

            processor = NexusProcessor(
                vector_indexer=self.vector_search_tool.indexer,
                graph_query_engine=graph_query_engine,
                probabilistic_query_engine=probabilistic_engine,
                embedding_pipeline=self.vector_search_tool.embedder,
                reranker=reranker,
                rerank_enabled=reranker is not None
            )
            rerank_status = "enabled" if reranker else "disabled"
            logger.info(f"NexusProcessor initialized with all 3 tiers + reranker ({rerank_status})")
            return processor
        except Exception as e:
            logger.warning(f"NexusProcessor init failed, using fallback: {e}")
            return None

    def _init_reranker(self) -> Optional[RerankerService]:
        """MEM-QWEN-002: Initialize cross-encoder reranker service."""
        try:
            # Get reranker config (defaults to small model for low latency)
            rerank_config = self.config.get('reranker', {})
            model_size = rerank_config.get('model_size', 'small')
            model_name = rerank_config.get('model_name')
            enabled = rerank_config.get('enabled', True)

            if not enabled:
                logger.info("Reranker disabled in config")
                return None

            reranker = RerankerService(
                model_name=model_name,
                model_size=model_size,
                max_length=rerank_config.get('max_length', 512),
                batch_size=rerank_config.get('batch_size', 32),
                enabled=True
            )
            logger.info(f"RerankerService initialized: model_size={model_size}")
            return reranker
        except Exception as e:
            logger.warning(f"Reranker init failed (disabled): {e}")
            return None

    @staticmethod
    def _build_bayesian_network(graph_service: GraphService):
        """Build Bayesian network from knowledge graph."""
        try:
            network_builder = NetworkBuilder(max_nodes=1000)
            network = network_builder.build_network(graph_service.graph)
            if network:
                logger.info("Bayesian network built successfully")
            return network
        except Exception as e:
            logger.warning(f"Bayesian network build failed: {e}")
            return None

    def execute(
        self,
        query: str,
        limit: int = 5,
        mode: str = "execution"
    ) -> List[Dict[str, Any]]:
        """Execute search through NexusProcessor or fallback."""
        if self.nexus_processor:
            try:
                result = self._execute_nexus(query, mode, limit)
                logger.info(f"NexusProcessor success: {len(result)} results")
                return result
            except Exception as e:
                logger.warning(f"NexusProcessor failed, falling back: {e}")

        logger.info("Using fallback VectorSearchTool")
        return self.vector_search_tool.execute(query, limit)

    def _execute_nexus(
        self,
        query: str,
        mode: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute via NexusProcessor and format results."""
        nexus_result = self.nexus_processor.process(
            query=query,
            mode=mode,
            top_k=50,
            token_budget=10000
        )

        all_results = nexus_result["core"] + nexus_result["extended"]
        limited_results = all_results[:limit]

        formatted = []
        for result in limited_results:
            formatted.append({
                "text": result.get("text", ""),
                "score": result.get("hybrid_score", result.get("score", 0.0)),
                "file_path": result.get("metadata", {}).get("file_path", ""),
                "chunk_index": result.get("metadata", {}).get("chunk_index", 0),
                "tier": result.get("tier", "unknown"),
                "metadata": result.get("metadata", {})
            })

        return formatted


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "memory-mcp.yaml"
    assert config_path.exists(), f"Config not found: {config_path}"

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config


def apply_migrations(config: Dict[str, Any]) -> None:
    """C3.7: Apply pending database migrations on startup."""
    migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    data_dir = Path(config.get('storage', {}).get('data_dir', './data'))
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "query_traces.db"

    if not migrations_dir.exists():
        return

    try:
        conn = sqlite3.connect(str(db_path))
        migration_file = migrations_dir / "007_query_traces_table.sql"
        if migration_file.exists():
            with open(migration_file, 'r') as f:
                conn.executescript(f.read())
        conn.close()
    except Exception as e:
        logger.warning(f"Database migration failed: {e}")
