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
from src.nexus.processor import NexusProcessor
from src.services.graph_service import GraphService
from src.services.graph_query_engine import GraphQueryEngine
from src.bayesian.network_builder import NetworkBuilder
from src.bayesian.probabilistic_query_engine import ProbabilisticQueryEngine
from src.stores.event_log import EventLog, EventType
from src.stores.kv_store import KVStore
from src.memory.lifecycle_manager import MemoryLifecycleManager
from src.memory.lifecycle_scheduler import LifecycleScheduler
from src.universal_components import (
    init_connascence_bridge,
    init_memory_client,
    init_tagger,
    init_telemetry_bridge,
)

tagger = init_tagger()
memory_client = init_memory_client()
telemetry_bridge = init_telemetry_bridge()
connascence_bridge = init_connascence_bridge()


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


def get_indexer() -> VectorIndexer:
    """Lazy initialize VectorIndexer."""
    global _indexer
    if _indexer is None:
        with _indexer_lock:
            if _indexer is None:
                persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
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
    from src.mcp.stdio_server import load_config as stdio_load

    return stdio_load()


def _get_data_dir(config: Dict[str, Any]) -> str:
    return config.get("storage", {}).get("data_dir", "./data")


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
                try:
                    builder = NetworkBuilder(max_nodes=1000)
                    bayesian_network = builder.build_network(graph_service.graph)
                except Exception as exc:
                    logger.warning("Bayesian network build failed: %s", exc)

                probabilistic_engine = ProbabilisticQueryEngine(
                    timeout_seconds=1.0,
                    network=bayesian_network
                )

                _nexus_processor = NexusProcessor(
                    vector_indexer=get_indexer(),
                    graph_query_engine=graph_query_engine,
                    probabilistic_query_engine=probabilistic_engine,
                    embedding_pipeline=get_embedder()
                )
    return _nexus_processor


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
        "version": "1.4.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "vector_indexer": "available",
            "embedding_pipeline": "available",
            "mode_detector": "available"
        }
    }


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
    """Store content in vector database."""
    try:
        indexer = get_indexer()
        embedder = get_embedder()
        event_log = get_event_log()
        lifecycle_manager = get_lifecycle_manager()

        # Generate embedding
        embedding = embedder.encode([request.text])[0]

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

        # Create chunk
        chunk = {
            "text": request.text,
            "file_path": metadata.get("file_path", "/memory/stored.md"),
            "chunk_index": 0,
            "metadata": {
                **metadata,
                "stored_at": datetime.utcnow().isoformat(),
                "source": "http_api"
            }
        }

        # Index
        indexer.index_chunks([chunk], [embedding.tolist()])

        event_log.log_event(
            EventType.CHUNK_ADDED,
            {
                "text_length": len(request.text),
                "project": metadata.get("project"),
                "tags_auto_filled": missing if not is_valid else [],
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        await asyncio.to_thread(lifecycle_manager.demote_stale_chunks)
        await asyncio.to_thread(lifecycle_manager.archive_demoted_chunks)

        return {
            "success": True,
            "stored_at": datetime.utcnow().isoformat(),
            "text_length": len(request.text),
            "metadata": metadata,
            "tags_auto_filled": missing if not is_valid else []
        }
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


def main():
    """Run HTTP server."""
    host = os.getenv("MEMORY_MCP_HTTP_HOST", "0.0.0.0")
    # Railway injects PORT, fall back to MEMORY_MCP_HTTP_PORT or 8080
    port = int(os.getenv("PORT", os.getenv("MEMORY_MCP_HTTP_PORT", "8080")))

    logger.info(f"Starting Memory MCP HTTP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
