"""
Consolidation Scheduler - Schedule maintenance during quiet periods
Part of META-006: Sleep System (Consolidation Scheduler)

Orchestrates memory consolidation, cleanup, and maintenance operations
during optimal quiet periods detected by the activity monitor.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import random

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    """Priority levels for scheduled tasks"""

    CRITICAL = 1  # Must run, even during activity
    HIGH = 2  # Run during quiet or low activity
    MEDIUM = 3  # Run only during quiet periods
    LOW = 4  # Run only during extended quiet
    BACKGROUND = 5  # Run only during idle


class TaskType(str, Enum):
    """Types of maintenance tasks"""

    CONSOLIDATION = "consolidation"  # Memory chunk consolidation
    DEDUPLICATION = "deduplication"  # Cross-tier deduplication
    GRAPH_COMPACTION = "graph_compaction"
    DRIFT_DETECTION = "drift_detection"
    ARCHIVAL = "archival"  # Move to long-term
    CLEANUP = "cleanup"  # Delete expired
    REINDEX = "reindex"  # Rebuild indices
    BACKUP = "backup"  # Create backup
    HEALTH_CHECK = "health_check"  # System health


@dataclass
class ScheduledTask:
    """A task scheduled for execution"""

    id: str
    task_type: TaskType
    priority: TaskPriority
    callback: Callable[..., Awaitable[Dict[str, Any]]]
    cron_expression: Optional[str] = None  # If time-based
    interval_minutes: Optional[int] = None  # If interval-based
    require_quiet: bool = True
    min_quiet_minutes: int = 10
    max_duration_minutes: int = 60
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of a task execution"""

    task_id: str
    task_type: TaskType
    started_at: datetime
    completed_at: datetime
    success: bool
    duration_ms: int
    result: Dict[str, Any]
    error: Optional[str] = None


class ConsolidationScheduler:
    """
    Schedules and executes maintenance tasks during quiet periods.

    Features:
    1. Priority-based task queue
    2. Quiet period detection integration
    3. Time-based and interval-based scheduling
    4. Backoff on failures
    5. Task history and metrics
    """

    # Default quiet hours (2 AM - 5 AM local time)
    DEFAULT_QUIET_HOURS = (2, 5)

    def __init__(
        self, activity_monitor: Optional[Any] = None, check_interval_seconds: int = 60
    ):
        self._activity_monitor = activity_monitor
        self._check_interval = check_interval_seconds

        self._tasks: Dict[str, ScheduledTask] = {}
        self._task_queue: List[ScheduledTask] = []
        self._history: List[TaskResult] = []
        self._max_history = 1000

        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._current_task: Optional[str] = None
        self._lock = asyncio.Lock()

        # Default scheduled tasks
        self._register_default_tasks()

    def _register_default_tasks(self) -> None:
        """Register default maintenance tasks (without callbacks)"""
        defaults = [
            ("consolidation-daily", TaskType.CONSOLIDATION, TaskPriority.HIGH, 1440),
            ("dedup-weekly", TaskType.DEDUPLICATION, TaskPriority.MEDIUM, 10080),
            ("drift-daily", TaskType.DRIFT_DETECTION, TaskPriority.MEDIUM, 1440),
            ("cleanup-daily", TaskType.CLEANUP, TaskPriority.HIGH, 1440),
            ("health-hourly", TaskType.HEALTH_CHECK, TaskPriority.CRITICAL, 60),
        ]

        for task_id, task_type, priority, interval in defaults:
            self._tasks[task_id] = ScheduledTask(
                id=task_id,
                task_type=task_type,
                priority=priority,
                callback=self._noop_callback,
                interval_minutes=interval,
                require_quiet=priority.value > TaskPriority.CRITICAL.value,
                enabled=False,  # Disabled until callback registered
            )

    async def _noop_callback(self) -> Dict[str, Any]:
        """Placeholder callback"""
        return {"status": "no_callback_registered"}

    async def start(self) -> None:
        """Start the scheduler"""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Consolidation scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler"""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Consolidation scheduler stopped")

    def register_task(
        self,
        task_id: str,
        task_type: TaskType,
        callback: Callable[..., Awaitable[Dict[str, Any]]],
        priority: TaskPriority = TaskPriority.MEDIUM,
        interval_minutes: Optional[int] = None,
        cron_expression: Optional[str] = None,
        require_quiet: bool = True,
        min_quiet_minutes: int = 10,
        max_duration_minutes: int = 60,
    ) -> ScheduledTask:
        """
        Register a new maintenance task.

        Args:
            task_id: Unique task identifier
            task_type: Type of maintenance task
            callback: Async function to execute
            priority: Task priority
            interval_minutes: Run every N minutes
            cron_expression: Cron schedule (alternative to interval)
            require_quiet: Whether task requires quiet period
            min_quiet_minutes: Minimum quiet time before running
            max_duration_minutes: Maximum allowed run time

        Returns:
            The registered ScheduledTask
        """
        task = ScheduledTask(
            id=task_id,
            task_type=task_type,
            priority=priority,
            callback=callback,
            interval_minutes=interval_minutes,
            cron_expression=cron_expression,
            require_quiet=require_quiet,
            min_quiet_minutes=min_quiet_minutes,
            max_duration_minutes=max_duration_minutes,
            enabled=True,
        )

        self._tasks[task_id] = task
        self._update_next_run(task)

        logger.info(f"Registered task: {task_id} ({task_type.value})")
        return task

    def set_callback(
        self, task_id: str, callback: Callable[..., Awaitable[Dict[str, Any]]]
    ) -> bool:
        """Set callback for an existing task and enable it"""
        task = self._tasks.get(task_id)
        if task:
            task.callback = callback
            task.enabled = True
            self._update_next_run(task)
            return True
        return False

    def enable_task(self, task_id: str) -> bool:
        """Enable a task"""
        task = self._tasks.get(task_id)
        if task:
            task.enabled = True
            self._update_next_run(task)
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """Disable a task"""
        task = self._tasks.get(task_id)
        if task:
            task.enabled = False
            return True
        return False

    def _update_next_run(self, task: ScheduledTask) -> None:
        """Calculate next run time for a task"""
        now = datetime.utcnow()

        if task.interval_minutes:
            if task.last_run:
                task.next_run = task.last_run + timedelta(minutes=task.interval_minutes)
            else:
                # First run: schedule soon but with jitter
                jitter = random.randint(0, min(60, task.interval_minutes))
                task.next_run = now + timedelta(minutes=jitter)

        elif task.cron_expression:
            # Simplified cron parsing (HH:MM format)
            try:
                hour, minute = map(int, task.cron_expression.split(":"))
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                task.next_run = target
            except Exception:
                task.next_run = now + timedelta(hours=24)

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                await self._process_due_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

    async def _process_due_tasks(self) -> None:
        """Process tasks that are due for execution"""
        now = datetime.utcnow()

        # Get due tasks sorted by priority
        due_tasks = [
            task
            for task in self._tasks.values()
            if task.enabled and task.next_run and task.next_run <= now
        ]

        due_tasks.sort(key=lambda t: t.priority.value)

        for task in due_tasks:
            # Check if we can run this task
            if await self._can_run_task(task):
                await self._execute_task(task)

    async def _can_run_task(self, task: ScheduledTask) -> bool:
        """Check if conditions allow running this task"""
        # Critical tasks always run
        if task.priority == TaskPriority.CRITICAL:
            return True

        # Check quiet period requirement
        if task.require_quiet:
            if self._activity_monitor:
                # Import here to avoid circular dependency
                from .activity_monitor import ActivityLevel

                level = self._activity_monitor.get_current_level()
                quiet_duration = self._activity_monitor.get_quiet_duration()

                # Check activity level
                if task.priority == TaskPriority.HIGH:
                    allowed_levels = [ActivityLevel.IDLE, ActivityLevel.LOW]
                elif task.priority == TaskPriority.MEDIUM:
                    allowed_levels = [ActivityLevel.IDLE, ActivityLevel.LOW]
                else:
                    allowed_levels = [ActivityLevel.IDLE]

                if level not in allowed_levels:
                    return False

                # Check quiet duration
                if quiet_duration:
                    if quiet_duration.total_seconds() / 60 < task.min_quiet_minutes:
                        return False
                else:
                    return False

            else:
                # No activity monitor - use time-based quiet hours
                hour = datetime.utcnow().hour
                quiet_start, quiet_end = self.DEFAULT_QUIET_HOURS
                if not (quiet_start <= hour < quiet_end):
                    return False

        return True

    async def _execute_task(self, task: ScheduledTask) -> TaskResult:
        """Execute a scheduled task"""
        async with self._lock:
            self._current_task = task.id

        started_at = datetime.utcnow()
        result_data = {}
        error_msg = None
        success = False

        try:
            logger.info(f"Executing task: {task.id}")

            # Execute with timeout
            result_data = await asyncio.wait_for(
                task.callback(), timeout=task.max_duration_minutes * 60
            )
            success = True
            task.run_count += 1

        except asyncio.TimeoutError:
            error_msg = f"Task timed out after {task.max_duration_minutes} minutes"
            task.error_count += 1
            logger.error(f"Task {task.id} timed out")

        except Exception as e:
            error_msg = str(e)
            task.error_count += 1
            logger.error(f"Task {task.id} failed: {e}")

        finally:
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            task.last_run = completed_at
            self._update_next_run(task)

            result = TaskResult(
                task_id=task.id,
                task_type=task.task_type,
                started_at=started_at,
                completed_at=completed_at,
                success=success,
                duration_ms=duration_ms,
                result=result_data,
                error=error_msg,
            )

            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]

            async with self._lock:
                self._current_task = None

            logger.info(
                f"Task {task.id} completed: success={success}, "
                f"duration={duration_ms}ms"
            )

            return result

    async def trigger_task(self, task_id: str) -> Optional[TaskResult]:
        """Manually trigger a task immediately"""
        task = self._tasks.get(task_id)
        if not task:
            return None

        return await self._execute_task(task)

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID"""
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all registered tasks"""
        return [
            {
                "id": t.id,
                "type": t.task_type.value,
                "priority": t.priority.name,
                "enabled": t.enabled,
                "require_quiet": t.require_quiet,
                "interval_minutes": t.interval_minutes,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "next_run": t.next_run.isoformat() if t.next_run else None,
                "run_count": t.run_count,
                "error_count": t.error_count,
            }
            for t in self._tasks.values()
        ]

    def get_history(
        self, task_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get task execution history"""
        history = self._history
        if task_id:
            history = [h for h in history if h.task_id == task_id]

        return [
            {
                "task_id": h.task_id,
                "task_type": h.task_type.value,
                "started_at": h.started_at.isoformat(),
                "completed_at": h.completed_at.isoformat(),
                "success": h.success,
                "duration_ms": h.duration_ms,
                "error": h.error,
            }
            for h in history[-limit:]
        ]

    def get_metrics(self) -> Dict[str, Any]:
        """Get scheduler metrics"""
        now = datetime.utcnow()

        total_runs = sum(t.run_count for t in self._tasks.values())
        total_errors = sum(t.error_count for t in self._tasks.values())

        recent_history = [
            h for h in self._history if h.completed_at >= now - timedelta(hours=24)
        ]
        recent_success = sum(1 for h in recent_history if h.success)

        return {
            "running": self._running,
            "current_task": self._current_task,
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "total_runs": total_runs,
            "total_errors": total_errors,
            "error_rate": total_errors / total_runs if total_runs > 0 else 0,
            "last_24h": {
                "runs": len(recent_history),
                "successes": recent_success,
                "success_rate": (
                    recent_success / len(recent_history) if recent_history else 0
                ),
            },
        }


# Singleton instance
_scheduler_instance: Optional[ConsolidationScheduler] = None


def get_consolidation_scheduler(
    activity_monitor: Optional[Any] = None, check_interval_seconds: int = 60
) -> ConsolidationScheduler:
    """Get singleton consolidation scheduler"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ConsolidationScheduler(
            activity_monitor=activity_monitor,
            check_interval_seconds=check_interval_seconds,
        )
    return _scheduler_instance
