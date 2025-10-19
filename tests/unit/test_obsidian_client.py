"""
Tests for ObsidianMCPClient (Week 7)

Tests portable vault synchronization.
"""

import pytest
from pathlib import Path
from src.mcp.obsidian_client import ObsidianMCPClient


@pytest.fixture
def mock_vault(tmp_path):
    """Create mock Obsidian vault."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create test files
    (vault / "note1.md").write_text("# Note 1\nContent of note 1")
    (vault / "note2.md").write_text("# Note 2\nContent of note 2")

    subdir = vault / "subfolder"
    subdir.mkdir()
    (subdir / "note3.md").write_text("# Note 3\nNested note")

    return vault


@pytest.fixture
def client(mock_vault):
    """Obsidian MCP client instance."""
    return ObsidianMCPClient(
        vault_path=str(mock_vault),
        api_url="http://localhost:27123"
    )


def test_client_initialization(mock_vault):
    """Test client initializes correctly."""
    client = ObsidianMCPClient(
        vault_path=str(mock_vault),
        api_url="http://localhost:27123"
    )

    assert client.vault_path == mock_vault
    assert client.api_url == "http://localhost:27123"
    assert client.timeout == 30


def test_sync_vault(client):
    """Test syncing entire vault."""
    result = client.sync_vault()

    assert result["success"] is True
    assert result["files_synced"] == 3  # 3 .md files
    assert result["total_chunks"] > 0
    assert isinstance(result["duration_ms"], int)
    assert result["errors"] == []


def test_sync_vault_with_file_extensions(client, mock_vault):
    """Test syncing with specific file extensions."""
    # Create a non-md file
    (mock_vault / "config.json").write_text('{"key": "value"}')

    result = client.sync_vault(file_extensions=[".md"])

    assert result["files_synced"] == 3  # Only .md files


def test_get_vault_stats(client):
    """Test getting vault statistics."""
    stats = client.get_vault_stats()

    assert stats["total_files"] == 3
    assert stats["total_size_bytes"] > 0
    assert ".md" in stats["file_types"]
    assert stats["file_types"][".md"] == 3
    assert stats["last_modified"] is not None


def test_export_to_vault(client, mock_vault):
    """Test exporting memories to vault."""
    chunks = [
        {
            "text": "Memory 1 content",
            "metadata": {"source": "vector", "created_at": "2025-10-18"}
        },
        {
            "text": "Memory 2 content",
            "metadata": {"source": "graph", "created_at": "2025-10-18"}
        }
    ]

    result = client.export_to_vault(chunks, "exported.md")

    assert result["success"] is True
    assert result["chunks_exported"] == 2

    # Verify file was created
    exported_file = mock_vault / "exported.md"
    assert exported_file.exists()

    content = exported_file.read_text()
    assert "Memory 1" in content
    assert "Memory 2" in content


def test_export_to_vault_empty_chunks(client):
    """Test exporting empty chunk list."""
    result = client.export_to_vault([])

    assert result["success"] is True
    assert result["chunks_exported"] == 0


def test_client_with_nonexistent_vault(tmp_path):
    """Test client with non-existent vault path."""
    nonexistent = tmp_path / "nonexistent"

    # Should not raise, just log warning
    client = ObsidianMCPClient(vault_path=str(nonexistent))
    assert client.vault_path == nonexistent
