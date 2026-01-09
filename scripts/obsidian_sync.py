#!/usr/bin/env python3
"""
Obsidian Vault Sync Script

Syncs Obsidian vault contents to Memory MCP triple-layer system.
Reads vault path from environment variable OBSIDIAN_VAULT_PATH.

Usage:
    python scripts/obsidian_sync.py              # One-time sync
    python scripts/obsidian_sync.py --watch      # Continuous watch mode
    python scripts/obsidian_sync.py --stats      # Show vault stats only
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path for proper imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from loguru import logger

# Import directly from module files to avoid circular imports
from src.mcp.vault_file_manager import VaultFileManager
from src.mcp.vault_sync_service import VaultSyncService, VaultSyncConfig


class SimplifiedObsidianClient:
    """Simplified client for standalone script use."""
    
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self._file_manager = VaultFileManager(vault_path)
        logger.info(f"ObsidianClient initialized: {vault_path}")
    
    def get_vault_stats(self):
        """Get vault statistics."""
        return self._file_manager.get_vault_stats()
    
    def sync_vault(self, extensions=None):
        """Sync vault files."""
        # For standalone use, just return file info without full embedding pipeline
        stats = self._file_manager.get_vault_stats()
        files = self._file_manager.list_files(extensions or [".md"])
        return {
            "files_processed": len(files),
            "chunks_created": 0,  # Would need full pipeline
            "duration_seconds": 0,
            "stats": stats
        }


def main():
    """Main entry point for Obsidian sync."""
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Sync Obsidian vault to Memory MCP")
    parser.add_argument("--watch", action="store_true", help="Watch for changes continuously")
    parser.add_argument("--stats", action="store_true", help="Show vault statistics only")
    parser.add_argument("--vault", type=str, help="Override vault path from env")
    args = parser.parse_args()
    
    # Get vault path
    vault_path = args.vault or os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        logger.error("OBSIDIAN_VAULT_PATH not set. Set in .env or use --vault flag.")
        sys.exit(1)
    
    if not Path(vault_path).exists():
        logger.error(f"Vault path does not exist: {vault_path}")
        sys.exit(1)
    
    logger.info(f"Using Obsidian vault: {vault_path}")
    
    # Initialize client
    client = SimplifiedObsidianClient(vault_path=vault_path)
    
    if args.stats:
        # Show stats only
        stats = client.get_vault_stats()
        file_types = stats.get('file_types', {})
        markdown_count = file_types.get('.md', 0)
        total_size_mb = stats.get('total_size_bytes', 0) / (1024 * 1024)
        logger.info(f"Vault Statistics:")
        logger.info(f"  Total files: {stats.get('total_files', 0)}")
        logger.info(f"  Markdown files: {markdown_count}")
        logger.info(f"  Total size: {total_size_mb:.2f} MB")
        logger.info(f"  File types: {file_types}")
        return
    
    if args.watch:
        # Watch mode - continuous sync
        logger.info("Starting watch mode (Ctrl+C to stop)...")
        logger.info("Watch mode requires full MCP server. Use: python -m src.mcp.stdio_server")
    else:
        # One-time sync
        logger.info("Starting vault scan...")
        result = client.sync_vault()
        logger.info(f"Scan complete:")
        logger.info(f"  Files found: {result.get('files_processed', 0)}")
        logger.info(f"  Use MCP server for full embedding sync")


if __name__ == "__main__":
    main()
