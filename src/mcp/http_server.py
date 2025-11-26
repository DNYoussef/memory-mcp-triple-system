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
from typing import Dict, Any, Optional
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
from src.routing.query_router import QueryRouter, QueryMode


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


def get_indexer() -> VectorIndexer:
    """Lazy initialize VectorIndexer."""
    global _indexer
    if _indexer is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        _indexer = VectorIndexer(persist_directory=persist_dir)
    return _indexer


def get_embedder() -> EmbeddingPipeline:
    """Lazy initialize EmbeddingPipeline."""
    global _embedder
    if _embedder is None:
        _embedder = EmbeddingPipeline()
    return _embedder


def get_mode_detector() -> ModeDetector:
    """Lazy initialize ModeDetector."""
    global _mode_detector
    if _mode_detector is None:
        _mode_detector = ModeDetector()
    return _mode_detector


def get_router() -> QueryRouter:
    """Lazy initialize QueryRouter."""
    global _router
    if _router is None:
        _router = QueryRouter()
    return _router


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


class ObsidianSyncRequest(BaseModel):
    vault_path: str = Field(..., description="Path to Obsidian vault")


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


@app.post("/tools/vector_search")
async def vector_search(request: VectorSearchRequest) -> Dict[str, Any]:
    """Semantic vector search."""
    try:
        indexer = get_indexer()
        embedder = get_embedder()
        mode_detector = get_mode_detector()

        # Detect mode if not provided
        mode = request.mode
        if not mode:
            detection = mode_detector.detect_mode(request.query)
            mode = detection.mode.value

        # Generate query embedding
        query_embedding = embedder.encode([request.query])[0]

        # Search
        results = indexer.search_similar(
            query_embedding=query_embedding.tolist(),
            top_k=request.limit
        )

        return {
            "content": [{"type": "text", "text": r.get("document", "")} for r in results],
            "mode": mode,
            "count": len(results),
            "query": request.query
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

        # Generate embedding
        embedding = embedder.encode([request.text])[0]

        # Create chunk
        chunk = {
            "text": request.text,
            "file_path": request.metadata.get("file_path", "/memory/stored.md"),
            "chunk_index": 0,
            "metadata": {
                **request.metadata,
                "stored_at": datetime.utcnow().isoformat(),
                "source": "http_api"
            }
        }

        # Index
        indexer.index_chunks([chunk], [embedding.tolist()])

        return {
            "success": True,
            "stored_at": datetime.utcnow().isoformat(),
            "text_length": len(request.text),
            "metadata": request.metadata
        }
    except Exception as e:
        logger.error(f"Memory store failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/detect_mode")
async def detect_mode(request: DetectModeRequest) -> Dict[str, Any]:
    """Detect query mode."""
    try:
        detector = get_mode_detector()
        result = detector.detect_mode(request.query)

        return {
            "mode": result.mode.value,
            "confidence": result.confidence,
            "token_budget": result.token_budget,
            "core_size": result.core_size,
            "extended_size": result.extended_size
        }
    except Exception as e:
        logger.error(f"Mode detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/graph_query")
async def graph_query(request: GraphQueryRequest) -> Dict[str, Any]:
    """Graph-based query (placeholder - returns vector results)."""
    try:
        # For now, delegate to vector search
        # Full graph query requires GraphService wiring
        indexer = get_indexer()
        embedder = get_embedder()

        query_embedding = embedder.encode([request.query])[0]
        results = indexer.search_similar(
            query_embedding=query_embedding.tolist(),
            top_k=5
        )

        return {
            "content": [{"type": "text", "text": r.get("document", "")} for r in results],
            "query": request.query,
            "max_hops": request.max_hops,
            "implementation": "vector_fallback"
        }
    except Exception as e:
        logger.error(f"Graph query failed: {e}")
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
    port = int(os.getenv("MEMORY_MCP_HTTP_PORT", "8080"))

    logger.info(f"Starting Memory MCP HTTP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
