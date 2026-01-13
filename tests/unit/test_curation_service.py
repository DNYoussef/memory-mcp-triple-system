"""
Unit tests for CurationService
Following TDD (London School) with proper test structure and sandbox validation.
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.services.curation_service import CurationService


class TestCurationServiceInitialization:
    """Test suite for CurationService initialization."""

    @pytest.fixture
    def mock_chroma_client(self):
        """Create mock ChromaDB client."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return client

    def test_initialization_with_existing_collection(self, mock_chroma_client, tmp_path):
        """Test initialization when collection exists."""
        service = CurationService(
            chroma_client=mock_chroma_client,
            collection_name="test_collection",
            data_dir=str(tmp_path)
        )

        assert service.client == mock_chroma_client
        assert service.collection_name == "test_collection"
        mock_chroma_client.get_collection.assert_called_once_with("test_collection")

    def test_initialization_creates_collection_if_not_exists(self, tmp_path):
        """Test initialization creates collection if it doesn't exist."""
        client = MagicMock()
        client.get_collection.side_effect = Exception("Collection not found")

        service = CurationService(
            chroma_client=client,
            collection_name="new_collection",
            data_dir=str(tmp_path)
        )

        client.create_collection.assert_called_once()
        assert service.collection is not None

    def test_initialization_creates_data_directory(self, mock_chroma_client, tmp_path):
        """Test initialization creates data directory."""
        data_dir = tmp_path / "data"

        service = CurationService(
            chroma_client=mock_chroma_client,
            data_dir=str(data_dir)
        )

        assert data_dir.exists()

    def test_initialization_requires_chroma_client(self, tmp_path):
        """Test initialization fails without chroma_client."""
        with pytest.raises(ValueError):
            CurationService(
                chroma_client=None,
                data_dir=str(tmp_path)
            )


class TestGetUnverifiedChunks:
    """Test suite for get_unverified_chunks method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create CurationService with mocked collection."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return CurationService(client, data_dir=str(tmp_path))

    def test_get_unverified_chunks_returns_list(self, service):
        """Test get_unverified_chunks returns list of chunks."""
        service.collection.get.return_value = {
            'ids': ['id1', 'id2'],
            'documents': ['text1', 'text2'],
            'metadatas': [
                {'file_path': '/file1.md', 'chunk_index': 0, 'verified': False},
                {'file_path': '/file2.md', 'chunk_index': 1, 'verified': False}
            ]
        }

        chunks = service.get_unverified_chunks(limit=20)

        assert len(chunks) == 2
        assert chunks[0]['id'] == 'id1'
        assert chunks[0]['text'] == 'text1'
        assert chunks[0]['verified'] is False

    def test_get_unverified_chunks_queries_with_verified_false(self, service):
        """Test query filters for verified=False."""
        service.collection.get.return_value = {'ids': []}

        service.get_unverified_chunks(limit=10)

        service.collection.get.assert_called_once_with(
            where={"verified": False},
            limit=10
        )

    def test_get_unverified_chunks_respects_limit(self, service):
        """Test limit parameter is passed correctly."""
        service.collection.get.return_value = {'ids': []}

        service.get_unverified_chunks(limit=5)

        assert service.collection.get.call_args[1]['limit'] == 5

    def test_get_unverified_chunks_limit_validation(self, service):
        """Test limit must be positive and <=100."""
        with pytest.raises(ValueError):
            service.get_unverified_chunks(limit=0)

        with pytest.raises(ValueError):
            service.get_unverified_chunks(limit=101)


class TestTagLifecycle:
    """Test suite for tag_lifecycle method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create CurationService with mocked collection."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return CurationService(client, data_dir=str(tmp_path))

    def test_tag_lifecycle_permanent(self, service):
        """Test tagging chunk as permanent."""
        result = service.tag_lifecycle('chunk123', 'permanent')

        assert result is True
        service.collection.update.assert_called_once()
        call_args = service.collection.update.call_args
        assert call_args[1]['ids'] == ['chunk123']
        assert call_args[1]['metadatas'][0]['lifecycle'] == 'permanent'

    def test_tag_lifecycle_temporary(self, service):
        """Test tagging chunk as temporary."""
        result = service.tag_lifecycle('chunk456', 'temporary')

        assert result is True
        call_args = service.collection.update.call_args
        assert call_args[1]['metadatas'][0]['lifecycle'] == 'temporary'

    def test_tag_lifecycle_ephemeral(self, service):
        """Test tagging chunk as ephemeral."""
        result = service.tag_lifecycle('chunk789', 'ephemeral')

        assert result is True
        call_args = service.collection.update.call_args
        assert call_args[1]['metadatas'][0]['lifecycle'] == 'ephemeral'

    def test_tag_lifecycle_invalid_tag_fails(self, service):
        """Test invalid lifecycle tag raises assertion."""
        with pytest.raises(ValueError):
            service.tag_lifecycle('chunk123', 'invalid_tag')

    def test_tag_lifecycle_adds_updated_at(self, service):
        """Test tagging adds updated_at timestamp."""
        service.tag_lifecycle('chunk123', 'permanent')

        call_args = service.collection.update.call_args
        assert 'updated_at' in call_args[1]['metadatas'][0]

    def test_tag_lifecycle_handles_errors(self, service):
        """Test tag_lifecycle returns False on error."""
        service.collection.update.side_effect = Exception("DB error")

        result = service.tag_lifecycle('chunk123', 'permanent')

        assert result is False


class TestMarkVerified:
    """Test suite for mark_verified method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create CurationService with mocked collection."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return CurationService(client, data_dir=str(tmp_path))

    def test_mark_verified_updates_metadata(self, service):
        """Test marking chunk as verified."""
        result = service.mark_verified('chunk123')

        assert result is True
        service.collection.update.assert_called_once()
        call_args = service.collection.update.call_args
        assert call_args[1]['ids'] == ['chunk123']
        assert call_args[1]['metadatas'][0]['verified'] is True

    def test_mark_verified_adds_verified_at(self, service):
        """Test verified_at timestamp is added."""
        service.mark_verified('chunk123')

        call_args = service.collection.update.call_args
        assert 'verified_at' in call_args[1]['metadatas'][0]
        assert 'updated_at' in call_args[1]['metadatas'][0]

    def test_mark_verified_handles_errors(self, service):
        """Test mark_verified returns False on error."""
        service.collection.update.side_effect = Exception("DB error")

        result = service.mark_verified('chunk123')

        assert result is False


class TestLogTime:
    """Test suite for log_time method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create CurationService."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return CurationService(client, data_dir=str(tmp_path))

    def test_log_time_creates_file(self, service):
        """Test log_time creates JSON file."""
        service.log_time(duration_seconds=180, chunks_curated=5)

        log_file = service.data_dir / 'curation_time.json'
        assert log_file.exists()

    def test_log_time_appends_to_existing_file(self, service):
        """Test log_time appends to existing log."""
        service.log_time(duration_seconds=60, chunks_curated=2)
        service.log_time(duration_seconds=120, chunks_curated=3)

        log_file = service.data_dir / 'curation_time.json'
        with open(log_file, 'r') as f:
            log = json.load(f)

        assert len(log['sessions']) == 2

    def test_log_time_calculates_stats(self, service):
        """Test log_time calculates statistics."""
        service.log_time(duration_seconds=180, chunks_curated=5)

        log_file = service.data_dir / 'curation_time.json'
        with open(log_file, 'r') as f:
            log = json.load(f)

        assert 'stats' in log
        assert log['stats']['total_time_minutes'] == 3.0
        assert log['stats']['total_chunks'] == 5

    def test_log_time_validation(self, service):
        """Test log_time validates inputs."""
        with pytest.raises(ValueError):
            service.log_time(duration_seconds=-1)

        with pytest.raises(ValueError):
            service.log_time(duration_seconds=60, chunks_curated=-1)


class TestPreferences:
    """Test suite for preferences methods."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create CurationService."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return CurationService(client, data_dir=str(tmp_path))

    def test_get_preferences_returns_defaults(self, service):
        """Test get_preferences returns default preferences."""
        prefs = service.get_preferences()

        assert prefs['user_id'] == 'default'
        assert prefs['time_budget_minutes'] == 5
        assert prefs['auto_suggest'] is True
        assert prefs['batch_size'] == 20

    def test_get_preferences_caches_defaults(self, service):
        """Test default preferences are cached."""
        prefs1 = service.get_preferences()
        prefs2 = service.get_preferences()

        # Should return same object from cache
        assert prefs1 == prefs2

    def test_save_preferences_updates_cache(self, service):
        """Test save_preferences updates cache."""
        new_prefs = {
            'user_id': 'default',
            'time_budget_minutes': 10,
            'auto_suggest': False,
            'weekly_review_day': 'monday',
            'weekly_review_time': '09:00',
            'batch_size': 15,
            'default_lifecycle': 'permanent'
        }

        service.save_preferences('default', new_prefs)
        retrieved_prefs = service.get_preferences('default')

        assert retrieved_prefs['time_budget_minutes'] == 10
        assert retrieved_prefs['auto_suggest'] is False

    def test_save_preferences_validates_required_fields(self, service):
        """Test save_preferences requires all fields."""
        incomplete_prefs = {
            'user_id': 'default',
            'time_budget_minutes': 10
        }

        with pytest.raises(ValueError):
            service.save_preferences('default', incomplete_prefs)


class TestAutoSuggestLifecycle:
    """Test suite for auto_suggest_lifecycle method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create CurationService."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return CurationService(client, data_dir=str(tmp_path))

    def test_auto_suggest_todo_returns_temporary(self, service):
        """Test chunks with TODO return temporary."""
        chunk = {'text': 'TODO: Implement this feature'}
        assert service.auto_suggest_lifecycle(chunk) == 'temporary'

    def test_auto_suggest_fixme_returns_temporary(self, service):
        """Test chunks with FIXME return temporary."""
        chunk = {'text': 'FIXME: This needs fixing'}
        assert service.auto_suggest_lifecycle(chunk) == 'temporary'

    def test_auto_suggest_reference_returns_permanent(self, service):
        """Test chunks with Reference return permanent."""
        chunk = {'text': 'Reference: Important concept definition'}
        assert service.auto_suggest_lifecycle(chunk) == 'permanent'

    def test_auto_suggest_definition_returns_permanent(self, service):
        """Test chunks with Definition return permanent."""
        chunk = {'text': 'Definition: Key term explained here'}
        assert service.auto_suggest_lifecycle(chunk) == 'permanent'

    def test_auto_suggest_short_text_returns_ephemeral(self, service):
        """Test short chunks (<50 words) return ephemeral."""
        chunk = {'text': 'Quick note about something'}
        assert service.auto_suggest_lifecycle(chunk) == 'ephemeral'

    def test_auto_suggest_long_text_returns_permanent(self, service):
        """Test long chunks (>200 words) return permanent."""
        chunk = {'text': ' '.join(['word'] * 250)}
        assert service.auto_suggest_lifecycle(chunk) == 'permanent'

    def test_auto_suggest_default_returns_temporary(self, service):
        """Test default case returns temporary."""
        chunk = {'text': ' '.join(['word'] * 100)}  # 100 words, no keywords
        assert service.auto_suggest_lifecycle(chunk) == 'temporary'


class TestCalculateStats:
    """Test suite for _calculate_stats method."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create CurationService."""
        client = MagicMock()
        collection = MagicMock()
        client.get_collection.return_value = collection
        return CurationService(client, data_dir=str(tmp_path))

    def test_calculate_stats_empty_sessions(self, service):
        """Test calculate_stats with no sessions."""
        stats = service._calculate_stats([])

        assert stats['total_time_minutes'] == 0
        assert stats['avg_time_per_day'] == 0
        assert stats['days_active'] == 0
        assert stats['total_chunks'] == 0

    def test_calculate_stats_single_session(self, service):
        """Test calculate_stats with one session."""
        sessions = [{
            'date': '2025-10-18T10:00:00',
            'duration_seconds': 180,
            'chunks_curated': 5
        }]

        stats = service._calculate_stats(sessions)

        assert stats['total_time_minutes'] == 3.0
        assert stats['days_active'] == 1
        assert stats['total_chunks'] == 5

    def test_calculate_stats_multiple_sessions_same_day(self, service):
        """Test calculate_stats with multiple sessions on same day."""
        sessions = [
            {'date': '2025-10-18T10:00:00', 'duration_seconds': 120, 'chunks_curated': 3},
            {'date': '2025-10-18T11:00:00', 'duration_seconds': 180, 'chunks_curated': 4}
        ]

        stats = service._calculate_stats(sessions)

        assert stats['total_time_minutes'] == 5.0
        assert stats['days_active'] == 1  # Same day
        assert stats['total_chunks'] == 7

    def test_calculate_stats_multiple_days(self, service):
        """Test calculate_stats with sessions across multiple days."""
        sessions = [
            {'date': '2025-10-18T10:00:00', 'duration_seconds': 300, 'chunks_curated': 5},
            {'date': '2025-10-19T10:00:00', 'duration_seconds': 300, 'chunks_curated': 5}
        ]

        stats = service._calculate_stats(sessions)

        assert stats['total_time_minutes'] == 10.0
        assert stats['days_active'] == 2
        assert stats['avg_time_per_day'] == 5.0
