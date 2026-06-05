#!/usr/bin/env python3
"""
Test script for RLM and SEED-003 implementations.

Tests:
- SEED-003: Promotion hook in lifecycle scheduler
- RLM-001: RLM module foundation
- RLM-002: RLMEnvironment base class
- RLM-003: Cost tracker and recursion limits
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_seed003_promotion_hook():
    """Test SEED-003: Promotion hook in lifecycle scheduler."""
    print("Test 1: SEED-003 - Promotion Hook in Lifecycle Scheduler")
    try:
        from src.memory.lifecycle_scheduler import LifecycleScheduler
        from src.memory.memory_promoter import MemoryPromoter

        # Verify LifecycleScheduler accepts promoter
        class MockLifecycleManager:
            def demote_stale_chunks(self): return 0
            def archive_demoted_chunks(self): return 0
            def cleanup_expired(self): return 0
            def get_expiring_soon(self, days=7, limit=100): return []

        manager = MockLifecycleManager()
        promoter = MemoryPromoter()
        scheduler = LifecycleScheduler(manager, promoter)

        # Check promoter is set
        assert scheduler.promoter is not None
        assert isinstance(scheduler.promoter, MemoryPromoter)

        # Check promotion methods exist
        assert hasattr(scheduler, "_check_promotions")
        assert hasattr(scheduler, "_get_promotion_candidates")
        assert hasattr(scheduler, "_execute_promotion")
        assert hasattr(scheduler, "get_promotion_stats")

        # Check stats
        stats = scheduler.get_promotion_stats()
        assert "total_promoted" in stats
        assert "promoter_stats" in stats

        print("  [PASS] Promotion hook works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_rlm001_module_foundation():
    """Test RLM-001: RLM module foundation."""
    print("Test 2: RLM-001 - RLM Module Foundation")
    try:
        from src.rlm import (
            RLMEnvironment,
            RLMConfig,
            RLMResult,
            ExecutionContext,
            CostTracker,
            CostConfig,
            CostRecord,
            CostAlert,
            RecursionLimitError,
            CostLimitError,
        )

        # Check version
        from src import rlm
        assert hasattr(rlm, "__version__")
        assert rlm.__version__ == "0.1.0"

        # Check all exports
        assert RLMEnvironment is not None
        assert CostTracker is not None
        assert RecursionLimitError is not None

        print("  [PASS] RLM module foundation works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_rlm002_environment():
    """Test RLM-002: RLMEnvironment base class."""
    print("Test 3: RLM-002 - RLMEnvironment Base Class")
    try:
        from src.rlm.rlm_environment import (
            RLMEnvironment,
            RLMConfig,
            RLMResult,
            ExecutionContext,
            ExecutionMode,
        )

        # Test config
        config = RLMConfig(max_depth=5, max_tokens=4000)
        assert config.max_depth == 5
        assert config.max_tokens == 4000
        assert config.sandbox_mode == True

        # Test execution context
        ctx = ExecutionContext()
        assert ctx.depth == 0
        assert ctx.tokens_used == 0

        # Test child context
        child = ctx.child("step_1")
        assert child.depth == 1
        assert child.path == ["step_1"]
        assert child.parent_context == ctx

        # Test RLMResult
        result = RLMResult(
            success=True,
            data={"test": "data"},
            depth_reached=3,
            tokens_used=1000,
            duration_ms=500
        )
        assert result.success
        assert result.depth_reached == 3
        assert result.error is None

        # Test execution mode enum
        assert ExecutionMode.SEARCH.value == "search"
        assert ExecutionMode.RECURSIVE.value == "recursive"

        print("  [PASS] RLMEnvironment base class works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_rlm003_cost_tracker():
    """Test RLM-003: Cost tracker and recursion limits."""
    print("Test 4: RLM-003 - Cost Tracker")
    try:
        from src.rlm.cost_tracker import (
            CostTracker,
            CostConfig,
            CostRecord,
            CostAlert,
            CostAlertLevel,
            RecursionLimitError,
            CostLimitError,
            TOKEN_COSTS,
        )

        # Test config
        config = CostConfig(
            max_recursion_depth=5,
            cost_limit_usd=0.50,
            spike_threshold=3.0
        )
        assert config.max_recursion_depth == 5
        assert config.cost_limit_usd == 0.50

        # Test tracker
        tracker = CostTracker(config)

        # Test recursion check
        tracker.check_recursion(1)
        tracker.check_recursion(3)
        tracker.check_recursion(5)

        # Test recursion limit error
        try:
            tracker.check_recursion(6)
            assert False, "Should have raised RecursionLimitError"
        except RecursionLimitError as e:
            assert e.depth == 6
            assert e.max_depth == 5

        # Test cost recording
        record = tracker.record_cost("test_op", 1000, "claude-3-haiku")
        assert record.tokens == 1000
        assert record.cost_usd > 0

        # Test stats
        stats = tracker.get_stats()
        assert stats["total_tokens"] == 1000
        assert stats["max_depth_reached"] == 6
        assert "usage_percent" in stats

        # Test alerts
        alerts = tracker.get_alerts()
        assert len(alerts) > 0

        # Test reset
        tracker.reset()
        stats = tracker.get_stats()
        assert stats["total_tokens"] == 0

        print("  [PASS] Cost tracker works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_rlm_integration():
    """Test RLM components integration."""
    print("Test 5: RLM Integration")
    try:
        from src.rlm import RLMConfig, ExecutionContext, CostTracker, CostConfig

        # Create integrated setup
        rlm_config = RLMConfig(max_depth=10)
        cost_config = CostConfig(max_recursion_depth=10)
        tracker = CostTracker(cost_config)

        # Simulate a recursive operation
        ctx = ExecutionContext()

        for i in range(5):
            tracker.check_recursion(i)
            tracker.record_cost(f"query_{i}", 500)
            ctx = ctx.child(f"step_{i}")

        assert ctx.depth == 5
        assert tracker.get_stats()["operations_count"] == 5

        print("  [PASS] RLM integration works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING SEED-003 AND RLM IMPLEMENTATIONS")
    print("=" * 60)
    print()

    results = []

    results.append(("SEED-003", test_seed003_promotion_hook()))
    print()

    results.append(("RLM-001", test_rlm001_module_foundation()))
    print()

    results.append(("RLM-002", test_rlm002_environment()))
    print()

    results.append(("RLM-003", test_rlm003_cost_tracker()))
    print()

    results.append(("Integration", test_rlm_integration()))
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
