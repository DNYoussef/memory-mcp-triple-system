"""
MCP Server Module
Provides MCP-compliant server exposing vector search tool.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from .server import create_app

__all__ = ['create_app']
