"""
File Watcher for Obsidian Vault
Monitors markdown files and triggers reindexing on changes.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import time
from pathlib import Path
from typing import Callable, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from loguru import logger


class MarkdownFileHandler(FileSystemEventHandler):
    """Handles markdown file system events."""

    def __init__(
        self,
        on_change: Callable[[Path], None],
        debounce_seconds: float = 2.0
    ):
        """
        Initialize handler.

        Args:
            on_change: Callback function when file changes
            debounce_seconds: Wait time before triggering callback
        """
        super().__init__()
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds
        self._pending_files: Set[Path] = set()
        self._last_event_time = 0.0

    def _is_markdown(self, path: str) -> bool:
        """Check if file is markdown."""
        return path.endswith('.md')

    def _should_ignore(self, path: str) -> bool:
        """Check if file should be ignored."""
        ignore_patterns = ['.trash', '.obsidian', '.git']
        return any(pattern in path for pattern in ignore_patterns)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if not event.is_directory and self._is_markdown(event.src_path):
            if not self._should_ignore(event.src_path):
                self._queue_file(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if not event.is_directory and self._is_markdown(event.src_path):
            if not self._should_ignore(event.src_path):
                self._queue_file(Path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if not event.is_directory and self._is_markdown(event.src_path):
            if not self._should_ignore(event.src_path):
                logger.info(f"File deleted: {event.src_path}")
                # TODO: Implement deletion from vector DB

    def _queue_file(self, file_path: Path) -> None:
        """Queue file for processing with debouncing."""
        self._pending_files.add(file_path)
        self._last_event_time = time.time()
        logger.debug(f"Queued: {file_path}")


class ObsidianVaultWatcher:
    """Watches Obsidian vault for changes."""

    def __init__(
        self,
        vault_path: Path,
        on_change: Callable[[Path], None],
        debounce_seconds: float = 2.0
    ):
        """
        Initialize vault watcher.

        Args:
            vault_path: Path to Obsidian vault
            on_change: Callback for file changes
            debounce_seconds: Debounce time
        """
        assert vault_path.exists(), f"Vault not found: {vault_path}"

        self.vault_path = vault_path
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds

        self.handler = MarkdownFileHandler(on_change, debounce_seconds)
        self.observer = Observer()

        logger.info(f"Initialized watcher for: {vault_path}")

    def start(self) -> None:
        """Start watching vault."""
        self.observer.schedule(
            self.handler,
            str(self.vault_path),
            recursive=True
        )
        self.observer.start()
        logger.info("Watcher started")

    def stop(self) -> None:
        """Stop watching vault."""
        self.observer.stop()
        self.observer.join()
        logger.info("Watcher stopped")

    def process_pending(self) -> None:
        """Process pending files (call periodically)."""
        if not self.handler._pending_files:
            return

        # Check if debounce period has elapsed
        elapsed = time.time() - self.handler._last_event_time
        if elapsed < self.debounce_seconds:
            return

        # Process all pending files
        files_to_process = list(self.handler._pending_files)
        self.handler._pending_files.clear()

        for file_path in files_to_process:
            try:
                self.on_change(file_path)
                logger.info(f"Processed: {file_path}")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
