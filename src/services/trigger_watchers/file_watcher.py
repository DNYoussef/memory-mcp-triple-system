"""File Watcher for Proactive Context Injection.

Monitors file system events and triggers context injection on file opens.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from loguru import logger

try:
    from watchdog.observers import Observer
    from watchdog.events import (
        FileSystemEventHandler,
        FileOpenedEvent,
        FileModifiedEvent,
        FileCreatedEvent,
        DirModifiedEvent,
    )

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog not installed. File watching will use polling fallback.")

from ..proactive_context_injector import ProactiveContextInjector
from ...integrations.proactive_schema import TriggerEvent


@dataclass
class WatchConfig:
    """Configuration for file watching."""

    paths: List[str] = field(default_factory=list)
    extensions: Set[str] = field(
        default_factory=lambda: {
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".md",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".sql",
            ".sh",
            ".ps1",
            ".bat",
            ".go",
            ".rs",
            ".java",
            ".kt",
            ".swift",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
        }
    )
    ignore_patterns: List[str] = field(
        default_factory=lambda: [
            r"__pycache__",
            r"\.git",
            r"node_modules",
            r"\.venv",
            r"venv",
            r"\.pytest_cache",
            r"\.mypy_cache",
            r"dist",
            r"build",
            r"\.egg-info",
            r"\.tox",
            r"\.coverage",
        ]
    )
    debounce_seconds: float = 2.0
    project_name: Optional[str] = None


class FileEventHandler(FileSystemEventHandler):
    """Handle file system events for proactive context injection."""

    def __init__(
        self,
        callback: Callable[[str, str], None],
        config: WatchConfig,
    ):
        """Initialize file event handler.

        Args:
            callback: Function to call on file access (file_path, event_type)
            config: Watch configuration
        """
        super().__init__()
        self.callback = callback
        self.config = config
        self._ignore_patterns = [re.compile(p) for p in config.ignore_patterns]
        self._last_events: Dict[str, datetime] = {}

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        for pattern in self._ignore_patterns:
            if pattern.search(path):
                return True
        return False

    def _should_process_extension(self, path: str) -> bool:
        """Check if file extension should be processed."""
        ext = Path(path).suffix.lower()
        return ext in self.config.extensions

    def _is_debounced(self, path: str) -> bool:
        """Check if event is within debounce window."""
        now = datetime.utcnow()
        last = self._last_events.get(path)

        if last and (now - last).total_seconds() < self.config.debounce_seconds:
            return True

        self._last_events[path] = now
        return False

    def on_modified(self, event):
        """Handle file modification (often indicates file open in editors)."""
        if event.is_directory:
            return

        path = event.src_path

        if self._should_ignore(path):
            return

        if not self._should_process_extension(path):
            return

        if self._is_debounced(path):
            return

        logger.debug(f"File modified: {path}")
        self.callback(path, "modified")

    def on_created(self, event):
        """Handle file creation."""
        if event.is_directory:
            return

        path = event.src_path

        if self._should_ignore(path):
            return

        if not self._should_process_extension(path):
            return

        if self._is_debounced(path):
            return

        logger.debug(f"File created: {path}")
        self.callback(path, "created")


class PollingFileWatcher:
    """Fallback polling-based file watcher when watchdog is unavailable."""

    def __init__(
        self,
        callback: Callable[[str, str], None],
        config: WatchConfig,
        poll_interval: float = 5.0,
    ):
        """Initialize polling watcher.

        Args:
            callback: Function to call on file changes
            config: Watch configuration
            poll_interval: Seconds between polls
        """
        self.callback = callback
        self.config = config
        self.poll_interval = poll_interval
        self._running = False
        self._file_mtimes: Dict[str, float] = {}
        self._ignore_patterns = [re.compile(p) for p in config.ignore_patterns]

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        for pattern in self._ignore_patterns:
            if pattern.search(path):
                return True
        return False

    def _scan_directory(self, directory: str) -> Dict[str, float]:
        """Scan directory for file modification times."""
        mtimes = {}

        for root, dirs, files in os.walk(directory):
            # Filter out ignored directories
            dirs[:] = [
                d for d in dirs if not self._should_ignore(os.path.join(root, d))
            ]

            for file in files:
                file_path = os.path.join(root, file)

                if self._should_ignore(file_path):
                    continue

                ext = Path(file_path).suffix.lower()
                if ext not in self.config.extensions:
                    continue

                try:
                    mtimes[file_path] = os.path.getmtime(file_path)
                except OSError:
                    pass

        return mtimes

    async def start(self):
        """Start polling."""
        self._running = True

        # Initial scan
        for path in self.config.paths:
            if os.path.isdir(path):
                self._file_mtimes.update(self._scan_directory(path))

        logger.info(
            f"Polling watcher started, monitoring {len(self._file_mtimes)} files"
        )

        while self._running:
            await asyncio.sleep(self.poll_interval)

            for path in self.config.paths:
                if not os.path.isdir(path):
                    continue

                current_mtimes = self._scan_directory(path)

                # Check for new or modified files
                for file_path, mtime in current_mtimes.items():
                    old_mtime = self._file_mtimes.get(file_path)

                    if old_mtime is None:
                        # New file
                        self.callback(file_path, "created")
                    elif mtime > old_mtime:
                        # Modified file
                        self.callback(file_path, "modified")

                self._file_mtimes.update(current_mtimes)

    def stop(self):
        """Stop polling."""
        self._running = False


class FileWatcher:
    """File watcher for proactive context injection.

    Monitors file system events and triggers context injection
    when files are opened/modified.

    Usage:
        watcher = FileWatcher(injector, config)
        await watcher.start()
        # ... later
        await watcher.stop()
    """

    def __init__(
        self,
        injector: ProactiveContextInjector,
        config: Optional[WatchConfig] = None,
    ):
        """Initialize file watcher.

        Args:
            injector: ProactiveContextInjector for triggering context injection
            config: Watch configuration (optional)
        """
        self.injector = injector
        self.config = config or WatchConfig()
        self._observer: Optional[Observer] = None
        self._polling_watcher: Optional[PollingFileWatcher] = None
        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task] = None
        # Captured at start() in the event-loop thread so watchdog-thread events
        # can be dispatched without asyncio.get_event_loop() (G4). One shared
        # handler so add_watch_path() never registers a duplicate (G5).
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._handler: Optional["FileEventHandler"] = None

        logger.info(
            f"FileWatcher initialized for {len(self.config.paths)} paths, "
            f"{len(self.config.extensions)} extensions"
        )

    def _on_file_event(self, file_path: str, event_type: str) -> None:
        """Handle file event (called from the watchdog thread).

        Uses the loop captured at start(), not asyncio.get_event_loop() - the
        latter raises in the watchdog thread on Python 3.10+ and the old bare
        except silently dropped every file event (G4).
        """
        loop = self._loop
        if loop is None:
            # Watcher not started inside an event loop; nothing to dispatch to.
            return
        try:
            loop.call_soon_threadsafe(
                self._event_queue.put_nowait,
                (file_path, event_type),
            )
        except RuntimeError:
            # Loop is closed/closing.
            pass

    async def _process_events(self) -> None:
        """Process queued file events."""
        while self._running:
            try:
                file_path, event_type = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0,
                )

                await self._trigger_injection(file_path, event_type)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing file event: {e}")

    async def _trigger_injection(self, file_path: str, event_type: str) -> None:
        """Trigger context injection for file event."""
        try:
            event = TriggerEvent.from_file_open(
                file_path=file_path,
                project=self.config.project_name,
            )

            # Add event type to metadata
            event.metadata["event_type"] = event_type

            context = await self.injector.handle_trigger(event)

            if context:
                logger.info(
                    f"Injected context for {file_path}: "
                    f"{len(context.chunks)} chunks, "
                    f"relevance={context.relevance_score:.2f}"
                )
            else:
                logger.debug(f"No context injected for {file_path}")

        except Exception as e:
            logger.error(f"Failed to trigger injection for {file_path}: {e}")

    async def start(self) -> None:
        """Start file watching."""
        if self._running:
            logger.warning("FileWatcher already running")
            return

        self._running = True

        # Capture the running loop for cross-thread event dispatch (G4).
        self._loop = asyncio.get_running_loop()

        # Start event processor
        self._processor_task = asyncio.create_task(self._process_events())

        if WATCHDOG_AVAILABLE:
            # Use watchdog for efficient file system monitoring
            self._observer = Observer()
            # One shared handler reused by add_watch_path (G5).
            self._handler = FileEventHandler(self._on_file_event, self.config)

            for path in self.config.paths:
                if os.path.exists(path):
                    self._observer.schedule(self._handler, path, recursive=True)
                    logger.info(f"Watching directory: {path}")
                else:
                    logger.warning(f"Watch path does not exist: {path}")

            self._observer.start()
            logger.info("FileWatcher started with watchdog")
        else:
            # Fallback to polling
            self._polling_watcher = PollingFileWatcher(
                self._on_file_event,
                self.config,
            )
            asyncio.create_task(self._polling_watcher.start())
            logger.info("FileWatcher started with polling fallback")

    async def stop(self) -> None:
        """Stop file watching."""
        self._running = False

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        if self._polling_watcher:
            self._polling_watcher.stop()
            self._polling_watcher = None

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None

        logger.info("FileWatcher stopped")

    def add_watch_path(self, path: str) -> bool:
        """Add a path to watch.

        Args:
            path: Directory path to watch

        Returns:
            True if successfully added
        """
        if not os.path.exists(path):
            logger.warning(f"Cannot add non-existent path: {path}")
            return False

        if path in self.config.paths:
            return True

        self.config.paths.append(path)

        if self._running and self._observer and WATCHDOG_AVAILABLE:
            # Reuse the single shared handler - creating a new one per path
            # registered a duplicate handler and double-fired events (G5).
            if self._handler is None:
                self._handler = FileEventHandler(self._on_file_event, self.config)
            self._observer.schedule(self._handler, path, recursive=True)
            logger.info(f"Added watch path: {path}")

        return True

    def remove_watch_path(self, path: str) -> bool:
        """Remove a path from watching.

        Args:
            path: Directory path to stop watching

        Returns:
            True if successfully removed
        """
        if path not in self.config.paths:
            return False

        self.config.paths.remove(path)
        logger.info(f"Removed watch path: {path}")

        # Note: watchdog doesn't support unscheduling individual paths
        # A full restart would be needed for complete removal

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get watcher statistics.

        Returns:
            Dict with watcher stats
        """
        return {
            "running": self._running,
            "watch_paths": self.config.paths,
            "extensions": list(self.config.extensions),
            "using_watchdog": WATCHDOG_AVAILABLE and self._observer is not None,
            "queue_size": self._event_queue.qsize(),
        }
