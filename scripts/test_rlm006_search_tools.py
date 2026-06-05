#!/usr/bin/env python3
"""
Test script for RLM-006: Memory MCP Search Tools.

Tests:
- search_by_namespace()
- search_by_time_range()
- search_by_content()
- search_graph_edges()
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_search_by_namespace():
    """Test search_by_namespace()."""
    print("Test 1: search_by_namespace()")
    try:
        from src.rlm.tools.search_tools import RLMSearchTools, SearchResult

        # Create test data
        kv_data = {
            "expertise:python:patterns": {"content": "Python design patterns", "created_at": "2026-01-20T10:00:00"},
            "expertise:python:testing": {"content": "Python testing best practices"},
            "expertise:rust:memory": {"content": "Rust memory management"},
            "findings:security:high:001": {"content": "SQL injection vulnerability"},
            "findings:security:low:002": {"content": "Missing CSRF token"},
            "tasks:project:task-001": {"content": "Implement feature X"},
        }

        tools = RLMSearchTools(kv_data=kv_data)

        # Test prefix search
        results = tools.search_by_namespace("expertise:python")
        assert len(results) == 2
        assert all(r.namespace == "expertise" for r in results)

        # Test broader prefix
        results = tools.search_by_namespace("findings")
        assert len(results) == 2

        # Test exact match
        results = tools.search_by_namespace("expertise:python:patterns", exact_match=True)
        assert len(results) == 1

        # Test no results
        results = tools.search_by_namespace("nonexistent")
        assert len(results) == 0

        print("  [PASS] search_by_namespace() works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_by_time_range():
    """Test search_by_time_range()."""
    print("Test 2: search_by_time_range()")
    try:
        from src.rlm.tools.search_tools import RLMSearchTools, TimeRange

        now = datetime.utcnow()
        yesterday = (now - timedelta(days=1)).isoformat()
        last_week = (now - timedelta(days=7)).isoformat()
        last_month = (now - timedelta(days=30)).isoformat()

        kv_data = {
            "task:recent:001": {"content": "Recent task", "created_at": yesterday},
            "task:week:002": {"content": "Week old task", "created_at": last_week},
            "task:old:003": {"content": "Old task", "created_at": last_month},
            "task:no_time:004": {"content": "No timestamp task"},
        }

        tools = RLMSearchTools(kv_data=kv_data)

        # Test last 3 days
        time_range = TimeRange.last_days(3)
        results = tools.search_by_time_range(time_range)
        # Should include recent + no_time (included if no timestamp)
        assert len(results) >= 1

        # Test last 14 days
        time_range = TimeRange.last_days(14)
        results = tools.search_by_time_range(time_range)
        assert len(results) >= 2

        # Test with namespace filter
        time_range = TimeRange.last_days(365)
        results = tools.search_by_time_range(time_range, namespace_filter="task:recent")
        assert len(results) == 1

        print("  [PASS] search_by_time_range() works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_by_content():
    """Test search_by_content()."""
    print("Test 3: search_by_content()")
    try:
        from src.rlm.tools.search_tools import RLMSearchTools

        kv_data = {
            "doc:001": {"content": "Python is a great programming language"},
            "doc:002": {"content": "JavaScript runs in the browser"},
            "doc:003": {"content": "PYTHON patterns for web development"},
            "doc:004": {"content": "Error handling in applications"},
        }

        tools = RLMSearchTools(kv_data=kv_data)

        # Test case-insensitive search (default)
        results = tools.search_by_content("python")
        assert len(results) == 2  # Both python and PYTHON

        # Test case-sensitive search
        results = tools.search_by_content("Python", case_sensitive=True)
        assert len(results) == 1

        # Test regex search
        results = tools.search_by_content(r"Error.*handling", use_regex=True)
        assert len(results) == 1

        # Test no results
        results = tools.search_by_content("nonexistent_query_xyz")
        assert len(results) == 0

        print("  [PASS] search_by_content() works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_graph_edges():
    """Test search_graph_edges()."""
    print("Test 4: search_graph_edges()")
    try:
        from src.rlm.tools.search_tools import RLMSearchTools, GraphEdgeFilter

        graph_data = {
            "nodes": [
                {"id": "1", "label": "User Service", "type": "service"},
                {"id": "2", "label": "Auth Service", "type": "service"},
                {"id": "3", "label": "User Database", "type": "database"},
                {"id": "4", "label": "Redis Cache", "type": "cache"},
            ],
            "edges": [
                {"source": "1", "target": "2", "label": "authenticates"},
                {"source": "1", "target": "3", "label": "reads"},
                {"source": "2", "target": "3", "label": "writes"},
                {"source": "1", "target": "4", "label": "caches"},
            ]
        }

        tools = RLMSearchTools(graph_data=graph_data)

        # Test relation filter
        edge_filter = GraphEdgeFilter(relation_type="authenticates")
        results = tools.search_graph_edges(edge_filter)
        assert len(results) == 1
        assert "authenticates" in results[0].content

        # Test source type filter
        edge_filter = GraphEdgeFilter(source_type="service")
        results = tools.search_graph_edges(edge_filter)
        assert len(results) == 4  # All edges have service as source

        # Test target type filter
        edge_filter = GraphEdgeFilter(target_type="database")
        results = tools.search_graph_edges(edge_filter)
        assert len(results) == 2  # reads and writes

        # Test combined filter
        edge_filter = GraphEdgeFilter(relation_type="reads", target_type="database")
        results = tools.search_graph_edges(edge_filter)
        assert len(results) == 1

        print("  [PASS] search_graph_edges() works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rlm_tools_integration():
    """Test RLMSearchTools integration."""
    print("Test 5: RLMSearchTools Integration")
    try:
        from src.rlm.tools import (
            RLMSearchTools,
            SearchResult,
            TimeRange,
            GraphEdgeFilter,
            search_by_namespace,
            search_by_content,
        )

        # Test imports work
        assert RLMSearchTools is not None
        assert SearchResult is not None
        assert TimeRange is not None
        assert GraphEdgeFilter is not None

        # Test convenience functions
        kv_data = {"test:001": {"content": "test data"}}
        results = search_by_namespace(kv_data, "test")
        assert len(results) == 1

        results = search_by_content(kv_data, "test")
        assert len(results) == 1

        # Test stats
        tools = RLMSearchTools(kv_data=kv_data)
        tools.search_by_namespace("test")
        tools.search_by_content("data")
        stats = tools.get_stats()
        assert stats["search_count"] == 2
        assert stats["kv_items"] == 1

        print("  [PASS] RLMSearchTools integration works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING RLM-006: MEMORY MCP SEARCH TOOLS")
    print("=" * 60)
    print()

    results = []

    results.append(("Namespace", test_search_by_namespace()))
    print()

    results.append(("TimeRange", test_search_by_time_range()))
    print()

    results.append(("Content", test_search_by_content()))
    print()

    results.append(("GraphEdges", test_search_graph_edges()))
    print()

    results.append(("Integration", test_rlm_tools_integration()))
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
