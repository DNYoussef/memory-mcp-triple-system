"""
MCP Protocol Handler — JSON-RPC over stdio.

Minimal implementation to satisfy stdio_server.py re-exports.
Routes MCP protocol messages to the existing request_router handlers.

This file was missing from the repo (never committed), breaking stdio transport.
"""

import json
import sys
from typing import Any, Dict

from loguru import logger

# Module-level singleton for NexusSearchTool (avoid OOM from re-init per call)
_nexus_tool = None

from .tool_registry import get_tool_definitions  # noqa: E402


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
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None,
            }
        )

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
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": req_id,
            }
        )

    try:
        result = handler(params)
        return json.dumps({"jsonrpc": "2.0", "result": result, "id": req_id})
    except Exception as e:
        logger.error(f"Handler error for {method}: {e}")
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }
        )


def _read_stdio_message() -> tuple[str, bool]:
    """Read either Content-Length framed MCP or newline-delimited JSON."""
    first = sys.stdin.buffer.readline()
    if not first:
        return "", False

    if b":" in first and not first.lstrip().startswith(b"{"):
        content_length = None
        header = first
        while True:
            if header.lower().startswith(b"content-length:"):
                content_length = int(header.split(b":", 1)[1].strip())
            header = sys.stdin.buffer.readline()
            if not header or header in (b"\r\n", b"\n"):
                break
        if not content_length:
            return "", True
        return sys.stdin.buffer.read(content_length).decode("utf-8"), True

    return first.decode("utf-8").strip(), False


def _write_stdio_response(response: str, framed: bool) -> None:
    """Write a JSON-RPC response using the request framing mode."""
    if framed:
        data = response.encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return

    sys.stdout.write(response + "\n")
    sys.stdout.flush()


def main():
    """Main stdio loop — read JSON-RPC messages from stdin, write to stdout."""
    logger.info("Memory MCP stdio server starting...")
    while True:
        message, framed = _read_stdio_message()
        if not message:
            break
        response = process_message(message)
        if response:
            _write_stdio_response(response, framed)
