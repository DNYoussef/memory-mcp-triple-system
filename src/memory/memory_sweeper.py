"""
Memory Sweeper Daemon - Continuous memory cleanup and optimization
Part of META-004: Waste System (Memory Compaction)

Background daemon that monitors memory health and triggers
cleanup operations based on configurable thresholds.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class SweeperState(str, Enum):
    """Sweeper daemon states"""
    IDLE = "idle"
    RUNNING = "running"
    SWEEPING = "sweeping"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class SweeperAction(str, Enum):
    """Actions the sweeper can take"""
    CONSOLIDATE = "consolidate"
    ARCHIVE = "archive"
    DELETE = "delete"
    DEMOTE = "demote"
    DEDUPLICATE = "deduplicate"
    COMPACT_GRAPH = "compact_graph"
    REINDEX = "reindex"


@dataclass
class SweeperMetrics:
    """Metrics from sweeper operations"""
    total_runs: int = 0
    total_chunks_processed: int = 0
    total_bytes_freed: int = 0
    total_chunks_archived: int = 0
    total_chunks_deleted: int = 0
    total_duplicates_merged: int = 0
    last_run_at: Optional[datetime] = None
    last_run_duration_ms: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "total_chunks_processed": self.total_chunks_processed,
            "total_bytes_freed": self.total_bytes_freed,
            "total_chunks_archived": self.total_chunks_archived,
            "total_chunks_deleted": self.total_chunks_deleted,
            "total_duplicates_merged": self.total_duplicates_merged,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_duration_ms": self.last_run_duration_ms,
            "errors": self.errors
        }


@dataclass
class SweeperConfig:
    """Configuration for memory sweeper"""
    # Sweep intervals
    sweep_interval_seconds: int = 3600  # 1 hour default
    aggressive_sweep_interval: int = 300  # 5 min when memory pressure high

    # Thresholds
    memory_pressure_threshold: float = 0.8  # 80% triggers aggressive mode
    chunk_age_days: int = 30
    min_confidence: float = 0.3
    similarity_threshold: float = 0.95

    # Limits
    max_chunks_per_sweep: int = 1000
    max_deletes_per_sweep: int = 100
    max_archives_per_sweep: int = 500

    # Features
    enable_deduplication: bool = True
    enable_archival: bool = True
    enable_deletion: bool = True
    enable_graph_compaction: bool = True
    dry_run: bool = False


@dataclass
class SweepResult:
    """Result of a single sweep operation"""
    sweep_id: str
    started_at: datetime
    completed_at: datetime
    state: SweeperState
    actions_taken: Dict[str, int] = field(default_factory=dict)
    bytes_freed: int = 0
    chunks_processed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sweep_id": self.sweep_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "state": self.state.value,
            "actions_taken": self.actions_taken,
            "bytes_freed": self.bytes_freed,
            "chunks_processed": self.chunks_processed,
            "errors": self.errors
        }


class MemorySweeper:
    """
    Background daemon for continuous memory optimization.

    Features:
    1. Periodic sweeps for stale content
    2. Memory pressure detection
    3. Automatic deduplication
    4. Graph compaction
    5. Lifecycle management (demote/archive/delete)
    """

    def __init__(self, config: Optional[SweeperConfig] = None):
        self.config = config or SweeperConfig()
        self.state = SweeperState.IDLE
        self.metrics = SweeperMetrics()
        self._sweep_counter = 0
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

        # Callbacks for actual operations (injected by user)
        self._callbacks: Dict[SweeperAction, Callable[..., Awaitable[Any]]] = {}

        # History of recent sweeps
        self._sweep_history: List[SweepResult] = []
        self._max_history = 100

    def register_callback(
        self,
        action: SweeperAction,
        callback: Callable[..., Awaitable[Any]]
    ) -> None:
        """
        Register a callback for a sweeper action.

        Callbacks should be async functions that perform the actual
        memory operations (e.g., database deletes, archival).
        """
        self._callbacks[action] = callback
        logger.info(f"Registered callback for action: {action.value}")

    async def start(self) -> None:
        """Start the sweeper daemon"""
        if self.state == SweeperState.RUNNING:
            logger.warning("Sweeper already running")
            return

        self.state = SweeperState.RUNNING
        self._stop_event.clear()
        self._task = asyncio.create_task(self._sweep_loop())
        logger.info("Memory sweeper daemon started")

    async def stop(self) -> None:
        """Stop the sweeper daemon"""
        if self.state == SweeperState.STOPPED:
            return

        logger.info("Stopping memory sweeper daemon...")
        self._stop_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=30.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                logger.warning("Sweeper task cancelled due to timeout")

        self.state = SweeperState.STOPPED
        logger.info("Memory sweeper daemon stopped")

    def pause(self) -> None:
        """Pause the sweeper (current sweep will complete)"""
        self._pause_event.clear()
        self.state = SweeperState.PAUSED
        logger.info("Memory sweeper paused")

    def resume(self) -> None:
        """Resume the sweeper"""
        self._pause_event.set()
        self.state = SweeperState.RUNNING
        logger.info("Memory sweeper resumed")

    async def trigger_sweep(self, force: bool = False) -> SweepResult:
        """Manually trigger a sweep operation"""
        return await self._run_sweep(force=force)

    async def _sweep_loop(self) -> None:
        """Main sweep loop"""
        while not self._stop_event.is_set():
            try:
                # Wait for pause to be lifted
                await self._pause_event.wait()

                # Check if we should stop
                if self._stop_event.is_set():
                    break

                # Determine interval based on memory pressure
                interval = await self._get_sweep_interval()

                # Wait for interval or stop signal
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=interval
                    )
                    # If we get here, stop was requested
                    break
                except asyncio.TimeoutError:
                    # Timeout means interval elapsed, run sweep
                    pass

                # Run the sweep
                await self._run_sweep()

            except Exception as e:
                logger.error(f"Error in sweep loop: {e}")
                self.metrics.errors += 1
                self.state = SweeperState.ERROR
                await asyncio.sleep(60)  # Back off on error
                self.state = SweeperState.RUNNING

    async def _get_sweep_interval(self) -> int:
        """Determine sweep interval based on conditions"""
        # Check memory pressure
        pressure = await self._check_memory_pressure()

        if pressure > self.config.memory_pressure_threshold:
            logger.info(f"Memory pressure high ({pressure:.2%}), using aggressive interval")
            return self.config.aggressive_sweep_interval

        return self.config.sweep_interval_seconds

    async def _check_memory_pressure(self) -> float:
        """Check current memory pressure (0.0 to 1.0)"""
        # If callback registered, use it
        if SweeperAction.COMPACT_GRAPH in self._callbacks:
            try:
                # This could be a callback that returns memory stats
                # For now, return a default value
                return 0.5
            except Exception:
                pass

        # Default: no pressure
        return 0.0

    async def _run_sweep(self, force: bool = False) -> SweepResult:
        """Execute a single sweep operation"""
        self._sweep_counter += 1
        sweep_id = f"sweep-{self._sweep_counter}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        self.state = SweeperState.SWEEPING
        started_at = datetime.utcnow()

        result = SweepResult(
            sweep_id=sweep_id,
            started_at=started_at,
            completed_at=started_at,
            state=SweeperState.SWEEPING
        )

        try:
            logger.info(f"Starting sweep {sweep_id}")

            # Run cleanup phases
            if self.config.enable_deduplication:
                await self._phase_deduplicate(result)

            if self.config.enable_archival:
                await self._phase_archive_stale(result)

            if self.config.enable_deletion:
                await self._phase_delete_expired(result)

            if self.config.enable_graph_compaction:
                await self._phase_compact_graph(result)

            result.state = SweeperState.IDLE

        except Exception as e:
            logger.error(f"Sweep {sweep_id} failed: {e}")
            result.errors.append(str(e))
            result.state = SweeperState.ERROR
            self.metrics.errors += 1

        finally:
            result.completed_at = datetime.utcnow()
            duration_ms = int((result.completed_at - started_at).total_seconds() * 1000)

            # Update metrics
            self.metrics.total_runs += 1
            self.metrics.total_chunks_processed += result.chunks_processed
            self.metrics.total_bytes_freed += result.bytes_freed
            self.metrics.last_run_at = result.completed_at
            self.metrics.last_run_duration_ms = duration_ms

            # Store in history
            self._sweep_history.append(result)
            if len(self._sweep_history) > self._max_history:
                self._sweep_history = self._sweep_history[-self._max_history:]

            self.state = SweeperState.RUNNING if self._task else SweeperState.IDLE

            logger.info(
                f"Sweep {sweep_id} complete: {result.chunks_processed} chunks, "
                f"{result.bytes_freed} bytes freed, {duration_ms}ms"
            )

        return result

    async def _phase_deduplicate(self, result: SweepResult) -> None:
        """Phase 1: Find and merge duplicate chunks"""
        if SweeperAction.DEDUPLICATE not in self._callbacks:
            return

        try:
            callback = self._callbacks[SweeperAction.DEDUPLICATE]
            dedup_result = await callback(
                similarity_threshold=self.config.similarity_threshold,
                max_pairs=self.config.max_chunks_per_sweep,
                dry_run=self.config.dry_run
            )

            merged = dedup_result.get("merged", 0)
            result.actions_taken["deduplicate"] = merged
            result.chunks_processed += merged * 2
            self.metrics.total_duplicates_merged += merged

        except Exception as e:
            logger.error(f"Deduplication phase failed: {e}")
            result.errors.append(f"deduplicate: {e}")

    async def _phase_archive_stale(self, result: SweepResult) -> None:
        """Phase 2: Archive old, low-access chunks"""
        if SweeperAction.ARCHIVE not in self._callbacks:
            return

        try:
            callback = self._callbacks[SweeperAction.ARCHIVE]
            archive_result = await callback(
                age_days=self.config.chunk_age_days,
                max_chunks=self.config.max_archives_per_sweep,
                dry_run=self.config.dry_run
            )

            archived = archive_result.get("archived", 0)
            bytes_freed = archive_result.get("bytes_freed", 0)

            result.actions_taken["archive"] = archived
            result.chunks_processed += archived
            result.bytes_freed += bytes_freed
            self.metrics.total_chunks_archived += archived

        except Exception as e:
            logger.error(f"Archive phase failed: {e}")
            result.errors.append(f"archive: {e}")

    async def _phase_delete_expired(self, result: SweepResult) -> None:
        """Phase 3: Delete chunks past retention"""
        if SweeperAction.DELETE not in self._callbacks:
            return

        try:
            callback = self._callbacks[SweeperAction.DELETE]
            delete_result = await callback(
                min_confidence=self.config.min_confidence,
                max_chunks=self.config.max_deletes_per_sweep,
                dry_run=self.config.dry_run
            )

            deleted = delete_result.get("deleted", 0)
            bytes_freed = delete_result.get("bytes_freed", 0)

            result.actions_taken["delete"] = deleted
            result.chunks_processed += deleted
            result.bytes_freed += bytes_freed
            self.metrics.total_chunks_deleted += deleted

        except Exception as e:
            logger.error(f"Delete phase failed: {e}")
            result.errors.append(f"delete: {e}")

    async def _phase_compact_graph(self, result: SweepResult) -> None:
        """Phase 4: Compact the knowledge graph"""
        if SweeperAction.COMPACT_GRAPH not in self._callbacks:
            return

        try:
            callback = self._callbacks[SweeperAction.COMPACT_GRAPH]
            compact_result = await callback(dry_run=self.config.dry_run)

            nodes_removed = compact_result.get("nodes_removed", 0)
            edges_removed = compact_result.get("edges_removed", 0)

            result.actions_taken["compact_graph"] = nodes_removed + edges_removed

        except Exception as e:
            logger.error(f"Graph compaction failed: {e}")
            result.errors.append(f"compact_graph: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current sweeper metrics"""
        return {
            "state": self.state.value,
            "config": {
                "sweep_interval_seconds": self.config.sweep_interval_seconds,
                "memory_pressure_threshold": self.config.memory_pressure_threshold,
                "dry_run": self.config.dry_run
            },
            "metrics": self.metrics.to_dict()
        }

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sweep history"""
        return [s.to_dict() for s in self._sweep_history[-limit:]]


# Singleton instance
_sweeper_instance: Optional[MemorySweeper] = None


def get_memory_sweeper(config: Optional[SweeperConfig] = None) -> MemorySweeper:
    """Get singleton memory sweeper instance"""
    global _sweeper_instance
    if _sweeper_instance is None:
        _sweeper_instance = MemorySweeper(config)
    return _sweeper_instance


async def start_sweeper_daemon(config: Optional[SweeperConfig] = None) -> MemorySweeper:
    """Convenience function to start the sweeper daemon"""
    sweeper = get_memory_sweeper(config)
    await sweeper.start()
    return sweeper
