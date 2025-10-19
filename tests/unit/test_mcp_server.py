"""
Unit tests for MCP Server
Following TDD (London School) with proper test structure.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from src.mcp.server import create_app, load_config


class TestMCPServer:
    """Test suite for MCP Server."""

    @pytest.fixture
    def mock_tool(self):
        """Create mock VectorSearchTool."""
        mock = MagicMock()
        mock.check_services.return_value = {
            'qdrant': 'available',
            'embeddings': 'available'
        }
        return mock

    @pytest.fixture
    def app(self, mock_tool):
        """Create test app instance."""
        with patch('src.mcp.server.VectorSearchTool', return_value=mock_tool):
            return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_app_creation(self, app):
        """Test app is created successfully."""
        assert app is not None
        assert app.title == "Memory MCP Triple System"
        assert app.version == "1.0.0"

    def test_health_endpoint_exists(self, client):
        """Test health endpoint is available."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_structure(self, client):
        """Test health endpoint returns correct structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "services" in data
        assert isinstance(data["services"], dict)

    def test_tools_endpoint_exists(self, client):
        """Test tools list endpoint is available."""
        response = client.get("/tools")
        assert response.status_code == 200

    def test_tools_endpoint_lists_vector_search(self, client):
        """Test vector_search tool is listed."""
        response = client.get("/tools")
        data = response.json()

        assert "tools" in data
        tools = data["tools"]
        assert len(tools) > 0

        tool_names = [t["name"] for t in tools]
        assert "vector_search" in tool_names

    def test_vector_search_tool_definition(self, client):
        """Test vector_search tool has proper definition."""
        response = client.get("/tools")
        tools = response.json()["tools"]

        vector_search = next(t for t in tools if t["name"] == "vector_search")
        assert "description" in vector_search
        assert "parameters" in vector_search
        assert "query" in vector_search["parameters"]
        assert "limit" in vector_search["parameters"]

    def test_load_config(self):
        """Test configuration loading."""
        config = load_config()

        assert config is not None
        assert "storage" in config
        assert "embeddings" in config
        assert "mcp" in config


class TestMCPServerIntegration:
    """Integration tests for MCP server (requires mocked services)."""

    @pytest.fixture
    def mock_vector_search_tool(self):
        """Create mock VectorSearchTool."""
        mock_tool = MagicMock()
        mock_tool.check_services.return_value = {
            'qdrant': 'available',
            'embeddings': 'available'
        }
        mock_tool.execute.return_value = [
            {
                'text': 'Test result',
                'file_path': '/test/file.md',
                'chunk_index': 0,
                'score': 0.95,
                'metadata': {}
            }
        ]
        return mock_tool

    @pytest.fixture
    def app_with_mock_tool(self, mock_vector_search_tool):
        """Create app with mocked vector search tool."""
        with patch('src.mcp.server.VectorSearchTool', return_value=mock_vector_search_tool):
            return create_app()

    @pytest.fixture
    def client_with_mock(self, app_with_mock_tool):
        """Create client with mocked services."""
        return TestClient(app_with_mock_tool)

    def test_health_check_all_services_available(self, client_with_mock):
        """Test health check when all services available."""
        response = client_with_mock.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert data["services"]["qdrant"] == "available"
        assert data["services"]["embeddings"] == "available"

    def test_vector_search_endpoint_success(self, client_with_mock):
        """Test vector search endpoint with successful query."""
        response = client_with_mock.post(
            "/tools/vector_search",
            params={"query": "test query", "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0

    def test_vector_search_default_limit(self, client_with_mock):
        """Test vector search uses default limit."""
        response = client_with_mock.post(
            "/tools/vector_search",
            params={"query": "test query"}
        )

        assert response.status_code == 200
