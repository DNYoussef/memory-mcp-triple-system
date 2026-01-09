"""
MCP Server Module
Provides MCP-compliant stdio server with 6 tools.

NASA Rule 10 Compliant: All functions <=60 LOC

Note: HTTP server (server.py) has been deprecated and archived.
Use stdio_server.py as the canonical MCP server.

Obsidian Integration (2026-01-08):
- ObsidianMCPClient: Facade for vault operations
- VaultFileManager: File discovery and metadata
- VaultSyncService: Sync operations
"""

from .stdio_server import NexusSearchTool, main as run_server
from .obsidian_client import ObsidianMCPClient
from .vault_file_manager import VaultFileManager
from .vault_sync_service import VaultSyncService, VaultSyncConfig

__all__ = [
    'NexusSearchTool',
    'run_server',
    'ObsidianMCPClient',
    'VaultFileManager',
    'VaultSyncService',
    'VaultSyncConfig'
]
