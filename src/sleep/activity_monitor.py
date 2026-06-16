"""
Activity Monitor - Detect quiet periods for sleep/consolidation
Part of META-006: Sleep System (Consolidation Scheduler)

Monitors system activity to detect quiet periods optimal for
memory consolidation and maintenance operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class ActivityLevel(str, Enum):
    """System activity levels"""

    IDLE = "idle"  # No activity, safe for heavy maintenance
    LOW = "low"  # Light activity, safe for light maintenance
    MODERATE = "moderate"  # Normal activity, defer maintenance
    HIGH = "high"  # Heavy activity, avoid any maintenance
    PEAK = "peak"  # Maximum activity, critical path


@dataclass
class ActivityEvent:
    """A recorded activity event"""

    timestamp: datetime
    event_type: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivityWindow:
    """Statistics for an activity time window"""

    start_time: datetime
    end_time: datetime
    event_count: int
    weighted_activity: float
    level: ActivityLevel
    peak_time: Optional[datetime]


class ActivityMonitor:
    """
    Monitors system activity to detect quiet periods.

    Features:
    1. Rolling window activity tracking
    2. Weighted event counting
    3. Quiet period detection
    4. Schedule-based activity prediction
    5. Callbacks for level changes
    """

    # Activity level thresholds (weighted events per minute)
    THRESHOLDS = {
        ActivityLevel.IDLE: 0.0,
        ActivityLevel.LOW: 0.5,
        ActivityLevel.MODERATE: 2.0,
        ActivityLevel.HIGH: 5.0,
        ActivityLevel.PEAK: 10.0,
    }

    # Event type weights
    DEFAULT_WEIGHTS = {
        "api_request": 1.0,
        "memory_write": 1.5,
        "memory_read": 0.5,
        "query": 0.8,
        "background_task": 0.3,
        "user_interaction": 2.0,
        "system_event": 0.2,
    }

    def __init__(
        self,
        window_minutes: int = 5,
        history_hours: int = 24,
        quiet_threshold_minutes: int = 10,
    ):
        self.window_minutes = window_minutes
        self.history_hours = history_hours
        self.quiet_threshold_minutes = quiet_threshold_minutes

        self._events: deque = deque(maxlen=100000)
        self._current_level = ActivityLevel.IDLE
        self._level_changed_at = datetime.utcnow()
        self._callbacks: List[Callable[[ActivityLevel, ActivityLevel], None]] = []
        self._quiet_since: Optional[datetime] = datetime.utcnow()
        self._weights = self.DEFAULT_WEIGHTS.copy()
        self._lock = asyncio.Lock()

        # Historical activity patterns by hour
        self._hourly_patterns: Dict[int, List[float]] = {h: [] for h in range(24)}

    def register_callback(
        self, callback: Callable[[ActivityLevel, ActivityLevel], None]
    ) -> None:
        """Register callback for activity level changes"""
        self._callbacks.append(callback)

    def set_weight(self, event_type: str, weight: float) -> None:
        """Set custom weight for an event type"""
        self._weights[event_type] = weight

    async def record_event(
        self, event_type: str, metadata: Optional[Dict[str, Any]] = None
    ) -> ActivityLevel:
        """
        Record an activity event.

        Returns the current activity level after recording.
        """
        async with self._lock:
            now = datetime.utcnow()
            weight = self._weights.get(event_type, 1.0)

            event = ActivityEvent(
                timestamp=now,
                event_type=event_type,
                weight=weight,
                metadata=metadata or {},
            )

            self._events.append(event)

            # Update current level
            new_level = self._calculate_current_level()

            if new_level != self._current_level:
                old_level = self._current_level
                self._current_level = new_level
                self._level_changed_at = now

                # Update quiet tracking
                if new_level in [ActivityLevel.IDLE, ActivityLevel.LOW]:
                    if self._quiet_since is None:
                        self._quiet_since = now
                else:
                    self._quiet_since = None

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(old_level, new_level)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

                logger.debug(
                    f"Activity level changed: {old_level.value} -> {new_level.value}"
                )

            # Record for hourly patterns
            hour = now.hour
            self._hourly_patterns[hour].append(weight)
            if len(self._hourly_patterns[hour]) > 1000:
                self._hourly_patterns[hour] = self._hourly_patterns[hour][-1000:]

            return self._current_level

    def _calculate_current_level(self) -> ActivityLevel:
        """Calculate current activity level from recent events"""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)

        # Count weighted events in window
        weighted_sum = sum(
            e.weight for e in self._events if e.timestamp >= window_start
        )

        # Convert to events per minute
        events_per_minute = weighted_sum / self.window_minutes

        # Determine level
        if events_per_minute >= self.THRESHOLDS[ActivityLevel.PEAK]:
            return ActivityLevel.PEAK
        elif events_per_minute >= self.THRESHOLDS[ActivityLevel.HIGH]:
            return ActivityLevel.HIGH
        elif events_per_minute >= self.THRESHOLDS[ActivityLevel.MODERATE]:
            return ActivityLevel.MODERATE
        elif events_per_minute >= self.THRESHOLDS[ActivityLevel.LOW]:
            return ActivityLevel.LOW
        else:
            return ActivityLevel.IDLE

    def is_quiet_period(self) -> bool:
        """Check if system is in a quiet period"""
        if self._quiet_since is None:
            return False

        quiet_duration = datetime.utcnow() - self._quiet_since
        return quiet_duration >= timedelta(minutes=self.quiet_threshold_minutes)

    def get_quiet_duration(self) -> Optional[timedelta]:
        """Get how long the system has been quiet"""
        if self._quiet_since is None:
            return None
        return datetime.utcnow() - self._quiet_since

    def get_current_level(self) -> ActivityLevel:
        """Get current activity level"""
        return self._current_level

    def get_activity_window(
        self, window_minutes: Optional[int] = None
    ) -> ActivityWindow:
        """Get activity statistics for a time window"""
        now = datetime.utcnow()
        minutes = window_minutes or self.window_minutes
        window_start = now - timedelta(minutes=minutes)

        events_in_window = [e for e in self._events if e.timestamp >= window_start]

        weighted_activity = sum(e.weight for e in events_in_window)
        peak_time = None
        if events_in_window:
            peak_event = max(events_in_window, key=lambda e: e.weight)
            peak_time = peak_event.timestamp

        return ActivityWindow(
            start_time=window_start,
            end_time=now,
            event_count=len(events_in_window),
            weighted_activity=weighted_activity,
            level=self._current_level,
            peak_time=peak_time,
        )

    def predict_activity(self, hours_ahead: int = 1) -> ActivityLevel:
        """
        Predict activity level for upcoming hours based on patterns.

        Uses historical hourly patterns to predict activity.
        """
        now = datetime.utcnow()
        target_hour = (now.hour + hours_ahead) % 24

        # Get historical pattern for target hour
        pattern = self._hourly_patterns.get(target_hour, [])

        if not pattern:
            return ActivityLevel.MODERATE  # Default prediction

        avg_activity = sum(pattern) / len(pattern) / self.window_minutes

        # Map to level
        if avg_activity >= self.THRESHOLDS[ActivityLevel.PEAK]:
            return ActivityLevel.PEAK
        elif avg_activity >= self.THRESHOLDS[ActivityLevel.HIGH]:
            return ActivityLevel.HIGH
        elif avg_activity >= self.THRESHOLDS[ActivityLevel.MODERATE]:
            return ActivityLevel.MODERATE
        elif avg_activity >= self.THRESHOLDS[ActivityLevel.LOW]:
            return ActivityLevel.LOW
        else:
            return ActivityLevel.IDLE

    def get_best_maintenance_window(
        self, duration_hours: int = 2, lookahead_hours: int = 24
    ) -> Optional[int]:
        """
        Find the best upcoming hour for maintenance.

        Returns hour (0-23) with lowest predicted activity.
        """
        now = datetime.utcnow()
        best_hour = None
        lowest_activity = float("inf")

        for offset in range(lookahead_hours):
            target_hour = (now.hour + offset) % 24
            pattern = self._hourly_patterns.get(target_hour, [])

            if pattern:
                avg = sum(pattern) / len(pattern)
                if avg < lowest_activity:
                    lowest_activity = avg
                    best_hour = target_hour

        return best_hour

    def get_hourly_patterns(self) -> Dict[int, float]:
        """Get average activity by hour"""
        result = {}
        for hour, pattern in self._hourly_patterns.items():
            if pattern:
                result[hour] = sum(pattern) / len(pattern)
            else:
                result[hour] = 0.0
        return result

    def get_metrics(self) -> Dict[str, Any]:
        """Get activity monitor metrics"""
        window = self.get_activity_window()

        return {
            "current_level": self._current_level.value,
            "level_changed_at": self._level_changed_at.isoformat(),
            "is_quiet_period": self.is_quiet_period(),
            "quiet_duration_minutes": (
                self.get_quiet_duration().total_seconds() / 60
                if self.get_quiet_duration()
                else None
            ),
            "window": {
                "event_count": window.event_count,
                "weighted_activity": round(window.weighted_activity, 3),
                "events_per_minute": round(
                    window.weighted_activity / self.window_minutes, 3
                ),
            },
            "total_events_tracked": len(self._events),
            "hourly_patterns_available": sum(
                1 for p in self._hourly_patterns.values() if p
            ),
        }


# Singleton instance
_activity_monitor: Optional[ActivityMonitor] = None


def get_activity_monitor(
    window_minutes: int = 5, history_hours: int = 24, quiet_threshold_minutes: int = 10
) -> ActivityMonitor:
    """Get singleton activity monitor"""
    global _activity_monitor
    if _activity_monitor is None:
        _activity_monitor = ActivityMonitor(
            window_minutes=window_minutes,
            history_hours=history_hours,
            quiet_threshold_minutes=quiet_threshold_minutes,
        )
    return _activity_monitor
