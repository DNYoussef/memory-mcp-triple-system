"""
Nexus Processor module for unified multi-tier RAG retrieval.

Lazy imports to avoid cascade crashes from optional Railway dependencies.
Production entrypoint: python -m src.mcp.http_server
"""

__all__ = ["NexusProcessor", "MemoryMCPQueryService"]


def __getattr__(name):
    if name == 'NexusProcessor':
        from .processor import NexusProcessor
        globals()['NexusProcessor'] = NexusProcessor
        return NexusProcessor
    if name == 'MemoryMCPQueryService':
        from .public_api import MemoryMCPQueryService
        globals()['MemoryMCPQueryService'] = MemoryMCPQueryService
        return MemoryMCPQueryService
    raise AttributeError(f"module 'src.nexus' has no attribute {name!r}")
