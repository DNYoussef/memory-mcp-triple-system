#!/usr/bin/env python3
"""
Test script for 6 bead implementations.

Tests:
- ORG-002: Mode-Aware Router
- VEC-002: Entity Extraction Script
- VEC-003: Promotion Pipeline
- SEED-002: Memory Promoter
- ORG-003: Loop 1.5 Storage Interface
- ORG-006: Telemetry Packet Schema
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_org002_mode_aware_router():
    """Test ORG-002: Mode-Aware Router."""
    print("Test 1: ORG-002 - Mode-Aware Router")
    try:
        from src.routing.mode_aware_router import (
            ModeAwareRouter, InteractionMode, RoutingWeight, RoutingDecision, MODE_WEIGHTS
        )
        router = ModeAwareRouter()

        # Test execution mode routing
        decision = router.route("What is the bug?", InteractionMode.EXECUTION)
        assert decision.beads_weight == 0.80, f"Expected 0.80, got {decision.beads_weight}"
        assert decision.memory_weight == 0.20, f"Expected 0.20, got {decision.memory_weight}"
        assert not decision.use_council

        # Test planning mode routing
        decision = router.route("What should I do?", InteractionMode.PLANNING)
        assert decision.beads_weight == 0.50
        assert decision.memory_weight == 0.50
        assert decision.use_council

        # Test brainstorming mode routing
        decision = router.route("What if we tried...", InteractionMode.BRAINSTORMING)
        assert decision.beads_weight == 0.20
        assert decision.memory_weight == 0.80

        # Test stats
        stats = router.get_routing_stats()
        assert stats["total_routes"] == 3

        print("  [PASS] Mode-aware routing works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_seed002_memory_promoter():
    """Test SEED-002: Memory Promoter."""
    print("Test 2: SEED-002 - Memory Promoter")
    try:
        from src.memory.memory_promoter import (
            MemoryPromoter, PromotionCandidate, ContentType, PromotionCriteria
        )
        promoter = MemoryPromoter()

        # Test high-value candidate (should promote)
        candidate = PromotionCandidate(
            memory_id="test-001",
            text="Important expertise about Python patterns",
            metadata={},
            access_count=50,
            reference_count=8,
            content_type=ContentType.EXPERTISE,
            user_importance=0.9
        )
        result = promoter.should_promote(candidate)
        assert result.should_promote, f"Expected promotion, got score {result.total_score}"
        print(f"  High-value score: {result.total_score:.3f} (should promote: {result.should_promote})")

        # Test low-value candidate (should not promote)
        candidate2 = PromotionCandidate(
            memory_id="test-002",
            text="Random context",
            metadata={},
            access_count=0,
            reference_count=0,
            content_type=ContentType.GENERAL,
            user_importance=0.2
        )
        result2 = promoter.should_promote(candidate2)
        assert not result2.should_promote, f"Expected rejection, got score {result2.total_score}"
        print(f"  Low-value score: {result2.total_score:.3f} (should promote: {result2.should_promote})")

        # Test batch evaluation
        results = promoter.evaluate_batch([candidate, candidate2])
        assert len(results) == 2

        # Test stats
        stats = promoter.get_promotion_stats()
        assert stats["total_evaluated"] >= 2

        print("  [PASS] Memory promoter works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_org003_loop_interfaces():
    """Test ORG-003: Loop 1.5 Storage Interface."""
    print("Test 3: ORG-003 - Loop 1.5 Storage Interface")
    try:
        from src.integrations.loop_interfaces import (
            Loop15StorageInterface, Loop3QueryInterface, SignalType, SIGNAL_CONFIDENCE
        )

        interface = Loop15StorageInterface()

        # Test storing a correction
        result = interface.store_correction(
            domain="coding",
            topic="python_style",
            content="Always use snake_case for function names",
            session_id="session-001"
        )
        assert result.success
        assert "L15-" in result.signal_id
        assert result.namespace_key == "expertise:coding:python_style"

        # Test storing a rule
        result2 = interface.store_rule(
            domain="communication",
            topic="email_tone",
            content="Be concise and direct",
            session_id="session-001"
        )
        assert result2.success

        # Test confidence levels
        assert SIGNAL_CONFIDENCE[SignalType.CORRECTION] == 0.90
        assert SIGNAL_CONFIDENCE[SignalType.RULE] == 0.90
        assert SIGNAL_CONFIDENCE[SignalType.APPROVAL] == 0.75
        assert SIGNAL_CONFIDENCE[SignalType.OBSERVATION] == 0.55

        # Test stats
        stats = interface.get_storage_stats()
        assert stats["stored_count"] >= 2

        print("  [PASS] Loop 1.5 storage interface works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_org006_telemetry_schema():
    """Test ORG-006: Telemetry Packet Schema."""
    print("Test 4: ORG-006 - Telemetry Packet Schema")
    try:
        from src.telemetry.packet_schema import (
            TelemetryPacket, TelemetryPacketBuilder, ActionType, TelemetryStatus,
            create_packet, parse_packet
        )

        # Test builder pattern
        packet = (TelemetryPacketBuilder()
            .who("coder:bug-fixer:1.0.0")
            .project("memory-mcp")
            .why(ActionType.BUGFIX)
            .duration(1500)
            .status(TelemetryStatus.SUCCESS)
            .tokens(500)
            .confidence(0.95)
            .build())

        assert packet.who == "coder:bug-fixer:1.0.0"
        assert packet.project == "memory-mcp"
        assert packet.why == ActionType.BUGFIX
        assert packet.duration_ms == 1500
        assert packet.status == TelemetryStatus.SUCCESS
        assert "TEL-" in packet.packet_id

        # Test convenience function
        packet2 = create_packet(
            who="tester:unit:1.0.0",
            project="test-project",
            why=ActionType.TESTING,
            duration_ms=2000,
            status=TelemetryStatus.SUCCESS
        )
        assert packet2.validate() == []  # No validation errors

        # Test parse
        data = packet.to_dict()
        parsed = parse_packet(data)
        assert parsed.who == packet.who
        assert parsed.project == packet.project

        # Test JSON serialization
        json_str = packet.to_json()
        assert "coder:bug-fixer:1.0.0" in json_str

        print("  [PASS] Telemetry packet schema works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_vec002_entity_extraction():
    """Test VEC-002: Entity Extraction Script (import test)."""
    print("Test 5: VEC-002 - Entity Extraction Script (import test)")
    try:
        import scripts.extract_graph_entities as extract_script

        # Verify the module loads correctly
        assert hasattr(extract_script, "extract_entities")
        assert hasattr(extract_script, "load_graph")
        assert hasattr(extract_script, "index_to_chromadb")
        assert hasattr(extract_script, "ENTITY_TYPES")

        # Check entity types
        assert "concept" in extract_script.ENTITY_TYPES
        assert "project" in extract_script.ENTITY_TYPES
        assert "expertise" in extract_script.ENTITY_TYPES

        print("  [PASS] Entity extraction script imports correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_vec003_promotion_pipeline():
    """Test VEC-003: Promotion Pipeline Script (import test)."""
    print("Test 6: VEC-003 - Promotion Pipeline Script (import test)")
    try:
        import scripts.promotion_pipeline as promo_script

        # Verify the module loads correctly
        assert hasattr(promo_script, "evaluate_candidates")
        assert hasattr(promo_script, "promote_to_chromadb")
        assert hasattr(promo_script, "promote_to_seed_archive")
        assert hasattr(promo_script, "get_expiring_memories")

        # Check constants
        assert promo_script.EXPIRY_WINDOW_DAYS == 7
        assert promo_script.MIN_PROMOTION_SCORE == 0.5

        print("  [PASS] Promotion pipeline script imports correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING ALL 6 BEAD IMPLEMENTATIONS")
    print("=" * 60)
    print()

    results = []

    results.append(("ORG-002", test_org002_mode_aware_router()))
    print()

    results.append(("SEED-002", test_seed002_memory_promoter()))
    print()

    results.append(("ORG-003", test_org003_loop_interfaces()))
    print()

    results.append(("ORG-006", test_org006_telemetry_schema()))
    print()

    results.append(("VEC-002", test_vec002_entity_extraction()))
    print()

    results.append(("VEC-003", test_vec003_promotion_pipeline()))
    print()

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: [{status}]")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
