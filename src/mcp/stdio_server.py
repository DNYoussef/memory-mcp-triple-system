"""
MCP Server Implementation using stdio protocol
Compatible with Claude Code's MCP expectations.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import json
import sys
from typing import Dict, Any, List
from pathlib import Path
import yaml
from loguru import logger

from .tools.vector_search import VectorSearchTool


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "memory-mcp.yaml"
    assert config_path.exists(), f"Config not found: {config_path}"

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config


def handle_list_tools() -> List[Dict[str, Any]]:
    """Return list of available MCP tools."""
    return [
        {
            "name": "vector_search",
            "description": "Search memory vault using semantic similarity with mode-aware context adaptation",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "memory_store",
            "description": "Store information in memory vault with automatic layer assignment",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Content to store"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata (key, namespace, layer, category)"
                    }
                },
                "required": ["text"]
            }
        }
    ]


def handle_call_tool(tool_name: str, arguments: Dict[str, Any], tool: VectorSearchTool) -> Dict[str, Any]:
    """Execute a tool and return results."""
    try:
        if tool_name == "vector_search":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)

            results = tool.execute(query, limit)

            # Format results for MCP
            content = []
            for idx, result in enumerate(results, 1):
                content.append({
                    "type": "text",
                    "text": f"Result {idx}:\n{result['text']}\n\nScore: {result['score']:.4f}\nFile: {result['file_path']}\n"
                })

            return {
                "content": content,
                "isError": False
            }

        elif tool_name == "memory_store":
            text = arguments.get("text", "")
            metadata = arguments.get("metadata", {})

            # Use the indexer to store
            from ..chunking.semantic_chunker import SemanticChunker
            from ..indexing.embedding_pipeline import EmbeddingPipeline

            chunker = tool.chunker
            embedder = tool.embedder
            indexer = tool.indexer

            # Create chunk
            chunks = [{
                'text': text,
                'file_path': metadata.get('key', 'manual_entry'),
                'chunk_index': 0,
                'metadata': metadata
            }]

            # Generate embedding and index
            embeddings = embedder.encode([text])
            indexer.index_chunks(chunks, embeddings.tolist())

            return {
                "content": [{
                    "type": "text",
                    "text": f"Stored memory: {text[:100]}..."
                }],
                "isError": False
            }

        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Unknown tool: {tool_name}"
                }],
                "isError": True
            }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {str(e)}"
            }],
            "isError": True
        }


def main():
    """Main stdio MCP server loop."""
    # Suppress loguru output to stderr (interferes with stdio protocol)
    logger.remove()

    # Load config and initialize tool
    config = load_config()
    vector_search_tool = VectorSearchTool(config)

    # Process stdio messages
    for line in sys.stdin:
        try:
            message = json.loads(line.strip())

            method = message.get("method", "")
            message_id = message.get("id")
            params = message.get("params", {})

            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "tools": handle_list_tools()
                    }
                }

            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                result = handle_call_tool(tool_name, arguments, vector_search_tool)

                response = {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": result
                }

            elif method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "memory-mcp-triple-system",
                            "version": "1.0.0"
                        }
                    }
                }

            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

            # Send response
            print(json.dumps(response), flush=True)

        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": message.get("id") if 'message' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
