"""
MCP Server Implementation using stdio protocol - Facade Module.
Compatible with Claude Code's MCP expectations.

This module maintains backwards compatibility by re-exporting from the
decomposed modules created in MEM-CLEAN-003:
- service_wiring.py: NexusSearchTool, config loading, migrations
- tool_registry.py: Tool definitions and schemas
- request_router.py: Tool execution handlers
- protocol_handler.py: MCP protocol and main loop

NASA Rule 10 Compliant: All functions <=60 LOC
"""

# Compatibility import retained for Phase 2 integration tests
from ..nexus.processor import NexusProcessor

# Re-export from service_wiring for backwards compatibility
from .service_wiring import (
    NexusSearchTool as _NexusSearchTool,
    load_config,
    apply_migrations,
    REQUIRED_TAGS,
    get_tagger,
    get_memory_client,
    get_telemetry_bridge,
    get_connascence_bridge,
    EventLog,
    KVStore,
    QueryTrace,
    HotColdClassifier,
    MemoryLifecycleManager,
    ObsidianMCPClient,
)


# P0-2 FIX: Lazy module-level access for backwards compatibility
def __getattr__(name):
    """Lazy load old global names via factory functions."""
    _lazy_map = {
        "tagger": get_tagger,
        "memory_client": get_memory_client,
        "telemetry_bridge": get_telemetry_bridge,
        "connascence_bridge": get_connascence_bridge,
    }
    if name in _lazy_map:
        return _lazy_map[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Re-export from tool_registry
from .tool_registry import (
    get_tool_definitions,
    handle_list_tools,
)

# Re-export from request_router
from .request_router import (
    handle_call_tool as _handle_call_tool,
    handle_vector_search,
    handle_memory_store,
    handle_graph_query,
    handle_entity_extraction,
    handle_hipporag_retrieve,
    handle_detect_mode,
    handle_lifecycle_status,
    handle_bayesian_inference,
    handle_unified_search,
    handle_obsidian_sync,
    handle_beads_ready_tasks,
    handle_beads_task_detail,
    handle_beads_query_tasks,
    _enrich_metadata_with_tagging as _request_router_enrich_metadata_with_tagging,
)

# Re-export from protocol_handler
from .protocol_handler import (
    handle_initialize_method,
    handle_tools_list_method,
    handle_tools_call_method,
    process_message,
    main,
)

# Legacy aliases for internal functions (prefix with underscore)
_handle_vector_search = handle_vector_search
_handle_memory_store = handle_memory_store
_handle_graph_query = handle_graph_query
_handle_entity_extraction = handle_entity_extraction
_handle_hipporag_retrieve = handle_hipporag_retrieve
_handle_detect_mode = handle_detect_mode
_handle_lifecycle_status = handle_lifecycle_status
_handle_bayesian_inference = handle_bayesian_inference
_handle_unified_search = handle_unified_search
_handle_obsidian_sync = handle_obsidian_sync
_handle_beads_ready_tasks = handle_beads_ready_tasks
_handle_beads_task_detail = handle_beads_task_detail
_handle_beads_query_tasks = handle_beads_query_tasks
_handle_initialize_method = handle_initialize_method
_handle_tools_list_method = handle_tools_list_method
_handle_tools_call_method = handle_tools_call_method
_process_message = process_message
_apply_migrations = apply_migrations

# Compatibility schema snippet (kept for integration tests)
VECTOR_SEARCH_SCHEMA_COMPAT = (
    '{"mode": {"type": "string", "enum": ["execution", "planning", "brainstorming"], '
    '"default": "execution"}}'
)


class NexusSearchTool(_NexusSearchTool):
    """Compatibility wrapper for NexusSearchTool."""


def _enrich_metadata_with_tagging(metadata):
    """Compatibility wrapper for tagging protocol in stdio_server."""
    enriched = _request_router_enrich_metadata_with_tagging(dict(metadata or {}))

    agent_name = enriched.get("agent_name", "unknown")
    agent_category = enriched.get("agent_category", "general")
    timestamp_iso = enriched.get("timestamp_iso")
    timestamp_unix = enriched.get("timestamp_unix")
    timestamp_readable = enriched.get("timestamp_readable")

    enriched["agent"] = {"name": agent_name, "category": agent_category}
    enriched["timestamp"] = {
        "iso": timestamp_iso,
        "unix": timestamp_unix,
        "readable": timestamp_readable,
    }
    enriched.setdefault("project", "memory-mcp-triple-system")
    enriched.setdefault("intent", "storage")
    enriched["_tagging_protocol"] = "memory-mcp-triple-system"
    return enriched


def handle_call_tool(tool_name, arguments, tool):
    """Compatibility router with explicit tool_name branches."""
    if tool_name == "vector_search":
        return handle_vector_search(arguments, tool)
    if tool_name == "memory_store":
        return handle_memory_store(arguments, tool)
    if tool_name == "graph_query":
        return handle_graph_query(arguments, tool)
    if tool_name == "entity_extraction":
        return handle_entity_extraction(arguments, tool)
    if tool_name == "hipporag_retrieve":
        return handle_hipporag_retrieve(arguments, tool)
    if tool_name == "detect_mode":
        return handle_detect_mode(arguments, tool)
    if tool_name == "obsidian_sync":
        return handle_obsidian_sync(arguments, tool)
    return _handle_call_tool(tool_name, arguments, tool)

# Expose all public names
__all__ = [
    # Service wiring
    "NexusSearchTool",
    "load_config",
    "apply_migrations",
    "REQUIRED_TAGS",
    "tagger",
    "memory_client",
    "telemetry_bridge",
    "connascence_bridge",
    "EventLog",
    "KVStore",
    "QueryTrace",
    "HotColdClassifier",
    "MemoryLifecycleManager",
    "ObsidianMCPClient",
    # Tool registry
    "get_tool_definitions",
    "handle_list_tools",
    # Request router
    "handle_call_tool",
    "handle_vector_search",
    "handle_memory_store",
    "handle_graph_query",
    "handle_entity_extraction",
    "handle_hipporag_retrieve",
    "handle_detect_mode",
    "handle_lifecycle_status",
    "handle_bayesian_inference",
    "handle_unified_search",
    "handle_obsidian_sync",
    "handle_beads_ready_tasks",
    "handle_beads_task_detail",
    "handle_beads_query_tasks",
    "_enrich_metadata_with_tagging",
    # Protocol handler
    "handle_initialize_method",
    "handle_tools_list_method",
    "handle_tools_call_method",
    "process_message",
    "main",
]


if __name__ == "__main__":
    main()
