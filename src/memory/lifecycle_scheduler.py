"""
Lifecycle Scheduler - Background task for lifecycle transitions.

Runs periodic demotion, archival, and cleanup operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .lifecycle_manager import MemoryLifecycleManager

logger = logging.getLogger(__name__)

# How often each sweep should run, measured as elapsed time since its last run
# (NOT a wall-clock hour). Anchoring to elapsed time means a sweep is never
# skipped just because the process was not alive at a particular hour.
ARCHIVAL_INTERVAL = timedelta(hours=6)
CLEANUP_INTERVAL = timedelta(hours=24)


class LifecycleScheduler:
    """Background scheduler for memory lifecycle transitions."""

    def __init__(self, lifecycle_manager: MemoryLifecycleManager):
        self.manager = lifecycle_manager
        self._running = False
        self._task: Optional[asyncio.Task] = None
        # Last time each periodic sweep actually ran. None means "never yet",
        # so the first loop iteration runs it (sweeping anything that piled up
        # while the process was down) instead of waiting for a wall-clock hour.
        self._last_archival: Optional[datetime] = None
        self._last_cleanup: Optional[datetime] = None

    async def start(self) -> None:
        """Start the lifecycle scheduler."""
        if self._running:
            logger.warning("Lifecycle scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Lifecycle scheduler started")

    async def stop(self) -> None:
        """Stop the lifecycle scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("Lifecycle scheduler task cancelled")
        logger.info("Lifecycle scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.now()

                logger.debug("Running hourly demotion check")
                demoted_count = await asyncio.to_thread(
                    self.manager.demote_stale_chunks
                )
                if demoted_count:
                    logger.info("Demoted %s stale chunks", demoted_count)

                if self._last_archival is None or (
                    now - self._last_archival >= ARCHIVAL_INTERVAL
                ):
                    logger.debug("Running 6-hourly archival check")
                    archived_count = await asyncio.to_thread(
                        self.manager.archive_demoted_chunks
                    )
                    self._last_archival = now
                    if archived_count:
                        logger.info("Archived %s demoted chunks", archived_count)

                if self._last_cleanup is None or (
                    now - self._last_cleanup >= CLEANUP_INTERVAL
                ):
                    logger.debug("Running daily cleanup")
                    cleanup_count = await asyncio.to_thread(
                        self.manager.cleanup_expired
                    )
                    self._last_cleanup = now
                    if cleanup_count:
                        logger.info("Cleaned up %s expired entries", cleanup_count)

            except Exception as exc:
                logger.error("Lifecycle scheduler error: %s", exc, exc_info=True)

            await asyncio.sleep(3600)
