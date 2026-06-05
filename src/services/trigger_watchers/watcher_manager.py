"""Watcher Manager for Proactive Context Injection.

Coordinates all trigger watchers (file, git, time, activity).

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger

from .file_watcher import FileWatcher, WatchConfig
from .git_watcher import GitWatcher, GitWatchConfig
from .time_scheduler import TimeScheduler, ScheduledTrigger, DEFAULT_SCHEDULES
from .activity_detector import ActivityDetector, ActivityType
from ..proactive_context_injector import ProactiveContextInjector


@dataclass
class WatcherManagerConfig:
    """Configuration for WatcherManager."""

    # File watcher config
    file_watch_paths: List[str] = field(default_factory=list)
    file_extensions: Optional[List[str]] = None
    file_ignore_patterns: Optional[List[str]] = None

    # Git watcher config
    git_repo_paths: List[str] = field(default_factory=list)
    git_poll_interval: float = 10.0

    # Time scheduler config
    time_schedules: Optional[List[ScheduledTrigger]] = None
    time_check_interval: float = 30.0

    # Activity detector config
    activity_window_minutes: int = 30
    activity_check_interval: float = 60.0

    # Enable/disable watchers
    enable_file_watcher: bool = True
    enable_git_watcher: bool = True
    enable_time_scheduler: bool = True
    enable_activity_detector: bool = True

    # Project name for context
    project_name: Optional[str] = None


class WatcherManager:
    """Manages all proactive context injection watchers.

    Coordinates file, git, time, and activity watchers to provide
    comprehensive proactive context injection.

    Usage:
        manager = WatcherManager(injector, config)
        await manager.start()
        # ... watchers running
        await manager.stop()
    """

    def __init__(
        self,
        injector: ProactiveContextInjector,
        config: Optional[WatcherManagerConfig] = None,
    ):
        """Initialize watcher manager.

        Args:
            injector: ProactiveContextInjector for all watchers
            config: WatcherManagerConfig (optional)
        """
        self.injector = injector
        self.config = config or WatcherManagerConfig()

        self._file_watcher: Optional[FileWatcher] = None
        self._git_watcher: Optional[GitWatcher] = None
        self._time_scheduler: Optional[TimeScheduler] = None
        self._activity_detector: Optional[ActivityDetector] = None

        self._running = False

        logger.info("WatcherManager initialized")

    def _create_file_watcher(self) -> Optional[FileWatcher]:
        """Create and configure file watcher."""
        if not self.config.enable_file_watcher:
            return None

        if not self.config.file_watch_paths:
            logger.info("No file watch paths configured, skipping FileWatcher")
            return None

        watch_config = WatchConfig(
            paths=self.config.file_watch_paths,
            project_name=self.config.project_name,
        )

        if self.config.file_extensions:
            watch_config.extensions = set(self.config.file_extensions)

        if self.config.file_ignore_patterns:
            watch_config.ignore_patterns = self.config.file_ignore_patterns

        return FileWatcher(self.injector, watch_config)

    def _create_git_watcher(self) -> Optional[GitWatcher]:
        """Create and configure git watcher."""
        if not self.config.enable_git_watcher:
            return None

        if not self.config.git_repo_paths:
            logger.info("No git repo paths configured, skipping GitWatcher")
            return None

        git_config = GitWatchConfig(
            repo_paths=self.config.git_repo_paths,
            poll_interval=self.config.git_poll_interval,
        )

        return GitWatcher(self.injector, git_config)

    def _create_time_scheduler(self) -> Optional[TimeScheduler]:
        """Create and configure time scheduler."""
        if not self.config.enable_time_scheduler:
            return None

        schedules = self.config.time_schedules or DEFAULT_SCHEDULES

        return TimeScheduler(
            self.injector,
            schedules=schedules,
            check_interval=self.config.time_check_interval,
        )

    def _create_activity_detector(self) -> Optional[ActivityDetector]:
        """Create and configure activity detector."""
        if not self.config.enable_activity_detector:
            return None

        return ActivityDetector(
            self.injector,
            window_minutes=self.config.activity_window_minutes,
            check_interval=self.config.activity_check_interval,
        )

    async def start(self) -> None:
        """Start all configured watchers."""
        if self._running:
            logger.warning("WatcherManager already running")
            return

        self._running = True

        # Create watchers
        self._file_watcher = self._create_file_watcher()
        self._git_watcher = self._create_git_watcher()
        self._time_scheduler = self._create_time_scheduler()
        self._activity_detector = self._create_activity_detector()

        # Start watchers concurrently
        start_tasks = []

        if self._file_watcher:
            start_tasks.append(self._file_watcher.start())
            logger.info("FileWatcher enabled")

        if self._git_watcher:
            start_tasks.append(self._git_watcher.start())
            logger.info("GitWatcher enabled")

        if self._time_scheduler:
            start_tasks.append(self._time_scheduler.start())
            logger.info("TimeScheduler enabled")

        if self._activity_detector:
            start_tasks.append(self._activity_detector.start())
            logger.info("ActivityDetector enabled")

        if start_tasks:
            await asyncio.gather(*start_tasks)
            logger.info(f"WatcherManager started with {len(start_tasks)} watchers")
        else:
            logger.warning("WatcherManager started with no watchers enabled")

    async def stop(self) -> None:
        """Stop all watchers."""
        self._running = False

        stop_tasks = []

        if self._file_watcher:
            stop_tasks.append(self._file_watcher.stop())

        if self._git_watcher:
            stop_tasks.append(self._git_watcher.stop())

        if self._time_scheduler:
            stop_tasks.append(self._time_scheduler.stop())

        if self._activity_detector:
            stop_tasks.append(self._activity_detector.stop())

        if stop_tasks:
            await asyncio.gather(*stop_tasks)

        self._file_watcher = None
        self._git_watcher = None
        self._time_scheduler = None
        self._activity_detector = None

        logger.info("WatcherManager stopped")

    def record_activity(
        self,
        activity_type: ActivityType,
        data: Optional[Dict[str, Any]] = None,
        project: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Record a user activity.

        Delegates to activity detector if enabled.

        Args:
            activity_type: Type of activity
            data: Activity-specific data
            project: Project name (if applicable)
            file_path: File path (if applicable)
        """
        if self._activity_detector:
            self._activity_detector.record_activity(
                activity_type,
                data=data,
                project=project or self.config.project_name,
                file_path=file_path,
            )

    def add_file_watch_path(self, path: str) -> bool:
        """Add a path to file watching.

        Args:
            path: Directory path to watch

        Returns:
            True if added successfully
        """
        if self._file_watcher:
            return self._file_watcher.add_watch_path(path)

        self.config.file_watch_paths.append(path)
        return True

    def add_git_repo(self, repo_path: str) -> bool:
        """Add a git repository to watch.

        Args:
            repo_path: Path to git repository

        Returns:
            True if added successfully
        """
        if self._git_watcher:
            return self._git_watcher.add_repo(repo_path)

        self.config.git_repo_paths.append(repo_path)
        return True

    def add_schedule(self, schedule: ScheduledTrigger) -> None:
        """Add a scheduled trigger.

        Args:
            schedule: ScheduledTrigger to add
        """
        if self._time_scheduler:
            self._time_scheduler.add_schedule(schedule)
        else:
            if self.config.time_schedules is None:
                self.config.time_schedules = []
            self.config.time_schedules.append(schedule)

    def trigger_manual_git_check(self, repo_path: str) -> None:
        """Trigger manual git check for a repository.

        Args:
            repo_path: Path to git repository
        """
        if self._git_watcher:
            self._git_watcher.trigger_manual_check(repo_path)

    def trigger_scheduled_now(self, trigger_id: str) -> bool:
        """Trigger a scheduled event immediately.

        Args:
            trigger_id: ID of scheduled trigger

        Returns:
            True if triggered
        """
        if self._time_scheduler:
            return self._time_scheduler.trigger_now(trigger_id)
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all watchers.

        Returns:
            Dict with combined stats
        """
        stats = {
            "running": self._running,
            "watchers_enabled": {
                "file_watcher": self._file_watcher is not None,
                "git_watcher": self._git_watcher is not None,
                "time_scheduler": self._time_scheduler is not None,
                "activity_detector": self._activity_detector is not None,
            },
        }

        if self._file_watcher:
            stats["file_watcher"] = self._file_watcher.get_stats()

        if self._git_watcher:
            stats["git_watcher"] = self._git_watcher.get_stats()

        if self._time_scheduler:
            stats["time_scheduler"] = self._time_scheduler.get_stats()

        if self._activity_detector:
            stats["activity_detector"] = self._activity_detector.get_stats()

        # Add injector stats
        stats["injector"] = self.injector.get_stats().to_dict()

        return stats

    @property
    def file_watcher(self) -> Optional[FileWatcher]:
        """Get file watcher instance."""
        return self._file_watcher

    @property
    def git_watcher(self) -> Optional[GitWatcher]:
        """Get git watcher instance."""
        return self._git_watcher

    @property
    def time_scheduler(self) -> Optional[TimeScheduler]:
        """Get time scheduler instance."""
        return self._time_scheduler

    @property
    def activity_detector(self) -> Optional[ActivityDetector]:
        """Get activity detector instance."""
        return self._activity_detector


# Singleton instance
_manager_instance: Optional[WatcherManager] = None


def get_watcher_manager(
    injector: Optional[ProactiveContextInjector] = None,
    config: Optional[WatcherManagerConfig] = None,
) -> WatcherManager:
    """Get singleton WatcherManager instance.

    Args:
        injector: ProactiveContextInjector (required on first call)
        config: WatcherManagerConfig (optional)

    Returns:
        WatcherManager instance
    """
    global _manager_instance

    if _manager_instance is None:
        if injector is None:
            raise ValueError("injector required for first initialization")
        _manager_instance = WatcherManager(injector, config)

    return _manager_instance


async def start_proactive_watchers(
    injector: ProactiveContextInjector,
    config: Optional[WatcherManagerConfig] = None,
) -> WatcherManager:
    """Convenience function to start proactive watchers.

    Args:
        injector: ProactiveContextInjector
        config: WatcherManagerConfig (optional)

    Returns:
        Started WatcherManager
    """
    manager = get_watcher_manager(injector, config)
    await manager.start()
    return manager
