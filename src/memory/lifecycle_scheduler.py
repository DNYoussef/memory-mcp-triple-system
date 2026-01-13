"""
Lifecycle Scheduler - Background task for lifecycle transitions.

Runs periodic demotion, archival, and cleanup operations.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from .lifecycle_manager import MemoryLifecycleManager

logger = logging.getLogger(__name__)


class LifecycleScheduler:
    """Background scheduler for memory lifecycle transitions."""

    def __init__(self, lifecycle_manager: MemoryLifecycleManager):
        self.manager = lifecycle_manager
        self._running = False
        self._task: Optional[asyncio.Task] = None

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
                current_hour = datetime.now().hour

                logger.debug("Running hourly demotion check")
                demoted_count = await asyncio.to_thread(
                    self.manager.demote_stale_chunks
                )
                if demoted_count:
                    logger.info("Demoted %s stale chunks", demoted_count)

                if current_hour % 6 == 0:
                    logger.debug("Running 6-hourly archival check")
                    archived_count = await asyncio.to_thread(
                        self.manager.archive_demoted_chunks
                    )
                    if archived_count:
                        logger.info("Archived %s demoted chunks", archived_count)

                if current_hour == 0:
                    logger.debug("Running daily cleanup")
                    cleanup_count = await asyncio.to_thread(
                        self.manager.cleanup_expired
                    )
                    if cleanup_count:
                        logger.info("Cleaned up %s expired entries", cleanup_count)

            except Exception as exc:
                logger.error("Lifecycle scheduler error: %s", exc, exc_info=True)

            await asyncio.sleep(3600)
