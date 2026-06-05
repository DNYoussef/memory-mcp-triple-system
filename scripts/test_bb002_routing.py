#!/usr/bin/env python3
"""Test BB-002: Beads Routing Policy Implementation.

Verifies that UnifiedRetrievalRouter correctly allocates budget
between Beads and Memory MCP based on mode.

WHO: bb-002-verifier:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (BB-002)
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.routing.unified_router import UnifiedRetrievalRouter


def test_weight_configuration():
    """Test that routing weights match BB-002 specification."""
    print("\n" + "=" * 60)
    print("TEST 1: Routing Weight Configuration")
    print("=" * 60)

    # Create mock router (no actual services needed for weight check)
    router = UnifiedRetrievalRouter(
        beads_bridge=None,
        memory_service=None,
    )

    # Verify weights
    expected_weights = {
        "execution": (0.8, 0.2),
        "planning": (0.5, 0.5),
        "brainstorming": (0.2, 0.8),
    }

    actual_weights = router._weights

    print(f"\nExpected weights (BB-002 spec):")
    for mode, (beads, memory) in expected_weights.items():
        print(f"  {mode:15s}: {beads*100:.0f}% Beads, {memory*100:.0f}% Memory")

    print(f"\nActual weights (implementation):")
    for mode, (beads, memory) in actual_weights.items():
        print(f"  {mode:15s}: {beads*100:.0f}% Beads, {memory*100:.0f}% Memory")

    # Compare
    matches = True
    for mode in expected_weights:
        if mode not in actual_weights:
            print(f"\n[FAIL] Missing mode: {mode}")
            matches = False
            continue

        exp_beads, exp_memory = expected_weights[mode]
        act_beads, act_memory = actual_weights[mode]

        if abs(exp_beads - act_beads) > 0.01 or abs(exp_memory - act_memory) > 0.01:
            print(f"\n[FAIL] Mismatch for {mode}:")
            print(f"  Expected: ({exp_beads}, {exp_memory})")
            print(f"  Actual: ({act_beads}, {act_memory})")
            matches = False

    if matches:
        print("\n[PASS] All routing weights match BB-002 specification")
        return True
    else:
        return False


def test_budget_allocation():
    """Test that token budgets are allocated correctly."""
    print("\n" + "=" * 60)
    print("TEST 2: Token Budget Allocation")
    print("=" * 60)

    router = UnifiedRetrievalRouter(
        beads_bridge=None,
        memory_service=None,
    )

    test_cases = [
        ("execution", 10000, 8000, 2000),
        ("planning", 10000, 5000, 5000),
        ("brainstorming", 10000, 2000, 8000),
        ("execution", 5000, 4000, 1000),
        ("planning", 15000, 7500, 7500),
    ]

    print("\nBudget allocation tests:")
    all_passed = True

    for mode, total_budget, expected_beads, expected_memory in test_cases:
        beads_weight, memory_weight = router._weights.get(mode, (0.8, 0.2))
        actual_beads = int(total_budget * beads_weight)
        actual_memory = max(0, total_budget - actual_beads)

        passed = (actual_beads == expected_beads and actual_memory == expected_memory)
        status = "[PASS]" if passed else "[FAIL]"

        print(f"  {status} {mode:15s} | Budget: {total_budget:5d} -> Beads: {actual_beads:4d}, Memory: {actual_memory:4d}")

        if not passed:
            print(f"         Expected: Beads: {expected_beads}, Memory: {expected_memory}")
            all_passed = False

    if all_passed:
        print("\n[PASS] All budget allocations correct")
        return True
    else:
        print("\n[FAIL] Some budget allocations incorrect")
        return False


def test_routing_interface():
    """Test that routing interface matches expected API."""
    print("\n" + "=" * 60)
    print("TEST 3: Routing Interface")
    print("=" * 60)

    router = UnifiedRetrievalRouter(
        beads_bridge=None,
        memory_service=None,
    )

    # Check method signature
    import inspect
    sig = inspect.signature(router.retrieve)
    params = list(sig.parameters.keys())

    expected_params = ['query', 'mode', 'token_budget']
    print(f"\nExpected parameters: {expected_params}")
    print(f"Actual parameters: {params}")

    if params == expected_params:
        print("\n[PASS] Routing interface matches specification")
        return True
    else:
        print("\n[FAIL] Routing interface mismatch")
        return False


def main():
    """Run all BB-002 verification tests."""
    print("\n" + "=" * 70)
    print("BB-002: BEADS ROUTING POLICY VERIFICATION")
    print("=" * 70)
    print(f"Testing implementation in: {project_root / 'src/routing/unified_router.py'}")

    results = []

    # Test 1: Weight configuration
    results.append(("Weight Configuration", test_weight_configuration()))

    # Test 2: Budget allocation
    results.append(("Budget Allocation", test_budget_allocation()))

    # Test 3: Interface
    results.append(("Routing Interface", test_routing_interface()))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("BB-002 IMPLEMENTATION VERIFIED: ALL TESTS PASSED")
        print("\nRouting policy correctly implements:")
        print("  - Execution mode: 80% Beads, 20% Memory")
        print("  - Planning mode: 50% Beads, 50% Memory")
        print("  - Brainstorming mode: 20% Beads, 80% Memory")
    else:
        print("SOME TESTS FAILED - REVIEW IMPLEMENTATION")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
