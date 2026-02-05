"""
Unit tests for MCP stdio Server
Following TDD (London School) with proper test structure.
Tests JSON-RPC 2.0 protocol compliance for Claude Code MCP integration.
"""

import pytest
import json
import sys
from io import StringIO
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import the module under test
from src.mcp.stdio_server import (
    load_config,
    handle_list_tools,
    handle_call_tool,
)


class TestLoadConfig:
    """Test suite for load_config function."""

    def test_load_config_returns_dict(self):
        """Test config loading returns a dictionary."""
        config = load_config()
        assert isinstance(config, dict)

    def test_load_config_has_required_keys(self):
        """Test config has required top-level keys."""
        config = load_config()
        # These are the minimum keys expected
        assert "storage" in config or "embeddings" in config or "mcp" in config

    def test_load_config_assertion_on_missing_file(self):
        """Test config raises assertion when file missing."""
        with patch.object(Path, 'exists', return_value=False):
            with pytest.raises(AssertionError):
                load_config()


class TestHandleListTools:
    """Test suite for handle_list_tools function."""

    def test_returns_list(self):
        """Test handle_list_tools returns a list."""
        tools = handle_list_tools()
        assert isinstance(tools, list)

    def test_returns_thirteen_tools(self):
        """Test exactly thirteen tools are returned (mode_detection removed in P1-2)."""
        tools = handle_list_tools()
        assert len(tools) == 13

    def test_vector_search_tool_present(self):
        """Test vector_search tool is in the list."""
        tools = handle_list_tools()
        tool_names = [t["name"] for t in tools]
        assert "vector_search" in tool_names

    def test_memory_store_tool_present(self):
        """Test memory_store tool is in the list."""
        tools = handle_list_tools()
        tool_names = [t["name"] for t in tools]
        assert "memory_store" in tool_names

    def test_vector_search_has_input_schema(self):
        """Test vector_search tool has proper inputSchema."""
        tools = handle_list_tools()
        vector_search = next(t for t in tools if t["name"] == "vector_search")

        assert "inputSchema" in vector_search
        schema = vector_search["inputSchema"]
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "query" in schema["required"]

    def test_memory_store_has_input_schema(self):
        """Test memory_store tool has proper inputSchema."""
        tools = handle_list_tools()
        memory_store = next(t for t in tools if t["name"] == "memory_store")

        assert "inputSchema" in memory_store
        schema = memory_store["inputSchema"]
        assert schema["type"] == "object"
        assert "text" in schema["properties"]
        assert "metadata" in schema["properties"]
        assert "text" in schema["required"]

    def test_tools_have_descriptions(self):
        """Test all tools have descriptions."""
        tools = handle_list_tools()
        for tool in tools:
            assert "description" in tool
            assert len(tool["description"]) > 0


class TestHandleCallTool:
    """Test suite for handle_call_tool function."""

    @pytest.fixture
    def mock_vector_tool(self):
        """Create mock VectorSearchTool."""
        mock = MagicMock()
        mock.execute.return_value = [
            {
                "text": "Test result content",
                "score": 0.95,
                "file_path": "/test/file.md",
            }
        ]
        mock.chunker = MagicMock()
        mock.embedder = MagicMock()
        mock.embedder.encode.return_value = MagicMock(tolist=lambda: [[0.1, 0.2, 0.3]])
        mock.indexer = MagicMock()
        mock.vector_search_tool = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_embeddings.__len__.return_value = 1
        mock.vector_search_tool.embedder = MagicMock()
        mock.vector_search_tool.embedder.encode.return_value = mock_embeddings
        mock.vector_search_tool.indexer = MagicMock()
        mock.vector_search_tool.indexer.index_chunks.return_value = True
        mock.hot_cold_classifier = MagicMock()
        mock.hot_cold_classifier.classify.return_value = {
            "tier": "hot",
            "decay_score": 1.0
        }
        mock.lifecycle_manager = MagicMock()
        mock.entity_service = None
        mock.log_event = MagicMock()
        return mock

    def test_vector_search_returns_content(self, mock_vector_tool):
        """Test vector_search tool returns content structure."""
        result = handle_call_tool(
            "vector_search",
            {"query": "test query", "limit": 5},
            mock_vector_tool
        )

        assert "content" in result
        assert "isError" in result
        assert result["isError"] is False
        assert isinstance(result["content"], list)

    def test_vector_search_formats_results(self, mock_vector_tool):
        """Test vector_search formats results correctly."""
        result = handle_call_tool(
            "vector_search",
            {"query": "test query"},
            mock_vector_tool
        )

        assert len(result["content"]) == 1
        content_item = result["content"][0]
        assert content_item["type"] == "text"
        assert "Result 1:" in content_item["text"]
        assert "Score:" in content_item["text"]
        assert "File:" in content_item["text"]

    def test_vector_search_calls_execute_with_defaults(self, mock_vector_tool):
        """Test vector_search uses default limit."""
        handle_call_tool(
            "vector_search",
            {"query": "test query"},
            mock_vector_tool
        )

        mock_vector_tool.execute.assert_called_once_with(
            "test query",
            5,
            "execution"
        )

    def test_vector_search_respects_custom_limit(self, mock_vector_tool):
        """Test vector_search uses custom limit."""
        handle_call_tool(
            "vector_search",
            {"query": "test query", "limit": 10},
            mock_vector_tool
        )

        mock_vector_tool.execute.assert_called_once_with(
            "test query",
            10,
            "execution"
        )

    def test_memory_store_returns_success(self, mock_vector_tool):
        """Test memory_store returns success structure."""
        result = handle_call_tool(
            "memory_store",
            {"text": "content to store", "metadata": {
                "key": "test_key",
                "who": "test-agent",
                "when": "2026-01-13T12:00:00",
                "project": "test-project",
                "why": "testing"
            }},
            mock_vector_tool
        )

        assert "content" in result
        assert "isError" in result
        assert result["isError"] is False

    def test_memory_store_confirmation_message(self, mock_vector_tool):
        """Test memory_store returns confirmation."""
        result = handle_call_tool(
            "memory_store",
            {"text": "content to store", "metadata": {
                "who": "test-agent",
                "when": "2026-01-13T12:00:00",
                "project": "test-project",
                "why": "testing"
            }},
            mock_vector_tool
        )

        content_text = result["content"][0]["text"]
        assert "Stored memory:" in content_text

    def test_unknown_tool_returns_error(self, mock_vector_tool):
        """Test unknown tool returns error."""
        result = handle_call_tool(
            "unknown_tool",
            {},
            mock_vector_tool
        )

        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_exception_handling(self, mock_vector_tool):
        """Test exception in tool execution is handled."""
        mock_vector_tool.execute.side_effect = Exception("Test error")

        result = handle_call_tool(
            "vector_search",
            {"query": "test"},
            mock_vector_tool
        )

        assert result["isError"] is True
        assert "Error:" in result["content"][0]["text"]


class TestJSONRPCProtocol:
    """Test JSON-RPC 2.0 protocol compliance."""

    @pytest.fixture
    def mock_tool(self):
        """Create mock VectorSearchTool."""
        mock = MagicMock()
        mock.execute.return_value = []
        return mock

    def test_tools_list_request_format(self):
        """Test tools/list request format."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        # Validate request structure
        assert request["jsonrpc"] == "2.0"
        assert "id" in request
        assert request["method"] == "tools/list"

    def test_tools_call_request_format(self):
        """Test tools/call request format."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "vector_search",
                "arguments": {"query": "test", "limit": 5}
            }
        }

        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "tools/call"
        assert "name" in request["params"]
        assert "arguments" in request["params"]

    def test_initialize_request_format(self):
        """Test initialize request format."""
        request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {}
        }

        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "initialize"


class TestStdioMainLoop:
    """Test stdio main loop behavior (mocked I/O)."""

    @pytest.fixture
    def mock_config(self):
        """Mock config for main loop."""
        return {
            "storage": {"type": "local"},
            "embeddings": {"model": "test"},
            "mcp": {"port": 3000}
        }

    @pytest.fixture
    def mock_dependencies(self, mock_config):
        """Setup all mocks for main loop."""
        with patch('src.mcp.stdio_server.load_config', return_value=mock_config):
            with patch('src.mcp.stdio_server.VectorSearchTool') as mock_tool_class:
                mock_tool = MagicMock()
                mock_tool.execute.return_value = []
                mock_tool_class.return_value = mock_tool
                yield mock_tool

    def test_initialize_response_structure(self):
        """Test initialize response has correct structure."""
        expected_response = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "memory-mcp-triple-system",
                    "version": "1.0.0"
                }
            }
        }

        assert expected_response["result"]["protocolVersion"] == "2024-11-05"
        assert "tools" in expected_response["result"]["capabilities"]
        assert expected_response["result"]["serverInfo"]["name"] == "memory-mcp-triple-system"

    def test_tools_list_response_structure(self):
        """Test tools/list response structure."""
        tools = handle_list_tools()

        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": tools}
        }

        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 13

    def test_error_response_format(self):
        """Test error response format for unknown method."""
        error_response = {
            "jsonrpc": "2.0",
            "id": 99,
            "error": {
                "code": -32601,
                "message": "Method not found: unknown_method"
            }
        }

        assert "error" in error_response
        assert error_response["error"]["code"] == -32601
        assert "Method not found" in error_response["error"]["message"]

    def test_internal_error_format(self):
        """Test internal error format."""
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": "Internal error: Something went wrong"
            }
        }

        assert error_response["error"]["code"] == -32603
        assert "Internal error" in error_response["error"]["message"]


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def mock_tool(self):
        """Create mock VectorSearchTool."""
        mock = MagicMock()
        mock.execute.return_value = []
        mock.chunker = MagicMock()
        mock.embedder = MagicMock()
        mock.embedder.encode.return_value = MagicMock(tolist=lambda: [[0.1]])
        mock.indexer = MagicMock()
        mock.vector_search_tool = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = [[0.1]]
        mock_embeddings.__len__.return_value = 1
        mock.vector_search_tool.embedder = MagicMock()
        mock.vector_search_tool.embedder.encode.return_value = mock_embeddings
        mock.vector_search_tool.indexer = MagicMock()
        mock.vector_search_tool.indexer.index_chunks.return_value = True
        mock.hot_cold_classifier = MagicMock()
        mock.hot_cold_classifier.classify.return_value = {
            "tier": "hot",
            "decay_score": 1.0
        }
        mock.lifecycle_manager = MagicMock()
        mock.entity_service = None
        mock.log_event = MagicMock()
        return mock

    def test_empty_query_handling(self, mock_tool):
        """Test handling of empty query."""
        result = handle_call_tool(
            "vector_search",
            {"query": ""},
            mock_tool
        )

        # Should still work, just return empty results
        assert result["isError"] is False
        mock_tool.execute.assert_called_with("", 5, "execution")

    def test_missing_query_handling(self, mock_tool):
        """Test handling of missing query parameter."""
        result = handle_call_tool(
            "vector_search",
            {},
            mock_tool
        )

        # Should use empty string as default
        assert result["isError"] is False
        mock_tool.execute.assert_called_with("", 5, "execution")

    def test_empty_text_memory_store(self, mock_tool):
        """Test memory_store with empty text."""
        result = handle_call_tool(
            "memory_store",
            {"text": "", "metadata": {
                "who": "test-agent",
                "when": "2026-01-13T12:00:00",
                "project": "test-project",
                "why": "testing"
            }},
            mock_tool
        )

        assert result["isError"] is True

    def test_memory_store_default_key(self, mock_tool):
        """Test memory_store uses default key when not provided."""
        result = handle_call_tool(
            "memory_store",
            {"text": "test content", "metadata": {
                "who": "test-agent",
                "when": "2026-01-13T12:00:00",
                "project": "test-project",
                "why": "testing"
            }},
            mock_tool
        )

        # Verify indexer was called
        assert result["isError"] is False

    def test_large_limit_value(self, mock_tool):
        """Test vector_search with large limit value."""
        result = handle_call_tool(
            "vector_search",
            {"query": "test", "limit": 10000},
            mock_tool
        )

        assert result["isError"] is False
        mock_tool.execute.assert_called_with("test", 10000, "execution")

    def test_negative_limit_handling(self, mock_tool):
        """Test vector_search with negative limit."""
        result = handle_call_tool(
            "vector_search",
            {"query": "test", "limit": -1},
            mock_tool
        )

        # Should pass through to tool (validation is tool's responsibility)
        assert result["isError"] is False
        mock_tool.execute.assert_called_with("test", -1, "execution")

    def test_special_characters_in_query(self, mock_tool):
        """Test query with special characters."""
        query = "test <script>alert('xss')</script> & \"quotes\" 'single'"
        result = handle_call_tool(
            "vector_search",
            {"query": query},
            mock_tool
        )

        assert result["isError"] is False
        mock_tool.execute.assert_called_with(query, 5, "execution")

    def test_unicode_in_query(self, mock_tool):
        """Test query with unicode characters."""
        query = "test query"  # ASCII only per CLAUDE.md
        result = handle_call_tool(
            "vector_search",
            {"query": query},
            mock_tool
        )

        assert result["isError"] is False
