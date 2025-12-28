"""
Vault File Manager - Focused component for Obsidian vault file operations.

Extracted from ObsidianMCPClient to improve cohesion.
Handles: file discovery, stats collection, file reading.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger


class VaultFileManager:
    """
    Manages file operations for Obsidian vault.

    Single Responsibility: File discovery and metadata.
    Cohesion: High - all methods work with vault files.
    """

    def __init__(self, vault_path: str):
        """
        Initialize vault file manager.

        Args:
            vault_path: Path to Obsidian vault directory
        """
        self.vault_path = Path(vault_path)
        if not self.vault_path.exists():
            logger.warning(f"Vault path does not exist: {vault_path}")

    def discover_files(
        self,
        extensions: Optional[List[str]] = None
    ) -> List[Path]:
        """
        Discover files in vault matching extensions.

        Args:
            extensions: File extensions to match (default: [".md"])

        Returns:
            List of file paths
        """
        if extensions is None:
            extensions = [".md"]

        files = []
        for ext in extensions:
            files.extend(self.vault_path.glob(f"**/*{ext}"))

        logger.debug(f"Discovered {len(files)} files in vault")
        return files

    def read_file(self, file_path: Path) -> Optional[str]:
        """
        Read file content with error handling.

        Args:
            file_path: Path to file

        Returns:
            File content or None on error
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return None

    def get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Get metadata for a file.

        Args:
            file_path: Path to file

        Returns:
            Metadata dict with path, modified_at, size_bytes
        """
        try:
            stat = file_path.stat()
            relative_path = str(file_path.relative_to(self.vault_path))

            return {
                "file_path": relative_path,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_bytes": stat.st_size,
                "source": "obsidian_vault",
                "vault_path": str(self.vault_path)
            }
        except Exception as e:
            logger.error(f"Failed to get metadata for {file_path}: {e}")
            return {}

    def get_vault_stats(self) -> Dict[str, Any]:
        """
        Get vault statistics.

        Returns:
            Stats dict with file counts, sizes, types
        """
        try:
            files = [f for f in self.vault_path.glob("**/*") if f.is_file()]
            total_size = sum(f.stat().st_size for f in files)

            # Count file types
            file_types: Dict[str, int] = {}
            for f in files:
                ext = f.suffix or "no_extension"
                file_types[ext] = file_types.get(ext, 0) + 1

            # Find last modified
            last_modified = None
            if files:
                last_file = max(files, key=lambda f: f.stat().st_mtime)
                last_modified = datetime.fromtimestamp(
                    last_file.stat().st_mtime
                ).isoformat()

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
