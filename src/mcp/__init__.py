"""
MCP Server Module
Provides MCP-compliant stdio server with 6 tools.

NASA Rule 10 Compliant: All functions ≤60 LOC

Note: HTTP server (server.py) has been deprecated and archived.
Use stdio_server.py as the canonical MCP server.
"""

from .stdio_server import NexusSearchTool, main as run_server

__all__ = ['NexusSearchTool', 'run_server']
