"""Time-Based Scheduler for Proactive Context Injection.

Triggers context injection based on time-of-day patterns.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

import asyncio
from datetime import datetime, time, timedelta
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from ..proactive_context_injector import ProactiveContextInjector
from ...integrations.proactive_schema import TriggerEvent, TriggerType, ContextPriority


class DayOfWeek(Enum):
    """Days of the week (ISO 8601 numbering)."""
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


@dataclass
class ScheduledTrigger:
    """A scheduled time-based trigger."""

    trigger_id: str
    hour: int  # 0-23
    minute: int = 0
    days: List[DayOfWeek] = field(default_factory=lambda: list(DayOfWeek))
    context_query: str = ""
    priority: ContextPriority = ContextPriority.MEDIUM
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_triggered: Optional[datetime] = None

    def matches_now(self, now: datetime) -> bool:
        """Check if this trigger should fire now."""
        if not self.enabled:
            return False

        # Check day of week
        current_day = DayOfWeek(now.isoweekday())
        if current_day not in self.days:
            return False

        # Check time (within 1 minute window)
        if now.hour != self.hour:
            return False
        if now.minute != self.minute:
            return False

        # Check if already triggered this minute
        if self.last_triggered:
            if (now - self.last_triggered).total_seconds() < 60:
                return False

        return True


@dataclass
class TimePattern:
    """Common time patterns for scheduling."""

    @staticmethod
    def weekday_morning(hour: int = 9) -> ScheduledTrigger:
        """Create weekday morning trigger."""
        return ScheduledTrigger(
            trigger_id=f"weekday-morning-{hour}",
            hour=hour,
            minute=0,
            days=[DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY,
                  DayOfWeek.THURSDAY, DayOfWeek.FRIDAY],
            context_query="morning standup daily tasks priorities",
            priority=ContextPriority.MEDIUM,
            metadata={"pattern": "weekday_morning"},
        )

    @staticmethod
    def weekday_afternoon(hour: int = 14) -> ScheduledTrigger:
        """Create weekday afternoon trigger."""
        return ScheduledTrigger(
            trigger_id=f"weekday-afternoon-{hour}",
            hour=hour,
            minute=0,
            days=[DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY,
                  DayOfWeek.THURSDAY, DayOfWeek.FRIDAY],
            context_query="afternoon progress blockers help-needed",
            priority=ContextPriority.LOW,
            metadata={"pattern": "weekday_afternoon"},
        )

    @staticmethod
    def end_of_day(hour: int = 17) -> ScheduledTrigger:
        """Create end-of-day trigger."""
        return ScheduledTrigger(
            trigger_id=f"end-of-day-{hour}",
            hour=hour,
            minute=0,
            days=[DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY,
                  DayOfWeek.THURSDAY, DayOfWeek.FRIDAY],
            context_query="daily summary accomplishments tomorrow",
            priority=ContextPriority.MEDIUM,
            metadata={"pattern": "end_of_day"},
        )

    @staticmethod
    def weekly_review(day: DayOfWeek = DayOfWeek.FRIDAY, hour: int = 16) -> ScheduledTrigger:
        """Create weekly review trigger."""
        return ScheduledTrigger(
            trigger_id=f"weekly-review-{day.name.lower()}",
            hour=hour,
            minute=0,
            days=[day],
            context_query="weekly review goals progress next-week",
            priority=ContextPriority.HIGH,
            metadata={"pattern": "weekly_review"},
        )

    @staticmethod
    def monday_planning(hour: int = 9) -> ScheduledTrigger:
        """Create Monday planning trigger."""
        return ScheduledTrigger(
            trigger_id="monday-planning",
            hour=hour,
            minute=0,
            days=[DayOfWeek.MONDAY],
            context_query="week planning priorities goals deadlines",
            priority=ContextPriority.HIGH,
            metadata={"pattern": "monday_planning"},
        )


# Default scheduled triggers
DEFAULT_SCHEDULES = [
    TimePattern.weekday_morning(9),
    TimePattern.weekday_afternoon(14),
    TimePattern.end_of_day(17),
    TimePattern.weekly_review(),
    TimePattern.monday_planning(),
]


class TimeScheduler:
    """Time-based scheduler for proactive context injection.

    Triggers context injection at scheduled times (morning standup,
    end of day review, weekly summaries, etc.).

    Usage:
        scheduler = TimeScheduler(injector)
        scheduler.add_schedule(TimePattern.weekday_morning())
        await scheduler.start()
        # ... later
        await scheduler.stop()
    """

    def __init__(
        self,
        injector: ProactiveContextInjector,
        schedules: Optional[List[ScheduledTrigger]] = None,
        check_interval: float = 30.0,
    ):
        """Initialize time scheduler.

        Args:
            injector: ProactiveContextInjector for triggering context injection
            schedules: Initial scheduled triggers (default: DEFAULT_SCHEDULES)
            check_interval: Seconds between schedule checks
        """
        self.injector = injector
        self.check_interval = check_interval
        self._schedules: Dict[str, ScheduledTrigger] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None

        # Initialize with provided or default schedules
        for schedule in (schedules or DEFAULT_SCHEDULES):
            self._schedules[schedule.trigger_id] = schedule

        logger.info(f"TimeScheduler initialized with {len(self._schedules)} schedules")

    async def _check_schedules(self) -> None:
        """Check and trigger scheduled events."""
        while self._running:
            now = datetime.now()
            # Iterate a snapshot so a concurrent add/remove_schedule cannot
            # raise "dict changed size during iteration".
            for schedule in list(self._schedules.values()):
                try:
                    if schedule.matches_now(now):
                        await self._trigger_scheduled(schedule, now)
                except asyncio.CancelledError:
                    # stop() cancels this task - propagate so it exits cleanly.
                    raise
                except Exception as exc:
                    # Guard PER schedule: one bad schedule is skipped so every
                    # other schedule in the snapshot still runs this cycle, and
                    # the loop never dies (no restart; _running stays True).
                    logger.error(
                        f"Schedule '{getattr(schedule, 'trigger_id', '?')}' "
                        f"failed (skipping): {exc}"
                    )

            await asyncio.sleep(self.check_interval)

    async def _trigger_scheduled(
        self,
        schedule: ScheduledTrigger,
        now: datetime,
    ) -> None:
        """Trigger context injection for a scheduled event."""
        try:
            event = TriggerEvent.from_time_of_day(
                hour=schedule.hour,
                day_of_week=now.isoweekday(),
            )

            # Override context query with schedule's query
            event.context_query = schedule.context_query
            event.priority = schedule.priority
            event.metadata.update(schedule.metadata)
            event.metadata["trigger_id"] = schedule.trigger_id

            context = await self.injector.handle_trigger(event)

            # Update last triggered time
            schedule.last_triggered = now

            if context:
                logger.info(
                    f"Scheduled injection triggered: {schedule.trigger_id}, "
                    f"{len(context.chunks)} chunks"
                )
            else:
                logger.debug(f"Scheduled trigger {schedule.trigger_id} produced no context")

        except Exception as e:
            logger.error(f"Failed to trigger scheduled injection: {e}")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("TimeScheduler already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._check_schedules())

        logger.info(
            f"TimeScheduler started with {len(self._schedules)} schedules, "
            f"checking every {self.check_interval}s"
        )

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

        logger.info("TimeScheduler stopped")

    def add_schedule(self, schedule: ScheduledTrigger) -> None:
        """Add or update a scheduled trigger.

        Args:
            schedule: ScheduledTrigger to add
        """
        self._schedules[schedule.trigger_id] = schedule
        logger.info(f"Added schedule: {schedule.trigger_id}")

    def remove_schedule(self, trigger_id: str) -> bool:
        """Remove a scheduled trigger.

        Args:
            trigger_id: ID of trigger to remove

        Returns:
            True if removed, False if not found
        """
        if trigger_id in self._schedules:
            del self._schedules[trigger_id]
            logger.info(f"Removed schedule: {trigger_id}")
            return True
        return False

    def enable_schedule(self, trigger_id: str) -> bool:
        """Enable a scheduled trigger.

        Args:
            trigger_id: ID of trigger to enable

        Returns:
            True if enabled, False if not found
        """
        if trigger_id in self._schedules:
            self._schedules[trigger_id].enabled = True
            return True
        return False

    def disable_schedule(self, trigger_id: str) -> bool:
        """Disable a scheduled trigger.

        Args:
            trigger_id: ID of trigger to disable

        Returns:
            True if disabled, False if not found
        """
        if trigger_id in self._schedules:
            self._schedules[trigger_id].enabled = False
            return True
        return False

    def list_schedules(self) -> List[ScheduledTrigger]:
        """List all scheduled triggers.

        Returns:
            List of all schedules
        """
        return list(self._schedules.values())

    def get_next_triggers(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get upcoming triggers within time window.

        Args:
            hours: Hours to look ahead

        Returns:
            List of upcoming trigger info
        """
        now = datetime.now()
        end_time = now + timedelta(hours=hours)
        upcoming = []

        current = now
        while current < end_time:
            for schedule in self._schedules.values():
                if schedule.matches_now(current):
                    upcoming.append({
                        "trigger_id": schedule.trigger_id,
                        "time": current.isoformat(),
                        "query": schedule.context_query,
                        "priority": schedule.priority.value,
                    })

            current += timedelta(minutes=1)

        # Deduplicate (same trigger shouldn't appear multiple times)
        seen = set()
        unique = []
        for item in upcoming:
            key = f"{item['trigger_id']}:{item['time'][:13]}"  # Hour precision
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return sorted(unique, key=lambda x: x["time"])

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics.

        Returns:
            Dict with scheduler stats
        """
        now = datetime.now()

        return {
            "running": self._running,
            "schedule_count": len(self._schedules),
            "enabled_count": sum(1 for s in self._schedules.values() if s.enabled),
            "schedules": [
                {
                    "trigger_id": s.trigger_id,
                    "hour": s.hour,
                    "minute": s.minute,
                    "days": [d.name for d in s.days],
                    "enabled": s.enabled,
                    "last_triggered": s.last_triggered.isoformat() if s.last_triggered else None,
                }
                for s in self._schedules.values()
            ],
            "next_triggers_24h": self.get_next_triggers(24),
        }

    def trigger_now(self, trigger_id: str) -> bool:
        """Manually trigger a schedule immediately.

        Args:
            trigger_id: ID of trigger to fire

        Returns:
            True if triggered, False if not found
        """
        if trigger_id not in self._schedules:
            return False

        schedule = self._schedules[trigger_id]
        asyncio.create_task(self._trigger_scheduled(schedule, datetime.now()))
        return True
