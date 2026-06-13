import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _read_message() -> Tuple[Optional[Dict[str, Any]], str]:
    first = sys.stdin.buffer.readline()
    if not first:
        return None, "none"

    # LSP-style framing, allowing any header order.
    if b":" in first and not first.lstrip().startswith(b"{"):
        content_length = None
        header_line = first
        while True:
            if header_line.lower().startswith(b"content-length:"):
                content_length = int(header_line.split(b":", 1)[1].strip())

            line = sys.stdin.buffer.readline()
            if not line:
                return None, "framed"
            if line in (b"\r\n", b"\n"):
                break
            header_line = line

        if content_length is None:
            return None, "framed"

        payload = sys.stdin.buffer.read(content_length)
        if not payload:
            return None, "framed"
        return json.loads(payload.decode("utf-8")), "framed"

    line = first.decode("utf-8").strip()
    if not line:
        return None, "line"
    return json.loads(line), "line"


def _write_message(message: Dict[str, Any], mode: str) -> None:
    if mode == "framed":
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return

    sys.stdout.write(json.dumps(message, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _handle_initialize(message: Dict[str, Any]) -> Dict[str, Any]:
    protocol_version = message.get("params", {}).get("protocolVersion") or "2024-11-05"
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "protocolVersion": protocol_version,
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "memory-mcp-triple-system",
                "version": "1.5.0",
            },
        },
    }


def _dispatch(stdio_server: Any, message: Dict[str, Any], tool: Any) -> Dict[str, Any]:
    try:
        response = stdio_server._process_message(message, tool)
    except TypeError:
        response = stdio_server.process_message(json.dumps(message))

    if isinstance(response, str):
        return json.loads(response) if response else {}
    return response


def main() -> None:
    root = Path(os.environ["MEMORY_MCP_ROOT"])
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    original_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        from src.mcp import stdio_server
    finally:
        sys.stdout = original_stdout

    try:
        stdio_server.logger.remove()
    except AttributeError:
        from loguru import logger
        logger.remove()

    config = stdio_server.load_config()
    stdio_server._apply_migrations(config)
    tool = stdio_server.NexusSearchTool(config)
    try:
        from src.mcp import protocol_handler
        protocol_handler._nexus_tool = tool
    except Exception:
        pass

    while True:
        message, mode = _read_message()
        if message is None:
            break

        if message.get("id") is None:
            continue

        method = message.get("method")
        if method == "initialize":
            response = _handle_initialize(message)
        elif method == "ping":
            response = {"jsonrpc": "2.0", "id": message.get("id"), "result": {}}
        else:
            response = _dispatch(stdio_server, message, tool)

        _write_message(response, mode)


if __name__ == "__main__":
    main()
