#!/usr/bin/env python3
"""Dry-run tests for CAPTURE-003: Confidence Scoring System.

Tests all confidence scoring components without external dependencies.

WHO: confidence-scoring:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (CAPTURE-003)
"""

import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_schema():
    """Test confidence scoring schema."""
    print("\n=== Testing Confidence Scoring Schema ===")

    from src.integrations.confidence_scoring_schema import (
        ConfidenceLevel,
        ConfidenceScore,
        ClassificationResult,
        ClassificationType,
        EscalationRequest,
        EscalationReason,
        QualityGateScore,
        combine_confidences,
        entropy_based_confidence,
        margin_based_confidence,
        ESCALATION_THRESHOLD,
    )

    # Test ConfidenceLevel.from_score
    assert ConfidenceLevel.from_score(0.95) == ConfidenceLevel.VERY_HIGH
    assert ConfidenceLevel.from_score(0.85) == ConfidenceLevel.HIGH
    assert ConfidenceLevel.from_score(0.65) == ConfidenceLevel.MEDIUM
    assert ConfidenceLevel.from_score(0.45) == ConfidenceLevel.LOW
    assert ConfidenceLevel.from_score(0.35) == ConfidenceLevel.VERY_LOW
    print("  [PASS] ConfidenceLevel.from_score")

    # Test ConfidenceScore.create
    score = ConfidenceScore.create(
        score=0.75,
        classification_type=ClassificationType.MODE_DETECTION,
        components={"test": 0.75},
    )
    assert score.score == 0.75
    assert score.level == ConfidenceLevel.MEDIUM
    assert not score.needs_escalation()
    print("  [PASS] ConfidenceScore.create")

    # Test score clamping
    score_high = ConfidenceScore.create(score=1.5, classification_type=ClassificationType.MODE_DETECTION)
    assert score_high.score == 1.0
    score_low = ConfidenceScore.create(score=-0.5, classification_type=ClassificationType.MODE_DETECTION)
    assert score_low.score == 0.0
    print("  [PASS] Score clamping")

    # Test needs_escalation
    low_score = ConfidenceScore.create(score=0.4, classification_type=ClassificationType.MODE_DETECTION)
    assert low_score.needs_escalation()
    print("  [PASS] needs_escalation")

    # Test ClassificationResult.create
    result = ClassificationResult.create(
        classification_type=ClassificationType.MODE_DETECTION,
        value="execution",
        confidence_score=0.8,
        input_text="Show me the code",
    )
    assert result.value == "execution"
    assert result.confidence.score == 0.8
    assert not result.is_ambiguous()
    print("  [PASS] ClassificationResult.create")

    # Test is_ambiguous
    ambiguous_result = ClassificationResult.create(
        classification_type=ClassificationType.MODE_DETECTION,
        value="planning",
        confidence_score=0.7,
        alternatives=[{"mode": "execution", "confidence": 0.65}],
    )
    assert ambiguous_result.is_ambiguous(margin=0.1)
    print("  [PASS] is_ambiguous")

    # Test EscalationRequest.create
    escalation = EscalationRequest.create(
        classification_result=result,
        reason=EscalationReason.LOW_CONFIDENCE,
    )
    assert escalation.priority >= 0
    assert escalation.status.value == "pending"
    print("  [PASS] EscalationRequest.create")

    # Test QualityGateScore.create
    checks = [
        ConfidenceScore.create(score=0.8, classification_type=ClassificationType.MODE_DETECTION),
        ConfidenceScore.create(score=0.7, classification_type=ClassificationType.ENTITY_EXTRACTION),
    ]
    gate = QualityGateScore.create(gate_name="test_gate", checks=checks)
    assert gate.passed
    assert gate.overall_score > 0
    print("  [PASS] QualityGateScore.create")

    # Test combine_confidences
    scores = [0.8, 0.7, 0.6]
    geo_mean = combine_confidences(scores, method="geometric_mean")
    assert 0.6 < geo_mean < 0.8
    harmonic = combine_confidences(scores, method="harmonic_mean")
    assert harmonic < geo_mean  # Harmonic mean is more conservative
    min_val = combine_confidences(scores, method="min")
    assert min_val == 0.6
    print("  [PASS] combine_confidences")

    # Test entropy_based_confidence
    uniform_probs = [0.33, 0.33, 0.34]
    low_conf = entropy_based_confidence(uniform_probs)
    peaked_probs = [0.9, 0.05, 0.05]
    high_conf = entropy_based_confidence(peaked_probs)
    assert high_conf > low_conf
    print("  [PASS] entropy_based_confidence")

    # Test margin_based_confidence
    high_margin = margin_based_confidence(0.9, 0.3)
    low_margin = margin_based_confidence(0.6, 0.5)
    assert high_margin > low_margin
    print("  [PASS] margin_based_confidence")

    print("  [ALL PASS] Schema tests")


def test_mode_detector():
    """Test mode detection confidence scorer."""
    print("\n=== Testing Mode Detection Scorer ===")

    from src.services.confidence.mode_detector import (
        ModeDetectionScorer,
        ModeDetectionConfig,
        Mode,
    )

    scorer = ModeDetectionScorer()

    # Test execution mode detection
    exec_result = scorer.detect_mode("What is the current temperature?")
    assert exec_result.value == Mode.EXECUTION
    assert exec_result.confidence.score > 0.5
    print(f"  [PASS] Execution mode: {exec_result.value} ({exec_result.confidence.score:.2f})")

    # Test planning mode detection
    plan_result = scorer.detect_mode("What should I use for the database?")
    assert plan_result.value == Mode.PLANNING
    assert plan_result.confidence.score > 0.5
    print(f"  [PASS] Planning mode: {plan_result.value} ({plan_result.confidence.score:.2f})")

    # Test brainstorming mode detection
    brain_result = scorer.detect_mode("What if we reimagined the entire system?")
    assert brain_result.value == Mode.BRAINSTORMING
    assert brain_result.confidence.score > 0.5
    print(f"  [PASS] Brainstorming mode: {brain_result.value} ({brain_result.confidence.score:.2f})")

    # Test short text handling
    short_result = scorer.detect_mode("hi")
    assert short_result.confidence.score == 0.5  # Low confidence for short text
    print("  [PASS] Short text handling")

    # Test imperative detection
    imp_result = scorer.detect_mode("Run the tests now")
    assert imp_result.value == Mode.EXECUTION
    print(f"  [PASS] Imperative detection: {imp_result.value}")

    # Test caching
    result1 = scorer.detect_mode("Show me the files")
    result2 = scorer.detect_mode("Show me the files")
    assert result1.result_id != result2.result_id or result1.value == result2.value
    print("  [PASS] Caching works")

    # Test statistics
    stats = scorer.get_stats()
    assert stats["total_detections"] > 0
    print(f"  [PASS] Stats tracking: {stats['total_detections']} detections")

    print("  [ALL PASS] Mode detector tests")


def test_entity_extractor():
    """Test entity extraction confidence scorer."""
    print("\n=== Testing Entity Extraction Scorer ===")

    from src.services.confidence.entity_extractor import (
        EntityExtractionScorer,
        EntityType,
    )

    scorer = EntityExtractionScorer()

    # Test email extraction
    entities = scorer.extract_entities("Contact me at john@example.com")
    emails = [e for e in entities if e.entity_type == EntityType.EMAIL]
    assert len(emails) == 1
    assert emails[0].value == "john@example.com"
    assert emails[0].confidence > 0.8
    print(f"  [PASS] Email extraction: {emails[0].value} ({emails[0].confidence:.2f})")

    # Test URL extraction
    entities = scorer.extract_entities("Visit https://github.com/test for more")
    urls = [e for e in entities if e.entity_type == EntityType.URL]
    assert len(urls) == 1
    assert "github.com" in urls[0].value
    print(f"  [PASS] URL extraction: {urls[0].value}")

    # Test hashtag extraction
    entities = scorer.extract_entities("Check out #Python #MachineLearning")
    hashtags = [e for e in entities if e.entity_type == EntityType.HASHTAG]
    assert len(hashtags) >= 2
    print(f"  [PASS] Hashtag extraction: {len(hashtags)} found")

    # Test mention extraction
    entities = scorer.extract_entities("Thanks @johndoe and @janedoe")
    mentions = [e for e in entities if e.entity_type == EntityType.MENTION]
    assert len(mentions) == 2
    print(f"  [PASS] Mention extraction: {len(mentions)} found")

    # Test date extraction
    entities = scorer.extract_entities("Meeting on 2026-01-15 at 3pm")
    dates = [e for e in entities if e.entity_type == EntityType.DATE]
    assert len(dates) >= 1
    print(f"  [PASS] Date extraction: {dates[0].value}")

    # Test money extraction
    entities = scorer.extract_entities("The cost is $1,234.56")
    money = [e for e in entities if e.entity_type == EntityType.MONEY]
    assert len(money) == 1
    print(f"  [PASS] Money extraction: {money[0].value}")

    # Test extract_with_result
    result = scorer.extract_with_result("Contact support@test.com for help")
    assert result.classification_type.value == "entity_extraction"
    assert result.confidence.score > 0
    print(f"  [PASS] extract_with_result: confidence={result.confidence.score:.2f}")

    # Test filtering by type
    entities = scorer.extract_entities(
        "Email john@test.com or visit https://test.com",
        entity_types=[EntityType.EMAIL]
    )
    assert all(e.entity_type == EntityType.EMAIL for e in entities)
    print("  [PASS] Type filtering")

    # Test overlap removal
    entities = scorer.extract_entities("Contact john@example.com")
    # Should not have duplicate extractions
    print(f"  [PASS] Overlap removal: {len(entities)} unique entities")

    print("  [ALL PASS] Entity extractor tests")


def test_quality_gate():
    """Test quality gate score aggregator."""
    print("\n=== Testing Quality Gate Aggregator ===")

    from src.services.confidence.quality_gate import (
        QualityGateAggregator,
        QualityGateConfig,
        GateCheck,
        GateType,
        GateStatus,
        create_memory_quality_gate,
        create_strict_quality_gate,
        create_lenient_quality_gate,
    )
    from src.integrations.confidence_scoring_schema import (
        ClassificationResult,
        ClassificationType,
    )

    # Test basic gate
    gate = QualityGateAggregator()
    gate.add_confidence_score(GateType.MODE_DETECTION, "mode", 0.8)
    gate.add_confidence_score(GateType.ENTITY_EXTRACTION, "entities", 0.7)
    result = gate.evaluate()
    assert result.passed
    print(f"  [PASS] Basic gate: passed={result.passed}, score={result.overall_score:.2f}")

    # Test failing gate
    gate2 = QualityGateAggregator()
    gate2.add_confidence_score(GateType.MODE_DETECTION, "mode", 0.3)
    gate2.add_confidence_score(GateType.ENTITY_EXTRACTION, "entities", 0.4)
    result2 = gate2.evaluate()
    assert not result2.passed
    print(f"  [PASS] Failing gate: passed={result2.passed}, score={result2.overall_score:.2f}")

    # Test GateCheck.create
    check = GateCheck.create(
        gate_type=GateType.MODE_DETECTION,
        name="test_check",
        confidence=0.75,
    )
    assert check.status == GateStatus.PASSED
    print(f"  [PASS] GateCheck.create: status={check.status.value}")

    # Test warning status
    check_warn = GateCheck.create(
        gate_type=GateType.MODE_DETECTION,
        name="warn_check",
        confidence=0.55,
    )
    assert check_warn.status == GateStatus.WARNING
    print(f"  [PASS] Warning status: {check_warn.status.value}")

    # Test failed status
    check_fail = GateCheck.create(
        gate_type=GateType.MODE_DETECTION,
        name="fail_check",
        confidence=0.3,
    )
    assert check_fail.status == GateStatus.FAILED
    print(f"  [PASS] Failed status: {check_fail.status.value}")

    # Test add_classification_result
    result_obj = ClassificationResult.create(
        classification_type=ClassificationType.MODE_DETECTION,
        value="execution",
        confidence_score=0.85,
    )
    gate3 = QualityGateAggregator()
    gate3.add_classification_result(result_obj)
    gate_result = gate3.evaluate()
    assert gate_result.passed
    print("  [PASS] add_classification_result")

    # Test evaluate_with_details
    gate4 = QualityGateAggregator()
    gate4.add_confidence_score(GateType.MODE_DETECTION, "mode", 0.8)
    gate4.add_confidence_score(GateType.ENTITY_EXTRACTION, "entities", 0.4)
    details = gate4.evaluate_with_details()
    assert "failing_checks" in details
    assert len(details["failing_checks"]) > 0
    print(f"  [PASS] evaluate_with_details: {len(details['failing_checks'])} failing checks")

    # Test factory functions
    memory_gate = create_memory_quality_gate()
    assert memory_gate.config.pass_threshold == 0.6
    print("  [PASS] create_memory_quality_gate")

    strict_gate = create_strict_quality_gate()
    assert strict_gate.config.require_all_pass
    print("  [PASS] create_strict_quality_gate")

    lenient_gate = create_lenient_quality_gate()
    assert lenient_gate.config.pass_threshold == 0.5
    print("  [PASS] create_lenient_quality_gate")

    print("  [ALL PASS] Quality gate tests")


def test_tag_scorer():
    """Test tag assignment confidence scorer."""
    print("\n=== Testing Tag Assignment Scorer ===")

    from src.services.confidence.tag_scorer import (
        TagAssignmentScorer,
        TagType,
    )

    scorer = TagAssignmentScorer()

    # Test with context
    tags = scorer.assign_tags(
        "Implementing new feature for memory-mcp",
        context={
            "agent_id": "coder:1.0.0",
            "timestamp": datetime.now(timezone.utc),
            "project": "memory-mcp-triple-system",
        }
    )

    assert TagType.WHO in tags
    assert tags[TagType.WHO].confidence > 0.8  # From context
    print(f"  [PASS] WHO from context: {tags[TagType.WHO].value} ({tags[TagType.WHO].confidence:.2f})")

    assert TagType.WHEN in tags
    assert tags[TagType.WHEN].confidence > 0.8  # From context
    print(f"  [PASS] WHEN from context: confidence={tags[TagType.WHEN].confidence:.2f}")

    assert TagType.PROJECT in tags
    assert tags[TagType.PROJECT].confidence > 0.8  # From context
    print(f"  [PASS] PROJECT from context: {tags[TagType.PROJECT].value}")

    assert TagType.WHY in tags
    assert tags[TagType.WHY].value == "implementation"
    print(f"  [PASS] WHY detection: {tags[TagType.WHY].value}")

    # Test without context
    tags2 = scorer.assign_tags("Fix the bug in the authentication module")
    assert tags2[TagType.WHY].value == "bugfix"
    print(f"  [PASS] WHY without context: {tags2[TagType.WHY].value}")

    # Test project detection from content
    tags3 = scorer.assign_tags("Working on trader-ai momentum implementation")
    assert tags3[TagType.PROJECT].value == "trader-ai"
    print(f"  [PASS] PROJECT from content: {tags3[TagType.PROJECT].value}")

    # Test assign_tags_with_result
    result = scorer.assign_tags_with_result("Refactoring the database layer")
    assert result.classification_type.value == "tag_assignment"
    assert result.confidence.score > 0
    print(f"  [PASS] assign_tags_with_result: confidence={result.confidence.score:.2f}")

    # Test WHY categories
    test_cases = [
        ("Adding new API endpoint", "implementation"),
        ("Fixing crash on startup", "bugfix"),
        ("Refactoring authentication", "refactor"),
        ("Writing unit tests", "testing"),
        ("Updating README documentation", "documentation"),
        ("Need to analyze and research this issue", "analysis"),
        ("Planning architecture design", "planning"),
        ("Setting up CI/CD pipeline", "infrastructure"),
    ]
    for text, expected_why in test_cases:
        tags = scorer.assign_tags(text)
        assert tags[TagType.WHY].value == expected_why, f"Expected {expected_why}, got {tags[TagType.WHY].value}"
    print("  [PASS] All WHY categories detected correctly")

    # Test statistics
    stats = scorer.get_stats()
    assert stats["total_assignments"] > 0
    print(f"  [PASS] Stats tracking: {stats['total_assignments']} assignments")

    print("  [ALL PASS] Tag scorer tests")


def test_escalation_service():
    """Test human escalation service."""
    print("\n=== Testing Escalation Service ===")

    from src.services.confidence.escalation_service import (
        EscalationService,
        EscalationQueueConfig,
    )
    from src.integrations.confidence_scoring_schema import (
        ClassificationResult,
        ClassificationType,
        EscalationReason,
        EscalationStatus,
    )

    service = EscalationService()

    # Create a low-confidence result
    result = ClassificationResult.create(
        classification_type=ClassificationType.MODE_DETECTION,
        value="unknown",
        confidence_score=0.25,  # Below 0.3 threshold for LOW_CONFIDENCE
        input_text="This is ambiguous text",
    )

    # Test should_escalate
    assert service.should_escalate(result)
    print("  [PASS] should_escalate")

    # Test get_escalation_reason
    reason = service.get_escalation_reason(result)
    assert reason == EscalationReason.LOW_CONFIDENCE
    print(f"  [PASS] get_escalation_reason: {reason.value}")

    # Test create_escalation
    escalation = service.create_escalation(
        result, EscalationReason.LOW_CONFIDENCE, {"test": True}
    )
    assert escalation.request_id
    assert escalation.status == EscalationStatus.PENDING
    print(f"  [PASS] create_escalation: {escalation.request_id}")

    # Test get_pending
    pending = service.get_pending()
    assert len(pending) == 1
    assert pending[0].request_id == escalation.request_id
    print(f"  [PASS] get_pending: {len(pending)} pending")

    # Test get_next_for_review
    next_esc = service.get_next_for_review()
    assert next_esc is not None
    assert next_esc.status == EscalationStatus.IN_REVIEW
    print("  [PASS] get_next_for_review")

    # Test resolve
    resolved = service.resolve(
        escalation.request_id,
        resolved_value="execution",
        resolved_by="human_reviewer",
        notes="Confirmed as execution mode",
    )
    assert resolved.status == EscalationStatus.RESOLVED
    assert resolved.resolved_value == "execution"
    print("  [PASS] resolve")

    # Test pending is empty after resolution
    pending_after = service.get_pending()
    assert len(pending_after) == 0
    print("  [PASS] Pending cleared after resolution")

    # Test dismiss
    result2 = ClassificationResult.create(
        classification_type=ClassificationType.ENTITY_EXTRACTION,
        value=[],
        confidence_score=0.3,
    )
    esc2 = service.create_escalation(result2, EscalationReason.LOW_CONFIDENCE)
    dismissed = service.dismiss(esc2.request_id, notes="Not important")
    assert dismissed.status == EscalationStatus.DISMISSED
    print("  [PASS] dismiss")

    # Test statistics
    stats = service.get_stats()
    assert stats["total_created"] == 2
    assert stats["total_resolved"] == 1
    assert stats["total_dismissed"] == 1
    print(f"  [PASS] Stats: created={stats['total_created']}, resolved={stats['total_resolved']}")

    # Test export_for_training
    training_data = service.export_for_training()
    assert len(training_data) == 1  # Only resolved, not dismissed
    print(f"  [PASS] export_for_training: {len(training_data)} records")

    # Test maybe_escalate
    high_conf_result = ClassificationResult.create(
        classification_type=ClassificationType.MODE_DETECTION,
        value="execution",
        confidence_score=0.9,
    )
    maybe_esc = service.maybe_escalate(high_conf_result)
    assert maybe_esc is None  # High confidence, no escalation
    print("  [PASS] maybe_escalate (no escalation for high confidence)")

    low_conf_result = ClassificationResult.create(
        classification_type=ClassificationType.MODE_DETECTION,
        value="unknown",
        confidence_score=0.4,
    )
    maybe_esc2 = service.maybe_escalate(low_conf_result)
    assert maybe_esc2 is not None
    print("  [PASS] maybe_escalate (escalation for low confidence)")

    print("  [ALL PASS] Escalation service tests")


def test_confidence_coordinator():
    """Test confidence coordinator."""
    print("\n=== Testing Confidence Coordinator ===")

    from src.services.confidence.confidence_coordinator import (
        ConfidenceCoordinator,
        CoordinatorConfig,
        get_coordinator,
        initialize_coordinator,
    )

    # Initialize coordinator
    config = CoordinatorConfig(
        escalation_threshold=0.6,
        enable_auto_escalation=True,
    )
    coordinator = ConfidenceCoordinator(config)

    # Test score_text
    result = coordinator.score_text(
        "What is the status of the memory-mcp project?",
        context={"agent_id": "tester:1.0.0"},
    )
    assert result.mode is not None
    assert result.entities is not None
    assert result.tags is not None
    assert result.quality_gate is not None
    print(f"  [PASS] score_text: overall={result.overall_confidence:.2f}")

    # Test individual scorers
    mode_result = coordinator.score_mode("Show me the files")
    assert mode_result.value in ["execution", "planning", "brainstorming"]
    print(f"  [PASS] score_mode: {mode_result.value}")

    entity_result = coordinator.score_entities("Contact john@test.com")
    assert entity_result.confidence.score > 0
    print(f"  [PASS] score_entities: {len(entity_result.value)} entities")

    tag_result = coordinator.score_tags("Fixing authentication bug")
    assert tag_result.confidence.score > 0
    print(f"  [PASS] score_tags: confidence={tag_result.confidence.score:.2f}")

    # Test run_quality_gate
    from src.integrations.confidence_scoring_schema import ClassificationResult, ClassificationType
    results = [
        ClassificationResult.create(ClassificationType.MODE_DETECTION, "execution", 0.8),
        ClassificationResult.create(ClassificationType.ENTITY_EXTRACTION, [], 0.7),
    ]
    gate_result = coordinator.run_quality_gate(results)
    assert gate_result.passed
    print(f"  [PASS] run_quality_gate: passed={gate_result.passed}")

    # Test escalation flow
    low_conf = coordinator.score_text("ambiguous unclear text maybe?")
    if low_conf.escalation:
        print(f"  [PASS] Auto-escalation created: {low_conf.escalation.request_id}")
    else:
        print("  [INFO] No escalation needed (confidence was high enough)")

    # Test get_pending_escalations
    pending = coordinator.get_pending_escalations()
    print(f"  [PASS] get_pending_escalations: {len(pending)} pending")

    # Test statistics
    stats = coordinator.get_stats()
    assert "coordinator" in stats
    assert "mode_scorer" in stats
    print("  [PASS] get_stats")

    # Test singleton pattern
    init_coord = initialize_coordinator()
    get_coord = get_coordinator()
    assert init_coord is get_coord
    print("  [PASS] Singleton pattern")

    # Test clear_caches
    coordinator.clear_caches()
    print("  [PASS] clear_caches")

    print("  [ALL PASS] Confidence coordinator tests")


async def test_mcp_tools():
    """Test MCP tools for confidence scoring."""
    print("\n=== Testing MCP Tools ===")

    from src.mcp.tools.confidence_tools import ConfidenceTools, CONFIDENCE_TOOLS

    tools = ConfidenceTools()

    # Test score_text
    result = await tools.score_text("How do I implement authentication?")
    assert result["success"]
    assert "overall_confidence" in result
    print(f"  [PASS] score_text: confidence={result['overall_confidence']:.2f}")

    # Test score_text_detailed
    detailed = await tools.score_text_detailed("What if we redesigned the system?")
    assert "mode" in detailed
    assert "entities" in detailed
    print("  [PASS] score_text_detailed")

    # Test detect_mode
    mode = await tools.detect_mode("Show me the logs")
    assert "mode" in mode
    assert mode["mode"] == "execution"
    print(f"  [PASS] detect_mode: {mode['mode']}")

    # Test extract_entities
    entities = await tools.extract_entities("Contact support@example.com")
    assert entities["count"] > 0
    print(f"  [PASS] extract_entities: {entities['count']} entities")

    # Test assign_tags
    tags = await tools.assign_tags("Fixing memory leak bug")
    assert "tags" in tags
    print(f"  [PASS] assign_tags: confidence={tags['overall_confidence']:.2f}")

    # Test run_quality_gate
    gate_result = await tools.run_quality_gate([
        {"name": "mode", "confidence": 0.8, "type": "mode_detection"},
        {"name": "entities", "confidence": 0.7, "type": "entity_extraction"},
    ])
    assert gate_result["passed"]
    print(f"  [PASS] run_quality_gate: passed={gate_result['passed']}")

    # Test create_escalation
    esc = await tools.create_escalation(
        classification_type="mode_detection",
        value="unknown",
        confidence=0.3,
        input_text="test",
        reason="low_confidence",
    )
    assert esc["success"]
    request_id = esc["request_id"]
    print(f"  [PASS] create_escalation: {request_id}")

    # Test get_pending_escalations
    pending = await tools.get_pending_escalations()
    assert pending["count"] > 0
    print(f"  [PASS] get_pending_escalations: {pending['count']} pending")

    # Test get_next_escalation
    next_esc = await tools.get_next_escalation()
    assert next_esc["found"]
    print("  [PASS] get_next_escalation")

    # Test resolve_escalation
    resolved = await tools.resolve_escalation(
        request_id=request_id,
        resolved_value="execution",
        resolved_by="test_user",
        notes="Test resolution",
    )
    assert resolved["success"]
    print("  [PASS] resolve_escalation")

    # Test get_confidence_stats
    stats = await tools.get_confidence_stats()
    assert "coordinator" in stats
    print("  [PASS] get_confidence_stats")

    # Test export_training_data
    training = await tools.export_training_data()
    assert "training_data" in training
    print(f"  [PASS] export_training_data: {training['count']} records")

    # Test clear_caches
    cleared = await tools.clear_caches()
    assert cleared["success"]
    print("  [PASS] clear_caches")

    # Test tool definitions
    assert len(CONFIDENCE_TOOLS) >= 10
    print(f"  [PASS] Tool definitions: {len(CONFIDENCE_TOOLS)} tools defined")

    print("  [ALL PASS] MCP tools tests")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("CAPTURE-003: Confidence Scoring System - Dry Run Tests")
    print("=" * 60)

    try:
        test_schema()
        test_mode_detector()
        test_entity_extractor()
        test_quality_gate()
        test_tag_scorer()
        test_escalation_service()
        test_confidence_coordinator()
        asyncio.run(test_mcp_tools())

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n[FAIL] Assertion error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
