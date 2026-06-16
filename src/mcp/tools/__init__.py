"""
MCP Tools Module
Implements tools exposed via MCP server.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from .vector_search import VectorSearchTool

__all__ = ["VectorSearchTool"]
