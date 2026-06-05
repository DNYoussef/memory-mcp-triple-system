#!/usr/bin/env python3
"""
Test script for RLM-007: Recursive Query Interface.

Tests:
- recursive_query() with string queries
- recursive_query() with callable query generators
- Depth limiting and max_depth config
- RecursiveQueryResult tracking
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_recursive_query_strings():
    """Test recursive_query() with string queries."""
    print("Test 1: recursive_query() with string queries")
    try:
        from src.rlm import RLMMemoryEnvironment, RLMConfig, RecursiveQueryResult

        # Create environment with test data
        config = RLMConfig(max_depth=5)
        env = RLMMemoryEnvironment(config=config)

        # Inject test data
        env._kv_data = {
            "expertise:python:patterns": {"content": "Python design patterns for web apps"},
            "expertise:python:testing": {"content": "Python testing frameworks pytest unittest"},
            "expertise:python:async": {"content": "Python async patterns asyncio"},
            "expertise:rust:memory": {"content": "Rust memory management ownership"},
            "findings:security:high:001": {"content": "SQL injection in Python web app"},
            "findings:security:medium:002": {"content": "Missing CSRF in Python Flask"},
            "findings:performance:low:003": {"content": "Slow database query in Python"},
        }
        env._loaded = True

        # Test: Search "python" then refine to "testing"
        result = env.recursive_query(["python", "testing"])

        assert isinstance(result, RecursiveQueryResult)
        assert result.depth == 2
        assert len(result.path) == 2
        assert result.path[0] == "python"
        assert result.path[1] == "testing"
        assert len(result.intermediate_counts) == 2
        assert result.intermediate_counts[0] >= 1  # At least one python item
        assert result.total_queries == 2

        print(f"  Depth: {result.depth}")
        print(f"  Path: {result.path}")
        print(f"  Intermediate counts: {result.intermediate_counts}")
        print(f"  Final results: {len(result.results)}")

        # Test: Deep query chain
        result2 = env.recursive_query(["expertise", "python", "patterns"])
        assert result2.depth == 3
        assert len(result2.results) >= 1

        print("  [PASS] recursive_query() with string queries works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recursive_query_callables():
    """Test recursive_query() with callable query generators."""
    print("Test 2: recursive_query() with callable generators")
    try:
        from src.rlm import RLMMemoryEnvironment, RLMConfig

        config = RLMConfig(max_depth=5)
        env = RLMMemoryEnvironment(config=config)

        # Inject test data
        env._kv_data = {
            "findings:bug:high:001": {"content": "Memory leak in service A"},
            "findings:bug:high:002": {"content": "Memory corruption in module B"},
            "findings:bug:medium:003": {"content": "Race condition in handler C"},
            "fixes:bug:001": {"content": "Fixed memory leak by adding cleanup"},
            "fixes:bug:002": {"content": "Fixed memory corruption with bounds check"},
        }
        env._loaded = True

        # Dynamic query generator
        def find_fixes(results):
            """Generate fix query based on found bugs."""
            if not results:
                return "fixes"
            # Extract first bug ID to find its fix
            first_result = results[0]
            item_id = first_result.get("id", "")
            if "findings:bug:" in item_id:
                bug_id = item_id.split(":")[-1]
                return f"fixes:bug:{bug_id}"
            return "fixes"

        # Test: Find bugs, then dynamically find fixes
        result = env.recursive_query([
            "findings:bug",
            find_fixes
        ])

        assert result.depth == 2
        assert result.path[0] == "findings:bug"
        # Second query should be generated dynamically
        assert "fixes" in result.path[1]

        print(f"  Path: {result.path}")
        print(f"  Results: {len(result.results)}")

        print("  [PASS] recursive_query() with callable generators works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recursive_query_depth_limit():
    """Test recursive_query() depth limiting."""
    print("Test 3: recursive_query() depth limiting")
    try:
        from src.rlm import RLMMemoryEnvironment, RLMConfig

        # Config with low max_depth
        config = RLMConfig(max_depth=2)
        env = RLMMemoryEnvironment(config=config)

        env._kv_data = {
            "a:b:c:d:e": {"content": "Deep nested item"},
        }
        env._loaded = True

        # Try to go deeper than max_depth
        result = env.recursive_query(["a", "b", "c", "d", "e"])

        # Should stop at depth 2
        assert result.depth <= 2
        assert len(result.path) <= 2

        print(f"  Max depth config: {config.max_depth}")
        print(f"  Actual depth: {result.depth}")
        print(f"  Path taken: {result.path}")

        print("  [PASS] recursive_query() depth limiting works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recursive_query_empty_results():
    """Test recursive_query() when no results found."""
    print("Test 4: recursive_query() with empty results")
    try:
        from src.rlm import RLMMemoryEnvironment, RLMConfig

        config = RLMConfig(max_depth=5)
        env = RLMMemoryEnvironment(config=config)

        env._kv_data = {
            "expertise:python": {"content": "Python content"},
        }
        env._loaded = True

        # Query that will have no results at depth 2
        result = env.recursive_query(["python", "nonexistent_xyz"])

        # Should stop early when no results
        assert result.depth == 2
        assert len(result.results) == 0
        assert result.intermediate_counts[-1] == 0

        print(f"  Stopped at depth: {result.depth}")
        print(f"  Final results: {len(result.results)}")

        print("  [PASS] recursive_query() handles empty results correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recursive_query_result_to_dict():
    """Test RecursiveQueryResult.to_dict()."""
    print("Test 5: RecursiveQueryResult.to_dict()")
    try:
        from src.rlm import RecursiveQueryResult

        result = RecursiveQueryResult(
            results=[{"id": "1", "content": "test"}],
            depth=3,
            path=["a", "b", "c"],
            intermediate_counts=[10, 5, 1],
            total_queries=3
        )

        d = result.to_dict()

        assert d["depth"] == 3
        assert d["path"] == ["a", "b", "c"]
        assert d["intermediate_counts"] == [10, 5, 1]
        assert d["total_queries"] == 3
        assert d["final_count"] == 1
        assert len(d["results"]) == 1

        print(f"  to_dict() output: {d}")

        print("  [PASS] RecursiveQueryResult.to_dict() works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rlm007_integration():
    """Test RLM-007 integration with other components."""
    print("Test 6: RLM-007 Integration")
    try:
        from src.rlm import (
            RLMMemoryEnvironment,
            RLMConfig,
            RecursiveQueryResult,
            RLMLogger,
        )
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config = RLMConfig(max_depth=10)
            env = RLMMemoryEnvironment(config=config)
            rlm_logger = RLMLogger(output_dir=tmpdir)

            # Load real data if available
            env.load_data("all")

            # Start trace
            trace_id = rlm_logger.start_trace("Test recursive query")

            # Execute recursive query
            result = env.recursive_query(
                ["expertise", "python"],
                limit_per_depth=10
            )

            # Log results
            rlm_logger.log_search("expertise", depth=1, result_count=result.intermediate_counts[0] if result.intermediate_counts else 0)
            if len(result.intermediate_counts) > 1:
                rlm_logger.log_recurse("python", depth=2)

            rlm_logger.end_trace(result=result.to_dict())

            # Verify
            stats = rlm_logger.get_stats()
            assert stats.total_events >= 2

            rlm_logger.close()

        print("  [PASS] RLM-007 integration works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING RLM-007: RECURSIVE QUERY INTERFACE")
    print("=" * 60)
    print()

    results = []

    results.append(("StringQueries", test_recursive_query_strings()))
    print()

    results.append(("CallableQueries", test_recursive_query_callables()))
    print()

    results.append(("DepthLimit", test_recursive_query_depth_limit()))
    print()

    results.append(("EmptyResults", test_recursive_query_empty_results()))
    print()

    results.append(("ToDict", test_recursive_query_result_to_dict()))
    print()

    results.append(("Integration", test_rlm007_integration()))
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
