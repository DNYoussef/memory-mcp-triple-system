"""
MCP Tool Definitions for Visual Memory.

MEM-QWEN-005: Tool definitions for screenshot/diagram ingestion and cross-modal search.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import List, Dict, Any

# MCP Tool Definitions for Visual Memory
VISUAL_MEMORY_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "ingest_screenshot",
        "description": "Ingest a screenshot into visual memory for later retrieval via cross-modal search",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Absolute path to screenshot image file (PNG, JPG, etc.)"
                },
                "title": {
                    "type": "string",
                    "description": "Title or label for the screenshot"
                },
                "context": {
                    "type": "string",
                    "description": "Contextual description of what the screenshot shows"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata (project, intent, tags, etc.)"
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "ingest_diagram",
        "description": "Ingest a diagram into visual memory for later retrieval via cross-modal search",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Absolute path to diagram image file (PNG, JPG, SVG, etc.)"
                },
                "title": {
                    "type": "string",
                    "description": "Title or label for the diagram"
                },
                "context": {
                    "type": "string",
                    "description": "Contextual description of what the diagram represents"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata (project, intent, tags, etc.)"
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "ingest_visual",
        "description": "Ingest any visual (photo, chart, UI element) into visual memory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Absolute path to image file"
                },
                "visual_type": {
                    "type": "string",
                    "enum": ["screenshot", "diagram", "photo", "chart", "ui_element", "other"],
                    "description": "Type of visual content",
                    "default": "other"
                },
                "title": {
                    "type": "string",
                    "description": "Title or label for the visual"
                },
                "context": {
                    "type": "string",
                    "description": "Contextual description"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "search_visual",
        "description": "Search visual memories with a text query (cross-modal: text finds images)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text search query describing what visual content to find"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 10
                },
                "visual_type": {
                    "type": "string",
                    "enum": ["screenshot", "diagram", "photo", "chart", "ui_element"],
                    "description": "Optional filter by visual type"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "unified_search",
        "description": "Search both text and visual memories with a single query",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "mode": {
                    "type": "string",
                    "enum": ["execution", "planning", "brainstorming"],
                    "description": "Query mode affecting result depth",
                    "default": "execution"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Total number of results",
                    "default": 10
                },
                "include_visual": {
                    "type": "boolean",
                    "description": "Include visual memories in search",
                    "default": True
                },
                "include_text": {
                    "type": "boolean",
                    "description": "Include text memories in search",
                    "default": True
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_visual",
        "description": "Get a specific visual memory by its document ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "Document ID of the visual memory"
                }
            },
            "required": ["doc_id"]
        }
    },
    {
        "name": "delete_visual",
        "description": "Delete a visual memory by its document ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "Document ID of the visual memory to delete"
                }
            },
            "required": ["doc_id"]
        }
    },
    {
        "name": "visual_stats",
        "description": "Get statistics about visual memory (count, types, embedder info)",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def get_visual_tools() -> List[Dict[str, Any]]:
    """Return list of visual memory MCP tool definitions."""
    return VISUAL_MEMORY_TOOLS


def get_tool_names() -> List[str]:
    """Return list of visual memory tool names."""
    return [tool["name"] for tool in VISUAL_MEMORY_TOOLS]
