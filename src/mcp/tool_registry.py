"""
Tool Registry Module - MCP tool definitions and schemas.

Contains all tool schemas for the Memory MCP system.
Extracted from stdio_server.py as part of MEM-CLEAN-003.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, Any, List

REGISTRY_VERSION = "1.0.0"


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Return list of available MCP tools with their schemas."""
    return [
        _vector_search_tool(),
        _unified_search_tool(),
        _memory_store_tool(),
        _graph_query_tool(),
        _bayesian_inference_tool(),
        _entity_extraction_tool(),
        _hipporag_retrieve_tool(),
        _detect_mode_tool(),
        _lifecycle_status_tool(),
        _obsidian_sync_tool(),
        _beads_ready_tasks_tool(),
        _beads_task_detail_tool(),
        _beads_query_tasks_tool(),
    ]


def _vector_search_tool() -> Dict[str, Any]:
    """Vector search tool definition."""
    return {
        "name": "vector_search",
        "version": REGISTRY_VERSION,
        "description": "Search memory vault using semantic similarity with mode-aware context adaptation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "limit": {"type": "integer", "description": "Number of results", "default": 5},
                "mode": {
                    "type": "string",
                    "description": "Query mode: execution, planning, or brainstorming",
                    "enum": ["execution", "planning", "brainstorming"],
                    "default": "execution"
                }
            },
            "required": ["query"]
        }
    }


def _unified_search_tool() -> Dict[str, Any]:
    """Unified Nexus search tool definition."""
    return {
        "name": "unified_search",
        "version": REGISTRY_VERSION,
        "description": "Full Nexus 5-step search (RECALL, FILTER, DEDUPE, RANK, COMPRESS)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "limit": {"type": "integer", "description": "Number of results", "default": 5},
                "mode": {
                    "type": "string",
                    "description": "Query mode: execution, planning, or brainstorming",
                    "enum": ["execution", "planning", "brainstorming"],
                    "default": "execution"
                }
            },
            "required": ["query"]
        }
    }


def _memory_store_tool() -> Dict[str, Any]:
    """Memory store tool definition."""
    return {
        "name": "memory_store",
        "version": REGISTRY_VERSION,
        "description": "Store information in memory vault with automatic layer assignment",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Content to store"},
                "metadata": {"type": "object", "description": "Optional metadata"}
            },
            "required": ["text"]
        }
    }


def _graph_query_tool() -> Dict[str, Any]:
    """Graph query tool definition."""
    return {
        "name": "graph_query",
        "version": REGISTRY_VERSION,
        "description": "Query knowledge graph using HippoRAG multi-hop reasoning",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query text for graph search"},
                "max_hops": {"type": "integer", "description": "Maximum hops", "default": 3},
                "limit": {"type": "integer", "description": "Number of results", "default": 10}
            },
            "required": ["query"]
        }
    }


def _bayesian_inference_tool() -> Dict[str, Any]:
    """Bayesian inference tool definition."""
    return {
        "name": "bayesian_inference",
        "version": REGISTRY_VERSION,
        "description": "Run probabilistic inference on memory graph",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query text"},
                "evidence": {"type": "object", "description": "Evidence mapping"}
            },
            "required": ["query"]
        }
    }


def _entity_extraction_tool() -> Dict[str, Any]:
    """Entity extraction tool definition."""
    return {
        "name": "entity_extraction",
        "version": REGISTRY_VERSION,
        "description": "Extract named entities from text using NER",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to extract entities from"},
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity types to extract (e.g., PERSON, ORG, CONCEPT)",
                    "default": ["PERSON", "ORG", "GPE", "CONCEPT"]
                }
            },
            "required": ["text"]
        }
    }


def _hipporag_retrieve_tool() -> Dict[str, Any]:
    """HippoRAG retrieve tool definition."""
    return {
        "name": "hipporag_retrieve",
        "version": REGISTRY_VERSION,
        "description": "Full HippoRAG pipeline: entity extraction + graph query + ranking",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query text"},
                "limit": {"type": "integer", "description": "Number of results", "default": 10},
                "mode": {
                    "type": "string",
                    "enum": ["execution", "planning", "brainstorming"],
                    "default": "execution"
                }
            },
            "required": ["query"]
        }
    }


def _detect_mode_tool() -> Dict[str, Any]:
    """Detect mode tool definition."""
    return {
        "name": "detect_mode",
        "version": REGISTRY_VERSION,
        "description": "Detect query mode (execution/planning/brainstorming) from text",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query to analyze for mode"}
            },
            "required": ["query"]
        }
    }


def _lifecycle_status_tool() -> Dict[str, Any]:
    """Lifecycle status tool definition."""
    return {
        "name": "lifecycle_status",
        "version": REGISTRY_VERSION,
        "description": "Get memory lifecycle statistics",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }


def _obsidian_sync_tool() -> Dict[str, Any]:
    """Obsidian sync tool definition."""
    return {
        "name": "obsidian_sync",
        "version": REGISTRY_VERSION,
        "description": "Sync Obsidian vault to memory system (C3.2)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File extensions to sync (default: ['.md'])",
                    "default": [".md"]
                }
            },
            "required": []
        }
    }


def _beads_ready_tasks_tool() -> Dict[str, Any]:
    """Beads ready tasks tool definition."""
    return {
        "name": "beads_ready_tasks",
        "version": REGISTRY_VERSION,
        "description": "Get unblocked Beads tasks ready for work",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max tasks to return", "default": 10},
                "brief": {"type": "boolean", "description": "Return brief info only", "default": True}
            },
            "required": []
        }
    }


def _beads_task_detail_tool() -> Dict[str, Any]:
    """Beads task detail tool definition."""
    return {
        "name": "beads_task_detail",
        "version": REGISTRY_VERSION,
        "description": "Get full details of a Beads task including dependencies and comments",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The task ID to retrieve"}
            },
            "required": ["task_id"]
        }
    }


def _beads_query_tasks_tool() -> Dict[str, Any]:
    """Beads query tasks tool definition."""
    return {
        "name": "beads_query_tasks",
        "version": REGISTRY_VERSION,
        "description": "Query Beads tasks with filters (status, priority, assignee)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status (open, in_progress, done)"},
                "priority": {"type": "integer", "description": "Filter by priority (1-5)"},
                "assignee": {"type": "string", "description": "Filter by assignee"},
                "limit": {"type": "integer", "description": "Max tasks to return", "default": 20}
            },
            "required": []
        }
    }


# Backwards compatibility alias
def handle_list_tools() -> List[Dict[str, Any]]:
    """Backwards compatibility wrapper for get_tool_definitions."""
    return get_tool_definitions()
