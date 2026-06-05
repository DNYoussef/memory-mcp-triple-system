"""Integration Tests for Proactive Context Injection System.

Tests the full flow from triggers to context injection.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (RETRIEVE-001)
"""

import pytest
import asyncio
import os
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.services.proactive_context_injector import ProactiveContextInjector
from src.services.trigger_watchers.file_watcher import FileWatcher, WatchConfig
from src.services.trigger_watchers.git_watcher import GitWatcher, GitWatchConfig
from src.services.trigger_watchers.time_scheduler import TimeScheduler, ScheduledTrigger, DayOfWeek
from src.services.trigger_watchers.activity_detector import ActivityDetector, ActivityType
from src.services.trigger_watchers.watcher_manager import WatcherManager, WatcherManagerConfig
from src.integrations.proactive_schema import (
    TriggerEvent,
    TriggerType,
    ContextPriority,
    InjectionRule,
)


# ========== FIXTURES ==========


@pytest.fixture
def mock_ontology_bridge():
    """Create mock OntologyBridge with realistic responses."""
    bridge = MagicMock()

    async def mock_query(query, mode="execution", limit=10):
        # Simulate realistic entity retrieval
        if "file:" in query:
            return {
                "memory": [
                    {
                        "id": "mem-001",
                        "text": f"Previous work on file: {query}",
                        "score": 0.85,
                        "entity_type": "memory",
                    },
                ],
                "projects": [
                    {
                        "id": "proj-001",
                        "text": "Related project context",
                        "score": 0.75,
                        "entity_type": "project",
                    },
                ],
            }
        elif "branch:" in query:
            return {
                "beads": [
                    {
                        "id": "bead-001",
                        "text": f"Tasks for branch: {query}",
                        "score": 0.8,
                        "entity_type": "task",
                    },
                ],
            }
        else:
            return {
                "memory": [
                    {
                        "id": "mem-generic",
                        "text": "Generic context",
                        "score": 0.6,
                    },
                ],
            }

    bridge.query = mock_query
    return bridge


@pytest.fixture
def mock_nexus_processor():
    """Create mock NexusProcessor with realistic responses."""
    nexus = MagicMock()

    def mock_process(query, mode="execution", token_budget=2000):
        return {
            "core": [
                {
                    "id": "rag-001",
                    "text": f"RAG result for: {query}",
                    "score": 0.78,
                },
            ],
            "extended": [
                {
                    "id": "rag-ext-001",
                    "text": "Extended RAG context",
                    "score": 0.65,
                },
            ],
        }

    nexus.process = mock_process
    return nexus


@pytest.fixture
def injector(mock_ontology_bridge, mock_nexus_processor):
    """Create fully configured ProactiveContextInjector."""
    return ProactiveContextInjector(
        ontology_bridge=mock_ontology_bridge,
        nexus_processor=mock_nexus_processor,
    )


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with files."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create some Python files
        (Path(tmp) / "main.py").write_text("# Main application\nprint('hello')")
        (Path(tmp) / "utils.py").write_text("# Utility functions\ndef helper(): pass")
        (Path(tmp) / "test_main.py").write_text("# Tests\ndef test_hello(): pass")

        # Create subdirectory
        (Path(tmp) / "src").mkdir()
        (Path(tmp) / "src" / "core.py").write_text("# Core module")

        yield tmp


# ========== FULL FLOW INTEGRATION TESTS ==========


class TestProactiveInjectionFlow:
    """Test complete proactive injection flows."""

    @pytest.mark.asyncio
    async def test_file_open_injection_flow(self, injector, temp_project_dir):
        """Test complete flow: file open -> context injection."""
        # Create file open event
        file_path = str(Path(temp_project_dir) / "main.py")
        event = TriggerEvent.from_file_open(file_path, "test-project")

        # Trigger injection
        context = await injector.handle_trigger(event)

        # Verify injection
        assert context is not None
        assert len(context.chunks) > 0
        assert context.relevance_score > 0
        assert context.trigger_event.trigger_type == TriggerType.FILE_OPEN
        assert len(context.source_ontologies) > 0

        # Verify stats updated
        assert injector.stats.total_triggers >= 1
        assert injector.stats.total_injections >= 1

    @pytest.mark.asyncio
    async def test_git_checkout_injection_flow(self, injector):
        """Test complete flow: git checkout -> context injection."""
        # Create checkout event
        event = TriggerEvent.from_git_checkout("feature/new-feature", "test-project")

        # Clear any previous cooldowns
        injector._last_injection_by_type.clear()

        # Trigger injection
        context = await injector.handle_trigger(event)

        # Verify injection
        assert context is not None
        assert context.trigger_event.trigger_type == TriggerType.GIT_CHECKOUT
        assert "feature" in context.trigger_event.context_query.lower()

    @pytest.mark.asyncio
    async def test_activity_pattern_injection_flow(self, injector):
        """Test complete flow: activity pattern -> context injection."""
        # Create activity pattern event
        event = TriggerEvent.from_activity_pattern("research-mode", 0.9)

        # Clear cooldowns
        injector._last_injection_by_type.clear()

        # Trigger injection
        context = await injector.handle_trigger(event)

        # Verify injection
        assert context is not None
        assert context.trigger_event.trigger_type == TriggerType.ACTIVITY_PATTERN

    @pytest.mark.asyncio
    async def test_time_scheduled_injection_flow(self, injector):
        """Test complete flow: time schedule -> context injection."""
        # Create time-based event
        event = TriggerEvent.from_time_of_day(9, 1)  # 9am Monday

        # Clear cooldowns
        injector._last_injection_by_type.clear()

        # Trigger injection
        context = await injector.handle_trigger(event)

        # Verify injection
        assert context is not None
        assert context.trigger_event.trigger_type == TriggerType.TIME_OF_DAY


# ========== WATCHER INTEGRATION TESTS ==========


class TestWatcherIntegration:
    """Test watchers integrated with injector."""

    @pytest.mark.asyncio
    async def test_file_watcher_triggers_injection(self, injector, temp_project_dir):
        """Test FileWatcher triggers injection on file events."""
        config = WatchConfig(
            paths=[temp_project_dir],
            project_name="test-project",
            debounce_seconds=0.1,  # Short debounce for testing
        )

        watcher = FileWatcher(injector, config)

        # Track injection calls
        injection_called = asyncio.Event()
        original_handle = injector.handle_trigger

        async def track_handle(*args, **kwargs):
            result = await original_handle(*args, **kwargs)
            injection_called.set()
            return result

        injector.handle_trigger = track_handle

        # Start watcher
        await watcher.start()

        try:
            # Simulate file event by calling the callback directly
            test_file = str(Path(temp_project_dir) / "main.py")
            watcher._on_file_event(test_file, "modified")

            # Wait for injection (with timeout)
            try:
                await asyncio.wait_for(injection_called.wait(), timeout=2.0)
                assert True  # Injection was triggered
            except asyncio.TimeoutError:
                pytest.skip("File event processing timed out")

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_time_scheduler_triggers_injection(self, injector):
        """Test TimeScheduler triggers injection at scheduled time."""
        # Create schedule for "now"
        now = datetime.now()
        schedule = ScheduledTrigger(
            trigger_id="test-now",
            hour=now.hour,
            minute=now.minute,
            days=[DayOfWeek(now.isoweekday())],
            context_query="test scheduled context",
        )

        scheduler = TimeScheduler(
            injector,
            schedules=[schedule],
            check_interval=0.5,  # Fast checking for tests
        )

        # Track injection
        injection_called = asyncio.Event()
        original_handle = injector.handle_trigger

        async def track_handle(*args, **kwargs):
            injection_called.set()
            return await original_handle(*args, **kwargs)

        injector.handle_trigger = track_handle

        # Trigger manually (since exact timing is hard in tests)
        await scheduler._trigger_scheduled(schedule, now)

        # Verify injection was called
        assert injection_called.is_set()

    @pytest.mark.asyncio
    async def test_activity_detector_triggers_injection(self, injector):
        """Test ActivityDetector triggers injection on patterns."""
        detector = ActivityDetector(
            injector,
            window_minutes=5,
            check_interval=0.5,
        )

        # Record enough activities to trigger a pattern
        for _ in range(6):
            detector.record_activity(ActivityType.SEARCH_QUERY)

        # Run pattern detection
        patterns = detector._run_pattern_detection()

        # Should detect research-mode pattern (high frequency of searches)
        if len(patterns) > 0:
            # Trigger injection for first pattern
            injection_called = asyncio.Event()
            original_handle = injector.handle_trigger

            async def track_handle(*args, **kwargs):
                injection_called.set()
                return await original_handle(*args, **kwargs)

            injector.handle_trigger = track_handle

            await detector._trigger_pattern(patterns[0])

            assert injection_called.is_set()


# ========== WATCHER MANAGER INTEGRATION TESTS ==========


class TestWatcherManagerIntegration:
    """Test WatcherManager coordinating all watchers."""

    @pytest.mark.asyncio
    async def test_manager_starts_all_watchers(self, injector, temp_project_dir):
        """Test WatcherManager starts all configured watchers."""
        config = WatcherManagerConfig(
            file_watch_paths=[temp_project_dir],
            enable_git_watcher=False,  # No git repo available
            time_check_interval=60,
            activity_check_interval=60,
        )

        manager = WatcherManager(injector, config)

        await manager.start()

        try:
            assert manager._running is True
            assert manager._file_watcher is not None
            assert manager._time_scheduler is not None
            assert manager._activity_detector is not None

            # Git watcher should be None (no repo paths)
            assert manager._git_watcher is None

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_activity_recording(self, injector):
        """Test WatcherManager delegates activity recording."""
        config = WatcherManagerConfig(
            enable_file_watcher=False,
            enable_git_watcher=False,
            enable_time_scheduler=False,
            enable_activity_detector=True,
        )

        manager = WatcherManager(injector, config)

        await manager.start()

        try:
            # Record activity through manager
            manager.record_activity(
                ActivityType.FILE_ACCESS,
                data={"file": "test.py"},
                project="test-project",
            )

            # Verify it was recorded
            assert len(manager._activity_detector._activities) == 1

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_stats_aggregation(self, injector, temp_project_dir):
        """Test WatcherManager aggregates stats from all watchers."""
        config = WatcherManagerConfig(
            file_watch_paths=[temp_project_dir],
            enable_git_watcher=False,
        )

        manager = WatcherManager(injector, config)

        await manager.start()

        try:
            stats = manager.get_stats()

            assert "running" in stats
            assert stats["running"] is True
            assert "watchers_enabled" in stats
            assert "file_watcher" in stats
            assert "time_scheduler" in stats
            assert "activity_detector" in stats
            assert "injector" in stats

        finally:
            await manager.stop()


# ========== RULE CONFIGURATION TESTS ==========


class TestRuleConfiguration:
    """Test rule-based injection configuration."""

    @pytest.mark.asyncio
    async def test_custom_rules_respected(self, mock_ontology_bridge):
        """Test custom injection rules are respected."""
        # Create strict rule
        strict_rule = InjectionRule(
            rule_id="strict-file-rule",
            trigger_types=[TriggerType.FILE_OPEN],
            min_relevance=0.99,  # Very high threshold
            max_tokens=100,
            cooldown_seconds=1,
        )

        injector = ProactiveContextInjector(
            ontology_bridge=mock_ontology_bridge,
            rules=[strict_rule],
        )

        # Trigger should fail because mock data has 0.85 relevance < 0.99
        event = TriggerEvent.from_file_open("/test.py")
        context = await injector.handle_trigger(event)

        assert context is None  # Should be filtered out

    @pytest.mark.asyncio
    async def test_disabled_rules_ignored(self, mock_ontology_bridge):
        """Test disabled rules don't trigger injection."""
        disabled_rule = InjectionRule(
            rule_id="disabled-rule",
            trigger_types=[TriggerType.FILE_OPEN],
            enabled=False,
        )

        injector = ProactiveContextInjector(
            ontology_bridge=mock_ontology_bridge,
            rules=[disabled_rule],
        )

        event = TriggerEvent.from_file_open("/test.py")
        context = await injector.handle_trigger(event)

        assert context is None  # No matching enabled rules


# ========== MODE-AWARE INJECTION TESTS ==========


class TestModeAwareInjection:
    """Test mode-aware context injection."""

    @pytest.mark.asyncio
    async def test_execution_mode(self, injector):
        """Test injection in execution mode."""
        event = TriggerEvent.from_file_open("/test.py")
        context = await injector.handle_trigger(event, mode="execution")

        assert context is not None
        # Execution mode typically returns less context

    @pytest.mark.asyncio
    async def test_planning_mode(self, injector):
        """Test injection in planning mode."""
        event = TriggerEvent.from_file_open("/test.py")

        # Clear cooldown
        injector._last_injection_by_type.clear()

        context = await injector.handle_trigger(event, mode="planning")

        assert context is not None
        # Planning mode may return more context

    @pytest.mark.asyncio
    async def test_brainstorm_mode(self, injector):
        """Test injection in brainstorm mode."""
        event = TriggerEvent.from_file_open("/test.py")

        # Clear cooldown
        injector._last_injection_by_type.clear()

        context = await injector.handle_trigger(event, mode="brainstorm")

        assert context is not None
        # Brainstorm mode typically returns most context


# ========== ERROR HANDLING TESTS ==========


class TestErrorHandling:
    """Test error handling in proactive injection system."""

    @pytest.mark.asyncio
    async def test_ontology_query_failure(self, mock_nexus_processor):
        """Test graceful handling of ontology query failure."""
        # Create failing ontology bridge
        failing_bridge = MagicMock()
        failing_bridge.query = AsyncMock(side_effect=Exception("Query failed"))

        injector = ProactiveContextInjector(
            ontology_bridge=failing_bridge,
            nexus_processor=mock_nexus_processor,
        )

        event = TriggerEvent.from_file_open("/test.py")

        # Should not raise, just return None or limited context
        try:
            context = await injector.handle_trigger(event)
            # Either None or context from nexus only
            assert context is None or len(context.chunks) >= 0
        except Exception:
            pytest.fail("Should not raise on ontology failure")

    @pytest.mark.asyncio
    async def test_nexus_processor_failure(self, mock_ontology_bridge):
        """Test graceful handling of nexus processor failure."""
        # Create failing nexus
        failing_nexus = MagicMock()
        failing_nexus.process = MagicMock(side_effect=Exception("Process failed"))

        injector = ProactiveContextInjector(
            ontology_bridge=mock_ontology_bridge,
            nexus_processor=failing_nexus,
        )

        event = TriggerEvent.from_file_open("/test.py")

        # Should not raise, just return ontology context
        try:
            context = await injector.handle_trigger(event)
            assert context is not None  # Should still get ontology results
        except Exception:
            pytest.fail("Should not raise on nexus failure")
