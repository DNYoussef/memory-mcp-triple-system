#!/usr/bin/env python3
"""
Test script for RLM Phase 2 implementations.

Tests:
- RLM-004: Trajectory logging
- RLM-005: Memory MCP export to RLM format
- RLM-009: Codebase environment for AI Exoskeleton projects
"""

import sys
import os
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_rlm004_trajectory_logging():
    """Test RLM-004: Trajectory logging."""
    print("Test 1: RLM-004 - Trajectory Logging")
    try:
        from src.rlm.logger import (
            RLMLogger,
            TrajectoryEvent,
            TrajectoryEventType,
            TrajectoryStats,
        )

        # Create logger with temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = RLMLogger(output_dir=tmpdir, session_id="test_session")

            # Start a trace
            trace_id = logger.start_trace("What files handle errors?")
            assert trace_id.startswith("trace_")

            # Log events
            logger.log_search("error handling", depth=1, result_count=5)
            logger.log_recurse("specific error types", depth=2)
            logger.log_search("exception handling", depth=2, result_count=3)
            logger.log_cost(tokens=1000, cost_usd=0.003, depth=2)

            # End trace
            logger.end_trace(result={"files": ["error.py", "handler.py"]}, tokens=1500)

            # Check stats
            stats = logger.get_stats()
            assert stats.total_events >= 5
            assert stats.max_depth == 2
            assert stats.total_searches == 2
            assert stats.total_recurses == 1

            # Check JSONL file exists
            log_files = list(Path(tmpdir).glob("*.jsonl"))
            assert len(log_files) == 1

            # Check visualizer URL
            url = logger.get_visualizer_url()
            assert "localhost:3001" in url

            logger.close()

        print("  [PASS] Trajectory logging works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rlm005_memory_environment():
    """Test RLM-005: Memory MCP export to RLM format."""
    print("Test 2: RLM-005 - Memory MCP Environment")
    try:
        from src.rlm.rlm_memory_env import (
            RLMMemoryEnvironment,
            MemoryChunk,
        )
        from src.rlm import RLMConfig

        # Create environment (may not have actual data)
        config = RLMConfig(max_depth=5)
        env = RLMMemoryEnvironment(config=config)

        # Check methods exist
        assert hasattr(env, "load_data")
        assert hasattr(env, "search")
        assert hasattr(env, "get_chunk")
        assert hasattr(env, "search_by_namespace")
        assert hasattr(env, "get_graph_neighbors")
        assert hasattr(env, "export_to_jsonl")

        # Test MemoryChunk
        chunk = MemoryChunk(
            id="test:chunk:001",
            content="Test content for memory chunk",
            namespace="test",
            source="kv",
            score=0.85
        )
        chunk_dict = chunk.to_dict()
        assert chunk_dict["id"] == "test:chunk:001"
        assert chunk_dict["namespace"] == "test"
        assert chunk_dict["score"] == 0.85

        # Try to load data (may not have files)
        env.load_data("all")

        # Check stats
        stats = env.get_stats()
        assert "kv_count" in stats
        assert "graph_nodes" in stats
        assert "loaded" in stats

        # Test search (even with empty data)
        results = env.search("test query", limit=5)
        assert isinstance(results, list)

        print("  [PASS] Memory MCP environment works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rlm009_codebase_environment():
    """Test RLM-009: Codebase environment for AI Exoskeleton."""
    print("Test 3: RLM-009 - Codebase Environment")
    try:
        from src.rlm.rlm_codebase_env import (
            RLMCodebaseEnvironment,
            CodeFile,
            AI_EXOSKELETON_PROJECTS,
            LANGUAGE_EXTENSIONS,
        )
        from src.rlm import RLMConfig

        # Check project list
        assert "memory-mcp" in AI_EXOSKELETON_PROJECTS
        assert "context-cascade" in AI_EXOSKELETON_PROJECTS
        assert len(AI_EXOSKELETON_PROJECTS) >= 10

        # Check language extensions
        assert "python" in LANGUAGE_EXTENSIONS
        assert ".py" in LANGUAGE_EXTENSIONS["python"]

        # Test CodeFile
        code_file = CodeFile(
            path="/test/path/file.py",
            project="test-project",
            language="python",
            size_bytes=1024,
            modified="2026-01-20T12:00:00"
        )
        file_dict = code_file.to_dict()
        assert file_dict["language"] == "python"
        assert file_dict["project"] == "test-project"

        # Create environment
        config = RLMConfig(max_depth=10)
        env = RLMCodebaseEnvironment(config=config)

        # Check methods exist
        assert hasattr(env, "load_data")
        assert hasattr(env, "search")
        assert hasattr(env, "get_chunk")
        assert hasattr(env, "search_content")
        assert hasattr(env, "get_project_stats")
        assert hasattr(env, "list_projects")
        assert hasattr(env, "export_index")

        # Index just the memory-mcp project (smaller test)
        success = env.load_data("memory-mcp")
        assert success, "Failed to load memory-mcp project"

        # Check stats
        stats = env.get_stats()
        assert stats["total_files"] > 0
        assert stats["indexed"] == True

        # Test search
        results = env.search("rlm", limit=5)
        assert isinstance(results, list)
        if results:
            assert "path" in results[0]
            assert "project" in results[0]

        # Test project stats
        project_stats = env.get_project_stats("memory-mcp")
        assert "file_count" in project_stats
        assert project_stats["file_count"] > 0

        print(f"  Indexed {stats['total_files']} files in memory-mcp")
        print("  [PASS] Codebase environment works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rlm_module_imports():
    """Test all RLM module imports."""
    print("Test 4: RLM Module Imports")
    try:
        from src.rlm import (
            # Base
            RLMEnvironment,
            RLMConfig,
            RLMResult,
            ExecutionContext,
            # Cost
            CostTracker,
            CostConfig,
            # Logger (RLM-004)
            RLMLogger,
            TrajectoryEvent,
            TrajectoryEventType,
            TrajectoryStats,
            # Memory (RLM-005)
            RLMMemoryEnvironment,
            MemoryChunk,
            # Codebase (RLM-009)
            RLMCodebaseEnvironment,
            CodeFile,
            AI_EXOSKELETON_PROJECTS,
        )

        from src import rlm
        assert rlm.__version__ == "0.2.0"

        print("  [PASS] All RLM module imports work correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rlm_integration():
    """Test RLM components integration."""
    print("Test 5: RLM Integration")
    try:
        from src.rlm import (
            RLMCodebaseEnvironment,
            RLMLogger,
            CostTracker,
            CostConfig,
            RLMConfig,
        )
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            config = RLMConfig(max_depth=5)
            cost_config = CostConfig(max_recursion_depth=5)
            tracker = CostTracker(cost_config)
            rlm_logger = RLMLogger(output_dir=tmpdir)

            # Create codebase env
            env = RLMCodebaseEnvironment(config=config)
            env.load_data("memory-mcp")

            # Simulate recursive search with logging
            trace_id = rlm_logger.start_trace("Find RLM files")

            for depth in range(3):
                tracker.check_recursion(depth)
                tracker.record_cost(f"search_{depth}", 200)
                rlm_logger.log_search(f"query_{depth}", depth=depth, result_count=5)

            rlm_logger.end_trace(result={"found": 15})

            # Check integration worked
            stats = rlm_logger.get_stats()
            assert stats.total_searches == 3

            cost_stats = tracker.get_stats()
            assert cost_stats["operations_count"] == 3

            rlm_logger.close()

        print("  [PASS] RLM integration works correctly")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("TESTING RLM PHASE 2 IMPLEMENTATIONS")
    print("=" * 60)
    print()

    results = []

    results.append(("RLM-004", test_rlm004_trajectory_logging()))
    print()

    results.append(("RLM-005", test_rlm005_memory_environment()))
    print()

    results.append(("RLM-009", test_rlm009_codebase_environment()))
    print()

    results.append(("Imports", test_rlm_module_imports()))
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
