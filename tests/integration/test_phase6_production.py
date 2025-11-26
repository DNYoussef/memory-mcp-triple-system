"""
Phase 6 Integration Tests - Production Hardening Validation

Tests production features:
1. C3.2: ObsidianClient integration
2. C3.3: Event logging
3. C3.4: KV store
4. C3.5: Lifecycle manager
5. C3.6: Query tracing
6. C3.7: Migration auto-apply
"""

import sys
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestC32ObsidianClient:
    """Test C3.2: ObsidianClient is importable and configured."""

    def test_obsidian_client_imported(self):
        """Verify ObsidianClient is imported in stdio_server."""
        from src.mcp.stdio_server import ObsidianMCPClient
        assert ObsidianMCPClient is not None

    def test_nexus_tool_has_obsidian_property(self, tmp_path):
        """Verify NexusSearchTool has obsidian_client property."""
        from src.mcp.stdio_server import NexusSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': str(tmp_path / 'chroma'),
                    'collection_name': 'test'
                },
                'data_dir': str(tmp_path / 'data')
            }
        }

        tool = NexusSearchTool(config)
        assert hasattr(tool, 'obsidian_client')


class TestC33EventLogging:
    """Test C3.3: Event logging is functional."""

    def test_event_log_initialized(self, tmp_path):
        """Verify EventLog is initialized in NexusSearchTool."""
        from src.mcp.stdio_server import NexusSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': str(tmp_path / 'chroma'),
                    'collection_name': 'test'
                },
                'data_dir': str(tmp_path / 'data')
            }
        }

        tool = NexusSearchTool(config)
        assert hasattr(tool, 'event_log')
        assert tool.event_log is not None

    def test_log_event_method_exists(self, tmp_path):
        """Verify log_event method exists."""
        from src.mcp.stdio_server import NexusSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': str(tmp_path / 'chroma'),
                    'collection_name': 'test'
                },
                'data_dir': str(tmp_path / 'data')
            }
        }

        tool = NexusSearchTool(config)
        assert callable(getattr(tool, 'log_event', None))


class TestC34KVStore:
    """Test C3.4: KV store is functional."""

    def test_kv_store_initialized(self, tmp_path):
        """Verify KVStore is initialized."""
        from src.mcp.stdio_server import NexusSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': str(tmp_path / 'chroma'),
                    'collection_name': 'test'
                },
                'data_dir': str(tmp_path / 'data')
            }
        }

        tool = NexusSearchTool(config)
        assert hasattr(tool, 'kv_store')
        assert tool.kv_store is not None


class TestC35LifecycleManager:
    """Test C3.5: Lifecycle manager is functional."""

    def test_lifecycle_manager_initialized(self, tmp_path):
        """Verify LifecycleManager is initialized."""
        from src.mcp.stdio_server import NexusSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': str(tmp_path / 'chroma'),
                    'collection_name': 'test'
                },
                'data_dir': str(tmp_path / 'data')
            }
        }

        tool = NexusSearchTool(config)
        assert hasattr(tool, 'lifecycle_manager')
        assert tool.lifecycle_manager is not None


class TestC36QueryTracing:
    """Test C3.6: Query tracing is functional."""

    def test_create_query_trace_method(self, tmp_path):
        """Verify create_query_trace method exists and works."""
        from src.mcp.stdio_server import NexusSearchTool

        config = {
            'embeddings': {'model': 'all-MiniLM-L6-v2'},
            'storage': {
                'vector_db': {
                    'persist_directory': str(tmp_path / 'chroma'),
                    'collection_name': 'test'
                },
                'data_dir': str(tmp_path / 'data')
            }
        }

        tool = NexusSearchTool(config)
        trace = tool.create_query_trace("test query", "execution")

        assert trace is not None
        assert trace.query == "test query"
        assert trace.mode_detected == "execution"


class TestC37Migrations:
    """Test C3.7: Migration auto-apply is functional."""

    def test_apply_migrations_function_exists(self):
        """Verify _apply_migrations function exists."""
        from src.mcp.stdio_server import _apply_migrations
        assert callable(_apply_migrations)

    def test_migrations_applied_on_startup(self, tmp_path):
        """Verify migrations are applied without error."""
        from src.mcp.stdio_server import _apply_migrations

        config = {
            'storage': {
                'data_dir': str(tmp_path / 'data')
            }
        }

        # Should not raise
        _apply_migrations(config)


class TestVersionUpdated:
    """Test version is updated to 1.4.0."""

    def test_version_is_1_4_0(self):
        """Verify version is 1.4.0 for Phase 6."""
        from src import __version__
        assert __version__ == "1.4.0", f"Expected 1.4.0, got {__version__}"


class TestProductionFeaturesSummary:
    """Summary test for all production features."""

    def test_all_production_imports_available(self):
        """Verify all Phase 6 imports are available."""
        from src.mcp.stdio_server import (
            EventLog,
            KVStore,
            QueryTrace,
            HotColdClassifier,
            MemoryLifecycleManager,
            ObsidianMCPClient
        )

        assert EventLog is not None
        assert KVStore is not None
        assert QueryTrace is not None
        assert HotColdClassifier is not None
        assert MemoryLifecycleManager is not None
        assert ObsidianMCPClient is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
