"""
Vault Sync Service - Focused component for vault synchronization.

Extracted from ObsidianMCPClient to improve cohesion.
Handles: file sync, incremental updates, export.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Protocol
from datetime import datetime
import time
from loguru import logger

from .vault_file_manager import VaultFileManager


class ChunkerProtocol(Protocol):
    """Protocol for chunking service."""
    def chunk_text(self, text: str, source: str) -> List[Dict[str, Any]]: ...


class EmbedderProtocol(Protocol):
    """Protocol for embedding service."""
    def encode(self, texts: List[str]) -> Any: ...


class IndexerProtocol(Protocol):
    """Protocol for indexing service."""
    def index_chunks(self, chunks: List[Dict], embeddings: List) -> bool: ...


class VaultSyncConfig:
    """Configuration for vault sync operations."""

    def __init__(
        self,
        extensions: Optional[List[str]] = None,
        poll_interval: int = 5
    ):
        self.extensions = extensions or [".md"]
        self.poll_interval = poll_interval


class VaultSyncService:
    """
    Handles vault synchronization operations.

    Single Responsibility: Sync vault content to memory system.
    Cohesion: High - all methods relate to sync operations.
    """

    def __init__(
        self,
        file_manager: VaultFileManager,
        chunker: ChunkerProtocol,
        embedder: EmbedderProtocol,
        indexer: IndexerProtocol
    ):
        """
        Initialize vault sync service.

        Args:
            file_manager: VaultFileManager instance
            chunker: Chunking service
            embedder: Embedding service
            indexer: Indexing service
        """
        self.file_manager = file_manager
        self.chunker = chunker
        self.embedder = embedder
        self.indexer = indexer

    def sync_vault(
        self,
        config: Optional[VaultSyncConfig] = None
    ) -> Dict[str, Any]:
        """
        Sync entire vault to memory system.

        Args:
            config: Sync configuration

        Returns:
            Sync result with stats
        """
        if config is None:
            config = VaultSyncConfig()

        start_time = time.time()
        files_synced = 0
        total_chunks = 0
        errors = []

        try:
            files = self.file_manager.discover_files(config.extensions)
            logger.info(f"Found {len(files)} files to sync")

            for file_path in files:
                result = self._sync_single_file(file_path)
                if result["success"]:
                    files_synced += 1
                    total_chunks += result["chunks"]
                else:
                    errors.append(f"{file_path.name}: {result['error']}")

            return {
                "success": len(errors) == 0,
                "files_synced": files_synced,
                "total_chunks": total_chunks,
                "duration_ms": int((time.time() - start_time) * 1000),
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Vault sync failed: {e}")
            return {
                "success": False,
                "files_synced": 0,
                "total_chunks": 0,
                "duration_ms": 0,
                "errors": [str(e)]
            }

    def _sync_single_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Sync single file to memory system.

        Args:
            file_path: Path to file

        Returns:
            Result with success, chunks, error
        """
        try:
            content = self.file_manager.read_file(file_path)
            if not content or not content.strip():
                return {"success": True, "chunks": 0, "error": None}

            metadata = self.file_manager.get_file_metadata(file_path)
            relative_path = metadata.get("file_path", str(file_path))

            # Chunk content
            chunks = self.chunker.chunk_text(content, relative_path)
            if not chunks:
                return {"success": True, "chunks": 0, "error": None}

            # Enrich with metadata
            for chunk in chunks:
                chunk['metadata'] = {**metadata, **chunk.get('metadata', {})}

            # Generate embeddings and index
            texts = [c['text'] for c in chunks]
            embeddings = self.embedder.encode(texts)
            self.indexer.index_chunks(chunks, embeddings.tolist())

            logger.info(f"Synced {file_path.name}: {len(chunks)} chunks")
            return {"success": True, "chunks": len(chunks), "error": None}

        except Exception as e:
            logger.error(f"Failed to sync {file_path}: {e}")
            return {"success": False, "chunks": 0, "error": str(e)}

    def watch_changes(
        self,
        callback: Callable[[str, str], None],
        config: Optional[VaultSyncConfig] = None
    ) -> None:
        """
        Watch for file changes and trigger callback.

        Args:
            callback: Function(file_path, event_type)
            config: Watch configuration
        """
        if config is None:
            config = VaultSyncConfig()

        logger.info(f"Starting watcher (interval: {config.poll_interval}s)")
        file_mtimes: Dict[str, float] = {}

        try:
            while True:
                for file_path in self.file_manager.discover_files(config.extensions):
                    try:
                        mtime = file_path.stat().st_mtime
                        file_key = str(file_path.relative_to(
                            self.file_manager.vault_path
                        ))

                        if file_key not in file_mtimes:
                            callback(file_key, "created")
                            file_mtimes[file_key] = mtime
                        elif mtime > file_mtimes[file_key]:
                            callback(file_key, "modified")
                            file_mtimes[file_key] = mtime

                    except Exception as e:
                        logger.error(f"Watch error for {file_path}: {e}")

                time.sleep(config.poll_interval)

        except KeyboardInterrupt:
            logger.info("Watcher stopped")

    def export_to_vault(
        self,
        chunks: List[Dict[str, Any]],
        output_file: str = "exported_memories.md"
    ) -> Dict[str, Any]:
        """
        Export memory chunks to vault.

        Args:
            chunks: Chunks to export
            output_file: Output filename

        Returns:
            Export result
        """
        try:
            output_path = self.file_manager.vault_path / output_file

            lines = [
                "# Exported Memories",
                f"Exported: {datetime.now().isoformat()}",
                f"Total chunks: {len(chunks)}",
                "", "---", ""
            ]

            for i, chunk in enumerate(chunks, 1):
                text = chunk.get("text", "")
                meta = chunk.get("metadata", {})
                lines.extend([
                    f"## Memory {i}",
                    f"**Source**: {meta.get('source', 'unknown')}",
                    f"**Created**: {meta.get('created_at', 'unknown')}",
                    "", text, "", "---", ""
                ])

            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            return {
                "success": True,
                "file_path": str(output_path),
                "chunks_exported": len(chunks)
            }

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return {
                "success": False,
                "file_path": "",
                "chunks_exported": 0,
                "error": str(e)
            }
