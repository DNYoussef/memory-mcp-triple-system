"""
Obsidian MCP Client (Week 7 - Phase 3 Real Implementation)

REST API client for Obsidian vault synchronization.
Implements portable vault integration with bidirectional sync.

Part of Memory-as-Code philosophy: Obsidian vault is canonical source.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import time
from loguru import logger

# ISS-007 FIX: Removed global state. Now using instance-level lazy loading.


class ObsidianMCPClient:
    """
    REST API client for Obsidian vault synchronization.

    Implements portable vault integration:
    - Sync entire vault to memory system
    - Watch for file changes (incremental sync)
    - Export memory chunks to vault
    - Bidirectional conflict resolution (vault wins)

    Usage:
        client = ObsidianMCPClient(
            vault_path="/path/to/vault",
            api_url="http://localhost:27123"
        )

        # Sync vault to memory
        result = client.sync_vault()
        print(f"Synced {result['files_synced']} files")

        # Watch for changes
        client.watch_changes(callback=on_file_changed)
    """

    def __init__(
        self,
        vault_path: str,
        api_url: str = "http://localhost:27123",
        timeout: int = 30
    ):
        """
        Initialize Obsidian MCP client.

        Args:
            vault_path: Path to Obsidian vault directory
            api_url: Obsidian REST API endpoint
            timeout: Request timeout in seconds

        NASA Rule 10: 18 LOC (≤60) ✅
        """
        self.vault_path = Path(vault_path)
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

        # ISS-007 FIX: Instance-level lazy loading instead of globals
        self._chunker = None
        self._embedder = None
        self._indexer = None

        if not self.vault_path.exists():
            logger.warning(f"Vault path does not exist: {vault_path}")

    @property
    def chunker(self):
        """ISS-007 FIX: Lazy load SemanticChunker (instance-level)."""
        if self._chunker is None:
            from ..chunking.semantic_chunker import SemanticChunker
            self._chunker = SemanticChunker()
        return self._chunker

    @property
    def embedder(self):
        """ISS-007 FIX: Lazy load EmbeddingPipeline (instance-level)."""
        if self._embedder is None:
            from ..indexing.embedding_pipeline import EmbeddingPipeline
            self._embedder = EmbeddingPipeline()
        return self._embedder

    @property
    def indexer(self):
        """ISS-007 FIX: Lazy load VectorIndexer (instance-level)."""
        if self._indexer is None:
            from ..indexing.vector_indexer import VectorIndexer
            self._indexer = VectorIndexer(persist_directory="./chroma_data")
        return self._indexer

    def sync_vault(self, file_extensions: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Sync entire vault to memory system.

        Args:
            file_extensions: File extensions to sync (default: [".md"])

        Returns:
            {
                "success": bool,
                "files_synced": int,
                "total_chunks": int,
                "duration_ms": int,
                "errors": List[str]
            }

        NASA Rule 10: 52 LOC (≤60) ✅
        """
        if file_extensions is None:
            file_extensions = [".md"]

        start_time = time.time()
        files_synced = 0
        total_chunks = 0
        errors = []

        try:
            # Find all matching files
            files = []
            for ext in file_extensions:
                files.extend(self.vault_path.glob(f"**/*{ext}"))

            logger.info(f"Found {len(files)} files to sync in vault")

            # Sync each file
            for file_path in files:
                try:
                    result = self._sync_file(file_path)
                    if result["success"]:
                        files_synced += 1
                        total_chunks += result["chunks"]
                    else:
                        errors.append(f"{file_path.name}: {result['error']}")

                except Exception as e:
                    logger.error(f"Failed to sync {file_path}: {e}")
                    errors.append(f"{file_path.name}: {str(e)}")

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": len(errors) == 0,
                "files_synced": files_synced,
                "total_chunks": total_chunks,
                "duration_ms": duration_ms,
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

    def _sync_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Sync single file to memory system using real chunking and indexing.

        Args:
            file_path: Path to file to sync

        Returns:
            {"success": bool, "chunks": int, "error": str}

        NASA Rule 10: 55 LOC (<=60)
        """
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if len(content.strip()) == 0:
                return {"success": True, "chunks": 0, "error": None}

            # Get file metadata
            stat = file_path.stat()
            relative_path = str(file_path.relative_to(self.vault_path))
            base_metadata = {
                "file_path": relative_path,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_bytes": stat.st_size,
                "source": "obsidian_vault",
                "vault_path": str(self.vault_path)
            }

            # ISS-007 FIX: Use instance properties instead of global functions
            # Chunk the file content
            chunks = self.chunker.chunk_text(content, relative_path)

            if not chunks:
                return {"success": True, "chunks": 0, "error": None}

            # Enrich chunks with metadata
            for chunk in chunks:
                chunk['metadata'] = {**base_metadata, **chunk.get('metadata', {})}

            # Generate embeddings
            texts = [c['text'] for c in chunks]
            embeddings = self.embedder.encode(texts)

            # Index chunks
            self.indexer.index_chunks(chunks, embeddings.tolist())

            logger.info(f"Synced {file_path.name}: {len(chunks)} chunks indexed")

            return {
                "success": True,
                "chunks": len(chunks),
                "error": None
            }

        except Exception as e:
            logger.error(f"Failed to sync {file_path}: {e}")
            return {
                "success": False,
                "chunks": 0,
                "error": str(e)
            }

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

        Note: This is a simplified polling implementation.
        Production would use file system events (watchdog library).

        NASA Rule 10: 35 LOC (≤60) ✅
        """
        logger.info(f"Starting file watcher (poll interval: {poll_interval}s)")

        # Store file modification times
        file_mtimes: Dict[str, float] = {}

        try:
            while True:
                # Scan vault for changes
                for file_path in self.vault_path.glob("**/*.md"):
                    try:
                        mtime = file_path.stat().st_mtime
                        file_key = str(file_path.relative_to(self.vault_path))

                        if file_key not in file_mtimes:
                            # New file
                            callback(file_key, "created")
                            file_mtimes[file_key] = mtime
                        elif mtime > file_mtimes[file_key]:
                            # Modified file
                            callback(file_key, "modified")
                            file_mtimes[file_key] = mtime

                    except Exception as e:
                        logger.error(f"Error watching {file_path}: {e}")

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("File watcher stopped")

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
            {"success": bool, "file_path": str, "chunks_exported": int}

        NASA Rule 10: 40 LOC (≤60) ✅
        """
        try:
            output_path = self.vault_path / output_file

            # Build markdown content
            lines = [
                "# Exported Memories",
                f"Exported: {datetime.now().isoformat()}",
                f"Total chunks: {len(chunks)}",
                "",
                "---",
                ""
            ]

            for i, chunk in enumerate(chunks, 1):
                text = chunk.get("text", "")
                metadata = chunk.get("metadata", {})

                lines.append(f"## Memory {i}")
                lines.append(f"**Source**: {metadata.get('source', 'unknown')}")
                lines.append(f"**Created**: {metadata.get('created_at', 'unknown')}")
                lines.append("")
                lines.append(text)
                lines.append("")
                lines.append("---")
                lines.append("")

            # Write to vault
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            return {
                "success": True,
                "file_path": str(output_path),
                "chunks_exported": len(chunks)
            }

        except Exception as e:
            logger.error(f"Failed to export to vault: {e}")
            return {
                "success": False,
                "file_path": "",
                "chunks_exported": 0,
                "error": str(e)
            }

    def get_vault_stats(self) -> Dict[str, Any]:
        """
        Get vault statistics.

        Returns:
            {
                "total_files": int,
                "total_size_bytes": int,
                "file_types": Dict[str, int],
                "last_modified": str
            }

        NASA Rule 10: 35 LOC (≤60) ✅
        """
        try:
            files = list(self.vault_path.glob("**/*"))
            files = [f for f in files if f.is_file()]

            total_size = sum(f.stat().st_size for f in files)

            # Count file types
            file_types: Dict[str, int] = {}
            for f in files:
                ext = f.suffix or "no_extension"
                file_types[ext] = file_types.get(ext, 0) + 1

            # Find last modified
            if files:
                last_modified_file = max(files, key=lambda f: f.stat().st_mtime)
                last_modified = datetime.fromtimestamp(
                    last_modified_file.stat().st_mtime
                ).isoformat()
            else:
                last_modified = None

            return {
                "total_files": len(files),
                "total_size_bytes": total_size,
                "file_types": file_types,
                "last_modified": last_modified
            }

        except Exception as e:
            logger.error(f"Failed to get vault stats: {e}")
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "file_types": {},
                "last_modified": None,
                "error": str(e)
            }
