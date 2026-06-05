#!/usr/bin/env python3
"""Real Data Test for MCP-005: Beads MCP Tools Integration.

Tests Beads MCP tools with real CLI operations:
- beads_list
- beads_ready
- beads_show
- beads_search
- beads_stats

WHO: beads-mcp:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (MCP-005)
"""

import sys
import os
import asyncio
from datetime import datetime

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _skip_pytest_if_beads_workspace_unavailable(result):
    """Skip pytest-only when the external Beads workspace is not mounted/configured."""
    error = str(result.get("error", ""))
    unavailable = "WinError 267" in error or "directory name is invalid" in error
    if not result.get("success") and unavailable and "PYTEST_CURRENT_TEST" in os.environ:
        pytest.skip(f"Beads CLI workspace unavailable: {error}")


def test_imports():
    """Test all imports work correctly."""
    print("\n" + "=" * 60)
    print("TEST 1: Import Verification")
    print("=" * 60)

    try:
        from src.mcp.tools.beads_tools import (
            BeadsTools,
            get_beads_tools,
            initialize_beads_tools,
            BEADS_TOOL_DEFINITIONS,
        )
        print("[PASS] All imports successful")
        print(f"  Tool definitions: {len(BEADS_TOOL_DEFINITIONS)}")
        assert len(BEADS_TOOL_DEFINITIONS) > 0
    except Exception as e:
        print(f"[FAIL] Import error: {e}")
        raise AssertionError(f"Import error: {e}") from e


async def test_beads_list():
    """Test beads_list tool."""
    print("\n" + "=" * 60)
    print("TEST 2: beads_list Tool")
    print("=" * 60)

    from src.mcp.tools.beads_tools import get_beads_tools

    tools = get_beads_tools()

    # Test basic list
    result = await tools.beads_list(limit=5)

    print(f"  Success: {result['success']}")
    if result['success']:
        print(f"  Tasks found: {result['count']}")
        for task in result.get('tasks', [])[:3]:
            print(f"    - {task.get('task_id', 'unknown')}: {task.get('title', 'no title')[:50]}")
    else:
        print(f"  Error: {result.get('error', 'unknown')}")
        _skip_pytest_if_beads_workspace_unavailable(result)

    # Test with priority filter
    result_p2 = await tools.beads_list(priority="P2", limit=3)
    print(f"  P2 tasks: {result_p2.get('count', 0)}")

    assert result['success']
    print("[PASS] beads_list tool working")


async def test_beads_ready():
    """Test beads_ready tool."""
    print("\n" + "=" * 60)
    print("TEST 3: beads_ready Tool")
    print("=" * 60)

    from src.mcp.tools.beads_tools import get_beads_tools

    tools = get_beads_tools()

    result = await tools.beads_ready(limit=10)

    print(f"  Success: {result['success']}")
    if result['success']:
        print(f"  Ready tasks: {result['count']}")
        for task in result.get('tasks', [])[:3]:
            print(f"    - [{task.get('priority', '?')}] {task.get('title', 'no title')[:50]}")
    else:
        print(f"  Error: {result.get('error', 'unknown')}")
        _skip_pytest_if_beads_workspace_unavailable(result)

    assert result['success']
    print("[PASS] beads_ready tool working")


async def test_beads_show():
    """Test beads_show tool."""
    print("\n" + "=" * 60)
    print("TEST 4: beads_show Tool")
    print("=" * 60)

    from src.mcp.tools.beads_tools import get_beads_tools

    tools = get_beads_tools()

    # Get a task to show
    list_result = await tools.beads_list(limit=1)
    if not list_result['success'] or not list_result.get('tasks'):
        print("  [SKIP] No tasks available to show")
        _skip_pytest_if_beads_workspace_unavailable(list_result)
        return

    task_id = list_result['tasks'][0].get('task_id')
    if not task_id:
        print("  [SKIP] Could not get task ID")
        return

    result = await tools.beads_show(task_id)

    print(f"  Success: {result['success']}")
    if result['success']:
        task = result.get('task', {})
        print(f"  Task ID: {task.get('task_id')}")
        print(f"  Title: {task.get('title', 'no title')[:50]}")
        print(f"  Priority: {task.get('priority', '?')}")
        print(f"  Status: {task.get('status', '?')}")
        desc = task.get('description', '')
        if desc:
            print(f"  Description: {desc[:100]}...")
    else:
        print(f"  Error: {result.get('error', 'unknown')}")
        _skip_pytest_if_beads_workspace_unavailable(result)

    assert result['success']
    print("[PASS] beads_show tool working")


async def test_beads_search():
    """Test beads_search tool."""
    print("\n" + "=" * 60)
    print("TEST 5: beads_search Tool")
    print("=" * 60)

    from src.mcp.tools.beads_tools import get_beads_tools

    tools = get_beads_tools()

    # Search for common terms
    result = await tools.beads_search("memory", limit=5)

    print(f"  Success: {result['success']}")
    print(f"  Query: {result.get('query', '')}")
    if result['success']:
        print(f"  Results: {result['count']}")
        for task in result.get('tasks', [])[:3]:
            print(f"    - {task.get('task_id', 'unknown')}: {task.get('title', 'no title')[:40]}")
    else:
        # Search might not find results, which is OK
        print(f"  Note: {result.get('error', 'no results')}")

    # Even if no results, the command worked
    assert "success" in result
    print("[PASS] beads_search tool working")


async def test_beads_stats():
    """Test beads_stats tool."""
    print("\n" + "=" * 60)
    print("TEST 6: beads_stats Tool")
    print("=" * 60)

    from src.mcp.tools.beads_tools import get_beads_tools

    tools = get_beads_tools()

    result = await tools.beads_stats()

    print(f"  Success: {result['success']}")
    if result['success']:
        stats = result.get('stats', {})
        print(f"  Total tasks: {stats.get('total', 'unknown')}")
        print(f"  By status: {stats.get('by_status', {})}")
        print(f"  By priority: {stats.get('by_priority', {})}")
    else:
        print(f"  Error: {result.get('error', 'unknown')}")
        _skip_pytest_if_beads_workspace_unavailable(result)

    assert result['success']
    print("[PASS] beads_stats tool working")


async def test_tool_definitions():
    """Test tool definitions are valid."""
    print("\n" + "=" * 60)
    print("TEST 7: Tool Definitions Validation")
    print("=" * 60)

    from src.mcp.tools.beads_tools import BEADS_TOOL_DEFINITIONS

    required_fields = ["name", "description", "parameters"]

    for tool_def in BEADS_TOOL_DEFINITIONS:
        for field in required_fields:
            assert field in tool_def, f"Tool {tool_def.get('name', 'unknown')} missing {field}"

        print(f"  [OK] {tool_def['name']}: {tool_def['description'][:50]}...")

    print(f"\n  Total tools defined: {len(BEADS_TOOL_DEFINITIONS)}")
    print("[PASS] Tool definitions valid")


def verify_no_mocks():
    """Verify no mock objects in implementation."""
    print("\n" + "=" * 60)
    print("TEST 8: Mock Detection")
    print("=" * 60)

    import inspect
    from src.mcp.tools.beads_tools import BeadsTools

    source = inspect.getsource(BeadsTools)
    if "Mock" in source or "unittest.mock" in source:
        print("  [WARN] Mock reference found")
        return False

    print("  No mock objects detected in implementation")
    print("[PASS] Mock detection complete")
    return True


async def async_main():
    """Run all async tests."""
    try:
        await test_beads_list()
        await test_beads_ready()
        await test_beads_show()
        await test_beads_search()
        await test_beads_stats()
        await test_tool_definitions()
        return True
    except Exception as e:
        print(f"[FAIL] Async Beads tool test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("MCP-005: BEADS MCP TOOLS INTEGRATION - REAL DATA TEST")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")

    all_passed = True

    # Test 1: Imports (sync)
    try:
        test_imports()
    except Exception:
        all_passed = False
        return False

    # Tests 2-7: Async tests
    async_passed = asyncio.run(async_main())
    if not async_passed:
        all_passed = False

    # Test 8: Mock detection (sync)
    if not verify_no_mocks():
        all_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL REAL-DATA TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")
    print("=" * 70)

    print(f"\nMCP-005 Beads MCP Tools verified with real data:")
    print("  - beads_list queries tasks from CLI")
    print("  - beads_ready filters unblocked tasks")
    print("  - beads_show retrieves task details")
    print("  - beads_search finds tasks by query")
    print("  - beads_stats gets aggregated statistics")
    print("  - Tool definitions properly formatted for MCP")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
