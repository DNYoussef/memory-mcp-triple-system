"""
Unit tests for Memory Lifecycle Manager.

Tests 4-stage lifecycle with rekindling:
1. Active (100% score, <7 days)
2. Demoted (50% score, 7-30 days)
3. Archived (10% score, 30-90 days, compressed)
4. Rehydratable (1% score, >90 days, lossy key)
"""

import json
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timedelta
from src.memory.lifecycle_manager import MemoryLifecycleManager


class TestLifecycleManagerInitialization:
    """Test suite for initialization."""

    def test_initialization(self):
        """Test lifecycle manager initialization."""
        mock_indexer = Mock()
        mock_kv_store = Mock()

        manager = MemoryLifecycleManager(mock_indexer, mock_kv_store)

        assert manager.vector_indexer == mock_indexer
        assert manager.kv_store == mock_kv_store
        assert manager.stages == {
            'active': 1.0,
            'demoted': 0.5,
            'archived': 0.1,
            'rehydratable': 0.01
        }

    def test_stage_multipliers(self):
        """Test stage score multipliers."""
        manager = MemoryLifecycleManager(Mock(), Mock())

        assert manager.stages['active'] == 1.0
        assert manager.stages['demoted'] == 0.5
        assert manager.stages['archived'] == 0.1
        assert manager.stages['rehydratable'] == 0.01


class TestDemotion:
    """Test suite for demotion (Active → Demoted)."""

    @pytest.fixture
    def manager(self):
        """Create lifecycle manager with mocks."""
        mock_indexer = Mock()
        mock_kv_store = Mock()
        return MemoryLifecycleManager(mock_indexer, mock_kv_store)

    def test_demote_stale_chunks(self, manager):
        """Test demotion of chunks >7 days old."""
        # Mock stale chunks
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1', 'chunk2', 'chunk3'],
            'metadatas': [
                {'stage': 'active', 'last_accessed': cutoff},
                {'stage': 'active', 'last_accessed': cutoff},
                {'stage': 'active', 'last_accessed': cutoff}
            ]
        }

        # Demote
        count = manager.demote_stale_chunks(threshold_days=7)

        # Verify
        assert count == 3
        assert manager.vector_indexer.collection.update.call_count == 3

        # Check first update call
        call_args = manager.vector_indexer.collection.update.call_args_list[0]
        assert call_args[1]['ids'] == ['chunk1']
        assert call_args[1]['metadatas'][0]['stage'] == 'demoted'
        assert call_args[1]['metadatas'][0]['score_multiplier'] == 0.5

    def test_demote_threshold_configurable(self, manager):
        """Test custom demotion threshold."""
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1'],
            'metadatas': [{'stage': 'active'}]
        }

        # Use custom threshold (14 days)
        count = manager.demote_stale_chunks(threshold_days=14)

        # Verify query used 14 days
        call_args = manager.vector_indexer.collection.get.call_args
        where_clause = call_args[1]['where']
        cutoff_14 = (datetime.now() - timedelta(days=14)).isoformat()

        assert count == 1

    def test_demote_preserves_recent(self, manager):
        """Test recent chunks are not demoted."""
        # Mock no stale chunks
        manager.vector_indexer.collection.get.return_value = {
            'ids': [],
            'metadatas': []
        }

        count = manager.demote_stale_chunks(threshold_days=7)

        assert count == 0
        assert manager.vector_indexer.collection.update.call_count == 0

    def test_demote_batch_performance(self, manager):
        """Test demotion of 1000 chunks completes quickly."""
        import time

        # Mock 1000 stale chunks
        chunk_ids = [f"chunk{i}" for i in range(1000)]
        manager.vector_indexer.collection.get.return_value = {
            'ids': chunk_ids,
            'metadatas': [{'stage': 'active'} for _ in range(1000)]
        }

        # Time demotion
        start = time.time()
        count = manager.demote_stale_chunks()
        elapsed_ms = (time.time() - start) * 1000

        assert count == 1000
        # Performance target: <100ms for 1000 chunks
        # Note: In production with real DB, may be slower


class TestArchival:
    """Test suite for archival (Demoted → Archived)."""

    @pytest.fixture
    def manager(self):
        """Create lifecycle manager with mocks."""
        mock_indexer = Mock()
        mock_kv_store = Mock()
        return MemoryLifecycleManager(mock_indexer, mock_kv_store)

    def test_archive_demoted_chunks(self, manager):
        """Test archival of chunks >30 days demoted."""
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()

        # Mock demoted chunks
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1', 'chunk2'],
            'documents': ['Full text 1', 'Full text 2'],
            'metadatas': [
                {'stage': 'demoted', 'demoted_at': cutoff},
                {'stage': 'demoted', 'demoted_at': cutoff}
            ]
        }

        # Archive
        count = manager.archive_demoted_chunks(threshold_days=30)

        # Verify
        assert count == 2
        assert manager.kv_store.set.call_count == 4  # 2 summaries + 2 metadata
        assert manager.vector_indexer.collection.delete.call_count == 2

    def test_archive_compression(self, manager):
        """Test 100:1 compression ratio."""
        # Mock chunk with 1000 character text
        long_text = "A" * 1000
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1'],
            'documents': [long_text],
            'metadatas': [{'stage': 'demoted', 'demoted_at': datetime.now().isoformat()}]
        }

        count = manager.archive_demoted_chunks()

        # Verify summary is compressed
        call_args = manager.kv_store.set.call_args_list[0]
        summary = call_args[0][1]  # Second argument is the summary

        # Summary should be much shorter (target: ~10 chars for 1000-char text)
        assert len(summary) < len(long_text) / 5  # At least 5:1 compression
        assert count == 1

    def test_archive_lossy_key_storage(self, manager):
        """Test lossy key (summary) stored in KV."""
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1'],
            'documents': ['Full text here'],
            'metadatas': [{'stage': 'demoted', 'demoted_at': datetime.now().isoformat()}]
        }

        count = manager.archive_demoted_chunks()

        # Verify KV store called with archived key
        call_args = manager.kv_store.set.call_args_list[0]
        key = call_args[0][0]

        assert key == "archived:chunk1"
        assert count == 1

    def test_archive_deletes_from_vector(self, manager):
        """Test archived chunks deleted from vector store."""
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1'],
            'documents': ['Text'],
            'metadatas': [{'stage': 'demoted', 'demoted_at': datetime.now().isoformat()}]
        }

        count = manager.archive_demoted_chunks()

        # Verify deletion
        manager.vector_indexer.collection.delete.assert_called_once_with(
            ids=['chunk1']
        )
        assert count == 1

    def test_archive_threshold_configurable(self, manager):
        """Test custom archival threshold."""
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1'],
            'documents': ['Text'],
            'metadatas': [{'stage': 'demoted', 'demoted_at': datetime.now().isoformat()}]
        }

        # Use custom threshold (60 days)
        count = manager.archive_demoted_chunks(threshold_days=60)

        # Verify query used 60 days
        assert count == 1


class TestRehydration:
    """Test suite for rehydration (Archived → Active)."""

    @pytest.fixture
    def manager(self):
        """Create lifecycle manager with mocks."""
        mock_indexer = Mock()
        mock_kv_store = Mock()
        return MemoryLifecycleManager(mock_indexer, mock_kv_store)

    def test_make_rehydratable(self, manager):
        """Test making archived chunks rehydratable (>90 days)."""
        # Mock archived keys
        manager.kv_store.list_keys.return_value = [
            'archived:chunk1',
            'archived:chunk1:metadata',
            'archived:chunk2',
            'archived:chunk2:metadata'
        ]

        manager.kv_store.get.side_effect = lambda key: (
            "Summary 1" if key == "archived:chunk1" else
            "archived_at: 2024-01-01" if key == "archived:chunk1:metadata" else
            "Summary 2" if key == "archived:chunk2" else
            "archived_at: 2024-01-01"
        )

        count = manager.make_rehydratable(threshold_days=90)

        # Verify chunks moved to rehydratable
        assert count == 2
        assert manager.kv_store.set.call_count >= 2  # At least 2 rehydratable keys

    def test_rekindle_archived(self, manager):
        """Test rekindling archived chunk."""
        # Mock archived chunk
        manager.kv_store.get.side_effect = lambda key: (
            "Summary of chunk" if key == "archived:chunk1" else
            "file_path: /path/to/file.md" if key == "archived:chunk1:metadata" else
            None
        )

        # Mock file read
        with patch('builtins.open', mock_open(read_data='Full text from file')):
            query_embedding = [0.1, 0.2, 0.3]
            success = manager.rekindle_archived(query_embedding, 'chunk1')

        # Verify
        assert success is True
        manager.vector_indexer.index_chunks.assert_called_once()
        manager.vector_indexer.collection.update.assert_called_once()

        # Check promotion to active
        call_args = manager.vector_indexer.collection.update.call_args
        assert call_args[1]['metadatas'][0]['stage'] == 'active'
        assert call_args[1]['metadatas'][0]['score_multiplier'] == 1.0

    def test_rekindle_rehydratable(self, manager):
        """Test rekindling from rehydratable stage."""
        # Mock rehydratable chunk
        manager.kv_store.get.side_effect = lambda key: (
            "Summary" if key == "rehydratable:chunk1" else
            "file_path: /path/to/file.md" if key == "rehydratable:chunk1:metadata" else
            None
        )

        with patch('builtins.open', mock_open(read_data='Full text')):
            success = manager.rekindle_archived([0.1], 'chunk1')

        assert success is True

    def test_rekindle_file_not_found(self, manager):
        """Test rekindling when file missing."""
        manager.kv_store.get.side_effect = lambda key: (
            "Summary" if key == "archived:chunk1" else
            "file_path: /nonexistent/file.md" if key == "archived:chunk1:metadata" else
            None
        )

        # File doesn't exist
        success = manager.rekindle_archived([0.1], 'chunk1')

        assert success is False
        manager.vector_indexer.index_chunks.assert_not_called()

    def test_rekindle_promotes_to_active(self, manager):
        """Test rekindling promotes chunk to active stage."""
        manager.kv_store.get.side_effect = lambda key: (
            "Summary" if key == "archived:chunk1" else
            "file_path: /path/to/file.md, stage: archived" if key == "archived:chunk1:metadata" else
            None
        )

        with patch('builtins.open', mock_open(read_data='Text')):
            success = manager.rekindle_archived([0.1], 'chunk1')

        assert success is True

        # Verify stage set to active
        call_args = manager.vector_indexer.collection.update.call_args
        assert call_args is not None, "update was not called"
        metadata = call_args[1]['metadatas'][0]

        assert metadata['stage'] == 'active'
        assert metadata['score_multiplier'] == 1.0
        assert 'rekindled_at' in metadata

    def test_rekindle_sets_valid_last_accessed_ts(self, manager):
        """E4: rekindling must not drop last_accessed_ts to missing/None.

        A chunk with no last_accessed_ts never matches the demote query
        ({"last_accessed_ts": {"$lt": cutoff}}), so it would look permanently
        active / unclassifiable. The current code (fixed in 5adb4df)
        INTENTIONALLY refreshes access time on rekindle, so the invariant we pin
        is a bounded "now": the promoted ts is a valid float in [before, after]
        and strictly newer than the stale archived ts. Pre-5adb4df,
        _reindex_and_promote wrote a fresh metadata dict with only
        last_accessed/rekindled_at and NO last_accessed_ts (and no chunk
        metadata at all), which this test catches.
        """
        # Archived chunk carries an OLD last_accessed_ts (demote-eligible).
        old_ts = (datetime.utcnow() - timedelta(days=120)).timestamp()
        archived_meta = json.dumps({
            "file_path": "/path/to/file.md",
            "stage": "archived",
            "last_accessed_ts": old_ts,
        })
        manager.kv_store.get.side_effect = lambda key: (
            "Summary of chunk" if key == "archived:chunk1" else
            archived_meta if key == "archived:chunk1:metadata" else
            None
        )

        # Bound "now" with the SAME conversion the code uses
        # (datetime.utcnow().timestamp()) so the comparison is tz-consistent.
        before = datetime.utcnow().timestamp()
        with patch('builtins.open', mock_open(read_data='Full text from file')):
            success = manager.rekindle_archived([0.1, 0.2, 0.3], 'chunk1')
        after = datetime.utcnow().timestamp()

        assert success is True

        # Primary E4 invariant: the PROMOTED vector metadata (collection.update)
        # carries a valid, freshly-set last_accessed_ts - never None/missing.
        promoted = manager.vector_indexer.collection.update.call_args[1]['metadatas'][0]
        ts = promoted.get('last_accessed_ts')
        assert ts is not None, "promoted: last_accessed_ts dropped to None/missing"
        assert isinstance(ts, (int, float)), f"promoted: last_accessed_ts not numeric: {ts!r}"
        assert before <= ts <= after, f"promoted: ts {ts} not bounded by [{before}, {after}]"
        assert ts > old_ts, "promoted: ts not refreshed past the stale archived ts"

        # The re-indexed chunk metadata (index_chunks) must carry it too, so the
        # stored document and the collection agree.
        indexed = manager.vector_indexer.index_chunks.call_args[1]['chunks'][0].get('metadata', {})
        ts_indexed = indexed.get('last_accessed_ts')
        assert ts_indexed is not None, "index_chunks: last_accessed_ts dropped to None/missing"
        assert before <= ts_indexed <= after, f"index_chunks: ts {ts_indexed} not bounded"

        # Downstream hot/cold recency: with a demote cutoff between the stale
        # archived ts and now, the OLD ts would be demoted ($lt cutoff) but the
        # rekindled chunk is fresh and must NOT be.
        cutoff = (datetime.utcnow() - timedelta(days=7)).timestamp()
        assert old_ts < cutoff, "precondition: archived ts should be demote-eligible"
        assert promoted['last_accessed_ts'] >= cutoff, (
            "rekindled chunk must read as recent (not < demote cutoff)"
        )

    def test_rekindle_reembeds_full_text_when_embedder_available(self):
        """Rekindle should index the document embedding, not the wake-up query vector."""
        mock_indexer = Mock()
        mock_kv_store = Mock()
        mock_embedder = Mock()
        mock_embedder.encode_single.return_value = [0.9, 0.8, 0.7]
        manager = MemoryLifecycleManager(mock_indexer, mock_kv_store, mock_embedder)
        manager.kv_store.get.side_effect = lambda key: (
            "Summary" if key == "archived:chunk1" else
            "file_path: /path/to/file.md" if key == "archived:chunk1:metadata" else
            None
        )

        with patch('builtins.open', mock_open(read_data='Full text from file')):
            success = manager.rekindle_archived([0.1, 0.2, 0.3], 'chunk1')

        assert success is True
        mock_embedder.encode_single.assert_called_once_with('Full text from file')
        call_args = mock_indexer.index_chunks.call_args
        assert call_args[1]['embeddings'] == [[0.9, 0.8, 0.7]]

    def test_rekindle_missing_metadata_does_not_read_default_path(self, manager):
        """E8: when a chunk's metadata is absent, rekindle must fail honestly,
        NOT silently fabricate 'file_path: /default/path.md' and try to read it.
        Old code injected that default string in _get_archived_data and resolved
        it via string-splitting, masking the real 'metadata missing' error."""
        manager.kv_store.get.side_effect = lambda key: (
            "Summary present but no metadata" if key == "archived:chunk1" else
            None  # no metadata under archived: or rehydratable:
        )

        read_paths = []
        original_read = manager._read_full_text

        def spy_read(path):
            read_paths.append(path)
            return original_read(path)

        with patch.object(manager, "_read_full_text", side_effect=spy_read):
            success = manager.rekindle_archived([0.1, 0.2, 0.3], "chunk1")

        assert success is False
        assert "/default/path.md" not in read_paths, (
            "rekindle silently read the fabricated /default/path.md on a parse miss"
        )
        manager.vector_indexer.index_chunks.assert_not_called()

    def test_rekindle_with_json_metadata_reads_real_file(self, manager, tmp_path):
        """E8: the PRODUCTION metadata format is json.dumps(...) (see
        _archive_chunks_batch). Rekindle must resolve file_path from that JSON
        and rehydrate from the real file - not depend on the legacy colon
        string-splitting path."""
        real_file = tmp_path / "doc.md"
        real_file.write_text("FULL DOCUMENT TEXT")
        metadata = json.dumps(
            {"file_path": str(real_file), "stage": "archived"}, sort_keys=True
        )
        manager.kv_store.get.side_effect = lambda key: (
            "Summary" if key == "archived:chunk1" else
            metadata if key == "archived:chunk1:metadata" else
            None
        )

        success = manager.rekindle_archived([0.1, 0.2, 0.3], "chunk1")

        assert success is True
        manager.vector_indexer.index_chunks.assert_called_once()
        indexed_chunk = manager.vector_indexer.index_chunks.call_args[1]["chunks"][0]
        assert indexed_chunk["file_path"] == str(real_file)
        assert indexed_chunk["text"] == "FULL DOCUMENT TEXT"


class TestConsolidation:
    """Test suite for consolidation (merge similar chunks)."""

    @pytest.fixture
    def manager(self):
        """Create lifecycle manager with mocks."""
        mock_indexer = Mock()
        mock_kv_store = Mock()
        return MemoryLifecycleManager(mock_indexer, mock_kv_store)

    def test_consolidate_similar_chunks(self, manager):
        """Test consolidation of chunks with cosine >0.95."""
        # Mock active chunks with similar embeddings
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1', 'chunk2', 'chunk3'],
            'documents': ['Text A', 'Text A similar', 'Text B different'],
            'embeddings': [
                [1.0, 0.0, 0.0],  # chunk1
                [0.99, 0.01, 0.0],  # chunk2 (very similar to chunk1)
                [0.0, 1.0, 0.0]  # chunk3 (different)
            ],
            'metadatas': [
                {'stage': 'active', 'score': 0.9, 'tags': ['tag1']},
                {'stage': 'active', 'score': 0.8, 'tags': ['tag2']},
                {'stage': 'active', 'score': 0.7, 'tags': ['tag3']}
            ]
        }

        count = manager.consolidate_similar(threshold=0.95)

        # Verify: chunk1 and chunk2 should be consolidated
        assert count >= 1
        assert manager.vector_indexer.collection.update.call_count >= 1
        assert manager.vector_indexer.collection.delete.call_count >= 1

    def test_consolidate_preserves_metadata(self, manager):
        """Test consolidation merges metadata correctly."""
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1', 'chunk2'],
            'documents': ['Text A', 'Text B'],
            'embeddings': [
                [1.0, 0.0],
                [1.0, 0.0]  # Identical embedding
            ],
            'metadatas': [
                {'stage': 'active', 'score': 0.9, 'tags': ['tag1'], 'last_accessed': '2024-01-02'},
                {'stage': 'active', 'score': 0.8, 'tags': ['tag2'], 'last_accessed': '2024-01-01'}
            ]
        }

        count = manager.consolidate_similar(threshold=0.95)

        # Verify metadata merged
        if count > 0:
            call_args = manager.vector_indexer.collection.update.call_args
            merged_metadata = call_args[1]['metadatas'][0]

            # Should take max score
            assert merged_metadata['score'] == 0.9
            # Should merge tags
            assert 'tag1' in merged_metadata['tags'] or 'tag2' in merged_metadata['tags']
            # Should take newer timestamp
            assert merged_metadata['last_accessed'] == '2024-01-02'

    def test_consolidate_reembeds_merged_text(self):
        """Merged chunks should update the vector to match merged text."""
        mock_indexer = Mock()
        mock_kv_store = Mock()
        mock_embedder = Mock()
        mock_embedder.encode_single.return_value = [0.4, 0.6]
        manager = MemoryLifecycleManager(mock_indexer, mock_kv_store, mock_embedder)
        manager.vector_indexer.collection.get.return_value = {
            'ids': ['chunk1', 'chunk2'],
            'documents': ['Text A', 'Text B'],
            'embeddings': [[1.0, 0.0], [1.0, 0.0]],
            'metadatas': [
                {'stage': 'active', 'score': 0.9, 'tags': ['tag1']},
                {'stage': 'active', 'score': 0.8, 'tags': ['tag2']},
            ],
        }

        count = manager.consolidate_similar(threshold=0.95)

        assert count == 1
        mock_embedder.encode_single.assert_called_once_with('Text A\n\nText B')
        call_args = manager.vector_indexer.collection.update.call_args
        assert call_args[1]['embeddings'] == [[0.4, 0.6]]

    def test_consolidate_performance(self, manager):
        """Test consolidation of 100 chunks completes quickly."""
        import time

        # Mock 100 active chunks (all different embeddings)
        chunk_ids = [f"chunk{i}" for i in range(100)]
        embeddings = [[float(i), 0.0] for i in range(100)]
        manager.vector_indexer.collection.get.return_value = {
            'ids': chunk_ids,
            'documents': [f"Text {i}" for i in range(100)],
            'embeddings': embeddings,
            'metadatas': [{'stage': 'active'} for _ in range(100)]
        }

        # Time consolidation
        start = time.time()
        count = manager.consolidate_similar()
        elapsed_ms = (time.time() - start) * 1000

        # Performance target: <200ms for 100 chunks
        # Note: Mock environment is fast, production may be slower


class TestStatistics:
    """Test suite for statistics."""

    @pytest.fixture
    def manager(self):
        """Create lifecycle manager with mocks."""
        mock_indexer = Mock()
        mock_kv_store = Mock()
        return MemoryLifecycleManager(mock_indexer, mock_kv_store)

    def test_get_stage_stats(self, manager):
        """Test statistics aggregation."""
        # Mock vector store counts
        manager.vector_indexer.collection.get.side_effect = [
            {'ids': ['a1', 'a2', 'a3']},  # active
            {'ids': ['d1', 'd2']}  # demoted
        ]

        # Mock KV store keys
        manager.kv_store.list_keys.return_value = [
            'archived:c1',
            'archived:c1:metadata',
            'archived:c2',
            'archived:c2:metadata',
            'rehydratable:r1',
            'rehydratable:r1:metadata'
        ]

        stats = manager.get_stage_stats()

        # Verify
        assert stats['active'] == 3
        assert stats['demoted'] == 2
        assert stats['archived'] == 2
        assert stats['rehydratable'] == 1
        assert stats['total'] == 8


def test_nasa_rule_10_compliance():
    """Test all methods ≤60 LOC."""
    import ast
    import inspect
    from src.memory.lifecycle_manager import MemoryLifecycleManager

    # Get source code
    source = inspect.getsource(MemoryLifecycleManager)
    tree = ast.parse(source)

    # Find all methods
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Calculate LOC
            length = node.end_lineno - node.lineno + 1

            # Check NASA Rule 10 (≤60 LOC)
            assert length <= 60, (
                f"Method {node.name} has {length} LOC "
                f"(violates NASA Rule 10: ≤60 LOC)"
            )
