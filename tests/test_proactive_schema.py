"""Tests for Proactive Context Injection Schema.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (RETRIEVE-001)
"""

import pytest
from datetime import datetime

from src.integrations.proactive_schema import (
    TriggerType,
    ContextPriority,
    TriggerEvent,
    InjectedContext,
    InjectionRule,
    InjectionStats,
    DEFAULT_RULES,
)


# ========== TRIGGER TYPE TESTS ==========


def test_trigger_type_values():
    """Test TriggerType enum values."""
    assert TriggerType.FILE_OPEN.value == "file-open"
    assert TriggerType.GIT_CHECKOUT.value == "git-checkout"
    assert TriggerType.TIME_OF_DAY.value == "time-of-day"
    assert TriggerType.ACTIVITY_PATTERN.value == "activity-pattern"
    assert TriggerType.PROJECT_SWITCH.value == "project-switch"
    assert TriggerType.BEADS_TASK_READY.value == "beads-task-ready"


def test_context_priority_values():
    """Test ContextPriority enum values."""
    assert ContextPriority.CRITICAL.value == "critical"
    assert ContextPriority.HIGH.value == "high"
    assert ContextPriority.MEDIUM.value == "medium"
    assert ContextPriority.LOW.value == "low"
    assert ContextPriority.BACKGROUND.value == "background"


# ========== TRIGGER EVENT TESTS ==========


def test_trigger_event_from_file_open():
    """Test TriggerEvent.from_file_open factory method."""
    event = TriggerEvent.from_file_open("/path/to/file.py", "my-project")

    assert event.trigger_type == TriggerType.FILE_OPEN
    assert event.source_data["file_path"] == "/path/to/file.py"
    assert event.source_data["project"] == "my-project"
    assert event.context_query == "file:/path/to/file.py"
    assert event.priority == ContextPriority.HIGH
    assert isinstance(event.detected_at, datetime)


def test_trigger_event_from_file_open_no_project():
    """Test TriggerEvent.from_file_open without project."""
    event = TriggerEvent.from_file_open("/path/to/file.py")

    assert event.source_data["project"] is None
    assert event.trigger_type == TriggerType.FILE_OPEN


def test_trigger_event_from_git_checkout():
    """Test TriggerEvent.from_git_checkout factory method."""
    event = TriggerEvent.from_git_checkout("feature-branch", "my-project")

    assert event.trigger_type == TriggerType.GIT_CHECKOUT
    assert event.source_data["branch"] == "feature-branch"
    assert event.source_data["project"] == "my-project"
    assert event.context_query == "branch:feature-branch project:my-project"
    assert event.priority == ContextPriority.HIGH


def test_trigger_event_from_time_of_day():
    """Test TriggerEvent.from_time_of_day factory method."""
    event = TriggerEvent.from_time_of_day(9, 1)  # 9am, Monday

    assert event.trigger_type == TriggerType.TIME_OF_DAY
    assert event.source_data["hour"] == 9
    assert event.source_data["day_of_week"] == 1
    assert event.priority == ContextPriority.MEDIUM


def test_trigger_event_from_activity_pattern():
    """Test TriggerEvent.from_activity_pattern factory method."""
    event = TriggerEvent.from_activity_pattern("research-mode", 0.85)

    assert event.trigger_type == TriggerType.ACTIVITY_PATTERN
    assert event.source_data["pattern"] == "research-mode"
    assert event.source_data["confidence"] == 0.85
    assert event.priority == ContextPriority.MEDIUM


def test_trigger_event_activity_pattern_low_confidence():
    """Test activity pattern with low confidence gets LOW priority."""
    event = TriggerEvent.from_activity_pattern("tentative", 0.5)

    assert event.priority == ContextPriority.LOW


# ========== INJECTED CONTEXT TESTS ==========


def test_injected_context_to_dict():
    """Test InjectedContext.to_dict serialization."""
    event = TriggerEvent.from_file_open("/test.py")
    context = InjectedContext(
        trigger_event=event,
        injected_at=datetime(2026, 1, 15, 12, 0, 0),
        chunks=[{"id": "chunk1", "text": "test"}],
        relevance_score=0.85,
        token_count=100,
        source_ontologies=["memory", "projects"],
        was_used=True,
        user_feedback="helpful",
    )

    result = context.to_dict()

    assert result["trigger_type"] == "file-open"
    assert result["chunk_count"] == 1
    assert result["relevance_score"] == 0.85
    assert result["token_count"] == 100
    assert result["source_ontologies"] == ["memory", "projects"]
    assert result["was_used"] is True
    assert result["user_feedback"] == "helpful"


def test_injected_context_defaults():
    """Test InjectedContext default values."""
    event = TriggerEvent.from_file_open("/test.py")
    context = InjectedContext(
        trigger_event=event,
        injected_at=datetime.utcnow(),
        chunks=[],
        relevance_score=0.5,
        token_count=0,
        source_ontologies=[],
    )

    assert context.was_used is False
    assert context.user_feedback is None


# ========== INJECTION RULE TESTS ==========


def test_injection_rule_defaults():
    """Test InjectionRule default values."""
    rule = InjectionRule(
        rule_id="test-rule",
        trigger_types=[TriggerType.FILE_OPEN],
    )

    assert rule.enabled is True
    assert rule.min_relevance == 0.5
    assert rule.max_tokens == 2000
    assert rule.cooldown_seconds == 300
    assert rule.require_ontologies is None


def test_injection_rule_custom_values():
    """Test InjectionRule with custom values."""
    rule = InjectionRule(
        rule_id="strict-rule",
        trigger_types=[TriggerType.FILE_OPEN, TriggerType.GIT_CHECKOUT],
        enabled=True,
        min_relevance=0.8,
        max_tokens=1000,
        cooldown_seconds=600,
        require_ontologies=["memory", "projects"],
    )

    assert rule.min_relevance == 0.8
    assert rule.max_tokens == 1000
    assert rule.cooldown_seconds == 600
    assert rule.require_ontologies == ["memory", "projects"]


# ========== INJECTION STATS TESTS ==========


def test_injection_stats_defaults():
    """Test InjectionStats default values."""
    stats = InjectionStats()

    assert stats.total_triggers == 0
    assert stats.total_injections == 0
    assert stats.by_trigger_type == {}
    assert stats.by_priority == {}
    assert stats.average_relevance == 0.0
    assert stats.total_tokens_injected == 0
    assert stats.used_count == 0
    assert stats.unused_count == 0


def test_injection_stats_injection_rate():
    """Test injection rate calculation."""
    stats = InjectionStats()

    # Zero triggers
    assert stats.injection_rate() == 0.0

    # Some triggers and injections
    stats.total_triggers = 10
    stats.total_injections = 7

    assert stats.injection_rate() == 0.7


def test_injection_stats_usage_rate():
    """Test usage rate calculation."""
    stats = InjectionStats()

    # Zero injections
    assert stats.usage_rate() == 0.0

    # Some injections and usage
    stats.total_injections = 10
    stats.used_count = 8

    assert stats.usage_rate() == 0.8


def test_injection_stats_to_dict():
    """Test InjectionStats.to_dict serialization."""
    stats = InjectionStats()
    stats.total_triggers = 100
    stats.total_injections = 75
    stats.by_trigger_type = {"file-open": 50, "git-checkout": 25}
    stats.by_priority = {"high": 60, "medium": 15}
    stats.average_relevance = 0.72
    stats.total_tokens_injected = 50000
    stats.used_count = 50
    stats.unused_count = 25

    result = stats.to_dict()

    assert result["total_triggers"] == 100
    assert result["total_injections"] == 75
    assert result["injection_rate"] == 0.75
    assert result["usage_rate"] == pytest.approx(50 / 75, rel=1e-2)


# ========== DEFAULT RULES TESTS ==========


def test_default_rules_exist():
    """Test that DEFAULT_RULES are defined."""
    assert len(DEFAULT_RULES) >= 4


def test_default_rules_have_file_open():
    """Test file-open rule exists in defaults."""
    file_rules = [r for r in DEFAULT_RULES if TriggerType.FILE_OPEN in r.trigger_types]
    assert len(file_rules) >= 1


def test_default_rules_have_git_checkout():
    """Test git-checkout rule exists in defaults."""
    git_rules = [
        r for r in DEFAULT_RULES if TriggerType.GIT_CHECKOUT in r.trigger_types
    ]
    assert len(git_rules) >= 1


def test_default_rules_have_valid_configs():
    """Test default rules have valid configurations."""
    for rule in DEFAULT_RULES:
        assert rule.rule_id
        assert len(rule.trigger_types) > 0
        assert 0 <= rule.min_relevance <= 1
        assert rule.max_tokens > 0
        assert rule.cooldown_seconds >= 0
