"""Tests for Proactive Context Injector Service.

WHO: proactive-injector:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (RETRIEVE-001)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.proactive_context_injector import (
    ProactiveContextInjector,
    get_proactive_injector,
)
from src.integrations.proactive_schema import (
    TriggerType,
    ContextPriority,
    TriggerEvent,
    InjectionRule,
    InjectionStats,
)


# ========== FIXTURES ==========


@pytest.fixture
def mock_ontology_bridge():
    """Create mock OntologyBridge."""
    bridge = MagicMock()
    bridge.query = AsyncMock(return_value={
        "memory": [
            {"id": "chunk1", "text": "test content", "score": 0.8},
            {"id": "chunk2", "text": "more content", "score": 0.75},
        ],
        "projects": [
            {"id": "chunk3", "text": "project info", "score": 0.7},
        ],
    })
    return bridge


@pytest.fixture
def mock_nexus_processor():
    """Create mock NexusProcessor."""
    nexus = MagicMock()
    nexus.process = MagicMock(return_value={
        "core": [
            {"id": "rag1", "text": "RAG result", "score": 0.85},
        ],
    })
    return nexus


@pytest.fixture
def injector(mock_ontology_bridge, mock_nexus_processor):
    """Create ProactiveContextInjector instance."""
    return ProactiveContextInjector(
        ontology_bridge=mock_ontology_bridge,
        nexus_processor=mock_nexus_processor,
    )


@pytest.fixture
def file_open_event():
    """Create a file open trigger event."""
    return TriggerEvent.from_file_open("/path/to/file.py", "test-project")


@pytest.fixture
def git_checkout_event():
    """Create a git checkout trigger event."""
    return TriggerEvent.from_git_checkout("feature-branch", "test-project")


# ========== INITIALIZATION TESTS ==========


def test_injector_initialization(mock_ontology_bridge):
    """Test ProactiveContextInjector initialization."""
    injector = ProactiveContextInjector(ontology_bridge=mock_ontology_bridge)

    assert injector.ontology_bridge == mock_ontology_bridge
    assert injector.nexus_processor is None
    assert len(injector.rules) > 0
    assert isinstance(injector.stats, InjectionStats)


def test_injector_with_custom_rules(mock_ontology_bridge):
    """Test ProactiveContextInjector with custom rules."""
    custom_rules = [
        InjectionRule(
            rule_id="custom-rule",
            trigger_types=[TriggerType.FILE_OPEN],
            min_relevance=0.9,
        ),
    ]

    injector = ProactiveContextInjector(
        ontology_bridge=mock_ontology_bridge,
        rules=custom_rules,
    )

    assert len(injector.rules) == 1
    assert "custom-rule" in injector.rules


# ========== TRIGGER HANDLING TESTS ==========


@pytest.mark.asyncio
async def test_handle_trigger_success(injector, file_open_event):
    """Test successful trigger handling."""
    context = await injector.handle_trigger(file_open_event)

    assert context is not None
    assert len(context.chunks) > 0
    assert context.relevance_score > 0
    assert context.token_count > 0
    assert len(context.source_ontologies) > 0


@pytest.mark.asyncio
async def test_handle_trigger_updates_stats(injector, file_open_event):
    """Test that trigger handling updates statistics."""
    initial_triggers = injector.stats.total_triggers

    await injector.handle_trigger(file_open_event)

    assert injector.stats.total_triggers == initial_triggers + 1


@pytest.mark.asyncio
async def test_handle_trigger_dry_run(injector, file_open_event):
    """Test dry run mode doesn't inject context."""
    context = await injector.handle_trigger(file_open_event, dry_run=True)

    assert context is not None
    # Should still return context but not add to history
    assert len(injector._injection_history) == 0


@pytest.mark.asyncio
async def test_handle_trigger_no_matching_rules(mock_ontology_bridge):
    """Test trigger with no matching rules returns None."""
    # Create injector with rule that doesn't match FILE_OPEN
    custom_rules = [
        InjectionRule(
            rule_id="git-only",
            trigger_types=[TriggerType.GIT_CHECKOUT],
        ),
    ]

    injector = ProactiveContextInjector(
        ontology_bridge=mock_ontology_bridge,
        rules=custom_rules,
    )

    event = TriggerEvent.from_file_open("/test.py")
    context = await injector.handle_trigger(event)

    assert context is None


@pytest.mark.asyncio
async def test_handle_trigger_cooldown(injector, file_open_event):
    """Test cooldown prevents rapid re-injection."""
    # First trigger should succeed
    context1 = await injector.handle_trigger(file_open_event)
    assert context1 is not None

    # Immediate second trigger should be blocked by cooldown
    context2 = await injector.handle_trigger(file_open_event)
    assert context2 is None


@pytest.mark.asyncio
async def test_handle_trigger_low_relevance(mock_ontology_bridge):
    """Test low relevance context is filtered out."""
    # Return low relevance chunks
    mock_ontology_bridge.query = AsyncMock(return_value={
        "memory": [
            {"id": "chunk1", "text": "low rel", "score": 0.2},
        ],
    })

    injector = ProactiveContextInjector(ontology_bridge=mock_ontology_bridge)

    event = TriggerEvent.from_file_open("/test.py")
    context = await injector.handle_trigger(event)

    # Should be None because relevance below threshold
    assert context is None


# ========== CONTEXT RETRIEVAL TESTS ==========


@pytest.mark.asyncio
async def test_query_ontology(injector, file_open_event):
    """Test ontology querying."""
    results = await injector._query_ontology(file_open_event, "execution", 10)

    assert "memory" in results or len(results) > 0
    injector.ontology_bridge.query.assert_called_once()


@pytest.mark.asyncio
async def test_query_nexus(injector, file_open_event):
    """Test nexus processor querying."""
    results = await injector._query_nexus(file_open_event, "execution", 2000)

    assert results is not None
    injector.nexus_processor.process.assert_called_once()


# ========== RULE MANAGEMENT TESTS ==========


def test_find_matching_rules(injector):
    """Test finding rules that match a trigger."""
    event = TriggerEvent.from_file_open("/test.py")
    rules = injector._find_matching_rules(event)

    assert len(rules) >= 1
    for rule in rules:
        assert TriggerType.FILE_OPEN in rule.trigger_types


def test_add_rule(injector):
    """Test adding a new rule."""
    new_rule = InjectionRule(
        rule_id="new-rule",
        trigger_types=[TriggerType.PROJECT_SWITCH],
    )

    injector.add_rule(new_rule)

    assert "new-rule" in injector.rules


def test_remove_rule(injector):
    """Test removing a rule."""
    # Add a rule first
    rule = InjectionRule(
        rule_id="to-remove",
        trigger_types=[TriggerType.FILE_OPEN],
    )
    injector.add_rule(rule)

    # Remove it
    result = injector.remove_rule("to-remove")

    assert result is True
    assert "to-remove" not in injector.rules


def test_remove_nonexistent_rule(injector):
    """Test removing a rule that doesn't exist."""
    result = injector.remove_rule("nonexistent")
    assert result is False


def test_enable_rule(injector):
    """Test enabling a rule."""
    # Disable first
    rule_id = list(injector.rules.keys())[0]
    injector.rules[rule_id].enabled = False

    result = injector.enable_rule(rule_id)

    assert result is True
    assert injector.rules[rule_id].enabled is True


def test_disable_rule(injector):
    """Test disabling a rule."""
    rule_id = list(injector.rules.keys())[0]

    result = injector.disable_rule(rule_id)

    assert result is True
    assert injector.rules[rule_id].enabled is False


def test_list_rules(injector):
    """Test listing all rules."""
    rules = injector.list_rules()

    assert len(rules) > 0
    for rule in rules:
        assert isinstance(rule, InjectionRule)


# ========== HISTORY AND STATS TESTS ==========


@pytest.mark.asyncio
async def test_injection_history(injector, file_open_event):
    """Test injection history tracking."""
    await injector.handle_trigger(file_open_event)

    history = injector.get_injection_history(limit=10)

    assert len(history) >= 1


@pytest.mark.asyncio
async def test_injection_history_filter_by_type(injector, file_open_event, git_checkout_event):
    """Test filtering injection history by trigger type."""
    # Clear cooldown by modifying last injection time
    injector._last_injection_by_type.clear()

    await injector.handle_trigger(file_open_event)

    history = injector.get_injection_history(
        limit=10,
        trigger_type=TriggerType.FILE_OPEN,
    )

    for ctx in history:
        assert ctx.trigger_event.trigger_type == TriggerType.FILE_OPEN


def test_mark_context_used(injector):
    """Test marking injected context as used."""
    # Manually add to history
    from src.integrations.proactive_schema import InjectedContext

    event = TriggerEvent.from_file_open("/test.py")
    ctx = InjectedContext(
        trigger_event=event,
        injected_at=datetime.utcnow(),
        chunks=[],
        relevance_score=0.8,
        token_count=100,
        source_ontologies=["memory"],
    )
    injector._injection_history.append(ctx)

    injector.mark_context_used(0)

    assert injector._injection_history[0].was_used is True
    assert injector.stats.used_count == 1


def test_get_stats(injector):
    """Test getting injection statistics."""
    stats = injector.get_stats()

    assert isinstance(stats, InjectionStats)
    assert hasattr(stats, "total_triggers")
    assert hasattr(stats, "total_injections")


# ========== HELPER METHOD TESTS ==========


def test_deduplicate_chunks(injector):
    """Test chunk deduplication."""
    chunks = [
        {"id": "chunk1", "text": "test"},
        {"id": "chunk1", "text": "test"},  # Duplicate
        {"id": "chunk2", "text": "other"},
    ]

    result = injector._deduplicate_chunks(chunks)

    assert len(result) == 2


def test_calculate_relevance(injector):
    """Test relevance calculation."""
    event = TriggerEvent.from_file_open("/test.py")
    chunks = [
        {"id": "chunk1", "score": 0.8},
        {"id": "chunk2", "score": 0.6},
    ]

    relevance = injector._calculate_relevance(chunks, event)

    assert relevance == pytest.approx(0.7, rel=1e-2)


def test_calculate_relevance_empty(injector):
    """Test relevance calculation with no chunks."""
    event = TriggerEvent.from_file_open("/test.py")
    relevance = injector._calculate_relevance([], event)

    assert relevance == 0.0


def test_estimate_tokens(injector):
    """Test token estimation."""
    chunks = [
        {"text": "This is some test content"},  # ~25 chars = ~6 tokens
        {"content": "More content here"},  # ~17 chars = ~4 tokens
    ]

    tokens = injector._estimate_tokens(chunks)

    assert tokens > 0
    assert tokens < 100  # Should be reasonable estimate


def test_truncate_to_tokens(injector):
    """Test token truncation."""
    chunks = [
        {"text": "a" * 100, "id": "1"},
        {"text": "b" * 100, "id": "2"},
        {"text": "c" * 100, "id": "3"},
    ]

    # Truncate to 50 tokens (~200 chars)
    result = injector._truncate_to_tokens(chunks, 50)

    assert len(result) <= 3
    assert injector._estimate_tokens(result) <= 50


# ========== COOLDOWN TESTS ==========


def test_is_in_cooldown_no_previous(injector):
    """Test cooldown with no previous injection."""
    event = TriggerEvent.from_file_open("/test.py")
    rules = [InjectionRule(rule_id="test", trigger_types=[TriggerType.FILE_OPEN])]

    result = injector._is_in_cooldown(event, rules)

    assert result is False


def test_is_in_cooldown_after_injection(injector):
    """Test cooldown after recent injection."""
    event = TriggerEvent.from_file_open("/test.py")

    # Simulate recent injection
    injector._last_injection_by_type[TriggerType.FILE_OPEN] = datetime.utcnow()

    rules = [InjectionRule(
        rule_id="test",
        trigger_types=[TriggerType.FILE_OPEN],
        cooldown_seconds=300,
    )]

    result = injector._is_in_cooldown(event, rules)

    assert result is True


def test_is_in_cooldown_expired(injector):
    """Test cooldown after it has expired."""
    event = TriggerEvent.from_file_open("/test.py")

    # Simulate old injection (10 minutes ago)
    injector._last_injection_by_type[TriggerType.FILE_OPEN] = (
        datetime.utcnow() - timedelta(minutes=10)
    )

    rules = [InjectionRule(
        rule_id="test",
        trigger_types=[TriggerType.FILE_OPEN],
        cooldown_seconds=60,  # 1 minute cooldown
    )]

    result = injector._is_in_cooldown(event, rules)

    assert result is False
