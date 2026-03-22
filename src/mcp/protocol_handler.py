"""
MCP Protocol Handler — JSON-RPC over stdio.

Minimal implementation to satisfy stdio_server.py re-exports.
Routes MCP protocol messages to the existing request_router handlers.

This file was missing from the repo (never committed), breaking stdio transport.
"""

import json
import sys
from typing import Any, Dict, List

from loguru import logger

# Module-level singleton for NexusSearchTool (avoid OOM from re-init per call)
_nexus_tool = None

from .tool_registry import get_tool_definitions


def handle_initialize_method(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "serverInfo": {
            "name": "memory-mcp-triple-system",
            "version": "1.5.0",
        },
    }


def handle_tools_list_method(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tools/list request."""
    tools = get_tool_definitions()
    return {"tools": tools}


def handle_tools_call_method(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tools/call request — delegate to request_router."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    # Singleton — do NOT re-create NexusSearchTool on every call (OOM risk)
    global _nexus_tool
    if _nexus_tool is None:
        from .service_wiring import NexusSearchTool, load_config
        config = load_config()
        _nexus_tool = NexusSearchTool(config)

    from .request_router import handle_call_tool
    return handle_call_tool(tool_name, arguments, _nexus_tool)


def process_message(message: str) -> str:
    """Process a single JSON-RPC message and return response."""
    try:
        request = json.loads(message)
    except json.JSONDecodeError as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": f"Parse error: {e}"},
            "id": None,
        })

    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    handlers = {
        "initialize": handle_initialize_method,
        "tools/list": handle_tools_list_method,
        "tools/call": handle_tools_call_method,
    }

    handler = handlers.get(method)
    if handler is None:
        if req_id is None:
            return ""  # Notification — no response needed
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": req_id,
        })

    try:
        result = handler(params)
        return json.dumps({"jsonrpc": "2.0", "result": result, "id": req_id})
    except Exception as e:
        logger.error(f"Handler error for {method}: {e}")
        return json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)},
            "id": req_id,
        })


def main():
    """Main stdio loop — read JSON-RPC messages from stdin, write to stdout."""
    logger.info("Memory MCP stdio server starting...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = process_message(line)
        if response:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
