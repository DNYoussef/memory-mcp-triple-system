"""
MCP Server Implementation using FastAPI
Exposes vector search tool for Claude Desktop integration.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import yaml
from pathlib import Path
from loguru import logger

from .tools.vector_search import VectorSearchTool


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    services: Dict[str, str]


class ToolListResponse(BaseModel):
    """Tool list response model."""
    tools: List[Dict[str, Any]]


def load_config() -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Returns:
        Configuration dictionary
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "memory-mcp.yaml"
    assert config_path.exists(), f"Config not found: {config_path}"

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded config from {config_path}")
    return config


def _get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get MCP tool definitions.

    Returns:
        List of tool definition dictionaries
    """
    return [
        {
            "name": "vector_search",
            "description": "Search memory vault using semantic similarity",
            "parameters": {
                "query": {
                    "type": "string",
                    "description": "Search query text"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5
                }
            }
        }
    ]


def create_app() -> FastAPI:
    """
    Create FastAPI application with MCP tools.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Memory MCP Triple System",
        description="MCP server for vector search and memory retrieval",
        version="1.0.0"
    )

    config = load_config()
    vector_search_tool = VectorSearchTool(config)

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint."""
        services = vector_search_tool.check_services()
        status = "healthy" if all(s == "available" for s in services.values()) else "degraded"
        return HealthResponse(status=status, services=services)

    @app.get("/tools", response_model=ToolListResponse)
    async def list_tools() -> ToolListResponse:
        """List available MCP tools."""
        return ToolListResponse(tools=_get_tool_definitions())

    @app.post("/tools/vector_search")
    async def vector_search(query: str, limit: int = 5) -> JSONResponse:
        """Execute vector search tool."""
        try:
            results = vector_search_tool.execute(query, limit)
            return JSONResponse(content={"results": results})
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    logger.info("MCP server initialized")
    return app


if __name__ == "__main__":
    import uvicorn

    config = load_config()
    mcp_config = config.get("mcp", {}).get("server", {})

    host = mcp_config.get("host", "localhost")
    port = mcp_config.get("port", 8080)

    logger.info(f"Starting MCP server on {host}:{port}")
    uvicorn.run(
        "src.mcp.server:create_app",
        host=host,
        port=port,
        factory=True,
        log_level="info"
    )
