"""
MCP Server Module
Provides MCP-compliant stdio server with 6 tools.

Note: The production entrypoint is `python -m src.mcp.http_server`.
Imports here are lazy to avoid crashing when optional dependencies
(pgmpy, reranker_service, etc.) are missing on Railway.
"""

# Lazy exports — only import when explicitly accessed
# Prevents module-level crash from missing optional deps at Railway startup
__all__ = [
    'NexusSearchTool',
    'run_server',
    'ObsidianMCPClient',
    'VaultFileManager',
    'VaultSyncService',
    'VaultSyncConfig',
]


def __getattr__(name):
    if name in ('NexusSearchTool', 'run_server'):
        from .stdio_server import NexusSearchTool, main as run_server  # noqa: F401
        globals()['NexusSearchTool'] = NexusSearchTool
        globals()['run_server'] = run_server
        return globals()[name]
    if name == 'ObsidianMCPClient':
        from .obsidian_client import ObsidianMCPClient
        globals()['ObsidianMCPClient'] = ObsidianMCPClient
        return ObsidianMCPClient
    if name == 'VaultFileManager':
        from .vault_file_manager import VaultFileManager
        globals()['VaultFileManager'] = VaultFileManager
        return VaultFileManager
    if name in ('VaultSyncService', 'VaultSyncConfig'):
        from .vault_sync_service import VaultSyncService, VaultSyncConfig
        globals()['VaultSyncService'] = VaultSyncService
        globals()['VaultSyncConfig'] = VaultSyncConfig
        return globals()[name]
    raise AttributeError(f"module 'src.mcp' has no attribute {name!r}")
