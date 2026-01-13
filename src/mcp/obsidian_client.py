"""
Obsidian MCP Client - Refactored Facade (Week 7 - Phase 3)

REST API client for Obsidian vault synchronization.
Implements portable vault integration with bidirectional sync.

REFACTORED: Extracted into focused components for high cohesion:
- VaultFileManager: File discovery and metadata
- VaultSyncService: Sync operations

This class now acts as a facade coordinating the components.

NASA Rule 10 Compliant: All functions <=60 LOC
Cohesion: HIGH (facade pattern - coordinates focused components)
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from loguru import logger

from .vault_file_manager import VaultFileManager
from .vault_sync_service import VaultSyncService, VaultSyncConfig


class ObsidianMCPClient:
    """
    Facade for Obsidian vault operations.

    Coordinates focused components:
    - VaultFileManager: File operations
    - VaultSyncService: Sync operations

    Usage:
        client = ObsidianMCPClient(vault_path="/path/to/vault")
        result = client.sync_vault()
        print(f"Synced {result['files_synced']} files")
    """

    def __init__(
        self,
        vault_path: str,
        chunker: Any = None,
        embedder: Any = None,
        indexer: Any = None
    ):
        """
        Initialize Obsidian MCP client.

        Args:
            vault_path: Path to Obsidian vault directory
            chunker: SemanticChunker instance (optional, lazy loaded)
            embedder: EmbeddingPipeline instance (optional, lazy loaded)
            indexer: VectorIndexer instance (optional, lazy loaded)
        """
        self.vault_path = Path(vault_path)
        self._file_manager = VaultFileManager(vault_path)

        # Store or lazy load dependencies
        self._chunker = chunker
        self._embedder = embedder
        self._indexer = indexer
        self._sync_service: Optional[VaultSyncService] = None

        logger.info(f"ObsidianMCPClient initialized: {vault_path}")

    @property
    def chunker(self):
        """Lazy load SemanticChunker."""
        if self._chunker is None:
            from ..chunking.semantic_chunker import SemanticChunker
            self._chunker = SemanticChunker()
        return self._chunker

    @property
    def embedder(self):
        """Lazy load EmbeddingPipeline."""
        if self._embedder is None:
            from ..indexing.embedding_pipeline import EmbeddingPipeline
            self._embedder = EmbeddingPipeline()
        return self._embedder

    @property
    def indexer(self):
        """Lazy load VectorIndexer."""
        if self._indexer is None:
            from ..indexing.vector_indexer import VectorIndexer
            self._indexer = VectorIndexer.get_instance(persist_directory="./chroma_data")
        return self._indexer

    @property
    def sync_service(self) -> VaultSyncService:
        """Get or create sync service."""
        if self._sync_service is None:
            self._sync_service = VaultSyncService(
                file_manager=self._file_manager,
                chunker=self.chunker,
                embedder=self.embedder,
                indexer=self.indexer
            )
        return self._sync_service

    def sync_vault(
        self,
        file_extensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Sync entire vault to memory system.

        Args:
            file_extensions: File extensions to sync (default: [".md"])

        Returns:
            Sync result with stats
        """
        config = VaultSyncConfig(extensions=file_extensions)
        return self.sync_service.sync_vault(config)

    def watch_changes(
        self,
        callback: Callable[[str, str], None],
        poll_interval: int = 5
    ) -> None:
        """
        Watch for file changes and sync incrementally.

        Args:
            callback: Function called on file change (path, event_type)
            poll_interval: Polling interval in seconds
        """
        config = VaultSyncConfig(poll_interval=poll_interval)
        self.sync_service.watch_changes(callback, config)

    def export_to_vault(
        self,
        chunks: List[Dict[str, Any]],
        output_file: str = "exported_memories.md"
    ) -> Dict[str, Any]:
        """
        Export memory chunks to Obsidian vault.

        Args:
            chunks: List of chunk dicts with "text" and "metadata"
            output_file: Output filename in vault

        Returns:
            Export result
        """
        return self.sync_service.export_to_vault(chunks, output_file)

    def get_vault_stats(self) -> Dict[str, Any]:
        """
        Get vault statistics.

        Returns:
            Stats dict with file counts, sizes, types
        """
        return self._file_manager.get_vault_stats()
