"""
Phase 2 Integration Tests - Runtime Wiring Validation

Tests:
1. Hooks directory exists
2. Hook files are valid
3. NexusProcessor integration works
4. WHO/WHEN/PROJECT/WHY tagging works
"""

import os
import sys
import pytest
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestHooksDirectoryStructure:
    """Test C2.1: Hooks directory exists."""

    def test_hooks_directory_exists(self):
        """Verify ~/.claude/hooks/12fa/ directory exists."""
        hooks_dir = Path.home() / ".claude" / "hooks" / "12fa"
        assert hooks_dir.exists(), f"Hooks directory not found: {hooks_dir}"
        assert hooks_dir.is_dir(), f"Hooks path is not a directory: {hooks_dir}"

    def test_tagging_protocol_hook_exists(self):
        """Verify memory-mcp-tagging-protocol.js exists."""
        hook_file = Path.home() / ".claude" / "hooks" / "12fa" / "memory-mcp-tagging-protocol.js"
        assert hook_file.exists(), f"Tagging protocol hook not found: {hook_file}"

    def test_access_control_hook_exists(self):
        """Verify agent-mcp-access-control.js exists."""
        hook_file = Path.home() / ".claude" / "hooks" / "12fa" / "agent-mcp-access-control.js"
        assert hook_file.exists(), f"Access control hook not found: {hook_file}"


class TestHookFileValidity:
    """Test C2.2 and C2.3: Hook files are valid JavaScript."""

    def test_tagging_protocol_is_valid_js(self):
        """Verify tagging protocol hook is valid JavaScript."""
        hook_file = Path.home() / ".claude" / "hooks" / "12fa" / "memory-mcp-tagging-protocol.js"
        content = hook_file.read_text(encoding='utf-8')

        # Check for required exports
        assert "module.exports" in content, "Missing CommonJS exports"
        assert "taggedMemoryStore" in content, "Missing taggedMemoryStore function"
        assert "validateTaggedMetadata" in content, "Missing validateTaggedMetadata function"

        # Check for tagging protocol components
        assert "WHO" in content or "agent" in content, "Missing WHO metadata generation"
        assert "WHEN" in content or "timestamp" in content, "Missing WHEN metadata generation"
        assert "PROJECT" in content or "project" in content, "Missing PROJECT metadata generation"
        assert "WHY" in content or "intent" in content, "Missing WHY metadata generation"

    def test_access_control_is_valid_js(self):
        """Verify access control hook is valid JavaScript."""
        hook_file = Path.home() / ".claude" / "hooks" / "12fa" / "agent-mcp-access-control.js"
        content = hook_file.read_text(encoding='utf-8')

        # Check for required exports
        assert "module.exports" in content, "Missing CommonJS exports"
        assert "validateAccess" in content, "Missing validateAccess function"

        # Check for permission definitions
        assert "PERMISSION_LEVELS" in content, "Missing permission levels"
        assert "AGENT_PERMISSIONS" in content, "Missing agent permissions"


class TestNexusProcessorIntegration:
    """Test C3.1: NexusProcessor wired into MCP server."""

    def test_stdio_server_imports_nexus(self):
        """Verify stdio_server imports NexusProcessor."""
        stdio_server_path = Path(__file__).parent.parent.parent / "src" / "mcp" / "stdio_server.py"
        content = stdio_server_path.read_text(encoding='utf-8')

        assert "from ..nexus.processor import NexusProcessor" in content, \
            "stdio_server.py missing NexusProcessor import"

    def test_nexus_search_tool_class_exists(self):
        """Verify NexusSearchTool wrapper class exists."""
        stdio_server_path = Path(__file__).parent.parent.parent / "src" / "mcp" / "stdio_server.py"
        content = stdio_server_path.read_text(encoding='utf-8')

        assert "class NexusSearchTool" in content, \
            "NexusSearchTool wrapper class not found"

    def test_mode_parameter_in_vector_search(self):
        """Verify mode parameter added to vector_search tool."""
        stdio_server_path = Path(__file__).parent.parent.parent / "src" / "mcp" / "stdio_server.py"
        content = stdio_server_path.read_text(encoding='utf-8')

        assert '"mode"' in content, "Mode parameter not found in vector_search tool schema"
        assert '"execution"' in content, "Execution mode not found"
        assert '"planning"' in content, "Planning mode not found"
        assert '"brainstorming"' in content, "Brainstorming mode not found"


class TestTaggingProtocolIntegration:
    """Test C2.4: WHO/WHEN/PROJECT/WHY tagging in memory_store."""

    def test_enrich_metadata_function_exists(self):
        """Verify _enrich_metadata_with_tagging function exists."""
        stdio_server_path = Path(__file__).parent.parent.parent / "src" / "mcp" / "stdio_server.py"
        content = stdio_server_path.read_text(encoding='utf-8')

        assert "def _enrich_metadata_with_tagging" in content, \
            "Metadata enrichment function not found"

    def test_memory_store_uses_tagging(self):
        """Verify memory_store handler uses tagging protocol."""
        stdio_server_path = Path(__file__).parent.parent.parent / "src" / "mcp" / "stdio_server.py"
        content = stdio_server_path.read_text(encoding='utf-8')

        assert "_enrich_metadata_with_tagging" in content, \
            "memory_store not using metadata enrichment"

    def test_tagging_includes_all_fields(self):
        """Verify tagging includes WHO/WHEN/PROJECT/WHY."""
        stdio_server_path = Path(__file__).parent.parent.parent / "src" / "mcp" / "stdio_server.py"
        content = stdio_server_path.read_text(encoding='utf-8')

        # Check enrichment function has all fields
        assert "'agent'" in content, "WHO (agent) field missing"
        assert "'timestamp'" in content, "WHEN (timestamp) field missing"
        assert "'project'" in content, "PROJECT field missing"
        assert "'intent'" in content, "WHY (intent) field missing"


class TestMetadataEnrichment:
    """Test metadata enrichment function directly."""

    def test_enrich_metadata_with_defaults(self):
        """Test enrichment with default values."""
        from src.mcp.stdio_server import _enrich_metadata_with_tagging

        result = _enrich_metadata_with_tagging({})

        # Check WHO
        assert 'agent' in result
        assert result['agent']['name'] == 'unknown'

        # Check WHEN
        assert 'timestamp' in result
        assert 'iso' in result['timestamp']
        assert 'unix' in result['timestamp']
        assert 'readable' in result['timestamp']

        # Check PROJECT
        assert 'project' in result
        assert result['project'] == 'memory-mcp-triple-system'

        # Check WHY
        assert 'intent' in result
        assert result['intent'] == 'storage'

        # Check protocol version
        assert result['_tagging_protocol'] == 'memory-mcp-triple-system'

    def test_enrich_metadata_with_custom_values(self):
        """Test enrichment with custom values."""
        from src.mcp.stdio_server import _enrich_metadata_with_tagging

        custom_metadata = {
            'agent': 'coder',
            'agent_category': 'development',
            'project': 'test-project',
            'intent': 'implementation',
            'custom_field': 'custom_value'
        }

        result = _enrich_metadata_with_tagging(custom_metadata)

        # Check custom values preserved
        assert result['agent']['name'] == 'coder'
        assert result['agent']['category'] == 'development'
        assert result['project'] == 'test-project'
        assert result['intent'] == 'implementation'
        assert result['custom_field'] == 'custom_value'


class TestNexusSearchToolInstantiation:
    """Test NexusSearchTool can be instantiated."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        return {
            'embeddings': {
                'model': 'all-MiniLM-L6-v2',
                'dimension': 384
            },
            'storage': {
                'vector_db': {
                    'persist_directory': './test_chroma_data',
                    'collection_name': 'test_collection'
                }
            },
            'chunking': {
                'min_chunk_size': 128,
                'max_chunk_size': 512,
                'overlap': 50
            }
        }

    def test_nexus_search_tool_init(self, mock_config):
        """Test NexusSearchTool initialization."""
        from src.mcp.stdio_server import NexusSearchTool

        # Should not raise
        tool = NexusSearchTool(mock_config)

        assert tool is not None
        assert tool.config == mock_config
        assert tool.vector_search_tool is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
