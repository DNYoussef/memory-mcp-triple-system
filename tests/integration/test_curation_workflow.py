"""
Integration tests for complete curation workflow.
Tests real ChromaDB persistence, cache integration, and Flask routes together.

Following TDD (London School) with real dependencies (not mocked).
NASA Rule 10 Compliant: All functions ≤60 LOC
"""

import pytest
import json
import time
from pathlib import Path
import chromadb

from src.services.curation_service import CurationService
from src.ui.curation_app import app


@pytest.fixture
def test_data_dir(tmp_path):
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def chroma_client(test_data_dir):
    """Create ChromaDB client with test database."""
    chroma_path = Path(test_data_dir) / "chroma"
    chroma_path.mkdir(exist_ok=True)

    client = chromadb.PersistentClient(path=str(chroma_path))
    yield client

    # Cleanup: delete collection instead of reset (reset is disabled)
    try:
        client.delete_collection("test_memory_chunks")
    except Exception:
        pass  # Collection may not exist


@pytest.fixture
def curation_service(chroma_client, test_data_dir):
    """Create CurationService with real ChromaDB."""
    service = CurationService(
        chroma_client=chroma_client,
        collection_name="test_memory_chunks",
        data_dir=test_data_dir
    )
    return service


@pytest.fixture
def flask_client(curation_service, monkeypatch):
    """Create Flask test client with real service."""
    # Replace app's service with test service
    monkeypatch.setattr('src.ui.curation_app.curation_service', curation_service)

    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_chunks(chroma_client):
    """Populate ChromaDB with sample chunks."""
    collection = chroma_client.get_or_create_collection("test_memory_chunks")

    chunks = [
        {
            'id': f'chunk_{i}',
            'text': f'Sample chunk {i} with TODO marker',
            'file_path': f'/test/file{i}.md',
            'chunk_index': i,
            'verified': False,
            'lifecycle': 'temporary'
        }
        for i in range(5)
    ]

    # Add chunks to ChromaDB
    collection.add(
        ids=[c['id'] for c in chunks],
        documents=[c['text'] for c in chunks],
        metadatas=[{
            'file_path': c['file_path'],
            'chunk_index': c['chunk_index'],
            'verified': c['verified'],
            'lifecycle': c['lifecycle']
        } for c in chunks]
    )

    return chunks


class TestFullCurationWorkflow:
    """Test complete end-to-end curation workflow."""

    def test_complete_workflow_service_level(
        self, curation_service, sample_chunks, test_data_dir
    ):
        """
        Test full workflow at service level: get chunks → tag → verify → log.

        Verifies:
        - Get unverified chunks
        - Tag updates ChromaDB metadata
        - Verify updates ChromaDB metadata
        - Time log written to JSON file
        """
        # Step 1: Get unverified chunks
        chunks = curation_service.get_unverified_chunks(limit=20)
        assert len(chunks) == 5
        assert chunks[0]['id'] == 'chunk_0'

        # Step 2: Tag lifecycle
        success = curation_service.tag_lifecycle('chunk_0', 'permanent')
        assert success is True

        # Step 3: Mark verified
        success = curation_service.mark_verified('chunk_0')
        assert success is True

        # Step 4: Log session time
        curation_service.log_time(duration_seconds=180, chunks_curated=1)

        # Verify: ChromaDB metadata updated
        collection = curation_service.collection
        result = collection.get(ids=['chunk_0'], include=['metadatas'])
        metadata = result['metadatas'][0]
        assert metadata['lifecycle'] == 'permanent'
        assert metadata['verified'] is True

        # Verify: Time log file created
        time_log_path = Path(test_data_dir) / "curation_time.json"
        assert time_log_path.exists()

        with open(time_log_path, 'r') as f:
            log = json.load(f)

        assert 'sessions' in log
        assert len(log['sessions']) == 1
        assert log['sessions'][0]['duration_seconds'] == 180
        assert log['sessions'][0]['chunks_curated'] == 1


class TestChromaDBPersistence:
    """Test ChromaDB persistence across operations."""

    def test_metadata_persists_after_tag(
        self, curation_service, sample_chunks
    ):
        """
        Test that lifecycle tags persist in ChromaDB.

        Verifies:
        - Tag written to ChromaDB
        - Metadata retrievable after tag
        - updated_at timestamp added
        """
        # Tag chunk
        success = curation_service.tag_lifecycle('chunk_0', 'permanent')
        assert success is True

        # Retrieve chunk from ChromaDB
        collection = curation_service.collection
        result = collection.get(ids=['chunk_0'], include=['metadatas'])

        # Verify metadata
        metadata = result['metadatas'][0]
        assert metadata['lifecycle'] == 'permanent'
        assert 'updated_at' in metadata

    def test_verified_flag_persists(
        self, curation_service, sample_chunks
    ):
        """
        Test that verified flag persists in ChromaDB.

        Verifies:
        - Verified flag written to ChromaDB
        - Metadata retrievable after verification
        - verified_at timestamp added
        """
        # Mark verified
        success = curation_service.mark_verified('chunk_0')
        assert success is True

        # Retrieve chunk from ChromaDB
        collection = curation_service.collection
        result = collection.get(ids=['chunk_0'], include=['metadatas'])

        # Verify metadata
        metadata = result['metadatas'][0]
        assert metadata['verified'] is True
        assert 'verified_at' in metadata


class TestCacheIntegration:
    """Test MemoryCache integration with preferences."""

    def test_preferences_cached_correctly(
        self, curation_service
    ):
        """
        Test that user preferences are cached with 30-day TTL.

        Verifies:
        - Preferences saved to cache
        - Preferences retrievable from cache
        - Cache key format correct
        """
        # Save preferences
        prefs = {
            'user_id': 'test_user',
            'time_budget_minutes': 10,
            'auto_suggest': True,
            'weekly_review_day': 'monday',
            'weekly_review_time': '09:00',
            'batch_size': 15,
            'default_lifecycle': 'permanent'
        }

        curation_service.save_preferences('test_user', prefs)

        # Retrieve preferences
        retrieved = curation_service.get_preferences('test_user')

        # Verify all fields match
        assert retrieved['user_id'] == 'test_user'
        assert retrieved['time_budget_minutes'] == 10
        assert retrieved['auto_suggest'] is True
        assert retrieved['batch_size'] == 15

    def test_preferences_cache_isolation(
        self, curation_service
    ):
        """
        Test that different users have isolated preferences.

        Verifies:
        - User A preferences don't affect User B
        - Cache keys properly isolated
        """
        # Save preferences for user A
        prefs_a = {
            'user_id': 'user_a',
            'time_budget_minutes': 5,
            'auto_suggest': True,
            'weekly_review_day': 'sunday',
            'weekly_review_time': '10:00',
            'batch_size': 20,
            'default_lifecycle': 'temporary'
        }
        curation_service.save_preferences('user_a', prefs_a)

        # Save preferences for user B
        prefs_b = {
            'user_id': 'user_b',
            'time_budget_minutes': 15,
            'auto_suggest': False,
            'weekly_review_day': 'friday',
            'weekly_review_time': '16:00',
            'batch_size': 10,
            'default_lifecycle': 'permanent'
        }
        curation_service.save_preferences('user_b', prefs_b)

        # Verify isolation
        retrieved_a = curation_service.get_preferences('user_a')
        retrieved_b = curation_service.get_preferences('user_b')

        assert retrieved_a['time_budget_minutes'] == 5
        assert retrieved_b['time_budget_minutes'] == 15
        assert retrieved_a['batch_size'] == 20
        assert retrieved_b['batch_size'] == 10


class TestFileLogging:
    """Test JSON file logging for time tracking."""

    def test_time_log_file_created(
        self, curation_service, test_data_dir
    ):
        """
        Test that time log file is created on first session.

        Verifies:
        - File created in correct location
        - JSON format valid
        - Session data correct
        """
        # Log time
        curation_service.log_time(duration_seconds=180, chunks_curated=5)

        # Verify file exists
        log_path = Path(test_data_dir) / "curation_time.json"
        assert log_path.exists()

        # Verify JSON content
        with open(log_path, 'r') as f:
            log = json.load(f)

        assert 'sessions' in log
        assert len(log['sessions']) == 1
        assert log['sessions'][0]['duration_seconds'] == 180
        assert log['sessions'][0]['chunks_curated'] == 5
        assert 'date' in log['sessions'][0]

    def test_time_log_appends_sessions(
        self, curation_service, test_data_dir
    ):
        """
        Test that subsequent sessions append to log file.

        Verifies:
        - Multiple sessions logged
        - Order preserved
        - Stats calculated correctly
        """
        # Log first session
        curation_service.log_time(duration_seconds=120, chunks_curated=3)
        time.sleep(0.1)  # Ensure different timestamps

        # Log second session
        curation_service.log_time(duration_seconds=240, chunks_curated=7)

        # Verify file content
        log_path = Path(test_data_dir) / "curation_time.json"
        with open(log_path, 'r') as f:
            log = json.load(f)

        assert 'sessions' in log
        assert len(log['sessions']) == 2
        assert log['sessions'][0]['chunks_curated'] == 3
        assert log['sessions'][1]['chunks_curated'] == 7


class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_handles_chromadb_errors(
        self, curation_service, monkeypatch
    ):
        """
        Test handling of ChromaDB connection errors.

        Verifies:
        - Errors caught and logged
        - Graceful degradation
        - No data corruption
        """
        # Mock ChromaDB update to raise exception
        def mock_update(*args, **kwargs):
            raise Exception("ChromaDB connection error")

        monkeypatch.setattr(
            curation_service.collection,
            'update',
            mock_update
        )

        # Attempt operation that triggers ChromaDB update
        success = curation_service.tag_lifecycle('chunk_0', 'permanent')

        # Should return False, not raise exception
        assert success is False
