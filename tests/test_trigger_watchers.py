"""Tests for Trigger Watchers.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (RETRIEVE-001)
"""

import pytest
import asyncio
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.services.trigger_watchers.file_watcher import FileWatcher, WatchConfig
from src.services.trigger_watchers.git_watcher import GitWatcher, GitWatchConfig, GitRepoState
from src.services.trigger_watchers.time_scheduler import (
    TimeScheduler,
    ScheduledTrigger,
    TimePattern,
    DayOfWeek,
)
from src.services.trigger_watchers.activity_detector import (
    ActivityDetector,
    ActivityType,
    ActivityEvent,
    DetectedPattern,
    SequentialPatternMatcher,
    FrequencyPatternMatcher,
    ProjectFocusPatternMatcher,
)
from src.services.trigger_watchers.watcher_manager import (
    WatcherManager,
    WatcherManagerConfig,
)
from src.integrations.proactive_schema import ContextPriority


# ========== FIXTURES ==========


@pytest.fixture
def mock_injector():
    """Create mock ProactiveContextInjector."""
    injector = MagicMock()
    injector.handle_trigger = AsyncMock(return_value=MagicMock(
        chunks=[{"id": "1", "text": "test"}],
        relevance_score=0.8,
        token_count=100,
    ))
    injector.get_stats = MagicMock(return_value=MagicMock(to_dict=lambda: {}))
    return injector


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


# ========== FILE WATCHER TESTS ==========


class TestFileWatcher:
    """Tests for FileWatcher."""

    def test_watch_config_defaults(self):
        """Test WatchConfig default values."""
        config = WatchConfig()

        assert len(config.extensions) > 0
        assert ".py" in config.extensions
        assert ".js" in config.extensions
        assert len(config.ignore_patterns) > 0

    def test_watch_config_custom(self):
        """Test WatchConfig with custom values."""
        config = WatchConfig(
            paths=["/test/path"],
            extensions={".custom"},
            ignore_patterns=["custom_ignore"],
        )

        assert config.paths == ["/test/path"]
        assert config.extensions == {".custom"}
        assert "custom_ignore" in config.ignore_patterns

    def test_file_watcher_initialization(self, mock_injector):
        """Test FileWatcher initialization."""
        config = WatchConfig(paths=["/test"])
        watcher = FileWatcher(mock_injector, config)

        assert watcher.injector == mock_injector
        assert watcher.config.paths == ["/test"]

    @pytest.mark.asyncio
    async def test_file_watcher_start_stop(self, mock_injector, temp_dir):
        """Test FileWatcher start and stop."""
        config = WatchConfig(paths=[temp_dir])
        watcher = FileWatcher(mock_injector, config)

        await watcher.start()
        assert watcher._running is True

        await watcher.stop()
        assert watcher._running is False

    def test_add_watch_path(self, mock_injector, temp_dir):
        """Test adding a watch path."""
        watcher = FileWatcher(mock_injector)

        result = watcher.add_watch_path(temp_dir)

        assert result is True
        assert temp_dir in watcher.config.paths

    def test_add_nonexistent_path(self, mock_injector):
        """Test adding nonexistent path fails."""
        watcher = FileWatcher(mock_injector)

        result = watcher.add_watch_path("/nonexistent/path")

        assert result is False

    def test_get_stats(self, mock_injector, temp_dir):
        """Test getting watcher stats."""
        config = WatchConfig(paths=[temp_dir])
        watcher = FileWatcher(mock_injector, config)

        stats = watcher.get_stats()

        assert "running" in stats
        assert "watch_paths" in stats
        assert "extensions" in stats

    @pytest.mark.asyncio
    async def test_on_file_event_from_thread_reaches_queue(self, mock_injector):
        """G4: an event raised from a non-loop thread (like the watchdog thread)
        still reaches the event queue. Old code called asyncio.get_event_loop()
        in that thread, which raises on Py3.10+ and was silently dropped."""
        watcher = FileWatcher(mock_injector)
        watcher._loop = asyncio.get_running_loop()  # captured by start() in real use

        loop = asyncio.get_running_loop()
        # A thread-pool executor thread has no event loop, like the watchdog thread.
        await loop.run_in_executor(None, watcher._on_file_event, "/x/a.py", "modified")

        item = await asyncio.wait_for(watcher._event_queue.get(), timeout=1.0)
        assert item == ("/x/a.py", "modified")

    def test_add_watch_path_reuses_single_handler(self, mock_injector, temp_dir, monkeypatch):
        """G5: add_watch_path reuses the shared handler and does not re-schedule
        an already-watched path (no duplicate handler / double-fire)."""
        import src.services.trigger_watchers.file_watcher as fw
        monkeypatch.setattr(fw, "WATCHDOG_AVAILABLE", True)

        watcher = FileWatcher(mock_injector)
        watcher._running = True
        watcher._observer = MagicMock()
        shared = MagicMock()
        watcher._handler = shared

        assert watcher.add_watch_path(temp_dir) is True
        watcher._observer.schedule.assert_called_once_with(shared, temp_dir, recursive=True)

        # Re-adding the same path must not register another watch.
        watcher._observer.schedule.reset_mock()
        assert watcher.add_watch_path(temp_dir) is True
        watcher._observer.schedule.assert_not_called()


# ========== GIT WATCHER TESTS ==========


class TestGitWatcher:
    """Tests for GitWatcher."""

    def test_git_watch_config_defaults(self):
        """Test GitWatchConfig default values."""
        config = GitWatchConfig()

        assert config.poll_interval == 10.0
        assert config.track_checkout is True
        assert config.track_merge is True

    def test_git_watcher_initialization(self, mock_injector):
        """Test GitWatcher initialization."""
        config = GitWatchConfig(repo_paths=["/test/repo"])
        watcher = GitWatcher(mock_injector, config)

        assert watcher.injector == mock_injector
        assert watcher.config.repo_paths == ["/test/repo"]

    def test_git_repo_state(self):
        """Test GitRepoState dataclass."""
        state = GitRepoState(
            path="/test/repo",
            current_branch="main",
            current_commit="abc123",
        )

        assert state.path == "/test/repo"
        assert state.current_branch == "main"
        assert state.is_rebasing is False
        assert state.is_merging is False

    def test_get_project_name(self, mock_injector):
        """Test project name extraction from repo path."""
        watcher = GitWatcher(mock_injector)

        name = watcher._get_project_name("/path/to/my-project")

        assert name == "my-project"


# ========== TIME SCHEDULER TESTS ==========


class TestTimeScheduler:
    """Tests for TimeScheduler."""

    def test_scheduled_trigger_defaults(self):
        """Test ScheduledTrigger default values."""
        trigger = ScheduledTrigger(
            trigger_id="test",
            hour=9,
        )

        assert trigger.minute == 0
        assert trigger.enabled is True
        assert len(trigger.days) == 7  # All days

    def test_scheduled_trigger_matches_now(self):
        """Test ScheduledTrigger.matches_now."""
        now = datetime.now()
        trigger = ScheduledTrigger(
            trigger_id="test",
            hour=now.hour,
            minute=now.minute,
            days=[DayOfWeek(now.isoweekday())],
        )

        assert trigger.matches_now(now) is True

    def test_scheduled_trigger_no_match_wrong_hour(self):
        """Test trigger doesn't match with wrong hour."""
        now = datetime.now()
        trigger = ScheduledTrigger(
            trigger_id="test",
            hour=(now.hour + 1) % 24,
            minute=now.minute,
        )

        assert trigger.matches_now(now) is False

    def test_scheduled_trigger_no_match_disabled(self):
        """Test disabled trigger doesn't match."""
        now = datetime.now()
        trigger = ScheduledTrigger(
            trigger_id="test",
            hour=now.hour,
            minute=now.minute,
            enabled=False,
        )

        assert trigger.matches_now(now) is False

    def test_time_pattern_weekday_morning(self):
        """Test TimePattern.weekday_morning factory."""
        trigger = TimePattern.weekday_morning(9)

        assert trigger.hour == 9
        assert DayOfWeek.MONDAY in trigger.days
        assert DayOfWeek.SATURDAY not in trigger.days
        assert DayOfWeek.SUNDAY not in trigger.days

    def test_time_pattern_weekly_review(self):
        """Test TimePattern.weekly_review factory."""
        trigger = TimePattern.weekly_review(DayOfWeek.FRIDAY, 16)

        assert trigger.hour == 16
        assert trigger.days == [DayOfWeek.FRIDAY]
        assert trigger.priority == ContextPriority.HIGH

    def test_time_scheduler_initialization(self, mock_injector):
        """Test TimeScheduler initialization."""
        scheduler = TimeScheduler(mock_injector)

        assert scheduler.injector == mock_injector
        assert len(scheduler._schedules) > 0

    def test_add_schedule(self, mock_injector):
        """Test adding a schedule."""
        scheduler = TimeScheduler(mock_injector, schedules=[])

        schedule = ScheduledTrigger(
            trigger_id="custom",
            hour=10,
        )
        scheduler.add_schedule(schedule)

        assert "custom" in scheduler._schedules

    def test_remove_schedule(self, mock_injector):
        """Test removing a schedule."""
        scheduler = TimeScheduler(mock_injector)
        scheduler.add_schedule(ScheduledTrigger(trigger_id="to-remove", hour=10))

        result = scheduler.remove_schedule("to-remove")

        assert result is True
        assert "to-remove" not in scheduler._schedules

    def test_enable_disable_schedule(self, mock_injector):
        """Test enabling/disabling a schedule."""
        scheduler = TimeScheduler(mock_injector)
        trigger_id = list(scheduler._schedules.keys())[0]

        scheduler.disable_schedule(trigger_id)
        assert scheduler._schedules[trigger_id].enabled is False

        scheduler.enable_schedule(trigger_id)
        assert scheduler._schedules[trigger_id].enabled is True

    def test_list_schedules(self, mock_injector):
        """Test listing schedules."""
        scheduler = TimeScheduler(mock_injector)

        schedules = scheduler.list_schedules()

        assert len(schedules) > 0
        assert all(isinstance(s, ScheduledTrigger) for s in schedules)

    @pytest.mark.asyncio
    async def test_check_schedules_survives_failing_schedule(self, mock_injector):
        """G6: a schedule that raises in matches_now must not kill the loop -
        the scheduler keeps cycling instead of dying with _running stuck True."""
        bad = MagicMock()
        bad.trigger_id = "bad"
        bad.matches_now.side_effect = RuntimeError("bad schedule")

        scheduler = TimeScheduler(mock_injector, schedules=[bad], check_interval=0.01)
        scheduler._running = True
        task = asyncio.create_task(scheduler._check_schedules())

        await asyncio.sleep(0.05)  # allow several check cycles

        # Old code: the first raise killed the task. Fixed: it kept cycling.
        assert not task.done()
        assert bad.matches_now.call_count >= 2

        scheduler._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_check_schedules_bad_schedule_does_not_block_good(self, mock_injector):
        """G6 contract: a bad schedule earlier in the snapshot must NOT prevent a
        later good schedule from being evaluated each cycle (per-schedule guard)."""
        bad = MagicMock()
        bad.trigger_id = "bad"
        bad.matches_now.side_effect = RuntimeError("bad schedule")
        good = MagicMock()
        good.trigger_id = "good"
        good.matches_now.return_value = False  # evaluated, but does not trigger

        # bad is inserted first, so it is iterated before good.
        scheduler = TimeScheduler(mock_injector, schedules=[bad, good], check_interval=0.01)
        scheduler._running = True
        task = asyncio.create_task(scheduler._check_schedules())

        await asyncio.sleep(0.05)  # allow several check cycles

        # Both are evaluated every cycle - the bad one is skipped, not fatal.
        assert not task.done()
        assert bad.matches_now.call_count >= 2
        assert good.matches_now.call_count >= 2  # the good schedule after bad still runs

        scheduler._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ========== ACTIVITY DETECTOR TESTS ==========


class TestActivityDetector:
    """Tests for ActivityDetector."""

    def test_activity_type_values(self):
        """Test ActivityType enum values."""
        assert ActivityType.FILE_ACCESS.value == "file_access"
        assert ActivityType.SEARCH_QUERY.value == "search_query"
        assert ActivityType.ERROR_ENCOUNTERED.value == "error_encountered"

    def test_activity_event_creation(self):
        """Test ActivityEvent dataclass."""
        event = ActivityEvent(
            activity_type=ActivityType.FILE_ACCESS,
            timestamp=datetime.utcnow(),
            data={"file": "test.py"},
            project="test-project",
        )

        assert event.activity_type == ActivityType.FILE_ACCESS
        assert event.data["file"] == "test.py"

    def test_activity_detector_initialization(self, mock_injector):
        """Test ActivityDetector initialization."""
        detector = ActivityDetector(mock_injector)

        assert detector.injector == mock_injector
        assert len(detector._activities) == 0
        assert len(detector._matchers) > 0

    def test_record_activity(self, mock_injector):
        """Test recording an activity."""
        detector = ActivityDetector(mock_injector)

        detector.record_activity(
            ActivityType.FILE_ACCESS,
            data={"file": "test.py"},
            project="test-project",
        )

        assert len(detector._activities) == 1
        assert detector._activities[0].activity_type == ActivityType.FILE_ACCESS

    def test_record_activity_trims_history(self, mock_injector):
        """Test activity history is trimmed."""
        detector = ActivityDetector(mock_injector, max_history=10)

        # Record more than max_history
        for i in range(15):
            detector.record_activity(ActivityType.FILE_ACCESS)

        assert len(detector._activities) == 10

    def test_get_recent_activities(self, mock_injector):
        """Test getting recent activities."""
        detector = ActivityDetector(mock_injector)

        detector.record_activity(ActivityType.FILE_ACCESS)
        detector.record_activity(ActivityType.SEARCH_QUERY)

        activities = detector.get_recent_activities(limit=5)

        assert len(activities) == 2

    def test_clear_history(self, mock_injector):
        """Test clearing activity history."""
        detector = ActivityDetector(mock_injector)
        detector.record_activity(ActivityType.FILE_ACCESS)

        detector.clear_history()

        assert len(detector._activities) == 0

    @pytest.mark.asyncio
    async def test_trigger_pattern_records_cooldown_on_injector_failure(self, mock_injector):
        """MECE G7: a failing injection must still record a cooldown.

        Previously the cooldown was added only after a successful
        handle_trigger(); on injector failure the except swallowed the error
        and the pattern re-fired every detection cycle, unbounded.
        """
        mock_injector.handle_trigger = AsyncMock(side_effect=RuntimeError("boom"))
        detector = ActivityDetector(mock_injector)

        pattern = DetectedPattern(
            pattern_id="debugging-sequence",
            pattern_type="sequential",
            confidence=0.9,
            evidence=["error", "error"],
            context_query="debugging error fix",
            priority=ContextPriority.HIGH,
        )

        # Must not raise even though the injector blows up.
        await detector._trigger_pattern(pattern)

        cooldown_key = f"{pattern.pattern_id}:{pattern.pattern_type}"
        assert cooldown_key in detector._recently_triggered


# ========== PATTERN MATCHER TESTS ==========


class TestPatternMatchers:
    """Tests for pattern matching strategies."""

    def test_sequential_pattern_matcher(self):
        """Test SequentialPatternMatcher."""
        matcher = SequentialPatternMatcher()

        activities = [
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow()),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow()),
            # Repeat pattern
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow()),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow()),
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow()),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow()),
        ]

        patterns = matcher.match(activities, window_minutes=30)

        # Should detect deep-dive-sequence pattern
        assert len(patterns) >= 1

    def test_frequency_pattern_matcher(self):
        """Test FrequencyPatternMatcher."""
        matcher = FrequencyPatternMatcher(frequency_threshold=3)

        activities = [
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
            ActivityEvent(ActivityType.SEARCH_QUERY, datetime.utcnow()),
        ]

        patterns = matcher.match(activities, window_minutes=30)

        assert len(patterns) >= 1
        assert patterns[0].pattern_type == "frequency"

    def test_project_focus_matcher(self):
        """Test ProjectFocusPatternMatcher."""
        matcher = ProjectFocusPatternMatcher(focus_threshold=0.7)

        activities = [
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow(), project="project-a"),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow(), project="project-a"),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow(), project="project-a"),
            ActivityEvent(ActivityType.FILE_ACCESS, datetime.utcnow(), project="project-b"),
        ]

        patterns = matcher.match(activities, window_minutes=30)

        assert len(patterns) >= 1
        assert patterns[0].pattern_type == "project_focus"


# ========== WATCHER MANAGER TESTS ==========


class TestWatcherManager:
    """Tests for WatcherManager."""

    def test_watcher_manager_config_defaults(self):
        """Test WatcherManagerConfig default values."""
        config = WatcherManagerConfig()

        assert config.enable_file_watcher is True
        assert config.enable_git_watcher is True
        assert config.enable_time_scheduler is True
        assert config.enable_activity_detector is True

    def test_watcher_manager_initialization(self, mock_injector):
        """Test WatcherManager initialization."""
        config = WatcherManagerConfig(
            file_watch_paths=["/test"],
            git_repo_paths=["/repo"],
        )
        manager = WatcherManager(mock_injector, config)

        assert manager.injector == mock_injector
        assert manager.config == config

    @pytest.mark.asyncio
    async def test_watcher_manager_start_stop(self, mock_injector, temp_dir):
        """Test WatcherManager start and stop."""
        config = WatcherManagerConfig(
            file_watch_paths=[temp_dir],
            enable_git_watcher=False,  # No git repo
        )
        manager = WatcherManager(mock_injector, config)

        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False

    def test_record_activity_delegation(self, mock_injector):
        """Test activity recording delegation."""
        config = WatcherManagerConfig(
            enable_file_watcher=False,
            enable_git_watcher=False,
            enable_time_scheduler=False,
        )
        manager = WatcherManager(mock_injector, config)

        # Manually create activity detector
        manager._activity_detector = ActivityDetector(mock_injector)

        manager.record_activity(
            ActivityType.FILE_ACCESS,
            data={"file": "test.py"},
        )

        assert len(manager._activity_detector._activities) == 1

    def test_get_stats(self, mock_injector):
        """Test getting combined stats."""
        manager = WatcherManager(mock_injector)

        stats = manager.get_stats()

        assert "running" in stats
        assert "watchers_enabled" in stats
        assert "injector" in stats
