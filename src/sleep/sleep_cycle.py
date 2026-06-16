"""
Sleep Cycle Manager - Orchestrates system sleep/wake cycles
Part of META-006: Sleep System (Consolidation Scheduler)

Manages system state transitions between active and sleep modes,
coordinating consolidation and maintenance during sleep periods.
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SleepState(str, Enum):
    """System sleep states"""

    AWAKE = "awake"  # Normal operation
    DROWSY = "drowsy"  # Preparing for sleep
    LIGHT_SLEEP = "light_sleep"  # Light maintenance
    DEEP_SLEEP = "deep_sleep"  # Heavy maintenance
    WAKING = "waking"  # Transitioning to awake


class WakeReason(str, Enum):
    """Reasons for waking from sleep"""

    SCHEDULED = "scheduled"  # Scheduled wake time
    ACTIVITY_DETECTED = "activity"  # User/system activity
    URGENT_TASK = "urgent_task"  # Urgent task needs execution
    EXTERNAL_TRIGGER = "external"  # Manual wake trigger
    HEALTH_CHECK = "health_check"  # Health check required
    ERROR = "error"  # Error during sleep


@dataclass
class SleepCycleConfig:
    """Configuration for sleep cycle behavior"""

    # Time-based settings (24-hour format)
    preferred_sleep_start: time = time(2, 0)  # 2 AM
    preferred_sleep_end: time = time(6, 0)  # 6 AM

    # Duration settings
    min_sleep_duration_minutes: int = 30
    max_sleep_duration_minutes: int = 240
    drowsy_duration_minutes: int = 5
    waking_duration_minutes: int = 5

    # Activity-based settings
    quiet_threshold_minutes: int = 15
    activity_wake_threshold: float = 2.0

    # Maintenance budgets (per sleep cycle)
    max_consolidation_ops: int = 100
    max_cleanup_ops: int = 50
    max_reindex_ops: int = 10


@dataclass
class SleepMetrics:
    """Metrics from sleep cycles"""

    total_sleep_cycles: int = 0
    total_sleep_duration_seconds: float = 0.0
    avg_sleep_duration_seconds: float = 0.0
    consolidations_performed: int = 0
    cleanups_performed: int = 0
    early_wakes: int = 0
    last_sleep_start: Optional[datetime] = None
    last_wake_time: Optional[datetime] = None
    last_wake_reason: Optional[WakeReason] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sleep_cycles": self.total_sleep_cycles,
            "total_sleep_duration_hours": round(
                self.total_sleep_duration_seconds / 3600, 2
            ),
            "avg_sleep_duration_minutes": round(
                self.avg_sleep_duration_seconds / 60, 2
            ),
            "consolidations_performed": self.consolidations_performed,
            "cleanups_performed": self.cleanups_performed,
            "early_wakes": self.early_wakes,
            "last_sleep_start": self.last_sleep_start.isoformat()
            if self.last_sleep_start
            else None,
            "last_wake_time": self.last_wake_time.isoformat()
            if self.last_wake_time
            else None,
            "last_wake_reason": self.last_wake_reason.value
            if self.last_wake_reason
            else None,
        }


class SleepCycleManager:
    """
    Manages system sleep/wake cycles for optimal maintenance.

    Sleep Cycle Phases:
    1. AWAKE - Normal operation, monitoring activity
    2. DROWSY - Activity low, preparing for sleep
    3. LIGHT_SLEEP - Light maintenance tasks
    4. DEEP_SLEEP - Heavy maintenance tasks
    5. WAKING - Transitioning back to awake

    Features:
    1. Activity-based sleep detection
    2. Time-based sleep scheduling
    3. Interruptible sleep for urgent tasks
    4. Progressive maintenance during sleep
    5. Graceful wake transitions
    """

    def __init__(
        self,
        config: Optional[SleepCycleConfig] = None,
        activity_monitor: Optional[Any] = None,
        scheduler: Optional[Any] = None,
    ):
        self.config = config or SleepCycleConfig()
        self._activity_monitor = activity_monitor
        self._scheduler = scheduler

        self._state = SleepState.AWAKE
        self._state_changed_at = datetime.utcnow()
        self._sleep_start: Optional[datetime] = None
        self._scheduled_wake: Optional[datetime] = None

        self._metrics = SleepMetrics()
        self._running = False
        self._cycle_task: Optional[asyncio.Task] = None
        self._wake_event = asyncio.Event()
        self._lock = asyncio.Lock()

        # Callbacks for state transitions
        self._on_sleep_callbacks: List[Callable[..., Awaitable[None]]] = []
        self._on_wake_callbacks: List[Callable[..., Awaitable[None]]] = []
        self._maintenance_callbacks: Dict[
            str, Callable[..., Awaitable[Dict[str, Any]]]
        ] = {}

    async def start(self) -> None:
        """Start the sleep cycle manager"""
        if self._running:
            return

        self._running = True
        self._cycle_task = asyncio.create_task(self._cycle_loop())
        logger.info("Sleep cycle manager started")

    async def stop(self) -> None:
        """Stop the sleep cycle manager"""
        self._running = False
        self._wake_event.set()  # Wake up if sleeping

        if self._cycle_task:
            self._cycle_task.cancel()
            try:
                await self._cycle_task
            except asyncio.CancelledError:
                pass

        logger.info("Sleep cycle manager stopped")

    def register_on_sleep(self, callback: Callable[..., Awaitable[None]]) -> None:
        """Register callback for when system enters sleep"""
        self._on_sleep_callbacks.append(callback)

    def register_on_wake(self, callback: Callable[..., Awaitable[None]]) -> None:
        """Register callback for when system wakes"""
        self._on_wake_callbacks.append(callback)

    def register_maintenance(
        self, name: str, callback: Callable[..., Awaitable[Dict[str, Any]]]
    ) -> None:
        """Register a maintenance task to run during sleep"""
        self._maintenance_callbacks[name] = callback

    async def trigger_sleep(self, duration_minutes: Optional[int] = None) -> bool:
        """Manually trigger sleep cycle"""
        if self._state != SleepState.AWAKE:
            return False

        duration = duration_minutes or self.config.max_sleep_duration_minutes
        await self._enter_sleep(duration)
        return True

    async def trigger_wake(
        self, reason: WakeReason = WakeReason.EXTERNAL_TRIGGER
    ) -> bool:
        """Manually trigger wake"""
        if self._state == SleepState.AWAKE:
            return False

        await self._wake_up(reason)
        return True

    async def _cycle_loop(self) -> None:
        """Main cycle monitoring loop"""
        while self._running:
            try:
                if self._state == SleepState.AWAKE:
                    await self._monitor_for_sleep()
                else:
                    await self._handle_sleep_state()

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cycle loop error: {e}")

    async def _monitor_for_sleep(self) -> None:
        """Monitor conditions for entering sleep"""
        now = datetime.utcnow()

        # Check if in preferred sleep window
        current_time = now.time()
        in_sleep_window = self._is_in_sleep_window(current_time)

        # Check activity level
        should_sleep = False

        if self._activity_monitor:
            is_quiet = self._activity_monitor.is_quiet_period()
            quiet_duration = self._activity_monitor.get_quiet_duration()

            if is_quiet and quiet_duration:
                quiet_minutes = quiet_duration.total_seconds() / 60
                if quiet_minutes >= self.config.quiet_threshold_minutes:
                    should_sleep = True

        elif in_sleep_window:
            # No activity monitor - use time-based sleep
            should_sleep = True

        if should_sleep:
            await self._transition_to_drowsy()

    def _is_in_sleep_window(self, current_time: time) -> bool:
        """Check if current time is in preferred sleep window"""
        start = self.config.preferred_sleep_start
        end = self.config.preferred_sleep_end

        if start <= end:
            return start <= current_time <= end
        else:
            # Handles overnight window (e.g., 22:00 to 06:00)
            return current_time >= start or current_time <= end

    async def _transition_to_drowsy(self) -> None:
        """Transition to drowsy state"""
        async with self._lock:
            if self._state != SleepState.AWAKE:
                return

            self._state = SleepState.DROWSY
            self._state_changed_at = datetime.utcnow()

        logger.info("Entering drowsy state")

        # Wait in drowsy state
        await asyncio.sleep(self.config.drowsy_duration_minutes * 60)

        # Check if still quiet
        if self._activity_monitor:
            is_quiet = self._activity_monitor.is_quiet_period()
            if not is_quiet:
                await self._cancel_sleep()
                return

        # Enter light sleep
        await self._enter_sleep(self.config.max_sleep_duration_minutes)

    async def _enter_sleep(self, duration_minutes: int) -> None:
        """Enter sleep state"""
        async with self._lock:
            self._state = SleepState.LIGHT_SLEEP
            self._state_changed_at = datetime.utcnow()
            self._sleep_start = datetime.utcnow()
            self._scheduled_wake = self._sleep_start + timedelta(
                minutes=duration_minutes
            )
            self._wake_event.clear()

        logger.info(f"Entering sleep (duration={duration_minutes}min)")

        # Notify callbacks
        for callback in self._on_sleep_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(f"On-sleep callback error: {e}")

        self._metrics.last_sleep_start = self._sleep_start

    async def _handle_sleep_state(self) -> None:
        """Handle operations during sleep states"""
        if self._state == SleepState.LIGHT_SLEEP:
            await self._do_light_maintenance()
            # Progress to deep sleep
            async with self._lock:
                self._state = SleepState.DEEP_SLEEP
                self._state_changed_at = datetime.utcnow()

        elif self._state == SleepState.DEEP_SLEEP:
            await self._do_deep_maintenance()

            # Check if should wake
            now = datetime.utcnow()
            if self._scheduled_wake and now >= self._scheduled_wake:
                await self._wake_up(WakeReason.SCHEDULED)
            elif self._check_should_wake():
                await self._wake_up(WakeReason.ACTIVITY_DETECTED)

        elif self._state == SleepState.DROWSY:
            # Still in drowsy, check if should cancel
            if self._activity_monitor:
                from .activity_monitor import ActivityLevel

                level = self._activity_monitor.get_current_level()
                if level not in [ActivityLevel.IDLE, ActivityLevel.LOW]:
                    await self._cancel_sleep()

        elif self._state == SleepState.WAKING:
            await asyncio.sleep(self.config.waking_duration_minutes * 60)
            async with self._lock:
                self._state = SleepState.AWAKE
                self._state_changed_at = datetime.utcnow()

    def _check_should_wake(self) -> bool:
        """Check if conditions require waking"""
        if self._activity_monitor:
            from .activity_monitor import ActivityLevel

            level = self._activity_monitor.get_current_level()
            return level in [ActivityLevel.HIGH, ActivityLevel.PEAK]
        return False

    async def _do_light_maintenance(self) -> None:
        """Perform light maintenance tasks"""
        logger.info("Performing light maintenance")

        # Run light maintenance callbacks
        for name, callback in self._maintenance_callbacks.items():
            if self._state != SleepState.LIGHT_SLEEP:
                break  # Wake requested

            try:
                result = await asyncio.wait_for(callback(), timeout=300)
                logger.debug(f"Light maintenance {name}: {result}")
            except asyncio.TimeoutError:
                logger.warning(f"Light maintenance {name} timed out")
            except Exception as e:
                logger.error(f"Light maintenance {name} failed: {e}")

    async def _do_deep_maintenance(self) -> None:
        """Perform deep maintenance tasks"""
        logger.info("Performing deep maintenance")
        self._metrics.consolidations_performed += 1

        # Trigger scheduler tasks if available
        if self._scheduler:
            # The scheduler will handle task execution
            pass

    async def _cancel_sleep(self) -> None:
        """Cancel sleep and return to awake"""
        async with self._lock:
            self._state = SleepState.AWAKE
            self._state_changed_at = datetime.utcnow()
            self._sleep_start = None
            self._scheduled_wake = None

        logger.info("Sleep cancelled due to activity")

    async def _wake_up(self, reason: WakeReason) -> None:
        """Wake from sleep"""
        async with self._lock:
            if self._state == SleepState.AWAKE:
                return

            prev_state = self._state  # noqa: F841
            self._state = SleepState.WAKING
            self._state_changed_at = datetime.utcnow()

        logger.info(f"Waking up (reason={reason.value})")

        # Calculate sleep duration
        if self._sleep_start:
            duration = (datetime.utcnow() - self._sleep_start).total_seconds()
            self._metrics.total_sleep_duration_seconds += duration
            self._metrics.total_sleep_cycles += 1
            self._metrics.avg_sleep_duration_seconds = (
                self._metrics.total_sleep_duration_seconds
                / self._metrics.total_sleep_cycles
            )

            # Track early wakes
            if self._scheduled_wake and datetime.utcnow() < self._scheduled_wake:
                self._metrics.early_wakes += 1

        self._metrics.last_wake_time = datetime.utcnow()
        self._metrics.last_wake_reason = reason
        self._sleep_start = None
        self._scheduled_wake = None

        # Notify callbacks
        for callback in self._on_wake_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(f"On-wake callback error: {e}")

        # Complete waking transition
        await asyncio.sleep(self.config.waking_duration_minutes * 60)

        async with self._lock:
            self._state = SleepState.AWAKE
            self._state_changed_at = datetime.utcnow()

    def get_state(self) -> SleepState:
        """Get current sleep state"""
        return self._state

    def is_sleeping(self) -> bool:
        """Check if system is in any sleep state"""
        return self._state in [SleepState.LIGHT_SLEEP, SleepState.DEEP_SLEEP]

    def get_metrics(self) -> Dict[str, Any]:
        """Get sleep cycle metrics"""
        return {
            "state": self._state.value,
            "state_changed_at": self._state_changed_at.isoformat(),
            "is_sleeping": self.is_sleeping(),
            "scheduled_wake": (
                self._scheduled_wake.isoformat() if self._scheduled_wake else None
            ),
            "metrics": self._metrics.to_dict(),
        }


# Singleton instance
_sleep_cycle_manager: Optional[SleepCycleManager] = None


def get_sleep_cycle_manager(
    config: Optional[SleepCycleConfig] = None,
    activity_monitor: Optional[Any] = None,
    scheduler: Optional[Any] = None,
) -> SleepCycleManager:
    """Get singleton sleep cycle manager"""
    global _sleep_cycle_manager
    if _sleep_cycle_manager is None:
        _sleep_cycle_manager = SleepCycleManager(
            config=config, activity_monitor=activity_monitor, scheduler=scheduler
        )
    return _sleep_cycle_manager
