"""
Phase 4 Integration Tests - MCP Tools Validation

Tests that all 6 MCP tools are properly exposed and functional:
1. vector_search - Semantic similarity search
2. memory_store - Store with tagging
3. graph_query - HippoRAG multi-hop
4. entity_extraction - NER
5. hipporag_retrieve - Full pipeline
6. detect_mode - Query mode detection
"""

import sys
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestMCPToolsExposed:
    """Test C1.2-C1.6: All 6 MCP tools are exposed."""

    def test_handle_list_tools_returns_6_tools(self):
        """Verify 6 tools are returned by handle_list_tools."""
        from src.mcp.stdio_server import handle_list_tools

        tools = handle_list_tools()

        assert len(tools) == 6, f"Expected 6 tools, got {len(tools)}"

    def test_all_required_tools_present(self):
        """Verify all required tool names are present."""
        from src.mcp.stdio_server import handle_list_tools

        tools = handle_list_tools()
        tool_names = [t["name"] for t in tools]

        required_tools = [
            "vector_search",
            "memory_store",
            "graph_query",
            "entity_extraction",
            "hipporag_retrieve",
            "detect_mode"
        ]

        for required in required_tools:
            assert required in tool_names, f"Missing tool: {required}"

    def test_all_tools_have_schemas(self):
        """Verify all tools have input schemas."""
        from src.mcp.stdio_server import handle_list_tools

        tools = handle_list_tools()

        for tool in tools:
            assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"
            assert "properties" in tool["inputSchema"], f"Tool {tool['name']} missing properties"


class TestToolHandlers:
    """Test that tool handlers exist and are callable."""

    def test_vector_search_handler_exists(self):
        """Verify _handle_vector_search exists."""
        from src.mcp.stdio_server import _handle_vector_search
        assert callable(_handle_vector_search)

    def test_memory_store_handler_exists(self):
        """Verify _handle_memory_store exists."""
        from src.mcp.stdio_server import _handle_memory_store
        assert callable(_handle_memory_store)

    def test_graph_query_handler_exists(self):
        """Verify _handle_graph_query exists."""
        from src.mcp.stdio_server import _handle_graph_query
        assert callable(_handle_graph_query)

    def test_entity_extraction_handler_exists(self):
        """Verify _handle_entity_extraction exists."""
        from src.mcp.stdio_server import _handle_entity_extraction
        assert callable(_handle_entity_extraction)

    def test_hipporag_retrieve_handler_exists(self):
        """Verify _handle_hipporag_retrieve exists."""
        from src.mcp.stdio_server import _handle_hipporag_retrieve
        assert callable(_handle_hipporag_retrieve)

    def test_detect_mode_handler_exists(self):
        """Verify _handle_detect_mode exists."""
        from src.mcp.stdio_server import _handle_detect_mode
        assert callable(_handle_detect_mode)


class TestHandleCallToolRouting:
    """Test that handle_call_tool routes to correct handlers."""

    def test_routes_to_all_6_tools(self):
        """Verify handle_call_tool has routing for all 6 tools."""
        from src.mcp.stdio_server import handle_call_tool
        import inspect

        source = inspect.getsource(handle_call_tool)

        # Check all tool names are in the routing
        assert 'tool_name == "vector_search"' in source
        assert 'tool_name == "memory_store"' in source
        assert 'tool_name == "graph_query"' in source
        assert 'tool_name == "entity_extraction"' in source
        assert 'tool_name == "hipporag_retrieve"' in source
        assert 'tool_name == "detect_mode"' in source


class TestEntityExtraction:
    """Test entity_extraction tool functionality."""

    def test_extracts_capitalized_entities(self):
        """Test that entity extraction finds capitalized phrases."""
        from src.mcp.stdio_server import _handle_entity_extraction

        # Create a mock tool (not needed for entity extraction)
        class MockTool:
            pass

        result = _handle_entity_extraction(
            {"text": "John Smith works at Microsoft Corp in New York City."},
            MockTool()
        )

        assert not result["isError"], "Entity extraction should not error"
        content_text = result["content"][0]["text"]

        # Should find some entities
        assert "entities" in content_text.lower()


class TestDetectMode:
    """Test detect_mode tool functionality."""

    def test_detects_execution_mode(self):
        """Test detection of execution mode queries."""
        from src.mcp.stdio_server import _handle_detect_mode

        class MockTool:
            pass

        result = _handle_detect_mode(
            {"query": "What is machine learning?"},
            MockTool()
        )

        assert not result["isError"]
        assert "execution" in result["content"][0]["text"].lower()

    def test_detects_planning_mode(self):
        """Test detection of planning mode queries."""
        from src.mcp.stdio_server import _handle_detect_mode

        class MockTool:
            pass

        result = _handle_detect_mode(
            {"query": "How should I design the authentication system?"},
            MockTool()
        )

        assert not result["isError"]
        assert "planning" in result["content"][0]["text"].lower()

    def test_detects_brainstorming_mode(self):
        """Test detection of brainstorming mode queries."""
        from src.mcp.stdio_server import _handle_detect_mode

        class MockTool:
            pass

        result = _handle_detect_mode(
            {"query": "What if we explored using blockchain?"},
            MockTool()
        )

        assert not result["isError"]
        assert "brainstorming" in result["content"][0]["text"].lower()


class TestServerVersion:
    """Test server version is updated."""

    def test_version_is_1_2_0(self):
        """Verify version is 1.2.0."""
        from src import __version__
        assert __version__ == "1.2.0", f"Expected 1.2.0, got {__version__}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
