"""Universal component wiring for memory-mcp-triple-system.

These components (ConnascenceBridge, TelemetryBridge, etc.) live in
~/.claude/library -- a local Claude Code extension library that does
not exist in production Docker containers. All imports are optional.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

LIBRARY_ROOT = Path(os.getenv("CLAUDE_LIBRARY_ROOT", Path.home() / ".claude"))
if LIBRARY_ROOT.exists() and str(LIBRARY_ROOT) not in sys.path:
    sys.path.insert(0, str(LIBRARY_ROOT))

try:
    from library.components.cognitive_architecture.integration.connascence_bridge import ConnascenceBridge
    from library.components.cognitive_architecture.integration.telemetry_bridge import TelemetryBridge
    from library.components.memory.memory_mcp_client import create_memory_mcp_client
    from library.components.observability.tagging_protocol import TaggingProtocol, create_simple_tagger
    LIBRARY_AVAILABLE = True
except ImportError:
    ConnascenceBridge = None  # type: ignore[assignment,misc]
    TelemetryBridge = None  # type: ignore[assignment,misc]
    create_memory_mcp_client = None  # type: ignore[assignment,misc]
    TaggingProtocol = None  # type: ignore[assignment,misc]
    create_simple_tagger = None  # type: ignore[assignment,misc]
    LIBRARY_AVAILABLE = False


def init_tagger():
    if create_simple_tagger is None:
        return None
    return create_simple_tagger(agent_id="memory-mcp-triple-system", project_id="memory-mcp-triple-system")


def init_memory_client():
    if create_memory_mcp_client is None:
        return None
    endpoint = os.getenv("MEMORY_MCP_URL", "http://localhost:3000")
    return create_memory_mcp_client(
        project_id="memory-mcp-triple-system",
        project_name="memory-mcp-triple-system",
        agent_id="memory-mcp-triple-system",
        agent_category="backend",
        capabilities=["memory", "retrieval", "graph"],
        mcp_endpoint=endpoint,
    )


def init_telemetry_bridge(loop_dir: Optional[str] = None):
    if TelemetryBridge is None:
        return None
    resolved = Path(loop_dir) if loop_dir else Path(".loop")
    return TelemetryBridge(loop_dir=resolved)


def init_connascence_bridge():
    if ConnascenceBridge is None:
        return None
    return ConnascenceBridge()
