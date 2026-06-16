"""Activity Pattern Detector for Proactive Context Injection.

Detects patterns in user activity and triggers anticipatory context injection.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: implementation (RETRIEVE-001)
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from ..proactive_context_injector import ProactiveContextInjector
from ...integrations.proactive_schema import TriggerEvent, ContextPriority


class ActivityType(str, Enum):
    """Types of user activities."""

    FILE_ACCESS = "file_access"
    SEARCH_QUERY = "search_query"
    TOOL_USE = "tool_use"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    GIT_OPERATION = "git_operation"
    PROJECT_SWITCH = "project_switch"
    ERROR_ENCOUNTERED = "error_encountered"
    TASK_COMPLETE = "task_complete"


@dataclass
class ActivityEvent:
    """A recorded user activity."""

    activity_type: ActivityType
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    project: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class DetectedPattern:
    """A detected activity pattern."""

    pattern_id: str
    pattern_type: str
    confidence: float
    evidence: List[str]  # List of activity descriptions that support this pattern
    context_query: str
    priority: ContextPriority
    detected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PatternMatcher:
    """Base class for pattern matching strategies."""

    def match(
        self,
        activities: List[ActivityEvent],
        window_minutes: int,
    ) -> List[DetectedPattern]:
        """Match patterns in activity history.

        Args:
            activities: List of recent activities
            window_minutes: Time window to consider

        Returns:
            List of detected patterns
        """
        raise NotImplementedError


class SequentialPatternMatcher(PatternMatcher):
    """Detect sequential activity patterns (A -> B -> C)."""

    def __init__(self):
        """Initialize sequential pattern matcher."""
        # Known sequences and their meanings
        self.known_sequences: List[Dict[str, Any]] = [
            {
                "pattern_id": "deep-dive-sequence",
                "sequence": [
                    ActivityType.SEARCH_QUERY,
                    ActivityType.FILE_ACCESS,
                    ActivityType.FILE_ACCESS,
                ],
                "min_matches": 3,
                "context_query": "detailed exploration investigation",
                "priority": ContextPriority.MEDIUM,
            },
            {
                "pattern_id": "debugging-sequence",
                "sequence": [
                    ActivityType.ERROR_ENCOUNTERED,
                    ActivityType.FILE_ACCESS,
                    ActivityType.SEARCH_QUERY,
                ],
                "min_matches": 2,
                "context_query": "debugging error fix troubleshoot",
                "priority": ContextPriority.HIGH,
            },
            {
                "pattern_id": "learning-sequence",
                "sequence": [
                    ActivityType.MEMORY_READ,
                    ActivityType.FILE_ACCESS,
                    ActivityType.MEMORY_WRITE,
                ],
                "min_matches": 2,
                "context_query": "learning documentation reference",
                "priority": ContextPriority.MEDIUM,
            },
            {
                "pattern_id": "task-completion-sequence",
                "sequence": [
                    ActivityType.FILE_ACCESS,
                    ActivityType.GIT_OPERATION,
                    ActivityType.TASK_COMPLETE,
                ],
                "min_matches": 2,
                "context_query": "task completion commit next-task",
                "priority": ContextPriority.LOW,
            },
        ]

    def match(
        self,
        activities: List[ActivityEvent],
        window_minutes: int,
    ) -> List[DetectedPattern]:
        """Match sequential patterns."""
        detected = []
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent = [a for a in activities if a.timestamp >= cutoff]

        if len(recent) < 2:
            return detected

        activity_types = [a.activity_type for a in recent]

        for seq_def in self.known_sequences:
            sequence = seq_def["sequence"]
            min_matches = seq_def["min_matches"]

            # Count subsequence matches
            matches = 0
            for i in range(len(activity_types) - len(sequence) + 1):
                if activity_types[i : i + len(sequence)] == sequence:
                    matches += 1

            if matches >= min_matches:
                confidence = min(0.95, 0.5 + (matches * 0.15))
                detected.append(
                    DetectedPattern(
                        pattern_id=seq_def["pattern_id"],
                        pattern_type="sequential",
                        confidence=confidence,
                        evidence=[
                            f"Sequence matched {matches} times in last {window_minutes} minutes"
                        ],
                        context_query=seq_def["context_query"],
                        priority=seq_def["priority"],
                    )
                )

        return detected


class FrequencyPatternMatcher(PatternMatcher):
    """Detect high-frequency activity patterns."""

    def __init__(
        self,
        frequency_threshold: int = 5,
        window_minutes: int = 15,
    ):
        """Initialize frequency pattern matcher.

        Args:
            frequency_threshold: Number of activities to trigger pattern
            window_minutes: Time window for frequency calculation
        """
        self.frequency_threshold = frequency_threshold
        self.window_minutes = window_minutes

    def match(
        self,
        activities: List[ActivityEvent],
        window_minutes: int,
    ) -> List[DetectedPattern]:
        """Match high-frequency patterns."""
        detected = []
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent = [a for a in activities if a.timestamp >= cutoff]

        # Count activities by type
        type_counts: Dict[ActivityType, int] = defaultdict(int)
        for activity in recent:
            type_counts[activity.activity_type] += 1

        # Check for high-frequency patterns
        for activity_type, count in type_counts.items():
            if count >= self.frequency_threshold:
                pattern = self._create_frequency_pattern(
                    activity_type, count, window_minutes
                )
                if pattern:
                    detected.append(pattern)

        return detected

    def _create_frequency_pattern(
        self,
        activity_type: ActivityType,
        count: int,
        window_minutes: int,
    ) -> Optional[DetectedPattern]:
        """Create a frequency-based pattern."""
        patterns = {
            ActivityType.FILE_ACCESS: {
                "pattern_id": "high-file-access",
                "context_query": "file navigation project structure",
                "priority": ContextPriority.MEDIUM,
            },
            ActivityType.SEARCH_QUERY: {
                "pattern_id": "research-mode",
                "context_query": "research investigation exploration",
                "priority": ContextPriority.HIGH,
            },
            ActivityType.ERROR_ENCOUNTERED: {
                "pattern_id": "error-storm",
                "context_query": "debugging errors fixes common-issues",
                "priority": ContextPriority.CRITICAL,
            },
            ActivityType.MEMORY_READ: {
                "pattern_id": "memory-intensive",
                "context_query": "context recall previous-work",
                "priority": ContextPriority.MEDIUM,
            },
        }

        if activity_type not in patterns:
            return None

        pattern_def = patterns[activity_type]
        confidence = min(0.95, 0.6 + (count - self.frequency_threshold) * 0.05)

        return DetectedPattern(
            pattern_id=pattern_def["pattern_id"],
            pattern_type="frequency",
            confidence=confidence,
            evidence=[
                f"{count} {activity_type.value} events in {window_minutes} minutes"
            ],
            context_query=pattern_def["context_query"],
            priority=pattern_def["priority"],
        )


class ProjectFocusPatternMatcher(PatternMatcher):
    """Detect project focus patterns."""

    def __init__(self, focus_threshold: float = 0.7):
        """Initialize project focus matcher.

        Args:
            focus_threshold: Ratio of activities in one project to trigger
        """
        self.focus_threshold = focus_threshold

    def match(
        self,
        activities: List[ActivityEvent],
        window_minutes: int,
    ) -> List[DetectedPattern]:
        """Match project focus patterns."""
        detected = []
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent = [a for a in activities if a.timestamp >= cutoff and a.project]

        if len(recent) < 3:
            return detected

        # Count activities by project
        project_counts: Dict[str, int] = defaultdict(int)
        for activity in recent:
            if activity.project:
                project_counts[activity.project] += 1

        total = sum(project_counts.values())

        # Check for focused work on single project
        for project, count in project_counts.items():
            ratio = count / total
            if ratio >= self.focus_threshold:
                confidence = min(0.95, ratio)
                detected.append(
                    DetectedPattern(
                        pattern_id=f"project-focus-{project}",
                        pattern_type="project_focus",
                        confidence=confidence,
                        evidence=[f"{ratio:.0%} of activities in project '{project}'"],
                        context_query=f"project:{project} context history",
                        priority=ContextPriority.MEDIUM,
                        metadata={"focused_project": project},
                    )
                )

        return detected


class ActivityDetector:
    """Activity pattern detector for proactive context injection.

    Records user activities and detects patterns that warrant
    anticipatory context injection.

    Usage:
        detector = ActivityDetector(injector)
        await detector.start()

        # Record activities
        detector.record_activity(ActivityType.FILE_ACCESS, {"file": "main.py"})
        detector.record_activity(ActivityType.SEARCH_QUERY, {"query": "how to fix bug"})

        await detector.stop()
    """

    def __init__(
        self,
        injector: ProactiveContextInjector,
        window_minutes: int = 30,
        check_interval: float = 60.0,
        max_history: int = 1000,
    ):
        """Initialize activity detector.

        Args:
            injector: ProactiveContextInjector for triggering context injection
            window_minutes: Time window for pattern detection
            check_interval: Seconds between pattern checks
            max_history: Maximum activity events to keep
        """
        self.injector = injector
        self.window_minutes = window_minutes
        self.check_interval = check_interval
        self.max_history = max_history

        self._activities: List[ActivityEvent] = []
        self._running = False
        self._detector_task: Optional[asyncio.Task] = None
        self._recently_triggered: Set[str] = set()
        self._trigger_cooldown = timedelta(minutes=10)

        # Pattern matchers
        self._matchers: List[PatternMatcher] = [
            SequentialPatternMatcher(),
            FrequencyPatternMatcher(),
            ProjectFocusPatternMatcher(),
        ]

        logger.info("ActivityDetector initialized")

    def record_activity(
        self,
        activity_type: ActivityType,
        data: Optional[Dict[str, Any]] = None,
        project: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Record a user activity.

        Args:
            activity_type: Type of activity
            data: Activity-specific data
            project: Project name (if applicable)
            file_path: File path (if applicable)
        """
        event = ActivityEvent(
            activity_type=activity_type,
            timestamp=datetime.utcnow(),
            data=data or {},
            project=project,
            file_path=file_path,
        )

        self._activities.append(event)

        # Trim history
        if len(self._activities) > self.max_history:
            self._activities = self._activities[-self.max_history :]

        logger.debug(f"Recorded activity: {activity_type.value}")

    async def _detect_patterns(self) -> None:
        """Detect patterns and trigger injections."""
        while self._running:
            try:
                patterns = self._run_pattern_detection()

                for pattern in patterns:
                    await self._trigger_pattern(pattern)

            except Exception as e:
                logger.error(f"Pattern detection error: {e}")

            await asyncio.sleep(self.check_interval)

    def _run_pattern_detection(self) -> List[DetectedPattern]:
        """Run all pattern matchers."""
        all_patterns = []

        for matcher in self._matchers:
            try:
                patterns = matcher.match(self._activities, self.window_minutes)
                all_patterns.extend(patterns)
            except Exception as e:
                logger.error(f"Pattern matcher error: {e}")

        # Filter by confidence and cooldown
        filtered = []
        now = datetime.utcnow()  # noqa: F841

        for pattern in all_patterns:
            if pattern.confidence < 0.5:
                continue

            cooldown_key = f"{pattern.pattern_id}:{pattern.pattern_type}"
            if cooldown_key in self._recently_triggered:
                continue

            filtered.append(pattern)

        return filtered

    async def _trigger_pattern(self, pattern: DetectedPattern) -> None:
        """Trigger context injection for detected pattern."""
        # Compute the cooldown key up front so it is registered even if the
        # injection raises. Otherwise a failing injector would never record a
        # cooldown and the same pattern would re-fire every detection cycle
        # (MECE G7: cooldown was previously added only after success).
        cooldown_key = f"{pattern.pattern_id}:{pattern.pattern_type}"
        try:
            event = TriggerEvent.from_activity_pattern(
                pattern=pattern.pattern_type,
                confidence=pattern.confidence,
            )

            # Override context query with pattern's query
            event.context_query = pattern.context_query
            event.priority = pattern.priority
            event.metadata["pattern_id"] = pattern.pattern_id
            event.metadata["evidence"] = pattern.evidence

            context = await self.injector.handle_trigger(event)

            if context:
                logger.info(
                    f"Pattern triggered injection: {pattern.pattern_id}, "
                    f"confidence={pattern.confidence:.2f}, "
                    f"{len(context.chunks)} chunks"
                )

        except Exception as e:
            logger.error(f"Failed to trigger pattern injection: {e}")

        finally:
            # Record the cooldown whether or not injection succeeded, so a
            # broken injector backs off for the cooldown window instead of
            # re-firing the pattern unbounded.
            self._recently_triggered.add(cooldown_key)
            asyncio.create_task(self._remove_cooldown(cooldown_key))

    async def _remove_cooldown(self, key: str) -> None:
        """Remove a pattern from cooldown after delay."""
        await asyncio.sleep(self._trigger_cooldown.total_seconds())
        self._recently_triggered.discard(key)

    async def start(self) -> None:
        """Start activity detection."""
        if self._running:
            logger.warning("ActivityDetector already running")
            return

        self._running = True
        self._detector_task = asyncio.create_task(self._detect_patterns())

        logger.info(f"ActivityDetector started, checking every {self.check_interval}s")

    async def stop(self) -> None:
        """Stop activity detection."""
        self._running = False

        if self._detector_task:
            self._detector_task.cancel()
            try:
                await self._detector_task
            except asyncio.CancelledError:
                pass
            self._detector_task = None

        logger.info("ActivityDetector stopped")

    def add_matcher(self, matcher: PatternMatcher) -> None:
        """Add a custom pattern matcher.

        Args:
            matcher: PatternMatcher to add
        """
        self._matchers.append(matcher)
        logger.info(f"Added pattern matcher: {type(matcher).__name__}")

    def get_recent_activities(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activity history.

        Args:
            limit: Maximum activities to return

        Returns:
            List of recent activities
        """
        recent = self._activities[-limit:]
        return [
            {
                "type": a.activity_type.value,
                "timestamp": a.timestamp.isoformat(),
                "project": a.project,
                "file_path": a.file_path,
                "data": a.data,
            }
            for a in reversed(recent)
        ]

    def get_detected_patterns(self) -> List[Dict[str, Any]]:
        """Get currently detected patterns.

        Returns:
            List of detected patterns
        """
        patterns = self._run_pattern_detection()
        return [
            {
                "pattern_id": p.pattern_id,
                "pattern_type": p.pattern_type,
                "confidence": p.confidence,
                "evidence": p.evidence,
                "context_query": p.context_query,
                "priority": p.priority.value,
            }
            for p in patterns
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics.

        Returns:
            Dict with detector stats
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=self.window_minutes)
        recent = [a for a in self._activities if a.timestamp >= cutoff]

        # Activity type distribution
        type_counts: Dict[str, int] = defaultdict(int)
        for activity in recent:
            type_counts[activity.activity_type.value] += 1

        # Project distribution
        project_counts: Dict[str, int] = defaultdict(int)
        for activity in recent:
            if activity.project:
                project_counts[activity.project] += 1

        return {
            "running": self._running,
            "total_activities": len(self._activities),
            "recent_activities": len(recent),
            "window_minutes": self.window_minutes,
            "activity_distribution": dict(type_counts),
            "project_distribution": dict(project_counts),
            "patterns_in_cooldown": len(self._recently_triggered),
            "matcher_count": len(self._matchers),
        }

    def clear_history(self) -> None:
        """Clear activity history."""
        self._activities.clear()
        self._recently_triggered.clear()
        logger.info("Activity history cleared")
