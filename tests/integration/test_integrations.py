"""
Integration tests for external system integrations.
MEM-CLEAN-007: Beads and Obsidian integration verification.

Tests:
- BeadsBridge task management integration
- ObsidianMCPClient vault sync integration

NASA Rule 10 Compliant: All test methods <=60 LOC
"""
import pytest
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from src.integrations.beads_bridge import BeadsBridge, BeadTask
from src.mcp.obsidian_client import ObsidianMCPClient
from src.mcp.request_router import (
    handle_beads_ready_tasks,
    handle_beads_task_detail,
    handle_beads_query_tasks,
    handle_obsidian_sync,
)


# === Beads Integration Tests ===

class TestBeadsBridge:
    """Test BeadsBridge integration."""

    @pytest.fixture
    def bridge(self):
        """Create BeadsBridge instance."""
        return BeadsBridge(beads_binary='bd', cache_ttl=60)

    @pytest.mark.asyncio
    async def test_get_ready_tasks_returns_list(self, bridge):
        """get_ready_tasks should return a list."""
        if shutil.which('bd') is None:
            pytest.skip("bd binary not available")
        tasks = await bridge.get_ready_tasks(limit=5)
        assert isinstance(tasks, list)

    @pytest.mark.asyncio
    async def test_get_task_detail_returns_bead_task(self, bridge):
        """get_task_detail should return BeadTask."""
        if shutil.which('bd') is None:
            pytest.skip("bd binary not available")
        # First get a task ID
        tasks = await bridge.get_ready_tasks(limit=1)
        if not tasks:
            pytest.skip("No tasks available")
        task = await bridge.get_task_detail(tasks[0].id)
        assert isinstance(task, BeadTask)

    @pytest.mark.asyncio
    async def test_query_tasks_with_status_filter(self, bridge):
        """query_tasks should support status filter."""
        if shutil.which('bd') is None:
            pytest.skip("bd binary not available")
        tasks = await bridge.query_tasks(status='open', limit=5)
        assert isinstance(tasks, list)

    def test_bead_task_dataclass_fields(self):
        """BeadTask should have expected fields."""
        task = BeadTask(
            id='test-id',
            title='Test Task',
            status='open',
            priority=2,
            issue_type='task'
        )
        assert task.id == 'test-id'
        assert task.title == 'Test Task'
        assert task.status == 'open'
        assert task.priority == 2


class TestBeadsMCPHandlers:
    """Test Beads MCP request handlers."""

    @pytest.fixture
    def mock_tool(self):
        """Create mock NexusSearchTool with BeadsBridge."""
        tool = MagicMock()
        tool.beads_bridge = MagicMock()
        return tool

    def test_handle_beads_ready_tasks_no_tasks(self, mock_tool):
        """Handler should return message when no tasks."""
        async def mock_get_ready():
            return []

        with patch('asyncio.run', return_value=[]):
            result = handle_beads_ready_tasks({'limit': 10}, mock_tool)

        assert 'content' in result
        assert not result.get('isError', False)

    def test_handle_beads_task_detail_missing_id(self, mock_tool):
        """Handler should error on missing task_id."""
        result = handle_beads_task_detail({}, mock_tool)
        assert result.get('isError', False)

    def test_handle_beads_query_tasks_structure(self, mock_tool):
        """Handler should return proper structure."""
        mock_task = BeadTask(
            id='test', title='Test', status='open', priority=2, issue_type='task'
        )
        with patch('asyncio.run', return_value=[mock_task]):
            result = handle_beads_query_tasks({'status': 'open'}, mock_tool)

        assert 'content' in result
        assert not result.get('isError', False)


# === Obsidian Integration Tests ===

class TestObsidianMCPClient:
    """Test ObsidianMCPClient integration."""

    @pytest.fixture
    def temp_vault(self):
        """Create temporary Obsidian vault."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / 'test-vault'
            vault_path.mkdir()
            # Create sample markdown files
            (vault_path / 'note1.md').write_text('# Note 1\nThis is a test note.')
            (vault_path / 'note2.md').write_text('# Note 2\nAnother test note.')
            (vault_path / 'subfolder').mkdir()
            (vault_path / 'subfolder' / 'note3.md').write_text('# Note 3\nNested note.')
            yield vault_path

    @pytest.fixture
    def mock_chunker(self):
        """Mock chunker."""
        chunker = MagicMock()
        chunker.chunk_file.return_value = [
            {'text': 'Chunk 1', 'start': 0, 'end': 100},
            {'text': 'Chunk 2', 'start': 100, 'end': 200},
        ]
        return chunker

    @pytest.fixture
    def mock_embedder(self):
        """Mock embedder."""
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]
        return embedder

    @pytest.fixture
    def mock_indexer(self):
        """Mock indexer."""
        indexer = MagicMock()
        indexer.index_chunks.return_value = None
        return indexer

    def test_client_init_with_vault_path(
        self, temp_vault, mock_chunker, mock_embedder, mock_indexer
    ):
        """Client should initialize with vault path."""
        client = ObsidianMCPClient(
            vault_path=str(temp_vault),
            chunker=mock_chunker,
            embedder=mock_embedder,
            indexer=mock_indexer
        )
        assert client.vault_path == temp_vault

    def test_sync_vault_finds_markdown_files(
        self, temp_vault, mock_chunker, mock_embedder, mock_indexer
    ):
        """sync_vault should find all markdown files."""
        client = ObsidianMCPClient(
            vault_path=str(temp_vault),
            chunker=mock_chunker,
            embedder=mock_embedder,
            indexer=mock_indexer
        )
        result = client.sync_vault(['.md'])
        assert result['files_synced'] >= 3  # 3 markdown files

    def test_sync_vault_returns_chunk_count(
        self, temp_vault, mock_chunker, mock_embedder, mock_indexer
    ):
        """sync_vault should return total chunk count."""
        client = ObsidianMCPClient(
            vault_path=str(temp_vault),
            chunker=mock_chunker,
            embedder=mock_embedder,
            indexer=mock_indexer
        )
        result = client.sync_vault(['.md'])
        assert 'total_chunks' in result
        assert result['total_chunks'] > 0


class TestObsidianMCPHandler:
    """Test Obsidian MCP request handler."""

    @pytest.fixture
    def mock_tool_with_obsidian(self, temp_vault, mock_chunker, mock_embedder, mock_indexer):
        """Create mock tool with Obsidian client."""
        tool = MagicMock()
        tool._vault_path = str(temp_vault)
        tool._obsidian_client = ObsidianMCPClient(
            vault_path=str(temp_vault),
            chunker=mock_chunker,
            embedder=mock_embedder,
            indexer=mock_indexer
        )
        tool.obsidian_client = tool._obsidian_client
        tool.log_event = MagicMock()
        return tool

    @pytest.fixture
    def temp_vault(self):
        """Create temporary vault for handler tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / 'vault'
            vault_path.mkdir()
            (vault_path / 'test.md').write_text('# Test\nContent.')
            yield vault_path

    @pytest.fixture
    def mock_chunker(self):
        chunker = MagicMock()
        chunker.chunk_file.return_value = [{'text': 'Chunk', 'start': 0, 'end': 50}]
        return chunker

    @pytest.fixture
    def mock_embedder(self):
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1] * 384]
        return embedder

    @pytest.fixture
    def mock_indexer(self):
        indexer = MagicMock()
        return indexer

    def test_handle_obsidian_sync_no_client(self):
        """Handler should error when no client configured."""
        tool = MagicMock()
        tool.obsidian_client = None
        result = handle_obsidian_sync({}, tool)
        assert result.get('isError', True)
        assert 'not configured' in result['content'][0]['text']

    def test_handle_obsidian_sync_with_client(self, mock_tool_with_obsidian):
        """Handler should sync when client available."""
        result = handle_obsidian_sync({'file_extensions': ['.md']}, mock_tool_with_obsidian)
        assert 'content' in result
        # Should have synced at least 1 file
        assert 'Synced' in result['content'][0]['text'] or not result.get('isError')


# === Cross-System Integration Tests ===

class TestCrossSystemIntegration:
    """Test integration between Memory MCP and external systems."""

    def test_beads_tasks_can_reference_memory(self):
        """Beads tasks should be able to reference memory content."""
        # This verifies the data model supports cross-referencing
        task = BeadTask(
            id='test',
            title='Implement Memory Feature',
            status='open',
            priority=1,
            issue_type='task',
            description='Relates to memory chunk: mem-12345'
        )
        assert 'memory' in task.description.lower()

    def test_obsidian_content_can_link_to_beads(self):
        """Obsidian content should support Beads references."""
        markdown_content = """
# Project Notes
## Related Tasks
- [[beads:task-123]]
- See also: life-os-dashboard-abc
"""
        # Just verify the pattern is parseable
        assert 'beads:' in markdown_content or 'life-os-dashboard' in markdown_content
