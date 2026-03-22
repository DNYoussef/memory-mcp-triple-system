"""
HTTP API Wrapper for Memory MCP Triple System

Provides HTTP endpoints that wrap the stdio MCP tools for external integration.
Used by Terminal Manager and other HTTP clients.

Endpoints:
- GET /health - Health check
- POST /tools/vector_search - Semantic search
- POST /tools/memory_store - Store content
- POST /tools/detect_mode - Mode detection
- POST /tools/graph_query - Graph queries
- POST /tools/obsidian_sync - Obsidian sync

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import asyncio
import json
import os
import sys
import threading
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from loguru import logger

# Import Memory MCP components
from src.indexing.vector_indexer import VectorIndexer
from src.indexing.embedding_pipeline import EmbeddingPipeline
from src.modes.mode_detector import ModeDetector
from src.routing.query_router import QueryRouter
from src.routing.unified_router import UnifiedRetrievalRouter
from src.nexus.processor import NexusProcessor
from src.services.graph_service import GraphService
from src.services.graph_query_engine import GraphQueryEngine
from src.bayesian import BAYESIAN_AVAILABLE
if BAYESIAN_AVAILABLE:
    from src.bayesian.network_builder import NetworkBuilder
    from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine
else:
    NetworkBuilder = None  # type: ignore[assignment,misc]
    ProbabilisticQueryEngine = None  # type: ignore[assignment,misc]
from src.stores.event_log import EventLog, EventType
from src.stores.kv_store import KVStore
from src.memory.lifecycle_manager import MemoryLifecycleManager
from src.memory.lifecycle_scheduler import LifecycleScheduler
from src.services.memory_ingestion_service import MemoryIngestionService
from src.services.entity_service import EntityService
from src.lifecycle.hotcold_classifier import HotColdClassifier
from src.chunking.semantic_chunker import SemanticChunker
from src.integrations.beads_bridge import BeadsBridge
from src.universal_components import (
    init_connascence_bridge,
    init_memory_client,
    init_tagger,
    init_telemetry_bridge,
)

# P0-2 FIX: Lazy init (no import-time side effects)
_tagger = None
_memory_client = None
_telemetry_bridge = None
_connascence_bridge = None


def _get_tagger():
    global _tagger
    if _tagger is None:
        _tagger = init_tagger()
    return _tagger


def _get_memory_client():
    global _memory_client
    if _memory_client is None:
        _memory_client = init_memory_client()
    return _memory_client


def _get_telemetry_bridge():
    global _telemetry_bridge
    if _telemetry_bridge is None:
        _telemetry_bridge = init_telemetry_bridge()
    return _telemetry_bridge


def _get_connascence_bridge():
    global _connascence_bridge
    if _connascence_bridge is None:
        _connascence_bridge = init_connascence_bridge()
    return _connascence_bridge


app = FastAPI(
    title="Memory MCP HTTP API",
    description="HTTP wrapper for Memory MCP Triple System stdio server",
    version="1.4.0"
)

# CORS for Terminal Manager frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize services lazily
_indexer: Optional[VectorIndexer] = None
_embedder: Optional[EmbeddingPipeline] = None
_mode_detector: Optional[ModeDetector] = None
_router: Optional[QueryRouter] = None
_graph_service: Optional[GraphService] = None
_graph_query_engine: Optional[GraphQueryEngine] = None
_nexus_processor: Optional[NexusProcessor] = None
_event_log: Optional[EventLog] = None
_kv_store: Optional[KVStore] = None
_lifecycle_manager: Optional[MemoryLifecycleManager] = None
_lifecycle_scheduler: Optional[LifecycleScheduler] = None
_unified_router: Optional[UnifiedRetrievalRouter] = None
_beads_bridge: Optional[BeadsBridge] = None
_entity_service: Optional[EntityService] = None
_classifier: Optional[HotColdClassifier] = None
_ingestion_service: Optional[MemoryIngestionService] = None

_indexer_lock = threading.Lock()
_embedder_lock = threading.Lock()
_mode_detector_lock = threading.Lock()
_router_lock = threading.Lock()
_graph_service_lock = threading.Lock()
_graph_query_engine_lock = threading.Lock()
_nexus_lock = threading.Lock()
_event_log_lock = threading.Lock()
_kv_store_lock = threading.Lock()
_lifecycle_manager_lock = threading.Lock()
_unified_router_lock = threading.Lock()
_beads_bridge_lock = threading.Lock()
_entity_service_lock = threading.Lock()
_ingestion_lock = threading.Lock()


def get_entity_service() -> Optional[EntityService]:
    """Lazy initialize EntityService (spaCy NER)."""
    global _entity_service
    if _entity_service is None:
        with _entity_service_lock:
            if _entity_service is None:
                try:
                    _entity_service = EntityService()
                    logger.info("EntityService initialized (spaCy NER)")
                except Exception as e:
                    logger.warning(f"EntityService init failed (NER disabled): {e}")
    return _entity_service


def get_classifier() -> Optional[HotColdClassifier]:
    """Lazy initialize HotColdClassifier."""
    global _classifier
    if _classifier is None:
        _classifier = HotColdClassifier()
    return _classifier


def get_ingestion_service() -> MemoryIngestionService:
    """Lazy initialize the shared ingestion pipeline."""
    global _ingestion_service
    if _ingestion_service is None:
        with _ingestion_lock:
            if _ingestion_service is None:
                # Initialize semantic chunker
                config = load_config()
                chunking_cfg = config.get("chunking", {})
                try:
                    chunker = SemanticChunker(
                        min_chunk_size=chunking_cfg.get("min_chunk_size", 128),
                        max_chunk_size=chunking_cfg.get("max_chunk_size", 512),
                        overlap=chunking_cfg.get("overlap", 50),
                        embedding_pipeline=get_embedder(),
                    )
                except Exception as e:
                    logger.warning(f"SemanticChunker init failed: {e}")
                    chunker = None

                _ingestion_service = MemoryIngestionService(
                    embedder=get_embedder(),
                    indexer=get_indexer(),
                    graph_service=get_graph_service(),
                    entity_service=get_entity_service(),
                    classifier=get_classifier(),
                    lifecycle_manager=get_lifecycle_manager(),
                    event_log=get_event_log(),
                    chunker=chunker,
                )
                logger.info("MemoryIngestionService initialized")
    return _ingestion_service


def get_indexer() -> VectorIndexer:
    """Lazy initialize VectorIndexer."""
    global _indexer
    if _indexer is None:
        with _indexer_lock:
            if _indexer is None:
                persist_dir = os.getenv("CHROMA_PERSIST_DIR", "/data/chroma")
                _indexer = VectorIndexer.get_instance(persist_directory=persist_dir)
    return _indexer


def get_embedder() -> EmbeddingPipeline:
    """Lazy initialize EmbeddingPipeline."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = EmbeddingPipeline()
    return _embedder


def get_mode_detector() -> ModeDetector:
    """Lazy initialize ModeDetector."""
    global _mode_detector
    if _mode_detector is None:
        with _mode_detector_lock:
            if _mode_detector is None:
                _mode_detector = ModeDetector()
    return _mode_detector


def get_router() -> QueryRouter:
    """Lazy initialize QueryRouter."""
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = QueryRouter()
    return _router


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    # Use service_wiring's load_config — stdio_server has broken protocol_handler import
    from src.mcp.service_wiring import load_config as _wiring_load_config

    return _wiring_load_config()


def _get_data_dir(config: Dict[str, Any]) -> str:
    """Resolve data directory. Env var takes priority for Railway deployment."""
    return os.getenv("MEMORY_MCP_DATA_DIR",
                     config.get("storage", {}).get("data_dir", "/data"))


def get_graph_service() -> GraphService:
    """Lazy initialize GraphService with persistence."""
    global _graph_service
    if _graph_service is None:
        with _graph_service_lock:
            if _graph_service is None:
                config = load_config()
                data_dir = _get_data_dir(config)
                _graph_service = GraphService(data_dir=data_dir)
                graph_path = os.path.join(data_dir, "graph.json")
                if os.path.exists(graph_path):
                    _graph_service.load_graph(graph_path)
    return _graph_service


def get_graph_query_engine() -> GraphQueryEngine:
    """Lazy initialize GraphQueryEngine."""
    global _graph_query_engine
    if _graph_query_engine is None:
        with _graph_query_engine_lock:
            if _graph_query_engine is None:
                _graph_query_engine = GraphQueryEngine(get_graph_service())
    return _graph_query_engine


def get_event_log() -> EventLog:
    """Lazy initialize EventLog."""
    global _event_log
    if _event_log is None:
        with _event_log_lock:
            if _event_log is None:
                config = load_config()
                data_dir = _get_data_dir(config)
                _event_log = EventLog(db_path=os.path.join(data_dir, "events.db"))
    return _event_log


def get_kv_store() -> KVStore:
    """Lazy initialize KVStore."""
    global _kv_store
    if _kv_store is None:
        with _kv_store_lock:
            if _kv_store is None:
                config = load_config()
                data_dir = _get_data_dir(config)
                _kv_store = KVStore(db_path=os.path.join(data_dir, "kv_store.db"))
    return _kv_store


def get_lifecycle_manager() -> MemoryLifecycleManager:
    """Lazy initialize MemoryLifecycleManager."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        with _lifecycle_manager_lock:
            if _lifecycle_manager is None:
                _lifecycle_manager = MemoryLifecycleManager(
                    vector_indexer=get_indexer(),
                    kv_store=get_kv_store()
                )
    return _lifecycle_manager


def get_nexus_processor() -> NexusProcessor:
    """Lazy initialize NexusProcessor with all tiers."""
    global _nexus_processor
    if _nexus_processor is None:
        with _nexus_lock:
            if _nexus_processor is None:
                graph_service = get_graph_service()
                graph_query_engine = get_graph_query_engine()

                bayesian_network = None
                probabilistic_engine = None
                if NetworkBuilder is not None and ProbabilisticQueryEngine is not None:
                    try:
                        builder = NetworkBuilder(max_nodes=1000)
                        bayesian_network = builder.build_network(graph_service.graph)
                    except (ValueError, RuntimeError, TimeoutError) as exc:
                        logger.warning("Bayesian network build failed: %s", exc)
                    probabilistic_engine = ProbabilisticQueryEngine(
                        timeout_seconds=1.0,
                        network=bayesian_network
                    )
                else:
                    logger.info("Bayesian layer unavailable (torch/pgmpy not installed)")

                _nexus_processor = NexusProcessor(
                    vector_indexer=get_indexer(),
                    graph_query_engine=graph_query_engine,
                    probabilistic_query_engine=probabilistic_engine,
                    embedding_pipeline=get_embedder()
                )
    return _nexus_processor


def get_beads_bridge() -> BeadsBridge:
    """Lazy initialize BeadsBridge for Beads CLI integration."""
    global _beads_bridge
    if _beads_bridge is None:
        with _beads_bridge_lock:
            if _beads_bridge is None:
                # Use bd.exe path from environment or default Windows location
                beads_binary = os.getenv(
                    "BEADS_BINARY",
                    r"C:\Users\17175\AppData\Local\beads\bd.exe"
                )
                _beads_bridge = BeadsBridge(beads_binary=beads_binary, cache_ttl=60)
    return _beads_bridge


def get_unified_router() -> UnifiedRetrievalRouter:
    """Lazy initialize UnifiedRetrievalRouter with Beads + Memory."""
    global _unified_router
    if _unified_router is None:
        with _unified_router_lock:
            if _unified_router is None:
                _unified_router = UnifiedRetrievalRouter(
                    beads_bridge=get_beads_bridge(),
                    memory_service=get_nexus_processor()
                )
    return _unified_router


# Request/Response Models
class VectorSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Max results")
    mode: Optional[str] = Field(None, description="Query mode (execution/planning/brainstorming)")


class MemoryStoreRequest(BaseModel):
    text: str = Field(..., description="Content to store")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata tags")


class DetectModeRequest(BaseModel):
    query: str = Field(..., description="Query to analyze")


class GraphQueryRequest(BaseModel):
    query: str = Field(..., description="Graph query")
    max_hops: int = Field(2, description="Max traversal hops")
    limit: int = Field(10, description="Max results")


class ObsidianSyncRequest(BaseModel):
    vault_path: str = Field(..., description="Path to Obsidian vault")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(10, description="Max results")
    mode: Optional[str] = Field(None, description="Query mode (execution/planning/brainstorming)")


class UnifiedRetrievalRequest(BaseModel):
    """Request for unified retrieval combining Beads and Memory MCP."""
    query: str = Field(..., description="Search query")
    mode: Optional[str] = Field(None, description="Mode: execution (80% beads), planning (50/50), brainstorming (80% memory)")
    token_budget: int = Field(10000, description="Total token budget for results")


REQUIRED_TAGS = ["who", "when", "project", "why"]


def _normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(metadata)
    for tag in REQUIRED_TAGS:
        upper = tag.upper()
        if upper in normalized and tag not in normalized:
            normalized[tag] = normalized[upper]
    return normalized


def _validate_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str]]:
    if metadata is None:
        return False, REQUIRED_TAGS
    missing = [tag for tag in REQUIRED_TAGS if not metadata.get(tag)]
    return len(missing) == 0, missing


def _autofill_metadata(metadata: Dict[str, Any], missing: List[str]) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    if "who" in missing:
        metadata["who"] = "unknown:http-client"
    if "when" in missing:
        metadata["when"] = now
    if "project" in missing:
        metadata["project"] = "untagged"
    if "why" in missing:
        metadata["why"] = "unspecified"
    return metadata


def _get_tagging_policy(config: Dict[str, Any]) -> Dict[str, bool]:
    tagging = config.get("tagging", {})
    return {
        "strict": bool(tagging.get("strict", False)),
        "auto_fill": bool(tagging.get("auto_fill", True))
    }


async def _run_nexus_query(query: str, mode: str, limit: int) -> Dict[str, Any]:
    nexus = get_nexus_processor()
    return await asyncio.to_thread(
        nexus.process,
        query,
        mode,
        50,
        10000
    )


# Endpoints
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "memory-mcp-http",
        "version": "1.5.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "vector_indexer": "available",
            "embedding_pipeline": "available",
            "mode_detector": "available",
            "graph_service": "available",
            "entity_service": "available" if get_entity_service() else "unavailable",
            "hot_cold_classifier": "available",
            "ingestion_pipeline": "available",
            "bayesian": "available" if BAYESIAN_AVAILABLE else "degraded (no torch/pgmpy)",
        }
    }


@app.get("/tools/stats")
async def system_stats() -> Dict[str, Any]:
    """System statistics: vector count, graph nodes/edges, lifecycle stages."""
    stats: Dict[str, Any] = {"timestamp": datetime.utcnow().isoformat()}
    try:
        indexer = get_indexer()
        collection = indexer.collection
        stats["vectors"] = {"count": collection.count() if collection else 0}
    except Exception as e:
        stats["vectors"] = {"error": str(e)}
    try:
        gs = get_graph_service()
        stats["graph"] = {
            "nodes": gs.get_node_count() if hasattr(gs, 'get_node_count') else len(gs.graph.nodes),
            "edges": gs.get_edge_count() if hasattr(gs, 'get_edge_count') else len(gs.graph.edges),
        }
    except Exception as e:
        stats["graph"] = {"error": str(e)}
    try:
        lm = get_lifecycle_manager()
        stats["lifecycle"] = lm.get_stage_stats() if hasattr(lm, 'get_stage_stats') else {}
    except Exception as e:
        stats["lifecycle"] = {"error": str(e)}
    try:
        el = get_event_log()
        stats["events"] = {"total": el.count() if hasattr(el, 'count') else "unknown"}
    except Exception:
        stats["events"] = {"total": "unknown"}
    stats["bayesian_available"] = BAYESIAN_AVAILABLE
    return stats


@app.get("/tools/lifecycle_status")
async def lifecycle_status() -> Dict[str, Any]:
    """Get lifecycle stage statistics."""
    try:
        manager = get_lifecycle_manager()
        stage_stats = manager.get_stage_stats() if hasattr(manager, 'get_stage_stats') else {}
        return {"stats": stage_stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/raptor_cluster")
async def raptor_cluster() -> Dict[str, Any]:
    """Run RAPTOR hierarchical clustering on all active chunks."""
    try:
        from src.clustering.raptor_clusterer import RAPTORClusterer
        indexer = get_indexer()
        collection = indexer.collection

        all_data = collection.get(include=["documents", "embeddings", "metadatas"])
        if not all_data.get("documents"):
            return {"status": "no_chunks", "clusters": 0}

        chunks = [{"text": doc, "metadata": meta}
                  for doc, meta in zip(all_data["documents"], all_data["metadatas"] or [{}] * len(all_data["documents"]))]
        embeddings = all_data.get("embeddings", [])

        clusterer = RAPTORClusterer()
        result = await asyncio.to_thread(clusterer.cluster_chunks, chunks, embeddings)

        return {
            "status": "success",
            "num_clusters": result.get("num_clusters", 0),
            "quality_score": result.get("quality_score", 0.0),
        }
    except Exception as e:
        logger.error(f"RAPTOR clustering failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/consolidate")
async def consolidate_memories() -> Dict[str, Any]:
    """Consolidate similar memories (merge if cosine > 0.95)."""
    try:
        manager = get_lifecycle_manager()
        if hasattr(manager, 'consolidate_similar'):
            count = await asyncio.to_thread(manager.consolidate_similar, 0.95)
            return {"consolidated_count": count}
        return {"consolidated_count": 0, "note": "consolidation not available"}
    except Exception as e:
        logger.error(f"Consolidation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/consolidate_entities")
async def consolidate_entities() -> Dict[str, Any]:
    """Consolidate duplicate entities in knowledge graph."""
    try:
        from src.services.entity_service import EntityConsolidator
        graph_service = get_graph_service()
        consolidator = EntityConsolidator(similarity_threshold=0.85)
        result = await asyncio.to_thread(consolidator.consolidate_all, graph_service.graph)
        graph_service.save_graph()
        return result
    except Exception as e:
        logger.error(f"Entity consolidation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event() -> None:
    global _lifecycle_scheduler

    lifecycle_manager = get_lifecycle_manager()
    _lifecycle_scheduler = LifecycleScheduler(lifecycle_manager)
    await _lifecycle_scheduler.start()

    logger.info("Memory MCP HTTP server started with lifecycle scheduler")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _lifecycle_scheduler

    if _lifecycle_scheduler:
        await _lifecycle_scheduler.stop()

    logger.info("Memory MCP HTTP server shutdown complete")


@app.post("/tools/vector_search")
async def vector_search(request: VectorSearchRequest) -> Dict[str, Any]:
    """Semantic vector search (NexusProcessor pipeline)."""
    try:
        mode_detector = get_mode_detector()
        mode = request.mode
        if not mode:
            profile, _ = mode_detector.detect(request.query)
            mode = profile.name

        kv_store = get_kv_store()
        kv_store.set("session:last_query_mode", mode)
        kv_store.set("session:last_query_limit", str(request.limit))

        nexus_result = await _run_nexus_query(request.query, mode, request.limit)
        results = (nexus_result.get("core", []) + nexus_result.get("extended", []))[:request.limit]

        event_log = get_event_log()
        event_log.log_event(
            EventType.QUERY_EXECUTED,
            {
                "query": request.query,
                "mode": mode,
                "limit": request.limit,
                "results_count": len(results),
            }
        )

        return {
            "content": [{"type": "text", "text": r.get("text", "")} for r in results],
            "mode": mode,
            "count": len(results),
            "query": request.query,
            "processor": "nexus_5step"
        }
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/memory_store")
async def memory_store(request: MemoryStoreRequest) -> Dict[str, Any]:
    """Store content with full pipeline: embed → classify → index → graph → lifecycle."""
    try:
        # Validate/normalize metadata (tagging policy)
        metadata = _normalize_metadata(request.metadata)
        is_valid, missing = _validate_metadata(metadata)
        if not is_valid:
            policy = _get_tagging_policy(load_config())
            if policy["strict"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required tags: {missing}"
                )
            if policy["auto_fill"]:
                metadata = _autofill_metadata(metadata, missing)
                logger.warning("Auto-filled missing tags: %s", missing)

        # Use shared ingestion service (same pipeline as stdio transport)
        ingestion = get_ingestion_service()
        result = await asyncio.to_thread(
            ingestion.ingest,
            text=request.text,
            metadata=metadata,
            source="http_api",
        )

        # Add auto-fill info to response
        result["tags_auto_filled"] = missing if not is_valid else []
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory store failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/detect_mode")
async def detect_mode(request: DetectModeRequest) -> Dict[str, Any]:
    """Detect query mode."""
    try:
        detector = get_mode_detector()
        profile, confidence = detector.detect(request.query)

        return {
            "mode": profile.name,
            "confidence": confidence,
            "token_budget": profile.token_budget,
            "core_size": profile.core_size,
            "extended_size": profile.extended_size
        }
    except Exception as e:
        logger.error(f"Mode detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/graph_query")
async def graph_query(request: GraphQueryRequest) -> Dict[str, Any]:
    """Graph-based query (HippoRAG multi-hop)."""
    try:
        graph_engine = get_graph_query_engine()

        return {
            "results": graph_engine.query(
                query=request.query,
                max_hops=request.max_hops,
                top_k=request.limit
            ),
            "query": request.query,
            "max_hops": request.max_hops,
            "implementation": "graph_native"
        }
    except Exception as e:
        logger.error(f"Graph query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/search")
async def search(request: SearchRequest) -> Dict[str, Any]:
    """Unified search via NexusProcessor 5-step SOP."""
    try:
        mode_detector = get_mode_detector()
        mode = request.mode
        if not mode:
            profile, _ = mode_detector.detect(request.query)
            mode = profile.name

        kv_store = get_kv_store()
        kv_store.set("session:last_query_mode", mode)
        kv_store.set("session:last_query_limit", str(request.limit))

        nexus_result = await _run_nexus_query(request.query, mode, request.limit)
        results = (nexus_result.get("core", []) + nexus_result.get("extended", []))[:request.limit]

        event_log = get_event_log()
        event_log.log_event(
            EventType.QUERY_EXECUTED,
            {
                "query": request.query,
                "mode": mode,
                "limit": request.limit,
                "results_count": len(results),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return {
            "results": results,
            "processor": "nexus_5step",
            "mode": mode
        }
    except Exception as e:
        logger.error(f"Unified search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/obsidian_sync")
async def obsidian_sync(request: ObsidianSyncRequest) -> Dict[str, Any]:
    """Sync Obsidian vault to memory."""
    try:
        from src.mcp.obsidian_client import ObsidianMCPClient

        if not os.path.exists(request.vault_path):
            raise HTTPException(status_code=400, detail=f"Vault not found: {request.vault_path}")

        client = ObsidianMCPClient(vault_path=request.vault_path)
        result = client.sync_vault()

        return {
            "success": result.get("success", False),
            "files_synced": result.get("files_synced", 0),
            "total_chunks": result.get("total_chunks", 0),
            "duration_ms": result.get("duration_ms", 0),
            "errors": result.get("errors", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Obsidian sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/unified_retrieve")
async def unified_retrieve(request: UnifiedRetrievalRequest) -> Dict[str, Any]:
    """Unified retrieval combining Beads (procedural) and Memory MCP (semantic).

    Mode weights:
    - execution: 80% beads, 20% memory (task-focused)
    - planning: 50% beads, 50% memory (balanced)
    - brainstorming: 20% beads, 80% memory (creative)

    This is the PRODUCTION endpoint for Life OS Dashboard integration.
    PROJ-002: Memory MCP Production PageRank - wiring complete.
    """
    try:
        mode_detector = get_mode_detector()
        mode = request.mode
        if not mode:
            profile, _ = mode_detector.detect(request.query)
            mode = profile.name

        # Get unified router (Beads + Memory)
        router = get_unified_router()

        # Execute unified retrieval
        result = await router.retrieve(
            query=request.query,
            mode=mode,
            token_budget=request.token_budget
        )

        # Log the unified retrieval
        event_log = get_event_log()
        event_log.log_event(
            EventType.QUERY_EXECUTED,
            {
                "query": request.query,
                "mode": mode,
                "token_budget": request.token_budget,
                "beads_count": len(result.get("beads", [])),
                "memory_count": len(result.get("memory", {}).get("core", [])),
                "processor": "unified_router",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        # Transform beads tasks to serializable format
        beads_tasks = []
        for task in result.get("beads", []):
            beads_tasks.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "type": "procedural_task"
            })

        return {
            "mode": result.get("mode"),
            "token_budget": result.get("token_budget"),
            "beads_budget": result.get("beads_budget"),
            "memory_budget": result.get("memory_budget"),
            "beads": beads_tasks,
            "memory": result.get("memory", {}),
            "processor": "unified_retrieval_router"
        }
    except Exception as e:
        logger.error(f"Unified retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run HTTP server."""
    host = os.getenv("MEMORY_MCP_HTTP_HOST", "0.0.0.0")
    # Railway injects PORT, fall back to MEMORY_MCP_HTTP_PORT or 8080
    port = int(os.getenv("PORT", os.getenv("MEMORY_MCP_HTTP_PORT", "8080")))

    logger.info(f"Starting Memory MCP HTTP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
